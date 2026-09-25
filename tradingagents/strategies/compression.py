"""Volatility-compression reads for the VDU/VCP ladder.

Three measurements the VDU/VCP producers never made, all pure functions over
bars the engine already holds:

* :func:`atr_compression_read` - where today's ATR/close sits in its OWN
  trailing distribution (the lower fifth of the last ~6 months is the
  "compressed" band the swing literature calls a volatility contraction).
* :func:`closing_range_read` - how wide the last few daily ranges were, and
  where each close finished inside its own range (a tight coil before a
  breakout).
* :func:`base_priming_read` - the two-bar state those two cannot express:
  yesterday was quiet (tight or inside), today expands out of it and clears the
  quiet bar's high on confirming volume.

All three are REPORTED ONLY. None returns a pass/fail gate the caller is meant
to enforce, none sets a candidate, and a series too short to measure returns
``None`` rather than a fabricated reading - the repo's unknown-over-invented
rule. The thresholds are conventional floors, not validated edge, so a consumer
that wants to gate on them must do so explicitly and say so.

No look-ahead: the ATR reading at bar *i* uses bars up to *i* only, and the
percentile is taken over the trailing window that ENDS at the last bar, so a
future bar can never re-rank a past reading. ``tests/test_compression.py``
pins that by re-reading the series at the original last bar.
"""

from __future__ import annotations

import statistics

# Conventional defaults (documented, not validated edge): a 14-bar ATR, a
# ~6-month trailing window, and the lower fifth of that window's ATR VALUES as
# the compression band.
ATR_WINDOW = 14
COMPRESSION_LOOKBACK = 126
COMPRESSION_PCT = 0.20
# A "tight" daily range: the bar's high-low width as a fraction of its close.
RANGE_SESSIONS = 3
RANGE_MAX_PCT = 0.010


def _atr_series(
    highs: list,
    lows: list,
    closes: list,
    window: int = ATR_WINDOW,
) -> list[float]:
    """Wilder ATR at every bar that has ``window`` true ranges behind it.

    ``out[j]`` is the ATR as of bar index ``window + j`` (0-based, over the
    common prefix of the three series), so the caller can align it with the
    bars. A bar whose PRIOR close is non-positive refuses the whole series (an
    empty list) rather than being coerced or skipped: a zero close would make
    every percentage reading downstream meaningless, and skipping one bar
    would silently misalign ``out[j]`` against the bar it describes.
    """
    n = min(len(highs or []), len(lows or []), len(closes or []))
    if n < window + 1:
        return []
    tr: list[float] = []
    for i in range(1, n):
        h, lo, pc = float(highs[i]), float(lows[i]), float(closes[i - 1])
        if pc <= 0:
            return []
        tr.append(max(h - lo, abs(h - pc), abs(lo - pc)))
    if len(tr) < window:
        return []
    out = [sum(tr[:window]) / window]
    for i in range(window, len(tr)):
        out.append((out[-1] * (window - 1) + tr[i]) / window)
    return out


def atr_compression_read(
    highs: list,
    lows: list,
    closes: list,
    *,
    window: int = ATR_WINDOW,
    lookback: int = COMPRESSION_LOOKBACK,
    pct: float = COMPRESSION_PCT,
) -> dict | None:
    """Today's ATR/close against its own trailing ATR distribution.

    Returns ``None`` when the history cannot support the read (fewer than
    ``window + 1`` bars). Otherwise:

    * ``atr`` / ``atr_pct`` - the current ATR in price and as a fraction of the
      current close
    * ``percentile`` - the share of the trailing ``lookback`` ATR values that
      are at or below the current one (empirical rank, so the window's minimum
      reads ``1/len(window)``, not 0)
    * ``compressed`` - ``percentile <= pct`` (the lower fifth by default);
      a REPORTED reading, never a gate
    * ``min_atr`` / ``median_atr`` / ``max_atr`` - the window it is ranked in

    The window ENDS at the last bar, so every value ranked is already observed.
    """
    a = _atr_series(highs, lows, closes, window=window)
    if not a:
        return None
    win = a[-lookback:] if lookback and lookback > 0 else a
    cur = a[-1]
    px = float(closes[-1])
    if px <= 0:
        return None
    rank = sum(1 for v in win if v <= cur) / len(win)
    return {
        "atr": round(cur, 6),
        "atr_pct": round(cur / px, 6),
        "percentile": round(rank, 4),
        "compressed": bool(rank <= pct),
        "pct_threshold": pct,
        "lookback": len(win),
        "window": window,
        "min_atr": round(min(win), 6),
        "median_atr": round(statistics.median(win), 6),
        "max_atr": round(max(win), 6),
    }


