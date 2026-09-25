"""`RegimeScore` (WP-4) - the ENVIRONMENT, not the name.

`docs/scores/RegimeScore.md` §5 (the composite) and §5.1 (the binding
prerequisite order), workstream `docs/scores/IMPLEMENTATION_PLAN.md` §5.3. **Path
C is canonical** (owner decision Q1, 2026-09-17): market-level inputs reusing
Path B's four-axis vocabulary - never the analysed ticker's own closes, which
would make this "a second `TechnicalScore` under a different name"
(`RegimeScore.md` §5.2).

Six rules this module exists to hold:

1. **Market-level, not name-level.** Every component is computed over the
   benchmark / the market panel / a volatility index. `get_regime_read` reads the
   analysed ticker's own closes, so it measures the name; `market_trend` below is
   the prerequisite-1 producer that measures the benchmark instead, and the
   name-level read is echoed by `regime_paths` as its own, differently-named
   value - never averaged into this one (`RegimeScore.md` §5.1).
2. **One producer per component, named.** Every row of ``COMPONENTS`` carries
   `module.function:line`; where a producer does not exist yet the smallest
   honest one lives here (`market_trend`, `vix_term_structure`) and its
   remaining gap is stated rather than proxied.
3. **`NA` is not `0`** (master rule 1): an absent component or an unmeasurable
   one leaves the denominator with its reason, and the composite is withheld
   below its floor - never `0`, never a neutral `50`.
4. **Its own band table** (`REGIME_BANDS`), advisory. Nothing here reads
   `decision_guardrail.SCORE_BANDS` (master rule 2).
5. **No invented coefficients.** No per-component weight vector is published, so
   the default is equal weight and the basis PRINTS that fact, together with the
   consequence (three of the six legs are volatility legs, so an equal vector
   gives volatility 50% where the owner's category table gives it 20%).
6. **Never a gate, never a size, never a direction.** The module imports nothing
   on the sizing path and asserts no direction for a name; its bands describe the
   environment. `regime_paths` echoes Path A's `position_scale` and never
   multiplies anything by it.

**The two regime paths stay two.** `get_regime_read` (Path A: one label) and
`get_regime_state` (Path B: four axes) share a word and no inputs, so they
disagree for the same name on the same day (`RegimeScore.md` §0.1). `regime_paths`
prints both under their own names with a `disagree` flag and **no reconciliation
of any kind** - the failure mode §6.3 requires a test to prevent.
"""

from __future__ import annotations

from typing import NamedTuple

from .score_engine import align, band_label, combine

# --- The owner's published table (RegimeScore.md §0.2) ---------------------
#
# The record, verbatim. It is a CATEGORY table, so it is not the weight vector
# this engine uses: no per-component vector is published, and inventing a
# within-category split would fabricate a coefficient (master rule 6). It is
# printed in the basis so a reader can see exactly how much of the owner's table
# the component set below touches.

OWNER_CATEGORY_WEIGHTS: dict[str, float] = {
    "market_trend": 20.0,
    "volatility": 20.0,
    "market_momentum": 15.0,
    "breadth": 15.0,
    "choppiness": 10.0,
    "sector_rotation": 10.0,
    "macro_credit": 5.0,
    "event_regime": 5.0,
}

#: The owner categories the component set below actually measures. The rest are
#: named in the basis as absent, so coverage cannot be read as "the whole
#: environment was measured".
MEASURED_CATEGORIES: tuple = (
    "market_trend",
    "volatility",
    "breadth",
    "choppiness",
)

#: `event_regime` is in the published table but the plan removed it from this
#: engine (RegimeScore.md §7 Q2, 2026-09-17): the same catalyst feeds
#: `EventScore`, and RegimeScore describes the environment while EventScore
#: describes the catalyst - a second 5% factor would double-count one catalyst.
EVENT_CATEGORY_MOVED_TO = "EventScore"

# --- The ramps -------------------------------------------------------------
#
# ``(lo, hi)`` -> 0..100 in the FAVOURABLE direction (inverted for
# ``lower_better``). Every edge is a hypothesis, collected here so Phase C has one
# thing to move and the basis can name it; none is a published constant, and the
# printed basis says so (``RAMP_BASIS``).

