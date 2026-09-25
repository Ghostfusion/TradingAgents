"""O'Neil / IBD distribution-day count for a market index.

A DISTRIBUTION DAY is a session that closes down at least 0.2% on volume
higher than the previous session - institutional selling into strength. IBD
treats a cluster of them (5+ inside ~4-5 weeks) as a market under distribution,
i.e. a topping signal.

This module implements the three rules that make the count mean anything, and
one that the swing literature usually omits:

* **25-session expiry** - a day drops out of the count 25 sessions later.
* **+5% rally cancel** - a day is cancelled early once the index closes 5% or
  more above THAT day's own close.
* **follow-through-day reset** - a confirmed FTD (a gain of >= 1.7% on volume
  above the prior session, landing 4-10 sessions after a correction low) resets
  the count to ZERO. Carrying pre-FTD days forward overstates the pressure a
  fresh uptrend is under.
* the count is of a series, so it needs no calendar - only the sessions the
  index actually traded.

Everything is positional: rules are evaluated in session order, so a vendor's
holiday calendar cannot change the answer. When ``dates`` is supplied the
returned rows carry the date string as well, for rendering.

Conventions are the published ones (0.2% / 25 sessions / +5% / 1.7% on
day 4-10), NOT validated edge for this engine: this is a REPORTED reading, and
a caller that gates on it owns that decision. Too little history returns
``None`` rather than a count computed from noise.
"""

from __future__ import annotations

DECLINE_PCT = 0.002
RALLY_CANCEL_PCT = 0.05
EXPIRY_SESSIONS = 25
FTD_MIN_GAIN = 0.017
FTD_WINDOW = (4, 10)
CORRECTION_LOOKBACK = 25
CORRECTION_MIN_DROP = 0.02
PRESSURE_COUNT = 5
MIN_BARS = 30


def _ftd_index(
    closes: list,
    volumes: list,
    *,
    min_gain: float,
    window: tuple[int, int],
    volume_confirm: bool,
    correction_lookback: int,
    correction_min_drop: float,
) -> int | None:
    """The last confirmed follow-through day, or None.

    A rally day (>= ``min_gain`` on volume above the prior session) qualifies
    when the lowest close 4-10 sessions earlier is at least
    ``correction_min_drop`` below the highest close in the
    ``correction_lookback`` sessions before it - i.e. the rally comes off a
    real pullback, not mid-trend noise.
    """
    lo_gap, hi_gap = window
    found: int | None = None
    for j in range(1, len(closes)):
        pc = closes[j - 1]
        if pc <= 0 or closes[j] < pc * (1 + min_gain):
            continue
        if volume_confirm and not (volumes[j] > volumes[j - 1]):
            continue
        start = j - hi_gap
        end = j - lo_gap
        if start < 0:
            continue
        seg = closes[start : end + 1]
        if not seg:
            continue
        lo_idx = start + min(range(len(seg)), key=lambda k: seg[k])
        peak_start = max(0, lo_idx - correction_lookback)
        peak = max(closes[peak_start:j])
        if peak <= 0 or closes[lo_idx] > peak * (1 - correction_min_drop):
            continue
        found = j
    return found


def distribution_days(
    index_closes: list,
    index_volumes: list,
    *,
    dates: list | None = None,
    decline_pct: float = DECLINE_PCT,
    rally_cancel_pct: float = RALLY_CANCEL_PCT,
    expiry_sessions: int = EXPIRY_SESSIONS,
    ftd_min_gain: float = FTD_MIN_GAIN,
    ftd_window: tuple = FTD_WINDOW,
    ftd_volume_confirm: bool = True,
    correction_lookback: int = CORRECTION_LOOKBACK,
    correction_min_drop: float = CORRECTION_MIN_DROP,
    pressure_count: int = PRESSURE_COUNT,
    min_bars: int = MIN_BARS,
    label: str = "index",
) -> dict | None:
    """Count the index's active distribution days as of the last bar.

    Returns ``None`` when there are fewer than ``min_bars`` bars or the two
    series disagree in length. Otherwise:

    * ``count`` - active distribution days right now
    * ``under_distribution`` - ``count >= pressure_count`` (5 by default)
    * ``active`` - one row per counted day: ``sessions_ago``, ``date`` (when
      ``dates`` was given), its own ``decline_pct`` and ``volume_ratio``
    * ``expired`` / ``cancelled_rally`` / ``reset_by_ftd`` - the three ways a
      day left the count; they always sum with ``count`` to the days detected
    * ``ftd`` - the last confirmed follow-through day (``sessions_ago``,
      ``gain_pct``, ``volume_confirmed``, and the low it followed), or None
    * ``since_ftd`` - sessions since that reset, or None

    The count is a reading: this function never returns a pass/fail gate.
    """
    closes = [float(c) for c in (index_closes or [])]
    volumes = [float(v) for v in (index_volumes or [])]
    if len(closes) != len(volumes) or len(closes) < min_bars:
        return None
    if any(c <= 0 for c in closes):
        return None
    row_dates: list | None = None
    if dates is not None and len(dates) == len(closes):
        row_dates = list(dates)

    detected: list[tuple[int, float, float]] = []
    for i in range(1, len(closes)):
        pc, pv = closes[i - 1], volumes[i - 1]
        if closes[i] > pc * (1 - decline_pct):
            continue
        if not (volumes[i] > pv):
            continue
        detected.append((i, 1 - closes[i] / pc, volumes[i] / pv if pv else 0.0))

    ftd_i = _ftd_index(
        closes,
        volumes,
        min_gain=ftd_min_gain,
        window=tuple(ftd_window),
        volume_confirm=ftd_volume_confirm,
        correction_lookback=correction_lookback,
        correction_min_drop=correction_min_drop,
    )
    last = len(closes) - 1

    def _row(i: int, decline: float, vr: float) -> dict:
        return {
            "sessions_ago": last - i,
            "date": row_dates[i] if row_dates else None,
            "decline_pct": round(decline, 4),
            "volume_ratio": round(vr, 3),
        }

    active: list[dict] = []
    expired = cancelled = reset = 0
    for i, decline, vr in detected:
        if last - i >= expiry_sessions:
            expired += 1
            continue
        if any(closes[j] >= closes[i] * (1 + rally_cancel_pct) for j in range(i + 1, last + 1)):
            cancelled += 1
            continue
        if ftd_i is not None and ftd_i > i:
            reset += 1
            continue
        active.append(_row(i, decline, vr))

    ftd_row = None
    if ftd_i is not None:
        ftd_row = {
            "sessions_ago": last - ftd_i,
            "date": row_dates[ftd_i] if row_dates else None,
            "gain_pct": round(closes[ftd_i] / closes[ftd_i - 1] - 1.0, 4),
            "volume_confirmed": bool(volumes[ftd_i] > volumes[ftd_i - 1]),
        }
    return {
        "count": len(active),
        "under_distribution": bool(len(active) >= pressure_count),
        "active": active,
        "expired": expired,
        "cancelled_rally": cancelled,
        "reset_by_ftd": reset,
        "detected": len(detected),
        "ftd": ftd_row,
        "since_ftd": (last - ftd_i) if ftd_i is not None else None,
        "thresholds": {
            "decline_pct": decline_pct,
            "rally_cancel_pct": rally_cancel_pct,
            "expiry_sessions": expiry_sessions,
            "ftd_min_gain": ftd_min_gain,
            "ftd_window": [int(ftd_window[0]), int(ftd_window[1])],
            "pressure_count": pressure_count,
        },
        "label": label,
        "bars": len(closes),
    }


__all__ = ["distribution_days"]
