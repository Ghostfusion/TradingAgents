"""Moomoo vendor contract fixes (phase C / defect audit).

Four defects, each with the behaviour it must not regress:

1. ``_format_financials`` must raise ``NoMarketDataError`` on an empty report
   list (like every sibling vendor) instead of returning a placeholder string
   that the router serves — and caches — as if moomoo had answered, so the
   yfinance/tiingo/alpha_vantage fallbacks are never consulted.
2. ``get_news_moomoo`` must trim its (undated server-side) news frame to the
   requested window and raise ``NoMarketDataError`` when nothing remains.
3. ``_check_ret`` must classify a throttled/quota message as a transient
   ``VendorRateLimitError``, not a permanent "not configured" verdict.
4. ``_cap_open_ctxs`` must not leave a closed context in its owner thread's
   thread-local, so ``_ensure_ctx`` never hands out an evicted context.

Hermetic: the moomoo SDK and the router seam are stubbed; no OpenD, no network,
no wall-clock dependence.
"""

import sys
import threading
import types
from datetime import datetime, timezone
from unittest import mock

import pandas as pd
import pytest

import tradingagents.dataflows.config as config_module
from tradingagents.dataflows import interface, moomoo
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import NoMarketDataError, VendorRateLimitError
from tradingagents.dataflows.moomoo import MoomooNotConfiguredError
from tradingagents.dataflows.vendor_cache import vendor_cache

RET_OK = 0


@pytest.fixture(autouse=True)
def _clean_env():
    config_module.reset_config()
    # The developer's .env may enable autostart; tests must never launch OpenD.
    set_config({"moomoo_autostart": False})
    vendor_cache.clear()
    moomoo._close_ctx()
    moomoo._autostart_attempted = False
    moomoo._last_probe_fail = 0.0
    yield
    with moomoo._ctx_lock:
        moomoo._live_ctxs.clear()
    moomoo._tls.moomoo_ctx = None
    config_module.reset_config()


# ---------------------------------------------------------------------------
# 1. Empty financials raise a typed error (router can fall through)
# ---------------------------------------------------------------------------


def test_format_financials_empty_reports_raises():
    with pytest.raises(NoMarketDataError) as excinfo:
        moomoo._format_financials(
            "US.AAPL", {"structure_list": [], "report_list": []}, "Income Statement"
        )
    assert excinfo.value.canonical == "US.AAPL"
    assert "Income Statement" in excinfo.value.detail


def test_format_financials_all_reports_after_cutoff_raises():
    data = {
        "structure_list": [],
        "report_list": [{"date_time_str": "2026-03-31", "item_list": []}],
    }
    with pytest.raises(NoMarketDataError):
        moomoo._format_financials("US.AAPL", data, "Balance Sheet", curr_date="2025-12-31")


def test_get_fundamentals_propagates_no_data_error():
    ctx = mock.Mock()
    ctx.get_financials_statements.return_value = (
        RET_OK,
        {"structure_list": [], "report_list": []},
    )
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        pytest.raises(NoMarketDataError) as excinfo,
    ):
        moomoo.get_fundamentals_moomoo("AAPL", "2025-06-30")
    assert excinfo.value.symbol == "AAPL"


def test_router_falls_through_when_moomoo_fundamentals_are_empty():
    """The router must consult the next vendor, not cache a moomoo placeholder."""
    ctx = mock.Mock()
    ctx.get_financials_statements.return_value = (
        RET_OK,
        {"structure_list": [], "report_list": []},
    )
    set_config({"data_vendors": {"fundamental_data": "moomoo,yfinance"}})
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        mock.patch.dict(
            interface.VENDOR_METHODS,
            {
                "get_fundamentals": {
                    "moomoo": moomoo.get_fundamentals_moomoo,
                    "yfinance": lambda *a, **k: "YF_FUNDAMENTALS",
                }
            },
            clear=False,
        ),
    ):
        out = interface.route_to_vendor("get_fundamentals", "AAPL", "2025-06-30")
    assert out == "YF_FUNDAMENTALS"


# ---------------------------------------------------------------------------
# 2. News respects the requested window
# ---------------------------------------------------------------------------


def _news_ctx(rows) -> mock.Mock:
    ctx = mock.Mock()
    ctx.get_search_news.return_value = (RET_OK, pd.DataFrame(rows))
    return ctx


def _news_row(title: str, when: str) -> dict:
    return {"title": title, "content": "", "time": when, "source": "TestWire"}


