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
    ENGINE_TOOLS,
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
    return names & set(ENGINE_TOOLS.values())


@pytest.fixture(autouse=True)
def _restore_config():
    yield
    set_config(dict(DEFAULT_CONFIG))


def test_no_engine_leaf_is_bound_to_any_analyst():
    """§13.3: engine leaves are application-internal, not LLM-facing tools.

    The engines are computed by the application and their results are SUPPLIED
    to the prompt, so a second discretionary route to a number the prompt
    already carries is exactly the ambiguity the contract removes. This
    supersedes the earlier "bindings are the inverse of the ownership map"
    contract: the map now drives the SUPPLIED BLOCK, not a tool binding.
    """
    set_config(_cfg())
    for analyst in ANALYSTS:
        assert _bound_score_leaves(analyst) == set(), analyst


def test_technical_score_is_bound_to_no_analyst():
    """The 2026-09-19 defect was `get_technical_score` on the FUNDAMENTALS
    analyst. The fix then was to move it to the market analyst; the contract now
    is that it is bound to neither - the map places its RESULT, and the result
    reaches both reports through the supplied scorecard."""
    set_config(_cfg())
    for analyst in ANALYSTS:
        assert "get_technical_score" not in _bound_score_leaves(analyst), analyst


def test_fundamentals_analyst_binds_no_engine_leaf():
    set_config(_cfg())
    assert _bound_score_leaves("fundamentals") == set()


def test_report_level_engines_get_no_analyst_block():
    """Regime, risk and trade are report-level by decision, not by omission.

    They are in the SUPPLIED scorecard like every other engine, but no analyst
    owns their section, so none is asked to report them.
    """
    set_config(_cfg())
    report_level = {e for e, section in ENGINE_SECTIONS.items() if section is None}
    assert report_level == {"regime", "risk", "trade"}
    for analyst in ANALYSTS:
        owned = engines_for_analyst(analyst)
        for engine in report_level:
            assert engine not in owned, (analyst, engine)


def test_every_engine_is_placed_exactly_once():
    """A section per engine, and only the four analyst sections are used."""
    assert set(ENGINE_SECTIONS) == set(ENGINES)
    assert set(ENGINE_SECTIONS.values()) - {None} <= set(ANALYSTS)


def test_gate_off_binds_no_score_leaf_at_all():
    """Gate off => the toolset is byte-identical to a pre-scorecard one."""
    set_config(_cfg(engines=False, master=False))
    for analyst in ANALYSTS:
        assert _bound_score_leaves(analyst) == set(), analyst


# --- the supplied full scorecard (§13.1, §13.2) -----------------------------


def _fake_snapshot(**over):
    """A snapshot shaped like `quant_scorecard`'s, with every engine measured."""
    engines = {}
    for name in ENGINES:
        engines[name] = {
            "engine": name,
            "enabled": True,
            "score": 60.0,
            "coverage": 1.0,
            "band": None,
            "reason": None,
            "result": {"floor": 2},
        }
    engines["news"] = {
        "engine": "news",
        "enabled": True,
        "score": None,
        "coverage": None,
        "band": None,
        "reason": "no news producer measured",
        "result": None,
    }
    engines.update(over)
    return {"ticker": "MSFT", "trade_date": "2026-09-19", "engines": engines}


def test_every_analyst_receives_the_full_scorecard():
    """§13.1: not only the engine the analyst owns - all eight."""
    snap = _fake_snapshot()
    for analyst in ANALYSTS:
        block = report_hygiene.scorecard_context_block(
            "MSFT", "2026-09-19", _cfg(), snap
        )
        for engine in ENGINES:
            assert report_hygiene._engine_label(engine) in block, (analyst, engine)


def test_scorecard_prints_tradescore_last_and_labelled_downstream():
    """§13.2: the composite is a reference point, not an anchor."""
    block = report_hygiene.scorecard_context_block(
        "MSFT", "2026-09-19", _cfg(), _fake_snapshot()
    )
    body = block.split("--- engine scorecard", 1)[1]
    assert body.index("TradeScore") > body.index("RiskScore")
    assert "NOT a trading instruction" in block


def test_scorecard_prints_score_coverage_floor_and_status():
    """§13.4: the floor is exposed beside the coverage."""
    block = report_hygiene.scorecard_context_block(
        "MSFT", "2026-09-19", _cfg(), _fake_snapshot()
    )
    assert "coverage 1" in block
    assert "required floor 2" in block
    assert "ABOVE FLOOR" in block


