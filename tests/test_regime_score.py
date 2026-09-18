"""`RegimeScore` (WP-4) - the plan's acceptance list, clause by clause.

Covers `docs/scores/IMPLEMENTATION_PLAN.md` §5.3 and `docs/scores/RegimeScore.md`
§6: (a) the label moves when the trend moves - with ``vol_pct == 0.5``, a strong
positive and a strong negative trend must not produce the same label; (b) a regime
score with no market data returns ``None``, never a neutral 50; (c) the score
never appears in a directional field; (d) the sizing scale is not an input to the
score and vice versa. Plus the producer table (one producer per component, in the
plan's prerequisite order), the two-path disagreement output (§6.3) and the
``regime.vol_percentile`` defect fix (§5.2/§5.3).

Offline and deterministic: every value is synthetic, no vendor call.
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path

import pytest

from tradingagents.strategies import regime as regime_mod
from tradingagents.strategies.regime import (
    choppiness,
    regime_label,
    vol_percentile,
    vol_percentile_read,
)
from tradingagents.strategies.regime_score import (
    AXIS_KEYS,
    COMPONENTS,
    COMPONENT_ORDER,
    COMPOSITE_MIN_COVERAGE,
    MEASURED_CATEGORIES,
    MIN_BARS,
    OWNER_CATEGORY_WEIGHTS,
    PATH_A_NAME,
    PATH_B_NAME,
    RAMPS,
    REGIME_BANDS,
    STATUS_ADVISORY,
    STATUS_RESEARCH_ONLY,
    align_components,
    market_trend,
    regime_paths,
    regime_score,
    vix_term_structure,
)

# The favourable / unfavourable end of every component, read from the producer's
# own unit (RAMPS' edges ARE those ends). A table that inverts one of these is the
# single biggest correctness risk this engine has.
COMPONENT_ENDS: dict[str, tuple[float, float]] = {
    "market_trend": (0.08, -0.08),          # P/SMA - 1, signed
    "breadth": (70.0, 30.0),                # percent above the 50d SMA
    "vix_percentile": (0.20, 0.80),         # lower rank = calmer = favourable
    "vix_term_structure": (0.90, 1.10),     # ratio < 1 = contango = favourable
    "choppiness": (25.0, 60.0),             # low CHOP = trending = favourable
    "realized_vol_percentile": (0.20, 0.80),
}


def _mid_values() -> dict:
    """Every component measurable, none extreme: score 71.67, coverage 1.0."""
    return {
        "market_trend": 0.06,
        "breadth": 60.0,
        "vix_percentile": 0.30,
        "vix_term_structure": 0.95,
        "choppiness": 35.0,
        "realized_vol_percentile": 0.30,
    }


def _series(n: int, *, step: float, base: float = 100.0) -> list[float]:
    """A smooth synthetic close series (no vendor call)."""
    out = [base]
    for _ in range(n - 1):
        out.append(out[-1] * (1.0 + step))
    return out


def _noisy(n: int, *, sigma: float, seed: int = 7) -> list[float]:
    """A noisy synthetic close series with a chosen amplitude. Deterministic:
    the seed is fixed, so the realized-vol ranking is reproducible."""
    rng = random.Random(seed)
    out = [100.0]
    for _ in range(n - 1):
        out.append(out[-1] * (1.0 + rng.gauss(0.0, sigma)))
    return out


def _wobbly(n: int = 120) -> list[float]:
    """A noisy series, so the close-only choppiness leg has something to read."""
    out = [100.0]
    for i in range(n - 1):
        out.append(out[-1] * (1.0 + (0.004 if i % 2 else -0.003)))
    return out


# --------------------------------------------------------------------------
# (a) the label moves when the trend moves (the defect-1 regression)
# --------------------------------------------------------------------------


def test_the_label_moves_when_the_trend_moves() -> None:
    """With ``vol_pct == 0.5`` the two trend signs must not give one label.

    `RegimeScore.md` §6.1 - the regression for defect 1: the choppiness branch was
    unreachable from the overlay path, so a mid-volatility tape was ``neutral``
    regardless of trend. The measured chop is what lets the trend leg speak.
    """
    up = regime_label(0.5, 0.10, 10.0)
    down = regime_label(0.5, -0.10, 10.0)
    assert up != down
    assert (up, down) == ("bull", "bear")


def test_the_trend_moves_through_the_real_overlay_path_at_vol_pct_half() -> None:
    """The same clause through `overlays.build_strategy_overlays`, whose own
    volatile leg pins ``vol_pct`` at 0.5 for every 60-251-bar history."""
    from tradingagents.strategies.overlays import build_strategy_overlays

    cfg = {"enable_strategy_overlays": True, "volatility_estimator": "close"}
    up = build_strategy_overlays(cfg, _series(120, step=0.004))
    down = build_strategy_overlays(cfg, _series(120, step=-0.004))
    assert up is not None and down is not None
    assert up["regime"] == "bull" and down["regime"] == "bear"


def test_a_ranging_tape_does_not_assert_a_trend() -> None:
    """The chop leg still vetoes: a strong price/SMA ratio inside a choppy tape
    is exactly the false-trend read it exists to prevent."""
    assert regime_label(0.5, 0.10, 70.0) == "neutral"
    assert regime_label(0.5, 0.10, None) == "neutral"


def test_an_unmeasured_volatility_percentile_is_not_asserted() -> None:
    """The defect fix, at the label: ``None`` means "not measured", so the
    volatility leg is skipped rather than the label raising or inventing a state."""
    assert regime_label(None, 0.10, 10.0) == "bull"
    assert regime_label(None, -0.10, 10.0) == "bear"
    assert regime_label(None, 0.0, 70.0) == "neutral"


def test_choppiness_is_one_unit_for_both_callers() -> None:
    """`RegimeScore.md` §6.2: the value the label compares is on the producer's
    own 0-100 scale, whatever history it was given."""
    ohlc = choppiness(
        _wobbly(), highs=_wobbly(), lows=_wobbly(), window=14
    )
    assert ohlc is None or 0.0 <= ohlc <= 100.0
    assert choppiness(_series(60, step=0.004), window=14) is not None
    assert choppiness([1.0, 2.0], window=14) is None


# --------------------------------------------------------------------------
# (b) no market data returns None, never a neutral 50
# --------------------------------------------------------------------------


def test_a_regime_score_with_no_market_data_returns_none_never_a_neutral_fifty() -> None:
    for empty in ({}, None, dict.fromkeys(COMPONENT_ORDER)):
        res = regime_score(empty)
        assert res["score"] is None, empty
        assert res["coverage"] == 0.0
        assert res["band"] is None
        assert res["withheld"] and "floor" in res["withheld"]
        assert res["status"] == STATUS_RESEARCH_ONLY


def test_one_component_alone_is_withheld() -> None:
    res = regime_score({"market_trend": 0.06})
    assert res["score"] is None
    assert res["measured"] == ["market_trend"]
    assert res["withheld"] == "1 of 6 components present, floor is 3"
    assert res["components"]["market_trend"]["aligned"] == pytest.approx(80.0)


def test_the_floor_is_tested_from_both_sides() -> None:
    at_floor = {k: _mid_values()[k] for k in ("market_trend", "breadth", "choppiness")}
    assert regime_score(at_floor)["score"] is not None
    below = {k: _mid_values()[k] for k in ("market_trend", "breadth")}
    res = regime_score(below)
    assert res["score"] is None
    assert res["withheld"] == "2 of 6 components present, floor is 3"


def test_the_floor_is_capped_at_the_component_set_own_size() -> None:
    """A count floor larger than the set would be an off switch wearing a floor's
    name (the WP-2 FGS lesson)."""
    from tradingagents.strategies.regime_score import _composite_floor

    assert _composite_floor() <= len(COMPONENT_ORDER)
    assert _composite_floor() == COMPOSITE_MIN_COVERAGE


def test_an_absent_component_does_not_punish_the_score() -> None:
    """`NA != 0`: dropping a component below the mean must RAISE the score, not
    drive it toward a neutral 50 or a punitive 0."""
    full = regime_score(_mid_values())
    dropped = {k: v for k, v in _mid_values().items() if k != "breadth"}
    after = regime_score(dropped)
    assert full["score"] is not None and after["score"] is not None
    assert after["score"] > full["score"]
    assert after["coverage"] == pytest.approx(5 / 6, abs=1e-4)
    assert "breadth" in after["absent"]


def test_coverage_drops_by_exactly_the_missing_component_weight() -> None:
    for name in COMPONENT_ORDER:
        res = regime_score({k: v for k, v in _mid_values().items() if k != name})
        assert res["coverage"] == pytest.approx(5 / 6, abs=1e-4), name
        assert res["absent"] == [name]
        assert name not in res["measured"]
        assert len(res["measured"]) == 5
        assert res["components"][name]["raw"] is None
        assert res["components"][name]["aligned"] is None


def test_a_bool_or_nan_where_a_measurement_is_declared_is_absent_not_zero() -> None:
    for raw in (True, float("nan"), float("inf"), "not a number"):
        out = align_components({"market_trend": raw})
        assert out["market_trend"] is None, raw
    assert align_components({"market_trend": 0.0})["market_trend"] == pytest.approx(50.0)


# --------------------------------------------------------------------------
# (c) the score never appears in a directional field
# --------------------------------------------------------------------------

_DIRECTIONAL_WORDS = (
    "bull", "bear", "buy", "sell", "long", "short", "overweight", "underweight",
    "up", "down", "signal", "bias",
)


def test_the_score_never_appears_in_a_directional_field() -> None:
    """`RegimeScore.md` §6.5: no "bullish because RegimeScore 68"."""
    res = regime_score(_mid_values())
    assert set(res) & {"direction", "signal", "bias", "stance", "forecast"} == set()
    band = res["band"]
    assert band == "constructive"
    lowered = band.lower()
    assert not any(word in lowered for word in _DIRECTIONAL_WORDS)
    basis = res["basis"].lower()
    assert not any(word in basis for word in ("bull", "bear", "buy", "sell"))
    assert "never a direction" in basis
    # the per-component `direction` is the ALIGNMENT of that measure, never a
    # direction for the name
    assert {
        entry["direction"] for entry in res["components"].values()
    } == {"higher_better", "lower_better"}


def test_regime_bands_are_not_the_decision_rating_bands() -> None:
    """Master rule 2: its own table, and not the guardrail's."""
    from tradingagents.strategies.decision_guardrail import SCORE_BANDS

    assert tuple(REGIME_BANDS) != tuple(SCORE_BANDS)
    assert not {label for _, label in REGIME_BANDS} & {label for _, label in SCORE_BANDS}
    for _, label in REGIME_BANDS:
        assert not any(word in label.lower() for word in _DIRECTIONAL_WORDS)


