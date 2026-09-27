# MomentumScore — the eight §54 momentum legs

*Engine module:* `tradingagents/strategies/momentum_score.py`
*Leaf:* `tradingagents/agents/utils/analysis_tools.py::get_momentum_score`
*Library (owner's, read-only):* [`momentum_score.md`](momentum_score.md), 2,064
lines, 54 sections. **This document is the engine's record of what it built,
what it declined and how it was verified — it never restates the library.**

The engine's question is *"how strong, how persistent and how well-confirmed is
this name's own price behaviour?"*. It is the first engine built from the
`momentum_score.md` library after `MOM-1`..`MOM-6`, and it is **additive**: it
reads the same underlying producers `TechnicalScore` reads and leaves that
engine's owner vector byte-identical (§5 below).

---

## 1. Registration (the `UNIV-NEWENGINE` plumbing contract)

| Surface | Value |
| --- | --- |
| Gate | `enable_momentum_score` |
| Gate default (shipped) | `False` — `default_config.py::SHIPPED_DEFAULTS` |
| Env alias | `TRADINGAGENTS_ENABLE_MOMENTUM_SCORE` — `default_config.py::_ENV_OVERRIDES` |
| `ENGINE_GATES` | `"momentum": "enable_momentum_score"` (`strategies/quant_scorecard.py`) |
| `ENGINE_TOOLS` | `"momentum": "get_momentum_score"` |
| `ENGINE_SECTIONS` | `"momentum": "market"` — the stock's own price behaviour is the market analyst's section |
| Leaf reader | `quant_scorecard._read_momentum:293` |
| Engine module | `strategies/momentum_score.py` |
| Doc | this file |
| Web | see §8 |

**No engine leaf is bound to a toolset** (`agents/toolsets.py::market_tools`
docstring): the number reaches the analyst as *supplied text* through
`report_hygiene.engine_score_block` / `scorecard_context_block` under
`enable_quant_scorecard`, and as the authoritative
`## MomentumScore (engine score)` report section derived from the ownership map.
`get_momentum_score` is declared in `tests/test_calc_agent_wiring.py::
TOOL_LEGACY_BINDING` with that consumer, exactly as the other eight engine leaves
are.

---

## 2. The eight legs (`momentum_score.md` §54)

`M = w_P·P + w_R·R + w_T·T + w_A·A + w_B·B + w_V·V + w_Q·Q + w_D·D`, each leg
itself a 0-100 family score over *members*, combined through
`score_engine.combine` (renormalised over the members measured; a leg below its
floor is withheld with its reason, never 0). 41 members in total.

| Leg | Members | Producer (existing, cited in `COMPONENTS`) | Section |
| --- | --- | --- | --- |
| **P** price | `r_5,r_21,r_63,r_126,r_252` | `extended_indicators.roc` / `factors.momentum_multihorizon:418` | §3 |
| | `mom_12_1` | `momentum.momentum_12_1:358` | §2.1 |
| **R** relative | `rs_slope_pct`, `rs_new_high`, `rs_divergence` | `relative_strength.slope_pct:49`, `rs_position:89`, `divergence:195` (via `relative_strength_report:214`) | §16 |
| | `rs_vs_sector` | `relative_strength.relative_strength_vs_sector:276` (sector SPDR ETF) | §1.4/§16 |
| | `rs_percentile` | `factors.percentile_rank:59` via the §48/§49 normalizer — present only when a reference cross-section is supplied | §1.6 |
| **T** trend strength | `adx`, `di_spread` | `technical_factors.adx:230` | §38/§39 |
| | `ma_distance` | `technical_factors.sma_legs:1050` | §5.1 |
| | `ma_slope` | `technical_depth.moving_average_depth:218` | §5.4 |
| | `sma_stack` | `swing.trend_architecture:76` | §5.5 |
| | `trend_slope`, `trend_r2` | `technical_depth.regression_read:149` (`slope_pct`, `r2`) | §9.1–§9.4 |
| **A** acceleration | `accel_short_medium` = `R_63−R_21` | the §4.1 spread over `momentum_multihorizon` | §4.1 |
| | `accel_medium_long` = `R_21−R_126` | the §4.2 spread | §4.2 |
| | `macd_hist_accel` | `technical_factors.macd_depth:1106` (`hist_accel`/close) | §11.4 |
| **B** breakout | `donchian_20/50/100/252` | `technical_factors.donchian_channel:468` at n = 20/50/100/252 (`persistence_up − persistence_dn`) | §6.1 |
| | `breakout_strength` | `technical_factors.volume_depth:1273` (ATR units) | §6.5/§30 |
| | `dist_from_high` | `factors.high_distance:35` | §6.2 |
| **V** volume | `rvol` | `momentum.rvol:25` | §13.1 |
| | `volume_trend` | `technical_factors.volume_depth:1273` | §13.2 |
| | `obv_slope_norm` | `technical_factors.obv_divergence:542` | §14 |
| | `cmf` | `extended_indicators.chaikin_money_flow:263` | §15 |
| | `pv_corr` | `factor_expressions.corr:224` (close vs volume, k=20) | §13.3 |
| **Q** quality | `efficiency_ratio` | `momentum_score.efficiency_ratio` (**built this round**) | §8.1 |
| | `positive_day_ratio` | `momentum_score.positive_day_ratio` (**built this round**) | §8.3 |
| | `autocorr1` | `book_risk.return_autocorrelation:355` (`acf[0]`) | §40 |
| | `vol_adjusted` | `factors.vol_adjusted_momentum:46` | §7.1 |
| **D** risk-adjusted | `realized_vol` | `regime.realized_vol:39` | §7/§26 |
| | `downside_dev` | `evaluate.downside_deviation:846` | §26 |
| | `max_drawdown` | `evaluate.max_drawdown:222` | §23 |
| | `ulcer` | `evaluate.ulcer_index:1037` | §25 |
| | `atr_pct` | `size.atr:143` (ATR/close) | §30 |

Bands and ramps are declared in one place (`BANDS`, `RAMPS`) and every edge is a
hypothesis, not a measurement — which is why the composite is `RESEARCH_ONLY`.

### 2.1 The composite weight vector is NOT owner-signed ⚠

§54 writes the weights symbolically (`w_P … w_D`). The only numbers the library
prints are §47's *"For example: 0.25M_price + 0.20M_trend + 0.15M_relative +
0.10M_acceleration + 0.10M_volume + 0.10M_quality + 0.05M_breakout +
0.05M_riskadj"*, which sum to 1.0. The engine declares **the library's own
example** as `LEG_WEIGHTS`, prints the vector it used in every `basis`, and
labels it in the docstring, the render and this document as **pending the
owner's ratification**. No value was invented; the alternative `weights=None`
falls back to `score_engine.combine`'s equal-weight path.

---

## 3. The normalization contract (`MOM-2`; §48 primary, §49 declined alternative)

`momentum_score.normalize_component(values, method=...)` is the engine's **one**
normalization contract:

```
§48 (primary, method="z"):  Z = (x − μ)/σ  →  Z* = clip(Z, −3, +3)  →  S = 50 + 16.667·Z*
§49 (alternative):          S = 100 · PercentileRank(x)          ← one-line change (method="percentile")
```

The three constants live in one named place (`Z_CENTER = 50.0`,
`Z_SCALE = 16.667`, `Z_WINSOR_LIMIT = 3.0`); the z leg reuses the repo's one
cross-sectional standardiser (`cross_section.cross_sectional_z:70`), and the
±3σ clip plus the affine map are the part that did not exist (no `16.667` token
was anywhere in the repo; `cross_section.winsorize:31` clips at the 0.01/0.99
**quantiles**, not at ±3σ; `score_engine.align:69` maps by band/ramp edges).

**What the library prescribes.** §48 is the base rule and §49 is introduced as
*"An alternative"*, so §48 is the default. §19 restates the same transform and
its own worked endpoints (`Z=−3 → 0`, `Z=0 → 50`, `Z=+3 → 100`).

**The ambiguity, and how it is resolved.** The library fixes the *transform* but
is silent on the *population*: both of its own forms are **cross-sectional**
(§19's `μ_M`/`σ_M`, §49's `PercentileRank`). A per-name engine has no universe to
standardise over, so:

* a member handed a **reference cross-section** (`reference={member: [values]}`)
  is normalized by §48 — the name under test is the last entry of its own
  reference set;
* otherwise the member is mapped by its **own declared band/ramp** through
  `score_engine.align` — the kernel's declared min/max form, which is the
  mapping every other engine in this repo uses.

**Which was built:** `normalize_component` implements §48 (and §49 behind
`method="percentile"`), and it is exercised whenever a reference cross-section is
supplied; the leaf, which has no universe and fetches none, uses the declared
ramps. Both statements are true of the code as landed, and `rs_percentile` exists
only on the reference path.

---

## 4. The meta set stays OUTSIDE the score (`MOM-3`; §§50–§52)

Emitted under `momentum_score(...)["meta"]` beside the number and never folded
into it.

| Item | Outcome | Producer / reason |
| --- | --- | --- |
| `MomentumCoverage` | **built** | `score_engine.combine`'s own coverage (weight fraction over the eight legs), plus the count of legs measured |
| horizon `Conviction` (§50) | **built** | `horizon_conviction` — both library forms: `1 − σ(S_5..S_252)/100` and `#{S_h>50}/N_h`, over the P leg's aligned horizon scores |
| horizon `Dispersion` (§51) | **built** | `horizon_dispersion` — `Std(S_5..S_252)` over the same horizon scores |
| family `Divergence` (§52) | **built** | `leg_divergence` — `S_price−S_volume`, `S_short−S_long`, `S_price−S_fundamental` (when a fundamental sub-score is supplied); printed as diagnostics only, exactly as §52 requires |
| `MomentumRegimeCompatibility` | **DECLINED, in writing** | No producer exists anywhere in the repo, and the library states **no formula** — §54 names the quantity and §43 says only that momentum *"should behave differently"* per regime. Building one means inventing a regime→compatibility mapping and a rating semantic, which is the owner's call, not a default (the `EVT-1` lesson: never fabricate a declared vector over inputs that are absent on most runs). Recorded in `momentum_score.DECLINED_SUB_ITEMS["regime_compatibility"]` |

---

## 5. Ownership (`MOM-4`, owner decision 2026-09-27): the legs STAY PUT

`technical_score.CATEGORY_WEIGHTS` keeps `momentum 18.0`, `relative_strength 12.0`,
`trend 20.0`, `breakout 10.0`, `volume 10.0`, `volatility 5.0` — byte-identical.
The migration this row considered is **declined**: MF-6 already trimmed that table
to the legs that survive the 2026-09-27 panel (owner decision, "trim the legs,
keep the vector"), and re-pointing 75 of its 100 points would re-derive
`TechnicalScore` a second time rather than add a new read.

**Consequence, recorded honestly:** `MomentumScore` and `TechnicalScore` overlap
on the producers they read (both read `sma_stack`, `adx`, `cmf`, `sqrt_rs_minus`,
`momentum_12_1`, the RS family, …). They answer different questions — *a nine-
category technical read* vs *an eight-family momentum read* — but a reader who
adds the two numbers is double-counting, and no composite does: `MomentumScore`
is outside `COMPOSITE_ENGINES` (`{fundamental, technical, regime, risk}`), so it
cannot enter `TradeScore` by adjacency.

---

## 6. The §54 redundancy audit (`MOM-5`)

The library names five mathematically redundant pairs. The 2026-09-27 panel
(37 dates × 149 names, `~/.tradingagents/cache/panels_edgar/panels/`) was used to
**measure** what its columns can carry — pooled cross-sectionally (across names at
a date) and within-name (across the 37 dates, averaged per name). Measured on the
panel's own columns; the rest is asserted from the arithmetic.

| Library claim | Measured (panel) | Verdict |
| --- | --- | --- |
| `ROC_21 ≈ R_21` | the two are the **same formula** at the same `n` (`extended_indicators.roc(closes,n)/100` and `momentum_multihorizon`'s horizon `n`) | **arithmetic identity**, not a correlation — the engine reads **one** producer per horizon and never both |
| `RSI ↔ recent returns` | `rsi ~ roc20`: **0.73 within-name**, 0.23 cross-sectional | **MEASURED, supported within-name.** The engine does **not** score RSI at all (RSI is §53's *Overextension* group, not one of the eight §54 legs), so no RSI/returns pair exists inside it |
| `MACD ↔ MA trend` | `macd_hist_pct ~ adx` 0.07; `~ aroon_osc` 0.24 (within-name 0.07/0.24) | **MEASURED, not supported** on this panel. The engine scores the MACD **histogram acceleration** (§11.4) in A, not the MACD level, and the MA/ADX block in T — so the overlap is a second difference, not the level |
| `SMA distance ↔ trend` | `above_sma200 ~ sma_stack` 0.61 cross-sectional, 0.35 within-name (20 names) | **MEASURED, partially supported.** Both are the same MA-state block; the engine keeps `ma_distance` (a continuous distance, §5.1) and `sma_stack` (a state, §5.5) in one family (T), which is where the library puts them, and accepts the correlation inside the family |
| `OBV/PVT/CMF ↔ price-volume` | `cmf ~ rvol` −0.01; `cmf ~ obv_bullish_div` −0.10; `rvol ~ elder_ratio` **0.93 within-name** | **MEASURED, mostly NOT supported.** The CMF/OBV/rvol measures are not interchangeable on this panel; the one real pair is `rvol ~ elder_ratio`, which the engine does **not** score (neither is a member). PVT has **no scale-free producer** (see §7) |
| oscillator cluster (context) | `stoch_k ~ williams_r` **1.00**; `rsi ~ stoch_k` 0.82 | **MEASURED** — this is the MF-6 cluster; the engine scores **none** of them |

**Engine-internal redundancy actions.** §53 lists *"Trend R²"* under **both**
Trend Strength and Momentum Quality; scoring both would make one regression fit
vote twice, so it is scored **once, in T**, and Q's copy is recorded as retired
(`RETIRED_MEMBERS["trend_r2_quality"]`). A second pending member, PVT, is
recorded rather than silently dropped (§7).

---

## 7. `MOM-6` — each §53 sub-item with no producer: built or declined

| Sub-item | Outcome | Evidence / reason |
| --- | --- | --- |
| efficiency ratio | **BUILT** | `momentum_score.efficiency_ratio` (§8.1, `|P_t−P_{t−n}| / Σ|dP_i|`). The nearest existing producer, `regime.choppiness:141`, computes the same ratio **inverted** onto its own 0-100 chop scale and never exposes it |
| positive-day ratio | **BUILT** | `momentum_score.positive_day_ratio` (§8.3); it also answers §8.2's trend consistency. No producer existed (`grep positive_day` = 0) |
| price-volume correlation | **BUILT** | wired to the existing generic producer `factor_expressions.corr:224` (close vs volume, k=20) as member `pv_corr`; no dedicated named producer existed |
| a 5-day return | **BUILT** | `extended_indicators.roc(closes, 5)/100` as member `r_5`; only `n=20` was wired before |
| 50/100/252-day breakouts | **BUILT** | `donchian_channel` is called at `n = 20/50/100/252` (`donchian_50/100/252`); only `n=20` was ever wired |
| horizon agreement | **BUILT** | `horizon_conviction` (§50) and `horizon_dispersion` (§51) over the P leg's aligned horizon scores — the repo's existing dispersion producers are cross-metric (`factor_dispersion.factor_score_dispersion:105`) or cross-category (`technical_score.technical_disagreement:624`), neither over `S_5..S_252` |
| industry-relative RS | **DECLINED, in writing** | no dedicated producer: `cross_section.industry_neutral_z:111` demeans a cross-section by a caller group and is wired to no RS read, and the repo carries no per-name industry return series; the sector leg (`relative_strength_vs_sector`) is the closest real reference and is already the R family's member. Recorded in `DECLINED_SUB_ITEMS["industry_relative"]` |
| PVT as a scored member | **DECLINED, in writing** | `extended_indicators.vpt:248` returns a **cumulative** level whose scale grows with the series length, so it cannot be compared across names or windows; no scale-free PVT trend producer exists. V keeps `obv_slope_norm`, `cmf`, `pv_corr`. Recorded in `RETIRED_MEMBERS["pvt"]` |

---

## 8. The web surfaces (`trading_web`)

The eight engines that predate this one are registered on **none** of the web's
per-engine surfaces (a repo-wide grep of `../trading_web` for
`get_technical_score`, `enable_*_score`, `TechnicalScore`, … returns zero code
hits). What exists is generic, and MomentumScore uses it:

| Surface | Change |
| --- | --- |
| `backend/capabilities.py` | `get_momentum_score` added to `VALUE_TOOL_SPECS` + `_value_tool_dispatch`, so the app can reach the read in-process |
| `frontend/src/valueTools.js` | catalogue entry + `VALUE_TOOL_NEEDS` gate note (`enable_momentum_score`) |
| `frontend/src/App.jsx` | no change needed — the ValueTools page renders the catalogue from `valueTools.js`, and the report viewer renders `run_card.json` generically |
| `backend/main.py` | no change needed — `allowed_config_keys()` auto-derives every `enable_*` gate, so the new gate appears on the Config screen on its own |
| `backend/config.py` | no change needed — the raw-command allowlist governs scripts, and this engine adds none |
| `README.md` | sync-table / count rows updated |
| `docs/web_TOPICS.md` | regenerated from the declarations |

The engine's number also reaches the app the way every engine does: the run
card's `quant_scorecard` block (present when `enable_quant_scorecard` is on) and
the report tree's `1_analysts/market.md` engine section.

---

## 9. Verification

`tests/test_momentum_score.py` (21 tests, `pytestmark = pytest.mark.timeout(120)`,
hermetic — the leaf's fetch is monkeypatched) covers:

* the eight legs are exactly §54's and each declares ≥ 1 mapped member naming a
  producer and a section — **a leg can never be silently absent** (every leg key
  is present in every result);
* the gate ships `False` in `SHIPPED_DEFAULTS` and `DEFAULT_CONFIG`, and is
  registered in `ENGINE_GATES`/`ENGINE_TOOLS`/`ENGINE_SECTIONS`;
* §48's endpoints and ±3σ clip, and §49 as a one-line alternative;
* the reference-cross-section path actually reaches `normalize_component`;
* the composite is withheld (not 0) below its floor, and the meta never moves it;
* §50's two forms, §51's dispersion, the written declines;
* `efficiency_ratio` / `positive_day_ratio` against the library's own formula;
* the leaf is gated off by default and, with the gate on, computes and renders
  **all eight legs** plus the meta block;
* `technical_score.CATEGORY_WEIGHTS` is unchanged (`MOM-4`).

`tests/test_calc_agent_wiring.py`, `tests/test_quant_scorecard.py` and
`tests/test_engine_ownership_map.py` are green with the ninth engine.

---

## 10. Status and limits

* **`RESEARCH_ONLY`.** The composite's weight vector is the library's §47
  *example* and the leg mappings are unmeasured hypotheses; Phase C is what turns
  them into a validated table (`MEASUREMENT_FINDINGS.md`).
* Nothing here sizes, gates, rates or reaches `decision_guardrail.SCORE_BANDS`.
  The bands are §49's own descriptive bands, which the library states are *"not
  trading recommendations"*.
* `MomentumScore` is **not** in `COMPOSITE_ENGINES`; it does not feed
  `TradeScore`.
* The run card carries MomentumScore through the `quant_scorecard` block; there
  is **no** dedicated `momentum_score` card key (the other engines have one), so
  a reader looking for a per-engine card block finds it inside the scorecard
  block instead.