RAMPS: dict[str, tuple[float, float]] = {
    # benchmark P/SMA - 1, signed (regime.trend_strength's quantity)
    "market_trend": (-0.10, 0.10),
    "breadth": (20.0, 80.0),  # percent of the panel above its 50d SMA
    "vix_percentile": (0.10, 0.90),  # 0-1 rank of the VIX level
    "vix_term_structure": (0.85, 1.15),  # VIX9D / VIX3M (inverted = stress)
    "choppiness": (20.0, 65.0),  # canonical CHOP, 0-100, high = ranging
    "realized_vol_percentile": (0.10, 0.90),  # 0-1 rank of realized vol
}

RAMP_BASIS = (
    "ramp edges are this engine's declared policy (no published coefficients); "
    "Phase C measures them against realised forward returns"
)

#: Bars below which a market-level trend is not asserted. The regime label's own
#: floor (`analysis_tools.get_regime_read`) is 60.
MIN_BARS = 60

#: The composite's floor, capped at the component set's own size.
COMPOSITE_MIN_COVERAGE = 3

# This engine's own advisory bands - never `decision_guardrail.SCORE_BANDS`.
# Environmental words only: a regime band is not a rating and not a direction
# (`RegimeScore.md` §5.4, §6.5).
REGIME_BANDS: tuple = (
    (80.0, "benign"),
    (60.0, "constructive"),
    (40.0, "mixed"),
    (20.0, "stressed"),
    (0.0, "hostile"),
)

#: A deterministic diagnostic (the producers below).
STATUS_ADVISORY = "ADVISORY"
#: An unvalidated combination (the composite: declared ramps, equal weights, no
#: Phase C measurement yet).
STATUS_RESEARCH_ONLY = "RESEARCH_ONLY"


class Component(NamedTuple):
    """One component: its category, its direction, its producer, its unit."""

    name: str
    category: str
    direction: str
    producer: str
    unit: str
    note: str = ""


def _c(name, category, direction, producer, unit, note=""):
    return Component(name, category, direction, producer, unit, note)


# --- The component map, in the plan's binding prerequisite order -----------
#
# `RegimeScore.md` §5.1 / plan §5.3: (1) market-level trend, (2) market-wide
# breadth, (3) VIX percentile, (4) VIX term structure, then the chop unit and
# only then the score. The declared order is that order, with the realised-vol
# percentile beside the VIX legs because it answers the same category question
# from the other side (own history vs the index).
#
# Producers that do not exist yet are named where they live and their gap is
# stated. The equity-IV term structure (`options_surface.term_structure_slope`)
# is NOT a substitute for the VIX term structure and is never fed in as one
# (RegimeScore.md §4) - the two are the same arithmetic over different inputs,
# and only the VIX9D/VIX3M inputs are a regime read.

COMPONENTS: dict[str, Component] = {
    c.name: c
    for c in (
        _c(
            "market_trend",
            "market_trend",
            "higher_better",
            "strategies/regime_score.py::market_trend:344",
            "P/SMA - 1 (signed)",
            "prerequisite 1; over the benchmark's closes, not the name's",
        ),
        _c(
            "breadth",
            "breadth",
            "higher_better",
            "strategies/market_breadth.py::market_breadth:114",
            "percent above the 50d SMA, 0-100",
            "prerequisite 2 (P0-3); the leaf passes pct_above_50d",
        ),
        _c(
            "vix_percentile",
            "volatility",
            "lower_better",
            "agents/utils/analysis_tools.py::_vix_percentile_read:7976",
            "0-1 rank of VIXCLS",
            "prerequisite 3 (P0-4); a level is not a regime input, the rank is",
        ),
        _c(
            "vix_term_structure",
            "volatility",
            "lower_better",
            "strategies/regime_score.py::vix_term_structure:401",
            "VIX9D / VIX3M ratio",
            "prerequisite 4 (P0-5); ABSENT data source - see VIX9D_SERIES",
        ),
        _c(
            "choppiness",
            "choppiness",
            "lower_better",
            "strategies/regime.py::choppiness:141",
            "canonical CHOP 0-100 (one unit, both branches)",
            "high = ranging; the producer returns None when unmeasurable",
        ),
        _c(
            "realized_vol_percentile",
            "volatility",
            "lower_better",
            "strategies/regime.py::vol_percentile:59",
            "0-1 rank of realised vol",
            "the defect fix: None when unmeasurable, never a fabricated 0.5",
        ),
    )
}

