"""Quantitative value screening scores - vendor-neutral.

Pure functions turning canonical financial line items into the classic
forensic/value scores plus the two valuation ratios the value watchlist
is built on:

- Beneish M-Score: likelihood reported earnings were manipulated.
- Altman Z-Score: bankruptcy risk within ~2 years.
- Piotroski F-Score: fundamental quality, 0-9.
- EV = MarketCap + TotalDebt - Cash
- EarningsYield = EBIT / EV
- Acquirer'sMultiple = EV / EBIT
- Tobin's Q = (MarketCap + TotalLiabilities) / TotalAssets
- GP/A: Novy-Marx gross profitability
- NOA: Hirshleifer et al. net operating assets

Input contract
--------------
Each function accepts a dict of canonical line items (names below)
to either a plain float (latest period) or a dict with 'current' and
'prior' keys (latest + year-ago period; needed by ratios). The vendor
layer (yfinance CSV, moomoo/alpha_vantage JSON & markdown) translates
vendor row labels into these canonical names.

Missing values never raise: when a score cannot be computed the
function returns None and the screener renders n/a instead of inventing
a number - real statements are missing rows alarmingly often.

Canonical line items (the screener matches vendor labels loosely):

- income: revenue, cogs (cost of revenue), sga, depreciation (incl.
  amortization), operating_income (EBIT), net_income, interest_expense,
  tax_expense
- balance: cash, total_debt, market_cap, total_assets, total_liabilities,
  current_assets, current_liabilities, retained_earnings, ppem (net PP&E),
  marketable_securities, net_receivables
- cashflow: operating_cashflow (CFO), dividends_paid, share_buybacks,
  debt_repayment, capex
"""

from __future__ import annotations


def _val(item):
    """Latest (or plain) value of a canonical item."""
    if item is None:
        return None
    if isinstance(item, dict):
        return item.get("current", item.get("value"))
    return item


def _prv(item):
    """Prior-period value of a canonical item (dict with 'prior')."""
    if isinstance(item, dict):
        return item.get("prior")
    return None


def _num(v):
    if isinstance(v, dict):
        v = v.get("current", v.get("value"))
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ratio(a, b):
    if a is None or b is None or b == 0:
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


def _cogs(m):
    """COGS with the cost-of-revenue fallback."""
    return _num(m.get("cogs")) or _num(m.get("cost_of_revenue"))


# Beneish M-Score

_M_CONSTANT = -4.84
_M_WEIGHTS = {
    "dsri": 0.92,
    "gmi": 0.528,
    "aqi": 0.404,
    "sgi": 0.892,
    "depi": 0.115,
    "sgai": -0.172,
    "tata": 4.679,
    "lvgi": -0.327,
}
# M > this -> earnings likely manipulated
M_SUSPECT = -1.78
# M < this -> manipulation unlikely
M_CLEAN = -2.22


def beneish_m_score(fin):
    """Beneish M-Score. None when any index is missing."""
    rev = _num(fin.get("revenue"))
    rev_p = _num(_prv(fin.get("revenue")))
    if rev is None or rev_p is None:
        return None
    recv = _num(fin.get("net_receivables"))
    recv_p = _num(_prv(fin.get("net_receivables")))
    dsri = _ratio(_ratio(recv, rev), _ratio(recv_p, rev_p))
    cogs = _cogs(fin)
    cogs_p = _num(_prv(fin.get("cogs"))) or _num(_prv(fin.get("cost_of_revenue")))
    gp = _sub(rev, cogs)
    gp_p = _sub(rev_p, cogs_p)
    gmi = _ratio(_ratio(gp_p, rev_p), _ratio(gp, rev))
    ca = _num(fin.get("current_assets"))
    ca_p = _num(_prv(fin.get("current_assets")))
    ppe = _num(fin.get("ppem"))
    ppe_p = _num(_prv(fin.get("ppem")))
    sec = _num(fin.get("marketable_securities"))
    sec_p = _num(_prv(fin.get("marketable_securities")))
    ta = _num(fin.get("total_assets"))
    ta_p = _num(_prv(fin.get("total_assets")))
    if None in (ca, ppe, sec, ta, ta_p):
        return None
    num_s = _sub(1.0, _ratio(_sub(_sub(_sub(ta, ca), ppe), sec), ta))
    den_s = _sub(
        1.0,
        _ratio(
            _sub(_sub(_sub(ta_p, ca_p), ppe_p), sec_p),
            ta_p,
        ),
    )
    aqi = _ratio(num_s, den_s)
    sgi = _ratio(rev, rev_p)
    dep = _num(fin.get("depreciation"))
    dep_p = _num(_prv(fin.get("depreciation")))
    # Canonical DEPI (Beneish 1999): [Dep_t-1/(PPE_t-1 + Dep_t-1)] /
    # [Dep_t/(PPE_t + Dep_t)] - the denominators are SUMS, not differences.
    depi = _ratio(_ratio(dep_p, _add(ppe_p, dep_p)), _ratio(dep, _add(ppe, dep)))
    sga = _num(fin.get("sga"))
    sga_p = _num(_prv(fin.get("sga")))
    sgai = _ratio(_ratio(sga, rev), _ratio(sga_p, rev_p))
    cl = _num(fin.get("current_liabilities"))
    ltd = _num(fin.get("total_debt"))
    cl_p = _num(_prv(fin.get("current_liabilities")))
    ltd_p = _num(_prv(fin.get("total_debt")))
    # Canonical LVGI (Beneish 1999): [(CL + LTD)/TA]_t / [(CL + LTD)/TA]_t-1
    # - leverage ADDS long-term debt to current liabilities.
    lvgi = _ratio(_ratio(_add(cl, ltd), ta), _ratio(_add(cl_p, ltd_p), ta_p))
    ni = _num(fin.get("net_income"))
    cfo = _num(fin.get("operating_cashflow"))
    tata = _ratio(_sub(ni, cfo), ta)
    idx = (dsri, gmi, aqi, sgi, depi, sgai, lvgi, tata)
    if any(i is None for i in idx):
        return None
    return (
        _M_CONSTANT
        + _M_WEIGHTS["dsri"] * dsri
        + _M_WEIGHTS["gmi"] * gmi
        + _M_WEIGHTS["aqi"] * aqi
        + _M_WEIGHTS["sgi"] * sgi
        + _M_WEIGHTS["depi"] * depi
        + _M_WEIGHTS["sgai"] * sgai
        + _M_WEIGHTS["tata"] * tata
        + _M_WEIGHTS["lvgi"] * lvgi
    )


