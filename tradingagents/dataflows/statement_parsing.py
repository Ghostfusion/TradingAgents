"""Vendor-output -> canonical line-item parsing shared by the agent tools.

Extracted from ``scripts/value_screener.py`` so the agent analysis tools (which
run inside the installed ``tradingagents`` CLI, whose wheel ships only
``tradingagents*`` and ``cli*``) can parse moomoo / yfinance / alpha_vantage /
Finnhub statement payloads without depending on ``scripts/`` being on
``sys.path``. ``scripts/value_screener.py`` re-exports these names so the
screener CLI and the tests that import them keep working unchanged.

Every parser here is pure over the payload string except ``fetch_ticker`` /
``screen_ticker``, which route through ``route_to_vendor`` (same package) and
the quantitative screens. No number is ever fabricated: a missing line item
stays ``None`` / "n/a".
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re

from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.dataflows.quantitative_scores import (
    acquirers_multiple,
    altman_z_score,
    beneish_m_score,
    earnings_yield,
    enterprise_value,
    gross_profitability,
    net_operating_assets,
    piotroski_f_score,
    tobins_q,
)

logger = logging.getLogger("statement_parsing")

# Labels that must never stand in for a canonical item even though one of its
# aliases matches them as a substring. Order within ``_ROW_ALIASES`` alone
# cannot express these: ``'ebit' in 'ebitda'`` matches the EBITDA line for
# ``operating_income``, and the combined "Total Liabilities And Equity" balance
# line matches the ``total_liabilities`` / ``total_debt`` aliases although it
# also carries shareholders' equity. Excluded labels are skipped and the alias
# scan continues, so a real standalone row still wins when one exists.
_ROW_LABEL_EXCLUDES = {
    "operating_income": ("ebitda",),
    "total_liabilities": ("equity",),
    "total_debt": ("equity",),
    # AOCI-style "Gains Losses Not Affecting Retained Earnings" is not retained
    # earnings, and yfinance lists it FIRST (MSFT/AMZN/NVDA 2026-09-16: Altman
    # Z's X2 read the -3.28bn AOCI row instead of +328.26bn on MSFT).
    "retained_earnings": ("not affecting",),
    # A contra-asset is not the period's depreciation expense. yfinance's
    # BALANCE SHEET carries only "Accumulated Depreciation" (-118.69bn on
    # MSFT), so without this the reader hands EV/EBITDA (and Beneish's
    # depreciation/gross-PPE leg) a negative expense wherever the balance
    # sheet is absorbed and no income/cash-flow row corrects it.
    "depreciation": ("accumulated",),
    # Deferred / unearned revenue is a liability, never revenue: yfinance's
    # balance sheet is the only payload in play here whose rows carry the word.
    "revenue": ("deferred", "unearned"),
}

#: Tokens that NEGATE the item an alias names. The exclusion list above cannot
#: express them because the token is not adjacent to the alias: yfinance's
#: "Total Non Current Assets" contains the ``current assets`` alias and moomoo's
#: "Other Non-Operating Income (Expenses)" the ``operating income`` alias, and
#: both name the opposite of the row being read (MSFT 2026-09-16: the non-current
#: rows supplied a 3.74 current ratio against the statement's own 1.23 and a
#: 403.5bn working capital against 38.9bn; the non-operating row supplied
#: EV/EBIT 779 and an 0.13% earnings yield against 23.7 and 4.22%).
_NEGATION_TOKENS = ("non ", "not ", "excluding ")

_ROW_ALIASES = {
    # ``sales`` must precede the ``operating income`` last-resort alias, else a
    # payload carrying both reports operating income as revenue (P0-10).
    "revenue": ["total revenue", "revenue", "sales", "operating income"],
    "cogs": ["cost of revenue", "cost of goods sold"],
    "sga": ["selling general", "sg&a", "sga expense", "selling and admin"],
    "depreciation": [
        "depreciation",
        "depreciation & amortization",
        "depreciation & depletion",  # moomoo cashflow label
    ],
    "operating_income": ["operating income", "ebit", "operating profit"],
    "net_income": ["net income", "net profit", "net income (common)"],
    "eps": ["diluted eps", "earnings per share", "basic eps"],
    "eps_yoy": [
        "diluted eps yoy",
        "eps yoy",
        "earnings per share yoy",
        "eps growth quarterly yoy",
        "epsgrowthquarterlyyoy",
        "epsgrowthttmyoy",
    ],
    "revenue_yoy": [
        "total revenue yoy",
        "revenue yoy",
        "revenue growth ttm yoy",
        "revenue growth quarterly yoy",
        "revenuegrowthttmyoy",
        "revenuegrowthquarterlyyoy",
    ],
    "interest_expense": ["interest expense", "interest paid"],
    "tax_expense": ["tax provision", "income tax", "tax expense"],
    "cash": ["cash and cash equivalents", "cash & equivalents", "cash & cash"],
    # Cash INCLUDING liquid short-term investments - the basis a net-debt or
    # net-cash statement needs (both vendors in play here carry it under a
    # different label: yfinance "Cash Cash Equivalents And Short Term
    # Investments" 76.651bn, moomoo "Cash and Cash Equivalents & Short-Term
    # Investments" 76.65bn), where `cash` alone binds yfinance's 20.935bn
    # cash-and-equivalents row. Reading `cash` for the DCF bridge made the
    # bridge basis depend on which vendor answered (MSFT 2026-09-16: net cash
    # +29.05bn in the printed leaf vs +19.83bn on the balance sheet's own
    # total debt).
    "cash_and_investments": [
        "cash and cash equivalents & short term investments",
        "cash cash equivalents and short term investments",
        "cash and cash equivalents and short term investments",
        "cash and short term investments",
        "cash equivalents and short term investments",
    ],
    "total_debt": [
        "total debt",
        "total borrowings",
        "long-term debt",
        "long term borrowings",
        "interest-bearing liabilities",
        "total liabilities",  # last-resort fallback only
    ],
    # Only read to complete `total_debt` when the payload carries no total row
    # (see `_total_debt_match`).
    "short_term_debt": [
        "short-term debt and capital lease obligation",
        "current debt and capital lease obligation",
        "short-term debt",
        "current debt",
        "short-term borrowings",
    ],
    "market_cap": ["market cap", "market capitalization", "marketcapitalization"],
    "beta": ["beta"],
    "shares": [
        "common shares outstanding",
        "shares outstanding",
        "total shares outstanding",
        "total shares issued",
        "shares issued",
        "diluted weighted average shares",
        "diluted shares outstanding",
        "diluted shares",
        "basic weightedaverage shares",
        "weighted average shares",
    ],
    "total_assets": ["total assets"],
    "total_equity": [
        "total shareholder equity",
        "total stockholders equity",
        "total stockholder equity",
        "total equity",
        "shareholders equity",
        "stockholders equity",
        "stockholder equity",
        "common stock equity",
    ],
    "total_liabilities": ["total liabilities"],
    "current_assets": ["total current assets", "current assets"],
    "current_liabilities": ["total current liabilities", "current liabilities"],
    "retained_earnings": ["retained earnings"],
    "ppem": ["property plant", "net ppe", "ppe", "fixed assets"],
    "marketable_securities": [
        "marketable securities",
        "short-term investments",
        # moomoo reports the securities-equivalent line under Financial Assets
        # / Available for Sale Securities (GAAP marketable-securities bucket).
        "financial assets",
        "available for sale securities",
    ],
    "inventory": ["inventory"],
    # The sector row ONLY. An earlier alias also accepted "industrygroup",
    # which is not a sector: ``_norm`` keeps the space in "Industry Group", so
    # the spaced vendor label never matched it, but an UNSEPARATED label
    # ("IndustryGroup") did. ``fin["sector"]`` is read at :1555 and selects
    # the Altman variant at :1565. A stray financial group resolves to XLF in
    # ``altman_variant_for``, which WITHHOLDS the variant for a non-financial
    # company. An industry group must never reach the sector key.
    "sector": ["sector"],
    "roe": ["roe ttm", "roe rfy", "roettm", "roerfy"],
    "net_receivables": [
        "receivables",  # moomoo aggregate line (net of the -Accounts/Taxes/Other sub-items)
        "net receivables",
        "accounts receivable",
    ],
    "operating_cashflow": ["operating cash flow", "cash flow from operating"],
    "dividends_paid": ["cash dividends paid", "dividends paid"],
    "share_buybacks": ["repurchase of common", "share repurchase", "buyback"],
    "debt_repayment": ["repayment of debt", "debt repayment"],
    "capex": ["capital expenditure", "purchase of property", "net ppe purchase"],
}


def _norm(s: str) -> str:
    """Normalize a row label for loose matching."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _label(key: str) -> str:
    """Vendor key -> human row label, splitting snake_case and camelCase.

    Alpha Vantage's OVERVIEW payload uses camelCase (``MarketCapitalization``)
    and its statements use snake_case (``totalRevenue``); ``_norm`` does not
    insert word boundaries, so storing the raw key left ``sharesoutstanding``
    unmatched against the ``shares outstanding`` alias. Splitting on both
    boundaries makes every alias form comparable.
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", key.replace("_", " "))
    return re.sub(r"\s+", " ", spaced).strip()


def _negates(norm_label: str, key: str) -> bool:
    """True when ``norm_label`` states the NEGATION of the ``key`` alias.

    ``"total non current assets"`` contains the ``current assets`` alias and
    ``"other non operating income expenses"`` the ``operating income`` alias;
    both name the opposite item, so the alias scan must not stop there.
    """
    return any(token in norm_label and token not in key for token in _NEGATION_TOKENS)


def _match_row(rows: dict, canonical: str):
    """Return the (label, value) for the best matching row, or None.

    Aliases are tried in ``_ROW_ALIASES`` order (most specific first) and the
    first alias that matches any row wins - so ``total_debt`` prefers a
    dedicated debt row over the catch-all ``total_liabilities`` row, and
    ``revenue`` prefers an explicit ``sales`` row over the ``operating income``
    last-resort alias. A row is only eligible when its normalized label avoids
    every needle in ``_ROW_LABEL_EXCLUDES`` for the canonical item: 'ebit' is a
    substring of 'EBITDA' and the combined "Total Liabilities And Equity" line
    is neither liabilities nor debt, so those labels are skipped even though an
    alias matches them. Rows whose label starts with ``-`` are moomoo sub-item /
    contra-account breakdowns (e.g. ``-Accumulated Depreciation``, ``-Cash and
    Cash Equivalents``) and are skipped so the canonical value always comes from
    the aggregate line that precedes them.

    The scan runs TWICE. The first pass skips every label that negates the item
    (see ``_negates``), so a "Non Current" row cannot stand in for a current one
    while a plain row exists in the same payload; the second pass repeats it
    allowing them, because some items are only ever reported negated (moomoo's
    "Non-Operating Interest Expense" IS MSFT's interest expense row). Payloads
    whose rows are already correct therefore bind identically under both passes
    - the retry only ever rescues a row the first pass skipped.
    """
    excludes = _ROW_LABEL_EXCLUDES.get(canonical, ())
    for allow_negated in (False, True):
        for alias in _ROW_ALIASES.get(canonical, []):
            key = _norm(alias)
            if not key:
                continue
            for label, value in rows.items():
                if label.startswith("-"):
                    continue
                norm_label = _norm(label)
                if any(needle in norm_label for needle in excludes):
                    continue
                if key not in norm_label:
                    continue
                if not allow_negated and _negates(norm_label, key):
                    continue
                return (label, value)
    return None


def _first_number(text: str) -> float | None:
    """Parse the first number from a formatted value like '$1.23B' or '1,234'."""
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    sign = -1.0 if text.startswith("-") else 1.0
    text = text.lstrip("-+")
    multiplier = 1.0
    for suffix, mult in (("t", 1e12), ("b", 1e9), ("m", 1e6), ("k", 1e3)):
        if text.lower().endswith(suffix):
            multiplier = mult
            text = text[:-1].strip()
            break
    match = re.search(r"[-+]?[0-9][0-9,]*(\.[0-9]+)?([eE][-+]?[0-9]+)?", text)
    if not match:
        return None
    try:
        return sign * multiplier * float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _percent_fraction(text: str) -> float | None:
    """Parse a '12.34%' / '-5.2%' YoY cell into a fraction (0.1234 / -0.052).

    None for '--', 'n/a' or any unparseable cell (never 0 - a missing growth
    figure must not be confused with zero growth)."""
    if text is None:
        return None
    raw = str(text).strip().rstrip("%")
    if not raw or raw.lower() in ("--", "n/a", "na", "-"):
        return None
    try:
        return float(raw) / 100.0
    except ValueError:
        return None


def _parse_csv_statements(payload: str) -> dict:
    """Parse a yfinance-style CSV statement into {row_label: latest_value}."""
    rows = {}
    try:
        reader = csv.reader(io.StringIO(payload))
        lines = [row for row in reader if row]
    except Exception:
        return rows
    if not lines:
        return rows
    # First line is the header: first cell is the label column, rest are dates.
    for row in lines[1:]:
        if not row or not row[0]:
            continue
        label = row[0].strip()
        # yfinance financial-statement columns are newest-first (like moomoo),
        # so the FIRST numeric cell is the most recent period and the rightmost
        # is the OLDEST. Taking the rightmost cell returned the oldest fiscal
        # year as "latest", corrupting I/R, M-Score, Piotroski and every ratio
        # screen that reads a single latest value.
        value = None
        for cell in row[1:]:
            parsed = _first_number(cell)
            if parsed is not None:
                value = parsed
                break
        rows[label] = value
    return rows


def _markdown_period_tables(payload: str) -> list[tuple[str, dict]]:
    """Parse moomoo-style markdown into ``[(period_label, {row: value}), ...]``
    sorted by the period year in the ``### `` header, NEWEST first.

    Moomoo sends its statement tables newest-first (2025, 2024, ...) and a
    ``get_fundamentals`` payload concatenates the income + balance + cashflow
    statements (12 tables for 4 years); sorting by period year keeps
    "current" unambiguous regardless of ordering. A payload without period
    headers is treated as one implicit table. Each table also gains
    ``"<label> YoY"`` rows from the YoY column so the canonical growth aliases
    (revenue_yoy / eps_yoy) keep working.
    """
    tables: list[tuple[str, dict]] = []
    current_label = ""
    current: dict = {}
    for line in (payload or "").splitlines():
        line = line.strip()
        if line.startswith("### "):
            if current:
                tables.append((current_label, current))
            current_label = line[4:].strip()
            current = {}
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("Item", "---", "Items"):
            continue
        label = cells[0]
        value = _first_number(cells[1])
        if not label or value is None:
            continue
        current[label] = value
        if len(cells) >= 4 and cells[2] not in ("--", ""):
            yoy = _percent_fraction(cells[2])
            if yoy is not None:
                current[f"{label} YoY"] = yoy
    if current:
        tables.append((current_label, current))

    def _year(label: str):
        return _period_year(label)

    tables.sort(key=lambda t: _year(t[0]), reverse=True)
    return tables


def _parse_markdown_periods(payload: str) -> list[dict]:
    """Period tables as bare row dicts, newest first (see
    ``_markdown_period_tables``)."""
    return [rows for _, rows in _markdown_period_tables(payload)]


def _parse_markdown_financials(payload: str) -> dict:
    """Parse a moomoo-style markdown payload into {row_label: latest_value}.

    When the payload carries several ``### <period>`` tables (moomoo sends
    newest-first), returns the NEWEST period's table - the previous
    last-write-wins behaviour accidentally kept the OLDEST period's values.
    Handles the 4-column statement layout ("| Item | Value | YoY | QoQ |"):
    the YoY cell (fraction) is stored under ``"<label> YoY"`` so canonical
    growth fields (revenue_yoy / eps_yoy) read it directly.
    """
    tables = _parse_markdown_periods(payload)
    return tables[0] if tables else {}


def _parse_json_statements(payload: str) -> dict:
    """Parse an alpha_vantage-style JSON payload into {row_label: latest_value}."""
    rows = {}
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return rows
    if not isinstance(data, dict):
        return rows
    # Company-overview keys are single-level; statements are per-report.
    reports = data.get("annualReports") or data.get("quarterlyReports") or []
    for key, value in data.items():
        if key in ("fiscalDateEnding", "reportedCurrency", "annualReports", "quarterlyReports"):
            continue
        if isinstance(value, dict):
            continue
        if key.lower() == "sector" and isinstance(value, str) and value.strip():
            rows["Sector"] = value.strip()
            continue
        # Single-level numeric fields (MarketCapitalization, SharesOutstanding,
        # Beta, DividendYield, ...). Dropping them left market_cap/shares/beta
        # unparsed whenever Alpha Vantage served, degrading EV/earnings-yield/
        # Altman/net-net to n/a for no reason.
        parsed = _first_number(value)
        if parsed is not None:
            rows[_label(key)] = parsed
    for report in reports:
        for key, value in report.items():
            if key in ("fiscalDateEnding", "reportedCurrency"):
                continue
            parsed = _first_number(value)
            if parsed is not None and _label(key) not in rows:
                rows[_label(key)] = parsed
    return rows


def _parse_text_report(payload: str) -> dict:
    """Parse yfinance fundamentals-style text (``Label: value`` lines).

    Statement payloads repeat the same labels once per reported period and are
    ordered newest-first (Tiingo's ``statements`` endpoint returns the latest
    quarter first; yfinance fundamentals text carries one period). The FIRST
    occurrence therefore wins, matching ``_parse_csv_statements`` (newest column
    first), ``_parse_json_statements`` and ``_parse_markdown_financials``
    (newest period table); the previous last-write-wins kept the OLDEST period's
    values - the same bug already fixed for moomoo markdown.
    """
    rows = {}
    for line in payload.splitlines():
        if line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        label, _, rest = line.partition(":")
        parsed = _first_number(rest)
        if label.strip() and parsed is not None:
            rows.setdefault(label.strip(), parsed)
        elif label.strip().lower() == "sector" and rest.strip():
            # non-numeric attributes (sector/industry) are kept as strings
            rows["Sector"] = rest.strip()
    return rows


_NON_EQUITY_TOKENS = ("ETF", "ETN", "TRUST", "INDEX", "FUND")


def _is_non_equity(name: str) -> bool:
    """Best-effort flag for non-stock securities (ETFs, ETNs, funds, indices)."""
    upper = (name or "").upper()
    return any(tok in upper for tok in _NON_EQUITY_TOKENS)


def _detect_currency(payload: str) -> str:
    """Best-effort statement-currency detection from vendor payloads.

    moomoo markdown headers carry ``(FY 2025, currency: JPY)``; yfinance
    fundamentals text carries a ``Financial Currency: JPY`` line (when present);
    alpha_vantage JSON carries a ``reportedCurrency`` field. Returns ``""``
    when unknown (yfinance CSV carries no marker).
    """
    text = payload or ""
    for pattern in (
        r"currency:\s*([A-Za-z]{3})",
        r"Financial\s+Currency:\s*([A-Za-z]{3})",
        r"\"reportedCurrency\"\s*:\s*\"([A-Za-z]{3})\"",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return ""


def _total_debt_match(rows: dict):
    """Total borrowings: a dedicated total row, else long-term + short-term legs.

    The legs exist because a payload can carry only the aggregates - moomoo's
    balance sheet has "Long Term Debt and Capital Lease Obligation" and
    "Short-Term Debt and Capital Lease Obligation" and NO total row, so the
    alias scan bound ``total_debt`` to the long-term leg alone. The DCF bridge
    then charged 47.60bn of debt against 56.83bn, printing $1.22/share too much
    fair value and +29.05bn of net cash against the balance sheet's own
    +19.825bn (MSFT 2026-09-16). The sum reproduces the vendor's own Total Debt
    exactly: 47,599 + 9,227 = 56,826.
    """
    match = _match_row(rows, "total_debt")
    if match is not None:
        norm = _norm(match[0])
        if "long term" not in norm and "non current" not in norm:
            return match
    short = _match_row(rows, "short_term_debt")
    if match is not None and short is not None:
        return (f"{match[0]} + {short[0]}", match[1] + short[1])
    return match


def _match_canonical(rows: dict, key: str):
    """``_match_row`` plus the derivations no single row carries."""
    if key == "total_debt":
        return _total_debt_match(rows)
    return _match_row(rows, key)


def _flat_canonical(rows: dict) -> dict:
    """Canonical line items from a flat single-period ``{label: value}`` row
    dict (yfinance CSV, alpha_vantage JSON, fundamentals text, Finnhub)."""
    canonical = {}
    for key in _ROW_ALIASES:
        match = _match_canonical(rows, key)
        if match is not None:
            canonical[key] = match[1]
    return canonical


def _markdown_canonical(text: str) -> dict:
    """Canonical line items from moomoo-style markdown with per-period tables.

    Every table is searched for each canonical key (a ``get_fundamentals``
    payload concatenates income + balance + cashflow, so the cashflow rows
    live in later tables). "Current" is the value from the newest period that
    has the key; "prior" is the same row label from the newest OTHER table.
    Keys with both become ``{"current": .., "prior": ..}`` dicts - the Beneish
    M-Score and the Piotroski time-components read the prior period, and the
    canonical input contract in ``quantitative_scores`` already supports the
    dict form. Keys with no prior stay flat (single float), so the screener's
    other reads and the growth aliases are unaffected.
    """
    tables = _markdown_period_tables(text)
    if not tables:
        return {}
    canonical = {}
    for key in _ROW_ALIASES:
        best = None  # (year, label, value, table_index)
        for idx, (period, rows) in enumerate(tables):
            m = _match_canonical(rows, key)
            if m is None:
                continue
            year = _period_year(period)
            if best is None or year > best[0]:
                best = (year, m[0], m[1], idx)
        if best is None:
            continue
        _year, label, cur, idx = best
        prior = None
        best_p = -1
        for jdx, (period, rows) in enumerate(tables):
            if jdx == idx:
                continue
            v = rows.get(label)
            if v is None:
                # The label is synthesized for keys no single row carries
                # (`total_debt` summed from its long/short-term legs), so an
                # exact-label lookup misses it in every other table. Re-match
                # the key there instead of dropping the prior period: the
                # Piotroski deleveraging and Beneish LVGI legs both read it.
                m2 = _match_canonical(rows, key)
                v = m2[1] if m2 is not None else None
            if v is None:
                continue
            y2 = _period_year(period)
            if y2 > best_p:
                prior, best_p = v, y2
        canonical[key] = {"current": cur, "prior": prior} if prior is not None else cur
    return canonical


def _period_year(period_label: str) -> int:
    """Fiscal year parsed from a moomoo ``### `` period label (e.g. "2025/FY")."""
    m = re.search(r"(20\d{2})", period_label or "")
    return int(m.group(1)) if m else -1


