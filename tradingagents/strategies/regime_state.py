"""Multi-axis regime state (regime-gate material).

Four independent, crisp state dimensions instead of one label — the
material's recommended architecture — each a pure read over price history:

* ``trend``    - TrendScore = (EMA20 - EMA50) / ATR14 → STRONG_BULL / BULL /
                 BEAR / STRONG_BEAR
* ``volatility`` - VolRatio = ATR14 / Median(ATR14, N) → LOW / NORMAL / HIGH /
                 EXTREME
* ``relative`` - R_stock - R_benchmark (vs a supplied benchmark/SPY series) →
                 UNDERPERFORM / NEUTRAL / OUTPERFORM
* ``drawdown`` - P / RollingHigh_N - 1 → NORMAL / CORRECTION / BEAR / SEVERE

``regime_state()`` aggregates them (multiple dimensions at once — never forced
into one label) and derives a graduated ``factor`` (F_regime) that scales
position size: Bull/Normal = 1.0, Bear/Normal = 0.5, Bear+High-Vol = 0.25,
Crash = 0.0. The factor composes multiplicatively with the knife guard.
All thresholds are config defaults, NOT universal constants (calibrate from
your universe / backtests); advisory — enforcement is opt-in at the caller.
"""

from __future__ import annotations

from typing import Any

TREND_STRONG = 1.0  # |TrendScore| above this = strong trend
VOL_RATIO_LOW = 0.7
VOL_RATIO_HIGH = 1.3
VOL_RATIO_EXTREME = 2.0
DD_CORRECTION = -0.05
DD_BEAR = -0.15
DD_SEVERE = -0.25
REL_WEAK = -0.005  # R_stock - R_bench below this = underperform


def _ema_series(values: list[float], window: int) -> list[float]:
    if len(values) < window or window <= 0:
        return []
    k = 2.0 / (window + 1.0)
    ema = [sum(values[:window]) / window]
    for v in values[window:]:
        ema.append(v * k + ema[-1] * (1.0 - k))
    return ema


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _atr14(highs: list[float], lows: list[float], closes: list[float]) -> float | None:
    if not highs or not lows or not closes or len(closes) < 16:
        return None
    trs = []
    for i in range(1, len(closes)):
        h, ll, pc = highs[i], lows[i], closes[i - 1]
        trs.append(max(h - ll, abs(h - pc), abs(ll - pc)))
    return sum(trs[-14:]) / 14.0


def regime_trend(closes: list[float], atr_value: float | None = None, strong: float = TREND_STRONG) -> dict:
    """TrendScore = (EMA20 - EMA50) / ATR14; -> STRONG_BULL/BULL/BEAR/STRONG_BEAR."""
    if not closes or len(closes) < 60:
        return {"score": None, "label": "UNKNOWN", "strong_threshold": strong}
    e20 = _ema_series(list(closes), 20)
    e50 = _ema_series(list(closes), 50)
    if not e20 or not e50:
        return {"score": None, "label": "UNKNOWN", "strong_threshold": strong}
    a = atr_value if atr_value is not None and atr_value > 0 else None
    if a is None:
        highs = [c * 1.01 for c in closes]
        lows = [c * 0.99 for c in closes]
        a = _atr14(highs, lows, list(closes))
    if not a or a <= 0:
        return {"score": None, "label": "UNKNOWN", "strong_threshold": strong}
    score = (e20[-1] - e50[-1]) / a
    if score > strong:
        label = "STRONG_BULL"
    elif score > 0:
        label = "BULL"
    elif score > -strong:
        label = "BEAR"
    else:
        label = "STRONG_BEAR"
    return {"score": round(float(score), 4), "label": label, "strong_threshold": strong}


def regime_vol_ratio(
    high: list[float], low: list[float], close: list[float],
    window: int = 20, low_thr: float = VOL_RATIO_LOW, high_thr: float = VOL_RATIO_HIGH,
    extreme_thr: float = VOL_RATIO_EXTREME,
) -> dict:
    """VolRatio = ATR14 / Median(ATR14, N) -> LOW/NORMAL/HIGH/EXTREME."""
    if not high or not low or not close or len(close) < max(window + 14, 34):
        return {"ratio": None, "label": "UNKNOWN", "thresholds": [low_thr, high_thr, extreme_thr]}
    atrs = []
    for i in range(len(close) - 1, 1, -1):
        # _atr14 needs >= 16 bars: include 15 prior bars + the current one
        start = max(0, i - 15)
        seg_h, seg_l, seg_c = high[start : i + 1], low[start : i + 1], close[start : i + 1]
        a = _atr14(seg_h, seg_l, seg_c)
        if a is not None:
            atrs.append(a)
        if len(atrs) >= window:
            break
    if not atrs:
        return {"ratio": None, "label": "UNKNOWN", "thresholds": [low_thr, high_thr, extreme_thr]}
    med = _median(atrs)
    if not med or med <= 0:
        return {"ratio": None, "label": "UNKNOWN", "thresholds": [low_thr, high_thr, extreme_thr]}
    ratio = atrs[0] / med
    if ratio < low_thr:
        label = "LOW"
    elif ratio <= high_thr:
        label = "NORMAL"
    elif ratio <= extreme_thr:
        label = "HIGH"
    else:
        label = "EXTREME"
    return {"ratio": round(float(ratio), 4), "label": label, "thresholds": [low_thr, high_thr, extreme_thr]}


