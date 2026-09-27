"""`TechnicalScore` - nine category sub-scores over already-computed components.

The engine the owner's staged weights describe (`docs/scores/TechnicalScore.md`
§0.2): trend 20, momentum 18, relative strength 12, price structure 12, volume
10, breakout/pullback 10, mean reversion 8, volatility/ATR 5, breadth 5.

Four rules this module exists to hold:

1. **One pure function over existing inputs.** It takes a flat
   ``{component: raw value}`` dict - every value is produced elsewhere, from the
   run's own OHLCV. No fetch, no formula, no vendor call lives here.
2. **Direction first, weight second.** Every component declares its direction,
   and the **non-monotonic** ones (RSI, MFI, stochastic, StochRSI, RSI2,
   Williams %R, Bollinger %b, the Elder thermometer, Keltner %b) are
   **band-mapped over the producer's own edges** - the same bands the producer's
   consumers already read. A naive ramp inverts them, and that inversion is the
   single biggest correctness risk in this engine.
3. **`NA` is not `0`** (master rule 1). A component with no value is absent from
   the dict or ``None``; it leaves the denominator, the category reports its
   coverage, and a category below its floor is withheld with the reason. Nothing
   is ever substituted with a neutral 50 or a punitive 0.
4. **Nothing here sizes anything.** `TechnicalScore` never touches
   `risk/sizing.py`, never feeds `decision_guardrail.SCORE_BANDS`, and is never
   quoted as a forecast. Its bands are advisory labels of its own.

Every ramp edge and every band's *score* is a **hypothesis** - the producer's own
edges are used wherever the producer publishes one, and the rest are this
engine's declared policy, printed in the basis and measured in Phase C against
realised forward returns. The band tables are declared here, in one place, so
that measurement has one thing to move.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from .score_engine import align, band_label, combine, coverage_floor

# --- The owner's weights ---------------------------------------------------

CATEGORY_WEIGHTS: dict[str, float] = {
    "trend": 20.0,
    "momentum": 18.0,
    "relative_strength": 12.0,
    "price_structure": 12.0,
    "volume": 10.0,
    "breakout": 10.0,
    "mean_reversion": 8.0,
    "volatility": 5.0,
    "breadth": 5.0,
}

CATEGORY_ORDER: tuple[str, ...] = tuple(CATEGORY_WEIGHTS)

# --- The band tables -------------------------------------------------------
#
# Walked top-down by ``score_engine.align``: the first entry whose edge the
# value is at or above wins, so the tables are written from the HIGH end of the
# input downward and each score is the contribution of THAT band - the
# favourable band for the non-monotonic inputs is not the top one. RSI is the
# clearest case: 45-70 (`strong`) scores 85 while >70 (`hot`) scores 45, because
# `hot` is where the producer's own consumers stop adding.
#
# The bands the producer's own consumers already read are marked below
# (TechnicalScore.md §0.3); the rest are this engine's declared policy.

BANDS: dict[str, tuple] = {
    # RSI: 45-70 is `strong`, >70 is `hot`, <40 is `broken` (swing.rsi_band).
    "rsi": ((70.0, 45.0), (45.0, 85.0), (40.0, 55.0), (0.0, 20.0)),
    # Stochastic K: <20 is `oversold`, the dip read.
    "stoch_k": ((80.0, 30.0), (20.0, 50.0), (0.0, 80.0)),
    # MFI: >80 is overbought.
    "mfi": ((80.0, 25.0), (20.0, 50.0), (0.0, 80.0)),
    # StochRSI: <0.2 is the entry.
    "stoch_rsi": ((0.8, 25.0), (0.2, 50.0), (0.0, 80.0)),
    # RSI2: <10 is the buy, >70 stretched.
    "rsi2": ((70.0, 25.0), (10.0, 50.0), (0.0, 85.0)),
    # Williams %R: -80..-100 is oversold.
    "williams_r": ((-20.0, 25.0), (-80.0, 50.0), (-100.0, 80.0)),
    # Bollinger %b: <=0 is the dip, >1 is extended.
    "bollinger_pct_b": ((1.0, 20.0), (0.5, 45.0), (0.0, 60.0), (-10.0, 85.0)),
    # Keltner %b: the mid-band is the read.
    "keltner_pct": ((1.0, 25.0), (0.5, 70.0), (0.0, 50.0), (-10.0, 35.0)),
    # Elder thermometer: `quiet` (<0.8) is the good dip read.
    "elder_ratio": ((1.5, 30.0), (0.8, 55.0), (0.0, 80.0)),
    # Boolean states: 1.0 true, 0.0 false (never a missing value).
    "above_sma200": ((1.0, 75.0), (0.0, 35.0)),
    "sma_stack": ((1.0, 80.0), (0.0, 30.0)),
    "golden_cross": ((1.0, 75.0), (0.0, 30.0)),
    "ichimoku_above_cloud": ((1.0, 75.0), (0.0, 35.0)),
    "rs_new_high": ((1.0, 80.0), (0.0, 45.0)),
    # A divergence is a warning, not a signal.
    "rs_divergence": ((1.0, 25.0), (0.0, 60.0)),
    "rs_above_sma": ((1.0, 70.0), (0.0, 35.0)),
    "near_sma200": ((1.0, 80.0), (0.0, 45.0)),
    "fib_zone": ((1.0, 80.0), (0.0, 50.0)),
    "volume_dry_up": ((1.0, 75.0), (0.0, 50.0)),
    "vcp_candidate": ((1.0, 80.0), (0.0, 45.0)),
    "near_breakout": ((1.0, 85.0), (0.0, 45.0)),
    "pullback_candidate": ((1.0, 75.0), (0.0, 50.0)),
    "trigger_candle": ((1.0, 80.0), (0.0, 45.0)),
    "obv_bullish_div": ((1.0, 75.0), (0.0, 50.0)),
}

# Ramps: ``(lo, hi)`` mapped to 0 -> 100 (inverted for ``lower_better``). Every
# edge is a hypothesis; Phase C measures them.
RAMPS: dict[str, tuple[float, float]] = {
    "adx": (15.0, 40.0),
    "di_spread": (-20.0, 20.0),
    "aroon_osc": (-60.0, 60.0),
    "roc20": (-0.10, 0.10),
    "momentum_12_1": (-0.20, 0.40),
    "macd_hist_pct": (-0.02, 0.02),
    "rs_slope_pct": (-0.10, 0.10),
    "rvol": (0.50, 2.00),
    "cmf": (-0.20, 0.20),
    "hurst": (0.40, 0.65),
    "atr_pct": (0.010, 0.050),
    "vol_percentile": (0.10, 0.90),
    "sqrt_rs_minus": (0.008, 0.030),
    "pct_above_50d": (20.0, 80.0),
    "pct_above_200d": (20.0, 80.0),
    "ad_ratio": (-0.30, 0.30),
    # TECH-14: the library's thrust is the EMA rising from 0.40 to 0.615
    # within the window - a +0.20 move in the advance ratio is the
    # canonical magnitude, so 0 credit at no rise and 100 at the event.
    "zweig_thrust": (0.0, 0.20),
    # max pain: how far spot sits from the monthly pin, in ATRs. Closer
    # is the mean-reverting read, so lower_better.
    "max_pain_dist_atr": (0.0, 2.0),
    # Donchian breakout persistence: signed net share of the last N closes
    # beyond the prior-window reference levels (persistence_up - persistence_dn),
    # in [-1, 1]. higher_better.
    "breakout_persistence": (-1.0, 1.0),
}


class Component(NamedTuple):
    """One component: which category it feeds, its direction, its producer."""

    name: str
    category: str
    direction: str
    producer: str
    note: str = ""


def _c(name, category, direction, producer, note=""):
    return Component(name, category, direction, producer, note)


# --- The component map -----------------------------------------------------

COMPONENTS: dict[str, Component] = {
    c.name: c
    for c in (
        # trend (20)
        _c("adx", "trend", "higher_better", "technical_factors.adx:230"),
        _c("di_spread", "trend", "higher_better", "technical_factors.adx:230 (di_plus - di_minus)"),
        _c("above_sma200", "trend", "higher_better", "swing.trend_architecture:76"),
        _c("sma_stack", "trend", "higher_better", "swing.trend_architecture:76"),
        _c("golden_cross", "trend", "higher_better", "extended_indicators.golden_death_cross:55"),
        _c("ichimoku_above_cloud", "trend", "higher_better", "extended_indicators.ichimoku:80"),
        _c("aroon_osc", "trend", "higher_better", "technical_factors.aroon:668 (up - down)"),
        # momentum (18)
        _c("rsi", "momentum", "higher_better", "swing.rsi:44", "NON-MONOTONIC: band-mapped"),
        _c("stoch_k", "momentum", "higher_better", "technical_factors.stochastic_oscillator:197", "NON-MONOTONIC"),
        _c("mfi", "momentum", "higher_better", "technical_factors.mf_index:163", "NON-MONOTONIC"),
        _c("roc20", "momentum", "higher_better", "extended_indicators.roc:151"),
        _c("momentum_12_1", "momentum", "higher_better", "momentum.momentum_12_1:358"),
        _c("macd_hist_pct", "momentum", "higher_better", "value_dip._macd_hist:502 / last close"),
        # relative strength (12)
        _c("rs_slope_pct", "relative_strength", "higher_better", "relative_strength.slope_pct:49 (percent per day)"),
        # The RS LEVEL (stock/benchmark) is scale-dependent - it is a price ratio,
        # not a normalised score - so it is NOT a component. `above_sma` (the RS
        # line against its own trailing average) is the scale-free equivalent.
        _c("rs_above_sma", "relative_strength", "higher_better", "relative_strength.rs_trend:68 (above_sma)"),
        _c("rs_new_high", "relative_strength", "higher_better", "relative_strength.rs_position:89"),
        _c("rs_divergence", "relative_strength", "higher_better", "relative_strength.divergence:195", "1 = divergence present (bad)"),
        # price structure (12)
        _c("bollinger_pct_b", "price_structure", "higher_better", "value_dip.bollinger_pct_b:77", "NON-MONOTONIC"),
        _c("keltner_pct", "price_structure", "higher_better", "technical_factors.keltner_channel:440", "NON-MONOTONIC"),
        _c("near_sma200", "price_structure", "higher_better", "value_dip.support_structure:833", "1 = within 3% of the 200-SMA"),
        _c("fib_zone", "price_structure", "higher_better", "swing.fib_levels:295"),
        _c("max_pain_dist_atr", "price_structure", "lower_better", "derivatives_gamma.max_pain:184 (abs distance / ATR)",
           "0 = spot sits on the monthly max-pain strike"),
        # volume (10)
        _c("rvol", "volume", "higher_better", "momentum.rvol:25"),
        _c("elder_ratio", "volume", "higher_better", "technical_factors.elder_thermometer:649", "NON-MONOTONIC"),
        _c("cmf", "volume", "higher_better", "extended_indicators.chaikin_money_flow:263"),
        _c("volume_dry_up", "volume", "higher_better", "value_dip.volume_dry_up:603"),
        # breakout / pullback (10)
        _c("vcp_candidate", "breakout", "higher_better", "swing.vcp_setup:342"),
        _c("near_breakout", "breakout", "higher_better", "swing.vcp_setup:342"),
        _c("pullback_candidate", "breakout", "higher_better", "swing.pullback_setup:161"),
        _c("trigger_candle", "breakout", "higher_better", "value_dip.trigger_candle:661"),
        # The Donchian breakout STATE (technical_factors.donchian_channel:
        # breakout_up/dn + persistence_up/dn) until now reached no category. Fed
        # via ``values`` or the ``donchian`` keyword of ``technical_score``.
        _c("breakout_persistence", "breakout", "higher_better",
           "technical_factors.donchian_channel (persistence_up - persistence_dn)"),
        # mean reversion (8)
        _c("stoch_rsi", "mean_reversion", "higher_better", "technical_factors.stoch_rsi:374", "NON-MONOTONIC"),
        _c("rsi2", "mean_reversion", "higher_better", "technical_factors.rsi2:406", "NON-MONOTONIC"),
        _c("williams_r", "mean_reversion", "higher_better", "technical_factors.williams_r:429", "NON-MONOTONIC"),
        _c("hurst", "mean_reversion", "lower_better", "mean_reversion.hurst_exponent:113", "H<0.5 is mean-reverting"),
        _c("obv_bullish_div", "mean_reversion", "higher_better", "technical_factors.obv_divergence:542"),
        # volatility (5) - risk-increasing, so every leg is lower_better
        _c("atr_pct", "volatility", "lower_better", "size.atr:143 / last close"),
        _c("vol_percentile", "volatility", "lower_better", "regime.vol_percentile:59"),
        _c("sqrt_rs_minus", "volatility", "lower_better", "volatility_models.semivariance:68"),
        # breadth (5)
        _c("pct_above_50d", "breadth", "higher_better", "strategies/market_breadth.py::market_breadth"),
        _c("pct_above_200d", "breadth", "higher_better", "strategies/market_breadth.py::market_breadth"),
        _c("ad_ratio", "breadth", "higher_better", "strategies/market_breadth.py::market_breadth"),
        # TECH-14 (owner decision 2026-09-27): the Zweig breadth thrust is a LEG
        # of this category, not a new weighted one - the declared
        # CATEGORY_WEIGHTS vector does not move. The raw value is the window's
        # EMA change in the advance ratio (`technical_depth.zweig_breadth_thrust`
        # returns the continuous magnitude AND the boolean event; the magnitude
        # is what a ramp can score).
        _c("zweig_thrust", "breadth", "higher_better",
           "technical_depth.zweig_breadth_thrust:400",
           "the EMA change in adv/(adv+dec) over the thrust window; the library's "
           "own event (\u00a7120) is the EMA rising 0.40 -> 0.615 within 10 bars, "
           "so the ramp below is that magnitude"),
    )
}

CATEGORY_COMPONENTS: dict[str, tuple[str, ...]] = {
    cat: tuple(c.name for c in COMPONENTS.values() if c.category == cat)
    for cat in CATEGORY_ORDER
}

# This engine's own advisory bands - never `decision_guardrail.SCORE_BANDS`.
TECH_BANDS: tuple = (
    (80.0, "strong uptrend"),
    (65.0, "constructive"),
    (50.0, "neutral"),
    (35.0, "deteriorating"),
    (20.0, "weak"),
    (0.0, "broken"),
)

STATUS_ADVISORY = "ADVISORY"

# A category floor of 2 of its own components; capped at the category's own
# count (a one-component category must not be withheld forever).
CATEGORY_MIN_COVERAGE = 2
COMPOSITE_MIN_COVERAGE = 3


def _coerce(value, component: Component):
    """Booleans become 1.0/0.0 (a boolean is a measurement, not a gap)."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return value


