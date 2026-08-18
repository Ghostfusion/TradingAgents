"""FMP HTTP client: shared key/retries for tradingagents/dataflows/fmp.py.

Degrades like the other vendors: any failure returns None so the router and
screener treat FMP as an optional enrichment source.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

BASE = "https://financialmodelingprep.com/stable"
TIMEOUT = 20
_MAX_RETRIES = 2


def f_key() -> "str | None":
    """API key from config or environment; None when unset."""
    try:
        from tradingagents.dataflows.config import get_config

        key = get_config().get("fmp_api_key")
    except Exception:
        key = None
    if key:
        return str(key)
    import os

    return os.environ.get("FMP_API_KEY") or os.environ.get("TRADINGAGENTS_FMP_API_KEY")


def fmp_get(path: str, params: "dict | None" = None) -> "dict | list | None":
    """GET ``BASE/{path}`` with apikey; parsed JSON or None on any failure."""
    import requests

    key = f_key()
    if not key:
        return None
    url = f"{BASE}/{path}"
    query = dict(params or {})
    query["apikey"] = key
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=query, timeout=TIMEOUT)
            if resp.status_code in (401, 403):
                logger.warning("FMP auth/forbidden (check FMP_API_KEY): %s", resp.status_code)
                return None
            if resp.status_code in (429,) or resp.status_code >= 500:
                if attempt < _MAX_RETRIES:
                    time.sleep(2 * (attempt + 1))
                    continue
                logger.warning("fmp %s: status %s", path, resp.status_code)
                return None
            if resp.status_code != 200:
                logger.warning("fmp %s: status %s", path, resp.status_code)
                return None
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("fmp %s failed: %s", path, exc)
            return None
    return None


__all__ = ["BASE", "TIMEOUT", "f_key", "fmp_get"]