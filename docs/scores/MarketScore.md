# MarketScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master —
architecture, cross-engine rules, the composite, the code defects, the phase plan,
the open questions). Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`RiskScore.md`](RiskScore.md), [`NewsScore.md`](NewsScore.md),
[`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
[`ValuationScore.md`](ValuationScore.md).

**Scope: the market-state engine only.** It designs `MarketScore` — *"how is this
stock behaving in the market?"* — from the owner's formula library in
[`../../Strategies/scores/market_score.md`](../../Strategies/scores/market_score.md).
The library's own framing, verbatim (`Strategies/scores/market_score.md:1-4`):

> For your architecture, I would define **MarketScore** as the quantitative score
> describing the **stock's current market behavior**—price trend, momentum,
> relative strength, volatility, volume, liquidity, market participation, mean
> reversion, and market-relative behavior.

Status: **designed, not built (2026-09-26).** There is no `MarketScore` module, no
gate, no leaf and no config key — §0.1 is the grep that says so, run this round.
The only artifact in the tree is the owner's formula library (2,885 lines, 140
numbered sections, 282 display formulas). This document accounts for that library;
it does not claim any part of it is implemented.

---

## 0. What this engine answers, and what it must not become

### 0.1 No MarketScore producer exists — answered by grep, not assumption

The claim "there is no `MarketScore` today" is a grep result, not an impression.
Run this round from the repo root:

```console
$ grep -rn "market_score\|MarketScore" --include=*.py tradingagents/ scripts/ tests/
$ echo $?
1
$ grep -rn "market_score" tradingagents/default_config.py .env.example
$ echo $?
1
```

**Zero matches in both** (exit status 1 = no line matched). Every hit for either
string in the tree is markdown: the owner's library
(`Strategies/scores/market_score.md`), the master's own `[ADDED 2026-09-26]` block
(`README.md` §1.1/§1.3), this document, and the sibling docs. The two places a
producer would have to register are both empty of it:

| Registry | Symbol | MarketScore entry |
| --- | --- | --- |
| Engine → gate map | `strategies/quant_scorecard.py::ENGINE_GATES:78` (eight keys: fundamental, technical, regime, risk, sentiment, news, event, trade) | **absent** |
| Config gate defaults | `default_config.py:1234-1276` (`enable_fundamental_score` … `enable_quant_scorecard`; env aliases `:341-353`) | **absent** — no `enable_market_score` |
| Leaf | `agents/utils/analysis_tools.py` (`get_fundamental_score:5331`, `get_technical_score:5691`, `get_risk_score:5967`, `get_trade_score:6047`, `get_regime_score:6448`, `get_sentiment_score:6652`, `get_news_score:6838`, `get_event_state:6184`) | **absent** — no `get_market_score` |

So a future implementation is a **new aggregation over existing numbers**, not a
rename of something that exists. The only 0-100 producers in the repo are the
other engines and the structural scorers named in `TechnicalScore.md` §0.1
(`factors.category_scores:258`, `data_quality.aggregate_quality:46`,
`news_relevance.score_news_article:56`, `decision_guardrail.SCORE_BANDS:27`) —
none of them market-state.

### 0.2 The boundary disagreement — the library and the built engines disagree about momentum, relative strength and volatility

The library's preamble (quoted above) hands this engine *price trend, momentum,
relative strength, volatility, volume, liquidity, market participation, mean
reversion and market-relative behavior*. The owner's other library, verbatim
(`Strategies/scores/technical_score.md:1-3`):

> Absolutely. For your architecture, I would make **TechnicalScore** the
> quantitative assessment of the stock's **technical condition and setup
> quality**, while keeping the broader **MarketScore** focused on market
> behavior/factor exposure such as momentum, relative strength, liquidity,
> volatility, and cross-sectional market characteristics.

So the two libraries agree with each other: momentum, relative strength and
volatility belong to **MarketScore**. But the **built** `TechnicalScore` already
owns exactly those, with the owner's own staged weights
(`docs/scores/TechnicalScore.md` §0.2; engine `strategies/technical_score.py::technical_score:324`):

| Category | TechnicalScore weight (built) | MarketScore library's claim on it |
| --- | --: | --- |
| Trend | **20%** | §5, §46, §47, §129 — "price trend" |
| Momentum | **18%** | §2, §3, §4, §55, §58, §128 — "momentum" |
| Relative strength | **12%** | §10-§14, §103, §104, §126, §127 — "relative strength" |
| Volatility / ATR | **5%** | §15-§22, §74, §107 — "volatility" |
| Breadth / participation | **5%** | §94-§102 — "market participation" |

**This document does not resolve that.** It records it as the first OPEN question
(§7 Q1) because it is the one decision that determines what is left to build: if
`TechnicalScore` keeps Trend/Momentum/Relative strength/Volatility/Breadth,
MarketScore's remaining library is §36 (liquidity), §79-§93 (tail/distribution,
beta/idio-vol/residual), §105-§118 (regime, options, short interest, flow) and
§131-§134 (normalisation) — and §105-§118 in turn collide with `RegimeScore`,
`RiskScore`, `SentimentScore` and `EventScore` (README §1.1's `[ADDED 2026-09-26]`
block records the same collision from the master's side).

Two further collisions inside the library itself, both recorded not fixed:

- **§139 hands the same quantity to two engines.** Its own recommended separation
  gives *Market regime* and *Breadth* to MarketScore **and** *Breadth regime*,
  *Correlation regime* and the VIX regime to `RegimeScore`. Breadth and the
  volatility regime therefore appear in two lists (§94-§102 vs §105-§107), which
  is the definition of the naming problem master rule 3 forbids.
- **§118 drops itself.** Insider transaction pressure "arguably belongs in your
  **Event/Sentiment** engine rather than MarketScore, so I wouldn't double-count
  it" (`Strategies/scores/market_score.md:2288-2291`) — and the repo now has those
  producers (`analysis_tools.py::get_insider_activity:2140`,
  `get_form4_insider:2130`).

### 0.3 The conventions this engine must pin — the library mixes units in three places

Master §1.2 requires every component to print its raw value with units and sign
beside its aligned contribution, because a single aligned score silently picks one
convention. The library carries **three unit ambiguities** that a build must pin
explicitly (they are library defects, §4 and §0.2 of the master's own defect
ledger is where this class of thing is recorded):

| Quantity | Convention A | Convention B | Why it matters |
| --- | --- | --- | --- |
| **Relative strength** | §10 difference of returns: `RS_n = R_stock,n − R_bench,n` | §11 ratio of price levels: `RSRatio_t = P_stock,t / P_bench,t`, then `RSROC_n = RSRatio_t/RSRatio_{t−n} − 1` | the two are not the same number for the same pair; the repo has both shapes (`relative_strength.py::rs_series:33` is a ratio series, `relative_strength.py::slope_pct:49` is a slope of that ratio) |
| **Realized volatility** | §16 `RV_n = √(Σ r_i²)` — a **window sum**, so it grows with `n` | §15 `σ_n = Std(r)` — a per-bar dispersion, and `σ_annual = Std(r)·√252` | `RV_n` and `σ_annual` are not comparable; the repo's `regime.py::realized_vol:39` annualizes (`√(252·Σr²)`), which is the §16 second formula |
| **Downside / upside volatility** | §17 `σ_down = Std(min(r_i, 0))` — **conditional-standard-deviation shape** | a true semivariance decomposition `RS⁻ + RS⁺ = RV` | `Std(min(r,0))` is taken over a series in which every up day is a literal `0`, so it is neither the conditional deviation (std of the negative-return days) nor `√RS⁻`; the repo's `factor_expressions.py::_side_vol:437` computes the conditional form (std of the positive days / of the negative days), and `TechnicalScore.md` §1/§4 owns the semivariance producer, which is still ABSENT |

**Design decision for any build: one convention per quantity, pinned in the
alignment step and printed with the raw value** — §10's return difference for the
RS *contribution*, §11's ratio series as its own component (never both under one
name); `√(Σ r²)` annualized for realized vol; and the conditional `Std(r | r<0)`
labelled *conditional deviation*, with the semivariance leg read from
`TechnicalScore.md`'s producer rather than re-derived here (master rule 3).

### 0.4 What this engine must not become

1. **Not a second `TechnicalScore`.** The library is a *factor-exposure* layer
   (§139), the built engine is an indicator/setup layer. Two engines reading the
   same trend/momentum/volatility numbers is the failure mode the library's own
   §138 warns about in its own words: *"If you give each one a separate 10% weight,
   you have accidentally created: Trend/momentum = 70%"* — and its remedy is
   `raw indicators → correlated-indicator clusters → factor subscores →
   MarketScore`, never "~130 calculations as independent votes" (§140).
2. **Not a forecast.** A market-state score describes; the library itself lists
   §77/§78 (MAE/MFE) as *"particularly useful if your MarketScore eventually
   becomes connected to trade execution"* — it must not.
3. **Not a gate.** Advisory only (master rule 2). The library's §79 tail-risk and
   §7-§9 drawdown sections read producers that `RiskScore` already scores; this
   engine may print them as state, never as an override.
4. **Not a cross-sectional rank without a cross-section.** §12, §13, §103, §131-§133
   are percentile constructs. `analysis_tools.py::get_cross_section_momentum:5409`
   falls back to *"the ticker plus up to 8 vendor peers"*
   (`dataflows/finnhub.py::get_company_peers_finnhub:380`, `peer_symbols:398`); a
   percentile over nine names is not a decile (§7 Q4).

---

## 1. Component inventory

The library's own sections, in order. **Formula count** = the number of
`$$…$$` display blocks in the section's line range (each block opens and closes
with a `$$` line) — **282 across the 140 sections**; §130, §137 and §139 carry
tables/prose instead of display formulas. **Status** is `elsewhere` when a
verified producer exists today, `PARTIAL` when only part of the section is
producible, `ABSENT` when nothing produces it. Every producer cell names a symbol
read this round; the line anchors here are the ones verified against the working
tree (several sibling docs' anchors have drifted by 4-120 lines — see §2 note).

| § | Section (library) | Formulas | Status | Producer / nearest honest producer (`module.symbol:line`) |
| --: | --- | --: | --- | --- |
| 1 | Return calculations | 5 | elsewhere | `factor_expressions._returns:355`; `evaluate.net_returns:35`; `momentum.momentum_12_1:358` |
| 2 | Multi-horizon momentum | 3 | elsewhere | `factor_expressions.mom:216` (5/10/20/60 via `alpha158_subset:373`); `factors.momentum_multihorizon:418` (21/63/126/252, **UNWIRED** per `TechnicalScore.md` §1) |
| 3 | Momentum excluding the most recent month | 1 | elsewhere | `momentum.momentum_12_1:358`; `factors.momentum:24` (lookback 252, skip 21) |
| 4 | Momentum acceleration | 4 | elsewhere | `sector_rank._acceleration:289`; `extended_indicators.momentum_oscillator:162` |
| 5 | Trend calculations | 12 | elsewhere | `swing.trend_architecture:76`; `extended_indicators.golden_death_cross:55`; `quant_baseline.trend_strength:28` (UNWIRED) |
| 6 | Distance from high/low | 5 | elsewhere | `factor_expressions._max_high:411`, `_min_low:420` (20-bar); `overlays.build_strategy_overlays:47` (52-week distance) |
| 7 | Drawdown | 3 | elsewhere | `evaluate.max_drawdown:222`; `book_risk.portfolio_drawdown:120`; `regime_state.regime_drawdown:146` |
| 8 | Drawdown recovery | 2 | PARTIAL | `evaluate.underwater_drawdowns:979` (episodes, not a recovery ratio) |
| 9 | Time-under-water | 2 | PARTIAL | `evaluate.underwater_drawdowns:979` |
| 10 | Relative strength vs benchmark | 2 | elsewhere | `relative_strength.relative_strength_report:214` |
| 11 | Relative strength ratio | 2 | elsewhere | `relative_strength.rs_series:33`; `relative_strength.slope_pct:49` |
| 12 | Relative momentum percentile | 2 | elsewhere | `factor_expressions.cross_sectional_rank:268`; `factors.percentile_rank:59`; `cross_section.momentum_book:398` |
| 13 | Sector-relative momentum | 3 | elsewhere | `sector_rank.sector_standing:176`; `sector_rank._momentum:27`; `sector_screener._rel_outperformance:248` |
| 14 | Risk-adjusted momentum | 2 | elsewhere | `cross_section.momentum_book:398` (return ÷ realized vol); `rotation.clenow_momentum:89` |
| 15 | Volatility | 2 | elsewhere | `evaluate.volatility:84`; `factor_expressions.std:155`; `regime.realized_vol:39` |
| 16 | Realized volatility | 2 | elsewhere | `regime.realized_vol:39`; `volatility_models.ewma_vol:397`; `quant_baseline.volatility:39` |
| 17 | Downside volatility | 2 | PARTIAL | `factor_expressions._side_vol:437` (conditional std); `rate_utils.downside_measures:149`; `evaluate.downside_deviation:846` — semivariance ABSENT |
| 18 | Upside volatility | 1 | PARTIAL | `factor_expressions._side_vol:437` (`up=True`) — no upside semivariance |
| 19 | Volatility ratio | 2 | elsewhere | `regime_state.regime_vol_ratio:92`; `rotation.vol_cones:123` |
| 20 | Volatility acceleration | 1 | ABSENT | no Δ(ratio) producer; nearest `regime_state.regime_vol_ratio:92` (level) |
| 21 | ATR | 3 | elsewhere | `size.atr:143`; `etf_risk._atr:122`; `regime_state._atr14:55` |
| 22 | ATR expansion | 1 | PARTIAL | `knife_guard.atr_ratio_z:115` (z of the ratio); `regime_state.regime_vol_ratio:92` |
| 23 | Beta | 1 | elsewhere | `evaluate.beta:901`; `etf_risk._beta:39` |
| 24 | Rolling beta | 2 | elsewhere | `evaluate.rolling_beta:939` |
| 25 | Alpha | 2 | elsewhere | `evaluate.alpha:920` |
| 26 | Information ratio | 3 | elsewhere | `evaluate.information_ratio:892`; `evaluate.tracking_error:869` |
| 27 | Tracking error | 1 | elsewhere | `evaluate.tracking_error:869` |
| 28 | Sharpe ratio | 2 | elsewhere | `evaluate.sharpe:94`; `evaluate.rolling_sharpe:1300` |
| 29 | Sortino ratio | 1 | elsewhere | `evaluate.sortino:860` |
| 30 | Calmar ratio | 1 | elsewhere | `evaluate.calmar_ratio:1018` |
| 31 | Gain/loss ratio | 1 | PARTIAL | `rate_utils.gain_to_pain:219` (gain-to-pain, not avg-win ÷ avg-loss) |
| 32 | Hit rate | 1 | PARTIAL | `alpha_health.win_rate_by_rating:266` (rating-conditional, not return-sign frequency) |
| 33 | Up/down capture | 2 | elsewhere | `evaluate.capture_ratio:1132`; `etf_risk._capture:53` |
| 34 | Volume calculations | 4 | elsewhere | `momentum.rvol:25`; `factor_expressions.avg_vol:246` |
| 35 | Dollar volume | 2 | PARTIAL | internal to `liquidity_risk.amihud_illiquidity:71`; `liquidity_risk.days_to_absorb:103` takes `adv` as a caller argument — no standalone ADV producer |
| 36 | Liquidity | 4 | elsewhere | `liquidity_risk.amihud_illiquidity:71`, `float_turnover:53`, `free_float_factor:34` |
| 37 | Price-volume relationship | 2 | elsewhere | `factor_expressions.corr:224` (`corr_ret_vol_20` in `alpha158_subset:373`) |
| 38 | Volume confirmation | 3 | PARTIAL | `technical_factors.elder_thermometer:649` (ratio, no sign); `value_dip.trigger_candle:661` |
| 39 | On-Balance Volume | 2 | PARTIAL | `technical_factors.obv_divergence:542` computes the OBV level locally and discards it |
| 40 | OBV divergence | 3 | elsewhere | `technical_factors.obv_divergence:542` |
| 41 | Accumulation/distribution | 3 | elsewhere | `extended_indicators.accumulation_distribution:224` |
| 42 | Chaikin Money Flow | 1 | elsewhere | `extended_indicators.chaikin_money_flow:263` |
| 43 | Money Flow Index | 4 | elsewhere | `technical_factors.mf_index:163` |
| 44 | VWAP | 2 | elsewhere | `momentum.vwap:49`; `extended_indicators.anchored_vwap:289` |
| 45 | VWAP slope | 1 | PARTIAL | `relative_strength.slope_pct:49` (generic OLS slope over any series) |
| 46 | Price efficiency | 2 | ABSENT | no `efficiency ratio` producer; nearest `regime.choppiness:141` (a different noise ratio) |
| 47 | Trend persistence | 4 | PARTIAL | `regime.choppiness:141`; `mean_reversion.mean_reversion_verdict:226` (label) |
| 48 | Consecutive return streak | 1 | ABSENT | no streak producer |
| 49 | Mean reversion | 2 | elsewhere | `value_dip.zscore:104`; `factors.z_score:68` |
| 50 | Return z-score | 1 | elsewhere | `factor_expressions.zscore:160`; `knife_guard.momentum_return_z:78` |
| 51 | Bollinger position | 3 | elsewhere | `value_dip.bollinger_pct_b:77` |
| 52 | Bollinger bandwidth | 1 | PARTIAL | `value_dip.bollinger_pct_b:77` returns the bands; the width ratio is not returned |
| 53 | Bollinger bandwidth percentile | 1 | ABSENT | no bandwidth series to rank |
| 54 | RSI | 2 | elsewhere | `swing.rsi:44`; `factor_expressions.rsi:175`; `technical_factors.rsi2:406` |
| 55 | RSI momentum | 1 | ABSENT | `swing.rsi:44` returns a scalar; `value_dip._rsi_series:472` holds the series but nothing differentiates it |
| 56 | RSI divergence | 4 | elsewhere | `value_dip.macd_divergence:542` (RSI / MACD-hist divergence verdict) |
| 57 | MACD | 3 | PARTIAL | `value_dip._macd_hist:502` (private); the vendor `get_indicators` text |
| 58 | MACD momentum | 1 | PARTIAL | `rule_eval.rule_signal_macd_hist_rising:103` (UNWIRED — no production reader) |
| 59 | Stochastic oscillator | 2 | elsewhere | `technical_factors.stochastic_oscillator:197` |
| 60 | Rate of change | 1 | elsewhere | `extended_indicators.roc:151`; `sector_rank._momentum:27` |
| 61 | Average Directional Index | 6 | elsewhere | `technical_factors.adx:230` |
| 62 | Directional bias | 2 | elsewhere | `technical_factors.adx:230` (`di_plus`/`di_minus`) |
| 63 | Ichimoku calculations | 5 | elsewhere | `extended_indicators.ichimoku:80` |
| 64 | Breakout calculations | 2 | elsewhere | `technical_factors.donchian_channel:468`; `swing.vcp_setup:342` |
| 65 | Breakout strength | 1 | PARTIAL | `swing.vcp_setup:342` (`pivot`, `near_breakout`) — no (P − resistance)/ATR |
| 66 | Breakout volume confirmation | 2 | PARTIAL | `swing.vcp_setup:342` (volume fade); `value_dip.trigger_candle:661` (rvol) |
| 67 | Gap calculations | 2 | elsewhere | `market_session.gap_type:220`; `pre_market.premarket_gap:40` |
| 68 | Gap fill | 1 | elsewhere | `market_session.gap_type:220` (`fill_probability`, `days_to_fill` — measured since 2026-09-17 per `RiskScore.md` §3.2) |
| 69 | Intraday strength | 2 | ABSENT | nearest `factor_expressions.high_low_range:251` |
| 70 | Close location value | 2 | ABSENT | no CLV producer |
| 71 | Candle body strength | 1 | PARTIAL | `extended_indicators._body:537` (private, used by `scan_candlesticks:603`) |
| 72 | Upper/lower wick ratios | 2 | PARTIAL | `extended_indicators.scan_candlesticks:603` (hammer/shooting-star need wick geometry) |
| 73 | Range expansion | 2 | elsewhere | `factor_expressions.high_low_range:251`; `value_dip.range_expansion_guard:1043` |
| 74 | Volatility-adjusted return | 2 | PARTIAL | `cross_section.momentum_book:398` (return ÷ vol); `knife_guard.momentum_return_z:78` |
| 75 | Sharpe-like momentum | 1 | elsewhere | `cross_section.momentum_book:398`; `evaluate.sharpe:94` |
| 76 | Downside-adjusted momentum | 1 | ABSENT | no momentum ÷ downside-deviation producer |
| 77 | Maximum adverse excursion | 1 | ABSENT | no MAE producer |
| 78 | Maximum favorable excursion | 1 | ABSENT | no MFE producer |
| 79 | Tail risk | 3 | elsewhere | `book_risk.simple_var:9`, `book_risk.cvar:18` |
| 80 | Skewness | 1 | elsewhere | `evaluate.skewness:818` |
| 81 | Kurtosis | 2 | elsewhere | `evaluate.kurtosis:832` |
| 82 | Return distribution stability | 2 | ABSENT | no rolling skew/kurt **change** producer |
| 83 | Autocorrelation | 1 | elsewhere | `book_risk.return_autocorrelation:355`; `mean_reversion.ar1_half_life:69` |
| 84 | Partial autocorrelation | 1 | ABSENT | no PACF producer |
| 85 | Hurst exponent | 4 | elsewhere | `mean_reversion.hurst_exponent:113` |
| 86 | Variance ratio | 3 | elsewhere | `mean_reversion.variance_ratio:259` |
| 87 | Trend-to-noise ratio | 1 | PARTIAL | `regime.choppiness:141` (a different noise ratio, 0-100) |
| 88 | Fractal dimension | 1 | ABSENT | no `D ≈ 2 − H` producer (Hurst exists; the transform does not) |
| 89 | Market beta regimes | 4 | PARTIAL | `evaluate.rolling_beta:939`; `etf_risk._beta:39` — no β20 − β252 compression |
| 90 | Idiosyncratic volatility | 2 | elsewhere | `lottery.idiosyncratic_vol:51` |
| 91 | Residual momentum | 2 | PARTIAL | `cross_section.residualize_returns:223` (residuals, not their sum) |
| 92 | Market correlation | 3 | elsewhere | `statistical.correlation_matrix:203`; `portfolio.mean_correlation:252` |
| 93 | Correlation regime | 1 | ABSENT | no ρ_short − ρ_long producer |
| 94 | Market breadth | 2 | PARTIAL | `sector_breadth.multi_breadth:165` (sector level); `moomoo_extra_tools.get_market_breadth:98` (**text blob only**) |
| 95 | Advance/decline ratio | 1 | ABSENT | internals of `sector_breadth.mcclellan_read:213` only; no numeric A/D producer |
| 96 | Advance/decline line | 1 | elsewhere | `sector_breadth.mcclellan_read:213` (MSI cumulative index) |
| 97 | Breadth percentage | 2 | elsewhere | `sector_breadth.multi_breadth:165` |
| 98 | Percent above moving average | 3 | elsewhere | `sector_breadth.multi_breadth:165`; `sector_rank.constituent_breadth:664` |
| 99 | New-high/new-low breadth | 2 | ABSENT | no NH/NL producer |
| 100 | Volume breadth | 3 | ABSENT | no up/down-volume breadth producer |
| 101 | Breadth thrust | 1 | PARTIAL | `sector_breadth.mcclellan_read:213` (McClellan oscillator/ratio) |
| 102 | Sector breadth | 1 | elsewhere | `sector_breadth.multi_breadth:165` |
| 103 | Sector-relative performance | 2 | elsewhere | `sector_rank.sector_standing:176` |
| 104 | Industry-relative performance | 1 | elsewhere | `sector_rank.rank_industry_group:600` |
| 105 | Market regime return | 3 | elsewhere | `overlays.build_strategy_overlays:47` (mom60); `regime.regime_label:194` |
| 106 | Market trend regime | 1 | elsewhere | `regime_state.regime_state:215`; `regime_score.regime_score:265` |
| 107 | Volatility regime | 1 | elsewhere | `regime_state.regime_vol_ratio:92`; `regime_score.regime_score:265` |
| 108 | Volatility term structure | 2 | elsewhere | `options_surface.term_structure_slope:227`; `analysis_tools._regime_components:6598` (VIX9D/VIX3M) |
| 109 | Realized vs implied volatility | 2 | ABSENT | no variance-risk-premium producer; nearest `options_surface.iv_percentile:15`, `iv_skew:25` |
| 110 | Implied volatility percentile | 1 | PARTIAL | `options_surface.iv_percentile:15` is §111's percentile; §110's `IVRank` = (IV − low)/(high − low) is a **different** definition and is not produced |
| 111 | IV percentile | 1 | elsewhere | `options_surface.iv_percentile:15` |
| 112 | Put/call ratios | 2 | elsewhere | `options_surface.put_call_oi_concentration:34` |
| 113 | Short interest | 1 | elsewhere | `short_interest.short_interest_percentile:35`; leaf `market_position_tools.get_short_interest:220` |
| 114 | Days to cover | 1 | ABSENT | no `days_to_cover` producer |
| 115 | Short-interest change | 1 | elsewhere | `short_interest.short_interest_percentile:35` (`change_pct`) |
| 116 | Short squeeze pressure | 1 | ABSENT | no squeeze producer; the library's own `f(...)` is unspecified |
| 117 | Institutional ownership change | 1 | PARTIAL | `orderflow.institutional_net:45` (flow, not ownership change); leaf `analysis_tools.get_ownership_concentration:8033` |
| 118 | Insider transaction pressure | 2 | elsewhere | `analysis_tools.get_insider_activity:2140`, `get_form4_insider:2130`; `news_data_tools.get_insider_transactions:154` — **library itself says this belongs to Event/Sentiment** (§118) |
| 119 | Market microstructure | 2 | elsewhere | `liquidity_risk.spread_estimate:547`, `roll_spread:309` |
| 120 | Effective spread | 2 | elsewhere | `liquidity_risk.spread_estimate:547` (Corwin-Schultz / Abdi-Ranaldo — OHLC **proxies** for the effective spread, not quotes) |
| 121 | Order imbalance | 1 | PARTIAL | `market_session.order_imbalance:281` (from institutional/retail nets, not buy/sell volume); `orderflow.summarize:128` |
| 122 | Quote imbalance | 1 | ABSENT | no bid/ask-size producer |
| 123 | VPIN-style order-flow toxicity | 1 | elsewhere | `orderflow.vpin:198`; `orderflow.knife_guard_vpin:103` |
| 124 | Market impact | 2 | elsewhere | `liquidity_risk.market_impact_slippage:348`, `kyle_lambda:262` |
| 125 | Liquidity-adjusted momentum | 2 | ABSENT | no momentum ÷ ILLIQ producer |
| 126 | Volatility-adjusted relative strength | 1 | ABSENT | no (R_stock − R_bench) ÷ σ_stock producer |
| 127 | Relative Sharpe | 1 | elsewhere | `evaluate.information_ratio:892` is the same object (`(R_i − R_B)/TE`) |
| 128 | Momentum consistency | 2 | ABSENT | no share-of-positive-horizons producer |
| 129 | Multi-horizon trend agreement | 1 | PARTIAL | `swing.trend_architecture:76` (2 of the 4 MAs) |
| 130 | Multi-factor market score | 0 | ABSENT | the 9-family architecture — design only |
| 131 | Factor normalization | 1 | elsewhere | `factors.z_score:68`; `cross_section.cross_sectional_z:70` |
| 132 | Robust normalization | 2 | PARTIAL | `cross_section.winsorize:31`; `analyst_revisions.winsor_z:253` — no MAD-based robust z |
| 133 | Percentile transformation | 2 | elsewhere | `factors.percentile_rank:59`; `factor_expressions.cross_sectional_rank:268` |
| 134 | Direction normalization | 2 | PARTIAL | `score_engine.align:69` (direction-aware mapping exists as the kernel) — no per-factor inversion table |
| 135 | Market factor subscores | 10 | ABSENT | no subscores; the built engines' subscores belong to those engines |
| 136 | Composite MarketScore | 1 | ABSENT | the whole engine |
| 137 | A practical initial weighting | 0 | ABSENT | library-only weight table (§5) |
| 138 | Don't double-count | 2 | ABSENT | design guidance (this document's §0.4.1) |
| 139 | Recommended separation | 0 | ABSENT | design guidance (this document's §0.2) |
| 140 | The MarketScore I'd actually build | 1 | ABSENT | target output spec (score + 9 subscores + coverage/freshness/agreement/confidence) |

**Counts:** `elsewhere` 78, `PARTIAL` 31, `ABSENT` 31 (total 140).

---

## 2. What already exists elsewhere

These are the producers the library's formulas would **reuse**, not re-derive
(master rule 3). Every row was read this round; the anchors are the verified ones.

| Library family | Producer (`path::symbol`) | What it returns | Reuse note |
| --- | --- | --- | --- |
| §1-§2, §34, §37, §49-§51, §54, §60, §73 raw values | `strategies/factor_expressions.py::alpha158_subset:373` (+ `mom:216`, `rsi:175`, `bias:208`, `std:155`, `zscore:160`, `high_low_range:251`, `avg_vol:246`, `corr:224`, `_max_high:411`, `_min_low:420`, `_side_vol:437`) | 16-series Alpha158-style vector off `{closes, opens, highs, lows, volumes}` | the closest thing in the repo to the library's §1-§6 raw layer; surfaced as text by `domain_bundles.get_factor_profile:124` / leaf `analysis_tools.get_factor_profile:12019` under `enable_factor_profile` |
| §3, §105 | `strategies/momentum.py::momentum_12_1:358`; `strategies/factors.py::momentum:24` | 12-1 momentum (skip 21, window 252) | one number, two callers already |
| §12-§14, §75 | `strategies/cross_section.py::momentum_book:398` (+ `cross_sectional_z:70`, `centered_rank:140`, `quantile_split:169`, `residualize_returns:201`, `neutralize_book:237`) | risk-adjusted momentum book over a caller panel, dollar/beta neutralised | leaf `analysis_tools.get_cross_section_momentum:5409`; panel = caller names or the ticker + ≤8 vendor peers (`dataflows/finnhub.py::get_company_peers_finnhub:380`, `peer_symbols:398`) |
| §10-§11 | `strategies/relative_strength.py::rs_series:33`, `slope_pct:49`, `rs_position:89`, `divergence:195`, `relative_strength_report:214` | ratio series, OLS slope, new-high flags, divergence, verdict | benchmark from `analysis_tools._benchmark_closes:322` (`benchmark_ticker`, default SPY); sector ETF via `analysis_tools._bench_ohlcv:1958` + `sector_rank.sector_group_of:163` |
| §7-§9, §15-§33, §79-§86 | `strategies/evaluate.py::max_drawdown:222`, `volatility:84`, `sharpe:94`, `rolling_sharpe:1300`, `sortino:860`, `calmar_ratio:1018`, `capture_ratio:1132`, `skewness:818`, `kurtosis:832`, `downside_deviation:846`, `tracking_error:869`, `information_ratio:892`, `beta:901`, `alpha:920`, `rolling_beta:939`, `underwater_drawdowns:979`, `ulcer_index:1037`, `tail_ratio:1166`, `deflated_sharpe:161` | the performance/risk-statistic family, all taking `returns` (+ `benchmark`) | `rate_utils.py::downside_measures:149`, `lower_partial_moment:186`, `kappa_ratio:204`, `gain_to_pain:219` are the partial-moment neighbours |
| §17-§18 | `strategies/factor_expressions.py::_side_vol:437` | conditional std of the positive-day returns / of the negative-day returns | **not** a semivariance decomposition; the semivariance producer is owned by `TechnicalScore.md` §1/§4 and is ABSENT |
| §19-§22 | `strategies/regime_state.py::regime_vol_ratio:92`, `vol_cap_factor:169`, `_atr14:55`; `strategies/knife_guard.py::atr_ratio_z:115`; `strategies/size.py::atr:143`; `strategies/etf_risk.py::_atr:122` | vol ratio, vol cap factor, ATR (3 producers) | `size.atr:143` returns `None` on failure (the `0.0` defect was fixed 2026-09-17) |
| §23-§24, §89-§90 | `strategies/evaluate.py::beta:901`, `rolling_beta:939`; `strategies/etf_risk.py::_beta:39`; `strategies/lottery.py::idiosyncratic_vol:51`; `strategies/book_risk.py::net_beta:179` | β, rolling β, per-name β, residual vol, book net beta | `net_beta` is a pure `sum(w·β)` helper with no book builder wiring it (`RiskScore.md` §3.3) |
| §34-§36, §119-§120, §124 | `strategies/liquidity_risk.py::amihud_illiquidity:71`, `float_turnover:53`, `free_float_factor:34`, `days_to_absorb:103`, `spread_estimate:442`, `kyle_lambda:262`, `roll_spread:309`, `volume_share_slippage:220`, `market_impact_slippage:243`, `liquidity_verdict:153` | ILLIQ, turnover, IWF, days-to-absorb, spread, Kyle λ, Roll spread, slippage, 3-valued verdict | `float_turnover`/`days_to_absorb` take ADV and float shares as **arguments** — no ADV producer (§35 PARTIAL) |
| §38-§45, §54-§62 | `strategies/technical_factors.py::ema:40`, `kst:57`, `mf_index:116`, `stochastic_oscillator:150`, `adx:183`, `pivot_points:243`, `stoch_rsi:319`, `rsi2:351`, `williams_r:374`, `keltner_channel:385`, `donchian_channel:413`, `obv_divergence:450`, `parabolic_sar:486`, `elder_thermometer:530`, `aroon:549`, `chaikin_oscillator:614`, `supertrend:673`, `volume_profile:708` | the indicator family | these are the same producers `TechnicalScore.md` §1 reads — the overlap in §0.2 |
| §39-§44, §60, §63 | `strategies/extended_indicators.py::golden_death_cross:55`, `ichimoku:80`, `roc:151`, `momentum_oscillator:162`, `force_index:206`, `accumulation_distribution:224`, `vpt:248`, `chaikin_money_flow:263`, `anchored_vwap:289`, `scan_candlesticks:603` | Ichimoku, crosses, ROC, A/D, VPT, CMF, VWAP, candlestick scan | leaf `analysis_tools.get_extended_indicators:8364` |
| §5, §64-§66 | `strategies/swing.py::trend_architecture:76`, `rsi:44`, `rsi_band:123`, `pullback_setup:161`, `vcp_setup:342`, `swing_low_stop:190`, `fib_levels:295`, `swing_report:457` | MA stack booleans, RSI + band, pullback/VCP candidates | leaf `analysis_tools.get_swing_set:465` |
| §49-§53, §56, §57, §73 | `strategies/value_dip.py::bollinger_pct_b:77`, `zscore:104`, `_rsi_series:472`, `_macd_hist:502`, `macd_divergence:542`, `volume_dry_up:603`, `trigger_candle:661`, `vdu_entry_setup:747`, `support_structure:833`, `range_expansion_guard:1043` | %b, z, RSI series, MACD lines, divergence verdict, VDU ladder | `_rsi_series:472` and `_macd_hist:502` are private — the series the library's §55/§58 need exist but are not public |
| §94-§104 | `strategies/sector_breadth.py::multi_breadth:165`, `mcclellan_read:213`, `rrg_heading:286`, `msi_zone:307`; `strategies/sector_rank.py::_momentum:27`, `sector_standing:176`, `_acceleration:289`, `rrg_quadrant:370`, `rank_sectors_multifactor:391`, `rank_industry_group:600`, `constituent_breadth:664`, `leadership_ratio:684`, `sector_group_of:163`; `strategies/sector_screener.py::classify_regime:110`, `dispersion_trend:163`, `_rel_outperformance:248`, `setup_a:270`, `setup_b:318`, `constituent_universe:456`, `leadership_ratio_ewcw:535` | sector-level breadth (% >20/50/200d), McClellan/MSI, RRG, sector and industry ranks, constituent breadth, EW/CW leadership | **sector/ETF level only**; market-wide numeric breadth is ABSENT (`moomoo_extra_tools.get_market_breadth:98` → `dataflows/moomoo.py::get_market_breadth_moomoo:1932` returns text) |
| §105-§107, §108 | `strategies/regime.py::realized_vol:39`, `vol_percentile:59`, `choppiness:141`, `regime_label:194`; `strategies/regime_state.py::regime_trend:65`, `regime_vol_ratio:92`, `regime_drawdown:146`, `regime_state:215`; `strategies/regime_score.py::regime_score:265`; `agents/utils/analysis_tools.py::_regime_components:6598` | regime label/state/factor, vol percentile, choppiness, VIX9D/VIX3M term structure | **`RegimeScore` owns these** (`regime_score.py::regime_score:265`); MarketScore may read them only as a named dependency |
| §113, §115 | `strategies/short_interest.py::short_interest_percentile:35` | percentile of the latest settlement in the name's own series, `change_pct`, a stated direction | the module docstring states it is `SentimentScore.md`'s producer — reusing it here is a double-count |
| §108, §111, §112 | `strategies/options_surface.py::iv_percentile:15`, `iv_skew:25`, `put_call_oi_concentration:34`, `term_structure_slope:227`, `implied_move_pct:42`, `expected_move_from_chain:110`; `strategies/derivatives_gamma.py::gex_per_strike:52`, `gamma_regime:105`, `opex_status:166` | IV percentile, skew, put/call OI, term structure, expected move, GEX/OPEX | `RiskScore.md` §1 already reads `iv_percentile` and `implied_move_pct` |
| §121, §123 | `strategies/orderflow.py::institutional_net:45`, `retail_net:49`, `summarize:128`, `vpin:198`, `knife_guard_vpin:103`; `strategies/market_session.py::order_imbalance:281` | flow nets, distribution score, VPIN, imbalance | vendor-only (moomoo); degrades to neutral |
| §131-§134 | `strategies/score_engine.py::align:69`, `combine:134`, `coverage_floor:45`, `band_label:115`, `NON_MONOTONIC_INPUTS:41`; `strategies/factors.py::z_score:68`, `percentile_rank:59`, `quality_band:224`, `_coverage_floor:246`; `strategies/cross_section.py::winsorize:31`, `fit_winsorize:325`; `strategies/factor_expressions.py::cross_sectional_rank:268`, `fit_zscore:306`, `apply_zscore:317`, `apply_winsorize:335` | direction-aware ramp/band mapping, coverage floor, percentile/z normalisation, winsorisation | the normalisation layer the library's §131-§134 asks for **already exists** as the shared kernel |
| input basis for all of the above | `agents/utils/analysis_tools.py::_ohlcv:214` (→ `dataflows/stockstats_utils.py::load_ohlcv:254`), `_benchmark_closes:322`, `_benchmark_bars:333`, `_bench_ohlcv:1893` | one cached, look-ahead-filtered OHLCV series per ticker + the benchmark's bars | every price-derived library formula reads this series; no new fetch needed for §1-§107 |

**Anchor note.** The verified anchors above differ from several sibling docs'
(`swing.rsi` is `:44`, not `:39`; `value_dip.support_structure` is `:833`, not
`:714`; `volatility_models.parkinson_vol` is `:155`, not `:48`;
`book_risk.portfolio_drawdown` is `:118`, not `:100`). The code is the ground
truth; this document cites only what it read this round.

---

## 3. The smallest honest producer

Ranked by **value ÷ effort**, where value = how many library sections it makes
scorable and effort = new code + new fetches. Every input named here is already
fetched on the normal run path unless stated otherwise.

| # | Producer to build | Library sections it unlocks | Exact inputs | Supplied by |
| --: | --- | --- | --- | --- |
| 1 | **A MarketScore component list over the existing factor-expression vector** — a pure function that takes the already-computed dicts and returns `{"score", "components", "coverage"}` via `score_engine.combine:142` | §131-§136 (the composite + normalisation) | `alpha158_subset:373` output + the component values §1 already lists | `analysis_tools._ohlcv:214` (vendor chain `load_ohlcv:254`); no new fetch |
| 2 | **Cross-sectional percentile of a multi-horizon momentum blend** | §2, §12, §13, §103, §133 | closes (320 bars) per name + a peer panel | `_ohlcv:214`; panel from `get_company_peers_finnhub:380`/`peer_symbols:398`, or a caller list (as `get_cross_section_momentum:5106` does) |
| 3 | **The time-series vs cross-sectional momentum split, named** (MOP vs JT) | §2, §3, §14, §128 | the name's own 12-1 return + the panel's ranked returns | `momentum.momentum_12_1:358` (TS) and `cross_section.momentum_book:398` (CS) — **both already exist**; the work is naming, not maths |
| 4 | **Distance-from-52-week-high as a first-class field** | §6, §129 | highs, closes (252-bar window) | `factor_expressions._max_high:411` is the 20-bar form; `overlays.build_strategy_overlays:47` already computes a 52-week distance — promote it to a named output |
| 5 | **Relative strength vs the sector ETF** (one canonical field) | §10, §11, §13, §103 | the name's closes + the sector SPDR's closes | `relative_strength.relative_strength_report:214` (benchmark-agnostic) + `sector_rank.sector_group_of:163` + `_bench_ohlcv:1893` (ETF closes) |
| 6 | **Robust (MAD) z + winsorisation, wired to the percentile transform** | §132 | any factor vector | `cross_section.winsorize:31`, `factor_expressions.apply_zscore:317`; the MAD form itself is new (~10 lines) |
| 7 | **Market-wide numeric breadth** (advance/decline, %>50d/%>200d for the US universe) | §94-§102 | constituent closes for the universe | `sector_breadth.multi_breadth:165` already accepts `{name: closes}`; `sector_screener.constituent_universe:456` builds the maps — the work is aggregating across sectors instead of per-sector |
| 8 | **A numeric ADV / dollar-volume producer** | §34, §35, §36, §125 | closes + volumes | `_ohlcv:214`; today ADV is only an argument to `liquidity_risk.float_turnover:53` and `days_to_absorb:103` |
| 9 | **Beta compression / correlation regime** | §89, §93 | returns + benchmark returns, two windows | `evaluate.rolling_beta:939` and `statistical.correlation_matrix:203` exist; only the difference/short-minus-long is new |
| 10 | **Bollinger bandwidth series + percentile** | §52, §53 | closes | `value_dip.bollinger_pct_b:77` already computes the bands; return the width |
| 11 | **Conditional deviation vs semivariance, labelled** | §17, §18, §74, §76 | the run's return series | `factor_expressions._side_vol:437` is the conditional form; the **semivariance** producer is `TechnicalScore.md` §1/§4's (`volatility_models`), read as a dependency — never re-derived here |
| 12 | **Market-wide short-interest / squeeze block** | §113-§116 | settlement series + float + ADV | `market_position_tools.get_short_interest:220` (vendor) + `short_interest.short_interest_percentile:35` — **owned by `SentimentScore.md`**; build here only if §7 Q5 resolves that way |

**Not worth building first:** §77/§78 (MAE/MFE — execution-adjacent, the library
itself defers them), §109 (variance risk premium — needs a matched IV/RV pair
neither surface guarantees), §122 (quote imbalance — needs L2 data the repo does
not fetch), §116 (squeeze — the library's own `f(...)` is unspecified).

---

## 4. What the evidence says

Every source below was fetched this round; the URL is the one fetched.

- **Cross-sectional momentum exists and is not explained by systematic risk.**
  Jegadeesh & Titman (1993), *Journal of Finance* 48(1):65-91, find that buying
  3-12-month winners and selling losers earned significant positive returns in
  NYSE/AMEX 1965-1989, that the profits are not due to systematic risk or delayed
  reaction to common factors, and that part of the abnormal return dissipates in
  the following two years.
  <https://ideas.repec.org/a/bla/jfinan/v48y1993i1p65-91.html>
  **Where the library differs:** §2 blends 1/3/6/12-month momentum with fixed
  weights `w₁…w₄` and §3 builds 12-1 by skipping the most recent month; JT's
  construction is a **cross-sectional decile rank** with a 1-month skip and a
  3-12-month holding period. The library's §2 is a *time-series* blend (the
  name's own past return) — it is the TSMOM object, not JT's. §12 (percentile
  rank) is the JT-shaped one.
- **Time-series momentum is a distinct signal from cross-sectional momentum.**
  Moskowitz, Ooi & Pedersen (2012), *Journal of Financial Economics* 104(2),
  document positive predictability from an instrument's **own** past 12-month
  return across 58 futures/forwards, persisting ~1 year then partially reversing,
  and state explicitly that this is "related to, but different from" the
  cross-sectional momentum literature.
  <https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum>
  **Where the library differs:** §2/§3 compute the TSMOM input but never rank it
  against a universe, and §12-§14 compute the CSMOM ranks without stating that
  the two are different signals. `TechnicalScore.md`'s appendix already names
  this distinction; this library does not.
- **The 52-week-high effect dominates past returns.** George & Hwang (2004),
  *Journal of Finance* 59(5):2145-2176: nearness to the 52-week high "dominates
  and improves upon the forecasting power of past returns (both individual and
  industry returns)", and its forecast "does not reverse in the long run".
  <https://doi.org/10.1111/j.1540-6261.2004.00695.x>
  **Where the library differs:** §6.1 defines the *gap* `P/High₂₅₂ − 1` (0 at the
  high, negative below) while George & Hwang's measure is a **ratio** `P/High`
  used as a cross-sectional rank — sign-flipped and unranked in the library.
- **High maximum daily returns predict low returns (the lottery/MAX effect).**
  Bali, Cakici & Whitelaw (2011), *Journal of Financial Economics* 99(2):427-446:
  a negative, significant relation between MAX (the maximum daily return over the
  past month) and expected returns, with >1%/month between extreme deciles,
  robust to size, book-to-market, momentum, reversals, liquidity and skewness —
  and including MAX reverses the idiosyncratic-volatility puzzle.
  <https://ideas.repec.org/a/eee/jfinec/v99y2011i2p427-446.html>
  **Where the library differs:** the library's volatility family (§15-§22) is
  built on **magnitude**, with no MAX term at all. The repo already ships the
  screen (`strategies/lottery.py::lottery_verdict:88`, `idiosyncratic_vol:51`,
  leaf `get_lottery_factors:11201`) — so the library's §15/§18 direction column
  is in tension with a screen the repo has.
- **High idiosyncratic volatility and high beta predict low returns.** Ang,
  Hodrick, Xing & Zhang (2006), *Journal of Finance* 61(1):259-299: stocks with
  high sensitivities to aggregate-volatility innovations, and stocks with high
  idiosyncratic volatility, have low average returns not explained by size,
  book-to-market, momentum or liquidity.
  <https://ideas.repec.org/a/bla/jfinan/v61y2006i1p259-299.html>
  **Where the library differs:** §90 computes `Std(ε)` as a *descriptor*; the
  paper's use is a **cross-sectional sort with a directional prediction**
  (high → low). The library's §134 direction table lists "Volatility — lower =
  better" but §90/§89 carry no direction.
- **The low-volatility anomaly is an arbitrage-limits phenomenon.** Baker,
  Bradley & Wurgler (2011), *Financial Analysts Journal* 67(1):40-54.
  <https://doi.org/10.2469/faj.v67.n1.4>
  **Where the library differs:** the library's §19/§20 treat *expanding*
  volatility as neutral information; BBW's argument is that the anomaly persists
  because benchmark-constrained managers cannot underweight it — which is a
  reason to print volatility as **risk-increasing**, not as a coin flip.
- **Size and book-to-market capture the cross-section, and β is flat.** Fama &
  French (1992), *Journal of Finance* 47(2):427-465: size and book-to-market
  combine to capture the variation associated with β, size, leverage, B/M and
  E/P, and "the relation between market β and average return is flat".
  <https://doi.org/10.1111/j.1540-6261.1992.tb04398.x> The three-factor model
  that formalises it: Fama & French (1993), *Journal of Financial Economics*
  33(1):3-56 <https://doi.org/10.1016/0304-405X(93)90023-5>; the five-factor
  extension adds profitability and investment: Fama & French (2015), *Journal of
  Financial Economics* 116(1):1-22
  <https://doi.org/10.1016/j.jfineco.2014.10.010>.
  **Where the library differs:** §23-§25 use β and CAPM α as the market-sensitivity
  and skill measures, and §89 treats β regimes as informative. FF's result is
  that β's *cross-sectional* price of risk is flat once size/value are included —
  so a MarketScore that weights β/α heavily is weighting a factor the evidence
  says carries no cross-sectional premium on its own.
- **Illiquidity is priced.** Amihud (2002), *Journal of Financial Markets*
  5(1):31-56.
  <https://doi.org/10.1016/S1386-4181(01)00024-6>
  **Where the library differs:** §36 defines ILLIQ exactly as Amihud does
  (`(1/N)Σ|R_t|/DollarVolume_t`, "higher means less liquid") and then adds
  `LiquidityScore = −ILLIQ` — a sign flip with **no scale**, which the library's
  §134 then has to re-invert again. The repo's producer is
  `liquidity_risk.amihud_illiquidity:71`.
- **The factor zoo is a multiple-testing problem.** Harvey, Liu & Zhu (2016),
  *Review of Financial Studies* 29(1):5-68, argue that with hundreds of tested
  factors the appropriate t-statistic hurdle is far above 2.
  <https://doi.org/10.1093/rfs/hhv059> And McLean & Pontiff (2016), *Journal of
  Finance* 71(1):5-32, measure the out-of-sample decay: portfolio returns 26%
  lower out-of-sample and 58% lower post-publication across 97 predictors.
  <https://doi.org/10.1111/jofi.12365>
  **Where the library differs — and this is the load-bearing one:** the library
  offers **282 display formulas** across 140 sections. Its own §140 answers this
  ("I would not implement all ~130 calculations as independent votes … raw
  indicators → correlated-indicator clusters → factor subscores → MarketScore")
  and §131-§134 supply the normalisation. The evidence says the **cluster count**,
  not the formula count, is what a weight vector may be built on: HLZ's hurdle and
  McLean & Pontiff's decay are exactly the penalty for treating correlated
  variants of one signal as independent evidence.

**Not fetched, therefore not cited:** any primary source for the momentum-crash
literature (Daniel & Moskowitz), Patton & Sheppard's semivariance decomposition,
and Faber's trend-filter study — `TechnicalScore.md`'s appendix already carries
those three, and this round's fetches were restricted to the list above.

---

## 5. The composite

Nothing here is implemented. The design constraints, in the order they bind:

1. **One pure function over existing numbers.** A module at
   `strategies/market_score.py` (**proposed path; nothing exists there today**)
   taking the already-computed component dicts (every input is the run's OHLCV,
   `analysis_tools._ohlcv:214`) and returning
   `{"score": 0-100 | None, "components": [...], "coverage": {...}}` through the
   shared kernel `score_engine.combine:142`. **No new fetch.**
2. **The kernel, not a copy.** `combine` renormalises over the present components
   (`Σ w_i·v_i / Σ w_i for present i`), reports `coverage = Σ w present / Σ w
   total`, and **withholds** the score below `coverage_floor(min_coverage, n)`
   with its reason (`score_engine.coverage_floor:53`; `score = None`, never 0 and
   never 50). `align:61` maps a raw value to a 0-100 contribution in the
   favourable direction via a two-sided ramp or the producer's own band table, and
   refuses to invent a neutral value. `NON_MONOTONIC_INPUTS:41` already names the
   eight band-mapped inputs (rsi, mfi, stochastic, stochrsi, rsi2, williams_r,
   bollinger_pct_b, elder_thermometer).
3. **The library's own §131-§137 pipeline, adopted as written:** raw indicator →
   correlated-indicator cluster → factor subscore → score. The library's nine
   subscore names (`MomentumScore`, `TrendScore`, `RelativeStrengthScore`,
   `VolumeScore`, `VolatilityScore`, `LiquidityScore`, `MeanReversionScore`,
   `MarketRegimeScore`, `RiskAdjustedScore`, §135) are the natural component list,
   **subject to §7 Q1** — five of the nine are `TechnicalScore`'s built
   categories.
4. **A proposed gate name: `enable_market_score`** — proposed, **not added to any
   code or config.** It would enter `quant_scorecard.ENGINE_GATES:78` the same way
   the other eight do, and the leaf would be reached as **scorecard text** under
   `enable_quant_scorecard`, not as a tool: `agents/toolsets.py::market_tools:230`
   documents that no score-engine leaf is bound to the market analyst
   (`report_hygiene.scorecard_context_block:253` is how an engine's number
   reaches a model).
5. **A proposed research-allocation weight: 7.5%, carved from `TechnicalScore`
   (20% → 12.5%), leaving the six-engine total at 100%.** This is a **proposal,
   not a decision and not a config change.** The arithmetic is the constraint: the
   owner's staged allocation (`README.md` §1.4) is Fundamental 35 / Technical 20 /
   Regime 15 / Risk 15 / News 7.5 / Sentiment 7.5 = 100%, so a seventh weighted
   engine cannot be added without removing weight from an existing one — and
   given §0.2, the engine that currently owns MarketScore's factor families is
   `TechnicalScore`. If §7 Q1 resolves the other way (TechnicalScore keeps
   momentum/RS/volatility), the honest weight is **0% until the engine's own
   factor set exists**, because a MarketScore that reads TechnicalScore's inputs
   is a second vote, not a new one.
6. **Its own band table, advisory.** Per master rule 2, nothing feeds
   `decision_guardrail.SCORE_BANDS:27`. MarketScore gets its own labels, and they
   are labels — never a gate, never a size.
7. **Coverage, freshness and confidence stay separate outputs.** The library's
   §140 output block prints `MarketCoverage`, `MarketDataFreshness`,
   `MarketFactorAgreement`, `MarketConfidence` **beside** the score, and its own
   sentence is the rule: *"a stock can have a high MarketScore but low confidence
   … You don't want missing data to silently turn into a neutral 50"*. That is
   master rule 1 (`NA ≠ 0`) stated in the library's own words.
8. **Nothing here sizes anything.** No touch of the executor's sizing path
   (`../TradingExecution/signald/risk/sizing.py:101`, fail-closed) or the repo's
   `size.composite_position_size:70`; the score may be printed beside a size,
   never as one.

### 5.1 What the score may be used for, and what it may not

| May | May not |
| --- | --- |
| a printed advisory block beside the market evidence | override a hard gate (`GATE_PRECEDENCE`, `../TradingExecution/signald/contracts.py:42`) |
| an attribution row ("which factor moved") | feed `decision_guardrail.SCORE_BANDS` |
| an input to Phase C research work (IC/decile/coverage rows) | set or scale a position |
| a cross-sectional context line ("leaders are outrunning laggards", with the panel size printed) | be quoted as a forecast, or as market breadth when the panel is nine names |

---

## 6. Verification requirements

What a future implementation must prove before any part of it may be called
built. These are the master's §6 requirements instantiated for this engine.

1. **The boundary is tested, not asserted.** A test asserts that no MarketScore
   component re-derives a `TechnicalScore` component (momentum 18%, relative
   strength 12%, volatility 5%, breadth 5%) or a `RegimeScore` leg — i.e. each
   MarketScore component names a producer that is *not* the corresponding
   `technical_score.py`/`regime_score.py` input, or is marked a stated dependency.
2. **Direction is tested at the producer's own edges.** The eight
   `NON_MONOTONIC_INPUTS:41` rows must move the right way at the producer's band
   edges (RSI 45-70 must not score below RSI 80); the volatility family must not
   be mechanically inverted (`TechnicalScore.md` §7 Q4 decided no blanket
   inversion).
3. **`NA ≠ 0`, tested from both sides.** A component dict with one factor missing
   drops `coverage` by that factor's weight and moves the score toward the mean of
   the *available* factors — never toward 0 and never toward 50. A missing factor
   never enters the denominator as a zero.
4. **A no-data run returns `None`** with the floor in the reason — never 0, never
   50 (`score_engine.combine:142`).
5. **Reproducibility.** A reader recomputing `Σ w·s / Σ w` from the printed
   attribution block must get the printed score to within rounding, and the
   printed raw value with its units and sign must sit beside each aligned
   contribution (master §1.2).
6. **The units are pinned and printed** (§0.3): one test feeds the §10 difference
   and the §11 ratio for the same pair and asserts they are labelled as different
   quantities; one asserts `RV` is annualized before it is compared to `σ_annual`;
   one asserts the downside leg is labelled *conditional deviation* and does not
   claim `RS⁻ + RS⁺ = RV`.
7. **The score never reaches a gate.** A test asserts the value appears in no
   `GATE_PRECEDENCE` check, no `risk_multiplier` input, and no sizing path.
8. **The cross-section is honest.** Any percentile field prints its panel size
   and refuses the percentile below a stated floor (the `get_cross_section_momentum:5106`
   pattern: "the printed panel size is part of the read").
9. **Redundancy is measured before weights are trusted.** Pairwise correlation of
   the component sub-scores over the EODHD panel, reported before any weight
   vector is treated as real (the library's own §138 is the reason).

---

## 7. OPEN questions for the owner

1. **The `TechnicalScore` boundary — first, because it decides the rest.** The
   built engine already owns Trend 20 / Momentum 18 / Relative strength 12 /
   Volatility 5 / Breadth 5 (`TechnicalScore.md` §0.2), while both libraries'
   preambles (`market_score.md:1-4`, `technical_score.md:1-3`) assign momentum,
   relative strength and volatility to MarketScore. Which reading governs? Options
   the owner can pick from, with the consequence of each: **(a)** TechnicalScore
   keeps them and MarketScore is built from §36/§79-§93/§108-§124 only (a
   liquidity/distribution/flow engine); **(b)** MarketScore takes momentum, RS and
   volatility and TechnicalScore drops to indicators/setup patterns, which
   re-opens `TechnicalScore.md`'s own §0.2 weights and its Phase C measurements;
   **(c)** both read the same producers with MarketScore as the *factor-exposure*
   view and TechnicalScore as the *setup* view — permitted only if every shared
   producer is named as a stated dependency and neither re-derives the other's
   number (master rule 3). This document does not resolve it.
   **[ANSWERED 2026-09-26 by the owner: three separate engines, none above the
   others, each with a stated question it answers.** `TechnicalScore` = *"what is
   this security doing?"* — RSI, MACD, stochastic, Bollinger %B, ATR, ADX, moving-
   average distance and crossover, price and volume momentum, price structure,
   breakouts, support/resistance, trend strength, **the security's own relative
   momentum**. `MarketScore` = *"what is the market doing around this security?"* —
   index trend and momentum, **market and sector breadth**, advance/decline, new
   highs/lows, market volatility, credit conditions, market liquidity, cross-asset
   confirmation, **index relative strength**, market participation. `RegimeScore`
   = *"what statistical/economic state is the environment in?"* — bull/bear,
   volatility, risk-on/off, liquidity, inflation, growth, monetary-policy,
   correlation, trend and crisis regimes. The owner's words: *"the three scores can
   therefore legitimately all be bullish without being duplicates."* **This is a
   reading (a)-shaped resolution with one addition** — `TechnicalScore` keeps its
   built categories (`Trend 20 / Momentum 18 / RS 12 / Volatility 5 / Breadth 5`,
   unchanged), and `MarketScore` is built from the *market-around-the-name* rows
   so its momentum, RS and breadth are index- and market-level rather than the
   security's own. The invariant-8 reading is the owner's D2 rule applied here too:
   where a producer is genuinely shared (`market_breadth`), it is **computed once
   and read twice**, with each reader's dependency named. `MASTER_PLAN.md` §2.1.]**
2. **Breadth and the market regime: MarketScore or `RegimeScore`?** The library's
   own §139 gives breadth and market regime to MarketScore *and* the breadth
   regime, correlation regime and VIX regime to RegimeScore. `RegimeScore` is
   built (`regime_score.py::regime_score:265`) and owns the market-wide
   environment; a market-wide breadth producer (missing today, §94-§102) would be
   its sixth/seventh leg. Which engine owns it?
   **[ANSWERED 2026-09-26: `MarketScore` owns market-wide breadth** (its §94-§102
   rows are the scoring dimension); `RegimeScore` keeps the breadth *regime* as a
   **state** input over the same producer. One producer, two readers — the same
   rule the owner stated for valuation (*"calculate it once, attribute it twice"*).
   `regime_score.breadth` is not moved and not duplicated.]**
3. **Does MarketScore implement the 140-section library or a clustered subset?**
   The library answers its own question (§140: clusters, not ~130 independent
   votes) and then lists 140 sections. Is the acceptance criterion "every section
   in §1 is either built or explicitly declared out of scope", or "the nine
   subscores exist"? Without this, "built" is unfalsifiable.
4. **What is the cross-sectional universe, and what is the floor?** §12, §13,
   §103, §131-§133 need a panel. `get_cross_section_momentum:5106` falls back to
   the ticker + ≤8 vendor peers (`peer_symbols:398`). A percentile over nine names
   is not a percentile, and the repo's own pattern is to label the panel size
   (`INSUFFICIENT_CROSS_SECTION`, `IMPLEMENTATION_PLAN.md:1282`). What is the floor —
   an index membership list, the vendor peer set, or a caller-supplied panel?
5. **Short interest, IV percentile, insider flow and gap: whose?** `short_interest.py`
   is `SentimentScore.md`'s producer; `options_surface.iv_percentile:15` and
   `implied_move_pct:42` are read by `RiskScore.md` §1; insider activity is
   EventScore's family (§118 says so itself); gaps are RiskScore's gap-risk 10%.
   Does MarketScore consume them as stated dependencies, or drop those sections?
6. **Per-name, market-wide, or both?** Most of the library is per-name; §94-§118
   are market-wide (breadth, regime, VIX, put/call, short interest, microstructure).
   `RiskScore.md` Q2/Q5 resolved the analogous question by giving the book-level
   computations to the executor and keeping the engine per-security. The same
   contract question applies here, and it is a contract decision, not a modelling
   one.
7. **Weight and gate: is MarketScore research-only, or a composite participant?**
   §5.5 proposes 7.5% carved from TechnicalScore; the alternative is 0% (research
   attribution only, like `NewsScore`/`SentimentScore`). And is
   `enable_market_score` wanted at all, or should the engine stay behind
   `enable_quant_scorecard` alone?
8. **Which of the three unit conventions in §0.3 does the owner want pinned?**
   §10 difference vs §11 ratio for relative strength; annualized `√(252·Σr²)` vs
   the window sum for realized volatility; conditional `Std(r \| r<0)` vs the
   semivariance leg. The document proposes the first of each pair, printed beside
   the raw value — but these are the numbers a reader will compare across engines.

---

## Appendix — the library's sections, verbatim

Section titles as they appear in `Strategies/scores/market_score.md`; the line
number is the `# N. Title` header line (file is 2,885 lines). Formula counts are
in §1.

| § | Line | Title |
| --: | --: | --- |
| 1 | 9 | Return calculations |
| 2 | 67 | Multi-horizon momentum |
| 3 | 104 | Momentum excluding the most recent month |
| 4 | 121 | Momentum acceleration |
| 5 | 155 | Trend calculations |
| 6 | 242 | Distance from high/low |
| 7 | 289 | Drawdown |
| 8 | 317 | Drawdown recovery |
| 9 | 336 | Time-under-water |
| 10 | 356 | Relative strength vs benchmark |
| 11 | 383 | Relative strength ratio |
| 12 | 403 | Relative momentum percentile |
| 13 | 423 | Sector-relative momentum |
| 14 | 448 | Risk-adjusted momentum |
| 15 | 470 | Volatility |
| 16 | 491 | Realized volatility |
| 17 | 511 | Downside volatility |
| 18 | 531 | Upside volatility |
| 19 | 543 | Volatility ratio |
| 20 | 566 | Volatility acceleration |
| 21 | 575 | ATR |
| 22 | 604 | ATR expansion |
| 23 | 614 | Beta |
| 24 | 633 | Rolling beta |
| 25 | 652 | Alpha |
| 26 | 672 | Information ratio |
| 27 | 698 | Tracking error |
| 28 | 707 | Sharpe ratio |
| 29 | 727 | Sortino ratio |
| 30 | 737 | Calmar ratio |
| 31 | 747 | Gain/loss ratio |
| 32 | 757 | Hit rate |
| 33 | 767 | Up/down capture |
| 34 | 787 | Volume calculations |
| 35 | 828 | Dollar volume |
| 36 | 846 | Liquidity |
| 37 | 883 | Price-volume relationship |
| 38 | 900 | Volume confirmation |
| 39 | 925 | On-Balance Volume |
| 40 | 946 | OBV divergence |
| 41 | 971 | Accumulation/distribution |
| 42 | 995 | Chaikin Money Flow |
| 43 | 1005 | Money Flow Index |
| 44 | 1034 | VWAP |
| 45 | 1051 | VWAP slope |
| 46 | 1061 | Price efficiency |
| 47 | 1089 | Trend persistence |
| 48 | 1122 | Consecutive return streak |
| 49 | 1136 | Mean reversion |
| 50 | 1157 | Return z-score |
| 51 | 1167 | Bollinger position |
| 52 | 1187 | Bollinger bandwidth |
| 53 | 1197 | Bollinger bandwidth percentile |
| 54 | 1208 | RSI |
| 55 | 1233 | RSI momentum |
| 56 | 1242 | RSI divergence |
| 57 | 1274 | MACD |
| 58 | 1295 | MACD momentum |
| 59 | 1304 | Stochastic oscillator |
| 60 | 1319 | Rate of change |
| 61 | 1330 | Average Directional Index |
| 62 | 1373 | Directional bias |
| 63 | 1389 | Ichimoku calculations |
| 64 | 1428 | Breakout calculations |
| 65 | 1446 | Breakout strength |
| 66 | 1456 | Breakout volume confirmation |
| 67 | 1473 | Gap calculations |
| 68 | 1492 | Gap fill |
| 69 | 1504 | Intraday strength |
| 70 | 1522 | Close location value |
| 71 | 1538 | Candle body strength |
| 72 | 1548 | Upper/lower wick ratios |
| 73 | 1564 | Range expansion |
| 74 | 1578 | Volatility-adjusted return |
| 75 | 1594 | Sharpe-like momentum |
| 76 | 1605 | Downside-adjusted momentum |
| 77 | 1615 | Maximum adverse excursion |
| 78 | 1630 | Maximum favorable excursion |
| 79 | 1645 | Tail risk |
| 80 | 1671 | Skewness |
| 81 | 1681 | Kurtosis |
| 82 | 1697 | Return distribution stability |
| 83 | 1713 | Autocorrelation |
| 84 | 1727 | Partial autocorrelation |
| 85 | 1737 | Hurst exponent |
| 86 | 1769 | Variance ratio |
| 87 | 1795 | Trend-to-noise ratio |
| 88 | 1807 | Fractal dimension |
| 89 | 1827 | Market beta regimes |
| 90 | 1852 | Idiosyncratic volatility |
| 91 | 1872 | Residual momentum |
| 92 | 1892 | Market correlation |
| 93 | 1912 | Correlation regime |
| 94 | 1925 | Market breadth |
| 95 | 1941 | Advance/decline ratio |
| 96 | 1951 | Advance/decline line |
| 97 | 1962 | Breadth percentage |
| 98 | 1978 | Percent above moving average |
| 99 | 2000 | New-high/new-low breadth |
| 100 | 2017 | Volume breadth |
| 101 | 2039 | Breadth thrust |
| 102 | 2051 | Sector breadth |
| 103 | 2065 | Sector-relative performance |
| 104 | 2081 | Industry-relative performance |
| 105 | 2090 | Market regime return |
| 106 | 2118 | Market trend regime |
| 107 | 2132 | Volatility regime |
| 108 | 2142 | Volatility term structure |
| 109 | 2160 | Realized vs implied volatility |
| 110 | 2178 | Implied volatility percentile |
| 111 | 2188 | IV percentile |
| 112 | 2198 | Put/call ratios |
| 113 | 2218 | Short interest |
| 114 | 2228 | Days to cover |
| 115 | 2238 | Short-interest change |
| 116 | 2247 | Short squeeze pressure |
| 117 | 2266 | Institutional ownership change |
| 118 | 2278 | Insider transaction pressure |
| 119 | 2298 | Market microstructure |
| 120 | 2318 | Effective spread |
| 121 | 2335 | Order imbalance |
| 122 | 2345 | Quote imbalance |
| 123 | 2355 | VPIN-style order-flow toxicity |
| 124 | 2369 | Market impact |
| 125 | 2395 | Liquidity-adjusted momentum |
| 126 | 2412 | Volatility-adjusted relative strength |
| 127 | 2422 | Relative Sharpe |
| 128 | 2432 | Momentum consistency |
| 129 | 2450 | Multi-horizon trend agreement |
| 130 | 2464 | Multi-factor market score |
| 131 | 2539 | Factor normalization |
| 132 | 2558 | Robust normalization |
| 133 | 2577 | Percentile transformation |
| 134 | 2595 | Direction normalization |
| 135 | 2623 | Market factor subscores |
| 136 | 2671 | Composite MarketScore |
| 137 | 2692 | A practical initial weighting |
| 138 | 2715 | The important part for your system: don't double-count |
| 139 | 2757 | Recommended separation in your architecture |
| 140 | 2822 | The MarketScore I'd actually build for your application |

**Provenance note (added 2026-09-26):** this document is the design account of a
library that has **no code**. Nothing in it may be quoted as built, measured or
weighted; §1's `elsewhere` rows are statements about *existing producers the
library would reuse*, not about MarketScore.
