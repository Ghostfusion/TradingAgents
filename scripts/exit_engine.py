#!/usr/bin/env python3
"""Run the exit engine over a book or a ticker list (advisory, never an order).

The engine walks each name from its entry to the latest bar and answers one
question: what is the exit decision **now**, and which of the five mechanisms
produced it? It composes the repo's own producers (the ATR the swing tools
print, the chandelier rule, the §101 ladder, the §58 time horizon) and adds the
three rules nothing else answered: a *confirmed* trend break, momentum
deterioration as persistence rather than level, and the opportunity-cost stall.

Nothing here places, sizes or gates a trade, and no report is a promise of a
fill: with only daily bars the model never invents an intrabar price.

    py -3.12 scripts/exit_engine.py --tickers NVDA AMKR --entry-bars 40
    py -3.12 scripts/exit_engine.py --holdings Positions/Account1/*.csv \\
        --entry-date 2026-08-15 --out-dir screener
    py -3.12 scripts/exit_engine.py --tickers NVDA --entry-date 2026-08-15 --variants

The report lands as ``<out-dir>/exit_engine_<stamp>.md`` (out-dir ``screener``
by default, so the web app's Reports -> "Screen reports" block renders it).

Exit codes: 0 ok, 2 no usable entry reference, 3 the engine gate is off,
4 usable bars for no name.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tradingagents.strategies.exit_engine import (  # noqa: E402
    DEFAULT_MOMENTUM_EXIT_THRESHOLD,
    EXIT_ACTIONS,
    ExitConfig,
    classify_exit,
    compare_exit_variants,
    evaluate_long_exit,
    initial_stop,
    momentum_deterioration,
    sma_break_confirmed,
    stall_exit,
    trailing_stop_level,
)

DEFAULT_OUT_DIR = "screener"
REPORT_PREFIX = "exit_engine_"
ENTRY_PRICE_COLUMNS = ("Average cost basis", "Average Cost", "Avg Cost", "Cost Price")


def _gate_on() -> bool:
    """The engine ships off; ``TRADINGAGENTS_ENABLE_EXIT_ENGINE`` arms it."""
    raw = os.environ.get("TRADINGAGENTS_ENABLE_EXIT_ENGINE", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off", ""):
        try:
            from tradingagents.dataflows.config import get_config

            return bool(get_config().get("enable_exit_engine", False))
        except Exception:  # noqa: BLE001 - an unreadable config is not an armed gate
            return False
    return False


def _bars(ticker: str, days: int) -> dict:
    """Daily OHLCV through the same look-ahead-filtered chain the tools read."""
    from tradingagents.agents.utils.analysis_tools import _ohlcv

    return _ohlcv(ticker, days=days)


def _holdings(paths: list[str]) -> tuple[dict[str, float | None], list[str]]:
    """``{symbol: average cost}`` plus what was read, from broker position CSVs."""
    prices: dict[str, float | None] = {}
    notes: list[str] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            notes.append(f"{raw}: not found")
            continue
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
            for row in csv.DictReader(handle):
                symbol = str(row.get("Symbol") or "").strip().upper()
                if not symbol or any(ch in symbol for ch in ("*", " ")):
                    continue
                cost = None
                for column in ENTRY_PRICE_COLUMNS:
                    value = str(row.get(column) or "").replace("$", "").replace(",", "").strip()
                    if value:
                        try:
                            cost = float(value)
                        except ValueError:
                            cost = None
                        break
                prices[symbol] = cost
        notes.append(f"{path}: {len(prices)} name(s)")
    return prices, notes


def _momentum_series(ticker: str) -> tuple[list[float], str]:
    """The recorded composite series for ``ticker``, oldest first."""
    try:
        from tradingagents.strategies.score_history import read_history

        rows = read_history(ticker)
    except Exception as exc:  # noqa: BLE001 - an absent store is not a measured score
        return [], f"score history unreadable ({type(exc).__name__})"
    series = [float(r["score"]) for r in rows if isinstance(r.get("score"), (int, float))]
    if not series:
        return [], "no recorded score history (the store holds a row per scored run date)"
    return series, f"{len(series)} recorded score(s)"


def _rs_deteriorating(closes: list[float], benchmark: list[float] | None) -> tuple[bool | None, str]:
    """The repo's own verdict: `lagging` is what "relative strength deteriorating" means."""
    if not benchmark or not closes:
        return None, "no benchmark series"
    try:
        from tradingagents.strategies.relative_strength import relative_strength_report

        verdict = str(relative_strength_report(list(closes), list(benchmark)).get("verdict") or "")
    except Exception as exc:  # noqa: BLE001
        return None, f"RS unavailable ({type(exc).__name__})"
    if verdict == "unknown":
        return None, "RS verdict unknown"
    return verdict == "lagging", f"RS verdict {verdict}"