def altman_z_score(fin):
    """Altman Z-Score. None when any input is missing."""
    ta = _num(fin.get("total_assets"))
    if ta is None or ta == 0:
        return None
    wc = _num(fin.get("working_capital"))
    re = _num(fin.get("retained_earnings"))
    ebit = _num(fin.get("operating_income"))
    mve = _num(fin.get("market_cap"))
    tl = _num(fin.get("total_liabilities"))
    sales = _num(fin.get("revenue"))
    if None in (wc, re, ebit, mve, tl, sales):
        return None
    x1 = _ratio(wc, ta)
    x2 = _ratio(re, ta)
    x3 = _ratio(ebit, ta)
    x4 = _ratio(mve, tl)
    x5 = _ratio(sales, ta)
    return 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5


def piotroski_f_score(fin):
    """Piotroski F-Score. None when inputs missing."""
    cfo = _num(fin.get("operating_cashflow"))
    ni = _num(fin.get("net_income"))
    if cfo is None or ni is None:
        return None
    score = 0
    roa = _num(fin.get("roa"))
    if roa is not None and roa > 0:
        score += 1
    if cfo > 0:
        score += 1
    if _sub(cfo, ni) and _sub(cfo, ni) > 0:
        score += 1
    roa_p = _num(_prv(fin.get("roa")))
    if roa is not None and roa_p is not None and roa > roa_p:
        score += 1
    lev = _num(fin.get("leverage"))
    lev_p = _num(_prv(fin.get("leverage")))
    if lev is not None and lev_p is not None and lev < lev_p:
        score += 1
    cr = _num(fin.get("current_ratio"))
    cr_p = _num(_prv(fin.get("current_ratio")))
    if cr is not None and cr_p is not None and cr > cr_p:
        score += 1
    sh = _num(fin.get("shares_issued"))
    if sh is not None and sh <= 0:
        score += 1
    gm = _num(fin.get("gross_margin"))
    gm_p = _num(_prv(fin.get("gross_margin")))
    if gm is not None and gm_p is not None and gm > gm_p:
        score += 1
    at = _num(fin.get("asset_turnover"))
    at_p = _num(_prv(fin.get("asset_turnover")))
    if at is not None and at_p is not None and at > at_p:
        score += 1
    return score


def enterprise_value(fin):
    """EV = MarketCap + TotalDebt - Cash. None when inputs missing."""
    mc = _num(fin.get("market_cap"))
    debt = _num(fin.get("total_debt"))
    cash = _num(fin.get("cash"))
    if None in (mc, debt, cash):
        return None
    return mc + debt - cash


def earnings_yield(fin):
    """EBIT / EV. None when inputs missing."""
    ev = enterprise_value(fin)
    ebit = _num(fin.get("operating_income"))
    if ev is None or ebit is None:
        return None
    return _ratio(ebit, ev)


def acquirers_multiple(fin):
    """EV/EBIT - the multiple acquirers pay. None when inputs missing."""
    ev = enterprise_value(fin)
    ebit = _num(fin.get("operating_income"))
    if ev is None or ebit is None:
        return None
    return _ratio(ev, ebit)


def tobins_q(fin):
    """Tobin's Q = (market cap + total liabilities) / total assets.

    The market value of the firm's assets over their book value, which stands
    in for replacement cost: the canonical has no market price for the debt and
    no appraisal of the asset base, so the two legs are stated rather than
    implied - equity is priced by the market, liabilities and assets are book.

    A missing ``total_liabilities`` returns ``None`` instead of the equity-only
    ratio: dropping the liabilities leg silently inflates Q (the P/B reading),
    and a substitute is not available. A non-positive market cap or total assets
    is likewise ``None`` (never a negative or infinite multiple).

    Returns ``{"value", "basis", "classification"}``.
    """
    mc = _num(fin.get("market_cap"))
    tl = _num(fin.get("total_liabilities"))
    ta = _num(fin.get("total_assets"))
    if mc is None or tl is None or ta is None or mc <= 0 or ta <= 0:
        return None
    return {
        "value": (mc + tl) / ta,
        "basis": "Tobin's Q = (market_cap + total_liabilities) / total_assets; "
        "equity at market, liabilities and assets at book (the replacement-cost "
        "proxy); latest period",
        "classification": "equity leg: market_cap; liabilities leg: "
        "total_liabilities; assets: total_assets",
    }


