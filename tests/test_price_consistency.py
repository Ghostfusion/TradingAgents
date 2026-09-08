"""Hermetic tests for the price-scale/staleness consistency guard.

Regression (INTU 2026-09-08): several setup tools (swing_set / swing_exits /
post_close / session_discipline / candlestick / bollinger / support / macd)
computed on a stale or wrongly-scaled OHLCV series (close 332.70 / ~677)
while the verified snapshot's close was 314.12 — so actionable stops, targets
and psych levels were silently built on the wrong price. The guard records the
verified close and warns any OHLCV tool whose latest close disagrees.
"""

from __future__ import annotations

import pytest

from tradingagents.agents.utils import price_consistency as PC
from tradingagents.agents.utils.price_consistency import (
    clear_verified_close_cache,
    ohlcv_scale_warning,
    set_verified_close,
)

pytestmark = pytest.mark.timeout(120)


@pytest.fixture(autouse=True)
def _clean_cache():
    clear_verified_close_cache()
    yield
    clear_verified_close_cache()


class TestVerifiedCloseCache:
    def test_set_and_read(self):
        set_verified_close("INTU", 314.12)
        assert PC.verified_close("intu") == 314.12  # case-insensitive
        set_verified_close("INTU", None)  # no-op
        assert PC.verified_close("INTU") == 314.12

    def test_missing_ticker_returns_none(self):
        assert PC.verified_close("NOPE") is None


class TestScaleWarning:
    def test_agreeing_close_no_warning(self):
        set_verified_close("INTU", 314.12)
        assert ohlcv_scale_warning("INTU", 314.12) == ""

    def test_agreeing_close_tolerance(self):
        set_verified_close("INTU", 314.12)
        assert ohlcv_scale_warning("INTU", 314.5) == ""  # <1%

    def test_stale_close_warns(self):
        set_verified_close("INTU", 314.12)
        warn = ohlcv_scale_warning("INTU", 332.70)  # the 9/4 stale close
        assert "PRICE-SCALE WARNING" in warn
        assert "332.70" in warn and "314.12" in warn
        assert "UNRELIABLE" in warn

    def test_corrupted_scale_warns_via_tuple(self):
        """The ~677-scale series (bollinger/support/macd price_lows) must be
        caught even when passed as a tuple of closes."""
        set_verified_close("INTU", 314.12)
        warn = ohlcv_scale_warning("INTU", (633.47, 649.1))
        assert "PRICE-SCALE WARNING" in warn

    def test_no_verified_close_no_warning(self):
        assert ohlcv_scale_warning("INTU", 332.70) == ""


def test_verified_close_populated_by_snapshot_builder(monkeypatch):
    """build_verified_market_snapshot records the authoritative close."""
    import pandas as pd

    from tradingagents.dataflows import market_data_validator as mdv

    df = pd.DataFrame(
        {
            "Date": ["2026-09-04", "2026-09-08"],
            "Open": [341.36, 325.36],
            "High": [346.00, 327.00],
            "Low": [330.12, 313.13],
            "Close": [332.70, 314.12],
            "Volume": [1234567, 1700915],
        }
    )
    monkeypatch.setattr(mdv, "_verified_rows", lambda symbol, d: df)
    mdv.build_verified_market_snapshot("INTU", "2026-09-08")
    assert PC.verified_close("INTU") == pytest.approx(314.12)
