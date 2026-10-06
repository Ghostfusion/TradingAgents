"""EODHD status classification, retry policy, symbol resolution and the quota ledger.

The four defects/features this pins, all measured against the vendor live 2026-10-06:

1. A **403 is a plan gate, not a credential fault**. Seven datasets answered 403 on a
   working key ("This data is not available for your subscription plan." / "...no
   access to Historical Market Cap Data Feed."), so the old message telling the
   operator to check ``EODHD_API_KEY`` sent them down the wrong path.
2. A **402 is not transient**: it was retried twice, with no sleep, and typed as a rate
   limit. It is now raised on the first attempt, naming the daily quota, because a
   retry inside the same run cannot succeed against a spent UTC day.
3. ``Retry-After`` (RFC 7231 s7.1.3, both forms) is honoured on a 429, and a 5xx backs
   off exponentially instead of being hammered immediately.
4. ``resolve_symbol_eodhd`` resolves a listing by rule instead of assuming the vendor
   symbol from the ticker, and ``eodhd_quota`` reports the plan's allowance and this
   process's own weighted spend from the one endpoint EODHD does not count.

Offline: the HTTP layer and ``_eodhd_get`` are mocked, so nothing touches the network.
"""

from __future__ import annotations

from unittest import mock

import pytest

from tradingagents.dataflows import eodhd, eodhd_quota
from tradingagents.dataflows.errors import (
    VendorNotConfiguredError,
    VendorRateLimitError,
)

pytestmark = pytest.mark.timeout(60)


def _resp(status, *, body=None, headers=None, text=""):
    r = mock.Mock()
    r.status_code = status
    r.headers = dict(headers or {})
    r.text = text
    if body is None:
        r.json.side_effect = ValueError("no json body")
    else:
        r.json.return_value = body
    return r


@pytest.fixture(autouse=True)
def _clean_ledger():
    eodhd_quota._reset()
    yield
    eodhd_quota._reset()


# ---------------------------------------------------------------------------
# Item 1: 403 is an entitlement problem on a valid key; 401 is the credential
# ---------------------------------------------------------------------------

def test_403_names_the_plan_and_never_the_key():
    resp = _resp(
        403,
        body={"message": "This data is not available for your subscription plan."},
    )
    with mock.patch("requests.get", return_value=resp), pytest.raises(
        VendorNotConfiguredError
    ) as ei:
        eodhd._eodhd_get("spreads/funding-stress", {})
    msg = str(ei.value)
    assert "plan does not include" in msg
    assert "VALID" in msg, "the operator must be told the key is fine"
    assert "check EODHD_API_KEY" not in msg, "the old misdiagnosis must not return"
    assert "not available for your subscription plan" in msg, (
        "the vendor's own words are the diagnosis and must survive"
    )


def test_401_still_names_the_credential():
    with mock.patch("requests.get", return_value=_resp(401)), pytest.raises(
        VendorNotConfiguredError
    ) as ei:
        eodhd._eodhd_get("eod/AAPL", {})
    msg = str(ei.value)
    assert "401" in msg and "EODHD_API_KEY" in msg
    assert "plan does not include" not in msg, "401 is not a plan gate"


# ---------------------------------------------------------------------------
# Item 2: 402 is raised at once, typed as a quota wall, not retried as a throttle
# ---------------------------------------------------------------------------

def test_402_is_not_retried_and_names_the_quota():
    calls = []

    def _get(*_a, **_kw):
        calls.append(1)
        return _resp(402, body={"error": "API limit used up"})

    slept = []
    with mock.patch("requests.get", side_effect=_get), mock.patch.object(
        eodhd.time, "sleep", slept.append
    ), pytest.raises(VendorRateLimitError) as ei:
        eodhd._eodhd_get("eod/AAPL", {})
    assert len(calls) == 1, "a 402 must not be retried inside the run"
    assert slept == [], "and must not sleep on the way out"
    msg = str(ei.value)
    assert "quota exhausted" in msg and "402" in msg
    assert "eod/AAPL" in msg and "API limit used up" in msg


