"""Capex-normalized FCF DCF (strategies/normalized_fcf.py) - pure/offline tests.

MSFT FY2026 is the regression anchor. The engine's single-rate DCF telescopes
into a perpetuity of *reported* FCF, so the company mid-AI-buildout prints
~$123.6/share; the accounting other end is maintenance FCF (ocf - D&A) at
~$254.5/share. The capex-intensity fade has to land in that range, and the
``defensive_capex_share`` knob has to continuously undo it back toward the
reported-FCF view.

Numbers: MSFT FY2026 release (revenue 331.8B, OCF 182.9B, capex 115.9B, D&A
43.45B, FCF 67.0B), diluted shares 7,567,453,176.4, cash 76.651B, debt 56.826B.
"""

import json

import pytest

from tradingagents.strategies.normalized_fcf import maintenance_fcf, normalized_fcf_dcf

MSFT = {
    "revenue": 331_800_000_000,
    "ocf": 182_900_000_000,
    "capex": 115_900_000_000,
    "depreciation": 43_450_000_000,
    "shares": 7_567_453_176.4,
    "wacc": 0.10,
    "cash": 76_651_000_000,
    "debt": 56_826_000_000,
}
_K = 1.025 / (0.10 - 0.025)  # repo Gordon convention: (1+g)/(wacc-g)
_ASSUMPTION_KEYS = {
    "revenue",
    "ocf",
    "capex",
    "depreciation",
    "revenue_growth",
    "margin",
    "initial_capex_ratio",
    "terminal_capex_ratio_effective",
    "capex_fade_years",
    "years",
    "terminal_growth",
    "defensive_capex_share",
    "cash",
    "debt",
}


def _msft(revenue_growth=0.10, **over):
    kw = {**MSFT, "revenue_growth": revenue_growth, **over}
    return normalized_fcf_dcf(**kw)


def _reported_perpetuity():
    """Perpetuity of the FCF the market sees (ocf - capex) + net cash bridge."""
    return (
        (MSFT["ocf"] - MSFT["capex"]) * _K + MSFT["cash"] - MSFT["debt"]
    ) / MSFT["shares"]


def _floor_perpetuity():
    """Perpetuity of maintenance FCF (ocf - D&A) + net cash bridge."""
    return (
        (MSFT["ocf"] - MSFT["depreciation"]) * _K + MSFT["cash"] - MSFT["debt"]
    ) / MSFT["shares"]


def test_constant_capex_ratio_telescopes_to_forward_perpetuity():
    # When the explicit path grows at terminal_growth the model collapses onto
    # the forward perpetuity on (ocf - depreciation): explicit PV + discounted
    # Gordon TV telescopes exactly, so the capex-intensity path is the only
    # lever. Both sides are computed here so the identity cannot pass vacuously.
    rev, ocf, capex, dep, shares = 1_000.0, 200.0, 60.0, 50.0, 10.0
    cash, debt, wacc, tg = 40.0, 10.0, 0.10, 0.025
    r = normalized_fcf_dcf(
        rev, ocf, capex, dep, shares, wacc, tg,
        capex_fade_years=1, terminal_growth=tg, cash=cash, debt=debt,
    )
    perp = (ocf - dep) / shares * (1 + tg) / (wacc - tg) + (cash - debt) / shares
    assert r["usable"] is True
    assert r["capex_ratio_path"] == pytest.approx([dep / rev] * 5)
    assert perp == pytest.approx(208.0)  # anchor: EV 2050 + net cash 30, /10 shares
    assert r["fair_value"] == pytest.approx(perp, rel=1e-9)
    assert r["fair_value"] == pytest.approx(perp, rel=0.01)


