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


class TestRunPriceBasis:
    """The evidence block's price basis (GOOG 2026-09-11 fact-check).

    The fundamentals report compared a FORMING 336.37 intraday close against
    intrinsic value, a PT upside and a 200-day SMA while the market section
    flagged the same bar provisional - and on the prior settled close the price
    was BELOW that SMA, so the structural read flips. The fundamentals analyst
    has no market-snapshot tool, so the basis is recorded once by the run OHLCV
    loader and rendered above the evidence leaves.
    """

    def test_set_and_read(self):
        PC.set_price_basis("goog", 336.37, as_of="2026-09-11")
        assert PC.price_basis("GOOG") == ("2026-09-11", 336.37)

    def test_forming_bar_is_labelled_provisional(self):
        PC.set_price_basis("GOOG", 336.37, as_of="2026-09-11")
        line = PC.price_basis_line("GOOG", curr_date="2026-09-11")
        assert "336.37" in line
        assert "FORMING intraday bar" in line
        assert "provisional" in line

    def test_settled_close_is_labelled_settled(self):
        PC.set_price_basis("GOOG", 330.39, as_of="2026-09-10")
        line = PC.price_basis_line("GOOG", curr_date="2026-09-11")
        assert "330.39" in line
        assert "settled close" in line
        assert "FORMING" not in line

    def test_unknown_basis_says_nothing(self):
        assert PC.price_basis_line("GOOG", curr_date="2026-09-11") == ""

    def test_clear_drops_the_basis_too(self):
        PC.set_price_basis("GOOG", 336.37, as_of="2026-09-11")
        clear_verified_close_cache()
        assert PC.price_basis("GOOG") is None


def test_ohlcv_loader_records_the_price_basis(monkeypatch):
    """The run-series loader is the single producer: whatever the price-derived
    tools computed on is what the evidence block states."""
    import pandas as pd

    from tradingagents.agents.utils import analysis_tools as AT

    df = pd.DataFrame(
        {
            "Date": ["2026-09-09", "2026-09-10", "2026-09-11"],
            "Close": [331.0, 330.39, 336.37],
            "High": [333.0, 332.0, 339.95],
            "Low": [329.0, 328.38, 332.74],
            "Open": [330.0, 331.0, 333.0],
            "Volume": [1_000_000.0, 1_100_000.0, 900_000.0],
        }
    )
    AT._clear_ohlcv_cache()
    monkeypatch.setattr(AT, "_load_ohlcv_df", lambda ticker: df)
    AT._ohlcv("GOOG")
    assert PC.price_basis("GOOG") == ("2026-09-11", 336.37)
    AT._clear_ohlcv_cache()
