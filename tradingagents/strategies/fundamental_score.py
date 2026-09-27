"""`FundamentalScore` - the four category sub-scores and their research composite.

The engine the owner's decisions Q1/Q2/Q5 draw a line through:

- **Published, advisory, deterministic:** the four category sub-scores - FQS
  (quality / profitability), FGS (growth), VS (valuation), FRS (financial risk) -
  each 0-100 over a peer panel, each with its own band table, coverage, withheld
  names and printed basis. A reader can recompute any of them from the factors
  that produced it.
- **Not published as a production score:** the *composite*. Nothing shows the
  combination has out-of-sample predictive validity, so it ships labelled
  `RESEARCH_ONLY`, without a band table (a label would invite the reading the
  status forbids), and it never reaches `decision_guardrail.SCORE_BANDS`.
- **`OpportunityScore` is a separate measurement and stays `null`.** This module
  has no opinion about it and writes no such key.

Every sub-score is a thin wrapper over the shared core
(`factors.category_scores`, the renamed round-3 quality composite): winsorise
0.01/0.99 -> cross-sectional z -> direction sign -> coverage-gated weighted mean
-> tie-aware percentile x100. The metric sets, directions and weights come from
`factor_schema`, so a factor has **one identity and one direction** repo-wide.

`NA` is not `0`: a factor the panel does not carry for a name is absent from that
name's row, the remaining weights renormalise, and a name below the coverage
floor is withheld with its reason rather than scored on what it lacks.

The DCF is the one factor the owner asked to be *scaled* rather than re-prosed
(§3.4): `dcf_confidence` scores the four legs the DCF family already prints, and
the factor entering VS is the raw upside multiplied by it - so a DCF nobody
could verify contributes less, with no sentence claiming it is an artifact.

Two routes supply that upside, caller-supplied first (FUND-21 / defect D-4): a
caller that owns a DCF passes `dcf_upside` + `dcf_confidence_value` and the
engine uses them unchanged; otherwise `fundamental_score_for_ticker` derives the
upside itself, for **every** panel name whose canonical financials the resolver
returned, from the repo's own producers (`dcf.compute_dcf`, then
`cycle_dcf.perpetuity_value` over `normalized_cycle_fcf`) and the confidence from
`dcf_confidence`. The route is recorded in the result and the basis, and a name
the panel's financials cannot support is `None` **with its reason**.
"""

from __future__ import annotations

import math
import re

from .factor_schema import (
    NA,
    SUBSCORE_FACTORS,
    availability_report,
    directions_for,
    subscore_directions,
    weights_for,
)
from .factors import QUALITY_BANDS, category_scores
from .score_engine import band_label, combine

# --- Advisory band tables --------------------------------------------------
#
# Per master rule 2 nothing here is `decision_guardrail.SCORE_BANDS`, and no
# table is a gate. FQS reuses the published quality table rather than defining a
# second one with the same meaning; the other three are this engine's own.

FQS_BANDS: tuple = QUALITY_BANDS

FGS_BANDS: tuple = (
    (80.0, "compounding"),
    (65.0, "growing"),
    (50.0, "steady"),
    (35.0, "stalling"),
    (20.0, "contracting"),
    (0.0, "shrinking"),
)

VS_BANDS: tuple = (
    (80.0, "cheap"),
    (65.0, "below-market"),
    (50.0, "fair"),
    (35.0, "rich"),
    (20.0, "expensive"),
    (0.0, "priced-for-perfection"),
)

FRS_BANDS: tuple = (
    (80.0, "fortress"),
    (65.0, "solid"),
    (50.0, "adequate"),
    (35.0, "stretched"),
    (20.0, "fragile"),
    (0.0, "distressed"),
)

SUBSCORE_BANDS: dict[str, tuple] = {
    "FQS": FQS_BANDS,
    "FGS": FGS_BANDS,
    "VS": VS_BANDS,
    "FRS": FRS_BANDS,
}

SUBSCORE_TITLES: dict[str, str] = {
    "FQS": "quality / profitability",
    "FGS": "growth",
    "VS": "valuation",
    "FRS": "financial risk",
}

STATUS_ADVISORY = "ADVISORY"
STATUS_RESEARCH_ONLY = "RESEARCH_ONLY"

# The composite's own coverage floor: a "composite" of one category is that
# category, and the design's whole reason for four sub-scores is that the four
# are reported separately. Two is the smallest number that combines anything.
COMPOSITE_MIN_COVERAGE = 2


