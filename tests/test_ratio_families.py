"""FundamentalScore ratio families in ``strategies/ratios.py`` (FUND-1..FUND-19),
plus the RISK-18 cash-burn legs (§48) that land in the same module.

One synthetic-fixture test per library family (``Strategies/scores/
fundamental_score.md``, ranked in ``docs/scores/FundamentalScore.md`` §3.6),
each covering the computed keys AND the None / near-zero-denominator refusal
(``NA != 0``). Offline and deterministic: every input is a literal dict.
"""

import pytest

from tradingagents.dataflows.statement_parsing import _canonicalize
from tradingagents.strategies.ratios import (
    MAD_SCALE,
    RENDER_ORDER,
    SBC_XBRL_TAG,
    compute_ratios,
    return_on_capital,
    robust_z,
    sbc_adjusted_fcf,
    shareholder_yield,
)

pytestmark = pytest.mark.timeout(180)


def _fin(**over):
    base = {
        "market_cap": 1000e6,
        "total_debt": 200e6,
        "cash": 50e6,
        "operating_income": 120e6,      # EBIT
        "depreciation": 30e6,           # -> EBITDA 150e6
        "revenue": 900e6,
        "net_income": 80e6,
        "total_equity": 500e6,
        "total_assets": 800e6,
        "total_liabilities": 400e6,
        "operating_cashflow": 90e6,     # OCF
        "capex": 30e6,                  # -> FCF 60e6
        "current_assets": 300e6,
        "current_liabilities": 150e6,
        "inventory": 60e6,
        "dividends_paid": 20e6,
        "interest_expense": 10e6,
        "share_buybacks": 15e6,
        "cogs": 600e6,
        "net_receivables": 120e6,
        "payables": 80e6,
        "tax_expense": 20e6,            # effective rate 20 / (80 + 20) = 20%
    }
    base.update(over)
    return base


def _series(values, years=(2023, 2024, 2025)):
    return {"values": list(values), "years": list(years)}


# ---------------------------------------------------------------------------
# FUND-1 - debt-service capacity (§9)
# ---------------------------------------------------------------------------

def test_fund1_coverage_family_and_near_zero_refusal():
    r = compute_ratios(_fin(debt_repayment=5e6))
    assert r["interest_coverage"] == pytest.approx(120e6 / 10e6)
    assert r["ebitda_interest_coverage"] == pytest.approx(150e6 / 10e6)
    assert r["cash_interest_coverage"] == pytest.approx(90e6 / 10e6)
    # FCCR: fixed charges proxied by interest (120+10) / (10+10) = 6.5
    assert r["fixed_charge_coverage"] == pytest.approx(6.5)
    # DSCR: OCF / (interest + debt repaid) = 90 / 15 = 6.0
    assert r["debt_service_coverage"] == pytest.approx(6.0)

    # A near-zero interest expense is a units artifact, not a 1e11x coverage.
    near = compute_ratios({"operating_income": 100.0, "interest_expense": 1e-9})
    assert near["interest_coverage"] is None
    assert near["ebitda_interest_coverage"] is None
    # Missing interest expense -> every coverage key refuses.
    assert compute_ratios(_fin(interest_expense=None))["interest_coverage"] is None


# ---------------------------------------------------------------------------
# FUND-4 - cash-flow family (§2/§3)
# ---------------------------------------------------------------------------

