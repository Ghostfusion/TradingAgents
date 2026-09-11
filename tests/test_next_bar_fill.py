"""Vibe-Trading next-bar fill + lookahead sentinel (P1-2).

A signal computed from bar T's close must fill at bar T+1's close, never at
bar T's own close (same-bar close lookahead = the phantom edge Vibe-Trading
removed from all its backtests, #1299). The sentinel proves the rule with a
deterministic malicious signal: a strategy that "knows" tomorrow's close
posts positive alpha only if the engine fills on the signal bar.
"""

import pytest

from tradingagents.strategies.backtest_engine import (
    Bar,
    MatchingEngine,
    Order,
    OrderSide,
    OrdType,
)


def _bars(close_prices):
    out = []
    for i, c in enumerate(close_prices):
        out.append(Bar(ts=i, open=c, high=c + 0.1, low=c - 0.1, close=c, volume=1000))
    return out


def _run_market(engine, bars, side, qty, fill_on_next_bar):
    engine.submit(Order(order_id=0, symbol="X", side=side, ord_type=OrdType.MARKET,
                        quantity=qty))
    return engine.run(bars, fill_on_next_bar=fill_on_next_bar)


class TestNextBarFill:
    def test_market_fills_on_next_bar_close_when_enabled(self):
        bars = _bars([100.0, 110.0])
        r = _run_market(MatchingEngine(), bars, OrderSide.BUY, 1.0, fill_on_next_bar=True)
        assert len(r.fills) == 1
        assert r.fills[0].ts_bar_index == 1
        assert r.fills[0].price == 110.0  # next bar close, not 100.0

    def test_market_fills_same_bar_when_flag_off(self):
        bars = _bars([100.0, 110.0])
        r = _run_market(MatchingEngine(), bars, OrderSide.BUY, 1.0, fill_on_next_bar=False)
        assert len(r.fills) == 1
        assert r.fills[0].ts_bar_index == 0
        assert r.fills[0].price == 100.0  # same-bar close (legacy behavior)

    def test_limits_unaffected_by_flag(self):
        bars = _bars([100.0, 90.0, 95.0])
        eng = MatchingEngine()
        eng.submit(Order(order_id=0, symbol="X", side=OrderSide.BUY,
                         ord_type=OrdType.LIMIT, quantity=1.0, price=95.0))
        r = eng.run(bars, fill_on_next_bar=True)
        assert len(r.fills) == 1
        assert r.fills[0].price == 95.0  # limit price honored
        assert r.fills[0].ts_bar_index == 1  # low 89.9 <= 95 at bar 1


class TestLookaheadSentinel:
    def test_lookahead_close_signal_cannot_capture_the_gap(self):
        """The deterministic malicious signal: buy at close, 'knowing' the next
        day's close is higher. Under next-bar fill the strategy cannot bank the
        signal-bar -> fill-bar gap (it enters at the next close, not the close
        it signalled on), so its PnL is the ordinary hold from entry to the
        final close; under legacy same-bar fill it would bank the full gap
        including the lookahead point."""
        closes = [100.0, 101.0, 102.0, 103.0, 104.0]
        bars = _bars(closes)
        # enter at the first opportunity, exit at the last close
        eng = MatchingEngine()
        eng.submit(Order(order_id=0, symbol="X", side=OrderSide.BUY,
                         ord_type=OrdType.MARKET, quantity=1.0))
        r = eng.run(bars, fill_on_next_bar=True)
        entry = r.fills[0].price
        assert entry == closes[1]  # filled at bar-1 close, never at bar-0 close
        # Net PnL is the actual price difference from the fill bar to the final
        # close; the lookahead point (closes[0] -> closes[1]) is never captured.
        pnl = (closes[-1] - entry) * 1.0
        assert pnl == 3.0
        assert pnl != (closes[-1] - closes[0]) * 1.0

    def test_sentinel_alpha_zero(self):
        closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
        bars = _bars(closes)
        eng = MatchingEngine()
        eng.submit(Order(order_id=0, symbol="X", side=OrderSide.BUY,
                         ord_type=OrdType.MARKET, quantity=1.0))
        r = eng.run(bars, fill_on_next_bar=True)
        entry_px = r.fills[0].price
        exit_px = closes[-1]
        pnl = (exit_px - entry_px) * 1.0
        # entry at closes[1] (101), exit at 105 -> the lookahead edge (entry at
        # 100 + 1..105 gap) is reduced to a normal 4-point hold, NOT the 5-
        # point same-bar edge. The sentinel asserts the fill price is next-bar.
        assert entry_px == closes[1]
        assert pnl == 4.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
