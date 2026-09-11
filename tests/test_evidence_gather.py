"""Hermetic tests for the forced-tool evidence gatherer (map side).

The gatherer must be deterministic in *composition* (which tools ran, in
request order), never registered on a failing/slow tool, and mark ``timeout``
without blocking the caller. These tests use no network, no live tools.
Also covers the short-circuit wrapper (already-gathered tools never re-invoke
the vendor on the analyst's gap-fill loop).
"""

from __future__ import annotations

import threading

from langchain_core.tools import tool

from tradingagents.agents.utils.evidence_gather import (
    MODEL_POOL_HEADER,
    MODEL_POOL_KEY,
    TOOL_EVIDENCE_KEY,
    format_evidence_block,
    gather_evidence,
    gather_for_analyst_node,
    make_short_circuit_tool_node,
    parse_forced_spec,
)


@tool
def get_financials(ticker: str, current_date: str | None = None) -> str:
    """Fake fundamentals surface."""
    return f"fin:{ticker}:{current_date or 'none'}"


@tool
def get_pe_metrics(ticker: str) -> str:
    """Fake valuation metrics."""
    return f"pem:{ticker}"


@tool
def get_boom() -> str:
    """Fake tool that always fails."""

    raise RuntimeError("vendor exploded")


@tool
def get_empty() -> str:
    """Fake tool returning a no-data sentinel."""

    return "unavailable"


@tool
def get_slow() -> str:
    """Fake hung tool (blocks a bit)."""

    from time import sleep

    sleep(0.4)
    return "eventually"


def _tools() -> dict:
    return {
        get_financials.name: get_financials,
        get_pe_metrics.name: get_pe_metrics,
        get_boom.name: get_boom,
        get_empty.name: get_empty,
        get_slow.name: get_slow,
    }


def test_evidence_key_is_tool_evidence():
    assert TOOL_EVIDENCE_KEY == "tool_evidence"


def test_parse_comma_list_dedup_order():
    names = ["get_b", "get_a", "get_c"]
    assert parse_forced_spec(" get_a , get_b , get_a ", names) == ["get_a", "get_b"]


def test_parse_empty_spec():
    assert parse_forced_spec("", ["get_a"]) == []
    assert parse_forced_spec(None, ["get_a"]) == []
    assert parse_forced_spec([], ["get_a"]) == []


def test_parse_unknown_skipped():
    out = parse_forced_spec("get_a,get_z", ["get_a"])
    assert out == ["get_a"]


def test_parse_all_expands_in_registration_order():
    names = ["get_b", "get_a"]
    assert parse_forced_spec("ALL", names) == ["get_b", "get_a"]


def test_gather_ok_ordered_and_args_filtered():
    leaves = gather_evidence(
        _tools(),
        ["get_financials", "get_pe_metrics"],
        context={"ticker": "TSM", "current_date": "2026-09-07"},
    )
    assert [leaf.tool for leaf in leaves] == ["get_financials", "get_pe_metrics"]
    fin = leaves[0]
    assert fin.status == "ok"
    assert "fin:TSM:2026-09-07" in fin.content
    # Only declared schema args are passed - the tool's own default stays.
    assert fin.args == {"ticker": "TSM", "current_date": "2026-09-07"}
    assert len(fin.args_hash) == 12


def test_gather_failure_leaf_never_raises():
    leaves = gather_evidence(_tools(), ["get_boom"], timeout_s=5)
    assert len(leaves) == 1
    leaf = leaves[0]
    assert leaf.status == "error"
    assert "raised RuntimeError" in leaf.content


def test_gather_no_data_sentinel():
    leaves = gather_evidence(_tools(), ["get_empty"], timeout_s=5)
    assert leaves[0].status == "no_data"


