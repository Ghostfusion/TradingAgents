# Score formulas and data sources

Every score in this repository is an advisory 0-100 number. This document gives,
for each one: the exact arithmetic, the weight vector, the threshold tables, and
the provider endpoint that supplies each input, so the calculation can be
reproduced or reimplemented elsewhere without reading the code.

Nine scores are composites built from weighted components. Beside them sit the
screening scores, computed per name and never aggregated (Piotroski F and its
paper-basis variant, the G-score, the Montier C-score), a peer-relative quality
composite, and one evaluation report over stored score snapshots. Every engine
follows the same combination rule (§1), reads its price history from the same
source (§3), and prints its bands rather than gating on them.

---

## 1. The combination rule

All composite engines share one kernel with three primitives.

### 1.1 Mapping a raw value to 0-100

**Ramp** — both edges required:

```
score = clamp((v - lo) / (hi - lo), 0, 1) * 100
lower_better:  frac = 1 - frac
```

**Band table** — for inputs whose relationship is not monotone (RSI-type
oscillators, %b, any "too much is bad" measure). A table of `(edge, score)` pairs
is walked **top-down**; the first `edge <= value` wins:

```
band = [(0.8, 25), (0.2, 50), (0.0, 80)]     # StochRSI: oversold scores HIGH
value 0.12 -> 0.12 >= 0.8? no; >= 0.2? no; >= 0.0? yes -> 80
value below the lowest edge -> absent (None), never 0
```

### 1.2 Combining components

```
score    = Σ wᵢ·vᵢ / Σ wᵢ        over the components that were MEASURED
coverage = Σ wᵢ(measured) / Σ wᵢ(all declared)     (a fraction)
floor    = minimum number of measured components required (a count)
```

- An unmeasured component is **absent**: it leaves the denominator. It is never
  entered as 0 and never as a neutral 50.
- Below the floor the composite is **withheld** — no number at all.
- With no weights supplied, the declared components are equally weighted.
- The floor always resolves against the **declared** set, so adding a component
  can never lower the bar.

### 1.3 Bands

Bands label a score; they never gate a decision. Each engine owns its table and
the first floor the score clears wins (walked top-down).

| Engine | Weight vector | Floor | Bands (floor → label) |
| --- | --- | --- | --- |
| FundamentalScore | equal ¼ over 4 sub-scores | 2 of 4 | sub-scores only |
| TechnicalScore | categories 20/18/12/12/10/10/8/5/5 | 3 of 9 categories | 80 strong uptrend · 65 constructive · 50 neutral · 35 deteriorating · 20 weak · 0 broken |
| MomentumScore | legs P .25 / R .15 / T .20 / A .10 / B .05 / V .10 / Q .10 / D .05 | 3 of 8 legs | 90 extremely strong · 75 strong · 60 moderately strong · 40 neutral · 25 weak · 10 very weak · 0 extremely weak |
| SentimentScore | categories 15/15/10/15/10/10/10/5/5/5 | 3 of 10 categories | 80 bullish-positioned · 65 constructive · 50 neutral · 35 cautious · 20 bearish-positioned · 0 capitulating |
| NewsScore | 11 components 10/10/15/20/10/5/10/5/5/5/5 | 2 of 11 | 80 high-information · 65 informative · 50 mixed · 35 quiet · 20 stale · 0 no-signal |
| EventScore | equal over 7 families | 2 of 7 | 80 event-window · 60 imminent · 40 approaching · 20 quiet · 0 clear |
| RegimeScore | equal over its declared set | 3 of 6 | 80 benign · 60 constructive · 40 mixed · 20 stressed · 0 hostile |
| RiskScore (**inverted**: 100 = low risk) | categories 15/15/10/10/15/10/15/10 | 3 of 8 categories | 80 low risk · 65 contained · 50 moderate · 35 elevated · 20 high · 0 severe |
| TradeScore | F .40 / T .25 / R .15 / K .20 | 2 of 4 | none |

Inside a category or leg that is not given its own vector, the members are
equally weighted. Categories with their own weight split it evenly across their
members.

---

## 2. Providers at a glance

