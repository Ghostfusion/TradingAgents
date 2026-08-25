"""--scan strategies: trend-pullback (A) and breakout (B) signal tests."""

from contextlib import ExitStack, contextmanager
from unittest import mock

import pytest

import scripts.value_screener as vs
from tradingagents.dataflows import statement_parsing as _sp_parsing


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






# Tests drive vs.main() end-to-end (benchmark SPDR closes, OHLCV scan bases,
# sector/revision lookups) that fetch live vendor data and can take 15-60s per
# test under a slow network. Keep the no-hang guard but allow a generous budget.
pytestmark = pytest.mark.timeout(600)


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
        _patched_router(_fixture_route),
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
    """--scan all keeps everything and adds TrendPB/Breakout columns."""
    with _patched_router(_breakout_route):
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
    assert "TrendPB" in out and "Breakout" in out


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
        _patched_router(_momentum_route),
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
        _patched_router(_momentum_flat_route),
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
        _patched_router(_fixture_route),
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


def _swing_csv(flatten: bool = False):
    """Swing-candidate daily series (noisy uptrend + 6-bar fading-volume
    pullback into the 20-day EMA). With ``flatten`` the price is a flat line
    (no trend) so the swing gate must drop it."""
    import math

    rows = ["Date,Open,High,Low,Close,Volume"]
    if flatten:
        for i in range(240):
            rows.append(f"2026-01-{i % 28 + 1:02d},100.1,102.0,98.0,100.0,5000000")
        return "\n".join(rows) + "\n"
    n = 252
    base = [100.0 + 0.5 * i + 8.0 * math.sin(i / 6) for i in range(n)]
    k = 2.0 / 21.0
    ema = sum(base[:20]) / 20.0
    for v in base[20:]:
        ema = v * k + ema * (1 - k)
    closes = base + [ema + 5.0, ema + 4.0, ema + 3.0, ema + 2.0, ema + 1.0, ema + 1.6]
    vols = [5_000_000] * len(closes)
    vols = vols[:-6] + [1_000_000] * 6  # volume fades into the pullback
    for i, (c, v) in enumerate(zip(closes, vols, strict=False)):
        rows.append(f"2026-01-{i % 28 + 1:02d},{c + 0.1:.2f},{c + 2:.2f},{c - 2:.2f},{c:.2f},{v}")
    return "\n".join(rows) + "\n"


def _spy_csv():
    """Flat benchmark so the stock's RS line reads as an established uptrend."""
    rows = ["Date,Open,High,Low,Close,Volume"]
    for i in range(260):
        rows.append(f"2026-01-{i % 28 + 1:02d},200.1,202.0,199.0,200.0,50000000")
    return "\n".join(rows) + "\n"


def _swing_route(method, *a, **k):
    if method == "get_stock_data":
        sym = a[0] if a else "?"
        if sym == "SPY":
            return _spy_csv()
        # Every symbol gets the candidate setup at first, or a flat line to
        # exercise the gate depending on the flatten flag below.
        return _swing_csv(flatten=sym == "FLAT")
    return "NO_DATA_AVAILABLE: no usable market data"


def test_scan_swing_passes_and_shows_columns(capsys):
    """--scan swing keeps RS-backed swing setups and shows Swing/RS/Stp/T2."""
    with (
        _patched_router(_swing_route),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_top_movers_moomoo",
            side_effect=_fake_losers_offline,
        ),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_hot_movers_moomoo",
            side_effect=_fake_losers_offline,
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
                "--min-atr-pct",
                "0",
                "--scan",
                "swing",
            ]
        )
    out = capsys.readouterr().out
    assert "Swing" in out and "RS" in out and "Stp" in out and "T2" in out


def test_scan_swing_filters_non_matches(capsys):
    """--scan swing must drop names without a stacked/RS-backed setup."""
    import pytest as _pytest

    def flat_route(method, *a, **k):
        if method == "get_stock_data":
            sym = a[0] if a else "?"
            return _spy_csv() if sym == "SPY" else _swing_csv(flatten=True)
        return "NO_DATA_AVAILABLE"

    with (
        _patched_router(flat_route),
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
                "--min-atr-pct",
                "0",
                "--scan",
                "swing",
            ]
        )


def _vcp_csv(flat: bool = False):
    """A VCP base: rally then three shallower pullbacks (15% -> 8% -> 3%)
    on fading volume; with ``flat`` a flat line (no pullbacks) instead."""
    rows = ["Date,Open,High,Low,Close,Volume"]
    if flat:
        for i in range(120):
            rows.append(f"2026-01-{i % 28 + 1:02d},100.1,102.0,98.0,100.0,5000000")
        return "\n".join(rows) + "\n"
    closes = [100.0 + 1.25 * i for i in range(80)]
    closes += [200.0, 190.0, 180.0, 172.0, 170.0, 178.0, 186.0, 195.0]
    closes += [195.0, 192.0, 188.0, 184.0, 188.0, 192.0, 196.0]
    closes += [196.0, 195.5, 194.2, 194.0, 195.0, 196.0, 197.0, 197.5, 198.0]
    vols = [10_000_000] * 80 + [8_000_000] * 8 + [6_000_000] * 7 + [4_000_000] * 9
    for i, (c, v) in enumerate(zip(closes, vols, strict=False)):
        rows.append(f"2026-01-{i % 28 + 1:02d},{c + 0.1:.2f},{c + 2:.2f},{c - 2:.2f},{c:.2f},{v}")
    return "\n".join(rows) + "\n"


def _vcp_route(method, *a, **k):
    if method == "get_stock_data":
        sym = a[0] if a else "?"
        return _vcp_csv(flat=sym == "FLAT")
    return "NO_DATA_AVAILABLE"


def test_scan_vcp_passes_and_shows_columns(capsys):
    """--scan vcp keeps VCP bases and shows VCP/Brk columns."""
    with (
        _patched_router(_vcp_route),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_top_movers_moomoo",
            side_effect=_fake_losers_offline,
        ),
        mock.patch(
            "tradingagents.dataflows.moomoo.get_hot_movers_moomoo",
            side_effect=_fake_losers_offline,
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
                "--min-atr-pct",
                "0",
                "--scan",
                "vcp",
            ]
        )
    out = capsys.readouterr().out
    assert "VCP" in out and "Brk" in out


def test_scan_vcp_filters_non_matches(capsys):
    """--scan vcp must drop names without a contracting base."""
    import pytest as _pytest

    def flat_route(method, *a, **k):
        if method == "get_stock_data":
            return _vcp_csv(flat=True)
        return "NO_DATA_AVAILABLE"

    with (
        _patched_router(flat_route),
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
                "--min-atr-pct",
                "0",
                "--scan",
                "vcp",
            ]
        )
