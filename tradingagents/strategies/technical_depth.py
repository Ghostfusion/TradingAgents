"""TechnicalScore's §8.2 depth families - pure, offline, **measurement-only**.

The library `Strategies/scores/technical_score.md` names dozens of formulas the
engine's Phase-A producer set never built (`docs/scores/TechnicalScore.md`
§8.2): the regression family (§74-§79), moving-average depth (§2/§4/§6),
candle/gap depth (§66/§68/§69), the Zweig breadth thrust (§120), per-name ADV
participation (§1 Breadth) and the legacy oscillators (§62, §113-§117). This
module is that backlog, deduplicated into one family per public producer.

Nothing here is ever a gate or a size: every function is a measurement a score
component may read, and nothing is fabricated - a series too short for a
producer returns ``None`` values **with a reason string** in ``unavailable``
(``NA != 0`` is the published contract). No fetch, no state, no network.
"""

from __future__ import annotations

import math

from .relative_strength import slope_pct as _slope_pct

__all__ = [
    "regression_read",
    "moving_average_depth",
    "ema_stack",
    "candle_strength",
    "gap_depth",
    "zweig_breadth_thrust",
    "adv_participation",
    "dpo",
    "ultimate_oscillator",
    "awesome_oscillator",
    "relative_vigor_index",
    "coppock_curve",
    "ease_of_movement",
]

#: The reason key every producer carries; a refused read says why in words.
_REASON = "unavailable"


def _finite(series) -> list[float]:
    """The finite floats of ``series`` (None / NaN / inf rows dropped)."""
    out: list[float] = []
    for v in series or []:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def _refused(keys, reason: str, n: int = 0) -> dict:
    """The one refusal shape: every key ``None`` + ``n`` + the reason."""
    out: dict = dict.fromkeys(keys)
    out["n"] = int(n)
    out[_REASON] = reason
    return out


def _sma_series(vals: list[float], n: int) -> list[float | None]:
    """SMA series; ``None`` for the first n-1 positions (or all if too short)."""
    if n <= 0 or len(vals) < n:
        return [None] * len(vals)
    out: list[float | None] = [None] * (n - 1)
    s = sum(vals[:n])
    out.append(s / n)
    for i in range(n, len(vals)):
        s += vals[i] - vals[i - n]
        out.append(s / n)
    return out


def _wma_series(vals: list[float], n: int) -> list[float | None]:
    """WMA series (weights 1..n, the library's §2 form)."""
    if n <= 0 or len(vals) < n:
        return [None] * len(vals)
    den = n * (n + 1) / 2.0
    out: list[float | None] = [None] * (n - 1)
    for i in range(n - 1, len(vals)):
        window = vals[i - n + 1 : i + 1]
        out.append(sum((j + 1) * v for j, v in enumerate(window)) / den)
    return out


def _wma_last(seg: list[float], n: int) -> float | None:
    if n <= 0 or len(seg) < n:
        return None
    window = seg[-n:]
    den = n * (n + 1) / 2.0
    return sum((j + 1) * v for j, v in enumerate(window)) / den


def _ema_series(vals: list[float], n: int) -> list[float | None]:
    """EMA series (SMA-seeded); ``None`` for the first n-1 positions."""
    if n <= 0 or len(vals) < n:
        return [None] * len(vals)
    k = 2.0 / (n + 1)
    out: list[float | None] = [None] * (n - 1)
    e = sum(vals[:n]) / n
    out.append(e)
    for v in vals[n:]:
        e = v * k + e * (1 - k)
        out.append(e)
    return out


def _hma_last(vals: list[float], n: int) -> float | None:
    """Hull MA: ``WMA_sqrt(n)(2*WMA_n/2 - WMA_n)`` (§2)."""
    if n < 2:
        return None
    half = n // 2
    sqrt_n = max(1, int(round(math.sqrt(n))))
    wf = _wma_series(vals, n)
    wh = _wma_series(vals, half)
    comp = [
        2.0 * wh[i] - wf[i] if (wf[i] is not None and wh[i] is not None) else None
        for i in range(len(vals))
    ]
    seg = [v for v in comp if v is not None]
    if len(seg) < sqrt_n:
        return None
    return _wma_last(seg, sqrt_n)


