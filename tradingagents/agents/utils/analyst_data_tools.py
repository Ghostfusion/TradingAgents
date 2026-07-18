"""Analyst-rating and earnings-calendar tools (Finnhub-backed)."""
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_analyst_ratings(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve sell-side analyst ratings and price-target consensus for a ticker.
    Returns the recommendation trend (strong buy / buy / hold / sell /
    strong sell counts per period) and the price-target consensus (mean,
    median, high, low, and number of analysts). Uses the configured
    analyst_ratings vendor.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: A formatted report of analyst ratings and price targets
    """
    return route_to_vendor("get_analyst_ratings", ticker)


@tool
def get_earnings_calendar(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    look_back_days: Annotated[
        int | None, "Days to look back from curr_date; omit for a 30-day window"
    ] = None,
) -> str:
    """
    Retrieve the upcoming earnings date and last reported EPS surprise for a
    ticker. Returns earnings date, EPS estimate, EPS actual, surprise percent,
    and revenue estimate. Uses the configured earnings_calendar vendor.

    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Trailing window; omit for a 30-day window

    Returns:
        str: A formatted report of upcoming earnings and EPS surprise
    """
    return route_to_vendor("get_earnings_calendar", ticker, curr_date, look_back_days)
