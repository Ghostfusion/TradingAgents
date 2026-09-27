"""Additional technical factors for the value-dip + swing combo (pure, offline).

Complements the existing RSI / Bollinger / ATR / MACD / RVOL with the
volume-price and trend-strength oscillators commonly used to confirm a dip
buy and its swing exit:

  KST        - Know-Sure-Thing multi-ROC momentum oscillator
  MFI        - Money Flow Index (volume-weighted RSI over typical price)
  Stochastic - %K/%D oversold oscillator (slow via sma3)
  ADX / DI   - Wilder Average Directional Index trend-strength filter
  Chandelier - trailing stop = highest high - k x ATR (in swing.py instead)

The depth reads at the end of the module (library §7/§8/§21-§25/§28-§30/
§43-§48/§58/§59/§80/§91/§101-§104) expose the level / slope / ratio form of
series the indicators above already build: the OBV level and slope, the
range position inside the Donchian channel, the SMA20/SMA100 legs, the MACD
line/signal/histogram with their one-bar changes, the Bollinger-bandwidth
family, a per-series mean-reversion z, the volume spike/trend/breakout
confirmation and the ATR ratio/movement/acceleration.

Every function is pure and returns None on missing/invalid input (the
no-fabrication rule). No network, no state.
"""

from __future__ import annotations

import math

import numpy as np


def _sma(series: list, n: int) -> list:
    """SMA series; None for the first n-1 positions."""
    out = [None] * (n - 1)
    for i in range(n - 1, len(series)):
        out.append(sum(series[i - n + 1 : i + 1]) / n)
    return out


def ema(series: list, n: int) -> list:
    """EMA series (SMA-seeded); None for the first n-1 positions.

    The single EMA implementation in the package: ``extended_indicators`` and
    ``value_dip`` import this function rather than re-defining it, so a change
    to the EMA convention can never diverge between them.
    """
    if not series or n <= 0:
        return [None] * len(series)
    k = 2.0 / (n + 1)
    out = [None] * (n - 1)
    ema_value = sum(series[:n]) / n
    out.append(ema_value)
    for v in series[n:]:
        ema_value = float(v) * k + ema_value * (1 - k)
        out.append(ema_value)
    return out


def _roc(value: float | None, prev: float | None) -> float | None:
    if value is None or prev is None or prev == 0:
        return None
    return float(value) / float(prev) - 1.0


def _ols_slope(values: list) -> float | None:
    """Least-squares slope per step of ``values`` (x = 0..n-1).

    The library's ``Slope(series, n)``. None with fewer than two usable
    observations. Used on series whose mean is not a usable denominator (OBV
    crosses zero), so the mean-normalised ``relative_strength.slope_pct``
    convention is not applicable.
    """
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if n < 2:
        return None
    xbar = (n - 1) / 2.0
    ybar = sum(vals) / n
    sxx = sum((i - xbar) ** 2 for i in range(n))
    if sxx <= 0:
        return None
    return sum((i - xbar) * (v - ybar) for i, v in enumerate(vals)) / sxx


def _pct_rank(window: list, value: float) -> float | None:
    """Share of ``window`` at or below ``value`` (the empirical rank used by
    ``compression.atr_compression_read``: the window minimum reads
    ``1/len(window)``, not 0). None on an empty window."""
    vals = [float(v) for v in window if v is not None]
    if not vals:
        return None
    return sum(1 for v in vals if v <= value) / len(vals)


def _p95(values: list) -> float | None:
    """Nearest-rank 95th percentile of ``values`` (library §58's denominator)."""
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return None
    idx = min(len(vals) - 1, max(0, math.ceil(0.95 * len(vals)) - 1))
    return vals[idx]


def kst(
    closes: list,
    roc1: int = 10,
    roc2: int = 15,
    roc3: int = 20,
    roc4: int = 30,
    sma1: int = 10,
    sma2: int = 10,
    sma3: int = 10,
    sma4: int = 15,
    sig: int = 9,
) -> dict:
    """Know Sure Thing: weighted sum of four smoothed ROC series.

    KST = (RCMA1*1)+(RCMA2*2)+(RCMA3*3)+(RCMA4*4); trigger = SMA(KST,9).
    Returns the current KST + trigger + a bullish crossover flag, or None
    when insufficient history.
    """
    if not closes or len(closes) < roc4 + max(sma1, sig) + 5:
        return {"kst": None, "trigger": None, "crossover": None, "kst_up": None}
    rc1 = [_roc(c, prev) for c, prev in zip(closes[roc1:], closes[:-roc1], strict=False)]
    rc2 = [_roc(c, prev) for c, prev in zip(closes[roc2:], closes[:-roc2], strict=False)]
    rc3 = [_roc(c, prev) for c, prev in zip(closes[roc3:], closes[:-roc3], strict=False)]
    rc4 = [_roc(c, prev) for c, prev in zip(closes[roc4:], closes[:-roc4], strict=False)]
    # Align to the shortest (rc4)
    n = len(rc4)
    rc1, rc2, rc3 = rc1[-n:], rc2[-n:], rc3[-n:]
    m1 = _sma(rc1, sma1)
    m2 = _sma(rc2, sma2)
    m3 = _sma(rc3, sma3)
    m4 = _sma(rc4, sma4)
    kst_series = [
        (a * 1.0 + b * 2.0 + c * 3.0 + d * 4.0)
        if (a is not None and b is not None and c is not None and d is not None)
        else None
        for a, b, c, d in zip(m1, m2, m3, m4, strict=False)
    ]
    valid = [x for x in kst_series if x is not None]
    if len(valid) < sig + 2:
        return {"kst": None, "trigger": None, "crossover": None, "kst_up": None}
    # Cut leading Nones (ROC warm-up) so the SMA window sees a contiguous series.
    start = next((i for i, x in enumerate(kst_series) if x is not None), 0)
    kst_trim = kst_series[start:]
    trig = _sma(kst_trim, sig)
    cur = kst_trim[-1]
    trig_cur = trig[-1]
    prev = kst_trim[-2]
    trig_prev = trig[-2]
    return {
        "kst": round(cur, 6) if cur is not None else None,
        "trigger": round(trig_cur, 6) if trig_cur is not None else None,
        "crossover": bool(
            cur is not None and trig_cur is not None and prev is not None
            and trig_prev is not None and cur > trig_cur and prev <= trig_prev
        ),
        "kst_up": bool(cur is not None and trig_cur is not None and cur >= trig_cur),
    }


def mf_index(highs, lows, closes, volumes, n: int = 14) -> float | None:
    """Money Flow Index: sum(positive MF) / (pos+neg) over ``n`` days.

    volume x typical price flow. MFI > 80 overbought, MFI < 20 oversold.
    None when history insufficient or any side missing.
    """
    if len(highs) < n or len(lows) < n or len(closes) < n or len(volumes) < n:
        return None
    def _tp(i):
        try:
            return (float(highs[i]) + float(lows[i]) + float(closes[i])) / 3.0
        except (TypeError, ValueError):
            return None

    pos = 0.0
    neg = 0.0
    for i in range(len(highs) - n, len(highs)):
        tp = _tp(i)
        tp_prev = _tp(i - 1)
        if tp is None or tp_prev is None:
            continue
        vol = float(volumes[i])
        mf = tp * vol
        if tp > tp_prev:
            pos += mf
        elif tp < tp_prev:
            neg += mf
    if pos + neg == 0:
        return 50.0
    if neg == 0:
        return 100.0
    return round(100.0 - 100.0 / (1.0 + pos / neg), 2)


