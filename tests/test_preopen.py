"""P1/P2/C3 pre-open + execution-quality helpers - offline tests.

preopen.py is pure reads over Alpaca bars/quotes (mocked here) - no network.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tradingagents.dataflows import preopen as po

pytestmark = pytest.mark.timeout(180)


def _bar(ts: str, v: float, c: float = 100.0) -> dict:
    return {"t": ts, "v": v, "c": c}


def _premarket_bars(days: int = 30, avg_vol: float = 100_000.0, today_vol: float = 250_000.0):
    """Synthetic 30-day pre-open 15-min bar series (UTC, 08:00Z = 04:00 ET)."""
    bars = []
    day = datetime(2026, 7, 1, tzinfo=timezone.utc)
    from datetime import timedelta

    for d in range(days):
        ts = (day + timedelta(days=d)).isoformat().replace("+00:00", "Z")
        v = avg_vol if d < days - 1 else today_vol
        bars.append(_bar(f"{ts[:10]}T08:00:00Z", v * 0.5))
        bars.append(_bar(f"{ts[:10]}T08:45:00Z", v * 0.3))
        bars.append(_bar(f"{ts[:10]}T09:20:00Z", v * 0.2))
    return bars


def test_premarket_rvol_computes_ratio(monkeypatch):
    """Today's pre-open volume / 30d avg -> the institutional RVOL read."""
    from tradingagents.dataflows import alpaca_common as ac

    bars = _premarket_bars(30, avg_vol=100_000.0, today_vol=250_000.0)
    monkeypatch.setattr(ac, "alpaca_get", lambda *a, **k: {"bars": bars})
    monkeypatch.setattr(ac, "alpaca_credentials", lambda: ("k", "s"))
    out = po.premarket_rvol("AAPL")
    assert out["rvol"] is not None
    # today = 250k, avg = 100k -> 2.5x
    assert out["rvol"] == pytest.approx(2.5, abs=0.2)
    assert out["window_days"] >= 20


def test_premarket_rvol_alpaca_off_returns_unavailable(monkeypatch):
    """No credentials -> explicit unavailable, never fabricated."""
    from tradingagents.dataflows import alpaca_common as ac

    monkeypatch.setattr(ac, "alpaca_credentials", lambda: (None, None))
    out = po.premarket_rvol("AAPL")
    assert out["rvol"] is None
    assert "alpaca not configured" in out["reason"]


def test_preopen_gap_missing_inputs_none():
    out = po.preopen_gap("AAPL", prev_close=None, latest_trade=100.0)
    assert out["gap_pct"] is None
    assert "missing" in out["reason"]


def test_preopen_gap_computes():
    out = po.preopen_gap("AAPL", prev_close=100.0, latest_trade=102.5)
    assert out["gap_pct"] == pytest.approx(0.025)
    assert out["preopen_price"] == 102.5


def test_preopen_book_depth_thin_detected():
    q = {"ap": 101.0, "as": 50, "bp": 100.0, "bs": 40}
    out = po.preopen_book_depth("AAPL", quote=q)
    assert out["spread_bps"] == pytest.approx(99.5, abs=1.0)  # (101-100)/100.5*1e4
    assert out["bid_ask_imbalance"] == pytest.approx(-0.111, abs=0.02)  # (40-50)/90
    assert out["thin"] is True


def test_preopen_book_depth_no_quote():
    out = po.preopen_book_depth("AAPL", quote={})
    assert out["spread_bps"] is None and out["thin"] is None


def test_postfill_drift_positive_and_none():
    assert po.postfill_drift(100.0, 101.0, 1)["drift_pct"] == pytest.approx(0.01)
    out = po.postfill_drift(None, 101.0, 1)
    assert out["drift_pct"] is None
    assert po.postfill_drift(100.0, 95.0, 3)["drift_pct"] == pytest.approx(-0.05)
