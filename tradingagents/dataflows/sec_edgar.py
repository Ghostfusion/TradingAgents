"""SEC EDGAR filings vendor (free, no API key).

Fetches a company's most recent SEC filings from the official EDGAR submissions
API (``data.sec.gov``) and summarizes them by form type. This surfaces the
event-risk signals that news-only analysis misses: 8-K (material events: M&A,
guidance, restatements), 10-K/10-Q (annual/quarterly reports), and S-1/S-3
(capital raises / dilution).

EDGAR is public and keyless but requires a descriptive User-Agent (per SEC fair
access policy) and tolerates only ~10 req/s per IP. The ticker -> CIK lookup uses
the SEC's ``company_tickers.json`` (cached in-process). Every network failure
degrades via ``NoMarketDataError`` so the router surfaces "no data" rather than
crashing.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import date

from .errors import NoMarketDataError
from .symbol_utils import normalize_symbol

logger = logging.getLogger(__name__)

# SEC fair-access: a descriptive User-Agent with a contact is required; the
# bare-project-form UA (no contact) is rejected with 403 on www/data.sec.gov.
_UA = "TradingAgentsResearch/1.0 (TradingAgents analysis; contact: research@example.com)"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_TIMEOUT = 20

# Form types worth surfacing, with a short label for the report.
_FORM_LABELS = {
    "8-K": "8-K (material event / M&A / guidance)",
    "10-K": "10-K (annual report)",
    "10-Q": "10-Q (quarterly report)",
    "S-1": "S-1 (IPO / primary raise)",
    "S-3": "S-3 (shelf / secondary offering)",
    "SC 13D": "SC 13D (activist / 5%+ stake)",
    "SC 13G": "SC 13G (institutional 5%+ stake)",
    "DEF 14A": "DEF 14A (proxy / governance)",
}

# XBRL financial-line tags (us-gaap) surfaced by ``get_financial_history``,
# with human labels. Coverage starts when the filer adopted XBRL (mostly
# 2009-2011 for large filers; later for others) - the report states the actual
# first/last fiscal years it found, so an early-year 'n/a' is honest
# (pre-XBRL) rather than an error.
# label -> candidate us-gaap tags (tried in order; first with FY data wins).
# Revenue: most filers report the ASC 606 tag today, legacy ``Revenues`` pre-2018.
# OCF: the abstract parent carries no value; the concrete tag is
# ``NetCashProvidedByUsedInOperatingActivities``.
_TAG_MAP = {
    "Revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"),
    "Net income (loss)": ("NetIncomeLoss",),
    "Operating cash flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "Capex (-)": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "Total assets": ("Assets",),
    "Total liabilities": ("Liabilities",),
    "Stockholders equity": ("StockholdersEquity",),
    "Cash & equivalents": ("CashAndCashEquivalentsAtCarryingValue",),
}
_COMPANYCONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{tag}.json"

_ticker_cik_cache: dict[str, str] | None = None


def _json_get(url: str, retries: int = 2):
    """GET a JSON document from SEC EDGAR with a descriptive User-Agent.

    SEC rate-limits IPs with HTTP 403 under parallel batch load; retry those
    with a short backoff rather than failing the whole analysis.
    """
    import time

    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 403 and attempt < retries:
                time.sleep(4 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")


def _ticker_map() -> dict[str, str]:
    """Load (lazily, cached) the SEC ticker -> CIK mapping."""
    global _ticker_cik_cache
    if _ticker_cik_cache is None:
        data = _json_get(_TICKERS_URL)
        _ticker_cik_cache = {
            str(row["ticker"]).upper(): str(row["cik_str"]) for row in data.values()
        }
    return _ticker_cik_cache


def _cik_for(ticker: str) -> str | None:
    """Resolve a ticker to its CIK, handling exchange-suffixed symbols."""
    base = normalize_symbol(ticker).split(".")[0].upper()
    return _ticker_map().get(base)


def get_sec_filings(ticker: str, limit: int = 10) -> str:
    """Return a formatted summary of the most recent SEC filings for a ticker.

    Args:
        ticker: Ticker symbol (exchange suffixes like ``0700.HK`` are stripped
            for the CIK lookup; non-US tickers typically have no EDGAR record).
        limit: Max filings to summarize (default 10).

    Returns:
        A markdown report of recent filings by form type + date + accession.
    """
    cik = _cik_for(ticker)
    if cik is None:
        raise NoMarketDataError(
            ticker,
            detail="no CIK found on EDGAR (non-US listing, or ticker not registered)",
        )

    try:
        payload = _json_get(_SUBMISSIONS_URL.format(cik=int(cik)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("EDGAR submissions fetch failed for %s (CIK %s): %s", ticker, cik, exc)
        raise NoMarketDataError(ticker, detail=f"EDGAR submissions fetch failed: {exc}") from exc

    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    accessions = recent.get("accessionNumber", []) or []
    primary_docs = recent.get("primaryDocument", []) or []

    if not forms:
        raise NoMarketDataError(ticker, detail="no recent EDGAR filings returned")

    shown = 0
    lines = [f"## {ticker.upper()} Recent SEC Filings (EDGAR)", ""]
    for i, form in enumerate(forms):
        if shown >= limit:
            break
        # Only surface forms we have a useful label for; skip the noisy 4/A,
        # EFFECT, S-8, etc. that carry little decision signal.
        if form not in _FORM_LABELS:
            continue
        date = dates[i] if i < len(dates) else "?"
        acc = accessions[i].replace("-", "") if i < len(accessions) else "?"
        doc = primary_docs[i] if i < len(primary_docs) else ""
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}" if acc else ""
        lines.append(f"- **{form}** — {_FORM_LABELS[form]} · filed {date}")
        if url:
            lines.append(f"  {url}")
        shown += 1

    if shown == 0:
        # Recent window had only forms we filtered out — still useful to say so.
        top_forms = sorted(set(forms))[:8]
        lines.append(f"(Recent filings were all in filtered form types: {', '.join(top_forms)})")

    lines.append("")
    lines.append(
        "Interpretation: 8-K filings flag material events (M&A, guidance changes, "
        "restatements); S-1/S-3 filings flag capital raises/dilution; SC 13D/G "
        "flag activist or large institutional positions. Weight event filings "
        "(8-K, S-1) above routine periodic reports."
    )
    return "\n".join(lines)
def get_financial_history(ticker: str, years: int = 15) -> str:
    """Annual 10-K financial history from SEC EDGAR XBRL (free, keyless).

    Pulls up to ``years`` of annual (10-K, FY) values for the eight core
    us-gaap tags via the companyconcept API and lays them out as a year-over-
    year table. This is the only free source that goes deeper than the ~4-5y
    statement history of the vendor APIs; coverage starts when the filer
    adopted XBRL (mostly ~2009-2011 for large filers), stated honestly as the
    reported first/last fiscal year per tag-row - early years render n/a only
    when the tag genuinely has no FY value yet. Raises ``NoMarketDataError``
    (consistent with ``get_sec_filings``) on any unresolvable ticker/network
    failure; a missing individual tag degrades to 'n/a', never invents.

    Args:
        ticker: Ticker symbol (exchange suffixes stripped for the CIK lookup;
            non-US tickers typically have no EDGAR record).
        years: Max fiscal years to include (default 15).

    Returns:
        A markdown table (fiscal year-end -> eight tag values) + history span.
    """
    cik = _cik_for(ticker)
    if cik is None:
        raise NoMarketDataError(
            ticker,
            detail="no CIK found on EDGAR (non-US listing, or ticker not registered)",
        )
    by_tag: dict[str, dict[str, int]] = {}
    span = None
    for label, tags in _TAG_MAP.items():
        annual: dict[str, int] = {}
        for tag in tags:
            try:
                payload = _json_get(_COMPANYCONCEPT_URL.format(cik=int(cik), tag=tag))
            except Exception as exc:  # noqa: BLE001
                logger.warning("EDGAR %s fetch failed for %s: %s", tag, ticker, exc)
                continue
            if not isinstance(payload, dict):
                continue
            rows = payload.get("units", {}).get("USD") or []
            # annual 10-K FY rows; instant concepts (assets etc.) carry no
            # ``start`` - match on form/fp alone, dedupe long-format restatements.
            for row in rows:
                if row.get("form") == "10-K" and row.get("fp") == "FY":
                    end = str(row.get("end") or "")[:10]
                    if not end or row.get("val") is None:
                        continue
                    start = str(row.get("start") or "")[:10]
                    if start:
                        try:
                            dur = (date.fromisoformat(end) - date.fromisoformat(start)).days
                        except ValueError:
                            dur = 0
                        # flow rows must span ~a full year; SEC often appends a
                        # short 90-day partial under the same FY end (restatement)
                        if dur < 300:
                            continue
                    annual[end] = int(row["val"])
            if annual:
                break
        if not annual:
            continue
        by_tag[label] = annual
        first, last = min(annual), max(annual)
        span = [first, last] if span is None else [min(span[0], first), max(span[1], last)]
    if not by_tag:
        raise NoMarketDataError(
            ticker,
            detail="no 10-K XBRL facts found on EDGAR (pre-XBRL filer, or no annual data)",
        )
    # desc fiscal-year-ends, capped by ``years`` per tag
    all_ends = sorted({e for ann in by_tag.values() for e in ann}, reverse=True)[: years]
    head = ["fiscal end"] + list(_TAG_MAP)
    rows = []
    for end in all_ends:
        row = [end]
        for label in _TAG_MAP:
            v = by_tag.get(label, {}).get(end)
            row.append(f"{v / 1e9:,.1f}B" if v is not None else "n/a")
        rows.append(row)
    lines = [
        f"## EDGAR XBRL financial history — {ticker} (annual 10-K, USD)",
        "",
    ]
    lines.append("| " + " | ".join(head) + " |")
    lines.append("|" + "|".join(["---"] * len(head)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    if span:
        lines.append("")
        lines.append(f"History span: {span[0]} → {span[1]} (XBRL coverage start; "
                     f"pre-{span[0]} years may be n/a).")
    lines.append("")
    lines.append("Source: SEC EDGAR companyconcept API (free, keyless). "
                 "Advisory — cite it for historical trends; the vendor "
                 "statements (get_income_statement etc.) remain the current-period source.")
    return "\n".join(lines)

_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"


def get_edgar_fulltext_search(query: str, forms: str | None = None,
                              date_range: str = "5y", limit: int = 8) -> str:
    """EDGAR full-text search (SEC efts.sec.gov, free, keyless).

    Searches the full text of SEC filings (10-K/10-Q/8-K/...) for a phrase and
    returns the top hits with form type, filing date and filer. Use for
    customer/supplier-concentration footnotes ("major customer"), peer 10-K
    mentions, and thematic scans. Keyless (descriptive UA only, per SEC fair
    access). Returns an explicit 'unavailable' message on any failure; a
    zero-hit search renders an honest 'no matching filings'.

    Args:
        query: phrase or term to match in filing text (e.g. '"major customer"').
        forms: optional comma-separated form filter (e.g. "10-K", "10-K,10-Q").
        date_range: optional relative window passed to EFTS (e.g. "1y", "5y").
        limit: max hits to render (default 8).
    """
    import urllib.parse as _up

    params = {"q": query}
    if forms:
        params["forms"] = forms
    if date_range:
        params["dateRange"] = date_range
    url = _EFTS_URL + "?" + _up.urlencode(params)
    try:
        data = _json_get(url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("EDGAR full-text search failed for %r: %s", query, exc)
        return f"EDGAR full-text search unavailable: {exc}"
    if not isinstance(data, dict):
        return "EDGAR full-text search unavailable: unexpected payload"
    hits = data.get("hits", {}).get("hits") or []
    total = (data.get("hits", {}).get("total") or {}).get("value")
    lines = [f"## EDGAR full-text search — {query!r}", ""]
    if not hits:
        lines.append("No matching filings (refine the phrase / forms / date range; "
                     "EFTS covers filings since 2001).")
    for h in hits[:limit]:
        src = h.get("_source", {})
        names = ", ".join(src.get("display_names") or []) or "?"
        form = src.get("form", "?")
        filed = src.get("file_date", "?")
        lines.append(f"- {filed} {form} — {names} (ADSH {src.get('adsh', '?')})")
    if total is not None:
        lines.append("")
        lines.append(f"Total matches: {total}")
    lines.append("")
    lines.append("Source: SEC EDGAR Full-Text Search (efts.sec.gov, keyless; filings since 2001). "
                 "Advisory — verify context in the actual filing before quoting.")
    return "\n".join(lines)

