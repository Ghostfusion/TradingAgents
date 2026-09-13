"""Tests for gather-time metric reconciliation (strategies/metric_reconcile.py).

Pure: no IO/LLM. The TJX 2026-09-08 fundamentals report quoted the same
metric at conflicting values from different vendors; this module detects the
conflict at ingest so the evidence block flags it before the analyst reduces.

Values are read from the line that NAMES the metric, so the QQQI 2026-09-13
ETF run (leaves carrying no market cap at all) no longer produces the phantom
"market_cap: VALUES CONFLICT range=10 .. 2026".
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.metric_reconcile import (
    extract_de_value,
    extract_metric_value,
    metric_for_tool,
    reconcile_metrics,
    render_reconcile,
)

# Verbatim heads of the QQQI 2026-09-13 leaves (tool_evidence.json): the
# leaf set carries NO market-cap figure anywhere, but it does carry a note date
# (2026) and a "10DayAverageTradingVolume" label - the first-number extractor
# read those as one and rendered "range=10 .. 2026", which the report then
# quoted as its AUM evidence.
_QQQI_FUNDAMENTALS = (
    "# Company Fundamentals for QQQI\n"
    "# Data retrieved on: 2026-09-13 12:26:56\n\n"
    "Name: NEOS NASDAQ-100(R) High Income ETF\n"
    "PE Ratio (TTM): 29.235441\n"
    "Dividend Yield: 9.00%\n"
    "52 Week High: 57.84\n"
)
_QQQI_BASIC = (
    "Basic Financials — QQQI (Finnhub)\n"
    "Sector: \n"
    "10DayAverageTradingVolume (vendor, basis unknown): 3.32287\n"
    "beta (vendor, basis unknown): 0.95023936\n"
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

    def test_extract_metric_value_is_label_anchored(self):
        assert extract_metric_value("get_fundamentals", "Market Cap: 99,105,693,696") == 99105693696.0
        assert extract_metric_value("get_ratios", "- Market cap: 102,260,850,000") == 102260850000.0
        assert (
            extract_metric_value("get_basic_financials", "marketCapitalization: 3659011800000.0")
            == 3659011800000.0
        )
        assert (
            extract_metric_value("get_dcf_valuation", "dcf adbe: fair_value=278.71 ev=112274906766.12")
            == 278.71
        )
        assert extract_metric_value("get_market_snapshot", "- Last: 250.27 | O 251.81 H 255") == 250.27
        assert extract_metric_value("get_verified_market_snapshot", "| Close | 248.81 |") == 248.81
        # an unlabelled number in the leaf is never used
        assert extract_metric_value("get_fundamentals", _QQQI_FUNDAMENTALS) is None
        assert extract_metric_value("get_basic_financials", _QQQI_BASIC) is None
        assert extract_metric_value("get_ratios", "- Div yield: n/a") is None
        # tools with no scalar label contract contribute nothing
        assert extract_metric_value("get_balance_sheet", "Total Debt,100") is None
        assert extract_metric_value("get_nonexistent", "Market Cap: 1") is None
        assert extract_metric_value("get_fundamentals", "") is None

    def test_reconcile_etf_market_cap_is_not_a_conflict(self):
        """QQQI 2026-09-13 regression: two leaves that carry no market cap must
        not manufacture a market_cap range (the run quoted "range=10 .. 2026"
        as its AUM evidence). The metric is reported as absent instead."""
        leaves = [
            {"tool": "get_fundamentals", "content": _QQQI_FUNDAMENTALS},
            {"tool": "get_basic_financials", "content": _QQQI_BASIC},
        ]
        r = reconcile_metrics(leaves)
        assert r["market_cap"]["conflict"] is False
        assert r["market_cap"]["values"] == []
        text = render_reconcile(r)
        assert "VALUES CONFLICT" not in text
        assert "NO VALUE IN EVIDENCE" in text

    def test_reconcile_market_snapshot_date_is_not_a_price(self):
        """The same defect hit price reconciliation (MU 2026-09-09 quoted
        "range=1028 .. 2026"): a note date must never become a snapshot price."""
        leaves = [
            {
                "tool": "get_market_snapshot",
                "content": "## MU Market Snapshot (EODHD)\n\n- Last: 1027.77 | O 999.35 H 1042.4\n",
            },
            {
                "tool": "get_verified_market_snapshot",
                "content": (
                    "## Verified market data snapshot for MU\n\n"
                    "- Requested analysis date: 2026-09-09\n\n"
                    "| Field | Value |\n|---|---:|\n| Close | 1027.77 |\n"
                ),
            },
        ]
        r = reconcile_metrics(leaves)
        assert r["market_snapshot"]["conflict"] is False
        assert r["market_snapshot"]["values"] == [1027.77, 1027.77]

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

    def test_render_reconcile_single_vendor_without_value_silent(self):
        # Nothing to reconcile with one vendor: its leaf already reports
        # unavailability, so the block stays quiet instead of adding noise.
        leaves = [{"tool": "get_dcf_valuation", "content": "dcf unavailable for X"}]
        assert render_reconcile(reconcile_metrics(leaves)) == ""
