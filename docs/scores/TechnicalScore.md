# TechnicalScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master —
architecture, cross-engine rules, the composite, the code defects, the phase plan,
the open questions). Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`RegimeScore.md`](RegimeScore.md), [`NewsScore.md`](NewsScore.md),
[`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
[`RiskScore.md`](RiskScore.md).

**Scope: the technical engine only.** It designs `TechnicalScore` — *"what is
this stock doing?"* — from the owner's nine categories in
[`../ScoreWeight/market.md`](../ScoreWeight/market.md). The environment the stock
trades in is `RegimeScore`; how much the position can hurt is `RiskScore`. This
document must not absorb either.

Status: **design (2026-09-17). Not started.** The components largely exist; the
**composite does not exist anywhere** (§0.1).

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
  `factors.quality_composite`, `capex_quality`, `data_quality.aggregate_quality`,
  `news_relevance.score_news_article`, `sector_rank.rank_sectors_multifactor:391`
  (sector-ETF level) and `decision_guardrail.SCORE_BANDS:27`. **None is
  technical.**
- Nearest technical-adjacent numbers, each explicitly *not* a technical
  composite: `knife_guard.knife_score:156` (K, higher = **worse**),
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
| RSI | `swing.rsi:39` + `swing.rsi_band:118` | 45-70 is `strong`, >70 is `hot`, <40 is `broken` — a **band**, not a ramp |
| Stochastic K/D | `technical_factors.stochastic_oscillator:146` | <20 is `oversold`, the dip read |
| StochRSI | `technical_factors.stoch_rsi:283` | <0.2 is the entry |
| RSI2 | `technical_factors.rsi2:315` | <10 is the buy |
| Williams %R | `technical_factors.williams_r:338` | -80..-100 is oversold |
| Bollinger %b | `value_dip.bollinger_pct_b:75` | <=0 is the dip, >1 is extended |
| MFI | `technical_factors.mf_index:112` | >80 is overbought |
| Elder thermometer | `technical_factors.elder_thermometer:476` | `quiet` (<0.8) is the good dip read |
| Keltner %b | `technical_factors.keltner_channel:349` | mid-band is the read |
| Support structure | `value_dip.support_structure:714` | *near* the 200-SMA is good, while `swing.trend_architecture:71` says *above* it is good — the same level, opposite signs, depending on the strategy |

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
| **Trend** | 20 | **PARTIAL** | no composite; `swing.trend_architecture:71` (booleans) + `regime_state.regime_trend:65` | `architecture.*` / `race.trend.score` | + | flags + context string / (EMA20-EMA50)/ATR14 | no 0-100 scale, no weighting basis |
| Trend → price vs SMA20/50/100/200 | — | PARTIAL | `swing.trend_architecture:71` computes SMA50, SMA200, EMA20 only | `above_sma50`, `above_sma200` | + | bool | SMA20, SMA100 ABSENT |
| Trend → EMA10/20/50 | — | SCORABLE | `technical_factors.ema:28` (public, any n); `swing._ema_last:29` (n=20); `momentum.ema9:38` | EMA series / `ema9` | + | price units | no leaf prints EMA10/EMA50 |
| Trend → SMA slope | — | SCORABLE | `swing.trend_architecture:71` (`sma50_rising` = 5-bar, `sma200_rising` = 15-bar) | `sma50_rising`, `sma200_rising` | + | bool | windows hardcoded inside the function |
| Trend → EMA slope | — | **ABSENT** | — | — | + | — | grepped `def .*slope` in `strategies/` → only `relative_strength.slope_pct:49`, `sector_screener.classify_regime:108`, `options_surface.term_structure_slope:152` |
| Trend → SMA50 > SMA200 stack | — | SCORABLE | `swing.trend_architecture:71` (`stacked`, `ema20_above_sma50`) | `stacked` | + | bool | — |
| Trend → golden-cross state | — | SCORABLE | `extended_indicators.golden_death_cross:53` | `golden`,`death`,`label` | + | bool/label | 2-bar crossover only (no "state" memory) |
| Trend → ADX | — | SCORABLE | `technical_factors.adx:179` | `adx` | + (>25 strong) | 0-100 | no percentile basis |
| Trend → DI+ / DI- | — | SCORABLE | `technical_factors.adx:179` | `di_plus`,`di_minus` | + (di+) | 0-100 | — |
| Trend → Aroon up / down | — | SCORABLE | `technical_factors.aroon:495` | `aroon_up`,`aroon_down` | + (up) | 0-100 | Aroon OSCILLATOR not computed; a `verdict` string substitutes |
| Trend → Ichimoku cloud state | — | SCORABLE | `extended_indicators.ichimoku:78` | `above_cloud`,`label`,`cloud_leading` | + | bool/label | — |
| Trend → regime trend score | (overlap) | SCORABLE | `regime_state.regime_trend:65` | `score` | + | (EMA20-EMA50)/ATR14, dimensionless | belongs to RegimeScore — naming clash per ground rule 3 |
| Trend → trend filter | — | SCORABLE | `quant_baseline.trend_strength:28` | — | + | 0-1 | UNWIRED (tests only) |
| **Momentum** | 18 | **PARTIAL** | no composite; inputs spread across 5 modules | — | + | — | no aggregation, mixed units |
| Momentum → RSI | — | SCORABLE | `swing.rsi:39` | `rsi.value`,`rsi.label` | **NON-MONO** (45-70 `strong`, >70 `hot`, <40 `broken`) | 0-100 | — |
| Momentum → RSI slope | — | **ABSENT** | — | — | — | — | `swing.rsi:39` returns a scalar; `swing.rsi_band:118` bands it but never differentiates |
| Momentum → MACD line | — | PARTIAL | `value_dip._macd_hist:500` (private) | — | + | price units | no public/leaf producer; only the vendor `get_indicators('macd')` text |
| Momentum → MACD histogram | — | PARTIAL | `value_dip._macd_hist:500`, surfaced only via `value_dip.macd_divergence:540` | `macd_hist_lows` | + | price units | the VALUE is never returned, only two trough lows |
| Momentum → MACD histogram slope | — | **UNWIRED** | `rule_eval.rule_signal_macd_hist_rising:103` | bool | + | bool | only reader is `scripts/rule_eval.py:24` + tests; no leaf |
| Momentum → Stochastic K/D | — | SCORABLE | `technical_factors.stochastic_oscillator:146` | `k`,`d` | **NON-MONO** (<20 `oversold` = good for a dip) | 0-100 | — |
| Momentum → ROC | — | SCORABLE | `extended_indicators.roc:149` (%), `sector_rank._momentum:27` (fraction) | `roc` | + | % or fraction | window is a parameter, not a policy |
| Momentum → momentum 5D | — | **ABSENT** | — | — | + | — | nearest: `knife_guard.momentum_return_z:75` (lookback=3) and `rotation.vol_cones:123` (5d vol, not return) |
| Momentum → momentum 20/60D | — | SCORABLE | `quant_baseline.momentum:17` (horizon default 60) | `momentum` | + | fraction | UNWIRED (tests only) |
| Momentum → momentum 21/63/126/252D (per name) | — | **UNWIRED** | `factors.momentum_multihorizon:400` (horizons 21/63/126/252 + `ensemble`) | `horizons`,`ensemble` | + | fraction | whitelisted unreachable: `tests/test_calc_agent_wiring.py:40` ("legacy factor composite") |
| Momentum → momentum 21/63/126/252D (sector ETF) | — | SCORABLE | `sector_rank._momentum:27` + `_MOMENTUM_WINDOWS:216`, wired in `rank_sectors_multifactor:391` | `ret_1m`,`ret_3m` | + | fraction | ETF level only |
| Momentum → momentum 252D (12-1) | — | SCORABLE | `momentum.momentum_12_1:358`, `factors.momentum:24` (lookback=252, skip=21) | `momentum` | + | fraction | `factors.momentum` consumed by `overlays.build_strategy_overlays:20` (mom60, skip=0) only |
| Momentum → acceleration / deceleration | — | SCORABLE | `sector_rank._acceleration:289` (R63-0.5*R126), `extended_indicators.momentum_oscillator:160` | `accel` | + | fraction / price units | — |
| Momentum → Clenow momentum | — | SCORABLE | `rotation.clenow_momentum:89` | — | + | ratio (exp(slope*252)*R2) | exposed as `get_clenow_momentum` |
| Momentum → KST / MFI | — | SCORABLE | `technical_factors.kst:53`, `technical_factors.mf_index:112` | `kst`,`trigger`,`crossover` / MFI value | **NON-MONO** for MFI (>80 overbought) | 0-100 (MFI) | — |
| **Relative strength** | 12 | **PARTIAL** | no composite; `relative_strength.relative_strength_report:132` returns a verdict, not a score | `verdict` | + | label + slope%/day | no scale to weight |
| RS → stock vs SPY | — | SCORABLE | `relative_strength.rs_series:33`, `relative_strength_report:132` | `rs`,`slope_pct`,`uptrend` | + | ratio + %/day | leaf binds only `benchmark_ticker` (SPY) — `analysis_tools._benchmark_closes:302` |
| RS → stock vs QQQ / sector ETF | — | PARTIAL | `etf_risk.etf_relative_strength:88` (bench_map) | `benchmarks[label][window].relative` | + | fraction | ETF path only (`get_etf_relative_strength:1768`, bound 450); no per-stock QQQ/sector leg |
| RS → RS slope | — | SCORABLE | `relative_strength.slope_pct:49` | `slope_pct` | + | %/day (mean-normalised OLS) | — |
| RS → RS position / new high | — | SCORABLE | `relative_strength.rs_position:89` | `new_high`,`near_high` | + | bool | — |
| RS → RS divergence | — | SCORABLE | `relative_strength.divergence:113` | `divergence` | − (divergence is bad) | bool | — |
| RS → relative rotation (RRG) | — | SCORABLE | `rotation.relative_rotation:43`, `sector_rank.rrg_quadrant:370`, `sector_breadth.rrg_heading:173` | `quadrant` | + | z-units (stock) / 0-100 pct (sector) | two implementations, different normalisation |
| RS → sector- and industry-relative momentum | — | SCORABLE | `sector_rank.rank_sectors_multifactor:391` (`momentum`,`rs`,`rs2`,`rs_momentum`,`quadrant`,`score`), `sector_rank.rank_industry_group:590`, `sector_rank.sector_standing:176`, `sector_screener._rel_outperformance:246` | `score`,`rs`,`rs2` | + | 0-100 percentile (ETF pool) / fraction | ETF/industry level only, never per-name |
| **Price structure & support/resistance** | 12 | **PARTIAL** | no composite; `value_dip.support_structure:714` is the nearest (label) | `verdict` | + (at support) | label | no scale |
| P/S-R → pivot points | — | SCORABLE | `technical_factors.pivot_points:239` | `p`,`r1`,`s1`,`r2`,`s2` | ± (level) | price | daily/weekly only; no distance-to-level metric |
| P/S-R → support structure | — | PARTIAL | `value_dip.support_structure:714` | `verdict`,`distance_to_sma200_pct` | + | label / fraction | the 1.5-ATR branch is DEAD — see §3 |
| P/S-R → volume profile POC / value area | — | PARTIAL | `technical_factors.volume_profile:654` | `poc`,`value_area_high`,`value_area_low` | ± (level) | price | value-area accumulator broken — see §3 |
| P/S-R → Donchian channel | — | PARTIAL | `technical_factors.donchian_channel:377` | `upper`,`lower`,`mid` | ± | price | `breakout_up`/`breakout_dn` are hardcoded `None` — see §3 |
| P/S-R → Fibonacci levels | — | SCORABLE | `swing.fib_levels:290`, `value_dip.fib_retrace_entry:785` | `near_level`,`zone` | + (in golden zone) | price / fraction | — |
| P/S-R → candlestick patterns | — | SCORABLE | `extended_indicators.scan_candlesticks:385` | `patterns{7 bools}` | ± | bool | no magnitude/strength |
| P/S-R → Bollinger %b | — | SCORABLE | `value_dip.bollinger_pct_b:75` | `pct_b` | **NON-MONO** (<=0 dip / >1 extended) | ratio (unbounded) | — |
| P/S-R → Keltner %b | — | SCORABLE | `technical_factors.keltner_channel:349` | `pct`,`mid` | ± | ratio | needs an ATR argument |
| P/S-R → Supertrend line | — | SCORABLE | `technical_factors.supertrend:619` | `line`,`direction` | + (direction up) | price / label | single-bar read, not a trailing series |
| P/S-R → swing-low stop | — | SCORABLE | `swing.swing_low_stop:185` | `stop`,`risk_pct` | − (risk) | price / fraction | — |
| **Volume & accumulation** | 10 | **PARTIAL** | no composite; 4 separate producers in mixed units | — | + | — | — |
| Volume → volume ratio / RVOL | — | SCORABLE | `momentum.rvol:25` | `rvol` | + | ratio (x average) | window 50 default; `value_dip.trigger_candle:625` uses 20 |
| Volume → Elder thermometer | — | SCORABLE | `technical_factors.elder_thermometer:476` | `ratio`,`heavy`,`quiet` | **NON-MONO** (`quiet` <0.8 is the good dip read) | ratio | — |
| Volume → A/D line | — | SCORABLE | `extended_indicators.accumulation_distribution:222` | value | + | share-volume units (unbounded) | cumulative sum, no normalisation |
| Volume → Chaikin oscillator | — | SCORABLE | `technical_factors.chaikin_oscillator:560` | value | + | unbounded A/D units | scale hazard — see §3 |
| Volume → Chaikin Money Flow | — | SCORABLE | `extended_indicators.chaikin_money_flow:261` | value | + (>=+0.1) | -1..1 | — |
| Volume → OBV | — | PARTIAL | `technical_factors.obv_divergence:396` | `obv_up`,`bullish_div` | + | bool | the OBV LEVEL is computed locally and discarded |
| Volume → Force Index / VPT | — | SCORABLE | `extended_indicators.force_index:204`, `extended_indicators.vpt:246` | value | + | unbounded | — |
| Volume → institutional flow | — | SCORABLE | `orderflow.institutional_net:45`, `orderflow.retail_net:49`, `orderflow.summarize:128` | `inst_net`,`distribution_score` | + (inst_net) / − (distribution) | vendor currency units / 0-1 | live moomoo only; degrades to neutral |
| Volume → volume dry-up | — | SCORABLE | `value_dip.volume_dry_up:601` | `dry_up`,`vdu_ratio` | + (low ratio) | ratio | — |
| **Breakout & pullback** | 10 | **PARTIAL** | no composite; state flags in 5 places | — | + | bools/labels | — |
| Breakout → channel breakout | — | PARTIAL | `technical_factors.donchian_channel:377` | `breakout_up/dn` | + | bool | always `None` — see §3 |
| Breakout → opening-range breakout | — | SCORABLE | `market_session.opening_range:72` | `breakout` | + | label `up`/`down`/None | needs intraday bars |
| Breakout → VCP base / near-breakout | — | SCORABLE | `swing.vcp_setup:326` | `candidate`,`near_breakout`,`pivot`,`depths` | + | bool / price / fractions | — |
| Breakout → shelf / first-pullback setup | — | SCORABLE | `sector_screener.setup_a:268`, `sector_screener.setup_b:310` | `state` | + | label | needs sector + constituent context |
| Pullback → pullback into EMA20 | — | SCORABLE | `swing.pullback_setup:156` | `candidate`,`near_ema`,`volume_fade` | + | bool | — |
| Pullback → first pullback (day) | — | SCORABLE | `momentum.first_pullback:210`, `momentum.intraday_pullback:325` | `candidate`,`rr`,`stop` | + | bool / R-multiple | — |
| Pullback → trigger candle | — | SCORABLE | `value_dip.trigger_candle:625` | `trigger`,`rvol` | + | bool / ratio | — |
| Pullback → VDU entry ladder | — | SCORABLE | `value_dip.vdu_entry_setup:670` | `candidate` | + | bool | — |
| Breakout → gap type | — | SCORABLE | `market_session.gap_type:137` | `type`,`fill_probability` | ± | label / prob | fill stats are HARDCODED constants (0.8/0.3/0.4/0.6) — see §3 |
| **Mean reversion** | 8 | **PARTIAL** | no composite; `mean_reversion.mean_reversion_verdict:183` is a label | `verdict` | + | label | no z-scale output |
| MR → mean-reversion z-score | — | PARTIAL | `value_dip.zscore:102` (generic helper) | — | ± | z | no per-series producer wired to any leaf; `factors.z_score:70` is cross-sectional only |
| MR → StochRSI | — | SCORABLE | `technical_factors.stoch_rsi:283` | `stochrsi` | **NON-MONO** (<0.2 oversold) | 0-1 | — |
| MR → RSI2 | — | SCORABLE | `technical_factors.rsi2:315` | value | **NON-MONO** (<10 buy) | 0-100 | — |
| MR → Williams %R | — | SCORABLE | `technical_factors.williams_r:338` | value | **NON-MONO** (-80..-100 oversold) | -100..0 | — |
| MR → Hurst / variance ratio / half-life | — | SCORABLE | `mean_reversion.hurst_exponent:112`, `mean_reversion.variance_ratio:216`, `mean_reversion.ar1_half_life:68`, `mean_reversion.ou_half_life:90` | `hurst`,`vr`,`z`,`half_life` | + (H<0.5 reverting) | 0-1 / ratio / bars | no leaf binds these — verify |
| MR → PSAR reversal flag | — | PARTIAL | `technical_factors.parabolic_sar:432` | `sar` | ± | price | `below`/`exit` always `None` — see §3 |
| MR → OBV divergence | — | SCORABLE | `technical_factors.obv_divergence:396` | `bullish_div` | + | bool | — |
| **Volatility & ATR** | 5 | **PARTIAL** | no composite | — | risk-increasing (higher = more risk; must be inverted for a favourable score) | — | — |
| Vol → ATR | — | SCORABLE | `size.atr:131`; `etf_risk._atr:120` (private); `regime_state._atr14:55` (private) | value | risk-increasing | price units | `size.atr:131` returns **0.0** on failure, not None — see §3 |
| Vol → ATR percentile | — | **ABSENT** | — | — | — | — | grepped `atr_pct|atr_percentile|percentile.*atr` in `tradingagents/` → only `etf_risk.etf_risk_profile:142`'s `atr_pct` (ATR/price, not a percentile) and a prose mention in `tradingagents/data/skills/volume_breakout.yaml:17` |
| Vol → realized volatility | — | SCORABLE | `regime.realized_vol:29`, `quant_baseline.volatility:39`, `etf_risk._realized_vol:69`, `volatility_models.parkinson_vol:48`, `garman_klass_vol:78`, `yang_zhang_vol:116`, `ewma_vol:185`, `garch11_fit:226` | value | risk-increasing | annualised fraction | 8 producers for one quantity — rule 3 naming problem |
| Vol → vol percentile | — | SCORABLE | `regime.vol_percentile:49`; `etf_risk.etf_risk_profile:142` (`vol_percentile`, ETF path only) | `vol_pctile` | risk-increasing | 0-1 | per-name trailing-history percentile only via the ETF leaf |
| Vol → vol cones | — | SCORABLE | `rotation.vol_cones:123` | `{win:{current,p25,p50,p75}}` | risk-increasing | annualised, 0-1 | 5 producers again |
| Vol → ATR-ratio / vol cap | — | SCORABLE | `regime_state.regime_vol_ratio:92`, `regime_state.vol_cap_factor:169`, `knife_guard.atr_ratio_z:112` | ratio / `F_vol` | risk-increasing | ratio / 0-1 scale | — |
| Vol → choppiness index | — | SCORABLE | `regime.choppiness:87` | value | ± | 0-100 | scale mismatch with `overlays.py:57` — see §3 |
| **Breadth & participation** | 5 | **PARTIAL** | sector-level only; market-wide is a vendor TEXT blob | — | + | — | not per-name, not numeric market-wide |
| Breadth → market-wide | — | PARTIAL | `moomoo_extra_tools.get_market_breadth:98` → `dataflows/moomoo.py:get_market_breadth_moomoo:1830` | rendered text only | + | none (string) | no numeric producer anywhere |
| Breadth → sector breadth matrix (%>20/50/200d) | — | SCORABLE | `sector_breadth.multi_breadth:60` | `pct_20d`,`pct_50d`,`pct_200d` | + | 0-100 per ETF | wired only inside `get_sector_rotation_screen:3618` (`analysis_tools.py:3747`) |
| Breadth → McClellan oscillator / MSI | — | SCORABLE | `sector_breadth.mcclellan_read:100`, `sector_breadth.msi_zone:194` | `mo`,`msi`,`zone` | + | oscillator / cumulative index | advisory only; never a gate |
| Breadth → constituent breadth | — | SCORABLE | `sector_rank.constituent_breadth:654` | `pct`,`n` | + | 0-100 | curated 10-name constituent lists (`sector_rank.SECTOR_CONSTITUENTS:585`) |
| Breadth → EW/CW leadership | — | SCORABLE | `sector_rank.leadership_ratio:674`, `sector_screener.leadership_ratio_ewcw:527` | `ratio` | + (>1 broad) | ratio | two implementations |
| Breadth → dispersion trend | — | SCORABLE | `sector_screener.dispersion_trend:161` | `rising/falling/flat` | ± | label | — |
| Breadth → per-name participation | — | **ABSENT** | — | — | — | — | only the vendor `get_capital_flow` (`moomoo_extra_tools.py:18`) string |

---

## 2. Tool leaves (what the analysts can actually call)

Bindings are in `tradingagents/agents/toolsets.py`; `market_tools()` starts at `:224`, `news_tools()` at `:345`, `fundamentals_company_tools()` at `:378`, `fundamentals_etf_tools()` at `:438`.

| Leaf (`function:line`) | Toolset binding (`agents/toolsets.py:line`) | What it returns | Wired? |
| --- | --- | --- | --- |
| `get_indicators:9` (`utils/technical_indicators_tools.py`) | market 228 | vendor indicator window report: `close_10_ema`, `close_50_sma`, `close_200_sma`, `macd`, `macds`, `macdh`, `rsi`, `boll`, `boll_ub`, `boll_lb`, `atr`, `vwma`, `mfi` (`dataflows/y_finance.py:85-154`) | yes |
| `get_technical_factors:5345` | market 293 | ADX/DI±, pivots, Aroon, Fisher, Chaikin, Elder-Ray, Supertrend, volume profile | yes |
| `get_extended_indicators:5406` | market 294 | Ichimoku, golden/death cross, CCI, ROC, momentum osc, TRIX, Force Index, A/D, VPT, CMF, anchored VWAP | yes |
| `get_candlestick_patterns:5473` | market 295 | doji/hammer/shooting-star/engulfing/morning+evening star scan (`extended_indicators.scan_candlesticks:385`) | yes |
| `get_swing_set:351` | market 253 | trend architecture, RSI band, pullback, structure stop, 2R/3R, scale-out, EMA trail, VCP, RS (`swing.swing_report:441`) | yes |
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
| `get_regime_read:964` | market (via market_tools list) | regime label + position scale + mom60 + 52w distance (`overlays.build_strategy_overlays:20`) | yes |
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

Searched (all three trees): `technical.?score|tech_score|technical_score|TechnicalScore` → zero matches in `TradingExecution` and `trading_web`; in `TradingAgents` only prose in design documents (the score-engine set in `docs/scores/`, `docs/ScoreWeight/market.md:38-131`) and `CHANGELOG.md`. `trend_score` → `agents/utils/analysis_tools.py:9247` (a **tool argument**, not a producer), `strategies/skills.py:109-120` (threshold reader), `tests/test_skill_overlays.py:41-50`, and live artifacts (`ToolCallLog/ASML_tool_calls.jsonl:14` trend_score=28, `HPE:9` =65, `MSFT:187` =72 — model-authored numbers). `\*\s*100\.0` + `score.*0-100` → the only producers emitting 0-100 are `factors.quality_composite` (fundamental peer percentile), `capex_quality` (fundamental), `data_quality.aggregate_quality` (data quality), `news_relevance.score_news_article` (news relevance), `sector_rank.rank_sectors_multifactor:391` (sector ETF level), `sector_screener.grade_for:124` (grade band), `decision_guardrail.SCORE_BANDS:27`. None is technical. Nearest technical-adjacent numbers, each not a technical composite: `quant_baseline.quant_signal:74` (score ≈[-1,1], UNWIRED — whitelisted as unreachable legacy, `docs/scores/FundamentalScore.md:242`), `knife_guard.knife_score:156` (K ≈0..3+, higher = **worse**), `regime_state.regime_trend:65` ((EMA20-EMA50)/ATR14, ATR units), `sector_rank.rank_sectors_multifactor:391` (0-100, ETF pool). The executor has the 0-100 `opportunity_score` slot but no technical producer; the web repo has none.

| # | Defect | Lines that disagree | What a reader sees wrong today |
| --: | --- | --- | --- |
| 1 | Donchian breakout flags are hardcoded `None` and **no caller derives them** | `strategies/technical_factors.py:390-391` (`"breakout_up": None,  # closes not passed; caller derives`) vs the leaf `agents/utils/analysis_tools.py:1160` (`get_mean_reversion_tech` prints only `d.get('upper')`/`d.get('lower')`) | a "Donchian breakout" component is unscorable from the only leaf that calls it; `value_dip.value_dip_setup:974` also stores the same None row |
| 2 | `parabolic_sar` is called without `closes`, so `below`/`exit` are always `None` | `technical_factors.parabolic_sar:432` (flag only when `closes is not None`) vs `analysis_tools.py:1160` → `_psar(data["highs"], data["lows"])` | a "close below SAR = downtrend exit" read never fires; only the raw SAR level is reported |
| 3 | `volume_profile` value-area accumulator is dead arithmetic: `acc` is incremented then immediately overwritten, and the moved bin is re-added in a branch that is then discarded | `technical_factors.volume_profile:688-692` (`acc += vol_by_bin[lo_i] if lo_i != hi_i else 0` then `acc = sum(vol_by_bin[lo_i : hi_i + 1])`) | the value area can collapse to the whole price range — measured in `reports/AMAT_20260914_191359/tool_evidence.json:3341`: `poc=169.5614 va_high=424.6382 va_low=169.5614` on a 424 close |
| 4 | `get_position_risk_multiplier` takes `knife_factor` (0..1) from the LLM; no leaf computes the composite K for the market analyst | `agents/utils/quant_adds_tools.py:96-125` (argument default `1.0`) vs `strategies/knife_guard.py:156` (`knife_score`, whose only caller is `value_dip.value_dip_setup:974`) | a "computed execution multiplier" is fed an invented factor; a 0.0 (block) or 1.0 (no reduction) both look measured |
| 5 | `get_skill_read` accepts a 0-100 `trend_score` from the model and can fold YAML constants onto it, printing a number that looks computed | `agents/utils/analysis_tools.py:9247` (`trend_score` argument) + `:9294-9300` ("Folded score (advisory)") vs `strategies/skills.py:117-120` (thresholds on the same opinion) | the report can quote "trend_score=72" / "Fold 60 + 12 = 72.0/100" with no producer behind either number; the live tool-call log shows exactly that (`ToolCallLog/MSFT_tool_calls.jsonl:187`) |
| 6 | `support_structure`'s primary branch is unreachable from the only leaf: the leaf passes no `atr_value`, so the "within 1.5 ATR of base low" test is skipped | `strategies/value_dip.py:738` (`if a is not None and ... ` — `a` is `None` when no ATR) vs `agents/utils/value_dip_tools.py:1018` (`support_structure(closes, highs, lows)`) | "multi-month-base-support" can never be emitted; only the 3%-proximity and holding-above-base branches fire |
| 7 | `size.atr` returns **0.0**, not None, on insufficient data — an NA→0 violation on the volatility input | `strategies/size.py:131-140` (`def atr(...) -> float: ... return 0.0`) vs the repo's own no-fabrication contract (`factors.py:5`, `technical_factors.py:12`) | a caller that checks `atr is not None` treats "unknown volatility" as "zero volatility"; `technical_factors.keltner_channel:349` only survives because it also tests `<= 0` |
| 8 | `rank_sectors_multifactor` substitutes `0.0` for a missing percentile in the risk leg, then emits a score | `strategies/sector_rank.py:536` (`0.6 * (s if s is not None else 0.0) + 0.4 * (d if d is not None else 0.0)`), guarded by `if (s is not None or d is not None)` | a sector with unmeasurable drawdown is scored as if it had the WORST drawdown percentile (0.0 is the floor of a higher-is-better percentile) — NA becomes a penalty, against ground rule 1 |
| 9 | `regime_label`'s chop branch is dead for the only caller: `overlays` passes `chop=0.4` against a default `chop_threshold=0.30`, while the canonical choppiness producer returns 0-100 | `strategies/overlays.py:57` (`regime_label(vol_pct, trend, 0.4)`) vs `strategies/regime.py:133` (default 0.30) and `regime.py:87` (`choppiness` returns 0-100) | with the common `vol_pct == 0.5` (`overlays.py:43` builds a 3-valued proxy) both prior branches miss and `0.4 <= 0.30` is False → the label is `neutral` regardless of trend; a quoted `regime=neutral` carries no information |
| 10 | `rule_eval.rule_signal_macd_hist_rising` (the only MACD-histogram-slope producer) has no production reader | `strategies/rule_eval.py:103` / registered at `:156` vs its only importers `scripts/rule_eval.py:24` and `tests/test_signal_action_sizing_ruleeval.py:14` | the MACD-histogram-slope sub-factor is unscoreable from any analyst tool |
| 11 | `gap_type`'s fill statistics are hardcoded constants, not measurements | `strategies/market_session.py:178-193` (`fill_prob=0.3/0.6/0.4/0.8`, `days=5/3/4/2` literal per branch) | a "fill probability" is printed as if measured from history; it is a 4-way lookup table (ground rule 6: measure, don't assume) |
| 12 | `chaikin_oscillator` returns an unbounded A/D-unit difference while the leaf labels it "positive=buying pressure" — the sign is a scale artefact, not a verdict | `technical_factors.chaikin_oscillator:560` (`round(ema_fast[-1] - ema_slow[-1], 4)`, raw share-volume units) vs `analysis_tools.py:xxxx` in `get_technical_factors:5345` (the `(positive=buying pressure)` suffix) | `reports/AMAT_20260914_191359/tool_evidence.json:3341` shows `chaikin=869687.156 (positive=buying pressure)` on a name the same block reports as `aroon … downtrend`, `di- > di+`, `sup... |

---

## 4. What is ABSENT / PARTIAL, and the smallest honest producer

| Missing piece | Data needed | Does the engine already fetch it? | Smallest honest producer |
| --- | --- | --- | --- |
| **Composite TechnicalScore (0-100)** | nothing new — the components below | yes, all inputs are the run's OHLCV (`analysis_tools._ohlcv:236`) | one pure function `strategies/technical_score.py` taking the already-computed component dicts, with the owner's weight table and a per-component direction (the 5 NON-MONO rows must be band-mapped, not passed through) |
| PCA/EMA slope, RSI slope | the existing EMA/RSI series | yes — `technical_factors.ema:28` returns the full series; `swing.rsi:39` returns only the last value | reuse the existing normalised-OLS helper `relative_strength.slope_pct:49` (it takes any series) — for RSI, promote `value_dip._rsi_series:470` (already a full Wilder series) to public |
| MACD line + histogram values (+ slope) | closes | yes — `value_dip._macd_hist:500` already returns `(line, signal, hist)` series | make `_macd_hist` public and add the three lines to `get_extended_indicators:5406`; slope = last minus prior bar (the same one-bar delta as `rule_eval.rule_signal_macd_hist_rising:103`) |
| momentum 5D | closes | yes | `extended_indicators.roc:149` is already parameterised — `roc(closes, 5)`; `factors.momentum_multihorizon:400` accepts a custom `horizons` tuple |
| ATR percentile (and per-name vol percentile) | a trailing ATR series | yes — `size.atr:131` over the cached 320-bar OHLCV | the loop already written for realized vol at `etf_risk.etf_risk_profile:163-172` (63d rolling windows over ~3Y, then `sum(x < cur)/n`) with `size.atr` in place of `_realized_vol:69`; note `regime.vol_percentile:49` is the same shape but takes a list of histories |
| OBV value (not just divergence) | closes + volumes | yes — `technical_factors.obv_divergence:396` computes the cumulative OBV and discards it (local `obv` at `:404`) | return the last OBV value alongside `obv_up` |
| Donchian breakout state | closes (already available in the leaf) | yes — `get_mean_reversion_tech:1160` has `closes` in scope | pass `closes` into `donchian_channel:377` (the docstring's stated caller contract) or derive in the leaf |
| PSAR exit state | closes | yes — same leaf | pass `closes=` to `parabolic_sar:432` (the parameter already exists) |
| mean-reversion z-score per series | the series | yes | `value_dip.zscore:102` is generic; apply it to `bollinger_pct_b` history / `Rsi` history / price-vs-Keltner and expose one z per signal |
| Per-name RS vs QQQ and vs the sector ETF | the benchmark series | yes — `_ohlcv` fetches any symbol, `_bench_ohlcv:1722` exists for SPY/QQQ/XLK, and `sector_rank.sector_group_of:163` maps a GICS sector to its SPDR ETF | call `relative_strength.relative_strength_report:132` once per benchmark (it is benchmark-agnostic) or use `etf_risk._period_ret:35`'s multi-window shape for the 21/63/126/252 legs |
| Market-wide numeric breadth | advance/decline, % above 50/200d for the US universe | partially — constituent closes are already fetched in bulk for the sector screens (`analysis_tools.py:3646-3748`, `sector_screener.constituent_universe:448`) | aggregate `sector_breadth.multi_breadth:60` across sectors instead of per-sector (the same function already accepts a `{name: closes}` map and returns per-key percentages) |
| Per-name participation / ADV share | volume history + account size | yes — `_ohlcv` volumes; `liquidity_risk.volume_share_slippage` is whitelisted legacy | `momentum.rvol:25` normalised by `elder_thermometer:476`'s 21-bar average is the honest ratio; the repo already has the slippage model in `strategies/liquidity_risk.py` |
| Momentum multi-horizon per name (already built, unreachable) | closes | yes | delete the `tests/test_calc_agent_wiring.py:40` whitelist and wire `factors.momentum_multihorizon:400` — or accept it as legacy and re-derive from `sector_rank._momentum:27` |

Note for the document: five NON-MONO rows are confirmed by reading, not assumed — `swing.rsi_band:118` (mid-band "strong"), `technical_factors.mf_index:112` (oversold good), `technical_factors.stochastic_oscillator:146` (`oversold` flag), `technical_factors.elder_thermometer:476` (`quiet` = good dip), and `value_dip.support_structure:714` (near the 200-SMA is *good*) against `swing.trend_architecture:71` (above the 200-SMA is good).

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
   `risk/sizing.py`. The existing sizing inputs (`size.atr:131`,
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

## 7. Open questions

1. **Does the owner want a technical *score* or a technical *state*?** Six of the
   nine categories are state descriptions (trend, structure, breakout), three are
   oscillators. A single 0-100 mixes them; the alternative is a score plus a
   state label, which the repo already does elsewhere
   (`regime_state.regime_state:215` returns four labels plus a factor).
2. **Which benchmark for relative strength?** Today the leaf binds only SPY
   (`analysis_tools._benchmark_closes:302`). The owner names SPY, QQQ *and* the
   sector ETF; the sector map exists (`sector_rank.sector_group_of:163`) but no
   per-stock QQQ/sector leg is wired.
3. **Intraday or daily?** `market_session.opening_range:72` and
   `momentum.intraday_pullback:325` need intraday bars; the rest of the engine is
   daily. The score's horizon must be stated once, not per component.
4. **Does the volatility category invert?** Volatility is *risk-increasing*: a
   favourable technical score arguably wants **low** volatility (or a *volatility
   contraction* — VCP — which is what `swing.vcp_setup:326` already detects). The
   owner's 5% weight does not say which.

---

## Appendix — methodology ledger

| Claim | Source | Where it bites |
| --- | --- | --- |
| Time-series momentum (own-history sign) and cross-sectional momentum (relative ranking) are related but **different** signals | Moskowitz, Ooi & Pedersen (2012) | the owner's "trend"/"momentum" categories are TSMOM-shaped; "relative strength" is CSMOM — the three must be named as distinct, and their correlation measured |
| Momentum has a distinct **tail-risk profile**: crashes concentrate after market declines and during rebounds, and are forecastable | Daniel & Moskowitz (2016) | the score is a state description, not a forecast (§0.4) |
| A simple moving-average trend filter historically reduced drawdowns | Faber (2007) | the SMA/EMA stack in `swing.trend_architecture:71` is this family — and its evidence is about *drawdown*, not about return |
| Trend filters, MA rules and TSMOM harvest **one latent factor**; stacking them double-counts | the composite-indicator double-counting literature | the redundancy step (§0.4) and the 50% weight sitting on correlated inputs |
| Momentum-crash risk is *state-dependent*, so momentum's payoff cannot be read without the regime | Daniel & Moskowitz (2016) | why `RegimeScore` and `TechnicalScore` stay separate (master §1.1) |
