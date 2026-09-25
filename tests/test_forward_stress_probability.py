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
from tradingagents.strategies.regime_score import (
    FORWARD_STRESS_KEY,
    MP_SPECTRUM_KEY,
    regime_score,
)

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


# --- X3's panel spectrum, printed through the same block --------------------


def test_the_panel_spectrum_prints_beside_the_score_without_displacing_r5() -> None:
    """X3 attaches under its OWN key, and only while its own gate is on.

    The gate registry row for ``enable_mp_lower_spectrum`` used to promise a
    count the engine never rendered (the read was computed into the breadth
    dict and dropped, and the run's call site did not even pass ``cfg``). It is
    PRINTED now, never scored - a panel-wide eigen-count is a backdrop, not a
    0-100 leg - and turning it on must not disturb R5's block.
    """
    panel = _panel()

    off = regime_score(_MID_VALUES, panel=panel)
    assert "printed" not in off

    set_config({"enable_mp_lower_spectrum": True})
    on = regime_score(_MID_VALUES, panel=panel)
    block = on["printed"][MP_SPECTRUM_KEY]
    assert block["status"] == "ok" and block["count"] is not None
    assert block["n_names"] == FS_MIN_NAMES  # one read for the whole panel
    assert {k: v for k, v in on.items() if k != "printed"} == off

    set_config(
        {"enable_mp_lower_spectrum": True, "enable_forward_stress_probability": True}
    )
    both = regime_score(_MID_VALUES, panel=panel)
    assert set(both["printed"]) == {MP_SPECTRUM_KEY, FORWARD_STRESS_KEY}


def test_the_printed_blocks_reach_the_report_text() -> None:
    """A printed block that only exists in the dict is not printed.

    ``RegimeScore`` renders its component table; the gated reads sit BESIDE it,
    so they render as their own lines rather than as a component.
    """
    from tradingagents.agents.utils.analysis_tools import _render_regime_score

    res = {
        "score": 50.0,
        "band": "neutral",
        "status": "RESEARCH_ONLY",
        "coverage": 1.0,
        "components": {},
        "basis": "basis",
        "printed": {
            MP_SPECTRUM_KEY: {
                "count": 9, "mp_lower": 0.25, "status": "ok",
                "window": 44, "n_names": 11, "panel_n": 11, "unavailable": None,
            }
        },
    }
    text = _render_regime_score(res, None)
    assert "printed mp_lower_spectrum:" in text
    assert "count=9" in text and "n_names=11" in text
    # gate off -> the key is absent -> nothing is rendered for it
    assert "printed" not in _render_regime_score({**res, "printed": {}}, None)


def test_the_run_read_passes_its_config_into_the_breadth_producer(monkeypatch) -> None:
    """The engine's own call site must pass the run's config.

    ``_market_breadth_read`` called ``market_breadth(panel)`` with ``cfg=None``,
    so no ``cfg``-driven producer behaviour (X3's switch among them) was
    reachable from a run; and the panel it builds is now cached for the printed
    reads so they share ONE cross-section.
    """
    from tradingagents.agents.utils import analysis_tools as A
    from tradingagents.dataflows import market_panel
    from tradingagents.strategies import market_breadth as MB

    panel = _panel()
    monkeypatch.setattr(market_panel, "market_closes", lambda fetch: dict(panel))
    monkeypatch.setattr(A, "_RUN_BREADTH_CACHE", {})
    seen: dict = {}
    real = MB.market_breadth

    def spy(closes_by_name, **kw):
        seen["cfg"] = kw.get("cfg")
        return real(closes_by_name, **kw)

    monkeypatch.setattr(MB, "market_breadth", spy)
    set_config({"enable_mp_lower_spectrum": True})

    read = A._market_breadth_read() or {}
    assert (seen.get("cfg") or {}).get("enable_mp_lower_spectrum") is True
    assert (read.get("mp_lower_spectrum") or {}).get("status") == "ok"
    assert set(A._market_panel()) == set(panel)  # one panel, shared
