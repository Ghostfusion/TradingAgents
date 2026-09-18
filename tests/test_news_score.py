"""`NewsScore` (WP-6): the absent categories, novelty, and the boundary.

Covers the plan's acceptance list (`docs/scores/IMPLEMENTATION_PLAN.md` §5.6 and
Phase D): (a) a repeated headline within the window scores lower than a
first-seen one; (b) relevance alone cannot raise the composite - the two are
independent inputs; (c) no `sentiment.py` aggregation function is imported by the
news path; (d) the five absent categories print `NA` with a reason, never 0;
(e) with the five fed `None` the score is `None` at 0% coverage.

Offline and deterministic: every value is synthetic, no vendor call.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tradingagents.strategies.news_score import (
    ABSENT_COMPONENTS,
    ABSENT_REASONS,
    COMPONENT_ORDER,
    COMPONENT_WEIGHTS,
    COMPONENTS,
    COMPOSITE_MIN_COVERAGE,
    NEWS_BANDS,
    RAMPS,
    SCALE_CONVENTION,
    align_components,
    component_weight_share,
    news_novelty,
    news_score,
)


def _present() -> dict:
    return {
        "relevance": 70.0,
        "novelty": 0.80,
        "earnings_surprise": 0.03,
        "corporate_events": 0.60,
        "analyst_revision": 0.20,
        "persistence": 1.00,
    }


# --------------------------------------------------------------------------
# (a) a repeated headline scores lower than a first-seen one
# --------------------------------------------------------------------------


def test_a_repeated_headline_has_lower_novelty_than_a_first_seen_one() -> None:
    first = news_novelty([{"title": "Company wins a major contract"},
                          {"title": "Analyst raises the price target"}])
    repeat = news_novelty([{"title": "Company wins a major contract"},
                           {"title": "Company WINS a major, CONTRACT!"}])
    assert first["novelty"] == pytest.approx(1.0)
    assert repeat["novelty"] == pytest.approx(0.5)
    assert repeat["novelty"] < first["novelty"]
    assert repeat["repeats"]


def test_the_repeat_is_only_a_repeat_within_the_window() -> None:
    arts = [
        {"title": "Old news", "timestamp": "2026-09-01T00:00:00"},
        {"title": "Old news", "timestamp": "2026-09-16T00:00:00"},
    ]
    assert news_novelty(arts, window=7)["novelty"] == pytest.approx(1.0)
    assert news_novelty(arts)["novelty"] == pytest.approx(0.5)


def test_the_novelty_component_moves_with_the_repeat() -> None:
    first = news_score({**_present(), "novelty": 1.0})["components"]["novelty"]["aligned"]
    repeat = news_score({**_present(), "novelty": 0.5})["components"]["novelty"]["aligned"]
    assert repeat < first


def test_empty_article_set_yields_no_novelty_not_zero() -> None:
    out = news_novelty([])
    assert out["novelty"] is None and out["n"] == 0
    assert "no usable headline" in out["basis"]


# --------------------------------------------------------------------------
# (b) relevance and materiality are independent; relevance alone cannot raise
# --------------------------------------------------------------------------


def test_relevance_alone_cannot_produce_a_composite() -> None:
    res = news_score({"relevance": 100.0})
    assert res["score"] is None
    assert "floor" in res["withheld"]


def test_materiality_is_never_inferred_from_relevance() -> None:
    hot = news_score({**_present(), "relevance": 100.0})
    assert hot["components"]["relevance"]["aligned"] == 100.0
    assert hot["components"]["materiality"]["aligned"] is None
    assert hot["components"]["materiality"]["reason"] == ABSENT_REASONS["materiality"]


def test_materiality_is_a_caller_supplied_independent_input() -> None:
    without = news_score({**_present(), "relevance": 100.0})
    with_mat = news_score({**_present(), "relevance": 100.0, "materiality": 0.10})
    assert with_mat["score"] > without["score"]
    assert with_mat["components"]["materiality"]["aligned"] is not None
    # the materiality leg does not move when relevance moves
    lo = news_score({**_present(), "relevance": 30.0, "materiality": 0.10})
    hi = news_score({**_present(), "relevance": 90.0, "materiality": 0.10})
    assert lo["aligned"]["materiality"] == hi["aligned"]["materiality"]


# --------------------------------------------------------------------------
# (d)/(e) the five absent categories print NA with a reason; feed them None
# --------------------------------------------------------------------------


def test_the_five_absent_categories_print_na_with_a_reason_never_zero() -> None:
    res = news_score({})
    assert len(ABSENT_COMPONENTS) == 5
    for name in ABSENT_COMPONENTS:
        entry = res["components"][name]
        assert entry["aligned"] is None, name  # never 0
        assert entry["reason"] == ABSENT_REASONS[name], name
        assert entry["reason"]  # non-empty
    assert set(res["absent_reasons"]) == set(ABSENT_COMPONENTS)
    assert "relevance" in res["absent_reasons"]["materiality"]


def test_with_the_five_absent_fed_none_the_score_is_none_at_zero_coverage() -> None:
    res = news_score({name: None for name in ABSENT_COMPONENTS})
    assert res["score"] is None
    assert res["coverage"] == 0.0
    assert len(res["absent_reasons"]) == 5


def test_all_none_returns_none_with_zero_coverage() -> None:
    res = news_score({})
    assert res["score"] is None and res["coverage"] == 0.0
    assert res["bands"] is None and res["status"] == "ADVISORY"


def test_a_missing_component_is_none_never_a_neutral_fifty() -> None:
    out = align_components({"relevance": 70.0})
    assert out["relevance"] is not None
    assert out["novelty"] is None
    assert set(out.values()) - {out["relevance"]} == {None}


def test_the_absent_legs_carry_their_owner_weight() -> None:
    for name in ABSENT_COMPONENTS:
        assert COMPONENT_WEIGHTS[name] > 0.0, name


# --------------------------------------------------------------------------
# coverage, weights and the attribution
# --------------------------------------------------------------------------


def test_the_present_components_score_the_weighted_mean_of_themselves() -> None:
    res = news_score(_present())
    present = {k: v for k, v in res["aligned"].items() if v is not None}
    assert set(present) == set(_present())
    num = sum(COMPONENT_WEIGHTS[k] * v for k, v in present.items())
    den = sum(COMPONENT_WEIGHTS[k] for k in present)
    assert res["score"] == pytest.approx(num / den, abs=0.005)
    assert res["coverage"] == pytest.approx(den / sum(COMPONENT_WEIGHTS.values()))


def test_a_supplied_weight_vector_is_used_and_printed() -> None:
    w = {name: 1.0 for name in COMPONENT_ORDER}
    w["novelty"] = 4.0
    res = news_score(_present(), weights=w)
    present = {k: v for k, v in res["aligned"].items() if v is not None}
    num = sum(w[k] * v for k, v in present.items())
    assert res["score"] == pytest.approx(num / sum(w[k] for k in present), abs=0.005)
    assert res["weights"] == w
    assert "supplied weights" in res["basis"]
    assert "owner weights" in news_score(_present())["basis"]


def test_the_basis_prints_the_absence_count_and_the_scale() -> None:
    res = news_score(_present())
    assert "5 absent with a reason" in res["basis"]
    assert res["scale"] == SCALE_CONVENTION
    assert "relevance is not materiality" in res["basis"]


def test_component_weight_share_renormalises() -> None:
    share = component_weight_share()
    assert sum(share.values()) == pytest.approx(1.0)
    assert share["fundamental_impact"] == pytest.approx(0.20)


def test_the_component_split_preserves_the_owner_category_totals() -> None:
    """The two partial categories are split, but their TOTALS are the owner's."""
    totals: dict[str, float] = {}
    for name, comp in COMPONENTS.items():
        totals[comp.category] = totals.get(comp.category, 0.0) + COMPONENT_WEIGHTS[name]
    assert totals == {
        "relevance_materiality": 20.0,
        "novelty": 15.0,
        "fundamental_impact": 20.0,
        "earnings_guidance": 15.0,
        "corporate_events": 10.0,
        "regulatory_legal": 5.0,
        "analyst_rating": 5.0,
        "macro_industry": 5.0,
        "persistence": 5.0,
    }
    assert sum(COMPONENT_WEIGHTS.values()) == pytest.approx(100.0)