def test_the_module_declares_its_own_bands_and_never_the_guardrails() -> None:
    """Master rule 2: the only mention of the guardrail in the module is the
    sentence that forbids reading it."""
    source = Path("tradingagents/strategies/regime_score.py").read_text(encoding="utf-8")
    assert "import decision_guardrail" not in source
    assert "from .decision_guardrail" not in source
    assert "from tradingagents.strategies.decision_guardrail" not in source
    # the two mentions are prose: the rule that forbids reading it, and the band
    # table's own comment. Nothing reads it (the AST guard above proves that).
    assert source.count("decision_guardrail.SCORE_BANDS") == 2
    assert REGIME_BANDS[0][0] == 80.0


# --------------------------------------------------------------------------
# (d) the sizing scale is not an input to the score, and vice versa
# --------------------------------------------------------------------------


def test_the_module_never_touches_the_sizing_path() -> None:
    """No import and no attribute access on the sizing path (prose mentions are
    not dependencies)."""
    import ast

    tree = ast.parse(
        Path("tradingagents/strategies/regime_score.py").read_text(encoding="utf-8")
    )
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            referenced.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            referenced.add(node.module or "")
            referenced.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Attribute):
            parts = []
            cur = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                referenced.add(".".join(reversed(parts)))
    for forbidden in (
        "sizing", "risk.sizing", "risk_multiplier", "knife_guard",
        "position_size", "decision_guardrail", "GATE_PRECEDENCE",
        "risk_governor", "volatility_target_scale",
    ):
        assert not any(forbidden in ref for ref in referenced), (forbidden, referenced)


