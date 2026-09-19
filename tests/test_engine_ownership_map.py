"""The engine ownership map: one table decides where a score appears.

Pins the 2026-09-19 defect where `get_technical_score` was bound to the
FUNDAMENTALS analyst - an analyst that does not own the price/trend domain - and
the master `enable_quant_scorecard` gate was absent from the repro config hash.

The contract under test is that three surfaces are three readings of one table:

* the tool binding (`agents/toolsets.py`),
* the per-analyst prompt fragment (`agents/utils/report_hygiene.py`),
* the report placement (`quant_scorecard.ENGINE_SECTIONS`).
"""

from __future__ import annotations

import pytest

from tradingagents.agents import toolsets
from tradingagents.agents.utils import report_hygiene
from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.strategies.quant_scorecard import (
    ENGINE_GATES,
    ENGINE_SECTIONS,
    engines_for_analyst,
)

ANALYSTS = ("market", "sentiment", "news", "fundamentals")
ENGINES = tuple(ENGINE_GATES)


def _cfg(**over: bool) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    for key in ENGINE_GATES.values():
        cfg[key] = over.get("engines", True)
    cfg["enable_quant_scorecard"] = over.get("master", True)
    return cfg


def _bound_score_leaves(analyst: str) -> set[str]:
    """The ENGINE score leaves bound to this analyst - not every `*_score` tool.

    `get_valuation_z_score` is a valuation tool that happens to end in `_score`;
    only the eight engine readers are governed by the ownership map.
    """
    names = {
        getattr(t, "name", getattr(t, "__name__", str(t)))
        for t in toolsets.analyst_toolset(analyst)
    }
    return names & set(toolsets.ENGINE_TOOLS.values())


@pytest.fixture(autouse=True)
def _restore_config():
    yield
    set_config(dict(DEFAULT_CONFIG))


def test_binding_is_the_inverse_of_the_ownership_map():
    """Every analyst binds exactly the leaves of the engines it owns."""
    set_config(_cfg())
    for analyst in ANALYSTS:
        owned = {
            toolsets.ENGINE_TOOLS[e]
            for e in engines_for_analyst(analyst)
        }
        assert _bound_score_leaves(analyst) == owned, analyst


def test_technical_score_belongs_to_the_market_analyst():
    """The defect: the price/trend domain's engine was on the valuation analyst."""
    set_config(_cfg())
    assert "get_technical_score" in _bound_score_leaves("market")
    assert "get_technical_score" not in _bound_score_leaves("fundamentals")


def test_fundamentals_analyst_binds_only_the_fundamental_engine():
    set_config(_cfg())
    assert _bound_score_leaves("fundamentals") == {"get_fundamental_score"}


def test_report_level_engines_are_bound_to_no_analyst():
    """Regime, risk and trade are report-level by decision, not by omission."""
    set_config(_cfg())
    report_level = {e for e, section in ENGINE_SECTIONS.items() if section is None}
    assert report_level == {"regime", "risk", "trade"}
    bound = set().union(*(_bound_score_leaves(a) for a in ANALYSTS))
    for engine in report_level:
        assert toolsets.ENGINE_TOOLS[engine] not in bound, engine


def test_every_engine_is_placed_exactly_once():
    """A section per engine, and only the four analyst sections are used."""
    assert set(ENGINE_SECTIONS) == set(ENGINES)
    assert set(ENGINE_SECTIONS.values()) - {None} <= set(ANALYSTS)


def test_gate_off_binds_no_score_leaf_at_all():
    """Gate off => the toolset is byte-identical to a pre-scorecard one."""
    set_config(_cfg(engines=False, master=False))
    for analyst in ANALYSTS:
        assert _bound_score_leaves(analyst) == set(), analyst


def test_master_gate_off_makes_the_prompt_block_empty():
    """The master gate governs the surface: no block, even with engines on."""
    assert report_hygiene.engine_score_block(
        "market", "MSFT", "2026-09-19", _cfg(master=False)
    ) == ""


def test_report_level_analyst_key_gets_no_block():
    """An analyst with no owned engine gets nothing to report."""
    assert report_hygiene.engine_score_block(
        "sentiment", "MSFT", "2026-09-19", _cfg(master=True)
    ) != ""  # sentiment DOES own the sentiment engine
    assert report_hygiene.engine_score_block(
        "nonexistent", "MSFT", "2026-09-19", _cfg(master=True)
    ) == ""


def test_block_carries_the_owned_engine_numbers(monkeypatch):
    """The result is SUPPLIED, so it lands regardless of the model's choices."""
    monkeypatch.setattr(
        report_hygiene, "_call_engine", lambda name, t, d: f"{name}: 72/100 coverage 68%"
    )
    block = report_hygiene.engine_score_block("market", "MSFT", "2026-09-19", _cfg())
    assert "get_technical_score: 72/100 coverage 68%" in block
    assert "TechnicalScore" in block
    assert "coverage" in block.lower()
    assert "NOT an order" in block
    # and it does NOT carry an engine the market analyst does not own
    assert "get_fundamental_score" not in block


def test_block_carries_both_engines_owned_by_the_news_analyst(monkeypatch):
    monkeypatch.setattr(
        report_hygiene, "_call_engine", lambda name, t, d: f"{name}: measured"
    )
    block = report_hygiene.engine_score_block("news", "MSFT", "2026-09-19", _cfg())
    assert "get_news_score: measured" in block
    assert "get_event_state: measured" in block


def test_config_hash_moves_with_the_master_scorecard_gate():
    """`same hash => same effective inputs` must hold for the master gate too."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import repro_check

    from tradingagents.default_config import DEFAULT_CONFIG as live

    original = live.get("enable_quant_scorecard")
    try:
        live["enable_quant_scorecard"] = False
        repro_check._CONFIG_HASH_CACHE.clear()
        off = repro_check._config_hash()
        live["enable_quant_scorecard"] = True
        repro_check._CONFIG_HASH_CACHE.clear()
        on = repro_check._config_hash()
    finally:
        live["enable_quant_scorecard"] = original
        repro_check._CONFIG_HASH_CACHE.clear()
    assert off != on