COMPONENT_ORDER: tuple = tuple(COMPONENTS)

#: The VIX9D FRED series id is NOT asserted here: `dataflows/fred.py` passes an
#: unknown alias through as a raw series id and returns None when the id does not
#: resolve, so the run-time id must be verified against FRED before it is wired
#: (see `local://wiring_regime.md`). Until then the leg is `NA` and printed,
#: never substituted with the equity-IV slope (`RegimeScore.md` §4).
VIX9D_SERIES = None
VIX3M_SERIES = "VXVCLS"
VIX_TERM_UNAVAILABLE = (
    "VIX9D/VIX3M term structure has no verified series source in this tree "
    "(RegimeScore.md §4: P0-5 ABSENT); the equity-IV slope is not a substitute"
)


def align_components(components: dict) -> dict[str, float | None]:
    """``{component: raw}`` -> ``{component: 0-100 favourable | None}``.

    An unknown key is ignored (the engine scores what it declares); a declared
    component with no value - absent, ``None``, non-finite, or a bool where a
    measurement is declared - is ``None`` and leaves the denominator. R3's leg
    takes the flagged read and aligns its FLAG (:func:`_spectral_flag`), never
    the functional it was read from. Never a neutral 50 (master rule 1).
    """
    values = components or {}
    declared, ramps = _declared_set()
    out: dict[str, float | None] = {}
    for name, comp in declared.items():
        raw = values.get(name)
        raw = _spectral_flag(raw) if name == SPECTRAL_CHANGE_KEY else raw
        lo, hi = ramps[name]
        out[name] = align(raw, direction=comp.direction, lo=lo, hi=hi)
    return out


def _composite_floor() -> int:
    """The composite floor, capped at the component set's own size.

    An uncapped count floor is an off switch wearing a floor's name (the WP-2
    FGS lesson): a set smaller than the floor could never score.
    """
    return max(1, min(int(COMPOSITE_MIN_COVERAGE), len(_declared_set()[0])))


def regime_score(components: dict, *, weights: dict | None = None, panel: dict | None = None) -> dict:
    """The 0-100 market-environment score over the declared components.

    ``components`` is ``{component: raw value}`` over the declared set: the six
    market-level legs plus R3's gated spectral read. Absent is ``NA``, never 0.

    ``weights`` overrides the default vector. ``None`` means **equal weight**,
    because no per-component weight vector is published - the owner's table is at
    category level and splitting it inside a category would fabricate a
    coefficient (master rule 6). The basis prints both facts and the distortion
    the equal vector implies. ``panel`` is R5's cross-section, PRINTED only.

    Returns ``{"score", "coverage", "components", "aligned", "measured",
    "absent", "band", "status", "withheld", "weights", "owner_categories",
    "basis"}``, plus ``"printed"`` (R5, gate on). ``status`` is ``RESEARCH_ONLY``:
    the ramps are declared policy and the combination is unvalidated.
    """
    declared = _declared_set()[0]
    aligned = align_components(components)
    floor = _composite_floor()
    combined = combine(
        aligned, weights=weights, min_coverage=floor, bands=REGIME_BANDS
    )
    measured = [name for name in declared if aligned.get(name) is not None]
    absent = [name for name in declared if aligned.get(name) is None]

    if weights is None:
        weight_basis = (
            "no per-component weight vector is published, equal weights used"
        )
    else:
        weight_basis = "supplied weights " + ", ".join(
            f"{k}={float(v):g}" for k, v in sorted(weights.items())
        )
    owner_absent = [k for k in OWNER_CATEGORY_WEIGHTS if k not in MEASURED_CATEGORIES]
    owner_txt = ", ".join(f"{k} {v:g}" for k, v in OWNER_CATEGORY_WEIGHTS.items())
    basis = " | ".join(
        [
            f"RegimeScore (RESEARCH_ONLY): {len(measured)} of {len(declared)} "
            f"declared component(s) measured, coverage {combined.get('coverage')}, "
            f"floor {floor}",
            weight_basis,
            "the owner's published table is at CATEGORY level and is not used as a "
            f"per-component vector ({owner_txt}); this component set measures "
            f"{len(MEASURED_CATEGORIES)} of its {len(OWNER_CATEGORY_WEIGHTS)} "
            f"categories ({', '.join(MEASURED_CATEGORIES)}); not measured here: "
            f"{', '.join(owner_absent)}",
            _volatility_note(declared),
            RAMP_BASIS,
            f"absent (NA, never 0): {', '.join(absent)}" if absent else "no component absent",
            "advisory environment read: never a gate, never a size, never a direction",
        ]
    )
    return _attach_printed_reads({
        "score": combined.get("score"),
        "coverage": combined.get("coverage"),
        "floor": combined.get("floor"),
        "components": {
            name: {
                "raw": (components or {}).get(name),
                "aligned": aligned.get(name),
                "direction": declared[name].direction,
                "category": declared[name].category,
                "producer": declared[name].producer,
                "unit": declared[name].unit,
                "note": declared[name].note,
            }
            for name in declared
        },
        "aligned": aligned,
        "measured": measured,
        "absent": absent,
        "band": band_label(combined.get("score"), REGIME_BANDS),
        "status": STATUS_RESEARCH_ONLY,
        "withheld": combined.get("withheld"),
        "weights": dict(weights) if weights is not None else None,
        "owner_categories": {
            "measured": list(MEASURED_CATEGORIES),
            "absent": owner_absent,
            "published": dict(OWNER_CATEGORY_WEIGHTS),
            "event_category_moved_to": EVENT_CATEGORY_MOVED_TO,
        },
        "basis": basis,
    }, panel)


