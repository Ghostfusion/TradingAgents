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
from datetime import date, timedelta

from .date_window import get_run_trade_date
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
    # Research and development (FUND-17): the income statement's R&D expense,
    # which the 106-factor table's §12 row found absent even though the whole
    # ``us-gaap`` namespace is already in hand - ``_company_facts`` fetches the
    # entire companyfacts payload in ONE request and ``annual_facts`` merely
    # filters it by this map, so declaring the row costs no extra fetch.
    # Verified live on MSFT's companyfacts (2026-09-28): the tag is present
    # under units ``USD``. The canonical key it feeds is what the G-Score's
    # peer-median leg reads (``quantitative_scores.growth_metrics`` ->
    # ``rd_intensity``); a filer that does not file it stays absent, never 0.
    "Research and development": ("ResearchAndDevelopmentExpense",),
    "Gross profit": ("GrossProfit",),
    "Operating cash flow": ("NetCashProvidedByUsedInOperatingActivities",),
    # Capex: filers switch the concept mid-history, exactly like revenue. AMZN
    # filed ``PaymentsToAcquirePropertyPlantAndEquipment`` through FY2016 and
    # ``PaymentsToAcquireProductiveAssets`` from FY2016 on (probed 2026-10-05:
    # the first tag's newest 10-K annual fact is FY2016 = 6,737M, the second's
    # is FY2025 = 131,819M). With only the first tag the series STOPPED at
    # FY2016, so every consumer that read its newest value read a nine-year-old
    # capex - and ``ratios.sbc_adjusted_fcf`` paired it with a current-year OCF,
    # publishing FCF 132,777M for AMZN against a true 7,695M. The two tags
    # disagree for FY2016 (6,737M vs 7,804M), so the earliest candidate keeps
    # winning that year and the merged series stays continuous.
    "Capex (-)": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),
    # Share-based compensation: the ONE us-gaap tag whose definition is the
    # cash-flow statement's non-cash add-back ("aggregate amount of noncash,
    # equity-based employee remuneration ... an add back when calculating net
    # cash generated by operating activities using the indirect method"), i.e.
    # exactly the amount ``ReportingFCF = OCF - capex`` counts as cash and the
    # SBC-adjusted (economic) FCF subtracts again (ValuationScore §55).
    #
    # DELIBERATELY a single tag, not a candidate list. The nearest alternative,
    # ``AllocatedShareBasedCompensationExpense``, is the INCOME-STATEMENT
    # allocated expense - a different quantity, not a second spelling: measured
    # 2026-09-27 on SIMO FY2025 they are 26,283,000 vs 203,305,000 (7.7x), so
    # silently falling back would change the measured factor name-for-name
    # across the cross-section. A filer that does not file this tag refuses
    # (see ``strategies/ratios.sbc_adjusted_fcf``) rather than substituting it.
    "Share-based compensation": ("ShareBasedCompensation",),
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
    # Deferred / unearned revenue (FUND-10): a LIABILITY, and the reason
    # ``_ROW_LABEL_EXCLUDES['revenue']`` refuses the word from the revenue
    # alias. Live MSFT companyfacts (2026-09-28) carries both spellings - the
    # contract-liability family and the older deferred-revenue family - so the
    # candidate list prefers the CURRENT contract liability (the standard
    # balance-sheet "unearned revenue" line) and falls back through the other
    # three, the same specific-first ordering ``Long-term debt`` uses.
    "Deferred revenue": (
        "ContractWithCustomerLiabilityCurrent",
        "DeferredRevenueCurrent",
        "ContractWithCustomerLiability",
        "DeferredRevenue",
    ),
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


#: The top-level classification fields of the last submissions payload per CIK.
#:
#: ``get_sec_filings`` reads only ``filings.recent`` and discards the payload's
#: ``sic`` / ``sicDescription`` / ``name`` / ``exchanges`` on **every** call, so a
#: caller that wants the regulatory classification has to pay for the fetch again.
#: This memo lets a later step read what the run already paid for.
#:
#: Bounded, and deliberately a memo rather than a cache: entries are only ever
#: *written* by a real fetch, and :func:`peek_sic` never fetches. A process that
#: resolves more than ``_SIC_MEMO_MAX`` issuers drops the oldest wholesale rather
#: than growing without bound - the fields are reproducible, so forgetting one
#: costs a ``None``, never a wrong answer.
_SIC_MEMO: dict[int, tuple[str | None, str | None]] = {}
_SIC_MEMO_MAX = 512


