"""Sector breadth + McClellan/MSI + RRG-heading (advisory breadth layer).

Extends the sector-rotation screen with:

1. ``multi_breadth``     - the % > 20d / 50d / 200d SMA participation matrix
                         per sector (the 50d-only ``constituent_breadth`` is
                         the 50d column).
2. ``mcclellan_read``    - per-sector normalized A/D (ANA x1000), the
                         McClellan Oscillator EMA19-EMA39, the momentum
                         (rising/falling) and the CUMULATIVE-SUM Summation
                         Index (the correct MSI definition - the EMA
                         difference alone is not the index, per the review).
3. ``rrg_heading``       - the RS-Ratio/RS-Momentum phase angle (degrees,
                         0-360) + the "constructive trajectory" and
                         "Weakening SW trap" flags that sit next to the
                         existing ``rrg_quadrant``.
4. ``msi_zone``          - the advisory risk-budget note from the MSI level
                         + 5d slope (advisory; the repo's risk governor stays
                         authoritative - never a gate).
5. ``mp_lower_spectrum`` - X3 (2608.09641): the count of eigenvalues of ONE
                         panel's correlation matrix below the Marchenko-Pastur
                         lower bound ``(1 - sqrt(n/w))^2``, which rises when the
                         effective number of independent bets collapses. Gated
                         by ``enable_mp_lower_spectrum`` (off by default), and a
                         per-PANEL read - never a per-symbol one.

All functions are pure, None-safe, and reuse the repo's existing helpers
(sma/ema/constituent fetch); the ~300-member S&P-500 universe built for the
screen is the exact data source the McClellan needs.
"""

from __future__ import annotations

import math

import numpy as np


def _sma(values: list, window: int, idx: int = -1) -> float | None:
    """SMA_{window} at ``idx`` (default last) - None when unavailable.

    ``idx`` may be negative (Python-style from-the-end); a negative window
    start is a valid slice (e.g. ``values[-200:]`` for 260 bars), only an
    absolute start < 0 (window exceeds the series length) is unavailable.
    """
    if not values or window <= 0:
        return None
    n = len(values)
    abs_idx = n + idx if idx < 0 else idx
    abs_start = abs_idx - window + 1
    if abs_start < 0 or abs_idx >= n:
        return None
    seg = values[abs_start:abs_idx + 1]
    return sum(seg) / len(seg) if seg else None


def _ema_series(values: list, span: int) -> list:
    """Full EMA series (span -> alpha=2/(span+1)); [] on no input."""
    if not values or span <= 0:
        return []
    alpha = 2.0 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


#: X3's gate (2608.09641). Off by default: with it off ``mp_lower_spectrum``
#: returns ``None`` and no breadth output carries an extra key, so a gate-off
#: run is byte-identical to the run before the read existed.
GATE_NAME = "enable_mp_lower_spectrum"

#: The number of RETURNS the panel correlation matrix is built over. One
#: trading year - the same 252 the volatility models annualize with and
#: ``market_breadth``'s ``*_52w`` counters use - so "a year of returns" means
#: one thing everywhere in the repo.
SPECTRUM_WINDOW = 252


def _panel_returns(closes_by_name: dict, window: int) -> tuple[list[str], list[list[float]]]:
    """``(names, return rows)`` for the panel's trailing ``window`` returns.

    A name enters only when it carries the WHOLE window: a correlation matrix
    built from series of different lengths is not one panel read, so a short,
    non-positive or flat series is left out and reported by
    ``mp_lower_spectrum``'s coverage fields rather than padded with a
    substituted value (rule 4).
    """
    names: list[str] = []
    rows: list[list[float]] = []
    for name, series in (closes_by_name or {}).items():
        closes: list[float] = []
        for value in (series or []):
            if value is None:
                continue
            f = float(value)
            if f == f:  # not NaN
                closes.append(f)
        if len(closes) < window + 1:
            continue
        seg = closes[-(window + 1):]
        if any(c <= 0.0 for c in seg):
            continue
        rets = [seg[i] / seg[i - 1] - 1.0 for i in range(1, len(seg))]
        if max(rets) == min(rets):  # a flat series has no correlation to give
            continue
        names.append(name)
        rows.append(rets)
    return names, rows


