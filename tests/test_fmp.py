"""FMP vendor + vendor-chain normalized_score tests (offline; mock the layers)."""

from contextlib import contextmanager
from unittest import mock

import pytest

# A moomoo-style markdown income statement (4 annual periods), as the vendor
# chain returns via ``get_income_statement``.
_INCOME_MD = """### 2025/FY  (FY 2025, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Total Operating Revenue | $416.16B | 6.43% | -- |
| Operating Profit | $133.05B | 7.98% | -- |
| Net Income to Common | $112.01B | 19.50% | -- |
### 2024/FY  (FY 2024, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Total Operating Revenue | $391.04B | 2.02% | -- |
| Operating Profit | $123.22B | 7.80% | -- |
| Net Income to Common | $93.74B | -3.36% | -- |
### 2023/FY  (FY 2023, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Total Operating Revenue | $383.29B | -2.80% | -- |
| Operating Profit | $114.30B | -4.30% | -- |
| Net Income to Common | $97.00B | -2.81% | -- |
### 2022/FY  (FY 2022, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Total Operating Revenue | $394.33B | 7.79% | -- |
| Operating Profit | $119.44B | 9.63% | -- |
| Net Income to Common | $99.80B | 5.41% | -- |
"""


def _fin():
    return {
        "market_cap": 4_430_136_000_000.0,
        "total_debt": 112_000_000_000.0,
        "cash": 16_000_000_000.0,
        "shares": 15_000_000_000.0,
    }


def _patch_chain(income=_INCOME_MD, fin=None, closes=None):
    """Patch route_to_vendor (income statement + stock prices) and fetch_ticker
    so normalized_score runs entirely offline through the vendor chain."""
    from contextlib import ExitStack

    from tradingagents.dataflows import interface as iface, statement_parsing as sp

    def route(method, *a, **k):
        if method == "get_income_statement":
            return income
        if method == "get_stock_data":
            # closes CSV: Date,Open,High,Low,Close,Volume (yearly rows)
            return closes if closes is not None else (
                "Date,Open,High,Low,Close,Volume\n"
                "2022-12-30,100,102,99,101,1000\n"
                "2023-12-29,110,112,109,111,1000\n"
                "2024-12-31,120,122,119,121,1000\n"
                "2025-12-31,130,132,129,131,1000\n"
            )
        return ""

    @contextmanager
    def _cm():
        with ExitStack() as stack:
            # normalized_score imports route_to_vendor from the interface
            # module directly (and statement_parsing re-exports the same name),
            # so patch both bindings to keep the test hermetic.
            stack.enter_context(mock.patch.object(iface, "route_to_vendor", side_effect=route))
            stack.enter_context(mock.patch.object(sp, "route_to_vendor", side_effect=route))
            stack.enter_context(
                mock.patch.object(sp, "fetch_ticker", return_value=fin if fin is not None else _fin())
            )
            # Force the vendor-chain path: even if an FMP key exists in the
            # env, never fall back to FMP inside these offline tests.
            stack.enter_context(mock.patch("tradingagents.dataflows.fmp.f_key", return_value=None))
            yield

    return _cm()


def test_income_series_extraction():
    from tradingagents.dataflows.statement_parsing import income_series

    s = income_series(_INCOME_MD)
    assert s is not None and len(s) == 4
    assert s[0]["year"] == 2022
    assert s[-1]["year"] == 2025
    assert s[-1]["revenue"] == pytest.approx(416.16e9, rel=0.01)
    assert s[-1]["ebit"] == pytest.approx(133.05e9, rel=0.01)
    assert s[-1]["net_income"] == pytest.approx(112.01e9, rel=0.01)


def test_income_series_no_payload_is_none():
    from tradingagents.dataflows.statement_parsing import income_series

    assert income_series("") is None
    assert income_series("NO_DATA_AVAILABLE: x") is None
    assert income_series("garbage not a statement") is None


def test_fmp_histories_and_surprises_parse():
    from tradingagents.dataflows import fmp

    income = [{"date": f"202{i}", "revenue": 1000.0, "ebit": 100.0,
               "netIncome": 80.0} for i in range(4)]
    evs = [{"date": f"202{i}", "enterpriseValue": 1200.0,
            "marketCapitalization": 1100.0} for i in range(4)]

    def fake_get(path, params=None):
        if path == "income-statement":
            return income
        if path == "enterprise-values":
            return evs
        if path == "earnings-surprises":
            return [{"date": "2026-01-01", "epsActual": 1.2, "epsEstimated": 0.9}]
        return None

    with mock.patch("tradingagents.dataflows.fmp.fmp_get", side_effect=fake_get):
        his = fmp.get_income_history("AAPL", limit=4)
        ev = fmp.get_ev_history("AAPL", limit=4)
        sur = fmp.get_earnings_surprises("AAPL")
    assert his and len(his) == 4
    assert ev and ev[0]["enterpriseValue"] == 1200.0
    assert sur and sur[0]["epsActual"] == 1.2


def test_no_history_returns_none():
    from tradingagents.dataflows import fmp

    with mock.patch("tradingagents.dataflows.fmp.fmp_get", return_value=None):
        assert fmp.get_income_history("AAPL") is None


def test_normalized_score_computes_from_vendor_chain():
    from tradingagents.dataflows import fmp

    with _patch_chain():
        nf = fmp.normalized_score("AAPL", years=5, current_date="2026-08-24")
    assert nf is not None
    assert nf["ev_nebit"] > 0
    assert 0.0 <= nf["pe_pct5"] <= 1.0
    assert nf["ev"] == pytest.approx(4_430_136_000_000.0 + 112e9 - 16e9, rel=0.05)
    assert nf["market_cap"] == pytest.approx(4_430_136_000_000.0, rel=0.05)


def test_normalized_score_no_income_degrades():
    from tradingagents.dataflows import fmp

    with _patch_chain(income="NO_DATA_AVAILABLE: x", fin=_fin()):
        nf = fmp.normalized_score("AAPL", years=5, current_date="2026-08-24")
    assert nf is None


def test_normalized_score_defaults_to_vendor_chain_not_fmp():
    """With a working vendor chain, fmp_get must never be called (no 429s)."""
    from tradingagents.dataflows import fmp

    with _patch_chain(), mock.patch("tradingagents.dataflows.fmp.fmp_get") as fg:
        nf = fmp.normalized_score("AAPL", years=5, current_date="2026-08-24")
    fg.assert_not_called()
    assert nf is not None


def test_no_key_no_calls():
    from tradingagents.dataflows import fmp_common

    with mock.patch.object(fmp_common, "f_key", return_value=None), \
         mock.patch("requests.get") as req:
        out = fmp_common.fmp_get("income-statement", {"symbol": "AAPL"})
    assert out is None
    req.assert_not_called()