def test_gather_timeout_marks_timeout_not_a_late_result():
    """A tool still running at the deadline is recorded as ``timeout``; its late
    result must never be served as if it finished in time.

    Uses an event-blocked fake (not a sleep) so the verdict does not depend on
    wall-clock elapsed bounds, which flake on a loaded box.
    """
    release = threading.Event()

    @tool
    def get_blocked() -> str:
        """Fake tool that outlives the gather deadline."""
        release.wait(timeout=10)
        return "late"

    try:
        leaves = gather_evidence(
            {get_blocked.name: get_blocked}, ["get_blocked"], timeout_s=0.05
        )
    finally:
        release.set()  # let the daemon drain thread exit

    assert len(leaves) == 1
    assert leaves[0].status == "timeout"
    assert "timed out after 0.05s" in leaves[0].content


def test_gather_missing_resolver_name_is_skipped():
    leaves = gather_evidence(_tools(), ["get_nope"], timeout_s=5)
    assert leaves == []


def test_gather_max_parallel_returns_all_timeouts_in_spec_order():
    """All three requested names come back as ``timeout`` leaves in request
    order when they outlive the deadline (deterministic composition)."""
    reg = {
        "get_slow": get_slow,
        "get_slow2": get_slow,
        "get_slow3": get_slow,
    }
    leaves = gather_evidence(
        reg, ["get_slow", "get_slow2", "get_slow3"], timeout_s=0.05, max_parallel=3
    )
    assert [leaf.tool for leaf in leaves] == ["get_slow", "get_slow2", "get_slow3"]
    assert all(leaf.status == "timeout" for leaf in leaves)


def test_args_hash_deterministic():
    a = gather_evidence(
        _tools(), ["get_financials"], context={"ticker": "TSM", "current_date": "x"}
    )[0].args_hash
    b = gather_evidence(
        _tools(), ["get_financials"], context={"ticker": "TSM", "current_date": "x"}
    )[0].args_hash
    assert a == b


def test_format_block_renders_headers_and_failures():
    leaves = gather_evidence(
        _tools(),
        ["get_financials", "get_boom", "get_empty", "get_slow"],
        context={"ticker": "TSM"},
        timeout_s=0.05,
    )
    block = format_evidence_block(leaves)
    assert "## Tool Evidence (deterministic - all invoked)" in block
    assert "### get_financials [ok]" in block
    assert "### get_boom [error]" in block
    assert "unavailable" in block
    assert "### get_slow [timeout]" in block
    assert "### get_empty [no_data]" in block


def test_format_block_empty():
    assert format_evidence_block([]) == ""


def _ai_tool_calls(*calls):
    """Build a bare state whose last message carries the given tool calls."""
    from langchain_core.messages import AIMessage

    return {"messages": [AIMessage(content="", tool_calls=list(calls))]}


def _fake_tool_node(real_tool, calls):
    """Fake langgraph ToolNode callable; records invocations it performed."""
    from langchain_core.messages import ToolMessage

    def node(state):
        calls["n"] += 1
        msgs = list(state["messages"])
        last = msgs[-1]
        out = []
        for c in (getattr(last, "tool_calls", None) or []):
            name = c.get("name", "")
            args = c.get("args", {})
            content = (
                real_tool.invoke(dict(args))
                if name == real_tool.name
                else f"ran:{name}"
            )
            out.append(
                ToolMessage(content=content, tool_call_id=c.get("id", ""), name=name)
            )
        return {"messages": out}

    return node


def test_short_circuit_gathered_tool_not_reinvoked():
    calls = {"n": 0}
    wrapped = make_short_circuit_tool_node(_fake_tool_node(get_financials, calls), "fundamentals")
    out = wrapped(
        {
            TOOL_EVIDENCE_KEY: {
                "fundamentals": [
                    {"tool": "get_financials", "status": "ok", "content": "data", "args_hash": "x"}
                ]
            },
            **_ai_tool_calls({"name": "get_financials", "args": {"ticker": "TSM"}, "id": "c1"}),
        }
    )
    assert calls["n"] == 0  # underlying ToolNode never ran
    msg = out["messages"][0]
    assert msg.tool_call_id == "c1"
    assert msg.name == "get_financials"
    assert "already gathered" in msg.content