def _resolve_entry(dates: list, entry_date: str | None, entry_bars: int | None) -> int | None:
    """The last bar at or before ``entry_date``, or ``entry_bars`` sessions back."""
    n = len(dates)
    if entry_bars is not None:
        return max(0, n - 1 - int(entry_bars))
    if entry_date:
        wanted = str(entry_date)[:10]
        found = None
        for i, value in enumerate(dates):
            if str(value)[:10] <= wanted:
                found = i
            else:
                break
        if found is not None:
            return found
        return None
    return None


def _rules_read(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    entry: float,
    entry_idx: int,
    config: ExitConfig,
    scores: list[float],
    rs: bool | None,
) -> dict:
    """Each mechanism's own current read, so the census is measured, not asserted."""
    window = closes[entry_idx:]
    days_held = len(closes) - 1 - entry_idx
    unrealized = closes[-1] / entry - 1.0 if entry > 0 else None
    atr_now = None
    if len(closes) >= config.atr_period + 1:
        from tradingagents.strategies.size import atr as _atr

        atr_now = _atr(highs, lows, closes, window=config.atr_period)
    high_water = max(highs[entry_idx:]) if highs and len(highs) == len(closes) else max(window)
    return {
        "initial_stop": initial_stop(entry, atr_now, multiple=config.initial_atr_multiple),
        "trailing_stop": trailing_stop_level(
            None, high_water, atr_now, multiple=config.trailing_atr_multiple
        ),
        "trend": sma_break_confirmed(
            closes, period=config.trend_ma_period, confirm_bars=config.trend_confirm_bars
        ),
        "momentum": momentum_deterioration(
            scores,
            threshold=config.momentum_exit_threshold,
            confirm_bars=config.momentum_confirm_bars,
        ),
        "stall": stall_exit(
            days_held,
            unrealized_return=unrealized,
            rs_deteriorating=rs,
            max_stalled_bars=config.max_stalled_bars,
        ),
        "days_held": days_held,
        "unrealized_return": unrealized,
        "high_water": high_water,
        "atr": atr_now,
    }


def _ladder_table() -> list[tuple[str, str]]:
    """The published vocabulary, computed through the engine's own classifier."""
    slots = ("risk_gate", "stop", "trailing_stop", "target", "thesis_break", "time_exit")
    rows = [(slot, classify_exit(slot, coverage=1)) for slot in slots]
    rows.append(("(none fired)", classify_exit(None, coverage=1)))
    rows.append(("(deteriorating, nothing fired)", classify_exit(None, coverage=1, deteriorated=True)))
    rows.append(("(nothing measured)", classify_exit(None, coverage=0)))
    return rows


