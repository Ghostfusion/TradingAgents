# Implementation Plan: quant decision arbitration — calibration + vendor reconciliation + hard-gate composition

Status: **PLAN** (no code change yet). Proposal from researched review
(working-agreement rule 7 + external review of TJX market.md).
Companion: `docs/design_report_verification_llm.md` (verifier), `docs/review_parent_tauricradingagents.md`.

Target deliverable: turn the four-reviewed "signal arbitration / confidence
scoring / data-quality controls / hard-gate precedence" pillars into code we
already have — most primitives exist; this plan CONNECTS them.

## Current state (grounded, 2026-09-08)

| Asset | Where | Gap |
| --- | --- | --- |
| Bucket calibration | `strategies/calibration.py` (`fit_buckets`, `calibrated_confidence`, `record_calibration_entry`) wired in `graph/trading_graph.py` (PM confidence, behind `enable_calibration` default False) | Bucket win-rates only (no isotonic/Platt, no per-regime, not fed to **sizing** or **consensus weights**) |
| Prediction ledger | `strategies/prediction_ledger.py` — logs rating/direction/entry/stop/confidence/horizon + realized outcome | Not connected into per-regime calibration loop |
| Ensemble | `strategies/consensus.py` (`agreement_score`, `consensus_from_score`) | Equal-weight only; no rolling OOS weights; no thresholded-consensus HOLD |
| Evidence leaves | `agents/utils/evidence_gather.py::ToolEvidenceLeaf` (`tool`, `args`, `args_hash`, `content`, `status`, `ts`) | No **vendor** / **metric-key** / **quality** field; same-metric-differs (TJX DCF 80.76 vs 80.60) only caught post-hoc by verifier `_internal_conflicts` |
| Risk gates | `risk_governor.govern()` (PASS/WARN/REJECT) + this session's `get_composed_risk_gate` (portfolio>trade) | No hard kill-switch tier beyond `halted` flag; precedence not enforced *in the graph*, only via tool output |

## Phase 1 — Gather-time metric reconciliation (data quality, highest leverage)

**Goal**: move the TJX-class internal conflict from "detected after reduce" to
"prevented at ingest": cluster same-metric leaves from multiple vendors and
either reconcile to a canonical band or tag conflict BEFORE the analyst reduces.

**Files**: `agents/utils/evidence_gather.py` (leaf shape + `_render_evidence`),
new `strategies/metric_reconcile.py` (pure).

- `METRIC_KEY` map: tool-name/args → canonical metric id (e.g. `get_dcf_valuation`
  → `dcf`, `get_ratios.Market cap` + `get_fundamentals.Market Cap` →
  `market_cap`). Exact-match map only (conservative).
- Extend `ToolEvidenceLeaf` with optional `metric` + `vendor` fields (from
  `VendorResult` metadata when present; else `unknown`).
- `reconcile_metrics(leaves) -> dict[metric -> {values, span, conflict: bool}]`:
  group leaves by metric, if >1 distinct value outside tolerance → mark
  `status="conflict"`, render into the evidence block:
  `"[reconcile] DCF fair value: 80.76 (get_dcf_valuation) / 80.60 (?); VALUES CONFLICT — verify before citing"`.
- `_format_evidence_block` appends the reconcile clause; `tool_evidence.json`
  persists the metric/vendor keys so the verifier + repro_check can consume.
