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
    "stoch_rsi",
    "rsi2",
    "williams_r",
    "keltner_channel",
    "donchian_channel",
    "obv_divergence",
    "parabolic_sar",
    "elder_thermometer",
]


def stoch_rsi(closes: list, n: int = 14) -> dict:
    """StochRSI = (RSI - min RSI) / (max RSI - min RSI) over the window.

    Smoother, more sensitive oversold read than plain RSI: StochRSI < 0.2
    oversold, > 0.8 overbought. None when history insufficient.
    """
    if len(closes) < n + 2:
        return {"stochrsi": None, "oversold": None, "overbought": None}
    rsi_valid = []
    for i in range(n, len(closes)):
        seg = closes[i - n : i + 1]
        gains = losses = 0.0
        for j in range(1, len(seg)):
            d = seg[j] - seg[j - 1]
            if d >= 0:
                gains += d
            else:
                losses -= d
        if gains + losses == 0:
            r = 50.0
        elif losses == 0:
            r = 100.0
        else:
            rs = gains / losses
            r = 100.0 - 100.0 / (1.0 + rs)
        rsi_valid.append(r)
    if len(rsi_valid) < n + 1:
        return {"stochrsi": None, "oversold": None, "overbought": None}
    window = rsi_valid[-(n + 1) :]
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
    mid = sum(closes[-n:]) / n
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


def donchian_channel(highs, lows, n: int = 20) -> dict:
    """Donchian Channel: N-day highest high / lowest low + breakout signal.

    Close above the upper channel = bullish breakout; below lower = bearish.
    """
    if len(highs) < n or len(lows) < n:
        return {"upper": None, "lower": None, "mid": None, "breakout_up": None, "breakout_dn": None}
    up = max(float(x) for x in highs[-n:])
    lo = min(float(x) for x in lows[-n:])
    mid = (up + lo) / 2.0
    return {
        "upper": round(up, 4),
        "lower": round(lo, 4),
        "mid": round(mid, 4),
        "breakout_up": None,  # closes not passed; caller derives
        "breakout_dn": None,
    }


def obv_divergence(closes, volumes, window: int = 30) -> dict:
    """On-Balance-Volume vs price: cumulative OBV trend vs price trend.

    Returns {'obv_up': bool, 'bullish_div': bool} for a price lower-low with
    a higher OBV low (bullish divergence) - a dip-reversal confirmation.
    """
    if len(closes) < window or len(volumes) < window:
        return {"obv_up": None, "bullish_div": None}
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
    first_price = closes[-len(first_obv) : -len(second_obv)] if len(second_obv) else closes[-len(first_obv) :]
    second_price = closes[-len(second_obv) :]
    price_dn = bool(
        len(second_price) and len(first_price) and second_price[-1] < first_price[-1]
    )
    obv_up = bool(
        len(second_obv) and len(first_obv) and second_obv[-1] > first_obv[-1]
    )
    return {"obv_up": obv_up, "bullish_div": bool(price_dn and obv_up)}


def parabolic_sar(highs, lows, af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.2) -> dict:
    """Parabolic SAR trailing stop (Wilder). Returns current SAR + a below/exit
    flag (close below SAR = downtrend). None when history insufficient."""
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
        return {"sar": round(sar, 4), "below": None, "exit": None}
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
