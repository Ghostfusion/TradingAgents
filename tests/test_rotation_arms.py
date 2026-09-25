"""The rotation backtest's arms: absolute momentum against a cash proxy.

The shipped arm (relative top-N) must not change, so the gated arm is reported
BESIDE it: `abs_gate` shunts each slot that fails its own absolute-momentum
hurdle against the risk-off proxy into that proxy. It is absent unless a cash
series is supplied, and an unmeasurable hurdle cannot move a position.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.sector_screener import backtest_rotation

pytestmark = pytest.mark.timeout(180)

N = 400
MIN_BARS = 65


def _series(n=N, *, rate=0.001, start=100.0):
    out, px = [], start
    for _ in range(n):
        px *= 1 + rate
        out.append(px)
    return out


def _up_then_down(n=N, *, up=0.004, down=-0.004, switch=0.5):
    out, px = [], 100.0
    for i in range(n):
        px *= 1 + (up if i < n * switch else down)
        out.append(px)
    return out


def _rotating_pool():
    """Four sectors whose ranks ROTATE: two steady, one up-then-down, one the
    mirror image - so the relative top-3 has to change hands at least once."""
    mirror = []
    px = 100.0
    for i in range(N):
        px *= 1 + (-0.004 if i < N * 0.5 else 0.004)
        mirror.append(px)
    return {
        "E1": _series(rate=0.0008),
        "E2": _series(rate=0.0009),
        "E3": _up_then_down(),
        "E4": mirror,
    }


BENCH = _series(rate=0.0008)


@pytest.mark.unit
def test_the_gated_arm_is_absent_without_a_cash_series():
    bt = backtest_rotation(_rotating_pool(), BENCH, min_bars=MIN_BARS)
    assert bt["abs_gate"] is None
    assert bt["strategy"]


@pytest.mark.unit
def test_the_shipped_arm_is_unchanged_by_the_new_parameters():
    """The arm is additive: the relative-momentum series must not move."""
    pool = _rotating_pool()
    base = backtest_rotation(pool, BENCH, min_bars=MIN_BARS)
    extended = backtest_rotation(
        pool,
        BENCH,
        min_bars=MIN_BARS,
        abs_momentum_window=21,
        cash_closes=_series(rate=0.002),
    )
    assert extended["strategy"] == base["strategy"]
    assert extended["turns"] == base["turns"]
    assert extended["equal"] == base["equal"]
    assert extended["bench"] == base["bench"]
    assert extended["abs_gate"] is not None


@pytest.mark.unit
def test_the_arm_aligns_with_the_baseline_series():
    pool = _rotating_pool()
    bt = backtest_rotation(
        pool, BENCH, min_bars=MIN_BARS, cash_closes=_series(rate=0.002)
    )
    n_expected = len(bt["strategy"])
    assert n_expected == N - MIN_BARS - 1
    assert len(bt["abs_gate"]["strategy"]) == n_expected


@pytest.mark.unit
def test_sectors_that_beat_cash_leave_the_arm_identical_to_the_baseline():
    # Every sector rises steadily and outruns the proxy at every horizon, so no
    # slot can be gated.
    pool = {f"E{i}": _series(rate=0.001 + i * 0.0001) for i in range(4)}
    cash = _series(rate=0.0001)
    bt = backtest_rotation(pool, BENCH, min_bars=MIN_BARS, cash_closes=cash)
    arm = bt["abs_gate"]
    assert arm is not None
    assert arm["gated_rebalances"] == 0
    assert arm["cash_weight_avg"] == 0.0
    assert arm["strategy"] == bt["strategy"]
    assert arm["turns"] == bt["turns"]


@pytest.mark.unit
def test_sectors_that_lose_to_cash_shunt_every_slot_to_the_risk_off_leg():
    pool = {f"E{i}": _series(rate=0.0002) for i in range(4)}
    cash = _series(rate=0.002)
    bt = backtest_rotation(pool, BENCH, min_bars=MIN_BARS, cost_bps=0.0, cash_closes=cash)
    arm = bt["abs_gate"]
    assert arm is not None
    assert arm["cash_weight_avg"] == 1.0
    assert arm["gated_rebalances"] >= 1
    # With every slot in the risk-off leg, each bar IS the cash proxy's return.
    expected = [cash[i + 1] / cash[i] - 1.0 for i in range(MIN_BARS, N - 1)]
    assert arm["strategy"] == pytest.approx(expected)


@pytest.mark.unit
def test_an_unmeasurable_hurdle_never_gates():
    """A window longer than the series leaves the hurdle unmeasured: the arm
    must then equal the baseline rather than assume anything."""
    pool = _rotating_pool()
    bt = backtest_rotation(
        pool,
        BENCH,
        min_bars=MIN_BARS,
        abs_momentum_window=10_000,
        cash_closes=_series(rate=0.002),
    )
    arm = bt["abs_gate"]
    assert arm is not None
    assert arm["gated_rebalances"] == 0
    assert arm["cash_weight_avg"] == 0.0
    assert arm["strategy"] == bt["strategy"]


@pytest.mark.unit
def test_the_buffer_is_absent_unless_asked_for():
    bt = backtest_rotation(_rotating_pool(), BENCH, min_bars=MIN_BARS)
    assert bt["hysteresis"] is None


@pytest.mark.unit
def test_hysteresis_holds_a_name_just_outside_the_cut_and_cuts_turnover():
    pool = _rotating_pool()
    bt = backtest_rotation(pool, BENCH, min_bars=MIN_BARS, hysteresis_ranks=3)
    arm = bt["hysteresis"]
    assert arm is not None
    assert bt["turns"] > 0, "the fixture must actually rotate the top-3"
    assert arm["held_over"] >= 1
    assert arm["turns"] < bt["turns"]
    assert arm["cash_weight_avg"] == 0.0


@pytest.mark.unit
def test_hysteresis_still_drops_a_name_that_fails_the_hurdle():
    """The buffer is not a licence to hold a sector losing to cash."""
    pool = {f"E{i}": _series(rate=0.0002) for i in range(4)}
    cash = _series(rate=0.002)
    bt = backtest_rotation(
        pool,
        BENCH,
        min_bars=MIN_BARS,
        cost_bps=0.0,
        hysteresis_ranks=3,
        cash_closes=cash,
    )
    arm = bt["hysteresis"]
    assert arm is not None
    assert arm["abs_gated"] is True
    assert arm["held_over"] == 0
    # Every name fails the hurdle, so the arm is entirely in the proxy.
    assert arm["cash_weight_avg"] == 1.0
    expected = [cash[i + 1] / cash[i] - 1.0 for i in range(MIN_BARS, N - 1)]
    assert arm["strategy"] == pytest.approx(expected)