def _remember_sic(cik: int, payload: dict) -> None:
    """Keep the classification fields of a payload we just fetched."""
    sic = payload.get("sic")
    desc = payload.get("sicDescription")
    _SIC_MEMO[int(cik)] = (str(sic) if sic else None, str(desc) if desc else None)
    if len(_SIC_MEMO) > _SIC_MEMO_MAX:
        _SIC_MEMO.clear()


def peek_sic(ticker: str) -> tuple[str | None, str | None]:
    """``(sic, sicDescription)`` **if this run already fetched the payload**.

    Returns ``(None, None)`` when it did not, and never fetches to find out: the
    security-context layer records a classification opportunistically, so an
    absent SIC means "not read", not "no SIC exists". The caller can tell the
    difference because it knows whether ``get_sec_filings`` ran.
    """
    cik = _cik_for(ticker)
    if cik is None:
        return (None, None)
    return _SIC_MEMO.get(int(cik), (None, None))


def recent_filing_forms(ticker: str, limit: int | None = None) -> list[dict]:
    """The recent filings as ROWS - the structured producer behind
    :func:`get_sec_filings`' markdown and the form vocabulary `news_score.
    corporate_events_score` types (one producer, two readers).

    Each row is ``{"form", "date", "accession", "document", "url"}``. **Every**
    form type is returned, including the ones ``get_sec_filings`` filters out of
    its prose: the caller decides what it can type, and an unknown form is
    ignored by the event table rather than defaulted. ``limit`` caps the rows
    (``None`` returns the whole recent window).

    Raises ``NoMarketDataError`` exactly as ``get_sec_filings`` does: no CIK, a
    failed fetch, or a payload with no filings.
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

    # The payload carries a regulatory classification this function never asks
    # for; keep it for a later step instead of making that step re-fetch.
    _remember_sic(cik, payload)

    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    accessions = recent.get("accessionNumber", []) or []
    primary_docs = recent.get("primaryDocument", []) or []

    if not forms:
        raise NoMarketDataError(ticker, detail="no recent EDGAR filings returned")

    rows: list[dict] = []
    for i, form in enumerate(forms):
        if limit is not None and len(rows) >= int(limit):
            break
        acc = str(accessions[i]).replace("-", "") if i < len(accessions) else ""
        doc = str(primary_docs[i]) if i < len(primary_docs) else ""
        rows.append(
            {
                "form": str(form),
                "date": str(dates[i]) if i < len(dates) else "",
                "accession": acc,
                "document": doc,
                "url": (
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}"
                    if acc
                    else ""
                ),
            }
        )
    return rows


def get_sec_filings(ticker: str, limit: int = 10) -> str:
    """Return a formatted summary of the most recent SEC filings for a ticker.

    Renders :func:`recent_filing_forms`, the structured producer, keeping only
    the forms that carry a label and a decision signal.

    Args:
        ticker: Ticker symbol (exchange suffixes like ``0700.HK`` are stripped
            for the CIK lookup; non-US tickers typically have no EDGAR record).
        limit: Max filings to summarize (default 10).

    Returns:
        A markdown report of recent filings by form type + date + accession.
    """
    rows = recent_filing_forms(ticker)

    shown = 0
    lines = [f"## {ticker.upper()} Recent SEC Filings (EDGAR)", ""]
    for row in rows:
        if shown >= limit:
            break
        form = row["form"]
        # Only surface forms we have a useful label for; skip the noisy 4/A,
        # EFFECT, S-8, etc. that carry little decision signal.
        if form not in _FORM_LABELS:
            continue
        lines.append(f"- **{form}** — {_FORM_LABELS[form]} · filed {row['date'] or '?'}")
        if row["url"]:
            lines.append(f"  {row['url']}")
        shown += 1

    if shown == 0:
        # Recent window had only forms we filtered out — still useful to say so.
        top_forms = sorted({row["form"] for row in rows})[:8]
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


# ---------------------------------------------------------------------------
# Form 4 insider transactions (the optional ``edgar`` extra)
#
# EDGAR is ISSUER-centric for Form 4: a ticker resolves to the issuer's CIK, so
# ``Company(ticker).get_filings(form=4)`` is exactly "this stock's insider
# transactions in a window". That is why Form 4 is wired here and 13F is not: a
# 13F-HR is FILER-centric (one fund's portfolio), so "who holds this stock" would
# need every filer's report scanned - thousands of requests per symbol - which is
# a worse answer than the holders list moomoo/yfinance already print.
#
# Verified against edgartools 5.61.1 before wiring, not from memory: the identity
# is set via ``set_identity("Name email")``, the window filter is
# ``get_filings(form=4, date=(start, end))``, the open-market rows are
# ``form4.market_trades``, and the 10b5-1 flag is
# ``TransactionSummary.has_10b5_1_plan`` - the documented ``has_10b5_1`` does not
# exist on that object in 5.61.1.
#
# ``edgartools`` is an OPTIONAL extra rather than a core dependency: it pulls
# pyarrow, lxml, orjson, rapidfuzz and rank-bm25, which is a lot of install weight
# for one vendor that sits at the end of a chain. ``pip install
# "tradingagents[edgar]"`` enables it; without the extra the vendor raises a typed
# ``NoMarketDataError`` naming the install, so the chain advances with a reason
# rather than an empty read.
# ---------------------------------------------------------------------------

#: edgartools' ``set_identity`` takes "Name email" and the library builds its own
#: SEC User-Agent from it. Same contact as ``_UA`` above - change both.
_IDENTITY = "TradingAgentsResearch vincent_liu@msn.com"

#: Labels for the Form 4 transaction codes the render prints. ``market_trades``
#: is already filtered to the open-market pair (P/S); the map exists so a code
#: the library adds later prints as its own letter instead of being dropped.
_F4_CODE_LABELS = {
    "P": "open-market purchase",
    "S": "open-market sale",
    "M": "option exercise",
    "A": "grant / award",
    "F": "tax withholding",
    "C": "conversion",
    "G": "gift",
    "D": "disposition (other)",
}

#: An ImportError is remembered (below) so a chain that reaches this vendor on
#: every symbol does not re-attempt the optional import each time.
_EDGAR_IMPORT_ERROR: str | None = None
_EDGAR_IDENTITY_SET = False


def _edgar_module():
    """The imported ``edgar`` module, or ``None`` when the extra is absent.

    Memoised on the failure path only: a successful import is a ``sys.modules``
    lookup, but a missing extra must not be re-attempted once per symbol.
    """
    global _EDGAR_IMPORT_ERROR
    if _EDGAR_IMPORT_ERROR is not None:
        return None
    try:
        import edgar
    except Exception as exc:  # noqa: BLE001 - the extra is optional: absence is a reason, not an error
        _EDGAR_IMPORT_ERROR = str(exc)
        return None
    return edgar


def _edgar_ready():
    """``(module, None)`` when ready to query, else ``(None, reason)``.

    Performs the one-time ``set_identity``: the SEC rejects a request with no
    reachable contact, and edgartools builds its own User-Agent from this
    identity, so it must be set before the first fetch. ``_UA`` covers this
    module's own requests; the library's requests are its own.
    """
    global _EDGAR_IDENTITY_SET
    edgar = _edgar_module()
    if edgar is None:
        return None, (
            f"the edgartools extra is not installed ({_EDGAR_IMPORT_ERROR}); "
            'install it with: pip install "tradingagents[edgar]"'
        )
    if not _EDGAR_IDENTITY_SET:
        try:
            edgar.set_identity(_IDENTITY)
        except Exception as exc:  # noqa: BLE001 - degrade to a reason, never raise
            return None, f"edgartools could not set the SEC identity: {exc}"
        _EDGAR_IDENTITY_SET = True
    return edgar, None


def _f4_num(value) -> float | None:
    """A numeric cell as a float, or ``None`` - never a substituted zero.

    A missing price is *unknown*, not free, and a NaN/inf cell is not a quantity;
    both become ``None`` so the render can print n/a honestly.
    """
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return out


def _f4_day(value) -> str | None:
    """A date-ish cell as ``YYYY-MM-DD``, or ``None``.

    The library hands back ``datetime.date``, pandas ``Timestamp`` and plain
    strings across its own paths, so all three are accepted rather than one being
    assumed and the others silently truncated.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value[:10] or None
    try:
        return value.date().isoformat()
    except AttributeError:
        return str(value)[:10] or None


