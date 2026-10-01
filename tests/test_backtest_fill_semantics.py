"""Fill-price honesty: a fill must be at a price the bar actually offered.

Two surfaces share one rule and are pinned together:

* ``scripts/backtest_strategy.py::backtest`` - the replay the advisory backtest
  script runs, and
* ``strategies/backtest_engine.py::MatchingEngine`` - the order state machine.

Three defects are covered. Each made the harness report a fill at a price the
replayed bar never traded at, always in the strategy's favour, so every
downstream metric (Sharpe, deflated Sharpe, PBO, the with/without-cost table)
was computed on a flattered return series:

1. A stop gapped through filled at its TRIGGER. A long's sell-stop fires on
   the gap-down days; booking it at the stop price rather than at the gap
   books price improvement on exactly the worst days.
2. The exit scan read the entry bar's own high/low although the entry was a
   next-bar CLOSE fill, so that bar's already-past range could stop the trade
   out - the same look-ahead the entry path already forbids.
3. A ``STOP_LIMIT`` filled at its limit on a bar where the limit was never
   reachable, i.e. an order that could not have filled was reported filled.
"""

import pytest

from tradingagents.strategies.backtest_engine import (
    Bar,
    MatchingEngine,
    Order,
    OrderSide,
    OrderStatus,
    OrdType,
)

pytestmark = pytest.mark.timeout(180)


def _bars(rows):
    return [Bar(i, o, h, lo, c) for i, (o, h, lo, c) in enumerate(rows)]


def _backtest(bars, **kw):
    from scripts import backtest_strategy as bs

    kw.setdefault("fee_bps", 0.0)
    kw.setdefault("slippage_ticks", 0.0)
    kw.setdefault("qty", 100.0)
    return bs.backtest(bars, **kw)


# ---------------------------------------------------------------------------
# 1. A stop gapped through fills at the gap, never at the trigger
# ---------------------------------------------------------------------------


class TestStopGapFill:
    def test_long_stop_gapped_down_fills_at_the_open(self):
        bars = _bars([
            (100, 101, 99, 100),
            (100, 102, 99.5, 101),   # next-bar-close entry at 101
            (85, 86, 84, 85),        # gaps to 85; 95 never trades
            (85, 88, 84, 86),
        ])
        res = _backtest(bars, entry=101.0, stop=95.0, targets=[120.0], side="long")
        assert res["exit_label"] == "stop"
        assert res["fills"][1]["bar"] == 2
        assert res["fills"][1]["price"] == 85.0
        # -1600 on 100 shares, not the -600 the trigger price would book.
        assert res["net_pnl"] == pytest.approx(-1600.0)

    def test_short_stop_gapped_up_fills_at_the_open(self):
        bars = _bars([
            (100, 101, 99, 100),
            (100, 102, 99.5, 101),
            (115, 116, 114, 115),    # gaps above the 105 stop
            (115, 118, 114, 116),
        ])
        res = _backtest(bars, entry=101.0, stop=105.0, targets=[80.0], side="short")
        assert res["exit_label"] == "stop"
        assert res["fills"][1]["bar"] == 2
        assert res["fills"][1]["price"] == 115.0
        assert res["net_pnl"] == pytest.approx(-1400.0)

    def test_stop_touched_intraday_still_fills_at_the_stop(self):
        """The control: no gap, so the stop price is the real fill."""
        bars = _bars([
            (100, 101, 99, 100),
            (100, 102, 99.5, 101),
            (100, 101, 94, 96),      # opens 100, trades down through 95
            (96, 98, 95, 97),
        ])
        res = _backtest(bars, entry=101.0, stop=95.0, targets=[120.0], side="long")
        assert res["exit_label"] == "stop"
        assert res["fills"][1]["price"] == 95.0


# ---------------------------------------------------------------------------
# 2. The exit scan starts after a next-bar CLOSE fill
# ---------------------------------------------------------------------------


def test_exit_scan_does_not_read_the_entry_bars_past_range():
    bars = _bars([
        (100, 101, 99, 100),
        (100, 102, 90, 101),     # entry at the close 101; low 90 is already past
        (99, 99, 94, 95),        # this is where the stop is really hit
    ])
    res = _backtest(bars, entry=101.0, stop=95.0, targets=[120.0], side="long")
    assert res["fills"][0]["bar"] == 1
    assert res["fills"][1]["bar"] == 2, "stop read the entry bar's past range"
    assert res["exit_label"] == "stop"


# ---------------------------------------------------------------------------
# 3. MatchingEngine: same two rules on the order state machine
# ---------------------------------------------------------------------------


class TestExitTradability:
    """A limit-locked bar cannot execute an exit AT ANY PRICE, so the stop and
    target checks must skip it exactly as the loop's mark-to-market already
    does - otherwise a stop is booked on a bar on which a sell was impossible.
    """

    def test_stop_does_not_execute_on_a_locked_limit_down_bar(self):
        bars = _bars([
            (100, 101, 99, 100),
            (100, 102, 99.5, 101),   # entry @ 101
            (95, 96, 89, 90.0),      # -10.9%: locked, a SELL cannot execute
            (88, 90, 86, 89),        # next tradable bar
        ])
        res = _backtest(bars, entry=101.0, stop=95.0, targets=[120.0],
                        side="long", limit_threshold=0.10)
        assert res["exit_label"] == "stop"
        assert res["fills"][1]["bar"] == 3, "stop executed on a locked bar"
        assert res["fills"][1]["price"] == 88.0

    def test_stop_does_not_execute_on_a_locked_limit_up_bar(self):
        bars = _bars([
            (100, 101, 99, 100),
            (100, 102, 99.5, 101),      # short entry @ 101
            (110, 112, 109, 112.0),     # +10.9%: locked, a BUY cannot execute
            (118, 119, 117, 118),
        ])
        res = _backtest(bars, entry=101.0, stop=110.0, targets=[80.0],
                        side="short", limit_threshold=0.10)
        assert res["exit_label"] == "stop"
        assert res["fills"][1]["bar"] == 3, "stop executed on a locked bar"
        assert res["fills"][1]["price"] == 118.0


