"""Extended technical indicators + candlestick patterns (pure, offline).

Complements ``technical_factors.py`` with the trend/momentum/volume group from
the standard indicator set that the project did not yet compute locally:

  Trend        - ichimoku cloud, golden/death cross
  Momentum     - cci, roc, momentum_oscillator, trix, force_index
  Volume       - accumulation_distribution (A/D line), vpt, chaikin_money_flow,
                 anchored_vwap
  Structure    - candlestick pattern scanner (doji, hammer, shootng star,
                 engulfing, morning/evening star)

Every function is pure and returns None / explicit-flag dicts on missing or
invalid input (the no-fabrication rule). No network, no state. They consume
the same OHLCV arrays (closes/highs/lows/volumes/opens) the existing
``technical_factors`` functions take, so they slot into the existing analyst
tools unchanged.
"""

from __future__ import annotations

from datetime import datetime

from .technical_factors import ema


def _sma(series: list, n: int) -> list:
    out = [None] * (n - 1)
    for i in range(n - 1, len(series)):
        out.append(sum(series[i - n + 1 : i + 1]) / n)
    return out


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _last(series):
    for v in reversed(series):
        if v is not None:
            return v
    return None


def _min_n(highs, lows, closes, n: int) -> bool:
    return (
        highs is not None and lows is not None and closes is not None
        and len(highs) >= n and len(lows) >= n and len(closes) >= n
    )


def golden_death_cross(closes, fast: int = 50, slow: int = 200) -> dict:
    """Golden / death cross label from the fast-vs-slow SMA stack.

    golden = fast SMA crossed above slow SMA recently (a golden cross);
    death = the reverse. None when history too short. Purely descriptive.
    """
    if not closes or len(closes) < slow + 5:
        return {"golden": None, "death": None, "label": None}
    f = _sma(closes, fast)
    s = _sma(closes, slow)
    pf, ps, cf, cs = f[-2], s[-2], f[-1], s[-1]
    if None in (pf, ps, cf, cs):
        return {"golden": None, "death": None, "label": None}
    label = None
    if cf > cs and pf <= ps:
        label = "golden"
    elif cf < cs and pf >= ps:
        label = "death"
    return {
        "golden": bool(label == "golden"),
        "death": bool(label == "death"),
        "label": label,
    }


def ichimoku(highs, lows, closes, conv: int = 9, base: int = 26,
             span_b: int = 52, displace: int = 26) -> dict:
    """Ichimoku Cloud (standard 9/26/52).

    Returns conversion/base lines, the leading spans A/B (cloud), the current
    close position vs the cloud, and the cloud shelf (current + displaced
    bracket) used as forward support/resistance. None when history insufficient.
    """
    if not _min_n(highs, lows, closes, max(span_b, conv, base)):
        return dict.fromkeys(("conversion", "base", "span_a", "span_b", "above_cloud", "cloud_leading", "label"))
    n = len(closes)
    # Keep the int window inputs in non-shadowed locals: the computed values
    # below reuse them as lookback widths, so they must never be overwritten.
    conv_win, base_win, spanb_win, disp = conv, base, span_b, displace

    def _range_mid(k, i):
        seg = range(i - k + 1, i + 1)
        hh = max((_f(highs[j]) for j in seg if _f(highs[j]) is not None), default=None)
        ll = min((_f(lows[j]) for j in seg if _f(lows[j]) is not None), default=None)
        return (hh + ll) / 2.0 if (hh is not None and ll is not None) else None

    i_last = n - 1
    conversion = _range_mid(conv_win, i_last)
    base_line = _range_mid(base_win, i_last)
    # Past cloud: span A = (conv+base)/2 of displace periods ago; span B =
    # 52-period midpoint displace periods ago.
    past_conv = _range_mid(conv_win, i_last - disp)
    past_base = _range_mid(base_win, i_last - disp)
    span_a = (past_conv + past_base) / 2.0 if (past_conv is not None and past_base is not None) else None
    span_b = _range_mid(spanb_win, i_last - disp)
    close = _f(closes[-1])

    above_cloud = None
    if span_a is not None and span_b is not None and close is not None:
        cloud_hi = max(span_a, span_b)
        above_cloud = close > cloud_hi
    label = "above" if above_cloud else ("below" if above_cloud is False else None)
    return {
        "conversion": conversion,
        "base": base_line,
        "span_a": span_a,
        "span_b": span_b,
        "above_cloud": above_cloud,
        "cloud_leading": (span_a, span_b) if (span_a is not None and span_b is not None) else None,
        "label": label,
    }


