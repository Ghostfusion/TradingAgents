# What the general-finance literature can teach this research engine

Date: 2026-10-07. Revision 1.

This directory holds twenty-eight learning briefs written from a local harvest of the arXiv
`q-fin.GN` (General Finance) category: 3095 records spanning 1997 to 2026. Each brief takes one
slice of that corpus, reads a set of papers in depth, and states what the evidence changes about how
a signal is measured, a model is evaluated, a book is allocated, and a research decision is
defended.

This repository is a research and analysis layer: deterministic calculators, wired to tool-calling
language-model analysts, scored by a registry, and concluded as a research decision that is checked
against a contract. It does not execute orders. So every take-away table here lands on a
research-layer surface - a calculator module, an agent tool, an analyst prompt, a config gate, a
score engine, a registry, or the evidence and report surfaces - and where a finding is only
actionable in an execution layer, the brief says so and records it as having no landing here rather
than inventing one.

`Strategies/books/` holds the companion set, written from a wider crawl of arXiv q-fin and its
cross-lists (4348 PDFs, 1997-2026) and organised into nineteen thematic books. Read the two
together. That library covers the agentic-LLM, backtest-evaluation, data-quality, factor and
microstructure material; this one is where the general-finance evidence lives: who lends, who
insures, who is regulated, what a rating, a filing or a text signal is worth, how a portfolio should
be built when the covariance is estimated rather than known, and how financial research fails to
replicate. Where a category overlaps, the brief here says so and adds rather than restates.

The same harvest was independently read for an execution layer elsewhere, in `nautilus_trader` under
`strategies/books2/`. That set is not this one: its take-away tables point at a Rust/Python
event-driven engine and its findings are written for execution. These briefs were written from the
PDFs for this repository, and share the corpus, not the conclusions.

## The harvest

| Field | Value |
| --- | --- |
| Source | arXiv full listing for `cat:q-fin.GN`, captured 2026-10-05 |
| Records harvested | 3095 |
| PDFs on disk | 3066 (29 besides are withdrawn or return HTTP 404) |
| Size | 3700.2 MB, downloaded over 185 minutes with a 3.0 s delay |
| Years spanned | 1997-2026 |
| Records with a journal reference | 792 (26%) |
| Records with a DOI | 918 (30%) |
| Records from 2021 onward | 933 (30%) |
| Primary categories | 1758 q-fin.GN, 290 physics.soc-ph, 139 econ.GN, 92 q-fin.ST, 82 cond-mat.stat-mech, 62 q-fin.TR, 58 q-fin.RM, 51 q-fin.PR |

Every record is cross-listed into `q-fin.GN`, arXiv's general-finance category and a cross-listing
attractor: it collects the econophysics ancestors (`cond-mat.*`, `physics.soc-ph`, `nlin.*`), the
general-economics cross-lists (`econ.GN`), and the applied work that does not fit a narrower `q-fin`
category. The early material is sociophysics and statistical mechanics, the middle is credit, macro
and portfolio work, and the recent material is dominated by crypto, machine learning and language
models. Practitioner microstructure is largely absent, because that material is primary in
`q-fin.TR`.

The harvest itself is not vendored into this repository. It is kept outside it, with the full record
set in `.state/metadata.jsonl` beside the PDFs, and the briefs cite papers by arXiv id, which is the
durable reference.

## How the briefs were produced

1. **Census.** Every one of the 3095 records was scored against the topic patterns of every
   category over its title and abstract, which produced the per-category counts in the table below.
   This is a census of the whole corpus, not a sample.
2. **Shortlist.** The highest-signal records per category became the candidate list, fewer where the
   category is smaller, with the score favouring title matches, journal publication and recency.
3. **Deep reading.** Between six and twelve papers per category were read from the PDFs, targeting
   the abstract, the model or data setup, the results tables, and the conclusion. Every number kept
   in a brief was read in the PDF and carries a page marker.
4. **Writing.** Each brief was written from those notes only, and cites papers by arXiv id, which is
   the durable reference anyone can re-fetch. Each brief's take-away table was then aimed at this
   repository specifically, for a research layer, with every cited path checked to exist.
