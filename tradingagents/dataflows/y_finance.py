import contextlib
import logging
from datetime import datetime
from typing import Annotated

import pandas as pd
import yfinance as yf
from dateutil.relativedelta import relativedelta

from .stockstats_utils import (
    StockstatsUtils,
    _assert_ohlcv_not_stale,
    filter_financials_by_date,
    load_ohlcv,
    yf_retry,
)
from .symbol_utils import NoMarketDataError, require_symbol

logger = logging.getLogger(__name__)


def get_YFin_data_online(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
):

    datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # Resolve broker/forex symbols to Yahoo's convention (XAUUSD+ -> GC=F).
    canonical = require_symbol(symbol)
    ticker = yf.Ticker(canonical)

    # yfinance treats ``end`` as EXCLUSIVE, so it would drop the requested
    # end_date row (and the current day when end_date is today). Request one day
    # past end_date so the requested range is actually inclusive (#986/#987).
    end_inclusive = (end_dt + relativedelta(days=1)).strftime("%Y-%m-%d")
    data = yf_retry(lambda: ticker.history(start=start_date, end=end_inclusive))

    # Empty result means the symbol is unknown/delisted. Raise a typed error
    # instead of returning prose: the routing layer turns it into a single
    # unambiguous "no data" signal so the agent never fabricates a price.
    if data.empty:
        raise NoMarketDataError(
            symbol, canonical, f"no rows between {start_date} and {end_date}"
        )

    # Remove timezone info from index for cleaner output
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    # Reject a stale frame (e.g. a year-old partial response) before it is
    # formatted into the report. Raises NoMarketDataError, which the router
    # turns into one clear unavailable signal (#1021).
    _assert_ohlcv_not_stale(data, end_date, symbol, canonical)

    # Round numerical values to 2 decimal places for cleaner display
    numeric_columns = ["Open", "High", "Low", "Close", "Adj Close"]
    for col in numeric_columns:
        if col in data.columns:
            data[col] = data[col].round(2)

    # Convert DataFrame to CSV string
    csv_string = data.to_csv()

    # Add header information; note the resolved symbol when it differs so the
    # agent (and user) can see which instrument was actually priced.
    label = canonical if canonical == symbol.upper() else f"{canonical} (from {symbol})"
    header = f"# Stock data for {label} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    return header + csv_string

