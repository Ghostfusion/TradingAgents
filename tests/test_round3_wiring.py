"""Round-3 wiring: gates, tool binding, screener columns, tool rows.

The phase tests cover the formulas; this file covers the *integration* contract
those formulas were landed into - the ten default-off gates, the analyst
toolset the new tool is bound through, the screener's cross-sectional columns
(including the failure mode where a name's sector median is selected from the
wrong group), and the `get_composite_rank` quality row's gate + honest degrade.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROUND3_GATES = (
    "enable_altman_variants",
    "enable_f_score_detail",
    "enable_growth_scores",
    "enable_weighted_sentiment_agg",
    "enable_crowd_ratio_bands",
    "enable_analyst_revision_index",
    "enable_quality_composite",
    "enable_score_eval_rows",
    "enable_weighted_sentiment_window",
    "enable_evidence_symmetry",
)


def _panel_fins(n: int = 10) -> dict:
    """n names with a full canonical statement set (F/M/Z/O all computable)."""
    out: dict = {}
    for i in range(n):
        k = 1.0 + 0.05 * i
        out[f"N{i}"] = {
            "revenue": {"current": 1000.0 * k, "prior": 800.0 * k},
            "net_receivables": {"current": 150.0 * k, "prior": 120.0 * k},
            "cogs": {"current": 600.0 * k, "prior": 450.0 * k},
            "cost_of_revenue": {"current": 620.0 * k, "prior": 470.0 * k},
            "sga": {"current": 120.0 * k, "prior": 100.0 * k},
            "depreciation": {"current": 60.0 * k, "prior": 50.0 * k},
            "current_assets": {"current": 700.0 * k, "prior": 650.0 * k},
            "ppem": {"current": 400.0 * k, "prior": 380.0 * k},
            "marketable_securities": {"current": 30.0 * k, "prior": 25.0 * k},
            "total_assets": {"current": 2000.0 * k, "prior": 1800.0 * k},
            "current_liabilities": {"current": 500.0 * k, "prior": 470.0 * k},
            "total_debt": {"current": 400.0 * k, "prior": 380.0 * k},
            "working_capital": 200.0 * k,
            "retained_earnings": 800.0 * k,
            "market_cap": 3000.0 * k,
            "cash": 300.0 * k,
            "total_liabilities": 900.0 * k,
            "operating_cashflow": 130.0 * k,
            "net_income": 100.0 * k,
            "interest_expense": 10.0 * k,
            "tax_expense": 20.0 * k,
            "operating_income": 90.0 * k,
            "inventory": {"current": 80.0 * k, "prior": 70.0 * k},
            "long_term_debt": {"current": 200.0 * k, "prior": 190.0 * k},
            "shares_outstanding": 100.0,
            "capex": 40.0 * k,
        }
    return out


def test_every_round3_gate_exists_and_defaults_off() -> None:
    from tradingagents.default_config import DEFAULT_CONFIG

    missing = [k for k in ROUND3_GATES if k not in DEFAULT_CONFIG]
    assert missing == []
    assert [k for k in ROUND3_GATES if DEFAULT_CONFIG[k] is not False] == []


def test_revision_tool_is_bound_to_the_fundamentals_analyst() -> None:
    from tradingagents.agents.toolsets import analyst_toolset

    names = {t.name for t in analyst_toolset("fundamentals")}
    assert "get_analyst_revision_index" in names


def test_revision_tool_joins_the_deterministic_gather_pool() -> None:
    """Context-only args: it must not widen the model-discretionary pool."""
    from tradingagents.agents.toolsets import analyst_toolset
    from tradingagents.agents.utils.evidence_gather import classify_tool_pools

    gather, model = classify_tool_pools(analyst_toolset("fundamentals"))
    assert "get_analyst_revision_index" in gather
    assert "get_analyst_revision_index" not in model


def _screener():
    root = str(Path(__file__).resolve().parents[1] / "scripts")
    if root not in sys.path:
        sys.path.insert(0, root)
    import value_screener

    return value_screener


def test_watchlist_renders_the_round3_columns_and_their_legend() -> None:
    vs = _screener()
    rows = [
        {"ticker": "AAA", "g_disp": "6/8 good", "c_disp": "1/6 good", "qual_disp": "88 elite"},
        {"ticker": "BBB", "rev_index": 1.5},
    ]
    md = vs._watchlist_markdown(rows)
    header = next(line for line in md.splitlines() if line.startswith("| Rank"))
    for col in ("| G |", "| C |", "| Qual |", "| RevIdx |"):
        assert col in header, col
    aaa = next(line for line in md.splitlines() if line.startswith("| 1 |"))
    assert "6/8 good" in aaa and "1/6 good" in aaa and "88 elite" in aaa
    bbb = next(line for line in md.splitlines() if line.startswith("| 2 |"))
    assert bbb.count("n/a") >= 3  # uncomputed cross-sectional columns
    assert "**RevIdx**" in md and "**Qual**" in md


def test_sector_medians_are_selected_from_the_names_own_group() -> None:
    """A median from another sector would make the G-Score a cross-sector claim."""
    from tradingagents.strategies.peer_universe import (
        resolve_growth_medians,
        sector_medians_for,
    )

    fins = _panel_fins(5)
    fins.update({f"U{i}": dict(_panel_fins(1)["N0"], net_income=-100.0) for i in range(5)})
    sectors = dict.fromkeys(fins, "TECH")
    sectors.update(dict.fromkeys([f"U{i}" for i in range(5)], "UTIL"))
    medians = resolve_growth_medians(fins, sectors, min_n=5)
    tech = sector_medians_for(medians, "TECH")
    util = sector_medians_for(medians, "UTIL")
    assert tech["roa"] and util["roa"]
    assert tech["roa"]["median"] > util["roa"]["median"]
    unknown = sector_medians_for(medians, "NOPE")
    assert unknown and all(v is None for v in unknown.values())
    assert "min_n=5" in medians["basis"]


def test_composite_rank_quality_row_degrades_below_the_peer_floor(monkeypatch) -> None:
    from tradingagents.agents.utils.analysis_tools import _quality_composite_row

    monkeypatch.setattr(
        "tradingagents.strategies.peer_universe.resolve_peer_universe",
        lambda **_kw: {"metrics": {}, "sectors": {}, "tickers": [], "n": 0, "dropped": {}},
    )
    row = _quality_composite_row("AAA", ["AAA", "BBB"], "2026-09-13")
    assert "unavailable" in row and "floor" in row


def test_composite_rank_quality_row_renders_score_band_and_coverage(monkeypatch) -> None:
    from tradingagents.agents.utils.analysis_tools import _quality_composite_row
    from tradingagents.strategies.peer_universe import _panel_from_fin

    fins = _panel_fins()
    panel = {
        "metrics": {t: _panel_from_fin(t, fin) for t, fin in fins.items()},
        "sectors": dict.fromkeys(fins, "TECH"),
        "tickers": sorted(fins),
        "n": len(fins),
        "dropped": {},
    }
    monkeypatch.setattr(
        "tradingagents.strategies.peer_universe.resolve_peer_universe", lambda **_kw: panel
    )
    row = _quality_composite_row("N9", list(fins), "2026-09-13")
    assert "quality composite N9:" in row
    assert "/100 (" in row
    assert "coverage" in row and "peers scored" in row
    assert "winsorised" in row


def test_quality_directions_cover_every_resolver_metric() -> None:
    """The tool path and the screener path must score the same metric set."""
    from tradingagents.strategies.factors import QUALITY_DIRECTIONS
    from tradingagents.strategies.peer_universe import _panel_from_fin

    keys = set(_panel_from_fin("X", _panel_fins(1)["N0"]))
    assert keys, "the panel must carry metrics for a full canonical fin"
    assert keys <= set(QUALITY_DIRECTIONS)


def test_composite_rank_gate_controls_the_quality_line(monkeypatch) -> None:
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.strategies.peer_universe import _panel_from_fin

    closes = [100.0 + 0.5 * i for i in range(300)]
    monkeypatch.setattr(at, "_ohlcv", lambda t: {"closes": closes})
    monkeypatch.setattr(
        "tradingagents.dataflows.finnhub.get_company_peers_finnhub", lambda t: ["BBB"]
    )
    monkeypatch.setattr(at, "_r3_flag", lambda name, default=False: False)
    off = at.get_composite_rank.invoke({"ticker": "AAA"})
    assert "composite rank AAA" in off
    assert "quality composite" not in off

    fins = {"AAA": _panel_fins(1)["N0"], "BBB": _panel_fins(1)["N0"]}
    panel = {
        "metrics": {t: _panel_from_fin(t, fin) for t, fin in fins.items()},
        "sectors": dict.fromkeys(fins, "TECH"),
        "tickers": sorted(fins),
        "n": len(fins),
        "dropped": {},
    }
    monkeypatch.setattr(
        "tradingagents.strategies.peer_universe.resolve_peer_universe", lambda **_kw: panel
    )
    monkeypatch.setattr(at, "_r3_flag", lambda name, default=False: True)
    on = at.get_composite_rank.invoke({"ticker": "AAA"})
    assert "quality composite" in on


@pytest.mark.parametrize("flag", ROUND3_GATES)
def test_gate_reads_never_raise(flag: str) -> None:
    from tradingagents.agents.utils.analysis_tools import _r3_flag

    assert _r3_flag(flag) in (True, False)
