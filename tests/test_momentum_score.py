"""MomentumScore engine + leaf tests (MOM-1..MOM-6).

Hermetic: the leaf's price fetch is monkeypatched, so no vendor call runs.
"""

from __future__ import annotations

import math

import pytest

pytestmark = pytest.mark.timeout(120)

from tradingagents.strategies.momentum_score import (  # noqa: E402
    BANDS,
    COMPONENTS,
    COMPOSITE_MIN_COVERAGE,
    DECLINED_SUB_ITEMS,
    LEG_COMPONENTS,
    LEG_ORDER,
    LEG_WEIGHTS,
    MOMENTUM_BANDS,
    NORMALIZATION_METHOD,
    PERCENTILE_METHOD,
    RAMPS,
    RETIRED_MEMBERS,
    efficiency_ratio,
    horizon_conviction,
    horizon_dispersion,
    momentum_meta,
    momentum_score,
    normalize_component,
    positive_day_ratio,
)


def _full_values() -> dict:
    """One plausible full member vector - every declared member present."""
    return {
        "r_5": 0.03,
        "r_21": 0.08,
        "r_63": 0.15,
        "r_126": 0.20,
        "r_252": 0.35,
        "mom_12_1": 0.22,
        "rs_slope_pct": 0.02,
        "rs_new_high": True,
        "rs_divergence": False,
        "rs_vs_sector": 0.03,
        "adx": 28.0,
        "di_spread": 6.0,
        "ma_distance": 0.04,
        "ma_slope": 0.01,
        "sma_stack": True,
        "trend_slope": 0.002,
        "trend_r2": 0.7,
        "accel_short_medium": 0.05,
        "accel_medium_long": 0.02,
        "macd_hist_accel": 0.002,
        "donchian_20": 0.6,
        "donchian_50": 0.4,
        "donchian_100": 0.2,
        "donchian_252": 0.1,
        "breakout_strength": 1.2,
        "dist_from_high": -0.02,
        "rvol": 1.4,
        "volume_trend": 0.05,
        "obv_slope_norm": 0.05,
        "cmf": 0.08,
        "pv_corr": 0.30,
        "efficiency_ratio": 0.45,
        "positive_day_ratio": 0.58,
        "autocorr1": 0.05,
        "vol_adjusted": 0.9,
        "realized_vol": 0.35,
        "downside_dev": 0.22,
        "max_drawdown": 0.18,
        "ulcer": 0.06,
        "atr_pct": 0.025,
    }


# ---------------------------------------------------------------------------
# The declaration: eight legs, every member mapped, the gate shipped off
# ---------------------------------------------------------------------------


def test_exactly_the_eight_section54_legs_are_declared():
    assert LEG_ORDER == ("P", "R", "T", "A", "B", "V", "Q", "D")
    assert set(LEG_COMPONENTS) == set(LEG_ORDER)
    assert sum(LEG_WEIGHTS.values()) == pytest.approx(1.0)
    assert set(LEG_WEIGHTS) == set(LEG_ORDER)


def test_no_declared_leg_is_silently_absent():
    """Every leg key is always present in the result, and no leg is empty."""
    res = momentum_score({})
    assert set(res["legs"]) == set(LEG_ORDER)
    for leg in LEG_ORDER:
        assert LEG_COMPONENTS[leg], f"leg {leg} declares no member"
        assert res["legs"][leg]["score"] is None  # nothing measured -> withheld
        assert res["legs"][leg]["withheld"]


def test_every_member_is_mapped_and_names_a_producer():
    for name, comp in COMPONENTS.items():
        assert comp.leg in LEG_ORDER, name
        assert name in RAMPS or name in BANDS, f"{name} has no mapping"
        assert "." in comp.producer, f"{name} names no producer"
        assert comp.section.startswith("§"), f"{name} cites no section"


def test_the_gate_ships_off_and_is_registered():
    from tradingagents.default_config import DEFAULT_CONFIG, SHIPPED_DEFAULTS
    from tradingagents.strategies.quant_scorecard import (
        ENGINE_GATES,
        ENGINE_SECTIONS,
        ENGINE_TOOLS,
    )

    assert ENGINE_GATES["momentum"] == "enable_momentum_score"
    assert ENGINE_TOOLS["momentum"] == "get_momentum_score"
    assert ENGINE_SECTIONS["momentum"] == "market"
    assert SHIPPED_DEFAULTS["enable_momentum_score"] is False
    assert DEFAULT_CONFIG["enable_momentum_score"] is False


# ---------------------------------------------------------------------------
# MOM-2: the normalization contract
# ---------------------------------------------------------------------------


