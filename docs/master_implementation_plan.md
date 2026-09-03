# Master Implementation Plan — System Improvements

*Synthesized from three independent LLM reviews of the current system:*
- `docs/remediation_chatgpt.md` (30 items, phased Tier 1–3, comprehensive)
- `docs/remediation_gemini.md` (tool bloat, falsification schema, typed state)
- `docs/remediation_claude.md` (validity, overfitting, ops, integrity)

*Scope decision (user): implement ALL three reviews, phased. Fundamentals-PIT:
classified as DEFERRED after vendor research (no clean restatement support).*

Every item is verified against the actual codebase: what exists, what is a true
gap, and how it fits. All work stays advisory + default-off; the five design
invariants (advisory-only, no-fabrication, downgrade-only guardrails, PIT
discipline, hermetic tests) are never weakened.

---

## Executive summary

| Workstream | Theme | Items | Effort |
|---|---|---|---|
| W1 — Measurement | Make the system scientifically testable | 11 | High (foundation) |
| W2 — Validation | Prove factors/theses survive OOS + costs | 12 | High |
| W3 — Data & Integrity | Close PIT/provenance/corporate-action holes | 8 | Medium |
| W4 — Architecture & Efficiency | Cut tool surface + token cost + complexity | 8 | Medium |

Top 5 quick wins (can land in one commit each):
1. **Decision prediction ledger** (W1-1) — log every decision as a prediction object; score vs realized N-day outcome. Enables almost everything else.
2. **Agent scorecard** (W1-6) — per-agent hit rate, avg return, calibration from the ledger.
3. **MAE/MFE per decision** (W1-3) — max adverse/favorable excursion from the outcome window.
4. **Data disagreement detection** (W3-4) — cross-vendor value spread flag (we already merge vendors; just surface the spread).
5. **Prompt-injection test** (W3-8) — adversarial news/social fixture into `news_analyst` prompt.

---

## W1 — Measurement workstream (make it scientifically testable)

**Outcome:** the system can answer "how often have we been right, under what conditions, which agent, after costs, when should I trust it?"

| # | Item | Source | Current state | Plan |
|---|---|---|---|---|
| W1-1 | **Decision prediction ledger** | ChatGPT #17, Claude closed-loop | `full_states_log_*.json` + `invalidations.jsonl` exist but no outcome scoring | New `strategies/prediction_ledger.py`: log `{ticker,date,rating,direction,entry,target,stop,confidence,horizon_days,data_quality}` per decision; `score(decision, realized)` at N days (hit rate, target reached, stop hit, return) → append outcome. Reuses existing log paths + `decision_history.py`. |
| W1-2 | **Confidence calibration engine** | ChatGPT #5 | PM emits `confidence`; no calibration | Bins predicted-confidence vs actual success (like ChatGPT's 50–60%→56% table); report in `run_card`/scorecard. Only for decisions with `data_quality=fresh` (no fabricated calibration on stale). |
| W1-3 | **MAE/MFE tracking** | ChatGPT #6 | absent | Record max adverse/favorable excursion (as % of entry) per outcome window; store alongside W1-1 rows. Pure computation over the vendor close series. |
| W1-4 | **AI analyst scorecard** | ChatGPT #18 | analysts exist, no per-agent measurement | From the ledger: per-agent (market/sentiment/news/fundamentals + each debate role) hit-rate, avg N-day return, calibration, horizon-window contribution. Feature `scripts/agent_scorecard.py`. |
| W1-5 | **Quant-only baseline** | ChatGPT #22 (Tier 1) | no baseline | Deterministic signal stack (factor score, momentum, value, quality, vol, trend) backtested side-by-side with (quant-only vs quant+LLM vs LLM-only) — the single most informative experiment; reuse `factor_bench` + `backtest_strategy`. Feature flag `enable_baseline_report`. |
| W1-6 | **Benchmark hierarchy** | ChatGPT #23 | backtests lack market comparators | Every strategy report gains S&P/Nasdaq/sector-ETF + simple-strategy (buy&hold, momentum, MA, value) rows: return/Sharpe/DD. Extend `strategy_quality_report.py`. |
| W1-7 | **Prediction outcome → guardrail feedback** | Claude closed-loop + ChatGPT | no feedback | When a decision's stop is breached or outcome contradicts the rating, auto-append an invalidation row (reuses `invalidation_ledger`) AND decrement the analyst's scorecard weight for the responsible agent. Advisory. |
| W1-8 | **LLM cost/performance ledger** | ChatGPT #20 | `run_card.json` logs tokens/model, not cost | Add per-run `cost_usd` estimate from token counts × provider rate table (`llm_clients`), surfaced in `run_card` + scorecard: quality-per-dollar. |
| W1-9 | **Model-vs-model benchmarking** | ChatGPT #21 | configurable providers exist | Reuse `debate_ab_harness.py`/`experiments.py`: same research packet across 2+ models → factual accuracy, hallucination, consistency, cost, latency, outcome. |
| W1-10 | **Regime-conditioned performance** | ChatGPT #4, Claude | regime exists, not tied to outcomes | Tag every ledger row with the regime (reuse `regime_from_opinion` + `strategies/regime.py`); tabulate strategy performance by regime (Bull/Bear/High-vol/Low-vol) — the exact 4×4 table ChatGPT proposes. |
| W1-11 | **Agent ablation framework** | ChatGPT #19 | `debate_ab_harness.py` exists | Extend to drop-one-agent runs (remove sentiment/news/market/fundamentals/bull/bear/risk-debate) and report each component's marginal contribution. Default-off, expensive — a script not a test. |

