"""Hermetic tests for the context A/B harness (``scripts/context_ab.py``).

The harness answers "does sending more computed context make the agent more
accurate?" - so the measurement itself has to be trustworthy. These tests pin
its four load-bearing properties, with no vendor and no key:

* items come from the **live** surfaces and the **real** renders (so the
  question set cannot drift from what the agents actually see);
* the shortlist is deterministic and never hides the intended tool;
* the scorer can fail - and, equally, the harness reports "no effect" when the
  producer gives the same answer under both conditions (no false positives);
* the demo path detects a difference when one exists, so a flat result means a
  flat effect, never broken plumbing.
"""

from __future__ import annotations

import scripts.context_ab as ab


def test_tool_items_cover_the_live_surfaces_without_naming_the_answer():
    items = ab.tool_items(limit=0)
    assert len(items) >= 50, "the item set collapsed - surfaces or docstrings changed"
    surfaces = ab._surfaces()
    for item in items:
        assert item.tool in {t.name for t in surfaces[item.surface]}
        # A question that names the tool measures copying, not selection.
        assert item.tool not in item.question, f"{item.tool} leaks into its own question"
        assert len(item.claim) > 3


def test_shortlist_is_deterministic_and_keeps_the_intended_tool():
    surface = ab._surfaces()["market"]
    intended = next(t.name for t in surface if t.name == "get_pair_risk")
    first = [t.name for t in ab.shortlist(surface, intended, k=8, seed=7)]
    again = [t.name for t in ab.shortlist(surface, intended, k=8, seed=7)]
    assert first == again
    assert intended in first
    assert len(first) == 8 and len(set(first)) == 8
    assert set(first) <= {t.name for t in surface}
    other = [t.name for t in ab.shortlist(surface, intended, k=8, seed=8)]
    assert other != first, "the seed must actually change the distractors"


def test_score_choice_normalizes_and_rejects_wrong_or_missing():
    assert ab.score_choice("get_pair_risk", "get_pair_risk")
    assert ab.score_choice(" Get_Pair_Risk ", "get_pair_risk")
    assert not ab.score_choice("get_pair_trade_signal", "get_pair_risk")
    assert not ab.score_choice(None, "get_pair_risk")
    assert not ab.score_choice("", "get_pair_risk")


def test_mcnemar_exact_matches_hand_computed_values():
    assert ab.mcnemar_exact(0, 0) == 1.0
    assert ab.mcnemar_exact(5, 5) == 1.0
    # 2 * (C(10,0)) / 2**10
    assert abs(ab.mcnemar_exact(10, 0) - 2 / 1024) < 1e-12
    # One-sided-ish magnitudes: more discordant pairs on one side is stronger.
    assert ab.mcnemar_exact(12, 1) < ab.mcnemar_exact(8, 3) < ab.mcnemar_exact(5, 5)


def test_read_items_ground_their_own_expectations():
    items = ab.read_items()
    assert len(items) >= 6, "the renders stopped carrying the measured rows"
    for item in items:
        assert item.required, item.name
        for token in item.required:
            assert ab._canon_number(token).lower() in ab._canon_text(item.block).lower(), (
                f"{item.name} expects {token!r}, which its own block does not contain"
            )
        assert not ab.score_read(item.without_block(), item.required), (
            f"{item.name} is answerable without the block - it measures nothing"
        )


def test_score_read_requires_every_number_and_tolerates_formatting():
    assert ab.score_read("verdict WARN, size 3.0%, dd 4.20%", ("WARN", "3.0%", "4.2%"))
    assert not ab.score_read("verdict WARN, size 3.0%", ("WARN", "3.0%", "4.2%"))
    assert not ab.score_read("I think risk is moderate", ("WARN",))


def test_ungrounded_figures_flags_invented_numbers_only():
    block = "risk snapshot: verdict=WARN size=3.0% dd=4.2%"
    grounded = "The block says size 3.0% and dd 4.2% with verdict WARN."
    assert ab.ungrounded_figures(grounded, block) == []
    invented = "The block says the stop is 12.5% and the size is 3.0%."
    assert ab.ungrounded_figures(invented, block) == ["12.5%"]
    # With no context at all, every figure is ungrounded - that is the point.
    assert ab.ungrounded_figures("roughly 105.2 and 3.0%", "") == ["105.2", "3.0%"]


def test_demo_run_detects_a_difference_and_labels_itself_synthetic(capsys):
    assert ab.main(["--demo", "--limit", "12"]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC" in out
    assert "McNemar p=" in out
    experiments = {
        "tools": ab.run_tools(ab.tool_items(limit=12), ab.demo_tool_producer(ab.tool_items(limit=12))),
        "reads": ab.run_reads(ab.read_items(), ab.demo_read_producer()),
    }
    # The synthetic producers do differ, so a flat result would mean the
    # plumbing is broken (the property this test defends).
    assert experiments["reads"].b() > 0
    assert experiments["tools"].accuracy("a") > experiments["tools"].accuracy("b")


def test_harness_reports_no_effect_when_the_producer_is_constant():
    """A producer unchanged by the condition must score as no effect."""
    items = ab.read_items()
    block = items[0].block
    answer = " ".join(items[0].required)

    def constant(_question: str, _context: str) -> str:
        return answer

    exp = ab.run_reads(items, constant)
    # The producer answers identically whatever the condition: the score may be
    # non-zero (the answer happens to ground one item) but it must be the SAME
    # in both conditions, so no effect can be claimed.
    assert exp.accuracy("a") == exp.accuracy("b")
    assert exp.b() == 0 and exp.c() == 0
    assert ab.mcnemar_exact(exp.b(), exp.c()) == 1.0
    assert "did not change" in ab.verdict([exp], synthetic=True)
    assert block  # the fixture is real, not empty