def test_the_sizing_scale_is_not_an_input_to_the_score() -> None:
    res = regime_score({"position_scale": 1.5, "momentum60": 0.2})
    assert res["score"] is None
    assert res["measured"] == []
    assert "position_scale" not in res["components"]


def test_the_two_paths_output_reconciles_nothing_and_echoes_the_scale() -> None:
    """§5.4: score != scale != state != confidence - the scale is echoed and
    multiplies nothing."""
    out = regime_paths(
        {"regime": "bull", "position_scale": 0.75, "momentum60": 0.12},
        {"labels": {"trend": "BULL", "volatility": "NORMAL",
                    "relative": "OUTPERFORM", "drawdown": "NORMAL"}},
    )
    assert out["path_a"]["position_scale"] == 0.75
    assert set(out) == {"disagree", "disagree_reason", "path_a", "path_b", "basis"}
    for key in out:
        assert not any(
            word in key for word in ("merged", "resolved", "average", "combined",
                                     "consensus", "reconciled", "reconciliation")
        )
    assert out["path_b"]["factor"] is None  # nothing derives a size here


# --------------------------------------------------------------------------
# the component table - one producer per component, in the plan's order
# --------------------------------------------------------------------------


def test_every_component_names_one_producer_with_a_line() -> None:
    """Master rule 3 / `RegimeScore.md` §5.1: one producer per component, named
    `module.function:line`. A producer inside `strategies/` is pinned to its line
    (a drift there means the table names a location that no longer holds it); a
    producer in another package is only resolved by symbol, because that file is
    edited by other workstreams and a moved line is not this engine's defect."""
    pattern = re.compile(r"^(?P<path>[\w/\.]+\.py)::(?P<func>[\w_]+):(?P<line>\d+)$")
    for name, comp in COMPONENTS.items():
        m = pattern.match(comp.producer)
        assert m, (name, comp.producer)
        # the table uses the house's package-relative spelling ("regime.py" /
        # "strategies/market_breadth.py"), so resolve it under the package root
        candidates = [Path(m.group("path")), Path("tradingagents") / m.group("path")]
        path = next((p for p in candidates if p.exists()), None)
        assert path is not None, (name, comp.producer)
        source = path.read_text(encoding="utf-8")
        assert f"def {m.group('func')}(" in source, (name, comp.producer)
        if path.parts[0] == "tradingagents" and path.parts[1] == "strategies":
            lines = source.splitlines()
            at = int(m.group("line")) - 1
            assert lines[at].startswith(f"def {m.group('func')}("), (
                name,
                comp.producer,
                lines[at][:60],
            )


