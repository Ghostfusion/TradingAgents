# Scoring, Sentiment-Aggregation & Composite-Score Research, Round 3

Status: **research only (2026-09-13), no code changed.** Round 3 of
[`design_quant_formulas_research.md`](design_quant_formulas_research.md)
(round 1, 2026-09-05) and
[`design_quant_formulas_research_round2.md`](design_quant_formulas_research_round2.md)
(round 2, 2026-09-11, landed via
[`implementation_plan_quant_formula_additions.md`](implementation_plan_quant_formula_additions.md)).
Rounds 1-2 swept **return-prediction and risk formulas**; this round sweeps
**score construction itself** — fundamental/quality score models, sentiment and
crowd scores, news-NLP aggregation, and the normalisation/composite/validation
machinery that turns a metric into a score.

**Added 2026-09-13 (second pass): one orchestration item, S11 — symmetric
evidence for paired roles.** §2 now also carries the staged gathering pattern for
the debate's *inputs*: a plan call, then code-fired deterministic fetches, then
the unchanged reduce. It sits in a *scoring* round on purpose — the judge's L2
dimension scores (`agents/arbiters/debate_judge.py::aggregate_scores`), the
`strategies/debate_score.py` rows and the calibration buckets are *measurements
of two sides*, and a measurement taken over asymmetric evidence is not
comparable. The discipline this round demands of scores (stated basis, stated
coverage, `unavailable` instead of a guess) is demanded there of *evidence*.

Companion: [`docs/implementation_plan_quant_formula_additions_round3.md`](implementation_plan_quant_formula_additions_round3.md)
(the phased plan for the adopted list; designed, not started).

---

## 0. Method

### 0.1 Source set

25 distinct URLs from the brief (33 list entries — the second batch repeated
8 market/crowd URLs from the first), plus 5 orchestration / judge-bias sources
added in the second pass for **S11** (ledger rows 26-30). All retrieved except two, both handled explicitly:

- `researchgate.net/publication/371311096` → **HTTP 403**; the identical paper
  was recovered from its arXiv primary (`arXiv:2306.02136v3`).
- `zenodo.org/records/17510736` → host unreachable (direct, `/api/records`,
  DOI resolver and Wayback all timed out); content retrieved from the same
  author's primary artifacts for that DOI (HF model card, GitHub repo,
  author-hosted model-report PDF). Marked below where it matters.

Per-source extraction (status, exact formulae, aggregation windows,
normalisation, validation evidence, engine fit) is recorded in §5, and the raw
per-source notes are kept verbatim in
[`docs/research/scoring_round3/`](research/scoring_round3/) (8 files, one per
research batch).

### 0.2 Inventory of the scoring surfaces already in the repo

Verified at the definition site before any candidate was listed, per the
round-2 exclusion rule:

| Surface | Where |
| --- | --- |
| Altman Z (original, 5 ratios), Beneish M, Piotroski F, EV, earnings yield, Acquirer's multiple, Novy-Marx GP/A, Hirshleifer NOA | `dataflows/quantitative_scores.py` |
| Consumed as **informational rows only** — "no score, ranking or filter reads them" | `dataflows/statement_parsing.py` (quality-rows block) |
| Ohlson O, Zmijewski X, Sloan accruals ratio, 5y median-margin normalized EBIT, PE percentile, `trap_verdict`, margin of safety (both denominator conventions) | `strategies/normalized.py` |
| Quality composite [0,1] from ROE+margin; `quant_signal`, `baseline_rating` | `strategies/quant_baseline.py` |
| CapEx-quality score 0-100 + penalty points + regime | `strategies/capex_quality.py` |
| Cross-sectional composite: `percentile_rank`, `composite_score` (rank/weight), `z_composite_alpha` (weighted z), `value_momentum_score` | `strategies/factors.py` |
| **Percentile 0-100 multifactor scoring with renormalised weights + tie-aware percentile + factor weights** | `strategies/sector_rank.py::rank_sectors_multifactor`, `_pct_rank`, `FACTOR_WEIGHTS` |
| `winsorize`, `cross_sectional_z`, `industry_neutral_z`, `centered_rank`, `quantile_split`, `no_trade_band` | `strategies/cross_section.py` |
| Canonical 0-100 score ↔ 5-tier rating bands + agreement check | `strategies/decision_guardrail.py::SCORE_BANDS`, `score_band_for`, `validate_score_action_agreement` |
| Rating agreement/consensus, numeric stance, distribution + compression check, per-rating win rate | `strategies/consensus.py`, `strategies/alpha_health.py` |
| Per-agent calibration scorecard | `strategies/calibration.py::scorecard` |
| Sentiment: velocity, mention-volume ratio, `decayed_weight` (half-life 7d), `weighted_sentiment` (recency × credibility), `surprise_velocity` (z vs baseline), `score_from_counts` (net share), `blended_score`, `aggregate_daily_sentiment` (per-day **unweighted** mean + `relevance_mean`), `daily_sentiment_sma` (7d SMA + innovation, calendar-reindexed, close-time cutoff) | `strategies/sentiment.py` |
| Sentiment research: lead/lag, Newey-West multi-horizon regression, sector-neutral z, residualisation on log-mcap + sector, rolling IC, IC term structure, quintile long/short, factor scale | `strategies/sentiment_research.py` |
| Loughran-McDonald tone + readability | `strategies/text_factors.py::lm_tone` (Q6) |
| Deterministic news relevance 0-100 + admission + official-source boost | `strategies/news_relevance.py::score_news_article`, `OFFICIAL_HOSTS` |
| Analyst ratings/price targets (yfinance, Finnhub trends + PT, moomoo consensus); **upgrade/downgrade counts** `{up, down, net}` | `dataflows/y_finance.py`, `finnhub.py`, `moomoo.py`, `yfinance_sector.py::fetch_revision_actions` |
| Security-type routing (operating company / ETF / CEF / …) | `strategies/security_type.py` |
| Sentiment-into-overlay fold behind an IC gate | `strategies/overlays.py::fold_sentiment_into_overlay`, `graph/trading_graph.py::_sentiment_factor_read` |
| **Debate evidence**: bull/bear are prompt-only over the four analyst reports — neither side has a tool bound | `agents/researchers/bull_researcher.py`, `bear_researcher.py` (`llm.invoke`, no `bind_tools`); `graph/setup.py` registers them as plain nodes (only the analysts get a `ToolNode`) |
| **Analyst evidence split**: *forced* (code-fired, args derived from run context) vs *model pool* (args only the model can supply) | `agents/utils/evidence_gather.py::classify_tool_pools`, `gather_for_analyst_node`, `_ShortCircuitToolNode`; design in `docs/design_mapreduce_forced_tool_gathering.md` |
| **Order/anchoring countermeasures already shipped** | pre-debate `researcher_independent_stances` (`enable_independent_vote`), anonymised + seeded order rotation (`agents/arbiters/debate_judge.py`), `strategies/debate_claim.py`, `strategies/debate_score.py` |

**Two facts drive this whole round.** (1) The repo computes many *point*
scores but no consumer ranks or filters on them — the statement layer says so
in a comment. (2) `aggregate_daily_sentiment` computes the FinBERT paper's
per-day mean and stores `relevance_mean`, but **no code uses relevance as a
weight**: `relevance_mean` is rendered, never multiplied.

### 0.3 Exclusion rule and the honesty rules for this round

Same entry rule as round 2 — a candidate is adopted only if it is **absent at
the definition site** *and* has a **named consumer** in this repo. Three
additional rules apply to scores specifically:

