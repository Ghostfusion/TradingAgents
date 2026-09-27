"""P0-P2 of `docs/design_eodhd_unused_surface.md`, offline.

The readers behind `enable_eodhd_rates`:
`tradingagents/dataflows/eodhd.py::real_yield_points_eodhd` /
`::get_real_yield_rates_eodhd` (TIPS real yields) and
`::inflation_expectation_eodhd` (the single producer of nominal - real) —
plus P1 `::get_bill_auction_rates_eodhd` (Treasury bill auction detail) and P2
`::map_identifiers_eodhd` (FIGI / LEI / CUSIP; CIK only as a labelled
cross-check, never a path).

Offline: `eodhd._eodhd_get` and `federal_reserve._get` are mocked, so nothing
touches the network. The payload shapes are the measured ones (probed live
2026-09-19: 895 rows, 179 dates, tenors 5Y/7Y/10Y/20Y/30Y).
"""

from __future__ import annotations

from unittest import mock

import pytest

from tradingagents.dataflows import eodhd, federal_reserve
from tradingagents.dataflows.errors import NoMarketDataError

# Rule 5: every test file carries its own deadline; these reads are mocked, so
# 30s is generous.
pytestmark = pytest.mark.timeout(30)

# The measured response body: the whole history in one call, oldest-first,
# five tenors. Every query parameter is ignored by the vendor (probed), which
# is why the tenor filter below is client-side.
_REAL_BODY = {
    "meta": {"total": 12},
    "data": [
        {"date": "2026-09-16", "tenor": "5Y", "rate": 2.44},
        {"date": "2026-09-16", "tenor": "10Y", "rate": 2.68},
        {"date": "2026-09-17", "tenor": "5Y", "rate": 2.46},
        {"date": "2026-09-17", "tenor": "7Y", "rate": 2.52},
        {"date": "2026-09-17", "tenor": "10Y", "rate": 2.61},
        {"date": "2026-09-17", "tenor": "20Y", "rate": 2.87},
        {"date": "2026-09-17", "tenor": "30Y", "rate": 3.04},
        # a row whose rate will not parse: dropped, never carried as 0.0
        {"date": "2026-09-17", "tenor": "10Y", "rate": None},
        {"date": "2026-09-17", "tenor": "10Y", "rate": ""},
    ],
}

# The nominal leg's own CSV (newest-first, as home.treasury.gov serves it).
_TREASURY_CSV = (
    'Date,"1 Mo","2 Mo","3 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"\n'
    "09/18/2026,3.97,4.09,4.12,4.20,4.28,4.44,4.62,4.86,4.93,5.01,5.22,5.34\n"
    "09/17/2026,3.95,4.05,4.10,4.18,4.25,4.40,4.58,4.80,4.88,4.96,5.18,5.30\n"
)


def _resp(text="", status=200):
    r = mock.Mock()
    r.status_code = status
    r.text = text
    r.raise_for_status = mock.Mock()
    return r


def _patch_both(real_body=None, csv_text=_TREASURY_CSV):
    """Mock both vendor seams; nothing touches the network."""
    return (
        mock.patch.object(eodhd, "_eodhd_get", return_value=real_body or _REAL_BODY),
        mock.patch("requests.get", return_value=_resp(csv_text)),
    )


# ---------------------------------------------------------------------------
# The real-yield reader
# ---------------------------------------------------------------------------

def test_points_are_structured_and_oldest_first():
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        pts = eodhd.real_yield_points_eodhd()
    assert pts, "expected points"
    assert set(pts[0]) == {"date", "tenor", "rate"}
    assert [(p["date"], p["tenor"]) for p in pts] == sorted(
        (p["date"], p["tenor"]) for p in pts
    ), "series must read oldest-first"
    assert all(isinstance(p["rate"], float) for p in pts)


def test_tenor_filter_is_client_side_and_exact():
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        ten = eodhd.real_yield_points_eodhd("10Y")
    assert ten, "expected 10Y rows"
    assert {p["tenor"] for p in ten} == {"10Y"}
    # 2026-09-16 and 2026-09-17 have a 10Y; the two unparseable rows are dropped.
    assert [p["rate"] for p in ten] == [2.68, 2.61]


