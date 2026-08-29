"""Phase 0 - cost-aware evaluation harness.

Pure helpers for measuring agent/screener outcomes honestly: net-of-cost
metrics, walk-forward splits and overfitting guards. Used by the memory-log
realized-return path and by per-phase validation.

Evaluation breadth (Lean L3): Sortino, downside deviation, beta/alpha/
Treynor/information-ratio, Probabilistic Sharpe, rolling beta and underwater
drawdown collection — so a strategy is judged on more than a single Sharpe +
max-drawdown (the classic overfit hole).

All functions are vectorized over simple sequences (lists) so they work
offline on synthetic data and on exported memory-log returns.
"""

from __future__ import annotations

import math


def _clean(values: list) -> list[float]:
    """Finite-float clean of a series (drops None / non-numeric / non-finite)."""
    out: list[float] = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def net_returns(
    returns: list[float],
    cost_bps: float = 10.0,
    illiq: float | None = None,
    illiq_cost_mult: float = 1e5,
) -> list[float | None]:
    """Subtract a per-trade cost (basis points) from each period return.

    Item 3 (liquidity-aware costs): when ``illiq`` (Amihud ILLIQ) is provided,
    scale cost up for illiquid names (mirrors ``exits.net_of_cost``). None
    ``illiq`` keeps the flat-cost behavior (backward compatible).
    """
    cost = cost_bps / 10000.0
    if illiq is not None:
        cost += float(illiq) * float(illiq_cost_mult) / 10000.0
    return [r - cost if r is not None else None for r in returns]


def total_return(returns: list[float]) -> float:
    """Compounded total return; None entries are treated as zero-return gaps."""
    prod = 1.0
    for r in returns:
        if r is not None:
            prod *= 1.0 + r
    return prod - 1.0


def cagr(returns: list[float], periods_per_year: float = 252.0) -> float:
    """Annualized compound growth over the return series."""
    n = sum(1 for r in returns if r is not None)
    if n <= 0:
        return 0.0
    years = n / periods_per_year
    if years <= 0:
        return 0.0
    return (1.0 + total_return(returns)) ** (1.0 / years) - 1.0


def volatility(returns: list[float], periods_per_year: float = 252.0) -> float:
    """Annualized standard deviation of returns."""
    vals = _clean(returns)
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return math.sqrt(var * periods_per_year)


def sharpe(returns: list[float], risk_free: float = 0.0,
           periods_per_year: float = 252.0) -> float:
    """Annualized Sharpe ratio."""
    vol = volatility(returns, periods_per_year)
    if vol <= 0:
        return 0.0
    return (cagr(returns, periods_per_year) - risk_free) / vol


def deflated_sharpe(returns: list[float], n_trials: int = 100,
                    risk_free: float = 0.0,
                    periods_per_year: float = 252.0) -> float:
    """Lopez de Prado style deflated Sharpe: penalize multi-trial tuning.

    The expected maximum Sharpe across n independent trials is approximated
    (Euler-Mascheroni-based) and subtracted from the observed Sharpe.
    """
    observed = sharpe(returns, risk_free, periods_per_year)
    if n_trials <= 1:
        return observed
    # Approximation of E[max Z] for standard normals under independence.
    expected_max = math.sqrt(2.0 * math.log(n_trials))
    return observed - expected_max


def max_drawdown(equity_curve: list[float]) -> float:
    """Maximum peak-to-trough drawdown of a cumulative equity curve."""
    peak = float("-inf")
    worst = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak if peak > 0 else 0.0
        worst = max(worst, dd)
    return worst


def equity_curve(returns: list[float], start: float = 100.0) -> list[float]:
    """Cumulative equity curve from period returns."""
    curve: list[float] = []
    level = start
    for r in returns:
        level *= 1.0 + (r if r is not None else 0.0)
        curve.append(level)
    return curve