def _subscore(sub: str, panel: dict, *, min_coverage=3, min_peers: int = 8,
              weights=None, **kw) -> dict:
    """One category sub-score: the shared core plus its own tables and status."""
    factors = SUBSCORE_FACTORS[sub]
    directions = subscore_directions(sub)
    # A factor the schema declares NA for this path must not silently score:
    # it is dropped from the direction table so the core reports it as
    # "no declared direction" if a panel ever carries it anyway.
    declared = availability_report(factors)
    core_directions = {
        f: d for f, d in directions.items() if f not in set(declared[NA])
    }
    res = category_scores(
        panel,
        directions=core_directions,
        weights=weights if weights is not None else weights_for(factors),
        min_coverage=_cap_floor(min_coverage, len(core_directions)),
        min_peers=min_peers,
        label=f"{sub} ({SUBSCORE_TITLES[sub]})",
        **kw,
    )
    bands = SUBSCORE_BANDS[sub]
    res["subscore"] = sub
    res["status"] = STATUS_ADVISORY
    res["title"] = SUBSCORE_TITLES[sub]
    res["bands"] = {
        name: band_label(score, bands) for name, score in (res.get("scores") or {}).items()
    }
    res["factors_declared"] = list(factors)
    res["factors_NA"] = declared[NA]
    res["directions"] = dict(directions)
    _restate_coverage_over_declared_factors(res, core_directions)
    return res


def _cap_floor(min_coverage, n_declared: int):
    """A count floor can never exceed the sub-score's own factor count.

    FGS has two factors with a supplier on this path; the design's default floor
    of 3 would withhold **every** name from it forever - an off switch wearing a
    floor's name. The floor is capped at the declared count (FQS's 7 leaves a
    floor of 3 alone), and a fraction is passed through: the core resolves it
    against the set it is actually given.
    """
    if isinstance(min_coverage, float) and 0.0 < min_coverage <= 1.0:
        return min_coverage
    try:
        return max(1, min(int(min_coverage), int(n_declared)))
    except (TypeError, ValueError):
        return 1


def _restate_coverage_over_declared_factors(res: dict, directions: dict) -> None:
    """Report each name's coverage over THIS sub-score's factors, not the panel's.

    ``category_scores`` counts coverage against the panel's whole metric set -
    correct for the quality composite, whose metric set *is* the panel's, and
    wrong for a sub-score: a name carrying 3 of FQS's 7 factors would print
    "3 of 12" because the panel also carries valuation and risk metrics FQS never
    reads. The denominator here is the sub-score's own declared factor set, so
    the number means "3 of the 7 factors this sub-score is made of".
    """
    declared = set(directions)
    floor = res.get("floor")
    res["metrics_used"] = [m for m in (res.get("metrics_used") or []) if m in declared]
    res["metrics_dropped"] = {
        m: why for m, why in (res.get("metrics_dropped") or {}).items() if m in declared
    }
    if res.get("basis"):
        # The core prints the floor against the PANEL's metric count; the
        # sub-score's reader needs the sub-score's. The substring is the core's
        # own formatting, pinned by a test.
        res["basis"] = re.sub(
            r"coverage floor (\d+) of (\d+) metrics",
            lambda m: f"coverage floor {m.group(1)} of {len(declared)} factors",
            str(res["basis"]),
        )
    cov = {}
    for name, entry in (res.get("coverage") or {}).items():
        metrics = [m for m in (entry.get("metrics") or []) if m in declared]
        cov[name] = {"n": len(metrics), "of": len(declared), "metrics": metrics}
    res["coverage"] = cov
    if floor is not None:
        res["withheld"] = {
            name: (
                f"coverage {entry['n']} of {entry['of']} factors < floor {floor}"
                if entry["n"] < floor
                else reason
            )
            for name, reason in (res.get("withheld") or {}).items()
            for entry in [cov.get(name) or {"n": 0, "of": len(declared)}]
        }


def quality_subscore(panel: dict, **kw) -> dict:
    """FQS - quality / profitability over the peer panel."""
    return _subscore("FQS", panel, **kw)


def growth_subscore(panel: dict, **kw) -> dict:
    """FGS - growth over the peer panel."""
    return _subscore("FGS", panel, **kw)


def valuation_subscore(panel: dict, **kw) -> dict:
    """VS - valuation over the peer panel.

    ``dcf_upside`` arrives already scaled by ``dcf_confidence`` when the caller
    has a DCF: the scaling is the caller's, because it is the only party that
    knows the four legs (see ``dcf_confidence``).
    """
    return _subscore("VS", panel, **kw)


def risk_subscore(panel: dict, **kw) -> dict:
    """FRS - financial risk over the peer panel."""
    return _subscore("FRS", panel, **kw)


SUBSCORE_FUNCS = {
    "FQS": quality_subscore,
    "FGS": growth_subscore,
    "VS": valuation_subscore,
    "FRS": risk_subscore,
}


def subscores(panel: dict, *, only=None, **kw) -> dict[str, dict]:
    """``{"FQS": {...}, ...}`` for the requested sub-scores (default: all four)."""
    wanted = tuple(only) if only else tuple(SUBSCORE_FUNCS)
    for sub in wanted:
        if sub not in SUBSCORE_FUNCS:
            raise KeyError(f"unknown sub-score {sub!r}; known: {sorted(SUBSCORE_FUNCS)}")
    return {sub: SUBSCORE_FUNCS[sub](panel, **kw) for sub in wanted}


