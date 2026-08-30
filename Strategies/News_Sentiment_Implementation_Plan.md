# News-Sentiment Factor — Implementation Plan

Status: **plan — no code changes yet.** Companion to `Strategies/News_Sentiment.md`
(the method spec: Alpha Vantage `NEWS_SENTIMENT` feed + lead/lag, multi-horizon
Newey-West regression, quintile long/short, sector/size neutralization, rolling
IC, IC term structure/half-life). This plan maps every spec item onto what the
fork **already has**, so the work is analytics + wiring, almost no new data.

---

## 0. What News_Sentiment.md specifies (condensed)

| # | Method | What it needs |
| --- | --- | --- |
| 1 | **Daily sentiment series** | AV `NEWS_SENTIMENT` feed → per-article `ticker_sentiment_score` (−1..1, `relevance_score` 0..1, fallback `overall_sentiment_score`) → daily mean → calendar-reindexed **7-day SMA**; pagination via `time_from`/`time_to`; timestamps bucketed so articles after 16:00 ET belong to the **next trading day** (lookahead guard) |
| 2 | **Lead/lag cross-correlation** | sentiment vs forward returns, lags `k ∈ [-10, +10]`, Pearson + Spearman + p-values; also test **raw innovations** (`S_t − S_{t−1}`) because the SMA auto-correlates |
| 3 | **Multi-horizon regression** | `R_{t→t+h} = α + β1·Sent_t + β2·R_{t−1} + β3·Δln(Vol_t) + ε`, h ∈ {1,3,5,10,20}, **Newey-West HAC** errors (maxlags ≥ h+1) for overlapping windows |
| 4 | **Quintile long/short backtest** | weekly rebalance, long Q5 / short Q1, 10 bps one-way cost, OOS split, Sharpe/max-DD; monotonicity + turnover + survivorship checks |
| 5 | **Sector + size neutralization** | per-date z-score within sector (min 3 names); then cross-sectional OLS of sentiment on log-mcap + sector dummies (`drop_first`) → residual = pure idiosyncratic signal |
| 6 | **Rolling Information Coefficient** | per-date Pearson + Rank IC vs forward h-day return; rolling mean; IC-IR (×√(252/h)); 1-sample t-test; benchmarks: mean rank IC 0.02–0.05, IR_IC > 1.0, % positive > 55–60% |
| 7 | **IC term structure / alpha decay** | mean Rank IC across h ∈ [1,30], exponential fit → half-life; fast (1–3d) = high-turnover, medium (5–15d) = bi-weekly/monthly, inverted = pair with reversal |

---

## 1. What the project already has (verified against source)

### 1.1 The data feed is ALREADY live — the vendor layer calls NEWS_SENTIMENT
- `tradingagents/dataflows/alpha_vantage_news.py::get_news` and
  `get_global_news` call `_make_api_request("NEWS_SENTIMENT", params)` with
  `tickers` / `time_from` / `time_to` and return the **raw feed** (dict/JSON
  string). `get_news` registers as the `alpha_vantage` vendor in the
  `news_data` chain tail. The doc's exact `ticker_sentiment[]` /
  `overall_sentiment_score` fields are in the response today but **never
  parsed** — the analyst sees the raw JSON, not a series.
- Keyless / additional sentiment feeds already wired:
  - `dataflows/gdelt.py::get_gdelt_tone_series` — daily avg-tone timeline
    (keyless; GDELT keeps a rolling ~3-month window; network-flaky, opt-in).
  - `dataflows/massive.py::get_news_massive` — per-article
    positive/negative/neutral + reasoning (key-gated, entitled plan).
  - `strategies/sentiment.py::compute_social_scores` — StockTwits labeled
    counts → signed score + **surprise velocity z** vs a persisted per-ticker
    rolling baseline (cache dir file), exposed as the `get_sentiment_computed`
    market tool and injected into the sentiment report (`enable_sentiment`
    default True).