def cci(highs, lows, closes, n: int = 20, constant: float = 0.015) -> float | None:
    """Commodity Channel Index.

    CCI = (TP - SMA(TP)) / (constant x mean-dev). Above +100 / below -100 are
    the conventional watch levels. None when history insufficient.
    """
    if not _min_n(highs, lows, closes, n):
        return None
    tp = [(_f(highs[i]) + _f(lows[i]) + _f(closes[i])) / 3.0 for i in range(len(closes))]
    tp = [x for x in tp if x is not None]
    if len(tp) < n:
        return None
    last = tp[-1]
    m = _sma(tp, n)
    m_last = m[-1]
    if m_last is None:
        return None
    dev = sum(abs(x - m_last) for x in tp[-n:]) / n
    if dev == 0:
        return None
    return round((last - m_last) / (constant * dev), 2)


def roc(closes, n: int = 12) -> float | None:
    """Rate of change: (close_n - close_{n}) / close_{n} x 100."""
    if not closes or len(closes) < n + 1:
        return None
    prev = _f(closes[-(n + 1)])
    cur = _f(closes[-1])
    if prev is None or cur is None or prev == 0:
        return None
    return round((cur - prev) / prev * 100.0, 2)


def momentum_oscillator(closes, n: int = 10) -> float | None:
    """Momentum oscillator: current close minus the close n periods ago."""
    if not closes or len(closes) < n + 1:
        return None
    prev = _f(closes[-(n + 1)])
    cur = _f(closes[-1])
    if prev is None or cur is None:
        return None
    return round(cur - prev, 4)


def trix(closes, n: int = 15, signal: int = 9) -> dict:
    """TRIX: one-period ROC of a triple-smoothed EMA.

    Reports the TRIX line + a 1-period signal (on the triple-EMA) and the
    crossover direction. None when history insufficient.
    """
    if not closes or len(closes) < n * 2 + signal + 5:
        return {"trix": None, "signal": None, "cross": None}
    f = [_f(x) for x in closes]
    if any(x is None for x in f):
        return {"trix": None, "signal": None, "cross": None}
    e1 = ema(f, n)
    e2 = ema([x for x in e1 if x is not None], n)
    e3 = ema([x for x in e2 if x is not None], n)
    e3 = [x for x in e3 if x is not None]
    if len(e3) < signal + 2:
        return {"trix": None, "signal": None, "cross": None}
    trix_vals = []
    for i in range(1, len(e3)):
        prev = e3[i - 1]
        cur = e3[i]
        trix_vals.append(((cur - prev) / prev * 100.0) if (prev and cur) else None)
    sig = _sma(trix_vals, signal)
    cur = trix_vals[-1]
    s = sig[-1]
    cross = None
    if len(trix_vals) >= 2 and sig[-2] is not None:
        cross = bool(cur > s and trix_vals[-2] <= sig[-2])
    return {"trix": round(cur, 6) if cur is not None else None,
            "signal": round(s, 6) if s is not None else None,
            "cross": cross}


def force_index(closes, volumes, n: int = 13) -> float | None:
    """Force Index: volume x (close - close_prev), EMA-smoothed over n."""
    if not closes or not volumes or len(closes) < n + 1 or len(volumes) < n + 1:
        return None
    diffs = []
    for i in range(1, len(closes)):
        c_prev = _f(closes[i - 1])
        c = _f(closes[i])
        v = _f(volumes[i])
        if c_prev is not None and c is not None and v is not None:
            diffs.append((c - c_prev) * v)
    if len(diffs) < n:
        return None
    e = ema(diffs, min(n, len(diffs)))
    e = [x for x in e if x is not None]
    return round(e[-1], 2) if e else None