def align_components(values: dict) -> dict[str, float | None]:
    """``{component: raw}`` -> ``{component: 0-100 favourable | None}``.

    An unknown key is ignored (the engine scores what it declares); a declared
    component with no value is ``None`` and leaves the denominator.
    """
    out: dict[str, float | None] = {}
    for name, comp in COMPONENTS.items():
        if name not in (values or {}):
            out[name] = None
            continue
        raw = _coerce(values.get(name), comp)
        if raw is None:
            out[name] = None
            continue
        if name in BANDS:
            out[name] = align(raw, direction=comp.direction, band=BANDS[name])
        elif name in RAMPS:
            lo, hi = RAMPS[name]
            out[name] = align(raw, direction=comp.direction, lo=lo, hi=hi)
        else:  # a declared component with no mapping is a defect, not a 50
            raise KeyError(f"component {name!r} has neither a band nor a ramp")
    return out


def category_score(category: str, aligned: dict, *, min_coverage=CATEGORY_MIN_COVERAGE) -> dict:
    """One category's 0-100 over its own components, or withheld with a reason."""
    if category not in CATEGORY_COMPONENTS:
        raise KeyError(f"unknown category {category!r}; known: {list(CATEGORY_ORDER)}")
    names = CATEGORY_COMPONENTS[category]
    comps = {name: aligned.get(name) for name in names}
    floor = coverage_floor(min_coverage, len(names))
    res = combine(comps, min_coverage=min(floor, len(names)))
    res["category"] = category
    res["weight"] = CATEGORY_WEIGHTS[category]
    res["band"] = band_label(res.get("score"), TECH_BANDS)
    res["raw_directions"] = {name: COMPONENTS[name].direction for name in names}
    return res


