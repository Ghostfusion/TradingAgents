"""R2 - book & tail risk: VaR/CVaR, scenario shocks, drawdown governor.

Pure helpers over return series and weights; deterministic and offline.
"""

from __future__ import annotations


def simple_var(returns: list, alpha: float = 0.05) -> float | None:
    """Historical VaR: alpha-quantile of returns (negative = loss)."""
    vals = sorted([float(r) for r in returns if r is not None])
    if not vals:
        return None
    k = max(1, int(alpha * len(vals)))
    return vals[k - 1]


def cvar(returns: list, alpha: float = 0.05) -> float | None:
    """Historical CVaR: mean of the worst alpha tail (negative = loss)."""
    vals = sorted([float(r) for r in returns if r is not None])
    if not vals:
        return None
    k = max(1, int(alpha * len(vals)))
    tail = vals[:k]
    return sum(tail) / len(tail)


def portfolio_cvar(
    returns_by_name: dict,
    weights: dict | None = None,
    alpha: float = 0.05,
) -> float | None:
    """Portfolio CVaR from one return series per name (aligned by index).

    Mixes the per-name daily return series with ``weights`` via
    :func:`portfolio_returns`, then takes the historical CVaR of the weighted
    book series. Semantics:

    - weights summing to **1.0** -> the normalized relative book (historical
      behavior).
    - weights summing to **< 1.0** -> the remainder is implicitly a **zero
      -return cash sleeve** (e.g. money market / cash in the account): the
      mixed series uses the raw (un-normalized) weights, so the daily returns
      are scaled by the invested fraction and the CVaR is diluted by cash
      holding. This is how "include cash as overall portfolio" is honored.
    - weights summing to **> 1.0** (config error) -> normalized down to 1.0
      to remain a valid portfolio.
    - no weights / all-zero -> equal weight across the provided names.

    Returns None when the series cannot be aligned (fewer than two names, or a
    name whose series is missing/short so no common index exists).
    """
    names = list(returns_by_name or {})
    if len(names) < 2:
        return None
    w = weights or {}
    total = sum(float(w.get(n, 0.0) or 0.0) for n in names)
    if total <= 0:
        # No weights given (or all zero): equal share per name.
        share = 1.0 / len(names)
        norm = dict.fromkeys(names, share)
    elif total > 1.0:
        # Over-allocated config: clamp to a valid portfolio (normalize down).
        norm = {n: float(w.get(n, 0.0) or 0.0) / total for n in names}
    else:
        # total in (0, 1]: use the raw weights so the remainder (1 - total)
        # stays as an implicit zero-return cash sleeve (dilutes the tail).
        norm = {n: float(w.get(n, 0.0) or 0.0) for n in names}
    mixed = portfolio_returns(norm, returns_by_name)
    if not mixed:
        return None
    return cvar(mixed, alpha)


def portfolio_returns(weights: dict, returns_by_name: dict) -> list:
    """Weighted aggregate portfolio return series (names aligned by index)."""
    keys = list(weights)
    series = [returns_by_name.get(k) for k in keys]
    if any(s is None for s in series):
        return []
    n = len(series[0])
    out = []
    for i in range(n):
        row = 0.0
        ok = True
        for w, s in zip([weights[k] for k in keys], series, strict=True):
            if i >= len(s):
                ok = False
                break
            v = s[i]
            if v is None:
                ok = False
                break
            row += float(w) * float(v)
        if ok:
            out.append(row)
    return out


def stress_loss(weights: dict, shock: float = -0.10) -> float:
    """Uniform shock loss (positive number) under given weights."""
    return -float(shock) * sum(max(0.0, float(w)) for w in weights.values())


def drawdown_gate(drawdown_pct: float | None, limit_pct: float = 0.10) -> bool:
    """True = new risk blocked while realized drawdown exceeds the limit."""
    if drawdown_pct is None:
        return False
    return float(drawdown_pct) > float(limit_pct)


__all__ = ["simple_var", "cvar", "portfolio_cvar", "portfolio_returns", "stress_loss", "drawdown_gate"]