def accumulation_distribution(highs, lows, closes, volumes) -> float | None:
    """Accumulation/Distribution line value (one-day ~ cumulative).

    CLV = ((C - L) - (H - C)) / (H - L); A/D += CLV x Volume. Returns the
    latest normalized A/D reading (the running sum's latest step). None when
    H == L for every bar or history too short.
    """
    if not _min_n(highs, lows, closes, 2) or not volumes or len(volumes) < 2:
        return None
    total = 0.0
    for i in range(len(closes)):
        h = _f(highs[i])
        lo = _f(lows[i])
        c = _f(closes[i])
        v = _f(volumes[i])
        if None in (h, lo, c, v):
            continue
        if h - lo == 0:
            continue
        clv = ((c - lo) - (h - c)) / (h - lo)
        total += clv * v
    return round(total, 2) if total else None


def vpt(closes, volumes) -> float | None:
    """Volume Price Trend: running sum of volume x percentage price change."""
    if not closes or not volumes or len(closes) < 2:
        return None
    total = 0.0
    for i in range(1, len(closes)):
        prev = _f(closes[i - 1])
        cur = _f(closes[i])
        v = _f(volumes[i])
        if prev is None or cur is None or v is None or prev == 0:
            continue
        total += v * ((cur - prev) / prev)
    return round(total, 2)


def chaikin_money_flow(highs, lows, closes, volumes, n: int = 20) -> float | None:
    """Chaikin Money Flow: sum(CLV x volume) / sum(volume) over n periods.

    > 0.1 buying pressure (accumulation), < -0.1 selling pressure.
    """
    if not _min_n(highs, lows, closes, n) or not volumes or len(volumes) < n:
        return None
    mfv = 0.0
    vol = 0.0
    for i in range(len(closes) - n, len(closes)):
        h = _f(highs[i])
        lo = _f(lows[i])
        c = _f(closes[i])
        v = _f(volumes[i])
        if None in (h, lo, c, v):
            return None
        if h - lo == 0:
            return None
        clv = ((c - lo) - (h - c)) / (h - lo)
        mfv += clv * v
        vol += v
    if vol == 0:
        return None
    return round(mfv / vol, 4)


def anchored_vwap(closes, volumes, anchor_price: float | None = None) -> float | None:
    """Anchored VWAP: cumulative (typical price x volume) / cumulative volume
    from an event anchor price (e.g. earnings gap / breakout). When
    ``anchor_price`` is None, anchors at the first bar (plain cumulative VWAP).
    """
    if not closes or not volumes:
        return None
    num = 0.0
    den = 0.0
    started = anchor_price is None
    for i in range(len(closes)):
        c = _f(closes[i])
        v = _f(volumes[i])
        if c is None or v is None:
            continue
        if anchor_price is not None and not started:
            if c >= anchor_price:
                started = True
            else:
                continue
        num += c * v
        den += v
    if den == 0:
        return None
    return round(num / den, 4)


# ---------------------------------------------------------------------------
# Event-anchored AVWAP levels (the anchor an analyst names, not the plain line)
# ---------------------------------------------------------------------------