def test_the_component_order_is_the_plans_prerequisite_order() -> None:
    """`RegimeScore.md` §5.1 / plan §5.3: trend, then breadth, then the VIX legs,
    then the chop unit - and only then the score."""
    assert COMPONENT_ORDER == (
        "market_trend",
        "breadth",
        "vix_percentile",
        "vix_term_structure",
        "choppiness",
        "realized_vol_percentile",
    )
    assert COMPONENTS["market_trend"].producer.endswith(
        "strategies/regime_score.py::market_trend:343"
    )


def test_every_component_has_a_ramp_a_direction_and_a_unit() -> None:
    for name, comp in COMPONENTS.items():
        assert name in RAMPS, name
        lo, hi = RAMPS[name]
        assert lo < hi, name
        assert comp.direction in ("higher_better", "lower_better"), name
        assert comp.unit and comp.category in OWNER_CATEGORY_WEIGHTS, name


def test_no_component_is_a_non_monotonic_technical_input() -> None:
    """The kernel's non-monotonic list is the technical engine's; a regime
    component ramped through one of those would be mixed up with a name-level
    oscillator."""
    from tradingagents.strategies.score_engine import NON_MONOTONIC_INPUTS

    assert not set(COMPONENTS) & set(NON_MONOTONIC_INPUTS)


