# Design: News, Filings, and Disclosure Signals

**Status:** DESIGN - not built
**Version:** 1.0
**Date:** 2026-09-23
**Scope:** The text channel - `text_factors`, `news_score`, `news_relevance`, `sentiment_score`,
`sentiment_research`, `dataflows/sec_edgar.py`, and the disclosure reads the analysts consume. Takes
the 3 high- and 9 medium-relevance text/news papers from the 2026 `q-fin` corpus survey.
**Parent:** `docs/design_fin_paper_survey_26.md` (v1.0, SURVEY)
**Rule-4 impact:** none. The app renders the news/sentiment blocks generically; no schema changes.

---

## 1. Executive summary

### The corpus's most usable text result, and it is a prior

**2608.14014** tags 4.57M articles across roughly 3,000 US stocks (2023-2026) with one of **17 event
tags** plus five binary attributes, clusters repeated coverage into **stories** so a first report is
separable from follow-ups, and measures beta-adjusted abnormal returns around **1.68M stock-day
events** against 364,405 neutral-sentiment events used as a built-in placebo. Three findings, each of
which is a number the engine could hold:

1. **The move is already spent by the closing bell.** Pooled across signed events, the cumulative
   move in the news direction by the close of publication day is **2.8x** its value twenty days
   later. For rumor-flagged events, the rumor day captures the *entire* move and the subsequent
   confirmation contributes nothing (+0.36% on the rumor day, -0.09% into news, +0.01% on the news
   day, -0.06% over days +6..+20).
2. **Markets underreact to numbers and overreact to stories.** Quantified tags keep drifting in the
   news direction for weeks - **capital returns +0.35% (`p < 0.001`), earnings +0.22% (`p < 0.001`)** -
   while soft story-driven tags give the move back - **macro -0.34% (`p < 0.001`), launch -0.18%,
   leadership -0.18%**. Under Benjamini-Hochberg at 5% the macro reversal plus the capital-returns and
   earnings continuations survive.
3. **News carries width as well as direction.** Publicity *raises* volatility before publication and
   volatility declines once the news is out, because publication resolves uncertainty.

The paper offers its table explicitly as "a prior in news-conditioned forecasting models". This
engine's house rule allows exactly that: a prior may widen or inform, and must not silently exclude.
The engine already has the shape for such a prior - `market_session.gap_type` (`:220`) is an
empirical conditional distribution used as context.

### Two sharp gaps in machinery that already exists

- **Agreement is measured and never learned from.** `strategies/sentiment.py` documents
  `consensus_over_seeds` and `agree_rate`; `strategies/consensus.py` has `agreement_score` (`:14`)
  and `weighted_consensus` (`:32`). **2603.20965** trains a logistic aggregator over three zero-shot
  agents' labels, **confidences** and agreement structure and raises balanced accuracy from 0.561
  (best single agent) to **0.612**, beating majority vote (0.573) and confidence-weighted vote
  (0.584). The engine computes every ingredient and uses none of them as a feature.
- **The filing-tone number is a dictionary the corpus says points the wrong way.** `text_factors.lm_tone`
  (`:121`) is a reduced Loughran-McDonald dictionary (`DICTIONARY_VERSION = "lm-seed-v1"`). **2607.14174**
  finds a Loughran-McDonald baseline "consistently, strongly negatively correlated with price at
  every level tested", and reports that **the narrow Item 1A risk-factor section beats the full filing
  at the single-firm level** (76% vs 75% on return, 75% vs 69% on volatility) while the reverse holds
  at sector and portfolio aggregation.

### The line the engine cannot cross

**2607.28127** (FinSMART) posts cumulative 264.9% against FinDPO's 109.8% by training on a reward
built from **publication-day returns** - the paper says so plainly, and it is the mechanism behind the
headline. That is a look-ahead a live decision path cannot have. It is recorded here as a clean
illustration of why the honesty doc's gates exist, and declined.

---

## 2. What this repo already has (verified)

