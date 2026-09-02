# Design: Market-First Refresh (incremental re-decision on a fast path)

**Status:** design proposal only — no code changed.
**Date:** 2026-09-02.
**Object:** make the project timely for intraday decision adjustments while
keeping the full multi-agent stack for the slow, deep cadence. This is an
architecture question; nothing here is committed or implemented.

Companion docs: `docs/pre_market_review.md` (the existing CONFIRM/REVISE/REJECT
delta reviewer — the seed of this design), `docs/design_multi_agent_debate.md`
(judiciary/grounding), `docs/api_reference.md` §3/§7 (graph, checkpoints,
persistence).

---

## 1. The problem, measured

A full `propagate()` deep run costs **~22–23 min per symbol** (measured in the
last batch, `reports/batch_summary_20260828_231618.jsonl`):

| symbol | wall_seconds |
| --- | --- |
| nvda | 1323.16 |
| qcom | 1330.52 |
| skhy | 1386.74 |
| avgo | 1398.22 |

The cost is dominated by LLM chains whose **inputs do not change intraday**:

- 4 analyst tool-loops (~73 market tools; fundamentals statements; news /
  sentiment / macro fetches).
- Bull/Bear researchers + Research Manager.
- 5-round × 3-role risk debate.
- Portfolio Manager + deterministic overlays.

Of all the inputs, **only the market analyst's feed (price / volume / vol /
session) moves at sub-day frequency**. Fundamentals, SEC filings, sentiment,
and macro reset on days-to-weeks. So re-running the full stack purely because
the price moved is ~90% wasted work — and the latency (20+ min) is already
past the window where the market is "the only thing moving".

The repo already proved the delta-review pattern:
`scripts/pre_market_review.py` re-checks a prior decision against measured
overnight deltas and emits a deterministic-first **CONFIRM / REVISE / REJECT**,
~60s/symbol. Its limits: it is pre-open, quote-only, and it reuses the
*decision* — not the analyst *reports*. This design generalizes it to an
intraday, report-reusing refresh.

---

## 2. What the research says (web search, 2026-09-02, 4 queries)

Sources converge on four patterns:

