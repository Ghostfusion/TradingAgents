from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.date_window import as_of_window, get_run_trade_date
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve stock price data (OHLCV) for a given ticker symbol.
    Uses the configured core_stock_apis vendor.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted dataframe containing the stock price data for the specified ticker symbol in the specified date range.
    """
    # Never serve OHLCV past the run's trade_date, whatever window the model
    # asked for (a no-op when no run date is set).
    start_date, end_date = as_of_window(start_date, end_date, get_run_trade_date())
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)
