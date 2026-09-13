"""Labelled quarterly-trend tables: one producer for the period labels and the
YoY / QoQ deltas the fundamentals analyst used to compute by hand.

NVDA 2026-09-12 review (defects D5/D6): the analyst wrote "+47% YoY" against a
Q4 base and put a MIXED-basis number "on the latest quarter", because the
yfinance statement payloads carry date-only columns and no producer existed
that named the two periods a delta compared. This tool is that producer: for
each statement it renders every period column with its derived fiscal-quarter
name, then a YoY and a QoQ cell whose text NAMES both compared periods, so a
two-quarter change can never be read as a year.

Payload shape: the yfinance CSV statements the router serves — a
``# <Statement> data for <T> (quarterly)`` header, a date header row, then
``Label,value,...`` rows. A payload in any other vendor format degrades to
``unavailable: <reason>``; the tool never guesses a number or a label.
"""

from __future__ import annotations

import csv
import math
import re
from collections import Counter
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Router degradation sentinels (interface.py): echo their reason instead of
# trying to parse them as a statement.
_SENTINEL_PREFIXES = ("NO_DATA_AVAILABLE", "DATA_UNAVAILABLE", "DATA_DISABLED")

_SECTION_ORDER = ("income", "balance", "cashflow")

_SECTION_TITLES = {
    "income": "Income Statement",
    "balance": "Balance Sheet",
    "cashflow": "Cash Flow",
}

_SECTION_METHODS = {
    "income": "get_income_statement",
    "balance": "get_balance_sheet",
    "cashflow": "get_cashflow",
}

# Canonical item name -> (section, vendor row-label aliases). A request is
# first matched against the payload's own row labels (exact, normalized); this
# table only names the working-capital set the review cared about so a caller
# can ask for "Total Debt" instead of the vendor's exact row wording. Every
# alias is the same measure on every vendor — no silent substitutions.
_ITEM_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "Total Revenue": ("income", ("Total Revenue", "Revenue", "Sales", "Operating Revenue")),
    "Gross Profit": ("income", ("Gross Profit",)),
    "Operating Income": ("income", ("Operating Income", "Total Operating Income As Reported")),
    "Net Income": ("income", ("Net Income", "Net Profit")),
    "Diluted EPS": ("income", ("Diluted EPS",)),
    "Accounts Receivable": ("balance", ("Accounts Receivable", "Receivables")),
    "Inventory": ("balance", ("Inventory",)),
    "Cash And Short Term Investments": (
        "balance",
        ("Cash Cash Equivalents And Short Term Investments",),
    ),
    "Total Debt": ("balance", ("Total Debt",)),
    "Free Cash Flow": ("cashflow", ("Free Cash Flow",)),
    "Operating Cash Flow": (
        "cashflow",
        ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities"),
    ),
    "Capital Expenditure": ("cashflow", ("Capital Expenditure",)),
}

_DEFAULT_ITEMS = (
    "Total Revenue",
    "Gross Profit",
    "Operating Income",
    "Net Income",
    "Diluted EPS",
    "Accounts Receivable",
    "Inventory",
    "Cash And Short Term Investments",
    "Total Debt",
)


def _norm(label: str) -> str:
    """Normalize a row label for matching (same form as statement_parsing)."""
    return re.sub(r"[^a-z0-9]+", " ", (label or "").lower()).strip()


def _to_float(cell: str) -> float | None:
    """Numeric cell -> float; blank / non-numeric / non-finite -> None (never 0.0)."""
    cell = (cell or "").strip()
    if not cell:
        return None
    try:
        value = float(cell)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _parse_statement_payload(
    payload: str,
) -> tuple[list[str], dict[str, list[float | None]]] | None:
    """Parse a yfinance CSV statement into ``(period_dates, {row: values})``.

    ``period_dates`` are the ISO dates of the header row, newest first (the
    order the vendor emits); ``values`` line up with them, ``None`` where the
    vendor left the cell blank or the row was short. Returns ``None`` when the
    payload is not this shape (another vendor format, a sentinel, empty) so the
    caller can say "unavailable" instead of guessing at the numbers.
    """
    lines = [
        ln for ln in (payload or "").splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    ]
    header_at = -1
    dates: list[str] = []
    for i, ln in enumerate(lines):
        cells = next(csv.reader([ln]), [])
        if not cells or cells[0].strip():
            continue
        rest = [c.strip() for c in cells[1:]]
        filled = [c for c in rest if c]
        if filled and all(_DATE_RE.match(c) for c in filled):
            header_at, dates = i, filled
            break
    if header_at < 0:
        return None

    rows: dict[str, list[float | None]] = {}
    for ln in lines[header_at + 1 :]:
        cells = next(csv.reader([ln]), [])
        if len(cells) < 2:
            continue
        label = _norm(cells[0])
        if not label:
            continue
        values = [_to_float(c) for c in cells[1 : 1 + len(dates)]]
        # A missing trailing cell must not shift the row: pad, never truncate
        # the front. Extra cells beyond the header are dropped.
        values += [None] * (len(dates) - len(values))
        rows.setdefault(label, values)
    if not rows:
        return None
    return dates, rows


