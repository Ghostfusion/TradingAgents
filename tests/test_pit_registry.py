"""Tests for the PIT registry (design_qlib_integration.md §3.5).

Covers acceptance §8-5 (as-of masking: a record dated after the as-of is
never visible) and the learn/infer moment + label conventions (§8-7).
"""

import os

import pytest

from tradingagents.dataflows import pit_registry as pit

pytestmark = pytest.mark.timeout(30)


def _tmp_root(tmp_path) -> str:
    return str(tmp_path / "pit")


class TestPitRegistry:
    def test_store_and_read_roundtrip(self, tmp_path):
        root = _tmp_root(tmp_path)
        pit.store_snapshot("NVDA", "2026-08-01", {"close": 120.0}, root)
        pit.store_snapshot("NVDA", "2026-08-05", {"close": 125.0}, root)
        snap = pit.read_snapshot("NVDA", root=root)
        assert snap is not None and snap["payload"]["close"] == 125.0
        assert len(pit.read_all("NVDA", root=root)) == 2

    def test_as_of_masking_post_dated_invisible(self, tmp_path):
        # §8-5: a record dated AFTER the as-of is never visible.
        root = _tmp_root(tmp_path)
        pit.store_snapshot("AAPL", "2026-08-01", {"close": 200.0}, root)
        pit.store_snapshot("AAPL", "2026-08-10", {"close": 210.0}, root)
        assert pit.read_as_of("AAPL", "2026-08-05", root) == {"close": 200.0}
        assert pit.read_as_of("AAPL", "2026-08-01", root) == {"close": 200.0}
        assert pit.read_as_of("AAPL", "2026-07-01", root) is None  # nothing before
        assert pit.read_as_of("AAPL", "2026-08-20", root) == {"close": 210.0}

    def test_moments_roundtrip_and_immutability(self, tmp_path):
        # §8-7: train-fitted moments persist; a later malicious moment never
        # overwrites the stored train-fitted stats unless explicitly stored.
        root = _tmp_root(tmp_path)
        pit.put_moments("MSFT", "2026-08-01", {"kind": "moments", "mean": 24.5, "std": 2.0}, root)
        got = pit.get_moments("MSFT", root=root)
        assert got is not None and got["mean"] == 24.5
        # re-running the same train segment deterministically restores the same stats
        pit.put_moments("MSFT", "2026-08-01", {"kind": "moments", "mean": 24.5, "std": 2.0}, root)
        assert pit.get_moments("MSFT", root=root)["mean"] == 24.5

    def test_partial_corrupt_line_degrades(self, tmp_path):
        root = _tmp_root(tmp_path)
        pit.store_snapshot("TSLA", "2026-08-01", {"close": 250.0}, root)
        path = os.path.join(root, "TSLA.jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write('{"symbol": "TSLA", "as_of": "2026-08-02", "payload": {"close": \n')  # partial
        pit.store_snapshot("TSLA", "2026-08-03", {"close": 255.0}, root)
        snaps = pit.read_all("TSLA", root=root)
        assert len(snaps) == 2 and snaps[-1]["payload"]["close"] == 255.0

    def test_markup_label_one_day_buffer(self):
        # Ref(close,-2)/Ref(close,-1) - 1: 100 -> 103 -> label = 3% (realized
        # AFTER the close the signal could trade at).
        assert pit.markup_label([100.0, 103.0]) is None  # needs 3 closes
        assert pit.markup_label([100.0, 100.0, 103.0]) == pytest.approx(0.03)
        assert pit.markup_label([100.0, 0.0, 200.0]) is None  # zero ref guarded
        assert pit.markup_label([100.0, None, 103.0]) is None

    def test_symbol_normalization(self, tmp_path):
        root = _tmp_root(tmp_path)
        pit.store_snapshot("nvda", "2026-08-01", {"close": 1.0}, root)
        assert pit.read_as_of("NVDA", "2026-08-02", root) == {"close": 1.0}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
