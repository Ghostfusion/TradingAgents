"""Value screener: universe sources (top-losers, heat-proxy) + screen gates.

Offline: moomoo ranks and vendor statements are mocked; nothing hits the
network or OpenD.
"""

import pytest
from unittest import mock

import scripts.value_screener as vs

FUND = "Market Cap: 3.2T\n"
BS = ("Date,2025-12-31\nCash And Cash Equivalents,300M\nTotal Debt,400M\n"
      "Total Assets,2.0B\nTotal Current Assets,700M\nTotal Current Liabilities,500M\n"
      "Total Liabilities,900M\nRetained Earnings,800M\nProperty Plant Equipment,400M")
INC = ("Date,2025-12-31\nTotal Revenue,1.0B\nOperating Income,150M\n"
       "Net Income,100M\nInterest Expense,10M\nTax Expense,20M")

_LOSERS = [
    {"symbol": "AAPL", "name": "Apple Inc.", "cur_price": 210.5,
     "change_ratio": -0.0421, "pe_ttm": 28.1, "market_cap": 3.2e12},
    {"symbol": "MSFT", "name": "Microsoft Corp.", "cur_price": 95.2,
     "change_ratio": -0.031, "pe_ttm": 35.0, "market_cap": 7.0e12},
]
_HOT = _LOSERS + [
    {"symbol": "NVDA", "name": "NVIDIA Corp.", "cur_price": 120.0,
     "change_ratio": 0.031, "pe_ttm": 55.0, "market_cap": 3.0e12},   # gainer, not a loser
    {"symbol": "CHEAP", "name": "Cheap Co", "cur_price": 15.0,
     "change_ratio": -0.05, "pe_ttm": 10.0, "market_cap": 2.0e9},    # price < 20 -> gated
    {"symbol": "EYE", "name": "Pricey Inc", "cur_price": 50.0,
     "change_ratio": -0.03, "pe_ttm": 55.0, "market_cap": 5.0e9},    # PE > 40 -> gated
    {"symbol": "ETFX", "name": "Vanguard InfoTech ETF", "cur_price": 100.0,
     "change_ratio": -0.02, "pe_ttm": 20.0, "market_cap": 4.0e10},   # not equity -> gated
]


def fake_route(method, *a, **k):
    t = a[0]
    if t != "AAPL":
        return "NO_DATA_AVAILABLE: no usable market data"
    return {"get_fundamentals": FUND, "get_balance_sheet": BS,
            "get_income_statement": INC}.get(method, "NO_DATA_AVAILABLE")


def fake_losers(sort_dir="losers", count=50, market="US", min_market_cap=0.0):
    assert sort_dir == "losers" and count == 2 and market == "US"
    return list(_LOSERS)


def fake_hot(count=50, market="US", min_market_cap=0.0):
    assert market == "US"
    return list(_HOT)


@pytest.fixture(autouse=True)
def _patch_vendors():
    with mock.patch.object(vs, "route_to_vendor", side_effect=fake_route), \
         mock.patch("tradingagents.dataflows.moomoo.get_top_movers_moomoo",
                    side_effect=fake_losers), \
         mock.patch("tradingagents.dataflows.moomoo.get_hot_movers_moomoo",
                    side_effect=fake_hot):
        yield


def test_top_losers_adds_name_and_daychg_columns(capsys):
    vs.main(["--universe", "top-losers", "-n", "2", "-d", "2026-01-02", "--min-mcap", "1e9"])
    out = capsys.readouterr().out
    assert "Apple Inc." in out
    assert "-4.21%" in out
    assert "US.AAPL" not in out  # prefix stripped by the vendor fn


def test_min_mcap_floor_gates_universe(capsys):
    """Default $100B floor: only mega-cap losers survive (float cap <= total)."""
    vs.main(["--universe", "top-losers", "-n", "2", "-d", "2026-01-02"])
    out = capsys.readouterr().out
    assert "Apple Inc." in out and "Microsoft Corp." in out  # both > $100B
    vs.main(["--universe", "top-losers", "-n", "2", "-d", "2026-01-02", "--min-mcap", "0"])
    out = capsys.readouterr().out


def test_classic_path_has_no_mover_columns(capsys):
    vs.main(["AAPL", "-d", "2026-01-02"])
    out = capsys.readouterr().out
    assert "DayChg" not in out
    assert "Name |" not in out
    assert "AAPL" in out


def test_universe_caps_limit(capsys):
    vs.main(["--universe", "top-losers", "-n", "2", "-d", "2026-01-02", "-l", "1"])
    out = capsys.readouterr().out
    assert out.count("| 1 |") >= 1


def test_heat_proxy_master_then_losers_with_gates(capsys):
    """heat-proxy: hot master -> losers only -> price>=20, 0<PE<=40, equities."""
    vs.main(["-u", "heat-proxy", "--market", "HK", "-n", "50", "-d", "2026-01-02", "-l", "50"])
    out = capsys.readouterr().out
    assert "Apple Inc." in out and "Microsoft Corp." in out  # losers kept
    assert "NVIDIA" not in out                                # gainer excluded
    assert "Cheap Co" not in out                             # price < 20 gated
    assert "Pricey Inc" not in out                           # PE > 40 gated
    assert "ETF" not in out                                   # non-equity gated


def test_currency_gate_blocks_mixed_ev():
    """Non-USD statement currency must zero out USD-only metrics."""
    fin = {"currency": "JPY", "market_cap": 3.68e10, "total_assets": 3.0e14,
           "cash": 6.8e13, "total_debt": 6.2e12, "operating_income": 5.0e11}
    row = vs.screen_ticker("JPPHY", fin)
    assert row["ev"] is None
    assert row["ev_ebit"] is None
    assert row["earnings_yield"] is None
    assert row["altman_z"] is None
    assert row["net_net"] is False


def test_scale_heuristic_flags_currency_mix():
    fin = {"market_cap": 3.68e10, "total_assets": 3.0e14,
           "cash": 6.8e13, "total_debt": 6.2e12, "operating_income": 5.0e11}
    assert vs._usd_consistent(fin) is False
    row = vs.screen_ticker("JPPHY", fin)
    assert row["ev"] is None
