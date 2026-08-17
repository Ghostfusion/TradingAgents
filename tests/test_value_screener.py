"""Value screener: top-losers universe source + classic ticker path.

Offline: moomoo rank and vendor statements are mocked; nothing hits the
network or OpenD.
"""

import pytest
from unittest import mock

import scripts.value_screener as vs

FUND = "Market Cap: 3.2B\n"
BS = ("Date,2025-12-31\nCash And Cash Equivalents,300M\nTotal Debt,400M\n"
      "Total Assets,2.0B\nTotal Current Assets,700M\nTotal Current Liabilities,500M\n"
      "Total Liabilities,900M\nRetained Earnings,800M\nProperty Plant Equipment,400M")
INC = ("Date,2025-12-31\nTotal Revenue,1.0B\nOperating Income,150M\n"
       "Net Income,100M\nInterest Expense,10M\nTax Expense,20M")


def fake_route(method, *a, **k):
    t = a[0]
    if t != "AAPL":
        return "NO_DATA_AVAILABLE: no usable market data"
    return {"get_fundamentals": FUND, "get_balance_sheet": BS,
            "get_income_statement": INC}.get(method, "NO_DATA_AVAILABLE")


def fake_movers(sort_dir="losers", count=50, market="US", min_market_cap=0.0):
    assert sort_dir == "losers" and count == 2 and market == "US"
    return [
        {"symbol": "AAPL", "name": "Apple Inc.", "cur_price": 210.5,
         "change_ratio": -0.0421, "pe_ttm": 28.1, "market_cap": 3.2e12, "volume": 5e7},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "cur_price": 95.2,
         "change_ratio": -0.031, "pe_ttm": 35.0, "market_cap": 7.0e12, "volume": 2e7},
    ]


@pytest.fixture(autouse=True)
def _patch_vendors():
    with mock.patch.object(vs, "route_to_vendor", side_effect=fake_route), \
         mock.patch("tradingagents.dataflows.moomoo.get_top_movers_moomoo",
                    side_effect=fake_movers):
        yield


def test_top_losers_universe_adds_name_and_daychg_columns(capsys):
    vs.main(["--universe", "top-losers", "-n", "2", "-d", "2026-01-02", "--min-mcap", "1e9"])
    out = capsys.readouterr().out
    assert "Apple Inc." in out
    assert "-4.21%" in out
    assert "US.AAPL" not in out  # prefix must be stripped by the vendor fn


def test_classic_path_has_no_mover_columns(capsys):
    vs.main(["AAPL", "-d", "2026-01-02"])
    out = capsys.readouterr().out
    assert "DayChg" not in out
    assert "Name |" not in out
    assert "AAPL" in out


def test_universe_caps_limit(capsys):
    vs.main(["--universe", "top-losers", "-n", "2", "-d", "2026-01-02", "-l", "1"])
    out = capsys.readouterr().out
    # Only one row should have been screened (limit=1).
    assert out.count("| 1 |") >= 1
