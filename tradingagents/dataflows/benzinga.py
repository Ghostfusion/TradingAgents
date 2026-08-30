"""Benzinga financial news vendor (free "Basic Financial News" tier).

Benzinga's Basic Financial News API (free tier, e.g. via the AWS Marketplace
"Basic Financial News API") returns ticker-scoped **financial** news with a
headline, a body teaser, and a link to the full story. It is the rare free feed
that is both ticker-filtered and financial-first, so it slots in BEFORE the
generic keyword feeds in the ``news_data`` chain.

Endpoint: ``GET https://api.benzinga.com/api/v2/news`` with ``tickers``,
``dateFrom``/``dateTo``, ``updatedSince`` and the ``token``.

Key: ``BENZINGA_API_KEY`` in ``.env``. Raises the typed errors the router
understands so a 401/403/429/empty degrades to the next vendor — never a
fabricated value. The free tier supplies headline + teaser + link (no full
body); the render reflects that honestly.
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests as _requests

from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://api.benzinga.com/api/v2"
TIMEOUT = 20
_MAX_RETRIES = 2
_ARTICLE_LIMIT = 10


def benzinga_api_key() -> str | None:
    """Benzinga key from config or environment; None when unset."""
    import os

    try:
        from .config import get_config

        cfg = get_config()
        val = cfg.get("benzinga_api_key")
        if val:
            return str(val)
    except Exception:  # noqa: BLE001 - config is best-effort
        pass
    return os.environ.get("BENZINGA_API_KEY")


def _benzinga_get(path: str, params: dict | None = None) -> list | None:
    """Authenticated GET ``BASE/{path}`` with token; parsed list or None."""
    key = benzinga_api_key()
    if not key:
        raise VendorNotConfiguredError(
            "Benzinga key is not set. Add BENZINGA_API_KEY to .env (free tier)."
        )
    url = f"{BASE}/{path}"
    query = dict(params or {})
    query["token"] = key
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _requests.get(url, params=query, timeout=TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - network failure degrades
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"Benzinga network error: {exc}") from exc
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("benzinga", path, detail="non-JSON response") from None
        if resp.status_code == 429:
            if attempt < _MAX_RETRIES:
                import time

                time.sleep(2 * (attempt + 1))
                continue
            raise VendorRateLimitError(f"Benzinga rate limit (429) on {path}")
        if resp.status_code in (401, 403):
            raise VendorNotConfiguredError(
                f"Benzinga auth/forbidden (check BENZINGA_API_KEY): {resp.status_code}"
            )
        if resp.status_code != 200:
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"Benzinga {path}: status {resp.status_code}")
        if isinstance(data, list):
            return data
        # Some errors come as {"error": "..."} on 200.
        if isinstance(data, dict) and data.get("error"):
            raise NoMarketDataError("benzinga", path, detail=str(data["error"]))
        return None
    return None


def get_news_benzinga(ticker: str, start_date: str, end_date: str) -> str:
    """Ticker-scoped financial news via ``/v2/news``.

    Renders headline, timestamp, source and the free-tier teaser + link.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    items = _benzinga_get(
        "news",
        {"tickers": ticker, "dateFrom": start_date, "dateTo": end_date, "pageSize": _ARTICLE_LIMIT},
    )
    if not items:
        raise NoMarketDataError(
            ticker, "news", detail=f"no articles between {start_date} and {end_date}"
        )
    lines = [f"## {ticker} News — Benzinga", ""]
    shown = 0
    for item in items:
        if shown >= _ARTICLE_LIMIT:
            break
        shown += 1
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "(no title)")[:120]
        date = str(item.get("created") or item.get("updated") or "")[:16]
        source = str(item.get("author") or item.get("source") or "").strip()
        # Free tier: teaser + link, not full body.
        teaser = str(item.get("teaser") or item.get("body") or "").replace("\n", " ").strip()
        link = str(item.get("url") or item.get("link") or "")
        lines.append(f"- **{title}**  ({date} {source})")
        if teaser:
            lines.append(f"  {teaser[:200]}")
        if link and link != "None":
            lines.append(f"  url: {link}")
    return "\n".join(lines)


__all__ = ["get_news_benzinga", "benzinga_api_key"]
