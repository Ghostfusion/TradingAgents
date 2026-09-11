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
import time
from datetime import datetime

import requests as _requests

from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://newsapi.org/v2"
TIMEOUT = 20
_MAX_RETRIES = 2
_ARTICLE_LIMIT = 10
_BACKOFF_BASE = 2.0
_BACKOFF_CAP = 8.0


def _backoff_seconds(attempt: int) -> float:
    """Bounded exponential backoff for retry ``attempt`` (0-based)."""
    return min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_CAP)


def _error_detail(resp) -> str:
    """Human detail for a failed response; the body is used as text only."""
    try:
        data = resp.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        msg = data.get("message") or data.get("error")
        if msg:
            return str(msg)[:200]
    text = str(getattr(resp, "text", "") or "").strip().replace("\n", " ")
    return text[:200] if text else f"HTTP {resp.status_code}"


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
    """Authenticated GET; parsed JSON dict or None on any non-data failure.

    The HTTP status is classified *before* the body is parsed: parsing first
    turned an HTML 429/5xx page (proxy/Cloudflare) into a permanent
    ``NoMarketDataError``, i.e. a rate limit typed as "no data". Only
    transient statuses (429/5xx) and network errors are retried, with bounded
    exponential backoff.
    """
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
                time.sleep(_backoff_seconds(attempt))
                continue
            raise VendorRateLimitError(f"NewsAPI network error: {exc}") from exc

        status = resp.status_code
        if status in (401, 403):
            raise VendorNotConfiguredError(
                f"NewsAPI auth/forbidden (check NEWSAPI_API_KEY): {status}"
            )
        if status == 429 or status >= 500:
            if attempt < _MAX_RETRIES:
                time.sleep(_backoff_seconds(attempt))
                continue
            raise VendorRateLimitError(
                f"NewsAPI {path}: status {status} - {_error_detail(resp)}"
            )
        if status != 200:
            # Non-retryable client error (400/404/...): permanent no-data.
            raise NoMarketDataError(
                "newsapi", path, detail=f"HTTP {status}: {_error_detail(resp)}"
            )
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("newsapi", path, detail="non-JSON response") from None
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
