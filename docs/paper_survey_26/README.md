# Paper-Survey Adoption - Index

Status: **IN PROGRESS - wave 0 (P0), the wave-1 state reads and the nine T1 items have landed (2026-09-24); the rest is not started.**
25 of the 44 buildable items are built, proved and pushed - the six P0 honesty instruments (H10, H1, H7, H11,
H4, H6), ten P1 state reads (R1, R3, R7, V6, V2, K3, V4, X3, X6, X8) and the nine T1 items (K2, R2, K1, H2, X2,
V3, V5, R5, N5) - each behind its own default-off gate with its failing-first proof, its `CHANGELOG.md` entry
and its `docs/gate_registry.md` row. Each was proved by mutating the source and watching its named test fail,
with the source restored byte-identical. **K2 landed REPORT-ONLY:** its `T^(H-1/2)` rescaling reaches the
strategy-evaluation row and the governor leg stays square-root-of-time, so the mandate question in decision 3
is still open. R3's in-run panel glue is the one landed read still dormant, and that is decision 2.
**Date:** 2026-09-24
**Survey:** [`../design_fin_paper_survey_26.md`](../design_fin_paper_survey_26.md) - v1.0 SURVEY, 309 papers read
(31 high / 111 medium / 124 low / 43 none relevance).
**Scope:** the six themed design docs derived from that survey, the six implementation plans that
sequence them, and the shared rules the six plans inherit.

This folder holds the adoption set. Each theme pairs one design doc (which owns the argument, the
paper evidence and the alternatives it declined) with one implementation plan (which owns the
sequence, the gates, the failing-first tests and the acceptance criteria). **This file owns what is
shared**: the ground rules, the measured dependency surface, the cross-theme phase map, the
dependency graph, the run-budget split, the open decisions and the landing protocol. The plans do
not restate any of it.

| Theme | Design doc | Implementation plan | Items | Gates |
|---|---|---|---|---|
| Honest evaluation | [`design_research_honesty_gates.md`](design_research_honesty_gates.md) | [`implementation_plan_research_honesty_gates.md`](implementation_plan_research_honesty_gates.md) | H1-H11 | 10 |
| Regime and state | [`design_regime_estimation_hardening.md`](design_regime_estimation_hardening.md) | [`implementation_plan_regime_estimation_hardening.md`](implementation_plan_regime_estimation_hardening.md) | R1-R9 | 5 + 1 extension |
| Risk and tails | [`design_risk_tail_and_coverage.md`](design_risk_tail_and_coverage.md) | [`implementation_plan_risk_tail_and_coverage.md`](implementation_plan_risk_tail_and_coverage.md) | K1-K6 | 4 |
| Volatility and options | [`design_vol_surface_and_vrp.md`](design_vol_surface_and_vrp.md) | [`implementation_plan_vol_surface_and_vrp.md`](implementation_plan_vol_surface_and_vrp.md) | V1-V8 | 5 |
| Cross-section and allocation | [`design_cross_section_and_allocation.md`](design_cross_section_and_allocation.md) | [`implementation_plan_cross_section_and_allocation.md`](implementation_plan_cross_section_and_allocation.md) | X1-X8 | 3 |
| Text, news, disclosure | [`design_news_and_filing_signals.md`](design_news_and_filing_signals.md) | [`implementation_plan_news_and_filing_signals.md`](implementation_plan_news_and_filing_signals.md) | N1-N7 | 7 |

**49 items, 44 buildable, 5 recorded-only or constraint-only** (R8, R9, V7, V8, K6).
**34 new config gates**, plus one extension of an existing one (`enable_bocpd`, for R1).

**Rule-4 impact: none.** Nothing in the set adds a tool, a CLI flag, a gate the sibling app reads,
or a JSON shape change. Each plan states its own impact line, and any item that later does touch the
externally visible surface must state its web impact in its own CHANGELOG entry.

**Anchor check.** Every `file.py:LINE` anchor the six design docs cite was re-verified against the
tree before the plans were written: **44 of 44 held**. Line numbers move; re-grep before acting on
any of them.

---

## 0. Ground rules (inherited, non-negotiable)

