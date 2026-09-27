"""`MomentumScore` - the eight §54 momentum legs over already-computed producers.

Implements the owner's library `docs/scores/momentum_score.md` (2,064 lines, 54
sections) §§47-§54. The engine's question is *"how strong, how persistent and how
well-confirmed is this name's price behaviour?"* - **the stock's own momentum**,
as distinct from `TechnicalScore` (the nine-category technical read; MOM-4 kept
that table intact), `RelativeStrength` (the RS line as a standalone tool) and the
fundamental engines.

Seven rules this module exists to hold:

1. **Eight families, not fifty indicators** (§54). The engine computes the eight
   sub-scores the library names - ``P`` price, ``R`` relative, ``T`` trend
   strength, ``A`` acceleration, ``B`` breakout, ``V`` volume confirmation,
   ``Q`` quality, ``D`` risk-adjusted - each itself a 0-100 family score over
   *members*, and combines them through :func:`score_engine.combine`. §54's own
   warning is the design brief: *"Don't let all 50+ indicators vote
   independently."*
2. **The meta set stays OUTSIDE the number** (§§50-§52). `MomentumConviction`,
   `MomentumDispersion`, `MomentumDivergence`, `MomentumCoverage` and
   `MomentumRegimeCompatibility` are emitted **beside** the score, never folded
   into it: the score is one number and the meta reads say whether that number
   is coherent.
3. **`NA` is not `0`** (master rule 1). A member whose producer could not measure
   is left out of its family's denominator; a family below its floor is
   *withheld with a reason*; the composite below its floor is withheld too.
4. **Reuse the producers, never re-derive their arithmetic.** Every member names
   the existing `strategies/*` producer it reads, with the section that defines
   it. The only arithmetic this module adds is what the library names and the
   tree lacked: the §48/§49 normalization contract, the §8.1 efficiency ratio and
   the §8.3 positive-day ratio (MOM-6).
5. **The normalization contract is declared ONCE** (MOM-2, §48/§49). See
   :func:`normalize_component`: §48 (`z -> winsorize ±3σ -> 50 + 16.667z`) is the
   primary and §49 (percentile rank) is the one-line alternative. The library
   gives the transform; it is silent on the *population* the standardisation runs
   over, and both of its own forms (§19, §49) are cross-sectional. A per-name
   engine has no cross-section, so a member measured **with a supplied reference
   cross-section** is normalized by that contract, and otherwise the member is
   mapped by its own declared band/ramp through :func:`score_engine.align` - the
   kernel's declared min/max form, which is the mapping every other engine in
   this repo uses. The choice, the section and the declined alternative are
   recorded in `docs/scores/MomentumScore.md`.
6. **The composite weight vector is the library's own §47 example, and it is
   NOT owner-signed.** §47 prints *"For example: 0.25M_price + 0.20M_trend +
   0.15M_relative + 0.10M_acceleration + 0.10M_volume + 0.10M_quality +
   0.05M_breakout + 0.05M_riskadj"* - an illustrative, self-consistent vector
   summing to 1.0. §54 leaves the weights symbolic. This module therefore
   declares the library's own example as :data:`LEG_WEIGHTS`, prints the vector
   it used in ``basis``, and **flags it as pending the owner's ratification**:
   the composite is `RESEARCH_ONLY` and no value here was invented.
7. **Nothing here sizes, gates, ratings or reaches `SCORE_BANDS`.** The bands are
   the library's own descriptive §49 bands (*"descriptive score bands, not
   trading recommendations"*), never `decision_guardrail.SCORE_BANDS`.

Ownership (MOM-4, owner decision 2026-09-27): **the six momentum-relevant legs
stay inside `technical_score.CATEGORY_WEIGHTS`.** The migration this row
considered - moving `momentum` 18.0, `relative_strength` 12.0, `trend` 20.0,
`breakout` 10.0, `volume` 10.0, `volatility` 5.0 out of `TechnicalScore` - is
**declined**: MF-6 already trimmed that table to the legs that survive the
2026-09-27 panel, and re-pointing 75 of its 100 points would re-derive
`TechnicalScore` a second time. `MomentumScore` is therefore **additive**: it
reads the same underlying producers and leaves the owner's vector byte-identical.
The consequence is recorded honestly in `MomentumScore.md` §5: the two engines
overlap on the producers they read.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from .cross_section import cross_sectional_z
from .score_engine import align, combine, coverage_floor

# ---------------------------------------------------------------------------
# §54 - the eight legs and their weights
# ---------------------------------------------------------------------------

#: §54's leg symbols, in the order the library prints them.
LEG_ORDER: tuple[str, ...] = ("P", "R", "T", "A", "B", "V", "Q", "D")

#: The library's own §47 *"For example"* vector. It sums to 1.0. **Illustrative
#: in the library and not owner-signed** - see rule 6 in the module docstring.
#: Printed in every result's ``basis`` so a reader always sees the vector used.
LEG_WEIGHTS: dict[str, float] = {
    "P": 0.25,  # M_price
    "R": 0.15,  # M_relative
    "T": 0.20,  # M_trend
    "A": 0.10,  # M_acceleration
    "B": 0.05,  # M_breakout
    "V": 0.10,  # M_volume
    "Q": 0.10,  # M_quality
    "D": 0.05,  # M_riskadj
}

#: The legs' printed names (§54's own gloss).
LEG_NAMES: dict[str, str] = {
    "P": "price momentum",
    "R": "relative momentum",
    "T": "trend strength",
    "A": "acceleration",
    "B": "breakout",
    "V": "volume confirmation",
    "Q": "momentum quality",
    "D": "risk-adjusted momentum",
}

#: §49's descriptive bands, verbatim. The library says in so many words that
#: these are *"descriptive score bands, not trading recommendations"* - they are
#: this engine's own advisory labels and never a rating table.
MOMENTUM_BANDS: tuple = (
    (90.0, "extremely strong"),
    (75.0, "strong"),
    (60.0, "moderately strong"),
    (40.0, "neutral"),
    (25.0, "weak"),
    (10.0, "very weak"),
    (0.0, "extremely weak"),
)

#: The engine's status. A composite the library weights only by example, over
#: ramps that no panel has measured, is not a validated score.
STATUS_RESEARCH_ONLY = "RESEARCH_ONLY"

#: A family may be reported over as few as two of its own members; the composite
#: over three of its eight legs. Both floors are capped at the set's own size, so
#: a small family (A has three members) is never withheld forever.
LEG_MIN_COVERAGE = 2
COMPOSITE_MIN_COVERAGE = 3


class Component(NamedTuple):
    """One member: the leg it feeds, its direction, its producer, its section."""

    name: str
    leg: str
    direction: str
    producer: str
    section: str
    note: str = ""


def _c(name, leg, direction, producer, section, note=""):
    return Component(name, leg, direction, producer, section, note)


# ---------------------------------------------------------------------------
# The mapping tables: bands (non-monotonic inputs) and ramps (monotonic ones).
#
# Walked top-down by ``score_engine.align``: the first edge the raw value clears
# wins. A ramp is ``(lo, hi)`` mapped 0 -> 100 (inverted when the component is
# ``lower_better``). Every edge is a declared hypothesis; nothing measures them
# yet (that is Phase C, `MEASUREMENT_FINDINGS.md`), so the composite stays
# RESEARCH_ONLY.
# ---------------------------------------------------------------------------

BANDS: dict[str, tuple] = {
    # A boolean state is a measurement, never a gap (1.0 true / 0.0 false).
    "rs_new_high": ((1.0, 80.0), (0.0, 45.0)),
    # A divergence is a warning, not a signal (§16's example).
    "rs_divergence": ((1.0, 25.0), (0.0, 60.0)),
    "sma_stack": ((1.0, 80.0), (0.0, 30.0)),
}

RAMPS: dict[str, tuple[float, float]] = {
    # P - price momentum (§3 horizons, §2.1 12-1)
    "r_5": (-0.12, 0.12),
    "r_21": (-0.25, 0.25),
    "r_63": (-0.35, 0.35),
    "r_126": (-0.50, 0.50),
    "r_252": (-0.70, 0.70),
    "mom_12_1": (-0.30, 0.50),
    # R - relative momentum (§16)
    "rs_slope_pct": (-0.10, 0.10),
    "rs_vs_sector": (-0.15, 0.15),
    # Already 0-100 when a reference cross-section was normalized by §48/§49.
    "rs_percentile": (0.0, 100.0),
    # T - trend strength (§5, §9, §38, §39)
    "adx": (15.0, 40.0),
    "di_spread": (-30.0, 30.0),
    "ma_distance": (-0.10, 0.10),
    "ma_slope": (-0.05, 0.05),
    "trend_slope": (-0.005, 0.005),
    "trend_r2": (0.0, 0.90),
    # A - acceleration (§4.1, §4.2, §11.4)
    "accel_short_medium": (-0.20, 0.20),
    "accel_medium_long": (-0.30, 0.30),
    "macd_hist_accel": (-0.010, 0.010),
    # B - breakout (§6.1-§6.5)
    "donchian_20": (-1.0, 1.0),
    "donchian_50": (-1.0, 1.0),
    "donchian_100": (-1.0, 1.0),
    "donchian_252": (-1.0, 1.0),
    "breakout_strength": (-0.5, 2.0),
    "dist_from_high": (-0.50, 0.0),
    # V - volume confirmation (§13-§15)
    "rvol": (0.5, 2.0),
    "volume_trend": (-0.30, 0.30),
    "obv_slope_norm": (-0.30, 0.30),
    "cmf": (-0.20, 0.20),
    "pv_corr": (-0.50, 0.50),
    # Q - momentum quality (§7.1, §8.1, §8.3, §40)
    "efficiency_ratio": (0.0, 0.60),
    "positive_day_ratio": (0.35, 0.65),
    "autocorr1": (-0.20, 0.20),
    "vol_adjusted": (-1.50, 1.50),
    # D - risk-adjusted momentum, all lower-is-better (§23, §25, §26, §30)
    "realized_vol": (0.15, 0.80),
    "downside_dev": (0.05, 0.45),
    "max_drawdown": (0.0, 0.40),
    "ulcer": (0.0, 0.15),
    "atr_pct": (0.01, 0.06),
}

#: Members retired **inside** this engine, with the reason. Kept as data so a
#: reader and the tests can tell a retired member from one never declared.
RETIRED_MEMBERS: dict[str, str] = {
    # §53 lists "Trend R²" under BOTH Trend Strength (T) and Momentum Quality
    # (Q): the library double-lists one fit. Scoring it in both families would
    # make one regression vote twice in the composite (the §54 redundancy
    # warning), so it is scored ONCE, in T, and Q's copy is retired.
    "trend_r2_quality": (
        "redundant: §53 lists Trend R² under both Trend Strength and Momentum "
        "Quality - one regression fit must not vote twice (MOM-5); scored once, in T"
    ),
    # The PVT producer (`extended_indicators.vpt:248`) returns a CUMULATIVE
    # level whose scale grows with the series length, so it is not comparable
    # across names or windows and has no scale-free trend producer.
    "pvt": (
        "no scale-free producer: extended_indicators.vpt:248 returns a cumulative "
        "PVT level (scale depends on series length); V keeps the scale-free "
        "obv_slope_norm, cmf and pv_corr instead"
    ),
}

# ---------------------------------------------------------------------------
# The member map (§53's sub-items, one row per producer read)
# ---------------------------------------------------------------------------

COMPONENTS: dict[str, Component] = {
    c.name: c
    for c in (
        # --- P: price momentum (§3, §2.1) --------------------------------
        _c("r_5", "P", "higher_better", "extended_indicators.roc(closes, 5)/100", "§3"),
        _c("r_21", "P", "higher_better", "extended_indicators.roc(closes, 21)/100", "§3"),
        _c("r_63", "P", "higher_better", "extended_indicators.roc(closes, 63)/100", "§3"),
        _c("r_126", "P", "higher_better", "extended_indicators.roc(closes, 126)/100", "§3"),
        _c("r_252", "P", "higher_better", "extended_indicators.roc(closes, 252)/100", "§3"),
        _c("mom_12_1", "P", "higher_better", "momentum.momentum_12_1:358", "§2.1"),
        # --- R: relative momentum (§16, §1.4, §1.6) ----------------------
        _c("rs_slope_pct", "R", "higher_better", "relative_strength.slope_pct:49 (x100)", "§16"),
        _c("rs_new_high", "R", "higher_better", "relative_strength.rs_position:89", "§16"),
        _c(
            "rs_divergence",
            "R",
            "higher_better",
            "relative_strength.divergence:195",
            "§16",
            "1 = divergence present (bad)",
        ),
        _c(
            "rs_vs_sector",
            "R",
            "higher_better",
            "relative_strength.relative_strength_vs_sector:276",
            "§1.4/§16",
        ),
        _c(
            "rs_percentile",
            "R",
            "higher_better",
            "factors.percentile_rank:59 (via §48/§49 normalize)",
            "§1.6/§48/§49",
            "supplied 0-100 only when a reference cross-section is handed in",
        ),
        # --- T: trend strength (§5, §9, §38, §39) ------------------------
        _c("adx", "T", "higher_better", "technical_factors.adx:230", "§38"),
        _c(
            "di_spread",
            "T",
            "higher_better",
            "technical_factors.adx:230 (di_plus - di_minus)",
            "§39",
        ),
        _c(
            "ma_distance",
            "T",
            "higher_better",
            "technical_factors.sma_legs:1050 (close/sma_fast - 1)",
            "§5.1",
        ),
        _c(
            "ma_slope",
            "T",
            "higher_better",
            "technical_depth.moving_average_depth:218 (ema_slope)",
            "§5.4",
        ),
        _c("sma_stack", "T", "higher_better", "swing.trend_architecture:76 (sma_stack)", "§5.5"),
        _c(
            "trend_slope",
            "T",
            "higher_better",
            "technical_depth.regression_read:149 (slope_pct)",
            "§9.1-§9.3",
        ),
        _c("trend_r2", "T", "higher_better", "technical_depth.regression_read:149 (r2)", "§9.4"),
        # --- A: acceleration (§4.1, §4.2, §11.4) -------------------------
        _c(
            "accel_short_medium",
            "A",
            "higher_better",
            "§4.1 R_63 - R_21 (over momentum_multihorizon:418)",
            "§4.1",
        ),
        _c(
            "accel_medium_long",
            "A",
            "higher_better",
            "§4.2 R_21 - R_126 (over momentum_multihorizon:418)",
            "§4.2",
        ),
        _c(
            "macd_hist_accel",
            "A",
            "higher_better",
            "technical_factors.macd_depth:1106 (hist_accel/close)",
            "§11.4",
        ),
        # --- B: breakout (§6.1-§6.5) -------------------------------------
        _c(
            "donchian_20",
            "B",
            "higher_better",
            "technical_factors.donchian_channel:468 (n=20, up-dn persistence)",
            "§6.1",
        ),
        _c(
            "donchian_50",
            "B",
            "higher_better",
            "technical_factors.donchian_channel:468 (n=50)",
            "§6.1",
            "MOM-6: n wired",
        ),
        _c(
            "donchian_100",
            "B",
            "higher_better",
            "technical_factors.donchian_channel:468 (n=100)",
            "§6.1",
            "MOM-6: n wired",
        ),
        _c(
            "donchian_252",
            "B",
            "higher_better",
            "technical_factors.donchian_channel:468 (n=252)",
            "§6.1",
            "MOM-6: n wired",
        ),
        _c(
            "breakout_strength",
            "B",
            "higher_better",
            "technical_factors.volume_depth:1273 (breakout_strength, ATR units)",
            "§6.5/§30",
        ),
        _c("dist_from_high", "B", "higher_better", "factors.high_distance:35", "§6.2"),
        # --- V: volume confirmation (§13-§15) ----------------------------
        _c("rvol", "V", "higher_better", "momentum.rvol:25", "§13.1"),
        _c(
            "volume_trend",
            "V",
            "higher_better",
            "technical_factors.volume_depth:1273 (volume_trend)",
            "§13.2",
        ),
        _c(
            "obv_slope_norm",
            "V",
            "higher_better",
            "technical_factors.obv_divergence:542 (obv_slope_norm)",
            "§14",
        ),
        _c("cmf", "V", "higher_better", "extended_indicators.chaikin_money_flow:263", "§15"),
        _c(
            "pv_corr",
            "V",
            "higher_better",
            "factor_expressions.corr:224 (close vs volume, k=20)",
            "§13.3",
            "MOM-6: built",
        ),
        # --- Q: momentum quality (§7.1, §8.1, §8.3, §40) -----------------
        _c(
            "efficiency_ratio",
            "Q",
            "higher_better",
            "momentum_score.efficiency_ratio (this module)",
            "§8.1",
            "MOM-6: built",
        ),
        _c(
            "positive_day_ratio",
            "Q",
            "higher_better",
            "momentum_score.positive_day_ratio (this module)",
            "§8.3",
            "MOM-6: built",
        ),
        _c(
            "autocorr1",
            "Q",
            "higher_better",
            "book_risk.return_autocorrelation:355 (acf[0])",
            "§40",
        ),
        _c("vol_adjusted", "Q", "higher_better", "factors.vol_adjusted_momentum:46", "§7.1"),
        # --- D: risk-adjusted momentum (§23, §25, §26, §30) --------------
        _c("realized_vol", "D", "lower_better", "regime.realized_vol:39", "§7/§26"),
        _c("downside_dev", "D", "lower_better", "evaluate.downside_deviation:846", "§26"),
        _c("max_drawdown", "D", "lower_better", "evaluate.max_drawdown:222", "§23"),
        _c("ulcer", "D", "lower_better", "evaluate.ulcer_index:1037", "§25"),
        _c("atr_pct", "D", "lower_better", "size.atr:143 (ATR/close)", "§30"),
    )
}

LEG_COMPONENTS: dict[str, tuple[str, ...]] = {
    leg: tuple(c.name for c in COMPONENTS.values() if c.leg == leg) for leg in LEG_ORDER
}

#: §53's sub-items this engine does NOT score, each with its reason (MOM-6).
DECLINED_SUB_ITEMS: dict[str, str] = {
    "industry_relative": (
        "MOM-6: no dedicated industry-relative momentum producer exists. "
        "`cross_section.industry_neutral_z:111` demeans a cross-section by a "
        "caller-supplied group and is not wired to any RS read, and the repo has "
        "no per-name industry return series to difference against; the sector leg "
        "(`relative_strength_vs_sector`) is the closest real reference and is "
        "already the R family's member"
    ),
    "regime_compatibility": (
        "MOM-3: `MomentumRegimeCompatibility` has no producer anywhere in the repo "
        "and the library states no formula for it (§54 names it; §43 states only "
        "that momentum 'should behave differently' per regime). Building one would "
        "mean inventing a regime->compatibility mapping and a rating semantic - a "
        "decision for the owner, not a default (the EVT-1 lesson)"
    ),
}

# ---------------------------------------------------------------------------
# MOM-2: the one normalization contract (§48 primary, §49 the alternative)
# ---------------------------------------------------------------------------

#: The declared method. §48 is the library's base rule; §49 is introduced as
#: *"An alternative"*, so §48 is the default.
NORMALIZATION_METHOD = "z"
PERCENTILE_METHOD = "percentile"

#: §48's constants, each in ONE named place so §49 is a one-line change.
#: ``50 + 16.667*z*`` with ``z* = clip(z, -3, 3)`` maps z=-3 -> 0, z=0 -> 50,
#: z=+3 -> 100 (the library's own worked endpoints in §19).
Z_CENTER = 50.0
Z_SCALE = 16.667
Z_WINSOR_LIMIT = 3.0

#: §48's `Z_i = (x_i - μ_i)/σ_i`. Reused from the repo's one cross-sectional
#: standardiser; the ±3σ clip and the affine map are the part that did not exist.
NORMALIZATION_SOURCE = "cross_section.cross_sectional_z:70 + §48 clip/map"


def normalize_component(
    values,
    *,
    method: str = NORMALIZATION_METHOD,
    center: float = Z_CENTER,
    scale: float = Z_SCALE,
    winsor: float = Z_WINSOR_LIMIT,
) -> list[float | None]:
    """The engine's ONE normalization contract (§48; §49 its one-line alternative).

    §48 - the primary::

        Z_i   = (x_i - mu_i) / sigma_i          # cross_section.cross_sectional_z
        Z*_i  = clip(Z_i, -3, +3)               # Z_WINSOR_LIMIT
        S_i   = 50 + 16.667 * Z*_i              # Z_CENTER + Z_SCALE

    §49 - the alternative, reachable by ``method="percentile"``::

        S_i = 100 * PercentileRank(x_i)

    ``values`` is a **cross-section of ONE component** - the population the
    library's ``mu_i``/``sigma_i`` and its ``PercentileRank`` both require (both
    §19 and §49 are cross-sectional). Returns one 0-100 score per input, or
    ``None`` per value when the cross-section is unusable (fewer than two finite
    observations, or zero spread) - **never 50**, which would claim a measurement
    that does not exist.

    This is declared once, here, and the engine consumes it for any member handed
    a reference cross-section. A per-name leaf has no universe to standardise
    over, so its members are mapped by their own declared bands/ramps through
    :func:`score_engine.align` instead - stated in the module docstring and in
    `docs/scores/MomentumScore.md`.
    """
    vals = list(values or ())
    if method == PERCENTILE_METHOD:
        clean = sorted(float(v) for v in vals if _finite(v) is not None)
        if len(clean) < 2:
            return [None] * len(vals)
        n = len(clean)
        out: list[float | None] = []
        for v in vals:
            f = _finite(v)
            if f is None:
                out.append(None)
                continue
            below = sum(1 for c in clean if c <= f)
            out.append(round(below / n * 100.0, 3))
        return out
    if method != NORMALIZATION_METHOD:
        raise ValueError(
            f"unknown normalization method {method!r}; known: "
            f"{NORMALIZATION_METHOD!r} (§48), {PERCENTILE_METHOD!r} (§49)"
        )
    res = cross_sectional_z(vals)
    if not res:
        return [None] * len(vals)
    zs = res.get("z") or []
    out = []
    for z in zs:
        if z is None:
            out.append(None)
            continue
        zc = max(-float(winsor), min(float(winsor), float(z)))
        out.append(round(max(0.0, min(100.0, center + scale * zc)), 3))
    return out


def _finite(value) -> float | None:
    """A finite float, or ``None`` (booleans and non-numerics are not values)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


