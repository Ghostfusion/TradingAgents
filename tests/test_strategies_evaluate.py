"""Phase 0 unit tests: cost-aware evaluation metrics (offline)."""

import math
import random
from statistics import NormalDist

import pytest

from tradingagents.strategies.evaluate import (
    _mintrl_observations,
    benjamini_yekutieli,
    cagr,
    deflated_sharpe,
    deflated_sharpe_ratio,
    deflated_sharpe_report,
    equity_curve,
    information_ratio,
    max_drawdown,
    min_track_record_length,
    net_returns,
    pbo_flag,
    sharpe,
    total_return,
    tracking_error,
    volatility,
    walk_forward_splits,
)

pytestmark = pytest.mark.timeout(120)


def test_net_returns_subtracts_costs():
    out = net_returns([0.01, -0.005], cost_bps=10)
    assert abs(out[0] - (0.01 - 0.001)) < 1e-9
    assert abs(out[1] - (-0.005 - 0.001)) < 1e-9


def test_net_returns_illiq_scales_cost():
    # item 3: illiquid name scales cost up; None illiq keeps flat cost.
    out = net_returns([0.01], cost_bps=10, illiq=1e-5)
    extra = 1e-5 * 1e5 / 10000.0  # +1bp
    assert abs(out[0] - (0.01 - 0.001 - extra)) < 1e-9
    flat = net_returns([0.01], cost_bps=10, illiq=None)
    assert abs(flat[0] - (0.01 - 0.001)) < 1e-9


def test_total_return_compounds():
    assert abs(total_return([0.1, 0.1]) - 0.21) < 1e-9
    assert total_return([]) == 0.0


def test_tracking_error_of_a_constant_offset_is_zero():
    """A flat cost offset on an exactly-tracked series is zero TE, not float
    noise: the std of the ~1e-18 residuals annualized to a TE ~7e-18 and then
    divided into a nonsense information ratio (IEI 2026-09-16 shipped
    info_ratio=-2.9e17 in an analyst prompt)."""
    raw = [0.012345, -0.009876, 0.004321, 0.007654,
           -0.003210, 0.001234, -0.005432, 0.002345]
    offset = [r - 0.001 for r in raw]
    assert tracking_error(offset, raw) == 0.0
    assert information_ratio(offset, raw) is None
    # A genuinely divergent series still measures.
    te = tracking_error(raw, [r * 1.5 for r in raw])
    assert te is not None and te > 1e-3


def test_cagr_zero_on_empty():
    assert cagr([]) == 0.0
    assert cagr([0.0, 0.0]) == 0.0


def test_sharpe_positive_for_up_trend():
    r = [0.0012 if i % 2 else 0.0005 for i in range(252)]
    assert sharpe(r) > 0
    assert volatility(r) > 0


def test_deflated_sharpe_penalizes_trials():
    r = [0.01, -0.005, 0.008, -0.003, 0.012]
    one = deflated_sharpe(r, n_trials=1)
    many = deflated_sharpe(r, n_trials=1000)
    assert many < one


def test_max_drawdown():
    curve = [100.0, 120.0, 110.0, 130.0]
    assert abs(max_drawdown(curve) - (120 - 110) / 120) < 1e-9


def test_equity_curve_compounds():
    eq = equity_curve([0.01] * 3, start=100)
    assert abs(eq[-1] - 100 * 1.01**3) < 1e-6


def test_walk_forward_splits():
    splits = list(walk_forward_splits(list(range(10)), train_len=3, test_len=2))
    assert len(splits) == 3
    assert splits[0][0] == [0, 1, 2]
    assert splits[0][1] == [3, 4]


def test_pbo_flag_detects_overfit():
    assert pbo_flag([1.0, 2.0, 0.5], [0.2, -0.5, 0.3]) is True  # best trial tanks
    assert pbo_flag([1.0, 2.0], [0.4, 0.5]) is False


# Alternating +/- returns: per-observation SR ~0.08 (mean 0.0008, sd 0.01), so
# the ANNUALIZED Sharpe is ~1.3 while the 50-trial per-observation selection
# threshold is ~2.80 - the scale gap the legacy difference mixes.
_ALTERNATING = [0.0108, -0.0092] * 250


def test_deflated_sharpe_ratio_is_per_observation_and_probabilistic():
    """Eq. (2) is applied in per-observation units and returns a probability.

    The legacy ``deflated_sharpe`` subtracts a unit-scale threshold from an
    annualized Sharpe, so its value here is a large negative Sharpe-unit
    difference; the DSR is a confidence in [0, 1] and reads the same series as
    indistinguishable from noise after 50 trials.
    """
    dsr = deflated_sharpe_ratio(_ALTERNATING, n_trials=50)
    assert dsr is not None
    assert 0.0 <= dsr <= 1.0
    assert dsr < 0.5
    assert deflated_sharpe(_ALTERNATING, n_trials=50) < 0.0


def test_deflated_sharpe_ratio_falls_as_trials_grow():
    small = deflated_sharpe_ratio(_ALTERNATING, n_trials=10)
    large = deflated_sharpe_ratio(_ALTERNATING, n_trials=1000)
    assert small is not None and large is not None
    assert large <= small


def test_deflated_sharpe_ratio_guards_degenerate_inputs():
    assert deflated_sharpe_ratio(_ALTERNATING, n_trials=1) is None        # N < 2
    assert deflated_sharpe_ratio([0.01, 0.02], n_trials=10) is None       # < 4 obs
    assert deflated_sharpe_ratio(_ALTERNATING, n_trials=10,
                                 sharpe_dispersion=0.0) is None           # no dispersion


