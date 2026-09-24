"""R2 (2606.23492): heavy-tailed emissions and a coverage-tested regime VaR.

One shared forward-backward kernel; only the per-state emission density and
M-step swap across families. The regime-conditional VaR is the running state
posterior times each state's CDF, and its output is checked by Kupiec and
Christoffersen joint conditional coverage on held-out data - the coverage test
IS the deliverable.

Offline and deterministic: every series is synthetic under a fixed seed, and the
verdicts are the ones the tests' own manufactured two-regime series produce.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from tradingagents.dataflows.config import get_config, reset_config, set_config
from tradingagents.strategies.book_risk import var_coverage_test
from tradingagents.strategies.regime import (
    hmm_filtered_regime,
    regime_conditional_var,
)

#: The Student-t degrees of freedom of the manufactured heavy tail. A low nu
#: makes the Gaussian CDF's tail error large enough to be rejected.
NU = 3.0

CALM, TURBULENT = 0.008, 0.025


def _two_regime_returns(n: int = 2000, seed: int = 7):
    """A two-regime series whose within-regime innovations are fat-tailed."""
    rng = np.random.default_rng(seed)
    regime = np.zeros(n, dtype=int)
    regime[500:900] = 1
    regime[1400:1650] = 1
    sigma = np.where(regime == 1, TURBULENT, CALM)
    z = rng.standard_t(NU, size=n) / math.sqrt(NU / (NU - 2.0))
    return regime.tolist(), (sigma * z).tolist()


def _posteriors(regime: list[int]) -> list:
    return [[1.0, 0.0] if s == 0 else [0.0, 1.0] for s in regime]


def _emissions(family: str) -> dict:
    if family == "student_t":
        # the family-native scale: sigma / sqrt(nu/(nu-2)) for a unit-variance t
        s = math.sqrt(NU / (NU - 2.0))
        return {"family": "student_t", "means": [0.0, 0.0],
                "scales": [CALM / s, TURBULENT / s], "nu": NU}
    return {"family": "gaussian", "means": [0.0, 0.0],
            "scales": [CALM, TURBULENT]}


def test_the_coverage_test_rejects_the_gaussian_var():
    """On a fat-tailed two-regime series the Gaussian VaR fails joint coverage.

    The Student-t VaR - the same data, the matching emission - does not. The
    verdict carries the coverage level and the held-out window it was computed on.
    """
    regime, rets = _two_regime_returns()
    post = _posteriors(regime)
    g_var = regime_conditional_var(post, _emissions("gaussian"), 0.05)
    t_var = regime_conditional_var(post, _emissions("student_t"), 0.05)

    g = var_coverage_test(rets, alpha=0.05, var_series=g_var)
    t = var_coverage_test(rets, alpha=0.05, var_series=t_var)

    assert g["verdict"] == "fail"
    assert t["verdict"] == "pass"

    # the reported verdict carries the coverage level and the held-out window
    assert g["coverage_level"] == pytest.approx(0.95)
    assert g["kupiec"]["expected"] == pytest.approx(0.05)
    assert g["window"]["n"] == len(rets)
    assert g["window"]["min_window"] > 0
    assert g["window"]["first"] is not None and g["window"]["last"] is not None
    assert g["n"] == len(rets)

    # the Gaussian CDF over-covers (its tail is thinner than the data's); the
    # Student-t CDF breaches at about its stated level
    assert g["kupiec"]["hit_rate"] < t["kupiec"]["hit_rate"]
    assert t["kupiec"]["hit_rate"] == pytest.approx(0.05, abs=0.02)


def test_the_coverage_test_refuses_a_thin_held_out_window():
    res = var_coverage_test([0.01] * 30, alpha=0.05, var_series=[-0.02] * 30)
    assert res["verdict"] == "unavailable"
    assert res["kupiec"]["p_value"] is None
    assert res["christoffersen"]["joint_p_value"] is None
    assert res["window"]["min_window"] >= 60


def test_a_quiet_var_that_never_breaches_is_still_judged():
    """A VaR that never breaches is over-conservative, so the POF test rejects it."""
    rets = [0.001 * i for i in range(1, 201)]          # strictly positive
    res = var_coverage_test(rets, alpha=0.05, var_series=[-10.0] * 200)
    assert res["verdict"] == "fail"
    assert res["kupiec"]["hits"] == 0
    assert res["christoffersen"]["joint_p_value"] is None  # no transitions


# --- the emission parameter on the shared kernel ---------------------------


def _two_regime_closes(n_up: int = 150, n_down: int = 150, seed: int = 5):
    """An up-regime then a down-regime close series (the existing HMM fixture)."""
    rng = np.random.default_rng(seed)
    r = np.concatenate([
        rng.normal(0.0012, 0.006, n_up),
        rng.normal(-0.0018, 0.020, n_down),
    ])
    return [100.0 * float(v) for v in np.exp(np.cumsum(r))]


def test_gaussian_emission_preserves_todays_probs_bit_for_bit():
    closes = _two_regime_closes()
    explicit = hmm_filtered_regime(closes, closes, closes, closes, n_states=2)
    default = hmm_filtered_regime(closes, closes, closes, closes, n_states=2,
                                  emission="gaussian")
    assert explicit is not None and default is not None
    assert explicit["probs"] == default["probs"]
    assert explicit["last"] == default["last"]
    assert explicit["emission"]["family"] == "gaussian"


def test_a_heavy_emission_falls_back_to_gaussian_when_the_gate_is_off():
    saved = dict(get_config() or {})
    closes = _two_regime_closes()
    try:
        set_config({**saved, "enable_hmm_heavy_tails": False})
        base = hmm_filtered_regime(closes, closes, closes, closes, n_states=2)
        fallback = hmm_filtered_regime(closes, closes, closes, closes, n_states=2,
                                       emission="student_t")
        assert fallback["emission"]["family"] == "gaussian"
        assert fallback["emission"]["gate_off_fallback"] is True
        assert fallback["probs"] == base["probs"]      # a gate-off run is unchanged
        assert "fell back to gaussian" in fallback["basis"]

        set_config({**saved, "enable_hmm_heavy_tails": True})
        heavy = hmm_filtered_regime(closes, closes, closes, closes, n_states=2,
                                    emission="student_t", nu=4.0)
        assert heavy["emission"]["family"] == "student_t"
        assert heavy["emission"]["gate_off_fallback"] is False
        assert heavy["emission"]["nu"] == pytest.approx(4.0)
        # the filter still produces a valid posterior row under the heavy family
        for row in heavy["probs"][heavy["first_index"]:]:
            assert row is not None and abs(sum(row) - 1.0) < 1e-6
    finally:
        reset_config()


def test_the_book_risk_consumer_hands_the_regime_var_to_the_coverage_test():
    """R2's VaR consumer sits in ``book_risk``: regime VaR -> coverage test."""
    from tradingagents.strategies.book_risk import _regime_var_coverage

    regime, rets = _two_regime_returns()
    out = _regime_var_coverage(rets, _posteriors(regime), _emissions("gaussian"), q=0.05)
    assert out["verdict"] == "fail"
    assert out["q"] == pytest.approx(0.05)
    assert len(out["var_series"]) == len(rets)
    assert out["window"]["min_window"] > 0


def test_a_k_other_than_two_reports_the_selection_criterion():
    closes = _two_regime_closes()
    res = hmm_filtered_regime(closes, closes, closes, closes, n_states=3)
    assert res is not None
    assert res["n_states"] == 3
    sel = res["selection"]
    assert sel["k"] == 3
    assert "supplied" in sel["criterion"]
    assert sel["bic"] is not None and sel["n_obs"] > 0 and sel["n_params"] > 0


def test_an_unknown_emission_family_is_refused():
    closes = _two_regime_closes()
    assert hmm_filtered_regime(closes, closes, closes, closes, n_states=2,
                               emission="cauchy") is None


def test_regime_conditional_var_is_a_named_gap_for_an_unmeasured_row():
    out = regime_conditional_var([None, [1.0, 0.0]], _emissions("gaussian"), 0.05)
    assert out[0] is None
    assert out[1] is not None and out[1] < 0.0     # a loss quantile, not a level
