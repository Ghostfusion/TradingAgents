"""Public-float lookups for the momentum low-float pillar (analysis-only).

The playbook requires float < 20M shares (ideally < 3-5M). This module is the
single source for that number so tools and the screener share one code path:

1. FMP company profile (optional key; returns None instantly when unset)
2. yfinance ``info`` as a guarded fallback - the call runs on a daemon thread
   so a slow/blocked vendor can never hang the scanner (worst case: None).

Degrades to None everywhere - unknown float simply leaves the pillar unknown
(``pillars()`` reports None instead of failing the scan).
"""

from __future__ import annotations

import threading


def fetch_float_shares(ticker: str, timeout: float = 8.0) -> float | None:
    """Best-effort public float in shares; None when every source fails."""
    # 1) FMP company profile (key-gated, fast).
    try:
        from tradingagents.dataflows.fmp import get_company_profile

        prof = get_company_profile(ticker)
        if prof:
            f = prof.get("floatShares")
            if f:
                return float(f)
    except Exception:  # noqa: BLE001 - enrichment must never raise
        pass
    # 2) yfinance info, guarded by a daemon thread + join timeout.
    result: dict = {}

    def _work() -> None:
        try:
            import yfinance as yf

            info = yf.Ticker(ticker).info or {}
            f = info.get("floatShares")
            if f:
                result["v"] = float(f)
        except Exception:  # noqa: BLE001
            pass

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join(timeout)
    return result.get("v")


__all__ = ["fetch_float_shares"]
