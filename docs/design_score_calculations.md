# Score calculations and data provenance

**What this document is.** One place that answers, for every score this tree
computes: *what is the arithmetic*, *which raw field feeds each term*, and
*which provider endpoint produced that field*. It is the as-built reference, not
a design proposal: every line number points at the code that runs today. The
per-engine design documents in `docs/scores/` answer "what should this engine
be"; this one answers "what is it, and where does its data come from".

Scope: the nine engine blocks persisted into `run_card.json`
(`fundamental_score`, `technical_score`, `momentum_score`, `sentiment_score`,
`news_score`, `event_state`, `regime_score`, `risk_score`, `trade_score`), the
`quant_scorecard` that aggregates them, and the screening scores that are
computed but not scored (`piotroski_f_score` and its paper-basis variant, the
Graham/Piotroski G-score, the Montier C-score), plus the quality composite and
the score evaluation rows.

---

## 1. Invariants every engine holds

These are structural. A change that breaks one is a defect, not a variant.

| # | Invariant | Where it is enforced |
| --- | --- | --- |
| 1 | **Absent is never 0 and never 50.** A component that could not be measured is `None` and leaves the denominator; it is never substituted with a neutral. | `strategies/score_engine.py:68` (`align`), `:141` (`combine`) |
| 2 | **The score is a weight-renormalised mean over the components that were measured**: `Σ wᵢ·vᵢ / Σ wᵢ`. | `score_engine.py:225` |
| 3 | **`coverage` is a weight FRACTION; `floor` is a component COUNT.** They are different units and are printed side by side. | `score_engine.py:196-205` |
| 4 | **Below the floor the score is withheld**, with a reason string, not published and not zeroed. | `score_engine.py:206-215` |
| 5 | **The floor resolves against the DECLARED component set, not the survivors.** | `score_engine.py:52` (`coverage_floor`) |
| 6 | **One producer per number.** Where the run card and the prompt both show a score, the card reads the run's own snapshot rather than recomputing it. | `reporting.py:1144` (fundamental), `:1287` (trade), `:1446` (scorecard) |
| 7 | **Scores are advisory.** No engine sets a rating, a position size or a gate. The one exception is the catalyst *hard block*, which is a producer's own verdict passed through, never an engine score. | `strategies/event_state.py:615`; `graph/trading_graph.py:1378` |
| 8 | **A gate-off run is byte-identical to a pre-engine run**: the block is `None` and the key is omitted. | every `_run_card_*` in `reporting.py` |

---

## 2. The kernel and the two data paths

### 2.1 The kernel — `strategies/score_engine.py`

```python
align(value, *, direction="higher_better"|"lower_better", band=None, lo=None, hi=None)
```

Two shapes, one function:

- **Ramp** — `lo` maps to 0, `hi` maps to 100, clamped; `lower_better` inverts
  (`frac = 1 - frac`). Both edges are required.
- **Band table** — the producer's own `[(edge, score), ...]`, walked **top-down**
  (first edge ≤ value wins). Used for the non-monotone legs, whose relationship
  is not a ramp. A value below the lowest edge returns `None`.

`None` in → `None` out; non-finite or unusable input → `None`; a band table takes
precedence over `direction` (so `direction` on a banded leg is descriptive only).

```python
combine(components, *, weights=None, min_coverage=3, bands=None) -> dict
```

- `weights=None` → **equal weight** over the declared components.
- A component with no declared weight (or weight 0) is **dropped** and named in
  `basis`.
- `coverage = Σ w(present) / Σ w(total)`; `floor = coverage_floor(min_coverage, n_declared)`,
  where a float in `(0,1]` is a fraction and anything else is a count.
- `band_label(score, bands)` walks the engine's own `[(floor, label), ...]` top-down.

`NON_MONOTONIC_INPUTS` (`score_engine.py:47`) names the leg(s) whose raw→aligned
pair must be printed as a triple. Today it holds `stoch_rsi` only.

### 2.2 Path A — the vendor router

Most *statement*, *news*, *macro* and *calendar* reads go through
`dataflows/interface.py:750 route_to_vendor(method, ...)`, which resolves a
`method` to a category and that category to an ordered chain
(`default_config.py:767-803`):

| Category | Chain (first = primary) | Serves |
| --- | --- | --- |
| `core_stock_apis` | `eodhd, moomoo, yfinance, tiingo, twelve_data, stockdata, benzinga` | `get_stock_data` |
| `technical_indicators` | `moomoo, yfinance, alpha_vantage` | indicator tool |
| `fundamental_data` | `moomoo, yfinance, tiingo, alpha_vantage` | fundamentals, balance sheet, cashflow, income statement |
| `news_data` | `eodhd, benzinga, moomoo, yfinance, alpha_vantage, stockdata, newsapi` | `get_news`, insider transactions |
| `news_sentiment` | `eodhd, alpha_vantage, gdelt` | daily sentiment series |
| `macro_data` | `fred, moomoo` | macro series |
| `prediction_markets` | `polymarket, moomoo` | event contracts |
| `analyst_ratings` | `moomoo, finnhub, yfinance, benzinga` | consensus, targets |
| `earnings_calendar` | `moomoo, finnhub, yfinance, benzinga` | next/forward prints |
| `options_data` | `moomoo, yfinance` | chains |