def test_short_circuit_delegates_ungathered_tool():
    calls = {"n": 0}
    wrapped = make_short_circuit_tool_node(_fake_tool_node(get_financials, calls), "market")
    out = wrapped(
        {
            TOOL_EVIDENCE_KEY: {
                "market": [
                    {"tool": "get_pe_metrics", "status": "ok", "args": {}, "args_hash": "y"}
                ]
            },
            **_ai_tool_calls(
                {"name": "get_pe_metrics", "args": {"ticker": "TSM"}, "id": "c1"},
                {"name": "get_financials", "args": {"ticker": "TSM"}, "id": "c2"},
            ),
        }
    )
    assert calls["n"] == 1  # c2 ran through the underlying node
    by_id = {m.tool_call_id: m for m in out["messages"]}
    assert "already gathered" in by_id["c1"].content
    assert by_id["c2"].content == get_financials.invoke({"ticker": "TSM"})


def test_short_circuit_passthrough_without_evidence():
    calls = {"n": 0}
    wrapped = make_short_circuit_tool_node(_fake_tool_node(get_financials, calls), "fundamentals")
    out = wrapped(
        {
            TOOL_EVIDENCE_KEY: {},
            **_ai_tool_calls({"name": "get_financials", "args": {"ticker": "TSM"}, "id": "c1"}),
        }
    )
    assert calls["n"] == 1  # legacy path: underlying node ran unchanged
    assert out["messages"][0].tool_call_id == "c1"


def test_evidence_context_includes_window_keys():
    """Window tools get real rolling dates (symbol/start/end/look_back_days)."""
    from tradingagents.agents.utils.evidence_gather import _evidence_context

    ctx = _evidence_context(
        {"company_of_interest": "TSM", "trade_date": "2026-09-07"}
    )
    assert ctx["symbol"] == "TSM"
    assert ctx["end_date"] == "2026-09-07"
    assert ctx["start_date"] == "2026-08-09"
    assert ctx["look_back_days"] == 30
    assert ctx["ticker"] == "TSM"
    assert ctx["current_date"] == "2026-09-07"
    assert ctx["curr_date"] == "2026-09-07"


def test_evidence_context_omits_window_keys_on_bad_date():
    """An unparseable trade date drops the window keys (tools keep defaults)."""
    from tradingagents.agents.utils.evidence_gather import _evidence_context

    ctx = _evidence_context({"company_of_interest": "TSM", "trade_date": "not-a-date"})
    assert "start_date" not in ctx
    assert "end_date" not in ctx
    assert "look_back_days" not in ctx
    assert ctx["ticker"] == "TSM"


def test_gather_passes_window_args_to_declared_tools():
    """A tool declaring symbol/start/end receives them; undected keys are ignored."""
    from tradingagents.agents.utils.evidence_gather import gather_for_analyst_node

    seen = {}

    @tool
    def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
        """Fake OHLCV surface (declares only the window keys)."""
        seen.update(symbol=symbol, start_date=start_date, end_date=end_date)
        return f"ohlcv {symbol} {start_date}..{end_date}"

    # Simulate the analyst node's bound tools list with the fake tool.
    node_state = {
        "company_of_interest": "TSM",
        "trade_date": "2026-09-07",
        "instrument_context": "",
        "messages": [],
    }
    # gather_for_analyst_node reads config analyst_forced_tools from config arg
    cfg = {
        "analyst_forced_tools": ["get_stock_data"],
        "analyst_forced_tools_timeout_s": 5,
        "analyst_forced_tools_max_parallel": 1,
        "analyst_forced_tools_summary_window": 12000,
    }
    block, evidence = gather_for_analyst_node(
        {**node_state, "tool_evidence": {}}, "market", [get_stock_data], cfg
    )
    assert seen.get("symbol") == "TSM"
    assert seen.get("start_date") == "2026-08-09"
    assert seen.get("end_date") == "2026-09-07"
    assert block != ""
    assert "ohlcv" in block


