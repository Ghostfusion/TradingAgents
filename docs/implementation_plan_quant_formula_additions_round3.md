# Scoring & Sentiment Formula Additions, Round 3 — Implementation Plan

Status: **LANDED (2026-09-13) - S1-S11 implemented, each with its own tests
(147 phase tests + 19 wiring tests) and its gate default-off; S9 stays
unscheduled (Appendix A).**
Implements the adopted list in
[`docs/design_quant_formulas_research_round3.md`](design_quant_formulas_research_round3.md)
(items **S1-S11**; **S11** is the orchestration/symmetry item from the
second research pass and is independent of the ten scoring phases). Each phase
names its target files and symbols, the exact
behaviour, the config gate, the tests that must be **proven failing first**, and
the acceptance criteria. Nothing here changes an existing computation: every
item is additive, default-off, and degrades to `unavailable` when its inputs are
missing.

---

## 0. Ground rules (inherited from round 2, non-negotiable)

1. **Deterministic first.** Every formula is a pure function over inputs the
   repo already fetches; no score lives in a prompt.
2. **One implementation per computation.** Extend the module that already owns
   the measure; the design doc's §1 ledger is the exclusion list.
3. **No fabrication.** A missing input yields `unavailable`/`None`, rendered as
   "unavailable". Every score prints its basis (metric set, coverage, variant,
   window). A variant that stands in for a paper's input (e.g. net income for
   "income before extraordinary items") is printed, never substituted silently.
4. **Gates must be able to fail.** Each new test is proven failing under a
   targeted mutation of the code it guards (§4).
5. **Default-off or existing flag.** New behaviour sits behind a config key that
   defaults to off, so a run's outputs cannot change silently.
6. **A score is not a rating.** Nothing in this plan may feed
   `strategies/decision_guardrail.py::SCORE_BANDS`; quality/sentiment composites
   carry their own band tables.
7. **No new vendors, no new models, no execution.** Every item uses the existing
   statement / OHLCV / news / analyst / options / FRED chain. Adding a
   transformer (FinBERT) or a social-media firehose is a **non-goal**.
8. **CHANGELOG + web impact.** Each landed phase gets a CHANGELOG entry; when it
   changes a tool output the sibling web app renders, the entry states the
   **web impact** (additive lines on tool cards; no JSON shape removal).
9. **Symmetry is measured, not assumed.** Any item that changes how evidence is
   gathered also emits a machine-readable symmetry row, and S11's plan call must
   **fall back to today's loop** when the plan is empty, invalid, or outside the
   tool whitelist.
