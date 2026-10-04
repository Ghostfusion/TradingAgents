"""G5 - threshold tuning gate: walk-forward + PBO before shipping a default.

Takes a strategy return series, splits into rolling train/test windows, uses
walk-forward splits from ``strategies.evaluate``, and reports whether the
best in-sample trial survives out-of-sample (deflated/PBO check).

With ``enable_trial_ledger`` on (default off) the deflation reads N and V back
from the trial ledger's recorded rows instead of an asserted trial count, and
the verdict names which it used; the scale-correct Deflated Sharpe Ratio
(Bailey & Lopez de Prado Eq. 2, a probability) rides beside the legacy deflated
number.

Usage:
    python scripts/evaluate_config_gate.py --returns 0.01,-0.02,...

Outputs a verdict and a non-zero hint (still returns 0).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _trials_and_dispersion(trials: int, ledger_dir: str | None) -> tuple[int, float | None, str]:
    """``(N, V, provenance)`` for the deflation: the ledger's when it is on.

    Provenance is ``"measured"`` when the ledger supplied both N and V (the
    rows are the recorded search), ``"caller (enable_trial_ledger off)"`` when
    the gate is off, and ``"caller (ledger unavailable: ...)"`` when the gate is
    on but the ledger holds fewer than two usable Sharpe rows - an unmeasured
    dispersion is never read as zero.
    """
    from tradingagents.strategies.trial_ledger import gate_on, trial_stats

    if not gate_on():
        return int(trials), None, "caller (enable_trial_ledger off)"
    stats = trial_stats(results_dir=ledger_dir)
    if stats.get("unavailable") is not None:
        return int(trials), None, f"caller (ledger unavailable: {stats['unavailable']})"
    return int(stats["n_trials"]), stats.get("sharpe_dispersion"), "measured"


def gate_verdict(returns: list, train_len: int = 60, test_len: int = 20, trials: int = 20,
                 ledger_dir: str | None = None) -> dict:
    """Walk-forward over the series; flag when the best-trial strategy tanks OOS.

    ``trials`` is only the *fallback* trial count. With ``enable_trial_ledger``
    on (default off) the deflation stops trusting it: N and V are read back from
    the trial ledger's own rows (``trial_ledger.trial_stats``), so the published
    number is deflated against the **recorded** search rather than an asserted
    one, and the record names which it used. Off, the caller's count is all there
    is and the record says so. The deflation's known unit limitation and the
    scale-correct alternative are documented at ``evaluate.deflated_sharpe`` and
    ``evaluate.deflated_sharpe_ratio``.
    """
    from tradingagents.strategies.evaluate import (
        deflated_sharpe,
        deflated_sharpe_ratio,
        pbo_flag,
        sharpe,
        walk_forward_splits,
    )

    if len(returns) < train_len + test_len + 1:
        return {"ok": None, "reason": "too few samples for walk-forward", "oos_best": None}

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
    n_trials, dispersion, provenance = _trials_and_dispersion(trials, ledger_dir)
    is_deflated = deflated_sharpe(returns, n_trials=n_trials, sharpe_dispersion=dispersion)
    dsr = deflated_sharpe_ratio(returns, n_trials=n_trials, sharpe_dispersion=dispersion)
    ok = (not ow) and (is_deflated > 0)
    return {
        "ok": ok,
        "reason": "PBO" if ow else ("deflated_sharpe<=0" if is_deflated <= 0 else "pass"),
        "in_best": round(max(in_sample), 3) if in_sample else None,
        "oos_best": round(oos_best, 3) if oos_best else None,
        "deflated_sharpe": round(is_deflated, 3),
        "deflated_sharpe_ratio": None if dsr is None else round(dsr, 4),
        "n_trials": n_trials,
        "dispersion": provenance,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--returns", required=True, help="comma-separated strategy returns (floats)"
    )
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
    print("deflated_sharpe_ratio:", band.get("deflated_sharpe_ratio"))
    print("n_trials:", band.get("n_trials"))
    print("dispersion:", band.get("dispersion"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
