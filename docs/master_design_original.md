# Master Design — TradingAgents (current capabilities)

*A from-scratch recap of what this project does TODAY. No future features, no
roadmap — every section describes behavior that exists and is tested. Written
as the design a rebuild would target, with the system's own modules, entry
points, and safety contracts as the specification.*

---

## 1. What this project is

A **multi-agent LLM financial analysis research system**. It takes one or more
tickers, runs a team of AI sub-agents (analysts → research debate → trader →
risk debate → portfolio manager) over real market data from many vendors, and
produces a written, machine-auditable analysis report card (rating, plan,
risk gate) for a human. **It is analysis-only: it never places an order, never
connects to a broker, and never executes anything.** All decisions are
advisory.

**Stack:** Python ≥3.12, LangGraph orchestration, vendor REST APIs for data,
LLM providers (OpenAI-compatible, configurable) for the agents, pytest for a
2501-test hermetic suite (177 test files).

---

## 2. Design principles (the invariants)

1. **Advisory, never executable.** No research output can emit an order.
   The system's hard gates (risk governor) gate *analysis*, not money.
2. **No fabrication, ever.** Computed values are produced by deterministic
   tools; a missing/unmeasurable value renders an explicit `unavailable` /
   `NO_DATA_AVAILABLE` — the LLM is never allowed to invent numbers.
3. **Point-in-time discipline.** Decisions bind to an `effective_trading_date`;
   news/report reads are filtered to the as-of window; backtests fill at the
   next bar (never at the signal bar's close — a lookahead sentinel test
   enforces it).
4. **Deterministic where possible.** Computed reads (technical factors,
   valuation, risk, sentiment, factor IC) are pure functions over vendor data;
   LLM output is only ever prose reasoning over those computed reads.
5. **Downgrade-only guardrails.** A stabilizer may cap a rating at Hold or
   soften it; it can NEVER upgrade. Property-tested.
6. **Hermetic tests.** The suite mocks vendor transports; no test touches the
   network or a real config root.

---

## 3. System topology

```
 Entry:  CLI (py -3.12 -m cli.main) · batch.analyze · pipeline.py · web app
              │
              ▼
 Data layer ──► dataflows/ (56 modules: vendors, router, breaker, calendar,
 │               caches, schema) — every market read goes through here
              ▼
 Agent layer ──► analysts (market/sentiment/news/fundamentals) → research
 │               debate (bull/bear → research manager) → trader →
 │               risk debate (aggressive/conservative/neutral → judge) →
 │               portfolio manager (decision + guardrail hook)
              ▼
 Strategy layer ──► strategies/ (69 modules: value-dip/swing, qlib factors,
 │                    risk/book, valuation, sentiment, statistical, ...)
 │                    consumed by agents as tools (146 tools)
              ▼
 Reporting ──► reporting.py → report tree (1_analysts … 5_portfolio/
                complete_report.md) + run_card.json + decision disclosure
                + hash-chained risk audit + persistent invalidation ledger
```

---

## 4. Data layer (`dataflows/`)

**Vendor access (56 modules).** 25+ data sources behind one router:
`route_to_vendor(method, *args)` → configured vendor chain with ordered
fallback. Categories: market data, fundamentals, options, news, macro,
insider/ratings, crypto, prediction markets, SEC filings, short interest.

**Robustness (all default-off unless noted):**
- `market_router.py` — `market_for_symbol` (US default, exchange-suffix
  aware: .TO/.L/.T/.KS/.TW…), `resolve_market_priority` (per-market vendor
  order from `market_source_priority`), `gap_fill` (supplement fields from
  secondary vendors), `caliber_consistency` (mixed adjusted/raw warning —
  price-caliber provenance on every `VendorResult`).
- `vendor_breaker.py` — thread-safe 3-fail/300s circuit breaker with
  half-open probe + per-market/vendor negative capability cache.
- `effective_date.py` — weekend/holiday → previous session, pre-close →
  prior session, post-close → current; `should_skip_all_closed` (used by the
  nightly driver, `--force-run` escape hatch).
- `vendor_cache.py` (v2 keys) / `news_cache.py` — TTL disk + in-memory caches;
  never caches a range ending today (forming bar), versioned keys.
- `schema.py` — typed `VendorResult`: provider, fallback_from, is_stale,
  data_quality (fresh|stale|partial|unknown), missing_fields, price_caliber,
  volume_unit. The honesty envelope every consumer reads.

