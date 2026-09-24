# Implementation Plan - Cross-Section and Allocation

Status: **IN PROGRESS** - wave 0+1 build started: X8 landed (2026-09-23). The rest of this plan is not started.
volatility-rank chain, one redundancy screen, two spectral reads, one peer-producer replacement, one
edge classifier, one validation study and one horizon decomposition - of the 2026 `q-fin` corpus
survey adoption, of parent [`../design_fin_paper_survey_26.md`](../design_fin_paper_survey_26.md).
**Parent design:** [`design_cross_section_and_allocation.md`](design_cross_section_and_allocation.md)
**Folder index:** [`README.md`](README.md) - the eight inherited ground rules, the measured dependency surface, the cross-theme phase map, the dependency graph and the landing protocol live there.
**Items:** X3 (P1), X8 (P1), X6 (P1), X2 (P3), X5 (P3), X7 (P3), X1 (P4), X4 (P4).
**Gates added:** 3 (`enable_mp_lower_spectrum`, `enable_trend_spectral`, `enable_peer_edge_classifier`); no extension to an existing gate.

## 0. Scope

This plan covers the cross-sectional channel only: the rank/selection machinery, the spectral reads
over the breadth and technical panels, the peer universe and its edges, and the redundancy screen
over the engine's own components. Every item is additive and default-off, and each one degrades to
`unavailable` rather than to a number when its inputs are missing (ground rule 4). The rules that
bind this theme specifically are rule 2 (X5 must *replace* the label resolver, not sit beside it),
rule 3 (nothing here enters `COMPOSITE_ENGINES`), rule 7 (all seven build items add a public
function to `strategies/`, so each ships with its first caller in the same commit), rule 8 (X1, X2,
X4, X5's fit and X6 are offline and may not be called from `prepare_initial_state`, `finalize_run`
or any agent tool), and rule 6 for the three gates. X6 adds no public function: it is a study.

## 1. Item cards

### X3 - Marchenko-Pastur lower-spectrum count

**Target.** `strategies/market_breadth.py` / `strategies/sector_breadth.py`, which already hold the panel (`sector_breadth.py:60` `multi_breadth`); new `mp_below_count(corr, n, w) -> {count, mp_lower, status}`. The panel is the 11 SPDR sector ETFs `sector_rank` already tracks.
**Phase / run mode.** P1 / in-run.
**Behaviour.** Counts the eigenvalues of the panel correlation matrix below the Marchenko-Pastur lower bound `(1 - sqrt(n/w))^2`; the count rises when the effective number of independent bets collapses. `status = "unavailable"` when `w <= n`, i.e. when the window is not longer than the number of names. A per-panel read, never a per-symbol one.
**Gate.** `enable_mp_lower_spectrum`.
**Failing-first test.** `tests/test_strategies_market_breadth.py::test_mp_below_count_unavailable_when_window_not_longer_than_names`. Mutation: change the `w <= n` guard to `w < n`. It asserts that `w == n` returns `status == "unavailable"` (not `count == 0`), that with `w > n` the count equals the number of eigenvalues below `(1 - sqrt(n/w))^2` and `mp_lower` equals that bound, and that with the gate off `multi_breadth`'s output is unchanged.
**Acceptance.** On the 11-ETF panel with `w > n`, `count` and `mp_lower` match the bound above; `w == n` and `w < n` both read `unavailable`; the output carries the window it was computed over; with the gate off, existing breadth output is byte-identical to today.
**Depends on.** P0-1 H10 (a panel read must report its window); R3 is the paired item - both spectral, one per panel read - not a dependency.
**Doc caveat.** Coincident and direction-blind - it cannot separate a crash from a bubble - and the paper's predictive claim is asserted more than demonstrated; report it as a state, never as a signal.

### X8 - spectral excess mass + cost-optimal span