def stochastic_oscillator(
    highs, lows, closes, k_window: int = 14, d_window: int = 3
) -> dict:
    """Stochastic %K/%D. %%K = (C - LL) / (HH - LL) x 100 with a slow SMA3
    %%D. Returns {'k','d','oversold','overbought','golden_cross'} or None
    values when insufficient history."""
    if len(highs) < k_window or len(lows) < k_window or len(closes) < k_window:
        return {"k": None, "d": None, "oversold": None, "overbought": None, "golden_cross": None}
    ks = []
    for i in range(k_window - 1, len(closes)):
        hh = max(highs[i - k_window + 1 : i + 1])
        ll = min(lows[i - k_window + 1 : i + 1])
        if hh == ll:
            ks.append(50.0)
        else:
            ks.append((float(closes[i]) - ll) / (hh - ll) * 100.0)
    ds = _sma(ks, d_window)
    k = ks[-1]
    d = ds[-1]
    return {
        "k": round(k, 2) if k is not None else None,
        "d": round(d, 2) if d is not None else None,
        "oversold": bool(k is not None and k < 20.0),
        "overbought": bool(k is not None and k > 80.0),
        "golden_cross": bool(
            len(ks) >= 2 and len(ds) >= 2
            and ks[-2] is not None and ds[-2] is not None
            and k is not None and d is not None
            and ks[-2] <= ds[-2] and k > d
        ),
    }


def adx(highs, lows, closes, n: int = 14) -> dict:
    """Wilder Average Directional Index + DI+/DI-.

    ADX measures trend strength (25 = strong). None when history insufficient.
    """
    if len(highs) < n + 1 or len(lows) < n + 1 or len(closes) < n + 1:
        return {"adx": None, "di_plus": None, "di_minus": None, "strong": None}
    trs = []
    pds = []
    mds = []
    for i in range(1, len(highs)):
        h, low_, pc = float(highs[i]), float(lows[i]), float(closes[i - 1])
        tr = max(h - low_, abs(h - pc), abs(low_ - pc))
        pd = h - float(highs[i - 1])
        md = float(lows[i - 1]) - low_
        pd = pd if (pd > 0 and pd > md) else 0.0
        md = md if (md > 0 and md > pd) else 0.0
        trs.append(tr)
        pds.append(pd)
        mds.append(md)
    def _wild(arr, n):
        # simple first window then Wilder smoothing
        out = [None] * (n - 1)
        first = sum(arr[:n]) / n
        out.append(first)
        for i in range(n, len(arr)):
            out.append((out[-1] * (n - 1) + arr[i]) / n)
        return out
    tr_s = _wild(trs, n)
    pd_s = _wild(pds, n)
    md_s = _wild(mds, n)
    di_p = di_m = None
    adx_series = []
    for i in range(len(tr_s)):
        tr, pd, md = tr_s[i], pd_s[i], md_s[i]
        if tr is not None and pd is not None and md is not None and tr > 0:
            dp = 100.0 * pd / tr
            dm = 100.0 * md / tr
            adx_series.append(abs(dp - dm) / (dp + dm) * 100.0 if (dp + dm) > 0 else 0.0)
        else:
            adx_series.append(None)
    valid_adx = [x for x in adx_series if x is not None]
    adx_val = None
    if len(valid_adx) >= n:
        # smooth the DX series (trim leading Nones for a contiguous SMA)
        start = next((i for i, x in enumerate(adx_series) if x is not None), 0)
        dx_s = _sma(adx_series[start:], n)
        adx_val = dx_s[-1] if dx_s and dx_s[-1] is not None else None
    # latest DI
    if tr_s and tr_s[-1] is not None and tr_s[-1] > 0:
        di_p = 100.0 * (pd_s[-1] / tr_s[-1]) if pd_s[-1] is not None else None
        di_m = 100.0 * (md_s[-1] / tr_s[-1]) if md_s[-1] is not None else None
    return {
        "adx": round(adx_val, 2) if adx_val is not None else None,
        "di_plus": round(di_p, 2) if di_p is not None else None,
        "di_minus": round(di_m, 2) if di_m is not None else None,
        "strong": bool(adx_val is not None and adx_val > 25.0),
    }


def pivot_points(
    high: float | None, low: float | None, close: float | None
) -> dict:
    """Classic daily/weekly pivot + support/resistance levels, R1-S3.

    The full Floor-Trader set (P, R1/R2/R3, S1/S2/S3), so the name matches
    what comes back. None fields when any input is missing.
    """
    if high is None or low is None or close is None:
        return {"p": None, "r1": None, "s1": None, "r2": None, "s2": None,
                "r3": None, "s3": None}
    try:
        h, low_, c = float(high), float(low), float(close)
    except (TypeError, ValueError):
        return {"p": None, "r1": None, "s1": None, "r2": None, "s2": None,
                "r3": None, "s3": None}
    p = (h + low_ + c) / 3.0
    return {
        "p": round(p, 4),
        "r1": round(2 * p - low_, 4),
        "s1": round(2 * p - h, 4),
        "r2": round(p + (h - low_), 4),
        "s2": round(p - (h - low_), 4),
        "r3": round(h + 2 * (p - low_), 4),
        "s3": round(low_ - 2 * (h - p), 4),
    }


def pivot_distance_atr(close: float | None, pivot: float | None,
                       atr_value: float | None) -> float | None:
    """Distance from close to a pivot level, in ATRs (stationary).

    A raw dollar distance to a pivot is not comparable across names or price
    levels: 5 points is noise in one instrument and a full stop in another.
    Dividing by ATR makes it stationary, which is the form a threshold or a
    model input can use. None when any input is missing or ATR is not positive
    - never 0.0, which would read as "price is exactly at the pivot".
    """
    try:
        if close is None or pivot is None or atr_value is None:
            return None
        atr_f = float(atr_value)
        if atr_f <= 0:
            return None
        return round((float(close) - float(pivot)) / atr_f, 4)
    except (TypeError, ValueError):
        return None


__all__ = [
    "ema",
    "kst",
    "mf_index",
    "stochastic_oscillator",
    "adx",
    "pivot_distance_atr",
    "pivot_points",
    "stoch_rsi",
    "rsi2",
    "williams_r",
    "keltner_channel",
    "donchian_channel",
    "range_position",
    "obv_divergence",
    "sma_legs",
    "macd_depth",
    "bollinger_bandwidth",
    "mean_reversion_z",
    "volume_depth",
    "atr_depth",
    "parabolic_sar",
    "elder_thermometer",
    "aroon",
    "fisher_transform",
    "chaikin_oscillator",
    "elder_ray",
    "supertrend",
    "volume_profile",
    "spectral_excess_mass",
    "cost_optimal_span",
]


def stoch_rsi(closes: list, n: int = 14) -> dict:
    """StochRSI = (RSI - min RSI) / (max RSI - min RSI) over the window.

    Smoother, more sensitive oversold read than plain RSI: StochRSI < 0.2
    oversold, > 0.8 overbought. None when history insufficient. Uses the
    Wilder RSI series (swing.rsi with RMA smoothing) and the standard
    n=14 min/max window (the old per-window simple-sum RSI was Cutler's).
    """
    from tradingagents.strategies.swing import rsi as _rsi_wilder

    if len(closes) < 3 * n + 1:
        return {"stochrsi": None, "oversold": None, "overbought": None}
    rsi_valid = []
    for i in range(3 * n, len(closes)):
        r = _rsi_wilder(closes[: i + 1], n)
        if r is not None:
            rsi_valid.append(r)
    if len(rsi_valid) < n:
        return {"stochrsi": None, "oversold": None, "overbought": None}
    window = rsi_valid[-n:]
    mn, mx = min(window), max(window)
    if mx == mn:
        return {"stochrsi": 0.5, "oversold": False, "overbought": False}
    cur = rsi_valid[-1]
    v = (cur - mn) / (mx - mn)
    return {
        "stochrsi": round(v, 4),
        "oversold": bool(v < 0.2),
        "overbought": bool(v > 0.8),
    }