def _evaluate_name(
    symbol: str,
    bars: dict,
    *,
    config: ExitConfig,
    entry_idx: int | None,
    entry_price: float | None,
    benchmark: list[float] | None,
    risk_gate: str | None,
    variants: bool,
) -> dict:
    closes = [float(c) for c in bars.get("closes") or []]
    if len(closes) < 2 or entry_idx is None:
        return {
            "symbol": symbol,
            "result": None,
            "reason": (
                "no usable bars" if len(closes) < 2 else "no entry reference in this series"
            ),
        }
    highs = [float(h) for h in bars.get("highs") or []]
    lows = [float(low) for low in bars.get("lows") or []]
    opens = [float(o) for o in bars.get("opens") or []]
    dates = list(bars.get("dates") or [])
    scores, score_note = _momentum_series(symbol)
    rs, rs_note = _rs_deteriorating(closes, benchmark)
    entry = float(entry_price) if entry_price else float(closes[entry_idx])
    common = {
        "closes": closes,
        "highs": highs or None,
        "lows": lows or None,
        "opens": opens or None,
        "dates": dates or None,
        "entry_idx": entry_idx,
        "entry_price": entry_price,
        "config": config,
        "momentum_scores": scores or None,
        "rs_deteriorating": rs,
        "risk_gate": risk_gate,
    }
    result = evaluate_long_exit(**common)
    payload = {
        "symbol": symbol,
        "result": result,
        "reason": None,
        "score_note": score_note,
        "rs_note": rs_note,
        "read": _rules_read(closes, highs, lows, entry, entry_idx, config, scores, rs),
        "bars": len(closes),
    }
    if variants:
        payload["variants"] = compare_exit_variants(
            closes,
            highs=highs or None,
            lows=lows or None,
            opens=opens or None,
            dates=dates or None,
            entry_idx=entry_idx,
            entry_price=entry,
            config=config,
            momentum_scores=scores or None,
            rs_deteriorating=rs,
            risk_gate=risk_gate,
        )
    return payload


