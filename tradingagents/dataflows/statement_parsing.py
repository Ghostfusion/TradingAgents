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
    piotroski_f_score,
)

logger = logging.getLogger("statement_parsing")

_ROW_ALIASES = {
    "revenue": ["total revenue", "revenue", "operating income", "sales"],
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
    "total_debt": [
        "total debt",
        "total borrowings",
        "long-term debt",
        "long term borrowings",
        "interest-bearing liabilities",
        "total liabilities",  # last-resort fallback only
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
    "sector": ["sector", "industrygroup"],
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
    "capex": ["capital expenditure", "purchase of property"],
}


def _norm(s: str) -> str:
    """Normalize a row label for loose matching."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _match_row(rows: dict, canonical: str):
    """Return the (label, value) for the best matching row, or None.

    Aliases are tried in ``_ROW_ALIASES`` order (most specific first) and the
    first alias that matches any row wins - so ``total_debt`` prefers a
    dedicated debt row over the catch-all ``total_liabilities`` row. Rows whose
    label starts with ``-`` are moomoo sub-item / contra-account breakdowns
    (e.g. ``-Accumulated Depreciation``, ``-Cash and Cash Equivalents``) and
    are skipped so the canonical value always comes from the aggregate line
    that precedes them.
    """
    for alias in _ROW_ALIASES.get(canonical, []):
        key = _norm(alias)
        for label, value in rows.items():
            if label.startswith("-"):
                continue
            if key and key in _norm(label):
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
        # Pick the rightmost numeric cell (most recent period).
        value = None
        for cell in reversed(row[1:]):
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
    for key, value in data.items():
        if key in ("fiscalDateEnding", "reportedCurrency"):
            continue
        if key.lower() == "sector" and isinstance(value, str) and value.strip():
            rows["Sector"] = value.strip()
    for report in data.get("annualReports", []) or data.get("quarterlyReports", []):
        for key, value in report.items():
            if key in ("fiscalDateEnding", "reportedCurrency"):
                continue
            parsed = _first_number(value)
            if parsed is not None and key not in rows:
                rows[key.replace("_", " ")] = parsed
    return rows


def _parse_text_report(payload: str) -> dict:
    """Parse yfinance fundamentals-style text (``Label: value`` lines)."""
    rows = {}
    for line in payload.splitlines():
        if ":" not in line:
            continue
        label, _, rest = line.partition(":")
        parsed = _first_number(rest)
        if label.strip() and parsed is not None:
            rows[label.strip()] = parsed
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


def _flat_canonical(rows: dict) -> dict:
    """Canonical line items from a flat single-period ``{label: value}`` row
    dict (yfinance CSV, alpha_vantage JSON, fundamentals text, Finnhub)."""
    canonical = {}
    for key in _ROW_ALIASES:
        match = _match_row(rows, key)
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
            m = _match_row(rows, key)
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
    if text.lstrip().startswith("{"):
        rows = _parse_json_statements(text)
        canonical = _flat_canonical(rows)
    elif any(ln.lstrip().startswith("|") for ln in text.splitlines()):
        canonical = _markdown_canonical(text)
    elif any(":" in ln for ln in text.splitlines()):
        rows = _parse_text_report(text)
        canonical = _flat_canonical(rows)
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


def fetch_ticker(ticker: str, curr_date: str) -> dict:
    """Pull the canonical line items for one ticker via the vendor chain."""
    canonical = {}
    # Fundamentals carries market cap (yfinance info / alpha_vantage overview).
    try:
        fund = route_to_vendor("get_fundamentals", ticker, curr_date)
        canonical.update(_canonicalize(fund))
    except Exception as exc:  # noqa: BLE001 - vendor chain already degrades
        logger.warning("%s fundamentals: %s", ticker, exc)
    for method in ("get_balance_sheet", "get_income_statement"):
        try:
            stmt = route_to_vendor(method, ticker, "annual", curr_date)
            canonical.update(_canonicalize(stmt))
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
        for k in ("eps_yoy", "revenue_yoy", "roe", "market_cap"):
            if k not in canonical and bf_canon.get(k) is not None:
                canonical[k] = bf_canon.get(k)
    except Exception as exc:  # noqa: BLE001
        logger.debug("%s finnhub basic financials: %s", ticker, exc)
    # Guard: a cash figure larger than total assets means a wrong-row match.
    ca_ = _latest(canonical.get("cash"))
    ta_ = _latest(canonical.get("total_assets"))
    if ca_ is not None and ta_ is not None and ca_ > ta_:
        canonical["cash"] = None
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
    # Derive working capital when both sides are available (Altman Z needs it).
    if "working_capital" not in canonical:
        ca = _latest(canonical.get("current_assets"))
        cl = _latest(canonical.get("current_liabilities"))
        if ca is not None and cl is not None:
            canonical["working_capital"] = ca - cl
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


def screen_ticker(ticker: str, fin: dict) -> dict:
    """Compute every screen for one ticker's canonical items."""
    usd = _usd_consistent(fin)
    ev = enterprise_value(fin) if usd else None
    am = acquirers_multiple(fin) if usd else None
    ey = earnings_yield(fin) if usd else None
    m_score = beneish_m_score(fin)
    z_score = altman_z_score(fin) if usd else None
    f_score = piotroski_f_score(fin)
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

        trap = trap_verdict(f_score=f_score, m_score=m_score, z_score=z_score)["level"]
    ne = _latest(fin.get("net_income"))
    te = _latest(fin.get("total_equity"))
    roe = None
    if ne is not None and te is not None and te > 0:
        roe = float(ne) / float(te)
    return {
        "ticker": ticker,
        "ev_ebit": round(am, 2) if am is not None else None,
        "earnings_yield": round(ey, 4) if ey is not None else None,
        "ev": round(ev, 2) if ev is not None else None,
        "f_score": f_score,
        "beneish_m": round(m_score, 3) if m_score is not None else None,
        "altman_z": round(z_score, 3) if z_score is not None else None,
        "net_net": net_net,
        "trap": trap,
        "roe": round(roe, 4) if roe is not None else None,
        "eps_yoy": _latest(fin.get("eps_yoy")),
        "revenue_yoy": _latest(fin.get("revenue_yoy")),
        "sector": fin.get("sector"),
    }


