# RegimeScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`NewsScore.md`](NewsScore.md),
[`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
[`RiskScore.md`](RiskScore.md), [`MarketScore.md`](MarketScore.md),
[`ValuationScore.md`](ValuationScore.md).

**Scope: the regime engine only.** It designs `RegimeScore` — *"what environment
is this stock trading in?"* — from the owner's eight categories in
[`../ScoreWeight/market.md`](../ScoreWeight/market.md). What the *stock* is doing
is `TechnicalScore`; how much the position can hurt is `RiskScore`. The owner's
own illustration of the distinction: *"MSFT's individual short-term tape can
deteriorate while the broader market regime remains constructive."*

Status: **built (2026-09-18); gate off by default.** `strategies/regime_score.py` is the engine, `get_regime_score` its leaf and `enable_regime_score` its membership switch. The two independent regime paths §0.1 describes still exist and still disagree on live data; the score prints both unreconciled rather than choosing between them (plan §9 Phase B exit). **Unmeasured** (vendor gate).

---

## 0. What this engine answers, and the two paths that already disagree

### 0.1 The name collision — `get_regime_read` vs `get_regime_state`

The reported MSFT "regime conflict" is **not a contradiction in the data**; it is
two different functions sharing one word. They share no inputs, no scales and no
label vocabulary, so they can disagree for the same name on the same day, and
both are bound to the market analyst.

| | **Path A — single label** | **Path B — multi-axis** |
| --- | --- | --- |
| Entry | `analysis_tools.get_regime_read:1146` → `overlays.build_strategy_overlays:47` | `quant_adds_tools.get_regime_state:20` → `regime_state.regime_state:215` |
| Also called by | the pre-graph fold `graph/trading_graph.py:778` | — |
| Inputs | the **analysed ticker's own closes** (≥60 bars) | closes + highs/lows + benchmark (`_benchmark_closes:302`, SPY) |
| Volatility | a 3-valued proxy `vol_pct ∈ {0.1, 0.5, 0.9}` (`overlays.py:41-55`) | ATR14/median(ATR14) ratio (`regime_vol_ratio:92`) |
| Labels | `{high_vol, bull, bear, neutral}` + a volatility-target `position_scale` | four axes: trend (STRONG_BULL/BULL/BEAR/STRONG_BEAR), volatility (LOW/NORMAL/HIGH/EXTREME), relative (UNDERPERFORM/NEUTRAL/OUTPERFORM), drawdown (NORMAL/CORRECTION/BEAR/SEVERE) + a crash flag + `F_regime` |
| Gate | `enable_strategy_overlays` (**default True**, `default_config.py:806`) | `regime_state_enable` (**default False**, `default_config.py:845`) at `trading_graph.py:905` |
| Sizing | the overlay's `position_scale` **is** applied by default | its size fold is off by default |

**Design consequence: a `RegimeScore` must name one producer per component, or
arbitrate with a stored reason.** The master's rule 3 (one number, one producer)
is not a formality here — the engine already ships two labels for one word, and a
third (the score) must not become a fourth.

### 0.2 The owner's weight table

| Category | Weight |
| --- | --: |
| Market trend | **20%** |
| Volatility regime | **20%** |
| Market momentum | **15%** |
| Breadth | **15%** |
| Choppiness / persistence | **10%** |
| Sector rotation | **10%** |
| Macro / credit | **5%** |
| Event regime | **5%** |

### 0.3 What this engine may claim — and what the evidence refuses

1. **A volatility regime is informative, but the *sign* of predictability is
   regime-dependent.** The literature is not "high vol = bad returns"; it is that
   predictability differs by regime. So `RegimeScore` describes the
   **environment** and never asserts a direction for the name.
2. **Rule-based is the honest baseline.** The engine's paths are rule-based
   thresholds, not probabilistic state inference. That is a legitimate choice —
   interpretable, no fitting, no look-ahead — but it must be stated as such, with
   a probabilistic upgrade (the repo already has `regime.hmm_regime:743` and
   `regime.bocpd:1327` built and lightly used) named as the successor rather than
   implied.
3. **Breadth is a participation/confirmation measure, not an established leading
   indicator.** The advance-decline line's predictive validity has never been
   rigorously established; what it does well is *confirm* and *diverge*. So the
   breadth category (15%) is scored as participation, and a divergence is a
   *diagnostic*, not a forecast.
4. **Persistence has formal tests the engine has not wired.** The owner names
   Hurst and variance ratio; both exist (`mean_reversion.hurst_exponent:113`,
   `variance_ratio:216` — Lo-MacKinlay) and neither is bound to the regime
   surface. The canonical choppiness index (`regime.choppiness:141`) is a proxy
   for the same question and is the one in the ledger today.

---

## 1. Component ledger

| Component | Weight | Status | Producer (module.function:line) | Output key | Direction | Scale/units | Gap |
| --- | --: | --- | --- | --- | --- | --- | --- |
| Market trend | 20 | PARTIAL | regime.trend_strength:130; regime_state.regime_trend:65; regime.regime_gate_read:850 | Path A: regime label / context; Path B: labels.trend + trend.score; gate: fast_downtrend, above_sma200, sma50_rising | higher price vs SMA = favourable | Path A ratio (P/SMA - 1, signed); Path B (EMA20-EMA50)/ATR14, label threshold +/-1.0 | Only the analysed ticker is measured; SPY only as benchmark (_benchmark_closes:302 -> benchmark_ticker, default SPY). QQQ/IWM ABSENT. |
| Trend -> SPY/QQQ/IWM index trend | sub | built 2026-09-27 | `regime.index_trend_reads:1787` over `_ohlcv` per index, emitted by `analysis_tools.get_regime_components` | P/SMA-1 per index | higher = index above trend | signed ratio + `above_sma` | three separately-labelled reads, no cross-index mean (the owner's weights do not exist)  [CORRECTED 2026-09-27: `REG-4` closed; live SPY +7.91%, QQQ +11.99%, IWM +2.75%, all above their 200-bar SMA.] |
| Trend -> 200-SMA / 50-SMA state | sub | SCORABLE | regime._sma:844 used by regime_gate_read:178 | above_sma200, sma50_rising | above and rising = favourable | boolean | - |
| Volatility regime | 20 | PARTIAL | regime.realized_vol:39; regime.vol_percentile:59; regime_state.regime_vol_ratio:92; rotation.vol_cones:123; volatility_models.ewma_vol:397, garch11_fit:226 | Path A: vol_pct (internal, not returned by the leaf); Path B: labels.volatility + volatility.ratio; vol_cap_factor input | high vol = risk-increasing | percentile 0-1; ATR ratio = ATR14/median(ATR14); vol_cones = annualized + p25/p50/p75 | VIX has no producer beyond a raw FRED series: no VIX percentile, no VIX term structure. **[CORRECTED 2026-09-26]** Both now exist as RegimeScore legs: the VIX percentile (`agents/utils/analysis_tools.py::_vix_percentile_read:9726`, leg `vix_percentile`) and the VIX9D/VIX3M term structure (`dataflows/cboe.py::vix_term_structure:282`, wired in `agents/utils/analysis_tools.py::_regime_components:6598`, leg `vix_term_structure`). The equity-IV slope remains a different object and is never substituted. |
| Volatility -> VIX level | sub | PARTIAL | dataflows.fred.get_macro_value:181 with alias vix -> VIXCLS at fred.py:68; leaf get_macro_indicators:9 | rendered FRED table (no numeric key) | high = risk-increasing | index points (level) | Raw level only, news-tool-only, no percentile. **[CORRECTED 2026-09-26]** A percentile now exists (`agents/utils/analysis_tools.py::_vix_percentile_read:9726`, leg `vix_percentile`), so the FRED table is no longer the only surface. |
| Volatility -> realized vol / vol percentile | sub | SCORABLE | regime.realized_vol:39; regime.vol_percentile:59 | vol_pct | high = risk-increasing | 0-1 rank; annualized fraction | - |
| Volatility -> volatility term structure | sub | PARTIAL | options_surface.term_structure_slope:227 | returned float | positive = contango (unfavourable for vol longs) | fraction | Equity-IV slope, not a VIX futures/VIX9D-VIX3M term structure (ABSENT). **[CORRECTED 2026-09-26]** The VIX9D/VIX3M index term structure now exists (`dataflows/cboe.py::vix_term_structure:282` -> `strategies/regime_score.py::vix_term_structure:408`, leg `vix_term_structure`); the equity-IV slope (`options_surface.term_structure_slope:227`) remains a different object over different inputs and is never substituted. |
| Market momentum | 15 | SCORABLE | factors.momentum:24 (overlays.py:82, lookback=60); rotation.clenow_momentum:89; momentum.momentum_12_1:358 | Path A: momentum60; leaf get_clenow_momentum:7356 | higher = favourable | fraction (rendered as +x.x%); Clenow = R-squared-penalised score | No market-wide (breadth-weighted) momentum; per-name only. |
| Breadth | 15 | PARTIAL | sector_breadth.multi_breadth:165; sector_breadth.mcclellan_read:213; sector_rank.constituent_breadth:664; sector_screener.breadth_with_gate:519 | pct_20d/pct_50d/pct_200d; mo/msi; pct + n | high percent above SMA = favourable (broadening) | percent above MA (0-100); MO/MSI signed oscillator | Sector-ETF/constituent level only, n-gated (n < 20 -> n/a). No market-wide A/D, no new highs/lows. **[CORRECTED 2026-09-26]** A whole-market panel producer now exists (`strategies/market_breadth.py::market_breadth:114`): `pct_above_20d/50d/200d`, `advance_decline`/`ad_ratio`, and `new_highs_52w`/`new_lows_52w`/`net_new_highs_52w`; its `pct_above_50d` is the RegimeScore `breadth` leg (`agents/utils/analysis_tools.py::_regime_components:6598`). |
| Breadth -> percent above 50 SMA / 200 SMA | sub | PARTIAL | sector_breadth.multi_breadth:165 (windows=(20,50,200)) | pct_50d, pct_200d | high = favourable | 0-100 per sector ETF | Per-sector, never whole-market. **[CORRECTED 2026-09-26]** Whole-market `pct_above_50d/200d` now exists in `strategies/market_breadth.py::market_breadth:114` (windows=(20,50,200)); `pct_above_50d` is the RegimeScore `breadth` leg. |
| Breadth -> advance/decline | sub | ABSENT | none | - | - | - | Grepped advance_decline|adv_dec|rise/fall: only the moomoo rendered string get_market_breadth:98 (moomoo.get_market_breadth_moomoo:1932). **[CORRECTED 2026-09-26]** A numeric market-wide producer now exists: `strategies/market_breadth.py::market_breadth:114` returns `advance_decline` (advancers - decliners) and `ad_ratio` ((adv - dec)/n, None on a small sample). |
| Breadth -> new highs / new lows | sub | ABSENT | none | - | - | - | Grepped new_high|new_lows|new_highs: only per-ticker RS flags (relative_strength.py:92, :121). **[CORRECTED 2026-09-26]** Market-wide counts now exist: `strategies/market_breadth.py::market_breadth:114` returns `new_highs`/`new_lows` (against the panel's own lookback), `new_highs_52w`/`new_lows_52w` (fixed 252-session lookback) and `net_new_highs_52w` (the high-low differential). |
| Breadth -> McClellan / MSI | sub | PARTIAL | sector_breadth.mcclellan_read:213; zone helper sector_breadth.msi_zone:307 | mo, mo_slope, msi | MO > 0 = favourable | oscillator index (signed) | Per sector; surfaced only inside get_sector_rotation_screen:3618 with enable_breadth on. |
| Choppiness & persistence | 10 | PARTIAL | regime.choppiness:141; mean_reversion.hurst_exponent:113; mean_reversion.variance_ratio:259 | leaf: chop=; Hurst; VR and z | high chop = unfavourable; H > 0.5 trending, H < 0.5 mean-reverting | 0-100 canonical CHOP (primary) vs 0-1 dispersion (close-only fallback); H 0-1; VR ratio | Two unit systems from one producer, and the callers disagree on which (see section 3). **[CORRECTED 2026-09-26]** `strategies/regime.py::choppiness:141` now returns **one** unit on both branches (canonical Dreiss CHOP on 0-100, or `100*(1-ER)` close-only) and `None` when unmeasurable; §3 defect 3 records the fix. |
| Choppiness -> market CUSUM | sub | SCORABLE | regime.cusum:1013 via get_shift_detection:7106 | signal, signal_at, mu0 | signal = sustained shift detected (risk-increasing) | CUSUM statistic / calibration threshold | Per-ticker series, not a market-index CUSUM. |
| Choppiness -> market EWMA | sub | SCORABLE | regime.ewma_control:1058 via get_shift_detection:7106 | signal, signal_at | signal = slow drift detected | EWMA control-chart z | Per-ticker; bocpd:389 exists but is surfaced elsewhere. |
| Sector rotation | 10 | SCORABLE | sector_rank.rank_sectors:37; sector_rank.rank_sectors_multifactor:391; rotation.relative_rotation:43; sector_rank.rrg_quadrant:370 | get_sector_rank:3410; get_sector_rotation_screen:3618; get_relative_rotation:7303 | top-3 / leading quadrant = favourable | rank number; RRG quadrant; cross-sectional percentile 0-100 | - |
| Macro & credit | 5 | PARTIAL | credit_spread.credit_stress_level:44; cycle_tilt.cycle_phase:130; regime_performance.macro_regime:76; cycle_tilt.taylor_rule:162 | get_credit_spread_read:4782 (level + scale + PD); get_cycle_tilt:2893 (phase + tilt); get_macro_regime_read:6492 (label) | wide spreads / restrictive policy = risk-increasing | band low/moderate/high/severe + 0..1 de-risk scale; regime enum | macro_regime takes caller-supplied markers (fetches nothing); cycle/credit do fetch FRED. |
| Macro -> yield curve | sub | SCORABLE | fred.py:45 alias (T10Y2Y); massive.is_yield_curve_inverted:372; leaf get_treasury_curve:7582 | rendered curve rows; boolean | inversion = risk-increasing | bps; boolean | No curvature / term-premium factor. |
| Macro -> Treasury volatility | sub | ABSENT | none | - | - | - | Grepped move_index|MOVE|treasury_vol: no producer; get_treasury_curve:7582 gives levels only. |
| Macro -> liquidity conditions | sub | PARTIAL | get_tga_balance (bound news_tools:361); get_sofr_curve:7568; liquidity_risk.liquidity_verdict:258 | rendered read | drain = risk-increasing | level / verdict enum | Bound to the news analyst, not market; no composite liquidity score. |
| Event regime | 5 | SCORABLE | catalyst.build_catalyst_snapshot:246; get_catalyst_scale:617; get_earnings_catalyst:206; get_earnings_event_read:535; get_opex_read:3108; get_economic_calendar:60 | scale (0..1) + verdict; implied move | imminent high-impact event = risk-increasing | 0..1 position-scale multiplier (scale=1 means no imminent catalyst) | Overlaps EventScore; only scale/verdict is numeric. |

---

## 2. Tool leaves

| Leaf (function:line) | Toolset binding (agents/toolsets.py:line) | What it returns | Wired? |
| --- | --- | --- | --- |
| get_regime_read:964 | market_tools:267 | regime label + position_scale + momentum60 + 52w distance + context | yes (Path A) |
| get_regime_components:2145 | market_tools:269 | one line: vol_pct, trend, chop (0-100), label (threshold 30.0) | yes |
| get_regime_state:20 (quant_adds_tools) | market_tools:270; fundamentals_company_tools:431; fundamentals_etf_tools:455 | 4 labelled axes + scores + F_regime + crash + hmm label | yes (Path B) |
| get_regime_gate_read:8467 | not in toolsets.py; bound in risk_tool_loop.py:119 and :167 | verdict/pass + vol_pct + fast_downtrend + reasons | yes, risk debators only |
| get_shift_detection:7106 | market_tools:268 | CUSUM + EWMA signal/index/mu0 + LZ complexity | yes |
| get_macro_regime_read:6492 | news_tools:355 | Risk-On / Liquidity-Contraction / Stagflation label + reasons (caller passes all five markers) | yes, news only |
| get_credit_spread_read:4782 | market_tools:286; news_tools:374 | HY/CCC/BB OAS band + 0..1 scale + implied 1y default prob | yes |
| get_cycle_tilt:2893 | market_tools:277 | cycle phase + favoured SPDR groups (FRED pmi / curve / hy) | yes |
| get_sector_rank:3410 | market_tools:275 | SPDR 1m/3m momentum ranking + the ticker sector standing | yes |
| get_sector_rotation_screen:3618 | market_tools:276 | regime cap + multi-factor rank + RRG + opt-in breadth matrix/McClellan/screens | yes |
| get_relative_rotation:7303 | market_tools:322 | RRG quadrant vs benchmark | yes |
| get_market_breadth:98 (moomoo_extra_tools) | news_tools:368 | moomoo vendor string: sector heat-map + rise/fall distribution | yes, non-numeric passthrough |
| get_macro_indicators:9 (macro_data_tools) | news_tools:354 | FRED window table (aliases incl. vix, yield_curve, 10y_2y_spread) | yes, news only |
| get_economic_calendar:60 (moomoo_extra_tools) | news_tools:362 | forward calendar of scheduled events | yes |
| get_earnings_catalyst:206 (moomoo_extra_tools) | news_tools:369 | per-print implied move + IV crush history | yes |
| get_catalyst_scale:617 | news_tools:370 | 0..1 catalyst scale + verdict | yes |
| get_earnings_event_read:535 | news_tools:371 | EPS surprise percent/side + PEAD setup | yes |
| get_opex_read:3108 | not found in the toolsets.py lists (leaf exists) | OPEX calendar + pin/unwind window | unwired in toolsets.py |
| get_clenow_momentum:7356 | market_tools:313 | Clenow persistence momentum score | yes |
| get_mean_reversion_quality:7009 | market_tools:299 | half-life / Hurst / variance-ratio block | yes |

---

## 3. Defects and dead seams

1. **[FIXED 2026-09-17, `ba50b5f`]** regime_label's choppiness branch was unreachable from overlays.build_strategy_overlays. overlays.py:57 calls regime_label(vol_pct, trend, 0.4); regime.py:133 sets chop_threshold: float = 0.30; the branch at regime.py:143 evaluates 0.4 <= 0.30 -> False always. A reader of today's report sees labels only from {high_vol, bull, bear, neutral} and can never see a choppy label, although the docstring at regime.py:135-137 advertises four labels.

2. **[OPEN - not a defect, a limitation]** The vol_pct proxy in overlays.py:41-55 has exactly three distinct values and is a constant for most histories. vol_pct is one of {0.9, 0.1, 0.5}: 0.9 iff vol_now > 1.5*vol_all (overlays.py:53); 0.1 iff vol_all > 0 and vol_now < 0.5*vol_all (overlays.py:54); else 0.5. vol_all is forced to 0.0 when len(logrets) < 252 (overlays.py:50), so with a 60-251-bar history both ratio branches fail and vol_pct is pinned at 0.5. Trace of the label for each value with chop=0.4 and chop_threshold=0.30:
   - vol_pct = 0.5 (below 0.75, above 0.25) -> falls through to 0.4 <= 0.30 = False -> neutral; the trend argument is ignored entirely. This is the deterministic outcome for every 60-251-bar series.
   - vol_pct = 0.9 (>= 0.75) -> high_vol; trend ignored.
   - vol_pct = 0.1 (<= 0.25, needs >= 252 bars) -> bull/bear when abs(trend) >= 0.02, else neutral.
   Net: the trend leg fires only at the single value 0.1; the choppiness leg fires never. The producer names the quantity vol_pct (a percentile) but emits a 3-bucket ratio flag, which a report would repeat as if it were a rank.

3. **[FIXED 2026-09-17, `ba50b5f`]** choppiness returned two different unit systems and its two callers disagreed on which one they were in. Producer regime.choppiness:141 returns the canonical Dreiss CHOP on 0-100 at regime.py:112 (100*log10(tr_sum/rng)/log10(n), requires len(c) >= n+1 and len(h) >= n and len(lo) >= n), and falls back to a 0-1 log-return dispersion, return float(pstdev(sample) or 0.5), at regime.py:123 (and 0.5 at regime.py:122) when highs/lows are missing. Callers:
   - overlays.py:57 passes the hardcoded constant 0.4 - not the producer at all, and on the 0-1 scale.
   - analysis_tools.py:2171-2173 computes the real chop = choppiness(closes, highs=data.get(highs), lows=data.get(lows), window=14) and passes chop_threshold=30.0.
   Which matches the producer: analysis_tools.py:2173 (30.0) matches the 0-100 primary return range; overlays.py:57 (0.4 against the 0.30 default) matches neither the primary range nor any measured value - it sits in the fallback 0-1 band but is a literal, so it can never be consistent with a close-only fallback either (that fallback returns a pstdev, not 0.4). A reader of get_regime_components therefore sees a chop value around 30-60 and a label computed against 30.0, while the overlay path computes its label against 0.30 from a constant - the two tools can disagree on label for the same ticker on the same day.

4. volatility_estimator only moves position_scale, never the label. overlays.py:60-72 computes an ewma/garch vol override that feeds volatility_target_scale, but label = regime_label(...) was already fixed at overlays.py:57 from the constant-bucket vol_pct. Two config paths read as one regime but only one uses the estimator.

5. get_regime_components builds non-overlapping windows, so its vol_pct is coarse. analysis_tools.py:2166 slices range(window, len(closes)+1, window) -> about 15 windows for a 320-bar series; vol_percentile:49 then ranks at 1/15 granularity, and because it ranks windows against a set that includes the latest itself (regime.py:57 uses <=), the printed vol_pct can never fall below about 0.067.

6. macro_regime (regime_performance.macro_regime:76) is fed only by the caller. The leaf get_macro_regime_read:6492 takes five optional floats and fetches nothing; the FRED fetchers that hold the same markers (get_macro_indicators:9, get_credit_spread_read:4782, get_cycle_tilt:2893) are not wired into it, so the RegimeScore macro leg can silently render n/a (mixed/unknown inputs) while the data exists in the same run.

---

## 4. What is ABSENT, and the smallest honest producer

| ABSENT / PARTIAL | Data needed | Already fetched somewhere? | Smallest honest producer |
| --- | --- | --- | --- |
| Market trend on SPY/QQQ/IWM | index close series | SPY only: _benchmark_closes:302 (config benchmark_ticker, default SPY) via _ohlcv:194 vendor chain. QQQ/IWM not fetched. | Reuse _ohlcv for SPY/QQQ/IWM with regime.trend_strength:130 per index; report the three separately (no composite without the owner's cross-index weights). |
| VIX percentile | VIX daily history | Yes: fred.get_macro_value:181 (fred.py:176) with alias vix -> VIXCLS at fred.py:68. | A percentile rank (regime.vol_percentile:59) over the VIXCLS series. **[CORRECTED 2026-09-26]** Built: `agents/utils/analysis_tools.py::_vix_percentile_read:9726` (rank of VIXCLS within its trailing year), the `vix_percentile` leg. |
| VIX / volatility term structure | VIX9D/VIX3M or futures curve | No: grepped vix9d|vix3m|vix_term; only equity-IV options_surface.term_structure_slope:227 exists. | Add VIX9D/VIX3M FRED aliases and apply term_structure_slope:152; until then PARTIAL, never substitute the equity-IV slope silently. **[CORRECTED 2026-09-26]** Built: `dataflows/cboe.py::vix_term_structure:282` reads Cboe's own VIX9D/VIX3M index history (not FRED); `strategies/regime_score.py::vix_term_structure:408` derives the ratio, the `vix_term_structure` leg. |
| Market-wide advance/decline | exchange-wide advancers/decliners | Only the moomoo rendered string get_market_breadth:98 -> moomoo.get_market_breadth_moomoo:1932, not numeric. | Promote the moomoo rise/fall distribution counts into a numeric A/D ratio inside moomoo.get_market_breadth_moomoo:1932; until then ABSENT (no fabrication from a rendered string). **[CORRECTED 2026-09-26]** Built instead over the panel: `strategies/market_breadth.py::market_breadth:114` returns numeric `advance_decline` and `ad_ratio`. |
| Market-wide new highs / new lows | counts of 20d/52w highs and lows | No: only per-ticker RS flags relative_strength.py:92 and :121. | Add a new_highs_lows(closes_map) producer over the cached _ohlcv universe; the sector path already builds such maps (constituent_breadth:654). **[CORRECTED 2026-09-26]** Built: `strategies/market_breadth.py::market_breadth:114` returns `new_highs`/`new_lows` and the fixed-lookback `new_highs_52w`/`new_lows_52w`/`net_new_highs_52w`. |
| Percent of stocks above 50/200 SMA (whole market) | full-US price panel | Yes at sector level: sector_breadth.multi_breadth:165 over dataflows.sp500_universe.fetch_sp500_universe (used at analysis_tools.py:3714-3747); no market-wide aggregate. | Reuse multi_breadth:60 over the whole SP500 universe map and aggregate pct_50d/pct_200d; gate n via sector_screener.breadth_with_gate:519. **[CORRECTED 2026-09-26]** Built: `strategies/market_breadth.py::market_breadth:114` returns `pct_above_20d/50d/200d` over the panel with `min_n=20`; `pct_above_50d` is the RegimeScore `breadth` leg. |
| Treasury volatility (MOVE) | MOVE index series | No: grepped move_index|MOVE|treasury_vol; get_treasury_curve:7582 gives levels only. | ABSENT; needs a MOVE source, or a realised-vol-of-DGS10 proxy via regime.realized_vol:39 on FRED 10y_treasury (fred.py:43). |
| Liquidity conditions composite | TGA / SOFR / reserves | Partially: get_tga_balance and get_sofr_curve:7568, both bound to news_tools:361. | Bind the existing leaves where macro claims are made; a composite needs owner weights (report the components, do not invent an index). |
| Macro label wiring | the five macro markers | Yes: get_macro_indicators:9 (rate/curve/DXY/vix) and get_credit_spread_read:4782 (HY spread). | Feed get_macro_regime_read:6492 from those two leaves instead of requiring caller-supplied floats. |

---

## 5. The composite — how `RegimeScore` gets built

1. **One producer per component, named.** For every row of §1, the document names
   the path it reads (A or B) or the leaf it calls. Where the two paths compute
   the same concept differently, **the score reads one and the other is
   reported as a separate, differently-named read** — never averaged, never
   silently preferred.
2. **Market-level, not name-level.** The owner's categories are about the
   *environment*: SPY/QQQ/IWM trend, market breadth, credit. Today five of the
   eight categories are computed from the **analysed ticker's own history**
   (`get_regime_read` uses the ticker's closes). A `RegimeScore` built from those
   would be a second `TechnicalScore` under a different name. The index-trend and
   market-breadth producers in §4 are therefore **prerequisites**, not
   enhancements.
3. **`NA ≠ 0`.** Same rule as everywhere: a missing category reduces the
   available weight and is printed. The engine's current sector breadth is
   `n`-gated (`n < 20 → n/a`), which is already the right shape — keep it.
4. **Score ≠ scale ≠ state ≠ confidence.** `RegimeScore` is the number; the
   `position_scale` (Path A's volatility-target multiplier) stays a separate
   output; the label stays a label. The owner's staged diagram shows a score; the
   engine's `F_regime` is a *factor*, not a score, and must not be renamed into
   one.
5. **Its own band table**, advisory, feeding nothing (master rule 2).
6. **The regime/risk boundary is fixed by question, not by producer.** Volatility
   *regime* (is the market's volatility high relative to its own history) is this
   engine; volatility *risk* (how much can this position lose at that
   volatility) is `RiskScore`. The same realized-vol producer may feed both, with
   the ownership named.

### 5.1 The prerequisite order

| Order | Item | Why first |
| --: | --- | --- |
| 1 | Market-level trend (SPY/QQQ/IWM) | without it the engine measures the name, not the environment |
| 2 | Market-wide breadth (percent above 50/200 SMA over the S&P panel) | the data is already fetched for the sector screens |
| 3 | VIX percentile (FRED VIXCLS history exists) | turns a raw level into a regime input |
| 4 | The chop unit decision (defect 2) | until one unit is chosen, the choppiness category has no defined scale |
| 5 | The score itself | only once 1-4 exist is there something to weight |

---

## 6. Verification requirements

1. **The label must move when the trend moves** (the defect-1 regression): with
   `vol_pct == 0.5`, a strong positive trend and a strong negative trend must not
   produce the same label.
2. **One unit for choppiness.** A test asserts the value the label compares is on
   the same scale as the producer's return range, for both callers.
3. **The two paths are tested for disagreement, not merged.** A test asserts that
   when Path A and Path B disagree, both values are present in the output with
   their names — the failure mode to prevent is silent reconciliation.
4. **A regime score with no market data returns `None`**, never a neutral 50.
5. **No direction is asserted.** A test asserts the score never appears in a
   directional field (no "bullish because RegimeScore 68").

---

## 7. Decisions (owner, 2026-09-17) - all resolved

**All decided (owner, 2026-09-17).** Each question keeps its text as the record
and carries its decision inline. The architecture decisions are in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §13; the engine-internal
answers are here.


1. **Which path is canonical for a score — A, B, or a new market-level C?** This
   is the owner's call, and it decides whether the score can ship before the
   market-level producers exist. **Recommendation: C** (market-level inputs,
   reusing B's four-axis vocabulary) — A is name-level and B's sizing fold is off by default. **CLOSED 2026-09-17 (plan §13 Q1): path C is canonical** - market-level inputs reusing B's four-axis vocabulary.
2. **Does the event category (5%) survive** if `EventScore` ships? The overlap is
   real (`build_catalyst_snapshot:219` feeds both). Master §3.2 defect 16 records
   the dead `catalyst_window` veto in `regime_gate_read:261` — the regime gate advertises an event veto that can never fire. **DECIDED 2026-09-17:**
remove the standalone event category from this engine when `EventScore` ships. The
same producer feeds both, so a second 5% factor double-counts one catalyst -
**RegimeScore describes the environment, EventScore describes the catalyst**.
3. **Hurst/variance-ratio as the persistence producer?** They exist, are formal,
   and are unwired. The alternative is to keep the choppiness index and label it a proxy. **DECIDED
2026-09-17:** the **variance ratio** (`mean_reversion.variance_ratio:259`) is the
canonical persistence producer; **Hurst stays a diagnostic/research input** and
must not also enter the score. One authoritative producer, not two.
4. **How is a regime *change* scored** as opposed to a regime *level*? The
   `cusum:295` / `ewma_control:340` / `bocpd:389` shift detectors exist and are
   surfaced by `get_shift_detection:7106`; none is part of the owner's table. **DECIDED 2026-09-17:** a regime **change** is a
separate **state/flag** (CUSUM / EWMA control / BOCPD, surfaced by
`get_shift_detection:7106`), not another weighted score category - "is the regime
changing?" and "what regime are we in?" are different dimensions.

---

## 8. The owner's formula library (`Strategies/scores/regime_score.md`, 2026-09-26)

**The library is 2,601 lines and 104 numbered top-level sections (`# 1.`–`# 104.`)**, plus a preamble and a closing architecture note. It holds **234 display-math formula blocks** — counted as `$$` delimiters alone on their own lines, two per block — plus inline `\( … \)` forms that are not counted. [`../ScoreWeight/market.md`](../ScoreWeight/market.md) §2 is the owner's eight-category weight table (the same table §0.2 prints) and lists 23 candidate factors; the library is the exhaustive formula set behind those categories and a large superset of the ledger in §1–§4 of this document. It is a candidate list, not a specification: §104 says *"I wouldn't actually implement all 100+ calculations directly into the final score."* Below, **built** = a producer exists that the built engine names; **elsewhere** = a producer exists but is owned by another engine/surface (the regime engine does not count it); **PARTIAL** = part of the section is implemented; **ABSENT** = no producer and the cell names the smallest honest one.

### 8.1 The library's sections against the engine

| § | Section | Formulas | Status | Verified producer (`module.symbol:line`) / smallest honest producer |
| --: | --- | --: | --- | --- |
| 1 | Trend Regime Calculations | 11 | PARTIAL | The distance ratio is leg 1: `regime.trend_strength:130` via `regime_score.market_trend:351`. SMA/EMA/crossover/golden-cross live on the technical surface (`extended_indicators.golden_death_cross:55`); MA slope is unwired. |
| 2 | ADX Trend-Strength Regime | 8 | elsewhere | `technical_factors.adx:230` (DI+/DI-/strong; TechnicalScore surface). |
| 3 | Trend Efficiency | 5 | PARTIAL | Kaufman ER is the close-only branch of `regime.choppiness:141`; R² via `rotation.clenow_momentum:89`. Trend-to-noise ABSENT. |
| 4 | Return Regime | 6 | elsewhere | `momentum`/`factors.momentum:24`; momentum lookbacks are TechnicalScore. |
| 5 | Volatility Regime | 10 | PARTIAL | `volatility_models.semivariance:68`, `parkinson_vol:155`, `garman_klass_vol:185`; realised vol `regime`/`volatility_models.ewma_vol:397`; ATR `compression._atr_series:43`. Rogers-Satchell and Bollinger width ABSENT here (BBW on the technical surface). |
| 6 | Volatility-of-Volatility | 2 | ABSENT | No producer; the smallest honest one is `volatility_models.ewma_vol:397` over itself. |
| 7 | Volatility Expansion / Compression | 4 | PARTIAL | Vol percentile is leg 6: `regime.vol_percentile:59`. Vol ratio / vol z ABSENT. |
| 8 | VIX / Implied Volatility Regime | 7 | PARTIAL | §8.1 VIX percentile = leg 3 (`analysis_tools._vix_percentile_read:9726`); §8.2 term structure = leg 4 (`regime_score.vix_term_structure:408`). IV/HV premium ABSENT. |
| 9 | Drawdown Regime | 4 | elsewhere | `regime_state.regime_state:215` drawdown axis; `book_risk` underwater series. |
| 10 | Market Breadth Regime | 7 | PARTIAL | `market_breadth.market_breadth:114` (pct_above_50d is leg 2; also advance_decline/ad_ratio, new_highs_52w/new_lows_52w/net_new_highs_52w). The cumulative A/D **line** (§10.2) ABSENT. |
| 11 | Breadth Thrust | 1 | ABSENT | Zweig thrust has no producer; smallest honest one is `market_breadth.market_breadth:114` over a short window. |
| 12 | Market Participation | 3 | ABSENT | No producer; smallest honest one is `market_breadth.market_breadth:114` (it returns panel percentages, not positive-return counts). |
| 13 | Correlation Regime | 3 | PARTIAL | `portfolio._max_pairwise_corr:61` (a cluster ceiling). Average pairwise correlation and the spike z ABSENT. |
| 14 | PCA / Common-Factor Regime | 3 | PARTIAL | `regime.spectral_change_read:1494` (absorption ratio, projector distance, PC1 share) and `sector_breadth.mp_lower_spectrum:112`. |
| 15 | Dispersion Regime | 2 | elsewhere | `alpha_health.cross_sectional_dispersion:119` (alpha-eval surface). |
| 16 | Market Concentration | 2 | ABSENT | No HHI / effective-N producer; smallest honest one is `sector_rank` weights if published. |
| 17 | Relative Strength Regime | 2 | elsewhere | `relative_strength.rs_series:33`, `rs_trend:68`, `rs_position:89`. |
| 18 | Relative Volatility | 1 | ABSENT | No producer; smallest honest one is `volatility_models` ratio over two series. |
| 19 | Beta Regime | 3 | elsewhere | `evaluate.beta:901`, `rolling_beta:939`. |
| 20 | Market Sensitivity Regime | 2 | ABSENT | No upside/downside beta producer; smallest honest one is splitting `evaluate.beta:901` by benchmark sign. |
| 21 | Liquidity Regime | 5 | PARTIAL | `liquidity_risk.amihud_illiquidity:71` (Amihud), `liquidity_risk` ADV dollar. Dollar-volume z ABSENT. |
| 22 | Market Stress Indicators | 4 | ABSENT | The four Z(...) indicators have no composite producer; the pieces exist (`regime.vol_percentile:59`, drawdown, correlation, `amihud_illiquidity:71`). |
| 23 | Credit Regime | 3 | elsewhere | `credit_spread.credit_stress_level:44` (a band + PD, not the spread/z formula); HY OAS via `analysis_tools._derive_macro_markers:9763`. |
| 24 | Yield Curve Regime | 3 | PARTIAL | `analysis_tools._derive_macro_markers:9763` reads FRED T10Y2Y; 10Y–3M and the change ABSENT. |
| 25 | Interest Rate Regime | 3 | PARTIAL | `cycle_tilt.taylor_rule:162`; policy change via `_derive_macro_markers:8887` (FRED EFFR). |
| 26 | Inflation Regime | 2 | PARTIAL | `cycle_tilt.py:163` takes an `inflation` argument (caller-supplied); no CPI producer. |
| 27 | Dollar Regime | 2 | PARTIAL | `regime_performance.macro_regime:76` consumes `dollar_index_chg_pct`; `_derive_macro_markers:8887` fills it (FRED `dollar_index`). |
| 28 | Commodity Regime | 3 | PARTIAL | `sector_drivers.py` binds WTI/copper to sectors; no commodity composite. |
| 29 | VIX/VIX3M Term Structure | 2 | built | `dataflows.cboe.vix_term_structure:282` -> `regime_score.vix_term_structure:408` (leg `vix_term_structure`). |
| 30 | Put/Call Regime | 3 | elsewhere | `options_surface.put_call_oi_concentration:34` (SentimentScore `put_call_ratio`). |
| 31 | Options Skew Regime | 2 | elsewhere | `options_surface.iv_skew:25`. |
| 32 | Volatility Surface Regime | 3 | elsewhere | `options_surface.term_structure_slope:227` (+ `surface_shape`). |
| 33 | Tail-Risk Regime | 3 | elsewhere | `tail_risk.tail_risk:174` (VaR/CVaR, RiskScore gate). |
| 34 | Skewness Regime | 1 | elsewhere | `evaluate.skewness:818`. |
| 35 | Kurtosis Regime | 2 | elsewhere | `evaluate.kurtosis:832`. |
| 36 | Autocorrelation Regime | 2 | elsewhere | `book_risk.return_autocorrelation:355`. |
| 37 | Hurst Exponent | 1 | elsewhere | `mean_reversion.hurst_exponent:113` — diagnostic only (§7 Q3). |
| 38 | Mean-Reversion Regime | 2 | PARTIAL | `mean_reversion.mean_reversion_verdict:226`. |
| 39 | Ornstein-Uhlenbeck Mean Reversion | 3 | PARTIAL | `mean_reversion.ou_half_life:91`. |
| 40 | Half-Life of Mean Reversion | 1 | PARTIAL | `mean_reversion.ar1_half_life:69`. |
| 41 | Stationarity Tests | 2 | elsewhere | `statistical.unit_root:101` (ADF + KPSS). |
| 42 | Regime Change / Structural Break | 1 | built | `regime.cusum:1013`, surfaced by `get_shift_detection` (a state, not a score leg — §7 Q4). |
| 43 | Chow Test | 1 | ABSENT | No Chow producer; smallest honest one is `statistical._ols_resid:92`. |
| 44 | Bayesian Change Point | 2 | built | `regime.bocpd:1327`. |
| 45 | Hidden Markov Model | 4 | built | `regime.hmm_regime:743`, `hmm_filtered_regime:545`. |
| 46 | Markov Transition Probability | 1 | built — `regime.hmm_transition_read:2092` reads `params.transmat` [CORRECTED 2026-09-27: `REG-16` closed 2026-09-27: emitted by `analysis_tools.get_regime_components`; live MSFT persistence 0.9023 at state 0/2.] |
| 47 | Regime Persistence | 2 | built — the same producer's `persistence` and `expected_duration` (`1/(1-A[i][i])`, None for an absorbing row) [CORRECTED 2026-09-27: live `[10.24, 1.89]` bars.] |
| 48 | Regime Entropy | 3 | PARTIAL | `complexity.permutation_entropy:19` is a price-series entropy, not a regime-probability entropy. |
| 49 | Regime Confidence | 1 | ABSENT | No producer; smallest honest one is `regime.hmm_filtered_regime:545`. |
| 50 | Regime Stability | 1 | ABSENT | No producer. |
| 51 | Regime Transition Probability | 2 | built — `hmm_transition_read`'s `next_state_probs` (row `s` of `A**horizon`) and `leave_probability` [CORRECTED 2026-09-27: `REG-16`.] |
| 52 | Regime Momentum | 1 | ABSENT | No producer. |
| 53 | Regime Acceleration | 1 | ABSENT | No producer. |
| 54 | Regime Trend | 2 | ABSENT | No producer. |
| 55 | Multi-Timeframe Regime | 2 | elsewhere | `factors.momentum:24` over multiple lookbacks (TechnicalScore). |
| 56 | Multi-Timeframe Agreement | 2 | ABSENT | No producer. |
| 57 | Cross-Asset Regime | 2 | ABSENT | No factor vector producer. |
| 58 | Risk-On / Risk-Off Spread | 1 | elsewhere | `regime_performance.macro_regime:76` (a label, not a spread). |
| 59 | Cyclical vs Defensive Spread | 1 | ABSENT | No producer; smallest honest one is `sector_rank.rank_sectors:37` on XLY/XLP. |
| 60 | High Beta vs Low Beta | 1 | ABSENT | No producer. |
| 61 | Small Cap vs Large Cap | 1 | ABSENT | No producer. |
| 62 | Growth vs Value | 1 | ABSENT | No producer. |
| 63 | Momentum vs Low Volatility | 1 | ABSENT | No producer. |
| 64 | Market Breadth × Trend Interaction | 1 | ABSENT | No producer. |
| 65 | Volatility × Trend Interaction | 1 | ABSENT | No producer. |
| 66 | Correlation × Volatility Interaction | 1 | ABSENT | No producer. |
| 67 | Market Stress Composite | 1 | ABSENT | No producer. |
| 68 | Trend Composite | 1 | ABSENT | No regime trend composite; `technical_score.technical_score` is the analogous technical aggregate (elsewhere). |
| 69 | Volatility Composite | 1 | ABSENT | No producer. |
| 70 | Breadth Composite | 1 | ABSENT | No producer. |
| 71 | Liquidity Composite | 1 | ABSENT | No producer. |
| 72 | Macro Composite | 1 | PARTIAL | `regime_performance.macro_regime:76` returns an enum label, not a weighted composite. |
| 73 | Cross-Asset Composite | 1 | ABSENT | No producer. |
| 74 | Full Regime Score | 3 | PARTIAL | `regime_score.regime_score` is the built composite, but with a different architecture: equal weights, linear ramps, no logistic — not the library's `100·σ(Σ wᵢRᵢ)`. |
| 75 | Percentile-Based Regime Score | 2 | PARTIAL | `regime.vol_percentile:59`, `factors.percentile_rank:59`, `normalized.percentile_hist_or_none:37`. |
| 76 | Robust Z-Score | 2 | ABSENT | No median/MAD robust-z producer. |
| 77 | Winsorized Score | 1 | elsewhere | `analyst_revisions.winsor_z:253`. |
| 78 | Logistic Normalization | 1 | ABSENT | No logistic normalization; `score_engine.align` is a linear ramp. |
| 79 | Min-Max Normalization | 1 | PARTIAL | `score_engine.align` (the `(lo,hi)` ramp) is a min-max form. |
| 80 | Directional Normalization | 2 | built | `score_engine.align` via `regime_score.align_components` (higher/lower_better inversion) — the house direction rule. |
| 81 | Rolling Normalization | 1 | PARTIAL | `volatility_models.ewma_vol:397` rolls; no rolling z producer. |
| 82 | Exponentially Weighted Regime Score | 2 | PARTIAL | `volatility_models.ewma_vol:397` (an EWMA filter, not a regime-score EWMA). |
| 83 | Bayesian Regime Score | 2 | PARTIAL | `regime.bocpd:1327` (change-point posterior, not a weighted regime score). |
| 84 | Regime Classification | 1 | built | `regime_state.regime_state:215` (Path B's four axes), `regime.regime_gate_read:850`. |
| 85 | Regime Distance | 4 | ABSENT | No Mahalanobis producer; smallest honest one is `covariance_models` correlation inverse. |
| 86 | Regime Similarity | 2 | ABSENT | No producer. |
| 87 | Clustering-Based Regime Detection | 2 | ABSENT | No k-means/GMM/DBSCAN regime producer. |
| 88 | Gaussian Mixture Regime Probability | 1 | PARTIAL | `regime.regime_conditional_var` builds a two-component Gaussian mixture, but for VaR, not a regime posterior. |
| 89 | Regime Entropy Penalty | 1 | ABSENT | No producer. |
| 90 | Regime Transition Penalty | 2 | ABSENT | No producer. |
| 91 | Regime Coverage | 2 | built | `score_engine.combine` via `regime_score` (`coverage`, `NA ≠ 0`, floor 3) — master rule 1. |
| 92 | Coverage Confidence | 1 | ABSENT | No producer. |
| 93 | Sample-Size Confidence | 1 | PARTIAL | Floors exist (`tail_risk` `MIN_OBS`, `covariance_models.SPECTRAL_MIN_OBS:189` = 30) but no confidence functional. |
| 94 | Data Freshness Decay | 1 | elsewhere | `sentiment.decayed_weight` (`strategies/sentiment.py:92`). |
| 95 | Factor-Weighted Confidence | 1 | ABSENT | No producer. |
| 96 | Regime Score with Confidence | 4 | PARTIAL — `regime.regime_state_metadata:2177` now emits entropy/entropy_normalized/confidence/stability/change/velocity/acceleration/surprise BESIDE the score [CORRECTED 2026-09-27: `REG-17` closed 2026-09-27: the block is emitted by `get_regime_components` and deliberately NOT multiplied into the number, per this item's own rule.] |
| 97 | Regime Score Change | 1 | ABSENT | No producer. |
| 98 | Regime Score Velocity | 1 | ABSENT | No producer. |
| 99 | Regime Score Acceleration | 1 | ABSENT | No producer. |
| 100 | Regime Persistence Score | 1 | ABSENT | No producer. |
| 101 | Regime Surprise | 1 | ABSENT | No producer. |
| 102 | Regime Stability Index | 1 | ABSENT | No producer. |
| 103 | Composite Regime Architecture | 0 | PARTIAL | `strategies/regime_score.py` implements the trend/volatility/breadth arm of the diagram; correlation, liquidity, macro and cross-asset arms are absent. |
| 104 | My Recommended Regime Engine for Your System | 3 | PARTIAL | Layer 1–3 partly exist; Layer 5's multi-number output is narrower — the engine emits `score`, `coverage`, `band` and the two path labels, not `RegimeConfidence`/`TransitionRisk`/`Entropy`/`Momentum`. |

**The VIX/implied-vol cross-check.** The doc's §1/§2 VIX material was corrected on 2026-09-26 — the Cboe index-history levels are the source, and the equity-IV slope is not a substitute. The library **agrees on the substance and disagrees on the tenor**. Its §8.1 `VIXPct = PercentileRank(VIX_t)` is exactly the `vix_percentile` leg (`agents/utils/analysis_tools.py::_vix_percentile_read:9726`). Its §8.2 and §29 both build the term structure from **two VIX index levels**, never from an equity option surface — the correction's rule — and `dataflows/cboe.py::vix_term_structure:282` states that rule in its own docstring (*"not one name's equity-IV slope"*). But the library's examples are VIX3M/VIX1M (§8.2) and VIX/VIX3M (§29), a **1-month** short leg, while the engine reads **VIX9D/VIX3M** (`strategies/regime_score.py::vix_term_structure:408`, ramp 0.85–1.15). The library also keeps the IV/HV premium (§8 preamble) and option-chain IV (§31, §32) under the same heading as VIX; those are precisely the equity surface the correction excludes, so the library hands over both the correct producer shape and the trap.

### 8.2 Not built — the backlog the library names

**The library's sections that are ABSENT or PARTIAL are the backlog**, and they cluster into four groups:

1. **Market-structure measures the six legs do not cover** — cumulative advance-decline line (§10.2), Zweig breadth thrust (§11), participation (§12), average pairwise correlation and its spike (§13), HHI / effective-N concentration (§16), relative volatility (§18), upside/downside beta (§20), market stress composite (§22). Several now have raw ingredients (`market_breadth.market_breadth:114` counts, `portfolio._max_pairwise_corr:61`, `evaluate.beta:901`) but no named regime producer.
2. **The cross-asset and macro arms of the §103 diagram** — the pair spreads (§58–§63), the interactions (§64–§66), and the trend/vol/breadth/liquidity/cross-asset composites (§68–§73). `regime_performance.macro_regime:76` gives a macro *label* and `credit_spread.credit_stress_level:44` a credit *band*; neither is the weighted composite these sections define.
3. **The confidence / state metadata the library insists on** — regime entropy (§48), confidence (§49), stability (§50), transition probability (§51), and the whole §96–§102 family (change, velocity, acceleration, persistence score, surprise, stability index). The library's own §96 argues these should travel *beside* the score, never multiplied into it; the engine follows the separation but emits none of the numbers.
4. **Statistical regime inference** — Chow (§43), Mahalanobis distance/similarity (§85–§86), clustering / GMM regime probability (§87–§88), robust-z / winsor / logistic normalization (§76–§78), rolling normalization (§81), factor-weighted confidence (§95), coverage confidence (§92). The HMM machinery exists (`regime.hmm_regime:743`, `regime._hmm_canonical:497`) but its transition/persistence outputs are not wired to the score surface.

### 8.3 Library-internal defects

1. **Two different VIX term-structure definitions under two sections.** §8.2 defines `VIXSlope = VIX_long/VIX_short − 1` with the example `VIX3M/VIX1M`; §29 defines `VIXRatio = VIX/VIX3M` and `VIXCurve = VIX − VIX3M`. Same name, different tenor **and** different functional form (ratio-minus-one vs raw ratio vs difference); a reader implementing "the VIX term structure" gets three different numbers.
2. **§8 is mislabelled.** The heading is *"VIX / Implied Volatility Regime"* but the section opens with `IVPremium = (IV_market − HV)/HV` and `IVHVRatio = IV/HV` — an implied-vs-realised comparison from one name's surface, a different object from the VIX index its subsections then use.
3. **Duplicated concepts across sections** (verified by reading): regime *change* is §52 (`Score_t − Score_{t−n}`) and §97 (`R_t − R_{t−1}`); *acceleration* is §53 and §99; *persistence* is §47 and §100; *confidence* is §92 and §95; *stability* is §50 (`1 − (1/k)Σ|p_t − p_{t−j}|` over regime **probabilities**) and §102 (`1 − Σ|R_{i,t} − R_{i,t−1}|/N` over **scores**) — two different formulas, one name. §45–§47 restate one HMM model three times.

### 8.4 Contradictions between the library and the code

The comparison points are the six legs' windows, floors, the `SPECTRAL_MIN_OBS=30` floor and the 3-leg composite floor.

| Comparison point | Library | Code (verified) |
| --- | --- | --- |
| Market-trend window / floor | §1.1 typical SMA20/50/100/200; §1.3 distance; no floor stated | `regime_score.market_trend:351`: window 200 or `n//2`, `MIN_BARS=60`; `regime.trend_strength:130` falls back to the whole-series mean |
| Breadth window / floor | §10.4/§10.5 percent above 200/50 SMA; no floor | `market_breadth.market_breadth:114`: windows `(20,50,200)`, `min_n=20` |
| VIX percentile | §8.1 `PercentileRank(VIX_t)`, no window | `_vix_percentile_read:8850`: VIXCLS rank over a trailing 252d, ~20-observation floor |
| VIX term structure | §8.2 VIX3M/VIX1M; §29 VIX/VIX3M (1-month short leg) | `dataflows/cboe.vix_term_structure:282` reads **VIX9D**/VIX3M; `regime_score.vix_term_structure:408` takes the ratio |
| Choppiness | **no CHOP section**; §3.1 Kaufman ER is the nearest | `regime.choppiness:141`: canonical Dreiss CHOP on 0-100, window 14; ER is the close-only fallback |
| Realized-vol percentile | §7.3 `PercentileRank(σ_t)` | `regime.vol_percentile:59`: non-overlapping 21-bar windows, self-inclusive (`<=`) rank |
| Spectral / PCA | §14 and §87 state no floor and no null band | `_spectral_windows:6217` requires `SPECTRAL_MIN_OBS=30` per window (`covariance_models.py:189`), `2·30+1` closes and ≥2 names; `regime.spectral_change_read:1494` cuts every move against a calibrated null band — the library's §14/§87 have no such calibration |
| Composite | §74 `100·σ(Σ wᵢ Rᵢ)` with per-category weights and a logistic | `regime_score.regime_score`: equal weight, linear `score_engine.align`, `COMPOSITE_MIN_COVERAGE=3` floor capped at the set size (`_composite_floor`, `regime_score.py:262`) |
| Normalization | §75 percentile-based; §80 directional | §80 is built (`score_engine.align`); §75 applies only to the two rank legs, the other four are linear ramps on raw values |
| Coverage | §91 `NA ≠ 0` coverage | built: `score_engine.combine` via `regime_score`, floor 3 — the one library principle adopted verbatim |

**A genuine code defect, found while ledgering this library (not a doc issue) — [FIXED 2026-09-26].** The leg now appends the current window when the stride missed it (`analysis_tools._regime_components`, guarded by `tests/test_analysis_tools.py::test_the_realized_vol_leg_ranks_the_window_that_ends_today`, which fails on the stride-only shape with `131.4 != 131.9`), so the window ranked as "latest" ends at the newest bar. The paragraph below is the defect as found. `agents/utils/analysis_tools.py::_regime_components:6598` builds the benchmark realized-vol windows as `[bench[i - window : i] for i in range(window, len(bench) + 1, window)]` with `window = 21`. When `len(bench)` is not a multiple of 21 the last window ends at `bench[len(bench) // 21 * 21]`, so the newest `len(bench) % 21` bars are dropped and the window ranked as "latest" is not the current one — e.g. 320 bars give a last window of `bench[294:315]`, excluding bars 315–319. Combined with `regime.vol_percentile:59`'s self-inclusive `<=`, the printed `realized_vol_percentile` can be stale by up to 20 bars and biased high by at least `1/n`. The existing §3 defect 5 records the self-inclusion but not the tail truncation.

---

## Appendix — methodology ledger

| Claim | Source | Where it bites |
| --- | --- | --- |
| HMM state inference vs rule-based thresholds: rule-based is the interpretable baseline, HMM gives state probabilities and persistence | the regime-detection literature | §0.3 point 2 — state the baseline honestly, name `hmm_regime:148`/`bocpd:389` as the successor |
| Return predictability differs by volatility regime; the sign is sample- and asset-dependent | the volatility-regime literature | §0.3 point 1 — the score describes environment, never direction |
| The variance ratio (VR > 1 persistence, VR < 1 mean reversion) and the Hurst exponent (H = 0.5 random walk) are the formal persistence tests, and neither alone is a random-walk verdict | Lo & MacKinlay; the Hurst literature | §0.3 point 4 — the unwired `variance_ratio:216` / `hurst_exponent:112` are the honest producers |
| The advance-decline line is a breadth/participation indicator whose *leading* validity has not been rigorously established | breadth-indicator reviews | §0.3 point 3 — breadth confirms and diverges, it does not forecast |
