"""Batch worker cap, and the per-worker memory isolation the cap depends on."""

import os
from pathlib import Path
from unittest import mock

import pytest

import batch
from tradingagents.agents.utils.memory import TradingMemoryLog


def test_workers_capped_below_limit():
    assert batch.effective_workers(8) == 4
    assert batch.effective_workers(3) == 3
    assert batch.effective_workers(-5) == 1


def test_env_override_is_a_ceiling():
    with mock.patch.dict(os.environ, {"TRADINGAGENTS_MAX_WORKERS": "6"}):
        assert batch.effective_workers(50) == 6
        assert batch.effective_workers(3) == 3  # requested < env ceiling
    with mock.patch.dict(os.environ, {"TRADINGAGENTS_MAX_WORKERS": "junk"}):
        assert batch.effective_workers(9) == 4


# ---------------------------------------------------------------------------
# Per-worker memory isolation (`_per_symbol_memory_path`)
#
# The cap above makes workers run concurrently; this is what keeps two of them
# from interleaving a read-modify-write cycle in one file. It was implemented
# and documented (`docs/developer/07-persistence.md` 7.1) with nothing proving
# it, which is exactly the shape the gate-registry rule exists to prevent.
# ---------------------------------------------------------------------------

_DECISION = "Rating: Buy\nEnter at $189-192, 6% portfolio cap."


@pytest.fixture()
def default_memory_log(tmp_path, monkeypatch):
    """The shared default, redirected, so the derived paths stay in tmp_path."""
    default = tmp_path / "memory" / "trading_memory.md"
    monkeypatch.setitem(batch.DEFAULT_CONFIG, "memory_log_path", str(default))
    return default


def test_per_symbol_memory_paths_are_distinct_beside_the_default(default_memory_log):
    aapl = Path(batch._per_symbol_memory_path("AAPL"))
    msft = Path(batch._per_symbol_memory_path("MSFT"))
    assert aapl != msft
    # Same directory as the shared file, and never the shared file itself.
    assert aapl.parent == msft.parent == default_memory_log.parent
    assert aapl != default_memory_log and msft != default_memory_log
    assert aapl.name == "AAPL.md" and msft.name == "MSFT.md"
    # A ticker that is legal on the wire but not a bare symbol still resolves.
    assert Path(batch._per_symbol_memory_path("BRK.B")).name == "BRK.B.md"


def test_per_symbol_memory_path_refuses_a_traversing_symbol(default_memory_log):
    for evil in ("../evil", "a/b", "..", ""):
        with pytest.raises(ValueError):
            batch._per_symbol_memory_path(evil)


def test_two_workers_memory_logs_do_not_see_each_others_entries(default_memory_log):
    aapl = TradingMemoryLog({"memory_log_path": batch._per_symbol_memory_path("AAPL")})
    msft = TradingMemoryLog({"memory_log_path": batch._per_symbol_memory_path("MSFT")})
    aapl.store_decision("AAPL", "2026-09-25", _DECISION)
    msft.store_decision("MSFT", "2026-09-25", _DECISION)
    aapl.store_decision("AAPL", "2026-09-26", _DECISION)

    assert [e["ticker"] for e in aapl.load_entries()] == ["AAPL", "AAPL"]
    assert [e["ticker"] for e in msft.load_entries()] == ["MSFT"]
    # ...and the shared default file was never written to by either worker.
    assert not default_memory_log.exists()
