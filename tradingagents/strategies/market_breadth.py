"""Market-WIDE breadth from a panel the run already fetched (P0-3).

``RegimeScore.md`` §1 marks market-wide advance/decline, new highs/lows and
percent-above-MA as **ABSENT**, and §4 names the smallest honest producer: no new
vendor, because ``sector_breadth.multi_breadth`` already takes a
``{name: closes}`` map and the sector screens already build that map in bulk over
the in-repo S&P universe. This module is that producer, market-wide instead of
per sector.

**One implementation, two scopes** (ground rule 2): the percent-above-MA columns
come from ``multi_breadth``, and the A/D, new-high/new-low and coverage counts are
computed from the same map - so the numbers cannot describe different panels.

The denominator-integrity gate is ``sector_screener.breadth_with_gate``'s rule: a
panel below ``min_n`` is **not** a breadth read, so the percentages render ``None``
with the reason rather than a noisy number over a handful of names (master rule 1).
"""

from __future__ import annotations

import math

import numpy as np

from .sector_breadth import SPECTRUM_WINDOW, mp_lower_spectrum, multi_breadth
from .sector_screener import breadth_with_gate

#: The market-wide bucket key handed to ``multi_breadth``. The panel is ONE
#: universe, not a sector map, so the key is a label rather than a ticker.
PANEL_KEY = "MARKET"

#: One trading year - the FIXED lookback behind the ``*_52w`` counters. 252 is
#: the session count the volatility models annualize with, so "52-week" means
#: the same thing everywhere in the repo. A name with fewer bars cannot print a
#: 52-week high, so it is excluded from the count and reported in
#: ``new_highs_52w_n`` rather than assumed flat.
_YEAR_SESSIONS = 252


def _usable(series) -> list[float] | None:
    """The finite closes of one name, or None when the series is unusable."""
    if not series:
        return None
    vals = [float(v) for v in series if v is not None]
    return vals if len(vals) >= 2 else None


def _spectrum_refused(names: int, window: int, reason: str) -> dict:
    """The one refusal shape of the X3 read: ``unavailable``, never zero."""
    return {
        "count": None,
        "mp_lower": None,
        "status": "unavailable",
        "window": window,
        "n_names": names,
        "unavailable": reason,
    }


def mp_below_count(corr, n: int, w: int) -> dict:
    """Eigenvalues of a panel correlation matrix below the Marchenko-Pastur
    lower bound (X3, 2608.09641).

    ``corr`` is the ``n x n`` correlation matrix of ONE panel's trailing ``w``
    returns; the bound is ``(1 - sqrt(n/w))^2``, the lower edge of the
    Marchenko-Pastur bulk for an ``n x w`` i.i.d. matrix. The count of
    eigenvalues below it RISES when the effective number of independent bets
    collapses - a panel whose names have started moving as one. Read it as a
    synchronization STATE: it is coincident and direction-blind, so it cannot
    separate a crash from a bubble and is never a signal.

    ``status`` is ``"unavailable"`` - never ``count == 0`` - when ``w <= n``:
    at a window no longer than the panel the bound collapses to 0 and the bulk
    has no lower edge, so "nothing sits below the bound" would be an artifact
    of a degenerate limit rather than a measurement. A missing, wrongly shaped
    or non-finite matrix refuses the same way (rule 4).

    Returns ``{count, mp_lower, status, window, n_names, unavailable}``: the
    window and the panel size the count was computed over travel with it (rule
    4 / H10), and ``unavailable`` carries the reason when the read is refused.
    """
    window = int(w)
    names = int(n)
    if window <= names:
        return _spectrum_refused(
            names, window,
            f"window {window} is not longer than the panel ({names} names): the "
            "Marchenko-Pastur lower bound collapses to 0, so no eigenvalue "
            "count would be a measurement",
        )
    matrix = np.asarray(corr, dtype=float) if corr is not None else None
    if matrix is None or matrix.ndim != 2 or matrix.shape != (names, names):
        shape = None if matrix is None else matrix.shape
        return _spectrum_refused(
            names, window,
            f"correlation matrix {shape} is not the {names}x{names} panel matrix",
        )
    if not np.all(np.isfinite(matrix)):
        return _spectrum_refused(
            names, window, "correlation matrix carries a non-finite entry"
        )
    lower = (1.0 - math.sqrt(names / window)) ** 2
    eigenvalues = np.linalg.eigvalsh(matrix)
    return {
        "count": int(np.count_nonzero(eigenvalues < lower)),
        "mp_lower": float(lower),
        "status": "ok",
        "window": window,
        "n_names": names,
        "unavailable": None,
    }


