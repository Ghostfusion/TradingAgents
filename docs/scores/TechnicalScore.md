# TechnicalScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master —
architecture, cross-engine rules, the composite, the code defects, the phase plan,
the open questions). Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`RegimeScore.md`](RegimeScore.md), [`NewsScore.md`](NewsScore.md),
[`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
[`RiskScore.md`](RiskScore.md),
[`MarketScore.md`](MarketScore.md), [`ValuationScore.md`](ValuationScore.md).

**Scope: the technical engine only.** It designs `TechnicalScore` — *"what is
this stock doing?"* — from the owner's nine categories in
[`../ScoreWeight/market.md`](../ScoreWeight/market.md). The environment the stock
trades in is `RegimeScore`; how much the position can hurt is `RiskScore`. This
document must not absorb either.

Status: **built (2026-09-18); gate off by default.** `strategies/technical_score.py` is the engine (40 components over 9 categories), `get_technical_score` is its leaf and `enable_technical_score` its membership switch. The composite §0.1 said existed nowhere is `technical_score`, and the price leg is the **one engine whose inputs were measured** - 30 panel dates, `MEASUREMENT_FINDINGS.md`.

---

## 0. What this engine answers, and what exists

### 0.1 No composite technical score exists — re-verified

The claim "there is no `TechnicalScore` today" is a grep result, not an
impression. Searched across all three trees (`TradingAgents`, `TradingExecution`,
`trading_web`) for `technical.?score|tech_score|technical_score|TechnicalScore`:

- `TradingExecution` and `trading_web`: **zero matches**.
- `TradingAgents`: only prose in design documents and the CHANGELOG.
- `trend_score`: `agents/utils/analysis_tools.py:9247` — a **tool argument the
  model supplies**, not a producer. The live tool-call logs show model-authored
  values (`ToolCallLog/MSFT_tool_calls.jsonl:187` = 72).
- The only 0-100 producers in the repo are fundamental or structural:
  `factors.category_scores`, `capex_quality`, `data_quality.aggregate_quality`,
  `news_relevance.score_news_article`, `sector_rank.rank_sectors_multifactor:391`
  (sector-ETF level) and `decision_guardrail.SCORE_BANDS:27`. **None is
  technical.**
- Nearest technical-adjacent numbers, each explicitly *not* a technical
  composite: `knife_guard.knife_score:159` (K, higher = **worse**),
  `regime_state.regime_trend:65` (a trend leg in ATR units, owned by
  RegimeScore), `quant_baseline.quant_signal:74` (≈[-1, 1], **unwired**, a
  whitelisted legacy factor composite).

So the composite is a **new aggregation of existing numbers**, not a rename of
something that exists.

### 0.2 The owner's weight table

| Category | Weight |
| --- | --: |
| Trend | **20%** |
| Momentum | **18%** |
| Relative strength | **12%** |
| Price structure / support-resistance | **12%** |
| Volume / accumulation | **10%** |
| Breakout / pullback | **10%** |
| Mean reversion | **8%** |
| Volatility / ATR | **5%** |
| Breadth / participation | **5%** |

### 0.3 The direction problem this engine has to solve first

Six of the owner's named inputs are **non-monotonic**: a naive
"higher = more favourable" mapping inverts them, and the engine's own consumers
already disagree about which end is good. Confirmed by reading the producers, not
assumed:

| Input | Producer | Why higher is not better |
| --- | --- | --- |
| RSI | `swing.rsi:44` + `swing.rsi_band:123` | 45-70 is `strong`, >70 is `hot`, <40 is `broken` — a **band**, not a ramp |
| Stochastic K/D | `technical_factors.stochastic_oscillator:197` | <20 is `oversold`, the dip read |
| StochRSI | `technical_factors.stoch_rsi:374` | <0.2 is the entry |
| RSI2 | `technical_factors.rsi2:406` | <10 is the buy |
| Williams %R | `technical_factors.williams_r:429` | -80..-100 is oversold |
| Bollinger %b | `value_dip.bollinger_pct_b:77` | <=0 is the dip, >1 is extended |
| MFI | `technical_factors.mf_index:163` | >80 is overbought |
| Elder thermometer | `technical_factors.elder_thermometer:649` | `quiet` (<0.8) is the good dip read |
| Keltner %b | `technical_factors.keltner_channel:440` | mid-band is the read |
| Support structure | `value_dip.support_structure:833` | *near* the 200-SMA is good, while `swing.trend_architecture:76` says *above* it is good — the same level, opposite signs, depending on the strategy |

**Design consequence: the composite never maps a raw indicator through a ramp.**
Every non-monotonic input is **band-mapped** (a piecewise table with the bands
the producer itself uses) and the mapping is printed beside the raw value. This is
the same rule the master states for risk conventions (§1.2), and it is the single
biggest correctness risk in this engine.

### 0.4 What this engine must not claim

Technical momentum is **not** an unconditional positive. The literature is
explicit that momentum has its own tail-risk profile (momentum crashes
concentrate in panic-and-rebound states) and that trend, moving-average rules and
time-series momentum harvest **one latent factor**, not three. Two consequences
that constrain the design:

1. **`TechnicalScore` is a state description, not a forecast.** A high score in a
   crash-prone tape is not a buy signal; the regime and risk engines exist
   precisely to say so.
2. **The redundancy step is mandatory, not cosmetic.** Trend (20%) + momentum
   (18%) + relative strength (12%) = 50% of the weight on inputs that are
   correlated by construction. Phase C measures the redundancy before any of
   these weights are treated as real.

---

## 1. Component ledger

Engine = TechnicalScore (owner's staged weights). Direction column: `+` = higher is favourable for a long; `NON-MONO` = the producer's own consumers treat a MID or LOW value as good, so a naive higher-is-better mapping inverts it.

| Component | Weight | Status | Producer (`module.function:line`) | Output key | Direction | Scale/units | Gap |
| --- | --: | --- | --- | --- | --- | --- | --- |
| **Trend** | 20 | **PARTIAL** | no composite; `swing.trend_architecture:76` (booleans) + `regime_state.regime_trend:65` | `architecture.*` / `race.trend.score` | + | flags + context string / (EMA20-EMA50)/ATR14 | no 0-100 scale, no weighting basis |
| Trend → price vs SMA20/50/100/200 | — | PARTIAL | `swing.trend_architecture:76` computes SMA50, SMA200, EMA20 only | `above_sma50`, `above_sma200` | + | bool | SMA20, SMA100 ABSENT |
| Trend → EMA10/20/50 | — | SCORABLE | `technical_factors.ema:40` (public, any n); `swing._ema_last:34` (n=20); `momentum.ema9:38` | EMA series / `ema9` | + | price units | no leaf prints EMA10/EMA50 |
| Trend → SMA slope | — | SCORABLE | `swing.trend_architecture:76` (`sma50_rising` = 5-bar, `sma200_rising` = 15-bar) | `sma50_rising`, `sma200_rising` | + | bool | windows hardcoded inside the function |
| Trend → EMA slope | — | **ABSENT** | — | — | + | — | grepped `def .*slope` in `strategies/` → only `relative_strength.slope_pct:49`, `sector_screener.classify_regime:110`, `options_surface.term_structure_slope:227` |
| Trend → SMA50 > SMA200 stack | — | SCORABLE | `swing.trend_architecture:76` (`stacked`, `ema20_above_sma50`) | `stacked` | + | bool | — |
| Trend → golden-cross state | — | SCORABLE | `extended_indicators.golden_death_cross:55` | `golden`,`death`,`label` | + | bool/label | 2-bar crossover only (no "state" memory) |
| Trend → ADX | — | SCORABLE | `technical_factors.adx:230` | `adx` | + (>25 strong) | 0-100 | no percentile basis |
| Trend → DI+ / DI- | — | SCORABLE | `technical_factors.adx:230` | `di_plus`,`di_minus` | + (di+) | 0-100 | — |
| Trend → Aroon up / down | — | SCORABLE | `technical_factors.aroon:668` | `aroon_up`,`aroon_down` | + (up) | 0-100 | Aroon OSCILLATOR not computed; a `verdict` string substitutes |
| Trend → Ichimoku cloud state | — | SCORABLE | `extended_indicators.ichimoku:80` | `above_cloud`,`label`,`cloud_leading` | + | bool/label | — |
| Trend → regime trend score | (overlap) | SCORABLE | `regime_state.regime_trend:65` | `score` | + | (EMA20-EMA50)/ATR14, dimensionless | belongs to RegimeScore — naming clash per ground rule 3 |
| Trend → trend filter | — | SCORABLE | `quant_baseline.trend_strength:28` | — | + | 0-1 | UNWIRED (tests only) |
| **Momentum** | 18 | **PARTIAL** | no composite; inputs spread across 5 modules | — | + | — | no aggregation, mixed units |
| Momentum → RSI | — | SCORABLE | `swing.rsi:44` | `rsi.value`,`rsi.label` | **NON-MONO** (45-70 `strong`, >70 `hot`, <40 `broken`) | 0-100 | — |
| Momentum → RSI slope | — | **ABSENT** | — | — | — | — | `swing.rsi:44` returns a scalar; `swing.rsi_band:123` bands it but never differentiates |
| Momentum → MACD line | — | PARTIAL | `value_dip._macd_hist:502` (private) | — | + | price units | no public/leaf producer; only the vendor `get_indicators('macd')` text |
| Momentum → MACD histogram | — | PARTIAL | `value_dip._macd_hist:502`, surfaced only via `value_dip.macd_divergence:542` | `macd_hist_lows` | + | price units | the VALUE is never returned, only two trough lows |
| Momentum → MACD histogram slope | — | **UNWIRED** | `rule_eval.rule_signal_macd_hist_rising:103` | bool | + | bool | only reader is `scripts/rule_eval.py:24` + tests; no leaf |
| Momentum → Stochastic K/D | — | SCORABLE | `technical_factors.stochastic_oscillator:197` | `k`,`d` | **NON-MONO** (<20 `oversold` = good for a dip) | 0-100 | — |
| Momentum → ROC | — | SCORABLE | `extended_indicators.roc:151` (%), `sector_rank._momentum:27` (fraction) | `roc` | + | % or fraction | window is a parameter, not a policy |
| Momentum → momentum 5D | — | **ABSENT** | — | — | + | — | nearest: `knife_guard.momentum_return_z:78` (lookback=3) and `rotation.vol_cones:123` (5d vol, not return) |
| Momentum → momentum 20/60D | — | SCORABLE | `quant_baseline.momentum:17` (horizon default 60) | `momentum` | + | fraction | UNWIRED (tests only) |
| Momentum → momentum 21/63/126/252D (per name) | — | **UNWIRED** | `factors.momentum_multihorizon:418` (horizons 21/63/126/252 + `ensemble`) | `horizons`,`ensemble` | + | fraction | whitelisted unreachable: `tests/test_calc_agent_wiring.py:40` ("legacy factor composite"). **[CORRECTED 2026-09-26: wired — `analysis_tools.py:2433` calls `momentum_multihorizon(closes)` and prints the horizons + ensemble; the `tests/test_calc_agent_wiring.py:40` whitelist entry was removed. Status is now SCORABLE.]** |
| Momentum → momentum 21/63/126/252D (sector ETF) | — | SCORABLE | `sector_rank._momentum:27` + `_MOMENTUM_WINDOWS:216`, wired in `rank_sectors_multifactor:391` | `ret_1m`,`ret_3m` | + | fraction | ETF level only |
| Momentum → momentum 252D (12-1) | — | SCORABLE | `momentum.momentum_12_1:358`, `factors.momentum:24` (lookback=252, skip=21) | `momentum` | + | fraction | `factors.momentum` consumed by `overlays.build_strategy_overlays:47` (mom60, skip=0) only |
| Momentum → acceleration / deceleration | — | SCORABLE | `sector_rank._acceleration:289` (R63-0.5*R126), `extended_indicators.momentum_oscillator:162` | `accel` | + | fraction / price units | — |
| Momentum → Clenow momentum | — | SCORABLE | `rotation.clenow_momentum:89` | — | + | ratio (exp(slope*252)*R2) | exposed as `get_clenow_momentum` |
| Momentum → KST / MFI | — | SCORABLE | `technical_factors.kst:104`, `technical_factors.mf_index:163` | `kst`,`trigger`,`crossover` / MFI value | **NON-MONO** for MFI (>80 overbought) | 0-100 (MFI) | — |
| **Relative strength** | 12 | **PARTIAL** | no composite; `relative_strength.relative_strength_report:214` returns a verdict, not a score | `verdict` | + | label + slope%/day | no scale to weight |
| RS → stock vs SPY | — | SCORABLE | `relative_strength.rs_series:33`, `relative_strength_report:132` | `rs`,`slope_pct`,`uptrend` | + | ratio + %/day | leaf binds only `benchmark_ticker` (SPY) — `analysis_tools._benchmark_closes:322` |
| RS → stock vs QQQ / sector ETF | — | PARTIAL | `etf_risk.etf_relative_strength:88` (bench_map) | `benchmarks[label][window].relative` | + | fraction | ETF path only (`get_etf_relative_strength:1768`, bound 450); no per-stock QQQ/sector leg |
| RS → RS slope | — | SCORABLE | `relative_strength.slope_pct:49` | `slope_pct` | + | %/day (mean-normalised OLS) | — |
| RS → RS position / new high | — | SCORABLE | `relative_strength.rs_position:89` | `new_high`,`near_high` | + | bool | — |
| RS → RS divergence | — | SCORABLE | `relative_strength.divergence:195` | `divergence` | − (divergence is bad) | bool | — |
| RS → relative rotation (RRG) | — | SCORABLE | `rotation.relative_rotation:43`, `sector_rank.rrg_quadrant:370`, `sector_breadth.rrg_heading:286` | `quadrant` | + | z-units (stock) / 0-100 pct (sector) | two implementations, different normalisation |
| RS → sector- and industry-relative momentum | — | SCORABLE | `sector_rank.rank_sectors_multifactor:391` (`momentum`,`rs`,`rs2`,`rs_momentum`,`quadrant`,`score`), `sector_rank.rank_industry_group:600`, `sector_rank.sector_standing:176`, `sector_screener._rel_outperformance:248` | `score`,`rs`,`rs2` | + | 0-100 percentile (ETF pool) / fraction | ETF/industry level only, never per-name |
| **Price structure & support/resistance** | 12 | **PARTIAL** | no composite; `value_dip.support_structure:833` is the nearest (label) | `verdict` | + (at support) | label | no scale |
| P/S-R → pivot points | — | SCORABLE | `technical_factors.pivot_points:290` | `p`,`r1`,`s1`,`r2`,`s2` | ± (level) | price | daily/weekly only; no distance-to-level metric |
| P/S-R → support structure | — | PARTIAL | `value_dip.support_structure:833` | `verdict`,`distance_to_sma200_pct` | + | label / fraction | the 1.5-ATR branch is DEAD — see §3 |
| P/S-R → volume profile POC / value area | — | PARTIAL | `technical_factors.volume_profile:827` | `poc`,`value_area_high`,`value_area_low` | ± (level) | price | value-area accumulator broken — see §3 |
| P/S-R → Donchian channel | — | PARTIAL | `technical_factors.donchian_channel:468` | `upper`,`lower`,`mid` | ± | price | `breakout_up`/`breakout_dn` are hardcoded `None` — see §3 |
| P/S-R → Fibonacci levels | — | SCORABLE | `swing.fib_levels:295`, `value_dip.fib_retrace_entry:904` | `near_level`,`zone` | + (in golden zone) | price / fraction | — |
| P/S-R → candlestick patterns | — | SCORABLE | `extended_indicators.scan_candlesticks:603` | `patterns{7 bools}` | ± | bool | no magnitude/strength |
| P/S-R → Bollinger %b | — | SCORABLE | `value_dip.bollinger_pct_b:77` | `pct_b` | **NON-MONO** (<=0 dip / >1 extended) | ratio (unbounded) | — |
| P/S-R → Keltner %b | — | SCORABLE | `technical_factors.keltner_channel:440` | `pct`,`mid` | ± | ratio | needs an ATR argument |
| P/S-R → Supertrend line | — | SCORABLE | `technical_factors.supertrend:792` | `line`,`direction` | + (direction up) | price / label | single-bar read, not a trailing series |
| P/S-R → swing-low stop | — | SCORABLE | `swing.swing_low_stop:190` | `stop`,`risk_pct` | − (risk) | price / fraction | — |
| **Volume & accumulation** | 10 | **PARTIAL** | no composite; 4 separate producers in mixed units | — | + | — | — |
| Volume → volume ratio / RVOL | — | SCORABLE | `momentum.rvol:25` | `rvol` | + | ratio (x average) | window 50 default; `value_dip.trigger_candle:661` uses 20 |
| Volume → Elder thermometer | — | SCORABLE | `technical_factors.elder_thermometer:649` | `ratio`,`heavy`,`quiet` | **NON-MONO** (`quiet` <0.8 is the good dip read) | ratio | — |
| Volume → A/D line | — | SCORABLE | `extended_indicators.accumulation_distribution:224` | value | + | share-volume units (unbounded) | cumulative sum, no normalisation |
| Volume → Chaikin oscillator | — | SCORABLE | `technical_factors.chaikin_oscillator:733` | value | + | unbounded A/D units | scale hazard — see §3 |
| Volume → Chaikin Money Flow | — | SCORABLE | `extended_indicators.chaikin_money_flow:263` | value | + (>=+0.1) | -1..1 | — |
| Volume → OBV | — | PARTIAL | `technical_factors.obv_divergence:542` | `obv_up`,`bullish_div` | + | bool | the OBV LEVEL is computed locally and discarded |
| Volume → Force Index / VPT | — | SCORABLE | `extended_indicators.force_index:206`, `extended_indicators.vpt:248` | value | + | unbounded | — |
| Volume → institutional flow | — | SCORABLE | `orderflow.institutional_net:45`, `orderflow.retail_net:49`, `orderflow.summarize:128` | `inst_net`,`distribution_score` | + (inst_net) / − (distribution) | vendor currency units / 0-1 | live moomoo only; degrades to neutral |
| Volume → volume dry-up | — | SCORABLE | `value_dip.volume_dry_up:603` | `dry_up`,`vdu_ratio` | + (low ratio) | ratio | — |
| **Breakout & pullback** | 10 | **PARTIAL** | no composite; state flags in 5 places | — | + | bools/labels | — |
| Breakout → channel breakout | — | PARTIAL | `technical_factors.donchian_channel:468` | `breakout_up/dn` | + | bool | always `None` — see §3 |
| Breakout → opening-range breakout | — | SCORABLE | `market_session.opening_range:72` | `breakout` | + | label `up`/`down`/None | needs intraday bars |
| Breakout → VCP base / near-breakout | — | SCORABLE | `swing.vcp_setup:342` | `candidate`,`near_breakout`,`pivot`,`depths` | + | bool / price / fractions | — |
| Breakout → shelf / first-pullback setup | — | SCORABLE | `sector_screener.setup_a:270`, `sector_screener.setup_b:318` | `state` | + | label | needs sector + constituent context |
| Pullback → pullback into EMA20 | — | SCORABLE | `swing.pullback_setup:161` | `candidate`,`near_ema`,`volume_fade` | + | bool | — |
| Pullback → first pullback (day) | — | SCORABLE | `momentum.first_pullback:210`, `momentum.intraday_pullback:325` | `candidate`,`rr`,`stop` | + | bool / R-multiple | — |
| Pullback → trigger candle | — | SCORABLE | `value_dip.trigger_candle:661` | `trigger`,`rvol` | + | bool / ratio | — |
| Pullback → VDU entry ladder | — | SCORABLE | `value_dip.vdu_entry_setup:747` | `candidate` | + | bool | — |
| Breakout → gap type | — | SCORABLE | `market_session.gap_type:220` | `type`,`fill_probability` | ± | label / prob | fill stats are HARDCODED constants (0.8/0.3/0.4/0.6) — see §3. **[CORRECTED 2026-09-26: stale — §3 defect 11 already carries the FIXED 2026-09-17 `ba50b5f` tag, and the tree agrees: `market_session.py::_gap_fill_stats:167` is the measured basis with a labelled minimum-sample fallback, not the literal lookup table.]** |
| **Mean reversion** | 8 | **PARTIAL** | no composite; `mean_reversion.mean_reversion_verdict:226` is a label | `verdict` | + | label | no z-scale output |
| MR → mean-reversion z-score | — | PARTIAL | `value_dip.zscore:104` (generic helper) | — | ± | z | no per-series producer wired to any leaf; `factors.z_score:70` is cross-sectional only |
| MR → StochRSI | — | SCORABLE | `technical_factors.stoch_rsi:374` | `stochrsi` | **NON-MONO** (<0.2 oversold) | 0-1 | — |
| MR → RSI2 | — | SCORABLE | `technical_factors.rsi2:406` | value | **NON-MONO** (<10 buy) | 0-100 | — |
| MR → Williams %R | — | SCORABLE | `technical_factors.williams_r:429` | value | **NON-MONO** (-80..-100 oversold) | -100..0 | — |
| MR → Hurst / variance ratio / half-life | — | SCORABLE | `mean_reversion.hurst_exponent:113`, `mean_reversion.variance_ratio:259`, `mean_reversion.ar1_half_life:69`, `mean_reversion.ou_half_life:91` | `hurst`,`vr`,`z`,`half_life` | + (H<0.5 reverting) | 0-1 / ratio / bars | no leaf binds these — verify |
| MR → PSAR reversal flag | — | PARTIAL | `technical_factors.parabolic_sar:605` | `sar` | ± | price | `below`/`exit` always `None` — see §3 |
| MR → OBV divergence | — | SCORABLE | `technical_factors.obv_divergence:542` | `bullish_div` | + | bool | — |
| **Volatility & ATR** | 5 | **PARTIAL** | no composite | — | risk-increasing (higher = more risk; must be inverted for a favourable score) | — | — |
| Vol → ATR | — | SCORABLE | `size.atr:143`; `etf_risk._atr:122` (private); `regime_state._atr14:55` (private) | value | risk-increasing | price units | **stale, corrected 2026-09-17:** `size.atr:143` returns **`None`** on failure (its own docstring records that returning `0.0` was the defect); the `0.0` claim was wrong |
| Vol → ATR percentile | — | **ABSENT** | — | — | — | — | grepped `atr_pct|atr_percentile|percentile.*atr` in `tradingagents/` → only `etf_risk.etf_risk_profile:142`'s `atr_pct` (ATR/price, not a percentile) and a prose mention in `tradingagents/data/skills/volume_breakout.yaml:17` |
| Vol → realized volatility | — | SCORABLE | `regime.realized_vol:39`, `quant_baseline.volatility:39`, `etf_risk._realized_vol:69`, `volatility_models.parkinson_vol:155`, `garman_klass_vol:78`, `yang_zhang_vol:116`, `ewma_vol:185`, `garch11_fit:226` | value | risk-increasing | annualised fraction | 8 producers for one quantity — rule 3 naming problem |
| Vol → vol percentile | — | **BLOCKED on a defect** | `regime.vol_percentile:59`; `etf_risk.etf_risk_profile:142` (`vol_percentile`, ETF path only) | `vol_pctile` | risk-increasing | 0-1 | **`regime.vol_percentile` returns `0.5` when it cannot measure** (`:56-60`: `if not wins or len(wins) < 2: return 0.5`) - a fabricated neutral, master rule 1's exact prohibition, and the reason the Phase-A `TechnicalScore` leaf does not consume it. Its home is `RegimeScore` (WP-4): the fix is `None` + reason, and every caller (`get_regime_components`, `regime_split_performance`) already guards `is not None`. **[CORRECTED 2026-09-26: the fix has landed — `regime.py::vol_percentile:59` now returns `None` when `len(wins) < 2` (its docstring: "never a fabricated 0.5"), and `vol_percentile_read:81` returns the reason string; no caller reads a `0.5`. The "BLOCKED on a defect" status above is therefore stale, and §8.4 #5's "the doc's §1 volatility row still records the old `0.5` behaviour as current" is now resolved: the leg is measurable.]** |
| Vol → vol cones | — | SCORABLE | `rotation.vol_cones:123` | `{win:{current,p25,p50,p75}}` | risk-increasing | annualised, 0-1 | 5 producers again |
| Vol → ATR-ratio / vol cap | — | SCORABLE | `regime_state.regime_vol_ratio:92`, `regime_state.vol_cap_factor:169`, `knife_guard.atr_ratio_z:115` | ratio / `F_vol` | risk-increasing | ratio / 0-1 scale | — |
| Vol → choppiness index | — | SCORABLE | `regime.choppiness:141` | value | ± | 0-100 | scale mismatch with `overlays.py:57` — see §3 |
| Vol → upside semivariance (RS⁺) | — | **ABSENT** | — | — | ± (the "good" leg; not risk-increasing on its own) | squared-return units; `√RS⁺` is a volatility in return units | grepped `semivar\|semi_?vol\|upside_vol\|downside_vol` over `tradingagents/` → **zero hits**; the measurement home is `volatility_models.py` (parkinson / garman_klass / yang_zhang / ewma / garch). **[CORRECTED 2026-09-26: built — `volatility_models.py::semivariance:68` returns `rs_plus` (= `RS⁺ = Σ max(r,0)²/n`) over the same `n` as the downside leg; the "zero hits" grep is stale. Status is now SCORABLE.]** |
| Vol → downside semivariance (RS⁻) | — | **ABSENT** | — | — | risk-increasing — this is the **persistent** leg | squared-return units; `√RS⁻` is a volatility in return units | same grep; `evaluate.downside_deviation:846` and `rate_utils.downside_measures:149` are *conditional* downside deviation, not semivariance — they do not satisfy `RS⁻ + RS⁺ = RV`. **[CORRECTED 2026-09-26: built — `volatility_models.py::semivariance:68` returns `rs_minus` (= `RS⁻ = Σ min(r,0)²/n`) and `sqrt_rs_minus`, with the exact `rs_minus + rs_plus = rv` decomposition (Patton & Sheppard 2015). Status is now SCORABLE.]** |
| Vol → semivariance asymmetry (RS⁻/RS⁺) | — | **ABSENT** | — | — | risk-increasing above 1 | ratio | a ratio of two conditional stds (`σ_up/σ_down`) is **confounded with drift** — it moves with the mean return, so it partly re-measures momentum; build the semivariance ratio, not the conditional-std one. **[CORRECTED 2026-09-26: built — `volatility_models.py::semivariance:68` returns `asymmetry` (the semivariance ratio `RS⁻/RS⁺`, not a `σ_up/σ_down` conditional-std ratio); the "zero hits" grep is stale. Status is now SCORABLE.]** |
| **Breadth & participation** | 5 | **PARTIAL** | sector-level only; market-wide is a vendor TEXT blob | — | + | — | not per-name, not numeric market-wide |
| Breadth → market-wide | — | PARTIAL | `moomoo_extra_tools.get_market_breadth:98` → `dataflows/moomoo.py:get_market_breadth_moomoo:1830` | rendered text only | + | none (string) | no numeric producer anywhere |
| Breadth → sector breadth matrix (%>20/50/200d) | — | SCORABLE | `sector_breadth.multi_breadth:165` | `pct_20d`,`pct_50d`,`pct_200d` | + | 0-100 per ETF | wired only inside `get_sector_rotation_screen:3618` (`analysis_tools.py:3765`) |
| Breadth → McClellan oscillator / MSI | — | SCORABLE | `sector_breadth.mcclellan_read:213`, `sector_breadth.msi_zone:307` | `mo`,`msi`,`zone` | + | oscillator / cumulative index | advisory only; never a gate |
| Breadth → constituent breadth | — | SCORABLE | `sector_rank.constituent_breadth:664` | `pct`,`n` | + | 0-100 | curated 10-name constituent lists (`sector_rank.SECTOR_CONSTITUENTS:645`) |
| Breadth → EW/CW leadership | — | SCORABLE | `sector_rank.leadership_ratio:684`, `sector_screener.leadership_ratio_ewcw:535` | `ratio` | + (>1 broad) | ratio | two implementations |
| Breadth → dispersion trend | — | SCORABLE | `sector_screener.dispersion_trend:163` | `rising/falling/flat` | ± | label | — |
| Breadth → per-name participation | — | **ABSENT** | — | — | — | — | only the vendor `get_capital_flow` (`moomoo_extra_tools.py:18`) string |

---

## 2. Tool leaves (what the analysts can actually call)

Bindings are in `tradingagents/agents/toolsets.py`; `market_tools()` starts at `:224`, `news_tools()` at `:345`, `fundamentals_company_tools()` at `:378`, `fundamentals_etf_tools()` at `:438`.

| Leaf (`function:line`) | Toolset binding (`agents/toolsets.py:line`) | What it returns | Wired? |
| --- | --- | --- | --- |
| `get_indicators:9` (`utils/technical_indicators_tools.py`) | market 228 | vendor indicator window report: `close_10_ema`, `close_50_sma`, `close_200_sma`, `macd`, `macds`, `macdh`, `rsi`, `boll`, `boll_ub`, `boll_lb`, `atr`, `vwma`, `mfi` (`dataflows/y_finance.py:85-154`) | yes |
| `get_technical_factors:5345` | market 293 | ADX/DI±, pivots, Aroon, Fisher, Chaikin, Elder-Ray, Supertrend, volume profile | yes |
| `get_extended_indicators:5406` | market 294 | Ichimoku, golden/death cross, CCI, ROC, momentum osc, TRIX, Force Index, A/D, VPT, CMF, anchored VWAP | yes |
| `get_candlestick_patterns:5473` | market 295 | doji/hammer/shooting-star/engulfing/morning+evening star scan (`extended_indicators.scan_candlesticks:603`) | yes |
| `get_swing_set:351` | market 253 | trend architecture, RSI band, pullback, structure stop, 2R/3R, scale-out, EMA trail, VCP, RS (`swing.swing_report:457`) | yes |
| `get_swing_exits:1051` | market 255 | chandelier stop + EMA trail + targets | yes |
| `get_volatility_contraction:1010` | market 273 | VCP candidate/depths/volume fade/near-breakout | yes |
| `get_relative_strength:488` | market 263 | RS verdict vs `benchmark_ticker` (SPY), 63d slope, near-high, divergence (`relative_strength_report:132`) | yes |
| `get_dip_technical:1108` | market 256 | RSI, Bollinger %b, Stochastic K, MFI, KST | yes |
| `get_mean_reversion_tech:1160` | market 257 | StochRSI, RSI2, Williams %R, Keltner, Donchian, OBV div, PSAR, Elder ratio | yes |
| `get_momentum_detail:2200` | market 272 | RVOL(50), VWAP, EMA9, 5 pillars, first pullback (`momentum.py`) | yes |
| `get_momentum_12_1:3220` | market 317 | 12-1 momentum (`momentum.momentum_12_1:358`) | yes |
| `get_momentum_scan:18` (`utils/momentum_tools.py`) | market 305 | RVOL, pillars, first-pullback with R/R, intraday block | yes |
| `get_sector_rank:3410` | market 275 | SPDR 1m/3m ranking + the name's sector standing | yes |
| `get_sector_rotation_screen:3618` | market 276 | sector multifactor rank + optional constituent breadth/EW-CW/Setup A-B + breadth matrix | yes |
| `get_relative_rotation:7303` | market 322 | RRG ratio/momentum/quadrant vs benchmark | yes |
| `get_volatility_estimators:7188` | market 296 | close/Parkinson/Garman-Klass/Yang-Zhang vol side by side | yes |
| `get_regime_read:964` | market (via market_tools list) | regime label + position scale + mom60 + 52w distance (`overlays.build_strategy_overlays:47`) | yes |
| `get_regime_components:2145` | market 269 | vol_pct, trend, choppiness that produced the label | yes |
| `get_regime_state:20` (`utils/quant_adds_tools.py`) | market 270; fundamentals 431/455 | 4-axis regime state + `F_regime` (`regime_state.regime_state:215`) | yes |
| `get_orderflow_read:1215` | market 274 | institutional/retail net, distribution score, divergence, alignment | yes |
| `get_capital_flow:18` (`utils/moomoo_extra_tools.py`) | market 252 | raw moomoo capital buckets by order size | yes |
| `get_market_breadth:98` (`utils/moomoo_extra_tools.py`) | news 368 (only) | market breadth text blob | yes, but not bound to the market analyst |
| `get_bollinger_pct_b:149` (`utils/value_dip_tools.py`) | market 287 | Bollinger %b | yes |
| `get_macd_divergence:926` | market 290 | RSI/MACD-hist divergence verdict | yes |
| `get_vdu_entry_setup:959` | market 291 | VDU ladder candidate + sub-signals | yes |
| `get_support_structure:997` | market 292 | support verdict + base/SMA200 distances | yes |
| `get_value_dip_setup:650` | not in `market_tools()`; used on the fundamentals path | the whole dip matrix incl. a `knife_composite` row | yes (fundamentals) |
| `get_etf_relative_strength:1768` | fundamentals_etf 450 | RS legs vs SPY/QQQ/XLK (`etf_risk.etf_relative_strength:88`) | yes (ETF only) |
| `get_factor_profile:8600` / `domain_bundles.get_factor_profile:124` | market 341 | Alpha158-style factor vector + rank-IC reads | yes |
| `get_ts_momentum_weights:8141` | market 333 | time-series momentum weights (`momentum.ts_momentum_weights:98`) | yes |
| `get_lottery_factors:8659` | market 282 | lottery-tilt screen | yes |
| `get_skill_read:9245` | market 254 | regime-from-opinion skill selection + advisory folded score | yes — but the trend score is caller-supplied |
| `get_position_risk_multiplier:96` (`quant_adds_tools.py`) | market (via `get_position_risk_multiplier`) | soft/hard multiplier (`risk_multiplier.combine`) | yes — knife_factor is caller-supplied |

---

## 3. Defects and dead seams

**Explicit answer — is there any composite technical score (0-100) anywhere in the three repos? NO.**

Searched (all three trees): `technical.?score|tech_score|technical_score|TechnicalScore` → zero matches in `TradingExecution` and `trading_web`; in `TradingAgents` only prose in design documents (the score-engine set in `docs/scores/`, `docs/ScoreWeight/market.md:38-131`) and `CHANGELOG.md`. `trend_score` → `agents/utils/analysis_tools.py:9247` (a **tool argument**, not a producer), `strategies/skills.py:109-120` (threshold reader), `tests/test_skill_overlays.py:41-50`, and live artifacts (`ToolCallLog/ASML_tool_calls.jsonl:14` trend_score=28, `HPE:9` =65, `MSFT:187` =72 — model-authored numbers). `\*\s*100\.0` + `score.*0-100` → the only producers emitting 0-100 are `factors.category_scores` (fundamental peer percentile), `capex_quality` (fundamental), `data_quality.aggregate_quality` (data quality), `news_relevance.score_news_article` (news relevance), `sector_rank.rank_sectors_multifactor:391` (sector ETF level), `sector_screener.grade_for:126` (grade band), `decision_guardrail.SCORE_BANDS:27`. None is technical. Nearest technical-adjacent numbers, each not a technical composite: `quant_baseline.quant_signal:74` (score ≈[-1,1], UNWIRED — whitelisted as unreachable legacy, `docs/scores/FundamentalScore.md:242`), `knife_guard.knife_score:159` (K ≈0..3+, higher = **worse**), `regime_state.regime_trend:65` ((EMA20-EMA50)/ATR14, ATR units), `sector_rank.rank_sectors_multifactor:391` (0-100, ETF pool). The executor has the 0-100 `opportunity_score` slot but no technical producer; the web repo has none.

| # | Defect | Lines that disagree | What a reader sees wrong today |
| --: | --- | --- | --- |
| 1 | **[FIXED 2026-09-17, `ba50b5f`]** Donchian breakout flags were hardcoded `None` and **no caller derived them** | `strategies/technical_factors.py:390-391` (`"breakout_up": None,  # closes not passed; caller derives`) vs the leaf `agents/utils/analysis_tools.py:1160` (`get_mean_reversion_tech` prints only `d.get('upper')`/`d.get('lower')`) | a "Donchian breakout" component is unscorable from the only leaf that calls it; `value_dip.value_dip_setup:1093` also stores the same None row |
| 2 | **[FIXED 2026-09-17, `ba50b5f`]** `parabolic_sar` was called without `closes`, so `below`/`exit` were always `None` | `technical_factors.parabolic_sar:605` (flag only when `closes is not None`) vs `analysis_tools.py:1178` → `_psar(data["highs"], data["lows"])` | a "close below SAR = downtrend exit" read never fires; only the raw SAR level is reported |
| 3 | **[FIXED 2026-09-17, `2c05701`]** `volume_profile` value-area accumulator is dead arithmetic: `acc` is incremented then immediately overwritten, and the moved bin is re-added in a branch that is then discarded | `technical_factors.volume_profile:827-692` (`acc += vol_by_bin[lo_i] if lo_i != hi_i else 0` then `acc = sum(vol_by_bin[lo_i : hi_i + 1])`) | the value area can collapse to the whole price range — measured in `reports/AMAT_20260914_191359/tool_evidence.json:3341`: `poc=169.5614 va_high=424.6382 va_low=169.5614` on a 424 close |
| 4 | **[FIXED 2026-09-17, `2c05701`]** `get_position_risk_multiplier` takes `knife_factor` (0..1) from the LLM; no leaf computes the composite K for the market analyst | `agents/utils/quant_adds_tools.py:96-125` (argument default `1.0`) vs `strategies/knife_guard.py:156` (`knife_score`, whose only caller is `value_dip.value_dip_setup:1093`) | a "computed execution multiplier" is fed an invented factor; a 0.0 (block) or 1.0 (no reduction) both look measured |
| 5 | **[FIXED 2026-09-17, `2c05701`]** `get_skill_read` accepts a 0-100 `trend_score` from the model and can fold YAML constants onto it, printing a number that looks computed | `agents/utils/analysis_tools.py:9247` (`trend_score` argument) + `:9294-9300` ("Folded score (advisory)") vs `strategies/skills.py:117-120` (thresholds on the same opinion) | the report can quote "trend_score=72" / "Fold 60 + 12 = 72.0/100" with no producer behind either number; the live tool-call log shows exactly that (`ToolCallLog/MSFT_tool_calls.jsonl:187`) |
| 6 | **[FIXED 2026-09-17, `2c05701`]** `support_structure`'s primary branch is unreachable from the only leaf: the leaf passes no `atr_value`, so the "within 1.5 ATR of base low" test is skipped | `strategies/value_dip.py:738` (`if a is not None and ... ` — `a` is `None` when no ATR) vs `agents/utils/value_dip_tools.py:1018` (`support_structure(closes, highs, lows)`) | "multi-month-base-support" can never be emitted; only the 3%-proximity and holding-above-base branches fire |
| 7 | **[FIXED 2026-09-17, `2c05701`]** `size.atr` returns **0.0**, not None, on insufficient data — an NA→0 violation on the volatility input | `strategies/size.py:131-140` (`def atr(...) -> float: ... return 0.0`) vs the repo's own no-fabrication contract (`factors.py:5`, `technical_factors.py:12`) | a caller that checks `atr is not None` treats "unknown volatility" as "zero volatility"; `technical_factors.keltner_channel:440` only survives because it also tests `<= 0` |
| 8 | **[FIXED 2026-09-17, `2c05701`]** `rank_sectors_multifactor` substitutes `0.0` for a missing percentile in the risk leg, then emits a score | `strategies/sector_rank.py:536` (`0.6 * (s if s is not None else 0.0) + 0.4 * (d if d is not None else 0.0)`), guarded by `if (s is not None or d is not None)` | a sector with unmeasurable drawdown is scored as if it had the WORST drawdown percentile (0.0 is the floor of a higher-is-better percentile) — NA becomes a penalty, against ground rule 1 |
| 9 | `regime_label`'s chop branch is dead for the only caller: `overlays` passes `chop=0.4` against a default `chop_threshold=0.30`, while the canonical choppiness producer returns 0-100 | `strategies/overlays.py:57` (`regime_label(vol_pct, trend, 0.4)`) vs `strategies/regime.py:133` (default 0.30) and `regime.py:87` (`choppiness` returns 0-100) | with the common `vol_pct == 0.5` (`overlays.py:43` builds a 3-valued proxy) both prior branches miss and `0.4 <= 0.30` is False → the label is `neutral` regardless of trend; a quoted `regime=neutral` carries no information. **[FIXED 2026-09-26: `overlays.py:62-63` now passes `chop = choppiness(closes_f, window=14)` (the 0-100 measured value), and `regime_label`'s threshold is the named `CHOP_TREND_THRESHOLD` = 30.0 (`regime.py:191`) on the same 0-100 scale — the chop branch is live for its caller. Aligns with `RegimeScore.md` §3 defect 1, which already carries the FIXED tag.]** |
| 10 | **[FIXED 2026-09-17, `2c05701`]** `rule_eval.rule_signal_macd_hist_rising` (the only MACD-histogram-slope producer) has no production reader | `strategies/rule_eval.py:103` / registered at `:156` vs its only importers `scripts/rule_eval.py:24` and `tests/test_signal_action_sizing_ruleeval.py:14` | the MACD-histogram-slope sub-factor is unscoreable from any analyst tool |
| 11 | **[FIXED 2026-09-17, `ba50b5f`]** `gap_type`'s fill statistics were hardcoded constants, not measurements | `strategies/market_session.py:178-193` (`fill_prob=0.3/0.6/0.4/0.8`, `days=5/3/4/2` literal per branch) | a "fill probability" is printed as if measured from history; it is a 4-way lookup table (ground rule 6: measure, don't assume) |
| 12 | **[FIXED 2026-09-17, `2c05701`]** `chaikin_oscillator` returns an unbounded A/D-unit difference while the leaf labels it "positive=buying pressure" — the sign is a scale artefact, not a verdict | `technical_factors.chaikin_oscillator:733` (`round(ema_fast[-1] - ema_slow[-1], 4)`, raw share-volume units) vs `analysis_tools.py:xxxx` in `get_technical_factors:5345` (the `(positive=buying pressure)` suffix) | `reports/AMAT_20260914_191359/tool_evidence.json:3341` shows `chaikin=869687.156 (positive=buying pressure)` on a name the same block reports as `aroon … downtrend`, `di- > di+`, `sup... |

---

## 4. What is ABSENT / PARTIAL, and the smallest honest producer

| Missing piece | Data needed | Does the engine already fetch it? | Smallest honest producer |
| --- | --- | --- | --- |
| **Composite TechnicalScore (0-100)** | nothing new — the components below | yes, all inputs are the run's OHLCV (`analysis_tools._ohlcv:236`) | one pure function `strategies/technical_score.py` taking the already-computed component dicts, with the owner's weight table and a per-component direction (the 5 NON-MONO rows must be band-mapped, not passed through) |
| PCA/EMA slope, RSI slope | the existing EMA/RSI series | yes — `technical_factors.ema:40` returns the full series; `swing.rsi:44` returns only the last value | reuse the existing normalised-OLS helper `relative_strength.slope_pct:49` (it takes any series) — for RSI, promote `value_dip._rsi_series:472` (already a full Wilder series) to public |
| MACD line + histogram values (+ slope) | closes | yes — `value_dip._macd_hist:502` already returns `(line, signal, hist)` series | make `_macd_hist` public and add the three lines to `get_extended_indicators:5406`; slope = last minus prior bar (the same one-bar delta as `rule_eval.rule_signal_macd_hist_rising:103`) |
| momentum 5D | closes | yes | `extended_indicators.roc:151` is already parameterised — `roc(closes, 5)`; `factors.momentum_multihorizon:418` accepts a custom `horizons` tuple |
| ATR percentile (and per-name vol percentile) | a trailing ATR series | yes — `size.atr:143` over the cached 320-bar OHLCV | the loop already written for realized vol at `etf_risk.etf_risk_profile:142-172` (63d rolling windows over ~3Y, then `sum(x < cur)/n`) with `size.atr` in place of `_realized_vol:69`; note `regime.vol_percentile:59` is the same shape but takes a list of histories |
| OBV value (not just divergence) | closes + volumes | yes — `technical_factors.obv_divergence:542` computes the cumulative OBV and discards it (local `obv` at `:404`) | return the last OBV value alongside `obv_up` |
| Donchian breakout state | closes (already available in the leaf) | yes — `get_mean_reversion_tech:1160` has `closes` in scope | pass `closes` into `donchian_channel:377` (the docstring's stated caller contract) or derive in the leaf |
| PSAR exit state | closes | yes — same leaf | pass `closes=` to `parabolic_sar:432` (the parameter already exists) |
| mean-reversion z-score per series | the series | yes | `value_dip.zscore:104` is generic; apply it to `bollinger_pct_b` history / `Rsi` history / price-vs-Keltner and expose one z per signal |
| Per-name RS vs QQQ and vs the sector ETF | the benchmark series | yes — `_ohlcv` fetches any symbol, `_bench_ohlcv:1722` exists for SPY/QQQ/XLK, and `sector_rank.sector_group_of:163` maps a GICS sector to its SPDR ETF | call `relative_strength.relative_strength_report:214` once per benchmark (it is benchmark-agnostic) or use `etf_risk._period_ret:35`'s multi-window shape for the 21/63/126/252 legs |
| Market-wide numeric breadth | advance/decline, % above 50/200d for the US universe | partially — constituent closes are already fetched in bulk for the sector screens (`analysis_tools.py:3664-3766`, `sector_screener.constituent_universe:456`) | aggregate `sector_breadth.multi_breadth:165` across sectors instead of per-sector (the same function already accepts a `{name: closes}` map and returns per-key percentages) |
| Per-name participation / ADV share | volume history + account size | yes — `_ohlcv` volumes; `liquidity_risk.volume_share_slippage` is whitelisted legacy | `momentum.rvol:25` normalised by `elder_thermometer:476`'s 21-bar average is the honest ratio; the repo already has the slippage model in `strategies/liquidity_risk.py` |
| Momentum multi-horizon per name (already built, unreachable) | closes | yes | delete the `tests/test_calc_agent_wiring.py:40` whitelist and wire `factors.momentum_multihorizon:418` — or accept it as legacy and re-derive from `sector_rank._momentum:27`. **[CORRECTED 2026-09-26: DONE — the whitelist entry is removed and `factors.momentum_multihorizon:418` is wired at `analysis_tools.py:2433`; no residual open item.]** |
| Upside / downside semivariance | the run's own return series (`analysis_tools._ohlcv:236` closes) | yes — nothing new to fetch | `volatility_models.semivariance(returns, *, min_obs=20) -> {"rs_up", "rs_down", "rs_total", "rs_ratio", "n"}` beside the existing estimators: `RS⁻ = Σ r²·1[r<0]`, `RS⁺ = Σ r²·1[r>0]`, and `RS⁻ + RS⁺ = RV` **exactly** (Patton & Sheppard 2015). `None` below `min_obs`, never `0`. The score consumes `√RS⁻` (return units, comparable to `realized_vol:29`) and the ratio; the raw sums print beside them. **Owned here** — `RiskScore.md` §1 reads it as a named dependency. **[CORRECTED 2026-09-26: BUILT — the real signature is `volatility_models.py::semivariance:68` = `semivariance(closes, window=None, *, min_obs=20, periods=_DAYS) -> dict` (it takes closes, not a returns series) returning `{rs_minus, rs_plus, rv, sqrt_rs_minus, sqrt_rs_plus, asymmetry, n, annualized, basis}`; every leg is `None` with the reason in `basis` below `min_obs`. The keys above (`rs_up`/`rs_down`/`rs_total`/`rs_ratio`) are superseded by the built names.]** |

Note for the document: five NON-MONO rows are confirmed by reading, not assumed — `swing.rsi_band:123` (mid-band "strong"), `technical_factors.mf_index:163` (oversold good), `technical_factors.stochastic_oscillator:197` (`oversold` flag), `technical_factors.elder_thermometer:649` (`quiet` = good dip), and `value_dip.support_structure:833` (near the 200-SMA is *good*) against `swing.trend_architecture:76` (above the 200-SMA is good).

---

## 5. The composite — how `TechnicalScore` gets built

Nothing here is implemented. The design constraints:

1. **One pure function, existing inputs.** `strategies/technical_score.py`
   taking the already-computed component dicts (the leaves in §2 already produce
   every one of them) and returning `{"score": 0-100, "components": [...],
   "coverage": {...}}`. No new data fetch: all inputs are the run's OHLCV, which
   `analysis_tools._ohlcv:236` already loads.
2. **`NA ≠ 0` (master rule 1).** A component with no value is dropped from the
   denominator, and the score prints `coverage = available_weight / 100`. A
   component may never be substituted with a neutral 50 or a punitive 0.
3. **Direction first, weight second.** Each component declares
   `direction: "higher_better" | "lower_better" | "band"`, and the band table is
   the producer's own (§0.3). The `band` rows are the majority of the
   mean-reversion category and half of momentum.
4. **Per-category score, then the weight.** Nine sub-scores (each 0-100 with its
   own coverage), then `Σ w_i · s_i / Σ w_i` over the *available* categories.
   This is what makes the attribution readable — the owner's own reason for
   separate scores.
5. **A band table of its own.** Per master rule 2, nothing feeds
   `decision_guardrail.SCORE_BANDS`. `TechnicalScore` gets its own bands, and
   they are **advisory labels** ("strong uptrend", "deteriorating") — never a
   gate, never a size.
6. **The overlap with `RegimeScore` is resolved by naming.** `regime_trend:65`
   (the (EMA20 − EMA50)/ATR14 leg) is a *regime* input; `realized_vol:29` and
   `choppiness:87` are regime inputs. `TechnicalScore`'s volatility category uses
   the **per-name** ATR/realized-vol producers, and its breadth category the
   **sector** breadth matrix. Where the same function would serve both engines,
   the engine that owns it is named in the table and the other reads it as a
   stated dependency — one producer, many readers (master rule 3).
7. **Nothing here sizes anything.** `TechnicalScore` never touches
   `risk/sizing.py`. The existing sizing inputs (`size.atr:143`,
   `risk_multiplier.combine`, `knife_guard`) keep their own paths.

### 5.1 What the score may be used for, and what it may not

| May | May not |
| --- | --- |
| a printed advisory block beside the technical evidence | override a hard gate |
| an attribution row in the report ("which category moved") | feed `decision_guardrail.SCORE_BANDS` |
| an input to the Phase C research layer (IC/decile work) | set or scale a position |
| a divergence diagnostic ("score up, price flat") | be quoted as a forecast |

---

## 6. Verification requirements

1. **Direction tests are mandatory for the band rows.** Each of the six
   non-monotonic inputs gets a test that feeds the producer's own band edges and
   asserts the *mapped* value moves the right way — e.g. RSI 45-70 must not score
   lower than RSI 80.
2. **Coverage is tested, not asserted.** Feed a component dict with one category
   missing and assert `coverage` drops by that category's weight and the score
   moves toward the mean of the *available* categories, not toward zero.
3. **A no-data run must not produce a number.** With every input `None`, the
   function returns `score = None` and `coverage = 0` — never `0` and never `50`.
4. **The composite must be reproducible** from the printed components: a reader
   recomputing `Σ w·s / Σ w` from the report's own attribution block must get the
   printed score to within rounding. (This is the same contract the DCF bridge
   carries in the fundamental engine.)
5. **Redundancy is measured before weights are trusted**: pairwise correlation of
   the nine category sub-scores over the EODHD panel, reported in Phase C.

---

## 7. Decisions (owner, 2026-09-17) - all resolved

**All decided (owner, 2026-09-17).** Each question keeps its text as the record
and carries its decision inline. The architecture decisions are in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §13; the engine-internal
answers are here.


1. **Does the owner want a technical *score* or a technical *state*?** Six of the
   nine categories are state descriptions (trend, structure, breakout), three are
   oscillators. A single 0-100 mixes them; the alternative is a score plus a
   state label, which the repo already does elsewhere
   (`regime_state.regime_state:215` returns four labels plus a factor). **DECIDED
2026-09-17:** `TechnicalScore` stays a **score**; the leaves stay **states**. The
chain is `raw metric -> state / classification -> normalised contribution -> score`,
so not every leaf has to produce its own 0-100.
2. **Which benchmark for relative strength?** Today the leaf binds only SPY
   (`analysis_tools._benchmark_closes:322`). The owner names SPY, QQQ *and* the
   sector ETF; the sector map exists (`sector_rank.sector_group_of:163`) but no per-stock QQQ/sector leg is wired. **DECIDED 2026-09-17:** the **sector ETF is
the primary** benchmark and SPY / QQQ are **contextual diagnostics** - a stock
beating SPY proves nothing if its whole sector is beating SPY. One canonical field
`relative_strength_vs_sector`, with `relative_strength_vs_spy` and
`relative_strength_vs_qqq` retained as diagnostics rather than three equally
weighted factors.
3. **Intraday or daily?** `market_session.opening_range:72` and
   `momentum.intraday_pullback:325` need intraday bars; the rest of the engine is
   daily. The score's horizon must be stated once, not per component. **CLOSED 2026-09-17 (plan §13 Q11): the horizon is daily** - the intraday leaves stay leaves and do not enter the daily score implicitly.
4. **Does the volatility category invert?** Volatility is *risk-increasing*: a
   favourable technical score arguably wants **low** volatility (or a *volatility
   contraction* — VCP — which is what `swing.vcp_setup:342` already detects). The owner's 5% weight does not say which. **DECIDED 2026-09-17:** **no blanket
inversion.** The category is **non-monotonic / contextual**: volatility magnitude
stays a context-and-risk variable, and the directional interpretation uses the
canonical semivariance method of §1 and §4. A test must not assert a mechanical
inversion.

---

## 8. The owner's formula library (`Strategies/scores/technical_score.md`, 2026-09-26)

**A second, larger library.** The doc's design source has been the owner's weight master table, `../ScoreWeight/market.md` (324 lines; four engine catalogs — TechnicalScore, Market/Regime, Risk, and the ~250–300-factor target — with the nine TechnicalScore categories and ~80–120 named factors). This section accounts for the *other* owner specification, `Strategies/scores/technical_score.md`: **2,847 lines, 133 numbered sections** (`^# \d+\.`), **40 sub-headings** (29 `##` + 11 `###`) and **275 display equations** (counted as `$$`-delimited pairs — `content.count('$$') // 2`; 550 `$$` lines / 2). It is a **different** library from `market.md` and **larger**: where `market.md` names the factors and their weights, this library enumerates the individual formulas behind them, one numbered section per metric, plus five score-architecture sections (§125–§133). The nine categories are the same nine `technical_score.CATEGORY_WEIGHTS` implements, so the library is the formula-level companion to the weight table, not a competing design.