def gross_profitability(fin):
    """Novy-Marx GP/A = (revenue - COGS) / total assets.

    Missing revenue, COGS or total assets returns ``None`` (never substitute
    operating income for COGS). Returns ``{"value", "basis", "classification"}``
    where ``classification`` records the COGS line used.
    """
    rev = _num(fin.get("revenue"))
    ta = _num(fin.get("total_assets"))
    cogs = _num(fin.get("cogs"))
    src = "cogs"
    if cogs is None:
        cogs = _num(fin.get("cost_of_revenue"))
        src = "cost_of_revenue"
    if rev is None or cogs is None or ta is None or ta == 0:
        return None
    return {
        "value": (rev - cogs) / ta,
        "basis": f"GP/A = (revenue - {src}) / total_assets; latest period",
        "classification": f"cogs line: {src}",
    }


def net_operating_assets(fin):
    """Hirshleifer et al. NOA = (operating assets - operating liabilities) / TA_prev.

    Operating assets = total assets minus financial assets (cash +
    marketable securities); operating liabilities = total liabilities minus
    total debt. The prior-year total assets is the denominator - a missing
    prior balance sheet returns ``None``. ``classification`` records the
    operating/financial split actually used (hybrids are ambiguous, so the
    split is stated, never inferred silently).
    """
    ta = _num(fin.get("total_assets"))
    ta_prev = _num(_prv(fin.get("total_assets")))
    tl = _num(fin.get("total_liabilities"))
    if ta is None or ta_prev is None or tl is None or ta_prev == 0:
        return None
    cash = _num(fin.get("cash"))
    sec = _num(fin.get("marketable_securities"))
    debt = _num(fin.get("total_debt"))
    fin_assets = (cash or 0.0) + (sec or 0.0)
    assets_desc = "+".join(
        n for n, v in (("cash", cash), ("marketable_securities", sec)) if v is not None
    ) or "none"
    operating_assets = ta - fin_assets
    operating_liabilities = tl - (debt or 0.0)
    debt_desc = "total_debt" if debt is not None else "no debt line"
    return {
        "value": (operating_assets - operating_liabilities) / ta_prev,
        "basis": "NOA = (operating assets - operating liabilities) / total_assets_prev; "
        "operating assets = total_assets - financial assets, "
        "operating liabilities = total_liabilities - total_debt",
        "classification": f"financial assets: {assets_desc}; debt line: {debt_desc}",
    }

# ---------------------------------------------------------------------------
# Altman variant family and distress zones (round-3 S1).
#
# ``altman_z_score`` above is the public-manufacturer discriminant; applying it
# to a non-manufacturer is the documented misuse the Z'/Z'' variants fix.
# Coefficients and cut-offs are the design doc's S1 table: Z'/Z'' use BOOK
# equity for X4, Z'' drops X5, Z''-EM adds 3.25.
# ---------------------------------------------------------------------------

_ALTMAN_VARIANTS = {
    "z": {
        "weights": {"x1": 1.2, "x2": 1.4, "x3": 3.3, "x4": 0.6, "x5": 1.0},
        "use_x5": True,
        "x4_basis": "market_cap",
        "add": 0.0,
        "label": "Z (public manufacturers)",
    },
    "z_prime": {
        "weights": {"x1": 0.717, "x2": 0.847, "x3": 3.107, "x4": 0.420, "x5": 0.998},
        "use_x5": True,
        "x4_basis": "book",
        "add": 0.0,
        "label": "Z' (private / non-manufacturers)",
    },
    "z_double_prime": {
        "weights": {"x1": 6.56, "x2": 3.26, "x3": 6.72, "x4": 1.05},
        "use_x5": False,
        "x4_basis": "book",
        "add": 0.0,
        "label": "Z'' (non-manufacturers, emerging)",
    },
    "z_double_prime_em": {
        "weights": {"x1": 6.56, "x2": 3.26, "x3": 6.72, "x4": 1.05},
        "use_x5": False,
        "x4_basis": "book",
        "add": 3.25,
        "label": "Z''-EM (emerging-market add-on)",
    },
}

_Z_ZONE_BANDS = "safe > 3.0; grey 1.8-3.0; distress < 1.8"
_ZP_ZONE_BANDS = "safe > 2.90; grey 1.23-2.90; distress < 1.23"
_ZPP_ZONE_BANDS = "safe > 2.60; grey 1.10-2.60; distress < 1.10"

_ALTMAN_ZONES = {
    "z": {"safe_min": 3.0, "distress_max": 1.8, "bands": _Z_ZONE_BANDS},
    "z_prime": {"safe_min": 2.90, "distress_max": 1.23, "bands": _ZP_ZONE_BANDS},
    "z_double_prime": {"safe_min": 2.60, "distress_max": 1.10, "bands": _ZPP_ZONE_BANDS},
    "z_double_prime_em": {
        "safe_min": 2.60, "distress_max": 1.10, "bands": _ZPP_ZONE_BANDS,
    },
}