# ---------------------------------------------------------------------------
# MOM-6 producers: the two §53 sub-items the tree genuinely lacked
# ---------------------------------------------------------------------------


def efficiency_ratio(closes, n: int = 20) -> float | None:
    """§8.1 directional efficiency ratio ``|P_t - P_(t-n)| / sum|dP_i|`` in [0, 1].

    ``1`` means the move was perfectly directional, ``0`` that every step undid
    the last. ``None`` when the series is too short or the path is flat (no
    denominator) - never a fabricated 0. The nearest producer in the tree,
    `regime.choppiness:141`, computes the same ratio **inverted** onto its own
    0-100 chop scale and never exposes the ratio, so a caller cannot reuse it
    (MOM-6).
    """
    vals = [_finite(c) for c in (closes or ())]
    vals = [v for v in vals if v is not None]
    if n < 1 or len(vals) < n + 1:
        return None
    path = sum(abs(vals[i] - vals[i - 1]) for i in range(len(vals) - n, len(vals)))
    if path <= 0:
        return None
    return round(abs(vals[-1] - vals[-1 - n]) / path, 6)


def positive_day_ratio(returns, n: int = 20) -> float | None:
    """§8.3 positive-day ratio ``sum I(r_i > 0) / n`` over the last ``n`` returns.

    ``None`` below two usable returns - a flat or empty window is not "0% up
    days". No producer existed anywhere in the tree (grep ``positive_day`` = 0);
    the library's §8.2 trend-consistency ratio is the same arithmetic, so one
    producer answers both (MOM-6).
    """
    vals = [_finite(r) for r in (returns or ())]
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return None
    window = vals[-int(n) :] if n and n > 0 else vals
    if not window:
        return None
    return round(sum(1 for r in window if r > 0) / len(window), 6)