| Instrument | Where, verified |
|---|---|
| Loughran-McDonald tone (reduced dictionary) | `strategies/text_factors.py:121` `lm_tone`, `DICTIONARY_VERSION = "lm-seed-v1"` |
| Readability, cross-document divergence | `strategies/text_factors.py:170`, `:198` |
| News relevance scoring and admission (lexical) | `strategies/news_relevance.py:53` `score_news_article`, `:97` `admit_article` |
| News novelty (first-seen share) | `strategies/news_score.py:215` `news_novelty` |
| News score over nine categories | `strategies/news_score.py:336` `news_score` |
| Sentiment aggregation, syndication dedup, after-close bucketing | `strategies/sentiment.py:626` `aggregate_weighted_sentiment`, `:511` `daily_sentiment_sma`, `:397` `_bucket_day` |
| Consensus / agreement / weighted consensus (**rating-based**) | `strategies/consensus.py:14` `agreement_score`, `:32` `weighted_consensus`, `rating_to_number`, `consensus_from_score` |
| Documented-but-absent: `consensus_over_seeds`, `agree_rate` | named in `strategies/sentiment.py`'s module docstring (lines 7, 10) with **no implementation anywhere** |
| Granger causality between two series | `strategies/statistical.py:273` `granger_causality` |
| Abnormal-return residualization | `strategies/cross_section.py:201` `residualize_returns` |
| Regime-conditioned tabulation of scored rows | `strategies/regime_performance.py:24` `regime_conditioned_performance` |
| A measured conditional prior, as precedent | `strategies/market_session.py:220` `gap_type` |
| SEC filing access | `dataflows/sec_edgar.py` (incl. `peek_sic` / Item 1A retrieval) |
| Entropy family (single-series) | `strategies/complexity.py:19` `permutation_entropy`, `:48` `approximate_entropy`, `:87` `lz_complexity` |

Grep for `event_tag | drift_table | drift_prior | tag_taxonomy` returns nothing: **no event-tag
taxonomy, no story clustering, and no per-tag forward-drift prior exist.**

## 3. The gaps, as builders

### N1 - An event-tag taxonomy, story clustering, and a per-tag drift prior

**Finding.** The engine's news pipeline scores an article and counts it. It cannot say what *kind* of
event the article is, whether it is the first report or the twentieth, or what a tag has historically
drifted by - which is the difference between counting news and knowing what news does.

**Paper.** 2608.14014 (numbers in §1 above).

**What to compute.**
- `tag_article(article) -> {tag, attrs}` over a fixed taxonomy, with `attrs` including
  `rumor`, `quantified`, `scheduled`, `forward_looking`, `primary_source`.
- `cluster_stories(articles, ticker, day) -> [{story_id, first_report: bool, tag}]` on title+summary
  embedding cosine (the paper uses 0.80), which is what makes first reports separable from follow-ups.
- `tag_drift_prior(tag) -> {drift_h6_20, width_term, n_events, lo, hi}` estimated offline on the
  engine's own panel, carried into the news read **as a prior with its interval and its event count**,
  never as a gate.
- The width term is a *separate* output: the paper's volatility result means a tag predicts a change
  in dispersion, not only in level.

**Inputs.** Timestamped articles with a signed sentiment (the engine's chain already carries
`ticker_sentiment_score`); daily adjusted closes plus SPY for betas; dollar volume for size buckets.
The paper distills an LLM teacher into an 82M student at 125-160 articles/s, so **production tagging
needs no per-article LLM call**; the engine has no teacher/student pair, so the equivalent is 1-2
batched tag calls per symbol-day over that day's articles.

**PIT.** Tags are descriptive labels, so tagging is PIT-safe provided the classifier is not retrained
on labels derived from the window it then conditions. Two specific breakers to guard: computing the
rolling beta over the full sample instead of ending at `t-1`, and landing a post-close article on its
own trading day - the latter already guarded by `sentiment._bucket_day` (`:397`), which rolls an
article stamped at or after 16:00 New York to the next session.

**Cost.** Tagging is cheap once a local classifier exists; the drift table is an offline estimation
over the report panel.

**Owner.** New module, consuming `cross_section.residualize_returns` (`:201`, the exact
`r_i - (alpha + beta*r_m)` form the paper uses), `news_score.news_novelty` (`:215`, the existing
NEW-vs-follow-up count) and `sentiment._bucket_day`.

**Caveat.** Descriptive, not causal - the authors say so. Per-tag p-values sit at the boundary for
several tags (Benjamini-Hochberg q between 0.05 and 0.07), and the neutral-coverage background drift
is **negative** for every size bucket (-0.92% small, -0.58% mid, -0.34% large), which the prior must
carry or it will misattribute the background to the tag.

### N2 - A filing-tone number that is supervised, section-scoped, and volatility-targeted