def closing_range_read(
    closes: list,
    highs: list,
    lows: list,
    *,
    sessions: int = RANGE_SESSIONS,
    max_pct: float = RANGE_MAX_PCT,
) -> dict | None:
    """Width and close position of each of the last ``sessions`` daily bars.

    ``range_pct[i] = (high - low) / close``; ``tight`` is true when EVERY one of
    those sessions stays at or under ``max_pct`` (1% by default) - the coil
    before a breakout. ``close_position[i] = (close - low) / (high - low)`` (1.0
    = a close at the high), reported for context and ``None`` on a zero-range
    bar rather than dividing by zero.

    Returns ``None`` when there are fewer than ``sessions`` bars, or when a
    close is non-positive. Reported only, never a gate.
    """
    n = min(len(closes or []), len(highs or []), len(lows or []))
    if n < sessions or sessions < 1:
        return None
    widths: list[float] = []
    positions: list[float | None] = []
    for h, lo, c in zip(highs[-sessions:], lows[-sessions:], closes[-sessions:], strict=False):
        h, lo, c = float(h), float(lo), float(c)
        if c <= 0:
            return None
        widths.append((h - lo) / c)
        positions.append((c - lo) / (h - lo) if h > lo else None)
    measured = [p for p in positions if p is not None]
    return {
        "range_pct": [round(w, 6) for w in widths],
        "mean_range_pct": round(sum(widths) / len(widths), 6),
        "tight": bool(all(w <= max_pct for w in widths)),
        "max_range_pct": max_pct,
        "sessions": sessions,
        "close_position": [round(p, 4) if p is not None else None for p in positions],
        "close_position_mean": (
            round(sum(measured) / len(measured), 4) if measured else None
        ),
    }


#: The range multiple today must print over the prior bar to count as expansion
#: (the contraction-to-expansion literature describes the expansion bar as a
#: multiple of the quiet one without fixing a number; 1.5x is the conventional
#: mid-point of the band the trader-facing sources use).
EXPANSION_RANGE_MULT = 1.5
#: The relative-volume multiple a confirming expansion needs. The band quoted in
#: the breakout sources is 1.3x-1.5x of the 50-day average; 1.4 is its mid-point.
EXPANSION_RVOL_MIN = 1.4
#: Where the close must finish inside today's bar (1.0 = at the high). The
#: sources' "close in the upper 25% of the candle" = 0.75.
EXPANSION_CLOSE_POS_MIN = 0.75
#: The volume baseline window: the 50-day average the VDU/breakout sources use.
EXPANSION_VOL_WINDOW = 50


