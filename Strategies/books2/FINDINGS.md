# FINDINGS - what the q-fin.GN corpus says this project should change

This is the consolidated, triaged output of the reading in this folder. Each of the
28 briefs ends with a take-away table - one row per paper read, shaped
"Finding | Where it lands | What to do". This file is the register across all 28:
390 rows collapsed to the distinct things that can actually be done, sorted by what
can be done about each one.

It is a todo list, not a second copy of the briefs. An item appears here once, names
the briefs that support it, and carries a status that says whether anything is left.
Three things are deliberately true of it:

- **Nothing is inflated.** Where a brief asked for something the repo already does,
  the row appears under section 6 as a corroboration, not under the work sections.
- **Nothing is invented.** Where a paper's only consequence is execution, the row is
  under section 7 as a recorded absence, not retargeted at a path that does not exist.
- **Provenance is marked on every row.** `[verified]` = the code was re-read this pass
  and checked at the line cited. `[reported]` = a brief's claim, grounded in the paper
  and in a path that exists, but not independently re-checked here. **Do not act on a
  `[reported]` row without opening the file.**

**Relationship to `Strategies/books/FINDINGS.md`.** That register covers the wider
`E:\fin paper` crawl (4,372 papers, 19 categories) and, between 2026-10-03 and
2026-10-04, landed two in-place fixes, five confirmed defects, an eighteen-row
methodology backlog and fifteen enhancements. This corpus is a different slice
(`q-fin.GN`), and it overlaps that one: **47 of the 390 rows here name a surface the
books backlog already landed** (section 6). Those are corroboration, not new work.
A third reading of this same harvest exists for `nautilus_trader` under its own
`strategies/books2/`; it is an execution-layer brief and shares the corpus, not its
conclusions.

---

## 0. The headline: the briefs under-credit the landed surface

Every row in this register was written by a reader who had the papers in front of
them and a map of the repository's paths, but not a reading of each module's current
behaviour. The first thing this register did was check the highest-impact rows
against the live tree. Of the **17 most consequential rows sampled, 6 are refuted
outright, 1 describes the design as intended, 6 are partly true with a smaller
remaining gap than stated, and 4 are real gaps.**

| # | The brief's claim | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | `kyle_lambda` is positive by construction, no direction control | PARTIAL - default `direction="sign_dp"` is; a `direction="lagged"` option already exists | `tradingagents/strategies/liquidity_risk.py:390,418-421` |
| 2 | Liquidity cost is a flat `cost_bps` and the value is not shown | PARTIAL - flat `cost_bps=10.0` plus an additive illiquidity term; `with_without_cost_table` prints the bps | `evaluate.py:37`; `signal_analysis.py` |
| 3 | The snapshot tool does not return a label's provenance | PARTIAL - the tool exists and emits as-of / latest-row / forming-bar notes, but no vendor or observed-vs-reconstructed label | `agents/utils/market_data_validation_tools.py:11`; `dataflows/market_data_validator.py:174-191` |
| 4 | `_selection_threshold` is an unnamed hard-coded constant | REFUTED - it is an explicitly named function | `tradingagents/strategies/evaluate.py:142` |
| 5 | `LIMITS_KEYS` carries no tail-budget or max-drawdown keys | REFUTED - both keys are present | `tradingagents/strategies/risk_governor.py:23-24` |
| 6 | Black-Litterman confidence is only tunable by overloading `tau` | REFUTED - `view_uncertainty_omega` is a per-view confidence; `tau_scale` is separate | `tradingagents/strategies/portfolio_optimizer.py:319,321` |
| 7 | The refusal ledger is off by default, so refusals go unmeasured | CONFIRMED - `enable_refusal_ledger` defaults False | `tradingagents/strategies/refusal_ledger.py:99` |
| 8 | The volatility switch has no default-neutral guard | PARTIAL - the switch exists (default `close`); `vol_pct` drives `regime_label` but **not** `position_scale`, which uses log-returns | `tradingagents/strategies/overlays.py:106,130,131` |
| 9 | `coverage_window` has no padded/imputed field | PARTIAL - `universe_label` returns `survivor_only` as claimed, but `padded_days` already exists | `tradingagents/strategies/coverage_window.py:55,157` |
| 10 | `config_robustness` does not flag an edge-of-box best cell | REFUTED - `edge_flag` and a cluster/plateau-spike read both exist and reach the note | `tradingagents/strategies/config_robustness.py:19,44` |
| 11 | `parity_violation` hard-codes `r = 0` with no carry term | REFUTED - `r` is a parameter; the pricing carries a `k*exp(-rr*tt)` forward term and a dividend | `tradingagents/strategies/options_surface.py:584,611` |
| 12 | `regime_paths` prints two unreconciled vocabularies | CONFIRMED as designed - Path A label + Path B axes + a `disagree` flag, no merge | `tradingagents/strategies/regime_score.py:765` |
| 13 | The spread/impact reads are printed without holder concentration | CONFIRMED gap - the reads exist; the tool prints them without `ownership_hhi` | `tradingagents/strategies/liquidity_risk.py:441,574` |
| 14 | `book_correlated_stress` tests channels separately | PARTIAL - it aggregates the whole book via `portfolio_returns`; no common-factor overlap share is named | `tradingagents/strategies/book_risk.py:148,163` |
| 15 | Any reported hit rate lacks its grounding verdict | REFUTED - `report_materiality_verdict` exists behind `enable_materiality_verdict` | `agents/utils/report_verifier.py:917` |
| 16 | `get_shift_detection` labels LZ complexity with a hand constant | CONFIRMED - `lzc > 0.9` decides `random/inefficient` vs `structured` | `agents/utils/analysis_tools.py:11837` |
| 17 | `polymarket` reports one rung of a ladder as "the" probability | CONFIRMED - `float(prices[0])` / `outcomes[0]` of one market | `tradingagents/dataflows/polymarket.py:122` |