### 1.2 Statistics (deps verified)
- `numpy`, `pandas>=2.3`, `scipy` **installed** (`statistical.py` already uses
  `scipy.stats`). `statsmodels` and `plotly` are **not** in `pyproject.toml` or
  the env; the repo's pattern is pure-NumPy implementations (see
  `statistical.unit_root` ADF/KPSS with critical-value tables).
- `strategies/statistical.py` already provides: `correlation_matrix`
  (pearson/spearman/kendall), `ols_factors` (pure-NumPy OLS with params/t/p/
  bse/CI), `normality`, `capm_decomposition`, `variance_inflation_factor`.

### 1.3 Evaluation & backtest
- `strategies/evaluate.py` — `net_returns(cost_bps)`, sharpe, sortino,
  deflated sharpe, max_drawdown, walk-forward splits, `pbo_flag`, calmar /
  ulcer / capture / tail-ratio / expectancy.
- `strategies/backtest_engine.py` + `backtest_models.py` (fill matching,
  `fixed_fee` / `maker_taker_fee` bps) + `scripts/backtest_strategy.py`.
- `scripts/evaluate_config_gate.py` (G5 walk-forward + PBO), `scripts/strategy_quality_report.py`,
  `scripts/orderflow_evaluate.py`.

### 1.4 Cross-sectional inputs
- Universe: screener `--universe eodhd-us` (~18k US symbols, no quota) or
  `top-losers` / `heat-proxy`.
- Sector: `get_sector_rank` / FMP → Finnhub → yfinance (sector_rank.py,
  `--sector-rank` / `--enrich-sector`).
- Market cap: `strategies/ratios.py` (`get_ratios`, free local) + yfinance.
- OHLCV: `_RUN_OHLCV_CACHE` shares one vendor fetch per (ticker, days) per run.

### 1.5 Wiring conventions (apply to every phase)
- Compute-as-tools: deterministic calculators wrapped as `@tool`s bound to the
  analyst ToolNodes (`compute_social_scores` is the model — score + z + counts,
  explicit "unavailable").
- No-fabrication: every function returns `float | None` / `dict | None` with a
  minimum-observation guard; sentinels never fabricated.
- New gates default OFF (`enable_*`), keys via `TRADINGAGENTS_*`/`.env`.
- Every change: tests with `pytest-timeout`, ruff clean, docs/README/CHANGELOG
  true, trading_web surface mirrored, commit + push.

---

## 2. Phases

### Phase 1 — Deterministic sentiment series (pure, offline)
**File:** `tradingagents/strategies/sentiment.py` (extend)

