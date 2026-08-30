from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


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
    return route_to_vendor("get_news", ticker, start_date, end_date)

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
    return route_to_vendor("get_global_news", curr_date, look_back_days, limit)

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
        return get_news_massive(ticker, start_date, end_date)
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