A chain member that fails raises `NoMarketDataError` (or the vendor's own error)
and the router advances to the next member.

### 2.3 Path B — the direct clients

Several score inputs **bypass the router entirely**. This is the single most
important provenance fact in this document, because the configured chain does not
apply to them:

| Surface | Client | Endpoint / SDK call | Code |
| --- | --- | --- | --- |
| **Every price bar** used by technical, momentum, risk, sentiment's price axis, regime, breadth, and all book legs | yfinance | `yf.download(symbol, start, end, auto_adjust=True)` — 5-year CSV cache in `data_cache_dir`, tail refresh, truncated to 320 bars | `dataflows/stockstats_utils.py:274 load_ohlcv`, `:336` (and `:245`) |
| Tone series | EODHD first | `GET https://eodhd.com/api/sentiments?s={ticker}&from=&to=` | `dataflows/eodhd.py:288` |
| Tone series fallbacks | Alpha Vantage, then GDELT (which always declines) | `GET https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=…`; `gdelt.py:243` returns `None` | `alpha_vantage_news.py:83`, `gdelt.py:243` |
| Article set for sentiment/news | Alpha Vantage | same `NEWS_SENTIMENT` endpoint, 30/120-day window | `agents/utils/analysis_tools.py:11704` |
| Statements (fundamentals, F/G/C scores) | moomoo → yfinance → tiingo → alpha_vantage (router) | OpenD `ctx.get_financials_statements(code, statement_type=1|2|3, financial_type=7|9, num=8)`; `yf.Ticker(...).balance_sheet/income_stmt/cashflow`; `GET https://api.tiingo.com/tiingo/fundamentals/{sym}/statements?statementType=…`; `function=BALANCE_SHEET|INCOME_STATEMENT|CASH_FLOW` | `dataflows/moomoo.py:1085`, `y_finance.py:684-756`, `tiingo.py:286-330`, `alpha_vantage_fundamentals.py:48-63` |
| Earnings / macro / Fed calendars (EventScore, NewsScore materiality) | moomoo OpenD | `get_earnings_calendar`, `get_economic_calendar`, `get_fed_watch_target_rate`, `get_financials_earnings_price_history` | `strategies/catalyst.py:436, 520, 525, 532` |
| Institutional flow | moomoo OpenD | `ctx.get_shareholders_institutional(code)` | `dataflows/moomoo.py:2604` |
| VIX level percentile | FRED | `GET https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&observation_start=&observation_end=&file_type=json` | `dataflows/fred.py:73`, `:249` |
| VIX term structure | Cboe CDN | `GET https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX9D_History.csv`, `…/VIX3M_History.csv` | `dataflows/cboe.py:30-32`, `:282` |
| Corporate filings (news_score) | SEC EDGAR | `GET https://data.sec.gov/submissions/CIK{cik:010d}.json` | `dataflows/sec_edgar.py:36`, `:478` |
| S&P 500 universe (every breadth leg) | Wikipedia API | `GET https://en.wikipedia.org/w/api.php?action=parse&page=List of S&P 500 companies&prop=wikitext&format=json` | `dataflows/sp500_universe.py:23`, `:120` |
| Social | StockTwits | `GET https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json` | `dataflows/stocktwits.py:29` |
| Product/clinical calendar (EventScore) | pdufa.bio | `GET https://www.pdufa.bio/api/v1/events?ticker={TICKER}&limit=200` | `dataflows/event_calendars.py:190` |
| Guidance changes (news_score) | Benzinga | `GET https://api.benzinga.com/api/v2.1/calendar/guidance?parameters[tickers]=…` | `dataflows/benzinga.py:456-470` |
| Options legs (sentiment, risk) | yfinance | `yf.Ticker(t).options` → `option_chain(expiry)` | `agents/utils/analysis_tools.py:10847-10882` |
| Short interest | yfinance | `Ticker.info["shortPercentOfFloat"]` | `dataflows/yfinance_short_interest.py:55` |
| Analyst revisions / agreement | yfinance | `Ticker.upgrades_downgrades` | `dataflows/yfinance_sector.py:159-245` |
| Peer set (fundamentals) | Finnhub SDK | `client.company_peers(ticker)` | `dataflows/finnhub.py:408` |
| Sector label | FMP → Finnhub → yfinance | FMP `profile`; `company_profile2`; `Ticker.info.sector` | `dataflows/yfinance_sector.py:64-119` |

**Consequence to state plainly:** the `core_stock_apis` chain is never consulted
by any score. `moomoo.get_stock_data_moomoo` (`request_history_kline`) exists and
is unreachable from these engines. A "why is EODHD not used for the technical
score" question has the answer "because the technical score calls `yf.download`
directly" — see §7 divergence D1.

---

## 3. Engine catalogue

| Block (`run_card.json`) | Engine module | Gate (shipped default) | Weight vector | Floor |
| --- | --- | --- | --- | --- |
| `fundamental_score` | `strategies/fundamental_score.py:252` | `enable_fundamental_score` (`default_config.py:1353`, **False**) | equal 1/4 over 4 sub-scores | 2 of 4 |
| `technical_score` | `strategies/technical_score.py:363` | `enable_technical_score` (`:1355`, **False**) | categories 20/18/12/12/10/10/8/5/5 | 3 of 9 categories (each 2 legs) |
| `momentum_score` | `strategies/momentum_score.py:644` | `enable_momentum_score` (`:1363`, **False**) | legs P .25 / R .15 / T .20 / A .10 / B .05 / V .10 / Q .10 / D .05 | 3 of 8 legs (each 2 members) |
| `sentiment_score` | `strategies/sentiment_score.py:467` | `enable_sentiment_score` (`:1369`, **False**) | categories 15/15/10/15/10/10/10/5/5/5 | 3 of 10 (each 1 component) |
| `news_score` | `strategies/news_score.py:1371` | `enable_news_score` (`:1372`, **False**) | 11 components 10/10/15/20/10/5/10/5/5/5/5 | 2 of 11 (each 1) |
| `event_state` | `strategies/event_state.py:591` | `enable_event_state` (`:1377`, **False**) | equal over 7 families | 2 of 7 |
| `regime_score` | `strategies/regime_score.py:265` | `enable_regime_score` (`:1390`, **False**) | equal (no vector published) | 3 of 6 |
| `risk_score` | `strategies/risk_score.py:521` | `enable_risk_score` (`:1393`, **False**) | categories 15/15/10/10/15/10/15/10, **inverted** (100 = low risk) | 3 of 8 categories (each 2) |
| `trade_score` | `strategies/trade_score.py:293` | `enable_trade_score` (`:1373`, **False**) | F .40 / T .25 / R .15 / K .20 | 2 of 4 |
| `quant_scorecard` | `strategies/quant_scorecard.py:501` | `enable_quant_scorecard` (`:1405`, **False**) | — (container) | — |

The live `.env` turns every one of these on except `enable_quality_composite`;
the shipped defaults are all off, which is why a fresh clone produces no score
blocks at all.

---

## 4. Engine by engine

### 4.1 FundamentalScore — cross-sectional, not a ramp

Entry: `agents/utils/analysis_tools.py:6452 get_fundamental_score` →
`strategies/fundamental_score.py:861 fundamental_score_for_ticker`.
Also read by `reporting.py:1169` and `quant_scorecard.py:260`, both from the
run's snapshot.

**Formula.** This engine never calls `align`. Each factor is mapped by
`strategies/factors.py:258 category_scores`:

```
winsorise 0.01/0.99  →  cross-sectional z  →  × direction sign
→ equal-weight mean over present factors  →  tie-aware percentile × 100 over the scored peers
```

The four sub-scores are then combined by `combine` with **equal 1/4 weights**
(`fundamental_score.py:291-295`). There are no per-factor weights anywhere:
`factor_schema._spec` hard-codes `base_weight=None` (`factor_schema.py:118-141`),
so "weight" below means `1/n` over the factors a name actually carries.

| Sub-score | Floor (resolved) | Factors (direction) |
| --- | --- | --- |
| `FQS` quality | 3 of 7 | `return_on_equity` (+), `return_on_assets` (+), `gp_a` (+), `f` (+), `m` (−), `noa` (−), `accruals` (−) |
| `FGS` growth | 2 of 2 | `revenue_yoy` (+), `eps_yoy` (+) — `rev_cagr5` is declared NA |
| `VS` valuation | 3 of 11 | `ev_ebitda`, `ev_ebit`, `ev_sales`, `price_to_earnings`, `price_to_book`, `price_to_sales`, `price_to_cash_flow`, `price_to_free_cash_flow` (all −), `earnings_yield` (+), `fcf_yield` (+), `dcf_upside` (+) — `val_z` is declared NA |
| `FRS` financial risk | 3 of 6 | `z` (+), `o` (−), `zmijewski_x` (−), `debt_to_equity` (−), `current` (+), `quick` (+) |

Every sub-score is called with the same `min_coverage=3` (`fundamental_score.py:116`);
`_cap_floor` (`:151`) caps it at the sub-score's own declared count, which is why
`FGS` resolves to 2 — a floor of 3 over two suppliers would withhold every name
forever.

**Factor arithmetic** (`strategies/ratios.py`, `dataflows/quantitative_scores.py`,
`strategies/normalized.py`):

| Factor | Formula | Code |
| --- | --- | --- |
| `return_on_equity` / `return_on_assets` | `NI/TE`, `NI/TA` | `ratios.py:802-803` |
| `gp_a` | `(revenue − cogs) / TA` | `quantitative_scores.py:299` |
| `f` | 9 binary Piotroski signals, summed 0-9 | `quantitative_scores.py:202` |
| `m` | Beneish, `M_CONSTANT + Σ wᵢ·indexᵢ` over 8 indices | `quantitative_scores.py:113` |
| `noa` | `(operating assets − operating liabilities) / TA_prior` | `quantitative_scores.py:322` |
| `accruals` | `(NI − CFO) / TA` | `normalized.py:62` |
| `revenue_yoy` / `eps_yoy` | `(cur − prior)/prior` from the statement pair; vendor YoY only when no pair exists | `statement_parsing.py:1101`, `:1081` |
| `ev_*`, `price_to_*` | EV and market-cap multiples | `ratios.py:794-801` (EV `:660`, EBITDA `:273`, FCF `:683`) |
| `earnings_yield` | **EBIT/EV** (`quantitative_scores.py:251`) — not NI/MC | `peer_universe.py:154` |
| `fcf_yield` | `(OCF − |capex|) / MC`, latest annual | `capex_quality.py:247` |
| `dcf_upside` | `(FV − price)/FV × dcf_confidence`; `dcf.compute_dcf` with rf 4 %, ERP 5 %, g 2.5 %, 5 y, else cycle-normalised FCF | `fundamental_score.py:717`, `:750-809`, `dcf.py:71`, `cycle_dcf.py:23` |
| `z` | Altman `1.2x₁+1.4x₂+3.3x₃+0.6x₄+1.0x₅` | `quantitative_scores.py:181` |
| `o` | Ohlson O logit | `normalized.py:178` |
| `zmijewski_x` | `−4.336 −4.513·ROA +5.679·(TL/TA) −0.004·(CA/CL)` | `normalized.py:238` |
| `debt_to_equity` | `TD/TE`, `None` when > 10 | `ratios.py:804` |
| `current` / `quick` | `CA/CL`, `(CA − inventory)/CL`; nulled if CA>TA or CL>TL | `ratios.py:675-681, 805-806` |

**Data provenance.** One statement fetch per name,
`statement_parsing.fetch_ticker` (`:1395`), makes exactly four routed calls —
`get_fundamentals`, `get_cashflow`, `get_balance_sheet`, `get_income_statement` —
against the `fundamental_data` chain (`moomoo → yfinance → tiingo → alpha_vantage`,
`default_config.py:775`). The vendor endpoints are the ones in §2.3. Two fills sit
on top:

- **Finnhub basic financials** (`client.company_basic_financials(symbol, "all")`,
  `finnhub.py:362`) supplies `eps_yoy`, `revenue_yoy`, `roe`, `market_cap`, `beta`
  **only when the routed fetch left the field missing** (`statement_parsing.py:1487`).
- **Peer set** from `client.company_peers(ticker)` (`finnhub.py:411`), first 8 names
  (`peer_universe.py:213`); the panel then re-fetches each peer's statements live
  with **no cache** (`peer_universe.py:322`).

**Period semantics.** Annual everywhere: moomoo `financial_type=7` tables trimmed
to 4 periods, yfinance annual statements date-filtered, tiingo annual window,
Alpha Vantage `annualReports` preferred. `fetch_ticker` never calls
`trailing_twelve_months`, so `*_ttm` keys are absent and every flow falls back to
the as-reported annual figure (`ratios.py:107`).

**Coverage / withhold.** Peer floor `min_peers=8` (`fundamental_score.py:116,866`);
sub-score floors 3/2/3/3 (`:128-132`); a factor present for fewer than
`max(2, floor)` *names* is dropped before the z-score (`factors.py:327`);
composite floor 2 of 4. Below any floor the block publishes `score=None` plus the
reason; bands apply to sub-scores only (`:145-147`).

**Divergences.** `_derive_dcf_upside` passes `basis=None` to `dcf_confidence`
(`:718-726`) although it builds a basis string two lines later, so the
data-quality leg is pinned at 0.6; `compute_ratios` is called without `price`
(`peer_universe.py:158`), so the P/E fallback (`ratios.py:706`) is dead; two
producers exist for `fcf_yield` and for `earnings_yield` and the panel picks one
of each silently (`peer_universe.py:78-92`).

### 4.2 TechnicalScore — 9 categories, 18 legs

Entry: `analysis_tools.py:6782 get_technical_score`; builder
`analysis_tools.py:6487 _technical_components`; also called by
`reporting.py:1240` and `quant_scorecard.py:284` from the same builder.

**Weights.** `CATEGORY_WEIGHTS` (`technical_score.py:50`) is the only vector:
trend 20, momentum 18, relative_strength 12, price_structure 12, volume 10,
breakout 10, mean_reversion 8, volatility 5, breadth 5. Inside a category
`combine` is called **without** weights (`:331`), so legs are equal-weighted and
a category's weight is split evenly across its legs.

| Leg | Category | Raw input | Mapping (exact) |
| --- | --- | --- | --- |
| `sma_stack` | trend | bool: EMA20 > SMA50 > SMA200, SMA50 rising (5 bars), SMA200 rising (15 bars) | band `[(1,80),(0,30)]` |
| `aroon_osc` | trend | `aroon_up − aroon_down`, each `(25 − bars_since_extreme)/25·100` | ramp −60 → 0, +60 → 100 |
| `momentum_12_1` | momentum | `P(t−21)/P(t−273) − 1` | ramp −0.20 → 0, +0.40 → 100 |
| `rs_slope_pct` | relative_strength | OLS slope of the RS line over 63 bars, normalised by its mean, %/day | ramp −0.10 → 0, +0.10 → 100 |
| `rs_new_high` | relative_strength | bool: RS line above its prior 252-bar max | band `[(1,80),(0,45)]` |
| `rs_divergence` | relative_strength | bool: price at a 252-bar high while RS is not within 3 % of its own | band `[(1,25),(0,60)]` — a present divergence scores low |
| `keltner_pct` | price_structure | `(close − lower)/(upper − lower)`, EMA20 ± 2·ATR14 | band `[(1,25),(0.5,70),(0,50),(−10,35)]`, below −10 → `None` |
| `near_sma200` | price_structure | bool: `abs(distance_to_sma200_pct) ≤ 3.0` (see divergence D6) | band `[(1,80),(0,45)]` |
| `cmf` | volume | Chaikin money flow, 20 bars | ramp −0.20 → 0, +0.20 → 100 |
| `near_breakout` | breakout | bool: `(base_high − close)/base_high ≤ 0.05` on the VCP's 90-bar base | band `[(1,85),(0,45)]` |
| `breakout_persistence` | breakout | `persistence_up − persistence_dn` on a 20-bar Donchian | ramp −1 → 0, +1 → 100 |
| `stoch_rsi` | mean_reversion | `(RSI14 − min)/(max − min)` over the last 14 RSI values | band `[(0.8,25),(0.2,50),(0,80)]` — oversold scores high |
| `obv_bullish_div` | mean_reversion | bool: price lower-low with OBV higher-low across the last 60 bars | band `[(1,75),(0,50)]` |
| `sqrt_rs_minus` | volatility | `√(Σ min(r,0)²/n)` over the series' close-to-close returns | ramp (inverted) 0.008 → 100, 0.030 → 0 |
| `pct_above_50d` / `pct_above_200d` | breadth | % of the S&P 500 panel above its own 50/200-day SMA | ramp 20 → 0, 80 → 100 |
| `ad_ratio` | breadth | `(advancers − decliners)/n` on the latest session | ramp −0.30 → 0, +0.30 → 100 |
| `zweig_thrust` | breadth | `EMA10(adv/(adv+dec))` change over 10 sessions | ramp 0 → 0, 0.20 → 100 |

**Data provenance.** Two sources only.

1. **The name's own daily bars** — `_ohlcv(ticker)` (`analysis_tools.py:229`,
   320 bars) → `stockstats_utils.load_ohlcv` → **`yf.download`**. Every leg is
   then computed locally from those bars by
   `swing.trend_architecture`, `technical_factors.*`, `momentum.momentum_12_1`,
   `relative_strength.*`, `extended_indicators.chaikin_money_flow`,
   `value_dip.support_structure`, `volatility_models.semivariance`,
   `size.atr`. The benchmark for the three RS legs is the same loader on
   `benchmark_ticker or "SPY"` (`default_config.py:1442`).
