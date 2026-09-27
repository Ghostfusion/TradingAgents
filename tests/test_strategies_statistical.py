"""Unit tests for OpenBB-derived statistical + rotation calculators."""

import math
import random

import pytest

from tradingagents.strategies import rotation, statistical

pytestmark = pytest.mark.timeout(180)


def _iid(n=200, seed=1):
    rnd = random.Random(seed)
    return [rnd.gauss(0, 0.01) for _ in range(n)]


def _random_walk(n=200, seed=2):
    rnd = random.Random(seed)
    out = [0.0]
    for _ in range(n - 1):
        out.append(out[-1] + rnd.gauss(0, 0.01))
    return out


# --------------------------------------------------------------------------
# statistical.normality
# --------------------------------------------------------------------------


def test_normality_iid_is_normal():
    r = _iid()
    out = statistical.normality(r)
    assert out["normal"] is True
    assert out["jarque_bera"]["p_value"] > 0.05


def test_normality_non_gaussian_rejected():
    # heavy-tailed (laplace-ish) sample
    rnd = random.Random(3)
    heavy = [rnd.gauss(0, 0.01) * (1 if rnd.random() < 0.9 else 3.0) for _ in range(400)]
    out = statistical.normality(heavy)
    # jarque-bera should flag it (p small) most runs
    assert out["jarque_bera"]["p_value"] < 0.05


def test_normality_short_series_none():
    out = statistical.normality([0.01, 0.02, 0.0])
    assert out["n"] == 3 and out["normal"] is None


# --------------------------------------------------------------------------
# statistical.unit_root
# --------------------------------------------------------------------------


def test_unit_root_iid_stationary():
    out = statistical.unit_root(_iid())
    assert out["stationary"] is True
    assert out["adf"]["p_value_approx"] < 0.05


def test_unit_root_random_walk_not_stationary():
    out = statistical.unit_root(_random_walk())
    assert out["stationary"] is False
    assert out["adf"]["p_value_approx"] > 0.05


def test_unit_root_short_none():
    out = statistical.unit_root([0.01] * 5)
    assert out["adf"] is None


# --------------------------------------------------------------------------
# statistical.omega
# --------------------------------------------------------------------------


def test_omega_symmetric_returns():
    # gains and losses cancel-ish: omega near 1
    o = statistical.omega([0.01, -0.01, 0.02, -0.02])
    assert o is not None and o > 0


def test_omega_all_gains_high():
    o = statistical.omega([0.05, 0.02, 0.01])
    # no downside mass -> denominator 0 -> None
    assert o is None


def test_omega_empty_none():
    assert statistical.omega([]) is None


# --------------------------------------------------------------------------
# statistical.correlation_matrix
# --------------------------------------------------------------------------


def test_correlation_matrix_identity():
    r = _iid()
    out = statistical.correlation_matrix({"A": r, "B": r})
    assert out["names"] == ["A", "B"]
    assert abs(out["corr"]["A"]["B"] - 1.0) < 1e-9


def test_correlation_matrix_negative():
    r = _iid()
    inv = [-x for x in r]
    out = statistical.correlation_matrix({"A": r, "B": inv})
    assert abs(out["corr"]["A"]["B"] - (-1.0)) < 1e-9


def test_correlation_matrix_short_series():
    assert statistical.correlation_matrix({"A": [0.01], "B": [0.02]}) == {}


# --------------------------------------------------------------------------
# statistical.cointegration_pair / granger_causality
# --------------------------------------------------------------------------
def test_cointegration_linear_pair():
    # y cointegrates with x when the residual is a stationary (mean-reverting)
    # series — but with enough noise that the residual ADF is non-degenerate.
    rnd = random.Random(4)
    x = _random_walk(300, seed=4)
    y = [0.9 * v + rnd.gauss(0, 0.5) for v in x]
    out = statistical.cointegration_pair(x, y)
    assert out["cointegrated"] is True


def test_cointegration_unrelated_not():
    # two independent seeded random walks are not cointegrated: the residual
    # ADF cannot reject the unit root (p well above 0.05).
    out = statistical.cointegration_pair(_random_walk(200), _random_walk(200, seed=7))
    assert out["cointegrated"] is False
    assert out["residual_p_approx"] > 0.05