def test_unpublished_tenor_is_named_never_interpolated():
    """A tenor the vendor does not publish must raise, naming the real set."""
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre, pytest.raises(NoMarketDataError) as ei:
        eodhd.real_yield_points_eodhd("3M")
    msg = str(ei.value)
    assert "3M" in msg, "the requested tenor must be named"
    assert "5Y" in msg, "the published set must be named"


def test_unparseable_rate_is_dropped_not_zero():
    """A row whose rate will not parse is absent - `None` is never `0.0`."""
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        pts = eodhd.real_yield_points_eodhd("10Y")
    assert 0.0 not in [p["rate"] for p in pts]
    # 2 parseable 10Y rows out of 4 in the fixture (two are None/"").
    assert len(pts) == 2


def test_empty_payload_raises():
    p_eod, p_tre = _patch_both(real_body={"meta": {"total": 0}, "data": []})
    with p_eod, p_tre, pytest.raises(NoMarketDataError):
        eodhd.real_yield_points_eodhd()


def test_rendered_carries_the_date_and_the_tenor():
    """A rate without its date and tenor is not a rate."""
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        out = eodhd.get_real_yield_rates_eodhd("10Y")
    assert "2026-09-17" in out and "10Y" in out
    assert "| 2026-09-17 | 2.61 |" in out
    assert "Rows: 2" in out, "coverage must be stated"


def test_tail_bounds_the_rows_without_hiding_coverage():
    """A report head must not carry the whole series, and must say so."""
    long_body = {
        "meta": {"total": 0},
        "data": [
            {"date": f"2026-01-{d:02d}", "tenor": "10Y", "rate": 2.0 + d / 100}
            for d in range(1, 21)
        ],
    }
    p_eod, p_tre = _patch_both(real_body=long_body)
    with p_eod, p_tre:
        out = eodhd.get_real_yield_rates_eodhd("10Y", tail=3)
    rows = [ln for ln in out.splitlines() if ln.startswith("| 2026-")]
    assert len(rows) == 3, f"expected 3 rendered rows, got {len(rows)}"
    assert "| 2026-01-20 |" in out, "the tail must be the most recent rows"
    assert "| 2026-01-01 |" not in out
    assert "Rows: 20" in out, "the full read must still be stated"
    assert "20 dates" in out or "20 rows" in out, "the withheld count must be named"


def test_prefetched_legs_change_nothing_but_the_read_count():
    """Supplying both legs must produce the identical pairing."""
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        direct = eodhd.inflation_expectation_eodhd("10Y")
        # fetch the legs OUTSIDE the no-call block, then prove the pairing
        # itself touches neither vendor seam when they are supplied
        real_leg = eodhd.real_yield_points_eodhd("10Y")
        nominal_leg = federal_reserve.treasury_curve_points("2026-09-18")
        with mock.patch.object(eodhd, "_eodhd_get") as no_call, \
                mock.patch("requests.get") as no_http:
            supplied = eodhd.inflation_expectation_eodhd(
                "10Y", real_points=real_leg, nominal_curve=nominal_leg
            )
        # the supplied-leg call must not have touched either vendor seam
        assert not no_call.called, "the real leg was re-read"
        assert not no_http.called, "the nominal leg was re-read"
    assert supplied["nominal"] == direct["nominal"]
    assert supplied["real"] == direct["real"]
    assert supplied["expectation"] == direct["expectation"]
    assert supplied["aligned"] == direct["aligned"]


