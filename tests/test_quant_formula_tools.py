"""Round-2 agent tools: gating, happy paths, and honest degradation.

Docs: ``docs/implementation_plan_quant_formula_additions.md``. The calculators
have their own gates (``test_liquidity_spread`` / ``test_book_risk_sizing`` /
``test_return_decomposition`` / ``test_conformal_bands`` /
``test_quality_factors`` / ``test_text_factors``); these gates cover the TOOL
layer the agents actually call: the DISABLED sentinel when a flag is off, the
rendered value when it is on, and an explicit unavailable line (never a
fabricated number) when the inputs are missing.
"""

from __future__ import annotations

import json

import pytest

from tradingagents.agents.utils import quant_formula_tools as qft

FLAGS = [
    ("get_spread_estimate", "enable_spread_estimator", {"ticker": "TEST"}),
    ("get_return_decomposition", "enable_return_decomposition", {"ticker": "TEST"}),
    ("get_valuation_band", "enable_conformal_bands", {"ticker": "TEST", "point_value": 100.0}),
    ("get_disclosure_tone", "enable_text_factors", {"ticker": "TEST"}),
    ("get_book_risk_budget", "enable_book_risk_sizing", {}),
]


def _cfg(monkeypatch, **flags):
    """Patch the live config the tools read through ``_flag``."""
    base = {
        "results_dir": "/nonexistent-results-dir",
        "conformal_alpha": 0.1,
        "conformal_min_pairs": 3,
        "conformal_window": 250,
        "max_position_pct": 0.5,
        "risk_daily_cvar_budget_pct": 0.03,
        "book_risk_sizing_min_scenarios": 60,
        "book_risk_sizing_max_delta": 0.05,
        "risk_basket_tickers": ["AAA", "BBB"],
        "risk_basket_weights": {"AAA": 0.5, "BBB": 0.5},
    }
    base.update(flags)
    monkeypatch.setattr("tradingagents.dataflows.config.get_config", lambda: base)
    return base


# --- the gate: every tool is a DISABLED sentinel while its flag is off -------


@pytest.mark.parametrize("tool_name,flag,args", FLAGS, ids=[f[0] for f in FLAGS])
def test_a_tool_is_a_disabled_sentinel_while_its_flag_is_off(monkeypatch, tool_name, flag, args):
    _cfg(monkeypatch)
    out = getattr(qft, tool_name).invoke(args)
    assert "DISABLED" in out
    assert flag in out, "the sentinel must name the flag to flip"
    assert "No value computed" in out


def test_the_flag_name_in_the_sentinel_matches_the_gate_that_guards_the_tool(monkeypatch):
    """A copy-pasted wrong flag would silently disable a tool for ever."""
    _cfg(monkeypatch, enable_spread_estimator=True)
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._ohlcv",
        lambda t, days=320: {"closes": [10.0, 10.1] * 20, "highs": [10.2] * 40, "lows": [9.9] * 40},
    )
    out = qft.get_spread_estimate.invoke({"ticker": "TEST"})
    assert "DISABLED" not in out


# --- Q1: spread estimate -----------------------------------------------------


def test_spread_estimate_renders_the_computed_floor(monkeypatch):
    _cfg(monkeypatch, enable_spread_estimator=True)
    mids = [100.0 + 0.01 * i for i in range(60)]
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._ohlcv",
        lambda t, days=320: {
            "closes": mids,
            "highs": [m * 1.01 for m in mids],
            "lows": [m * 0.99 for m in mids],
        },
    )
    out = qft.get_spread_estimate.invoke({"ticker": "TEST"})
    assert "spread estimate TEST" in out
    assert "basis=" in out and "FLOOR" in out
    assert "unavailable" not in out
    # Value-level gate: the synthetic series has a 2% high-low range, so the
    # rendered percentage must be a spread of that order - not 100x off, not 0.
    pct = float(out.split("% of price")[0].rsplit("(", 1)[1])
    assert 0.5 <= pct <= 5.0, out


def test_spread_estimate_says_unavailable_when_the_correction_is_negative(monkeypatch):
    _cfg(monkeypatch, enable_spread_estimator=True)
    closes = [100.0 * (1.02 ** i) for i in range(60)]
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._ohlcv",
        lambda t, days=320: {"closes": closes, "highs": closes, "lows": [c * 0.98 for c in closes]},
    )
    out = qft.get_spread_estimate.invoke({"ticker": "TEST"})
    assert "unavailable" in out


# --- Q5: return decomposition ------------------------------------------------


def test_return_decomposition_renders_both_legs(monkeypatch):
    _cfg(monkeypatch, enable_return_decomposition=True)
    closes = [100.0 + i for i in range(40)]
    opens = [c - 1.0 for c in closes]
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._ohlcv",
        lambda t, days=320: {"closes": closes, "opens": opens},
    )
    out = qft.get_return_decomposition.invoke({"ticker": "TEST"})
    assert "intraday" in out and "overnight" in out
    assert "share of total variance" in out


def test_return_decomposition_says_unavailable_without_opens(monkeypatch):
    _cfg(monkeypatch, enable_return_decomposition=True)
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._ohlcv",
        lambda t, days=320: {"closes": [100.0 + i for i in range(40)], "opens": []},
    )
    out = qft.get_return_decomposition.invoke({"ticker": "TEST"})
    assert "unavailable" in out


# --- Q6: disclosure tone -----------------------------------------------------


