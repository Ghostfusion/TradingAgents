"""Capital-allocation / CapEx-quality read (advisory, pure, deterministic).

AMZN 2026-09-09 report-review lesson: one trailing FCF sign is NOT a quality
verdict for a high-capex name. ``capex_quality_read`` separates PRODUCTIVE
investment from OVERINVESTMENT / DISTRESS along the dimensions the external
review proposed:

* CapEx intensity  = |capex| / revenue (z vs the name's own history; no
  sector panel by design)
* FCF margin / yield = (OCF - |capex|) based
* Funding cover     = OCF / |capex|    (CapEx funding stress)
* CapEx 5y CAGR vs revenue 5y CAGR     (investment-vs-scale elasticity)
* Incremental ROIC = dNOPAT / d(Invested Capital)     (3y lag)
* CapEx ROI 3y     = dNOPAT / d|capex|
* Economic spread  = incremental ROIC - WACC
* Payback 3y       = d|capex| / (dNOPAT + dD&A)   (FCF-noise-avoided)
* FCF recovery gap = max(0, mcap*target_yield - FCF)
* 5-regime label + 0-100 score + valuation-penalty points

NEVER a hard gate: it feeds the analyst narrative / PM discussion only.
Every unavailable input degrades to explicit None (n/a), the composite
renormalizes over measured components, and partial reads are labeled.

Series convention: oldest-first lists, None allowed; the read anchors on the
latest non-None year.
"""

from __future__ import annotations

from statistics import fmean, pstdev

__all__ = ["capex_quality_read"]


def _num(x) -> float | None:
    try:
        v = float(x)
        return v if v == v else None  # noqa: PLR0124 NaN guard
    except (TypeError, ValueError):
        return None


def _num_seq(s) -> list:
    return [_num(v) for v in (s or [])]


def _last(seq) -> float | None:
    s = _num_seq(seq)
    return s[-1] if s else None


def _cagr(seq, min_span: int = 5) -> float | None:
    """CAGR over the measured span (need >= min_span+1 values)."""
    s = [v for v in _num_seq(seq) if v is not None]
    if len(s) < min_span + 1:
        return None
    lo, hi = s[0], s[-1]
    if lo in (None, 0.0) or hi in (None, 0.0):
        return None
    return (hi / lo) ** (1.0 / (len(s) - 1)) - 1.0


def _delta(seq, lag: int = 3) -> float | None:
    s = [v for v in _num_seq(seq) if v is not None]
    if len(s) < lag + 1:
        return None
    return s[-1] - s[-lag - 1]


def _score01(v, lo, hi) -> float | None:
    """Linear 0..1 map over [lo, hi]; None passthrough; degenerate guard."""
    if v is None or hi <= lo:
        return None
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def _inv01(v, lo, hi) -> float | None:
    """Inverted linear map (1 - score01); None passthrough."""
    s = _score01(v, lo, hi)
    return (1.0 - s) if s is not None else None


def _quality_score(
    *,
    fcf_y: float | None,
    cap_z: float | None,
    funding: float | None,
    elasticity: float | None,
    incr_roic: float | None,
    spread: float | None,
    cap_roi_3y: float | None,
    payback_3y: float | None,
    wacc: float,
    target_fcf_yield: float,
    cap_rev: float | None,
) -> float | None:
    """0-100 weighted composite over whatever components are measurable.

    Weights mirror the external review proposal (yield 15, intensity-z 10,
    funding 10, elasticity 5, incremental ROIC 20, spread 15, CapEx ROI 10,
    payback 10, cap_rev 5). Missing components are dropped and present
    weights renormalized, so the score states exactly what it measured.
    """
    components: list[tuple[float | None, float]] = [
        (_score01(fcf_y, 0.0, target_fcf_yield), 15),      # FCF yield
        (_inv01(cap_z, -1.0, 2.0), 10),                    # intensity z (own hist)
        (_score01(funding, 0.6, 1.5), 10),                 # funding cover
        (_inv01(elasticity, 1.0, 2.5), 5),                 # capex elasticity
        (_score01(incr_roic, 0.0, wacc * 2.0), 20),        # incremental ROIC
        (_score01(spread, wacc - 0.10, wacc + 0.05), 15),  # economic spread
        (_score01(cap_roi_3y, 0.0, 0.25), 10),             # CapEx ROI 3y
        (_inv01(payback_3y, 2.0, 12.0), 10),               # payback
        (_score01(cap_rev, 0.0, 0.30), 5),                 # intensity level
    ]
    acc = 0.0
    w_sum = 0.0
    for c, w in components:
        if c is not None:
            acc += c * w
            w_sum += w
    if w_sum <= 0:
        return None
    return round(acc / w_sum * 100.0, 1)


