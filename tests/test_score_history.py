"""The score-history store and the movement rule (WP-12 `P12-8`).

Acceptance (`docs/scores/ResearchLayerWiring.md` §7, verbatim): *first run: no
delta keys and `Movement: UNAVAILABLE`. Second run under a validated vector:
`trade_delta` against the printed prior date. Vector changed, or not yet
validated: still `UNAVAILABLE`.*

The invariant this defends is the owner's (§9 D2):

    no validated vector -> no delta -> no movement

and the reason is **vector validity, not `RESEARCH_ONLY`** — a delta implicitly
claims *both* observations are legitimate, and until the vector is measured and
promoted that claim is not grounded. So every withheld case is asserted
individually, with its reason, because "no delta" alone cannot distinguish a quiet
day from a rule doing its job.

`NA` rules: no prior row means **no delta keys at all**, never a zero.

Offline and deterministic: a `tmp_path` cache dir, no vendor call, no clock.
"""

from __future__ import annotations

import json

import pytest

from tradingagents.strategies import score_history as sh

TICKER = "MSFT"


def _composite(
    score: float | None = 76.75,
    status: str | None = "RESEARCH_ONLY",
    weights: dict | None = None,
    source: str = "owner",
) -> dict:
    return {
        "score": score,
        "coverage": 0.95,
        "status": status,
        "weights": weights or {
            "fundamental": 0.40,
            "technical": 0.25,
            "regime": 0.15,
            "risk": 0.20,
        },
        "weights_source": source,
    }


# ---------------------------------------------------------------------------
# the store
# ---------------------------------------------------------------------------


def test_a_row_is_written_per_scored_date_and_the_vector_travels_with_it(tmp_path):
    row = sh.record_score(TICKER, "2026-09-11", _composite(73.20), tmp_path)
    assert row is not None
    assert row["date"] == "2026-09-11"
    assert row["score"] == 73.20
    assert row["vector"] == sh.vector_key(_composite(73.20))
    assert row["status"] == "RESEARCH_ONLY"

    rows = sh.read_history(TICKER, tmp_path)
    assert len(rows) == 1
    assert rows[0]["vector"] == row["vector"]


def test_re_running_the_same_date_does_not_rewrite_history(tmp_path):
    """One row per scored run date: an observation is never silently replaced."""
    sh.record_score(TICKER, "2026-09-11", _composite(73.20), tmp_path)
    again = sh.record_score(TICKER, "2026-09-11", _composite(99.0), tmp_path)
    assert again is None
    assert [r["score"] for r in sh.read_history(TICKER, tmp_path)] == [73.20]


def test_history_is_read_oldest_first_and_a_corrupt_line_is_skipped(tmp_path):
    path = sh.history_path(TICKER, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"date": "2026-09-04", "score": 70.0, "vector": "v"})
        + "\n{not json\n"
        + json.dumps({"date": "2026-09-11", "score": 73.2, "vector": "v"})
        + "\n",
        encoding="utf-8",
    )
    assert [r["date"] for r in sh.read_history(TICKER, tmp_path)] == [
        "2026-09-04",
        "2026-09-11",
    ]


def test_a_composite_with_no_score_records_nothing(tmp_path):
    assert sh.record_score(TICKER, "2026-09-11", {"score": None}, tmp_path) is None
    assert sh.record_score(TICKER, None, _composite(), tmp_path) is None
    assert sh.read_history(TICKER, tmp_path) == []


# ---------------------------------------------------------------------------
# the movement rule — every withheld case names its reason
# ---------------------------------------------------------------------------


def test_the_first_run_has_no_movement_and_says_why(tmp_path):
    out = sh.score_movement(
        TICKER, "2026-09-11", _composite(status="VALIDATED"), tmp_path
    )
    assert out["movement"] == sh.MOVEMENT_UNAVAILABLE
    assert out["reason"] == "no prior scored observation"
    assert out["delta"] is None and out["prev"] is None