# ---------------------------------------------------------------------------
# Alignment and the family/sub-composite assembly
# ---------------------------------------------------------------------------


def align_components(values: dict) -> dict[str, float | None]:
    """``{member: raw}`` -> ``{member: 0-100 favourable | None}``.

    A declared member with no value is ``None`` and leaves its family's
    denominator; an unknown key is ignored (the engine scores what it declares).
    A declared member with neither a band nor a ramp is a defect, not a 50.
    """
    out: dict[str, float | None] = {}
    for name, comp in COMPONENTS.items():
        if name not in (values or {}):
            out[name] = None
            continue
        raw = values.get(name)
        if isinstance(raw, bool):
            raw = 1.0 if raw else 0.0
        if _finite(raw) is None:
            out[name] = None
            continue
        if name in BANDS:
            out[name] = align(raw, direction=comp.direction, band=BANDS[name])
        elif name in RAMPS:
            lo, hi = RAMPS[name]
            out[name] = align(raw, direction=comp.direction, lo=lo, hi=hi)
        else:  # pragma: no cover - a declared member must be mappable
            raise KeyError(f"component {name!r} has neither a band nor a ramp")
    return out


def leg_score(leg: str, aligned: dict, *, min_coverage=LEG_MIN_COVERAGE) -> dict:
    """One §54 family's 0-100 over its own members, or withheld with a reason."""
    if leg not in LEG_COMPONENTS:
        raise KeyError(f"unknown leg {leg!r}; known: {list(LEG_ORDER)}")
    names = LEG_COMPONENTS[leg]
    comps = {name: aligned.get(name) for name in names}
    floor = coverage_floor(min_coverage, len(names))
    res = combine(comps, min_coverage=min(floor, len(names)))
    res["leg"] = leg
    res["leg_name"] = LEG_NAMES[leg]
    return res


