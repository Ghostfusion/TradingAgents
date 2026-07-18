from datetime import datetime

from .alpha_vantage_common import _filter_csv_by_date_range, _make_api_request
from .errors import NoMarketDataError


def get_stock(
    symbol: str,
    start_date: str,
    end_date: str
) -> str:
    """
    Returns raw daily OHLCV values, adjusted close values, and historical split/dividend events
    filtered to the specified date range.

    Args:
        symbol: The name of the equity. For example: symbol=IBM
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        CSV string containing the daily adjusted time series data filtered to the date range.
    """
    # Parse dates to determine the range
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    today = datetime.now()

    # Choose outputsize based on whether the requested range is within the latest 100 days
    # Compact returns latest 100 data points, so check if start_date is recent enough
    days_from_today_to_start = (today - start_dt).days
    outputsize = "compact" if days_from_today_to_start < 100 else "full"

    params = {
        "symbol": symbol,
        "outputsize": outputsize,
        "datatype": "csv",
    }

    response = _make_api_request("TIME_SERIES_DAILY_ADJUSTED", params)

    filtered = _filter_csv_by_date_range(response, start_date, end_date)

    # An empty/whitespace result means the symbol is unknown/delisted/not
    # covered. Raise the typed error so the router tries the next vendor and,
    # if all fail, emits an honest no-data sentinel — instead of returning an
    # empty CSV that the vendor cache would store and replay as "success".
    if not filtered or not filtered.strip():
        raise NoMarketDataError(
            symbol, detail=f"no rows between {start_date} and {end_date}"
        )
    return filtered