| Provider | What it supplies to scores | Access |
| --- | --- | --- |
| **Yahoo Finance** | Every daily price bar behind a technical, momentum, risk, regime, breadth or sentiment-price input | `yf.download(symbol, start, end, auto_adjust=True)`; also `Ticker.info`, `Ticker.balance_sheet/income_stmt/cashflow`, `Ticker.upgrades_downgrades`, `Ticker.options` + `option_chain` |
| **moomoo (OpenD gateway)** | Financial statements, earnings/economic/Fed calendars, implied move, institutional flow | Local SDK, `OpenQuoteContext.<method>(...)` (no HTTP endpoint) |
| **EODHD** | Daily news-sentiment series; exchange symbol lists | `https://eodhd.com/api/sentiments`, `https://eodhd.com/api/exchange-symbol-list/{market}` |
| **Alpha Vantage** | Article set + per-ticker tone for the sentiment and news engines; statement fallbacks | `https://www.alphavantage.co/query?function=NEWS_SENTIMENT|OVERVIEW|BALANCE_SHEET|INCOME_STATEMENT|CASH_FLOW` |
| **Tiingo** | Statement fallback | `https://api.tiingo.com/tiingo/fundamentals/{symbol}/statements?statementType=...` |
| **Finnhub** | Peer set, basic financial gap-fill, profile/sector fallback, earnings-calendar fallback | `company_peers`, `company_basic_financials`, `company_profile2` (SDK) |
| **FMP** | Company profile → sector label (first choice) | `profile` endpoint |
| **FRED** | VIX level series (percentile leg) | `https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS` |
| **Cboe** | VIX9D / VIX3M index history (term-structure leg) | `https://cdn.cboe.com/api/global/us_indices/daily_prices/{VIX9D,VIX3M}_History.csv` |
| **SEC EDGAR** | Filing forms for the corporate-events component | `https://data.sec.gov/submissions/CIK{cik:010d}.json` |
| **Benzinga** | Guidance revisions | `https://api.benzinga.com/api/v2.1/calendar/guidance` |
| **StockTwits** | Retail message stream (bull/bear labels) | `https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json` |
| **pdufa.bio** | FDA / clinical catalyst calendar | `https://www.pdufa.bio/api/v1/events?ticker={TICKER}&limit=200` |
| **Wikipedia API** | The S&P 500 constituent list that defines the breadth panel | `https://en.wikipedia.org/w/api.php?action=parse&page=List of S&P 500 companies&prop=wikitext&format=json` |
| **GDELT** | News-sentiment fallback (declines: its article feed carries no tone) | DOC API |

Two routing notes that matter when reproducing the numbers:

- Statement reads (fundamentals and the F/G/C screens) go through an ordered
  fallback chain: **moomoo → yfinance → tiingo → Alpha Vantage**, with Finnhub
  filling only fields the routed fetch left missing.
- Price history does **not** go through that chain. Every bar-derived input in
  every score is Yahoo Finance, regardless of any vendor preference configured
  elsewhere.

---

## 3. Price, breadth and benchmark inputs

| Input | Source | Notes |
| --- | --- | --- |
| Daily OHLCV for a name | `yf.download`, `auto_adjust=True` | 5-year CSV cache, tail-refreshed, truncated to the newest **320 sessions** for scoring |
| Benchmark series | the same call on SPY | used by the relative-strength legs and the regime trend leg |
| Breadth panel | S&P 500 list from the Wikipedia API, then one 320-session download per constituent | ≥20 usable names required, else every breadth percentage is absent |
| Book legs (RiskScore) | the configured basket; each name's bars from the same Yahoo call | the basket is a configuration input, not a data source |

---

## 4. Engine formulas

### 4.1 FundamentalScore — cross-sectional, not a ramp

The only engine that scores a name **relative to its peer group** rather than
against fixed edges.

```
per factor:  winsorise at 1st/99th percentile
             -> cross-sectional z-score across the peer panel
             -> multiply by the factor's direction (+1 good, -1 bad)
             -> equal-weight mean over the factors the name carries
             -> tie-aware percentile rank across the scored peers -> 0..100

composite:   equal ¼ over the four sub-scores, floor 2 of 4
```