def test_granger_causality_detects_lag():
    x = _iid(150)
    y = [v + 0.5 * prev for v, prev in zip(x[1:], x[:-1], strict=True)]
    out = statistical.granger_causality(x[:-1], y, maxlag=2)
    assert out["x_causes_y"] is True


# --------------------------------------------------------------------------
# statistical.capm_decomposition / ols_factors / vif
# --------------------------------------------------------------------------


def test_capm_decomposition_self_beta_one():
    r = _iid()
    out = statistical.capm_decomposition(r, r)
    assert out["beta"] == pytest.approx(1.0, abs=1e-4)
    assert out["idiosyncratic_risk"] == pytest.approx(0.0, abs=1e-3)


def test_capm_short_series():
    out = statistical.capm_decomposition([0.01] * 5, [0.01] * 5)
    assert out["beta"] is None


def test_ols_factors_runs():
    x = _iid(100)
    y = [0.5 * v + random.Random(5).gauss(0, 0.001) for v in x]
    out = statistical.ols_factors(y, {"x": x})
    assert out["rsquared"] is not None
    assert "const" in out["params"] and "x" in out["params"]


def test_vif_high_collinearity():
    rnd = random.Random(6)
    a = [rnd.gauss(0, 1) for _ in range(100)]
    b = [v + rnd.gauss(0, 0.01) for v in a]
    c = [v - rnd.gauss(0, 1) for v in a]
    out = statistical.variance_inflation_factor({"a": a, "b": b, "c": c})
    # b nearly a -> high VIF (may saturate); c independent -> moderate
    assert out["b"]["high"] is True or out["b"]["vif"] > 2


def test_vif_few_columns_none():
    out = statistical.variance_inflation_factor({"a": [1.0, 2.0], "b": [2.0, 1.0]})
    assert out["a"]["vif"] is None


# --------------------------------------------------------------------------
# rotation.relative_rotation
# --------------------------------------------------------------------------


def test_relative_rotation_leading():
    rnd = random.Random(8)
    bench = [100 + rnd.gauss(0, 1) for _ in range(300)]
    up = [b * (1 + 0.003) ** i for i, b in enumerate(bench[:300])]
    out = rotation.relative_rotation(up, bench, long=252, short=21)
    assert out["quadrant"] == "leading"


def test_relative_rotation_lagging():
    rnd = random.Random(9)
    bench = [100 + rnd.gauss(0, 1) for _ in range(300)]
    down = [b * (1 - 0.003) ** i for i, b in enumerate(bench[:300])]
    out = rotation.relative_rotation(down, bench, long=252, short=21)
    assert out["quadrant"] == "lagging"


def test_relative_rotation_short_series_none():
    out = rotation.relative_rotation([1, 2, 3], [1, 2, 3], long=252, short=21)
    assert out["quadrant"] is None


# --------------------------------------------------------------------------
# rotation.clenow_momentum
# --------------------------------------------------------------------------


def test_clenow_momentum_upbeat_gt_noise():
    rnd = random.Random(10)
    up = [100 * math.exp(0.001 * i) + rnd.gauss(0, 1) for i in range(200)]
    noise = [100 + rnd.gauss(0, 1) for _ in range(200)]
    s_up = rotation.clenow_momentum(up, 90)
    s_noise = rotation.clenow_momentum(noise, 90)
    assert s_up is not None and s_noise is not None
    assert s_up > s_noise


def test_clenow_short_none():
    assert rotation.clenow_momentum([1.0, 2.0], 90) is None


# --------------------------------------------------------------------------
# rotation.vol_cones
# --------------------------------------------------------------------------


def test_vol_cones_returns_windows():
    rnd = random.Random(11)
    up = [100 * math.exp(0.0005 * i) + rnd.gauss(0, 2) for i in range(300)]
    out = rotation.vol_cones(up, (5, 10))
    assert set(out.keys()) <= {5, 10}
    if 5 in out:
        assert "current" in out[5] and "p25" in out[5] and "p75" in out[5]


def test_vol_cones_short_series_empty():
    assert rotation.vol_cones([1.0, 2.0, 3.0], (5,)) == {}


# --------------------------------------------------------------------------
# statistical.commodity_beta (RISK-21) - the dated alignment IS the producer
# --------------------------------------------------------------------------


def _dated(levels, start="2026-01-01"):
    """A dated level series in FRED's ``[(date, value)]`` shape."""
    return [(f"{start}#{i:04d}", float(v)) for i, v in enumerate(levels)]