**What it changes.** The engine is gated off by default and is **advisory** (`technical_score.STATUS_ADVISORY`), like every score composite; it never overrides `GATE_PRECEDENCE`. The library does not add a gate, a size or a forecast — §127 is an explicit warning *against* letting indicators vote independently, and §132 is the coverage rule the engine already honours (absent components leave the denominator; the score is never multiplied by coverage). Parts of the library are already the engine's own contract (§125/§126/§132), parts name producers the repo already has, and parts are backlog (§8.2). The library also **contradicts** the code in a few places (§8.4) and **contradicts itself** in a few more (§8.3).


### 8.1 The library's sections against the engine

One row per numbered library section. **Status** is verified against a symbol read
this round: `built` = a producer computes the section's quantity; `PARTIAL` = some
of the section's formulas exist and the named ones do not; `ABSENT` = no producer
found by grep over `tradingagents/`; `elsewhere` = the quantity exists but a
different engine owns it (master rule 3). **Formulas** is the count of
`$$`-delimited display equations in the section, not named sub-formulas.

| # | Library section | Formulas | Status (verified symbol) |
| --: | --- | --: | --- |
| 1 | Price-derived calculations | 4 | built — `extended_indicators.roc:151` (N-period ROC), `momentum._log_returns:79` (log return) |
| 2 | Moving averages | 5 | PARTIAL — SMA `technical_factors._sma:32`, EMA `technical_factors.ema:40`; **WMA, HMA absent** (grep `wma` / `hull` → no hits) |
| 3 | Moving-average positioning | 6 | PARTIAL — `swing.trend_architecture:76` (`above_sma50`/`above_sma200`), `value_dip.support_structure:833`; SMA20/SMA100 legs absent (matches §1 ledger) |
| 4 | Moving-average slopes | 5 | PARTIAL — `swing.trend_architecture:76` (`sma50_rising` 5-bar, `sma200_rising` 15-bar); no EMA slope (only `relative_strength.slope_pct:49` exists) |
| 5 | Moving-average crossovers | 4 | PARTIAL — `extended_indicators.golden_death_cross:55`; crossover spread and velocity absent |
| 6 | EMA crossover systems | 3 | PARTIAL — the fast/slow pair is `value_dip._macd_hist:502` (12/26); EMA5/EMA20 and ATR-normalised stack absent |
| 7 | MACD | 6 | PARTIAL — `value_dip._macd_hist:502` (line/signal/hist); histogram slope `rule_eval.rule_signal_macd_hist_rising:103` (unwired); histogram acceleration absent |
| 8 | MACD crossover | 2 | PARTIAL — derivable from `value_dip._macd_hist:502`; no producer emits `I(MACD>Signal)` or the ATR-normalised spread |
| 9 | RSI | 2 | built — `swing.rsi:44` |
| 10 | RSI distance from thresholds | 2 | built — `swing.rsi_band:123` (producer band edges) |
| 11 | RSI slope | 3 | PARTIAL — series at `value_dip._rsi_series:472`; no slope or acceleration producer |
| 12 | RSI divergence | 5 | PARTIAL — `value_dip.macd_divergence:542`; the continuous `Z(ΔRSI)−Z(ΔPrice)` form absent |
| 13 | Stochastic oscillator | 4 | PARTIAL — `technical_factors.stochastic_oscillator:197` (`k`,`d`); spread and slope not returned |
| 14 | Williams %R | 1 | built — `technical_factors.williams_r:429` |
| 15 | CCI | 3 | built — `extended_indicators.cci:128` |
| 16 | ROC | 1 | built — `extended_indicators.roc:151` |
| 17 | Momentum indicator | 2 | PARTIAL — `extended_indicators.momentum_oscillator:162`; the ATR-normalised form is §30 (absent) |
| 18 | Rate-of-change acceleration | 1 | ABSENT |
| 19 | Bollinger Bands | 4 | built — `value_dip.bollinger_pct_b:77` (`mid`/`upper`/`lower`) |
| 20 | Bollinger %B | 1 | built — `value_dip.bollinger_pct_b:77` (engine component `bollinger_pct_b`) |
| 21 | Bollinger bandwidth | 1 | ABSENT — `value_dip.bollinger_pct_b:77` returns the bands, never `BBW` |
| 22 | Bollinger bandwidth percentile | 1 | ABSENT |
| 23 | Bollinger squeeze | 3 | PARTIAL — `swing.vcp_setup:342` (contraction) and `compression.atr_compression_read:75` (ATR-based percentile, not BBW) |
| 24 | Bollinger expansion | 1 | ABSENT |
| 25 | Bollinger mean-reversion distance | 1 | PARTIAL — `value_dip.bollinger_pct_b:77` computes `(C−LB)/(UB−LB)`; the `(C−MB)/(UB−LB)` form absent |
| 26 | ATR | 2 | built — `size.atr:143` |
| 27 | Normalized ATR | 1 | built — `size.atr:143` / close (engine's `atr_pct`) |
| 28 | ATR expansion | 1 | PARTIAL — `compression.atr_compression_read:75` (percentile, not the short/long ratio) |
| 29 | ATR contraction | 1 | PARTIAL — `compression.atr_compression_read:75` |
| 30 | ATR-normalized movement | 1 | ABSENT — nearest is `knife_guard.atr_ratio_z:115` (ATR ratio z, not price-move/ATR) |
| 31 | ADX | 6 | built — `technical_factors.adx:230` |
| 32 | Directional movement spread | 2 | built — `technical_factors.adx:230` (`di_plus`,`di_minus`); the engine forms `di_spread` |
| 33 | ADX trend-strength score | 3 | PARTIAL — `technical_factors.adx:230`; no ADX percentile or `f(ADX)` score (nearest `regime.trend_strength:130` is SMA200-based) |
| 34 | Parabolic SAR | 3 | built — `technical_factors.parabolic_sar:605` |
| 35 | Ichimoku | 5 | built — `extended_indicators.ichimoku:80` |
| 36 | Ichimoku cloud position | 3 | PARTIAL — `extended_indicators.ichimoku:80` (bool `above_cloud`, `span_a`/`span_b`); no `(C−bottom)/(top−bottom)` ratio |
| 37 | Cloud thickness | 2 | PARTIAL — `extended_indicators.ichimoku:80` exposes the spans via `cloud_leading`; no thickness/ATR read |
| 38 | Pivot points | 7 | built — `technical_factors.pivot_points:290` |
| 39 | Pivot distance | 3 | built — `technical_factors.pivot_distance_atr:318` |
| 40 | Support/resistance | 4 | built — `technical_factors.donchian_channel:468` (`upper`=HighestHigh, `lower`=LowestLow) |
| 41 | Breakout | 1 | built — `technical_factors.donchian_channel:468` (`breakout_up` vs `breakout_ref_up`) |
| 42 | Breakdown | 1 | built — `technical_factors.donchian_channel:468` (`breakout_dn` vs `breakout_ref_dn`) |
| 43 | Breakout persistence | 1 | ABSENT |
| 44 | False breakout | 3 | ABSENT |
| 45 | Volume-confirmed breakout | 1 | PARTIAL — `value_dip.trigger_candle:661` (volume-confirmed trigger), `volume_flags.rvol_ex_mechanical:90`; no `BreakoutStrength × V/avg` product |
| 46 | Price-volume divergence | 3 | PARTIAL — `technical_factors.obv_divergence:542` (OBV vs price); no `Slope(C) − Slope(V)` producer |
| 47 | OBV | 1 | PARTIAL — `technical_factors.obv_divergence:542` builds the cumulative OBV and discards the level |
| 48 | OBV slope | 2 | ABSENT |
| 49 | OBV divergence | 1 | built — `technical_factors.obv_divergence:542` |
| 50 | Accumulation/Distribution | 3 | built — `extended_indicators.accumulation_distribution:224` |
| 51 | Chaikin Money Flow | 1 | built — `extended_indicators.chaikin_money_flow:263` |
| 52 | Chaikin oscillator | 1 | built — `technical_factors.chaikin_oscillator:733` |
| 53 | Money Flow Index | 3 | built — `technical_factors.mf_index:163` |
| 54 | VWAP | 1 | built — `momentum.vwap:49`; `extended_indicators.anchored_vwap:289` |
| 55 | VWAP deviation | 2 | ABSENT — `extended_indicators.anchored_vwap:289` returns the level only |
| 56 | Volume-weighted moving average | 1 | built — `rule_eval.rule_signal_price_above_vwma:142` (rule-level, no leaf) |
| 57 | Relative volume | 1 | built — `momentum.rvol:25`; `volume_flags.rvol_ex_mechanical:90` |
| 58 | Volume spike | 1 | ABSENT |
| 59 | Volume trend | 1 | ABSENT |
| 60 | Volume-price trend | 1 | built — `extended_indicators.vpt:248` |
| 61 | Force Index | 2 | built — `extended_indicators.force_index:206` |
| 62 | Ease of Movement | 1 | ABSENT |
| 63 | Acceleration/deceleration | 1 | ABSENT — `extended_indicators.momentum_oscillator:162` is a fixed-n momentum, not generic `Acceleration(X)` |
| 64 | Candlestick calculations | 5 | built — `extended_indicators.scan_candlesticks:603` (private `_body:537`, `_range_:541`) |
| 65 | Close location | 2 | PARTIAL — CLV computed inline at `extended_indicators.accumulation_distribution:224`, never returned |
| 66 | Intraday strength | 1 | ABSENT |
| 67 | Gap | 1 | built — `market_session.gap_type:220` |
| 68 | Gap continuation | 1 | ABSENT |
| 69 | Gap fill | 1 | PARTIAL — `market_session._gap_fill_stats:167` (private, measured fill stats) |
| 70 | Higher-high / lower-high structure | 5 | built — `value_dip.higher_low_structure:733` |
| 71 | Swing-high / swing-low structure | 2 | built — `extended_indicators.swing_pivots:321`; `swing._pivot_lows:332` |
| 72 | Trend structure | 3 | built — `swing.trend_architecture:76` |
| 73 | Linear regression trend | 3 | built — `relative_strength.slope_pct:49` (mean-normalised OLS slope of any series) |
| 74 | Regression R² | 1 | PARTIAL — computed inside `rotation.clenow_momentum:89`; not exposed as its own read |
| 75 | Trend quality | 1 | PARTIAL — `rotation.clenow_momentum:89` (slope×R² shape, not `Sign(β)×R²`) |
| 76 | Linear regression channel | 3 | ABSENT |
| 77 | Regression-channel position | 1 | ABSENT |
| 78 | Efficiency ratio | 1 | elsewhere — `regime.choppiness:141` (close-only Kaufman ER, inverted; RegimeScore owns it) |
| 79 | Trend-to-noise ratio | 1 | ABSENT |
| 80 | Price z-score | 1 | PARTIAL — `value_dip.zscore:104` (generic helper); `factors.z_score:68` is cross-sectional |
| 81 | Return z-score | 1 | elsewhere — `knife_guard.momentum_return_z:78` |
| 82 | Mean-reversion score | 1 | PARTIAL — `mean_reversion.mean_reversion_verdict:226` returns a label, not a z-composite |
| 83 | Autocorrelation | 2 | PARTIAL — `mean_reversion._ar1_fit:39` (AR(1) coefficient); ACF at lags 1/5/20 absent |
| 84 | Variance ratio | 1 | built — `mean_reversion.variance_ratio:259` |
| 85 | Hurst exponent | 4 | built — `mean_reversion.hurst_exponent:113` |
| 86 | Fractal dimension | 1 | ABSENT |
| 87 | Volatility | 2 | elsewhere — `regime.realized_vol:39`, `volatility_models.ewma_vol:397` (RegimeScore / RiskScore read it) |
| 88 | Downside volatility | 1 | built — `volatility_models.semivariance:68` (`rs_minus` = RS⁻) |
| 89 | Volatility percentile | 1 | built — `regime.vol_percentile:59` |
| 90 | Volatility regime | 1 | elsewhere — `regime_state.regime_vol_ratio:92` |
| 91 | Volatility acceleration | 1 | ABSENT |
| 92 | Range volatility | 1 | PARTIAL — `compression.closing_range_read:123` (bar-width read, not `Std(H−L)`) |
| 93 | Parkinson volatility | 2 | built — `volatility_models.parkinson_vol:155` |
| 94 | Garman-Klass volatility | 1 | built — `volatility_models.garman_klass_vol:185` |
| 95 | Rogers-Satchell volatility | 1 | PARTIAL — RS is a term inside `volatility_models.yang_zhang_vol:288` (`volatility_models.py:301`); no standalone σ_RS |
| 96 | Range expansion | 1 | PARTIAL — `value_dip.range_expansion_guard:1043` is a guard, not the plain `(H−L)/SMA(H−L)` ratio |
| 97 | ATR percentile | 1 | built — `compression.atr_compression_read:75` |
| 98 | Drawdown | 1 | elsewhere — `evaluate.max_drawdown:222`; `regime_state.regime_drawdown:146` (RiskScore) |
| 99 | Maximum drawdown | 1 | elsewhere — `evaluate.max_drawdown:222` |
| 100 | Drawdown recovery | 1 | elsewhere — `book_risk.py:1330` (recovery quantiles; RiskScore) |
| 101 | Time since high | 1 | ABSENT |
| 102 | Distance from high | 1 | elsewhere — `factors.high_distance:35` [CORRECTED 2026-09-26: the symbol name was wrong — `strategies/factors.py` defines `high_distance:35` ("price / trailing high − 1"); there is no `distance_from_52w_high`.] |
| 103 | Distance from low | 1 | ABSENT |
| 104 | Position within range | 1 | ABSENT — `technical_factors.donchian_channel:468` returns `mid`, never the position |
| 105 | Pivot structure | 1 | built — `technical_factors.pivot_distance_atr:318` |
| 106 | Fibonacci retracement | 5 | built — `swing.fib_levels:295`; `value_dip.fib_retrace_entry:904` |
| 107 | Donchian channels | 4 | built — `technical_factors.donchian_channel:468` |
| 108 | Keltner Channels | 4 | built — `technical_factors.keltner_channel:440` |
| 109 | Keltner/Bollinger squeeze | 2 | built — `technical_factors.squeeze_momentum` (BB inside KC + the release flag vs the prior bar's ATR) [CORRECTED 2026-09-27: `TECH-7`/`TECH-12`'s remaining leg.] |
| 110 | TTM-style squeeze momentum | 2 | built — the same producer's `momentum`/`direction` at the release (the §30 ATR-normalised move, since this item gives no formula) [CORRECTED 2026-09-27: the formula choice is declared in the module docstring.] |
| 111 | Aroon | 3 | built — `technical_factors.aroon:668` |
| 112 | TRIX | 4 | built — `extended_indicators.trix:173` |
| 113 | DPO | 1 | ABSENT |
| 114 | Ultimate Oscillator | 3 | ABSENT |
| 115 | Awesome Oscillator | 2 | ABSENT |
| 116 | Relative Vigor Index | 2 | ABSENT |
| 117 | Coppock Curve | 1 | ABSENT |
| 118 | Know Sure Thing | 1 | built — `technical_factors.kst:104` |
| 119 | Technical breadth | 2 | built — `market_breadth.market_breadth:114` (engine's `pct_above_50d`/`pct_above_200d`); `sector_breadth.multi_breadth:165` |
| 120 | Technical breadth thrust | 1 | built — `technical_depth.zweig_breadth_thrust:400` (the EMA of adv/(adv+dec) and the Zweig event) is now a LEG of the `breadth` category (`technical_score.COMPONENTS['zweig_thrust']`, ramp 0.0-0.20 = this item's own 0.40→0.615 event) [CORRECTED 2026-09-27: owner decision: a leg, not a new weight; `CATEGORY_WEIGHTS` unchanged.] |
| 121 | New-high/new-low technical breadth | 2 | built — `market_breadth.market_breadth:114` (`net_new_highs_52w`) |
| 122 | Relative technical strength | 1 | PARTIAL — `sector_screener._rel_outperformance:248` (ETF/sector level; no per-name sector-median) |
| 123 | Technical factor normalization | 4 | PARTIAL — `value_dip.zscore:104`, `factors.z_score:68`, `normalized.percentile_hist_or_none:40`; no registry applies them across indicators |
| 124 | Sector-relative technical normalization | 1 | PARTIAL — `sector_screener._rel_outperformance:248`; no per-indicator sector-median normaliser |
| 125 | Technical subscores | 8 | built — `technical_score.category_score` + `CATEGORY_COMPONENTS` (nine categories; the library's eight groups lack a Setup-Quality sub-score) |
| 126 | Composite TechnicalScore | 1 | built — `strategies/technical_score.py::technical_score`; leaf `agents/utils/analysis_tools.py::get_technical_score:6012` |
| 127 | Redundancy control (not 100 indicators voting) | 0 | ABSENT — no indicator-correlation producer; nearest `consensus.agreement_score:14` is sentiment-rating dispersion |
| 128 | Recommended indicator clusters | 1 | PARTIAL — `technical_score.CATEGORY_COMPONENTS` (nine categories; the library's setup-quality cluster absent) |
| 129 | Technical State | 1 | built — `technical_score.technical_state` (the library's state names, from five directional legs + ADX) [CORRECTED 2026-09-27: `TECH-23`; states the library does not name are recorded as unbound rather than invented.] |
| 130 | Technical acceleration | 2 | built — `technical_score.technical_acceleration` returns velocity (this item's first difference), acceleration (the second) and jerk (the third), naming the divergence [CORRECTED 2026-09-27: the ticket asked for the second difference; the library calls the second `TechnicalJerk`.] |
| 131 | Technical disagreement | 2 | built — `technical_score.technical_disagreement` over the category sub-scores, returning the inputs it compared [CORRECTED 2026-09-27: `TECH-23`.] |
| 132 | Technical coverage | 2 | built — `technical_score.technical_score` returns `coverage`/`floor`; `score_engine.coverage_floor:53` |
| 133 | Recommended architecture | 1 | PARTIAL — realised as `strategies/technical_score.py` (nine categories + composite + coverage); no acceleration/disagreement node |

**Count: 54 `built`, 37 `PARTIAL`, 34 `ABSENT`, 8 `elsewhere`.**

### 8.2 Not built — the backlog the library names

Grouped by family; the largest gaps carry the smallest honest producer already in
the repo. Every one of these is a **backlog** row, not a defect claim.

| Family | Library sections | Smallest honest producer |
| --- | --- | --- |
| **Bollinger-bandwidth family** — the widest single gap: `BBW`, its percentile, the contraction squeeze, expansion and the mean-reversion distance | 21, 22, 23, 24, 25 | `value_dip.bollinger_pct_b:77` already builds `mid`/`upper`/`lower`; `BBW=(UB−LB)/MB` and its percentile are two lines over the same window, and `compression.atr_compression_read:75` is the existing percentile-of-own-history template |
| **Regression family** — R², trend quality, channel and channel position, trend-to-noise, efficiency ratio | 74, 75, 76, 77, 78, 79 | `rotation.clenow_momentum:89` already fits `linregress` (slope and R²); `relative_strength.slope_pct:49` is the shared normalised-OLS helper and `regime.choppiness:141` the ER |
| **Legacy oscillators** — DPO, Ultimate Oscillator, Awesome Oscillator, RVI, Coppock, EOM | 62, 113, 114, 115, 116, 117 | the module shape is `technical_factors.py` (one pure `def` per indicator, `None` below min-obs); `technical_factors.ema:40`/`_sma:24` are the smoothers each needs |
| **Score-layer state** — redundancy control, the state enum, acceleration, disagreement | 127, 129, 130, 131 | `strategies/technical_score.py::technical_score` already returns per-category sub-scores and coverage, so dispersion/acceleration are readers of its own output; the state enum is `TECH_BANDS` widened |
| **OBV depth** — the OBV level and its slope | 47, 48 | `technical_factors.obv_divergence:542` computes the cumulative series and discards it (`obv` at the loop) |
| **Breakout depth** — persistence, false breakout | 43, 44 | `technical_factors.donchian_channel:468` now returns `breakout_ref_up`/`breakout_ref_dn`, the checkable breakout level persistence is measured against |
| **Volume depth** — volume spike, volume trend, volume-confirmed ratio | 58, 59, 45 | `momentum.rvol:25` and `volume_flags.rvol_ex_mechanical:90` are the existing RVOL producers |
| **Moving-average depth** — WMA, HMA, EMA slope, crossover spread/velocity, EMA5/EMA20 stack | 2, 4, 5, 6 | `technical_factors.ema:40` returns the full series; `swing.trend_architecture:76` already emits two slope booleans |
| **MACD depth** — crossover, ATR-normalised spread, histogram acceleration | 7, 8 | `value_dip._macd_hist:502` returns `(line, signal, hist)`; `rule_eval.rule_signal_macd_hist_rising:103` is the one-bar-delta template |
| **Candle/gap depth** — intraday strength, gap continuation, continuous gap fill | 66, 68, 69 | `extended_indicators.scan_candlesticks:603` and `market_session.gap_type:220` already hold the OHLC they need |
| **RSI depth** — slope/acceleration, continuous divergence | 11, 12 | `value_dip._rsi_series:472` is a full Wilder series; `value_dip.macd_divergence:542` already reads RSI divergence |
| **Range/position depth** — time since high, distance from low, position within range | 101, 103, 104 | `technical_factors.donchian_channel:468` returns the `upper`/`lower` the three need |
| **Breadth depth** — breadth thrust | 120 | `market_breadth.advance_decline_line` returns the per-session `advancers`/`decliners` and the leaf feeds `technical_depth.zweig_breadth_thrust` from the same panel [CORRECTED 2026-09-27: WIRED 2026-09-27 (TECH-14).] |
| **ATR depth** — ATR expansion/contraction ratio, ATR-normalised movement, vol acceleration, standalone Rogers-Satchell | 28, 29, 30, 91, 95 | `size.atr:143` (series via the cached 320 bars), `compression.atr_compression_read:75`, `volatility_models.yang_zhang_vol:288` |
| **Keltner/TTM squeeze** | 109, 110 | `technical_factors.keltner_channel:440` and `value_dip.bollinger_pct_b:77` already return both band pairs the squeeze compares |

### 8.3 Library-internal defects

Verified by reading the library only — every item is a repetition, a duplicate
symbol or a false label **inside** `Strategies/scores/technical_score.md`.

| # | Defect | Where | Why it is wrong |
| --: | --- | --- | --- |
| 1 | **ROC defined twice** | §1 "N-period ROC" (`100(C_t−C_{t−n})/C_{t−n}`) vs §16 "ROC" (`((C_t−C_{t−n})/C_{t−n})×100`) | identical formula in two numbered sections — one quantity, two section numbers |
| 2 | **Normalised momentum defined twice** | §17 `NormalizedMomentum=(C_t−C_{t−n})/ATR_n` vs §30 `ATRMove=(C_t−C_{t−n})/ATR_n` | same expression, two names, two sections |
| 3 | **Money-flow multiplier ≡ close-location value** | §50 `MFM=((C−L)−(H−C))/(H−L)` vs §65 `CLV=((C−L)−(H−C))/(H−L)` | identical expression under two symbols; both are cited as the A/D input |
| 4 | **Rolling support/resistance ≡ Donchian levels** | §40 `Resistance_n=HighestHigh_n`, `Support_n=LowestLow_n` vs §107 `DCUpper_n`/`DCLower_n` | the same two quantities named twice; §41/§42 then reuse them a third time |
| 5 | **VWAP ≡ VWMA** | §54 `ΣP_iV_i/ΣV_i` vs §56 `ΣC_iV_i/ΣV_i` | the same weighted mean with `P=C`; two sections for one calculation |
| 6 | **`MRScore` defined twice with incompatible inputs** | §82 `MRScore=−w₁ZPrice−w₂RSI_Z−w₃ROC_Z` vs §125 `MRScore=f(RSI, ZPrice, BBPosition, DistanceToMA, Autocorrelation)` | same symbol, different inputs; §82's own text says the **sign is undecided** ("depends on whether you're scoring reversion opportunity or current trend quality") |
| 7 | **`TechnicalScore` composite defined three times, three weight vectors** | §126 (8 groups), §128 (`Σ w_k ClusterScore_k`, 7 clusters), §133 (`w₁Trend+…+w₈`, 9 nodes) | three incompatible composites under one symbol; none matches the owner's nine-category table the engine implements |
| 8 | **"Downside volatility" is a false label** | §88 `σ_down=Std(min(r,0))` | `min(r,0)` keeps a **zero for every up-return**, so the standard deviation is taken over a mixed series — it is neither a downside deviation nor the semivariance leg, and it understates downside dispersion |
| 9 | **`f` is a placeholder** | §33 `TrendStrength=f(ADX)` | `f` is never defined; the section offers no formula, only the name |
| 10 | **Four symbols have no definition** | §127 (redundancy control), §129 (`TechnicalState` enum), §130 (`TechnicalAcceleration`/`Jerk`), §131 (`TechnicalDispersion`/`Agreement`) | named, never given a formula — design intent, not library |

### 8.4 Contradictions between the library and the code

The engine's band-mapping rule (§0.3: a non-monotonic input walks a piecewise
band table, first edge cleared wins) is the comparison for every library formula
the engine band-maps. Reported, not changed.

| # | Library says | Code does | Kind |
| --: | --- | --- | --- |
| 1 | §88 downside volatility is `Std(min(r,0))` — a dispersion of a zero-padded series | `volatility_models.semivariance:68` defines the downside leg as `RS⁻=Σ min(r,0)²/n` and insists `RS⁻+RS⁺=RV` **exactly**; its docstring states a conditional/truncated σ is "confounded with drift" and "not what this returns" | **object/sign** — the library's quantity is not the code's, and the code rejects the library's construction |
| 2 | §10 `RSIOversold=30−RSI` — a *positive, rising* value as RSI falls below 30, i.e. **low RSI is the signal** | `technical_score.BANDS["rsi"]` scores RSI `<40` at **20** (its weakest band) and 45–70 at 85 | **band vs ramp / opposite sign** — the same input is favourable-low in the library and unfavourable-low in the engine |
| 3 | §126 composite weights are Trend 20, Momentum 20, Volatility 10, S/R 15, Volume 10, MR 10, Structure 10, Setup 5 — **no Relative Strength, no Breadth** | `technical_score.CATEGORY_WEIGHTS` is the owner's nine categories (Trend 20, Momentum 18, RS 12, PS 12, Volume 10, Breakout 10, MR 8, Volatility 5, Breadth 5) | **weight vector + component set** |
| 4 | §108 Keltner position is a bounded `(C−Lower)/(Upper−Lower)` with **no stated preferred band** | `technical_score.BANDS["keltner_pct"]` scores `0.5–1` at 70, `0–0.5` at 50, `>1` at 25, `<0` at 35 — and the doc's §0.3 calls "mid-band" the read, which the table does not implement | **band defined where the library defines none** (readme/doc-vs-code tension) |
| 5 | §89 `VolPercentile=PercentileRank(σ_n)` implies a **measured** rank | `regime.vol_percentile:59` returns `None` when `len(wins) < 2` — no fabricated 0.5 today, but the doc's §1 volatility row still records the old `0.5` behaviour as current | **stale doc claim** (the library is satisfied; the doc row is not). **[CORRECTED 2026-09-26: the §1 row now carries the dated correction and no longer records the `0.5` as current — this contradiction is closed.]** |
| 6 | §27 `NATR = 100·ATR_n/C_t` (**percent**) | engine `atr_pct` is passed as `size.atr:143` **/ last close** (a fraction) against `RAMPS["atr_pct"]=(0.010, 0.050)` | **scale** — both are the same quantity; the 100× is the seam |
| 7 | §13/§53 define stochastic and MFI as formulas with **no band** | `technical_score.BANDS["stoch_k"]`, `BANDS["mfi"]` band-map both (`>80`→30/25, `<20`→80) | engine policy the library does not supply — divergence, not error |
| 8 | **[FIXED 2026-09-26]** `score_engine.NON_MONOTONIC_INPUTS:41` now names the component keys (`stoch_k`, `stoch_rsi`, `elder_ratio`), and `tests/test_scorecard_contracts.py::test_the_declared_set_is_not_larger_than_the_engine_can_show` forbids the whitelist that hid it; as found, it named `"stochastic"`, `"stochrsi"`, `"elder_thermometer"` while the engine's own components/BANDS are `"stoch_k"`, `"stoch_rsi"`, `"elder_ratio"` | `analysis_tools._non_monotonic_triples:5916` intersects on the component name, so **three of the nine** non-monotonic inputs never print their raw→aligned mapping triple | **code defect** (name mismatch), verified by reading both files |

---

## Appendix — methodology ledger

| Claim | Source | Where it bites |
| --- | --- | --- |
| Time-series momentum (own-history sign) and cross-sectional momentum (relative ranking) are related but **different** signals | Moskowitz, Ooi & Pedersen (2012) | the owner's "trend"/"momentum" categories are TSMOM-shaped; "relative strength" is CSMOM — the three must be named as distinct, and their correlation measured |
| Momentum has a distinct **tail-risk profile**: crashes concentrate after market declines and during rebounds, and are forecastable | Daniel & Moskowitz (2016) | the score is a state description, not a forecast (§0.4) |
| A simple moving-average trend filter historically reduced drawdowns | Faber (2007) | the SMA/EMA stack in `swing.trend_architecture:76` is this family — and its evidence is about *drawdown*, not about return |
| Trend filters, MA rules and TSMOM harvest **one latent factor**; stacking them double-counts | the composite-indicator double-counting literature | the redundancy step (§0.4) and the 50% weight sitting on correlated inputs |
| Momentum-crash risk is *state-dependent*, so momentum's payoff cannot be read without the regime | Daniel & Moskowitz (2016) | why `RegimeScore` and `TechnicalScore` stay separate (master §1.1) |
| Realized **semivariance** splits volatility into an upside and a downside leg with `RS⁻ + RS⁺ = RV` exactly; **downside semivariance is the more persistent and more forecast-relevant leg**, and negative jumps raise future volatility while positive jumps lower it — "bad" vs "good" volatility | Patton & Sheppard (2015), *Good volatility, bad volatility: signed jumps and the persistence of volatility* | §1's three new volatility rows and §4's producer: the **downside** leg carries the risk weight, and a conditional `StdDev(r \| r<0)` is a different object that does not decompose |
| High **idiosyncratic volatility** predicts **lower** next-month returns (the IVOL puzzle), and high-beta / high-volatility stocks underperform low-volatility ones, explained by benchmark-constrained arbitrage limits | Ang, Hodrick, Xing & Zhang (2006); Baker, Bradley & Wurgler (2011) | the direction column of **every** volatility row: volatility is risk-increasing, never a favourable score on its own. The repo already screens the same family from the other side — `get_lottery_factors:8739` → `strategies/lottery.py:88 lottery_verdict`, bound at `toolsets.py:287` |
| Stocks with a high **maximum** daily return (the lottery / MAX effect) subsequently underperform | Bali, Cakici & Whitelaw (2011) | the same row: "high volatility = opportunity" is in direct tension with a screen the repo already ships |