**W1 gates:** every item is hermetic (fixture decisions + fixture outcomes); tests use synthetic price series. W1-1 is the dependency for W1-2/3/4/7/10/11 — order first.

---

## W2 — Validation workstream (prove it survives OOS + costs)

**Outcome:** factors and backtests are robust to overfitting, costs, capacity, survivorship — not just in-sample lucky.

| # | Item | Source | Current state | Plan |
|---|---|---|---|---|
| W2-1 | **Deflated Sharpe Ratio (DSR) + PBO** | ChatGPT #2, Gemini | `evaluate_config_gate.py` has PBO/walk-forward for config, not factors | Add DSR (deflate Sharpe by #factors tried + sample length) to `factor_bench.py`; auto-compute when `--n-trials` known. |
| W2-2 | **Combinatorial Purged Cross-Validation (CPCV)** | Gemini | absent | `strategies/evaluate.py` add CPCV folds (purging + embargo) for factor/strategy validation; wire into `factor_bench` + `backtest_strategy`. |
| W2-3 | **Walk-forward as first-class** | ChatGPT #3 | only in `evaluate_config_gate` | Lift `walk_forward_splits` into `strategies/evaluate.py` (already the source); give `factor_bench`/`alpha_zoo` a `--walk-forward` mode reporting train/test per fold. |
| W2-4 | **In-sample vs out-of-sample split enforcement** | ChatGPT #2 | proposals evaluate on full sample | `factor_proposal_loop` must train on a leading split and report OOS IC only (a one-commit guard). |
| W2-5 | **Alpha Quality Score + A/B/C/D rank** | ChatGPT #2 | IC/ICIR exist | Composite score (predictive IC, stability, ICIR, decay, OOS, regime robustness, turnover, cost-adjusted, capacity) in `signal_analysis` + a `classify_alpha()` → A/B/C/D. |
| W2-6 | **Transaction-cost realism** | ChatGPT #7, Gemini | `backtest_models.py` has fee + slippage + fill-prob | Add **Almgren-Chriss/square-root impact** model from `20d_adv` (average daily volume) + spread provenance; config `backtest_impact_model`. Reuses `adv` reads. |
| W2-7 | **Turnover + capacity analysis** | ChatGPT #8 | absent in backtest output | Report per-strategy turnover (from `positions` vs `target_positions` deltas) + capacity (position size vs ADV fraction). |
| W2-8 | **Borrow-cost/short-availability** | Claude | shorts allowed in some backtests, no borrow model | Add optional borrow-rate + availability cap for short legs; flag when a short backtest ran without it. |
| W2-9 | **Corporate-action normalization** | ChatGPT #25, Claude | price caliber exists; actions not backtest-normalized | OASIS-equivalent: splits/reverse/dividends/spinoffs/ticker-change handling in `backtest_strategy` series prep; reuse `eodhd /div + /splits`. |
| W2-10 | **Survivorship-bias protection** | ChatGPT #24, Claude | universe = current | `pit_registry`-style "was this symbol in the universe as-of date?" guard on backtest universes (screener/pipeline top-movers); retain delisted rows. |
| W2-11 | **Stress/scenario grid** | ChatGPT #12, Gemini | risk-debate framing only | `get_stress_grid(ticker, {-revenue%, +discount-rate-bps})` → shifted rating/stop rows in `decision.md` (computed, advisory) — reuses DCF + risk machinery. |
| W2-12 | **Earnings-event simulation** | ChatGPT #13 | `events.py`, `catalyst.py` exist | Model pre-earnings IV expansion + post-earnings drift scenarios in backtests/options reads; advisory, flag-gated. |