@tool
def get_bsm_quote_fake(spot: float, strike: float, t_years: float, vol: float) -> str:
    """Fake options-quote tool: all args are model-supplied (not in context)."""
    return "fake bsm"


def test_classify_splits_model_pool_by_required_args():
    """A tool with a required arg the context can't supply -> model pool."""
    from tradingagents.agents.utils.evidence_gather import classify_tool_pools

    gather, model = classify_tool_pools([get_financials, get_bsm_quote_fake])
    assert "get_financials" in gather
    assert "get_bsm_quote_fake" in model


def test_all_gathers_only_gather_pool(caplog):
    """ALL force-gathers the auto pool; model-pool tools are never attempted."""
    cfg = {
        "analyst_forced_tools": ["ALL"],
        "analyst_forced_tools_timeout_s": 5,
        "analyst_forced_tools_max_parallel": 1,
        "analyst_forced_tools_summary_window": 12000,
    }
    block, evidence = gather_for_analyst_node(
        {"company_of_interest": "TSM", "trade_date": "2026-09-07", "messages": [], "tool_evidence": {}},
        "market",
        [get_financials, get_bsm_quote_fake],
        cfg,
    )
    # Only the auto tool gathered; the model-pool tool is listed, not attempted.
    assert [leaf["tool"] for leaf in evidence["market"]] == ["get_financials"]
    assert evidence[MODEL_POOL_KEY]["market"] == ["get_bsm_quote_fake"]
    assert "get_financials" in block
    assert MODEL_POOL_HEADER in block
    assert "get_bsm_quote_fake" in block


def test_explicit_model_name_skipped_with_warning(caplog):
    """A forced name in the model pool is skipped (never error-attempted)."""
    from tradingagents.agents.utils.evidence_gather import gather_for_analyst_node

    cfg = {
        "analyst_forced_tools": ["get_bsm_quote_fake", "get_financials"],
        "analyst_forced_tools_timeout_s": 5,
        "analyst_forced_tools_max_parallel": 1,
        "analyst_forced_tools_summary_window": 12000,
    }
    block, evidence = gather_for_analyst_node(
        {"company_of_interest": "TSM", "trade_date": "2026-09-07", "messages": [], "tool_evidence": {}},
        "market",
        [get_financials, get_bsm_quote_fake],
        cfg,
    )
    assert [leaf["tool"] for leaf in evidence["market"]] == ["get_financials"]
    assert any("model pool" in r.getMessage() for r in caplog.records)


def test_model_supplied_override_moves_gather_tool_into_model():
    """analyst_tools_model_supplied escape hatch FORCE-moves a name to model pool."""
    from tradingagents.agents.utils.evidence_gather import (
        MODEL_POOL_KEY,
        gather_for_analyst_node,
    )

    cfg = {
        "analyst_forced_tools": ["ALL"],
        "analyst_tools_model_supplied": ["get_financials"],
        "analyst_forced_tools_timeout_s": 5,
        "analyst_forced_tools_max_parallel": 1,
        "analyst_forced_tools_summary_window": 12000,
    }
    _, evidence = gather_for_analyst_node(
        {"company_of_interest": "TSM", "trade_date": "2026-09-07", "messages": [], "tool_evidence": {}},
        "market",
        [get_financials, get_bsm_quote_fake],
        cfg,
    )
    assert evidence[MODEL_POOL_KEY]["market"] == ["get_bsm_quote_fake", "get_financials"]


