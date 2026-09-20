"""Phase 1: the decision factorial (docs/design_decision_context.md section 12).

The experiment asks whether context volume changes the DECISION, and the doc is
explicit that the answer must be named correctly:

- `C2 - C1` isolates volume ONLY if C1 preserves C2's evidence and differs in
  length, so the retention table decides whether a contrast is a volume effect, a
  content-retention effect, or no ablation at all;
- a paired transition matrix is more informative than CCI, because aggregates
  cannot separate a systematic directional -> hold drift from churn in both
  directions;
- the arms must consume the SAME deterministic evidence snapshot, or the pair is
  invalid rather than merely noisy.

These tests pin the instrument, not the model. Every one of them failed at some
point during the build, in the order they appear.
"""

from __future__ import annotations

import pytest

import scripts.context_ab as ab

pytestmark = pytest.mark.timeout(60)


def _item(prose: str = "", packet: str = "", snap: dict | None = None) -> ab.DecisionItem:
    prose = prose or (
        "## Section A\nrevenue_growth=5.00%  beat consensus\n"
        "margin=41.20%  miss consensus\n"
        "free_text_without_any_number_here\n"
        "cash=12.30B\n"
        "another_prose_line_with_no_figure\n"
    )
    packet = packet or "[RUN STRUCTURE]\n\n[TRADE_SCORE]\n  trade_score: 59.46\n"
    return ab.DecisionItem(
        name="t1", ticker="TST", as_of="2026-09-20",
        arms={"c1": ab.compact_prose(prose), "c2": prose,
              "p1": ab.compact_prose(packet), "p2": packet},
        snapshot=snap or {
            "snapshot_id": "TST_2026-09-20",
            "data_snapshot_hash": "d", "engine_output_hash": "e",
            "model_parameters_hash": "m",
        },
    )


class TestCompaction:
    def test_evidence_mode_keeps_every_evidential_line(self):
        text = "revenue=5.00%\nplain prose with no figure\ncash=12.30B\n"
        out = ab.compact_prose(text)
        assert "revenue=5.00%" in out
        assert "cash=12.30B" in out
        assert "plain prose with no figure" not in out

    def test_evidence_mode_retains_every_figure(self):
        text = "a=1.00%\nb=2.00%\nc=3.00%\nprose\n"
        assert ab._figures(ab.compact_prose(text)) == ab._figures(text)

    def test_bounded_mode_is_the_doc_construction_and_loses_evidence(self):
        # The doc's literal "bounded to first/last rows" DOES drop evidence, which
        # is why it cannot produce a volume effect - the retention table proves it.
        text = "\n".join(f"row_{i}={i}.00%" for i in range(12))
        out = ab.compact_prose(text, head=2, tail=2, mode="bounded")
        assert "elided" in out
        assert len(ab._figures(out)) < len(ab._figures(text))


class TestRetention:
    def test_table_counts_both_sides_and_a_percentage(self):
        c2 = "a=1.00%\nb=2.00%\n"
        c1 = "a=1.00%\n"
        table = ab.retention_table(c2, c1)
        assert table["unique_figures"]["c2"] == 2
        assert table["unique_figures"]["c1"] == 1
        assert table["unique_figures"]["retained_pct"] == 50.0
        assert table["_chars"]["retained_pct"] is not None

    def test_no_ablation_is_reported_as_no_ablation(self):
        # The first draft checked retention only, and called a 2-character
        # difference a "context-volume effect". Two identical-size contexts
        # measure nothing, and saying otherwise is the vacuous result the doc
        # warns about.
        same = "a=1.00%\nb=2.00%\n"
        verdict = ab.retention_verdict(ab.retention_table(same, same))
        assert "NO VOLUME ABLATION AVAILABLE" in verdict

    def test_lost_evidence_is_named_content_retention_not_volume(self):
        c2 = "beat consensus\nbeat consensus\nbeat consensus\n" + "x=1.00%\n" * 20
        c1 = "beat consensus\n" + "x=1.00%\n" * 1
        verdict = ab.retention_verdict(ab.retention_table(c2, c1))
        assert "content-retention effect" in verdict

    def test_full_retention_with_a_real_drop_is_a_volume_effect(self):
        c2 = "a=1.00%\n" + "prose filler line\n" * 40
        c1 = ab.compact_prose(c2)
        verdict = ab.retention_verdict(ab.retention_table(c2, c1))
        assert "context-volume effect" in verdict


class TestTransitions:
    def test_matrix_and_directional_moves(self):
        t = ab.transition_matrix([("Buy", "Hold"), ("Buy", "Hold"), ("Sell", "Buy")])
        assert t["matrix"]["Buy -> Hold"] == 2
        assert t["directional"]["directional_to_hold"] == 2
        assert t["directional"]["bearish_to_bullish"] == 1

    def test_hold_to_directional_is_counted_separately(self):
        t = ab.transition_matrix([("Hold", "Buy")])
        assert t["directional"]["hold_to_directional"] == 1
        assert t["directional"]["directional_to_hold"] == 0

    def test_flip_rate_counts_changed_decisions_only(self):
        exp = ab.DecisionExperiment()
        exp.records = [
            ab.DecisionRecord(item="a", per_arm={"c1": {"llm_rating": "Buy"},
                                                 "c2": {"llm_rating": "Hold"}}),
            ab.DecisionRecord(item="b", per_arm={"c1": {"llm_rating": "Buy"},
                                                 "c2": {"llm_rating": "Buy"}}),
        ]
        assert exp.flip_rate("c1", "c2") == 0.5