def test_fund4_cash_flow_family_and_growth_divergence():
    r = compute_ratios(_fin())
    assert r["ocf_yield"] == pytest.approx(0.09)
    assert r["fcf_yield"] == pytest.approx(0.06)
    assert r["fcf_margin"] == pytest.approx(60e6 / 900e6)
    assert r["ocf_margin"] == pytest.approx(0.1)
    assert r["fcf_to_net_income"] == pytest.approx(0.75)
    assert r["ocf_to_net_income"] == pytest.approx(90e6 / 80e6)
    assert r["fcf_to_ebitda"] == pytest.approx(0.4)
    assert r["ocf_to_ebitda"] == pytest.approx(0.6)
    assert r["capex_to_ocf"] == pytest.approx(1.0 / 3.0)
    assert r["ev_to_fcf"] == pytest.approx(1150e6 / 60e6)
    assert r["ocf_ni_growth_divergence"] is None  # no series supplied

    grown = compute_ratios(_fin(
        operating_cashflow_series=_series([80e6, 95e6, 90e6]),
        net_income_series=_series([60e6, 70e6, 80e6]),
    ))
    # OCF growth (90/95 - 1) - NI growth (80/70 - 1)
    assert grown["ocf_ni_growth_divergence"] == pytest.approx((90.0 / 95.0 - 1) - (80.0 / 70.0 - 1))

    # No FCF -> every FCF-derived key refuses, never zero.
    no_fcf = compute_ratios(_fin(capex=None))
    assert no_fcf["fcf_margin"] is None and no_fcf["ev_to_fcf"] is None


# ---------------------------------------------------------------------------
# FUND-5 - leverage family (§8)
# ---------------------------------------------------------------------------

def test_fund5_leverage_family():
    r = compute_ratios(_fin())
    assert r["net_debt"] == pytest.approx(150e6)
    assert r["net_debt_to_ebitda"] == pytest.approx(1.0)
    assert r["debt_to_ebitda"] == pytest.approx(200e6 / 150e6)
    assert r["debt_to_assets"] == pytest.approx(0.25)
    assert r["net_debt_to_fcf"] == pytest.approx(2.5)
    assert r["cash_to_debt"] == pytest.approx(0.25)
    assert r["net_cash_yield"] == pytest.approx(-0.15)  # net debt, not net cash
    assert r["ocf_to_debt"] == pytest.approx(0.45)

    # No depreciation -> EBITDA None -> its leverage keys refuse.
    r2 = compute_ratios(_fin(depreciation=None))
    assert r2["net_debt_to_ebitda"] is None and r2["debt_to_ebitda"] is None


# ---------------------------------------------------------------------------
# FUND-2 - level ROIC / capital employed (§1/§6)
# ---------------------------------------------------------------------------

def test_fund2_level_roic_and_capital_employed():
    cap = return_on_capital(_fin())
    ic = 200e6 + 500e6 - 50e6
    assert cap["invested_capital"] == pytest.approx(ic)
    assert cap["capital_employed"] == pytest.approx(800e6 - 150e6)
    assert cap["tax_rate"] == pytest.approx(0.2)
    assert cap["nopat"] == pytest.approx(96e6)
    assert cap["roic"] == pytest.approx(96e6 / ic)
    assert cap["roce"] == pytest.approx(120e6 / (800e6 - 150e6))
    assert cap["return_on_capital"] == pytest.approx(120e6 / ic)
    assert cap["invested_capital_turnover"] == pytest.approx(900e6 / ic)
    assert cap["reason"] is None

    # The same producers land in compute_ratios.
    r = compute_ratios(_fin())
    assert r["roic"] == pytest.approx(cap["roic"])
    assert r["return_on_capital"] == pytest.approx(cap["return_on_capital"])

    # No tax rate derivable -> ROIC refuses with a reason; ROCE still computes.
    no_tax = return_on_capital(_fin(tax_expense=None, net_income=None))
    assert no_tax["roic"] is None and no_tax["nopat"] is None
    assert "no tax rate" in no_tax["reason"]
    assert no_tax["roce"] is not None

    # No debt/equity -> no invested capital, reasoned.
    none = return_on_capital(_fin(total_debt=None, total_equity=None))
    assert none["invested_capital"] is None and "invested capital" in none["reason"]


# ---------------------------------------------------------------------------
# FUND-3 - buyback / shareholder yield (§10/§11)
# ---------------------------------------------------------------------------