def test_news_filters_out_of_window_rows():
    ctx = _news_ctx(
        [
            _news_row("IN_WINDOW_HEADLINE", "2020-03-10 10:00:00"),
            _news_row("OUT_OF_WINDOW_HEADLINE", "2020-09-10 10:00:00"),
        ]
    )
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
    ):
        out = moomoo.get_news_moomoo("AAPL", "2020-03-01", "2020-03-31")
    assert "IN_WINDOW_HEADLINE" in out
    assert "OUT_OF_WINDOW_HEADLINE" not in out


def test_news_raises_when_nothing_in_window():
    ctx = _news_ctx([_news_row("OLD_HEADLINE", "2020-01-05 10:00:00")])
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        pytest.raises(NoMarketDataError) as excinfo,
    ):
        moomoo.get_news_moomoo("AAPL", "2020-06-01", "2020-06-30")
    assert excinfo.value.canonical == "US.AAPL"


def test_news_raises_on_empty_frame():
    ctx = _news_ctx([])
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        pytest.raises(NoMarketDataError),
    ):
        moomoo.get_news_moomoo("AAPL", "2020-06-01", "2020-06-30")


def test_news_accepts_epoch_seconds_string():
    # moomoo documents a formatted ``time`` string, but an epoch-seconds string
    # must not be silently misparsed (pd.to_datetime would read it as 1970 ns)
    # and dropped as out-of-window.
    epoch = int(datetime(2020, 3, 10, 10, 0, tzinfo=timezone.utc).timestamp())
    ctx = _news_ctx(
        [
            _news_row("EPOCH_HEADLINE", str(epoch)),
            _news_row("OUT_OF_WINDOW_HEADLINE", "2020-09-10 10:00:00"),
        ]
    )
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
    ):
        out = moomoo.get_news_moomoo("AAPL", "2020-03-01", "2020-03-31")
    assert "EPOCH_HEADLINE" in out
    assert "OUT_OF_WINDOW_HEADLINE" not in out


# ---------------------------------------------------------------------------
# 3. Throttle messages are rate limits, not "not configured"
# ---------------------------------------------------------------------------


def test_no_available_quota_is_rate_limit():
    with pytest.raises(VendorRateLimitError):
        moomoo._check_ret(-1, "no available quota for this request", "AAPL", "US.AAPL")


def test_login_message_still_not_configured():
    with pytest.raises(MoomooNotConfiguredError):
        moomoo._check_ret(-1, "please login first", "AAPL", "US.AAPL")


def test_no_available_account_still_not_configured():
    with pytest.raises(MoomooNotConfiguredError):
        moomoo._check_ret(-1, "no available account", "AAPL", "US.AAPL")


# ---------------------------------------------------------------------------
# 4. Evicted contexts are never handed out again
# ---------------------------------------------------------------------------


class _FakeQuoteContext:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False

    def close(self):
        self.closed = True


def _fake_sdk() -> types.ModuleType:
    mod = types.ModuleType("moomoo")
    mod.OpenQuoteContext = _FakeQuoteContext
    return mod


def test_evicted_ctx_is_not_handed_out_again():
    with (
        mock.patch.dict(sys.modules, {"moomoo": _fake_sdk()}),
        mock.patch.object(moomoo, "_probe_or_use_cache", return_value=True),
        mock.patch.object(moomoo, "_max_open_ctxs", return_value=1),
    ):
        first = moomoo._ensure_ctx()
        assert moomoo._tls.moomoo_ctx is first
        with mock.patch.object(moomoo, "_max_open_ctxs", return_value=0):
            moomoo._cap_open_ctxs()
        assert first.closed
        assert moomoo._tls.moomoo_ctx is None

        second = moomoo._ensure_ctx()
        assert second is not first
        assert second.closed is False
        assert second in moomoo._live_ctxs


def test_ctx_evicted_by_another_thread_is_rebuilt():
    """The victim's thread-local cannot be cleared from the evicting thread."""
    results = {}
    ready = threading.Event()
    rebuild = threading.Event()

    def worker():
        results["first"] = moomoo._ensure_ctx()
        ready.set()
        rebuild.wait(5)
        results["second"] = moomoo._ensure_ctx()

    with (
        mock.patch.dict(sys.modules, {"moomoo": _fake_sdk()}),
        mock.patch.object(moomoo, "_probe_or_use_cache", return_value=True),
        mock.patch.object(moomoo, "_max_open_ctxs", return_value=1),
    ):
        thread = threading.Thread(target=worker)
        thread.start()
        assert ready.wait(5)
        with mock.patch.object(moomoo, "_max_open_ctxs", return_value=0):
            moomoo._cap_open_ctxs()
        rebuild.set()
        thread.join(5)
        assert not thread.is_alive()

    assert results["first"] is not results["second"]
    assert results["first"].closed
    assert results["second"].closed is False