**What this means for using the register.** A row is a lead, not a spec. The reading
was done from the papers, so it is strongest on *what the literature establishes* and
weakest on *what this repository already does about it*. Before acting on any row,
open the file, as the provenance tag says. Row 16 and row 17 are the two the sample
promoted to defects; the rest of the confirmed gaps are in section 2.

---

## 1. How to read a row

- **`[verified]`** - re-read at the cited line this pass.
- **`[reported]`** - a brief's claim; the path exists, the behaviour is not re-checked.
- **`[NN]`** - the brief that carries the full argument and the page-anchored citation
  (`Strategies/books2/NN_*.md`).
- **`[landed in books/]`** - the `E:\fin paper` register already shipped this surface.

A `- [ ]` item is work. A `- [x]` item is already true of the repo and is listed so
it is not "fixed" a second time.

**When a row is taken.** Follow master rule 1b (a calculator earns its place through a
tool, and a tool through a prompt) and master rule 9 (the change lands with every doc
it invalidates, in one commit). A row that names a path is a lead: confirm the module
still has that symbol before writing anything.

---

## 2. Confirmed defects and misleading reads

The smallest section, and the only one that is purely a fix list. Four rows survived
verification as real gaps; two of them (`C1`, `C2`) are defects the corpus names
exactly.

| # | Defect | Fix | Source |
| --- | --- | --- | --- |
| C1 | **`get_shift_detection` labels LZ complexity with a hand constant.** `analysis_tools.py:11837` prints `random/inefficient` above `lzc > 0.9` and `structured` below. A complexity statistic is only interpretable against a null calibrated at the same series length, and `complexity.py` has no minimum-length refusal either - finite-size bias grows with smoothness (`+0.075` at `H=0.5`, `+0.323` at `H=0.9`). `[verified]` | Calibrate the cut on surrogate series of the same length and print the band beside the number; give `permutation_entropy` / `approximate_entropy` / `lz_complexity` a length floor tied to the bias table and return `None` below it. | [16], `2512.02352v3` |
| C2 | **`polymarket` reads one rung of a ladder as the probability.** `polymarket.py:122` takes `float(prices[0])` and `outcomes[0]` of a single market. A mutually exclusive ladder is a distribution, and its implied median is tail-robust; a single rung is not the same number. `[verified]` | When a topic returns several rungs of one ladder, normalise the rungs and report the implied median; label a "will X occur by date Y" contract as a deadline contract rather than a probability of X. | [21], `2609.23969v1`, `2605.00493v2` |
| C3 | **The liquidity reads carry no holder concentration.** `roll_spread` / `spread_estimate` / `amihud_illiquidity` exist and `ownership_hhi` exists, but the liquidity tool prints the first three without the fourth, so a concentrated holder base is invisible next to the spread. `[verified]` | Expose `ownership_hhi` beside the spread/impact read, so a concentrated-collateral name carries its concentration with its cost number. | [09], [25] |
| C4 | **The market snapshot has no label provenance.** The validator emits as-of, latest-row and forming-bar notes but not the vendor, nor whether a column is an observed event or a reconstructed state - so a terminal label can be read as ground truth. `[verified]` | Return the label's provenance (vendor, as-of, observed-vs-reconstructed) beside the value. | [27], `2607.02823v4` |

**Two rows that are one decision away from being defects.**

- **`kyle_lambda`'s default is the non-identified estimator.** The default
  `direction="sign_dp"` builds the regressor as `sign(delta_price) * volume`, so lambda
  is positive by construction; the identified form (`direction="lagged"`, sign from the
  prior bar) exists but is not the default. `[verified]` The literature rejects the
  default. **Whether the default moves is the owner's call** - it changes a published
  number. [23], [25], `1807.08278v3`
- **`book_correlated_stress` aggregates the whole book** rather than testing the direct
  and common-factor channels separately, and names no overlap share. `[verified]` The
  corpus asks for the overlap share beside the shock. [01], `1306.3704v1`

---

## 3. Owner decisions - the corpus raises a policy question

Each of these is real, cited, and changes how a number is computed or reported. They
are grouped so they can be decided in a batch. None should be landed on sight.

- [ ] **D1. The `kyle_lambda` default** (section 2). Move it to the identified form, or
  keep `sign_dp` and label it. `[verified]`
- [ ] **D2. Turn the refusal ledger on.** `enable_refusal_ledger` defaults False, so a
  tradability gate's precision is assumed rather than scored; the corpus's own point is
  that a refused candidate is measurable only if recorded. `[verified]` [20], [26]
- [ ] **D3. The deflation policy is a priced choice.** Going from a 1.96 to a 3.0
  hurdle moves the false-discovery rate from 8.8% to 1%. `_selection_threshold` is
  already a named function `[verified]`; the open question is whether the *value* is a
  policy constant, named in review. [28], `2209.13623v3`
- [ ] **D4. Cost and participation parameters are owner-set and must be printed.**
  `cost_bps=10.0` (flat), `fee_bps=0.0`, and a participation cap decide every
  cost-adjusted statistic; the corpus's finding is that a flat cost cannot express a
  flow-regularity-dependent cost, so the assumption must travel with the number. [20], [23]
