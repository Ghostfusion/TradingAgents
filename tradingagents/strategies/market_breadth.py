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

from .sector_breadth import multi_breadth
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


def market_breadth(
    closes_by_name: dict,
    *,
    windows: tuple = (20, 50, 200),
    min_n: int = 20,
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
    return out


__all__ = ["market_breadth", "PANEL_KEY"]
