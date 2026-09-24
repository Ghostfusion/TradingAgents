"""N5: the prompt-condition A/B harness (OFFLINE - ground rule 8).

The engine's prompt strings do not change: what changes is that a prompt edit
becomes ATTRIBUTABLE - two conditions produce two distinguishable ledger rows and
a per-condition accuracy table, and a run whose condition was not recorded is
`unavailable` rather than pooled into the total.

The harness is the deliverable and the framing explicitly is not: the paper's own
`n = 72` per cell and its sign flips across context windows are not evidence that
a framing effect exists, and nothing here asserts one.

Offline and deterministic: a temporary ledger directory, synthetic closes, no
LLM call, no network and no wall clock in any assertion.
"""

from __future__ import annotations

import tempfile

import pytest

from tradingagents.agents.utils.prompt_metrics import (
    PROMPT_CONDITION_KEY,
    condition_accuracy,
    condition_descriptor,
    record_condition_run,
)
from tradingagents.strategies import prediction_ledger as pl

#: The gate, passed directly (the harness reads it by its literal name).
ON = {"enable_prompt_condition_harness": True}

_PROMPT_A = "Rate the outlook. Respond with rating and confidence."
_PROMPT_B = (
    "Rate the outlook from the quantified evidence. Respond with rating and "
    "confidence."
)


def _arm(label: str, verdicts: list[bool], results_dir: str, *, prompt: str) -> dict:
    """Write one arm's ledger rows; return its ``closes_by_key`` for scoring.

    ``verdicts[i]`` True means a winning long outcome, False a losing one, so the
    per-condition accuracy is known by construction. The ticker is arm-prefixed
    so the two arms occupy distinct ledger rows.
    """
    condition = condition_descriptor(label, {"analyst_market": prompt})
    closes: dict = {}
    for i, win in enumerate(verdicts):
        ticker, date = f"{label.upper()}-{i}", f"2026-01-{i + 1:02d}"
        row = record_condition_run(
            condition, cfg=ON, ticker=ticker, date=date, rating="Buy",
            direction="long", entry=100.0, confidence=0.7, horizon_days=2,
            results_dir=results_dir,
        )
        assert row[PROMPT_CONDITION_KEY] == label
        closes[(ticker, date)] = [101.0 if win else 99.0]
    return closes


def test_condition_recorded_per_run() -> None:
    """Acceptance: two conditions -> two distinguishable rows and two accuracy
    numbers, each with its count; a run whose condition was not recorded is
    `unavailable`, never pooled into the total."""
    results_dir = tempfile.mkdtemp()
    closes: dict = {}
    closes.update(_arm("arm_a", [True, True, True, True, False, False],
                       results_dir, prompt=_PROMPT_A))
    closes.update(_arm("arm_b", [True, False, False, False, False, False],
                       results_dir, prompt=_PROMPT_B))
    # A run whose condition was NOT recorded - the live writer's own row shape.
    pl.log_decision(ticker="Z0", date="2026-01-07", rating="Buy", direction="long",
                    entry=100.0, horizon_days=2, results_dir=results_dir)
    closes[("Z0", "2026-01-07")] = [101.0]

    rows = pl.rows(results_dir)
    # two conditions -> two DISTINGUISHABLE rows
    assert {r[PROMPT_CONDITION_KEY] for r in rows} == {"arm_a", "arm_b", None}
    recorded = next(r for r in rows if r["ticker"] == "ARM_A-0")
    assert recorded["prompt_condition"] == "arm_a"
    # the prompt is versioned as a first-class input, so the row carries WHICH
    # prompt text produced it - not just the arm's name.
    assert recorded["prompt_version"] == condition_descriptor(
        "arm_a", {"analyst_market": _PROMPT_A}
    )["version_id"]

    out = condition_accuracy(pl.score_all(closes, results_dir), cfg=ON)
    conds = out["conditions"]
    assert set(conds) == {"arm_a", "arm_b"}
    assert conds["arm_a"]["n"] == 6 and conds["arm_b"]["n"] == 6
    assert conds["arm_a"]["accuracy"] == pytest.approx(4 / 6, abs=1e-4)
    assert conds["arm_b"]["accuracy"] == pytest.approx(1 / 6, abs=1e-4)
    # the two arms carry different prompt versions, and neither label spans two
    # prompt texts.
    assert conds["arm_a"]["versions"] != conds["arm_b"]["versions"]
    assert not conds["arm_a"]["version_conflict"]

    # the unrecorded run is unattributed, not folded into any arm's rate
    assert out["unattributed"]["no_condition"] == 1
    assert out["n_rows"] == 13 and out["n_scored"] == 12
    assert None not in conds

    # the floor: an arm below min_n reports its count, never a rate from noise
    floored = condition_accuracy(pl.score_all(closes, results_dir), cfg=ON, min_n=8)
    assert all(a["below_min_n"] and a["accuracy"] is None
               for a in floored["conditions"].values())


def test_the_harness_is_off_by_default_and_writes_nothing() -> None:
    """ADDITIVE and default-OFF: with the gate off no row is written and no arm
    is scored, so a gate-off run gains nothing."""
    results_dir = tempfile.mkdtemp()
    cond = condition_descriptor("arm_a", {"analyst_market": _PROMPT_A})

    refused = record_condition_run(cond, cfg={}, ticker="T0", date="2026-01-01",
                                   rating="Buy", results_dir=results_dir)
    assert refused["status"] == "unavailable"
    assert "enable_prompt_condition_harness" in refused["unavailable"]
    assert pl.rows(results_dir) == []

    off = condition_accuracy([], cfg={})
    assert off["status"] == "unavailable"
    assert off["conditions"] == {}
