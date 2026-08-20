"""V1 - normalized earnings, historical percentile valuation and trap verdict.

Value-style fixes: cyclical peak/trough earnings misprice names, so we
normalize EBIT to a 5-year median margin, express valuation relative to the
name's own history (5y percentile), and collapse the forensic gates into one
auditable trap-risk verdict.
"""

from __future__ import annotations


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
    if accrual is not None and accrual > th.get("accrual_cap", 0.02):
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


__all__ = [
    "median_norm_ebit",
    "percentile_hist",
    "accruals_ratio",
    "trap_verdict",
    "margin_of_safety",
]
