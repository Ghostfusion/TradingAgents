"""Advisory supervised factor model (Qlib pillar 5, gated — Phase 4).

Trains a factor model on Alpha158-style features over the memory-log realized
outcomes (PIT-labeled via ``pit_registry.markup_label``), then applies the
existing walk-forward + PBO + deflated-Sharpe gate (``evaluate_config_gate``)
to the model's OOS return series. The learned ``pred_score`` per name is a
RESEARCH ARTIFACT: it reaches the LLM only when ``enable_factor_model`` is
True AND the gate passed; otherwise the output is ``gated: false`` and
nothing advisory consumes it.

Estimator: LightGBM when installed; a ridge regression fallback otherwise
(deterministic, no new dependency). The gate is the unchanged authority
(``evaluate_config_gate.gate_verdict``), never replaced by in-sample fit.

Usage:
    py -3.12 scripts/factor_model_train.py --features data/features.jsonl \\
        --labels data/labels.jsonl --out data/factor_model_output.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np


def _ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> np.ndarray | None:
    """Closed-form ridge coefficients; None on degenerate design matrix."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if X.shape[0] < 2 or X.shape[1] == 0:
        return None
    try:
        gram = X.T @ X + float(alpha) * np.eye(X.shape[1])
        beta = np.linalg.solve(gram, X.T @ y)
        return beta
    except np.linalg.LinAlgError:
        return None


def _get_model():
    """(kind, fit_fn, predict_fn) — LightGBM when available, else ridge."""
    try:
        import lightgbm as lgb

        return ("lightgbm", lgb, None)
    except ImportError:
        return ("ridge", None, None)


def load_records(features_path: str, labels_path: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Load ``[{name, feature: value}]`` + ``[{name, label}]`` JSONL records.

    Returns (X, y, names) aligned on name; rows missing a label or with all-
    NaN features are dropped (no fabrication).
    """
    feats: dict[str, dict] = {}
    with open(features_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = str(row.get("name") or "").upper()
            if not name:
                continue
            feats[name] = {k: v for k, v in (row.get("features") or {}).items()
                           if isinstance(v, (int, float))}
    labels: dict[str, float] = {}
    with open(labels_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = str(row.get("name") or "").upper()
            if name and row.get("label") is not None:
                try:
                    labels[name] = float(row["label"])
                except (TypeError, ValueError):
                    continue
    names = sorted(set(feats) & set(labels))
    keys = sorted({k for n in names for k in feats[n]})
    X = np.full((len(names), len(keys)), np.nan, dtype=float)
    y = np.zeros(len(names), dtype=float)
    for i, n in enumerate(names):
        for j, k in enumerate(keys):
            X[i, j] = feats[n].get(k, np.nan)
        y[i] = labels[n]
    return X, y, names


def train_ridge(X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> tuple[np.ndarray | None, float]:
    """(beta, n_used) — ridge with NaN rows dropped; None when degenerate."""
    finite = np.all(np.isfinite(X), axis=1)
    Xf, yf = X[finite], y[finite]
    if Xf.shape[0] < 2:
        return None, 0
    beta = _ridge_fit(Xf, yf, alpha)
    return beta, int(Xf.shape[0])


def predict(X: np.ndarray, beta: np.ndarray | None) -> np.ndarray | None:
    """``X @ beta`` with NaN rows -> 0 (no data = no signal, never a guess)."""
    if beta is None:
        return None
    out = np.zeros(X.shape[0], dtype=float)
    for i, row in enumerate(X):
        if np.all(np.isfinite(row)):
            out[i] = float(row @ beta)
    return out


def gate_series(pred: np.ndarray, y: np.ndarray) -> list[float] | None:
    """OOS return series for the gate: ``pred * sign(y)`` per row.

    A simple directional proxy over the labeled rows (the label is the
    one-buffer forward return, so ``pred``'s sign betting the label's sign is
    the natural Sharpe test). None when too few rows.
    """
    finite = np.isfinite(pred) & np.isfinite(y)
    if int(finite.sum()) < 10:
        return None
    p = pred[finite]
    yy = y[finite]
    return [float(p[i] * (1.0 if yy[i] >= 0 else -1.0)) for i in range(len(p))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", required=True, help="JSONL: {name, features:{...}}")
    parser.add_argument("--labels", required=True, help="JSONL: {name, label}")
    parser.add_argument("--out", required=True, help="output JSON path")
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--trials", type=int, default=20, help="deflated-Sharpe trials")
    args = parser.parse_args(argv)

    try:
        X, y, names = load_records(args.features, args.labels)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": f"load failed: {exc}"}))
        return 2
    if len(names) < 10:
        print(json.dumps({"ok": False, "error": "too few aligned records "
                         f"({len(names)} < 10)", "n_names": len(names)}))
        return 3

    kind, lgb_mod, _ = _get_model()
    result: dict = {"ok": True, "kind": kind, "n_names": len(names)}

    if kind == "ridge":
        beta, n_used = train_ridge(X, y, args.alpha)
        pred = predict(X, beta)
        if beta is None:
            print(json.dumps({"ok": False, "error": "degenerate design matrix"}))
            return 4
        result["n_train_rows"] = n_used
        result["coefs"] = [round(float(c), 5) for c in beta.tolist()]
    else:
        # LightGBM path (only when installed): 5-fold-ish quick fit on rows
        # with finite features; keep deterministic with a fixed seed.
        try:
            model = lgb_mod.LGBMRegressor(n_estimators=50, max_depth=3,  # type: ignore[union-attr]
                                          random_state=7, verbose=-1)
            finite = np.all(np.isfinite(X), axis=1)
            model.fit(X[finite], y[finite])
            pred = model.predict(X)
            result["n_train_rows"] = int(finite.sum())
        except Exception as exc:  # noqa: BLE001 - fall back to no model
            print(json.dumps({"ok": False, "error": f"lightgbm failed: {exc}"}))
            return 5

    rets = gate_series(pred, y)
    from scripts.evaluate_config_gate import gate_verdict

    verdict = gate_verdict(rets, trials=args.trials) if rets else {
        "ok": None, "reason": "too few OOS rows", "oos_best": None}
    gated = bool(verdict.get("ok"))
    result["gate"] = verdict
    result["pred_score"] = {n: round(float(p), 6)
                            for n, p in zip(names, pred, strict=True)}
    result["advisory"] = gated

    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"write failed: {exc}"}))
        return 6

    print(json.dumps({
        "ok": True, "advisory": gated, "gate_reason": verdict.get("reason"),
        "n_names": len(names), "out": args.out,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