10. **Dark launches are measured, not assumed.** Every gate is env-mappable
    (`_ENV_OVERRIDES` carries all ten, so `TRADINGAGENTS_ENABLE_*` flips it;
    an unmapped name would be silently ignored). A gate stays `False` in
    `default_config.py` until its phase is proven: flip **one** gate at a time,
    in a labelled run, and diff that run against a gate-off run on the same
    basket. Three **pre-existing** scripts do the work: `scripts/repro_check.py
    --evidence` prints the per-run forced-tool evidence and the cross-run
    composition diff; `scripts/report_verify.py --report-dir <tree>` writes that
    tree's `verify_flags.json`; and `scripts/verify_sweep.py` condenses it into
    per-claim verdicts, read-only, exiting 1 on any CONFIRMED/SUSPECT — which is
    what blocks the flip. Only additive, declared lines are acceptable.
    `run_card.json`'s `config_hash` is taken over the **whole** `DEFAULT_CONFIG`,
    so a gate flip already moves it. `scripts/repro_check.py::_config_hash()`
    hashed a fixed 14-key LLM list that did **not** cover the round-3 gates; that
    list now carries all ten, with a test proving the hash moves when a gate
    flips. Naming the flipped gate in the run output remains the operator's step.
    The override is read from the process environment - which until 2026-09-13 was not enough: importing the package
    reloaded the whole `.env` with `override=True` to force the three output-token cap keys, rewriting `os.environ`
    for every other key the file declares. An exported gate was therefore silently replaced by the file's value and
    the ONLY way to flip one was editing `.env`. That reload is now scoped to the three cap keys, so a gate can be
    flipped per run (`TRADINGAGENTS_ENABLE_X=true py -3.12 batch.py --symbols MU ...`) as well as through `.env`, and
    either way the flip moves `run_card.json`'s `config_hash`.

    **Measured flips (2026-09-13; the deployed gather path plus each gate's own tool row, live vendors, MU on
    2026-09-11):**
    - **S1** +2 lines, **S2** +7 lines (`get_quality_factors` / `get_earnings_quality`): the variant + zone + basis
      line, the F detail with its withheld band and the paper's large-cap weak-signal flag. Additive, declared, no
      extra vendor calls. **S8** changes nothing in a run (its consumer is the quality-report script). **S6** flips
      its tool from the DISABLED sentinel to a real read that degrades honestly (coverage guard), 1 call.
    - **S3** adds the quality row but `get_composite_rank` **timed out at the 30 s forced-tool budget** in a full
      run (status `timeout`, thread still draining) - the row was silently absent, so the operator left the gate off.
      Options: raise the per-tool timeout, shrink the peer panel, or accept and declare it.
    - **S10** +9 lines on `get_quality_factors`, no extra calls: the C-Score reads (`3/6 band=middle (risk screen)`,
      with `c5` named as a proxy), while the G-Score can only print `1 of 1 computed signal(s) (7 excluded, not
      scored 0) band=unavailable` - the peer medians come from the screener's own cross-section, not from the tool, so
      7 of 8 legs are excluded by design. Honest, but thin in the report path; the medians need a fetch there before
      the G row carries a band.
    - **S4** rendered `weighted news aggregation unavailable: no usable signed articles.` on the live feed: the
      configured `news_sentiment` chain serves day aggregates, not signed per-article scores, so the row is an honest
      no-op until a score-bearing source is in the chain.
    - **S7** +12 lines (the weighted table, its basis line and `n_history=32 scored days (min_history=30)`), ~2 vendor
      calls. **S5** +1 row (`ratio=78.9 band=crowded-bullish net_share=+0.579 dispersion=0.706 agreement=0.500`,
      display-only and source-labelled), 0 extra calls; the parallel `velocity` sigma moved between runs, but the
      OFF-vs-OFF control moved it by the same amount with `score` and `n` stable - feed drift, not the gate.
    - **S11** measured (MU, live vendors, env-flip per process): **S11b** moves `get_macro_indicators`
      (`indicator=10y_treasury`) out of the news model pool into the gather - 23 -> 24 leaves, pool 4 -> 3, +1 vendor
      call, ~+6 s, and nothing else changed in either direction; **S11a** over the completed run's evidence renders
      `ASYMMETRIC` (6 analyst pairs, 190 differing tool names, 7 persisted rows, **zero vendor calls**, 0.0 ms) - the
      per-side numbers are the usable part, the verdict reads ASYMMETRIC by construction because analysts bind
      different toolsets; **S11d**'s live plan call returned `{}` (`empty plan` -> fallback with the reason, 0 calls
      fired) for all three analyst pools (2.4 s / 1.2 s / 17.1 s), and validation rejects out-of-whitelist, malformed
      and out-of-schema plans with a named reason; the fundamentals gather is byte-identical with the gate on
      (48 leaves, same pool, same block), and the news differences under the gate are feed drift (an OFF-vs-OFF
      control moved the same `get_catalyst_scale` FOMC probability and `get_global_news` URLs).
    - **S11c is wired** (it previously had no reachable operator path): `evidence_symmetry_pairs` /
      `TRADINGAGENTS_EVIDENCE_SYMMETRY_PAIRS` declares the pairs, the live `_journal_executed` path applies the
      shared split rule, and a declared `budget` (or the smallest discretionary count an already-run partner
      recorded) suppresses the surplus **and journals it with its args**. Measured on the real path: budget 1 ->
      surplus suppressed; derived -> mirrors the partner's observed 2; no pair declared -> byte-identical to today.
      Caveat measured: the mirror drops the evidence **leaf** after the call already executed, so the transcript
      still holds that result - keep budgets at or above a pair's natural counts, or the verifier will flag claims
      based on a result the evidence file no longer carries. The S11a row keeps reporting the **planned** set, so the
      pair verdict does not move when the mirror acts.

---

## 1. Phase map

| Phase | Item | Lands in | Config gate | Size | Depends on |
| --- | --- | --- | --- | --- | --- |
| **S1** | Altman variants + distress zones | `dataflows/quantitative_scores.py`, `strategies/normalized.py` | `enable_altman_variants` | S | — |
| **S2** | F-Score paper basis, bands, applicability | `dataflows/quantitative_scores.py`, `strategies/normalized.py` | `enable_f_score_detail` | S | — |
| **S10** | G-Score + C-Score | `dataflows/quantitative_scores.py`, `strategies/cross_section.py` | `enable_growth_scores` | M | peer universe (§1.1, resolved) |
| **S4** | Weighted/unweighted news aggregation | `strategies/sentiment.py` | `enable_weighted_sentiment_agg` | S-M | — |
| **S5** | Crowd ratio, dispersion, extreme bands | `strategies/sentiment.py` | `enable_crowd_ratio_bands` | S | — |
| **S6** | Analyst revision index | `strategies/analyst_revisions.py` (new) | `enable_analyst_revision_index` | S | — |
| **S3** | Composite quality score 0-100 | `strategies/factors.py`, `strategies/cross_section.py` | `enable_quality_composite` | M | peer universe (§1.1, resolved) |
| **S8** | Score evaluation rows (IC/deciles/coverage/stability) | `strategies/alpha_health.py` | `enable_score_eval_rows` | S | S3 or any new score |
| **S7** | Weighted rolling sentiment window + warm-up guard | `strategies/sentiment.py` | `enable_weighted_sentiment_window` | S | — |
| **S11** | Symmetric evidence for paired roles (a: report, b: deterministic default args, c: mirrored budget, d: plan call) | `agents/utils/evidence_gather.py`, `graph/setup.py`, `scripts/repro_check.py` | `enable_evidence_symmetry` | M | independent of S1-S10 |