def capex_quality_read(
    revenue,
    ocf,
    capex,
    nopat,
    invested_capital=None,
    deprec_amort=None,
    market_cap=None,
    wacc: float | None = None,
    target_fcf_yield: float = 0.03,
) -> dict:
    """CapEx-allocation read from annual series (oldest-first, None ok).

    Returns every metric + ``regime`` (HARVEST / PRODUCTIVE /
    PRODUCTIVE_INVESTMENT / INVESTMENT_WATCH / OVERINVESTMENT / DISTRESS or
    "n/a"), ``score`` (0-100) and ``penalty_points`` (0-30, advisory).
    """
    wacc_f = 0.12 if (w := _num(wacc)) is None else w
    rev = _num_seq(revenue)
    ocf_s = _num_seq(ocf)
    capex_s = []
    for v in _num_seq(capex):
        capex_s.append(abs(v) if v is not None else None)
    nopat_s = _num_seq(nopat)
    ic_s = _num_seq(invested_capital) if invested_capital is not None else []
    da_s = _num_seq(deprec_amort) if deprec_amort is not None else []

    oc_l = _last(ocf_s)
    cx_l = _last(capex_s)
    rev_l = _last(rev)
    mc_l = _num(market_cap)

    fcf_l = (oc_l - cx_l) if (oc_l is not None and cx_l is not None) else None

    # intensity z vs the series' own history
    ratios: list = []
    for v, rv in zip(capex_s, rev, strict=False):
        if v is None or rv in (None, 0.0):
            continue
        ratios.append(v / rv)
    cap_z = None
    if len(ratios) >= 4:
        m = fmean(ratios)
        s = pstdev(ratios)
        if s and s == s:
            cap_z = round((ratios[-1] - m) / s, 2)

    funding = (oc_l / cx_l) if (oc_l is not None and cx_l not in (None, 0.0)) else None
    cap_rev = (cx_l / rev_l) if (cx_l is not None and rev_l not in (None, 0.0)) else None
    capex_cagr = _cagr(capex_s, 5)
    rev_cagr = _cagr(rev, 5)
    elasticity = None
    if capex_cagr is not None and rev_cagr is not None and abs(rev_cagr) > 0.005:
        elasticity = capex_cagr / rev_cagr

    d_nopat = _delta(nopat_s, 3)
    d_ic = _delta(ic_s, 3) if ic_s else None
    d_cx = _delta(capex_s, 3)
    incr_roic = None
    if d_nopat is not None and d_ic and d_ic not in (None, 0.0):
        incr_roic = d_nopat / d_ic
    spread = (incr_roic - wacc_f) if (incr_roic is not None and wacc_f is not None) else None
    cap_roi_3y = (d_nopat / d_cx) if (d_nopat is not None and d_cx and d_cx not in (None, 0.0)) else None
    payback_3y = None
    if d_cx is not None and d_cx > 0 and d_nopat is not None:
        d_da = _delta(da_s, 3) if da_s else None
        if d_da is not None:
            denom = d_nopat + d_da
            if denom not in (None, 0.0):
                payback_3y = d_cx / denom

    fcf_recovery = None
    if fcf_l is not None and mc_l:
        fcf_recovery = max(0.0, mc_l * target_fcf_yield - fcf_l)

    # ---- regime (deterministic) ----
    if fcf_l is None:
        regime = "n/a"
    elif fcf_l >= 0:
        regime = "HARVEST" if (spread is None or spread >= 0) else "PRODUCTIVE"
    elif funding is not None and funding < 0.6:
        regime = "DISTRESS"
    elif spread is not None and spread < -0.02:
        regime = "OVERINVESTMENT"
    elif incr_roic is not None and incr_roic >= (wacc_f or 0.12) * 0.98:
        regime = "PRODUCTIVE_INVESTMENT"
    elif elasticity is not None and elasticity > 1.3:
        regime = "INVESTMENT_WATCH"
    else:
        regime = "INVESTMENT_WATCH"

    score = _quality_score(
        fcf_y=fcf_l / mc_l if (fcf_l is not None and mc_l) else None,
        cap_z=cap_z,
        funding=funding,
        elasticity=elasticity,
        incr_roic=incr_roic,
        spread=spread,
        cap_roi_3y=cap_roi_3y,
        payback_3y=payback_3y,
        wacc=wacc_f,
        target_fcf_yield=target_fcf_yield,
        cap_rev=cap_rev,
    )

    # advisory valuation penalty from the economic spread
    if spread is None:
        penalty = None
    elif spread > 0.05:
        penalty = 0
    elif spread > 0:
        penalty = 5
    elif spread > -0.05:
        penalty = 10
    elif spread > -0.15:
        penalty = 20
    else:
        penalty = 30

    return {
        "fcf": fcf_l,
        "fcf_yield": fcf_l / mc_l if (fcf_l is not None and mc_l) else None,
        "cap_rev": cap_rev,
        "cap_z": cap_z,
        "funding": funding,
        "cap_cagr5": capex_cagr,
        "rev_cagr5": rev_cagr,
        "elasticity": elasticity,
        "incr_roic": incr_roic,
        "spread": spread,
        "cap_roi_3y": cap_roi_3y,
        "payback_3y": payback_3y,
        "fcf_recovery": fcf_recovery,
        "regime": regime,
        "score": score,
        "penalty_points": penalty,
        "wacc": round(wacc_f, 4),
    }