def test_fund3_shareholder_yield_sign_convention():
    # A vendor filing repurchases as a negative outflow must still read +1.5%.
    r = compute_ratios(_fin(share_buybacks=-15e6))
    assert r["buyback_yield"] == pytest.approx(0.015)
    assert r["dividend_yield"] == pytest.approx(0.02)
    assert r["shareholder_yield"] == pytest.approx(0.035)

    sy = shareholder_yield(_fin(share_buybacks=-15e6))
    assert sy["buyback_yield"] == pytest.approx(0.015)

    # Both legs required: no dividends -> the sum refuses, the buyback leg stays.
    half = shareholder_yield(_fin(dividends_paid=None))
    assert half["buyback_yield"] == pytest.approx(0.015)
    assert half["shareholder_yield"] is None
    assert "shareholder yield cannot be summed" in half["reason"]

    # No repurchase line -> buyback refused with a reason, never zero.
    none = shareholder_yield(_fin(share_buybacks=None))
    assert none["buyback_yield"] is None
    assert "share_buybacks" in none["reason"]

    # Net-issuance sign: +5 shares at $100 over a $1bn cap is a NEGATIVE yield.
    issued = shareholder_yield(
        _fin(shares={"current": 105.0, "prior": 100.0}), market_cap=1000e6, price=100.0
    )
    assert issued["net_issuance_yield"] == pytest.approx(-(5.0 * 100.0) / 1000e6)


# ---------------------------------------------------------------------------
# FUND-6 - margins and the stability legs (§5/§28)
# ---------------------------------------------------------------------------

def test_fund6_margins_and_stability_legs():
    r = compute_ratios(_fin())
    assert r["gross_margin"] == pytest.approx(1.0 / 3.0)
    assert r["ebit_margin"] == pytest.approx(120e6 / 900e6)
    assert r["ebitda_margin"] == pytest.approx(150e6 / 900e6)
    assert r["net_margin"] == pytest.approx(80e6 / 900e6)

    # No series -> no dispersion to measure (None, not 0).
    assert r["gross_margin_stability"] is None
    assert r["operating_margin_stability"] is None
    # No NOPAT / invested-capital series exists in the canonical payload.
    assert r["roic_stability"] is None

    s = compute_ratios(_fin(
        gross_profit_series=_series([240e6, 255e6, 300e6]),
        operating_income_series=_series([100e6, 110e6, 120e6]),
        revenue_series=_series([800e6, 850e6, 900e6]),
    ))
    # -sigma, so a LARGER (less negative) value is a more stable margin.
    assert s["gross_margin_stability"] is not None and s["gross_margin_stability"] < 0
    assert s["operating_margin_stability"] is not None and s["operating_margin_stability"] < 0
    # The margin series themselves are exposed (EBIT margin = EBIT / revenue).
    assert s["gross_margin_series"] == [pytest.approx(240e6 / 800e6), pytest.approx(255e6 / 850e6), pytest.approx(300e6 / 900e6)]
    assert s["ebit_margin_series"][-1] == pytest.approx(120e6 / 900e6)
    assert r["gross_margin_series"] is None and r["ebit_margin_series"] is None


# ---------------------------------------------------------------------------
# FUND-8 - normalized FCF yield and the FCF / cash-conversion stabilities
# ---------------------------------------------------------------------------

def test_fund8_normalized_fcf_and_stabilities():
    r = compute_ratios(_fin())
    assert r["normalized_fcf"] is None and r["fcf_stability"] is None
    assert r["cash_conversion_stability"] is None

    f = compute_ratios(_fin(
        operating_cashflow_series=_series([80e6, 95e6, 90e6]),
        capex_series=_series([20e6, 25e6, 30e6]),
        revenue_series=_series([800e6, 850e6, 900e6]),
        net_income_series=_series([60e6, 70e6, 80e6]),
    ))
    # FCF series = [60, 70, 60]e6 -> median 60e6.
    assert f["normalized_fcf"] == pytest.approx(60e6)
    assert f["normalized_fcf_yield"] == pytest.approx(0.06)
    assert f["fcf_stability"] is not None and f["fcf_stability"] < 0
    assert f["cash_conversion_stability"] is not None and f["cash_conversion_stability"] < 0


