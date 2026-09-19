"""`RiskScore` - the 0-100 risk composite, INVERTED (100 = low risk).

Implements `docs/scores/RiskScore.md` §5 (the composite over the owner's eight
categories) and `docs/scores/IMPLEMENTATION_PLAN.md` §5.4. The engine's question
is *"how much can this hurt?"* - the owner's eight staged weights, in one
direction.

Six rules this module exists to hold:

1. **One pure function over existing inputs.** It takes a flat
   ``{component: raw value}`` dict - every value is produced elsewhere, by the
   producer its row names. No fetch, no formula, no vendor call, no ticker.
2. **The three pinned conventions are aligned HERE, visibly** (§0.3, §5.4):
   tail loss as a **positive loss fraction of book equity** (``book_risk.cvar:18``
   is negative, ``book_risk.stress_loss:123`` is positive - both align the same
   way), drawdown as a **positive magnitude** (so the engine reads
   ``book_context.measured_book_drawdown:102`` and never
   ``regime_state.regime_drawdown:146``, whose sign is the opposite), and
   correlation as the **largest-cluster share of book** - an explicitly labelled
   *proxy*, never a correlation coefficient. The alignment is done in the score
   and never by changing a producer, which would break that producer's other
   readers. Every component row prints its raw value with units and sign beside
   its aligned contribution.
3. **`NA` is not `0`** (master rule 1). An absent component leaves the
   denominator, the category reports its coverage, and the composite reports a
   raised **uncertainty** (``1 - coverage``). Nothing is ever substituted with a
   neutral 50 or a punitive 0; a count floor is capped at the component set's own
   size (the WP-2 FGS lesson).
4. **No fabricated coefficients** (master rule 6). The owner's eight category
   weights are published in `RiskScore.md` §1 and are used verbatim; **no
   sub-factor weight vector is published anywhere**, so each category runs
   equal-weight over its scored components and prints that fact.
5. **The semivariance leg is `sqrt(RS-)` in return units, and the identity is
   checked.** The raw sums ``RS-``, ``RS+``, ``RV`` are printed beside it, and a
   triple that does not satisfy ``RS- + RS+ = RV`` exactly (the producer's own
   decomposition contract, `volatility_models.semivariance`) **fails** rather
   than scoring a number whose basis is broken.
6. **Nothing here sizes anything, gates anything, or reaches `SCORE_BANDS`.** The
   module never imports the sizing path, `risk_governor`, `GATE_PRECEDENCE` or
   `decision_guardrail`; its bands are its own advisory labels and the score is a
   diagnostic, never a reason to buy (§5.4).

Every ramp edge and every band score is a **hypothesis** - the producer's own
edges are used wherever the producer publishes one, and the rest are this
engine's declared policy, printed in the basis and measured in Phase C. The
tables live here, in one place, so that measurement has one thing to move.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from .score_engine import align, band_label, combine, coverage_floor

# --- The owner's weights (RiskScore.md §1, ../ScoreWeight/market.md) --------

CATEGORY_WEIGHTS: dict[str, float] = {
    "volatility": 15.0,
    "tail": 15.0,
    "liquidity": 10.0,
    "gap": 10.0,
    "correlation": 15.0,
    "concentration": 10.0,
    "drawdown": 15.0,
    "event": 10.0,
}

CATEGORY_ORDER: tuple[str, ...] = tuple(CATEGORY_WEIGHTS)

# --- The pinned conventions (§0.3) ------------------------------------------
#
# One convention per quantity. Where a producer's sign differs from the pinned
# one, the component declares a `pin` and the alignment happens in the score.

PIN_TAIL = "positive loss as a fraction of book equity"
PIN_DRAWDOWN = "positive magnitude"
PIN_CORRELATION = "largest-cluster share of book (a labelled proxy, never a correlation coefficient)"

#: ``pin`` values: ``identity`` (the producer already carries the pinned form),
#: ``negate`` (the producer carries a negative loss - ``book_risk.cvar``), and
#: ``abs`` (a signed magnitude whose sign is not the risk - a gap).
PIN_IDENTITY = "identity"
PIN_NEGATE = "negate"
PIN_ABS = "abs"

# --- Component kinds --------------------------------------------------------

SCORED = "scored"
PRINTED = "printed"


class Component(NamedTuple):
    """One component: its category, how it aligns, its producer, its units."""

    name: str
    category: str
    kind: str
    direction: str
    producer: str
    units: str
    pin: str = PIN_IDENTITY
    convention: str = ""
    note: str = ""


def _c(name, category, direction, producer, units, kind=SCORED,
       pin=PIN_IDENTITY, convention="", note=""):
    return Component(name, category, kind, direction, producer, units, pin,
                     convention, note)


# --- The component map ------------------------------------------------------
#
# The producer column is the `module.function:line` the row reads, exactly as
# `RiskScore.md` §1/§5.1 names it. A component is a KEY in the caller's dict;
# the score never imports a producer, so the label is the whole binding.

COMPONENTS: dict[str, Component] = {
    c.name: c
    for c in (
        # --- volatility risk (15) -----------------------------------------
        _c("realized_vol", "volatility", "lower_better",
           "regime.realized_vol:29", "annualized fraction (x sqrt 252)"),
        _c("sqrt_rs_minus", "volatility", "lower_better",
           "volatility_models.semivariance:52 (sqrt_rs_minus)",
           "return units (sqrt of squared-return units)",
           note="the raw sums RS-/RS+/RV are printed beside it; RS- + RS+ = RV must hold"),
        _c("implied_move_pct", "volatility", "lower_better",
           "options_surface.implied_move_pct:42", "fraction (1-sigma ATM-implied)",
           note="canonical when a valid surface exists (Q4)"),
        _c("iv_percentile", "volatility", "lower_better",
           "options_surface.iv_percentile:15", "percentile 0..1"),
        _c("gex_short_gamma", "volatility", "lower_better",
           "derivatives_gamma.gamma_regime:105 (short gamma)",
           "boolean (1 = short gamma, risk-increasing)"),
        # --- tail risk (15) - pinned: positive loss as a fraction of equity
        _c("cvar", "tail", "lower_better",
           "book_risk.cvar:18", "loss fraction of book equity",
           pin=PIN_NEGATE, convention=PIN_TAIL,
           note="producer returns a NEGATIVE loss; pinned to positive here"),
        _c("portfolio_cvar", "tail", "lower_better",
           "book_risk.portfolio_cvar:28", "loss fraction of book equity",
           pin=PIN_NEGATE, convention=PIN_TAIL,
           note="producer returns a NEGATIVE loss; pinned to positive here"),
        _c("stress_loss", "tail", "lower_better",
           "book_risk.stress_loss:123", "loss fraction of book equity",
           convention=PIN_TAIL,
           note="producer already returns a POSITIVE magnitude"),
        _c("es_pct", "tail", "lower_better",
           "executor tail.ESResult.value_pct (tail.py:56)",
           "fraction of book equity",
           convention=PIN_TAIL,
           note="the executor's third unit for the same idea; positive"),
        _c("extreme_quantile_es", "tail", "lower_better",
           "book_risk.extreme_quantile_var:451 (es)", "loss fraction of book equity",
           pin=PIN_NEGATE, convention=PIN_TAIL,
           note="EVT/GPD Expected Shortfall; producer returns it NEGATIVE"),
        # --- liquidity risk (10) ------------------------------------------
        _c("amihud_illiquidity", "liquidity", "lower_better",
           "liquidity_risk.amihud_illiquidity:71",
           "ILLIQ (mean |return| per dollar volume)"),
        _c("days_to_absorb", "liquidity", "lower_better",
           "liquidity_risk.days_to_absorb:103",
           "days at the 15% participation cap"),
        _c("spread_pct", "liquidity", "lower_better",
           "liquidity_risk.spread_estimate:442", "fraction of price"),
        _c("kyle_lambda", "liquidity", "lower_better",
           "liquidity_risk.kyle_lambda:262",
           "price change per unit signed volume", kind=PRINTED,
           note="the producer's own docstring: a relative/cross-sectional read, "
                "never an absolute market quote - so no absolute ramp exists"),
        _c("liquidity_verdict", "liquidity", "lower_better",
           "liquidity_risk.liquidity_verdict:153",
           "ordinal label (liquid | caution | illiquid)", kind=PRINTED,
           note="the governor consumes the label; it is printed beside, not scored"),
        # --- gap risk (10) -------------------------------------------------
        _c("gap_pct", "gap", "lower_better",
           "market_session.gap_type:137 (gap_pct)", "fraction (signed; magnitude pinned)",
           pin=PIN_ABS, note="a gap is a magnitude risk; the sign is not the risk"),
        _c("gap_atr", "gap", "lower_better",
           "pre_market.premarket_gap:40 (gap_atr)", "ATR units",
           pin=PIN_ABS),
        _c("through_stop", "gap", "lower_better",
           "pre_market.premarket_gap:40 (through_stop)",
           "boolean (1 = the gap trades through the stop)"),
        _c("premarket_rvol", "gap", "lower_better",
           "preopen.premarket_rvol:65", "ratio vs the 30d average"),
        # --- correlation risk (15) - pinned: largest-cluster share (proxy) -
        _c("cluster_exposure_share", "correlation", "lower_better",
           "executor gate._correlation_stress:369 (cluster_notional / portfolio_exposure)",
           "share of book 0..1", convention=PIN_CORRELATION,
           note="the pinned PROXY (Q1): not a correlation coefficient and never "
                "printed as one"),
        _c("book_correlated_stress", "correlation", "lower_better",
           "book_risk.book_correlated_stress:128", "loss fraction of book equity",
           note="producer already returns a POSITIVE magnitude"),
        # --- concentration risk (10) --------------------------------------
        _c("portfolio_hhi", "concentration", "lower_better",
           "liquidity_risk.ownership_hhi:130 (the HHI formula, over POSITION weights)",
           "HHI over position weights (sum w^2, 0..1)",
           note="portfolio concentration, NOT holder concentration"),
        _c("top_position_share", "concentration", "lower_better",
           "risk_governor.default_limits:20 (max_position_pct 0.30)",
           "fraction of book"),
        _c("sector_max_share", "concentration", "lower_better",
           "portfolio_optimizer.enforce_sector_exposure:169", "fraction of book"),
        # --- portfolio drawdown (15) - pinned: positive magnitude ----------
        _c("measured_book_drawdown", "drawdown", "lower_better",
           "book_context.measured_book_drawdown:102", "positive fraction 0..1",
           convention=PIN_DRAWDOWN,
           note="THE single resolver; regime_state.regime_drawdown:146 is the "
                "opposite sign and is deliberately not read"),
        _c("cdar", "drawdown", "lower_better",
           "book_risk.cdar:174 (cdar)", "positive fraction 0..1",
           convention=PIN_DRAWDOWN),
        _c("kill_switch_rung", "drawdown", "lower_better",
           "risk_hierarchy.kill_switch_state:81 / risk/ladder.rung_for:82",
           "rung 0..4"),
        # --- event risk (10) - EXPOSURE, not occurrence (§5.7 boundary) ----
        _c("catalyst_scale", "event", "higher_better",
           "catalyst.build_catalyst_snapshot:219 (scale)",
           "multiplier [0.25, 1.0] (1.0 = no imminent catalyst)",
           note="EXPOSURE: how dangerous the event is for this position, "
                "never EventScore's occurrence/imminence question"),
        _c("catalyst_risk_penalty", "event", "higher_better",
           "events.catalyst_risk_penalty:53", "multiplier <= 1 (1.0 = no penalty)",
           note="EXPOSURE"),
        _c("event_hard_block", "event", "lower_better",
           "catalyst.build_catalyst_snapshot:219 (hard_block)", "boolean",
           note="the producer's block is authoritative and is NOT set by this "
                "score; it is read here as exposure only"),
        _c("opex_window", "event", "lower_better",
           "derivatives_gamma.opex_status:127 (in_opex_week)", "boolean"),
        _c("position_mult_by_side", "event", "higher_better",
           "events.position_mult_by_side:34", "multiplier 0..1.5", kind=PRINTED,
           note="a SIZE, printed beside the score and never scored by it "
                "(score != scale)"),
    )
}

CATEGORY_COMPONENTS: dict[str, tuple[str, ...]] = {
    cat: tuple(c.name for c in COMPONENTS.values() if c.category == cat)
    for cat in CATEGORY_ORDER
}

# --- The alignment tables ---------------------------------------------------
#
# Walked top-down by ``score_engine.align`` (first edge the value clears wins),
# so every table is written from the HIGH end of the pinned value downward.
# Bands are for the booleans and the labelled states; ramps for the continuous
# measures. Every edge is a hypothesis unless the producer publishes one.

BANDS: dict[str, tuple] = {
    # A short-gamma book is the risk-increasing dealer state.
    "gex_short_gamma": ((1.0, 20.0), (0.0, 70.0)),
    # The gap traded through the stop: the strongest reject the producer emits.
    "through_stop": ((1.0, 15.0), (0.0, 75.0)),
    # The producer's own earnings blackout; read as exposure, never set here.
    "event_hard_block": ((1.0, 5.0), (0.0, 85.0)),
    "opex_window": ((1.0, 25.0), (0.0, 75.0)),
}

RAMPS: dict[str, tuple[float, float]] = {
    # volatility
    "realized_vol": (0.10, 0.60),
    "sqrt_rs_minus": (0.008, 0.030),
    "implied_move_pct": (0.01, 0.10),
    "iv_percentile": (0.10, 0.90),
    # tail (pinned positive loss fraction of book equity)
    "cvar": (0.0, 0.10),
    "portfolio_cvar": (0.0, 0.10),
    "stress_loss": (0.0, 0.10),
    "es_pct": (0.0, 0.10),
    "extreme_quantile_es": (0.0, 0.15),
    # liquidity
    "amihud_illiquidity": (1e-9, 1e-6),
    "days_to_absorb": (0.0, 30.0),
    "spread_pct": (0.0005, 0.02),
    # gap
    "gap_pct": (0.0, 0.05),
    "gap_atr": (0.0, 3.0),
    "premarket_rvol": (1.0, 5.0),
    # correlation
    "cluster_exposure_share": (0.10, 0.50),
    "book_correlated_stress": (0.0, 0.10),
    # concentration
    "portfolio_hhi": (0.05, 0.50),
    "top_position_share": (0.05, 0.30),
    "sector_max_share": (0.15, 0.45),
    # drawdown (pinned positive magnitude)
    "measured_book_drawdown": (0.0, 0.30),
    "cdar": (0.0, 0.25),
    "kill_switch_rung": (0.0, 4.0),
    # event (exposure)
    "catalyst_scale": (0.25, 1.0),
    "catalyst_risk_penalty": (0.5, 1.0),
}

# This engine's own advisory labels - never `decision_guardrail.SCORE_BANDS`,
# whose labels are ratings (Buy/Hold/Sell). These are risk levels.
RISK_BANDS: tuple = (
    (80.0, "low risk"),
    (65.0, "contained"),
    (50.0, "moderate"),
    (35.0, "elevated"),
    (20.0, "high"),
    (0.0, "severe"),
)

STATUS_ADVISORY = "ADVISORY"

# A category floor of 2 of its own components, capped at the category's own
# scored count (a two-component category must not be withheld forever).
CATEGORY_MIN_COVERAGE = 2
COMPOSITE_MIN_COVERAGE = 3

# --- The semivariance leg (§0.3, acceptance (g)) ----------------------------

#: The decomposition triple the producer's contract is stated over.
SEMIVARIANCE_KEYS: tuple[str, ...] = ("rs_minus", "rs_plus", "rv")

#: ``RS- + RS+ = RV`` is exact in the producer's arithmetic; the tolerance only
#: absorbs the float summation order, never a real disagreement.
SEMIVARIANCE_TOL = 1e-12


def semivariance_leg(values: dict) -> dict:
    """Validate ``RS- + RS+ = RV`` and return the leg the score consumes.

    The pinned unit is ``sqrt(RS-)`` in **return units** (comparable to
    ``regime.realized_vol:29``); the raw squared-return sums are returned
    beside it so the row can print them. A supplied ``sqrt_rs_minus`` must equal
    ``sqrt(RS-)``; a triple that does not satisfy the identity **raises** -
    a score built on a broken decomposition is not a number, it is a defect.
    All four keys absent is not an error: the leg is simply absent (``None``),
    never 0.
    """
    vals = dict(values or {})
    supplied = {k: vals.get(k) for k in SEMIVARIANCE_KEYS}
    sqrt_supplied = vals.get("sqrt_rs_minus")
    if all(v is None for v in supplied.values()) and sqrt_supplied is None:
        return {
            "rs_minus": None, "rs_plus": None, "rv": None,
            "sqrt_rs_minus": None, "identity": None,
            "basis": "semivariance absent (no rs_minus/rs_plus/rv supplied)",
        }
    missing = [k for k, v in supplied.items() if v is None]
    if missing:
        raise ValueError(
            "semivariance identity cannot be checked: missing "
            + ", ".join(missing)
            + " (the producer's contract is RS- + RS+ = RV; supply all three, "
            "or none)"
        )
    try:
        rm, rp, rv = (float(supplied[k]) for k in SEMIVARIANCE_KEYS)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"semivariance inputs are not numeric: {exc}") from exc
    if not all(math.isfinite(x) for x in (rm, rp, rv)):
        raise ValueError(f"semivariance inputs are not finite: {rm!r}, {rp!r}, {rv!r}")
    if rm < 0 or rp < 0:
        raise ValueError(
            f"semivariance legs are squared-return sums and cannot be negative: "
            f"RS-={rm!r}, RS+={rp!r}"
        )
    if abs((rm + rp) - rv) > SEMIVARIANCE_TOL + 1e-9 * abs(rv):
        raise ValueError(
            f"semivariance identity violated: RS- + RS+ = {rm + rp!r} != RV = {rv!r} "
            "(the producer's full-sample decomposition is RS- + RS+ = RV exactly)"
        )
    derived = math.sqrt(rm)
    if sqrt_supplied is None:
        sq = derived
    else:
        sq = float(sqrt_supplied)
        if abs(sq - derived) > 1e-12 + 1e-9 * derived:
            raise ValueError(
                f"sqrt_rs_minus = {sq!r} does not equal sqrt(RS-) = {derived!r}"
            )
    return {
        "rs_minus": rm,
        "rs_plus": rp,
        "rv": rv,
        "sqrt_rs_minus": sq,
        "identity": f"RS- + RS+ = RV exactly ({rm:.6g} + {rp:.6g} = {rv:.6g})",
        "basis": (
            f"semivariance leg: sqrt(RS-) = {sq:.6g} in return units; "
            f"raw sums RS-={rm:.6g}, RS+={rp:.6g}, RV={rv:.6g} printed beside it"
        ),
    }


def _coerce(value, component: Component):
    """Booleans become 1.0/0.0 (a boolean is a measurement, not a gap)."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return value


