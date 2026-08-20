"""Alpaca data-only REST client (analysis project; no trading endpoints).

Rate-limit aware for the free tier: IEX feed, 200 requests/min. Calls are
globally paced (~171/min ceiling) and 429s back off using Retry-After /
X-RateLimit-Reset headers where present. Batch endpoints are used upstream
(comma-separated symbols) to minimise call count.
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Free tier = IEX feed, 200 req/min per key; keep headroom under it.
_MIN_CALL_INTERVAL = 0.35  # seconds -> ~171 req/min ceiling
_pace_lock = threading.Lock()
_last_call = 0.0

DATA_BASE = "https://data.alpaca.markets/v2"
#: calendar/clock live on the (paper) trading host, not the data host
TRADING_BASE = "https://paper-api.alpaca.markets/v2"
_TIMEOUT = 20
_MAX_RETRIES = 2


def alpaca_credentials() -> tuple[str | None, str | None]:
    """(API key id, secret) from config/.env; (None, None) if unset."""
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config()
        key_id = cfg.get("alpaca_api_key_id")
        secret = cfg.get("alpaca_api_secret")
    except Exception:
        key_id = secret = None
    return (str(key_id) if key_id else None, str(secret) if secret else None)


def _pace() -> None:
    """Thread-safe minimum inter-call interval, so bursts never trip 429."""
    global _last_call
    with _pace_lock:
        now = time.monotonic()
        wait = _MIN_CALL_INTERVAL - (now - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def _sleep_from_headers(resp, fallback: float) -> None:
    """Sleep on rate-limit responses: Retry-After / X-RateLimit-Reset, else fallback."""
    wait = None
    ra = resp.headers.get("Retry-After")
    if ra and ra.isdigit():
        wait = float(ra)
    else:
        reset = resp.headers.get("X-RateLimit-Reset")
        if reset and reset.isdigit():
            wait = max(0.0, float(reset) - time.time())
    if wait is None:
        wait = fallback
    time.sleep(min(max(wait, 0.0), 30.0))


def alpaca_get(path: str, params: dict | None = None, base: str = DATA_BASE) -> dict | list | None:
    """GET ``base/{path}`` signed, paced; parsed JSON or None on any failure."""
    import requests

    key_id, secret = alpaca_credentials()
    if not key_id or not secret:
        return None
    url = f"{base}/{path}"
    headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret}
    query = dict(params or {})
    for attempt in range(_MAX_RETRIES + 1):
        _pace()
        try:
            resp = requests.get(url, params=query, headers=headers, timeout=_TIMEOUT)
            if resp.status_code in (401, 403):
                logger.warning("Alpaca auth failed (check ALPACA keys): %s", resp.status_code)
                return None
            if resp.status_code in (429,) or resp.status_code >= 500:
                if attempt < _MAX_RETRIES:
                    _sleep_from_headers(resp, 2 * (attempt + 1))
                    continue
                logger.warning("alpaca %s: status %s", path, resp.status_code)
                return None
            if resp.status_code != 200:
                logger.warning("alpaca %s: status %s", path, resp.status_code)
                return None
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("alpaca %s failed: %s", path, exc)
            return None
    return None


__all__ = ["DATA_BASE", "TRADING_BASE", "alpaca_credentials", "alpaca_get"]
