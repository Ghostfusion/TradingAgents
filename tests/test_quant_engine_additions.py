"""Quant-engine additions tests (HRP / 12-1 momentum / industry-neutral z)."""

import pytest

from tradingagents.strategies.cross_section import industry_neutral_z
from tradingagents.strategies.hierarchical_risk_parity import hrp_weights
from tradingagents.strategies.momentum import momentum_12_1
from tradingagents.strategies.statistical import omega

pytestmark = pytest.mark.timeout(60)


def _returns(steps: dict, n: int = 120) -> dict:
    out = {}
    for name, step in steps.items():
        out[name] = [step] * n  # flat-ish series per name
    return out


def test_hrp_weights_sum_to_one_and_names():
    r = _returns({"A": 0.001, "B": 0.001, "C": 0.001, "D": 0.001})
    out = hrp_weights(r)
    assert out["weights"]
    assert abs(sum(out["weights"].values()) - 1.0) < 1e-6
    assert set(out["order"]) == {"A", "B", "C", "D"}


def test_hrp_correlated_pair_cluster_adjacent():
    # A/B highly correlated (identical series), C/D less so -> A & B adjacent
    # in the HRP order.
    a = [0.001 + i * 1e-5 for i in range(120)]
    b = [0.001 + i * 1e-5 for i in range(120)]  # = A
    c = [-0.0005 + i * 1e-5 for i in range(120)]
    d = [0.0003 + (i % 7) * 1e-5 for i in range(120)]
    out = hrp_weights({"A": a, "B": b, "C": c, "D": d})
    order = out["order"]
    assert abs(order.index("A") - order.index("B")) == 1  # adjacent
    assert "hierarchical" in out["note"]


def test_hrp_degrades_equal_on_bad_cov():
    out = hrp_weights({"A": [0.001] * 30, "B": [0.001] * 10})  # unaligned/short
    assert out["weights"]
    assert "equal-weight" in out["note"]


def test_hrp_no_names_empty():
    assert hrp_weights({})["weights"] == {}


def test_momentum_12_1_skips_last_month():
    # 300 rising closes: base ~13mo ago < ref ~1mo ago -> positive momentum.
    closes = [100.0 + i for i in range(300)]
    m = momentum_12_1(closes)
    assert m is not None and m > 0
    # manual: ref = closes[-21]; base = closes[-21-252-1]
    ref = closes[-21]
    base = closes[-21 - 252 - 1]
    assert m == round(ref / base - 1.0, 6)


def test_momentum_12_1_requires_bars():
    assert momentum_12_1([100.0] * 200) is None  # < 274 bars
    assert momentum_12_1([]) is None
    assert momentum_12_1([100.0] * 280) is not None


def test_industry_neutral_z_removes_sector_effect():
    # Two sectors; the sector-2 values are systematically lower, but after
    # demeaning the cross-sectional z has zero sector bias.
    values = [10.0, 11.0, 12.0, 1.0, 2.0, 3.0]
    sector = {0: "Tech", 1: "Tech", 2: "Tech", 3: "Staples", 4: "Staples", 5: "Staples"}
    out = industry_neutral_z(values, sector)
    assert out is not None
    z = out["z"]
    assert len(z) == 6
    # mean of neutralized z ~ 0 (cross-sectional), sectors balanced:
    assert abs(sum(x for x in z if x is not None)) < 1e-6


def test_industry_neutral_z_two_values_valid():
    # 2 demeaned values are enough to z-score (std > 0); returns a dict.
    out = industry_neutral_z([1.0, 2.0], {0: "A", 1: "A"})
    assert out is not None and len(out["z"]) == 2


def test_omega_ratio_existing_statistical():
    # Existing statistical.omega is the Omega source; sanity-pin it.
    o = omega([1.0, 2.0, -1.0])
    assert o is not None and o > 1.0
    assert omega([1.0, 1.0]) is None  # no losses -> +inf -> None (n/a)


def test_strategy_quality_render_includes_omega(monkeypatch):
    # get_strategy_quality now surfaces omega; monkeypatch _ohlcv so no
    # vendor call, assert the omega token appears.
    from tradingagents.agents.utils import analysis_tools as T

    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": _up(200)})
    tool = next(t for t in T.__dict__.values()
                if getattr(t, "name", None) == "get_strategy_quality")
    out = tool.invoke({"ticker": "AAPL"})
    assert "omega=" in out


def _up(start: float = 100.0, step: float = 0.5, n: int = 200) -> list:
    return [start + step * i for i in range(n)]
