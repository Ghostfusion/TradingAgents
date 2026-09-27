"""GDELT news vendor (free, no API key).

GDELT DOC 2.0 is a fully free, keyless full-text news search API covering a
rolling ~3-month window across 65 translated languages.

**What this vendor does and does not deliver (measured against GDELT's own
documentation, 2026-09-27).** The ``mode=artlist`` response used here carries
article metadata only - ``url``/``url_mobile``/``title``/``seendate``/
``socialimage``/``domain``/``language``/``sourcecountry``. It carries **no
per-article tone**: GDELT's ``tone`` is a *query filter and sort* (``tone<-5``,
``sort=tonedesc``) plus the separate ``mode=timelineTone``/``mode=tonechart``
outputs and the GKG dataset. So the tone surfaces (``get_gdelt_tone_series``,
``_sentiment_points_gdelt``) refuse with that reason instead of parsing a field
that is not there; wiring ``mode=timelineTone`` is a separate change that needs a
live probe (GDELT answers 429 to this host, 2026-09-27). Nothing is inferred
from a headline.

Endpoints used:
- ``/api/v2/doc/doc`` with ``mode=artlist`` (article list) + ``format=json``
  -> headline, URL, date, source, domain, language.

News asset = ticker keywords OR the company name; GDELT is keyword-based (no
legal-entity ticker map), so we pass the ticker verbatim.
``get_global_news_gdelt`` serves the router's macro
``get_global_news(curr_date, look_back_days, limit)`` contract from the
configured ``global_news_queries``. Missing / malformed data degrades to the
typed errors the router understands (never a fabricated value).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import requests as _requests

from .config import get_config
from .errors import NoMarketDataError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
# GDELT's endpoint is historically network-flaky (connect timeouts). Keep the
# per-call timeout short and fail fast so an opt-in run degrades to the next
# vendor instead of stalling the news fetch for tens of seconds.
TIMEOUT = 8
_MAX_RETRIES = 1
_ARTICLE_LIMIT = 8
# GDELT DOC 2.0 accepts at most 250 records per request.
_MAXARTICLE_LIMIT = 250


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
        # Status BEFORE the body parse. GDELT answers a rate-limited request with
        # a plain-text 429 body and no content-type (measured live 2026-09-27), so
        # a `resp.json()` first classified its rate limit as "non-JSON response" -
        # a no-data verdict that skips the rate-limit path entirely.
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
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("gdelt", "doc", detail="non-JSON response") from None
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


def _doc_datetime(date_str: str, *, last: bool) -> str:
    """``YYYY-MM-DD`` -> the DOC API's own ``YYYYMMDDHHMMSS`` window stamp.

    ``STARTDATETIME``/``ENDDATETIME`` are documented as ``YYYYMMDDHHMMSS``; the
    previous call sites assembled ``YYYY-MM-DD`` + ``"000000"``, a string that is
    not that format. A window the API cannot read is a window it does not apply,
    and for a historical run that is the lookahead class this repo treats as
    critical - so the form is built here and raises ValueError on a bad date
    rather than reaching the wire.
    """
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d") + (
        "235959" if last else "000000"
    )


def _render_articles(header: str, articles: list, limit: int) -> str:
    """Headline/date/source/URL for each GDELT article.

    Shared by the ticker-news and global-news surfaces. No tone line: the
    ``mode=artlist`` response carries none (module docstring).
    """
    lines = [f"## {header}", ""]
    for index, article in enumerate(articles):
        if index >= limit:
            break
        title = str(article.get("title") or "(no title)")[:120]
        url = str(article.get("url") or "")
        source = str(article.get("source") or "").split("/")[-1] or ""
        date = str(article.get("seendate") or "")[:8]
        lines.append(f"- **{title}**  ({date} {source})")
        if url:
            lines.append(f"  url: {url}")
    return "\n".join(lines)


def get_news_gdelt(ticker: str, start_date: str, end_date: str) -> str:
    """Headlines for a ticker over [start_date, end_date] (the DOC article list).

    Renders each article's headline, date, source and URL. The ``mode=artlist``
    response carries no per-article tone, so no polarity is printed or implied.
    GDELT keeps only a rolling ~3-month window; a request outside it degrades to
    NoMarketDataError -> next vendor.
    """
    articles = _gdelt_get(
        {
            "query": _fmt_name(ticker),
            "startdatetime": _doc_datetime(start_date, last=False),
            "enddatetime": _doc_datetime(end_date, last=True),
            "maxrecords": _ARTICLE_LIMIT,
        }
    )
    if not articles:
        raise NoMarketDataError(
            ticker, "doc", detail=f"no articles between {start_date} and {end_date}"
        )
    return _render_articles(f"{ticker} News — GDELT", articles, _ARTICLE_LIMIT)


def _fmt_query(query: str) -> str:
    """One macro search phrase -> a GDELT query term (spaces -> phrase)."""
    text = str(query or "").strip()
    if not text:
        return ""
    return f'"{text}"' if " " in text else text


def get_global_news_gdelt(curr_date: str, look_back_days: int | None = None,
                          limit: int | None = None) -> str:
    """Global/macro headlines for the router's ``get_global_news`` contract
    ``(curr_date, look_back_days, limit)``.

    GDELT has no macro feed (it is a keyword engine), so coverage comes from the
    configured ``global_news_queries`` OR-joined into one query over the
    trailing window ending at ``curr_date``; ``look_back_days`` / ``limit``
    default to ``global_news_lookback_days`` / ``global_news_article_limit``.
    The ``mode=artlist`` response carries no per-article tone, so none is
    printed. No coverage degrades to NoMarketDataError -> the router tries the
    next vendor (never a fabricated headline).
    """
    datetime.strptime(curr_date, "%Y-%m-%d")
    config = get_config()
    if look_back_days is None:
        look_back_days = config["global_news_lookback_days"]
    if limit is None:
        limit = config["global_news_article_limit"]
    query = " OR ".join(
        q for q in (_fmt_query(q) for q in config["global_news_queries"]) if q
    )
    if not query:
        raise NoMarketDataError(
            curr_date, "doc", detail="no global_news_queries configured"
        )
    start = (
        datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=int(look_back_days))
    ).strftime("%Y-%m-%d")
    articles = _gdelt_get(
        {
            "query": query,
            "startdatetime": _doc_datetime(start, last=False),
            "enddatetime": _doc_datetime(curr_date, last=True),
            "maxrecords": max(1, min(int(limit), _MAXARTICLE_LIMIT)),
        }
    )
    if not articles:
        raise NoMarketDataError(
            curr_date, "doc", detail=f"no macro articles between {start} and {curr_date}"
        )
    return _render_articles(
        f"Global Macro News {start} to {curr_date} — GDELT",
        articles,
        int(limit),
    )


#: Why the tone surfaces cannot measure. The DOC ``mode=artlist`` response this
#: vendor reads carries no per-article tone - GDELT's ``tone`` is a query
#: filter and sort, and a per-day series needs ``mode=timelineTone`` (or the GKG
#: dataset), which is a separate, unwired call. Stated once so every refusing
#: surface cites the same reason instead of a data-gap that does not exist.
_NO_ARTICLE_TONE = (
    "the GDELT DOC 2.0 article-list response this vendor reads carries no "
    "per-article tone (tone is a query filter/sort there; a per-day series needs "
    "mode=timelineTone, not wired) - no headline-derived substitute is invented"
)


def get_gdelt_tone_series(ticker: str, look_back_days: int = 7) -> str:
    """Unavailable: there is no per-article tone on this path (``_NO_ARTICLE_TONE``).

    Kept as a named surface because the news tool and the analyst prompt
    reference it; the honest output is the reason, never a series inferred from
    headlines. Wiring GDELT's own tone mode (``mode=timelineTone``) is what would
    make this measurable, and it needs its own live probe.
    """
    return f"gdelt tone unavailable for {ticker}: {_NO_ARTICLE_TONE}"


def _sentiment_points_gdelt(ticker: str, start_date: str, end_date: str) -> list[dict] | None:
    """Always None: this path has no per-article tone (``_NO_ARTICLE_TONE``).

    Kept as the news-sentiment chain's GDELT leg so the router's fall-through is
    explicit, and logged so a run's journal names the reason rather than looking
    like a vendor that merely had no coverage. A caller reads None as "no data",
    which is the truth here. The native-scale/-100..100 note that used to live on
    this function applies to GDELT's tone mode once it is wired, not to now.
    """
    logger.info(
        "gdelt: no sentiment points for %s (%s..%s): %s",
        ticker,
        start_date,
        end_date,
        _NO_ARTICLE_TONE,
    )
    return None


_GDELT_TRANSFORM = "native tone -100..100 divided by 100 via sentiment_score.normalise_sentiment"


def _gdelt_unit_points(points: list[dict]) -> list[dict]:
    """GDELT native-tone points -> the canonical unit scale (-1..1).

    Reuses ``strategies.sentiment_score.normalise_sentiment`` (the engine's one
    scale table, the same mapping ``SCALE_TABLE["gdelt"]`` pins) rather than a
    second one, so a GDELT ``sma_7d``/``innovation`` is directly comparable to an
    EODHD/Alpha Vantage one. A point the engine cannot read is dropped, never
    replaced with 0 (``NA != 0``).
    """
    from tradingagents.strategies.sentiment_score import normalise_sentiment

    out: list[dict] = []
    for p in points or []:
        unit = normalise_sentiment(p.get("score"), "gdelt")
        if unit["value"] is None:
            continue
        out.append({"date": p["date"], "score": unit["value"], "n": p.get("n")})
    return out


def get_news_sentiment_gdelt(ticker: str, start_date: str, end_date: str) -> str:
    """Daily news-tone series on the canonical unit scale (-1..1) + 7-day SMA.

    The transform is the substance: GDELT's tone output is on -100..100 while the
    EODHD/Alpha Vantage feeds that share this route deliver -1..1, so a series is
    normalised (``_gdelt_unit_points``, i.e.
    ``sentiment_score.normalise_sentiment(_, "gdelt")``) **before** it is
    aggregated, and the transform is named in the returned text so a reader can
    never compare a GDELT ``sma_7d`` with an unnormalised EODHD one.

    The GDELT leg of this chain cannot measure today (``_NO_ARTICLE_TONE``), so
    the honest output is that reason; the transform below is what a wired tone
    mode would feed, and is exercised by the recorded native-scale points the
    tests supply.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    points = _sentiment_points_gdelt(ticker, start_date, end_date)
    if not points:
        return f"gdelt sentiment unavailable for {ticker}: {_NO_ARTICLE_TONE}"
    unit_points = _gdelt_unit_points(points)
    if not unit_points:
        return (
            f"gdelt sentiment unavailable for {ticker}: tone present but "
            f"unreadable on the native -100..100 scale"
        )
    from tradingagents.strategies.sentiment import daily_sentiment_sma

    series = daily_sentiment_sma(unit_points, window=7) or [
        {"date": p["date"], "score": p["score"], "sma_7d": None, "innovation": None, "n": p["n"]}
        for p in unit_points
    ]
    lines = [
        f"## {ticker} Daily News Tone — GDELT (unit scale -1..1; {_GDELT_TRANSFORM})",
        "",
    ]
    lines.append("| date | tone | sma_7d | innovation | articles |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in series:
        sc = f"{r['score']:+.2f}" if r["score"] is not None else "n/a"
        sma = f"{r['sma_7d']:+.2f}" if r["sma_7d"] is not None else "n/a"
        inn = f"{r['innovation']:+.2f}" if r["innovation"] is not None else "n/a"
        lines.append(f"| {r['date']} | {sc} | {sma} | {inn} | {r['n']} |")
    latest = series[-1]
    # .4f at the source: a computed tone's repr leaks 17 digits into the
    # prompt, and the analysts copy tool numbers verbatim by rule (the same
    # leak reached AMZN news.md prose via the EODHD sibling, 2026-09-14).
    tone = f"{latest['score']:.4f}" if latest["score"] is not None else "n/a"
    sma = f"{latest['sma_7d']:.4f}" if latest["sma_7d"] is not None else "n/a"
    tail = ["", f"- latest tone {tone}, 7d SMA {sma} (unit scale -1..1; {_GDELT_TRANSFORM})"]
    if latest.get("innovation") is not None:
        tail.append(f"- latest tone innovation {latest['innovation']:+.2f}")
    return "\n".join(lines + tail)


__all__ = [
    "get_news_gdelt",
    "get_global_news_gdelt",
    "get_gdelt_tone_series",
]