5. **Verification.** A script kept beside the harvest checks every brief for ASCII and line-feed
   hygiene, the required sections, whether every cited arXiv id resolves against the harvest
   metadata, whether every paper listed as read in depth has a local PDF, and whether every
   repository path cited in a take-away table exists.

## The corpus by category

`Records` counts harvest records whose title or abstract matches the category, so a paper can belong to more than one. `Recent` counts records from 2021 onward. `Read` counts the papers read in depth for that brief.

| Brief | Records | Years | Journal refs | Recent | Read |
| --- | --- | --- | --- | --- | --- |
| `01_networks_and_systemic_risk.md` | 322 | 2003-2026 | 124 | 56 | 12 |
| `02_banking_credit_and_funding.md` | 223 | 2000-2026 | 59 | 86 | 12 |
| `03_crypto_defi_and_perpetuals.md` | 193 | 2012-2026 | 40 | 121 | 12 |
| `04_machine_learning_for_finance.md` | 156 | 2008-2026 | 18 | 126 | 12 |
| `05_bubbles_crashes_and_criticality.md` | 153 | 2000-2026 | 55 | 24 | 12 |
| `06_econophysics_and_agent_based_markets.md` | 148 | 2000-2025 | 51 | 16 | 12 |
| `07_macro_rates_and_fx.md` | 140 | 2001-2026 | 30 | 30 | 12 |
| `08_predictability_and_trading_strategies.md` | 122 | 2001-2026 | 22 | 52 | 12 |
| `09_insurance_pension_and_household_finance.md` | 115 | 2002-2026 | 32 | 38 | 12 |
| `10_portfolio_and_allocation.md` | 112 | 2000-2026 | 15 | 52 | 12 |
| `11_language_models_news_and_text.md` | 100 | 2011-2026 | 23 | 73 | 12 |
| `12_options_and_derivatives.md` | 96 | 2008-2026 | 17 | 41 | 12 |
| `13_stylized_facts_and_scaling.md` | 93 | 1998-2026 | 35 | 14 | 12 |
| `14_volatility_and_microstructure_noise.md` | 86 | 1998-2026 | 19 | 40 | 12 |
| `15_esg_climate_and_sustainability.md` | 79 | 2010-2026 | 16 | 41 | 10 |
| `16_information_theory_and_complexity.md` | 61 | 2007-2026 | 11 | 16 | 10 |
| `17_quantum_and_exotic_methods.md` | 55 | 2003-2025 | 24 | 12 | 8 |
| `18_energy_and_commodities.md` | 53 | 2006-2026 | 14 | 15 | 10 |
| `19_manipulation_fraud_and_governance.md` | 47 | 2007-2026 | 8 | 27 | 10 |
| `20_market_design_regulation_and_fees.md` | 43 | 2007-2026 | 11 | 21 | 10 |
| `21_prediction_markets_and_betting.md` | 24 | 2009-2026 | 1 | 10 | 8 |
| `22_risk_measures_and_drawdowns.md` | 23 | 2009-2026 | 2 | 10 | 8 |
| `23_market_making_and_inventory.md` | 22 | 2006-2026 | 8 | 9 | 8 |
| `24_regimes_and_change_points.md` | 18 | 2006-2026 | 3 | 6 | 8 |
| `25_execution_impact_and_order_book.md` | 24 | 2009-2026 | 6 | 13 | 12 |
| `26_order_flow_hft_and_latency.md` | 29 | 2008-2026 | 2 | 13 | 10 |
| `27_market_data_quality.md` | 12 | 2016-2026 | 1 | 8 | 6 |
| `28_overfitting_and_research_integrity.md` | 9 | 2011-2025 | 3 | 5 | 6 |

## The briefs

