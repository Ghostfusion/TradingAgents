# Measurement findings (WP-10)

**What this document is.** The written finding the plan requires at the end of
Phase C: *"a written finding per engine: which categories survived, which are
redundant, which should be dropped, and what the measured weights are"*
(`IMPLEMENTATION_PLAN.md` §9, Phase C). It is written from one executed run of
the measurement layer, `scripts/score_panel.py`, and it distinguishes three
things on every line:

| Mark | Meaning |
| --- | --- |
| **MEASURED** | computed by the harness over the panel named below, with its `n` |
| **UNMEASURED** | the producer or the vendor leg is not available, with the reason |
| **DECLARED** | the owner's own table or policy, printed because a measurement layer may not invent one |

It never claims a measurement that did not happen. Where a number is
`UNMEASURED`, the reason is stated; where a number is `MEASURED` on a small
sample, the `n` travels with it.

**Run of record** (2026-09-18, engine at `1b8e82d` + the WP-10 work):

```
py -3.12 scripts/score_panel.py --dates 2026-08-06,...,2026-09-17 \
    --symbols-file ~/.tradingagents/cache/panel_universe_sample.txt
py -3.12 scripts/score_panel.py --evaluate-only --dates ... --json
```

* Panel: `C:\Users\vince\.tradingagents\cache\panels\<date>.json` — one file per
  trading date, 30 files, **MEASURED**.
* Cross-section: **149 of 150** requested NASDAQ common stocks (a strided
  sample of the EODHD symbol list), 30 trading dates 2026-08-06 … 2026-09-17,
  **154,188 metric cells**, **MEASURED**.
* Label: **`OK`** — 30 cross-sections, median 147 eligible names, against the
  floors `min_periods=20` / `min_names=100` / `5` names per bucket.
* Cost: **0 API calls** this run (every date was already cached); the first
  build spent **29 dates × (100 + 150) = 7,250 calls** under the vendor's own
  model (`100 + N` per request, 500-symbol cap). The panel is cached per date and
  a second invocation re-fetches nothing — **MEASURED** (29 `dates_fetched`, 1
  cache hit, `api_calls: 0` on the second run).
* **The fundamentals leg is vendor-gated, and this is the measured proof:**

  | probe | result |
  | --- | --- |
  | `GET /api/eod/AAPL.US` (the key the repo already uses) | **200** — the key is live |
  | `GET /api/exchange-symbol-list/NASDAQ` | **200**, 5,485 symbols |
  | `GET /api/bulk-fundamentals/NASDAQ` | **403** `VendorNotConfiguredError` |
  | `GET /api/fundamentals/AAPL.US` | **403** |

  The bulk-fundamentals endpoint needs the **Extended Fundamentals** plan
  (plan §3.2, §15) and this key does not carry it. The panel records the 403 in
  each date's `_meta.legs.fundamentals` and in `_meta.vendor_gate`; the build
  does not crash and does not write an empty panel, and every date is retried on
  the next run. `P0-2` therefore stays open for the reason the plan already
  gave, now with an HTTP status beside it.

---

## 1. `TechnicalScore` — the one engine this panel can measure

**Coverage: 36 of 40 components MEASURED** (the 4 missing are the breadth
category: market-wide A/D, %-above-50d, %-above-200d need a panel the
per-name leg does not fetch, and `vol_percentile` is not on the run's
component path). Everything below is a Spearman rank IC against the 5-day
forward return, 25 usable cross-sections, 147–149 names each.