def regime_relative(stock: list[float], benchmark: list[float] | None, weak: float = REL_WEAK) -> dict:
    """Relative strength = R_stock - R_benchmark (e.g. vs SPY) -> UNDERPERFORM/NEUTRAL/OUTPERFORM."""
    if not stock or len(stock) < 2:
        return {"relative_ret": None, "label": "UNKNOWN", "weak_threshold": weak}
    r_stock = stock[-1] / stock[-2] - 1.0
    if not benchmark or len(benchmark) < 2:
        # no benchmark -> neutral (cannot judge)
        return {"relative_ret": None, "label": "NEUTRAL", "weak_threshold": weak}
    r_bench = benchmark[-1] / benchmark[-2] - 1.0
    rel = r_stock - r_bench
    if rel < weak:
        label = "UNDERPERFORM"
    elif rel > -weak:
        label = "OUTPERFORM"
    else:
        label = "NEUTRAL"
    return {"relative_ret": round(float(rel), 4), "label": label, "weak_threshold": weak}


def regime_drawdown(closes: list[float], window: int = 252) -> dict:
    """DD = P / RollingHigh_N - 1 -> NORMAL/CORRECTION/BEAR/SEVERE."""
    if not closes:
        return {"drawdown": None, "label": "UNKNOWN", "thresholds": [DD_CORRECTION, DD_BEAR, DD_SEVERE]}
    roll = closes[-window:] if len(closes) > window else closes
    high = max(roll)
    if high <= 0:
        return {"drawdown": None, "label": "UNKNOWN", "thresholds": [DD_CORRECTION, DD_BEAR, DD_SEVERE]}
    dd = closes[-1] / high - 1.0
    if dd > DD_CORRECTION:
        label = "NORMAL"
    elif dd > DD_BEAR:
        label = "CORRECTION"
    elif dd > DD_SEVERE:
        label = "BEAR"
    else:
        label = "SEVERE"
    return {"drawdown": round(float(dd), 4), "label": label, "thresholds": [DD_CORRECTION, DD_BEAR, DD_SEVERE]}


def regime_factor(
    trend: str,
    volatility: str,
    drawdown: str = "NORMAL",
) -> float:
    """Graduated F_regime for position sizing (Bull/Normal=1.0, Bear/High=0.25, Crash=0.0).

    Conservative composition: the worst of (trend, volatility, drawdown) wins.
    """
    if "CRASH" in drawdown.upper() or volatility == "EXTREME":
        return 0.0
    scores = {"STRONG_BULL": 1.0, "BULL": 1.0, "BEAR": 0.5, "STRONG_BEAR": 0.25}
    trend_s = scores.get(trend.upper(), 1.0)
    vol_s = {"LOW": 1.0, "NORMAL": 1.0, "HIGH": 0.5, "EXTREME": 0.0}.get(volatility.upper(), 1.0)
    dd_s = {"NORMAL": 1.0, "CORRECTION": 0.75, "BEAR": 0.5, "SEVERE": 0.0}.get(drawdown.upper(), 1.0)
    return min(trend_s, vol_s, dd_s)


def regime_state(
    closes: list[float],
    high: list[float] | None = None,
    low: list[float] | None = None,
    benchmark: list[float] | None = None,
    atr_value: float | None = None,
) -> dict[str, Any]:
    """Aggregate the four regime dimensions + the combined F_regime factor.

    Returns a dict: ``{trend, volatility, relative, drawdown, factor,
    labels, crash}``. Missing inputs degrade each dimension to UNKNOWN (never
    fabricate); the factor defaults to 1.0 on unknowns (advisory display).
    """
    trend = regime_trend(closes, atr_value)
    vol = regime_vol_ratio(high, low, closes) if (high and low) else {"ratio": None, "label": "UNKNOWN", "thresholds": [VOL_RATIO_LOW, VOL_RATIO_HIGH, VOL_RATIO_EXTREME]}
    rel = regime_relative(closes, benchmark)
    dd = regime_drawdown(closes)
    labels = {"trend": trend["label"], "volatility": vol["label"], "relative": rel["label"], "drawdown": dd["label"]}
    crash = bool(vol.get("label") == "EXTREME" or dd.get("label") == "SEVERE")
    factor = regime_factor(trend["label"], vol["label"], dd["label"])
    return {
        "trend": trend,
        "volatility": vol,
        "relative": rel,
        "drawdown": dd,
        "labels": labels,
        "crash": crash,
        "factor": factor,
    }