def fundamental_score(
    panel: dict,
    *,
    weights: dict | None = None,
    min_coverage=COMPOSITE_MIN_COVERAGE,
    subscore_min_coverage=3,
    only=None,
    **kw,
) -> dict:
    """The research composite over the four sub-scores, or withheld with a reason.

    ``panel`` is ``{ticker: {factor: value}}`` - the same shape
    ``factors.category_scores`` consumes, so one panel feeds all four.

    ``min_coverage`` is the **composite's** floor (how many of the four
    sub-scores must be present); ``subscore_min_coverage`` is each sub-score's
    own floor over its factor set. They are different questions and are kept
    apart: a name can carry a fully-covered VS and an FQS below its own floor.

    ``weights`` is the composite's own vector over sub-score names; ``None``
    means equal weights, which is what this ships with: the source's
    ``0.35/0.25/0.25/0.15`` and the owner's withdrawn ``40/25/15/20`` are both
    unmeasured, so the engine runs ``1/4`` each and **prints that fact** rather
    than adopting either.

    Returns ``{"scores", "coverage", "components", "withheld", "subscores",
    "weights", "status", "basis", "unavailable"}``. ``scores`` is ``None`` for a
    name whose sub-scores fall below the floor - never 0, never 50.
    """
    subs = subscores(panel, only=only, min_coverage=subscore_min_coverage, **kw)
    names = sorted({t for s in subs.values() for t in (s.get("scores") or {})})
    scored_names = sorted({t for s in subs.values() for t in (s.get("coverage") or {})})
    all_names = sorted(set(names) | set(scored_names))

    out_scores: dict[str, float | None] = {}
    out_cov: dict[str, dict] = {}
    out_comp: dict[str, dict] = {}
    out_withheld: dict[str, str] = {}
    for name in all_names:
        comps = {
            sub: (res.get("scores") or {}).get(name)
            for sub, res in subs.items()
        }
        combined = combine(comps, weights=weights, min_coverage=min_coverage)
        out_comp[name] = dict(combined.get("components") or {})
        present = [s for s, v in comps.items() if v is not None]
        total = len(comps)
        out_cov[name] = {
            "n": len(present),
            "of": total,
            "subscores": present,
            "coverage": combined.get("coverage"),
        }
        if combined.get("score") is None:
            out_withheld[name] = combined.get("withheld") or "composite withheld"
            out_scores[name] = None
        else:
            out_scores[name] = combined["score"]

    w_basis = (
        "equal weights (1/4 each; no validated vector published)"
        if weights is None
        else "weights: " + ", ".join(f"{k}={float(v):g}" for k, v in sorted(weights.items()))
    )
    basis = (
        f"FundamentalScore composite [{STATUS_RESEARCH_ONLY}]: {w_basis} over "
        f"{len(subs)} sub-score(s) {sorted(subs)} -> {len(names)} name(s) scored, "
        f"{len(out_withheld)} withheld (floor {min_coverage} present sub-scores); "
        f"the four sub-scores are the advisory output, the composite is a research "
        f"artifact until Phase C measures it; no band table is applied"
    )
    unavailable = None
    if not names:
        unavailable = "no sub-score produced a scored name"
    return {
        "scores": out_scores,
        "coverage": out_cov,
        # Fundamental is a PANEL engine: `coverage` is per-name, so the floor is
        # the sub-score count each name must present, not a per-name value.
        "floor": min_coverage,
        "components": out_comp,
        "withheld": out_withheld,
        "subscores": subs,
        "weights": dict(weights) if weights is not None else None,
        "status": STATUS_RESEARCH_ONLY,
        "basis": basis,
        "unavailable": unavailable,
    }


# --- DCF confidence (§3.4) -------------------------------------------------

# A DCF whose legs could not all be read cannot be more than this confident.
# One documented constant with one meaning ("we could not verify all four
# legs"), measured against realised forward returns in Phase C - not a grade an
# implementer assigns.
INCOMPLETE_CAP = 0.6

DCF_THRESHOLDS: dict = {
    # assumption stability: an assumed beta inside this fraction of its own
    # value is a narrow sensitivity; wider is a wider range of fair values.
    "beta_narrow": 0.20,
    # terminal sensitivity: a terminal value share at or below ``share_ok`` is
    # unremarkable, at or above ``share_high`` the fair value is mostly a
    # terminal assumption.
    "share_ok": 0.60,
    "share_high": 0.90,
    "share_floor": 0.30,
    # fcf stability: the coefficient of variation at or above which the annual
    # FCF series is too uneven for a single growth assumption.
    "fcf_cv_bad": 1.0,
    "fcf_min_obs": 3,
    "incomplete_cap": INCOMPLETE_CAP,
}


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _leg_data_quality(basis_conflict, basis) -> tuple[float | None, str]:
    if basis_conflict:
        return 0.6, f"basis conflict: {basis_conflict}"
    if not basis:
        return 0.6, "no basis stated by the DCF payload"
    return 1.0, f"single stated basis ({basis}), no conflict"