def altman_variant(fin, variant="z"):
    """One Altman discriminant variant over canonical items (round-3 S1).

    Returns ``{"value", "variant", "x4_basis", "basis", "components"}`` or
    ``None`` when a required input is missing. ``variant`` is one of
    ``z | z_prime | z_double_prime | z_double_prime_em``. Z/Z' use X5
    (sales/TA); Z''/Z''-EM drop it; Z'/Z'' use BOOK equity for X4 (the
    ``book_equity`` line, or ``total_equity`` as the stated proxy when absent);
    Z''-EM adds 3.25. The basis string prints the variant, the X4 source and
    every substitution made - two variants are never comparable as if equal.
    """
    spec = _ALTMAN_VARIANTS.get(variant)
    if spec is None:
        return None
    ta = _num(fin.get("total_assets"))
    if ta is None or ta == 0:
        return None
    wc = _num(fin.get("working_capital"))
    re = _num(fin.get("retained_earnings"))
    ebit = _num(fin.get("operating_income"))
    tl = _num(fin.get("total_liabilities"))
    if None in (wc, re, ebit, tl):
        return None
    x1 = _ratio(wc, ta)
    x2 = _ratio(re, ta)
    x3 = _ratio(ebit, ta)
    notes = []
    if spec["x4_basis"] == "market_cap":
        x4_num, x4_src = _num(fin.get("market_cap")), "market equity (market_cap)"
    else:
        x4_num = _num(fin.get("book_equity"))
        if x4_num is not None:
            x4_src = "book equity (book_equity)"
        else:
            x4_num = _num(fin.get("total_equity"))
            x4_src = "book equity (total_equity proxy)"
            if x4_num is not None:
                notes.append("book equity absent: total_equity used as the stated proxy")
    if x4_num is None:
        return None
    x4 = _ratio(x4_num, tl)
    comp = {"x1": x1, "x2": x2, "x3": x3, "x4": x4}
    val = (
        spec["weights"]["x1"] * x1
        + spec["weights"]["x2"] * x2
        + spec["weights"]["x3"] * x3
        + spec["weights"]["x4"] * x4
    )
    if spec["use_x5"]:
        sales = _num(fin.get("revenue"))
        if sales is None:
            return None
        x5 = _ratio(sales, ta)
        comp["x5"] = x5
        val += spec["weights"]["x5"] * x5
    val += spec["add"]
    basis = (
        f"variant={variant} ({spec['label']}); X4 basis: {x4_src}; "
        f"X5: {'sales/total_assets' if spec['use_x5'] else 'dropped'}"
    )
    if spec["add"]:
        basis += f"; Z''-EM: +{spec['add']} constant added"
    if notes:
        basis += "; " + "; ".join(notes)
    return {
        "value": val,
        "variant": variant,
        "x4_basis": x4_src,
        "basis": basis,
        "components": comp,
    }


def altman_zone(z, variant):
    """Distress zone for an Altman score under its variant's band table (S1).

    Returns ``{"zone", "bands", "variant", "basis"}`` where zone is
    ``safe | grey | distress``, or ``None`` when the variant is unknown or the
    score is not a number. The variant's published cut-offs are used exactly;
    the band table is echoed so a raw score is never left unlabelled.
    """
    spec = _ALTMAN_ZONES.get(variant)
    if spec is None:
        return None
    try:
        zf = float(z)
    except (TypeError, ValueError):
        return None
    if zf > spec["safe_min"]:
        zone = "safe"
    elif zf < spec["distress_max"]:
        zone = "distress"
    else:
        zone = "grey"
    return {
        "zone": zone,
        "bands": spec["bands"],
        "variant": variant,
        "basis": f"zone={zone}; bands: {spec['bands']}; variant={variant}",
    }


def altman_variant_for(*, ticker="", identity=None, provider_meta=None, sector=None, fin=None):
    """Select the Altman variant a name should be read under, or withhold it.

    Routing follows ``strategies/security_type.py`` plus the model's own stated
    limitation: funds/ETFs -> ``None`` (the discriminants are estimated on
    non-financial operating companies); financial-sector names -> ``None``
    (Altman excludes financials); an operating company that is a manufacturer
    (inventory AND COGS present) -> ``z``; otherwise -> ``z_double_prime``.
    Returns ``{"variant": str | None, "reason": str, "basis": str}``.
    """
    from tradingagents.strategies.security_type import classify_security

    cls = classify_security(ticker, identity=identity, provider_meta=provider_meta)
    if cls.get("security_type") == "ETF":
        return {
            "variant": None,
            "reason": (
                "fund/ETF: the Altman discriminants are estimated on non-financial "
                "operating companies and are not defined for funds"
            ),
            "basis": f"security_type={cls.get('security_type')}",
        }
    if sector:
        try:
            from tradingagents.strategies.sector_rank import sector_group_of

            group = sector_group_of(sector)
        except Exception:  # noqa: BLE001 - a missing map must not block the read
            group = None
        if group == "XLF":
            return {
                "variant": None,
                "reason": (
                    "financial company: Altman Z is not recommended for financials "
                    "(its estimation sample excluded them)"
                ),
                "basis": f"sector={sector}",
            }
    inv = _num(fin.get("inventory")) if fin else None
    cogs = _cogs(fin) if fin else None
    if inv is not None and cogs is not None:
        variant = "z"
        reason = "manufacturer (inventory and COGS present): original Z"
    else:
        variant = "z_double_prime"
        reason = (
            "non-manufacturer (no inventory/COGS economics): Z'' (drops X5, book-equity X4)"
        )
    return {
        "variant": variant,
        "reason": reason,
        "basis": f"security_type={cls.get('security_type')}; {reason}",
    }