**Lookahead discipline.** `market_data_validator.py` + `pit_registry.py`
(PIT-safe snapshots) back every temporal read; a `test_news_lookahead` suite
rejects future/undated articles in backtest windows.

---

## 5. Agent layer

**Four analyst types** (one LLM sub-agent each, with curated tool lists):
- **Market analyst** — price action, technicals, regime, liquidity, options,
  market breadth, skill-read (regime-from-opinion overlay).
- **Sentiment analyst** — news-sentiment series, social/gdelt, prediction
  markets, fund flows.
- **News analyst** — company + global news, macro, earnings calendar,
  sentiment series, credit-spread reads, **news-relevance scoring +
  admission** (deterministic 0–100, official-source boost, spam drop,
  degrade triple: all_failed/empty/unavailable).
- **Fundamentals analyst** — statements, ratios, valuation, margin of safety,
  earnings quality.

**Research debate.** Bull vs bear researchers argue over the same computed
reads; a research manager judges (structured JSON with scores + grounded
claim ledger + L1 verdict). Structured-debate machinery enforces JSON output,
claim verification, and round bounds.

**Trader.** Builds the execution plan (entry/stop/targets/position size)
from analyst outputs + the research verdict, citing computed levels.

**Risk debate.** Aggressive / conservative / neutral debators + a judge
produce the risk verdict; `risk_governor.py` applies hard gates (position
size cap, limit thresholds) that analysis-only enforces — a REJECT verdict
flags `risk_halt`.

**Portfolio manager.** Produces the final decision (rating, position size,
stop, targets) with a **downgrade-only guardrail hook**:
`decision_guardrail.py` (risk-cap at Hold, near-resistance/no-inflow cap,
near-support/no-outflow soften, confidence cap on stale data) and the PM
schema carries `data_quality` / `guardrail_reason` / `risk_cap`. Structured
output is rebuilt per-field on missing fields (`retry_structured_missing_fields`)
instead of blind re-rolls.

**146 agent tools** across 14 `agents/utils/*_tools.py`; all calcs in
`strategies/` are reachable from the agent tool surface — enforced by the
`test_calc_agent_wiring` gate.

---

## 6. Strategy / calculation layer (`strategies/`, 69 modules)

Named families actually implemented and consumed:

- **Value-dip / swing** — `value_dip.py`, `swing.py`, `mean_reversion.py`,
  `normalized.py`, `fundamental_floors.py`, `catalyst.py`, `events.py`.
- **Qlib factor research** — `factor_expressions.py` (Alpha158-style subset +
  expression evaluator + AST **purity gate**), `signal_analysis.py` (rank
  IC/ICIR, quantile long-short, IC decay), `factor_model_train.py` /
  `factor_proposal_loop.py` scripts, `alpha_zoo.py` (safe operator zoo +
  `factor_bench.py` offline rank-IC bench).
- **Risk & book** — `book_risk.py` (portfolio CVaR + correlated stress +
  drawdown gate), `liquidity_risk.py`, `risk_checks.py`, `risk_sizing.py`,
  `risk_manager.py`, `orderflow.py`.
- **Valuation & credit** — `dcf.py`, `ratios.py`, `credit_spread.py`,
  `fixed_income.py`, `options_math.py`, `rate_utils.py`.
- **Sentiment & behavior** — `sentiment.py`, `sentiment_research.py`,
  `reflection.py`, `journal.py`.
- **Portfolio construction** — `portfolio.py`, `portfolio_optimizer.py`,
  `portfolio_strategy.py` (topk-drop / enhanced-index), `cross_section.py`,
  `rotation.py`, `sector_rank.py`.
- **Honesty + audit additions** — `news_relevance.py`, `report_disclosure.py`,
  `invalidation_ledger.py`, `hash_chain_audit.py`.

All advisory; most gated by default-off config flags.

---

## 7. Decision + reporting output

`reporting.write_report_tree` saves, per run:

```
<TICKER>_<YYYYMMDD>_<HHMMSS>/
  1_analysts/    market.md sentiment.md news.md fundamentals.md
  2_research/    bull.md bear.md manager.md + structured_debate.md
  3_trading/     trader.md
  4_risk/        aggressive.md conservative.md neutral.md verdict.md
                 + risk gate block + structured evidence
  5_portfolio/   decision.md   (+ decision disclosure block, flag-gated)
  complete_report.md           (consolidated, TOC)
  run_card.json                (config hash, commit, LLM, verdict)
```