**W2 dependency:** W2-5 consumes W2-3/6; W2-1 needs `--n-trials` from the proposal loop. Everything reuses existing modules (no new vendor pipelines).

---

## W3 — Data & Integrity workstream (close the holes)

**Outcome:** PIT discipline covers fundamentals decision-level quality; corporate actions and disagreements surface; ingestion is injection-hardened.

| # | Item | Source | Current state | Plan |
|---|---|---|---|---|
| W3-1 | **Decision-level data-quality score** | ChatGPT #26 | `data_quality` per decision (coarse) | Per-input scores (price/volume/fundamentals/news/options/macro) → weighted overall 0–100; map to confidence tiers; record in ledger. Reuses `VendorResult` fields. |
| W3-2 | **Data disagreement detection** | ChatGPT #27 | vendors merged, spread not surfaced | Cross-vendor numeric spread (EPS, revenue, target) flagged `DATA CONFLICT (x%)` in `VendorResult`/disclosure; reuse `caliber_consistency` plumbing. |
| W3-3 | **Fundamentals PIT (restatements)** | Claude | **DEFERRED (user decision)** | Vendor research: EODHD supports a filing-date filter (limited) but FMP/Tiingo return period dates, not filing vintages; no vendor cleanly exposes full restatement history. Defer with trigger: adopt when a vendor exposes filed-vintage restatements; meanwhile document the limitation in `master_design_original.md` integrity pillar + assert "as-of filed-date where available (SEC 10-K/Q `filed_at`)". |
| W3-4 | **Effective-date invariant everywhere** | Claude | effective-date binds price/news; fundamentals not checked | Add a PIT assertion: fundamental reads used in a decision must carry `period`/as-of ≤ effective date; refuse `period > effective_date` (fail-closed on data). |
| W3-5 | **Options depth layer** | ChatGPT #14, Claude | `options_math.py`, chain tool exist | Add IV surface/rank/percentile, skew, term structure, put/call OI, gamma, VRP, expected move + IV-crush — the "bullish but IV prices a 12% move → calls unattractive" clarity. New `strategies/options_surface.py` bound as a tool. |
| W3-6 | **Thesis-vs-evidence matrix** | ChatGPT #15 | `structured_debate` claim ledger exists | Render thesis rows × evidence/strength/contradiction/status in the research report; computed from the claim ledger + computed metrics (not LLM prose). |
| W3-7 | **"What would change my mind?" first-class** | ChatGPT #16 | `invalidation_conditions` exist, not structured | Structured `FalsificationCondition[]` (metric, operator, threshold) per decision + auto-monitor on subsequent closes; breach → auto-invalidation + alert in `decision.md`. Pipes into `invalidation_ledger` (Gemini's exact proposal). |
| W3-8 | **Prompt-injection resistance test** | Claude | news/social flows into analyst prompts; spam filters only | Adversarial fixture (instruction-injecting headline) → assert it never alters analyst behavior (hermetic; prompt-level assertions). Same for web `read_url`/document text if ever bound to agents. |

---

## W4 — Architecture & Efficiency workstream (cut surface + cost)

**Outcome:** 146 tools → domain bundles; typed graph state; lower token cost; monitored ops.