_INCOME_ROW_KEYS = {
    "revenue": ("total revenue", "total operating revenue", "revenue", "sales"),
    "ebit": ("operating profit", "operating income", "ebit", "operating income loss"),
    "net_income": ("net income to common", "net income", "net profit", "profit for the period"),
}


def _match_income_row(rows: dict, needles: tuple) -> float | None:
    """First non-contra row whose label contains any needle; value via
    ``_first_number`` so display strings like ``$391.04B`` parse."""
    for label, value in rows.items():
        low = str(label).lower()
        if low.startswith("-"):
            continue  # moomoo sub-item / contra breakdowns
        if any(n in low for n in needles):
            parsed = _first_number(value)
            if parsed is not None:
                return parsed
    return None


def _income_rows_from_markdown(tables: list) -> list[dict] | None:
    """Per-period {revenue, ebit, net_income} from markdown period tables,
    newest first as returned. Rows are matched by label (e.g. moomoo's
    "Total Operating Revenue" / "Operating Profit" / "Net Income to Common").
    """
    out = []
    for period, rows in tables:
        rev = _match_income_row(rows, _INCOME_ROW_KEYS["revenue"])
        eb = _match_income_row(rows, _INCOME_ROW_KEYS["ebit"])
        ni = _match_income_row(rows, _INCOME_ROW_KEYS["net_income"])
        if rev is not None and eb is not None:
            rec = {"year": _period_year(period), "revenue": float(rev), "ebit": float(eb), "net_income": ni}
            out.append(rec)
    return out or None


