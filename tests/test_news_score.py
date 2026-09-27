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
    FORM_EVENT_SCORES,
    GUIDANCE_RAMP,
    NEWS_BANDS,
    NEWS_CATEGORIES,
    NEWS_CATEGORY_ORDER,
    NEWS_CATEGORY_WEIGHTS,
    PERSISTENCE_MIN_PERIODS,
    RAMPS,
    SCALE_CONVENTION,
    align_components,
    component_weight_share,
    corporate_events_score,
    guidance_change_score,
    news_confidence,
    news_novelty,
    news_persistence,
    news_score,
    news_volume_acceleration,
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
    res = news_score(dict.fromkeys(ABSENT_COMPONENTS))
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
    w = dict.fromkeys(COMPONENT_ORDER, 1.0)
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
    assert len(COMPONENT_ORDER) >= COMPOSITE_MIN_COVERAGE


# --- the Alpha Vantage feed arrives as a JSON STRING, not a dict -------------


def test_the_av_news_reader_parses_the_json_string_the_vendor_returns(monkeypatch):
    """`_make_api_request` ALWAYS returns `response_text` - a JSON STRING
    (`dataflows/alpha_vantage_common.py:120`) - so its declared `dict | str`
    return is always the `str` branch. An `isinstance(raw, dict)` test therefore
    never passed, and this reader returned `[]` on every call for every symbol
    and date: the vendor served ~50 articles and the type check discarded all of
    them, which is why NewsScore reported "no news producer measured" and could
    never measure. The fundamentals sibling documents the same contract
    (`alpha_vantage_fundamentals.py:9`).
    """
    import json

    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import alpha_vantage_news as avn

    feed = [{"title": "Qualcomm joins WEDA", "overall_sentiment_score": 0.31}]
    monkeypatch.setattr(avn, "get_news", lambda *a, **k: json.dumps({"feed": feed}))
    assert at._av_news_articles("QCOM", "2026-08-20", "2026-09-19") == feed


def test_the_av_news_reader_still_accepts_a_dict_and_rejects_junk(monkeypatch):
    """The tolerant shape: a dict (some callers parse first) works, and a body
    that is not JSON is an empty feed rather than an exception."""
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import alpha_vantage_news as avn

    feed = [{"title": "x"}]
    monkeypatch.setattr(avn, "get_news", lambda *a, **k: {"feed": feed})
    assert at._av_news_articles("QCOM", "2026-08-20", "2026-09-19") == feed

    monkeypatch.setattr(avn, "get_news", lambda *a, **k: "not json at all")
    assert at._av_news_articles("QCOM", "2026-08-20", "2026-09-19") == []

    monkeypatch.setattr(avn, "get_news", lambda *a, **k: '{"Information": "rate limit"}')
    assert at._av_news_articles("QCOM", "2026-08-20", "2026-09-19") == []


# ---------------------------------------------------------------------------
# The assembler leg this engine declares: persistence
# ---------------------------------------------------------------------------


def _mention_points(*pairs):
    return [{"date": d, "score": 0.1, "n": n} for d, n in pairs]


def test_persistence_is_assembled_from_the_mention_count_series(monkeypatch) -> None:
    """`news_score` declares persistence against `sentiment.mention_volume`, and
    the leg stayed absent on the claim that no per-day count series existed. It
    does: `_sentiment_points_with_source` -> `daily_sentiment_sma` returns `n`
    per calendar day."""
    from tradingagents.agents.utils import analysis_tools as at

    _silence_leaf(monkeypatch)
    points = _mention_points(("2026-09-01", 2), ("2026-09-02", 2),
                             ("2026-09-03", 2), ("2026-09-04", 8))
    monkeypatch.setattr(at, "_sentiment_points_with_source",
                        lambda *a, **k: (points, "eodhd"))

    vals = at._news_components("PERS", "2026-09-04")
    # the headline window is EMPTY here on purpose: mentions and headlines are
    # different feeds, so an empty news set must not withhold the attention leg
    assert vals["persistence"] == pytest.approx(8 / 2.0)