2. **The breadth panel** — `_market_breadth_read` (`:390`) →
   `dataflows/market_panel.market_closes`, whose universe is the S&P 500 from
   `sp500_universe.fetch_sp500_universe` (**Wikipedia API**, cached 7 days) and
   whose fetcher is `_ohlcv` per constituent (≈500 `yf.download` calls, process-
   cached). Producers: `strategies/market_breadth.market_breadth:179`
   (`pct_above_*`, `ad_ratio`) and `technical_depth.zweig_breadth_thrust:400` fed
   by `market_breadth.advance_decline_line:343`.

No `route_to_vendor` call exists in this family.

**Coverage / withhold.** Category floor 2 legs (`CATEGORY_MIN_COVERAGE`,
`technical_score.py:289`); composite floor 3 of 9 categories (`:290`). Breadth legs
are `None` when the panel has fewer than 20 usable names
(`market_breadth.py:282,300`). Bands (`TECH_BANDS`): ≥80 strong uptrend, ≥65
constructive, ≥50 neutral, ≥35 deteriorating, ≥20 weak, else broken.

**Retirement ledger.** `RETIRED_COMPONENTS` (`:233`) records the 25 of 43 legs the
2026-09-27 panel retired; category weights were **not** renormalised, so a retired
leg's share now sits in its surviving siblings' equal split.