def momentum_score(
    values: dict,
    *,
    weights: dict | None = None,
    reference: dict | None = None,
    min_coverage=COMPOSITE_MIN_COVERAGE,
    normalize_method: str = NORMALIZATION_METHOD,
) -> dict:
    """The eight §54 leg sub-scores and their weighted composite.

    ``values`` is ``{member: raw}`` from a producer - nothing is fetched here.
    ``reference`` is an OPTIONAL ``{member: cross-section list}``: a member with a
    reference is normalized by the declared §48 contract instead of its ramp
    (MOM-2), and ``rs_percentile`` exists only on that path.

    Returns ``{"score", "coverage", "floor", "legs", "components", "present",
    "absent", "withheld", "label", "bands", "status", "weights",
    "weight_basis", "basis", "meta"}``. Every leg is always present as a key (a
    leg that could not measure carries ``None`` and its reason), so no leg can
    vanish silently. ``meta`` carries the §§50-52 diagnostics, computed beside
    the score and never inside it.
    """
    vals = dict(values or {})
    refs = dict(reference or {})
    for member, cross_section in refs.items():
        if member not in COMPONENTS:
            continue
        normalized = normalize_component(cross_section, method=normalize_method)
        # The normalized value for THIS name is the LAST entry by convention:
        # the caller appends the name under test to its reference set.
        vals[member] = normalized[-1] if normalized else None
    aligned = align_components(vals)

    legs: dict[str, dict] = {}
    for leg in LEG_ORDER:
        legs[leg] = leg_score(leg, aligned)

    leg_scores = {leg: legs[leg].get("score") for leg in LEG_ORDER}
    w = dict(LEG_WEIGHTS if weights is None else weights)
    res = combine(leg_scores, weights=w, min_coverage=min_coverage, bands=MOMENTUM_BANDS)

    present = sorted(n for n, v in aligned.items() if v is not None)
    absent = sorted(n for n, v in aligned.items() if v is None)
    out = {
        "score": res.get("score"),
        "coverage": res.get("coverage"),
        "floor": res.get("floor"),
        "legs": legs,
        "components": {k: aligned[k] for k in sorted(aligned)},
        "present": present,
        "absent": absent,
        "withheld": res.get("withheld"),
        "label": res.get("label"),
        "bands": MOMENTUM_BANDS,
        "status": STATUS_RESEARCH_ONLY,
        "weights": {k: float(w.get(k, 0.0) or 0.0) for k in LEG_ORDER},
        "weight_basis": (
            "the library's §47 illustrative vector (pending the owner's "
            "ratification - not an owner-signed table)"
        ),
        "basis": res.get("basis"),
    }
    out["meta"] = momentum_meta(legs, aligned)
    return out


