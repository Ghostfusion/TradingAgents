"""Phase 2 - relative strength (RS) vs a benchmark (e.g. SPY/^GSPC).

The swing framework ( Strategies/framework.md) requires leadership against the
broader market: the RS line (stock price / benchmark ratio) must be in an
established uptrend and making new highs before or simultaneously with the
stock price. When the price makes a new high but the RS line does not, that is
negative divergence - the leadership is fading.

Pure, offline-testable helpers. Callers feed two daily close series (stock +
benchmark, tails aligned under the assumption they end on the same date) and
get flags, never raw vendor output.
"""

from __future__ import annotations


def align_tail(stock: list, benchmark: list) -> tuple[list, list] | None:
    """Align two daily series by their tails (assumes same end date).

    Daily series from different vendors may differ slightly in length; the
    framework's RS ratio is meaningful only over common trading days, so the
    last ``min(len)`` observations of both are kept. Returns None when either
    series is too short to be meaningful.
    """
    if not stock or not benchmark:
        return None
    n = min(len(stock), len(benchmark))
    if n < 2:
        return None
    return [float(v) for v in stock[-n:]], [float(v) for v in benchmark[-n:]]


def rs_series(stock: list, benchmark: list) -> list | None:
    """Daily RS line  = stock / benchmark, aligned on the tail.

    Ratios where either side is missing/non-positive are skipped; None when
    fewer than two ratios survive (no derivable trend).
    """
    a, b = align_tail(stock, benchmark) or (None, None)
    if a is None or b is None:
        return None
    out = []
    for sa, sb in zip(a, b, strict=True):
        if sa is not None and sb is not None and sa > 0 and sb > 0:
            out.append(sa / sb)
    return out if len(out) >= 2 else None


def slope_pct(series: list, window: int = 20) -> float | None:
    """OLS slope of ``series[-window:]`` normalized by its mean -> %/day.

    None when the segment is too short or degenerate (flat mean).
    """
    if not series or window < 2:
        return None
    seg = series[-window:]
    n = len(seg)
    x = list(range(n))
    xm = sum(x) / n
    ym = sum(seg) / n
    den = sum((xi - xm) ** 2 for xi in x)
    if den == 0 or abs(ym) < 1e-12:
        return None
    slope = sum((xi - xm) * (yi - ym) for xi, yi in zip(x, seg, strict=True)) / den
    return slope / abs(ym)


def rs_trend(rs: list, window: int = 20) -> dict:
    """Established-uptrend check for the RS line.

    An uptrend needs a positive normalized slope over the window *and* the RS
    line above its own trailing average (holding, not just tickling).
    """
    if rs is None or len(rs) < window:
        return {"rs": None, "slope_pct": None, "above_sma": None, "uptrend": None}
    sl = slope_pct(rs, window)
    sma = sum(rs[-window:]) / window
    last = rs[-1]
    above = bool(last >= sma) if sma and sma > 0 else None
    up = bool(sl is not None and sl > 0 and above is not None and above)
    return {
        "rs": round(last, 6),
        "slope_pct": round(sl * 100.0, 4) if sl is not None else None,
        "above_sma": above,
        "uptrend": up,
    }


def rs_position(rs: list, lookback: int = 252) -> dict:
    """Where the RS line sits vs its own prior window (new-high / near-high).

    ``new_high`` is strict (today beats every prior observation), ``near_high``
    is within 3% of the prior window high (the "making new highs before or
    simultaneously with price" reading).
    """
    if rs is None or not lookback or len(rs) < 2:
        return {"new_high": None, "near_high": None, "dist_from_high": None}
    n = min(lookback, len(rs) - 1)
    prior = rs[-(n + 1) : -1]
    if not prior:
        return {"new_high": None, "near_high": None, "dist_from_high": None}
    prior_high = max(prior)
    last = rs[-1]
    if prior_high <= 0:
        return {"new_high": None, "near_high": None, "dist_from_high": None}
    return {
        "new_high": last > prior_high,
        "near_high": last >= 0.97 * prior_high,
        "dist_from_high": (last / prior_high - 1.0),
    }


#: The RS-breakdown lookback: one quarter. The rotation literature measures a
#: former leader over 3-12 months and warns that the most recent MONTH is
#: dominated by short-term reversal, so 63 sessions is the shortest window that
#: asks "is the leadership broken?" rather than "was yesterday noisy?".
RS_BREAKDOWN_LOOKBACK = 63


