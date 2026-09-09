"""Per-rule forward-return evaluation CLI (advisory).

Evaluates configured indicators (RSI>70, MACD-hist rising, Bollinger
extension, high-vol, above-VWMA, ...) over a ticker's close series and
prints a per-rule table of forward 1/5/10/20-day returns, hit rate, average /
median, max-adverse/max-favourable, annualized Sharpe and profit factor. A
rule with fewer than 30 events renders INSUFFICIENT - never a noise table
(SKHY 2026-09-09 review-loop: indicator set must be measured, not assumed).

Usage:
    py -3.12 scripts/rule_eval.py --ticker SKHY
    py -3.12 scripts/rule_eval.py --ticker AMZN --json
    py -3.12 scripts/rule_eval.py --ticker NVDA --rules rsi_overbought,macd_hist_rising

Exit code 0 always (advisory; never gates a decision).
"""

from __future__ import annotations

import argparse
import json
import sys

from tradingagents.strategies.rule_eval import DEFAULT_RULES, evaluate_rule


def _closes_for(ticker: str) -> dict:
    """Verified close series via the same date-aware source the snapshot uses."""
    from datetime import date as _date

    from tradingagents.dataflows.stockstats_utils import load_ohlcv

    df = load_ohlcv(ticker, _date.today().isoformat())
    if df is None or df.empty:
        return {"closes": [], "highs": [], "lows": [], "volumes": []}
    cols = {c.lower(): c for c in df.columns}
    return {
        "closes": [float(x) for x in df[cols["close"]].tolist() if x == x],
        "highs": [float(x) for x in df[cols["high"]].tolist() if x == x],
        "lows": [float(x) for x in df[cols["low"]].tolist() if x == x],
        "volumes": [float(x) for x in df[cols.get("volume", cols["close"])].tolist() if x == x],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="SKHY", help="Ticker symbol (default SKHY).")
    parser.add_argument(
        "--rules",
        default=",".join(DEFAULT_RULES),
        help="Comma list of rule names in DEFAULT_RULES (default: all).",
    )
    parser.add_argument("--json", action="store_true", help="Prints machine-readable JSON.")
    args = parser.parse_args()

    data = _closes_for(args.ticker)
    if len(data["closes"]) < 60:
        print(f"rule eval unavailable for {args.ticker}: need >= 60 closes (got {len(data['closes'])}).",
              file=sys.stderr)
        return 1

    chosen = [n.strip() for n in args.rules.split(",") if n.strip()]
    results = []
    for name in chosen:
        rfn = DEFAULT_RULES.get(name)
        if rfn is None:
            print(f"unknown rule: {name} (available: {', '.join(DEFAULT_RULES)}", file=sys.stderr)
            continue
        results.append(evaluate_rule(
            data["closes"], data["highs"], data["lows"], data["volumes"], rfn, label=name,
        ))

    if args.json:
        print(json.dumps({"ticker": args.ticker, "rules": results}, indent=2))
        return 0

    print(f"=== rule evaluation: {args.ticker} ({len(data['closes'])} bars) ===")
    for r in results:
        if r["verdict"] == "INSUFFICIENT":
            print(f"  {r['label']:<22} INSUFFICIENT (n={r['n_events']} < {r['min_events']})")
            continue
        print(f"  {r['label']:<22} PREDICTIVE n={r['n_events']}")
        for h in sorted(r["stats"]):
            s = r["stats"][h]
            if s["avg"] is None:
                print(f"      fwd{h:<3} n=0")
                continue
            pf = "inf" if s["profit_factor"] == float("inf") else (
                f"{s['profit_factor']:.2f}" if s["profit_factor"] is not None else "n/a")
            sh = f"{s['sharpe']:.2f}" if s["sharpe"] is not None else "n/a"
            print(
                f"      fwd{h:<3} avg={s['avg']:+.2%} med={s['median']:+.2%} hit={s['hit']:.0%} "
                f"MAE={s['max_adverse']:+.2%} MFE={s['max_favourable']:+.2%} "
                f"sharpe={sh} PF={pf}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
