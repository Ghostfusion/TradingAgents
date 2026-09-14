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
            "net_income": {"current": 100.0 * k, "prior": 95.0 * k},
            "interest_expense": 10.0 * k,
            "tax_expense": 20.0 * k,
            "operating_income": 90.0 * k,
            "inventory": {"current": 80.0 * k, "prior": 70.0 * k},
            "long_term_debt": {"current": 200.0 * k, "prior": 190.0 * k},
            "shares_outstanding": 100.0,
            "shares_issued": 0.0,
            "capex": 40.0 * k,
        }
    return out


def test_every_round3_gate_exists() -> None:
    from tradingagents.default_config import DEFAULT_CONFIG

    assert [k for k in ROUND3_GATES if k not in DEFAULT_CONFIG] == []


def test_shipped_gate_defaults_are_off() -> None:
    """The SHIPPED default is off.

    Deliberately NOT asserted on the in-process DEFAULT_CONFIG: that dict is
    built from the operator's .env, so a dark launch - the whole point of these
    gates - would fail the test. A clean interpreter whose cwd has no .env sees
    only the code's literal defaults.
    """
    import os
    import subprocess
    import sys
    import tempfile

    repo = str(Path(__file__).resolve().parents[1])
    env = {k: v for k, v in os.environ.items() if not k.startswith("TRADINGAGENTS_")}
    env["PYTHONPATH"] = repo
    code = (
        "from tradingagents.default_config import DEFAULT_CONFIG as D;"
        f"print([g for g in {ROUND3_GATES!r} if D[g]])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tempfile.gettempdir(),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=True,
    )
    assert out.stdout.strip() == "[]", out.stdout + out.stderr


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


@pytest.fixture
def r3_gates():
    """Flip round-3 gates through the real thread-local config, then restore."""
    from tradingagents.dataflows.config import set_config
    from tradingagents.default_config import DEFAULT_CONFIG

    def _set(**flags):
        set_config(flags)

    yield _set
    set_config({k: DEFAULT_CONFIG[k] for k in ROUND3_GATES})


def test_screen_row_has_no_round3_keys_when_the_gates_are_off(r3_gates) -> None:
    """The consumers the plan names must not change the row until a gate flips."""
    from tradingagents.dataflows.statement_parsing import screen_ticker

    r3_gates(enable_altman_variants=False, enable_f_score_detail=False)
    row = screen_ticker("AAA", _panel_fins(1)["N0"])
    assert {"altman_zone", "altman_variant", "f_score_band"}.isdisjoint(row)
    assert row["trap"] in {"LOW", "MEDIUM", "HIGH", "n/a"}


def test_screen_row_carries_the_zone_and_band_when_the_gates_are_on(r3_gates) -> None:
    from tradingagents.dataflows.statement_parsing import screen_ticker

    fin = _panel_fins(1)["N0"]
    r3_gates(enable_altman_variants=False, enable_f_score_detail=False)
    off = screen_ticker("AAA", fin)
    r3_gates(enable_altman_variants=True, enable_f_score_detail=True)
    on = screen_ticker("AAA", fin)
    assert on["altman_zone"] in {"safe", "grey", "distress"}
    assert on["altman_variant"] in {"z", "z_double_prime"}
    assert on["f_score_band"] in {"high", "low", "middle"}
    assert on["trap"] == off["trap"], "the zone/band are render-only extras"
    assert on["f_score"] == off["f_score"] and on["altman_z"] == off["altman_z"]


def test_earnings_quality_renders_the_zone_and_band_when_on(r3_gates, monkeypatch) -> None:
    from tradingagents.agents.utils import analysis_tools as at

    fin = _panel_fins(1)["N0"]
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda ticker, current_date, **kw: fin,
    )
    r3_gates(enable_altman_variants=False, enable_f_score_detail=False)
    off = at.get_earnings_quality.invoke({"ticker": "AAA", "current_date": "2026-09-13"})
    assert "altman_zone=" not in off and "f_score_band=" not in off
    assert "trap_risk=" in off
    r3_gates(enable_altman_variants=True, enable_f_score_detail=True)
    on = at.get_earnings_quality.invoke({"ticker": "AAA", "current_date": "2026-09-13"})
    assert "altman_zone=" in on and "variant=" in on
    assert "f_score_band=" in on


def test_trap_cell_appends_the_zone_only_when_present() -> None:
    vs = _screener()

    assert vs._trap_cell({"trap": "LOW"}) == "LOW"
    assert vs._trap_cell({"trap": "MEDIUM", "altman_zone": "grey"}) == "MEDIUM (grey)"
    assert vs._trap_cell({}) is None


