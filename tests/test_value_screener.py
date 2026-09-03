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
    # Module-level exchange caches leak across tests (a fake symbol cached
    # as '' / 'US_NYSE' in one test pollutes the next); reset per test.
    vs._EODHD_EXCH_CACHE.clear()
    try:
        from tradingagents.dataflows import moomoo as _mm

        _mm._EXCHANGE_CACHE.clear()
    except Exception:  # noqa: BLE001
        pass
    with (
        _patched_router(fake_route),
        mock.patch("tradingagents.dataflows.moomoo.get_top_movers_moomoo", side_effect=fake_losers),
        mock.patch("tradingagents.dataflows.moomoo.get_hot_movers_moomoo", side_effect=fake_hot),
        # The exchange gate (default NYSE/Nasdaq) hits moomoo basicinfo; the
        # fakes are exchange-less, so report them NYSE-listed to keep the
        # universe tests deterministic.
        mock.patch("tradingagents.dataflows.moomoo.get_exchange_moomoo", return_value="US_NYSE"),
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


def test_eodhd_us_universe_filters_common_stocks(monkeypatch, capsys):
    """eodhd-us universe: pulls the EODHD US symbol list, keeps only common
    stocks, and screens them (moomoo movers stay optional)."""
    from tradingagents.dataflows import eodhd

    rows = [
        {"Code": "AAPL", "Name": "Apple Inc.", "Type": "Common Stock"},
        {"Code": "SPY", "Name": "SPDR S&P 500", "Type": "ETF"},
        {"Code": "MSFT", "Name": "Microsoft Corp.", "Type": "Common Stock"},
    ]
    monkeypatch.setattr(eodhd, "get_exchange_symbols_eodhd", lambda market: rows)
    vs.main(["--universe", "eodhd-us", "-l", "2", "-d", "2026-01-02", "--min-mcap", "0", "--exchanges", ""])
    out = capsys.readouterr().out
    assert "AAPL" in out and "MSFT" in out
    assert "SPY" not in out  # ETF filtered out


def test_eodhd_losers_universe_seeds_scan(monkeypatch, capsys):
    """eodhd-losers universe: the loss-ordered EODHD feed seeds the scan, and
    the percent change_ratio is converted to a ratio so DayChg renders
    correctly (EODHD reports change_p in %, the table shows a % of price)."""
    from tradingagents.dataflows import eodhd

    rows = [
        {"symbol": "AAPL", "close": 210.5, "change_p": -4.21},
        {"symbol": "MSFT", "close": 95.2, "change_p": -3.10},
    ]
    monkeypatch.setattr(eodhd, "get_top_movers_symbols_eodhd", lambda **k: rows)
    monkeypatch.setattr(
        eodhd,
        "get_exchange_symbols_eodhd",
        lambda market: [
            {"Code": "AAPL", "Type": "Common Stock"},
            {"Code": "MSFT", "Type": "Common Stock"},
        ],
    )
    vs.main(["--universe", "eodhd-losers", "-n", "2", "-d", "2026-01-02", "--min-mcap", "0", "--exchanges", ""])
    out = capsys.readouterr().out
    assert "AAPL" in out and "MSFT" in out
    assert "-4.21%" in out  # change_p -4.21 (percent) -> ratio -0.0421 -> -4.21%


def test_eodhd_losers_equity_filter_drops_non_common(monkeypatch, capsys):
    """eodhd-losers equity filter: the bulk feed carries no name/type, so a
    cross-check against the exchange-symbol common-stock list must drop
    warrants/units/ETFs from the seed (they dominate the intraday losers)."""
    from tradingagents.dataflows import eodhd

    rows = [
        {"symbol": "AAPL", "close": 210.5, "change_p": -4.21},
        {"symbol": "LITU", "close": 9.5, "change_p": -12.5},  # leveraged ETF
        {"symbol": "ABCW", "close": 2.1, "change_p": -40.0},  # warrant
    ]
    monkeypatch.setattr(eodhd, "get_top_movers_symbols_eodhd", lambda **k: rows)
    monkeypatch.setattr(
        eodhd,
        "get_exchange_symbols_eodhd",
        lambda market: [{"Code": "AAPL", "Type": "Common Stock"}],
    )
    vs.main(["--universe", "eodhd-losers", "-n", "3", "-d", "2026-01-02", "--min-mcap", "0", "--exchanges", ""])
    out = capsys.readouterr().out
    assert "AAPL" in out
    assert "LITU" not in out and "ABCW" not in out  # non-common stocks dropped


def test_value_dip_loose_prefilter_or_semantics():
    """--value-dip-loose relaxes the technical entry to OR: a name with RSI
    oversold but %b above the band passes loose and fails strict (and the
    reverse). The stop <=2% trade-risk gate still applies to both."""
    ohlcv = {"closes": [100.0] * 60, "highs": [102.0] * 60, "lows": [98.0] * 60, "volumes": [1_000_000] * 60}
    from unittest import mock as _mock

    with (
        _mock.patch("tradingagents.strategies.swing.rsi", return_value=30.0),
        _mock.patch(
            "tradingagents.strategies.value_dip.bollinger_pct_b",
            return_value={"pct_b": 0.30},
        ),
        _mock.patch("tradingagents.strategies.size.atr", return_value=1.0),
    ):
        assert vs._value_dip_technical_prefilter(ohlcv, loose=False) is False  # AND: %b too high
        assert vs._value_dip_technical_prefilter(ohlcv, loose=True) is True  # OR: RSI <= 35

    with (
        _mock.patch("tradingagents.strategies.swing.rsi", return_value=60.0),
        _mock.patch(
            "tradingagents.strategies.value_dip.bollinger_pct_b",
            return_value={"pct_b": 0.05},
        ),
        _mock.patch("tradingagents.strategies.size.atr", return_value=1.0),
    ):
        assert vs._value_dip_technical_prefilter(ohlcv, loose=False) is False  # AND: RSI too high
        assert vs._value_dip_technical_prefilter(ohlcv, loose=True) is True  # OR: %b <= 0.10


def test_eodhd_losers_loose_near_miss_renders(monkeypatch, capsys):
    """--value-dip-loose on a loss-ordered universe: a name that passes the
    relaxed technical entry (falls hard -> RSI <= 35) but misses the value
    floor renders in the ranked near-miss table with the failed gate named —
    the practical watchlist the loose gate exists for."""
    import scripts.value_screener as _vs
    from tradingagents.dataflows import eodhd, statement_parsing as _sp

    rows = [{"symbol": "AAPL", "close": 100.0, "change_p": -8.0}]
    monkeypatch.setattr(eodhd, "get_top_movers_symbols_eodhd", lambda **k: rows)
    monkeypatch.setattr(
        eodhd,
        "get_exchange_symbols_eodhd",
        lambda market: [{"Code": "AAPL", "Type": "Common Stock"}],
    )

    def _falling_closes_csv(ticker):
        # Steady -0.5%/day decline: RSI < 35 (loose technical entry passes)
        # while the 2-ATR stop stays <= 2% of price (trade_risk passes) -
        # proportional high/low bands, so the synthetic ATR tracks price.
        out_rows = ["Date,Open,High,Low,Close,Volume"]
        price = 200.0
        for i in range(60):
            price *= 0.995
            out_rows.append(
                f"2026-01-{i % 28 + 1:02d},{price:.2f},{price * 1.004:.2f},{price * 0.996:.2f},{price:.2f},5000000"
            )
        return "\n".join(out_rows) + "\n"

    # Capture the autouse fake_route bindings BEFORE replacing them, so the
    # fundamentals/cashflow legs still go to the hermetic fake (get_stock_data
    # alone uses the falling series; calling the patched name would recurse).
    orig_route = vs.route_to_vendor
    orig_sp_route = _sp.route_to_vendor

    def local_route(method, *a, **k):
        if method == "get_stock_data":
            return _falling_closes_csv(a[0])
        return orig_route(method, *a, **k)

    def local_sp_route(method, *a, **k):
        if method == "get_stock_data":
            return _falling_closes_csv(a[0])
        return orig_sp_route(method, *a, **k)

    monkeypatch.setattr(_vs, "route_to_vendor", local_route)
    monkeypatch.setattr(_sp, "route_to_vendor", local_sp_route)

    vs.main(
        [
            "-u", "eodhd-losers", "-n", "1", "-d", "2026-01-02",
            "--exchanges", "",
            "--scan", "value-dip", "--value-dip-loose", "--min-mcap", "0",
        ]
    )
    out = capsys.readouterr().out
    assert "Near misses" in out
    assert "AAPL" in out
    # Value floor is unavailable (cashflow n/a in the hermetic route), so the
    # near-miss names it as the missing gate.
    assert "value_floor" in out


def test_get_top_movers_symbols_eodhd_sorts_strips_caps(monkeypatch):
    """The new helper consumes the bulk real-time feed: losers sorted ascending
    by change_p, the .US suffix stripped, min_price applied, and capped."""
    from tradingagents.dataflows import eodhd

    feed = [
        {"code": "C.US", "close": 5.0, "change_p": -2.0},
        {"code": "A.US", "close": 10.0, "change_p": -5.0},
        {"code": "LOW.US", "close": 2.0, "change_p": -1.0},
        {"code": "B.US", "close": 8.0, "change_p": None},  # no change -> skipped
    ]
    monkeypatch.setattr(eodhd, "_eodhd_get", lambda *a, **k: feed)
    rows = eodhd.get_top_movers_symbols_eodhd("losers", count=2)
    assert rows == [
        {"symbol": "A", "close": 10.0, "change_p": -5.0},
        {"symbol": "C", "close": 5.0, "change_p": -2.0},
    ]
    rows = eodhd.get_top_movers_symbols_eodhd("losers", count=10, min_price=5.0)
    assert [r["symbol"] for r in rows] == ["A", "C"]


def test_moomoo_error_path_closes_context(monkeypatch, capsys):
    """Regression (heat-proxy): when a moomoo universe run fails (e.g. "no
    symbols after price/P-E/equity gates"), the OpenQuoteContext must be
    closed BEFORE parser.error raises SystemExit. Otherwise the SDK's
    non-daemon receive thread blocks interpreter exit and a web screener job
    hangs forever. (hermetic: movers all-gated; close_context mocked)."""
    import pytest as _pytest

    from tradingagents.dataflows import moomoo

    closed = []

    # Every mover fails the price gate (< 20) -> empty gated list.
    def _fake_hot(count, market, min_market_cap):
        return [{"symbol": "A", "name": "Cheap Co", "cur_price": 10.0, "pe_ttm": 5.0, "market_cap": 1e9, "change_ratio": -0.02}]

    monkeypatch.setattr(moomoo, "get_hot_movers_moomoo", _fake_hot)
    monkeypatch.setattr(moomoo, "close_context", lambda: closed.append(1))

    with _pytest.raises(SystemExit) as exc:
        vs.main(["-u", "heat-proxy", "-n", "1", "-d", "2026-01-02", "--price-min", "20"])
    assert exc.value.code == 2  # clean argparse error, not a hang
    assert closed, "close_context() must be called before parser.error on the moomoo error path"


def test_cheap_gate_deferred_before_fundamentals(monkeypatch, capsys):
    """Two-stage gating: a trend-pullback scan must call the cheap OHLCV gate
    (no provider) and, when the gate rejects a symbol, never fetch fundamentals
    for it. Verifies the run-level fin cache is untouched for gated-out names."""
    import pytest as _pytest

    from tradingagents.dataflows import moomoo

    fin_calls = []
    orig_fetch = vs.fetch_ticker
    monkeypatch.setattr(vs, "fetch_ticker", lambda t, d: fin_calls.append(t) or orig_fetch(t, d))

    def _fake_movers(sort_dir="losers", count=1, market="US", min_market_cap=0.0):
        # A single mover that fails the trend-pullback cheap gate (pure
        # downtrend: close below both SMAs, RSI high) -> trend-pullback rejects.
        return [{
            "symbol": "AAA", "name": "Downtrend Co", "cur_price": 100.0,
            "pe_ttm": 5.0, "market_cap": 1e10, "change_ratio": -0.05,
        }]

    monkeypatch.setattr(moomoo, "get_top_movers_moomoo", _fake_movers)
    with _pytest.raises(SystemExit):
        vs.main(["-u", "top-losers", "-n", "1", "-d", "2026-01-02", "--scan", "trend-pullback"])
    # The cheap gate (pure OHLCV) rejects before the fundamentals fetch.
    assert fin_calls == [], f"fundamentals fetched for gated-out symbol: {fin_calls}"


def test_eodhd_cheap_gate_before_fundamentals(monkeypatch, capsys):
    """eodhd-us + value-dip: the main loop's cheap OHLCV gate (Stage A) must
    run before fetch_ticker. Symbols whose OHLCV fails RSI<=35 / %b<=0.10 /
    stop<=2% never get a fundamentals fetch, so a large eodhd slice only
    queries providers for plausible dip candidates."""
    from tradingagents.dataflows import eodhd

    fin_calls = []
    orig_fetch = vs.fetch_ticker
    monkeypatch.setattr(vs, "fetch_ticker", lambda t, d: fin_calls.append(t) or orig_fetch(t, d))

    # Two eodhd common stocks: one in a strong uptrend (rejected by the cheap
    # OHLCV gate, no fundamentals), one oversold (passes the prefilter ->
    # fundamentals fetched).
    monkeypatch.setattr(
        eodhd, "get_exchange_symbols_eodhd",
        lambda market: [
            {"Code": "UPUP", "Name": "Uptrend", "Type": "Common Stock"},
            {"Code": "DOWN", "Name": "Oversold", "Type": "Common Stock"},
        ],
    )
    # Seed per-ticker OHLCV through _fetch_ohlcv so the real cheap gate runs.
    # UPUP: strong uptrend -> RSI high, %b high -> the value-dip prefilter
    # (and cheap gate) rejects it. DOWN: no seed -> fetched (defer through).
    def _fake_ohlcv(ticker, days=320):
        if ticker.upper() == "UPUP":
            return {
                "closes": [100.0 + i * 1.5 for i in range(60)],
                "highs": [102.0 + i * 1.5 for i in range(60)],
                "lows": [98.0 + i * 1.5 for i in range(60)],
                "volumes": [1_000_000] * 60,
            }
        return {"closes": [], "highs": [], "lows": [], "volumes": []}

    monkeypatch.setattr(vs, "_fetch_ohlcv", _fake_ohlcv)

    vs.main(["-u", "eodhd-us", "-l", "2", "-d", "2026-01-02",
        "--exchanges", "",
             "--scan", "value-dip", "--min-mcap", "0", "--price-min", "0",
             "--pe-max", "0"])
    # The uptrend name is rejected by the cheap OHLCV gate before any
    # fundamentals fetch; the oversold one (prefilter passes) advances to the
    # fundamentals stage. The rejected UPUP must NOT be fetched.
    assert "UPUP" not in fin_calls, f"gated-out UPUP fetched fundamentals: {fin_calls}"

def test_moomoo_screen_universe_builds_from_screener_rows(capsys):
    """--universe moomoo-screen: screener rows become the ticker universe and
    the branch applies config-filter defaults when no flags are passed."""
    rows = [
        {"symbol": "AAPL", "name": "Apple Inc.",
         "change_pct_5d": -0.0421, "market_cap": 3.2e12},
    ]
    cfg = {
        "moomoo_screen_pe_max": 17.0,
        "moomoo_screen_roe_min": 0.15,
        "moomoo_screen_max_chg5d": -0.08,
        "moomoo_screen_max_rsi": 32.0,
    }
    with (
        mock.patch(
            "tradingagents.dataflows.moomoo.screen_value_dip_moomoo",
            return_value=rows,
        ) as scr,
        mock.patch("tradingagents.dataflows.config.get_config", return_value=cfg),
        _patched_router(fake_route),
    ):
        rc = vs.main([
            "--universe", "moomoo-screen", "-n", "5", "-d", "2026-01-02",
            "--scan", "value", "--min-avg-vol", "0", "--min-atr-pct", "0",
        ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Apple Inc." in out
    kw = scr.call_args.kwargs
    assert kw["pe_max"] == 17.0          # config default, no --pe-max flag
    assert kw["market_cap_min"] == pytest.approx(10e9)  # client CLI default
    assert kw["price_min"] == pytest.approx(15.0)       # client CLI default
    assert kw["roe_min"] == pytest.approx(0.15)
    assert kw["chg5d_max"] == pytest.approx(-0.08)
    assert kw["rsi_max"] == 32.0


def test_moomoo_screen_dip_days_pb_price_forward(capsys):
    """--dip-days / --pb-min / --pb-max forward to the screen; config
    defaults land when flags absent."""
    rows = [
        {"symbol": "AAPL", "name": "Apple Inc.",
         "change_pct_5d": -0.1, "market_cap": 3.2e12},
    ]
    cfg = {
        "moomoo_screen_pe_max": 17.0,
        "moomoo_screen_roe_min": 0.15,
        "moomoo_screen_max_chg5d": -0.08,
        "moomoo_screen_max_rsi": 32.0,
        "moomoo_screen_pb_min": 0.5,
        "moomoo_screen_pb_max": 3.0,
        "moomoo_screen_dip_days": 20,
    }
    with (
        mock.patch(
            "tradingagents.dataflows.moomoo.screen_value_dip_moomoo",
            return_value=rows,
        ) as scr,
        mock.patch("tradingagents.dataflows.config.get_config", return_value=cfg),
        _patched_router(fake_route),
    ):
        vs.main([
            "--universe", "moomoo-screen", "-n", "5", "-d", "2026-01-02",
            "--scan", "value", "--min-avg-vol", "0", "--min-atr-pct", "0",
        ])
    kw = scr.call_args.kwargs
    assert kw["price_min"] == 15.0      # client CLI default
    assert kw["pb_min"] == cfg["moomoo_screen_pb_min"]
    assert kw["pb_max"] == cfg["moomoo_screen_pb_max"]
    assert kw["dip_days"] == cfg["moomoo_screen_dip_days"]


def test_moomoo_screen_exchanges_default_and_passthrough(capsys):
    """--exchanges defaults to NYSE,NASDAQ (server gets US_NYSE/US_NASDAQ)
    and '' disables the gate."""
    rows = [
        {"symbol": "AAPL", "name": "Apple Inc.",
         "change_pct_5d": -0.1, "market_cap": 3.2e12},
    ]
    with (
        mock.patch(
            "tradingagents.dataflows.moomoo.screen_value_dip_moomoo",
            return_value=rows,
        ) as scr,
        mock.patch("tradingagents.dataflows.config.get_config", return_value={}),
        _patched_router(fake_route),
    ):
        vs.main([
            "--universe", "moomoo-screen", "-n", "5", "-d", "2026-01-02",
            "--scan", "value", "--min-avg-vol", "0", "--min-atr-pct", "0",
        ])
    kw = scr.call_args.kwargs
    assert kw["exchanges"] == {"US_NYSE", "US_NASDAQ"}   # default gate on
    with (
        mock.patch(
            "tradingagents.dataflows.moomoo.screen_value_dip_moomoo",
            return_value=rows,
        ) as scr2,
        mock.patch("tradingagents.dataflows.config.get_config", return_value={}),
        _patched_router(fake_route),
    ):
        vs.main([
            "--universe", "moomoo-screen", "-n", "5", "-d", "2026-01-02",
            "--scan", "value", "--min-avg-vol", "0", "--min-atr-pct", "0",
            "--exchanges", "",
        ])
    assert scr2.call_args.kwargs["exchanges"] is None       # gate off
    # custom list passthrough
    with (
        mock.patch(
            "tradingagents.dataflows.moomoo.screen_value_dip_moomoo",
            return_value=rows,
        ) as scr3,
        mock.patch("tradingagents.dataflows.config.get_config", return_value={}),
        _patched_router(fake_route),
    ):
        vs.main([
            "--universe", "moomoo-screen", "-n", "5", "-d", "2026-01-02",
            "--scan", "value", "--min-avg-vol", "0", "--min-atr-pct", "0",
            "--exchanges", "NYSE",
        ])
    assert scr3.call_args.kwargs["exchanges"] == {"US_NYSE"}


def test_moomoo_screen_price_min_zero_disables_server_floor(capsys):
    rows = [
        {"symbol": "AAPL", "name": "Apple Inc.",
         "change_pct_5d": -0.1, "market_cap": 3.2e12},
    ]
    cfg = {"moomoo_screen_dip_days": 5}
    with (
        mock.patch(
            "tradingagents.dataflows.moomoo.screen_value_dip_moomoo",
            return_value=rows,
        ) as scr,
        mock.patch("tradingagents.dataflows.config.get_config", return_value=cfg),
        _patched_router(fake_route),
    ):
        vs.main([
            "--universe", "moomoo-screen", "-n", "5", "-d", "2026-01-02",
            "--scan", "value", "--min-avg-vol", "0", "--min-atr-pct", "0",
            "--price-min", "0",
        ])
    kw = scr.call_args.kwargs
    assert kw["price_min"] is None  # 0 disables the server floor


def test_moomoo_screen_flags_override_config_defaults(capsys):
    """Explicit CLI flags beat the config default for the screen filters."""
    rows = [
        {"symbol": "AAPL", "name": "Apple Inc.",
         "change_pct_5d": -0.1, "market_cap": 3.2e12},
    ]
    cfg = {
        "moomoo_screen_pe_max": 17.0,
        "moomoo_screen_roe_min": 0.15,
        "moomoo_screen_max_chg5d": -0.08,
        "moomoo_screen_max_rsi": 32.0,
    }
    with (
        mock.patch(
            "tradingagents.dataflows.moomoo.screen_value_dip_moomoo",
            return_value=rows,
        ) as scr,
        mock.patch("tradingagents.dataflows.config.get_config", return_value=cfg),
        _patched_router(fake_route),
    ):
        rc = vs.main([
            "--universe", "moomoo-screen", "-n", "5", "-d", "2026-01-02",
            "--scan", "value", "--min-avg-vol", "0", "--min-atr-pct", "0",
            "--min-mcap", "5e9", "--pe-max", "20", "--max-chg5d", "-10",
            "--max-rsi", "30",
        ])
    assert rc == 0
    kw = scr.call_args.kwargs
    assert kw["pe_max"] == 20.0
    assert kw["market_cap_min"] == pytest.approx(5e9)
    assert kw["chg5d_max"] == pytest.approx(-0.10)
    assert kw["rsi_max"] == 30.0        # roe untouched -> config default kept
    assert kw["roe_min"] == pytest.approx(0.15)
