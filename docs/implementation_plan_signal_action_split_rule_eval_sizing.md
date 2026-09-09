# Implementation Plan: security-signal/action split + rule evaluation + position-sizing composite

Status: **PLAN** (no code change yet). Proposed from the 40-point external
review of the SKHY market.md (evidence-first; the two already-shipped P0s —
insufficient-history flagging and options OI convention disclosure, commits
`2ac9d01`/`51e5b1b` — came out of the same review). Companion:
`docs/design_report_verification_llm.md` (verifier), `docs/implementation_plan_quant_decision_arbitration.md`
(hard gates + calibration), `AGENT_ONBOARDING.md` rule 8 (verify → adjudicate).

## Target

Take three of the review's highest-leverage asks from "architecture exists in
pieces" to "single visible output":

1. **Security signal vs portfolio action** — the review's #1/#21: a report
   currently ends in one `HOLD` label that carries both "the stock is
   bullish" and "the portfolio says no new risk". Split into two explicit
   outputs fed by two independent layers (signal engine vs composed risk
   gate).
2. **Position-sizing composite** — the review's #33: size =
   f(expected return, volatility, confidence, liquidity, portfolio DD),
   computed once and surfaced as `recommended_position_pct`.
3. **Per-rule forward-return evaluation** — the review's #11/#12/#13: measure
   which rules actually predict forward 1/5/10/20-day returns over the
   prediction ledger, so the indicator set stops being an untested pile.

All advisory / explicitly labeled; nothing gates by default beyond the
existing composed-risk gate (which already outranks everything).

## Current state (grounded, 2026-09-09)

| Asset | Where | Gap |
| --- | --- | --- |
| Security-level signal | `research_decision.json`: `rating`, `direction`, `recommended_allocation_pct`, `confidence`-adjacent fields (see `decision_hash` schema) | The signal and the portfolio veto collapse into the final `rating`; no separate "thesis is bullish" vs "portfolio says wait" fields |
| Composed risk gate | `get_composed_risk_gate` (`kill > portfolio > trade > liquidity > regime > data`), `kill_switch_state`, live proof TJX reject | Precedence is enforced in the TOOL; the graph/decision only records the final REJECT, not the signal that was overridden |
| Position sizing | `get_position_sizing (Kelly + risk budget + stop)` + `get_position_risk_multiplier` (regime/vol/knife factor) + `tranche_plan` | Disconnected: Kelly, risk-multiplier and liquidity are each computed but no single `recommended_position_pct` composites them with the gate |
| Rule evidence | `strategies/prediction_ledger.py` (`predictions.jsonl`: rating/direction/…/outcome/MAE/MFE/hit/stop/target) + `scripts/alpha_health.py` | Ledger logs DECISIONS; no per-RULE forward-return table (RSI>70 alone vs RSI+MACD+volume conditional) so nothing tells you which indicator additions help |
| Insufficient-history metadata | NEW in the verified snapshot (per-indicator `(insufficient history: N/MIN)`) | Not yet joined into sizing/confidence adjustments (an "uncertainty penalty", review #37) |

## Phase 1 — security_signal / portfolio_action split (visibility, smallest)

**Goal**: every report ends with two explicit, machine-readable fields so a
bullish signal is never buried under a portfolio veto.

**Files**: `agents/utils/` (decision render / `SignalProcessor`), new pure
`strategies/signal_action.py` (advisory splitter); graph snapshot context.

- `signal_action_split(inputs) -> {security_signal, portfolio_action, combined}`
  where:
  - `security_signal` = the analyst/debate/PM verdict BEFORE the risk gate
    (RATING source), e.g. BULLISH/BEARISH/NEUTRAL + `signal_confidence`
    (calibrated when `enable_calibration` on).
  - `portfolio_action` = the composed risk gate's effective instruction:
    HOLD / NO_NEW_RISK / REDUCE / EXIT / TRADE_ALLOWED, from
    `get_composed_risk_gate` + `kill_switch_state` + drawdown gate.
  - Decision matrix: signal x gate → final action (advisory; cannot override
    the gate upward — the gate can only downgrade).
- Wire the gate's structured result (already available in the composed-gate
  tool output and `final_state["risk_context"]`) into `research_decision.json`
  as new additive fields `security_signal`, `portfolio_action` (old trees
  parse fine — additive-only, per repo contract).
- 5_portfolio render: keep the existing risk-gate block; append a one-line
  `Security signal: BULLISH | Portfolio action: HOLD / NO NEW RISK` so the
  split is visible in decision.md without changing the verdict semantics.