def _fiscal_quarter(date: str, fy_end_month: int | None) -> tuple[int, int] | None:
    """``(fiscal_year, fiscal_quarter)`` for a period end, or None.

    General mapping for a fiscal year ending in ``fy_end_month``: a quarter
    ending ``k`` months into the fiscal year is Q(k).
    """
    if fy_end_month is None:
        return None
    year, month = int(date[:4]), int(date[5:7])
    quarter = ((month - fy_end_month - 1) % 12) // 3 + 1
    fiscal_year = year + (1 if month > fy_end_month else 0)
    return fiscal_year, quarter


def _period_cell(date: str, fy_end_month: int | None) -> str:
    """Table header cell: the date, plus the fiscal quarter when derivable."""
    fq = _fiscal_quarter(date, fy_end_month)
    return f"{date} (FY{fq[0]} Q{fq[1]})" if fq else date


def _period_short(date: str, fy_end_month: int | None) -> str:
    """Delta-label period name: "Q2 FY27" when fiscal, else the bare date."""
    fq = _fiscal_quarter(date, fy_end_month)
    return f"Q{fq[1]} FY{fq[0] % 100:02d}" if fq else date


def _fmt_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value == int(value) and abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _delta_cell(
    values: list[float | None],
    cur_i: int,
    base_i: int,
    dates: list[str],
    fy_end_month: int | None,
) -> str:
    """A delta that names both periods, or an n/a explaining what is missing."""
    if base_i >= len(dates):
        return "n/a (series too short)"
    current, base = values[cur_i], values[base_i]
    if current is None or base is None:
        return "n/a (value missing)"
    if base == 0:
        return "n/a (zero base)"
    pct = (current - base) / base * 100.0
    base_label = _period_short(dates[base_i], fy_end_month)
    cur_label = _period_short(dates[cur_i], fy_end_month)
    return f"{pct:+.1f}% ({base_label} -> {cur_label})"


def _infer_fiscal_year_end_month(
    ticker: str,
    curr_date: str,
    parsed: dict[str, tuple[list[str], dict[str, list[float | None]]]],
) -> int | None:
    """Fiscal-year-end month from the vendor's own ANNUAL period ends.

    Quarterly columns alone cannot tell a January fiscal-year end from an
    October one — both report Jan/Apr/Jul/Oct period ends — so the labels are
    anchored on the annual statement, whose period ends ARE fiscal year ends by
    construction. Returns None when that cannot be derived (caller then falls
    back to bare dates rather than guessing a quarter name).
    """
    quarterly_months = {int(d[5:7]) for dates, _ in parsed.values() for d in dates}
    try:
        payload = route_to_vendor("get_income_statement", ticker, "annual", curr_date)
    except Exception:  # noqa: BLE001 - the fiscal label is advisory; the trend tables are not
        return None
    if not isinstance(payload, str):
        return None
    annual = _parse_statement_payload(payload)
    if annual is None:
        return None
    months = [int(d[5:7]) for d in annual[0]]
    month, count = Counter(months).most_common(1)[0]
    if len(months) > 1 and count * 2 <= len(months):
        return None  # no strict majority: the annual ends themselves disagree
    if month not in quarterly_months:
        return None  # inconsistent with the quarterly columns: do not guess
    return month


def _match_item(
    name: str,
    parsed: dict[str, tuple[list[str], dict[str, list[float | None]]]],
) -> tuple[str, str] | None:
    """Resolve a requested item to ``(section, normalized_row_label)``."""
    wanted = _norm(name)
    for section in _SECTION_ORDER:  # 1. the payload's own row label
        section_parsed = parsed.get(section)
        if section_parsed is not None and wanted in section_parsed[1]:
            return section, wanted
    spec = _ITEM_SPECS.get(name)
    if spec is None:  # 2. a declared canonical name or alias
        for canonical, candidate in _ITEM_SPECS.items():
            if wanted in {_norm(canonical)} | {_norm(a) for a in candidate[1]}:
                spec = candidate
                break
    if spec is None:
        return None
    section, aliases = spec
    section_parsed = parsed.get(section)
    if section_parsed is not None:
        for alias in aliases:
            key = _norm(alias)
            if key in section_parsed[1]:
                return section, key
    # Section unavailable, or the vendor dropped the row: keep the request so
    # the report can attribute the gap instead of silently omitting the item.
    return section, _norm(aliases[0])


def _unavailable_reason(section: str, payload: object) -> str:
    """Why one statement section cannot be rendered."""
    if isinstance(payload, Exception):
        return f"{_SECTION_METHODS[section]} raised {type(payload).__name__}: {payload}"
    if isinstance(payload, str) and payload.lstrip().startswith(_SENTINEL_PREFIXES):
        first_line = payload.strip().splitlines()[0] if payload.strip() else "empty payload"
        return first_line[:300]
    return (
        f"{_SECTION_METHODS[section]} payload is not the yfinance CSV statement "
        "shape this tool parses"
    )