| # | Item | Source | Current state | Plan |
|---|---|---|---|---|
| W4-1 | **Composite domain tools** | Gemini (core) | 146 atomic tools | New `get_market_technicals(symbol, as_of)` / `get_fundamental_profile(...)` / `get_sentiment_flow_feed(...)` / `get_factor_profile(...)` / `get_portfolio_risk_envelope(...)` — one pydantic envelope per analyst persona (deterministic aggregation + data-quality flags; the LLM stops chaining micro-tools). Keep atomic tools for scripts/web; agents prefer bundles. |
| W4-2 | **Typed graph state** | Gemini | LangGraph state is a plain dict | `AnalystSummary → ResearchVerdict → TradeProposal → RiskVerdict → Decision` typed/pydantic artifacts; downstream agents receive structured outputs + computed levels only, never raw tool-call dumps (recency-bias + token savings). |
| W4-3 | **Falsification schema in debate** | Gemini, Claude | debate has claim ledger, no numeric falsification | `GroundedDebateArgument` (thesis + falsification criteria {metric, op, threshold}); judge enforces metric ∈ computed set + auto-rejects a thesis whose current level already breaches its own condition. Pipes into W3-7. |
| W4-4 | **Factor→Agent bridge** | Gemini | `factor_profile` exists; analysts don't consume IC | Market/bull/bear agents gain the symbol's current factor vector: rank-IC, decile, regime-conditioned performance (feeds W1-10). |
| W4-5 | **Local/hybrid model routing** | Gemini | providers only | Optional tier (Ollama/vLLM) for data-extraction/intermediate analyst calls; frontier models reserved for Research Manager/Risk Judge/PM. Config `llm_tier_map`. |
| W4-6 | **Cross-asset/macro regime engine** | Gemini | `regime.py` exists (price/vol) | Add explicit macro regime (rates, yield-curve, credit spread, USD, vol surface) → Risk-On/Contraction/Stagflation; agents read threshold adjustments per regime. Reuses FRED/fed/macro reads. |
| W4-7 | **Monitoring/alerting** | Claude | breaker + invalidation logged, JSONL only | Add a push path: webhook/Slack/email digest on breaker trips, stale thresholds, invalidation breaches, HALT (execution-adjacent) — config `monitor_notify` default-off. |
| W4-8 | **Complexity/dependency report** | Claude #29, ChatGPT cleanliness | 56+69+146 modules, manual docs | Periodic `scripts/complexity_report.py`: unused exports, circular imports, per-module LOC + complexity; run in CI (non-blocking advisory report) so the surface doesn't silently grow. |

---

## Recommended phase order

```
Phase 1 (measurement foundation)     W1-1, W1-3, W1-8        [prediction ledger + MAE/MFE + cost]
Phase 2 (validation guards)          W2-4, W2-3, W2-1, W2-2  [OOS enforcement, walk-forward, DSR/CPCV]
Phase 3 (data integrity)             W3-1, W3-2, W3-4, W3-7  [quality score, disagreement, PIT assert, falsification]
Phase 4 (scorecard + calibration)    W1-2, W1-4, W1-6, W1-7  [calibration, scorecard, benchmarks, feedback]
Phase 5 (architecture)               W4-1, W4-2, W4-3, W4-4  [bundles, typed state, falsification schema, factor bridge]
Phase 6 (regime + scenario)          W1-10, W1-11, W2-11, W4-6
Phase 7 (costs + capacity)           W2-6, W2-7, W2-8, W2-9, W2-10
Phase 8 (ops + polish)               W1-5, W1-9, W3-5, W3-6, W3-8, W4-5, W4-7, W4-8
```

Each phase = its own commit + push after tests green + docs-true sync
(`README`/`api_reference`/`developer/04`/`AGENT_ONBOARDING`/`CHANGELOG`).

---

## Defers & explicit non-goals

- **Fundamentals-PIT restatements** (W3-3) — DEFERRED per research + user
  decision (no vendor supports clean restatement vintages; adopt when one does).
- **Research knowledge graph** (ChatGPT #28) — Tier 3; defer unless longitudinal
  research becomes a focus.
- **Local fine-tuning / training pipeline** — out of scope (provider-LLM based).
- **Execution/order layer** — explicitly NOT part of this plan (see
  `master_design_original.md` section 10; a separate execution design exists
  separately and stays separate).
- All new features remain advisory + default-off; hard gates unchanged.

---

## Success criteria (how we know it worked)

1. `agent_scorecard.py` shows measured hit-rate/calibration per agent on ≥100
   archived decisions (no new runs required — replay from logs).
2. A factor that passes `factor_bench` in-sample but fails DSR/CPCV/OOS is
   rejected automatically (W2-1/2/4).
3. `decision.md` gains 3 computed blocks: falsification conditions +
   auto-breach alert, stress grid, data-quality score — all advisory.
4. Agent prompts' token footprint drops measurably with W4-1/W4-2 (compare
   `run_card` token fields before/after).
5. Injection fixture (W3-8) makes the news analyst deterministic — the same
   prompt with an injected instruction produces the same structured output.
6. Full suite stays green (2,501→~3,000 tests), hermetic, ruff-clean.