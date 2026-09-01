#!/usr/bin/env python3
"""Pre-market review of a prior close-time decision (design:
``docs/pre_market_review.md``).

Reads the machine-shaped prior state (``full_states_log_<date>.json``) + the
human ``5_portfolio/decision.md`` from a prior report folder, fetches measured
overnight deltas (pre-market/open quote, B1 catalyst snapshot), runs the
deterministic verdict arbiter (``strategies/pre_market.review_decision``), then
optionally invokes the Pre-Market Reviewer LLM (a deep-think prompt variant) to
emit a ``PreMarketVerdict``. Writes ``pre_market_review_<today>.md`` next to
the report folder.

Same-night (in-batch) mode = catalyst/quality re-check only (no quote → CONFIRM
or REVISE on the catalyst window). The pre-open gap re-anchor path is invoked
here, standalone, before the next open.

Examples:
    py -3.12 scripts/pre_market_review.py --ticker EIX
    py -3.12 scripts/pre_market_review.py --ticker EIX --prior-date 2026-08-22
    py -3.12 scripts/pre_market_review.py --ticker EIX --report-dir reports/EIX_20260822_181500 --dry-run
    py -3.12 scripts/pre_market_review.py --ticker EIX --skip-llm   # deterministic verdict only

Exit codes: 0 ok, 2 review produced a REJECT (paper-book skip), 3 no prior
report found, 4 deltas could not be fetched.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import os
import sys
from pathlib import Path

from tradingagents.dataflows.config import get_config as _get_config
from tradingagents.default_config import DEFAULT_CONFIG

# scripts/ is not a package; load like pipeline.py does for value_screener.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _discover_report_dir(ticker: str, report_dir: str | None, prior_date: str | None) -> str | None:
    """None explicitly given: newest ``reports/<TICKER>_<ts>/`` folder."""
    if report_dir:
        return report_dir if os.path.isdir(report_dir) else None
    from tradingagents.dataflows.utils import resolve_output_path

    reports_root = resolve_output_path("reports")
    if not reports_root.is_dir():
        return None
    hits = []
    for folder in reports_root.iterdir():
        if not folder.is_dir():
            continue
        stem = folder.name
        base = stem.split("_")[0].upper()
        if base == (ticker or "").upper():
            hits.append(folder)
    if not hits:
        return None
    if prior_date:
        stamp = prior_date.replace("-", "")
        hit = next((h for h in hits if stamp in h.name), None)
        if hit:
            return str(hit)
        return None
    return str(sorted(hits, key=lambda p: os.path.getmtime(p), reverse=True)[0])


def _fetch_deltas(ticker: str, trade_date: str, prior_date: str, prior_state: dict) -> dict:
    """Fetch measured overnight deltas: a price window + B1 catalyst snapshot.

    The vendor CSV is ``Date,Open,High,Low,Close,Volume``. ``prior_close`` =
    the last close on or before ``prior_date``; ``open_price`` is a real-time
    pre-market/latest price when available (Alpaca 1m snapshot when enabled,
    else yfinance ``fast_info.last_price``), falling back to the latest daily
    close. ``atr`` = ATR(14) over the window. The gap the arbiter computes is
    therefore the genuine overnight delta, not a noise artifact.
    """
    from tradingagents.dataflows.interface import route_to_vendor
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.strategies.catalyst import build_catalyst_snapshot, fetch_catalyst_data
    from tradingagents.strategies.size import atr as _atr

    prior_dt = _dt.date.fromisoformat(prior_date)
    start = (prior_dt - _dt.timedelta(days=30)).isoformat()
    end = (_dt.date.fromisoformat(trade_date) + _dt.timedelta(days=1)).isoformat()
    deltas: dict = {"catalyst": None, "open_price": None, "prior_close": None, "atr": None}
    closes, highs, lows = [], [], []
    try:
        out = route_to_vendor("get_stock_data", ticker, start, end) or ""
        prior_close = None
        latest_close = None
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("date,"):
                continue
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                d = parts[0].strip()
                h = float(parts[2])
                lo = float(parts[3])
                c = float(parts[4])
            except (ValueError, IndexError):
                continue
            closes.append(c)
            highs.append(h)
            lows.append(lo)
            # Last close on or before the prior trade date = the prior close.
            if d <= prior_date and prior_close is None:
                prior_close = c
            latest_close = c
        deltas["prior_close"] = prior_close
        deltas["open_price"] = latest_close  # daily fallback; overridden below
        if len(closes) >= 15:
            deltas["atr"] = _atr(highs, lows, closes, window=14)
    except Exception:  # noqa: BLE001 - degrade like the router
        deltas["open_price"] = None

    # Defect-4 / feature-1: prefer a real-time pre-market/latest price.
    realtime = _realtime_price(ticker)
    if realtime is not None:
        deltas["open_price"] = realtime

    # P1/P2 advisory pre-open reads (Alpaca free IEX; all degrade to 'unavailable'
    # when Alpaca is off - never fabricated). Fed to the reviewer as context only.
    try:
        from tradingagents.dataflows.preopen import (
            premarket_rvol,
            preopen_book_depth,
            preopen_gap,
        )

        deltas["premarket_rvol"] = premarket_rvol(ticker)
        deltas["preopen_gap"] = preopen_gap(ticker, prev_close=deltas.get("prior_close"))
        deltas["preopen_depth"] = preopen_book_depth(ticker)
    except Exception:  # noqa: BLE001 - advisory reads degrade to None
        deltas["premarket_rvol"] = None
        deltas["preopen_gap"] = None
        deltas["preopen_depth"] = None

    try:
        data = fetch_catalyst_data(ticker, trade_date)
        if data is not None:
            deltas["catalyst"] = build_catalyst_snapshot(data, trade_date, DEFAULT_CONFIG)
    except Exception:  # noqa: BLE001
        deltas["catalyst"] = None

    # Feature 5: guarded headline delta for the reviewer's context (never a hard
    # gate — titles only, degrades to []).
    deltas["news_titles"] = _headline_delta(ticker, start, end)
    return deltas


def _headline_delta(ticker: str, start: str, end: str, limit: int = 3) -> list[str]:
    """First ``limit`` overnight headlines for the reviewer context (feature 5).

    Uses the configured news chain (moomoo/yfinance/...); any failure degrades to
    [] (the reviewer then has no news line — never a fabricated headline).
    """
    try:
        from tradingagents.dataflows.interface import route_to_vendor

        out = route_to_vendor("get_news", ticker, start, end) or ""
        titles = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("-"):
                cand = line.lstrip("- ").strip().strip("*").strip()
                if len(cand) > 8 and cand not in titles:
                    titles.append(cand)
            if len(titles) >= limit:
                break
        return titles
    except Exception:  # noqa: BLE001
        return []


def _realtime_price(ticker: str) -> float | None:
    """A real-time/latest pre-market price, guarded by source.

    Order: Alpaca 1-minute snapshot (when ``enable_alpaca``) -> yfinance
    ``fast_info.last_price`` -> None (caller keeps the daily close). Any
    failure degrades to None; never raises, never invents.
    """
    try:
        cfg = _get_config()
        if cfg.get("enable_alpaca"):
            from tradingagents.dataflows.alpaca import get_intraday as _ai

            snap = _ai([ticker])
            price = (snap or {}).get(ticker, {}).get("price")
            if price:
                return float(price)
    except Exception:  # noqa: BLE001
        pass
    try:
        import yfinance as yf

        from tradingagents.dataflows.symbol_utils import normalize_symbol

        fi = yf.Ticker(normalize_symbol(ticker)).fast_info
        price = fi.get("last_price") if hasattr(fi, "get") else getattr(fi, "last_price", None)
        if price and price > 0:
            return float(price)
    except Exception:  # noqa: BLE001
        pass
    return None


def _extract_prior_close(state: dict) -> float | None:
    """Best-effort prior close from the stored state (may be absent)."""
    # The full_states_log does not persist OHLCV closes; a prior decision's
    # 'Trade date' close would need the vendor again. Keep None → the arbiter
    # treats the quote as the anchor only (gap pct None is fine for same-night).
    return None


def _build_summary(deltas: dict, verdict: dict) -> str:
    """Compact, number-only summary string the reviewer LLM indexes."""
    lines = []
    gap = verdict.get("gap") or {}
    if gap.get("gap_pct") is not None:
        lines.append(f"- gap: {gap['gap_pct']:+.1%} ({gap.get('gap_atr') or 0:.2f}A)")
    cat = verdict.get("catalyst") or {}
    if cat.get("hard_block"):
        lines.append(f"- catalyst: HARD BLOCK (earnings {cat.get('earnings_date')})")
    elif cat.get("verdict") != "no-imminent-catalyst":
        lines.append(f"- catalyst: {cat['verdict']} scale {cat.get('scale', 1.0):.2f}")
    ra = verdict.get("reanchor") or {}
    if ra.get("valid"):
        lines.append(
            f"- re-anchored: entry {ra.get('avg_entry')} stop {ra.get('stop')} "
            f"peak-deployed {ra.get('peak_deployed_pct', 0):.1%}"
        )
    if (deltas or {}).get("news_titles"):
        lines.append("- overnight headlines: " + " | ".join(deltas["news_titles"]))
    rv = deltas.get("premarket_rvol") or {}
    if rv.get("rvol") is not None:
        lines.append(
            f"- pre-market RVOL {rv['rvol']:.2f}x "
            f"(today {rv['today_vol']:.0f} vs {rv['avg_vol']:.0f} 30d pre-open avg; "
            f"{'>2.0x institutional' if rv['rvol'] >= 2.0 else 'retail/quiet'})"
        )
    pg = deltas.get("preopen_gap") or {}
    if pg.get("gap_pct") is not None:
        lines.append(f"- pre-open gap {pg['gap_pct']:+.2%} vs live pre-open "
                     f"price {pg.get('preopen_price')}")
    pd = deltas.get("preopen_depth") or {}
    if pd.get("thin") is not None:
        lines.append(f"- pre-open book: spread_bps={pd.get('spread_bps')} "
                     f"bid/ask imbalance={pd.get('bid_ask_imbalance')} "
                     f"thin={'YES' if pd.get('thin') else 'no'}")
    if not lines:
        lines.append("- no measurable overnight gap / catalyst delta")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True, help="ticker symbol")
    parser.add_argument("--prior-date", default=None, help="prior trade date YYYY-MM-DD")
    parser.add_argument("--report-dir", default=None, help="explicit prior report folder")
    parser.add_argument("--trade-date", default=None, help="today YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="print verdict, write nothing")
    parser.add_argument("--skip-llm", action="store_true", help="deterministic verdict only")
    args = parser.parse_args(argv)

    trade_date = args.trade_date or _dt.date.today().isoformat()
    report_dir = _discover_report_dir(args.ticker, args.report_dir, args.prior_date)
    if not report_dir:
        print(f"no prior report found for {args.ticker}", file=sys.stderr)
        return 3

    from tradingagents.strategies.pre_market import (
        load_prior_state,
        parse_planned_levels,
        reanchor_plan,
        review_decision,
    )

    prior = load_prior_state(report_dir, args.prior_date)
    if not prior["state"]:
        print(f"[warn] no full_states_log for {args.ticker} in {report_dir}; using decision.md only")

    deltas = _fetch_deltas(args.ticker, trade_date, args.prior_date or trade_date, prior)
    decision_text = prior["decision_md"] or (prior["state"] or {}).get(
        "final_trade_decision", ""
    )
    # Defect-1 fix: extract the prior plan's entry/stop and re-anchor the
    # tranche plan to the measured open so the gap/through-stop/adverse-fill
    # checks (and the re-anchored REVISE levels) actually run.
    planned = parse_planned_levels(prior.get("state") or {}, decision_text)
    anchor = reanchor_plan(
        deltas.get("open_price"),
        deltas.get("atr"),
        max_position_pct=float(DEFAULT_CONFIG.get("max_position_pct", 0.30)),
        max_book_position_pct=float(DEFAULT_CONFIG.get("risk_max_position_pct", 0.45)),
    )
    verdict = review_decision(
        prior_close=deltas.get("prior_close"),
        open_price=deltas.get("open_price"),
        prior_stop=planned.get("stop"),
        entry_price=planned.get("entry"),
        atr_value=deltas.get("atr"),
        catalyst_snapshot=deltas.get("catalyst"),
        reanchor=anchor,
    )
    # Item 5 (limit-order directive when pre-market liquidity is thin): firms
    # avoid market orders pre-open because spreads are wide. When the measured
    # volume implies a thin/illiquid book, append a deterministic directive to
    # the verdict reasons so the reviewer/order path prefers limit orders and
    # reduced size. Best-effort: never changes the verdict, only adds a reason.
    try:
        from datetime import datetime as _dt2, timedelta as _td

        from tradingagents.dataflows.interface import route_to_vendor
        from tradingagents.strategies.market_session import premarket_liquidity

        _end = _dt2.now().strftime("%Y-%m-%d")
        _start = (_dt2.now() - _td(days=40)).strftime("%Y-%m-%d")
        _out = route_to_vendor("get_stock_data", args.ticker, _start, _end) or ""
        _vols = []
        for _ln in _out.splitlines():
            _ln = _ln.strip()
            if not _ln or _ln.startswith("#") or _ln.lower().startswith("date,"):
                continue
            _p = _ln.split(",")
            if len(_p) >= 6:
                with contextlib.suppress(ValueError):
                    _vols.append(float(_p[5]))
        if len(_vols) >= 30:
            _latest = float(_vols[-1])
            _avg = sum(_vols[-30:]) / 30
            _liq = premarket_liquidity(_latest, _avg)
            if _liq.get("verdict") in ("thin", "illiquid"):
                # Cookbook recipe 2 execution read: a one-sided depth confirms
                # the thin-book directive (best-effort; never blocks).
                _depth_line = ""
                try:
                    from tradingagents.strategies.market_session import book_depth_read

                    _bid = deltas.get("preopen_bid")
                    _ask = deltas.get("preopen_ask")
                    _bs = deltas.get("preopen_bid_size")
                    _as = deltas.get("preopen_ask_size")
                    if _bid is not None and _ask is not None and _bs is not None and _as is not None:
                        _bd = book_depth_read(_bid, _ask, _bs, _as)
                        if _bd.get("microprice") is not None:
                            _depth_line = (
                                f" depth: microprice={_bd['microprice']} "
                                f"obi={_bd['obi']:+.2f} ({_bd['verdict']})"
                            )
                except Exception:  # noqa: BLE001 - advisory only
                    pass
                verdict["reasons"].append(
                    f"pre-market liquidity {_liq['verdict']} (ratio {_liq['ratio']:.2f})"
                    f"{_depth_line}: prefer limit orders and reduce size at the "
                    "open (wide spreads)"
                )
    except Exception:  # noqa: BLE001 - the directive is best-effort, never blocks
        pass
    summary = _build_summary(deltas, verdict)

    reviewed = None
    if not args.skip_llm:
        try:
            from tradingagents.agents.overrides.pre_market_reviewer import (
                create_pre_market_reviewer,
            )
            from tradingagents.llm_clients.factory import create_llm_client

            client = create_llm_client(
                provider=DEFAULT_CONFIG["llm_provider"],
                model=DEFAULT_CONFIG["deep_think_llm"],
                base_url=DEFAULT_CONFIG.get("backend_url"),
            )
            reviewer = create_pre_market_reviewer(client.get_llm())
            reviewed = reviewer(decision_text, summary)
        except Exception as exc:  # noqa: BLE001 - deterministic verdict fallback
            print(f"[warn] reviewer LLM unavailable ({exc}); using deterministic verdict")

    # The deterministic arbiter is the safety floor: a deterministic REJECT can
    # never be downgraded by the LLM.
    final_verdict = verdict["verdict"]
    if reviewed and verdict["verdict"] == "REJECT":
        final_verdict = "REJECT"

    body = [
        f"# Pre-Market Review — {args.ticker} ({trade_date})",
        "",
        f"**Prior report**: `{report_dir}`",
        f"**Prior decision**: {decision_text[:400]}",
        "",
        "## Measured deltas",
        summary,
        "",
        "## Deterministic verdict",
        f"**{verdict['verdict']}**",
        "; ".join(verdict["reasons"]),
        "",
    ]
    if reviewed:
        body += ["## Reviewer verdict", reviewed, ""]

    out_text = "\n".join(body)
    if args.dry_run:
        print(out_text)
        return 0

    out_dir = Path(report_dir)
    out_path = out_dir / f"pre_market_review_{trade_date}.md"
    out_path.write_text(out_text, encoding="utf-8")
    print(f"wrote {out_path}")

    # Feature 3: paper-book ledger — one row per review; resolved next review.
    try:
        from tradingagents.strategies.pre_market import record_review, resolve_ledger

        ledger_path = os.path.join(DEFAULT_CONFIG["data_cache_dir"], "pre_market_ledger.jsonl")
        record_review(
            ledger_path,
            ticker=args.ticker,
            prior_date=args.prior_date or trade_date,
            trade_date=trade_date,
            verdict=final_verdict,
            reasons=verdict.get("reasons") or [],
            gap_pct=(verdict.get("gap") or {}).get("gap_pct"),
            catalyst_verdict=(verdict.get("catalyst") or {}).get("verdict"),
            prior_close=deltas.get("prior_close"),
        )
        n = resolve_ledger(ledger_path, args.ticker, trade_date, deltas.get("open_price"))
        if n:
            print(f"[ledger] resolved {n} prior review(s) for {args.ticker}")
    except Exception as exc:  # noqa: BLE001 - ledger is best-effort
        print(f"[ledger] skipped for {args.ticker}: {exc}")

    # Close the moomoo context while the process is healthy (see value_screener
    # main()): the SDK's receive thread keeps the process alive after main()
    # returns, and closing at interpreter exit can block.
    try:
        from tradingagents.dataflows.moomoo import close_context

        close_context()
    except Exception:  # noqa: BLE001 - closing is best-effort
        pass
    return 0 if final_verdict != "REJECT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
