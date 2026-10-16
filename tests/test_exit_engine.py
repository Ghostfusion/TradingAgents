"""The exit engine's contract: point-in-time, fail-closed, evidence-backed.

Every test here is hermetic - synthetic bars, no vendor, no network - because
what is being pinned is arithmetic and ordering, not a live read: the stop in
force on a bar may not use that bar's own high, the trailing stop may never move
down, and an unmeasurable rule may never be reported as "no exit".
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.exit_engine import (
    DEFAULT_MOMENTUM_EXIT_THRESHOLD,
    EXIT_ACTIONS,
    ExitConfig,
    classify_exit,
    compare_exit_variants,
    evaluate_long_exit,
    initial_stop,
    momentum_deterioration,
    sma_break_confirmed,
    stall_exit,
    trailing_stop_level,
)

pytestmark = pytest.mark.timeout(120)


def _bars(closes: list[float], spread: float = 1.0) -> tuple[list[float], list[float]]:
    """Highs/lows around a close series, so the ATR stays the same order as the spread."""
    return [c + spread for c in closes], [c - spread for c in closes]


def _flat(n: int, price: float = 100.0) -> list[float]:
    return [price] * n


def test_the_initial_stop_is_the_entry_minus_the_configured_atr_multiple():
    assert initial_stop(100.0, 2.0, multiple=2.5) == pytest.approx(95.0)
    assert initial_stop(100.0, 2.0, multiple=3.0) == pytest.approx(94.0)
    # An unmeasurable ATR is not a stop at the entry: None, never a fabricated level.
    assert initial_stop(100.0, None) is None
    assert initial_stop(100.0, 0.0) is None
    assert initial_stop(None, 2.0) is None


def test_the_trailing_level_ratchets_and_never_moves_down():
    levels = []
    previous = None
    for highest_high, atr in ((100.0, 2.0), (110.0, 2.0), (105.0, 2.0), (120.0, 5.0), (120.0, 9.0)):
        previous = trailing_stop_level(previous, highest_high, atr, multiple=3.0)
        levels.append(previous)
    assert levels == sorted(levels), "a trailing stop that can fall is not a trailing stop"
    assert levels[0] == pytest.approx(94.0)
    assert levels[-1] == pytest.approx(105.0)
    assert trailing_stop_level(95.0, 100.0, None) is None


def test_the_stop_in_force_ignores_the_bar_it_is_tested_on():
    """The spike bar may only raise the stop for the bar after it (no look-ahead)."""
    closes = _flat(61) + [100.0, 100.0]
    highs = [101.0] * 61 + [200.0, 101.0]
    lows = [99.0] * 61 + [99.0, 99.0]
    result = evaluate_long_exit(
        closes,
        highs=highs,
        lows=lows,
        entry_idx=55,
        config=ExitConfig(enable_trend=False, enable_momentum=False),
    )
    assert result["exit_index"] == 62, "the exit belongs to the bar AFTER the spike"
    assert result["reason"] == "trailing_stop"
    assert result["hwm"] == pytest.approx(200.0)


def test_a_close_evaluated_stop_fills_at_the_next_tradable_price_not_the_stop():
    closes = _flat(56) + [93.0, 92.0]
    highs, lows = _bars(closes)
    result = evaluate_long_exit(
        closes,
        highs=highs,
        lows=lows,
        entry_idx=55,
        config=ExitConfig(enable_trend=False, enable_momentum=False),
    )
    assert result["initial_stop"] == pytest.approx(95.0)
    assert (result["action"], result["reason"]) == ("EXIT", "stop")
    assert result["exit_index"] == 56
    assert result["execution"] == "next close"
    assert result["exit_price"] == pytest.approx(closes[57])
    assert result["exit_price"] != result["initial_stop"]
    assert result["net_return"] < result["gross_return"], "costs are netted out"


def test_the_intraday_convention_tests_the_low_and_a_gap_fills_at_the_open():
    config = ExitConfig(enable_trend=False, enable_momentum=False, stop_evaluation="intraday")

    gapped = _flat(56) + [93.0]
    highs, lows = _bars(gapped)
    opened = list(gapped)
    result = evaluate_long_exit(
        gapped, highs=highs, lows=lows, opens=opened, entry_idx=55, config=config
    )
    assert result["exit_index"] == 56
    assert result["execution"] == "gapped open"
    assert result["exit_price"] == pytest.approx(opened[56])

    # A bar that trades THROUGH the stop without gapping fills at the stop, and the
    # close convention would not have fired at all: the low is what the rule tests.
    through = _flat(56) + [96.0]
    highs2, lows2 = _bars(through)
    result2 = evaluate_long_exit(
        through, highs=highs2, lows=lows2, opens=_flat(57), entry_idx=55, config=config
    )
    assert result2["exit_index"] == 56
    assert result2["execution"] == "stop level"
    assert result2["exit_price"] == pytest.approx(result2["initial_stop"])
    close_convention = evaluate_long_exit(
        through,
        highs=highs2,
        lows=lows2,
        entry_idx=55,
        config=ExitConfig(enable_trend=False, enable_momentum=False),
    )
    assert close_convention["exit_index"] is None


def test_an_unconfirmed_trend_break_is_a_reduce_and_a_confirmed_one_is_an_exit():
    closes = _flat(58) + [98.0, 97.0]
    highs, lows = _bars(closes)
    base = ExitConfig(enable_momentum=False)

    confirmed = evaluate_long_exit(closes, highs=highs, lows=lows, entry_idx=55, config=base)
    assert confirmed["action"] == "EXIT"
    assert confirmed["reason"] == "thesis_break"
    assert confirmed["trend_break"] is True

    unconfirmed = evaluate_long_exit(
        closes,
        highs=highs,
        lows=lows,
        entry_idx=55,
        config=ExitConfig(enable_momentum=False, trend_confirm_bars=3),
    )
    assert unconfirmed["action"] == "REDUCE"
    assert unconfirmed["trend_break"] is False
    assert unconfirmed["reason"] == "deteriorating (unconfirmed)"


def test_the_momentum_rule_needs_both_the_confirmation_count_and_measured_scores():
    below = DEFAULT_MOMENTUM_EXIT_THRESHOLD - 2.0
    assert momentum_deterioration([below, below, below], confirm_bars=3)["deteriorated"] is True
    assert momentum_deterioration([below, below], confirm_bars=3)["deteriorated"] is None
    assert momentum_deterioration([below, None, below], confirm_bars=3)["deteriorated"] is None
    assert (
        momentum_deterioration([DEFAULT_MOMENTUM_EXIT_THRESHOLD + 1.0, below, below],
                              confirm_bars=3)["deteriorated"]
        is False
    )


def test_the_momentum_rule_fires_the_thesis_slot_through_the_engine():
    closes = _flat(60)
    highs, lows = _bars(closes)
    below = DEFAULT_MOMENTUM_EXIT_THRESHOLD - 5.0
    result = evaluate_long_exit(
        closes,
        highs=highs,
        lows=lows,
        entry_idx=55,
        config=ExitConfig(enable_trend=False),
        momentum_scores=[below, below, below],
    )
    assert result["momentum_deteriorating"] is True
    assert result["action"] == "EXIT"
    assert result["reason"] == "thesis_break"
    assert result["conditions"]["thesis_break"] is True


def test_the_stall_rule_ships_off_and_is_inert_until_it_is_armed():
    assert ExitConfig().enable_stall_exit is False
    assert ExitConfig().resolved().enable_stall_exit is False
    assert stall_exit(25, unrealized_return=-0.01, rs_deteriorating=True)["exit"] is True
    assert stall_exit(25, unrealized_return=0.01, rs_deteriorating=True)["exit"] is False
    assert stall_exit(25, unrealized_return=-0.01, rs_deteriorating=None)["exit"] is None
    assert stall_exit(None, unrealized_return=-0.01, rs_deteriorating=True)["exit"] is None

    stalled = _flat(30)
    highs, lows = _bars(stalled)
    armed = evaluate_long_exit(
        stalled,
        highs=highs,
        lows=lows,
        entry_idx=5,
        config=ExitConfig(enable_trend=False, enable_momentum=False, enable_stall_exit=True),
        rs_deteriorating=True,
    )
    assert (armed["action"], armed["reason"]) == ("EXIT", "time_exit")
    assert armed["days_held"] == 20
    unarmed = evaluate_long_exit(
        stalled,
        highs=highs,
        lows=lows,
        entry_idx=5,
        config=ExitConfig(enable_trend=False, enable_momentum=False),
        rs_deteriorating=True,
    )
    assert unarmed["exit_index"] is None


def test_an_unmeasurable_rule_is_named_and_never_read_as_no_exit():
    closes = _flat(60)
    highs, lows = _bars(closes)
    result = evaluate_long_exit(
        closes, highs=highs, lows=lows, entry_idx=55, config=ExitConfig(enable_trend=False)
    )
    assert result["action"] == "HOLD"
    assert "momentum_unmeasured" in result["absent"]
    assert "sessions" in result["absent"]["momentum_unmeasured"]
    assert result["coverage"] >= 1, "the measurable slots were still evaluated"


def test_a_position_whose_protective_stop_cannot_be_measured_is_unavailable():
    closes = _flat(60)
    result = evaluate_long_exit(closes, entry_idx=0)
    assert result["action"] == "UNAVAILABLE"
    assert "protective stop" in result["reason"]
    assert "stop_unmeasured" in result["absent"]

    # With only closes the ATR falls back to the sanctioned proxy, and the basis says
    # so; a perfectly flat series has no volatility to proxy, and gets no ATR at all.
    varying = [100.0 + (i % 5) for i in range(60)]
    proxied = evaluate_long_exit(varying, entry_idx=55)
    assert "proxy" in proxied["basis"]
    assert proxied["action"] in EXIT_ACTIONS
    assert evaluate_long_exit(closes, entry_idx=55)["action"] == "UNAVAILABLE"


def test_a_risk_reject_is_a_risk_exit_and_it_leads_the_ladder():
    closes = _flat(60)
    highs, lows = _bars(closes)
    result = evaluate_long_exit(
        closes, highs=highs, lows=lows, entry_idx=55, risk_gate="REJECT"
    )
    assert (result["action"], result["reason"]) == ("RISK_EXIT", "risk_gate")
    assert result["exit_index"] == 56, "terminal risk leads every other slot"
    benign = evaluate_long_exit(closes, highs=highs, lows=lows, entry_idx=55, risk_gate="PASS")
    assert benign["action"] != "RISK_EXIT"


def test_the_published_actions_cover_every_outcome():
    assert EXIT_ACTIONS == ("HOLD", "REDUCE", "EXIT", "RISK_EXIT", "UNAVAILABLE")
    assert classify_exit("risk_gate", coverage=5) == "RISK_EXIT"
    assert classify_exit("stop", coverage=5) == "EXIT"
    assert classify_exit("trailing_stop", coverage=5) == "EXIT"
    assert classify_exit("time_exit", coverage=5) == "EXIT"
    assert classify_exit(None, coverage=5, deteriorated=True) == "REDUCE"
    assert classify_exit(None, coverage=5) == "HOLD"
    assert classify_exit(None, coverage=0) == "UNAVAILABLE"
    assert classify_exit(None, coverage=5, protective_measured=False) == "UNAVAILABLE"


def test_a_missing_entry_reference_is_unavailable_rather_than_a_silent_recent_entry():
    closes = _flat(60)
    highs, lows = _bars(closes)
    assert evaluate_long_exit(closes, highs=highs, lows=lows)["action"] == "UNAVAILABLE"
    by_date = evaluate_long_exit(
        closes,
        highs=highs,
        lows=lows,
        dates=[f"2026-01-{i + 1:02d}" for i in range(60)],
        entry_date="2026-01-56",
    )
    assert by_date["entry_idx"] == 55


def test_the_confirmed_break_uses_the_sma_the_engine_ledger_already_prints():
    from tradingagents.strategies.technical_factors import sma_legs

    closes = [100.0 + i for i in range(120)]
    ours = sma_break_confirmed(closes, period=50, confirm_bars=2)
    theirs = sma_legs(closes, fast=50, slow=100)
    assert theirs["sma_fast"] is not None
    assert ours["ma"] == pytest.approx(theirs["sma_fast"])
    assert ours["below"] is False, "a rising series is above its own average"
    assert sma_break_confirmed([1.0, 2.0], period=50)["break"] is None


def test_the_trailing_variant_exits_where_the_initial_stop_alone_never_does():
    closes = _flat(55) + [100.0 + 4 * i for i in range(1, 16)]
    closes += [closes[-1] - 6 * i for i in range(1, 9)]
    highs, lows = _bars(closes)
    comparison = compare_exit_variants(closes, highs=highs, lows=lows, entry_idx=50)
    initial = comparison["variants"]["initial_stop_only"]
    trailing = comparison["variants"]["plus_trailing"]
    assert initial["exit_index"] is None, "a 2.5 ATR stop never catches this give-back"
    assert trailing["reason"] == "trailing_stop"
    assert trailing["exit_index"] is not None
    assert trailing["net_return"] < trailing["gross_return"]
    assert trailing["surrendered_pct"] is not None
    assert comparison["order"] == [
        "initial_stop_only",
        "plus_trailing",
        "plus_trend",
        "plus_momentum_and_stall",
    ]


def test_the_stall_variant_is_the_only_one_that_ends_a_stalled_trade():
    closes = _flat(30)
    highs, lows = _bars(closes)
    comparison = compare_exit_variants(
        closes,
        highs=highs,
        lows=lows,
        entry_idx=5,
        momentum_scores=None,
        rs_deteriorating=True,
    )
    without_stall = comparison["variants"]["plus_trend"]
    with_stall = comparison["variants"]["plus_momentum_and_stall"]
    assert without_stall["exit_index"] is None
    assert (with_stall["action"], with_stall["reason"]) == ("EXIT", "time_exit")
    assert with_stall["holding_days"] == 20
    assert with_stall["net_return"] is not None
