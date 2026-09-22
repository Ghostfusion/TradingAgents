"""The market-wide panel (P0-2) and the breadth wiring into the two engines.

`market_breadth.market_breadth` (P0-3) was fully implemented with zero
production callers, so `technical_score`'s three breadth legs and
`regime_score.breadth` were declared and never measured on every run. These
tests defend the two things that closes: the panel is built ONCE per run, and
the read reaches the component dicts.

The network is never touched: `market_panel.market_closes` is replaced with a
synthetic panel, so the real `market_breadth` still runs over it and only the
fetch is stubbed.
"""

from __future__ import annotations

from unittest import mock

import pytest

from tradingagents.agents.utils import analysis_tools as T
from tradingagents.dataflows import market_panel as mp, sp500_universe as su
from tradingagents.strategies.market_breadth import market_breadth

BARS = 260
#: 20 rising + 5 falling = 80% above the 50d/200d SMA and (20-5)/25 = 0.6 A/D.
PANEL_UP, PANEL_DOWN = 20, 5


def _rising(bars: int = BARS, drift: float = 0.1) -> list[float]:
    return [100.0 + drift * i for i in range(bars)]


def _falling(bars: int = BARS, drift: float = 0.1) -> list[float]:
    return [100.0 - drift * i for i in range(bars)]


def _panel(up: int = PANEL_UP, down: int = PANEL_DOWN) -> dict:
    panel = {f"UP{i}": _rising() for i in range(up)}
    panel.update({f"DN{i}": _falling() for i in range(down)})
    return panel


def _ohlcv_block(closes: list[float]) -> dict:
    return {
        "closes": list(closes),
        "highs": [c + 0.5 for c in closes],
        "lows": [c - 0.5 for c in closes],
        "volumes": [5_000_000.0] * len(closes),
    }


@pytest.fixture(autouse=True)
def _clean_caches():
    T._clear_ohlcv_cache()
    mp._reset_market_panel_cache()
    yield
    T._clear_ohlcv_cache()
    mp._reset_market_panel_cache()


# ---------------------------------------------------------------------------
# The panel builder
# ---------------------------------------------------------------------------


def test_the_panel_carries_every_name_the_universe_named():
    got = mp.market_closes(lambda t: _rising(60),
                           universe={"rows": {"Tech": ["AAA", "BBB"], "Energy": ["CCC"]}})
    assert sorted(got) == ["AAA", "BBB", "CCC"]
    assert all(len(v) == 60 for v in got.values())


def test_the_universe_is_deduplicated():
    """Two sectors listing the same ticker is one name, not two."""
    got = mp.market_closes(lambda t: _rising(60),
                           universe={"rows": {"Tech": ["AAA", "BBB"], "Other": ["AAA"]}})
    assert sorted(got) == ["AAA", "BBB"]


def test_the_panel_is_built_once_for_the_process():
    """The owner's decision: one S&P 500 panel per run, not per call."""
    calls = []

    def fetch(ticker):
        calls.append(ticker)
        return _rising(60)

    universe = {"rows": {"Tech": ["AAA", "BBB", "CCC"]}}
    first = mp.market_closes(fetch, universe=universe)
    second = mp.market_closes(fetch, universe=universe)
    assert calls == ["AAA", "BBB", "CCC"]  # not six
    assert first is second


def test_a_failing_fetch_stays_in_the_panel_with_an_empty_series():
    """A dropped name would leave the denominator; `market_breadth`'s coverage
    must report it instead."""
    def fetch(ticker):
        if ticker == "BBB":
            raise RuntimeError("vendor down")
        return _rising(60)

    got = mp.market_closes(fetch, universe={"rows": {"Tech": ["AAA", "BBB"]}})
    assert got["BBB"] == []
    read = market_breadth(got, min_n=1)
    assert read["n"] == 1 and read["coverage"] == 0.5


def test_limit_bounds_the_panel():
    got = mp.market_closes(lambda t: _rising(60),
                           universe={"rows": {"Tech": ["AAA", "BBB", "CCC"]}}, limit=2)
    assert len(got) == 2


def test_an_unavailable_universe_is_an_empty_panel_not_a_partial_one(monkeypatch):
    monkeypatch.setattr(su, "fetch_sp500_universe", lambda refresh=False: None)
    assert mp.market_closes(lambda t: _rising(60)) == {}