def _f4_endpoint(days: int) -> tuple[str, str]:
    """``(start, end)`` ISO dates: the ``days`` up to the run trade date.

    Anchored on ``get_run_trade_date()`` rather than ``date.today()`` so two runs
    of one symbol read the same window - the reproducibility contract the score
    panels already use.
    """
    end = get_run_trade_date()
    try:
        start = (date.fromisoformat(end) - timedelta(days=days)).isoformat()
    except (TypeError, ValueError):
        end = date.today().isoformat()
        start = (date.today() - timedelta(days=days)).isoformat()
    return start, end


def _insider_rows(ticker: str, start_date: str, end_date: str) -> list[dict]:
    """Form 4 **open-market** insider transactions for ``ticker``, as ROWS.

    Private on purpose: the render below is the only consumer today, and a public
    producer with no caller outside this module is what the calc-wiring gate
    exists to reject. Promote it the moment a signal wants the rows (an insider
    buy/sell net is the obvious one).

    One dict per transaction, newest first, over ``[start_date, end_date]`` matched
    on the **transaction** date (a filing can land days after the trade). This is
    the open-market subset - grants, option exercises and tax withholding are
    compensation mechanics rather than a decision - which is also the subset the
    Massive fallback labels.

    Every key but ``value`` is read straight off the filing; ``value`` is DERIVED
    as ``shares * price`` and is ``None`` when either is missing. ``plan_10b5_1``
    is the filing's own Rule 10b5-1 flag: a pre-scheduled sale is a weaker signal
    than a discretionary one (``None`` = the footnotes do not say).

    Raises ``NoMarketDataError`` when the extra is absent, the query fails, or no
    Form 4 landed in the window - so the router advances the chain with a reason.
    """
    edgar, reason = _edgar_ready()
    if edgar is None:
        raise NoMarketDataError(ticker, detail=reason)

    # EDGAR's Form 4 index is keyed by the issuer, so a class-suffixed symbol
    # still queries its base ("BRK.B" -> "BRK").
    base = normalize_symbol(ticker).split(".")[0].upper()
    try:
        filings = edgar.Company(base).get_filings(form=4, date=(start_date, end_date))
    except Exception as exc:  # noqa: BLE001 - a vendor failure degrades to no-data
        raise NoMarketDataError(ticker, detail=f"EDGAR Form 4 query failed: {exc}") from exc

    rows: list[dict] = []
    for filing in filings or []:
        try:
            form4 = filing.obj()
        except Exception:  # noqa: BLE001 - one malformed filing is skipped, not fatal
            continue
        if form4 is None:
            continue
        try:
            summary = form4.get_ownership_summary()
            trades = form4.market_trades
        except Exception:  # noqa: BLE001 - a filing whose tables will not parse is skipped
            continue
        if trades is None or len(trades) == 0:
            continue
        insider = getattr(summary, "insider_name", None)
        position = getattr(summary, "position", None)
        plan = getattr(summary, "has_10b5_1_plan", None)
        filed = _f4_day(getattr(filing, "filing_date", None))
        for _, trade in trades.iterrows():
            shares = _f4_num(trade.get("Shares"))
            price = _f4_num(trade.get("Price"))
            rows.append({
                "date": _f4_day(trade.get("Date")),
                "insider": insider,
                "position": position,
                "code": trade.get("Code"),
                "kind": trade.get("TransactionType"),
                "shares": shares,
                "price": price,
                "value": None if (shares is None or price is None) else shares * price,
                "remaining": _f4_num(trade.get("Remaining")),
                "acquired_disposed": trade.get("AcquiredDisposed"),
                "direct_indirect": trade.get("DirectIndirect"),
                "plan_10b5_1": plan,
                "filed": filed,
            })

    if not rows:
        raise NoMarketDataError(
            ticker,
            detail=(
                f"no open-market Form 4 transactions on EDGAR between "
                f"{start_date} and {end_date}"
            ),
        )
    # Newest first; a row with no parseable date sorts last rather than first.
    rows.sort(key=lambda r: r["date"] or "", reverse=True)
    return rows