1. **Measurement before adoption.** P0 is the instrument, not a signal. The survey's own thesis is
   that this corpus hands the engine "an audit standard, a set of coverage-aware estimators, and a
   repeated reminder that the volatility-and-structure channels are forecastable while the return
   channel mostly is not". A phase that adds a score before P0 lands is adopting an untested claim.
2. **One producer per derived quantity.** No item may become a second authority beside an existing
   one. Three items are explicitly constrained by their own docs and are the ones most likely to
   violate this: **K4** (must not sit beside `ledoit_wolf_shrink`), **X5** (must *replace*
   `resolve_peer_universe`'s label resolver, not add to it), and **H10** (a *reader* of the loaded
   frame, not a second data-quality authority).
3. **Nothing enters the composite by adjacency.** `COMPOSITE_ENGINES` stays
   `(fundamental, technical, regime, risk)`. No item in the six docs proposes a member change;
   several propose inputs to an existing member's components. That distinction is the difference
   between a signal and a state read, and the plans keep it.
4. **Coverage travels with the number.** Missing data is `unavailable`, never zero. Every item that
   can be computed over a padded or thin window must report the window (H10 is the mechanism) or
   refuse.
5. **Gates must be able to fail.** Each new test is proven failing under a targeted mutation of the
   code it guards. Tests assert observable behaviour, never wiring or source text.
6. **Six registration points per gate**: `DEFAULT_CONFIG`, an `_ENV_OVERRIDES` row, a
   `docs/gate_registry.md` row with an enforcement site, a `tests/test_gate_env_toggles.py`
   `REGISTRY` entry, `.env.example`, and a `docs/api_reference.md` section 1.1 row (regenerate with
   `scripts/gen_api_reference_table.py --write`). Registering a gate also moves the coverage
   sentence in `docs/gate_registry.md`.
7. **A new public function in `strategies/` or `dataflows/` ships with its first caller in the same
   commit**, or
   `tests/test_calc_agent_wiring.py::test_public_calc_reachable_or_whitelisted` fails.
   Underscore-prefixed names are exempt; tests do not count.
8. **Offline artefacts are not in-run producers.** Items marked OFFLINE may not be called from
   `prepare_initial_state`, `finalize_run`, or any agent tool.

---

## 1. The dependency surface, measured (2026-09-23)

Cost estimates in the six docs assume a numerical stack. Measured against the interpreter that runs
this engine (`py -3.12`, Python 3.12.10):

| Package | Installed | Declared in manifest | Directly imported by the engine |
|---|---|---|---|
| numpy | 2.2.6 | yes (was not - fixed) | yes (5 modules) |
| scipy | 1.15.3 | yes (was not - fixed) | yes (2 modules) |
| pandas | 3.0.5 | yes | yes |
| networkx | 3.5 | no | no |
| numba | 0.61.2 | no | no |
| matplotlib | 3.10.3 | no | no |
| torch | 2.7.1+cpu | no | no |
| sklearn | **absent** | no | no |
| statsmodels, arch, hmmlearn, ruptures | absent | no | no |

### 1.1 One defect, already fixed

`tradingagents/strategies/statistical.py:18` does `from scipy import stats` and `:19`
`from scipy.special import betainc`; `sentiment_research.py:27` does the same. That module is
reached at runtime from **12 sites in `agents/utils/analysis_tools.py`** and from
`strategies/lottery.py:74` - the analyst tool surface, not dead code.

**Neither numpy nor scipy was declared.** A clean install of the declared manifest resolves **no
scipy at all**: every scipy edge from a declared dependency is extras-gated
(`pandas -> scipy>=1.14.1; extra == "computation"`, `yfinance -> scipy>=1.6.3; extra == "repair"`,
`networkx -> scipy>=1.11.2; extra == "default"`), and the only packages requiring scipy
unconditionally in this environment (`PyMatting`, `albumentations`, `colour-science`, `rembg`,
`scikit-image`) are image packages the engine does not depend on. numpy arrives transitively
(`pandas`, `stockstats`) but is still imported directly and undeclared.

Fixed: `numpy>=1.26.0` and `scipy>=1.11.2` declared in both `pyproject.toml` and
`requirements.txt`. The floors are conservative on purpose - the API surface in use is
`np.array` / `np.linalg` / `np.asarray` and `scipy.stats` / `scipy.special.betainc` /
`scipy.optimize`, all long-stable, and no numpy-2-only API is used. **This is why P0 needs no new
dependency**: the honesty instruments are numpy + scipy work.