def _pin(value, component: Component):
    """The raw producer value in the component's PINNED convention."""
    if value is None:
        return None
    if isinstance(value, str):
        return value  # a label is printed, never aligned
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    if component.pin == PIN_NEGATE:
        return -v
    if component.pin == PIN_ABS:
        return abs(v)
    return v


def _align_one(name: str, component: Component, pinned):
    """Map a pinned value to its 0-100 favourable contribution, or None."""
    if component.kind == PRINTED or pinned is None or isinstance(pinned, str):
        return None
    if name in BANDS:
        return align(pinned, direction=component.direction, band=BANDS[name])
    if name in RAMPS:
        lo, hi = RAMPS[name]
        return align(pinned, direction=component.direction, lo=lo, hi=hi)
    # a declared scored component with no mapping is a defect, not a 50
    raise KeyError(f"component {name!r} has neither a band nor a ramp")


def align_components(values: dict) -> dict[str, dict]:
    """``{component: raw}`` -> ``{component: row}``, conventions pinned visibly.

    Each row carries the **raw** producer value, the **pinned** value in the
    engine's own convention, the **units**, the **sign** rule applied, the
    producer, and the aligned 0-100 contribution. An absent or unusable value is
    ``None`` and leaves the denominator - never 0, never a neutral 50. An
    unknown key is ignored (the engine scores what it declares).
    """
    vals = dict(values or {})
    leg = semivariance_leg(vals)
    out: dict[str, dict] = {}
    for name, comp in COMPONENTS.items():
        if name == "sqrt_rs_minus":
            raw = leg["sqrt_rs_minus"]
            pinned = raw
        else:
            raw = _coerce(vals.get(name), comp)
            pinned = _pin(raw, comp)
        row = {
            "raw": raw,
            "pinned": pinned,
            "units": comp.units,
            "pin": comp.pin,
            "direction": comp.direction,
            "category": comp.category,
            "producer": comp.producer,
            "kind": comp.kind,
            "convention": comp.convention,
            "aligned": _align_one(name, comp, pinned),
        }
        if name == "sqrt_rs_minus":
            row["rs_minus"] = leg["rs_minus"]
            row["rs_plus"] = leg["rs_plus"]
            row["rv"] = leg["rv"]
            row["identity"] = leg["identity"]
            row["note"] = comp.note
        out[name] = row
    return out


