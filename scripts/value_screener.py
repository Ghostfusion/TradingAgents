"""Value watchlist screener - builds a master list of value candidates.

Usage
-----
    python scripts/value_screener.py AAPL MSFT GOOG -d 2026-06-30
    python scripts/value_screener.py --file universe.txt -d 2026-06-30 --limit 10

For each ticker the screener pulls the configured fundamental vendors
(``moomoo,yfinance`` by default, or whatever ``fundamental_data`` points at)
through ``route_to_vendor``, translates the vendor output into canonical line
items, computes the classic screens, and prints a ranked watchlist table.

Screens (from ``strategies/Math.md``):

* Magic Formula: Earnings Yield = EBIT / EV, Return on Capital (EBIT / invested
  capital) - rank on both.
* Acquirer's Multiple: EV / EBIT (lower is better).
* Piotroski Quality: F-Score >= 7 plus low P/B.
* Shareholder Yield: dividends + buybacks + net debt reduction / market cap.
* Net-Net: market cap < 2/3 * (current assets - total liabilities).
* Fraud / bankruptcy guards: Beneish M-Score, Altman Z-Score.

The screener never fabricates: a missing line item makes the corresponding
screen "n/a" rather than a guessed number.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.dataflows.interface import route_to_vendor  # noqa: E402
from tradingagents.dataflows.quantitative_scores import (  # noqa: E402
    acquirers_multiple,
    altman_z_score,
    beneish_m_score,
    earnings_yield,
    enterprise_value,
    piotroski_f_score,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("value_screener")

# ---------------------------------------------------------------------------
# Vendor-output -> canonical line items
# ---------------------------------------------------------------------------

# Canonical key -> list of substrings that identify the row in vendor output.
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


def rank_watchlist(results: list) -> list:
    """Rank on earnings yield (desc), then EV/EBIT (asc); missing -> end."""

    def key(r):
        ey = r["earnings_yield"] if r["earnings_yield"] is not None else -1.0
        am = r["ev_ebit"] if r["ev_ebit"] is not None else float("inf")
        return (-ey, am)

    return sorted(results, key=key)


def _watchlist_markdown(results: list) -> str:
    """Print the ranked watchlist as a table.

    ``Name`` / ``DayChg`` columns appear only when the run carried mover
    metadata (i.e. the universe came from moomoo's top-losers rank).
    """
    show_name = any(r.get("name") for r in results)
    show_chg = any(r.get("day_change") is not None for r in results)
    heads = ["Rank", "Ticker"]
    if show_name:
        heads.append("Name")
    heads += ["EY", "EV/EBIT", "EV", "F", "M", "Z", "NetNet"]
    show_mom = any(r.get("pills") is not None for r in results)
    if show_mom:
        heads += ["Pills", "Pull", "RR"]
    show_live = any(r.get("line_price") is not None for r in results)
    if show_live:
        heads += ["L1Px", "VWAP1m", "1mVol"]
    show_norm = any(r.get("nebit_ev_ebit") is not None for r in results)
    if show_norm:
        heads.append("NEV/EBIT")
        heads.append("PE5Y")
    show_scan = any(r.get("scan_a") or r.get("scan_b") for r in results)
    if show_scan:
        heads.append("ScanA")
        heads.append("ScanB")
    show_growth = any(
        r.get("eps_yoy") is not None or r.get("revenue_yoy") is not None or r.get("roe") is not None
        for r in results
    )
    if show_growth:
        heads += ["EpsYoY", "RevYoY", "ROE"]
    show_sector = any(r.get("sec_rank") is not None for r in results)
    if show_sector:
        heads += ["Sec", "Rank"]
    show_rev = any(r.get("rev_net") is not None for r in results)
    if show_rev:
        heads.append("RevUp")
    show_inst = any(r.get("inst_latest_pp") is not None for r in results)
    if show_inst:
        heads.append("Inst")
    show_swing = any(r.get("scan_c") for r in results)
    if show_swing:
        heads += ["ScanC", "RS", "Stp", "T2"]
    show_vcp = any(r.get("vcp_flag") for r in results)
    if show_vcp:
        heads += ["VCP", "Brk"]
    show_trap = any(r.get("trap") not in (None, "n/a") for r in results)
    if show_trap:
        heads.append("Trap")
    if show_chg:
        heads.append("DayChg")
    seps = ["---"] * len(heads)
    header = f"# Value Watchlist ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
    out = [
        header,
        "| " + " | ".join(heads) + " |",
        "| " + " | ".join(seps) + " |",
    ]
    for i, r in enumerate(results, 1):

        def cell(v, fmt=None):
            if v is None:
                return "n/a"
            return fmt.format(v) if fmt else str(v)

        cells = [str(i), r["ticker"]]
        if show_name:
            cells.append(cell(r.get("name")))
        cells += [
            cell(r["earnings_yield"], "{:.2%}"),
            cell(r["ev_ebit"]),
            cell(r["ev"]),
            cell(r["f_score"]),
            cell(r["beneish_m"]),
            cell(r["altman_z"]),
            "yes" if r["net_net"] else "no",
        ]
        if show_mom:
            cells.append(cell(r.get("pills")))
            cells.append("yes" if r.get("pullback") else "no")
            cells.append(cell(r.get("mom_rr")))
        if show_live:
            cells.append(cell(r.get("line_price")))
            cells.append(cell(r.get("line_vwap")))
            cells.append(cell(r.get("line_vol")))
        if show_norm:
            cells.append(cell(r.get("nebit_ev_ebit")))
            cells.append(cell(r.get("pe_pct5"), "{:.0%}"))
        if show_scan:
            cells.append("yes" if r.get("scan_a") else "no")
            cells.append("yes" if r.get("scan_b") else "no")
        if show_growth:
            cells.append(cell(r.get("eps_yoy"), "{:.1%}"))
            cells.append(cell(r.get("revenue_yoy"), "{:.1%}"))
            cells.append(cell(r.get("roe"), "{:.1%}"))
        if show_sector:
            cells.append(cell(r.get("sector")))
            rank = r.get("sec_rank")
            cells.append(
                cell(rank) if rank is None else (f"T{rank}" if r.get("sec_top3") else str(rank))
            )
        if show_rev:
            cells.append(cell(r.get("rev_net"), "%+d"))
        if show_inst:
            cells.append(cell(r.get("inst_latest_pp"), "%+.1f"))
        if show_swing:
            cells.append("yes" if r.get("scan_c") else "no")
            cells.append(cell(r.get("swing_rs") or "n/a"))
            cells.append(cell(r.get("swing_stop_pct"), "{:.1%}"))
            cells.append(cell(r.get("swing_t2_pct"), "{:.1%}"))
        if show_vcp:
            cells.append("yes" if r.get("vcp_flag") else "no")
            cells.append(cell(r.get("vcp_brk"), "{:.1%}"))
        if show_trap:
            cells.append(cell(r.get("trap")))
        if show_chg:
            cells.append(cell(r.get("day_change"), "{:+.2%}"))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def print_watchlist(results) -> None:
    """Print the ranked watchlist (legacy entry point for tests)."""
    print(_watchlist_markdown(results))


def save_watchlist(markdown, out_dir, ts=None):
    """Write the watchlist markdown to <out_dir>/<finish_timestamp>.md."""
    from datetime import datetime as _dt

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    stamp = ts or _dt.now().strftime("%Y%m%d_%H%M%S")
    file = out_path / (stamp + ".md")
    file.write_text(markdown + "\n", encoding="utf-8")
    return file


def _fetch_ohlcv(ticker: str, days: int = 320) -> dict:
    """Daily OHLCV via the vendor chain (csv): closes/highs/lows/volumes."""
    try:
        from datetime import datetime, timedelta

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        out = route_to_vendor("get_stock_data", ticker, start, end) or ""
        closes, opens, highs, lows, volumes = [], [], [], [], []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("date,"):
                continue
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                closes.append(float(parts[4]))
                opens.append(float(parts[1]))
                highs.append(float(parts[2]))
                lows.append(float(parts[3]))
                volumes.append(float(parts[5]))
            except ValueError:
                pass
        if closes:
            return {"closes": closes, "highs": highs, "lows": lows, "volumes": volumes}
    except Exception:
        pass
    try:
        from tradingagents.dataflows.alpaca import get_bars as _alpaca_bars
        from tradingagents.dataflows.config import get_config

        if get_config().get("enable_alpaca"):
            bars = _alpaca_bars(ticker, timeframe="1Day", limit=330)
            # Free IEX tier returns only the latest daily bar (historical daily
            # needs a paid tier); require enough depth for ATR/scan before use.
            if bars and len(bars) >= 15:
                return {
                    "closes": [float(b["c"]) for b in bars],
                    "highs": [float(b["h"]) for b in bars],
                    "lows": [float(b["l"]) for b in bars],
                    "volumes": [float(b["v"]) for b in bars],
                    "opens": [float(b["o"]) for b in bars],
                }
    except Exception:
        pass
    return {"closes": [], "opens": [], "highs": [], "lows": [], "volumes": []}


def _fetch_closes(ticker: str, days: int = 320) -> list:
    """Daily closes via the vendor chain (csv); empty on failure."""
    return _fetch_ohlcv(ticker, days=days)["closes"]


_BENCHMARK_CACHE: dict = {}


def _benchmark_closes() -> list:
    """Benchmark (SPY or TRADINGAGENTS_BENCHMARK_TICKER) closes for the RS
    line; cached per run so one fetch serves every symbol. Empty on failure
    (the swing scan then treats RS as unknown and never blocks on it)."""
    try:
        from tradingagents.dataflows.config import get_config

        bench = get_config().get("benchmark_ticker") or "SPY"
    except Exception:
        bench = "SPY"
    if bench not in _BENCHMARK_CACHE:
        _BENCHMARK_CACHE[bench] = _fetch_closes(bench)
    return _BENCHMARK_CACHE[bench]


def _swing_scan(symbol: str, ohlcv: dict, benchmark: list) -> dict | None:
    """Composite swing read for one symbol + display metrics for the table."""
    try:
        from tradingagents.strategies.size import atr as _atr
        from tradingagents.strategies.swing import swing_report

        closes = ohlcv.get("closes") or []
        highs = ohlcv.get("highs") or []
        lows = ohlcv.get("lows") or []
        vols = ohlcv.get("volumes") or []
        if len(closes) < 200:
            return None
        atr_v = _atr(highs, lows, closes, window=14)
        rep = swing_report(closes, highs, lows, vols, atr_value=atr_v, benchmark_closes=benchmark)
        if not rep:
            return None
        out = dict(rep)
        t2 = (rep.get("targets") or {}).get("t2")
        last = closes[-1] if closes else None
        out["t2_pct"] = (float(t2) / last - 1.0) if (t2 and last) else None
        return out
    except Exception:  # noqa: BLE001 - a failed swing read must not abort a run
        return None


def _vcp_scan(ohlcv: dict) -> dict | None:
    """Volatility Contraction Pattern read for one symbol."""
    try:
        from tradingagents.strategies.swing import vcp_setup

        closes = ohlcv.get("closes") or []
        highs = ohlcv.get("highs") or []
        lows = ohlcv.get("lows") or []
        vols = ohlcv.get("volumes") or []
        if len(closes) < 90:
            return None
        return vcp_setup(closes, highs, lows, vols)
    except Exception:  # noqa: BLE001 - a failed vcp read must not abort a run
        return None


_SECTOR_RANK_CACHE: dict = {}


def _sector_ranking() -> dict:
    """SPDR sector ranking (11 ETFs via the vendor chain, cached per run)."""
    if not _SECTOR_RANK_CACHE:
        from tradingagents.strategies.sector_rank import SPDR_SECTORS, rank_sectors

        closes_map = {}
        for etf in SPDR_SECTORS:
            closes = _fetch_closes(etf)
            if closes:
                closes_map[etf] = closes
        _SECTOR_RANK_CACHE["value"] = rank_sectors(closes_map)
    return _SECTOR_RANK_CACHE["value"]


def _fetch_sector_guarded(ticker: str) -> str | None:
    try:
        from tradingagents.dataflows.yfinance_sector import fetch_sector

        return fetch_sector(ticker)
    except Exception:  # noqa: BLE001 - enrichment must never abort a run
        return None


def _fetch_revision_guarded(ticker: str) -> dict | None:
    try:
        from tradingagents.dataflows.yfinance_sector import fetch_revision_actions

        return fetch_revision_actions(ticker)
    except Exception:  # noqa: BLE001
        return None


def _inst_accumulation(payload) -> dict | None:
    """Sum of the two most recent %-of-float period changes from the moomoo
    institutional-holdings table ("| period | inst | shares | pct | chg pp |");
    None when the payload carries no change cells."""
    if not payload or str(payload).startswith(("NO_DATA", "DATA_")):
        return None
    chgs = []
    for line in str(payload).splitlines():
        line = line.strip()
        if not line.startswith("|") or "pp" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 5 and cells[4].endswith("pp"):
            v = _first_number(cells[4])
            if v is not None:
                chgs.append(v)
    if not chgs:
        return None
    latest = chgs[0]
    two_q = latest + (chgs[1] if len(chgs) > 1 else 0.0)
    return {"latest_pp": latest, "two_q_pp": two_q, "accumulate": two_q > 0}


def _sma(series, n: int) -> float | None:
    if len(series) < n or n <= 0:
        return None
    return sum(series[-n:]) / n


def _ema(series, n: int) -> float | None:
    if len(series) < n or n <= 0:
        return None
    k = 2.0 / (n + 1)
    ema = sum(series[:n]) / n
    for v in series[n:]:
        ema = v * k + ema * (1 - k)
    return ema


def _rsi(closes, n: int = 14) -> float | None:
    if len(closes) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(1, n + 1):
        diff = closes[-i] - closes[-i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    if gains + losses == 0:
        return 50.0
    rs = gains / losses if losses > 0 else float("inf")
    return round(100.0 - 100.0 / (1.0 + rs), 2)


def _boll_squeeze(closes, n: int = 20) -> bool:
    """True when Bollinger width (20,2) is at its lowest in the last n bars."""
    if len(closes) < n * 2:
        return False
    widths = []
    for i in range(len(closes) - n, len(closes) + 1):
        window = closes[i - n : i]
        if len(window) < n:
            continue
        mid = sum(window) / n
        var = sum((v - mid) ** 2 for v in window) / n
        sd = var**0.5
        if mid > 0:
            widths.append(4 * sd / mid)
    return bool(widths) and widths[-1] == min(widths)


def scan_signals(ohlcv: dict) -> dict | None:
    """Strategy A (trend pullback) / B (breakout) flags + metrics from OHLCV."""
    closes = ohlcv.get("closes") or []
    highs = ohlcv.get("highs") or []
    lows = ohlcv.get("lows") or []
    volumes = ohlcv.get("volumes") or []
    if len(closes) < 200 or not highs or not lows or not volumes:
        return None
    close = closes[-1]
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)
    sma20 = _sma(closes, 20)
    ema20 = _ema(closes, 20)
    rsi = _rsi(closes, 14)
    hi52 = max(closes[-252:]) if len(closes) >= 252 else max(closes)
    hi52_dist = close / hi52 - 1.0 if hi52 else None
    qret = closes[-1] / closes[-64] - 1.0 if len(closes) >= 64 and closes[-64] else None
    avg20 = _sma(volumes, 20)
    rvol = volumes[-1] / avg20 if avg20 else None
    squeeze = _boll_squeeze(closes)

    strategy_a = bool(
        close > sma50
        and sma50 > sma200
        and lows[-1] <= ema20
        and close >= ema20
        and rsi is not None
        and 40.0 <= rsi <= 55.0
        and qret is not None
        and qret >= 0.10
    )
    strategy_b = bool(
        hi52_dist is not None
        and hi52_dist >= -0.10
        and close > sma20
        and close > sma50
        and ((rvol is not None and rvol > 1.5) or (rvol is not None and rvol < 0.75 and squeeze))
    )
    return {
        "a": strategy_a,
        "b": strategy_b,
        "rsi": rsi,
        "qret": qret,
        "rvol": rvol,
        "squeeze": squeeze,
        "hi52_dist": hi52_dist,
    }


def composite_scores(results: list, closes_map: dict) -> dict:
    """EY + momentum + 52w-distance factors -> composite score per ticker."""
    from tradingagents.strategies.factors import (
        composite_score,
        high_distance,
        momentum,
    )

    factors = {}
    for r in results:
        f = {}
        if r.get("earnings_yield") is not None:
            f["ey"] = r["earnings_yield"]
        closes = closes_map.get(r["ticker"]) or []
        if len(closes) >= 70:
            m = momentum(closes, lookback=60, skip=0)
            d = high_distance(closes, window=min(252, len(closes)))
            if m is not None:
                f["mom"] = m
            if d is not None:
                f["dist"] = d
        factors[r["ticker"]] = f
    return composite_score(factors)


def allocation_block(scores: dict) -> str:
    """Capped value-proportional allocation text (V3)."""
    from tradingagents.dataflows.config import get_config
    from tradingagents.strategies.portfolio import allocation_block as _ab

    return _ab(scores, cfg=get_config())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="*", help="ticker symbols")
    parser.add_argument("-f", "--file", help="file with one ticker per line")
    parser.add_argument(
        "-d",
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="current date (yyyy-mm-dd)",
    )
    parser.add_argument("-l", "--limit", type=int, default=50, help="max tickers to process")
    parser.add_argument(
        "-u",
        "--universe",
        choices=("tickers", "top-losers", "heat-proxy"),
        default="tickers",
        help="symbol source: 'tickers' (positional/file, default), "
        "'top-losers' (moomoo intraday decliners; refreshes daily) "
        "or 'heat-proxy' (same as top-losers, US-only - the official "
        "trade-rank proxy for the proprietary in-app Heat List)",
    )
    parser.add_argument(
        "--market", default="US", help="market key for --universe top-losers/heat-proxy (US/HK)"
    )
    parser.add_argument(
        "-n", "--movers-count", type=int, default=50, help="how many decliners to pull (max 200)"
    )
    parser.add_argument(
        "--min-mcap",
        type=float,
        default=10e9,
        help="market-cap floor in USD (default $10B; 0 disables)",
    )
    parser.add_argument(
        "--price-min",
        type=float,
        default=15.0,
        help="min last price in USD (default 15; 0 disables)",
    )
    parser.add_argument(
        "--pe-max", type=float, default=40.0, help="max P/E (TTM) (default 40; 0 disables)"
    )
    parser.add_argument(
        "--min-avg-vol",
        type=float,
        default=1_000_000,
        help="min 30-day average daily volume in shares (default 1M; 0 disables)",
    )
    parser.add_argument(
        "--min-atr-pct",
        type=float,
        default=2.0,
        help="min ATR(14) as %% of price (default 2; 0 disables)",
    )
    parser.add_argument(
        "--max-mcap",
        type=float,
        default=0.0,
        help="market-cap ceiling in USD (framework 2B-100B focus; 0 disables)",
    )
    parser.add_argument(
        "--min-eps-yoy",
        type=float,
        default=0.0,
        help="min EPS YoY change as %% (framework >= 20; 0 disables)",
    )
    parser.add_argument(
        "--min-rev-yoy",
        type=float,
        default=0.0,
        help="min revenue YoY change as %% (framework >= 15; 0 disables)",
    )
    parser.add_argument(
        "--min-roe",
        type=float,
        default=0.0,
        help="min return on equity as %% (framework >= 15; 0 disables)",
    )
    parser.add_argument(
        "--sector-rank",
        action="store_true",
        help="confirm the sector is a top-3 SPDR group (1m/3m momentum); "
        "adds Sec/Rank columns and keeps only top-3 sectors",
    )
    parser.add_argument(
        "--revision",
        action="store_true",
        help="require positive net analyst upgrades in the last 60d "
        "(yfinance proxy for forward earnings revisions); adds RevUp column",
    )
    parser.add_argument(
        "--inst-accum",
        action="store_true",
        help="require institutional accumulation (last two 13F periods "
        "%%-of-float change > 0, moomoo); adds Inst column",
    )
    parser.add_argument(
        "--intraday",
        action="store_true",
        help="append live Alpaca L1 price / 1m VWAP / volume columns",
    )
    parser.add_argument(
        "--scan",
        choices=("value", "trend-pullback", "breakout", "momentum", "swing", "vcp", "all"),
        default="all",
        help="scan mode: 'value' (classic), 'trend-pullback' (20/50 EMA "
        "dip in uptrend), 'breakout' (volatility contraction/breakout), "
        "'momentum' (day-trade pre-filter + first pullback), 'swing' "
        "(techno-fundamental swing: stacked trend + RS vs benchmark + "
        "pullback + stops/targets), 'vcp' (volatility contraction pattern: "
        "successively shallower pullbacks on fading volume), or 'all' "
        "(default: keep all, flag strategies)",
    )
    parser.add_argument(
        "--out-dir",
        default="screener",
        help="folder for the saved watchlist markdown (finish timestamp)",
    )
    parser.add_argument(
        "--rank",
        choices=("value", "composite"),
        default=None,
        help="ranking mode; default reads config enable_composite_rank",
    )
    parser.add_argument(
        "--enable-float",
        action="store_true",
        help="fetch public float (FMP/yfinance) for the momentum low-float pillar",
    )
    parser.add_argument(
        "--journal",
        default=None,
        metavar="PATH",
        help="append momentum candidate rows to a JSONL journal and print its stats",
    )
    parser.add_argument(
        "--alloc", action="store_true", help="append a capped allocation plan block"
    )
    args = parser.parse_args(argv)

    # The proprietary Heat List (search/news/trade telemetry) is app-only and
    # not exposed by any moomoo API; 'heat-proxy' is the sanctioned stand-in
    # (top-movers rank) so the daily losers-of-the-moment list keeps rotating.
    if args.universe == "heat-proxy":
        args.market = "US"

    mover_meta: dict = {}
    float_cache: dict = {}
    scan_meta: dict = {}
    tickers = list(args.tickers)
    if args.universe in ("top-losers", "heat-proxy"):
        try:
            from tradingagents.dataflows.moomoo import (
                MoomooNotConfiguredError,
                get_hot_movers_moomoo,
                get_top_movers_moomoo,
            )

            if args.universe == "heat-proxy":
                # Heat-list stand-in: the official hot master (gainers+losers,
                # hottest first), then keep the losers of the moment.
                movers = get_hot_movers_moomoo(
                    count=args.movers_count,
                    market=args.market,
                    min_market_cap=args.min_mcap,
                )
                losers = [
                    m for m in movers if m.get("change_ratio") is not None and m["change_ratio"] < 0
                ]
                movers = losers
            else:
                movers = get_top_movers_moomoo(
                    sort_dir="losers",
                    count=args.movers_count,
                    market=args.market,
                    min_market_cap=args.min_mcap,
                )
            # Equity-only, price, P/E (TTM), market-cap, 30d volume, ATR gates.
            need_ohlcv = bool(args.min_avg_vol or args.min_atr_pct or args.scan != "value")
            ohlcv_cache: dict = {}
            scan_meta: dict = {}
            gated = []
            for m in movers[: args.movers_count * 4]:
                if _is_non_equity(m.get("name")):
                    continue
                price = m.get("cur_price")
                pe = m.get("pe_ttm")
                cap = m.get("market_cap")
                if args.price_min and (price is None or price < args.price_min):
                    continue
                if args.pe_max and (pe is None or not (0.0 < pe <= args.pe_max)):
                    continue
                if args.min_mcap and (cap is None or cap < args.min_mcap):
                    continue
                if need_ohlcv:
                    symbol = (m.get("symbol") or "").upper()
                    ohlcv = ohlcv_cache.get(symbol)
                    if ohlcv is None:
                        ohlcv = _fetch_ohlcv(symbol)
                        ohlcv_cache[symbol] = ohlcv
                    if args.scan != "value":
                        sig = scan_signals(ohlcv) or {}
                        scan_meta[symbol] = sig
                        if args.scan in ("trend-pullback", "breakout"):
                            if args.scan == "trend-pullback" and not sig.get("a"):
                                continue
                            if args.scan == "breakout" and not sig.get("b"):
                                continue
                        if args.scan == "momentum":
                            try:
                                from tradingagents.strategies.momentum import (
                                    first_pullback as _fp,
                                    pillars as _pill,
                                    rvol as _rvol,
                                    session_flags as _sess,
                                )

                                closes = ohlcv["closes"]
                                vols = ohlcv["volumes"]
                                opens = ohlcv.get("opens") or []
                                rv = _rvol(vols) if vols else None
                                fl = float_cache.get(symbol)
                                if args.enable_float and fl is None:
                                    try:
                                        from tradingagents.dataflows.float_shares import (
                                            fetch_float_shares,
                                        )

                                        fl = fetch_float_shares(symbol)
                                        float_cache[symbol] = fl
                                    except Exception:
                                        fl = None
                                pill = _pill(
                                    close=price,
                                    day_volume=vols[-1] if vols else None,
                                    prev_close=closes[-2] if len(closes) >= 2 else None,
                                    day_open=opens[-1] if opens else None,
                                    rv=rv,
                                    float_shares=fl,
                                )
                                pull = _fp(
                                    closes, ohlcv["highs"], ohlcv["lows"], vols, opens=opens or None
                                )
                                session = _sess(peak_pnl=None, current_pnl=None)
                                scan_meta[symbol]["momentum"] = {
                                    "pillars": {
                                        kk: bool(vv) for kk, vv in pill.items() if vv is not None
                                    },
                                    "pullback": bool(pull.get("candidate")),
                                    "mom_rr": pull.get("rr"),
                                }
                                # 5-pillar pre-filter: skip when any *known*
                                # pillar fails; unknown pillars (no data)
                                # keep the symbol so scans stay honest.
                                if any(v is False for v in pill.values()):
                                    continue
                                if args.journal and pull.get("candidate"):
                                    from tradingagents.strategies.journal import (
                                        record_momentum_trade,
                                    )

                                    record_momentum_trade(
                                        args.journal,
                                        symbol,
                                        date=args.date,
                                        pillars=pill,
                                        pullback=pull,
                                        session=session,
                                        price=price,
                                        note="screener momentum candidate",
                                    )
                            except Exception:
                                pass
                    if args.scan == "swing":
                        bench = _benchmark_closes()
                        sw = _swing_scan(symbol, ohlcv, bench)
                        if sw is not None:
                            scan_meta[symbol]["swing"] = sw
                        if not (sw and sw.get("candidate")):
                            continue
                    if args.scan == "vcp":
                        vc = _vcp_scan(ohlcv)
                        if vc is not None:
                            scan_meta[symbol]["vcp"] = vc
                        if not (vc and vc.get("candidate")):
                            continue
                    if args.min_avg_vol:
                        vols = ohlcv["volumes"][-30:]
                        avg_vol = sum(vols) / len(vols) if vols else 0.0
                        if avg_vol < args.min_avg_vol:
                            continue
                    if args.min_atr_pct:
                        closes = ohlcv["closes"]
                        if len(closes) < 15 or not ohlcv["highs"] or not ohlcv["lows"]:
                            continue
                        from tradingagents.strategies.size import atr as _atr

                        a = _atr(ohlcv["highs"], ohlcv["lows"], closes, window=14)
                        last = closes[-1]
                        if last <= 0 or (a / last * 100.0) < args.min_atr_pct:
                            continue
                gated.append(m)
            movers = gated[: args.movers_count]
            if not movers:
                parser.error("no symbols after price/P-E/equity gates")
            for m in movers:
                symbol = (m.get("symbol") or "").upper()
                if not symbol:
                    continue
                tickers.append(symbol)
                if m.get("name") or m.get("change_ratio") is not None:
                    mover_meta[symbol] = {
                        "name": m.get("name"),
                        "day_change": m.get("change_ratio"),
                        "market_cap": m.get("market_cap"),
                    }
            logger.info("top-losers universe: %d symbols from moomoo", len(tickers))
        except MoomooNotConfiguredError as exc:
            parser.error(f"moomoo top-losers unavailable: {exc}")
        except Exception as exc:  # noqa: BLE001 - a universe source must fail loudly
            parser.error(f"moomoo top-losers failed: {exc}")
    elif args.file:
        with open(args.file, encoding="utf-8") as fh:
            tickers += [ln.strip().upper() for ln in fh if ln.strip()]
    if not tickers:
        parser.error("no tickers provided (positional args, --file, or --universe top-losers)")

    results = []
    fmp_use = False
    try:
        from tradingagents.dataflows.config import get_config

        fmp_use = bool(get_config().get("fmp_api_key"))
    except Exception:
        fmp_use = False
    for ticker in tickers[: args.limit]:
        try:
            fin = fetch_ticker(ticker, args.date)
            meta = mover_meta.get(ticker.upper(), {})
            # The moomoo rank carries market cap per symbol, but moomoo's
            # fundamentals feed (statements) does not - inject it so the EV /
            # earnings-yield / acquirer screens can run on the daily list.
            meta_cap = meta.get("market_cap")
            fin_cap = _latest(fin.get("market_cap"))
            # Prefer the day-of rank cap (real-time) over the parsed one when
            # both exist; inject when fundamentals lacked a cap entirely.
            if meta_cap is not None and (fin_cap is None or fin_cap < meta_cap):
                fin["market_cap"] = meta_cap
            cap = _latest(fin.get("market_cap"))
            if args.min_mcap and cap is not None and cap < args.min_mcap:
                logger.info("skip %s: market cap %.2fB < floor", ticker, cap / 1e9)
                continue
            row = screen_ticker(ticker, fin)
            # Phase-1 growth / structure gates - applied only when the metric
            # is MEASURED (missing data keeps the row: "n/a", never fabricated).
            if (
                args.min_eps_yoy
                and row.get("eps_yoy") is not None
                and (row["eps_yoy"] * 100.0) < args.min_eps_yoy
            ):
                logger.info(
                    "skip %s: EPS YoY %.1f%% < %.0f%%",
                    ticker,
                    row["eps_yoy"] * 100.0,
                    args.min_eps_yoy,
                )
                continue
            if (
                args.min_rev_yoy
                and row.get("revenue_yoy") is not None
                and (row["revenue_yoy"] * 100.0) < args.min_rev_yoy
            ):
                logger.info(
                    "skip %s: revenue YoY %.1f%% < %.0f%%",
                    ticker,
                    row["revenue_yoy"] * 100.0,
                    args.min_rev_yoy,
                )
                continue
            if args.min_roe and row.get("roe") is not None and (row["roe"] * 100.0) < args.min_roe:
                logger.info(
                    "skip %s: ROE %.1f%% < %.0f%%", ticker, row["roe"] * 100.0, args.min_roe
                )
                continue
            if args.max_mcap and cap is not None and cap > args.max_mcap:
                logger.info(
                    "skip %s: market cap %.2fB > ceiling %.2fB",
                    ticker,
                    cap / 1e9,
                    args.max_mcap / 1e9,
                )
                continue
            if args.sector_rank:
                from tradingagents.strategies.sector_rank import sector_standing

                sector = row.get("sector") or _fetch_sector_guarded(ticker)
                standing = sector_standing(sector, _sector_ranking())
                row["sector"] = standing.get("sector") or sector
                row["sec_rank"] = standing.get("rank")
                row["sec_top3"] = standing.get("top3_3m")
                if standing.get("verdict") == "tracking":  # measured, not top-3
                    logger.info(
                        "skip %s: sector %s rank %s not top-3",
                        ticker,
                        row["sector"],
                        row["sec_rank"],
                    )
                    continue
            if args.revision:
                rev = _fetch_revision_guarded(ticker)
                row["rev_net"] = rev.get("net") if rev else None
                if row["rev_net"] is not None and row["rev_net"] <= 0:
                    logger.info("skip %s: net analyst revisions %+d <= 0", ticker, row["rev_net"])
                    continue
            if args.inst_accum:
                inst = _inst_accumulation(route_to_vendor("get_institution_holdings", ticker))
                row["inst_latest_pp"] = inst.get("latest_pp") if inst else None
                row["inst_two_q_pp"] = inst.get("two_q_pp") if inst else None
                if inst is not None and inst.get("accumulate") is False:
                    logger.info(
                        "skip %s: institutional distribution (2q pp %.2f)", ticker, inst["two_q_pp"]
                    )
                    continue
            if fmp_use:
                _nf = None
                try:
                    from tradingagents.dataflows.fmp import normalized_score as _nsc

                    _nf = _nsc(ticker)
                except Exception:
                    _nf = None
                if _nf:
                    row["nebit_ev_ebit"] = _nf.get("ev_nebit")
                    row["pe_pct5"] = _nf.get("pe_pct5")
                    row["fmp_ev"] = _nf.get("ev")
            sig = scan_meta.get(ticker.upper())
            row["scan_a"] = bool(sig and sig.get("a"))
            row["scan_b"] = bool(sig and sig.get("b"))
            _mom = (sig or {}).get("momentum") if sig else None
            row["pills"] = sum(1 for v in _mom["pillars"].values() if v) if _mom else None
            row["pullback"] = bool(_mom.get("pullback")) if _mom else False
            row["mom_rr"] = _mom.get("mom_rr") if _mom else None
            _sw = (sig or {}).get("swing") if sig else None
            row["scan_c"] = bool(_sw and _sw.get("candidate"))
            _sw_rs = ((_sw or {}).get("relative_strength") or {}) if _sw else {}
            row["swing_rs"] = _sw_rs.get("verdict")
            row["swing_stop_pct"] = ((_sw or {}).get("stop") or {}).get("risk_pct")
            row["swing_t2_pct"] = (_sw or {}).get("t2_pct")
            _vc = (sig or {}).get("vcp") if sig else None
            row["vcp_flag"] = bool(_vc and _vc.get("candidate"))
            row["vcp_brk"] = (_vc or {}).get("close_to_base")
            row["scan_rsi"] = sig.get("rsi") if sig else None
            row["scan_rvol"] = sig.get("rvol") if sig else None
            row["scan_qret"] = sig.get("qret") if sig else None
            row["name"] = meta.get("name")
            row["day_change"] = meta.get("day_change")
            results.append(row)
            logger.info("screened %s", ticker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not screen %s: %s", ticker, exc)

    if args.intraday and results:
        try:
            from tradingagents.dataflows.alpaca import get_intraday as _intraday
            from tradingagents.dataflows.alpaca_common import alpaca_credentials

            kid, sec = alpaca_credentials()
            if kid and sec:
                snap = _intraday([r["ticker"] for r in results])
                for r in results:
                    info = (snap or {}).get(r["ticker"]) or {}
                    r["line_price"] = info.get("price")
                    r["line_vwap"] = info.get("vwap")
                    r["line_vol"] = info.get("volume")
        except Exception:
            pass
    ranked = rank_watchlist(results)
    alloc_extra = ""
    if args.alloc and results:
        alloc_extra = allocation_block(
            {r["ticker"]: r.get("earnings_yield") or 0.001 for r in results}
        )
        markdown = _watchlist_markdown(ranked) + "\n\n" + alloc_extra
    else:
        markdown = _watchlist_markdown(ranked)
    print_watchlist(ranked)
    if alloc_extra:
        print(alloc_extra)
    if alloc_extra:
        print(alloc_extra)
    try:
        from tradingagents.dataflows.alpaca import get_clock as _alpaca_clock
        from tradingagents.dataflows.config import get_config

        if get_config().get("enable_alpaca"):
            clock = _alpaca_clock()
            if clock is not None and not clock.get("is_open"):
                note = "[alpaca] market CLOSED (use /calendar for next open)"
                print(note)
                markdown = markdown.rstrip() + "\n\n" + note + "\n"
    except Exception:
        pass
    if args.journal and args.scan == "momentum":
        try:
            from tradingagents.strategies.journal import format_summary, momentum_stats

            print(format_summary(momentum_stats(args.journal)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("momentum journal summary failed: %s", exc)
    saved = save_watchlist(markdown, args.out_dir)
    print(f"[screener] saved watchlist to {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