### 1.2 sklearn is absent, and three items need it or a hand-rolled equivalent

| Item | Needs | Consequence |
|---|---|---|
| X2 | an L1 solver for double-selection | scipy has no LASSO. Add sklearn, or implement the selection half in-house (~80 lines) - the doc only needs a survivor list. |
| X5 | a fitted gradient-boosted tree | leaf co-occurrence needs a fitted tree. `sklearn.ensemble.GradientBoostingRegressor` is the small option. |
| K4 | a trained encoder | already deferred pending a training pipeline. Unchanged. |
| V1 | three ML forecasters | the doc's own architecture; sklearn or the engine's existing regressions. |

**Decision requested** - see section 5, item 7.

### 1.3 torch is installed but undeclared, and it changes two items' cost

**torch 2.7.1+cpu is already installed** in this interpreter (pulled in by side packages the engine
does not declare), and the engine imports it nowhere. So N1's story clustering and N6's relevance
comparison *can* run locally without a hosted endpoint - but only if torch is **declared**, which
makes the dependency-profile change explicit rather than accidental. The news doc's fallback
(1-2 batched LLM tag calls per symbol-day, embeddings from an existing provider) remains the
lower-commitment option. **Decision requested** - see section 5, item 8.

### 1.4 tsbootstrap exists and matches the H11 claim

2607.06690's library is real and public: block, residual, sieve and wild bootstrap plus adaptive
conformal calibrators (EnbPI, ACI, NexCP, AgACI) behind one typed API. H11 does **not** require it -
a moving-block bootstrap for a claim statistic is ~30 lines over numpy, and the block length already
has a stated rule (lag-1 autocorrelation plus an ADF check). Adopting the library buys the conformal
calibrators, which are the part H11 wants for the paired band. **Decision requested** - item 9.

### 1.5 Nothing else in the corpus needs a new package

GPH log-periodogram and local Whittle (V2), Marchenko-Pastur bounds (X3, V5), projector distance and
absorption ratio (R3), `Tr(A^3)` (R7), NNLS (H9), Kupiec/Christoffersen coverage tests (R2), an fBm
drawdown table (K2), and the realized-measure proxies (V6) are all numpy/scipy work at this engine's
scale.

---

## 2. Phase map

Sizes: S = under a day, M = one to three days, L = a week or more.