def _leg_assumption_stability(beta, beta_assumed, beta_range, thresholds) -> tuple[float | None, str]:
    if beta is None:
        return None, "beta not reported"
    if not beta_assumed:
        return 1.0, f"beta {beta:g} measured, not assumed"
    if beta_range is None:
        return 0.6, f"beta {beta:g} assumed, sensitivity range not reported"
    try:
        spread = abs(float(beta_range))
    except (TypeError, ValueError):
        return 0.6, f"beta {beta:g} assumed, sensitivity range unreadable"
    rel = spread / abs(float(beta)) if beta else 1.0
    if rel <= float(thresholds["beta_narrow"]):
        return 0.85, f"beta {beta:g} assumed within +/-{rel:.0%} of itself"
    return 0.6, f"beta {beta:g} assumed across +/-{rel:.0%} of itself"


def _leg_fcf_stability(fcf_series, thresholds) -> tuple[float | None, str]:
    vals = [float(v) for v in (fcf_series or []) if v is not None and math.isfinite(float(v))]
    n = len(vals)
    if n < int(thresholds["fcf_min_obs"]):
        return None, f"annual FCF series has {n} period(s), needs {int(thresholds['fcf_min_obs'])}"
    mean = sum(vals) / n
    if mean == 0:
        return None, "annual FCF series has a zero mean (no scale to compare against)"
    var = sum((v - mean) ** 2 for v in vals) / n
    cv = (var ** 0.5) / abs(mean)
    bad = float(thresholds["fcf_cv_bad"])
    score = _clamp01(1.0 - (cv / bad)) if bad > 0 else 0.0
    return score, f"annual FCF coefficient of variation {cv:.2f} over {n} periods"


def _leg_terminal_sensitivity(terminal_share, thresholds) -> tuple[float | None, str]:
    if terminal_share is None:
        return None, "terminal value share not reported"
    try:
        share = float(terminal_share)
    except (TypeError, ValueError):
        return None, "terminal value share unreadable"
    ok = float(thresholds["share_ok"])
    high = float(thresholds["share_high"])
    floor = float(thresholds["share_floor"])
    if share <= ok:
        return 1.0, f"terminal value is {share:.0%} of fair value"
    if share >= high:
        return floor, f"terminal value is {share:.0%} of fair value"
    frac = (share - ok) / (high - ok)
    return 1.0 - frac * (1.0 - floor), f"terminal value is {share:.0%} of fair value"


def dcf_confidence(
    *,
    basis: str | None = None,
    basis_conflict=None,
    beta: float | None = None,
    beta_assumed: bool = False,
    beta_range: float | None = None,
    fcf_series=None,
    terminal_share: float | None = None,
    thresholds: dict | None = None,
) -> dict:
    """0-1 confidence in a DCF read, from the four legs the family already prints.

    Every leg is measured, never asserted (§3.3/§3.4): data quality from the
    payload's own basis registry and conflict flag, assumption stability from
    whether beta was assumed and how wide its sensitivity range is, FCF stability
    from the coefficient of variation of the annual FCF series, terminal
    sensitivity from the terminal share of fair value.

    A leg that cannot be read is ``None`` and is listed in ``legs_missing`` - the
    confidence is then capped at ``INCOMPLETE_CAP`` (see its comment) rather than
    silently inheriting full credit from the legs that *were* readable.

    Returns ``{"confidence", "legs", "reasons", "legs_missing", "complete",
    "thresholds", "basis"}``. ``confidence`` is ``None`` only when no leg could be
    read at all.
    """
    th = dict(DCF_THRESHOLDS)
    if thresholds:
        th.update(thresholds)
    legs: dict[str, float | None] = {}
    reasons: dict[str, str] = {}
    for name, (value, why) in (
        ("data_quality", _leg_data_quality(basis_conflict, basis)),
        ("assumption_stability", _leg_assumption_stability(beta, beta_assumed, beta_range, th)),
        ("fcf_stability", _leg_fcf_stability(fcf_series, th)),
        ("terminal_sensitivity", _leg_terminal_sensitivity(terminal_share, th)),
    ):
        legs[name] = None if value is None else round(float(value), 4)
        reasons[name] = why
    missing = sorted(k for k, v in legs.items() if v is None)
    present = [v for v in legs.values() if v is not None]
    confidence = None
    if present:
        prod = 1.0
        for v in present:
            prod *= float(v)
        if missing:
            prod = min(prod, float(th["incomplete_cap"]))
        confidence = round(prod, 4)
    basis_str = (
        "dcf confidence: product of the measured legs "
        f"{sorted(k for k, v in legs.items() if v is not None)}"
        + (f", capped at {th['incomplete_cap']:g} (unread legs: {missing})" if missing else "")
        + (f" -> {confidence}" if confidence is not None else " -> unavailable")
    )
    return {
        "confidence": confidence,
        "legs": legs,
        "reasons": reasons,
        "legs_missing": missing,
        "complete": not missing,
        "thresholds": {k: th[k] for k in sorted(th)},
        "basis": basis_str,
    }