Peer panel = the name plus up to 8 peers from Finnhub `company_peers`; a
sub-score needs `n ≥ 8` names or it is withheld. A factor needs at least
`max(2, floor)` names present or it is dropped before the z-score. There are no
per-factor weights anywhere: each is `1/n` over the factors a name carries.

| Sub-score | Floor | Factors (direction) | Formula |
| --- | --- | --- | --- |
| **Quality** | 3 of 7 | ROE (+), ROA (+), gross profitability (+), Piotroski F (+), Beneish M (−), net operating assets (−), accruals (−) | `NI/TE`, `NI/TA`, `(rev−cogs)/TA`, 9 binary signals 0-9, `M = const + Σw·index` over 8 indices, `(opAssets−opLiab)/TA_prior`, `(NI−CFO)/TA` |
| **Growth** | 2 of 2 | revenue YoY (+), EPS YoY (+) | `(cur−prior)/prior` from the statement pair; vendor TTM YoY only when no pair exists |
| **Valuation** | 3 of 11 | EV/EBITDA, EV/EBIT, EV/Sales, P/E, P/B, P/S, P/CF, P/FCF (all −), earnings yield (+), FCF yield (+), DCF upside (+) | `EV = MC + debt − cash`; `EBITDA = op income + D&A`; `FCF = OCF − |capex|`; earnings yield = **EBIT/EV**; DCF upside = `(FV − price)/FV × confidence`, DCF at rf 4 %, ERP 5 %, g 2.5 %, 5 years, or a cycle-normalised FCF perpetuity |
| **Financial risk** | 3 of 6 | Altman Z (+), Ohlson O (−), Zmijewski X (−), debt/equity (−), current ratio (+), quick ratio (+) | `Z = 1.2x₁+1.4x₂+3.3x₃+0.6x₄+1.0x₅`; `X = −4.336 −4.513·ROA +5.679·TL/TA −0.004·CA/CL`; `D/E` nulled above 10 |

**Data sources.** One statement fetch per name makes four reads —
fundamentals, cash flow, balance sheet, income statement — against
**moomoo `get_financials_statements(code, statement_type=1|2|3,
financial_type=7, num=8)`** first, then `yf.Ticker(...).balance_sheet /
income_stmt / cashflow`, then Tiingo `/fundamentals/{sym}/statements`, then
Alpha Vantage `BALANCE_SHEET|INCOME_STATEMENT|CASH_FLOW`. Annual periods only:
moomoo fiscal-year tables trimmed to 4, Alpha Vantage annual reports preferred;
no TTM path exists, so every flow is the as-reported annual figure. Finnhub
`company_basic_financials(symbol,"all")` fills `eps_yoy`, `revenue_yoy`, `roe`,
`market_cap`, `beta` when the routed fetch left them empty.

### 4.2 TechnicalScore — 9 categories, 18 legs

Category weights: trend 20, momentum 18, relative strength 12, price structure
12, volume 10, breakout 10, mean reversion 8, volatility 5, breadth 5. A
category needs 2 measured legs; the composite needs 3 of 9 categories.