def category_score(category: str, aligned_rows: dict,
                   *, min_coverage=CATEGORY_MIN_COVERAGE) -> dict:
    """One category's 0-100 over its own SCORED components, or withheld.

    The printed-only components (the liquidity verdict, ``kyle_lambda``, the
    event size multiplier) are reported beside the score and never enter its
    denominator. Equal weights within the category: no sub-factor vector is
    published, and the basis says so.
    """
    if category not in CATEGORY_COMPONENTS:
        raise KeyError(f"unknown category {category!r}; known: {list(CATEGORY_ORDER)}")
    names = CATEGORY_COMPONENTS[category]
    scored = [n for n in names if COMPONENTS[n].kind == SCORED]
    printed = [n for n in names if COMPONENTS[n].kind == PRINTED]
    comps = {n: (aligned_rows.get(n) or {}).get("aligned") for n in scored}
    floor = min(coverage_floor(min_coverage, len(scored)), len(scored))
    res = combine(comps, min_coverage=floor)
    res["category"] = category
    res["weight"] = CATEGORY_WEIGHTS[category]
    res["band"] = band_label(res.get("score"), RISK_BANDS)
    res["printed"] = {n: (aligned_rows.get(n) or {}).get("raw") for n in printed}
    res["component_weights"] = "equal (no sub-factor vector is published)"
    return res


