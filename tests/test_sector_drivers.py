"""The sector -> macro-driver mapping (strategies/sector_drivers.py).

Item 5 of the playbook survey: every input the "has the catalyst changed?" check
needs was already live in the engine, but nothing bound a sector to the series
that drives it. These tests pin the binding's completeness, the sign convention,
and the rule that an unread series reads ``None`` rather than ``False`` - a
signal nobody measured has not failed a sign test.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.sector_drivers import (
    KNOWN_DRIVERS,
    SECTOR_DRIVERS,
    UNMAPPED_REASONS,
    _driver_change_read,
    driver_aliases,
    sector_driver_read,
)
from tradingagents.strategies.sector_rank import SPDR_SECTORS

pytestmark = pytest.mark.timeout(60)


def _series(n: int, *, start: float = 1.0, step: float = 0.0) -> list:
    return [start + step * i for i in range(n)]


def test_every_spdr_sector_is_mapped_or_has_a_stated_reason():
    """A sector cannot fall through silently: either it has a driver, or the
    engine says why it does not."""
    for sector in SPDR_SECTORS:
        assert sector in SECTOR_DRIVERS or sector in UNMAPPED_REASONS, sector


def test_the_mapping_names_only_drivers_the_engine_can_fetch():
    """A typo would otherwise read as 'unmapped' and never be noticed."""
    for sector, (driver, direction) in SECTOR_DRIVERS.items():
        assert driver in KNOWN_DRIVERS, (sector, driver)
        assert direction in (-1, 1), (sector, direction)
    assert set(driver_aliases()) == {d for d, _ in SECTOR_DRIVERS.values()}


def test_the_change_read_counts_observations_not_days():
    """Windows are observations because FRED frequency varies by series."""
    flat_then_up = _series(80, start=1.0) + [2.0]
    read = _driver_change_read(flat_then_up)
    assert read["observations"] == 81
    assert read["level"] == 2.0
    assert read["change_1m"] == pytest.approx(1.0)
    assert read["change_3m"] == pytest.approx(1.0)


def test_an_unmeasured_window_is_none_never_zero():
    """21 observations cannot produce a 21-observation change."""
    short = _driver_change_read(_series(10, start=1.0, step=0.1))
    assert short["observations"] == 10
    assert short["level"] == pytest.approx(1.9)
    assert short["change_1m"] is None and short["change_3m"] is None
    assert _driver_change_read([])["level"] is None


def test_the_sign_convention_is_the_documented_one():
    """Rates up HURTS the duration sectors and HELPS nobody mapped that way;
    oil up helps energy; a steeper curve helps financials."""
    rising_rates = {"10y_treasury": _series(80, start=4.0, step=0.01)}
    tech = sector_driver_read("XLK", rising_rates)
    assert tech["driver"] == "10y_treasury" and tech["direction"] == -1
    assert tech["favourable_3m"] is False

    falling_rates = {"10y_treasury": _series(80, start=5.0, step=-0.01)}
    assert sector_driver_read("XLU", falling_rates)["favourable_3m"] is True

    rising_oil = {"wti": _series(80, start=60.0, step=0.5)}
    energy = sector_driver_read("XLE", rising_oil)
    assert energy["driver"] == "wti" and energy["favourable_3m"] is True

    steeper = {"10y_2y_spread": _series(80, start=-0.5, step=0.02)}
    banks = sector_driver_read("XLF", steeper)
    assert banks["driver"] == "10y_2y_spread" and banks["favourable_3m"] is True

    flat = {"10y_treasury": _series(80, start=4.0)}
    zero = sector_driver_read("XLK", flat)
    assert zero["favourable_3m"] is False  # a flat move fails the sign test


def test_a_series_nobody_read_is_none_not_a_failed_sign_test():
    """The mapping exists but the fetch did not: unmeasured, never 'no'."""
    missing = sector_driver_read("XLK", {})
    assert missing["mapped"] is True
    assert missing["level"] is None and missing["change_1m"] is None
    assert missing["favourable_1m"] is None and missing["favourable_3m"] is None
    assert missing["observations"] == 0
    assert "0 observation" in missing["basis"]


def test_an_unmapped_sector_says_why_instead_of_borrowing_a_series():
    xlv = sector_driver_read("XLV", {"hy_oas": _series(80, step=0.1)})
    assert xlv["mapped"] is False and xlv["driver"] is None
    assert xlv["favourable_3m"] is None
    assert "defensive demand" in xlv["unmapped_reason"]
    assert xlv["unmapped_reason"] in xlv["basis"]


def test_the_basis_names_the_observation_count_and_the_direction():
    read = sector_driver_read("XLE", {"wti": _series(80, start=60.0, step=0.5)})
    assert "80 observation" in read["basis"]
    assert "up helps XLE" in read["basis"]
