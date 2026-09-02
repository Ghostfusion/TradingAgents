"""Tests for the runfile declarative front-end + experiment ledger.

Covers design_qlib_integration.md 8-4 + 8-11:
- runfile -> pipeline argv equivalence (dry-run), config-hash stability
- ledger append/round-trip + status lifecycle
- experiments.py filter / diff / json read views
"""

import json
import os

import pytest

from scripts import runfile as rf

pytestmark = pytest.mark.timeout(30)

RUNFILE_YAML = """
universe:
  tickers: [AAPL, MSFT]
  top: 2
  limit: 0
  min_mcap: 1e10
  price_min: 10
  pe_max: 50
date: "2026-09-02"
vendor: moomoo
depth: deep
analysts: [market]
workers: 2
movers:
  count: 10
  direction: losers
stages:
  fit: {start: "2026-01-01", end: "2026-06-30"}
  valid: {start: "2026-07-01", end: "2026-08-01"}
  test: {start: "2026-08-02", end: "2026-09-01"}
factor_model:
  enable: false
"""

@pytest.fixture()
def runfile_yaml(tmp_path):
    p = tmp_path / "nightly.yaml"
    p.write_text(RUNFILE_YAML, encoding="utf-8")
    return str(p)

class TestRunfileToArgv:
    def test_expansion_matches_pipeline_flags(self, runfile_yaml):
        data = rf.load_runfile(runfile_yaml)
        argv = rf.runfile_to_argv(data)
        joined = " ".join(argv)
        assert "-f" not in joined  # tickers path, not file
        assert "AAPL" in argv and "MSFT" in argv
        assert "--top" in argv and "2" in argv
        assert "-d" in argv and "2026-09-02" in argv
        assert "--vendor" in argv and "moomoo" in argv
        assert "--analysts" in argv and "market" in argv
        assert "--movers-direction" in argv and "losers" in argv
        assert "--workers" in argv and "2" in argv

    def test_config_hash_stable(self, runfile_yaml):
        data = rf.load_runfile(runfile_yaml)
        h1 = rf.config_hash(rf._params_from_runfile(data))
        h2 = rf.config_hash(rf._params_from_runfile(data))
        assert h1 == h2 and len(h1) == 16
        assert rf.config_hash({"a": 1}) != rf.config_hash({"a": 2})

    def test_dry_run_prints_argv(self, runfile_yaml, capsys):
        code = rf.main(["--runfile", runfile_yaml, "--dry-run"])
        out = capsys.readouterr().out
        assert code == 0
        assert "run_id:" in out and "config_hash:" in out and "pipeline.py" in out

class TestLedger:
    def test_append_roundtrip_and_status(self, tmp_path):
        d = str(tmp_path / "ledger")
        p1 = rf.ledger_append({"run_id": "r1", "status": "pending"}, d)
        assert p1 and os.path.exists(p1)
        rf.ledger_append({"run_id": "r1", "status": "done"}, d)
        with open(p1, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        assert [r["status"] for r in rows] == ["pending", "done"]

    def test_corrupt_line_degrades(self, tmp_path):
        d = str(tmp_path / "ledger")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "experiments.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"run_id": "r1", "status": "pending"}\n')
            fh.write("not-json\n")
            fh.write('{"run_id": "r2", "status": "done"}\n')
        from scripts import experiments as ex

        rows = ex.load_rows(d)
        assert [r["run_id"] for r in rows] == ["r1", "r2"]

class TestExperimentsView:
    @pytest.fixture()
    def seeded(self, tmp_path):
        d = str(tmp_path / "ledger")
        rf.ledger_append({"run_id": "a", "status": "done", "config_hash": "h1",
                          "metrics": {"ic": 0.05, "pbo": False}}, d)
        rf.ledger_append({"run_id": "b", "status": "done", "config_hash": "h2",
                          "metrics": {"ic": 0.01, "pbo": False}}, d)
        rf.ledger_append({"run_id": "c", "status": "failed", "config_hash": "h3",
                          "metrics": {"ic": 0.0}}, d)
        return d

    def test_filter_and_json(self, seeded, capsys):
        from scripts import experiments as ex

        code = ex.main(["--ledger-dir", seeded, "--filter-metrics", "ic>0.02,status=done",
                        "--format", "json"])
        out = capsys.readouterr().out
        assert code == 0
        rows = json.loads(out)
        assert len(rows) == 1 and rows[0]["run_id"] == "a"

    def test_diff(self, seeded, capsys):
        from scripts import experiments as ex

        code = ex.main(["--ledger-dir", seeded, "--diff", "a", "b"])
        out = capsys.readouterr().out
        assert code == 0
        assert "field" in out and "a" in out and "b" in out

    def test_missing_diff_id(self, seeded, capsys):
        from scripts import experiments as ex

        assert ex.main(["--ledger-dir", seeded, "--diff", "a", "zzz"]) == 2

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

