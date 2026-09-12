"""Q2 unit tests: minimum-CVaR sizing, copula scenarios, governor sizing fold."""

import hashlib
import json

import pytest

from tradingagents.strategies.book_risk import (
    copula_scenarios,
    cvar,
    min_cvar_weights,
    portfolio_returns,
)
from tradingagents.strategies.risk_governor import build_risk_snapshot, govern

ALPHA = 0.05


def _fingerprint(scenarios: list) -> str:
    """Stable hash of a scenario list - comparable without a giant diff."""
    payload = json.dumps(scenarios, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _asymmetric_book() -> dict:
    """3-name book: a safe name, a mild name and a name with a hard tail."""
    t = 200
    return {
        "safe": [0.0012 if i % 5 else 0.0015 for i in range(t)],
        "mid": [0.0008 if i % 7 else -0.012 for i in range(t)],
        "risky": [0.002 if i % 4 else -0.08 for i in range(t)],
    }


def _dependent_fat_tail_book() -> dict:
    """Two names sharing a heavy common crash every 6th day (fat, dependent)."""
    t = 150
    return {
        "x": [(-0.06 if i % 6 == 0 else 0.004 + (0.01 if i % 3 else -0.002)) for i in range(t)],
        "y": [(-0.05 if i % 6 == 0 else 0.004 + (0.008 if i % 4 else -0.001)) for i in range(t)],
    }


# ---------------------------------------------------------------------------
# min_cvar_weights
# ---------------------------------------------------------------------------


def test_min_cvar_lowers_cvar_against_equal_weight():
    series = _asymmetric_book()
    current = {"safe": 0.4, "mid": 0.3, "risky": 0.3}
    res = min_cvar_weights(series, alpha=ALPHA, cap=0.5, max_delta=0.15, current=current)
    assert res is not None

    equal = dict.fromkeys(series, 1.0 / 3)
    equal_cvar = cvar(portfolio_returns(equal, series), ALPHA)
    assert equal_cvar is not None
    # cvar is reported as a positive loss fraction, so the optimum is a
    # *smaller* number than the equal-weight loss.
    assert res["cvar"] < -equal_cvar

    assert sum(res["weights"].values()) == pytest.approx(1.0, abs=1e-6)
    for name, w in res["weights"].items():
        assert 0.0 <= w <= 0.5 + 1e-6
        assert abs(w - current[name]) <= 0.15 + 1e-6
    assert res["n"] == 200
    assert res["alpha"] == ALPHA
    assert res["basis"]


def test_min_cvar_respects_the_move_limit():
    series = _asymmetric_book()
    current = {"safe": 0.4, "mid": 0.3, "risky": 0.3}
    res = min_cvar_weights(series, alpha=ALPHA, cap=0.9, max_delta=0.05, current=current)
    assert res is not None
    for name, w in res["weights"].items():
        assert abs(w - current[name]) <= 0.05 + 1e-6
        assert 0.0 <= w <= 0.9 + 1e-6
    assert res["binding"] == "max_delta"


def test_min_cvar_none_below_scenario_floor():
    series = {name: s[:10] for name, s in _asymmetric_book().items()}
    assert min_cvar_weights(series, alpha=ALPHA, cap=0.5) is None
    # The floor is the cause, not the data: the same sample solves with a
    # lower floor and reports the true sample count.
    res = min_cvar_weights(series, alpha=ALPHA, cap=0.5, min_scenarios=5)
    assert res is not None
    assert res["n"] == 10


def test_min_cvar_none_on_degenerate_inputs():
    series = _asymmetric_book()
    assert min_cvar_weights({"safe": series["safe"]}) is None
    assert min_cvar_weights(series, cap=0.0) is None
    assert min_cvar_weights(series, alpha=0.0) is None
    assert min_cvar_weights(series, alpha=1.0) is None
    assert min_cvar_weights(series, cap=float("nan")) is None
    assert min_cvar_weights(series, max_delta=float("inf")) is None


def test_min_cvar_ragged_non_finite_input_does_not_raise():
    series = {
        "a": [0.01, -0.02] * 40,
        "b": [0.0] * 39 + [None] * 5,
        "c": [0.001] * 40 + [float("nan")],
    }
    res = min_cvar_weights(series, cap=0.6, min_scenarios=30)
    assert res is not None
    assert res["n"] == 39  # aligned to the shortest usable series, no raise


# ---------------------------------------------------------------------------
# governor sizing fold
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("size_pct", "cfg"),
    [
        (0.10, {}),
        (0.29, {"max_position_pct": 0.30}),
        (0.60, {"max_position_pct": 0.30}),
        (None, {}),
    ],
)
def test_governor_verdict_unchanged_by_sizing(size_pct, cfg):
    sizing = {"weights": {"safe": 0.5, "mid": 0.35, "risky": 0.15}, "binding": "cap"}
    base = govern(size_pct, cfg)
    with_sizing = govern(size_pct, cfg, sizing=sizing)
    assert with_sizing["verdict"] == base["verdict"]
    assert with_sizing["reasons"] == base["reasons"]
    assert with_sizing.get("touches") == base.get("touches")