def test_prefetched_legs_still_pair_every_tenor():
    """One real read + one nominal read must serve all five tenors."""
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        real_leg = eodhd.real_yield_points_eodhd()
        nominal_leg = federal_reserve.treasury_curve_points("2026-09-18")
    got = {}
    for t in ("5Y", "10Y", "30Y"):
        r = eodhd.inflation_expectation_eodhd(
            t, real_points=real_leg, nominal_curve=nominal_leg
        )
        assert r["unavailable"] is None, r["unavailable"]
        got[t] = r["expectation"]
    assert got["5Y"] == pytest.approx(4.86 - 2.46)
    assert got["10Y"] == pytest.approx(5.01 - 2.61)
    assert got["30Y"] == pytest.approx(5.34 - 3.04)


def test_prefetched_leg_missing_the_tenor_is_unavailable():
    """A supplied series without the requested tenor is a named gap."""
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        real_leg = eodhd.real_yield_points_eodhd()
        nominal_leg = federal_reserve.treasury_curve_points("2026-09-18")
    r = eodhd.inflation_expectation_eodhd(
        "2Y", real_points=real_leg, nominal_curve=nominal_leg
    )
    assert r["expectation"] is None
    assert "no supplied rows for tenor '2Y'" in r["unavailable"]


# ---------------------------------------------------------------------------
# The pairing - the ONE producer of nominal - real
# ---------------------------------------------------------------------------

def test_expectation_is_the_subtraction_and_carries_both_dates():
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        r = eodhd.inflation_expectation_eodhd("10Y")
    assert r["nominal"] == 5.01  # 2026-09-18 row
    assert r["real"] == 2.61  # 2026-09-17 row
    assert r["expectation"] == pytest.approx(2.40)
    assert r["nominal_date"] == "2026-09-18"
    assert r["real_date"] == "2026-09-17"
    assert r["unavailable"] is None


def test_mismatched_dates_are_labelled_not_silent():
    """The two legs are a day apart in production; the gap must be visible."""
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        r = eodhd.inflation_expectation_eodhd("10Y")
    assert r["aligned"] is False
    assert r["gap_days"] == 1
    assert "nominal 10Y par yield" in r["basis"]
    assert "TIPS 10Y real yield" in r["basis"]


def test_aligned_when_both_legs_share_a_date():
    """With the nominal leg pinned to the real leg's date, aligned is True."""
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        r = eodhd.inflation_expectation_eodhd("10Y", "2026-09-17")
    assert r["nominal"] == 4.96
    assert r["nominal_date"] == "2026-09-17"
    assert r["aligned"] is True
    assert r["gap_days"] == 0


def test_missing_real_leg_is_unavailable_never_zero():
    """A dead real leg yields a reason, not a 0.0 risk-free rate."""
    with mock.patch.object(eodhd, "_eodhd_get", side_effect=RuntimeError("gateway down")):
        r = eodhd.inflation_expectation_eodhd("10Y")
    assert r["expectation"] is None
    assert r["real"] is None
    assert "real leg unavailable" in r["unavailable"]


def test_missing_nominal_leg_is_unavailable_never_zero():
    p_eod, p_tre = _patch_both()
    with p_eod, mock.patch("requests.get", side_effect=RuntimeError("treasury down")):
        r = eodhd.inflation_expectation_eodhd("10Y")
    assert r["expectation"] is None
    assert r["nominal"] is None
    assert "nominal leg unavailable" in r["unavailable"]


def test_tenor_absent_from_the_nominal_curve_is_named():
    """A tenor the nominal CSV lacks must be reported, not silently zeroed."""
    csv_short = (
        'Date,"1 Mo","3 Mo"\n'
        "09/18/2026,3.97,4.12\n"
    )
    p_eod, p_tre = _patch_both(csv_text=csv_short)
    with p_eod, p_tre:
        r = eodhd.inflation_expectation_eodhd("10Y")
    assert r["nominal"] is None
    assert r["expectation"] is None
    assert "no 10Y maturity" in r["unavailable"]


def test_expectation_moves_with_the_tenor():
    """The pairing is not a constant: each tenor reads its own two legs."""
    p_eod, p_tre = _patch_both()
    with p_eod, p_tre:
        five = eodhd.inflation_expectation_eodhd("5Y")
        thirty = eodhd.inflation_expectation_eodhd("30Y")
    assert five["expectation"] == pytest.approx(4.86 - 2.46)
    assert thirty["expectation"] == pytest.approx(5.34 - 3.04)
    assert five["expectation"] != thirty["expectation"]