| Brief | Scope |
| --- | --- |
| `01_networks_and_systemic_risk.md` | the network of direct exposures is a weak standalone channel that switches on only when it meets a common-asset shock, and every network statistic worth publishing is the one read against a heterogeneous null |
| `02_banking_credit_and_funding.md` | funding is the residual of settlement, credit risk is not stationary, and the leverage rule is part of the price mechanism |
| `03_crypto_defi_and_perpetuals.md` | the cost of consensus stayed pinned to transfer value while market making, liquidations and stablecoin issuance ran on tail-heavy, cost-free mechanics the research layer can already measure |
| `04_machine_learning_for_finance.md` | a fitted model's claim is bounded by its evaluation design, not its architecture |
| `05_bubbles_crashes_and_criticality.md` | the defensible output is a distribution over a regime change, not a crash date and not a short signal |
| `06_econophysics_and_agent_based_markets.md` | a stylised fact you measure can be an artifact of the horizon, the estimator, or the mean field |
| `07_macro_rates_and_fx.md` | the tradable macro signal in this corpus is a scheduled-announcement parallel shift of the whole curve plus a Taylor-rule currency factor, and a single-name equity research layer can consume it only through its regime, sector-duration and rate-convention surfaces. |
| `08_predictability_and_trading_strategies.md` | the cross-section is mostly real and the time series mostly is not, so decay, costs and leakage are the binding constraints |
| `09_insurance_pension_and_household_finance.md` | the household demand side is lumpy, and the products that serve it are priced by fees, taxes and mortality rather than by the market |
| `10_portfolio_and_allocation.md` | the allocation inputs this repo already shrinks are still its weakest link, because every construction rule is a design choice whose ranking moves with the test assets, the estimator and the rebalancing rule |
| `11_language_models_news_and_text.md` | the model that reads the news is part of the measurement |
| `12_options_and_derivatives.md` | every implied number this repo publishes is a vendor IV mapped through a zero-rate Black-76, and the surface literature says to price the carry and distrust the fit |
| `13_stylized_facts_and_scaling.md` | the heavy tails and the scaling exponents are functionals of the conditioning variable and the estimator, so a lone published exponent is not a measurement of the asset |
| `14_volatility_and_microstructure_noise.md` | pick the estimator your risk measure will be scored on, not the one that wins the forecast MSE |
| `15_esg_climate_and_sustainability.md` | the measurable ESG signal is inter-rater disagreement, and this research layer holds no ESG, climate or carbon surface to carry it |
| `16_information_theory_and_complexity.md` | an entropy or complexity feature earns its place only when it carries a null and a coverage window, and the slice supplies both. |
| `17_quantum_and_exotic_methods.md` | the slice yields no tradable signal, but its measurement failures - unbalanced samples, nominal-confidence calibration, and unlogged optimisation cost - map directly onto this repo's calibration and evaluation surfaces |
| `18_energy_and_commodities.md` | the transferable content for an equity-research layer is storage, carry and mean reversion, not the trading of power itself |
| `19_manipulation_fraud_and_governance.md` | the detectors in this slice fail quietly at their reported precision, so the research layer must publish evidence grades rather than accusations |
| `20_market_design_regulation_and_fees.md` | a rule change is a dated change to a decision contract, and a fee is a policy the owner sets |
| `21_prediction_markets_and_betting.md` | a market-implied probability beats the public forecaster on one venue, but its tape cannot tell you who traded, so cite it as a calibrated prior and never as a direction-dependent signal. |
| `22_risk_measures_and_drawdowns.md` | the tail measures a book budget actually wants are exactly the ones whose estimates are most fragile, so every published tail must carry its sample, its coverage and its quality |
| `23_market_making_and_inventory.md` | dealer pricing power sets the spread, but the part a research layer can use is the spread and inventory estimator, not the quoting mechanic |
| `24_regimes_and_change_points.md` | in this 2006-2026 harvest the only state model that beat its benchmark out of sample was the one filtered and re-estimated online, and every detector read in hindsight was the wrong instrument for a live gate. |
| `25_execution_impact_and_order_book.md` | the research layer can consume this corpus only as a calibration target and a set of measurement warnings, because the execution engine is not where this repository lives. |
| `26_order_flow_hft_and_latency.md` | at the research layer the transferable part is order flow as a feature and the data-quality gates that decide whether that feature is measurable at all |
| `27_market_data_quality.md` | a recorded outcome is the collector's classification, not the event it names, and the research layer must publish that provenance and its degradation next to the number |
| `28_overfitting_and_research_integrity.md` | the published predictor literature replicates, but one bad data row and one unrecorded trial count can still erase a strategy |

## What the corpus says collectively

These are the findings that recur across independent slices of this corpus, so they are the ones worth acting on in a research engine.

