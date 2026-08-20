"""Tier 1/2 moomoo enrichment tools: flow, smart money, catalysts, breadth.

Each tool routes through ``route_to_vendor`` behind the ``moomoo``-only
categories registered in ``interface.py``.  All categories are optional — a
vendor failure (OpenD down, region/permission gate) degrades to a
``DATA_UNAVAILABLE`` sentinel and the analyst proceeds without the signal,
exactly like the other optional enrichment categories.
"""

from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_capital_flow(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str | None, "current date yyyy-mm-dd (optional)"] = None,
) -> str:
    """
    Retrieve capital inflow/outflow for a ticker by order size (super/big/mid/
    small) on a weekly basis, plus the latest session's capital distribution.
    Institutional distribution (sustained large-order outflows) vs accumulation
    (inflows) is a positioning gauge for the market analyst. Uses the configured
    capital_flow vendor.

    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Optional current date in yyyy-mm-dd format

    Returns:
        str: A formatted report of capital flow by order size
    """
    return route_to_vendor("get_capital_flow", ticker, curr_date)


@tool
def get_smart_money(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve ARK fund activity in a ticker: recent transactions, net shares
    bought/sold, and the last activity date. ARK is a high-profile growth
    investor, so sustained institutional activity here is a smart-money signal
    for the fundamentals analyst (absence of activity is neutral). Uses the
    configured smart_money vendor.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: A formatted report of ARK institutional activity
    """
    return route_to_vendor("get_smart_money", ticker)


@tool
def get_economic_calendar(
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    look_days: Annotated[int | None, "days ahead to look; omit for a 14-day window"] = None,
) -> str:
    """
    Retrieve upcoming economic events (CPI, FOMC, payrolls, …) with country,
    importance, previous/consensus/actual values. These scheduled macro events
    are the dominant short-term catalysts for rates and equities, so the news
    analyst can date the next catalyst and flag exposure. Uses the configured
    economic_calendar vendor.

    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_days (int): Days ahead to fetch; omit for a default of 14

    Returns:
        str: A formatted table of upcoming economic events
    """
    if look_days is None:
        look_days = 14
    return route_to_vendor("get_economic_calendar", curr_date, look_days)


@tool
def get_fed_watch() -> str:
    """
    Retrieve market-implied Fed target-rate probabilities for upcoming FOMC
    meetings. A numeric macro anchor (what the rates market prices) for the news
    analyst, complementing news and prediction markets. Uses the configured
    fed_watch vendor.

    Returns:
        str: A formatted report of Fed target-rate probabilities
    """
    return route_to_vendor("get_fed_watch")


@tool
def get_market_breadth() -> str:
    """
    Retrieve US market breadth: sector heat-map moves and the rise/fall
    distribution across the market. Separates a stock's idiosyncratic move from
    a market-wide regime — useful for the news analyst's macro context. Uses the
    configured market_breadth vendor.

    Returns:
        str: A formatted report of US market breadth
    """
    return route_to_vendor("get_market_breadth")


@tool
def get_revenue_breakdown(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve the latest period's revenue breakdown by segment/region with each
    segment's share of total revenue. Segment mix shifts and concentration are
    quality flags for the fundamentals analyst beyond aggregate revenue growth.
    Uses the configured revenue_breakdown vendor.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: A formatted report of segment revenue breakdown
    """
    return route_to_vendor("get_revenue_breakdown", ticker)


@tool
def get_corporate_actions(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve recent corporate actions for a ticker: dividend history (amounts,
    ex/record/payable dates) and stock splits. Consistent dividends and buybacks
    signal management confidence and shareholder-return discipline; splits are
    usually cosmetic. Uses the configured corporate_actions vendor.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: A formatted report of dividends and stock splits
    """
    return route_to_vendor("get_corporate_actions", ticker)


@tool
def get_dividends(
    ticker: Annotated[str, "ticker symbol"],
    limit: Annotated[int | None, "max dividend rows to return; default 5"] = None,
) -> str:
    """
    Recent cash dividends for a ticker (Massive.com). Returns declaration /
    ex / record / pay dates, cash amount, currency, frequency and the
    split-adjustment factor. Rising / consistent regular dividends signal
    return discipline; the adjustment factor helps normalize split history.

    Args:
        ticker (str): Ticker symbol of the company
        limit (int): max rows; default 5

    Returns:
        str: A formatted dividend report, or an explicit 'unavailable' message
    """
    if limit is None:
        limit = 5
    from tradingagents.dataflows.massive import get_dividends_massive

    try:
        return get_dividends_massive(ticker, limit)
    except Exception as exc:  # noqa: BLE001
        return f"dividends unavailable for {ticker}: {exc}"


@tool
def get_ipos(
    limit: Annotated[int | None, "max IPO rows to return, default 10"] = None,
    status: Annotated[str, "IPO status filter: pending, priced, withdrawn"] = "pending",
) -> str:
    """
    Recent IPOs (Massive.com): issuer, ticker, expected/announced date, offer
    price, size and status. New listings are fresh-money / catalyst events the
    news analyst can weigh as a universe or event-risk input.

    Args:
        limit (int): max rows; default 10
        status (str): IPO status filter

    Returns:
        str: A formatted IPO list, or an explicit 'unavailable' message
    """
    if limit is None:
        limit = 10
    from tradingagents.dataflows.massive import get_ipos_massive

    try:
        return get_ipos_massive(limit, status)
    except Exception as exc:  # noqa: BLE001
        return f"ipos unavailable: {exc}"



@tool
def get_earnings_catalyst(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve historical earnings-day reaction data for a ticker: per past
    earnings the market-implied move, the IV crush, and the day-of price
    reaction. A large historical implied move and deep IV crush mean earnings is
    a major single-day catalyst — size positions accordingly. Uses the
    configured earnings_catalyst vendor.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: A formatted report of earnings-day reaction history
    """
    return route_to_vendor("get_earnings_catalyst", ticker)


@tool
def get_institution_holdings(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve institutional ownership for a ticker: the share of float held by
    institutions and its period-over-period change, plus the number of reporting
    institutions (13F-style aggregate). A rising institutional % with stable price
    flags accumulation; a falling % flags distribution. Uses the configured
    institution_data vendor.

    Args:
        ticker (str): Ticker symbol

    Returns:
        str: Institutional ownership by reporting period
    """
    return route_to_vendor("get_institution_holdings", ticker)


@tool
def get_earnings_surprise_history(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str | None, "current date yyyy-mm-dd (optional)"] = None,
) -> str:
    """
    Retrieve historical earnings surprises for a ticker: per past print the EPS
    estimate vs actual (surprise %), the day-of price reaction, the option-implied
    move, and IV crush. A succession of beats (acceleration) and large implied
    moves flag elevated catalyst risk. Uses the configured earnings_surprise vendor.

    Args:
        ticker (str): Ticker symbol
        curr_date (str): Optional current date

    Returns:
        str: Earnings surprise + reaction history table
    """
    return route_to_vendor("get_earnings_surprise_history", ticker, curr_date)


@tool
def get_expected_move(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str | None, "current date yyyy-mm-dd (optional)"] = None,
) -> str:
    """
    Retrieve the option-market-implied expected move for the upcoming earnings
    print (1σ, from the current-period earnings price history), plus a
    price-based ±band on the last close. Use to size event risk. Uses the
    configured expected_move vendor.

    Args:
        ticker (str): Ticker symbol
        curr_date (str): Optional current date

    Returns:
        str: Expected move % and band
    """
    return route_to_vendor("get_expected_move", ticker, curr_date)