def test_a_favourable_end_scores_strictly_above_the_unfavourable_one() -> None:
    for name, (good, bad) in COMPONENT_ENDS.items():
        hi = align_components({name: good})[name]
        lo = align_components({name: bad})[name]
        assert hi is not None and lo is not None, name
        assert hi > lo, (name, good, hi, bad, lo)


def test_an_undeclared_key_is_ignored_not_scored() -> None:
    out = align_components({"not_a_component": 1.0, "choppiness": 35.0})
    assert "not_a_component" not in out
    assert out["choppiness"] is not None
    assert out["market_trend"] is None


# --------------------------------------------------------------------------
# the composite's honesty
# --------------------------------------------------------------------------


def test_the_printed_weight_vector_is_the_one_used() -> None:
    """Master rule 6: no vector is published, so the default is equal weight and
    the basis PRINTS the fact."""
    res = regime_score(_mid_values())
    assert res["weights"] is None
    assert "no per-component weight vector is published, equal weights used" in res["basis"]
    # equal weight: the printed score IS the mean of the aligned values
    aligned = [res["aligned"][name] for name in COMPONENT_ORDER]
    assert res["score"] == pytest.approx(sum(aligned) / len(aligned), abs=0.005)


def test_a_supplied_weight_vector_is_used_and_printed() -> None:
    weights = dict.fromkeys(COMPONENT_ORDER, 1.0)
    weights["market_trend"] = 4.0
    res = regime_score(_mid_values(), weights=weights)
    num = sum(weights[k] * res["aligned"][k] for k in COMPONENT_ORDER)
    assert res["score"] == pytest.approx(num / sum(weights.values()), abs=0.005)
    assert res["weights"] == weights
    assert "supplied weights" in res["basis"]


def test_a_reader_recomputing_the_weighted_mean_gets_the_printed_score() -> None:
    res = regime_score(_mid_values())
    num = den = 0.0
    for name, entry in res["components"].items():
        value = entry["aligned"]
        if value is None:
            continue
        num += value
        den += 1.0
    assert res["score"] == pytest.approx(num / den, abs=0.005)
    assert res["coverage"] == pytest.approx(1.0)


def test_the_basis_names_the_owner_table_and_the_categories_it_cannot_measure() -> None:
    res = regime_score(_mid_values())
    basis = res["basis"]
    assert "CATEGORY level" in basis
    for category, weight in OWNER_CATEGORY_WEIGHTS.items():
        assert f"{category} {weight:g}" in basis, category
    for absent in ("market_momentum", "sector_rotation", "macro_credit", "event_regime"):
        assert absent in basis
    assert res["owner_categories"]["measured"] == list(MEASURED_CATEGORIES)
    assert res["owner_categories"]["event_category_moved_to"] == "EventScore"
    assert len(MEASURED_CATEGORIES) == 4


def test_the_basis_states_the_distortion_the_equal_vector_implies() -> None:
    """Three legs of six are volatility legs: an equal vector gives volatility
    50% where the owner's table gives it 20%. Stated, not hidden."""
    res = regime_score(_mid_values())
    assert "gives volatility 50%" in res["basis"]
    assert sum(
        1 for c in COMPONENTS.values() if c.category == "volatility"
    ) == 3


def test_the_status_vocabulary_is_the_plans() -> None:
    """ADVISORY for a deterministic diagnostic, RESEARCH_ONLY for an unvalidated
    combination."""
    assert regime_score(_mid_values())["status"] == STATUS_RESEARCH_ONLY == "RESEARCH_ONLY"
    assert STATUS_ADVISORY == "ADVISORY"
    assert market_trend(_series(120, step=0.004))["status"] == STATUS_ADVISORY
    assert vix_term_structure(12.0, 15.0)["status"] == STATUS_ADVISORY


