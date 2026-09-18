"""`TechnicalScore` (WP-3) and the semivariance producer.

Covers the plan's acceptance list (`docs/scores/IMPLEMENTATION_PLAN.md` §5.2):
(a) each band row's mapped value moves the right way at the producer's own edges
- RSI 45-70 must not score lower than RSI 80; (b) coverage drops by exactly the
missing category's weight and the score moves toward the mean of the present
categories; (c) all-`None` returns `None` / 0 coverage; (d) a reader recomputing
`Σw·s / Σw` from the printed attribution gets the printed score; (e)
`TechnicalScore` never touches `risk/sizing.py`.

Offline and deterministic: every value is synthetic, no vendor call.
"""

from __future__ import annotations

import math
import random

import pytest

from tradingagents.strategies.technical_score import (
    BANDS,
    CATEGORY_COMPONENTS,
    CATEGORY_MIN_COVERAGE,
    CATEGORY_ORDER,
    CATEGORY_WEIGHTS,
    COMPONENTS,
    COMPOSITE_MIN_COVERAGE,
    RAMPS,
    TECH_BANDS,
    align_components,
    category_score,
    category_weight_share,
    technical_score,
)
from tradingagents.strategies.volatility_models import semivariance

# The favourable / unfavourable ends of every non-monotonic input, taken from
# the producers' own consumers (TechnicalScore.md §0.3). A table that inverts
# one of these is the single biggest correctness risk this engine has.
NON_MONOTONIC_ENDS: dict[str, tuple[float, float]] = {
    "rsi": (60.0, 80.0),          # 45-70 `strong` beats >70 `hot`
    "stoch_k": (10.0, 90.0),      # <20 oversold is the dip read
    "mfi": (10.0, 90.0),          # >80 overbought
    "stoch_rsi": (0.1, 0.9),      # <0.2 is the entry
    "rsi2": (5.0, 80.0),          # <10 is the buy
    "williams_r": (-90.0, -10.0),  # -80..-100 oversold
    "bollinger_pct_b": (-0.2, 1.2),  # <=0 dip, >1 extended
    "elder_ratio": (0.5, 2.0),    # `quiet` (<0.8) is the good dip read
    "keltner_pct": (0.5, 1.2),    # the mid-band is the read
}


def _full_values() -> dict:
    return {
        "adx": 30.0, "di_spread": 10.0, "above_sma200": True, "sma_stack": True,
        "golden_cross": True, "ichimoku_above_cloud": True, "aroon_osc": 40.0,
        "rsi": 60.0, "stoch_k": 50.0, "mfi": 50.0, "roc20": 0.05,
        "momentum_12_1": 0.20, "macd_hist_pct": 0.005, "rs_slope_pct": 0.05,
        "rs_above_sma": True, "rs_new_high": False, "rs_divergence": False,
        "bollinger_pct_b": 0.6, "keltner_pct": 0.5, "near_sma200": True,
        "fib_zone": False, "rvol": 1.4, "elder_ratio": 1.0, "cmf": 0.1,
        "volume_dry_up": False, "vcp_candidate": False, "near_breakout": True,
        "pullback_candidate": True, "trigger_candle": True, "stoch_rsi": 0.5,
        "rsi2": 40.0, "williams_r": -50.0, "hurst": 0.5, "obv_bullish_div": True,
        "atr_pct": 0.02, "vol_percentile": 0.5, "sqrt_rs_minus": 0.015,
        "pct_above_50d": 55.0, "pct_above_200d": 50.0, "ad_ratio": 0.1,
    }


# --------------------------------------------------------------------------
# (a) the band rows move the right way at the producer's own edges
# --------------------------------------------------------------------------


def test_every_non_monotonic_input_scores_its_favourable_end_higher() -> None:
    for name, (good, bad) in NON_MONOTONIC_ENDS.items():
        mapped_good = align_components({name: good})[name]
        mapped_bad = align_components({name: bad})[name]
        assert mapped_good is not None and mapped_bad is not None, name
        assert mapped_good > mapped_bad, (
            f"{name}: the producer's favourable end ({good}) scored {mapped_good}, "
            f"its unfavourable end ({bad}) scored {mapped_bad} - the table is inverted"
        )


def test_rsi_45_to_70_does_not_score_below_rsi_80() -> None:
    strong = align_components({"rsi": 60.0})["rsi"]
    hot = align_components({"rsi": 80.0})["rsi"]
    assert strong > hot


def test_monotone_ramps_are_ordered() -> None:
    for name, (lo, hi) in RAMPS.items():
        comp_dir = COMPONENTS[name].direction
        low = align_components({name: lo})[name]
        high = align_components({name: hi})[name]
        assert low is not None and high is not None, name
        if comp_dir == "higher_better":
            assert high > low, name
        else:
            assert high < low, name


