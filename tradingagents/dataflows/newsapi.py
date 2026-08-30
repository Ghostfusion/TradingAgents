"""NewsAPI.org vendor (free Developer plan: 100 requests/day).

Global + national news headlines across ~150k sources. The free plan serves
development / light workloads, so it is wired as a *last* fallback for
``get_global_news`` (and optionally ``get_news`` via keyword search for the
macro/news analysts). Key: ``NEWSAPI_API_KEY`` in ``.env``.

Endpoints:
- ``/v2/top-headlines`` (country/category) for global/macro headlines.
- ``/v2/everything`` (keyword search) for macro-topic queries.

Raises the typed errors the router understands so a 401/429/empty degrades to
the next vendor — never a fabricated value.
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests as _requests

from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://newsapi.org/v2"
TIMEOUT = 20
_MAX_RETRIES = 2
_ARTICLE_LIMIT = 10


def newsapi_api_key() -> str | None:
    """NewsAPI key from config or environment; None when unset."""
    import os

    try:
        from .config import get_config

        cfg = get_config()
        val = cfg.get("newsapi_api_key")
        if val:
            return str(val)
    except Exception:  # noqa: BLE001 - config is best-effort
        pass
    return os.environ.get("NEWSAPI_API_KEY")


def _newsapi_get(path: str, params: dict | None = None) -> dict | None:
    """Authenticated GET; parsed JSON dict or None on any non-data failure."""
    key = newsapi_api_key()
    if not key:
        raise VendorNotConfiguredError(
            "NewsAPI key is not set. Add NEWSAPI_API_KEY to .env."
        )
    url = f"{BASE}/{path}"
    query = dict(params or {})
    query["apiKey"] = key
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _requests.get(url, params=query, timeout=TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - network failure degrades
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"NewsAPI network error: {exc}") from exc
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("newsapi", path, detail="non-JSON response") from None
        if resp.status_code == 429:
            if attempt < _MAX_RETRIES:
                import time

                time.sleep(2 * (attempt + 1))
                continue
            raise VendorRateLimitError(f"NewsAPI rate limit (429) on {path}")
        if resp.status_code in (401, 403):
            raise VendorNotConfiguredError(
                f"NewsAPI auth/forbidden (check NEWSAPI_API_KEY): {resp.status_code}"
            )
        if resp.status_code == 400:
            raise NoMarketDataError("newsapi", path, detail=str(data.get("message") or "bad request"))
        if resp.status_code != 200:
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"NewsAPI {path}: status {resp.status_code}")
        if not isinstance(data, dict):
            raise NoMarketDataError("newsapi", path, detail="malformed response")
        if data.get("status") == "error":
            raise NoMarketDataError("newsapi", path, detail=str(data.get("message") or "error"))
        return data
    return None


def _render_articles(title_label: str, articles: list, limit: int = _ARTICLE_LIMIT) -> str:
    rows = [f"## {title_label} — NewsAPI.org", ""]
    shown = 0
    for a in articles:
        if shown >= limit:
            break
        shown += 1
        if not isinstance(a, dict):
            continue
        title = str(a.get("title") or "(no title)")[:140]
        source = (a.get("source") or {}).get("name") if isinstance(a.get("source"), dict) else ""
        desc = str(a.get("description") or "").replace("\n", " ").strip()[:200]
        url = str(a.get("url") or "")
        published = str(a.get("publishedAt") or "")[:16]
        rows.append(f"- **{title}**  ({published} {source})")
        if desc:
            rows.append(f"  {desc}")
        if url and url != "None":
            rows.append(f"  url: {url}")
    return "\n".join(rows)


def get_global_news_newsapi(
    curr_date: str, look_back_days: int | None = None, limit: int | None = None
) -> str:
    """Top business + macro headlines (global) via ``/v2/top-headlines``.

    Uses the business category + a small set of macro keywords through
    ``/v2/everything`` so the macro/news analysts get a deterministic-format
    global read. Respects the config look-back / article defaults.
    """
    datetime.strptime(curr_date, "%Y-%m-%d")
    lb = look_back_days or 7
    lim = limit or _ARTICLE_LIMIT
    # Macro-economics keyword query for the news analyst.
    data = _newsapi_get(
        "everything",
        {
            "q": '(economy OR inflation OR "interest rates" OR fed OR gdp)',
            "from": (datetime.strptime(curr_date, "%Y-%m-%d") - __import__("datetime").timedelta(days=lb)).strftime("%Y-%m-%d"),
            "to": curr_date,
            "sortBy": "publishedAt",
            "pageSize": min(lim, 100),
            "language": "en",
        },
    )
    articles = (data or {}).get("articles") or []
    if not articles:
        return f"No global news for {curr_date} (NewsAPI)"
    return _render_articles("Global Macro News", articles, lim)


def get_news_newsapi(ticker: str, start_date: str, end_date: str) -> str:
    """Keyword-scoped news for a ticker via ``/v2/everything`` (ticker search).

    Useful as a supplementary ticker-news source (avoiding the free plan's 100
    req/day by keeping it last). GDELT / Massive / Benzinga are preferred for
    ticker news; NewsAPI is keyword-based.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    data = _newsapi_get(
        "everything",
        {
            "q": ticker,
            "from": start_date,
            "to": end_date,
            "sortBy": "publishedAt",
            "pageSize": _ARTICLE_LIMIT,
            "language": "en",
        },
    )
    articles = (data or {}).get("articles") or []
    if not articles:
        raise NoMarketDataError(ticker, "everything", detail="no articles")
    return _render_articles(f"{ticker} News", articles)


__all__ = ["get_news_newsapi", "get_global_news_newsapi", "newsapi_api_key"]