def _donchian_breakout(donchian) -> float | None:
    """Signed Donchian breakout-persistence read in [-1, 1], or None.

    Fed by ``technical_factors.donchian_channel``. The primary read is the net
    persistence ``persistence_up - persistence_dn`` (the share of the last N
    closes beyond the prior-window reference levels, §43/§44); when the channel
    exposed no persistence but did expose the breakout flags, the flag sign is
    used (``+1`` up / ``-1`` down / ``0`` neither). A dict with neither returns
    ``None`` so the component stays absent — never a neutral 0.
    """
    if not isinstance(donchian, dict):
        return None
    pu = donchian.get("persistence_up")
    pd = donchian.get("persistence_dn")
    if pu is not None or pd is not None:
        return (float(pu) if pu is not None else 0.0) - (float(pd) if pd is not None else 0.0)
    up = donchian.get("breakout_up")
    dn = donchian.get("breakout_dn")
    if up is None and dn is None:
        return None
    return (1.0 if up else 0.0) - (1.0 if dn else 0.0)


def technical_score(
    values: dict,
    *,
    donchian: dict | None = None,
    weights: dict | None = None,
    min_coverage=COMPOSITE_MIN_COVERAGE,
    category_min_coverage=CATEGORY_MIN_COVERAGE,
) -> dict:
    """The nine category sub-scores and their weighted composite.

    ``values`` is ``{component: raw value}`` over the components declared in
    ``COMPONENTS``; anything absent is ``NA`` and is reported, never scored as 0.

    ``donchian`` is the optional ``technical_factors.donchian_channel`` output.
    When supplied and ``values`` does not already carry ``breakout_persistence``,
    the Donchian breakout state is turned into that component (net persistence,
    ``persistence_up - persistence_dn``) so the breakout category can measure it.
    Keyword-only and defaulted to ``None``, so every pre-existing caller is
    unchanged. A caller may instead pass ``values["breakout_persistence"]``
    directly.

    ``weights`` overrides the owner's category weights; ``None`` uses them, and
    the basis prints which vector was used. The composite renormalises over the
    categories that produced a score, so a category that could not be measured
    lowers ``coverage`` instead of the score.

    Returns ``{"score", "coverage", "categories", "components", "aligned",
    "bands", "weights", "status", "withheld", "basis"}``.
    """
    merged = dict(values or {})
    if "breakout_persistence" not in merged:
        breakout = _donchian_breakout(donchian)
        if breakout is not None:
            merged["breakout_persistence"] = breakout
    aligned = align_components(merged)
    cats = {
        cat: category_score(cat, aligned, min_coverage=category_min_coverage)
        for cat in CATEGORY_ORDER
    }
    w = dict(weights) if weights is not None else dict(CATEGORY_WEIGHTS)
    comps = {cat: cats[cat].get("score") for cat in CATEGORY_ORDER}
    combined = combine(comps, weights=w, min_coverage=min_coverage)

    measured = [name for name, v in aligned.items() if v is not None]
    absent = [name for name, v in aligned.items() if v is None]
    basis = (
        f"TechnicalScore: {len(measured)} of {len(COMPONENTS)} component(s) measured "
        f"-> {sum(1 for c in cats.values() if c.get('score') is not None)} of "
        f"{len(CATEGORY_ORDER)} category sub-scores -> "
        f"{'owner' if weights is None else 'supplied'} weights "
        f"{dict(sorted(w.items()))}; "
        f"non-monotonic inputs band-mapped over the producer's own edges "
        f"({sorted(n for n in BANDS if n in measured)}); "
        f"coverage {combined.get('coverage')}; "
        f"component coverage {len(measured)}/{len(COMPONENTS)}; "
        f"advisory only - never a gate, never a size, never a forecast"
    )
    return {
        "score": combined.get("score"),
        "coverage": combined.get("coverage"),
        "floor": combined.get("floor"),
        "categories": cats,
        "components": {
            name: {
                "raw": merged.get(name),
                "aligned": aligned.get(name),
                "direction": COMPONENTS[name].direction,
                "category": COMPONENTS[name].category,
                "producer": COMPONENTS[name].producer,
            }
            for name in COMPONENTS
        },
        "aligned": aligned,
        "bands": band_label(combined.get("score"), TECH_BANDS),
        "weights": w if weights is not None else None,
        "status": STATUS_ADVISORY,
        "withheld": combined.get("withheld"),
        "measured": measured,
        "absent": absent,
        "basis": basis,
    }