# ---------------------------------------------------------------------------
# Piotroski F-Score - the paper's basis, bands and applicability (round-3 S2).
#
# ``piotroski_f_score`` above is untouched for existing callers; this detailed
# form computes each of the nine signals from the current/prior chain on the
# paper's stated basis (beginning-of-year assets; the accrual test in RATIO
# form CFO>ROA; leverage as (LTD+current portion)/AVERAGE TA) and records every
# substitution in ``deviations``.
# ---------------------------------------------------------------------------

_F_BAND = "low 0-1; high 8-9"
_F_BAND_NOT_USED = "0-2/8-9 (Wikipedia), 0-3/7-9 (Nature review Table 9)"


def _piotroski_band(score):
    if score <= 1:
        label = "low"
    elif score >= 8:
        label = "high"
    else:
        label = "middle"
    return {"label": label, "bands": _F_BAND, "not_used": _F_BAND_NOT_USED}


def piotroski_f_score_detailed(fin, *, classification=None, sector=None):
    """Nine Piotroski signals on the paper's basis, + band and deviations (S2).

    Signals (True/False, or ``None`` when an input is genuinely missing):
    ``f_roa`` (ROA_t = NI_t / beginning-of-year TA > 0), ``f_cfo`` (CFO>0),
    ``f_droa`` (ROA_t > ROA_t-1), ``f_accrual`` (the RATIO test CFO > ROA),
    ``f_dlever`` (delta of (LTD + current portion)/AVERAGE TA < 0),
    ``f_dliquid`` (current ratio rose), ``f_eq`` (no common equity issued),
    ``f_dmargin`` (gross margin rose), ``f_dturn`` (asset turnover rose).

    Returns ``{"score", "signals", "band", "basis", "deviations"}`` or ``None``
    when no signal is computable or the security-type/financial guard withholds
    the model. ``band`` is assigned only when ALL nine signals are present
    (both periods measurable); a missing prior withholds the band and records
    the reason. Every substitution is recorded in ``deviations``.
    """
    if classification and classification.get("security_type") == "ETF":
        return None
    if sector:
        try:
            from tradingagents.strategies.sector_rank import sector_group_of

            if sector_group_of(sector) == "XLF":
                return None
        except Exception:  # noqa: BLE001
            pass

    dev = []
    ni = _num(fin.get("net_income"))
    ni_p = _num(_prv(fin.get("net_income")))
    ta = _num(fin.get("total_assets"))
    ta_p = _num(_prv(fin.get("total_assets")))
    cfo = _num(fin.get("operating_cashflow"))
    dev.append(
        "income basis: net_income used for income-before-extraordinary-items "
        "(the vendor chain carries no extraordinary-items line)"
    )

    if ta_p is not None:
        begin_ta = ta_p
    elif ta is not None:
        begin_ta = ta
        dev.append(
            "ROA denominator: ending total assets (beginning-of-year assets unavailable)"
        )
    else:
        begin_ta = None
    roa = _ratio(ni, begin_ta)
    if ni_p is not None and ta_p is not None:
        roa_p = _ratio(ni_p, ta_p)
        dev.append("prior-year ROA denominator: TA_prev (TA_t-2 is not in the chain)")
    else:
        roa_p = None

    signals = {}
    signals["f_roa"] = (roa > 0) if roa is not None else None
    signals["f_cfo"] = (cfo > 0) if cfo is not None else None
    signals["f_droa"] = (roa > roa_p) if (roa is not None and roa_p is not None) else None
    signals["f_accrual"] = (cfo > roa) if (cfo is not None and roa is not None) else None

    debt = _num(fin.get("total_debt"))
    debt_p = _num(_prv(fin.get("total_debt")))
    lev = lev_p = None
    if debt is not None and ta is not None and ta_p is not None:
        lev = debt / ((ta + ta_p) / 2.0)
    elif debt is not None and ta is not None:
        lev = debt / ta
        dev.append("leverage denominator: ending total assets (average TA unavailable)")
    if debt_p is not None and ta_p is not None:
        lev_p = debt_p / ta_p
        dev.append("prior leverage denominator: TA_prev (TA_t-2 unavailable for the average)")
    signals["f_dlever"] = (lev < lev_p) if (lev is not None and lev_p is not None) else None

    cr = _ratio(_num(fin.get("current_assets")), _num(fin.get("current_liabilities")))
    cr_p = _ratio(_num(_prv(fin.get("current_assets"))), _num(_prv(fin.get("current_liabilities"))))
    signals["f_dliquid"] = (cr > cr_p) if (cr is not None and cr_p is not None) else None

    sh = _num(fin.get("shares_issued"))
    if sh is None:
        cur_sh = _num(fin.get("shares"))
        prv_sh = _num(_prv(fin.get("shares")))
        if cur_sh is not None:
            sh = (cur_sh - prv_sh) if prv_sh is not None else cur_sh
    signals["f_eq"] = (sh <= 0) if sh is not None else None

    rev = _num(fin.get("revenue"))
    rev_p = _num(_prv(fin.get("revenue")))
    cogs = _cogs(fin)
    cogs_p = _num(_prv(fin.get("cogs"))) or _num(_prv(fin.get("cost_of_revenue")))
    gm = _ratio(_sub(rev, cogs), rev)
    gm_p = _ratio(_sub(rev_p, cogs_p), rev_p)
    signals["f_dmargin"] = (gm > gm_p) if (gm is not None and gm_p is not None) else None

    at = _ratio(rev, ta)
    at_p = _ratio(rev_p, ta_p)
    signals["f_dturn"] = (at > at_p) if (at is not None and at_p is not None) else None

    computed = [v for v in signals.values() if v is not None]
    if not computed:
        return None
    score = sum(1 for v in computed if v)
    missing = [k for k, v in signals.items() if v is None]
    band = _piotroski_band(score) if not missing else None
    if missing:
        dev.append("band withheld: signals missing for " + ", ".join(missing))

    mc = _num(fin.get("market_cap"))
    if mc is not None and mc >= 10e9:
        dev.append(
            "weak-signal flag: large market cap (the paper's F-spread is "
            "insignificant for large caps; analyst coverage also weakens it)"
        )
    basis = (
        "Piotroski F (paper basis): ROA=NI/beginning TA; F_ACCRUAL=CFO>ROA ratio; "
        "F_DLEVER=delta((LTD+current portion)/average TA)"
    )
    return {
        "score": score,
        "signals": signals,
        "band": band,
        "basis": basis,
        "deviations": dev,
    }