- [ ] **D5. A volatility-estimator switch needs a default-neutral guard.** Flipping
  `close` to `ewma`/`garch` should move the label percentile, not only the position
  scale; today `vol_pct` drives `regime_label` and the scale uses log-returns.
  `[verified]` [14]
- [ ] **D6. The sentiment overlay's IC floor is provider-specific.**
  `fold_sentiment_into_overlay` holds `min_ic = 0.02`; a change of provider is a change
  of protocol that invalidates prior calibration, so the floor must be re-measured per
  provider and the provider set recorded on it. [11], `2609.31013v1`
- [ ] **D7. Report BIC beside a caller-supplied state count.** The number of regimes is
  a model-selection choice; it is not identified by the data, and a caller-supplied `K`
  is currently presented as if it were. [24], `0710.0745v1`
- [ ] **D8. Treat a lone R/S Hurst as a diagnostic, not a signal.** `hurst_exponent` is
  honestly documented as rescaled-range `[verified]`, and the repo's own measured
  `hurst` component is rank IC -0.008 with a deflated Sharpe of -1.5. Adding a
  detrended-fluctuation / first-passage alternative with its i.i.d. null is an
  enhancement; retiring the R/S value from a mean-reversion claim is a decision. [13], [14], [16]
- [ ] **D9. Cap conventionally-favoured low-volatility names as crowded.** Objective
  risk rules concentrate holdings into estimation noise; the corpus's reading is that a
  low realised-vol name is a crowded name and deserves the same cap as any concentrated
  exposure. [20], `1004.1670v4`

---

## 4. New work - producers and reads the repo does not have

Grouped by the surface the row lands on. Each item is small, cited, and additive.
Everything here is `[reported]` unless marked.

### 4.1 Tail and risk

- [ ] Race the tail exponent against **log-normal and stretched-exponential** rivals; the
  power law wins only a truncated tail (~20%) and then not significantly, and the repo
  fits a GPD (`book_risk.extreme_quantile_var`) without ever comparing an alternative. [13]
- [ ] **Publish a CVaR with its observation count and a robustness flag**; one outlier can
  make historical ES arbitrarily large and estimates below ~2,000 observations are biased
  low. Keep the `tail_risk` refusal floor and surface `window["n"]` with every number. [22]
- [ ] Record the **mixture-of-exponentials** alternative beside the single GPD fit and let
  the coverage test choose between them. [06]
- [ ] Add a **rolling tail-index / tail-dependence** read beside `copula_scenarios`, and
  report the copula family and the conditioning convention with it. [22], `2203.10777v1`
- [ ] For an energy-linked book, compute the tail through the **joint covariance** and print
  the joint-versus-independent VaR pair: dropping the power-gas correlation nearly doubles
  three-year VaR. [18], `0910.0236v3`
- [ ] Add a **flight-to-quality / spread-narrowing** stress branch; the book stress model
  applies only adverse uniform shocks. [23], `2601.08263v3`
- [ ] Carry a **volume-uncertainty** term beside the tail number: market volatility depends
  on trade-value and volume moments, not one sigma. [10], [22]
- [ ] Report a **distance-to-threshold / transition width** beside a crash estimate, never a
  single point. [17], `1810.07690v2`
- [ ] Mark any conditional (co-risk / contribution) measure as **not classically
  backtestable** by violation counts. [22], `2206.02582v2`

### 4.2 Covariance and the correlation graph

- [ ] Add an explicit **positive-semidefinite test** (Cholesky, then eigenvalue flooring)
  before any variance-minimising weight; real covariance matrices carry negative
  eigenvalues of order 1e-8 that inflate a variance-minimising score by orders of
  magnitude. [17], `2007.01430v1`
- [ ] Report the **condition number** of the shrunk matrix next to an allocation, so a
  rotated book is visible. [10], `2107.06194v5`
- [ ] **Partition the covariance by a stress state**: the stock-bond correlation flips sign
  with stress, so the diversification benefit is conditional and one unconditional matrix
  is the wrong input. [13], `1310.4538v2`
- [ ] Prefer a shrinkage estimator with an explicit **missing-data path** over previous-tick
  synchronisation (under asynchronicity over 80% of one-second returns are missing and
  naive correlation is biased to zero). [26], `1803.04894v2`
- [ ] Compare the observed spectrum against a **herding / one-factor null** before reading
  sector structure into it, and pair `panel_spectrum` with `spectral_null_band`. [01], [06]
- [ ] Add a **time-varying crypto beta** and an out-strength ranking beside `panel_spectrum`
  (crypto influence is a shifting network). [03], `2606.25466v3`
- [ ] Offer the restricted **factor-GARCH covariance** as an alternative to the Ledoit-Wolf
  path for large panels (six parameters, daily betas). [14], `1609.07051v6`

### 4.3 Microstructure, execution and impact

- [ ] Extend `book_depth_read` from a top-of-book imbalance to a **multi-level imbalance
  vector**, and say when only level 1 is available rather than presenting it as the book.
  Depth beyond level 1 carries price information and cuts out-of-sample RMSE by 65-75%
  on large-tick names. [25], [26], `1907.06230v2`
- [ ] Make `order_imbalance` **state its direction source**; when direction is inferred from
  a book feed, downgrade to `unavailable` rather than emit a signed pressure. [25]
- [ ] Add a **trade-sign imbalance** series and the metaorder-scale persistence statistic;
  order flow is split, not random, and the raw tier share is not the flow read. [25], `2308.01112v1`
- [ ] Replace the single `square_root_impact` constant with a **calibrated (k, psi) pair and
  an explicit transient-decay term**, recording the exponent and aggregation interval in
  the fill record. Impact is concave and transient, not linear and permanent. [23], [25]
