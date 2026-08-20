"""Phase 2 - sector & industry group confirmation (top 3 of 11 SPDR groups).

The swing framework requires the candidate's sector to be a top performer over
a rolling 1-month and 3-month window (e.g. the top 3 of the 11 SPDR sector
ETFs). This module ranks the SPDR groups purely from their daily close series
- the screener feeds the closes from the vendor chain and reads the flags back.
"""

from __future__ import annotations

# The 11 SPDR sector ETFs (XLY=XLC renamed in 1998; kept the current ticker).
SPDR_SECTORS = {
    "XLE": "Energy",
    "XLF": "Financials",
    "XLK": "Technology",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLY": "Consumer Disc.",
    "XLP": "Consumer Staples",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLC": "Communications",
}


def _momentum(closes: list, window: int) -> float | None:
    """Return over the trailing ``window`` bars (close vs window bars ago)."""
    if not closes or len(closes) <= window:
        return None
    base = closes[-window - 1]
    if base is None or base <= 0:
        return None
    return closes[-1] / base - 1.0


def rank_sectors(closes_map: dict, window_1m: int = 21, window_3m: int = 63) -> dict:
    """Rank the SPDR groups by 3-month momentum (primary) + 1-month standing.

    ``closes_map``: {SPDR ticker: daily closes}. Sectors with insufficient
    history sort last and are never ranked top-3. Returns ``None`` when no
    usable series at all.
    """
    rows = []
    for etf, closes in (closes_map or {}).items():
        r1 = _momentum(closes, window_1m)
        r3 = _momentum(closes, window_3m)
        rows.append(
            {
                "etf": etf,
                "name": SPDR_SECTORS.get(etf, etf),
                "ret_1m": round(r1, 4) if r1 is not None else None,
                "ret_3m": round(r3, 4) if r3 is not None else None,
                "rank": None,
            }
        )
    ranked = sorted(rows, key=lambda r: (r["ret_3m"] is None, -(r["ret_3m"] or 0.0)))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i if r["ret_3m"] is not None else None
    by_1m = sorted(rows, key=lambda r: (r["ret_1m"] is None, -(r["ret_1m"] or 0.0)))
    valid = [r for r in ranked if r["ret_3m"] is not None]
    if not valid:
        return {"ranked": ranked, "top3_3m": [], "top3_1m": []}
    top3_3m = [r["etf"] for r in ranked[:3] if r["rank"] is not None]
    top3_1m = [r["etf"] for r in by_1m[:3] if r["ret_1m"] is not None]
    return {"ranked": ranked, "top3_3m": top3_3m, "top3_1m": top3_1m}


def _canonical_sector(sector: str) -> str:
    """Map a GICS/yfinance sector string to the SPDR short label (lowercase)."""
    key = sector.strip().lower()
    return _GICS_TO_SPDR.get(key, key)


# GICS naming vs the SPDR short labels (FMP/av profile and yfinance report
# GICS names; the SPDR group names differ in spelling, e.g. "Financial
# Services" vs "Financials", "Information Technology" vs "Technology").
_GICS_TO_SPDR = {
    "information technology": "technology",
    "communication services": "communications",
    "consumer discretionary": "consumer disc.",
    "financial services": "financials",
    "financial": "financials",
    "healthcare": "health care",
    "consumer staples": "consumer staples",
    "real estate": "real estate",
    "utilities": "utilities",
    "energy": "energy",
    "materials": "materials",
    "industrials": "industrials",
}


def sector_standing(sector: str | None, ranking: dict | None) -> dict:
    """Where a candidate's sector sits in the ranking.

    Verdicts: ``top3`` (in the 3-month top-3), ``tracking`` (ranked but not
    top-3), ``unknown`` (sector or ranking unavailable).
    """
    if not sector or not ranking:
        return {
            "sector": sector,
            "rank": None,
            "top3_3m": None,
            "top3_1m": None,
            "verdict": "unknown",
        }
    sector = sector.strip()
    canon = _canonical_sector(sector)
    for r in ranking.get("ranked", []):
        name = str(r.get("name", "")).lower()
        if canon == name or (canon and (canon in name or name in canon)):
            top3 = r["etf"] in ranking.get("top3_3m", [])
            return {
                "sector": r["name"],
                "rank": r["rank"],
                "etf": r["etf"],
                "top3_3m": top3,
                "top3_1m": r["etf"] in ranking.get("top3_1m", []),
                "verdict": "top3" if top3 else "tracking",
            }
    return {"sector": sector, "rank": None, "top3_3m": None, "top3_1m": None, "verdict": "unknown"}


__all__ = [
    "SPDR_SECTORS",
    "rank_sectors",
    "sector_standing",
]