def mp_lower_spectrum(closes_by_name: dict, *, window: int = SPECTRUM_WINDOW,
                      cfg: dict | None = None) -> dict | None:
    """X3: the Marchenko-Pastur lower-spectrum read of ONE panel (gated).

    ``closes_by_name`` is ``{name: [close, ...]}`` - the same panel shape
    ``market_breadth`` takes, and the shape the sector screen already builds for
    the 11 SPDR sector ETFs ``sector_rank`` tracks. The panel's correlation
    matrix is built over the trailing ``window`` returns and handed to
    ``market_breadth.mp_below_count``, which owns the bound, the count and the
    ``w <= n`` refusal; this function owns the panel, its window and its
    coverage. One call per panel, never one per symbol.

    Returns ``None`` when ``enable_mp_lower_spectrum`` is off (its default),
    and otherwise the ``mp_below_count`` record plus ``panel_n`` - how many
    names the panel OFFERED, beside ``n_names``, how many carried the window.
    A panel that cannot yield two full-window names reads ``status:
    "unavailable"`` with the counts, never a zero.

    The read is coincident and direction-blind - it cannot separate a crash
    from a bubble - so it is reported as a state, never as a signal.
    """
    try:
        from tradingagents.dataflows.config import get_config

        gate = get_config() if cfg is None else cfg
    except Exception:  # noqa: BLE001 - a config read must never break the read
        gate = cfg or {}
    if not bool((gate or {}).get("enable_mp_lower_spectrum", False)):
        return None
    # Deferred: ``market_breadth`` imports THIS module at the top (it reuses
    # ``multi_breadth``), so the producer is imported at call time.
    from .market_breadth import mp_below_count

    win = int(window)
    offered = len(closes_by_name or {})
    names, rows = _panel_returns(closes_by_name, win)
    if len(names) < 2:
        return {
            "count": None,
            "mp_lower": None,
            "status": "unavailable",
            "window": win,
            "n_names": len(names),
            "panel_n": offered,
            "unavailable": (
                f"panel read refused: {len(names)} of {offered} name(s) carry "
                f"{win} returns (2 are needed for a correlation matrix)"
            ),
        }
    corr = np.corrcoef(np.asarray(rows, dtype=float))
    return {**mp_below_count(corr, len(names), win), "panel_n": offered}


def multi_breadth(closes_map: dict, *, windows: tuple = (20, 50, 200),
                  min_n: int = 20) -> dict:
    """Sector breadth matrix: {etf: {'n', 'n_20d', 'n_50d', 'n_200d',
    'pct_20d', 'pct_50d', 'pct_200d', 'small_sample': bool}}.

    Each column = % of the members that CARRY that window whose last close >
    SMA_w. A member with fewer bars than a window is left out of THAT column's
    denominator and reported in ``n_<w>d`` - it is never counted as not-above,
    because a name with no 200d SMA is no evidence about the 200d line and
    counting it as one depresses the column by construction. A column with no
    eligible member reads ``None``, never a fabricated ``0.0``: a count over an
    empty denominator is not a breadth read (the rule ``market_breadth`` states
    for its 52-week pair). The columns reported are the 20/50/200 trio whatever
    ``windows`` says, so a caller asking for another window reads ``None``
    rather than a number from a different window.

    A sector with n < ``min_n`` gets ``small_sample=True`` (breadth not
    meaningful) but keeps the raw n so the display is honest instead of a fake
    percentage.
    """
    out = {}
    columns = (20, 50, 200)
    for etf, members in (closes_map or {}).items():
        n = 0
        above = dict.fromkeys(columns, 0)
        eligible = dict.fromkeys(columns, 0)
        for c in (members or {}).values() if isinstance(members, dict) else (members or []):
            if not c:
                continue
            n += 1
            for w in windows:
                if w not in eligible:
                    continue
                sma = _sma(c, w)
                if sma is None:
                    continue
                eligible[w] += 1
                if c[-1] > sma:
                    above[w] += 1
        row: dict = {"n": n, "small_sample": (not n) or n < min_n, "min_n": min_n}
        for w in columns:
            den = eligible.get(w) or 0
            row[f"n_{w}d"] = den
            row[f"pct_{w}d"] = round(100.0 * above.get(w, 0) / den, 1) if den else None
        out[etf] = row
    return out


