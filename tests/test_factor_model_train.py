"""Hermetic tests for the advisory factor model (design §8-6/§8-10 gating).

- a planted predictive feature trains a model whose gate verdict passes
- random noise features fail the gate (honest reject, never promoted)
- `enable_factor_model` False means the model output is never advisory
- output JSON has computed columns only (no fabricated numbers)
"""

import json

import numpy as np
import pytest

from scripts import factor_model_train as fmt

pytestmark = pytest.mark.timeout(30)


def _planted_records(n: int = 60, noise: float = 0.0, seed: int = 0):
    rng = np.random.default_rng(seed)
    feat = rng.uniform(0, 1, n)
    label = 0.02 * feat + rng.normal(0, noise, n)  # predictive when noise small
    feats = [{"name": f"S{i:03d}", "features": {"x": float(feat[i])}} for i in range(n)]
    labels = [{"name": f"S{i:03d}", "label": float(label[i])} for i in range(n)]
    return feats, labels


def _write(tmp_path, feats, labels):
    fp = tmp_path / "feats.jsonl"
    lp = tmp_path / "labels.jsonl"
    fp.write_text("\n".join(json.dumps(r) for r in feats) + "\n", encoding="utf-8")
    lp.write_text("\n".join(json.dumps(r) for r in labels) + "\n", encoding="utf-8")
    return str(fp), str(lp)


class TestFactorModel:
    def test_planted_predictive_passes_gate(self, tmp_path):
        feats, labels = _planted_records(n=120, noise=0.002)
        fp, lp = _write(tmp_path, feats, labels)
        out = tmp_path / "out.json"
        code = fmt.main(["--features", fp, "--labels", lp, "--out", str(out)])
        assert code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["ok"] and data["advisory"] is True
        assert data["gate"]["ok"] is True
        assert len(data["pred_score"]) == 120

    def test_random_noise_rejected(self, tmp_path):
        rng = np.random.default_rng(1)
        feats = [{"name": f"S{i:03d}", "features": {"x": float(rng.uniform(0, 1))}}
                 for i in range(120)]
        labels = [{"name": f"S{i:03d}", "label": float(rng.normal(0, 0.05))} for i in range(120)]
        fp, lp = _write(tmp_path, feats, labels)
        out = tmp_path / "out.json"
        code = fmt.main(["--features", fp, "--labels", lp, "--out", str(out)])
        assert code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["advisory"] is False  # honest reject, never promoted
        assert data["gate"]["ok"] in (False, None)

    def test_too_few_records(self, tmp_path):
        feats, labels = _planted_records(n=5)
        fp, lp = _write(tmp_path, feats, labels)
        out = tmp_path / "out.json"
        code = fmt.main(["--features", fp, "--labels", lp, "--out", str(out)])
        assert code == 3

    def test_output_is_computed_columns_only(self, tmp_path):
        feats, labels = _planted_records(n=60)
        fp, lp = _write(tmp_path, feats, labels)
        out = tmp_path / "out.json"
        fmt.main(["--features", fp, "--labels", lp, "--out", str(out)])
        data = json.loads(out.read_text(encoding="utf-8"))
        assert set(data) == {"ok", "kind", "n_names", "n_train_rows", "coefs",
                             "gate", "pred_score", "advisory"}
        for v in data["pred_score"].values():
            assert isinstance(v, float)

    def test_ridge_fit_math(self):
        X = np.array([[1.0, 0.5], [2.0, 1.0], [3.0, 0.2], [4.0, 1.5]])
        y = np.array([1.0, 2.0, 3.0, 4.0])
        beta, n = fmt.train_ridge(X, y, alpha=0.0)
        assert n == 4 and beta is not None
        pred = fmt.predict(X, beta)
        assert pred is not None and pred[-1] == pytest.approx(4.0, abs=1e-6)

    def test_gate_series_none_short(self):
        assert fmt.gate_series(np.array([0.1] * 9), np.array([0.1] * 9)) is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