def dcf_upside_scaled(upside, confidence) -> dict:
    """The DCF upside factor, scaled by its confidence - the §3.4 requirement.

    ``upside`` is the raw ``price / fair value``-style factor the DCF family
    produces (``normalized.margin_of_safety_bases``); the effective value the VS
    sub-score consumes is ``upside * confidence``. A ``None`` confidence means no
    DCF read at all, so the effective value is ``None`` - the factor leaves the
    denominator rather than entering at full weight.
    """
    if upside is None or confidence is None:
        return {
            "raw": upside,
            "confidence": confidence,
            "effective": None,
            "basis": "dcf upside: unavailable (no upside or no confidence read)",
        }
    raw = float(upside)
    conf = _clamp01(float(confidence))
    return {
        "raw": raw,
        "confidence": conf,
        "effective": raw * conf,
        "basis": (
            f"dcf upside: raw {raw:.4g} x confidence {conf:.2f} = {raw * conf:.4g}"
        ),
    }


# --- The engine-derived DCF route (FUND-21 / defect D-4) -------------------
#
# The caller-supplied `dcf_upside` is the first route and stays unchanged. This
# is the fallback for every caller that does not own a DCF: the peer-panel
# resolver already fetched each name's canonical financials, so the repo's own
# DCF producers run over that statement instead of leaving the factor dead.
#
# `rf` has no panel source - the DCF leaves read it from a macro vendor - so the
# engine uses the DCF family's own documented fallback (0.04, the value
# `analysis_tools._dcf_context` and `get_normalized_cycle_dcf` both use) and
# STATES the assumption in the basis. A missing beta is not substituted
# silently: it enters `dcf_confidence` as `beta_assumed`, the leg that lowers the
# confidence, exactly as §3.3/§3.4 intend.

DCF_FALLBACK_RF = 0.04
DCF_FALLBACK_ERP = 0.05
DCF_FALLBACK_GROWTH = 0.025
DCF_FALLBACK_YEARS = 5


def _fin_value(v):
    """Current-period value of a canonical item (flat float or current/prior dict)."""
    if isinstance(v, dict):
        return v.get("current", v.get("value"))
    return v


def _fin_number(v) -> float | None:
    v = _fin_value(v)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _fin_annual_series(fin: dict, key: str) -> list[float]:
    """The annual series ``statement_parsing.fetch_ticker`` attached, or ``[]``.

    ``fin[key + "_series"]`` is a bare list of floats on the fetch path and a
    ``{"values": [...]}`` entry when a caller passes ``annual_series``' own
    output through ``financials=``; both are read. A series with a hole (a
    ``None`` value) is refused rather than zero-filled - the same rule
    ``_series_from_payload`` applies.
    """
    entry = (fin or {}).get(f"{key}_series")
    if isinstance(entry, dict):
        entry = entry.get("values")
    if not isinstance(entry, (list, tuple)) or not entry:
        return []
    vals = [_fin_number(v) for v in entry]
    if any(v is None for v in vals):
        return []
    return [float(v) for v in vals]


def _fin_fcf_series(fin: dict) -> list[float]:
    """The annual FCF series the panel's financials already carry, oldest first.

    ``fcf_series`` when the SEC XBRL path attached it, else operating cashflow
    minus |capex| per year when both series are present, else the single latest
    annual run rate - a one-point series ``compute_dcf`` accepts and the
    mid-cycle normaliser refuses for want of three points. Never manufactured: a
    year with a missing leg is not filled.
    """
    direct = _fin_annual_series(fin, "fcf")
    if direct:
        return direct
    ocf = _fin_annual_series(fin, "operating_cashflow")
    capex = _fin_annual_series(fin, "capex")
    if ocf and capex and len(ocf) == len(capex):
        return [o - abs(c) for o, c in zip(ocf, capex, strict=True)]
    o = _fin_number((fin or {}).get("operating_cashflow"))
    c = _fin_number((fin or {}).get("capex"))
    if o is not None and c is not None:
        return [o - abs(c)]
    return []