| Leg | Category | Raw input | Mapping |
| --- | --- | --- | --- |
| `sma_stack` | trend | EMA20 > SMA50 > SMA200, SMA50 rising over 5 bars, SMA200 rising over 15 | band 1→80, 0→30 |
| `aroon_osc` | trend | Aroon up − Aroon down, each `(25 − bars since extreme)/25·100` | ramp −60→0, +60→100 |
| `momentum_12_1` | momentum | `P(t−21)/P(t−273) − 1` | ramp −0.20→0, +0.40→100 |
| `rs_slope_pct` | relative strength | OLS slope of the stock/benchmark ratio over 63 bars, normalised, %/day | ramp −0.10→0, +0.10→100 |
| `rs_new_high` | relative strength | RS line above its prior 252-bar maximum | band 1→80, 0→45 |
| `rs_divergence` | relative strength | price at a 252-bar high while RS is not within 3 % of its own | band 1→25, 0→60 (a present divergence scores low) |
| `keltner_pct` | price structure | `%b = (close − lower)/(upper − lower)`, EMA20 ± 2·ATR14 | band 1→25, 0.5→70, 0→50, −10→35; below −10 absent |
| `near_sma200` | price structure | close within 3 % of the 200-day SMA | band 1→80, 0→45 |
| `cmf` | volume | Chaikin money flow, 20 bars: `Σ(CLV·V)/ΣV`, `CLV = ((C−L)−(H−C))/(H−L)` | ramp −0.20→0, +0.20→100 |
| `near_breakout` | breakout | `(base_high − close)/base_high ≤ 5 %` on a 90-bar base | band 1→85, 0→45 |
| `breakout_persistence` | breakout | share of the last 20 closes above the prior 20-bar high minus the mirror below the low, 20-bar Donchian | ramp −1→0, +1→100 |
| `stoch_rsi` | mean reversion | `(RSI14 − min)/(max − min)` over the last 14 RSI values | band 0.8→25, 0.2→50, 0→80 (oversold scores high) |
| `obv_bullish_div` | mean reversion | price lower-low with OBV higher-low across the last 60 bars | band 1→75, 0→50 |
| `sqrt_rs_minus` | volatility | `√(Σ min(r,0)²/n)` over the series' daily returns | ramp (inverted) 0.008→100, 0.030→0 |
| `pct_above_50d`, `pct_above_200d` | breadth | % of the S&P 500 panel above its own 50/200-day SMA | ramp 20→0, 80→100 |
| `ad_ratio` | breadth | `(advancers − decliners)/n`, latest session | ramp −0.30→0, +0.30→100 |
| `zweig_thrust` | breadth | 10-day EMA of the daily advance share, change over 10 sessions | ramp 0→0, 0.20→100 |

**Data sources.** The name's own Yahoo daily bars for 14 of the 18 legs —
Aroon, ATR, Keltner, Chaikin, VCP, StochRSI, OBV, semivariance are all computed
locally from OHLCV — plus the SPY series for the three relative-strength legs.
The four breadth legs read the S&P 500 panel described in §3.

### 4.3 MomentumScore — 8 legs, 41 members

Leg weights: P (price) .25, R (relative strength) .15, T (trend) .20,
A (acceleration) .10, B (breakout) .05, V (volume) .10, Q (trend quality) .10,
D (downside) .05. Each leg needs 2 members; the composite needs 3 of 8 legs.

| Leg | Members and ramps |
| --- | --- |
| **P** | `r_5` ±0.12, `r_21` ±0.25, `r_63` ±0.35, `r_126` ±0.50, `r_252` ±0.70, `mom_12_1` −0.30…+0.50 |
| **R** | `rs_slope_pct` ±0.10 %/day, `rs_new_high` band 1→80, `rs_divergence` band 1→25, `rs_vs_sector` ±0.15 (20-day excess vs the sector ETF), `rs_percentile` 0-100 |
| **T** | `adx` 15…40, `di_spread` ±30, `ma_distance` ±0.10, `ma_slope` ±0.05, `sma_stack` band 1→80, `trend_slope` ±0.005 %/bar, `trend_r2` 0…0.90 |
| **A** | `accel_short_medium` (R63−R21) ±0.20, `accel_medium_long` (R21−R126) ±0.30, `macd_hist_accel` ±0.010 |
| **B** | `donchian_20/50/100/252` persistence spread ±1, `breakout_strength` −0.5…2.0, `dist_from_high` −0.50…0 |
| **V** | `rvol` 0.5…2.0, `volume_trend` ±0.30, `obv_slope_norm` ±0.30, `cmf` ±0.20, `pv_corr` ±0.50 |
| **Q** | `efficiency_ratio` 0…0.60, `positive_day_ratio` 0.35…0.65, `autocorr1` ±0.20, `vol_adjusted` ±1.50 |
| **D** | `realized_vol` 0.15…0.80 (lower better), `downside_dev` 0.05…0.45, `max_drawdown` 0…0.40, `ulcer` 0…0.15, `atr_pct` 0.01…0.06 |

