# ScoreUniverse — the systems beyond the set, and what the tree already computes

**Part of the score-engine design set: [`README.md`](README.md)** (master —
architecture, cross-engine rules, the composite, the code defects, the phase plan,
the open questions). Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`RiskScore.md`](RiskScore.md), [`NewsScore.md`](NewsScore.md),
[`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
[`MarketScore.md`](MarketScore.md), [`ValuationScore.md`](ValuationScore.md),
[`CompositeTradeScore.md`](CompositeTradeScore.md).

**Scope: the survey.** The owner's `Strategies/other_score.md` (1,186 lines, 32
numbered sections, plus a closing 24-system hierarchy) catalogs the quantitative
scoring systems *outside* the nine libraries in `Strategies/scores/` and then
recommends a hierarchy for them. This document accounts for that survey section by
section: what the tree already computes, what it does not, where a survey system
would collide with a built engine, and what each gap would need.

Status: **a survey ledger. Nothing here is built, weighted or gated for the
survey — no module, gate, config key or leaf was added (2026-09-26).** Of the 32
sections, **10 contain a quantity the tree already computes in full** (§2, §4, §5,
§6, §7, §8, §9, §10, §17, §21), **3 are wholly absent** (§20, §22, §23) and the
remaining **19 are half-built**; §7 puts every gap to an owner decision.

---

## 0. Provenance, the true counts, and what this document may not do

### 0.1 The survey's framing, verbatim

> *"Yes. If you mean **quantitative stock/investment scoring systems beyond the
> eight-ish scores you've been building**, there is a very large ecosystem. They
> fall into several families."* (`Strategies/other_score.md:1-3`)

It then works through 32 families, from factor/style scores (§1) to a composite
conviction score (§32), and closes with two sections that matter more than the
list: **"The larger score universe"** (`:1102`, a 9-branch / 44-leaf taxonomy) and
**"For your system specifically"** (`:1145`, the hierarchy). Its own warning:

> *"I would **not** turn all of these into 30–40 top-level scores. That creates the
> exact problem you're already trying to avoid: redundant evidence, unstable
> weighting, and an increasingly enormous decision context."* (`:1147-1151`)

### 0.2 The hierarchy — the counts, counted

The master (`README.md` §1.1) said "20 secondary engines"; the survey's list is
**numbered 10–20, which is eleven entries**, and 9 + 20 + 4 = 33 ≠ 24. Counted
from the list entries:

| Tier | Count | Names |
| --- | --: | --- |
| Core investment engines | **9** | Fundamental, Valuation, Technical, **Momentum**, Regime, Risk, News, Sentiment, Event |
| Secondary / specialised | **11** | Earnings, Flow, Options, Breadth, RelativeStrength, Quality, CapitalAllocation, Moat, AIAdoption, AIThreat, Crowding |
| Meta-scores, kept separate | **4** | DataConfidence, SignalAgreement, ForecastUncertainty, ModelConsensus |
| **Total** | **24** | |

**Exactly 8 of the 24 share a name with a specified library** (fundamental,
valuation, technical, regime, risk, news, sentiment, event). `MomentumScore` has
**no library** — the library `market_score.md` specifies a `MarketScore`, which is
**not one of the 24 names**. None of the 11 secondary names has a library; none of
the 4 meta names has one either, though three have a nearest producer (§3). The
master's *"Twenty of the 24 named systems have no spec, no library and no code"*
is corrected in the same round (§5 D-2).

### 0.3 What this document may not do

1. **It may not create an engine.** No weight, gate, leaf, config key or composite
   entry exists for anything in the survey, and none is proposed here as decided.
2. **It may not resolve a collision.** Where a survey system restates a quantity a
   built engine already owns, invariant 8 (one quantity → one authoritative
   producer) makes it an owner decision — recorded in §6, not taken.
3. **It may not treat the survey's formulas as specifications.** They are sketches
   in prose: three of them are dimensionally wrong as written (§5 D-1, D-8, D-12),
   and the tree's own producers disagree with several (§5).
4. **It may not quietly re-use a name.** `MomentumScore`, `FlowScore`,
   `OptionsScore`, `BreadthScore`, `QualityScore`, `CrowdingScore`,
   `EarningsScore`, `MoatScore`, `SignalAgreementScore` and `ModelConsensusScore`
   each denote something in the survey and something else in the tree (§5 D-9).

---

## 1. The ledger — all 32 sections

Verdict vocabulary: **PRESENT** (built as described), **PARTIAL** (some legs
exist), **ABSENT** (nothing in the tree), **ELSEWHERE** (a different built object
already computes the quantity). Every symbol below was read this round; line
numbers are inside the named symbol.

| § | Section | Verdict | Producer(s) | Note |
| --: | --- | --- | --- | --- |
| 1 | Factor / Style Scores (10 named) | **PARTIAL** | `strategies/factors.py::momentum:24`, `::value_momentum_score:80`, `::category_scores:258`, `::quality_band:224`; `strategies/momentum.py::momentum_12_1:358`; `strategies/quant_baseline.py::value_score:52`, `::quality_score:63`; `strategies/liquidity_risk.py::amihud_illiquidity:71` | 9 of the 10 have *some* producer; **Size has none** (`strategies/size.py` is position sizing, not a size factor). No score is named or composited as the survey describes |
| 2 | Composite Fundamental (Piotroski F, Altman Z, Beneish M) | **PRESENT** | `dataflows/quantitative_scores.py::piotroski_f_score:202`, `::piotroski_f_score_detailed:590`, `::altman_z_score:181`, `::altman_variant:409`, `::beneish_m_score:113` | All three built and **component-by-component identical** to the survey; the tree additionally ships Z'/Z''/Z''-EM, Ohlson O, Zmijewski X, Mohanram G and Montier C |
| 3 | Earnings / Estimate (Revision, Surprise, Acceleration) | **PARTIAL** | `strategies/analyst_revisions.py::revision_ratio:79`, `::estimate_change_index:176`, `::revision_index:289`; `strategies/events.py::surprise_score:17`; `strategies/catalyst.py::last_earnings_surprise:77` | Revision and Surprise built; **Earnings Acceleration ABSENT** (`strategies/sector_rank.py::_acceleration:289` is *price* acceleration) |
| 4 | Analyst / Consensus (Consensus, Target Upside, Dispersion) | **ELSEWHERE** for 4.1, **ABSENT** for 4.2–4.3 | `strategies/consensus.py::weighted_consensus:32`, `::rating_to_number:8`, `::agreement_score:14`; `agents/utils/analysis_tools.py::get_consensus:2607` | Consensus is built as a continuous stance in [-1,1], not the survey's count fraction; **no target-price upside and no target-price dispersion producer** |
| 5 | Sentiment (news, social, momentum, divergence) | **PRESENT** / **PARTIAL** | `strategies/sentiment_score.py::sentiment_score:467`; `strategies/sentiment.py::aggregate_weighted_sentiment:1450`, `::daily_sentiment_sma:511`, `::compute_social_scores:273`, `::sentiment_velocity:25`; `strategies/sentiment_score.py::confirmation_quadrant:342` | News tone, momentum and social tone are built; **engagement weighting is not** (an LLM instruction, not a producer); divergence exists as a 4-label quadrant, not a z-difference |
| 6 | News / Event (intensity, novelty, event impact, catalyst) | **ELSEWHERE** / **PRESENT** / **PARTIAL** / **ABSENT** | `strategies/sentiment.py::mention_volume:776`; `strategies/news_score.py::news_novelty:331`; `strategies/event_state.py::imminence:349`; `strategies/catalyst.py::implied_move_from_history:138` | Intensity is built but wired as *attention*, not as a neutral leg; novelty built; **no `P × M` product**; **no signed catalyst score** |
| 7 | Technical (Trend, Breakout, Mean-Reversion, RS, Trend Quality) | **PRESENT** / **PARTIAL** | `strategies/technical_score.py::technical_score:324` (categories `trend`, `breakout`, `mean_reversion`, `relative_strength`); `strategies/regime_state.py::regime_relative:127`; `strategies/relative_strength.py::relative_strength_report:214`; `strategies/regime.py::trend_strength:130` | Trend and RS built; Breakout's canonical value is unreachable (`donchian_channel:413` returns `None`); the engine's mean-reversion set differs from the survey's; TrendConsistency has no producer **[CORRECTED 2026-09-26: stale — `strategies/technical_factors.py::donchian_channel:468` takes `closes` and computes `breakout_up`/`breakout_dn` against `breakout_ref_up`/`breakout_ref_dn`, and two callers pass it (`agents/utils/analysis_tools.py:1364`, `strategies/value_dip.py:1555`). The residual gap is narrower: `technical_score`'s `breakout` category (`strategies/technical_score.py:47` weight, components `:184-187` = `vcp_candidate`/`near_breakout`/`pullback_candidate`/`trigger_candle`) never consumes the Donchian value. `MASTER_PLAN.md` DOC-1.]** |
| 8 | Regime (trend, volatility, risk-on/off, HMM) | **PRESENT** / **PARTIAL** | `strategies/regime.py::hmm_filtered_regime:545`, `::hmm_regime:743`, `::vol_percentile:59`; `strategies/regime_state.py::regime_vol_ratio:92`, `::regime_trend:65`; `strategies/regime_score.py::regime_score:265`; `strategies/regime_performance.py::macro_regime:76` | HMM filtered probabilities built (not surfaced into `RegimeScore`); vol regime built with an ATR-ratio estimator, not `σ_short/σ_long`; risk-on/off built without commodities |
| 9 | Market Breadth (A/D ratio, A/D line, thrust, % above SMA) | **PARTIAL** / **ABSENT** / **PRESENT** | `strategies/market_breadth.py::market_breadth:114`; `agents/utils/analysis_tools.py::_market_breadth_read:375`; `strategies/sector_breadth.py::mcclellan_read:213` | `% above SMA` (20/50/200) is fully built and market-wide; `ad_ratio` is a **net** ratio, not the survey's adv/dec; **no cumulative A/D line**; thrust exists per sector, not market-wide |
| 10 | Relative Strength / Leadership (benchmark-relative, sector-relative, relative momentum) | **PRESENT** / **PARTIAL** | `strategies/regime_state.py::regime_relative:127`; `strategies/sector_screener.py::_rel_outperformance:248`; `strategies/rotation.py::relative_rotation:43`; `strategies/sector_breadth.py::rrg_heading:286` | Benchmark-relative is built — **and is the same formula as §7's Relative Strength**, listed twice; sector-relative is built inside the sector screen; stock-minus-**sector** momentum has no producer |
| 11 | Factor Exposure | **PARTIAL** | `strategies/factors.py::fama_french_5_factor:518` (built, **no reader**), `::composite_score:115`; `agents/utils/analysis_tools.py::get_composite_rank:5292` | FF5 loadings exist but are unreachable; no Value-heavy / Growth-heavy exposure composite |
| 12 | Crowding | **PARTIAL** | `strategies/short_interest.py::short_interest_percentile:35`; `agents/utils/moomoo_extra_tools.py::get_institution_holdings:236`; `strategies/orderflow.py`; `strategies/options_surface.py` | Legs exist, no object. `SentimentScore`'s `extreme_crowding` is **attention** crowding, a different quantity |
| 13 | Short-Squeeze | **PARTIAL** | `strategies/short_interest.py::short_interest_percentile:35`; `dataflows/massive.py::get_short_interest_massive:485` (days-to-cover, printed only) | No squeeze composite; no securities-lending rate; `strategies/short_interest.py::DIRECTION` states high short interest is **bearish positioning with squeeze risk**, not a bullish signal |
| 14 | Options (IV score, IV rank, put/call, skew, gamma exposure) | **PARTIAL** | `strategies/options_surface.py::iv_percentile:15`, `::put_call_oi_concentration:34`, `::iv_skew:25`, `::volatility_risk_premium:140`; `strategies/derivatives_gamma.py::gex_per_strike:52` | Four of five built. **IV Rank min-max ABSENT** (only the percentile form); `get_options_iv_read` prints `n/a` because no per-day IV history source exists |
| 15 | Flow (ETF, institutional, dark-pool / block) | **PARTIAL** | `strategies/orderflow.py::institutional_net:45`, `::distribution_score:61`; `dataflows/finra.py::get_dark_pool_flow:109` | Institutional and dark-pool flow exist as raw reads; **ETF net flow ABSENT** (the producer itself records that no vendor here publishes creation/redemption — `strategies/sector_screener.py::ETF_VOLUME_NOTE:888`); **block-flow ABSENT** |
| 16 | Insider (buying score, transaction abnormality) | **PARTIAL** | `dataflows/massive.py::get_form4_insider_massive:625`; `agents/utils/analysis_tools.py::get_form4_insider:2195` | Buys/sells counts and dollar values are emitted — the **inputs** of `IBS`, not the ratio; no historical-average transaction size |
| 17 | Institutional Ownership | **PRESENT** | `agents/utils/moomoo_extra_tools.py::get_institution_holdings:236`; `strategies/liquidity_risk.py::ownership_hhi:130`; `agents/utils/analysis_tools.py::get_ownership_concentration:8033` | IO, ΔIO and concentration all have producers; the HHI is scoped as a governance flag, on a 0–10000 scale |
| 18 | Capital Allocation (ROIC, reinvestment, buyback yield, dividend yield, TSY) | **PARTIAL** | `strategies/capex_quality.py::capex_quality_read:126`; `strategies/ratios.py::compute_ratios:437`; `strategies/capital_income.py::indicated_yield:55`; `agents/utils/market_position_tools.py::get_share_buyback_authorization:49` | Dividend yield built; **level ROIC, reinvestment rate, buyback yield and total shareholder yield all ABSENT** (only *incremental* ROIC exists; the buyback tool refuses the remaining-authorization number by design) |
| 19 | Moat / Competitive Advantage | **PARTIAL** | `strategies/value_dip.py::decline_driver_check:952`; `strategies/capex_quality.py::capex_quality_read:126`; `dataflows/patentsview.py::get_patent_activity:57` | A loss-of-moat proxy and an innovation gauge; market share, pricing power, switching costs and customer concentration have no producer — `value_dip.py:964` says the data is unavailable |
| 20 | AI / Technology Adoption | **ABSENT** | `none` | Zero hits for `ai_adoption` / `ai_threat` / `disruption_exposure`; nearest is theme *mention* detection (`strategies/theme_triggers.py::theme_triggers:145`) |
| 21 | Valuation (relative, historical percentile, DCF MOS, reverse DCF) | **PRESENT** | `strategies/fundamental_score.py::valuation_subscore:220`; `strategies/peer_universe.py::sector_medians_for:430`; `strategies/value_dip.py::valuation_z_read:122`; `strategies/normalized.py::margin_of_safety:120`; `strategies/reverse_dcf.py::reverse_dcf:90` | **All four legs have producers**, none assembled into a `ValuationScore`; historical *percentile* is a z-score today. This is the section that overlaps the specified-but-unbuilt library ([`ValuationScore.md`](ValuationScore.md) §0.2) |
| 22 | Economic Sensitivity (rate, inflation, USD, commodity betas) | **ABSENT** | `none` | No per-name regression on macro factors. Adjacent objects are a **regime label** (`strategies/regime_performance.py::macro_regime:76`) and a **credit band** (`strategies/credit_spread.py::credit_stress_level:44`) — neither is `Cov(R, X)/Var(X)` |
| 23 | ESG / Sustainability | **ABSENT** | `none` | No ESG dataflow or producer, and the survey's own hierarchy reserves no slot for it (§5 D-6) |
| 24 | Governance Risk | **PARTIAL** | `strategies/liquidity_risk.py::ownership_hhi:130`; `strategies/value_dip.py::decline_driver_check:952` | One of seven variables (ownership concentration) has a producer; board independence, related-party transactions, auditor issues, executive turnover and compensation have none |
| 25 | Dilution | **PARTIAL** | `dataflows/statement_parsing.py::enrich_screen_ratios:1101` (`shares_issued`); `agents/utils/market_position_tools.py::get_share_buyback_authorization:49`; `agents/utils/benzinga_tools.py::get_offerings_calendar:73` | The share-count change is derived and consumed by Piotroski (`f_eq`); **no `DilutionScore`**, and the options/RSU/convertible overhang leg has no input at all |
| 26 | Buyback Quality | **PARTIAL** | `agents/utils/market_position_tools.py::get_share_buyback_authorization:49` | Repurchase **spend** and the 4-quarter share-count change exist; neither `BuybackYield` nor `CapitalAllocationQuality` exists as a scored quantity, and no feed carries a repurchase *price* |
| 27 | Sustainability / Earnings Persistence | **PARTIAL** | `strategies/earnings_quality.py::earnings_quality_verdict:24`, `::dechow_dichev_aq:118`; `dataflows/quantitative_scores.py::growth_score:842` | Accrual quality built (Sloan/Dechow-Dichev); the **persistence statistic** (`σ(ΔEPS)`, EPS autocorrelation) has no producer |
| 28 | Forecast Uncertainty | **PARTIAL** | `strategies/tail_risk.py::_uncertainty:103`; `strategies/conformal.py::quantile_band:118`; `strategies/sentiment.py::sentiment_dispersion:1005` | Ensemble dispersion and calibrated intervals exist; **none of the survey's five forecast-dispersion inputs** has a producer (price-target low/high/mean are fetched but never spread) |
| 29 | Model Confidence | **PARTIAL** | `strategies/calibration.py::calibrated_confidence:171`, `::calibration_table:22`, `::isotonic_calibrate:143`; `strategies/conformal.py::calibrate:64`; `strategies/decision_guardrail.py::cap_pm_confidence_on_judge:226` | The calibration half is built and deliberately kept separate from the score; the **multi-model consensus/dispersion pair** has no producer (and no ensemble of independent models to feed it) |
| 30 | Data Quality / Coverage | **PARTIAL** (best covered) | `strategies/data_quality.py::aggregate_quality:46`, `::disagreement_flag:80`, `::fundamentals_pit_ok:102`; `strategies/sentiment.py::decayed_weight:799` | `aggregate_quality` is a weighted mean over six named inputs with four tiers, renormalised so absence is never 0; per-engine `coverage` supplies `CoverageScore`; missing: a source-quality/consistency leg and the survey's product form |
| 31 | Signal Agreement | **PARTIAL** | `strategies/consensus.py::agreement_score:14`; `strategies/score_disagreement.py::risk_disagreement:128`; `strategies/regime_score.py::regime_paths:765`; `strategies/orderflow.py::alignment:91` | Agreement exists **per surface** (ratings, one engine vs the debate, two regime paths, flow tiers) — **never across the engine vector** |
| 32 | Composite Conviction | **PARTIAL** | `strategies/trade_score.py::trade_score:293` (the `BaseSignal` slot), `strategies/data_quality.py::aggregate_quality:46`, `strategies/consensus.py::agreement_score:14`, `strategies/risk_score.py::risk_score:521`, `strategies/regime_score.py::regime_score:265` | **No `Conviction` object.** Every leg has a nearest producer, but two are the wrong shape and the formula's risk term is wrong as written (§5 D-1) |

---

## 2. What the survey asks for that the tree already has

Fourteen sections describe a quantity that already exists. The three strongest:

### 2.1 §2 — Piotroski, Altman and Beneish are built, and match

Component-by-component, with no difference found:

* **F-Score** — `dataflows/quantitative_scores.py::piotroski_f_score:202` (plain)
  and `::piotroski_f_score_detailed:590` (paper basis, gated
  `enable_f_score_detail`, default False). The nine signals are ROA>0, CFO>0,
  CFO>NI, ΔROA>0, Δleverage<0, Δcurrent-ratio>0, shares-issued≤0, Δgross-margin>0,
  Δasset-turnover>0 — the survey's four buckets, and it never lists the nine.
* **Z-Score** — `::altman_z_score:181` returns exactly
  `1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 1.0·X5` with the survey's five ratios; the
  engine additionally ships `::altman_variant:409` (Z'/Z''/Z''-EM) and
  `::altman_zone:482`.
* **M-Score** — `::beneish_m_score:113` with the eight canonical 1999 indices and
  weights (`dsri 0.92, gmi 0.528, aqi 0.404, sgi 0.892, depi 0.115, sgai −0.172,
  tata 4.679, lvgi −0.327`) and the `−4.84` constant.

The survey omits the variants the tree already has (Ohlson O at
`strategies/normalized.py::ohlson_o_score:157`, Zmijewski X at `:217`, Mohanram G
at `dataflows/quantitative_scores.py::growth_score:842`, Montier C at
`::overpriced_score:934`) — a subset, not a contradiction.

### 2.2 §21 — the valuation legs exist; only the assembly does not

Relative multiples (`strategies/ratios.py::compute_ratios:437` plus peer medians
`strategies/peer_universe.py::sector_medians_for:430`) feed
`strategies/fundamental_score.py::valuation_subscore:220`; historical deviation is
`strategies/value_dip.py::valuation_z_read:122`; margin of safety is
`strategies/normalized.py::margin_of_safety:120`; reverse DCF is
`strategies/reverse_dcf.py::reverse_dcf:90`. **This is the same collision
[`ValuationScore.md`](ValuationScore.md) §0.2 records as unresolved** — a new
engine would compete with a sub-score of a built one.

### 2.3 §30 — data quality is the best-covered system in the survey

`strategies/data_quality.py::aggregate_quality:46` is already a weighted mean over
six named inputs (price 22 / volume 15 / fundamentals 22 / news 14 / options 12 /
macro 15) with four tiers, renormalised over present inputs; `::disagreement_flag:80`
is the cross-vendor consistency check and `::fundamentals_pit_ok:102` the
point-in-time rule. The survey's closing rule — *"This should ideally be separate
from the investment score"* — is the repo's own four-output discipline
(`README.md` §1.4).

---

## 3. What is half-built

| System | What exists | What is missing |
| --- | --- | --- |
| §7 Breakout | `technical_score`'s `breakout` category (10 %), VCP/pullback/trigger producers | the price-breakout **value**: `strategies/technical_factors.py::donchian_channel:468` returns `None` and no caller derives it (`README.md` §3.1 defect 3) **[CORRECTED 2026-09-26: both halves stale — `donchian_channel` takes `closes` and computes `breakout_up`/`breakout_dn` (`breakout_ref_up`/`breakout_ref_dn` are the prior-window levels it is checked against), and two callers pass it (`agents/utils/analysis_tools.py:1364`, `strategies/value_dip.py:1555`). What is still missing is the consumption: `technical_score`'s `breakout` category reads only `vcp_candidate`/`near_breakout`/`pullback_candidate`/`trigger_candle` (`strategies/technical_score.py:184-187`), never the Donchian value. `MASTER_PLAN.md` DOC-1.]** |
| §7 Trend Quality | `strategies/regime.py::trend_strength:130` | TrendConsistency, and the product `TQS = strength × consistency` — nearest built analogue is `strategies/rotation.py::clenow_momentum:89` |
| §8 Regime | `strategies/regime.py::hmm_filtered_regime:545` (filtered `P(Regime_k \| obs)`) | the wiring into `RegimeScore` — `RegimeScore.md` §104 row 46 records it PARTIAL |
| §9 Breadth | `% above 20/50/200` market-wide | the survey's adv/dec ratio (the tree's `ad_ratio` is net), a cumulative A/D line, and a market-wide thrust |
| §14 Options | IV percentile, put/call concentration, skew, GEX | IV **rank** (min-max), and a per-day IV history to feed it |
| §15 Flow | institutional net, distribution score, dark-pool raw flow | ETF net flow (no vendor publishes it — stated by the producer) and block flow |
| §16 Insider | Form-4 buys/sells counts and values | the ratio `IBS = Buys/(Buys+Sells)` and a historical-average transaction size |
| §18 Capital allocation | incremental ROIC, dividend yield, repurchase spend | level ROIC, reinvestment rate, buyback yield, total shareholder yield |
| §25–§26 Dilution and buybacks | share-count change; repurchase spend | `DilutionRate`, the options/RSU/convertible overhang, `BuybackYield`, `CapitalAllocationQuality` |
| §27 Persistence | accrual-quality verdict, Dechow-Dichev | `σ(ΔEPS)` / EPS autocorrelation |
| §28–§29 Uncertainty and model confidence | ensemble dispersion, calibrated confidence, conformal intervals | forecast dispersion of any of the five kinds; the multi-model consensus/dispersion pair |
| §31 Agreement | four per-surface agreement reads | the cross-engine number |
| §32 Conviction | every leg's nearest producer | the object, and a corrected risk term |

---

## 4. What has no producer at all

* **§1 Size Score** — `strategies/size.py` is position sizing, not a size factor,
  and `factor_schema.py` has no size/market-cap factor. The smallest honest
  producer is a winsorised `log(market_cap)` cross-sectional factor.
* **§3 Earnings Acceleration** — `strategies/sector_rank.py::_acceleration:289`
  is *price* acceleration; the earnings series exist
  (`dataflows/statement_parsing.py::sane_eps_yoy:1032`,
  `::sane_revenue_yoy:1048`) but nothing differences them.
* **§4.2 Price-target upside and §4.3 target dispersion** — the vendor leaf prints
  mean/median/high/low; nothing computes `(target − price)/price` or the spread.
* **§6.4 Catalyst score** — `strategies/catalyst.py::build_catalyst_snapshot:246`
  returns an *unsigned de-risk scale*, because the snapshot only knows de-risking
  events (miss, macro, Fed).
* **§20 AI adoption / AI threat** — nothing; no canonical quantitative reference
  exists either (the survey's own text calls them thematic).
* **§22 Economic sensitivity** — no per-name macro beta. The only "beta" slot in
  the system, `BookState.net_beta`, is a dead field (`README.md` §3.1 defect 5). **[CORRECTED 2026-09-26: the slot is unpopulated, not unproduced — `strategies/book_risk.py::net_beta:179` computes the book beta and `strategies/cross_section.py:470-471` emits it as `net_beta_raw`/`net_beta`; what is missing is the wire — no production `BookState(...)` construction (`../TradingExecution/signald/risk/state.py:82`) passes it, so the executor field stays `None`. `MASTER_PLAN.md` DOC-20.]**
* **§23 ESG** — nothing, and the survey's hierarchy gives it no slot.

---

## 5. The survey's own defects, and the corrections they force here

**D-1 — §32's risk term is dimensionally wrong and direction-inverted.**
The survey writes `Conviction = BaseSignal × DataConfidence × Agreement × (1 − Risk)`
(`:1087-1096`, the `(1-Risk)` term at `:1095`). In this repo every engine is 0-100
with **100 = favourable**, so `RiskScore` 100 = **low** risk
(`strategies/risk_score.py::risk_score:521`; `README.md` §1.2). Therefore
`1 − Risk` with `Risk = 79.39` evaluates to `−78.39` (not a multiplier at all),
and after rescaling, `1 − Risk/100` is **1 at maximum risk and 0 at minimum** —
the opposite of the intent. The aligned term is `Risk/100`. The same survey also
mixes a 0-100 leg (`DataConfidence`, `BaseSignal`) with 0-1 legs (`Agreement`).
Recorded first in [`CompositeTradeScore.md`](CompositeTradeScore.md) §3.10.

**D-2 — the master's own counts were wrong, and are corrected this round.**
`README.md` §1.1 said "20 secondary engines" (the list has 11) and "Twenty of the
24 named systems have no spec, no library and no code" — but 8 of the 24 *do*
share a name with a library. Both corrected in place with a dated marker.

**D-3 — three sections define dilution, two define buyback yield.** §18's
`IssuanceYield` (`:694`), §24's "shareholder dilution" (`:867`) and §25's
`DilutionRate` (`:881-893`); §18's `BuybackYield` (`:676-682`) and §26's `BQ`
(`:903-907`). Invariant 8 requires the survey to say which section owns each.

**D-4 — the same formula is listed twice.** §7 `RS = R_stock − R_benchmark` and
§10 `RR = R_stock − R_benchmark` are identical; the tree computes it once
(`strategies/regime_state.py::regime_relative:127`).

**D-5 — `ad_ratio` names two different quantities.** The survey's
`ADR = Advancing/Declining` is a ratio of counts; the tree's
`strategies/market_breadth.py::market_breadth:114` computes
`(advancers − decliners) / n`. The survey's ratio has no producer, and a reader
reusing the name would get the other number.

**D-6 — §23 ESG has no slot in the survey's own hierarchy**, which lists
THEMATIC (AI adoption, disruption) and QUALITY (moat, governance, capital,
persistence) but no ESG branch — an internal inconsistency between the section
list and the closing plan.

**D-7 — §29 forbids collapsing what §32 collapses.** §29: *"I would **not**
collapse these into one number"*; §32 makes `ModelDispersion` a leg of one
`Conviction`. Not a strict contradiction — Conviction is a confidence object — but
the two sentences cannot both be read literally.

**D-8 — §14 gives one name two formulas.** `IVScore = PercentileRank(IV)` and
`IVRank = (IV − IV_min)/(IV_max − IV_min)` are different functions; the tree's
`strategies/options_surface.py::iv_percentile:15` docstring calls itself "IV
rank/percentile", so the ambiguity would be inherited (invariant 15).

**D-9 — §14's GEX formula contradicts the implementation.**
`GEX = Σ Gamma_i × OI_i × ContractSize × Price²` versus
`strategies/derivatives_gamma.py::gex_per_strike:52`'s
`gamma × OI × strike × 100` with a computed Black-76 gamma. Same name, different
formula, and the tree's version is the one with a documented sign convention.

**D-10 — §9's breadth thrust is a name with no formula.** Unlike the two measures
above it in the same section, it states no definition and no producer exists.

**D-11 — §8's trend-regime inputs match no producer.**
`Regime = f(SMA50, SMA200, ADX)`; the built legs are
`(EMA20 − EMA50)/ATR14` (`strategies/regime_state.py::regime_trend:65`),
benchmark `P/SMA − 1` (`strategies/regime_score.py::market_trend:351`) and
`f(vol_pct, trend, chop)` (`strategies/regime.py::regime_label:194`). ADX is a
`technical_score` component, never a regime input.

**D-12 — §22's sensitivities are a different object from the tree's macro reads.**
`β_rates = Cov(R_stock, ΔYield)/Var(ΔYield)` versus a market-level regime **label**
and a credit **band**. The survey's betas are a per-name regression that does not
exist.

**D-13 — §11's formula binds one symbol to two terms.**
`FactorScore = w_M·Market + w_V·Value + w_Growth + w_Q·Quality + w_M·Momentum` —
`w_M` is Market *and* Momentum, and Growth carries no subscript.

**D-14 — §17's IOC scale differs from the tree's.** `IOC = Σ Ownership_i²` in
fractions versus `strategies/liquidity_risk.py::ownership_hhi:130`'s Σ `holder_pct`²
on a **0–10000** scale.

**D-15 — §28 files forecast dispersion as uncertainty; its own canonical source
says it is a return signal.** Diether, Malloy & Scherbina (2002), fetched, finds
higher dispersion predicts **lower** future returns and states the evidence is
*"inconsistent with a view that dispersion in analysts' forecasts proxies for
risk"* (Appendix A). The survey puts it in the meta/uncertainty layer.

**D-16 — §16's insider category is declared and unfed.**
`strategies/factor_schema.py:50` lists "Insider Activity" among the categories,
but no `SUBSCORE_FACTORS` entry carries it and no `fundamental_score.py` code
feeds it — the same gap §16 itself exposes.

**D-17 — two stale provenance citations in code, found by this pass and fixed.**
`strategies/sentiment_score.py:200` and `:214` cited
`sentiment.aggregate_weighted_sentiment:1450` (the symbol is at **626**), and
`strategies/news_score.py:143` cited `news_relevance.score_news_article:56`
(the symbol is at **56**); `strategies/sentiment_score.py:203` and `:206` cited
`sentiment.daily_sentiment_sma:1335` (the symbol is at **511**). These strings are
*printed* as component provenance, so the stale numbers were visible output. Fixed
in this round, and the same drift across `docs/scores/` (a third citation form the
checker never covered) is snapped by the extended checker — §6.3.

---

## 6. The collisions, and the one rule that governs them

### 6.1 Which survey system would double-count which built engine

| Survey system | Collides with | The invariant |
| --- | --- | --- |
| §1 Value / Growth / Quality / Profitability / Earnings Quality | `FundamentalScore` sub-scores `valuation_subscore:211`, `growth_subscore:206`, `quality_subscore:201`; `strategies/factors.py::category_scores:258` | 8, 15 |
| §1 Momentum | `TechnicalScore`'s momentum/trend categories | 8, 15 |
| §1 Low-Volatility | `RiskScore` (100 = low risk) and `strategies/evaluate.py::volatility:84` | 18, 8 |
| §1 Liquidity | `RiskScore`'s liquidity component and `strategies/liquidity_risk.py` | 8 |
| §1 Investment / §18 Capital Allocation | `strategies/capex_quality.py::capex_quality_read:126`, the Capital Efficiency category | 8 |
| §4.1 Analyst consensus | `strategies/consensus.py::weighted_consensus:32` — the same quantity computed a second way | 8 |
| §4.3 / §28 Dispersion | `strategies/sentiment.py::sentiment_dispersion:1005`; `SentimentScore`'s dispersion component | 15 |
| §6.1 News intensity | `strategies/sentiment.py::mention_volume:776` (already read by two engines) | 8 |
| §7 Relative Strength / §10 benchmark-relative | each other — one quantity listed twice | 8 |
| §8 Regime paths | `RegimeScore`'s market-wide legs vs name-level `technical_score` legs | 12 |
| §11 Factor exposure | `FundamentalScore` (value/quality), `TechnicalScore` (momentum) | 8 |
| §12 Crowding | `SentimentScore`'s `extreme_crowding` (attention, not ownership) | 15 |
| §13 Short squeeze | `SentimentScore`'s `short_pct_float` leg; the producer's stated **bearish** direction | 8, 15 |
| §14 Options | `RiskScore`'s `iv_percentile` and `gamma_regime` components; `SentimentScore`'s `options` component | 8, 15 |
| §15 Institutional flow | `SentimentScore`'s `institutional` leg (`inst_flow_z`) | 8 |
| §16 Insider / §25 Dilution | Piotroski's `f_eq` share-issuance boolean | 8 |
| §21 Valuation | `FundamentalScore.valuation_subscore:211` — the open boundary | 8 |
| §27 Persistence / §30 Data quality | `FundamentalScore` FQS/FGS; the advisory `aggregate_quality` read | 8, 11 |
| §32 Conviction | `TradeScore` already carries `K` and `R` — the product would count both twice | 11, 18 |

### 6.2 What this means, stated once

Nothing in §6.1 is a defect: the tree's separation is the design. It means **a
survey system may not be built as a second producer of a quantity a built engine
already owns** — it must either become a *component* of that engine (named in its
`factor_schema` set), a *diagnostic* with no composite, or an owner decision that
moves the quantity. §8 asks for exactly that decision, per system.

### 6.3 The citation drift this pass found and fixed

`docs/scores/` cites code three ways: `path.py::symbol:LINE`, bare `path.py:N`, and
`module.symbol:LINE`. Only the first two were ever machine-checked. The third —
used in 1,346 places — had drifted: **378 citations fell outside the named
symbol's own region** (typically landing in the *previous* function's body or in a
module docstring), because lines were inserted above the definitions over many
rounds. An extended checker (`_verify_citations2.py`, region-aware, `--write`
snaps the number to the symbol's definition line) repaired them in this round; the
five stale strings in the two score modules (§5 D-17) were fixed by hand because
they are *printed* provenance. A citation whose line is inside the symbol's body —
a ratio key, a branch, a tool binding — is left exactly where it is.

---

## 7. What each system would cost

No item may start without the owner decision in §8. "Missing producer" names the
thing that does not exist; nothing here is an estimate of effort.

| System | Producers that exist | Missing producer | Measurement / contract | Decision |
| --- | --- | --- | --- | --- |
| Size (§1) | none | `log(market_cap)` winsorised-z factor + a `factor_schema` category | cross-sectional panel (Phase C) | **Q1** |
| Earnings Acceleration (§3) | the `sane_eps_yoy` / `sane_revenue_yoy` series | `Δ(growth)` producer | 4-5 annual points only — needs a stated floor | **Q1** |
| Price-target upside + dispersion (§4.2–4.3) | the vendor target triple | `(target − price)/price` and the spread, both `NA`-honest | vendor passthrough today | **Q1** |
| Catalyst score (§6.4) | `build_catalyst_snapshot:219` (unsigned) | a **signed** catalyst source | needs positive-catalyst events, not just de-risking | **Q1** |
| A/D line + market-wide thrust (§9) | `market_breadth:114` (same-day net) | a running sum and a Zweig-ratio read over the same panel | one producer, two readings | **Q1** |
| IV Rank (§14) | `iv_percentile:15` | a per-day IV history | vendor gap — the leaf already prints `n/a` | **Q1** |
| ETF flow (§15) | none | a net-flow / creation-redemption source | **no vendor publishes it** (stated in-code) | **Q1** |
| Insider ratio + abnormality (§16) | Form-4 counts and values | `buys/(buys+sells)`; a historical-average size | none | **Q1** |
| Level ROIC / reinvestment / TSY (§18) | incremental ROIC, dividends, repurchase spend | `roic(nopat, ic)`, reinvestment rate, `DY + BY − IssuanceYield` | needs a level-ROIC convention declared | **Q1** |
| Moat (§19) | loss-of-moat proxy, patent activity | margin stability, market share, pricing power | vendor-blocked (`value_dip.py:964`) | **Q1** |
| AI adoption / threat (§20) | theme mentions | a text/exposure classifier | no canonical reference exists | **Q1** |
| Economic sensitivity (§22) | FRED series are reachable | a per-name OLS on aligned macro series | a stated window; the `net_beta` slot is dead **[CORRECTED 2026-09-26: unpopulated, not unproduced — `strategies/book_risk.py::net_beta:179` produces the book beta and `strategies/cross_section.py:470-471` emits it; the missing part is the executor `BookState` wire, see §4]** | **Q1** |
| ESG (§23) | none | an ESG vendor row | absent; the survey's own hierarchy has no slot | **Q1** |
| Governance (§24) | ownership HHI | board/related-party/auditor/turnover/compensation | filing-blocked | **Q1** |
| Dilution + buyback quality (§25–§26) | share-count change, repurchase spend | `DilutionRate`, `BuybackYield`, `CapitalAllocationQuality` | Piotroski's `f_eq` must be re-pointed or declared a cross-check | **Q2** |
| Persistence (§27) | accrual-quality verdict | `σ(ΔEPS)` / lag-1 autocorrelation | needs a period floor | **Q1** |
| Forecast dispersion (§28) | ensemble dispersion, conformal intervals | `forecast_dispersion(...)` over a stored cross-section | percentile needs a cross-section, not one name's history | **Q1** |
| Model consensus/dispersion (§29) | the calibration layer | a set of independent model scores | no ensemble exists to feed it | **Q3** |
| Cross-engine agreement (§31) | four per-surface reads | `engine_agreement(scores)` over the engine vector | refuses below two measured engines; `None` is never 0 | **Q3** |
| `Conviction` (§32) | every leg's nearest producer | agreement + data confidence of the right shape | risk term must be `Risk/100`; `BaseSignal` must **not** be `TradeScore` | **Q4** |
| Any new engine at all | — | — | a gate, a leaf, an `ENGINE_GATES` entry, a `default_config.py` key, a web-app sync | **Q5** |

---

## 8. OPEN questions for the owner

* **Q1 — which of the single-system gaps, if any, get a producer?** §4 lists them:
  Size, Earnings Acceleration, price-target upside/dispersion, a signed catalyst
  score, the A/D line and market-wide thrust, IV Rank, ETF flow, the insider
  ratio, level ROIC / reinvestment / TSY, moat legs, AI exposure, macro betas,
  ESG, governance legs, persistence, forecast dispersion. Several are blocked by
  data, not by formula (ETF flow, moat, governance, ESG, IV history).
* **Q2 — dilution and buyback yield are claimed twice by the survey itself**
  (§18/§24/§25 and §18/§26). Which section owns each formula, and is Piotroski's
  `f_eq` re-pointed at a new `dilution_rate` or kept as a screening cross-check?
* **Q3 — the meta layer.** Do you want the cross-engine agreement read (§31) and
  the multi-model consensus/dispersion pair (§29)? The first needs a new producer
  over `quant_scorecard`'s engine vector; the second has no ensemble to feed it.
  **[ANSWERED 2026-09-26: yes — as a LAYER beside the engines, never as a tenth
  engine.** *"How much do the engines agree, how much do they disagree, and how
  reliable is the aggregate?"* is a different question from *"what does each
  information source say?"*, and the owner's formulas are in `MASTER_PLAN.md` §2.1
  (D6). The layer is **strictly downstream** — *"avoid engine → meta → engine …
  that creates circularity"*. The multi-model pair (§29) stays **data-blocked**:
  the repo runs one model per role, so there is no `M` to average; the shape is
  specified and the plumbing is not built speculatively.]**
* **Q4 — `Conviction` (§32).** Build it as a **separate** object — which is the
  only reading that avoids counting `K` and `R` twice — with the risk term written
  `Risk/100` and `BaseSignal` explicitly *not* `TradeScore`?
  **[ANSWERED 2026-09-26, and this survey's formula is SUPERSEDED:
  `Conviction = AgreementScore × EvidenceConfidence` (0-100), with no
  `BaseSignal` and no risk term** — the survey's
  `BaseSignal × DataConfidence × Agreement × (1 − Risk)` is replaced, which also
  removes the `(1 − Risk)` direction problem D-1 recorded (risk is a gate, per
  D3, not a multiplier inside a conviction). The object is a meta-property, so it
  lives in the meta layer.]**
* **Q5 — does any survey system become a tenth engine?** If so it needs the full
  set: a gate, a leaf, an `ENGINE_GATES`/`ENGINE_TOOLS` entry, a
  `default_config.py` key, a doc, and the web-app sync (`trading_web`'s five
  surfaces). The 24-name hierarchy implies at most 11 secondary engines and 4
  meta-scores; the survey's own advice is not to build them all.
  **[ANSWERED 2026-09-26: not automatically — and the criterion is stated.** The
  owner's test is not *"does this produce a number?"* (almost anything can) but
  *"does it represent a sufficiently distinct economic information dimension that
  deserves independent lifecycle, coverage, attribution, validation and
  configuration?"*, with **orthogonality as the diagnostic**:
  `Orthogonality = 1 − |Corr(SurveyScore, ExistingScores)|`. A survey correlating
  **0.94** with `SentimentScore` does not need an engine of its own; one near
  **0** has an argument. The owner's own examples of systems that *could* qualify
  are positioning, options flow, institutional flow, capital-flow pressure,
  supply-chain stress, AI adoption and alternative data — judged one at a time,
  never as a batch. **Consequence for this document: every `UNIV-*` gap below
  stays a component or a diagnostic, and the gate/leaf/registry/config/doc/web
  plumbing is NOT built speculatively.** The orthogonality measurement is a
  Phase 3 (panel) row, since it is a correlation like every other one.]**
* **Q6 — `MomentumScore`.** It is one of the survey's nine *core* engines and has
  no engine module, while `MarketScore` — which has a library — is not one of the 24
  names. **[CORRECTED 2026-09-27: the first half of that is no longer true in the
  document sense — the owner's `momentum_score.md` (54 sections) is now the
  MomentumScore library, and its §47-§54 architecture is what `MASTER_PLAN.md` §10's
  new `MOM-1`..`MOM-6` rows build. The code half stands: no module, no gate, no
  fifth web surface.]** Which one is the core slot for the stock's own market behaviour?
  **[ANSWERED 2026-09-26: `MomentumScore`.** *"Momentum is a characteristic of the
  security's own return behavior"*, while `MarketScore` describes the **broader
  market's** behaviour — so the core slot is `MomentumScore`, and `MarketScore`
  is the market-level engine D1 defines. The legs the owner names for it: price
  momentum `MOM_n = P_t/P_{t−n} − 1` at 5/21/63/126/252, risk-adjusted
  `RAMOM = R_n/σ_n`, relative momentum `R_stock − R_benchmark`, sector-relative
  `R_stock − R_sector`, acceleration `MOM_short − MOM_long`, consistency
  `N_positive_periods/N_periods` and persistence `N_positive_returns/N`. The
  ownership matrix that comes with the answer is in `MASTER_PLAN.md` §2.1 (D7)
  and it is the *arbitration* invariant 8 needed: RSI/MACD/%B/ATR/ADX/MA-crossovers
  stay `TechnicalScore`'s; the 12-1 return and the multi-horizon/relative/
  acceleration legs become `MomentumScore`'s; S&P and Nasdaq momentum, breadth and
  advance/decline are `MarketScore`'s; VIX is `MarketScore` or `RegimeScore`
  *depending on definition* — the one row the answer deliberately leaves for the
  build.]**
* **Q7 — the survey's naming.** Do you want the tree's names to follow the survey
  (`EarningsScore`, `FlowScore`, `OptionsScore`, `BreadthScore`,
  `RelativeStrengthScore`, `QualityScore`, `CrowdingScore`) for the components
  that already exist inside other engines — or keep the tree's component names and
  treat the survey's names as families?

---

## Appendix A — external sources, fetched this round

Every DOI below was resolved through CrossRef; the title, authors, year and
journal/publisher are what the record returned. Where the record returned no
volume or pages, none is stated. Rows already in the master's ledger (§C.1 rows
1-12, §C.2 rows 13-31) are **not** repeated here. This table is the ledger for the
survey's systems; the master's §C.2 carries a pointer to it plus the four rows that
constrain an **architecture** choice rather than one system.

| Source | Bears on |
| --- | --- |
| Piotroski (2000), "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers", *Journal of Accounting Research* — DOI `10.2307/2672906` | §2 F-Score (`dataflows/quantitative_scores.py::piotroski_f_score:202`) |
| Altman (1968), "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy", *The Journal of Finance* — DOI `10.1111/j.1540-6261.1968.tb00843.x` | §2 Z-Score (`::altman_z_score:181`) |
| Beneish (1999), "The Detection of Earnings Manipulation", *Financial Analysts Journal* — DOI `10.2469/faj.v55.n5.2296` | §2 M-Score (`::beneish_m_score:113`) |
| Fama & French (1992), "The Cross-Section of Expected Stock Returns", *The Journal of Finance* — DOI `10.1111/j.1540-6261.1992.tb04398.x` | §1 Value/Growth; `strategies/fundamental_score.py::valuation_subscore:220` |
| Fama & French (1993), "Common risk factors in the returns on stocks and bonds", *Journal of Financial Economics* — DOI `10.1016/0304-405x(93)90023-5` | §1 size/value benchmarks; `strategies/factors.py::fama_french_5_factor:518` |
| Fama & French (2015), "A five-factor asset pricing model", *Journal of Financial Economics* — DOI `10.1016/j.jfineco.2014.10.010` | §1 Profitability/Investment; §11 exposure; `strategies/factors.py` FF5 |
| Jegadeesh & Titman (1993), "Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency", *The Journal of Finance* — DOI `10.1111/j.1540-6261.1993.tb04702.x` | §1 Momentum; `strategies/momentum.py::momentum_12_1:358` |
| Banz (1981), "The relationship between return and market value of common stocks", *Journal of Financial Economics* — DOI `10.1016/0304-405x(81)90018-0` | §1 **Size Score** — the one factor/style score with no producer |
| Ang, Hodrick, Xing & Zhang (2006), "The Cross-Section of Volatility and Expected Returns", *The Journal of Finance*, 61(1) 259-299 — DOI `10.1111/j.1540-6261.2006.00836.x` | §1 Low-Volatility; `strategies/lottery.py::idiosyncratic_vol:51`; the invariant-18 collision |
| Amihud (2002), "Illiquidity and stock returns: cross-section and time-series effects", *Journal of Financial Markets* — DOI `10.1016/s1386-4181(01)00024-6` | §1 Liquidity; `strategies/liquidity_risk.py::amihud_illiquidity:71` |
| Bernard & Thomas (1989), "Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?", *Journal of Accounting Research* — DOI `10.2307/2491062` | §3 Earnings Surprise; `strategies/events.py::surprise_score:17` |
| Chan, Jegadeesh & Lakonishok (1996), "Momentum Strategies", *The Journal of Finance* — DOI `10.1111/j.1540-6261.1996.tb05222.x` | §3 Earnings Revision; `strategies/analyst_revisions.py::revision_ratio:79` |
| He & Narayanamoorthy (2020), "Earnings acceleration and stock returns", *Journal of Accounting and Economics* — DOI `10.1016/j.jacceco.2019.101238` | §3 **Earnings Acceleration** — ABSENT, and distinct from `strategies/sector_rank.py::_acceleration:289` |
| Womack (1996), "Do Brokerage Analysts' Recommendations Have Investment Value?", *The Journal of Finance* — DOI `10.1111/j.1540-6261.1996.tb05205.x` | §4.1 analyst consensus; `strategies/consensus.py::weighted_consensus:32` |
| Brav & Lehavy (2003), "An Empirical Analysis of Analysts' Target Prices: Short-term Informativeness and Long-term Dynamics", *The Journal of Finance* — DOI `10.1111/1540-6261.00593` | §4.2 price-target upside — no producer |
| Diether, Malloy & Scherbina (2002), "Differences of Opinion and the Cross Section of Stock Returns", *The Journal of Finance* — DOI `10.1111/0022-1082.00490` | §4.3 and §28 dispersion — and the source that makes dispersion a return signal, not a risk proxy (D-15) |
| Tetlock (2011), "All the News That's Fit to Reprint: Do Investors React to Stale Information?", *The Review of Financial Studies* — DOI `10.1093/rfs/hhq141` | §6.2 news novelty; `strategies/news_score.py::news_novelty:331` |
| Kaplan & Garrick (1981), "On The Quantitative Definition of Risk", *Risk Analysis* — DOI `10.1111/j.1539-6924.1981.tb01350.x` | §6.3 event impact as (scenario, probability, consequence) |
| Lo, Mamaysky & Wang (2000), "Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation", *The Journal of Finance* — DOI `10.1111/0022-1082.00265` | §7 trend and breakout evidence; the `donchian_channel:467` gap |
| Hamilton (1989), "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle", *Econometrica* — DOI `10.2307/1912559` | §8 HMM regime; `strategies/regime.py::hmm_filtered_regime:545` |
| Gilchrist & Zakrajšek (2012), "Credit Spreads and Business Cycle Fluctuations", *American Economic Review* — DOI `10.1257/aer.102.4.1692` | §8 risk-on/off credit leg; `strategies/credit_spread.py::credit_stress_level:44` |
| Andersen, Bollerslev, Diebold & Labys (2003), "Modeling and Forecasting Realized Volatility", *Econometrica* — DOI `10.1111/1468-0262.00418` | §8 volatility regime; `strategies/regime.py::vol_percentile:59` |
| Zweig (1986), *Martin Zweig's Winning on Wall Street* (Warner Books) | §9 breadth thrust — the canonical definition, and the reason its absence is a gap rather than a wording problem |
| Murphy (1999), *Technical Analysis of the Financial Markets* (New York Institute of Finance / Penguin) | §9 A/D line and %-above-SMA conventions; §8 MA-based trend regime |
| Moskowitz & Grinblatt (1999), "Do Industries Explain Momentum?", *The Journal of Finance* — DOI `10.1111/0022-1082.00146` | §10 sector-relative return; `strategies/sector_screener.py::_rel_outperformance:248` |
| de Kempenaer (2011), "Everything is Relative Strength is Everything", in *New Frontiers in Technical Analysis*, Wiley — DOI `10.1002/9781118531525.ch2` | §10 relative momentum / RRG quadrants; `strategies/rotation.py::relative_rotation:43` |
| Frazzini & Pedersen (2014), "Betting against beta", *Journal of Financial Economics* — DOI `10.1016/j.jfineco.2013.10.005` | §11 low-volatility exposure leg |
| Khandani & Lo (2011), "What happened to the quants in August 2007? Evidence from factors and transactions data", *Journal of Financial Markets* — DOI `10.1016/j.finmar.2010.07.005` | §12 crowding as unwind risk |
| Coval & Stafford (2007), "Asset fire sales (and purchases) in equity markets", *Journal of Financial Economics* — DOI `10.1016/j.jfineco.2006.09.007` | §12 and §15 institutional flow |
| Asquith, Pathak & Ritter (2005), "Short interest, institutional ownership, and stock returns", *Journal of Financial Economics* — DOI `10.1016/j.jfineco.2005.01.001` | §13 short interest as a return signal |
| Boehmer, Jones & Zhang (2008), "Which Shorts Are Informed?", *The Journal of Finance* — DOI `10.1111/j.1540-6261.2008.01324.x` | §13 direction — supports `strategies/short_interest.py::DIRECTION`'s warning |
| Carr & Wu (2009), "Variance Risk Premiums", *Review of Financial Studies* — DOI `10.1093/rfs/hhn038` | §14 IV score and the VRP leg |
| Bakshi, Kapadia & Madan (2003), "Stock Return Characteristics, Skew Laws, and the Differential Pricing of Individual Equity Options", *Review of Financial Studies* — DOI `10.1093/rfs/16.1.0101` | §14 skew; `strategies/options_surface.py::iv_skew:25` |
| Gârleanu, Pedersen & Poteshman (2009), "Demand-Based Option Pricing", *Review of Financial Studies* — DOI `10.1093/rfs/hhp005` | §14 gamma exposure; `strategies/derivatives_gamma.py::gex_per_strike:52` |
| Ben-David, Franzoni & Moussawi (2018), "Do ETFs Increase Volatility?", *The Journal of Finance* — DOI `10.1111/jofi.12727` | §15 ETF flow — the measure with no input on this repo's vendors |
| Buti, Rindi & Werner (2017), "Dark pool trading strategies, market quality and welfare", *Journal of Financial Economics* — DOI `10.1016/j.jfineco.2016.02.002` | §15 dark-pool / block flow; `dataflows/finra.py::get_dark_pool_flow:109` |
| Jeng, Metrick & Zeckhauser (2003), "Estimating the Returns to Insider Trading: A Performance-Evaluation Perspective", *Review of Economics and Statistics* — DOI `10.1162/003465303765299936` | §16 insider buying |
| Gompers & Metrick (2001), "Institutional Investors and Equity Prices", *The Quarterly Journal of Economics* — DOI `10.1162/003355301556392` | §17 institutional ownership |
| Gompers, Ishii & Metrick (2003), "Corporate Governance and Equity Prices", *The Quarterly Journal of Economics* — DOI `10.1162/00335530360535162` | §24 governance |
| Chen, Roll & Ross (1986), "Economic Forces and the Stock Market", *The Journal of Business* — DOI `10.1086/296344` | §22 economic sensitivity — the evidence for a per-name macro-beta producer |
| Pástor, Stambaugh & Taylor (2021), "Sustainable investing in equilibrium", *Journal of Financial Economics* — DOI `10.1016/j.jfineco.2020.12.011` | §23 ESG — and why it stays outside the decision composite |
| Damodaran, "Relative Valuation: First Principles", in *Damodaran on Valuation*, Wiley — DOI `10.1002/9781119201786.ch7` | §21 relative valuation |
| Pontiff & Woodgate (2008), "Share Issuance and Cross-sectional Returns", *The Journal of Finance* — DOI `10.1111/j.1540-6261.2008.01335.x` | §25 dilution — share issuance as its own cross-sectional predictor |
| Ikenberry, Lakonishok & Vermeulen (1995), "Market underreaction to open market share repurchases", *Journal of Financial Economics* — DOI `10.1016/0304-405X(95)00826-Z` | §26 buyback quality |
| Frankel & Litov (2009), "Earnings persistence", *Journal of Accounting and Economics* — DOI `10.1016/j.jacceco.2008.11.008` | §27 earnings persistence |
| Murphy (1973), "A New Vector Partition of the Probability Score", *Journal of Applied Meteorology* — DOI `10.1175/1520-0450(1973)012<0595:ANVPOT>2.0.CO;2` | §29 model confidence; `strategies/calibration.py::calibrated_confidence:171` |
| Guo, Pleiss, Sun & Weinberger (2017), "On Calibration of Modern Neural Networks", arXiv:1706.04599 | §29 — why a stated confidence may not be used as a multiplier uncorrected |
| Wang & Strong (1996), "Beyond Accuracy: What Data Quality Means to Data Consumers", *Journal of Management Information Systems* — DOI `10.1080/07421222.1996.11518099` | §30 data quality; `strategies/data_quality.py::aggregate_quality:46` |
| Kuncheva & Whitaker (2003), "Measures of Diversity in Classifier Ensembles and Their Relationship with the Ensemble Accuracy", *Machine Learning* — DOI `10.1023/A:1022859003006` | §31 agreement vs dispersion |
| Clemen (1989), "Combining forecasts: A review and annotated bibliography", *International Journal of Forecasting* — DOI `10.1016/0169-2070(89)90012-5` | §29/§31 — the consensus/dispersion pair |
| Triantaphyllou (2000), *Multi-criteria Decision Making Methods: A Comparative Study*, Springer — DOI `10.1007/978-1-4757-3157-6` | §32 — the multiplicative (noncompensatory) aggregation shape, with ledger rows 29 and 31 |

**One fetch failed and is reported as such:** Sloan (1996) resolves only through
JSTOR, which served a bot-challenge page; its title/author/year/journal are from
search metadata and **no DOI or page numbers are asserted here**. The paper is
already row 7 of the master's ledger, so nothing depends on this pass.

---

## Appendix B — internal citations used

Every symbol below was read this round. The survey's own line numbers refer to
`Strategies/other_score.md`.

| Claim | Symbol |
| --- | --- |
| the survey's framing and its warning against 30-40 scores | `Strategies/other_score.md:1-3`, `:1147-1151` |
| the hierarchy, counted | `Strategies/other_score.md:1145-1186` (core 1-9, secondary 10-20, meta 21-24) |
| Piotroski / Altman / Beneish | `dataflows/quantitative_scores.py::piotroski_f_score:202`, `::piotroski_f_score_detailed:590`, `::altman_z_score:181`, `::altman_variant:409`, `::beneish_m_score:113` |
| the other composite scorers the survey never names | `strategies/normalized.py::ohlson_o_score:157`, `::zmijewski_score:217`, `dataflows/quantitative_scores.py::growth_score:842`, `::overpriced_score:934` |
| the ten factor/style categories | `strategies/factor_schema.py:40`, `::SUBSCORE_FACTORS:399` |
| momentum, quality, liquidity producers | `strategies/momentum.py::momentum_12_1:358`, `strategies/factors.py::momentum:24`, `::category_scores:258`, `::quality_band:224`, `strategies/liquidity_risk.py::amihud_illiquidity:71` |
| the FQS/FGS/VS/FRS sub-score family | `strategies/fundamental_score.py::quality_subscore:210`, `::growth_subscore:206`, `::valuation_subscore:211`, `::risk_subscore:221`, `::fundamental_score:243` |
| earnings revision and surprise | `strategies/analyst_revisions.py::revision_ratio:79`, `::estimate_change_index:176`, `::revision_index:289`, `strategies/events.py::surprise_score:17`, `strategies/catalyst.py::last_earnings_surprise:77` |
| consensus and its leaves | `strategies/consensus.py::weighted_consensus:32`, `::rating_to_number:8`, `::agreement_score:14`, `agents/utils/analysis_tools.py::get_consensus:2607` |
| sentiment producers | `strategies/sentiment_score.py::sentiment_score:467`, `strategies/sentiment.py::aggregate_weighted_sentiment:1450`, `::daily_sentiment_sma:511`, `::compute_social_scores:273`, `::mention_volume:43`, `::sentiment_dispersion:209` |
| news and event producers | `strategies/news_score.py::news_novelty:331`, `strategies/event_state.py::imminence:349`, `strategies/catalyst.py::implied_move_from_history:138`, `::build_catalyst_snapshot:219` |
| technical, regime, breadth, relative strength | `strategies/technical_score.py::technical_score:324`, `strategies/regime.py::hmm_filtered_regime:545`, `::vol_percentile:59`, `::trend_strength:130`, `strategies/regime_state.py::regime_relative:127`, `::regime_trend:65`, `strategies/market_breadth.py::market_breadth:114`, `agents/utils/analysis_tools.py::_market_breadth_read:375`, `strategies/sector_breadth.py::mcclellan_read:213`, `strategies/relative_strength.py::relative_strength_report:214` |
| options, flow, insider | `strategies/options_surface.py::iv_percentile:15`, `::put_call_oi_concentration:34`, `::iv_skew:25`, `strategies/derivatives_gamma.py::gex_per_strike:52`, `strategies/orderflow.py::institutional_net:45`, `dataflows/finra.py::get_dark_pool_flow:109`, `dataflows/massive.py::get_form4_insider_massive:625` |
| ownership, capital allocation, moat | `agents/utils/moomoo_extra_tools.py::get_institution_holdings:236`, `strategies/liquidity_risk.py::ownership_hhi:130`, `strategies/capex_quality.py::capex_quality_read:126`, `strategies/value_dip.py::decline_driver_check:952`, `dataflows/patentsview.py::get_patent_activity:57` |
| valuation legs | `strategies/peer_universe.py::sector_medians_for:430`, `strategies/value_dip.py::valuation_z_read:122`, `strategies/normalized.py::margin_of_safety:120`, `strategies/reverse_dcf.py::reverse_dcf:90` |
| the tail systems | `dataflows/statement_parsing.py::enrich_screen_ratios:1101`, `agents/utils/market_position_tools.py::get_share_buyback_authorization:49`, `strategies/earnings_quality.py::earnings_quality_verdict:24`, `::dechow_dichev_aq:118`, `strategies/tail_risk.py::_uncertainty:103`, `strategies/conformal.py::quantile_band:118`, `strategies/calibration.py::calibrated_confidence:171`, `strategies/data_quality.py::aggregate_quality:46`, `strategies/score_disagreement.py::risk_disagreement:128`, `strategies/regime_score.py::regime_paths:765` |
| the composite and its own document | `strategies/trade_score.py::trade_score:293`, `::ENGINE_WEIGHTS:100`, `::RESEARCH_ALLOCATION:112` |

---

## Related documents

* [`README.md`](README.md) — the master: §1.1 (the survey block, corrected), §1.2
  (direction convention, 100 = favourable), §1.4 (the composite, the four-outputs
  rule), §2.1 (the binding invariants), Appendix C.1/C.2 (the evidence ledgers).
* [`ValuationScore.md`](ValuationScore.md) §0.2/§7 — the §21 boundary.
* [`MarketScore.md`](MarketScore.md) §1 — the momentum/relative-strength boundary.
* [`CompositeTradeScore.md`](CompositeTradeScore.md) §3.10 — the `Conviction`
  product form and its inverted risk term.
* [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §7 (WP-10) and §9 Phase C —
  where any measurement these systems need would run.
