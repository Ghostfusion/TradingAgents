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

# SEC fair-access: a descriptive User-Agent with a reachable contact is required;
# the bare-project-form UA (no contact) is rejected with 403 on www/data.sec.gov,
# and a non-deliverable placeholder (research@example.com, what shipped before
# 2026-09-17) is what gets an IP throttled under batch load. The contact below is
# the project owner's. Same string as sp500_universe.py:122 - change both.
_UA = "TradingAgentsResearch/1.0 (TradingAgents analysis; contact: vincent_liu@msn.com)"
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
# label -> candidate us-gaap tags, earliest candidate winning PER PERIOD END
# (``annual_facts`` merges them by fiscal end, so a filer that switched concepts
# mid-history keeps both halves of its series).
# Revenue: most filers report the ASC 606 tag today, legacy ``Revenues`` pre-2018.
# OCF: the abstract parent carries no value; the concrete tag is
# ``NetCashProvidedByUsedInOperatingActivities``.
#
# The six balance-sheet rows below were added for the WP-10 panel's fundamentals
# leg (2026-09-18), which needs the current-asset / current-liability / debt legs
# that ``compute_ratios`` reads. Each was verified against live EDGAR payloads
# before being mapped (MSFT carried all six; LULU and WDC carry the current-asset
# pair, and LULU legitimately has no borrowings at all). A filer that does not
# file one of these tags prints 'n/a' for that row - never a substituted zero.
# ``D&A`` is the one row with no universal tag: MSFT files ``Depreciation`` and
# ``AmortizationOfIntangibleAssets`` as separate concepts and no single D&A tag,
# so its D&A row is honestly n/a here rather than a sum under a new definition.
_TAG_MAP = {
    "Revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"),
    "Net income (loss)": ("NetIncomeLoss",),
    "Diluted EPS": ("EarningsPerShareDiluted",),
    "Operating income": ("OperatingIncomeLoss",),
    "D&A": ("DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet"),
    "Gross profit": ("GrossProfit",),
    "Operating cash flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "Capex (-)": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "Total assets": ("Assets",),
    "Total liabilities": ("Liabilities",),
    "Stockholders equity": ("StockholdersEquity",),
    "Cash & equivalents": ("CashAndCashEquivalentsAtCarryingValue",),
    "Current assets": ("AssetsCurrent",),
    "Current liabilities": ("LiabilitiesCurrent",),
    "Inventory": ("InventoryNet",),
    "Short-term investments": ("ShortTermInvestments", "MarketableSecuritiesCurrent"),
    "Long-term debt": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "Long-term debt, current": ("LongTermDebtCurrent", "DebtCurrent"),
    "Retained earnings": ("RetainedEarningsAccumulatedDeficit",),
    "Cost of revenue": ("CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"),
    "Liabilities and equity": ("LiabilitiesAndStockholdersEquity",),
}

#: The annual-report forms whose XBRL facts are annual statements. ``10-K`` is the
#: domestic filer; ``20-F`` is the foreign private issuer (SIMO files nothing else
#: - before this list existed the panel's SEC leg silently saw 0 of 19 tags for
#: every FPI) and ``40-F`` is the Canadian MJDS filer. Amendments (``10-K/A``)
#: carry the same facts and are matched on the form before the slash.
_ANNUAL_FORMS = ("10-K", "20-F", "40-F")

#: The subset of ``_ANNUAL_FORMS`` that marks a **foreign private issuer**. It
#: matters for exactly one derived quantity: an FPI's US-listed line may be an
#: **ADS** whose ratio EDGAR does not carry, so the traded price is per-ADS while
#: the cover-page count below is per **ordinary** share. Multiplying the two
#: overstates a market capitalisation by that ratio - measured on SIMO
#: 2026-09-17 (1 ADS = 4 ordinary shares): the panel derived **$34.0B** against a
#: real **$8.1-8.6B**, making P/E 277.28 instead of ~69 and P/B 40.93 instead of
#: ~10. The flag exists so the market-cap join can refuse rather than produce a
#: wrong number.
_FOREIGN_FORMS = ("20-F", "40-F")

# The reference-year rule - "the newest eligible fiscal end carried by the core
# statement lines, so a tag with no value there is absent rather than substituted
# from another year" - belongs to the CANONICAL ASSEMBLY, not here: it reads
# assembled statement labels rather than raw tags. It lives at
# ``scripts/score_panel.py::SEC_REFERENCE_LABELS``. A reference-tag tuple was
# declared here once and read by nothing; do not re-add one.

