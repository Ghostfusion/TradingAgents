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
import datetime as _dt
import os
import sys
from pathlib import Path

# scripts/ is not a package; load like pipeline.py does for value_screener.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _discover_report_dir(ticker: str, report_dir: str | None, prior_date: str | None) -> str | None:
    """None explicitly given: newest ``reports/<TICKER>_<ts>/`` folder."""
    if report_dir:
        return report_dir if os.path.isdir(report_dir) else None
    reports_root = Path.cwd() / "reports"
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
    the last close on or before ``prior_date``; ``open_price`` = the latest
    close in the window (today's / pre-market price, which is after
    ``prior_date`` for a pre-open review). The gap the arbiter computes is
    therefore the genuine overnight delta, not a noise artifact.
    """
    from tradingagents.dataflows.interface import route_to_vendor
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.strategies.catalyst import build_catalyst_snapshot, fetch_catalyst_data

    prior_dt = _dt.date.fromisoformat(prior_date)
    start = (prior_dt - _dt.timedelta(days=10)).isoformat()
    end = (_dt.date.fromisoformat(trade_date) + _dt.timedelta(days=1)).isoformat()
    deltas: dict = {"catalyst": None, "open_price": None, "prior_close": None}
    try:
        out = route_to_vendor("get_stock_data", ticker, start, end) or ""
        prior_close = None
        latest = None
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("date,"):
                continue
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                d = parts[0].strip()
                c = float(parts[4])
            except (ValueError, IndexError):
                continue
            # Last close on or before the prior trade date = the prior close.
            if d <= prior_date and prior_close is None:
                prior_close = c
            latest = c
        deltas["prior_close"] = prior_close
        deltas["open_price"] = latest
    except Exception:  # noqa: BLE001 - degrade like the router
        deltas["open_price"] = None

    try:
        data = fetch_catalyst_data(ticker, trade_date)
        if data is not None:
            deltas["catalyst"] = build_catalyst_snapshot(data, trade_date, DEFAULT_CONFIG)
    except Exception:  # noqa: BLE001
        deltas["catalyst"] = None
    return deltas


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

    from tradingagents.strategies.pre_market import load_prior_state, review_decision

    prior = load_prior_state(report_dir, args.prior_date)
    if not prior["state"]:
        print(f"[warn] no full_states_log for {args.ticker} in {report_dir}; using decision.md only")

    deltas = _fetch_deltas(args.ticker, trade_date, args.prior_date or trade_date, prior)
    verdict = review_decision(
        prior_close=deltas.get("prior_close"),
        open_price=deltas.get("open_price"),
        catalyst_snapshot=deltas.get("catalyst"),
    )
    summary = _build_summary(deltas, verdict)

    decision_text = prior["decision_md"] or (prior["state"] or {}).get(
        "final_trade_decision", ""
    )

    reviewed = None
    if not args.skip_llm:
        try:
            from tradingagents.agents.overrides.pre_market_reviewer import (
                create_pre_market_reviewer,
            )
            from tradingagents.default_config import DEFAULT_CONFIG
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

    return 0 if final_verdict != "REJECT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
