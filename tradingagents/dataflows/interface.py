import logging

from .alpha_vantage import (
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_global_news as get_alpha_vantage_global_news,
    get_income_statement as get_alpha_vantage_income_statement,
    get_indicator as get_alpha_vantage_indicator,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_stock as get_alpha_vantage_stock,
)
from .config import get_config
from .errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)
from .finnhub import (
    get_analyst_ratings_finnhub,
    get_basic_financials_finnhub,
    get_company_peers_finnhub,
    get_earnings_calendar_finnhub,
    get_global_news_finnhub,
    get_insider_activity_finnhub,
    get_news_finnhub,
)
from .fred import get_macro_data as get_fred_macro_data
from .massive import (
    get_macro_indicators_massive,
    get_news_massive,
)
from .moomoo import (
    get_analyst_ratings_moomoo,
    get_balance_sheet_moomoo,
    get_capital_flow_moomoo,
    get_cashflow_moomoo,
    get_corporate_actions_moomoo,
    get_earnings_calendar_moomoo,
    get_earnings_catalyst_moomoo,
    get_earnings_surprise_history_moomoo,
    get_economic_calendar_moomoo,
    get_expected_move_moomoo,
    get_fed_watch_moomoo,
    get_fundamentals_moomoo,
    get_income_statement_moomoo,
    get_indicators_moomoo,
    get_insider_transactions_moomoo,
    get_institution_holdings_moomoo,
    get_macro_indicators_moomoo,
    get_market_breadth_moomoo,
    get_news_moomoo,
    get_options_chain_moomoo,
    get_prediction_markets_moomoo,
    get_revenue_breakdown_moomoo,
    get_short_interest_moomoo,
    get_smart_money_moomoo,
    get_stock_data_moomoo,
)
from .polymarket import get_prediction_markets as get_polymarket_prediction_markets
from .sec_edgar import get_sec_filings
from .vendor_cache import vendor_cache
from .y_finance import (
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_fundamentals as get_yfinance_fundamentals,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
    get_stock_stats_indicators_window,
    get_YFin_data_online,
)
from .yfinance_news import get_global_news_yfinance, get_news_yfinance
from .yfinance_options import get_options_chain_yfinance
from .yfinance_short_interest import get_short_interest_yfinance

logger = logging.getLogger(__name__)

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {"description": "OHLCV stock price data", "tools": ["get_stock_data"]},
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": ["get_indicators"],
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
            "get_basic_financials",
            "get_company_peers",
            "get_insider_activity",
        ],
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ],
    },
    "macro_data": {
        "description": "Macroeconomic indicators (rates, inflation, labor, growth)",
        "tools": [
            "get_macro_indicators",
        ],
    },
    "prediction_markets": {
        "description": "Market-implied probabilities for forward-looking events",
        "tools": [
            "get_prediction_markets",
        ],
    },
    "analyst_ratings": {
        "description": "Sell-side analyst ratings and price targets",
        "tools": [
            "get_analyst_ratings",
        ],
    },
    "earnings_calendar": {
        "description": "Upcoming earnings dates and EPS surprises",
        "tools": [
            "get_earnings_calendar",
        ],
    },
    "options_data": {
        "description": "Options implied volatility, open interest, and put/call ratio",
        "tools": [
            "get_options_chain",
        ],
    },
    "sec_filings": {
        "description": "SEC EDGAR filings (8-K, 10-K/Q, S-1/3, 13D/G)",
        "tools": [
            "get_sec_filings",
        ],
    },
    "short_interest": {
        "description": "Short interest, days-to-cover, and ownership split",
        "tools": [
            "get_short_interest",
        ],
    },
    # moomoo-only enrichment categories (Tier 1/2). All optional — a vendor
    # failure degrades to a sentinel instead of aborting the run.
    "capital_flow": {
        "description": "Capital inflow/outflow by order size and session distribution",
        "tools": ["get_capital_flow"],
    },
    "smart_money": {
        "description": "ARK fund institutional activity in a ticker",
        "tools": ["get_smart_money"],
    },
    "economic_calendar": {
        "description": "Upcoming economic events with consensus/actual (CPI, FOMC, payrolls)",
        "tools": ["get_economic_calendar"],
    },
    "fed_watch": {
        "description": "Market-implied Fed target-rate probabilities",
        "tools": ["get_fed_watch"],
    },
    "market_breadth": {
        "description": "US market breadth: sector heat map and rise/fall distribution",
        "tools": ["get_market_breadth"],
    },
    "revenue_breakdown": {
        "description": "Segment/regional revenue breakdown for the latest period",
        "tools": ["get_revenue_breakdown"],
    },
    "corporate_actions": {
        "description": "Dividend history, buybacks, and stock splits",
        "tools": ["get_corporate_actions"],
    },
    "earnings_catalyst": {
        "description": "Historical earnings-day implied move, IV crush, and price reaction",
        "tools": ["get_earnings_catalyst"],
    },
    # A-series enrichment (moomoo-only, optional).
    "institution_data": {
        "description": "Institutional ownership % and changes by reporting period (13F-style)",
        "tools": ["get_institution_holdings"],
    },
    "earnings_surprise": {
        "description": "Historical earnings surprises (EPS actual vs estimate) + day reaction + implied move",
        "tools": ["get_earnings_surprise_history"],
    },
    "expected_move": {
        "description": "Option-implied expected move for the upcoming earnings print",
        "tools": ["get_expected_move"],
    },
}