- Analyst prompt (each analyst's system message): "when the evidence block
  marks a metric as CONFLICT, quote the range or say 'vendor conflict'; never
  pick one silently".

**Acceptance**: on the TJX tree, `get_dcf_valuation`/EPV/market-cap now render a
`CONFLICT` reconcile line; an analyst citing one lone value of a conflicted
metric becomes verifier-visible. Pure-function tests (no LLM).

## Phase 2 — Calibrated confidence everywhere (confidence scoring)

**Goal**: make confidence tradable.

**Files**: `strategies/calibration.py`, `strategies/prediction_ledger.py`,
`graph/trading_graph.py` (PM), `strategies/size.py`.

1. **Per-regime calibration buckets**: extend `fit_buckets` to accept a
   `regime` partition (from `regime_state`/`regime.py` label), store
   `{regime: {...bins}}`. `calibrated_confidence(declared, table, regime)`.
2. **Isotonic/Platt**: add an optional `calibrator` fit (`strategies/calibration.py`, sklearn import lazy — hermetric-safe) on the ledger rows when `len>=500`, else bucket; keep bucket as the base path. This matches the field's practice (Platt sparse / isotonic ~500+).
3. **Wire into sizing**: `get_position_sizing` (Kelly + risk budget) accepts an
   optional `calibrated_p`; when `enable_calibration` on, PM uses
   `calibrated_confidence(pm.confidence, regime)` instead of raw `confidence`
   for the size calcs + the existing judge-uncertainty cap (extend the pattern
   at `trading_graph.py:1962`).
4. **Wire into consensus**: Phase below.

**Acceptance**: with `enable_calibration=true` + a ledger file, a PM confidence
of 0.9 whose bucket says 0.45 maps to 0.45 in sizing; test via pure
`calibrated_confidence` + one hermfetic regression.

## Phase 3 — Weighted + thresholded consensus (signal arbitration)

**Files**: `strategies/consensus.py`, `agents/utils/independent_vote.py`,
`agents/managers/portfolio_manager.py`.

- `weighted_consensus(stances: [(rating_number, weight)], agreement) → (score, consensus)`:
  replace `agreement_score`'s equal-weight with a weight per analyst:
  default equal; when `enable_calibration` on, weight ∝ inverse-calibration-error
  (hit rate per agent from `scorecard`), refit walking-forward.
- `should_hold(score, threshold)`: `|score| < threshold` → HOLD/watch — the
  reviewer's "thresholded consensus" — with threshold default 0.25 (config).
- PM prompt: "a consensus below threshold is HOLD; never force a direction from
  a sub-threshold signal" (+ advisory, `enable_consensus_threshold` default off).

**Acceptance**: pure tests on weighted/map-hold; PM prompt regression (the flags).

## Phase 4 — Hard-gate composition in the graph (hard-gate precedence)

**Files**: `strategies/decision_guardrail.py` (existing degrade-only stabilizer),
`strategies/risk_governor.py`, `agents/utils/analysis_tools.py:get_composed_risk_gate`
(shipped), `graph/trading_graph.py`.

- **Compose in code, not just tool**: a `risk_hierarchy(state_dict) → (verdict,
  blocker)` calculator that walks, earliest-block wins:
  kill-switch (`halted`) → portfolio drawdown (composed gate) → liquidity
  (`ILLIQUID`) → size/capital cap → regime veto. The COMPOSED tool already
  applies the top 2; run the kill-switch + size caps through the same resolver.
- **Kill-switch tier**: config `risk_kill_switch_dayloss_pct` (soft) → set
  `halted` in state; hard panics stop new entries (mirror `risk_governor.halted`)
  — a persistent escalation state, default off.
- **Wire into final action**: the PM's `HOLD / BUY / ...` maps to a composed
  `port_gate / trade_gate / setup / trigger` verdict in `decision_guardrail`
  (advisory block in `decision.md`, no execution change by default).

**Acceptance**: hermfetic: given a state with `halt=True` or drawdown over limit,
`riskHierarchy` returns the earliest blocker; tool output + `decision.md`
advisory block shows the precedence chain.

## Phase 4 — Walk-forward validation harness (make it measurable)

- `scripts/calibration_walkforward.py --ledger <jsonl> [--regime-field]`:
  in-sample fit → calibration build → OOS eval (reliability, ECE, Brier)
  per regime; prints the curve + a recommendation. Pure (consumes
  prediction_ledger rows only; no live data).
- Outputs an auditable calibration-report (json+md) the user can read.

## Tests

- `tests/test_metric_reconcile.py` (pure: grouping, conflict tag, no-fp when consistent)
- `tests/test_calibration_regime.py` (pure: regime buckets + isotonic)
- `tests/test_consensus_weighted.py` (pure: weights + threshold-HOLD)
- `tests/test_risk_hierarchy.py` (pure: ordering, kill-switch first)
- Every new test with `pytestmark = pytest.mark.timeout(...)`; ruff clean.

## Defaults / safety

- All new behavior behind existing/additional config flags, default **OFF**
  (bit-identical pipeline until enabled): `enable_calibration`,
  `enable_consensus_threshold`, `enable_metric_reconcile`, `risk_enabled`.
- Tool + leaf metadata is additive; old `toolevidence.json` files parse.

## Ordering / dependencies

1. Phase 1 (reconcile) — independent, highest user-facing value.
2. Phase 2 (calibration loop) — depends only on existing ledger.
3. Phase 3 (ensemble) — depends on Phase 2 weights.
4. Phase 4 (compose + guillotine) — independent; largest new architecture.

(Phases 2 + 4 can swap; 1 and 3 mostly after those.)

## Not in scope (design decision; see design doc)

- Changing the saved-report format beyond additive evidence fields.
- Any auto-rewriting of analyst marks; reconcile/calibration/consequences are
  disclosure-first, not silent edits.
- Web UI knobs (the web app mirrors flags when added).
- No execution of real trades — all advisory.

## What it buys (measurable)

- Analyst citation of a reconciled metric → verifier-stable.
- Confidence → tradable (sizing + %), lowers the "verbally confident but
  miscalibrated" risk that the field flags as #1.
- Disagreement → thresholded HOLD (fewer forced calls).
- Drawdown/halt → always first, in composer.