def test_the_ramps_are_declared_policy_and_said_so() -> None:
    assert "declared policy" in regime_score(_mid_values())["basis"]
    assert "Phase C measures them" in regime_score(_mid_values())["basis"]


# --------------------------------------------------------------------------
# the producers: market_trend (prerequisite 1) and the VIX term structure
# --------------------------------------------------------------------------


def test_market_trend_measures_the_benchmark_not_the_name() -> None:
    up = market_trend(_series(240, step=0.003))
    down = market_trend(_series(240, step=-0.003))
    assert up["trend"] > 0 and down["trend"] < 0
    assert up["above_sma"] is True and down["above_sma"] is False
    assert up["sma_window"] == 200
    assert "the benchmark, not the analysed name" in up["basis"]


def test_market_trend_is_none_below_the_bar_floor_never_zero() -> None:
    out = market_trend(_series(MIN_BARS - 1, step=0.003))
    assert out["trend"] is None and out["above_sma"] is None
    assert out["n"] == MIN_BARS - 1
    assert str(MIN_BARS) in out["withheld"]
    assert market_trend([])["trend"] is None
    assert market_trend(None)["trend"] is None


def test_market_trend_prints_the_sma_window_it_actually_used() -> None:
    """A short benchmark history shortens the window; a reader must not quote a
    200-day read that was never one."""
    out = market_trend(_series(80, step=0.003))
    assert out["sma_window"] == 40
    assert "SMA40" in out["basis"]


def test_market_trend_does_not_change_when_the_name_changes() -> None:
    """The whole point of prerequisite 1: the same benchmark gives the same
    read for two different analysed names."""
    bench = _series(240, step=0.003)
    a = market_trend(bench)["trend"]
    b = market_trend(list(bench))["trend"]
    assert a == b


def test_vix_term_structure_reads_a_level_pair_never_the_equity_iv_slope() -> None:
    contango = vix_term_structure(12.0, 15.0)
    inverted = vix_term_structure(24.0, 20.0)
    assert contango["ratio"] == pytest.approx(0.8)
    assert contango["slope"] == pytest.approx(3.0)
    assert contango["inverted"] is False
    assert inverted["inverted"] is True
    assert "not the equity-IV slope" in contango["basis"]


def test_vix_term_structure_is_none_when_a_level_is_missing_never_zero() -> None:
    for pair in ((None, 15.0), (12.0, None), (12.0, 0.0)):
        out = vix_term_structure(*pair)
        assert out["ratio"] is None and out["slope"] is None
        assert out["inverted"] is None
        assert "equity-IV slope is not a substitute" in out["basis"]
    assert vix_term_structure(12.0, 15.0)["withheld"] is None


def test_the_vix_term_component_is_absent_until_a_series_is_verified() -> None:
    """P0-5 is ABSENT in this tree: no fabricated series id, so the leg is NA and
    printed rather than proxied."""
    from tradingagents.strategies.regime_score import VIX9D_SERIES, VIX_TERM_UNAVAILABLE

    assert VIX9D_SERIES is None
    assert "not a substitute" in VIX_TERM_UNAVAILABLE
    res = regime_score({"market_trend": 0.06, "breadth": 60.0, "choppiness": 35.0})
    assert "vix_term_structure" in res["absent"]


# --------------------------------------------------------------------------
# the vol_percentile defect fix (RegimeScore.md §5.2, plan §5.3)
# --------------------------------------------------------------------------


def test_vol_percentile_returns_none_with_a_reason_when_it_cannot_measure() -> None:
    """The defect: ``0.5`` on failure was a fabricated neutral (master rule 1)."""
    assert vol_percentile([]) is None
    assert vol_percentile([_noisy(30, sigma=0.001)]) is None
    out = vol_percentile_read([_noisy(30, sigma=0.001)])
    assert out["percentile"] is None
    assert out["windows"] == 1
    assert "needs 2" in out["reason"]
    assert "never a fabricated 0.5" in out["basis"]