def get_stock_stats_indicators_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:

    best_ind_params = {
        # Moving Averages
        "close_50_sma": (
            "50 SMA: A medium-term trend indicator. "
            "Usage: Identify trend direction and serve as dynamic support/resistance. "
            "Tips: It lags price; combine with faster indicators for timely signals."
        ),
        "close_200_sma": (
            "200 SMA: A long-term trend benchmark. "
            "Usage: Confirm overall market trend and identify golden/death cross setups. "
            "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
        ),
        "close_10_ema": (
            "10 EMA: A responsive short-term average. "
            "Usage: Capture quick shifts in momentum and potential entry points. "
            "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
        ),
        # MACD Related
        "macd": (
            "MACD: Computes momentum via differences of EMAs. "
            "Usage: Look for crossovers and divergence as signals of trend changes. "
            "Tips: Confirm with other indicators in low-volatility or sideways markets."
        ),
        "macds": (
            "MACD Signal: An EMA smoothing of the MACD line. "
            "Usage: Use crossovers with the MACD line to trigger trades. "
            "Tips: Should be part of a broader strategy to avoid false positives."
        ),
        "macdh": (
            "MACD Histogram: Shows the gap between the MACD line and its signal. "
            "Usage: Visualize momentum strength and spot divergence early. "
            "Tips: Can be volatile; complement with additional filters in fast-moving markets."
        ),
        # Momentum Indicators
        "rsi": (
            "RSI: Measures momentum to flag overbought/oversold conditions. "
            "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
            "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
        ),
        # Volatility Indicators
        "boll": (
            "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
            "Usage: Acts as a dynamic benchmark for price movement. "
            "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
        ),
        "boll_ub": (
            "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
            "Usage: Signals potential overbought conditions and breakout zones. "
            "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
        ),
        "boll_lb": (
            "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
            "Usage: Indicates potential oversold conditions. "
            "Tips: Use additional analysis to avoid false reversal signals."
        ),
        "atr": (
            "ATR: Averages true range to measure volatility. "
            "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
            "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
        ),
        # Volume-Based Indicators
        "vwma": (
            "VWMA: A moving average weighted by volume. "
            "Usage: Confirm trends by integrating price action with volume data. "
            "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
        ),
        "mfi": (
            "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
            "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
            "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
        ),
    }

    if indicator not in best_ind_params:
        # This vendor cannot produce the requested indicator (a bad
        # LLM-supplied name, or one stockstats has no description for). Raise
        # the typed no-data error so the router falls through to another
        # vendor / emits the sentinel instead of caching a report of blank
        # "date: " rows as if it were real data.
        raise NoMarketDataError(
            symbol,
            detail=(
                f"indicator {indicator!r} is not supported by yfinance/stockstats "
                f"(choose from: {list(best_ind_params.keys())})"
            ),
        )

    end_date = curr_date
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    # Optimized: Get stock data once and calculate indicators for all dates
    try:
        indicator_data = _get_stock_stats_bulk(symbol, indicator, curr_date)

        # Generate the date range we need
        current_dt = curr_date_dt
        date_values = []

        while current_dt >= before:
            date_str = current_dt.strftime('%Y-%m-%d')

            # Look up the indicator value for this date
            if date_str in indicator_data:
                indicator_value = indicator_data[date_str]
            else:
                indicator_value = "N/A: Not a trading day (weekend or holiday)"

            date_values.append((date_str, indicator_value))
            current_dt = current_dt - relativedelta(days=1)

        # Build the result string
        ind_string = ""
        for date_str, value in date_values:
            ind_string += f"{date_str}: {value}\n"

    except NoMarketDataError:
        raise  # Unknown/delisted symbol — let the router emit the sentinel
    except Exception:
        # The bulk path failed (bad indicator name, stockstats error, upstream
        # data problem). Log the real cause — never print — then fall back to
        # the per-date implementation, which raises the typed error on failure
        # so the computation degrades through the router's no-data channel
        # instead of being returned as a report of blank "date: " rows that the
        # vendor cache would freeze for its TTL.
        logger.exception(
            "Bulk stockstats computation failed for %s (%s); falling back to per-date",
            symbol,
            indicator,
        )
        ind_string = ""
        while curr_date_dt >= before:
            indicator_value = get_stockstats_indicator(
                symbol, indicator, curr_date_dt.strftime("%Y-%m-%d")
            )
            ind_string += f"{curr_date_dt.strftime('%Y-%m-%d')}: {indicator_value}\n"
            curr_date_dt = curr_date_dt - relativedelta(days=1)

    result_str = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {end_date}:\n\n"
        + ind_string
        + "\n\n"
        + best_ind_params.get(indicator, "No description available.")
    )

    return result_str


def _get_stock_stats_bulk(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to calculate"],
    curr_date: Annotated[str, "current date for reference"]
) -> dict:
    """
    Optimized bulk calculation of stock stats indicators.
    Fetches data once and calculates indicator for all available dates.
    Returns dict mapping date strings to indicator values.
    """
    from stockstats import wrap

    data = load_ohlcv(symbol, curr_date)
    df = wrap(data)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    # Calculate the indicator for all rows at once
    df[indicator]  # This triggers stockstats to calculate the indicator

    # Create a dictionary mapping date strings to indicator values
    result_dict = {}
    for _, row in df.iterrows():
        date_str = row["Date"]
        indicator_value = row[indicator]

        # Handle NaN/None values
        if pd.isna(indicator_value):
            result_dict[date_str] = "N/A"
        else:
            result_dict[date_str] = str(indicator_value)

    return result_dict