def test_every_declared_component_has_a_mapping() -> None:
    for name in COMPONENTS:
        assert (name in BANDS) ^ (name in RAMPS), name


def test_band_tables_are_written_top_down() -> None:
    for name, table in BANDS.items():
        edges = [edge for edge, _ in table]
        assert edges == sorted(edges, reverse=True), name
        scores = [score for _, score in table]
        assert all(0.0 <= s <= 100.0 for s in scores), name


def test_booleans_are_measurements_not_gaps() -> None:
    assert align_components({"above_sma200": True})["above_sma200"] == 75.0
    assert align_components({"above_sma200": False})["above_sma200"] == 35.0


def test_missing_components_are_none_never_a_neutral_fifty() -> None:
    out = align_components({"rsi": 60.0})
    assert out["rsi"] == 85.0
    assert out["mfi"] is None
    assert set(out.values()) - {85.0} == {None}
    assert align_components({"rsi": None})["rsi"] is None
    assert align_components({"rsi": float("nan")})["rsi"] is None
    # an undeclared key is ignored, not scored
    assert "not_a_component" not in align_components({"not_a_component": 1.0})


def test_technical_bands_are_not_the_decision_rating_bands() -> None:
    from tradingagents.strategies.decision_guardrail import SCORE_BANDS

    assert tuple(TECH_BANDS) != tuple(SCORE_BANDS)
    assert not {label for _, label in TECH_BANDS} & {label for _, label in SCORE_BANDS}


# --------------------------------------------------------------------------
# (b) coverage drops by exactly the missing category's weight
# --------------------------------------------------------------------------


def test_a_missing_category_lowers_coverage_by_its_own_weight() -> None:
    full = technical_score(_full_values())
    assert full["score"] is not None
    assert full["coverage"] == pytest.approx(1.0)

    for category in CATEGORY_ORDER:
        dropped = {
            k: v for k, v in _full_values().items()
            if k not in CATEGORY_COMPONENTS[category]
        }
        res = technical_score(dropped)
        expected = 1.0 - CATEGORY_WEIGHTS[category] / sum(CATEGORY_WEIGHTS.values())
        assert res["coverage"] == pytest.approx(expected), category
        assert res["categories"][category]["score"] is None, category
        assert res["score"] is not None


def test_the_score_moves_toward_the_mean_of_the_present_categories() -> None:
    vals = _full_values()
    strong = {**vals, "adx": 40.0, "di_spread": 20.0, "aroon_osc": 60.0,
              "above_sma200": True, "sma_stack": True, "golden_cross": True}
    weak = {**vals, "adx": 10.0, "di_spread": -20.0, "aroon_osc": -60.0,
            "above_sma200": False, "sma_stack": False, "golden_cross": False}
    hi = technical_score(strong)["score"]
    lo = technical_score(weak)["score"]
    assert hi > lo
    # with the category removed the two extremes converge (the mean of what is
    # left is all that remains)
    hi_wo = technical_score({k: v for k, v in strong.items()
                             if k not in CATEGORY_COMPONENTS["trend"]})["score"]
    lo_wo = technical_score({k: v for k, v in weak.items()
                             if k not in CATEGORY_COMPONENTS["trend"]})["score"]
    assert abs(hi_wo - lo_wo) < abs(hi - lo)


# --------------------------------------------------------------------------
# (c) all-None
# --------------------------------------------------------------------------


def test_all_none_returns_none_with_zero_coverage() -> None:
    res = technical_score({})
    assert res["score"] is None
    assert res["coverage"] == 0.0
    assert "floor" in res["withheld"]
    assert res["bands"] is None
    assert res["status"] == "ADVISORY"


def test_one_category_alone_is_withheld_from_the_composite() -> None:
    vals = {k: v for k, v in _full_values().items()
            if COMPONENTS[k].category == "trend"}
    res = technical_score(vals)
    assert res["categories"]["trend"]["score"] is not None
    assert res["score"] is None  # 20 of 100 weight, below the composite floor
    assert "floor" in res["withheld"]


# --------------------------------------------------------------------------
# (d) the attribution recomputes the score
# --------------------------------------------------------------------------


def test_a_reader_recomputing_the_weighted_mean_gets_the_printed_score() -> None:
    res = technical_score(_full_values())
    num = 0.0
    den = 0.0
    for cat, entry in res["categories"].items():
        score = entry.get("score")
        if score is None:
            continue
        num += CATEGORY_WEIGHTS[cat] * score
        den += CATEGORY_WEIGHTS[cat]
    # the kernel prints the score to 2dp; recomputing from the printed
    # attribution lands within half a unit of that precision
    assert res["score"] == pytest.approx(num / den, abs=0.005)
    assert res["coverage"] == pytest.approx(den / sum(CATEGORY_WEIGHTS.values()))


