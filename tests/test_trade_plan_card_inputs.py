"""W4 — the trade-plan card in the deterministic decision context is measured.

Both ``build_trade_plan`` callers used to pass only ticker/price/config, so
every run rendered a wall of ``unavailable`` (unified stop / tranche rows /
tiers / BE / trail) - including the copy injected into
``computed_decision_context`` that the Trader, PM, risk debators and RM read.
``trading_graph._compiled_decision_context`` now hands it
``trade_plan.measured_inputs``.

Hermetic: the vendor close seam is stubbed; no network, no LLM, no clock.
"""

from __future__ import annotations

import math

import tradingagents.graph.trading_graph as tg


def _closes(n: int = 200) -> list[float]:
    """Deterministic positive series with 1-3% swings (no RNG, no clock)."""
    return [100.0 + 0.02 * i + 3.0 * math.sin(i / 5.0) for i in range(n)]


def _config(**over) -> dict:
    cfg = {
        "enable_strategy_overlays": False,
        "enable_risk_governor": False,
        "enable_tranche_risk": False,
        "enable_events": False,
        "enable_orderflow": False,
        "enable_position_contract": False,
        "enable_agreement": False,
        "enable_calibration": False,
        "target_vol": 0.15,
    }
    cfg.update(over)
    return cfg


def _card(monkeypatch, closes):
    graph = object.__new__(tg.TradingAgentsGraph)
    graph.config = _config()
    monkeypatch.setattr(graph, "_try_fetch_closes", lambda *a, **k: closes)
    text = graph._compiled_decision_context("NVDA", {})
    start = text.index("### Trade plan card: NVDA")
    return text[start:]


def _line(card: str, needle: str) -> str:
    return next(line for line in card.splitlines() if needle in line)


def test_card_renders_measured_stop_and_tranche_rows(monkeypatch):
    card = _card(monkeypatch, _closes())

    stop_line = _line(card, "Unified stop (invalidation)")
    assert "unavailable" not in stop_line

    tranche_line = _line(card, "Tranche execution")
    assert "P1" in tranche_line and "P2" in tranche_line and "P3" in tranche_line
    assert "unavailable" not in tranche_line

    assert "- Reference price:" in card
    assert "Reference price: unavailable" not in card


def test_card_without_closes_stays_unavailable(monkeypatch):
    """No closes -> explicit ``unavailable``, never an invented number."""
    card = _card(monkeypatch, [])

    assert "- Reference price: unavailable" in card
    assert "- **Unified stop (invalidation): unavailable**" in card
    assert "- Tranche execution: unavailable" in card
