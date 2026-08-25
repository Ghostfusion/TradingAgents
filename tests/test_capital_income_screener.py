"""Standalone capital-income screener (scripts/capital_income_screener.py) tests.

Hermetic: yfinance + the vendor OHLCV chain are mocked so no network is
touched. Verifies the three-stage methodology (liquidity screen -> yield rank
-> cap/weight) end-to-end through the CLI, and that it runs standalone (no
graph/agent imports).
"""


from pathlib import Path

import pytest

import scripts.capital_income_screener as cis


class _FakeTicker:
    """Minimal yfinance Ticker stand-in with price + info."""

    def __init__(self, price, dividend_rate, market_cap=None):
        self._price = price
        self._info = {
            "dividendRate": dividend_rate,
            "marketCap": market_cap,
        }
        self.fast_info = type("FI", (), {"last_price": price})()

    def get_info(self):
        return self._info

    def history(self, period="5d"):
        import pandas as pd

        return pd.DataFrame({"Close": [self._price]})


def _patch_yf(monkeypatch, tickers: dict):
    """tickers: {SYM: (price, dividend_rate, market_cap)}."""
    import yfinance as yf

    def fake_ticker(sym):
        p, d, mc = tickers[sym]
        return _FakeTicker(p, d, mc)

    monkeypatch.setattr(yf, "Ticker", fake_ticker)


def _patch_route(monkeypatch, csv_by_sym: dict):
    """Mock the vendor OHLCV chain: {SYM: csv}. The script imports
    route_to_vendor at module level, so patch the script's own reference."""

    def fake_route(method, *a, **k):
        if method == "get_stock_data":
            sym = a[0].upper()
            return csv_by_sym.get(sym, "")
        return ""

    monkeypatch.setattr(cis, "route_to_vendor", fake_route)


def _csv(closes, vols):
    rows = ["Date,Open,High,Low,Close,Volume"]
    for i, (c, v) in enumerate(zip(closes, vols, strict=False)):
        rows.append(f"2026-01-{i % 28 + 1:02d},{c},{c},{c},{c},{v}")
    return "\n".join(rows) + "\n"


def test_standalone_imports_no_graph():
    """The script must not import the graph or any agent module (static
    check - order-independent)."""
    src_path = Path(cis.__file__)
    src = src_path.read_text(encoding="utf-8")
    assert "tradingagents.graph" not in src
    assert "tradingagents.agents" not in src
    # It only pulls the safe vendor chain + the pure strategy module.
    assert "tradingagents.dataflows.interface" in src
    assert "tradingagents.strategies.capital_income" in src


def test_screener_ranks_by_yield_and_caps(monkeypatch, capsys):
    _patch_yf(monkeypatch, {
        "A": (20.0, 1.5, 500e6),   # yield 7.5%
        "B": (25.0, 1.0, 300e6),   # yield 4.0%
        "C": (30.0, 2.4, 900e6),   # yield 8.0% -> top
    })
    _patch_route(monkeypatch, {
        "A": _csv([20.0] * 70, [100_000] * 70),   # ADTV $2M
        "B": _csv([25.0] * 70, [60_000] * 70),    # ADTV $1.5M
        "C": _csv([30.0] * 70, [100_000] * 70),   # ADTV $3M
    })
    rc = cis.main(["A", "B", "C", "--top", "2", "--min-mcap", "0", "--min-adtv", "0", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    # top-2 by yield = C (8%) then A (7.5%)
    assert "| 1 | C |" in out
    assert "| 2 | A |" in out
    assert "8.00" in out and "7.50" in out
    # equal-weight fallback (MV n/a for preferreds) -> 50% each for 2 names
    assert "50.0%" in out


def test_screener_liquidity_gate_filters(monkeypatch, capsys):
    _patch_yf(monkeypatch, {
        "A": (20.0, 1.5, 500e6),   # liquid
        "B": (25.0, 1.0, 50e6),    # below $250M -> not liquid
    })
    _patch_route(monkeypatch, {
        "A": _csv([20.0] * 70, [100_000] * 70),
        "B": _csv([25.0] * 70, [60_000] * 70),
    })
    rc = cis.main(["A", "B", "--top", "50", "--min-mcap", "250", "--min-adtv", "1", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| 1 | A |" in out
    assert "| 2 | B |" not in out  # B fails the market-cap gate


def test_screener_json_output(monkeypatch, capsys):
    _patch_yf(monkeypatch, {"A": (20.0, 1.5, 500e6)})
    _patch_route(monkeypatch, {"A": _csv([20.0] * 70, [100_000] * 70)})
    rc = cis.main(["A", "--top", "50", "--min-mcap", "0", "--min-adtv", "0", "--json"])
    assert rc == 0
    import json

    plan = json.loads(capsys.readouterr().out)
    assert plan["ranked"][0]["ticker"] == "A"
    assert plan["ranked"][0]["yield"] == pytest.approx(0.075, rel=0.01)


def test_screener_no_tickers_errors(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        cis.main([])