def test_429_honours_retry_after_delay_seconds():
    slept = []
    with mock.patch(
        "requests.get", return_value=_resp(429, headers={"Retry-After": "1"})
    ), mock.patch.object(eodhd.time, "sleep", slept.append), pytest.raises(
        VendorRateLimitError
    ):
        eodhd._eodhd_get("eod/AAPL", {})
    # Two retries, each obeying the header rather than the fixed 2s/4s ladder.
    assert slept == [1.0, 1.0], slept


def test_429_honours_retry_after_http_date():
    slept = []
    # An HTTP-date in the past yields 0.0, not a negative sleep and not the fallback.
    with mock.patch(
        "requests.get",
        return_value=_resp(429, headers={"Retry-After": "Thu, 01 Dec 2020 00:00:00 GMT"}),
    ), mock.patch.object(eodhd.time, "sleep", slept.append), pytest.raises(
        VendorRateLimitError
    ):
        eodhd._eodhd_get("eod/AAPL", {})
    assert slept == [0.0, 0.0], slept


def test_retry_after_is_absent_never_zero():
    """An unparseable or missing header falls back to backoff, it is not read as 0."""
    assert eodhd._retry_after_seconds(None) is None
    assert eodhd._retry_after_seconds("") is None
    assert eodhd._retry_after_seconds("not-a-date") is None
    assert eodhd._retry_after_seconds(mock.Mock()) is None, "a Mock header is absent"
    assert eodhd._retry_after_seconds("120") == 60.0, "capped at a minute"
    assert eodhd._retry_after_seconds("-5") == 0.0


def test_5xx_backs_off_before_retrying():
    slept = []
    with mock.patch("requests.get", return_value=_resp(503)), mock.patch.object(
        eodhd.time, "sleep", slept.append
    ), pytest.raises(VendorRateLimitError):
        eodhd._eodhd_get("eod/AAPL", {})
    assert slept == [2.0, 4.0], "a transient 5xx retries with exponential backoff"


def test_non_retryable_4xx_still_raises_after_the_attempts():
    calls = []
    with mock.patch("requests.get", side_effect=lambda *a, **k: (calls.append(1), _resp(404))[1]), \
            pytest.raises(VendorRateLimitError):
        eodhd._eodhd_get("eod/AAPL", {})
    assert len(calls) == eodhd._MAX_RETRIES + 1, "unchanged: 4xx retries twice"


# ---------------------------------------------------------------------------
# Item 3: symbol resolution by rule, never by position
# ---------------------------------------------------------------------------

# The measured /search rows (live 2026-10-06).
_TSM_ROWS = [
    {"Code": "TSM", "Exchange": "US", "Type": "Common Stock", "isPrimary": False,
     "ISIN": "US8740391003", "Name": "Taiwan Semiconductor Manufacturing"},
    {"Code": "TSM", "Exchange": "BA", "Type": "Common Stock", "isPrimary": False,
     "ISIN": None, "Name": "Taiwan Semiconductor Manufacturing Company L"},
    {"Code": "TSMX", "Exchange": "US", "Type": "ETF", "isPrimary": False,
     "ISIN": "US25461A5442", "Name": "Direxion Daily TSM Bull 2X Shares"},
]

_GOOG_ROWS = [
    {"Code": "GOOG", "Exchange": "US", "Type": "Common Stock", "isPrimary": True,
     "ISIN": "US02079K1079", "Name": "Alphabet Inc Class C"},
    {"Code": "GOOG", "Exchange": "TO", "Type": "Common Stock", "isPrimary": False,
     "ISIN": None, "Name": "Alphabet CDR (CAD Hedged)"},
    {"Code": "GOOG", "Exchange": "NEO", "Type": "Common Stock", "isPrimary": True,
     "ISIN": "CA02080K1049", "Name": "Alphabet Inc CDR"},
]


