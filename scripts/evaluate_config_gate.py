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
                 ledger_dir: str | None = None, round_trip_cost: float = 0.0) -> dict:
    """Walk-forward over the series; flag when the best-trial strategy tanks OOS.

    ``trials`` is only the *fallback* trial count. With ``enable_trial_ledger``
    on (default off) the deflation stops trusting it: N and V are read back from
    the trial ledger's own rows (``trial_ledger.trial_stats``), so the published
    number is deflated against the **recorded** search rather than an asserted
    one, and the record names which it used. Off, the caller's count is all there
    is and the record says so. The deflation's known unit limitation and the
    scale-correct alternative are documented at ``evaluate.deflated_sharpe`` and
    ``evaluate.deflated_sharpe_ratio``.

    ``min_track_record`` adds E2: the length the record would need before the
    measured Sharpe could be called above zero at 95% confidence, given its own
    skewness and kurtosis - per-observation units (the paper's own convention),
    beside the annualized Sharpe the other numbers are built from.

    ``round_trip_cost`` adds E5: the gross-edge precondition. The gate's
    significance is taken on the raw return series, which is a GROSS series - a
    deflated Sharpe can pass on an edge that a single round trip would consume.
    When ``round_trip_cost`` is > 0 the verdict is refused (``ok`` None,
    ``reason`` "gross edge below round-trip cost") if the series' mean
    per-period return does not clear it. ``gross_edge`` and ``cost_floor`` are
    reported either way, so the grossness of the test is never silent, and the
    default 0.0 is the off state: a caller that supplies no cost keeps the
    previous verdict exactly.
    """
    from tradingagents.strategies.evaluate import (
        deflated_sharpe,
        deflated_sharpe_ratio,
        min_track_record_length,
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
    mintrl = min_track_record_length(returns)
    ok = (not ow) and (is_deflated > 0)
    reason = "PBO" if ow else ("deflated_sharpe<=0" if is_deflated <= 0 else "pass")
    # E5: a significance test on a GROSS series is not a tradability test. When
    # a round-trip cost is supplied, refuse the verdict outright if the series'
    # mean per-period return does not clear it - a strategy whose gross edge
    # sits under its own trading cost cannot be significant *after* trading,
    # whatever the deflated Sharpe of the gross series says.
    gross_edge = (sum(returns) / len(returns)) if returns else None
    cost_floor_hit = (
        round_trip_cost > 0.0 and gross_edge is not None
        and gross_edge < float(round_trip_cost)
    )
    if cost_floor_hit:
        ok, reason = None, "gross edge below round-trip cost"
    return {
        "ok": ok,
        "reason": reason,
        "gross_edge": None if gross_edge is None else round(gross_edge, 6),
        "cost_floor": float(round_trip_cost),
        "in_best": round(max(in_sample), 3) if in_sample else None,
        "oos_best": round(oos_best, 3) if oos_best else None,
        "deflated_sharpe": round(is_deflated, 3),
        "deflated_sharpe_ratio": None if dsr is None else round(dsr, 4),
        "min_track_record": mintrl,
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
    parser.add_argument(
        "--round-trip-cost", type=float, default=0.0,
        help="E5: refuse the verdict when the mean per-period return is below "
             "this round-trip cost (default 0.0 = gross-significance test only)",
    )
    args = parser.parse_args(argv)
    try:
        returns = [float(x) for x in args.returns.split(",") if x.strip()]
    except ValueError as exc:
        print(f"bad returns list: {exc}")
        return 2
    band = gate_verdict(returns, train_len=args.train, test_len=args.test,
                        round_trip_cost=args.round_trip_cost)
    print("verdict:", band.get("ok"))
    print("reason:", band.get("reason"))
    print("gross_edge:", band.get("gross_edge"))
    print("cost_floor:", band.get("cost_floor"))
    print("in_sample_best:", band.get("in_best"))
    print("oos_best:", band.get("oos_best"))
    print("deflated_sharpe:", band.get("deflated_sharpe"))
    print("deflated_sharpe_ratio:", band.get("deflated_sharpe_ratio"))
    mintrl = band.get("min_track_record")
    print("min_track_record:", None if mintrl is None else round(mintrl["min_track_record"], 1))
    print("min_track_record_years:",
          None if mintrl is None else round(mintrl["min_track_record_years"], 3))
    print("n_trials:", band.get("n_trials"))
    print("dispersion:", band.get("dispersion"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
