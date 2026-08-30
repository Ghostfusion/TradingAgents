"""Fixed-income / preferred analytics tests (quants.md §Fixed Income; offline)."""

import pytest

from tradingagents.strategies.fixed_income import (
    bond_convexity,
    dv01,
    indicated_yield,
    macaulay_duration,
    modified_duration,
    preferred_ytm,
)

pytestmark = pytest.mark.timeout(120)


def test_indicated_yield():
    assert indicated_yield(5.0, 100.0) == pytest.approx(0.05)
    assert indicated_yield(None, 100.0) is None
    assert indicated_yield(5.0, 0.0) is None
    assert indicated_yield(5.0, None) is None


def test_preferred_ytm_par_bond():
    # Par bond: price == par -> YTM == coupon/dividend rate.
    assert preferred_ytm(5.0, 100.0, 100.0, 10) == pytest.approx(0.05, rel=0.01)
    # Perpetual (no years) -> None (no fabricated YTM).
    assert preferred_ytm(5.0, 100.0, 100.0, None) is None
    assert preferred_ytm(5.0, 120.0, 100.0, 10) < 0.05  # premium priced -> lower YTM


def test_macaulay_duration_zero_coupon():
    # Zero-coupon bond: duration == time to maturity.
    cash = [{"t": 5.0, "amount": 100.0}]
    assert macaulay_duration(cash, 0.05) == pytest.approx(5.0, rel=1e-3)
    assert macaulay_duration([], 0.05) is None
    assert macaulay_duration(cash, None) is None


def test_modified_duration_and_dv01():
    # Coupon bond: Macaulay ~ slightly less than maturity.
    cash = [{"t": 1.0, "amount": 5.0}, {"t": 2.0, "amount": 5.0}, {"t": 3.0, "amount": 105.0}]
    mac = macaulay_duration(cash, 0.05)
    assert mac is not None and 0 < mac < 3.0
    mod = modified_duration(mac, 0.05)
    assert mod is not None and 0 < mod < mac
    assert modified_duration(None, 0.05) is None
    # DV01 = D_mod * price * 1e-4.
    dv = dv01(mod, 100.0)
    assert dv is not None and dv == pytest.approx(mod * 100.0 * 0.0001)
    assert dv01(None, 100.0) is None


def test_bond_convexity_positive():
    cash = [{"t": 1.0, "amount": 5.0}, {"t": 2.0, "amount": 5.0}, {"t": 3.0, "amount": 105.0}]
    cv = bond_convexity(cash, 0.05)
    assert cv is not None and cv > 0
    assert bond_convexity([], 0.05) is None


def test_screener_render_fi_columns():
    """_render_markdown with fi=True adds YTM/DMod/DV01 columns and the
    perpetual n/a note."""
    from scripts.capital_income_screener import _render_markdown

    plan = {
        "used_equal_weight": True,
        "ranked": [
            {"ticker": "GS-PD", "price": 25.0, "dividend": 1.0, "yield": 0.04,
             "mv": 1e9, "adtv": 5e6, "liquid": True, "weight": 0.03},
        ],
    }
    md = _render_markdown(plan, source="test", top=50, fi=True, fi_horizon=10)
    assert "YTM%" in md and "DMod" in md and "DV01" in md
    assert "GS-PD" in md
    # Without a horizon the perpetual note appears.
    md2 = _render_markdown(plan, source="test", top=50, fi=True, fi_horizon=None)
    assert "n/a" in md2.lower() or "perpetuals render n/a" in md2
    # Non-fi render unchanged (no YTM column).
    md3 = _render_markdown(plan, source="test", top=50, fi=False)
    assert "YTM%" not in md3