**Data sources.** All 41 members are computed locally from the name's Yahoo
daily bars (320 sessions); the three relative-strength legs also read SPY, and
`rs_vs_sector` reads the sector ETF's bars after resolving the sector from FMP
`profile`, then Finnhub `company_profile2`, then `Ticker.info.sector`.

### 4.4 SentimentScore — 10 categories, 18 components

Category weights: news sentiment 15, momentum 15, breadth 10, institutional 15,
analyst 10, retail/social 10, options 10, short interest 5, dispersion 5,
extreme crowding 5. A category needs 1 component; the composite 3 of 10.

| Component | Category | Raw | Mapping | Source |
| --- | --- | --- | --- | --- |
| `weighted_tone` | news sentiment | relevance-weighted daily tone | ramp ±0.5 | Alpha Vantage `NEWS_SENTIMENT`, 120 days, weight = relevance/100 |
| `sma_7d` | news sentiment | 7-day rolling mean tone | ramp ±0.5 | the daily tone series (EODHD first) |
| `tone_innovation` | momentum | `tone_t − sma_7d_{t−1}` | ramp ±0.5 | same series |
| `tone_velocity` | momentum | OLS slope/day over the last 5 tones | ramp ±0.05 | same series |
| `bull_share` | breadth | share of the day's articles with tone > +0.05 | ramp 0.2…0.8 | Alpha Vantage articles |
| `neutral_share` | breadth | share with \|tone\| < 0.05 | ramp 0.2…0.8, lower better | Alpha Vantage articles |
| `inst_flow_z` | institutional | z-score of the latest Δ in institutional % of float | ramp ±2 | moomoo `get_shareholders_institutional` |
| `revision_ratio` | analyst | `(up − down)/(up + down)`, 60 days | ramp ±0.5 | Yahoo `upgrades_downgrades` |
| `analyst_agreement` | analyst | `1 − (max − min)/2` over the 5 rating tiers | ramp 0.2…0.8 | same feed |
| `social_score` | retail/social | `(bull − bear)/(bull + bear)` | ramp ±0.5 | StockTwits stream |
| `social_velocity` | retail/social | z of today vs the last 30 stored scores | ramp ±2 | StockTwits stream |
| `iv_skew` | options | `(put_iv − call_iv)/atm_iv` | ramp 0.8…1.2, lower better | Yahoo option chain |
| `put_call_ratio` | options | `put_oi / call_oi` | ramp 0.7…1.3, lower better | same chain |
| `short_pct_float` | short interest | fraction of float | ramp 0.05…0.25, lower better | Yahoo `shortPercentOfFloat` |
| `dispersion` | dispersion | weighted σ of per-article tone | ramp 0.2…0.8, lower better | Alpha Vantage articles |
| `dispersion_agreement` | dispersion | weighted modal label share | ramp 0.2…0.8 | same |
| `crowd_ratio` | extreme crowding | `bull/(bull + bear)·100` | ramp 20…80, lower better | StockTwits |
| `mention_heat` | extreme crowding | recent mentions / mean of prior days | ramp 0.5…3.0, lower better | tone series' article counts |

**Data sources.** Two independent reads of Alpha Vantage `NEWS_SENTIMENT`: one
for the weighted/breadth/dispersion legs (relevance-weighted, no decay), and the
daily tone series used by the SMA/momentum legs, which is resolved as
**EODHD `/sentiments`** first and Alpha Vantage second (GDELT declines — its
article feed carries no tone). Because the two are separate reads, the weighted
leg and the SMA leg can come from different vendors in one run. A mixed-source
tone series is refused rather than scored.

A **quadrant** is reported beside the score: the sign of the name's abnormal
return (vs SPY) × the sign of the change in `tone_innovation`, yielding
confirm-up / diverge-up / confirm-down / diverge-down, or none when either axis
is unreadable.

### 4.5 NewsScore — 11 components, 9 categories