- [ ] Use the **Almgren-Chriss temporary-impact** term for intermediated/OTC flow; treat
  `square_root_impact` as a permanent-impact model with no decay. [23], `1807.08278v3`
- [ ] Express the cost as **order theta or order sqrt(theta) by flow regularity**; a flat
  `cost_bps` cannot express it, so record the flow-smoothness assumption beside the number. [23]
- [ ] Add a **locked/crossed-quote and spread-shock state** to `aggregate_quality` /
  `disagreement_flag`, so a crash window is flagged rather than traded (spread +141.60%,
  locked/crossed 8.01 to 24.40%). [26], `1211.6667v1`
- [ ] Cross-check `kyle_lambda` against `spread_estimate` on the same name-period; refuse to
  publish one without the other when they disagree by an order of magnitude. [25], `0903.2428v1`
- [ ] Model a forced seller with `days_to_absorb` **consuming a fixed fraction of ADV per
  interval** and state the participation assumption; never spread a liquidation linearly
  over weeks. [25]
- [ ] Express the `limit_gate` threshold **in ticks as well as percent**, so a one-tick-wide
  name is not treated like a wide-spread name. [25], `1012.0349v4`
- [ ] Make the spread/impact term **price-level-dependent** for binary contracts: the quoted
  spread widens to 1,300-1,800 bps below price 0.10, so a longshot costs what the venue
  charges, not a flat fee. [21], `2604.24366v2`

### 4.4 Regime and change-points

- [ ] Add a **faster-than-exponential-growth axis** beside `trend_strength` and `choppiness`,
  and keep fair-value language out of the label: a bubble is a dynamic regime, not a
  mispricing. [05], `1404.2140v1`
- [ ] Gate the bubble detector on its **validity filters** (`0.1 <= m <= 0.9`,
  `6 <= omega <= 13`, `B < 0` and `b >= 0`) before any label is emitted. [05], `1108.0099v3`
- [ ] Keep the bubble flag **conditional** in `regime_gate_read` and hold exogenous-shock
  risk in the separate `risk_governor` limits: the model covers endogenous crashes only,
  about two-thirds of them. [05], `1107.3171v3`
- [ ] Report the **warm-up prefix** of the walk-forward HMM as unmeasured and carry the
  re-estimation cadence in the read's basis; the early estimates are unstable and online
  re-estimation is what traded. [24], `2309.00875v3`
- [ ] When a macro or stress covariate is added, report the **with-covariate and
  without-covariate** result per series and return absent rather than neutral where no
  regime is visible. [24], `2604.21734v1`
- [ ] Test `hmm_regime` / `bocpd` at **several sampling frequencies** before fitting one drift
  to an intraday series; flow potentials switch between single-well and double-well with
  window length. [26], `2509.02941v1`
- [ ] Treat **market-structure events** (an index future listing, a rule change) as regime
  breaks in the change-point read rather than assuming a stationary generator. [14], `2109.15060v1`
- [ ] Prefer the **causal sign/spectral read** over a rolling correlation when the question
  is a change of relationship; a rolling window lags a regime change by construction. [24], `physics/0607197v1`

### 4.5 Forecasting and volatility

- [ ] Declare a **naive/random-walk benchmark per family** in `BENCHMARK_BY_FAMILY` and refuse
  to report a forecast score without it; baselines are under-used in the published field. [04], `2503.01591v1`
- [ ] Score a **multi-horizon** forecast with the declared rules rather than collapsing it to
  one horizon (multi-horizon probability term structures are learnable). [04], `2111.09902v4`
- [ ] Score a volatility forecast against the **realized horizon scaling per instrument**
  rather than assuming square-root-of-time; fitted exponents clustered at 0.43-0.54 across
  assets. [17], `2505.13019v2`
- [ ] Report the **drift term** as part of the forecast score record instead of hiding it
  inside a fixed lookback; non-stationarity imposes an unavoidable error floor of order V. [16], `2512.23596v2`
- [ ] Add a **joint long-memory-and-multifractality** read (a generalized Hurst exponent
  `h(q)` through the partition function) beside `memory_parameter`: conventional
  long-memory tests over-reject under multifractality, and eleven of twelve FX pairs have
  no return long memory once multifractality is modelled. [13], `1601.00903v1`
- [ ] Add a **detrended-fluctuation Hurst** and, separately, a first-passage exponent with
  its i.i.d. null, beside the rescaled-range read. [13], [14], `2512.02352v3`
- [ ] Expose **multi-scale persistence**; persistence drifts between 2-4 day and 64-128+ day
  shocks, so a single GARCH persistence is not structural. [14], `2402.01354v2`
- [ ] Add a **self-excitation / branching-ratio** diagnostic beside the memory parameter and
  report the ratio against 1. [25], `2509.21244v1`
- [ ] Add a **signed return-volatility correlation** estimator beside the volatility proxies
  (herding reproduces the leverage effect with tau about 19 days). [06], `1407.5258v1`
- [ ] **Condition `normality` on an observable stress level** and report both the conditional
  and unconditional verdicts; 17% of stress-ordered equity windows look non-normal against
  83% randomly ordered. [13], `1310.4538v2`
- [ ] Promote the **bipower-proxy jump-share** read behind its gate so a jump is classified by
  its own return profile, not by a news timestamp (only 4.3% of jumps are news-tagged). [14], `2404.16467v1`

### 4.6 Text, sentiment and language models

