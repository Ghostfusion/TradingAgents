#!/usr/bin/env python3
"""E6/E7/E8 offline caller: a declared forecast score, the DM/MZ diagnostics, and
the equal-weight combination arm.

Computes one of the ``forecast_contract.SCORING_RULES`` with the producer in
``tradingagents/strategies/forecast_scores.py`` (E7); the Diebold-Mariano test
and the Mincer-Zarnowitz calibration regression with ``calibration`` (E6); and
the pool combination arm with ``forecast_registry.equal_weight_combination``
(E8). Offline and pure; the frozen forecasting contract (design §11.0) is not
touched - the diagnostics ride BESIDE a ``ForecastEvaluation``, they do not add a
field to it.

Usage:
    python scripts/forecast_scores.py --rule RMSE --actual 1,2,3 --forecast 1.1,2.2,3.3
    python scripts/forecast_scores.py --rule CRPS --actual 1,2 --members "2,2,2;4,4,4"
    python scripts/forecast_scores.py --rule MAE --actual 1,2,3 --forecast 1.1,2,3.2 --benchmark 1.5,2.5,3.5
    python scripts/forecast_scores.py --combine "0.20;0.22;0.19"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _floats(text: str) -> list[float]:
    return [float(x) for x in text.split(",") if x.strip()]


def _ensembles(text: str) -> list[list[float]]:
    return [
        [float(x) for x in member.split(",") if x.strip()]
        for member in text.split(";") if member.strip()
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", default="RMSE",
                        choices=["CRPS", "QLIKE", "RMSE", "MAE"])
    parser.add_argument("--actual", default=None, help="realized values (','-separated)")
    parser.add_argument("--forecast", default=None, help="point forecasts (','-separated)")
    parser.add_argument("--members", default=None,
                        help="CRPS only: ';'-separated ensembles, each ','-separated")
    parser.add_argument("--benchmark", default=None,
                        help="benchmark forecasts, for the Diebold-Mariano test")
    parser.add_argument("--combine", default=None,
                        help="E8: ';'-separated member forecasts to equal-weight combine")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from tradingagents.strategies.calibration import diebold_mariano, mz_regression
    from tradingagents.strategies.forecast_registry import equal_weight_combination
    from tradingagents.strategies.forecast_scores import score_forecast

    try:
        actual = _floats(args.actual) if args.actual else None
        point = _floats(args.forecast) if args.forecast else None
        members = _ensembles(args.members) if args.members else None
        benchmark = _floats(args.benchmark) if args.benchmark else None
        members_flat = _floats(args.combine) if args.combine and ";" not in args.combine \
            else ([float(x) for x in args.combine.split(";") if x.strip()]
                  if args.combine else None)
    except ValueError as exc:
        print(f"bad input list: {exc}")
        return 2

    out: dict = {}
    if actual is not None and args.rule == "CRPS" and members is not None:
        out["score"] = score_forecast("CRPS", actual, members)
    elif actual is not None and point is not None:
        out["score"] = score_forecast(args.rule, actual, point)
    if actual is not None and point is not None:
        out["mz"] = mz_regression(actual, point)
    if actual is not None and point is not None and benchmark is not None:
        fwd = [abs(a - f) for a, f in zip(actual, point, strict=False)]
        bwd = [abs(a - b) for a, b in zip(actual, benchmark, strict=False)]
        out["diebold_mariano"] = diebold_mariano(fwd, bwd)
    if members_flat is not None:
        out["combination"] = equal_weight_combination(members_flat)

    if not out:
        print("nothing to do: supply --actual with --forecast/--members, or --combine")
        return 2
    print(json.dumps(out, indent=2) if args.json else out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
