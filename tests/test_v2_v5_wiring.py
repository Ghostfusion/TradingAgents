"""V2/V3 wiring unit tests: screener composite rank + allocation; exits; alloc block."""

from contextlib import ExitStack, contextmanager
from unittest import mock

import pytest

import scripts.value_screener as vs
from tradingagents.dataflows import statement_parsing as _sp_parsing
from tradingagents.strategies.contract import build_position_contract
from tradingagents.strategies.portfolio import allocation_block


@contextmanager
def _patched_router(route):
    """Patch the vendor router wherever this module reaches it.

    ``fetch_ticker`` now lives in ``statement_parsing`` (the installed-CLI
    contract), so patching only ``vs.route_to_vendor`` leaks live vendor
    calls; patch both bindings.
    """
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(vs, "route_to_vendor", side_effect=route))
        stack.enter_context(
            mock.patch.object(_sp_parsing, "route_to_vendor", side_effect=route)
        )
        yield


def _closes_csv(step):
    rows = ["Date,Open,High,Low,Close,Volume"]
    price = 100.0
    for i in range(140):
        price += step
        rows.append(
            f"2026-01-{i % 28 + 1:02d},{price:.2f},{price + 3:.2f},{price - 3:.2f},{price:.2f},5000000"
        )
    return "\n".join(rows) + "\n"


FUND = "Market Cap: 3.2T\n"
BS = (
    "Date,2025-12-31\nCash And Cash Equivalents,300M\nTotal Debt,400M\n"
    "Total Assets,2.0B\nTotal Current Assets,700M\nTotal Current Liabilities,500M\n"
    "Total Liabilities,900M\nRetained Earnings,800M\nProperty Plant Equipment,400M"
)
INC = (
    "Date,2025-12-31\nTotal Revenue,1.0B\nOperating Income,150M\n"
    "Net Income,100M\nInterest Expense,10M\nTax Expense,20M"
)


def fake_route(method, *a, **k):
    t = a[0]
    if method == "get_stock_data":
        return _closes_csv(0.5) if t == "AAPL" else _closes_csv(0.0)
    if t != "AAPL":
        return "NO_DATA_AVAILABLE: no usable market data"
    return {"get_fundamentals": FUND, "get_balance_sheet": BS, "get_income_statement": INC}.get(
        method, "NO_DATA_AVAILABLE"
    )


def fake_losers(sort_dir="losers", count=50, market="US", min_market_cap=0.0):
    return [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "cur_price": 210.5,
            "change_ratio": -0.0421,
            "pe_ttm": 28.1,
            "market_cap": 3.2e12,
        },
        {
            "symbol": "MSFT",
            "name": "Microsoft Corp.",
            "cur_price": 95.2,
            "change_ratio": -0.031,
            "pe_ttm": 35.0,
            "market_cap": 7.0e12,
        },
    ]


@pytest.fixture(autouse=True)
def _patch():
    with (
        _patched_router(fake_route),
        mock.patch("tradingagents.dataflows.moomoo.get_top_movers_moomoo", side_effect=fake_losers),
        mock.patch("tradingagents.dataflows.moomoo.get_hot_movers_moomoo", side_effect=fake_losers),
    ):
        yield


def test_composite_scores_ranks_momentum_higher():
    closes = {"AAPL": [100.0 + 0.5 * i for i in range(140)], "MSFT": [100.0] * 140}
    scores = vs.composite_scores(
        [{"ticker": "AAPL", "earnings_yield": 0.05}, {"ticker": "MSFT", "earnings_yield": None}],
        closes,
    )
    assert scores["AAPL"] > scores["MSFT"]


def test_alloc_flag_prints_plan(capsys):
    vs.main(
        ["--universe", "top-losers", "-n", "2", "-d", "2026-01-02", "--min-mcap", "1e9", "--alloc"]
    )
    out = capsys.readouterr().out
    assert "Allocation plan" in out


def test_allocation_block_sums_to_one_when_uncapped():
    text = allocation_block({"A": 0.5, "B": 0.3, "C": 0.2}, cfg={"max_name_weight": 0.5})
    assert "Allocation plan" in text
    assert "allocated: 100.0%" in text


def test_volume_and_atr_gates_defaults_pass():
    """Default gates (vol>=1M, ATR%>2) accept the fixture OHLCV."""
    with _patched_router(fake_route):
        o = vs._fetch_ohlcv("MSFT")
    assert len(o["closes"]) >= 100
    avg_vol = sum(o["volumes"][-30:]) / 30
    assert avg_vol >= 1_000_000
    from tradingagents.strategies.size import atr

    a = atr(o["highs"], o["lows"], o["closes"], window=14)
    assert (a / o["closes"][-1] * 100.0) > 2.0


def test_contract_exits_fields_when_enabled():
    closes = [100.0 + 0.1 * i for i in range(20)]
    c = build_position_contract(
        cfg={"enable_exits": True, "atr_mult": 2.0, "breakeven_atr": 1.0, "target_atr": 4.0},
        closes=closes,
    )
    assert c is not None
    assert c.breakeven_stop is not None and c.target is not None
    assert "exits:" in (c.exit_note or "")
