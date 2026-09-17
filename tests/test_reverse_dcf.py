"""Reverse-DCF (price-implied valuation) unit tests — pure/offline.

Reference case: MSFT 2026-09-16 — price 490.30, shares 7_567_453_176.4,
wacc 0.10, cash 76_651_000_000, debt 56_826_000_000, current FCF 66_980_000_000.
The straight-line DCF printed ~$124.80/share against this price and the write-up
labelled the gap a "modeling artifact"; these tests pin what the price actually
implies. All figures are hand-computed from the shared perpetuity convention
``FCF*(1+g)/(wacc-g) + net_cash``.
"""

import json

import pytest

from tradingagents.strategies.reverse_dcf import (
    implied_growth_for_fcf,
    reverse_dcf,
)

MSFT_PRICE = 490.30
MSFT_SHARES = 7_567_453_176.4
MSFT_WACC = 0.10
MSFT_CASH = 76_651_000_000
MSFT_DEBT = 56_826_000_000
MSFT_FCF = 66_980_000_000
MSFT_NET_CASH = MSFT_CASH - MSFT_DEBT

# Stated acceptance tolerance for the hand-computed implied-FCF figures.
REL_TOL = 0.01


def _msft(**overrides) -> dict:
    kwargs = {
        "market_price": MSFT_PRICE,
        "shares": MSFT_SHARES,
        "wacc": MSFT_WACC,
        "current_fcf": MSFT_FCF,
        "cash": MSFT_CASH,
        "debt": MSFT_DEBT,
    }
    kwargs.update(overrides)
    return reverse_dcf(**kwargs)


def _row(result: dict, g: float) -> dict:
    return {round(r["g"], 6): r for r in result["rows"]}[g]


def _forward_fv(g: float, fcf: float = MSFT_FCF) -> float:
    """Independent forward valuation, matching the dcf.py convention."""
    return (fcf * (1.0 + g) / (MSFT_WACC - g) + MSFT_NET_CASH) / MSFT_SHARES


@pytest.mark.unit
class TestPriceImpliedFcf:
    def test_implied_fcf_at_three_growth_rates(self):
        # tolerance: 1% relative (REL_TOL) against hand-computed MSFT values.
        r = _msft()
        assert r["usable"] is True
        assert _row(r, 0.025)["implied_fcf"] == pytest.approx(271.5e9, rel=REL_TOL)
        assert _row(r, 0.05)["implied_fcf"] == pytest.approx(176.7e9, rel=REL_TOL)
        assert _row(r, 0.07)["implied_fcf"] == pytest.approx(104.0e9, rel=REL_TOL)

    def test_implied_multiple_is_price_over_implied_fcf_per_share(self):
        r = _msft()
        row = _row(r, 0.025)
        expected = MSFT_PRICE / (271.5e9 / MSFT_SHARES)
        assert row["implied_multiple"] == pytest.approx(expected, rel=REL_TOL)
        assert row["implied_multiple"] == pytest.approx(
            MSFT_PRICE / row["implied_fcf_per_share"], rel=1e-12
        )

    def test_implied_fcf_strictly_decreases_as_growth_rises(self):
        # More growth allowed per unit of FCF -> less steady-state FCF required.
        r = _msft()
        implied = [row["implied_fcf"] for row in r["rows"]]
        assert len(implied) > 1
        assert all(later < earlier for earlier, later in zip(implied, implied[1:]))

    def test_rows_round_trip_back_to_the_price(self):
        # Each row, fed forward through the shared convention, must reproduce
        # the observed price: implied_fcf and g are one consistent answer.
        r = _msft()
        assert r["rows"]
        for row in r["rows"]:
            fv = (row["implied_fcf"] * (1.0 + row["g"]) / (MSFT_WACC - row["g"])
                  + MSFT_NET_CASH) / MSFT_SHARES
            assert fv == pytest.approx(MSFT_PRICE, rel=1e-9)

    def test_growth_at_or_above_wacc_is_never_emitted(self):
        r = _msft(growths=(0.03, 0.10, 0.15))
        assert [row["g"] for row in r["rows"]] == [0.03]
        assert all(row["g"] < MSFT_WACC for row in r["rows"])

    def test_model_fv_uses_the_forward_convention(self):
        r = _msft()
        row = _row(r, 0.04)
        assert row["model_fv_at_current_fcf"] == pytest.approx(
            _forward_fv(0.04), rel=1e-9
        )

    def test_model_fv_and_crossing_are_none_without_current_fcf(self):
        r = _msft(current_fcf=None)
        assert r["usable"] is True
        assert all(row["model_fv_at_current_fcf"] is None for row in r["rows"])
        assert r["crossing_g"] is None

    def test_result_is_json_serialisable(self):
        json.dumps(_msft())
        json.dumps(_msft(market_price=None))


