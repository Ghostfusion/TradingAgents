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

BASIS RULE (NVDA 2026-09-12). A ratio is only meaningful with the period it was
built from, and this module used to mix them silently: ``P/E`` divided the
current market cap by the FY2026 ANNUAL net income (43.90x) while the
balance-sheet ratios used the latest quarter, so one block carried two periods
and nothing said so - the report then quoted 43.90 as a "realized multiple"
against a live TTM basis of 27.63x. Flow items (revenue, earnings, cash flow,
capex, dividends) are now taken from the ``*_ttm`` keys when the caller supplies
them (see ``statement_parsing.trailing_twelve_months``), and the result carries a
``basis`` block stating which period each family came from; ``render_ratios``
prints it as the block's first line.
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


def _flow(fin: dict, *keys):
    """First present numeric among ``keys`` (a TTM key wins over its reported one).

    Explicit ``is not None`` rather than ``or``: a legitimate 0.0 must not fall
    through to the next key.
    """
    for key in keys:
        value = _num(fin.get(key))
        if value is not None:
            return value
    return None


def _basis_label(flows: str, flows_period: str | None, balance: str | None) -> str:
    """One sentence naming the period behind every family in the block."""
    if flows == "TTM":
        flow = f"TTM ({flows_period})" if flows_period else "TTM"
    else:
        flow = f"as reported ({flows_period})" if flows_period else "as reported"
    parts = [f"flows {flow}"]
    if balance:
        parts.append(f"balance sheet {balance}")
    return "; ".join(parts)


def compute_ratios(fin: dict, price: float | None = None,
                   basis: dict | None = None) -> dict:
    """Compute the full ratio block from canonical line items.

    ``fin`` is the canonical line-items dict (see ``scripts/value_screener``
    ``_ROW_ALIASES``): market_cap, total_debt, cash, operating_income,
    depreciation, revenue, net_income, total_equity, total_assets,
    operating_cashflow, capex, current_assets, current_liabilities, inventory,
    dividends_paid - plus the optional ``*_ttm`` flow keys, which take
    precedence over their reported counterparts. ``price`` is the current price:
    it is the P/E fallback (``price / eps``) when no earnings figure is
    available at all, and is annotated as such in the rendered block.

    ``basis`` states the periods the inputs came from
    (``{"flows", "flows_period", "balance"}``); when omitted it is inferred
    from whether a ``*_ttm`` key is present. Returns a dict with one key per
    ratio plus ``basis``; a key is absent->None when its input is missing.
    Never fabricates.
    """
    mc = _num(fin.get("market_cap"))
    debt = _num(fin.get("total_debt"))
    cash = _num(fin.get("cash"))
    # Flows: the trailing-twelve-month figure wins when the caller supplied it,
    # so the block pairs a current market cap with a current window instead of
    # with a stale annual one (the D1 defect).
    op = _flow(fin, "operating_income_ttm", "operating_income")   # EBIT
    dep = _num(fin.get("depreciation"))
    rev = _flow(fin, "revenue_ttm", "revenue")
    ni = _flow(fin, "net_income_ttm", "net_income")
    eps = _flow(fin, "eps_ttm", "eps")
    te = _num(fin.get("total_equity"))
    ta = _num(fin.get("total_assets"))
    tl = _num(fin.get("total_liabilities"))
    ocf = _flow(fin, "operating_cashflow_ttm", "operating_cashflow")
    capex = _flow(fin, "capex_ttm", "capex")
    ca = _num(fin.get("current_assets"))
    cl = _num(fin.get("current_liabilities"))
    inv = _num(fin.get("inventory"))
    divs = _flow(fin, "dividends_paid_ttm", "dividends_paid")

    ev = _add(mc, _sub(debt, cash)) if (mc is not None) else None

    # Balance-sheet subset invariant: current assets/liabilities can never
    # exceed total assets/liabilities. A *proven* violation (both values
    # present and current > total) means the canonical parse picked the wrong
    # row (observed on MSFT 2026-09-08: a current ratio of 3.74 vs the true
    # 1.23 when current_assets was mis-parsed) — null the ratio rather than
    # emit a wrong number. Missing totals (None) cannot prove a violation, so
    # the ratio still computes from what is available.
    ca_ok = ca is not None and (ta is None or ca <= ta)
    cl_ok = cl is not None and (tl is None or cl <= tl)
    current = _ratio(ca, cl) if ca_ok and cl_ok else None
    quick = (
        _ratio(_sub(ca, inv), cl)
        if (ca_ok and cl_ok and inv is not None)
        else None
    )

    ebitda = _add(op, dep) if (op is not None or dep is not None) else None
    # capex/dividends are expenditures: some vendors report them as a negative
    # GAAP outflow (yfinance/Tiingo), others as a positive magnitude (moomoo).
    # abs() makes FCF and dividend yield correct under both conventions
    # (OCF - capex with a negative capex would ADD capital spending back,
    # inflating FCF and every FCF-derived screen).
    # abs() on a None capex/divs would raise - guard both operands.
    fcf = _sub(ocf, abs(capex)) if (ocf is not None and capex is not None) else None
    divs_abs = abs(divs) if divs is not None else None

    # P/E on the earnings basis the block actually has. ``price`` was a dead
    # parameter (documented but never referenced) - the documented sanity check
    # is now the fallback, and it is LABELLED so a price/EPS multiple is never
    # mistaken for the market-cap/earnings one.
    p_e = _ratio(mc, ni)
    p_e_fallback = False
    if p_e is None and price is not None and eps:
        p_e = _ratio(price, eps)
        p_e_fallback = p_e is not None
    resolved_basis = dict(basis or {})
    if not resolved_basis:
        resolved_basis = {"flows": "TTM" if any(
            k in fin for k in ("net_income_ttm", "revenue_ttm", "operating_cashflow_ttm")
        ) else "as reported"}
    resolved_basis["p_e_fallback"] = p_e_fallback
    resolved_basis["label"] = _basis_label(
        str(resolved_basis.get("flows") or "as reported"),
        resolved_basis.get("flows_period"),
        resolved_basis.get("balance"),
    )
    return {
        "basis": resolved_basis,
        "ev": ev,
        "ev_ebitda": _ratio(ev, ebitda),
        "ev_ebit": _ratio(ev, op),
        "ev_sales": _ratio(ev, rev),
        "price_to_earnings": p_e,
        "price_to_book": _ratio(mc, te),
        "price_to_sales": _ratio(mc, rev),
        "price_to_cash_flow": _ratio(mc, ocf),
        "price_to_free_cash_flow": _ratio(mc, fcf),
        "return_on_equity": _ratio(ni, te),
        "return_on_assets": _ratio(ni, ta),
        "debt_to_equity": (_ratio(debt, te) if te and _ratio(debt, te) is not None and _ratio(debt, te) <= 10 else None),
        "current": current,
        "quick": quick,
        "cash_ratio": _ratio(cash, cl) if cl_ok else None,
        "dividend_yield": (
            _ratio(divs_abs, mc)
            if (divs_abs is not None and mc and _ratio(divs_abs, mc) is not None and _ratio(divs_abs, mc) <= 0.25)
            else None
        ),
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
    basis = ratios.get("basis") or {}
    lines = [f"- basis: {basis['label']}"] if basis.get("label") else []
    fallback_note = " (basis: price / reported EPS)" if basis.get("p_e_fallback") else ""
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
            note = fallback_note if key == "price_to_earnings" else ""
            lines.append(f"- {label}: {float(v):.2f}{note}")
    return "\n".join(lines)


__all__ = ["compute_ratios", "render_ratios", "RENDER_ORDER"]
