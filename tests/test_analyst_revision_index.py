"""S6 - analyst revision / estimate-change index (MSCI recipe, coverage-guarded).

Docs: ``docs/implementation_plan_quant_formula_additions_round3.md`` S6 and §4.

Gates: the hand-computed three-period weighted ratio (weights 3/2/1); the
one-action window -> ``unavailable``; the estimate-change leg unavailable with
the missing-input reason; the +/-3 z-clip visible on an outlier fixture; and the
tool layer (flag-off DISABLED sentinel, rendered rows, honest degradation) with
``fetch_revision_actions`` monkeypatched - no network.
"""

from __future__ import annotations

import pytest

from tradingagents.agents.utils import analyst_revision_tools as art
from tradingagents.strategies.analyst_revisions import (
    estimate_change_index,
    revision_index,
    revision_ratio,
    winsor_z,
)

# --- revision_ratio: the hand-computed weighted example ----------------------


def test_revision_ratio_reproduces_the_hand_computed_three_period_example():
    # r0 = (3-1)/4 = 0.5; r1 = (1-1)/2 = 0; r2 = (0-2)/2 = -1
    # 3*0.5 + 2*0 + 1*(-1) = 0.5
    history = [
        {"up": 3, "down": 1},
        {"up": 1, "down": 1},
        {"up": 0, "down": 2},
    ]
    read = revision_ratio(history)
    assert read["index"] == pytest.approx(0.5)
    assert read["weights_applied"] == [3.0, 2.0, 1.0]
    assert read["coverage"] == 8
    assert read["periods_used"] == 3
    # the unweighted mean ships beside the weighted one: (0.5+0-1)/3
    assert read["ratio"] == pytest.approx(-1.0 / 6.0)
    assert "denominator=up+down" in read["basis"]
    assert "deviation" in read["basis"].lower()


def test_revision_ratio_weights_the_recent_period_hardest():
    # same three ratio legs, reversed recency: the newest leg dominates
    history = [
        {"up": 1, "down": 0},
        {"up": 0, "down": 0},
        {"up": 0, "down": 1},
    ]
    read = revision_ratio(history)
    # 3*1 + 2*0 + 1*(-1) = 2
    assert read["index"] == pytest.approx(2.0)


def test_revision_ratio_accepts_the_net_augmented_count_shape():
    read = revision_ratio([{"up": 2, "down": 1, "net": 1}])
    # one aggregate window -> the leading weight (3) applies to (2-1)/3 = 1/3
    assert read["index"] == pytest.approx(1.0)
    assert read["coverage"] == 3
    assert read["periods_used"] == 1
    assert read["weights_applied"] == [3.0]


# --- coverage guard ----------------------------------------------------------


def test_revision_ratio_one_action_window_is_unavailable():
    read = revision_ratio([{"up": 1, "down": 0}])
    assert read["index"] is None
    assert read["coverage"] == 1
    assert "coverage guard" in read["unavailable"]
    assert "2" in read["unavailable"]


def test_revision_ratio_exactly_two_actions_is_available():
    read = revision_ratio([{"up": 1, "down": 1}])
    assert read["index"] == pytest.approx(0.0)
    assert read["coverage"] == 2


def test_revision_ratio_missing_up_down_counts_is_unavailable():
    read = revision_ratio([{"net": 2}])
    assert read["index"] is None
    assert "no period with both up and down counts" in read["unavailable"]


# --- estimate_change_index ---------------------------------------------------


def test_estimate_change_index_hand_computed_five_level_series():
    # most-recent-first; symmetric % change per lag, weights 9/7/5/3
    levels = [110.0, 100.0, 90.0, 80.0, 70.0]
    changes = [
        (110 - 100) / ((110 + 100) / 2),
        (100 - 90) / ((100 + 90) / 2),
        (90 - 80) / ((90 + 80) / 2),
        (80 - 70) / ((80 + 70) / 2),
    ]
    expected = 9 * changes[0] + 7 * changes[1] + 5 * changes[2] + 3 * changes[3]
    read = estimate_change_index(levels)
    assert read["index"] == pytest.approx(expected)
    assert read["changes"] == pytest.approx(changes)
    assert read["weights"] == [9.0, 7.0, 5.0, 3.0]


def test_estimate_change_index_short_series_is_unavailable_with_the_reason():
    read = estimate_change_index([110.0, 100.0, 90.0, 80.0])
    assert read["index"] is None
    assert read["unavailable"]
    assert "need 5" in read["unavailable"]
    assert "consensus" in read["unavailable"]
    assert "never fabricated" in read["unavailable"]


def test_estimate_change_index_none_and_empty_are_unavailable():
    for levels in (None, []):
        read = estimate_change_index(levels)
        assert read["index"] is None
        assert read["n_supplied"] == 0


def test_estimate_change_index_zero_levels_is_unavailable():
    read = estimate_change_index([0, 0, 0, 0, 0])
    assert read["index"] is None
    assert "zero denominator" in read["unavailable"]


# --- winsor_z ----------------------------------------------------------------


