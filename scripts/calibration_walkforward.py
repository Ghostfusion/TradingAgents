"""Walk-forward calibration audit for the prediction ledger (pure, offline).

Consumes the decision prediction ledger (``prediction_ledger.rows()``),
which logs per-decision ``{confidence, outcome}`` (outcome hit = direction
matched realized return), then:

1. builds per-regime calibration buckets on an IN-SAMPLE slice
   (``fit_buckets_by_regime``),
2. evaluates on a later OUT-OF-SAMPLE slice — reliability curve (raw
   confidence bins vs. realized hit rate) + Expected Calibration Error,
3. prints the per-regime table and the OOS ECE so you can audit whether the
   PM's declared confidence is actually calibrated (ECE ~0 = good; >0.10 =
   poorly calibrated, pair with ``enable_calibration``).

Pure / offline: reads the ledger file only (or the default path); never
writes; no live data.

Usage:
    py -3.12 scripts/calibration_walkforward.py --ledger PATH [--is-frac 0.7]
"""

from __future__ import annotations

import argparse
import sys

_BINS = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0001)]


def _scored_rows(rows: list[dict]) -> list[dict]:
    """Filter ledger rows to those with confidence AND a realized outcome."""
    out = []
    for r in rows:
        conf = r.get("confidence")
        outd = r.get("outcome")
        if conf is None or not isinstance(outd, dict):
            continue
        hit = outd.get("hit")
        if hit is None:
            continue
        try:
            c = float(conf)
        except (TypeError, ValueError):
            continue
        if not (0.0 <= c <= 1.0):
            continue
        out.append({
            "confidence": c,
            "won": bool(hit),
            "regime": str(r.get("regime") or "_all"),
        })
    return out


def _reliability(rows: list[dict]) -> list[dict]:
    """Actual hit rate per confidence bin for the given rows."""
    tab: list[dict] = []
    for lo, hi in _BINS:
        bin_rows = [r for r in rows if lo <= r["confidence"] < hi]
        if not bin_rows:
            continue
        tab.append({
            "bin": f"{lo:.0%}-{min(hi, 1.0):.0%}",
            "n": len(bin_rows),
            "predicted_mid": round((lo + hi) / 2.0, 3),
            "actual_hit_rate": round(sum(1 for r in bin_rows if r["won"]) / len(bin_rows), 3),
        })
    return tab


def _ece(rows: list[dict]) -> float | None:
    """Expected Calibration Error over the binned rows."""
    tab = _reliability(rows)
    if not tab:
        return None
    n = sum(t["n"] for t in tab)
    if n <= 0:
        return None
    return round(
        sum(abs(t["actual_hit_rate"] - t["predicted_mid"]) * t["n"] for t in tab) / n,
        4,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger", default=None,
        help=(
            "results dir containing predictions.jsonl (the ledger root the "
            "prediction_ledger module uses; default = ~/.tradingagents/logs)"
        ),
    )
    parser.add_argument(
        "--is-frac", type=float, default=0.7,
        help="In-sample fraction (rest = out-of-sample evaluation) (default 0.7)",
    )
    args = parser.parse_args()

    import tradingagents.strategies.prediction_ledger as PL
    from tradingagents.strategies.calibration import (
        calibrated_confidence_by_regime,
        fit_buckets_by_regime,
    )

    rows = PL.rows(args.ledger)
    if not rows:
        print("no ledger rows (pass --ledger PATH if not the default).")
        return 1
    cal = _scored_rows(rows)
    if not cal:
        print("no ledger rows with both confidence and a realized outcome.")
        return 1

    n = len(cal)
    split = max(1, int(n * args.is_frac))
    is_, oos = cal[:split], cal[split:]
    tables = fit_buckets_by_regime(is_)

    print(f"ledger rows={n}  in-sample-fit={len(is_)}  OOS-eval={len(oos)}\n")

    print("== per-regime in-sample calibration tables ==")
    if not tables:
        print("  (no regime-partitioned buckets — small/empty history)")
    for rg, t in sorted(tables.items()):
        print(f"  {rg}:")
        for (lo, hi), b in sorted(t.items()):
            print(f"    {lo:.0%}-{hi:.0%}: n={b['n']} win_rate={b['win_rate']:.1%}")

    print("\n== OOS reliability (raw confidence -> realized hit rate) ==")
    for t in _reliability(oos):
        print(
            f"  {t['bin']}: n={t['n']} actual_hit={t['actual_hit_rate']:.1%} "
            f"(bin mid {t['predicted_mid']:.0%})"
        )

    ece = _ece(oos)
    verdict = "calibrated" if ece is not None and ece <= 0.10 else "poorly calibrated"
    print(f"\nOOS ECE: {ece if ece is not None else 'n/a'} ({verdict})")

    # Show what the by-regime calibrator would do to a 0.8 OOS declared conf.
    mapped = calibrated_confidence_by_regime(0.8, tables, regime="_all", min_n=1)
    print(f"sample: a declared 0.80 confidence maps to {mapped if mapped is not None else 'identity'}")
    return 0 if ece is None or ece <= 0.10 else 1


if __name__ == "__main__":
    sys.exit(main())
