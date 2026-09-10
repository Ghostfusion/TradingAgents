"""Tests for the ETF decline-driver hierarchy.

The IGV 2026-09-09 review loop: get_decline_driver_check returned clean=True
for an ETF — a company-oriented screen (fraud/distress, negative FCF/ROE)
meaningless for a fund. etf_decline_driver classifies the cause of an ETF's
decline into MARKET / SECTOR / ETF_SPECIFIC / CONSTITUENT_DRIVEN / UNKNOWN.
"""

from __future__ import annotations

from tradingagents.strategies.etf_decline_driver import etf_decline_driver


def _closes(down: float, window: int = 80) -> list[float]:
    """A noisy walk that ends exactly ``down``% below its own recent peak.

    The last 10 bars interpolate linearly to a level ``(1-down)`` of the
    bar-10 peak, so the end-of-series drawdown is ≈ ``down`` (not an
    exponential per-bar drop that overshoots)."""
    import random

    rng = random.Random(42)
    series = [100.0]
    for _ in range(window):
        series.append(series[-1] + rng.uniform(-0.5, 0.5))
    target = series[-10] * (1.0 - down)  # drawdown measured from ~10 bars back
    start = series[-10]
    for i in range(1, 11):
        series.append(start + (target - start) * i / 10.0)
    return series


def test_market_driven_on_spy_drawdown():
    spy = _closes(down=0.15)
    r = etf_decline_driver("IGV", spy_closes=spy)
    assert r["driver"] == "MARKET_DRIVEN"


def test_market_driven_on_vix_spike():
    vix = [25.0] * 60 + [35.0] * 10
    r = etf_decline_driver("IGV", vix_series=vix, vix_spike_threshold=30.0)
    assert r["driver"] == "MARKET_DRIVEN"


def test_sector_driven_on_xlk_drawdown():
    xlk = _closes(down=0.10)
    r = etf_decline_driver("IGV", xlk_closes=xlk, sector_dd_threshold=-0.08)
    assert r["driver"] == "SECTOR_DRIVEN"


def test_etf_specific_on_relative_weakness():
    etf = _closes(down=0.07)
    xlk = _closes(down=0.02)
    r = etf_decline_driver(
        "IGV", etf_closes=etf, xlk_closes=xlk,
        sector_dd_threshold=-0.08, etf_dd_threshold=-0.05,
    )
    # etf dd -7% > its threshold; XLK only -2% -> not sector; relative 3m -> ETF_SPECIFIC
    assert r["driver"] == "ETF_SPECIFIC"


def test_market_precedes_sector():
    spy = _closes(down=0.15)
    xlk = _closes(down=0.10)
    r = etf_decline_driver("IGV", spy_closes=spy, xlk_closes=xlk)
    assert r["driver"] == "MARKET_DRIVEN"


def test_unknown_when_no_signals():
    assert etf_decline_driver("IGV")["driver"] == "UNKNOWN"
    assert etf_decline_driver("IGV", etf_closes=_closes(down=0.0), spy_closes=_closes(down=0.0))["driver"] == "UNKNOWN"