def test_flat_window_understates_the_perpetuity_by_the_growth_drag():
    # revenue_growth=0.0 pins the ratio at D&A/revenue, so the window is a flat
    # FCF = ocf - dep. Discounting that flat stream and only growing it from the
    # terminal date lands BELOW the forward perpetuity (and converges to FCF/wacc,
    # not FCF (1+g)/(wacc-g) as the window lengthens). This is a documented
    # property of the window, not a fabrication - asserted on both sides.
    rev, ocf, capex, dep, shares = 1_000.0, 200.0, 60.0, 50.0, 10.0
    cash, debt, wacc, tg = 40.0, 10.0, 0.10, 0.025
    perp = (ocf - dep) / shares * (1 + tg) / (wacc - tg) + (cash - debt) / shares
    flat = normalized_fcf_dcf(
        rev, ocf, capex, dep, shares, wacc, 0.0,
        capex_fade_years=1, terminal_growth=tg, cash=cash, debt=debt,
    )
    assert flat["fair_value"] == pytest.approx(187.15, rel=1e-3)
    assert flat["fair_value"] < perp
    one_year = normalized_fcf_dcf(
        rev, ocf, capex, dep, shares, wacc, 0.0,
        years=1, capex_fade_years=1, terminal_growth=tg, cash=cash, debt=debt,
    )
    long_window = normalized_fcf_dcf(
        rev, ocf, capex, dep, shares, wacc, 0.0,
        years=100, capex_fade_years=1, terminal_growth=tg, cash=cash, debt=debt,
    )
    # the drag GROWS as the window lengthens (a flat stream replaces the growing
    # perpetuity for longer) and the value approaches ocf-dep capitalized at wacc
    # (a no-growth perpetuity), still below the growing one.
    assert perp - long_window["fair_value"] > perp - flat["fair_value"] > perp - one_year["fair_value"] > 0
    assert long_window["fair_value"] == pytest.approx(
        (ocf - dep) / shares / wacc + (cash - debt) / shares, rel=1e-3
    )


def test_msft_fy2026_fade_beats_permanently_depressed_and_buildout_views():
    reported = _reported_perpetuity()
    floor = _floor_perpetuity()
    assert reported == pytest.approx(123.57, rel=0.01)  # reported-FCF perpetuity

    fade = _msft()  # revenue_growth 0.10, intensity fades to D&A/revenue
    flat = _msft(revenue_growth=0.0)  # same fade, revenue held constant
    no_fade = _msft(
        capex_fade_years=10_000,
        terminal_capex_ratio=MSFT["capex"] / MSFT["revenue"],
    )
    # The fade must beat both the perpetuity of today's depressed FCF and the
    # assumption that the buildout intensity is permanent.
    assert fade["fair_value"] > reported
    assert fade["fair_value"] > 123.57
    assert no_fade["fair_value"] < fade["fair_value"]
    assert no_fade["fair_value"] == pytest.approx(167.89, rel=1e-3)
    # On the flat-revenue variant the fade sits strictly between the two
    # accounting anchors: above the reported-FCF perpetuity, below the
    # maintenance buildout ceiling (the ceiling with the net-cash bridge is
    # ~254.5; the brief's 258.3 is the same figure before the bridge).
    assert flat["fair_value"] < floor
    assert flat["fair_value"] < 258.3
    assert reported < flat["fair_value"] < floor
    assert fade["terminal_share"] == pytest.approx(
        fade["pv_terminal"] / (fade["pv_explicit"] + fade["pv_terminal"])
    )
    assert 0.0 < fade["terminal_share"] < 1.0


def test_defensive_capex_share_mirrors_the_fade_continuously():
    no_fade = _msft(
        terminal_capex_ratio=MSFT["capex"] / MSFT["revenue"],
        capex_fade_years=10_000,
    )
    full_defence = _msft(defensive_capex_share=1.0)
    assert full_defence["fair_value"] == pytest.approx(no_fade["fair_value"], rel=1e-9)
    assert full_defence["assumptions"]["terminal_capex_ratio_effective"] == pytest.approx(
        MSFT["capex"] / MSFT["revenue"]
    )
    # The knob is the continuous mirror: half-defence lands between full fade
    # and no fade.
    fade = _msft()
    half = _msft(defensive_capex_share=0.5)
    assert fade["fair_value"] > half["fair_value"] > full_defence["fair_value"]
    # Out-of-range values are clamped, never extrapolated.
    assert _msft(defensive_capex_share=5.0)["fair_value"] == pytest.approx(
        full_defence["fair_value"]
    )


def test_capex_ratio_path_fades_monotonically_then_holds_flat():
    r = _msft(revenue_growth=0.0)
    path = r["capex_ratio_path"]
    assert r["assumptions"]["years"] == 5
    assert len(path) == len(r["fcf_path"]) == 5
    assert path[0] == pytest.approx(MSFT["capex"] / MSFT["revenue"])
    assert path[-1] == pytest.approx(MSFT["depreciation"] / MSFT["revenue"])
    assert all(a >= b for a, b in zip(path, path[1:], strict=False))
    assert all(v > 0 for v in r["fcf_path"])

    # fade window = 2: the ratio reaches terminal at year 2 and is flat after.
    short = _msft(revenue_growth=0.0, capex_fade_years=2)["capex_ratio_path"]
    assert short[1] == pytest.approx(short[2]) == pytest.approx(short[3]) == pytest.approx(short[4])
    assert short == sorted(short, reverse=True)
    assert short[0] > short[1]

    # A longer window only lengthens the projection, it does not change the tail.
    longer = _msft(revenue_growth=0.0, years=8)
    assert len(longer["fcf_path"]) == 8
    assert longer["capex_ratio_path"][-1] == pytest.approx(path[-1])


