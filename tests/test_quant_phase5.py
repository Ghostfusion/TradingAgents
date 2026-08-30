"""Quant Phase-5 tests: credit hazard, variance-swap strike, implementation
shortfall (offline)."""

import pytest

from tradingagents.strategies.credit_spread import (
    default_probability,
    hazard_from_spread,
)
from tradingagents.strategies.evaluate import implementation_shortfall
from tradingagents.strategies.options_math import variance_swap_strike

pytestmark = pytest.mark.timeout(120)


def test_hazard_from_spread():
    # spread 5% (0.05), RR 40% -> lambda = 0.05/0.6 = 0.0833.
    assert hazard_from_spread(0.05, 0.40) == pytest.approx(0.05 / 0.6, rel=1e-6)
    assert hazard_from_spread(None) is None
    assert hazard_from_spread(0.0) is None
    assert hazard_from_spread(0.05, 1.0) is None  # invalid recovery


def test_default_probability():
    # lambda 0.0833 over 1y -> PD = 1 - exp(-0.0833) = 0.08.
    pd = default_probability(0.05, 1.0, 0.40)
    assert pd is not None and 0.07 < pd < 0.09
    # Longer horizon increases PD.
    pd5 = default_probability(0.05, 5.0, 0.40)
    assert pd5 is not None and pd5 > pd
    assert default_probability(None, 1.0) is None
    assert default_probability(0.05, 0.0) is None


def test_variance_swap_strike_synthetic():
    # Wider grid so each OTM side has >= 3 strikes around F=100.
    strikes = [70, 80, 90, 100, 110, 120, 130]
    calls = [31.0, 21.0, 12.0, 4.0, 1.1, 0.3, 0.08]  # OTM calls above 100
    puts = [0.08, 0.3, 1.1, 4.0, 12.0, 21.0, 31.0]  # OTM puts below 100
    s = variance_swap_strike(strikes, calls, puts, 100.0, 0.5, 0.0)
    assert s is not None and s > 0


def test_variance_swap_invalid_none():
    assert variance_swap_strike([], [], [], 100.0, 0.5) is None
    assert variance_swap_strike([80, 90], [1, 2], [1, 2], 100.0, 0.5) is None  # <3/side
    assert variance_swap_strike([80, 90, 100], [1, 2, 3], [1, 2, 3], 100.0, 0.5) is None  # <3 OTM per side
    assert variance_swap_strike([80, 90, 100, 110, 120], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], 0.0, 0.5) is None


def test_implementation_shortfall():
    # decision 100, arrival 100.5 (price rose), fill 100.6 -> explicit +0.2
    # vs arrival, market +0.5 vs decision, total 0.7bp (per-share qty=1).
    res = implementation_shortfall(100.0, 100.5, 100.6)
    assert res is not None
    # explicit = (fill-arrival)*qty = 0.1*1; market = (arrival-decision)*qty=0.5.
    assert res["explicit"] == pytest.approx(0.1)
    assert res["market_impact"] == pytest.approx(0.5)
    # total = 0.6/100 notional -> 60 bp.
    assert res["implementation_shortfall_bp"] == pytest.approx(60.0, rel=0.01)
    # With quantity 1000 the explicit grows.
    res2 = implementation_shortfall(100.0, 100.5, 100.6, quantity=1000.0)
    # total = 0.6 * 1000 = 600 over notional 100*1000 = 100000 -> 60 bp.
    assert res2["explicit"] == pytest.approx(100.0)
    assert res2["implementation_shortfall_bp"] == pytest.approx(60.0, rel=0.01)
    # Missing price -> None.
    assert implementation_shortfall(None, 100.0, 100.0) is None
    assert implementation_shortfall(100.0, 0.0, 100.0) is None


def test_strategy_quality_execution_is():
    """build_report's execution block reports avg implementation shortfall
    from the paper-ledger rows."""
    import os
    import tempfile

    from scripts.strategy_quality_report import build_report

    with tempfile.TemporaryDirectory() as d:
        import json

        rows = [
            {"realized_return": 0.01, "arrival_price": 100.0, "fill_price": 100.5, "prior_close": 99.5},
            {"realized_return": -0.02, "arrival_price": 100.0, "fill_price": 99.8, "prior_close": 100.5},
        ]
        with open(os.path.join(d, "pre_market_ledger.jsonl"), "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        report = build_report(d)
        ex = report["execution"]
        assert ex["avg_is_bp"] is not None
        assert ex["rows_with_slippage"] >= 0