1. **A score whose inputs the engine cannot obtain is excluded, not planned.**
   (The Composite Financial Index's four ratios; MSCI's estimate-level
   changes; Baker-Wurgler's IPO- and issuance-based proxies.)
2. **No weight vector is invented.** Either the source publishes weights
   (MSCI `{3,2,1}` / `{9,7,5,3}`, fffinstill pillar weights, the sector-rotation
   doc's 8-factor weights) or the item uses **equal weights with the
   renormalise-over-present-factors rule the repo already implements**
   (`rank_sectors_multifactor`), and says so in its output.
3. **A score is not a rating.** Nothing added here may feed
   `decision_guardrail.SCORE_BANDS` (the *decision* score ↔ rating contract);
   quality/sentiment composites carry their own published band tables.

---

## 1. Ledger — where the round-3 sources land on what already exists

| Round-3 source topic | Status | Landed as / evidence | Residual gap this round adopts |
| --- | --- | --- | --- |
| Piotroski nine criteria | **present** | `quantitative_scores.piotroski_f_score` — all nine tests, YoY deltas via `_prv`, sum 0-9 | the paper's *basis* (beginning-of-year assets, LTD+current portion / **average** assets, accrual test in ratio form), the **band** interpretation, and an applicability gate → **S2** |
| Altman Z (public manufacturer) | **present** | `quantitative_scores.altman_z_score` = `1.2X1+1.4X2+3.3X3+0.6X4+1.0X5`, X4 = `market_cap/total_liabilities` | the **Z'/Z''/Z''-EM variants** and **any zone band** (the only "distress" labels in the repo are `capex_quality`'s investment regime and the ETF decline-driver hierarchy — no Altman zone is computed) → **S1** |
| Beneish M | **present** (both published cuts: `M_SUSPECT=-1.78`, `M_CLEAN=-2.22`) | `beneish_m_score` | applicability (manufacturing-only per the source) noted in S2's guard; the CFA-UK `-1.89` variant is **not** adopted (the two published cuts already exist) |
| Ohlson O / Zmijewski | **present** | `normalized.ohlson_o_score`, `zmijewski_score`, rendered in the value-dip row | none |
| Composite / point systems | **partially present** | `factors.composite_score` (rank-based 0-1), `z_composite_alpha`, `rank_sectors_multifactor` (percentile 0-100 + renormalised weights), `quant_baseline.quality_score`, `capex_quality` | **no fundamental/quality composite with a stated metric set, coverage floor and published bands** → **S3** |
| FinBERT per-day mean of probabilities | **partially present** | `sentiment.aggregate_daily_sentiment` = per-day unweighted mean; close-time look-ahead guard already implemented | the engine has no classifier, so the paper's `P(pos)−P(neg)` is not computable; what is missing is the **weighted generalisation** with the confidence caveat stated → **S4** |
| Confidence-weighted aggregation (Berkeley) | **partially present** | `sentiment.weighted_sentiment` weights *social messages* by recency × caller-supplied credibility | no per-article signed polarity × confidence path for **news**, and no dispersion/neutral accounting → **S4/S5** |
| Rolling-window aggregation (QuantConnect 10-day, exponential) | **partially present** | `daily_sentiment_sma` (7d SMA, unweighted, calendar-reindexed) | exponential **recency weighting inside the window** + an explicit warm-up/min-history guard → **S7** |
| Bull/bear ratio + contrarian bands | **partially present** | `score_from_counts` = net share `(B−BE)/(B+BE)` | the **ratio** form `B/(B+BE)` with its 40/60 bands, and per-item dispersion → **S5** |
| MarketGrader sentiment score | **partially present** | 3 of its 4 legs already exist (MACD via `get_indicators`, 50/100/200-day returns + RSI/relative-strength reads) | its **weights are undisclosed** and its 4th leg needs consensus-EPS history → excluded as a model, bands cited as prior art in S5 |
| MSCI analyst sentiment index | **absent** | — (only raw `{up, down, net}` counts and consensus levels exist) | the **weighted revision ratio**, coverage rule and winsorised z → **S6** |
| Baker-Wurgler sentiment index | **absent** | no sentiment-index construction exists (the library's only eigen-decomposition is the correlation-matrix square root in `strategies/book_risk.py::copula_scenarios`) | a **reduced-proxy** BW-style index, with the five unavailable proxies named → **S9** |
| Score-based portfolio evidence (Nature review) | **absent as an evaluation row** | `alpha_health`/`evaluate` cover ratings, DSR/PBO/CPCV — not *score* deciles | **score IC/decile/coverage/stability rows** for any new composite → **S8** |
| G-Score / C-Score (Mohanram / Montier) | **absent** | — | **S10** |
| fffinstill / CFI / AlphaSense / SMA / Adanos / FMP / Lycore / Zenodo / MarketGrader | design templates | nothing landed | patterns only; the quantitative parts are excluded in §3 with the reason |
| Evidence symmetry across the debate's paired roles | **partially present** | the debate reads ONE shared set of four analyst reports (both sides byte-identical), the forced gather is deterministic in composition, and the judge is anonymised + order-rotated | the **model-pool remainder** is neither measured nor mirrored (**33 model-discretionary tools** on the audited QQQI run), and no symmetry row/assertion exists → **S11** |
| Staged orchestration (plan → code-fired fetch → reduce) | **present for the analysts** | `docs/design_mapreduce_forced_tool_gathering.md` §2-§3 + `evidence_gather.gather_evidence` | the plan call that turns model-pool args into code-fired fetches, and a mirrored discretionary budget → **S11** |

---

## 2. Adopted list — absent, grounded, buildable

Each item: formula → provenance → why it fits *this* engine → consumer → data →
failure mode.

### S1 — Altman variant family and distress zones

$$Z = 1.2X_1+1.4X_2+3.3X_3+0.6X_4+1.0X_5,\qquad X_4=\frac{\text{MV equity}}{\text{book TL}}$$
$$Z' = 0.717X_1+0.847X_2+3.107X_3+0.420X_4+0.998X_5,\quad X_4=\frac{\text{BOOK equity}}{\text{TL}}$$
$$Z'' = 6.56X_1+3.26X_2+6.72X_3+1.05X_4 \ \ (\text{no } X_5),\qquad
Z''_{\text{EM}} = 3.25 + Z''$$

with $X_1=$ working capital/TA, $X_2=$ retained earnings/TA,
$X_3=$ EBIT/TA, $X_5=$ sales/TA.

| Variant | Safe | Grey | Distress |
| --- | --- | --- | --- |
| $Z$ (public manufacturers) | $>3.0$ | $1.8$–$3.0$ | $<1.8$ |
| $Z'$ (private) | $>2.90$ | $1.23$–$2.90$ | $<1.23$ |
| $Z''$ (non-manufacturers, emerging) | $>2.60$ | $1.10$–$2.60$ | $<1.10$ |

- **Provenance:** visbanking publishes the **original Z and its 3.0/1.8 zones
  only** — the variants are *not* on that page
  ([src](https://visbanking.com/financial-ratio-analysis-examples)); they are
  recovered from the Altman literature and corroborated at
  [Wikipedia Altman Z-score](https://en.wikipedia.org/wiki/Altman_Z-score)
  and the Nature review's Table 9
  ([src](https://www.nature.com/articles/s41599-024-03888-4)), which states
  `Z(M) ≥3 sound / ≤1.8 high risk` and `Z(NM) ≥2.6 sound / ≤1.1 high risk`
  — i.e. the two variants are the *documented* form for non-manufacturers.
  Validation: original estimation sample 66 firms (33 bankrupt, all
  manufacturers); 72% two-year accuracy (1968) rising to ~80-90% one-year in
  the 31-year re-tests; **explicitly not recommended for financial companies**.
  A European application (Graham Secker) reports the red zone $Z<1$
  underperforming the market by 5-6% p.a. over 1990-2008 (CFA UK summary,
  [src](https://www.cfauk.org/pi-listing/man-machine-the-evolution-of-fundamental-scoring-models-and-ml-implications)).
- **Fit:** the repo computes the *public-manufacturer* discriminant for every
  name it can, including services, HK/EM listings and (until the security-type
  gate) funds. Applying $Z$ to a non-manufacturer is the documented misuse
  $Z''$ exists to fix, and no zone band exists in the repo at all, so a raw
  number like `2.4` is currently unlabelled.
- **Consumer:** `dataflows/quantitative_scores.py` (`altman_z_score` keeps its
  exact current output; add `altman_variant(fin, variant)` +
  `altman_zone(z, variant)`), the `trap_verdict` row in
  `strategies/normalized.py`, the screener column, and a fundamentals tool row.
- **Data:** statements the engine already pulls; $X_4$ needs market cap
  (original) or book equity (variants) — the engine's canonical carries
  `market_cap` and total equity; if only total equity is present the output
  records that the book-equity X4 uses total equity as a stated proxy.
- **Failure mode:** funds and financials → `unavailable` (the model's own
  limitation), *not* a silently computed number; a missing prior period for
  $Z$ still returns the original variant; the chosen variant and the reason are
  always printed so two variants can never be compared as if identical.

### S2 — Piotroski: the paper's basis, the bands, and an applicability gate

The nine signals are already implemented; what is missing is the **basis** and
the **interpretation**:

1. $F_{ROA}=1$ if $ROA_t>0$, $ROA=\dfrac{NI_t}{\text{TA}_{t-1}$
   (beginning-of-year)}}$;
2. $F_{CFO}=1$ if $CFO_t>0$ (same denominator);
3. $F_{\Delta ROA}=1$ if $ROA_t>ROA_{t-1}$;
4. $F_{ACCRUAL}=1$ if $CFO>ROA$ (i.e. accruals $<0$);
5. $F_{\Delta LEVER}=1$ if $\Delta\!\left(\dfrac{\text{LTD incl. current portion}}{\text{average TA}}\right)<0$;
6. $F_{\Delta LIQUID}=1$ if $\Delta(\text{current ratio})>0$;
7. $F_{EQ}=1$ if the firm issued no common equity;
8. $F_{\Delta MARGIN}=1$ if $\Delta(\text{gross margin})>0$;
9. $F_{\Delta TURN}=1$ if $\Delta(\text{asset turnover})>0$;
   $F=\sum F_i\in[0,9]$.

- **Provenance:** Piotroski (2000), UChicago GSB Selected Paper No. 84
  ([src](https://www.anderson.ucla.edu/documents/areas/prg/asam/2019/F-Score.pdf)):
  high-BM quintile, 14,043 firm-years, 1976-1996; high−low one-year
  market-adjusted return **0.230** (high 0.134 vs low −0.096, $t=5.59$),
  two-year 0.432, long/short ≈23%/yr, **+2-3% per extra signal** with size/BM/
  momentum/accruals controls. Bands: **low $=0$ or $1$, high $=8$ or $9$**
  ([Wikipedia](https://en.wikipedia.org/wiki/Piotroski_F-score) states the
  wider 0-2/8-9 convention; the Nature review's Table 9 uses 0-3 poor /
  7-9 good). Failure modes stated by the paper: benefits concentrated in
  **small/medium** firms (large-cap spread insignificant, $p=0.20$), no edge
  **with analyst coverage** (0.114, $t=1.83$), high price/volume partitions
  lose the *high* leg, ad-hoc feature selection and acknowledged
  data-snooping. External: sector dependence (Wikipedia), and Schwartz &
  Hanauer (2024) find the return is largely **style-factor exposure** rather
  than unique alpha (CFA UK summary).
- **Fit:** the current implementation feeds vendor-computed ratio fields
  (`roa`, `leverage`, `current_ratio`, `gross_margin`, `asset_turnover`),
  which are ending/average-asset based, and returns a bare 0-9 — no band, and
  no statement that a large-cap, heavily covered name carries a documented
  weaker signal. Both are cheap to fix *without* touching the existing
  function's output.
- **Consumer:** `quantitative_scores.piotroski_f_score_detailed(fin)` (new —
  per-signal booleans + `basis` + `deviations`, while `piotroski_f_score`
  stays byte-identical for existing callers), `trap_verdict`, screener column,
  fundamentals tool row.
- **Data:** two consecutive balance sheets/income statements (`_prv` chain);
  `income before extraordinary items` is usually absent in vendor feeds →
  recorded as a deviation (net income used, basis printed), never silently.
- **Failure mode:** funds/financials → `unavailable` with the reason; a
  missing prior period returns the summary score with the band withheld rather
  than guessing; the detailed basis must never be mixed with the old field
  basis in one comparison.

### S3 — Composite quality score (0-100, equal-weight winsorised z, percentile-mapped)

$$z_{i,m}=\operatorname{sign}_m\cdot\frac{\tilde x_{i,m}-\bar x_m}{\sigma_m},
\qquad \tilde x = \text{winsorise}(x;\,0.01,0.99)$$
$$Z_i=\frac{\sum_{m\in M_i} z_{i,m}}{|M_i|},\qquad \text{require } |M_i|\ge k
\ \text{of } |M|$$
$$\text{QualityScore}_i = 100\cdot\widehat{\text{RankPct}}(Z_i)$$

with $M$ = the metric set the engine already computes (F, M, Z, O, GP/A, NOA,
Sloan accruals, CapEx quality), $\operatorname{sign}_m$ flipped for
lower-is-better metrics (M, accruals, leverage), and $\widehat{\text{RankPct}}$
the tie-aware cross-sectional percentile the repo already has.

- **Provenance:** the Nature review lists the recurring constituent metrics
  (total assets, current ratio, sales, earnings, leverage, working capital,
  accruals, cash flows, margins) and states that **no standardisation and no
  weight vector is published anywhere in the literature it surveys** — scores
  are raw binary sums or ratio formulas
  ([src](https://www.nature.com/articles/s41599-024-03888-4)). fffinstill
  publishes the missing machinery but for a *sector-percentile* composite:
  `Category = Σ(percentile × weight) ÷ Σ(weights)` with **missing metrics
  excluded and the remaining weights renormalised to 100%**, then pillar
  weights, six lens weight sets, and a band table
  (70-100 elite, 60-69 above average, 50-59 sector median, 40-49 below,
  20-39 poor, <20 distressed)
  ([src](https://fffinstill.com/research/methodology)). The repo's own
  `rank_sectors_multifactor` already implements the same renormalisation over
  present factors at percentile 0-100.
- **Fit:** the engine holds ~10 independent quality/distress point scores and
  **no consumer ranks on any of them**. A single composite is what makes them
  usable by the screener and by the analyst surface, and it is exactly the
  shape `sector_rank` proved out — extended from ETFs to names.
- **Consumer:** `strategies/factors.py` (owns cross-sectional composites) —
  `quality_composite(scores_by_ticker, *, directions, min_coverage)`, reusing
  `percentile_rank` and `cross_section.winsorize`; screener column;
  `get_composite_rank` tool extension for the fundamentals analyst.
- **Data:** the sub-scores above plus a **peer universe** — resolved: the
  screener's scan universe (`--universe`, default `eodhd-us`, with
  `--rank composite`), through **one resolver that lands with S10** and is then
  reused here (§1.1 of the implementation plan). `get_company_peers` (today
  `[ticker] + peers[:8]`, nine names at most) keeps its meaning as the narrow
  tool-level comparison set; it is not the composite's universe.
- **Failure mode:** peer sets smaller than the stated floor (default 8) →
  `unavailable` (a z over three names is noise); a metric present for fewer
  than `min_coverage` names is dropped with the drop printed; the composite is
  **not** a rating — its bands are the quality bands above, and it must never
  be passed to `decision_guardrail.SCORE_BANDS`; sector-neutral
  (`industry_neutral_z`) vs raw-$z$ is a stated switch, not a silent default.

### S4 — News aggregation: the published mean, and a labelled weighted generalisation

$$S_t^{\text{published}} = \frac{1}{N_t}\sum_{n=1}^{N_t}\left[P_n(\text{pos})-P_n(\text{neg})\right]
\qquad\text{(FinBERT paper)}$$
$$S_t^{\text{weighted}} = \frac{\sum_n w_n\,s_n}{\sum_n w_n},\qquad
w_n = \frac{\text{relevance}_n}{100}\cdot 2^{-\text{age}_n/HL}\cdot b_{\text{official}}$$

where $s_n\in[-1,1]$ is the vendor/news polarity, $HL$ a stated half-life, and
$b$ an optional official-source boost — **explicitly a defined generalisation,
not the published formula**, because the paper's inputs are per-article softmax
class probabilities and the engine has none.

- **Provenance:** the per-day mean is exact from
  [arXiv:2306.02136v3](https://arxiv.org/html/2306.02136v3)
  (`SentimentScore_t = (1/N_t)Σ[P_n(pos) − P_n(neg)]`, titles only, non-trading
  day news aligned to the next trading day, 1,056,471 headlines, MSE-only
  evaluation: FinBERT+LSTM val MSE 3.20e-4 vs sentiment-free LSTM 1.19e-3).
  The confidence-weighted sibling is Berkeley's deployed
  `WeightedSentimentScore = Σ_i s_i·conf_i`, $s_i\in\{+1,-1\}$, neutral 0,
  $conf_i$ = FinBERT confidence
  ([project](https://www.ischool.berkeley.edu/projects/2024/sentiment-analysis-financial-markets),
  [slides](https://www.ischool.berkeley.edu/sites/default/files/sentiment-analysis-for-financial-markets.pdf))
  — note they **tried and rejected** mode-of-labels, per-label average
  confidence, and a temporal-decay term, which is why decay is optional here
  and defaults off. The exponential recency weight and the 10-day window are
  the production contract in
  [QuantConnect's FinBERT recipe](https://www.quantconnect.com/docs/v2/writing-algorithms/machine-learning/hugging-face/popular-models/finbert)
  (`w = e^{linspace(0,1,n)}` normalised, monthly rebalance with a 14-day
  minimum gap, 30-day warm-up). AlphaSense's document score is the same
  family: `(#positive − #negative) / total statements`, confidence-weighted,
  then cross-sectionally normalised to zero mean
  ([src](https://www.alpha-sense.com/blog/engineering/sentiment-score/)).
  The honest caveat is documented too: FinBERT probabilities are **not
  calibrated** and calibration is proposed as future work
  ([src](https://www.emergentmind.com/topics/sentiment-analysis-using-finbert))
  — so no threshold trade may be justified by these scores.
- **Fit:** `aggregate_daily_sentiment` already buckets by ticker/day with the
  close-time look-ahead guard and the next-session alignment, and already
  collects `relevance_mean`; the missing piece is using it as a weight, plus
  the unweighted companion, $n$, neutral share, dispersion and basis line that
  make the two comparable. The vendor feed is already signed (AV
  `ticker_sentiment_score`, EODHD `normalized`, GDELT tone).
- **Consumer:** `strategies/sentiment.py` —
  `aggregate_weighted_sentiment(...)` next to `aggregate_daily_sentiment`
  (whose output stays byte-identical), surfaced through
  `get_news_sentiment_series` / `get_sentiment_computed`,
  `domain_bundles.get_sentiment_flow_feed`, and the news analyst's citation
  rule.
- **Data:** signed per-article polarity ✓ (vendor feeds), publication
  timestamps ✓, article counts ✓, relevance 0-100 ✓. **Per-article model
  confidence does not exist** — relevance is an unsigned heuristic, so the
  weighting is a proxy and the output says so.
- **Failure mode:** syndicated duplicates inflate $N_t$ → dedupe by headline
  before scoring (the paper dedupes on unique titles); a high-relevance day
  with $N_t=1$ must print $n$ and refuse to be read as a consensus; all-neutral
  news must be distinguishable from no news (neutral share + `n` rendered);
  the weighted and unweighted numbers must always ship together, because a
  silent switch between them would change every downstream fold.

### S5 — Crowd ratio, dispersion, and display-only extreme bands

$$\text{BullBearRatio} = \frac{B}{B+BE}\times 100\ \ (\text{neutrals excluded}),\qquad
\text{NetShare} = \frac{B-BE}{B+BE}\ \ (\text{already implemented})$$
$$\text{Dispersion} = \sqrt{\frac{\sum_i w_i (s_i-\bar s_w)^2}{\sum_i w_i}},\qquad
\text{Agreement} = \max_b \frac{\sum_{i\in b} w_i}{\sum_i w_i}$$

- **Provenance:** the ratio form, its neutrals-excluded denominator and the
  crowded-bullish $>60$ / crowded-bearish $<40$ bands are defined with a worked
  example (45 bull, 30 bear, 25 neutral → 60%) in
  [TradingSim's bull/bear guide](https://www.tradingsim.com/blog/bull-bear-ratio),
  which also states the two limitations that govern its use here: it is a
  **weekly survey** (the engine has none — it has StockTwits/Reddit counts) and
  **herds stay wrong for months**, so extremes persist. Dispersion/agreement as
  a *confidence* modifier follows the Fidelity/SMA "volume + intensity +
  statistical significance" framing
  ([src](https://www.fidelity.com/webcontent/ap110398-researchsnapshot-content/16.13/help/Learn_More_About_Social_Sentiment.pdf))
  and the Adanos finding that buzz predicts **volatility, not direction**
  (`Buzz↔|return|` r=0.16, `sentiment↔return` r=0.08, next-day vol r=0.09,
  sentiment sign r=−0.00)
  ([whitepaper](https://adanos.org/x-stock-sentiment)).
- **Fit:** `compute_social_scores` already derives the net-share form from
  StockTwits counts and a surprise velocity, and `consensus_overlap` already
  measures modal agreement for *verdicts* — but the sentiment path has no
  ratio, no bands and no dispersion, so a loud-but-split name reads the same as
  a quiet consensus.
- **Consumer:** `strategies/sentiment.py` (additive rows on
  `compute_social_scores`, gated), the sentiment analyst's computed line, the
  `blended_score` input, and the web sentiment card.
- **Data:** the counts the engine already ingests; **no advisor survey** — so
  the output is labelled "crowd ratio (StockTwits/Reddit counts)", never
  "Investors Intelligence bull/bear", and no put/call or AAII cross-check is
  claimed.
- **Failure mode:** bands are **display-only** (no validation evidence exists
  in the source, and the source itself warns extremes persist for months);
  dispersion needs $n\ge$ a floor or renders `unavailable`; the ratio is
  undefined when $B+BE=0$ and must not fall back to 50.

### S6 — Analyst revision / estimate-change index (MSCI recipe, coverage-guarded)

$$\text{RR}(t)=\sum_{l=0}^{2} w_{-l}\,\frac{N^{\text{up}}_{t-21l}-N^{\text{down}}_{t-21l}}{N^{\text{total}}_{t-21l}},
\qquad \{w\}=\{3,2,1\}$$
$$\text{EC}(t)=\sum_{l=0}^{3} w_l\,\frac{E_{t-63l}-E_{t-63(l+1)}}{\left(|E_{t-63l}|+|E_{t-63(l+1)}|\right)/2},
\qquad \{w\}=\{9,7,5,3\}$$
$$\text{AS}_i=\operatorname{winsor\!-\!z}_{\pm3}\!\left(\text{avg of available descriptor groups}\right)$$

- **Provenance:** MSCI Analyst Sentiment Indexes methodology (April 2025,
  [src](https://www.msci.com/documents/10199/a925c038-cf5e-9701-fe7a-e4414a06b1ca)):
  the five descriptor groups (CPS, EPS, Sales, Recommendation, Price Target),
  the revision-ratio and estimate-change forms with the exact `{3,2,1}` /
  `{9,7,5,3}` weights, quarterly rebalancing with a 20% one-way turnover cap,
  and the **coverage rule**: only groups covered by more than one analyst
  count, missing groups average the available ones, at least one group
  required. **No performance/validation section exists in that document** —
  which is why this item may inform, never gate.
- **Fit:** the engine already has `fetch_revision_actions` (`{up, down, net}`)
  feeding the screener and `value_dip`'s re-rating catalyst row, plus
  consensus counts and price-target levels from three vendors. What is missing
  is the *weighted, winsorised, coverage-guarded* index form — today a single
  `net` count with no denominator, no recency weighting and no coverage check.
- **Consumer:** new `strategies/analyst_revisions.py`
  (`revision_ratio(...)`, `estimate_change_index(...)`, `winsor_z(..., 3.0)`),
  a fundamentals tool row, `value_dip`'s `revision_score` input, screener
  column.
- **Data:** revision **counts** ✓ (up/down; total = up+down, stated as a
  deviation from MSCI's analyst-coverage denominator). Estimate **levels** per
  quarter ✗ — the engine has current consensus and price targets, not a
  3-4-quarter estimate history, so the estimate-change leg renders
  `unavailable` with that reason until a longer history source exists.
- **Failure mode:** no per-analyst identity in `upgrades_downgrades` → one
  firm's five actions can dominate; require $\ge2$ distinct actions and print
  the count; a thin-coverage name returns `unavailable` (MSCI's own >1-analyst
  rule); never gate on it (no published evidence).

### S7 — Weighted rolling window with warm-up and decision-gap guards

$$S^{\text{roll}}_t=\frac{\sum_{k=0}^{K-1} \omega_k\, S_{t-k}}{\sum_k \omega_k},
\qquad \omega_k = e^{\,\text{linspace}(0,1,K)_k}\ \text{(most recent = 1)}$$

- **Provenance:** QuantConnect's production recipe above: previous **10 days**
  of news, per-article softmax, exponentially increasing weights
  `np.exp(np.linspace(0,1,n))` normalised, decision at month-start +1 with a
  **14-day minimum gap**, **30-day warm-up** before any trade, GPU node for the
  model.
- **Fit:** `daily_sentiment_sma` gives a 7-day *unweighted* SMA plus the
  innovation on a calendar-reindexed series — the correct base, missing only
  the exponential weights and the explicit "not enough history" guard the
  production contract requires.
- **Consumer:** `strategies/sentiment.py::weighted_rolling_sentiment(...)`
  (reuses the calendar reindexing and close-time cutoff), the sentiment tool
  output, the overlay fold.
- **Data:** the daily sentiment series already produced by
  `aggregate_daily_sentiment` / the EODHD/GDELT readers.
- **Failure mode:** the engine has no monthly cadence — the window and the
  minimum history are **exposed as parameters and printed**, never hard-coded
  to a schedule; the existing 7d SMA path stays byte-identical.

### S8 — Score evaluation rows (IC, deciles, coverage, stability)

$$\text{IC}_t=\rho_{\text{Spearman}}\!\left(\text{score}_{i,t},\ r_{i,t\to t+h}\right),\qquad
\text{Stability}_t=\rho_{\text{Spearman}}\!\left(\text{score}_{i,t},\ \text{score}_{i,t-1}\right)$$

plus decile mean forward returns with a monotonicity flag (Spearman of decile
index vs decile mean), and `coverage = scored names / universe`.

- **Provenance:** the F-Score paper's own high/low spread methodology
  (market-adjusted, prior-year sorts to avoid look-ahead) is the template;
  Lycore's production guidance is the validation discipline — walk-forward
  with strict temporal separation, forward returns at multiple horizons,
  **IC and rank IC rather than return attribution**, `p<0.05` **after
  multiple-testing correction**, and the warning that a 15% backtest Sharpe
  frequently goes to zero live
  ([src](https://www.lycore.com/blog/financial-news-sentiment-analysis/)).
  The Nature review is the counter-example that justifies this item: it
  reports **no factor-control tests** and never names look-ahead, restatements,
  sector concentration, data-snooping or publication bias (verified by full-text
  search) — a gap this repo must not inherit.
- **Fit:** `sentiment_research` already implements rolling IC, IC term
  structure and quintile long/short **for sentiment panels**; `alpha_health`
  has score distribution/compression and per-rating win rate; `evaluate` has
  DSR/PBO/CPCV. What is missing is the generic rows that make a *new* score
  (S3, S10, S6) honest.
- **Consumer:** `strategies/alpha_health.py` (new
  `score_evaluation_rows(scores_by_date, prices, holding, n_buckets)`) reusing
  the existing IC/quintile primitives; `scripts/strategy_quality_report.py`;
  the screener's quality report.
- **Data:** score snapshots + prices — the run store and the screener both
  hold them.
- **Failure mode:** minimum observations before a row is emitted; the rows are
  **never a standalone verdict** (DSR/PBO already exist for the multiple-testing
  side); a monotonicity claim requires all deciles populated.

### S9 — Reduced BW-style market sentiment index (**not scheduled**; kept as Appendix A in the plan)

Standardise each proxy, orthogonalise it against macro, take the first
principal component of the residual correlation matrix, then sign-normalise so
higher = sentiment. The published reference weights:

$$S_t = -0.241\,\text{CEFD}_t + 0.242\,\text{TURN}_{t-1} + 0.253\,\text{NIPO}_t
+ 0.257\,\text{RIPO}_{t-1} + 0.112\,S_t - 0.283\,\text{PD-ND}_{t-1}$$

and the orthogonalised variant (each proxy first regressed on industrial
production growth, consumption growth, employment growth and an NBER-recession
dummy):

$$S^{\perp}_t = -0.198\,\text{CEFD}^{\perp}_t + 0.225\,\text{TURN}^{\perp}_{t-1}
+ 0.234\,\text{NIPO}^{\perp}_t + 0.263\,\text{RIPO}^{\perp}_{t-1}
+ 0.211\,S^{\perp}_t - 0.243\,\text{PD-ND}^{\perp}_{t-1}$$

- **Provenance:** Baker & Wurgler (2006),
  [src](https://pages.stern.nyu.edu/~jwurgler/papers/wurgler_baker_cross_section.pdf):
  the six proxies with their transformations (TURN logged and detrended by its
  own 5-year average; CEFD, NIPO, S current; RIPO, PD−ND lagged one year), the
  two-stage PCA recipe (PC1 of the six proxies **and their lags** → keep each
  proxy's higher-correlation lead/lag → PC1 of the six selected, PC1 = 49% of
  variance, correlation with the 12-term stage 0.95), the annual frequency with
  a one-year effective lag, and the conditional evidence (the effect is
  strongest for young, small, high-volatility, unprofitable, non-dividend-paying
  and distressed names). Two corrections to the brief that came with this
  round: the paper defines **no pre-1964/post-1964 sub-index** (its long
  variant is a reduced 1935-2001 index of CEFD, S and lagged TURN), and every
  one of the six proxies is **market/macro-wide**, not per-ticker.
- **Fit:** the engine can build *some* of the construct's spirit from what it
  already fetches (a broad-basket turnover proxy from names it prices, the
  equity put/call ratio and a VIX/vol term-structure slope from the options
  chain, RRP/TGA liquidity and the macro orthogonalisation regressors from
  FRED, a capital-flow proxy from the flow tool) — which is exactly why the
  output must name the proxies it could **not** build (IPO count, IPO
  first-day returns, equity share in new issues, dividend premium, CEF
  discount).
- **Consumer:** new `strategies/market_sentiment_index.py` (only if a
  market-level consumer asks for it — the sentiment overlay today is
  per-ticker), gated default-off.
- **Data:** as above; **five of six published proxies are unavailable**, so the
  result is a *variant*, labelled as such, with its own loadings printed.
- **Failure mode:** annual frequency and a one-year lag make it useless for
  daily decisions — the output must state the frequency and the lag; fewer than
  a stated minimum of proxies → `unavailable` rather than a one-proxy "index";
  the PC1 sign is arbitrary until normalised, so the sign convention must be
  fixed and reported.

### S10 — G-Score and C-Score as siblings of the F-Score

$$G=\sum_{j=1}^{8}G_j\in[0,8]\qquad C=\sum_{j=1}^{6}C_j\in[0,6]$$

- $G_1=1$ if $ROA>$ industry median; $G_2=1$ if $CFO>$ industry median;
  $G_3=1$ if $CFO>$ net income;
  $G_4=1$ if $\operatorname{Var}(ROA)<$ industry median;
  $G_5=1$ if $\operatorname{Var}(\text{YoY sales growth})<$ industry median;
  $G_6=1$ if R&D intensity $>$ industry median;
  $G_7=1$ if CapEx intensity $>$ industry median;
  $G_8=1$ if advertising intensity $>$ industry median.
- $C_1=1$ if the NI-vs-cash-flow divergence **widened** vs last year;
  $C_2=1$ if receivable days rose; $C_3=1$ if inventory days rose;
  $C_4=1$ if other current assets rose; $C_5=1$ if depreciation ÷ gross fixed
  assets fell; $C_6=1$ if total assets grew $>10\%$.

- **Provenance:** the Nature review's Tables 6 and 7 (exact criterion lists)
  and Table 9 (bands: **G 6-8 good / 0-2 poor; C 0-2 good / 5-6 poor**)
  ([src](https://www.nature.com/articles/s41599-024-03888-4)). Performance
  context from the CFA UK survey: Mohanram's growth analog produced
  double-digit long/short excess return with significance after
  momentum/value/accruals/size controls, positive in **21 of 23 years**
  (hit ratio >91%), and Amor-Tapia & Tascon (2016) found that **only G and F
  survived out-of-sample testing** across four European markets
  ([src](https://www.cfauk.org/pi-listing/man-machine-the-evolution-of-fundamental-scoring-models-and-ml-implications));
  Montier's overpriced C-score is cited with a consistent >8% US return in the
  review.
- **Fit:** the F-Score is the **value** analogue, and this book is
  growth/semis-heavy (XLK, SOXX, IGV, AIQ, QQQI) — the growth score is the
  category the repo cannot currently assess at all, and the C-score is the
  missing *overpriced/fragile-accounting* risk read for names that pass the
  value screens. Both are binary sums with published bands, so they carry the
  same transparency the repo already values in F/M/Z.
- **Consumer:** `dataflows/quantitative_scores.py`
  (`growth_score(fin, medians)`, `overpriced_score(fin)`),
  `strategies/cross_section.py::group_median(values_by_key, groups)` for the
  industry medians, screener columns, a fundamentals tool row.
- **Data:** medians from the same resolved universe, partitioned by the
  existing `sector_map` labels (per-group floor 5) — `sector_map` is a
  ticker→sector label dict in this repo, not a constituent list, so the
  partition is what it can supply; R&D is in the statement chain,
  **advertising usually is not**
  (→ $G_8$ degrades to unavailable, printed); $G_4/G_5$ need a **5-year**
  annual series — available via the free SEC XBRL history tool the
  fundamentals analyst already has.
- **Failure mode:** industry medians need a peer floor (default 5) or the
  comparison is meaningless; $G_8$ and any missing median degrade to
  `unavailable`, never to 0; the C-score is a **risk screen, not a short
  signal**.

### S11 — Symmetric evidence for paired roles (orchestration; added for score comparability)

Three stages, grafted onto the machinery that already exists — the analyst stage
gains a *plan* call for the tools whose args only a model can supply, then code
fires it, then the analyst/debater reduces:

$$\text{plan} = \text{LLM}_{\text{cheap}}(\text{role}, \text{schemas}) \rightarrow \{(tool, \{arg: value\})\}$$
$$\text{leaves} = \text{code-execute}(\text{plan})\quad(\text{bounded parallel, per-call timeout, error leaves})$$
$$\text{report} = \text{LLM}(\text{evidence-block}(\text{leaves}))\quad(\text{shape unchanged})$$

and the contract the paired roles are held to:

$$\text{SYM}(A,B) \iff W_A = W_B \;\wedge\; K_A = K_B \;\wedge\; |D_A| = |D_B|$$

with $W$ the tool whitelist, $K$ the arg *keys* and $D$ the discretionary calls
used. Symmetry is of **access**, never of conclusion.

- **Provenance:** ReWOO plans with evidence placeholders and executes afterwards —
  "5x token efficiency and 4% accuracy improvement on HotpotQA", plus explicit
  robustness "under tool-failure scenarios"
  ([arXiv:2305.18323](https://arxiv.org/abs/2305.18323)); LLMCompiler splits a
  Function-Calling Planner / Task-Fetching Unit / Executor for parallel calls — up
  to 3.7x latency speedup, 6.7x cost saving and ~9% accuracy over ReAct
  ([arXiv:2312.04511](https://arxiv.org/abs/2312.04511), ICML 2024);
  plan-then-solve prompting is the prompt-level form of the same staging
  ([arXiv:2305.04091](https://arxiv.org/abs/2305.04091), ACL 2023). Anthropic's
  taxonomy names these **prompt chaining**, **parallelisation (sectioning)** and
  **orchestrator-workers**
  ([src](https://www.anthropic.com/engineering/building-effective-agents)).
  For the *other* half of the problem — order and anchoring — pairwise judges show
  position bias that "is not due to random chance", varies significantly across
  judges and tasks, is weakly influenced by prompt-component length but
  **strongly affected by the quality gap** between the compared solutions
  (15 judges, 22 tasks, >150,000 instances;
  [arXiv:2406.07791](https://arxiv.org/abs/2406.07791), AACL-IJCNLP 2025) — which
  is why order counterbalancing is the standard mitigation and why S11 keeps the
  rotation the repo already has instead of replacing it.
- **Fit:** the repo already solved the *first* half: bull and bear consume one
  shared report set, so there is no per-side tool choice to unbalance. What is
  unbalanced sits upstream — `classify_tool_pools` moves a tool into the
  deterministic gather only when every required arg is derivable from
  `{ticker, symbol, current_date, curr_date, start_date, end_date,
  look_back_days}`, so everything else stays model-discretionary: **33 tools on
  the audited QQQI run** (market 28, news 4, fundamentals 1). The cost is on
  record — the news analyst's five `get_macro_indicators` calls produced no
  evidence leaves, and `report_verifier` then flagged five tool-grounded
  10Y/RRP/Polymarket lines UNSUPPORTED. Symmetric *firing* is what makes the
  judge's dimension scores and the calibration buckets comparable; it does not
  make the two arguments equally good.
- **Consumer:** `agents/utils/evidence_gather.py` (`gather_for_analyst_node`,
  `_args_for`, plus a `symmetry_report`), `graph/setup.py` (a pre-debate
  assertion node), `scripts/repro_check.py --evidence` (symmetry columns),
  `agents/utils/report_verifier.py` (an advisory `evidence_asymmetry` family),
  and the web debate panel.
- **Data:** all of it already exists — `tool_evidence.json` leaves, the
  `ToolCallLog/*.jsonl` journal, `_model_pool` per analyst, and (since the
  `_journal_executed` fix) the model-pool call args.
- **Failure mode:** a bad plan must **fall back to today's loop** — never raise,
  never silently thin the evidence; **never bind tools to the debaters** (that
  would *create* the per-side choice this item removes); never force-fire the
  catalog (the existing design curates ~10-20 tools per analyst with `ALL`
  opt-in, and the planner selects only within the model-pool remainder); equal
  access must not be reported as equal merit, and no symmetry row may gate a
  verdict.

---

## 3. Explicitly excluded (present, unbuildable, or evidence-weak)

| Candidate | Why excluded |
| --- | --- |
| Variance ratio, CUSUM/EWMA, entropy, Ohlson/Zmijewski, Dechow-Dichev, Taylor rule, MAX/IVOL, AC/TWAP/VWAP/POV, vol-target, Cornish-Fisher, Kappa/LPM, Burke/Martin/Pain, ruin/optimal-f, GP/A, NOA, LM tone, conformal bands, min-CVaR sizing | **already implemented** (rounds 1-2) — verified at the definition site |
| Composite Financial Index's four ratios (primary reserve, net operating revenues, return on net position, viability) | the inputs (expendable net position, non-operating revenues) **do not exist for corporates** and are meaningless for funds; only the *pattern* is transferable (`strength = ratio ÷ common-scale value`, clamped, weighted sum, healthy ≥ 3) and S1/S2/S3 already carry it. Source: [UMS FY20 ratios](https://www.maine.edu/finance/wp-content/uploads/sites/39/2021/03/F-UMSGUS-FY20-ratios.pdf) |
| fffinstill per-metric point tables | **not published** — the page states it is a weighted percentile model, not a point table; its published pillar/lens weights and renormalisation rule are cited as prior art in S3, and its "Trajectory Conviction" backtest (top quintile +14.71% vs bottom −15.46%, 2018-2025, 10 of 12 periods) is a **market** model with no published health-score IC |
| Zenodo weekly rollup (Roy) | the "weighted aggregation" **does not exist** — the code concatenates headlines and prompts Mistral for a narrative; the evaluated classifier (Gradient Boosting on embeddings) scores **test accuracy 0.429 / F1 0.388**, and the source itself lists sentiment-weighted aggregation as future work |
| Fidelity/SMA S-Score internals (per-message scoring, weights, half-life, dedupe) | **not published** in the Fidelity PDF; the formula in circulation comes from a successor vendor's FAQ and is flagged unverified in the research note. Fidelity's own caveat ("has not validated the integrity of this data") and the absence of any IC/hit-rate make it a template, not a method |
| AlphaSense / MarketGrader weights | AlphaSense publishes its scale, the `(#pos − #neg)/total` document score and a cross-sectional normalisation, but the ">90% accurate" claim has no sample or benchmark; MarketGrader's four indicators are reproducible but its **weights are explicitly not disclosed**, and 3 of its 4 legs already exist in the repo |
| Adanos X/Twitter + FMP social indicator | require a social firehose the engine does not ingest (X/Twitter, Reddit at scale) and a spam/source-authority graph; the *buzz skeleton* (mentions, quality, diversity via 1/HHI, 3d-vs-3d trend) is a deferred design note, not a phase, because its validation shows it predicts **volatility, not sign** |
| MSCI estimate-change leg (estimate levels over 3-4 quarters, analyst coverage counts) | inputs absent (only current consensus/PT) → S6 ships the revision-ratio leg and renders this leg `unavailable` with the reason; MSCI publishes **no** validation section at all |
| Baker-Wurgler's six proxies as published | all six are macro/market-wide and **five are unobtainable** here (IPO count, IPO first-day returns, equity share in new issues, dividend premium, CEF discount) → S9 is a labelled reduced-proxy variant at low priority; the "pre-1964 sub-index" in the brief is not in the paper |
| Dechow F-Score / SEC AQM | need SEC AAER/prosecution labels the engine cannot source |
| L-Score (Dorantes, 8 binary criteria) | the review's table states the criteria only as "positive change" without the direction/sign convention needed to implement them unambiguously; not adopted on an under-specified definition |
| ML replacement of the additive scores (balanced-panel/rolling-window learners) | the repo's ground rules require deterministic, auditable scores; the CFA UK source's own warning (selection bias, small-sample properties, poor robustness, alpha decay ≈26% out-of-sample and ≈58% post-publication per McLean & Pontiff) is the reason the additive scores stay, with S8 supplying the out-of-sample discipline instead |

---

## 4. Priority and the binding constraint

The evidence gathered this round points at the same conclusion as round 2, one
level up: **the constraint is not score coverage, it is score *use* and
*validation*.** The repo holds a dozen point scores, none of which any ranking
or filter consumes, and the sentiment pipeline stores a relevance number it
never weights. Correspondingly the highest-value items are the ones that turn
existing measurements into a usable, evaluated score — not new indicators.
The same logic extends one level up: **S11** turns the *evidence* behind the
debate's scores into a measured, symmetric input, because a judge's dimension
scores are only comparable when both sides argued over the same evidence.

Suggested order (detail in the implementation plan):

1. **S1** Altman variants + zones — small, removes a documented misuse (the
   public-manufacturer discriminant on non-manufacturers) and gives an
   unlabelled number a band.
2. **S2** F-Score basis/bands/applicability — small, correctness of an
   already-shipped score.
3. **S10** G-Score + C-Score — medium, genuinely new coverage for the
   growth/semis-heavy book, with published criteria and bands.
4. **S4** weighted news aggregation + confidence caveat — small-medium, the
   highest-value sentiment item: it uses data the pipeline already collects.
5. **S5** crowd ratio + dispersion — small, display-only bands with the
   source's own caveats.
6. **S6** revision-ratio index — small, half the inputs already exist.
7. **S3 + S8** composite quality score and its evaluation rows — medium, and
   only honest together: a composite without IC/coverage/stability rows is
   another unvalidated number.
8. **S7** weighted rolling window + warm-up guard — small.
9. **S9** reduced market sentiment index — **not scheduled**: the research is
   kept as Appendix A in the plan and reopens only if a market-level consumer
   with a decision path appears.
10. **S11** symmetric evidence for paired roles — start with the **no-LLM** parts
    (a symmetry report over the leaves the pipeline already journals, and
    deterministic default args that move enumerable tools out of the model
    pool); add the mirrored discretionary budget and the stage-1 plan call only
    if the measured asymmetry still justifies them.

Two dependencies are settled rather than left open. The **peer universe** for S3
and S10 is the screener scan universe behind one resolver that lands with S10
(§1.1 of the plan), so the third phase to land and the seventh share one
implementation instead of two assumptions. And new tool rows grow the
schema-derived **model pool** that S11 measures — 214 tools repo-wide, 41
model-pool today (33 on the audited run) — so a coverage item is never neutral
with respect to the symmetry work.

---

## 5. Source ledger

Raw per-source extracts — verbatim, including each retrieval note and every
`UNVERIFIED` flag — are in [`research/scoring_round3/`](research/scoring_round3/),
one file per research batch: `piotroski_fundamental.md`,
`altman_composite.md`, `quality_portfolios_index.md`, `finbert_core.md`,
`finbert_applied.md`, `news_pipeline_berkeley.md`,
`vendor_sentiment_scores.md`, `institutional_indices.md`.

| # | Source | Status | Contributed |
| --- | --- | --- | --- |
| 1 | [UCLA F-Score PDF](https://www.anderson.ucla.edu/documents/areas/prg/asam/2019/F-Score.pdf) | retrieved (42pp) | nine criteria with exact bases, 0-1/8-9 bands, 14,043 firm-years 1976-1996, spread 0.230, failure modes → S2 |
| 2 | [Wikipedia Piotroski](https://en.wikipedia.org/wiki/Piotroski_F-score) | retrieved | 0-2/8-9 convention, sector/cyclical caveats, Schwartz & Hanauer 2024 → S2 |
| 3 | [visbanking](https://visbanking.com/financial-ratio-analysis-examples) | partially (original Z only) | original Z + 3.0/1.8 zones; variants **not** on the page → S1 |
| 4 | [fffinstill methodology](https://fffinstill.com/research/methodology) | retrieved | percentile composite with renormalisation, pillar/lens weights, band table, sector rules; point tables not published → S3 |
| 5 | [CFA UK man+machine](https://www.cfauk.org/pi-listing/man-machine-the-evolution-of-fundamental-scoring-models-and-ml-implications) | retrieved | M-Score cut −1.89 (manufacturing-only), Sloan bands, Secker's Z<1 red zone, G-Score 21/23 years, Amor-Tapia & Tascon out-of-sample, ML/alpha-decay warnings → S1/S2/S10 |
| 6 | [Nature review](https://www.nature.com/articles/s41599-024-03888-4) | retrieved (+Tables 1-11) | F/G/C/L criteria and bands, Z/O/M thresholds, recurring metric list, "no standardisation/weights published", no factor-control tests → S3/S10 |
| 7 | [UMS CFI](https://www.maine.edu/finance/wp-content/uploads/sites/39/2021/03/F-UMSGUS-FY20-ratios.pdf) | retrieved | ratio → common-scale strength factor → weighted sum pattern (weights 35/10/20/35, scale −4..10, healthy ≥3); ratios inapplicable → §3 |
| 8 | [Berkeley project](https://www.ischool.berkeley.edu/projects/2024/sentiment-analysis-financial-markets) · [PDF](https://www.ischool.berkeley.edu/sites/default/files/sentiment-analysis-for-financial-markets.pdf) | retrieved | `Σ s_i·conf_i` formula, rejected alternatives (mode, label counts, decay) → S4 |
| 9 | [Fidelity S-Score](https://www.fidelity.com/webcontent/ap110398-researchsnapshot-content/16.13/help/Learn_More_About_Social_Sentiment.pdf) | retrieved (2pp) | scale −4.25..4.25, neutral ±1, SMAs/messages/min coverage, "not validated" caveat; internals unpublished → S5/§3 |
| 10 | [AlphaSense](https://www.alpha-sense.com/blog/engineering/sentiment-score/) | retrieved | sentence labels + confidence, `(#pos−#neg)/total`, cross-sectional normalisation to −99..99 → S4/S5 |
| 11 | [MarketGrader](https://www.marketgrader.com/blog/understanding-the-marketgrader-sentiment-score/) | retrieved | four indicators, 0-10 scale, bands ≤3.9/4-6.9/≥7, missing-indicator reallocation; weights undisclosed → §3 |
| 12 | [MSCI Analyst Sentiment](https://www.msci.com/documents/10199/a925c038-cf5e-9701-fe7a-e4414a06b1ca) | retrieved (16pp) | five descriptor groups, `{3,2,1}` / `{9,7,5,3}` weights, coverage rule, winsor ±3, quarterly rebalance; no validation → S6 |
| 13 | [TradingSim bull/bear](https://www.tradingsim.com/blog/bull-bear-ratio) | retrieved | ratio formula, neutrals excluded, 40/60 bands, persistence limitation → S5 |
| 14 | [FMP weighting guide](https://site.financialmodelingprep.com/education/other/social-sentiment-indicator--indepth-guide-to-analyzing-market-sentiment) | retrieved | the three named weighting factors (no weights), ±1 aggregation rule → §3 |
| 15 | [Adanos X sentiment](https://adanos.org/x-stock-sentiment) | retrieved (+whitepaper) | VADER 40% / RoBERTa 60% ensemble, 5-factor buzz score with exact component math, validation showing volatility-not-sign → §3/S5 |
| 16 | [Baker-Wurgler](https://pages.stern.nyu.edu/~jwurgler/papers/wurgler_baker_cross_section.pdf) | retrieved (full) | six proxies + transformations, two-stage PCA recipe, exact weights (raw and orthogonalised), annual/lagged, conditional evidence → S9 |
| 17 | [arXiv:2306.02136v3](https://arxiv.org/html/2306.02136v3) | retrieved (full) | per-day mean formula, softmax, next-trading-day alignment, titles-only, 1,056,471 records, MSE results, limitations → S4 |
| 18 | [ResearchGate 371311096](https://www.researchgate.net/publication/371311096_Financial_sentiment_analysis_using_FinBERT_with_application_in_predicting_stock_movement) | **403** | replaced by #17 (same paper) |
| 19 | [emergentmind](https://www.emergentmind.com/topics/sentiment-analysis-using-finbert) | retrieved | aggregation schemes (mean / weighted-by-topic / argmax), neutral as residual, uncalibrated-probability warning, benchmarks → S4 |
| 20 | [Medium FinBERT walkthrough](https://medium.com/@ravirajshinde2000/financial-news-sentiment-analysis-using-finbert-25afcc95e65f) | retrieved (+notebook) | concrete tokenisation/label order (`finbert-tone`, argmax), no daily aggregation → S4 |
| 21 | [QuantConnect FinBERT](https://www.quantconnect.com/docs/v2/writing-algorithms/machine-learning/hugging-face/popular-models/finbert) | retrieved | 10-day window, `e^{linspace}` weights, softmax, monthly cadence + 14-day gap + 30-day warm-up → S4/S7 |
| 22 | [finbert.org](https://finbert.org/) | retrieved (commercial wrapper) | model card facts taken from `ProsusAI/finbert` + Araci 2019 (PhraseBank 4,845 sentences, 64-token limit, Acc 0.86/F1 0.84) → S4 |
| 23 | [Lycore](https://www.lycore.com/blog/financial-news-sentiment-analysis/) | retrieved | LM pre-filter → FinBERT order, <80ms/doc, source-credibility/velocity/cross-source wording, IC/rank-IC walk-forward discipline → S8 |
| 24 | [Zenodo 17510736](https://zenodo.org/records/17510736) | landing page unreachable; author artifacts used | weekly grouping by concatenation (no weighted formula), GBM on embeddings, test Acc 0.429/F1 0.388 → §3 |
| 25 | [Berkeley project page](https://www.ischool.berkeley.edu/projects/2024/sentiment-analysis-financial-markets) (dup of #8) · Fidelity/AlphaSense/MarketGrader/MSCI/TradingSim/Adanos/Baker-Wurgler repeated in the second batch | — | no new content |

Second pass (orchestration / judge bias, for S11):

| # | Source | Status | Contributed |
| --- | --- | --- | --- |
| 26 | [ReWOO](https://arxiv.org/abs/2305.18323) (arXiv:2305.18323, 2023) | retrieved (abs + abstract) | plan-with-evidence-placeholders before execution; 5x token efficiency, +4% HotpotQA, robustness under tool failure → S11 |
| 27 | [LLMCompiler](https://arxiv.org/abs/2312.04511) (arXiv:2312.04511, ICML 2024) | retrieved (abs + abstract) | planner / task-fetching unit / executor split for parallel function calls; up to 3.7x latency, 6.7x cost, ~9% accuracy vs ReAct → S11 |
| 28 | [Plan-and-Solve](https://arxiv.org/abs/2305.04091) (arXiv:2305.04091, ACL 2023) | retrieved (abs + abstract) | devise a plan, then carry out the subtasks; the prompt-level form of the staging → S11 |
| 29 | [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) (2024-12-19) | retrieved (full) | the workflow taxonomy that names the pattern: prompt chaining, parallelisation (sectioning/voting), orchestrator-workers, evaluator-optimizer; "workflows are systems where LLMs and tools are orchestrated through predefined code paths" → S11 |
| 30 | [Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge](https://arxiv.org/abs/2406.07791) (arXiv:2406.07791, AACL-IJCNLP 2025) | retrieved (abs + abstract) | 15 judges, 22 tasks, >150,000 instances; bias "not due to random chance", varies by judge/task, strongly affected by the solution quality gap; repetition stability / position consistency / preference fairness metrics → why S11 keeps order rotation and never treats symmetry as merit |