# ---------------------------------------------------------------------------
# MOM-3: the meta set - beside the number, never inside it
# ---------------------------------------------------------------------------

#: §50/§51's horizon list.
HORIZON_ORDER: tuple[int, ...] = (5, 21, 63, 126, 252)

#: The P-leg members that carry each horizon's 0-100 score.
HORIZON_MEMBERS: dict[int, str] = {
    5: "r_5",
    21: "r_21",
    63: "r_63",
    126: "r_126",
    252: "r_252",
}


def horizon_scores(aligned: dict) -> dict[int, float | None]:
    """``{horizon: S_h}`` - the P leg's per-horizon 0-100 scores (§50/§51).

    §50's ``S_5..S_252`` and §51's ``Dispersion`` are defined over the horizon
    scores, so they are read from the P leg's aligned members rather than from a
    second producer.
    """
    return {h: (aligned or {}).get(m) for h, m in HORIZON_MEMBERS.items()}


def horizon_conviction(scores: dict) -> dict:
    """§50's horizon agreement, in BOTH forms the library prints.

    * ``by_dispersion = 1 - sigma(S_h)/100`` over the present horizons.
    * ``by_count = #\\{S_h > 50\\} / N_h``.

    Fewer than two measured horizons -> both legs ``None`` with a reason, never
    a fabricated 0 or a fabricated 1.
    """
    present = {h: s for h, s in (scores or {}).items() if s is not None}
    n = len(present)
    if n < 2:
        return {
            "by_dispersion": None,
            "by_count": None,
            "n": n,
            "horizons": dict(scores or {}),
            "reason": f"need >= 2 measured horizons for an agreement read, got {n}",
        }
    mean = sum(present.values()) / n
    sigma = math.sqrt(sum((s - mean) ** 2 for s in present.values()) / n)
    return {
        "by_dispersion": round(max(0.0, min(1.0, 1.0 - sigma / 100.0)), 4),
        "by_count": round(sum(1 for s in present.values() if s > 50.0) / n, 4),
        "n": n,
        "horizons": dict(scores or {}),
        "reason": None,
    }


