"""Tests for the factor-proposal loop (design §8-10).

- a planted predictive candidate gets a computed IC row and a gated adopt flag
- random-noise proposals are honestly rejected
- the candidate sheet renders only computed columns (numeric/boolean/reason)
"""

import json

import numpy as np
import pytest

from scripts import factor_proposal_loop as fpl

pytestmark = pytest.mark.timeout(30)


def _records(n: int = 120, predictive: bool = True, seed: int = 3):
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, n)
    fwd = 0.15 * x + rng.normal(0, 0.02, n) if predictive else rng.normal(0, 0.1, n)
    noise = rng.normal(0, 0.1, n)
    return [
        {"name": f"S{i:03d}", "as_of": "2026-08-01",
         "features": {"mom_5": float(x[i]), "noise_1": float(noise[i])},
         "fwd_return": float(fwd[i])}
        for i in range(n)
    ]


class TestProposalLoop:
    def test_planted_candidate_adopted(self):
        recs = _records(predictive=True)
        out = fpl.evaluate_candidates(["mom_5", "noise_1"], recs, min_ic=0.02)
        assert out["mom_5"]["ic"] is not None and out["mom_5"]["ic"] > 0.3
        assert out["mom_5"]["adopted"] is True
        assert out["mom_5"]["gate_reason"] == "pass"

    def test_random_noise_rejected(self):
        recs = _records(predictive=False, seed=9)
        out = fpl.evaluate_candidates(["noise_1", "mom_5"], recs, min_ic=0.02)
        for factor in ("noise_1", "mom_5"):
            assert out[factor]["adopted"] is False  # honest reject

    def test_sheet_computed_columns_only(self):
        recs = _records(predictive=True)
        out = fpl.evaluate_candidates(["mom_5"], recs)
        row = out["mom_5"]
        assert set(row) == {"ic", "icir", "ls_return", "n", "gated", "adopted",
                            "gate_reason"}
        assert isinstance(row["ic"], float) and isinstance(row["n"], int)
        assert isinstance(row["gated"], bool) and isinstance(row["adopted"], bool)

    def test_too_few_rows_honest(self):
        recs = _records(n=8)
        out = fpl.evaluate_candidates(["mom_5"], recs)
        assert out["mom_5"]["n"] == 0 and out["mom_5"]["adopted"] is False

    def test_cli_writes_sheet(self, tmp_path):
        recs = _records(predictive=True)
        rp = tmp_path / "records.jsonl"
        rp.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
        op = tmp_path / "candidates.jsonl"
        code = fpl.main(["--records", str(rp), "--out", str(op),
                         "--proposals", "mom_5,noise_1"])
        assert code == 0
        rows = [json.loads(line) for line in op.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(rows) == 2
        adopted = [r["candidate"] for r in rows if r["adopted"]]
        assert adopted == ["mom_5"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