def category_weight_share(weights: dict | None = None) -> dict[str, float]:
    """``{category: weight}`` actually used, so a reader can renormalise."""
    w = dict(weights) if weights is not None else dict(CATEGORY_WEIGHTS)
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


# --- The §129-§131 state readers -------------------------------------------
#
# §129/§130/§131 name `TechnicalState`, `TechnicalAcceleration`/`Jerk` and
# `TechnicalDispersion`/`Agreement` but give none of them a formula (§8.3
# defect 10 of `docs/scores/TechnicalScore.md`), so the mapping each reader
# applies is this engine's declared policy - the position `TECH_BANDS` already
# occupies - while every constant is printed so a measurement can move it.

#: §129's seven state names, verbatim (`Strategies/scores/technical_score.md`
#: lines 2576-2582). The library names all seven; none is unbound.
TECHNICAL_STATES: tuple[str, ...] = (
    "STRONG_UPTREND",
    "UPTREND",
    "WEAK_UPTREND",
    "NEUTRAL",
    "WEAK_DOWNTREND",
    "DOWNTREND",
    "STRONG_DOWNTREND",
)

#: §129's `f(MAAlignment, MASlope, ADX, MACD, Structure)` split into the four
#: legs whose SIGN carries the direction; `adx` is the magnitude, read apart.
_STATE_DIRECTIONAL_LEGS: tuple[str, ...] = (
    "ma_alignment", "ma_slope", "macd", "structure",
)

