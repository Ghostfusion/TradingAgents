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
    Retrieve recent SEC filings for a ticker: primarily SEC EDGAR 8-K (material
    events), 10-K/10-Q (annual/quarterly reports), S-1/S-3 (capital raises), and
    SC 13D/G (stake disclosures).

    **Fallback**: when official SEC EDGAR is unavailable for any reason (HTTP
    403 from SEC fair-access throttling, network failure, no EDGAR record for a
    non-US listing), this falls back to insider filing activity from Massive
    (Form 4 open-market insider transactions), which is a different, narrower
    dataset — the returned text states it is the Massive insider-activity
    fallback so the agent never mistakes Form-4 insider filings for the full
    8-K/10-K set.

    Args:
        ticker (str): Ticker symbol of the company
        limit (int): Max filings to return; omit for a default of 10
        start_date (str): Input for the Massive form-4 fallback window (default:
            one year ago today)
        end_date (str): End of the massive form-4 fallback window (default: today)

    Returns:
        str: SEC EDGAR filings, or a clearly-labelled Massive insider-activity
        fallback, or an explicit unavailable message.
    """
    if limit is None:
        limit = 10
    try:
        result = route_to_vendor("get_sec_filings", ticker, limit)
        # The router returns an explicit sentinel for a clean "no data" (e.g. no
        # CIK / EDGAR record). Treat any sentinel as an EDGAR miss -> fallback.
        if result and result.startswith(("NO_DATA", "DATA_UNAVAILABLE", "DATA_DISABLED")):
            return _sec_filings_massive_fallback(ticker)
        return result
    except Exception as exc:  # noqa: BLE001 - this category raises on primary failure
        _log_sec_fallback(ticker, exc)
        return _sec_filings_massive_fallback(ticker)


def _sec_filings_massive_fallback(ticker: str) -> str:
    """Insider filing activity from Massive when SEC EDGAR is unavailable.

    Returns Form-4 open-market insider transactions over the trailing 365 days,
    clearly labelled so the agent treats it as the insider-activity subset, not
    the full 8-K/10-K filing set. Degrades to an explicit unavailable message
    if Massive also fails (no fabrication).
    """
    from datetime import date, timedelta

    try:
        from tradingagents.dataflows.massive import get_form4_insider_massive

        end = date.today().isoformat()
        start = (date.today() - timedelta(days=365)).isoformat()
        header = (
            f"SEC EDGAR filings unavailable for {ticker.upper()}; showing the "
            "**Massive insider-activity fallback** (Form 4 open-market "
            "transactions — this is NOT the 8-K/10-K/S-1 filing set)."
        )
        body = get_form4_insider_massive(ticker, start, end)
        return f"{header}\n\n{body}"
    except Exception as exc:  # noqa: BLE001 - fallback also degraded
        return (
            f"SEC filings unavailable for {ticker.upper()}: SEC EDGAR failed and "
            f"the Massive insider fallback also had no data ({exc}). Do not "
            f"fabricate filing information."
        )


def _log_sec_fallback(ticker: str, exc: Exception) -> None:
    import logging

    logging.getLogger(__name__).warning(
        "sec_edgar unavailable for %s; falling back to Massive insider filings: %s",
        ticker,
        exc,
    )

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