def _income_rows_from_csv(payload: str) -> list[dict] | None:
    """Per-period {revenue, ebit, net_income} from a yfinance-style CSV
    (``label: {date: value}`` via the statement CSV parse). Dates sorted.
    """
    rows = _parse_csv_statement_rows(payload)
    if not rows:
        return None
    dates = sorted({d for vals in rows.values() for d in vals})
    if not dates:
        return None
    out = []
    for date in dates:
        def _pick(needles, _date=date):
            for label, vals in rows.items():
                low = str(label).lower()
                if low.startswith("-"):
                    continue
                if any(n in low for n in needles) and _date in vals:
                    return vals[_date]
            return None
        rev = _pick(_INCOME_ROW_KEYS["revenue"])
        eb = _pick(_INCOME_ROW_KEYS["ebit"])
        ni = _pick(_INCOME_ROW_KEYS["net_income"])
        if rev is not None and eb is not None:
            year = int(str(date)[:4]) if str(date)[:4].isdigit() else 0
            out.append({"year": year, "revenue": float(rev), "ebit": float(eb), "net_income": ni})
    return out or None


def income_series(payload: str) -> list[dict] | None:
    """Time-ordered (oldest->newest) annual {revenue, ebit, net_income} rows
    from an income-statement payload (moomoo markdown or yfinance CSV).

    Returns a list of dicts (oldest first) suitable for ``median_norm_ebit``
    (which reads ``revenues``/``ebits`` and only needs both per period), or
    None when <2 usable periods or no payload. Never fabricates: missing rows
    drop the period entirely, and a non-parsable payload yields None.
    """
    if not payload or str(payload).lstrip().startswith(("NO_DATA", "DATA_DISABLED", "DATA_UNAVAILABLE")):
        return None
    try:
        tables = _markdown_period_tables(payload)
    except Exception:  # noqa: BLE001
        tables = []
    if tables:
        rows = _income_rows_from_markdown(tables)
        if rows:
            rows.reverse()  # markdown is newest-first -> oldest first
            return rows
    rows = _income_rows_from_csv(payload)
    if rows:
        rows.sort(key=lambda r: r.get("_y", 0))  # CSV dates already sorted
    return rows