@pytest.mark.parametrize(
    "over, needle",
    [
        ({"revenue": None}, "revenue"),
        ({"shares": 0.0}, "shares"),
        ({"wacc": 0.02}, "terminal_growth"),
        ({"debt": 5e12}, "equity"),
    ],
)
def test_unusable_inputs_return_a_reason_and_never_raise(over, needle):
    r = _msft(**over)
    assert r["usable"] is False
    assert isinstance(r["reason"], str) and needle in r["reason"]
    assert r["fair_value"] is None
    assert r["pv_explicit"] is None and r["pv_terminal"] is None
    assert r["terminal_share"] is None
    assert r["fcf_path"] == [] and r["capex_ratio_path"] == []
    assert isinstance(r["assumptions"], dict)
    assert set(r["assumptions"]) == _ASSUMPTION_KEYS


def test_missing_revenue_still_reports_what_it_can():
    r = _msft(revenue=None)
    assert r["usable"] is False
    assert "revenue" in r["reason"]
    # the assumption set is populated as far as the inputs allow
    assert r["assumptions"]["revenue"] is None
    assert r["assumptions"]["margin"] is None
    assert r["assumptions"]["initial_capex_ratio"] is None
    assert r["assumptions"]["terminal_capex_ratio_effective"] is None
    assert r["assumptions"]["ocf"] == MSFT["ocf"]
    assert r["assumptions"]["years"] == 5
    assert r["maintenance"]["maintenance_fcf"] == pytest.approx(139_450_000_000)


def test_result_is_json_able_and_reproducible_from_its_assumptions():
    r = _msft()
    json.dumps(r)  # JSON-able: floats/str/bool/list only
    a = r["assumptions"]
    assert set(a) == _ASSUMPTION_KEYS
    assert a["initial_capex_ratio"] == pytest.approx(MSFT["capex"] / MSFT["revenue"])
    assert a["terminal_capex_ratio_effective"] == pytest.approx(
        MSFT["depreciation"] / MSFT["revenue"]
    )
    # a leaf printed from the result is reproducible from the assumption set
    replay = normalized_fcf_dcf(
        a["revenue"], a["ocf"], a["capex"], a["depreciation"], r["shares"],
        r["wacc"], a["revenue_growth"], margin=a["margin"], years=a["years"],
        terminal_capex_ratio=a["terminal_capex_ratio_effective"],
        capex_fade_years=a["capex_fade_years"], terminal_growth=a["terminal_growth"],
        cash=a["cash"], debt=a["debt"], defensive_capex_share=a["defensive_capex_share"],
    )
    assert replay["fair_value"] == pytest.approx(r["fair_value"])
    assert replay["fcf_path"] == pytest.approx(r["fcf_path"])
    assert r["maintenance"]["maintenance_fcf"] == pytest.approx(139_450_000_000)
    assert r["maintenance"]["reported_fcf"] == pytest.approx(67_000_000_000)


def test_maintenance_fcf_msft_numbers_and_none_safety():
    r = maintenance_fcf(MSFT["ocf"], MSFT["depreciation"], MSFT["capex"])
    assert r["maintenance_fcf"] == pytest.approx(139_450_000_000)
    assert r["reported_fcf"] == pytest.approx(67_000_000_000)
    assert r["growth_capex"] == pytest.approx(72_450_000_000)
    assert r["maintenance_fcf"] == pytest.approx(
        r["reported_fcf"] + r["growth_capex"]
    )
    assert isinstance(r["basis"], str) and "D&A" in r["basis"]

    # missing capex: the reported/growth views vanish, the maintenance floor stands
    no_capex = maintenance_fcf(100.0, 30.0)
    assert no_capex["maintenance_fcf"] == pytest.approx(70.0)
    assert no_capex["reported_fcf"] is None
    assert no_capex["growth_capex"] is None
    assert no_capex["basis"] == r["basis"]
    # missing D&A: no floor at all, never a fabricated number
    nothing = maintenance_fcf(None, None, None)
    assert nothing["maintenance_fcf"] is None
    assert nothing["reported_fcf"] is None
    assert nothing["growth_capex"] is None
