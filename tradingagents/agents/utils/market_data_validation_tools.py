from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.market_data_validator import build_verified_market_snapshot


@tool
def get_verified_market_snapshot(
    symbol: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[
        int, "number of recent trading rows to include for sanity-checking"
    ] = 30,
) -> str:
    """Deterministic verification snapshot for exact market-data claims.

    Returns the latest OHLCV row on or before curr_date, common technical
    indicators, and recent closes. Call this before making exact claims about
    price levels, Bollinger bands, RSI, MACD, moving averages, support /
    resistance, or historical comparisons, and treat it as the source of truth.
    """
    try:
        return build_verified_market_snapshot(symbol, curr_date, look_back_days)
    except (NoMarketDataError, ValueError) as exc:
        # Match the router's degradation contract: an unknown/delisted/stale
        # symbol surfaces the same honest "no data" signal every other tool
        # returns, not a raw exception the analyst might misread.
        return (
            f"NO_DATA_AVAILABLE: No verified market data for '{symbol}' "
            f"({exc}). The symbol may be invalid, delisted, or the vendor "
            f"returned stale data. Do not estimate or fabricate values."
        )

@tool
def get_live_price_sanity(
    live_price: Annotated[float | None, "live/intraday print price"],
    day_low: Annotated[float | None, "verified day low"],
    day_high: Annotated[float | None, "verified day high"],
    buffer_pct: Annotated[float, "outside-by fraction tolerated"] = 0.05,
) -> str:
    """Label whether a live print is INSIDE or OUTSIDE the verified day bar.

    Reconciliation guard: a real-time quote far outside the verified OHLC
    (by ``buffer_pct``) is far more likely a stale feed / symbol mismatch
    than a genuine move. Call before reconciling an intraday print with the
    verified bar - the verdict tells you whether to trust it as a true quote
    or flag it as questionable.
    """
    from tradingagents.dataflows.market_data_validator import live_price_sanity

    try:
        return live_price_sanity(live_price, day_low, day_high, buffer_pct)
    except Exception as exc:  # noqa: BLE001 - advisory read degrades
        return f"live price sanity unavailable: {exc}"



