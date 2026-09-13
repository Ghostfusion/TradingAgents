"""S10 unit tests: resolve_peer_universe (offline; vendor calls monkeypatched).

Guards: the symbol-list fetch is skipped when the caller supplies its own
universe; per-name failures are counted; a sub-floor group returns None.
"""

from tradingagents.strategies.cross_section import group_median
from tradingagents.strategies.peer_universe import resolve_peer_universe

PANEL_KEYS = {"f", "m", "z", "o", "gp_a", "noa", "accruals"}


def _fin():
    return {
        "net_income": {"current": 120.0, "prior": 80.0},
        "operating_cashflow": 150.0,
        "total_assets": {"current": 1000.0, "prior": 900.0},
        "total_liabilities": {"current": 500.0, "prior": 450.0},
        "current_assets": {"current": 400.0, "prior": 350.0},
        "current_liabilities": {"current": 200.0, "prior": 250.0},
        "total_equity": {"current": 400.0, "prior": 350.0},
        "market_cap": 600.0,
        "revenue": {"current": 1200.0, "prior": 1000.0},
        "cogs": {"current": 700.0, "prior": 650.0},
        "retained_earnings": 200.0,
        "working_capital": 200.0,
        "shares": {"current": 100.0, "prior": 100.0},
        "net_receivables": {"current": 100.0, "prior": 90.0},
        "ppem": {"current": 500.0, "prior": 480.0},
        "cash": {"current": 150.0, "prior": 120.0},
        "depreciation": {"current": 50.0, "prior": 45.0},
    }


def _patch_fetch(monkeypatch, fn):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", fn)


def _patch_sector(monkeypatch, fn):
    monkeypatch.setattr("tradingagents.dataflows.yfinance_sector.fetch_sector", fn)


def test_symbol_list_path(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.dataflows.eodhd.get_exchange_symbols_eodhd",
        lambda market="US": [
            {"Code": "AAA", "Type": "Common Stock", "Exchange": "NYSE"},
            {"Code": "BBB", "Type": "Common Stock", "Exchange": "NASDAQ"},
            {"Code": "CCC", "Type": "Common Stock", "Exchange": "PINK"},
            {"Code": "DDD", "Type": "ETF", "Exchange": "NYSE"},
        ],
    )
    _patch_fetch(monkeypatch, lambda t, d: _fin())
    _patch_sector(monkeypatch, lambda t: {"AAA": "Technology", "BBB": "Financials"}.get(t.upper()))

    out = resolve_peer_universe(current_date="2026-01-01")
    assert out["tickers"] == ["AAA", "BBB"]
    assert out["n"] == 2
    assert out["sectors"] == {"AAA": "Technology", "BBB": "Financials"}
    assert out["dropped"].get("exchange filtered (not NYSE/Nasdaq)") == 1
    assert set(out["metrics"]["AAA"]) <= PANEL_KEYS
    assert "f" in out["metrics"]["AAA"]
    assert "EODHD US common stock list" in out["basis"]


def test_explicit_tickers_skip_symbol_list(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("exchange symbol list must not be fetched")

    monkeypatch.setattr("tradingagents.dataflows.eodhd.get_exchange_symbols_eodhd", boom)
    _patch_fetch(monkeypatch, lambda t, d: _fin())
    _patch_sector(monkeypatch, lambda t: "Technology")

    out = resolve_peer_universe(tickers=["aaa", "AAA", "bbb"], current_date="2026-01-01")
    assert out["tickers"] == ["AAA", "BBB"]
    assert "explicit ticker list" in out["basis"]


def test_financials_skip_statement_fetch(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("statement fetch must not run when financials are supplied")

    _patch_fetch(monkeypatch, boom)
    _patch_sector(monkeypatch, lambda t: "Technology")

    out = resolve_peer_universe(tickers=["AAA"], financials={"AAA": _fin()})
    assert out["tickers"] == ["AAA"]


def test_per_name_failure_is_counted(monkeypatch):
    def fetch(t, d):
        if t == "BBB":
            raise RuntimeError("vendor down")
        return _fin()

    _patch_fetch(monkeypatch, fetch)
    _patch_sector(monkeypatch, lambda t: "Technology")

    out = resolve_peer_universe(tickers=["AAA", "BBB"])
    assert out["tickers"] == ["AAA"]
    assert out["dropped"].get("statement_fetch_failed") == 1


def test_resolved_group_below_floor_returns_none(monkeypatch):
    _patch_fetch(monkeypatch, lambda t, d: _fin())
    _patch_sector(monkeypatch, lambda t: "Technology")

    out = resolve_peer_universe(tickers=["AAA", "BBB"])
    values = {t: out["metrics"][t]["f"] for t in out["tickers"]}
    med = group_median(values, out["sectors"], min_n=5)
    assert med["Technology"] is None