def test_an_empty_panel_is_none_from_the_producer():
    assert market_breadth({}) is None


# ---------------------------------------------------------------------------
# The wiring into the two engines
# ---------------------------------------------------------------------------


@pytest.fixture
def _stub_market(monkeypatch):
    """A synthetic panel, a stubbed price fetch, and no network on the VIX legs."""
    monkeypatch.setattr(mp, "market_closes", lambda fetch, **kw: _panel())
    monkeypatch.setattr(T, "_ohlcv", lambda ticker, days=320: _ohlcv_block(_rising()))
    monkeypatch.setattr(T, "_vix_percentile_read", lambda *a, **k: {})
    monkeypatch.setattr(
        "tradingagents.dataflows.cboe.vix_term_structure", lambda *a, **k: {}
    )
    return _panel()


def test_the_technical_breadth_legs_come_from_the_shared_panel(_stub_market):
    vals = T._technical_components("TEST")
    assert vals["pct_above_50d"] == pytest.approx(80.0)
    assert vals["pct_above_200d"] == pytest.approx(80.0)
    assert vals["ad_ratio"] == pytest.approx(0.6)


def test_the_regime_breadth_leg_reads_the_50d_column(_stub_market):
    vals = T._regime_components()
    assert vals["breadth"] == pytest.approx(80.0)


def test_both_engines_share_one_panel_build(monkeypatch):
    """The two assemblers and the run card all read one panel per run."""
    calls = []
    monkeypatch.setattr(
        mp, "market_closes", lambda fetch, **kw: (calls.append(1), _panel())[1]
    )
    monkeypatch.setattr(T, "_ohlcv", lambda ticker, days=320: _ohlcv_block(_rising()))
    monkeypatch.setattr(T, "_vix_percentile_read", lambda *a, **k: {})
    monkeypatch.setattr(
        "tradingagents.dataflows.cboe.vix_term_structure", lambda *a, **k: {}
    )
    T._technical_components("TEST")
    T._regime_components()
    assert len(calls) == 1


def test_an_unavailable_panel_leaves_breadth_absent_never_zero(monkeypatch):
    """The whole point of the gate: a named gap, not a confident zero."""
    monkeypatch.setattr(mp, "market_closes", lambda fetch, **kw: {})
    monkeypatch.setattr(T, "_ohlcv", lambda ticker, days=320: _ohlcv_block(_rising()))
    vals = T._technical_components("TEST")
    assert "pct_above_50d" not in vals
    assert "pct_above_200d" not in vals
    assert "ad_ratio" not in vals
    assert "rsi" in vals  # the name's own legs are unaffected


def test_a_panel_below_min_n_leaves_breadth_absent_never_zero(monkeypatch):
    monkeypatch.setattr(
        mp, "market_closes", lambda fetch, **kw: {f"S{i}": _rising(60) for i in range(4)}
    )
    monkeypatch.setattr(T, "_ohlcv", lambda ticker, days=320: _ohlcv_block(_rising()))
    vals = T._technical_components("TEST")
    assert "pct_above_50d" not in vals and "ad_ratio" not in vals


def test_the_panel_is_fetched_through_the_runs_own_ohlcv_cache(monkeypatch):
    """The panel must not become a second price source: every series it carries
    comes from `_ohlcv`, so it cannot describe a different basis than the run."""
    monkeypatch.setattr(
        su, "fetch_sp500_universe",
        lambda refresh=False: {"rows": {"Tech": ["AAA", "SPY"]}},
    )
    monkeypatch.setattr(T, "_ohlcv", lambda ticker, days=320: _ohlcv_block(_rising(60)))
    mp._reset_market_panel_cache()
    panel = mp.market_closes(lambda t: T._ohlcv(t).get("closes") or [])
    assert panel["AAA"] == _rising(60)


def test_the_read_degrades_to_none_when_the_panel_raises(monkeypatch):
    def boom(fetch, **kw):
        raise RuntimeError("universe offline")

    monkeypatch.setattr(mp, "market_closes", boom)
    with mock.patch.object(T, "_RUN_BREADTH_CACHE", {}):
        assert T._market_breadth_read() is None