VENDOR_LIST = [
    "yfinance",
    "fred",
    "polymarket",
    "alpha_vantage",
    "finnhub",
    "sec_edgar",
    "moomoo",
    "massive",
]

# Optional enrichment categories. These add macro/event context to the news
# analyst but are not core to a decision, so a vendor failure here degrades to a
# sentinel instead of aborting the run (a bad LLM-supplied indicator, a missing
# key, or a network blip should not crash an analysis over flavour data). Core
# categories (prices, fundamentals, news) still raise so a broken primary is loud.
OPTIONAL_CATEGORIES = {
    "macro_data",
    "prediction_markets",
    "analyst_ratings",
    "earnings_calendar",
    "options_data",
    "sec_filings",
    "short_interest",
    # moomoo-only enrichment (Tier 1/2 + A-series): failures degrade to a sentinel.
    "capital_flow",
    "smart_money",
    "economic_calendar",
    "fed_watch",
    "market_breadth",
    "revenue_breakdown",
    "corporate_actions",
    "earnings_catalyst",
    "institution_data",
    "earnings_surprise",
    "expected_move",
}

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "moomoo": get_stock_data_moomoo,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "moomoo": get_indicators_moomoo,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
        "moomoo": get_fundamentals_moomoo,
        "finnhub": get_basic_financials_finnhub,
    },
    "get_basic_financials": {
        "finnhub": get_basic_financials_finnhub,
    },
    "get_company_peers": {
        "finnhub": get_company_peers_finnhub,
    },
    "get_insider_activity": {
        "finnhub": get_insider_activity_finnhub,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
        "moomoo": get_balance_sheet_moomoo,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
        "moomoo": get_cashflow_moomoo,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
        "moomoo": get_income_statement_moomoo,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
        "finnhub": get_news_finnhub,
        "moomoo": get_news_moomoo,
        "massive": get_news_massive,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
        "finnhub": get_global_news_finnhub,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
        "moomoo": get_insider_transactions_moomoo,
    },
    # macro_data
    "get_macro_indicators": {
        "fred": get_fred_macro_data,
        "massive": get_macro_indicators_massive,
        "moomoo": get_macro_indicators_moomoo,
    },
    # prediction_markets
    "get_prediction_markets": {
        "polymarket": get_polymarket_prediction_markets,
        "moomoo": get_prediction_markets_moomoo,
    },
    # analyst_ratings
    "get_analyst_ratings": {
        "finnhub": get_analyst_ratings_finnhub,
        "moomoo": get_analyst_ratings_moomoo,
    },
    # earnings_calendar
    "get_earnings_calendar": {
        "finnhub": get_earnings_calendar_finnhub,
        "moomoo": get_earnings_calendar_moomoo,
    },
    # options_data
    "get_options_chain": {
        "yfinance": get_options_chain_yfinance,
        "moomoo": get_options_chain_moomoo,
    },
    # sec_filings
    "get_sec_filings": {
        "sec_edgar": get_sec_filings,
    },
    # short_interest
    "get_short_interest": {
        "yfinance": get_short_interest_yfinance,
        "moomoo": get_short_interest_moomoo,
    },
    # moomoo-only enrichment (Tier 1/2)
    "get_capital_flow": {
        "moomoo": get_capital_flow_moomoo,
    },
    "get_smart_money": {
        "moomoo": get_smart_money_moomoo,
    },
    "get_economic_calendar": {
        "moomoo": get_economic_calendar_moomoo,
    },
    "get_fed_watch": {
        "moomoo": get_fed_watch_moomoo,
    },
    "get_market_breadth": {
        "moomoo": get_market_breadth_moomoo,
    },
    "get_revenue_breakdown": {
        "moomoo": get_revenue_breakdown_moomoo,
    },
    "get_corporate_actions": {
        "moomoo": get_corporate_actions_moomoo,
    },
    "get_earnings_catalyst": {
        "moomoo": get_earnings_catalyst_moomoo,
    },
    "get_institution_holdings": {
        "moomoo": get_institution_holdings_moomoo,
    },
    "get_earnings_surprise_history": {
        "moomoo": get_earnings_surprise_history_moomoo,
    },
    "get_expected_move": {
        "moomoo": get_expected_move_moomoo,
    },
}