- [ ] **Persist a cross-provider spread** beside every LLM-derived tone, the way the
  cross-vendor `disagreement_flag` is carried, and treat a model's stated confidence as
  noise (conditioning on it *lowers* agreement from 0.52 to 0.48). [11], `2609.31013v1`
- [ ] Carry the **provider identity** in the debate capability matrix, so an all-one-model
  debate panel is visible as one correlated voice. [04], `2504.10789v1`
- [ ] Record the **model checkpoint, cutoff and window** as provenance of any text factor
  whose IC is measured here, so a stored number can be read back against the information
  it was allowed to see. [11], `2604.21433v1`
- [ ] Add a **task-specific stress / governance lexicon** beside `lm_tone` and version it
  with the existing `DICTIONARY_VERSION` scheme (task-specific dictionaries beat general
  ones: 0.79 vs 0.63 test accuracy). [11], `2101.00719v1`
- [ ] Encode **narrative-dimension exposure** as a separate statistic and sweep horizons
  before assuming a text feature that helps at one month helps at one quarter. [11], `2511.15214v2`
- [ ] **Screen text-derived features for memorisation** with the `leaky_pipeline` null and
  log anonymisation as a test rather than a fix. [08], [11], `2309.17322v1`, `2512.23847v2`
- [ ] Add a **human-agreement / macro-F1 validation row** for any text classifier that becomes
  a feature before it is trusted as a score input. [11], `2607.13968v1`
- [ ] Extend the fail-closed capability matrix so a model is only allowed the text tasks it
  can do - comprehension of short narrative, not free-form reasoning over long
  table-heavy filings (knowledge errors 50-55%). [11], `2310.08678v1`

### 4.7 Data quality and complexity

- [ ] Add a **null-band wrapper** for the complexity statistics that returns the statistic,
  its empirical i.i.d. null band and the tail size together, and refuses below a stated
  minimum length. This backs C1. [16], `2512.02352v3`
- [ ] Add a **cross-sectional entropy leg** beside `average_pairwise_correlation` and
  `concentration_hhi`, carrying a declared universe and microstate count; cross-sectional
  entropy varies ten times more than index volatility. [14], [16]
- [ ] Add a **negative-tail correlation estimator** beside `average_pairwise_correlation`
  and publish both, labelled; it is more sensitive than Pearson and Pearson misses the
  2015-2016 crash. [01], `2510.21165v1`
- [ ] Add a **mutual-information screen** beside `residualize_returns` / `industry_neutral_z`;
  a near-zero linear correlation must not be read as independence. [16], `1711.06185v3`
- [ ] Add an **ingestion-time range and identity check** before a row can reach a backtest:
  one erroneous data row can erase a strategy. [28], `2306.01740v4`
- [ ] Report an explicit **imputed fraction** per input and add an imputation-method
  sensitivity run at the decision level. [27], `2309.17379v1`
- [ ] Enforce and log **maturity and moneyness filters** as an input-quality input before any
  option surface fit. [27], `2501.17490v2`
- [ ] Record **order-lifetime and modification-count coverage** as an input-quality line, so a
  flow statistic can be marked stale when the tape is dominated by fleeting orders. [25], `2507.22712v2`
- [ ] **Encode missingness as a feature** rather than imputing it away silently, and report a
  fitted tail parameter with any rare-event probability. [22], `1412.5351v1`
- [ ] Record whether each return series feeding risk is **trade-weighted or time-weighted**;
  a VaR inherits the price-probability definition behind it. [22], `2101.08559v3`
- [ ] Add an **edge-count and node-isolation monitor** on the top-correlation graph as a
  risk-regime read (edges 455 to 294, isolated nodes 39.52% to 59.97%), labelled
  unvalidated. [16], `2308.02914v2`

### 4.8 Portfolio, sizing and construction

- [ ] Add an **absolute-position budget** (not only a volatility scalar) to the sizing
  contract, so a position cap doubles as a tail read. [23], `2207.09951v1`
- [ ] Add a **volume-uncertainty haircut** alongside `composite_position_size` and
  `risk_of_ruin`. [10], `2507.21824v1`
- [ ] Carry a **skew term** beside the ATR basis so `build_position_contract` does not treat
  a negative-skew book as symmetric. [10], `2310.12333v1`
- [ ] Publish `effective_holdings` and `weight_hhi` **per regime**, and let `min_names_ok`
  depend on the regime rather than one threshold. [10], `2204.13398v1`
- [ ] Add a **continuous eligibility score** beside `winsorize` / `neutralize_book`, so
  exclusion is a graded axis rather than a binary filter. [10], `2512.22858v2`
- [ ] Split `mean_correlation` and `correlation_penalty` into **positive and anti-correlation
  halves** instead of one signed average (anti-correlation is up to 43% of pairs, is
  scale-free, and moves only on declines). [01], `2404.00028v2`
- [ ] Report **agreement across the engines** in `engines_for_analyst`, so a
  correlated-but-confident scorecard is visible before it becomes a book. [10], `2604.02279v2`
- [ ] Cap leverage on **binary / event positions at one** and size from premium-at-risk. [21], `2605.10400v2`
- [ ] Base the volatility-target scale on **autocorrelation and clustering**, not a single
  realised-volatility number. [14], `2504.20116v1`

### 4.9 Evaluation, overfitting and research integrity

- [ ] Add a **re-optimisation stability diagnostic** over shifted windows, beside
  `cscv_pbo`; backtested parameters never converge under adaptation. [06], `2202.00831v1`
- [ ] Report a **per-period information coefficient** and the out-of-sample split beside the
  pooled number (returns decay about 50% far from the original sample and 25% by year
  three). [28], `2209.13623v3`
