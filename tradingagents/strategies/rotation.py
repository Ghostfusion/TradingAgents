"""Cross-sectional trend-quality & rotation calculators (OpenBB Q6-Q8).

Relative Rotation (RRG quadrants), Clenow momentum (trend persistence x
noise) and volatility cones (multi-horizon relative vol). Pure / offline,
``float | None`` on insufficient or degenerate input.
"""

from __future__ import annotations

import math

try:
    import numpy as _np
    from scipy import stats as _st
except Exception:  # noqa: BLE001 - degrade to pure-python fallbacks below
    _np = None
    _st = None


def _clean(series) -> list[float]:
    out = []
    for v in series:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def _z_normalize(series: list[float]) -> list[float] | None:
    vals = _clean(series)
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))
    if sd <= 0:
        return [0.0] * len(vals)
    return [(v - mean) / sd for v in vals]


def relative_rotation(stock: list, benchmark: list, long: int = 252,
                      short: int = 21) -> dict:
    """Relative Rotation Graph (RRG): RS ratio x RS momentum quadrants.

    RS ratio = stock/benchmark relative performance (normalized); RS momentum
    = rate of change of the RS ratio over ``short``. Quadrants:
    leading (++), weakening (+-), lagging (--), improving (-+).
    Returns ``{rs_ratio, rs_momentum, quadrant}`` or all-``None`` when the
    benchmark series is shorter than ``long + short``.
    """
    s = _clean(stock)
    b = _clean(benchmark)
    n = min(len(s), len(b))
    if n < long + short:
        return {"rs_ratio": None, "rs_momentum": None, "quadrant": None}
    s = s[:n]
    b = b[:n]
    rs = [s[i] / b[i] if b[i] > 0 else None for i in range(n)]
    rs = [r for r in rs if r is not None]
    if len(rs) < long + short:
        return {"rs_ratio": None, "rs_momentum": None, "quadrant": None}
    # RS ratio over the long window (latest), normalized z
    long_rs = rs[-long:]
    zr = _z_normalize(long_rs)
    if zr is None:
        return {"rs_ratio": None, "rs_momentum": None, "quadrant": None}
    rs_ratio = zr[-1]
    # momentum = short-window ROC of the ratio, then z-normalize the history
    rocs = [
        (rs[i] / max(rs[i - short], 1e-12) - 1.0)
        for i in range(short, len(rs))
    ]
    zm = _z_normalize(rocs)
    rs_momentum = zm[-1] if zm else 0.0
    if rs_ratio >= 0 and rs_momentum >= 0:
        q = "leading"
    elif rs_ratio >= 0 and rs_momentum < 0:
        q = "weakening"
    elif rs_ratio < 0 and rs_momentum < 0:
        q = "lagging"
    else:
        q = "improving"
    return {"rs_ratio": round(rs_ratio, 4), "rs_momentum": round(rs_momentum, 4),
            "quadrant": q}


def clenow_momentum(closes: list, window: int = 90, periods: float = 252.0) -> float | None:
    """Clenow momentum: exp(OLS log-price slope x periods) x R².

    Penalizes a noisy trend (R²) and rewards persistence. Returns the score
    or None when there are fewer than ``window`` closes or the fit is flat.
    """
    vals = _clean(closes)
    if len(vals) < window:
        return None
    y = vals[-window:]
    logs = [math.log(v) for v in y if v > 0]
    if len(logs) < 3:
        return None
    xs = list(range(1, len(logs) + 1))
    try:
        if _st is not None:
            res = _st.linregress(xs, logs)
            slope = float(res.slope)
            r2 = float(res.rvalue ** 2)
        else:
            n = len(logs)
            mx = sum(xs) / n
            my = sum(logs) / n
            num = sum((x - mx) * (y - my) for x, y in zip(xs, logs, strict=True))
            den = sum((x - mx) ** 2 for x in xs)
            slope = num / den if den > 0 else 0.0
            r2 = 1.0
        if not math.isfinite(slope) or not math.isfinite(r2):
            return None
        return math.exp(slope * float(periods)) * r2
    except Exception:  # noqa: BLE001
        return None


def vol_cones(closes: list, windows: tuple = (5, 10, 21, 63, 126)) -> dict:
    """Realized-volatility cones: current vs percentile bands per horizon.

    Returns ``{win: {current, p25, p50, p75}}`` (annualized) for each window
    that has enough data; a short series yields fewer windows. Empty when no
    window is computable.
    """
    vals = _clean(closes)
    out = {}
    if len(vals) < 3:
        return out
    rets = [vals[i] / vals[i - 1] - 1.0 for i in range(1, len(vals)) if vals[i - 1] > 0]
    if len(rets) < 3:
        return out
    for w in windows:
        w = int(w)
        if len(rets) < w:
            continue
        chunks = [rets[i - w:i] for i in range(w, len(rets) + 1)]
        vols = []
        for c in chunks:
            m = sum(c) / len(c)
            var = sum((v - m) ** 2 for v in c) / (len(c) - 1)
            vols.append(math.sqrt(var * 252.0))
        vols.sort()
        n = len(vols)
        idx = {25: min(n - 1, int(0.25 * n)), 50: min(n - 1, int(0.50 * n)),
               75: min(n - 1, int(0.75 * n))}
        out[w] = {
            "current": round(vols[-1], 4),
            "p25": round(vols[idx[25]], 4),
            "p50": round(vols[idx[50]], 4),
            "p75": round(vols[idx[75]], 4),
        }
    return out


__all__ = ["relative_rotation", "clenow_momentum", "vol_cones"]