def test_every_component_has_a_ramp_and_a_direction() -> None:
    for name, comp in COMPONENTS.items():
        assert name in RAMPS, name
        assert comp.direction in ("higher_better", "lower_better")


def test_news_bands_are_not_the_decision_rating_bands() -> None:
    from tradingagents.strategies.decision_guardrail import SCORE_BANDS

    assert tuple(NEWS_BANDS) != tuple(SCORE_BANDS)
    assert not {label for _, label in NEWS_BANDS} & {
        label for _, label in SCORE_BANDS
    }


# --------------------------------------------------------------------------
# the boundary: no sentiment.py aggregate, no sizing, no other engine
# --------------------------------------------------------------------------


def _module_references() -> tuple[set[str], list[str]]:
    tree = ast.parse(
        Path("tradingagents/strategies/news_score.py").read_text(encoding="utf-8")
    )
    referenced: set[str] = set()
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            referenced.update(a.name for a in node.names)
            imported_modules.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            referenced.add(node.module or "")
            imported_modules.append(node.module or "")
            referenced.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Attribute):
            parts = []
            cur = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                referenced.add(".".join(reversed(parts)))
    return referenced, imported_modules


def test_the_news_path_imports_no_sentiment_aggregation_function() -> None:
    refs, modules = _module_references()
    assert "sentiment" not in modules, modules
    aggregates = ("aggregate_weighted_sentiment", "aggregate_daily_sentiment",
                  "daily_sentiment_sma", "weighted_rolling_sentiment")
    for agg in aggregates:
        assert agg not in refs, agg


def test_the_module_imports_no_other_score_engine_or_event_code() -> None:
    refs, _ = _module_references()
    for other in ("sentiment_score", "fundamental_score", "technical_score",
                  "event_score", "events", "regime_score", "risk_score"):
        assert not any(other in r for r in refs), (other, refs)


def test_the_module_never_touches_the_sizing_or_gate_path() -> None:
    refs, _ = _module_references()
    for forbidden in ("sizing", "risk.sizing", "risk_multiplier", "knife_guard",
                      "position_size", "decision_guardrail"):
        assert not any(forbidden in r for r in refs), (forbidden, refs)


def test_the_composite_floor_is_below_the_component_set() -> None:
    assert COMPOSITE_MIN_COVERAGE <= len(COMPONENT_ORDER)
