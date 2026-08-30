from .alpha_vantage_common import _make_api_request, format_datetime_for_api
from .errors import NoMarketDataError


def _sentiment_points_alpha_vantage(
    ticker: str, start_date: str, end_date: str
) -> list[dict] | None:
    """Daily aggregated sentiment from the NEWS_SENTIMENT feed.

    Parses ``ticker_sentiment[]`` into per-day mean scores (-1..1) with the
    post-16:00 ET next-day bucket (lookahead guard). Returns
    ``[{"date", "score", "n", "used_overall"}]`` or None.
    """
    from tradingagents.strategies.sentiment import aggregate_daily_sentiment

    raw = get_news(ticker, start_date, end_date)
    if isinstance(raw, str):
        raise NoMarketDataError(ticker, "news_sentiment", detail="AV returned an error string")
    articles = raw.get("feed") if isinstance(raw, dict) else None
    if not articles:
        raise NoMarketDataError(ticker, "news_sentiment", detail="empty feed")
    days = aggregate_daily_sentiment(articles, ticker=ticker)
    if not days:
        raise NoMarketDataError(ticker, "news_sentiment", detail="no usable scores")
    return [{"date": d["date"], "score": d["score"], "n": d["n"]} for d in days]


def get_news_sentiment_alpha_vantage(ticker: str, start_date: str, end_date: str) -> str:
    """Daily news-sentiment series (NEWS_SENTIMENT feed) - scale -1..1.

    Renders the daily mean + 7-day SMA + latest innovation + article count.
    Free tier is 25 req/day -> this sits last in the news_sentiment chain.
    """
    points = _sentiment_points_alpha_vantage(ticker, start_date, end_date)
    if not points:
        return f"News sentiment unavailable for {ticker} (Alpha Vantage)"
    from tradingagents.strategies.sentiment import daily_sentiment_sma

    series = daily_sentiment_sma(points, window=7) or [
        {"date": p["date"], "score": p["score"], "sma_7d": None, "innovation": None, "n": p["n"]}
        for p in points
    ]
    lines = [f"## {ticker} Daily News Sentiment — Alpha Vantage (scale -1..1)", ""]
    lines.append("| date | score | sma_7d | innovation | articles |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in series:
        sc = f"{r['score']:+.2f}" if r["score"] is not None else "n/a"
        sma = f"{r['sma_7d']:+.2f}" if r["sma_7d"] is not None else "n/a"
        inn = f"{r['innovation']:+.2f}" if r["innovation"] is not None else "n/a"
        lines.append(f"| {r['date']} | {sc} | {sma} | {inn} | {r['n']} |")
    latest = series[-1]
    tail = [
        "",
        f"- latest score {latest['score'] if latest['score'] is not None else 'n/a'}, "
        f"7d SMA {latest['sma_7d'] if latest['sma_7d'] is not None else 'n/a'}",
    ]
    if latest.get("innovation") is not None:
        tail.append(f"- latest sentiment innovation {latest['innovation']:+.2f}")
    return "\n".join(lines + tail)


def get_news(ticker, start_date, end_date) -> dict[str, str] | str:
    """Returns live and historical market news & sentiment data from premier news outlets worldwide.

    Covers stocks, cryptocurrencies, forex, and topics like fiscal policy, mergers & acquisitions, IPOs.

    Args:
        ticker: Stock symbol for news articles.
        start_date: Start date for news search.
        end_date: End date for news search.

    Returns:
        Dictionary containing news sentiment data or JSON string.
    """

    params = {
        "tickers": ticker,
        "time_from": format_datetime_for_api(start_date),
        "time_to": format_datetime_for_api(end_date, end_of_day=True),
    }

    return _make_api_request("NEWS_SENTIMENT", params)

def get_global_news(curr_date, look_back_days: int = 7, limit: int = 50) -> dict[str, str] | str:
    """Returns global market news & sentiment data without ticker-specific filtering.

    Covers broad market topics like financial markets, economy, and more.

    Args:
        curr_date: Current date in yyyy-mm-dd format.
        look_back_days: Number of days to look back (default 7).
        limit: Maximum number of articles (default 50).

    Returns:
        Dictionary containing global news sentiment data or JSON string.
    """
    from datetime import datetime, timedelta

    # The tool forwards None for these when the caller omitted them; fall back
    # to the same defaults as the yfinance/finnhub implementations so a
    # no-argument call doesn't crash on `timedelta(days=None)`.
    if look_back_days is None:
        look_back_days = 7
    if limit is None:
        limit = 50

    # Calculate start date
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - timedelta(days=look_back_days)
    start_date = start_dt.strftime("%Y-%m-%d")

    params = {
        "topics": "financial_markets,economy_macro,economy_monetary",
        "time_from": format_datetime_for_api(start_date),
        "time_to": format_datetime_for_api(curr_date, end_of_day=True),
        "limit": str(limit),
    }

    return _make_api_request("NEWS_SENTIMENT", params)


def get_insider_transactions(symbol: str) -> dict[str, str] | str:
    """Returns latest and historical insider transactions by key stakeholders.

    Covers transactions by founders, executives, board members, etc.

    Args:
        symbol: Ticker symbol. Example: "IBM".

    Returns:
        Dictionary containing insider transaction data or JSON string.
    """

    params = {
        "symbol": symbol,
    }

    return _make_api_request("INSIDER_TRANSACTIONS", params)
