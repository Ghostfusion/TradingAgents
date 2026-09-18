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
# P0-5: the index-level history CSVs on the same CDN. VIX9D is NOT on FRED (FRED
# carries VXVCLS for the 3-month, and its discontinued 3-month series is VXOCLS,
# not VXVCLS), so the 9-day leg needs this file.
CBOE_VIX_HISTORY_URL = (
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv"
)
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


# ---------------------------------------------------------------------------
# P0-5: the VIX term structure (index levels, NOT one name's equity-IV slope)
# ---------------------------------------------------------------------------

_VIX_SERIES = {"vix9d": "VIX9D", "vix3m": "VIX3M"}
_VIX_CACHE_TTL = 24 * 3600  # end-of-day files: one fetch per day
_VIX_CACHE_FILE = "cboe_vix_term_structure.json"


def _vix_cache_path() -> str | None:
    """``data_cache_dir/cboe_vix_term_structure.json``, or None when unset."""
    import os

    try:
        from tradingagents.dataflows.config import get_config

        base_dir = (get_config() or {}).get("data_cache_dir") or os.getenv("TRADINGAGENTS_CACHE_DIR")
    except Exception:  # noqa: BLE001 - advisory
        base_dir = os.getenv("TRADINGAGENTS_CACHE_DIR")
    if not base_dir:
        return None
    try:
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, _VIX_CACHE_FILE)
    except OSError:
        return None


def _vix_cache_read() -> dict | None:
    import json
    import os
    import time

    path = _vix_cache_path()
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            blob = json.load(f)
        if blob.get("ts") and time.time() - blob["ts"] < _VIX_CACHE_TTL:
            return blob
    except (OSError, ValueError):
        pass
    return None


def _vix_cache_write(payload: dict) -> None:
    import json
    import time

    path = _vix_cache_path()
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({**payload, "ts": time.time()}, f)
    except OSError:
        pass


def _vix_last_level(name: str) -> tuple[str | None, float | None]:
    """``(date, close)`` of the last row of one Cboe index-history CSV.

    The CDN files are ``DATE,OPEN,HIGH,LOW,CLOSE``; Cboe writes DATE as
    ``MM/DD/YYYY`` (verified live 2026-09-17: the last row read ``09/17/2026``), so
    ``as_of`` is passed through in the vendor's own format rather than silently
    re-formatted. The last row with a non-empty CLOSE is the latest level. Any failure returns
    ``(None, None)`` so the caller prints the reason rather than a stale number -
    this producer is strategy-facing and deliberately does NOT raise the vendor
    taxonomy the routed methods above use.
    """
    import csv
    import io

    try:
        resp = requests.get(
            CBOE_VIX_HISTORY_URL.format(name=name), timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        text = resp.text
    except requests.RequestException as exc:
        logger.warning("Cboe %s history fetch failed: %s", name, exc)
        return None, None
    try:
        rows = list(csv.DictReader(io.StringIO(text)))
    except (csv.Error, ValueError):
        return None, None
    for row in reversed(rows):
        close = (row.get("CLOSE") or row.get("Close") or "").strip()
        if not close:
            continue
        try:
            return ((row.get("DATE") or row.get("Date") or "").strip() or None), float(close)
        except ValueError:
            continue
    return None, None


def vix_term_structure(*, refresh: bool = False) -> dict:
    """VIX9D / VIX3M levels, slope and state, or ``None`` keys with the reason.

    ``RegimeScore.md`` §1 and §4 are explicit that the equity-IV slope
    (``options_surface.term_structure_slope``, from one name's option chain) is
    **not** a VIX term structure and must never be substituted silently. This is
    the real thing: the two Cboe index levels, their slope and the
    contango/backwardation state.

    Returns::

        {"vix9d": float | None, "vix3m": float | None,
         "slope": float | None,   # vix3m - vix9d, the shared long-minus-short sign
         "state": "contango" | "backwardation" | None,
         "as_of": str | None, "basis": str, "reason": str | None}

    The slope uses the **same sign convention** as
    ``options_surface.term_structure_slope`` so a reader comparing them compares
    like with like - they remain different objects, and ``basis`` says which one
    this is. ``state`` is ``contango`` when the 3-month level is at or above the
    9-day (the normal upward slope; a flat curve is not stress) and
    ``backwardation`` when it is below (near-term stress priced above the
    3-month). An unmeasurable pair is ``None``, never a defaulted state, and the
    equity-IV slope is never returned under a VIX name.
    """
    if not refresh:
        cached = _vix_cache_read()
        if cached and cached.get("vix9d") is not None:
            return cached
    levels: dict = {}
    dates: list[str] = []
    for key, name in _VIX_SERIES.items():
        date, close = _vix_last_level(name)
        levels[key] = close
        if date:
            dates.append(date)
    vix9d, vix3m = levels.get("vix9d"), levels.get("vix3m")
    slope = None if (vix9d is None or vix3m is None) else float(vix3m) - float(vix9d)
    state = None if slope is None else ("contango" if slope >= 0 else "backwardation")
    reason = None
    if state is None:
        missing = sorted(k for k, v in levels.items() if v is None)
        reason = (
            "Cboe index-history CSV unreachable or empty for "
            + ", ".join(missing)
            + f" ({CBOE_VIX_HISTORY_URL.format(name='VIX9D')} / "
            f"{CBOE_VIX_HISTORY_URL.format(name='VIX3M')})"
        )
    out = {
        "vix9d": vix9d,
        "vix3m": vix3m,
        "slope": slope,
        "state": state,
        "as_of": max(dates) if dates else None,
        "basis": (
            "Cboe VIX9D/VIX3M index levels (not one name's equity-IV slope)"
            if state is not None
            else "Cboe VIX9D/VIX3M unavailable"
        ),
        "reason": reason,
    }
    if state is not None:
        _vix_cache_write(out)
    return out