def test_scorecard_names_an_unmeasurable_engine_as_na_not_zero():
    """`NA != 0` (master rule 1) must survive into the LLM context."""
    block = report_hygiene.scorecard_context_block(
        "MSFT", "2026-09-19", _cfg(), _fake_snapshot()
    )
    assert "NewsScore: NA - no news producer measured" in block
    assert "NewsScore: 0" not in block


def test_scorecard_block_is_empty_when_the_master_gate_is_off():
    """The master gate governs the surface: no block, and no snapshot read."""
    assert (
        report_hygiene.scorecard_context_block(
            "MSFT", "2026-09-19", _cfg(master=False), _fake_snapshot()
        )
        == ""
    )


def test_scorecard_block_is_empty_without_a_snapshot():
    """No snapshot means no numbers - never a recompute, never a guess."""
    assert (
        report_hygiene.scorecard_context_block("MSFT", "2026-09-19", _cfg(), None) == ""
    )


def test_gate_off_engines_are_omitted_from_the_scorecard():
    """A gated-off engine is not part of the scorecard at all.

    The manifest sentence names all eight engines by design, so the check is on
    the rendered rows, not the whole block.
    """
    snap = _fake_snapshot()
    snap["engines"]["risk"]["enabled"] = False
    block = report_hygiene.scorecard_context_block(
        "MSFT", "2026-09-19", _cfg(), snap
    )
    rows = block.split("--- engine scorecard", 1)[1].split("--- end scorecard", 1)[0]
    assert not [ln for ln in rows.splitlines() if ln.startswith("RiskScore:")]
    assert [ln for ln in rows.splitlines() if ln.startswith("TechnicalScore:")]


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


# --- the deterministic engine section in the analyst report -----------------


def test_sentiment_report_gets_its_engine_section_deterministically():
    """The gap this closes: `SentimentReport` (`agents/schemas.py:444`) has no
    field for an engine result, so the supplied block reached that analyst's
    PROMPT but its appearance in the REPORT was model discretion - the earlier
    QCOM run's model volunteered it into `narrative`, the next run's did not.
    Rendering it here removes the discretion."""
    section = report_hygiene.engine_report_section(
        "sentiment", "MSFT", "2026-09-19", _cfg(), _fake_snapshot()
    )
    assert section.startswith("## SentimentScore (engine score)")
    assert "SentimentScore: 60/100" in section
    assert "required floor 2" in section
    assert "ABOVE FLOOR" in section


def test_an_analyst_gets_only_the_engines_it_owns():
    """Placement stays the ownership map's decision - the renderer reads it."""
    snap = _fake_snapshot()
    for analyst in ANALYSTS:
        section = report_hygiene.engine_report_section(
            analyst, "MSFT", "2026-09-19", _cfg(), snap
        )
        for engine in engines_for_analyst(analyst):
            assert report_hygiene._engine_label(engine) in section, (analyst, engine)
        for engine in ENGINES:
            if engine in engines_for_analyst(analyst):
                continue
            assert f"## {report_hygiene._engine_label(engine)} (engine score)" not in section, (
                analyst,
                engine,
            )


def test_engine_section_is_empty_when_the_master_gate_is_off():
    assert (
        report_hygiene.engine_report_section(
            "market", "MSFT", "2026-09-19", _cfg(master=False), _fake_snapshot()
        )
        == ""
    )


def test_engine_section_is_empty_without_a_snapshot():
    """No snapshot means no section - never a recompute, never a guess."""
    assert (
        report_hygiene.engine_report_section("market", "MSFT", "2026-09-19", _cfg(), None)
        == ""
    )


def test_engine_section_names_an_unmeasurable_engine_as_na():
    snap = _fake_snapshot()
    snap["engines"]["news"] = {
        "engine": "news",
        "enabled": True,
        "score": None,
        "coverage": None,
        "band": None,
        "reason": "no news producer measured",
        "result": None,
    }
    section = report_hygiene.engine_report_section(
        "news", "MSFT", "2026-09-19", _cfg(), snap
    )
    assert "**NewsScore: NA** - no news producer measured" in section
    assert "NewsScore: 0" not in section


def test_engine_section_is_deterministic():
    """Same snapshot in, byte-identical text out - no clock, no ordering drift."""
    snap = _fake_snapshot()
    first = report_hygiene.engine_report_section(
        "news", "MSFT", "2026-09-19", _cfg(), snap
    )
    second = report_hygiene.engine_report_section(
        "news", "MSFT", "2026-09-19", _cfg(), snap
    )
    assert first == second
