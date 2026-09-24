"""R5 (2602.07066): a calibrated forward stress probability from the cross-section.

The read is IN-SAMPLE calibrated and the calibration report is PART of the output,
because an uncalibrated probability is a score wearing a probability's name. The
horizon is stated in the output, never implied by the caller.

Offline and deterministic: the panel is synthetic with a fixed seed, no vendor
call, no wall clock and no network.
"""

from __future__ import annotations

import numpy as np
import pytest

from tradingagents.dataflows.config import reset_config, set_config
from tradingagents.strategies.market_breadth import (
    FS_MIN_BIN_N,
    FS_MIN_NAMES,
    forward_stress_probability,
)
from tradingagents.strategies.regime_score import FORWARD_STRESS_KEY, regime_score

#: The gate dict the producer takes directly (its own read, by its literal name).
ON = {"enable_forward_stress_probability": True}

_MONTHS = 30
_SESSIONS = 21
_BARS = _MONTHS * _SESSIONS + 1

_MID_VALUES = {
    "market_trend": 0.06,
    "breadth": 60.0,
    "vix_percentile": 0.30,
    "vix_term_structure": 0.95,
    "choppiness": 35.0,
    "realized_vol_percentile": 0.30,
}


def _panel(names: int = FS_MIN_NAMES, *, seed: int = 11) -> dict:
    """A deterministic cross-section: heterogeneous vol, then a two-month selloff.

    Fixed seed and no vendor call - the panel is the fixture, not a market
    observation, so the read is reproducible.
    """
    rng = np.random.default_rng(seed)
    out = {}
    for i in range(names):
        vol = 0.01 + 0.02 * (i / max(1, names - 1))
        steps = rng.normal(0.0, vol, _BARS - 1)
        steps[-2 * _SESSIONS:] -= 0.004  # a stress episode, so the outcome is observed
        out[f"N{i:02d}"] = list(100.0 * np.cumprod(1.0 + steps))
    return out


def teardown_function() -> None:
    reset_config()


def test_the_probability_carries_its_calibration_report() -> None:
    """Acceptance: ``p_stress`` never travels without the report behind it, the
    horizon is stated in the output, and a cross-section too thin to calibrate is
    ``unavailable``, never a number."""
    out = forward_stress_probability(_panel(), cfg=ON)

    assert out["status"] == "ok"
    assert out["p_stress"] is not None and 0.0 <= out["p_stress"] <= 1.0
    assert out["horizon"]["months"] == 1
    assert out["horizon"]["label"] == "one-month-ahead"
    assert out["horizon"]["sessions"] == _SESSIONS

    # The calibration report is PRESENT whenever p_stress is, and p_stress IS the
    # current band's realised hit rate - the number and its reliability are one
    # object, not a score beside a report.
    assert "calibration" in out and isinstance(out["calibration"], dict)
    cal = out["calibration"]
    assert cal["table"], "the calibration report must carry its bands"
    band = out["fragility"]["band"]
    row = next(r for r in cal["table"] if r["bin"] == band)
    assert out["p_stress"] == pytest.approx(row["actual_hit_rate"])
    assert row["n"] >= FS_MIN_BIN_N
    assert cal["stress_months"] >= 1

    # A cross-section too thin to calibrate: the denominator rule withholds the
    # probability with its reason rather than fitting one on a handful of names.
    thin = forward_stress_probability(_panel(names=FS_MIN_NAMES - 1), cfg=ON)
    assert thin["status"] == "unavailable"
    assert thin["p_stress"] is None
    assert thin["calibration"] is None
    assert str(FS_MIN_NAMES) in thin["unavailable"]


def test_the_read_is_gated_off_by_default_and_refuses() -> None:
    """ADDITIVE and default-OFF: with the gate off the read is refused by name,
    never computed, so a gate-off run gains nothing."""
    out = forward_stress_probability(_panel(), cfg={})
    assert out["status"] == "unavailable"
    assert out["p_stress"] is None
    assert "enable_forward_stress_probability" in out["unavailable"]


def test_the_read_is_printed_beside_the_score_and_never_scored() -> None:
    """R5 lands PRINTED in `regime_score`: the block appears only with the gate on
    and every SCORED key is byte-identical to the gate-off run."""
    off = regime_score(_MID_VALUES)
    assert "printed" not in off

    set_config({"enable_forward_stress_probability": True})
    on = regime_score(_MID_VALUES, panel=_panel())

    assert on["printed"][FORWARD_STRESS_KEY]["status"] == "ok"
    assert {k: v for k, v in on.items() if k != "printed"} == off