| Component | Weight | Raw | Mapping | Source |
| --- | --- | --- | --- | --- |
| `relevance` | 10 | mean per-article relevance, first 40 articles | ramp 20…80 | Alpha Vantage `NEWS_SENTIMENT`, 30 days |
| `materiality` | 10 | \|option-implied move\| for the next print | ramp 0.01…0.10 | moomoo `get_financials_earnings_price_history` (`predict_vola_ratio_newest`) |
| `novelty` | 15 | first-seen share within 30 days | ramp 0…1 | the same article set |
| `fundamental_impact` | 20 | — | declared, **no producer** | — |
| `earnings_surprise` | 10 | `(actual − estimate)/\|estimate\|` | ramp ±0.05 | moomoo `get_earnings_calendar` |
| `guidance_change` | 5 | signed relative midpoint change | ramp ±0.05 | Benzinga `/v2.1/calendar/guidance` |
| `corporate_events` | 10 | max form score: 8-K 75, SC 13D 70, DEF 14A 55, SC 13G 55, S-1 50, 10-K 45, S-3 40, 10-Q 35 | ramp 0…100 | SEC `data.sec.gov/submissions` |
| `regulatory_legal` | 5 | matched share × severity | ramp 0…1, lower better | Alpha Vantage `topics[]` |
| `analyst_revision` | 5 | `(up − down)/(up + down)`, 60 days | ramp ±0.5 | Yahoo `upgrades_downgrades` |
| `industry_shock` | 5 | Σ(stock − sector) return over 30 sessions | ramp ±0.10 | Yahoo bars for the name and its sector ETF |
| `persistence` | 5 | mention ratio `recent / baseline` | ramp 0.5…3.0, lower better | the tone series' article counts |

The composite needs 2 of 11 components. Categories group these into relevance &
materiality 20, novelty 15, fundamental impact 20, earnings & guidance 15,
corporate events 10, regulatory 5, analyst 5, macro/industry 5, persistence 5.

### 4.6 EventScore — 7 families, imminence

No weights: each family contributes one day-count, converted to imminence, and
the composite is the mean over present families (floor 2 of 7).

```
days      = the family's nearest forward day-count
imminence = clamp(1 − days / H, 0, 1)
score     = 100 × imminence
```

| Family | Horizon `H` | Source of the day-count |
| --- | --- | --- |
| earnings | 60 days | moomoo `get_earnings_calendar` (fetched −35 d … +95 d, in ≤7-day chunks) |
| macro | 3 days | moomoo `get_economic_calendar` (HIGH-importance events only) |
| fed | 10 days | moomoo `get_fed_watch_target_rate` (earliest meeting; modal probability printed) |
| opex | 7 days | date arithmetic only: the third Friday, and the Mon/Tue unwind after it |
| product / clinical | 90 days | pdufa.bio `/api/v1/events` (FDA and readout dates) |
| court | 90 days | declared, no producer |
| investor day | 60 days | declared, no producer |

Flags (`earnings_in_window`, `macro_count_high`, `catalyst_unassessed`,
`opex_in_week`, `opex_post_unwind`, `fed_modal_prob`) are printed, never scored.

The earnings family also produces a **hard block**: a print within the
configured window (default 5 days) forces a rejection downstream. That is a
calendar rule, not part of the score.

### 4.7 RegimeScore — market environment, 6 components

Equal weights; floor 3 of 6. Every leg is computed over the benchmark (SPY).

| Component | Raw | Mapping | Source |
| --- | --- | --- | --- |
| `market_trend` | benchmark `P/SMA − 1` (200-day when ≥200 bars) | ramp ±0.10 | Yahoo SPY bars |
| `breadth` | % of the S&P 500 above its 50-day SMA | ramp 20…80 | §3 panel |
| `vix_percentile` | 0-1 rank of VIX over 252 sessions | ramp 0.10…0.90, lower better | FRED `series/observations?series_id=VIXCLS` |
| `vix_term_structure` | `VIX9D / VIX3M` | ramp 0.85…1.15, lower better | Cboe `VIX9D_History.csv`, `VIX3M_History.csv` |
| `choppiness` | canonical CHOP, 14 bars: `100·log10(ΣTR/(HH−LL))/log10(n)` | ramp 20…65, lower better | Yahoo SPY OHLC |
| `realized_vol_percentile` | 0-1 rank of realised vol over every 21-bar window | ramp 0.10…0.90, lower better | Yahoo SPY bars |

