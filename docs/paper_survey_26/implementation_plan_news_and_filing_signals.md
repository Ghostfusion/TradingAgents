# Implementation Plan - Text, News and Disclosure Signals

Status: **PLAN - not started.** Implements the seven items (N1-N7) of the text, news and disclosure
theme, one of the six themes derived from
[`../design_fin_paper_survey_26.md`](../design_fin_paper_survey_26.md) (v1.0, SURVEY).
**Parent design:** [`design_news_and_filing_signals.md`](design_news_and_filing_signals.md) - owns the
findings, the papers, the alternatives and the caveats for N1-N7; this plan owns the sequence, the
gates, the failing-first tests and the acceptance criteria.
**Folder index:** [`README.md`](README.md) - the eight inherited ground rules, the measured dependency
surface, the cross-theme phase map, the dependency graph, the run-budget split and the landing
protocol live there.
**Items:** N3 (P2); N1, N2, N4, N5, N6, N7 (P3).
**Gates added:** 7 - `enable_learned_aggregator`, `enable_news_event_tags`, `enable_filing_sentiment`,
`enable_multidim_sentiment`, `enable_prompt_condition_harness`, `enable_embedding_relevance`,
`enable_leadlag_plausibility`. No existing gate is extended by this theme.

## 0. Scope

This plan covers N1-N7 only: the text channel (`text_factors`, `news_score`, `news_relevance`,
`sentiment_score`, `sentiment_research`, `dataflows/sec_edgar.py`) and the disclosure reads the
analysts consume. Every item is additive and default-off, changes no existing computation, and
degrades to `unavailable` when its inputs are missing.

The inherited rules that bind this theme specifically are **rule 3** (nothing enters
`COMPOSITE_ENGINES` - N1-N7 feed `news_score` and `sentiment_score`, which sit outside it by the
owner's existing decision), **rule 4** (`n_events` and intervals travel with N1's prior, N4 refuses an
empty admitted set, N6 reports its disagreements), **rule 5** (each test proven failing under a
targeted mutation), **rule 7** (a new public function in `strategies/` or `dataflows/` ships with its
first caller), and **rule 8** (N5 and N7 are OFFLINE, never called from `prepare_initial_state`,
`finalize_run` or any agent tool). The rest are in [`README.md`](README.md).

**Not built.** No sentiment branch is built on a halted news-quantification surface, and none of the
material the design doc's section 4 records as declined or out of reach becomes a build target.
2607.28127 (FinSMART) is the case in point: its reward is built from publication-day returns **by
design**, which is a look-ahead a live decision path cannot have.

## 1. Item cards

### N3 - Learned aggregator over labels, confidences and agreement

**Target.** New module consuming `strategies/consensus.py` (`agreement_score:14`,
`weighted_consensus:32`, `rating_to_number`, `consensus_from_score`) and
`strategies/prediction_ledger.py`; symbol
`learned_aggregator(agent_outputs, agreement_features) -> {label, confidence}`.
**Phase / run mode.** P2 / in-run.
**Behaviour.** A logistic aggregator trained over labels, confidences and the agreement structure the
engine already measures. Confidence is the geometric mean token probability where logprobs are
exposed, else a clipped self-report. `consensus.py` keeps operating on ratings and is unmodified; the
documented-but-absent `consensus_over_seeds` (docstring line 7) and `agree_rate` (line 10) in
`strategies/sentiment.py` are not implemented here - the feature vector is the deliverable.
**Gate.** `enable_learned_aggregator`, default off.
**Failing-first test.** `tests/test_learned_aggregator.py::test_agreement_structure_columns_required` -
delete the agreement-structure columns from the feature vector (leaving votes and confidences only)
and the test must fail by name: it asserts the trained aggregator beats the confidence-weighted vote
(0.584) and the majority vote (0.573) on a fixture ledger, and that the agreement-structure columns
are what carry it past them.
**Acceptance.** On the fixture ledger the aggregator's balanced accuracy exceeds 0.584 and 0.573;
trained only on outcomes strictly before the evaluation window; `unavailable` when the ledger holds no
labelled history; `consensus.py`'s outputs unchanged bit-for-bit.
**Depends on.** Nothing.
**Doc caveat.** The target is next-day direction at a 53% base rate, the edge is ~5 balanced-accuracy
points, and the paper concedes the prompt partition may drive part of it; its base models are not this
engine's providers and per-token logprobs are not uniformly exposed.