# ---------------------------------------------------------------------------
# Mohanram G-Score and Montier C-Score (round-3 S10).
#
# Binary sums with the review's Table 9 bands. Industry-median legs need the
# caller's peer medians (``group_median`` over the resolved universe): with
# ``medians=None`` those legs are EXCLUDED with a printed reason, never scored
# 0. G4/G5 additionally need a 5-year annual series; fewer years -> excluded.
# G8 (advertising intensity) is unavailable for feeds lacking the line.
# ---------------------------------------------------------------------------

_PEER_FLOOR = 5
_G_BAND = "good 6-8; poor 0-2 (Nature review Table 9)"
_C_BAND = "good 0-2; poor 5-6 (Nature review Table 9)"


def _median_of(medians, key, deviations):
    """Peer median for ``key`` (``{median, n}``), or None with a recorded reason."""
    entry = (medians or {}).get(key)
    if not isinstance(entry, dict) or entry.get("median") is None:
        deviations.append(f"{key}: industry median unavailable (excluded, not scored 0)")
        return None
    n = entry.get("n")
    if n is not None and int(n) < _PEER_FLOOR:
        deviations.append(f"{key}: peer group n={n} below floor {_PEER_FLOOR} (excluded)")
        return None
    return float(entry["median"])


def _variance(values):
    """Population variance of a numeric list (None when fewer than 2 points)."""
    if not values or len(values) < 2:
        return None
    m = sum(values) / len(values)
    return sum((v - m) ** 2 for v in values) / len(values)


def _series(fin, *keys):
    """First key holding a complete finite annual series (oldest -> newest)."""
    for key in keys:
        s = fin.get(key)
        if isinstance(s, (list, tuple)) and s:
            vals = [_num(v) for v in s]
            if all(v is not None for v in vals):
                return [float(v) for v in vals]
    return None


def signal_summary(read, denominator: int) -> str:
    """Score headline that never prints a partial sum under the full denominator.

    With the peer medians absent (the tool path) or a 5-year series missing, the
    G/C scores sum only the computable signals - so ``1/8`` reads as Mohanram's
    G = 1 when in truth ONE signal was computable. The full denominator is only
    used when every signal is present (the case that also carries a band);
    otherwise the headline states the computed count and the exclusion. The
    per-signal reasons live in ``deviations``.
    """
    signals = (read or {}).get("signals") or {}
    computed = [v for v in signals.values() if v is not None]
    total = len(signals) or int(denominator)
    score = (read or {}).get("score")
    if score is None:
        return "unavailable"
    if len(computed) == total:
        return f"{score}/{total}"
    return (
        f"{score} of {len(computed)} computed signal(s) "
        f"({total - len(computed)} excluded, not scored 0)"
    )


