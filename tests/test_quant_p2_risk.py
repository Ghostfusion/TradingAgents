"""Tests for P2: Cornish-Fisher VaR, Kappa/LPM, Burke/Martin/Pain, gain-to-pain,
risk of ruin, optimal f."""

import pytest

from tradingagents.strategies.evaluate import (
    burke_ratio,
    martin_ratio,
    pain_index,
    pain_ratio,
)
from tradingagents.strategies.rate_utils import (
    gain_to_pain,
    kappa_ratio,
    lower_partial_moment,
)
from tradingagents.strategies.size import modified_var, optimal_f, risk_of_ruin

pytestmark = pytest.mark.timeout(60)


# --- Cornish-Fisher modified VaR ------------------------------------------


def test_modified_var_normal_returns_close_to_gaussian():
    import random

    rnd = random.Random(42)
    rets = [rnd.gauss(0.0005, 0.02) for _ in range(300)]
    m = modified_var(rets, alpha=0.05)
    assert m is not None and m > 0
    # Gaussian 95% VaR ~ 1.645*0.02 - 0.0005 ~ 0.0324
    assert 0.02 < m < 0.06


def test_modified_var_negative_skew_increases_var():
    rets = [-(x * x) * 0.01 - 0.001 for x in [i / 100 for i in range(1, 200)]]  # left-skew
    m_skew = modified_var(rets, alpha=0.05)
    import random

    rnd = random.Random(7)
    m_gauss = modified_var([rnd.gauss(0.0, 0.02) for _ in range(200)], alpha=0.05)
    assert m_skew is not None and (m_gauss is None or m_skew > m_gauss)


def test_modified_var_none_safe():
    assert modified_var([], alpha=0.05) is None
    assert modified_var([0.01, 0.02, -0.01], alpha=0.05) is None  # < 5 obs


# --- Kappa / LPM ---------------------------------------------------------


def test_lower_partial_moment_specializes():
    rets = [0.02, -0.03, 0.01, -0.04]
    lpm1 = lower_partial_moment(rets, 0.0, 1.0)
    # lpm1 = mean shortfall over ALL obs: (0.03 + 0.04)/4 = 0.0175
    assert lpm1 == pytest.approx(0.0175)
    lpm2 = lower_partial_moment(rets, 0.0, 2.0)
    # lpm2 = ((0.03^2 + 0.04^2)/4)^0.5
    assert lpm2 == pytest.approx(((0.03 ** 2 + 0.04 ** 2) / 4) ** 0.5)


def test_kappa_ratio_bounds():
    rets = [0.02, -0.01, 0.03, -0.005]  # positive mean
    k = kappa_ratio(rets, 0.0, 2.0)
    assert k is not None and k > 0
    # worse downside -> lower kappa
    rets_bad = [0.03, -0.06, 0.02, -0.05]
    assert kappa_ratio(rets_bad, 0.0, 2.0) < k


def test_kappa_none_safe():
    assert kappa_ratio([0.01, 0.02, 0.03], 0.0) is None  # no shortfalls -> LPM 0
    assert kappa_ratio([], 0.0) is None


# --- Burke / Martin / Pain ------------------------------------------------


def test_burke_martin_pain_positive_for_profitable_series():
    rets = [0.002] * 100 + [-0.01] + [0.003] * 99  # small drawdown after up-trend
    assert burke_ratio(rets) is not None
    assert martin_ratio(rets) is not None
    assert pain_index(rets) is not None and pain_index(rets) >= 0
    assert pain_ratio(rets) is not None


def test_burke_none_on_no_drawdown():
    rets = [0.001] * 150  # monotone up -> no drawdown events
    assert burke_ratio(rets) is None
    assert pain_index(rets) == pytest.approx(0.0)


def test_ratios_none_safe():
    assert burke_ratio([]) is None
    assert martin_ratio([]) is None
    assert pain_index([]) is None
    assert pain_ratio([]) is None


# --- gain-to-pain ---------------------------------------------------------


def test_gain_to_pain():
    rets = [0.05, -0.02, 0.03, -0.01]
    assert gain_to_pain(rets) == pytest.approx(0.08 / 0.03)


def test_gain_to_pain_none_on_lossless_or_empty():
    assert gain_to_pain([0.01, 0.02]) is None  # no pain
    assert gain_to_pain([]) is None


# --- ruin / optimal f -----------------------------------------------------


def test_risk_of_ruin_increases_with_fraction():
    r_small = risk_of_ruin(0.55, 1.0, 0.02)
    r_large = risk_of_ruin(0.55, 1.0, 0.5)
    assert r_small is not None and r_large is not None
    assert r_large >= r_small


def test_risk_of_ruin_none_on_bad_inputs():
    assert risk_of_ruin(1.1, 1.0, 0.1) is None  # p out of range
    assert risk_of_ruin(0.5, 0.0, 0.1) is None  # payoff <= 0
    assert risk_of_ruin(0.5, 1.0, 1.5) is None  # f >= 1


def test_optimal_f_sane_range():
    rets = [0.05, -0.02, 0.03, -0.01, 0.02, -0.005] * 20
    f = optimal_f(rets)
    assert f is not None and 0 < f <= 1.0


def test_optimal_f_none_with_ruin_returns():
    assert optimal_f([-1.0, 0.01, 0.02]) is None  # a -100% return breaks the product
    assert optimal_f([]) is None
