"""Computed valuation & profitability ratios (offline, no paid plan).

Replicates the ratio block that Massive's plan-gated ``/stocks/financials/v1/ratios``
returns, computed locally from the project's OWN canonical line items (already
fetched via moomoo/yfinance/alpha_vantage + the value-screener parser). This is
the "compute, don't narrate" core: the fundamentals analyst reads the same
precomputed numbers without needing a paid entitlement.

Formulas (standard finance defs; all USD when the underlying inputs are USD):

  EV           = MarketCap + TotalDebt - Cash
  EV/EBIT      = EV / OperatingIncome
  EV/EBITDA    = EV / (OperatingIncome + Depreciation)   # D&A back-add
  EV/Sales     = EV / Revenue
  P/E          = MarketCap / NetIncome
  P/B          = MarketCap / TotalEquity
  P/S          = MarketCap / Revenue
  P/CF         = MarketCap / OperatingCashFlow
  P/FCF        = MarketCap / FreeCashFlow         (FCF = OCF - Capex)
  ROE          = NetIncome / TotalEquity
  ROA          = NetIncome / TotalAssets
  D/E          = TotalDebt / TotalEquity
  Current      = CurrentAssets / CurrentLiabilities
  Quick        = (CurrentAssets - Inventory) / CurrentLiabilities
  Cash ratio   = Cash / CurrentLiabilities
  Div yield    = DividendsPaid / MarketCap       (approximation; see note)
  FCF          = OperatingCashFlow - Capex
  Market cap   = market_cap (passthrough)

No-fabrication rule: every ratio returns ``None`` when an input is missing
(never an invented number), mirroring ``dataflows/quantitative_scores``. The
caller renders the present values and ``n/a`` for the rest.
"""

from __future__ import annotations


def _num(v):
    """Latest/plain numeric value of a canonical item (flat or {current:..})."""
    if v is None:
        return None
    if isinstance(v, dict):
        v = v.get("current", v.get("value"))
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ratio(a, b):
    if a is None or b is None or not b:
        return None
    return a / b


def _sub(a, b):
    if a is None or b is None:
        return None
    return a - b


def _add(a, b):
    if a is None or b is None:
        return None
    return a + b


def compute_ratios(fin: dict, price: float | None = None) -> dict:
    """Compute the full ratio block from canonical line items.

    ``fin`` is the canonical line-items dict (see ``scripts/value_screener``
    ``_ROW_ALIASES``): market_cap, total_debt, cash, operating_income,
    depreciation, revenue, net_income, total_equity, total_assets,
    operating_cashflow, capex, current_assets, current_liabilities, inventory,
    dividends_paid. ``price`` is the current price (used only to sanity-check
    P/E vs EPS when ``markcap/eps`` is not available; NOT required for the
    aggregated formulas below).

    Returns a dict with one key per ratio; a key is absent->None when its input
    is missing. Never fabricates.
    """
    mc = _num(fin.get("market_cap"))
    debt = _num(fin.get("total_debt"))
    cash = _num(fin.get("cash"))
    op = _num(fin.get("operating_income"))         # EBIT
    dep = _num(fin.get("depreciation"))
    rev = _num(fin.get("revenue"))
    ni = _num(fin.get("net_income"))
    te = _num(fin.get("total_equity"))
    ta = _num(fin.get("total_assets"))
    ocf = _num(fin.get("operating_cashflow"))
    capex = _num(fin.get("capex"))
    ca = _num(fin.get("current_assets"))
    cl = _num(fin.get("current_liabilities"))
    inv = _num(fin.get("inventory"))
    divs = _num(fin.get("dividends_paid"))

    ev = _add(mc, _sub(debt, cash)) if (mc is not None) else None

    ebitda = _add(op, dep) if (op is not None or dep is not None) else None
    fcf = _sub(ocf, capex) if (ocf is not None) else None

    return {
        "ev": ev,
        "ev_ebitda": _ratio(ev, ebitda),
        "ev_ebit": _ratio(ev, op),
        "ev_sales": _ratio(ev, rev),
        "price_to_earnings": _ratio(mc, ni),
        "price_to_book": _ratio(mc, te),
        "price_to_sales": _ratio(mc, rev),
        "price_to_cash_flow": _ratio(mc, ocf),
        "price_to_free_cash_flow": _ratio(mc, fcf),
        "return_on_equity": _ratio(ni, te),
        "return_on_assets": _ratio(ni, ta),
        "debt_to_equity": _ratio(debt, te),
        "current": _ratio(ca, cl),
        "quick": _ratio(_sub(ca, inv), cl) if (ca is not None and cl is not None and inv is not None) else None,
        "cash_ratio": _ratio(cash, cl),
        "dividend_yield": _ratio(divs, mc) if (divs is not None and mc) else None,
        "free_cash_flow": fcf,
        "market_cap": mc,
    }


RENDER_ORDER = [
    ("ev", "EV", "int"),
    ("ev_ebitda", "EV/EBITDA", "float"),
    ("ev_ebit", "EV/EBIT", "float"),
    ("ev_sales", "EV/Sales", "float"),
    ("price_to_earnings", "P/E", "float"),
    ("price_to_book", "P/B", "float"),
    ("price_to_sales", "P/S", "float"),
    ("price_to_cash_flow", "P/CF", "float"),
    ("price_to_free_cash_flow", "P/FCF", "float"),
    ("return_on_equity", "ROE", "pct"),
    ("return_on_assets", "ROA", "pct"),
    ("debt_to_equity", "D/E", "float"),
    ("current", "Current", "float"),
    ("quick", "Quick", "float"),
    ("cash_ratio", "Cash ratio", "float"),
    ("dividend_yield", "Div yield", "pct"),
    ("free_cash_flow", "FCF", "int"),
    ("market_cap", "Market cap", "int"),
]


def render_ratios(ratios: dict) -> str:
    """Render the computed ratio dict to a ``key: value`` markdown block.

    Missing values render ``n/a`` (never a fabricated number); the block is
    formatted the same way the plan-gated Massive block is, so the analyst
    can substitute it directly.
    """
    lines = []
    for key, label, kind in RENDER_ORDER:
        v = ratios.get(key)
        if v is None:
            lines.append(f"- {label}: n/a")
            continue
        if kind == "pct":
            lines.append(f"- {label}: {float(v):.2%}")
        elif kind == "int":
            lines.append(f"- {label}: {float(v):,.0f}")
        else:
            lines.append(f"- {label}: {float(v):.2f}")
    return "\n".join(lines)


__all__ = ["compute_ratios", "render_ratios", "RENDER_ORDER"]