def test_persistence_stays_absent_without_a_mention_series(monkeypatch) -> None:
    from tradingagents.agents.utils import analysis_tools as at

    _silence_leaf(monkeypatch)
    monkeypatch.setattr(at, "_sentiment_points_with_source", lambda *a, **k: ([], "unit"))

    assert "persistence" not in at._news_components("PERS", "2026-09-04")


# ---------------------------------------------------------------------------
# The assembler legs this engine declares: materiality, corporate events,
# guidance change
# ---------------------------------------------------------------------------


def _silence_leaf(monkeypatch) -> None:
    """Every live producer `_news_components` reaches, stubbed to "nothing".

    The leaf is offline by construction (no vendor call in a test), and the SEC
    filings reader it now consults is stubbed too - the *tests* would otherwise
    resolve a CIK over the network. Individual tests override the leg under test.
    """
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import config as cfg_mod, sec_edgar, yfinance_sector
    from tradingagents.strategies import analyst_revisions as ar

    monkeypatch.setattr(at, "_av_news_articles", lambda *a, **k: [])
    monkeypatch.setattr(at, "_catalyst_snapshot", lambda *a, **k: {})
    monkeypatch.setattr(at, "_sentiment_points_with_source", lambda *a, **k: ([], "unit"))
    monkeypatch.setattr(ar, "revision_ratio", lambda *a, **k: {})
    monkeypatch.setattr(sec_edgar, "recent_filing_forms", lambda *a, **k: [])
    # the sector label resolves over a vendor chain (FMP -> Finnhub -> yfinance)
    monkeypatch.setattr(yfinance_sector, "fetch_sector", lambda *a, **k: None)
    monkeypatch.setattr(cfg_mod, "get_config", lambda: {"enable_benzinga_surface": False})


def test_materiality_and_surprise_read_the_one_catalyst_snapshot(monkeypatch) -> None:
    """NEWS-1: the 20-weight materiality row is EventScore's own number.

    `catalyst.build_catalyst_snapshot` already carries `implied_move` - the
    figure the event engine reads - so the news leaf consumes it (owner Q6)
    instead of leaving the component caller-supplied forever. The same snapshot
    supplies the surprise leg: **the old call passed the snapshot DICT to
    `last_earnings_surprise`, which takes the vendor calendar LIST**, so every
    row was a `str` and the surprise leg could never measure at all.
    """
    from tradingagents.agents.utils import analysis_tools as at

    _silence_leaf(monkeypatch)
    monkeypatch.setattr(
        at,
        "_catalyst_snapshot",
        lambda *a, **k: {"implied_move": 0.042, "last_surprise": {"surprise": 0.015}},
    )

    vals = at._news_components("MAT", "2026-09-04")
    assert vals["materiality"] == pytest.approx(0.042)
    assert vals["earnings_surprise"] == pytest.approx(0.015)


def test_materiality_stays_absent_without_an_implied_move(monkeypatch) -> None:
    from tradingagents.agents.utils import analysis_tools as at

    _silence_leaf(monkeypatch)
    monkeypatch.setattr(at, "_catalyst_snapshot", lambda *a, **k: {"implied_move": None})

    assert "materiality" not in at._news_components("MAT", "2026-09-04")


def test_corporate_events_are_typed_from_the_recent_filings(monkeypatch) -> None:
    """NEWS-4: the declared form vocabulary (`sec_edgar._FORM_LABELS` ->
    `FORM_EVENT_SCORES`) reaches the engine through `recent_filing_forms`."""
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import sec_edgar

    _silence_leaf(monkeypatch)
    monkeypatch.setattr(
        sec_edgar,
        "recent_filing_forms",
        lambda *a, **k: [
            {"form": "10-Q", "date": "2026-09-01"},
            {"form": "8-K", "date": "2026-09-02"},
        ],
    )

    vals = at._news_components("FILER", "2026-09-04")
    # the most material recognised form wins, not the mean of the set
    assert vals["corporate_events"] == pytest.approx(FORM_EVENT_SCORES["8-K"])


