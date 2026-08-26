"""Additional technical factors for the value-dip + swing combo (pure, offline).

Complements the existing RSI / Bollinger / ATR / MACD / RVOL with the
volume-price and trend-strength oscillators commonly used to confirm a dip
buy and its swing exit:

  KST        - Know-Sure-Thing multi-ROC momentum oscillator
  MFI        - Money Flow Index (volume-weighted RSI over typical price)
  Stochastic - %K/%D oversold oscillator (slow via sma3)
  ADX / DI   - Wilder Average Directional Index trend-strength filter
  Chandelier - trailing stop = highest high - k x ATR (in swing.py instead)

Every function is pure and returns None on missing/invalid input (the
no-fabrication rule). No network, no state.
"""

from __future__ import annotations


def _sma(series: list, n: int) -> list:
    """SMA series; None for the first n-1 positions."""
    out = [None] * (n - 1)
    for i in range(n - 1, len(series)):
        out.append(sum(series[i - n + 1 : i + 1]) / n)
    return out


def _ema(series: list, n: int) -> list:
    """EMA series; None for the first n-1 positions."""
    if not series or n <= 0:
        return [None] * len(series)
    k = 2.0 / (n + 1)
    out = [None] * (n - 1)
    ema = sum(series[:n]) / n
    out.append(ema)
    for v in series[n:]:
        ema = float(v) * k + ema * (1 - k)
        out.append(ema)
    return out


def _roc(value: float | None, prev: float | None) -> float | None:
    if value is None or prev is None or prev == 0:
        return None
    return float(value) / float(prev) - 1.0


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
    """Classic daily/weekly pivot + support/resistance levels."""
    if high is None or low is None or close is None:
        return {"p": None, "r1": None, "s1": None, "r2": None, "s2": None}
    try:
        h, low_, c = float(high), float(low), float(close)
    except (TypeError, ValueError):
        return {"p": None, "r1": None, "s1": None, "r2": None, "s2": None}
    p = (h + low_ + c) / 3.0
    return {
        "p": round(p, 4),
        "r1": round(2 * p - low_, 4),
        "s1": round(2 * p - h, 4),
        "r2": round(p + (h - low_), 4),
        "s2": round(p - (h - low_), 4),
    }


__all__ = [
    "kst",
    "mf_index",
    "stochastic_oscillator",
    "adx",
    "pivot_points",
]