- [ ] Add a **false-acceptance-rate row** beside `win_rate_by_rating` / `score_distribution`,
  and stop publishing bare accuracy for any rare-event score. [04], [19]
- [ ] Log **every generative run** with `trial_ledger.record`, not only the reported one, so a
  downstream inference is deflated by the true number of runs (G-hacking is the selective
  reporting of one of many runs). [28], `2503.16974v4`
- [ ] Record each **re-optimisation** as a separate trial so the ledger accumulates the true
  number of effective searches. [06], `2202.00831v1`
- [ ] Estimate and record a **finite IC half-life** when sizing and when setting a strategy's
  expected life; signals decay as adoption rises. [08], `2605.23905v1`
- [ ] Run the null harness across **several reference classes** and report the band, not a
  single synthetic path; a robustness conclusion is conditional on the null model. [28], `1104.4249v2`
- [ ] **Pin the dataset digest** with the tamper-evident ledger and compare the artifact, not
  the declaration, so a re-run must reproduce the selected result. [28], `2306.01740v4`
- [ ] Hold out the **most recent period** with `oos_split`, re-run the frozen parameters, and
  require it to pass before promotion. [28], `2306.01740v4`
- [ ] Treat **genetic-algorithm indicator parameters** as in-sample artefacts and evaluate
  rules on an outlier-robust forward-return distribution. [08], `2206.12282v1`
- [ ] **Charge search effort against the result**: a wide search cannot be presented as a
  single clean result. [17], `2008.08669v1`
- [ ] Require an **explicit warm-up** before averaging IC, and refuse a cross-section that
  falls below the period floors. [06], `1305.2121v3`

### 4.10 Crypto, energy, commodities and prediction markets

- [ ] **Split crypto universes into coin and token classes** with separate screen rules; they
  are different size distributions and growth regimes. [03], `1803.03088v2`
- [ ] Add an **LP / convexity read** that mirrors `gamma_regime` for a quoted price range (a
  constant-product LP position is short variance and short convexity). [03], `2106.14404v1`
- [ ] Carry **tick-range concentration and price-range exposure** as venue liquidity inputs. [03], `2106.14404v1`
- [ ] Add **fork and airdrop event rows** that fire on the chain clock, not the equity
  calendar. [03], `2303.08748v3`
- [ ] Size crypto positions under a **kinked rate curve**, not an average rate (utilisation hit
  100% and borrow rates jumped two orders of magnitude). [03], `2303.08748v3`
- [ ] Add a **chain-reorg / double-spend** scenario and a **DeFi liquidation-cascade** stress
  scenario keyed to the collateral-to-borrow ratio. [03], `2004.04605v2`, `2009.13235v6`
- [ ] Estimate a **long-memory parameter on the gas series** and keep gas as a cost, never a
  hedge. [03], `2406.06524v2`
- [ ] Extend the energy/materials driver reads with a **front-versus-fourth curve-state flag**,
  so a carry read is not silently reported as a spot move. [18], `2308.00383v1`
- [ ] Route energy/materials names through **mid-cycle normalization** and carry the min/max
  span, not only the median: a single-run-rate DCF overstates value at a pricing peak. [18], `2112.09816v2`
- [ ] Add a **commodity-spread scenario leg** beside the bear/base/bull range, with the
  break-even spread as the strike. [18], `2112.09816v2`
- [ ] Run `mean_reversion_verdict` / `ar1_half_life` on the **driver series** that feed the
  sector read and publish the half-life beside the verdict. [18], `2605.13320v1`
- [ ] Add a **volatility-decay note** to the leveraged-ETF risk profile (`-(beta^2 - beta)/2`)
  and refuse to compare a leveraged ETF's return against a leveraged index without it. [18], `1610.09404v1`
- [ ] Register **"commodity financialization" and "energy transition"** as themes and route a
  rotation read through `relative_rotation`, so the flow-direction caveat travels with the
  theme mention. [18], `1607.07582v1`
- [ ] Feed a **matrix-HAR multi-horizon realized-variance** forecast through `rv_forecast` /
  `publish_realized_volatility_forecast` for energy names, and register the
  rolling-variance benchmark for comparison. [18], `2606.05991v1`

### 4.11 ESG, climate and carbon

The repo has no ESG, climate or carbon surface at all, and the brief's finding is that it
should keep it that way as a *provider field* while routing carbon exposure through
machinery that already exists. `[reported]`

- [ ] Keep the documented **"ESG deliberately absent"** note; if a rater is ever wired,
  version every field by provider and never merge providers (ESG rating effects flip when
  the provider is swapped). [15], `2606.31469v1`
- [ ] Surface the existing **talk-versus-walk gap**: `text_factors.divergence(filing, news)`
  already returns `tone_gap`, and `get_disclosure_tone` already calls it - no new ESG tool. [15]
- [ ] Route a **carbon-contagion** leg to the existing correlation (15) and concentration (10)
  categories, whose pins and units are already declared, rather than adding an engine. [15], `2503.10644v1`
- [ ] Extend the **news tag vocabulary** so climate regulation is a `regulatory_legal` news
  category, and carry ETS II 2027 / the 2030 uncapping as dated calendar events. [15], `2212.11787v1`
- [ ] Record that a **carbon price would be a second energy-sector driver** (`SECTOR_DRIVERS`
  maps XLE to `wti` only), and that `THEME_REGISTRY` has no climate/carbon id. [15]

---

## 5. Label and disclosure discipline - the additive majority

Most of the 390 rows ask for a read to say what it is. These are one-liners: a basis
string, a provenance field, a number printed beside a value. They are cheap, additive,
and they are what stops a corrected number from being silently read as the old one.