def get_insider_transactions_sec_edgar(ticker: str, days: int = 365) -> str:
    """Open-market Form 4 insider transactions from SEC EDGAR (keyless, free).

    The vendor behind ``get_insider_transactions``: the trailing ``days`` up to
    the run trade date, one row per open-market trade, the per-insider net, and
    the Rule 10b5-1 flag. Rendered from :func:`_insider_rows`, so the prose and
    any future structured consumer cannot disagree about the same filing.

    Raises ``NoMarketDataError`` (via the producer) when the extra is absent or
    EDGAR has nothing in the window; the router turns that into its typed NO_DATA
    sentinel, so a caller never sees an empty table dressed as data.
    """
    start, end = _f4_endpoint(days)
    rows = _insider_rows(ticker, start, end)

    lines = [
        f"## SEC EDGAR Form 4 insider transactions — {normalize_symbol(ticker)} "
        f"(open-market only)",
        "",
        f"Window: {start} to {end} (trailing {days} days to the run trade date). "
        f"{len(rows)} open-market transaction(s) across "
        f"{len({r['insider'] for r in rows if r['insider']})} insider(s).",
        "",
        "| date | insider | position | code | shares | price | value | remaining |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        code = (r["code"] or "?")
        label = _F4_CODE_LABELS.get(code.upper(), code)
        lines.append(
            f"| {r['date'] or 'n/a'} | {r['insider'] or 'n/a'} | {r['position'] or 'n/a'} "
            f"| {code} ({label}) "
            f"| {'n/a' if r['shares'] is None else format(r['shares'], ',.0f')} "
            f"| {'n/a' if r['price'] is None else format(r['price'], ',.2f')} "
            f"| {'n/a' if r['value'] is None else '$' + format(r['value'], ',.0f')} "
            f"| {'n/a' if r['remaining'] is None else format(r['remaining'], ',.0f')} |"
        )

    # Per-insider open-market net: the number the prose has to give, because a
    # table of individual trades does not answer "was this insider buying".
    by_insider: dict[str, dict[str, float]] = {}
    for r in rows:
        acc = by_insider.setdefault(
            r["insider"] or "unknown",
            {"bought": 0.0, "sold": 0.0, "buy_value": 0.0, "sell_value": 0.0},
        )
        code = (r["code"] or "").upper()
        shares = r["shares"] or 0.0
        value = r["value"] or 0.0
        if code == "P":
            acc["bought"] += shares
            acc["buy_value"] += value
        elif code == "S":
            acc["sold"] += shares
            acc["sell_value"] += value

    lines.append("")
    lines.append("**Open-market net per insider** (grants, option exercises and tax "
                 "withholding are excluded by construction):")
    for name, acc in sorted(
        by_insider.items(), key=lambda kv: -(kv[1]["buy_value"] + kv[1]["sell_value"])
    ):
        net = acc["bought"] - acc["sold"]
        lines.append(
            f"- {name}: net {net:+,.0f} shares "
            f"(bought {acc['bought']:,.0f} for ${acc['buy_value']:,.0f}; "
            f"sold {acc['sold']:,.0f} for ${acc['sell_value']:,.0f})"
        )

    flagged = sum(1 for r in rows if r["plan_10b5_1"] is True)
    unknown = sum(1 for r in rows if r["plan_10b5_1"] is None)
    lines.append("")
    lines.append(
        f"Rule 10b5-1: {flagged} transaction(s) filed under a pre-scheduled plan "
        f"(a weaker signal than a discretionary trade); {unknown} whose footnotes "
        f"do not say either way."
    )
    lines.append("")
    lines.append(
        "Source: SEC EDGAR Form 4 (keyless, free) via edgartools — the OPEN-MARKET "
        "subset only, so 'no insider buys' here does not mean 'no Form 4 was "
        "filed'. `value` is derived (shares x price). Advisory input, not a rating."
    )
    return "\n".join(lines)

