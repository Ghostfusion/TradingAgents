"""Tests for the ETF valuation engine (weighted constituent multiples).

The IGV 2026-09-09 review loop: an ETF had no valuation because company
statement tools returned "unavailable". etf_valuation computes the
ETF-appropriate valuation from the underlying basket — harmonic P/E, forward
P/E, earnings/FCF yield, growth, valuation percentile, vs-SPY/vs-XLK, and
top-N concentration. Every metric is None-safe.
"""

from __future__ import annotations

from tradingagents.strategies.etf_valuation import etf_valuation


def _constituents():
    return {
        "A": {"price": 100.0, "eps_ttm": 10.0, "eps_fwd": 12.0, "fcf": 5.0, "mcap": 1000.0, "rev_growth": 0.10, "eps_growth": 0.20},
        "B": {"price": 50.0, "eps_ttm": 5.0, "eps_fwd": 6.0, "fcf": 2.0, "mcap": 500.0, "rev_growth": 0.05, "eps_growth": 0.10},
    }


def test_harmonic_pe_equal_weight():
    # Equal weight: P/E_A = 10, P/E_B = 10 -> harmonic = 10.
    r = etf_valuation("IGV", constituents=_constituents())
    assert r["weighted_pe"] == 10.0
    assert r["earnings_yield"] == 0.1
    assert r["n_constituents"] == 2
    assert r["weights_used"] == "equal"


def test_harmonic_pe_weighted():
    # Weight A=0.75, B=0.25: 1/(0.75/10 + 0.25/10) = 10 (same P/E).
    # Change B's EPS to 2.5 -> P/E_B = 20: 1/(0.75/10 + 0.25/20) = 11.43.
    c = _constituents()
    c["B"]["eps_ttm"] = 2.5
    r = etf_valuation("IGV", constituents=c, weights={"A": 0.75, "B": 0.25})
    assert r["weighted_pe"] == round(1.0 / (0.75 / 10.0 + 0.25 / 20.0), 2)
    assert r["weights_used"] == "provided"


def test_forward_pe_and_fcf_yield():
    r = etf_valuation("IGV", constituents=_constituents())
    # forward P/E: A 100/12=8.33, B 50/6=8.33 -> harmonic 8.33
    assert r["forward_pe"] == round(1.0 / (0.5 / 8.3333 + 0.5 / 8.3333), 2)
    # FCF yield: (0.5*5 + 0.5*2) / (0.5*1000 + 0.5*500) = 3.5/750 = 0.00467
    assert r["fcf_yield"] == round(3.5 / 750.0, 4)


def test_valuation_percentile_and_benchmarks():
    r = etf_valuation("IGV", constituents=_constituents(), etf_pe_history=[8.0, 9.0, 10.0, 12.0], spy_pe=20.0, xlk_pe=25.0)
    # wpe=10 -> percentile rank within [8,9,10,12] = 2/4 = 0.5
    assert r["valuation_percentile"] == 0.5
    assert r["vs_spy"] == round(10.0 / 20.0, 3)
    assert r["vs_xlk"] == round(10.0 / 25.0, 3)


def test_top_n_weight():
    c = _constituents()
    c["C"] = {"price": 10.0, "eps_ttm": 1.0, "eps_fwd": 1.0, "fcf": 0.1, "mcap": 100.0, "rev_growth": 0.0, "eps_growth": 0.0}
    r = etf_valuation("IGV", constituents=c, top_n=2)
    # equal weight 1/3 each; top-2 = 2/3
    assert r["top_n_weight"] == round(2.0 / 3.0, 4)


def test_missing_metric_skipped_not_fabricated():
    c = _constituents()
    c["B"] = {**c["B"], "eps_ttm": None}  # B has no EPS -> skipped from P/E
    r = etf_valuation("IGV", constituents=c)
    # only A contributes: P/E = 10
    assert r["weighted_pe"] == 10.0
    assert r["n_constituents"] == 2  # still counted as present (has other metrics)


def test_empty_constituents_all_none():
    r = etf_valuation("IGV", constituents={})
    assert r["weighted_pe"] is None
    assert r["n_constituents"] == 0
    assert r["weights_used"] == "none"


def test_sector_constituents_extended():
    from tradingagents.strategies.sector_rank import SECTOR_CONSTITUENTS

    for etf in ("IGV", "CIBR", "SKYY", "AIQ", "BOTZ", "DTCR", "NXTG", "IYW", "FINX", "XSD"):
        assert etf in SECTOR_CONSTITUENTS, etf
        assert len(SECTOR_CONSTITUENTS[etf]) >= 5