**Divergences.** `near_sma200` compares a **fraction** (`support_structure`
returns `(p − SMA200)/SMA200`, `value_dip.py:897`) against `3.0`, i.e. "within
300 %", so the leg is effectively always true (D6); the docstring of `_ohlcv`
claims the vendor chain while the code calls yfinance (D1); `keltner_pct` is
band-mapped and noted `NON-MONOTONIC` but is missing from
`score_engine.NON_MONOTONIC_INPUTS`, so its raw→aligned triple is never printed
(D7).

### 4.3 MomentumScore — 8 legs, 36 members

Entry: `analysis_tools.py:7116 get_momentum_score`; builder
`analysis_tools.py:6847 _momentum_components`; also `quant_scorecard.py:305`.

**Weights.** `LEG_WEIGHTS` (`momentum_score.py:89`): P 0.25, R 0.15, T 0.20,
A 0.10, B 0.05, V 0.10, Q 0.10, D 0.05. Legs are equal-weighted internally
(`leg_score:631`), each with floor 2 members; composite floor 3 of 8 legs.

| Leg | Members (all ramps unless noted) |
| --- | --- |
| **P** price | `r_5` (−0.12…0.12), `r_21` (0.25), `r_63` (0.35), `r_126` (0.50), `r_252` (0.70), `mom_12_1` (−0.30…0.50) |
| **R** relative strength | `rs_slope_pct` (±0.10 %/day), `rs_new_high` (band 1→80), `rs_divergence` (band 1→25), `rs_vs_sector` (±0.15, 20-day excess vs the SPDR ETF), `rs_percentile` (0-100, cross-sectional) |
| **T** trend | `adx` (15…40), `di_spread` (±30), `ma_distance` (±0.10), `ma_slope` (±0.05), `sma_stack` (band 1→80), `trend_slope` (±0.005 %/bar), `trend_r2` (0…0.90) |
| **A** acceleration | `accel_short_medium` (R63−R21, ±0.20), `accel_medium_long` (R21−R126, ±0.30), `macd_hist_accel` (±0.010) |
| **B** breakout | `donchian_20/50/100/252` (persistence spread, ±1), `breakout_strength` (−0.5…2.0), `dist_from_high` (−0.50…0) |
| **V** volume | `rvol` (0.5…2.0), `volume_trend` (±0.30), `obv_slope_norm` (±0.30), `cmf` (±0.20), `pv_corr` (±0.50) |
| **Q** quality of trend | `efficiency_ratio` (0…0.60), `positive_day_ratio` (0.35…0.65), `autocorr1` (±0.20), `vol_adjusted` (±1.50) |
| **D** downside | `realized_vol` (0.15…0.80, lower better), `downside_dev` (0.05…0.45), `max_drawdown` (0…0.40), `ulcer` (0…0.15), `atr_pct` (0.01…0.06) |

**Data provenance.** All 36 members come from ONE fetch: `_ohlcv(ticker)` →
`load_ohlcv` → **`yf.download`** (`stockstats_utils.py:336`), 320 bars. Two
auxiliary reads: the benchmark closes for the RS legs (`_benchmark_closes`, same
loader on SPY) and the sector ETF for `rs_vs_sector`
(`yfinance_sector.fetch_sector:64` → FMP `profile` → Finnhub `company_profile2` →
`Ticker.info.sector`), then the ETF's bars from the same loader. No router.

**Coverage / withhold.** Leg floor `min(coverage_floor(2, n), n)`; composite floor
3 of 8 legs; bands 90/75/60/40/25/10 (`MOMENTUM_BANDS`).

**Divergences.** `rs_slope_pct`'s note says "×100" but the assembler passes the
producer's %/day unscaled, so the ramp means ±0.10 %/day; `meta.coverage` is a leg
count while the top-level `coverage` is a weight fraction (two numbers, one name);
`reference=` normalisation can double-map `rs_percentile` (D10).

### 4.4 SentimentScore — 10 categories, 18 components

Entry: `analysis_tools.py:8222 get_sentiment_score`; builder
`analysis_tools.py:7981 _sentiment_components(ticker, date, days=120)`.