def growth_metrics(fin) -> dict:
    """The seven per-name inputs the G-Score's peer medians are built from.

    One definition for both consumers (rule 2): ``growth_score`` compares these
    values against medians that a peer cross-section of THIS function produces,
    so the score path and the screener's medians cannot drift. An input the
    feed does not carry is simply absent from the result - never 0.

    Keys: ``roa``, ``cfo`` (CFO / beginning-of-year TA), ``var_roa`` (needs the
    5-year ``roa_series``), ``var_sales_growth`` (needs the 5-year
    ``revenue_series``), ``rd_intensity``, ``capex_intensity``,
    ``ad_intensity``. ``roa_series_n`` / ``revenue_series_n`` carry the
    observed series lengths so a caller can print why a variance leg is
    missing.
    """
    out: dict = {}
    ni = _num(fin.get("net_income"))
    cfo = _num(fin.get("operating_cashflow"))
    ta = _num(fin.get("total_assets"))
    ta_p = _num(_prv(fin.get("total_assets")))
    begin_ta = ta_p if ta_p is not None else ta
    rev = _num(fin.get("revenue"))
    roa = _ratio(ni, begin_ta)
    if roa is not None:
        out["roa"] = roa
    cfo_int = _ratio(cfo, begin_ta)
    if cfo_int is not None:
        out["cfo"] = cfo_int
    roa_series = _series(fin, "roa_series")
    out["roa_series_n"] = 0 if roa_series is None else len(roa_series)
    if roa_series is not None and len(roa_series) >= 5:
        out["var_roa"] = _variance(roa_series)
    rev_series = _series(fin, "revenue_series")
    out["revenue_series_n"] = 0 if rev_series is None else len(rev_series)
    if rev_series is not None and len(rev_series) >= 5:
        growths = [
            rev_series[i] / rev_series[i - 1] - 1.0
            for i in range(1, len(rev_series))
            if rev_series[i - 1]
        ]
        if len(growths) >= 2:
            out["var_sales_growth"] = _variance(growths)
    rd = _num(fin.get("research_development")) or _num(fin.get("rd_expense"))
    rd_int = _ratio(rd, rev)
    if rd_int is not None:
        out["rd_intensity"] = rd_int
    cap_int = _ratio(_num(fin.get("capex")), rev)
    if cap_int is not None:
        out["capex_intensity"] = cap_int
    adv = _num(fin.get("advertising")) or _num(fin.get("advertising_expense"))
    adv_int = _ratio(adv, rev)
    if adv_int is not None:
        out["ad_intensity"] = adv_int
    return out


def growth_score(fin, medians=None):
    """Mohanram G-Score G1..G8 with Table 9 bands (round-3 S10).

    ``medians`` is the peer-universe median map (``{metric: {"median","n"}}``,
    from ``group_median``), keyed by ``roa | cfo | var_roa |
    var_sales_growth | rd_intensity | capex_intensity | ad_intensity``. Missing
    medians exclude their leg (recorded). ``medians=None`` (the tool path)
    leaves only G3 computable - it never scores a median leg 0. G4/G5 need a
    5-year annual series (``roa_series`` / ``revenue_series``); fewer years
    exclude them. G8 is unavailable when the feed lacks the advertising line.

    Returns ``{"score", "signals", "band", "basis", "deviations"}`` or ``None``
    when no signal is computable. ``band`` is assigned only when all eight
    signals are present.
    """
    dev = []
    signals = {}
    g = growth_metrics(fin)
    ni = _num(fin.get("net_income"))
    cfo = _num(fin.get("operating_cashflow"))
    roa = g.get("roa")
    cfo_int = g.get("cfo")

    signals["g3"] = (cfo > ni) if (cfo is not None and ni is not None) else None

    m_roa = _median_of(medians, "roa", dev)
    signals["g1"] = (roa > m_roa) if (roa is not None and m_roa is not None) else None
    m_cfo = _median_of(medians, "cfo", dev)
    signals["g2"] = (cfo_int > m_cfo) if (cfo_int is not None and m_cfo is not None) else None

    m_vr = _median_of(medians, "var_roa", dev)
    var_roa = g.get("var_roa")
    if var_roa is None:
        dev.append(
            f"g4: 5-year ROA series unavailable (n={g.get('roa_series_n', 0)})"
            " - excluded, not 0"
        )
        signals["g4"] = None
    else:
        signals["g4"] = (var_roa < m_vr) if m_vr is not None else None

    m_vs = _median_of(medians, "var_sales_growth", dev)
    var_growth = g.get("var_sales_growth")
    if g.get("revenue_series_n", 0) < 5:
        dev.append(
            f"g5: 5-year revenue series unavailable (n={g.get('revenue_series_n', 0)})"
            " - excluded, not 0"
        )
        signals["g5"] = None
    elif var_growth is not None and m_vs is not None:
        signals["g5"] = var_growth < m_vs
    else:
        signals["g5"] = None

    m_rd = _median_of(medians, "rd_intensity", dev)
    rd_int = g.get("rd_intensity")
    if rd_int is None:
        dev.append("g6: R&D line absent from the feed - excluded, not 0")
    signals["g6"] = (rd_int > m_rd) if (rd_int is not None and m_rd is not None) else None

    m_cap = _median_of(medians, "capex_intensity", dev)
    cap_int = g.get("capex_intensity")
    if cap_int is None:
        dev.append("g7: Capex line absent from the feed - excluded, not 0")
    signals["g7"] = (cap_int > m_cap) if (cap_int is not None and m_cap is not None) else None

    m_adv = _median_of(medians, "ad_intensity", dev)
    adv_int = g.get("ad_intensity")
    if adv_int is None:
        dev.append("g8: advertising line absent from the feed - unavailable, not 0")
    signals["g8"] = (adv_int > m_adv) if (adv_int is not None and m_adv is not None) else None

    computed = [v for v in signals.values() if v is not None]
    if not computed:
        return None
    score = sum(1 for v in computed if v)
    missing = [k for k, v in signals.items() if v is None]
    if not missing:
        band = {"label": "good" if score >= 6 else "poor" if score <= 2 else "middle",
                "bands": _G_BAND}
    else:
        band = None
        dev.append("band withheld: signals missing for " + ", ".join(missing))
    basis = (
        "G-Score = sum(G1..G8): G1 ROA>peer median; G2 CFO/TA>median; G3 CFO>NI; "
        "G4 Var(ROA)<median; G5 Var(YoY sales growth)<median; G6 R&D intensity>median; "
        "G7 CapEx intensity>median; G8 advertising intensity>median. "
        f"peer medians: {'supplied' if medians else 'none (median legs excluded)'}"
    )
    return {"score": score, "signals": signals, "band": band, "basis": basis, "deviations": dev}


