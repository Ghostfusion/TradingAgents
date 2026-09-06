# Quant-Finance Formulas Research — exhaustive gap scan vs. the existing strategy library

Status: **research only (2026-09-05), no code changed.** Web-validated across
factor models, options/vol, risk metrics, time-series statistics, execution,
macro rules, accounting quality, calendar effects, and portfolio overlays.
Each candidate is cross-checked against the 93 `strategies/*.py` modules to
confirm it is genuinely absent before being listed.

## 0. Method

1. Inventoried the existing library (93 modules; ~177 agent tools) and the
   covered areas: returns/technicals, factors (Alpha158-style, momentum,
   value, quality), valuation (DCF, EV multiples, Graham/NCAV/EPV), regime
   (HMM, choppiness), portfolio (HRP, risk-parity, min-variance, Kelly,
   Black-Litterman, Ledoit-Wolf, sector/industry-neutral z), backtest
   integrity (walk-forward, CPCV, PBO, PIT, delisted costs), risk (VaR/CVaR,
   EVT/GPD, drawdown events + recovery, Merton, credit hazard), options
   (BSM Greeks, vanna/vomma/charm, IV skew, GEX, breakeven/PMCC, expected
   move, OPEX), macro/regime, sentiment, orderflow/microstructure (Kyle,
   microprice, VIF, square-root impact), statistics (PSR, DSR, omega, Hurst,
   AR1/OU half-life, rank-IC/ICIR, cointegration/ECM, unit-root).
2. Deep web search per gap area (factor anomalies, evaluation statistics,
   higher-order Greeks, vol-surface metrics, drawdown/risk ratios, time
   series measures, execution models, macro rules, accounting models,
   calendar effects, portfolio overlays, copulas/Bayesian change detection,
   money management).
3. Verified each candidate against the repo; **already-present items are
   excluded** (PSR/DSR, Hurst, half-life, Ledoit-Wolf, vanna/vomma/charm,
   ulcer, downside deviation, square-root impact, HMM regime, fractional
   Kelly, profit factor).

## 1. Adopted list (genuinely absent, useful, buildable)

### A. Options / volatility surface (highest fit — the project already has a
strong options layer; these complete it)

| # | Formula | Where it fits |
|---|---|---|
| A1 | **Third-order Greeks: speed, zomma** — `speed = -Γ (1 + d1/σ√T)/S`, `zomma = Γ (d1·d2 − 1)/σ` | `strategies/options_math.py` already computes delta/gamma/vega/theta/rho/vanna/vomma/charm (BSM). Speed/zomma are the missing third-order legs; cheap, closed-form, unit-testable. Advisory: gamma stability near expiry / fast markets. |
| A2 | **Vol-surface shape metrics** — 25-delta risk reversal `RR = IV(25Δ call) − IV(25Δ put)`, 25-delta butterfly `BF = IV(25Δ call) + IV(25Δ put) − 2·IV(ATM)`, term-structure slope `TS = IV(1M) − IV(3M)` | `strategies/options_surface.py` has a single put/call skew ratio; the standard RR/BF/TS triad (the desk convention) is absent. Needs delta-interpolation across strikes — moderate effort. |
| A3 | **Model-free variance-swap fair strike (VIX methodology)** — `K_var = (2e^{rT}/T)[ ∫_0^F P(K)/K² dK + ∫_F^∞ C(K)/K² dK ]` (discrete: `Σ (ΔKᵢ/Kᵢ²) e^{rT} Q(Kᵢ)` + the `F/K₀` log-contract correction); vol strike = `√K_var` | The implied-move (simplified 1σ) exists; the full model-free strip — comparable *across* maturities, feeds variance-risk-premium and vol-term-structure reads — is absent. Chain-driven. |
| A4 | **Put-call parity violation / conversion-reversal arb screen** — check `C − P ≈ S − K·e^{−rT}` (with dividends: `− PV(D)`); flag persistent violations beyond costs | Project already fetches full option chains; a parity-violation flag is a cheap, deterministic market-quality/arbitrage signal absent today. |

### B. Risk metrics (downside-tail family)

