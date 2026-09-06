"""Tests for the macro-depth additions (Phase: macro spec, all six items).

Covers the FRED liquidity/commodity/global-rate aliases (pure resolution),
the keyless Treasury Fiscal TGA balance (monkeypatched requests), and the
yfinance FX snapshot (monkeypatched yfinance module). Network paths are
live-verified separately; these pin the pure logic and the degrade paths.
"""

import sys

import pytest

import tradingagents.dataflows.fred as fred
import tradingagents.dataflows.fx as fx
import tradingagents.dataflows.treasury_fiscal as tf

pytestmark = pytest.mark.timeout(90)

# ---------------------------------------------------------------------------
# FRED aliases (items 1, 2, 4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("alias", "series_id"),
    [
        # liquidity
        ("tga", "WDTGAL"),
        ("treasury_general_account", "WDTGAL"),
        ("tga_week_avg", "WTREGEN"),
        ("reverse_repo", "RRPONTSYD"),
        ("repo", "RPONTSYD"),
        ("fed_balance_sheet", "WALCL"),
        ("effr", "EFFR"),
        ("sofr", "SOFR"),
        # commodities
        ("wti", "DCOILWTICO"),
        ("crude_oil", "DCOILWTICO"),
        ("gold", "GOLDAMGBD228NLBM"),
        ("natgas", "DHHNGSP"),
        ("henry_hub", "DHHNGSP"),
        ("copper", "PCOPPUSDM"),
        # global policy rates
        ("ecb_rate", "ECBDFR"),
        ("boj_rate", "IRSTCB01JPM156N"),
    ],
)
def test_fred_aliases_resolve(alias, series_id):
    assert fred._resolve_series_id(alias) == series_id


# ---------------------------------------------------------------------------
# Treasury Fiscal TGA (item 3)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": self._data}


def _tga_row(date, bal, acct="Treasury General Account (TGA) Closing Balance"):
    return {"record_date": date, "account_type": acct,
            "close_today_bal": "null", "open_today_bal": str(bal)}


def test_tga_renders_latest_and_draw_read(monkeypatch):
    rows = [_tga_row("2026-09-03", 903_928), _tga_row("2026-09-02", 944_364),
            _tga_row("2026-09-01", 942_800)]
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp(rows))
    out = tf.get_tga_balance(days=3)
    assert "903.9B" in out and "944.4B" in out
    assert "Net draw" in out and "reserve injection" in out


def test_tga_ignores_null_string_and_falls_back(monkeypatch):
    # even a closing row whose fields are all "null"/missing must not crash
    rows = [_tga_row("2026-09-03", None), _tga_row("2026-09-02", None)]
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp(rows))
    out = tf.get_tga_balance(days=2)
    assert "n/a" in out


def test_tga_degrades_on_failure(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr("requests.get", boom)
    out = tf.get_tga_balance()
    assert "unavailable" in out


# ---------------------------------------------------------------------------
# FX snapshot (item 5)
# ---------------------------------------------------------------------------


class _Hist:
    def __init__(self, closes):
        self._closes = closes

    def __len__(self):
        return len(self._closes)

    def tolist(self):
        return self._closes

    def __getitem__(self, key):
        return self

    @property
    def Close(self):
        return self


def _fake_ticker_factory(closes_by_sym):
    class _T:
        def __init__(self, sym):
            self._sym = sym

        def history(self, **kwargs):
            closes = closes_by_sym.get(self._sym)
            if closes is None:
                return type("Empty", (), {"__len__": lambda s: 0})()
            return _Hist(closes)

    return _T


def test_fx_snapshot_renders_pairs(monkeypatch):
    import types

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _fake_ticker_factory(
        {"^DXY": [100.0, 100.5, 101.0, 101.2, 101.5, 101.8] * 2,
         "EURUSD=X": [1.16, 1.16, 1.17, 1.17, 1.16, 1.16] * 2,
         "USDJPY=X": [155.0, 156.0, 155.5, 156.5, 156.0, 156.2] * 2}
    )
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)
    out = fx.get_fx_snapshot()
    assert out is not None
    assert "DXY" in out and "EUR/USD" in out and "USD/JPY" in out
    assert "1d" in out and "5d" in out


def test_fx_snapshot_none_when_all_pairs_missing(monkeypatch):
    import types

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _fake_ticker_factory({})
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)
    assert fx.get_fx_snapshot() is None


# ---------------------------------------------------------------------------
# Tool exports (item 6)
# ---------------------------------------------------------------------------


def test_tools_exported_in_agent_utils():
    from tradingagents.agents.utils.agent_utils import (
        get_fx_snapshot,
        get_tga_balance,
    )

    assert get_tga_balance is not None and get_fx_snapshot is not None
