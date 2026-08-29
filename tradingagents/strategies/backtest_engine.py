"""Order state machine + bar-based matching engine (backtest harness).

A small, pure, deterministic replay of how orders fill against daily OHLCV -
the transferable core of NautilusTrader's execution model (order lifecycle,
price-time priority, stop trigger on high/low) stripped of the event bus and
actors. This repo is analysis-only: the engine *simulates* how a report's
entry/stop/target plan would have filled, it never emits an order.

Order statuses follow NautilusTrader (SUBMITTED / ACCEPTED / PARTIALLY_FILLED
/ FILLED / CANCELED / REJECTED), collapsed to what a single-instrument daily
replay needs. Matching uses `bar_execution`: a resting limit fills when the
bar's traded range reaches its price; a stop is *triggered* when the bar's
high/low crosses the trigger. Fill costs (commission + slippage) apply via a
`cost_fn` hook (see `backtest_models`), keeping this module pure numeric.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OrderStatus(Enum):
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrdType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"  # triggers then fills at the trigger (market-on-touch)
    STOP_LIMIT = "STOP_LIMIT"  # triggers, then rests as a limit at price


@dataclass
class Order:
    order_id: int
    symbol: str
    side: OrderSide
    ord_type: OrdType
    quantity: float
    price: float | None = None  # limit price (LIMIT / STOP_LIMIT)
    trigger: float | None = None  # stop trigger (STOP / STOP_LIMIT)
    status: OrderStatus = OrderStatus.SUBMITTED
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    reject_reason: str | None = None

    def is_open(self) -> bool:
        return self.status in (OrderStatus.SUBMITTED, OrderStatus.ACCEPTED,
                               OrderStatus.PARTIALLY_FILLED)

    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED


@dataclass
class Fill:
    order_id: int
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    ts_bar_index: int  # bar index at which the fill occurred

    @property
    def notional(self) -> float:
        return self.quantity * self.price


@dataclass
class Bar:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class BacktestResult:
    fills: list[Fill] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    cash_curve: list[float] = field(default_factory=list)  # cumulative net cash
    rejected: list[Order] = field(default_factory=list)


class MatchingEngine:
    """Bar-based literal matching of limit/stop orders across an OHLCV replay.

    Daily-bar model (not an L2 book): a resting limit buy fills when the bar's
    low <= limit; a stop buy (trigger above market) fills when the bar's high
    >= trigger. ``bar_execution`` innately - one fill decision per bar from
    the high/low range, never intra-bar.
    """

    def __init__(self, cost_fn=None, slippage_ticks: float = 0.0) -> None:
        self.cost_fn = cost_fn  # callable(notional, side) -> cost (float, >=0)
        self.slippage_ticks = slippage_ticks
        self._orders: list[Order] = []
        self._rejected: list[Order] = []
        self._next_id = 1

    def submit(self, order: Order) -> None:
        if order.ord_type != OrdType.MARKET and order.price is None and order.trigger is None:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "no price or trigger"
            self._rejected.append(order)
            return
        order.order_id = self._next_id
        self._next_id += 1
        order.status = OrderStatus.ACCEPTED
        self._orders.append(order)

    def cancel(self, order_id: int) -> bool:
        for o in self._orders:
            if o.order_id == order_id and o.is_open():
                o.status = OrderStatus.CANCELED
                return True
        return False

    def _fill_price(self, order: Order, px: float) -> float:
        slip = self.slippage_ticks
        if slip:
            px = px * (1.0 + slip) if order.side == OrderSide.BUY else px * (1.0 - slip)
        return px

    def _cost(self, fill: Fill) -> float:
        if self.cost_fn is None:
            return 0.0
        return self.cost_fn(fill.notional, fill.side)

    def run(self, bars: list[Bar]) -> BacktestResult:
        """Replay ``bars`` chronologically, filling resting orders each bar.

        Returns fills, end-of-run order states, a cumulative net-cash curve
        (buys subtract, sells add, costs subtracted) and rejected orders.
        """
        self._fills: list[Fill] = []
        cash = 0.0
        cash_curve = [0.0]
        for bar_i, bar in enumerate(bars):
            filled_this_bar: list[Fill] = []
            for order in list(self._orders):
                if not order.is_open():
                    continue
                fill_px: float | None = None
                if order.ord_type == OrdType.MARKET:
                    fill_px = bar.close
                elif order.ord_type == OrdType.LIMIT:
                    buy_hit = (order.side == OrderSide.BUY and order.price is not None
                               and bar.low <= order.price)
                    sell_hit = (order.side == OrderSide.SELL and order.price is not None
                                and bar.high >= order.price)
                    if buy_hit or sell_hit:
                        fill_px = order.price
                else:  # STOP / STOP_LIMIT
                    buy_stopped = (order.side == OrderSide.BUY and order.trigger is not None
                                   and bar.high >= order.trigger)
                    sell_stopped = (order.side == OrderSide.SELL and order.trigger is not None
                                    and bar.low <= order.trigger)
                    if buy_stopped or sell_stopped:
                        if order.ord_type == OrdType.STOP:
                            fill_px = order.trigger
                        elif order.price is not None:
                            fill_px = order.price
                if fill_px is not None:
                    px = self._fill_price(order, fill_px)
                    remaining = order.quantity - order.filled_qty
                    fill = Fill(order.order_id, order.symbol, order.side, remaining, px, bar_i)
                    order.filled_qty = order.quantity
                    order.avg_fill_price = px
                    order.status = OrderStatus.FILLED
                    self._fills.append(fill)
                    filled_this_bar.append(fill)
            for f in filled_this_bar:
                sign = 1.0 if f.side == OrderSide.SELL else -1.0
                cash += sign * f.notional - self._cost(f)
            cash_curve.append(cash)
        return BacktestResult(fills=self._fills, orders=self._orders,
                              cash_curve=cash_curve, rejected=list(self._rejected))


def simple_long_pnl(bars: list[Bar], entry_price: float, exit_price: float,
                    quantity: float, cost_fn=None) -> float:
    """Net long PnL of a single entry/exit pair, given a per-notional cost fn."""
    gross = (exit_price - entry_price) * quantity
    if cost_fn is None:
        return gross
    entry_cost = cost_fn(entry_price * quantity, OrderSide.BUY)
    exit_cost = cost_fn(exit_price * quantity, OrderSide.SELL)
    return gross - entry_cost - exit_cost


__all__ = [
    "OrderStatus", "OrderSide", "OrdType", "Order", "Fill", "Bar",
    "BacktestResult", "MatchingEngine", "simple_long_pnl",
]