def test_corporate_events_ignore_a_filing_filed_after_the_trade_date(monkeypatch) -> None:
    """A historical run must not read a filing filed after `end` (lookahead)."""
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import sec_edgar

    _silence_leaf(monkeypatch)
    monkeypatch.setattr(
        sec_edgar,
        "recent_filing_forms",
        lambda *a, **k: [{"form": "8-K", "date": "2026-09-10"}],
    )

    assert "corporate_events" not in at._news_components("FILER", "2026-09-04")


def test_guidance_change_is_wired_behind_the_benzinga_gate(monkeypatch) -> None:
    """NEWS-3: the gate-on route feeds the SIGNED midpoint change.

    The engine's own ramp for `guidance_change` is a signed relative change, so
    the aligned 0-100 the producer also returns is NOT what the leaf passes.
    """
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import benzinga, config as cfg_mod

    _silence_leaf(monkeypatch)
    monkeypatch.setattr(
        cfg_mod, "get_config", lambda: {"enable_benzinga_surface": True}
    )
    monkeypatch.setattr(
        benzinga,
        "guidance_revision_rows",
        lambda *a, **k: [
            {
                "revenue_guidance_min": 100.0,
                "revenue_guidance_max": 120.0,
                "revenue_guidance_prior_min": 80.0,
                "revenue_guidance_prior_max": 100.0,
            }
        ],
    )

    vals = at._news_components("GUID", "2026-09-04")
    # (110 - 90) / 90 = +0.2222: a raise, signed, not the saturated 100
    assert vals["guidance_change"] == pytest.approx(0.2222, abs=1e-4)


def test_guidance_change_stays_absent_with_the_gate_off(monkeypatch) -> None:
    from tradingagents.agents.utils import analysis_tools as at

    _silence_leaf(monkeypatch)  # get_config -> enable_benzinga_surface False

    assert "guidance_change" not in at._news_components("GUID", "2026-09-04")


# ---------------------------------------------------------------------------
# D-1: the `categories` key both renderers read
# ---------------------------------------------------------------------------


def test_the_categories_key_covers_every_declared_owner_category() -> None:
    res = news_score(_present())
    assert set(res["categories"]) == set(NEWS_CATEGORY_ORDER)
    assert set(res["categories"]) == set(NEWS_CATEGORIES)


def test_every_category_block_mirrors_the_sentiment_score_shape() -> None:
    res = news_score(_present())
    for cat, entry in res["categories"].items():
        for key in ("score", "coverage", "floor", "withheld", "band", "weight",
                    "category", "raw_directions"):
            assert key in entry, (cat, key)
        assert entry["category"] == cat
        assert entry["weight"] == pytest.approx(NEWS_CATEGORY_WEIGHTS[cat])


def test_an_unmeasurable_category_carries_a_withheld_reason() -> None:
    res = news_score({})
    for cat, entry in res["categories"].items():
        assert entry["score"] is None, cat
        assert entry["withheld"], cat
        assert "floor" in entry["withheld"], cat


def test_a_two_component_category_scores_from_one_measured_leg() -> None:
    # relevance present, materiality absent: the category still scores, and the
    # absent leg lowers the category coverage rather than counting as a zero
    res = news_score({"relevance": 70.0})
    cat = res["categories"]["relevance_materiality"]
    assert cat["score"] == pytest.approx(
        align_components({"relevance": 70.0})["relevance"], abs=0.005
    )
    assert cat["coverage"] == pytest.approx(0.5)
    assert "materiality" in cat["components"]


# ---------------------------------------------------------------------------
# NEWS-8: news-volume acceleration (the first difference)
# ---------------------------------------------------------------------------


def test_a_flat_count_series_scores_zero_acceleration() -> None:
    out = news_volume_acceleration([{"n": 3}, {"n": 3}, {"n": 3}, {"n": 3}])
    assert out is not None
    assert out["acceleration"] == 0.0   # a measurement, not a gap
    assert out["normalized"] is None    # sigma_V == 0: no scale to normalise by
    assert out["sigma"] == 0.0