**Weights.** `CATEGORY_WEIGHTS` (`sentiment_score.py:138`): news_sentiment 15,
momentum 15, breadth 10, institutional 15, analyst 10, retail_social 10,
options 10, short_interest 5, dispersion 5, extreme_crowding 5. Components inside
a category are **equal-weighted** (`category_score:444` calls `combine` without
weights). Category floor 1, composite floor 3 of 10.

| Component | Category | Raw | Mapping | Producer |
| --- | --- | --- | --- | --- |
| `weighted_tone` | news_sentiment | relevance-weighted daily tone | ramp ±0.5 | `sentiment.aggregate_weighted_sentiment:1487` |
| `sma_7d` | news_sentiment | 7-day rolling mean tone | ramp ±0.5 | `sentiment.daily_sentiment_sma:1335` |
| `tone_innovation` | momentum | `score_t − sma_7d_{t−1}` | ramp ±0.5 | same |
| `tone_velocity` | momentum | OLS slope/day over the last 5 scores | ramp ±0.05 | `sentiment.sentiment_velocity:41` |
| `bull_share` | breadth | share of the day's articles with tone > +0.05 | ramp 0.2…0.8 | `aggregate_weighted_sentiment:1487` |
| `neutral_share` | breadth | share with \|tone\| < 0.05 | ramp 0.2…0.8, lower better | same |
| `inst_flow_z` | institutional | z of the latest Δ in institutional % of float | ramp ±2 | `sentiment_research.inst_flow_z:82` |
| `revision_ratio` | analyst | `(up − down)/(up + down)`, 60 d | ramp ±0.5 | `analyst_revisions.revision_ratio:79` |
| `analyst_agreement` | analyst | `1 − (max − min)/2` over the 5-tier map | ramp 0.2…0.8 | `sentiment_research.analyst_agreement:167` |
| `social_score` | retail_social | `(bull − bear)/(bull + bear)` from StockTwits labels | ramp ±0.5 | `sentiment.score_from_counts:824` |
| `social_velocity` | retail_social | z of today vs the last 30 stored scores | ramp ±2 | `sentiment.surprise_velocity:806` |
| `iv_skew` | options | `(put_iv − call_iv)/atm_iv` | ramp 0.8…1.2, lower better | `options_surface.iv_skew:25` |
| `put_call_ratio` | options | `put_oi / call_oi` | ramp 0.7…1.3, lower better | `options_surface.put_call_oi_concentration:34` |
| `short_pct_float` | short_interest | fraction of float | ramp 0.05…0.25, lower better | `yfinance_short_interest.short_interest_fields:37` |
| `dispersion` | dispersion | weighted σ of per-article tone | ramp 0.2…0.8, lower better | `sentiment.sentiment_dispersion:1005` |
| `dispersion_agreement` | dispersion | weighted modal label share | ramp 0.2…0.8 | same |
| `crowd_ratio` | extreme_crowding | `bull/(bull + bear)·100` | ramp 20…80, lower better | `sentiment.crowd_ratio:941` |
| `mention_heat` | extreme_crowding | `recent / mean(prior days)` | ramp 0.5…3.0, lower better | `sentiment.mention_volume:776` |

**Data provenance.** The tone series is resolved by
`_sentiment_points_with_source` (`analysis_tools.py:7930`) in its own inline order
— **EODHD `/sentiments`**, then Alpha Vantage `NEWS_SENTIMENT`, then GDELT (which
always returns `None`). `weighted_tone`, `bull_share`, `neutral_share` and
`dispersion` come from a **second** Alpha Vantage `NEWS_SENTIMENT` fetch
(`_av_news_articles:11704`), 120 days, relevance weight `rel/100`, no decay. So
the weighted and the SMA legs can be built from **different vendors in one run**.

The remaining inputs: `inst_flow_z` ← moomoo
`get_shareholders_institutional`; `revision_ratio` and `analyst_agreement` ←
yfinance `Ticker.upgrades_downgrades`; the four social legs ← StockTwits stream
JSON; `iv_skew`/`put_call_ratio` ← the **third** listed yfinance expiry's chain;
`short_pct_float` ← `Ticker.info`; the quadrant's price axis ← `_ohlcv` abnormal
return. Reddit, Seeking Alpha, Benzinga, EODHD `/news` and moomoo news reach only
the analyst's `get_news` tool, never this engine.

**Coverage / withhold.** Category floor 1, composite floor 3 of 10 categories.
Mixed tone sources are **refused** before scoring (`_resolve_sources:383` →
`refused=True`, score `None`). Bands: ≥80 bullish-positioned … ≥0 capitulating.
`status` is always `ADVISORY`; nothing sizes or gates.

**Divergences.** `_av_news_articles` hardcodes Alpha Vantage, the fifth member of
`news_data`; `revision_ratio` sits behind `enable_analyst_revision_index`
(**False** by default) while `analyst_agreement` is ungated; the options legs
bypass the `options_data` chain.

### 4.5 NewsScore — 11 components, 9 categories

Entry: `analysis_tools.py:8983 get_news_score`; builder
`analysis_tools.py:8659 _news_components(ticker, date, days=30)`.

**Weights.** `COMPONENT_WEIGHTS` (`news_score.py:65`): relevance 10,
materiality 10, novelty 15, fundamental_impact 20, earnings_surprise 10,
guidance_change 5, corporate_events 10, regulatory_legal 5, analyst_revision 5,
industry_shock 5, persistence 5. Unlike SentimentScore, the categories here **do**
use the per-component vector (`_category_score:254`). Composite floor 2 of 11.

| Component | Raw | Mapping | Producer → endpoint |
| --- | --- | --- | --- |
| `relevance` | mean per-article relevance, first 40 articles | ramp 20…80 | `news_relevance.score_news_article:57` over AV `NEWS_SENTIMENT` |
| `materiality` | \|implied move\| fraction | ramp 0.01…0.10 | `catalyst.implied_move_from_history:138` ← moomoo `get_financials_earnings_price_history` (`predict_vola_ratio_newest`) |
| `novelty` | first-seen share in 30 d | ramp 0…1 | `news_score.news_novelty:331` |
| `fundamental_impact` | — | ramp 0…1, **no producer** | declared absent (`ABSENT_REASONS:124`) |
| `earnings_surprise` | `(actual − estimate)/\|estimate\|` | ramp ±0.05 | `events.surprise_score:17` ← moomoo earnings calendar |
| `guidance_change` | signed relative midpoint change | ramp ±0.05 (engine) on a ±0.10 producer | `news_score.guidance_change_score:794` ← Benzinga guidance calendar; gate `enable_benzinga_surface` **False** |
| `corporate_events` | max form score | ramp 0…100; 8-K 75, SC 13D 70, DEF 14A 55, SC 13G 55, S-1 50, 10-K 45, S-3 40, 10-Q 35 | `news_score.corporate_events_score:679` ← `sec_edgar.recent_filing_forms:478` |
| `regulatory_legal` | matched-share × severity | ramp 0…1, lower better | `news_score.tag_category_read:1004` over AV `topics[]` |
| `analyst_revision` | `(up − down)/(up + down)`, 60 d | ramp ±0.5 | `analyst_revisions.revision_ratio:79`; gate off by default |
| `industry_shock` | Σ(stock − sector) over 30 pairs | ramp ±0.10 | `news_score.industry_shock:1104`; sector via `yfinance_sector.fetch_sector` |
| `persistence` | mention ratio `recent/baseline` | ramp 0.5…3.0, lower better | `sentiment.mention_volume:776` over the tone series' `n` column |

