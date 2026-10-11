#!/usr/bin/env python3
"""Strategy-quality report: honest metrics from the paper/realized ledgers.

Item 7 (industry practice): firms periodically grade a strategy on its actual,
post-cost track record before trusting it with more capital. This script reads
the two machine-shaped ledgers the framework already writes and reports the
metrics a firm would ask for:

  - the reflection ledger (strategy_ledger.jsonl) — per-analyst realized alpha
  - the pre-market paper-book ledger (pre_market_ledger.jsonl) — realized
    review returns (CONFIRM/REVISE/REJECT resolved against the open)

It computes, via ``strategies/evaluate.py`` (cost-aware, walk-forward aware):
  - realized returns series from the ledgers
  - net-of-cost cumulative / CAGR / Sharpe (liquid names default 10bps; pass
    ``--illiq`` to scale cost up)
  - max drawdown of the book
  - per-analyst win rate + mean alpha
  - pre-market reviewer win rate (resolved rows)

A scheduled run just wires this into a cron / nightly step; it never trades.

Examples:
    py -3.12 scripts/strategy_quality_report.py
    py -3.12 scripts/strategy_quality_report.py --data-dir ~/.tradingagents
    py -3.12 scripts/strategy_quality_report.py --json

Exit codes: 0 ok.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _default_data_dir() -> str:
    from tradingagents.default_config import DEFAULT_CONFIG

    return DEFAULT_CONFIG.get("data_cache_dir") or os.path.expanduser("~/.tradingagents")


def _load_jsonl(path: str) -> list:
    rows = []
    if not path or not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def _flag(name: str, default: bool = False) -> bool:
    """Read a config gate; a config read must never break the report."""
    try:
        from tradingagents.dataflows.config import get_config

        return bool((get_config() or {}).get(name, default))
    except Exception:  # noqa: BLE001 - a config read must never break the report
        return default


def _score_eval_block(data_dir: str) -> dict:
    """S8 rows: score IC / deciles / coverage / stability over the alpha ledger.

    The panel is the emitted-decision alpha ledger (``alpha_ledger.jsonl``:
    ticker + effective_date + rating); the score is the numeric stance
    (``rating_to_number``). Prices are aligned to the snapshot dates through
    the same private OHLCV chain ``scripts/alpha_health.py`` uses; a name that
    fails to fetch simply drops out (never fabricated). Advisory: any failure
    degrades to ``available=False`` with the reason, never raises.
    """
    rows = _load_jsonl(os.path.join(data_dir, "alpha_ledger.jsonl"))
    if not rows:
        return {
            "available": False,
            "reason": "no alpha_ledger.jsonl with emitted decisions",
            "n": 0,
        }
    from tradingagents.strategies.alpha_health import rating_to_number

    scores_by_date: dict = {}
    for r in rows:
        d = str(r.get("effective_date") or "")
        t = str(r.get("ticker") or "").upper()
        s = rating_to_number(r.get("rating"))
        if d and t and s is not None:
            scores_by_date.setdefault(d, {})[t] = s
    if not scores_by_date:
        return {"available": False, "reason": "no scored rows with a rating", "n": 0}
    try:
        from tradingagents.agents.utils.analysis_tools import _ohlcv
    except Exception as exc:  # noqa: BLE001 - report stays advisory
        return {"available": False, "reason": f"OHLCV chain unavailable: {exc}", "n": 0}
    dates = sorted(scores_by_date)
    prices: dict = {}
    for t in sorted({t for d in dates for t in scores_by_date[d]}):
        try:
            oh = _ohlcv(t, days=320) or {}
        except Exception:  # noqa: BLE001 - one missing name degrades, never fails
            continue
        by_date = dict(zip(oh.get("dates") or [], oh.get("closes") or [], strict=False))
        prices[t] = [by_date.get(d) for d in dates]
    from tradingagents.strategies.alpha_health import score_evaluation_rows

    return score_evaluation_rows(scores_by_date, prices, holding=5)


def _benchmark_arms(closes: list) -> dict:
    """Simple comparator arms on the benchmark's own clock (FinRL-Meta's set).

    ``buy_and_hold`` is the close-to-close series itself; ``momentum_20d`` holds
    the benchmark only after a positive 20-session trailing return (else floored
    at cash, 0%); ``ma_cross_50d`` holds it only while the close sits above its
    own 50-session mean. All three come from the one fetched series - no extra
    vendor call, no second clock.
    """
    bh: list = []
    mom: list = []
    ma: list = []
    for i in range(1, len(closes)):
        r = closes[i] / closes[i - 1] - 1.0
        bh.append(r)
        past = closes[max(0, i - 20):i]
        mom.append(r if len(past) >= 2 and (past[-1] / past[0] - 1.0) > 0 else 0.0)
        window = closes[max(0, i - 50):i + 1]
        ma.append(r if len(window) >= 50 and closes[i] > sum(window) / len(window) else 0.0)
    return {"buy_and_hold": bh, "momentum_20d": mom, "ma_cross_50d": ma}


def _benchmark_surface_block(pm_realized, cost_bps: float) -> dict:
    """The book's own baseline-relative row, loss-side metrics included.

    ALWAYS ON (design_finrl_integration §6.4). With no baseline supplied the
    surface is a named refusal carrying the strategy row - the design row's point
    is that a raw single curve is never the deliverable, so the artifact says so
    instead of printing the curve alone.
    """
    net = [float(v) for v in (pm_realized or []) if v is not None]
    if not net:
        return {"available": False, "reason": "no resolved pre-market rows to measure"}
    try:
        from tradingagents.strategies.benchmark_surface import benchmark_surface

        surface = benchmark_surface(net, None, cost_bps=float(cost_bps))
        surface["available"] = surface.get("unavailable") is None
        return surface
    except Exception as exc:  # noqa: BLE001 - report stays advisory
        return {"available": False, "reason": f"benchmark surface unavailable: {exc}"}


def _cross_sectional_null_block(pm_rows) -> dict:
    """Per-name mean realized PnL -> the cross-sectional null (H3 Stage 3).

    The book's realized rows grouped by ticker: is the mean across names
    distinguishable from zero, or is one name carrying the record? A named
    refusal when no resolved row carries a ticker - never a pass by absence.
    """
    per_name: dict = {}
    for row in pm_rows or []:
        ticker = str(row.get("ticker") or "").strip().upper()
        value = row.get("realized_return")
        if not ticker or value is None:
            continue
        per_name.setdefault(ticker, []).append(float(value))
    if not per_name:
        return {"available": False, "reason": "no resolved rows carry a ticker"}
    try:
        from tradingagents.strategies.null_harness import cross_sectional_null

        read = cross_sectional_null(per_name) or {}
        read["available"] = read.get("verdict") != "unavailable"
        return read
    except Exception as exc:  # noqa: BLE001 - advisory
        return {"available": False, "reason": f"cross-sectional null unavailable: {exc}"}


def _run_economics_block(trees_dir: str) -> dict:
    """The per-run quality x cost join over report trees (Dream-RSI Phase B).

    Reads each tree's ``run_card.json`` beside its ``verify_flags.json`` and joins
    the cap-bound LLM cost to the verifier's own blocks. No writer change, no
    vendor call: both inputs already exist on disk.
    """
    import glob

    from tradingagents.strategies.run_economics import run_economics

    rows: list = []
    for card_path in sorted(glob.glob(os.path.join(trees_dir, "*", "run_card.json"))):
        tree = os.path.dirname(card_path)
        try:
            with open(card_path, encoding="utf-8") as fh:
                card = json.load(fh)
        except (OSError, ValueError):
            continue
        verify = None
        flags_path = os.path.join(tree, "verify_flags.json")
        if os.path.exists(flags_path):
            try:
                with open(flags_path, encoding="utf-8") as fh:
                    verify = json.load(fh)
            except (OSError, ValueError):
                verify = None
        econ = run_economics(card, verify_flags=verify)
        econ["tree"] = os.path.basename(tree)
        rows.append(econ)
    priced = [r for r in rows if r.get("cost_upper_usd") is not None]
    return {
        "available": bool(rows),
        "trees_dir": trees_dir,
        "n_trees": len(rows),
        "n_priced": len(priced),
        "n_passed": sum(1 for r in rows if r.get("quality") is not None),
        "rows": rows,
        "reason": None if rows else f"no run_card.json under {trees_dir}",
        "basis": (
            "per-tree join of run_card.json's cap-bound llm_cost_est against "
            "verify_flags.json's own blocks (Dream-RSI Phase B); the research-depth "
            "knob is not recorded in the run card, so the sweep answers "
            "cost-vs-quality per run and cannot yet attribute it to a depth"
        ),
    }


def build_report(data_dir: str, cost_bps: float = 10.0) -> dict:
    """Collect ledger metrics into a dict; never raises.

    ``cost_bps`` is the one-way cost used to net the realized returns (default
    10bps = liquid; a higher value models an illiquid/impactful book).
    """
    from tradingagents.strategies.evaluate import (
        cagr,
        equity_curve,
        max_drawdown,
        net_returns,
        sharpe,
        total_return,
    )

    out = {"data_dir": data_dir, "ledgers": {}}

    # 1. Reflection ledger (per-analyst realized alpha).
    ref_path = os.path.join(data_dir, "strategy_ledger.jsonl")
    ref_rows = _load_jsonl(ref_path)
    analysts: dict[str, dict] = {}
    for r in ref_rows:
        a = r.get("analyst") or "?"
        delta = r.get("delta_r")
        if delta is None:
            continue
        bucket = analysts.setdefault(a, {"n": 0, "wins": 0, "sum": 0.0})
        bucket["n"] += 1
        bucket["sum"] += float(delta)
        if float(delta) > 0:
            bucket["wins"] += 1
    analyzed = {"rows": len(ref_rows), "by_analyst": {}}
    for a, b in sorted(analysts.items()):
        analyzed["by_analyst"][a] = {
            "n": b["n"],
            "win_rate": round(b["wins"] / b["n"], 3) if b["n"] else None,
            "mean_alpha": round(b["sum"] / b["n"], 4) if b["n"] else None,
        }
    out["ledgers"]["reflection"] = analyzed

    # 2. Pre-market paper-book ledger (realized review returns).
    pm_path = os.path.join(data_dir, "pre_market_ledger.jsonl")
    pm_rows = _load_jsonl(pm_path)
    pm_realized = [float(r["realized_return"]) for r in pm_rows if r.get("realized_return") is not None]
    wins = sum(1 for v in pm_realized if v > 0)
    out["ledgers"]["pre_market"] = {
        "rows": len(pm_rows),
        "resolved": len(pm_realized),
        "win_rate": round(wins / len(pm_realized), 3) if pm_realized else None,
        "avg_realized": round(sum(pm_realized) / len(pm_realized), 5) if pm_realized else None,
        # The per-row series itself. The old --benchmark block read a
        # ``realized`` key that this dict never carried, so its arm series was
        # always empty and the whole hierarchy silently never rendered.
        "realized": [round(float(v), 6) for v in pm_realized],
    }

    # 2b. C1 execution block: arrival-vs-fill slippage + fill-rate (advisory).
    slips = [float(r["slippage_bps"]) for r in pm_rows if r.get("slippage_bps") is not None]
    fills = [r for r in pm_rows if r.get("fill_price") is not None]
    # Implementation-shortfall (TCA) per row: (fill - arrival) + (arrival - decision)
    # proxied over the paper book; decision = prior_close, arrival/fill as stored.
    is_rows = []
    for r in pm_rows:
        if r.get("fill_price") is None or r.get("arrival_price") is None or r.get("prior_close") is None:
            continue
        try:
            from tradingagents.strategies.evaluate import implementation_shortfall

            res = implementation_shortfall(
                float(r["prior_close"]), float(r["arrival_price"]), float(r["fill_price"])
            )
            if res is not None:
                is_rows.append(res["implementation_shortfall_bp"])
        except Exception:  # noqa: BLE001 - one bad row degrades
            continue
    out["execution"] = {
        "rows_with_slippage": len(slips),
        "avg_slippage_bps": round(sum(slips) / len(slips), 2) if slips else None,
        "fill_rate": round(len(fills) / len(pm_rows), 3) if pm_rows else None,
        "avg_is_bp": round(sum(is_rows) / len(is_rows), 2) if is_rows else None,
        "note": "arrival-benchmark slippage: (fill - arrival)/arrival in bps; "
                "avg_is_bp = implementation shortfall (decision->arrival->fill) "
                "in bps; higher = worse execution. None when no measured "
                "arrival/fill (the paper book records the review open as fill).",
    }

    # 2c2. C3 alpha-profile: post-fill drift vs arrival (the "did our fill
    #      leak / did price move against us" test). Uses the paper ledger's own
    #      arrival_price + realized_return proxies (no new vendor). The drift
    #      arithmetic comes from preopen.postfill_drift, which was exported and
    #      tested but reached no report (D3 triage, 2026-10-04).
    fills = [r for r in pm_rows if r.get("arrival_price") and r.get("prior_close")]
    drift_rows = []
    drift_reads = []
    for r in fills:
        arr = float(r["arrival_price"])
        # fill proxy = prior_close (the decision-time close) - C1 semantics
        try:
            from tradingagents.dataflows.preopen import postfill_drift

            read = postfill_drift(arr, float(r["prior_close"]), days_held=1)
        except Exception:  # noqa: BLE001 - one bad row degrades
            read = None
        if read and read.get("drift_pct") is not None:
            drift_rows.append(read["drift_pct"])
            drift_reads.append(read)
    out["alpha_profile"] = {
        "rows": len(drift_rows),
        "avg_postfill_drift_pct": round(sum(drift_rows) / len(drift_rows) * 100, 3) if drift_rows else None,
        "pos_drift_share": round(sum(1 for d in drift_rows if d > 0) / len(drift_rows), 3) if drift_rows else None,
        "note": "post-fill drift: (decision-close - arrival)/arrival over the paper "
                "book. Positive share = fills benign; sustained negative = possible "
                "adverse selection / leak (review execution).",
    }
    # postfill_drift section: the calculator's own per-row reads (days held +
    # the reason a row is unmeasured), so a missing price is named, not zeroed.
    out["postfill_drift"] = {
        "days_held": 1,
        "rows": len(drift_reads),
        "avg_drift_pct": (
            round(sum(d["drift_pct"] for d in drift_reads) / len(drift_reads), 6)
            if drift_reads
            else None
        ),
        "reason": (
            drift_reads[0]["reason"] if drift_reads else "no measured arrival/close rows"
        ),
    }

    # 2d. D1 sleeve attribution: the pre-market ledger carries a per-decision
    #     sleeve tag (value-dip / swing / vcp / momentum / hold) when the run
    #     provided one; group realized returns by sleeve when present.
    sleeves: dict[str, dict] = {}
    for r in pm_rows:
        sv = (r.get("sleeve") or "hold").strip() or "hold"
        rr = r.get("realized_return")
        if rr is None:
            continue
        b = sleeves.setdefault(sv, {"n": 0, "wins": 0, "sum": 0.0})
        b["n"] += 1
        b["sum"] += float(rr)
        if float(rr) > 0:
            b["wins"] += 1
    out["sleeves"] = {
        sv: {
            "n": b["n"],
            "win_rate": round(b["wins"] / b["n"], 3) if b["n"] else None,
            "avg_realized": round(b["sum"] / b["n"], 5) if b["n"] else None,
        }
        for sv, b in sorted(sleeves.items())
    }

    # 3. Whole-book net-of-cost metrics from the realized returns (pre-market
    #    book as the canonical series; flat 10bps default, scaled by --illiq).
    out["metrics"] = {"available": bool(pm_realized), "cost_bps": cost_bps}
    if pm_realized:
        # W1-10 regime-conditioned performance (strategies/regime_performance.py):
        # per-regime hit rate + avg return from the resolved ledger rows (a row
        # with realized_return carries an implicit outcome; the regime comes
        # from a `regime` / `sleeve` field when the driver stamps it, else the
        # honest "unknown" bucket - never fabricated).
        try:
            from tradingagents.strategies.regime_performance import (
                regime_conditioned_performance,
            )

            out["regime"] = regime_conditioned_performance(
                [
                    {
                        "regime": str(_r.get("regime") or _r.get("sleeve") or "unknown"),
                        "outcome": {
                            "hit": (_r.get("realized_return") or 0.0) > 0,
                            "return_pct": (
                                round(float(_r.get("realized_return")) * 100.0, 4)
                                if _r.get("realized_return") is not None else None
                            ),
                        },
                    }
                    for _r in pm_rows
                    if _r.get("realized_return") is not None
                ],
                regime_field="regime",
            )
        except Exception:  # noqa: BLE001 - advisory
            out["regime"] = None
        net = net_returns(pm_realized, cost_bps=cost_bps)
        eq = equity_curve(net)
        out["metrics"].update(
            {
                "total_return": round(total_return(net), 4),
                "cagr": round(cagr(net), 4) if len(net) else None,
                "sharpe": round(sharpe(net), 3) if len(net) >= 2 else None,
                "max_drawdown": round(max_drawdown(eq), 4) if eq else None,
            }
        )
        # Qlib with/without-cost report table (design_qlib_integration.md
        # §3.2, signal_analysis.with_without_cost_table): the same metrics on
        # the RAW series vs the net-of-cost series, so the cost drag is
        # visible side by side.
        raw = [float(v) for v in pm_realized if v is not None]
        try:
            from tradingagents.strategies.signal_analysis import (
                with_without_cost_table,
            )

            wwc = with_without_cost_table(raw, cost_bps=cost_bps)
            if wwc:
                out["metrics"]["with_without_cost"] = {
                    "without_cost": wwc["without_cost"],
                    "with_cost": wwc["with_cost"],
                    "cost_bps": cost_bps,
                }
        except Exception:  # noqa: BLE001 - advisory table degrades
            out["metrics"]["with_without_cost"] = None
        # D2 alpha-decay monitor: rolling 4-week hit rate / sharpe vs the
        # full-history baseline. DRIFT when the rolling measure trails the
        # baseline for 2 consecutive periods (config `drift_periods`).
        try:
            hist = [float(v) for v in pm_realized if v is not None]
            if len(hist) >= 12:
                n = max(5, min(20, len(hist) // 4))
                recent = hist[-n:]
                base_win = sum(1 for v in hist if v > 0) / len(hist)
                recent_win = sum(1 for v in recent if v > 0) / len(recent)
                base_sharpe = sharpe(hist) if len(hist) >= 2 else None
                recent_sharpe = sharpe(recent) if len(recent) >= 2 else None
                threshold = float(os.environ.get("TRADINGAGENTS_DRIFT_THRESHOLD", "0.15"))
                drift_win = (recent_win < base_win - threshold) if base_win else False
                drift_sharpe = (
                    recent_sharpe is not None
                    and base_sharpe is not None
                    and recent_sharpe < base_sharpe - 0.3
                )
                out["drift"] = {
                    "window": n,
                    "baseline_win_rate": round(base_win, 3),
                    "recent_win_rate": round(recent_win, 3),
                    "baseline_sharpe": round(base_sharpe, 3) if base_sharpe is not None else None,
                    "recent_sharpe": round(recent_sharpe, 3) if recent_sharpe is not None else None,
                    "drift_win_rate": bool(drift_win),
                    "drift_sharpe": bool(drift_sharpe),
                    "review_hint": "DRIFT detected" if (drift_win or drift_sharpe) else "stable",
                }
        except Exception:  # noqa: BLE001 - drift monitor is advisory
            out["drift"] = None
    # S8 score-evaluation rows (default off): IC / deciles / coverage /
    # stability over the emitted-decision panel. Inputs to DSR/PBO, never a
    # standalone verdict; only present when the gate is on so the legacy
    # report output stays unchanged.
    if _flag("enable_score_eval_rows"):
        out["score_eval"] = _score_eval_block(data_dir)
    # 4. Baseline-relative surface (FinRL 8 / design_finrl_integration §6.4): the
    #    loss-side four (mean / variance / CVaR / P(return >= 0)) this report
    #    never carried, plus the named refusal when no baseline is supplied.
    out["benchmark_surface"] = _benchmark_surface_block(pm_realized, cost_bps)
    # 4b. The cross-sectional null over REAL per-name PnL (H3 Stage 3).
    out["cross_sectional_null"] = _cross_sectional_null_block(pm_rows)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=None, help="ledger dir (default: config data_cache_dir)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--illiq", action="store_true",
                        help="scale net cost up to 50bps (illiquid / impact-heavy book)")
    parser.add_argument("--benchmark", default=None,
                        help="benchmark ticker (e.g. SPY): renders the benchmark's own "
                             "arms (buy&hold / momentum_20d / ma_cross_50d) on its own "
                             "session clock - see the clock note, it is not aligned to "
                             "the book's per-review series")
    parser.add_argument("--trees", default=None,
                        help="report-trees dir: joins each tree's run_card.json cost "
                             "(a cap bound) to its verify_flags.json quality - the "
                             "per-run 'was it worth it' read (Dream-RSI Phase B)")
    args = parser.parse_args(argv)

    data_dir = args.data_dir or _default_data_dir()
    # Ensure the data dir is absolute so ledger paths resolve regardless of CWD.
    data_dir = os.path.abspath(os.path.expanduser(data_dir))
    cost_bps = 50.0 if args.illiq else 10.0
    report = build_report(data_dir, cost_bps=cost_bps)

    if args.trees:
        report["run_economics"] = _run_economics_block(args.trees)

    # Benchmark context (advisory): the benchmark's OWN arms on the benchmark's own
    # clock. Deliberately NOT mixed with the book: the book's realized series is
    # one observation per resolved review and the benchmark's is one per session,
    # so a "common tail" of the two would be a clock mismatch dressed up as a
    # comparison. The ledger records each row's own trade/resolved dates, so a
    # matched-window read is derivable later - a named gap, not a silent one.
    if args.benchmark:
        try:
            from scripts.backtest_strategy import fetch_bars
            from tradingagents.strategies.benchmark_surface import benchmark_rows

            bars = fetch_bars(args.benchmark, 500)
            closes = [b.close for b in (bars or [])]
            if len(closes) > 1:
                arms = _benchmark_arms(closes)
                block = benchmark_rows(
                    arms["buy_and_hold"],
                    {k: v for k, v in arms.items() if k != "buy_and_hold"},
                )
                block["ticker"] = args.benchmark.upper()
                block["clock"] = (
                    "the benchmark's own session clock; the book's series is one "
                    "observation per resolved review and is not aligned to it here"
                )
                report["benchmark_arms"] = block
            else:
                report["benchmark_arms"] = {"error": f"no bars for {args.benchmark}"}
        except Exception as exc:  # noqa: BLE001 - benchmark is advisory
            report["benchmark_arms"] = {"error": str(exc)}

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    lines = ["# Strategy Quality Report", f"\nData dir: `{data_dir}`", ""]
    ref = report["ledgers"]["reflection"]
    lines.append(f"## Reflection ledger ({ref['rows']} realized outcomes)")
    for a, s in (ref.get("by_analyst") or {}).items():
        lines.append(f"- {a}: n={s['n']} win_rate={s['win_rate']} mean_alpha={s['mean_alpha']}")
    pm = report["ledgers"]["pre_market"]
    lines.append(f"\n## Pre-market paper-book ({pm['resolved']} resolved of {pm['rows']})")
    lines.append(f"- win_rate={pm['win_rate']} avg_realized={pm['avg_realized']}")
    m = report["metrics"]
    if m.get("available"):
        lines.append(f"\n## Book metrics (net of {m.get('cost_bps', 10.0):g}bps)")
        lines.append(
            f"- total_return={m['total_return']} sharpe={m['sharpe']} "
            f"max_drawdown={m['max_drawdown']}"
        )
    else:
        lines.append("\nNo realized pre-market rows yet — run pre-market reviews to populate.")
    se = report.get("score_eval")
    if se is not None:
        lines.append("\n## Score evaluation rows (S8)")
        if se.get("available") is False:
            lines.append(f"- unavailable: {se.get('reason')} (n={se.get('n', 0)})")
        else:
            ic = se.get("ic") or {}
            dec = se.get("deciles") or {}
            cov = se.get("coverage") or {}
            stab = se.get("stability") or {}
            lines.append(
                f"- rank IC: n={ic.get('n')} holding={se.get('holding')}d "
                f"mean={ic.get('mean_rank_ic')} ic_ir={ic.get('ic_ir')}"
                + ("" if ic.get("available") else f" (unavailable: {ic.get('reason')})")
            )
            lines.append(
                f"- deciles: n={dec.get('n')} holding={se.get('holding')}d "
                f"monotonicity={dec.get('monotonicity')} "
                f"buckets_filled={dec.get('buckets_filled')}"
                + ("" if dec.get("available") else f" (unavailable: {dec.get('reason')})")
            )
            lines.append(
                f"- coverage: n={cov.get('n')} scored/universe="
                f"{cov.get('scored')}/{cov.get('universe')} ratio={cov.get('ratio')}"
                + ("" if cov.get("available") else f" (unavailable: {cov.get('reason')})")
            )
            lines.append(
                f"- stability: n={stab.get('n')} mean_rank_autocorr="
                f"{stab.get('mean_rank_autocorr')}"
                + ("" if stab.get("available") else f" (unavailable: {stab.get('reason')})")
            )
            lines.append(f"- {se.get('basis')}")
    surface = report.get("benchmark_surface")
    if surface is not None:
        lines.append("\n## Baseline-relative surface (FinRL 8; loss-side rows)")
        if surface.get("available") is False:
            lines.append(f"- unavailable: {surface.get('reason') or surface.get('unavailable')}")
        else:
            for row in surface.get("rows") or []:
                if row["name"] == "strategy":
                    # The six classic columns are already printed above; print the
                    # four this report never carried, and no duplicate of them.
                    lines.append(
                        f"- strategy (loss side): mean={row['mean']} variance={row['variance']} "
                        f"cvar={row['cvar']} P(return>=0)={row['prob_ge_threshold']} "
                        f"(cost {row['cost_bps']:g}bps)"
                    )
                else:
                    lines.append(
                        f"- {row['name']}: n={row['n']} mean={row['mean']} variance={row['variance']} "
                        f"cvar={row['cvar']} P(return>=0)={row['prob_ge_threshold']} "
                        f"sharpe={row['sharpe']} maxdd={row['max_drawdown']} calmar={row['calmar']}"
                    )
            lines.append(f"- {surface.get('reason') or surface.get('basis')}")
    cs = report.get("cross_sectional_null")
    if cs is not None:
        lines.append("\n## Cross-sectional null over per-name PnL (H3 Stage 3)")
        if cs.get("available") is False:
            lines.append(f"- unavailable: {cs.get('reason') or cs.get('unavailable')}")
        else:
            st = cs.get("sign_test") or {}
            lines.append(
                f"- n_names={cs.get('n_names')} mean={cs.get('mean')} sd={cs.get('sd')} "
                f"t={cs.get('t')} df={cs.get('df')} p={cs.get('p_value')} -> {cs.get('verdict')}"
            )
            lines.append(
                f"- sign test: {st.get('n_positive')} positive / {st.get('n_negative')} "
                f"negative / {st.get('n_tied')} tied, p={st.get('p_value')}"
            )
            lines.append(f"- {cs.get('basis')}")
    harms = report.get("benchmark_arms")
    if harms is not None:
        lines.append(f"\n## Benchmark arms ({harms.get('ticker') or args.benchmark})")
        if harms.get("error"):
            lines.append(f"- error: {harms['error']}")
        else:
            for row in harms.get("rows") or []:
                lines.append(
                    f"- {row['name']}: n={row['n']} total_return={row['total_return']} "
                    f"cagr={row['cagr']} ann_vol={row['ann_vol']} sharpe={row['sharpe']} "
                    f"maxdd={row['max_drawdown']} calmar={row['calmar']} cvar={row['cvar']} "
                    f"P(return>=0)={row['prob_ge_threshold']}"
                )
            lines.append(f"- clock: {harms.get('clock')}")
    econ = report.get("run_economics")
    if econ is not None:
        lines.append("\n## Run economics (cap-bound cost vs verifier quality, Phase B)")
        if not econ.get("available"):
            lines.append(f"- unavailable: {econ.get('reason')}")
        else:
            for row in econ.get("rows") or []:
                quality = row.get("quality") or {}
                lines.append(
                    f"- {row.get('tree')}: {row.get('ticker')} "
                    f"cost<={row.get('cost_upper_usd')} "
                    f"flags={quality.get('flags_count')} {quality.get('flagged_stems')} "
                    f"flags_per_usd={row.get('flags_per_usd')}"
                )
            lines.append(f"- priced trees: {econ.get('n_priced')} of {econ.get('n_trees')}, "
                         f"with a verifier run: {econ.get('n_passed')}")
            lines.append(f"- {econ.get('basis')}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
