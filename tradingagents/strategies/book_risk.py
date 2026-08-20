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


__all__ = ["simple_var", "cvar", "portfolio_returns", "stress_loss", "drawdown_gate"]
