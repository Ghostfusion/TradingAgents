"""The vendor failure policy: a refusal already known is not re-asked.

The design is retained — a failure still degrades to the next vendor through the
typed taxonomy (see `docs/developer/03-dataflow-vendors.md` §3.1b). What these
tests pin is the half that was missing: the *verdict* is remembered.

Measured 2026-09-30 across one set of batch logs: **575** FMP `profile` 429s,
**60** Massive snapshot 403s (30 `gainers` + 30 per-ticker) and **26** Finnhub
`get_analyst_ratings` 403s — every one a re-ask of a refusal already known.
"""

from __future__ import annotations

import pytest

from tradingagents.dataflows import fmp_common, massive, vendor_breaker

pytestmark = pytest.mark.timeout(600)


class _Response:
    """Minimal requests.Response stand-in: only what the vendors read."""

    def __init__(self, status_code: int):
        self.status_code = status_code

    def json(self):
        return {}


@pytest.fixture(autouse=True)
def _clean_gate(monkeypatch):
    """No breaker/negative-cache state, and no real sleeps, inside these tests."""
    vendor_breaker.reset()
    monkeypatch.setattr("time.sleep", lambda *_: None)
    yield
    vendor_breaker.reset()


# ---------------------------------------------------------------------------
# FMP - a free tier that has said "no" must stop being asked
# ---------------------------------------------------------------------------


def test_a_refused_fmp_endpoint_is_remembered_not_re_asked(monkeypatch):
    """401/403 is a key/plan verdict: one refusal covers every later call."""
    calls: list[str] = []

    def _fake_get(url, params=None, timeout=None):
        calls.append(url)
        return _Response(403)

    monkeypatch.setattr(fmp_common, "f_key", lambda: "test-key")
    monkeypatch.setattr("requests.get", _fake_get)

    assert fmp_common.fmp_get("profile") is None
    assert len(calls) == 1, "a 403 must not be retried"

    assert fmp_common.fmp_get("profile") is None
    assert len(calls) == 1, "the refusal is remembered, so no second request"

    assert fmp_common.fmp_get("income-statement") is None
    assert len(calls) == 2, "a DIFFERENT endpoint is still asked for"


def test_a_throttled_fmp_endpoint_is_skipped_once_the_breaker_opens(monkeypatch):
    """A 429 is transient, so it is retried - then it counts toward the breaker."""
    calls: list[str] = []

    def _fake_get(url, params=None, timeout=None):
        calls.append(url)
        return _Response(429)

    monkeypatch.setattr(fmp_common, "f_key", lambda: "test-key")
    monkeypatch.setattr("requests.get", _fake_get)

    for _ in range(vendor_breaker.DEFAULT_MAX_FAILURES):
        assert fmp_common.fmp_get("profile") is None
    spent = vendor_breaker.DEFAULT_MAX_FAILURES * (fmp_common._MAX_RETRIES + 1)
    assert len(calls) == spent

    assert fmp_common.fmp_get("profile") is None
    assert len(calls) == spent, "an open breaker must skip without a request"


# ---------------------------------------------------------------------------
# Massive - the plan gates per ENDPOINT, never per symbol
# ---------------------------------------------------------------------------


def test_massive_capability_is_the_endpoint_never_the_symbol():
    zm = massive._capability("/v2/snapshot/locale/us/markets/stocks/tickers/ZM")
    nvda = massive._capability("/v2/snapshot/locale/us/markets/stocks/tickers/NVDA")
    assert zm == nvda, "one symbol's 403 must cover the whole endpoint"
    assert "tickers" in zm

    assert massive._capability("/stocks/financials/v1/ratios") == "stocks/financials/v1/ratios"
    assert massive._capability("/v2/snapshot/locale/us/markets/stocks/gainers") != zm


def test_a_massive_403_suppresses_the_next_symbol_as_not_configured(monkeypatch):
    """The skip is a plan verdict, so it must leave as the not-configured type."""
    from tradingagents.dataflows.errors import VendorNotConfiguredError

    calls: list[str] = []

    def _fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        return _Response(403)

    monkeypatch.setattr(massive, "massive_api_key", lambda: "test-key")
    monkeypatch.setattr("requests.get", _fake_get)

    with pytest.raises(VendorNotConfiguredError):
        massive._get("/v2/snapshot/locale/us/markets/stocks/tickers/ZM")
    assert len(calls) == 1

    with pytest.raises(VendorNotConfiguredError) as caught:
        massive._get("/v2/snapshot/locale/us/markets/stocks/tickers/NVDA")
    assert len(calls) == 1, "the same endpoint on another symbol is not re-asked"
    assert "known unavailable" in str(caught.value)


def test_a_throttled_massive_endpoint_raises_rate_limit_not_a_plan_verdict(monkeypatch):
    """A transient throttle must PROPAGATE, never read as a served 'unavailable'."""
    from tradingagents.dataflows.errors import VendorRateLimitError

    monkeypatch.setattr(massive, "massive_api_key", lambda: "test-key")
    monkeypatch.setattr("requests.get", lambda *a, **k: _Response(429))

    for _ in range(vendor_breaker.DEFAULT_MAX_FAILURES):
        with pytest.raises(VendorRateLimitError):
            massive._get("/v2/snapshot/locale/us/markets/stocks/gainers")

    with pytest.raises(VendorRateLimitError) as caught:
        massive._get("/v2/snapshot/locale/us/markets/stocks/gainers")
    assert "breaker" in str(caught.value)


# ---------------------------------------------------------------------------
# Finnhub - the analyst-ratings endpoint 403s on the free tier
# ---------------------------------------------------------------------------


def test_a_refused_finnhub_ratings_endpoint_is_skipped_before_the_client(monkeypatch):
    from tradingagents.dataflows import finnhub
    from tradingagents.dataflows.errors import NoMarketDataError

    def _boom():
        raise AssertionError("a skipped capability must not build a client")

    monkeypatch.setattr(finnhub, "_client", _boom)
    vendor_breaker.note_vendor_refused("finnhub", "analyst-ratings")

    with pytest.raises(NoMarketDataError):
        finnhub.get_analyst_ratings_finnhub("AAPL")
