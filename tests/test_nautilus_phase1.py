"""Phase-1 tests: backtest engine (order lifecycle + bar matching) + fee models."""

import pytest

from tradingagents.strategies import backtest_models as bm
from tradingagents.strategies.backtest_engine import (
    Bar,
    MatchingEngine,
    Order,
    OrderSide,
    OrderStatus,
    OrdType,
)

pytestmark = pytest.mark.timeout(180)


def _bars():
    return [
        Bar(1, 100, 102, 98, 101),
        Bar(2, 101, 103, 99, 102),
        Bar(3, 102, 99, 97, 98),
        Bar(4, 98, 100, 97, 99),
    ]


# ---------------------------------------------------------------------------
# Order state machine
# ---------------------------------------------------------------------------


def test_order_lifecycle():
    o = Order(0, "X", OrderSide.BUY, OrdType.LIMIT, 10, price=99.0)
    assert o.status == OrderStatus.SUBMITTED
    assert o.is_open()
    o.status = OrderStatus.ACCEPTED
    assert o.is_open()
    o.status = OrderStatus.FILLED
    assert not o.is_open()
    assert o.is_filled()
    o.status = OrderStatus.CANCELED
    assert not o.is_open()
    assert not o.is_filled()


def test_submit_rejects_no_price_or_trigger():
    eng = MatchingEngine()
    bad = Order(0, "X", OrderSide.BUY, OrdType.LIMIT, 10)
    eng.submit(bad)
    assert bad.status == OrderStatus.REJECTED
    assert bad.reject_reason is not None
    r = eng.run(_bars())
    assert len(r.rejected) == 1


def test_cancel_open_order():
    eng = MatchingEngine()
    o = Order(0, "X", OrderSide.BUY, OrdType.LIMIT, 10, price=50.0)
    eng.submit(o)
    assert eng.cancel(o.order_id) is True
    assert o.status == OrderStatus.CANCELED
    assert eng.cancel(o.order_id) is False


# ---------------------------------------------------------------------------
# Bar matching
# ---------------------------------------------------------------------------


def test_limit_buy_fills_when_low_reaches_price():
    eng = MatchingEngine()
    eng.submit(Order(0, "X", OrderSide.BUY, OrdType.LIMIT, 10, price=99.0))
    r = eng.run(_bars())
    # Fills on bar 2 (low 99).
    assert len(r.fills) == 1
    assert r.fills[0].side == OrderSide.BUY
    assert r.fills[0].price == 99.0
    assert r.fills[0].quantity == 10


def test_stop_buy_triggers_on_high_cross():
    # Trigger at 103 -> fills on bar 2 (high 103) at the trigger.
    eng = MatchingEngine()
    eng.submit(Order(0, "X", OrderSide.BUY, OrdType.STOP, 10, trigger=103.0))
    r = eng.run(_bars())
    assert len(r.fills) == 1
    assert r.fills[0].price == 103.0


def test_market_order_fills_first_bar():
    eng = MatchingEngine()
    eng.submit(Order(0, "X", OrderSide.BUY, OrdType.MARKET, 10))
    r = eng.run(_bars())
    assert len(r.fills) == 1
    assert r.fills[0].ts_bar_index == 0


def test_unfilled_limit_rests_to_end():
    eng = MatchingEngine()
    eng.submit(Order(0, "X", OrderSide.BUY, OrdType.LIMIT, 10, price=50.0))
    r = eng.run(_bars())
    assert r.fills == []
    assert r.orders[0].status == OrderStatus.ACCEPTED  # still resting


# ---------------------------------------------------------------------------
# Cash curve + costs
# ---------------------------------------------------------------------------


def test_cash_curve_buy_sell_net():
    eng = MatchingEngine()
    # Buy fills on bar 0 (market @ close 101); the sell is a limit at 102 that
    # fills on bar 1 (high 103 >= 102) - so gross = 102*10 - 101*10.
    eng.submit(Order(0, "X", OrderSide.BUY, OrdType.MARKET, 10))
    eng.submit(Order(0, "X", OrderSide.SELL, OrdType.LIMIT, 10, price=102.0))
    r = eng.run(_bars())
    assert r.cash_curve[-1] == pytest.approx(102 * 10 - 101 * 10)


def test_costs_subtracted_from_cash():
    fee = lambda notional, side: notional * 5 / 10000  # noqa: E731
    eng = MatchingEngine(cost_fn=fee)
    eng.submit(Order(0, "X", OrderSide.BUY, OrdType.MARKET, 10))
    eng.submit(Order(0, "X", OrderSide.SELL, OrdType.LIMIT, 10, price=102.0))
    r = eng.run(_bars())
    gross = 102 * 10 - 101 * 10
    costs = 101 * 10 * 5 / 10000 + 102 * 10 * 5 / 10000
    assert r.cash_curve[-1] == pytest.approx(gross - costs)


def test_slippage_adverse_tick():
    eng = MatchingEngine(slippage_ticks=0.01)
    eng.submit(Order(0, "X", OrderSide.BUY, OrdType.MARKET, 10))
    r = eng.run(_bars())
    # Buy slips up 1% -> fill above the close used.
    assert r.fills[0].price > 101.0


def test_simple_long_pnl_net_of_cost():
    from tradingagents.strategies.backtest_engine import simple_long_pnl

    cost = lambda notional, side: notional * 5 / 10000  # noqa: E731
    pnl = simple_long_pnl(_bars(), 100.0, 110.0, 10, cost_fn=cost)
    gross = (110 - 100) * 10
    costs = 100 * 10 * 5 / 10000 + 110 * 10 * 5 / 10000
    assert pnl == pytest.approx(gross - costs)


# ---------------------------------------------------------------------------
# backtest_models
# ---------------------------------------------------------------------------


def test_fixed_fee():
    assert bm.fixed_fee(1000.0, 5) == pytest.approx(0.5)  # 5 bps
    assert bm.fixed_fee(1000.0, 0) == 0.0
    assert bm.fixed_fee(None, 5) == 0.0


def test_maker_taker_fee():
    assert bm.maker_taker_fee(1000.0, maker_bps=1, taker_bps=5, liquidity="maker") == pytest.approx(0.1)
    assert bm.maker_taker_fee(1000.0, maker_bps=1, taker_bps=5, liquidity="taker") == pytest.approx(0.5)


def test_slip_price():
    assert bm.slip_price(100.0, 0.01, "none") == 100.0
    assert bm.slip_price(100.0, 0.01, "fixed") == pytest.approx(100.01)
    assert bm.slip_price(100.0, 0.01, "probabilistic") == pytest.approx(100.01)  # deterministic
    assert bm.slip_price(100.0, 0.0, "fixed") == 100.0


def test_make_cost_fn():
    fn = bm.make_cost_fn(fee_bps=5)
    assert fn(1000.0, OrderSide.BUY) == pytest.approx(0.5)


def test_limit_fill_probability_bounds():
    assert bm.limit_fill_probability(0.0, base=0.5) == pytest.approx(0.5)
    assert bm.limit_fill_probability(1.0) == pytest.approx(0.0)
    assert 0 <= bm.limit_fill_probability(2.0) <= 1.0