**Target.** `strategies/technical_factors.py`; new `spectral_excess_mass(returns) -> {mass, condition_met}` and `cost_optimal_span(cost_bps, vol) -> int`; consumed by `swing`.
**Phase / run mode.** P1 / in-run.
**Behaviour.** `spectral_excess_mass` expresses P&L in volatility-normalized returns and reports whether low-frequency spectral mass meets the zero-drift condition under which trend alpha exists; `cost_optimal_span` converts the engine's cost estimate and the symbol's volatility into a lookback. Both are reported beside the swing factor, never inside its score.
**Gate.** `enable_trend_spectral`.
**Failing-first test.** `tests/test_strategies_technical_factors.py::test_cost_optimal_span_is_monotone_in_cost`. Mutation: return the zero-cost span, ignoring `cost_bps`. It asserts the span is a positive `int` and is monotone in `cost_bps` over a fixture cost grid (differing between a near-zero and a high cost input), and that `condition_met` is False on white noise and True on a series with a planted low-frequency component.
**Acceptance.** The swing factor's value is identical with the gate on and off - the read sits beside the score, not in it - while the two new fields appear beside it; the returned span is a positive integer that responds to `cost_bps`.
**Depends on.** nothing.
**Doc caveat.** The decomposition is a condition, not a signal: it says when to expect trend alpha, not which direction - read it as a filter on when the swing factor deserves weight.

### X6 - forward-rank test of the existing liquidity estimators

**Target.** A study script over `strategies/liquidity_risk.py:71` `amihud_illiquidity` and `:262` `kyle_lambda`, using `strategies/signal_analysis.py:64` `rank_ic` as the statistic. **No new estimator is written or added.**
**Phase / run mode.** P1 / offline.
**Behaviour.** Computes `rank_ic(lambda_month_t, fwd_return_t+1)` over the report panel and emits a numbers-of-record table that names its window; rows where trade direction cannot be determined read `unavailable`. It produces that table and nothing else.
**Gate.** none (a study over an estimator that already exists - there is no production surface to gate).
**Failing-first test.** `tests/test_liquidity_forward_rank.py::test_forward_window_not_contemporaneous`. Mutation: shift the return leg from `t+1` to `t`. It asserts that on a fixture where the contemporaneous and forward rank correlations differ in sign, the reported `rank_ic` matches the forward window and the record names `fwd_return_t+1`.
**Acceptance.** Every symbol-month's `rank_ic` is computed against `fwd_return_t+1`, undetermined rows read `unavailable`, and the commit adds no public function to `strategies/` - so `tests/test_calc_agent_wiring.py::test_public_calc_reachable_or_whitelisted` is unaffected.
**Depends on.** nothing (both the estimator and the statistic already exist).
**Doc caveat.** Daily bars give a crude trade-direction proxy; the paper's own result uses intraday direction and the estimator's quality on daily data is unmeasured.

### X2 - redundancy screen over components

**Target.** `strategies/factor_expressions.py` and `alpha_zoo.py` (whose bench is `alpha_zoo.py:243` `bench_zoo`); new `redundancy_screen(candidates, controls) -> {kept, dropped, coefficients}`, run offline on a schedule and consumed by the score-engine documentation.
**Phase / run mode.** P3 / offline (a scheduled script).
**Behaviour.** Double-selection LASSO over the engine's candidate factors against a control set, with a selection window that must not overlap the evaluation window. Its consumption is a decision, not a computation: a component that never survives the screen becomes a *documented* component rather than a scored one.
**Gate.** none (a scheduled script - nothing is added to the in-run surface).
**Failing-first test.** `tests/test_redundancy_screen.py::test_every_dropped_component_is_logged`. Mutation: delete the refusal-ledger write for dropped components. It asserts that every dropped component has a ledger row naming the screen and the window, that `kept` and `dropped` partition `candidates` with no overlap, and that a second run on a shifted window reports the survivor-list difference.
**Acceptance.** `kept + dropped == candidates` with no duplicates, selection disjoint from evaluation, one P0-3 refusal-ledger row per dropped component, and the screen is reachable only offline.
**Depends on.** P0-3 H7 (dropped components are logged into the refusal ledger).
**Doc caveat.** No stability test across refits is reported by the paper - a survivor list that changes every refit is not a finding - so any use here must re-run the screen and compare.