- `aggregate_daily_sentiment(articles, ticker, day_cutoff_time="16:00",
  tz="America/New_York")` → `[{date, score, n_articles, relevance_mean}]`
  - per-article: `ticker_sentiment_score` when the `ticker_sentiment[]` entry
    matches; fallback `overall_sentiment_score` (flagged); skip neither.
  - article timestamps after `day_cutoff_time` on trading day t are bucketed
    to the next trading day (the doc's lookahead rule).
- `daily_sentiment_sma(series, window=7)` → calendar-reindexed `daily_mean`,
  `sma_7d` (min_periods=1), `innovation = score_t − sma_7d_{t−1}` (doc: "raw
  daily sentiment innovations" for novelty/shock tests), `mention_count/day`.
- Generic enough to reuse for GDELT tone and Massive per-article sentiment
  (both already provide per-day/per-article values).
- Guards: < 3 non-null days → `None`; tz-aware timestamps only.

**Tests:** extend `tests/test_strategies_sentiment.py` — synthetic feed with
known scores; calendar reindex across a weekend; post-close bucketing; SMA/
innovation math; None guards. All offline.

### Phase 2 — Research/evaluation module (pure, offline)
**File:** `tradingagents/strategies/sentiment_research.py` (new)

- `sentiment_lead_lag(sent, returns, max_lags=10)` → per-lag Pearson/Spearman
  + p + n (scipy; reuse `statistical` style). Accepts `innovations` flag.
- `multi_horizon_sentiment_regression(df, horizons=[1,3,5,10,20])` →
  per-h OLS with controls `ret_lag1`, `Δln(vol)` and **Newey-West HAC**
  covariance (Bartlett kernel, `maxlags = max(1, h+1)`), pure NumPy (~30 lines,
  no statsmodels dependency — consistent with the repo's ADF/KPSS precedent).
  Reports β_sent, t, p, adj-R², n; < 30 clean obs → None.
- `quintile_long_short(prices, signals, rebalance="W-FRI", cost_bps=10,
  oos_split=None)` → per-date Q1..Q5 + LS-net; metrics via `evaluate.py`
  (ann return, vol, Sharpe, max DD); monotonicity (Q5>Q4>…>Q1 share) and
  turnover (share of names changed per rebalance); requires ≥ 10 names/date.
- `sector_neutral_z(signals, sector_map, min_assets=3, winsorize=3.0)` and
  `residualize_sentiment(signals, mcap, sector_map, min_assets=15)` →
  per-date cross-sectional OLS of sentiment on `log_mcap` + sector dummies
  (`drop_first`), standardized residuals (pure NumPy, reuse
  `statistical._ols_resid`).
- `rolling_information_coefficient(signals, prices, holding=5, window=12)` →
  per-date Pearson/Rank IC + rolling mean + IC-IR (√(252/h)) + t-test.
- `ic_term_structure(signals, prices, max_horizon=30, min_assets=15)` →
  per-h mean Rank IC/IR/t/p + exponential decay fit (`scipy.optimize.curve_fit`)
  + half-life.

**Tests:** `tests/test_strategies_sentiment_research.py` — synthetic panels
(reuse the doc's own simulation approach: seeded random walks + a planted
predictive tilt), assert IC/decay recovery, HAC Wider-CI sanity vs plain OLS,
neutralization drives corr(signal, log-mcap) → ~0.

### Phase 3 — Feed parsing + agent tools (compute-as-tools)
**File:** `tradingagents/dataflows/alpha_vantage_news.py` (+ gdelt.py, interface.py)

- New `get_news_sentiment_series(ticker, start, end)` on the AV module:
  reuses the existing `NEWS_SENTIMENT` call, **parses** `ticker_sentiment[]`
  into the Phase-1 daily series (mean + 7d SMA + innovation + n), renders
  markdown (vendor contract). Register as `alpha_vantage` for a new optional
  category `news_sentiment` (`VENDOR_METHODS["get_news_sentiment"]["alpha_vantage"]`,
  `OPTIONAL_CATEGORIES`). GDELT variant aggregates `get_gdelt_tone_series`
  (keyless); Massive variant aggregates per-article sentiment (key).
- Free-tier reality: AV is 25 req/day → **tail** of the chain, never first;
  `vendor_cache` TTL already applies (news excluded → keep exclusion, but the
  series is computed data — cacheable in the new category).

**Tools** (`agents/utils/analysis_tools.py`, bound to market/sentiment ToolNode):
- `get_news_sentiment_series(ticker, look_back_days=30)` — daily mean + 7d SMA
  + latest innovation + mention count (AV → GDELT → Massive, each labeled).
- `get_sentiment_lead_lag(ticker, max_lags=10, innovations=False)` — the
  cross-correlation table (market tool; grounds "sentiment leads/lags" claims).
- `get_sentiment_computed` (existing) upgraded: append the series line
  (`sma_7d`, `innovation`) next to score + velocity — backward compatible.
- Per-ticker IC/decay stay **script-level** (they need a cross-section;
  a single-name "IC" would be fabricated breadth — honest scope).

### Phase 4 — Cross-sectional factor evaluation (screener + scripts)
**File:** `scripts/sentiment_factor_eval.py` (new; mirrors
`evaluate_config_gate.py` conventions)

- Universe from `--universe` (default `eodhd-us`), `--limit`.
- Per-name daily sentiment (AV key-gated; names without AV coverage fall back
  to GDELT), sector + mcap via existing vendors, returns via the run OHLCV
  cache.
- Builds the panel: `sector_neutral_z` → `residualize_sentiment` → rolling IC +
  IC term structure + half-life → quintile long/short (OOS via
  `evaluate_config_gate`-style walk-forward split, fees via
  `backtest_models.fixed_fee`).
- Output: markdown report + jsonl rows; `--walk-forward` reuses the G5 gate.
- `scripts/strategy_quality_report.py`: optional sentiment-factor header
  (mean rank IC, IC-IR, half-life, LS Sharpe) — advisory rows from the eval
  output when present.
- Screener optional `--sentiment-factor` columns: `Sent7` (7d tone SMA),
  `SentZ` (innovation z) — computed only when article coverage ≥ min (honest
  `n/a` otherwise; never fabricated).

### Phase 5 — Optional overlay gate (default OFF, per repo convention)
- New config: `enable_sentiment_factor` (+ `sentiment_factor_min_coverage`,
  `sentiment_factor_min_ic`, `sentiment_factor_max_scale` 1.2 / min 0.5).
- `_apply_strategy_overlays`: fold `sentiment_scale` into the contract
  multiply **only when** measured IC ≥ floor and coverage ≥ min; otherwise
  scale = 1.0 (never blocks, matches catalyst's neutral default). The doc's
  decay analysis feeds the *cadence* (holding-period guidance for
  pre_market_review / swing) rather than new order machinery — the repo is
  analysis-only.

### Phase 6 — trading_web + docs
- trading_web: `run_value_tools` += `get_news_sentiment_series` /
  `get_sentiment_lead_lag` (+ App.jsx options, README sync table, hermetic
  test), per working agreement.
- Docs: `docs/api_reference.md` §5/§6.1/§6.4, `docs/developer/04-strategies.md`,
  `docs/AGENT_ONBOARDING.md` changelog, `CHANGELOG.md`.

---

## 3. Decisions / honest limits

- **No new vendor.** AV `NEWS_SENTIMENT` is already wired; the doc's feed is
  live today, only its analytics are missing.
- **No statsmodels, no plotly.** Newey-West in pure NumPy (repo precedent:
  `statistical.unit_root`); the scripts print tables (the web SPA already has
  charting via existing endpoints if needed later).
- **GDELT ≈ 3-month window** caps history for long-horizon IC/regression —
  AV is the historical path (limit 200, paginate via `time_from`/`time_to`;
  premium 1,000). Document the coverage tradeoff per feed.
- **Lookahead is structural:** post-16:00 ET articles bucket to the next
  trading day (Phase 1), and the eval's "signal as of t vs return t→t+h"
  alignment must use close-of-t buckets — same discipline as
  `alpha_vantage._filter_reports_by_date`.
- **Breadth threshold:** cross-sectional analyses (IC, quintiles,
  neutralization) degrade cleanly below 10–15 names/date — a narrow universe
  still gets single-name lead/lag only.
- **IC benchmarks** (0.02–0.05 mean rank IC, IR > 1.0, >55–60% positive) and
  the three decay profiles from the doc become the gate thresholds in Phase 5,
  not just commentary.

## 4. Sequencing & validation

P1 → P3 → P2 → P4 → P5 → P6 (P2 is independent of P3; build P1 first so both
consume it). Each phase: unit tests with `pytest-timeout`, `ruff check`, full
suite green, commit + push, docs true. Live smoke at P4:
`py -3.12 scripts/sentiment_factor_eval.py --universe eodhd-us --limit 20`
prints IC term structure, half-life and LS Sharpe from real AV + GDELT.

Mapping: **News_Sentiment.md §1 → Phase 1**, §2–3 → Phase 2, §(feed) → Phase 3,
§4–6 (backtest/neutralization/IC) → Phase 4, §7 (decay) → Phase 5 cadence input.