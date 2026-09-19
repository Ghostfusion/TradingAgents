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
        _c("adx", "trend", "higher_better", "technical_factors.adx:179"),
        _c("di_spread", "trend", "higher_better", "technical_factors.adx:179 (di_plus - di_minus)"),
        _c("above_sma200", "trend", "higher_better", "swing.trend_architecture:71"),
        _c("sma_stack", "trend", "higher_better", "swing.trend_architecture:71"),
        _c("golden_cross", "trend", "higher_better", "extended_indicators.golden_death_cross:53"),
        _c("ichimoku_above_cloud", "trend", "higher_better", "extended_indicators.ichimoku:78"),
        _c("aroon_osc", "trend", "higher_better", "technical_factors.aroon:513 (up - down)"),
        # momentum (18)
        _c("rsi", "momentum", "higher_better", "swing.rsi:39", "NON-MONOTONIC: band-mapped"),
        _c("stoch_k", "momentum", "higher_better", "technical_factors.stochastic_oscillator:146", "NON-MONOTONIC"),
        _c("mfi", "momentum", "higher_better", "technical_factors.mf_index:112", "NON-MONOTONIC"),
        _c("roc20", "momentum", "higher_better", "extended_indicators.roc:149"),
        _c("momentum_12_1", "momentum", "higher_better", "momentum.momentum_12_1:358"),
        _c("macd_hist_pct", "momentum", "higher_better", "value_dip._macd_hist:500 / last close"),
        # relative strength (12)
        _c("rs_slope_pct", "relative_strength", "higher_better", "relative_strength.slope_pct:49 (percent per day)"),
        # The RS LEVEL (stock/benchmark) is scale-dependent - it is a price ratio,
        # not a normalised score - so it is NOT a component. `above_sma` (the RS
        # line against its own trailing average) is the scale-free equivalent.
        _c("rs_above_sma", "relative_strength", "higher_better", "relative_strength.rs_trend:132 (above_sma)"),
        _c("rs_new_high", "relative_strength", "higher_better", "relative_strength.rs_position:89"),
        _c("rs_divergence", "relative_strength", "higher_better", "relative_strength.divergence:113", "1 = divergence present (bad)"),
        # price structure (12)
        _c("bollinger_pct_b", "price_structure", "higher_better", "value_dip.bollinger_pct_b:75", "NON-MONOTONIC"),
        _c("keltner_pct", "price_structure", "higher_better", "technical_factors.keltner_channel:349", "NON-MONOTONIC"),
        _c("near_sma200", "price_structure", "higher_better", "value_dip.support_structure:714", "1 = within 3% of the 200-SMA"),
        _c("fib_zone", "price_structure", "higher_better", "swing.fib_levels:290"),
        # volume (10)
        _c("rvol", "volume", "higher_better", "momentum.rvol:25"),
        _c("elder_ratio", "volume", "higher_better", "technical_factors.elder_thermometer:494", "NON-MONOTONIC"),
        _c("cmf", "volume", "higher_better", "extended_indicators.chaikin_money_flow:261"),
        _c("volume_dry_up", "volume", "higher_better", "value_dip.volume_dry_up:601"),
        # breakout / pullback (10)
        _c("vcp_candidate", "breakout", "higher_better", "swing.vcp_setup:326"),
        _c("near_breakout", "breakout", "higher_better", "swing.vcp_setup:326"),
        _c("pullback_candidate", "breakout", "higher_better", "swing.pullback_setup:156"),
        _c("trigger_candle", "breakout", "higher_better", "value_dip.trigger_candle:625"),
        # mean reversion (8)
        _c("stoch_rsi", "mean_reversion", "higher_better", "technical_factors.stoch_rsi:283", "NON-MONOTONIC"),
        _c("rsi2", "mean_reversion", "higher_better", "technical_factors.rsi2:315", "NON-MONOTONIC"),
        _c("williams_r", "mean_reversion", "higher_better", "technical_factors.williams_r:338", "NON-MONOTONIC"),
        _c("hurst", "mean_reversion", "lower_better", "mean_reversion.hurst_exponent:112", "H<0.5 is mean-reverting"),
        _c("obv_bullish_div", "mean_reversion", "higher_better", "technical_factors.obv_divergence:414"),
        # volatility (5) - risk-increasing, so every leg is lower_better
        _c("atr_pct", "volatility", "lower_better", "size.atr:131 / last close"),
        _c("vol_percentile", "volatility", "lower_better", "regime.vol_percentile:50"),
        _c("sqrt_rs_minus", "volatility", "lower_better", "volatility_models.semivariance:48"),
        # breadth (5)
        _c("pct_above_50d", "breadth", "higher_better", "strategies/market_breadth.py::market_breadth"),
        _c("pct_above_200d", "breadth", "higher_better", "strategies/market_breadth.py::market_breadth"),
        _c("ad_ratio", "breadth", "higher_better", "strategies/market_breadth.py::market_breadth"),
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


def technical_score(
    values: dict,
    *,
    weights: dict | None = None,
    min_coverage=COMPOSITE_MIN_COVERAGE,
    category_min_coverage=CATEGORY_MIN_COVERAGE,
) -> dict:
    """The nine category sub-scores and their weighted composite.

    ``values`` is ``{component: raw value}`` over the components declared in
    ``COMPONENTS``; anything absent is ``NA`` and is reported, never scored as 0.

    ``weights`` overrides the owner's category weights; ``None`` uses them, and
    the basis prints which vector was used. The composite renormalises over the
    categories that produced a score, so a category that could not be measured
    lowers ``coverage`` instead of the score.

    Returns ``{"score", "coverage", "categories", "components", "aligned",
    "bands", "weights", "status", "withheld", "basis"}``.
    """
    aligned = align_components(values)
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
                "raw": (values or {}).get(name),
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


__all__ = [
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
]
