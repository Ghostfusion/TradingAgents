"""Execution multiplier (two-tier soft/hard risk) tests - halve-not-block."""

from __future__ import annotations

import pytest

from tradingagents.strategies.contract import build_position_contract
from tradingagents.strategies.risk_multiplier import RiskMultiplier, combine

pytestmark = pytest.mark.timeout(120)


def _closes():
    return [100.0 + 0.1 * i for i in range(60)]


# --- combine ---


def test_softs_multiply():
    r = combine(RiskMultiplier(soft={"regime": 0.5, "knife": 0.5}))
    assert r["factor"] == 0.25
    assert r["blocked"] is False
    assert r["soft_reasons"] == ["regime", "knife"]  # catalog order
    assert r["hard_reasons"] == []


def test_softs_include_vol_cap():
    r = combine(RiskMultiplier(soft={"vol_cap": 0.5, "regime": 1.0}))
    assert r["factor"] == 0.5
    # 1.0 softs are skipped from reasons (only <1.0 reported)
    assert r["soft_reasons"] == ["vol_cap"]


def test_hard_blocks_regardless_of_softs():
    r = combine(RiskMultiplier(soft={"regime": 0.25, "knife": 0.25}, hard=("halt",)))
    assert r["factor"] == 0.0
    assert r["blocked"] is True
    assert r["hard_reasons"] == ["halt"]


def test_hard_known_names():
    for name in (
        "halt", "insufficient_liquidity", "max_portfolio_risk",
        "data_quality_failure", "broker_safety",
    ):
        r = combine(RiskMultiplier(hard=(name,)))
        assert r["blocked"] is True and r["hard_reasons"] == [name]


def test_unknown_hard_fails_safe():
    # an unknown hard flag must BLOCK (never silently pass)
    r = combine(RiskMultiplier(hard=("wat",)))
    assert r["blocked"] is True
    assert "wat" in r["hard_reasons"]


def test_none_multiplier_is_neutral():
    r = combine(None)
    assert r["factor"] == 1.0 and r["blocked"] is False


def test_soft_values_clamped():
    # values below 0 clamp to 0 (a negative soft is a full stop, not a boost)
    r = combine(RiskMultiplier(soft={"knife": -1.0, "regime": 2.0}))
    assert r["factor"] == 0.0


# --- contract integration ---


def test_contract_scales_by_execution_multiplier():
    c1 = build_position_contract(cfg={}, closes=_closes(), calibrated_p=0.65)
    c2 = build_position_contract(cfg={}, closes=_closes(), calibrated_p=0.65, knife_factor=0.5)
    assert c1.size_pct > 0
    # size is rounded to 4dp; allow the rounding tolerance
    assert abs(c2.size_pct - round(c1.size_pct * 0.5, 4)) < 1e-9
    assert any("exec_mult" in r for r in c2.reason_parts)


def test_contract_hard_guard_blocks_to_zero():
    c = build_position_contract(
        cfg={}, closes=_closes(), calibrated_p=0.65,
        hard_guards=("halt",),
    )
    assert c.size_pct == 0.0
    assert any("HARD BLOCK" in r for r in c.reason_parts)


def test_contract_empty_hard_guards_neutral():
    c = build_position_contract(cfg={}, closes=_closes(), calibrated_p=0.65, hard_guards=())
    assert c.size_pct > 0
    assert not any("HARD BLOCK" in r for r in c.reason_parts)