def market_breadth(
    closes_by_name: dict,
    *,
    windows: tuple = (20, 50, 200),
    min_n: int = 20,
    cfg: dict | None = None,
    spectrum_window: int = SPECTRUM_WINDOW,
) -> dict | None:
    """Market-wide breadth over a panel of close series, or None for an empty map.

    ``closes_by_name`` is ``{name: [close, ...]}`` (oldest -> newest), the shape
    the sector screens already build. Returns::

        {
          "pct_above_20d" | "pct_above_50d" | "pct_above_200d": 0-100 | None,
          "n": usable names, "coverage": usable / total,
          "advance_decline": advancers - decliners (0 when none moved),
          "ad_ratio": (advancers - decliners) / n, or None on a small sample,
          "new_highs": names at their own series high,
          "new_lows": names at their own series low,
          "new_highs_52w" | "new_lows_52w" | "net_new_highs_52w": counts over a
              FIXED one-year lookback, or None when no name carries a year,
          "new_highs_52w_n": how many names carried the full year,
          "small_sample": bool, "min_n": int, "basis": str,
          "reason": why the percentages are withheld (small sample only),
          "mp_lower_spectrum": the panel's Marchenko-Pastur lower-spectrum read
              (``{count, mp_lower, status, window, n_names, ...}``) - present
              ONLY with ``enable_mp_lower_spectrum`` on, so every key above is
              byte-identical to the run before the read existed,
        }

    ``new_highs``/``new_lows`` are measured against **the series each name was
    given** - the caller's trailing window is the lookback, so a 252-bar panel
    makes them 52-week highs/lows and a 60-bar panel does not. The basis string
    says which window the panel carried, so the read cannot be quoted as a
    52-week figure it never measured.

    The ``_52w`` pair is the one that CAN be quoted as 52-week: it measures the
    last ``_YEAR_SESSIONS`` (252) closes whatever the panel length, so a 60-bar
    and a 300-bar panel agree for the same last year of bars. A name with fewer
    than a year of bars is excluded from the count and reported in
    ``new_highs_52w_n`` - never counted, and never assumed not-at-a-high. With
    no name carrying a year the pair is ``None`` rather than ``0``: a count over
    an empty denominator is not a breadth read (master rule 1).

    Never returns 0 for an absent read: an empty map is ``None``, and a panel
    below ``min_n`` keeps its counts with the percentages withheld and the reason
    printed (``small_sample``).

    ``cfg``/``spectrum_window`` drive the ONE gated extra key: with
    ``enable_mp_lower_spectrum`` on, ``mp_lower_spectrum`` (X3) reads the
    Marchenko-Pastur lower spectrum of THIS panel - one read for the panel, not
    one per name - and reports the window it was computed over. With the gate
    off (the default, and the only state in which the key is absent) the read is
    never taken and nothing above moves.
    """
    panel = {k: v for k, v in (closes_by_name or {}).items() if _usable(v)}
    if not panel:
        return None
    total = len(closes_by_name or {})
    n = len(panel)
    row = (multi_breadth({PANEL_KEY: panel}, windows=windows, min_n=min_n) or {}).get(PANEL_KEY) or {}
    gated = breadth_with_gate(row, min_n=min_n)
    advancers = decliners = highs = lows = 0
    highs_52w = lows_52w = 0
    year_names = 0
    bars = 0
    for series in panel.values():
        vals = _usable(series)
        bars = max(bars, len(vals))
        if vals[-1] > vals[-2]:
            advancers += 1
        elif vals[-1] < vals[-2]:
            decliners += 1
        if vals[-1] >= max(vals):
            highs += 1
        if vals[-1] <= min(vals):
            lows += 1
        # The ``_52w`` pair uses a FIXED lookback, so it does not move with the
        # panel length the way ``new_highs``/``new_lows`` do: a 60-bar panel and
        # a 300-bar panel give the same answer for the same last year of bars.
        # A name shorter than a year is excluded and counted in
        # ``new_highs_52w_n`` - never treated as not-at-a-high.
        if len(vals) >= _YEAR_SESSIONS:
            year = vals[-_YEAR_SESSIONS:]
            year_names += 1
            if vals[-1] >= max(year):
                highs_52w += 1
            if vals[-1] <= min(year):
                lows_52w += 1
    out = {
        "n": n,
        "coverage": round(n / total, 3) if total else 0.0,
        "advance_decline": advancers - decliners,
        # The RATIO form of the same numerator over the same panel - so
        # `technical_score`'s declared `ad_ratio` leg has the producer its own
        # component table names, and the difference and the ratio are one
        # producer's two readings rather than two producers of one quantity
        # (rule 15). Withheld on a small sample for the same reason the
        # percentages are: a 3-name advance/decline ratio is not a market read.
        "ad_ratio": (None if gated.get("small_sample")
                     else round((advancers - decliners) / n, 4)),
        "advancers": advancers,
        "decliners": decliners,
        "new_highs": highs,
        "new_lows": lows,
        # New fields only: ``new_highs``/``new_lows`` above keep their meaning
        # (counts against the panel window), so nothing already printed moves.
        "new_highs_52w": highs_52w if year_names else None,
        "new_lows_52w": lows_52w if year_names else None,
        "net_new_highs_52w": (highs_52w - lows_52w) if year_names else None,
        "new_highs_52w_n": year_names,
        "small_sample": bool(gated.get("small_sample")),
        "min_n": min_n,
        "basis": (
            f"{n}-name panel, up to {bars} bars each; new highs/lows are measured "
            f"against that window; the _52w pair over a fixed "
            f"{_YEAR_SESSIONS}-session year ({year_names} of {n} names carry one)"
        ),
    }
    for w in windows:
        key = f"pct_above_{w}d"
        value = row.get(f"pct_{w}d")
        out[key] = None if gated.get("small_sample") else value
    if tuple(windows) != (20, 50, 200):
        # ``multi_breadth`` computes the above-counts for the windows it is
        # given but REPORTS only the 20/50/200 columns, so any other window is
        # None here rather than a number from a different window. Stated, not
        # silently dropped.
        out["basis"] += " | the shared producer reports the 20/50/200 columns only"
    if gated.get("reason"):
        out["reason"] = gated["reason"]
    # X3: ONE Marchenko-Pastur lower-spectrum read for the panel (never one per
    # name), gated by ``enable_mp_lower_spectrum`` - off by default, which is
    # what keeps every key above byte-identical to the run before the read
    # existed. With the gate on it ADDS this one key and moves nothing else.
    spectrum = mp_lower_spectrum(panel, window=spectrum_window, cfg=cfg)
    if spectrum is not None:
        out["mp_lower_spectrum"] = spectrum
    return out