def risk_score(
    components: dict,
    *,
    weights: dict | None = None,
    min_coverage=COMPOSITE_MIN_COVERAGE,
    category_min_coverage=CATEGORY_MIN_COVERAGE,
) -> dict:
    """The eight category sub-scores and their weighted composite (100 = low risk).

    ``components`` is ``{component: raw value}`` over the components declared in
    ``COMPONENTS``, plus the semivariance triple (``rs_minus``/``rs_plus``/``rv``)
    when the volatility leg is measured. Anything absent is ``NA`` and is
    reported, never scored as 0 or 50.

    ``weights`` overrides the owner's category weights; ``None`` uses them and
    the basis prints which vector was used. The composite renormalises over the
    categories that produced a score, so an unmeasured category **raises the
    reported uncertainty** (``1 - coverage``) instead of moving the score.

    Returns ``{"score", "coverage", "uncertainty", "categories", "components",
    "aligned", "contributions", "bands", "weights", "status", "withheld",
    "measured", "absent", "printed", "basis"}``.
    """
    rows = align_components(components)
    cats = {
        cat: category_score(cat, rows, min_coverage=category_min_coverage)
        for cat in CATEGORY_ORDER
    }
    w = dict(weights) if weights is not None else dict(CATEGORY_WEIGHTS)
    comps = {cat: cats[cat].get("score") for cat in CATEGORY_ORDER}
    combined = combine(comps, weights=w, min_coverage=min_coverage)

    contributions: dict[str, dict] = {}
    for cat in CATEGORY_ORDER:
        s = cats[cat].get("score")
        wc = float(w.get(cat, 0.0) or 0.0)
        contributions[cat] = {
            "weight": wc,
            "score": s,
            "contribution": (wc * s) if s is not None else None,
        }

    coverage = combined.get("coverage")
    uncertainty = round(1.0 - float(coverage or 0.0), 4)
    measured = sorted(n for n, r in rows.items() if r["aligned"] is not None)
    absent = sorted(
        n for n, r in rows.items() if r["aligned"] is None and COMPONENTS[n].kind == SCORED
    )
    printed = sorted(n for n, r in rows.items() if COMPONENTS[n].kind == PRINTED)
    basis = (
        f"RiskScore: INVERTED (100 = low risk). "
        f"{len(measured)} of {sum(1 for c in COMPONENTS.values() if c.kind == SCORED)} "
        f"scored component(s) measured -> "
        f"{sum(1 for c in cats.values() if c.get('score') is not None)} of "
        f"{len(CATEGORY_ORDER)} category sub-scores -> "
        f"{'owner' if weights is None else 'supplied'} category weights "
        f"{dict(sorted(w.items()))}; "
        f"no sub-factor weight vector is published, equal weights within each category; "
        f"pinned conventions - tail loss {PIN_TAIL}, drawdown {PIN_DRAWDOWN}, "
        f"correlation {PIN_CORRELATION}; "
        f"coverage {coverage}, uncertainty (1 - coverage) {uncertainty}; "
        f"advisory only - never a gate, never a size, never a forecast"
    )
    return {
        "score": combined.get("score"),
        "coverage": coverage,
        "floor": combined.get("floor"),
        "uncertainty": uncertainty,
        "categories": cats,
        "components": rows,
        "aligned": {n: r["aligned"] for n, r in rows.items()},
        "contributions": contributions,
        "bands": band_label(combined.get("score"), RISK_BANDS),
        "weights": w if weights is not None else None,
        "status": STATUS_ADVISORY,
        "withheld": combined.get("withheld"),
        "measured": measured,
        "absent": absent,
        "printed": printed,
        "basis": basis,
    }


def category_weight_share(weights: dict | None = None) -> dict[str, float]:
    """``{category: weight}`` actually used, so a reader can renormalise."""
    w = dict(weights) if weights is not None else dict(CATEGORY_WEIGHTS)
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


__all__ = [
    "CATEGORY_WEIGHTS",
    "CATEGORY_ORDER",
    "CATEGORY_COMPONENTS",
    "COMPONENTS",
    "Component",
    "SCORED",
    "PRINTED",
    "BANDS",
    "RAMPS",
    "RISK_BANDS",
    "STATUS_ADVISORY",
    "PIN_TAIL",
    "PIN_DRAWDOWN",
    "PIN_CORRELATION",
    "PIN_IDENTITY",
    "PIN_NEGATE",
    "PIN_ABS",
    "SEMIVARIANCE_KEYS",
    "SEMIVARIANCE_TOL",
    "CATEGORY_MIN_COVERAGE",
    "COMPOSITE_MIN_COVERAGE",
    "semivariance_leg",
    "align_components",
    "category_score",
    "risk_score",
    "category_weight_share",
]