**Data provenance.** Article set = Alpha Vantage `NEWS_SENTIMENT`, 30-day window.
Materiality and earnings surprise = the run's single catalyst snapshot, which
reads moomoo `get_earnings_calendar` and `get_financials_earnings_price_history`.
Corporate events = SEC `data.sec.gov/submissions`. Guidance = Benzinga. Analyst
revision = yfinance upgrades/downgrades. Industry shock = `_ohlcv` closes for the
name and its sector ETF. Persistence = the EODHD/AV tone series.

**Coverage / withhold.** Floor 2 of 11 components; five components are declared
absent with a printed reason (`ABSENT_COMPONENTS:92`). Bands: ≥80
high-information … ≥0 no-signal.

**Divergences.** `guidance_change` is ramped twice (producer saturates at ±10 %,
engine at ±5 %); `tag_category_read` is fed AV `topics` with `importance_rank`
`None`, so severity is always 1.0; `news_confidence` and `weighted_novelty` are
never passed by the wired caller.

### 4.6 EventScore — 7 families, imminence only

Entry: `analysis_tools.py:7620 get_event_state`; builder
`analysis_tools.py:7551`; card block `reporting.py:1554`; scorecard row
`quant_scorecard.py:422`. All three read the run's
`strategy_overlays.catalyst` snapshot — produced by
`catalyst.fetch_catalyst_data:491` → `build_catalyst_snapshot:246`.

**Formula.** No weights: `score = mean(present family scores)`, floor 2 of 7.

```
imminence = clamp(1 − days_until / H, 0, 1)
score_family = align(imminence, higher_better, lo=0, hi=1) = 100 × imminence
```

| Family | Horizon `H` | Day-count source | Provider |
| --- | --- | --- | --- |
| `earnings` | 60 | `catalyst.next_earnings:97` | moomoo `get_earnings_calendar` (`catalyst.py:436`), chunked to 6 days over `−35d … +95d` |
| `macro` | 3 | `macro_imminence:150` (HIGH-star events only) | moomoo `get_economic_calendar` (`:525`) |
| `fed` | 10 | `fed_imminence:169` (earliest meeting, `modal_prob` printed) | moomoo `get_fed_watch_target_rate` (`:532`) |
| `opex` | 7 | `derivatives_gamma.opex_status:234` | **none** — pure date arithmetic (third Friday) |
| `product_clinical` | 90 | `event_components:480` over `forward_calendar:377` | pdufa.bio `/api/v1/events` (`event_calendars.py:190`), gate `enable_event_calendars` |
| `court` | 90 | `court_calendar_rows:210` returns `None` by design | — |
| `investor_day` | 60 | `company_event_calendars:245` hardcodes `None` | — |

Flags (`earnings_in_window`, `macro_count_high`, `catalyst_unassessed`,
`fed_modal_prob`, `opex_in_week`, `opex_post_unwind`) are printed and **never
scored**.

**Hard block.** Set iff `0 ≤ days_until ≤ catalyst_hard_block_days` (default 5) on
the nearest print, and it forces `REJECT` downstream
(`graph/trading_graph.py:1378`). The engine copies it through; it never sets it.

**Coverage / withhold.** Floor 2 of 7 families; only earnings + macro + fed +
opex can measure out of the box (OPEX always can), so a vendor outage leaves the
composite withheld at 1 of 7. Bands: ≥80 event-window … ≥0 clear.

**Divergences.** Horizon 60 vs a 95-day fetch means a print 61–95 days out
measures as 0.0 rather than absent; the company-calendar families have no horizon
filter for the same reason; `macro_count_high=0` can mean "none in 3 days" while
events at 4–14 days were discarded.

### 4.7 RegimeScore — market environment, equal weights

Entry: `analysis_tools.py:7895 get_regime_score`; builder
`analysis_tools.py:7695 _regime_components`.

**Weights.** None published: `combine(aligned, weights=None, min_coverage=3)`
(`regime_score.py:285`). The owner's 8-category table (20/20/15/15/10/10/5/5) is
printed in `basis` and **not used**; only 4 of its 8 categories have a producer.

| Component | Raw | Mapping | Producer → provider |
| --- | --- | --- | --- |
| `market_trend` | benchmark `P/SMA − 1` | ramp ±0.10 | `regime_score.market_trend:351`; SPY closes via `yf.download` |
| `breadth` | % of the S&P 500 above its 50-day SMA | ramp 20…80 | `market_breadth.market_breadth:179`; Wikipedia universe + `yf.download` per name |
| `vix_percentile` | 0-1 rank of VIXCLS | ramp 0.10…0.90, lower better | `_vix_percentile_read:11407` → FRED `series/observations?series_id=VIXCLS` |
| `vix_term_structure` | `VIX9D / VIX3M` | ramp 0.85…1.15, lower better | `cboe.vix_term_structure:282` → Cboe `VIX9D_History.csv`, `VIX3M_History.csv` |
| `choppiness` | canonical CHOP 0-100 | ramp 20…65, lower better | `regime.choppiness:141` over benchmark OHLC |
| `realized_vol_percentile` | 0-1 rank of realised vol | ramp 0.10…0.90, lower better | `regime.vol_percentile_read:81` over every 21-bar window of the benchmark |
| `spectral_change` (gated) | 0/1 flag | ramp 1→0 | `regime.spectral_change_read:1494`; gate `enable_spectral_null_band` False |

**Two paths.** `two_paths` is a diagnostic, never a merge: Path A is the
`overlays.build_strategy_overlays` vocabulary (`high_vol | bull | bear | neutral`),
Path B is the four-axis `regime_state` vocabulary (`trend`, `volatility`,
`relative`, `drawdown` + `crash`). `disagree` is a declared contradiction rule
(`regime_score.py:717-763`); both paths are run over the **benchmark**, and Path B
gets `benchmark=None`, so its `relative` axis is unmeasured.

**Coverage / withhold.** Floor 3 of 6; bands 80/60/40/20. Benchmarked series are
truncated to 320 bars with a 10-day staleness rejection; the FRED leg needs ≥20
observations; the Cboe leg has only a 24-hour cache TTL and no date-vs-today check.

**Divergences.** VIX percentile is taken as of `datetime.now()`
(`analysis_tools.py:7768`), not the run's trade date, so a backdated run cannot
reproduce it; `benchmark_ticker=None` means every non-US run still trends SPY.

### 4.8 RiskScore — 34 declared components, 8 categories, inverted

Entry: `analysis_tools.py:7403 get_risk_score`; builder
`analysis_tools.py:7197 _risk_components`.

