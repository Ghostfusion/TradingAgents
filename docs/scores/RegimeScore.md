# RegimeScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`NewsScore.md`](NewsScore.md),
[`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
[`RiskScore.md`](RiskScore.md).

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
| Entry | `analysis_tools.get_regime_read:964` → `overlays.build_strategy_overlays:20` | `quant_adds_tools.get_regime_state:20` → `regime_state.regime_state:215` |
| Also called by | the pre-graph fold `graph/trading_graph.py:778` | — |
| Inputs | the **analysed ticker's own closes** (≥60 bars) | closes + highs/lows + benchmark (`_benchmark_closes:302`, SPY) |
| Volatility | a 3-valued proxy `vol_pct ∈ {0.1, 0.5, 0.9}` (`overlays.py:41-55`) | ATR14/median(ATR14) ratio (`regime_vol_ratio:92`) |
| Labels | `{high_vol, bull, bear, neutral}` + a volatility-target `position_scale` | four axes: trend (STRONG_BULL/BULL/BEAR/STRONG_BEAR), volatility (LOW/NORMAL/HIGH/EXTREME), relative (UNDERPERFORM/NEUTRAL/OUTPERFORM), drawdown (NORMAL/CORRECTION/BEAR/SEVERE) + a crash flag + `F_regime` |
| Gate | `enable_strategy_overlays` (**default True**, `default_config.py:800`) | `regime_state_enable` (**default False**, `default_config.py:839`) at `trading_graph.py:905` |
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
   a probabilistic upgrade (the repo already has `regime.hmm_regime:148` and
   `regime.bocpd:389` built and lightly used) named as the successor rather than
   implied.
3. **Breadth is a participation/confirmation measure, not an established leading
   indicator.** The advance-decline line's predictive validity has never been
   rigorously established; what it does well is *confirm* and *diverge*. So the
   breadth category (15%) is scored as participation, and a divergence is a
   *diagnostic*, not a forecast.
4. **Persistence has formal tests the engine has not wired.** The owner names
   Hurst and variance ratio; both exist (`mean_reversion.hurst_exponent:112`,
   `variance_ratio:216` — Lo-MacKinlay) and neither is bound to the regime
   surface. The canonical choppiness index (`regime.choppiness:87`) is a proxy
   for the same question and is the one in the ledger today.

---

## 1. Component ledger

| Component | Weight | Status | Producer (module.function:line) | Output key | Direction | Scale/units | Gap |
| --- | --: | --- | --- | --- | --- | --- | --- |
| Market trend | 20 | PARTIAL | regime.trend_strength:76; regime_state.regime_trend:65; regime.regime_gate_read:178 | Path A: regime label / context; Path B: labels.trend + trend.score; gate: fast_downtrend, above_sma200, sma50_rising | higher price vs SMA = favourable | Path A ratio (P/SMA - 1, signed); Path B (EMA20-EMA50)/ATR14, label threshold +/-1.0 | Only the analysed ticker is measured; SPY only as benchmark (_benchmark_closes:302 -> benchmark_ticker, default SPY). QQQ/IWM ABSENT. |
| Trend -> SPY/QQQ/IWM index trend | sub | ABSENT | none | - | - | - | No index-trend producer; grepped (spy|qqq|iwm).*trend and index_closes (the latter appears only inside regime_gate_read:178). |
| Trend -> 200-SMA / 50-SMA state | sub | SCORABLE | regime._sma:172 used by regime_gate_read:178 | above_sma200, sma50_rising | above and rising = favourable | boolean | - |
| Volatility regime | 20 | PARTIAL | regime.realized_vol:29; regime.vol_percentile:49; regime_state.regime_vol_ratio:92; rotation.vol_cones:123; volatility_models.ewma_vol:185, garch11_fit:226 | Path A: vol_pct (internal, not returned by the leaf); Path B: labels.volatility + volatility.ratio; vol_cap_factor input | high vol = risk-increasing | percentile 0-1; ATR ratio = ATR14/median(ATR14); vol_cones = annualized + p25/p50/p75 | VIX has no producer beyond a raw FRED series: no VIX percentile, no VIX term structure. |
| Volatility -> VIX level | sub | PARTIAL | dataflows.fred.get_macro_value:176 with alias vix -> VIXCLS at fred.py:68; leaf get_macro_indicators:9 | rendered FRED table (no numeric key) | high = risk-increasing | index points (level) | Raw level only, news-tool-only, no percentile. |
| Volatility -> realized vol / vol percentile | sub | SCORABLE | regime.realized_vol:29; regime.vol_percentile:49 | vol_pct | high = risk-increasing | 0-1 rank; annualized fraction | - |
| Volatility -> volatility term structure | sub | PARTIAL | options_surface.term_structure_slope:152 | returned float | positive = contango (unfavourable for vol longs) | fraction | Equity-IV slope, not a VIX futures/VIX9D-VIX3M term structure (ABSENT). |
| Market momentum | 15 | SCORABLE | factors.momentum:24 (overlays.py:82, lookback=60); rotation.clenow_momentum:89; momentum.momentum_12_1:358 | Path A: momentum60; leaf get_clenow_momentum:7356 | higher = favourable | fraction (rendered as +x.x%); Clenow = R-squared-penalised score | No market-wide (breadth-weighted) momentum; per-name only. |
| Breadth | 15 | PARTIAL | sector_breadth.multi_breadth:60; sector_breadth.mcclellan_read:100; sector_rank.constituent_breadth:654; sector_screener.breadth_with_gate:511 | pct_20d/pct_50d/pct_200d; mo/msi; pct + n | high percent above SMA = favourable (broadening) | percent above MA (0-100); MO/MSI signed oscillator | Sector-ETF/constituent level only, n-gated (n < 20 -> n/a). No market-wide A/D, no new highs/lows. |
| Breadth -> percent above 50 SMA / 200 SMA | sub | PARTIAL | sector_breadth.multi_breadth:60 (windows=(20,50,200)) | pct_50d, pct_200d | high = favourable | 0-100 per sector ETF | Per-sector, never whole-market. |
| Breadth -> advance/decline | sub | ABSENT | none | - | - | - | Grepped advance_decline|adv_dec|rise/fall: only the moomoo rendered string get_market_breadth:98 (moomoo.get_market_breadth_moomoo:1830). |
| Breadth -> new highs / new lows | sub | ABSENT | none | - | - | - | Grepped new_high|new_lows|new_highs: only per-ticker RS flags (relative_strength.py:92, :121). |
| Breadth -> McClellan / MSI | sub | PARTIAL | sector_breadth.mcclellan_read:100; zone helper sector_breadth.msi_zone:194 | mo, mo_slope, msi | MO > 0 = favourable | oscillator index (signed) | Per sector; surfaced only inside get_sector_rotation_screen:3618 with enable_breadth on. |
| Choppiness & persistence | 10 | PARTIAL | regime.choppiness:87; mean_reversion.hurst_exponent:112; mean_reversion.variance_ratio:216 | leaf: chop=; Hurst; VR and z | high chop = unfavourable; H > 0.5 trending, H < 0.5 mean-reverting | 0-100 canonical CHOP (primary) vs 0-1 dispersion (close-only fallback); H 0-1; VR ratio | Two unit systems from one producer, and the callers disagree on which (see section 3). |
| Choppiness -> market CUSUM | sub | SCORABLE | regime.cusum:295 via get_shift_detection:7106 | signal, signal_at, mu0 | signal = sustained shift detected (risk-increasing) | CUSUM statistic / calibration threshold | Per-ticker series, not a market-index CUSUM. |
| Choppiness -> market EWMA | sub | SCORABLE | regime.ewma_control:340 via get_shift_detection:7106 | signal, signal_at | signal = slow drift detected | EWMA control-chart z | Per-ticker; bocpd:389 exists but is surfaced elsewhere. |
| Sector rotation | 10 | SCORABLE | sector_rank.rank_sectors:37; sector_rank.rank_sectors_multifactor:391; rotation.relative_rotation:43; sector_rank.rrg_quadrant:370 | get_sector_rank:3410; get_sector_rotation_screen:3618; get_relative_rotation:7303 | top-3 / leading quadrant = favourable | rank number; RRG quadrant; cross-sectional percentile 0-100 | - |
| Macro & credit | 5 | PARTIAL | credit_spread.credit_stress_level:44; cycle_tilt.cycle_phase:63; regime_performance.macro_regime:76; cycle_tilt.taylor_rule:89 | get_credit_spread_read:4782 (level + scale + PD); get_cycle_tilt:2893 (phase + tilt); get_macro_regime_read:6492 (label) | wide spreads / restrictive policy = risk-increasing | band low/moderate/high/severe + 0..1 de-risk scale; regime enum | macro_regime takes caller-supplied markers (fetches nothing); cycle/credit do fetch FRED. |
| Macro -> yield curve | sub | SCORABLE | fred.py:45 alias (T10Y2Y); massive.is_yield_curve_inverted:372; leaf get_treasury_curve:7582 | rendered curve rows; boolean | inversion = risk-increasing | bps; boolean | No curvature / term-premium factor. |
| Macro -> Treasury volatility | sub | ABSENT | none | - | - | - | Grepped move_index|MOVE|treasury_vol: no producer; get_treasury_curve:7582 gives levels only. |
| Macro -> liquidity conditions | sub | PARTIAL | get_tga_balance (bound news_tools:361); get_sofr_curve:7568; liquidity_risk.liquidity_verdict:153 | rendered read | drain = risk-increasing | level / verdict enum | Bound to the news analyst, not market; no composite liquidity score. |
| Event regime | 5 | SCORABLE | catalyst.build_catalyst_snapshot:219; get_catalyst_scale:617; get_earnings_catalyst:206; get_earnings_event_read:535; get_opex_read:3108; get_economic_calendar:60 | scale (0..1) + verdict; implied move | imminent high-impact event = risk-increasing | 0..1 position-scale multiplier (scale=1 means no imminent catalyst) | Overlaps EventScore; only scale/verdict is numeric. |

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

3. **[FIXED 2026-09-17, `ba50b5f`]** choppiness returned two different unit systems and its two callers disagreed on which one they were in. Producer regime.choppiness:87 returns the canonical Dreiss CHOP on 0-100 at regime.py:112 (100*log10(tr_sum/rng)/log10(n), requires len(c) >= n+1 and len(h) >= n and len(lo) >= n), and falls back to a 0-1 log-return dispersion, return float(pstdev(sample) or 0.5), at regime.py:123 (and 0.5 at regime.py:122) when highs/lows are missing. Callers:
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
| Market trend on SPY/QQQ/IWM | index close series | SPY only: _benchmark_closes:302 (config benchmark_ticker, default SPY) via _ohlcv:194 vendor chain. QQQ/IWM not fetched. | Reuse _ohlcv for SPY/QQQ/IWM with regime.trend_strength:76 per index; report the three separately (no composite without the owner's cross-index weights). |
| VIX percentile | VIX daily history | Yes: fred.get_macro_value:176 (fred.py:176) with alias vix -> VIXCLS at fred.py:68. | A percentile rank (regime.vol_percentile:49) over the VIXCLS series. |
| VIX / volatility term structure | VIX9D/VIX3M or futures curve | No: grepped vix9d|vix3m|vix_term; only equity-IV options_surface.term_structure_slope:152 exists. | Add VIX9D/VIX3M FRED aliases and apply term_structure_slope:152; until then PARTIAL, never substitute the equity-IV slope silently. |
| Market-wide advance/decline | exchange-wide advancers/decliners | Only the moomoo rendered string get_market_breadth:98 -> moomoo.get_market_breadth_moomoo:1830, not numeric. | Promote the moomoo rise/fall distribution counts into a numeric A/D ratio inside moomoo.get_market_breadth_moomoo:1830; until then ABSENT (no fabrication from a rendered string). |
| Market-wide new highs / new lows | counts of 20d/52w highs and lows | No: only per-ticker RS flags relative_strength.py:92 and :121. | Add a new_highs_lows(closes_map) producer over the cached _ohlcv universe; the sector path already builds such maps (constituent_breadth:654). |
| Percent of stocks above 50/200 SMA (whole market) | full-US price panel | Yes at sector level: sector_breadth.multi_breadth:60 over dataflows.sp500_universe.fetch_sp500_universe (used at analysis_tools.py:3714-3747); no market-wide aggregate. | Reuse multi_breadth:60 over the whole SP500 universe map and aggregate pct_50d/pct_200d; gate n via sector_screener.breadth_with_gate:511. |
| Treasury volatility (MOVE) | MOVE index series | No: grepped move_index|MOVE|treasury_vol; get_treasury_curve:7582 gives levels only. | ABSENT; needs a MOVE source, or a realised-vol-of-DGS10 proxy via regime.realized_vol:29 on FRED 10y_treasury (fred.py:43). |
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
2026-09-17:** the **variance ratio** (`mean_reversion.variance_ratio:216`) is the
canonical persistence producer; **Hurst stays a diagnostic/research input** and
must not also enter the score. One authoritative producer, not two.
4. **How is a regime *change* scored** as opposed to a regime *level*? The
   `cusum:295` / `ewma_control:340` / `bocpd:389` shift detectors exist and are
   surfaced by `get_shift_detection:7106`; none is part of the owner's table. **DECIDED 2026-09-17:** a regime **change** is a
separate **state/flag** (CUSUM / EWMA control / BOCPD, surfaced by
`get_shift_detection:7106`), not another weighted score category - "is the regime
changing?" and "what regime are we in?" are different dimensions.

---

## Appendix — methodology ledger

| Claim | Source | Where it bites |
| --- | --- | --- |
| HMM state inference vs rule-based thresholds: rule-based is the interpretable baseline, HMM gives state probabilities and persistence | the regime-detection literature | §0.3 point 2 — state the baseline honestly, name `hmm_regime:148`/`bocpd:389` as the successor |
| Return predictability differs by volatility regime; the sign is sample- and asset-dependent | the volatility-regime literature | §0.3 point 1 — the score describes environment, never direction |
| The variance ratio (VR > 1 persistence, VR < 1 mean reversion) and the Hurst exponent (H = 0.5 random walk) are the formal persistence tests, and neither alone is a random-walk verdict | Lo & MacKinlay; the Hurst literature | §0.3 point 4 — the unwired `variance_ratio:216` / `hurst_exponent:112` are the honest producers |
| The advance-decline line is a breadth/participation indicator whose *leading* validity has not been rigorously established | breadth-indicator reviews | §0.3 point 3 — breadth confirms and diverges, it does not forecast |
