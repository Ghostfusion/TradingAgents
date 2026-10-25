# 13 — Score internals: gates, surfaces, provenance seams and the divergence ledger

**Audience: developers of this repository.** The formulas and the provider
endpoints live in [`docs/design_score_calculations.md`](../design_score_calculations.md),
which is written to be readable by someone outside this tree. This file holds
what only matters inside it: which gate switches a block on, where each number
is published, which engines bypass the vendor router, and the twelve standing
divergences between what the code does and what its prose says.

---

## 1. Gates

Every score ships **off** and is switched on by an `enable_*` key
(`tradingagents/default_config.py`), overridable by the matching
`TRADINGAGENTS_ENABLE_*` environment variable. The live `.env` turns all of them
on except the quality composite.

| Block | Gate | Shipped default | Callers (tool / card / scorecard) |
| --- | --- | --- | --- |
| FundamentalScore | `enable_fundamental_score` | False | `get_fundamental_score` (`analysis_tools.py:6452`); `reporting.py:1144`; `quant_scorecard.py:260` |
| TechnicalScore | `enable_technical_score` | False | `get_technical_score` (`:6782`); `reporting.py:1222`; `quant_scorecard.py:279` |
| MomentumScore | `enable_momentum_score` | False | `get_momentum_score` (`:7116`); `quant_scorecard.py:305`; screener |
| SentimentScore | `enable_sentiment_score` | False | `get_sentiment_score` (`:8222`); `reporting.py:1733`; `quant_scorecard.py:384` |
| NewsScore | `enable_news_score` | False | `get_news_score` (`:8983`); `reporting.py:1779`; `quant_scorecard.py:407` |
| EventScore | `enable_event_state` | False | `get_event_state` (`:7620`); `reporting.py:1554`; `quant_scorecard.py:422` |
| RegimeScore | `enable_regime_score` | False | `get_regime_score` (`:7895`); `reporting.py:1704`; `quant_scorecard.py:327` |
| RiskScore | `enable_risk_score` | False | `get_risk_score` (`:7403`); `reporting.py:1712`; `quant_scorecard.py:355` |
| TradeScore | `enable_trade_score` | False | `get_trade_score` (`:7436`); `reporting.py:1287`; `quant_scorecard.py:472` |
| Quant scorecard | `enable_quant_scorecard` | False | `graph/trading_graph.py:782-806`; `reporting.py:1446` |
| Forward calendars (EventScore's product/clinical family) | `enable_event_calendars` | False | `reporting.py:1530`; `analysis_tools.py:7520` |
| Quality composite | `enable_quality_composite` | False | `analysis_tools.py:5933`; screener column |
| Score eval rows | `enable_score_eval_rows` | False | `scripts/strategy_quality_report.py:485` |
| F-score detail / G + C scores | `enable_f_score_detail`, `enable_growth_scores` | False | `quant_formula_tools.py:282-311`; `statement_parsing.py:1656` |

A gate-off run is byte-identical to a pre-engine run: the block is `None` and
its run-card key is omitted.

## 2. Where each number is published

| Number | Tool (LLM leaf) | `run_card.json` key |
| --- | --- | --- |
| FundamentalScore | `get_fundamental_score` | `fundamental_score` |
| TechnicalScore | `get_technical_score` | `technical_score` |
| MomentumScore | `get_momentum_score` | `quant_scorecard.engine_detail` |
| SentimentScore | `get_sentiment_score` | `sentiment_score` |
| NewsScore | `get_news_score` | `news_score` |
| EventScore | `get_event_state` | `event_state` |
| RegimeScore | `get_regime_score` | `regime_score` |
| RiskScore | `get_risk_score` | `risk_score` |
| TradeScore | `get_trade_score` | `trade_score` |
| container | — | `quant_scorecard` (`scorecard_status`, `vector_status`, `movement`, `engine_detail`) |

Every block carries `status`, `score`, `coverage`, `withheld` (when withheld)
and `basis` — the weight vector actually used plus the components measured — so
a reader can recompute the number from the card alone.

## 3. The one-producer rule

Where the card and the prompt both show a score, the card reads the run's own
snapshot instead of recomputing it (`reporting.py:1144`, `:1287`, `:1446`).
Recomputation is a fallback for a legacy state only, and it is a *second
producer*: `resolve_peer_universe` re-fetches statements live with no cache, and
the 2026-09-20 measurement recorded in `reporting.py:1155-1170` found 113 metric
diffs between two identical calls and three composites for one `(MSFT,
2026-09-20)` — 61.25 / 69.38 / 79.17.

## 4. Provenance seams

The three facts that make the external document's endpoint tables differ from
the configured vendor chains:

1. **The price path bypasses the router.** `_ohlcv`
   (`agents/utils/analysis_tools.py:229`) → `dataflows/stockstats_utils.py:274
   load_ohlcv` → `yf.download` (`:336`). Every bar-based leg (technical,
   momentum, risk, regime, breadth, the sentiment price axis, all book legs) is
   Yahoo-only; `core_stock_apis` (EODHD first, `default_config.py:767`) is never
   consulted, and `moomoo.get_stock_data_moomoo` (`request_history_kline`) is
   unreachable from these engines. `_ohlcv`'s own docstring says "via the vendor
   chain" (`:230`).
2. **Sentiment and News hardcode Alpha Vantage.** `_av_news_articles`
   (`analysis_tools.py:11704`) → `alpha_vantage_news.get_news`
   (`alpha_vantage_news.py:83`); the tone series is resolved by an inline
   re-implementation of the `news_sentiment` chain in
   `_sentiment_points_with_source` (`:7930`) — EODHD first, AV second, GDELT
   declining (`gdelt.py:243`). The `news_data` chain (reddit, seekingalpha,
   benzinga, eodhd `/news`, moomoo news) never reaches either engine.
3. **EventScore calls the moomoo SDK directly.** `catalyst.py:436` (earnings),
   `:525` (economic), `:532` (Fed watch) — no finnhub/yfinance/benzinga
   fallback, unlike the `earnings_calendar` chain the analyst tool uses
   (`moomoo.py:1384`, which raises to trigger finnhub).

## 5. Divergence ledger (D1–D12)

Grouped, because several share one cause. Each is a real gap between what the
documentation or a reader would assume and what the code does. **None is fixed
by the document that records it.**

**D1 — the price path bypasses the vendor chain** (§4.1).

**D2 — several engines hardcode one vendor regardless of the configured chain**
(§4.2): sentiment/news on Alpha Vantage; the options legs read yfinance
directly (`analysis_tools.py:10847-10882`) while the chain is `moomoo,yfinance`;
the EventScore calendars on moomoo.

**D3 — two producers for one key.** `fcf_yield` (`capex_quality.py:247` vs
`ratios.py:724`), `earnings_yield` (EBIT/EV in `quantitative_scores.py:251` vs
NI/MC in `ratios.py:725`), and the tone series (EODHD-first for the SMA legs,
AV-only for the weighted legs).

**D4 — declared-but-unsupplied components.** 19 of RiskScore's 34 declared keys
never appear in `_risk_components` (`analysis_tools.py:7197`), including the
entire `event` category; NewsScore's `fundamental_impact` has no producer at
all.

**D5 — floors can make a declared engine unpublishable.** With the shipped empty
basket, RiskScore's book categories are unmeasurable, leaving 2 of 8 categories
against a floor of 3, so the composite withholds even with the gate on. Live
cards publish volatility + tail + liquidity + drawdown and withhold gap,
correlation, concentration and event (coverage 0.45-0.55).

**D6 — `near_sma200` compares a fraction to 3.0.** `support_structure` returns
`(p − SMA200)/SMA200` (`value_dip.py:897`), and the caller tests `<= 3.0`
(`analysis_tools.py:6573`) — "within 300 %" — so the leg is effectively always
true when measurable.

**D7 — banded legs missing from `NON_MONOTONIC_INPUTS`.** `keltner_pct` is
band-mapped and annotated NON-MONOTONIC (`technical_score.py:170`) but only
`stoch_rsi` is declared (`score_engine.py:47`), so the raw→aligned evidence
triple is never printed for it.

**D8 — two different numbers share one name.** `momentum_score` returns a
weight-fraction `coverage` and a leg-count `meta.coverage`; `fundamental_score`
reports `panel_n` for both the resolved panel and the DCF-supplied count.

**D9 — the EventScore horizon is narrower than its fetch.**
`HORIZONS["earnings"] = 60` over a 95-day fetch (`catalyst.py:37`), and the
company calendars have no horizon filter at all: an event past the horizon
scores 0.0 and counts as *present*, inflating coverage.

**D10 — double mapping.** `rs_percentile` (0-100) is fed back through its own
ramp when `reference=` normalisation runs.

**D11 — stale line citations inside the ledgers.** The `COMPONENTS` tables in
`technical_score`, `sentiment_score`, `risk_score`, `event_state` and
`momentum_score` cite producer line numbers that have drifted (e.g.
`risk_score.py` cites `portfolio_cvar:28`, actual `:61`).

**D12 — the card and the prompt can disagree if the snapshot is missing** (§3).

## 6. Changing a component

1. Declare it in the engine's `COMPONENTS` / `COMPONENT_WEIGHTS` with direction,
   exact mapping and producer citation.
2. Supply it in the matching `_*_components` builder in
   `agents/utils/analysis_tools.py` — a missing key is an absent component, a
   fabricated 0 is a defect.
3. If the value is non-monotone, add it to `score_engine.NON_MONOTONIC_INPUTS`,
   or its evidence triple is unreachable.
4. Measure any new prompt text against `tests/test_prompt_budget_contract.py`
   (`LONGEST_BULLET_LIMIT` is the binding constraint).
5. Land the engine change, the run-card block, the report render, the external
   formula document and this file in one commit.