def test_vol_percentile_still_ranks_a_measurable_history() -> None:
    """The fix must not turn the producer into a permanent None."""
    quiet = [_noisy(30, sigma=0.001, seed=i) for i in range(5)]
    loud = quiet + [_noisy(30, sigma=0.05, seed=99)]
    ranked = vol_percentile(loud, current_window=21)
    assert ranked is not None and 0.0 < ranked <= 1.0
    assert ranked == pytest.approx(1.0)  # the loudest window is the latest
    read = vol_percentile_read(loud, current_window=21)
    assert read["percentile"] == pytest.approx(1.0)
    assert read["reason"] is None
    assert read["windows"] == 6
    assert "percentile of 6 trailing window(s)" in read["basis"]


def test_the_defect_fix_is_the_only_thing_that_moved_in_the_producer() -> None:
    """The rank itself is unchanged: the same history still ranks the same way
    (the latest window sits at 2 of 3, strictly between the two older ones)."""
    hist = [
        _noisy(30, sigma=0.001, seed=1),
        _noisy(30, sigma=0.05, seed=2),
        _noisy(30, sigma=0.003, seed=3),
    ]
    pct = vol_percentile(hist, current_window=21)
    assert pct == pytest.approx(2 / 3)
    assert math.isclose(vol_percentile_read(hist)["percentile"], pct, rel_tol=1e-12)


def test_the_fixed_producer_leaves_the_denominator_in_the_score() -> None:
    """The point of the fix: an unmeasurable leg is `NA`, printed, not a 50."""
    res = regime_score({**_mid_values(), "realized_vol_percentile": None})
    assert "realized_vol_percentile" in res["absent"]
    assert res["coverage"] == pytest.approx(5 / 6, abs=1e-4)
    assert res["score"] == pytest.approx(
        sum(res["aligned"][k] for k in COMPONENT_ORDER if k != "realized_vol_percentile")
        / 5,
        abs=0.005,
    )


def test_vol_percentile_read_is_exported_from_the_regime_module() -> None:
    assert "vol_percentile_read" in regime_mod.__all__


# --------------------------------------------------------------------------
# the two paths are tested for disagreement, not merged (§6.3)
# --------------------------------------------------------------------------


def test_the_two_paths_are_tested_for_disagreement_not_merged() -> None:
    out = regime_paths(
        {"regime": "bull", "position_scale": 1.0},
        {"labels": {"trend": "STRONG_BEAR", "volatility": "HIGH",
                    "relative": "UNDERPERFORM", "drawdown": "BEAR"}},
    )
    assert out["disagree"] is True
    assert "contradiction" in out["disagree_reason"]
    # BOTH values present, with their names, and nothing resolved between them
    assert out["path_a"]["name"] == PATH_A_NAME == "get_regime_read"
    assert out["path_b"]["name"] == PATH_B_NAME == "get_regime_state"
    assert out["path_a"]["label"] == "bull"
    assert out["path_b"]["axes"] == {
        "trend": "STRONG_BEAR",
        "volatility": "HIGH",
        "relative": "UNDERPERFORM",
        "drawdown": "BEAR",
    }
    assert out["path_b"]["trend"] == "STRONG_BEAR"
    assert set(out["path_b"]["axes"]) == set(AXIS_KEYS)
    assert "no reconciliation" in out["basis"]


def test_a_volatility_contradiction_is_also_named() -> None:
    out = regime_paths(
        {"regime": "high_vol"},
        {"labels": {"trend": "BULL", "volatility": "LOW"}},
    )
    assert out["disagree"] is True
    assert "volatility axis is LOW" in out["disagree_reason"]


def test_a_resolution_disagreement_is_named_as_such_not_as_a_contradiction() -> None:
    out = regime_paths(
        {"regime": "neutral"},
        {"labels": {"trend": "STRONG_BULL", "volatility": "NORMAL"}},
    )
    assert out["disagree"] is True
    assert "resolution disagreement" in out["disagree_reason"]