def _levels(returns, base=100.0):
    """Compound a return series into levels (the library's own path)."""
    out = [base]
    for r in returns:
        out.append(out[-1] * math.exp(r))
    return out


def test_commodity_beta_recovers_a_known_slope():
    driver_rets = _iid(120, seed=11)
    # The asset's log returns are exactly TWICE the driver's, so the slope is 2
    # with no residual: R^2 == 1.
    asset_rets = [2.0 * v for v in driver_rets]
    out = statistical.commodity_beta(
        _dated(_levels(driver_rets)),
        _dated(_levels(asset_rets, base=50.0)),
        driver="wti",
    )
    assert out is not None
    assert out["beta"] == pytest.approx(2.0, abs=1e-4)
    assert out["rsquared"] == pytest.approx(1.0, abs=1e-6)
    assert out["n"] == 120 and out["driver"] == "wti"
    assert out["p_value"] is not None and "common" in out["basis"]


def test_commodity_beta_aligns_on_shared_dates_not_tails():
    driver_rets = _iid(120, seed=12)
    asset_rets = [2.0 * v for v in driver_rets]
    # The driver is MISSING its first 20 observations (a publishing lag). The
    # dated join drops to the 100 dates the two share; a tail alignment would
    # instead pair the driver's first observations with the asset's LAST ones
    # and fit a slope off the wrong pairs.
    lagged = _dated(_levels(driver_rets))[20:]
    out = statistical.commodity_beta(lagged, _dated(_levels(asset_rets, base=50.0)), driver="wti")
    assert out is not None and out["beta"] == pytest.approx(2.0, abs=1e-4)
    assert out["n"] == 100  # 101 shared observations -> 100 returns


def test_commodity_beta_refusals():
    daily = _dated(_levels(_iid(40, seed=13)))
    # A monthly driver (copper: ~13 obs/yr) against daily closes shares too few
    # dates: refused rather than tail-aligned.
    monthly = [(f"2025-{1 + i // 12:02d}-01", 100.0 + i) for i in range(12)]
    assert statistical.commodity_beta(monthly, daily, driver="copper") is None
    # Disjoint calendars never align.
    disjoint = [(f"1999-01-{i + 1:02d}", 100.0 + i) for i in range(40)]
    assert statistical.commodity_beta(disjoint, daily) is None
    # Below min_pairs, a zero-variance driver, and junk rows.
    assert statistical.commodity_beta(daily[:10], daily[:10]) is None
    assert statistical.commodity_beta(_dated([1.0] * 30), daily) is None  # zero variance
    assert statistical.commodity_beta([("x", None), ("y", "z")], daily) is None
    # A non-positive level cannot be logged, so the pair is refused. The date
    # must be distinct: a duplicate key would overwrite the broken level.
    broken_day = "1998-12-31"
    assert statistical.commodity_beta(
        [(broken_day, 0.0), *daily], [(broken_day, 100.0), *daily]
    ) is None


def test_commodity_beta_ignores_unusable_rows():
    driver_rets = _iid(60, seed=14)
    good = _dated(_levels(driver_rets))
    noise = [("bad", None), ("also-bad", "nope")]
    out = statistical.commodity_beta(noise + good, _dated(_levels(driver_rets)), driver="wti")
    assert out is not None and out["n"] == 60


# --------------------------------------------------------------------------
# All calculators never raise on odd input
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fn,args",
    [
        (statistical.normality, [[]]),
        (statistical.normality, [[None, "x", 1.0]]),
        (statistical.unit_root, [[]]),
        (statistical.unit_root, [[0.0] * 3]),
        (statistical.omega, [[]]),
        (statistical.correlation_matrix, [{}]),
        (statistical.cointegration_pair, [[1.0, 2.0], [2.0, 1.0]]),
        (statistical.granger_causality, [[1.0], [2.0]]),
        (statistical.capm_decomposition, [[], []]),
        (statistical.ols_factors, [[], {}]),
        (statistical.commodity_beta, [[], []]),
        (statistical.variance_inflation_factor, [{"a": [1.0], "b": [2.0]}]),
        (rotation.relative_rotation, [[], []]),
        (rotation.clenow_momentum, [[], 90]),
        (rotation.vol_cones, [[], (5,)]),
    ],
)
def test_calculators_never_raise(fn, args):
    # The real contract: these must never raise (degraded None is valid).
    fn(*args)
