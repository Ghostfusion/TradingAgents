"""W4 — pre-graph risk context: one producer, consumed by the gate.

Covers ``tradingagents/graph/trading_graph.py``:

* ``_precompute_risk_context`` is the SINGLE producer of the Portfolio
  Manager's pre-decision risk numbers (CVaR / liquidity / book drawdown /
  limits) and the post-graph risk governor CONSUMES them from
  ``risk_context`` instead of recomputing (a second computation of the same
  number is exactly the defect this guards).
* the ``insufficient_liquidity`` hard guard reads the liquidity verdict from
  the risk context. The old read was a dict-key read on ``risk_snapshot``,
  which ``build_risk_snapshot`` returns as a ``str`` - so the guard could
  never fire, and would now raise on that read.

Hermetic: the vendor close seam and the two share-count seams are stubbed;
no network, no LLM, no wall clock.
"""

from __future__ import annotations

import math

import pytest

import tradingagents.graph.trading_graph as tg


def _closes(n: int = 200) -> list[float]:
    """Deterministic positive series with 1-3% swings (no RNG, no clock)."""
    return [100.0 + 0.02 * i + 3.0 * math.sin(i / 5.0) for i in range(n)]


def _config(**over) -> dict:
    cfg = {
        "enable_strategy_overlays": True,
        "enable_events": False,
        "enable_orderflow": False,
        "enable_position_contract": False,
        "enable_hard_guards": True,
        "enable_risk_governor": True,
        "enable_liquidity_gate": True,
        "enable_agreement": False,
        "enable_calibration": False,
        "enable_exits": False,
        "enable_tranche_risk": False,
        "risk_basket_tickers": ["SPY", "QQQ"],
        "risk_basket_weights": {},
        "risk_audit_enabled": False,
        "risk_max_drawdown_pct": 0.10,
        "max_position_pct": 0.30,
        "risk_daily_cvar_budget_pct": 0.03,
        "target_vol": 0.15,
        "position_odds": 1.0,
        "kelly_fraction": 0.25,
        "risk_per_trade": 0.01,
        "atr_mult": 2.0,
    }
    cfg.update(over)
    return cfg


def _graph(monkeypatch, closes, **cfg_over):
    graph = object.__new__(tg.TradingAgentsGraph)
    graph.config = _config(**cfg_over)
    monkeypatch.setattr(graph, "_try_fetch_closes", lambda *a, **k: closes)
    return graph


def test_pre_graph_context_is_the_only_producer(monkeypatch):
    """The gate consumes the hoisted numbers: one drawdown computation total."""
    graph = _graph(monkeypatch, _closes())

    calls = {"drawdown": 0}

    def _drawdown(_ticker):
        calls["drawdown"] += 1
        return 0.042

    monkeypatch.setattr(graph, "_basket_drawdown", _drawdown)
    import tradingagents.dataflows.float_shares as float_shares
    import tradingagents.dataflows.statement_parsing as statement_parsing

    monkeypatch.setattr(float_shares, "fetch_float_shares", lambda _t: 4_000_000.0)
    monkeypatch.setattr(
        statement_parsing, "fetch_ticker", lambda _t, _d: {"shares": {"current": 20_000_000.0}}
    )

    ctx = graph._precompute_risk_context("NVDA")
    assert ctx["book_drawdown"] == pytest.approx(0.042)
    assert ctx["drawdown_limit"] == pytest.approx(0.10)
    assert ctx["max_position_pct"] == pytest.approx(0.30)
    assert ctx["cvar_budget_pct"] == pytest.approx(0.03)
    # IWF = float / total = 0.20 < 0.50 -> the composite verdict is ILLIQUID.
    assert ctx["liquidity"]["verdict"] == "illiquid"
    assert ctx["liquidity"]["iwf"] == pytest.approx(0.20)
    assert ctx["liquidity"]["dangers"]
    assert calls["drawdown"] == 1

    import tradingagents.strategies.risk_governor as rg

    seen: dict = {}

    def _govern(size, cfg, **kw):
        seen.update(kw)
        return {"verdict": "PASS", "reasons": [], "numbers": "size unknown"}

    monkeypatch.setattr(rg, "govern", _govern)

    state = {
        "trade_date": "2026-08-19",
        "final_trade_decision": "Hold",
        "risk_context": dict(ctx),
    }
    out = graph._apply_strategy_overlays(state, "NVDA")

    # Consumed, not recomputed: the pre-graph read is the only drawdown call.
    assert calls["drawdown"] == 1
    assert seen["drawdown_pct"] == pytest.approx(0.042)
    assert seen["liquidity_verdict"] == "illiquid"
    assert seen["liquidity_dangers"] == ctx["liquidity"]["dangers"]
    assert out["risk_context"]["book_drawdown"] == pytest.approx(0.042)
    assert out["risk_context"]["liquidity"]["verdict"] == "illiquid"


def test_insufficient_liquidity_guard_reads_risk_context(monkeypatch):
    """ILLIQUID read -> hard guard; anything else (liquid / unknown) stays silent.

    The pre-fix read was ``(risk_snapshot or {}).get("liquidity_verdict")`` on a
    ``str`` snapshot, so the guard could never appear - and the fixture below
    carries a real ``risk_snapshot`` string to prove the new read is
    independent of it.
    """
    graph = _graph(
        monkeypatch,
        _closes(),
        enable_position_contract=True,
        enable_risk_governor=False,
    )

    def _contract(verdict):
        state = {
            "trade_date": "2026-08-19",
            "final_trade_decision": "Buy",
            "risk_snapshot": "risk snapshot: size 2.0%; cvar 1.50%",
            "risk_context": {"liquidity": {"verdict": verdict, "dangers": ["IWF=20.00% below 50.00%"]}},
        }
        return graph._apply_strategy_overlays(state, "NVDA")

    illiquid = _contract("illiquid")
    assert "insufficient_liquidity" in (illiquid.get("position_contract") or "")

    liquid = _contract("liquid")
    assert "insufficient_liquidity" not in (liquid.get("position_contract") or "")

    unknown = _contract(None)
    assert "insufficient_liquidity" not in (unknown.get("position_contract") or "")

    absent = graph._apply_strategy_overlays(
        {"trade_date": "2026-08-19", "final_trade_decision": "Buy"}, "NVDA"
    )
    assert "insufficient_liquidity" not in (absent.get("position_contract") or "")
