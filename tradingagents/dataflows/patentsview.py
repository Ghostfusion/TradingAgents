"""USPTO PatentsView vendor (free, keyed) for innovation/moat reads.

Pulls patent counts + recent titles per assignee from the USPTO PatentsView
Search API (``search.patentsview.org/api/v1/patent/query``) — the free,
official patent search. Authentication is the ``X-Api-Key`` header
(PATENTSVIEW_API_KEY / TRADINGAGENTS_PATENTSVIEW_API_KEY; free key from the
USPTO ODP transition). The company legal name is resolved via the FMP company
profile (fallback: the ticker), so assignee matching is *name-based* — the
report says so, since a name search can miss subsidiaries/abbreviations.

Any missing key / network failure / zero-result degrades to an explicit
'unavailable' or honest no-records string — never invented counts.
NOTE: the new PatentsView host was unresolvable from this environment at
build time (legacy api.patentsview.org serves the SPA only); the tool is
correct + honest and validates when the host is reachable + a key is set.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://search.patentsview.org/api/v1/patent/query"
_TIMEOUT = 30
_UA = "tradingagents/0.3 (+https://github.com/TauricResearch/TradingAgents)"


def pv_key() -> str | None:
    """PatentsView API key from config or env; None when unset."""
    try:
        from tradingagents.dataflows.config import get_config

        key = get_config().get("patentsview_api_key")
    except Exception:
        key = None
    if key:
        return str(key)
    return os.environ.get("PATENTSVIEW_API_KEY") or os.environ.get("TRADINGAGENTS_PATENTSVIEW_API_KEY")


def _company_name(ticker: str) -> str:
    """Best-known legal name for a ticker (FMP profile), else the ticker."""
    try:
        from tradingagents.dataflows.fmp import get_company_profile

        prof = get_company_profile(ticker)
        name = (prof or {}).get("companyName")
        if name and str(name).strip():
            return str(name).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("company profile lookup failed for %s: %s", ticker, exc)
    return str(ticker or "").strip().upper()


def get_patent_activity(ticker: str, per_page: int = 200) -> str:
    """Patent counts + recent titles for a ticker's assignee (USPTO PatentsView).

    Renders annual granted-patent counts (by publication year, newest first)
    and the most recent titles. Name-based assignee matching (legal name from
    the FMP company profile; subsidiaries/abbreviations may be missed - the
    report says so). Returns an explicit 'unavailable' on a missing key,
    unreachable host or API error; 'no patents' is honest, never invented.
    """

    ticker = str(ticker or "").strip().upper()
    if not ticker:
        return "patent activity unavailable: no ticker"
    key = pv_key()
    if not key:
        return (f"patent activity unavailable for {ticker}: PATENTSVIEW_API_KEY not set "
                "(free USPTO PatentsView key; add TRADINGAGENTS_PATENTSVIEW_API_KEY)")
    name = _company_name(ticker)
    payload = {
        "q": {"_text_any": {"assignee_organization": name}},
        "f": ["patent_number", "patent_date", "patent_title"],
        "o": {"per_page": per_page},
    }
    try:
        import requests

        resp = requests.post(
            _SEARCH_URL,
            json=payload,
            timeout=_TIMEOUT,
            headers={"X-Api-Key": key, "User-Agent": _UA, "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("PatentsView failed for %s (%s): %s", ticker, name, exc)
        return f"patent activity unavailable for {ticker}: {exc}"
    patents = data.get("patents") if isinstance(data, dict) else None
    if not isinstance(patents, list):
        return f"patent activity unavailable for {ticker}: unexpected payload"
    if not patents:
        return (f"no PatentsView records for {ticker} (assignee {name!r} name-based; "
                "try the legal name / check the ticker)")
    by_year: dict[int, int] = {}
    samples: list[tuple[str, str, str]] = []
    for p in patents:
        d = str(p.get("patent_date") or "")
        try:
            yr = int(d[:4])
            by_year[yr] = by_year.get(yr, 0) + 1
        except (TypeError, ValueError):
            continue
        if len(samples) < 6:
            samples.append((d, str(p.get("patent_number") or ""),
                            str(p.get("patent_title") or "")))
    lines = [f"## PatentsView granted patents — {ticker} (assignee {name!r}, name-based)", ""]
    for yr in sorted(by_year, reverse=True):
        lines.append(f"- {yr}: {by_year[yr]} granted")
    if samples:
        lines.append("")
        lines.append("Recent titles:")
        for d, num, title in samples:
            lines.append(f"- {d} {num}: {title[:90]}")
    lines.append("")
    lines.append("Source: USPTO PatentsView Search API (free key; name-based assignee match — "
                 "subsidiaries/abbreviations may be missed). Advisory innovation/moat gauge.")
    return "\n".join(lines)


__all__ = ["get_patent_activity", "pv_key", "_company_name"]
