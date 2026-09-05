"""Option-position breakeven / PMCC discipline tests (options_breakeven.py)."""

import pytest

from tradingagents.strategies.options_breakeven import (
    catalyst_window,
    delta_profile,
    long_leg_time_split,
    pmcc_breakeven,
    pmcc_read,
    short_call_discipline,
    theta_zone,
)

pytestmark = pytest.mark.timeout(60)


def test_pmcc_breakeven_is_strike_plus_premium():
    assert pmcc_breakeven(300.0, 103.13) == 403.13


def test_pmcc_breakeven_none_safe():
    assert pmcc_breakeven(None, 103.13) is None
    assert pmcc_breakeven(300.0, None) is None
    assert pmcc_breakeven(-1.0, 10.0) is None  # invalid inputs -> None


def test_short_call_discipline_floor():
    # sample: breakeven 403.13; short strike 390 violates, 410 satisfies.
    ok = short_call_discipline(410.0, 403.13)
    assert ok["ok"] is True and round(ok["cushion"], 2) == 6.87
    bad = short_call_discipline(390.0, 403.13)
    assert bad["ok"] is False and bad["cushion"] == -13.13


def test_short_call_discipline_none_safe():
    d = short_call_discipline(None, 403.13)
    assert d["ok"] is None and d["cushion"] is None


def test_long_leg_time_split():
    # AVGO: spot 346, strike 300, premium 103.13 -> intrinsic 46, extrinsic 57.13.
    s = long_leg_time_split(346.0, 300.0, 103.13)
    assert s["itm"] is True
    assert round(s["intrinsic"], 2) == 46.0
    assert round(s["extrinsic"], 2) == 57.13
    assert round(s["intrinsic_pct"], 1) == 44.6
    assert round(s["extrinsic_pct"], 1) == 55.4


def test_long_leg_time_split_otm_locks_extrinsic():
    # OTM long leg -> intrinsic 0, full premium is time value.
    s = long_leg_time_split(100.0, 300.0, 50.0)
    assert s["itm"] is False and s["intrinsic"] == 0.0
    assert s["extrinsic"] == 50.0 and s["extrinsic_pct"] == 100.0


def test_delta_profile_bands():
    assert "0.75-0.85" in delta_profile(0.80)
    assert "mid-delta" in delta_profile(0.5)
    assert "0.20-0.30" in delta_profile(0.25)
    assert "very-low" in delta_profile(0.1)
    assert delta_profile(None) is None


def test_theta_zone_window():
    assert "30-45d" in theta_zone(38)
    assert "under 30d" in theta_zone(10)
    assert "over 45d" in theta_zone(90)
    assert theta_zone(None) is None


def test_catalyst_window_imminence():
    assert catalyst_window(3)["imminent"] is True
    assert "avoid" in catalyst_window(3)["note"]
    assert catalyst_window(21)["imminent"] is False
    assert catalyst_window(None) == {"imminent": None, "note": None}


def test_pmcc_read_combined_avgo_sample():
    r = pmcc_read(
        300.0, 103.13,
        short_strike=390.0, spot=346.0, short_ttm_days=35.0,
        delta=0.8, days_to_earnings=6, days_to_ex_div=2,
    )
    assert r["long_breakeven"] == 403.13
    assert r["short_discipline"]["ok"] is False  # 390 < 403.13 floor violated
    assert r["long_leg_split"]["itm"] is True
    assert "deep-ITM" in r["delta_profile"]
    assert "30-45d" in r["short_theta_zone"]
    assert r["earnings_window"]["imminent"] is True
    assert "ex-div" in r["assignment"]["note"]


def test_pmcc_read_partial_inputs_na():
    # Only the mandatory pair -> everything else renders n/a, never fabricated.
    r = pmcc_read(300.0, 103.13)
    assert r["long_breakeven"] == 403.13
    assert r["short_discipline"]["ok"] is None
    assert r["long_leg_split"]["intrinsic"] is None
    assert r["delta_profile"] is None
    assert r["short_theta_zone"] is None
    assert r["earnings_window"] == {"imminent": None, "note": None}