1. **Reuse prior analysis as memory; update only deltas, not the whole report.**
   Cached prior report + diff-based update beats regenerating unchanged
   sections; memory-augmented inference / RAG is the practical way to inject
   new facts without retraining (QuantAgent short-window agents, FinPos
   continuous position awareness, generic "incremental updates not full
   recomputation").

2. **A cheap rule-based trigger in front of the expensive step.**
   A deterministic gate decides "reuse cached decision" vs "re-run the slow
   deliberative stage", with hysteresis so tiny oscillations do not thrash;
   Event-Condition-Action / reactive-controller + slow deliberative step is
   the standard framing.

3. **Only refresh the impacted stages.**
   Recompute regime/sizing only if volatility or macro shifted; re-synthesize
   the decision only if upstream signals crossed a threshold; keep the rest
   cached (universe, static fundamentals, invariant rules).

4. **Staleness policy + deterministic post-processing.**
   Cache report + timestamp + session + thesis; on reuse compare current
   inputs to the cached assumptions — non-material change → keep thesis and
   append a short update; material change → mark stale and regenerate. Never
   act on stale context silently, and never let the LLM bypass deterministic
   risk checks. LangGraph **checkpoint/resume** (already in this repo's
   `graph/checkpointer.py`) is the confirmed seam for reseeding state and
   skipping completed nodes.

All four are consistent with this repo's contracts: no-fabrication,
compute-as-tools, advisory-first (hard gating stays in the deterministic
overlays).

---

## 3. Target architecture: three tiers

```
INTRADAY (new bar / new session)
   │
   ▼
T0  DETERMINISTIC GATE  (seconds, no LLM)
    refresh OHLCV → recompute regime/ATR/swing/RS/catalyst/risk-gate/contract
    compare vs stored snapshot from the last full run (hysteresis bands)
    │
    ├─ HOLD       → reuse last decision; stamp snapshot; done  (<1 min)
    ├─ UPDATE     → Tier 1
    └─ ESCALATE   → Tier 2 (or Tier 1 with REJECT posture):
                     stop/target breach, hard-block window,
                     governor REJECT, regime flip, earnings binary gap
   │
   ▼
T1  MARKET REFRESH  (≈3–6 min)
    ONLY the Market analyst tool-loop re-runs (its feed moved)
    Prior full-stack reports (sentiment/news/fundamentals/RM plan)
      read from full_states_log and injected with "cached as-of <ts>" labels
    Re-run JUST: Market analyst → Trader → risk debaters (1 round each)
      → Portfolio Manager → deterministic overlays (already cheap)
    Output: updated decision + delta memo (price/vol/risk-gate changes cited)
    → memory log + paper ledger (same as a full run)
   │
   ▼
T2  FULL RUN  (as today, 20+ min) — only when T0/T1 says the thesis is broken,
    or on the scheduled nightly/weekly cadence
```

Key framing (from the search):

- **T0** = the reactive router. ATR-relative price change, session identity,
  catalyst-window state, and governor verdict decide HOLD vs UPDATE vs
  ESCALATE. Hysteresis + cooldown prevent loop flapping.
- **T1** = today's `--analysts market --depth shallow` run, but **seeded with
  prior reports instead of empty inputs**. The missing piece today is reuse of
  the other three analyst reports + the prior plan, so the PM argues with the
  full context rather than from a single source. That is a state-seeding
  change, not a new graph.
- **T2** = the existing full pipeline, unchanged, on the slow cadence.

---

## 4. Decision semantics

| Verdict | Meaning | LLM spend |
| --- | --- | --- |
| HOLD | thesis intact; prior decision reused; snapshot timestamp updated | 0 |
| UPDATE (REVISE) | market moved materially; new decision + delta memo citing recomputed numbers | T1 only |
| ESCALATE (REJECT) | measured breach (through stop, hard-block, governor REJECT, regime flip) | T2 full re-run or paper-book skip |

Mirrors `pre_market_review.py`'s semantics: **REVISE/REJECT only on measured
deltas; HOLD/CONFIRM by default**.

---

## 5. Module map (seams — no new algorithm code)

| Concern | Existing seam |
| --- | --- |
| Prior reports + decision to reuse | `results_dir/<t>/TradingAgentsStrategy_logs/full_states_log_<date>.json`, memory log (pending), `reporting.write_report_tree` |
| Deterministic refresh + verdict | `pre_market_review.py` CONFIRM/REVISE/REJECT, `strategies/pre_market.py`, `_apply_strategy_overlays`, `_RUN_OHLCV_CACHE` (one fetch/run) |
| Market-only fast chain | `--analysts market`, `--depth shallow`, `analyst_concurrency` — exists today |
| State resume / skip completed nodes | `graph/checkpointer.py` (LangGraph thread resume; `update_state()` to fork from a prior checkpoint) |
| Computed numbers for the PM | `_compiled_decision_context` + `risk_context` (already injected into Trader/PM/risk debators/researchers) |
| Staleness labels (no-fabrication) | a "cached as-of" line in injected reports + the delta memo (same honesty rule as `-calculated` / `unavailable`) |
| Persistence of the new decision | memory log append + `pre_market_ledger.jsonl` paper book (resolves realized vs benchmark) |
| Web | `run_premarket` / `run_nightly` capability routers — a `run_market_refresh` slot |

---

## 6. Cost & risk (honest)

- **Latency**: T0 seconds; T1 ≈ 3–6 min (one analyst loop + 3 × 1-round
  debaters + PM); T2 unchanged at 20+ min.
- **No-fabrication preserved**: reused reports carry explicit `as-of` labels;
  the PM never treats cached fundamentals as fresh. Deterministic post-checks
  still run outside the LLM.
- **Stale-fundamental risk is bounded**: fundamentals/news/sentiment reset on
  the nightly full run; intraday the market view is the live input by design.
- **Thrash risk**: hysteresis + ATR-relative triggers + a per-ticker cooldown
  prevent loop flapping.
- **Honest limits**: a market-only refresh cannot catch a fundamentals event
  (earnings/guidance surprise) — that is what the T2/nightly cadence and the
  T0 catalyst-window check are for; a binary gap still escalates.

---

## 7. Suggested rollout (per phase: tests, docs, web mirror, commit — working agreement)

1. **P0 — T0 gate** (+ snapshot stamp, HOLD path). Small, zero LLM, low risk.
2. **P1 — T1 market-refresh** (seeded state, 3×1-round risk, PM re-decision,
   delta memo). ~1–2 days with hermetic tests.
3. **P2 — escalation + cadence wiring** (T2 triggers, scheduler slot, web
   `run_market_refresh`).
4. **P3 — optional** journaling of HOLD vs UPDATE accuracy (Brier-style, like
   the debate A/B harness).

**Why it is tractable:** P0–P1 reuse machinery that already exists —
`pre_market_review`'s delta verdict, the market-only analyst selection, the
deterministic overlay pipeline, and LangGraph checkpoint resume. The fast path
is orchestration, not new algorithm code.


---

## Qlib OnlineManager / DelayTrainer alignment (design_qlib_integration.md §1a-16)

The fast path is the fork's analog of Qlib's `OnlineManager.routine()` model
rolling. The alignment is exact:

| Fast-path tier | Qlib OnlineManager analog | Seam |
| --- | --- | --- |
| T2 nightly full run | the **delayed training batch** — `DelayTrainer` records every window's model tasks, then trains them ALL at the end (parallel via the existing `batch.py` worker pool). T2 IS the delay-train: models/reports are (re)built for the whole history in one pass, then `prepare_signals`-style ensembling (the candidate-zoo selection from FinRL §6.6) picks the online models for the next period | `scripts/runfile.py` (phase-2 declarative runs) + `factor_model_train.py` (phase-4, gated) |
| T1 market-only refresh | `OnlineManager.routine()` — reuse the day's ALREADY-TRAINED models to refresh predictions from new data (no retrain). T1 reuses the prior analyst reports as cached as-of state (via `pit_registry`) and re-runs only market analyst → trader → 1-round risk → PM | `dataflows/pit_registry.py` (as-of snapshot reads) + `signal_analysis` (IC/decay advisory) |
| T0 deterministic gate | the **decision policy**: `routine()` decides HOLD/UPDATE/ESCALATE from deltas (regime/ATR/catalyst/risk recompute vs the stored snapshot with hysteresis) — the fast path's decision policy is the same shape | `strategies/factor_expressions.py` (`get_factor_profile` diff vs the stored snapshot) + the existing overlays |

Constraints that carry over (design_qlib non-goals):
- T1 NEVER retrains — retraining is T2's delayed batch (the DelayTrainer
  split means a T1 refresh in the morning never waits on a full retrain).
- `history` (which models were online per day) is the ledger's job: the
  recorder-style `experiments` rows (phase 2) record `{config_hash, metrics,
  status}` so the online/offline attribution is reproducible.
- Still advisory: the refresh updates the decision context, never the hard
  gates (regime → catalyst → contract → governor stay the authority).
- `fast_path_*` config keys formalize the cadence; nothing ships until the
  fast-path implementation phase (design_market_refresh_fastpath Phase 2+).
