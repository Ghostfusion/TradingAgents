"""Phase 4 of the entry/exit price engine: the risk-adjusted maximum entry.

``risk_adjusted_entry`` is §68's ceiling from the stop-distance rule,
``E_max = S / (1 - f)``, plus §87/§88's CVaR permission half reported as a
**status** - a name over the book's budget cannot be entered at any price, so
folding it into a number would misstate it.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.risk_entry import CVAR_STATUSES, risk_adjusted_entry

pytestmark = pytest.mark.timeout(600)


def test_max_entry_solves_the_stop_distance_rule():
    out = risk_adjusted_entry(stop=95.0, max_stop_fraction=0.10)
    assert out["value"] == pytest.approx(95.0 / 0.90)
    assert out["status"] == "OK"
    assert out["stop_fraction"] == pytest.approx(0.10)


def test_a_tighter_stop_fraction_raises_the_ceiling():
    tight = risk_adjusted_entry(stop=95.0, max_stop_fraction=0.05)
    loose = risk_adjusted_entry(stop=95.0, max_stop_fraction=0.20)
    assert tight["value"] < loose["value"]


def test_no_stop_is_no_source_never_a_fallback_price():
    out = risk_adjusted_entry(max_stop_fraction=0.10)
    assert out["value"] is None
    assert out["status"] == "NO_SOURCE"
    assert out["reason"]


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -0.01, 1.0, 2.0, "n/a", True])
def test_unusable_stop_fraction_is_absent(bad):
    out = risk_adjusted_entry(stop=95.0, max_stop_fraction=bad)
    assert out["value"] is None
    assert out["status"] == "NO_SOURCE"


def test_cvar_over_budget_is_a_status_not_a_price():
    """The AMD run's binding constraint: name CVaR 9% vs a 3% budget."""
    out = risk_adjusted_entry(
        stop=95.0, max_stop_fraction=0.10, name_cvar=0.09, cvar_budget=0.03
    )
    assert out["cvar_status"] == "OVER_BUDGET"
    # the price is still reported - the permission is separate
    assert out["value"] == pytest.approx(95.0 / 0.90)
    assert out["status"] == "OK"


def test_cvar_within_budget_is_ok():
    out = risk_adjusted_entry(
        stop=95.0, max_stop_fraction=0.10, name_cvar=0.02, cvar_budget=0.03
    )
    assert out["cvar_status"] == "OK"


def test_cvar_absent_without_both_terms():
    assert risk_adjusted_entry(stop=95.0, max_stop_fraction=0.10)["cvar_status"] == "NO_SOURCE"
    assert (
        risk_adjusted_entry(stop=95.0, max_stop_fraction=0.10, name_cvar=0.02)["cvar_status"]
        == "NO_SOURCE"
    )
    assert set(CVAR_STATUSES) == {"OK", "OVER_BUDGET", "NO_SOURCE"}