def test_section48_normalization_endpoints():
    # z = -3 -> 0, z = 0 -> 50, z = +3 -> 100 (the library's own §19 endpoints).
    assert NORMALIZATION_METHOD == "z"
    # A symmetric cross-section: the two extremes are 3 sigma out only when the
    # sample is built that way, so pin the affine map directly on z = 0 too.
    flat = normalize_component([5.0, 5.0, 5.0])
    assert flat == [None, None, None]  # zero spread -> no measurement, never 50
    same = normalize_component([1.0])
    assert same == [None]
    mid = normalize_component([1.0, 2.0, 3.0, 4.0, 5.0])
    assert mid[2] == pytest.approx(50.0)  # the centre of a symmetric sample


def test_section48_winsorizes_at_three_sigma():
    # A cross-section whose outlier is far beyond 3 sigma must clip, not run on.
    values = [0.0] * 20 + [1000.0]
    out = normalize_component(values)
    assert max(v for v in out if v is not None) <= 100.0
    assert min(v for v in out if v is not None) >= 0.0


def test_section49_is_a_one_line_alternative():
    out = normalize_component([1.0, 2.0, 3.0, 4.0], method=PERCENTILE_METHOD)
    assert out == [25.0, 50.0, 75.0, 100.0]


def test_a_reference_cross_section_normalizes_the_named_member():
    values = _full_values()
    # The name under test sits far above a tight reference set (0.0 x10, 0.5).
    ref = {"cmf": [0.0] * 10 + [0.5]}
    res = momentum_score(values, reference=ref)
    ramp = momentum_score(values)["components"]["cmf"]
    assert res["legs"]["V"]["score"] is not None
    # The §48 z path and the declared ramp disagree: the reference makes the
    # outlier strong (> 80), while the ramp scored 0.08 at ~70.
    assert res["components"]["cmf"] > 80.0
    assert res["components"]["cmf"] != ramp


# ---------------------------------------------------------------------------
# The composite and the meta layer (MOM-3)
# ---------------------------------------------------------------------------


def test_the_composite_reads_every_leg_and_reports_coverage():
    res = momentum_score(_full_values())
    assert res["score"] is not None
    assert res["coverage"] == 1.0
    assert res["floor"] == COMPOSITE_MIN_COVERAGE
    assert res["label"] in [label for _, label in MOMENTUM_BANDS]
    # Every member but `rs_percentile` is present; that one exists only on the
    # reference-cross-section path, so it is absent here by construction.
    assert res["absent"] == ["rs_percentile"]
    assert len(res["present"]) == len(COMPONENTS) - 1


def test_below_the_floor_the_composite_is_withheld_never_zero():
    res = momentum_score({"r_5": 0.1})  # one leg, one member
    assert res["score"] is None
    assert res["withheld"]


def test_meta_is_outside_the_number():
    """The meta block never moves the score: same members, same composite."""
    values = _full_values()
    res = momentum_score(values)
    meta = res["meta"]
    # Recomputing the meta on the same legs gives the same numbers, and the
    # composite is unchanged by the meta's presence.
    again = momentum_meta(res["legs"], res["components"])
    assert again["coverage"] == meta["coverage"]
    assert res["score"] == momentum_score(values)["score"]
    assert "conviction" in meta and "dispersion" in meta and "divergence" in meta


def test_section50_conviction_has_both_library_forms():
    agree = horizon_conviction({5: 60.0, 21: 62.0, 63: 61.0, 126: 63.0, 252: 60.0})
    assert agree["by_count"] == 1.0
    assert agree["by_dispersion"] > 0.9
    split = horizon_conviction({5: 80.0, 21: 20.0})
    assert split["by_count"] == 0.5
    thin = horizon_conviction({5: 60.0})
    assert thin["by_dispersion"] is None and thin["by_count"] is None
    assert thin["reason"]


def test_section51_dispersion_needs_two_horizons():
    assert horizon_dispersion({5: 50.0})["dispersion"] is None
    d = horizon_dispersion({5: 40.0, 21: 60.0})
    assert d["dispersion"] == pytest.approx(10.0)


def test_mom3_declined_items_are_recorded_in_writing():
    assert "regime_compatibility" in DECLINED_SUB_ITEMS
    assert "industry_relative" in DECLINED_SUB_ITEMS
    assert "trend_r2_quality" in RETIRED_MEMBERS  # the library's own double-listing
    assert "pvt" in RETIRED_MEMBERS
    res = momentum_score(_full_values())
    assert res["meta"]["regime_compatibility"]["value"] is None
    assert res["meta"]["regime_compatibility"]["declined"]


# ---------------------------------------------------------------------------
# MOM-6: the two members the tree lacked
# ---------------------------------------------------------------------------