**Finding.** `lm_tone` (`:121`) is the engine's only filing-tone number. It is a fixed reduced
dictionary with no volatility target and no section scope - and the corpus's finding is that this
class of dictionary is negatively correlated with price.

**Paper.** 2607.14174 builds two document-term matrices (full text and Item 1A alone), learns word
polarities supervised against **both return and volatility labels** at three aggregation levels, and
reports the reversal that matters: full-filing sentiment wins at sector and portfolio level
(78% vs 73% return accuracy), but **Item 1A alone wins at the single-firm level** (Nvidia: 76% vs 75%
return, 75% vs 69% volatility).

**What to compute.** `filing_sentiment(filing, scope="item_1a"|"full") -> {score, vol_score}` where
`scope="item_1a"` is the **default for firm-level use** - the inverse of the naive choice - and
`vol_score` is a distinct output because risk-factor language is argued to inform volatility more
directly than direction. Both the dictionary baseline and the supervised score should be reported
side by side for one release cycle, since the paper's claim is precisely that they disagree.

**Inputs.** 10-K text with Item 1A extracted - `dataflows/sec_edgar.py` already retrieves the section;
the engine needs a section *parser* it does not have. Training labels need a few years of return and
volatility outcomes.

**PIT.** Filing date is known; the supervised lexicon is frozen per version and must carry its
version with the score.

**Cost.** One parse and score per filing; offline lexicon training.

**Owner.** `strategies/text_factors.py` for the score, `dataflows/sec_edgar.py` for extraction.

**Caveat.** One sector, 94 firms, and the headline reversal rests on a single named company with a
6-point volatility edge at `n = 1`. 10-K bodies are boilerplate-heavy, which is the dilution the paper
blames; a parser that extracts the wrong section would silently reproduce the full-filing case.

### N3 - Learn the agreement the engine already measures

**Finding, stated precisely.** The engine has consensus *machinery* but no confidence-aware
aggregation, and its docstring is ahead of its code. `strategies/consensus.py` really does implement
`agreement_score` (`:14`, the normalized range of 5-tier stances), `weighted_consensus` (`:32`),
`consensus_from_score` and `rating_to_number` - all operating on **ratings**, not on confidences.
Meanwhile `strategies/sentiment.py`'s module docstring documents two helpers that **do not exist
anywhere in the package**: `consensus_over_seeds(verdicts)` at docstring line 7 and
`agree_rate(verdicts)` at line 10, with no implementation behind either. So disagreement is
computable from ratings, promised for seeds, and in no case consumed as a feature.

**Paper.** 2603.20965's three zero-shot agents (performance, guidance, risk lenses) each return
`{label, confidence, rationale}`; a **trained logistic aggregator** over labels, confidences and the
agreement structure raises balanced accuracy for next-day direction from **0.561 to 0.612**, beating
majority vote (0.573) and confidence-weighted vote (0.584). Confidence is the geometric mean token
probability where logprobs are exposed, else a clipped self-report.

**What to compute.** `learned_aggregator(agent_outputs, agreement_features) -> {label, confidence}`
trained on the engine's own decision ledger - which already stores the outcomes this needs. The
feature vector is the missing part: it must include *agreement structure*, not just the votes.