def test_a_supplied_weight_vector_is_printed_and_used() -> None:
    w = {cat: 1.0 for cat in CATEGORY_ORDER}
    w["trend"] = 4.0
    res = technical_score(_full_values(), weights=w)
    num = sum(w[c] * res["categories"][c]["score"] for c in CATEGORY_ORDER)
    assert res["score"] == pytest.approx(num / sum(w.values()), abs=0.005)
    assert res["weights"] == w
    assert "supplied weights" in res["basis"]
    assert "owner weights" in technical_score(_full_values())["basis"]


def test_category_weight_share_renormalises() -> None:
    share = category_weight_share()
    assert sum(share.values()) == pytest.approx(1.0)
    assert share["trend"] == pytest.approx(0.20)


def test_components_carry_their_producer_and_direction() -> None:
    res = technical_score(_full_values())
    for name, entry in res["components"].items():
        assert entry["producer"], name
        assert entry["direction"] in ("higher_better", "lower_better")
        assert entry["category"] in CATEGORY_ORDER


def test_category_score_rejects_an_unknown_category() -> None:
    with pytest.raises(KeyError):
        category_score("nope", {})


def test_category_floor_is_capped_at_the_category_size() -> None:
    """A category smaller than the floor still scores (the FGS lesson)."""
    vals = {k: v for k, v in _full_values().items()
            if COMPONENTS[k].category == "volatility"}
    res = category_score("volatility", align_components(vals),
                         min_coverage=CATEGORY_MIN_COVERAGE)
    assert res["score"] is not None
    assert res["band"] in {label for _, label in TECH_BANDS}


# --------------------------------------------------------------------------
# (e) it never sizes anything
# --------------------------------------------------------------------------