# ---------------------------------------------------------------------------
# The nominal leg: one producer, two presentations
# ---------------------------------------------------------------------------

def test_treasury_points_are_structured_and_skip_blank_cells():
    with mock.patch("requests.get", return_value=_resp(_TREASURY_CSV)):
        curve = federal_reserve.treasury_curve_points("2026-09-18")
    assert curve["date"] == "2026-09-18"
    assert curve["as_of"] == "09/18/2026"
    assert curve["points"]["10 Yr"] == 5.01
    assert all(isinstance(v, float) for v in curve["points"].values())


def test_treasury_points_are_lookahead_safe():
    """The at-or-before rule must survive the refactor."""
    with mock.patch("requests.get", return_value=_resp(_TREASURY_CSV)):
        curve = federal_reserve.treasury_curve_points("2026-09-17")
    assert curve["date"] == "2026-09-17"
    assert curve["points"]["10 Yr"] == 4.96


def test_rendered_curve_still_comes_from_the_same_parse():
    """`get_treasury_curve` renders the structured read - one producer."""
    with mock.patch("requests.get", return_value=_resp(_TREASURY_CSV)):
        curve = federal_reserve.treasury_curve_points("2026-09-18")
        rendered = federal_reserve.get_treasury_curve("2026-09-18")
    for label, rate in curve["rows"]:
        assert f"| {label} | {rate} |" in rendered
    assert f"As of: {curve['as_of']}" in rendered


# ---------------------------------------------------------------------------
# P1 - the bill-auction reader (a bill curve point is not a note curve point)
# ---------------------------------------------------------------------------

# The measured auction shape: date, tenor, the auction's own discount/coupon
# and their averages, plus the auction identity (maturity_date, cusip). The
# third row's numerics are unparseable on purpose - they must stay None.
_BILL_BODY = {
    "meta": {"total": 3},
    "data": [
        {
            "date": "2026-09-18",
            "tenor": "13WK",
            "discount": 3.58,
            "coupon": 3.64,
            "avg_discount": 3.57,
            "avg_coupon": 3.63,
            "maturity_date": "2026-12-17",
            "cusip": "912797XX1",
        },
        {
            "date": "2026-09-18",
            "tenor": "4WK",
            "discount": 4.02,
            "coupon": 4.09,
            "avg_discount": 4.01,
            "avg_coupon": 4.08,
            "maturity_date": "2026-10-15",
            "cusip": "912797YY2",
        },
        {
            "date": "2026-09-17",
            "tenor": "13WK",
            "discount": None,
            "coupon": "",
            "avg_discount": None,
            "avg_coupon": None,
            "maturity_date": "2026-12-16",
            "cusip": "912797ZZ3",
        },
    ],
}


def test_bill_points_carry_the_auction_identity():
    """The point of the bill read is the auction identity, not a curve point."""
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_BILL_BODY):
        pts = eodhd._bill_auction_points_eodhd("13WK")
    assert set(pts[0]) == {
        "date",
        "tenor",
        "discount",
        "coupon",
        "avg_discount",
        "avg_coupon",
        "maturity_date",
        "cusip",
    }, "every field the design names must be carried"
    assert [p["date"] for p in pts] == ["2026-09-17", "2026-09-18"], "oldest-first"
    assert pts[-1]["cusip"] == "912797XX1"
    assert pts[-1]["maturity_date"] == "2026-12-17"


def test_bill_tenor_filter_is_client_side_and_exact():
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_BILL_BODY):
        four = eodhd._bill_auction_points_eodhd("4WK")
    assert {p["tenor"] for p in four} == {"4WK"}
    assert [p["cusip"] for p in four] == ["912797YY2"]