# --- Multi-year canonical series -------------------------------------------
#
# One producer for the per-year series the score readers already expect:
# ``growth_metrics`` reads ``roa_series`` / ``revenue_series`` for the Mohanram
# G-Score's G4/G5 legs, and the earnings-quality tool reads the cash-flow
# series for Dechow-Dichev accrual quality. Both readers existed with NO writer
# (found in the 2026-09-17 factor-model inventory): G4/G5 always reported
# "5-year ROA series unavailable (n=0)" and ``dd_aq`` was structurally n/a.
# Every period is canonicalised through ``_flat_canonical`` - the same matcher
# the flat merge uses - so a series value cannot disagree with the newest-period
# value for the same key.

#: Canonical keys a series is emitted for, in emission order. Only keys with a
#: consumer: ``revenue``/``roa`` feed the G-Score, the other three feed
#: Dechow-Dichev (accruals = (NI - CFO) / total assets).
SERIES_KEYS: tuple = ("revenue", "net_income", "total_assets", "operating_cashflow")

#: SEC XBRL row label -> canonical series key, for ``sec_annual_series``. The
#: labels are ``sec_edgar._TAG_MAP``'s, so the two files must move together.
_SEC_SERIES_KEYS: dict = {
    "Revenue": "revenue",
    "Net income (loss)": "net_income",
    "Total assets": "total_assets",
    "Operating cash flow": "operating_cashflow",
    "Diluted EPS": "diluted_eps",
    "Operating income": "operating_income",
    "D&A": "d_and_a",
    "Capex (-)": "capex",
    "Gross profit": "gross_profit",
    "Total liabilities": "total_liabilities",
    "Stockholders equity": "stockholders_equity",
    "Cash & equivalents": "cash_and_equivalents",
}


def _period_token(label: str) -> str:
    """Short period token from a table header or a CSV date column.

    ``"Income Statement (2025/FY)"`` -> ``"2025/FY"``; a bare date stays as it
    is. Only used to label a series in provenance, so it never invents a period
    the payload does not state.
    """
    text = str(label or "").strip()
    if text.endswith(")") and "(" in text:
        return text[text.rindex("(") + 1 : -1].strip() or text
    return text


def _period_canonicals(payload: str) -> list:
    """Per-period ``(year, period_token, canonical)`` from one statement
    payload, OLDEST first.

    Markdown (moomoo) sends one table per STATEMENT per period - a
    ``get_fundamentals`` payload concatenates income + balance + cashflow for
    four years, i.e. 12 tables for 4 periods - so tables are MERGED BY FISCAL
    YEAR into one canonical dict per year (the same "search every table for the
    key" rule ``_markdown_canonical`` applies to the newest period). The
    yfinance/tiingo CSV shape resolves to one canonical dict per date column.

    Both shapes read their rows through ``_flat_canonical``, the same matcher
    the merged payload uses, so a series value cannot disagree with the
    newest-period value for the same key.
    """
    text = (payload or "").strip()
    if not text or text.startswith("NO_DATA") or text.startswith("DATA_"):
        return []
    by_year: dict = {}
    token_by_year: dict = {}
    tables = _markdown_period_tables(text)
    if tables:
        for period, rows in tables:
            year = _period_year(period)
            canon = _flat_canonical(rows)
            if year <= 0 or not canon:
                continue
            slot = by_year.setdefault(year, {})
            for key, value in canon.items():
                slot.setdefault(key, value)
            token_by_year.setdefault(year, _period_token(period))
    else:
        rows = _parse_csv_statement_rows(text)
        for date in sorted({d for vals in rows.values() for d in vals}):
            year = int(str(date)[:4]) if str(date)[:4].isdigit() else 0
            if year <= 0:
                continue
            canon = _flat_canonical({k: v[date] for k, v in rows.items() if date in v})
            if not canon:
                continue
            by_year.setdefault(year, canon)
            token_by_year.setdefault(year, str(date))
    return [(year, token_by_year[year], by_year[year]) for year in sorted(by_year)]


def _series_from_payload(payload: str) -> dict:
    """Complete per-year series ONE payload supports (oldest -> newest).

    ``{key_series: {"values": [...], "years": [...], "periods": [...]}}``. A key
    missing in ANY period of this payload is omitted rather than zero-filled - a
    series with a hole is not a series.
    """
    periods = _period_canonicals(payload)
    if len(periods) < 2:
        return {}
    years = [year for year, _label, _canon in periods]
    labels = [label for _year, label, _canon in periods]
    out: dict = {}
    for key in SERIES_KEYS:
        vals = [canon.get(key) for _year, _label, canon in periods]
        if all(v is not None for v in vals):
            out[f"{key}_series"] = {
                "values": [float(v) for v in vals],
                "years": list(years),
                "periods": list(labels),
            }
    return out


def annual_series(payloads) -> dict:
    """Multi-year canonical series stacked from the statement payloads.

    ``payloads`` is an ordered iterable of raw statement texts (any shape
    ``_canonicalize`` accepts). Each payload is stacked INDEPENDENTLY and the
    longest complete series wins per key - the values of one key are never
    spliced across payloads, because a vendor switch mid-series would join
    periods that need not share a scale or a currency (the mix the ``currency``
    guard exists to refuse).

    ``roa_series`` is then derived from the chosen net-income and total-asset
    series, ALIGNED BY FISCAL YEAR and on beginning-of-year assets - the
    convention ``growth_metrics`` uses for the ROA level (NI / prior-year total
    assets), so the level and the variance of the series cannot disagree. That
    join can cross payloads, exactly as the level ROA already does in
    ``enrich_screen_ratios`` (income and balance arrive as separate payloads on
    the yfinance path); a year without a prior-year balance sheet is skipped,
    so the ROA series is shorter than the revenue series and never indexed by
    position.

    Returns ``{key_series: {"values": [...], "years": [...], "periods": [...]}}``;
    empty when no payload carries two complete periods.

    This is the **vendor** path. ``sec_annual_series`` is its SEC XBRL sibling -
    the same shape, built from the filer's 10-K history, which reaches back
    further than a vendor statement does (those carry ~4-5 annual periods). The
    caller merges the two **per key by keeping whichever series is longer** and
    never splices them, the same one-series-per-key rule this function applies
    across payloads; the SEC leg is skipped for a non-USD filer, whose XBRL
    facts are not on the canonical scale.
    """
    best: dict = {}
    for payload in payloads or ():
        for key, entry in _series_from_payload(payload).items():
            if len(entry["values"]) > len((best.get(key) or {}).get("values") or ()):
                best[key] = entry
    _add_roa(best)
    return best


def _add_roa(best: dict) -> None:
    """Attach ``roa_series`` to a stacked series dict, in place.

    Derived from the chosen net-income and total-asset series, ALIGNED BY FISCAL
    YEAR and on beginning-of-year assets - the convention ``growth_metrics`` uses
    for the ROA level (NI / prior-year total assets), so the level and the
    variance of the series cannot disagree. That join can cross payloads, exactly
    as the level ROA already does in ``enrich_screen_ratios`` (income and balance
    arrive as separate payloads on the yfinance path); a year without a prior-year
    balance sheet is skipped, so the ROA series is shorter than the revenue series
    and never indexed by position. One implementation: both the vendor path and
    the SEC XBRL path read this.
    """
    ni = best.get("net_income_series")
    ta = best.get("total_assets_series")
    if not (ni and ta):
        return
    ta_by_year = dict(zip(ta["years"], ta["values"], strict=False))
    roa_years, roa_vals, roa_labels = [], [], []
    ni_by_year = dict(zip(ni["years"], ni["values"], strict=False))
    label_by_year = dict(zip(ni["years"], ni["periods"], strict=False))
    for year in sorted(ni_by_year):
        prior = ta_by_year.get(year - 1)
        if prior:
            roa_years.append(year)
            roa_vals.append(ni_by_year[year] / prior)
            roa_labels.append(label_by_year.get(year, str(year)))
    if len(roa_vals) >= 2:
        best["roa_series"] = {
            "values": roa_vals,
            "years": roa_years,
            "periods": roa_labels,
        }


