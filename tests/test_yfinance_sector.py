"""Guarded yfinance enrichments (sector + analyst revisions) - offline tests."""

from unittest import mock

from tradingagents.dataflows.yfinance_sector import fetch_revision_actions, fetch_sector


class _FakeInfo:
    def __init__(self, payload):
        self._p = payload

    @property
    def sector(self):
        raise AttributeError  # spoof dict access not needed

    def get(self, key, default=None):
        return self._p.get(key, default)


def test_fetch_sector_returns_value(monkeypatch):
    monkeypatch.setattr(
        "yfinance.Ticker", lambda t: type("T", (), {"info": {"sector": "Technology"}})
    )
    assert fetch_sector("AAPL") == "Technology"


def test_fetch_sector_fmp_primary(monkeypatch):
    # FMP answers -> its sector wins (no yfinance call needed).
    with mock.patch(
        "tradingagents.dataflows.fmp.get_company_profile",
        return_value={"sector": "Information Technology"},
    ):
        def boom(t):
            raise AssertionError("yfinance should not be called when FMP answers")

        monkeypatch.setattr("yfinance.Ticker", boom)
        assert fetch_sector("AAPL") == "Information Technology"


def test_fetch_sector_fmp_missing_falls_back_to_yfinance():
    with mock.patch(
        "tradingagents.dataflows.fmp.get_company_profile",
        return_value={"sector": "", "company": "Apple"},
    ), mock.patch(
        "yfinance.Ticker", return_value=type("T", (), {"info": {"sector": "Technology"}})
    ):
        assert fetch_sector("AAPL") == "Technology"


def test_fetch_sector_neither_source():
    with (
        mock.patch("tradingagents.dataflows.fmp.get_company_profile", return_value=None),
        mock.patch("yfinance.Ticker", return_value=type("T", (), {"info": {}})),
    ):
        assert fetch_sector("AAPL") is None


def test_fetch_sector_none_on_failure(monkeypatch):
    def boom(t):
        raise RuntimeError("no network")

    monkeypatch.setattr("yfinance.Ticker", boom)
    assert fetch_sector("AAPL") is None


def test_fetch_sector_empty_info():
    with mock.patch("yfinance.Ticker", return_value=type("T", (), {"info": {}})):
        assert fetch_sector("AAPL") is None


def test_fetch_revision_actions_counts_window():
    from datetime import datetime

    class _Df:
        empty = False

        def iterrows(self):
            rows = [
                # recent actions inside the 60d window
                (0, {"ActionDate": datetime.now(), "Action": "up"}),
                (1, {"ActionDate": datetime.now(), "Action": "down"}),
                (2, {"ActionDate": datetime.now(), "Action": "main"}),
                (3, {"ActionDate": datetime.now(), "Action": "up"}),
                # stale action outside the window
                (4, {"ActionDate": datetime.now().replace(year=2000), "Action": "down"}),
            ]
            return iter(rows)

    class _T:
        upgrades_downgrades = _Df()

    with mock.patch("yfinance.Ticker", return_value=_T()):
        res = fetch_revision_actions("AAPL", days=60)
    assert res == {"up": 2, "down": 1, "net": 1}


def test_fetch_revision_actions_none_on_failure(monkeypatch):
    def boom(t):
        raise RuntimeError("no network")

    monkeypatch.setattr("yfinance.Ticker", boom)
    assert fetch_revision_actions("AAPL") is None