A second, independent read is reported beside the score (`two_paths`): a
single-label vocabulary (high-vol / bull / bear / neutral) and a four-axis
vocabulary (trend, volatility, relative, drawdown). They are never merged; a
declared contradiction rule flags disagreement.

### 4.8 RiskScore — 8 categories, inverted

100 = low risk. Category weights: volatility 15, tail 15, liquidity 10, gap 10,
correlation 15, concentration 10, drawdown 15, event 10. A category needs 2
measured components, the composite 3 of 8 categories.

| Category | Measured components (formula → ramp) | Source |
| --- | --- | --- |
| volatility | `realized_vol` = annualised σ over 21 closes (0.10…0.60); `sqrt_rs_minus` = `√(Σ min(r,0)²/n)` (0.008…0.030); `implied_move_pct` = ATM 1σ move (0.01…0.10) | Yahoo bars; Yahoo option chain |
| tail | `portfolio_cvar` = book CVaR at 5 % (0…0.10); `stress_loss` = uniform −10 % book loss (0…0.10) | basket bars |
| liquidity | `amihud_illiquidity` = mean(\|r\|/dollar volume) (1e-9…1e-6); `spread_pct` = Corwin–Schultz + Abdi–Ranaldo estimate (0.0005…0.02) | Yahoo bars |
| gap | `gap_atr` = \|gap\| in ATR units (0…3) | Yahoo bars |
| correlation | `book_correlated_stress` = mean of the worst-decile mixed book returns (0…0.10) | basket bars |
| drawdown | `measured_book_drawdown` = max drawdown of the basket (0…0.30); `cdar` = conditional drawdown at risk (0…0.25) | basket bars |
| concentration / event | declared but never supplied in this pipeline — these categories therefore stay absent and leave the denominator | — |

All ramps are lower-better. The book legs use the configured basket's names and
weights; with no basket configured those categories are absent, which is why the
composite can be withheld even when enabled.

`uncertainty` is reported beside the score as `1 − coverage`, where coverage is
the fraction of **category weight** measured — not a per-component measure.

### 4.9 TradeScore — the decision composite

```
F fundamental 0.40, T technical 0.25, R regime 0.15, K risk 0.20
floor 2 of 4; no band table
```

RiskScore enters **inverted** (100 = low risk, so a high K helps). No other
engine is included: sentiment, news, momentum and event are standalone reads.
This vector is the owner's, unvalidated, and it is not the same object as any
allocation table elsewhere in the system.

### 4.10 Screening scores (computed, never aggregated)

| Score | Formula | Inputs → source |
| --- | --- | --- |
| **Piotroski F** | 9 binary signals, 0-9: ROA>0, CFO>0, CFO−NI>0, ΔROA>0, Δleverage<0, Δcurrent ratio>0, no share issuance, Δgross margin>0, Δasset turnover>0. A missing input scores 0 | annual statements (§4.1 chain) |
| **Piotroski F (paper basis)** | Same nine signals, stricter definitions: ROA on *beginning* total assets, accrual in ratio form, leverage = LTD / average TA; band (0-1 low / 8-9 high) only when all nine exist | same |
| **G-score** | 8 signals vs **peer medians**: ROA, CFO/beginning TA, CFO>NI, Var(ROA), Var(sales growth), R&D/revenue, capex/revenue, advertising/revenue, 0-8; band 6-8 good / 0-2 poor | same, plus peer medians |
| **Montier C-score** | 6 flags: NI−CFO divergence widening, receivable days up, inventory days up, other current assets up, D&A/net PP&E down, total assets +10 %, 0-6; band 0-2 good / 5-6 poor | same |
| **Quality composite** | Same z → percentile machinery as §4.1 over 7 metrics (F, M, Z, O, gross profitability, NOA, accruals); needs 8 peers, floor 3 metrics | same peer panel |
| **Score evaluation rows** | IC (Spearman/Pearson), decile spreads, coverage, rank stability, top-bucket turnover over stored score snapshots | a stored score ledger (input, not a vendor feed) |

The screening scores print `N of M computed` rather than a partial sum under the
full denominator, and withhold their band unless every signal is present.

