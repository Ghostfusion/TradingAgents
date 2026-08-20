"""Phase 2 - formal money management.

Quarter-Kelly position sizing from a confidence (win-probability) estimate,
volatility targeting with smoothing (Moreira-Muir style), ATR-based stops and
a portfolio-level CVaR budget.

Kappa: quarter-Kelly = 0.25 * (2*p - 1) / win-loss ratio net of costs.
Kept conservative: raw Kelly shape clipped, then scaled by a fraction.
"""

from __future__ import annotations


def kelly_fraction(p_win: float, odds: float = 1.0) -> float:
    """Full Kelly fraction (b*p - q)/b with b=odds (win/loss payoff ratio)."""
    if odds <= 0:
        return 0.0
    p = max(0.0, min(1.0, float(p_win)))
    q = 1.0 - p
    f = (odds * p - q) / odds
    return max(0.0, min(f, 1.0))


def position_size_kelly(
    confidence: float, odds: float = 1.0, fraction: float = 0.25, max_size: float = 1.0
) -> float:
    """Portfolio fraction for a signal with `confidence` win probability."""
    f = kelly_fraction(confidence, odds)
    return max(0.0, min(f * fraction, max_size))


def volatility_target_scale(
    returns: list[float], target_vol: float = 0.15, decay: float = 0.94
) -> float:
    """Scale (0..3) so the portfolio targets `target_vol` annualized vol.

    Uses EWR volatility; smoothing caps turnover. Returns None-safe 0 on no data.
    """
    import math

    if len(returns) < 5 or target_vol <= 0:
        return 0.0
    var = 0.0
    for r in returns:
        var = decay * var + (1.0 - decay) * (r * r)
    eff_var = var * 252.0
    if eff_var <= 0:
        return 0.0
    raw = target_vol / math.sqrt(eff_var)
    return max(0.0, min(raw, 3.0))


def atr(high: list[float], low: list[float], close: list[float], window: int = 14) -> float:
    """Average True Range over the window."""
    if not (len(high) == len(low) == len(close)) or len(high) < 2:
        return 0.0
    trs = []
    for i in range(1, len(high)):
        tr = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        trs.append(tr)
    sample = trs[-window:]
    return sum(sample) / len(sample) if sample else 0.0


def stop_loss_atr(
    close: list[float], high: list[float], low: list[float], atr_mult: float = 2.0
) -> float:
    """Stop level = close - atr_mult * ATR; None when insufficient data."""
    a = atr(high, low, close)
    if a <= 0 or not close:
        return 0.0
    return close[-1] - atr_mult * a


def cvar_budget(returns: list[float], alpha: float = 0.05, budget: float = 0.05) -> float:
    """Max fraction of budget the expected tail loss may consume.

    returns = portfolio strategy returns; alpha = tail quantile.
    Returns the (negative) tail mean; caller compares vs |budget|.
    """
    vals = sorted([r for r in returns if r is not None])
    if not vals:
        return 0.0
    k = max(1, int(alpha * len(vals)))
    tail = vals[:k]
    return sum(tail) / len(tail)


def position_size_with_risk(
    confidence: float,
    odds: float,
    atr: float,
    close: float,
    risk_per_trade: float = 0.01,
    cap: float = 1.0,
) -> float:
    """Cap Kelly share by risk-per-trade / stop distance.

    size = min(kelly_frac_quarter, risk_per_trade / stop_distance_pct)
    """
    stop_dist = (atr * 2.0) / close if close > 0 and atr > 0 else 0.0
    kelly_part = kelly_fraction(confidence, odds) * 0.25
    risk_part = (risk_per_trade / stop_dist) if stop_dist and risk_per_trade else cap
    return max(0.0, min(kelly_part, risk_part, cap))


__all__ = [
    "kelly_fraction",
    "position_size_kelly",
    "volatility_target_scale",
    "atr",
    "stop_loss_atr",
    "cvar_budget",
    "position_size_with_risk",
]