**Weights.** `CATEGORY_WEIGHTS` (`risk_score.py:58`): volatility 15, tail 15,
liquidity 10, gap 10, correlation 15, concentration 10, drawdown 15, event 10 —
used verbatim. Within a category the scored components are equal-weighted. Score
100 = **low** risk; bands 80/65/50/35/20.

**Measured today** (verified against the live cards): `realized_vol`,
`sqrt_rs_minus`, `implied_move_pct`, `amihud_illiquidity`, `spread_pct`,
`gap_atr`, `portfolio_cvar`, `stress_loss`, `book_correlated_stress`, `cdar`,
`measured_book_drawdown`. Everything else declared is unsupplied by
`_risk_components` — 19 of the 34 keys never appear in that function's body.

| Category | Component | Raw → mapping | Producer |
| --- | --- | --- | --- |
| volatility | `realized_vol` | annualised σ, 21 closes → 0.10…0.60 lower-better | `regime.realized_vol:39` |
| volatility | `sqrt_rs_minus` | `√(Σ min(r,0)²/n)` → 0.008…0.030 | `volatility_models.semivariance:52`, identity `RS⁻+RS⁺=RV` re-checked |
| volatility | `implied_move_pct` | ATM 1σ move → 0.01…0.10 | `options_surface.implied_move_pct:42` over the yfinance chain |
| tail | `portfolio_cvar` | book loss fraction (negated) → 0…0.10 | `book_risk.portfolio_cvar:61` |
| tail | `stress_loss` | uniform −10 % book loss → 0…0.10 | `book_risk.stress_loss:143` |
| liquidity | `amihud_illiquidity` | `mean(\|r\|/dollar volume)` → 1e-9…1e-6 | `liquidity_risk.amihud_illiquidity:71` |
| liquidity | `spread_pct` | Corwin–Schultz + Abdi–Ranaldo → 0.0005…0.02 | `liquidity_risk.spread_estimate:574` |
| gap | `gap_atr` | \|gap\| in ATR units → 0…3 | `pre_market.premarket_gap:40` |
| correlation | `book_correlated_stress` | worst-decile mixed return → 0…0.10 | `book_risk.book_correlated_stress:148` |
| drawdown | `measured_book_drawdown` | max drawdown, configured basket → single name → `None` | `book_context.measured_book_drawdown:102` |
| drawdown | `cdar` | conditional drawdown at risk on the mixed curve → 0…0.25 | `book_risk.cdar:219` |

**Data provenance.** One bar source for every single-name leg (`_ohlcv` →
`yf.download`, ≥30 closes required, else the dict is empty). The book legs read
the **configured basket** (`configured_basket` over `risk_basket_tickers` /
`risk_basket_weights`) and fetch each name through the same loader. The implied
move reads a yfinance option chain. Nothing in this engine touches FRED, Cboe,
credit spreads or an index series.

**Coverage / withhold.** Category floor 2 scored components, composite floor 3 of
8 categories; `uncertainty = 1 − coverage` and `coverage` is a category-weight
fraction (so absences *inside* a category that still clears its floor do not raise
it). Live cards publish volatility + tail + liquidity + drawdown and withhold gap,
correlation, concentration and event — coverage 0.45-0.55.

**Divergences.** The `event` category can never fire (`catalyst_scale`,
`event_hard_block`, `opex_window` are unsupplied); `portfolio_hhi` is declared as
an HHI over position weights but cites a **holder** HHI producer that returns
0-10000; `days_to_absorb`'s note says a 15 % participation cap while the producer
uses 10 %; `es_pct` and `cluster_exposure_share` name producers in the sibling
execution repo.

### 4.9 TradeScore and the quant scorecard

`quant_scorecard` is a container: it calls each enabled engine with the run's
inputs and records `MEASURED | NA | DISABLED` per engine
(`quant_scorecard.py:80-90, 501`). `trade_score` reads four of those scores and
combines them with the owner's vector.

```
trade = combine({F, T, R, K}, weights=ENGINE_WEIGHTS, min_coverage=2)
ENGINE_WEIGHTS = {fundamental: 0.40, technical: 0.25, regime: 0.15, risk: 0.20}
```

- **K is inverted before use**: RiskScore publishes 100 = low risk, so a high K
  helps the composite.
- `weights_source` is `"owner"` unless a caller supplies a vector; the status
  ladder prints `RESEARCH_ONLY` until an evidence record exists
  (`trade_score.py:210`).