def test_deflated_sharpe_ratio_uses_the_measured_dispersion():
    """A tightly clustered search deflates less than the unit-variance default:
    V is what the selection threshold is actually built from."""
    assumed = deflated_sharpe_ratio(_ALTERNATING, n_trials=50)
    measured = deflated_sharpe_ratio(_ALTERNATING, n_trials=50,
                                     sharpe_dispersion=0.0005)
    assert assumed is not None and measured is not None
    assert measured > assumed


def test_deflated_sharpe_report_carries_the_ratio():
    rep = deflated_sharpe_report([0.001, -0.002, 0.003] * 40, n_trials=10)
    assert rep["ratio"] is not None and 0.0 <= rep["ratio"] <= 1.0
    assert rep["ratio"] != rep["value"]  # a probability beside the difference


def test_min_track_record_reproduces_the_papers_three_examples():
    """The closed form, checked against the primary source's own numbers.

    Bailey & Lopez de Prado, "The Sharpe Ratio Efficient Frontier" (2012) §5
    publishes the MinTRL for an annualized Sharpe of 2 to clear 1 at 95% under
    IID normal returns: 2.73 years on daily data, 2.83 weekly, 3.24 monthly.
    Those three come out only if the formula is applied in PER-OBSERVATION units
    (which the paper states in words) with the standardized kurtosis (3, not the
    excess) - the convention this module's PSR already uses.
    """
    z = NormalDist().inv_cdf(0.95)
    for periods, expected_years in ((252.0, 2.73), (52.0, 2.83), (12.0, 3.24)):
        obs = _mintrl_observations(2.0 / math.sqrt(periods), 1.0 / math.sqrt(periods),
                                   0.0, 3.0, z)
        assert obs is not None
        assert obs / periods == pytest.approx(expected_years, abs=0.02)


def test_min_track_record_rises_with_skew_kurtosis_and_confidence():
    """The paper's three stated directions, at a fixed Sharpe: more negative
    skew, fatter tails and a higher confidence level each demand a LONGER record
    (as does a weaker Sharpe, its fourth)."""
    z95 = NormalDist().inv_cdf(0.95)
    z99 = NormalDist().inv_cdf(0.99)
    base = _mintrl_observations(0.15, 0.05, 0.0, 3.0, z95)
    assert base is not None
    assert _mintrl_observations(0.15, 0.05, -1.0, 3.0, z95) > base
    assert _mintrl_observations(0.15, 0.05, 0.0, 9.0, z95) > base
    assert _mintrl_observations(0.15, 0.05, 0.0, 3.0, z99) > base
    assert _mintrl_observations(0.10, 0.05, 0.0, 3.0, z95) > base


def test_min_track_record_is_none_when_no_length_can_suffice():
    """The paper's own case: at or below the benchmark no record is long
    enough, so a number there would be a fabrication."""
    assert _mintrl_observations(0.05, 0.05, 0.0, 3.0, 1.645) is None
    assert _mintrl_observations(0.04, 0.05, 0.0, 3.0, 1.645) is None
    rng = random.Random(3)
    healthy = [rng.gauss(0.001, 0.01) for _ in range(400)]
    out = min_track_record_length(healthy)
    assert out is not None and out["min_track_record"] > 0
    assert out["n"] == 400 and out["benchmark_sharpe"] == 0.0
    assert out["min_track_record_years"] == pytest.approx(out["min_track_record"] / 252.0)
    assert out["confidence"] == pytest.approx(0.95)
    # A bar below the measured Sharpe still leaves a finite length; one at or
    # above it leaves none.
    assert min_track_record_length(healthy, benchmark_sharpe=out["observed_sharpe"] / 2) is not None
    assert min_track_record_length(healthy, benchmark_sharpe=out["observed_sharpe"] * 2) is None
    assert min_track_record_length([0.01] * 40) is None           # zero variance
    assert min_track_record_length([0.01, -0.02, 0.01]) is None   # < 4 observations
    assert min_track_record_length(healthy, alpha=1.5) is None    # not a probability


def test_the_report_carries_the_length_beside_the_deflated_number():
    """E2: no reported Sharpe without the record length its claim would need."""
    rep = deflated_sharpe_report([0.001, -0.002, 0.003] * 40, n_trials=10)
    assert rep["min_track_record"] is not None
    assert rep["min_track_record"]["n"] == 120
    assert "in observations not calendar terms" in rep["min_track_record"]["basis"]


def test_the_family_fdr_step_up_is_one_producer():
    """Benjamini-Yekutieli by default; Benjamini-Hochberg only on request.

    The harmonic term is what makes BY valid for the arbitrarily dependent
    p-values a family of signals on one return matrix produces, so the two
    methods must not be interchangeable. A None anywhere in the list is refused
    rather than dropped, because dropping it would mis-align the positional
    ``surviving`` list against a caller's own rows.
    """
    ps = [0.001, 0.015, 0.2, 0.3, 0.5]
    by = benjamini_yekutieli(ps, 0.05)
    assert by["method"] == "BY"
    assert by["harmonic"] == pytest.approx(sum(1.0 / i for i in range(1, 6)))
    assert by["surviving"] == [True, False, False, False, False]
    assert by["cut_rank"] == 1 and by["reject"] == [0.001]
    bh = benjamini_yekutieli(ps, 0.05, independent=True)
    assert bh["method"] == "BH" and bh["harmonic"] == 1.0
    # BH is the less conservative rule, and at this p-set it rejects strictly more.
    assert sum(bh["surviving"]) == 2 > sum(by["surviving"])
    assert benjamini_yekutieli(ps, 0.0)["cut_rank"] == 0
    assert benjamini_yekutieli([]) is None
    assert benjamini_yekutieli([0.01, None]) is None
