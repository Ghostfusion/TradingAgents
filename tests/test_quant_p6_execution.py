"""Tests for Phase 6: Almgren-Chriss + TWAP/VWAP/POV execution schedules."""

import pytest

from tradingagents.strategies.execution_schedule import (
    almgren_chriss,
    pov_schedule,
    twap_schedule,
    vwap_schedule,
)

pytestmark = pytest.mark.timeout(60)


def test_almgren_chriss_boundary_and_shape():
    ac = almgren_chriss(10000, 10, 0.02, 1e-6, 1e-6)
    assert ac["schedule"]
    assert ac["schedule"][0][1] < 10000  # remaining decreases
    assert ac["schedule"][-1][1] == 0.0  # fully liquidated
    # front-loaded: the first trade is the largest
    vs = [v for _, _, v in ac["schedule"]]
    assert vs[0] > vs[-1]
    assert ac["kappa"] is not None and ac["e_is"] is not None


def test_almgren_chriss_none_safe():
    assert almgren_chriss(0, 10, 0.02, 1e-6, 1e-6)["schedule"] == []
    assert almgren_chriss(100, 0, 0.02, 1e-6, 1e-6)["schedule"] == []
    assert almgren_chriss(None, 10, 0.02, 1e-6, 1e-6)["schedule"] == []


def test_twap_uniform():
    t = twap_schedule(10000, 5)["schedule"]
    assert len(t) == 5
    assert t[-1][1] == 0.0
    assert all(v == pytest.approx(2000.0) for _, _, v in t)


def test_vwap_volume_weighted():
    v = vwap_schedule(100, [10, 20, 10, 60])["schedule"]
    assert [round(tr, 1) for _, _, tr in v] == [10.0, 20.0, 10.0, 60.0]
    assert v[-1][1] == 0.0


def test_pov_participation_control():
    p = pov_schedule(1000, 500, 0.10)
    assert p["schedule"][0][2] == pytest.approx(50.0)  # 10% of 500
    # completes in 20 intervals (1000/50)
    assert p["n"] == 20
    assert pov_schedule(1000, 500, 0.20)["n"] == 10


def test_pov_none_safe():
    assert pov_schedule(1000, 0, 0.10)["schedule"] == []
    assert pov_schedule(1000, 500, 2.0)["schedule"] == []  # participation > 1