### N1 - Event tags, story clustering and a per-tag drift prior

**Target.** New module: `tag_article(article) -> {tag, attrs}` over a fixed taxonomy with `attrs`
including `rumor`, `quantified`, `scheduled`, `forward_looking`, `primary_source`;
`cluster_stories(articles, ticker, day) -> [{story_id, first_report: bool, tag}]` on title+summary
embedding cosine (the paper's 0.80); `tag_drift_prior(tag) -> {drift_h6_20, width_term, n_events, lo,
hi}`. Consumes `cross_section.residualize_returns:201` (the exact `r_i - (alpha + beta*r_m)` form the
paper uses), `news_score.news_novelty:215` and `sentiment._bucket_day:397`.
**Phase / run mode.** P3 / in-run tagging and clustering + offline fit for the drift table.
**Behaviour.** Tagging and clustering run in-run at 1-2 batched tag calls per symbol-day (the engine
has no teacher/student pair, so a per-article LLM call is not the analogue); the drift table is
estimated offline on the panel and read in-run. The prior widens or informs the news read and **never
gates it**; `width_term` is separate because a tag predicts a change in dispersion, not only in level.
**Gate.** `enable_news_event_tags`, default off.
**Failing-first test.** `tests/test_news_event_tags.py::test_background_drift_is_subtracted` - remove
the background-drift subtraction from the offline fit and the test must fail by name: it asserts that a
tag whose measured drift equals its size bucket's background (-0.92% small, -0.58% mid, -0.34% large)
yields a prior of ~0, and that every fitted row carries `n_events`, `lo` and `hi`.
**Acceptance.** `tag_drift_prior` returns `unavailable` for a tag with no fitted row; every fitted row
carries `n_events` and an interval; the background is subtracted per size bucket; no caller may read
the prior as an exclusion. Both breakers are guarded: the rolling beta ends at `t-1`, and `_bucket_day`
rolls an article stamped at or after 16:00 New York to the next session.
**Depends on.** P0-1 (H10) for the window the offline panel reports; the in-run reader needs the
offline artefact alone.
**Doc caveat.** Descriptive, not causal - the authors say so; several tags sit at the FDR boundary
(Benjamini-Hochberg q between 0.05 and 0.07) and the neutral-coverage background drift is negative in
every size bucket.

### N2 - Item 1A-scoped, volatility-supervised filing tone

**Target.** `strategies/text_factors.py` (`lm_tone:121`, `DICTIONARY_VERSION = "lm-seed-v1"`) for the
score, `dataflows/sec_edgar.py` for extraction; symbol `filing_sentiment(filing,
scope="item_1a"|"full") -> {score, vol_score}`, plus the section parser the engine does not have.
**Phase / run mode.** P3 / in-run scoring + offline fit (the supervised lexicon).
**Behaviour.** Two document-term matrices (full text and Item 1A alone) with word polarities learned
supervised against **both** return and volatility labels; `scope="item_1a"` is the firm-level default,
the inverse of the naive choice, and `vol_score` is a distinct output because risk-factor language is
argued to inform volatility more directly than direction. Dictionary baseline and supervised score are
reported side by side for one release cycle, because the paper's claim is that they disagree.
**Gate.** `enable_filing_sentiment`, default off.
**Failing-first test.** `tests/test_filing_sentiment.py::test_item_1a_is_the_default_scope` - flip the
default `scope` to `"full"` and the test must fail by name: it asserts the default call reports
`scope == "item_1a"` and returns both `score` and `vol_score`, and that a filing with no extractable
Item 1A is `unavailable` rather than silently scored as full.
**Acceptance.** On a filing whose Item 1A section is present, the default call is Item 1A-scoped and
carries both outputs; the frozen lexicon version travels with every score; `lm_tone`'s output is
unchanged bit-for-bit; a wrong-section parse is detectable because the score reports its own scope.
**Depends on.** Nothing.
**Doc caveat.** One sector, 94 firms, and the headline reversal rests on a single named company with a
6-point volatility edge at `n = 1`; 10-K bodies are boilerplate-heavy, and a parser that extracts the
wrong section would silently reproduce the full-filing case.

### N4 - Five-dimension elicitation, relevance-weighted

**Target.** New module beside `strategies/sentiment_score.py`: per-article elicitation of relevance,
polarity, intensity, uncertainty, forwardness, aggregated to the week by a relevance-weighted mean.
Consumes `news_relevance.admit_article:97` and `sentiment._bucket_day:397`.
**Phase / run mode.** P3 / in-run, admitted subset only.
**Behaviour.** The five dimensions stay separate in the output rather than collapsing into one
polarity-like number, and the prompt version is stored with every score. Elicitation runs only on
articles `admit_article` admitted, at one structured LLM call per admitted article - the admission
filter is a prerequisite, not an optimisation.
**Gate.** `enable_multidim_sentiment`, default off.
**Failing-first test.** `tests/test_multidim_sentiment.py::test_relevance_weighted_aggregation` -
replace the relevance-weighted mean with an unweighted mean and the test must fail by name: it asserts
the weekly aggregate equals the relevance-weighted mean on a fixture whose admitted articles differ in
relevance and intensity, and differs from the unweighted one.
**Acceptance.** Every score carries `prompt_version`; an article rejected by `admit_article` never
receives an elicitation call; the five dimensions are returned separately; `unavailable` when the
admitted set is empty; the reported `uncertainty` is the elicited dimension, not `lm_tone`'s
dictionary count.
**Depends on.** Nothing in this theme.
**Doc caveat.** One commodity, weekly, with AUC differences **inside one standard deviation** and a
20% sample; LLM-elicited dimensions shift silently under model upgrades, so the prompt version must be
stored with every score - a requirement, not a nicety.

### N5 - Prompt-condition A/B harness

**Target.** `agents/utils/prompt_metrics.py`, extended from decision-context telemetry to a
**condition** axis: the prompt is versioned as a first-class input, the condition is recorded per run,
and per-condition accuracy is scored on the decision ledger.
**Phase / run mode.** P3 / offline.
**Behaviour.** Adopt the harness, not the framing. The engine's prompt strings do not change; what
changes is that a prompt edit becomes attributable, and any LLM claim can be re-scored against a
non-LLM comparator on identical inputs.
**Gate.** `enable_prompt_condition_harness`, default off.
**Failing-first test.** `tests/test_prompt_condition_harness.py::test_condition_recorded_per_run` -
stop writing the prompt condition into the ledger row and the test must fail by name: it asserts two
runs under different conditions produce two distinguishable rows and a per-condition accuracy table,
and that a run whose condition was not recorded is `unavailable` rather than pooled into the total.
**Acceptance.** Two conditions produce two ledger rows and two accuracy numbers, each with its count;
no run is scored without a condition; the comparison doubles LLM spend, so it runs offline on a sample
(ground rule 8).
**Depends on.** Nothing.
**Doc caveat.** The paper is **weak evidence for its own framing** (`n = 72` per cell, sign flips
across context windows, no multiple-comparison control against a 50% baseline); the harness is the
deliverable and the framing explicitly is not.

### N6 - Embedding news relevance, compared not swapped

**Target.** `strategies/news_relevance.py`: an embedding-based relevance score beside the lexical
`score_news_article:53` and `admit_article:97`, with their disagreements logged.
**Phase / run mode.** P3 / in-run.
**Behaviour.** Both scores are reported per article for a bounded period and every disagreement is
logged. The lexical filter remains the admitting authority, because it is explainable and the
embedding filter is not - this is deliberately a comparison first, and replacing it needs evidence,
not plausibility.
**Gate.** `enable_embedding_relevance`, default off.
**Failing-first test.** `tests/test_embedding_relevance.py::test_lexical_admission_unchanged_and_disagreements_logged` -
let the embedding score feed `admit_article` and the test must fail by name: it asserts admission
decisions are bit-identical to the lexical-only decisions over a fixture feed while the gate is on,
and that each disagreement between the two scores appears in the log.
**Acceptance.** With the gate on, admission decisions are unchanged; both scores and every
disagreement are reported; `unavailable` when no encoder is configured - the gate being on is not the
same as an encoder being present.
**Depends on.** The dependency decision in section 5 (torch declared, or a hosted embedding endpoint);
nothing else in this theme.
**Doc caveat.** Weak-to-moderate evidence: two markets, six TWSE stocks as one of them, a single
headline number with no confidence interval, no significance test and no tradable target (MAE on
price level is not a return) - do not replace the lexical filter on this paper alone.

### N7 - Semantic plausibility screen on lead-lag candidates

**Target.** New module reusing `strategies/statistical.py:273` (`granger_causality`) as-is: a
candidate-pair scan plus an LLM semantic plausibility stage **in front of** the existing test, with
rejections written to the refusal ledger (P0-3).
**Phase / run mode.** P3 / offline (one LLM call per candidate pair, cached).
**Behaviour.** The statistical test stays the authority; the semantic stage only removes pairs it
cannot justify, and it can never promote a pair the test rejects. Rejections are logged, so the
screen's precision becomes measurable instead of assumed.
**Gate.** `enable_leadlag_plausibility`, default off.
**Failing-first test.** `tests/test_leadlag_plausibility.py::test_rejection_logged_and_test_keeps_authority` -
drop the refusal-ledger write for rejected pairs and the test must fail by name: it asserts a rejected
pair is absent from the candidate list handed to `granger_causality` **and** present in the refusal
ledger with its reason, and that an accepted pair's verdict is the statistical test's alone.
**Acceptance.** Every rejection appears in the refusal ledger with its reason; no pair is dropped
without a record; both series are observed up to `t`; `unavailable` when the candidate universe is
empty.
**Depends on.** P0-3 (H7) refusal ledger; the sector-ETF-to-name pairs the engine already knows.
**Doc caveat.** The paper's setting supplies per-event probability series and natural-language event
titles that do not exist here, its own scale is weak (18 rolling periods, 554 markets), and the
sector-ETF-to-name analogue is a much narrower application than the paper's.

## 2. Item table

| ID | Deliverable | Owner | Phase | Run mode | Gate |
|---|---|---|---|---|---|
| N3 | learned aggregator over labels, confidences and agreement | new, consuming `consensus.py` + `prediction_ledger.py` | P2 | in-run | `enable_learned_aggregator` |
| N1 | event tags, story clustering, per-tag drift prior, width term | new, consuming `cross_section` / `news_score` / `sentiment` | P3 | in-run + offline fit | `enable_news_event_tags` |
| N2 | Item 1A-scoped, volatility-supervised filing sentiment | `strategies/text_factors.py`, `dataflows/sec_edgar.py` | P3 | in-run + offline fit | `enable_filing_sentiment` |
| N4 | five-dimension elicitation with relevance weighting | new, beside `sentiment_score.py` | P3 | in-run, admitted subset only | `enable_multidim_sentiment` |
| N5 | prompt-condition A/B harness | `agents/utils/prompt_metrics.py` | P3 | offline | `enable_prompt_condition_harness` |
| N6 | embedding-based news relevance (compared, not swapped) | `strategies/news_relevance.py` | P3 | in-run | `enable_embedding_relevance` |
| N7 | semantic plausibility screen on lead-lag candidates | new, reusing `statistical.granger_causality` | P3 | offline | `enable_leadlag_plausibility` |

Order within the theme is the design doc's recommended build order: N3, N1, N2, N5, N7, N4, N6 - N6
last, because it compares rather than replaces and should run for a bounded period before any swap.

## 3. Gates added by this plan

| Gate | Item | Enforcement site | Default |
|---|---|---|---|
| `enable_learned_aggregator` | N3 | the new aggregator module, read from the decision path | off |
| `enable_news_event_tags` | N1 | the new tag/cluster module, and the prior read in the news path | off |
| `enable_filing_sentiment` | N2 | `strategies/text_factors.py`, fed by `dataflows/sec_edgar.py` | off |
| `enable_multidim_sentiment` | N4 | the new module beside `strategies/sentiment_score.py` | off |
| `enable_prompt_condition_harness` | N5 | `agents/utils/prompt_metrics.py` | off |
| `enable_embedding_relevance` | N6 | `strategies/news_relevance.py` | off |
| `enable_leadlag_plausibility` | N7 | the new screen in front of `strategies/statistical.py:273` | off |

All seven register at the six points named in [`README.md`](README.md) section 0 rule 6 -
`DEFAULT_CONFIG`, an `_ENV_OVERRIDES` row, a `docs/gate_registry.md` row with an enforcement site, a
`tests/test_gate_env_toggles.py` `REGISTRY` entry, `.env.example`, and a `docs/api_reference.md`
section 1.1 row. Each registration also moves `docs/gate_registry.md`'s coverage sentence.

## 4. Dependencies

**In-theme.** No item in N1-N7 requires another to land first; the design doc's build order is a
preference, not a constraint. Two items read an artefact rather than a sibling: N1's in-run path reads
its own offline drift table, and N6 reads the encoder decision in section 5.

**Cross-theme, by ID only.**

- **P0-3 (H7) refusal ledger -> N7**: the screen's rejections are logged into it, which is what makes
  the screen's precision measurable rather than assumed.
- **P0-1 (H10) coverage window -> N1's offline drift table**: the drift table is a panel statistic
  over a padded or thin window and must report its window or refuse (rule 4).
- **P0-4 (H11) intervals -> N1's `lo`/`hi`**: if the prior's interval is published as a claim, it is a
  claim statistic and takes the block-bootstrap rule, not an IID band.
- **P0-6 (H6) three verdicts -> every finding this theme produces**: a tag at the FDR boundary, a
  filing score resting on `n = 1`, and an embedding comparison with no significance test must all be
  able to come out INCONCLUSIVE.
- **P0-2 (H1) trial ledger -> N5**: a condition sweep is a search, so the number of conditions tested
  is a trial count that comes from the ledger, never from the harness's own assertion.

## 5. Decisions requested (owner)

1. **Do N3 + N1 land first?** The design doc's recommended order puts N3 first (the ingredients
   already exist, the label source already exists, and it is the smallest item in the theme with a
   measured effect: 0.561 to 0.612 balanced accuracy against a 0.573 majority vote) and N1 second (the
   theme's largest result). This plan assumes yes.
2. **May the engine add a hosted-embedding dependency** for N1's tagging and N6's comparison? torch
   2.7.1+cpu is already installed in the interpreter, imported by the engine nowhere, and **not
   declared** - so local tagging is possible only if torch is declared, which makes the
   dependency-profile change explicit rather than accidental. The lower-commitment fallback the design
   doc scopes is 1-2 batched tag calls per symbol-day plus provider embeddings
   ([`README.md`](README.md) section 5 item 8).
3. **Is one release cycle the intended side-by-side window for N2?** Both the dictionary baseline and
   the supervised score are reported together for one release cycle because the paper's claim is
   precisely that they disagree; confirm that `lm_tone` is not retired at the end of it without that
   evidence.
4. **Where does N1's offline drift table live and how is it read?** Rule 8 forbids calling offline
   artefacts from `prepare_initial_state`, `finalize_run` or any agent tool, so the reader path must be
   a stored table loaded as data, not an in-run fit; nominate the artefact's home before N1 lands.
5. **Where is N4's `prompt_version` stored?** The design doc makes storing it a requirement, not a
   nicety, but does not name the field's home; this plan assumes it travels with the score record.

## 6. Honest limits

1. **N1's per-tag table is a prior, and several of its tags sit at the FDR boundary** (Benjamini-
   Hochberg q between 0.05 and 0.07). Reporting a boundary tag as a finding would be exactly the
   over-claim the honesty theme forbids; the prior carries `n_events` and its interval, and the
   background drift is subtracted.
2. **The corpus's text results are the weakest in the survey by evidence quality.** Three of the
   papers here rest on one commodity, one sector, or sixty-nine cells; N1 is the exception, and it is
   descriptive rather than causal by its own statement.
3. **N4's cost is real** - one LLM call per admitted article - and the admission filter is a
   prerequisite, not an optimisation. N6 is a comparison, never a swap on this evidence, and N5
   adopts the harness, not the framing.
4. **Two items (N1, N6) need torch or a hosted encoder**, which changes the engine's dependency
   profile; that is the owner's decision in section 5, not something inherited from a design doc.
5. **Nothing here enters the composite by adjacency.** N1-N7 feed `news_score` and `sentiment_score`,
   which sit outside `COMPOSITE_ENGINES` by the owner's existing decision, and this plan does not
   propose changing that.
6. **None of this was backtested against this engine.** N3's 0.612 is the paper's number on the paper's
   models; the engine's ledger is the only place it can be re-measured, and until then it is untested.