def mcclellan_read(closes_map: dict, *, burn_in: int = 60) -> dict:
    """Per-sector McClellan Oscillator + Summation Index (cumulative-sum).

    Returns ``{etf: {'n', 'mo', 'mo_slope', 'msi': float|None, 'burn_in':
    bool}}`` where ``msi`` = cumsum of the oscillator (the CORRECT MSI
    definition). None-safe; a sector with < ``burn_in`` aligned bars gets
    ``burn_in=True`` (cold-start, not trusted - the spec's own rule).
    """
    out = {}
    # align all members of a sector to a common index length
    for etf, members in (closes_map or {}).items():
        streams = []
        for c in ((members or {}).values() if isinstance(members, dict) else (members or [])):
            if c and len(c) > 1:
                streams.append(c)
        if not streams:
            out[etf] = {"n": 0, "mo": None, "mo_slope": None, "msi": None,
                        "burn_in": True}
            continue
        n = min(len(c) for c in streams)
        aligned = [c[-n:] for c in streams]
        # daily A - D / (A + D) x 1000 per bar over the aligned window.
        # IMPORTANT: the *normalized* ratio (A-D)/(A+D) saturates at +-1 on
        # one-directional markets and EMA19-EMA39 of a constant series decays
        # to 0 (flattened-regime artifact). Keep the normalized A/D for the
        # cross-sector comparability the spec requires, but feed the raw
        # daily net (A - D) into the EMAs so a sustained advance reads
        # non-zero (the classic McClellan tracks the raw net advances).
        ana = []
        nets = []
        for i in range(1, n):
            adv = dec = 0
            for c in aligned:
                d = c[i] - c[i - 1]
                if d > 0:
                    adv += 1
                elif d < 0:
                    dec += 1
            tot = adv + dec
            nets.append(adv - dec)
            ana.append(((adv - dec) / tot) * 1000.0 if tot > 0 else 0.0)
        if len(ana) < 3:
            out[etf] = {"n": len(streams), "mo": None, "mo_slope": None,
                        "msi": None, "burn_in": True}
            continue
        # oscillator on the RAW net advances (per-bar), scaled by the sector
        # size so readings are comparable across sectors but not tiny: net is
        # in shares-of-members, x(1000/N) normalizes a full-swing sector to
        # +-1000 (the spec's ANA scale) while a monotone market stays non-zero.
        scale = 1000.0 / max(len(streams), 1)
        nets_scaled = [net * scale for net in nets]
        e19 = _ema_series(nets_scaled, 19)
        e39 = _ema_series(nets_scaled, 39)
        osc = [a - b for a, b in zip(e19, e39, strict=True)]
        msi_series = []
        acc = 0.0
        for o in osc:
            acc += o
            msi_series.append(acc)
        # cold-start guard: burn-in bars required before the readings count
        too_short = len(ana) < burn_in
        mo = osc[-1]
        mo_prev = osc[-2] if len(osc) > 1 else mo
        out[etf] = {
            "n": len(streams),
            "mo": round(mo, 1) if not too_short else None,
            "mo_slope": ("Rising" if mo > mo_prev else "Falling") if not too_short else None,
            "msi": round(msi_series[-1], 1) if not too_short else None,
            "burn_in": too_short,
        }
    return out


def rrg_heading(rs_ratio: float | None, rs_momentum: float | None,
                prev_ratio: float | None = None,
                prev_momentum: float | None = None) -> dict:
    """RRG phase angle (degrees 0-360) + trajectory flags.

    dx = RS-Ratio change, dy = RS-Momentum change; heading = atan2(dy, dx)
    mod 360. Flags: ``constructive`` (northeast-ish heading) and
    ``weakening_trap`` (high absolute RS-Ratio but heading into the southwest
    = late-stage crowded momentum). None-safe.
    """
    if rs_ratio is None or rs_momentum is None or prev_ratio is None or prev_momentum is None:
        return {"heading_deg": None, "constructive": None, "weakening_trap": None}
    dx = rs_ratio - prev_ratio
    dy = rs_momentum - prev_momentum
    heading = math.degrees(math.atan2(dy, dx)) % 360.0
    constructive = heading < 90.0  # northeast
    weakening_trap = rs_ratio >= 100.0 and 180.0 <= heading <= 270.0
    return {"heading_deg": round(heading, 1), "constructive": constructive,
            "weakening_trap": weakening_trap}


def msi_zone(msi: float | None, msi_slope5: float | None,
             base_risk: float = 1000.0) -> dict:
    """Advisory MSI zone + suggested risk-budget multiplier (never a gate).

    Maps the Summation Index level + 5-day slope to the spec's zone table.
    ``msi_slope5`` = deltas over the last 5 bars. The repo's risk governor
    stays authoritative - this is context for the report, not an order.
    """
    if msi is None:
        return {"zone": "n/a (cold start)", "mult": None, "effective": None,
                "allow_new_longs": None}
    slope = msi_slope5 if msi_slope5 is not None else 0.0
    if msi > 0:
        if msi > 1200 and slope < 0:
            zone, mult, allow = "Climax Exhaustion", 0.5, True
        elif slope >= 0:
            zone, mult, allow = "Expansion", 1.0, True
        else:
            zone, mult, allow = "Deceleration", 0.75, True
    else:
        if msi < -1000 and slope > 0:
            zone, mult, allow = "Washout Capitulation", 0.5, True
        elif slope < 0:
            zone, mult, allow = "Structural Distribution", 0.0, False
        else:
            zone, mult, allow = "Accumulation / Basing", 0.25, True
    return {"zone": zone, "mult": mult, "effective": round(base_risk * mult, 2),
            "allow_new_longs": allow}


__all__ = ["GATE_NAME", "SPECTRUM_WINDOW", "mp_lower_spectrum", "multi_breadth",
           "mcclellan_read", "rrg_heading", "msi_zone"]