def _fmt(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{float(value):,.{digits}f}"


def _markdown(rows: list[dict], config: ExitConfig, notes: list[str], stamp: str) -> str:
    out = [
        f"# Exit engine - {stamp} (research only; it never places, sizes or gates an order)",
        "",
        "**Ladder** (slot -> action, computed by the engine's own classifier): "
        + ", ".join(f"`{slot}` -> `{action}`" for slot, action in _ladder_table()),
        "",
        f"**Vocabulary**: {', '.join(f'`{a}`' for a in EXIT_ACTIONS)}",
        "",
        "**Parameters**: 2.5xATR initial stop, 3xATR chandelier from the high-water mark, "
        f"MA{config.trend_ma_period} x{config.trend_confirm_bars} confirmation, momentum "
        f"exit below {config.momentum_exit_threshold:g} "
        f"(the composite's own band edge; the brief's 35 sits inside it) x"
        f"{config.momentum_confirm_bars}, stall {config.max_stalled_bars}d "
        f"({'armed' if config.enable_stall_exit else 'off'}), evaluation "
        f"{config.stop_evaluation}, costs {config.cost_bps:g}bps. "
        "Sources: LeBeau 2005 (2-3xATR initial, 3xATR chandelier, 30-50d MA for stocks); "
        "Alvarez 2015 (2.5xATR at the close: 776 total R vs 607 intraday, 164 no-stop); "
        "Alvarez 2014 (the stall rule left CAR and MDD essentially unchanged - hence off).",
        "",
        "| Symbol | Action | Reason | Exit | Days | Entry | Stop now | Trail now | Fill | Exec | Net | Cov | Absent |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        result = row.get("result")
        if not result:
            out.append(
                f"| {row['symbol']} | UNAVAILABLE | {row.get('reason')} | - | - | - | - | - | - | - | - | 0 | - |"
            )
            continue
        exit_text = (
            "open"
            if result["exit_index"] is None
            else f"bar {result['exit_index']} @ {_fmt(result['exit_price'])}"
        )
        absent = ", ".join(sorted(result["absent"])) or "-"
        out.append(
            "| {sym} | {action} | {reason} | {exit} | {days} | {entry} | {stop} | {trail} | "
            "{fill} | {execn} | {net} | {cov} | {absent} |".format(
                sym=row["symbol"],
                action=result["action"],
                reason=result["reason"],
                exit=exit_text,
                days=result["days_held"],
                entry=_fmt(result["entry_price"]),
                stop=_fmt(result["stop_now"]),
                trail=_fmt(result["trailing_stop"]),
                fill=_fmt(result["exit_price"]),
                execn=result["execution"] or "-",
                net="n/a" if result["net_return"] is None else f"{result['net_return']:+.2%}",
                cov=result["coverage"],
                absent=absent,
            )
        )
    out += ["", "## Per-name rule census", ""]
    for row in rows:
        read = row.get("read")
        if not read:
            continue
        result = row.get("result") or {}
        trend, mom, stall = read["trend"], read["momentum"], read["stall"]
        open_return = (
            "n/a" if read["unrealized_return"] is None else f"{read['unrealized_return']:+.2%}"
        )
        momentum_line = mom["reason"] or (
            f"last {mom['last']}, {mom['sessions_below']} of {config.momentum_confirm_bars} "
            f"below {config.momentum_exit_threshold:g}"
        )
        trend_line = (
            f"MA{config.trend_ma_period} {_fmt(trend['ma'])} x{config.trend_confirm_bars}, "
            f"below {trend['below']}, bars below {trend['bars_below']}, break {trend['break']}"
        )
        if trend["reason"]:
            trend_line += f" ({trend['reason']})"
        out += [
            f"### {row['symbol']}",
            f"- bars {row['bars']}; entry bar {result.get('entry_idx', '-')}; held "
            f"{read['days_held']} sessions; open return {open_return}",
            f"- ATR{config.atr_period} {_fmt(read['atr'], 4)}; high-water {_fmt(read['high_water'])}; "
            f"initial stop {_fmt(read['initial_stop'])}; chandelier at the current high-water "
            f"{_fmt(read['trailing_stop'])}",
            f"- trend: {trend_line}",
            f"- momentum: {momentum_line}",
            f"- stall: {stall['reason']}",
            f"- basis: {result.get('basis') or 'n/a'}",
            f"- scores: {row.get('score_note')}; relative strength: {row.get('rs_note')}",
            "",
        ]
    for row in rows:
        variants = row.get("variants")
        if not variants:
            continue
        out += [
            f"## {row['symbol']} - the four-variant ladder (identical entry)",
            "",
            "| Variant | Action | Reason | Exit | Days | Net | Peak gain | Surrendered | Triggered |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for name in variants["order"]:
            variant = variants["variants"][name]
            out.append(
                f"| {name} | {variant['action']} | {variant['reason']} | "
                f"{'-' if variant['exit_index'] is None else variant['exit_index']} | "
                f"{variant['holding_days'] if variant['holding_days'] is not None else '-'} | "
                f"{_fmt(variant['net_return'], 4)} | "
                f"{_fmt(variant['peak_gain_pct'], 4)} | "
                f"{_fmt(variant['surrendered_pct'], 4)} | "
                f"{', '.join(sorted(variant['triggered'])) or '-'} |"
            )
        out.append("")
    if notes:
        out += ["## Notes", *[f"- {note}" for note in notes], ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", nargs="*", default=[], help="symbols to evaluate")
    parser.add_argument(
        "--holdings",
        nargs="*",
        default=[],
        help="broker position CSV(s) for symbols + the average cost basis",
    )
    parser.add_argument("--entry-date", default=None, help="YYYY-MM-DD the position was opened")
    parser.add_argument(
        "--entry-bars", type=int, default=None, help="sessions held (alternative to --entry-date)"
    )
    parser.add_argument("--entry-price", type=float, default=None, help="entry price for every name")
    parser.add_argument("--benchmark", default="SPY", help="benchmark ticker for the RS verdict")
    parser.add_argument("--bars", type=int, default=320, help="daily bars to fetch")
    parser.add_argument("--risk-gate", default=None, help="PASS | WARN | REJECT (unmeasured when absent)")
    parser.add_argument("--initial-mult", type=float, default=2.5)
    parser.add_argument("--trailing-mult", type=float, default=3.0)
    parser.add_argument("--trend-confirm", type=int, default=2)
    parser.add_argument("--trend-ma", type=int, default=50)
    parser.add_argument("--momentum-threshold", type=float, default=DEFAULT_MOMENTUM_EXIT_THRESHOLD)
    parser.add_argument("--momentum-confirm", type=int, default=3)
    parser.add_argument("--stall-days", type=int, default=20)
    parser.add_argument("--enable-stall", action="store_true", help="arm the stall rule (off by default)")
    parser.add_argument(
        "--stop-evaluation", choices=("close", "intraday"), default="close",
        help="close (measured better by ~30%%) or intraday",
    )
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--variants", action="store_true", help="add the four-variant comparison")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON instead")
    args = parser.parse_args(argv)

    if not _gate_on():
        print(
            "exit engine is gated off: set TRADINGAGENTS_ENABLE_EXIT_ENGINE=true "
            "(or the config key enable_exit_engine) to run it."
        )
        return 3
    if args.entry_date is None and args.entry_bars is None:
        print(
            "no entry reference: pass --entry-date YYYY-MM-DD (the day the position was "
            "opened) or --entry-bars N (sessions held). An exit rule without an entry is "
            "not an exit rule."
        )
        return 2

    held, notes = _holdings(args.holdings) if args.holdings else ({}, [])
    tickers = [str(t).strip().upper() for t in args.tickers if str(t).strip()]
    for symbol in held:
        if symbol not in tickers:
            tickers.append(symbol)
    if not tickers:
        print("nothing to evaluate: pass --tickers or --holdings")
        return 2

    config = ExitConfig(
        initial_atr_multiple=args.initial_mult,
        trailing_atr_multiple=args.trailing_mult,
        trend_ma_period=args.trend_ma,
        trend_confirm_bars=args.trend_confirm,
        momentum_exit_threshold=args.momentum_threshold,
        momentum_confirm_bars=args.momentum_confirm,
        max_stalled_bars=args.stall_days,
        enable_stall_exit=bool(args.enable_stall),
        stop_evaluation=args.stop_evaluation,
        cost_bps=args.cost_bps,
    ).resolved()

    benchmark_bars = _bars(args.benchmark, args.bars) if args.benchmark else {}
    benchmark = [float(c) for c in (benchmark_bars.get("closes") or [])] or None

    rows: list[dict] = []
    for symbol in tickers:
        bars = _bars(symbol, args.bars)
        dates = list(bars.get("dates") or [])
        entry_idx = _resolve_entry(dates, args.entry_date, args.entry_bars)
        rows.append(
            _evaluate_name(
                symbol,
                bars,
                config=config,
                entry_idx=entry_idx,
                entry_price=args.entry_price or held.get(symbol),
                benchmark=benchmark,
                risk_gate=args.risk_gate,
                variants=bool(args.variants),
            )
        )
    usable = [r for r in rows if r.get("result")]
    if not usable:
        print("no name had both usable bars and an in-range entry reference; nothing written.")
        return 4

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.json:
        print(json.dumps({"config": config.__dict__, "rows": rows}, indent=2, default=str))
        return 0

    markdown = _markdown(rows, config, notes, stamp)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{REPORT_PREFIX}{stamp}.md"
    path.write_text(markdown, encoding="utf-8")
    print(markdown)
    counts: dict[str, int] = {}
    for row in usable:
        action = str(row["result"]["action"])
        counts[action] = counts.get(action, 0) + 1
    print(f"[exit-engine] {len(usable)}/{len(rows)} named: " + ", ".join(
        f"{action} {counts[action]}" for action in EXIT_ACTIONS if action in counts
    ))
    print(f"[exit-engine] report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
