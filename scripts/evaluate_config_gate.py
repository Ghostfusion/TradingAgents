"""G5 - threshold tuning gate: walk-forward + PBO before shipping a default.

Takes a strategy return series, splits into rolling train/test windows, uses
walk-forward splits from ``strategies.evaluate``, and reports whether the
best in-sample trial survives out-of-sample (deflated/PBO check).

Usage:
    python scripts/evaluate_config_gate.py --returns 0.01,-0.02,...

Outputs a verdict and a non-zero hint (still returns 0).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def gate_verdict(returns: list, train_len: int = 60, test_len: int = 20,
                 trials: int = 20) -> dict:
    """Walk-forward over the series; flag when the best-trial strategy tanks OOS."""
    from tradingagents.strategies.evaluate import (
        sharpe, deflated_sharpe, walk_forward_splits, pbo_flag,
    )

    if len(returns) < train_len + test_len + 1:
        return {"ok": None, "reason": "too few samples for walk-forward",
                "oos_best": None}

    in_sample = []
    out_of_sample = []
    for train, test in walk_forward_splits(returns, train_len, test_len):
        if not train or not test:
            continue
        in_sample.append(sharpe(train))
        out_of_sample.append(sharpe(test))

    if not in_sample:
        return {"ok": None, "reason": "no valid walk-forward splits"}

    oos_best = max(out_of_sample) if out_of_sample else None
    ow = pbo_flag(in_sample, out_of_sample, threshold=-0.1)
    is_deflated = deflated_sharpe(returns, n_trials=trials)
    ok = (not ow) and (is_deflated > 0)
    return {
        "ok": ok,
        "reason": "PBO" if ow else ("deflated_sharpe<=0" if is_deflated <= 0 else "pass"),
        "in_best": round(max(in_sample), 3) if in_sample else None,
        "oos_best": round(oos_best, 3) if oos_best else None,
        "deflated_sharpe": round(is_deflated, 3),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--returns", required=True,
                        help="comma-separated strategy returns (floats)")
    parser.add_argument("--train", type=int, default=60)
    parser.add_argument("--test", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        returns = [float(x) for x in args.returns.split(",") if x.strip()]
    except ValueError as exc:
        print(f"bad returns list: {exc}")
        return 2
    band = gate_verdict(returns, train_len=args.train, test_len=args.test)
    print("verdict:", band.get("ok"))
    print("reason:", band.get("reason"))
    print("in_sample_best:", band.get("in_best"))
    print("oos_best:", band.get("oos_best"))
    print("deflated_sharpe:", band.get("deflated_sharpe"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())