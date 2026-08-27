"""Phase 0 - cost-aware evaluation harness.

Pure helpers for measuring agent/screener outcomes honestly: net-of-cost
metrics, walk-forward splits and overfitting guards. Used by the memory-log
realized-return path and by per-phase validation.

All functions are vectorized over simple sequences (lists) so they work
offline on synthetic data and on exported memory-log returns.
"""

from __future__ import annotations

import math


def net_returns(
    returns: list[float],
    cost_bps: float = 10.0,
    illiq: float | None = None,
    illiq_cost_mult: float = 1e5,
) -> list[float]:
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
    vals = [r for r in returns if r is not None]
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


__all__ = [
    "net_returns", "total_return", "cagr", "volatility", "sharpe",
    "deflated_sharpe", "max_drawdown", "equity_curve", "walk_forward_splits",
    "pbo_flag",
]
