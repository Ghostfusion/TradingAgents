"""Symbol normalization and market-data error types for vendor calls.

Yahoo Finance (the default vendor) uses specific ticker conventions that
differ from the broker / TradingView / MT5 style symbols users often type:

    user types        Yahoo wants       why
    ---------------   ---------------   -----------------------------------
    XAUUSD, XAUUSD+   GC=F              gold has no forex pair on Yahoo;
                                        it is quoted as a COMEX future
    EURUSD            EURUSD=X          spot forex pairs take a ``=X`` suffix
    BTCUSD            BTC-USD           crypto pairs use a ``-`` separator
    SPX500, US500     ^GSPC             index CFDs map to Yahoo index symbols

Passing the raw broker symbol to Yahoo returns an empty result, which the
agents previously received as free text and could hallucinate a price
around (see issue #781). Centralizing the mapping here means every yfinance
entry point resolves symbols the same way, and new instruments are added by
appending a table row rather than editing call sites.
"""

from __future__ import annotations

import logging

# NoMarketDataError lives in the vendor-error taxonomy (errors.py); re-exported
# here for the many call sites that import it alongside normalize_symbol.
from .errors import NoMarketDataError as NoMarketDataError

logger = logging.getLogger(__name__)


# ISO-4217 codes common enough to appear in retail forex pairs. A bare
# six-letter symbol whose halves are BOTH in this set is treated as a spot
# forex pair and given Yahoo's ``=X`` suffix.
_FOREX_CURRENCIES = frozenset(
    {
        "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD",
        "CNY", "CNH", "HKD", "SGD", "SEK", "NOK", "DKK", "PLN",
        "MXN", "ZAR", "TRY", "INR", "KRW", "BRL", "RUB", "THB",
    }
)

# Crypto bases that brokers quote against USD without a separator.
_CRYPTO_BASES = frozenset(
    {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "BCH", "DOT", "AVAX", "LINK"}
)

# Explicit aliases for instruments whose broker symbol does not map to a
# Yahoo symbol by rule. Metals/energy resolve to their front-month future;
# index CFD names resolve to the underlying Yahoo index symbol. Extend by
# adding rows — no call site changes required.
_ALIASES = {
    # Precious metals (spot names -> COMEX/NYMEX futures)
    "XAUUSD": "GC=F", "XAU": "GC=F", "GOLD": "GC=F",
    "XAGUSD": "SI=F", "XAG": "SI=F", "SILVER": "SI=F",
    "XPTUSD": "PL=F", "XPDUSD": "PA=F",
    # Energy
    "WTICOUSD": "CL=F", "USOIL": "CL=F", "WTI": "CL=F",
    "BCOUSD": "BZ=F", "UKOIL": "BZ=F", "BRENT": "BZ=F",
    "NATGAS": "NG=F", "XNGUSD": "NG=F",
    "COPPER": "HG=F", "XCUUSD": "HG=F",
    # Index CFDs -> Yahoo index symbols
    "SPX500": "^GSPC", "US500": "^GSPC", "SPX": "^GSPC",
    "NAS100": "^NDX", "US100": "^NDX", "USTEC": "^NDX",
    "US30": "^DJI", "DJI30": "^DJI", "WS30": "^DJI",
    "GER40": "^GDAXI", "GER30": "^GDAXI", "DE40": "^GDAXI",
    "UK100": "^FTSE", "JP225": "^N225", "JPN225": "^N225",
    "FRA40": "^FCHI", "EU50": "^STOXX50E", "HK50": "^HSI",
}

# Crypto quote currencies that all map to Yahoo's USD pair. Yahoo lists only
# ``<BASE>-USD`` (not the USDT/USDC stablecoin pairs), so a broker symbol quoted
# in any of these resolves to ``-USD`` (#982). Longest first so ``USDT``/``USDC``
# match before the ``USD`` substring.
_CRYPTO_QUOTES = ("USDT", "USDC", "USD")


def crypto_base(raw: str) -> str | None:
    """Return the crypto base (e.g. ``BTC``) for a known USD/USDT/USDC-quoted
    crypto symbol in any form the pipeline may hold — ``BTC-USD``, ``BTCUSD``,
    ``BTC-USDT`` — or None for non-crypto symbols. Purely syntactic.
    """
    if not isinstance(raw, str):
        return None
    compact = raw.strip().upper().rstrip("+").replace("-", "")
    for quote in _CRYPTO_QUOTES:
        if compact.endswith(quote):
            base = compact[: -len(quote)]
            return base if base in _CRYPTO_BASES else None
    return None


def _normalize_crypto(s: str) -> str | None:
    """Return ``<BASE>-USD`` for a known USD/USDT/USDC-quoted crypto, else None."""
    base = crypto_base(s)
    return f"{base}-USD" if base else None


