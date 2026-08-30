# Quant Formula Map — Implementation Plan

Status: **plan — no code changes yet.** Studied `Strategies/quants.md` (the full
formula reference, 1763 lines: returns → statistics → volatility models →
portfolio → factor models → risk/VaR → options → fixed income → credit →
execution/microstructure → statistical arbitrage → ML → Monte Carlo →
backtest hygiene) and `Strategies/quant2.md` (the condensed cheat-sheet;
heavy overlap — both read, overlapping formulas treated once). This plan maps
the formulas that are **not already implemented** in the fork onto concrete
modules/tools/tests, following the repo's deterministic-first, no-fabrication,
compute-as-tools conventions. Everything here is a pure calculator over data
the repo already fetches; no new vendors.

---

## 1. Already implemented (excluded from scope — verified against source)

| Formula family | Repo home |
| --- | --- |
| Simple/log/gross/cumulative returns, annualized vol (√252) | everywhere; `evaluate.py` |
| Sample mean/var/std, covariance, Pearson/Spearman/Kendall correlation | `statistical.py` |
| Skew/kurtosis, normality tests, ADF/KPSS unit-root | `statistical.py` (`normality`, `unit_root`) |
| Rolling z-score, winsorization, rank/cross-sectional z, neutralization, IC, signal decay (IC term structure) | sentiment `sentiment_research.py` (also for the sentiment factor) |
| OLS, R²/adj-R², t-stat, SE, AIC/BIC-style reporting, VIF, CAPM alpha/beta, factor OLS | `statistical.py` (`ols_factors`, `capm_decomposition`, `variance_inflation_factor`) |
| AR/MA/ARIMA diagnostics, autocorrelation | `statistical.unit_root`, cointegration (ECM-ish) |
| Cointegration spread + Engle–Granger | `statistical.cointegration_pair` |
| EWMA/SMA/EMA (indicators) | `technical_factors.py` / stockstats |
| Volatility cones (multi-horizon vol percentiles) | `rotation.py::vol_cones` |
| Realized vol, vol percentile, regime label | `regime.py` |
| Portfolio moments, MVO, GMV, max-Sharpe/tangency, risk-parity, min-variance, risk contribution, sector caps, correlation penalty | `portfolio_optimizer.py`, `portfolio.py` |
| Kelly (single asset), vol-target size, ATR stops | `size.py`, `contract.py` |
| MCR/CCR/PCR (Marginal/Component/Percent Contribution to Risk) | `portfolio_optimizer.risk_contribution` (verify output names; extend if needed) |
| Sharpe / Sortino / Calmar / Ulcer / capture / tail-ratio / expectancy, net returns, walk-forward, Deflated Sharpe, PBO | `evaluate.py`, `scripts/evaluate_config_gate.py` |
| Max drawdown, running peak, drawdown gate, underwater draws | `evaluate.py`, `book_risk.py` |
| Historical + parametric VaR, CVaR/ES, dollar VaR, horizon VaR | `book_risk.py`, `get_horizon_var` |
| Stress loss, correlated stress | `book_risk.py` (stress_loss, book_correlated_stress) |
| Black–Scholes-Merton family (Black-76), Greeks (delta/gamma/vega/theta/rho), IV, vol surface | `options_math.py` + cboe surface |
| Put-call parity, moneyness/log-moneyness | `options_math.py` (derivable) |
| VWAP, TWAP, POV, participation, volume-share/market-impact slippage, Amihud, days-to-absorb | `liquidity_risk.py`, `backtest_models.py`, `momentum.vwap` |
| RSI, MACD, ROC, moving-average crossover | `extended_indicators.py`, `technical_factors.py` |
| Gross/net exposure, turnover, transaction cost, net strategy return, fill modeling, MAE/MFE | `backtest_engine.py`, `backtest_models.py`, `evaluate.py` (partly) |
| Risk-adjusted performance + Monte Carlo SE/CI | `evaluate.py` + `statistical` (sampling) |
| CVaR/ES book + drawdown governor | `risk_governor.py` |

---

## 2. High-value gaps (targeted)

### Tier 1 — the plan's core

