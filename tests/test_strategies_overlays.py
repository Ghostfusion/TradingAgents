"""Overlay wiring unit tests (offline, deterministic)."""

import pytest

from tradingagents.strategies.overlays import (
    build_strategy_overlays, apply_overlay_to_state, record_reflection_outcome,
)


def _closes(n=260, base=100.0, step=0.25):
    return [base + step * i for i in range(n)]


def test_overlay_disabled_returns_none():
    assert build_strategy_overlays({"enable_strategy_overlays": False}, _closes()) is None


def test_overlay_too_few_prices_none():
    assert build_strategy_overlays({"enable_strategy_overlays": True}, [1.0, 2.0]) is None


def test_overlay_builds_context():
    ov = build_strategy_overlays({"enable_strategy_overlays": True, "target_vol": 0.15},
                                 _closes())
    assert ov is not None
    assert ov["regime"] in ("bull", "bear", "neutral", "high_vol")
    assert 0.0 < ov["position_scale"] <= 1.5
    assert "regime=" in ov["context"]


def test_apply_overlay_preserves_state():
    state = {"final_trade_decision": "hold"}
    out = apply_overlay_to_state(state, {"regime": "bear", "position_scale": 0.5})
    assert out["strategy_overlays"]["regime"] == "bear"
    assert state.get("strategy_overlays") is None  # original untouched


def test_apply_overlay_none_noop():
    out = apply_overlay_to_state({"a": 1}, None)
    assert "strategy_overlays" not in out


def test_record_reflection_guarded(tmp_path):
    cfg_off = {"enable_reflection": False}
    record_reflection_outcome(cfg_off, str(tmp_path / "l.jsonl"), "market", "AAPL",
                              "2026-01-02", 0.02)
    assert not (tmp_path / "l.jsonl").exists()


def test_record_reflection_writes(tmp_path):
    cfg = {"enable_reflection": True}
    path = str(tmp_path / "ledger.jsonl")
    record_reflection_outcome(cfg, path, "market", "AAPL", "2026-01-02", 0.02)
    record_reflection_outcome(cfg, path, "market", "MSFT", "2026-01-03", -0.01)
    from tradingagents.strategies.reflection import ReflectionLedger
    store = ReflectionLedger(path=path)
    assert store.total("market") == 2
