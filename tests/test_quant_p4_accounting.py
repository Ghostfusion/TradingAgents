"""Tests for P4: Ohlson O-score, Zmijewski X-score, Dechow-Dichev accrual
quality."""

import pytest

from tradingagents.strategies.earnings_quality import (
    dechow_dichev_aq,
    earnings_quality_verdict,
)
from tradingagents.strategies.normalized import ohlson_o_score, zmijewski_score

pytestmark = pytest.mark.timeout(60)


# --- Ohlson O-score -------------------------------------------------------


def test_ohlson_healthy_firm_low_prob():
    # Low leverage, profitable, positive working capital.
    o = ohlson_o_score(total_assets=1000, total_liabilities=300,
                       working_capital=150, current_assets=400,
                       current_liabilities=250, net_income=80,
                       funds_from_ops=95, ni_prev=70)
    assert o["verdict"] == "healthy"
    assert o["p"] < 0.2 and o["score"] < 0


def test_ohlson_distressed_firm_high_prob():
    # High leverage, thin margin -> distress.
    o = ohlson_o_score(total_assets=1000, total_liabilities=900,
                       working_capital=20, current_assets=200,
                       current_liabilities=180, net_income=5,
                       funds_from_ops=8, ni_prev=-2)
    assert o["verdict"] == "distress"
    assert o["p"] > 0.5


def test_ohlson_none_safe():
    o = ohlson_o_score(None, 300, 150, 400, 250, 80, 95)
    assert o["score"] is None and o["verdict"] is None


# --- Zmijewski ------------------------------------------------------------


def test_zmijewski_healthy_and_distress():
    h = zmijewski_score(net_income=80, total_assets=1000,
                        total_liabilities=300, current_assets=400,
                        current_liabilities=250)
    assert h["verdict"] == "healthy" and h["score"] < 0
    d = zmijewski_score(net_income=5, total_assets=1000,
                        total_liabilities=900, current_assets=200,
                        current_liabilities=180)
    assert d["verdict"] == "distress" and d["score"] > 0


def test_zmijewski_none_safe():
    assert zmijewski_score(None, 1000, 300, 400, 250)["score"] is None


# --- Dechow-Dichev AQ -----------------------------------------------------


def test_dd_aq_perfect_fit_is_zero():
    # Non-monotone CFO (avoids 3-lag collinearity); accruals exactly
    # explained by current CFO -> zero residual.
    cfo = [1.0, 3.0, 2.0, 5.0, 4.0, 7.0, 6.0, 9.0, 8.0, 11.0]
    accruals = [0.5 * c for c in cfo]
    aq = dechow_dichev_aq(accruals, cfo)
    assert aq is not None and aq < 1e-6


def test_dd_aq_noisy_higher():
    import random

    rnd = random.Random(3)
    cfo = [1.0, 3.0, 2.0, 5.0, 4.0, 7.0, 6.0, 9.0, 8.0, 11.0, 10.0, 13.0]
    noisy = [0.5 * c + rnd.gauss(0.0, 0.3) for c in cfo]
    clean = [0.5 * c for c in cfo]
    aq_noisy = dechow_dichev_aq(noisy, cfo)
    aq_clean = dechow_dichev_aq(clean, cfo)
    assert aq_clean is not None and aq_clean < 1e-6
    assert aq_noisy is not None and aq_noisy > aq_clean


def test_dd_aq_none_short():
    assert dechow_dichev_aq([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) is None  # < 6 obs
    assert dechow_dichev_aq([], []) is None


def test_quality_verdict_unchanged_by_dd():
    r = earnings_quality_verdict(10, 9, 100, fcf=4, eps_growth=0.2, fcf_growth=-0.1)
    assert r["level"] == "HIGH"  # regression guard: DD addition didn't change the verdict
