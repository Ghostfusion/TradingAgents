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
            if ni < 0:
                # Negative income inverts the ratio's meaning: the 0.8/1.0
                # warning bands assume a positive denominator. A negative NI
                # with positive OCF means non-cash charges + working-capital
                # effects dominate the gap, not uncollected paper earnings
                # (IREN 2026-09-10 review loop).
                if cc < 0:
                    flags.append("cash_conversion_negative_ni")
                    evidence.append(
                        f"cash conversion {cc:.2f} (negative NI - ratio sign "
                        "inverted; inspect non-cash items instead of the "
                        "< 0.8 warning)"
                    )
                elif cc < 1.0:
                    flags.append("cash_conversion_caution")
                    evidence.append(f"cash conversion {cc:.2f} (0-1 with negative NI)")
            elif cc >= 1.0:
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


def dechow_dichev_aq(accruals: list, cfo: list) -> float | None:
    """Dechow-Dichev accrual quality = residual std of the regression of
    working-capital accruals on cash from operations lagged/current/lead.

    Regresses ``accruals_t`` on ``[cfo_{t-1}, cfo_t, cfo_{t+1}]`` (OLS) and
    returns the residual standard deviation (smaller = better accrual quality
    — accruals map into cash flow). Requires >= 6 aligned periods (enough
    residual degrees of freedom); None otherwise / zero-variance regressor.
    The accrual series is centered first (the classical DD uses period t
    working-capital accruals; a mean-shift is immaterial to the residual std).
    """
    a = [float(x) for x in (accruals or []) if x is not None]
    c = [float(x) for x in (cfo or []) if x is not None]
    n = min(len(a), len(c))
    if n < 6:
        return None
    # build aligned regressor rows: [cfo_{t-1}, cfo_t, cfo_{t+1}]
    rows = []
    y = []
    for i in range(1, n - 1):
        rows.append([c[i - 1], c[i], c[i + 1]])
        y.append(a[i])
    if len(rows) < 6:
        return None
    # OLS via normal equations
    X = [[1.0] + r for r in rows]
    k = len(X[0])
    m = len(X)
    XtX = [[sum(X[t][i] * X[t][j] for t in range(m)) for j in range(k)] for i in range(k)]
    Xty = [sum(X[t][i] * y[t] for t in range(m)) for i in range(k)]
    try:
        # Gaussian elimination
        aug = [row[:] + [Xty[i]] for i, row in enumerate(XtX)]
        nk = k
        for col in range(nk):
            pivot = max(range(col, nk), key=lambda r: abs(aug[r][col]))
            aug[col], aug[pivot] = aug[pivot], aug[col]
            pv = aug[col][col]
            if abs(pv) < 1e-12:
                return None
            aug[col] = [v / pv for v in aug[col]]
            for r in range(nk):
                if r != col and abs(aug[r][col]) > 1e-15:
                    f = aug[r][col]
                    aug[r] = [aug[r][j] - f * aug[col][j] for j in range(nk + 1)]
        beta = [aug[i][nk] for i in range(nk)]
    except (ZeroDivisionError, ValueError):
        return None
    resid = [y[i] - sum(beta[j] * X[i][j] for j in range(k)) for i in range(m)]
    rss = sum(rr * rr for rr in resid)
    dof = m - k
    if dof <= 0:
        return None
    return round((rss / dof) ** 0.5, 6)


__all__ = ["earnings_quality_verdict", "dechow_dichev_aq"]