# ---------------------------------------------------------------------------
# FUND-9 - numeric growth and WC/assets (§7)
# ---------------------------------------------------------------------------

def test_fund9_growth_and_working_capital_to_assets():
    r = compute_ratios(_fin(
        total_assets_series=_series([700e6, 750e6, 800e6]),
        net_receivables={"current": 120e6, "prior": 100e6},
        inventory={"current": 60e6, "prior": 50e6},
        total_debt={"current": 200e6, "prior": 190e6},
    ))
    assert r["asset_growth"] == pytest.approx((800.0 - 750.0) / 750.0)
    assert r["receivables_growth"] == pytest.approx(0.2)
    assert r["inventory_growth"] == pytest.approx(0.2)
    assert r["debt_growth"] == pytest.approx(10.0 / 190.0)
    assert r["working_capital_to_assets"] == pytest.approx((300e6 - 150e6) / 800e6)

    assert compute_ratios(_fin())["asset_growth"] is None  # one point is no series


# ---------------------------------------------------------------------------
# FUND-14 - robust (median/MAD) z-score (§23)
# ---------------------------------------------------------------------------

def test_fund14_robust_z_primitive():
    z = robust_z([1.0, 2.0, 3.0, 100.0])
    # median = 2.5; MAD = median(|.|) = 1.0; scale = 1.4826 * 1.0
    assert z[2] == pytest.approx((3.0 - 2.5) / (MAD_SCALE * 1.0))
    assert z[3] > 60  # the outlier is not winsorised away
    # No dispersion -> no scale to standardise against.
    assert robust_z([1.0, 1.0, 1.0]) == [None, None, None]
    # Fewer than three points cannot place a median/MAD.
    assert robust_z([1.0, 2.0]) == [None, None]
    # None inputs stay None and do not enter the fit.
    assert robust_z([None, 1.0, 2.0, 3.0])[0] is None


def test_fund14_robust_route_in_the_normaliser_is_opt_in():
    """The factor-normalisation path consumes the primitive, off by default."""
    from tradingagents.strategies.cross_section import cross_sectional_z

    vals = [1.0, 2.0, 3.0, 100.0]
    default = cross_sectional_z(vals)
    # Default path unchanged: mean/std and the outlier's own (huge) z.
    assert default["mean"] == pytest.approx(26.5)
    assert default["z"][3] == pytest.approx((100.0 - 26.5) / default["std"])
    assert default["std"] > 40

    robust = cross_sectional_z(vals, robust=True)
    # Robust location/scale: median 2.5, 1.4826 * MAD(1.0).
    assert robust["mean"] == pytest.approx(2.5)
    assert robust["std"] == pytest.approx(MAD_SCALE * 1.0)
    assert robust["z"] == robust_z(vals)
    # Refused below three points and on zero MAD.
    assert cross_sectional_z([1.0, 2.0], robust=True) is None
    assert cross_sectional_z([5.0, 5.0, 5.0], robust=True) is None


# ---------------------------------------------------------------------------
# FUND-18 - turnover / cash-conversion cycle (§6)
# ---------------------------------------------------------------------------