def horizon_dispersion(scores: dict) -> dict:
    """§51's ``Std(S_5, S_21, S_63, S_126, S_252)``, kept OUTSIDE the score.

    A low dispersion means the horizons agree; a high one means the momentum is
    conflicted. Fewer than two measured horizons -> ``None`` with a reason.
    """
    present = [s for s in (scores or {}).values() if s is not None]
    n = len(present)
    if n < 2:
        return {
            "dispersion": None,
            "n": n,
            "reason": f"need >= 2 measured horizons for a dispersion, got {n}",
        }
    mean = sum(present) / n
    sigma = math.sqrt(sum((s - mean) ** 2 for s in present) / n)
    return {"dispersion": round(sigma, 4), "n": n, "reason": None}


def leg_divergence(legs: dict, *, fundamental: float | None = None) -> dict:
    """§52's family-score divergences, as DIAGNOSTICS (never subtracted).

    Builds ``S_price - S_volume``, ``S_short - S_long`` (the 21d vs 252d
    horizon scores) and, when a fundamental sub-score is supplied,
    ``S_price - S_fundamental``. A leg that could not measure leaves the pair
    ``None`` with that leg's own withheld reason.
    """
    scores = {leg: (entry or {}).get("score") for leg, entry in (legs or {}).items()}
    p, v = scores.get("P"), scores.get("V")
    out = {
        "price_minus_volume": None if p is None or v is None else round(p - v, 2),
        "price_minus_fundamental": (
            None if p is None or fundamental is None else round(p - fundamental, 2)
        ),
        "short_minus_long": None,  # filled below from the horizon scores
        "note": (
            "diagnostics only - the library says these 'should generally be "
            "diagnostics, not automatically subtracted from the score' (§52)"
        ),
    }
    return out