| # | Formula(s) from docs | Gap | New module / tool |
| --- | --- | --- | --- |
| 1 | **Parkinson, Garman–Klass volatility estimators** — `σ²_P = Σ ln²(H/L)/(4·n·ln2)`, `σ²_GK = mean[ ½ln²(H/L) − (2ln2−1)·ln²(C/O) ]` | repo only uses close-to-close realized vol (`regime.realized_vol`); the OHLC data is already fetched, so range-based vol is free and more efficient (captures intraday range, very relevant on sparse/delisted bars) | `strategies/volatility_models.py`: `parkinson_vol`, `garman_klass_vol`, `yang_zhang_vol` (optional, needs overnight gap — label availability); tools `get_volatility_estimators(ticker)` (market) |
| 2 | **EWMA volatility (RiskMetrics λ=0.94)** — `σ²_t = λσ²_{t−1} + (1−λ)r²_{t−1}`; also the EWMA covariance matrix | no EWMA-based vol anywhere; the standard risk-neutral vol forecaster | `volatility_models.py`: `ewma_vol(returns, lam=0.94, initial_var="sample")`; feeds `regime.vol_percentile` + `size.volatility_target_scale` as an option (config `volatility_estimator: close|parkinson|garman_klass|ewma`, default close — no behavior change) |
| 3 | **GARCH(1,1) conditional vol** — `σ²_t = ω + αε²_{t−1} + βσ²_{t−1}`, long-run `ω/(1−α−β)` | repo has no conditional-vol model; vol forecasts power sizing/VaR | `volatility_models.py`: `garch11_fit(returns)` (pure-NumPy MLE via `scipy.optimize.minimize`, constraints ω,α,β≥0, α+β<1; returns ω,α,β, conditional-vol series, long-run vol, `converged` flag; < 60 obs → None); tool `get_garch_volatility(ticker)` (market) |
| 4 | **Incremental VaR + Component VaR** — `IVaR_i = VaR(w+Δw_i) − VaR(w)`, `CVaR_i = w_i·∂VaR/∂w_i` | `book_risk` has book CVaR but no per-name tail attribution; the PM can't answer "which name is the tail" | `book_risk.py`: `incremental_var(returns_by_name, weights, alpha, delta=0.01)`, `component_var(...)` (via MCR·w_i using the covariance-normal method: CVaR decomposition = w_i·(Σw)_i/(√(w′Σw)/(2·h·z?) — use the standard MCR scaling so the components sum to total VaR); tool `get_tail_decomposition(names, weights)` (market) — advisory, never a gate |
| 5 | **OU / AR(1) mean-reversion half-life** — `t_½ = ln2/θ` (OU), `t_½ = −ln2/ln(1+φ̂)` (AR(1), φ̂<0) | `cointegration_pair` tests stationarity but no half-life; mean-reversion validity (value-dip) is asserted not measured | `strategies/mean_reversion.py`: `ar1_half_life(series)`, `ou_half_life(series, dt=1.0)`; tool `get_mean_reversion_quality(ticker)` (market: half-life, AR(1) φ, OU θ, regime verdict stable/mean-reverting/non-reverting); optionally cross-checked against `cointegration_pair` |
| 6 | **Roll effective-spread estimator** — `spread = 2√(−Cov(ΔP_t, ΔP_{t−1}))` (Cov<0) | execution-cost proxy requires quote data the repo lacks; Roll gives a spread estimate from daily prices alone — direct input to the liquidity-aware cost model (`exits.net_of_cost(illiq=…)` extended) | `liquidity_risk.py`: `roll_spread(closes)`; render in `get_liquidation_days` / `get_liquidity_risk` output; optional cost-bps uplift in `net_of_cost` when `roll_spread` is measurable |

### Tier 2 — worthwhile follow-ups