class TestDistribution:
    def test_entropy_separates_directional_from_volatile(self):
        # The doc's two cases: same CCI, very different behaviour. The
        # distribution must tell them apart.
        flat = [{"llm_rating": r} for r in
                ["Buy"] * 10 + ["Hold"] * 80 + ["Sell"] * 10]
        volatile = [{"llm_rating": r} for r in
                    ["Buy"] * 20 + ["Hold"] * 60 + ["Sell"] * 20]
        d_flat = ab.decision_distribution(flat)
        d_vol = ab.decision_distribution(volatile)
        assert d_flat["p_no_trade"] > d_vol["p_no_trade"]
        assert d_vol["directional_entropy"] > d_flat["directional_entropy"]

    def test_unparseable_rating_is_not_defaulted_to_hold(self):
        d = ab.decision_distribution([{"llm_rating": None}, {"llm_rating": "Buy"}])
        assert d["n"] == 1
        assert d["hold"] == 0


class TestSnapshotInvariant:
    def test_a_missing_engine_hash_is_not_a_mismatch(self):
        # The first draft collapsed None == None into a mismatch and invalidated
        # 8 of 12 REAL snapshots whose runs predate the scorecard gate. All four
        # arms had consumed the same evidence; the check was demanding that the
        # snapshot be RICH when the invariant only requires it to be the SAME.
        snap = {"data_snapshot_hash": "d", "engine_output_hash": None,
                "model_parameters_hash": "m"}
        assert ab._snapshot_check(snap, dict(snap)) == "match"

    def test_a_genuinely_different_hash_is_a_mismatch(self):
        a = {"data_snapshot_hash": "d", "engine_output_hash": "e",
             "model_parameters_hash": "m"}
        b = dict(a, data_snapshot_hash="OTHER")
        assert ab._snapshot_check(a, b) == "mismatch"

    def test_one_sided_hash_is_a_mismatch(self):
        # One arm saw an engine output the other did not: a real disagreement.
        a = {"data_snapshot_hash": "d", "engine_output_hash": None,
             "model_parameters_hash": "m"}
        b = dict(a, engine_output_hash="e")
        assert ab._snapshot_check(a, b) == "mismatch"

    def test_no_identity_at_all_is_unverifiable_not_a_pass(self):
        empty = {"data_snapshot_hash": None, "engine_output_hash": None,
                 "model_parameters_hash": None}
        assert ab._snapshot_check(empty, dict(empty)) == "unverifiable"

    def test_a_mismatched_snapshot_invalidates_the_pair(self):
        item = _item()

        def producer(it, arm):
            snap = dict(it.snapshot)
            if arm == "c2":
                snap["data_snapshot_hash"] = "DIFFERENT"   # a market refresh
            return {"llm_rating": "Hold", "snapshot": snap}

        exp = ab.run_decisions([item], producer)
        assert exp.invalid == ["t1"]
        assert exp.records[0].invalid is True
        # An invalidated pair contributes nothing to the contrasts.
        assert exp.arm_records("c2") == []

    def test_an_unverifiable_pair_is_kept_and_flagged(self):
        item = _item(snap={"snapshot_id": None, "data_snapshot_hash": None,
                           "engine_output_hash": None, "model_parameters_hash": None})

        def producer(it, arm):
            return {"llm_rating": "Hold", "snapshot": dict(it.snapshot)}

        exp = ab.run_decisions([item], producer)
        assert exp.invalid == []
        assert exp.records[0].unverifiable is True
        assert "NO identity hash" in ab.format_decision_report(exp, "test")

    def test_matching_snapshots_stay_valid(self):
        def producer(it, arm):
            return {"llm_rating": "Hold", "snapshot": dict(it.snapshot)}

        exp = ab.run_decisions([_item()], producer)
        assert exp.invalid == []
        assert len(exp.records[0].per_arm) == 4


class TestProducers:
    def test_demo_producer_is_deterministic(self):
        item = _item()
        a = ab.demo_decision_producer(seed=5)(item, "c1")
        b = ab.demo_decision_producer(seed=5)(item, "c1")
        assert a["llm_rating"] == b["llm_rating"]
        assert a["snapshot"] == item.snapshot

    def test_parse_decision_reads_the_rating_line(self):
        got = ab.parse_decision("Rating: **Overweight**\nConfidence: 0.72\nReason: x")
        assert got["llm_rating"] == "Overweight"
        assert got["llm_confidence"] == 0.72

    def test_parse_decision_rejects_a_non_tier_word(self):
        # A rating the vocabulary does not contain is no rating, never a Hold.
        assert ab.parse_decision("Rating: StrongBuyish\n")["llm_rating"] is None

    def test_full_demo_run_reports_every_arm(self):
        exp = ab.run_decisions([_item()], ab.demo_decision_producer())
        text = ab.format_decision_report(exp, "test")
        for arm in ab.ARMS:
            assert ab.ARM_LABELS[arm] in text
        assert "paired transitions" in text
        assert "distribution" in text
        assert "grounding" in text
        assert "retention" in text


class TestGrounding:
    def test_an_unsupported_figure_is_counted(self):
        exp = ab.DecisionExperiment()
        exp.records = [ab.DecisionRecord(item="a", per_arm={
            "c1": {"answer": "Rating: Buy, target 999.99", "context": "price=100.00"},
            "c2": {"answer": "Rating: Buy", "context": "price=100.00"},
        })]
        assert exp.grounding("c1") == 1
        assert exp.grounding("c2") == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