def rs_breakdown(rs: list, lookback: int = RS_BREAKDOWN_LOOKBACK) -> dict:
    """Lower-side twin of :func:`rs_position`: is the RS line breaking DOWN?

    ``rs_position`` only asks whether the RS line is making new highs, so a name
    whose relative strength is in freefall reads the same as one that is merely
    quiet. This asks the opposite three questions over ``lookback`` sessions
    (63 = one quarter):

    * ``new_low`` - the RS line is below every prior observation in the window
      (strict, mirroring ``new_high``).
    * ``near_low`` - within 3% of the prior window low (mirroring ``near_high``,
      which is within 3% of the prior window high).
    * ``lower_high`` - the RECENT half's peak is below the EARLIER half's peak,
      i.e. the line is making lower highs rather than being quiet. Both peaks
      travel with the flag so the reading can be checked by eye; ``None`` when
      the window is too short to have two halves (never ``False``).

    Every leg is ``None`` rather than ``False`` when the series is unusable: an
    unmeasured breakdown is not an absent one. REPORTED only - nothing gates on
    this, and nothing should until it has been measured against the unfiltered
    baseline (the RS-breakdown premise is the one the momentum literature's
    skip-month rule exists to avoid).
    """
    empty = {
        "new_low": None,
        "near_low": None,
        "lower_high": None,
        "dist_from_low": None,
        "prior_low": None,
        "earlier_peak": None,
        "recent_peak": None,
        "lookback": lookback,
        "label": None,
    }
    if not rs or not lookback or len(rs) < 2:
        return empty
    n = min(int(lookback), len(rs) - 1)
    prior = rs[-(n + 1) : -1]
    if not prior:
        return empty
    prior_low = min(prior)
    if prior_low <= 0:
        return empty
    last = rs[-1]
    new_low = bool(last < prior_low)
    near_low = bool(last <= 1.03 * prior_low)
    half = n // 2
    recent_peak = earlier_peak = lower_high = None
    if half >= 2:
        recent_peak = max(rs[-half:])
        earlier_peak = max(prior[:-half] or prior)
        lower_high = bool(recent_peak < earlier_peak)
    if new_low and lower_high:
        label = "freefall"
    elif new_low:
        label = "new-relative-low"
    elif lower_high:
        label = "lower-highs"
    elif near_low:
        label = "near-relative-low"
    else:
        label = "holding"
    return {
        "new_low": new_low,
        "near_low": near_low,
        "lower_high": lower_high,
        "dist_from_low": last / prior_low - 1.0,
        "prior_low": prior_low,
        "earlier_peak": earlier_peak,
        "recent_peak": recent_peak,
        "lookback": n,
        "label": label,
    }


def divergence(stock: list, benchmark: list, lookback: int = 252) -> dict:
    """Negative divergence: price makes a new high while RS does not."""
    rs = rs_series(stock, benchmark)
    base = rs_position(rs, lookback) if rs is not None else {}
    if rs is None or len(stock) < 2:
        return {"price_new_high": None, "divergence": None, **base}
    n = min(lookback, len(stock) - 1)
    prior = stock[-(n + 1) : -1]
    price_new_high = bool(prior and stock[-1] > max(prior))
    div = bool(price_new_high and not base.get("near_high"))
    return {
        "price_new_high": price_new_high,
        "rs_new_high": base.get("new_high"),
        "rs_near_high": base.get("near_high"),
        "divergence": div,
        "dist_from_high": base.get("dist_from_high"),
    }


def relative_strength_report(
    stock: list, benchmark: list, window: int = 63, lookback: int = 252
) -> dict:
    """Composite RS verdict for a candidate: trend + position + divergence.

    ``window`` is the *established-trend* window (default 63 trading days
    ~ 1 quarter): a current pullback can make a 20-day RS slope negative
    while the quarterly trend is still intact, which is exactly the setup
    the swing framework wants to buy.

    Verdicts: ``leading`` (uptrend near new highs), ``uptrend``, ``lagging``
    (downtrend/falling RS), ``diverging`` (price new high, RS not) or
    ``unknown`` when there is no usable series.
    """
    rs = rs_series(stock, benchmark)
    if rs is None:
        return {"rs": None, "verdict": "unknown", "context": "RS n/a (benchmark data missing)"}
    trend = rs_trend(rs, window)
    pos = rs_position(rs, lookback)
    div = bool(divergence(stock, benchmark, lookback).get("divergence"))
    if div:
        verdict = "diverging"
    elif trend["uptrend"] is True and pos.get("near_high"):
        verdict = "leading"
    elif trend["uptrend"] is True:
        verdict = "uptrend"
    else:
        verdict = "lagging"
    sl = trend.get("slope_pct")
    bd = rs_breakdown(rs)
    ctx = (
        f"RS={trend['rs']} slope={sl:+.2f}%/d uptrend={trend['uptrend']} "
        f"near_high={pos.get('near_high')} divergence={div} "
        f"breakdown={bd.get('label')}"
    )
    return {
        "rs": trend["rs"],
        "slope_pct": trend["slope_pct"],
        "uptrend": trend["uptrend"],
        "above_sma": trend["above_sma"],
        "new_high": pos.get("new_high"),
        "near_high": pos.get("near_high"),
        "divergence": div,
        "verdict": verdict,
        "context": ctx,
        # The lower-side twin, carried as its own block (reported, never scored):
        # a former leader going into freefall is what the divergence flag cannot
        # see, because a falling RS line makes no new high either way.
        "breakdown": bd,
    }


__all__ = [
    "align_tail",
    "rs_series",
    "slope_pct",
    "rs_trend",
    "rs_position",
    "rs_breakdown",
    "RS_BREAKDOWN_LOOKBACK",
    "divergence",
    "relative_strength_report",
]