def walk_forward_splits(returns: list[float], train_len: int, test_len: int):
    """Yield (train, test) return slices for walk-forward evaluation."""
    i = 0
    while i + train_len + test_len <= len(returns):
        yield returns[i:i + train_len], returns[i + train_len:i + train_len + test_len]
        i += test_len


def pbo_flag(results_by_trial: list[float], test_results: list[float],
             threshold: float = 0.0) -> bool:
    """Crude overfit flag: best-trial in-sample picks fail out-of-sample."""
    if not results_by_trial or not test_results:
        return False
    best_idx = max(range(len(results_by_trial)), key=lambda i: results_by_trial[i])
    return test_results[best_idx] < threshold


def skewness(returns: list[float]) -> float | None:
    """Standardized skewness (γ3); None for <3 finite observations."""
    vals = _clean(returns)
    if len(vals) < 3:
        return None
    n = len(vals)
    mean = sum(vals) / n
    m2 = sum((v - mean) ** 2 for v in vals) / n
    if m2 == 0:
        return None
    m3 = sum((v - mean) ** 3 for v in vals) / n
    return m3 / (m2 ** 1.5)


def kurtosis(returns: list[float]) -> float | None:
    """Standardized kurtosis (γ4, normal = 3); None for <4 observations."""
    vals = _clean(returns)
    if len(vals) < 4:
        return None
    n = len(vals)
    mean = sum(vals) / n
    m2 = sum((v - mean) ** 2 for v in vals) / n
    if m2 == 0:
        return None
    m4 = sum((v - mean) ** 4 for v in vals) / n
    return m4 / (m2 ** 2)


def downside_deviation(returns: list[float], mar: float = 0.0,
                       periods_per_year: float = 252.0) -> float | None:
    """Annualized downside deviation about a minimum-return target (MAR).

    Only observations below the target contribute (Lean's Sortino
    denominator); None for an empty/short series.
    """
    vals = _clean(returns)
    if not vals:
        return None
    dd = sum(max(mar - v, 0.0) ** 2 for v in vals) / len(vals)
    return math.sqrt(dd * periods_per_year)


def sortino(returns: list[float], mar: float = 0.0,
            periods_per_year: float = 252.0) -> float | None:
    """Annualized Sortino: excess CAGR over target per unit of downside dev."""
    ddev = downside_deviation(returns, mar, periods_per_year)
    if ddev is None or ddev <= 0:
        return None
    return (cagr(returns, periods_per_year) - mar) / ddev


def tracking_error(returns: list[float], benchmark: list[float],
                   periods_per_year: float = 252.0) -> float | None:
    """Annualized std dev of (algo - benchmark) period returns."""
    r = _clean(returns)
    b = _clean(benchmark)
    n = min(len(r), len(b))
    if n < 2:
        return None
    diff = [r[i] - b[i] for i in range(n)]
    var = sum(d * d for d in diff) / (n - 1)
    return math.sqrt(var * periods_per_year)


def information_ratio(returns: list[float], benchmark: list[float],
                      periods_per_year: float = 252.0) -> float | None:
    """Annualized excess return per unit of tracking error."""
    te = tracking_error(returns, benchmark, periods_per_year)
    if te is None or te <= 0:
        return None
    return (cagr(returns, periods_per_year) - cagr(benchmark, periods_per_year)) / te


def beta(returns: list[float], benchmark: list[float],
         periods_per_year: float = 252.0) -> float | None:
    """Algo beta vs benchmark: cov(algo, bench) / var(bench)."""
    r = _clean(returns)
    b = _clean(benchmark)
    n = min(len(r), len(b))
    if n < 2:
        return None
    rb = r[:n]
    bb = b[:n]
    mr = sum(rb) / n
    mb = sum(bb) / n
    varb = sum((x - mb) ** 2 for x in bb) / (n - 1)
    if varb <= 0:
        return None
    cov = sum((rb[i] - mr) * (bb[i] - mb) for i in range(n)) / (n - 1)
    return cov / varb