def test_resolves_the_us_listing_first():
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_TSM_ROWS):
        got = eodhd.resolve_symbol_eodhd("TSM")
    assert got["resolved"] == "TSM.US", "the US listing wins over the vendor's row order"
    assert got["unavailable"] is None
    assert got["type"] == "Common Stock"
    assert got["isin"] == "US8740391003"


def test_is_primary_alone_is_not_a_sufficient_selector():
    """Every TSM row reports isPrimary False, including the US common stock, so the
    US preference must come first and the flag only break a tie."""
    assert all(r["isPrimary"] is False for r in _TSM_ROWS)
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_TSM_ROWS):
        got = eodhd.resolve_symbol_eodhd("TSM")
    assert got["resolved"] == "TSM.US"
    assert got["is_primary"] is False, "the row's own flag is reported as it is"


def test_preferred_exchange_is_honoured():
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_GOOG_ROWS):
        got = eodhd.resolve_symbol_eodhd("GOOG", preferred_exchange="NEO")
    assert got["resolved"] == "GOOG.NEO"
    assert got["isin"] == "CA02080K1049"


def test_class_share_keeps_the_vendors_spelling():
    """EODHD writes BRK-B; joining Code.Exchange must not re-edit it to BRK.B."""
    rows = [{"Code": "BRK-B", "Exchange": "US", "Type": "Common Stock",
             "isPrimary": True, "ISIN": "US0846707026", "Name": "Berkshire Hathaway Inc"}]
    with mock.patch.object(eodhd, "_eodhd_get", return_value=rows):
        got = eodhd.resolve_symbol_eodhd("BRK.B")
    assert got["resolved"] == "BRK-B.US"


def test_other_venues_of_the_same_instrument_are_carried_and_flagged_ambiguous():
    with mock.patch.object(eodhd, "_eodhd_get", return_value=_TSM_ROWS):
        got = eodhd.resolve_symbol_eodhd("TSM")
    assert got["ambiguous"] is True
    assert [a["ticker"] for a in got["alternatives"]] == ["TSM.BA"], (
        "only the same code on another exchange is an alternative listing"
    )
    assert got["alternatives"][0]["exchange"] == "BA"
    assert got["other_matches"] == 1, "TSMX is a different product, not a listing"


def test_a_different_security_is_never_offered_as_an_alternative():
    """A leveraged ETF whose name embeds the query is a different product, not this
    instrument on another venue - the mis-flag the live smoke caught (search/AAPL
    returns AAPD/AAPU/APLY, three unrelated funds)."""
    rows = [
        {"Code": "AAPL", "Exchange": "US", "Type": "Common Stock", "isPrimary": True,
         "ISIN": "US0378331005", "Name": "Apple Inc"},
        {"Code": "AAPD", "Exchange": "US", "Type": "ETF", "isPrimary": False,
         "ISIN": "US25461A5360", "Name": "Direxion Daily AAPL Bear 1X Shares"},
        {"Code": "AAPU", "Exchange": "US", "Type": "ETF", "isPrimary": False,
         "ISIN": "US25461A5287", "Name": "Direxion Daily AAPL Bull 2X Shares"},
    ]
    with mock.patch.object(eodhd, "_eodhd_get", return_value=rows):
        got = eodhd.resolve_symbol_eodhd("AAPL")
    assert got["resolved"] == "AAPL.US"
    assert got["alternatives"] == [], "AAPD/AAPU are other securities"
    assert got["ambiguous"] is False
    assert got["other_matches"] == 2


def test_a_single_listing_is_not_ambiguous():
    rows = [{"Code": "AAPL", "Exchange": "US", "Type": "Common Stock",
             "isPrimary": True, "ISIN": "US0378331005", "Name": "Apple Inc"}]
    with mock.patch.object(eodhd, "_eodhd_get", return_value=rows):
        got = eodhd.resolve_symbol_eodhd("AAPL")
    assert got["ambiguous"] is False and got["alternatives"] == []
    assert got["other_matches"] == 0