- [ ] **Name the estimator** in every volatility read's `basis` and rank percentiles only
  against windows from the same estimator (range estimators sit 1-3 tenths below
  close-to-close at every window). [14], `2205.00104v1`
- [ ] **Label the window and the sampling frequency** with every rolling read (a panel
  statistic reports how far its window is from the current regime; complexity needs the
  window length to pick the right null row). [16], [24], [27]
- [ ] **Print the cost, fee and participation values used** beside every cost-adjusted
  statistic, and the flow-smoothness assumption beside the cost. [20], [23]
- [ ] **Label retrospective diagnostics as retrospective**: `bocpd`, `cusum`, `ewma_control`
  are not crash warnings, and a break is an interval, not a trigger. [05], [24]
- [ ] **State the aggregation horizon and valid bar count** with every regime read, and do not
  fit a state model on the finest available bar. [24]
- [ ] **Label the volatility state as a volatility state**, not a bull/bear forecast. [24]
- [ ] **Report which axis** produced a `regime_factor` reduction (worst-of three axes) rather
  than presenting the multiplier as a constant. [24]
- [ ] **Print the threshold used** for a limit gate, a tail cut and a severity rule, and state
  the short-interest percentile as a distinct state. [20]
- [ ] **Store the information-arrival timestamp** with any flow score and refuse the score
  when the anchor is ambiguous. [19], `2605.02286v2`
- [ ] **Report the in-scope sample and every exclusion stage with its count**, and refuse a
  statistic padded before first observation (in-scope attrition left 0.7% of candidates
  computable). [19], `2605.00459v1`
- [ ] **Tag every backtest/simulator run with its data source**, and re-run under perturbed
  intensities and fees before a deflated Sharpe is treated as evidence. [25], `2207.09951v1`
- [ ] **Record the label's provenance** on the market snapshot (backs C4). [27]
- [ ] **Report the basis/fit window** on any calibration, and flag a calibration quoted
  without the window it was fitted on. [27], `1805.12110v1`
- [ ] **Surface `vendor_skip_reason`** in the evidence block, so a number computed from a
  degraded vendor chain says so. [27], `2606.31675v1`
- [ ] **Keep the sweep's CONFIRMED/SUSPECT rows** in the standard verification so null results
  and failed gates are visible. [27], `2607.02823v4`
- [ ] **State the direction source** on an imbalance read and downgrade to `unavailable` when
  it is inferred. [25]
- [ ] **Record the sampling interval** that produced each bar and refuse a waiting-time
  statistic computed from second-rounded times. [25], `1312.2004v1`
- [ ] **Print the `cost_bps`/`fee_bps` and the participation cap** used beside every
  cost-adjusted number. [20]
- [ ] **Record the model, temperature, seed policy and cross-run spread** with
  `record_condition_run`, aggregate 3-5 runs before they become labels, and never record a
  single completion as a label (model output is stochastic even at temperature zero). [28], `2503.16974v4`
- [ ] **Report per-signal reliability flags** beside a text read, so a degraded read shows up
  before the PnL does. [11], `2412.01069v2`

---

## 6. The corpus corroborates the repo (already true - do not "fix" these)

These rows ask for something the repo already does. They are listed so that a later reader
does not implement them twice, and because a corpus that independently arrives at the same
answer is evidence the design is right.

**Verified against the code this pass (`[verified]`):**

- [x] **`sentiment_score` already refuses to mix scales.** `SCALE_TABLE` pins `unit`/`eodhd`/
  `alpha_vantage` at -1..1 and `gdelt` at -100..100, every leg goes through
  `normalise_sentiment`, and two sources in one read are refused rather than averaged
  (`sentiment_score.py:56,80,399-402`). Brief 11's two rows are already the behaviour.
- [x] **`regime.hmm_transition_read` already reports per-state persistence and duration.**
  `stay_probabilities` (per state), `expected_duration` (per state) and the current
  `persistence` are all returned (`regime.py:2248-2259`). Brief 24's row is already done.
- [x] **`regime_score.regime_paths` already prints both vocabularies unreconciled**, with a
  `disagree` flag (`regime_score.py:765`). The brief's ask is "keep it" - it is kept.
- [x] **`config_robustness` already flags an edge-of-box best cell and an isolated spike**
  (`config_robustness.py:19,44`).
- [x] **`coverage_window` already emits `padded_days`**, and `universe_label` returns
  `survivor_only` as a fail-safe (`coverage_window.py:55,157`).
- [x] **`black_litterman_weights` already takes a per-view confidence**
  (`view_uncertainty_omega`, `portfolio_optimizer.py:319`) - `tau` is not the only lever.
- [x] **`report_verifier` already carries the materiality verdict and the conflict checks**
  (`report_verifier.py:917,272,338`), gated by `enable_materiality_verdict`.
- [x] **`evaluate._selection_threshold` is a named function**, not a raw constant
  (`evaluate.py:142`).
- [x] **`risk_governor.LIMITS_KEYS` already carries the tail-budget and max-drawdown keys**
  (`risk_governor.py:23-24`).
- [x] **`parity_violation` takes `r` as a parameter and carries a forward term**
  (`options_surface.py:584,611`) - no hard-coded zero-rate pilot.
- [x] **`mean_reversion.memory_profile` already pairs the roughness (R/S) read with the memory
  parameter**, and both are documented as such (`mean_reversion.py:113,184-193`).
- [x] **`kyle_lambda` already has the identified `direction="lagged"` option**
  (`liquidity_risk.py:418-421`); only the *default* is the non-identified estimator.