def overpriced_score(fin):
    """Montier C-Score C1..C6 - an overpriced/fragile-accounting RISK SCREEN (S10).

    C1 NI-vs-cash-flow divergence widened; C2 receivable days rose; C3
    inventory days rose; C4 other current assets rose; C5 depreciation / gross
    fixed assets fell (net PP&E used as the stated proxy); C6 total assets grew
    >10%. Returns ``{"score", "signals", "band", "basis", "deviations",
    "risk_screen": True}`` or ``None`` when no signal is computable. This is a
    risk screen, NOT a short signal; ``band`` is assigned only when all six
    signals are present.
    """
    dev = []
    signals = {}
    ni, ni_p = _num(fin.get("net_income")), _num(_prv(fin.get("net_income")))
    cfo, cfo_p = _num(fin.get("operating_cashflow")), _num(_prv(fin.get("operating_cashflow")))
    ta, ta_p = _num(fin.get("total_assets")), _num(_prv(fin.get("total_assets")))
    rev, rev_p = _num(fin.get("revenue")), _num(_prv(fin.get("revenue")))

    div, div_p = _sub(ni, cfo), _sub(ni_p, cfo_p)
    signals["c1"] = (div > div_p) if (div is not None and div_p is not None) else None

    recv, recv_p = _num(fin.get("net_receivables")), _num(_prv(fin.get("net_receivables")))
    dso, dso_p = _ratio(recv, rev), _ratio(recv_p, rev_p)
    signals["c2"] = (dso > dso_p) if (dso is not None and dso_p is not None) else None

    inv, inv_p = _num(fin.get("inventory")), _num(_prv(fin.get("inventory")))
    cogs, cogs_p = _cogs(fin), _num(_prv(fin.get("cogs"))) or _num(_prv(fin.get("cost_of_revenue")))
    dinv, dinv_p = _ratio(inv, cogs), _ratio(inv_p, cogs_p)
    signals["c3"] = (dinv > dinv_p) if (dinv is not None and dinv_p is not None) else None

    ca, ca_p = _num(fin.get("current_assets")), _num(_prv(fin.get("current_assets")))
    cash, cash_p = _num(fin.get("cash")), _num(_prv(fin.get("cash")))
    if None in (ca, ca_p, cash, cash_p, recv, recv_p, inv, inv_p):
        signals["c4"] = None
        dev.append(
            "c4: other current assets need current_assets/cash/receivables/inventory "
            "(both periods) - excluded"
        )
    else:
        signals["c4"] = (ca - cash - recv - inv) > (ca_p - cash_p - recv_p - inv_p)

    dep, dep_p = _num(fin.get("depreciation")), _num(_prv(fin.get("depreciation")))
    ppe, ppe_p = _num(fin.get("ppem")), _num(_prv(fin.get("ppem")))
    dev.append("c5: gross fixed assets unavailable - net PP&E (ppem) used as the stated proxy")
    rate = _ratio(dep, ppe)
    rate_p = _ratio(dep_p, ppe_p)
    signals["c5"] = (rate < rate_p) if (rate is not None and rate_p is not None) else None

    signals["c6"] = ((ta / ta_p - 1.0) > 0.10) if (ta is not None and ta_p) else None

    computed = [v for v in signals.values() if v is not None]
    if not computed:
        return None
    score = sum(1 for v in computed if v)
    missing = [k for k, v in signals.items() if v is None]
    if not missing:
        band = {"label": "good" if score <= 2 else "poor" if score >= 5 else "middle",
                "bands": _C_BAND}
    else:
        band = None
        dev.append("band withheld: signals missing for " + ", ".join(missing))
    basis = (
        "Montier C-Score = sum(C1..C6): NI-vs-CFO divergence widened; receivable days; "
        "inventory days; other current assets; depreciation/gross fixed assets; "
        "total assets +10%. RISK SCREEN - not a short signal."
    )
    return {
        "score": score,
        "signals": signals,
        "band": band,
        "basis": basis,
        "deviations": dev,
        "risk_screen": True,
    }