def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")


def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")


def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(",")]

    # An explicit "none"/"off"/"disabled" vendor choice disables the whole
    # category: the router returns a clear placeholder and never calls any
    # vendor. This lets callers turn off an optional data source (e.g. analyst
    # ratings for crypto) without deleting it from the config. An empty string
    # is NOT "disabled" — it is treated as "default" below, so use "none".
    if any(v.lower() in ("none", "off", "disabled") for v in primary_vendors):
        return (
            f"DATA_DISABLED: the '{category}' data source is disabled in the "
            f"current configuration. Proceed without it; do not fabricate values."
        )

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    all_available_vendors = list(VENDOR_METHODS[method].keys())

    # The configured vendor list IS the chain: we do NOT silently fall back to
    # vendors the user did not choose (#988/#289) — that returned data from an
    # unexpected source and caused cross-vendor inconsistencies. For multi-vendor
    # fallback, list them in order, e.g. data_vendors="yfinance,alpha_vantage".
    # The "default" sentinel (no explicit config) uses all available vendors.
    explicit = [v for v in primary_vendors if v and v != "default"]
    if explicit:
        vendor_chain = [v for v in explicit if v in VENDOR_METHODS[method]]
        if not vendor_chain:
            raise ValueError(
                f"Configured vendor(s) {explicit} not available for '{method}'. "
                f"Available: {all_available_vendors}."
            )
    else:
        vendor_chain = all_available_vendors

    last_no_data: NoMarketDataError | None = None
    first_error: Exception | None = None

    # Serve a fresh TTL-cache hit without touching any vendor (quota savings).
    cached = vendor_cache.get(method, category, args, kwargs)
    if cached is not None:
        logger.info("Vendor cache hit for %s (%s); skipping network fetch.", method, category)
        return cached

    for vendor in vendor_chain:
        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            result = impl_func(*args, **kwargs)
            # Log which vendor actually served the call so free-tier quota burn
            # is visible in the logs, then cache successful results.
            logger.info("Vendor %r served %s (%s)", vendor, method, category)
            vendor_cache.set(method, category, args, kwargs, result)
            return result
        except VendorRateLimitError:
            logger.warning("Vendor %r rate-limited for %s; trying next vendor.", vendor, method)
            continue
        except VendorNotConfiguredError as e:
            logger.warning("Vendor %r not configured for %s; trying next vendor.", vendor, method)
            if first_error is None:
                first_error = e  # Surface it if no other vendor can serve the call.
            continue
        except NoMarketDataError as e:
            last_no_data = e  # No data here; another configured vendor may have it
            continue
        except Exception as e:
            # Don't let one vendor's failure crash the call when another can
            # serve it, but never swallow silently: a broken primary must be
            # visible in the logs (#989), not hidden behind a fallback's verdict.
            logger.warning("Vendor %r failed for %s: %s", vendor, method, e)
            if first_error is None:
                first_error = e
            continue

    # If any vendor reported "no data", the symbol is genuinely unavailable.
    # Return one explicit, instructive sentinel rather than a vendor-specific
    # empty string, so the agent reports "unavailable" instead of inventing a
    # value. This takes precedence over incidental fallback errors.
    if last_no_data is not None:
        if first_error is not None:
            # A vendor also hit a real error; surface it in logs so the no-data
            # verdict can't hide a broken primary (network/auth/etc.).
            logger.warning(
                "Returning NO_DATA for %s, but a vendor errored earlier: %s",
                method,
                first_error,
            )
        sym = last_no_data.symbol
        canonical = last_no_data.canonical
        resolved = "" if canonical == sym else f" (resolved to '{canonical}')"
        # Surface the typed error's detail (e.g. "latest row is 2025-06-11 ...
        # stale") so the agent sees the specific reason — invalid symbol, no
        # coverage, or stale data — not just a generic "unavailable".
        reason = f" ({last_no_data.detail})" if last_no_data.detail else ""
        return (
            f"NO_DATA_AVAILABLE: No usable market data for '{sym}'{resolved} from "
            f"any configured vendor{reason}. The symbol may be invalid, delisted, "
            f"not covered, or the vendor returned stale data. Do not estimate or "
            f"fabricate values — report that data is unavailable for this symbol."
        )

    # No vendor returned data and none reported clean "no data" — surface the
    # first real error (e.g. the primary vendor's network failure). Optional
    # enrichment categories degrade to a sentinel instead, so flavour data can't
    # abort the run.
    if first_error is not None:
        if category in OPTIONAL_CATEGORIES:
            logger.warning("Optional %s unavailable for %s: %s", category, method, first_error)
            return (
                f"DATA_UNAVAILABLE: optional {category} could not be retrieved "
                f"({first_error}). Proceed without it; do not fabricate values."
            )
        raise first_error

    raise RuntimeError(f"No available vendor for '{method}'")
