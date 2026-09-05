"""Earnings-quality verdict (quant-engine v2 A3, advisory).

Consolidates the 2025 institutional consensus into one advisory verdict:
- OCF/NI > 1.0 healthy, 0.8-1.0 caution, < 0.8 warning
- accrual ratio (NI-OCF)/TA: <5% acceptable, 5-10% elevated, >10% concerning
- FCF = OCF - capex; persistent negative FCF + positive NI = red flag
- "rising EPS while FCF/OCF deteriorates" -> quality penalty flag
Pure / None-safe: missing inputs degrade that check to n/a (never a
fabricated number).
"""

from __future__ import annotations


def _num(x, default=None):
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def earnings_quality_verdict(
    net_income: float | None,
    ocf: float | None,
    total_assets: float | None,
    *,
    fcf: float | None = None,
    capex: float | None = None,
    eps_growth: float | None = None,
    fcf_growth: float | None = None,
) -> dict:
    """Advisory earnings-quality verdict from the consensus thresholds.

    Returns ``{'level': 'LOW'|'MEDIUM'|'HIGH', 'evidence': [..],
    'cash_conversion': float|None, 'accrual': float|None, 'fcf': float|None,
    'flags': [..]}``. Evidence counts flags -> level (>=2 HIGH, >=1 MEDIUM,
    else LOW). FCF = OCF - |capex| (capex treated as a magnitude; vendors may
    sign it as a GAAP outflow). No inputs -> {'level': None, ...} (n/a).
    """
    ni = _num(net_income)
    o = _num(ocf)
    ta = _num(total_assets)
    fc = _num(fcf)
    cx = _num(capex)
    eg = _num(eps_growth)
    fg = _num(fcf_growth)
    if fc is None and cx is not None and o is not None:
        # Capex is a magnitude: vendors may sign it as a GAAP outflow
        # (yfinance/Tiingo) or a positive value; |capex| matches the DCF
        # machinery's convention so OCF - capex never inflates FCF.
        fc = o - abs(cx)
    if (ni is None and o is None and ta is None and fc is None
            and cx is None and eg is None and fg is None):
        return {"level": None, "evidence": [], "cash_conversion": None,
                "accrual": None, "fcf": None, "flags": []}
    evidence: list = []
    flags: list = []
    cc = None
    accrual = None
    if ni is not None and o is not None:
        if ni != 0:
            cc = o / ni
            if cc >= 1.0:
                flags.append("cash_conversion_healthy")
            elif cc >= 0.8:
                flags.append("cash_conversion_caution")
                evidence.append(f"cash conversion {cc:.2f} (0.8-1.0 caution)")
            else:
                flags.append("cash_conversion_warning")
                evidence.append(f"cash conversion {cc:.2f} (< 0.8 warning)")
        if ta:
            accrual = (ni - o) / ta
            if accrual > 0.10:
                evidence.append(f"accruals {accrual:.3f} (> 10% concerning)")
            elif accrual > 0.05:
                evidence.append(f"accruals {accrual:.3f} (5-10% elevated)")
    if ni is not None and fc is not None and fc < 0 and ni > 0:
        evidence.append("negative FCF with positive NI (red flag)")
    if eg is not None and fg is not None and eg > 0 and fg < 0:
        evidence.append("rising EPS while FCF falls (quality penalty)")
    level = "LOW" if not evidence else "HIGH" if len(evidence) >= 2 else "MEDIUM"
    return {
        "level": level,
        "evidence": evidence,
        "cash_conversion": round(cc, 3) if cc is not None else None,
        "accrual": round(accrual, 4) if accrual is not None else None,
        "fcf": round(fc, 2) if fc is not None else None,
        "flags": flags,
    }


__all__ = ["earnings_quality_verdict"]
