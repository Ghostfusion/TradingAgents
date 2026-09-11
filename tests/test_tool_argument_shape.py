"""No LLM-facing tool may ask the model to transcribe numbers.

A tool is only usable if the model can actually supply its input. Every tool
whose advertised schema takes a list/object argument asks the model to
re-type numbers it holds only as prose - the diagnosis behind this plan's R2
(``get_vif_read`` wanted a dict of indicator series, so a call meant copying
60-90 digits and a single dropped value produced a confident wrong answer).

The rule is not "no list arguments" - identifiers and windows are fine, and a
tool must be allowed to take a list of TICKERS. It is: a complex argument is a
decision, recorded here with its reason, and the set may only shrink as tools
are reshaped to take names. A brand-new bound tool with a list/dict argument
fails the gate until someone writes that decision down.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# tool -> (kind, why). "names" = identifiers/windows only, the tool fetches
# the numbers itself. "numeric" = the model must supply figures; recorded debt
# with a conversion note, not an accepted design.
COMPLEX_ARG_DECISIONS: dict[str, tuple[str, str]] = {
    "get_allocation": ("numeric", "dict of name -> score; reshape to tickers + a fetched score"),
    "get_allocation_black_litterman": (
        "numeric",
        "market_caps is a name -> cap map; tickers alone would let the tool fetch caps",
    ),
    "get_book_correlation": ("numeric", "dict of name -> aligned return series"),
    "get_constituent_cap_weights": ("numeric", "list of raw weights; a ticker list is the drivable form"),
    "get_exit_overrides": ("numeric", "targets + per-symbol state maps of figures"),
    "get_hrp_alloc": ("numeric", "dict of name -> aligned return series"),
    "get_pair_trade_signal": ("numeric", "two close series (pre-existing)"),
    "get_portfolio_weights": ("numeric", "map of ticker -> score"),
    "get_risk_parity_alloc": ("numeric", "dict of name -> aligned return series"),
    "get_signal_quality": ("numeric", "signal + forward-return series, aligned 1:1"),
    "get_ts_momentum_weights": ("numeric", "dict of name -> daily close series"),
}


def _surfaces() -> list[tuple[str, list]]:
    from tradingagents.agents.toolsets import analyst_toolset
    from tradingagents.agents.utils import risk_tool_loop

    risk_tool_loop._build_lists()
    return [
        ("market", analyst_toolset("market")),
        ("news", analyst_toolset("news")),
        ("fundamentals", analyst_toolset("fundamentals")),
        ("risk debators", risk_tool_loop.RISK_DEBATOR_TOOLS),
        ("trader", risk_tool_loop.TRADER_TOOLS),
    ]


def complex_args(tool) -> list[str]:
    """Advertised parameter names whose JSON type is array or object."""
    props: dict = {}
    schema = getattr(tool, "args_schema", None)
    if schema is not None and hasattr(schema, "model_json_schema"):
        props = (schema.model_json_schema().get("properties") or {})
    if not props and isinstance(getattr(tool, "args", None), dict):
        props = tool.args
    return sorted(
        name
        for name, spec in props.items()
        if isinstance(spec, dict) and spec.get("type") in ("array", "object")
    )


def _bound_tools() -> dict[str, set[str]]:
    return {surface: {t.name for t in tools} for surface, tools in _surfaces()}


def test_complex_arguments_are_decided():
    offenders: dict[str, list[str]] = {}
    for surface, tools in _surfaces():
        for tool in tools:
            args = complex_args(tool)
            if args and tool.name not in COMPLEX_ARG_DECISIONS:
                offenders.setdefault(surface, []).append(f"{tool.name}({', '.join(args)})")
    assert not offenders, (
        "these bound tools advertise list/object arguments with no recorded "
        f"decision - the model would have to transcribe numbers: {offenders}. "
        "Reshape the tool to take names/identifiers, or add an entry to "
        "COMPLEX_ARG_DECISIONS with the reason."
    )


def test_decisions_are_live_and_shrinkable():
    """A decision must still describe a bound tool that still has the arg."""
    surfaces = _bound_tools()
    all_bound = set().union(*surfaces.values())
    by_name = {t.name: t for _, tools in _surfaces() for t in tools}
    unknown = sorted(n for n in COMPLEX_ARG_DECISIONS if n not in all_bound)
    assert not unknown, (
        "COMPLEX_ARG_DECISIONS lists tools that are not bound (any more): "
        f"{unknown}. Delete those entries so the debt list only shrinks."
    )
    resolved = sorted(n for n in COMPLEX_ARG_DECISIONS if not complex_args(by_name[n]))
    assert not resolved, (
        f"these tools no longer take list/object arguments: {resolved}. "
        "Delete their entries - the debt is paid."
    )


def test_detector_has_teeth():
    class FakeTool:
        name = "get_fake"

        class args_schema:  # noqa: N801 - mirrors attrs-style access
            @staticmethod
            def model_json_schema():
                return {"properties": {"series": {"type": "array"}, "ticker": {"type": "string"}}}

    assert complex_args(FakeTool) == ["series"]

    class CleanTool:
        name = "get_clean"
        args_schema = type(
            "S", (), {"model_json_schema": staticmethod(lambda: {"properties": {"ticker": {"type": "string"}}})}
        )

    assert complex_args(CleanTool) == []


@pytest.mark.parametrize("surface", sorted(_bound_tools()), ids=lambda s: s)
def test_no_duplicate_tool_names_within_a_surface(surface):
    """One name, one callable - a duplicate would shadow the earlier entry."""
    tools = dict(_surfaces())[surface]
    names = [t.name for t in tools]
    assert len(names) == len(set(names)), f"{surface} binds a duplicate tool name"