Landing order: **S1, S2, S10, S4, S5, S6, S3+S8 (together), S7** — the two
correctness fixes first, then the new-coverage score, then the sentiment items
that consume data the pipeline already collects, then the composite **with** its
evaluation rows. **S9 is not in this order** — it is not a phase any more; its
research is Appendix A and §5 records what would reopen it.

S11 is orthogonal to that order and starts with its **no-LLM** steps (S11a
symmetry report, S11b deterministic default args), which can land at any point;
S11c/S11d wait for S11a's measured asymmetry to justify them. Nothing in S11
touches a scoring path, so it can also ship independently of this round.

### 1.1 Resolved decisions (2026-09-13 review pass)

These were open decisions. They are settled here so that no phase can start on a
different assumption than the phase that follows it.

- **Peer universe (S3, S10) — the screener scan universe.** The universe is the
  set the run actually ranked: `scripts/value_screener.py`'s `--universe`
  (default `eodhd-us`: the EODHD US common-stock list after the exchange gate,
  with `--file` and positional tickers overriding), and `--rank composite`
  selects the composite ordering. That is a genuine cross-section (hundreds of
  names), which is what a percentile and a median need. **One resolver** returns
  the metrics panel, the sector labels and the peer count; **S10 lands it** (the
  first consumer) and S3 reuses it — never a second implementation (rule 2).
  S10's industry medians are that universe **partitioned by the existing
  `sector_map` labels** (per-group `min_n=5`), not a separate source.
  **`get_company_peers` is not the universe.** Today's `get_composite_rank`
  builds its peer set as `[ticker] + peers[:8]` from Finnhub — nine names at
  most, which is exactly
  S3's floor before any metric drops out, and too few for a defensible median.
  It keeps its current meaning: the narrow tool-level comparison set.
  Consequence for the order: **no S10 code before the resolver exists**, and S3
  is written against the same resolver.
- **S9 — not scheduled.** Removed from the phase map and from the landing order;
  the research is kept as Appendix A. It reopens only if a market-level consumer
  with a decision path appears (§5), and then with its own phase entry.

---

## 2. Phase detail

### S1 — Altman variants + distress zones

**Target.** `dataflows/quantitative_scores.py`: `altman_z_score` (unchanged,
byte-identical output), `altman_variant(fin, variant)` for
`"z" | "z_prime" | "z_double_prime" | "z_double_prime_em"`, and
`altman_zone(z, variant)` returning `{"zone", "bands", "variant", "basis"}`.
`strategies/normalized.py`: `trap_verdict` renders the zone alongside the raw Z.

**Behaviour.**
- Coefficients and cut-offs exactly as the design doc's S1 table; $Z'$ and $Z''$
  use **book** equity for $X_4$; $Z''$ drops $X_5$; the EM variant adds 3.25.
- Variant selection: `security_type` gates it — operating company →
  `z_double_prime` when the name is not a manufacturer (no inventory/COGS
  economics) and `z` otherwise; financials, funds and CEFs → `unavailable` with
  the reason (the model's own stated limitation).
- Each output prints the variant, the X4 basis (market cap vs book equity, with
  the total-equity proxy named when book equity is absent) and the band table
  used.

**Acceptance.** Hand-computed fixtures reproduce each variant and each zone
boundary (2.99/3.01, 1.22/1.24, 2.59/2.61, 1.09/1.11); a fund ticker returns
`unavailable`; `altman_z_score`'s output for a company fixture is unchanged from
`HEAD`; a missing book-equity field prints the total-equity proxy and does not
silently switch variants.

**Consumers (landed).** `statement_parsing.screen_ticker` computes the gated
variant + zone (via `altman_variant_for`) and the F-Score band, passes both into
`trap_verdict` and exposes `altman_zone` / `altman_variant` / `f_score_band` on
the row; `get_earnings_quality` renders them; the screener's `Trap` column shows
the zone. Gate-off rows keep their previous key set exactly.

### S2 — Piotroski paper basis, bands, applicability

**Target.** `dataflows/quantitative_scores.py`:
`piotroski_f_score_detailed(fin)` returning
`{"score", "signals": {...9 booleans...}, "band", "basis", "deviations"}`;
`piotroski_f_score` keeps its current output. `strategies/normalized.py`:
`trap_verdict` consumes the band.

**Behaviour.**
- Signals 1-9 per the design doc's S2 definitions, with
  `F_ACCRUAL` as the **ratio** test ($CFO>ROA$) and `F_ΔLEVER` as
  $\Delta(\text{LTD+current portion}/\text{average TA})$, each computed from the
  `_prv` chain when both periods are present.
- `band` uses the paper's tested extremes (`low: 0-1`, `high: 8-9`) and prints
  the alternative published conventions it is *not* using (0-2/8-9, 0-3/7-9).
- `deviations` records every substitution (net income for income-before-
  extraordinary-items; ending assets when a beginning value is unavailable) and
  the applicability caveats that are measurable: large-market-cap and
  analyst-covered names carry the paper's weak-signal flag.
- Funds and financials → `unavailable` (no score, no band).

**Acceptance.** Each of the nine signals is exercised in **both** directions on
fixtures; a missing prior period yields the score with `band=None` and a printed
reason; a substitution populates `deviations` (and the test fails if a
substitution is made without recording it); a fund returns `unavailable`.

### S10 — G-Score and C-Score

**Target.** `dataflows/quantitative_scores.py`: `growth_score(fin, medians)`,
`overpriced_score(fin)`; `strategies/cross_section.py`:
`group_median(values_by_key, groups, min_n=5)` and `resolve_peer_universe(...)`
(§1.1), which lands with this phase and is reused by S3.

**Behaviour.**
- $G_1..G_8$ and $C_1..C_6$ exactly as specified, with industry medians from the
  resolved peer universe (§1.1) partitioned by sector; `medians` carries its own
  `n` and the test refuses a peer group below `min_n`.
- Bands printed from the review's Table 9 (`G 6-8 good / 0-2 poor`,
  `C 0-2 good / 5-6 poor`); the C-score is labelled a **risk screen**.
