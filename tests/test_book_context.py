"""Number integrity for the measured book drawdown: ONE resolver, one number.

Regression (NVDA 2026-09-12 decision.md review): the report carried two numbers
under the name "book drawdown" - the rendered block said 7.24% (the configured
8-name basket, the value the governor gated on) while ``get_book_tail_risk`` /
``get_composed_risk_gate`` defaulted to ``{ticker: 1.0}`` and reported NVDA's own
20.21%, which the trader then fed into ``get_risk_gate`` and cited as a REJECT
the real gate never issued. The resolution rules and the honest source label are
what these tests pin. Hermetic: closes are injected, no network.
"""

from __future__ import annotations

from unittest import mock

import pytest

from tradingagents.strategies import book_context as BC

pytestmark = pytest.mark.timeout(120)


def _closes(n: int, start: float = 100.0, end: float = 200.0) -> list[float]:
    """Deterministic positive ramp."""
    return [start + (end - start) * i / (n - 1) for i in range(n)]


def _crash_closes(n: int = 60) -> list[float]:
    """Ramp up then a ~30% decline: a large, known drawdown."""
    up = _closes(n // 2, 100.0, 200.0)
    down = [200.0 * (0.70 ** (i / (n // 2 - 1))) for i in range(n // 2)]
    return up + down


def test_configured_basket_needs_two_names():
    assert BC.configured_basket({"risk_basket_tickers": ["SPY"]}) == {}
    assert BC.configured_basket({"risk_basket_tickers": []}) == {}
    assert BC.configured_basket(
        {"risk_basket_tickers": ["SPY", "GLD"], "risk_basket_weights": {"SPY": 0.6}}
    ) == {"SPY": 0.6, "GLD": 0.0}


def test_no_basket_returns_the_name_labelled_as_such():
    dd, meta = BC.measured_book_drawdown(
        {}, lambda name: _crash_closes(), fallback_symbol="NVDA"
    )
    assert dd is not None and dd > 0.25
    assert meta["source"] == "single_name"
    assert BC.describe_source(meta) == "NVDA alone (no basket configured)"


def test_configured_basket_wins_and_differs_from_the_name():
    """The reported number is the basket's, and a caller can see it is not the
    name's own drawdown - the confusion the defect shipped."""
    cfg = {
        "risk_basket_tickers": ["AAA", "BBB"],
        "risk_basket_weights": {"AAA": 0.5, "BBB": 0.5},
    }
    series = {"AAA": _crash_closes(), "BBB": _closes(60, 100.0, 200.0)}
    dd, meta = BC.measured_book_drawdown(cfg, lambda n: series[n], fallback_symbol="AAA")
    solo, _ = BC.measured_book_drawdown({}, lambda n: series["AAA"], fallback_symbol="AAA")
    assert meta["source"] == "configured_basket"
    assert meta["resolved"] == ["AAA", "BBB"]
    assert BC.describe_source(meta) == "configured basket (2/2 names)"
    assert dd is not None and solo is not None and dd != solo


def test_unresolvable_basket_falls_back_and_says_so():
    cfg = {"risk_basket_tickers": ["AAA", "BBB"], "risk_basket_weights": {}}
    dd, meta = BC.measured_book_drawdown(
        cfg, lambda n: _crash_closes() if n == "AAA" else [], fallback_symbol="AAA"
    )
    assert dd is not None
    assert meta["source"] == "single_name_fallback"
    assert BC.describe_source(meta) == "AAA alone (configured basket unresolved)"
    assert meta["basket"]["source"] == "configured_basket"  # why it fell back


def test_one_resolved_leg_is_not_a_book():
    cfg = {"risk_basket_tickers": ["AAA", "BBB"], "risk_basket_weights": {"AAA": 1.0}}
    dd, meta = BC.measured_book_drawdown(cfg, lambda n: _crash_closes() if n == "AAA" else [])
    assert dd is None and meta["source"] == "configured_basket"


def test_missing_history_is_unknown_not_zero():
    dd, meta = BC.measured_book_drawdown({}, lambda name: [100.0, 101.0], fallback_symbol="NVDA")
    assert dd is None and meta["source"] == "single_name"


# ---------------------------------------------------------------------------
# Tool wiring: the label reaches the report, and a supplied drawdown is a
# what-if that cannot move the verdict.
# ---------------------------------------------------------------------------


def test_book_tail_risk_reports_which_book_it_measured(monkeypatch):
    from tradingagents.agents.utils import analysis_tools as T

    monkeypatch.setattr(T, "_ohlcv", lambda ticker: {"closes": _crash_closes()})
    out = T.get_book_tail_risk.invoke({"ticker": "NVDA"})
    assert "source=configured basket (8/8 names)" in out

    with mock.patch(
        "tradingagents.dataflows.config.get_config",
        lambda: {"risk_basket_tickers": [], "risk_basket_weights": {}},
    ):
        out = T.get_book_tail_risk.invoke({"ticker": "NVDA"})
    assert "source=NVDA alone (no basket configured)" in out


def test_composed_gate_labels_a_single_name_fallback(monkeypatch):
    from tradingagents.agents.utils import analysis_tools as T

    monkeypatch.setattr(T, "_ohlcv", lambda ticker: {"closes": _crash_closes()})
    cfg = {
        "risk_basket_tickers": [],
        "risk_basket_weights": {},
        "risk_max_drawdown_pct": 0.10,
        "max_position_pct": 0.30,
        "risk_daily_cvar_budget_pct": 0.03,
        "sector_cap_limit": 0.35,
        "risk_daily_loss_budget_pct": 0.03,
        "risk_hwm_soft_pct": 0.10,
        "risk_hwm_hard_pct": 0.20,
    }
    with mock.patch("tradingagents.dataflows.config.get_config", lambda: cfg):
        out = T.get_composed_risk_gate.invoke({"ticker": "NVDA", "size_pct": 0.02})
    assert "source NVDA alone (no basket configured)" in out
    assert "blocked by portfolio" in out


def test_get_risk_gate_treats_a_supplied_drawdown_as_a_what_if():
    """The house verdict must not be decided by a caller-supplied state value:
    the NVDA verification passed 20.2% and reported a REJECT the composed gate
    never issued."""
    from tradingagents.agents.utils import analysis_tools as T

    out = T.get_risk_gate.invoke({"size_pct": 0.015, "drawdown_pct": 0.202})
    assert "risk: PASS" in out
    assert "REJECT" not in out.split("drawdown_whatif")[0]  # verdict precedes the what-if
    assert "drawdown_whatif=20.20%" in out
    assert "NOT the house verdict" in out
    assert "get_composed_risk_gate" in out


def test_get_risk_gate_without_a_drawdown_is_unchanged():
    from tradingagents.agents.utils import analysis_tools as T

    out = T.get_risk_gate.invoke({"size_pct": 0.40})
    assert "REJECT" in out and "cap 30.0%" in out
