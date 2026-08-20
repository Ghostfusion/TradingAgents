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
    depi = _ratio(_ratio(dep_p, _sub(ppe_p, dep_p)), _ratio(dep, _sub(ppe, dep)))
    sga = _num(fin.get("sga"))
    sga_p = _num(_prv(fin.get("sga")))
    sgai = _ratio(_ratio(sga, rev), _ratio(sga_p, rev_p))
    cl = _num(fin.get("current_liabilities"))
    ltd = _num(fin.get("total_debt"))
    cl_p = _num(_prv(fin.get("current_liabilities")))
    ltd_p = _num(_prv(fin.get("total_debt")))
    lvgi = _ratio(_ratio(_sub(cl, ltd), ta), _ratio(_sub(cl_p, ltd_p), ta_p))
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
    if _num(fin.get("roa")) or 0 > 0:
        score += 1
    if cfo > 0:
        score += 1
    if _sub(cfo, ni) and _sub(cfo, ni) > 0:
        score += 1
    roa = _num(fin.get("roa"))
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
