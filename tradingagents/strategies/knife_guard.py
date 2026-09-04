"""Composite knife-guard engine (falling-knife score + graduated response).

Builds a weighted composite knife score K from five normalized components and
maps it to a graduated size multiplier F_knife (1.0 / 0.5 / 0.25 / 0.0) plus a
separate transaction-cost guard band (Davis-Norman / Shreve-Soner cube-root
no-trade half-width).

Design notes (from the knife-guard review + the composite-score material):

* Thresholds are NOT universal constants — the defaults here are starting
  points and should be calibrated from the asset universe, timeframe and
  transaction costs (the material's explicit caution). All advisory.
* The score is continuous on purpose: a borderline K=2.6 scales size to 0.25x
  instead of flipping from "buy" to "don't buy" (graduated risk response).
* Directional conditioning everywhere: volume/ATR legs only count when the
  price is actually falling (or below the slow EMA) so the guard never blocks
  a rapid up-breakout.

Severity legs (each >= 0; bigger = worse):

* s_ret  = max(0, -Z_return)         momentum crash (short-window return z)
* s_vol  = max(0, +Z_volume-ratio)   volume spike z, only while the last bar fell
* s_atr  = max(0, +Z_atr-ratio)      abnormal range z, only while close < EMA20
* s_dd   = max(0, -Z_drawdown)       3-day drawdown z
* s_of   = scaled downside VPIN     max(0, (vpin-0.5)/0.5) when given

K = sum(w_i * s_i), weights default to the material's suggested balance
[0.25, 0.20, 0.20, 0.20, 0.15].
"""

from __future__ import annotations

from typing import Any

DEFAULT_WEIGHTS: dict[str, float] = {
    "ret": 0.25,
    "vol": 0.20,
    "atr": 0.20,
    "dd": 0.20,
    "of": 0.15,
}
DEFAULT_BANDS: tuple[float, float, float] = (1.5, 2.5, 3.0)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _std(values: list[float], mean: float | None = None) -> float | None:
    if len(values) < 2:
        return None
    m = mean if mean is not None else _mean(values)
    if m is None:
        return None
    var = sum((v - m) ** 2 for v in values) / len(values)
    return var ** 0.5


def _z(value: float | None, mean: float | None, sd: float | None) -> float | None:
    if value is None or mean is None or sd is None or sd <= 0:
        return None
    return (value - mean) / sd


def _returns(closes: list[float], window: int = 20) -> list[float]:
    out = []
    for i in range(max(1, len(closes) - window), len(closes)):
        if closes[i - 1] > 0:
            out.append(closes[i] / closes[i - 1] - 1.0)
    return out


