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

The block also carries the FundamentalScore library's families
(``docs/scores/FundamentalScore.md`` §3.6/§4.1; formulas from the owner's
``Strategies/scores/fundamental_score.md``), so one call is their producer:

  Coverage (§9)      EBIT/Interest, EBITDA/Interest, CFO/Interest, FCCR, DSCR
  Cash flow (§2/§3)  OCF yield/margin, FCF yield/margin, FCF/NI, CFO/NI,
                     FCF/EBITDA, CFO/EBITDA, CapEx/OCF, EV/FCF, OCF-vs-NI growth
  Leverage (§8)      net debt, net debt/EBITDA, debt/EBITDA, debt/assets,
                     net debt/FCF, cash/debt, net cash yield, OCF/debt
  Capital returns    ROIC, ROCE, Return on Capital, invested-capital turnover,
  (§1/§10)           buyback yield, shareholder yield, net-issuance yield
  Margins (§5/§28)   gross/EBIT/EBITDA/net margin + gross & operating margin
                     stability (−σ) and ROIC stability
  FCF (§3)           normalized FCF yield, FCF stability (−σ of FCF margin),
                     cash-conversion stability (−σ of CFO/NI)
  Growth/WC (§7)     asset/debt/receivables/inventory growth, WC/assets
  Turnover (§6)      DIO, DSO, DPO, cash-conversion cycle, the turnover ratios
  Bonds (§14)        earnings-yield and FCF-yield spreads over a passed-in
                     risk-free rate (this module never fetches one)
  SBC (§55,          SBC, SBC/revenue, SBC-adjusted FCF and SBC/FCF - the
  ValuationScore)    economic cash flow = reported FCF - us-gaap:ShareBasedCompensation,
                     read from the one XBRL concept whose definition is the
                     cash-flow add-back; a filer without it refuses with a reason
                     rather than adjusting by zero. Engine keys only: the vendor
                     statements carry no SBC row, so they are NOT in RENDER_ORDER
                     (see the note there) - the read renders through the
                     quality-factors leaf, which reads the SEC series.

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


#: Scale factor making the MAD of a normal sample equal its standard deviation
#: (library §23: ``RobustZ = (X - median) / (1.4826 * MAD)``). Absent from the
#: tree before this module - the cross-section layer standardises on mean/std.
MAD_SCALE = 1.4826

#: Smallest |denominator| this module divides by. A coverage or leverage ratio
#: over a near-zero denominator (no interest expense, no debt, no EBITDA) is a
#: units artifact, not a measurement, so the key is refused as ``None``.
_MIN_DENOM = 1e-6


def _latest(v):
    """Newest value of a canonical item (flat, or ``{"current": ..}``)."""
    if isinstance(v, dict):
        return v.get("current", v.get("value"))
    return v


def _prior(v):
    """Prior-period value of a canonical item (``None`` when not carried)."""
    return v.get("prior") if isinstance(v, dict) else None


def _series_entry(fin: dict, key: str):
    """A canonical series for ``key`` as ``{"values", "years"}``, or ``None``.

    Two shapes are accepted, both emitted by ``statement_parsing``: the
    multi-year ``<key>_series`` stack (``fetch_ticker``'s ``annual_series`` /
    ``sec_annual_series``) and a ``{current, prior}`` pair (the moomoo merged
    payload). One point is not a series - a stability needs at least two.
    """
    entry = fin.get(f"{key}_series")
    if isinstance(entry, dict) and len(entry.get("values") or ()) >= 2:
        return {
            "values": [float(v) for v in entry["values"] if v is not None],
            "years": list(entry.get("years") or []),
        }
    cur, prior = _latest(fin.get(key)), _prior(fin.get(key))
    if cur is not None and prior is not None:
        return {"values": [float(prior), float(cur)], "years": []}
    return None


def _series_ratio(fin: dict, num_key: str, den_key: str):
    """Point-wise ``num / den`` across two canonical series, or ``None``.

    Aligned by fiscal year when both stacks carry years; otherwise used only
    when the two have equal length (the ``{current, prior}`` shape). A zero
    denominator drops that point; fewer than two points is not a series.
    """
    n, d = _series_entry(fin, num_key), _series_entry(fin, den_key)
    if not n or not d:
        return None
    if n["years"] and d["years"]:
        d_by_year = dict(zip(d["years"], d["values"], strict=False))
        vals = [
            nv / d_by_year[y]
            for y, nv in zip(n["years"], n["values"], strict=False)
            if y in d_by_year and d_by_year[y]
        ]
    elif len(n["values"]) == len(d["values"]):
        vals = [a / b for a, b in zip(n["values"], d["values"], strict=False) if b]
    else:
        return None
    return vals if len(vals) >= 2 else None


def _first_difference(values):
    """Series growth over the last step, or ``None`` on a missing/zero base."""
    if not values or len(values) < 2:
        return None
    cur, prev = values[-1], values[-2]
    if cur is None or prev is None or prev == 0:
        return None
    return (float(cur) - float(prev)) / float(prev)


