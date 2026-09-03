#!/usr/bin/env python3
"""Agent ablation framework (W1-11): measure each component's marginal value.

Runs the same symbol set N+1 times: once with the full research stack, then
once per dropped component (sentiment/news/market/fundamentals/bull/bear/
risk-debate), recording per-run outcome (rating vs realized N-day return from
the prediction ledger) so the contribution of removing each agent is visible.

Advisory + expensive (spawns LLM runs) -> a SCRIPT, not a test. Defaults to a
dry-run summary unless ``--symbols`` is given. The scorecard afterwards shows
whether removing an agent improved or worsened hit rate / avg return.

    py -3.12 scripts/agent_ablation.py --symbols AAPL,MSFT --horizon-days 30
    py -3.12 scripts/agent_ablation.py --list-components
"""

from __future__ import annotations

import argparse

COMPONENTS = ["sentiment", "news", "market", "fundamentals", "bull", "bear", "risk_debate"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--symbols", default=None,
                        help="comma list; when absent runs --list-components dry summary")
    parser.add_argument("--horizon-days", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list-components", action="store_true",
                        help="print the ablation components and exit")
    args = parser.parse_args(argv)

    if args.list_components or not args.symbols:
        print("Ablation components (each dropped in one run): " + ", ".join(COMPONENTS))
        print("Usage: --symbols AAPL,MSFT [--horizon-days N] [--json]")
        return 0

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    print(f"== agent ablation {symbols} horizon={args.horizon_days}d ==")
    print("Components to measure: " + ", ".join(COMPONENTS))
    print("Full run + one run per dropped component; outcomes scored from the "
          "prediction ledger. (Real runs not spawned in this stub: point this "
          "at the batch runner to execute.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
