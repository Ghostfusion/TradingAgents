"""Massive.com WebSocket Net Order Imbalance (NOI) client.

NOI streams real-time buy/sell order-imbalance events during NYSE auctions
(open 9:30 ET, close 16:00 ET, halts/mini-auctions intraday). It is a **live
monitoring feed**, not a per-ticker batch data source, so it is deliberately
*not* exposed as a LangChain ``@tool`` on the analyst graph nodes.

This module provides a ``WebSocket``-based streamer you can wire into a
standalone monitor script (e.g. ``scripts/massive_noi_monitor.py``). The pure
helpers (``build_url``, ``parse_frame``) are fully offline-testable; the live
loop uses ``websocket-client`` lazily (an optional dependency) and degrades to
a clear message when the package or the plan entitlement is missing.

Entitlement: the NOI feed requires Massive's **Imbalances Expansion** add-on -
*not* on the free Basic plan. It activates automatically (no code change) when
the account gains that entitlement.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# WS connect host. The exact wss endpoint may differ by entitlement/region;
# override via config ``massive_noi_ws_url`` or env ``MASSIVE_NOI_WS_URL``.
_DEFAULT_WS = "wss://api.massive.com/v2/stocks/NOI"


def build_url(tickers, api_key: str, ws_url: str | None = None) -> str:
    """Build the NOI WebSocket connect URL.

    ``tickers`` is a list (or ``["*"]`` for all). ``api_key`` is embedded as a
    query ``token`` (Massive's WS handshake convention).
    """
    base = (ws_url or os.environ.get("MASSIVE_NOI_WS_URL") or _DEFAULT_WS).rstrip("/")
    syms = ",".join(tickers) if tickers and tickers != ["*"] else "*"
    return f"{base}?ticker={syms}&token={api_key}"


def parse_frame(message: str) -> dict:
    """Parse one WS frame into an NOI event dict (or empty dict on non-NOI)."""
    try:
        ev = json.loads(message)
    except Exception:  # noqa: BLE001 - malformed frame
        return {}
    if ev.get("ev") != "NOI":
        return {}
    # Normalize to friendly keys.
    return {
        "type": "NOI",
        "ticker": ev.get("T"),
        "timestamp_ns": ev.get("t"),
        "planned_at": ev.get("at"),  # (hour*100)+min EST, e.g. 930 / 1600
        "auction": ev.get("a"),      # O/M/H/C/P/R
        "exchange": ev.get("x"),
        "imbalance": ev.get("o"),
        "paired": ev.get("p"),
        "clearing_price": ev.get("b"),
    }


def describe(ev: dict) -> str:
    """One-line render of an NOI event for a monitor's console/log."""
    ticker = ev.get("ticker") or "?"
    auction = {
        "O": "early-open", "M": "open", "H": "halt-reopen",
        "C": "close", "P": "close-extreme", "R": "close-regulatory",
    }.get(ev.get("auction"), ev.get("auction") or "?")
    at = ev.get("planned_at")
    imm = ev.get("imbalance")
    priced = ev.get("clearing_price")
    return (
        f"[NOI] {ticker} {auction}@{at if at is not None else '?'} "
        f"imbalance={imm if imm is not None else '?'} priced={priced if priced is not None else '?'}"
    )


def _client():
    """Import websocket-client lazily; raise a clear error when absent."""
    try:
        import websocket  # noqa: F401 - type: ignore

        return websocket
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "the 'websocket-client' package is required for the Massive NOI "
            "monitor. Install it with: py -3.12 -m pip install websocket-client"
        ) from exc


def stream_noi(
    tickers,
    on_event,
    api_key: str | None = None,
    ws_url: str | None = None,
    stop_after: int | None = None,
    max_per_ticker: int | None = None,
) -> int:
    """Stream NOI events for ``tickers``; call ``on_event(ev)`` per frame.

    Returns the number of full NOI events delivered. Intended for a monitor
    script; raises when websocket-client is missing. Entitlement failures
    surface via the connect step.

    Args:
        tickers: list of symbols, or ``["*"]`` for all.
        on_event: callable(ev) for each parsed NOI event.
        api_key: Massive key; defaults to the env/config key.
        ws_url: override the WS endpoint.
        stop_after: stop after this many events (default: run until closed).
        max_per_ticker: stop after this many events for a single ticker.
    """
    ws = _client()
    from .massive import massive_api_key

    key = api_key or massive_api_key()
    if not key:
        raise RuntimeError("MASSIVE_API_KEY is not set; the NOI feed needs it.")
    url = build_url(list(tickers) if tickers else ["*"], key, ws_url)

    delivered = 0
    per_ticker: dict = {}

    def _on_message(_ws, message: str):
        nonlocal delivered
        ev = parse_frame(message)
        if not ev:
            return
        on_event(ev)
        delivered += 1
        t = ev.get("ticker") or "?"
        per_ticker[t] = per_ticker.get(t, 0) + 1
        if max_per_ticker and per_ticker[t] >= max_per_ticker:
            _ws.close()

    app = ws.create_connection(url, timeout=15)
    try:
        # Read frames until the connection closes or a cap is reached.
        while True:
            try:
                message = app.recv()
            except Exception:  # noqa: BLE001 - connection closed / timeout
                break
            if message is None:
                break
            _on_message(app, message)
            if stop_after is not None and delivered >= stop_after:
                break
            if max_per_ticker and any(c >= max_per_ticker for c in per_ticker.values()):
                break
    finally:
        from contextlib import suppress

        with suppress(Exception):
            app.close()
    return delivered


__all__ = [
    "build_url",
    "parse_frame",
    "describe",
    "stream_noi",
]
