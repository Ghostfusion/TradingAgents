"""S&P 500 constituent universe (free, disk-cached) for the sector screen.

Fetches the canonical S&P 500 constituents (symbol / GICS sector) from
Wikipedia's list (REST API wikitext, keyless), maps GICS sector -> the SPDR
ETF, and caches the result on disk for a week.

Survivorship note: the Wikipedia list is the *current* S&P 500 - correct for
live breadth reads, biased for any backtest (the P4 backtest stays on the
ETF-level path by design). Any failure degrades to None (the caller renders
n/a or falls back to the EODHD path), never fabricated.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

logger = logging.getLogger(__name__)

_API_URL = "https://en.wikipedia.org/w/api.php"
_PAGE = "List of S&P 500 companies"
_CACHE_TTL = 7 * 24 * 3600  # weekly refresh (the list churns via corporate actions)
_FILENAME = "sp500_universe.json"

# GICS sector name -> SPDR ETF (only the sectors SPDR_SECTORS tracks).
_GICS_MAP = {
    "information technology": "XLK",
    "communication services": "XLC",
    "consumer discretionary": "XLY",
    "financials": "XLF",
    "health care": "XLV",
    "industrials": "XLI",
    "consumer staples": "XLP",
    "energy": "XLE",
    "materials": "XLB",
    "real estate": "XLRE",
    "utilities": "XLU",
}

# One constituent row (wikitable): {{NyseSymbol|0P0}} || Security || GICS Sector..
_ROW_RE = re.compile(
    r"\{\{NyseSymbol\|(?P<sym>[A-Z0-9.\- ]+?)\}\}\s*\|\|\s*[^|]+?\|\|\s*(?P<sector>[^|]+?)\s*\|\|"
)


def _cache_path() -> str | None:
    try:
        from tradingagents.dataflows.config import get_config

        base = (get_config() or {}).get("data_cache_dir") or os.getenv("TRADINGAGENTS_CACHE_DIR")
    except Exception:  # noqa: BLE001 - advisory
        base = os.getenv("TRADINGAGENTS_CACHE_DIR")
    if not base:
        return None
    try:
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, _FILENAME)
    except OSError:
        return None


def _read_cache() -> dict | None:
    path = _cache_path()
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            blob = json.load(f)
        if (blob.get("ts") and time.time() - blob["ts"] < _CACHE_TTL
                and isinstance(blob.get("rows"), dict)):
            return blob
    except (OSError, ValueError):
        pass
    return None


def _write_cache(payload: dict) -> None:
    path = _cache_path()
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError as exc:  # noqa: BLE001 - best-effort cache write
        logger.warning("sp500 universe cache write failed: %s", exc)


def _parse_wikitext(wt: str) -> tuple[dict, int]:
    rows: dict[str, list] = {}
    bucketed = 0
    for m in _ROW_RE.finditer(wt):
        sym = m.group("sym").strip().replace(".", "-").upper()
        sector = m.group("sector").strip().lower()
        etf = _GICS_MAP.get(sector)
        if not sym or not etf:
            continue
        rows.setdefault(etf, []).append(sym)
        bucketed += 1
    return rows, bucketed


def fetch_sp500_universe(refresh: bool = False) -> dict | None:
    """GICS sector -> [tickers] for the current S&P 500 (disk-cached weekly).

    Returns ``{spdr_etf: [ticker, ...], 'stats': {'n_total', 'n_bucketed',
    'ts'}}`` or None on any failure. ``refresh=True`` bypasses the cache.
    """
    if not refresh:
        blob = _read_cache()
        if blob:
            return blob
    try:
        import requests

        resp = requests.get(
            _API_URL,
            params={"action": "parse", "page": _PAGE, "prop": "wikitext",
                    "format": "json", "formatversion": "2"},
            headers={"User-Agent": "TradingAgentsResearch/1.0 contact@example.com"},
            timeout=40,
        )
        resp.raise_for_status()
        wt = (resp.json().get("parse", {}) or {}).get("wikitext", "")
        if not wt:
            logger.warning("sp500 wikitext empty")
            return None
        rows, bucketed = _parse_wikitext(wt)
        if not rows:
            logger.warning("sp500 wikitext parse found no rows")
            return None
        payload = {"rows": rows, "stats": {"n_total": sum(len(v) for v in rows.values()),
                                           "n_bucketed": bucketed, "ts": time.time()}}
        _write_cache(payload)
        return payload
    except Exception as exc:  # noqa: BLE001 - optional enrichment
        logger.warning("sp500 universe fetch failed: %s", exc)
        return None


__all__ = ["fetch_sp500_universe", "_GICS_MAP", "_parse_wikitext"]