def test_bill_missing_rate_is_none_never_zero():
    """A missing/blank discount is absent - `None` is never `0.0`."""
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_BILL_BODY):
        pts = eodhd._bill_auction_points_eodhd("13WK")
    assert [p["discount"] for p in pts] == [None, 3.58]
    assert [p["coupon"] for p in pts] == [None, 3.64]
    assert 0.0 not in [p["discount"] for p in pts]


def test_bill_tenor_that_is_not_a_bill_is_named_never_interpolated():
    """`10Y` is a note tenor: it must raise, naming the published bill set."""
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_BILL_BODY), pytest.raises(
        NoMarketDataError
    ) as ei:
        eodhd._bill_auction_points_eodhd("10Y")
    msg = str(ei.value)
    assert "10Y" in msg, "the requested tenor must be named"
    assert "13WK" in msg and "52WK" in msg, "the published set must be named"


def test_bill_empty_payload_raises():
    with mock.patch.object(
        eodhd, "_eodhd_get", return_value={"meta": {"total": 0}, "data": []}
    ), pytest.raises(NoMarketDataError):
        eodhd._bill_auction_points_eodhd()


def test_bill_rendered_curve_prints_date_tenor_and_cusip():
    """The default render is the current bill curve: one row per tenor."""
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_BILL_BODY):
        out = eodhd.get_bill_auction_rates_eodhd()
    assert "| 13WK | 2026-09-18 | 3.58 | 3.64 | 2026-12-17 | 912797XX1 |" in out
    assert "| 4WK | 2026-09-18 | 4.02 |" in out
    assert "Rows: 3" in out, "coverage must be stated"
    assert "Coverage: 2026-09-17 to 2026-09-18" in out
    assert "a bill curve point is not a note curve point" in out


def test_bill_tail_bounds_rows_without_hiding_coverage():
    long_body = {
        "meta": {"total": 0},
        "data": [
            {
                "date": f"2026-08-{d:02d}",
                "tenor": "13WK",
                "discount": 3.0 + d / 100,
                "coupon": None,
                "avg_discount": None,
                "avg_coupon": None,
                "maturity_date": None,
                "cusip": None,
            }
            for d in range(1, 21)
        ],
    }
    with mock.patch.object(eodhd, "_eodhd_get", return_value=long_body):
        out = eodhd.get_bill_auction_rates_eodhd("13WK", tail=3)
    rows = [ln for ln in out.splitlines() if ln.startswith("| 2026-")]
    assert len(rows) == 3, f"expected 3 rendered rows, got {len(rows)}"
    assert "| 2026-08-20 |" in out, "the tail must be the most recent rows"
    assert "| 2026-08-01 |" not in out
    assert "Rows: 20" in out, "the full read must still be stated"
    assert "of 20 rows" in out, "the withheld count must be named"


def test_bill_rendered_series_keeps_the_tenor_on_every_row():
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_BILL_BODY):
        out = eodhd.get_bill_auction_rates_eodhd("13WK")
    assert "Tenor(s): 13WK" in out
    assert "| 2026-09-18 | 3.58 | 3.64 | 3.57 | 3.63 | 2026-12-17 | 912797XX1 |" in out
    # the unparseable row renders `-`, not a fabricated 0.0
    assert "| 2026-09-17 | - | - | - | - | 2026-12-16 | 912797ZZ3 |" in out
    assert "0.0" not in out


# ---------------------------------------------------------------------------
# P2 - the identifier join (FIGI / LEI / CUSIP; CIK is a labelled cross-check)
# ---------------------------------------------------------------------------

# `filter[isin]` maps one US ISIN to EVERY listing (18 rows measured live), so
# row 0 is a foreign listing: taking it would silently pick the wrong row.
_ID_BODY = {
    "data": [
        {
            "symbol": "AAPL.MX",
            "isin": "US0378331005",
            "figi": "BBG000B9XRY4",
            "lei": "HWUPKR0MPOU8FGXBT394",
            "cusip": "037833100",
            "cik": "0000320193",
        },
        {
            "symbol": "AAPL.US",
            "isin": "US0378331005",
            "figi": "BBG000B9XRY4",
            "lei": "HWUPKR0MPOU8FGXBT394",
            "cusip": "037833100",
            "cik": "0000320193",
        },
        {
            "symbol": "APC.DE",
            "isin": "US0378331005",
            "figi": "BBG000B9XRY4",
            "lei": "HWUPKR0MPOU8FGXBT394",
            "cusip": "037833100",
            "cik": "0000320193",
        },
    ]
}