# Per-share values are reported in USD/shares (and occasionally USD/shares in a
# separate unit key), not plain USD, so the row reader must accept the units the
# SEC actually files under rather than assume "USD" for every concept.
_UNIT_KEYS = ("USD", "USD/shares")

# EBITDA and FCF have no us-gaap tag: they are DERIVED in the consumer
# (``OperatingIncomeLoss + D&A`` and ``OCF - capex``) and labelled derived
# wherever they are printed. Fetched-as-a-tag would be a fabrication.
_DERIVED_LABELS = ("EBITDA", "FCF")
_COMPANYCONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{tag}.json"
# One call returns EVERY us-gaap tag for the filer, where the per-tag concept
# endpoint costs one request each (11 for the eight rows below). The SEC's
# published fair-access ceiling is 10 requests/second per IP, so the single call
# is what makes extending the tag set affordable. Kept as the primary path with
# the per-tag loop as the fallback: a multi-MB payload can fail or truncate where
# a small one would not, and losing every tag at once is a worse failure than
# losing one.
_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


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


def _company_facts(cik: int) -> dict | None:
    """The whole ``facts`` block for the filer, in ONE request.

    Carries every namespace the payload has - ``us-gaap`` (the statements) and
    ``dei`` (the cover-page share count) - so the two readers share one fetch
    rather than paying a second request for the share count. Returns None on any
    failure, so the caller falls back to the per-tag concept endpoint rather
    than losing the table.
    """
    try:
        payload = _json_get(_COMPANYFACTS_URL.format(cik=int(cik)))
    except Exception as exc:  # noqa: BLE001 - the caller has a fallback path
        logger.warning("EDGAR companyfacts fetch failed for CIK %s: %s", cik, exc)
        return None
    facts = payload.get("facts") if isinstance(payload, dict) else None
    return facts if isinstance(facts, dict) else None


def _us_gaap_facts(cik: int) -> dict | None:
    """Every us-gaap concept for the filer (``_company_facts``' us-gaap view)."""
    gaap = (_company_facts(cik) or {}).get("us-gaap")
    return gaap if isinstance(gaap, dict) else None


def _annual_rows(rows) -> dict[str, dict]:
    """Annual FY values from one concept's unit list, by period end.

    A row qualifies when its form is an annual report (``_ANNUAL_FORMS``, before
    any ``/A`` amendment suffix) and its fiscal period is ``FY``. Flow concepts
    carry ``start`` and must span ~a full year: the SEC often appends a short
    90-day partial under the same FY end (restatement), which would otherwise
    overwrite the annual figure. Instant concepts (assets etc.) carry no
    ``start`` and are matched on form/fp alone.

    Returns ``{fiscal_end: {"val": value, "filed": filing_date}}``. The ``filed``
    date is what makes a point-in-time read possible: a panel for a past trading
    date must not see a filing that had not happened yet, or it measures the
    future. Where a period end carries several filings the latest one wins (a
    restatement supersedes the original).
    """
    annual: dict[str, dict] = {}
    for row in rows or []:
        form = str(row.get("form") or "").split("/")[0]
        if form not in _ANNUAL_FORMS or row.get("fp") != "FY":
            continue
        end = str(row.get("end") or "")[:10]
        if not end or row.get("val") is None:
            continue
        start = str(row.get("start") or "")[:10]
        if start:
            try:
                dur = (date.fromisoformat(end) - date.fromisoformat(start)).days
            except ValueError:
                dur = 0
            if dur < 300:
                continue
        filed = str(row.get("filed") or "")[:10]
        prev = annual.get(end)
        if prev is None or filed >= prev["filed"]:
            annual[end] = {"val": row["val"], "filed": filed}
    return annual


def _cover_page_shares(rows) -> dict[str, dict]:
    """Cover-page share counts by period end, from ANY filing form.

    The dei count is not an annual statement line: it is the number printed on
    the cover of whichever report was filed, so a 10-Q's count is legitimately
    newer than the last 10-K's. Filtering it through ``_annual_rows`` (10-K/20-F,
    fp=FY) would throw away every quarterly cover page and leave a market
    capitalisation up to a year stale for no reason.
    """
    out: dict[str, dict] = {}
    for row in rows or []:
        end = str(row.get("end") or "")[:10]
        if not end or row.get("val") is None:
            continue
        filed = str(row.get("filed") or "")[:10]
        prev = out.get(end)
        if prev is None or filed >= prev["filed"]:
            out[end] = {"val": row["val"], "filed": filed}
    return out


