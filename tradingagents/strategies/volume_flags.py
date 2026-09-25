"""Mechanically-huge volume: OPEX weeks and witching sessions.

Option expiration concentrates volume that has nothing to do with a name's
supply/demand: the third Friday of every month (quadruple witching in
Mar/Jun/Sep/Dec) prints multiples of a normal session's turnover, and the
sessions leading into it run hot. An RVOL or dry-up read that takes those
sessions at face value is reading the options market, not the stock:

* a trigger candle can be "confirmed" by OPEX turnover alone, and
* a 50-bar volume average that contains an OPEX week is inflated, so an
  ordinary session looks like a dry-up.

:func:`mechanical_volume_flags` marks the sessions to discount and
:func:`rvol_ex_mechanical` re-computes the ratio over the unflagged sessions
only. Both are positional over the caller's own session list (no holiday
calendar is consulted, so the flag set cannot disagree with the bars it
describes), and an unparseable date - or a flags list that does not match the
series - makes the read UNMEASURED rather than silently unflagged.

The flag is a READING. Whether a gate should use the discounted ratio is the
caller's decision and is gated by ``enable_mechanical_volume_discount``
(default off), so no existing trigger silently changes meaning.
"""

from __future__ import annotations

from datetime import date, datetime

from .derivatives_gamma import opex_dates

# The five sessions ending on OPEX Friday are "OPEX week"; quarterly witching
# is the same week in Mar/Jun/Sep/Dec.
OPEX_WINDOW = 5
QUARTERLY_MONTHS = (3, 6, 9, 12)


def _parse_dates(dates) -> list[date] | None:
    """ISO strings / date / datetime -> ``date`` list, or None if unparseable."""
    out: list[date] = []
    for d in dates or []:
        if isinstance(d, datetime):
            out.append(d.date())
        elif isinstance(d, date):
            out.append(d)
        else:
            try:
                out.append(date.fromisoformat(str(d).strip()[:10]))
            except ValueError:
                return None
    return out or None


def mechanical_volume_flags(
    dates,
    *,
    opex_window: int = OPEX_WINDOW,
    quarterly_only: bool = False,
    include_unwind: bool = False,
) -> list[bool] | None:
    """One flag per session: does it sit in an OPEX week?

    ``opex_window`` counts sessions INCLUDING OPEX Friday itself (5 = the week
    into expiration). ``quarterly_only`` restricts the flag to quadruple
    witching months. ``include_unwind`` also flags the first session after an
    OPEX date - the post-expiration unwind, when positions have just rolled.

    Returns ``None`` when no date could be parsed (unmeasured, never "nothing
    is mechanical").
    """
    parsed = _parse_dates(dates)
    if not parsed:
        return None
    years = {d.year for d in parsed}
    opex = {d for y in years for d in opex_dates(y)}
    if quarterly_only:
        opex = {d for d in opex if d.month in QUARTERLY_MONTHS}
    if not opex:
        return [False] * len(parsed)
    flags: list[bool] = []
    for i, _d in enumerate(parsed):
        nxt = next((j for j in range(i, len(parsed)) if parsed[j] in opex), None)
        flag = nxt is not None and (nxt - i) < opex_window
        if not flag and include_unwind:
            prev = next((j for j in range(i - 1, -1, -1) if parsed[j] in opex), None)
            flag = prev is not None and (i - prev) == 1
        flags.append(flag)
    return flags


def rvol_ex_mechanical(
    volumes: list,
    dates=None,
    *,
    window: int = 50,
    flags: list[bool] | None = None,
    opex_window: int = OPEX_WINDOW,
    quarterly_only: bool = False,
) -> dict | None:
    """Relative volume with the mechanically-huge sessions taken out.

    ``rvol`` divides today's volume by the mean of the prior ``window``
    sessions; ``rvol_ex_mechanical`` divides it by the mean of those same
    sessions MINUS the flagged ones, so an OPEX spike cannot inflate the
    baseline. ``excluded`` counts the dropped sessions and ``measured`` says
    whether any flag set was available at all - a caller must not read
    ``rvol_ex_mechanical`` as a discount when ``measured`` is False.

    Returns ``None`` when there is no usable volume series or the flag list
    does not align with it (a misaligned flag list would discount the wrong
    sessions).
    """
    vols = [float(v) for v in (volumes or [])]
    if not vols or window < 1:
        return None
    if flags is None and dates is not None:
        flags = mechanical_volume_flags(
            dates, opex_window=opex_window, quarterly_only=quarterly_only
        )
    if flags is not None and len(flags) != len(vols):
        return None
    prior = vols[max(0, len(vols) - 1 - window) : len(vols) - 1]
    if not prior:
        return None
    raw_den = sum(prior) / len(prior)
    adj_den = None
    kept: list = []
    if flags is not None:
        kept = [
            v
            for i, v in enumerate(prior, start=len(vols) - 1 - len(prior))
            if not flags[i]
        ]
        adj_den = (sum(kept) / len(kept)) if kept else None
    today = vols[-1]
    return {
        "rvol": round(today / raw_den, 3) if raw_den > 0 else None,
        "rvol_ex_mechanical": round(today / adj_den, 3) if adj_den and adj_den > 0 else None,
        "measured": flags is not None,
        "excluded": len(prior) - len(kept),
        "flagged_today": bool(flags[-1]) if flags else None,
        "window": window,
        "opex_window": opex_window,
    }


__all__ = ["mechanical_volume_flags", "rvol_ex_mechanical"]