def test_winsor_z_clips_the_outlier_at_three():
    values = [7.0] * 11 + [1000.0]
    read = winsor_z(values)
    assert read is not None
    assert max(read["raw_z"]) > 3.0, "the fixture must actually breach the cap"
    assert max(read["z"]) == pytest.approx(3.0)
    assert all(abs(v) <= 3.0 for v in read["z"])
    assert read["n_clipped"] == 1
    assert "3" in read["basis"]


def test_winsor_z_none_below_two_observations_or_zero_dispersion():
    assert winsor_z([1.0]) is None
    assert winsor_z([5.0, 5.0, 5.0]) is None


# --- revision_index assembly -------------------------------------------------


def test_revision_index_assembles_the_available_leg_with_its_basis():
    history = [
        {"up": 3, "down": 1},
        {"up": 1, "down": 1},
        {"up": 0, "down": 2},
    ]
    read = revision_index(history)
    assert read["index"] == pytest.approx(0.5)  # only the revision leg is available
    assert read["legs"]["revision_ratio"] == pytest.approx(0.5)
    assert read["legs"]["estimate_change"] is None
    assert read["available"] == ["revision_ratio"]
    assert "estimate_change" in read["unavailable"]
    assert read["coverage"] == 8
    assert read["gates"] is False
    assert "never gates" in read["basis"]
    assert "denominator=up+down" in read["basis"]


def test_revision_index_coverage_failure_leaves_no_index():
    read = revision_index([{"up": 1, "down": 0}])
    assert read["index"] is None
    assert read["available"] == []
    assert "revision_ratio" in read["unavailable"]


def test_revision_index_averages_both_legs_when_levels_are_supplied():
    history = [{"up": 3, "down": 1}, {"up": 1, "down": 1}, {"up": 0, "down": 2}]
    read = revision_index(history, levels=[110.0, 100.0, 90.0, 80.0, 70.0])
    assert set(read["available"]) == {"revision_ratio", "estimate_change"}
    assert read["index"] == pytest.approx(
        (read["legs"]["revision_ratio"] + read["legs"]["estimate_change"]) / 2.0
    )
    assert read["unavailable"] == {}


# --- the tool layer (fetch_revision_actions monkeypatched, offline) ----------


def _cfg(monkeypatch, **flags):
    base = {"results_dir": "/nonexistent-results-dir"}
    base.update(flags)
    monkeypatch.setattr("tradingagents.dataflows.config.get_config", lambda: base)
    return base


def _patch_source(monkeypatch, result=None, exc=None):
    import tradingagents.dataflows.yfinance_sector as ys

    def fake(ticker, days=60, timeout=12.0):
        if exc is not None:
            raise exc
        return result

    monkeypatch.setattr(ys, "fetch_revision_actions", fake)


def test_tool_is_a_disabled_sentinel_while_the_flag_is_off(monkeypatch):
    _cfg(monkeypatch)
    out = art.get_analyst_revision_index.invoke({"ticker": "TEST", "current_date": "2026-09-13"})
    assert "DISABLED" in out
    assert "enable_analyst_revision_index" in out
    assert "No value computed" in out


def test_tool_renders_the_weighted_index_and_the_estimate_unavailable(monkeypatch):
    _cfg(monkeypatch, enable_analyst_revision_index=True)
    _patch_source(monkeypatch, {"up": 3, "down": 1, "net": 2})
    out = art.get_analyst_revision_index.invoke({"ticker": "TEST", "current_date": "2026-09-13"})
    assert "analyst revision index TEST" in out
    assert "+1.5000" in out  # 3 * (3-1)/(3+1)
    assert "coverage=4" in out
    assert "denominator=up+down" in out
    assert "estimate_change: unavailable" in out
    assert "consensus" in out


def test_tool_reports_the_coverage_guard_on_a_one_action_window(monkeypatch):
    _cfg(monkeypatch, enable_analyst_revision_index=True)
    _patch_source(monkeypatch, {"up": 1, "down": 0, "net": 1})
    out = art.get_analyst_revision_index.invoke({"ticker": "TEST", "current_date": "2026-09-13"})
    assert "analyst revision index unavailable for TEST" in out
    assert "coverage guard" in out


def test_tool_reports_unavailable_when_the_source_returns_nothing(monkeypatch):
    _cfg(monkeypatch, enable_analyst_revision_index=True)
    _patch_source(monkeypatch, None)
    out = art.get_analyst_revision_index.invoke({"ticker": "TEST", "current_date": "2026-09-13"})
    assert "analyst revision index unavailable for TEST" in out
    assert "no upgrade/downgrade actions" in out


def test_tool_reports_unavailable_on_a_source_error(monkeypatch):
    _cfg(monkeypatch, enable_analyst_revision_index=True)
    _patch_source(monkeypatch, exc=RuntimeError("no network"))
    out = art.get_analyst_revision_index.invoke({"ticker": "TEST", "current_date": "2026-09-13"})
    assert "analyst revision index unavailable for TEST" in out
    assert "no network" in out


def test_tool_exports_its_list():
    assert len(art.ANALYST_REVISION_TOOLS) == 1
    assert art.ANALYST_REVISION_TOOLS[0] is art.get_analyst_revision_index
    assert set(art.get_analyst_revision_index.args) == {"ticker", "current_date"}