def swing_pivots(highs, lows, *, left: int = 5, right: int = 5) -> dict:
    """The most recent CONFIRMED swing pivot indices (fractal low and high).

    A pivot low at ``i`` needs its low strictly below the ``left`` bars before
    it and the ``right`` bars after it. The confirmation window is the point:
    the newest ``right`` bars can never be a pivot, because a low that can still
    be undercut is not a swing. Ties do not qualify - a flat shelf is not a
    pivot.

    Returns ``{"low", "high", "left", "right"}``, ``None`` where the series
    holds no pivot of that kind.
    """
    h = [_f(x) for x in (highs or [])]
    lo = [_f(x) for x in (lows or [])]
    n = min(len(h), len(lo))
    lw, rw = int(left), int(right)
    out: dict = {"low": None, "high": None, "left": lw, "right": rw}
    if lw < 1 or rw < 1 or n < lw + rw + 1:
        return out
    for i in range(n - rw - 1, lw - 1, -1):
        lows_w = lo[i - lw : i + rw + 1]
        highs_w = h[i - lw : i + rw + 1]
        if (
            out["low"] is None
            and None not in lows_w
            and lo[i] == min(lows_w)
            and lows_w.count(lo[i]) == 1
        ):
            out["low"] = i
        if (
            out["high"] is None
            and None not in highs_w
            and h[i] == max(highs_w)
            and highs_w.count(h[i]) == 1
        ):
            out["high"] = i
        if out["low"] is not None and out["high"] is not None:
            break
    return out


