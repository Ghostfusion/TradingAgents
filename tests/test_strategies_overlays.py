"""Overlay wiring unit tests (offline, deterministic)."""

import numpy as np
import pytest

from tradingagents.strategies.overlays import (
    apply_overlay_to_state,
    build_strategy_overlays,
    fold_flow_into_overlay,
    record_reflection_outcome,
)

pytestmark = pytest.mark.timeout(60)


def _closes(n=260, base=100.0, step=0.25):
    return [base + step * i for i in range(n)]


def test_overlay_disabled_returns_none():
    assert build_strategy_overlays({"enable_strategy_overlays": False}, _closes()) is None


def test_overlay_too_few_prices_none():
    assert build_strategy_overlays({"enable_strategy_overlays": True}, [1.0, 2.0]) is None


def test_overlay_builds_context():
    ov = build_strategy_overlays({"enable_strategy_overlays": True, "target_vol": 0.15}, _closes())
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
    record_reflection_outcome(
        cfg_off, str(tmp_path / "l.jsonl"), "market", "AAPL", "2026-01-02", 0.02
    )
    assert not (tmp_path / "l.jsonl").exists()


def test_fold_flow_scales_position_and_warns():
    flow = {
        "distribution_score": 0.79,
        "flag": "distribution",
        "divergence": "distribution_into_strength",
        "text": "order flow: inst_net=-2e7 FLOW_WARNING",
    }
    overlay = {"regime": "bear", "position_scale": 1.0, "context": "regime=bear"}
    out = fold_flow_into_overlay(overlay, flow, threshold=0.7)
    assert out["position_scale"] == round(1.0 * (1.0 - 0.79), 3)
    assert out["flow"]["warning"] is True
    assert "FLOW_WARNING" in out["context"]


def test_fold_flow_none_is_noop():
    overlay = {"position_scale": 1.0, "context": "x"}
    assert fold_flow_into_overlay(overlay, None) is overlay


def test_record_reflection_writes(tmp_path):
    cfg = {"enable_reflection": True}
    path = str(tmp_path / "ledger.jsonl")
    record_reflection_outcome(cfg, path, "market", "AAPL", "2026-01-02", 0.02)
    record_reflection_outcome(cfg, path, "market", "MSFT", "2026-01-03", -0.01)
    from tradingagents.strategies.reflection import ReflectionLedger

    store = ReflectionLedger(path=path)
    assert store.total("market") == 2

def test_fold_sentiment_neutral_when_no_measurement():
    from tradingagents.strategies.overlays import fold_sentiment_into_overlay

    overlay = {"position_scale": 1.0, "context": "regime=bull"}
    out = fold_sentiment_into_overlay(overlay, None)
    assert out["position_scale"] == 1.0
    assert "news_sentiment" not in out


def test_fold_sentiment_scales_when_ic_clears_floor():
    from tradingagents.strategies.overlays import fold_sentiment_into_overlay

    overlay = {"position_scale": 1.0, "context": ""}
    out = fold_sentiment_into_overlay(
        overlay,
        {"rank_ic": 0.05, "innovation": 0.3, "sma_7d": 0.4, "source": "eodhd"},
        min_ic=0.02,
    )
    assert out["position_scale"] == pytest.approx(1.2, abs=1e-3)
    assert out["news_sentiment"]["source"] == "eodhd"
    assert "news-sentiment scale" in out["context"]


def test_fold_sentiment_neutral_below_ic_floor():
    from tradingagents.strategies.overlays import fold_sentiment_into_overlay

    overlay = {"position_scale": 1.0, "context": ""}
    out = fold_sentiment_into_overlay(
        overlay, {"rank_ic": 0.01, "innovation": 0.3, "source": "eodhd"}
    )
    assert out["position_scale"] == 1.0
    assert out["news_sentiment"]["scale"] == 1.0


def test_graph_sentiment_read_returns_context(monkeypatch):
    """_sentiment_factor_read returns a measured read with the EODHD points
    fed + strong closes; the fold then scales."""
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    cfg = DEFAULT_CONFIG.copy()
    cfg["enable_sentiment_factor"] = True
    ta = TradingAgentsGraph(debug=False, config=cfg)
    rng = np.random.default_rng(5)
    closes = list(100.0 * np.cumprod(1 + rng.normal(0.001, 0.02, 120)))
    # 90 sentiment days with a planted 3-day predictive tilt.
    fwd = [closes[i + 3] / closes[i] - 1.0 for i in range(90)]
    points = [
        {"date": f"2026-05-{1 + i // 30:02d}", "score": float(5 * fwd[i] + rng.standard_normal()), "n": 2}
        for i in range(90)
    ]
    monkeypatch.setattr(
        "tradingagents.dataflows.eodhd._sentiment_points_eodhd", lambda *a, **k: points
    )
    read = ta._sentiment_factor_read("AAPL", closes)
    assert read is not None
    assert read["source"] == "eodhd"
    assert abs(read["rank_ic"]) >= 0.02
    assert read["innovation"] is not None


def test_graph_sentiment_read_off_returns_none():
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    cfg = DEFAULT_CONFIG.copy()
    cfg["enable_sentiment_factor"] = False
    ta = TradingAgentsGraph(debug=False, config=cfg)
    assert ta._sentiment_factor_read("AAPL", [100.0] * 120) is None


