"""Alpaca data-only REST client (analysis project; no trading endpoints).

This module *deliberately* implements only market-data/calendar endpoints so the
analysis pipeline never touches orders/positions/paper accounts.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

DATA_BASE = "https://data.alpaca.markets/v2"
#: calendar/clock live on the (paper) trading host, not the data host
TRADING_BASE = "https://paper-api.alpaca.markets/v2"
_TIMEOUT = 20
_MAX_RETRIES = 2


def alpaca_credentials() -> "tuple[str | None, str | None]":
    """(API key id, secret) from config/.env; (None, None) if unset."""
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config()
        key_id = cfg.get("alpaca_api_key_id")
        secret = cfg.get("alpaca_api_secret")
    except Exception:
        key_id = secret = None
    return (str(key_id) if key_id else None, str(secret) if secret else None)


def alpaca_get(path: str, params: "dict | None" = None,
              base: "str" = DATA_BASE) -> "dict | list | None":
    """GET ``base/{path}`` signed; parsed JSON or None on any failure."""
    import requests

    key_id, secret = alpaca_credentials()
    if not key_id or not secret:
        return None
    url = f"{base}/{path}"
    headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret}
    query = dict(params or {})
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=query, headers=headers, timeout=_TIMEOUT)
            if resp.status_code in (401, 403):
                logger.warning("Alpaca auth failed (check ALPACA keys): %s", resp.status_code)
                return None
            if resp.status_code in (429,) or resp.status_code >= 500:
                if attempt < _MAX_RETRIES:
                    time.sleep(2 * (attempt + 1))
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