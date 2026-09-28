"""CAPE (Shiller P/E) - VAL-16's arithmetic over the deflated EPS window."""

import pytest

from tradingagents.strategies.cape import (
    CAPE_MIN_YEARS,
    CAPE_YEARS,
    cape_band,
    cape_ratio,
)

pytestmark = pytest.mark.timeout(600)


def _flat_cpi(years, value=100.0):
    return [(f"{y}-12-31", value) for y in years]


def _ten_years(start=2015, eps=10.0):
    return [(f"{y}-12-31", eps) for y in range(start, start + CAPE_YEARS)]


def test_flat_cpi_gives_the_nominal_pe():
    """With a constant deflator the real window equals the nominal one."""
    out = cape_ratio(100.0, _ten_years(), _flat_cpi(range(2015, 2026)))
    assert out["cape"] == pytest.approx(10.0)
    assert out["years_used"] == CAPE_YEARS
    assert out["reason"] is None
    assert out["window"] == ("2015-12-31", "2024-12-31")


def test_inflation_lowers_cape_below_the_nominal_pe():
    """Older nominal EPS inflate into today's dollars, so CAPE < P/E."""
    cpi = [(f"{y}-12-31", 100.0 + 10.0 * (y - 2015)) for y in range(2015, 2026)]
    out = cape_ratio(100.0, _ten_years(), cpi)
    assert out["mean_real_eps"] > 10.0
    assert out["cape"] < 10.0


def test_the_deflation_base_cancels():
    """CAPE is invariant to a uniform rescaling of the CPI level."""
    years = list(range(2015, 2026))
    one = cape_ratio(100.0, _ten_years(), _flat_cpi(years, 100.0))
    two = cape_ratio(100.0, _ten_years(), _flat_cpi(years, 260.0))
    assert one["cape"] == two["cape"]


def test_short_window_is_absent_with_a_reason():
    """Five usable years is under the floor: no CAPE, and the reason says so.

    Note the window is shortened by having FEW EPS points, not by dating them
    late: a period with no later CPI still deflates against the last CPI at or
    before it, so moving the dates does not shrink coverage.
    """
    out = cape_ratio(100.0, _ten_years(start=2021)[:5], _flat_cpi(range(2015, 2026)))
    assert out["cape"] is None
    assert out["years_used"] == 5
    assert str(CAPE_MIN_YEARS) in out["reason"]


def test_non_positive_mean_real_eps_is_absent_not_negative():
    """A loss-making window cannot yield a ratio; it yields a reason."""
    out = cape_ratio(100.0, _ten_years(eps=-3.0), _flat_cpi(range(2015, 2026)))
    assert out["cape"] is None
    assert "non-positive mean real EPS" in out["reason"]


def test_no_deflator_for_the_periods_is_absent():
    """EPS with no overlapping CPI is unmeasurable, not zero."""
    later_cpi = [(f"{y}-12-31", 100.0) for y in range(2030, 2040)]
    out = cape_ratio(100.0, _ten_years(), later_cpi)
    assert out["cape"] is None
    assert out["years_used"] == 0
    assert "overlaps a CPI observation" in out["reason"]


@pytest.mark.parametrize("bad", [None, "x", 0, -1.0])
def test_bad_price_is_absent(bad):
    out = cape_ratio(bad, _ten_years(), _flat_cpi(range(2015, 2026)))
    assert out["cape"] is None
    assert out["reason"]


def test_no_cpi_series_is_absent():
    out = cape_ratio(100.0, _ten_years(), [])
    assert out["cape"] is None
    assert out["reason"] == "no CPI series"


def test_bare_year_dates_are_accepted():
    """A year-only period end is read as December, not rejected."""
    out = cape_ratio(100.0, [(y, 10.0) for y in range(2015, 2025)],
                     _flat_cpi(range(2015, 2026)))
    assert out["cape"] == pytest.approx(10.0)


@pytest.mark.parametrize("cape,expected", [
    (None, "n/a"), (10.0, "low"), (15.0, "moderate"), (24.9, "moderate"),
    (25.0, "elevated"), (44.0, "stretched"),
])
def test_bands(cape, expected):
    assert cape_band(cape) == expected
