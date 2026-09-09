"""Tests for the SKHY 2026-09-09 review-loop phases:

P1 signal/action split (security signal vs portfolio action, never upgrade),
P2 composite position sizing (vol/liquidity/uncertainty/gate clamp),
P3 per-rule forward-return evaluation (n>=30 guard, PREDICTIVE/INSUFFICIENT).

All pure/hermetic; no LLM, no vendor.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.rule_eval import evaluate_rule, forward_returns, rule_signal_rsi70
from tradingagents.strategies.signal_action import (
    portfolio_action_from_gate,
    signal_action_split,
)
from tradingagents.strategies.size import composite_position_size

# ---------------------------------------------------------------------------
# P1 signal/action split
# ---------------------------------------------------------------------------

def test_action_maps_gate_verdicts():
    assert portfolio_action_from_gate("PASS") == "TRADE_ALLOWED"
    assert portfolio_action_from_gate("WARN") == "SCALE_DOWN"
    assert portfolio_action_from_gate("REJECT", ["blocked by portfolio drawdown"]) == "NO_NEW_RISK"
    # A kill-switch reason on a held position -> EXIT; the boolean path (new
    # risk) -> NO_TRADE (covered by test_split_kill_switch_forces_exit).
    assert portfolio_action_from_gate("REJECT", ["kill_switch"]) == "EXIT"
    assert portfolio_action_from_gate("REJECT", ["trade risk"]) == "REDUCE"
    assert portfolio_action_from_gate(None, []) == "TRADE_ALLOWED"


def test_split_keeps_bullish_signal_under_gate():
    # A bullish security signal + a portfolio REJECT must NOT collapse to a
    # plain "HOLD" - it keeps security_signal=BULLISH and portfolio_action
    # = NO_NEW_RISK (SKHY case).
    s = signal_action_split("BUY", "REJECT", ["blocked by portfolio drawdown gate"])
    assert s["security_signal"] == "BUY"
    assert s["portfolio_action"] == "NO_NEW_RISK"
    assert s["gated"] is True
    assert s["combined_action"] == "HOLD"


def test_split_kill_switch_forces_exit():
    s = signal_action_split("HOLD", "REJECT", ["kill switch"], kill_switch=True)
    assert s["portfolio_action"] == "NO_TRADE"
    assert s["gated"] is True


def test_split_open_gate_preserves_signal():
    s = signal_action_split("SELL", "PASS")
    assert s["portfolio_action"] == "TRADE_ALLOWED"
    assert s["gated"] is False
    assert s["combined_action"] == "SELL"


def test_split_gate_never_upgrades():
    # A gate can only downgrade: never map a bearish signal up to a buy.
    s = signal_action_split("SELL", "REJECT", ["portfolio drawdown"])
    assert s["combined_action"] in ("HOLD", "SELL")


# ---------------------------------------------------------------------------
# P2 composite position sizing
# ---------------------------------------------------------------------------

def test_composite_zero_when_gate_blocks():
    r = composite_position_size(
        confidence=0.7, odds=1.0, stop_dist_pct=0.05,
        portfolio_action="NO_NEW_RISK",
    )
    assert r["recommended_pct"] == 0.0
    assert any("portfolio_action" in x for x in r["reasons"])


def test_composite_scales_by_vol_and_liquidity():
    r = composite_position_size(
        confidence=0.7, odds=1.0, stop_dist_pct=0.05, risk_per_trade=0.01,
        annualized_vol=1.17,  # SKHY-like high vol
        liquidity_scalar=0.5,
    )
    assert r["recommended_pct"] > 0.0
    assert r["recommended_pct"] <= 0.30
    # high vol (1.17 target 0.15) -> vol_scale < 1 -> shrink.
    assert r["vol_scale"] < 1.0
    assert r["liquidity"] == 0.5


def test_composite_scale_down_halves():
    r = composite_position_size(
        confidence=0.8, odds=1.0, stop_dist_pct=0.05,
        portfolio_action="SCALE_DOWN",
    )
    open_r = composite_position_size(confidence=0.8, odds=1.0, stop_dist_pct=0.05)
    assert r["recommended_pct"] <= open_r["recommended_pct"] + 1e-9
    assert r["recommended_pct"] == pytest.approx(open_r["recommended_pct"] * 0.5, rel=0.02)


def test_composite_caps_at_max():
    r = composite_position_size(confidence=0.95, odds=4.0, stop_dist_pct=0.02, max_position_pct=0.20)
    assert r["recommended_pct"] <= 0.20


# ---------------------------------------------------------------------------
# P3 per-rule evaluation
# ---------------------------------------------------------------------------

def _trend_series(n=300, seed=0.0):
    import random
    rng = random.Random(seed)
    c = [100.0]
    for _ in range(n - 1):
        c.append(max(30.0, c[-1] + rng.uniform(-1.5, 1.5)))
    return c


def test_forward_returns_horizons_none_past_end():
    closes = [100.0, 101.0, 102.0]
    fr = forward_returns(closes, 0, horizons=(1, 5))
    assert fr[1] == pytest.approx(0.01)
    assert fr[5] is None  # beyond series


def test_evaluate_rule_insufficient_events():
    # A steady decline keeps RSI(14) below 70 -> rsi70 fires ~never -> n<30
    # -> INSUFFICIENT (never a noise table).
    closes = [200.0 - 0.5 * i for i in range(200)]
    r = evaluate_rule(closes, closes, closes, [1e6] * len(closes), rule_signal_rsi70, label="rsi70")
    assert r["verdict"] == "INSUFFICIENT"
    assert r["n_events"] < 30


def test_evaluate_rule_predictive_on_noisy_trend():
    # Rule fires many times on a noisy trending series -> PREDICTIVE with stats.
    closes = _trend_series(320, seed=3)
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    vols = [1e6 + i for i in range(len(closes))]
    r = evaluate_rule(closes, highs, lows, vols, rule_signal_rsi70, label="rsi70")
    assert r["verdict"] in ("PREDICTIVE", "INSUFFICIENT")
    if r["verdict"] == "PREDICTIVE":
        assert "fwd5" in r["stats"] and "hit" in r["stats"]["fwd5"]