def test_the_module_never_touches_the_sizing_path() -> None:
    """No import and no attribute access on the sizing path (the docstring's
    mention of `risk/sizing.py` is prose, and prose is not a dependency)."""
    import ast
    from pathlib import Path

    tree = ast.parse(
        Path("tradingagents/strategies/technical_score.py").read_text(encoding="utf-8")
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
    for forbidden in ("sizing", "risk.sizing", "risk_multiplier", "knife_guard",
                      "position_size", "decision_guardrail"):
        assert not any(forbidden in ref for ref in referenced), (forbidden, referenced)


# --------------------------------------------------------------------------
# the semivariance producer (TechnicalScore.md §4, pinned in RiskScore.md §0.3)
# --------------------------------------------------------------------------


def _returns(n: int = 120, seed: int = 7) -> list[float]:
    rng = random.Random(seed)
    closes = [100.0]
    for _ in range(n):
        closes.append(closes[-1] * (1.0 + rng.gauss(0.0005, 0.012)))
    return closes


def test_rs_minus_plus_rs_plus_equals_rv_exactly() -> None:
    out = semivariance(_returns())
    assert out["rs_minus"] + out["rs_plus"] == pytest.approx(out["rv"], abs=1e-15)


def test_semivariance_is_none_below_the_floor_never_zero() -> None:
    out = semivariance(_returns(10))
    assert out["rs_minus"] is None and out["sqrt_rs_minus"] is None
    assert out["n"] == 10
    assert "never 0" in out["basis"]


def test_the_downside_leg_is_the_one_that_rises_in_a_decline() -> None:
    up = [100.0]
    for _ in range(60):
        up.append(up[-1] * 1.01)
    down = [100.0]
    for _ in range(60):
        down.append(down[-1] * 0.99)
    up_out = semivariance(up)
    down_out = semivariance(down)
    assert down_out["rs_minus"] > up_out["rs_minus"]
    assert up_out["rs_plus"] > down_out["rs_plus"]
    assert up_out["asymmetry"] == 0.0
    assert down_out["asymmetry"] is None  # no upside leg to divide by


def test_semivariance_annualises_both_legs_and_the_total() -> None:
    out = semivariance(_returns())
    assert out["annualized"]["sqrt_rs_minus"] == pytest.approx(
        out["sqrt_rs_minus"] * math.sqrt(252.0), rel=1e-9
    )
    assert out["annualized"]["rv"] == pytest.approx(math.sqrt(out["rv"] * 252.0), rel=1e-9)


def test_semivariance_uses_the_full_sample_not_the_count_of_each_sign() -> None:
    """A conditional ``sum(r^2)/n_down`` would NOT satisfy RS- + RS+ = RV."""
    out = semivariance(_returns())
    assert out["basis"].count("exactly") == 1
    assert "RS- + RS+ = RV exactly" in out["basis"]


# --------------------------------------------------------------------------
# the leaf, the gate and the run-card block
# --------------------------------------------------------------------------


def test_gate_off_keeps_the_engine_tool_out_of_every_toolset(monkeypatch) -> None:
    import tradingagents.dataflows.config as cfgmod
    from tradingagents.agents import toolsets

    monkeypatch.setattr(cfgmod, "get_config", lambda: {})
    names_off = [t.name for t in toolsets.fundamentals_company_tools()]
    assert "get_technical_score" not in names_off
    assert "get_fundamental_score" not in names_off
    monkeypatch.setattr(
        cfgmod, "get_config", lambda: {"enable_technical_score": True}
    )
    names_on = [t.name for t in toolsets.fundamentals_company_tools()]
    assert set(names_on) - set(names_off) == {"get_technical_score"}


def test_gate_off_makes_the_leaf_say_so(monkeypatch) -> None:
    import tradingagents.dataflows.config as cfgmod
    from tradingagents.agents.utils.analysis_tools import get_technical_score

    monkeypatch.setattr(cfgmod, "get_config", lambda: {"enable_technical_score": False})
    out = get_technical_score.invoke({"ticker": "MSFT"})
    assert "gated off" in out and "enable_technical_score" in out


def test_the_leaf_assembles_components_from_the_run_bars(monkeypatch) -> None:
    """A synthetic series exercises the assembly without a vendor call."""
    import tradingagents.agents.utils.analysis_tools as at

    n = 320
    closes = [100.0 + i * 0.2 + (i % 7) * 0.1 for i in range(n)]
    bars = {
        "dates": [f"d{i}" for i in range(n)],
        "closes": closes,
        "highs": [c * 1.01 for c in closes],
        "lows": [c * 0.99 for c in closes],
        "volumes": [1_000_000.0 + i * 100 for i in range(n)],
        "opens": closes,
        "absence": None,
    }
    monkeypatch.setattr(at, "_ohlcv", lambda ticker, days=320: bars)
    monkeypatch.setattr(at, "_benchmark_closes", lambda: list(closes))
    vals = at._technical_components("TEST")
    assert len(vals) >= 20, sorted(vals)
    for name in vals:
        assert name in COMPONENTS, name
    res = technical_score(vals)
    assert res["score"] is not None
    text = at._render_technical_score("TEST", res)
    assert "TechnicalScore - TEST" in text
    assert "composite [ADVISORY]" in text
    assert "never a gate, never a size, never a forecast" in text


def test_the_leaf_returns_unavailable_with_too_few_bars(monkeypatch) -> None:
    import tradingagents.agents.utils.analysis_tools as at

    monkeypatch.setattr(
        at, "_ohlcv", lambda ticker, days=320: {"closes": [1.0, 2.0], "highs": [], "lows": [], "volumes": []}
    )
    assert at._technical_components("TEST") == {}


def test_run_card_block_is_absent_when_the_gate_is_off() -> None:
    from tradingagents.reporting import _run_card_technical_score

    assert _run_card_technical_score("MSFT", {}) is None


def test_run_card_block_carries_the_attribution(monkeypatch) -> None:
    import tradingagents.agents.utils.analysis_tools as at
    from tradingagents.reporting import _run_card_technical_score

    n = 320
    closes = [100.0 + i * 0.2 + (i % 7) * 0.1 for i in range(n)]
    bars = {
        "dates": [f"d{i}" for i in range(n)], "closes": closes,
        "highs": [c * 1.01 for c in closes], "lows": [c * 0.99 for c in closes],
        "volumes": [1_000_000.0 + i * 100 for i in range(n)], "opens": closes,
        "absence": None,
    }
    monkeypatch.setattr(at, "_ohlcv", lambda ticker, days=320: bars)
    monkeypatch.setattr(at, "_benchmark_closes", lambda: list(closes))
    block = _run_card_technical_score("TEST", {"enable_technical_score": True})
    assert block["status"] == "ADVISORY"
    assert block["score"] is not None
    num = den = 0.0
    for cat, entry in block["categories"].items():
        if entry["score"] is None:
            continue
        num += entry["weight"] * entry["score"]
        den += entry["weight"]
    assert block["score"] == pytest.approx(num / den, abs=0.005)
    assert block["coverage"] == pytest.approx(den / sum(CATEGORY_WEIGHTS.values()))
    assert block["components"]
    assert block["basis"].startswith("TechnicalScore:")


def test_run_card_block_degrades_without_costing_the_card(monkeypatch) -> None:
    import tradingagents.agents.utils.analysis_tools as at
    from tradingagents.reporting import _run_card_technical_score

    def _boom(ticker, days=320):
        raise RuntimeError("bars unavailable")

    monkeypatch.setattr(at, "_ohlcv", _boom)
    block = _run_card_technical_score("TEST", {"enable_technical_score": True})
    assert block["score"] is None and "bars unavailable" in block["unavailable"]
