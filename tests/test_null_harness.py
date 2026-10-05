"""H3 synthetic-null workflow falsification: the harness and its diagnostics.

The failing-first proof is :func:`test_white_noise_clean_inside_leak_outside`:
under the white-noise reference class a clean (out-of-sample) pipeline must sit
inside the null band and a deliberately planted in-sample leak must exceed it.
"""

import math
import random

import pytest

from tradingagents.strategies.evaluate import (
    effective_candidates,
    inflation_diagnostics,
    max_abs_z,
    z_statistic,
)
from tradingagents.strategies.null_harness import (
    FAMILYWISE_FALSE_POSITIVE,
    REFERENCE_CLASSES,
    candidate_matrix,
    empirical_null_band,
    falsify_workflow,
    generate_null,
    leaky_pipeline,
    reference_pipeline,
    run_null_harness,
)

pytestmark = pytest.mark.timeout(300)


# --- the failing-first proof -------------------------------------------------

def test_white_noise_clean_inside_leak_outside():
    band = run_null_harness(reference_pipeline, reference_class="white_noise",
                            n_replications=1000, n_obs=252, seed=0)
    assert band["quantile"] is not None and band["n_usable"] == 1000

    # One white-noise sample, two pipelines on it: the honest one (select on IS,
    # report that candidate's OOS value) sits inside the band; the planted leak
    # (report the in-sample maximum) exceeds it.
    sample = generate_null("white_noise", 252, seed=107)
    clean = falsify_workflow(reference_pipeline(sample), band)
    leak = falsify_workflow(leaky_pipeline(sample), band)

    assert clean["falsified"] is False
    assert clean["verdict"] == "inside_null_band"
    assert leak["falsified"] is True
    assert leak["verdict"] == "exceeds_null_band"
    assert leak["observed"] > clean["observed"]


def test_familywise_rate_grows_with_the_search():
    """The K=1 band is ~alpha; a K-candidate search inflates the false-positive rate.

    2604.15531's headline, reproduced on the reference zoo: a search of K
    candidates rejects at roughly ``1 - (1-alpha)^K`` under the null (5.3% at
    K=1, 92.3% at K=50), so the leak's outside-band rate must dwarf the clean
    pipeline's.
    """
    band = run_null_harness(reference_pipeline, reference_class="white_noise",
                            n_replications=1000, n_obs=252, seed=0)
    q = band["quantile"]
    assert q is not None
    m = 200
    clean_out = sum(
        reference_pipeline(generate_null("white_noise", 252, seed=s)) > q
        for s in range(1000, 1000 + m))
    leak_out = sum(
        leaky_pipeline(generate_null("white_noise", 252, seed=s)) > q
        for s in range(1000, 1000 + m))
    clean_rate, leak_rate = clean_out / m, leak_out / m
    assert clean_rate <= 0.10                        # ~alpha
    assert leak_rate >= 0.20                         # a 7-candidate search
    assert leak_rate > 2.0 * clean_rate


# --- generators and the band -------------------------------------------------

def test_generators_are_mean_zero_and_deterministic():
    for name in REFERENCE_CLASSES:
        a = generate_null(name, 500, seed=7)
        b = generate_null(name, 500, seed=7)
        assert a == b, name
        assert len(a) == 500
        assert all(math.isfinite(v) for v in a)
        # A null environment has no directional edge: its sample mean is noise.
        assert abs(sum(a) / len(a)) < 5e-3, name
        # And it is not a constant series (the generators carry variance).
        assert max(a) > min(a), name


def test_unknown_reference_class_names_itself():
    with pytest.raises(ValueError, match="white_noise"):
        generate_null("no_such_class", 10, seed=0)


def test_empirical_null_band_order_statistic():
    samples = [float(i) for i in range(100)]           # 0..99
    band = empirical_null_band(samples, alpha=0.05)
    # inverted empirical CDF: sorted[ceil(0.95*100)-1] == sorted[94] == 94
    assert band["quantile"] == 94.0
    assert band["n_usable"] == 100
    assert empirical_null_band([], 0.05)["quantile"] is None
    assert empirical_null_band([float("nan")], 0.05)["quantile"] is None


def test_falsify_refuses_without_a_band():
    out = falsify_workflow(1.0, {"quantile": None, "alpha": 0.05})
    assert out["falsified"] is None
    assert out["verdict"] == "unavailable"


def test_familywise_warning_is_carried():
    assert FAMILYWISE_FALSE_POSITIVE[1] == pytest.approx(0.053)
    assert FAMILYWISE_FALSE_POSITIVE[50] == pytest.approx(0.923)


# --- Stage 2 diagnostics -----------------------------------------------------

def test_z_statistic_and_refusals():
    rng = random.Random(3)
    assert z_statistic([rng.gauss(0.0, 0.01) for _ in range(200)]) is not None
    assert z_statistic([0.01]) is None            # one observation
    assert z_statistic([0.0] * 50) is None        # zero variance
    # A positive mean against small noise is a large positive z.
    assert z_statistic([0.01 + rng.gauss(0.0, 0.001) for _ in range(200)]) > 5.0


def test_effective_candidates_limits():
    rng = random.Random(11)
    independent = [
        [rng.gauss(0.0, 1.0) for _ in range(300)] for _ in range(4)
    ]
    k_eff = effective_candidates(independent)
    assert k_eff is not None and 3.5 < k_eff <= 4.0

    row = [rng.gauss(0.0, 1.0) for _ in range(300)]
    assert effective_candidates([row, list(row), list(row)]) == pytest.approx(1.0, abs=1e-6)

    assert effective_candidates([[0.0] * 10]) is None      # one candidate
    assert max_abs_z([[0.0] * 10]) is None                 # no computable z


def test_inflation_diagnostics_reports_delta_and_k_eff():
    rng = random.Random(5)
    n = 200
    is_rows = [[0.01 + rng.gauss(0.0, 0.001) for _ in range(n)] for _ in range(4)]
    wf_rows = [[rng.gauss(0.0, 0.01) for _ in range(n)] for _ in range(4)]
    diag = inflation_diagnostics(is_rows, wf_rows)
    assert diag["z_is_star"] is not None and diag["z_wf_star"] is not None
    assert diag["z_is_star"] > diag["z_wf_star"] > 0.0
    assert diag["delta_z"] is not None and diag["delta_z"] > 0.0
    assert diag["k_eff"] is not None and 3.0 < diag["k_eff"] <= 4.0
    assert diag["n_candidates"] == 4

    empty = inflation_diagnostics([], None)
    assert empty["delta_z"] is None and empty["k_eff"] is None


def test_candidate_matrix_splits_in_and_out_of_sample():
    is_rows, wf_rows = candidate_matrix(generate_null("garch11", 252, seed=1))
    assert len(is_rows) == 7                       # one row per candidate
    assert len(wf_rows) == 1                       # the selected winner only
    assert all(len(r) == 126 for r in is_rows)
    assert len(wf_rows[0]) == 126


def test_stage2_delta_z_is_the_difference_of_the_winners():
    """Stage 2 reads its inflation diagnostic off one candidate matrix."""
    sample = generate_null("white_noise", 252, seed=404)
    is_matrix, wf_matrix = candidate_matrix(sample)
    diag = inflation_diagnostics(is_matrix, wf_matrix)
    assert diag["z_is_star"] is not None and diag["z_wf_star"] is not None
    assert diag["delta_z"] == pytest.approx(diag["z_is_star"] - diag["z_wf_star"])