def test_id_mapping_by_symbol_returns_the_three_new_identifiers():
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_ID_BODY):
        got = eodhd.map_identifiers_eodhd(symbol="AAPL.US")
    assert got["listing"] == "AAPL.US"
    assert got["figi"] == "BBG000B9XRY4"
    assert got["lei"] == "HWUPKR0MPOU8FGXBT394"
    assert got["cusip"] == "037833100"
    assert got["unavailable"] is None
    assert got["rows"] == 3, "the returned row count must be visible"


def test_id_mapping_picks_the_primary_listing_not_row_zero():
    """An ISIN maps to every listing; row 0 is a foreign listing here."""
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_ID_BODY):
        got = eodhd.map_identifiers_eodhd(isin="US0378331005")
    assert got["listing"] == "AAPL.US", "the primary (.US) listing must be selected"
    assert got["listing"] != _ID_BODY["data"][0]["symbol"]


def test_id_mapping_ambiguous_selection_is_named_not_row_zero():
    """No primary listing and more than one candidate -> a named gap."""
    body = {
        "data": [
            dict(_ID_BODY["data"][0], symbol="AAPL.MX"),
            dict(_ID_BODY["data"][2], symbol="APC.DE"),
        ]
    }
    with mock.patch.object(eodhd, "_eodhd_get", return_value=body):
        got = eodhd.map_identifiers_eodhd(isin="US0378331005")
    assert got["figi"] is None, "an ambiguous read must not return a row's identifiers"
    assert "ambiguous" in got["unavailable"]
    assert "none primary (.US)" in got["unavailable"]


def test_id_mapping_requires_exactly_one_query():
    with pytest.raises(ValueError):
        eodhd.map_identifiers_eodhd()
    with pytest.raises(ValueError):
        eodhd.map_identifiers_eodhd(isin="US0378331005", symbol="AAPL.US")


def test_id_mapping_absent_field_is_none_never_empty_string():
    body = {"data": [{"symbol": "ZZZZ.US", "isin": "US0000000000", "figi": "BBG000000001"}]}
    with mock.patch.object(eodhd, "_eodhd_get", return_value=body):
        got = eodhd.map_identifiers_eodhd(symbol="ZZZZ.US")
    assert got["figi"] == "BBG000000001"
    assert got["lei"] is None and got["cusip"] is None, "absent must stay None"
    assert got["cik_cross_check"] is None


def test_id_mapping_vendor_failure_is_reported_not_raised():
    with mock.patch.object(eodhd, "_eodhd_get", side_effect=RuntimeError("gateway down")):
        got = eodhd.map_identifiers_eodhd(symbol="AAPL.US")
    assert got["figi"] is None
    assert "identifier read failed" in got["unavailable"]


def test_id_mapping_empty_payload_is_reported_not_raised():
    with mock.patch.object(eodhd, "_eodhd_get", return_value={"data": []}):
        got = eodhd.map_identifiers_eodhd(symbol="AAPL.US")
    assert "no identifier rows" in got["unavailable"]


def test_cik_is_a_labelled_cross_check_with_no_second_path():
    """`sec_edgar._cik_for` owns the CIK join; EODHD's value is a cross-check."""
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_ID_BODY):
        got = eodhd.map_identifiers_eodhd(symbol="AAPL.US")
    assert "cik" not in got, "the CIK must never be returned as an identifier"
    assert got["cik_cross_check"] == "0000320193", "the vendor value is still viewable"
    # No public eodhd surface resolves a CIK: a second path is the rule-15
    # violation the design demotes.
    assert not [n for n in dir(eodhd) if "cik" in n.lower()]
