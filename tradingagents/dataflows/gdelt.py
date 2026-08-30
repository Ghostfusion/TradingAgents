"""GDELT news + native tone/sentiment vendor (free, no API key).

GDELT DOC 2.0 is a fully free, keyless full-text news search API covering a
rolling ~3-month window across 65 translated languages. Crucially for this
project it returns a computer-coded **tone** for each article (avg tone,
positive/negative/hit quotas, emotional lexicons) - a *computed* sentiment the
analysts can cite rather than one they must guess from headlines (the same
no-fabrication value as Massive's per-article sentiment).

Endpoints used:
- ``/api/v2/doc/doc`` with ``mode=artlist`` (article list) + ``format=json``
  -> headline, URL, date, source + native tone fields.

News asset = ticker keywords OR the company name; GDELT is keyword-based (no
legal-entity ticker map), so we pass the ticker verbatim and let the tone be
the signal. Missing / malformed data degrades to the typed errors the router
understands (never a fabricated value).
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests as _requests

from .errors import NoMarketDataError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
# GDELT's endpoint is historically network-flaky (connect timeouts). Keep the
# per-call timeout short and fail fast so an opt-in run degrades to the next
# vendor instead of stalling the news fetch for tens of seconds.
TIMEOUT = 8
_MAX_RETRIES = 1
_ARTICLE_LIMIT = 8


def _gdelt_get(params: dict) -> list | None:
    """GET the DOC 2.0 endpoint; return the ``articles`` list or None.

    GDELT has no key; it signals rate limiting and errors via HTTP status or
    an ``Error`` field in the JSON body.
    """
    url = BASE
    query = dict(params or {})
    query.update({"mode": "artlist", "format": "json"})
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _requests.get(url, params=query, timeout=TIMEOUT)
        except Exception as exc:  # noqa: BLE001 - network failure degrades
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"GDELT network error: {exc}") from exc
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("gdelt", "doc", detail="non-JSON response") from None
        if resp.status_code == 429:
            if attempt < _MAX_RETRIES:
                import time

                time.sleep(2 * (attempt + 1))
                continue
            raise VendorRateLimitError("GDELT rate limit (429)")
        if resp.status_code != 200:
            # Any non-200 with an error body -> degrade (no data to report).
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"GDELT doc: status {resp.status_code}")
        if not isinstance(data, dict):
            raise NoMarketDataError("gdelt", "doc", detail="malformed response")
        if isinstance(data.get("Error"), str) and data["Error"]:
            raise NoMarketDataError("gdelt", "doc", detail=data["Error"])
        articles = data.get("articles")
        if isinstance(articles, list):
            return articles
        return None
    return None


def _fmt_name(ticker: str) -> str:
    """Ticker -> a keyword GDELT can match. For a plain alphabetic ticker use
    it verbatim (quoted to force a phrase match where sensible)."""
    return f'"{ticker}"'


def get_news_gdelt(ticker: str, start_date: str, end_date: str) -> str:
    """News + native GDELT tone for a ticker over [start_date, end_date].

    Renders each article with headline, date, source, URL and the tone block
    (avg tone, positive %, negative %, neutral %) - the shape the news /
    sentiment analysts consume. GDELT keeps only a rolling ~3-month window; a
    request outside it degrades to NoMarketDataError -> next vendor.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    articles = _gdelt_get(
        {
            "query": _fmt_name(ticker),
            "startdatetime": start_date + "000000",
            "enddatetime": end_date + "235959",
            "maxrecords": _ARTICLE_LIMIT,
        }
    )
    if not articles:
        raise NoMarketDataError(
            ticker, "doc", detail=f"no articles between {start_date} and {end_date}"
        )
    lines = [f"## {ticker} News — GDELT (native tone)", ""]
    for _shown, a in enumerate(articles):
        if _shown >= _ARTICLE_LIMIT:
            break
        title = str(a.get("title") or "(no title)")[:120]
        url = str(a.get("url") or "")
        source = str(a.get("source") or "").split("/")[-1] or ""
        date = str(a.get("seendate") or "")[:8]
        # GDELT native tone fields.
        tone = a.get("tone")  # "avg_tone,pos,neg,neutral"
        tone_str = "n/a"
        if isinstance(tone, str) and "," in tone:
            t = [x.strip() for x in tone.split(",")]
            tone_str = f"avg={t[0]} pos={t[1] if len(t) > 1 else '?'} neg={t[2] if len(t) > 2 else '?'} neu={t[3] if len(t) > 3 else '?'}"
        lines.append(f"- **{title}**  ({date} {source})")
        lines.append(f"  tone: {tone_str}")
        if url:
            lines.append(f"  url: {url}")
    return "\n".join(lines)


def get_gdelt_tone_series(ticker: str, look_back_days: int = 7) -> str:
    """Daily GDELT tone timeline for a ticker (avg tone per day) over the
    trailing ``look_back_days``. A computed sentiment series the sentiment
    analyst can cite (trend + latest)."""
    end = datetime.now()
    start = end - __import__("datetime").timedelta(days=look_back_days + 1)
    s = start.strftime("%Y-%m-%d")
    e = end.strftime("%Y-%m-%d")
    articles = _gdelt_get(
        {
            "query": _fmt_name(ticker),
            "startdatetime": s + "000000",
            "enddatetime": e + "235959",
            "maxrecords": 50,
        }
    ) or []
    if not articles:
        return f"gdelt tone unavailable for {ticker}: no coverage in trailing {look_back_days}d (GDELT keeps ~3 months)"
    # Aggregate avg tone per calendar day.
    from collections import defaultdict

    per_day = defaultdict(list)
    for a in articles:
        t = (a.get("tone") or "") if isinstance(a.get("tone"), str) else ""
        parts = t.split(",")
        if parts and _is_num(parts[0]):
            date = str(a.get("seendate") or "")[:8]
            per_day[date].append(float(parts[0]))
    if not per_day:
        return f"gdelt tone unavailable for {ticker}: tone fields missing"
    lines = [f"gdelt tone series {ticker} (avg per day, trailing {look_back_days}d):"]
    for day in sorted(per_day)[-look_back_days:]:
        vals = per_day[day]
        avg = sum(vals) / len(vals)
        lines.append(f"  {day}: {avg:.2f} (n={len(vals)})")
    latest = lines[-1]
    return "\n".join(lines) + "\n  latest=" + latest.split(": ", 1)[-1]


def _is_num(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


__all__ = [
    "get_news_gdelt",
    "get_gdelt_tone_series",
]