| component | category | IC | ICIR | spread D10−D1 | mono | turnover | persistence | OOS | DSR | CPCV overfit |
| --- | --- | --: | --: | --: | --: | --: | --: | --- | --: | --- |
| `above_sma200` | trend | 0.110 | 7.97 | – | 0/9 | – | 0.95 | SIGN_HOLDS | – | no |
| `adx` | trend | 0.035 | 2.68 | −0.017 | 5/9 | 0.10 | 0.99 | SIGN_HOLDS | −3.5 | **yes** |
| `aroon_osc` | trend | 0.121 | 8.92 | −0.230 | 4/9 | 0.24 | 0.94 | SIGN_HOLDS | −2.6 | no |
| `di_spread` | trend | 0.030 | 2.50 | −0.463 | 3/9 | 0.17 | 0.95 | SIGN_FLIPS | – | **yes** |
| `golden_cross` | trend | – | – | – | – | – | – | UNMEASURED | – | no |
| `ichimoku_above_cloud` | trend | 0.120 | 7.44 | – | 0/9 | – | 0.91 | SIGN_HOLDS | – | no |
| `sma_stack` | trend | 0.101 | 9.18 | – | 0/9 | – | 0.97 | SIGN_HOLDS | – | no |
| `macd_hist_pct` | momentum | −0.041 | −4.23 | −0.012 | 4/9 | 0.15 | 0.95 | SIGN_HOLDS | −2.9 | **yes** |
| `mfi` | momentum | −0.013 | −1.14 | −0.029 | 4/9 | 0.15 | 0.91 | SIGN_HOLDS | −3.1 | **yes** |
| `momentum_12_1` | momentum | 0.046 | 2.03 | −0.516 | 5/9 | 0.05 | 1.00 | SIGN_FLIPS | – | **yes** |
| `roc20` | momentum | 0.039 | 2.99 | −0.175 | 2/9 | 0.18 | 0.91 | SIGN_HOLDS | – | **yes** |
| `rsi` | momentum | 0.088 | 6.85 | −0.182 | 6/9 | 0.22 | 0.93 | SIGN_HOLDS | – | **yes** |
| `stoch_k` | momentum | 0.049 | 4.14 | −0.001 | 5/9 | 0.44 | 0.83 | SIGN_FLIPS | −2.7 | **yes** |
| `rs_above_sma` | relative strength | 0.061 | 3.97 | – | 0/9 | – | 0.89 | SIGN_HOLDS | – | no |
| `rs_divergence` | relative strength | – | – | – | 1/9 | 0.72 | 0.32 | SIGN_FLIPS | – | no |
| `rs_new_high` | relative strength | 0.038 | 2.93 | – | 0/9 | 0.59 | 0.49 | SIGN_HOLDS | – | no |
| `rs_slope_pct` | relative strength | 0.107 | 6.83 | −0.327 | 6/9 | 0.04 | 1.00 | SIGN_HOLDS | −2.7 | **yes** |
| `bollinger_pct_b` | price structure | 0.031 | 2.51 | −0.184 | 4/9 | 0.42 | 0.85 | SIGN_FLIPS | – | **yes** |
| `fib_zone` | price structure | −0.009 | −1.09 | – | 0/9 | 0.24 | 0.76 | SIGN_FLIPS | – | no |
| `keltner_pct` | price structure | 0.072 | 5.77 | −0.040 | 5/9 | 0.25 | 0.89 | SIGN_FLIPS | −3.1 | **yes** |
| `near_sma200` | price structure | – | – | – | 0/9 | – | – | SIGN_HOLDS | – | no |
| `cmf` | volume | 0.153 | 12.44 | 0.124 | 5/9 | 0.17 | 0.95 | SIGN_HOLDS | −1.8 | no |
| `elder_ratio` | volume | 0.051 | 4.71 | 0.265 | 5/9 | 0.67 | 0.54 | SIGN_HOLDS | −2.5 | no |
| `rvol` | volume | 0.064 | 5.88 | 0.291 | 5/9 | 0.61 | 0.65 | SIGN_HOLDS | −2.5 | no |
| `volume_dry_up` | volume | −0.028 | −1.93 | – | 2/9 | – | 0.79 | SIGN_FLIPS | – | no |
| `near_breakout` | breakout | 0.101 | 6.23 | – | 2/9 | 0.18 | 0.86 | SIGN_HOLDS | – | no |
| `pullback_candidate` | breakout | 0.016 | 1.44 | – | 0/9 | 0.81 | 0.22 | SIGN_HOLDS | – | no |
| `trigger_candle` | breakout | −0.020 | −1.49 | – | 0/9 | 0.87 | 0.11 | SIGN_HOLDS | – | no |
| `hurst` | mean reversion | −0.008 | −0.98 | 0.032 | 6/9 | 0.00 | 1.00 | SIGN_HOLDS | −1.5 | no |
| `obv_bullish_div` | mean reversion | −0.064 | −4.95 | – | 0/9 | 0.29 | 0.71 | SIGN_HOLDS | – | no |
| `rsi2` | mean reversion | −0.034 | −2.34 | −0.016 | 5/9 | 0.70 | 0.40 | SIGN_FLIPS | – | no |
| `stoch_rsi` | mean reversion | −0.066 | −4.29 | −0.050 | 3/9 | 0.53 | 0.71 | SIGN_HOLDS | −3.2 | **yes** |
| `williams_r` | mean reversion | 0.049 | 4.14 | −0.001 | 5/9 | 0.44 | 0.83 | SIGN_FLIPS | −2.7 | **yes** |
| `atr_pct` | volatility | −0.134 | −7.39 | −0.006 | 4/9 | 0.11 | 0.99 | SIGN_HOLDS | −2.8 | no |
| `sqrt_rs_minus` | volatility | −0.146 | −11.93 | 0.043 | 5/9 | 0.01 | 1.00 | SIGN_HOLDS | −2.4 | no |
| `pct_above_50d`, `pct_above_200d`, `ad_ratio` | breadth | **UNMEASURED** — market-wide breadth needs a panel the per-name leg does not fetch | | | | | | | | |
| `vol_percentile` | volatility | **UNMEASURED** — not on the run's component path (`regime.vol_percentile` returns 0.5 when it cannot measure; WP-3 excluded it deliberately) | | | | | | | | |

