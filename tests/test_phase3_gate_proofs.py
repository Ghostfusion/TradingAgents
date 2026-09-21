"""The two Phase-3 data-surface gates must actually fire.

`docs/gate_registry.md` §8 requires, for every gate, "a test that **fails when
the gate is ignored**". `enable_options_surface` and `enable_risk_free_curve`
shipped without one: the existing tests (`test_cboe.py`,
`test_federal_reserve.py`) prove the *vendor* and the *routing*, but every one
of them calls the vendor function directly or routes with the gate untouched -
so nothing failed if the gate was removed and the tools always fetched.

These tests close that hole. Each asserts the observable contract: with the gate
off the tool returns a DISABLED sentinel and **does not reach the router**; with
it on it does.
"""

from __future__ import annotations

from unittest import mock

import pytest

from tradingagents.agents.utils import analysis_tools
from tradingagents.dataflows.config import reset_config, set_config


@pytest.fixture(autouse=True)
def _isolate_config():
    """Each case gets a clean thread-local config, then the default back."""
    reset_config()
    yield
    reset_config()


CASES = [
    ("get_options_surface", {"ticker": "AAPL"}, "enable_options_surface"),
    ("get_sofr_curve", {}, "enable_risk_free_curve"),
    ("get_treasury_curve", {}, "enable_risk_free_curve"),
]


@pytest.mark.parametrize("name,kwargs,gate", CASES)
def test_gate_off_returns_a_sentinel_and_never_fetches(name, kwargs, gate):
    """The whole point of the gate: off means no request, not a silent fetch."""
    set_config({gate: False})
    tool = getattr(analysis_tools, name)
    with mock.patch.object(analysis_tools, "route_to_vendor") as router:
        out = tool.invoke(kwargs)
    router.assert_not_called()
    assert "DATA_DISABLED" in out
    # the sentinel names the key (underscores rendered as spaces) and the env var
    assert gate.replace("_", " ") in out
    assert f"TRADINGAGENTS_{gate.upper()}" in out


@pytest.mark.parametrize("name,kwargs,gate", CASES)
def test_gate_on_reaches_the_router(name, kwargs, gate):
    """On means the tool is a thin pass-through - no second producer."""
    set_config({gate: True})
    tool = getattr(analysis_tools, name)
    with mock.patch.object(analysis_tools, "route_to_vendor", return_value="OK") as router:
        out = tool.invoke(kwargs)
    assert out == "OK"
    assert router.call_count == 1


def test_a_broken_config_degrades_to_off_not_on():
    """A gate that cannot be read must never let a tool pretend data exists."""
    from tradingagents.agents.utils.analysis_tools import _feature_gate

    with mock.patch(
        "tradingagents.dataflows.config.get_config",
        side_effect=RuntimeError("config exploded"),
    ):
        sentinel = _feature_gate("enable_options_surface", "TRADINGAGENTS_ENABLE_OPTIONS_SURFACE")
    assert sentinel is not None and "DATA_DISABLED" in sentinel