# --- R5: a calibrated forward stress probability from the cross-section -----
#
# 2602.07066 aggregates MONTHLY cross-sectional fragility signals - return
# dispersion, downside extremes, higher moments - over the tracked universe into
# a one-month-ahead probability of entering a high-stress regime. This module
# already builds a market-wide panel (P0-3), so R5's only cost is the
# aggregation, not the data.
#
# The probability is IN-SAMPLE CALIBRATED and says so: the bands come from
# ``calibration.calibration_table`` over the SAME panel's own history - one
# calibration implementation, never a second - and ``p_stress`` IS the current
# fragility band's realised hit rate, so the number and its reliability are the
# same object. The calibration report travels WITH the number (an uncalibrated
# probability is a score wearing a probability's name) and the horizon is stated
# in the output, never implied by the caller.
#
# A cross-section too thin to calibrate is ``unavailable``, never a number: the
# denominator-integrity rule is ``sector_screener.breadth_with_gate``'s, read
# rather than restated.
#
# R8 binds the wording: this is a fitted read on one panel, not a
# walk-forward-tested detector, so ``caveat`` travels on EVERY returned read and
# nothing here reads as an early warning.

#: One trading month - 21 sessions, the same 252/12 the volatility convention
#: implies. The panel is aggregated at MONTHLY frequency, the paper's cadence.
MONTH_SESSIONS = 21

#: R5's cross-section floor, the same 20 ``market_breadth`` withholds below: a
#: probability fitted on a handful of names is not a market fragility read.
FS_MIN_NAMES = 20

#: The history floor. Fewer complete monthly observations than this and the
#: calibration bands hold too few rows to be a calibration at all.
FS_MIN_MONTHS = 24

#: The floor on a SINGLE calibration band's own count: a band fitted on a couple
#: of months would print a "probability" read from noise.
FS_MIN_BIN_N = 5