#: ADX at/above which a fully-aligned leg set is called `STRONG_*` rather than
#: the plain direction (Wilder's conventional 25). An engine-declared edge.
STRONG_TREND_ADX = 25.0

#: Ceiling of the population std of a vector bounded to ``[0, 100]``: half the
#: entries at each edge give ``(100 - 0)/2 = 50``. §131's `NormalizedDispersion`
#: divides by a normaliser it never fixes; this is the one §131 implies.
_DISAGREEMENT_SCALE = 50.0


def technical_state(legs: dict, *, adx: float | None = None,
                    strong_adx: float = STRONG_TREND_ADX) -> dict:
    """§129's seven-state ``TechnicalState`` from the five factors it names.

    Reads the factors §129's ``TrendState = f(MAAlignment, MASlope, ADX, MACD,
    Structure)`` names, supplied by the caller (no producer in this engine
    computes a state). Each of the four **directional** legs (``ma_alignment``,
    ``ma_slope``, ``macd``, ``structure``) is reduced to its sign (``+1`` /
    ``0`` / ``-1``); ``adx`` is the trend-strength magnitude, taken from the
    ``adx`` keyword or, if that is absent, from ``legs["adx"]`` when present.

    The net sign count maps to §129's enum::

        net  +4 (adx >= strong_adx)    -> STRONG_UPTREND     net  0      -> NEUTRAL
        net  +4 (weaker adx) or +3     -> UPTREND            net  -1/-2  -> WEAK_DOWNTREND
        net  +1 or +2                  -> WEAK_UPTREND       net  -3     -> DOWNTREND
                                                             net  -4     -> STRONG_DOWNTREND
                                                                            (if adx >= strong_adx),
                                                                            else DOWNTREND

    The seven names are §129's own (``Strategies/scores/technical_score.md``
    lines 2576-2582); **none is unbound** — the library names all seven. §129
    gives the mapping function ``f`` no formula, so the sign-count rule and
    ``strong_adx`` are this engine's declared policy, not a library formula.
    ``STRONG_UPTREND`` and ``STRONG_DOWNTREND`` cannot be reached without a
    numeric ``adx``: strength is undefined without it.

    Returns ``{"state", "net", "direction", "legs_compared", "adx",
    "strong_adx", "reason"}``. ``reason`` is a string and ``state`` is ``None``
    when no directional leg carries a usable reading — never a fabricated
    ``NEUTRAL``.
    """
    out = {
        "state": None, "net": None, "direction": None, "legs_compared": [],
        "adx": None, "strong_adx": float(strong_adx), "reason": None,
    }
    src = legs if isinstance(legs, dict) else {}
    signs: dict[str, int] = {}
    for name in _STATE_DIRECTIONAL_LEGS:
        value = src.get(name)
        if value is None:
            continue
        try:
            fv = float(value)
        except (TypeError, ValueError):
            continue
        signs[name] = 1 if fv > 0 else (-1 if fv < 0 else 0)
    if not signs:
        out["reason"] = (
            "no directional leg among ma_alignment/ma_slope/macd/structure: "
            "state unmeasured"
        )
        return out
    adx_val = adx if adx is not None else src.get("adx")
    try:
        adx_val = float(adx_val) if adx_val is not None else None
    except (TypeError, ValueError):
        adx_val = None
    net = sum(signs.values())
    strong = adx_val is not None and adx_val >= float(strong_adx)
    if net >= 4 and strong:
        state = "STRONG_UPTREND"
    elif net >= 3:
        state = "UPTREND"
    elif net >= 1:
        state = "WEAK_UPTREND"
    elif net == 0:
        state = "NEUTRAL"
    elif net >= -2:
        state = "WEAK_DOWNTREND"
    elif net >= -3:
        state = "DOWNTREND"
    elif strong:
        state = "STRONG_DOWNTREND"
    else:
        state = "DOWNTREND"
    out.update({
        "state": state,
        "net": net,
        "direction": "up" if net > 0 else ("down" if net < 0 else "flat"),
        "legs_compared": [n for n in _STATE_DIRECTIONAL_LEGS if n in signs],
        "adx": adx_val,
    })
    return out


