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

import pytest

import tradingagents.graph.trading_graph as tg

# Cold-start: this file imports the graph, whose module scope drags in the
# analysis tools; a cold interpreter spends minutes inside conftest. The
# file-level marker overrides --timeout, so it has to be the generous one.
pytestmark = pytest.mark.timeout(600)


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


def test_card_renders_the_advisory_entry_ceiling_row(monkeypatch):
    """Phase 0: the card carries the long-entry ceiling as an advisory row.

    The R:R term is measurable from the closes alone, so a price-only card
    reports it and *names* the two statement-path sources it could not see -
    coverage 1/3, never a silent 3/3.
    """
    card = _card(monkeypatch, _closes())

    ceiling_line = _line(card, "Entry ceiling (advisory)")
    assert "unavailable" not in ceiling_line
    assert "binding: risk_reward" in ceiling_line
    assert "coverage 1/3" in ceiling_line
    assert "missing: valuation, expected_return" in ceiling_line

    headroom = _line(card, "Ceiling headroom")
    assert "distance" in headroom and "margin" in headroom


def test_card_without_closes_reports_no_ceiling_source(monkeypatch):
    """No closes -> no measurable ceiling source -> NO_SOURCE, never a price."""
    card = _card(monkeypatch, [])

    ceiling_line = _line(card, "Entry ceiling (advisory)")
    assert ceiling_line.startswith(
        "- Entry ceiling (advisory): unavailable - status NO_SOURCE"
    )
    assert "coverage 0/3" in ceiling_line
    assert "Ceiling headroom" not in card


def test_card_renders_the_103_exit_predicate_over_the_measured_levels(monkeypatch):
    """§103's EXIT block reaches the Trader and the PM through this one card.

    ``build_trade_plan`` called ``entry_exit_price`` without a single exit
    input and then discarded ``assembled["exit"]``, so ``exits.exit_decision``
    - which has no other caller in the repo - never ran for a plan and the
    agents saw no exit price at all. The trailing level is the trail read's own
    price; the target is the plan's final tier.
    """
    card = _card(monkeypatch, _closes())

    predicate = _line(card, "§103 exit predicate")
    assert "coverage 3/7" in predicate
    assert "stop=False" in predicate
    assert "trailing_stop=" in predicate
    assert "target=" in predicate

    levels = _line(card, "§103 exit levels")
    assert "stop_loss " in levels
    assert "trailing_stop " in levels and "(EMA20)" in levels
    assert "target " in levels and "(T2)" in levels
    assert "precedence: risk_gate > stop > trailing_stop > target" in levels


def test_the_exit_predicate_fires_on_a_breached_stop_at_its_own_price():
    """A breached level names the exit and the price it would transact at."""
    from tradingagents.strategies.trade_plan import build_trade_plan

    card = build_trade_plan(ticker="T", price=90.0, tranche={"stop": 95.0}, config={})

    predicate = _line(card, "§103 exit predicate")
    assert "FIRES - stop at exit price 95.00" in predicate
    assert "coverage 1/7" in predicate


def test_card_without_closes_names_every_exit_absent(monkeypatch):
    """Nothing decidable -> ``exit`` is None and every exit is named absent.

    An unmeasured exit must never read as "no exit" (``exit_decision``'s own
    contract), which is why the absent list is rendered rather than an
    all-false condition set.
    """
    card = _card(monkeypatch, [])

    predicate = _line(card, "§103 exit predicate")
    assert "no exit condition could be evaluated" in predicate
    assert "coverage 0/7" in predicate

    absent = _line(card, "not measurable at plan time")
    assert "(absent, NOT 'no exit')" in absent
    assert "risk_gate" in absent and "thesis_break" in absent and "expected_value" in absent


def test_final_entry_price_names_the_value_of_every_term(monkeypatch):
    """§100's ``min`` is only auditable if the terms behind it are readable."""
    card = _card(monkeypatch, _closes())

    line = _line(card, "Final entry price")
    assert "over the §103 terms present" in line
    assert "max_entry_price=" in line
    assert "target_entry_price=" in line


def _card_and_block(monkeypatch, closes):
    """The card and the §103 block captured from its own assembly."""
    graph = object.__new__(tg.TradingAgentsGraph)
    graph.config = _config()
    monkeypatch.setattr(graph, "_try_fetch_closes", lambda *a, **k: closes)
    capture: dict = {}
    graph._compiled_decision_context("NVDA", {}, capture=capture)
    return capture.get("entry_exit") or {}


def test_the_card_captures_the_103_block_it_rendered(monkeypatch):
    """The Trader, the PM and the artifact all read this ONE dict, so it must
    carry the card's own numbers: the captured final entry price is the value
    the card's "Final entry price" row printed."""
    block = _card_and_block(monkeypatch, _closes())

    assert block["entry"]["final_entry_price"] is not None
    final_line = _line(_card(monkeypatch, _closes()), "Final entry price")
    assert f"{block['entry']['final_entry_price']:.2f}" in final_line
    # The exit side travels with it: the levels the §101 predicate was evaluated
    # on, and the precedence it names the first exit in.
    assert block["levels"]["unified_stop"] is not None
    assert block["levels"]["target"] is not None
    assert block["exit"]["precedence"][0] == "risk_gate"


def test_the_rendered_price_block_names_every_absent_exit(monkeypatch):
    """This block is what the Trader's and the PM's sections print. A level the
    run could not measure is named absent, never read as "no exit"."""
    from tradingagents.strategies.trade_plan import render_entry_exit_block

    text = render_entry_exit_block(_card_and_block(monkeypatch, _closes()))

    assert "Final entry price:" in text
    assert "Entry ceiling (max):" in text
    assert "Exit predicate:" in text
    assert "risk_gate" in text and "thesis_break" in text
    assert "unavailable" in text  # the CVaR / execution rows were unmeasurable
    # It travels inside text `reporting._looks_truncated` scans for a max_tokens
    # cut, so the block ends on a sentence, never on a bare measured name.
    assert text.rstrip().endswith(".")


def test_the_price_block_renders_nothing_for_a_run_that_computed_no_card():
    from tradingagents.strategies.trade_plan import render_entry_exit_block

    assert render_entry_exit_block(None) == ""
    assert render_entry_exit_block({}) == ""
