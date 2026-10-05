#!/usr/bin/env python3
"""Run the synthetic-null workflow-falsification harness offline (plan H3).

**Offline by construction, and that is a requirement rather than a preference.**
The honesty theme's ground rule 8 forbids the decision path
(``prepare_initial_state``, ``finalize_run``, any agent tool) from calling any of
this: ``5 x 1000`` full-pipeline replays are prohibitive in-run and fine offline.
So the one place a null band can honestly be built is here - a script an
operator runs - and this script is also the first caller H3's harness had, which
is what lets it satisfy the repo's public-function wiring rule.

It adds no arithmetic. Stage 1 replays the workflow's walk-forward winner under
each of the five reference classes and reports the environment's empirical
``(1-alpha)`` quantile; Stage 2 reads ``Delta_Z`` and ``K_eff`` from the
retained candidate matrix:

  * the generators and the band - ``strategies/null_harness.py``
  * the HAC z, ``Delta_Z`` and ``K_eff`` - ``strategies/evaluate.py``
  * the recorded search size - ``strategies/trial_ledger.py`` (H1), when a
    ``--ledger-dir`` is supplied (the ledger is what makes retaining the
    candidate matrix possible)

The demo pipelines are the module's own: ``reference_pipeline`` is honest
(out-of-sample) and ``leaky_pipeline`` selects and reports in-sample. On a null
the first sits inside the band and the second exceeds it - the failing-first
proof, printed on every run.

Usage::

    py -3.12 scripts/null_harness.py
    py -3.12 scripts/null_harness.py --reference-class garch11 --replications 2000
    py -3.12 scripts/null_harness.py --json
    py -3.12 scripts/null_harness.py --ledger-dir ~/.tradingagents/logs

Exit codes: 0 ran with a usable band for every class, 2 a class was unknown or
its band was unusable.
"""

from __future__ import annotations

import argparse
import json
import sys

from tradingagents.strategies import null_harness as nh
from tradingagents.strategies.evaluate import inflation_diagnostics


def _run_one(reference_class: str, replications: int, alpha: float,
             n_obs: int, seed: int, samples: int = 200) -> dict:
    """One reference class: the null band, the outside-band rates, Stage 2."""
    band = nh.run_null_harness(
        nh.reference_pipeline, reference_class=reference_class,
        n_replications=replications, alpha=alpha, n_obs=n_obs, seed=seed)
    quantile = band["quantile"]
    clean_out = leak_out = 0
    example_clean: dict | None = None
    example_leak: dict | None = None
    deltas: list[float] = []
    k_effs: list[float] = []
    for i in range(samples):
        data = nh.generate_null(reference_class, n_obs, seed=seed + 100_000 + i)
        if quantile is not None:
            clean_stat = nh.reference_pipeline(data)
            leak_stat = nh.leaky_pipeline(data)
            clean_out += clean_stat > quantile
            leak_out += leak_stat > quantile
            if i == 0:
                example_clean = nh.falsify_workflow(clean_stat, band)
                example_leak = nh.falsify_workflow(leak_stat, band)
        is_matrix, wf_matrix = nh.candidate_matrix(data)
        diag = inflation_diagnostics(is_matrix, wf_matrix)
        if diag["delta_z"] is not None:
            deltas.append(diag["delta_z"])
        if diag["k_eff"] is not None:
            k_effs.append(diag["k_eff"])
    return {
        "band": band,
        "samples": samples,
        "clean_outside_rate": clean_out / samples if quantile is not None else None,
        "leak_outside_rate": leak_out / samples if quantile is not None else None,
        "example_clean": example_clean,
        "example_leak": example_leak,
        "mean_delta_z": sum(deltas) / len(deltas) if deltas else None,
        "mean_k_eff": sum(k_effs) / len(k_effs) if k_effs else None,
    }


def _ledger_size(ledger_dir: str | None) -> dict | None:
    if not ledger_dir:
        return None
    from tradingagents.strategies.trial_ledger import trial_stats

    return trial_stats(results_dir=ledger_dir)


def _print_text(report: dict) -> None:
    fw = nh.FAMILYWISE_FALSE_POSITIVE
    print("H3 synthetic-null workflow falsification "
          f"(familywise false positive: {fw[1]:.1%} at K=1, {fw[50]:.1%} at K=50)")
    print("A null band is what noise alone produces; a winner above it is a "
          "false positive, not skill.\n")
    for name, row in report["classes"].items():
        band = row["band"]
        quantile = band["quantile"]
        print(f"[{name}]  band {quantile if quantile is None else f'{quantile:.4f}'} "
              f"over {band['n_usable']}/{band['n_replications']} replays")
        cr, lr = row["clean_outside_rate"], row["leak_outside_rate"]
        print(f"    clean pipeline  -> outside-band rate "
              f"{'n/a' if cr is None else f'{cr:.1%}'}  (K=1 baseline ~= alpha)")
        print(f"    planted leak    -> outside-band rate "
              f"{'n/a' if lr is None else f'{lr:.1%}'}  (a search over K candidates)")
        if row["example_clean"] is not None and row["example_leak"] is not None:
            print(f"    example sample  -> clean {row['example_clean']['verdict']}, "
                  f"leak {row['example_leak']['verdict']}")
        dz, ke = row["mean_delta_z"], row["mean_k_eff"]
        print(f"    Stage 2         -> mean Delta_Z "
              f"{'n/a' if dz is None else f'{dz:+.4f}'}, mean K_eff "
              f"{'n/a' if ke is None else f'{ke:.2f}'} over {row['samples']} samples")
    ledger = report.get("ledger")
    if ledger is not None:
        print(f"\ntrial ledger: {ledger.get('n_trials')} recorded row(s), "
              f"dispersion {ledger.get('sharpe_dispersion')}")
    print("\nCaveat (2604.15531): this is a necessary-condition screen, not a "
          "certification, and a pipeline can be tuned to pass it.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="H3 null-environment harness")
    parser.add_argument("--reference-class", default="all",
                        help="one of the five, or 'all'")
    parser.add_argument("--replications", type=int, default=1000)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--n-obs", type=int, default=252)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ledger-dir", default=None,
                        help="read the recorded search size from H1's trial ledger")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.reference_class == "all":
        classes = list(nh.REFERENCE_CLASSES)
    elif args.reference_class in nh.REFERENCE_CLASSES:
        classes = [args.reference_class]
    else:
        print(f"unknown reference class {args.reference_class!r}; choose from "
              f"{', '.join(nh.REFERENCE_CLASSES)} or 'all'", file=sys.stderr)
        return 2

    report: dict = {"alpha": args.alpha, "replications": args.replications,
                    "n_obs": args.n_obs, "seed": args.seed, "classes": {}}
    unusable = False
    for name in classes:
        row = _run_one(name, args.replications, args.alpha, args.n_obs, args.seed)
        if row["band"]["quantile"] is None:
            unusable = True
        report["classes"][name] = row
    report["ledger"] = _ledger_size(args.ledger_dir)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_text(report)
    return 2 if unusable else 0


if __name__ == "__main__":
    raise SystemExit(main())
