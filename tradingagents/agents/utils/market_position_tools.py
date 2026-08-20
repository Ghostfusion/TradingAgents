"""Market-positioning and filing tools (free data sources)."""
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_options_chain(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str | None, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve options-market data for a ticker: implied volatility, open
    interest, volume, and the put/call ratio for the nearest-dated expiry.
    Uses the configured options_data vendor.

    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date in yyyy-mm-dd format

    Returns:
        str: A formatted report of implied volatility and put/call positioning
    """
    return route_to_vendor("get_options_chain", ticker, curr_date)


@tool
def get_sec_filings(
    ticker: Annotated[str, "ticker symbol"],
    limit: Annotated[int | None, "Max filings to summarize; omit for a default of 10"] = None,
) -> str:
    """
    Retrieve recent SEC EDGAR filings for a ticker: 8-K (material events), 10-K/10-Q
    (annual/quarterly reports), S-1/S-3 (capital raises), and SC 13D/G (stake
    disclosures). Uses the configured sec_filings vendor.

    Args:
        ticker (str): Ticker symbol of the company
        limit (int): Max filings to return; omit for a default of 10

    Returns:
        str: A formatted report of recent filings with dates and links
    """
    if limit is None:
        limit = 10
    return route_to_vendor("get_sec_filings", ticker, limit)


@tool
def get_short_interest(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve short-interest and ownership data for a ticker: shares short,
    days-to-cover, short % of float, and insider/institutional ownership.
    Uses the configured short_interest vendor.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: A formatted report of short interest and ownership
    """
    return route_to_vendor("get_short_interest", ticker)


@tool
def get_short_volume(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve daily short-sale volume ratio (% of total volume sold short) for a
    ticker from FINRA/ATS data via Massive.com. Elevated readings indicate
    heavy intraday shorting — a conviction / squeeze signal.

    Args:
        ticker (str): Ticker symbol of the company
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format

    Returns:
        str: A formatted report of daily short-volume ratios
    """
    from tradingagents.dataflows.massive import get_short_volume_massive

    try:
        return get_short_volume_massive(ticker, start_date, end_date)
    except Exception as exc:  # noqa: BLE001
        return f"short volume unavailable for {ticker}: {exc}"


@tool
def get_market_snapshot(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Latest consolidated market snapshot for a stock from Massive.com: latest
    day/minute/prevDay bars, VWAP, today's change, plus quote/trade when the
    plan includes them. A verification-grade read for exact price-level
    claims. Returns an explicit 'unavailable' message when the account plan
    lacks snapshot access.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: snapshot OHLCV/VWAP/change, or an explicit 'unavailable' message
    """
    from tradingagents.dataflows.massive import get_market_snapshot_massive

    try:
        return get_market_snapshot_massive(ticker)
    except Exception as exc:  # noqa: BLE001
        return f"market snapshot unavailable for {ticker}: {exc}"


@tool
def get_top_movers(
    direction: Annotated[str, "'gainers' or 'losers'"] = "gainers",
    count: Annotated[int | None, "max rows to return; omit for a default of 10"] = None,
) -> str:
    """
    Top U.S. market gainers/losers by snapshot from Massive.com — a clean,
    OpenD-independent universe source. Returns a ranked list of tickers with
    their close and today's % change, or an explicit 'unavailable' message when
    the account plan lacks snapshot access.

    Args:
        direction (str): 'gainers' or 'losers'
        count (int): max rows to render; default 10

    Returns:
        str: a ranked list of top movers, or an explicit 'unavailable' message
    """
    if count is None:
        count = 10
    from tradingagents.dataflows.massive import get_top_movers_massive

    try:
        return get_top_movers_massive(direction, count)
    except Exception as exc:  # noqa: BLE001
        return f"top movers unavailable: {exc}"