### X5 - valuation-anchored peer weights

**Target.** `strategies/peer_universe.py`, **replacing** `resolve_peer_universe` (`:174`) rather than sitting beside it; new `valuation_anchored_peers(characteristics) -> {weights_by_peer}` feeding the existing peer-relative multiples. The other consumers to migrate are `resolved_peer_names` (`:150`) and `resolve_growth_medians` (`:304`).
**Phase / run mode.** P3 / offline fit.
**Behaviour.** A gradient-boosted tree is fit on a valuation multiple (EV/EBITDA or EV/Sales) from point-in-time fundamentals; peer weights are importance-weighted leaf-node co-occurrence, so two names are peers because the model prices them alike, not because they share a sector code. The fit is offline; leaf co-occurrence at inference is trivial.
**Gate.** none (a replacement decision - a gate would imply keeping two peer producers, which rule 2 forbids).
**Failing-first test.** `tests/test_peer_universe.py::test_peer_relative_multiple_uses_valuation_peers`. Mutation: re-point the peer-relative consumer at the label path. It asserts that on a fixture where the sector-label peer set and the valuation peer set differ, the consumer's peer set is the valuation one; the mutation yields the label set and fails by name.
**Acceptance.** On the fixture, every peer-relative consumer - the peer-relative multiple, `resolved_peer_names`, `resolve_growth_medians` - resolves to the valuation set, and `weights_by_peer` is a normalized distribution over peers for each name.
**Depends on.** nothing (the fundamentals engine already assembles point-in-time characteristics).
**Doc caveat.** Built on private-market deals, so the similarity's stability is inherited from a valuation target that behaves differently in public markets - and the peer set already has a producer here, making this the item in this doc most likely to become duplication.

### X7 - relation-classified peer edges

**Target.** `strategies/peer_universe.py` and `strategies/theme_triggers.py` (whose cheap-scan pattern fits candidate generation); a classifier over `resolve_peer_universe`'s candidate edges plus the relation-conditioned aggregation. Inputs already present: `strategies/security_context.py`, `strategies/text_factors.py`, `dataflows/sec_edgar.py`.
**Phase / run mode.** P3 / offline.
**Behaviour.** Every candidate peer edge is classified into economic relations; competitor edges are dropped before the pair z-score divergence is aggregated with co-movement weights into a per-symbol mean-reversion read. One call per candidate edge, cached per filing pair.
**Gate.** `enable_peer_edge_classifier`.
**Failing-first test.** `tests/test_peer_edge_classifier.py::test_competitor_edges_dropped_and_logged`. Mutation: skip the competitor drop so competitor edges reach the aggregation. It asserts that a fixture whose candidates are all competitors yields no signal (`unavailable`, not zero) and that every drop has a refusal-ledger row; the mutation yields a signal and fails by name.
**Acceptance.** Every candidate edge carries a relation class, no competitor edge reaches the aggregation, each dropped edge has a P0-3 row, and an all-competitor fixture reads `unavailable`.
**Depends on.** P0-3 H7 (dropped edges are logged into the refusal ledger).
**Doc caveat.** The pair-divergence signal is a mean-reversion claim on a horizon this engine's mandate may not hold long enough to realise.

### X1 - volatility-rank transition chain