def date_anchor_index(dates, event_date) -> int | None:
    """The bar index an event anchors: the FIRST session at or after it, or None.

    The anchor is where the move the event caused begins. An event on a session
    anchors that session (the reaction is intraday); an event on a non-session -
    a Saturday statement, a holiday - anchors the next session, which is the
    first bar that can contain the reaction.

    None when the event falls after the last session: a future event has no bar
    to anchor, and anchoring the last bar would invent one. None for an
    unparseable date or a series with no usable dates - never bar 0 by default.

    The date is PARSED, not length-checked: ``"not-a-date"`` is ten characters
    and would string-compare against every ISO date without ever failing.
    """
    try:
        want = datetime.strptime(str(event_date or "")[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    for i, d in enumerate(dates or []):
        try:
            when = datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if when >= want:
            return i
    return None


def anchored_vwap_levels(
    closes,
    highs,
    lows,
    volumes,
    *,
    dates=None,
    event_dates=None,
    left: int = 5,
    right: int = 5,
    volume_multiple: float = 1.5,
) -> dict | None:
    """Anchored VWAP from several event anchors, each measured against the last close.

    ``anchored_vwap`` answers one question - the cumulative VWAP from a price
    level. This answers the one an analyst actually asks: from WHICH anchor, and
    has price lost it. Each anchor is located as a bar INDEX and the level is
    computed by the existing ``anchored_vwap`` over the slice from that bar, so
    there is one implementation of the arithmetic (master rule 15) and the two
    cannot disagree.

    Anchors reported, in order:

    * ``swing_low`` / ``swing_high`` - the most recent confirmed fractal pivot
      (``swing_pivots``). The low is the start of the current rally, so losing
      its VWAP is the classic "the buyers who started this are underwater" read.
    * ``opex_monthly`` / ``opex_quarterly`` - the most recent monthly (third
      Friday) and quarterly (Mar/Jun/Sep/Dec) expiries, taken from
      ``derivatives_gamma.opex_dates`` - the repo's one OPEX calendar, not a
      second third-Friday calculation.
    * any ``event_dates`` the CALLER supplies, e.g. ``{"fomc": "2026-09-16"}``.
      FOMC and earnings dates come from a calendar, so they are taken as input
      and never inferred from the bars.

    The date-anchored levels need ``dates`` (the session axis). Without it they
    are reported as a named gap rather than anchored at bar 0.

    Returns ``{"levels", "last_close", "shift", "basis"}``, or None with fewer
    than 2 bars. Every attempted anchor gets a row: a value, or ``None`` with
    the reason. ``shift`` is the read the anchors exist for - price below the
    swing-low VWAP on expanding volume - and it is ``None`` when no swing low
    was found, never ``False`` on an unmeasured axis.
    """
    cs = [_f(x) for x in (closes or [])]
    vs = [_f(x) for x in (volumes or [])]
    n = min(len(cs), len(vs))
    if n < 2 or cs[n - 1] is None:
        return None
    last = cs[n - 1]
    ds = [str(d)[:10] for d in (dates or [])]
    levels: dict = {}
    notes: list[str] = []

    def _add(name: str, idx: int | None, why: str) -> None:
        if idx is None or not 0 <= idx < n:
            levels[name] = {
                "index": None, "date": None, "vwap": None,
                "above": None, "distance_pct": None, "reason": why,
            }
            return
        vwap = anchored_vwap(cs[idx:n], vs[idx:n])
        if vwap is None:
            levels[name] = {
                "index": idx, "date": None, "vwap": None,
                "above": None, "distance_pct": None,
                "reason": "no usable bar after the anchor",
            }
            return
        levels[name] = {
            "index": idx,
            "date": ds[idx] if idx < len(ds) else None,
            "vwap": vwap,
            "above": bool(last > vwap),
            "distance_pct": round((last / vwap - 1.0) * 100.0, 3) if vwap else None,
        }

    piv = swing_pivots(highs, lows, left=left, right=right)
    _add("swing_low", piv["low"], f"no confirmed {left}/{right} pivot low in this series")
    _add("swing_high", piv["high"], f"no confirmed {left}/{right} pivot high in this series")

    if ds:
        last_day = ds[n - 1] if n - 1 < len(ds) else ""
        try:
            from .derivatives_gamma import opex_dates

            years = {int(last_day[:4]), int(last_day[:4]) - 1} if len(last_day) == 10 else set()
            monthly = sorted(
                d.isoformat()
                for y in sorted(years)
                for d in opex_dates(y)
                if d.isoformat() <= last_day
            )
            if monthly:
                _add("opex_monthly", date_anchor_index(ds, monthly[-1]),
                     "no monthly expiry at or before this series")
                quarterly = [d for d in monthly if int(d[5:7]) in (3, 6, 9, 12)]
                if quarterly:
                    _add("opex_quarterly", date_anchor_index(ds, quarterly[-1]),
                         "no quarterly expiry at or before this series")
            else:
                notes.append("no OPEX date falls inside this series")
        except Exception:  # noqa: BLE001 - the calendar is optional
            notes.append("OPEX calendar unavailable")
    else:
        notes.append(
            "no session dates supplied, so the OPEX and caller event anchors are omitted"
        )

    for name, when in sorted((event_dates or {}).items()):
        _add(str(name), date_anchor_index(ds, when),
             f"event date {when!r} is outside this series")

    shift = None
    low = levels.get("swing_low") or {}
    if low.get("vwap") is not None:
        idx = int(low["index"])
        vols = [v for v in vs[idx:] if v is not None]
        avg = (sum(vols) / len(vols)) if vols else None
        last_vol = vs[n - 1]
        ratio = round(last_vol / avg, 3) if (avg and last_vol is not None) else None
        lost = bool(last < low["vwap"])
        expanding = ratio is not None and ratio >= float(volume_multiple)
        shift = {
            "lost_swing_low_vwap": lost,
            "volume_ratio": ratio,
            "volume_multiple": float(volume_multiple),
            "on_expanding_volume": expanding,
            "signal": bool(lost and expanding),
        }

    measured = sum(1 for lv in levels.values() if lv.get("vwap") is not None)
    basis = (
        f"{measured} of {len(levels)} anchor(s) measured over {n} bars; swing "
        f"pivots confirmed {int(left)}/{int(right)}; each level is "
        f"anchored_vwap over the slice from its own bar"
    )
    if notes:
        basis += " | " + "; ".join(notes)
    return {"levels": levels, "last_close": last, "shift": shift, "basis": basis}


# ---------------------------------------------------------------------------
# Candlestick patterns (structure)
# ---------------------------------------------------------------------------


def _body(open_, close):
    return close - open_


def _range_(high, low):
    return high - low


def _doji(o, h, lo, c, tol: float = 0.1) -> bool:
    r = _range_(h, lo)
    return r > 0 and abs(_body(o, c)) / r < tol


def _hammer(o, h, lo, c) -> str | None:
    """Hammer / shooting star share a long shadow; distinguish by close side.
    Returns 'hammer' (lower shadow, body top) or None."""
    r = _range_(h, lo)
    if r <= 0:
        return None
    body = _body(o, c)
    upper = h - max(o, c)
    lower = min(o, c) - lo
    if lower >= 2 * abs(body) and abs(body) > 0 and upper <= abs(body):
        return "hammer"
    return None


def _shoot(o, h, lo, c) -> str | None:
    r = _range_(h, lo)
    if r <= 0:
        return None
    body = _body(o, c)
    upper = h - max(o, c)
    lower = min(o, c) - lo
    if upper >= 2 * abs(body) and abs(body) > 0 and lower <= abs(body):
        return "shooting_star"
    return None


def _stars(opens, closes, highs, lows, i) -> list[str]:
    """Morning/evening star (3-candle). Returns matching pattern names."""
    out = []
    if i < 2 or i >= len(closes):
        return out
    o1, c1 = _f(opens[i - 2]), _f(closes[i - 2])
    o2, c2 = _f(opens[i - 1]), _f(closes[i - 1])
    o3, c3 = _f(opens[i]), _f(closes[i])
    h3 = _f(highs[i])
    lo3 = _f(lows[i])
    if None in (o1, c1, o2, c2, o3, c3, h3, lo3):
        return out
    # Morning star: big down candle, small middle, up close > midpoint.
    if c1 < o1 and _range_(h3, lo3) * 0.5 > 0:
        mid_body = abs(_body(o2, c2))
        big = abs(_body(o1, c1)) > 2 * mid_body and mid_body > 0
        if big and (c3 > o3) and (c3 > (o1 + c1) / 2.0):
            out.append("morning_star")
    # Evening star: mirror.
    if c1 > o1 and _range_(h3, lo3) * 0.5 > 0:
        mid_body = abs(_body(o2, c2))
        big = abs(_body(o1, c1)) > 2 * mid_body and mid_body > 0
        if big and (c3 < o3) and (c3 < (o1 + c1) / 2.0):
            out.append("evening_star")
    return out


def scan_candlesticks(opens, highs, lows, closes, lookback: int = 5) -> dict:
    """Scan the most recent candles for common patterns.

    Returns the latest emerging pattern set (dict of bools) + the raw bar
    stats (open/high/low/close) so the analyst can decide, never fabricate.
    """
    patterns = {
        "doji": None, "hammer": None, "shooting_star": None,
        "bullish_engulfing": None, "bearish_engulfing": None,
        "morning_star": None, "evening_star": None,
    }
    if not opens or not highs or not lows or not closes:
        return {"patterns": patterns, "bars": []}
    n = len(closes)
    m = min(lookback, n)
    bars = []
    for i in range(n - m, n):
        o = _f(opens[i])
        h = _f(highs[i])
        lo = _f(lows[i])
        c = _f(closes[i])
        if None in (o, h, lo, c):
            bars.append({"open": None})
            continue
        bars.append({"open": o, "high": h, "low": lo, "close": c})
        # engulfing needs the prior bar
        if i >= 1:
            po = _f(opens[i - 1])
            pc = _f(closes[i - 1])
            if po is not None and pc is not None:
                if _doji(o, h, lo, c):
                    patterns["doji"] = True
                pat = _hammer(o, h, lo, c)
                if pat:
                    patterns["hammer"] = True
                pat2 = _shoot(o, h, lo, c)
                if pat2:
                    patterns["shooting_star"] = True
                if c > o and pc < po and c > pc and o < po:  # bullish engulf
                    patterns["bullish_engulfing"] = True
                if c < o and pc > po and c < pc and o > po:  # bearish engulf
                    patterns["bearish_engulfing"] = True
                for star in _stars(opens, closes, highs, lows, i):
                    patterns[star] = True
    return {"patterns": patterns, "bars": bars}