| # | Formula(s) | Gap | Module / tool |
| --- | --- | --- | --- |
| 7 | **Implementation shortfall** — `IS = decision-value − execution-value + opportunity-cost`; decision→arrival→fill decomposition | `pre_market`/paper ledger records review gap + fill proxy but never computes IS; TCA analogue promised in the institutional design (C1) | `evaluate.py`: `implementation_shortfall(decision_px, arrival_px, fill_px, qty, final_price, opportunity_days)`; wire into `pre_market.record_review` book rows + `strategy_quality_report` execution block |
| 8 | **Fixed-income: YTM approx, Macaulay/Modified duration, DV01, convexity** for preferreds — `YTM ≈ (C+(F−P)/n)/((F+P)/2)`, `D_mod = D_mac/(1+y/m)`, `DV01 ≈ D_mod·P·0.0001`, convexity for the −D·Δy + ½C·Δy² approximation | `capital_income_screener` computes `indicated_yield` only; preferreds are bond-like (fixed dividends, par-value fundaments) — yield + duration + DV01 make the income book tradeable | `strategies/fixed_income.py`: `preferred_ytm(dividend, price, par, years)`, `macaulay_duration(cashflows, y, t)`, `modified_duration`, `dv01`, `bond_convexity` (all `float|None`, no-fabrication); screener columns `YTM` / `DMod` / `DV01` in `capital_income_screener.py` + `scripts/capital_income_screener.py --columns ytm` (default off) |
| 9 | **Credit-spread → hazard/default probability** — `s ≈ λ(1−RR)`, `PD(0,t) = 1 − e^{−λt}` | `credit_spread.credit_stress_level` gives bands but no default-probability read | `credit_spread.py`: `hazard_from_spread(spread, rr=0.4)`, `default_probability(spread, years, rr=0.4)`; render alongside the band in `get_credit_spread_read` (label assumption RR=0.4) |
| 10 | **Variance-swap fair strike approximation** — `K_var ≈ (2e^{rT}/T)[∫₀^F P(K)/K² dK + ∫_F^∞ C(K)/K² dK]` | cboe surface has OTM calls/puts that price variance; event-vol premium (earnings IV crush) is currently asserted, not quantified | `options_math.py`: `variance_swap_strike(chain, r, t, forward)` (trapz over strikes; needs min 3 strikes per side else None); advisory tool `get_variance_premium(ticker)` |

### Tier 3 — explicit non-goals (reasons)

| Formula | Why not now |
| --- | --- |
| Black–Litterman posterior / market-implied returns | needs explicit views + τ/Ω priors; single-name analysis-overlay has no view machinery; risk-parity already covers allocation |
| Fama–French 3/5-factor regression | requires monthly factor CSV downloads (new data source), US-only, low per-ticker decision signal; `capm_decomposition` already separates systematic/idiosyncratic |
| Heston / local-vol / Merton jump / binomial tree | pricing models for execution; the repo is analysis-only and the cboe surface already delivers **market** IV/Greeks — a stochastic-vol model adds no new decision number |
| ML (MSE/MAE/cross-entropy, ridge/lasso/elastic-net, PCA, F1/AUC) | repo is deterministic-first, no ML runtime; these are validation metrics with no model to validate |
| Monte-Carlo tail (Cholesky σ-path) | `var_cvar_horizon` covers the decision need; a full MC engine is out of proportion to data frequency |
| GBM/Euler–Maruyama simulators | backtest engine uses bar-matched fills, not price paths |

---

## 3. Wiring & conventions (every phase)

- **Pure, offline, `float|None`**: every new calculator degrades with an
  explicit unavailable on insufficient data (min-obs guards, never fabricated).
- **Compute-as-tools**: each calculator gets a `@tool` in `analysis_tools.py`,
  re-exported in `agent_utils`, bound to the right analyst ToolNode + prompt
  (market for vol/mean-reversion/execution; news/fundamentals where relevant).
- **Gates default OFF**: config keys + `TRADINGAGENTS_*` env overrides; the
  `volatility_estimator` switch (close|parkinson|garman_klass|ewma|garch) is
  off-by-default (close preserved) so existing runs are unchanged.
- **Tests**: hermetic, `pytest.mark.timeout`, synthetic inputs (seeded) —
  `tests/test_strategies_volatility_models.py`,
  `tests/test_strategies_mean_reversion.py`,
  `tests/test_fixed_income.py`, extend `test_book_risk` / `test_liquidity_risk`
  / `test_analysis_tools`.
- **Docs/README/CHANGELOG + trading_web mirror** after each phase.

## 4. Phases (dependency-ordered)

### Phase 1 — Volatility models (volatility_models.py: parkinson / garman_klass / ewma / garch11)
- New module + `get_volatility_estimators(ticker)` + `get_garch_volatility(ticker)` tools (market), `volatility_estimator` config switch wired into `regime.vol_percentile` + `size.volatility_target_scale`.
- Tests: known-input recovery (synthetic OHLC with prescribed range vol; EWMA recursion identity; GARCH recovers a simulated GARCH(1,1) process; <60 obs / non-converged → None).