_MEDIAN_KEYS = (
    "roa", "cfo", "var_roa", "var_sales_growth", "rd_intensity", "capex_intensity", "ad_intensity"
)


def test_partial_g_score_is_never_printed_over_the_full_denominator() -> None:
    """`1/8` reads as Mohanram's G = 1; the truth was one computable signal."""
    from tradingagents.dataflows.quantitative_scores import growth_score, signal_summary

    fin = _panel_fins(1)["N0"]
    partial = growth_score(fin, None)
    assert partial["band"] is None
    head = signal_summary(partial, 8)
    assert "/8" not in head and "computed signal" in head and "not scored 0" in head

    rich = dict(
        fin,
        roa_series=[0.05, 0.06, 0.07, 0.08, 0.09],
        revenue_series=[100.0, 110.0, 120.0, 130.0, 140.0],
        research_development=8.0,
        advertising=3.0,
    )
    medians = {k: {"median": 0.001, "n": 9} for k in _MEDIAN_KEYS}
    full = growth_score(rich, medians)
    assert all(v is not None for v in full["signals"].values())
    assert signal_summary(full, 8).endswith("/8")
    assert signal_summary({"score": None, "signals": {}}, 8) == "unavailable"


def test_quality_tool_compresses_the_median_exclusions_when_no_panel_is_supplied(
    r3_gates, monkeypatch
) -> None:
    from tradingagents.agents.utils.quant_formula_tools import get_quality_factors

    fin = _panel_fins(1)["N0"]
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda ticker, current_date, **kw: fin,
    )
    r3_gates(enable_growth_scores=True)
    out = get_quality_factors.invoke({"ticker": "AAA", "current_date": "2026-09-13"})
    assert "peer-median leg(s) excluded" in out
    assert "industry median unavailable" not in out
    assert "g_score=" in out and "/8" not in out
    assert "c_score=" in out and "/6" not in out


def test_round3_gates_are_env_mappable(monkeypatch) -> None:
    """A gate an operator cannot flip from .env is not a dark-launch gate.

    `_apply_env_overrides` only reads names in `_ENV_OVERRIDES`, so an unmapped
    `TRADINGAGENTS_ENABLE_*` is silently ignored (and the .env.example block for
    this round would document ten variables that do nothing).
    """
    from tradingagents import default_config as dc

    mapped = set(dc._ENV_OVERRIDES.values())
    unmapped = sorted(set(ROUND3_GATES) - mapped)
    assert unmapped == []
    # Base config: DEFAULT_CONFIG's own types (the validator checks every mapped
    # target), with the ten gates forced off so the env var is what flips them.
    env_of = {key: env for env, key in dc._ENV_OVERRIDES.items()}
    # The operator's own dark launch lives in os.environ (a .env is loaded at
    # package import), so clear the ten names before asserting on two of them.
    for gate in ROUND3_GATES:
        monkeypatch.delenv(env_of[gate], raising=False)
    base = dict(dc.DEFAULT_CONFIG)
    base.update(dict.fromkeys(ROUND3_GATES, False))
    monkeypatch.setenv("TRADINGAGENTS_ENABLE_ALTMAN_VARIANTS", "true")
    monkeypatch.setenv("TRADINGAGENTS_ENABLE_EVIDENCE_SYMMETRY", "false")
    cfg = dc._apply_env_overrides(base)
    assert cfg["enable_altman_variants"] is True
    assert cfg["enable_evidence_symmetry"] is False
    assert [g for g in ROUND3_GATES if cfg[g]] == ["enable_altman_variants"]


def test_composite_rank_parses_the_rendered_peer_string(monkeypatch) -> None:
    """The vendor returns TEXT; iterating it made the peer set the characters of
    "Peers: NVDA, ..." (peers e/P/r/s, and a statement fetch for the symbol "N")."""
    from tradingagents.agents.utils import analysis_tools as at

    seen: list = []

    def _ohlcv(t):
        seen.append(str(t))
        return {"closes": [100.0 + 0.5 * i for i in range(300)]}

    monkeypatch.setattr(at, "_ohlcv", _ohlcv)
    monkeypatch.setattr(
        "tradingagents.dataflows.finnhub.get_company_peers_finnhub",
        lambda t: "Peers: NVDA, AVGO, AMD, INTC, TXN, MRVL, QCOM, ADI, MPWR, ALAB",
    )
    out = at.get_composite_rank.invoke({"ticker": "MU"})
    assert "peers_ranked:" in out
    ranked = out.split("peers_ranked:")[1]
    assert "NVDA" in ranked and "AVGO" in ranked
    assert "e" not in ranked.replace("peers_ranked:", "").split(",")[0].strip().lower()
    assert "N" not in seen and "e" not in seen
    assert "NVDA" in seen and "MU" in seen
