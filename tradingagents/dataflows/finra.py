"""FINRA official data vendor (keyless) for short-sale volume + ATS dark-pool flow.

Sources (both official FINRA, free, no API key on the public tier):

- ``regShoDaily`` (api.finra.org, group otcMarket): Reg SHO daily short-sale
  volume per issue (short shares, total shares) per trade date.
- ``weeklySummary`` (api.finra.org, group otcMarket): per-ATS (MPID) weekly
  off-exchange/ATS share volume, trade count and notional per issue.

IMPORTANT — public-tier freshness: the keyless public tier of api.finra.org
serves the historical window (verified: weeklySummary's latest week is
2023-11; regShoDaily's single published date is 2026-01-06). Every row the
API returns carries its ``tradeReportDate`` / ``weekStartDate`` as-of, and
both tools render that date prominently and gate on staleness: when the
latest served date is older than the staleness threshold the report says so
explicitly instead of presenting old numbers as current. A registered FINRA
public API key (free, ``FINRA_API_KEY`` + OAuth) is the documented upgrade
path to current daily data; the tools stay keyless and honest meanwhile.

Any network failure degrades to an explicit 'unavailable' string; missing
rows are never invented.
"""

from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)

_BASE = "https://api.finra.org/data/group/otcMarket/name"
_TIMEOUT = 25
_UA = "tradingagents/0.3 (+https://github.com/TauricResearch/TradingAgents)"
_SSV_STALE_DAYS = 21
_DARKPOOL_STALE_DAYS = 90


def _get(dataset: str, params: dict | None = None):
    """GET a FINRA dataset row list; raises on failure."""
    import requests

    resp = requests.get(
        f"{_BASE}/{dataset}",
        params=params or {},
        timeout=_TIMEOUT,
        headers={"User-Agent": _UA, "Accept": "application/json"},
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError(f"unexpected FINRA payload for {dataset}: {type(data).__name__}")
    return data


def get_short_sale_volume(ticker: str, days: int = 5) -> str:
    """Daily Reg SHO short-sale volume for a ticker (FINRA, keyless).

    Aggregates short-sale shares, short-exempt shares and total shares across
    reporting facilities per trade date, newest first, and renders short-sale
    % of total. Renders the last *served* date with an explicit staleness
    banner when the FINRA public tier's newest date is > ``_SSV_STALE_DAYS``
    old — never presents old data as current.
    """
    ticker = str(ticker or "").strip().upper()
    if not ticker:
        return "short-sale volume unavailable: no ticker"
    try:
        rows = _get(
            "regShoDaily",
            {"filter": f"securitiesInformationProcessorSymbolIdentifier(EQ){ticker}",
             "limit": str(max(days * 8, 24))},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("FINRA regShoDaily failed for %s: %s", ticker, exc)
        return f"short-sale volume unavailable for {ticker}: {exc}"
    if not rows:
        return f"short-sale volume unavailable for {ticker}: no FINRA records"
    by_day: dict[str, dict] = {}
    for r in rows:
        day = str(r.get("tradeReportDate") or "")
        if not day:
            continue
        agg = by_day.setdefault(day, {"short": 0, "exempt": 0, "total": 0})
        agg["short"] += int(r.get("shortParQuantity") or 0)
        agg["exempt"] += int(r.get("shortExemptParQuantity") or 0)
        agg["total"] += int(r.get("totalParQuantity") or 0)
    newest = max(by_day)
    lines = [f"## Reg SHO daily short-sale volume — {ticker} (FINRA, keyless)", ""]
    for day in sorted(by_day, reverse=True)[:days]:
        a = by_day[day]
        pct = (a["short"] / a["total"] * 100) if a["total"] else 0.0
        lines.append(f"- {day}: short {a['short']:,} / total {a['total']:,} "
                     f"({pct:.1f}% short; +{a['exempt']:,} exempt)")
    try:
        lag_days = (datetime.date.today() - datetime.date.fromisoformat(newest)).days
    except ValueError:
        lag_days = 0
    if lag_days > _SSV_STALE_DAYS:
        lines.append("")
        lines.append(f"NOTE: FINRA public tier's newest published date is {newest} "
                     f"({lag_days}d ago) — not a live feed; treat as reference only. "
                     "get_short_interest remains the current short-interest source, "
                     "and a free FINRA API key upgrades this to the current daily file.")
    lines.append("")
    lines.append("Source: FINRA Reg SHO Daily (api.finra.org, keyless, as-of the dates above).")
    return "\n".join(lines)


def get_dark_pool_flow(ticker: str, weeks: int = 3) -> str:
    """Weekly ATS / off-exchange flow for a ticker from FINRA OTC Transparency.

    Aggregates per-week ATS share volume, trade count and notional across all
    reporting market participants (MPIDs) for the issue. Renders the latest
    *served* week with an explicit as-of; gates on ``_DARKPOOL_STALE_DAYS``
    (the keyless tier's weeklySummary last week is 2023-11 — the report says
    so rather than presenting it as current dark-pool flow).
    """
    ticker = str(ticker or "").strip().upper()
    if not ticker:
        return "dark-pool flow unavailable: no ticker"
    try:
        rows = _get(
            "weeklySummary",
            {"filter": f"issueSymbolIdentifier(EQ){ticker}",
             "sort": "weekStartDate(desc)", "limit": str(max(weeks * 30, 60))},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("FINRA weeklySummary failed for %s: %s", ticker, exc)
        return f"dark-pool flow unavailable for {ticker}: {exc}"
    rows = [r for r in rows if r.get("issueSymbolIdentifier") == ticker]
    if not rows:
        return f"dark-pool flow unavailable for {ticker}: no FINRA ATS records"
    by_week: dict[str, dict] = {}
    for r in rows:
        wk = str(r.get("weekStartDate") or r.get("summaryStartDate") or "")
        if not wk:
            continue
        agg = by_week.setdefault(wk, {"shares": 0, "trades": 0, "notional": 0.0})
        agg["shares"] += int(r.get("totalWeeklyShareQuantity") or 0)
        agg["trades"] += int(r.get("totalWeeklyTradeCount") or 0)
        agg["notional"] += float(r.get("totalNotionalSum") or 0.0)
    newest = max(by_week)
    lines = [f"## FINRA ATS weekly off-exchange flow — {ticker}", ""]
    for wk in sorted(by_week, reverse=True)[:weeks]:
        a = by_week[wk]
        lines.append(f"- week {wk}: {a['shares']:,} shares / {a['trades']:,} trades "
                     f"/ ${a['notional']:,.0f} notional across ATS participants")
    try:
        lag_days = (datetime.date.today() - datetime.date.fromisoformat(newest)).days
    except ValueError:
        lag_days = 0
    if lag_days > _DARKPOOL_STALE_DAYS:
        lines.append("")
        lines.append(f"NOTE: FINRA public tier's newest ATS week is {newest} "
                     f"({lag_days}d ago) — no live free per-ticker dark-pool source; "
                     "treat the above as reference only (a FINRA API key upgrades "
                     "to the current window).")
    lines.append("")
    lines.append("Source: FINRA OTC Transparency weeklySummary (keyless, as-of the weeks above).")
    return "\n".join(lines)


__all__ = ["get_short_sale_volume", "get_dark_pool_flow"]