def rsi2(closes: list, n: int = 2) -> float | None:
    """2-period RSI - a fast mean-reversion oversold/overbought read.

    RSI2 < ~10 is an extreme contrarian buy signal (Connors style).
    """
    if len(closes) < n + 1:
        return None
    seg = closes[-(n + 1) :]
    gains = losses = 0.0
    for j in range(1, len(seg)):
        d = seg[j] - seg[j - 1]
        if d >= 0:
            gains += d
        else:
            losses -= d
    if gains + losses == 0:
        return 50.0
    if losses == 0:
        return 100.0
    rs = gains / losses
    return round(100.0 - 100.0 / (1.0 + rs), 2)


def williams_r(highs, lows, closes, n: int = 14) -> float | None:
    """Williams %R = (HHn - Close) / (HHn - LLn) x -100. -80..-100 oversold."""
    if len(highs) < n or len(lows) < n or len(closes) < n:
        return None
    hh = max(float(x) for x in highs[-n:])
    ll = min(float(x) for x in lows[-n:])
    if hh == ll:
        return -50.0
    return round((hh - float(closes[-1])) / (hh - ll) * -100.0, 2)


def keltner_channel(closes, atr_value=None, n: int = 20, k: float = 2.0) -> dict:
    """Keltner Channel: EMA(20) +/- k x ATR. Returns mid/upper/lower + price %b
    within the channel (mean-reversion). None when history insufficient."""
    if not closes or len(closes) < n or atr_value is None or atr_value <= 0:
        return {"mid": None, "upper": None, "lower": None, "pct": None}
    # Keltner uses an EMA midpoint (the old code used an SMA, which shifted the
    # channel mid in trending series). EMA = prev_ema*(1-a) + price*a, a=2/(n+1),
    # seeded on the SMA of the first n observations.
    prices = [float(x) for x in closes]
    seed = sum(prices[:n]) / n
    alpha = 2.0 / (n + 1)
    ema = seed
    for p in prices[n:]:
        ema = ema + alpha * (p - ema)
    mid = ema
    upper = mid + float(k) * float(atr_value)
    lower = mid - float(k) * float(atr_value)
    if upper == lower:
        return {"mid": round(mid, 4), "upper": round(upper, 4), "lower": round(lower, 4), "pct": 0.5}
    pct = (float(closes[-1]) - lower) / (upper - lower)
    return {
        "mid": round(mid, 4),
        "upper": round(upper, 4),
        "lower": round(lower, 4),
        "pct": round(pct, 4),
    }


def donchian_channel(highs, lows, n: int = 20, closes=None) -> dict:
    """Donchian Channel: N-day highest high / lowest low + breakout signal.

    ``upper`` / ``lower`` / ``mid`` are the N-bar range *including* the latest
    bar (a level read). The breakout flags compare the latest **close** against
    the channel formed by the **prior** N bars - the standard definition, and
    the only one that can ever be true, since a close cannot exceed the high of
    the bar it belongs to. ``breakout_ref_up`` / ``breakout_ref_dn`` are those
    prior-window levels, so the flag is checkable against the printed numbers.

    Depth of the same read (library §43/§44): ``persistence_up`` /
    ``persistence_dn`` are the share of the last ``n`` closes that stayed
    beyond ``breakout_ref_up`` / ``breakout_ref_dn`` (0..1, the observation
    window so far), and ``false_breakout_up`` / ``false_breakout_dn`` flag a
    close that had cleared the reference level earlier in the window but is
    back inside it on the latest bar - a failed breakout, not a breakout.

    ``closes`` is optional: without it the flags and the persistence reads stay
    ``None`` (the levels are still returned) and ``breakout_reason`` says why.
    ``reason`` is a string only when the levels themselves cannot be measured.
    Every in-repo caller passes ``closes``.
    """
    if len(highs) < n or len(lows) < n:
        return {
            "upper": None, "lower": None, "mid": None,
            "breakout_up": None, "breakout_dn": None,
            "breakout_ref_up": None, "breakout_ref_dn": None,
            "persistence_up": None, "persistence_dn": None,
            "false_breakout_up": None, "false_breakout_dn": None,
            "reason": f"fewer than {n} highs/lows: channel unmeasured",
            "breakout_reason": f"fewer than {n} highs/lows: no reference level",
        }
    up = max(float(x) for x in highs[-n:])
    lo = min(float(x) for x in lows[-n:])
    mid = (up + lo) / 2.0
    breakout_up = breakout_dn = ref_up = ref_dn = None
    persistence_up = persistence_dn = None
    false_up = false_dn = None
    breakout_reason = "no closes supplied: breakout state unmeasured"
    if closes is not None and len(closes):
        if len(highs) >= n + 1 and len(lows) >= n + 1:
            ref_up = max(float(x) for x in highs[-n - 1:-1])
            ref_dn = min(float(x) for x in lows[-n - 1:-1])
            last = float(closes[-1])
            breakout_up = bool(last > ref_up)
            breakout_dn = bool(last < ref_dn)
            tail = [float(x) for x in closes[-n:]]
            persistence_up = sum(1 for x in tail if x > ref_up) / len(tail)
            persistence_dn = sum(1 for x in tail if x < ref_dn) / len(tail)
            prior = tail[:-1]
            false_up = bool(last < ref_up and any(x > ref_up for x in prior))
            false_dn = bool(last > ref_dn and any(x < ref_dn for x in prior))
            breakout_reason = None
        else:
            breakout_reason = (
                f"fewer than {n + 1} highs/lows: no prior-window reference level"
            )
    return {
        "upper": round(up, 4),
        "lower": round(lo, 4),
        "mid": round(mid, 4),
        "breakout_up": breakout_up,
        "breakout_dn": breakout_dn,
        "breakout_ref_up": round(ref_up, 4) if ref_up is not None else None,
        "breakout_ref_dn": round(ref_dn, 4) if ref_dn is not None else None,
        "persistence_up": round(persistence_up, 4) if persistence_up is not None else None,
        "persistence_dn": round(persistence_dn, 4) if persistence_dn is not None else None,
        "false_breakout_up": false_up,
        "false_breakout_dn": false_dn,
        "reason": None,
        "breakout_reason": breakout_reason,
    }