def _median(values):
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def _stdev(values):
    """Sample standard deviation, or ``None`` below two points."""
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    return (sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5


def _stability(values):
    """Library §28 in its signed form: ``-sigma``, so larger = more stable."""
    if not values:
        return None
    sd = _stdev(values)
    return None if sd is None else -sd


def _ratio_min(n, d, min_abs: float = _MIN_DENOM):
    """``n / d`` guarded against a ``None`` and a near-zero denominator."""
    if n is None or d is None:
        return None
    try:
        n = float(n)
        d = float(d)
    except (TypeError, ValueError):
        return None
    if abs(d) < min_abs:
        return None
    return n / d


def _scale(v, k: float):
    return None if v is None else float(v) * k


def _avg_basis(fin: dict, key: str, fallback):
    """Average of a ``{current, prior}`` balance pair, else the flat value.

    The library's turnover ratios divide by *average* inventory / receivables /
    payables (§6). A flat canonical value has no prior, so it is used as the
    point-in-time basis rather than refused - the caller's ``basis`` block
    still states which period the block came from.
    """
    cur, prior = _latest(fin.get(key)), _prior(fin.get(key))
    if cur is not None and prior is not None:
        return (float(cur) + float(prior)) / 2.0
    return fallback


def _ebitda(op, dep):
    """EBITDA = EBIT + D&A, or ``None`` when either leg is missing.

    One helper for the coverage family (FUND-1) and the leverage family
    (FUND-5); ``compute_ratios`` used to build this inline for ``ev_ebitda``
    and drop it.
    """
    if op is None or dep is None:
        return None
    return op + dep


def robust_z(values) -> list:
    """Median/MAD z-scores of ``values`` (library §23), element-aligned.

    ``RobustZ = (X - median) / (1.4826 * MAD)`` with ``MAD`` the median absolute
    deviation. ``None`` inputs stay ``None``; fewer than three usable points or a
    zero MAD (no dispersion to standardise against) returns all-``None`` rather
    than a fabricated scale.
    """
    out: list = [None] * len(values)
    usable = [float(v) for v in values if v is not None]
    if len(usable) < 3:
        return out
    med = _median(usable)
    mad = _median([abs(v - med) for v in usable])
    if not mad:
        return out
    scale = MAD_SCALE * mad
    for i, v in enumerate(values):
        if v is not None:
            out[i] = (float(v) - med) / scale
    return out


def _effective_tax_rate(fin: dict, tax_rate: float | None):
    """Caller's rate, else the effective rate ``tax_expense / (NI + tax)``."""
    if tax_rate is not None:
        rate = float(tax_rate)
        return rate if 0.0 <= rate <= 1.0 else None
    tax = _flow(fin, "tax_expense")
    ni = _flow(fin, "net_income_ttm", "net_income")
    if tax is None or ni is None or (ni + tax) <= 0:
        return None
    rate = tax / (ni + tax)
    return rate if 0.0 <= rate <= 1.0 else None


def return_on_capital(fin: dict, *, tax_rate: float | None = None) -> dict:
    """The library's level capital-return family (§1, §6).

    ``invested_capital = total_debt + total_equity - cash`` (library §1);
    ``capital_employed = total_assets - current_liabilities`` (the standard
    employed-capital definition the library leaves to the reader). ``NOPAT =
    EBIT * (1 - tax_rate)``, with ``tax_rate`` the caller's, else the effective
    rate ``tax_expense / (net_income + tax_expense)``.

    This is the **level** producer the tree lacked: ``strategies/capex_quality``
    exposes only the 3-lag incremental ``incr_roic``, and
    ``agents/utils/value_dip_tools.py`` builds ``invested_capital`` per year
    (``:435-513``) and a local ``roic`` (``:1342``, ``:1476``) that never leaves
    its own module - **duplication reported, not fixed here** (that file is not
    this module's). Every value is ``None`` with a ``reason`` when an input is
    missing; no fetching happens here.

    Returns ``{"ebit", "tax_rate", "nopat", "invested_capital",
    "capital_employed", "roic", "roce", "return_on_capital",
    "invested_capital_turnover", "reason"}``.
    """
    op = _flow(fin, "operating_income_ttm", "operating_income")
    debt = _num(fin.get("total_debt"))
    te = _num(fin.get("total_equity"))
    cash = _num(fin.get("cash"))
    ta = _num(fin.get("total_assets"))
    cl = _num(fin.get("current_liabilities"))
    rev = _flow(fin, "revenue_ttm", "revenue")

    invested_capital = None
    if debt is not None and te is not None:
        invested_capital = debt + te - (cash or 0.0)
    capital_employed = ta - cl if (ta is not None and cl is not None) else None

    rate = _effective_tax_rate(fin, tax_rate)
    nopat = op * (1.0 - rate) if (op is not None and rate is not None) else None

    roic = _ratio_min(nopat, invested_capital)
    roce = _ratio_min(op, capital_employed)
    roc = _ratio_min(op, invested_capital)
    turnover = _ratio_min(rev, invested_capital)

    reason = None
    if invested_capital is None:
        reason = "no invested capital (needs total_debt and total_equity)"
    elif invested_capital <= 0:
        reason = "invested capital is not positive (cash exceeds debt + equity)"
    elif roic is None and rate is None:
        reason = (
            "no tax rate (pass tax_rate, or supply tax_expense + net_income "
            "to derive the effective rate); ROCE and turnover are still computed"
        )
    return {
        "ebit": op,
        "tax_rate": rate,
        "nopat": nopat,
        "invested_capital": invested_capital,
        "capital_employed": capital_employed,
        "roic": roic,
        "roce": roce,
        "return_on_capital": roc,
        "invested_capital_turnover": turnover,
        "reason": reason,
    }


def shareholder_yield(fin: dict, *, market_cap: float | None = None,
                      price: float | None = None) -> dict:
    """Buyback yield and total shareholder yield from ``share_buybacks`` (§10).

    **Sign convention (stated, because the two vendors disagree):**
    ``share_buybacks`` is the cash spent repurchasing shares and is taken
    ``abs()`` - yfinance/Tiingo file it negative (an outflow), moomoo as a
    positive magnitude. ``buyback_yield`` is therefore a positive gross
    repurchase yield. ``net_issuance_yield`` keeps the library's §11 sign -
    *negative* net issuance means net buybacks - and subtracts the issuance leg
    only when a ``shares`` ``{current, prior}`` pair and a ``price`` exist; the
    canonical vocabulary carries no "proceeds from issuance" line, so the leg is
    ``None`` with a reason otherwise.

    ``shareholder_yield = dividend_yield + buyback_yield`` requires **both**
    legs (a partial sum under that name would understate the yield); either may
    be ``None`` with the reason on the key's absence. ``market_cap`` may be
    passed to avoid re-reading ``fin``. No fetching.

    Returns ``{"dividend_yield", "buyback_yield", "shareholder_yield",
    "net_issuance_yield", "reason"}``.
    """
    mc = market_cap if market_cap is not None else _num(fin.get("market_cap"))
    divs = _flow(fin, "dividends_paid_ttm", "dividends_paid")
    buybacks = _flow(fin, "share_buybacks_ttm", "share_buybacks")
    divs_abs = abs(divs) if divs is not None else None
    buy_abs = abs(buybacks) if buybacks is not None else None

    dividend_yield = _ratio_min(divs_abs, mc)
    buyback_yield = _ratio_min(buy_abs, mc)
    total = (
        dividend_yield + buyback_yield
        if (dividend_yield is not None and buyback_yield is not None)
        else None
    )

    net_issuance_yield = None
    if price is not None and mc:
        cur, prior = _latest(fin.get("shares")), _prior(fin.get("shares"))
        if cur is not None and prior is not None:
            net_issuance_yield = -((float(cur) - float(prior)) * float(price)) / float(mc)

    reason = None
    if mc is None or not mc:
        reason = "no market cap"
    elif buybacks is None:
        reason = "no share_buybacks line in the canonical statements"
    elif dividend_yield is None:
        reason = "no dividends_paid line, so shareholder yield cannot be summed"
    elif net_issuance_yield is None:
        reason = (
            "net-issuance yield needs a shares {current, prior} pair and a price; "
            "gross buyback yield is unaffected"
        )
    return {
        "dividend_yield": dividend_yield,
        "buyback_yield": buyback_yield,
        "shareholder_yield": total,
        "net_issuance_yield": net_issuance_yield,
        "reason": reason,
    }


#: The XBRL concept this read is allowed to use for the SBC leg, named in full
#: so a refusal can say exactly what it looked for. It is ``sec_edgar._TAG_MAP``'s
#: "Share-based compensation" row, surfaced under the canonical key ``sbc``.
SBC_XBRL_TAG = "us-gaap:ShareBasedCompensation"

#: The candidate that is deliberately NOT used as a fallback, with the live
#: measurement that disqualifies it (see the docstring's refusal note).
SBC_REJECTED_TAG = "us-gaap:AllocatedShareBasedCompensationExpense"


def sbc_adjusted_fcf(
    fin: dict,
    *,
    fcf: float | None = None,
    revenue: float | None = None,
    market_cap: float | None = None,
) -> dict:
    """Share-based-compensation adjustment to free cash flow (ValuationScore §55).

    The library keeps two measures rather than one:

        ReportedFCF  = OCF - |capex|          (what ``compute_ratios`` publishes)
        EconomicFCF  = ReportedFCF - SBC      (the same cash flow with the
                                               non-cash equity compensation
                                               charged as the cost it is)

    ``SBC`` is the **cash-flow statement's non-cash add-back**, i.e.
    ``us-gaap:ShareBasedCompensation`` (``SBC_XBRL_TAG``; the label
    ``sec_edgar._TAG_MAP`` maps to the canonical ``sbc`` key, carried as a flat
    value by the panel and as ``sbc_series`` on the ``with_sec_series`` path).
    It is the exact amount OCF adds back, so subtracting it again is the
    economic-cost read and not a double count. The companion ratio the external
    quality review names beside the other quality metrics is
    ``SBC / Revenue`` (``altman_composite.md``, Quality pillar, `SBC/Revenue`).

    **Refusal, never a substituted zero.** A filer that does not carry the tag
    gets ``sbc=None``, ``economic_fcf=None`` and a ``reason`` that names the
    missing concept - ``EconomicFCF`` is *not* set equal to ``ReportedFCF``,
    because "no SBC line" is not "no SBC cost" and the neutral substitution is
    the failure ``EventScore.md`` §8 records. The nearest alternative concept,
    ``AllocatedShareBasedCompensationExpense`` (``SBC_REJECTED_TAG``), is the
    INCOME-STATEMENT allocated expense: measured 2026-09-27 on SIMO FY2025 the
    two are 26,283,000 vs 203,305,000 (7.7x), so using it as a fallback would
    silently redefine the factor from one name to the next.

    ``fcf`` / ``revenue`` / ``market_cap`` are optional pass-throughs so a caller
    that already computed them (``compute_ratios``) prints one number and no
    second formula exists. Without them, FCF is ``OCF - |capex|`` under this
    module's own ``abs()`` convention (vendors disagree on the capex sign) and
    revenue is the latest canonical/TTM figure.

    Returns ``{"sbc", "reported_fcf", "economic_fcf", "sbc_to_revenue",
    "sbc_to_ocf", "sbc_to_fcf", "economic_fcf_yield", "xbrl_tag", "basis",
    "reason"}``; every ratio is ``None`` when its own denominator is missing.
    No fetching, no exceptions.
    """
    def _leg(*flat_keys: str, series_key: str, prefer_series: bool):
        """Latest value of a leg, preferring the basis the SBC leg came from.

        When SBC is read from the SEC 10-K ``sbc_series`` the cash-flow legs
        follow it to the series too, so the adjustment never subtracts one
        fiscal year's equity compensation from another year's cash flow.
        """
        if prefer_series:
            entry = _series_entry(fin, series_key)
            if entry:
                return _num(entry["values"][-1])
        value = _num(_flow(fin, *flat_keys))
        if value is None:
            entry = _series_entry(fin, series_key)
            if entry:
                value = _num(entry["values"][-1])
        return value

    sbc = _num(_flow(fin, "sbc_ttm", "sbc"))
    sbc_from_series = False
    if sbc is None:
        entry = _series_entry(fin, "sbc")
        if entry:
            sbc = _num(entry["values"][-1])
            sbc_from_series = True

    ocf = _leg(
        "operating_cashflow_ttm",
        "operating_cashflow",
        series_key="operating_cashflow",
        prefer_series=sbc_from_series,
    )
    capex = _leg("capex_ttm", "capex", series_key="capex", prefer_series=sbc_from_series)
    rev = revenue if revenue is not None else _leg(
        "revenue_ttm", "revenue", series_key="revenue", prefer_series=sbc_from_series
    )
    mc = market_cap if market_cap is not None else _num(fin.get("market_cap"))

    reported = _num(fcf)
    if reported is None:
        reported = (
            _sub(ocf, abs(capex)) if (ocf is not None and capex is not None) else None
        )

    economic = _sub(reported, sbc) if (reported is not None and sbc is not None) else None

    reason = None
    if sbc is None:
        reason = (
            f"no {SBC_XBRL_TAG} value for this filer: the canonical statements carry "
            f"no share-based-compensation line, so the SBC adjustment is refused "
            f"({SBC_REJECTED_TAG} is the income-statement allocated expense, a "
            f"different quantity, and is not substituted)"
        )
    elif reported is None:
        reason = (
            "reported free cash flow unavailable (needs operating cash flow and capex), "
            "so the SBC adjustment has no base"
        )

    if sbc is None:
        sbc_basis = "no SBC line"
    elif _num(fin.get("sbc_ttm")) is not None:
        sbc_basis = "ttm"
    elif sbc_from_series:
        sbc_basis = "as reported (SEC 10-K annual series)"
    else:
        sbc_basis = "as reported"

    return {
        "sbc": sbc,
        "reported_fcf": reported,
        "economic_fcf": economic,
        "sbc_to_revenue": _ratio_min(sbc, rev),
        "sbc_to_ocf": _ratio_min(sbc, ocf),
        # Only meaningful against a POSITIVE reported FCF: a ratio of a
        # positive SBC to a negative FCF flips sign and reads as a "credit".
        "sbc_to_fcf": (
            _ratio_min(sbc, reported) if (reported is not None and reported > 0) else None
        ),
        "economic_fcf_yield": _ratio_min(economic, mc),
        "xbrl_tag": SBC_XBRL_TAG if sbc is not None else None,
        "basis": f"{sbc_basis}; SBC = {SBC_XBRL_TAG}" if sbc is not None else sbc_basis,
        "reason": reason,
    }


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
                   basis: dict | None = None,
                   risk_free: float | None = None) -> dict:
    """Compute the full ratio block from canonical line items.

    ``fin`` is the canonical line-items dict (see ``scripts/value_screener``
    ``_ROW_ALIASES``): market_cap, total_debt, cash, operating_income,
    depreciation, revenue, net_income, total_equity, total_assets,
    operating_cashflow, capex, current_assets, current_liabilities, inventory,
    dividends_paid - plus the optional ``*_ttm`` flow keys, which take
    precedence over their reported counterparts, and the additional family
    inputs ``interest_expense``, ``debt_repayment``, ``share_buybacks``,
    ``cogs``, ``net_receivables``, ``payables``, ``tax_expense``,
    ``working_capital`` and the canonical ``*_series`` stacks. ``price`` is the
    current price: it is the P/E fallback (``price / eps``) when no earnings
    figure is available at all, and is annotated as such in the rendered block.
    ``risk_free`` is the risk-free rate for the §14 bond-spread keys - this
    module **never fetches one** (no vendor calls), so it is an argument; when
    omitted the two spread keys are ``None``.

    ``basis`` states the periods the inputs came from
    (``{"flows", "flows_period", "balance"}``); when omitted it is inferred
    from whether a ``*_ttm`` key is present. Returns a dict with one key per
    ratio plus ``basis``; a key is absent->None when its input is missing.
    Never fabricates. This function is additive: every pre-existing key keeps
    its name and its value.
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
    # Family inputs (FUND-1/3/4/5/18): canonical keys the merge already carries
    # and nothing read. ``interest_expense`` and ``share_buybacks`` were aliases
    # with zero consumers before this block.
    ie = _flow(fin, "interest_expense_ttm", "interest_expense")
    dp = _flow(fin, "debt_repayment_ttm", "debt_repayment")
    cogs = _flow(fin, "cogs_ttm", "cogs")
    ar = _flow(fin, "net_receivables_ttm", "net_receivables")
    ap = _flow(fin, "payables_ttm", "payables")
    wc = _num(fin.get("working_capital"))
    if wc is None:
        wc = _sub(ca, cl)

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

    # One EBITDA helper for the coverage (FUND-1), cash-flow (FUND-4) and
    # leverage (FUND-5) families; same value the inline expression produced.
    ebitda = _ebitda(op, dep)
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

    # --- FUND-1: coverage / debt-service family (§9) ----------------------
    # FCCR's "fixed charges" are proxied by interest_expense: the canonical
    # vocabulary carries no lease/rental line, and inventing one would be a
    # fabricated denominator. DSCR's debt service = interest + debt repaid
    # (the ``debt_repayment`` alias), cash available = OCF.
    fixed_charge_coverage = _ratio_min(_add(op, ie), _add(ie, ie))
    debt_service_coverage = _ratio_min(ocf, _add(ie, abs(dp)) if dp is not None else None)

    # --- FUND-4: cash-flow family (§2/§3) ---------------------------------
    fcf_yield = _ratio_min(fcf, mc)
    earnings_yield = _ratio_min(ni, mc)
    ocf_growth = _first_difference((_series_entry(fin, "operating_cashflow") or {}).get("values"))
    ni_growth = _first_difference((_series_entry(fin, "net_income") or {}).get("values"))

    # --- FUND-5: leverage family (§8) -------------------------------------
    net_debt = _sub(debt, cash)

    # --- FUND-2 / FUND-3: capital returns and capital allocation ----------
    cap = return_on_capital(fin)
    sy = shareholder_yield(fin, market_cap=mc)
    # ValuationScore §55: the SBC-adjusted (economic) FCF, read from the same
    # ``fcf``/``rev`` this block publishes so the two measures of one cash flow
    # cannot drift apart.
    sbc_read = sbc_adjusted_fcf(fin, fcf=fcf, revenue=rev, market_cap=mc)

    # --- FUND-6: margins and the stability legs (§5/§28) ------------------
    gm = _num(fin.get("gross_margin"))
    if gm is None:
        gm = _ratio_min(_sub(rev, cogs), rev)
    gm_series = _series_ratio(fin, "gross_profit", "revenue")
    if gm_series is None and isinstance(fin.get("gross_margin"), dict):
        _gm_cur, _gm_prv = _latest(fin.get("gross_margin")), _prior(fin.get("gross_margin"))
        if _gm_cur is not None and _gm_prv is not None:
            gm_series = [float(_gm_prv), float(_gm_cur)]

    # --- FUND-8: FCF stability (§3), read from the canonical series -------
    # ``fcf_series`` exists on the SEC-XBRL path (``sec_annual_series`` derives
    # it) and, when a vendor payload carries current+prior OCF/capex, the pair
    # is used. The plain vendor stack has no capex series, so FCF stability is
    # None there - stated, not fabricated.
    fcf_values = (_series_entry(fin, "fcf") or {}).get("values")
    if fcf_values is None:
        _ocf_e, _capex_e = _series_entry(fin, "operating_cashflow"), _series_entry(fin, "capex")
        if _ocf_e and _capex_e and len(_ocf_e["values"]) == len(_capex_e["values"]):
            fcf_values = [
                a - abs(b) for a, b in zip(_ocf_e["values"], _capex_e["values"], strict=False)
            ]
    rev_e = _series_entry(fin, "revenue")
    fcf_margin_series = None
    if fcf_values and rev_e and len(fcf_values) == len(rev_e["values"]):
        fcf_margin_series = [
            a / b for a, b in zip(fcf_values, rev_e["values"], strict=False) if b
        ]
    normalized_fcf = _median(fcf_values) if fcf_values else None

    # --- RISK-18 cash-burn risk (§48) -------------------------------------
    # The library's own CFD = (FCF_t - FCF_{t-1}) / |FCF_{t-1}|, read from the
    # SAME canonical series the stability leg reads, so FCF_t and FCF_{t-1}
    # cannot drift apart. A zero prior FCF is refused: the library's +epsilon
    # guard would divide by nothing. (The runway half lives in the returned
    # dict below, where the current ``cash`` and ``fcf`` are in scope.)
    fcf_deterioration = None
    if fcf_values and len(fcf_values) >= 2:
        _fcf_t, _fcf_prev = fcf_values[-1], fcf_values[-2]
        if _fcf_t is not None and _fcf_prev not in (None, 0):
            fcf_deterioration = (_fcf_t - _fcf_prev) / abs(_fcf_prev)

    # --- FUND-18: turnover / working-capital family (§6) ------------------
    inv_basis = _avg_basis(fin, "inventory", inv)
    ar_basis = _avg_basis(fin, "net_receivables", ar)
    ap_basis = _avg_basis(fin, "payables", ap)
    dio = _ratio_min(_scale(inv_basis, 365.0), cogs)
    dso = _ratio_min(_scale(ar_basis, 365.0), rev)
    dpo = _ratio_min(_scale(ap_basis, 365.0), cogs)
    ccc = _sub(_add(dio, dso), dpo)

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
        # ---- FUND-1 coverage / debt-service (§9) -------------------------
        "ebitda": ebitda,
        "interest_coverage": _ratio_min(op, ie),
        "ebitda_interest_coverage": _ratio_min(ebitda, ie),
        "cash_interest_coverage": _ratio_min(ocf, ie),
        "fixed_charge_coverage": fixed_charge_coverage,
        "debt_service_coverage": debt_service_coverage,
        # ---- FUND-4 cash flow (§2/§3) ------------------------------------
        "ocf_yield": _ratio_min(ocf, mc),
        "fcf_yield": fcf_yield,
        "earnings_yield": earnings_yield,
        "ocf_margin": _ratio_min(ocf, rev),
        "fcf_margin": _ratio_min(fcf, rev),
        "ocf_to_net_income": _ratio_min(ocf, ni),
        "fcf_to_net_income": _ratio_min(fcf, ni),
        "ocf_to_ebitda": _ratio_min(ocf, ebitda),
        "fcf_to_ebitda": _ratio_min(fcf, ebitda),
        "capex_to_ocf": _ratio_min(abs(capex), ocf) if capex is not None else None,
        "ev_to_fcf": _ratio_min(ev, fcf),
        "ocf_ni_growth_divergence": (
            ocf_growth - ni_growth
            if (ocf_growth is not None and ni_growth is not None)
            else None
        ),
        # ---- FUND-5 leverage (§8) ----------------------------------------
        "net_debt": net_debt,
        "net_debt_to_ebitda": _ratio_min(net_debt, ebitda),
        "debt_to_ebitda": _ratio_min(debt, ebitda),
        "debt_to_assets": _ratio_min(debt, ta),
        "net_debt_to_fcf": _ratio_min(net_debt, fcf),
        "cash_to_debt": _ratio_min(cash, debt),
        "net_cash_yield": _ratio_min(_sub(cash, debt), mc),
        "ocf_to_debt": _ratio_min(ocf, debt),
        # ---- FUND-2 capital returns (§1/§6) ------------------------------
        "invested_capital": cap["invested_capital"],
        "capital_employed": cap["capital_employed"],
        "roic": cap["roic"],
        "roce": cap["roce"],
        "return_on_capital": cap["return_on_capital"],
        "invested_capital_turnover": cap["invested_capital_turnover"],
        # ---- FUND-3 capital allocation (§10/§11) -------------------------
        "buyback_yield": sy["buyback_yield"],
        "shareholder_yield": sy["shareholder_yield"],
        "net_issuance_yield": sy["net_issuance_yield"],
        # ---- ValuationScore §55: SBC adjustment --------------------------
        # ``sbc_adjusted_fcf`` owns the formula; these four keys are the read's
        # own output, so no second FCF adjustment exists anywhere. They are NOT
        # in RENDER_ORDER: the vendor statements carry no SBC row, so the
        # rendering leaf would print four permanent ``n/a`` lines (see the note
        # on RENDER_ORDER).
        "sbc": sbc_read["sbc"],
        "sbc_to_revenue": sbc_read["sbc_to_revenue"],
        "sbc_adjusted_fcf": sbc_read["economic_fcf"],
        "sbc_to_fcf": sbc_read["sbc_to_fcf"],
        # ---- FUND-6 margins (§5) -----------------------------------------
        "gross_margin": gm,
        "ebit_margin": _ratio_min(op, rev),
        "ebitda_margin": _ratio_min(ebitda, rev),
        "net_margin": _ratio_min(ni, rev),
        "gross_margin_stability": _stability(gm_series),
        "operating_margin_stability": _stability(_series_ratio(fin, "operating_income", "revenue")),
        # The margin series themselves (lists, not rendered rows): the EBIT-margin
        # series is what the stability leg consumes, exposed so a caller need not
        # re-derive it from the canonical payload.
        "gross_margin_series": gm_series,
        "ebit_margin_series": _series_ratio(fin, "operating_income", "revenue"),
        # No NOPAT / invested-capital series exists in the canonical payload,
        # so a ROIC dispersion cannot be measured from it - refused, not faked.
        "roic_stability": None,
        # ---- FUND-8 FCF stability (§3) -----------------------------------
        "normalized_fcf": normalized_fcf,
        "normalized_fcf_yield": _ratio_min(normalized_fcf, mc),
        "fcf_stability": _stability(fcf_margin_series),
        "cash_conversion_stability": _stability(
            _series_ratio(fin, "operating_cashflow", "net_income")
        ),
        # ---- RISK-18 cash-burn risk (§48) --------------------------------
        # CashRunway = Cash / |FCF_negative|. Only meaningful while FCF is
        # NEGATIVE (it is funding a burn), so a positive/zero FCF yields None
        # rather than an infinite ratio - the reader sees `free_cash_flow`
        # beside it and knows which case it is. Units: YEARS of the current
        # annual/TTM burn.
        "cash_runway_years": (_ratio_min(cash, -fcf) if (fcf is not None and fcf < 0) else None),
        # CFD = (FCF_t - FCF_{t-1}) / |FCF_{t-1}|, from the canonical series.
        "fcf_deterioration": fcf_deterioration,
        # ---- FUND-9 growth / working capital (§7) ------------------------
        "asset_growth": _first_difference(
            (_series_entry(fin, "total_assets") or {}).get("values")
        ),
        "debt_growth": _first_difference((_series_entry(fin, "total_debt") or {}).get("values")),
        "receivables_growth": _first_difference(
            (_series_entry(fin, "net_receivables") or {}).get("values")
        ),
        "inventory_growth": _first_difference(
            (_series_entry(fin, "inventory") or {}).get("values")
        ),
        "working_capital_to_assets": _ratio_min(wc, ta),
        # ---- FUND-18 turnover / cash-conversion cycle (§6) ---------------
        "dio": dio,
        "dso": dso,
        "dpo": dpo,
        "cash_conversion_cycle": ccc,
        "inventory_turnover": _ratio_min(cogs, inv_basis),
        "receivables_turnover": _ratio_min(rev, ar_basis),
        "payables_turnover": _ratio_min(cogs, ap_basis),
        "working_capital_turnover": _ratio_min(rev, wc),
        "asset_turnover": _ratio_min(rev, ta),
        # ---- FUND-19 bond spread (§14; risk-free passed in, never fetched)
        "earnings_yield_over_bonds": (
            _sub(earnings_yield, risk_free)
            if (earnings_yield is not None and risk_free is not None)
            else None
        ),
        "fcf_yield_over_bonds": (
            _sub(fcf_yield, risk_free)
            if (fcf_yield is not None and risk_free is not None)
            else None
        ),
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
    # FundamentalScore library families (docs/scores/FundamentalScore.md §3.6).
    # The analyst ratio leaf renders every one of these automatically, so the
    # computed numbers reach a reader instead of stopping at this function.
    ("ebitda", "EBITDA", "int"),
    ("interest_coverage", "EBIT/interest", "float"),
    ("ebitda_interest_coverage", "EBITDA/interest", "float"),
    ("cash_interest_coverage", "CFO/interest", "float"),
    ("fixed_charge_coverage", "FCCR", "float"),
    ("debt_service_coverage", "DSCR", "float"),
    ("ocf_yield", "OCF yield", "pct"),
    ("fcf_yield", "FCF yield", "pct"),
    ("earnings_yield", "Earnings yield", "pct"),
    ("ocf_margin", "OCF margin", "pct"),
    ("fcf_margin", "FCF margin", "pct"),
    ("ocf_to_net_income", "CFO/NI", "float"),
    ("fcf_to_net_income", "FCF/NI", "float"),
    ("ocf_to_ebitda", "CFO/EBITDA", "float"),
    ("fcf_to_ebitda", "FCF/EBITDA", "float"),
    ("capex_to_ocf", "CapEx/OCF", "float"),
    ("ev_to_fcf", "EV/FCF", "float"),
    ("ocf_ni_growth_divergence", "OCF-NI growth", "pct"),
    ("net_debt", "Net debt", "int"),
    ("net_debt_to_ebitda", "Net debt/EBITDA", "float"),
    ("debt_to_ebitda", "Debt/EBITDA", "float"),
    ("debt_to_assets", "Debt/assets", "pct"),
    ("net_debt_to_fcf", "Net debt/FCF", "float"),
    ("cash_to_debt", "Cash/debt", "float"),
    ("net_cash_yield", "Net cash yield", "pct"),
    ("ocf_to_debt", "OCF/debt", "pct"),
    ("invested_capital", "Invested capital", "int"),
    ("capital_employed", "Capital employed", "int"),
    ("roic", "ROIC", "pct"),
    ("roce", "ROCE", "pct"),
    ("return_on_capital", "ROC (EBIT/IC)", "pct"),
    ("invested_capital_turnover", "IC turnover", "float"),
    ("buyback_yield", "Buyback yield", "pct"),
    ("shareholder_yield", "Shareholder yield", "pct"),
    ("net_issuance_yield", "Net issuance yield", "pct"),
    # No SBC rows here on purpose. ``compute_ratios`` carries the §55 keys
    # (``sbc``/``sbc_to_revenue``/``sbc_adjusted_fcf``/``sbc_to_fcf``) but this
    # list is what the analyst ratio leaf renders, and that leaf reads the
    # VENDOR statements - which carry no share-based-compensation row at all
    # (verified live 2026-09-27 on MSFT's moomoo annual cash-flow statement:
    # D&A and working capital are itemised, the SBC add-back is not). Rendering
    # them here would print four permanent ``n/a`` lines in every fundamentals
    # report. The read reaches the model through
    # ``quant_formula_tools.get_quality_factors``, which fetches the SEC XBRL
    # series the tag lives in.
    ("gross_margin", "Gross margin", "pct"),
    ("ebit_margin", "EBIT margin", "pct"),
    ("ebitda_margin", "EBITDA margin", "pct"),
    ("net_margin", "Net margin", "pct"),
    ("gross_margin_stability", "GM stability", "float"),
    ("operating_margin_stability", "OM stability", "float"),
    ("roic_stability", "ROIC stability", "float"),
    ("normalized_fcf", "Normalized FCF", "int"),
    ("normalized_fcf_yield", "Normalized FCF yield", "pct"),
    ("fcf_stability", "FCF stability", "float"),
    ("cash_conversion_stability", "CFO/NI stability", "float"),
    # RISK-18 cash-burn risk (§48, RiskScore.md §8.2): the runway is YEARS of
    # the current burn and prints `n/a` whenever FCF is not funding one; the
    # deterioration leg is the library's signed YoY FCF change.
    ("cash_runway_years", "Cash runway (years)", "float"),
    ("fcf_deterioration", "FCF deterioration", "pct"),
    ("asset_growth", "Asset growth", "pct"),
    ("debt_growth", "Debt growth", "pct"),
    ("receivables_growth", "AR growth", "pct"),
    ("inventory_growth", "Inventory growth", "pct"),
    ("working_capital_to_assets", "WC/assets", "pct"),
    ("dio", "DIO", "float"),
    ("dso", "DSO", "float"),
    ("dpo", "DPO", "float"),
    ("cash_conversion_cycle", "CCC", "float"),
    ("inventory_turnover", "Inventory turnover", "float"),
    ("receivables_turnover", "Receivables turnover", "float"),
    ("payables_turnover", "Payables turnover", "float"),
    ("working_capital_turnover", "WC turnover", "float"),
    ("asset_turnover", "Asset turnover", "float"),
    ("earnings_yield_over_bonds", "Earnings yield - rf", "pct"),
    ("fcf_yield_over_bonds", "FCF yield - rf", "pct"),
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


__all__ = [
    "compute_ratios",
    "render_ratios",
    "return_on_capital",
    "shareholder_yield",
    "sbc_adjusted_fcf",
    "SBC_XBRL_TAG",
    "robust_z",
    "RENDER_ORDER",
    "MAD_SCALE",
]