def alpha(returns: list[float], benchmark: list[float], risk_free: float = 0.0,
          periods_per_year: float = 252.0) -> float | None:
    """Jensen's alpha: annPerf - (rf + beta*(benchAnnPerf - rf))."""
    b = beta(returns, benchmark, periods_per_year)
    if b is None:
        return None
    return (cagr(returns, periods_per_year) - risk_free
            - b * (cagr(benchmark, periods_per_year) - risk_free))


def treynor(returns: list[float], benchmark: list[float], risk_free: float = 0.0,
            periods_per_year: float = 252.0) -> float | None:
    """Excess annual return per unit of beta."""
    b = beta(returns, benchmark, periods_per_year)
    if b is None or b == 0:
        return None
    return (cagr(returns, periods_per_year) - risk_free) / b


def rolling_beta(returns: list[float], benchmark: list[float],
                 window: int = 132) -> list[float | None]:
    """Per-window beta series over aligned returns (Lean window 132 default)."""
    r = _clean(returns)
    b = _clean(benchmark)
    out: list[float | None] = []
    for end in range(window, min(len(r), len(b)) + 1):
        out.append(beta(r[end - window:end], b[end - window:end]))
    return out


def probabilistic_sharpe(returns: list[float], benchmark_sharpe: float = 0.0,
                         periods_per_year: float = 252.0) -> float | None:
    """Bailey & Lopez de Prado Probabilistic Sharpe Ratio.

    Uses the NON-annualized per-observation Sharpe (mean/std) as the point
    estimate, with skewness/kurtosis correction inside the estimator's
    standard error — PSR = Phi((SR_obs - SR_bench) /
    sqrt((1 - g3*SR + (g4-1)/4*SR^2)/(n-1))). None for <4 observations or a
    degenerate estimator variance. Advisory significance, not a mandate.
    """
    vals = _clean(returns)
    if len(vals) < 4:
        return None
    mean = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))
    if sd <= 0:
        return None
    sr = mean / sd
    g3 = skewness(vals)
    g4 = kurtosis(vals)  # standardized kurtosis, normal = 3
    if g3 is None or g4 is None:
        return None
    var_est = (1 - g3 * sr + (g4 - 1) / 4 * sr ** 2) / (len(vals) - 1)
    if var_est <= 0:
        return None
    z = (sr - benchmark_sharpe) / math.sqrt(var_est)
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def underwater_drawdowns(equity: list[float]) -> list[dict]:
    """Sequence of peak-to-trough-to-recovery drawdown events.

    Each event: ``{'peak','trough','depth','recovery'}`` where ``recovery`` is
    the number of bars to get back to the prior peak (None if still underwater
    at series end). Complement to the single ``max_drawdown`` scalar.
    """
    vals = _clean(equity)
    events: list[dict] = []
    if len(vals) < 2:
        return events
    peak = vals[0]
    trough = vals[0]
    trough_i = 0
    for i, v in enumerate(vals[1:], start=1):
        if v >= peak:
            if trough < peak:
                events.append({
                    "peak": peak,
                    "trough": trough,
                    "depth": (peak - trough) / peak if peak > 0 else 0.0,
                    "recovery": i - trough_i,
                })
            peak = v
            trough = v
            trough_i = i
        elif v < trough:
            trough = v
            trough_i = i
    if trough < peak:
        events.append({
            "peak": peak,
            "trough": trough,
            "depth": (peak - trough) / peak if peak > 0 else 0.0,
            "recovery": None,
        })
    return events


__all__ = [
    "net_returns", "total_return", "cagr", "volatility", "sharpe",
    "deflated_sharpe", "max_drawdown", "equity_curve", "walk_forward_splits",
    "pbo_flag",
    "skewness", "kurtosis", "downside_deviation", "sortino",
    "tracking_error", "information_ratio", "beta", "alpha", "treynor",
    "rolling_beta", "probabilistic_sharpe", "underwater_drawdowns",
]