def obv_divergence(closes, volumes, window: int = 30) -> dict:
    """On-Balance-Volume vs price: cumulative OBV trend vs price trend.

    ``obv`` is the last cumulative OBV **level** the trend read is built on
    (library §47) and ``obv_slope`` its least-squares slope per bar over the
    last ``window`` values (§48 ``Slope(OBV,n)``), with ``obv_slope_norm``
    that slope divided by the mean volume over the same window (§48's
    normalisation). ``obv_up`` / ``bullish_div`` are the original bools for a
    price lower-low with a higher OBV low (bullish divergence) - a
    dip-reversal confirmation.

    ``reason`` is a string when fewer than ``window`` closes/volumes were
    supplied; the level and slope are never fabricated.
    """
    if len(closes) < window or len(volumes) < window:
        return {
            "obv": None, "obv_slope": None, "obv_slope_norm": None,
            "obv_up": None, "bullish_div": None,
            "reason": f"fewer than {window} closes/volumes: OBV unmeasured",
        }
    obv = 0.0
    obv_series = []
    prev_c = None
    for c, v in zip(closes, volumes, strict=False):
        if prev_c is not None and v is not None:
            if float(c) > float(prev_c):
                obv += float(v)
            elif float(c) < float(prev_c):
                obv -= float(v)
        obv_series.append(obv)
        prev_c = float(c)
    seg = obv_series[-2 * window :] if len(obv_series) >= 2 * window else obv_series
    half = len(seg) // 2
    first_obv, second_obv = seg[:half], seg[half:]
    # Mirror the price slice off the SAME tail `seg` was cut from, so the first
    # half's price aligns with the first half's OBV (previously the offset
    # slice came out empty for equal halves, dead-coding bullish_div).
    seg_closes = closes[-len(seg) :] if len(seg) else []
    first_price, second_price = seg_closes[:half], seg_closes[half:]
    price_dn = bool(
        len(second_price) and len(first_price) and second_price[-1] < first_price[-1]
    )
    obv_up = bool(
        len(second_obv) and len(first_obv) and second_obv[-1] > first_obv[-1]
    )
    obv_slope = _ols_slope(obv_series[-window:])
    vols_tail = [float(v) for v in volumes[-window:] if v is not None]
    avg_vol = sum(vols_tail) / len(vols_tail) if vols_tail else None
    obv_slope_norm = (
        obv_slope / avg_vol if (obv_slope is not None and avg_vol) else None
    )
    return {
        "obv": round(obv_series[-1], 4) if obv_series else None,
        "obv_slope": round(obv_slope, 4) if obv_slope is not None else None,
        "obv_slope_norm": (
            round(obv_slope_norm, 6) if obv_slope_norm is not None else None
        ),
        "obv_up": obv_up,
        "bullish_div": bool(price_dn and obv_up),
        "reason": None,
    }


def parabolic_sar(highs, lows, af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.2, closes=None) -> dict:
    """Parabolic SAR trailing stop (Wilder). Returns current SAR + a below/exit
    flag (close below SAR = downtrend). None when history insufficient.

    ``closes`` is optional; ``below``/``exit`` are only computed when it is
    provided (the function cannot know the close from highs/lows alone).
    """
    if len(highs) < 2 or len(lows) < 2:
        return {"sar": None, "below": None, "exit": None}
    try:
        af = float(af_start)
        trend = 1  # up
        sar = float(lows[0])
        ep = float(highs[0])
        for i in range(1, len(highs)):
            sar = sar + af * (ep - sar)
            hi = float(highs[i])
            lo = float(lows[i])
            if trend == 1:
                if lo < sar:
                    trend = -1
                    sar = ep
                    ep = lo
                    af = float(af_start)
                else:
                    if hi > ep:
                        ep = hi
                        af = min(af + float(af_step), float(af_max))
            else:
                if hi > sar:
                    trend = 1
                    sar = ep
                    ep = hi
                    af = float(af_start)
                else:
                    if lo < ep:
                        ep = lo
                        af = min(af + float(af_step), float(af_max))
        below = bool(float(closes[-1]) < sar) if closes is not None and len(closes) else None
        return {"sar": round(sar, 4), "below": below, "exit": below}
    except (TypeError, ValueError, ZeroDivisionError):
        return {"sar": None, "below": None, "exit": None}


def elder_thermometer(volumes, n: int = 21) -> dict:
    """Elder's thermometer = current volume / (21-day average volume).

    A ratio > 1.0 = heavy participation, < 1.0 = low participation (a calm
    dip in a quiet tape). None when history insufficient.
    """
    if len(volumes) < n:
        return {"ratio": None, "heavy": None, "quiet": None}
    avg = sum(float(x) for x in volumes[-n:]) / n
    if avg <= 0:
        return {"ratio": None, "heavy": None, "quiet": None}
    ratio = float(volumes[-1]) / avg
    return {
        "ratio": round(ratio, 4),
        "heavy": bool(ratio > 1.0),
        "quiet": bool(ratio < 0.8),
    }


def aroon(highs, lows, n: int = 25) -> dict:
    """Aroon trend-age oscillator: how long since the N-period high/low.

    AroonUp = (N - bars since highest high) / N x 100; AroonDown mirrors the
    lowest low. Up > 70 with Down < 30 = strong uptrend; a crossover of the
    two signals a trend change. None when history insufficient.
    """
    if len(highs) < n + 1 or len(lows) < n + 1:
        return {"aroon_up": None, "aroon_down": None, "verdict": None}
    seg_h = [float(x) for x in highs[-(n + 1) :]]
    seg_l = [float(x) for x in lows[-(n + 1) :]]
    hh = max(seg_h)
    ll = min(seg_l)
    bars_since_high = (len(seg_h) - 1) - seg_h.index(hh)
    bars_since_low = (len(seg_l) - 1) - seg_l.index(ll)
    up = (n - bars_since_high) / n * 100.0
    down = (n - bars_since_low) / n * 100.0
    if up > 70 and down < 30:
        verdict = "uptrend"
    elif down > 70 and up < 30:
        verdict = "downtrend"
    elif up > down:
        verdict = "up-bias"
    else:
        verdict = "down-bias"
    return {"aroon_up": round(up, 2), "aroon_down": round(down, 2), "verdict": verdict}


def fisher_transform(closes, n: int = 9) -> dict:
    """Fisher Transform: normalizes price to sharpen turning points.

    Fisher = 0.5 * ln((1 + x) / (1 - x)) where x is a normalized price over
    the window. A Fisher crossing above its prior value (trigger) after an
    extreme low is a reversal signal. None when history insufficient.
    """
    if len(closes) < n + 1:
        return {"fisher": None, "trigger": None, "verdict": None}
    try:
        import math

        vals = []
        for i in range(n, len(closes)):
            seg = [float(c) for c in closes[i - n + 1 : i + 1]]
            hi, lo = max(seg), min(seg)
            x = 0.0 if hi == lo else 2.0 * (float(closes[i]) - lo) / (hi - lo) - 1.0
            # clamp to avoid log(0)
            x = max(-0.999, min(0.999, x))
            vals.append(0.5 * math.log((1.0 + x) / (1.0 - x)))
        fisher = vals[-1]
        trigger = vals[-2] if len(vals) >= 2 else None
        verdict = None
        if trigger is not None:
            if fisher > trigger and fisher < -1.0:
                verdict = "reversal-up"
            elif fisher < trigger and fisher > 1.0:
                verdict = "reversal-down"
            elif fisher > trigger:
                verdict = "up"
            else:
                verdict = "down"
        return {"fisher": round(fisher, 4), "trigger": round(trigger, 4) if trigger is not None else None, "verdict": verdict}
    except (TypeError, ValueError, ZeroDivisionError):
        return {"fisher": None, "trigger": None, "verdict": None}