### Phase 2 — Risk tail decomposition (book_risk incremental_var / component_var)
- `get_tail_decomposition(names, weights)` tool (market); components sum to total book VaR (sanity test); advisory only; render in `get_book_tail_risk` output.
- Tests: 2-asset synthetic covariance where one name dominates the tail; sum-conservation; degenerate Σ → None.

### Phase 3 — Mean-reversion quality + Roll spread
- `strategies/mean_reversion.py` (ar1_half_life / ou_half_life) + `get_mean_reversion_quality(ticker)` (market); `liquidity_risk.roll_spread` + render in `get_liquidity_risk` / `get_liquidation_days`.
- Tests: AR(1) with known φ → half-life; OU with known θ; an integrated (random-walk) series → None/non-reverting; Roll spread on synthetic prices with planted spread.

### Phase 4 — Fixed-income preferreds (strategies/fixed_income.py) + capital_income columns
- `preferred_ytm` / `macaulay_duration` / `modified_duration` / `dv01` / `bond_convexity`; `capital_income_screener` gains `YTM`/`DMod`/`DV01` columns (default off via flag).
- Tests: YTM formula recovery (par bond → coupon/par); duration of a zero-coupon = T; convexity positive; missing price/dividend → n/a.

### Phase 5 — Credit hazard + variance premium + IS (strategy-quality/eval)
- `credit_spread.hazard_from_spread` / `default_probability` rendered in `get_credit_spread_read`; `options_math.variance_swap_strike` + `get_variance_premium(ticker)` (news, event-vol); `evaluate.implementation_shortfall` wired into the paper-ledger row + `strategy_quality_report` execution block.
- Tests per piece (hermetic).

### Phase 6 — Web + docs
- trading_web `run_value_tools` += the new tools (+ App.jsx options + README + hermetic test); `api_reference.md` §6.4 tool table + §1.1 env keys; developer `04-strategies.md`; `Strategies/index.md` row; `AGENT_ONBOARDING.md` changelog; `CHANGELOG.md`.

## 5. Honest limits

- **Range-based vol assumptions**: Parkinson/GK presume continuous trading with no overnight gaps; label results as day-only estimates (the repo's daily OHLC has gaps on overnight/news days) — still strictly better than close-to-close for intraday risk.
- **GARCH estimation noise**: MLE on ≤ 260 daily obs is noisy; the tool reports `converged` + n and the long-run vol, and the `volatility_estimator` switch defaults to the current close-based path so nothing changes unless opted in.
- **Roll spread**: assumes zero drift, no serial correlation in the efficient price, and symmetric spreads — on daily bars it under-estimates true spread; use as a relative (cross-sectional) proxy, never an absolute market quote.
- **Component VaR**: the normal-covariance decomposition is exact only under joint normality; fine for book-tail attribution, not for fat-tailed stress (which `book_correlated_stress` already covers).
- **Preferred YTM**: uses `years`/par approximations; perpetual preferreds have no maturity — YTM rendered only when a call/redemption or duration horizon is inferable, else `n/a` (never convert perpetuals into a fake YTM).
- **Variance-swap strike**: approximates the log-contract integral with a finite OTM strike grid; needs ≥ 3 strikes per side, else `n/a`.

## 6. Sequencing & validation

P1 → P2 → P3 → P4 → P5 → P6 (P1/P2 are independent; P3 depends on nothing;
P4–P6 are independent too — batch where sensible). Each phase: hermetic tests
with `pytest-timeout`, `ruff check` clean, full-suite green, commit + push,
docs/README/CHANGELOG true, trading_web mirrored. Live smoke at P1:
`get_volatility_estimators('AAPL')` returns close/parkinson/gk/ewma side by
side; at P3 `get_mean_reversion_quality('SPY')` returns "non-reverting" (the
honest answer for an index).

Mapping: **quants.md §Statistics/Volatility → P1**, §Risk & Performance /
§Portfolio → P2, §Statistical Arbitrage / §Execution → P3, §Fixed Income /
Credit → P4–P5, §Options → P5, §How-to-use → ordering. quant2.md is the
condensed duplicate — its unique bits (Rho/thetas names, DV01, cashflow
PV) are covered by P4.