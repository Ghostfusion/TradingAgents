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
    with (
        mock.patch("tradingagents.dataflows.fmp.get_company_profile", return_value=None),
        mock.patch("tradingagents.dataflows.finnhub.get_profile_finnhub", side_effect=_no_finnhub),
    ):
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
    with (
        mock.patch(
            "tradingagents.dataflows.fmp.get_company_profile",
            return_value={"sector": "", "company": "Apple"},
        ),
        mock.patch(
            "yfinance.Ticker", return_value=type("T", (), {"info": {"sector": "Technology"}})
        ),
    ):
        assert fetch_sector("AAPL") == "Technology"


def _no_finnhub(*a, **k):
    return None


def test_fetch_sector_neither_source():
    with (
        mock.patch("tradingagents.dataflows.fmp.get_company_profile", return_value=None),
        mock.patch("tradingagents.dataflows.finnhub.get_profile_finnhub", side_effect=_no_finnhub),
        mock.patch("yfinance.Ticker", return_value=type("T", (), {"info": {}})),
    ):
        assert fetch_sector("AAPL") is None


def test_fetch_sector_none_on_failure(monkeypatch):
    def boom(t):
        raise RuntimeError("no network")

    with (
        mock.patch("tradingagents.dataflows.fmp.get_company_profile", return_value=None),
        mock.patch("tradingagents.dataflows.finnhub.get_profile_finnhub", side_effect=_no_finnhub),
        mock.patch("yfinance.Ticker", boom),
    ):
        assert fetch_sector("AAPL") is None


def test_fetch_sector_empty_info():
    with (
        mock.patch("tradingagents.dataflows.fmp.get_company_profile", return_value=None),
        mock.patch("tradingagents.dataflows.finnhub.get_profile_finnhub", side_effect=_no_finnhub),
        mock.patch("yfinance.Ticker", return_value=type("T", (), {"info": {}})),
    ):
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


def test_fetch_sector_finnhub_second_tier():
    # FMP misses -> Finnhub (profile2) supplies the sector -> wins.
    from tradingagents.dataflows import yfinance_sector as ys

    def boom(t):
        raise AssertionError("yfinance should not be reached when finnhub answers")

    with (
        mock.patch("tradingagents.dataflows.fmp.get_company_profile", return_value=None),
        mock.patch(
            "tradingagents.dataflows.finnhub.get_profile_finnhub",
            return_value={"finnhubIndustry": "Technology", "ticker": "AAPL"},
        ),
        mock.patch("yfinance.Ticker", side_effect=boom),
    ):
        assert ys.fetch_sector("AAPL") == "Technology"


def test_fetch_sector_fmp_wins_over_finnhub():
    from tradingagents.dataflows import yfinance_sector as ys

    with (
        mock.patch(
            "tradingagents.dataflows.fmp.get_company_profile",
            return_value={"sector": "Consumer Cyclical"},
        ),
        mock.patch("tradingagents.dataflows.finnhub.get_profile_finnhub", side_effect=_no_finnhub),
        mock.patch(
            "yfinance.Ticker", side_effect=lambda t: (_ for _ in ()).throw(AssertionError("no yf"))
        ),
    ):
        assert ys.fetch_sector("AAPL") == "Consumer Cyclical"