def build_financial_trends_report(
    ticker: str,
    curr_date: str,
    items: list[str] | None = None,
    periods: int = 5,
) -> str:
    """Render the labelled quarterly-trend report (the tool's whole body)."""
    requested = list(items) if items else list(_DEFAULT_ITEMS)
    try:
        periods = max(1, int(periods))
    except (TypeError, ValueError):
        periods = 5

    payloads: dict[str, object] = {}
    for section in _SECTION_ORDER:
        try:
            payloads[section] = route_to_vendor(
                _SECTION_METHODS[section], ticker, "quarterly", curr_date
            )
        except Exception as exc:  # noqa: BLE001 - one statement must not sink the report
            payloads[section] = exc

    parsed: dict[str, tuple[list[str], dict[str, list[float | None]]]] = {}
    reasons: dict[str, str] = {}
    for section in _SECTION_ORDER:
        payload = payloads[section]
        candidate = _parse_statement_payload(payload) if isinstance(payload, str) else None
        if candidate is None:
            reasons[section] = _unavailable_reason(section, payload)
        else:
            parsed[section] = candidate

    if not parsed:
        detail = "; ".join(f"{_SECTION_TITLES[s]}: {reasons[s]}" for s in _SECTION_ORDER)
        return (
            f"unavailable: no quarterly statement payload could be parsed for {ticker} "
            f"on {curr_date} ({detail}). Do not estimate; report these figures as "
            "unavailable."
        )

    fy_end_month = _infer_fiscal_year_end_month(ticker, curr_date, parsed)

    lines = [
        f"# Financial Trends for {ticker} (quarterly, as of {curr_date})",
        "# Values are raw vendor figures (unscaled). Each section's deltas compare its LATEST "
        "period against the labelled base:",
        "# YoY = same fiscal quarter four columns back, QoQ = the previous column. "
        "'n/a' means that period or value is absent (or the series is too short) — never inferred.",
        "",
    ]
    if fy_end_month is None:
        lines.append(
            "# Fiscal-year end could not be derived from the vendor's annual period ends; "
            "period columns carry dates only."
        )
        lines.append("")
    else:
        lines.append(
            "# Fiscal quarters derived from the vendor's annual period ends "
            f"(fiscal year ends in month {fy_end_month:02d})."
        )
        lines.append("")

    resolved: dict[str, list[tuple[str, str]]] = {section: [] for section in _SECTION_ORDER}
    missing: list[str] = []
    for name in requested:
        match = _match_item(name, parsed)
        if match is None:
            missing.append(name)
        else:
            resolved[match[0]].append((name, match[1]))

    for section in _SECTION_ORDER:
        if section not in parsed:
            lines.append(f"## {_SECTION_TITLES[section]}")
            lines.append(f"unavailable: {reasons[section]}")
            lines.append("")
            continue
        section_items = resolved[section]
        if not section_items:
            available = ", ".join(n for n, (s, _) in _ITEM_SPECS.items() if s == section)
            lines.append(f"## {_SECTION_TITLES[section]}")
            lines.append(
                f"_No requested items on this statement (available by name: {available})._"
            )
            lines.append("")
            continue
        dates, rows = parsed[section]
        shown = dates[:periods]
        lines.append(f"## {_SECTION_TITLES[section]}")
        lines.append(
            "| Item | "
            + " | ".join(_period_cell(d, fy_end_month) for d in shown)
            + " | YoY | QoQ |"
        )
        lines.append("| --- |" + " --- |" * (len(shown) + 2))
        for name, key in section_items:
            values = rows.get(key)
            if values is None:
                values = [None] * len(dates)
            cells = [_fmt_value(values[i]) for i in range(len(shown))]
            cells.append(_delta_cell(values, 0, 4, dates, fy_end_month))
            cells.append(_delta_cell(values, 0, 1, dates, fy_end_month))
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        lines.append("")

    if missing:
        for name in missing:
            lines.append(
                f"n/a {name}: no matching row in the fetched quarterly statements "
                "(row labels must match the vendor's own statement labels)."
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


@tool
def get_financial_trends(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    items: Annotated[list[str] | None, "row labels to include; omit for the default set"] = None,
    periods: Annotated[int, "how many quarterly period columns to show (default 5)"] = 5,
) -> str:
    """
    Retrieve labelled quarterly statement trends (period columns plus YoY/QoQ deltas).
    Uses the configured fundamental_data vendor and emits one markdown table per statement.
    Every delta names the two periods it compared, so a quarter-on-quarter change is
    never mistaken for a year.
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd
        items (list[str]): Row labels to include (default: revenue, gross profit, operating
            income, net income, diluted EPS, accounts receivable, inventory, cash + short-term
            investments, total debt)
        periods (int): Number of quarterly period columns to show (default 5)
    Returns:
        str: Markdown tables of quarterly trends, or "unavailable: <reason>"
    """
    return build_financial_trends_report(ticker, curr_date, items, periods)
