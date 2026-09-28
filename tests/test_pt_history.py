"""NEWS-6 - the persisted price-target consensus store and its revision read."""

import json

import pytest

from tradingagents.strategies.pt_history import (
    pt_history_path,
    pt_revision,
    read_pt_history,
    record_pt_snapshot,
)

pytestmark = pytest.mark.timeout(600)


def _snap(mean, **kw):
    out = {"mean": mean, "median": mean, "high": mean + 5, "low": mean - 5,
           "current": mean, "count": 20, "source": "test"}
    out.update(kw)
    return out


def test_one_row_per_date(tmp_path):
    assert record_pt_snapshot("msft", _snap(500.0), "2026-09-01", tmp_path) is not None
    assert pt_history_path("msft", tmp_path).exists()


def test_a_rerun_on_the_same_date_does_not_rewrite(tmp_path):
    record_pt_snapshot("MSFT", _snap(500.0), "2026-09-01", tmp_path)
    assert record_pt_snapshot("MSFT", _snap(999.0), "2026-09-01", tmp_path) is None
    rows = read_pt_history("MSFT", tmp_path)
    assert len(rows) == 1
    assert rows[0]["mean"] == 500.0


def test_a_snapshot_with_no_target_is_not_recorded(tmp_path):
    assert record_pt_snapshot("MSFT", {"mean": None, "median": None}, "2026-09-01", tmp_path) is None
    assert read_pt_history("MSFT", tmp_path) == []


def test_read_is_oldest_first(tmp_path):
    record_pt_snapshot("MSFT", _snap(300.0), "2026-03-01", tmp_path)
    record_pt_snapshot("MSFT", _snap(500.0), "2026-09-01", tmp_path)
    assert [r["date"] for r in read_pt_history("MSFT", tmp_path)] == [
        "2026-03-01", "2026-09-01"]


def test_a_corrupt_line_does_not_lose_the_history(tmp_path):
    record_pt_snapshot("MSFT", _snap(500.0), "2026-09-01", tmp_path)
    with pt_history_path("MSFT", tmp_path).open("a", encoding="utf-8") as fh:
        fh.write("{not json}\n")
    assert len(read_pt_history("MSFT", tmp_path)) == 1


def test_one_observation_is_not_a_revision(tmp_path):
    record_pt_snapshot("MSFT", _snap(500.0), "2026-09-01", tmp_path)
    out = pt_revision("MSFT", tmp_path)
    assert out["revision"] is None
    assert out["observations"] == 1
    assert "two are needed" in out["reason"]


def test_no_history_is_not_a_revision(tmp_path):
    out = pt_revision("MSFT", tmp_path)
    assert out["revision"] is None
    assert out["observations"] == 0
    assert out["reason"]


def test_the_revision_is_the_step_and_carries_its_basis(tmp_path):
    record_pt_snapshot("MSFT", _snap(400.0), "2026-03-01", tmp_path)
    record_pt_snapshot("MSFT", _snap(500.0), "2026-09-01", tmp_path)
    out = pt_revision("MSFT", tmp_path)
    assert out["revision"] == pytest.approx(100.0)
    assert out["revision_pct"] == pytest.approx(25.0)
    assert out["direction"] == "up"
    assert out["revision_since_first"] == pytest.approx(100.0)
    assert out["span"] == ("2026-03-01", "2026-09-01")
    assert out["prior_date"] == "2026-03-01"
    assert out["latest_date"] == "2026-09-01"
    assert out["reason"] is None


def test_a_downward_revision_is_named(tmp_path):
    record_pt_snapshot("MSFT", _snap(500.0), "2026-03-01", tmp_path)
    record_pt_snapshot("MSFT", _snap(450.0), "2026-09-01", tmp_path)
    out = pt_revision("MSFT", tmp_path)
    assert out["revision"] == pytest.approx(-50.0)
    assert out["direction"] == "down"


def test_an_unchanged_target_is_flat_not_up(tmp_path):
    record_pt_snapshot("MSFT", _snap(500.0), "2026-03-01", tmp_path)
    record_pt_snapshot("MSFT", _snap(500.0), "2026-09-01", tmp_path)
    assert pt_revision("MSFT", tmp_path)["direction"] == "flat"


def test_the_row_keeps_the_levels_it_was_given(tmp_path):
    record_pt_snapshot("MSFT", _snap(500.0, count=42), "2026-09-01", tmp_path)
    row = read_pt_history("MSFT", tmp_path)[0]
    assert row["high"] == 505.0 and row["low"] == 495.0
    assert row["count"] == 42
    assert json.dumps(row)  # the row is JSON-serialisable as written