def sec_annual_series(ticker: str, years: int = 15) -> dict:
    """``annual_series``-shaped series from the SEC XBRL 10-K history.

    The vendor statements carry ~4-5 annual periods; a filer's XBRL history goes
    back to its adoption (mostly 2009-2011 for large filers), which is what clears
    the 5-period bar the Mohanram G4/G5 legs and the CAGR family need - the reason
    those legs printed "5-year ROA series unavailable (n=0)" wherever the data
    existed upstream. P0-1's consumer half.

    Values are **as-reported 10-K figures in USD**, a different basis from the
    vendor's normalised statements, so a caller must not splice the two: the merge
    in ``fetch_ticker`` takes the LONGER series per key and names the source.
    ``EBITDA`` and ``FCF`` are derived here (``operating_income + d_and_a`` and
    ``operating_cashflow - capex``) and labelled derived - neither has a us-gaap
    tag, and fetching one would be a fabrication.

    Returns ``{}`` for a non-US ticker, a pre-XBRL filer or any failure: the series
    is additive and must never fail a run (the same contract the rendered leaf's
    ``NoMarketDataError`` is caught under).
    """
    try:
        from .sec_edgar import financial_history_series

        payload = financial_history_series(ticker, years=years)
    except Exception as exc:  # noqa: BLE001 - optional depth, never fatal
        logger.debug("%s SEC XBRL series: %s", ticker, exc)
        return {}
    out: dict = {}
    for label, by_end in (payload.get("series") or {}).items():
        key = _SEC_SERIES_KEYS.get(label)
        if key is None:
            continue
        # Longest run of CONSECUTIVE fiscal years: a series with a hole is not a
        # series (the same rule ``_series_from_payload`` applies to a payload's
        # own periods), so a tag that skips a year contributes only its longest
        # unbroken stretch rather than a misaligned array.
        run = _longest_year_run(by_end)
        if len(run) >= 2:
            out[f"{key}_series"] = {
                "values": [float(v) for _y, _e, v in run],
                "years": [y for y, _e, _v in run],
                "periods": [e for _y, e, _v in run],
            }
    _add_derived_series(out)
    _add_roa(out)
    return out


def _longest_year_run(by_end: dict) -> list:
    """``[(year, end, value)]`` for the longest run of consecutive fiscal years."""
    rows = sorted((int(str(end)[:4]), str(end), val) for end, val in (by_end or {}).items())
    best: list = []
    run: list = []
    for row in rows:
        if run and row[0] == run[-1][0] + 1:
            run.append(row)
        else:
            run = [row]
        if len(run) > len(best):
            best = list(run)
    return best


def _add_derived_series(out: dict) -> None:
    """Attach the DERIVED annual series (EBITDA, FCF), labelled as derived.

    Neither has a us-gaap tag: EBITDA is ``operating_income + d_and_a`` and FCF is
    ``operating_cashflow - capex`` (capex is filed positive). A year missing either
    operand is dropped, never zero-filled.
    """
    oi, da = out.get("operating_income_series"), out.get("d_and_a_series")
    if oi and da:
        da_by_year = dict(zip(da["years"], da["values"], strict=False))
        vals, yrs, per = [], [], []
        for year, value, period in zip(oi["years"], oi["values"], oi["periods"], strict=False):
            if da_by_year.get(year) is not None:
                vals.append(value + da_by_year[year])
                yrs.append(year)
                per.append(period)
        if len(vals) >= 2:
            out["ebitda_series"] = {"values": vals, "years": yrs, "periods": per, "derived": True}
    ocf, capex = out.get("operating_cashflow_series"), out.get("capex_series")
    if ocf and capex:
        cx_by_year = dict(zip(capex["years"], capex["values"], strict=False))
        vals, yrs, per = [], [], []
        for year, value, period in zip(ocf["years"], ocf["values"], ocf["periods"], strict=False):
            if cx_by_year.get(year) is not None:
                vals.append(value - cx_by_year[year])
                yrs.append(year)
                per.append(period)
        if len(vals) >= 2:
            out["fcf_series"] = {"values": vals, "years": yrs, "periods": per, "derived": True}


def _parse_csv_statement_rows(payload: str) -> dict:
    """yfinance-style CSV -> {label: {date: value}} (header date columns)."""
    import io as _io

    rows = {}
    try:
        reader = csv.reader(_io.StringIO(payload or ""))
        lines = [r for r in reader if r and not (r[0] or "").startswith("#")]
    except Exception:
        return rows
    if not lines:
        return rows
    header = None
    data_start = 0
    for idx, row in enumerate(lines):
        if not (row[0] or "").strip():
            header = row[1:]
            data_start = idx + 1
            break
    if header is None:
        return rows
    for row in lines[data_start:]:
        if not row or not (row[0] or "").strip():
            continue
        label = row[0].strip()
        vals = {}
        for i, cell in enumerate(row[1:]):
            parsed = _first_number(cell)
            if parsed is not None and i < len(header):
                vals[str(header[i])[:10]] = parsed
        if vals:
            rows[label] = vals
    return rows


def _latest(v):
    """Current-period value of a canonical item (flat float or a
    ``{"current": .., "prior": ..}`` dict)."""
    if isinstance(v, dict):
        return v.get("current", v.get("value"))
    return v


def _prior(v):
    """Prior-period value of a canonical item (dict with a ``prior`` key)."""
    return v.get("prior") if isinstance(v, dict) else None


def sane_eps_yoy(fin: dict) -> float | None:
    """EPS YoY (fraction) with a degenerate-base guard.

    A |YoY| beyond +/-300% is almost always a denominator artifact (the
    prior-year EPS base was near $0), not an economic signal - e.g. the
    -2280% figure the decline-driver tool raised on QCOM 2026-09-07.
    Trust the vendor ratio only when it is within that bound; otherwise
    recompute from the current/prior EPS pair and return None (n/a) when
    no safe base exists. Never returns a meaningless magnitude.
    """
    v = _latest(fin.get("eps_yoy"))
    if v is not None and abs(v) <= 3.0:
        return v
    cur = _latest(fin.get("eps"))
    prior = _prior(fin.get("eps"))
    if cur is None or prior is None or prior == 0 or abs(prior) < 0.01:
        return None
    return (cur - prior) / prior


def sane_revenue_yoy(fin: dict) -> float | None:
    """Revenue YoY (fraction) with the same degenerate-base guard as EPS.

    Same artifact class as ``sane_eps_yoy`` (MSFT 2026-09-08: a vendor
    percent-scaled 17.79 rendered as +1779%). A |YoY| beyond +/-300% is a
    denominator/units artifact, not a signal; recompute from the current/prior
    revenue pair and return None (n/a) when no safe base exists.

    Additionally guards the percent-scaled case below 300%: a raw value in
    (0.3, 3.0] (i.e. 30-300% claimed YoY) is recomputed from the revenue pair
    and the pair's (ground-truth) value is preferred — so a percent-scaled
    +1.88 (QCOM 2026-09-08 rendered 188% vs the true +1.88%) resolves to the
    pair's ~1.9%, not the 100x artifact.
    """
    v = _latest(fin.get("revenue_yoy"))
    cur = _latest(fin.get("revenue"))
    prior = _prior(fin.get("revenue"))
    pair = None
    if cur is not None and prior is not None and prior != 0 and abs(prior) >= 0.01:
        pair = (float(cur) - float(prior)) / float(prior)
    if v is not None and abs(v) <= 3.0:
        if pair is not None:
            # The pair is ground truth; prefer it whenever the vendor value is
            # ambiguous (percent-scaled) OR even when sane — it is always the
            # most defensible read. Only fall back to the vendor value when no
            # revenue pair exists.
            return pair
        if 0.3 < abs(float(v)) <= 3.0 and abs(float(v)) > 1.0:
            # No pair to arbitrate, but >100% YoY is implausible for revenue
            # without a pair: almost certainly percent-scaled (1.88 == 1.88%).
            return float(v) / 100.0
        return v
    return pair


