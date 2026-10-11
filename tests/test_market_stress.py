"""The turbulence index, its own-history gate, and the tool/gate wiring."""

import random

import pytest

from tradingagents.dataflows.config import get_config, set_config
from tradingagents.strategies.market_stress import (
    turbulence_index,
    turbulence_read,
)

pytestmark = pytest.mark.timeout(120)


def _panel(n_names=5, n_obs=60, shock=False, seed=3):
    rng = random.Random(seed)
    panel = {}
    for i in range(n_names):
        series = [rng.gauss(0.0, 0.01) for _ in range(n_obs)]
        if shock and i == 0:
            series[-1] = 0.06
        panel[f"N{i}"] = series
    return panel


def test_a_shock_scores_above_a_quiet_window():
    quiet = turbulence_index(_panel(n_obs=40), min_obs=5)
    shocked = turbulence_index(_panel(n_obs=40, shock=True), min_obs=5)
    assert quiet is not None and shocked is not None
    assert quiet["index"] is not None and quiet["index"] > 0.0
    assert shocked["index"] > quiet["index"]


def test_the_scored_cross_section_is_excluded_from_its_own_window():
    rng = random.Random(11)
    panel = {f"N{i}": [rng.gauss(0.0, 0.01) for _ in range(30)] + [0.03 * (i + 1)]
             for i in range(4)}
    default = turbulence_index(panel, min_obs=5)
    assert default is not None
    assert default["index"] is not None
    assert default["n_obs"] == 30  # the scored row is dropped
    # An explicit target is the caller's own convention: it scores that vector
    # against EVERY observation the panel carries (no row is dropped).
    explicit = turbulence_index(
        panel, target={f"N{i}": 0.03 * (i + 1) for i in range(4)}, min_obs=5
    )
    assert explicit is not None
    assert explicit["index"] is not None and explicit["n_obs"] == 31


def test_sigma_is_the_engine_shrink_with_a_reported_intensity():
    read = turbulence_index(_panel(), min_obs=5)
    raw = turbulence_index(_panel(), min_obs=5, shrinkage=False)
    assert read is not None and raw is not None
    assert read["shrinkage"] is not None and 0.0 <= read["shrinkage"] <= 1.0
    assert raw["shrinkage"] is None and raw["unavailable"] is None


def test_a_singular_covariance_refuses_rather_than_inverting():
    read = turbulence_index({"A": [0.01] * 20, "B": [0.02] * 20}, min_obs=5,
                            shrinkage=False)
    assert read is not None
    assert read["index"] is None
    assert "singular" in read["unavailable"]


def test_read_gates_on_its_own_history_and_refuses_below_the_floor():
    read = turbulence_read(_panel(n_obs=80, shock=True), min_obs=5, min_history=20)
    assert read["gate"] is True and read["threshold"] is not None
    assert read["latest"] > read["threshold"]
    assert read["n_points"] > 20
    thin = turbulence_read(_panel(n_obs=8), min_obs=5, min_history=20)
    assert thin["gate"] is None and thin["unavailable"]


def test_a_one_name_panel_has_no_cross_section():
    assert turbulence_index({"A": [0.01, 0.02, 0.03]}) is None
    read = turbulence_read({"A": [0.01, 0.02, 0.03]})
    assert read["n_dim"] == 1 and read["gate"] is None and read["unavailable"]


def test_the_tool_is_gated_off_by_default_and_renders_when_switched_on(monkeypatch):
    """The gate, the tool, and the panel it reads - all through the real loader."""
    from tradingagents.agents.utils import analysis_tools

    saved = dict(get_config())
    set_config({**saved, "enable_turbulence_read": False})
    try:
        off = analysis_tools.get_turbulence_read.invoke({"ticker": "SPY"})
        assert "DATA_DISABLED" in off and "TRADINGAGENTS_ENABLE_TURBULENCE_READ" in off

        rng = random.Random(4)
        closes = [100.0]
        for _ in range(80):
            closes.append(closes[-1] * (1.0 + rng.gauss(0.0005, 0.01)))
        monkeypatch.setattr(
            analysis_tools, "_ohlcv", lambda ticker, days=320: {"closes": list(closes)}
        )
        set_config({**saved, "enable_turbulence_read": True})
        on = analysis_tools.get_turbulence_read.invoke(
            {"ticker": "SPY", "names": ["SPY", "QQQ", "IWM"]}
        )
        assert "Market Turbulence Read" in on
        assert "caller-supplied" in on
        assert "gate:" in on
    finally:
        set_config(saved)