def technical_acceleration(series, n: int = 1) -> dict:
    """Second difference of a composite/indicator series (§130).

    Reads a numeric ``series`` — a history of ``technical_score``'s ``"score"``
    (the composite) or of any single indicator the caller has recorded — and
    differences it with an ``n``-step lag:

    * ``velocity`` — ``x_t - x_{t-n}``, the quantity §130 writes as
      ``TechnicalAcceleration = TechnicalScore_t - TechnicalScore_{t-n}``.
    * ``acceleration`` — ``x_t - 2 x_{t-n} + x_{t-2n}``, the second difference
      (this module's acceleration read; §130 names the same expression
      ``TechnicalJerk``).
    * ``jerk`` — the third difference ``accel_t - accel_{t-n}``; ``None`` until
      ``3n + 1`` observations exist.

    A flat series gives ``acceleration == 0``; a convex one a positive second
    difference. Returns ``{"acceleration", "velocity", "jerk", "n",
    "observations", "reason"}`` with the three numbers ``None`` and ``reason``
    a string when fewer than ``2n + 1`` usable observations exist (never a
    fabricated 0).
    """
    lag = int(n)
    out = {
        "acceleration": None, "velocity": None, "jerk": None,
        "n": lag, "observations": 0, "reason": None,
    }
    vals = [float(v) for v in (series or []) if v is not None]
    out["observations"] = len(vals)
    if lag < 1 or len(vals) < 2 * lag + 1:
        out["reason"] = (
            f"fewer than {2 * max(lag, 1) + 1} usable observations at lag "
            f"n={lag}: acceleration unmeasured"
        )
        return out
    velocity = vals[-1] - vals[-1 - lag]
    accel = vals[-1] - 2.0 * vals[-1 - lag] + vals[-1 - 2 * lag]
    jerk = None
    if len(vals) >= 3 * lag + 1:
        prev_accel = vals[-1 - lag] - 2.0 * vals[-1 - 2 * lag] + vals[-1 - 3 * lag]
        jerk = accel - prev_accel
    out.update({
        "acceleration": round(accel, 6),
        "velocity": round(velocity, 6),
        "jerk": round(jerk, 6) if jerk is not None else None,
        "reason": None,
    })
    return out


