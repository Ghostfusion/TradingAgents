"""Tests for get_etf_mechanics (NAV premium/discount + distributions).

The IGV 2026-09-09 review loop: fund distributions were called corporate
dividends and fund mechanics were absent. get_etf_mechanics exposes NAV
premium/discount and labels distributions as ETF distributions — every field
None-safe, never fabricated.
"""

from __future__ import annotations

from unittest import mock

from tradingagents.agents.utils.analysis_tools import get_etf_mechanics


def _mk_tk(info: dict):
    class _Tk:
        pass

    _Tk.info = info  # yfinance .info is a dict
    return _Tk()


def test_mechanics_nav_premium_rendered_from_info():
    tk = _mk_tk({"navPrice": 100.0, "regularMarketPrice": 101.5})
    with mock.patch("yfinance.Ticker", return_value=tk), mock.patch(
        "tradingagents.agents.utils.moomoo_extra_tools.get_corporate_actions",
        return_value="## Corporate Actions\n- dividend $0.017 2026-06-15",
    ):
        out = get_etf_mechanics.invoke({"ticker": "IGV"})
    assert "NAV premium/discount: +1.50%" in out
    assert "Distributions:" in out


def test_mechanics_nav_missing_renders_na():
    tk = _mk_tk({"navPrice": None, "regularMarketPrice": 101.0})
    with mock.patch("yfinance.Ticker", return_value=tk), mock.patch(
        "tradingagents.agents.utils.moomoo_extra_tools.get_corporate_actions",
        return_value="corporate actions unavailable for IGV",
    ):
        out = get_etf_mechanics.invoke({"ticker": "IGV"})
    assert "NAV premium/discount: n/a" in out


def test_mechanics_never_raises_on_bad_ticker():
    with mock.patch("yfinance.Ticker", side_effect=RuntimeError("down")), mock.patch(
        "tradingagents.agents.utils.moomoo_extra_tools.get_corporate_actions",
        side_effect=RuntimeError("down"),
    ):
        out = get_etf_mechanics.invoke({"ticker": "ZZZZ"})
    assert "## ETF mechanics" in out
    assert "n/a" in out