**Already landed by the `Strategies/books/` register (2026-10-03/04)** - 47 rows here name
these surfaces. Treat them as corroboration and do not re-do them:

- `memory_parameter(on_volatility=True)` (C6), `rv_forecast(log_rv=True)` (C5),
  `n_effective` / `effective_candidates` (C4), `var_coverage_test(simulate=True)` (C9),
  `copula_scenarios` model-risk (C11), `IMPACT_MODEL_SHAPES` (C13), `PARTICIPATION_CAP`
  (C14), `kyle_lambda(direction=)` (C15), `correlation_matrix` kurtosis (C17),
  `ols_factors(hac=True)` (C18);
- `cscv_pbo` (E1), `min_track_record_length` (E2), `excess_accuracy` (E3), the H3 null
  harness (E4/H3), the cost-floor precondition (E5), `diebold_mariano` + `mz_regression`
  (E6), the CRPS/QLIKE producers (E7), `equal_weight_combination` (E8), Ledoit-Wolf in the
  optimiser (E9), `regime_stability_check` (E10), `half_life_for_event` (E11),
  `mp_iid_premise` (E12), the lead/lag `relation` label (E14), `sticky_markov` (E15);
- `deflated_sharpe_ratio` (D1), the G5 gate reading `trial_ledger.trial_stats` (D2), the
  wiring gate's AST detector + `GAP_CALCULATORS` (D3), `universe_label` (D4), the paired
  McNemar/DM tests under FDR control (H4).

**Rows that ask for "no change", explicitly.** Several rows are the corpus confirming the
current design and asking that it be left alone: `stockstats_utils._clean_dataframe`
already counts and logs its forward-fills (C16 refuted in the books register); the
`enable_tail_risk_layer` / `enable_long_memory` gates leaving the roughness read emitted
while the memory record is `unavailable`; and `regime_paths` staying unreconciled.

---

## 7. Recorded absences - no research-layer landing

Eleven rows have no landing here, and the correct response is to say so rather than build a
producer the layer cannot feed. `[reported]`

| Brief | The finding | Why it has no landing |
| --- | --- | --- |
| 01 | Contagion is non-monotone in connectivity, critical degree ~5-10 | No stored directed exposure graph; do not invent a producer without one. Do not drop maturity from any future exposure store (short layers carry 97% of loans). |
| 02 | Overnight funding is the residual of payment imbalance, not a price | No settlement or funding model; do not publish a standalone exogenous funding-rate factor. |
| 02 | Loan maturity is distinct economic structure | No instrument or tenor model; never collapse distinct credit tenors into one synthetic series. |
| 03 | Perpetual funding rates, perp basis, on-chain pool state | `get_crypto_prices` returns OHLCV only and no calculator consumes funding or pool state. |
| 09 | Trained decumulation policies and lattice-DP withdrawal contours | A lightweight deterministic layer cannot re-derive a trained policy or a 4-D lattice; do not surface their outputs as values. |
| 17 | 13 implemented quantum-finance applications, none using machine learning | Do not add quantum tooling; record the classical baseline beside any exotic method and treat a quantum-advantage claim as unvalidated. |
| 21 | Funding cannot impose uniform boundary control under bounded transfers | No funding or perpetual engine; an instrument-design caveat, not a mechanism to model. |
| 23 | Dealer market power moves gilt yields 2.5-5.3 pp | No repo/dealer-network feed and no intermediary-concentration state variable. |
| 23 | Divergence loss is a deterministic function of the price-ratio change | No LP or automated-market-maker module; do not invent one. |
| 23 | Learned quoting under a self-exciting book | Outright quoting policy is an execution-layer artefact; only the penalty and fee-tolerance findings transfer. |
| 16 | Cross-sectional efficiency as normalized Kelly growth | Routed to `signal_analysis.py`; no separate authority. |

---

## 8. Claims refuted or needing verification first

Six of the seventeen sampled rows were refuted outright (section 0), and eleven more were
half-true. Two consequences:

- **The refuted rows are recorded, not complied with.** Implementing `config_robustness`'s
  edge flag, `coverage_window`'s padded field, Black-Litterman confidence or
  `LIMITS_KEYS` would have added a second mechanism beside one that already exists.
- **Every remaining `[reported]` row in sections 4 and 5 has the same risk.** They were not
  re-checked. The pattern of the refutations is specific and predictable: a brief proposes a
  *read* or a *parameter*; the module already returns it under a name the brief did not
  know. Open the file before acting.

---

## 9. Coverage and honest limits

- **Every one of the 390 take-away rows is represented here**, either as work (sections 3-5),
  as a corroboration (section 6), as an absence (section 7) or as a refutation (section 8).
  Section 6's "already landed" list covers 47 of them by surface rather than one by one.
- **17 rows were verified against the code; the other 373 are `[reported]`.** The sample was
  deliberately the highest-impact rows, where being wrong costs the most, and it found the
  refutation rate high enough that the rest should be treated as leads.
- **This register is a reading of a reading.** The briefs are one pass over 292 papers; this
  is a triage of their tables, not an independent re-read of the papers. Where a brief's
  claim matters, its own `## Papers read in depth` section names the paper and the
  limitation it recorded.
- **The corpus is single-market and single-period in most rows** - a great many of the
  findings above carry a named limitation in their brief's `## Caveats`, and those limits
  were not repeated here. Read the brief before acting on a row.
- **The overlap with `Strategies/books/` is named, not resolved.** Where the two registers
  differ, the books register is the one backed by a re-read of the code; this one is the
  newer corpus and is broader on the research side.