def _derive_dcf_upside(
    fin: dict,
    *,
    rf: float = DCF_FALLBACK_RF,
    erp: float = DCF_FALLBACK_ERP,
    growth: float = DCF_FALLBACK_GROWTH,
    years: int = DCF_FALLBACK_YEARS,
    g: float = DCF_FALLBACK_GROWTH,
) -> dict:
    """One name's DCF upside from the canonical financials the panel holds.

    ``upside`` is the FV-basis margin of safety ``(fair value - price) / fair
    value`` - the quantity ``normalized.margin_of_safety`` and
    ``get_normalized_cycle_dcf`` print, and the one the schema's ``+1``
    direction means. Two of the repo's own producers are tried, in this order:

    1. ``dcf.compute_dcf`` over the annual FCF series (the run-rate DCF), when
       the latest annual FCF is positive;
    2. ``cycle_dcf.perpetuity_value`` over ``normalized_cycle_fcf`` (the
       mid-cycle DCF for cyclical reporters), which needs >= 3 annual periods;
       the per-share fair value is ``pv / shares`` with no EV -> equity bridge,
       the same convention ``get_normalized_cycle_dcf`` uses for this producer.

    ``price`` is ``market_cap / shares`` - the derivation ``_dcf_context`` uses,
    and the one that keeps the ratio independent of the share basis.

    Returns ``{"upside", "route", "fair_value", "price", "terminal_share",
    "confidence", "fcf_series", "beta", "beta_assumed", "reason", "basis"}``.
    ``upside`` is ``None`` **with a reason** when the panel's financials cannot
    support a DCF - never 0, never a proxy.
    """
    from .cycle_dcf import normalized_cycle_fcf, perpetuity_value
    from .dcf import compute_dcf

    fin = fin or {}
    fcf = _fin_fcf_series(fin)
    shares = _fin_number(fin.get("shares"))
    market_cap = _fin_number(fin.get("market_cap"))
    cash = _fin_number(fin.get("cash"))
    debt = _fin_number(fin.get("total_debt"))
    beta = _fin_number(fin.get("beta"))
    beta_assumed = beta is None
    beta_used = 1.0 if beta_assumed else float(beta)
    price = (market_cap / shares) if (market_cap and shares) else None

    out: dict = {
        "upside": None,
        "route": None,
        "fair_value": None,
        "price": price,
        "terminal_share": None,
        "confidence": None,
        "fcf_series": fcf,
        "beta": beta,
        "beta_assumed": beta_assumed,
        "reason": None,
        "basis": "",
    }

    def _refuse(reason: str) -> dict:
        out["reason"] = reason
        out["basis"] = f"dcf upside: unavailable ({reason})"
        return out

    if not fcf:
        return _refuse(
            "the panel's financials carry no free-cash-flow series (no "
            "fcf_series, and not both of operating_cashflow_series/capex_series)"
        )
    if price is None or not shares:
        return _refuse(
            "no shares and market cap to price a fair value "
            f"(shares={shares}, market_cap={market_cap})"
        )

    res = None
    if float(fcf[-1]) > 0:
        res = compute_dcf(
            fcf,
            rf=float(rf),
            beta=beta_used,
            erp=float(erp),
            growth=float(growth),
            years=int(years),
            shares=float(shares),
            cash=float(cash or 0.0),
            debt=float(debt or 0.0),
        )
    if res is not None:
        route = "dcf.compute_dcf"
        fair = float(res["price"])
        terminal_share = res.get("terminal_share")
    else:
        cyc = normalized_cycle_fcf(fcf)
        if cyc.get("median") is None:
            return _refuse(
                "no usable run-rate DCF (latest annual FCF "
                f"{float(fcf[-1]):.4g}) and the mid-cycle normaliser needs >= 3 "
                f"annual periods (have {cyc.get('n')})"
            )
        wacc = float(rf) + beta_used * float(erp)
        pv = perpetuity_value(cyc["median"], wacc, float(g))
        if pv is None:
            return _refuse(
                f"no usable DCF: wacc {wacc:.4g} <= perpetual growth {float(g):.4g}"
            )
        route = "cycle_dcf.perpetuity_value"
        fair = float(pv) / float(shares)
        terminal_share = None

    if fair is None or not math.isfinite(fair) or fair <= 0:
        return _refuse(f"{route} produced no positive fair value")

    upside = (fair - price) / fair
    confidence = dcf_confidence(
        basis=None,
        beta=beta,
        beta_assumed=beta_assumed,
        beta_range=None,
        fcf_series=fcf,
        terminal_share=terminal_share,
    )
    out.update(
        {
            "upside": upside,
            "route": route,
            "fair_value": fair,
            "terminal_share": terminal_share,
            "confidence": confidence,
            "basis": (
                f"dcf upside: engine-derived ({route}); fair value {fair:.4g} vs "
                f"price {price:.4g} -> FV-basis margin of safety {upside:.4g}; "
                f"rf {float(rf):g}"
                + (
                    " (assumed, no macro read on the panel path)"
                    if float(rf) == DCF_FALLBACK_RF
                    else ""
                )
                + f", erp {float(erp):g}, beta {beta_used:g}"
                + (" (assumed)" if beta_assumed else " (provider)")
            ),
        }
    )
    return out