def test_short_circuit_passes_through_model_pool_calls():
    """A model-pool call executes for real (not short-circuited)."""
    calls = {"n": 0}
    fake_node = _fake_tool_node(get_financials, calls)
    wrapped = make_short_circuit_tool_node(fake_node, "market")
    out = wrapped(
        {
            TOOL_EVIDENCE_KEY: {
                "market": [{"tool": "get_financials", "status": "ok", "args": {}, "args_hash": "x"}],
                MODEL_POOL_KEY: {"market": ["get_bsm_quote_fake"]},
            },
            **_ai_tool_calls({"name": "get_bsm_quote_fake", "args": {}, "id": "c-m"}),
        }
    )
    assert calls["n"] == 1  # model-pool call reached the underlying ToolNode
    assert out["messages"][0].tool_call_id == "c-m"
    # Its result is journaled as an evidence leaf so report verification can
    # see what the analyst actually received (macro/prediction gap on JPM/GS
    # 2026-09-08 was unverifiable because model-pool results were transcript-only).
    leaves = out.get("tool_evidence", {}).get("market")
    assert leaves and any(leaf["tool"] == "get_financials" for leaf in leaves)


# --------------------------------------------------------------------------
# Per-analyst tool-call log (which of the model-pool tools the LLM invoked)
# --------------------------------------------------------------------------


def test_tool_call_log_records_short_and_executed(monkeypatch):
    """Regression (QCOM 2026-09-07): nothing persisted which model-pool tools
    the LLM actually called. The short-circuit wrapper must log every model
    tool call per analyst (executed + short_circuit) with pool classification."""
    from tradingagents.agents.utils import tool_call_log as TCL

    recorded: list = []
    monkeypatch.setattr(
        TCL,
        "log_tool_call",
        lambda *a, **k: recorded.append({"analyst": a[0], "tool": a[1], "event": a[2], **k}),
    )
    calls = {"n": 0}
    wrapped = make_short_circuit_tool_node(_fake_tool_node(get_financials, calls), "market")
    wrapped(
        {
            TOOL_EVIDENCE_KEY: {
                "market": [{"tool": "get_financials", "status": "ok", "args": {}, "args_hash": "x"}],
                MODEL_POOL_KEY: {"market": ["get_bsm_quote_fake", "get_pe_metrics"]},
            },
            "company_of_interest": "TSM",
            "trade_date": "2026-09-07",
            **_ai_tool_calls(
                {"name": "get_financials", "args": {"ticker": "TSM"}, "id": "c-g"},     # gathered -> short_circuit
                {"name": "get_bsm_quote_fake", "args": {}, "id": "c-p"},                # model pool -> executed
                {"name": "get_boom", "args": {}, "id": "c-x"},                        # not pooled, not gathered -> executed
            ),
        }
    )
    # Underlying node ran the two non-short-circuited calls.
    assert calls["n"] == 1
    # Two log lines: short_circuit for get_financials, executed for the pool + boom.
    by_tool = {r["tool"]: r for r in recorded}
    assert set(by_tool) == {"get_financials", "get_bsm_quote_fake", "get_boom"}
    assert by_tool["get_financials"]["event"] == "short_circuit"
    assert by_tool["get_financials"]["in_model_pool"] is False
    assert by_tool["get_bsm_quote_fake"]["event"] == "executed"
    assert by_tool["get_bsm_quote_fake"]["in_model_pool"] is True
    assert by_tool["get_boom"]["event"] == "executed"
    assert by_tool["get_boom"]["in_model_pool"] is False
    assert all(r["analyst"] == "market" for r in recorded)
    assert all((r.get("state") or {}).get("company_of_interest") == "TSM" for r in recorded)


def test_tool_call_log_dir_resolution(monkeypatch):
    from pathlib import Path

    from tradingagents.agents.utils import tool_call_log as _log

    # Default = <data_cache_dir>/tool_calls
    assert _log._log_dir({"data_cache_dir": "C:/cache", "tool_call_log_dir": ""}) \
        == Path("C:/cache") / "tool_calls"
    # Explicit override wins
    assert _log._log_dir({"data_cache_dir": "C:/cache", "tool_call_log_dir": "D:/logs/tc"}) \
        == Path("D:/logs/tc")
    # No cache dir and no override -> None (no write)
    assert _log._log_dir({}) is None