def _ratio_num(n, d):
    """n/d guarded: None when either side missing or the denominator is 0."""
    if n is None or d is None:
        return None
    try:
        d = float(d)
        n = float(n)
    except (TypeError, ValueError):
        return None
    if d == 0:
        return None
    return n / d


def enrich_screen_ratios(fin: dict) -> None:
    """Derive the ratio inputs the Piotroski F-Score needs but no vendor row
    provides directly (``roa``, ``leverage``, ``current_ratio``,
    ``gross_margin``, ``asset_turnover``, ``shares_issued``), including their
    prior-period values, and store them back into ``fin`` in place.

    Every input is pure-computed from the canonical financials the chain
    already fetches (net income, total assets, equity, current assets /
    liabilities, revenue, cogs, shares), with current+prior so the F-Score's
    period-over-period checks can run. A missing side leaves the sub-ratio
    unset (n/a) - never fabricated. Returns None; mutates ``fin`` only.
    """

    def _pair(n_key, d_key):
        n, n_p = _latest(fin.get(n_key)), _prior(fin.get(n_key))
        d, d_p = _latest(fin.get(d_key)), _prior(fin.get(d_key))
        cur = _ratio_num(n, d)
        prv = _ratio_num(n_p, d_p)
        if cur is None and prv is None:
            return None
        return {"current": cur, "prior": prv}

    roa = _pair("net_income", "total_assets")
    if roa is not None:
        fin["roa"] = roa
    lev = _pair("total_assets", "total_equity")
    if lev is not None:
        fin["leverage"] = lev
    cr = _pair("current_assets", "current_liabilities")
    if cr is not None:
        fin["current_ratio"] = cr
    rev = _latest(fin.get("revenue"))
    cog = _latest(fin.get("cogs")) or _latest(fin.get("cost_of_revenue"))
    rev_p, cog_p = _prior(fin.get("revenue")), (_prior(fin.get("cogs")) or _prior(fin.get("cost_of_revenue")))
    gm = _ratio_num((rev - cog) if (rev is not None and cog is not None) else None, rev)
    gm_p = _ratio_num((rev_p - cog_p) if (rev_p is not None and cog_p is not None) else None, rev_p)
    if gm is not None or gm_p is not None:
        fin["gross_margin"] = {"current": gm, "prior": gm_p}
    at = _pair("revenue", "total_assets")
    if at is not None:
        fin["asset_turnover"] = at
    sh, sh_p = _latest(fin.get("shares")), _prior(fin.get("shares"))
    if sh is not None:
        # Net share change proxy: <= 0 means shares reduced (buyback) -> +
        # the Piotroski share-issuance sub-score.
        fin["shares_issued"] = (
            (sh - sh_p) if sh_p is not None else sh
        )



def _canonicalize(payload: str) -> dict:
    """Turn a vendor payload string into a canonical line-item dict.

    Works for yfinance CSV (``get_balance_sheet`` etc.), moomoo markdown
    (``get_fundamentals``), alpha_vantage JSON (``get_fundamentals``) and
    yfinance fundamentals text (``get_fundamentals``). Moomoo markdown keeps
    the prior period as ``{current, prior}`` dicts for the ratio screens. A
    ``currency`` key is added when the payload states a non-default reporting
    currency, so USD-only metrics can refuse to mix currencies.
    """
    text = (payload or "").strip()
    if not text or text.startswith("NO_DATA") or text.startswith("DATA_"):
        return {}
    # yfinance statement payloads prepend ``# Data retrieved on: ...`` comment
    # header lines before a CSV body. Those comment lines contain a colon, so a
    # naive ``":"`` check would win and the CSV body would be mis-routed to
    # _parse_text_report (empty canonical dict; all fundamentals degrade to n/a).
    # Use the FULL text for branch selection (moomoo markdown keeps its ``##`` /
    # ``###`` period headers), but ONLY count ``":"`` lines that are not ``#``
    # comments, so a comma-separated body falls through to the CSV branch.
    def _is_comment(ln: str) -> bool:
        return ln.lstrip().startswith("#") or not ln.strip()

    if text.lstrip().startswith("{"):
        rows = _parse_json_statements(text)
        canonical = _flat_canonical(rows)
    elif any(ln.lstrip().startswith("|") for ln in text.splitlines()):
        canonical = _markdown_canonical(text)
    elif any(":" in ln and not _is_comment(ln) for ln in text.splitlines()):
        canonical = _flat_canonical(_parse_text_report(text))
    else:
        rows = _parse_csv_statements(text)
        canonical = _flat_canonical(rows)
    currency = _detect_currency(text)
    if currency and currency != "USD":
        canonical["currency"] = currency
    return canonical


# ---------------------------------------------------------------------------
# Watchlist construction
# ---------------------------------------------------------------------------


