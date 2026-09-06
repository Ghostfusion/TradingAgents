"""Congressional stock-trade data (free, keyless) for the fundamentals analyst.

Sources (both public mirrors of the official House / Senate periodic
transaction reports; refreshed as the chambers disclose):

- House: ``TattooedHead/house-stock-watcher-data`` (GitHub mirror of the
  House Stock Watcher dataset; every discloseable House trade).
- Senate: ``timothycarambat/senate-stock-watcher-data`` (mirror of
  senator-stock-watcher).

Both files are bulk JSON (11 MB + 3 MB), so the parsed rows are cached
in-process for a few hours — a session that screens many tickers should not
re-download the full files per ticker. Any network/key failure degrades to
``None`` (the analysis tool renders 'unavailable'), mirroring the other
optional vendors.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

_HOUSE_URL = (
    "https://raw.githubusercontent.com/TattooedHead/house-stock-watcher-data/"
    "main/data/all_transactions.json"
)
_SENATE_URL = (
    "https://raw.githubusercontent.com/timothycarambat/"
    "senate-stock-watcher-data/master/aggregate/all_transactions.json"
)
_TIMEOUT = 30
_CACHE_TTL = 6 * 3600  # seconds; the disclosures refresh only when chambers file

_cache: dict[str, tuple[float, list]] = {}


def _get_json(url: str) -> list:
    """GET a JSON array with a short timeout; raises on failure."""
    import requests

    resp = requests.get(
        url,
        timeout=_TIMEOUT,
        headers={"User-Agent": "tradingagents/0.3 (+https://github.com/TauricResearch/TradingAgents)"},
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError(f"unexpected payload for {url}: {type(data).__name__}")
    return data


def _cached_rows(key: str, url: str) -> list:
    """Rows for a source, cached in-process for the TTL (or until failure)."""
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    rows = _get_json(url)
    _cache[key] = (now, rows)
    return rows


def _classify(tx_type: str) -> str:
    """'Purchase'/'Sale (Full)'/'Exchange' -> P/S/X (case/whitespace-robust)."""
    t = (tx_type or "").strip().lower()
    if t.startswith("purchase"):
        return "P"
    if t.startswith("sale"):
        return "S"
    if t.startswith("exchange") or t.startswith("transfer"):
        return "X"
    return "?"


def _row(r: dict) -> dict | None:
    """Normalize one watcher row; None when it has no usable ticker/date."""
    ticker = str(r.get("ticker") or "").strip().upper()
    if not ticker:
        return None
    t = _classify(str(r.get("type") or ""))
    dt = str(r.get("transaction_date") or r.get("disclosure_date") or "")
    amount = r.get("amount")
    mid = r.get("amount_mid")
    if mid is not None:
        try:
            mid = float(mid)
        except (TypeError, ValueError):
            mid = None
    return {
        "ticker": ticker,
        "type": t,
        "amount": amount,
        "mid": mid,
        "date": dt,
        "owner": str(r.get("owner") or ""),
        "name": str(r.get("senator") or r.get("representative") or ""),
    }


def _filter_rows(rows: list, ticker: str) -> list:
    """Normalized rows matching ``ticker`` (open-market P/S only, sorted desc)."""
    out = []
    for r in rows or []:
        n = _row(r)
        if n and n["ticker"] == ticker.upper() and n["type"] in ("P", "S"):
            if n["amount"] is None and n["mid"] is None:
                continue
            out.append(n)
    out.sort(key=lambda x: (x["date"] or ""), reverse=True)
    return out


def _net_summary(rows: list) -> dict:
    """Counts: buys, sells, net (buys - sells); mid-$ net when mids exist."""
    buys = sum(1 for r in rows if r["type"] == "P")
    sells = sum(1 for r in rows if r["type"] == "S")
    return {
        "buys": buys,
        "sells": sells,
        "net": buys - sells,
    }


def _render(rows: list, chamber: str, limit: int = 8) -> str:
    """Markdown block for one chamber's matched trades."""
    s = _net_summary(rows)
    head = f"**{chamber}**: {s['buys']} buys / {s['sells']} sells (net {s['net']:+d})"
    if not rows:
        return head + " — no open-market trades"
    lines = [head, ""]
    for r in rows[:limit]:
        amt = r["amount"] or (f"${r['mid']:,.0f}" if r["mid"] is not None else "n/a")
        owner = f" ({r['owner']})" if r["owner"] else ""
        lines.append(f"- {r['date']} {r['type']} {amt}{owner} — {r['name']}")
    if len(rows) > limit:
        lines.append(f"- … {len(rows) - limit} more")
    return "\n".join(lines)


def get_congress_trades(ticker: str, limit: int = 8) -> str:
    """Matched House + Senate trades for a ticker, as a formatted report.

    Returns a string ("**House**: n buys / m sells (net +/-k)" blocks + the
    sample rows), or an explicit 'congress trades unavailable for X: reason'
    on a failure. Each chamber renders independently so one source failing
    never wipes the other. Free, keyless sources (GitHub mirrors of the
    House/Senate Stock Watcher datasets).
    """
    ticker = str(ticker or "").strip().upper()
    if not ticker:
        return "congress trades unavailable: no ticker"
    blocks = []
    errors = []
    for key, url, label in (("house", _HOUSE_URL, "House"), ("senate", _SENATE_URL, "Senate")):
        try:
            blocks.append(_render(_filter_rows(_cached_rows(key, url), ticker), label, limit))
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s congress data failed for %s: %s", label, ticker, exc)
            errors.append(f"{label}: {exc}")
    if not blocks:
        return f"congress trades unavailable for {ticker}: " + ("; ".join(errors) or "unknown")
    body = "\n\n".join(blocks)
    if errors:
        body += f"\n\n(unavailable: {'; '.join(errors)})"
    return body


__all__ = ["get_congress_trades", "_filter_rows", "_net_summary", "_render"]
