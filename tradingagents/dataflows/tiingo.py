"""Tiingo data vendor (free "Starter" tier) — additive market data source.

Tiingo (https://www.tiingo.com) is a stock/fundamental market-data provider.
The free *Starter* tier (live-probed with the project's key) exposes:

- **EOD OHLCV** (`/tiingo/daily/{t}/prices`) — deep history (7+ yrs), with
  `adjClose`/`divCash`/`splitFactor` and `resampleFreq` in
  daily/weekly/monthly/annually;
- **Fundamental statements** (`/tiingo/fundamentals/{t}/statements`) — clean
  JSON income / balance / cashflow keyed by `dataCode`
  (`revenue`, `costRev`, `epsDil`, `shareswaDil`, `netIncComStock`,
  `equity`, `retainedEarnings`, `inventory`, `ncfo`, `capex`, ...);
- **IEX quote snapshot** (`/iex/{t}`) — a delayed quote (prevClose/high/low/
  last/volume);
- **Crypto OHLCV** (`/tiingo/crypto/prices?tickers=btcusd`) — per-asset bars.

Not on the free tier (probed, do not wire): `tiingo/news` (403 permission) and
`tiingo/intraday` (404 paywall).

Tier limits are low (~1,000 calls/day, 50/hr, 500 symbols/mo), so Tiingo sits
**last** in vendor chains after eodhd/moomoo/massive and leans on the repo's
disk TTL vendor cache. It follows the same typed-error taxonomy as massive/
eodhd so ``route_to_vendor`` degrades to the next vendor on a missing key
(``VendorNotConfiguredError``), a 429 (``VendorRateLimitError``) or no rows
(``NoMarketDataError``).

Statement strings are rendered as ``label : value`` blocks with
canonical-friendly English labels (``revenue`` / ``cost of goods sold`` /
``total assets`` / ``total equity`` / ``cash and cash equivalents`` /
``operating cash flow`` / ``capital expenditure`` ...) so
``statement_parsing._canonicalize`` maps them into the project's canonical
line items unchanged via ``_ROW_ALIASES`` — a second free fundamentals source
behind moomoo, and a working one on the free tier where Massive's
snapshots/fundamentals 403.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime

from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://api.tiingo.com"
TIMEOUT = 20
_MAX_RETRIES = 2

# Canonical-friendly English label for each streamable Tiingo dataCode.
# Only codes whose labels match ``statement_parsing._ROW_ALIASES`` are mapped,
# so the canonicalizer picks them up; the rest are informational.
_INCOME_CODES = {
    "revenue": "revenue",
    "costRev": "cost of goods sold",
    "grossProfit": "gross profit",
    "sga": "selling general",
    "opinc": "operating income",
    "ebit": "ebit",
    "netIncComStock": "net income",
    "epsDil": "diluted eps",
    "shareswaDil": "diluted weighted average shares",
    "shareswa": "weighted average shares",
    "taxExp": "tax expense",
    "intexp": "interest expense",
}
_BALANCE_CODES = {
    "cashAndEq": "cash and cash equivalents",
    "totalAssets": "total assets",
    "totalLiabilities": "total liabilities",
    "equity": "total equity",
    "retainedEarnings": "retained earnings",
    "inventory": "inventory",
    "acctRec": "net receivables",
    "assetsCurrent": "current assets",
    "liabilitiesCurrent": "current liabilities",
    "ppeq": "property plant",
    "investmentsCurrent": "short-term investments",
    "debt": "total debt",
}
_CASHFLOW_CODES = {
    "ncfo": "operating cash flow",
    "capex": "capital expenditure",
    "payDiv": "cash dividends paid",
    "depamor": "depreciation",
    "freeCashFlow": "free cash flow",
}


def tiingo_api_key() -> str | None:
    """Tiingo key from config or environment; None when unset."""
    try:
        from tradingagents.dataflows.config import get_config

        key = get_config().get("tiingo_api_key")
    except Exception:
        key = None
    if key:
        return str(key)
    return os.environ.get("TIINGO_API_KEY")


def _tiingo_get(path: str, params: dict | None = None) -> list | dict | None:
    """Authenticated GET; parsed JSON or None on any non-data failure.

    Tiingo auth is ``Authorization: Token <key>``. Raises the typed taxonomy:
    401/403 -> VendorNotConfiguredError (bad key / entitlements), 429 /
    >=500 -> VendorRateLimitError (retried), other non-200 -> None, empty
    returns left to the caller.
    """
    import requests as _requests

    key = tiingo_api_key()
    if not key:
        raise VendorNotConfiguredError(
            "Tiingo API key is not configured. Set TIINGO_API_KEY in .env "
            "(or tiingo_api_key in config)."
        )
    url = f"{BASE}/{path}"
    headers = {"Authorization": f"Token {key}"}
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if resp.status_code in (401, 403):
                # 403 can be an entitlements gap (e.g. the news endpoint) - the
                # key is valid but the plan lacks the dataset.
                raise VendorNotConfiguredError(
                    f"Tiingo returned HTTP {resp.status_code} for {path} (bad "
                    "key or plan lacks this dataset)"
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < _MAX_RETRIES:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise VendorRateLimitError(
                    f"Tiingo {path} returned HTTP {resp.status_code}"
                )
            if resp.status_code != 200:
                logger.warning("Tiingo %s: status %s", path, resp.status_code)
                return None
            return resp.json()
        except VendorNotConfiguredError:
            raise
        except VendorRateLimitError:
            raise
        except _requests.Timeout as exc:
            raise VendorRateLimitError(f"Tiingo {path} timed out") from exc
        except _requests.RequestException as exc:
            raise VendorRateLimitError(f"Tiingo {path} request failed: {exc}") from exc
    return None


def _fmt(v: float) -> str:
    """Render a numeric value without trailing scientific noise."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "n/a"
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return f"{f:.4f}".rstrip("0").rstrip(".")


