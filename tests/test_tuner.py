"""Tests for the optional tuner front-end (design §3.10)."""

import json

import numpy as np
import pytest

from scripts import tuner

pytestmark = pytest.mark.timeout(30)


class TestTuner:
    def test_grid_ranks_better_alpha_first(self):
        rng = np.random.default_rng(5)
        n = 200
        x = rng.uniform(0, 1, n)
        y = 0.02 * x + rng.normal(0, 0.01, n)
        X = np.column_stack([x, rng.normal(0, 0.5, n)])
        rows = tuner.search_grid(X, y)
        assert rows and rows[0]["oos_sharpe"] is not None
        # a low-ridge fit on predictive features should beat the all-noise
        # second column ridge; rows are sorted desc by oos_sharpe
        assert rows[0]["oos_sharpe"] >= (rows[-1]["oos_sharpe"] or 0)

    def test_gate_is_authority(self):
        rng = np.random.default_rng(6)
        n = 200
        x = rng.uniform(0, 1, n)
        y = 0.05 * x + rng.normal(0, 0.01, n)  # strongly predictive
        X = np.column_stack([x])
        rows = tuner.search_grid(X, y)
        gated = [r for r in rows if r["gate"].get("ok")]
        assert gated  # at least one grid point passes on predictive data

    def test_cli_writes_results(self, tmp_path):
        rng = np.random.default_rng(7)
        n = 150
        x = rng.uniform(0, 1, n)
        y = 0.03 * x + rng.normal(0, 0.01, n)
        fp = tmp_path / "feats.jsonl"
        lp = tmp_path / "labels.jsonl"
        fp.write_text("\n".join(
            json.dumps({"name": f"S{i:03d}", "features": {"x": float(x[i])}})
            for i in range(n)) + "\n", encoding="utf-8")
        lp.write_text("\n".join(
            json.dumps({"name": f"S{i:03d}", "label": float(y[i])})
            for i in range(n)) + "\n", encoding="utf-8")
        op = tmp_path / "tuner.json"
        code = tuner.main(["--features", str(fp), "--labels", str(lp),
                           "--out", str(op)])
        assert code == 0
        data = json.loads(op.read_text(encoding="utf-8"))
        assert data["ok"] and len(data["grid"]) == 4


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