def technical_disagreement(categories) -> dict:
    """§131 dispersion / agreement across the category sub-scores.

    Reads the per-category 0-100 scores — either the ``"categories"`` mapping
    of a ``technical_score(...)`` result (each value a sub-dict carrying
    ``"score"``) or a plain ``{category: score}`` mapping — and reports how far
    apart the measured categories are. Only non-``None`` scores enter;
    ``compared`` names exactly which inputs were used, because §0.4/§6.5 make
    redundancy control mandatory before the weights are trusted.

    * ``dispersion`` — the population standard deviation of the compared scores.
    * ``disagreement`` — ``dispersion / 50`` (§131's ``NormalizedDispersion``;
      50 is the largest population std a vector bounded to ``[0, 100]`` can
      have — half the entries at each edge). A fully agreeing vector gives
      ``0``; one split half at ``0`` and half at ``100`` gives ``1``.
    * ``agreement`` — ``1 - disagreement`` (§131's ``TechnicalAgreement``).

    Returns ``{"disagreement", "agreement", "dispersion", "scale", "compared",
    "n", "reason"}`` with the numbers ``None``, ``compared`` empty and
    ``reason`` a string when fewer than two measured sub-scores were supplied.
    """
    out = {
        "disagreement": None, "agreement": None, "dispersion": None,
        "scale": _DISAGREEMENT_SCALE, "compared": [], "n": 0, "reason": None,
    }
    src = None
    if isinstance(categories, dict):
        inner = categories.get("categories")
        src = inner if isinstance(inner, dict) else categories
    scores: dict[str, float] = {}
    for name, value in (src or {}).items():
        if isinstance(value, dict):
            value = value.get("score")
        if value is None:
            continue
        try:
            scores[str(name)] = float(value)
        except (TypeError, ValueError):
            continue
    if len(scores) < 2:
        out["compared"] = sorted(scores)
        out["n"] = len(scores)
        out["reason"] = (
            "fewer than 2 measured category sub-scores: dispersion unmeasured"
        )
        return out
    vals = list(scores.values())
    mean = sum(vals) / len(vals)
    dispersion = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
    disagreement = dispersion / _DISAGREEMENT_SCALE
    out.update({
        "disagreement": round(disagreement, 6),
        "agreement": round(1.0 - disagreement, 6),
        "dispersion": round(dispersion, 6),
        "compared": sorted(scores),
        "n": len(vals),
    })
    return out


__all__ = [
    "TECHNICAL_STATES",
    "STRONG_TREND_ADX",
    "CATEGORY_WEIGHTS",
    "CATEGORY_ORDER",
    "CATEGORY_COMPONENTS",
    "COMPONENTS",
    "Component",
    "BANDS",
    "RAMPS",
    "TECH_BANDS",
    "STATUS_ADVISORY",
    "CATEGORY_MIN_COVERAGE",
    "COMPOSITE_MIN_COVERAGE",
    "align_components",
    "category_score",
    "technical_score",
    "category_weight_share",
    "technical_state",
    "technical_acceleration",
    "technical_disagreement",
]