---

## 5. Worked arithmetic

Real kernel output for a technical composite:

```
# one leg, ramped
aroon_osc raw 0.0
  frac = (0 - -60) / (60 - -60) = 0.5          -> 50.0

# one leg, banded
stoch_rsi raw 0.12, band [(0.8,25),(0.2,50),(0,80)]
  0.12 >= 0.8? no; >= 0.2? no; >= 0.0? yes     -> 80.0

# one category (equal weights, floor 2 legs)
trend = (80 + 50) / 2 = 65.0                      coverage 1.0, floor 2

# the composite (measured categories only)
components  = trend 65.0, momentum 100.0, price_structure 75.0,
              volume 60.0, volatility 90.0        (relative_strength,
              breakout, mean_reversion, breadth absent)
weights     = 20 + 18 + 12 + 10 + 5 = 65 of 100   -> coverage 0.65
score       = (20·65 + 18·100 + 12·75 + 10·60 + 5·90) / 65
            = 5050 / 65 = 77.69                   -> "constructive" (>= 65)
```

Had the four absent categories been entered as 0 instead, the same inputs give
`5050/100 = 50.5`, i.e. "neutral" — one half-point above the neutral floor. That
is the whole reason the denominator is renormalised rather than filled.

---

## 6. Endpoint reference

| Input | Exact call |
| --- | --- |
| Daily bars | `yf.download(symbol, start, end, auto_adjust=True)` |
| Statements (first) | moomoo `OpenQuoteContext.get_financials_statements(code, statement_type=1\|2\|3, financial_type=7\|9, num=8)` |
| Statements (fallback) | `yf.Ticker(sym).balance_sheet / income_stmt / cashflow` |
| Statements (fallback) | `GET https://api.tiingo.com/tiingo/fundamentals/{sym}/statements?statementType=incomeStatement\|balanceSheet\|cashFlow` |
| Statements (fallback) | `GET https://www.alphavantage.co/query?function=BALANCE_SHEET\|INCOME_STATEMENT\|CASH_FLOW&symbol=` and `function=OVERVIEW` |
| Financial gap-fill | Finnhub `company_basic_financials(symbol, "all")` |
| Peers | Finnhub `company_peers(ticker)` |
| Sector label | FMP `profile` → Finnhub `company_profile2` → `yf.Ticker(s).info["sector"]` |
| Articles / tone (AV) | `GET https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=…&time_from=…&time_to=…` |
| Tone series (first) | `GET https://eodhd.com/api/sentiments?s={ticker}&from=…&to=…&fmt=json` |
| Analyst actions | `yf.Ticker(t).upgrades_downgrades` |
| Options | `yf.Ticker(t).options` → `option_chain(expiry)` |
| Short interest | `yf.Ticker(t).info["shortPercentOfFloat"]` |
| Institutional flow | moomoo `get_shareholders_institutional(code)` |
| Social | `GET https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json` |
| Earnings calendar | moomoo `get_earnings_calendar(market, begin_date, end_date)` (≤7-day windows) |
| Implied move | moomoo `get_financials_earnings_price_history(code)` → `predict_vola_ratio_newest` |
| Economic calendar | moomoo `get_economic_calendar(begin_date, end_date)` |
| Fed watch | moomoo `get_fed_watch_target_rate()` |
| FDA / clinical | `GET https://www.pdufa.bio/api/v1/events?ticker={TICKER}&limit=200` |
| Filings | `GET https://data.sec.gov/submissions/CIK{cik:010d}.json` |
| Guidance | `GET https://api.benzinga.com/api/v2.1/calendar/guidance?parameters[tickers]=…` |
| VIX level | `GET https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&observation_start=…&observation_end=…&file_type=json` |
| VIX term structure | `GET https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX9D_History.csv` (and `VIX3M_History.csv`) |
| S&P 500 universe | `GET https://en.wikipedia.org/w/api.php?action=parse&page=List of S&P 500 companies&prop=wikitext&format=json` |
| Exchange symbol list | `GET https://eodhd.com/api/exchange-symbol-list/{market}?fmt=json` |