def test_unknown_asset_type_is_a_named_gap_and_makes_no_call():
    with mock.patch.object(eodhd, "_eodhd_get") as no_call:
        got = eodhd.resolve_symbol_eodhd("AAPL", asset_type="warrant")
    assert no_call.call_count == 0, "an ignored filter must not be sent"
    assert "warrant" in got["unavailable"]
    assert "stock" in got["unavailable"], "the allowed set must be named"
    assert got["resolved"] is None


def test_empty_query_and_no_match_report_rather_than_raise():
    with mock.patch.object(eodhd, "_eodhd_get") as no_call:
        empty = eodhd.resolve_symbol_eodhd("   ")
    assert no_call.call_count == 0 and "empty query" in empty["unavailable"]
    with mock.patch.object(eodhd, "_eodhd_get", return_value=[]):
        none = eodhd.resolve_symbol_eodhd("ZZZZ")
    assert none["resolved"] is None and "no listing matched" in none["unavailable"]


def test_vendor_failure_reports_the_reason():
    with mock.patch.object(
        eodhd, "_eodhd_get", side_effect=RuntimeError("gateway down")
    ):
        got = eodhd.resolve_symbol_eodhd("AAPL")
    assert got["resolved"] is None
    assert "symbol search failed" in got["unavailable"]


def test_query_is_percent_encoded_into_the_path():
    seen = {}

    def _get(path, params=None, **_kw):
        seen["path"] = path
        return []

    with mock.patch.object(eodhd, "_eodhd_get", side_effect=_get):
        eodhd.resolve_symbol_eodhd("Apple Inc")
        assert seen["path"] == "search/Apple%20Inc", seen["path"]
        eodhd.resolve_symbol_eodhd("BRK.B")
        assert seen["path"] == "search/BRK.B", "a class share stays a documented path"


# ---------------------------------------------------------------------------
# Item 4: the weights-aware quota ledger and the free account read
# ---------------------------------------------------------------------------

def test_declared_weights_are_the_vendors_numbers():
    assert eodhd_quota.weight_for("symbol-change-history") == 5
    assert eodhd_quota.weight_for("historical-market-cap/AAPL.US") == 10
    assert eodhd_quota.weight_for("cboe/indices") == 10
    assert eodhd_quota.weight_for("calendar/trends") == 10
    # Undeclared paths are one counted call, which is what /eod and /search measured.
    assert eodhd_quota.weight_for("eod/AAPL.US") == 1
    assert eodhd_quota.weight_for("search/TSM") == 1
    assert eodhd_quota.weight_for("calendar/earnings") == 1


def test_the_ledger_counts_weighted_calls_not_requests():
    eodhd_quota.note_call("eod/AAPL.US")
    eodhd_quota.note_call("eod/MSFT.US")
    eodhd_quota.note_call("cboe/index")
    spend = eodhd_quota.observed_spend()
    assert spend["requests"] == 3
    assert spend["weighted_calls"] == 12, "10 for the CBOE read, not 1"
    assert spend["by_endpoint"]["eod/AAPL.US"] == {"requests": 1, "weighted_calls": 1}


def test_the_account_endpoint_is_never_counted():
    assert eodhd_quota.is_free_path("user")
    assert eodhd_quota.is_free_path("/user?fmt=json")
    assert not eodhd_quota.is_free_path("eod/AAPL.US")
    # The hook in _eodhd_get must not bill the reading of the bill.
    eodhd._quota_note("user")
    assert eodhd_quota.observed_spend()["requests"] == 0
    eodhd._quota_note("eod/AAPL.US")
    assert eodhd_quota.observed_spend()["requests"] == 1


def test_a_successful_get_is_ledgered_and_the_free_one_is_not():
    ok = _resp(200, body=[{"date": "2026-10-06", "close": 1.0}])
    with mock.patch("requests.get", return_value=ok):
        eodhd._eodhd_get("eod/AAPL.US", {})
        assert eodhd_quota.observed_spend()["weighted_calls"] == 1
        eodhd._eodhd_get("user", {})
    assert eodhd_quota.observed_spend()["requests"] == 1, "only /eod was counted"