1. **The evaluation design, not the model, decides what survives.** A matched classification-versus-regression
   experiment moved a portfolio's value-weighted Sharpe from 1.39 to 2.08 with the same features and models
   (`2108.02283v7`); a GARCH-GRU hybrid cut volatility MSE by 72 percent while the resulting Value-at-Risk and
   Expected Shortfall models did not inherit it and the hybrid shortfall tests failed (`2310.01063v1`); and seven
   language models scoring the same earnings calls agreed at a mean pairwise rank correlation of only 0.52, so the
   provider is part of the measurement (`2609.31013v1`). The recurring practical lesson is to fix the scoring rule
   before comparing models, and to report the metric that is actually being optimised.

2. **Bookkeeping and definition errors are larger than most signal sizes.** Net-return and arithmetic-mean
   bookkeeping inflated the S&P 500 Sharpe ratio by nearly 30 percent and overstated the 1960-2020 terminal value by
   89 percent (`2405.10920v1`); a single erroneous odds row turned two published betting ROIs of 17.29 and 28.82
   percent into -7.36 and -6.31 percent while the coefficients and bet sequence reproduced exactly (`2306.01740v4`);
   and a recorded outcome label was shown to be a joint function of the platform event and the collector's polling
   design (`2607.02823v4`). Before tuning anything, check what the number means.

3. **Fitted models in this corpus are frequently non-identifiable, and the tail is often an artifact.** Kinetic
   wealth exchange has no stationary distribution for any finite population, and its power-law window lasts only
   about 300 steps at N = 10,000 (`0809.4139v2`); two parameters of an extended Chiarella agent-based model enter
   the same term so both cannot be calibrated (`2208.14207v1`); the log-periodic power law yields a distribution
   over the critical time rather than a date, and about one bubble in three ends without a crash (`1107.3171v3`);
   and the roughness statistic carries a finite-size bias of +0.323 at H = 0.9 (`2512.02352v3`). Report the
   identifiable part, and say which part is a convention.

4. **Tail-sensitive risk measures are fragile by construction, and the axioms force Value-at-Risk.** One observation
   beyond the quantile can make a historical expected-shortfall estimate arbitrarily large, while VaR needs more
   than (1-alpha)n points to move (`2206.02582v2`); any surplus-invariant, law-invariant, conic and
   truncation-closed acceptance set must be a VaR acceptance set (`1707.05596v2`); and close to three quarters of
   random equity windows look non-normal against one in six stress-ordered ones (`1310.4538v2`). Choose the risk
   measure as a policy, and test the estimator's stability on your own sample.

5. **Market data is not clean, and the defect is usually in the source, not the parser.** Public prediction-market
   book feeds recovered the trade aggressor only about 59 percent of the time, flipping the sign of
   direction-dependent measures on most markets (`2604.24366v2`); mini flash crashes turned out to be a venue-rule
   artefact in which 67.85 percent of the episodes were ISO-initiated (`1211.6667v1`); and comparability across
   providers is the exception rather than the rule, as ESG raters disagree far more than credit raters do
   (`2606.31469v1`). Validate a feed against an independent record of the same events before computing anything
   from it.

6. **Rules and incentives reroute activity rather than removing it.** Europe gained 13.88 additional ICOs per
   region-month after the DAO Report (`2602.00138v1`); a delisting mandate left aggregate stablecoin volume flat
   while shifting the venue cross-section by 0.818 pre-event standard deviations (`2607.09514v1`); and lengthening
   the settlement horizon of an ultra-short contract, rather than adding surveillance, removes the manipulation
   signature (`2606.31675v1`). Model the venue's rule set as part of the payoff, not as a footnote.

7. **Every detector is a false-positive machine, and its cost is measurable.** A conventional Z-score spoofing screen
   on the LUNA tape flagged orders priced $0.01 and $0.11 far from the spread and missed inserted spoofing
   entirely, while a classifier's F1 halved from 80.40 to 46.08 once neutral book states entered the label set
   (`2308.08683v1`, `2403.13429v1`); and deflating the top two volume quantiles as suspected wash trading destroyed
   legitimate flow and cut a portfolio Sharpe from 1.41 to 0.96 (`2404.07222v3`). Report precision, recall and the
   cost of the errors, not the hit count.

