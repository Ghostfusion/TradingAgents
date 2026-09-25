"""Volatility-compression reads for the VDU/VCP ladder.

Two measurements the VDU/VCP producers never made, both pure functions over
bars the engine already holds:

* :func:`atr_compression_read` - where today's ATR/close sits in its OWN
  trailing distribution (the lower fifth of the last ~6 months is the
  "compressed" band the swing literature calls a volatility contraction).
* :func:`closing_range_read` - how wide the last few daily ranges were, and
  where each close finished inside its own range (a tight coil before a
  breakout).

Both are REPORTED ONLY. Neither returns a pass/fail gate the caller is meant
to enforce, neither sets a candidate, and a series too short to measure returns
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


__all__ = ["atr_compression_read", "closing_range_read"]