#: The declared outcome rule: a month is a HIGH-STRESS month when the
#: equal-weight panel return sits below this quantile of the panel's own monthly
#: history. Declared policy - the paper's own threshold is not carried here.
FS_STRESS_QUANTILE = 0.2

#: What the record names itself, and the R8 label that binds its wording.
FS_LABEL = "forward stress probability (one-month-ahead, cross-sectional, in-sample)"
FS_CAVEAT = (
    "in-sample calibration: the bands are fitted on the same panel history they "
    "score, so this is a fitted read, not a walk-forward-tested detector, and the "
    "probability is not evidence of an edge (R8)"
)

#: ``calibration_table`` prints a band as a label ("50%-60%"); the edges are read
#: back from that label so the ONE bin table in the repo stays
#: ``calibration._BINS`` and is never copied here.
_BIN_SEPARATOR = "%-"


def _fs_horizon(months: int = 1) -> dict:
    """The horizon, stated IN the output: months, sessions and the plain label."""
    return {
        "months": int(months),
        "sessions": MONTH_SESSIONS * int(months),
        "frequency": "monthly",
        "label": "one-month-ahead" if int(months) == 1 else f"{int(months)}-month-ahead",
    }


def _fs_unavailable(reason: str, *, n_names: int = 0, n_months: int = 0,
                    horizon: dict | None = None, window: dict | None = None) -> dict:
    """The one refusal shape of the R5 read: ``unavailable``, never a number.

    The reason and the window it was computed over travel with it (ground rule 4
    / H10), and ``calibration`` is present as ``None`` so a caller cannot read a
    missing key as a probability with no report.
    """
    return {
        "label": FS_LABEL,
        "p_stress": None,
        "horizon": horizon or _fs_horizon(),
        "calibration": None,
        "fragility": None,
        "n_names": n_names,
        "n_months": n_months,
        "window": window,
        "status": "unavailable",
        "unavailable": reason,
        "basis": reason,
        "caveat": FS_CAVEAT,
    }


def _monthly_returns(series) -> list[float]:
    """Non-overlapping monthly returns from one close series (oldest -> newest).

    A partial trailing month is DROPPED rather than annualized from a stub: a
    month the panel did not complete is not a monthly observation.
    """
    vals = _usable(series)
    if vals is None:
        return []
    out = []
    for end in range(len(vals) - 1, MONTH_SESSIONS - 1, -MONTH_SESSIONS):
        start = end - MONTH_SESSIONS
        if start < 0 or vals[start] <= 0:
            continue
        out.append(vals[end] / vals[start] - 1.0)
    out.reverse()
    return out


def _cross_moments(cross: list[float]) -> dict:
    """The cross-sectional fragility moments of ONE month's return vector."""
    n = len(cross)
    mean = sum(cross) / n
    var = sum((x - mean) ** 2 for x in cross) / n
    sd = math.sqrt(var)
    skew = (sum(((x - mean) / sd) ** 3 for x in cross) / n) if sd > 0 else 0.0
    return {
        "dispersion": sd,
        "downside_share": sum(1 for x in cross if x < mean - sd) / n,
        "skew": skew,
        "market_return": mean,
    }


def _rank01(values: list[float], x: float) -> float:
    """The share of ``values`` at or below ``x`` - a deterministic 0-1 rank."""
    n = len(values)
    if n <= 0:
        return 0.0
    return sum(1 for v in values if v <= x) / n


def _bin_edges(label) -> tuple[float, float] | None:
    """``(lo, hi)`` read back from a ``calibration_table`` label ("50%-60%")."""
    parts = str(label or "").split(_BIN_SEPARATOR)
    if len(parts) != 2:
        return None
    try:
        lo = int(parts[0]) / 100.0
        hi = int(parts[1].rstrip("%")) / 100.0
    except ValueError:
        return None
    return lo, hi


def _bin_for(table: list[dict], value: float) -> dict | None:
    """The ``calibration_table`` row whose band holds ``value``, or None.

    The band is located from the label ``calibration_table`` printed, so there is
    ONE bin table in the repo (``calibration._BINS``) and this read cannot drift
    from it.
    """
    for row in table or []:
        edges = _bin_edges(row.get("bin"))
        if edges is None:
            continue
        lo, hi = edges
        upper = 1.0001 if hi >= 1.0 else hi
        if lo <= value < upper:
            return row
    return None