def test_two_agreeing_paths_are_not_flagged() -> None:
    out = regime_paths(
        {"regime": "bull"},
        {"labels": {"trend": "BULL", "volatility": "NORMAL",
                    "relative": "OUTPERFORM", "drawdown": "NORMAL"}},
    )
    assert out["disagree"] is False
    assert out["disagree_reason"]


def test_an_unreadable_path_makes_the_flag_none_not_false() -> None:
    missing_a = regime_paths({}, {"labels": {"trend": "BEAR"}})
    assert missing_a["disagree"] is None
    assert "reported no label" in missing_a["disagree_reason"]
    missing_b = regime_paths({"regime": "bear"}, {})
    assert missing_b["disagree"] is None
    assert "reported no axis" in missing_b["disagree_reason"]


def test_the_two_paths_read_the_real_producers_shapes() -> None:
    """The echoed shapes are the ones the tree actually produces:
    `overlays.build_strategy_overlays` and `regime_state.regime_state`."""
    from tradingagents.strategies.overlays import build_strategy_overlays
    from tradingagents.strategies.regime_state import regime_state

    series = _series(260, step=0.003)
    label_read = build_strategy_overlays(
        {"enable_strategy_overlays": True, "volatility_estimator": "close"}, series
    )
    axes = regime_state(series, benchmark=_series(260, step=0.001))
    out = regime_paths(label_read, axes)
    assert out["path_a"]["label"] == label_read["regime"]
    assert out["path_b"]["axes"] == {
        k: axes["labels"][k] for k in AXIS_KEYS
    }
    assert out["path_a"]["position_scale"] == label_read["position_scale"]
    assert out["path_b"]["factor"] == axes["factor"]
    assert out["disagree"] in (True, False)


def test_the_paths_are_not_a_score_and_hold_no_composite_number() -> None:
    out = regime_paths(
        {"regime": "bull"},
        {"labels": {"trend": "BULL", "volatility": "NORMAL"}},
    )
    assert "score" not in out
    assert "score" not in out["path_a"] and "score" not in out["path_b"]
    assert not any("score" in key for key in out)
    assert not any("score" in key for key in out["path_b"]["axes"])


# --------------------------------------------------------------------------
# the wiring (added by the integration owner after the shared files landed)
# --------------------------------------------------------------------------


def test_gate_off_keeps_the_regime_tool_out_of_every_toolset(monkeypatch) -> None:
    import tradingagents.dataflows.config as cfgmod
    from tradingagents.agents import toolsets

    monkeypatch.setattr(cfgmod, "get_config", lambda: {})
    off = [t.name for t in toolsets.market_tools()]
    assert "get_regime_score" not in off
    monkeypatch.setattr(cfgmod, "get_config", lambda: {"enable_regime_score": True})
    on = [t.name for t in toolsets.market_tools()]
    assert set(on) - set(off) == {"get_regime_score"}


def test_gate_off_writes_no_card_key() -> None:
    from tradingagents.reporting import _run_card_regime_score

    assert _run_card_regime_score({}) is None


def test_the_leaf_says_the_gate_is_off(monkeypatch) -> None:
    import tradingagents.dataflows.config as cfgmod
    from tradingagents.agents.utils.analysis_tools import get_regime_score

    monkeypatch.setattr(cfgmod, "get_config", lambda: {"enable_regime_score": False})
    out = get_regime_score.invoke({})
    assert "gated off" in out and "enable_regime_score" in out


def test_the_card_block_degrades_without_market_data(monkeypatch) -> None:
    import tradingagents.agents.utils.analysis_tools as at
    from tradingagents.reporting import _run_card_regime_score

    monkeypatch.setattr(at, "_regime_components", lambda: {})
    block = _run_card_regime_score({"enable_regime_score": True})
    assert block["score"] is None
    assert "no market data" in block["unavailable"]
