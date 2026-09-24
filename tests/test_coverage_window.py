"""H10: the coverage window and the padded-panel refusal.

``coverage_window`` reads when a symbol's series begins; ``data_quality``
refuses to compute a panel statistic over a padded window (ground rule 4:
coverage travels with the number).
"""

from __future__ import annotations

import pandas as pd

from tradingagents.strategies.coverage_window import (
    SURVIVOR_ONLY,
    coverage_window,
)
from tradingagents.strategies.data_quality import panel_statistic


def _frame(leading_missing: int = 40, n: int = 100) -> pd.Series:
    """A calendar-aligned panel: ``leading_missing`` NaN positions then bars."""
    index = pd.bdate_range("2020-01-01", periods=n)
    values = [float("nan")] * leading_missing
    values += [float(i + 1) for i in range(n - leading_missing)]
    return pd.Series(values, index=index)


def _gate(monkeypatch, on: bool) -> None:
    """Flip ``enable_coverage_window`` at the config accessor the read uses."""
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"enable_coverage_window": on},
    )


def test_padded_panel_is_unavailable(monkeypatch):
    """A panel with 40 leading NaNs is padded by 40, and the dependent panel
    statistic reads ``unavailable`` - never a number. Removing the
    ``padded_days > 0`` refusal branch of ``panel_statistic`` fails this test.
    """
    _gate(monkeypatch, on=True)
    padded = _frame(40)

    window = coverage_window(padded)
    assert window["padded_days"] == 40
    assert window["n_bars"] == 60
    assert window["unavailable"] is None
    assert window["alignment"] == "calendar-aligned"

    stat = panel_statistic(padded)
    assert stat["statistic"] is None
    assert stat["unavailable"]

    dense = _frame(0)
    dense_window = coverage_window(dense)
    assert dense_window["padded_days"] == 0

    dense_stat = panel_statistic(dense)
    assert dense_stat["unavailable"] is None
    expected = sum(float(i + 1) for i in range(100)) / 100
    assert dense_stat["statistic"] == expected


def test_gate_off_computes_the_statistic_without_reading_the_window(monkeypatch):
    """The gate is what makes the refusal reachable, and it is off by default:
    with it off the padded frame is averaged exactly as a caller did before H10
    existed, and the record says no window was read."""
    _gate(monkeypatch, on=False)

    stat = panel_statistic(_frame(40))
    assert stat["window"] is None
    assert stat["unavailable"] is None
    assert stat["n"] == 60
    assert stat["statistic"] == sum(float(i + 1) for i in range(60)) / 60


def test_a_list_is_accepted_and_labels_are_positions():
    series = [float("nan")] * 3 + [1.0, 2.0, 3.0]
    window = coverage_window(series)
    assert window["padded_days"] == 3
    assert window["n_bars"] == 3
    assert window["alignment"] == "positional"
    assert (window["first_valid"], window["last_valid"]) == (3, 5)


def test_empty_and_all_missing_degrade_not_to_zero_coverage(monkeypatch):
    _gate(monkeypatch, on=True)
    empty = coverage_window([])
    assert empty["n_bars"] == 0
    assert empty["first_valid"] is None
    assert empty["unavailable"]

    all_nan = coverage_window([float("nan"), float("nan")])
    assert all_nan["n_bars"] == 0
    assert all_nan["unavailable"]
    assert panel_statistic([float("nan")])["statistic"] is None
    assert SURVIVOR_ONLY == "survivor_only"
