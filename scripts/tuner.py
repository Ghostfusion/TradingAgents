"""Optional hyperparameter search front-end (Qlib pillar 19) — DEP-FREE GRID.

Searches the factor-model hyperparameters (ridge alpha / lightgbm depth) over
rolling windows and reports candidates rank-ordered by the OOS gate verdict.
**Search only: every candidate still passes the existing walk-forward+PBO
gate (``evaluate_config_gate``) before promotion — search finds, the gate
decides.** ``enable_tuner`` is False by default; the tuner itself never
mutates the promoted model.

The search is a deterministic grid (no optuna/hyperopt dependency): for each
alpha in ``[0.01, 0.1, 1, 10]`` train on the train slice, evaluate on the
test slice, record ``{alpha, test_sharpe, gate: {ok, reason}}``.

Usage:
    py -3.12 scripts/tuner.py --features data/feats.jsonl --labels data/labels.jsonl \\
        --out data/tuner.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from scripts.factor_model_train import gate_series, load_records, predict, train_ridge


def rolling_splits(n: int, train_len: int, test_len: int):
    """Deterministic walk-forward (train, test) index slices."""
    i = 0
    while i + train_len + test_len <= n:
        yield slice(i, i + train_len), slice(i + train_len, i + train_len + test_len)
        i += test_len


def search_grid(X: np.ndarray, y: np.ndarray,
                alphas: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0),
                train_len: int = 60, test_len: int = 20) -> list[dict]:
    """Grid search over ridge alpha with walk-forward OOS evaluation.

    Each row: ``{alpha, oos_sharpe, oos_n, gate: {ok, reason}}`` using the
    SAME ``gate_verdict`` the promotion path uses. Degenerate windows are
    skipped (no fabrication).
    """
    from scripts.evaluate_config_gate import gate_verdict

    rows: list[dict] = []
    for alpha in alphas:
        oos_rets: list[float] = []
        for tr, te in rolling_splits(len(X), train_len, test_len):
            beta, n_used = train_ridge(X[tr], y[tr], alpha)
            if beta is None or n_used < 2:
                continue
            pred = predict(X[te], beta)
            if pred is None:
                continue
            seg = gate_series(pred, y[te])
            if seg:
                oos_rets.extend(seg)
        if not oos_rets:
            rows.append({"alpha": alpha, "oos_sharpe": None, "oos_n": 0,
                         "gate": {"ok": None, "reason": "no OOS windows"}})
            continue
        from tradingagents.strategies.evaluate import sharpe

        rows.append({
            "alpha": alpha,
            "oos_sharpe": round(sharpe(oos_rets), 4) if len(oos_rets) >= 2 else None,
            "oos_n": len(oos_rets),
            "gate": gate_verdict(oos_rets),
        })
    rows.sort(key=lambda r: (r["oos_sharpe"] is not None, -float(r["oos_sharpe"] or 0)))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--alphas", default="0.01,0.1,1.0,10.0")
    args = parser.parse_args(argv)

    try:
        X, y, names = load_records(args.features, args.labels)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": f"load failed: {exc}"}))
        return 2
    if len(names) < 10:
        print(json.dumps({"ok": False, "error": "too few records",
                          "n_names": len(names)}))
        return 3

    alphas = tuple(float(a) for a in args.alphas.split(",") if a.strip())
    rows = search_grid(X, y, alphas)
    best = next((r for r in rows if r["gate"].get("ok")), None)

    out = {"ok": True, "n_names": len(names), "grid": rows,
           "best_gated": best}
    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"write failed: {exc}"}))
        return 4
    print(json.dumps({"ok": True, "best_gated": bool(best),
                      "best_alpha": best["alpha"] if best else None,
                      "out": args.out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
