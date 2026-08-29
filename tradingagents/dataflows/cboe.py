"""CBOE free delayed options-chain surface (no API key).

Fetches the full delayed options chain for a symbol from CBOE's public
endpoint (``https://cdn.cboe.com/api/global/delayed_quotes/options/{SYMBOL}.json``)
and renders a compact surface: strike, days-to-expiry, IV, and the greeks
exactly as CBOE delivers them. The delayed feed does not always populate the
greeks (values are absent or 0 for deep-ITM / illiquid contracts), so a
missing value renders as ``n/a`` — never an estimate (no fabrication).

The endpoint needs no key or paid plan. Failures degrade through the typed
error taxonomy: an empty chain or an unknown symbol raises
``NoMarketDataError`` (so the router emits one honest "no data" signal), and
throttling / server errors raise ``VendorRateLimitError``.
"""
from __future__ import annotations

import logging
from datetime import datetime

import requests

from .errors import NoMarketDataError, VendorRateLimitError

logger = logging.getLogger(__name__)

CBOE_OPTIONS_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json"
REQUEST_TIMEOUT = 30

# Cap the rendered surface so a full chain cannot flood the analyst context.
MAX_ROWS = 60

def _parse_occ(option: str) -> dict | None:
    """Split an OCC option symbol (root + YYMMDD + C/P + strike*1000).

    e.g. ``SPY260828C00500000`` -> {"expiry": "2026-08-28", "type": "C",
    "strike": 500.0}. The trailing 15 characters are always ``YYMMDD`` (6) +
    ``C|P`` (1) + the zero-padded strike*1000 (8), so the root is everything
    before them. Returns None for a malformed symbol — unparseable contracts
    are skipped, never guessed.
    """
    if not isinstance(option, str) or len(option) < 15:
        return None
    root = option[:-15]
    expiry = option[-15:-9]
    cp = option[-9]
    strike_str = option[-8:]
    if not root or not root.isalpha() or cp not in ("C", "P"):
        return None
    try:
        strike = int(strike_str) / 1000.0
        expiry_dt = datetime.strptime(expiry, "%y%m%d")
    except ValueError:
        return None
    return {"expiry": expiry_dt.strftime("%Y-%m-%d"), "type": cp, "strike": strike}


def _fmt_num(v) -> str:
    """Format a numeric field; None/non-numeric renders as ``n/a`` (honest)."""
    if v is None:
        return "n/a"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "n/a"
    return f"{f:.4f}"


def _fetch(symbol: str) -> tuple[dict, str]:
    """GET the CBOE delayed options payload; returns ``(data, as_of)``.

    :raises NoMarketDataError: unknown symbol (404) or a non-JSON body.
    :raises VendorRateLimitError: 429 / 5xx / network failure.
    """
    try:
        resp = requests.get(CBOE_OPTIONS_URL.format(symbol=symbol), timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise VendorRateLimitError(f"CBOE request failed: {exc}") from exc
    if resp.status_code == 404:
        raise NoMarketDataError(
            symbol, symbol, detail=f"CBOE returned no options chain for '{symbol}'"
        )
    if resp.status_code in (429,) or 500 <= resp.status_code < 600:
        raise VendorRateLimitError(f"CBOE HTTP {resp.status_code}")
    resp.raise_for_status()
    try:
        payload = resp.json()
    except ValueError as exc:
        raise NoMarketDataError(symbol, symbol, detail="CBOE returned a non-JSON body") from exc
    data = payload.get("data") or {}
    as_of = (payload.get("timestamp") or "").split(" ")[0]
    return data, as_of


def get_options_surface(symbol: str) -> str:
    """Render CBOE's delayed options chain as a compact surface (markdown).

    Returns rows of ``{strike, dte, iv, delta, gamma, theta, vega, rho}``
    (plus bid/ask/open-interest/volume) for the chain, sorted by
    days-to-expiry then strike. Days-to-expiry (DTE) is computed from CBOE's
    ``timestamp`` as-of date; greeks/IV appear exactly as CBOE delivers them,
    with absent values as ``n/a``.

    :raises NoMarketDataError: blank symbol, 404, empty chain, or no parseable rows.
    """
    symbol = str(symbol or "").strip().upper()
    if not symbol:
        raise NoMarketDataError(symbol, "<blank>", detail="blank ticker symbol")
    data, as_of = _fetch(symbol)
    options = data.get("options") or []
    if not options:
        raise NoMarketDataError(symbol, symbol, detail="CBOE returned no option rows")

    as_of_dt = None
    if as_of:
        try:
            as_of_dt = datetime.strptime(as_of, "%Y-%m-%d")
        except ValueError:
            as_of_dt = None

    rows = []
    for row in options:
        parsed = _parse_occ(row.get("option")) if row.get("option") else None
        if parsed is None:
            continue
        dte = None
        if as_of_dt is not None:
            try:
                dte = (datetime.strptime(parsed["expiry"], "%Y-%m-%d") - as_of_dt).days
            except ValueError:
                dte = None
        rows.append(
            {
                "strike": parsed["strike"],
                "dte": dte,
                "type": parsed["type"],
                "iv": _fmt_num(row.get("iv")),
                "delta": _fmt_num(row.get("delta")),
                "gamma": _fmt_num(row.get("gamma")),
                "theta": _fmt_num(row.get("theta")),
                "vega": _fmt_num(row.get("vega")),
                "rho": _fmt_num(row.get("rho")),
                "bid": _fmt_num(row.get("bid")),
                "ask": _fmt_num(row.get("ask")),
                "oi": row.get("open_interest") or 0,
                "volume": row.get("volume") or 0,
            }
        )
    if not rows:
        raise NoMarketDataError(symbol, symbol, detail="no parseable option rows")

    # Nearest expiry first, then strike, then calls-before-puts (stable order).
    rows.sort(
        key=lambda r: (r["dte"] if r["dte"] is not None else 10**9, r["strike"], r["type"])
    )
    total = len(rows)
    if len(rows) > MAX_ROWS:
        rows = rows[:MAX_ROWS]

    lines = [
        f"# CBOE Options Surface: {symbol} (as of {as_of or 'unknown date'})",
        "Source: CBOE free delayed quotes (no key). IV/greeks as delivered by CBOE; "
        "absent values are 'n/a' (never estimated).",
        "| Strike | DTE | Type | IV | Delta | Gamma | Theta | Vega | Rho | Bid | Ask | OI | Vol |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        dte = r["dte"] if r["dte"] is not None else "n/a"
        lines.append(
            f"| {r['strike']:.2f} | {dte} | {r['type']} | {r['iv']} | {r['delta']} | "
            f"{r['gamma']} | {r['theta']} | {r['vega']} | {r['rho']} | {r['bid']} | "
            f"{r['ask']} | {r['oi']} | {r['volume']} |"
        )
    if total > len(rows):
        lines.append(f"\n_(showing the nearest {len(rows)} of {total} contracts)_")
    return "\n".join(lines)