def _engine_dcf_upside(
    ticker: str,
    panel: dict,
    financials: dict,
    *,
    rf: float = DCF_FALLBACK_RF,
    erp: float = DCF_FALLBACK_ERP,
    growth: float = DCF_FALLBACK_GROWTH,
    years: int = DCF_FALLBACK_YEARS,
    g: float = DCF_FALLBACK_GROWTH,
) -> tuple[dict, dict, dict]:
    """The engine-derived route over the whole panel (FUND-21 / defect D-4).

    Derives the DCF factor for EVERY name whose canonical financials the
    resolver returned, not just the analysed ticker: a single name's upside
    cannot be z-scored against peers who have none (``factors.category_scores``
    drops a metric present for one of ten names), so a leaf alone could never
    light this factor up. The value entering the panel is ``upside x
    dcf_confidence`` - the §3.4 scaling, unchanged.

    Returns ``(panel, own, summary)``: the panel with the derived factor added
    to each supported name, the analysed ticker's ``dcf_upside_scaled``-shaped
    record (``route``/``reason`` filled), and the printed summary of what each
    route supplied and why the rest were refused.
    """
    routes: dict[str, int] = {}
    reasons: dict[str, int] = {}
    derived: dict[str, float] = {}
    own: dict | None = None

    for name in sorted(panel):
        fin = financials.get(name)
        if not isinstance(fin, dict):
            why = "no canonical financials on the resolver result"
            reasons[why] = reasons.get(why, 0) + 1
            if name == ticker:
                own = {
                    "raw": None,
                    "confidence": None,
                    "effective": None,
                    "route": None,
                    "reason": why,
                    "basis": f"dcf upside: unavailable ({why})",
                }
            continue
        d = _derive_dcf_upside(fin, rf=rf, erp=erp, growth=growth, years=years, g=g)
        if d["upside"] is None:
            why = str(d["reason"] or "unavailable")
            reasons[why] = reasons.get(why, 0) + 1
            if name == ticker:
                own = {
                    "raw": None,
                    "confidence": None,
                    "effective": None,
                    "route": None,
                    "reason": why,
                    "basis": f"dcf upside: unavailable ({why})",
                }
            continue
        scaled = dcf_upside_scaled(d["upside"], (d["confidence"] or {}).get("confidence"))
        if scaled["effective"] is None:
            why = "the DCF confidence could not be measured"
            reasons[why] = reasons.get(why, 0) + 1
            if name == ticker:
                own = {**scaled, "route": d["route"], "reason": why}
            continue
        derived[name] = scaled["effective"]
        routes[str(d["route"])] = routes.get(str(d["route"]), 0) + 1
        if name == ticker:
            own = {
                **scaled,
                "route": d["route"],
                "reason": None,
                "fair_value": d["fair_value"],
                "price": d["price"],
            }

    if own is None:
        why = "the analysed ticker is not in the resolved panel"
        own = {
            "raw": None,
            "confidence": None,
            "effective": None,
            "route": None,
            "reason": why,
            "basis": f"dcf upside: unavailable ({why})",
        }

    if derived:
        panel = {
            name: ({**row, "dcf_upside": derived[name]} if name in derived else row)
            for name, row in panel.items()
        }

    route_txt = ", ".join(f"{k}={v}" for k, v in sorted(routes.items())) or "none"
    reason_txt = ", ".join(f"{k} ({v})" for k, v in sorted(reasons.items())) or "none"
    summary = {
        "route": "engine-derived",
        "panel_n": len(derived),
        "panel_of": len(panel),
        "routes": routes,
        "reasons": reasons,
        "basis": (
            f"dcf upside (engine-derived, FUND-21): {len(derived)} of {len(panel)} "
            f"panel name(s) supplied by {route_txt}; refused: {reason_txt}; scaled "
            f"by dcf_confidence per §3.4"
        ),
    }
    return panel, own, summary