# Single-letter dotted suffix that is a Yahoo *exchange* market, not a US
# share class. Yahoo's only single-letter exchange is London (``.L``), e.g.
# ``AZN.L``; every other single-letter dotted suffix on Yahoo (``.A``/``.B``/
# ``.C``/``.D``/``.K``...) is a US share class, which Yahoo quotes with a
# HYPHEN (``BRK-B``, ``BF-A``), not a dot. Converting ``.X -> -X`` fixes e.g.
# moomoo's ``MOG.A``/``PBR.A`` (which Yahoo cannot resolve) into ``MOG-A``/
# ``PBR-A``. Multi-letter suffixes (``.SA`` Brazil, ``.TO``, ``.AX``, ``.HK``,
# ``.NS``, ``.BO``, ...) are real exchange markets and are never touched.
_SINGLE_LETTER_EXCHANGE_SUFFIXES = frozenset({"L"})  # London


def _normalize_share_class(s: str) -> str | None:
    """Return the hyphen form of a dotted US share-class symbol, else None.

    Yahoo quotes US share classes with a hyphen: ``BRK.B`` -> ``BRK-B``,
    ``MOG.A`` -> ``MOG-A``, ``PBR.A`` -> ``PBR-A``. A trailing ``.X`` where
    ``X`` is a single letter (not the ``.L`` London exchange) and the ticker
    part is alphanumeric qualifies; anything else (multi-letter exchange
    suffixes like ``.SA``/``.TO``/``.AX``, indices, forex, crypto) is left
    unchanged.
    """
    if len(s) < 3 or s[-2] != ".":
        return None
    letter = s[-1]
    if not letter.isalpha() or letter in _SINGLE_LETTER_EXCHANGE_SUFFIXES:
        return None
    head = s[:-2]
    if not head or not head.isalnum():
        return None
    return f"{head}-{letter}"


def normalize_symbol(raw: str) -> str:
    """Map a user/broker symbol to its canonical Yahoo Finance symbol.

    Resolution order (first match wins):
      1. Explicit alias table (metals, energy, index CFDs).
      2. Crypto rule: a known crypto base quoted in USD/USDT/USDC (dashed or
         not) -> ``BASE-USD``.
      3. Forex rule: six letters that are two ISO currency codes -> ``PAIR=X``.
      4. US share class: a dotted single-letter suffix (``.A``/``.B``/...) ->
         hyphen form (``-A``/``-B``) for Yahoo (``BRK.B`` -> ``BRK-B``). The
         ``.L`` London suffix and all multi-letter exchange suffixes are kept.
      5. Otherwise the upper-cased symbol is returned unchanged (plain
         equities, ETFs, Yahoo-native symbols like ``GC=F`` or ``^GSPC``).

    A trailing ``+`` (broker CFD marker, e.g. ``XAUUSD+``) is stripped before
    matching. The function is purely syntactic — it performs no network
    calls — so it is safe to apply on every request.

    Blank / whitespace-only / non-string input canonicalizes to ``""`` (the
    raw value is never returned), so a vendor caller can detect "nothing to
    query" with ``not canonical.strip()`` instead of letting a blank reach
    yfinance and blow up with a raw TypeError + noisy HTTP ERROR logs.
    """
    if not isinstance(raw, str) or not raw.strip():
        return ""

    s = raw.strip().upper()
    # Broker CFD/qualifier suffixes Yahoo never uses.
    s = s.rstrip("+")

    crypto = _normalize_crypto(s)
    if s in _ALIASES:
        canonical = _ALIASES[s]
    elif crypto is not None:
        canonical = crypto
    elif len(s) == 6 and s[:3] in _FOREX_CURRENCIES and s[3:] in _FOREX_CURRENCIES:
        canonical = f"{s}=X"
    else:
        share = _normalize_share_class(s)
        canonical = share if share is not None else s

    if canonical != raw.strip().upper():
        logger.info("Resolved symbol %r to Yahoo symbol %r", raw, canonical)
    return canonical


def require_symbol(raw) -> str:
    """Normalize and require a non-blank symbol for a vendor call.

    Returns the canonical symbol, or raises ``NoMarketDataError`` (the typed
    vendor error the router understands) when the input is blank/whitespace -
    so the chain degrades to a clean ``NO_DATA_AVAILABLE: blank ticker``
    sentinel instead of leaking yfinance's raw ``TypeError`` / HTTP-error
    logs into the run. Every yfinance entry point should resolve its symbol
    through this helper.
    """
    canonical = normalize_symbol(raw)
    if not canonical or not canonical.strip():
        shown = "''" if raw in (None, "") else repr(raw)
        raise NoMarketDataError(
            str(raw or ""),
            "<blank>",
            detail=f"blank/empty ticker symbol {shown}: nothing to query",
        )
    return canonical