def test_news_volume_acceleration_is_the_first_difference() -> None:
    out = news_volume_acceleration([{"n": 2}, {"n": 2}, {"n": 8}])
    assert out is not None
    assert out["acceleration"] == pytest.approx(6.0)
    assert out["normalized"] is not None


def test_news_volume_acceleration_refuses_below_two_counts() -> None:
    assert news_volume_acceleration([]) is None
    assert news_volume_acceleration([{"n": 5}]) is None
    assert news_volume_acceleration([{"n": None}]) is None


# ---------------------------------------------------------------------------
# NEWS-10: the library's persistence quantity
# ---------------------------------------------------------------------------


def test_news_persistence_positive_share_and_multi_lambda_decay() -> None:
    points = [{"score": s} for s in (0.1, -0.2, 0.3, 0.4, -0.1)]
    out = news_persistence(points)
    assert out is not None
    assert out["positive_share"] == pytest.approx(0.6)
    assert 0.0 <= out["decayed_persistence"] <= 1.0
    assert out["half_lives"] == [7.0, 14.0, 30.0]


def test_news_persistence_decays_older_positive_periods() -> None:
    # same positive share (3 of 5), but the positives sit at the RECENT end in
    # one series and the OLD end in the other: the multi-lambda kernel must
    # score the recent one higher
    recent = news_persistence([{"score": s} for s in (0.0, 0.0, 1.0, 1.0, 1.0)])
    older = news_persistence([{"score": s} for s in (1.0, 1.0, 1.0, 0.0, 0.0)])
    assert recent["positive_share"] == older["positive_share"] == pytest.approx(0.6)
    assert recent["decayed_persistence"] > older["decayed_persistence"]


def test_news_persistence_refuses_below_the_stated_minimum() -> None:
    assert PERSISTENCE_MIN_PERIODS > 1
    assert news_persistence([{"score": 0.1}] * (PERSISTENCE_MIN_PERIODS - 1)) is None
    assert news_persistence([]) is None


# ---------------------------------------------------------------------------
# NEWS-11: a first-class NewsConfidence output, distinct from coverage
# ---------------------------------------------------------------------------


def test_news_confidence_names_its_recipe_and_moves_with_the_sample() -> None:
    thin = news_confidence(1, 1)
    fat = news_confidence(7, 10)
    assert thin is not None and fat is not None
    for key in ("confidence", "sample_size", "positive", "negative",
                "positive_share", "c_n", "wilson_low", "wilson_high",
                "wilson_width", "bayesian_mean"):
        assert key in thin, key
    assert thin["sample_size"] == 1 and fat["sample_size"] == 10
    assert thin["confidence"] < fat["confidence"]
    assert "Wilson" in thin["basis"] and "C_N" in thin["basis"]


def test_news_confidence_refuses_an_empty_sample() -> None:
    assert news_confidence(0, 0) is None
    assert news_confidence(None, None) is None


def test_the_scores_confidence_key_is_not_the_coverage_value() -> None:
    conf = news_confidence(7, 10)
    res = news_score(_present(), confidence=conf)
    assert res["confidence"]["sample_size"] == 10
    # coverage is a weight share; confidence is what the sample supports. They
    # are different units and the result never presents one as the other.
    assert res["confidence"]["confidence"] != res["coverage"]
    assert "WEIGHT SHARE" in res["basis"]
    without = news_score(_present())
    assert without["coverage"] == res["coverage"]
    assert without["confidence"] is None


# ---------------------------------------------------------------------------
# NEWS-4 / D-2: corporate_events from the declared form table
# ---------------------------------------------------------------------------


def test_corporate_events_score_uses_the_declared_table() -> None:
    out = corporate_events_score(["8-K", "10-Q"])
    assert out["score"] == pytest.approx(FORM_EVENT_SCORES["8-K"])
    assert set(out["forms"]) == {"8-K", "10-Q"}
    assert out["mean"] == pytest.approx(
        (FORM_EVENT_SCORES["8-K"] + FORM_EVENT_SCORES["10-Q"]) / 2
    )
    assert "DECLARED" in out["basis"]