def get_stockstats_indicator(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
) -> str:

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    curr_date = curr_date_dt.strftime("%Y-%m-%d")

    try:
        indicator_value = StockstatsUtils.get_stock_stats(
            symbol,
            indicator,
            curr_date,
        )
    except NoMarketDataError:
        raise  # Unknown/delisted symbol — let the router emit the sentinel
    except Exception as exc:
        # Log the real cause (never print) and raise the typed error: a failed
        # computation must degrade through the router's no-data channel, not be
        # returned as a blank success string the vendor cache would serve for
        # its whole TTL.
        logger.exception(
            "stockstats indicator %s failed for %s on %s", indicator, symbol, curr_date
        )
        raise NoMarketDataError(
            symbol,
            detail=f"stockstats indicator {indicator!r} computation failed: {exc}",
        ) from exc

    return str(indicator_value)


# Below this relative gap the vendor dividendYield and the same vendor's
# trailing-12m dividend record are treated as agreeing (yield endpoints round
# differently; a 25% gap is a real disagreement, not rounding).
_YIELD_DIVERGENCE = 0.25


def _dividend_yield_note(info: dict, ticker_obj, rendered_pct: float | None) -> str:
    """Cross-check the vendor ``dividendYield`` against the SAME vendor's own
    trailing-12-month dividend record, and return a correction note when the
    two disagree by more than 25%.

    QQQI 2026-09-13 (fundamentals review loop): ``info['dividendYield']`` is
    0.09, rendered as 9.00%, while ``Ticker.dividends`` pays ~0.63/month - the
    trailing twelve prints sum to 7.649 = 14.02% at the 54.56 reference price,
    and EVERY rolling 12-payment window since inception is 13.4-14.0%. The
    field is unreconcilable with the payment record, not stale, and a report
    quoting it understates the payout by ~5 points. Advisory: returns "" when
    the record is missing/empty or agrees; never raises.
    """
    if not rendered_pct or rendered_pct <= 0:
        return ""
    try:
        divs = ticker_obj.dividends
    except Exception:  # noqa: BLE001 - advisory cross-check, never load-bearing
        return ""
    if divs is None or len(divs) == 0:
        return ""
    price = None
    for key in ("regularMarketPrice", "previousClose", "navPrice"):
        try:
            price = float(info.get(key))
        except (TypeError, ValueError):
            price = None
        if price:
            break
    if not price:
        return ""
    try:
        idx = pd.to_datetime(divs.index)
        cutoff = pd.Timestamp.now(tz=idx.tz) - pd.Timedelta(days=365)
        ttm = float(pd.Series(divs.to_numpy(), index=idx).loc[idx > cutoff].sum())
    except Exception:  # noqa: BLE001 - advisory
        return ""
    if ttm <= 0:
        return ""
    ttm_pct = ttm / price * 100.0
    if abs(ttm_pct - rendered_pct) / max(ttm_pct, rendered_pct) <= _YIELD_DIVERGENCE:
        return ""
    return (
        f"\n# NOTE: vendor 'Dividend Yield' ({rendered_pct:.2f}%) contradicts the same "
        f"vendor's trailing-12m dividend record ({ttm:,.4f}/share = {ttm_pct:.2f}% at "
        f"{price:,.2f}). Treat the payment record as the yield; do not quote the "
        f"vendor dividendYield field."
    )


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get company fundamentals overview from yfinance."""
    canonical = require_symbol(ticker)
    try:
        ticker_obj = yf.Ticker(canonical)
        info = yf_retry(lambda: ticker_obj.info)

        if not info:
            raise NoMarketDataError(ticker, canonical, "no fundamentals returned")

        fields = [
            ("Name", info.get("longName")),
            ("Sector", info.get("sector")),
            ("Industry", info.get("industry")),
            # The listing venue belongs to the identity block. Without it a
            # report stating a true venue ("iShares 3-7 Year Treasury Bond
            # ETF, exchange NGM") reads as fabrication, because no leaf carries
            # an exchange for the symbol - it was flagged UNSUPPORTED on both
            # the IEI 2026-09-16 trees.
            ("Exchange", info.get("exchange")),
            ("Market Cap", info.get("marketCap")),
            ("PE Ratio (TTM)", info.get("trailingPE")),
            ("Forward PE", info.get("forwardPE")),
            ("PEG Ratio", info.get("pegRatio")),
            ("Price to Book", info.get("priceToBook")),
            ("EPS (TTM)", info.get("trailingEps")),
            ("Forward EPS", info.get("forwardEps")),
            ("Dividend Yield", info.get("dividendYield")),
            ("Beta", info.get("beta")),
            ("52 Week High", info.get("fiftyTwoWeekHigh")),
            ("52 Week Low", info.get("fiftyTwoWeekLow")),
            ("50 Day Average", info.get("fiftyDayAverage")),
            ("200 Day Average", info.get("twoHundredDayAverage")),
            ("Revenue (TTM)", info.get("totalRevenue")),
            ("Gross Profit", info.get("grossProfits")),
            ("EBITDA", info.get("ebitda")),
            ("Net Income", info.get("netIncomeToCommon")),
            ("Profit Margin", info.get("profitMargins")),
            ("Operating Margin", info.get("operatingMargins")),
            ("Return on Equity", info.get("returnOnEquity")),
            ("Return on Assets", info.get("returnOnAssets")),
            ("Debt to Equity", info.get("debtToEquity")),
            ("Current Ratio", info.get("currentRatio")),
            ("Book Value", info.get("bookValue")),
            ("Operating Cash Flow", info.get("operatingCashflows")),
            ("Free Cash Flow", info.get("freeCashflow")),
        ]

        lines = []
        div_yield_pct: float | None = None
        # yfinance reports ratio fields as decimal fractions (0.24 = 24%); the
        # ratio/margin labels below imply a percentage, so widen to % to avoid
        # a 100x unit drift in the LLM's read (see yfinance_short_interest).
        _PCT_FIELDS = {
            "Dividend Yield",
            "Profit Margin",
            "Operating Margin",
            "Return on Equity",
            "Return on Assets",
        }
        for label, value in fields:
            if value is None:
                continue
            if label in _PCT_FIELDS:
                y = float(value)
                # yfinance's dividendYield is normally a fraction (0.0073 =
                # 0.73%), but some symbols return it percent-scaled (0.73).
                # A yield above 25% is implausible for any normal equity, so
                # treat it as percent-scaled and re-normalize (MSFT 2026-09-08
                # rendered 73.00% from a 0.73 input).
                if label == "Dividend Yield" and y > 0.25:
                    y = y / 100.0
                if label == "Dividend Yield":
                    div_yield_pct = y * 100.0
                lines.append(f"{label}: {y * 100:.2f}%")
            elif label == "Debt to Equity" and float(value) > 10:
                # A D/E above 10 is a units/scaling artifact, not a real
                # leverage ratio (MSFT 2026-09-08: 29.118 vs the true 0.13).
                # Never emit an implausible number; say so instead.
                lines.append(f"{label}: n/a (implausible vendor value > 10)")
            else:
                lines.append(f"{label}: {value}")

        # yfinance returns a stub dict (e.g. {"trailingPegRatio": None}) for
        # unknown symbols, so `info` is truthy but every field is empty. Treat
        # "no usable fields" as no data rather than emitting a bare header the
        # agent might fabricate around.
        if not lines:
            raise NoMarketDataError(ticker, canonical, "no fundamental fields returned")

        header = f"# Company Fundamentals for {canonical}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return (
            header
            + "\n".join(lines)
            + _dividend_yield_note(info, ticker_obj, div_yield_pct)
        )

    except NoMarketDataError:
        raise
    except Exception:
        # Re-raise, never return an "Error retrieving..." prose blob as a
        # SUCCESS: a returned string is cached by the router and skips the
        # vendor fallback, so a transient failure would masquerade as an
        # authoritative (stale) answer. Letting it bubble lets route_to_vendor
        # skip to the next vendor and never caches the failure.
        raise


# The vendor CSV prints ABSOLUTE integers (``19639000000.0``) with no units
# line, so a reader has no scale to anchor on: MSFT 2026-09-16 fundamentals.md
# quoted four cash-flow rows as "196390 x10^6" and "900070 x10^6" - a 10x
# mis-scale on FCF, capex, operating cash flow, deferred tax and total revenue,
# with no leaf anywhere stating an ``x10^6`` header. ``financial_trends`` already
# states its scale ("# Values are raw vendor figures (unscaled)."); the three
# statement payloads now say the same, and name what the digits mean, so the
# scale can never be inferred from the size of the number alone.
_STATEMENT_UNITS_NOTE = (
    "# Values are raw vendor figures (unscaled): absolute units, so "
    "19639000000.0 = $19.639bn (NOT 196,390 x10^6).\n"
)


#: The standard ways a vendor can compute a ``Net Debt`` row, as
#: ``(debt rows to add, cash row, description)``. A vendor row is only
#: unexplained when NO basis reproduces it: excluding short-term investments -
#: or capital-lease obligations - from net debt is a convention, not a sign
#: error, and two vendors can disagree in sign without either being wrong
#: (MSFT 2026-09-16: yfinance's row is 56,826 - 20,935 = 19,359 on financial
#: debt excluding leases less cash, while cash + ST investments less total debt
#: including leases is +19,825 NET CASH - the two numbers differ by ~0.5bn in
#: magnitude and by the whole sign, so the old note called the vendor row
#: mis-signed and the report repeated that claim).
_NET_DEBT_BASES = (
    (
        ("Total Debt",),
        "Cash And Cash Equivalents",
        "total debt less cash and equivalents",
    ),
    (
        ("Total Debt",),
        "Cash Cash Equivalents And Short Term Investments",
        "total debt less cash and ST investments",
    ),
    (
        ("Long Term Debt And Capital Lease Obligation", "Current Debt And Capital Lease Obligation"),
        "Cash And Cash Equivalents",
        "total debt including lease obligations, less cash and equivalents",
    ),
    (
        ("Long Term Debt And Capital Lease Obligation", "Current Debt And Capital Lease Obligation"),
        "Cash Cash Equivalents And Short Term Investments",
        "total debt including lease obligations, less cash and ST investments",
    ),
    (
        ("Long Term Debt", "Current Debt"),
        "Cash And Cash Equivalents",
        "financial debt excluding capital-lease obligations, less cash and equivalents",
    ),
    (
        ("Long Term Debt", "Current Debt"),
        "Cash Cash Equivalents And Short Term Investments",
        "financial debt excluding capital-lease obligations, less cash and ST investments",
    ),
)


def _row_values(csv_string: str) -> dict[str, float]:
    """``{exact row label: newest non-empty value}`` for a vendor CSV payload.

    Exact labels on purpose: substring matching cannot separate yfinance's
    ``Long Term Debt`` from ``Long Term Debt And Capital Lease Obligation``,
    and the wider row is listed first (so a substring reader silently adds
    16.5bn of lease obligations to a debt leg, or drops them from the cash
    cross-check).
    """
    out: dict[str, float] = {}
    for line in csv_string.splitlines():
        if line.startswith("#"):
            continue
        cells = line.split(",")
        label = cells[0].strip()
        if not label or label.startswith("-"):
            continue
        for cell in cells[1:]:
            cell = cell.strip()
            if not cell:
                continue
            with contextlib.suppress(ValueError):
                out[label.lower()] = float(cell)
            break
    return out


def _net_debt_note(csv_string: str, ticker: str) -> str:
    """Disclose the BASIS of a yfinance balance-sheet ``Net Debt`` row.

    Never raises; returns "" when the payload cannot disagree with itself.

    The old revision fired whenever cash + ST investments exceeded total debt
    and told the model the vendor row "is net-CASH ... do not quote it" - a
    definitional difference relabelled as a vendor error (MSFT 2026-09-16: the
    vendor row is consistent with financial debt excluding capital-lease
    obligations less cash and equivalents; the report then wrote that the row
    "is mis-signed", a claim about the vendor's formula that was never traced).
    Now the row is reconciled against ``_NET_DEBT_BASES`` first: a row that
    some standard basis reproduces is DISCLOSED (naming that basis, the widest
    basis, and its own figure), and only a row that no basis can reproduce is
    reported as unreproducible - still without asserting what the vendor meant.
    """
    rows = _row_values(csv_string)
    nd = rows.get("net debt")
    debt_sti = rows.get("total debt")
    cash_sti = rows.get("cash cash equivalents and short term investments")
    if None in (nd, debt_sti, cash_sti):
        return ""
    wide_net = cash_sti - debt_sti
    tolerance = 0.01 * abs(nd) + 1.0

    def _basis_value(debt_labels, cash_label) -> float | None:
        legs = [rows.get(label.lower()) for label in debt_labels]
        cash = rows.get(cash_label.lower())
        if cash is None or any(leg is None for leg in legs):
            return None
        return sum(legs) - cash

    matched: tuple[str, float] | None = None
    for debt_labels, cash_label, description in _NET_DEBT_BASES:
        value = _basis_value(debt_labels, cash_label)
        if value is not None and abs(value - nd) <= tolerance:
            matched = (description, value)
            break

    if wide_net <= 0:
        # The widest basis agrees this is net debt. Silence, as before: a
        # magnitude difference there is a definition (AMZN's row reconciles
        # against financial debt EXCLUDING its large operating-lease
        # liabilities, which this payload does not carry as a separable row),
        # and a note would only teach the model to distrust a row whose sign is
        # right.
        return ""
    if matched is not None:
        description, value = matched
        return (
            f"\n# NOTE: the vendor 'Net Debt' row ({nd:,.2f}) is consistent with "
            f"the narrower basis it uses - {description} ({value:,.2f}). On the "
            f"widest basis (cash + ST investments {cash_sti:,.2f} minus total debt "
            f"{debt_sti:,.2f}) the company is NET CASH by {wide_net:,.2f}. Quote "
            f"one basis, name it, and do not call the vendor row a sign error: "
            f"the difference is the definition, not the arithmetic."
        )
    return (
        f"\n# NOTE: the vendor 'Net Debt' row ({nd:,.2f}) cannot be reproduced "
        f"from this payload's own debt and cash rows (the rows that would "
        f"explain it - financial debt excluding lease obligations, or a "
        f"cash-only definition - are not all carried here). Cash + ST "
        f"investments ({cash_sti:,.2f}) exceed total debt ({debt_sti:,.2f}), so "
        f"on the widest basis the company is NET CASH by {wide_net:,.2f}. State "
        f"the basis you quote; do not present the vendor row as the company's "
        f"own net position."
    )


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
):
    """Get balance sheet data from yfinance."""
    canonical = require_symbol(ticker)
    try:
        ticker_obj = yf.Ticker(canonical)

        if freq.lower() == "quarterly":
            data = yf_retry(lambda: ticker_obj.quarterly_balance_sheet)
        else:
            data = yf_retry(lambda: ticker_obj.balance_sheet)

        data = filter_financials_by_date(data, curr_date)

        if data.empty:
            raise NoMarketDataError(ticker, canonical, "no balance sheet data")

        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()

        # Add header information
        header = f"# Balance Sheet data for {canonical} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += _STATEMENT_UNITS_NOTE + "\n"

        return header + csv_string + _net_debt_note(csv_string, ticker)

    except NoMarketDataError:
        raise
    except Exception:
        raise


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
):
    """Get cash flow data from yfinance."""
    canonical = require_symbol(ticker)
    try:
        ticker_obj = yf.Ticker(canonical)

        if freq.lower() == "quarterly":
            data = yf_retry(lambda: ticker_obj.quarterly_cashflow)
        else:
            data = yf_retry(lambda: ticker_obj.cashflow)

        data = filter_financials_by_date(data, curr_date)

        if data.empty:
            raise NoMarketDataError(ticker, canonical, "no cash flow data")

        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()

        # Add header information
        header = f"# Cash Flow data for {canonical} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += _STATEMENT_UNITS_NOTE + "\n"

        return header + csv_string

    except NoMarketDataError:
        raise
    except Exception:
        raise


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
):
    """Get income statement data from yfinance."""
    canonical = require_symbol(ticker)
    try:
        ticker_obj = yf.Ticker(canonical)

        if freq.lower() == "quarterly":
            data = yf_retry(lambda: ticker_obj.quarterly_income_stmt)
        else:
            data = yf_retry(lambda: ticker_obj.income_stmt)

        data = filter_financials_by_date(data, curr_date)

        if data.empty:
            raise NoMarketDataError(ticker, canonical, "no income statement data")

        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()

        # Add header information
        header = f"# Income Statement data for {canonical} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += _STATEMENT_UNITS_NOTE + "\n"

        return header + csv_string

    except NoMarketDataError:
        raise
    except Exception:
        raise


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol of the company"]
):
    """Get insider transactions data from yfinance."""
    canonical = require_symbol(ticker)
    try:
        ticker_obj = yf.Ticker(canonical)
        data = yf_retry(lambda: ticker_obj.insider_transactions)

        # Empty is normal here (many valid symbols have no insider filings),
        # so report it plainly rather than treating the symbol as invalid.
        if data is None or data.empty:
            return f"No insider transactions reported for symbol '{canonical}'"

        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()

        # Add header information
        header = f"# Insider Transactions data for {canonical}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception:
        # Keep the empty-result path above (a real "no filings" answer); only
        # the failure path changes: re-raise so the router falls back instead
        # of caching an "Error retrieving..." string as truth.
        raise


def get_earnings_calendar_yfinance(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
    look_ahead_days: Annotated[int | None, "Days to look ahead; unused"] = None,
) -> str:
    """Earnings dates + last reported EPS surprise from yfinance (keyless).

    Keyless fallback for the earnings_calendar category: ``get_earnings_dates``
    returns the upcoming earnings date(s) and the most recent reported
    EPS/estimate/surprise, so a run never depends on the moomoo/Finnhub path.
    """
    canonical = require_symbol(ticker)
    try:
        ticker_obj = yf.Ticker(canonical)
        dates = yf_retry(lambda: ticker_obj.get_earnings_dates(limit=8))
        if dates is None or dates.empty:
            raise NoMarketDataError(ticker, canonical, "no earnings dates")
        # Countdown anchor: "in Nd" is the figure a report must quote rather
        # than compute itself. NVDA 2026-09-12 news.md called the next print
        # "83 days away" - the gap from the PRIOR print (2026-08-26 ->
        # 2026-11-17); from the analysis date the count was 66.
        cur = None
        if curr_date:
            try:
                cur = datetime.strptime(str(curr_date), "%Y-%m-%d").date()
            except (TypeError, ValueError):
                cur = None
        rows = []
        for index, row in dates.iterrows():
            eps_est = row.get("EPS Estimate")
            eps_act = row.get("Reported EPS")
            surprise = row.get("Surprise(%)")
            parts = []
            if eps_est is not None and not pd.isna(eps_est):
                parts.append(f"estimate={eps_est:.2f}")
            if eps_act is not None and not pd.isna(eps_act):
                parts.append(f"reported={eps_act:.2f}")
            if surprise is not None and not pd.isna(surprise):
                parts.append(f"surprise_pct={surprise:.2f}")
            line = f"{index.strftime('%Y-%m-%d')} " + (
                "; ".join(parts) if parts else "scheduled"
            )
            if cur is not None:
                days_out = (index.date() - cur).days
                if days_out >= 0:
                    line += f" (in {days_out}d)"
            rows.append(line)
        if not rows:
            raise NoMarketDataError(ticker, canonical, "no earnings dates")
        header = f"# Earnings calendar for {canonical}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        # The vendor computes Surprise(%) from EPS it does not expose at full
        # precision, so it need not equal (reported-estimate)/estimate on the
        # 2dp pair printed beside it (NVDA 2026-08-26: 6.16% vs 6.22%). Named
        # so a reader does not take the difference for a slip.
        header += (
            "# Note: surprise_pct is the vendor's own figure (from unrounded EPS),"
            " so it need not equal (reported-estimate)/estimate on the 2dp values"
            " shown.\n\n"
        )
        return header + "\n".join(rows)
    except NoMarketDataError:
        raise
    except Exception:
        raise


def get_institution_holdings_yfinance(
    ticker: Annotated[str, "ticker symbol of the company"],
) -> str:
    """Institutional + major holders from yfinance (keyless).

    Keyless ownership read: institutional holders (shares/change/date, e.g.
    Vanguard/BlackRock rows) and the major-holders % breakdown (insiders /
    institutions / public float). Complements moomoo's `get_institution_holdings`.
    """
    canonical = require_symbol(ticker)
    try:
        ticker_obj = yf.Ticker(canonical)
        inst = yf_retry(lambda: ticker_obj.institutional_holders)
        major = yf_retry(lambda: ticker_obj.major_holders)
        lines = []
        if inst is not None and not inst.empty:
            lines.append("Institutional holders (largest):")
            for _, row in inst.head(15).iterrows():
                holder = row.get("Holder")
                shares = row.get("Shares")
                date = row.get("Date Reported")
                pct = row.get("% Out")
                parts = []
                if shares is not None and not pd.isna(shares):
                    parts.append(f"shares={float(shares):,.0f}")
                if pct is not None and not pd.isna(pct):
                    parts.append(f"pct_out={float(pct):.2f}%")
                if date is not None and not pd.isna(date):
                    parts.append(f"date={date}")
                if parts:
                    lines.append(f"  {holder}: " + "; ".join(parts))
        if major is not None and not major.empty:
            lines.append("Major-holders breakdown:")
            for _, row in major.iterrows():
                label = row.get(0)
                pct = row.get(1)
                if label is not None and pct is not None:
                    lines.append(f"  {label}: {pct}")
        if not lines:
            raise NoMarketDataError(ticker, canonical, "no ownership data")
        header = f"# Ownership for {canonical}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + "\n".join(lines)
    except NoMarketDataError:
        raise
    except Exception:
        raise


def get_analyst_ratings_yfinance(
    ticker: Annotated[str, "ticker symbol of the company"],
) -> str:
    """Analyst recommendation summary + price-target consensus (keyless).

    Keyless sell-side read: yfinance ``recommendations_summary`` (strongBuy/
    buy/hold/sell/strongSell counts) + ``analyst_price_targets`` (current/low/
    high/mean/median). Complements the Finnhub ratings chain without a key.
    """
    canonical = require_symbol(ticker)
    try:
        ticker_obj = yf.Ticker(canonical)
        recs = yf_retry(lambda: ticker_obj.recommendations_summary)
        targets = yf_retry(lambda: ticker_obj.analyst_price_targets)
        lines = []
        if recs is not None and not recs.empty:
            # recommendations_summary is NEWEST-FIRST (0m, -1m, -2m, -3m), so
            # iloc[-1] read the three-month-old row and labelled it "latest".
            row = recs.iloc[0]
            if "period" in recs.columns:
                current = recs[recs["period"].astype(str) == "0m"]
                if not current.empty:
                    row = current.iloc[0]
            period = row.get("period")
            stamp = "" if period is None or pd.isna(period) else f" {period}"
            lines.append(f"Recommendation summary (latest period{stamp}):")
            # The 1.5.2 columns are strongBuy/buy/hold/sell/strongSell. There is
            # no "underperform" column, so the strong-sell count was silently
            # dropped from every report this leg ever produced.
            for col in ("strongBuy", "buy", "hold", "sell", "strongSell"):
                val = row.get(col)
                if val is not None and not pd.isna(val):
                    lines.append(f"  {col}: {int(val)}")
        # yfinance declares this a dict, not a DataFrame
        # (base.py::get_analyst_price_targets -> "Keys: current low high mean
        # median"), so the old .empty / .iloc[-1] reads raised AttributeError on
        # every call and killed the whole leg.
        if isinstance(targets, dict) and targets:
            lines.append("Analyst price-target consensus:")
            for label in ("current", "low", "high", "mean", "median"):
                val = targets.get(label)
                if val is not None and not pd.isna(val):
                    lines.append(
                        f"  {label}: {val:.2f}" if isinstance(val, float) else f"  {label}: {val}"
                    )
        if not lines:
            raise NoMarketDataError(ticker, canonical, "no analyst data")
        header = f"# Analyst ratings for {canonical}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + "\n".join(lines)
    except NoMarketDataError:
        raise
    except Exception:
        raise
