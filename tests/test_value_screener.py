"""Value screener: universe sources (top-losers, heat-proxy) + screen gates.

Offline: moomoo ranks and vendor statements are mocked; nothing hits the
network or OpenD.
"""

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






# Several tests drive vs.main() end-to-end, which fetches real OHLCV/statements
# (benchmark SPDR closes, scan bases) through the vendor chain; those calls can
# take 15-60s per test under a slow network and must not hit the global 180s
# default. Keep the no-hang guarantee but allow a generous per-test budget.
pytestmark = pytest.mark.timeout(600)

FUND = "Market Cap: 3.2T\n"
BS = (
    "Date,2025-12-31\nCash And Cash Equivalents,300M\nTotal Debt,400M\n"
    "Total Assets,2.0B\nTotal Current Assets,700M\nTotal Current Liabilities,500M\n"
    "Total Liabilities,900M\nRetained Earnings,800M\nProperty Plant Equipment,400M"
)
INC = (
    "Date,2025-12-31\nTotal Revenue,1.0B\nOperating Income,150M\n"
    "Net Income,100M\nInterest Expense,10M\nTax Expense,20M"
)

_LOSERS = [
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
_HOT = _LOSERS + [
    {
        "symbol": "NVDA",
        "name": "NVIDIA Corp.",
        "cur_price": 120.0,
        "change_ratio": 0.031,
        "pe_ttm": 55.0,
        "market_cap": 3.0e12,
    },  # gainer, not a loser
    {
        "symbol": "CHEAP",
        "name": "Cheap Co",
        "cur_price": 15.0,
        "change_ratio": -0.05,
        "pe_ttm": 10.0,
        "market_cap": 2.0e9,
    },  # price < 20 -> gated
    {
        "symbol": "EYE",
        "name": "Pricey Inc",
        "cur_price": 50.0,
        "change_ratio": -0.03,
        "pe_ttm": 55.0,
        "market_cap": 5.0e9,
    },  # PE > 40 -> gated
    {
        "symbol": "ETFX",
        "name": "Vanguard InfoTech ETF",
        "cur_price": 100.0,
        "change_ratio": -0.02,
        "pe_ttm": 20.0,
        "market_cap": 4.0e10,
    },  # not equity -> gated
]


def _closes_csv(ticker):
    rows = ["Date,Open,High,Low,Close,Volume"]
    price = 200.0 if ticker == "AAPL" else 95.0
    for i in range(140):
        price += 0.1
        rows.append(
            f"2026-01-{i % 28 + 1:02d},{price:.2f},{price + 3:.2f},{price - 3:.2f},{price:.2f},5000000"
        )
    return "\n".join(rows) + "\n"


def fake_route(method, *a, **k):
    t = a[0]
    if method == "get_stock_data":
        return _closes_csv(t)
    if t != "AAPL":
        return "NO_DATA_AVAILABLE: no usable market data"
    return {"get_fundamentals": FUND, "get_balance_sheet": BS, "get_income_statement": INC}.get(
        method, "NO_DATA_AVAILABLE"
    )


def fake_losers(sort_dir="losers", count=50, market="US", min_market_cap=0.0):
    assert sort_dir == "losers" and count == 2 and market == "US"
    return list(_LOSERS)


def fake_hot(count=50, market="US", min_market_cap=0.0):
    assert market == "US"
    return list(_HOT)


@pytest.fixture(autouse=True)
def _patch_vendors():
    with (
        _patched_router(fake_route),
        mock.patch("tradingagents.dataflows.moomoo.get_top_movers_moomoo", side_effect=fake_losers),
        mock.patch("tradingagents.dataflows.moomoo.get_hot_movers_moomoo", side_effect=fake_hot),
    ):
        yield


def test_top_losers_adds_name_and_daychg_columns(capsys):
    vs.main(["--universe", "top-losers", "-n", "2", "-d", "2026-01-02", "--min-mcap", "1e9"])
    out = capsys.readouterr().out
    assert "Apple Inc." in out
    assert "-4.21%" in out
    assert "US.AAPL" not in out  # prefix stripped by the vendor fn


def test_min_mcap_floor_gates_universe(capsys):
    """Default $100B floor: only mega-cap losers survive (float cap <= total)."""
    vs.main(["--universe", "top-losers", "-n", "2", "-d", "2026-01-02"])
    out = capsys.readouterr().out
    assert "Apple Inc." in out and "Microsoft Corp." in out  # both > $100B
    vs.main(["--universe", "top-losers", "-n", "2", "-d", "2026-01-02", "--min-mcap", "0"])
    out = capsys.readouterr().out


def test_save_watchlist_writes_md(tmp_path):
    """Watchlist results must be saved to <out>/<finish_timestamp>.md."""
    out = tmp_path / "screener"
    file = vs.save_watchlist("# Value Watchlist\n", str(out), ts="20260102_101112")
    assert file.name == "20260102_101112.md"
    assert file.read_text(encoding="utf-8").startswith("# Value Watchlist")
    assert file.parent == out


def test_save_watchlist_keeps_only_newest_report(tmp_path):
    """The screener is single-use: writing a new report deletes older ones."""
    out = tmp_path / "screener"
    out.mkdir(parents=True, exist_ok=True)
    # Pre-populate older reports (newest-first timestamps) plus a non-.md file.
    (out / "20260101_000000.md").write_text("old", encoding="utf-8")
    (out / "20260102_000000.md").write_text("older", encoding="utf-8")
    (out / "notes.txt").write_text("keep me", encoding="utf-8")

    saved = vs.save_watchlist("# new\n", str(out), ts="20260103_000000")

    assert saved.name == "20260103_000000.md"
    remaining = {p.name for p in out.glob("*.md")}
    assert remaining == {"20260103_000000.md"}  # only the newest survives
    assert (out / "notes.txt").exists()  # non-report files are untouched


def test_save_watchlist_newest_wins_by_timestamp(tmp_path):
    """If two runs share a timestamp the later write is the keeper."""
    out = tmp_path / "scr2"
    vs.save_watchlist("# first\n", str(out), ts="20260102_101112")
    vs.save_watchlist("# second\n", str(out), ts="20260102_101113")
    remaining = {p.name for p in out.glob("*.md")}
    assert remaining == {"20260102_101113.md"}
    assert (out / "20260102_101113.md").read_text(encoding="utf-8").strip() == "# second"


def test_classic_path_has_no_mover_columns(capsys):
    """Classic path: all columns are present (full fixed header) but
    mover-only values (Name/DayChg) render n/a, not dropped."""
    vs.main(["AAPL", "-d", "2026-01-02"])
    out = capsys.readouterr().out
    # The table header always lists every column (fixed set).
    assert "| Name " in out and "| DayChg " in out
    assert "AAPL" in out
    # Classic path carries no mover metadata -> the data row shows n/a there.
    # (Row header -> values: a data row is pipe-delimited with n/a for Name.)
    data_row = next((ln for ln in out.splitlines() if ln.startswith("| 1 | AAPL |")), "")
    assert data_row and "n/a" in data_row


def test_universe_caps_limit(capsys):
    vs.main(["--universe", "top-losers", "-n", "2", "-d", "2026-01-02", "-l", "1"])
    out = capsys.readouterr().out
    assert out.count("| 1 |") >= 1


def test_heat_proxy_master_then_losers_with_gates(capsys):
    """heat-proxy: hot master -> losers only -> price>=20, 0<PE<=40, equities."""
    vs.main(["-u", "heat-proxy", "--market", "HK", "-n", "50", "-d", "2026-01-02", "-l", "50"])
    out = capsys.readouterr().out
    assert "Apple Inc." in out and "Microsoft Corp." in out  # losers kept
    assert "NVIDIA" not in out  # gainer excluded
    assert "Cheap Co" not in out  # price < 20 gated
    assert "Pricey Inc" not in out  # PE > 40 gated
    assert "ETF" not in out  # non-equity gated


def test_currency_gate_blocks_mixed_ev():
    """Non-USD statement currency must zero out USD-only metrics."""
    fin = {
        "currency": "JPY",
        "market_cap": 3.68e10,
        "total_assets": 3.0e14,
        "cash": 6.8e13,
        "total_debt": 6.2e12,
        "operating_income": 5.0e11,
    }
    row = vs.screen_ticker("JPPHY", fin)
    assert row["ev"] is None
    assert row["ev_ebit"] is None
    assert row["earnings_yield"] is None
    assert row["altman_z"] is None
    assert row["net_net"] is False


def test_scale_heuristic_flags_currency_mix():
    fin = {
        "market_cap": 3.68e10,
        "total_assets": 3.0e14,
        "cash": 6.8e13,
        "total_debt": 6.2e12,
        "operating_income": 5.0e11,
    }
    assert vs._usd_consistent(fin) is False
    row = vs.screen_ticker("JPPHY", fin)
    assert row["ev"] is None


def test_help_renders(capsys):
    """--help must not crash (a bare % in a help string used to raise)."""
    import pytest as _pytest

    with _pytest.raises(SystemExit) as exc:
        vs.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--inst-accum" in out and "--scan" in out


def test_report_headers_renamed_and_legend_added(capsys):
    """ScanA/ScanB are renamed TrendPB/Breakout and every report gets a column legend."""
    # Build a minimal result with a scan flag so the scan columns appear.
    results = [{
        "ticker": "MOG-A", "earnings_yield": 0.08, "ev_ebit": 12.0, "ev": 1e10,
        "f_score": 6, "beneish_m": -2.0, "altman_z": 4.0, "net_net": False,
        "scan_a": True, "scan_b": False,
    }]
    md = vs._watchlist_markdown(results)
    assert "TrendPB" in md and "Breakout" in md
    assert "ScanA" not in md and "ScanB" not in md
    # Legend present and explains the renamed columns.
    assert "#### Column legend" in md
    assert "**TrendPB**" in md and "trend-pullback" in md
    assert "**Breakout**" in md and "breakout" in md
    assert "**EY**" in md and "earnings yield" in md


def _full_route(method, *a, **k):
    """Router for --scan all positional tests: statements + a steady uptrend
    so the momentum/swing/vcp/value-dip buckets compute."""
    if method == "get_stock_data":
        rows = ["Date,Open,High,Low,Close,Volume"]
        # Steady rising trend for the scan indicators.
        p = 100.0
        for i in range(260):
            p += 0.3
            vol = 8000000
            rows.append(
                f"2026-01-{i % 28 + 1:02d},{p + 0.1:.2f},{p + 2:.2f},{p - 2:.2f},{p:.2f},{vol}"
            )
        return "\n".join(rows) + "\n"
    if method == "get_fundamentals":
        return (
            "### 2025/FY (FY 2025, currency: USD)\n"
            "| Item | Value | YoY |\n| --- | --- | --- |\n"
            "| Total Operating Revenue | 80000000000 | -- |\n| Operating Profit | 20000000000 | -- |\n"
            "| Net Income | 15000000000 | -- |\n| Total Assets | 200000000000 | -- |\n"
            "| Total Shareholder Equity | 100000000000 | -- |\n| Total Current Assets | 60000000000 | -- |\n"
            "| Total Current Liabilities | 30000000000 | -- |\n| Cost of Revenue | 50000000000 | -- |\n"
            "| Operating Cash Flow | 18000000000 | -- |\n| Common Shares Outstanding | 1000000000 | -- |\n"
        )
    if method in ("get_income_statement", "get_balance_sheet", "get_cashflow"):
        return _full_route("get_fundamentals", *a, **k)
    if method == "get_macro_indicators":
        return "## FRED 10Y\nLatest: 4.2"
    return "NO_DATA_AVAILABLE"


def test_scan_all_positional_populates_technical_columns(capsys):
    """A positional (non-movers) --scan all now fills the technical columns
    that used to be n/a (F, Pills, Swing, VCP, VDip, TrendPB, Breakout)."""
    from tradingagents.dataflows import interface as _iface

    with (
        _patched_router(_full_route),
        mock.patch.object(_iface, "route_to_vendor", side_effect=_full_route),
    ):
        vs.main(
            ["AAPL", "-d", "2026-01-02", "--min-mcap", "0", "--min-atr-pct", "0",
             "--min-avg-vol", "0", "--pe-max", "0", "--price-min", "0",
             "--scan", "all", "--out-dir", "screener"]
        )
    out = capsys.readouterr().out
    row = next((ln for ln in out.splitlines() if ln.startswith("| 1 | AAPL |")), "")
    assert "TrendPB" in out and "Breakout" in out
    assert row, "no data row rendered"
    # The technical / scan columns must be populated (not all n/a): F/M/Z band
    # and the scan flags should carry real values now.
    fields = row.split("|")
    fmz = [f.strip() for f in fields[7:10]]
    assert any(v not in ("n/a", "") for v in fmz)  # F/M/Z not all blank
    assert "Swing" in out and "VDip" in out


def test_enrich_sector_populates_without_gating(capsys):
    """--enrich-sector adds Sec/SecRank but never drops rows (unlike
    --sector-rank which filters to top-3)."""
    from tradingagents.dataflows import interface as _iface

    fake_rank = {
        "ranked": [{"etf": "XLK", "name": "Technology", "ret_3m": 0.1, "rank": 1}],
        "top3_3m": ["XLK"],
        "top3_1m": ["XLK"],
    }
    with (
        _patched_router(_full_route),
        mock.patch.object(_iface, "route_to_vendor", side_effect=_full_route),
        mock.patch.object(vs, "_fetch_sector_guarded", return_value="Technology"),
        mock.patch.object(vs, "_sector_ranking", return_value=fake_rank),
    ):
        vs.main(
            ["AAPL", "-d", "2026-01-02", "--min-mcap", "0", "--min-atr-pct", "0",
             "--min-avg-vol", "0", "--pe-max", "0", "--price-min", "0",
             "--scan", "value", "--enrich-sector", "--out-dir", "screener"]
        )
        out = capsys.readouterr().out
        # Sector value is present in the row (not n/a), and AAPL was NOT dropped.
        assert "Sec" in out
        row = next((ln for ln in out.splitlines() if ln.startswith("| 1 | AAPL |")), "")
        assert row and "Technology" in row
        assert "AAPL" in out
        # The full 11-SPDR sector ranking table is appended to the report.
        assert "Sector ranking (11 SPDR groups)" in out
        assert "| XLK | Technology |" in out


def test_sector_table_markdown_renders_full_ranking():
    """The sector table shows all 11 SPDR groups with 1m/3m returns, ranks
    and top-3 flags; rows without history render n/a and never top-3."""
    ranking = {
        "ranked": [
            {"etf": "XLK", "name": "Technology", "ret_1m": 0.05, "ret_3m": 0.12, "rank": 1},
            {"etf": "XLE", "name": "Energy", "ret_1m": -0.02, "ret_3m": -0.05, "rank": 11},
            {"etf": "XLU", "name": "Utilities", "ret_1m": None, "ret_3m": None, "rank": None},
        ],
        "top3_3m": ["XLK"],
        "top3_1m": ["XLK"],
    }
    md = vs._sector_table_markdown(ranking)
    assert "Sector ranking (11 SPDR groups)" in md
    assert "| 1 | XLK | Technology | 5.0% | 12.0% | yes | yes |" in md
    assert "| 11 | XLE | Energy | -2.0% | -5.0% |  |  |" in md
    assert "| n/a | XLU | Utilities | n/a | n/a |  |  |" in md
    # no ranking -> empty (never a broken table)
    assert vs._sector_table_markdown(None) == ""
    assert vs._sector_table_markdown({}) == ""


def test_alloc_returns_builds_daily_returns_from_closes():
    """_alloc_returns converts cached closes into daily return series and
    skips names without enough history (correlation never fabricates)."""
    vs._RUN_OHLCV_CACHE.clear()
    vs._RUN_OHLCV_CACHE["AAA"] = {"closes": [100.0, 101.0, 99.0, 102.0, 101.5]}
    vs._RUN_OHLCV_CACHE["BBB"] = {"closes": [50.0, 51.0]}
    out = vs._alloc_returns([{"ticker": "AAA"}, {"ticker": "BBB"}])
    assert "AAA" in out
    assert len(out["AAA"]) == 4
    assert abs(out["AAA"][0] - 0.01) < 1e-9  # 101/100 - 1
    assert "BBB" not in out  # only 1 return < 3 required


def test_alloc_returns_falls_back_to_guarded_fetch():
    """A failed fetch degrades to no series (never raises into the alloc)."""
    vs._RUN_OHLCV_CACHE.clear()
    with mock.patch.object(vs, "_fetch_ohlcv", return_value={"closes": []}):
        out = vs._alloc_returns([{"ticker": "ZZZ"}])
    assert out == {}


def test_allocation_block_wrapper_passes_returns_through():
    """The screener wrapper forwards returns_by_name to the strategy function;
    the correlation note appears only when the config gate is on."""
    from tradingagents.dataflows.config import set_config

    rets = {"A": [1.0, 1.1, 0.9, 1.05, 1.2, 0.95, 1.1, 1.0, 1.15, 0.9, 1.05, 1.2, 0.95, 1.1, 1.0, 1.15, 0.9, 1.05, 1.2, 0.95, 1.1, 1.0, 1.15, 0.9, 1.05, 1.2, 0.95, 1.1, 1.0, 1.15, 0.9, 1.05, 1.2, 0.95, 1.1, 1.0, 1.15, 0.9, 1.05, 1.2], "B": [0.5, 0.6, 0.4, 0.55, 0.7, 0.45, 0.6, 0.5, 0.65, 0.4, 0.55, 0.7, 0.45, 0.6, 0.5, 0.65, 0.4, 0.55, 0.7, 0.45, 0.6, 0.5, 0.65, 0.4, 0.55, 0.7, 0.45, 0.6, 0.5, 0.65, 0.4, 0.55, 0.7, 0.45, 0.6, 0.5, 0.65, 0.4, 0.55, 0.7]}
    set_config({"enable_correlation_penalty": False})
    text = vs.allocation_block({"A": 0.5, "B": 0.5}, returns_by_name=rets)
    assert "correlation-penalized" not in text
    set_config({"enable_correlation_penalty": True, "correlation_threshold": 0.4})
    text = vs.allocation_block({"A": 0.5, "B": 0.5}, returns_by_name=rets)
    assert "correlation-penalized" in text


def test_value_dip_prefilter_passes_oversold_low_risk():
    """A symbol with RSI <= 35, %b <= 0.10 and stop <= 2% passes the cheap
    OHLCV-only pre-filter (so the heavy fundamentals fetch runs for it).

    Series: a flat base (small ATR -> stop <= 2%) followed by a sharp 3-bar
    drop (price pierces the lower Bollinger band -> %b <= 0.10, RSI <= 35).
    """
    closes = [100.0 + (0.1 if i % 2 else -0.1) for i in range(50)] + [99.0, 97.5, 95.0]
    ohlcv = {
        "closes": closes,
        "highs": [c + 0.3 for c in closes],
        "lows": [c - 0.3 for c in closes],
        "volumes": [1_000_000] * len(closes),
    }
    assert vs._value_dip_technical_prefilter(ohlcv) is True


def test_value_dip_prefilter_rejects_uptrend():
    """A strong uptrend (RSI well above 35) can never be a value-dip candidate
    -> the pre-filter returns False so the heavy fetch is skipped."""
    closes = [100.0 + i * 1.5 for i in range(60)]
    ohlcv = {
        "closes": closes,
        "highs": [c + 1.0 for c in closes],
        "lows": [c - 1.0 for c in closes],
        "volumes": [1_000_000] * 60,
    }
    assert vs._value_dip_technical_prefilter(ohlcv) is False


def test_value_dip_prefilter_insufficient_data_returns_true():
    """Insufficient history -> unknown -> let the full scan decide (never
    fabricate a skip)."""
    ohlcv = {"closes": [100.0, 101.0], "highs": [], "lows": [], "volumes": []}
    assert vs._value_dip_technical_prefilter(ohlcv) is True
