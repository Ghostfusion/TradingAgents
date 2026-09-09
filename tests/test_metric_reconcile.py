"""Tests for gather-time metric reconciliation (strategies/metric_reconcile.py).

Pure: no IO/LLM. The TJX 2026-09-08 fundamentals report quoted the same
metric at conflicting values from different vendors; this module detects the
conflict at ingest so the evidence block flags it before the analyst reduces.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.metric_reconcile import (
    extract_de_value,
    extract_value,
    metric_for_tool,
    reconcile_metrics,
    render_reconcile,
)


@pytest.mark.timeout(30)
class TestMetricReconcile:
    def test_extract_de_value_shapes(self):
        assert extract_de_value("Debt to Equity: 5.62") == 5.62
        assert extract_de_value("D/E: 0.06") == 0.06
        assert extract_de_value("d_e=0.0552") == 0.0552
        assert extract_de_value("Total Debt 100") is None  # no D/E label
        assert extract_de_value("") is None

    def test_reconcile_flags_de_conflict(self):
        """ARM 2026-09-09 loop: get_fundamentals raw D/E 5.62 vs get_ratios
        computed 0.06 vs balance-sheet d_e 0.055 must surface as a
        debt_to_equity conflict, not be hidden by first-number extraction."""
        leaves = [
            {"tool": "get_fundamentals", "content": "Debt to Equity: 5.62"},
            {"tool": "get_ratios", "content": "D/E: 0.06"},
            {"tool": "get_balance_sheet_health", "content": "d_e=0.0552"},
        ]
        r = reconcile_metrics(leaves)
        de = r.get("debt_to_equity")
        assert de is not None
        assert de["conflict"] is True
        assert de["span"][0] >= 0.0552 and de["span"][1] <= 5.62
        text = render_reconcile(r)
        assert "debt_to_equity" in text
        assert "VALUES CONFLICT" in text

    def test_metric_for_tool_maps(self):
        assert metric_for_tool("get_dcf_valuation") == "dcf"
        assert metric_for_tool("get_ratios") == "market_cap"
        assert metric_for_tool("get_nonexistent") is None
        assert metric_for_tool("") is None

    def test_extract_value_formats(self):
        assert extract_value("$80.60") == 80.6
        assert extract_value("market cap 1,234,567") == 1234567.0
        assert extract_value("12.3%") == 12.3
        assert extract_value("") is None
        assert extract_value("no numbers here") is None

    def test_reconcile_no_conflict_when_consistent(self):
        leaves = [
            {"tool": "get_fundamentals", "content": "Market Cap: 141.8B"},
            {"tool": "get_ratios", "content": "- Market cap: 141.8B"},
        ]
        r = reconcile_metrics(leaves)
        assert not r["market_cap"]["conflict"]
        assert r["market_cap"]["span"] == (141.8, 141.8)

    def test_reconcile_conflict_different_values(self):
        leaves = [
            {"tool": "get_fundamentals", "content": "Market Cap: 141.8B"},
            {"tool": "get_ratios", "content": "- Market cap: 145.3B"},
        ]
        r = reconcile_metrics(leaves)
        assert r["market_cap"]["conflict"] is True
        assert r["market_cap"]["span"] == (141.8, 145.3)
        assert r["market_cap"]["vendors"] == ["get_fundamentals", "get_ratios"]

    def test_reconcile_unknown_tool_ignored(self):
        leaves = [{"tool": "get_nonexistent", "content": "Market Cap: 1.0"}]
        assert reconcile_metrics(leaves) == {}

    def test_reconcile_unparseable_value_keeps_vendor(self):
        # A vendor that returned no usable value must not hide a conflict
        # between two others (it still counts as a vendor, no value).
        leaves = [
            {"tool": "get_fundamentals", "content": "Market Cap: 141.8B"},
            {"tool": "get_ratios", "content": "unavailable"},
            {"tool": "get_basic_financials", "content": "marketCapitalization: 145.3B"},
        ]
        r = reconcile_metrics(leaves)
        assert r["market_cap"]["conflict"] is True
        assert r["market_cap"]["vendors"] == [
            "get_basic_financials",
            "get_fundamentals",
            "get_ratios",
        ]

    def test_render_reconcile_only_conflicts(self):
        leaves = [
            {"tool": "get_fundamentals", "content": "Market Cap: 141.8B"},
            {"tool": "get_ratios", "content": "- Market cap: 145.3B"},
        ]
        text = render_reconcile(reconcile_metrics(leaves))
        assert "VALUES CONFLICT" in text
        assert "range=141.8 .. 145.3" in text
        assert "do NOT quote a single value" in text

    def test_render_reconcile_consistent_silent(self):
        leaves = [{"tool": "get_fundamentals", "content": "Market Cap: 141.8B"}]
        assert render_reconcile(reconcile_metrics(leaves)) == ""