def momentum_return_z(closes: list[float], lookback: int = 3, window: int = 20) -> float | None:
    """Z-score of the last ``lookback``-day return against the rolling window."""
    rets = _returns(closes, window=window)
    if len(rets) < max(8, window // 2):
        return None
    mean = _mean(rets[:-lookback]) if len(rets) > lookback else None
    sd = _std(rets[:-lookback], mean) if mean is not None else None
    if mean is None or sd is None or sd <= 0:
        return None
    last_ret = _returns(closes, window=lookback)
    if not last_ret:
        return None
    return (last_ret[-1] - mean) / sd


def volume_shock_z(volumes: list[float], window: int = 20) -> float | None:
    """Z of the volume/median-volume ratio over the rolling window."""
    if not volumes or len(volumes) < max(8, window // 2):
        return None
    sample = volumes[-window:]
    med = sorted(sample)[len(sample) // 2] if sample else None
    if not med or med <= 0:
        return None
    ratios = [v / med for v in sample]
    mean = _mean(ratios)
    sd = _std(ratios, mean)
    # ratios are already v/median - do NOT divide again by the median
    return _z(ratios[-1], mean, sd)


def _true_range(highs: list[float], lows: list[float], closes: list[float], i: int) -> float:
    h = highs[i]
    low_ = lows[i]
    pc = closes[i - 1]
    return max(h - low_, abs(h - pc), abs(low_ - pc))


def atr_ratio_z(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    atr_window: int = 14,
    z_window: int = 20,
) -> float | None:
    """Z of the latest TR/ATR ratio over the rolling window (ATR shock)."""
    if not highs or not lows or not closes or len(closes) < max(atr_window + 4, z_window + atr_window):
        return None
    trs = [_true_range(highs, lows, closes, i) for i in range(1, len(closes))]
    a = _mean(trs[-atr_window:]) if trs else None
    if not a or a <= 0:
        return None
    ratios = [t / a for t in trs[-z_window:]]
    mean = _mean(ratios)
    sd = _std(ratios, mean)
    return _z(ratios[-1], mean, sd)


def drawdown_3d_z(closes: list[float], lookback: int = 3, window: int = 20) -> float | None:
    """Z of the last ``lookback``-day drawdown (negative returns deepen it)."""
    rets = _returns(closes, window=window)
    if len(rets) <= lookback:
        return None
    base = rets[: len(rets) - lookback]
    mean = _mean(base)
    sd = _std(base, mean)
    if mean is None or sd is None or sd <= 0:
        return None
    last = sum(rets[-lookback:])
    return (last - mean) / sd


def _ema_last(closes: list[float], window: int = 20) -> float | None:
    if len(closes) < window:
        return None
    k = 2.0 / (window + 1.0)
    ema = sum(closes[:window]) / window
    for c in closes[window:]:
        ema = c * k + ema * (1.0 - k)
    return ema


def knife_score(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
    vpin_downside: float | None = None,
    weights: dict[str, float] | None = None,
    ema_window: int = 20,
) -> dict[str, Any]:
    """Composite falling-knife score.

    Returns a dict with ``K`` (weighted severity sum, ~0..3+), the per-leg
    severities and z's, the regime flag (close below slow EMA) and the
    graduated ``factor`` from ``knife_factor``.

    Args:
        closes: daily close series (newest last).
        highs/lows: daily OHLC extremes (ATR leg; None disables that leg).
        volumes: daily volumes (volume-shock leg; None disables).
        vpin_downside: downside-conditioned VPIN read (0..1) — the order-flow
            leg; None disables.
        weights: per-leg weights; defaults to ``DEFAULT_WEIGHTS``.
        ema_window: slow EMA for the regime conditioning.

    Returns:
        dict: {K, factors, severities, z's, regime, factor, band}
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    last_ret = None
    if len(closes) >= 2 and closes[-2] > 0:
        last_ret = closes[-1] / closes[-2] - 1.0

    z_ret = momentum_return_z(closes, lookback=3, window=20)
    s_ret = max(0.0, -z_ret) if z_ret is not None else 0.0

    z_vol = volume_shock_z(volumes) if volumes else None
    s_vol = (max(0.0, z_vol) if z_vol is not None else 0.0) if (last_ret is not None and last_ret < 0) else 0.0

    z_atr = atr_ratio_z(highs, lows, closes) if (highs and lows) else None
    ema = _ema_last(closes, ema_window)
    below_ema = ema is not None and closes[-1] < ema
    s_atr = (max(0.0, z_atr) if z_atr is not None else 0.0) if below_ema else 0.0

    z_dd = drawdown_3d_z(closes, lookback=3, window=20)
    s_dd = max(0.0, -z_dd) if z_dd is not None else 0.0

    s_of = 0.0
    if vpin_downside is not None:
        try:
            v = float(vpin_downside)
            s_of = max(0.0, (v - 0.5) / 0.5)
        except (TypeError, ValueError):
            s_of = 0.0

    K = (
        w.get("ret", 0.25) * s_ret
        + w.get("vol", 0.20) * s_vol
        + w.get("atr", 0.20) * s_atr
        + w.get("dd", 0.20) * s_dd
        + w.get("of", 0.15) * s_of
    )
    factor, band = knife_factor(K)
    return {
        "K": round(float(K), 4),
        "factor": factor,
        "band": band,
        "severities": {
            "ret": round(s_ret, 4),
            "vol": round(s_vol, 4),
            "atr": round(s_atr, 4),
            "dd": round(s_dd, 4),
            "of": round(s_of, 4),
        },
        "z": {
            "ret": round(z_ret, 4) if z_ret is not None else None,
            "vol": round(z_vol, 4) if z_vol is not None else None,
            "atr": round(z_atr, 4) if z_atr is not None else None,
            "dd": round(z_dd, 4) if z_dd is not None else None,
        },
        "regime": {
            "below_ema": below_ema,
            "ema": round(ema, 4) if ema is not None else None,
            "last_return": round(last_ret, 6) if last_ret is not None else None,
        },
        "weights": {k: round(float(v), 4) for k, v in w.items()},
        "bands": {"reduce": DEFAULT_BANDS[0], "caution": DEFAULT_BANDS[1], "block": DEFAULT_BANDS[2]},
    }


def knife_factor(
    K: float,
    bands: tuple[float, float, float] = DEFAULT_BANDS,
) -> tuple[float, str]:
    """Graduated knife multiplier from the composite score.

    F = 1.0 (K < 1.5) / 0.5 (1.5-2.5) / 0.25 (2.5-3.0) / 0.0 (>= 3.0).
    Returns (factor, band_label). Bands are config defaults, not universal —
    calibrate from your universe / backtests.
    """
    b1, b2, b3 = bands
    if b1 > K:
        return 1.0, "normal"
    if b2 > K:
        return 0.5, "reduce"
    if b3 > K:
        return 0.25, "caution"
    return 0.0, "block"


def guard_band_halfwidth(
    lambda_cost: float,
    sigma_daily: float,
    gamma: float = 1.0,
) -> float | None:
    """Davis-Norman / Shreve-Soner no-trade band half-width.

    ``h = (1.5 * lambda * sigma^2 / gamma)^(1/3)`` — the asymptotic band for
    proportional transaction cost ``lambda``, daily vol ``sigma`` and risk
    aversion ``gamma`` (the material's cube-root formula). Returns None when
    the inputs are degenerate.

    Caution (per the material): this is an asymptotic result under specific
    model assumptions, not a universal production formula — calibrate h from
    your costs and universe.
    """
    if lambda_cost is None or sigma_daily is None or gamma is None:
        return None
    try:
        l_ = float(lambda_cost)
        s_ = float(sigma_daily)
        g_ = float(gamma)
    except (TypeError, ValueError):
        return None
    if l_ <= 0 or s_ <= 0 or g_ <= 0:
        return None
    return (1.5 * l_ * s_ ** 2 / g_) ** (1.0 / 3.0)


def should_trade(weight_drift: float, halfwidth: float | None) -> bool:
    """True when the weight drift clears the no-trade band (trade triggers)."""
    if halfwidth is None:
        return True  # no band computed -> do not suppress (fail-open display)
    return abs(float(weight_drift)) > float(halfwidth)