def annual_facts(ticker: str, years: int = 15) -> dict:
    """The structured annual facts behind ``get_financial_history``.

    One request per filer, one shape for every reader (ground rule 2): the
    rendered leaf and ``statement_parsing.sec_annual_series`` both read this, so
    the table and the series can never disagree about a fiscal year.

    Returns ``{"series": {label: {fiscal_end: {"val", "filed"}}},
    "shares": {fiscal_end: {"val", "filed"}}, "span": [first, last] | None,
    "foreign_private_issuer": bool, "years": years}``. ``shares`` is the dei
    cover-page count
    (``EntityCommonStockSharesOutstanding``), which carries its own period ends
    and is far fresher than the fiscal-year balance - the leg a market
    capitalisation needs. ``foreign_private_issuer`` is True when that cover page
    came from a 20-F/40-F: the count is then **ordinary** shares while a
    US-listed price may be per **ADS**, and EDGAR does not carry the ratio, so a
    reader deriving a market cap from the two must refuse rather than guess (see
    ``_FOREIGN_FORMS``). Raises ``NoMarketDataError`` on an unresolvable ticker
    (non-US listing, no CIK) or when no tag carries an annual value, exactly as
    the rendered leaf does, so a caller treating the facts as optional must
    catch it.

    Args:
        ticker: Ticker symbol (exchange suffixes stripped for the CIK lookup).
        years: Max fiscal years to include per row (default 15).
    """
    cik = _cik_for(ticker)
    if cik is None:
        raise NoMarketDataError(
            ticker,
            detail="no CIK found on EDGAR (non-US listing, or ticker not registered)",
        )
    facts = _company_facts(int(cik))
    gaap = (facts or {}).get("us-gaap")
    # The per-tag fallback exists for ONE failure: the multi-MB companyfacts
    # payload did not arrive. A payload that arrived and simply carries no
    # us-gaap namespace (an IFRS filer such as TSM files under ``ifrs-full``) is
    # NOT that failure - falling back there would spend one request per tag to
    # collect a page of 404s and still find nothing.
    per_tag = facts is None
    by_tag: dict[str, dict[str, dict]] = {}
    span = None
    for label, tags in _TAG_MAP.items():
        # Candidates are merged BY PERIOD END, earliest candidate winning, rather
        # than "the first tag with any data wins". Filers switch tags mid-history
        # (revenue moved to the ASC 606 concept in 2018; NVDA's
        # ``CostOfGoodsAndServicesSold`` stops in 2021 and ``CostOfRevenue``
        # carries on), so first-tag-wins silently returns a series that ends
        # years before the filer's latest report - and a point-in-time read then
        # finds nothing at the reference year while the value sits in the next
        # candidate all along.
        merged: dict[str, dict] = {}
        for tag in tags:
            rows: dict[str, dict] = {}
            if isinstance(gaap, dict):
                units = (gaap.get(tag) or {}).get("units") or {}
                for unit in _UNIT_KEYS:
                    rows = _annual_rows(units.get(unit) or [])
                    if rows:
                        break
            elif per_tag:
                # Fallback: one request per tag (the pre-companyfacts path).
                try:
                    payload = _json_get(_COMPANYCONCEPT_URL.format(cik=int(cik), tag=tag))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("EDGAR %s fetch failed for %s: %s", tag, ticker, exc)
                    continue
                if not isinstance(payload, dict):
                    continue
                units = payload.get("units") or {}
                for unit in _UNIT_KEYS:
                    rows = _annual_rows(units.get(unit) or [])
                    if rows:
                        break
            else:
                break
            for end, entry in rows.items():
                merged.setdefault(end, entry)
        if not merged:
            continue
        by_tag[label] = merged
        first, last = min(merged), max(merged)
        span = [first, last] if span is None else [min(span[0], first), max(span[1], last)]
    if not by_tag:
        raise NoMarketDataError(
            ticker,
            detail=(
                "no us-gaap annual facts on EDGAR for this filer "
                + ("(the companyfacts payload could not be fetched, and no "
                   "individual tag carried annual data)"
                   if per_tag else
                   "(pre-XBRL filer, or a filer reporting outside us-gaap - "
                   "e.g. an IFRS filer such as TSM)")
            ),
        )
    dei = (facts or {}).get("dei")
    shares: dict[str, dict] = {}
    # Whether the cover-page count belongs to a 20-F/40-F filer, whose US-listed
    # line may be an ADS. Detected on the dei rows themselves: the cover page is
    # where the count comes from, so the form that printed it is the form that
    # decides the unit.
    foreign_private_issuer = False
    if isinstance(dei, dict):
        units = (dei.get("EntityCommonStockSharesOutstanding") or {}).get("units") or {}
        for unit in ("shares", "shares/shares"):
            rows = units.get(unit) or []
            for row in rows:
                if str(row.get("form") or "").split("/")[0] in _FOREIGN_FORMS:
                    foreign_private_issuer = True
                    break
            shares = _cover_page_shares(rows)
            if shares:
                break
    return {
        "series": by_tag,
        "shares": shares,
        "span": span,
        "foreign_private_issuer": foreign_private_issuer,
        "years": years,
    }


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