@pytest.mark.unit
class TestCrossingGrowth:
    def test_crossing_g_needs_about_8pct_perpetual_growth(self):
        r = _msft()
        cg = r["crossing_g"]
        assert cg is not None
        assert cg == pytest.approx(0.0804, abs=0.002)
        # Strictly inside the searched interval: above every probed growth and
        # below the WACC bound.
        assert 0.07 < cg < MSFT_WACC
        # The forward model at the crossing reproduces the observed price
        # within 0.5%.
        assert _forward_fv(cg) == pytest.approx(MSFT_PRICE, rel=0.005)


@pytest.mark.unit
class TestUnusableInputs:
    def test_missing_wacc_is_unusable(self):
        r = _msft(wacc=None)
        assert r["usable"] is False
        assert r["reason"]
        assert r["rows"] == []

    def test_zero_shares_is_unusable(self):
        r = _msft(shares=0)
        assert r["usable"] is False
        assert r["reason"]
        assert r["rows"] == []

    def test_missing_price_is_unusable(self):
        r = _msft(market_price=None)
        assert r["usable"] is False
        assert r["reason"]
        assert r["rows"] == []

    def test_no_growth_below_wacc_is_unusable(self):
        r = _msft(growths=(0.10, 0.12, 0.5))
        assert r["usable"] is False
        assert r["reason"]
        assert r["rows"] == []

    def test_none_of_the_unusable_inputs_raise(self):
        for kwargs in (
            {"wacc": None},
            {"shares": 0},
            {"market_price": None},
            {"growths": (0.10, 0.12)},
            {"market_price": "junk", "shares": "junk", "wacc": "junk"},
        ):
            r = _msft(**kwargs)
            assert r["usable"] is False
            assert r["rows"] == []


@pytest.mark.unit
class TestImpliedGrowthForFcf:
    def test_sane_value_for_the_msft_price(self):
        g = implied_growth_for_fcf(
            MSFT_PRICE, MSFT_SHARES, MSFT_WACC, MSFT_FCF,
            cash=MSFT_CASH, debt=MSFT_DEBT,
        )
        assert g is not None
        assert g == pytest.approx(0.0804, abs=0.002)
        assert _forward_fv(g) == pytest.approx(MSFT_PRICE, rel=0.005)

    def test_none_when_price_is_unreachable(self):
        # The value diverges toward ~$9.7M/share as g -> wacc; $20M/share is
        # above that ceiling, so no perpetual growth of this FCF explains it.
        assert implied_growth_for_fcf(
            2e7, MSFT_SHARES, MSFT_WACC, MSFT_FCF, cash=MSFT_CASH, debt=MSFT_DEBT
        ) is None

    def test_near_wacc_bound_when_price_is_extreme_but_reachable(self):
        g = implied_growth_for_fcf(
            9_000_000.0, MSFT_SHARES, MSFT_WACC, MSFT_FCF,
            cash=MSFT_CASH, debt=MSFT_DEBT,
        )
        assert g is not None
        assert MSFT_WACC - 1e-3 < g < MSFT_WACC

    def test_none_on_unusable_inputs(self):
        assert implied_growth_for_fcf(None, MSFT_SHARES, MSFT_WACC, MSFT_FCF) is None
        assert implied_growth_for_fcf(MSFT_PRICE, 0, MSFT_WACC, MSFT_FCF) is None
        assert implied_growth_for_fcf(MSFT_PRICE, MSFT_SHARES, None, MSFT_FCF) is None
        assert implied_growth_for_fcf(MSFT_PRICE, MSFT_SHARES, MSFT_WACC, None) is None

    def test_none_when_price_already_met_at_zero_growth(self):
        # The forward value at g=0 is ~$91/share; a price below it has no
        # crossing inside (0, wacc).
        assert implied_growth_for_fcf(
            60.0, MSFT_SHARES, MSFT_WACC, MSFT_FCF, cash=MSFT_CASH, debt=MSFT_DEBT
        ) is None