def test_governor_halt_and_budget_verdicts_unchanged_by_sizing():
    sizing = {"weights": {}, "cvar": 0.02}
    assert govern(0.05, halted=True)["verdict"] == "REJECT"
    assert govern(0.05, halted=True, sizing=sizing)["verdict"] == "REJECT"
    base = govern(0.05, {"risk_daily_cvar_budget_pct": 0.03}, cvar_pct=0.05)
    sized = govern(0.05, {"risk_daily_cvar_budget_pct": 0.03}, cvar_pct=0.05, sizing=sizing)
    assert base["reasons"] == sized["reasons"]


def test_governor_stores_sizing_verbatim_only_when_supplied():
    sizing = {"weights": {"safe": 1.0}}
    v = govern(0.05, {}, sizing=sizing)
    assert v["sizing"] is sizing
    assert "sizing" not in govern(0.05, {})


def test_snapshot_byte_identical_without_sizing_and_carries_it_when_given():
    verdict = {"verdict": "WARN", "reasons": ["size near cap"]}
    base = build_risk_snapshot(verdict, size_pct=0.28, stop_pct=0.02)
    assert build_risk_snapshot(verdict, size_pct=0.28, stop_pct=0.02, sizing=None) == base
    sized = build_risk_snapshot(
        verdict, size_pct=0.28, stop_pct=0.02, sizing={"binding": "cap"}
    )
    assert sized.startswith(base)
    assert '"binding":"cap"' in sized


# ---------------------------------------------------------------------------
# copula_scenarios
# ---------------------------------------------------------------------------


def test_copula_scenarios_deterministic_from_seed():
    series = _dependent_fat_tail_book()
    a = copula_scenarios(series, n=1500, nu=3, seed=11)
    b = copula_scenarios(series, n=1500, nu=3, seed=11)
    c = copula_scenarios(series, n=1500, nu=3, seed=12)
    assert a is not None and b is not None and c is not None
    assert _fingerprint(a["scenarios"]) == _fingerprint(b["scenarios"])
    assert _fingerprint(a["scenarios"]) != _fingerprint(c["scenarios"])
    assert len(a["scenarios"]) == 1500
    assert set(a["scenarios"][0]) == {"x", "y"}


def test_copula_scenarios_stay_inside_the_empirical_marginals():
    series = _dependent_fat_tail_book()
    res = copula_scenarios(series, n=500, seed=3)
    assert res is not None
    for name, sample in series.items():
        lo, hi = min(sample), max(sample)
        for row in res["scenarios"]:
            assert lo - 1e-12 <= row[name] <= hi + 1e-12


def test_copula_tail_dependence_ordering():
    series = _dependent_fat_tail_book()
    t_cop = copula_scenarios(series, n=2000, nu=3, family="t", seed=7)
    gauss = copula_scenarios(series, n=2000, family="gaussian", seed=7)
    indep = copula_scenarios(series, n=2000, family="independent", seed=7)
    assert t_cop is not None and gauss is not None and indep is not None

    q = t_cop["tail_dependence"]["quantile"]
    t_agg = t_cop["tail_dependence"]["aggregate"]
    g_agg = gauss["tail_dependence"]["aggregate"]
    i_agg = indep["tail_dependence"]["aggregate"]
    # Low-nu t copula: joint lower tails; Gaussian: none asymptotically;
    # independence: the unconditional baseline q.
    assert t_agg > g_agg > i_agg
    assert i_agg < 0.15
    assert t_agg > q
    assert t_cop["nu"] == 3
    assert indep["nu"] is None


def test_copula_scenarios_none_on_degenerate_input():
    assert copula_scenarios({}) is None
    assert copula_scenarios({"a": [0.01] * 30}) is None
    assert copula_scenarios({"a": [0.01], "b": [0.02]}) is None
    assert copula_scenarios({"a": [0.01] * 30, "b": [0.02] * 30}, family="bogus") is None
