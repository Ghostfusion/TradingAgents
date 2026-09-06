"""After-cost validation gate for the sector rotation screen (P4).

Runs the rotation backtest (monthly-rebalance top-3 SPDR RS/momentum,
`backtest_rotation` in strategies/sector_screener.py) against the equal-weight
sector basket and the SPY benchmark, and reports Sharpe / Calmar / max
drawdown / information ratio with AND without transaction costs via the
repo's evaluate machinery. NOTHING about the screen is "trusted" until the
after-cost numbers here clear — the research (design doc §2) says the edge is
cost-fragile, so the no-cost line is the optimistic ceiling and the cost line
is the honest one.

Usage:
    py -3.12 scripts/validate_sector_rotation.py [--hold 21] [--top 3]
        [--cost-bps 5] [--etfs XLK,XLC,...]
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(
        description="After-cost validation of the sector-rotation screen (P4 gate)."
    )
    ap.add_argument("--hold", type=int, default=21, help="rebalance holding bars (default 21 ~ monthly)")
    ap.add_argument("--top", type=int, default=3, help="number of top sectors held (default 3)")
    ap.add_argument("--cost-bps", type=float, default=5.0, help="per-rebalance cost in bps (default 5)")
    ap.add_argument("--etfs", type=str, default="", help="comma list of SPDR ETFs (default: all 11)")
    args = ap.parse_args()

    try:
        from tradingagents.strategies.sector_rank import SPDR_SECTORS
        from tradingagents.strategies.sector_screener import backtest_rotation
    except Exception as exc:  # noqa: BLE001
        print(f"validate_sector_rotation unavailable: {exc}")
        return 1

    # Fetch the history via the vendor chain (same path the tool uses).
    from tradingagents.agents.utils.analysis_tools import _benchmark_closes, _ohlcv  # noqa: PLC2701

    etfs = [e.strip().upper() for e in args.etfs.split(",") if e.strip()] or list(SPDR_SECTORS)
    closes_map = {}
    for etf in etfs:
        o = _ohlcv(etf)
        if len(o.get("closes") or []) >= 65:
            closes_map[etf] = o["closes"]
    bench = _benchmark_closes()
    if not closes_map or not bench:
        print("unavailable: no SPDR/benchmark history from the vendor chain.")
        return 1

    bt = backtest_rotation(closes_map, bench, hold_bars=args.hold, top_n=args.top,
                           cost_bps=args.cost_bps)
    if not bt["strategy"] or len(bt["strategy"]) < 30:
        print(f"unavailable: backtest too short ({len(bt['strategy'])} bars).")
        return 1

    from tradingagents.strategies import evaluate

    print(f"## Sector rotation validation (monthly-top-{args.top}) — after-cost gate")
    print(f"window: {len(bt['strategy'])} bars | turnover: {bt['turns']:.2f} weight-units "
          f"| cost: {args.cost_bps:g} bps/rebalance")
    header = f"{'variant':<28}{'Sharpe':>8}{'Calmar':>8}{'MaxDD':>9}{'IR vs SPY':>10}"
    print(header)
    print("-" * len(header))
    for label, rets in (("rotation (with costs)", bt["strategy"]), ("equal-weight basket", bt["equal"])):
        rw, r0 = rets, bt["bench"]
        sharpe = evaluate.sharpe(rw)
        ec = evaluate.equity_curve(rw)
        mdd = evaluate.max_drawdown(ec)
        calmar = evaluate.cagr(rw) / mdd if mdd and mdd > 0 else float("nan")
        ir = evaluate.information_ratio(rw, r0) if len(r0) == len(rw) else float("nan")
        print(f"{label:<28}{sharpe:>8.3f}{calmar:>8.3f}{mdd:>9.2%}{ir:>10.3f}")
    # no-cost rotation line (the optimistic ceiling)
    bt0 = backtest_rotation(closes_map, bench, hold_bars=args.hold, top_n=args.top, cost_bps=0.0)
    sharpe0 = evaluate.sharpe(bt0["strategy"])
    mdd0 = evaluate.max_drawdown(evaluate.equity_curve(bt0["strategy"]))
    print(f"{'rotation (no cost)':<28}{sharpe0:>8.3f}{'—':>8}{mdd0:>9.2%}{'—':>10}")
    print("")
    print("Interpretation: if the with-cost rotation line does NOT clear the "
          "equal-weight basket AND SPY on Sharpe/IR, the screen is context-only "
          "(no outperformance claim allowed). This is the gate, not a guarantee.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