def momentum_meta(legs: dict, aligned: dict, *, fundamental: float | None = None) -> dict:
    """§§50-§52 + coverage, assembled BESIDE the score (MOM-3).

    ``conviction`` and ``dispersion`` are the horizon reads (§50/§51);
    ``divergence`` is the family-score read (§52); ``coverage`` is
    `score_engine.combine`'s own weight fraction over the eight legs;
    ``regime_compatibility`` is **declined in writing** - see
    :data:`DECLINED_SUB_ITEMS`.
    """
    hs = horizon_scores(aligned)
    conv = horizon_conviction(hs)
    disp = horizon_dispersion(hs)
    div = leg_divergence(legs, fundamental=fundamental)
    long_s, short_s = hs.get(252), hs.get(21)
    if short_s is not None and long_s is not None:
        div["short_minus_long"] = round(short_s - long_s, 2)
    leg_fraction = sum(1 for leg in LEG_ORDER if (legs.get(leg) or {}).get("score") is not None)
    return {
        "conviction": conv,
        "dispersion": disp,
        "divergence": div,
        "coverage": round(leg_fraction / len(LEG_ORDER), 4),
        "regime_compatibility": {
            "value": None,
            "declined": DECLINED_SUB_ITEMS["regime_compatibility"],
        },
    }


__all__ = [
    "BANDS",
    "COMPONENTS",
    "COMPOSITE_MIN_COVERAGE",
    "DECLINED_SUB_ITEMS",
    "HORIZON_MEMBERS",
    "HORIZON_ORDER",
    "LEG_COMPONENTS",
    "LEG_MIN_COVERAGE",
    "LEG_NAMES",
    "LEG_ORDER",
    "LEG_WEIGHTS",
    "MOMENTUM_BANDS",
    "NORMALIZATION_METHOD",
    "NORMALIZATION_SOURCE",
    "PERCENTILE_METHOD",
    "RAMPS",
    "RETIRED_MEMBERS",
    "STATUS_RESEARCH_ONLY",
    "Z_CENTER",
    "Z_SCALE",
    "Z_WINSOR_LIMIT",
    "align_components",
    "efficiency_ratio",
    "horizon_conviction",
    "horizon_dispersion",
    "horizon_scores",
    "leg_divergence",
    "leg_score",
    "momentum_meta",
    "momentum_score",
    "normalize_component",
    "positive_day_ratio",
]