def test_disclosure_tone_renders_counts_and_a_zero_hit_read(monkeypatch):
    _cfg(monkeypatch, enable_text_factors=True)
    monkeypatch.setattr(
        qft, "_fetch_news_text", lambda t, d: "the company reported a loss and a shortfall"
    )
    monkeypatch.setattr(qft, "_fetch_filing_text", lambda t, d: "")
    out = qft.get_disclosure_tone.invoke({"ticker": "TEST"})
    assert "dictionary lm-seed-v1" in out
    assert "tone=" in out and "divergence=unavailable" in out


def test_disclosure_tone_reports_zero_hits_as_no_signal(monkeypatch):
    _cfg(monkeypatch, enable_text_factors=True)
    monkeypatch.setattr(qft, "_fetch_news_text", lambda t, d: "the and of to a an it")
    monkeypatch.setattr(qft, "_fetch_filing_text", lambda t, d: "")
    out = qft.get_disclosure_tone.invoke({"ticker": "TEST"})
    assert "tone=zero_hits" in out
    assert "NOT neutral" in out or "not neutral" in out


def test_disclosure_tone_says_unavailable_without_text(monkeypatch):
    _cfg(monkeypatch, enable_text_factors=True)
    monkeypatch.setattr(qft, "_fetch_news_text", lambda t, d: "")
    monkeypatch.setattr(qft, "_fetch_filing_text", lambda t, d: "")
    out = qft.get_disclosure_tone.invoke({"ticker": "TEST"})
    assert "unavailable" in out


# --- Q2: book risk budget ----------------------------------------------------


def test_book_risk_budget_solves_under_the_budget(monkeypatch):
    _cfg(monkeypatch, enable_book_risk_sizing=True)
    import random

    rng = random.Random(7)
    series = {
        name: [rng.gauss(0.0002, 0.01) for _ in range(140)]
        for name in ("AAA", "BBB")
    }
    for i in range(0, 140, 7):
        series["BBB"][i] -= 0.02  # asymmetric tail for BBB
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._ohlcv",
        lambda t, days=320: {"closes": [100.0 + c for c in series.get(t, [])]},
    )
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._daily_returns",
        lambda closes: list(closes),
    )
    out = qft.get_book_risk_budget.invoke({})
    assert "book risk budget" in out
    assert "target:" in out and "book CVaR" in out
    assert "nothing here is an order" in out


def test_book_risk_budget_says_unavailable_with_fewer_than_two_usable_names(monkeypatch):
    _cfg(monkeypatch, enable_book_risk_sizing=True, risk_basket_tickers=["AAA"], risk_basket_weights={"AAA": 1.0})
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._ohlcv",
        lambda t, days=320: {"closes": [100.0 + i for i in range(60)]},
    )
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._daily_returns",
        lambda closes: list(closes),
    )
    out = qft.get_book_risk_budget.invoke({})
    assert "unavailable" in out


# --- Q4: quality factors are always-on (no flag) ----------------------------


def test_quality_factors_is_not_flag_gated(monkeypatch):
    """Q4 ships as informational rows: no flag, and no fabricated value."""
    _cfg(monkeypatch)
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d: {}
    )
    out = qft.get_quality_factors.invoke({"ticker": "TEST"})
    assert "DISABLED" not in out
    assert "unavailable" in out


def test_quality_factors_renders_hand_checked_values(monkeypatch):
    _cfg(monkeypatch)
    fin = {
        "revenue": 1000.0,
        "cogs": 600.0,
        "total_assets": {"current": 2000.0, "prior": 1800.0},
        "total_liabilities": 900.0,
        "cash": 300.0,
        "marketable_securities": 100.0,
        "total_debt": 400.0,
    }
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d: fin
    )
    out = qft.get_quality_factors.invoke({"ticker": "TEST"})
    assert "gp_a=0.2000" in out
    assert "noa=+0.6111" in out
    assert "quality counterweight" in out


# --- Q3: valuation band prerequisite ----------------------------------------


def test_valuation_band_names_its_missing_prerequisite(monkeypatch, tmp_path):
    _cfg(monkeypatch, enable_conformal_bands=True, results_dir=str(tmp_path))
    out = qft.get_valuation_band.invoke({"ticker": "TEST", "point_value": 100.0})
    assert "unavailable" in out
    assert "valuation_pairs.jsonl" in out
    assert "left unbanded" in out


def test_valuation_band_refuses_below_the_pair_floor(monkeypatch, tmp_path):
    _cfg(monkeypatch, enable_conformal_bands=True, results_dir=str(tmp_path), conformal_min_pairs=40)
    ledger = tmp_path / "TEST"
    ledger.mkdir()
    (ledger / "valuation_pairs.jsonl").write_text(
        "".join(json.dumps([100.0 + i, 101.0 + i]) + "\n" for i in range(5)),
        encoding="utf-8",
    )
    out = qft.get_valuation_band.invoke({"ticker": "TEST", "point_value": 100.0})
    assert "unavailable" in out
    assert "floor" in out


def test_valuation_band_renders_the_calibrated_band_and_coverage(monkeypatch, tmp_path):
    _cfg(monkeypatch, enable_conformal_bands=True, results_dir=str(tmp_path), conformal_min_pairs=40)
    ledger = tmp_path / "TEST"
    ledger.mkdir()
    # 60 pairs whose residuals are known: the band must be calibrated, not a
    # constant, and the realized coverage must be reported beside the nominal.
    rows = []
    for i in range(60):
        actual = 100.0 + (i % 7) * 0.5
        rows.append(json.dumps([100.0, actual]))
    (ledger / "valuation_pairs.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    out = qft.get_valuation_band.invoke({"ticker": "TEST", "point_value": 100.0})
    assert "valuation band TEST" in out
    assert "nominal" in out and "realized" in out
    assert "point value 100.0000 is" in out
    assert "INSIDE" in out or "OUTSIDE" in out