def test_an_unvalidated_vector_withholds_the_delta_even_with_a_prior_row(tmp_path):
    """§9 D2's hard invariant: `no validated vector -> no delta -> no movement`.

    The prior row exists and the vector is identical — the *only* thing missing
    is the promotion, and that alone is enough to withhold the delta.
    """
    sh.record_score(TICKER, "2026-09-11", _composite(73.20), tmp_path)
    out = sh.score_movement(
        TICKER, "2026-09-18", _composite(76.75, status="RESEARCH_ONLY"), tmp_path
    )
    assert out["movement"] == sh.MOVEMENT_UNAVAILABLE
    assert "not validated" in out["reason"]
    assert out["delta"] is None


def test_a_validated_vector_with_a_prior_row_produces_the_delta(tmp_path):
    validated = _composite(status="VALIDATED")
    sh.record_score(TICKER, "2026-09-11", {**validated, "score": 73.20}, tmp_path)
    out = sh.score_movement(
        TICKER, "2026-09-18", {**validated, "score": 76.75}, tmp_path
    )
    assert out["movement"] == sh.MOVEMENT_AVAILABLE
    assert out["prev"] == 73.20
    assert out["prev_date"] == "2026-09-11"
    assert out["delta"] == pytest.approx(3.55)


def test_a_changed_vector_withholds_the_delta(tmp_path):
    """A delta across a weight change is not a delta."""
    validated = _composite(status="VALIDATED")
    sh.record_score(TICKER, "2026-09-11", {**validated, "score": 73.20}, tmp_path)
    moved = _composite(
        status="VALIDATED",
        weights={
            "fundamental": 0.35,
            "technical": 0.30,
            "regime": 0.15,
            "risk": 0.20,
        },
    )
    out = sh.score_movement(TICKER, "2026-09-18", {**moved, "score": 76.75}, tmp_path)
    assert out["movement"] == sh.MOVEMENT_UNAVAILABLE
    assert out["reason"] == "the vector changed between the two observations"
    assert out["delta"] is None


def test_a_changed_weights_source_alone_is_a_changed_vector(tmp_path):
    """The owner's published vector and a measured one are not the same claim."""
    assert sh.vector_key(_composite(source="owner")) != sh.vector_key(
        _composite(source="measured")
    )


def test_the_delta_is_against_the_previous_observation_not_the_latest(tmp_path):
    validated = _composite(status="PRODUCTION")
    for date, score in (("2026-09-04", 70.0), ("2026-09-11", 73.20)):
        sh.record_score(TICKER, date, {**validated, "score": score}, tmp_path)
    out = sh.score_movement(
        TICKER, "2026-09-18", {**validated, "score": 76.75}, tmp_path
    )
    assert out["prev"] == 73.20
    assert out["prev_date"] == "2026-09-11"


def test_a_later_run_for_an_earlier_date_does_not_see_the_future(tmp_path):
    """The prior row is strictly earlier than the run date, never a later one."""
    validated = _composite(status="VALIDATED")
    sh.record_score(TICKER, "2026-09-18", {**validated, "score": 76.75}, tmp_path)
    out = sh.score_movement(
        TICKER, "2026-09-11", {**validated, "score": 73.20}, tmp_path
    )
    assert out["movement"] == sh.MOVEMENT_UNAVAILABLE
    assert out["reason"] == "no prior scored observation"


def test_the_vector_key_is_stable_and_order_independent():
    a = _composite(weights={"fundamental": 0.4, "risk": 0.2})
    b = _composite(weights={"risk": 0.2, "fundamental": 0.4})
    assert sh.vector_key(a) == sh.vector_key(b)
    assert sh.vector_key(None) == "unknown|"


def test_only_a_promoted_rung_counts_as_validated():
    for status in ("RESEARCH_ONLY", None, "banana"):
        assert not sh.vector_validated(_composite(status=status)), status
    for status in ("VALIDATED", "CONTRACT_MIGRATION", "PRODUCTION"):
        assert sh.vector_validated(_composite(status=status)), status