def test_fund18_turnover_and_cash_conversion_cycle():
    r = compute_ratios(_fin())
    assert r["dio"] == pytest.approx(60e6 / 600e6 * 365.0)
    assert r["dso"] == pytest.approx(120e6 / 900e6 * 365.0)
    assert r["dpo"] == pytest.approx(80e6 / 600e6 * 365.0)
    assert r["cash_conversion_cycle"] == pytest.approx(r["dio"] + r["dso"] - r["dpo"])
    assert r["inventory_turnover"] == pytest.approx(10.0)
    assert r["receivables_turnover"] == pytest.approx(7.5)
    assert r["payables_turnover"] == pytest.approx(7.5)
    assert r["working_capital_turnover"] == pytest.approx(6.0)
    assert r["asset_turnover"] == pytest.approx(1.125)

    # Any missing leg refuses the cycle rather than publishing a partial sum.
    assert compute_ratios(_fin(payables=None))["cash_conversion_cycle"] is None

    # The payables alias is canonical vocabulary (statement_parsing).
    canon = _canonicalize("Total Assets: 1000\nAccounts Payable: 50\n")
    assert canon["payables"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# FUND-19 - earnings yield over bonds (§14); risk-free passed in, never fetched
# ---------------------------------------------------------------------------

def test_fund19_bond_spread_uses_the_passed_in_rate():
    r = compute_ratios(_fin(), risk_free=0.04)
    assert r["earnings_yield_over_bonds"] == pytest.approx(0.08 - 0.04)
    assert r["fcf_yield_over_bonds"] == pytest.approx(0.06 - 0.04)
    # No rate passed -> no spread (this module never fetches one).
    assert compute_ratios(_fin())["earnings_yield_over_bonds"] is None


# ---------------------------------------------------------------------------
# Additivity - the pre-existing block is unchanged and the render list grows
# ---------------------------------------------------------------------------

def test_pre_existing_keys_keep_their_values_and_shape():
    legacy = {
        "ev": 1150e6,
        "ev_ebitda": 1150e6 / 150e6,
        "ev_ebit": 1150e6 / 120e6,
        "ev_sales": 1150e6 / 900e6,
        "price_to_earnings": 1000e6 / 80e6,
        "price_to_book": 2.0,
        "price_to_sales": 1000e6 / 900e6,
        "price_to_cash_flow": 1000e6 / 90e6,
        "price_to_free_cash_flow": 1000e6 / 60e6,
        "return_on_equity": 0.16,
        "return_on_assets": 0.1,
        "debt_to_equity": 0.4,
        "current": 2.0,
        "quick": 1.6,
        "cash_ratio": 50e6 / 150e6,
        "dividend_yield": 0.02,
        "free_cash_flow": 60e6,
        "market_cap": 1000e6,
    }
    r = compute_ratios(_fin())
    for key, expected in legacy.items():
        assert r[key] == pytest.approx(expected), key

    # The new keys are rendered (so the analyst ratio leaf prints them).
    rendered = {key for key, _label, _kind in RENDER_ORDER}
    for key in ("interest_coverage", "roic", "shareholder_yield", "cash_conversion_cycle"):
        assert key in rendered


def test_rendered_block_refuses_missing_family_values():
    from tradingagents.strategies.ratios import render_ratios

    text = render_ratios(compute_ratios(_fin()))
    assert "- EBIT/interest: 12.00" in text
    assert "n/a" in text  # series-only families render n/a, never a number


# ---------------------------------------------------------------------------
# FUND-23 - the screener's ROC / SY columns
# ---------------------------------------------------------------------------

def test_screener_carries_the_roc_and_sy_columns():
    import scripts.value_screener as vs

    legend = dict(vs._WATCHLIST_LEGEND)
    assert "ROC" in legend and "SY" in legend
    md = vs._watchlist_markdown([{
        "ticker": "X",
        "earnings_yield": 0.08, "ev_ebit": 9.0, "ev": 1e9,
        "return_on_capital": 0.18, "shareholder_yield": 0.035,
    }])
    header = md.splitlines()[2]
    assert "ROC" in header and "SY" in header
    assert "18.0%" in md and "3.5%" in md


# ---------------------------------------------------------------------------
# RISK-18 - cash-burn risk (§48): the runway, the deterioration leg, printing
# ---------------------------------------------------------------------------

def test_risk18_cash_runway_measures_only_a_real_burn():
    # CashRunway = Cash / |FCF_negative|: cash 50 / burn 100 = 0.5 years, over
    # the canonical FCF = OCF - |capex| = -70 - 30.
    burn = compute_ratios(_fin(cash=50e6, operating_cashflow=-70e6, capex=30e6))
    assert burn["free_cash_flow"] == pytest.approx(-100e6)
    assert burn["cash_runway_years"] == pytest.approx(0.5)

    # A non-negative FCF funds no burn: None, never an infinite or negative
    # runway (the base fixture's FCF is +60e6, and 30-30 is exactly zero).
    assert compute_ratios(_fin())["cash_runway_years"] is None
    assert compute_ratios(_fin(operating_cashflow=30e6))["cash_runway_years"] is None
    # Missing cash refuses even while the burn is real.
    no_cash = compute_ratios(_fin(cash=None, operating_cashflow=-70e6, capex=30e6))
    assert no_cash["cash_runway_years"] is None


def test_risk18_fcf_deterioration_reads_the_canonical_series():
    # CFD = (FCF_t - FCF_{t-1}) / |FCF_{t-1}| = (-300 + 100) / 100 = -2.0
    worse = compute_ratios(_fin(fcf_series=_series([-100e6, -300e6])))
    assert worse["fcf_deterioration"] == pytest.approx(-2.0)
    # An improving cash flow is a POSITIVE change, not a magnitude.
    better = compute_ratios(_fin(fcf_series=_series([-300e6, -100e6])))
    assert better["fcf_deterioration"] == pytest.approx(200e6 / 300e6)
    # One point is not a change, and a zero prior is the epsilon guard's no-op.
    assert compute_ratios(_fin(fcf_series=_series([-100e6])))["fcf_deterioration"] is None
    assert compute_ratios(_fin(fcf_series=_series([0.0, -100e6])))["fcf_deterioration"] is None
    # No series at all (the plain vendor stack) refuses rather than guessing.
    assert compute_ratios(_fin())["fcf_deterioration"] is None


def test_risk18_renders_the_burn_family_and_refuses_a_non_burn():
    from tradingagents.strategies.ratios import render_ratios

    burning = render_ratios(
        compute_ratios(
            _fin(
                cash=50e6,
                operating_cashflow=-70e6,
                capex=30e6,
                fcf_series=_series([-40e6, -100e6]),
            )
        )
    )
    assert "- Cash runway (years): 0.50" in burning
    assert "- FCF deterioration: -150.00%" in burning
    # The calm fixture has a positive FCF, so the runway row reads n/a while
    # both keys exist - a reader never sees an invented number.
    calm = render_ratios(compute_ratios(_fin()))
    assert "- Cash runway (years): n/a" in calm
    assert "- FCF deterioration: n/a" in calm


# ---------------------------------------------------------------------------
# ValuationScore §55 - the SBC-adjusted (economic) free-cash-flow read
# ---------------------------------------------------------------------------

def test_vs55_sbc_adjustment_reads_the_cashflow_addback():
    """ReportedFCF and EconomicFCF are kept as two measures, per §55."""
    fin = _fin(operating_cashflow=90e6, capex=30e6, revenue=900e6, sbc=12e6)
    read = sbc_adjusted_fcf(fin, market_cap=1000e6)
    assert read["xbrl_tag"] == SBC_XBRL_TAG
    assert read["sbc"] == pytest.approx(12e6)
    assert read["reported_fcf"] == pytest.approx(60e6)
    assert read["economic_fcf"] == pytest.approx(48e6), "economic = FCF - SBC"
    assert read["sbc_to_revenue"] == pytest.approx(12e6 / 900e6)
    assert read["sbc_to_ocf"] == pytest.approx(12e6 / 90e6)
    assert read["sbc_to_fcf"] == pytest.approx(12e6 / 60e6)
    assert read["economic_fcf_yield"] == pytest.approx(48e6 / 1000e6)
    assert read["reason"] is None
    # The block prints ONE cash-flow adjustment, from the same FCF it publishes.
    r = compute_ratios(fin)
    assert r["sbc"] == pytest.approx(12e6)
    assert r["sbc_adjusted_fcf"] == pytest.approx(r["free_cash_flow"] - 12e6)
    assert r["sbc_to_revenue"] == pytest.approx(12e6 / 900e6)


def test_vs55_refuses_without_the_xbrl_concept_never_a_zero_adjustment():
    """A filer that does not file ``us-gaap:ShareBasedCompensation`` refuses.

    The fabricated neutral - ``EconomicFCF = ReportedFCF - 0`` - is the failure
    this asserts against: the refusal must leave ``economic_fcf`` None rather
    than equal to the reported figure, and name the concept it looked for.
    """
    fin = _fin(operating_cashflow=90e6, capex=30e6, revenue=900e6)  # no sbc key
    read = sbc_adjusted_fcf(fin, market_cap=1000e6)
    assert read["sbc"] is None and read["xbrl_tag"] is None
    assert read["reported_fcf"] == pytest.approx(60e6)
    assert read["economic_fcf"] is None, "an absent SBC line is not a zero SBC cost"
    assert read["sbc_to_revenue"] is None
    assert SBC_XBRL_TAG in read["reason"]
    assert "not substituted" in read["reason"]
    # The ratio block carries the same refusal, not a substituted adjustment,
    # and no permanent n/a rows (the vendor path can never fill them).
    r = compute_ratios(fin)
    assert r["sbc"] is None and r["sbc_adjusted_fcf"] is None
    from tradingagents.strategies.ratios import render_ratios

    assert "SBC" not in render_ratios(r)


def test_vs55_does_not_fall_back_to_the_income_statement_sbo_tag():
    """The income-statement allocated expense is a different quantity.

    Measured 2026-09-27 on SIMO FY2025: ``us-gaap:ShareBasedCompensation``
    26,283,000 vs ``us-gaap:AllocatedShareBasedCompensationExpense`` 203,305,000
    (7.7x). A canonical dict carrying only the allocated leg must refuse, so no
    silent redefinition can enter a cross-section.
    """
    fin = _fin(
        operating_cashflow=90e6,
        capex=30e6,
        revenue=900e6,
        allocated_share_based_compensation_expense=203.305e6,
    )
    read = sbc_adjusted_fcf(fin)
    assert read["sbc"] is None
    assert read["economic_fcf"] is None


def test_vs55_reads_the_sec_series_when_no_flat_key_is_present():
    """``fetch_ticker(with_sec_series=True)`` yields ``sbc_series``, not a flat key."""
    fin = _fin(
        sbc_series=_series([8e6, 10e6, 12e6]),
        operating_cashflow_series=_series([70e6, 80e6, 90e6]),
        capex_series=_series([20e6, 25e6, 30e6]),
        revenue_series=_series([700e6, 800e6, 900e6]),
    )
    read = sbc_adjusted_fcf(fin)
    assert read["sbc"] == pytest.approx(12e6)
    assert read["reported_fcf"] == pytest.approx(60e6)
    assert read["economic_fcf"] == pytest.approx(48e6)
    # No flat revenue either: the ratio reads the newest series point.
    flat = dict(fin)
    flat.pop("revenue")
    assert sbc_adjusted_fcf(flat)["sbc_to_revenue"] == pytest.approx(12e6 / 900e6)


def test_the_series_reader_accepts_fetch_tickers_bare_list_shape():
    """``fetch_ticker`` stores ``<key>_series`` as a BARE list of floats.

    That is the documented convention - ``peer_universe._series_values`` states
    it ("``statement_parsing.fetch_ticker`` stores a series as a bare list of
    floats ... Both shapes are accepted here") and ``analysis_tools``'
    Dechow-Dichev block asserts it (``isinstance(s, list)``). This reader
    required the wrapped ``{"values": ...}`` entry instead, so **every** series
    the SEC / vendor path attached was rejected - the INCY 2026-09-29 finding.
    """
    from tradingagents.strategies.ratios import _series_entry

    assert _series_entry({"revenue_series": [1.0, 2.0, 3.0]}, "revenue") == {
        "values": [1.0, 2.0, 3.0],
        "years": [],
    }
    # The wrapped entry (``annual_series``' own return value, handed through a
    # caller's ``financials=``) still reads, and keeps the years it carries.
    assert _series_entry({"revenue_series": _series([1.0, 2.0, 3.0])}, "revenue") == {
        "values": [1.0, 2.0, 3.0],
        "years": [2023, 2024, 2025],
    }
    # One point is not a series; absence stays None rather than a fabricated pair.
    assert _series_entry({"revenue_series": [1.0]}, "revenue") is None
    assert _series_entry({}, "revenue") is None


def test_vs55_reads_the_bare_list_sbc_series_fetch_ticker_emits():
    """A filer that FILES the tag must not read as one that does not.

    INCY 2026-09-29: ``get_quality_factors`` printed "no
    us-gaap:ShareBasedCompensation value for this filer" while the run's own
    EDGAR table carried 17 annual values ($249,346,000 in FY2025) - the series
    was a bare list and the reader rejected it, so the refusal blamed the filer
    for a shape the reader would not read.
    """
    fin = _fin(
        sbc_series=[8e6, 10e6, 12e6],
        operating_cashflow_series=[70e6, 80e6, 90e6],
        net_income_series=[60e6, 70e6, 80e6],
        capex_series=[20e6, 25e6, 30e6],
        revenue_series=[700e6, 800e6, 900e6],
    )
    read = sbc_adjusted_fcf(fin)
    assert read["sbc"] == pytest.approx(12e6)
    assert read["reported_fcf"] == pytest.approx(60e6)
    assert read["economic_fcf"] == pytest.approx(48e6)
    assert read["reason"] is None, "the filer's own series must not be refused"
    assert read["sbc_to_revenue"] == pytest.approx(12e6 / 900e6)
    # The same stack also lights up the series-derived ratio leg, which the
    # shape mismatch had left permanently None.
    r = compute_ratios(fin)
    assert r["sbc"] == pytest.approx(12e6)
    assert r["sbc_adjusted_fcf"] == pytest.approx(48e6)
    # OCF growth (90/80 - 1) - NI growth (80/70 - 1)
    assert r["ocf_ni_growth_divergence"] == pytest.approx(
        (90.0 / 80.0 - 1) - (80.0 / 70.0 - 1)
    )


def test_vs55_ratio_to_fcf_is_refused_when_reported_fcf_is_negative():
    """SBC / negative FCF flips sign and would read as a credit."""
    read = sbc_adjusted_fcf(
        _fin(operating_cashflow=-70e6, capex=30e6, sbc=12e6, revenue=900e6)
    )
    assert read["reported_fcf"] == pytest.approx(-100e6)
    assert read["economic_fcf"] == pytest.approx(-112e6)
    assert read["sbc_to_fcf"] is None
    # SBC/Revenue is unaffected by the FCF sign and still computes.
    assert read["sbc_to_revenue"] == pytest.approx(12e6 / 900e6)


def test_vs55_is_not_rendered_as_permanent_n_a_rows():
    """The §55 keys are engine outputs; the read renders only where it has input.

    The analyst ratio leaf reads the VENDOR statements, which carry no
    share-based-compensation row (live MSFT 2026-09-27), so four ``n/a`` lines
    there would be pure prompt noise. The read reaches the model through
    ``quant_formula_tools.get_quality_factors`` instead (its own tests pin that).
    """
    from tradingagents.strategies.ratios import render_ratios

    block = render_ratios(compute_ratios(_fin(sbc=12e6)))
    assert "SBC" not in block
    assert "- FCF:" in block