**Target.** New module `strategies/rank_transition.py`; `rank_transition(returns, kind="volatility"|"return") -> {P, forward_rank_prob}`. Consumes `strategies/cross_section.py:140` `centered_rank`; feeds `strategies/portfolio_strategy.py:35` `topk_drop_weights`, which already does the selection half.
**Phase / run mode.** P4 / offline, weekly.
**Behaviour.** Builds a 10-decile transition matrix over names ranked monthly by trailing volatility, `P^X_ab(t) = P(rank_i(t+D) = b | rank_i(t) = a)`, then `pi^V_i = sum_{b<=2} P^V` (probability of landing in the two calmest deciles) and the blend `S_i = (1-lam)*pi^R_i + lam*pi^V_i`. `kind="volatility"` is the default; `kind="return"` is available **only** with the `unforecastable` flag attached.
**Gate.** none (offline by construction - a weekly job, not a per-run producer).
**Failing-first test.** `tests/test_rank_transition.py::test_return_chain_requires_unforecastable_flag`. Mutation: allow `kind="return"` without the flag. It asserts that the call without the flag refuses and names `unforecastable` in the refusal, that `kind` defaults to `"volatility"`, and that with the flag every reported number carries it.
**Acceptance.** `P` is row-stochastic with 10 rows and 10 columns, `forward_rank_prob` lies in [0,1], the return chain without the flag refuses, and nothing in the module is reachable from `prepare_initial_state`, `finalize_run` or any agent tool.
**Depends on.** P0-1 H10 (a panel read must report its window).
**Doc caveat.** Author-run and LLM-assisted, self-reported with no replication; the diversification gain from residual distance is a separate claim from the rank forecast and should be evaluated separately.

### X4 - eigenmode variance ratio by horizon

**Target.** New module beside `strategies/covariance_models.py`; `horizon_memory(corr_series, horizons) -> {vr_by_mode, persistent_share}`.
**Phase / run mode.** P4 / offline, weekly.
**Behaviour.** Computes an eigenmode-indexed variance-ratio matrix over a horizon grid so a risk estimate can state how much of itself is persistent versus reverting. Cost is `O(T * horizons)` per pair, so it is a panel-offline job, not a per-symbol one.
**Gate.** none (offline by construction - a weekly job, not a per-run producer).
**Failing-first test.** `tests/test_horizon_memory.py::test_persistent_share_is_a_fraction_of_the_estimate`. Mutation: divide by the wrong denominator so the share is no longer normalized. It asserts that on an anti-persistent fixture the share is below 0.5 and on a persistent fixture above it, and that the share lies in [0,1] in both cases; the mutation fails by name.
**Acceptance.** `persistent_share` lies in [0,1] and the output names the horizon grid it was computed over; `vr_by_mode` is indexed by eigenmode; no in-run caller exists.
**Depends on.** P0-1 H10 (a panel read must report its window).
**Doc caveat.** The paper's multi-year memory sits far outside this engine's days-to-weeks mandate, and its 28-year window precludes narrower regime dating - adopt the question, and expect the engine's own answer at short horizons to be unimpressive.

## 2. Item table

| ID | Deliverable | Owner | Phase | Run mode | Gate |
|---|---|---|---|---|---|
| X3 | MP lower-spectrum count | `market_breadth.py`, `sector_breadth.py` | P1 | in-run | `enable_mp_lower_spectrum` |
| X8 | spectral excess mass + cost-optimal span | `technical_factors.py` | P1 | in-run | `enable_trend_spectral` |
| X6 | forward-rank test (study) | `signal_analysis.py` + `liquidity_risk.py` | P1 | offline | none (study) |
| X2 | redundancy screen | `factor_expressions.py`, `alpha_zoo.py` | P3 | offline | none (scheduled script) |
| X5 | valuation-anchored peer weights | `peer_universe.py` (replaces) | P3 | offline fit | none (replacement decision) |
| X7 | relation-classified peer edges | `peer_universe.py`, `theme_triggers.py` | P3 | offline | `enable_peer_edge_classifier` |
| X1 | volatility-rank transition chain | `rank_transition.py` (new) | P4 | offline, weekly | none (offline job) |
| X4 | eigenmode variance ratio by horizon | new, beside `covariance_models.py` | P4 | offline, weekly | none (offline job) |

## 3. Gates added by this plan