| # | Formula | Notes |
|---|---|---|
| B1 | **Modified VaR (Cornish-Fisher)** — `z_CF = z + (z²−1)S/6 + (z³−3z)K/24 − (2z³−5z)S²/36`; `VaR_m = −(μ + z_CF·σ)` | Project has historical VaR/CVaR and EVT/GPD tail VaR; the Cornish-Fisher moment-corrected quantile (standard practice when returns are skewed/leptokurtic) sits between them. Cheap. |
| B2 | **Kappa ratio + lower partial moments** — `LPM_l = (1/n) Σ max(MAR − R, 0)^l`, `Kappa_l = (r̄ − MAR) / LPM_l^{1/l}` | Generalizes Sortino (l=2) with adjustable downside aversion; absent (downside deviation exists, LPM family doesn't). |
| B3 | **Burke ratio** — `(r̄ − r_f)/√(Σ_j D_j²)` over drawdown events + **Martin ratio (UPI)** — `(r̄ − r_f)/UlcerIndex` + **Pain index/ratio** | Ulcer index exists (evaluate.py); the drawdown-averaging siblings (Burke, Martin, Pain) don't. Cheap adds sharing the `drawdown_events` machinery. |
| B4 | **Gain-to-pain ratio** — `ΣR⁺ / |ΣR⁻|` | Journal has profit factor (gross wins/losses); return-based GPR on a return series is a distinct measure for strategy-quality rows. |
| B5 | **Risk of ruin + optimal f** — fixed-fraction ruin probability (derives from win rate, payoff, fraction; no single closed form — family of approximations) + Vince optimal f (max geometric growth) | Fractional Kelly exists (position_sizing, kelly_alloc); the ruin-probability survival constraint that Kelly alone ignores is absent. |

### C. Time-series / statistics

| # | Formula | Notes |
|---|---|---|
| C1 | **Lo-MacKinlay variance ratio** — `VR(k) = Var(r⁽ᵏ⁾)/(k·Var(r))` with the heteroskedasticity-robust z-stat | Hurst, AR1/OU half-life, unit-root all exist; VR(k) with significance is the standard complement (momentum vs mean-reversion verdict at multiple horizons). Cheap. |
| C2 | **Complexity/entropy of the return series** — normalized permutation entropy `PE = −Σ p(π)ln p(π)/ln m!`, approximate entropy `ApEn(m, r=0.2σ)`, Lempel-Ziv `C_LZ = c(n)log_a(n)/n` | Regime enrichment: `regime.py` uses vol/trend/HMM; entropy features (market-structure complexity) are a distinct, absent input — feeds HMM/choppiness overlays and regime-conditional sizing. |
| C3 | **Online shift detection — CUSUM/EWMA** — `C_t⁺ = max(0, C⁺_{t−1} + x_t − μ₀ − k)`, `k = δσ/2`, signal `C⁺ > h`; EWMA control limits `μ₀ ± L·σ√(λ/(2−λ)(1−(1−λ)^{2t}))` | Fast detection of small sustained shifts (mean/vol) — complements the HMM state classifier (slow, batch) with an online trigger. Distinct use-case; absent. |
| C4 | **Dependence beyond correlation — Kendall's τ + Student-t copula tail dependence** — `τ = (2/n(n−1)) Σ sgn(x_i−x_j)sgn(y_i−y_j)`; Gaussian-copula link `τ = (2/π)arcsin(ρ)`; t-copula tail `λ = 2·t_{ν+1}(−√((ν+1)(1−ρ)/(1+ρ)))` | `correlation_matrix` is Pearson-only; `cointegration_pair` covers linear dependence. Tail-dependence (joint-crash co-movement) for book risk is absent and is the standard complement to covariance-only views. |

### D. Factor / alpha

| # | Formula | Notes |
|---|---|---|
| D1 | **Lottery-factor screens: MAX + IVOL** — `MAX_t = max over daily returns in month`; IVOL = residual vol of a factor-model regression `r_i − r_f = α + β′f + ε`, `IVOL = √Var(ε)` | Cross-sectional predictors: high MAX/IVOL → lower forward returns (Bali et al. 2011; confirmed 2024-25 literature incl. China/Brazil). `alpha_zoo` has the expression engine but no MAX/IVOL screens; `cross_section.py` has z/neutralization/quantiles. Direct fit for the screener + cross_section. |
| D2 | **Harvey-Liu multiple-testing t-threshold (t ≈ 3) + power-curve adjustment** | DSR already penalizes multi-trial selection; a Harvey-Liu "haircut" t-stat as a lightweight report row (threshold guidance, not a gate) is a one-liner. Optional. |

### E. Accounting / fundamentals

| # | Formula | Notes |
|---|---|---|
| E1 | **Ohlson O-score (logit distress)** — `O = −1.32 − 0.407·SIZE + 6.03·TLTA − 1.43·WCTA + 0.0757·CLCA − 1.72·OENEG − 2.37·NITA − 1.83·FUTL + 0.285·INTWO − 0.521·CHIN`; `p = e^O/(1+e^O)` | Altman Z, Beneish M, Piotroski F all exist (normalized.py); the O-score (logit bankruptcy) is the standard missing sibling — validates distress from a different functional form. Also cheap: Zmijewski X-score `X = −4.336 − 4.513·ROA + 5.679·TLTA − 0.004·CLCA` (cutoff 0). |
| E2 | **Dechow-Dichev accrual-quality regression** — regress working-capital accruals on `CFO_{t−1}, CFO_t, CFO_{t+1}`; quality = residual std (smaller = better) | The project's accrual *ratio* is the point-in-time level; the DD regression measures accrual *quality* over time. Needs 3-period cash-flow history — feasible with the statement chain. |

### F. Macro rules

| # | Formula | Notes |
|---|---|---|
| F1 | **Taylor-rule implied rate + policy-rate deviation** — `i = r* + π + 0.5(π − π*) + 0.5(y − y*)` (smoothed variant anchored on the last funds rate); report `actual − rule` (tight/easy stance) | FRED macro data + cycle_tilt exist; the rule computation converting data → a single stance number is absent. Cheap, deterministic. |
| F2 | **Term-premium decomposition (ACM-lite)** — `y_10y = E[avg expected short path] + term premium` | Treasury curve exists; the yield-split into expectations + premium needs a Nelson-Siegel/affine fit — research-grade, heavier. Optional. |
| F3 | **Financial-conditions index (NFCI-lite)** — single-factor/weighted z across credit spreads, equity, vol, FX | All input series exist (credit_spread, treasury, vol); a standardized composite is a moderate add. | 

### G. Execution

| # | Formula | Notes |
|---|---|---|
| G1 | **Almgren-Chriss optimal schedule** — `x(t) = X·sinh(κ(T−t))/sinh(κT)`, `κ = √(λσ²/η)`; costs `E[IS] = ½γX² + ηΣ(Δx)²/τ`, `Var(IS) = σ²τΣx²` — plus TWAP/VWAP/POV schedules (`v_k = (x_{k−1}−x_k)/τ`) | Square-root impact + capacity + participation-scaled spread cost exist (backtest_models); the AC mean-variance optimal trajectory + per-schedule cost comparison is the missing execution layer. Realistic for a "how to execute this size" advisory read. |

### H. Portfolio overlay

| # | Formula | Notes |
|---|---|---|
| H1 | **Volatility-targeting overlay** — `w* = min(cap, σ_target/σ_realized)·w` (realized vol rolling, annualized) | `overlays.py` folds regime/sentiment; no risk-scaled exposure overlay. Relevant given the existing risk-sizing rows. Cheap. |
| H2 | **CPPI** — `E = m·max(P − F, 0)`, cushion `C = P − F`, risky weight `w = E/P` (floor-protected) | Distinct from vol-target; useful for the value-dip/portfolio legs. Medium effort. |

### I. Calendar (flagged low-priority — honest evidence caveat)

| # | Formula | Notes |
|---|---|---|
| I1 | **Turn-of-month / day-of-week / expiry-week window stats** — indicator regression `r_t = α + βD_t + ε`; TOM window = last day + first 3-4 days of next month | OPEX dates already computed. The 2026 literature review: anomalies persist in full samples but largely vanish post-1990s after data-mining correction; TOM retains some residuals but costs can erase it. Build only as an *investigative* stat row, never a gate. |

## 2. Explicitly excluded (already in the library)

PSR + DSR (evaluate.py), Hurst / AR1-half-life / OU-half-life (mean_reversion),
Ledoit-Wolf + EWMA cov (covariance_models), rank-IC + ICIR (signal_analysis),
square-root impact + participation cost + capacity (backtest_models),
vanna/vomma/charm (options_math), ulcer_index + downside_deviation +
drawdown_events-with-recovery (evaluate), HMM regime + choppiness (regime),
fractional Kelly + quarter-Kelly (size/position_sizing/kelly_alloc),
cointegration/ECM/Granger/VIF (statistical), Beneish/Piotroski/Altman
(normalized), Max drawdown + Calmar-family rows (evaluate/strategy_quality),
EVT/GPD tail VaR (tail_extreme_var), weight_entropy (portfolio — diversification,
not time-series entropy), profit factor (journal).

## 3. Suggested priority (for a future implementation pass)

1. **A1+A2** (speed/zomma; RR/BF/TS shape) — small, closes the options layer.
2. **B1+B2+B3** (Cornish-Fisher VaR; Kappa/LPM; Burke/Martin/Pain) — small,
   completes the downside family next to the existing VaR/CVaR/EVT reads.
3. **C1+C3** (variance ratio; CUSUM/EWMA) — small, statistical complements.
4. **E1** (Ohlson O-score + Zmijewski) — small, one more distress model family.
5. **F1** (Taylor rule) — cheap macro stance number.
6. **D1** (MAX/IVOL) — medium (needs a factor regression), highest alpha
   research value.
7. **G1** (Almgren-Chriss) — medium advisory execution read.
8. **H1** (vol-target overlay) — medium, portfolio-level.
9. **A3/A4** (var-swap strike; parity screen) — medium, chain-driven.
10. **C2/C4/F2/F3/H2/I1** — research-grade or low-priority; build only if a
    specific agent surface needs them.