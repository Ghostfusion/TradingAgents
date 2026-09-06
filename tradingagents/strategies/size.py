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
    returns: list[float],
    target_vol: float = 0.15,
    decay: float = 0.94,
    vol_override: float | None = None,
) -> float:
    """Scale (0..3) so the portfolio targets `target_vol` annualized vol.

    Uses EWR volatility by default; ``vol_override`` supplies an externally
    computed annualized vol (e.g. GARCH long-run vol from the
    ``volatility_estimator`` config) so the sizing reflects the chosen
    estimator. Returns None-safe 0 on no data.
    """
    import math

    if len(returns) < 5 or target_vol <= 0:
        return 0.0
    if vol_override is not None and vol_override > 0:
        raw = target_vol / float(vol_override)
        return max(0.0, min(raw, 3.0))
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
        # No-fabrication contract: insufficient/degenerate data -> None, never a
        # fabricated stop at 0 (a "stop at zero" read as a plausible level).
        return None
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


def modified_var(returns: list[float], alpha: float = 0.05,
                 periods_per_year: float = 252.0) -> float | None:
    """Cornish-Fisher modified VaR (skewness/kurtosis-adjusted quantile).

    z_CF = z + (z^2 - 1)*S/6 + (z^3 - 3z)*K/24 - (2z^3 - 5z)*S^2/36; VaR =
    -(mu + z_CF * sigma) over the horizon. More accurate than Gaussian VaR for
    skewed/leptokurtic returns (the standard practice between historical and
    EVT VaR). Returns a positive loss magnitude (None on <5 obs / zero sigma).
    """
    vals = [float(r) for r in returns if r is not None]
    if len(vals) < 5:
        return None
    from tradingagents.strategies.evaluate import kurtosis, skewness

    mu = sum(vals) / len(vals)
    var = sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)
    sig = var ** 0.5
    if sig <= 0:
        return None
    from statistics import NormalDist

    z = NormalDist().inv_cdf(float(alpha))
    s = skewness(vals) or 0.0
    k = kurtosis(vals) or 0.0
    z_cf = z + (z * z - 1.0) * s / 6.0 + (z * z * z - 3.0 * z) * k / 24.0 \
        - (2.0 * z * z * z - 5.0 * z) * s * s / 36.0
    return -(mu + z_cf * sig)


def risk_of_ruin(p_win: float, payoff: float, fraction: float) -> float | None:
    """Approximate fixed-fraction risk of ruin (survival constraint).

    Ruin = falling to zero after repeated trades at a fixed fraction of
    capital. Uses the biased-random-walk approximation: with per-trade log
    growth ``g = p*ln(1+f*b) + (1-p)*ln(1-f)`` and per-trade log variance
    ``v = p*ln(1+f*b)^2 + (1-p)*ln(1-f)^2 - g^2``, the infinite-horizon ruin
    probability from unit bankroll is ``min(exp(-2g/v), 1)`` for a positive
    edge, and ~1 for a negative edge (eventual ruin). This is the survival
    constraint fractional Kelly ignores. None when inputs unusable.
    """
    try:
        p = float(p_win)
        b = float(payoff)
        f = float(fraction)
    except (TypeError, ValueError):
        return None
    if not (0.0 < p < 1.0) or b <= 0 or f <= 0 or f >= 1.0:
        return None
    import math

    l1 = math.log(1.0 + f * b)
    l2 = math.log(1.0 - f)
    g = p * l1 + (1.0 - p) * l2
    if g < 0:
        # Negative expected log growth -> ruin is (asymptotically) certain.
        return 1.0
    v = p * l1 * l1 + (1.0 - p) * l2 * l2 - g * g
    if v <= 0:
        return 0.0
    return min(math.exp(-2.0 * g / v), 1.0)


def optimal_f(returns: list[float], fracs: int = 80) -> float | None:
    """Vince optimal f: the fixed fraction maximizing geometric growth
    (max of prod(1 + f*r_i) over a grid). Advisory sizing input — combine with
    fractional-Kelly discipline; never used directly as a live size.
    """
    vals = [float(r) for r in returns if r is not None]
    if len(vals) < 5 or any(v <= -1.0 for v in vals):
        return None
    best_f, best_g = 0.0, -1.0
    for i in range(1, fracs + 1):
        f = i / float(fracs)
        g = 1.0
        for v in vals:
            g *= (1.0 + f * v)
        if g > best_g:
            best_g, best_f = g, f
    return best_f


__all__ = [
    "kelly_fraction",
    "position_size_kelly",
    "volatility_target_scale",
    "atr",
    "stop_loss_atr",
    "cvar_budget",
    "position_size_with_risk",
    "modified_var",
    "risk_of_ruin",
    "optimal_f",
]