- $G_4/G_5$ need a 5-year annual series — sourced from the SEC XBRL history the
  fundamentals path already reads; fewer years → those two signals are excluded
  from the sum and recorded, never scored 0.
- $G_8$ (advertising intensity) is `unavailable` for the many names whose feeds
  lack the line, and its absence is printed.

**Acceptance.** Hand-computed fixtures reproduce G and C totals and both band
edges; a peer group below the floor returns `unavailable`; a 3-year history
yields a 6-signal G with the two variance signals explicitly excluded; $G_8$
absence is visible in the output.

### S4 — Weighted/unweighted news aggregation

**Target.** `strategies/sentiment.py`:
`aggregate_weighted_sentiment(articles, ticker="", *, window=…, half_life=…,
official_boost=…, min_n=…)` next to `aggregate_daily_sentiment` (which stays
byte-identical), exported through the module's `__all__`; surfaced on
`get_news_sentiment_series` / `get_sentiment_computed`.

**Behaviour.**
- Emits per day: `unweighted` (the published mean of polarity),
  `weighted` ($\sum w_n s_n / \sum w_n$), `n`, `neutral_share` ($|s|<\varepsilon$,
  $\varepsilon$ printed), `dispersion`, and a `basis` line naming the weight
  formula and the fact that relevance is an **unsigned proxy for confidence**,
  not a model probability.