| Gate | Item | Enforcement site | Default |
|---|---|---|---|
| `enable_mp_lower_spectrum` | X3 | `strategies/market_breadth.py`, `strategies/sector_breadth.py` | off |
| `enable_trend_spectral` | X8 | `strategies/technical_factors.py` | off |
| `enable_peer_edge_classifier` | X7 | `strategies/peer_universe.py` | off |

The six registration points per gate are in [`README.md`](README.md). The other five items add no
gate and each says why in its card: X6 is a study, X2 is a scheduled script, X5 is a replacement
decision, and X1 and X4 are offline jobs.

## 4. Dependencies

This theme's slice of the cross-item graph. Other-theme items are named by ID; their own plans own
their detail.

```text
P0-1 H10 coverage_window ...... -> X3, X1, X4 (a panel read reports its window or refuses)
P0-3 H7  refusal ledger ....... -> X2 (dropped components logged), X7 (dropped competitor edges logged)
P1 X3    mp_below_count ....... + R3 eigen null band: both spectral, one per panel read
X3 panel ...................... = the 11 SPDR sector ETFs sector_rank already tracks (no new data)
X6 study ...................... over liquidity_risk.py:71 amihud_illiquidity, :262 kyle_lambda,
                                 using signal_analysis.py:64 rank_ic; adds no estimator
X1 chain ...................... consumes cross_section.py:140 centered_rank,
                                 feeds portfolio_strategy.py:35 topk_drop_weights
X5 weights .................... REPLACES peer_universe.py:174 resolve_peer_universe;
                                 it may not sit beside it (rule 2, one producer per derived quantity)
X7 edges ...................... consumes resolve_peer_universe's candidates; drops competitor edges
                                 before the relation-conditioned aggregation
X1, X2, X4, X5's fit, X6 ...... offline by construction; rule 8 forbids in-run callers
```

One ordering constraint is hard here: **X5 cannot land as an addition** - the label resolver is
retired in the same commit that the valuation producer lands, and every peer-relative consumer is
migrated with it. Everything else in the theme is independently landable.

## 5. Decisions requested (owner)

- **This theme's own line:** whether **X3 + X6 + X2** land first, and whether the panel-scale items
  **X1, X4** are scoped as a weekly offline job rather than per-run producers. This plan assumes
  offline for both.
- **scikit-learn:** X2's double-selection needs an L1 solver and X5's peer weights need a fitted
  tree, and scipy has no LASSO. Add `scikit-learn` as a declared dependency, or scope X2 to a
  hand-rolled L1 selection (the doc only needs a survivor list)?
- **X5 at all:** the replacement is binding (rule 2), so the decision is not whether it duplicates
  the label resolver but whether it lands, given that its similarity is anchored to a private-market
  valuation target.
- **X1's return chain:** built behind the `unforecastable` flag, or not built at all, given the
  paper's own evidence that the chain carries no signal?

## 6. Honest limits

1. **This theme's headline is a negative one.** The cross-sectional return rank is close to
   unforecastable (monthly log-likelihood gain 0.007 against the volatility chain's 0.108), so
   adopting this theme should reduce confidence in the return-forecasting halves of the score
   engines, not raise it.
2. **X1 and X4 cannot run in a run.** Both need a full cross-section against a ~40-minute
   four-symbol budget, so their in-run value is zero by construction and their outputs are weekly
   offline artefacts.
3. **X5 and X6 are the two items most likely to break a house rule** - X5 by becoming a second peer
   producer, X6 by being mistaken for a new estimator. Both are constrained in place above, and both
   were nearly mis-specified by the survey itself.
4. **X3's information is coincident and direction-blind**, and its paper's predictive claim is
   asserted more than demonstrated; it is a state read, and no item here promotes it to a signal.
5. **Nothing here enters `COMPOSITE_ENGINES`.** X1-X8 feed existing engines' inputs or measure
   existing estimators, and the theme proposes no member change.