def base_priming_read(
    closes: list,
    highs: list,
    lows: list,
    volumes: list,
    *,
    tight_pct: float = RANGE_MAX_PCT,
    expansion_mult: float = EXPANSION_RANGE_MULT,
    rvol_min: float = EXPANSION_RVOL_MIN,
    close_pos_min: float = EXPANSION_CLOSE_POS_MIN,
    vol_window: int = EXPANSION_VOL_WINDOW,
) -> dict:
    """T-1 base priming: yesterday was quiet, today expands out of it.

    The two-bar state the VDU ladder never expressed. ``closing_range_read``
    asks whether the last few bars were tight - today included - so it cannot
    say "yesterday coiled, today expanded", which is the actual entry shape:
    supply stops moving on a quiet bar, and the expansion bar that clears it is
    where demand shows up.

    Legs, each reported separately so the read can be argued with:

    * ``prev_tight`` - the PRIOR bar's ``(high-low)/close`` is at or under
      ``tight_pct`` (1% by default, the same floor ``closing_range_read`` uses).
    * ``prev_inside`` - the prior bar sits inside the one before it (a textbook
      inside bar). The sources accept "inside or quiet", so either primes.
    * ``expansion`` - today's range is at least ``expansion_mult`` (1.5x) the
      prior bar's range: the coil has been broken.
    * ``cleared`` - today's close is above the prior bar's high.
    * ``rvol`` / ``rvol_ok`` - today's volume over the mean of the prior
      ``vol_window`` (50) sessions, needing ``rvol_min`` (1.4x). The divisor is
      the number of bars that slice actually holds, so a short volume series
      cannot inflate the ratio.
    * ``close_position`` / ``close_ok`` - where the close finished inside
      today's own bar, needing ``close_pos_min`` (0.75 = the top quarter).

    ``primed`` is True only when EVERY leg is measured and true, and ``None``
    when any leg is unmeasured (too few bars, a zero-range bar, no volume) -
    never ``False``, which would report an unmeasured setup as an absent one.
    REPORTED ONLY: this returns no candidate and no gate, and the thresholds are
    conventional floors, not validated edge.
    """
    thresholds = {
        "tight_pct": tight_pct,
        "expansion_mult": expansion_mult,
        "rvol_min": rvol_min,
        "close_pos_min": close_pos_min,
        "vol_window": vol_window,
    }
    empty = {
        "primed": None,
        "prev_tight": None,
        "prev_inside": None,
        "prev_range_pct": None,
        "expansion": None,
        "expansion_ratio": None,
        "cleared": None,
        "rvol": None,
        "rvol_ok": None,
        "close_position": None,
        "close_ok": None,
        "thresholds": thresholds,
        "reasons": [],
    }
    n = min(len(closes or []), len(highs or []), len(lows or []))
    if n < 3:
        return {**empty, "reasons": ["fewer than 3 bars: no prior/expansion pair"]}
    c, h, lo = float(closes[-1]), float(highs[-1]), float(lows[-1])
    pc, ph, pl = float(closes[-2]), float(highs[-2]), float(lows[-2])
    ph2, pl2 = float(highs[-3]), float(lows[-3])
    if c <= 0 or pc <= 0:
        return {**empty, "reasons": ["non-positive close: range percentages undefined"]}

    reasons: list[str] = []
    prev_range_pct = (ph - pl) / pc
    prev_tight = bool(prev_range_pct <= tight_pct)
    prev_inside = bool(ph <= ph2 and pl >= pl2)
    prev_primed = bool(prev_tight or prev_inside)
    if not prev_primed:
        reasons.append(
            f"prior bar was neither tight ({prev_range_pct:.4f} > {tight_pct}) "
            "nor an inside bar"
        )

    today_range, prev_range = h - lo, ph - pl
    expansion_ratio = (
        round(today_range / prev_range, 4) if prev_range > 0 else None
    )
    expansion = (
        bool(today_range >= expansion_mult * prev_range)
        if expansion_ratio is not None
        else None
    )
    if expansion is False:
        reasons.append(
            f"today's range is {expansion_ratio}x the prior bar's (< {expansion_mult}x)"
        )
    cleared = bool(c > ph)
    if not cleared:
        reasons.append("close did not clear the prior bar's high")

    close_position = (c - lo) / (h - lo) if h > lo else None
    close_ok = bool(close_position >= close_pos_min) if close_position is not None else None
    if close_ok is False:
        reasons.append(
            f"close finished at {close_position:.2f} of today's bar (< {close_pos_min})"
        )
    elif close_ok is None:
        reasons.append("zero-range bar: close position unmeasured")

    vols = [float(v) for v in (volumes or []) if v is not None]
    prior_vol = vols[max(0, len(vols) - 1 - vol_window) : len(vols) - 1]
    rvol = None
    if len(prior_vol) >= 2 and vols:
        base = sum(prior_vol) / len(prior_vol)
        rvol = round(vols[-1] / base, 4) if base > 0 else None
    rvol_ok = bool(rvol >= rvol_min) if rvol is not None else None
    if rvol_ok is False:
        reasons.append(f"rvol {rvol}x < {rvol_min}x on the expansion bar")
    elif rvol_ok is None:
        reasons.append("volume baseline unmeasured (fewer than 2 prior sessions)")

    legs = (prev_primed, expansion, cleared, rvol_ok, close_ok)
    primed = True if all(leg is True for leg in legs) else (
        None if any(leg is None for leg in legs) else False
    )
    if primed is None:
        reasons.append("unmeasured leg(s): primed is unknown, not False")
    return {
        "primed": primed,
        "prev_tight": prev_tight,
        "prev_inside": prev_inside,
        "prev_range_pct": round(prev_range_pct, 6),
        "expansion": expansion,
        "expansion_ratio": expansion_ratio,
        "cleared": cleared,
        "rvol": rvol,
        "rvol_ok": rvol_ok,
        "close_position": round(close_position, 4) if close_position is not None else None,
        "close_ok": close_ok,
        "thresholds": thresholds,
        "reasons": reasons,
    }


__all__ = ["atr_compression_read", "base_priming_read", "closing_range_read"]