def financial_history_series(ticker: str, years: int = 15) -> dict:
    """The STRUCTURED annual series behind ``get_financial_history``.

    One implementation, two readers (ground rule 2): the markdown leaf renders
    from this, and ``statement_parsing.sec_annual_series`` consumes it for the
    multi-year series the G-Score G4/G5 legs and the CAGR family need - which the
    ~4-5y vendor statements cannot clear. Reads ``annual_facts`` (the 10-K / 20-F
    / 40-F annual facts, with their filing dates) and flattens it to the
    ``{fiscal_end: value}`` shape both readers index by period.

    Returns ``{"series": {label: {fiscal_end: value}}, "span": [first, last] |
    None, "years": years}``. Raises ``NoMarketDataError`` on an unresolvable
    ticker (non-US listing, no CIK) or when no tag carries an annual 10-K FY
    value, exactly as the rendered leaf does, so a caller that treats the series
    as optional must catch it.

    Args:
        ticker: Ticker symbol (exchange suffixes stripped for the CIK lookup).
        years: Max fiscal years to include per row (default 15).
    """
    facts = annual_facts(ticker, years=years)
    return {
        "series": {
            label: {end: entry["val"] for end, entry in by_end.items()}
            for label, by_end in facts["series"].items()
        },
        "span": facts["span"],
        "years": years,
    }


def get_financial_history(ticker: str, years: int = 15) -> str:
    """Annual financial history from SEC EDGAR XBRL (free, keyless).

    Renders ``financial_history_series`` - the structured producer - so the table
    and any consumer of the series can never disagree. The values come from one
    ``companyfacts`` request per filer (the per-tag concept endpoint is the
    fallback when the larger payload fails), covering the domestic 10-K and the
    foreign-private-issuer 20-F / MJDS 40-F annual reports. This is the only free
    source that goes deeper than the ~4-5y statement history of the vendor APIs;
    coverage starts when the filer adopted XBRL (mostly ~2009-2011 for large
    filers), stated honestly as the reported first/last fiscal year per tag-row -
    early years render n/a only when the tag genuinely has no FY value yet.
    Raises ``NoMarketDataError`` (consistent with ``get_sec_filings``) on any
    unresolvable ticker/network failure; a missing individual tag degrades to
    'n/a', never invents. EBITDA and FCF have no us-gaap tag and are NOT printed
    here: they are derived by the consumer and labelled derived.

    Args:
        ticker: Ticker symbol (exchange suffixes stripped for the CIK lookup;
            non-US tickers typically have no EDGAR record).
        years: Max fiscal years to include (default 15).

    Returns:
        A markdown table (fiscal year-end -> one column per tag row) + span.
    """
    series = financial_history_series(ticker, years=years)
    by_tag = series["series"]
    span = series["span"]
    # desc fiscal-year-ends, capped by ``years`` per tag
    all_ends = sorted({e for ann in by_tag.values() for e in ann}, reverse=True)[: years]
    head = ["fiscal end"] + list(_TAG_MAP)
    rows = []
    for end in all_ends:
        row = [end]
        for label in _TAG_MAP:
            v = by_tag.get(label, {}).get(end)
            if v is None:
                row.append("n/a")
            elif label == "Diluted EPS":
                row.append(f"{v:,.2f}")
            else:
                row.append(f"{v / 1e9:,.1f}B")
        rows.append(row)
    lines = [
        f"## EDGAR XBRL financial history — {ticker} (annual 10-K / 20-F, USD)",
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
    lines.append("Source: SEC EDGAR companyfacts API (free, keyless). "
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

