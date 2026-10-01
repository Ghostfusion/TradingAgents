"""§103's price families: the §8-§42 constructions and the complete member set.

The member lists are asserted verbatim against the spec: the whole point of the
object is that a reader can check §103's recommendation off the report line by
line, so an accidental rename has to fail a test rather than quietly drop a row.

Hermetic: pure functions, deterministic series, no clock, no network.
"""

from __future__ import annotations

import math

import pytest

from tradingagents.strategies import entry_exit_families as fam

pytestmark = pytest.mark.timeout(60)

#: `Strategies/entry_exit.md` §103 "Recommended complete Entry/Exit object",
#: copied verbatim - the golden list the implementation must keep matching.
_ENTRY_SPEC = (
    "signal_price",
    "fair_value_price",
    "valuation_entry_price",
    "technical_entry_price",
    "momentum_entry_price",
    "volatility_entry_price",
    "support_entry_price",
    "expected_return_entry_price",
    "risk_adjusted_entry_price",
    "liquidity_adjusted_entry_price",
    "execution_price",
    "max_entry_price",
    "final_entry_price",
)
_EXIT_SPEC = (
    "stop_loss_price",
    "volatility_stop",
    "ATR_stop",
    "support_stop",
    "trailing_stop",
    "break_even_stop",
    "fair_value_target",
    "technical_target",
    "momentum_target",
    "volatility_target",
    "risk_reward_target",
    "time_exit",
    "event_exit",
    "thesis_break_exit",
    "expected_value_exit",
    "final_exit_price",
)


def _closes(n: int = 60) -> list[float]:
    """Deterministic series with a real sigma and a real ATR (no RNG, no clock)."""
    return [100.0 + 0.05 * i + 2.0 * math.sin(i / 3.0) for i in range(n)]


def test_the_member_lists_are_103_verbatim():
    assert fam.ENTRY_MEMBERS == _ENTRY_SPEC
    assert fam.EXIT_MEMBERS == _EXIT_SPEC


def test_sigma_is_none_rather_than_zero_when_unmeasurable():
    """Two closes cannot make a volatility, and 0.0 would read as "no
    volatility" - the NA-as-zero class the no-fabrication contract forbids."""
    assert fam.daily_sigma([100.0, 101.0]) is None
    assert fam.daily_sigma([]) is None
    measured = fam.daily_sigma(_closes())
    assert measured is not None and measured > 0.0


def test_section_9_and_10_entries_follow_their_formulas():
    closes = _closes()
    ref = closes[-1]
    sigma = fam.daily_sigma(closes)
    assert sigma is not None
    out = fam.section_103_members(closes=closes, price=ref)["entry"]

    expected_vol_entry = ref - ref * sigma * math.sqrt(fam.VOL_ENTRY_HORIZON_DAYS)
    assert out["volatility_entry_price"]["value"] == pytest.approx(expected_vol_entry)
    assert out["volatility_entry_price"]["value"] < ref

    support, basis = fam.support_level(closes, None)
    assert basis == "close-proxy"  # no lows were supplied
    assert support is not None
    assert out["support_entry_price"]["value"] == pytest.approx(
        support * (1.0 + fam.SUPPORT_BUFFER_PCT)
    )
    assert out["support_entry_price"]["value"] > support


def test_the_stops_sit_below_the_entry_and_the_targets_above_it():
    closes = _closes()
    entry = closes[-1]
    stop = entry * 0.95
    members = fam.section_103_members(
        closes=closes,
        price=entry,
        entry=entry,
        stop=stop,
        technical_target=entry * 1.08,
        config={"atr_mult": 2.0, "min_rr": 2.0},
    )["exit"]

    for name in ("volatility_stop", "ATR_stop", "support_stop"):
        assert members[name]["value"] < entry, name
    for name in ("volatility_target", "risk_reward_target", "technical_target"):
        assert members[name]["value"] > entry, name

    # §37: entry + r_m * (entry - stop).
    assert members["risk_reward_target"]["value"] == pytest.approx(
        entry + 2.0 * (entry - stop)
    )
    # §56: the break-even stop is ABOVE the entry (cushion * ATR of profit).
    assert members["break_even_stop"]["value"] > entry


def test_the_unproducible_members_are_absent_with_a_reason():
    """Momentum has no score -> price map and a fair value needs statements:
    both are named absent, never filled with a plausible-looking number."""
    closes = _closes()
    out = fam.section_103_members(closes=closes, price=closes[-1], entry=closes[-1])

    entry_momentum = out["entry"]["momentum_entry_price"]
    assert entry_momentum["value"] is None and entry_momentum["reason"]
    exit_momentum = out["exit"]["momentum_target"]
    assert exit_momentum["value"] is None and exit_momentum["reason"]
    assert out["entry"]["fair_value_price"]["value"] is None
    assert out["exit"]["fair_value_target"]["value"] is None
    assert out["exit"]["event_exit"]["value"] is None


def test_a_supplied_fair_value_fills_both_fair_value_members():
    closes = _closes()
    entry = closes[-1]
    out = fam.section_103_members(
        closes=closes, price=entry, entry=entry, fair_value=entry * 1.2
    )

    assert out["entry"]["fair_value_price"]["value"] == pytest.approx(entry * 1.2)
    assert out["exit"]["fair_value_target"]["value"] == pytest.approx(
        entry * 1.2 * (1.0 - fam.FAIR_VALUE_HAIRCUT)
    )


def test_atr_off_closes_is_labelled_a_proxy():
    """The basis travels with the number, so a stop priced off a close-to-close
    proxy cannot be mistaken for one priced off the run's real highs/lows."""
    closes = _closes()
    proxy, proxy_source = fam.atr_read(closes, None, None)
    assert proxy_source == "proxy" and proxy is not None and proxy > 0.0

    highs = [c + 2.0 for c in closes]
    lows = [c - 2.0 for c in closes]
    true_range, tr_source = fam.atr_read(closes, highs, lows)
    assert tr_source == "h/l"
    assert true_range is not None and proxy is not None and true_range > proxy


def test_every_member_is_a_value_or_a_named_absence():
    """The one shape the whole object keeps: ``{value, status, reason}``, and
    ``status`` is NO_SOURCE exactly when there is no value."""
    closes = _closes()
    out = fam.section_103_members(
        closes=closes, price=closes[-1], entry=closes[-1], stop=closes[-1] * 0.95
    )

    for group in ("entry", "exit"):
        for name, record in out[group].items():
            assert set(record) == {"value", "status", "reason"}, name
            if record["value"] is None:
                assert record["status"] == "NO_SOURCE", name
                assert record["reason"], name
            else:
                assert record["status"] == "OK", name