- No band table (`TRADE_BANDS = ()`), so `band` is always `None`.
- `news`, `sentiment`, `momentum` and `event` are **not** in the composite: a key
  that is not one of the four engines is excluded, never weighted
  (`_normalise:249`, `_ALIASES:79` — the reason recorded is "not a TradeScore
  engine (master rule 17)").
- `scorecard_status` = `COMPLETE` only when every engine is measured; any
  gate-off or NA engine makes it `PARTIAL`.
- `movement` is structurally `UNAVAILABLE`: only `trading_graph.py:798` injects
  it and `score_history.score_movement` withholds while the vector is unvalidated.

### 4.10 Scores that are computed but not scored

| Score | Entry | Formula | Inputs → provider |
| --- | --- | --- | --- |
| `piotroski_f_score` | `dataflows/quantitative_scores.py:202` | 9 binary signals summed 0-9: ROA>0, CFO>0, CFO−NI>0, ΔROA>0, Δleverage<0, Δcurrent ratio>0, no share issuance, Δgross margin>0, Δasset turnover>0. A missing input scores **0** | annual statements via `fetch_ticker` |
| `piotroski_f_score_detailed` | `:590` | Paper basis: ROA on **beginning** TA, accrual in ratio form, LTD/avg TA; band only when all nine signals exist | same |
| `growth_score` (G) | `:851` | 8 signals vs **peer medians** (ROA, CFO/begin-TA, CFO>NI, Var(ROA), Var(sales growth), R&D/revenue, capex/revenue, advertising/revenue), 0-8 | same, plus `resolve_growth_medians` |
| `overpriced_score` (Montier C) | `:943` | 6 flags: NI−CFO divergence, receivable days up, inventory days up, other current assets up, D&A/net PP&E down, total assets +10 %, 0-6 | same |
| quality composite | `strategies/factors.py:258`, gated `enable_quality_composite` (False) | Same z → percentile machinery as FundamentalScore over 7 metrics (`f`, `m`, `z`, `o`, `gp_a`, `noa`, `accruals`), floor 3, `min_peers=8` | same peer panel |
| `score_eval_rows` | `strategies/alpha_health.py:627`, gated `enable_score_eval_rows` | IC (Spearman/Pearson), deciles, coverage, stability, turnover over stored score snapshots | `<data_dir>/alpha_ledger.jsonl`, written by `reporting.write_alpha_ledger:902` behind `alpha_ledger_enable` |

Two facts about the live configuration: `enable_score_eval_rows` is on while its
only data producer `alpha_ledger_enable` is off, so the block can only report
`available=False`; and the G/C and quality columns in the screener are driven by
CLI flags (`--growth-scores`, `--quality-score`), not by the config gates.

---

## 5. Worked arithmetic

A leg's contribution, and a composite, using the kernel's own semantics. Every
number below is the output of `score_engine.align` / `combine` as they run today:

```
# one leg (technical, ramped)
aroon_osc  raw = 0.0
align(0.0, higher_better, lo=-60, hi=60)
  frac = (0 - -60) / (60 - -60) = 60/120 = 0.5  ->  50.0

# one leg (banded, non-monotone)
stoch_rsi  raw = 0.12
band [(0.8,25),(0.2,50),(0,80)] walked top-down: 0.12 >= 0.8? no; >= 0.2? no; >= 0.0? yes -> 80.0

# one category (equal weights inside, floor 2 legs)
trend = combine({sma_stack: 80.0, aroon_osc: 50.0}, weights=None, min_coverage=2)
  present = 2 of 2, weight 2 of 2  ->  score = (80 + 50)/2 = 65.0, coverage = 1.0, floor = 2

# the composite (categories weighted; an absent category leaves the denominator)
technical = combine(
  {trend: 65.0, momentum: 100.0, relative_strength: None, price_structure: 75.0,
   volume: 60.0, breakout: None, mean_reversion: None, volatility: 90.0, breadth: None},
  weights=CATEGORY_WEIGHTS, min_coverage=3, bands=TECH_BANDS)
  present  = trend, momentum, price_structure, volume, volatility
  weight   = 20+18+12+10+5 = 65 of 100   ->  coverage = 0.65
  score    = (20·65 + 18·100 + 12·75 + 10·60 + 5·90) / 65 = 5050/65 = 77.69
  floor    = coverage_floor(3, 9) = 3; present 5 >= 3  ->  published
  band     = band_label(77.69, TECH_BANDS) = "constructive"   (>= 65, < 80)
```

An absent leg is **not** a zero. Had those four categories entered as 0, the same
inputs give `5050/100 = 50.5`, i.e. "neutral" where the engine actually publishes
"constructive" — one half-point above the neutral floor, which is exactly why the
denominator is renormalised rather than filled.

---

## 6. Where each number is published

| Number | Tool (LLM leaf) | `run_card.json` key | Report surface |
| --- | --- | --- | --- |
| FundamentalScore | `get_fundamental_score` | `fundamental_score` | analyst block, `complete_report.md` |
| TechnicalScore | `get_technical_score` | `technical_score` | analyst block |
| MomentumScore | `get_momentum_score` | `quant_scorecard.engine_detail` | scorecard block |
| SentimentScore | `get_sentiment_score` | `sentiment_score` | analyst block |
| NewsScore | `get_news_score` | `news_score` | analyst block |
| EventScore | `get_event_state` | `event_state` | scorecard block |
| RegimeScore | `get_regime_score` | `regime_score` | scorecard block |
| RiskScore | `get_risk_score` | `risk_score` | scorecard block |
| TradeScore | `get_trade_score` | `trade_score` | scorecard block |
| Quant scorecard | — | `quant_scorecard` | `format_quant_scorecard` |

Every one of these blocks carries `status`, `score`, `coverage`, `withheld` (when
withheld) and `basis` — the weight vector actually used plus the components that
were present — so a reader can recompute the number from the card alone.

---

## 7. Known divergences (flagged, not fixed)

Grouped, because several share one cause. Each is a real gap between what the
documentation or a reader would assume and what the code does.

**D1 — the price path bypasses the vendor chain.** `_ohlcv`'s docstring says "via
the vendor chain" (`analysis_tools.py:230`) but it calls `load_ohlcv` →
`yf.download` (`stockstats_utils.py:336`). Every bar-based leg (technical,
momentum, risk, regime, breadth, the sentiment price axis, all book legs) is
Yahoo-only; `core_stock_apis` (EODHD first) is never consulted.

**D2 — several engines hardcode one vendor regardless of the configured chain.**
Sentiment/News hardcode Alpha Vantage `NEWS_SENTIMENT`; the sentiment tone chain
is re-implemented inline instead of routed; the options legs read yfinance
directly; the EventScore calendars call the moomoo SDK directly with no
finnhub/yfinance fallback.

**D3 — two producers for one key.** `fcf_yield` (`capex_quality.py:247` vs
`ratios.py:724`), `earnings_yield` (EBIT/EV vs NI/MC), and the tone series
(EODHD-first for the SMA legs, AV-only for the weighted legs).

**D4 — declared-but-unsupplied components.** 19 of RiskScore's 34 keys and the
`event` category are never supplied by `_risk_components`; NewsScore's
`fundamental_impact` has no producer at all.

**D5 — floors can make a declared engine unpublishable.** With the shipped empty
basket, RiskScore's book categories are unmeasurable, leaving 2 of 8 categories
against a floor of 3, so the composite withholds even with the gate on.

**D6 — `near_sma200` compares a fraction to 3.0.** `support_structure` returns
`(p − SMA200)/SMA200`, and the caller tests `<= 3.0` (300 %), so the leg is
effectively always true when measurable (`analysis_tools.py:6573`).

**D7 — banded legs missing from `NON_MONOTONIC_INPUTS`.** `keltner_pct` is
band-mapped and annotated NON-MONOTONIC, but only `stoch_rsi` is declared, so the
evidence triple is never printed for it.

**D8 — two different numbers share one name.** `momentum_score` returns a
weight-fraction `coverage` and a leg-count `meta.coverage`; `fundamental_score`
reports `panel_n` for both the resolved panel and the DCF-supplied count.

**D9 — the EventScore horizon is narrower than its fetch.** `HORIZONS["earnings"]
= 60` over a 95-day fetch, and the company calendars have no horizon filter at
all: an event past the horizon scores 0.0 and counts as *present*, inflating
coverage.

**D10 — double mapping.** `rs_percentile` (0-100) is fed back through its own
ramp when `reference=` normalisation runs.

**D11 — stale line citations inside the ledgers.** `COMPONENTS` tables in
`technical_score`, `sentiment_score`, `risk_score`, `event_state` and
`momentum_score` cite producer line numbers that have drifted (e.g.
`risk_score.py` cites `portfolio_cvar:28`, actual `:61`). The citations are
documentation, not code, but they send a reader to the wrong line.

**D12 — the card and the prompt can disagree if the snapshot is missing.** All
card blocks read the run's snapshot first and fall back to recomputation only for
a legacy state; a recompute is a second producer (`resolve_peer_universe` has no
cache, so two identical calls differed by 113 metrics on the 2026-09-20
measurement recorded in `reporting.py:1155-1170`).

---

## 8. Changing a component

1. Declare it in the engine's `COMPONENTS`/`COMPONENT_WEIGHTS` with its direction,
   exact mapping and producer citation.
2. Supply it in the corresponding `_*_components` builder in
   `agents/utils/analysis_tools.py` — a missing key is an absent component, a
   fabricated 0 is a defect.
3. If the value is non-monotone, add it to `score_engine.NON_MONOTONIC_INPUTS`,
   or its evidence triple is unreachable.
4. Measure the new prompt text against the bullet limits in
   `tests/test_prompt_budget_contract.py` (`LONGEST_BULLET_LIMIT` is the binding
   one).
5. Land the engine change, the run-card block, the report render and this
   document in one commit.
