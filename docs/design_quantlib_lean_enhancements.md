# Deep Study: QuantLib + Lean → TradingAgents Enhancements

**Status:** design / research (no code yet).
**Source study:** shallow clones read in this session of
[`quantlib/QuantLib`](https://github.com/quantlib/QuantLib) and
[`quantconnect/lean`](https://github.com/quantconnect/lean), mapped onto the
fork's deterministic `strategies/*` calculators and overlays.

This is a *research-to-design* doc, same shape as
`docs/design_institutional_value_dip_workflow.md`. Nothing here is committed
yet; each item is a read-only deterministic calculator (float | `None` output,
no-fabrication) that slots under `tradingagents/strategies/` and wires into the
existing overlay/veto layer **without touching the LangGraph**.

---

## 0. TL;DR

Two very different teachers:

- **QuantLib** is a *pricing/measurement* library → gives exact risk, vol,
  options, rate, and statistics math the fork currently hand-waves (VaR/CVaR at
  horizon, implied vol + Greeks, vol-surface interpolation, downside/regret,
  monotone interpolation, rate-convention hygiene).
- **Lean** is an *execution/framework* engine → gives the rigorous operational
  skeleton the fork lacks: a real **two-pass risk loop that emits position-exit
  overrides**, covariance-based **risk-budgeting** construction, **evaluation
  breadth** beyond Sharpe (Sortino/PSR/rolling/underwater), **MAE/MFE exit
  quality**, **order-cost modeling**, and **config-robustness** (not argmax).

Combined: make TradingAgents' *numbers* exact (QL) and its *decisions
operationally defensible* (Lean), without breaking the analysis-only mandate.

---

## 1. What the fork already has (so we don't re-suggest it)

Verified against source:
- `book_risk.py`: simple VaR, CVaR, portfolio_cvar, stress_loss, correlated
  stress, drawdown_gate.
- `evaluate.py`: net_returns, cagr, volatility, **sharpe**, **deflated_sharpe**
  (PBO), max_drawdown, equity_curve, walk_forward_splits, pbo_flag.
- `portfolio.py`: value_ratio_weights, capped_weights, sector_cap,
  adjust_for_caps, mean_correlation/correlation_penalty (Pearson).
- `exits.py`: stop_to_breakeven, target_level, net_of_cost, exit_check,
  breakeven_after_confirmation.
- `journal.py`: momentum win/loss + discipline summary.
- `size.py`: kelly, vol-target, atr, stop_loss_atr, cvar_budget.
- `risk_governor.py`: gate (PASS/WARN/REJECT) on new risk.
- `technical_factors.py`: Keltner/Donchian/Supertrend/Aroon/correlation already
  present.
- `dcf.py`, `value_dip.py`, `regime.py`, `calibration.py`, `consensus.py`.

---

## 2. QuantLib-sourced concepts (pricing/measurement rigor)

Module paths are from the QuantLib tree.

### Q1. Horizon VaR/CVaR (parametric + empirical) ⭐ quick win
- **Source:** `ql/math/statistics/gaussianstatistics.hpp`
  (gaussianValueAtRisk/gaussianExpectedShortfall) +
  `ql/math/statistics/riskstatistics.hpp` (valueAtRisk/expectedShortfall, the
  `-min(x,0)` negation convention).
- **Why:** `book_risk.py` emits *daily* CVaR; the LLM then hand-waves multi-day
  risk as "~3× daily". QL gives a horizon-correct, defensible number.
- **Signature:**
  ```python
  def var_cvar_horizon(returns, horizon_days, alpha=0.95, method="empirical") -> dict
  # {'emp_var','emp_cvar','param_var','param_cvar','scaling_valid','n'}
  ```
- **Risk gate:** sqrt(T) scaling only valid for i.i.d. — gate on
  `return_autocorrelation` (Q4) else `scaling_valid=False`.

### Q2. Implied volatility + Greeks (Black-76) ⭐ quick win
- **Source:** `ql/pricingengines/blackformula.hpp` (`blackFormula`,
  `blackFormulaImpliedStdDevApproximation` — Brenner-Subrahmanyan /
  Corrado-Miller 1996).
- **Why:** fork has **zero** options capability; the analyst "estimates"
  rich/cheap options. Exact IV + delta/gamma/vega/theta is a citeable number.
- **Signature:**
  ```python
  def implied_vol_and_greeks(spot, strike, t, r, q, mid, option_type) -> dict
  # {'implied_vol','delta','gamma','vega','theta','forward'}
  ```
- **Risk:** needs forward (r,q) and clean mids; require `mid > intrinsic` else
  `None`; bid/ask noise dominates.

### Q3. Vol surface in variance-time, forward vol
- **Source:** `ql/termstructures/volatility/equityfx/blackvoltermstructure.hpp`
  (`blackVol`/`blackVariance`/`blackForwardVol`), `blackvarianccurve.hpp`,
  `blackvolsurfacedelta.hpp`.
- **Why:** LLM averages implied vols across strikes/expiries as if comparable;
  **variance is additive, vol is not**. Gives a term-consistent ATM level +
  steep/flat read.
- **Signature:**
  ```python
  def black_vol_surface(expiries, deltas, ivs, atm_forward) -> dict
  # {'atm_vol','forward_vol','slope','surface'}
  ```
- **Risk:** sparse chains → require `len >= 3` else `None`.

### Q4. Return autocorrelation → gates sqrt(T)/variance-time claims ⭐ quick win
- **Source:** `ql/math/autocovariance.hpp` (FFT, mean-removed).
- **Why:** pure rigor gate for Q1/Q3/Q5; momentum books have lag-1 ACF, so naive
  scaling understates risk. Cheap, high payoff, ~10 lines.
- **Signature:**
  ```python
  def return_autocorrelation(returns, max_lag=5) -> dict
  # {'acf','q_stat','is_iidish'}
  ```
- **Risk:** require `n >= 32` else `None`.

### Q5. Monte Carlo tail for the book (Cholesky + std error)
- **Source:** `ql/methods/montecarlo/` (mcsimulation, pathgenerator,
  brownianbridge) + `riskstatistics.hpp`.
- **Why:** natural upgrade to `book_risk`/`portfolio`: downside as a
  distribution with standard error, not a scalar guess.
- **Signature:**
  ```python
  def monte_carlo_tail(cov, weights, horizon, seed, paths=50000, alpha=0.95) -> dict
  # {'p05','p01','mean','std','var_alpha','cvar_alpha','se'}
  ```
- **Risk:** cov must be PSD for Cholesky; fall back to diagonal model and flag
  `'psd': False`.

### Q6. Tail-dependence beyond Pearson
- **Source:** `ql/math/copulas/` (clayton/gumbel/frank/plackett/huslerreiss).
- **Why:** `portfolio.py` uses Pearson, which misses joint-tail co-movement that
  crashes baskets. Quote exact λ_L/λ_U.
- **Signature:**
  ```python
  def tail_dependence(x, y, copula="clayton") -> dict
  # {'lambda_lower','lambda_upper','spearman_rho','kendall_tau','n'}
  ```
- **Risk:** data-hungry; refuse `n < 30`; basket/portfolio layer only.

### Q7. Downside / regret toolkit
- **Source:** `ql/math/statistics/riskstatistics.hpp` (semiVariance,
  regret(target) with N/(N-1) bias, shortfall, averageShortfall).
- **Why:** the LLM flags downside qualitatively; exact target-anchored numbers
  feed the risk governor veto, complementing `book_risk` CVaR.
- **Signature:**
  ```python
  def downside_measures(returns, target) -> dict
  # {'semi_deviation','downside_deviation','regret','shortfall_prob','avg_shortfall','n'}
  ```
- **Risk:** regret needs ≥2 samples below target; guard → `None`.

### Q8. Income/credit math: YTM, duration, convexity
- **Source:** `ql/cashflows/cashflows.hpp` (NPV, yield, duration, convexity);
  `ql/pricingengines/bond/bondfunctions.hpp` (yield, duration, zSpread).
- **Why:** `dcf.py` computes NPV but never inverts to YTM or gives
  duration/convexity — missing exact numbers for income/credit names.
- **Signature:**
  ```python
  def bond_yield_duration(dates, amounts, price, settle, day_count="Act/365F",
                          compounding="Annual") -> dict
  # {'ytm','macaulay','modified','convexity','npv','accrued'}
  ```
- **Risk:** needs real cashflow schedule + tradable settlement + reliable price;
  `None` otherwise. Day-count convention must be documented.

### Q9. Monotone / log interpolation for sparse OHLCV
- **Source:** `ql/math/interpolations/convexmonotoneinterpolation.hpp`
  (Hagan-West), `loginterpolation.hpp`, `cubicinterpolation.hpp`.
- **Why:** vendors return gaps; the LLM hallucinates fills. Monotone-convex/log
  fill is safe.
- **Signature:**
  ```python
  def monotone_fill(x, y, xi, method="log_linear", force_positive=True) -> list[float]
  ```
- **Risk:** never extrapolate beyond observed range; drop out-of-range points.

### Q10. Rate/compounding/day-count hygiene
- **Source:** `ql/interestrate.hpp` (InterestRate → discountFactor,
  compoundFactor, equivalentRate, impliedRate).
- **Why:** the LLM guesses whether a quoted yield is simple/continuous/annual;
  one compound-factor mapping makes every annualization exact.
- **Signature:**
  ```python
  def rate_equivalent(rate, day_count, comp, target_comp, t) -> dict
  # {'discount_factor','compound_factor','equivalent_rate'}
  ```
- **Risk:** mechanical, low; require explicit comp/day_count args (no silent
  defaults) so an input is never mislabeled.

---

## 3. Lean-sourced concepts (operational/framework rigor)

Module paths are from the Lean tree.

### L1. Two-pass risk loop that EMITS exit overrides ⭐ biggest architectural gap
- **Source:** `Algorithm.Framework/Risk/*.cs`; wiring
  `Algorithm/QCAlgorithm.Framework.cs::ProcessInsights`.
- **Why:** `risk_governor`/`book_risk` are **gates** returning PASS/WARN/REJECT
  to *block new risk*. There is **no per-step second pass that liquidates /
  shrinks existing positions**. Lean's
  `RiskManagement.ManageRisk(targets) -> IEnumerable<IPortfolioTarget>` is the
  exact shape to copy: construction targets → risk-management **override**
  targets (weight 0 = liquidate) → execution.
- **Signature:**
  ```python
  def manage_risk(targets, peak, current, max_drawdown_pct=0.05) -> dict|str
  # overrides[sym] = 0.0 when current/peak - 1 < -max_drawdown_pct; else 'unavailable'
  ```
- **Risk:** needs per-symbol peak/entry state persisted with the paper ledger.

### L2. Covariance risk-parity / min-variance construction ⭐ quick win
- **Source:** `Algorithm.Framework/Portfolio/{RiskParity,MinimumVariance,
  MeanVariance,MaximumSharpeRatio,UnconstrainedMeanVariance}PortfolioOptimizer.cs`.
- **Why:** `portfolio.py` does value-ratio + hard clips + mean-correlation
  penalty → diversification-by-guesstimate. No covariance → can't answer how
  much risk each name contributes, no real risk-budgeting.
- **Signature:**
  ```python
  def risk_parity_weights(returns_by_name, lower=0.0, upper=1.0,
                          tol=1e-11, max_iter=15000) -> dict|str
  # cov from aligned returns; iterate RC_i / inv(cov)W = const (Spinu Newton)
  ```
- **Risk:** cov on short/sparse history unstable; renormalize+cap; degrade to
  equal-weight on singular cov.

### L3. Evaluation breadth: Sortino/PSR/rolling/underwater ⭐ quick win
- **Source:** `Common/Statistics/Statistics.cs` (Sortino, PSR, TrackingError);
  `PortfolioStatistics.cs` (Alpha/Beta/Treynor/IR); `Report/Rolling.cs`
  (window-132 rolling beta/sharpe); `Report/DrawdownCollection.cs`
  (top-N underwater: peak/trough/depth/recovery).
- **Why (verified):** `evaluate.py` has sharpe + deflated + single max_drawdown
  but **no** Sortino/downside-deviation, beta/alpha/Treynor/IR, PSR,
  rolling series, or underwater duration/recovery. Classic Sharpe+drawdown
  overfit hole.
- **Signatures:**
  ```python
  def sortino(returns, mar=0.0, ppy=252.0) -> float|None
  def probabilistic_sharpe(returns, n_trials, ppy=252) -> float|None  # needs skew,kurt
  def rolling_beta(returns, benchmark, window=132)   # pearson*(sd_algo/sd_bench)
  def underwater_drawdowns(equity) -> [{'peak','trough','depth','recovery'}]
  ```
- **Risk:** none; pure formulas. MAR is a free parameter (document default).

### L4. Trailing stop from highest unrealized profit
- **Source:** `Algorithm.Framework/Risk/TrailingStopRiskManagementModel.cs`.
- **Why (verified):** `exits.py` has stop-to-breakeven (1 ATR) and ATR targets
  but no margin-giveback/peak-trail rule. A position that ran +40% and gave
  back 30% is never force-exited.
- **Signature:**
  ```python
  def trailing_stop_exit(entry, peak, current, trail_pct=0.05) -> dict|str
  # {'exit','stop_px','drawdown_from_peak'}
  ```
- **Risk:** trailing % vs ATR stop can conflict — decide precedence (peak-trail
  wins when both trigger).

### L5. Trade excursions: MAE/MFE, profit factor
- **Source:** `Common/Statistics/TradeStatistics.cs`.
- **Why (verified):** `journal.py` tracks win/loss + R:R, no MAE/MFE, profit
  factor, or intra-trade drawdown → can't detect exit-motivated-by-luck vs
  skill (core exit-quality QA).
- **Signature:**
  ```python
  def trade_excursions(trades) -> dict|str
  # {'mae','mfe','profit_factor','max_intra_trade_drawdown'}
  ```
- **Risk:** needs per-trade OHLC path during holding; ledger is order-level, may
  need bar history.

### L6. Order-cost / volume-share slippage on the paper ledger
- **Source:** `Common/Orders/Slippage/{VolumeShareSlippage,
  MarketImpactSlippage}Model.cs`; `Algorithm.Framework/Execution/
  SpreadExecutionModel.cs`.
- **Why (verified):** `liquidity_risk.py` is static screens (Amihud, ADV,
  float turnover); the paper ledger uses arrival_vs_fill without a volume-share
  cost curve. Cannot bound "a 2%-of-ADV order costs X bps".
- **Signature:**
  ```python
  def volume_share_slippage(order_qty, adv, price, vol_limit=0.1,
                            price_impact=0.025) -> float|str
  # price * price_impact * min(qty/adv, vol_limit)^2
  ```
- **Risk:** ADV/participation must feed the ledger; avoid double-counting static
  illiquidity.

### L7. Magnitude-scored alpha / insight
- **Source:** `Common/Algorithm/Framework/Alphas/Insight.cs` +
  `InsightScore.cs`.
- **Why (verified):** `calibration.py` buckets confidence → realized win-rate
  (direction hit = Δr > 0). No predicted-MAGNITUDE vs actual scoring, no horizon
  accuracy. The repo never learns "I said +12%/30d, realized +2%".
- **Signature:**
  ```python
  def alpha_score(direction, predicted_magnitude, period_days, actual_return,
                  confidence=None) -> dict|str
  # {'hit','magnitude_err','score','horizon_ok'}
  ```
- **Risk:** none; needs forward realized returns overlapped by horizon.

### L8. Config robustness, not argmax
- **Source:** `Optimizer/Analysis/{OptimizationSlicing,OptimizationClustering,
  OptimizationFailedBacktests}.cs`.
- **Why (verified):** `evaluate_config_gate.py` grids and returns single best by
  score = overfit-to-one-point. No "best at search-box edge" or "good configs
  are fragile spikes" read.
- **Signature:**
  ```python
  def config_robustness(results, param_names) -> dict|str
  # {'edge_flag':{p:bool},'clusters':int,'best_cluster_spread','n'}
  ```
- **Risk:** heuristic; edge/cluster flags advisory, never causal sensitivity.

### L9. Sector exposure enforcement with renormalization
- **Source:** `Algorithm.Framework/Risk/MaximumSectorExposureRiskManagementModel.cs`
  + `Portfolio/SectorWeightingPortfolioConstructionModel.cs`.
- **Why (verified):** `sector_rank.py` is momentum RANKING (a signal);
  `portfolio.sector_cap` is a hard clip leaving excess as stale cash. No live
  per-sector ceiling + budget reallocation.
- **Signature:**
  ```python
  def enforce_sector_exposure(weights_by_name, sector_of, max_sector=0.20) -> dict|str
  ```
- **Risk:** needs sector map; GICS mapping already in `sector_rank`.

### L10. Confidence-weighted (proportional) construction
- **Source:** `Algorithm.Framework/Portfolio/{InsightWeighting,
  ConfidenceWeighted}PortfolioConstructionModel.cs`.
- **Why (verified):** `portfolio.py` hard-clips (excess → cash), discarding
  signal shape; Lean rescales proportionally, preserving relative ranking.
- **Signature:**
  ```python
  def confidence_weights(conf) -> dict   # w_i = conf_i / sum(conf)
  ```
- **Risk:** none; decide order vs caps layer.

### L11. Per-loop wall-clock budget guard
- **Source:** `Engine/AlgorithmTimeLimitManager.cs`,
  `Engine/TransactionHandlers/*TransactionHandler.cs`.
- **Why:** this is an LLM graph where a multi-turn agent / broken vendor call can
  hang a pre-market/review job. A per-step budget lets the run degrade instead
  of hanging.
- **Signature:**
  ```python
  def time_budget_ok(start_ns, budget_s, now_ns=None) -> bool
  ```
- **Risk:** trivial logic; real value is placing the check at every graph step
  (touches LangGraph wiring, higher effort).

---

## 4. Recommended phases (highest ROI first)

### Phase 1 — evaluation & exit rigor (pure, data-already-in-hand)
- L3 `sortino`, `probabilistic_sharpe`, `rolling_beta`, `underwater_drawdowns`
  → add to `evaluate.py` + `strategy_quality_report.py`/`orderflow_evaluate.py`.
- L4 `trailing_stop_exit`, L5 `trade_excursions` → over the paper
  ledger/journal already written.
- Q4 `return_autocorrelation` → gate every sqrt(T)/variance-time claim.
- Wire all as `@tool`s to the market analyst (compute-as-tools).

### Phase 2 — exact measurement (QL pricing/math)
- Q1 `var_cvar_horizon` → upgrade `book_risk` daily CVaR into horizon-correct
  param+empirical with an honesty flag; feed the risk governor.
- Q2 `implied_vol_and_greeks` + Q3 `black_vol_surface` → greenfield options
  capability (when an option chain is available; else `None`).
- Q7 `downside_measures`, Q10 `rate_equivalent` → risk governor veto + DCF.
- Each a deterministic calculator + hermetic test.

### Phase 3 — risk-budgeting & exit management (structural)
- L1 `manage_risk` two-pass → the biggest conceptual upgrade: a
  per-timestep **position-exit override** layer alongside (not replacing) the
  new-risk gate. Persist per-symbol peak/entry with the paper ledger.
- L2 `risk_parity_weights`, L9 `enforce_sector_exposure`, L10
  `confidence_weights` → covariance-based construction replacing hard clips.
- L6 `volume_share_slippage` → order-cost curve on the ledger.

### Phase 4 — learning & robustness
- L7 `alpha_score` (magnitude+horizon calibration), L8 `config_robustness`
  (edge/cluster flags for `evaluate_config_gate`).
- Q5 `monte_carlo_tail`, Q6 `tail_dependence`, Q8 `bond_yield_duration`, Q9
  `monotone_fill` → as the data/tiers allow (plan-gated like other rows).

---

## 5. Non-goals / risks

- **No execution layer** — L1/L6 are *decision artifacts* (paper book + cost
  model), mirroring the fork's analysis-only mandate; full Lean-style order
  routing/TransactionHandler is out of scope.
- **Options are data-gated** — Q2/Q3 need a real option chain (moomoo/yfinance
  options_data chain exists but is often permission/data-thin); always `None`
  on unavailable, never fabricated.
- **Overfitting** — every new gate/calculator ships default-off behind a config
  flag and must pass the existing walk-forward (`evaluate_config_gate`) before
  being defaulted on, per the fork's policy.
- **Covariance instability** (L2/Q5) — renormalize+cap, degrade to equal-weight
  / diagonal on singular cov; never emit a false-precision weight.
- **Keep it analysis-only** — PSR (L3) and config-robustness (L8) are advisory
  significance reads, not a mandate to trade a param.

---

## 6. Quick-wins verdict

1. **L3 evaluate breadth** (sortino/PSR/rolling/underwater) — pure formulas on
   returns already aligned; closes the Sharpe-only overfit hole at ~zero cost.
2. **Q1 var_cvar_horizon + Q4 autocorrelation** — horizon-correct risk with an
   honesty flag; upgrades existing daily CVaR, gated on i.i.d.
3. **Q2 implied_vol_and_greeks** — greenfield options capability where the
   analyst currently guesstimates rich/cheap.

All three are read-only deterministic `float | None` functions; quick,
hermetic-tested, and they strengthen the *numbers* the 5 decision agents cite.
