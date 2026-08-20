"""Massive.com data vendor: U.S. news with native sentiment (first integration).

Massive (``api.massive.com``, the renamed Polygon.io lineage) is a U.S.-centric
market-data provider. This module starts with the highest-leverage data it
exposes for TradingAgents: per-ticker news with **structured sentiment** from
the ``/v2/reference/news`` endpoint. Every article carries ``insights[]`` with
a ``sentiment`` (positive/negative/neutral) plus a ``sentiment_reasoning``
string, so the Sentiment and News analysts can read a computed signal instead
of guessing polarity from raw headlines.

Follows the vendor taxonomy in ``errors.py`` like the other vendors:

- a missing key raises ``MassiveNotConfiguredError`` so the routing layer treats
  the vendor as "unavailable" instead of crashing;
- empty / no-usable-rows raises ``NoMarketDataError`` so the router emits an
  honest "no data" signal rather than an empty string;
- transient 429 throttling surfaces as ``VendorRateLimitError`` so the router
  degrades to the next vendor instead of failing a run.

Scope note: Massive is US-centric. It is deliberately additive to the existing
moomoo/yfinance coverage (which handle HK/JP/IN/SS/SZ/etc.), not a replacement,
and production users must pick a plan whose recency (15-min delayed vs
real-time) matches the use case.
"""

from __future__ import annotations

import logging
import os
import time

import requests

from .config import get_config
from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://api.massive.com"
TIMEOUT = 20
_MAX_RETRIES = 2
_NEWS_LIMIT = 10  # default articles requested per query

# Possible sentiment values the provider returns.
_VALID_SENTIMENTS = {"positive", "negative", "neutral"}


class MassiveNotConfiguredError(VendorNotConfiguredError):
    """Raised when Massive is selected but no API key is configured.

    A ``VendorNotConfiguredError`` (and thus still a ValueError), so the routing
    layer's "vendor unavailable" handling and existing ValueError callers both
    keep working.
    """


def massive_api_key() -> str | None:
    """Massive key from config or environment; None when unset.

    Resolves from (1) the ``massive_api_key`` config key, then (2) env
    ``MASSIVE_API_KEY``. This mirrors the finnhub/fmp key resolution so the key
    stays in .env (gitignored) and never in code.
    """
    try:
        key = get_config().get("massive_api_key")
    except Exception:
        key = None
    if key:
        return str(key)
    return os.environ.get("MASSIVE_API_KEY")


def _get(path: str, params: dict | None = None) -> list | dict | None:
    """Authenticated GET; parsed JSON or None on any non-data failure.

    Raises no-network errors via the typed taxonomy on the way out:
    401/403 -> VendorNotConfigured-ish, 429 -> VendorRateLimitError, empty
    result conventions are left to the caller.
    """
    key = massive_api_key()
    if not key:
        raise MassiveNotConfiguredError(
            "Massive API key is not configured. Set MASSIVE_API_KEY in .env "
            "(or massive_api_key in config)."
        )
    url = f"{BASE}{path}"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if resp.status_code in (401, 403):
                # Access-denied (403) can also be an entitlements gap — the key
                # is valid but the account's plan lacks the requested endpoint.
                logger.warning(
                    "Massive auth/entitlement %s for %s; check MASSIVE_API_KEY "
                    "and the account plan.",
                    resp.status_code,
                    path,
                )
                raise MassiveNotConfiguredError(
                    f"Massive returned HTTP {resp.status_code} (bad key or "
                    "plan lacks this dataset)"
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < _MAX_RETRIES:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise VendorRateLimitError(
                    f"Massive {path} returned HTTP {resp.status_code}"
                )
            if resp.status_code != 200:
                logger.warning("Massive %s: status %s", path, resp.status_code)
                return None
            return resp.json()
        except MassiveNotConfiguredError:
            raise
        except VendorRateLimitError:
            raise
        except requests.Timeout as exc:
            raise VendorRateLimitError(f"Massive {path} timed out") from exc
        except requests.RequestException as exc:
            if attempt < _MAX_RETRIES:
                logger.warning("Massive %s transient: %s; retrying", path, exc)
                continue
            logger.warning("Massive %s failed after retries: %s", path, exc)
            return None
    return None


def _requested_ticker_in(article: dict, ticker: str) -> bool:
    """True when ``ticker`` appears in the article's tickers or insights."""
    tickers = article.get("tickers") or []
    if ticker.lower() in [t.lower() for t in tickers]:
        return True
    for insight in article.get("insights") or []:
        if (insight.get("ticker") or "").lower() == ticker.lower():
            return True
    return False


def get_news_massive(
    ticker: str, start_date: str, end_date: str, limit: int = _NEWS_LIMIT
) -> str:
    """Retrieve recent news articles with structured sentiment for a ticker.

    Filters the provider's multi-ticker articles down to rows tagged with the
    requested symbol, and renders each article's sentiment + reasoning so the
    news / sentiment analysts read a computed polarity rather than raw prose.

    Args:
        ticker: Case-sensitive symbol (AAPL).
        start_date / end_date: yyyy-mm-dd publishing window.
        limit: cap on articles fetched before the ticker filter.

    Returns a formatted markdown report, or raises ``NoMarketDataError`` when
    no article matches the ticker.
    """
    payload = _get(
        "/v2/reference/news",
        {
            "ticker": ticker,
            "published_utc.gte": f"{start_date}T00:00:00Z",
            "published_utc.lte": f"{end_date}T23:59:59Z",
            "limit": limit,
        },
    )
    articles = (payload or {}).get("results") if isinstance(payload, dict) else payload
    if not isinstance(articles, list) or not articles:
        raise NoMarketDataError(
            ticker, detail=f"Massive returned no news for {start_date}..{end_date}"
        )

    relevant = [a for a in articles if _requested_ticker_in(a, ticker)]
    if not relevant:
        raise NoMarketDataError(
            ticker,
            detail=f"Massive returned news but none tagged with {ticker} "
            f"(provider articles carry multiple tickers)",
        )

    lines = [
        f"## {ticker} Massive.com news with sentiment ({start_date} to {end_date}):",
        "",
    ]
    for article in relevant:
        title = article.get("title", "No Title")
        published = article.get("published_utc", "")
        pub = article.get("publisher") or {}
        source = pub.get("name", "")
        url = article.get("article_url", "")
        lines.append(f"### {title}")
        if published:
            lines.append(f"Published: {published}")
        if source:
            lines.append(f"Source: {source}")
        desc = article.get("description")
        if desc:
            lines.append(f"{desc}")
        # Only surface the sentiment tagged for THIS ticker.
        own_insight = None
        for insight in article.get("insights") or []:
            if (insight.get("ticker") or "").lower() == ticker.lower():
                own_insight = insight
                break
        if own_insight:
            sentiment = own_insight.get("sentiment", "")
            reasoning = own_insight.get("sentiment_reasoning", "")
            tag = sentiment if sentiment in _VALID_SENTIMENTS else "unavailable"
            lines.append(f"Sentiment: {tag}")
            if reasoning:
                lines.append(f"Sentiment reasoning: {reasoning}")
        if url:
            lines.append(f"Link: {url}")
        lines.append("")
    return "\n".join(lines)


__all__ = ["get_news_massive", "massive_api_key", "MassiveNotConfiguredError"]