**Read the signs against the declared direction.** `atr_pct`, `sqrt_rs_minus`
and `hurst` are `lower_better` components, so their **negative** IC is the
engine's favourable direction, not a failure — the measurement is on the raw
component value, and the alignment inverts it. `sqrt_rs_minus` has the largest
|IC| in the table (−0.146) and the cleanest persistence (1.00, turnover 0.01):
the volatility category's semivariance leg is the most stable signal measured
here. `atr_pct` is next (−0.134).

**Categories, with the measured verdict** (weights are the engine's own
`CATEGORY_WEIGHTS` — **DECLARED**, unchanged by this document):

| category | weight | verdict | survived (MODERATE/STRONG IC, not redundant) | drop candidates (WEAK IC or redundant) |
| --- | --: | --- | --- | --- |
| trend | 20 | SURVIVES | `adx`, `aroon_osc`, `sma_stack` | `above_sma200`, `di_spread`, `ichimoku_above_cloud` |
| momentum | 18 | SURVIVES | `macd_hist_pct`, `momentum_12_1` | `mfi`, `roc20`, `rsi`, `stoch_k` |
| relative strength | 12 | SURVIVES | `rs_new_high` | `rs_above_sma`, `rs_slope_pct` |
| price structure | 12 | **REDUNDANT** | – | `bollinger_pct_b`, `fib_zone`, `keltner_pct` |
| volume | 10 | SURVIVES | `cmf` | `elder_ratio`, `rvol`, `volume_dry_up` |
| breakout | 10 | SURVIVES | `near_breakout` | `pullback_candidate`, `trigger_candle` |
| mean reversion | 8 | SURVIVES | `obv_bullish_div`, `rsi2`, `stoch_rsi` | `hurst`, `williams_r` |
| volatility | 5 | **REDUNDANT** | – | `atr_pct`, `sqrt_rs_minus` |
| breadth | 5 | **UNMEASURED** | – | – (needs the market-wide panel, P0-3's producer) |

The verdict rule is declared in the output, not hidden: *survives* = at least
one component with a MODERATE/STRONG rank IC (`alpha_health.ic_label`,
`weak=0.03`) that is not flagged redundant; *redundant* = a measured component
at |Spearman| ≥ 0.80 with a stronger partner. **`REDUNDANT` here means "no
component of this category stands alone"** — `price_structure`'s four
components are `bollinger_pct_b`, `keltner_pct`, `near_sma200`, `fib_zone`, of
which the first two are band-mapped non-monotonic reads of the same price
position and the last two are boolean proximity flags; `volatility`'s two are
both downside-dispersion measures (`atr_pct` and the semivariance leg).

**What the numbers do NOT say.** A 30-date window is one month of one market;
25 usable cross-sections is the *floor*, not a sample size that settles a
weight. `ICIR` above ~5 is an artifact of a near-constant IC series, not
evidence of a 5-sigma factor. The DSR is printed with the spread series' own
mean and dispersion for exactly this reason, and it is negative for most
components once the 36-trial penalty is applied — which is the honest reading:
**this window does not validate 36 factors.**

---

## 2. The redundancy matrix — the gate on the weight table

**MEASURED**: 136 pairwise Spearman correlations among the 17 components of the
trend + momentum + relative-strength block, over the 149-name cross-section.
Mean |ρ| **0.36**, max |ρ| **1.00**, **46** pairs at |ρ| ≥ 0.5, **15** at
|ρ| ≥ 0.7, **8** at |ρ| ≥ 0.80 (flagged redundant). The strongest:

| pair | ρ | n |
| --- | --: | --: |
| `golden_cross` \| `rs_above_sma` | 1.000 | 16 |
| `above_sma200` \| `golden_cross` | 0.878 | 16 |
| `golden_cross` \| `ichimoku_above_cloud` | 0.878 | 16 |
| `golden_cross` \| `rs_slope_pct` | 0.840 | 16 |
| `golden_cross` \| `rsi` | 0.840 | 16 |
| `di_spread` \| `rsi` | 0.819 | 4,326 |
| `rsi` \| `stoch_k` | 0.816 | 4,326 |
| `roc20` \| `rsi` | 0.805 | 4,326 |
| `ichimoku_above_cloud` \| `rs_above_sma` | 0.775 | 4,326 |
| `aroon_osc` \| `rsi` | 0.730 | 4,326 |
| `ichimoku_above_cloud` \| `rsi` | 0.726 | 4,326 |
| `di_spread` \| `roc20` | 0.714 | 4,326 |
| `aroon_osc` \| `roc20` | 0.713 | 4,326 |

**The `golden_cross` rows are weak evidence and are labelled as such**: that
component is present for only 16 of 4,326 possible (name, date) observations
(the producer fires only when a cross is detected in the window), so its
|ρ| = 1.00 rests on 16 points. The `n` is printed beside every pair for this
reason. The **`rsi` rows are strong evidence**: `di_spread` (0.819),
`stoch_k` (0.816) and `roc20` (0.805) each carry thousands of observations and
each sits at or above the redundancy threshold.

**Finding — the 50% block is largely one bet, as the plan suspected.** The plan's
sentence was *"trend filters, MA rules and TSMOM harvest one latent factor"*
(§7). The matrix confirms it inside `momentum`: `rsi`, `stoch_k` and `roc20`
are ≥ 0.80 correlated pairwise, and `williams_r` is an exact algebraic
transform of `stoch_k` (Williams %R = −100 × (1 − stochastic), the same
oscillator) — two components of one category are one number, and
`alpha_health`'s own `NON_MONOTONIC_INPUTS` list already names them as separate
band tables. `aroon_osc`, `di_spread` and `ichimoku_above_cloud` add further
0.7+ links across `trend` and `momentum`.

**Recommendation (evidence, not a change).** Before any weight vector for
`TechnicalScore` is treated as a starting point, the momentum category should be
reduced to one oscillator (`rsi` or `stoch_k`, not both) and the trend category's
MA-state components (`above_sma200`, `sma_stack`, `ichimoku_above_cloud`,
`golden_cross`) treated as one MA-regime leg. The engine's own
`CATEGORY_WEIGHTS` is **DECLARED** and unchanged by this document; the panel
does not revise it, and the vector it prints is that table, labelled
`RESEARCH_ONLY`.

**The FCF-yield cluster is UNMEASURED — every member of it.**

| cluster member | status |
| --- | --- |
| `fcf_yield` | **UNMEASURED** — producer is `capex_quality`, which needs the annual series; the factor schema already marks it `NA` on the panel path |
| `price_to_free_cash_flow` | **UNMEASURED** — the ratio block needs the vendor fundamentals payload (403) |
| `price_to_cash_flow` | **UNMEASURED** — same |
| `earnings_yield` | **UNMEASURED** — same |
| `val_z` | **UNMEASURED** — needs the name's own multiple history; the schema marks it `NA` on the panel path |

The matrix reports the block with `n_pairs: 0` and all five members under
`missing`, so a reader cannot mistake an unmeasured cluster for a measured one.
**This is the finding the vendor gate creates**: the plan's second named
redundancy question cannot be answered until the Extended Fundamentals plan is
granted.

---

## 3. The multiple-testing family

**MEASURED** over the 36 measured factors, 25 usable cross-sections:

| check | result | reading |
| --- | --- | --- |
| `pbo_flag` | **False** | the factor with the best in-sample spread (`cmf`) also had a positive out-of-sample spread — no family-level overfit signal at the family level |
| `reality_check` | p = **0.0020** (stat 0.065, 20 candidates × 20 obs, stationary bootstrap, block 5, seed 0) | the best spread beats a zero benchmark more than chance |
| `spa` | p = **0.0020** (studentised, 0 recentred) | same conclusion under Hansen's studentised null |
| per-factor `deflated_sharpe` | 15 of 36 factors produced a value; **21 withheld** | 16 had no spread series at all (tie-collapsed boolean components — see §5); 5 were withheld because their spread series compounds to ≤ −100%, where a growth rate is not a real number |
| per-factor `purge CPCV` (`purged_cpcv_splits`, 5 folds, no embargo) | **14 of 36 flagged overfit** | the best in-sample fold's out-of-sample spread was negative — the factor family is not stable across period cuts |

The family-level checks pass and the per-factor checks mostly do not. Both are
true and both belong in the finding: with 36 factors measured together, a
family-level p-value of 0.002 is the weakest form of evidence, and a per-factor
CPCV overfit mask on 14 of them is the strongest form of warning.

---

## 4. The other engines — findings, all UNMEASURED on the factor axis

Every one of these engines **exists in the tree** and is read by the registry
(the run's `engines` block), and none of them carries a single panel-measurable
factor. The reason is the same in each case and is stated rather than implied.

| engine | declared factors | measured | why not |
| --- | --: | --: | --- |
| `fundamental_score` | 28 | **0** | the entire engine reads vendor fundamentals: the bulk endpoint 403s (Extended Fundamentals) and the single-ticker endpoint 403s too. The panel's own ratio block comes from the same payload, so nothing substitutes. **The FCF-yield cluster, the valuation category and the growth category are UNMEASURED for this reason alone.** |
| `risk_score` | 32 | **0** | its inputs are position/book-level (`book_risk`, drawdown, concentration) or options/vol surfaces — no cross-sectional producer on a per-name price+fundamentals panel |
| `sentiment_score` | 18 | **0** | news/social/analyst/options/short-interest producers are per-name vendor reads; a bulk panel does not carry them |
| `news_score` | 11 | **0** | GDELT/EODHD news reads are per-name and per-article; the engine also has no category weight table the registry can read (its vector prints `UNMEASURED` with that reason) |
| `regime_score` | 6 | **0** | it is a **market-level** object: its components are market trend, breadth, VIX percentile and term structure — one value per date, not one per name. A cross-sectional IC is not the right statistic for it, and this layer does not fake one. |
| `event_state` | 0 | **0** | **not a scored engine**: EventScore is a state/flag object (master §1.4: four output types stay four), so it is out of the panel's scope by construction, and the registry says so |

Their weight vectors, as printed by the run (**DECLARED**, `RESEARCH_ONLY`, none
revised here):

| engine | vector | provenance |
| --- | --- | --- |
| `technical_score` | trend 20 / momentum 18 / relative strength 12 / price structure 12 / volume 10 / breakout 10 / mean reversion 8 / volatility 5 / breadth 5 | the engine's own `CATEGORY_WEIGHTS` |
| `sentiment_score` | news 15 / momentum 15 / institutional 15 / breadth 10 / analyst 10 / retail-social 10 / options 10 / short interest 5 / dispersion 5 / extreme crowding 5 | the engine's own `CATEGORY_WEIGHTS` |
| `risk_score` | the engine's own declared table | `CATEGORY_WEIGHTS` on the engine module |
| `fundamental_score` | **equal weights, 1/4 per sub-score** | no validated vector is published — the engine prints this fact in its own basis, and this document repeats it rather than inventing one |
| `news_score`, `regime_score` | `UNMEASURED` | no category weight table the measurement layer can read |

---

## 5. What the measurement layer cannot say (and what it therefore does not)

* **One month, one market, one sample.** 30 dates of a 150-name NASDAQ stride.
  The floors are cleared and nothing more: a 25-cross-section IC is a
  diagnostic, not a validation. No weight should be promoted on this evidence,
  and none is (`RESEARCH_ONLY`).
* **The signs are raw.** Every IC is measured on the component's raw value, so a
  `lower_better` component reads negative by construction. Direction lives in
  the engine's alignment, not in this table.
* **Boolean components are tie-collapsed.** `above_sma200`, `golden_cross`,
  `ichimoku_above_cloud`, `near_sma200`, `rs_above_sma`, `sma_stack` and
  `volume_dry_up` fill too few rank buckets for a decile spread: their
  `spread`/`turnover` rows are withheld with the reason, their `ordering`
  carries `sparse: true`, and 16 factors have no spread series for the DSR.
  `near_sma200`, `rs_divergence` and `vcp_candidate` return no IC at all: a
  cross-section with no dispersion makes the correlation undefined, and the
  harness now withholds the row instead of printing `nan`.
* **Sector and regime robustness are NOT emitted.** The plan's §7 deliverable
  list names them; this ticket did not implement them, and they are recorded
  here as a gap rather than left to look measured. (A sector split needs a
  sector label per name — a per-name vendor call the bulk path does not carry —
  and a regime split needs a regime series per date, which `RegimeScore` will
  produce.)
* **No weight vector is invented.** The panel produces the engines' own tables
  beside their measured evidence, or `None`. Below the cross-section floors it
  produces **no vector at all** and labels the panel
  `INSUFFICIENT_CROSS_SECTION` (owner Q4) — a tested output, not a comment.
* **Nothing here reaches a gate or a size.** The module imports no sizing path,
  no `risk_governor`, no `GATE_PRECEDENCE` and no `decision_guardrail`; a test
  asserts it with an AST guard, and no `SCORE_BANDS` table is read.

---

## 6. Defects found while measuring (all fixed, failing-first)

| # | defect | evidence | fix |
| --- | --- | --- | --- |
| 1 | **`evaluate.cagr` returned a COMPLEX number** for a series whose compounded return is ≤ −100%. A decile long-short **spread** reaches this (it can lose more than 100% of notional in one period), and the value reached the report as `(-2.7667+0.0002j)` | the first full run of the layer | `cagr` guards the base: `0` → −100%/yr (a total loss), below zero → `nan` with the reason in the docstring; the layer additionally withholds a non-finite deflated Sharpe and prints the spread series' own mean/dispersion beside it |
| 2 | **`alpha_health.score_evaluation_rows` printed `nan` as a factor's rank IC** when a cross-section had no dispersion (scipy returns nan for a constant input) — three boolean components reported `nan` instead of a row with a reason | the same run | the IC row is withheld with `rank IC non-finite on this panel (a cross-section with no dispersion …)` |
| 3 | **The panel's default price loader recursed into the panel's own patch** of `analysis_tools._ohlcv`, so a live run produced **0 names of 150** with no error anywhere | the first live build | `PriceProvider` captures the real loader as a function object at construction; a regression test builds a provider through the *default* loader (the stub-loader tests could not see this) |
| 4 | **An empty fetch was cached as a panel**, which would have turned one vendor failure into a permanently "cached" thin date | design review of the cache path | an empty fetch writes no file and the date is retried; the run records `source: empty-fetch` |

---

## 7. The one-line summary

**`TechnicalScore` is measurable today and its 50% block is measurably
redundant** (8 pairs at |ρ| ≥ 0.80, 46 at |ρ| ≥ 0.50, `williams_r` ≡ `stoch_k`);
**every fundamental factor — including the whole FCF-yield cluster — is
UNMEASURED because the EODHD Extended Fundamentals plan returns 403 on this
key**, which the panel now records per date instead of hiding; **the other five
engines have no cross-sectional producer on this panel and are reported
UNMEASURED with their reasons**; and **no weight vector is produced anywhere in
this document** — the vectors printed are the engines' own declared tables,
labelled `RESEARCH_ONLY`, with their measured evidence beside them.