def test_fetch_sector_etf_universe_wins_over_provider_misclassification():
    """IGV 2026-09-09 review loop: provider metadata says ETF tickers are
    'Financial Services' (IGV/SOXX/XLK all came back wrong). The ETF
    canonical mapping must win over the wrong provider sector, no vendor
    call needed."""
    from tradingagents.dataflows import yfinance_sector as ys

    def boom(t):  # noqa: ANN001
        raise AssertionError("no provider call")
    # Providers would say "Financial Services"; ETF identity must override.
    for etf, expected in (("IGV", "Technology"), ("SOXX", "Technology"),
                          ("XLK", "Technology"), ("CIBR", "Technology"),
                          ("SKYY", "Technology")):
        with (
            mock.patch("tradingagents.dataflows.fmp.get_company_profile",
                       return_value={"sector": "Financial Services"}),
            mock.patch("tradingagents.dataflows.finnhub.get_profile_finnhub",
                      return_value={"finnhubIndustry": "Financial Services"}),
            mock.patch("yfinance.Ticker", side_effect=boom),
        ):
            assert ys.fetch_sector(etf) == expected, etf
    # A company ticker is untouched by the ETF mapping (goes to provider).
    with (
        mock.patch("tradingagents.dataflows.fmp.get_company_profile",
                  return_value={"sector": "Financial Services"}),
        mock.patch("tradingagents.dataflows.finnhub.get_profile_finnhub", side_effect=_no_finnhub),
        mock.patch("yfinance.Ticker", side_effect=boom),
    ):
        assert ys.fetch_sector("BAC") == "Financial Services"


def _no_yf(t):
    raise AssertionError("yfinance must not be reached when a provider answers")


def test_profile_finnhub_does_not_invent_a_sector_key():
    """The vendor's classification is ``finnhubIndustry`` - Finnhub's OWN
    taxonomy, not GICS. Copying it onto a key named ``sector`` made a key named
    *sector* hold an *industry* value, so the one consumer read a taxonomy it
    could not see (docs/design_security_context.md section 7.2). The function
    returns the vendor payload unmodified; the consumer does the mapping."""
    from tradingagents.dataflows import finnhub

    # The vendor's REAL key set, live-probed 2026-09-22. There is no `sector`
    # key and no `industry` key at all, so the old rename was the only source of
    # `sector` - and the payload must come back exactly as it arrived.
    payload = {
        "ticker": "AAPL",
        "finnhubIndustry": "Technology",
        "country": "US",
        "currency": "USD",
        "exchange": "NASDAQ/NMS (Global Select Market)",
        "ipo": "1980-12-12",
        "marketCapitalization": 4020000.0,
        "name": "Apple Inc",
        "phone": "14089961010",
        "shareOutstanding": 14840.0,
        "weburl": "https://www.apple.com/",
    }
    with mock.patch.object(finnhub, "_client") as client:
        client.return_value.company_profile2.return_value = payload
        out = finnhub.get_profile_finnhub("AAPL")

    assert out is not None
    assert "sector" not in out, "the vendor payload must come back unmodified"
    assert out == payload, "no key may be added, removed or changed"
    assert out["finnhubIndustry"] == "Technology"


def test_fetch_sector_reads_finnhub_industry_when_that_is_all_there_is():
    """End to end: Finnhub's own field reaches ``fetch_sector``, so the vendor
    module does not need to rename anything for the value to arrive."""
    from tradingagents.dataflows import yfinance_sector as ys

    with (
        mock.patch("tradingagents.dataflows.fmp.get_company_profile", return_value=None),
        mock.patch(
            "tradingagents.dataflows.finnhub.get_profile_finnhub",
            return_value={"ticker": "AAPL", "finnhubIndustry": "Technology"},
        ),
        mock.patch("yfinance.Ticker", side_effect=_no_yf),
    ):
        assert ys.fetch_sector("AAPL") == "Technology"


def test_fetch_sector_keeps_the_vendor_sector_key_ahead_of_industry():
    """Precedence preserved. The old rename only fired when ``sector`` was
    ABSENT, so a payload carrying both must still answer with ``sector``."""
    from tradingagents.dataflows import yfinance_sector as ys

    with (
        mock.patch("tradingagents.dataflows.fmp.get_company_profile", return_value=None),
        mock.patch(
            "tradingagents.dataflows.finnhub.get_profile_finnhub",
            return_value={"sector": "Financial Services", "finnhubIndustry": "Banking"},
        ),
        mock.patch("yfinance.Ticker", side_effect=_no_yf),
    ):
        assert ys.fetch_sector("AAPL") == "Financial Services"
