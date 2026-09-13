"""Look-ahead window + error-classification contract for the news vendors.

Phase C of ``docs/implementation_plan_defect_audit.md``: finnhub's global news
ignored ``curr_date``/``look_back_days``/``limit``, its earnings calendar
queried a purely backward window, its insider window read ``datetime.now()``,
``NoMarketDataError`` carried the human message in ``canonical``, and
newsapi/benzinga classified the response *body* before the HTTP status (an
HTML 429 became a permanent no-data error) while retrying non-transient
statuses with no delay.

Hermetic: the vendor client / HTTP seam is stubbed with canned responses - no
network, no wall clock, no real vendor SDK.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from tradingagents.dataflows import benzinga, finnhub, newsapi
from tradingagents.dataflows.errors import NoMarketDataError, VendorRateLimitError


def _epoch(year: int, month: int, day: int, hour: int = 12) -> float:
    """Unix seconds for a UTC instant (Finnhub's article ``datetime`` unit)."""
    return datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp()


# ---------------------------------------------------------------------------
# finnhub: global news window + limit
# ---------------------------------------------------------------------------


class _NewsClient:
    def __init__(self, news):
        self._news = news

    def general_news(self, category, min_id=0):
        return self._news


_NEWS = [
    {"headline": "Future leak", "datetime": _epoch(2026, 9, 11)},
    {"headline": "Recent one", "datetime": _epoch(2026, 9, 9)},
    {"headline": "Old one", "datetime": _epoch(2026, 7, 1)},
    {"headline": "Recent two", "datetime": _epoch(2026, 9, 7)},
]


def test_global_news_only_returns_in_window_articles(monkeypatch):
    monkeypatch.setattr(finnhub, "_client", lambda: _NewsClient(_NEWS))

    out = finnhub.get_global_news_finnhub("2026-09-10", look_back_days=7, limit=10)

    assert "Recent one" in out
    assert "Recent two" in out
    # Dated after curr_date: a historical run must never see it (look-ahead).
    assert "Future leak" not in out
    # Dated before curr_date - look_back_days.
    assert "Old one" not in out


def test_global_news_honours_limit(monkeypatch):
    monkeypatch.setattr(finnhub, "_client", lambda: _NewsClient(_NEWS))

    out = finnhub.get_global_news_finnhub("2026-09-10", look_back_days=7, limit=1)

    assert "Recent one" in out
    assert "Recent two" not in out


# ---------------------------------------------------------------------------
# finnhub: earnings calendar is forward-looking
# ---------------------------------------------------------------------------


class _EarningsClient:
    def __init__(self, payload):
        self._payload = payload
        self.calls: list[dict] = []

    def earnings_calendar(self, **kwargs):
        self.calls.append(kwargs)
        return self._payload


def test_earnings_calendar_queries_the_forward_window(monkeypatch):
    client = _EarningsClient(
        {"earningsCalendar": [{"date": "2026-10-02", "epsEstimate": 1.5}]}
    )
    monkeypatch.setattr(finnhub, "_client", lambda: client)

    out = finnhub.get_earnings_calendar_finnhub("AAPL", "2026-09-10")

    # Next catalyst date => the query must start at the as-of date and look
    # forward (default look_back_days=30), not backward.
    assert client.calls == [
        {
            "_from": "2026-09-10",
            "to": "2026-10-10",
            "symbol": "AAPL",
            "international": False,
        }
    ]
    assert "2026-10-02" in out


# ---------------------------------------------------------------------------
# finnhub: insider window derives from the analysis date
# ---------------------------------------------------------------------------


class _InsiderClient:
    def __init__(self, payload):
        self._payload = payload
        self.calls: list[tuple] = []

    def stock_insider_sentiment(self, symbol, _from=None, to=None):
        self.calls.append((_from, to))
        return self._payload


def test_insider_window_uses_passed_date_not_now(monkeypatch):
    client = _InsiderClient(
        {"data": [{"year": 2026, "month": 8, "change": 5.0, "mspr": 1.0}]}
    )

    class _NoNowDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # pragma: no cover - must never be reached
            raise AssertionError("insider window must not read the wall clock")

    monkeypatch.setattr(finnhub, "datetime", _NoNowDatetime)
    monkeypatch.setattr(finnhub, "_client", lambda: client)

    out = finnhub.get_insider_activity_finnhub("AAPL", "2026-09-10")

    assert client.calls == [("2025-09-15", "2026-09-10")]
    assert "Insider Sentiment" in out


# ---------------------------------------------------------------------------
# finnhub: typed absence detail
# ---------------------------------------------------------------------------


class _EmptyPeersClient:
    def company_peers(self, symbol):
        return []


def test_company_peers_absence_carries_the_message_as_detail(monkeypatch):
    monkeypatch.setattr(finnhub, "_client", _EmptyPeersClient)

    with pytest.raises(NoMarketDataError) as ei:
        finnhub.get_company_peers_finnhub("AAPL")

    err = ei.value
    assert err.detail == "no peer data returned"
    assert err.canonical == "AAPL"
    assert "no peer data returned" in str(err)
    # The message must not be mistaken for the canonical queried symbol.
    assert "queried as" not in str(err)


# ---------------------------------------------------------------------------
# newsapi / benzinga: status classification + retry policy
# ---------------------------------------------------------------------------

_MISSING = object()


class _Resp:
    """Minimal requests.Response stand-in (no network)."""

    def __init__(self, status, body="<html>cloudflare</html>", json_data=_MISSING):
        self.status_code = status
        self.text = body
        self._json = json_data

    def json(self):
        if self._json is _MISSING:
            raise ValueError("not json")
        return self._json


def _getter(module):
    return module._newsapi_get if module is newsapi else module._benzinga_get


def _key_attr(module) -> str:
    return "newsapi_api_key" if module is newsapi else "benzinga_api_key"


@pytest.mark.parametrize("mod", [newsapi, benzinga], ids=["newsapi", "benzinga"])
@pytest.mark.parametrize("status", [429, 503])
def test_transient_status_with_html_body_is_typed_rate_limit(monkeypatch, mod, status):
    monkeypatch.setattr(mod, _key_attr(mod), lambda: "test-key")
    slept: list[float] = []
    monkeypatch.setattr(mod, "time", SimpleNamespace(sleep=slept.append), raising=False)
    attempts: list[int] = []

    def fake_get(url, params=None, timeout=None):
        attempts.append(1)
        return _Resp(status)

    monkeypatch.setattr(mod._requests, "get", fake_get)

    with pytest.raises(VendorRateLimitError):
        _getter(mod)("everything")

    # Retried with a delay before giving up (never a permanent no-data error).
    assert len(attempts) == mod._MAX_RETRIES + 1
    assert len(slept) == mod._MAX_RETRIES
    assert all(delay > 0 for delay in slept)


@pytest.mark.parametrize("mod", [newsapi, benzinga], ids=["newsapi", "benzinga"])
def test_permanent_client_error_is_not_retried(monkeypatch, mod):
    monkeypatch.setattr(mod, _key_attr(mod), lambda: "test-key")
    monkeypatch.setattr(mod, "time", SimpleNamespace(sleep=lambda *_: None), raising=False)
    attempts: list[int] = []

    def fake_get(url, params=None, timeout=None):
        attempts.append(1)
        return _Resp(404, json_data={"message": "no such endpoint"})

    monkeypatch.setattr(mod._requests, "get", fake_get)

    with pytest.raises(NoMarketDataError) as ei:
        _getter(mod)("everything")

    # A 404 is permanent: one attempt, reported as no-data (not rate limit).
    assert len(attempts) == 1
    assert "404" in ei.value.detail


def test_earnings_calendar_prints_the_countdown(monkeypatch):
    """Finnhub rows carry the days-out figure the report quotes (2026-09-10 ->
    2026-10-02 = 22d) instead of the model computing it."""
    client = _EarningsClient(
        {"earningsCalendar": [{"date": "2026-10-02", "epsEstimate": 1.5}]}
    )
    monkeypatch.setattr(finnhub, "_client", lambda: client)

    out = finnhub.get_earnings_calendar_finnhub("AAPL", "2026-09-10")

    assert "Days out: 22" in out