def _ols(xs: list[float], ys: list[float]):
    """OLS fit ``y = a + b*x``; returns ``(slope, intercept, r2, resid_sd)``."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den
    intercept = my - slope * mx
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys, strict=True))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = (1.0 - ss_res / ss_tot) if ss_tot > 0 else None
    return slope, intercept, r2, math.sqrt(ss_res / n)


# ---------------------------------------------------------------------------
# 1. The regression family (library §73-§79; TECH-15)
# ---------------------------------------------------------------------------


def regression_read(
    closes: list, window: int = 20, *, z: float = 1.0
) -> dict:
    """OLS regression trend read over the last ``window`` closes.

    ``slope``/``intercept`` are the §73 fit of ``P_t = a + b*t`` (t = 0..n-1);
    ``r2`` is §74; ``trend_quality = Sign(beta) * R2`` is §75; the channel is
    the §76 fitted line +/- ``z`` residual standard deviations, and
    ``channel_position`` is the §77 ``(P - Lower) / (Upper - Lower)``;
    ``trend_to_noise`` is the §79 ``|C_t - C_(t-n)| / sd(C)``. All over the same
    single window, so the parts are one fit rather than five conventions.

    Returns ``{slope, intercept, r2, slope_pct, trend_quality, channel_mid,
    channel_upper, channel_lower, channel_position, residual_sd,
    trend_to_noise, n, unavailable}``. Refused (all ``None`` + the reason) below
    ``window`` observations or on a flat series (zero total variance, where R2
    has no denominator). ``channel_position`` is ``None`` when ``z`` collapses
    the channel (zero residual spread).
    """
    keys = (
        "slope", "intercept", "r2", "slope_pct", "trend_quality",
        "channel_mid", "channel_upper", "channel_lower", "channel_position",
        "residual_sd", "trend_to_noise",
    )
    vals = _finite(closes)
    if len(vals) < window or window < 3:
        return _refused(
            keys, f"need >= {window} closes (window >= 3), got {len(vals)}", len(vals)
        )
    seg = vals[-window:]
    n = len(seg)
    fit = _ols(list(range(n)), seg)
    if fit is None:
        return _refused(keys, "degenerate fit: every x is identical", n)
    slope, intercept, r2, resid_sd = fit
    if r2 is None:
        return _refused(keys, "flat series: zero total variance, R2 undefined", n)
    mean = sum(seg) / n
    sp = _slope_pct(seg, n)
    quality = (1.0 if slope > 0 else -1.0 if slope < 0 else 0.0) * r2
    mid = intercept + slope * (n - 1)
    upper = mid + z * resid_sd
    lower = mid - z * resid_sd
    width = upper - lower
    position = (seg[-1] - lower) / width if width > 0 else None
    sd = math.sqrt(sum((v - mean) ** 2 for v in seg) / n)
    tnr = abs(seg[-1] - seg[0]) / sd if sd > 0 else None
    return {
        "slope": round(slope, 6),
        "intercept": round(intercept, 6),
        "r2": round(r2, 6),
        "slope_pct": None if sp is None else round(sp, 6),
        "trend_quality": round(quality, 6),
        "channel_mid": round(mid, 6),
        "channel_upper": round(upper, 6),
        "channel_lower": round(lower, 6),
        "channel_position": None if position is None else round(position, 6),
        "residual_sd": round(resid_sd, 6),
        "trend_to_noise": None if tnr is None else round(tnr, 6),
        "n": n,
        _REASON: None,
    }


# ---------------------------------------------------------------------------
# 2. Moving-average depth (library §2, §4, §5, §6; TECH-8/TECH-17)
# ---------------------------------------------------------------------------


def moving_average_depth(
    closes: list,
    *,
    wma_n: int = 20,
    hma_n: int = 20,
    ema_n: int = 20,
    ema_k: int = 5,
    cross_fast: int = 50,
    cross_slow: int = 200,
    cross_k: int = 5,
) -> dict:
    """WMA / HMA / EMA slope / MA-crossover spread and velocity (one window).

    ``wma`` and ``hma`` are the library's §2 weighted and Hull averages at the
    last bar; ``ema_slope`` is the §4 ``(EMA_t - EMA_(t-k)) / EMA_(t-k)``;
    ``cross_spread`` is §5's ``(MA_fast - MA_slow) / MA_slow`` and
    ``cross_velocity`` its ``cross_k``-bar change; ``golden_cross`` is
    ``MA_fast > MA_slow``.

    Returns ``{wma, hma, ema_slope, cross_spread, cross_velocity, golden_cross,
    n, unavailable}``. Refused (all ``None`` + the reason) when the series is
    shorter than the longest leg needs - the family is reported over ONE window
    so its parts cannot describe different series.
    """
    keys = ("wma", "hma", "ema_slope", "cross_spread", "cross_velocity", "golden_cross")
    vals = _finite(closes)
    sqrt_n = max(1, int(round(math.sqrt(hma_n)))) if hma_n >= 2 else 1
    need = max(
        wma_n,
        (hma_n + sqrt_n - 1) if hma_n >= 2 else 1,
        ema_n + ema_k,
        cross_slow + cross_k,
    )
    if len(vals) < need:
        return _refused(
            keys, f"need >= {need} closes for the longest leg, got {len(vals)}",
            len(vals),
        )
    n = len(vals)
    wma = _wma_last(vals, wma_n)
    hma = _hma_last(vals, hma_n)

    ema = [v for v in _ema_series(vals, ema_n) if v is not None]
    ema_slope = None
    if len(ema) >= ema_k + 1 and ema[-1 - ema_k] != 0:
        ema_slope = (ema[-1] - ema[-1 - ema_k]) / ema[-1 - ema_k]

    fast = _sma_series(vals, cross_fast)
    slow = _sma_series(vals, cross_slow)
    cross_spread = None
    cross_velocity = None
    golden = None
    if fast[-1] is not None and slow[-1] is not None and slow[-1] != 0:
        golden = bool(fast[-1] > slow[-1])
        cross_spread = (fast[-1] - slow[-1]) / slow[-1]
        if fast[-1 - cross_k] is not None and slow[-1 - cross_k] not in (None, 0):
            past = (fast[-1 - cross_k] - slow[-1 - cross_k]) / slow[-1 - cross_k]
            cross_velocity = cross_spread - past
    return {
        "wma": None if wma is None else round(wma, 6),
        "hma": None if hma is None else round(hma, 6),
        "ema_slope": None if ema_slope is None else round(ema_slope, 6),
        "cross_spread": None if cross_spread is None else round(cross_spread, 6),
        "cross_velocity": None if cross_velocity is None else round(cross_velocity, 6),
        "golden_cross": golden,
        "n": n,
        _REASON: None,
    }


def ema_stack(closes: list, atr_value: float | None, *, fast: int = 5, slow: int = 20) -> dict:
    """EMA-fast vs EMA-slow spread normalised by ATR (library §6).

    ``stack = (EMA_fast - EMA_slow) / atr_value``. Returns
    ``{stack, ema_fast, ema_slow, n, unavailable}``. Refused when the series is
    shorter than ``slow`` or ``atr_value`` is missing / non-positive - a stack
    without volatility is not a normalised read.
    """
    keys = ("stack", "ema_fast", "ema_slow")
    vals = _finite(closes)
    if len(vals) < max(fast, slow) or fast <= 0 or slow <= 0:
        return _refused(
            keys, f"need >= {max(fast, slow)} closes, got {len(vals)}", len(vals)
        )
    if atr_value is None or not math.isfinite(float(atr_value)) or float(atr_value) <= 0:
        return _refused(keys, "atr_value missing or non-positive", len(vals))
    ef = [v for v in _ema_series(vals, fast) if v is not None][-1]
    es = [v for v in _ema_series(vals, slow) if v is not None][-1]
    stack = (ef - es) / float(atr_value)
    return {
        "stack": round(stack, 6),
        "ema_fast": round(ef, 6),
        "ema_slow": round(es, 6),
        "n": len(vals),
        _REASON: None,
    }


# ---------------------------------------------------------------------------
# 3. Candle / gap depth (library §65, §66, §68, §69; TECH-18)
# ---------------------------------------------------------------------------


def candle_strength(opens: list, highs: list, lows: list, closes: list) -> dict:
    """Last-bar intraday strength and close location (library §65, §66).

    ``intraday_strength = (C - L) / (H - L)`` (§66, 0 at the low, 1 at the
    high), ``close_location = ((C-L) - (H-C)) / (H-L)`` (§65, -1..1) and
    ``body_pct = |C - O| / (H - L)`` (§64). Returns
    ``{intraday_strength, close_location, body_pct, range, close, n,
    unavailable}``. Refused when any series is empty or the last bar has no
    range (``H == L``, a ratio with no denominator).
    """
    keys = ("intraday_strength", "close_location", "body_pct", "range", "close")
    if not opens or not highs or not lows or not closes:
        return _refused(keys, "open/high/low/close series required")
    o, h, lo, c = (float(opens[-1]), float(highs[-1]), float(lows[-1]), float(closes[-1]))
    if not all(math.isfinite(v) for v in (o, h, lo, c)):
        return _refused(keys, "last bar carries a non-finite OHLC value", len(closes))
    rng = h - lo
    if rng <= 0:
        return _refused(keys, "zero range on the last bar (H == L)", len(closes))
    return {
        "intraday_strength": round((c - lo) / rng, 6),
        "close_location": round(((c - lo) - (h - c)) / rng, 6),
        "body_pct": round(abs(c - o) / rng, 6),
        "range": round(rng, 6),
        "close": round(c, 6),
        "n": len(closes),
        _REASON: None,
    }


def gap_depth(closes: list, opens: list, highs: list, lows: list) -> dict:
    """Last-bar overnight gap: continuation sign and continuous fill (§68/§69).

    ``gap_pct = (O_t - C_(t-1)) / C_(t-1)``; ``continuation`` is §68's
    ``Sign(gap) * Sign(C_t - O_t)`` (+1 gap-and-follow-through, -1 reversal);
    ``fill_fraction`` is the §69 formula as a CONTINUOUS 0..1 read (the share
    of the gap price retraced on the gap bar), with ``filled`` the binary
    ``>= 1``. Returns ``{type, gap_pct, continuation, fill_fraction, filled, n,
    unavailable}``. ``type`` is ``up``/``down``/``flat``; refused below two
    closes, on a zero prior close, or at a zero-size gap.
    """
    keys = ("type", "gap_pct", "continuation", "fill_fraction", "filled")
    if len(closes) < 2 or not opens or not highs or not lows:
        return _refused(
            keys, "need >= 2 closes and aligned open/high/low series", len(closes)
        )
    prev_close = float(closes[-2])
    o, h, lo, c = (float(opens[-1]), float(highs[-1]), float(lows[-1]), float(closes[-1]))
    if prev_close <= 0:
        return _refused(keys, "prior close is non-positive", len(closes))
    gap = (o - prev_close) / prev_close
    if gap == 0:
        return _refused(keys, "zero-size gap: no gap to continue or fill", len(closes))
    continuation = (1 if gap > 0 else -1) * (1 if c > o else -1 if c < o else 0)
    if gap > 0:
        size = o - prev_close
        frac = (prev_close - lo) / size
        gtype = "up"
    else:
        size = prev_close - o
        frac = (h - prev_close) / size
        gtype = "down"
    frac = max(0.0, min(1.0, frac))
    return {
        "type": gtype,
        "gap_pct": round(gap, 6),
        "continuation": continuation,
        "fill_fraction": round(frac, 6),
        "filled": bool(frac >= 1.0),
        "n": len(closes),
        _REASON: None,
    }


# ---------------------------------------------------------------------------
# 4. Breadth thrust over an adv/dec series (library §120; TECH-14)
# ---------------------------------------------------------------------------


def zweig_breadth_thrust(
    advancers: list,
    decliners: list,
    *,
    ema_len: int = 10,
    window: int = 10,
    decline_threshold: float = 0.40,
    rise_threshold: float = 0.615,
) -> dict:
    """Zweig breadth thrust from an advancers/decliners SERIES (library §120).

    Takes the two series (no fetch). Daily ratio ``adv / (adv + dec)``, its
    ``ema_len``-period EMA, and the Zweig event: the EMA rose from below
    ``decline_threshold`` to above ``rise_threshold`` within ``window`` bars.
    Returns ``{ratio, ema, ema_change, signal, n, unavailable}`` - ``ratio`` and
    ``ema`` are the latest values, ``ema_change`` the ``window``-bar change and
    ``signal`` the boolean event. Refused (all ``None`` + the reason) below
    ``ema_len + window`` aligned finite observations, or when too few days carry
    a positive ``adv + dec`` total.
    """
    keys = ("ratio", "ema", "ema_change", "signal")
    a = _finite(advancers)
    d = _finite(decliners)
    m = min(len(a), len(d)) if (a and d) else 0
    if m < ema_len + window:
        return _refused(
            keys,
            f"need >= {ema_len + window} aligned adv/dec observations, got {m}",
            m,
        )
    a, d = a[-m:], d[-m:]
    ratios = [x / (x + y) for x, y in zip(a, d, strict=True) if (x + y) > 0]
    if len(ratios) < ema_len + window:
        return _refused(keys, "too few days with a positive adv+dec total", len(ratios))
    ema = [v for v in _ema_series(ratios, ema_len) if v is not None]
    if len(ema) < window + 1:
        return _refused(keys, "EMA history too short for the thrust window", len(ema))
    latest = ema[-1]
    window_min = min(ema[-(window + 1):])
    signal = bool(latest > rise_threshold and window_min < decline_threshold)
    return {
        "ratio": round(ratios[-1], 6),
        "ema": round(latest, 6),
        "ema_change": round(latest - ema[-1 - window], 6),
        "signal": signal,
        "n": len(ratios),
        _REASON: None,
    }


def adv_participation(volumes: list, *, window: int = 21) -> dict:
    """Per-name participation: today's volume vs the name's own ADV (§1 Breadth).

    ``adv`` is the mean of the ``window`` volumes ENDING BEFORE the last bar
    (the trailing average daily volume), and ``participation`` is the latest
    volume over it (1.0 = an average day). Returns
    ``{adv, latest_volume, participation, window, n, unavailable}``. Refused
    when fewer than ``window + 1`` volumes are present or the ADV is
    non-positive.
    """
    keys = ("adv", "latest_volume", "participation", "window")
    vals = _finite(volumes)
    if window < 1 or len(vals) < window + 1:
        return _refused(
            keys, f"need >= {window + 1} volumes (window + today), got {len(vals)}",
            len(vals),
        )
    hist = vals[-window - 1 : -1]
    adv = sum(hist) / len(hist)
    if adv <= 0:
        return _refused(keys, "ADV is non-positive", len(vals))
    return {
        "adv": round(adv, 4),
        "latest_volume": round(vals[-1], 4),
        "participation": round(vals[-1] / adv, 6),
        "window": int(window),
        "n": len(vals),
        _REASON: None,
    }


# ---------------------------------------------------------------------------
# 5. Legacy oscillators - one pure def each (library §62, §113-§117; TECH-21)
# ---------------------------------------------------------------------------


def dpo(closes: list, n: int = 20, *, shift: int | None = None) -> dict:
    """Detrended Price Oscillator ``C_(t-shift) - SMA(C, n)`` (library §113).

    ``shift`` is the traditional centring offset; ``None`` selects ``n//2 + 1``
    (the library notes the shift "depends on implementation"). Returns
    ``{dpo, price, sma, shift, n, unavailable}``; refused below ``n`` closes or
    when the shifted bar does not exist.
    """
    keys = ("dpo", "price", "sma", "shift")
    vals = _finite(closes)
    if n < 2 or len(vals) < n:
        return _refused(keys, f"need >= {n} closes, got {len(vals)}", len(vals))
    off = (n // 2 + 1) if shift is None else max(0, int(shift))
    if off >= len(vals):
        return _refused(keys, f"shift {off} reaches before the series", len(vals))
    sma = sum(vals[-n:]) / n
    price = vals[-1 - off]
    return {
        "dpo": round(price - sma, 6),
        "price": round(price, 6),
        "sma": round(sma, 6),
        "shift": off,
        "n": len(vals),
        _REASON: None,
    }


def ultimate_oscillator(
    closes: list, highs: list, lows: list, *, p1: int = 7, p2: int = 14, p3: int = 28
) -> dict:
    """Ultimate Oscillator over three lookbacks (library §114).

    ``BP = C - min(L, C_prev)``, ``TR = max(H, C_prev) - min(L, C_prev)``;
    ``UO = 100 * (4*Avg_p1(BP/TR) + 2*Avg_p2 + Avg_p3) / 7`` (sum-of-BP over
    sum-of-TR per window). Returns ``{uo, avg7, avg14, avg28, n, unavailable}``;
    refused below ``p3 + 1`` aligned bars.
    """
    keys = ("uo", "avg7", "avg14", "avg28")
    c = _finite(closes)
    h = _finite(highs)
    lo = _finite(lows)
    m = min(len(c), len(h), len(lo)) if (c and h and lo) else 0
    if m < p3 + 1:
        return _refused(keys, f"need >= {p3 + 1} aligned bars, got {m}", m)
    c, h, lo = c[-m:], h[-m:], lo[-m:]
    bp: list[float] = []
    tr: list[float] = []
    for i in range(1, m):
        cp = c[i - 1]
        bp.append(c[i] - min(lo[i], cp))
        tr.append(max(h[i], cp) - min(lo[i], cp))
    avgs = []
    for p in (p1, p2, p3):
        sum_tr = sum(tr[-p:])
        avgs.append(sum(bp[-p:]) / sum_tr if sum_tr > 0 else None)
    if any(a is None for a in avgs):
        return _refused(keys, "a window has zero true range", m)
    uo = 100.0 * (4.0 * avgs[0] + 2.0 * avgs[1] + avgs[2]) / 7.0
    return {
        "uo": round(uo, 6),
        "avg7": round(avgs[0], 6),
        "avg14": round(avgs[1], 6),
        "avg28": round(avgs[2], 6),
        "n": m,
        _REASON: None,
    }


def awesome_oscillator(highs: list, lows: list, *, fast: int = 5, slow: int = 34) -> dict:
    """Awesome Oscillator ``SMA_fast(median) - SMA_slow(median)`` (library §115).

    Median price is ``(H + L) / 2``. Returns ``{ao, fast_sma, slow_sma, n,
    unavailable}``; refused below ``slow`` aligned bars.
    """
    keys = ("ao", "fast_sma", "slow_sma")
    h = _finite(highs)
    lo = _finite(lows)
    m = min(len(h), len(lo)) if (h and lo) else 0
    if m < max(fast, slow):
        return _refused(keys, f"need >= {max(fast, slow)} bars, got {m}", m)
    h, lo = h[-m:], lo[-m:]
    median = [(a + b) / 2.0 for a, b in zip(h, lo, strict=True)]
    fs = sum(median[-fast:]) / fast
    ss = sum(median[-slow:]) / slow
    return {
        "ao": round(fs - ss, 6),
        "fast_sma": round(fs, 6),
        "slow_sma": round(ss, 6),
        "n": m,
        _REASON: None,
    }


def relative_vigor_index(
    opens: list, highs: list, lows: list, closes: list, *, n: int = 10, signal: int = 4
) -> dict:
    """Relative Vigor Index + its signal line (library §116).

    ``RVI = SMA(C - O, n) / SMA(H - L, n)``, ``signal = SMA(RVI, 4)``. Returns
    ``{rvi, signal, n, unavailable}``; refused below ``n + signal - 1`` aligned
    bars or when a denominator window is zero.
    """
    keys = ("rvi", "signal")
    o = _finite(opens)
    h = _finite(highs)
    lo = _finite(lows)
    c = _finite(closes)
    m = min(len(o), len(h), len(lo), len(c)) if (o and h and lo and c) else 0
    if m < n + signal - 1:
        return _refused(keys, f"need >= {n + signal - 1} bars, got {m}", m)
    o, h, lo, c = o[-m:], h[-m:], lo[-m:], c[-m:]
    num = _sma_series([cj - oj for oj, cj in zip(o, c, strict=True)], n)
    den = _sma_series([hj - lj for hj, lj in zip(h, lo, strict=True)], n)
    rvi_series = [
        num[i] / den[i]
        for i in range(m)
        if num[i] is not None and den[i] not in (None, 0)
    ]
    if len(rvi_series) < signal:
        return _refused(keys, "RVI history too short for the signal line", len(rvi_series))
    return {
        "rvi": round(rvi_series[-1], 6),
        "signal": round(sum(rvi_series[-signal:]) / signal, 6),
        "n": m,
        _REASON: None,
    }


def coppock_curve(
    closes: list, *, roc_long: int = 14, roc_short: int = 11, wma_n: int = 10
) -> dict:
    """Coppock Curve ``WMA_wma_n(ROC_roc_long + ROC_roc_short)`` (library §117).

    ROC is in PERCENT (the library's §1 form). Returns ``{coppock, roc_sum, n,
    unavailable}`` where ``roc_sum`` is the latest summed ROC; refused below
    ``roc_long + wma_n`` closes or on a non-positive price in the window.
    """
    keys = ("coppock", "roc_sum")
    vals = _finite(closes)
    if roc_long < 1 or roc_short < 1:
        return _refused(keys, "roc_long / roc_short must be positive", len(vals))
    if len(vals) < roc_long + wma_n:
        return _refused(
            keys,
            f"need >= {roc_long + wma_n} closes, got {len(vals)}",
            len(vals),
        )
    combined: list[float] = []
    start = max(roc_long, roc_short)
    for i in range(start, len(vals)):
        base_l, base_s = vals[i - roc_long], vals[i - roc_short]
        if base_l <= 0 or base_s <= 0:
            continue
        combined.append((vals[i] / base_l - 1.0) * 100.0 + (vals[i] / base_s - 1.0) * 100.0)
    if len(combined) < wma_n:
        return _refused(keys, "too few summed-ROC observations for the WMA", len(combined))
    wma = _wma_last(combined, wma_n)
    return {
        "coppock": None if wma is None else round(wma, 6),
        "roc_sum": round(combined[-1], 6),
        "n": len(vals),
        _REASON: None if wma is not None else "WMA over the summed ROC is undefined",
    }


def ease_of_movement(highs: list, lows: list, volumes: list, *, n: int = 14) -> dict:
    """Ease of Movement, per-bar and its ``n``-bar average (library §62).

    ``EMV = ((H+L)/2 - (H_prev+L_prev)/2) / (V / (H - L))``. Bars with a zero
    range or zero volume are skipped. Returns ``{emv, emv_avg, n, unavailable}``
    where ``emv`` is the last available bar and ``emv_avg`` its ``n``-period
    mean; refused when fewer than ``n + 1`` aligned bars or fewer than ``n``
    usable EMV readings.
    """
    keys = ("emv", "emv_avg")
    h = _finite(highs)
    lo = _finite(lows)
    v = _finite(volumes)
    m = min(len(h), len(lo), len(v)) if (h and lo and v) else 0
    if m < n + 1:
        return _refused(keys, f"need >= {n + 1} aligned bars, got {m}", m)
    h, lo, v = h[-m:], lo[-m:], v[-m:]
    series: list[float] = []
    for i in range(1, m):
        mid = (h[i] + lo[i]) / 2.0 - (h[i - 1] + lo[i - 1]) / 2.0
        rng = h[i] - lo[i]
        if rng <= 0 or v[i] <= 0:
            continue
        series.append(mid / (v[i] / rng))
    if len(series) < n:
        return _refused(keys, "too few usable EOM readings", len(series))
    return {
        "emv": round(series[-1], 8),
        "emv_avg": round(sum(series[-n:]) / n, 8),
        "n": m,
        _REASON: None,
    }
