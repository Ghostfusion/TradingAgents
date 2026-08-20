"""--scan strategies: trend-pullback (A) and breakout (B) signal tests."""

from unittest import mock

import pytest

import scripts.value_screener as vs


def _ohlcv(closes, vols, hi_off=0.5, lo_off=0.5):
    return {
        "closes": [float(c) for c in closes],
        "highs": [float(c) + hi_off for c in closes],
        "lows": [float(c) - lo_off for c in closes],
        "volumes": [float(v) for v in vols],
    }


@pytest.fixture(autouse=True)
def _patch_network():
    with (
        mock.patch.object(vs, "route_to_vendor", side_effect=_fixture_route),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_top_movers_moomoo", side_effect=_fake_losers_offline
        ),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_hot_movers_moomoo", side_effect=_fake_losers_offline
        ),
    ):
        yield


def test_breakout_strategy_flagged():
    # Long uptrend to new highs, then a 10x volume spike candle.
    closes = [100.0 + 0.2 * i for i in range(230)]
    volumes = [1_000_000.0] * 229 + [10_000_000.0]
    sig = vs.scan_signals(_ohlcv(closes, volumes))
    assert sig is not None
    assert sig["b"] is True
    assert sig["rvol"] is not None and sig["rvol"] > 1.5
    assert sig["hi52_dist"] >= -0.10


def test_insufficient_history_none():
    assert vs.scan_signals(_ohlcv([100.0] * 50, [1e6] * 50)) is None


def test_metrics_present_on_fixture():
    closes = [100.0 + 0.3 * i for i in range(240)]
    vols = [5_000_000.0] * 240
    sig = vs.scan_signals(_ohlcv(closes, vols))
    assert sig is not None
    assert {"a", "b", "rsi", "qret", "rvol", "squeeze", "hi52_dist"} <= set(sig)


def _breakout_route(method, *a, **k):
    if method == "get_stock_data":
        rows = ["Date,Open,High,Low,Close,Volume"]
        price = 100.0
        for i in range(240):
            price += 0.2
            vol = "10000000" if i == 239 else "1000000"
            rows.append(
                f"2026-01-{i % 28 + 1:02d},{price:.2f},{price + 3:.2f},{price - 3:.2f},{price:.2f},{vol}"
            )
        return "\n".join(rows) + "\n"
    return "NO_DATA_AVAILABLE: no usable market data"


def test_scan_all_keeps_rows_and_flags(capsys):
    """--scan all keeps everything and adds ScanA/ScanB columns."""
    with mock.patch.object(vs, "route_to_vendor", side_effect=_breakout_route):
        vs.main(
            [
                "--universe",
                "top-losers",
                "-n",
                "2",
                "-d",
                "2026-01-02",
                "--min-mcap",
                "1e9",
                "--scan",
                "all",
            ]
        )
    out = capsys.readouterr().out
    assert "ScanA" in out and "ScanB" in out


def _fixture_route(method, *a, **k):
    if method == "get_stock_data":
        rows = ["Date,Open,High,Low,Close,Volume"]
        price = 100.0
        for i in range(240):
            price += 0.2  # steady uptrend, flat volume -> rvol ~1 -> B false
            rows.append(
                f"2026-01-{i % 28 + 1:02d},{price:.2f},{price + 3:.2f},{price - 3:.2f},{price:.2f},5000000"
            )
        return "\n".join(rows) + "\n"
    return "NO_DATA_AVAILABLE: no usable market data"


def _momentum_route(method, *a, **k):
    if method == "get_stock_data":
        rows = ["Date,Open,High,Low,Close,Volume"]
        price = 15.0  # in the $2-$20 band
        vols = ["1000000"] * 59 + ["8000000"]  # RVOL ~8
        for i, vol in enumerate(vols):
            rows.append(
                f"2026-01-{i % 28 + 1:02d},{price:.2f},{price + 0.2:.2f},{price - 0.2:.2f},{price:.2f},{vol}"
            )
        return "\n".join(rows) + "\n"
    return "NO_DATA_AVAILABLE"


def _fake_losers_mom(*a, **k):
    # cur_price inside the $2-$20 momentum band
    return [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "cur_price": 15.0,
            "change_ratio": 0.05,
            "pe_ttm": 28.1,
            "market_cap": 3.2e12,
        },
        {
            "symbol": "MSFT",
            "name": "Microsoft Corp.",
            "cur_price": 14.0,
            "change_ratio": 0.04,
            "pe_ttm": 35.0,
            "market_cap": 7.0e12,
        },
    ]


def test_scan_momentum_passes_and_shows_pills(capsys):
    """--scan momentum keeps in-band names and shows Pills/Pull/RR columns."""
    with (
        mock.patch.object(vs, "route_to_vendor", side_effect=_momentum_route),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_top_movers_moomoo", side_effect=_fake_losers_mom
        ),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_hot_movers_moomoo", side_effect=_fake_losers_mom
        ),
    ):
        vs.main(
            [
                "--universe",
                "top-losers",
                "-n",
                "2",
                "-d",
                "2026-01-02",
                "--min-mcap",
                "1e9",
                "--scan",
                "momentum",
            ]
        )
    out = capsys.readouterr().out
    assert "Pills" in out and "Pull" in out and "RR" in out


def test_scan_momentum_filters_out_non_rvol(capsys):
    """Flat-volume names (RVOL~1) must be dropped by the momentum scan."""
    import pytest as _pytest

    with (
        mock.patch.object(vs, "route_to_vendor", side_effect=_momentum_flat_route),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_top_movers_moomoo",
            side_effect=_fake_losers_offline,
        ),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_hot_movers_moomoo",
            side_effect=_fake_losers_offline,
        ),
        _pytest.raises(SystemExit),
    ):
        vs.main(
            [
                "--universe",
                "top-losers",
                "-n",
                "2",
                "-d",
                "2026-01-02",
                "--min-mcap",
                "1e9",
                "--scan",
                "momentum",
            ]
        )


def _momentum_flat_route(method, *a, **k):
    if method == "get_stock_data":
        rows = ["Date,Open,High,Low,Close,Volume"]
        price = 15.0
        for i in range(60):
            rows.append(
                f"2026-01-{i % 28 + 1:02d},{price:.2f},{price + 0.2:.2f},{price - 0.2:.2f},{price:.2f},1000000"
            )
        return "\n".join(rows) + "\n"
    return "NO_DATA_AVAILABLE"


def test_scan_breakout_filters_non_matches(capsys):
    """--scan breakout must drop symbols that do not show a breakout setup."""
    import pytest as _pytest

    with (
        mock.patch.object(vs, "route_to_vendor", side_effect=_fixture_route),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_top_movers_moomoo",
            side_effect=_fake_losers_offline,
        ),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_hot_movers_moomoo",
            side_effect=_fake_losers_offline,
        ),
        _pytest.raises(SystemExit),
    ):
        vs.main(
            [
                "--universe",
                "top-losers",
                "-n",
                "2",
                "-d",
                "2026-01-02",
                "--min-mcap",
                "1e9",
                "--scan",
                "breakout",
            ]
        )


def _fake_losers_offline(sort_dir="losers", count=50, market="US", min_market_cap=0.0):
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