def market_trend(benchmark_closes: list) -> dict:
    """The BENCHMARK's own trend - prerequisite 1 of `RegimeScore.md` §5.1.

    `analysis_tools.get_regime_read:964` reads the ANALYSED TICKER's closes, so
    it measures the name, not the environment; a `RegimeScore` built from that
    would be a second `TechnicalScore` under a different name (§5.2). This reads
    the benchmark's closes instead: `analysis_tools._benchmark_closes:302`
    (config ``benchmark_ticker``, default SPY) is the run-time source and the leaf
    passes its series here.

    Returns ``{"trend": P/SMA - 1 signed | None, "above_sma": bool | None,
    "sma": float | None, "sma_window": int, "n": int, "status", "basis",
    "withheld": reason | None}``. The value is `regime.trend_strength:121`'s
    quantity computed over the benchmark (one implementation); below `MIN_BARS`
    closes it is ``None`` with the reason - never ``0.0`` (master rule 1). The
    basis prints the SMA window actually used, because a short benchmark history
    shortens it (`trend_strength` falls back to the whole series) and a reader
    must not quote a 200-day read that was not one.
    """
    from .regime import trend_strength

    closes = [c for c in (benchmark_closes or []) if c is not None]
    n = len(closes)
    if n < MIN_BARS:
        return {
            "trend": None,
            "above_sma": None,
            "sma": None,
            "sma_window": None,
            "n": n,
            "status": STATUS_ADVISORY,
            "withheld": f"{n} benchmark bar(s), {MIN_BARS} needed for a trend read",
            "basis": f"market trend unmeasurable: {n} benchmark bar(s), needs {MIN_BARS}",
        }
    # The same window convention the name-level regime leaf uses: 200 bars when
    # the history carries them, half the series below that (and the basis prints
    # which one was used, so a short benchmark history is not quoted as a 200-day
    # read).
    window = 200 if n > 200 else min(200, max(2, n // 2))
    trend = trend_strength([float(c) for c in closes], sma_window=window)
    sma = sum(float(c) for c in closes[-window:]) / window
    above = bool(float(closes[-1]) >= sma)
    return {
        "trend": trend,
        "above_sma": above,
        "sma": sma,
        "sma_window": window,
        "n": n,
        "status": STATUS_ADVISORY,
        "withheld": None,
        "basis": (
            f"benchmark trend {trend:+.4f} = P/SMA{window} - 1 over {n} bar(s) "
            f"(regime.trend_strength); the benchmark, not the analysed name"
        ),
    }


def vix_term_structure(vix9d: float | None, vix3m: float | None) -> dict:
    """The VIX9D / VIX3M term structure - P0-5's smallest honest producer.

    `RegimeScore.md` §4 marks this ABSENT and states the trap: the equity-IV
    slope (`options_surface.term_structure_slope:152`) is **not** a substitute, so
    this takes the two volatility-INDEX levels and derives both reads from them.
    It cannot silently accept an equity surface, because an equity surface is not
    a pair of VIX levels.

    Returns ``{"slope": vix3m - vix9d (index points), "ratio": vix9d / vix3m,
    "inverted": bool | None, "n": 0|2, "status", "basis", "withheld"}``. The
    slope uses `term_structure_slope:152` (one implementation). The SCORE aligns
    on the scale-free ratio, because a point spread is not comparable across
    volatility levels. Either input unreadable -> both reads ``None`` with the
    reason, never a fabricated 0 (master rule 1); `VIX9D_SERIES` is ``None``
    until a series id is verified, so in this tree the leg is normally NA.
    """
    from .options_surface import term_structure_slope

    if vix9d is None or vix3m is None or not vix3m:
        return {
            "slope": None,
            "ratio": None,
            "inverted": None,
            "n": 0,
            "status": STATUS_ADVISORY,
            "withheld": "VIX9D and VIX3M both needed to measure the term structure",
            "basis": VIX_TERM_UNAVAILABLE,
        }
    slope = term_structure_slope(float(vix9d), float(vix3m))
    ratio = float(vix9d) / float(vix3m)
    return {
        "slope": slope,
        "ratio": ratio,
        "inverted": bool(slope is not None and slope < 0.0),
        "n": 2,
        "status": STATUS_ADVISORY,
        "withheld": None,
        "basis": (
            f"VIX9D {float(vix9d):.2f} / VIX3M {float(vix3m):.2f} = {ratio:.3f} "
            f"(slope {slope:+.2f} index points, "
            f"{'inverted' if slope < 0 else 'contango'}); a LEVEL pair, not the "
            f"equity-IV slope"
        ),
    }


# --- R3: the flagged spectral read (2607.06373) ----------------------------
#
# A spectrum estimated from a finite window moves on its own, so this engine
# declares a cross-sectional structural change only when the movement exceeds the
# calibrated first-order null band `regime.spectral_change_read` reports. What
# enters the score is that read's FLAG - never the absorption ratio, never the
# projector distance - and `align_components` takes the flag out of the record,
# so a raw functional cannot reach the score even by accident.
#
# The component is declared only while its gate is on, because the declared set
# is what the coverage denominator counts: with the gate off (the default) this
# engine measures exactly the six market-level legs it measured before, and a
# gate-off run is byte-identical.

#: R3's component: the flagged spectral read. Its unit is the flag, and its
#: declared input is the read rather than a number (see :func:`_spectral_flag`).
SPECTRAL_CHANGE_COMPONENT = Component(
    name="spectral_change",
    category="breadth",
    direction="lower_better",
    producer="strategies/regime.py::spectral_change_read:1159",
    unit="flag: 1 = a spectral move beyond the calibrated null band",
    note=(
        "R3 (2607.06373); the FLAG enters, never the absorption ratio or the "
        "projector distance it was read from"
    ),
)

#: The key a caller passes for R3's read.
SPECTRAL_CHANGE_KEY = SPECTRAL_CHANGE_COMPONENT.name

#: R3's ramp: the flag is 0 (no move beyond the band) or 1 (a move beyond it).
#: Declared policy like every other edge here - no published coefficient exists.
SPECTRAL_CHANGE_RAMP: tuple[float, float] = (0.0, 1.0)


def _spectral_gate() -> bool:
    """Is R3's spectral null-band read switched on? (``enable_spectral_null_band``)

    The component below is only *declared* while the gate is on. Off by default,
    and an unreadable config leaves it off - a config read must never break the
    score it guards.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_spectral_null_band", False))


def _declared_set() -> tuple[dict, dict]:
    """The declared component table and its ramps, for the R3 gate's state.

    ``(COMPONENTS, RAMPS)`` with the gate off (the module's own tables, no copy,
    so a gate-off score reads exactly the six legs it read before), plus R3's
    spectral leg while ``enable_spectral_null_band`` is on.
    """
    if _spectral_gate():
        return (
            {**COMPONENTS, SPECTRAL_CHANGE_KEY: SPECTRAL_CHANGE_COMPONENT},
            {**RAMPS, SPECTRAL_CHANGE_KEY: SPECTRAL_CHANGE_RAMP},
        )
    return COMPONENTS, RAMPS


def _volatility_note(declared: dict) -> str:
    """The equal vector's real distortion, over the DECLARED set.

    Three of the six market-level legs are volatility legs; R3's leg is not, and
    the equal vector is over the declared set, so the count has to travel with
    the table rather than being frozen into the sentence.
    """
    legs = sum(1 for comp in declared.values() if comp.category == "volatility")
    return (
        f"{legs} of the {len(declared)} components are volatility-regime legs, so "
        f"an equal vector gives volatility {100.0 * legs / len(declared):g}% where "
        "the owner's table gives it 20% - stated, not hidden"
    )


def _spectral_flag(raw):
    """The FLAG out of R3's read - never the functional the flag was read from.

    The declared input for this component is the flagged READ
    (``regime.spectral_change_read``) or the bare flag (``0.0`` / ``1.0``).
    Anything else - the absorption ratio, the projector distance, a value on any
    other scale - is ``None``, so a raw functional cannot enter the score even by
    accident (R3's item 3).
    """
    if isinstance(raw, dict):
        flag = raw.get("flag")
        return None if flag is None else (1.0 if flag else 0.0)
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    if isinstance(raw, (int, float)) and float(raw) in (0.0, 1.0):
        return float(raw)
    return None


def _spectral_change_values(
    prev_window: dict, curr_window: dict, *, cfg: dict | None = None
) -> dict:
    """R3's flagged read as the ``{component: value}`` mapping `regime_score` takes.

    The leaf supplies the two rolling windows of the tracked cross-section - a
    per-PANEL read, never per-symbol. The gate is read inside
    :func:`regime.spectral_change_read`, so with it off (the default) this
    returns ``{}`` and the component is not declared at all; with a panel too thin
    to read, the read reports ``unavailable`` with its window and the component
    stays `NA` rather than entering the score as a zero.

    The value handed back is the FLAG (``1.0`` / ``0.0``). `align_components`
    also accepts the read itself and takes the flag out of it, which is what keeps
    the absorption ratio and the projector distance out of the score.
    """
    from .regime import spectral_change_read

    read = spectral_change_read(prev_window, curr_window, cfg=cfg)
    if read is None or read.get("flag") is None:
        return {}
    return {SPECTRAL_CHANGE_KEY: 1.0 if read["flag"] else 0.0}


# --- R5: the forward-stress read (PRINTED, never scored) -------------------
#
# R5's probability is a cross-SECTION read with a stated horizon, and it is
# IN-SAMPLE calibrated: the number and the evidence behind it are one object. It
# is PRINTED beside the score and never scored BY it - an environment band is not
# a probability, and no per-component weight vector exists to score a seventh leg
# - so it never enters the declared/scored set and the coverage denominator and
# every pinned count over the component table are untouched. The block is added
# only while `enable_forward_stress_probability` is on: with the gate off (the
# default) the returned dict is byte-identical to the run before the read existed.

#: The key R5's read is printed under.
FORWARD_STRESS_KEY = "forward_stress_probability"

#: The key X3's panel spectrum is printed under.
MP_SPECTRUM_KEY = "mp_lower_spectrum"


def _forward_stress_gate() -> bool:
    """Is R5's forward-stress read switched on?
    (``enable_forward_stress_probability``)

    The key is read by its literal name so the gate registry's read-site scan
    finds it. Off by default, and an unreadable config leaves it off - a config
    read must never break the score it guards.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_forward_stress_probability", False))


def _forward_stress_printed(panel, *, cfg: dict | None = None) -> dict:
    """R5's read for the PRINTED block - the ONE producer, never a second one.

    Deferred import: the producer lives in ``market_breadth`` and reads its own
    gate, so a gate-off caller gets the producer's refusal (with its reason)
    rather than an empty block. Printing it here is what makes R5 reachable from
    this engine without adding a scored leg.
    """
    from .market_breadth import forward_stress_probability

    return forward_stress_probability(panel or {}, cfg=cfg)


def _spectrum_gate() -> bool:
    """Is X3's panel-spectrum read switched on? (``enable_mp_lower_spectrum``)

    Same discipline as R5's: the key is read by its literal name so the gate
    registry's read-site scan finds it, and an unreadable config leaves it OFF
    rather than breaking the score it is printed beside.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_mp_lower_spectrum", False))


def _spectrum_printed(panel, *, cfg: dict | None = None) -> dict | None:
    """X3's read for the PRINTED block - the ONE producer, never a second one.

    ``sector_breadth.mp_lower_spectrum`` reads its own gate and returns ``None``
    when it is off, so this returns ``None`` in exactly that case rather than an
    empty block. The read is per PANEL (one correlation matrix for the whole
    cross-section), which is why it is printed here and never scored: a collapse
    in the effective number of independent bets is a backdrop, not a 0-100 leg.
    """
    from .sector_breadth import mp_lower_spectrum

    return mp_lower_spectrum(panel or {}, cfg=cfg)


def _attach_printed_reads(result: dict, panel) -> dict:
    """The gated PRINTED blocks, attached only while their own gate is on.

    With every gate off (the default) the dict is returned untouched, so a
    gate-off run prints exactly the keys it printed before these reads existed.
    Each read attaches under its own key: X3's arrival must not displace R5's.
    """
    printed: dict = {}
    if _forward_stress_gate():
        printed[FORWARD_STRESS_KEY] = _forward_stress_printed(panel)
    if _spectrum_gate():
        spectrum = _spectrum_printed(panel)
        if spectrum is not None:
            printed[MP_SPECTRUM_KEY] = spectrum
    if printed:
        result["printed"] = printed
    return result


# --- The two regime paths --------------------------------------------------

PATH_A_NAME = "get_regime_read"
PATH_B_NAME = "get_regime_state"

#: Path B's four axes (`regime_state.regime_state:215` -> ``labels``).
AXIS_KEYS: tuple = ("trend", "volatility", "relative", "drawdown")

_TREND_UP = frozenset({"STRONG_BULL", "BULL"})
_TREND_DOWN = frozenset({"BEAR", "STRONG_BEAR"})
_TREND_STRONG = _TREND_UP | _TREND_DOWN
_VOL_CALM = frozenset({"LOW"})


def _axis_labels(state_axes: dict) -> dict[str, str | None]:
    """Path B's four axis labels, from ``labels`` or the axis dicts themselves."""
    src = state_axes or {}
    labels = src.get("labels")
    out: dict[str, str | None] = {}
    for key in AXIS_KEYS:
        value = None
        if isinstance(labels, dict):
            value = labels.get(key)
        if value is None:
            entry = src.get(key)
            value = entry.get("label") if isinstance(entry, dict) else entry
        out[key] = str(value) if value is not None else None
    return out


def _label_read_label(label_read: dict) -> str | None:
    """Path A's single label (``overlays.build_strategy_overlays``), or None."""
    src = label_read or {}
    for key in ("regime", "label"):
        value = src.get(key)
        if value is not None:
            return str(value)
    return None


def _disagreement(label, axes: dict, crash) -> tuple[bool | None, str]:
    """This module's declared disagreement rule: NOTHING is reconciled.

    Two shapes, both named in the reason so the flag cannot be read as a verdict:
    a **contradiction** (the two reads assert opposite things about the same
    concept) and a **resolution disagreement** (Path A claims no direction while
    Path B names a strong state). ``None`` when either read is unreadable - a
    disagreement between an unmeasured read and a measured one is not measurable,
    and `None` is not `False` (master rule 1).
    """
    if label is None:
        return None, f"not comparable: {PATH_A_NAME} reported no label"
    if all(v is None for v in axes.values()):
        return None, f"not comparable: {PATH_B_NAME} reported no axis"
    trend = axes.get("trend")
    vol = axes.get("volatility")
    if label == "bull" and trend in _TREND_DOWN:
        return True, (
            f"contradiction: {PATH_A_NAME} labels bull while {PATH_B_NAME}'s "
            f"trend axis is {trend}"
        )
    if label == "bear" and trend in _TREND_UP:
        return True, (
            f"contradiction: {PATH_A_NAME} labels bear while {PATH_B_NAME}'s "
            f"trend axis is {trend}"
        )
    if label == "high_vol" and vol in _VOL_CALM:
        return True, (
            f"contradiction: {PATH_A_NAME} labels high_vol while {PATH_B_NAME}'s "
            f"volatility axis is {vol}"
        )
    if crash and label == "bull":
        return True, (
            f"contradiction: {PATH_A_NAME} labels bull while {PATH_B_NAME} "
            f"raises its crash flag"
        )
    if label == "neutral" and trend in _TREND_STRONG:
        return True, (
            f"resolution disagreement: {PATH_A_NAME} claims no direction "
            f"(neutral) while {PATH_B_NAME} names a strong trend ({trend}) - "
            f"neither read is reconciled"
        )
    return False, (
        f"no contradiction on the shared concepts: {PATH_A_NAME} label {label}, "
        f"{PATH_B_NAME} trend {trend or 'n/a'} / volatility {vol or 'n/a'}"
    )


def regime_paths(label_read: dict, state_axes: dict) -> dict:
    """Path A and Path B, printed side by side and NEVER reconciled.

    `RegimeScore.md` §0.1: `get_regime_read` (Path A - one label from the
    analysed ticker's own closes) and `get_regime_state` (Path B - four axes from
    closes + benchmark) share a word, no inputs, no scales and no vocabulary, so
    they can disagree for the same name on the same day. §6.3 requires the
    disagreement to be TESTED, not merged, and the failure mode to prevent is
    silent reconciliation.

    So this output is an echo with a flag, nothing more: each read keeps its own
    name and its own value, there is no merged label, no average and no
    precedence, and `disagree` is this module's declared rule
    (:func:`_disagreement`) with its reason printed. Path A's `position_scale` is
    echoed and used for nothing - the score is not a size and the size is not a
    score (`RegimeScore.md` §5.4).

    Returns ``{"disagree", "disagree_reason", "path_a", "path_b", "basis"}``.
    ``disagree`` is ``None`` when either read is unreadable.
    """
    label = _label_read_label(label_read)
    axes = _axis_labels(state_axes)
    src_b = state_axes or {}
    crash = src_b.get("crash")
    disagree, reason = _disagreement(label, axes, crash)
    return {
        "disagree": disagree,
        "disagree_reason": reason,
        "path_a": {
            "name": PATH_A_NAME,
            "label": label,
            "position_scale": (label_read or {}).get("position_scale"),
            "momentum60": (label_read or {}).get("momentum60"),
            "high_distance": (label_read or {}).get("high_distance"),
            "read": dict(label_read or {}),
        },
        "path_b": {
            "name": PATH_B_NAME,
            "trend": axes["trend"],
            "volatility": axes["volatility"],
            "relative": axes["relative"],
            "drawdown": axes["drawdown"],
            "axes": dict(axes),
            "crash": crash,
            "factor": src_b.get("factor"),
            "read": dict(src_b),
        },
        "basis": (
            f"two regime paths, two names, no reconciliation: {PATH_A_NAME} "
            f"(one label, the analysed ticker's own closes) and {PATH_B_NAME} "
            f"(four axes, closes + benchmark) share no inputs and no vocabulary "
            f"(RegimeScore.md §0.1); each value is echoed as its own read, and "
            f"nothing here is merged, averaged or given precedence; "
            f"position_scale is echoed and used for nothing; disagree={disagree} "
            f"({reason})"
        ),
    }


__all__ = [
    "OWNER_CATEGORY_WEIGHTS",
    "MEASURED_CATEGORIES",
    "EVENT_CATEGORY_MOVED_TO",
    "RAMPS",
    "RAMP_BASIS",
    "MIN_BARS",
    "COMPOSITE_MIN_COVERAGE",
    "REGIME_BANDS",
    "STATUS_ADVISORY",
    "STATUS_RESEARCH_ONLY",
    "Component",
    "COMPONENTS",
    "COMPONENT_ORDER",
    "VIX9D_SERIES",
    "VIX3M_SERIES",
    "VIX_TERM_UNAVAILABLE",
    "SPECTRAL_CHANGE_COMPONENT",
    "SPECTRAL_CHANGE_KEY",
    "SPECTRAL_CHANGE_RAMP",
    "FORWARD_STRESS_KEY",
    "MP_SPECTRUM_KEY",
    "PATH_A_NAME",
    "PATH_B_NAME",
    "AXIS_KEYS",
    "align_components",
    "regime_score",
    "market_trend",
    "vix_term_structure",
    "regime_paths",
]
