from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.dataflows.news_cache import CoalescingCache
from tradingagents.strategies import news_relevance

# Owner-wait coalescing TTL cache for identical news fetches (DSA pillar 9).
# Only engaged while enable_news_relevance is on: default path is untouched.
_NEWS_CACHE = CoalescingCache()


def _news_relevance_enabled() -> bool:
    try:
        return bool(get_config().get("enable_news_relevance", False))
    except Exception:  # noqa: BLE001 - advisory, degrade to off
        return False


# Cache-schema version (Vibe-Trading cache-version guard): part of every key.
# Bump when a stored news record's meaning changes so old entries can never
# resurface under a new schema.
_NEWS_CACHE_VERSION = 1


def _news_key(*parts) -> tuple:
    """Versioned cache key (schema version + call identity)."""
    return (_NEWS_CACHE_VERSION, *parts)


def _cached_news(parts: tuple, fn, *args) -> str:
    """Deduplicate identical concurrent fetches (one vendor call per key)."""
    if not _news_relevance_enabled():
        return fn(*args)
    return _NEWS_CACHE.fetch(_news_key(*parts), fn, *args)[0]


def _degrade_note(result: str) -> str:
    """Honesty fold (DSA degrade triple): 'no news' never means 'search failed'. """
    if not _news_relevance_enabled():
        return result
    low = (result or "").strip().lower()
    if not low:
        return result + "\n\n(relevance: empty - no articles retrieved; neutral, not a signal)"
    if any(m in low for m in ("no news found", "no global news", "no articles", "unavailable", "failed", "error")):
        label = news_relevance.degrade_triple(
            all_failed=any(m in low for m in ("failed", "error")),
            empty="no news" in low or "no articles" in low or "no global news" in low,
        )
        return result + f"\n\n(relevance: {label} - degrade triple; treat as neutral, not a directional signal)"
    return result


@tool
def get_news_relevance_read(
    title: Annotated[str, "Article title to classify"],
    ticker: Annotated[str, "Ticker symbol to score relevance against"],
    source_url: Annotated[str, "Source URL; the host is checked for official sources"] = "",
    snippet: Annotated[str, "Article snippet or abstract"] = "",
    company_name: Annotated[str, "Company name (e.g. 'Microsoft') to match in title/snippet"] = "",
) -> str:
    """
    Deterministic news-relevance read (DSA advisory): a 0-100 relevance score
    of one news item vs a ticker (code-in-title +55 / snippet +34 / URL +18,
    company-name +45 or +26 ambiguous / snippet +28 / +16, official-source +8,
    macro-term -12, clamped) with the admission verdict (official sources pass;
    spam/app-download signals drop) and official-source classification. The
    score is computed, never guessed - use it to rank a news batch for the
    highest-signal items before writing the report.
    """
    r = news_relevance.score_news_article(
        title=title, url=source_url, snippet=snippet,
        ticker=ticker, company_name=company_name,
    )
    admitted = news_relevance.admit_article(title, url=source_url)
    official = news_relevance.is_official(source_url)
    return "\n".join([
        f"Relevance score: {r['score']:.1f}/100",
        f"Admitted: {'yes' if admitted else 'no (spam/app-download signal)'}",
        f"Official source: {'yes' if official else 'no'}",
        f"Reasons: {', '.join(r['reasons']) or 'none'}",
    ])


@tool
def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve news data for a given ticker symbol.
    Uses the configured news_data vendor.
    Args:
        ticker (str): Ticker symbol
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted string containing news data
    """
    result = _cached_news(
        ("get_news", ticker, start_date, end_date),
        route_to_vendor, "get_news", ticker, start_date, end_date,
    )
    return _degrade_note(result)

@tool
def get_news_sentiment(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Daily news-sentiment series for a ticker (scale -1..1 unless noted): per-day
    mean score, 7-day SMA, latest innovation, article count. Uses the configured
    news_sentiment chain (EODHD /sentiments -> Alpha Vantage NEWS_SENTIMENT ->
    GDELT native tone). Cite before any "news sentiment is turning" claim; an
    explicit unavailable string when no feed has coverage.
    """
    return route_to_vendor("get_news_sentiment", ticker, start_date, end_date)


@tool
def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int | None, "Days to look back; omit to use the configured default"] = None,
    limit: Annotated[int | None, "Max articles to return; omit to use the configured default"] = None,
) -> str:
    """
    Retrieve global news data.
    Uses the configured news_data vendor. Defaults for look_back_days and
    limit come from DEFAULT_CONFIG (global_news_lookback_days,
    global_news_article_limit); pass explicit values to override.

    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Number of days to look back; omit to inherit config
        limit (int): Maximum number of articles to return; omit to inherit config

    Returns:
        str: A formatted string containing global news data
    """
    result = _cached_news(
        ("get_global_news", curr_date, look_back_days, limit),
        route_to_vendor, "get_global_news", curr_date, look_back_days, limit,
    )
    return _degrade_note(result)

@tool
def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve insider transaction information about a company.
    Uses the configured news_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
    Returns:
        str: A report of insider transaction data
    """
    return route_to_vendor("get_insider_transactions", ticker)


@tool
def get_massive_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve Massive.com news for a ticker with structured per-article sentiment
    (positive / negative / neutral) plus the provider's sentiment reasoning.

    Massive's news endpoint tags every article with the sentiment it assigns
    to each ticker, so this tool lets the news / sentiment analysts read a
    computed polarity instead of guessing from raw headlines.

    Args:
        ticker (str): Ticker symbol
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted string containing news data with sentiment labels
    """
    from tradingagents.dataflows.massive import get_news_massive

    try:
        return _degrade_note(get_news_massive(ticker, start_date, end_date))
    except Exception as exc:  # noqa: BLE001
        return f"massive news unavailable for {ticker}: {exc}"


@tool
def get_gdelt_sentiment(
    ticker: Annotated[str, "Ticker symbol"],
    look_back_days: Annotated[int, "Days of GDELT tone history to aggregate"] = 7,
) -> str:
    """
    GDELT native news-tone sentiment for a ticker: a daily average-tone series
    over the trailing ``look_back_days`` (keyless, free). GDELT's tone is a
    computer-coded -100..100 lexical sentiment score, so it is a *computed*
    sentiment read the analysts can cite (or see an explicit 'unavailable'
    when GDELT is unreachable/missing - never fabricated).

    Args:
        ticker (str): Ticker symbol
        look_back_days (int): Rolling window in days; default 7.
    Returns:
        str: GDELT daily tone series (+ latest), or an explicit 'unavailable'.
    """
    from tradingagents.dataflows.gdelt import get_gdelt_tone_series

    try:
        return get_gdelt_tone_series(ticker, look_back_days)
    except Exception as exc:  # noqa: BLE001 - degrade, never raise in the tool loop
        return f"gdelt sentiment unavailable for {ticker}: {exc}"
