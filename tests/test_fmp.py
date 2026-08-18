"""FMP vendor unit tests (offline; mock the HTTP layer)."""

from unittest import mock

import pytest


def _patch(income, evs, surprises=None, prices=None):
    def fake_get(path, params=None):
        if path == "income-statement":
            return income
        if path == "enterprise-values":
            return evs
        if path == "earnings-surprises":
            return surprises
        if path == "historical-price-full":
            return {"historical": prices} if prices is not None else None
        return None

    return mock.patch("tradingagents.dataflows.fmp.fmp_get",
                      side_effect=fake_get)


def test_histories_and_surprises_parse():
    from tradingagents.dataflows import fmp

    income = [{"date": f"202{i}", "revenue": 1000.0, "ebit": 100.0,
               "netIncome": 80.0} for i in range(4)]
    evs = [{"date": f"202{i}", "enterpriseValue": 1200.0,
            "marketCapitalization": 1100.0} for i in range(4)]
    with _patch(income, evs,
                                       surprises=[{"date": "2026-01-01",
                                                   "epsActual": 1.2,
                                                   "epsEstimated": 0.9}]):
        his = fmp.get_income_history("AAPL", limit=4)
        ev = fmp.get_ev_history("AAPL", limit=4)
        sur = fmp.get_earnings_surprises("AAPL")
    assert his and len(his) == 4
    assert ev and ev[0]["enterpriseValue"] == 1200.0
    assert sur and sur[0]["epsActual"] == 1.2


def test_no_history_returns_none():
    from tradingagents.dataflows import fmp

    with _patch(None, None):
        assert fmp.get_income_history("AAPL") is None


def test_normalized_score_computes():
    from tradingagents.dataflows import fmp

    income = [{"date": f"y{i}",
               "revenue": 1000.0,
               "ebit": 100.0 - 2 * i,   # margin dips a bit
               "netIncome": 60.0} for i in range(6)]
    evs = [{"date": f"y{i}", "enterpriseValue": 1200.0,
            "marketCapitalization": 1100.0} for i in range(6)]
    with _patch(income, evs):
        nf = fmp.normalized_score("AAPL", years=5)
    assert nf is not None
    assert nf["ev_nebit"] == pytest.approx(1200.0 / 96.0, rel=0.1)
    assert 0.0 <= nf["pe_pct5"] <= 1.0


def test_no_key_no_calls():
    from tradingagents.dataflows import fmp_common

    with mock.patch.object(fmp_common, "f_key", return_value=None), \
         mock.patch("requests.get") as req:
        out = fmp_common.fmp_get("income-statement", {"symbol": "AAPL"})
    assert out is None
    req.assert_not_called()