_ACCOUNT = {
    "subscriptionType": "yearly",
    "apiRequests": 2666,
    "dailyRateLimit": 100000,
    "extraLimit": 500,
    "email": "someone@example.invalid",
}


def test_snapshot_reads_the_account_and_drops_the_email():
    snap = eodhd_quota.quota_snapshot(refresh=True, fetch=lambda: _ACCOUNT)
    assert snap["available"] is True
    assert (snap["used"], snap["limit"], snap["extra"]) == (2666, 100000, 500)
    assert snap["remaining"] == 97334
    assert snap["status"] == "ok"
    assert snap["plan"] == "yearly"
    assert snap["resets_at"].endswith("Z")
    assert "email" not in snap, "rule 6: no personal info leaves this module"
    assert "someone@example.invalid" not in str(snap)


def test_snapshot_is_cached_and_refresh_bypasses_it():
    calls = []

    def _fetch():
        calls.append(1)
        return _ACCOUNT

    eodhd_quota.quota_snapshot(refresh=True, fetch=_fetch)
    eodhd_quota.quota_snapshot(fetch=_fetch)
    assert len(calls) == 1, "a second read inside the TTL must not re-request"
    eodhd_quota.quota_snapshot(refresh=True, fetch=_fetch)
    assert len(calls) == 2


def test_status_thresholds():
    at = lambda used, extra=0: eodhd_quota._status(used, 100, extra)  # noqa: E731
    assert at(10) == "ok"
    assert at(80) == "near_limit"
    assert at(95) == "critical"
    assert at(100) == "exhausted"
    assert at(100, extra=5) == "critical", "a reserve means the wall is not reached"


def test_snapshot_reports_unavailable_and_never_raises():
    def _boom():
        raise RuntimeError("gateway down")

    snap = eodhd_quota.quota_snapshot(refresh=True, fetch=_boom)
    assert snap["available"] is False
    assert snap["used"] is None, "unavailable is not 0"
    assert "gateway down" in snap["unavailable"]
    line = eodhd_quota.format_quota_line(refresh=False)
    assert "quota unavailable" in line


def test_a_failed_read_is_cached_so_an_outage_is_not_re_hammered():
    """An outage must not turn every call into another request: the failure is cached
    for the TTL and only `refresh=True` retries."""
    calls = []

    def _boom():
        calls.append(1)
        raise RuntimeError("gateway down")

    eodhd_quota.quota_snapshot(refresh=True, fetch=_boom)
    eodhd_quota.quota_snapshot(fetch=_boom)
    assert len(calls) == 1, "the cached failure must serve the second call"
    eodhd_quota.quota_snapshot(refresh=True, fetch=_boom)
    assert len(calls) == 2, "refresh must always retry"


def test_snapshot_reports_a_payload_without_quota_fields():
    snap = eodhd_quota.quota_snapshot(refresh=True, fetch=lambda: {"foo": 1})
    assert snap["available"] is False
    assert "dailyRateLimit" in snap["unavailable"]


def test_quota_line_carries_both_readings():
    eodhd_quota.note_call("eod/AAPL.US")
    eodhd_quota.quota_snapshot(refresh=True, fetch=lambda: _ACCOUNT)
    line = eodhd_quota.format_quota_line()
    assert "2,666 of 100,000" in line
    assert "500 in reserve" in line
    assert "This process: 1 requests = ~1 counted calls." in line
    assert eodhd_quota.format_spend_breakdown() == "By endpoint: eod/AAPL.US 1x (~1)."


def test_warning_logs_once_per_threshold_per_day(caplog):
    hot = {"dailyRateLimit": 100, "apiRequests": 85, "subscriptionType": "x"}
    with caplog.at_level("WARNING"):
        eodhd_quota.quota_snapshot(refresh=True, fetch=lambda: hot)
        eodhd_quota.quota_snapshot(refresh=True, fetch=lambda: hot)
    assert len([r for r in caplog.records if "daily quota" in r.getMessage()]) == 1
