"""Short-interest percentile over a name's own settlement series (P0-6).

``SentimentScore.md`` §1 marks short interest **PARTIAL**: the settlement series
is already fetched (``yfinance_short_interest``, ``massive``), but only the raw
level is printed - no percentile and no change basis. A level is not a signal on
its own: 12% short is crowded for one name and ordinary for another, and only the
name's OWN settlement history can say which.

**The direction is stated, never implied.** High short interest is **not**
bullish: it is bearish positioning with a squeeze *risk* attached, and the two are
not the same claim (``SentimentScore.md`` §0.2 point 4). The ``direction`` field
carries that sentence so a reader cannot turn the percentile into a squeeze thesis
by quoting the number alone.

Settlement cadence is **bi-monthly** (FINRA reports the 15th and last business day
settlements, published on the 7th business day after), so ``min_obs`` is counted
in settlements, not days: four settlements is roughly two months.
"""

from __future__ import annotations

from .normalized import percentile_hist_or_none

#: Settlements below this are not a series: FINRA's cadence is bi-monthly, so four
#: is about two months of history - enough to rank, not enough to call a trend.
MIN_SETTLEMENTS = 4

DIRECTION = (
    "high short interest is bearish positioning with a squeeze RISK, not a bullish "
    "signal - the percentile says where the level sits in this name's own history, "
    "not that the crowd is right or that a squeeze is due"
)


def short_interest_percentile(series, *, min_obs: int = MIN_SETTLEMENTS) -> dict:
    """Percentile of the LATEST settlement within the name's own settlements.

    ``series`` is the settlement values **oldest -> newest** (the caller reverses
    a newest-first vendor payload). Returns::

        {"percentile": 0..1 | None, "latest": float | None, "prior": float | None,
         "change_pct": float | None, "n": int, "min_obs": int,
         "basis": str, "direction": str}

    ``percentile`` is ``None`` below ``min_obs`` settlements **with the reason
    printed** - a single settlement has no rank to report, and 0.5 would read as
    "mid-range" when the truth is "unknown" (master rule 1). ``change_pct`` is the
    period-over-period move of the latest settlement, which is the other half of
    the missing basis: a level can be high and falling.
    """
    vals = [float(v) for v in (series or []) if v is not None]
    n = len(vals)
    latest = vals[-1] if vals else None
    prior = vals[-2] if n >= 2 else None
    change = ((latest / prior - 1.0) * 100.0) if (latest is not None and prior) else None
    pct = percentile_hist_or_none(vals, min_obs=min_obs)
    if pct is None:
        basis = (
            f"unmeasurable: {n} settlement(s) held, {min_obs} needed "
            "(FINRA settles twice a month)"
        )
    else:
        basis = f"latest of {n} settlements, {pct:.0%} percentile of this name's own history"
    return {
        "percentile": pct,
        "latest": latest,
        "prior": prior,
        "change_pct": change,
        "n": n,
        "min_obs": min_obs,
        "basis": basis,
        "direction": DIRECTION,
    }


__all__ = ["short_interest_percentile", "MIN_SETTLEMENTS", "DIRECTION"]
