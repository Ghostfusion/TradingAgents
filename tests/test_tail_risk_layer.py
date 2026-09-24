"""K1 (2604.08765): a tail number that carries its quality and its uncertainty.

The one-directional rule is the test: input quality and estimation uncertainty
may WIDEN the band or WITHHOLD the number, never narrow it. A red quality
verdict is ``unavailable`` rather than a number, the breach rate travels with
the number, and the coverage test lands beside it.

Offline and deterministic: synthetic returns under a fixed seed.
"""

from __future__ import annotations

import numpy as np
import pytest

from tradingagents.dataflows.config import get_config, reset_config, set_config
from tradingagents.strategies.tail_risk import tail_risk

QUALITY_KEYS = ("price", "volume", "fundamentals", "news", "options", "macro")


@pytest.fixture(autouse=True)
def _gate_on():
    saved = dict(get_config() or {})
    set_config({**saved, "enable_tail_risk_layer": True})
    yield
    reset_config()


def _returns(n: int = 300, seed: int = 11) -> list[float]:
    rng = np.random.default_rng(seed)
    return [float(x) for x in rng.normal(0.0004, 0.012, n)]


def _quality(score: float) -> dict:
    return dict.fromkeys(QUALITY_KEYS, float(score))


def test_quality_only_widens():
    """A monotonically worsening quality input yields a NON-DECREASING band width.

    Status moves ``ok`` -> ``widened`` -> ``unavailable``, and no input ever
    narrows the band.
    """
    rets = _returns()
    widths, statuses, vars_ = [], [], []
    for q in (95.0, 85.0, 80.0, 75.0, 70.0, 65.0, 55.0, 40.0):
        res = tail_risk(rets, _quality(q))
        assert res["band"] is not None
        widths.append(res["band"]["width"])
        statuses.append(res["status"])
        vars_.append(res["var"])

    assert all(widths[i] <= widths[i + 1] + 1e-12 for i in range(len(widths) - 1))
    assert statuses[0] == "ok"
    assert "widened" in statuses
    assert statuses[-1] == "unavailable"
    rank = {"ok": 0, "widened": 1, "unavailable": 2}
    assert [rank[s] for s in statuses] == sorted(rank[s] for s in statuses)

    # the published number only ever moves OUTWARD (more negative), then is withheld
    measured = [v for v in vars_ if v is not None]
    assert all(measured[i] >= measured[i + 1] for i in range(len(measured) - 1))
    assert vars_[-1] is None

    # the uncertainty term is present and the breach rate travels with the number
    clean = tail_risk(rets, _quality(95.0))
    assert clean["uncertainty"]["score"] >= 0.0
    assert clean["breach_rate"] is not None
    assert clean["band"]["width"] < tail_risk(rets, _quality(65.0))["band"]["width"]


def test_a_red_quality_verdict_is_unavailable_rather_than_a_number():
    res = tail_risk(_returns(), _quality(40.0))
    assert res["status"] == "unavailable"
    assert res["var"] is None and res["cvar"] is None
    assert res["q_score"] == pytest.approx(40.0)


def test_no_measured_quality_is_refused():
    res = tail_risk(_returns(), {})
    assert res["status"] == "unavailable"
    assert res["q_score"] is None
    assert res["var"] is None


def test_the_gate_off_read_is_refused():
    saved = dict(get_config() or {})
    set_config({**saved, "enable_tail_risk_layer": False})
    try:
        res = tail_risk(_returns(), _quality(95.0))
        assert res["status"] == "unavailable"
        assert res["var"] is None
        assert "enable_tail_risk_layer is off" in res["basis"]
    finally:
        set_config(saved)


def test_ensemble_dispersion_needs_at_least_two_members():
    rets = _returns()
    rng = np.random.default_rng(2)
    one = tail_risk(rets, _quality(95.0),
                    members=[list(rng.normal(0.0, 0.01, 200))])
    assert one["uncertainty"]["members"] == 1
    assert one["uncertainty"]["dispersion"] is None      # never 0 for one member

    two = tail_risk(rets, _quality(95.0),
                    members=[list(rng.normal(0.0, 0.01, 200)),
                             list(rng.normal(0.0, 0.03, 200))])
    assert two["uncertainty"]["members"] == 2
    assert two["uncertainty"]["dispersion"] is not None
    assert two["uncertainty"]["dispersion"] > 0.0


def test_the_coverage_test_and_the_breach_rate_land_with_the_number():
    res = tail_risk(_returns(), _quality(95.0))
    cov = res["coverage"]
    assert {"kupiec", "christoffersen", "verdict", "n", "coverage_level",
            "window"} <= set(cov)
    assert cov["window"]["min_window"] > 0
    assert cov["coverage_level"] == pytest.approx(0.95)
    assert res["breach_rate"] == cov["kupiec"]["hit_rate"]


def test_a_thin_series_is_refused():
    res = tail_risk([0.01, -0.02, 0.005], _quality(95.0))
    assert res["status"] == "unavailable"
    assert res["var"] is None


def test_risk_score_declares_the_tail_layer_as_printed_only():
    """K1's consumer: PRINTED beside the score, never scored by it.

    ``tests/test_risk_score.py`` pins the correlation category at exactly 2
    scored components, so the layer lands as a printed-only row (R3/R7
    precedent) - it cannot move a scored count.
    """
    from tradingagents.strategies.risk_score import (
        COMPONENTS,
        PRINTED,
        SCORED,
        align_components,
        risk_score,
    )

    comp = COMPONENTS["tail_risk"]
    assert comp.kind == PRINTED
    assert comp.category == "tail"
    assert comp.producer.startswith("tail_risk.tail_risk:")
    tail_scored = [n for n, c in COMPONENTS.items()
                   if c.category == "tail" and c.kind == SCORED]
    assert tail_scored == ["cvar", "portfolio_cvar", "stress_loss", "es_pct",
                           "extreme_quantile_es"]

    vals = {"cvar": -0.03, "portfolio_cvar": -0.035, "stress_loss": 0.03,
            "es_pct": 0.04, "extreme_quantile_es": -0.05, "tail_risk": -0.02}
    rows = align_components(vals)
    assert rows["tail_risk"]["aligned"] is None
    assert "tail_risk" in risk_score(vals)["printed"]