def _render_statements(data, statement_type: str, codes: dict,
                       symbol: str) -> str:
    """Render Tiingo fundamental statements as ``label : value`` text blocks.

    One block per reported quarter (newest first). Only the codes in ``codes``
    render; the labels are canonical-friendly so statement_parsing maps them.
    """
    if not isinstance(data, list):
        data = []
    if not data:
        raise NoMarketDataError(
            symbol, symbol, detail=f"no {statement_type} rows for {symbol}"
        )
    lines = [f"## {symbol} {statement_type.replace('-', ' ')} — Tiingo", ""]
    for q in data:
        period = str(q.get("date") or "")
        rows = q.get("statementData") or {}
        if isinstance(rows, dict):
            rows = rows.get(statement_type) or []
        table = {r.get("dataCode"): r.get("value") for r in rows} if isinstance(rows, list) else {}
        entries = [(codes.get(k), v) for k, v in table.items() if k in codes and codes.get(k)]
        if not entries:
            continue
        lines.append(f"### {period[:10]} ({q.get('year')} Q{q.get('quarter')})")
        for label, value in entries:
            lines.append(f"{label} : {_fmt(value)}")
        lines.append("")
    if len(lines) == 2:
        raise NoMarketDataError(
            symbol, symbol, detail=f"no usable {statement_type} rows for {symbol}"
        )
    footer = (
        f"# Data retrieved via Tiingo on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    return "\n".join(lines).rstrip() + "\n" + footer


def _validate(start_date: str, end_date: str) -> None:
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")


def get_stock_data_tiingo(symbol: str, start_date: str, end_date: str,
                          resample_freq: str | None = None) -> str:
    """Daily (or resampled) OHLCV via Tiingo, as CSV.

    Matches the yfinance/moomoo/eodhd shape (``Date,Open,High,Low,Close,Volume``)
    so the screener's ``_fetch_ohlcv`` and the analyst tool loops consume it
    unchanged. ``resample_freq`` is one of daily/weekly/monthly/annually.
    """
    _validate(start_date, end_date)
    params = {"startDate": start_date, "endDate": end_date}
    if resample_freq:
        params["resampleFreq"] = resample_freq
    data = _tiingo_get(f"tiingo/daily/{symbol}/prices", params)
    if not isinstance(data, list) or not data:
        raise NoMarketDataError(
            symbol, symbol, detail=f"no rows between {start_date} and {end_date}"
        )
    rows = list(data)  # Tiingo returns oldest-first
    lines = ["Date,Open,High,Low,Close,Volume"]
    for r in rows:
        try:
            date = str(r.get("date") or "")[:10]
            o = float(r.get("open"))
            h = float(r.get("high"))
            lo = float(r.get("low"))
            c = float(r.get("close"))
            v = float(r.get("volume") or 0)
        except (TypeError, ValueError):
            continue
        lines.append(f"{date},{o:.2f},{h:.2f},{lo:.2f},{c:.2f},{v:.0f}")
    if len(lines) == 1:
        raise NoMarketDataError(
            symbol, symbol, detail=f"no rows between {start_date} and {end_date}"
        )
    header = (
        f"# Stock data for {symbol} (Tiingo) from {start_date} to {end_date}\n"
        f"# Total records: {len(rows)}\n"
        f"# Data retrieved via Tiingo on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + "\n".join(lines)


def get_income_statement_tiingo(symbol: str, start_date: str, end_date: str) -> str:
    """Income statement via Tiingo, rendered as canonical-friendly text."""
    _validate(start_date, end_date)
    data = _tiingo_get(
        f"tiingo/fundamentals/{symbol}/statements",
        {"statementType": "incomeStatement", "startDate": start_date, "endDate": end_date},
    ) or []
    return _render_statements(data, "incomeStatement", _INCOME_CODES, symbol)


def get_balance_sheet_tiingo(symbol: str, start_date: str, end_date: str) -> str:
    """Balance sheet via Tiingo, rendered as canonical-friendly text."""
    _validate(start_date, end_date)
    data = _tiingo_get(
        f"tiingo/fundamentals/{symbol}/statements",
        {"statementType": "balanceSheet", "startDate": start_date, "endDate": end_date},
    ) or []
    return _render_statements(data, "balanceSheet", _BALANCE_CODES, symbol)


def get_cashflow_tiingo(symbol: str, start_date: str, end_date: str) -> str:
    """Cash-flow statement via Tiingo, rendered as canonical-friendly text."""
    _validate(start_date, end_date)
    data = _tiingo_get(
        f"tiingo/fundamentals/{symbol}/statements",
        {"statementType": "cashFlow", "startDate": start_date, "endDate": end_date},
    ) or []
    return _render_statements(data, "cashFlow", _CASHFLOW_CODES, symbol)


def get_fundamentals_tiingo(symbol: str, start_date: str, end_date: str) -> str:
    """Combined fundamentals (income + balance + cashflow) for a ticker."""
    parts = []
    for fn in (get_income_statement_tiingo, get_balance_sheet_tiingo,
               get_cashflow_tiingo):
        try:
            parts.append(fn(symbol, start_date, end_date))
        except Exception as exc:  # noqa: BLE001 - partial statements degrade
            logger.debug("Tiingo %s %s: %s", symbol, fn.__name__, exc)
    if not parts:
        raise NoMarketDataError(
            symbol, symbol, detail=f"no fundamentals for {symbol}"
        )
    return "\n\n".join(parts)


def get_market_snapshot_tiingo(ticker: str) -> str:
    """Delayed IEX quote snapshot via Tiingo — a verification-grade price read.

    Renders prevClose / open / high / low / last / volume with a timestamp; an
    explicit 'unavailable' message when the IEX feed returns no quote (so the
    caller treats it as a degrade, never a fabricated price).
    """
    data = _tiingo_get(f"iex/{ticker}")
    if not isinstance(data, list) or not data:
        raise NoMarketDataError(
            ticker, ticker, detail=f"no IEX quote for {ticker}"
        )
    row = data[0]
    lines = [
        f"## {ticker} — IEX snapshot (Tiingo)",
        f"timestamp: {row.get('timestamp') or 'n/a'}",
        f"open: {_fmt(row.get('open'))}",
        f"high: {_fmt(row.get('high'))}",
        f"low: {_fmt(row.get('low'))}",
        f"last: {_fmt(row.get('tngoLast') if row.get('tngoLast') is not None else row.get('last'))}",
        f"prev_close: {_fmt(row.get('prevClose'))}",
        f"volume: {_fmt(row.get('volume'))}",
    ]
    return "\n".join(lines)


def get_crypto_prices_tiingo(ticker: str, start_date: str, end_date: str,
                             convert_currency: str = "USD") -> str:
    """Crypto OHLCV via Tiingo, as CSV (btcusd -> BTC-USD normalized by caller).

    The ``priceData`` array is rendered as ``Date,Open,High,Low,Close,Volume``.
    TradingAgents normalizes crypto symbols to Yahoo ``BTC-USD``; this function
    expects the Tiingo code form (``btcusd``) - see ``_crypto_code``.
    """
    _validate(start_date, end_date)
    data = _tiingo_get(
        "tiingo/crypto/prices",
        {
            "tickers": ticker,
            "convertCurrency": convert_currency,
            "startDate": start_date,
            "endDate": end_date,
        },
    )
    rows = []
    if isinstance(data, list) and data:
        rows = (data[0].get("priceData") or []) if isinstance(data[0], dict) else []
    if not rows:
        raise NoMarketDataError(
            ticker, ticker, detail=f"no crypto rows for {ticker}"
        )
    lines = ["Date,Open,High,Low,Close,Volume"]
    for r in rows:
        try:
            date = str(r.get("date") or "")[:10]
            o = float(r.get("open"))
            h = float(r.get("high"))
            lo = float(r.get("low"))
            c = float(r.get("close"))
            v = float(r.get("volume") or 0)
        except (TypeError, ValueError):
            continue
        lines.append(f"{date},{o:.2f},{h:.2f},{lo:.2f},{c:.2f},{v:.4f}")
    if len(lines) == 1:
        raise NoMarketDataError(ticker, ticker, detail="no crypto rows")
    header = (
        f"# Crypto data for {ticker} ({convert_currency}) via Tiingo "
        f"{start_date}..{end_date}\n\n"
    )
    return header + "\n".join(lines)


def _crypto_code(symbol: str) -> str:
    """Yahoo-style crypto symbol (``BTC-USD``) -> Tiingo code (``btcusd``).

    Handles ``BTC-USD`` (base-USD), ``ethusd`` (already Tiingo form) and
    ``BTC/USD`` - strips an explicit quote currency and appends ``usd``.
    """
    s = symbol.upper().replace("/", "-")
    parts = s.split("-")
    base = parts[0]
    # ``ethusd`` (no dash) would otherwise become ``ethusdusd``.
    if base.endswith("USD") and len(base) > 3:
        base = base[:-3]
    return base.lower() + "usd"


__all__ = [
    "tiingo_api_key",
    "get_stock_data_tiingo",
    "get_income_statement_tiingo",
    "get_balance_sheet_tiingo",
    "get_cashflow_tiingo",
    "get_fundamentals_tiingo",
    "get_market_snapshot_tiingo",
    "get_crypto_prices_tiingo",
    "_crypto_code",
]
