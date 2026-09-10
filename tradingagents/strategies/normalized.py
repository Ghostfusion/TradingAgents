"""V1 - normalized earnings, historical percentile valuation and trap verdict.

Value-style fixes: cyclical peak/trough earnings misprice names, so we
normalize EBIT to a 5-year median margin, express valuation relative to the
name's own history (5y percentile), and collapse the forensic gates into one
auditable trap-risk verdict.
"""

from __future__ import annotations

import math


def median_norm_ebit(
    revenues: list, ebit_margins: list | None = None, ebits: list | None = None, years: int = 5
) -> float | None:
    """Normalized EBIT = 5y median EBIT margin x current sales.

    Feed either a margin series directly, or separate revenue+EBIT series.
    """
    current_sales = revenues[-1] if revenues else None
    if current_sales is None or current_sales <= 0:
        return None
    if ebit_margins is None:
        ebit_margins = []
        for rev, eb in zip(revenues, ebits if ebits else [], strict=False):
            if rev and rev > 0:
                ebit_margins.append(eb / rev)
    sample = [m for m in ebit_margins if m is not None]
    if not sample:
        return None
    sample_sorted = sorted(sample[-years:] if years else sample)
    median = sample_sorted[len(sample_sorted) // 2]
    return median * current_sales


def percentile_hist(value: float | None, series: list) -> float:
    """Percentile rank (0-1) of `value` within its trailing history; 0.5 fallback."""
    vals = [float(v) for v in series if v is not None]
    if value is None or not vals:
        return 0.5
    below = sum(1 for v in vals if v <= value)
    return below / len(vals)


def accruals_ratio(
    net_income: float | None, cfo: float | None, total_assets: float | None
) -> float | None:
    """Sloan-style accruals ratio = (NI - CFO) / TA (high = earnings quality risk)."""
    if net_income is None or cfo is None or not total_assets:
        return None
    if abs(total_assets) < 1e-9:
        return None
    return (net_income - cfo) / total_assets


def trap_verdict(
    *,
    f_score=None,
    m_score=None,
    z_score=None,
    mom12: float | None = None,
    accrual: float | None = None,
    thresholds: dict = None,
) -> dict:
    """Collapse forensic gates into trap risk LOW/MEDIUM/HIGH + evidence list.

    Evidence triggers: Beneish M > -1.78 (manipulation), Altman Z < 1.81
    (distress), negative 12-1m momentum, accrual > 0.06, no F-Score.
    """
    th = thresholds or {}
    evidence = []
    if z_score is not None and z_score < th.get("z_floor", 1.78):
        evidence.append(f"altman_z={z_score:.2f} (distress)")
    if m_score is not None and m_score > th.get("m_suspect", -1.78):
        evidence.append(f"beneish_m={m_score:.2f} (manipulation-risk)")
    if mom12 is not None and mom12 < th.get("mom_floor", 0.0):
        evidence.append("12-1m momentum negative")
    if accrual is not None and accrual > th.get("accrual_cap", 0.06):
        evidence.append(f"accruals={accrual:.3f}")
    if f_score is not None and f_score < th.get("f_floor", 4):
        evidence.append(f"f_score={f_score} (< {th.get('f_floor', 4)})")
    if not evidence:
        return {"level": "LOW", "evidence": []}
    level = "HIGH" if len(evidence) >= 2 else "MEDIUM"
    return {"level": level, "evidence": evidence}


def margin_of_safety(price: float, intrinsic: float | None) -> float | None:
    """(intrinsic - price) / intrinsic; None when unquantifiable."""
    if not intrinsic or intrinsic <= 0 or price is None:
        return None
    return (intrinsic - price) / intrinsic


def margin_of_safety_bases(price: float, intrinsic: float | None) -> dict:
    """MoS under both denominator conventions + the price/intrinsic multiple.

    ``fv_basis`` == (IV - P) / IV  (the project's conventional margin_of_safety;
    how far below fair value the price is).
    ``price_basis`` == (IV - P) / P (negative: the discount/premium relative to
    the price; equals -(price/IV - 1)).
    ``price_to_intrinsic`` == P / IV.
    None-safe: returns None for any field when a denominator is unquantifiable.
    """
    if intrinsic is None or intrinsic <= 0 or price is None:
        return {"fv_basis": None, "price_basis": None, "price_to_intrinsic": None}
    p, iv = float(price), float(intrinsic)
    return {
        "fv_basis": (iv - p) / iv,
        "price_basis": (iv - p) / p,
        "price_to_intrinsic": p / iv,
    }


def _fnum(v) -> float | None:
    """Coerce to float or None (None-safe)."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ohlson_o_score(
    total_assets: float | None,
    total_liabilities: float | None,
    working_capital: float | None,
    current_assets: float | None,
    current_liabilities: float | None,
    net_income: float | None,
    funds_from_ops: float | None,
    ni_prev: float | None = None,
    total_assets_prev: float | None = None,
) -> dict:
    """Ohlson (1980) O-score — logit bankruptcy/distress probability.

    ``O = -1.32 - 0.407*SIZE + 6.03*TLTA - 1.43*WCTA + 0.0757*CLCA
    - 1.72*OENEG - 2.37*NITA - 1.83*FUTL + 0.285*INTWO - 0.521*CHIN``,
    ``p = 1/(1+e^-O)``. SIZE = ln(total_assets); TLTA = liabilities/assets;
    WCTA = working capital/assets; CLCA = current liab/current assets;
    OENEG = 1 if liabilities > assets; NITA = NI/assets; FUTL = FFO/liab;
    INTWO = 1 if NI negative in prior year too (uses ``ni_prev`` when given,
    else 0); CHIN = (NI_t - NI_{t-1})/(|NI_t|+|NI_{t-1}|) or 0.

    Complements Altman Z in the analyst verdict (a different functional form
    validated on the same distress question). Returns ``{'score','p',
    'verdict'}``; ``verdict`` = ``distress`` (p > 0.5) / ``watch`` (p > 0.2) /
    ``healthy``; all None when the core inputs are missing.
    """
    ta = _fnum(total_assets)
    tl = _fnum(total_liabilities)
    wc = _fnum(working_capital)
    ca = _fnum(current_assets)
    cl = _fnum(current_liabilities)
    ni = _fnum(net_income)
    ffo = _fnum(funds_from_ops)
    nip = _fnum(ni_prev)
    if ta is None or tl is None or ni is None:
        return {"score": None, "p": None, "verdict": None}
    if ta <= 0:
        return {"score": None, "p": None, "verdict": None}
    size = math.log(ta)
    tlta = tl / ta
    wcta = wc / ta if wc is not None else 0.0
    clca = (cl / ca) if (cl is not None and ca and ca > 0) else 0.0
    oeneg = 1.0 if tl > ta else 0.0
    nita = ni / ta
    futl = ffo / tl if (ffo is not None and tl and tl > 0) else 0.0
    intwo = 1.0 if (nip is not None and nip < 0) else 0.0
    chin = 0.0
    if ni is not None and nip is not None and (abs(ni) + abs(nip)) > 0:
        chin = (ni - nip) / (abs(ni) + abs(nip))
    o = (-1.32 - 0.407 * size + 6.03 * tlta - 1.43 * wcta + 0.0757 * clca
         - 1.72 * oeneg - 2.37 * nita - 1.83 * futl + 0.285 * intwo
         - 0.521 * chin)
    try:
        p = 1.0 / (1.0 + math.exp(-o))
    except OverflowError:
        p = 1.0 if o > 0 else 0.0
    verdict = "distress" if p > 0.5 else "watch" if p > 0.2 else "healthy"
    return {"score": round(o, 4), "p": round(p, 4), "verdict": verdict}


def zmijewski_score(
    net_income: float | None,
    total_assets: float | None,
    total_liabilities: float | None,
    current_assets: float | None,
    current_liabilities: float | None,
) -> dict:
    """Zmijewski (1984) X-score — probit distress.

    ``X = -4.336 - 4.513*ROA + 5.679*TLTA - 0.004*CACL`` where CACL is the
    CURRENT RATIO CA/CL (canonical published form); cutoff 0 (X > 0 =
    distress / higher bankruptcy risk). None-safe like the rest.
    """
    ni = _fnum(net_income)
    ta = _fnum(total_assets)
    tl = _fnum(total_liabilities)
    ca = _fnum(current_assets)
    cl = _fnum(current_liabilities)
    if ni is None or ta is None or tl is None or ta <= 0:
        return {"score": None, "verdict": None}
    roa = ni / ta
    tlta = tl / ta
    # canonical liquidity term is the current ratio CA/CL with a -0.004
    # coefficient (the old CL/CA inverted the (weak) liquidity direction)
    cacl = ca / cl if (ca is not None and cl and cl > 0) else 0.0
    x = -4.336 - 4.513 * roa + 5.679 * tlta - 0.004 * cacl
    verdict = "distress" if x > 0 else "healthy"
    return {"score": round(x, 4), "verdict": verdict}


__all__ = [
    "median_norm_ebit",
    "percentile_hist",
    "accruals_ratio",
    "trap_verdict",
    "margin_of_safety",
    "ohlson_o_score",
    "zmijewski_score",
]