def _payload_period(payload: str) -> str | None:
    """The newest period a statement/fundamentals payload describes, or None.

    CSV shape (yfinance/tiingo): the header row's first non-empty cell is the
    newest period (``,2026-07-31,2026-04-30,...``). Markdown shape (moomoo):
    the first ``### <label>`` period header. This exists so a derived number
    can STATE its basis - a figure whose period cannot be established is
    reported as unlabelled rather than labelled wrongly (NVDA 2026-09-12: the
    ratio block mixed an annual P/E with quarterly balance-sheet rows and said
    nothing about either).
    """
    text = (payload or "").strip()
    if not text:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if "," in stripped:
            cells = [c.strip() for c in stripped.split(",")]
            if not cells[0] and len(cells) > 1 and cells[1]:
                return cells[1][:10]
            continue
        break
    match = re.search(r"^###\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


#: Payload period kinds that CONTRADICT the basis a vendor was asked for. Only
#: explicit, machine-readable labels count: a bare ISO date states no kind, so
#: it never flags. Diffing every period on every payload would instead flag
#: intraday market movement as loudly as a mislabelled statement.
_CONTRADICTING_KINDS = {
    "annual": ("quarterly", "ttm"),
    "quarterly": ("annual", "ttm"),
}
_QUARTER_RE = re.compile(r"\bq[1-4]\b")


def _period_kind(period: str | None) -> str:
    """``annual`` / ``quarterly`` / ``ttm`` / ``unstated`` for a period token.

    Recognizes the labels the chains actually emit - moomoo's ``2025/FY`` /
    ``2026/Q2`` markdown headings and ``### Income Statement (FY 2025)``
    style headers, alpha_vantage TTM columns - and refuses to guess for
    yfinance's bare date headers, which state no kind at all.
    """
    token = (period or "").strip().lower()
    if not token:
        return "unstated"
    if "ttm" in token or "trailing" in token:
        return "ttm"
    if "fy" in token or "annual" in token:
        return "annual"
    if _QUARTER_RE.search(token) or "quarter" in token:
        return "quarterly"
    return "unstated"


def _basis_conflict(basis: str, kind: str) -> bool:
    """True when a payload's observed kind contradicts the requested basis."""
    return kind in _CONTRADICTING_KINDS.get(basis, ())


def _basis_entry(source: str, basis: str, payload: str | None) -> dict:
    """Provenance record for one absorbed payload.

    ``basis`` is what the merge ASKED the vendor for, ``period`` is what the
    payload says, ``observed_kind`` classifies that period and
    ``basis_conflict`` is the pair that proves a mismatch. Until this existed
    both statement pulls were stamped a flat ``annual`` whatever came back -
    how the AMZN 2026-09-14 report merged FY-annual rows with TTM quarters
    (EV/EBIT 32.79 -> -30551.06) with nothing recording the disagreement.
    """
    period = _payload_period(payload) if payload else None
    kind = _period_kind(period)
    return {
        "source": source,
        "basis": basis,
        "period": period,
        "observed_kind": kind,
        "basis_conflict": _basis_conflict(basis, kind),
    }


def trailing_twelve_months(ticker: str, curr_date: str, periods: int = 4) -> dict:
    """Sum the newest ``periods`` quarters of the FLOW line items (TTM).

    One producer for a trailing-twelve-month total. Every key requires FULL
    coverage - all ``periods`` columns present - before it is reported, because
    a partial window would present three quarters as a year (NVDA 2026-09-12:
    the ratio block's P/E used FY2026 ANNUAL net income, 43.90x, while the TTM
    basis was 27.63x, and nothing said which). Keys without coverage are
    ABSENT from the result, never zero-filled.

    Only the quarterly CSV shape is summed: a vendor whose payload carries one
    period per table (moomoo markdown, with its own YoY/QoQ columns) returns
    ``source: None`` and the caller must degrade honestly rather than invent a
    window.
    """
    flows = {
        "revenue": "revenue",
        "operating_income": "operating_income",
        "net_income": "net_income",
        "eps": "eps",
        "operating_cashflow": "operating_cashflow",
        "capex": "capex",
        "dividends_paid": "dividends_paid",
    }
    out: dict = {"periods": [], "source": None, "complete": False}
    merged: dict[str, dict] = {}
    for method in ("get_income_statement", "get_cashflow"):
        try:
            payload = route_to_vendor(method, ticker, "quarterly", curr_date)
        except Exception as exc:  # noqa: BLE001 - vendor chain already degrades
            logger.warning("%s %s (quarterly, TTM): %s", ticker, method, exc)
            continue
        try:
            rows = _parse_csv_statement_rows(payload)
        except Exception as exc:  # noqa: BLE001 - a malformed payload is not fatal
            logger.warning("%s %s (quarterly, TTM) unparsed: %s", ticker, method, exc)
            rows = {}
        if rows:
            merged.update(rows)
            if out["source"] is None:
                out["source"] = f"{method} (quarterly)"
    if not merged:
        return out
    for canonical, suffix in flows.items():
        found = _match_row(merged, canonical)
        if not found:
            continue
        series = found[1] if isinstance(found[1], dict) else {}
        dated = sorted(
            ((str(day)[:10], float(val)) for day, val in series.items() if val is not None),
            reverse=True,
        )
        if len(dated) < periods:
            continue
        window = dated[:periods]
        out[f"{suffix}_ttm"] = float(sum(val for _, val in window))
        if suffix == "revenue":
            out["periods"] = [day for day, _ in window]
    # "complete" = a full ``periods``-quarter window was established AND at
    # least one flow key was summed from it. Per-key coverage is enforced
    # above, so this flag only says whether the window itself was usable.
    out["complete"] = bool(out["periods"]) and any(k.endswith("_ttm") for k in out)
    return out


def fetch_ticker(
    ticker: str,
    curr_date: str,
    *,
    with_provenance: bool = False,
    with_sec_series: bool = False,
):
    """Pull the canonical line items for one ticker via the vendor chain.

    ``with_provenance=True`` returns ``(canonical, provenance)`` where
    provenance maps every recorded key to ``{source, basis, period,
    observed_kind, basis_conflict}`` - the merge below is last-writer-wins
    across up to four vendor payloads, so without this a derived ratio cannot
    state which period or vendor it came from (that silence is what let one
    NVDA report quote an annual P/E beside quarterly balance-sheet rows,
    2026-09-12).

    ``basis`` is what the merge requested and ``observed_kind`` what the
    payload's own newest period states; ``basis_conflict`` is True when those
    two disagree (an annual request answered with a quarterly or TTM payload),
    which is the AMZN 2026-09-14 signature. A payload whose period states no
    kind (a bare date header) is never flagged as a conflict.
    """
    canonical = {}
    provenance: dict[str, dict] = {}
    payloads: list = []

    def absorb(payload: str, source: str, basis: str) -> None:
        got = _canonicalize(payload)
        entry = _basis_entry(source, basis, payload)
        if entry["basis_conflict"]:
            logger.warning(
                "%s %s: newest period %r (%s) contradicts the requested %s basis; "
                "recording basis_conflict on %d key(s)",
                ticker, source, entry["period"], entry["observed_kind"], basis, len(got),
            )
        canonical.update(got)
        payloads.append(payload)
        for key in got:
            provenance[key] = dict(entry)

    # Fundamentals carries market cap (yfinance info / alpha_vantage overview).
    try:
        fund = route_to_vendor("get_fundamentals", ticker, curr_date)
        absorb(fund, "get_fundamentals", "info")
    except Exception as exc:  # noqa: BLE001 - vendor chain already degrades
        logger.warning("%s fundamentals: %s", ticker, exc)
    # The cash-flow statement owns ``operating_cashflow`` (P/CF) and ``capex``
    # (P/FCF), the two canonical inputs ``ratios.compute_ratios`` declares but
    # which no other payload on this path carries: without them both ratios are
    # None for every name (measured 2026-09-24: P/CF present 0/30 on the deepest
    # decliners, while market cap, P/E and P/B were 30/30).
    #
    # Filled from a WHITELIST, and only where the key is missing - not a blanket
    # absorb(). absorb() is last-writer-wins over loosely-matched row labels, and
    # this payload also carries net income, D&A, cash and debt legs: absorbing it
    # moved AAPL's EV until "equity value is not positive: debt exceeds enterprise
    # value" and failed six screens (test_analysis_tools, test_growth_screens,
    # test_v2_v5_wiring, 2026-09-24). Two keys in, nothing else can move.
    try:
        cf = route_to_vendor("get_cashflow", ticker, "annual", curr_date)
        cf_canon = _canonicalize(cf)
        cf_entry = _basis_entry("get_cashflow", "annual", cf)
        for key in ("operating_cashflow", "capex"):
            if key not in canonical and cf_canon.get(key) is not None:
                canonical[key] = cf_canon.get(key)
                provenance[key] = dict(cf_entry)
    except Exception as exc:  # noqa: BLE001 - vendor chain already degrades
        logger.warning("%s get_cashflow: %s", ticker, exc)
    for method in ("get_balance_sheet", "get_income_statement"):
        try:
            stmt = route_to_vendor(method, ticker, "annual", curr_date)
            absorb(stmt, method, "annual")
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s %s: %s", ticker, method, exc)
    # Finnhub basic financials (free tier, key-gated): a single call fills the
    # growth / ROE screens when the key is present (fills in eps/revenue YoY
    # and ROE where the statement chain lacks them). Only ever fills gaps -
    # an existing canonical value is never overwritten. Calls the vendor
    # directly (Finnhub-specific, not part of the fundamental_data chain).
    try:
        from tradingagents.dataflows.finnhub import get_basic_financials_finnhub

        bf = get_basic_financials_finnhub(ticker, curr_date)
        bf_canon = _canonicalize(bf)
        for k in ("eps_yoy", "revenue_yoy", "roe", "market_cap", "beta"):
            if k not in canonical and bf_canon.get(k) is not None:
                canonical[k] = bf_canon.get(k)
                # Finnhub's own payload period, classified the same way as the
                # statement pulls so one reader handles every entry.
                provenance[k] = _basis_entry("finnhub basic financials", "vendor TTM/annual", bf)
    except Exception as exc:  # noqa: BLE001
        logger.debug("%s finnhub basic financials: %s", ticker, exc)
    # Guard: a cash figure larger than total assets means a wrong-row match.
    ca_ = _latest(canonical.get("cash"))
    ta_ = _latest(canonical.get("total_assets"))
    if ca_ is not None and ta_ is not None and ca_ > ta_:
        canonical["cash"] = None
        provenance["cash"] = {
            "source": "guard",
            "basis": "nulled (cash exceeded total assets)",
            "period": None,
            "observed_kind": "unstated",
            "basis_conflict": False,
        }
    # Currency heuristic for ADRs: yfinance reports statements in the local
    # currency (e.g. JPY) with no marker in the CSV, while market cap arrives
    # in USD. A total-assets / market-cap ratio above 1000x only occurs when
    # currencies are mixed (e.g. 303T JPY assets vs 36B USD market cap) - flag
    # it so the USD-only metrics refuse to mix.
    if canonical.get("currency") is None:
        mc = _latest(canonical.get("market_cap"))
        ta = _latest(canonical.get("total_assets"))
        if mc and ta and ta / mc > 1000:
            canonical["currency"] = "non_usd"
    # Multi-year series (one producer: ``annual_series``). Attached only when a
    # payload carries two complete periods, so a reader's "n=0" reason stays
    # honest when the chain has no history. The provenance row names the period
    # span and re-uses the payload-kind classifier: a series built from a
    # quarterly payload while ``annual`` was requested flags a conflict here
    # rather than printing as a clean annual series.
    for key, entry in annual_series(payloads).items():
        vals = entry["values"]
        labels = entry["periods"]
        kind = _period_kind(labels[-1] if labels else None)
        canonical[key] = vals
        provenance[key] = {
            "source": "derived",
            "basis": f"annual series, {len(vals)} period(s), oldest -> newest",
            "period": f"{labels[0]} .. {labels[-1]}" if len(labels) > 1 else (labels[0] if labels else None),
            "observed_kind": kind,
            "basis_conflict": _basis_conflict("annual", kind),
        }
    # Deeper annual series from the SEC XBRL 10-K history (P0-1): the vendor
    # statements carry ~4-5 periods, a filer's XBRL history goes back to its
    # adoption, and the 5-period legs (G4/G5, the CAGR family, Dechow-Dichev's
    # 8-period accrual window) need the depth. **Opt-in** (``with_sec_series``):
    # it costs one EDGAR request and the figures are as-reported USD, so the
    # leaves that need the depth ask for it and every other caller keeps the
    # hermetic vendor path it has today.
    # The LONGER series wins PER KEY and the source is named - the two are
    # different bases (as-reported vs normalised) and are never spliced. Skipped
    # for a non-USD filer, because the XBRL figures are USD-only and mixing them
    # is the hazard the currency guard exists to refuse.
    if with_sec_series and canonical.get("currency") != "non_usd":
        for key, entry in sec_annual_series(ticker).items():
            if len(entry["values"]) <= len(canonical.get(key) or ()):
                continue
            labels = entry["periods"]
            canonical[key] = entry["values"]
            provenance[key] = {
                "source": "sec_xbrl",
                "basis": (
                    f"SEC XBRL 10-K series, {len(entry['values'])} period(s), "
                    "oldest -> newest"
                    + (" (derived)" if entry.get("derived") else "")
                ),
                "period": f"{labels[0]} .. {labels[-1]}" if len(labels) > 1 else (labels[0] if labels else None),
                "observed_kind": "annual",
                "basis_conflict": False,
            }
    # Derive working capital when both sides are available (Altman Z needs it).
    if "working_capital" not in canonical:
        ca = _latest(canonical.get("current_assets"))
        cl = _latest(canonical.get("current_liabilities"))
        if ca is not None and cl is not None:
            canonical["working_capital"] = ca - cl
            provenance["working_capital"] = {
                "source": "derived",
                "basis": "current_assets - current_liabilities",
                "period": (provenance.get("current_assets") or {}).get("period"),
                # Inherited from the operands: the derivation adds no basis of
                # its own, so it inherits theirs (including any conflict).
                "observed_kind": (provenance.get("current_assets") or {}).get(
                    "observed_kind", "unstated"
                ),
                "basis_conflict": bool(
                    (provenance.get("current_assets") or {}).get("basis_conflict")
                ),
            }
    if with_provenance:
        return canonical, provenance
    return canonical


def _usd_consistent(fin: dict) -> bool:
    """True when EV-family screens can mix figures from this ticker.

    moomoo reports ADR statements in the underlying currency (e.g. JPY) while
    market cap arrives in USD - mixing them produces nonsense EV (e.g. JPY cash
    68T minus a USD 36B market cap). Refuse the USD-only metrics unless the
    statements are USD (or currency is unknown/yfinance-style) *and* the
    asset/market-cap scale looks sane.
    """
    if fin.get("currency") not in (None, "", "USD"):
        return False
    mc = _latest(fin.get("market_cap"))
    ta = _latest(fin.get("total_assets"))
    # Only a currency mix produces assets >1000x the market cap.
    return not (mc and ta and ta / mc > 1000)


def _r3_flag(name: str, default: bool = False) -> bool:
    """Read an enable_* flag from the live config (never raises).

    The round-3 S1/S2 rows are additive and default-off: with the gate off the
    screen row and the trap verdict keep exactly their previous shape.
    """
    try:
        from tradingagents.dataflows.config import get_config

        return bool((get_config() or {}).get(name, default))
    except Exception:  # noqa: BLE001 - a config read must never break a screen
        return default


def screen_ticker(ticker: str, fin: dict) -> dict:
    """Compute every screen for one ticker's canonical items."""
    # Derive the ratio inputs the Screens need that no vendor row provides
    # directly (roa / leverage / current_ratio / gross_margin / asset_turnover /
    # shares_issued), so the Piotroski F-Score computes on the vendor chain.
    enrich_screen_ratios(fin)
    usd = _usd_consistent(fin)
    ev = enterprise_value(fin) if usd else None
    am = acquirers_multiple(fin) if usd else None
    ey = earnings_yield(fin) if usd else None
    m_score = beneish_m_score(fin)
    z_score = altman_z_score(fin) if usd else None
    f_score = piotroski_f_score(fin)
    # Round-3 S1/S2 (gated): the Altman variant + its distress zone, and the
    # F-Score's paper band. Both are render-only extras: with the gates off the
    # row carries neither key and `trap_verdict` receives neither argument, so
    # the screen output is byte-identical to before. The zone follows the
    # SELECTED variant (Z'' for a non-manufacturer), which is why it is not
    # tied to the USD-consistency check the original market-cap Z uses.
    sector = fin.get("sector")
    z_variant = z_zone = f_band = None
    if _r3_flag("enable_altman_variants"):
        try:
            from tradingagents.dataflows.quantitative_scores import (
                altman_variant,
                altman_variant_for,
                altman_zone,
            )

            asset = altman_variant_for(ticker=ticker, sector=sector, fin=fin)
            variant = asset.get("variant")
            if variant:
                read = altman_variant(fin, variant)
                if read and read.get("value") is not None:
                    z_variant = variant
                    z_zone = altman_zone(read["value"], variant)
        except Exception:  # noqa: BLE001 - an advisory row must not break the screen
            z_variant = z_zone = None
    if _r3_flag("enable_f_score_detail"):
        try:
            from tradingagents.dataflows.quantitative_scores import (
                piotroski_f_score_detailed,
            )

            f_band = (piotroski_f_score_detailed(fin, sector=sector) or {}).get("band")
        except Exception:  # noqa: BLE001 - an advisory row must not break the screen
            f_band = None
    # Quality rows (informational): Novy-Marx gross profitability and
    # Hirshleifer et al. net operating assets. They feed the watchlist columns
    # only - no score, ranking or filter reads them.
    gp_a_row = gross_profitability(fin)
    noa_row = net_operating_assets(fin)
    # Tobin's Q prices the equity leg off the market and the rest off the
    # balance sheet, so it mixes currencies exactly like the EV family does:
    # a JPY statement under a USD market cap produces a meaningless Q (the
    # JPPHY EV defect), hence the same USD gate.
    q_row = tobins_q(fin) if usd else None
    mc = _latest(fin.get("market_cap"))
    ca = _latest(fin.get("current_assets"))
    tl = _latest(fin.get("total_liabilities"))
    net_net = (
        usd
        and mc is not None
        and ca is not None
        and tl is not None
        and mc < (2.0 / 3.0) * (ca - tl)
    )
    trap = "n/a"
    if any(v is not None for v in (f_score, m_score, z_score)):
        from tradingagents.strategies.normalized import trap_verdict

        trap = trap_verdict(
            f_score=f_score,
            m_score=m_score,
            z_score=z_score,
            z_variant=z_variant,
            z_zone=z_zone,
            f_band=f_band,
        )["level"]
    ne = _latest(fin.get("net_income"))
    te = _latest(fin.get("total_equity"))
    roe = None
    if ne is not None and te is not None and te > 0:
        roe = float(ne) / float(te)
    row = {
        "ticker": ticker,
        "ev_ebit": round(am, 2) if am is not None else None,
        "earnings_yield": round(ey, 4) if ey is not None else None,
        "ev": round(ev, 2) if ev is not None else None,
        "tobins_q": round(q_row["value"], 3) if q_row else None,
        "f_score": f_score,
        "beneish_m": round(m_score, 3) if m_score is not None else None,
        "altman_z": round(z_score, 3) if z_score is not None else None,
        "net_net": net_net,
        "trap": trap,
        "gp_a": round(gp_a_row["value"], 4) if gp_a_row else None,
        "noa": round(noa_row["value"], 4) if noa_row else None,
        "gp_a_classification": gp_a_row["classification"] if gp_a_row else None,
        "noa_classification": noa_row["classification"] if noa_row else None,
        "tobins_q_classification": q_row["classification"] if q_row else None,
        "roe": round(roe, 4) if roe is not None else None,
        "eps_yoy": sane_eps_yoy(fin),
        "revenue_yoy": sane_revenue_yoy(fin),
        "sector": fin.get("sector"),
    }
    # The round-3 keys appear ONLY when their gate supplied a value, so a
    # gate-off row has exactly the shape it had before this landed.
    if z_zone:
        row["altman_zone"] = z_zone["zone"]
        row["altman_variant"] = z_variant
    if f_band:
        row["f_score_band"] = f_band.get("label")
    return row