- Defaults: equal weights ⇒ `weighted == unweighted` (proving the default cannot
  change today's numbers); `official_boost` and any decay term default to 1.0
  and 1.0 respectively (the Berkeley team tried and rejected decay).
- Dedupe by normalised headline before counting (syndication), and keep the
  existing close-time → next-session bucketing.
- The output never presents a single-article day as a consensus: `n` is always
  rendered and `weighted` is suppressed (rendered `n/a`) below `min_n`.

**Acceptance.** With equal weights the two aggregations are identical to the
last decimal on a fixture; a duplicate headline does not raise `n`; an
official-source article with high relevance moves `weighted` but not
`unweighted`; a one-article day renders `n=1` with the weighted value withheld;
`aggregate_daily_sentiment`'s output is unchanged from `HEAD`.

### S5 — Crowd ratio, dispersion, extreme bands

**Target.** `strategies/sentiment.py`: `crowd_ratio(bullish, bearish)` →
`{"ratio", "net_share", "band", "basis"}`; `sentiment_dispersion(scores,
weights=None)`; additive rows on `compute_social_scores`.

**Behaviour.**
- `ratio = B/(B+BE)×100`, neutrals excluded; bands `>60 crowded-bullish`,
  `<40 crowded-bearish`, else `neutral`; `B+BE == 0` → `unavailable` (never 50).
- `dispersion` = weighted population std of per-item polarity; `agreement` =
  modal weight share, reusing the existing `consensus_overlap` semantics.
- The rendered line labels the source as **crowd counts (StockTwits/Reddit)**
  and states the bands are display-only, with the source's persistence caveat.

**Acceptance.** The source's worked example (45/30/25 → 60.0, `crowded-bullish`)
reproduces; 0/0 → `unavailable`; dispersion on a two-cluster fixture exceeds a
one-cluster fixture with the same mean; the band never changes a gate verdict
(assert the governor output is byte-identical with the phase on and off).

### S6 — Analyst revision index

**Target.** new `strategies/analyst_revisions.py`: `revision_ratio(history,
weights=(3,2,1), period=21)`, `estimate_change_index(levels, weights=(9,7,5,3))`,
`winsor_z(values, limit=3.0)`; a fundamentals tool row
`get_analyst_revision_index`; `value_dip`'s existing `revision_score` input.

**Behaviour.**
- `revision_ratio` consumes the existing `{up, down}` counts over the last three
  periods and prints its denominator convention (`up+down`, **a deviation** from
  MSCI's analyst-coverage denominator, which the engine cannot observe).
- `estimate_change_index` takes a quarterly estimate-level series: with fewer
  than the required levels it returns `unavailable` **with the reason** (the
  engine has current consensus/PT only).
- Coverage guard: fewer than two distinct actions in the window →
  `unavailable` (a single firm's spree must not move a score).
- `winsor_z` clips at ±3 as MSCI specifies, and the output prints the clip.

**Acceptance.** `revision_ratio` reproduces a hand-computed three-period example
with weights 3/2/1; a one-action window returns `unavailable`; the estimate-change
leg returns `unavailable` with the missing-input reason on the live feed; the
z-clip is visible on a fixture with an outlier.

### S3 — Composite quality score

**Target.** `strategies/factors.py`: `quality_composite(scores_by_ticker, *,
directions, weights=None, min_coverage=…)`; `strategies/cross_section.py`
provides the winsorised z (existing `winsorize` + `cross_sectional_z`).
Screener column; `get_composite_rank` extension.

**Behaviour.**
- Per metric: winsorise (0.01/0.99) → cross-sectional $z$ → apply the metric's
  direction sign; composite $Z$ = mean over present metrics; require
  `|M_i| ≥ min_coverage` of the full metric set, else `unavailable` with the
  count.
- Score = tie-aware percentile of $Z$ in the peer set × 100 (the same percentile
  semantics as `sector_rank._pct_rank`), with the metric set, the directions,
  the per-metric coverage and the peer-set size printed.
- Bands are the **quality** bands (elite/above-average/median/below-average/
  poor/distressed) — explicitly not the decision rating bands.
- `industry_neutral_z` is an opt-in switch, default raw $z$, and the choice is
  printed.

**Acceptance.** A fixture with a known best/worst name ranks them 100/0 and
monotone in between; dropping a metric below `min_coverage` changes the printed
coverage, not the ranking silently; a peer set below the floor returns
`unavailable`; a name missing one metric still scores (renormalised) and the
renormalisation is visible.

### S8 — Score evaluation rows

**Target.** `strategies/alpha_health.py`:
`score_evaluation_rows(scores_by_date, prices, holding=5, n_buckets=10)`
reusing `strategies/sentiment_research.py::rolling_information_coefficient` for
rank IC (no second IC implementation) and the bucket helper semantics of
`quintile_long_short`; consumed by `scripts/strategy_quality_report.py`.

**Behaviour.**
- Rows: mean rank IC and IC IR; decile mean forward returns + a monotonicity
  flag; `coverage` (scored / universe); `stability` (rank autocorrelation of
  consecutive snapshots); each row prints its `n` and the holding period.
- Row emitted only above a minimum observation count; below it →
  `unavailable` with the count.
- The rendered block states that these rows are **inputs to** DSR/PBO, never a
  standalone verdict.

**Acceptance.** A synthetic score that is a perfect rank transform of forward
returns yields decile means monotone and IC ≈ 1; a random score does not;
coverage is computed on a panel with a deliberately missing name; a short panel
returns `unavailable` with the count.

### S7 — Weighted rolling sentiment window

**Target.** `strategies/sentiment.py`:
`weighted_rolling_sentiment(points, window=10, *, exponential=True,
min_history=…)`, reusing `daily_sentiment_sma`'s calendar reindexing and
close-time cutoff.

**Behaviour.**
- Weights $e^{\text{linspace}(0,1,K)}$ normalised, most recent = 1, applied over
  the calendar-reindexed daily series (missing days carry no score, not a zero).
- `min_history` (default 30 days, the production contract's warm-up) is a
  parameter; below it the function returns `unavailable` with the observed
  history length.
- The 7d SMA path stays byte-identical; both are rendered side by side so a
  reader can see the weighting's effect.

**Acceptance.** On a fixture with a recent spike the weighted value exceeds the
unweighted SMA and both are printed; a 12-day history with
`min_history=30` returns `unavailable`; the existing SMA output is unchanged.

### S11 — Symmetric evidence for paired roles

Split into four steps so the cheap, non-LLM parts land first and the plan call
exists only if the measurement justifies it. S11 changes *how evidence is
gathered*; it does not change how anything is scored.

**S11a - Symmetry report (no LLM, no new vendor calls).**

*Target.* `agents/utils/evidence_gather.py::symmetry_report(evidence, model_pool)`;
`scripts/repro_check.py --evidence` renders it.

*Behaviour.* Per analyst/role pair: planned vs fired vs leaves vs `unavailable`,
the arg-**key** diff across the pair, the as-of dates, and the discretionary
counts read from `_model_pool`. One verdict line - `SYMMETRIC` or
`ASYMMETRIC - differs on: <tools>` - plus the differing tool names. The same
block is written into the run's evidence file and the debate state so the web
panel can render it.

*Acceptance.* A fixture pair with one extra tool on side A reports `ASYMMETRIC`
and names it; an equal pair reports `SYMMETRIC`; a pair with no leaves renders
`unavailable` rather than `SYMMETRIC`; the report itself makes **zero** vendor
calls (asserted by a call counter, not by inspection).

**S11b - Deterministic default args (no LLM).**

*Target.* `evidence_gather.CONTEXT_ARG_KEYS` / `_args_for`, plus declared
per-tool defaults for enumerable args.

*Behaviour.* Where a model-pool tool has a defensible enumerable default (e.g.
`indicator`), the default is declared and the tool moves into the deterministic
gather, so composition becomes deterministic for free. A tool with no defensible
default **stays** in the model pool - an arg is never invented to force a tool
in.

*Acceptance.* A fixture tool with a declared default moves pool with its reason
printed; a tool without one stays; the forced leaf set is byte-identical for a
single-valued enum.

**S11c - Mirrored discretionary budget (no LLM change).**

*Target.* the analyst tool-loop / `_journal_executed` path.

*Behaviour.* Each paired role gets the same discretionary call allowance; a
surplus call beyond the mirror is suppressed **and journaled with its args**, so
the asymmetry is visible rather than hidden. The mirror is per pair, not global.
The allowance is read from the declared pair specs (`evidence_symmetry_pairs` /
`TRADINGAGENTS_EVIDENCE_SYMMETRY_PAIRS`, a JSON list of `{roles, budget}`): a
declared `budget` is used verbatim, otherwise the mirror binds to the smallest
discretionary count an **already-run** partner recorded. With no declared pair
the mirror is inert, so a gate-on run is byte-identical to a gate-off one, and
the split rule itself is shared (`_split_discretionary`) with the pair-level API
so the two call sites cannot drift.

*Acceptance.* Three discretionary calls on side A against one on side B produce
journal entries for the two unmatched A calls plus an `ASYMMETRIC` symmetry row;
the mirrored case is clean; suppression never drops a forced (S11b) leaf.

**S11d - Argument-plan call + pre-debate assertion (LLM, gated off).**

*Target.* `gather_for_analyst_node` (the plan stage) and a `graph/setup.py`
pre-debate node.

*Behaviour.* One cheap completion per analyst emits a typed
`{tool: {arg: value}}` plan over the model-pool remainder, validated against each
tool's own args schema and against a tool whitelist; code then fires it through
the existing executor (bounded parallel, per-call timeout, error leaves) into the
same `tool_evidence` reducer. An empty, invalid or out-of-whitelist plan
**falls back to today's loop** and says so in the run output. The pre-debate node
asserts the symmetry contract (same whitelist, same arg keys, mirrored counts)
and records the verdict; it never blocks a debate - it labels one.

*Acceptance.* A plan is journaled and the fired leaves match it 1:1; an invalid
plan leaves the run on the legacy path with a stated reason, and with the gate
off the run's outputs are unchanged from `HEAD`; the assertion writes
`SYMMETRIC`/`ASYMMETRIC` into the debate state without altering any verdict.

---

## Appendix A — S9: reduced BW-style market sentiment index (**not scheduled**)

Kept so the research is not lost. This is **not** a phase: it has no row in the
phase map, no position in the landing order, and no gate until the reopening
condition in §5 is met.

**Target.** new `strategies/market_sentiment_index.py`:
`bw_style_index(proxies_by_date, macro_by_date, min_proxies=…)` with an internal
pure `_pc1(matrix)` (numpy is already a dependency of `sentiment_research`).

**Behaviour.**
- Standardise each proxy → regress on the macro set (industrial production,
  consumption, employment, recession dummy — all FRED) → PC1 of the residual
  correlation matrix → sign-normalise so higher = sentiment; print loadings,
  variance explained, proxy names **and the five published proxies that are
  missing** (IPO count, IPO first-day returns, equity share in new issues,
  dividend premium, CEF discount).
- Fewer than `min_proxies` available → `unavailable` (never a one-proxy
  "index"); the annual frequency and one-year effective lag are printed with the
  output, and the index is explicit that it is **not** the BW index.

**Acceptance.** On a synthetic 4-proxy panel with a planted common factor, PC1
recovers it and the sign convention is stable across reruns; with one proxy the
function returns `unavailable`; the loadings and missing-proxy list are rendered.

---

## 3. Cross-cutting wiring

| Surface | Change |
| --- | --- |
| `tradingagents/default_config.py` | ten `enable_*` keys from §1, all `False` |
| `strategies/sentiment.py::__all__` | the three new sentiment functions |
| Peer universe | `strategies/cross_section.py::resolve_peer_universe` (§1.1) — shared by S3 and S10, prints the peer count and the sector partition; the screener columns read it |
| Rule-10 tooling | `scripts/repro_check.py --evidence`, `scripts/report_verify.py --report-dir <tree>`, `scripts/verify_sweep.py` — all pre-existing and test-covered (`tests/test_repro_crosscheck.py`, `tests/test_report_verify.py`, `tests/test_verify_sweep.py`), so no rule depends on unwritten code. Caveat found on inspection: `verify_sweep.py`'s own docstring advertises a `scripts/report_verify.py --verify` flag that **does not exist** (`report_verify` takes `--report-dir`, `--model`, `--provider`, `--max-calls`, `--stem`) — use the real flag, and correcting that docstring is a small standalone fix, not part of a phase |
| Tools | S1/S2/S10 rows on the existing fundamentals tools; `get_analyst_revision_index` (S6); `get_composite_rank` gains the quality score (S3); S4/S5/S7 rows on `get_news_sentiment_series` / `get_sentiment_computed` |
| Screener | G/C columns (S10), quality composite (S3), revision index (S6) |
| `scripts/strategy_quality_report.py` | S8 rows |
| `docs/api_reference.md` | the new keys and tools in the canonical tables **in the same commit** |
| `docs/developer/04-strategies.md`, `Strategies/index.md` | module/flag/consumer rows per phase |
| Sibling web app | additive tool-card lines only; **web impact** stated per CHANGELOG entry (no JSON shape removal, no CLI flag change) |
| S11 | `enable_evidence_symmetry` in `default_config.py`; `repro_check --evidence` gains the symmetry columns; the debate panel renders the symmetry row; `docs/api_reference.md` gets the key and the `symmetry_report` shape |

---

## 4. Test and mutation matrix

| Phase | Test file | Gates | Mutations that must break them |
| --- | --- | --- | --- |
| S1 | `tests/test_altman_variants.py` | each variant's hand-computed value; every zone boundary; fund → `unavailable`; X4 basis printed; `altman_z_score` unchanged | use market cap for the variants' X4; keep X5 in Z''; shift a cut-off by 0.01; drop the fund guard |
| S2 | `tests/test_piotroski_basis.py` | nine signals both directions; band edges; missing prior → no band; deviations recorded; fund → `unavailable` | score `F_ACCRUAL` on raw NI instead of the ratio; clamp a missing signal to 0; assign a band without both periods |
| S10 | `tests/test_growth_scores.py` | G/C totals and band edges; peer floor; 6-signal G with variance legs excluded; G8 absence visible | substitute a sector mean for the median; count a missing signal as 0; accept a 4-name peer group |
| S4 | `tests/test_sentiment_weighted_agg.py` | equal-weight identity; dedupe; official boost moves weighted only; `n=1` withholds the weighted value; legacy output unchanged | drop the dedupe; apply the boost to the unweighted mean; emit a weighted value below `min_n` |
| S5 | `tests/test_sentiment_crowd_ratio.py` | worked example 45/30/25 → 60; 0/0 → `unavailable`; dispersion ordering; governor output unchanged | include neutrals in the denominator; fall back to 50 on 0/0; let the band influence a verdict |
| S6 | `tests/test_analyst_revision_index.py` | 3-period weighted ratio; one-action window → `unavailable`; estimate leg `unavailable` with reason; ±3 clip | flatten the weights; drop the coverage guard; fabricate estimate levels |
| S3 | `tests/test_quality_composite.py` | best/worst → 100/0; monotone fixture; coverage-floor behaviour; renormalisation visible; peer floor | skip winsorising; average over the full metric set when one is missing; use the decision rating bands |
| S8 | `tests/test_score_eval_rows.py` | perfect-rank score → monotone deciles + IC≈1; random score → not monotone; coverage on a short panel; min-obs floor | compute IC on the score's own sign only; bucket with a fixed width instead of rank; report coverage as always 1.0 |
| S7 | `tests/test_sentiment_rolling_window.py` | recency spike > unweighted SMA; `min_history` guard; SMA path unchanged | weight the oldest observations highest; zero-fill missing days; ignore `min_history` |
| S9 (Appendix A) | `tests/test_market_sentiment_index.py` | planted common factor recovered; sign stable; one proxy → `unavailable`; missing-proxy list rendered | skip the macro orthogonalisation; return a one-proxy index; flip the sign convention between runs |
| S11 | `tests/test_evidence_symmetry.py` | asymmetric fixture → `ASYMMETRIC` + the named tool; equal → `SYMMETRIC`; no-leaf pair → `unavailable`; zero vendor calls in the report; a declared-default tool moves pool; the mirrored budget journals the surplus; an invalid plan falls back with a reason; gate off → run output unchanged | count leaves but not planned tools; drop the budget mirror; let an invalid plan raise; let the plan fire outside the whitelist; report `SYMMETRIC` when a side has no leaves |

Every test file is proven failing under its mutation list before the phase is
considered landed, and the full suite plus `py -3.12 -m ruff check tradingagents/
tests/` must be green per commit.

---

## 5. Risks, non-goals, and open decisions

- **Risk: proxy-by-convenience.** S4's relevance weighting and S6's
  `up+down` denominator are *substitutes* for inputs the sources actually use
  (model confidence; analyst coverage). Mitigation is contractual: the output
  prints the substitution, and the two comparisons (weighted vs unweighted;
  engine ratio vs MSCI ratio) ship side by side.
- **Risk: composite scores invite over-reading.** A 0-100 quality score with
  bands looks authoritative. Mitigation: S3 ships **with** S8's rows, the
  coverage line, and the explicit statement that the composite is not a rating.
- **Risk: peer-set dependence.** Both S3 and S10 are cross-sectional; a small or
  stale peer set makes them meaningless. Both carry a floor and print the peer
  count, and §1.1 fixes *which* set that is.
- **Risk: new coverage widens the asymmetry surface S11 measures.** The pool
  split is derived from each tool's own schema (rule 9), so every new tool row
  joins one of the two pools automatically — and the rows added here (S1/S2/S10
  on the fundamentals tools, S6's `get_analyst_revision_index`, S4/S5/S7 on the
  sentiment tools, S3's `get_composite_rank` extension) are exactly the
  multi-arg, model-fed kind that lands in the model pool. Measured after this
  landing: **215** `@tool` functions repo-wide, **199 bound** across the three
  analysts (market 115: 87 gather / 28 model; news 27: 23/4; fundamentals 57:
  48/9 over the company+ETF union) — i.e. **41 model-pool tools** catalog-wide,
  unchanged: the new S6 tool takes only run-context args (ticker + date), so it
  landed in the **gather** pool, and no round-3 row added a model-discretionary
  argument. Not a reason to slow down,
  but a real interaction: a new tool must either take args the gather context
  supplies or be counted in the S11a symmetry row, and S8's coverage rows are the
  other half of the measurement (a score nothing fires is visible there).
- **Risk: sentiment scores are uncalibrated.** The research is explicit that
  FinBERT-style probabilities are not calibrated and that buzz predicts
  volatility rather than sign. No item here may gate a decision on a sentiment
  level; the existing opt-in overlay IC gate stays the only path from sentiment
  to sizing.
- **Risk: display-only bands drift into gates.** The crowd bands (S5) and the
  Piotroski large-cap/analyst-coverage flags (S2) are display-only by contract;
  a phase that later wants to gate on them must bring its own out-of-sample
  evidence.
- **Non-goals.** No transformer/FinBERT dependency; no social-media firehose; no
  ML replacement of the additive scores; no new vendor; no change to the
  decision rating contract; no re-implementation of anything in the design
  doc's §3 exclusion table.
- **Risk: the plan call becomes a new single point of failure.** An empty,
  invalid or out-of-whitelist plan must fall back to today's loop; the plan is
  journaled so `repro_check` can diff it, and the gate defaults off.
- **Risk: symmetry mistaken for correctness.** Equal tool access does not make two
  arguments equally good, and forcing equal *conclusions* would destroy the
  debate. S11 mirrors access and budgets only, and never gates a verdict; the
  existing order rotation and pre-debate independent stances stay the
  countermeasures for the anchoring half (`arXiv:2406.07791`).
- **Non-goal: binding tools to the debaters.** Both sides read one shared report
  set today; giving them their own tools would *create* the per-side selection
  imbalance S11 exists to remove.
- **Decision (resolved 2026-09-13): the peer universe is the screener scan
  universe** (§1.1) — one resolver, landed by S10 and reused by S3; S10's medians
  are that universe partitioned by the existing `sector_map` labels. The earlier
  second option ("the sector map's constituents") was not buildable as written:
  `sector_map` is a ticker→sector *label* dict, and the repo has no constituent
  resolver — which is why the partition is the correct reading of it.
- **Decision (resolved 2026-09-13): S9 is not scheduled.** It is macro-level,
  annual, one-year-lagged and reduced-proxy, so it cannot inform a daily decision;
  the research is kept as Appendix A so it is not lost. It reopens only if a
  market-level consumer with a decision path appears — and then as its own phase
  with its own gate.

---

## 6. Verification per landed phase

1. New tests written, then **proven failing** with the mutation applied and reverted.
2. Affected subset run, then the full suite
   (`py -3.12 -m pytest tests/ -q -p no:cacheprovider`) plus
   `py -3.12 -m ruff check tradingagents/ tests/`.
3. `docs/api_reference.md` updated for any new key or tool in the same commit.
4. CHANGELOG entry with the web impact when a consumed output changes.
5. `Strategies/index.md` and `docs/developer/04-strategies.md` rows updated.
6. Commit + push per phase; no phase is left partially landed.
