"""P0 of `docs/design_eodhd_unused_surface.md`, offline.

The readers behind `enable_eodhd_rates`:
`tradingagents/dataflows/eodhd.py::real_yield_points_eodhd` /
`::get_real_yield_rates_eodhd` (TIPS real yields) and
`::inflation_expectation_eodhd` (the single producer of nominal - real).

Offline: `eodhd._eodhd_get` and `federal_reserve._get` are mocked, so nothing
touches the network. The payload shapes are the measured ones (probed live
2026-09-19: 895 rows, 179 dates, tenors 5Y/7Y/10Y/20Y/30Y).
"""

from __future__ import annotations

from unittest import mock

import pytest

from tradingagents.dataflows import eodhd, federal_reserve
from tradingagents.dataflows.errors import NoMarketDataError

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