8. **Costs and physical mechanics dominate apparent edges.** Battery arbitrage does not clear its own roughly
   100 EUR/MWh wear cost in most European day-ahead markets (`2112.09816v2`), with zero-wear profitability on only
   about 310 days of 2019 in Spain (`2007.00486v2`); the market-based variance of an allocation differs from the
   Markowitz variance by the coefficient of variation of trade volume (`2507.21824v1`); and option-implied discount
   factors sat about 37.50 bp above OIS while parity residuals were compressed to near zero (`2604.19604v6`).
   Where a mechanism has a denomination, model the denomination.

9. **Concentration is the norm on both sides of the market.** The top six mining pools held 89.4 percent of capacity
   (`2606.03153v1`); no observed governance-token distribution needed more than 100 addresses for a quorum
   (`2102.10096v2`); the median household portfolio never fell below an effective two stocks over 2001-2021
   (`2503.17778v1`); and dealer pricing power plus network transmission accounted for 2.5 to 5.3 percentage points
   of gilt yield deviation (`2603.10690v1`). Liquidity and counterparty assumptions that assume many participants
   are wrong in the tail.

10. **Contagion and stability are non-monotone in connectivity and leverage.** Direct interbank exposures are a weak
    standalone channel that becomes a strong amplifier once a common asset shock is added (`1306.3704v1`); the
    critical degree is a closed form, small (about 5 to 10) against an observed mean degree near 15 (`1402.4783v2`);
    and a 16 percent capital floor can force selling into a decline and turn an absorbable shock into a catastrophe
    (`1403.1637v1`). Risk limits deserve a simulated second-order test, not only a first-order one.

11. **Persistence, when measured properly, is real but state-dependent.** Publication-bias corrections across three
    independent teams shrank in-sample returns by only 10 to 15 percent, with false discovery rates under
    10 percent (`2209.13623v3`); the cross-sectional factor zoo's bound on false discovery is 8.5 to 25 percent
    (`2206.15365v10`); and yet the risk-return trade-off is positive and significant only in low-volatility states
    (`1410.6005v1`). The binding constraint is the analyst's own specification search and the regime, not a
    t-statistic threshold.

12. **Out-of-sample survival correlates with online re-estimation and with honest calibration.** The only regime
    model in its slice that was filtered and re-estimated online returned 15.18 percent annualised against
    -2.44 percent for a backward-looking rule (`2309.00875v3`); held-out calibration slope 0.013 and intercept
    +2.816 exposed a model whose development AUROC of 0.8594 collapsed to 0.4642 (`2607.02823v4`); and a maturity
    regression that reproduced coefficients exactly still failed the replication's data audit (`2306.01740v4`).
    Prefer the model that can be updated and checked over the one that fits best in hindsight.

## How to use these documents

- Treat the short answer at the top of each brief as the checklist for that topic, and the take-away
  table as the list of concrete places where this repository should change.
- Treat the caveats section as binding. These are mostly single-market, single-period studies, and
  the briefs say so where it matters.
- Where a brief names a paper as a lead rather than reading it, no claim is made about it; follow the
  id when the claim matters.
- A row whose landing is a config gate is a policy question, not a defect: this repository keeps its
  defaults deliberate, and enabling a gate is the owner's call.

## Limits

Four limits apply to everything in this directory. First, the corpus is one arXiv category, and
`q-fin.GN` is a cross-listing attractor rather than a field: it over-represents econophysics and
sociophysics, and under-represents practitioner microstructure. Second, the composition is uneven:
credit, macro, crypto and machine learning appear as bodies of evidence, while market data quality,
overfitting and execution appear through single papers, so those briefs are short and say so. Third,
the general-finance literature is where ESG and text-signal results with attractive numbers are
published, so publication bias is real in exactly those slices; those briefs are written
accordingly. Fourth, the lens is a research layer, so a finding whose only consequence is a matching
engine, a gateway or a colocation decision is recorded as having no landing here - that is a scope
statement, not a judgement that the finding is wrong.

None of these documents contains trading advice or a profitability claim. They are statements about
mechanisms, measurement and evaluation design, and every one of them is falsifiable against the
cited paper.
