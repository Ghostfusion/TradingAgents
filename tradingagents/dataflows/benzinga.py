"""Benzinga financial news vendor.

Benzinga returns ticker-scoped **financial** news with a headline, a link, the
author, the date and the tagged tickers. It is the rare free feed that is both
ticker-filtered and financial-first, so it slots in BEFORE the generic keyword
feeds in the ``news_data`` chain.

Endpoint: ``GET https://api.benzinga.com/api/v2/news`` with ``tickers``,
``dateFrom``/``dateTo`` and the ``token``.

**The response encoding is negotiated by header, not by parameter.** Benzinga's
default is XML; ``Accept: application/json`` is the only switch, and the
``format=json`` query parameter is silently ignored (measured 2026-09-20, see
``_HEADERS``). Without the header every call fails as ``non-JSON response``.

Key: ``BENZINGA_API_KEY`` in ``.env``. Raises the typed errors the router
understands so a 401/403/429/empty degrades to the next vendor — never a
fabricated value.

Measured on the live key 2026-09-20: the ``/v2/news`` payload carries ``title``,
``url``, ``created``, ``author``, ``stocks``, ``channels``, ``importance_rank``
and ``image``, while **``teaser`` and ``body`` come back as empty strings** — so
the render is headline + link, and it says so rather than implying a teaser.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

import requests as _requests

from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://api.benzinga.com/api/v2"
TIMEOUT = 20
_MAX_RETRIES = 2
_ARTICLE_LIMIT = 10
_BACKOFF_BASE = 2.0
_BACKOFF_CAP = 8.0

#: Benzinga's default response encoding is **XML**. Measured live 2026-09-20
#: against ``api.benzinga.com``:
#:
#:     no header                 -> 200  Content-Type: application/xml
#:     Accept: application/json  -> 200  Content-Type: application/json
#:     format=json               -> 200  Content-Type: application/xml  (IGNORED)
#:
#: ``format=json`` is a query parameter the vendor **silently ignores** - the
#: same "a parameter that does nothing is worse than a named gap" trap as
#: EODHD's ignored ``year``. The header is the only switch, so it is sent on
#: every request: without it ``resp.json()`` raises on an XML body, which the
#: status classifier below types as ``NoMarketDataError("non-JSON response")``
#: and the whole vendor degrades on every call.
_HEADERS = {"Accept": "application/json"}


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
        msg = data.get("error") or data.get("message")
        if msg:
            return str(msg)[:200]
    text = str(getattr(resp, "text", "") or "").strip().replace("\n", " ")
    return text[:200] if text else f"HTTP {resp.status_code}"


def _unescape(value) -> str:
    """Decode HTML entities a vendor ships in its own text.

    Benzinga escapes ampersands in headlines, so the raw field reads
    ``Technology Hardware, Storage &amp; Peripherals``. The render is markdown
    read by a human and by the analyst, so the entity is decoded rather than
    passed through as literal text.
    """
    import html

    return html.unescape(str(value or "")).replace("\n", " ").strip()


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
    """Authenticated GET ``BASE/{path}`` with token; parsed list or None.

    The HTTP status is classified *before* the body is parsed: parsing first
    turned an HTML 429/5xx page (proxy/Cloudflare) into a permanent
    ``NoMarketDataError``, i.e. a rate limit typed as "no data". Only
    transient statuses (429/5xx) and network errors are retried, with bounded
    exponential backoff.
    """
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
            resp = _requests.get(url, params=query, timeout=TIMEOUT, headers=_HEADERS)
        except Exception as exc:  # noqa: BLE001 - network failure degrades
            if attempt < _MAX_RETRIES:
                time.sleep(_backoff_seconds(attempt))
                continue
            raise VendorRateLimitError(f"Benzinga network error: {exc}") from exc

        status = resp.status_code
        if status in (401, 403):
            raise VendorNotConfiguredError(
                f"Benzinga auth/forbidden (check BENZINGA_API_KEY): {status}"
            )
        if status == 429 or status >= 500:
            if attempt < _MAX_RETRIES:
                time.sleep(_backoff_seconds(attempt))
                continue
            raise VendorRateLimitError(
                f"Benzinga {path}: status {status} - {_error_detail(resp)}"
            )
        if status != 200:
            # Non-retryable client error (400/404/...): permanent no-data.
            raise NoMarketDataError(
                "benzinga", path, detail=f"HTTP {status}: {_error_detail(resp)}"
            )
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("benzinga", path, detail="non-JSON response") from None
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
        # Titles arrive HTML-escaped ("Technology Hardware, Storage &amp;
        # Peripherals"). The render is markdown read by a human and by the
        # analyst, so the entity must be decoded or the reader sees `&amp;`.
        title = _unescape(item.get("title"))[:120] or "(no title)"
        date = str(item.get("created") or item.get("updated") or "")[:16]
        source = str(item.get("author") or item.get("source") or "").strip()
        # Headline + link on this tier; `teaser`/`body` come back as empty
        # strings, so the render emits nothing rather than a blank line.
        teaser = _unescape(item.get("teaser") or item.get("body"))
        link = str(item.get("url") or item.get("link") or "")
        lines.append(f"- **{title}**  ({date} {source})")
        if teaser:
            lines.append(f"  {teaser[:200]}")
        if link and link != "None":
            lines.append(f"  url: {link}")
    return "\n".join(lines)


__all__ = ["get_news_benzinga", "benzinga_api_key"]
