"""Value watchlist screener - builds a master list of value candidates.

Usage
-----
    python scripts/value_screener.py AAPL MSFT GOOG -d 2026-06-30
    python scripts/value_screener.py --file universe.txt -d 2026-06-30 --limit 10

For each ticker the screener pulls the configured fundamental vendors
(``moomoo,yfinance`` by default, or whatever ``fundamental_data`` points at)
through ``route_to_vendor``, translates the vendor output into canonical line
items, computes the classic screens, and prints a ranked watchlist table.

Screens (from ``strategies/Math.md``):

* Magic Formula: Earnings Yield = EBIT / EV, Return on Capital (EBIT / invested
  capital) - rank on both.
* Acquirer's Multiple: EV / EBIT (lower is better).
* Piotroski Quality: F-Score >= 7 plus low P/B.
* Shareholder Yield: dividends + buybacks + net debt reduction / market cap.
* Net-Net: market cap < 2/3 * (current assets - total liabilities).
* Fraud / bankruptcy guards: Beneish M-Score, Altman Z-Score.

The screener never fabricates: a missing line item makes the corresponding
screen "n/a" rather than a guessed number.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.dataflows.interface import route_to_vendor  # noqa: E402

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("value_screener")

# Re-export the vendor-output -> canonical line-item parsing layer (moved to
# ``tradingagents.dataflows.statement_parsing`` so the *installed* CLI - whose
# wheel ships only ``tradingagents*`` and ``cli*`` - can import it without
# ``scripts/`` on sys.path). Names are re-exported here (not just used) so the
# screener CLI and tests importing ``scripts.value_screener`` keep working.
from tradingagents.dataflows.statement_parsing import (  # noqa: E402,F401
    _NON_EQUITY_TOKENS,
    _ROW_ALIASES,
    _canonicalize,
    _detect_currency,
    _first_number,
    _flat_canonical,
    _is_non_equity,
    _latest,
    _markdown_canonical,
    _markdown_period_tables,
    _match_row,
    _norm,
    _parse_csv_statements,
    _parse_json_statements,
    _parse_markdown_financials,
    _parse_markdown_periods,
    _parse_text_report,
    _percent_fraction,
    _period_year,
    _usd_consistent,
    fetch_ticker,
    screen_ticker,
)


def rank_watchlist(results: list) -> list:
    """Rank on earnings yield (desc), then EV/EBIT (asc); missing -> end."""

    def key(r):
        ey = r["earnings_yield"] if r["earnings_yield"] is not None else -1.0
        am = r["ev_ebit"] if r["ev_ebit"] is not None else float("inf")
        return (-ey, am)

    return sorted(results, key=key)


# Legend for every column that can appear in the watchlist report table.
# Header name -> one-line meaning. Emitted as a bullet list after the table in
# every screener report so the terse header abbreviations are self-explanatory.
_WATCHLIST_LEGEND = (
    ("Rank", "row position in the results (1 = best match)"),
    ("Ticker", "symbol screened"),
    ("Name", "company name (from the intraday movers rank)"),
    ("EY", "earnings yield = EBIT / enterprise value (higher = cheaper)"),
    ("EV/EBIT", "acquirer's multiple = EV / EBIT (lower = cheaper)"),
    ("EV", "enterprise value = market cap + total debt - cash"),
    ("F", "Piotroski F-Score (0-9 accounting quality; >=7 strong)"),
    ("M", "Beneish M-Score (earnings-manipulation likelihood > -1.78 elevated)"),
    ("Z", "Altman Z-Score (bankruptcy risk; < 1.8 distress zone)"),
    ("NetNet", "net-net flag: market cap < 2/3 x (current assets - total liabilities)"),
    ("Pills", "momentum 5-pillar score passed (0-5 day-trade prefilter)"),
    ("Pull", "momentum first-pullback candidate (yes/no)"),
    ("RR", "momentum reward/risk ratio"),
    ("L1Px", "live Alpaca L1 last price"),
    ("VWAP1m", "1-minute VWAP (Alpaca)"),
    ("1mVol", "1-minute volume (Alpaca)"),
    ("NEV/EBIT", "EV / 5-yr median-margin normalized EBIT (NEBIT)"),
    ("PE5Y", "5-year P/E percentile (0-1 position vs own history)"),
    ("TrendPB", "trend-pullback setup flag (Strategy A, yes/no)"),
    ("Breakout", "breakout setup flag (Strategy B, yes/no)"),
    ("EpsYoY", "diluted EPS year-over-year growth"),
    ("RevYoY", "revenue year-over-year growth"),
    ("ROE", "return on equity (net income / equity)"),
    ("Sec", "sector name"),
    ("SecRank", "sector rank within its 11-SPDR group (T# = top-3)"),
    ("RevUp", "net analyst revisions (up - down)"),
    ("Inst", "institutional accumulation: latest quarterly %-of-float change (pp; += accumulating)"),
    ("Swing", "swing setup candidate (yes/no)"),
    ("RS", "relative strength vs benchmark (verdict)"),
    ("Stp", "swing stop distance (% of price)"),
    ("T2", "swing target-2 distance (% of price)"),
    ("VCP", "volatility-contraction-pattern base flag (yes/no)"),
    ("Brk", "distance below the VCP base high (%, 0 = at breakout)"),
    ("VDip", "value-dip candidate flag (yes/no)"),
    ("FCFy", "free cash flow yield (FCF / market cap)"),
    ("RSI", "RSI-14"),
    ("%b", "Bollinger %b (price position inside the band)"),
    ("Stp%", "value-dip stop distance (% of price)"),
    ("Trap", "forensic trap-risk verdict (low / medium / high)"),
    ("Sent7", "7-day news-sentiment SMA (EODHD /sentiments, -1..1)"),
    ("SentZ", "latest news-sentiment innovation (score - 7d SMA)"),
    ("ILLIQ", "Amihud illiquidity (price impact per $ traded; higher = more illiquid)"),
    ("FltTurn", "float turnover = ADV / float shares (daily; <0.5% thin, >100% squeeze)"),
    ("IWF", "free-float factor = float / total shares (<0.5 = passive under-allocation)"),
    ("MFI", "Money Flow Index (volume-weighted RSI; <20 oversold, >80 overbought)"),
    ("StocK", "Stochastic %K (oscillator; <20 oversold) - dip-entry timing"),
    ("KST", "Know-Sure-Thing momentum oscillator (KST vs trigger; up = momentum confirm)"),
    ("Chandel", "Chandelier exit flag (close below highest-high - 3x ATR = trailing exit)"),
    ("Graham", "Graham Number = sqrt(22.5 x EPS x BVPS) cheapness floor"),
    ("NCAV", "net-net = (current assets - total liabilities) / shares (deep-value floor)"),
    ("EPV", "Earnings Power Value per share (normalized earnings floor)"),
    ("StochRSI", "StochRSI (0-1; <0.2 oversold) - smoothed RSI oversold"),
    ("RSI2", "2-period RSI (fast contrarian oversold read)"),
    ("W%R", "Williams %R (oscillator; < -80 oversold)"),
    ("Kelt", "Keltner Channel position (price % within EMA +/- 2x ATR)"),
    ("Donch", "Donchian upper channel (20-day high breakout level)"),
    ("OBV", "On-Balance-Volume up flag (bullish OBV divergence = dip-reversal confirm)"),
    ("PSAR", "Parabolic SAR (trailing stop level)"),
    ("Elder", "Elder thermometer (volume / 21-day avg volume)"),
    ("Aroon", "Aroon trend-age oscillator (up/down; >70 = strong trend)"),
    ("Fisher", "Fisher Transform (normalized reversal signal; extreme = turn)"),
    ("Supertrend", "ATR-based trailing line (up/down direction)"),
    ("POC", "Volume-profile point of control (price level with most volume)"),
    ("DayChg", "intraday change % (from the movers rank)"),
)


def _legend_markdown(only: set[str] | None = None) -> str:
    """Render the column legend as a markdown bullet list.

    ``only`` restricts the legend to the columns actually shown (the watchlist
    table prunes all-empty/all-"n/a"/all-"no" columns, so the legend has to
    match the table).
    """
    lines = ["\n#### Column legend", ""]
    for name, meaning in _WATCHLIST_LEGEND:
        if only is None or name in only:
            lines.append(f"- **{name}** - {meaning}")
    lines.append("")
    return "\n".join(lines)


_EMPTY_CELLS = {"", "n/a", "no", "none", "-", "—", "nan"}


def _empty_cell(v) -> bool:
    return str(v).strip().lower() in _EMPTY_CELLS


def prune_empty_columns(heads: list, rows: list[dict]) -> tuple:
    """Drop columns where EVERY row is empty / "n/a" / "no" / "-".

    ``Rank`` and ``Ticker`` are always kept; a column survives when any row
    carries real content (a number or an explicit marker). Returns
    ``(kept_heads, pruned_rows)``.
    """
    kept = [
        h for h in heads
        if h in ("Rank", "Ticker") or any(not _empty_cell(r.get(h)) for r in rows)
    ]
    return kept, [[r.get(h) for h in kept] for r in rows]


def _sector_table_markdown(ranking: dict | None) -> str:
    """Render the full 11-SPDR sector ranking as a markdown table.

    The framework rule (Strategies/framework.md) is that a candidate's sector
    must be a top performer over a rolling 1-month and 3-month window (top 3
    of the 11 SPDR groups). The watchlist only shows the *candidate's* rank
    (SecRank column); this table surfaces the whole ranking so the reader can
    see which sectors are leading and where the candidate's group stands.
    Rows with no usable history render n/a and sort last (never top-3).
    """
    if not ranking or not ranking.get("ranked"):
        return ""
    top3_3m = set(ranking.get("top3_3m") or [])
    top3_1m = set(ranking.get("top3_1m") or [])
    lines = [
        "\n#### Sector ranking (11 SPDR groups)",
        "",
        "| Rank | ETF | Sector | 1m ret | 3m ret | Top-3 3m | Top-3 1m |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in ranking.get("ranked", []):
        etf = r.get("etf", "")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(r.get("rank")) if r.get("rank") is not None else "n/a",
                    etf,
                    str(r.get("name", etf)),
                    f"{r['ret_1m']:.1%}" if r.get("ret_1m") is not None else "n/a",
                    f"{r['ret_3m']:.1%}" if r.get("ret_3m") is not None else "n/a",
                    "yes" if etf in top3_3m else "",
                    "yes" if etf in top3_1m else "",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append(
        "Top-3 3m = the sector groups the framework's top-3 rule requires; "
        "a candidate's SecRank column shows where its own group stands."
    )
    lines.append("")
    return "\n".join(lines)


def _watchlist_markdown(results: list) -> str:
    """Render the ranked watchlist as a complete table.

    Every screenable column is shown on every row (fixed order); a column the
    run did not compute is rendered ``n/a`` rather than dropped, so the set of
    columns is identical from one report to the next (the ``_WATCHLIST_LEGEND``
    always matches the table). ``Name`` / ``DayChg`` etc. show ``n/a`` when the
    run carried no such metadata.
    """

    def cell(v, fmt=None):
        if v is None:
            return "n/a"
        return fmt.format(v) if fmt else str(v)

    def flag(v):
        # None -> n/a (not computed); True/False -> yes/no.
        if v is None:
            return "n/a"
        return "yes" if v else "no"

    heads = [
        "Rank", "Ticker", "Name",
        "EY", "EV/EBIT", "EV", "F", "M", "Z", "NetNet",
        "Pills", "Pull", "RR",
        "L1Px", "VWAP1m", "1mVol",
        "NEV/EBIT", "PE5Y",
        "TrendPB", "Breakout",
        "EpsYoY", "RevYoY", "ROE",
        "Sec", "SecRank", "RevUp", "Inst",
        "Swing", "RS", "Stp", "T2",
        "VCP", "Brk",
        "VDip", "FCFy", "RSI", "%b", "Stp%",
        "Trap", "ILLIQ", "FltTurn", "IWF", "Graham", "NCAV", "EPV", "MFI", "StocK", "KST", "Chandel", "StochRSI", "RSI2", "W%R", "Kelt", "Donch", "OBV", "PSAR", "Elder", "Aroon", "Fisher", "Supertrend", "POC", "DayChg", "Sent7", "SentZ",
    ]
    seps = ["---"] * len(heads)
    header = f"# Value Watchlist ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    out = [
        header,
        "",
        "| " + " | ".join(heads) + " |",
        "| " + " | ".join(seps) + " |",
    ]
    rows: list[dict] = []
    for i, r in enumerate(results, 1):
        rank = r.get("sec_rank")
        sec_rank = (
            cell(rank) if rank is None else (f"T{rank}" if r.get("sec_top3") else str(rank))
        )
        cells = [
            str(i), r["ticker"], cell(r.get("name")),
            cell(r.get("earnings_yield"), "{:.2%}"),
            cell(r.get("ev_ebit")), cell(r.get("ev")),
            cell(r.get("f_score")), cell(r.get("beneish_m")), cell(r.get("altman_z")),
            flag(r.get("net_net")),
            cell(r.get("pills")), flag(r.get("pullback")), cell(r.get("mom_rr")),
            cell(r.get("line_price")), cell(r.get("line_vwap")), cell(r.get("line_vol")),
            cell(r.get("nebit_ev_ebit")), cell(r.get("pe_pct5"), "{:.0%}"),
            flag(r.get("scan_a")), flag(r.get("scan_b")),
            cell(r.get("eps_yoy"), "{:.1%}"),
            cell(r.get("revenue_yoy"), "{:.1%}"),
            cell(r.get("roe"), "{:.1%}"),
            cell(r.get("sector")), sec_rank,
            cell(r.get("rev_net"), "%+d"), cell(r.get("inst_latest_pp"), "%+.1f"),
            flag(r.get("scan_c")), cell(r.get("swing_rs") or "n/a"),
            cell(r.get("swing_stop_pct"), "{:.1%}"), cell(r.get("swing_t2_pct"), "{:.1%}"),
            flag(r.get("vcp_flag")), cell(r.get("vcp_brk"), "{:.1%}"),
            flag(r.get("vdip_flag")), cell(r.get("vdip_fcfy"), "{:.1%}"),
            cell(r.get("vdip_rsi"), "{:.0f}"), cell(r.get("vdip_pctb"), "{:.0%}"),
            cell(r.get("vdip_stop_pct"), "{:.1%}"),
            cell(r.get("trap")),
            cell(r.get("illiq"), "{:.2e}"),
            cell(r.get("float_turnover"), "{:.3%}"),
            cell(r.get("iwf"), "{:.2%}"),
            cell(r.get("graham")),
            cell(r.get("ncav")),
            cell(r.get("epv_ps")),
            cell(r.get("mfi"), "{:.0f}"),
            cell(r.get("stoch_k"), "{:.0f}"),
            cell(r.get("kst"), "{:.3f}"),
            "yes" if r.get("chandel_exit") else "no",
            cell(r.get("stochrsi"), "{:.2f}"),
            cell(r.get("rsi2"), "{:.0f}"),
            cell(r.get("wr"), "{:.0f}"),
            cell(r.get("kelt_pct"), "{:.2f}"),
            cell(r.get("donch_up")),
            cell(r.get("obv_up")),
            cell(r.get("psar")),
            cell(r.get("elder"), "{:.2f}"),
            cell(r.get("aroon_up"), "{:.0f}"),
            cell(r.get("fisher"), "{:.2f}"),
            cell(r.get("supertrend_dir")),
            cell(r.get("poc")),
            cell(r.get("day_change"), "{:+.2%}"),
            cell(r.get("sent7"), "{:+.2f}"),
            cell(r.get("sentz"), "{:+.2f}"),
        ]
        rows.append(dict(zip(heads, cells, strict=True)))
    if not rows:
        out.append(_legend_markdown())
        return "\n".join(out)
    kept, pruned = prune_empty_columns(heads, rows)
    out = [
        header,
        "",
        "| " + " | ".join(kept) + " |",
        "| " + " | ".join(["---"] * len(kept)) + " |",
    ]
    for row in pruned:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    out.append(_legend_markdown(set(kept)))
    return "\n".join(out)


def print_watchlist(results) -> None:
    """Print the ranked watchlist (legacy entry point for tests)."""
    print(_watchlist_markdown(results))


def save_watchlist(markdown, out_dir, ts=None):
    """Write the watchlist markdown to <out_dir>/<finish_timestamp>.md.

    The screener is a single-use daily tool, so only the newest report is
    kept: after writing, every *older* ``.md`` report in the folder is
    deleted. The folder keeps at most one report (the one just written). A
    non-``.md`` file is never touched.
    """
    from datetime import datetime as _dt

    from tradingagents.dataflows.utils import resolve_output_path

    out_dir = out_dir or "screener"
    out_path = resolve_output_path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    stamp = ts or _dt.now().strftime("%Y%m%d_%H%M%S")
    file = out_path / (stamp + ".md")
    file.write_text(markdown + "\n", encoding="utf-8")
    # Keep only the newest report (the one just written): delete older .md
    # reports so the folder never accumulates stale single-use outputs.
    try:
        newer = [
            p
            for p in out_path.glob("*.md")
            if p.is_file() and p.resolve() != file.resolve()
        ]
        for old in newer:
            old.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001 - cleanup must never abort a save
        logger.warning(
            "watchlist cleanup of older reports in %s failed (newest kept): %s",
            out_path,
            exc,
        )
    return file


def _sentiment_cols(ticker: str, curr_date: str) -> tuple[float | None, float | None]:
    """Sent7 (7-day news-sentiment SMA) + SentZ (latest innovation) per name.

    EODHD ``/sentiments`` via the news_sentiment chain; (None, None) when the
    feed has no coverage (renders ``n/a`` - never fabricated).
    """
    try:
        from datetime import timedelta

        from tradingagents.dataflows.eodhd import _sentiment_points_eodhd
        from tradingagents.strategies.sentiment import daily_sentiment_sma

        end = curr_date
        start = (datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=45)).strftime("%Y-%m-%d")
        points = _sentiment_points_eodhd(ticker, start, end)
        if not points:
            return None, None
        series = daily_sentiment_sma(points, window=7)
        if not series:
            return None, None
        latest = series[-1]
        return latest.get("sma_7d"), latest.get("innovation")
    except Exception:  # noqa: BLE001 - column degrades to n/a
        return None, None


def _fetch_ohlcv(ticker: str, days: int = 320) -> dict:
    """Daily OHLCV via the vendor chain (csv): closes/highs/lows/volumes."""
    # Optional Massive Flat-File bulk history (opt-in, OFF by default). When
    # TRADINGAGENTS_ENABLE_MASSIVE_FLAT=true and a day-aggregates CSV sits in
    # `massive_flat_dir` (config `massive_flat_dir`, default data/massive_flat),
    # read that ticker's series first so ATR/scan bases come from bulk history
    # instead of N per-ticker calls. Only used when it resolves >=15 rows.
    try:
        from tradingagents.dataflows.config import get_config
        from tradingagents.dataflows.massive_flat import ohlcv_for_ticker_dir

        cfg = get_config()
        if cfg.get("enable_massive_flat"):
            flat = ohlcv_for_ticker_dir(cfg.get("massive_flat_dir"), ticker)
            if flat and len(flat.get("closes") or []) >= 15:
                return flat
    except Exception:
        pass
    try:
        from datetime import datetime, timedelta

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        out = route_to_vendor("get_stock_data", ticker, start, end) or ""
        closes, opens, highs, lows, volumes = [], [], [], [], []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("date,"):
                continue
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                closes.append(float(parts[4]))
                opens.append(float(parts[1]))
                highs.append(float(parts[2]))
                lows.append(float(parts[3]))
                volumes.append(float(parts[5]))
            except ValueError:
                pass
        if closes:
            return {"closes": closes, "highs": highs, "lows": lows, "volumes": volumes}
    except Exception:
        pass
    try:
        from tradingagents.dataflows.alpaca import get_bars as _alpaca_bars
        from tradingagents.dataflows.config import get_config

        if get_config().get("enable_alpaca"):
            bars = _alpaca_bars(ticker, timeframe="1Day", limit=330)
            # Free IEX tier returns only the latest daily bar (historical daily
            # needs a paid tier); require enough depth for ATR/scan before use.
            if bars and len(bars) >= 15:
                return {
                    "closes": [float(b["c"]) for b in bars],
                    "highs": [float(b["h"]) for b in bars],
                    "lows": [float(b["l"]) for b in bars],
                    "volumes": [float(b["v"]) for b in bars],
                    "opens": [float(b["o"]) for b in bars],
                }
    except Exception:
        pass
    return {"closes": [], "opens": [], "highs": [], "lows": [], "volumes": []}


def _fetch_closes(ticker: str, days: int = 320) -> list:
    """Daily closes via the vendor chain (csv); empty on failure."""
    return _fetch_ohlcv(ticker, days=days)["closes"]


_BENCHMARK_CACHE: dict = {}


def _benchmark_closes() -> list:
    """Benchmark (SPY or TRADINGAGENTS_BENCHMARK_TICKER) closes for the RS
    line; cached per run so one fetch serves every symbol. Empty on failure
    (the swing scan then treats RS as unknown and never blocks on it)."""
    try:
        from tradingagents.dataflows.config import get_config

        bench = get_config().get("benchmark_ticker") or "SPY"
    except Exception:
        bench = "SPY"
    if bench not in _BENCHMARK_CACHE:
        _BENCHMARK_CACHE[bench] = _fetch_closes(bench)
    return _BENCHMARK_CACHE[bench]


# Shared run-wide caches so OHLCV / float are fetched at most once per symbol
# across the movers gating pass and the results loop (avoids double network).
_RUN_OHLCV_CACHE: dict = {}
_RUN_FLOAT_CACHE: dict = {}


def _compute_scan_row(
    symbol: str,
    ohlcv: dict,
    fin: dict,
    current_date: str = "",
    enable_float: bool = False,
    loose: bool = False,
) -> dict:
    """All scan intelligence for one symbol -> a flat dict of flags + metrics.

    Returns top-level ``a``/``b`` (TrendPB/Breakout), ``rsi``/``rvol``/``qret``
    and sub-dicts ``momentum``/``swing``/``vcp``/``value_dip`` so every scan
    column can be filled regardless of the active ``--scan`` mode. Each bucket
    is best-effort (a failure leaves that bucket absent -> the row shows n/a).
    """
    out: dict = {}
    try:
        sig = scan_signals(ohlcv) or {}
        for k in ("a", "b", "rsi", "rvol", "qret"):
            if k in sig:
                out[k] = sig[k]
    except Exception:  # noqa: BLE001
        pass
    # Momentum (day-trade pre-filter + first pullback).
    try:
        from tradingagents.strategies.momentum import (
            first_pullback as _fp,
            pillars as _pill,
            rvol as _rvol,
        )

        closes = ohlcv.get("closes") or []
        vols = ohlcv.get("volumes") or []
        opens = ohlcv.get("opens") or []
        rv = _rvol(vols) if vols else None
        fl = None
        if enable_float:
            from tradingagents.dataflows.float_shares import fetch_float_shares

            fl = _RUN_FLOAT_CACHE.get(symbol)
            if fl is None and fl != 0:
                fl = fetch_float_shares(symbol)
                _RUN_FLOAT_CACHE[symbol] = fl
        pill = _pill(
            close=closes[-1] if closes else None,
            day_volume=vols[-1] if vols else None,
            prev_close=closes[-2] if len(closes) >= 2 else None,
            day_open=opens[-1] if opens else None,
            rv=rv,
            float_shares=fl,
        )
        pull = _fp(
            closes, ohlcv.get("highs") or [], ohlcv.get("lows") or [], vols, opens=opens or None
        )
        out["momentum"] = {
            "pillars": {kk: bool(vv) for kk, vv in pill.items() if vv is not None},
            "pullback": bool(pull.get("candidate")),
            "mom_rr": pull.get("rr"),
        }
    except Exception:  # noqa: BLE001
        pass
    # Swing (techno-fundamental, uses the benchmark close series).
    try:
        sw = _swing_scan(symbol, ohlcv, _benchmark_closes())
        if sw is not None:
            out["swing"] = sw
    except Exception:  # noqa: BLE001
        pass
    # VCP base.
    try:
        vc = _vcp_scan(ohlcv)
        if vc is not None:
            out["vcp"] = vc
    except Exception:  # noqa: BLE001
        pass
    # Value-dip (needs the canonical financials).
    try:
        vd = _value_dip_scan(symbol, ohlcv, fin, current_date, loose)
        if vd is not None:
            out["value_dip"] = vd
    except Exception:  # noqa: BLE001
        pass
    return out


def _swing_scan(symbol: str, ohlcv: dict, benchmark: list) -> dict | None:
    """Composite swing read for one symbol + display metrics for the table."""
    try:
        from tradingagents.strategies.size import atr as _atr
        from tradingagents.strategies.swing import swing_report

        closes = ohlcv.get("closes") or []
        highs = ohlcv.get("highs") or []
        lows = ohlcv.get("lows") or []
        vols = ohlcv.get("volumes") or []
        if len(closes) < 200:
            return None
        atr_v = _atr(highs, lows, closes, window=14)
        rep = swing_report(closes, highs, lows, vols, atr_value=atr_v, benchmark_closes=benchmark)
        if not rep:
            return None
        out = dict(rep)
        t2 = (rep.get("targets") or {}).get("t2")
        last = closes[-1] if closes else None
        out["t2_pct"] = (float(t2) / last - 1.0) if (t2 and last) else None
        return out
    except Exception:  # noqa: BLE001 - a failed swing read must not abort a run
        return None


def _vcp_scan(ohlcv: dict) -> dict | None:
    """Volatility Contraction Pattern read for one symbol."""
    try:
        from tradingagents.strategies.swing import vcp_setup

        closes = ohlcv.get("closes") or []
        highs = ohlcv.get("highs") or []
        lows = ohlcv.get("lows") or []
        vols = ohlcv.get("volumes") or []
        if len(closes) < 90:
            return None
        return vcp_setup(closes, highs, lows, vols)
    except Exception:  # noqa: BLE001 - a failed vcp read must not abort a run
        return None


def _value_dip_technical_prefilter(ohlcv: dict, loose: bool = False) -> bool:
    """Cheap OHLCV-only pre-filter for the value-dip gating pass.

    The value-dip candidate requires ``technical_entry`` (RSI(14) <= 35 and
    %b <= 0.10; OR when ``loose``) AND ``trade_risk`` (stop distance <= 2% of
    price) — both computable from the OHLCV alone. Symbols failing these can
    never be candidates, so the heavy fundamentals fetch (statements +
    cashflow, ~6 moomoo calls) is skipped for them: the gating pass drops from
    ~7 vendor calls/symbol to 1. Returns True when the gates pass OR when the
    inputs are insufficient (unknown -> let the full scan decide, never
    fabricate).
    """
    try:
        from tradingagents.strategies.size import atr as _atr
        from tradingagents.strategies.swing import rsi as _rsi
        from tradingagents.strategies.value_dip import (
            MAX_ACCOUNT_RISK,
            PCTB_ENTRY,
            RSI_ENTRY,
            STOP_ATR_MULT,
            bollinger_pct_b,
        )

        closes = ohlcv.get("closes") or []
        highs = ohlcv.get("highs") or []
        lows = ohlcv.get("lows") or []
        if len(closes) < 20 or not highs or not lows:
            return True  # insufficient -> let the full scan decide
        price = float(closes[-1])
        rsi_val = _rsi(closes, 14)
        bb = bollinger_pct_b(closes)
        pct_b = bb.get("pct_b") if bb else None
        a = _atr(highs, lows, closes, window=14)
        stop_dist = STOP_ATR_MULT * a if a and a > 0 else None
        stop_pct = stop_dist / price if (stop_dist is not None and price > 0) else None
        if loose:
            technical_entry = bool(
                (rsi_val is not None and rsi_val <= RSI_ENTRY)
                or (pct_b is not None and pct_b <= PCTB_ENTRY)
            )
        else:
            technical_entry = bool(
                (rsi_val is not None and rsi_val <= RSI_ENTRY)
                and (pct_b is not None and pct_b <= PCTB_ENTRY)
            )
        trade_risk = bool(stop_pct is not None and stop_pct <= MAX_ACCOUNT_RISK)
        return technical_entry and trade_risk
    except Exception:  # noqa: BLE001 - prefilter degrades to "fetch heavy"
        return True


def _value_dip_scan(
    symbol: str, ohlcv: dict, fin: dict, current_date: str = "", loose: bool = False
) -> dict | None:
    """Value Dip + Swing hybrid setup read for one symbol.

    Runs the value-dip allocation matrix (value floor + technical entry +
    trade risk + exit target) against the symbol's OHLCV and its canonical
    financials (margin of safety, FCF yield, valuation Z). ``loose`` relaxes
    the technical entry to RSI<=35 OR %b<=0.10 (harvest mode). Returns None
    when there is insufficient price history or the strategy import fails.
    """
    try:
        from tradingagents.strategies.size import atr as _atr
        from tradingagents.strategies.value_dip import (
            fcf_yield as _fcfy,
            value_dip_setup as _setup,
        )

        closes = ohlcv.get("closes") or []
        highs = ohlcv.get("highs") or []
        lows = ohlcv.get("lows") or []
        vols = ohlcv.get("volumes") or []
        if len(closes) < 20:
            return None
        # Value inputs from the canonical financials (best-effort; a missing
        # value renders the row unknown rather than failing the gate).
        try:
            from tradingagents.agents.utils.value_dip_tools import (
                _fcf_series_from_cashflow as _fcf_series,
            )
            from tradingagents.dataflows.interface import route_to_vendor

            mc = _latest(fin.get("market_cap"))
            cf_key = (symbol.upper(), current_date)
            if cf_key not in _CASHFLOW_CACHE and current_date:
                _CASHFLOW_CACHE[cf_key] = route_to_vendor(
                    "get_cashflow", symbol, "annual", current_date
                )
            cf_payload = _CASHFLOW_CACHE.get(cf_key, "")
            fcf_series = _fcf_series(cf_payload) if cf_payload else None
            fy = _fcfy(fcf_series[0] if fcf_series else None, mc)  # newest period first
            fcf_raw = fcf_series[0] if fcf_series else None
            mos = None  # intrinsic unavailable here; value floor falls back to FCF yield
            # Step-1 balance-sheet / profitability inputs from the canonical
            # line items (a missing side renders the row unknown, never fails).
            d_e = None
            te = _latest(fin.get("total_equity"))
            td = _latest(fin.get("total_debt"))
            if td is not None and te:
                d_e = float(td) / float(te)
            cr = None
            ca_ = _latest(fin.get("current_assets"))
            cl_ = _latest(fin.get("current_liabilities"))
            if ca_ is not None and cl_:
                cr = float(ca_) / float(cl_)
            roe = None
            ne = _latest(fin.get("net_income"))
            if ne is not None and te:
                roe = float(ne) / float(te)
        except Exception:  # noqa: BLE001 - value inputs degrade
            fy = None
            mos = None
            fcf_raw = None
            d_e = cr = roe = None
        atr_v = _atr(highs, lows, closes, window=14)
        setup = _setup(
            closes,
            highs,
            lows,
            vols,
            margin_of_safety=mos,
            fcf_yield=fy,
            val_z=None,
            atr_value=atr_v,
            debt_to_equity=d_e,
            current_ratio=cr,
            roe=roe,
            fcf=fcf_raw,
            loose_technical=loose,
        )
        if not setup.get("rows"):
            return None
        rows = setup["rows"]
        te = rows.get("technical_entry") or {}
        tr = rows.get("trade_risk") or {}
        vf = rows.get("value_floor") or {}
        # Which measured gates failed — feeds the near-miss table under loose.
        gates = {
            name: (rows.get(name) or {}).get("pass")
            for name in ("value_floor", "technical_entry", "trade_risk", "balance_sheet", "profitability")
        }
        missing = [n for n, ok in gates.items() if ok is False]
        return {
            "candidate": bool(setup.get("candidate")),
            "fcf_yield": vf.get("fcf_yield"),
            "rsi": te.get("rsi"),
            "pct_b": te.get("pct_b"),
            "stop_pct": tr.get("stop_pct"),
            "gates": gates,
            "missing": missing,
            "reasons": setup.get("reasons") or [],
        }
    except Exception:  # noqa: BLE001 - a failed value-dip read must not abort a run
        return None


def _vd_near_miss_row(vd: dict, symbol: str) -> dict:
    """Compact near-miss row for a failed loose value-dip read.

    ``dist`` is a distance-to-entry proxy: how far each oversold signal sits
    from its threshold (0 when satisfied), used to rank the near-miss table.
    """
    rv = vd.get("rsi")
    pb = vd.get("pct_b")
    dist = 0.0
    if rv is not None and rv > 35.0:
        dist += rv - 35.0
    if pb is not None and pb > 0.10:
        dist += pb - 0.10
    return {
        "ticker": symbol,
        "rsi": rv,
        "pct_b": pb,
        "stop_pct": vd.get("stop_pct"),
        "fcf_yield": vd.get("fcf_yield"),
        "missing": vd.get("missing") or [],
        "dist": dist,
    }


def _cheap_gate(ohlcv: dict, scan: str, loose: bool = False) -> bool | None:
    """Two-stage gate, stage A: a PURE OHLCV-only pre-filter (no provider).

    ``loose`` relaxes the value-dip technical entry to OR (harvest mode).

    Returns:
      - False  -> definitively NOT a candidate -> drop before any fundamentals
                 fetch (saves the ~4-6 vendor calls per symbol).
      - True   -> keep (either genuinely passes, or the scan has no cheap
                 signal / the inputs are insufficient to decide -> defer to
                 the full scan, never fabricate a skip).
    Only the already-fetched cached OHLCV is used; no new vendor call happens
    here. Enrichment that needs a provider (float, sector, revisions,
    fundamentals) is deliberately deferred to stage B/C on survivors.
    """
    scan = (scan or "").strip().lower()
    # value / all have no cheap technical signal (value needs fundamentals;
    # 'all' flags everything) -> keep, defer.
    if scan in ("value", "all"):
        return True
    closes = (ohlcv or {}).get("closes") or []
    highs = (ohlcv or {}).get("highs") or []
    lows = (ohlcv or {}).get("lows") or []
    vols = (ohlcv or {}).get("volumes") or []
    # trend-pullback / breakout: reuse scan_signals' exact Strategy A/B flags.
    if scan in ("trend-pullback", "breakout"):
        sig = scan_signals(ohlcv)
        if sig is None:
            return True  # insufficient bars -> unknown -> keep
        return bool(sig.get("a")) if scan == "trend-pullback" else bool(sig.get("b"))
    # vcp: pure-OHLCV base detection.
    if scan == "vcp":
        vc = _vcp_scan(ohlcv)
        if vc is None:
            return True
        return bool(vc.get("candidate"))
    # value-dip: reuse the existing cheap technical prefilter (RSI/%b/stop).
    if scan == "value-dip":
        return _value_dip_technical_prefilter(ohlcv, loose)
    # swing: trend stack is pure OHLCV (RS uses the shared cached benchmark).
    if scan == "swing":
        try:
            from tradingagents.strategies.size import atr as _atr
            from tradingagents.strategies.swing import swing_report

            if len(closes) < 200:
                return True
            atr_v = _atr(highs, lows, closes, window=14)
            rep = swing_report(
                closes, highs, lows, vols,
                atr_value=atr_v, benchmark_closes=_benchmark_closes(),
            )
            if not rep:
                return True
            return bool(rep.get("candidate"))
        except Exception:  # noqa: BLE001 - defer on failure
            return True
    # momentum: 5-pillar pre-filter WITHOUT the float pillar (float fetch is
    # deferred to stage B/C, so the float pillar is 'unknown' here -> kept).
    if scan == "momentum":
        try:
            from tradingagents.strategies.momentum import pillars as _pill, rvol as _rvol

            rv = _rvol(vols) if vols else None
            pill = _pill(
                close=closes[-1] if closes else None,
                day_volume=vols[-1] if vols else None,
                prev_close=closes[-2] if len(closes) >= 2 else None,
                day_open=((ohlcv or {}).get("opens") or [None])[-1],
                rv=rv,
                float_shares=None,  # deferred -> unknown -> keep through A
            )
            # Drop when any *known* pillar fails; unknown (None) pillars keep
            # the name so momentum stays honest under deferred float.
            return not any(v is False for v in pill.values())
        except Exception:  # noqa: BLE001 - defer on failure
            return True
    return True  # unknown scan -> keep (defer)


# Run-level cache so stage B fetches each survivor's fundamentals ONCE even
# though the movers path and the main loop both call fetch_ticker / cashflow.
_FIN_CACHE: dict = {}
_CASHFLOW_CACHE: dict = {}


def _fetch_fin_cached(ticker: str, current_date: str) -> dict:
    """fetch_ticker memoized per (ticker, date) for the run."""
    key = (ticker.upper(), current_date)
    if key not in _FIN_CACHE:
        _FIN_CACHE[key] = fetch_ticker(ticker, current_date)
    return _FIN_CACHE[key]


_SECTOR_RANK_CACHE: dict = {}


def _sector_ranking() -> dict:
    """SPDR sector ranking (11 ETFs via the vendor chain, cached per run)."""
    if not _SECTOR_RANK_CACHE:
        from tradingagents.strategies.sector_rank import SPDR_SECTORS, rank_sectors

        closes_map = {}
        for etf in SPDR_SECTORS:
            closes = _fetch_closes(etf)
            if closes:
                closes_map[etf] = closes
        _SECTOR_RANK_CACHE["value"] = rank_sectors(closes_map)
    return _SECTOR_RANK_CACHE["value"]


def _fetch_sector_guarded(ticker: str) -> str | None:
    try:
        from tradingagents.dataflows.yfinance_sector import fetch_sector

        return fetch_sector(ticker)
    except Exception:  # noqa: BLE001 - enrichment must never abort a run
        return None


def _fetch_revision_guarded(ticker: str) -> dict | None:
    try:
        from tradingagents.dataflows.yfinance_sector import fetch_revision_actions

        return fetch_revision_actions(ticker)
    except Exception:  # noqa: BLE001
        return None


def _inst_accumulation(payload) -> dict | None:
    """Sum of the two most recent %-of-float period changes from the moomoo
    institutional-holdings table ("| period | inst | shares | pct | chg pp |");
    None when the payload carries no change cells."""
    if not payload or str(payload).startswith(("NO_DATA", "DATA_")):
        return None
    chgs = []
    for line in str(payload).splitlines():
        line = line.strip()
        if not line.startswith("|") or "pp" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 5 and cells[4].endswith("pp"):
            v = _first_number(cells[4])
            if v is not None:
                chgs.append(v)
    if not chgs:
        return None
    latest = chgs[0]
    two_q = latest + (chgs[1] if len(chgs) > 1 else 0.0)
    return {"latest_pp": latest, "two_q_pp": two_q, "accumulate": two_q > 0}


def _sma(series, n: int) -> float | None:
    if len(series) < n or n <= 0:
        return None
    return sum(series[-n:]) / n


def _ema(series, n: int) -> float | None:
    if len(series) < n or n <= 0:
        return None
    k = 2.0 / (n + 1)
    ema = sum(series[:n]) / n
    for v in series[n:]:
        ema = v * k + ema * (1 - k)
    return ema


def _rsi(closes, n: int = 14) -> float | None:
    if len(closes) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(1, n + 1):
        diff = closes[-i] - closes[-i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    if gains + losses == 0:
        return 50.0
    rs = gains / losses if losses > 0 else float("inf")
    return round(100.0 - 100.0 / (1.0 + rs), 2)


def _boll_squeeze(closes, n: int = 20) -> bool:
    """True when Bollinger width (20,2) is at its lowest in the last n bars."""
    if len(closes) < n * 2:
        return False
    widths = []
    for i in range(len(closes) - n, len(closes) + 1):
        window = closes[i - n : i]
        if len(window) < n:
            continue
        mid = sum(window) / n
        var = sum((v - mid) ** 2 for v in window) / n
        sd = var**0.5
        if mid > 0:
            widths.append(4 * sd / mid)
    return bool(widths) and widths[-1] == min(widths)


def scan_signals(ohlcv: dict) -> dict | None:
    """Strategy A (trend pullback) / B (breakout) flags + metrics from OHLCV."""
    closes = ohlcv.get("closes") or []
    highs = ohlcv.get("highs") or []
    lows = ohlcv.get("lows") or []
    volumes = ohlcv.get("volumes") or []
    if len(closes) < 200 or not highs or not lows or not volumes:
        return None
    close = closes[-1]
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)
    sma20 = _sma(closes, 20)
    ema20 = _ema(closes, 20)
    rsi = _rsi(closes, 14)
    hi52 = max(closes[-252:]) if len(closes) >= 252 else max(closes)
    hi52_dist = close / hi52 - 1.0 if hi52 else None
    qret = closes[-1] / closes[-64] - 1.0 if len(closes) >= 64 and closes[-64] else None
    avg20 = _sma(volumes, 20)
    rvol = volumes[-1] / avg20 if avg20 else None
    squeeze = _boll_squeeze(closes)

    strategy_a = bool(
        close > sma50
        and sma50 > sma200
        and lows[-1] <= ema20
        and close >= ema20
        and rsi is not None
        and 40.0 <= rsi <= 55.0
        and qret is not None
        and qret >= 0.10
    )
    strategy_b = bool(
        hi52_dist is not None
        and hi52_dist >= -0.10
        and close > sma20
        and close > sma50
        and ((rvol is not None and rvol > 1.5) or (rvol is not None and rvol < 0.75 and squeeze))
    )
    return {
        "a": strategy_a,
        "b": strategy_b,
        "rsi": rsi,
        "qret": qret,
        "rvol": rvol,
        "squeeze": squeeze,
        "hi52_dist": hi52_dist,
    }


def composite_scores(results: list, closes_map: dict) -> dict:
    """EY + momentum + 52w-distance factors -> composite score per ticker."""
    from tradingagents.strategies.factors import (
        composite_score,
        high_distance,
        momentum,
    )

    factors = {}
    for r in results:
        f = {}
        if r.get("earnings_yield") is not None:
            f["ey"] = r["earnings_yield"]
        closes = closes_map.get(r["ticker"]) or []
        if len(closes) >= 70:
            m = momentum(closes, lookback=60, skip=0)
            d = high_distance(closes, window=min(252, len(closes)))
            if m is not None:
                f["mom"] = m
            if d is not None:
                f["dist"] = d
        factors[r["ticker"]] = f
    return composite_score(factors)


def allocation_block(scores: dict, returns_by_name: dict | None = None) -> str:
    """Capped value-proportional allocation text (V3).

    ``returns_by_name`` (ticker -> daily return series) enables the opt-in
    correlation-aware penalty (config ``enable_correlation_penalty``) before
    the caps; names without a series are left unchanged.
    """
    from tradingagents.dataflows.config import get_config
    from tradingagents.strategies.portfolio import allocation_block as _ab

    return _ab(scores, cfg=get_config(), returns_by_name=returns_by_name)


def _alloc_returns(results: list) -> dict:
    """Daily return series per result ticker for the correlation-aware alloc.

    Reuses the run's OHLCV cache (scan modes already fetched the series) and
    falls back to a guarded fetch; names without >=3 aligned closes are left
    out (correlation never fabricates).
    """
    out: dict = {}
    for r in results:
        sym = (r.get("ticker") or "").upper()
        ohlcv = _RUN_OHLCV_CACHE.get(sym)
        if ohlcv is None:
            try:
                ohlcv = _fetch_ohlcv(sym)
                _RUN_OHLCV_CACHE[sym] = ohlcv
            except Exception:  # noqa: BLE001 - alloc degrades to uncorrelated
                ohlcv = None
        closes = (ohlcv or {}).get("closes") or []
        rets = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            if prev:
                rets.append(closes[i] / prev - 1.0)
        if len(rets) >= 3:
            out[sym] = rets
    return out


# Client-side exchange gate (default NYSE+Nasdaq, applied to every
# universe): moomoo's screen V2 EXCHANGE simple field is non-functional for
# US, so each candidate is checked via get_stock_basicinfo exchange_type
# (moomoo universes / tickers) or the EODHD symbol-list Exchange column
# (eodhd-us / eodhd-losers). Unknown exchange -> dropped (strict, default-on).
_EODHD_EXCH_CACHE: dict[str, str] = {}


def _parse_exchanges(raw: str) -> set[str]:
    """'NYSE,NASDAQ' -> {'NYSE','NASDAQ'}; '' / None -> empty (gate off)."""
    if not raw:
        return set()
    return {e.strip().upper() for e in str(raw).split(",") if e.strip()}


def _exchange_ok(symbol: str, allowed: set[str]) -> bool:
    """True when the symbol's exchange is in ``allowed`` (canonical short
    names). EODHD cache first (list-based, for eodhd universes), else the
    moomoo basicinfo lookup (cached per symbol). A failed lookup drops the
    symbol (strict) but never aborts the run.
    """
    ex = _EODHD_EXCH_CACHE.get(symbol)
    if ex is None:
        try:
            from tradingagents.dataflows.moomoo import get_exchange_moomoo

            raw = get_exchange_moomoo(symbol)
            ex = (raw or "").removeprefix("US_").upper() if raw else ""
        except Exception:  # noqa: BLE001 - lookup failure drops, never aborts
            ex = ""
    return (ex or "") in allowed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="*", help="ticker symbols")
    parser.add_argument("-f", "--file", help="file with one ticker per line")
    parser.add_argument(
        "-d",
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="current date (yyyy-mm-dd)",
    )
    parser.add_argument("-l", "--limit", type=int, default=50, help="max tickers to process")
    parser.add_argument(
        "-u",
        "--universe",
        choices=("tickers", "eodhd-us", "top-losers", "heat-proxy", "eodhd-losers", "moomoo-screen"),
        default="eodhd-us",
        help="symbol source: 'eodhd-us' (EODHD full US symbol list, default), "
        "'tickers' (positional/file), "
        "'top-losers' (moomoo intraday decliners; refreshes daily), "
        "'heat-proxy' (same as top-losers, US-only - the official "
        "trade-rank proxy for the proprietary in-app Heat List), "
        "or 'eodhd-losers' (EODHD bulk US real-time feed, one call; the "
        "biggest intraday decliners seed a loss-ordered scan for "
        "value-dip/momentum candidates - OpenD-independent, no moomoo quota)",
    )
    parser.add_argument(
        "--market", default="US", help="market key for --universe top-losers/heat-proxy (US/HK)"
    )
    parser.add_argument(
        "-n",
        "--movers-count",
        type=int,
        default=50,
        help="how many decliners to pull (moomoo movers max 200; "
        "eodhd-losers accepts up to ~18k)",
    )
    parser.add_argument(
        "--min-mcap",
        type=float,
        default=10e9,
        help="market-cap floor in USD (default $10B; 0 disables)",
    )
    parser.add_argument(
        "--price-min",
        type=float,
        default=15.0,
        help="min last price in USD (default 15; 0 disables)",
    )
    parser.add_argument(
        "--pe-max", type=float, default=40.0, help="max P/E (TTM) (default 40; 0 disables)"
    )
    parser.add_argument(
        "--max-chg5d", type=float, default=0.0,
        help="moomoo-screen: max 5-day change as %% (e.g. -5 = down 5%%+); "
        "0 disables (default 0)"
    )
    parser.add_argument(
        "--max-rsi", type=float, default=0.0,
        help="moomoo-screen: max RSI(14) (oversold upper bound; 0 disables)"
    )
    parser.add_argument(
        "--max-debt-assets", type=float, default=0.0,
        help="moomoo-screen: max debt-to-assets as %% (0 disables)"
    )
    parser.add_argument(
        "--dip-days", type=int, default=0,
        help="moomoo-screen: pullback window in days for the %% change filter "
        "(default 0 -> config moomoo_screen_dip_days, itself 5)"
    )
    parser.add_argument(
        "--pb-min", type=float, default=0.0,
        help="moomoo-screen: min price-to-book ratio (0 -> config default; 0.5 "
        "with --pb-max 3.0 mirrors the reference value-dip band)"
    )
    parser.add_argument(
        "--pb-max", type=float, default=0.0,
        help="moomoo-screen: max price-to-book ratio (0 disables)"
    )
    parser.add_argument(
        "--exchanges", type=str, default="NYSE,NASDAQ",
        help="comma list of listing exchanges to keep (all universes; "
        "default NYSE,NASDAQ; empty '' disables the gate)"
    )
    parser.add_argument(
        "--min-avg-vol",
        type=float,
        default=1_000_000,
        help="min 30-day average daily volume in shares (default 1M; 0 disables)",
    )
    parser.add_argument(
        "--min-atr-pct",
        type=float,
        default=2.0,
        help="min ATR(14) as %% of price (default 2; 0 disables)",
    )
    parser.add_argument(
        "--max-mcap",
        type=float,
        default=0.0,
        help="market-cap ceiling in USD (framework 2B-100B focus; 0 disables)",
    )
    parser.add_argument(
        "--min-eps-yoy",
        type=float,
        default=0.0,
        help="min EPS YoY change as %% (framework >= 20; 0 disables)",
    )
    parser.add_argument(
        "--min-rev-yoy",
        type=float,
        default=0.0,
        help="min revenue YoY change as %% (framework >= 15; 0 disables)",
    )
    parser.add_argument(
        "--min-roe",
        type=float,
        default=0.0,
        help="min return on equity as %% (framework >= 15; 0 disables)",
    )
    parser.add_argument(
        "--sector-rank",
        action="store_true",
        help="confirm the sector is a top-3 SPDR group (1m/3m momentum); "
        "adds Sec/Rank columns and keeps only top-3 sectors",
    )
    parser.add_argument(
        "--sentiment",
        action="store_true",
        help="add Sent7/SentZ columns: 7-day news-sentiment SMA and latest "
        "sentiment innovation (EODHD /sentiments; n/a without coverage)",
    )
    parser.add_argument(
        "--revision",
        action="store_true",
        help="require positive net analyst upgrades in the last 60d "
        "(yfinance proxy for forward earnings revisions); adds RevUp column",
    )
    parser.add_argument(
        "--inst-accum",
        action="store_true",
        help="require institutional accumulation (last two 13F periods "
        "%%-of-float change > 0, moomoo); adds Inst column",
    )
    parser.add_argument(
        "--intraday",
        action="store_true",
        help="append live Alpaca L1 price / 1m VWAP / volume columns",
    )
    parser.add_argument(
        "--enrich-sector",
        action="store_true",
        help="populate Sec/SecRank columns without gating (unlike --sector-rank)",
    )
    parser.add_argument(
        "--enrich-rev",
        action="store_true",
        help="populate RevUp (net analyst revisions) without gating (unlike --revision)",
    )
    parser.add_argument(
        "--enrich-inst",
        action="store_true",
        help="populate Inst (institutional accumulation) without gating (unlike --inst-accum)",
    )
    parser.add_argument(
        "--scan",
        choices=(
            "value",
            "trend-pullback",
            "breakout",
            "momentum",
            "swing",
            "vcp",
            "value-dip",
            "all",
        ),
        default="all",
        help="scan mode: 'value' (classic), 'trend-pullback' (20/50 EMA "
        "dip in uptrend), 'breakout' (volatility contraction/breakout), "
        "'momentum' (day-trade pre-filter + first pullback), 'swing' "
        "(techno-fundamental swing: stacked trend + RS vs benchmark + "
        "pullback + stops/targets), 'vcp' (volatility contraction pattern: "
        "successively shallower pullbacks on fading volume), 'value-dip' "
        "(Value Dip + Swing hybrid: value floor + RSI/%%b oversold entry + "
        "trade risk + exit target), or 'all' "
        "(default: keep all, flag strategies)",
    )
    parser.add_argument(
        "--value-dip-loose",
        action="store_true",
        help="value-dip: relax the technical entry to RSI<=35 OR %%b<=0.10 "
        "(vs AND) so the harvest catches names with only one oversold signal; "
        "also emits a ranked near-miss table (up to 50) showing which gate "
        "each near candidate missed. Strict AND by default.",
    )
    parser.add_argument(
        "--out-dir",
        default="screener",
        help="folder for the saved watchlist markdown (finish timestamp)",
    )
    parser.add_argument(
        "--rank",
        choices=("value", "composite"),
        default=None,
        help="ranking mode; default reads config enable_composite_rank",
    )
    parser.add_argument(
        "--enable-float",
        action="store_true",
        help="fetch public float (FMP/yfinance) for the momentum low-float pillar",
    )
    parser.add_argument(
        "--journal",
        default=None,
        metavar="PATH",
        help="append momentum candidate rows to a JSONL journal and print its stats",
    )
    parser.add_argument(
        "--alloc", action="store_true", help="append a capped allocation plan block"
    )
    args = parser.parse_args(argv)

    # The proprietary Heat List (search/news/trade telemetry) is app-only and
    # not exposed by any moomoo API; 'heat-proxy' is the sanctioned stand-in
    # (top-movers rank) so the daily losers-of-the-moment list keeps rotating.
    if args.universe == "heat-proxy":
        args.market = "US"

    # Exchange gate: allowed set from --exchanges ('' disables). Applied to
    # every universe - server list (moomoo-screen), EODHD list (eodhd-us /
    # eodhd-losers), or per-symbol basicinfo (tickers / top-losers /
    # heat-proxy).
    try:
        from tradingagents.dataflows.config import get_config as _gc

        _exch_cfg = (_gc().get("moomoo_screen_exchanges") or "NYSE,NASDAQ")
    except Exception:  # noqa: BLE001 - config absence degrades to default
        _exch_cfg = "NYSE,NASDAQ"
    allowed_exch = _parse_exchanges(
        args.exchanges
        if args.exchanges != parser.get_default("exchanges")
        else _exch_cfg
    )
    mover_meta: dict = {}
    float_cache: dict = {}
    scan_meta: dict = {}
    near_miss: list[dict] = []
    _RUN_OHLCV_CACHE.clear()
    _RUN_FLOAT_CACHE.clear()
    _BENCHMARK_CACHE.clear()
    _FIN_CACHE.clear()
    _CASHFLOW_CACHE.clear()
    tickers = list(args.tickers)
    # Positional tickers always win: the eodhd-us default only applies when no
    # explicit symbol source is given (no positional tickers, no --file).
    if tickers:
        args.universe = "tickers"
    if args.universe == "eodhd-us":
        # EODHD full US symbol list (51k symbols on the EOD plan) is the
        # default universe: it never hits the moomoo K-line quota and covers
        # the whole US market. Filter to common stocks, then apply the
        # price/mcap gates in the results loop. The moomoo movers universes
        # (top-losers / heat-proxy) remain available as the optional
        # intraday-momentum source.
        try:
            from tradingagents.dataflows.eodhd import get_exchange_symbols_eodhd

            symbols = get_exchange_symbols_eodhd("US")
            common = [
                s.get("Code")
                for s in symbols
                if s.get("Type") == "Common Stock" and s.get("Code")
            ]
            # EODHD codes are bare ("AAPL"); the rest of the pipeline expects
            # Yahoo-style tickers, which for US common stocks is the bare code.
            tickers = [c.upper() for c in common]
            # Exchange gate via the same symbol list (one cached call): keep
            # only NYSE/Nasdaq when the default --exchanges is active.
            if allowed_exch:
                _EODHD_EXCH_CACHE.update(
                    {str(s.get("Code")).upper(): str(s.get("Exchange") or "").upper()
                     for s in symbols if s.get("Code")}
                )
                before = len(tickers)
                tickers = [c for c in tickers if _exchange_ok(c, allowed_exch)]
                logger.info(
                    "exchange gate: eodhd-us %d -> %d (NYSE/Nasdaq)", before, len(tickers)
                )
            logger.info("eodhd-us universe: %d common stocks from EODHD", len(tickers))
            if len(tickers) > args.limit:
                print(
                    f"[screener] eodhd-us universe has {len(tickers)} symbols; "
                    f"--limit {args.limit} caps the scan to the first {args.limit} "
                    f"(pass a larger --limit to broaden the scan)."
                )
        except Exception as exc:  # noqa: BLE001 - a universe source must fail loudly
            parser.error(f"eodhd-us universe failed: {exc}")

    elif args.universe == "moomoo-screen":
        # Whole-market value-dip scan via moomoo Stock Screening V2
        # (get_stock_screen): server-side AND of value anchors + dip timing.
        # Rows are the API's own output - price/pe/roe/rsi/52w-distance are
        # already the screen's answer, so they feed mover_meta (name/day/mcap
        # used by the results loop for rank context) and the results loop
        # gates them like any other universe.
        try:
            from tradingagents.dataflows.moomoo import (
                MoomooNotConfiguredError,
                close_context,
                screen_value_dip_moomoo,
            )

            def _err(msg: str):
                with contextlib.suppress(Exception):
                    close_context()
                parser.error(msg)

            # Screen defaults come from config (env-overridable); explicit
            # CLI flags win over the config default when set.
            cfg = {}
            try:
                from tradingagents.dataflows.config import get_config

                cfg = get_config() or {}
            except Exception:  # noqa: BLE001 - config absence degrades to built-ins
                cfg = {}

            def _d(name):  # argparse default for a flag (explicit flag wins)
                return parser.get_default(name)

            pe_max = args.pe_max if args.pe_max != _d("pe_max") else cfg.get("moomoo_screen_pe_max")
            # Server floors mirror the CLIENT's gates exactly (client is
            # authoritative): --price-min / --min-mcap apply to both the
            # server request and the results loop; 0 disables both.
            mcap_min = args.min_mcap or None
            roe_min = (
                args.min_roe / 100.0
                if args.min_roe != _d("min_roe")
                else cfg.get("moomoo_screen_roe_min")
            )
            chg5d = (
                args.max_chg5d / 100.0
                if args.max_chg5d != _d("max_chg5d")
                else cfg.get("moomoo_screen_max_chg5d")
            )
            rsi = (
                args.max_rsi
                if args.max_rsi != _d("max_rsi")
                else cfg.get("moomoo_screen_max_rsi")
            )
            price_floor = args.price_min or None
            pb_min = args.pb_min if args.pb_min else cfg.get("moomoo_screen_pb_min")
            pb_max = args.pb_max if args.pb_max else cfg.get("moomoo_screen_pb_max")
            dip_days = args.dip_days or cfg.get("moomoo_screen_dip_days") or 5
            # -n caps the TOTAL symbols returned: page through the screen in
            # page_size chunks until we have (roughly) n symbols.
            n_want = args.movers_count or 100
            page_size = min(n_want, 200)
            n_pages = max(1, -(-n_want // page_size))
            screen_rows = screen_value_dip_moomoo(
                market=args.market,
                pe_min=0.0 if (pe_max or 0) > 0 else None,
                pe_max=pe_max or None,
                market_cap_min=mcap_min or None,
                roe_min=roe_min or None,
                net_margin_min=None,
                debt_assets_max=args.max_debt_assets / 100.0 if args.max_debt_assets else None,
                chg5d_max=chg5d or None,
                rsi_max=rsi or None,
                price_min=price_floor,
                pb_min=pb_min or None,
                pb_max=pb_max or None,
                dip_days=dip_days,
                exchanges=(
                    {"US_" + e for e in allowed_exch}
                    if allowed_exch else None
                ),
                price_to_52w_min=None,
                price_to_52w_max=None,
                page_count=page_size,
                max_pages=n_pages,
            )
            # Gate on _is_non_equity; real-time cap/PE from the screen are
            # authoritative, the results loop still applies its own gates.
            seen = set()
            for row in screen_rows:
                if _is_non_equity(row.get("name")):
                    continue
                symbol = (row.get("symbol") or "").upper()
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                mover_meta[symbol] = {
                    "name": row.get("name"),
                    "day_change": row.get("change_pct_5d"),
                    "market_cap": row.get("market_cap"),
                }
                tickers.append(symbol)
            logger.info(
                "moomoo-screen universe: %d value-dip symbols from moomoo "
                "screener V2", len(tickers))
        except MoomooNotConfiguredError as exc:
            _err(f"moomoo screen unavailable: {exc}")

    elif args.universe in ("top-losers", "heat-proxy"):
        try:
            from tradingagents.dataflows.moomoo import (
                MoomooNotConfiguredError,
                close_context,
                get_hot_movers_moomoo,
                get_top_movers_moomoo,
            )

            # parser.error raises SystemExit; the moomoo OpenQuoteContext spawns
            # a non-daemon receive thread that would otherwise block interpreter
            # exit (the process hangs after the error). Tear the context down
            # first so the error path exits cleanly (matches the main() teardown).
            def _err(msg: str):
                with contextlib.suppress(Exception):
                    close_context()
                parser.error(msg)

            if args.universe == "heat-proxy":
                # Heat-list stand-in: the official hot master (gainers+losers,
                # hottest first), then keep the losers of the moment.
                movers = get_hot_movers_moomoo(
                    count=args.movers_count,
                    market=args.market,
                    min_market_cap=args.min_mcap,
                )
                losers = [
                    m for m in movers if m.get("change_ratio") is not None and m["change_ratio"] < 0
                ]
                movers = losers
            else:
                movers = get_top_movers_moomoo(
                    sort_dir="losers",
                    count=args.movers_count,
                    market=args.market,
                    min_market_cap=args.min_mcap,
                )
            # Equity-only, price, P/E (TTM), market-cap, 30d volume, ATR gates.
            need_ohlcv = bool(args.min_avg_vol or args.min_atr_pct or args.scan != "value")
            gated = []
            for m in movers[: args.movers_count * 4]:
                if _is_non_equity(m.get("name")):
                    continue
                price = m.get("cur_price")
                pe = m.get("pe_ttm")
                cap = m.get("market_cap")
                if args.price_min and (price is None or price < args.price_min):
                    continue
                if args.pe_max and (pe is None or not (0.0 < pe <= args.pe_max)):
                    continue
                if args.min_mcap and (cap is None or cap < args.min_mcap):
                    continue
                if need_ohlcv:
                    symbol = (m.get("symbol") or "").upper()
                    ohlcv = _RUN_OHLCV_CACHE.get(symbol)
                    if ohlcv is None:
                        ohlcv = _fetch_ohlcv(symbol)
                        _RUN_OHLCV_CACHE[symbol] = ohlcv
                    if args.scan != "value":
                        sig = scan_signals(ohlcv) or {}
                        scan_meta[symbol] = sig
                        if args.scan in ("trend-pullback", "breakout"):
                            if args.scan == "trend-pullback" and not sig.get("a"):
                                continue
                            if args.scan == "breakout" and not sig.get("b"):
                                continue
                        if args.scan == "momentum":
                            try:
                                from tradingagents.strategies.momentum import (
                                    first_pullback as _fp,
                                    pillars as _pill,
                                    rvol as _rvol,
                                    session_flags as _sess,
                                )

                                closes = ohlcv["closes"]
                                vols = ohlcv["volumes"]
                                opens = ohlcv.get("opens") or []
                                rv = _rvol(vols) if vols else None
                                fl = float_cache.get(symbol)
                                if args.enable_float and fl is None:
                                    try:
                                        from tradingagents.dataflows.float_shares import (
                                            fetch_float_shares,
                                        )

                                        fl = fetch_float_shares(symbol)
                                        float_cache[symbol] = fl
                                    except Exception:
                                        fl = None
                                pill = _pill(
                                    close=price,
                                    day_volume=vols[-1] if vols else None,
                                    prev_close=closes[-2] if len(closes) >= 2 else None,
                                    day_open=opens[-1] if opens else None,
                                    rv=rv,
                                    float_shares=fl,
                                )
                                pull = _fp(
                                    closes, ohlcv["highs"], ohlcv["lows"], vols, opens=opens or None
                                )
                                session = _sess(peak_pnl=None, current_pnl=None)
                                scan_meta[symbol]["momentum"] = {
                                    "pillars": {
                                        kk: bool(vv) for kk, vv in pill.items() if vv is not None
                                    },
                                    "pullback": bool(pull.get("candidate")),
                                    "mom_rr": pull.get("rr"),
                                }
                                # 5-pillar pre-filter: skip when any *known*
                                # pillar fails; unknown pillars (no data)
                                # keep the symbol so scans stay honest.
                                if any(v is False for v in pill.values()):
                                    continue
                                if args.journal and pull.get("candidate"):
                                    from tradingagents.strategies.journal import (
                                        record_momentum_trade,
                                    )

                                    record_momentum_trade(
                                        args.journal,
                                        symbol,
                                        date=args.date,
                                        pillars=pill,
                                        pullback=pull,
                                        session=session,
                                        price=price,
                                        note="screener momentum candidate",
                                    )
                            except Exception:
                                pass
                    if args.scan == "swing":
                        bench = _benchmark_closes()
                        sw = _swing_scan(symbol, ohlcv, bench)
                        if sw is not None:
                            scan_meta[symbol]["swing"] = sw
                        if not (sw and sw.get("candidate")):
                            continue
                    if args.scan == "vcp":
                        vc = _vcp_scan(ohlcv)
                        if vc is not None:
                            scan_meta[symbol]["vcp"] = vc
                        if not (vc and vc.get("candidate")):
                            continue
                    if args.scan == "value-dip":
                        # Cheap OHLCV-only pre-filter: symbols failing the
                        # technical entry + trade-risk gates can never be
                        # value-dip candidates, so skip the heavy fundamentals
                        # fetch (statements + cashflow, ~6 moomoo calls) for
                        # them. This drops the gating pass from ~7 vendor
                        # calls/symbol to 1 for the non-candidates.
                        if not _value_dip_technical_prefilter(ohlcv, loose=args.value_dip_loose):
                            continue
                        fin = _fetch_fin_cached(symbol, args.date)
                        vd = _value_dip_scan(symbol, ohlcv, fin, args.date, loose=args.value_dip_loose)
                        if vd is not None:
                            scan_meta[symbol]["value_dip"] = vd
                        if not (vd and vd.get("candidate")):
                            # Only real evaluations (the matrix produced
                            # gates) belong in the near-miss table; a no-data
                            # read renders n/a, never a fabricated "miss".
                            if args.value_dip_loose and vd and "gates" in vd:
                                near_miss.append(_vd_near_miss_row(vd, symbol))
                            continue
                    if args.min_avg_vol:
                        vols = ohlcv["volumes"][-30:]
                        avg_vol = sum(vols) / len(vols) if vols else 0.0
                        if avg_vol < args.min_avg_vol:
                            continue
                    if args.min_atr_pct:
                        closes = ohlcv["closes"]
                        if len(closes) < 15 or not ohlcv["highs"] or not ohlcv["lows"]:
                            continue
                        from tradingagents.strategies.size import atr as _atr

                        a = _atr(ohlcv["highs"], ohlcv["lows"], closes, window=14)
                        last = closes[-1]
                        if last <= 0 or (a / last * 100.0) < args.min_atr_pct:
                            continue
                gated.append(m)
            movers = gated[: args.movers_count]
            if not movers:
                _err("no symbols after price/P-E/equity gates")
            for m in movers:
                symbol = (m.get("symbol") or "").upper()
                if not symbol:
                    continue
                tickers.append(symbol)
                if m.get("name") or m.get("change_ratio") is not None:
                    mover_meta[symbol] = {
                        "name": m.get("name"),
                        "day_change": m.get("change_ratio"),
                        "market_cap": m.get("market_cap"),
                    }
            logger.info("top-losers universe: %d symbols from moomoo", len(tickers))
        except MoomooNotConfiguredError as exc:
            _err(f"moomoo top-losers unavailable: {exc}")
    elif args.universe == "eodhd-losers":
        # EODHD bulk US real-time feed (one call, ~18k rows, OpenD-independent):
        # the biggest intraday decliners seed a loss-ordered scan so
        # value-dip/momentum candidates (RSI/%b oversold, stop<=2%) are
        # harvested from the movers list instead of an alphabetical eodhd-us
        # slice. Rows carry close + change only (no name/mcap/PE on the bulk
        # feed), so the price gate applies here; the mcap/PE gates run later
        # in the results loop. Same Stage A/B/C two-stage gating afterwards.
        try:
            from tradingagents.dataflows.eodhd import (
                NoMarketDataError,
                VendorRateLimitError,
                get_exchange_symbols_eodhd,
                get_top_movers_symbols_eodhd,
            )

            movers = get_top_movers_symbols_eodhd(
                direction="losers",
                count=args.movers_count,
                min_price=args.price_min,
            )
            gated = [m for m in movers if m.get("symbol")]
            if not gated:
                parser.error("no symbols after eodhd-losers feed gate")
            # Equity filter: the bulk feed carries no name/type, so warrants,
            # units and ETFs dominate the biggest-decliner list. Cross-check
            # against the EODHD exchange-symbol common-stock set (one cached
            # call) and keep only genuine common stocks; degrade to the
            # unfiltered list if the reference call fails (never abort).
            try:
                eodhd_symbols = get_exchange_symbols_eodhd("US")
                common_set = {
                    str(s.get("Code")).upper()
                    for s in eodhd_symbols
                    if s.get("Type") == "Common Stock" and s.get("Code")
                }
                if allowed_exch:
                    _EODHD_EXCH_CACHE.update(
                        {str(s.get("Code")).upper(): str(s.get("Exchange") or "").upper()
                         for s in eodhd_symbols if s.get("Code")}
                    )
            except Exception:  # noqa: BLE001 - reference unavailability degrades
                common_set = set()
            if common_set:
                before = len(gated)
                gated = [m for m in gated if m["symbol"] in common_set]
                logger.info(
                    "eodhd-losers equity filter: %d -> %d (common stocks)",
                    before,
                    len(gated),
                )
            if not gated:
                parser.error("no common stocks after eodhd-losers equity filter")
            if allowed_exch:
                before = len(gated)
                gated = [m for m in gated if _exchange_ok(m["symbol"], allowed_exch)]
                logger.info(
                    "exchange gate: eodhd-losers %d -> %d (NYSE/Nasdaq)",
                    before, len(gated),
                )
            if not gated:
                parser.error("no NYSE/Nasdaq symbols after exchange gate")
            for m in gated:
                tickers.append(m["symbol"])
                if m.get("change_p") is not None:
                    # change_p is percent; DayChg renders as a ratio.
                    mover_meta[m["symbol"]] = {"day_change": m["change_p"] / 100.0}
            logger.info(
                "eodhd-losers universe: %d common stocks from EODHD real-time feed",
                len(tickers),
            )
        except (NoMarketDataError, VendorRateLimitError) as exc:
            parser.error(f"eodhd-losers universe unavailable: {exc}")
        except Exception as exc:  # noqa: BLE001 - a universe source must fail loudly
            parser.error(f"eodhd-losers universe failed: {exc}")
    elif args.file:
        with open(args.file, encoding="utf-8") as fh:
            tickers += [ln.strip().upper() for ln in fh if ln.strip()]
    if not tickers:
        parser.error(
            "no tickers provided (positional args, --file, or --universe "
            "eodhd-us/top-losers/eodhd-losers)"
        )

    results = []
    fmp_use = False
    try:
        from tradingagents.dataflows.config import get_config

        fmp_use = bool(get_config().get("fmp_api_key"))
    except Exception:
        fmp_use = False
    for ticker in tickers[: args.limit]:
        try:
            # Exchange gate for the per-symbol universes (tickers /
            # top-losers / heat-proxy); eodhd-us / eodhd-losers are already
            # list-filtered above, moomoo-screen inside the screen fn.
            if (
                allowed_exch
                and args.universe not in ("eodhd-us", "eodhd-losers")
                and not _exchange_ok(ticker.upper(), allowed_exch)
            ):
                logger.info("exchange gate: drop %s", ticker)
                continue
            meta = mover_meta.get(ticker.upper(), {})
            # STAGE A: cheap OHLCV-only gate (no provider) BEFORE any
            # fundamentals fetch. Only the single cached OHLCV series is used;
            # float / sector / revisions / fundamentals are deferred to stage
            # B/C on survivors. value/all have no cheap technical signal so
            # they fall straight through to the fundamentals stage.
            ohlcv = None
            if args.scan != "value":
                sym_up = ticker.upper()
                ohlcv = _RUN_OHLCV_CACHE.get(sym_up)
                if ohlcv is None:
                    ohlcv = _fetch_ohlcv(ticker)
                    _RUN_OHLCV_CACHE[sym_up] = ohlcv
                if not _cheap_gate(ohlcv, args.scan, loose=args.value_dip_loose):
                    logger.info("cheap gate: skip %s (%s)", ticker, args.scan)
                    continue
            # Free price floor from the (already fetched) OHLCV close applies
            # to every scan when the last close is measurable.
            if args.price_min and ohlcv:
                closes = (ohlcv or {}).get("closes") or []
                if closes and closes[-1] is not None and closes[-1] < args.price_min:
                    logger.info("skip %s: price %.2f < floor", ticker, closes[-1])
                    continue
            # STAGE B: fundamentals for survivors (memoized -> once per ticker).
            fin = _fetch_fin_cached(ticker, args.date)
            # The moomoo rank carries market cap per symbol, but moomoo's
            # fundamentals feed (statements) does not - inject it so the EV /
            # earnings-yield / acquirer screens can run on the daily list.
            meta_cap = meta.get("market_cap")
            fin_cap = _latest(fin.get("market_cap"))
            # Prefer the day-of rank cap (real-time) over the parsed one when
            # both exist; inject when fundamentals lacked a cap entirely.
            if meta_cap is not None and (fin_cap is None or fin_cap < meta_cap):
                fin["market_cap"] = meta_cap
            cap = _latest(fin.get("market_cap"))
            if args.min_mcap and cap is not None and cap < args.min_mcap:
                logger.info("skip %s: market cap %.2fB < floor", ticker, cap / 1e9)
                continue
            row = screen_ticker(ticker, fin)
            # Phase-1 growth / structure gates - applied only when the metric
            # is MEASURED (missing data keeps the row: "n/a", never fabricated).
            if (
                args.min_eps_yoy
                and row.get("eps_yoy") is not None
                and (row["eps_yoy"] * 100.0) < args.min_eps_yoy
            ):
                logger.info(
                    "skip %s: EPS YoY %.1f%% < %.0f%%",
                    ticker,
                    row["eps_yoy"] * 100.0,
                    args.min_eps_yoy,
                )
                continue
            if (
                args.min_rev_yoy
                and row.get("revenue_yoy") is not None
                and (row["revenue_yoy"] * 100.0) < args.min_rev_yoy
            ):
                logger.info(
                    "skip %s: revenue YoY %.1f%% < %.0f%%",
                    ticker,
                    row["revenue_yoy"] * 100.0,
                    args.min_rev_yoy,
                )
                continue
            if args.min_roe and row.get("roe") is not None and (row["roe"] * 100.0) < args.min_roe:
                logger.info(
                    "skip %s: ROE %.1f%% < %.0f%%", ticker, row["roe"] * 100.0, args.min_roe
                )
                continue
            if args.max_mcap and cap is not None and cap > args.max_mcap:
                logger.info(
                    "skip %s: market cap %.2fB > ceiling %.2fB",
                    ticker,
                    cap / 1e9,
                    args.max_mcap / 1e9,
                )
                continue
            # Compute every scan bucket (TrendPB/Breakout/RSI/volume + momentum +
            # swing + VCP + value-dip) so the report columns are filled for both
            # the movers and the positional/file universes. For a dedicated
            # --scan mode, filter to that setup (mirrors the movers gating).
            row_scan: dict = {}
            if args.scan != "value":
                sym = ticker.upper()
                ohlcv = _RUN_OHLCV_CACHE.get(sym)
                if ohlcv is None:
                    ohlcv = _fetch_ohlcv(ticker)
                    _RUN_OHLCV_CACHE[sym] = ohlcv
                row_scan = _compute_scan_row(
                    ticker, ohlcv, fin, args.date, args.enable_float, loose=args.value_dip_loose
                )
                if args.scan == "trend-pullback" and not row_scan.get("a"):
                    continue
                if args.scan == "breakout" and not row_scan.get("b"):
                    continue
                if args.scan == "momentum":
                    _p = (row_scan.get("momentum") or {}).get("pillars") or {}
                    if any(v is False for v in _p.values()):
                        continue
                if args.scan == "swing" and not (row_scan.get("swing") or {}).get("candidate"):
                    continue
                if args.scan == "vcp" and not (row_scan.get("vcp") or {}).get("candidate"):
                    continue
                if args.scan == "value-dip":
                    vd_row = row_scan.get("value_dip") or {}
                    if not vd_row.get("candidate"):
                        # Only real evaluations belong in the near-miss table.
                        if args.value_dip_loose and "gates" in vd_row:
                            near_miss.append(_vd_near_miss_row(vd_row, ticker))
                        continue
            if args.sector_rank:
                from tradingagents.strategies.sector_rank import sector_standing

                sector = row.get("sector") or _fetch_sector_guarded(ticker)
                standing = sector_standing(sector, _sector_ranking())
                row["sector"] = standing.get("sector") or sector
                row["sec_rank"] = standing.get("rank")
                row["sec_top3"] = standing.get("top3_3m")
                if standing.get("verdict") == "tracking":  # measured, not top-3
                    logger.info(
                        "skip %s: sector %s rank %s not top-3",
                        ticker,
                        row["sector"],
                        row["sec_rank"],
                    )
                    continue
            if args.revision:
                rev = _fetch_revision_guarded(ticker)
                row["rev_net"] = rev.get("net") if rev else None
                if row["rev_net"] is not None and row["rev_net"] <= 0:
                    logger.info("skip %s: net analyst revisions %+d <= 0", ticker, row["rev_net"])
                    continue
            if args.inst_accum:
                inst = _inst_accumulation(route_to_vendor("get_institution_holdings", ticker))
                row["inst_latest_pp"] = inst.get("latest_pp") if inst else None
                row["inst_two_q_pp"] = inst.get("two_q_pp") if inst else None
                if inst is not None and inst.get("accumulate") is False:
                    logger.info(
                        "skip %s: institutional distribution (2q pp %.2f)", ticker, inst["two_q_pp"]
                    )
                    continue
            # Non-gating enrichments: populate Sec/SecRank / RevUp / Inst columns
            # without applying the filtering of --sector-rank / --revision /
            # --inst-accum, so the report shows these values but never drops rows.
            if args.enrich_sector:
                from tradingagents.strategies.sector_rank import sector_standing

                sector = row.get("sector") or _fetch_sector_guarded(ticker)
                standing = sector_standing(sector, _sector_ranking())
                row["sector"] = standing.get("sector") or sector
                row["sec_rank"] = standing.get("rank")
                row["sec_top3"] = standing.get("top3_3m")
            if args.enrich_rev:
                rev = _fetch_revision_guarded(ticker)
                row["rev_net"] = rev.get("net") if rev else None
            if args.enrich_inst:
                inst = _inst_accumulation(route_to_vendor("get_institution_holdings", ticker))
                row["inst_latest_pp"] = inst.get("latest_pp") if inst else None
                row["inst_two_q_pp"] = inst.get("two_q_pp") if inst else None
            if fmp_use:
                _nf = None
                try:
                    from tradingagents.dataflows.fmp import normalized_score as _nsc

                    _nf = _nsc(ticker)
                except Exception:
                    _nf = None
                if _nf:
                    row["nebit_ev_ebit"] = _nf.get("ev_nebit")
                    row["pe_pct5"] = _nf.get("pe_pct5")
                    row["fmp_ev"] = _nf.get("ev")
            sig = row_scan
            row["scan_a"] = bool(sig and sig.get("a"))
            row["scan_b"] = bool(sig and sig.get("b"))
            _mom = (sig or {}).get("momentum") if sig else None
            row["pills"] = sum(1 for v in _mom["pillars"].values() if v) if _mom else None
            row["pullback"] = bool(_mom.get("pullback")) if _mom else False
            row["mom_rr"] = _mom.get("mom_rr") if _mom else None
            _sw = (sig or {}).get("swing") if sig else None
            row["scan_c"] = bool(_sw and _sw.get("candidate"))
            _sw_rs = ((_sw or {}).get("relative_strength") or {}) if _sw else {}
            row["swing_rs"] = _sw_rs.get("verdict")
            row["swing_stop_pct"] = ((_sw or {}).get("stop") or {}).get("risk_pct")
            row["swing_t2_pct"] = (_sw or {}).get("t2_pct")
            _vc = (sig or {}).get("vcp") if sig else None
            row["vcp_flag"] = bool(_vc and _vc.get("candidate"))
            row["vcp_brk"] = (_vc or {}).get("close_to_base")
            _vd = (sig or {}).get("value_dip") if sig else None
            row["vdip_flag"] = bool(_vd and _vd.get("candidate"))
            row["vdip_fcfy"] = (_vd or {}).get("fcf_yield")
            row["vdip_rsi"] = (_vd or {}).get("rsi")
            row["vdip_pctb"] = (_vd or {}).get("pct_b")
            row["vdip_stop_pct"] = (_vd or {}).get("stop_pct")
            row["scan_rsi"] = sig.get("rsi") if sig else None
            row["scan_rvol"] = sig.get("rvol") if sig else None
            row["scan_qret"] = sig.get("qret") if sig else None
            if args.sentiment:
                row["sent7"], row["sentz"] = _sentiment_cols(ticker, args.date)
            name_fill = meta.get("name")
            if not name_fill:
                name_fill = fin.get("name") or fin.get("company_name") or fin.get("long_name")
            row["name"] = name_fill
            row["day_change"] = meta.get("day_change")
            # risk2.md liquidity columns (pure-calculable from OHLCV + float +
            # shares; n/a when the inputs are missing - never fabricated).
            try:
                from tradingagents.strategies.liquidity_risk import (
                    amihud_illiquidity as _illiq,
                    float_turnover as _ft,
                    free_float_factor as _iwf,
                )

                _ohl = _RUN_OHLCV_CACHE.get(ticker.upper())
                if _ohl is None:
                    _ohl = _fetch_ohlcv(ticker)
                    _RUN_OHLCV_CACHE[ticker.upper()] = _ohl
                _cl = _ohl.get("closes") or []
                _vl = _ohl.get("volumes") or []
                row["illiq"] = _illiq(_cl, _vl)
                _adv = sum(_vl[-30:]) / len(_vl[-30:]) if len(_vl) >= 30 else None
                _fs = None
                try:
                    from tradingagents.dataflows.float_shares import fetch_float_shares

                    _fs = fetch_float_shares(ticker)
                except Exception:  # noqa: BLE001
                    _fs = None
                row["float_turnover"] = _ft(_adv, _fs)
                _sh = fin.get("shares")
                _tot = _sh.get("current") if isinstance(_sh, dict) else _sh
                row["iwf"] = _iwf(_fs, _tot)
                # fundamental floors (Graham / NCAV / EPV)
                try:
                    from tradingagents.strategies.fundamental_floors import (
                        earnings_power_value as _epv,
                        epv_per_share as _epv_ps,
                        graham_number as _g,
                        ncav_per_share as _ncav,
                    )

                    _eps = _latest(fin.get("eps"))
                    _te = _latest(fin.get("total_equity"))
                    _tot_s = _latest(fin.get("shares"))
                    _bvps = (_te / _tot_s) if (_te and _tot_s) else None
                    _ca = _latest(fin.get("current_assets"))
                    _tl = _latest(fin.get("total_liabilities"))
                    _ebit = _latest(fin.get("operating_income"))
                    _ta = _latest(fin.get("total_assets"))
                    _beta = _latest(fin.get("beta"))
                    from tradingagents.strategies.dcf import wacc_from_beta as _wacc

                    _w = _wacc(0.04, _beta if _beta is not None else 1.0)
                    row["graham"] = _g(_eps, _bvps)
                    row["ncav"] = _ncav(_ca, _tl, _tot_s)
                    _epv_r = _epv(_ebit, 0.21, _w)
                    row["epv_ps"] = _epv_ps(_epv_r.get("epv"), _tot_s) if _epv_r else None
                except Exception:  # noqa: BLE001 - floors degrade to n/a
                    pass
                # technical factors (Phases 1-3): MFI / Stoch / KST / Chandelier
                try:
                    _hi = _ohl.get("highs") or []
                    _lo = _ohl.get("lows") or []
                    from tradingagents.strategies.size import atr as _atr14
                    from tradingagents.strategies.technical_factors import (
                        kst as _kst,
                        mf_index as _mfi,
                        stochastic_oscillator as _stoch,
                    )

                    row["mfi"] = _mfi(_hi, _lo, _cl, _vl)
                    _s = _stoch(_hi, _lo, _cl)
                    row["stoch_k"] = _s.get("k")
                    row["stoch_os"] = _s.get("oversold")
                    _kk = _kst(_cl)
                    row["kst"] = _kk.get("kst")
                    _at = _atr14(_hi, _lo, _cl, window=14) if len(_hi) >= 15 else None
                    from tradingagents.strategies.swing import chandelier_exit as _ch

                    _chd = _ch(_cl, _at)
                    row["chandel_exit"] = _chd.get("exit")
                    # mean-reversion technicals (StochRSI / RSI2 / W%R / Kelt /
                    # Donch / OBV / PSAR / Elder)
                    from tradingagents.strategies.technical_factors import (
                        aroon as _aroon,
                        donchian_channel as _don,
                        elder_thermometer as _elder,
                        fisher_transform as _fisher,
                        keltner_channel as _kelt,
                        obv_divergence as _obv,
                        parabolic_sar as _psar,
                        rsi2 as _rsi2,
                        stoch_rsi as _srsi,
                        supertrend as _supertrend,
                        volume_profile as _volprof,
                        williams_r as _wr,
                    )

                    _sr = _srsi(_cl)
                    row["stochrsi"] = _sr.get("stochrsi")
                    row["rsi2"] = _rsi2(_cl)
                    row["wr"] = _wr(_hi, _lo, _cl)
                    _ke = _kelt(_cl, atr_value=_at)
                    row["kelt_pct"] = _ke.get("pct")
                    _dn = _don(_hi, _lo)
                    row["donch_up"] = _dn.get("upper")
                    row["donch_lo"] = _dn.get("lower")
                    _ov = _obv(_cl, _vl)
                    row["obv_up"] = _ov.get("obv_up")
                    row["psar"] = _psar(_hi, _lo).get("sar")
                    row["elder"] = _elder(_vl).get("ratio")
                    # new dip/swing factors (Aroon / Fisher / Supertrend / POC)
                    _ar = _aroon(_hi, _lo)
                    row["aroon_up"] = _ar.get("aroon_up")
                    _fi = _fisher(_cl)
                    row["fisher"] = _fi.get("fisher")
                    _st = _supertrend(_hi, _lo, _cl)
                    row["supertrend_dir"] = _st.get("direction")
                    _vp = _volprof(_cl, _vl)
                    row["poc"] = _vp.get("poc")
                except Exception:  # noqa: BLE001 - technical factors degrade to n/a
                    pass
            except Exception:  # noqa: BLE001 - liquidity columns degrade to n/a
                pass
            results.append(row)
            logger.info("screened %s", ticker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not screen %s: %s", ticker, exc)

    if args.intraday and results:
        try:
            from tradingagents.dataflows.alpaca import get_intraday as _intraday
            from tradingagents.dataflows.alpaca_common import alpaca_credentials

            kid, sec = alpaca_credentials()
            if kid and sec:
                snap = _intraday([r["ticker"] for r in results])
                for r in results:
                    info = (snap or {}).get(r["ticker"]) or {}
                    r["line_price"] = info.get("price")
                    r["line_vwap"] = info.get("vwap")
                    r["line_vol"] = info.get("volume")
        except Exception:
            pass
    # Resolve the ranking mode: an explicit --rank wins, else the env/config
    # flag (enable_composite_rank). Previously --rank composite / the config
    # key were parsed but never read — the screener always used value ranking.
    from tradingagents.dataflows.config import get_config as _get_cfg

    rank_mode = args.rank or ("composite" if _get_cfg().get("enable_composite_rank") else "value")
    if rank_mode == "composite":
        closes_map = {}
        for r in results:
            try:
                closes = _fetch_closes(r["ticker"])
                if len(closes) >= 70:
                    closes_map[r["ticker"]] = closes
            except Exception:
                pass
        scores = composite_scores(results, closes_map) or {}
        ranked = sorted(results, key=lambda r2: scores.get(r2["ticker"]) or -1.0, reverse=True)
    else:
        ranked = rank_watchlist(results)
    alloc_extra = ""
    if args.alloc and results:
        alloc_extra = allocation_block(
            {r["ticker"]: r.get("earnings_yield") or 0.001 for r in results},
            returns_by_name=_alloc_returns(results),
        )
        markdown = _watchlist_markdown(ranked) + "\n\n" + alloc_extra
    else:
        markdown = _watchlist_markdown(ranked)
    # Full 11-SPDR sector ranking table: appended whenever the ranking was
    # computed (--sector-rank / --enrich-sector), so the reader sees the whole
    # sector table, not just the candidate's SecRank column.
    if args.sector_rank or args.enrich_sector:
        sector_table = _sector_table_markdown(_sector_ranking())
        if sector_table:
            markdown = markdown.rstrip() + "\n\n" + sector_table
            print(sector_table)
    # Value-dip loose gate: ranked near-miss table (up to 50) — the names
    # that passed the relaxed entry but missed another gate, honest about
    # which gate each failed.
    if args.value_dip_loose and near_miss:
        near_miss.sort(key=lambda nm: (len(nm["missing"]), nm["dist"]))
        near_miss = near_miss[:50]
        nm_lines = [
            "\n## Near misses (value-dip loose gate — missing gate)",
            "",
            "| Ticker | RSI | %b | Stp% | FCFy | Missing (gate) |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for nm_row in near_miss:
            nm_lines.append(
                "| {t} | {rsi} | {pb} | {stp} | {fy} | {miss} |".format(
                    t=nm_row["ticker"],
                    rsi=f"{nm_row['rsi']:.1f}" if nm_row["rsi"] is not None else "n/a",
                    pb=f"{nm_row['pct_b']:.2f}" if nm_row["pct_b"] is not None else "n/a",
                    stp=(
                        f"{nm_row['stop_pct'] * 100.0:.1f}%"
                        if nm_row["stop_pct"] is not None
                        else "n/a"
                    ),
                    fy=(
                        f"{nm_row['fcf_yield'] * 100.0:.1f}%"
                        if nm_row["fcf_yield"] is not None
                        else "n/a"
                    ),
                    miss=", ".join(nm_row["missing"]) or "n/a",
                )
            )
        nm_block = "\n".join(nm_lines)
        markdown = markdown.rstrip() + "\n\n" + nm_block + "\n"
        print(nm_block)
        print(f"[screener] {len(near_miss)} value-dip near misses (loose gate)")
    print_watchlist(ranked)
    if alloc_extra:
        print(alloc_extra)
    try:
        from tradingagents.dataflows.alpaca import get_clock as _alpaca_clock
        from tradingagents.dataflows.config import get_config

        if get_config().get("enable_alpaca"):
            clock = _alpaca_clock()
            if clock is not None and not clock.get("is_open"):
                note = "[alpaca] market CLOSED (use /calendar for next open)"
                print(note)
                markdown = markdown.rstrip() + "\n\n" + note + "\n"
    except Exception:
        pass
    if args.journal and args.scan == "momentum":
        try:
            from tradingagents.strategies.journal import format_summary, momentum_stats

            print(format_summary(momentum_stats(args.journal)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("momentum journal summary failed: %s", exc)
    saved = save_watchlist(markdown, args.out_dir)
    print(f"[screener] saved watchlist to {saved}")
    # Close the moomoo context while the process is healthy: the SDK's
    # OpenQuoteContext spawns a non-daemon receive thread that keeps the
    # process alive after main() returns, and closing at interpreter exit can
    # block on the dead receive loop (the web job then times out even though
    # the report is written).
    try:
        from tradingagents.dataflows.moomoo import close_context

        close_context()
    except Exception:  # noqa: BLE001 - closing is best-effort
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
