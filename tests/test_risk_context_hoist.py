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
        "risk_standalone_cvar_limit_pct": 0.03,
        "risk_portfolio_cvar_budget_pct": 0.03,
        # These fixtures are 200 bars (199 returns), so they declare a floor the
        # series actually clears; the DEFAULT floor (250) and the refusal it
        # produces are pinned by their own test below.
        "risk_cvar_min_observations": 20,
        "target_vol": 0.15,
        "position_odds": 1.0,
        "kelly_fraction": 0.25,
        "risk_per_trade": 0.01,
        "atr_mult": 2.0,
    }
    cfg.update(over)
    return cfg


def _dated(closes: list[float]) -> list[tuple[str, float]]:
    """Unique ascending ISO dates for a close series (28-day months)."""
    return [(f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", c) for i, c in enumerate(closes)]


def _graph(monkeypatch, closes, **cfg_over):
    graph = object.__new__(tg.TradingAgentsGraph)
    graph.config = _config(**cfg_over)
    monkeypatch.setattr(graph, "_try_fetch_closes", lambda *a, **k: closes)
    # The basket mixes the DATED fetch (it refuses a session mismatch), so both
    # views of the one vendor call are stubbed; every name gets the same
    # sessions here, which is the live case.
    monkeypatch.setattr(graph, "_try_fetch_closes_dated", lambda *a, **k: _dated(closes))
    # The decision-binding NAME leg reads the PIT-filtered source (its OWN
    # seam, `_pit_closes`), so the vendor-chain stub above does not feed it.
    monkeypatch.setattr(graph, "_pit_closes", lambda *a, **k: closes)
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
    # TWO limits, one per leg (owner decision 2026-10-12): the name's own
    # standalone limit and the portfolio budget, both shipped at 0.03 so a
    # default run's verdicts are unchanged.
    assert ctx["standalone_cvar_limit_pct"] == pytest.approx(0.03)
    assert ctx["portfolio_cvar_budget_pct"] == pytest.approx(0.03)
    # Each CVaR states the window it was measured over (owner review
    # 2026-10-12): the name leg is one series, the book leg the basket matrix -
    # both one observation shorter than the closes they came from.
    assert ctx["single_cvar_n"] == len(_closes()) - 1
    assert ctx["book_cvar_n"] == len(_closes()) - 1
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
    # BOTH tail legs reach the gate, each with its own number, and which one the
    # portfolio test read is RECORDED rather than inferred (owner decision
    # 2026-10-12: `book_cvar or single_cvar` against one key used to let a PASS
    # on one number sit beside a breach of "the same" limit on the other).
    assert seen["cvar_pct"] == pytest.approx(ctx["book_cvar"])
    assert seen["name_cvar_pct"] == pytest.approx(ctx["single_cvar"])
    assert out["risk_context"]["cvar_gate_basis"] == "configured_reference_book"
    assert seen["liquidity_verdict"] == "illiquid"
    assert seen["liquidity_dangers"] == ctx["liquidity"]["dangers"]
    assert out["risk_context"]["book_drawdown"] == pytest.approx(0.042)
    assert out["risk_context"]["liquidity"]["verdict"] == "illiquid"


def test_a_thin_series_publishes_no_cvar_and_names_the_refusal(monkeypatch):
    """The observation floor fails CLOSED, on BOTH gate legs.

    A CVaR is a mean over a tail the estimator floors (`k = max(1, int(alpha*n))`),
    so `len(rets) >= 5` used to publish a "95 % CVaR" that was ONE observation -
    a statement about a single day wearing a tail measure's name. Below the floor
    the leg publishes nothing and says why, so the governor's CVaR reason stops
    firing instead of pricing noise (owner decision 2026-10-12).
    """
    thin = _graph(monkeypatch, _closes(200), risk_cvar_min_observations=250)
    ctx = thin._precompute_risk_context("NVDA")
    assert "single_cvar" not in ctx
    assert "below the 250-observation floor" in ctx["single_cvar_reason"]
    # The floor is the NAME leg's, deliberately: the book leg's window is the
    # basket names' common VENDOR window (~217 sessions live), where a
    # 250-observation floor would disable the portfolio test rather than harden
    # it. It keeps its own producer guard, and `book_cvar_n` makes a thin book
    # visible.
    assert ctx["book_cvar"] is not None
    assert ctx["book_cvar_n"] == len(_closes(200)) - 1

    # At the floor the leg publishes, and the window rides with the value.
    at_floor = _graph(monkeypatch, _closes(251), risk_cvar_min_observations=250)
    ctx2 = at_floor._precompute_risk_context("NVDA")
    assert ctx2["single_cvar"] is not None
    assert ctx2["single_cvar_n"] == 250
    assert "single_cvar_reason" not in ctx2

    # And a source that returns nothing is a named absence too, never a zero.
    empty = _graph(monkeypatch, [], risk_cvar_min_observations=250)
    assert empty._precompute_risk_context("NVDA")["single_cvar_reason"] == (
        "unavailable: no usable price series"
    )


def test_the_gate_reads_the_candidate_book_when_a_size_is_measured(monkeypatch):
    """The portfolio test measures the book WITH this candidate (owner decision
    2026-10-12): the configured reference basket is identical across every tree of
    a batch, so on its own it cannot speak to the candidate in front of it.

    The size is the one the run itself put on the table - here the position
    contract's own size - and the candidate then becomes the leg the governor
    reads, with `cvar_gate_basis` recording that it did. With no size measured the
    reference book stands instead, and says so.
    """
    graph = _graph(monkeypatch, _closes(260))
    import tradingagents.dataflows.float_shares as float_shares
    import tradingagents.dataflows.statement_parsing as statement_parsing

    monkeypatch.setattr(float_shares, "fetch_float_shares", lambda _t: 4_000_000.0)
    monkeypatch.setattr(
        statement_parsing, "fetch_ticker", lambda _t, _d: {"shares": {"current": 20_000_000.0}}
    )

    import tradingagents.strategies.risk_governor as rg

    seen: dict = {}

    def _govern(size, cfg, **kw):
        seen.update(kw)
        return {"verdict": "PASS", "reasons": [], "numbers": "captured"}

    monkeypatch.setattr(rg, "govern", _govern)
    state = {
        "trade_date": "2026-08-19",
        "final_trade_decision": "Buy",
        "position_contract": "size 10.0%, stop 90.0 (from entry 100.00)",
    }
    out = graph._apply_strategy_overlays(state, "NVDA")
    ctx = out["risk_context"]
    assert ctx["cvar_gate_basis"] == "candidate_book"
    assert ctx["candidate_weight_pct"] == pytest.approx(0.10)
    assert ctx["candidate_cvar"] is not None
    assert ctx["candidate_cvar_n"] == len(_closes(260)) - 1
    assert ctx["candidate_delta_cvar"] is not None
    assert seen["cvar_pct"] == pytest.approx(ctx["candidate_cvar"])
    assert seen["name_cvar_pct"] == pytest.approx(ctx["single_cvar"])

    # No measured size -> the configured reference book is the portfolio leg.
    out2 = graph._apply_strategy_overlays(
        {"trade_date": "2026-08-19", "final_trade_decision": "Hold"}, "NVDA"
    )
    ctx2 = out2["risk_context"]
    assert ctx2["cvar_gate_basis"] == "configured_reference_book"
    assert "candidate_cvar" not in ctx2


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


def test_kill_switch_state_is_produced_and_can_fire(monkeypatch):
    """The emergency tier is WRITTEN, so EXIT / NO_TRADE can finally fire.

    `signal_action_split`'s `kill_switch` leg was dead: three call sites read
    ``state["kill_switch_state"]["active"]`` and NOTHING wrote the key, so every
    read took the silent ``False`` default and a hard book drawdown could never
    force the emergency action. The producer is MEASURED - the one realized book
    drawdown this run already resolved, against the configured HWM hard tier -
    and the session-p&l leg, which has no in-engine producer (the executor owns
    live p&l), is NAMED rather than guessed.
    """
    from tradingagents.strategies.signal_action import signal_action_split

    graph = _graph(monkeypatch, _closes())

    def _run(drawdown):
        state = {
            "trade_date": "2026-08-19",
            "final_trade_decision": "Hold",
            "risk_context": {"book_drawdown": drawdown},
        }
        return graph._apply_strategy_overlays(state, "NVDA").get("kill_switch_state") or {}

    # A realized book drawdown past the hard tier arms it.
    armed = _run(0.25)
    assert armed.get("active") is True
    assert armed.get("drawdown_pct") == pytest.approx(0.25)
    assert armed.get("hard_max_drawdown_pct") == pytest.approx(0.20)
    assert "drawdown" in (armed.get("measured_legs") or [])
    # The leg with no in-engine producer is named, never silently false.
    assert armed.get("day_loss_pct") is None
    assert "day_loss" in (armed.get("unmeasured_legs") or [])

    # And the split it feeds now reaches the emergency action.
    split = signal_action_split(
        "Hold", gate_verdict="REJECT", kill_switch=bool(armed.get("active"))
    )
    assert split["portfolio_action"] == "NO_TRADE"

    # Below the tier it is measured CLEAR, not absent.
    clear = _run(0.02)
    assert clear.get("active") is False
    assert "drawdown" in (clear.get("measured_legs") or [])

    # No measurable drawdown: the leg is absent from measured_legs, so the state
    # says "not measured" instead of reporting a clear book.
    unknown = _run(None)
    assert unknown.get("active") is False
    assert "drawdown" not in (unknown.get("measured_legs") or [])


def test_the_plan_consumes_the_pre_graph_risk_context(monkeypatch):
    """The plan's risk half reads the SAME snapshot the governor gates on.

    Guards the producer<->consumer seam: ``_precompute_risk_context`` writes
    ``single_cvar`` / ``standalone_cvar_limit_pct`` / ``liquidity.verdict`` and
    ``_compiled_decision_context`` hands exactly those to the plan. A rename on
    either side would silently put the entry block back to
    ``cvar_status: NO_SOURCE`` while the report's decision basis still cites a
    measured CVaR - the internal inconsistency this wiring removes (MU
    2026-10-02 read ``CVaR: NO_SOURCE`` in the card beside ``CVaR 10.79% >
    budget 3.00%`` in the same report's basis line).
    """
    graph = _graph(monkeypatch, _closes())
    import tradingagents.dataflows.float_shares as float_shares
    import tradingagents.dataflows.statement_parsing as statement_parsing

    monkeypatch.setattr(float_shares, "fetch_float_shares", lambda _t: 4_000_000.0)
    monkeypatch.setattr(
        statement_parsing, "fetch_ticker", lambda _t, _d: {"shares": {"current": 20_000_000.0}}
    )

    ctx = graph._precompute_risk_context("NVDA")
    assert ctx["single_cvar"] is not None

    capture: dict = {}
    graph._compiled_decision_context(
        "NVDA", {"risk_context": ctx}, closes=_closes(), capture=capture
    )
    entry = capture["entry_exit"]["entry"]
    # The measured CVaR reached the plan as a STATUS (OK / OVER_BUDGET) - never
    # NO_SOURCE, and never a price.
    assert entry["cvar_status"] in ("OK", "OVER_BUDGET")
    assert entry["liquidity_status"] == ctx["liquidity"]["verdict"]
