# Quant-Engine Additions — Design & Implementation (HRP, 12-1 momentum, Omega, industry-neutral z)

Status: **design + implementation (2026-09-05).** From a pasted end-to-end
quant-equity spec (§1–§6) reviewed against the repo and validated by web
research. Four genuinely new items are implemented here — HRP portfolio
construction, 12-1 momentum, the Omega ratio, and industry-neutralized
factor z-scores. Everything else in the spec was already adopted (the repo's
architecture validates the spec: PIT → factor → composite → covariance →
optimizer → backtest). All additions are advisory, None-safe, and follow the
repo's pure/offline conventions.

## 1. What the spec validated as already-adopted

| Spec § | Repo machinery | Verdict |
| --- | --- | --- |
| §2 winsorize → z → composite | `cross_section.winsorize` (1/99) + rank/z + composite | already adopted |
| §2 Piotroski / EV/EBITDA / ROIC / E-P | `quantitative_scores` / `fundamental_floors` / `normalized` | already adopted |
| §3 vol / beta+alpha / MDD / VaR / CVaR | `evaluate.py`, `get_capm_risk`, `get_tail_risk`, `get_horizon_var` | already adopted |
| §4 Sharpe / Sortino / Calmar / IR / Treynor | `get_strategy_quality` | already adopted |
| §6 Ledoit-Wolf covariance | `covariance_models.py` | already adopted |
| §5 MVO / risk-parity | `portfolio_optimizer` (`risk_parity_weights`, `min_variance_weights`…) | already adopted |
| §6 end-to-end flow | `effective_date` → `cross_section` → `covariance_models` → `portfolio` → `evaluate.py` | validates the repo's architecture |

## 2. The four additions (with web evidence)

### 2.1 HRP — Hierarchical Risk Parity (`strategies/hierarchical_risk_parity.py` + `get_hrp_alloc`)

- **Evidence:** HRP is more robust out-of-sample than (unconstrained) MVO,
  especially under noisy covariance; avoids the Σ inversion instability; 2025
  Columbia study: more robust to composition changes + limits extreme losses
  better (returns more conservative). Not a higher-return alpha source.
- **Algorithm** (Lopez de Prado): (1) distance `d = sqrt(0.5*(1-ρ))` from the
  covariance matrix; (2) single-linkage hierarchical clustering; (3)
  quasi-diagonalization (reorder so correlated assets are adjacent); (4)
  recursive bisection splitting risk inverse to cluster variance.
- Pure/offline, reuses the aligned-returns convention; degrades to
  equal-weight on unusable covariance (like `portfolio_optimizer`).
- Tool: `get_hrp_alloc(returns_by_name)` — HRP weights + cluster structure +
  note; bound to the market analyst.

### 2.2 12-1 Momentum (`momentum_12_1`)

- **Evidence:** the canonical Jegadeesh–Titman specification — rank on
  t−12→t−2, **skip the most recent month** because t−1 exhibits short-term
  reversal, not continuation; classic ~1%/mo. The repo's momentum reads
  (clenow/TS/pillars) use other windows and don't skip the last month.
- Implementation: `momentum_12_1(closes)` = `P[-21] / P[-252] - 1` (skip the
  latest 21 bars); None-safe; a small pure read (`get_momentum_12_1` tool or
  a field on the existing `get_momentum_detail` read).

### 2.3 Omega Ratio (`omega_ratio` + a row in `get_strategy_quality`)

- **Evidence:** full-distribution (non-parametric) ratio of gains to losses
  below a threshold L; better than Sharpe for skewed/fat-tailed returns;
  threshold-based (investor-specific); little add under ~symmetric returns.
- Implementation: `omega_ratio(returns, threshold) =
  sum(max(r-L,0))/(sum(max(L-r,0)))` over the return series;
  `get_strategy_quality` gains an Omega row (threshold = mean or 0).

### 2.4 Industry-Neutralized Factor Z (`cross_section.industry_neutral_z`)

- **Evidence:** Grinold–Kahn — demean each factor by its industry mean (or
  residualize on industry dummies), then z-score; removes the industry
  component so the signal is sector-relative; standard cross-sectional
  practice.
- Implementation: `industry_neutral_z(values, sector_map, lower_q, upper_q)` =
  winsorize → demean by sector → z-score; pure, reuses `winsorize`.

## 3. Non-goals

- Unusual-activity/flow feeds (data-gap); execution/sizing (no-execution
  mandate); anything beyond the four additions above.

## 4. Honest limits

- HRP is a **risk-side** improvement (robust, drawdown-limiting), not an
  alpha source; "more conservative in returns."
- Omega adds little under ~symmetric returns — a complement to Sharpe, not a
  replacement.
- Industry-neutralization needs sector membership per name; degrades to
  plain z when absent.
- 12-1 skip needs ≥252 bars (else None, never fabricated).

## 5. Phases

1. `docs/design_quant_engine_additions.md` (this file).
2. **HRP**: `hierarchical_risk_parity.py` + `get_hrp_alloc` + bind + tests.
3. **12-1 momentum**: `momentum_12_1` + tool/momentum-detail field + tests.
4. **Omega**: `omega_ratio` + `get_strategy_quality` row + tests.
5. **Industry-neutral z**: `cross_section.industry_neutral_z` + tests.
6. Docs (api_reference / CHANGELOG / README / session / index if appropriate) +
   suite + commit + push.