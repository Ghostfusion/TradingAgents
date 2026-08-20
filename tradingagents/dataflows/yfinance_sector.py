"""Guarded yfinance enrichments for the screener (analysis-only).

Provides the two Phase-1/2 inputs the moomoo vendor chain does not cover:

* ``fetch_sector``           - the ticker's GICS sector (yfinance ``info``)
* ``fetch_revision_actions`` - analyst grade actions in the last N days
  (yfinance ``upgrades_downgrades``) as a cheap proxy for "positive forward
  earnings revisions" - net upgrades over downgrades in the window

Every call is daemon-thread guarded (a slow vendor can never hang the
scanner; worst case: None). The screener treats None as "no data" and then
reports n/a rather than fabricating a number.
"""

from __future__ import annotations

import threading


def _ticker_info(ticker: str, timeout: float = 8.0) -> dict:
    """yfinance ``Ticker(ticker).info`` on a daemon thread; {} on timeout."""
    result: dict = {}

    def _work() -> None:
        try:
            import yfinance as yf

            result.update(yf.Ticker(ticker).info or {})
        except Exception:  # noqa: BLE001 - enrichment must never raise
            pass

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join(timeout)
    return result


def fetch_sector(ticker: str, timeout: float = 8.0) -> str | None:
    """GICS sector for the ticker; None when unavailable.

    1) FMP company profile (key-gated, instant when the key is set and not
       rate-limited) - the authoritative source when available.
    2) yfinance ``info`` on a daemon thread as a guarded fallback (slow /
       blocked vendor or unset key can never hang the scanner; worst case:
       None = unknown sector, which the sector gate treats as no-data).
    """
    # 1) FMP company profile (key-gated, fast).
    try:
        from tradingagents.dataflows.fmp import get_company_profile

        prof = get_company_profile(ticker)
        if prof:
            sec = str(prof.get("sector") or "").strip()
            if sec and sec.lower() != "none":
                return sec
    except Exception:  # noqa: BLE001 - enrichment must never raise
        pass
    # 2) yfinance guarded fallback.
    info = _ticker_info(ticker, timeout=timeout)
    sec = (info.get("sector") or "").strip()
    return sec or None


def fetch_revision_actions(ticker: str, days: int = 60, timeout: float = 12.0) -> dict | None:
    """Analyst upgrade/downgrade actions in the last ``days`` as a revisions
    proxy: {"up", "down", "net"} counts; None when the source is unavailable."""
    result: dict = {}

    def _work() -> None:
        try:
            from datetime import datetime, timedelta

            import yfinance as yf

            df = yf.Ticker(ticker).upgrades_downgrades
            if df is None or df.empty:
                return
            cutoff = datetime.now() - timedelta(days=int(days))
            up = down = 0
            for _, row in df.iterrows():
                try:
                    when = row.get("ActionDate") or row.get("date")
                    action = str(row.get("Action") or row.get("Grade") or "").lower()
                except Exception:  # noqa: BLE001
                    continue
                if when is None:
                    continue
                if isinstance(when, str):
                    try:
                        when = datetime.strptime(str(when)[:10], "%Y-%m-%d")
                    except ValueError:
                        continue
                if when < cutoff:
                    continue
                if "up" in action:
                    up += 1
                elif "down" in action:
                    down += 1
            result["up"], result["down"] = up, down
            result["net"] = up - down
        except Exception:  # noqa: BLE001
            pass

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join(timeout)
    return result if "net" in result else None


__all__ = ["fetch_sector", "fetch_revision_actions"]