class TestExitSlippage:
    """The exit leg pays slippage too. Charging the entry only understates the
    round trip by one leg, and always in the strategy's favour.
    """

    def test_long_exit_leg_pays_slippage(self):
        bars = _bars([
            (100, 101, 99, 100),
            (100, 102, 99.5, 101),   # entry @ 101 -> 101 * 1.01 = 102.01
            (102, 125, 101, 124),    # target 120 touched
        ])
        res = _backtest(bars, entry=101.0, stop=95.0, targets=[120.0],
                        side="long", slippage_ticks=0.01)
        assert res["exit_label"] == "target120.00"
        assert res["fills"][1]["price"] == pytest.approx(118.8)  # 120 * 0.99
        assert res["gross_pnl"] == pytest.approx(1679.0)

    def test_short_exit_leg_pays_slippage(self):
        bars = _bars([
            (100, 101, 99, 100),
            (100, 102, 99.5, 101),   # short entry @ 101 -> 101 * 0.99 = 99.99
            (100, 101, 75, 76),      # target 80 touched
        ])
        res = _backtest(bars, entry=101.0, stop=105.0, targets=[80.0],
                        side="short", slippage_ticks=0.01)
        assert res["exit_label"] == "target80.00"
        assert res["fills"][1]["price"] == pytest.approx(80.8)  # 80 * 1.01
        assert res["gross_pnl"] == pytest.approx(1919.0)


NAN = float("nan")


def _suspended(i):
    return Bar(i, NAN, NAN, NAN, NAN)


class TestSuspendedBarDoesNotLeakNaN:
    """A suspended bar has no price at all. Falling back to one reported NaN as
    the exit price and poisoned net_pnl, the CSV row and both printed stats.
    """

    def test_final_suspended_bar_marks_to_the_last_real_price(self):
        bars = _bars([
            (100, 101, 99, 100),
            (100, 102, 99.5, 101),   # entry @ 101
            (101, 103, 100, 102),
        ]) + [_suspended(3)]
        res = _backtest(bars, entry=101.0, stop=95.0, targets=[150.0], side="long")
        assert res["fills"][1]["bar"] == 2
        assert res["fills"][1]["price"] == 102.0
        assert res["net_pnl"] == pytest.approx(100.0)

    def test_no_tradable_bar_reports_an_unexecuted_plan(self):
        bars = _bars([(100, 101, 99, 100)]) + [_suspended(1)]
        res = _backtest(bars, entry=101.0, stop=95.0, targets=[150.0], side="long")
        assert res["position_filled"]["executed"] is False
        assert res["position_filled"]["qty"] == 0.0
        assert res["entry_price"] == 101.0
        assert res["net_pnl"] == pytest.approx(0.0)


class TestMatchingEngineNonFiniteBar:
    """A bar with no price fills nothing - including MARKET, whose fill price
    is the bar's close with no level to compare against.
    """

    def test_market_order_rides_through_a_suspended_bar(self):
        eng = MatchingEngine()
        eng.submit(Order(0, "X", OrderSide.BUY, OrdType.MARKET, 100))
        res = eng.run([_suspended(0), Bar(1, 100, 101, 99, 100)])
        assert len(res.fills) == 1
        assert res.fills[0].ts_bar_index == 1
        assert res.fills[0].price == 100.0

    def test_no_finite_bar_means_no_fill(self):
        eng = MatchingEngine()
        eng.submit(Order(0, "X", OrderSide.BUY, OrdType.MARKET, 100))
        res = eng.run([_suspended(0), _suspended(1)])
        assert res.fills == []
        assert res.orders[0].status == OrderStatus.ACCEPTED


class TestMatchingEngineStopFill:
    def test_sell_stop_gapped_through_fills_at_the_open(self):
        eng = MatchingEngine()
        eng.submit(Order(0, "X", OrderSide.SELL, OrdType.STOP, 100, trigger=95.0))
        res = eng.run(_bars([(88, 89, 84, 85)]))
        assert len(res.fills) == 1
        assert res.fills[0].price == 88.0

    def test_buy_stop_gapped_through_fills_at_the_open(self):
        eng = MatchingEngine()
        eng.submit(Order(0, "X", OrderSide.BUY, OrdType.STOP, 100, trigger=105.0))
        res = eng.run(_bars([(115, 116, 114, 115)]))
        assert len(res.fills) == 1
        assert res.fills[0].price == 115.0


class TestMatchingEngineStopLimit:
    def test_unreachable_limit_rests_instead_of_filling(self):
        eng = MatchingEngine()
        eng.submit(Order(0, "X", OrderSide.BUY, OrdType.STOP_LIMIT, 100,
                         price=100.0, trigger=105.0))
        res = eng.run(_bars([(100, 110, 106, 108), (95, 99, 94, 96)]))
        assert len(res.fills) == 1, "filled on a bar where 100 never traded"
        assert res.fills[0].ts_bar_index == 1
        assert res.fills[0].price == 100.0

    def test_reachable_limit_fills_on_the_trigger_bar(self):
        eng = MatchingEngine()
        eng.submit(Order(0, "X", OrderSide.BUY, OrdType.STOP_LIMIT, 100,
                         price=104.0, trigger=105.0))
        res = eng.run(_bars([(100, 110, 103, 108)]))
        assert len(res.fills) == 1
        assert res.fills[0].ts_bar_index == 0
        assert res.fills[0].price == 104.0
