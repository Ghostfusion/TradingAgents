"""Window / look-ahead / data-integrity regressions (defect-audit phase C).

Each test reproduces one defect these modules shipped with, and fails on the
pre-fix code:

* ``stockdata`` EOD / news validated the dates then neither sent nor applied
  them, so a backtest window got the vendor's default (recent) rows;
* ``massive`` wrapped its vendor call in ``except Exception`` and returned the
  "upgrade your plan" string for a 429/timeout the router counts as served;
* ``market_data_validator.live_price_sanity``'s OUTSIDE branch was unreachable
  (an in-buffer print past the bar edge was labelled with the wrong band);
* ``yfinance_options._nearest_expiry`` fell back to the FARTHEST expiry;
* ``market_position_tools._parse_statement_rows`` turned an unparseable cell
  into a fabricated ``0.0`` that then entered sums/deltas;
* ``stockstats_utils._clean_dataframe`` ``bfill``-ed an early row from a later
  (possibly post-as-of) row;
* ``date_window.in_window`` kept an undated item for a window that ended
  yesterday (24h slack).

Hermetic: every HTTP/vendor seam is stubbed; the only clock dependency is a
monkeypatched ``datetime`` in the date-window test.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import mock

import pandas as pd
import pytest

from tradingagents.agents.utils import market_position_tools as mpt
from tradingagents.dataflows import (
    date_window as dw,
    market_data_validator as mdv,
    massive,
    stockdata,
    stockstats_utils as su,
)
from tradingagents.dataflows.errors import VendorRateLimitError
from tradingagents.dataflows.massive import MassiveNotConfiguredError
from tradingagents.dataflows.yfinance_options import _nearest_expiry

pytestmark = pytest.mark.timeout(120)


def _resp(payload, status=200):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = payload
    return r


# ---------------------------------------------------------------------------
# stockdata: the requested window must reach the vendor AND be enforced locally
# ---------------------------------------------------------------------------


@pytest.fixture()
def _sd_key(monkeypatch):
    monkeypatch.setenv("STOCKDATA_API_KEY", "sd_test")
    monkeypatch.setattr(stockdata, "stockdata_api_key", lambda: "sd_test")


def test_stockdata_eod_applies_requested_window(_sd_key):
    payload = {
        "data": [
            {"date": "2026-09-01T00:00:00.000Z", "open": 1.0, "high": 1.0,
             "low": 1.0, "close": 1.0, "volume": 1},  # after end_date
            {"date": "2026-08-15T00:00:00.000Z", "open": 2.0, "high": 2.0,
             "low": 2.0, "close": 2.0, "volume": 2},  # inside
            {"date": "2026-07-01T00:00:00.000Z", "open": 3.0, "high": 3.0,
             "low": 3.0, "close": 3.0, "volume": 3},  # before start_date
        ]
    }
    with mock.patch.object(stockdata, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(payload)
        out = stockdata.get_stock_data_stockdata("AAPL", "2026-08-01", "2026-08-20")
        params = mreq.get.call_args[1]["params"]

    assert "2026-08-15" in out
    assert "2026-09-01" not in out  # look-ahead row excluded
    assert "2026-07-01" not in out  # pre-window row excluded
    assert params["symbols"] == "AAPL"
    assert params["date_from"] == "2026-08-01"
    assert params["date_to"] == "2026-08-20"


def test_stockdata_news_applies_requested_window(_sd_key):
    payload = {
        "data": [
            {"title": "FUTURE ARTICLE", "date": "2026-09-02", "source": "x",
             "description": "d"},
            {"title": "INSIDE ARTICLE", "date": "2026-08-15", "source": "y",
             "description": "d"},
            {"title": "PAST ARTICLE", "date": "2026-07-01", "source": "z",
             "description": "d"},
        ]
    }
    with mock.patch.object(stockdata, "_requests", spec=True) as mreq:
        mreq.get.return_value = _resp(payload)
        out = stockdata.get_news_stockdata("AAPL", "2026-08-01", "2026-08-20")
        params = mreq.get.call_args[1]["params"]

    assert "INSIDE ARTICLE" in out
    assert "FUTURE ARTICLE" not in out  # look-ahead article excluded
    assert "PAST ARTICLE" not in out    # pre-window article excluded
    assert params["published_after"] == "2026-08-01"
    assert params["published_before"] == "2026-08-20"


# ---------------------------------------------------------------------------
# massive: transport/throttle errors must propagate, not become "upgrade"
# ---------------------------------------------------------------------------


def _massive_key(monkeypatch):
    monkeypatch.setattr(massive, "massive_api_key", lambda: "k")
    monkeypatch.setattr(massive.time, "sleep", lambda *_: None)


def test_massive_ratios_429_propagates(monkeypatch):
    _massive_key(monkeypatch)
    with (
        mock.patch.object(massive.requests, "get", return_value=mock.Mock(status_code=429)),
        pytest.raises(VendorRateLimitError),
    ):
        massive.get_ratios_massive("AAPL")


def test_massive_snapshot_5xx_propagates(monkeypatch):
    _massive_key(monkeypatch)
    with (
        mock.patch.object(massive.requests, "get", return_value=mock.Mock(status_code=503)),
        pytest.raises(VendorRateLimitError),
    ):
        massive.get_market_snapshot_massive("AAPL")


def test_massive_top_movers_timeout_propagates(monkeypatch):
    _massive_key(monkeypatch)
    with mock.patch.object(
        massive.requests, "get", side_effect=massive.requests.Timeout("t")
    ), pytest.raises(VendorRateLimitError):
        massive.get_top_movers_massive("gainers", 5)


def test_massive_entitlement_403_still_degrades():
    """The documented 403/plan case must keep returning the honest advisory."""
    with mock.patch.object(
        massive, "_get", side_effect=MassiveNotConfiguredError("403 plan")
    ):
        out = massive.get_ratios_massive("AAPL")
    assert "upgrade at massive.com/pricing" in out


# ---------------------------------------------------------------------------
# live_price_sanity: all four bands reachable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("live", "expected_band"),
    [
        (105.0, "INSIDE verified bar"),        # inside [100, 110]
        (97.0, "OUTSIDE verified bar"),        # below bar, inside 5% buffer (>=95)
        (113.0, "OUTSIDE verified bar"),       # above bar, inside 5% buffer (<=115.5)
        (90.0, "BELOW verified day-low"),      # beyond the buffer
        (120.0, "ABOVE verified day-high"),    # beyond the buffer
    ],
)
def test_live_price_sanity_bands(live, expected_band):
    out = mdv.live_price_sanity(live, 100.0, 110.0, buffer_pct=0.05)
    assert expected_band in out


def test_live_price_sanity_unknown_inputs():
    out = mdv.live_price_sanity(None, 100.0, 110.0)
    assert "insufficient data" in out


# ---------------------------------------------------------------------------
# yfinance_options: "nearest expiry" must be the nearest, not the farthest
# ---------------------------------------------------------------------------


def test_nearest_expiry_fallback_is_nearest_not_farthest():
    expiries = ["2026-09-18", "2026-10-16", "2026-11-20"]
    # curr_date is past every expiry, so none clears the 3-day cutoff; the
    # fallback must be the nearest available expiry (ascending order assumed).
    assert _nearest_expiry(expiries, "2026-12-01") == "2026-09-18"


def test_nearest_expiry_prefers_first_beyond_cutoff():
    expiries = ["2026-09-18", "2026-10-16", "2026-11-20"]
    assert _nearest_expiry(expiries, "2026-10-01") == "2026-10-16"


# ---------------------------------------------------------------------------
# market_position_tools: an unparseable cell is not a fabricated 0.0
# ---------------------------------------------------------------------------


def test_parse_statement_rows_marks_unparseable_cell_none():
    rows = mpt._parse_statement_rows("Repurchase Of Common Stock,-100,N/A,-90\n")
    assert dict(rows)["Repurchase Of Common Stock"] == [-100.0, None, -90.0]


def test_buyback_tool_does_not_sum_or_difference_fabricated_zeros(monkeypatch):
    cf = "Repurchase Of Common Stock,-100000000,N/A,-90000000,-80000000\n"
    bs = "Ordinary Shares Number,N/A,1000000,900000,800000,700000\n"

    def fake_route(method, *args, **kwargs):
        return cf if method == "get_cashflow" else bs

    monkeypatch.setattr(mpt, "route_to_vendor", fake_route)
    out = mpt.get_share_buyback_authorization.invoke({"ticker": "TEST"})

    # The missing quarter is omitted, not rendered as a real 0M quarter.
    assert "-100M, -90M, -80M" in out
    # Shares delta is computed from the real latest print (1.0M -> 0.7M), not
    # from a fabricated 0 latest.
    assert "4-quarter change 300,000 shares" in out


def test_buyback_tool_all_unparseable_shares_row_degrades(monkeypatch):
    bs = "Ordinary Shares Number,N/A,--,N/A\n"

    def fake_route(method, *args, **kwargs):
        return "" if method == "get_cashflow" else bs

    monkeypatch.setattr(mpt, "route_to_vendor", fake_route)
    out = mpt.get_share_buyback_authorization.invoke({"ticker": "TEST"})
    assert "no numeric quarters" in out  # honest, not a crash or a fake 0


# ---------------------------------------------------------------------------
# stockstats_utils: no backfill from a later (post-as-of) row
# ---------------------------------------------------------------------------


def test_clean_dataframe_does_not_backfill_from_later_row():
    df = pd.DataFrame({
        "Date": pd.to_datetime(["2026-08-10", "2026-08-11", "2026-08-12"]),
        "Open": [float("nan"), 20.0, 30.0],
        "High": [11.0, 21.0, 31.0],
        "Low": [9.0, 19.0, 29.0],
        "Close": [10.5, 20.5, 30.5],
        "Volume": [1000.0, 2000.0, 3000.0],
    })
    cleaned = su._clean_dataframe(df)

    # 2026-08-10's missing Open must stay missing: the next row can be dated
    # after the run's as-of date, so backfilling it would leak future data.
    assert pd.isna(cleaned.iloc[0]["Open"])


def test_clean_dataframe_still_forward_fills_interior_gaps():
    df = pd.DataFrame({
        "Date": pd.to_datetime(["2026-08-10", "2026-08-11", "2026-08-12"]),
        "Open": [10.0, float("nan"), 30.0],
        "High": [11.0, 21.0, 31.0],
        "Low": [9.0, 19.0, 29.0],
        "Close": [10.5, 20.5, 30.5],
        "Volume": [1000.0, 2000.0, 3000.0],
    })
    cleaned = su._clean_dataframe(df)
    assert cleaned.iloc[1]["Open"] == 10.0  # filled from the earlier row


# ---------------------------------------------------------------------------
# date_window: undated items are not admitted for a window that ended yesterday
# ---------------------------------------------------------------------------


def test_in_window_rejects_undated_for_window_ended_yesterday(monkeypatch):
    fixed = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed if tz is None else fixed.astimezone(tz)

    monkeypatch.setattr(dw, "datetime", _Clock)

    yesterday = fixed - timedelta(days=1)
    assert dw.in_window(None, fixed - timedelta(days=7), yesterday) is False
    # A window that still reaches the present day keeps undated items (live).
    assert dw.in_window(None, fixed - timedelta(days=7), fixed) is True