**Inputs.** Agent outputs with confidences (the engine's structured-output path can expose them) and
realized next-day outcomes from the prediction ledger.

**PIT.** Train on outcomes strictly before the evaluation window.

**Cost.** A logistic regression over a modest feature vector; the labelled history is the cost.

**Owner.** New module, consuming `strategies/consensus.py` and `strategies/prediction_ledger.py`.

**Caveat.** The target is next-day direction at a **53% base rate** and the edge is ~5 balanced-
accuracy points; the paper concedes the prompt partition may drive part of it. Its base models are not
this engine's providers, and per-token logprobs are not uniformly exposed.

### N4 - Multi-dimensional sentiment, with the dimensions named

**Finding.** Sentiment enters the engine as a polarity-like number. The corpus's evidence is that
*polarity is the weakest of five dimensions*.

**Paper.** 2603.11408 elicits **relevance, polarity, intensity, uncertainty, forwardness** per
article, aggregates to the week by a relevance-weighted mean of each dimension, and reports AUC 0.6515
and IC 0.2283 against an AlphaVantage-only baseline's 0.5694 and 0.0910 - with **intensity and
uncertainty the top SHAP features**.

**What to compute.** Per-article multi-dimension elicitation with a **relevance-weighted**
aggregation, and the dimensions kept separate in the output rather than collapsed. Note the engine
already emits an `uncertainty` count from `lm_tone` (`:121`) - a dictionary count, not an elicited
dimension, and the paper's point is that the elicited version carries the signal.

**Inputs.** The article set the engine already fetches; one structured LLM call per article.

**PIT.** Article timestamp; `sentiment._bucket_day` (`:397`) already handles the after-close case.

**Cost.** One LLM call per article - this is the doc's most expensive per-run item, so it belongs on
the admitted subset after `news_relevance.admit_article` (`:97`), not on the raw feed.

**Owner.** New module beside `strategies/sentiment_score.py`.

**Caveat.** One commodity, weekly, with AUC differences **inside one standard deviation** and a 20%
sample. LLM-elicited dimensions are prompt-versioned and shift silently under model upgrades, so the
prompt version must be stored with every score - a requirement, not a nicety.

### N5 - A harness that can detect a prompt-framing effect (not a framing)

**Finding.** The engine's analyst prompts are fixed strings with no versioning and no A/B path, so a
framing effect cannot be detected or attributed even if it exists.

**Paper.** 2606.00061 adds Soros reflexivity awareness to a zero-shot forecasting prompt across four
accumulating conditions and reports that the effect is **model-dependent**: one model improves
monotonically, another only at a 60-month window, a third mostly does not - and **the same model flips
sign across context windows**. With `n = 72` per cell and no multiple-comparison control against a
50% baseline.

**What to compute.** A prompt-condition A/B harness: version the prompt as a first-class input, record
which condition produced a run, and score per-condition accuracy on the engine's own decision ledger.
**Adopt the harness, not the framing.** This is the same requirement 2606.22719 imposes from the other
direction (re-score any LLM claim against a non-LLM comparator on identical inputs), and the same one
the honesty doc needs for attribution.

**Inputs.** The existing prompt strings and the decision ledger.

**PIT.** Not applicable; it is a measurement of the engine's own behaviour.

**Cost.** Doubles the LLM spend of any run used for the comparison, so run it offline on a sample.

**Owner.** `agents/utils/prompt_metrics.py` already exists for decision-context telemetry - this
extends it to a *condition* axis.

**Caveat.** The paper is **weak evidence for its own framing** (`n = 72`, sign flips across windows).
The harness is the deliverable and the framing is explicitly not.

### N6 - Semantic news selection instead of lexical admission

**Finding.** `news_relevance.score_news_article` (`:53`) admits by ticker-in-title (+55), snippet
(+34), URL (+18) and company-name matches. An article that is genuinely material but never names the
ticker is scored low.

**Paper.** 2603.19286 encodes every article with a pre-trained encoder and pools the day's articles
using the **stock-name embedding as an attention query**, reporting a 7.11% one-day-ahead price MAE
reduction.

**What to compute.** An embedding-based relevance score to run **alongside** the lexical one for a
bounded period, with their disagreements logged. This is deliberately a comparison first: the engine's
lexical filter is explainable and the embedding filter is not, so replacing it needs evidence, not
plausibility.

**Inputs.** A text encoder (torch) the engine does not have, or a hosted embedding endpoint.

**PIT.** Article timestamp.

**Cost.** One embedding per article; cheap if hosted.

**Owner.** `strategies/news_relevance.py`.

**Caveat.** Weak-to-moderate evidence: two markets, six TWSE stocks as one of them, a single headline
number with **no confidence interval, no significance test, and no tradable target** (MAE on price
level is not a return). Do not replace the lexical filter on this paper alone.

### N7 - A semantic plausibility screen on lead-lag candidates

**Finding.** `statistical.granger_causality` (`:273`) tests a caller-supplied pair and cannot tell an
economically nonsensical lead from a real one. Nothing screens candidates *before* the test.

**Paper.** 2602.07048 screens pairs by Granger strength into a top-100, then has an LLM judge whether
each directed lead admits a **plausible economic mechanism**, raising the win rate from 51.4% to 54.5%
and cutting the average losing trade from $649 to $347.

**What to compute.** A candidate-pair universe scan plus an LLM semantic plausibility stage *in front
of* the existing Granger machinery. The statistical test stays the authority; the LLM only removes
pairs it cannot justify, and its rejections are logged (a refusal ledger, per the honesty doc's H7).

**Inputs.** The engine's sector-ETF-to-name pairs, which are already known, plus their titles/descriptions.

**PIT.** Both series observed up to `t`.

**Cost.** One LLM call per candidate pair, offline and cached.

**Owner.** New module; `statistical.granger_causality` (`:273`) is reused as-is.

**Caveat.** The paper's setting supplies per-event probability series and natural-language event
titles that do not exist here, and its own scale is weak (18 rolling periods, 554 markets). The
analogue - sector-ETF-to-name leads - is a much narrower application than the paper's.

---

## 4. Recorded and declined

- **2607.28127 (FinSMART)** - declined. Its reward is built from publication-day returns **by design**,
  which is a look-ahead a live path cannot have; the paper is candid that this is the mechanism behind
  the headline. Recorded as the clearest case in the corpus of a result the honesty doc's gates exist
  to catch.
- **2608.29669** (a Wasserstein-barycentric peer field from frozen multi-year article embeddings)
  requires a sentence encoder plus a multi-year per-firm article archive the engine does not have, and
  its headline rests on **52 firms** - below a usable cross-section. Cross-referenced from the risk
  doc as out of reach.
- **2604.26811** (transfer-entropy spillover network, news versus social media) produces a **network
  description with no measured forward-return mapping**, so under the rule that nothing enters the
  composite by adjacency there is no consumable number here. It also needs a true second media source;
  the engine's social proxy cannot stand in.
- **2603.19286**'s encoder and **2603.11408**'s per-article elicitation both need torch or a hosted
  embedding/LLM endpoint at volume; N4 and N6 are scoped to admitted subsets for that reason.

## 5. Owners, in one table

| # | Produces | Owner | New module? |
|---|---|---|---|
| N1 | event tags, story clustering, per-tag drift prior, width term | new, consuming `cross_section` / `news_score` / `sentiment` | yes |
| N2 | Item 1A-scoped, volatility-supervised filing sentiment | `strategies/text_factors.py`, `dataflows/sec_edgar.py` | partly |
| N3 | learned aggregator over labels, confidences and agreement | new, consuming `consensus.py` + `prediction_ledger.py` | yes |
| N4 | five-dimension elicitation with relevance weighting | new, beside `sentiment_score.py` | yes |
| N5 | prompt-condition A/B harness | `agents/utils/prompt_metrics.py` | no |
| N6 | embedding-based news relevance (compared, not swapped) | `strategies/news_relevance.py` | no |
| N7 | semantic plausibility screen on lead-lag candidates | new, reusing `statistical.granger_causality` | yes |

## 6. Honest limits

1. **N1's per-tag table is a prior, and several of its tags sit at the FDR boundary.** Reporting a
   boundary tag as a finding would be exactly the over-claim the honesty doc forbids; the prior must
   carry `n_events` and its interval, and the background drift must be subtracted.
2. **The corpus's text results are the weakest in the survey by evidence quality.** Three of the
   papers here rest on one commodity, one sector, or sixty-nine cells. N1 is the exception, and it is
   descriptive rather than causal by its own statement.
3. **N4's cost is real.** One LLM call per article against a per-name flow of tens of articles per day
   is affordable; against a raw feed it is not. The admission filter is a prerequisite, not an
   optimisation.
4. **Two items would need torch or a hosted encoder**, which changes the engine's dependency profile -
   a decision the owner should make explicitly rather than inherit from a design doc.
5. **Nothing here enters the composite by adjacency.** N1-N7 feed `news_score` and `sentiment_score`,
   which sit outside `COMPOSITE_ENGINES` by the owner's existing decision, and the doc does not
   propose changing that.

## 7. Recommended build order

1. **N3** - the ingredients already exist, the label source already exists, and it is the smallest
   item with a measured effect in the theme.
2. **N1** - the theme's largest result; the tag taxonomy and story clustering are the substantial
   parts, the drift table is the payoff.
3. **N2** - closes the `lm_tone` question honestly, and its default (`item_1a`) is the opposite of
   what the engine would do today.
4. **N5** - a measurement change, cheap, and it makes every later prompt edit attributable.
5. **N7**, **N4**, **N6** - in that order; N6 deliberately last, because it compares rather than
   replaces and should run for a bounded period before any swap.

**Decision requested:** whether N3 + N1 land first, and whether the engine may add a hosted-embedding
dependency for N1's tagging and N6's comparison.