| Phase | Leads with | Items | Run mode | Size | Depends on |
|---|---|---|---|---|---|
| **P0** | the six measurement instruments | H10, H1, H7, H11, H4, H6 | in-run | S-S | - |
| **P1** | zero-new-data state reads | X3, X6, V6, V2, R1, R3, R7, K2, K3, X8, V4 | in-run, except X6 (offline study) | S | P0's H10 for the panel items |
| **P2** | composite reads over existing producers | K1, R2, N3, K5, H2 | in-run | M | P0 (H11's intervals for the coverage test), P1 |
| **P3** | new producers, mostly with an offline fit | H5, H8, H9, N1, N2, N4, N5, N6, N7, R4, R5, X2, X5, X7, V3, V5 | mixed | M-L | P0 + P1 |
| **P4** | offline and panel-scale | H3, X1, X4, R6, V1, K4 | OFFLINE | L | H1's ledger; for R6, the onset panel |

P0 leads because the survey's largest transferable theme is honest evaluation, because these six
items are the cheapest in the whole set, and because they decide whether the later items deserve to
land at all. Each is independently landable.

Landing rule: **one item per commit**, each with its own CHANGELOG entry and its own failing-first
proof. A phase is complete when every item in it is either landed or explicitly deferred in writing.

### 2.1 Difficulty order (an estimate, not a schedule)

The phase map above is a **priority** order: the instruments first, because they decide whether the
later items deserve to land at all. This is the same 44 buildable items sorted by **cost**, which is a
different question; the two orders agree at the ends and disagree in the middle. Sizes use §2's own
scale (S = under a day, M = one to three days, L = a week or more).

Difficulty is estimated from four measurable things rather than from the paper's importance: **(a)**
how much surface the item touches - one function in an existing host is smaller than a new module plus
its callers; **(b)** whether it needs data or a dependency the engine does not hold; **(c)** whether it
can change a live decision (size, governor, admission); **(d)** whether it needs an offline fit, a
panel job, or the replacement of an existing producer. Within a tier the order is judgement; the tier
is the signal. Nothing here was re-measured against the engine - it is a reading of the cards.

**T0 - built (16).** The six P0 instruments and the ten P1 state reads. Every one is a single module or
a single function over numpy and scipy, with no new data source. They went first because they are the
cheapest items in the set, which is also why the plan sized P0 and P1 at S - and it is the reason the
remaining work is genuinely harder, not merely later.

| # | Item | What it is | Phase | Gate | Status |
|---|---|---|---|---|---|
| 1 | X6 | forward-rank study over the existing liquidity estimators | P1 | none (offline study) | built |
| 2 | R1 | duration-law hazard on `bocpd` plus the covering metric | P1 | extends `enable_bocpd` | built |
| 3 | V6 | jump-robust daily-bar proxies; a tail read that names its source | P1 | `enable_jump_robust_proxies` | built |
| 4 | V4 | pre-event ATM IV shape, indexed in event time | P1 | `enable_event_iv_lift` | built |
| 5 | K3 | cross-strike risk-neutral skew proxy | P1 | `enable_rn_skew_proxy` | built |
| 6 | X3 | Marchenko-Pastur lower-spectrum count | P1 | `enable_mp_lower_spectrum` | built |
| 7 | X8 | spectral excess mass and cost-optimal span | P1 | `enable_trend_spectral` | built |
| 8 | H10 | coverage window, and the refusal it licenses | P0 | `enable_coverage_window` | built |
| 9 | R7 | triadic stress index and epicentre | P1 | `enable_triadic_stress` | built |
| 10 | V2 | memory parameter beside a HAR forecast | P1 | `enable_long_memory` | built |
| 11 | H4 | R-squared ceiling and excess accuracy | P0 | `enable_accuracy_ceiling` | built |
| 12 | H7 | refusal ledger and save-to-miss ratio | P0 | `enable_refusal_ledger` | built |
| 13 | H1 | trial ledger and dispersion-aware deflation | P0 | `enable_trial_ledger` | built |
| 14 | R3 | spectral null band (landed; its in-run glue is still dormant) | P1 | `enable_spectral_null_band` | built |
| 15 | H6 | three-way verdict and family FDR | P0 | `enable_materiality_verdict` | built |
| 16 | H11 | autocorrelation-aware intervals and information gap | P0 | `enable_bootstrap_intervals` | built |

**T1 - small, unblocked, numpy and scipy only (9 - all built 2026-09-24).** One host module each, no new data
source, no new dependency, no fitted model.

| # | Item | What it is | Phase | Gate | Status |
|---|---|---|---|---|---|
| 17 | K2 | four drawdown expectations and the right time-scaling | P1 | `enable_drawdown_envelope` | built - report-only |
| 18 | H2 | availability-typed factor DSL gate (registration-time, free) | P2 | `enable_factor_availability_gate` | built |
| 19 | X2 | redundancy screen over components (a scheduled script) | P3 | none (scheduled script) | built |
| 20 | V3 | RND recovery, only when it is identifiable | P3 | `enable_rnd_recovery` | built |
| 21 | V5 | eigenspace rotation as a state variable, with the MP check | P3 | `enable_eigen_rotation` | built |
| 22 | R2 | heavy-tailed emissions and a coverage-tested VaR | P2 | `enable_hmm_heavy_tails` | built |
| 23 | R5 | calibrated forward stress probability from the cross-section | P3 | `enable_forward_stress_probability` | built |
| 24 | K1 | a tail number that carries its quality and uncertainty | P2 | `enable_tail_risk_layer` | built |
| 25 | N5 | prompt-condition A/B harness | P3 | `enable_prompt_condition_harness` | built |

Landed in six commits, because three pairs share a file: K2+R2+K1 all write
`strategies/book_risk.py`, and H2+X2 both write `strategies/alpha_zoo.py` - the same reason H10+K3+X8 shared
one in wave 0. What each item decided, and the limits it states, are in its `CHANGELOG.md` entry.

**T2 - medium: a new module plus a fit or an LLM stage (9).**

| # | Item | What it is | Phase | Gate | Status |
|---|---|---|---|---|---|
| 26 | H9 | report attribution and factor novelty | P3 | `enable_report_attribution` | not started |
| 27 | H5 | five-gate verdict, positive controls, next-open variant | P3 | `enable_rule_policy_gates` | not started |
| 28 | N3 | learned aggregator over labels, confidences and agreement | P2 | `enable_learned_aggregator` | not started |
| 29 | N6 | embedding news relevance, compared not swapped | P3 | `enable_embedding_relevance` | blocked - encoder decision |
| 30 | N4 | five-dimension elicitation, relevance-weighted | P3 | `enable_multidim_sentiment` | not started |
| 31 | N2 | Item 1A-scoped, volatility-supervised filing tone | P3 | `enable_filing_sentiment` | not started |
| 32 | X7 | relation-classified peer edges | P3 | `enable_peer_edge_classifier` | not started |
| 33 | N7 | semantic plausibility screen on lead-lag candidates | P3 | `enable_leadlag_plausibility` | not started |
| 34 | H8 | vintage/lag guard and the non-LLM comparator | P3 | `enable_vintage_guard` | blocked - vintage store |

**T3 - large: an offline fit, a panel job, or a replacement (10).**

| # | Item | What it is | Phase | Gate | Status |
|---|---|---|---|---|---|
| 35 | R4 | shift-date proposer plus an LR-VAR validator | P3 | `enable_regime_shift_proposer` | needs a policy corpus |
| 36 | X1 | volatility-rank transition chain | P4 | none (weekly offline job) | not started |
| 37 | X4 | eigenmode variance ratio by horizon | P4 | none (weekly offline job) | not started |
| 38 | N1 | event tags, story clustering and a per-tag drift prior | P3 | `enable_news_event_tags` | not started |
| 39 | X5 | valuation-anchored peer weights (a replacement, not a sibling) | P3 | none (replacement) | needs a fitted tree |
| 40 | K4 | covariance from characteristics on the ragged path | P4 | none (deferred) | blocked - training stack |
| 41 | V1 | volatility forecast pool and regime-similarity routing | P4 | none (needs the state vector) | blocked - VXV and HY spread |
| 42 | R6 | the gate every early-warning indicator must pass | P4 | none (gate module) | blocked - no onset panel |
| 43 | H3 | synthetic-null workflow falsification | P4 | none (offline harness) | needs 5 x 1000 replays |
| 44 | K5 | size below Kelly when a costly boundary is near | P2 | `enable_boundary_sizing` | smallest code, largest blast radius |

**Not in the order.** R8 and R9 are constraints that bind now and specify no build; V7, V8 and K6 are
declined or recorded-only (K6's option tape exceeds this engine's vendors). And a T1 item is not
automatically next: **H2 landed ahead of H8 anyway**, because the availability DECLARATION is buildable
without the sourced lag table - the classes stop at what this repo can state (a filing date, a session
close) and an undeclared field fails closed. **What H8 still owes H2 is the table itself:** populating it
is what turns "we refuse what we cannot date" into "we date it correctly".

---

## 3. Cross-item dependencies

```text
P0-1 H10 coverage_window ......... gates every panel statistic in P1 and P4
P0-2 H1  trial ledger ............ -> H3 (Stage 2 retains the candidate matrix)
P0-4 H11 intervals ............... -> H4 excess_accuracy, H6 materiality, K1 band, R2 coverage test
P0-3 H7  refusal ledger .......... -> N7 (rejections logged), X2 (dropped components logged)
P0-6 H6  three verdicts .......... -> every later item's findings, which must be able to be INCONCLUSIVE
P1 V2   memory_parameter ......... <- K2 (Hurst is computed today; a memory parameter is the complement)
P1 X3   mp_below_count ........... + R3 eigen null band: both spectral, one per panel read
P1 R1   hazard_mode .............. independent; smallest change in the regime theme
P2 H2   availability gate ........ <- a per-field availability table (H8's publication-lag work).
                                    H2 LANDED 2026-09-24 with only the classes this repo can state
                                    (a filing date, a session close) and a fail-closed default;
                                    H8 is what would populate the table.
P2 R2   coverage-tested VaR ...... -> K1 (the coverage test ships with the tail layer)
P4 R6   onset gate ............... <- the labelled onset panel, which does not exist yet
P4 K4   characteristics covariance <- an offline encoder; must replace, not sit beside
```

Two ordering constraints are hard: **H3 cannot land before H1's ledger exists**, and **R6 cannot
land before the onset panel exists**. Everything else is independently landable.

---

## 4. In-run versus offline (the 40-minute budget)

A four-symbol run takes ~40 minutes end to end (measured: the MCD interactive run at `ff27ab4` took
2405 s). Against that budget:

**In-run, cheap (seconds or less).** H10, H1, H7, H11, H4, H6, X3, V2, V6, R1, R3, R7, K2, K3, K5,
V4, X8, H2, N3, K1, R2, V3, N6.

**In-run but material.** N1 (1-2 batched tag calls per symbol-day), N4 (one LLM call per **admitted**
article - the most expensive per-run item in the set, and the admission filter is a prerequisite),
V5 (only where the MP edge allows, which is usually `unavailable` at this book's size).

**Offline by construction, never in-run.** H3 (5 x 1000 replays), X1, X4, X5's fit, X2, X6, N5, N7,
R4, R6, K4, V1's refit. Ground rule 8 forbids calling these from `prepare_initial_state`,
`finalize_run`, or any agent tool.

**Panel needs.** R3, R5, X1, X3, X4 and V5 read a cross-section, not a symbol. For R3, R5, X4 and
V5 the docs recommend a **weekly offline pass** rather than a per-run producer; R5's calibration
belongs with `strategies/calibration.py`, and X3 is cheap enough per panel because it runs on 11
sector ETFs.

---

## 5. Open decisions (owner)

Each themed plan ends with its own line; those six, plus five the grounding work surfaced.

**From the six plans.**

1. **Honesty (H):** which subset to build, and whether **H10 + H1 + H7** land together as a first
   pass.
2. **Regime (R):** whether **R1 + R2** land as a first pass, and whether to fund the labelled onset
   panel that **R6** depends on.
3. **Risk (K):** whether **K1 + K2** land as a first pass, and whether the mandate permits the
   **`T^(H-1/2)` rescaling** to reach the drawdown governor. **[PARTLY ANSWERED 2026-09-24]** K1 and K2 have
   both landed: K1 scored-printed as planned, and K2 as the card's own documented fallback for an unanswered
   mandate - **report-only**, reaching the strategy-evaluation row while `risk_governor.govern`, `drawdown_gate`
   and `book_context.measured_book_drawdown` stay untouched on the square-root-of-time convention. **The
   governor question itself is still open:** it is the one line that would change a gate's output rather than
   a report's, so it waits for you.
4. **Volatility (V):** whether **V6 + V2** land as a first pass, and whether **`VXV` and a HY-spread
   series** are worth adding to the vendor surface to enable V1's full state vector.
5. **Cross-section (X):** whether **X3 + X6 + X2** land first, and whether the panel-scale items
   (**X1, X4**) are scoped as a weekly offline job rather than per-run producers.
6. **News (N):** whether **N3 + N1** land first, and whether the engine may add a hosted-embedding
   dependency for N1's tagging and N6's comparison.

**Surfaced by the grounding work.**

7. **scikit-learn:** add it as a declared dependency, or scope **X2** to a hand-rolled L1 selection?
   X5 and V1 are affected either way. K4 is deferred regardless.
8. **torch:** installed but undeclared. Declare it, making N1/N6 local and explicit, or keep the
   hosted/LLM-call route the news doc already scoped?
9. **tsbootstrap:** adopt the library for H11's conformal calibrators, or keep the in-house
   moving-block bootstrap (no new dependency, and the block-length rule is already specified)?
10. **H8's data sourcing:** an as-reported vintage store needs ALFRED (or a documented lag
    substitution). `dataflows/pit_registry.read_as_of` masks payloads by as-of date but only for
    payloads stored under the right date - the vintage store is the missing half.
11. **`docs/scores/MEASUREMENT_FINDINGS.md`** is owner-authored and already records three fields as
    "not measured" that are now measured. Findings from these phases need a home; nominate the file
    (and its edit convention) or a new ledger, and say which.

12. **The score panel's `N` (surfaced by the H1 build).** H1 wired the trial ledger into `alpha_zoo.bench_zoo`,
    which is where candidates are recorded and read back. `scripts/score_panel.py` still deflates by the family
    count it measured itself (`len(tested)`), which is a measured count for *that* panel and not a caller's
    assertion - so the card's clause holds there as stated. Moving that site to the ledger's dispersion is **not
    a one-liner and should not be wired blind**: the ledger records Sharpes under the equity convention
    (`periods_per_year=252`) while the panel's decile-spread series is per-period (`periods_per_year=1.0`), so
    `V` would have to be rescaled (`V / 252`) before it is dimensionally valid against that statistic. The
    owner's call, recorded rather than guessed.

13. **H9's gate key already exists (surfaced by the T1 integration, 2026-09-24).** H9's card names
    `enable_report_attribution`, and that key **ships today** for the DSA-2 advisory layer
    (`default_config.py:991`, the DSA family in `docs/gate_registry.md`). A new gate cannot be registered
    under an existing key - the six-point protocol asserts the key is absent - so H9 takes either an
    extension of that gate or a new name (`enable_report_influence` is free), and this plan's "34 new config
    gates" becomes 33 new plus one extension, the shape R1 already has. Every other unbuilt gate name across
    the six plans was checked the same day: **no other collision**. The card and both tables carry the note.

**Standing constraint, restated:** R9 is not a build. Regime information conditions *how much to
trust* another read; it is never concatenated onto it.

---

## 6. Landing protocol

Per item, in order:

1. **Failing-first proof.** Write the test, prove it **fails** under a targeted mutation of the code
   it guards, restore the source **byte-identical** (assert sha256 in a `finally`), and assert the
   expected test name appears in the failure output.
2. **Gate registration (six points)** if the item adds a gate - section 0 rule 6.
3. **Wiring in the same commit** if the item adds a public function to `strategies/` or
   `dataflows/` - section 0 rule 7.
4. **Full engine suite** (`py -3.12 -m pytest tests -q`, ~11-13 min) for any code change, run
   detached, with no source edits while it runs and no other suite concurrently. A docs-only commit
   does not need it.
5. **`py -3.12 -m ruff check .`** clean. Scratch scripts removed before the suite runs; the
   repo-root lint sees untracked `.py` files.
6. **Docs in the same commit**: `CHANGELOG.md` (newest entry directly under the first
   `### Changed`), `docs/AGENT_ONBOARDING.md` (newest entry above the current top dated entry),
   `docs/gate_registry.md` (the row **and** the coverage sentence), `.env.example`,
   `docs/api_reference.md` section 1.1 (via `scripts/gen_api_reference_table.py --write`), and any
   design doc whose status line changes.
7. **Web impact stated** in the CHANGELOG entry if the item touches a tool, flag or JSON shape the
   sibling app consumes. Contract tests:
   `py -3.12 -m pytest tests/test_engine_contract.py tests/test_doc_claims.py -q` from
   `trading_web/`.
8. **One item per commit**, explicit paths staged (never `git add -A`), with
   `git diff --cached --numstat` inspected before the commit. Doc edits must show `N 0`.

---

## 7. Honest limits

1. **None of this was backtested against this engine.** Every proposal in the six design docs is
   untested here until P0's instruments say otherwise. The set sequences the instruments first for
   exactly that reason.
2. **A gate is not evidence of an edge.** Adopting all five phases makes the engine harder to fool
   and no more likely to be right.
3. **The corpus's results are mostly single-window, single-market preprints.** Each item carries its
   paper's caveat into the design docs, and those caveats are the reason several items are declined
   (V7, V8, K6, the absence of H3's certification claim).
4. **Two of the three most load-bearing regime results are negative** (R8, R9), and the news theme's
   text results are the weakest in the survey by evidence quality. Adopting the vocabulary of a
   result is not adopting the result.
5. **The cost numbers are the papers' plus the measured dependency surface.** Where a cost was not
   measured (V1's refit cadence, N1's tagging latency at feed volume), the item says so rather than
   guessing.
6. **Nothing here enters `COMPOSITE_ENGINES`.** Six docs, 49 items, zero member changes - and that
   is a deliberate property of the corpus's findings, not an omission.