def forward_stress_probability(
    panel: dict,
    *,
    cfg: dict | None = None,
    horizon_months: int = 1,
) -> dict:
    """R5: a calibrated one-month-ahead probability the market enters stress.

    ``panel`` is ``{name: [close, ...]}`` - the same shape ``market_breadth``
    takes, so the panel breadth already pays for is the panel this read uses.
    Each name's closes are folded into **non-overlapping monthly returns** (21
    sessions), the cross-section is made rectangular (the same names at every
    observation), and three cross-sectional fragility signals are read per month:
    return **dispersion**, the **downside share** (names below mean - 1 sd), and
    the cross-sectional **skew** - the paper's dispersion / downside-extreme /
    higher-moment trio. Their percentile ranks average into a 0-1 *fragility*.

    The outcome is the equal-weight panel's NEXT month falling in the bottom
    ``FS_STRESS_QUANTILE`` of the panel's own monthly returns. Fragility and
    outcome become ``calibration_table`` rows, and ``p_stress`` is the realised
    hit rate of the band the CURRENT fragility falls in - so the probability and
    the evidence behind it are one object, and the report is part of the output.

    Returns ``{'label', 'p_stress', 'horizon', 'calibration', 'fragility',
    'n_names', 'n_months', 'window', 'status', 'unavailable', 'basis',
    'caveat'}``. ``horizon`` states the horizon IN the output. ``calibration``
    is a report whenever ``p_stress`` is a number, and ``None`` on a refusal.
    Any refusal - gate off, an empty panel, a cross-section below
    ``FS_MIN_NAMES`` (the ``breadth_with_gate`` rule), too few complete months,
    no observed stress month, no populated band for the current fragility, or a
    band below ``FS_MIN_BIN_N`` rows - returns ``p_stress`` None with
    ``unavailable`` carrying the reason: never 0, never an uncalibrated number.

    Behind ``enable_forward_stress_probability`` (default off, env
    ``TRADINGAGENTS_ENABLE_FORWARD_STRESS_PROBABILITY``): with the gate off the
    read reports ``unavailable`` with the reason, so a gate-off run computes
    nothing new. ``regime_score`` prints the read beside the score and never
    scores it.
    """
    horizon = _fs_horizon(horizon_months)
    # The key is read by its literal name so the gate registry's read-site scan
    # finds it; an unreadable config leaves the gate off and computes nothing.
    try:
        from tradingagents.dataflows.config import get_config

        gate = get_config() if cfg is None else cfg
    except Exception:  # noqa: BLE001 - a config read must never break the read
        gate = cfg or {}
    if not bool((gate or {}).get("enable_forward_stress_probability", False)):
        return _fs_unavailable(
            "enable_forward_stress_probability is off (default): the read is not "
            "produced on a gate-off run",
            horizon=horizon,
        )

    offered = len(panel or {})
    usable = {k: v for k, v in (panel or {}).items() if _usable(v)}
    n = len(usable)
    if n == 0:
        return _fs_unavailable("no usable close series in the panel", horizon=horizon)
    # The denominator-integrity rule is `breadth_with_gate`'s, read rather than
    # restated - a cross-section below the floor is not a market read.
    gated = breadth_with_gate({"n": n}, min_n=FS_MIN_NAMES)
    if gated.get("small_sample"):
        return _fs_unavailable(
            f"cross-section of {n} usable name(s) of {offered} offered: "
            f"{gated.get('reason')} - a probability fitted on {n} names is not a "
            "market fragility read",
            n_names=n,
            horizon=horizon,
            window={"n_names": n, "panel_n": offered, "names": sorted(usable)},
        )

    monthly = {name: _monthly_returns(series) for name, series in usable.items()}
    observed_max_months = max((len(r) for r in monthly.values()), default=0)
    monthly = {name: r for name, r in monthly.items() if len(r) >= FS_MIN_MONTHS}
    if not monthly:
        return _fs_unavailable(
            f"no usable name carries {FS_MIN_MONTHS} complete monthly observations",
            n_names=n,
            n_months=observed_max_months,
            horizon=horizon,
        )
    n_months = min(len(r) for r in monthly.values())
    # A rectangular panel: the same names at every observation, so the
    # cross-section cannot change size between the fragility read and the outcome
    # it is calibrated against.
    months = {name: r[-n_months:] for name, r in monthly.items()}

    moments = [
        _cross_moments([months[name][t] for name in months])
        for t in range(n_months)
    ]
    disps = [m["dispersion"] for m in moments]
    downs = [m["downside_share"] for m in moments]
    skews = [m["skew"] for m in moments]
    # Rising dispersion and a rising downside share are fragility; a MORE
    # NEGATIVE skew is too, so the skew rank is inverted before it is averaged in.
    fragility = [
        (_rank01(disps, disps[t]) + _rank01(downs, downs[t])
         + (1.0 - _rank01(skews, skews[t]))) / 3.0
        for t in range(n_months)
    ]
    market = [m["market_return"] for m in moments]
    threshold = float(np.quantile(np.asarray(market, dtype=float), FS_STRESS_QUANTILE))
    stress = [x < threshold for x in market]

    rows = [
        {"confidence": fragility[t], "outcome": {"hit": bool(stress[t + 1])}}
        for t in range(n_months - 1)
    ]
    if len(rows) < FS_MIN_MONTHS:
        return _fs_unavailable(
            f"only {len(rows)} fragility->outcome pair(s), below the "
            f"{FS_MIN_MONTHS} needed to calibrate",
            n_names=len(months),
            n_months=n_months,
            horizon=horizon,
        )
    if not any(r["outcome"]["hit"] for r in rows):
        return _fs_unavailable(
            "no high-stress month in the panel's own history: a probability of an "
            "event never observed cannot be calibrated",
            n_names=len(months),
            n_months=n_months,
            horizon=horizon,
        )

    # Deferred: `calibration` is a leaf module, imported at call time so this
    # module's own import block (and every line below it) is unchanged.
    from .calibration import calibration_table

    table = calibration_table(rows)
    current = fragility[-1]
    band = _bin_for(table, current)
    base_window = {
        "n_names": len(months),
        "n_months": n_months,
        "names": sorted(months),
        "frequency": "monthly",
        "sessions_per_month": MONTH_SESSIONS,
        "incomplete_trailing_month_dropped": True,
    }
    if band is None or int(band.get("n") or 0) < FS_MIN_BIN_N:
        got = "no band" if band is None else f"band {band['bin']} with n={band['n']}"
        return _fs_unavailable(
            f"the current fragility {current:.3f} has {got} at or above the "
            f"{FS_MIN_BIN_N}-row floor, so no calibrated probability exists for it",
            n_names=len(months),
            n_months=n_months,
            horizon=horizon,
            window=base_window,
        )

    calibration = {
        "table": table,
        "n_rows": len(rows),
        "n_bins": len(table),
        "min_bin_n": FS_MIN_BIN_N,
        "current_bin": band["bin"],
        "band_n": int(band["n"]),
        "stress_months": sum(1 for r in rows if r["outcome"]["hit"]),
        "outcome_rule": (
            f"high-stress = equal-weight panel return below the "
            f"{FS_STRESS_QUANTILE:.0%} quantile of the panel's own monthly "
            "history (the quantile is fitted on the full history - in-sample, see "
            "caveat)"
        ),
        "basis": (
            "calibration.calibration_table over the panel's own history (ONE "
            "calibration implementation); p_stress is the current fragility "
            "band's realised hit rate, so the number and its reliability are the "
            "same object"
        ),
    }
    return {
        "label": FS_LABEL,
        "p_stress": float(band["actual_hit_rate"]),
        "horizon": horizon,
        "calibration": calibration,
        "fragility": {
            "value": float(current),
            "band": band["bin"],
            "components": {
                "dispersion": float(disps[-1]),
                "downside_share": float(downs[-1]),
                "skew": float(skews[-1]),
            },
            "market_return": float(market[-1]),
            "stress_threshold": threshold,
        },
        "n_names": len(months),
        "n_months": n_months,
        "window": base_window,
        "status": "ok",
        "unavailable": None,
        "basis": (
            f"R5 (2602.07066): {len(months)} names x {n_months} complete monthly "
            "observations; fragility = mean percentile rank of cross-sectional "
            "dispersion, downside share and inverted skew; outcome = next month in "
            f"the bottom {FS_STRESS_QUANTILE:.0%} of the panel's own monthly "
            f"returns; p_stress from the {band['bin']} band (n={band['n']}), "
            "IN-SAMPLE calibrated"
        ),
        "caveat": FS_CAVEAT,
    }


__all__ = [
    "market_breadth",
    "mp_below_count",
    "PANEL_KEY",
    "forward_stress_probability",
    "MONTH_SESSIONS",
    "FS_MIN_NAMES",
    "FS_MIN_MONTHS",
    "FS_MIN_BIN_N",
    "FS_STRESS_QUANTILE",
]