**Decision disclosure** (computed, advisory, default-off) lists
invalidation conditions, consensus (supporting/opposing from the L1 side),
watch conditions + next-check (effective-date calendar), attribution,
source-caliber footers. **Invalidation conditions** are persisted to a
JSONL ledger (`decision_history.py --invalidate`, action-report auto-records
stop breaches).

**Audit trail:** `risk_audit.jsonl` is a SHA-256-chained tamper-evident
ledger (`hash_chain_audit.py`, `risk_report.py --verify-chain`). Truncation
of an LLM section is detected and marked honestly (never hidden).

---

## 8. Entry surfaces

**Interactive CLI** (`py -3.12 -m cli.main`, script `tradingagents`):
guided workflow — ticker, analysis date, analysts, provider/model selection,
then the live multi-agent run with a rich dashboard (progress, tool calls,
tokens, live reports). `--symbol MSFT` runs non-interactively with defaults.

**Batch** (`batch.py`) — symbols, depth, vendor, analysts, workers (capped);
batch summary JSONL + per-symbol report folders.

**Pipeline** (`pipeline.py`) — universe sources (tickers/top-losers/
heat-proxy/top-movers), top-N, vendor, market, movers count, workers.

**Scripts (24)** — `value_screener`, `pre_market_review`, `nightly_review`
(effective-date skip + `--force-run`), `action_report` (basket vs report
conditions MET/NOT_MET/UNKNOWN), `backtest_strategy` (next-bar fills, fills
vs targets), `factor_bench`, `factor_model_train`, `factor_proposal_loop`,
`strategy_quality_report`, `risk_report` (audit summary/verify-chain),
`capital_income_screener`, `decision_history` (+ invalidation ledger),
`positions_to_basket` (recomputes risk-basket weights from `positions/*.csv`
→ .env + book_value.json), `rebuild_complete_report`, `smoke_structured_output`,
`debate_ab_harness`, `orderflow_evaluate`, `evaluate_config_gate`, tuner,
runfile, `massive_noi_monitor`, `validate_massive_flat`, `experiments`,
`sentiment_factor_eval`.

**Web app** (sibling repo `trading_web`) — FastAPI + React 19, login-gated;
screens: Dashboard (reports + jobs), Run batch, Screener, Pipeline,
Pre-market, Nightly, Action report, Value tools (36 in-process computed
tools), History, Reports viewer, Config, Audit, Raw `--help` allowlist.
Read-only; mirrors the same repo's tools + `.env` config.

---

## 9. Configuration

`tradingagents/default_config.py` — `DEFAULT_CONFIG` + env map (all
`TRADINGAGENTS_*`), `.env.example` mirror. Key toggles (all default OFF,
advisory):
- `enable_decision_guardrail` — downgrade-only PM stabilizer + confidence cap
- `enable_market_routing` — per-market vendor priority + breaker + gap-fill
- `enable_skill_overlays` / `skill_dir` — YAML strategy skills +
  regime-from-opinion (bounded ±20 adjustments)
- `enable_news_relevance` — relevance scoring + official boost + news cache
- `enable_report_attribution` — decision disclosure block
- `enable_decision_audit` — claim-vs-computed audit note
- `risk_audit_enabled` (default ON) — hash-chained risk audit ledger
- `vendor_cache_enabled` (default ON) — TTL vendor cache
- `risk_basket_tickers` / `risk_basket_weights` — computed by
  `positions_to_basket` for book-level risk reads

Docs-true set stays in sync: `docs/api_reference.md`,
`docs/developer/04-strategies.md`, `docs/AGENT_ONBOARDING.md`, `README.md`,
`CHANGELOG.md`.

---

## 10. What the project explicitly does NOT do (current)

- **No order placement, no broker connectivity, no execution.** The word
  "trading" in the name = analysis for trading, not trading.
- **No local model fine-tuning.** LLMs are provider-side (OpenAI-compatible);
  the repo hosts no training runs.
- **No market-making / HFT / aggressive order flow semantics.**
- **No live account data** beyond reading vendor market data + optional
  read-only broker positions (web portfolio view).
- **No fabricated numbers**: unavailable data stays unavailable.

---

## 11. Verification posture

- 2501 tests / 177 files; unit + wiring + property suites (guardrail
  never-upgrades property, lookahead sentinel, calc→agent reachability gate,
  caliber consistency, hash-chain tamper, coalescing cache concurrency).
- Vendor paths default-off respected: default behavior is bit-identical when
  optional flags are unset (regression-tested).
- Web app mirrors repo surfaces; its 60-test suite runs against the same
  repo imports.