def fundamental_score_for_ticker(
    ticker: str,
    current_date: str | None = None,
    *,
    peers=None,
    min_peers: int = 8,
    min_coverage=3,
    composite_min_coverage=COMPOSITE_MIN_COVERAGE,
    resolver=None,
    dcf_upside=None,
    dcf_confidence_value=None,
    **kw,
) -> dict:
    """Resolve the peer panel for ``ticker`` and score it - the leaf's one call.

    The panel comes from the one peer-panel producer
    (``peer_universe.resolve_peer_universe``, with the score-metric extension
    on): the ticker plus its resolved peers, which is the same universe
    ``get_composite_rank`` scores. ``resolver`` is injectable so the engine can be
    tested without a vendor call.

    ``dcf_upside`` is the raw DCF upside and ``dcf_confidence_value`` its 0-1
    confidence from ``dcf_confidence``; when both are given the VS sub-score
    consumes the **scaled** value (§3.4), so a DCF nobody could verify
    contributes less with no prose involved. That route is first and unchanged.

    When ``dcf_upside`` is not given, the engine derives the factor itself for
    **every** panel name whose canonical financials the resolver returned
    (``_engine_dcf_upside``: ``dcf.compute_dcf``, else
    ``cycle_dcf.perpetuity_value`` over ``normalized_cycle_fcf``; confidence from
    ``dcf_confidence``). One name's upside cannot be z-scored against peers who
    have none, so deriving the whole panel is what actually lights the factor up.
    A name the financials cannot support is left without it, with the reason
    recorded in ``dcf_upside_panel`` - never a 0 and never a proxy.

    Returns the ``fundamental_score`` dict plus ``ticker``, ``panel_basis``,
    ``panel_n``, ``dcf_upside`` (the analysed ticker's own record, carrying the
    ``route`` that supplied it and a ``reason`` when it could not be) and
    ``dcf_upside_panel`` (the per-route summary over the panel).
    """
    from datetime import datetime

    key = str(ticker or "").strip().upper()
    if not key:
        raise ValueError("get_fundamental_score requires a ticker")
    if resolver is None:
        from .peer_universe import resolve_peer_universe as resolver  # type: ignore[no-redef]

    date = current_date or datetime.now().strftime("%Y-%m-%d")
    if peers is None:
        from .peer_universe import resolved_peer_names

        names = resolved_peer_names(key)
    else:
        names = [key] + [str(p).strip().upper() for p in peers if str(p).strip()]
        names = list(dict.fromkeys(names))
    panel_res = resolver(
        tickers=names, current_date=date, include_score_metrics=True
    )
    panel = {str(k).upper(): dict(v) for k, v in (panel_res.get("metrics") or {}).items()}
    financials = {
        str(k).upper(): v
        for k, v in (panel_res.get("financials") or {}).items()
        if isinstance(v, dict)
    }

    if dcf_upside is not None:
        # Route 1 - the caller's own DCF, unchanged.
        scaled = dcf_upside_scaled(dcf_upside, dcf_confidence_value)
        scaled["route"] = "caller-supplied"
        scaled["reason"] = (
            None
            if scaled["effective"] is not None
            else "no dcf_confidence_value to scale the caller's upside by"
        )
        injected = scaled["effective"] is not None and key in panel
        if injected:
            panel[key] = {**panel[key], "dcf_upside": scaled["effective"]}
        dcf_panel = {
            "route": "caller-supplied",
            "panel_n": 1 if injected else 0,
            "panel_of": len(panel),
            "routes": {"caller-supplied": 1} if injected else {},
            "reasons": {} if injected else {str(scaled["reason"]): 1},
            "basis": (
                "dcf upside (caller-supplied): raw "
                f"{scaled['raw']} x confidence {scaled['confidence']} = "
                f"{scaled['effective']} on {key}"
                + ("" if injected else f"; NOT injected ({scaled['reason']})")
            ),
        }
    else:
        # Route 2 - the engine derives it for the whole panel (FUND-21).
        panel, scaled, dcf_panel = _engine_dcf_upside(key, panel, financials)

    res = fundamental_score(
        panel,
        min_coverage=composite_min_coverage,
        subscore_min_coverage=min_coverage,
        min_peers=min_peers,
        **kw,
    )
    res["ticker"] = key
    res["panel_basis"] = panel_res.get("basis")
    res["panel_n"] = len(panel)
    res["panel_names"] = sorted(panel)
    res["dcf_upside"] = scaled
    res["dcf_upside_panel"] = dcf_panel
    res["basis"] = f"{res['basis']} | {dcf_panel['basis']}"
    return res


def factor_gap_report() -> dict:
    """``{sub-score: {"present": [...], "NA": [...]}}`` - the printed schema gap.

    The design's rule is that an unavailable factor is recorded rather than
    proxied, so the report is part of the engine's output: it names exactly which
    of each sub-score's factors has no supplier on the panel path.
    """
    return {sub: availability_report(SUBSCORE_FACTORS[sub]) for sub in SUBSCORE_FACTORS}


__all__ = [
    "FQS_BANDS",
    "FGS_BANDS",
    "VS_BANDS",
    "FRS_BANDS",
    "SUBSCORE_BANDS",
    "SUBSCORE_FUNCS",
    "STATUS_ADVISORY",
    "STATUS_RESEARCH_ONLY",
    "COMPOSITE_MIN_COVERAGE",
    "INCOMPLETE_CAP",
    "DCF_THRESHOLDS",
    "quality_subscore",
    "growth_subscore",
    "valuation_subscore",
    "risk_subscore",
    "subscores",
    "fundamental_score",
    "fundamental_score_for_ticker",
    "dcf_confidence",
    "dcf_upside_scaled",
    "factor_gap_report",
    "directions_for",
]
