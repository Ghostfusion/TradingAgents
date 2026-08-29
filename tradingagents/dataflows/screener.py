"""US equity screener + market movers via yfinance's free screener.

yfinance exposes Yahoo's public equity-screener API (no key, no paid plan)
through predefined queries and its own discovery/movers feeds. This module
wraps two surfaces:

- ``screen_equities``: screen a universe by metric (valuation/size filters)
  and return rows of ``{symbol, price, pe, eps, beta, mkt_cap, ...}``.
- ``get_market_movers``: the session's top ``gainers`` / ``losers`` /
  ``active`` names (Yahoo's ``day_gainers`` / ``day_losers`` / ``most_actives``
  discovery).

Fields come straight from Yahoo's quote payload; a missing field renders as
``n/a``, never estimated (no fabrication). An empty screen raises
``NoMarketDataError``; throttling / server errors surface as
``VendorRateLimitError``.
"""
from __future__ import annotations

import logging

from yfinance import screener as _yf_screener

from .errors import NoMarketDataError, VendorRateLimitError

logger = logging.getLogger(__name__)

# Friendly screener names -> Yahoo predefined query keys. Extend freely.
MARKET_QUERIES = {
    "us": "aggressive_small_caps",
    "growth": "growth_technology_stocks",
    "value": "undervalued_large_caps",
    "small_cap": "small_cap_gainers",
    "shorted": "most_shorted_stocks",
    "active": "most_actives",
}

# Mover kinds -> Yahoo discovery queries.
MOVERS_QUERIES = {
    "gainers": "day_gainers",
    "losers": "day_losers",
    "active": "most_actives",
}

# Yahoo answers predefined queries in the screener body only when the key is
# known; referencing anything else raises. Cache the known keys once on import.
_KNOWN_QUERIES = frozenset(getattr(_yf_screener, "PREDEFINED_SCREENER_QUERIES", {}))

MAX_ROWS = 50  # Yahoo's count cap is 250; keep the table bounded for context.
DEFAULT_SCREEN_LIMIT = 50
DEFAULT_MOVERS_LIMIT = 10


def _resolve_query(market: str) -> str:
    """Map a friendly market name to a known predefined query key."""
    key = (market or "us").strip().lower()
    return MARKET_QUERIES.get(key, MARKET_QUERIES["us"])


def _fetch_quotes(query: str, limit: int) -> list[dict]:
    """Run a predefined Yahoo screener query and return its quote rows.

    This is the network seam — hermetic tests patch it directly.
    """
    try:
        result = _yf_screener.screen(query, count=max(1, int(limit)))
    except Exception as exc:  # noqa: BLE001 - any network/HTTP failure degrades
        raise VendorRateLimitError(f"Yahoo screener request failed: {exc}") from exc
    quotes = (result or {}).get("quotes") or []
    return [q for q in quotes if isinstance(q, dict)]


def _pick(q: dict, key: str):
    """Pull a quote field; None/NaN -> 'n/a' (honest, never invented)."""
    v = q.get(key)
    if v is None:
        return "n/a"
    try:
        if isinstance(v, float) and v != v:  # NaN
            return "n/a"
    except (TypeError, ValueError):
        return "n/a"
    return v


def _fmt_cap(v) -> str:
    """Format market cap (e.g. 1.4T, 340B, 850M); missing -> 'n/a'."""
    if v is None:
        return "n/a"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "n/a"
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if f >= div:
            return f"{f / div:.2f}{suf}"
    return f"{f:.0f}"


