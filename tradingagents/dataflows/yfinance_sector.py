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

import math
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


def _etf_universe_sector(ticker: str) -> str | None:
    """Sector for a known ETF from the repo's issuer mapping (no vendor call).

    Vendor metadata misclassifies ETFs (IGV/SOXX/XLK all come back as
    "Financial Services" from yfinance/FMP — the review-flagged bug on the
    2026-09-09 IGV report). The ETF universe lists are authoritative for
    their members: an SPDR sector maps to its own label, an industry ETF
    maps to its parent sector's label.
    """
    try:
        from tradingagents.strategies.sector_rank import (
            INDUSTRY_ETFS,
            SPDR_SECTORS,
        )
    except Exception:  # noqa: BLE001 - enrichment must never raise
        return None
    t = (ticker or "").strip().upper()
    if t in SPDR_SECTORS:
        return SPDR_SECTORS[t]
    if t in INDUSTRY_ETFS:
        parent = INDUSTRY_ETFS[t][0]
        return SPDR_SECTORS.get(parent)
    return None


def fetch_sector(ticker: str, timeout: float = 8.0) -> str | None:
    """GICS sector for the ticker; None when unavailable.

    0) ETF identity first: a known ETF's sector comes from the repo's
       universe mapping (never the provider's equity-sector field, which
       misattributes ETFs — e.g. IGV/SOXX/XLK returned "Financial Services").
    1) FMP company profile (key-gated, instant when the key is set and not
       rate-limited) - the authoritative source when available.
    2) yfinance ``info`` on a daemon thread as a guarded fallback (slow /
       blocked vendor or unset key can never hang the scanner; worst case:
       None = unknown sector, which the sector gate treats as no-data).
    """
    etf_sector = _etf_universe_sector(ticker)
    if etf_sector:
        return etf_sector
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
    # 2) Finnhub company_profile2 (key-gated) - a second authoritative source
    #    when the FMP key is rate-limited/unset.
    try:
        from tradingagents.dataflows.finnhub import get_profile_finnhub

        prof = get_profile_finnhub(ticker)
        sec = str((prof or {}).get("sector") or "").strip()
        if sec:
            return sec
    except Exception:  # noqa: BLE001
        pass
    # 3) yfinance guarded fallback.
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


#: The vendor's estimate-trend level columns, most-recent-first. The window is a
#: 90-day LAG over one quarter's consensus - NOT four quarters.
_ESTIMATE_LEVEL_COLUMNS = ("current", "7daysAgo", "30daysAgo", "60daysAgo", "90daysAgo")

#: The period row the levels are read from: the current quarter.
_ESTIMATE_PERIOD = "0q"

#: What the estimate-trend levels ARE, for `analyst_revisions.estimate_change_index`.
#: Passed as `level_basis` so the printed basis cannot claim MSCI's quarterly
#: series when the numbers came from a 90-day lag window.
ESTIMATE_LEVEL_BASIS = "vendor 90-day estimate-trend"


def fetch_estimate_trend(
    ticker: str, period: str = _ESTIMATE_PERIOD, timeout: float = 8.0
) -> list | None:
    """Most-recent-first EPS estimate LEVELS, or None when unavailable.

    ``yfinance.Ticker.eps_trend`` returns a frame whose columns are the level
    observations (``current``, ``7daysAgo``, ``30daysAgo``, ``60daysAgo``,
    ``90daysAgo``) and whose rows are periods (``0q``, ``+1q``, ``0y``, ``+1y``).
    This returns the requested period's row as a five-element most-recent-first
    list - the shape ``strategies/analyst_revisions.estimate_change_index``
    requires (``len(weights) + 1`` levels; ``DEFAULT_ESTIMATE_WEIGHTS`` is
    ``(9, 7, 5, 3)``, so five).

    **The window is 90 days, not four quarters.** These are four lagged reads of
    ONE quarter's consensus, so a caller feeding them MUST pass
    ``level_basis=ESTIMATE_LEVEL_BASIS`` - otherwise the leg's basis line would
    claim MSCI's quarterly series. The arithmetic is identical either way; the
    label is what keeps it honest.

    Levels are returned AS GIVEN. A missing or non-finite observation returns
    ``None`` rather than a shorter series: a short series silently changes what
    the index means, and ``estimate_change_index`` already refuses one with a
    printed reason.
    """
    result: dict = {}

    def _work() -> None:
        try:
            import yfinance as yf

            df = yf.Ticker(ticker).eps_trend
            if df is None or df.empty:
                return
            if period not in list(getattr(df, "index", [])):
                return
            if any(c not in df.columns for c in _ESTIMATE_LEVEL_COLUMNS):
                return
            row = df.loc[period]
            levels: list[float] = []
            for col in _ESTIMATE_LEVEL_COLUMNS:
                try:
                    v = float(row.get(col))
                except (TypeError, ValueError):
                    return
                if not math.isfinite(v):
                    return
                levels.append(v)
            result["levels"] = levels
        except Exception:  # noqa: BLE001 - enrichment must never raise
            pass

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join(timeout)
    return result.get("levels")


def fetch_eps_revisions(
    ticker: str, period: str = _ESTIMATE_PERIOD, timeout: float = 8.0
) -> dict | None:
    """The vendor's own analyst up/down revision COUNTS, or None.

    ``yfinance.Ticker.eps_revisions`` carries ``upLast7days`` / ``upLast30days``
    / ``downLast7Days`` / ``downLast30days`` per period row. Returns
    ``{"up", "down", "net", "up_7d", "down_7d", "period"}`` or ``None``.

    This is NOT the same object as :func:`fetch_revision_actions`, which grades
    ``upgrades_downgrades`` *actions* by string-matching the grade. The two have
    different denominators - a graded-action history versus the vendor's own
    tally - so both are kept and the caller names which one it used.
    """
    result: dict = {}

    def _work() -> None:
        try:
            import yfinance as yf

            df = yf.Ticker(ticker).eps_revisions
            if df is None or df.empty:
                return
            if period not in list(getattr(df, "index", [])):
                return
            row = df.loc[period]

            def _i(col: str) -> int | None:
                try:
                    v = float(row.get(col))
                except (TypeError, ValueError):
                    return None
                return int(v) if math.isfinite(v) else None

            up, down = _i("upLast30days"), _i("downLast30days")
            if up is None or down is None:
                return
            result.update(
                up=up,
                down=down,
                net=up - down,
                up_7d=_i("upLast7days"),
                down_7d=_i("downLast7Days"),
                period=period,
            )
        except Exception:  # noqa: BLE001 - enrichment must never raise
            pass

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join(timeout)
    return result if "net" in result else None


__all__ = [
    "fetch_sector",
    "fetch_revision_actions",
    "fetch_estimate_trend",
    "fetch_eps_revisions",
    "ESTIMATE_LEVEL_BASIS",
]