**Acceptance**: on an existing FLAG tree (e.g. SKHY/AMZN), JSON + decision.md
show the two fields; a "bullish but gated" case renders
`security_signal=BULLISH, portfolio_action=HOLD (REJECT)` rather than a bare
HOLD. Pure-function tests (no LLM) for the matrix + gate-cannot-upgrade rule.

## Phase 2 — recommended_position_pct composite (sizing)

**Goal**: one deterministic number the PM/size path and the user both see:
`recommended_position_pct = f(Kelly|CalibratedConfidence, realized vol, risk
budget, liquidity cost, portfolio drawdown allowance)` — always clamped by
the composed gate to 0 on REJECT.

**Files**: `strategies/size.py` (pure composite), `agents/utils/analysis_tools.py`
(`get_position_sizing` gains an optional composite path or a new
`get_composite_sizing` tool — advisory), graph PM prompt note.

- Composite formula (all existing primitives): compute
  `base = min(Kelly(base_p, b), capped_by_risk_budget)`; multiply by the
  position-risk-multiplier factor (regime/vol/knife composite, already wired)
  and a liquidity scalar (from `get_liquidation_days`/illiq, e.g.
  participation ≤ 5% ADV = 1.0, >20% = 0.0); if composed gate REJECT →
  force 0 (and set `portfolio_action=HOLD`).
- `insufficient-history` hints from the snapshot feed an *uncertainty
  discount* (review #37) — small, labeled, only when a load-bearing indicator
  was flagged.
- Output renders: `recommended_position_pct`, `basis` (which factors were
  measured vs n/a) — never a silent number.

**Acceptance**: on SKHY (n=43, gate REJECT, vol 117%) the composite is 0% with
`reason=composed_gate_REJECT`; on a pass-gate liquid name it lands inside
[0, cap] with per-factor attribution. Hermetic + pure unit tests; one live
disable-default-off guard left OFF (gate keeps its current authority).

## Phase 3 — per-rule forward-return evaluation (evidence for the indicator set)

**Goal**: convert `predictions.jsonl` + close history into a per-rule table
(forward 1/5/10/20-day return, hit rate, avg/median return, MAE/MFE, Sharpe,
profit factor) for each configured rule and each rule+confirmation
combination, out-of-sample by construction (lead-lag on close records).

**Files**: new `strategies/rule_eval.py` (pure), new
`scripts/rule_eval.py` (CLI: `--ledger <dir> [--json] [--rules rsi70,macd_hist,bb_ext,vol_2sig]`),
entry in `docs/api_reference.md`.

- Rule set (advisory, deterministic): the 8-indicator core (RSI>70 /
  RSI<35, MACD-hist rising/falling, BB extension, vol percentile>90, VWMA
  distance, ATR contraction→expansion, short-interest>30%, the
  regime/knife composites) + conditional combos (e.g. `RSI>70 AND
  hist_rising AND vol>1.5σ`), each evaluated against the ledger's decisions
  plus the verified close series for forward returns.
- Small-sample guard: rules with `n < 30` prints render `INSUFFICIENT` (the
  methodology-registry ethos from the review), so the output is honest rather
  than a table of noise.
- Output feeds: nothing gates by default — the report is advisory; the alpha-
  health ledger (`scripts/alpha_health.py`) and `evaluate_config_gate`
  remain the validation rails.

**Acceptance**: on the current ledger (hypo or real), the CLI prints a table
with per-rule `PREDICTIVE/INSUFFICIENT` and shows a conditional-vs-base
incremental row (AUC deltas), so the reviewer's #13/#14 "does adding a signal
help?" is answered with a number, not an opinion.

## Test + verification plan (all phases)

- Pure-function tests for `signal_action_split`, the sizing composite, and
  `rule_eval` math (deterministic fixtures, no LLM/vendor).
- One hermetic tool test per new tool surface (mock `_ohlcv`/chain as in the
  VRP/OI tests).
- Full ruff on touched files; `pytest` on the touched test files + the two
  broad suites the changes touch (test_analysis_tools, test_strategies_.
- Live smoke post-build: run `scripts/rule_eval.py` on the latest report
  trees; read the split fields back from `research_decision.json`.

## Sequence + commits

1. `feat(decision): security_signal/portfolio_action split (advisory)` + tests.
2. `feat(sizing): composite recommended_position_pct with gate clamp + uncertainty discount`.
3. `feat(eval): rule_eval.py per-rule forward-return table (n>=30 guard)` + CLI.
4. Docs: `docs/api_reference.md` rows, CHANGELOG per commit, this plan
   flipped to `SHIPPED` when all three land.

Each phase ships independently and is default-off/advisory; none changes the
hard-gate precedence (portfolio REJECT keeps failing closed).