def _render(title: str, quotes: list[dict], max_rows: int, columns: tuple[str, ...]) -> str:
    """Render quote rows as a markdown table over a fixed column subset."""
    col_headers = {
        "symbol": "Symbol",
        "name": "Name",
        "price": "Price",
        "change_pct": "Chg %",
        "pe": "P/E",
        "eps": "EPS",
        "beta": "Beta",
        "mkt_cap": "Mkt Cap",
        "volume": "Volume",
    }
    shown = quotes[:max_rows]
    lines = [title, "", "| " + " | ".join(col_headers[c] for c in columns) + " |",
             "| " + " | ".join("---" for _ in columns) + " |"]
    for q in shown:
        cells = []
        for c in columns:
            if c == "mkt_cap":
                cells.append(_fmt_cap(q.get("marketCap")))
            else:
                cells.append(str(_pick(q, _FIELD_MAP[c])))
        lines.append("| " + " | ".join(cells) + " |")
    if len(quotes) > max_rows:
        lines.append(f"\n_(showing {max_rows} of {len(quotes)} results)_")
    return "\n".join(lines)


_FIELD_MAP = {
    "symbol": "symbol",
    "name": "shortName",
    "price": "regularMarketPrice",
    "change_pct": "regularMarketChangePercent",
    "pe": "trailingPE",
    "eps": "epsTrailingTwelveMonths",
    "beta": "beta",
    "volume": "regularMarketVolume",
}

_SCREEN_COLUMNS = ("symbol", "name", "price", "change_pct", "pe", "eps", "beta", "mkt_cap")
_MOVERS_COLUMNS = ("symbol", "name", "price", "change_pct", "volume")


def screen_equities(
    market: str = "us", limit: int = 50, filters: dict | None = None
) -> str:
    """Screen US equities via yfinance's free screener.

    Returns ``{symbol, price, pe, eps, beta, mkt_cap, ...}`` rows as markdown.
    ``market`` picks a predefined universe; ``filters`` may override it with a
    raw predefined query key (``filters={"query": "day_gainers"}``). Missing
    fields render ``n/a``. Raises ``NoMarketDataError`` on an empty screen.
    """
    limit = max(1, int(limit or DEFAULT_SCREEN_LIMIT))
    query = None
    if isinstance(filters, dict):
        query = filters.get("query")
    elif isinstance(filters, str) and filters.strip():
        query = filters.strip()
    if not query:
        query = _resolve_query(market)
    if query not in _KNOWN_QUERIES:
        # A sentinel (not a plain guidance string) so the router does not
        # cache this bad-argument reply for 6h as if it were real data.
        return (
            f"DATA_UNAVAILABLE: equity screener unavailable - unknown query "
            f"{query!r}. Known predefined queries: {', '.join(sorted(_KNOWN_QUERIES)) or 'none available'}."
        )
    quotes = _fetch_quotes(query, min(limit, MAX_ROWS))
    if not quotes:
        raise NoMarketDataError(
            market, query, detail=f"no rows for screener '{query}'"
        )
    return _render(
        f"## Equity screen: {query} (yfinance, free no-key)",
        quotes,
        min(limit, MAX_ROWS),
        _SCREEN_COLUMNS,
    )


def get_market_movers(kind: str = "gainers", limit: int = 10) -> str:
    """Top U.S. market movers via Yahoo's discovery screener (free).

    ``kind``: ``gainers`` | ``losers`` | ``active``. Returns ranked rows of
    ``{symbol, price, change_pct, volume, name}``. An empty feed raises
    ``NoMarketDataError``; an invalid ``kind`` returns a guiding message
    without raising (a bad argument must not crash the run).
    """
    key = (kind or "gainers").strip().lower()
    query = MOVERS_QUERIES.get(key)
    if not query:
        return (
            f"DATA_UNAVAILABLE: market movers unavailable - invalid kind "
            f"{kind!r}; use one of {sorted(MOVERS_QUERIES)}."
        )
    limit = max(1, int(limit or DEFAULT_MOVERS_LIMIT))
    quotes = _fetch_quotes(query, min(limit, MAX_ROWS))
    if not quotes:
        raise NoMarketDataError(kind, query, detail=f"no movers for '{kind}'")
    return _render(
        f"## Market movers: {key} (yfinance, free no-key)",
        quotes,
        min(limit, MAX_ROWS),
        _MOVERS_COLUMNS,
    )