def test_efficiency_ratio_is_the_library_formula():
    # A perfectly directional move of +1 per bar scores 1.0.
    assert efficiency_ratio([1, 2, 3, 4, 5, 6], 5) == pytest.approx(1.0)
    # A path that returns to its start scores 0.0.
    assert efficiency_ratio([5, 4, 5, 4, 5, 5], 5) == pytest.approx(0.0)
    assert efficiency_ratio([1, 2], 5) is None
    assert efficiency_ratio([3, 3, 3, 3], 3) is None  # no path -> no denominator


def test_positive_day_ratio_counts_up_days():
    assert positive_day_ratio([0.01, -0.01, 0.02, 0.0], 4) == pytest.approx(0.5)
    assert positive_day_ratio([0.01]) is None


# ---------------------------------------------------------------------------
# The leaf: gated off by default, renders under a real call
# ---------------------------------------------------------------------------


def _bars(n: int = 300) -> dict:
    closes, highs, lows, volumes = [], [], [], []
    for i in range(n):
        price = 100.0 + i * 0.4 + 3.0 * math.sin(i / 7.0)
        closes.append(price)
        highs.append(price + 1.0)
        lows.append(price - 1.0)
        volumes.append(1_000_000.0 + 200_000.0 * math.cos(i / 5.0))
    return {
        "dates": [f"2025-01-{i:03d}" for i in range(n)],
        "opens": list(closes),
        "closes": closes,
        "highs": highs,
        "lows": lows,
        "volumes": volumes,
    }


def _enable(monkeypatch, ticker: str = "TEST", on: bool = True):
    from tradingagents.agents.utils import analysis_tools as at

    bars = _bars()
    monkeypatch.setattr(at, "_ohlcv", lambda *_a, **_k: bars)
    monkeypatch.setattr(at, "_benchmark_closes", lambda: bars["closes"])
    monkeypatch.setattr(at, "_benchmark_bars", lambda: bars)
    monkeypatch.setattr(at, "_r3_flag", lambda name, default=False: on)
    # Keep the sector leg hermetic: no vendor label fetch in a unit test.
    import tradingagents.dataflows.yfinance_sector as yfs

    monkeypatch.setattr(yfs, "fetch_sector", lambda *_a, **_k: None)
    return at


def test_the_leaf_is_gated_off_by_default(monkeypatch):
    at = _enable(monkeypatch, on=False)
    out = at.get_momentum_score.invoke({"ticker": "TEST"})
    assert "gated off" in out
    assert "enable_momentum_score" in out


def test_the_leaf_computes_and_renders_every_leg(monkeypatch):
    at = _enable(monkeypatch, on=True)
    out = at.get_momentum_score.invoke({"ticker": "TEST"})
    assert "MomentumScore - TEST" in out
    for leg in LEG_ORDER:
        assert f"- {leg} (" in out, f"leg {leg} missing from the render"
    assert "meta (beside the score" in out
    assert "horizon conviction" in out
    assert "basis:" in out


def test_the_leaf_names_the_ratified_weights_and_keeps_the_status_honest(monkeypatch):
    """The owner ratified §47's numbers on 2026-09-27, so the leaf must say the
    table is owner-signed - and must STILL say RESEARCH_ONLY, because ratifying
    the weights is not the WP-10 measurement the VALIDATED rung needs."""
    at = _enable(monkeypatch, on=True)
    out = at.get_momentum_score.invoke({"ticker": "TEST"})
    assert "RATIFIED by the owner" in out
    assert "pending the owner's ratification" not in out
    assert "RESEARCH_ONLY" in out


def test_the_leaf_only_emits_declared_members_and_measures_the_key_ones(monkeypatch):
    """Guards the leaf->engine key contract (a misnamed key is a silent gap)."""
    at = _enable(monkeypatch, on=True)
    vals = at._momentum_components("TEST")
    assert set(vals) <= set(COMPONENTS), set(vals) - set(COMPONENTS)
    # The members the 300 synthetic bars carry must actually arrive - including
    # `sma_stack`, whose producer spells the state `stacked`.
    for key in (
        "r_5",
        "r_21",
        "r_63",
        "r_126",
        "r_252",
        "mom_12_1",
        "adx",
        "di_spread",
        "ma_distance",
        "sma_stack",
        "trend_r2",
        "macd_hist_accel",
        "donchian_252",
        "rvol",
        "pv_corr",
        "efficiency_ratio",
        "positive_day_ratio",
        "max_drawdown",
        "atr_pct",
    ):
        assert key in vals, key


def test_the_leaf_never_duplicates_a_producer_arithmetic():
    """MOM-4: TechnicalScore's owner vector is untouched by this engine."""
    from tradingagents.strategies.technical_score import CATEGORY_WEIGHTS

    assert CATEGORY_WEIGHTS["momentum"] == 18.0
    assert CATEGORY_WEIGHTS["relative_strength"] == 12.0
    assert CATEGORY_WEIGHTS["trend"] == 20.0