def chaikin_oscillator(highs, lows, closes, volumes, fast: int = 3, slow: int = 10) -> float | None:
    """Chaikin Oscillator = EMA(fast) of A/D line - EMA(slow) of A/D line.

    Positive = buying pressure (accumulation); negative = selling pressure.
    None when history insufficient.
    """
    if len(highs) < slow + 2 or len(lows) < slow + 2 or len(closes) < slow + 2 or len(volumes) < slow + 2:
        return None
    try:
        ad = 0.0
        ad_series = []
        for i in range(len(closes)):
            hi, lo, c, v = float(highs[i]), float(lows[i]), float(closes[i]), float(volumes[i])
            mfm = 0.0 if hi == lo else ((c - lo) - (hi - c)) / (hi - lo)
            ad += mfm * v
            ad_series.append(ad)
        ema_fast = ema(ad_series, fast)
        ema_slow = ema(ad_series, slow)
        if ema_fast[-1] is None or ema_slow[-1] is None:
            return None
        return round(float(ema_fast[-1]) - float(ema_slow[-1]), 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def elder_ray(highs, lows, closes, n: int = 13) -> dict:
    """Elder-Ray: Bull Power = High - EMA(n); Bear Power = Low - EMA(n).

    Rising bull power + falling (less negative) bear power = buying pressure;
    the reverse = selling pressure. None when history insufficient.
    """
    if len(highs) < n or len(lows) < n or len(closes) < n:
        return {"bull_power": None, "bear_power": None, "verdict": None}
    try:
        ema_vals = ema([float(c) for c in closes], n)
        if ema_vals[-1] is None:
            return {"bull_power": None, "bear_power": None, "verdict": None}
        e = ema_vals[-1]
        bull = float(highs[-1]) - e
        bear = float(lows[-1]) - e
        # compare to the prior bar for the trend of each power line
        ema_prev = ema_vals[-2] if len(ema_vals) >= 2 else None
        if ema_prev is None:
            return {"bull_power": round(bull, 4), "bear_power": round(bear, 4), "verdict": None}
        bull_prev = float(highs[-2]) - ema_prev
        bear_prev = float(lows[-2]) - ema_prev
        if bull > bull_prev and bear > bear_prev:
            verdict = "buying-pressure"
        elif bull < bull_prev and bear < bear_prev:
            verdict = "selling-pressure"
        elif bull > 0 and bear < 0:
            verdict = "mixed-bull"
        else:
            verdict = "mixed-bear"
        return {"bull_power": round(bull, 4), "bear_power": round(bear, 4), "verdict": verdict}
    except (TypeError, ValueError, ZeroDivisionError):
        return {"bull_power": None, "bear_power": None, "verdict": None}


def supertrend(highs, lows, closes, atr_mult: float = 3.0, n: int = 10) -> dict:
    """Supertrend: ATR-based trailing line that flips direction.

    Basic band = (high + low) / 2 +/- atr_mult x ATR(n); the line trails the
    band on the trend side and flips when price closes through it. Returns
    the current line + direction (up/down). None when history insufficient.
    """
    if len(highs) < n + 1 or len(lows) < n + 1 or len(closes) < n + 1:
        return {"line": None, "direction": None}
    try:
        from tradingagents.strategies.size import atr as _atr

        atr_v = _atr(highs, lows, closes, window=n)
        if atr_v is None or atr_v <= 0:
            return {"line": None, "direction": None}
        # simple single-bar read: basic band around the midpoint
        mid = (float(highs[-1]) + float(lows[-1])) / 2.0
        upper = mid + float(atr_mult) * atr_v
        lower = mid - float(atr_mult) * atr_v
        c = float(closes[-1])
        if c > upper:
            direction = "up"
            line = lower
        elif c < lower:
            direction = "down"
            line = upper
        else:
            # inside the band: keep the prior direction via the close vs mid
            direction = "up" if c >= mid else "down"
            line = lower if direction == "up" else upper
        return {"line": round(line, 4), "direction": direction}
    except (TypeError, ValueError, ZeroDivisionError):
        return {"line": None, "direction": None}


def volume_profile(closes, volumes, bins: int = 20) -> dict:
    """Volume profile: distribute each bar's volume across price bins.

    Returns the point of control (POC = price bin with the most volume) and
    the value area: the smallest contiguous band around the POC holding >=70%
    of the volume, expanded one bin at a time toward the heavier neighbour (at
    a range edge the expansion is necessarily one-sided, so a bimodal
    distribution can legitimately span the whole range - `value_area_pct` is
    returned so that is visible rather than assumed). A dip into the POC /
    value-area low is a stronger mean-reversion support zone. None when
    history insufficient.
    """
    if len(closes) < 2 or len(volumes) < 2 or bins < 2:
        return {"poc": None, "value_area_high": None, "value_area_low": None}
    try:
        lo = min(float(c) for c in closes)
        hi = max(float(c) for c in closes)
        if hi <= lo:
            return {"poc": None, "value_area_high": None, "value_area_low": None}
        width = (hi - lo) / bins
        vol_by_bin = [0.0] * bins
        for c, v in zip(closes, volumes, strict=False):
            idx = min(bins - 1, int((float(c) - lo) / width))
            vol_by_bin[idx] += float(v)
        total = sum(vol_by_bin)
        if total <= 0:
            return {"poc": None, "value_area_high": None, "value_area_low": None}
        poc_idx = max(range(bins), key=lambda i: vol_by_bin[i])
        poc = lo + (poc_idx + 0.5) * width
        # value area: expand around the POC until ~70% of volume is covered
        target = total * 0.7
        acc = vol_by_bin[poc_idx]
        lo_i = hi_i = poc_idx
        while acc < target and (lo_i > 0 or hi_i < bins - 1):
            # Expand toward the heavier neighbour. The while guard guarantees
            # the else branch has room (lo_i == 0 implies hi_i < bins - 1).
            if lo_i > 0 and (hi_i >= bins - 1 or vol_by_bin[lo_i - 1] >= vol_by_bin[hi_i + 1]):
                lo_i -= 1
            else:
                hi_i += 1
            # The band is the accumulation: recompute it from the bins rather
            # than incrementally (the incremental add that used to sit here was
            # immediately overwritten, i.e. dead).
            acc = sum(vol_by_bin[lo_i : hi_i + 1])
        return {
            "poc": round(poc, 4),
            "value_area_high": round(lo + (hi_i + 0.5) * width, 4),
            "value_area_low": round(lo + (lo_i + 0.5) * width, 4),
            "value_area_pct": round(acc / total, 4),
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return {"poc": None, "value_area_high": None, "value_area_low": None}


# ---------------------------------------------------------------------------
# Trend-following as spectral excess mass (2607.19497), with the lookback the
# engine's own cost estimate can pay for. Both are STATE READS: reported
# beside the swing factor, never folded into its score.
# ---------------------------------------------------------------------------

#: Poisson-kernel span of the spectral read. 250 periods is the long span the
#: trend-following literature reports as the practical optimum; the decay it
#: implies, ``lambda = 1 - 2/(span+1)``, is this module's own EMA convention
#: (:func:`ema` uses ``k = 2/(n+1)``), so the kernel is the filter a caller of
#: the swing factor would actually run rather than an abstract taper.
_SPECTRAL_SPAN = 250

#: Shortest series the spectral read is attempted on: below this the null's
#: own sampling spread (which shrinks only as 1/sqrt(n)) is the same size as a
#: low-frequency component the read is supposed to find.
_SPECTRAL_MIN_OBS = 64

#: The excess must clear this many sampling standard deviations of the
#: white-noise null. A bare positive sign is met by roughly half of all
#: white-noise draws, so the sign alone is not a gate; 2 sigma is a ~2.5%
#: false-positive rate under the null.
_SPECTRAL_NULL_SIGMA = 2.0

#: Share of one period's volatility the round trip may cost per period. This
#: is the design knob that sets the span's scale (the paper's own calibration
#: is its backtest); it is not fitted to any symbol.
_COST_BUDGET_VOL_SHARE = 0.005

#: Span bounds: a lookback below one period is meaningless, and past two
#: trading years the engine's days-to-weeks mandate is gone.
_SPAN_MIN = 1
_SPAN_MAX = 504


def spectral_excess_mass(returns: list, span: int = _SPECTRAL_SPAN) -> dict:
    """Poisson-kernel-weighted excess low-frequency spectral mass.

    2607.19497 expresses a trend system's P&L in volatility-normalized
    returns and splits it into autocorrelation and drift terms: at zero drift
    the alpha is exactly the *excess low-frequency spectral mass*, i.e. the
    power the Poisson kernel of span ``span`` sees above what white noise
    carries over the same window. It is a CONDITION, not a signal - it says
    when trend alpha can exist, never which direction the name will go - so it
    is reported beside the swing factor and never inside its score.

    ``mass`` is that excess in vol^2 units: the Poisson-kernel-weighted
    autocovariance sum (the kernel's spectral integral, by Wiener-Khinchin),
    net of the finite-sample bias ``-(n-k)/n^2`` of the biased autocorrelation
    estimator, and doubled for the two-sided spectrum. It is compared against
    ``_SPECTRAL_NULL_SIGMA`` sampling standard deviations of the white-noise
    null, ``2*sqrt(sum(w^2)/n)``, which is the read's own noise floor.

    Both fields are None - never a fabricated ``False`` - when the series is
    shorter than ``_SPECTRAL_MIN_OBS`` or carries no dispersion (a constant
    series has no low-frequency content to measure against its own noise).

    Cost: one length-``2n`` FFT. The caller reports the window it passed.
    """
    try:
        values = [float(v) for v in returns if v is not None]
    except (TypeError, ValueError):
        return {"mass": None, "condition_met": None}
    if not values or span < 2:
        return {"mass": None, "condition_met": None}
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = int(x.size)
    if n < _SPECTRAL_MIN_OBS:
        return {"mass": None, "condition_met": None}
    sd = float(x.std())
    if not sd > 0.0:
        return {"mass": None, "condition_met": None}
    z = (x - float(x.mean())) / sd
    lam = 1.0 - 2.0 / (span + 1.0)
    lags = np.arange(1, n, dtype=float)
    weights = (1.0 - lam) * lam ** (lags - 1.0)
    # Biased sample autocorrelation of the normalized series, from its power
    # spectrum (acf[0] == 1 because z has unit variance).
    spec = np.fft.rfft(z, 2 * n)
    acf = np.fft.irfft(spec * np.conjugate(spec), 2 * n)[:n] / n
    # Under white noise the biased estimator is centred at -(n-k)/n^2, so the
    # excess is measured against that null rather than against zero.
    excess = 2.0 * float(np.dot(weights, acf[1:] + (n - lags) / (n * n)))
    null_sd = 2.0 * float(np.sqrt(float(np.dot(weights, weights)) / n))
    return {
        "mass": round(excess, 6),
        "condition_met": bool(excess > _SPECTRAL_NULL_SIGMA * null_sd),
    }


def cost_optimal_span(cost_bps: float, vol: float) -> int | None:
    """Lookback span whose turnover spends the engine's cost estimate.

    An EMA of span ``s`` replaces ``2/(s+1)`` of its weight each period (the
    convention :func:`ema` uses), so the round trip it pays per period is
    ``cost * 2/(s+1)``. Holding that inside ``_COST_BUDGET_VOL_SHARE`` of one
    period's volatility gives ``s >= 2*cost/(share*vol)``: a dearer round trip
    or a calmer name buys a longer lookback, which is the trade-off the
    cost-optimal-span result states.

    ``vol`` is the symbol's per-period volatility, in the same return units as
    ``cost_bps`` is a fraction of. Returns None - never a fabricated span -
    when either input is missing or non-positive.
    """
    try:
        cost = float(cost_bps)
        sigma = float(vol)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(cost) or not math.isfinite(sigma) or cost < 0.0 or sigma <= 0.0:
        return None
    span = math.ceil(2.0 * (cost / 10_000.0) / (_COST_BUDGET_VOL_SHARE * sigma))
    return max(_SPAN_MIN, min(int(span), _SPAN_MAX))


# ---------------------------------------------------------------------------
# Depth reads (TechnicalScore library §7/§8/§21-§25/§28-§30/§43-§48/§58/§59/
# §80/§91/§101-§104): the level / slope / ratio form of a series the module
# already computes, so a leaf can print a checkable number instead of a bool.
# Every producer refuses with a ``reason`` string - never a fabricated 0 -
# when its series is too short, and an optional leg that cannot be measured
# carries its own ``<leg>_reason`` while the rest of the read stands.
# ---------------------------------------------------------------------------

#: §59's volume-trend pair; the slower leg sets the volume history the read
#: needs, which is why :func:`volume_depth` asks for 60 sessions, not 20.
_VOL_TREND_FAST = 20
_VOL_TREND_SLOW = 60


def range_position(highs, lows, closes, n: int = 20) -> dict:
    """Where the latest close sits inside the N-bar high/low range.

    * ``high_n`` / ``low_n`` - the N-bar highest high / lowest low, the levels
      :func:`donchian_channel` returns.
    * ``bars_since_high`` - bars since the most recent N-bar high (0 = the
      latest bar); the library's §101 ``HighAge``.
    * ``distance_from_low`` - ``close / low_n - 1`` (§103), a fraction.
    * ``range_position`` - ``(close - low_n) / (high_n - low_n)`` (§104), 0 at
      the low and 1 at the high; ``None`` on a zero-width range rather than a
      fabricated 0.5.

    ``reason`` is a string when fewer than ``n`` highs/lows or no close were
    supplied.
    """
    if len(highs) < n or len(lows) < n or not closes:
        return {
            "high_n": None, "low_n": None, "bars_since_high": None,
            "distance_from_low": None, "range_position": None,
            "reason": f"fewer than {n} bars (or no close): range unmeasured",
        }
    hs = [float(x) for x in highs[-n:]]
    ls = [float(x) for x in lows[-n:]]
    high_n = max(hs)
    low_n = min(ls)
    last = float(closes[-1])
    last_high = max(i for i, v in enumerate(hs) if v == high_n)
    width = high_n - low_n
    return {
        "high_n": round(high_n, 4),
        "low_n": round(low_n, 4),
        "bars_since_high": n - 1 - last_high,
        "distance_from_low": round(last / low_n - 1.0, 6) if low_n > 0 else None,
        "range_position": round((last - low_n) / width, 4) if width > 0 else None,
        "reason": None,
    }


def sma_legs(closes, fast: int = 20, slow: int = 100) -> dict:
    """Price vs the SMA20 / SMA100 legs the engine ledger records as absent.

    ``sma_fast`` / ``sma_slow`` are the latest simple moving averages over the
    module's own :func:`_sma`, and ``above_fast`` / ``above_slow`` the library
    §3 ``MAState`` booleans (``close > SMA_n``). ``reason`` is a string when
    fewer than ``slow`` closes were supplied.
    """
    if not closes or len(closes) < slow or fast < 1 or slow < 1:
        return {
            "sma_fast": None, "sma_slow": None, "above_fast": None,
            "above_slow": None,
            "reason": f"fewer than {slow} closes: SMA legs unmeasured",
        }
    vals = [float(c) for c in closes]
    last = vals[-1]
    sma_fast = _sma(vals, fast)[-1] if len(vals) >= fast else None
    sma_slow = _sma(vals, slow)[-1]
    return {
        "sma_fast": round(sma_fast, 4) if sma_fast is not None else None,
        "sma_slow": round(sma_slow, 4),
        "above_fast": bool(last > sma_fast) if sma_fast is not None else None,
        "above_slow": bool(last > sma_slow),
        "reason": None,
    }


def _macd_series(closes, fast: int, slow: int, signal: int):
    """MACD line / signal / histogram series aligned to ``closes``.

    The same three lines ``value_dip._macd_hist`` builds, assembled from this
    module's own :func:`ema` (the single EMA convention both modules share), so
    a public MACD producer can live here without editing that module or
    importing its private helper. Returns ``(line, signal, hist)``, or None
    when the warm-up is incomplete.
    """
    if not closes or len(closes) < slow + signal + 2:
        return None
    vals = [float(c) for c in closes]
    ema_fast = ema(vals, fast)
    ema_slow = ema(vals, slow)
    line = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(ema_fast, ema_slow, strict=False)
    ]
    start = next((i for i, v in enumerate(line) if v is not None), None)
    if start is None:
        return None
    sig = [None] * start + ema(line[start:], signal)
    hist = [
        (lv - s) if (lv is not None and s is not None) else None
        for lv, s in zip(line, sig, strict=False)
    ]
    return line, sig, hist


def macd_depth(closes, fast: int = 12, slow: int = 26, signal: int = 9,
               atr_value: float | None = None) -> dict:
    """MACD line / signal / histogram plus their one-bar changes (§7/§8).

    * ``macd`` / ``signal`` / ``hist`` - the latest line, signal and histogram.
    * ``macd_slope`` / ``signal_slope`` / ``hist_slope`` - one-bar deltas
      (§7's ``MACDSlope`` / ``HistogramSlope`` with k=1, the same delta
      ``rule_eval.rule_signal_macd_hist_rising`` tests).
    * ``hist_accel`` - ``Δhist_t - Δhist_{t-1}`` (§7's
      ``HistogramAcceleration``).
    * ``crossover`` - ``I(MACD > Signal)`` (§8).
    * ``atr_spread`` - ``(MACD - Signal)/ATR`` (§8's ``MACDSpread``) when
      ``atr_value`` is a positive number, else ``None`` with
      ``atr_spread_reason`` naming the missing ATR.

    ``reason`` is a string when fewer than ``slow + signal + 2`` closes were
    supplied (the MACD warm-up this module's ``value_dip._macd_hist`` uses).
    """
    empty = {
        "macd": None, "signal": None, "hist": None,
        "macd_slope": None, "signal_slope": None, "hist_slope": None,
        "hist_accel": None, "crossover": None, "atr_spread": None,
        "reason": None, "atr_spread_reason": None,
    }
    series = _macd_series(closes, fast, slow, signal)
    if series is None:
        return {**empty, "reason": (
            f"fewer than {slow + signal + 2} closes: MACD warm-up incomplete"
        )}
    line, sig, hist = series
    line_v = [v for v in line if v is not None]
    sig_v = [v for v in sig if v is not None]
    hist_v = [v for v in hist if v is not None]
    if not line_v or not sig_v or not hist_v:
        return {**empty, "reason": "no usable MACD bar after the warm-up"}
    out = {
        "macd": round(line_v[-1], 4),
        "signal": round(sig_v[-1], 4),
        "hist": round(hist_v[-1], 4),
        "macd_slope": round(line_v[-1] - line_v[-2], 4) if len(line_v) >= 2 else None,
        "signal_slope": round(sig_v[-1] - sig_v[-2], 4) if len(sig_v) >= 2 else None,
        "hist_slope": round(hist_v[-1] - hist_v[-2], 4) if len(hist_v) >= 2 else None,
        "hist_accel": None,
        "crossover": bool(line_v[-1] > sig_v[-1]),
        "atr_spread": None,
        "reason": None,
        "atr_spread_reason": None,
    }
    if len(hist_v) >= 3:
        out["hist_accel"] = round(
            (hist_v[-1] - hist_v[-2]) - (hist_v[-2] - hist_v[-3]), 4
        )
    try:
        atr = float(atr_value) if atr_value is not None else None
    except (TypeError, ValueError):
        atr = None
    if atr is None or atr <= 0.0:
        out["atr_spread_reason"] = "no positive ATR supplied: spread not normalised"
    else:
        out["atr_spread"] = round((line_v[-1] - sig_v[-1]) / atr, 6)
    return out


def bollinger_bandwidth(closes, window: int = 20, k: float = 2.0,
                        lookback: int = 100, pct: float = 0.2,
                        expansion_lag: int = 5) -> dict:
    """Bollinger bandwidth, its own-history percentile and the squeeze reads.

    The bands are the same population-standard-deviation construction
    ``value_dip.bollinger_pct_b`` uses; the bandwidth is
    ``BBW = (UB - LB)/MB = 2k*sd/MB`` (§21).

    * ``bbw`` - the latest bandwidth.
    * ``bbw_percentile`` - its empirical rank against the trailing
      ``lookback`` bandwidths (§22, the same rank convention as
      ``compression.atr_compression_read``).
    * ``squeeze`` - ``bbw_percentile <= pct`` (§23, the lower fifth by
      default); a REPORTED reading, never a gate.
    * ``expansion`` - ``BBW_t/BBW_{t-expansion_lag} - 1`` (§24).
    * ``mean_reversion_distance`` - ``(close - MB)/(UB - LB)`` (§25), the
      mid-band-referenced form ``bollinger_pct_b`` does not compute; ``None``
      on a zero-width band rather than a fabricated 0.

    ``reason`` is a string when fewer than ``window + expansion_lag`` closes
    were supplied, or when the middle band is non-positive (the bandwidth has
    no denominator).
    """
    empty = {
        "bbw": None, "bbw_percentile": None, "squeeze": None,
        "expansion": None, "mean_reversion_distance": None, "reason": None,
    }
    if (not closes or window < 2 or expansion_lag < 1
            or len(closes) < window + expansion_lag):
        return {**empty, "reason": (
            f"fewer than {window + expansion_lag} closes: bandwidth unmeasured"
        )}
    vals = [float(c) for c in closes]
    bbw_series = []
    for i in range(window, len(vals) + 1):
        seg = vals[i - window:i]
        mid = sum(seg) / window
        if mid <= 0:
            bbw_series.append(None)
            continue
        sd = math.sqrt(sum((v - mid) ** 2 for v in seg) / window)
        bbw_series.append(2.0 * float(k) * sd / mid)
    last_seg = vals[-window:]
    mid = sum(last_seg) / window
    sd = math.sqrt(sum((v - mid) ** 2 for v in last_seg) / window)
    upper = mid + float(k) * sd
    lower = mid - float(k) * sd
    bbw = bbw_series[-1]
    if bbw is None:
        return {**empty, "reason": "non-positive middle band: bandwidth undefined"}
    valid = [v for v in bbw_series if v is not None]
    rank_window = valid[-lookback:] if lookback and lookback > 0 else valid
    rank = _pct_rank(rank_window, bbw)
    lagged = bbw_series[-1 - expansion_lag]
    width = upper - lower
    return {
        "bbw": round(bbw, 6),
        "bbw_percentile": round(rank, 4) if rank is not None else None,
        "squeeze": bool(rank <= pct) if rank is not None else None,
        "expansion": round(bbw / lagged - 1.0, 6) if lagged else None,
        "mean_reversion_distance": (
            round((vals[-1] - mid) / width, 4) if width > 0 else None
        ),
        "reason": None,
    }


def mean_reversion_z(series, value: float | None = None, min_n: int = 4) -> dict:
    """Z-score of one observation against its own history (§80).

    ``value`` defaults to the last usable observation of ``series`` (the
    "current reading vs its own past" form the ledger names for the RSI / %b /
    price-vs-band histories). The statistic is ``value_dip.zscore`` - the
    repo's single generic z helper, imported rather than re-derived; the sign
    is preserved, so a below-mean reading stays negative.

    Returns ``z``, the ``value`` measured and ``n`` (usable observations).
    ``reason`` is a string when fewer than ``min_n`` observations exist, the
    series carries no dispersion, or no value could be resolved - the z is
    never fabricated.
    """
    from .value_dip import zscore

    vals = [float(v) for v in (series or []) if v is not None]
    if value is None and vals:
        value = vals[-1]
    try:
        z = zscore(value, vals, min_n=min_n) if value is not None else None
    except (TypeError, ValueError):
        z = None
    if z is None:
        return {
            "z": None,
            "value": value,
            "n": len(vals),
            "reason": (
                f"fewer than {min_n} observations, no value, or zero "
                "dispersion: z unmeasured"
            ),
        }
    return {"z": round(z, 4), "value": value, "n": len(vals), "reason": None}


def volume_depth(closes, volumes, n: int = 20, *, highs=None, lows=None,
                 atr_value: float | None = None) -> dict:
    """Volume spike / trend and the volume-confirmed breakout (§58/§59/§45).

    * ``volume_spike`` - latest volume / the nearest-rank 95th percentile of
      the last ``n`` volumes (§58).
    * ``volume_trend`` - ``SMA(V,20)/SMA(V,60) - 1`` (§59), computed with the
      module's own :func:`_sma`.
    * ``volume_ratio`` - latest volume / the mean of the last ``n`` volumes,
      the ``V/avg`` leg of §45.
    * ``breakout_strength`` - ``(close - prior N-bar highest high)/ATR``
      (§41), reported signed (negative = no breakout); needs ``highs``/``lows``.
    * ``breakout_confirmation`` - ``breakout_strength x volume_ratio`` (§45),
      the volume-confirmed breakout ratio.

    ``reason`` is a string when the volume history is shorter than
    ``max(n, 60)`` (the §59 pair sets the required history); the breakout leg
    alone is ``None`` with ``breakout_reason`` when no highs/lows were
    supplied, the prior channel is too short, or the ATR is unmeasurable.
    """
    empty = {
        "volume_spike": None, "volume_trend": None, "volume_ratio": None,
        "breakout_strength": None, "breakout_confirmation": None,
        "reason": None, "breakout_reason": None,
    }
    need = max(n, _VOL_TREND_SLOW)
    if not closes or not volumes or len(closes) < need or len(volumes) < need:
        return {**empty, "reason": (
            f"fewer than {need} closes/volumes: volume depth unmeasured"
        )}
    vs = [float(v) for v in volumes]
    last_v = vs[-1]
    p95 = _p95(vs[-n:])
    mean_n = sum(vs[-n:]) / n
    sma_fast = _sma(vs, _VOL_TREND_FAST)[-1]
    sma_slow = _sma(vs, _VOL_TREND_SLOW)[-1]
    ratio = last_v / mean_n if mean_n > 0 else None
    out = {
        "volume_spike": round(last_v / p95, 4) if p95 and p95 > 0 else None,
        "volume_trend": round(sma_fast / sma_slow - 1.0, 6) if sma_slow else None,
        "volume_ratio": round(ratio, 4) if ratio is not None else None,
        "breakout_strength": None,
        "breakout_confirmation": None,
        "reason": None,
        "breakout_reason": None,
    }
    if highs is None or lows is None:
        out["breakout_reason"] = "no highs/lows supplied: breakout strength unmeasured"
        return out
    if len(highs) < n + 1 or len(lows) < n + 1:
        out["breakout_reason"] = (
            f"fewer than {n + 1} highs/lows: no prior-window breakout level"
        )
        return out
    ref = max(float(x) for x in highs[-n - 1:-1])
    atr = atr_value
    if atr is None:
        from .size import atr as _atr

        atr = _atr([float(x) for x in highs], [float(x) for x in lows],
                   [float(c) for c in closes])
    try:
        atr = float(atr) if atr is not None else None
    except (TypeError, ValueError):
        atr = None
    if atr is None or atr <= 0.0:
        out["breakout_reason"] = "ATR unmeasurable: breakout strength not normalised"
        return out
    strength = (float(closes[-1]) - ref) / atr
    out["breakout_strength"] = round(strength, 4)
    if ratio is not None:
        out["breakout_confirmation"] = round(strength * ratio, 4)
    else:
        out["breakout_reason"] = "volume baseline unmeasured: confirmation not scaled"
    return out


def atr_depth(highs, lows, closes, short: int = 14, long: int = 50,
              move_n: int = 5, accel_lag: int = 1) -> dict:
    """ATR ratio / normalised movement / volatility acceleration (§28-§30, §91).

    Uses ``size.atr`` - the repo's scalar ATR producer - on the full series and
    on a lagged slice, so this is the *ratio* read and not
    ``compression.atr_compression_read``'s percentile.

    * ``atr_short`` / ``atr_long`` - ATR over ``short`` and ``long`` true
      ranges (the latter through :func:`size.atr`'s mean-of-TRs definition).
    * ``atr_pct`` - ``atr_short / close`` (§27 ``NATR`` as a fraction).
    * ``atr_ratio`` / ``atr_expansion`` / ``atr_contraction`` -
      ``ATR_short/ATR_long``, ``ratio - 1`` (§28) and ``1 - ratio`` (§29).
    * ``atr_move`` - ``(close_t - close_{t-move_n})/ATR_short`` (§30).
    * ``vol_acceleration`` - ``atr_pct_t - atr_pct_{t-accel_lag}`` (§91), the
      ATR% series standing in for the volatility regime.

    ``reason`` is a string when the series are misaligned, shorter than
    ``max(long, move_n) + 1`` bars, or an ATR leg is unmeasurable.
    """
    empty = {
        "atr_short": None, "atr_long": None, "atr_pct": None,
        "atr_ratio": None, "atr_expansion": None, "atr_contraction": None,
        "atr_move": None, "vol_acceleration": None, "reason": None,
    }
    need = max(long, move_n) + 1
    if (len(highs) != len(lows) or len(lows) != len(closes)
            or len(closes) < need or short < 1 or long < 1
            or move_n < 1 or accel_lag < 1 or accel_lag >= len(closes) - 1):
        return {**empty, "reason": (
            f"fewer than {need} aligned bars: ATR depth unmeasured"
        )}
    from .size import atr as _atr

    h = [float(x) for x in highs]
    lo = [float(x) for x in lows]
    c = [float(x) for x in closes]
    atr_short = _atr(h, lo, c, window=short)
    atr_long = _atr(h, lo, c, window=long)
    if atr_short is None or atr_long is None or atr_short <= 0.0 or atr_long <= 0.0:
        return {**empty, "reason": "ATR unmeasurable: depth not computed"}
    ratio = atr_short / atr_long
    atr_pct = atr_short / c[-1] if c[-1] > 0 else None
    prev_atr = _atr(h[:-accel_lag], lo[:-accel_lag], c[:-accel_lag], window=short)
    prev_close = c[-1 - accel_lag]
    prev_pct = (
        prev_atr / prev_close if (prev_atr is not None and prev_close > 0) else None
    )
    return {
        "atr_short": round(atr_short, 6),
        "atr_long": round(atr_long, 6),
        "atr_pct": round(atr_pct, 6) if atr_pct is not None else None,
        "atr_ratio": round(ratio, 6),
        "atr_expansion": round(ratio - 1.0, 6),
        "atr_contraction": round(1.0 - ratio, 6),
        "atr_move": round((c[-1] - c[-1 - move_n]) / atr_short, 4),
        "vol_acceleration": (
            round(atr_pct - prev_pct, 6)
            if (atr_pct is not None and prev_pct is not None) else None
        ),
        "reason": None,
    }

