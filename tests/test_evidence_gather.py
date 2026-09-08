"""Hermetic tests for the forced-tool evidence gatherer (map side).

The gatherer must be deterministic in *composition* (which tools ran, in
spec order), never raise on a failing/slow tool, and mark ``timeout``
without blocking the caller. These tests use no network, no real tools.
"""

from __future__ import annotations

from time import monotonic

from langchain_core.tools import tool

from tradingagents.agents.utils.evidence_gather import (
    TOOL_EVIDENCE_KEY,
    format_evidence_block,
    gather_evidence,
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


def test_gather_timeout_returns_quickly_and_marks_timeout():
    start = monotonic()
    leaves = gather_evidence(_tools(), ["get_slow"], timeout_s=0.05)
    elapsed = monotonic() - start
    assert elapsed < 0.3  # far below the 0.4s fake hang
    assert leaves[0].status == "timeout"
    assert "timed out after" in leaves[0].content


def test_gather_missing_resolver_name_is_skipped():
    leaves = gather_evidence(_tools(), ["get_nope"], timeout_s=5)
    assert leaves == []


def test_gather_max_parallel_runs_concurrently():
    reg = {
        "get_slow": get_slow,
        "get_slow2": get_slow,
        "get_slow3": get_slow,
    }
    start = monotonic()
    leaves = gather_evidence(reg, ["get_slow", "get_slow2", "get_slow3"], timeout_s=0.2)
    elapsed = monotonic() - start
    # Three 0.4s sleeps in parallel at max_parallel=3 => well under 1.2s
    # sequential; the join caps at timeout 0.2 so this runs ~0.2s.
    assert elapsed < 0.9
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