def test_corporate_events_score_refuses_empty_and_all_unknown() -> None:
    empty = corporate_events_score([])
    assert empty["score"] is None
    assert "no filed forms" in empty["reason"]
    unknown = corporate_events_score(["XYZ", "ZZZ"])
    assert unknown["score"] is None
    assert "no recognised SEC form" in unknown["reason"]
    assert set(unknown["ignored"]) == {"XYZ", "ZZZ"}


def test_corporate_events_score_ignores_unknown_forms_but_keeps_known() -> None:
    out = corporate_events_score(["8-K", "XYZ"])
    assert out["score"] == pytest.approx(FORM_EVENT_SCORES["8-K"])
    assert out["ignored"] == ["XYZ"]


def test_corporate_events_score_windows_dated_rows_only() -> None:
    rows = [
        {"form": "8-K", "date": "2026-09-01"},
        {"form": "10-Q", "date": "2026-06-01"},
    ]
    out = corporate_events_score(rows, window_days=30)
    assert out["forms"] == ["8-K"]
    assert out["window_days"] == 30


# ---------------------------------------------------------------------------
# NEWS-3: guidance_change from the (gated) guidance revision rows
# ---------------------------------------------------------------------------


def test_guidance_change_scores_a_raise_above_50_and_a_cut_below() -> None:
    up = guidance_change_score([{
        "revenue_guidance_min": 110.0, "revenue_guidance_max": 130.0,
        "revenue_guidance_prior_min": 90.0, "revenue_guidance_prior_max": 110.0,
    }])
    assert up["score"] > 50.0
    assert up["revenue_change"] == pytest.approx(0.20)
    assert up["ramp"] == list(GUIDANCE_RAMP)
    down = guidance_change_score([{
        "eps_guidance_min": 0.9, "eps_guidance_max": 1.1,
        "eps_guidance_prior_min": 1.2, "eps_guidance_prior_max": 1.4,
    }])
    assert down["score"] < 50.0
    flat = guidance_change_score([{
        "revenue_guidance_min": 100.0, "revenue_guidance_max": 120.0,
        "revenue_guidance_prior_min": 100.0, "revenue_guidance_prior_max": 120.0,
    }])
    assert flat["score"] == pytest.approx(50.0)


def test_guidance_change_refuses_without_a_prior_range() -> None:
    forward_only = guidance_change_score([{
        "revenue_guidance_min": 110.0, "revenue_guidance_max": 130.0,
    }])
    assert forward_only["score"] is None
    assert "prior range" in forward_only["reason"]
    assert guidance_change_score([])["score"] is None


def test_the_industry_shock_leg_is_the_sector_relative_move(monkeypatch) -> None:
    """NEWS-7: the leg is measured against the ticker's SECTOR ETF, not breadth."""
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.dataflows import yfinance_sector

    _silence_leaf(monkeypatch)
    monkeypatch.setattr(
        yfinance_sector, "fetch_sector", lambda *a, **k: "Technology"
    )
    # the stock's daily returns beat a flat sector's, with dispersion to
    # standardise against
    stock = [100.0, 103.0, 102.0, 106.0, 105.0, 110.0]
    sector = [100.0] * 6
    monkeypatch.setattr(
        at,
        "_closes_upto",
        lambda ticker, end: stock if ticker == "SHOCK" else sector,
    )

    vals = at._news_components("SHOCK", "2026-09-04", days=5)
    assert vals["industry_shock"] > 0


def test_the_industry_shock_leg_stays_absent_without_a_resolvable_sector(monkeypatch) -> None:
    from tradingagents.agents.utils import analysis_tools as at

    _silence_leaf(monkeypatch)  # fetch_sector -> None

    assert "industry_shock" not in at._news_components("SHOCK", "2026-09-04")
