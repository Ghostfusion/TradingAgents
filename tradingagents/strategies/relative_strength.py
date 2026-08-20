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
    ctx = (
        f"RS={trend['rs']} slope={sl:+.2f}%/d uptrend={trend['uptrend']} "
        f"near_high={pos.get('near_high')} divergence={div}"
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
    }


__all__ = [
    "align_tail",
    "rs_series",
    "slope_pct",
    "rs_trend",
    "rs_position",
    "divergence",
    "relative_strength_report",
]
