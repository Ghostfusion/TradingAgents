"""`SentimentScore` (WP-7): the pinned scale, the composite, the quadrant.

Covers the plan's acceptance list (`docs/scores/IMPLEMENTATION_PLAN.md` §5.6 and
Phase D): (a) a GDELT series and an EODHD series over the same window produce
comparable `sma_7d`/`innovation`, or the code refuses to mix them; (b) four
fixtures produce four distinct quadrant labels; (c) `mention_volume` (attention)
and the tone aggregate enter as **separate** components and are never summed;
(d) the gated producers are exercised so a default-off flag cannot hide a broken
path; (e) `NA` is not `0`.

Offline and deterministic: every value is synthetic, no vendor call.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from tradingagents.strategies.sentiment_score import (
    CANONICAL_SCALE,
    CATEGORY_COMPONENTS,
    CATEGORY_ORDER,
    CATEGORY_WEIGHTS,
    COMPONENTS,
    COMPOSITE_MIN_COVERAGE,
    CONFIRMATION_QUADRANTS,
    RAMPS,
    SCALE_CONVENTION,
    SCALE_TABLE,
    SCALE_UNIT,
    SENTIMENT_BANDS,
    TONE_COMPONENTS,
    align_components,
    category_score,
    category_weight_share,
    confirmation_quadrant,
    normalise_components,
    normalise_sentiment,
    sentiment_score,
)


def _full_values() -> dict:
    return {
        "weighted_tone": 0.20, "sma_7d": 0.15,
        "tone_innovation": 0.10, "tone_velocity": 0.02,
        "bull_share": 0.60, "neutral_share": 0.30,
        "inst_flow_z": 0.80, "revision_ratio": 0.20, "analyst_agreement": 0.60,
        "social_score": 0.30, "social_velocity": 1.00,
        "iv_skew": 1.00, "put_call_ratio": 1.00,
        "short_pct_float": 0.10, "dispersion": 0.40, "dispersion_agreement": 0.60,
        "crowd_ratio": 50.0, "mention_heat": 1.20,
    }


# --------------------------------------------------------------------------
# (a) the scale is pinned first, printed, and mixed sources are refused
# --------------------------------------------------------------------------


def test_gdelt_and_eodhd_reads_are_comparable_after_normalisation() -> None:
    """A GDELT -100..100 series normalises onto the same unit as an EODHD one."""
    assert normalise_sentiment(8.5, "gdelt")["value"] == pytest.approx(0.085, abs=1e-6)
    assert normalise_sentiment(0.085, "eodhd")["value"] == pytest.approx(0.085, abs=1e-6)
    assert normalise_sentiment(0.085, "alpha_vantage")["value"] == pytest.approx(0.085)

    gdelt = {"sma_7d": 15.0, "tone_innovation": 9.0}
    eodhd = {"sma_7d": 0.15, "tone_innovation": 0.09}
    g_norm, _, _ = normalise_components(gdelt, source="gdelt")
    e_norm, _, _ = normalise_components(eodhd, source="eodhd")
    for name in ("sma_7d", "tone_innovation"):
        assert align_components(g_norm)[name] == pytest.approx(
            align_components(e_norm)[name], abs=1e-6
        )


def test_an_unknown_source_is_refused_not_guessed() -> None:
    out = normalise_sentiment(0.4, "bloomberg")
    assert out["value"] is None and "unknown" in out["basis"]


def test_mixing_two_tone_sources_is_refused() -> None:
    vals = _full_values()
    vals["weighted_tone"] = 15.0   # a GDELT reading
    res = sentiment_score(
        vals, source={"weighted_tone": "gdelt", "sma_7d": "eodhd"}
    )
    assert res["score"] is None
    assert res["refused"] is True
    assert "refuses to mix" in res["withheld"]
    assert "gdelt" in res["withheld"] and "eodhd" in res["withheld"]


def test_the_scale_convention_is_printed_in_the_basis() -> None:
    res = sentiment_score(_full_values(), source="eodhd")
    assert "unit (-1..1)" in res["basis"]
    assert res["scale"]["convention"] == SCALE_CONVENTION
    assert res["scale"]["canonical"] == "unit (-1..1)"
    assert tuple(res["scale"]["table"]["gdelt"]) == SCALE_TABLE["gdelt"]
    assert res["components"]["weighted_tone"]["scale"]


def test_a_gdelt_sourced_composite_matches_an_eodhd_sourced_one() -> None:
    eodhd = sentiment_score(_full_values(), source="eodhd")
    vals = _full_values()
    for name in TONE_COMPONENTS:
        vals[name] = vals[name] * 100.0
    gdelt = sentiment_score(vals, source="gdelt")
    assert gdelt["score"] == pytest.approx(eodhd["score"], abs=0.01)


# --------------------------------------------------------------------------
# (b) the quadrant produces four distinct labels, never a collapse into two
# --------------------------------------------------------------------------


def test_four_fixtures_produce_four_distinct_quadrant_labels() -> None:
    got = {
        confirmation_quadrant(0.02, 0.10),
        confirmation_quadrant(0.02, -0.10),
        confirmation_quadrant(-0.02, -0.10),
        confirmation_quadrant(-0.02, 0.10),
    }
    assert got == set(CONFIRMATION_QUADRANTS)
    assert len(got) == 4


def test_quadrant_reads_words_booleans_and_dicts_too() -> None:
    assert confirmation_quadrant("rising", "bullish") == "confirm-up"
    assert confirmation_quadrant("falling", "bearish") == "confirm-down"
    assert confirmation_quadrant({"sign": 1}, {"direction": -1}) == "diverge-up"
    assert confirmation_quadrant(True, False) == "diverge-up"


def test_quadrant_never_fabricates_on_a_flat_or_missing_read() -> None:
    assert confirmation_quadrant(None, 0.1) is None
    assert confirmation_quadrant(0.0, 0.1) is None
    assert confirmation_quadrant(0.1, "neutral") is None
    assert confirmation_quadrant(float("nan"), 0.1) is None


def test_the_headline_quadrant_appears_on_the_score_when_a_price_read_is_given() -> None:
    res = sentiment_score(_full_values(), price_read=0.03)
    assert res["quadrant"] == confirmation_quadrant(0.03, _full_values()["tone_innovation"])


# --------------------------------------------------------------------------
# (c) attention and tone are separate rows, never summed
# --------------------------------------------------------------------------


def test_mention_heat_and_the_tone_legs_are_separate_components() -> None:
    assert "mention_heat" in COMPONENTS
    assert "weighted_tone" in COMPONENTS
    assert COMPONENTS["mention_heat"].category != COMPONENTS["weighted_tone"].category
    res = sentiment_score(_full_values())
    entry = res["components"]
    assert "mention_heat" in entry and "weighted_tone" in entry
    # changing attention does not move the tone legs
    loud = {**_full_values(), "mention_heat": 3.0}
    res2 = sentiment_score(loud)
    assert res2["aligned"]["weighted_tone"] == res["aligned"]["weighted_tone"]
    assert res2["aligned"]["mention_heat"] != res["aligned"]["mention_heat"]


def test_attention_and_tone_are_not_summed_into_one_number() -> None:
    """The two components are in different categories, so neither can stand in
    for the other in the composite."""
    tone_cat = COMPONENTS["weighted_tone"].category
    heat_cat = COMPONENTS["mention_heat"].category
    assert tone_cat != heat_cat
    assert "mention_heat" not in CATEGORY_COMPONENTS[tone_cat]
    assert "weighted_tone" not in CATEGORY_COMPONENTS[heat_cat]


# --------------------------------------------------------------------------
# (d) the gated producers are exercised
# --------------------------------------------------------------------------


def test_the_weighted_aggregation_producer_feeds_the_engine() -> None:
    """Exercises the path behind `enable_weighted_sentiment_agg`."""
    from tradingagents.strategies.sentiment import aggregate_weighted_sentiment

    arts = [
        {
            "title": f"Headline {i}",
            "time_published": "20260916T120000",
            "ticker_sentiment": [
                {"ticker": "TEST", "ticker_sentiment_score": 0.4,
                 "relevance_score": 80.0}
            ],
        }
        for i in range(4)
    ]
    rows = aggregate_weighted_sentiment(arts, "TEST")
    assert rows and rows[-1]["weighted"] is not None
    res = sentiment_score({**_full_values(), "weighted_tone": rows[-1]["weighted"]})
    assert res["components"]["weighted_tone"]["aligned"] is not None


def test_the_crowd_ratio_producer_feeds_the_engine() -> None:
    """Exercises the path behind `enable_crowd_ratio_bands`."""
    from tradingagents.strategies.sentiment import crowd_ratio

    row = crowd_ratio(70, 30)
    assert row and row.get("ratio") is not None
    res = sentiment_score({**_full_values(), "crowd_ratio": row["ratio"]})
    assert res["components"]["crowd_ratio"]["aligned"] is not None


# --------------------------------------------------------------------------
# (e) NA is not 0, and the composite reports its coverage
# --------------------------------------------------------------------------


def test_all_none_returns_none_with_zero_coverage() -> None:
    res = sentiment_score({})
    assert res["score"] is None and res["coverage"] == 0.0
    assert res["bands"] is None and "floor" in res["withheld"]
    assert res["status"] == "ADVISORY"


def test_a_missing_category_lowers_coverage_by_its_weight() -> None:
    full = sentiment_score(_full_values())
    assert full["score"] is not None
    assert full["coverage"] == pytest.approx(1.0)
    for cat in CATEGORY_ORDER:
        dropped = {
            k: v for k, v in _full_values().items()
            if k not in CATEGORY_COMPONENTS[cat]
        }
        res = sentiment_score(dropped)
        expected = 1.0 - CATEGORY_WEIGHTS[cat] / sum(CATEGORY_WEIGHTS.values())
        assert res["coverage"] == pytest.approx(expected), cat
        assert res["categories"][cat]["score"] is None


def test_a_missing_component_is_none_never_a_neutral_fifty() -> None:
    out = align_components({"weighted_tone": 0.2})
    assert out["weighted_tone"] is not None
    assert out["sma_7d"] is None
    assert set(out.values()) - {out["weighted_tone"]} == {None}
    assert align_components({"weighted_tone": float("nan")})["weighted_tone"] is None


# --------------------------------------------------------------------------
# the attribution recomputes the score; weights are printed
# --------------------------------------------------------------------------


def test_a_reader_recomputing_the_weighted_mean_gets_the_printed_score() -> None:
    res = sentiment_score(_full_values())
    num = den = 0.0
    for cat, entry in res["categories"].items():
        score = entry.get("score")
        if score is None:
            continue
        num += CATEGORY_WEIGHTS[cat] * score
        den += CATEGORY_WEIGHTS[cat]
    assert res["score"] == pytest.approx(num / den, abs=0.005)
    assert res["coverage"] == pytest.approx(den / sum(CATEGORY_WEIGHTS.values()))


def test_a_supplied_weight_vector_is_used_and_printed() -> None:
    w = dict.fromkeys(CATEGORY_ORDER, 1.0)
    w["news_sentiment"] = 4.0
    res = sentiment_score(_full_values(), weights=w)
    num = sum(w[c] * res["categories"][c]["score"] for c in CATEGORY_ORDER)
    assert res["score"] == pytest.approx(num / sum(w.values()), abs=0.005)
    assert res["weights"] == w
    assert "supplied weights" in res["basis"]
    assert "owner weights" in sentiment_score(_full_values())["basis"]


def test_category_weight_share_renormalises() -> None:
    share = category_weight_share()
    assert sum(share.values()) == pytest.approx(1.0)
    assert share["news_sentiment"] == pytest.approx(0.15)


def test_the_owner_category_weights_are_the_published_table() -> None:
    assert sum(CATEGORY_WEIGHTS.values()) == pytest.approx(100.0)
    assert set(CATEGORY_ORDER) == set(CATEGORY_COMPONENTS)
    for cat, names in CATEGORY_COMPONENTS.items():
        assert names, cat


def test_category_score_rejects_an_unknown_category() -> None:
    with pytest.raises(KeyError):
        category_score("nope", {})


def test_a_single_component_category_still_scores() -> None:
    vals = {k: v for k, v in _full_values().items()
            if COMPONENTS[k].category == "short_interest"}
    res = category_score("short_interest", align_components(vals))
    assert res["score"] is not None


def test_every_component_has_a_ramp_and_a_producer() -> None:
    for name, comp in COMPONENTS.items():
        assert name in RAMPS, name
        assert comp.producer, name
        assert comp.direction in ("higher_better", "lower_better")


def test_sentiment_bands_are_not_the_decision_rating_bands() -> None:
    from tradingagents.strategies.decision_guardrail import SCORE_BANDS

    assert tuple(SENTIMENT_BANDS) != tuple(SCORE_BANDS)
    assert not {label for _, label in SENTIMENT_BANDS} & {
        label for _, label in SCORE_BANDS
    }


# --------------------------------------------------------------------------
# the boundaries: no cross-engine number, no sizing path
# --------------------------------------------------------------------------


def _module_references() -> set[str]:
    tree = ast.parse(Path("tradingagents/strategies/sentiment_score.py").read_text(
        encoding="utf-8"
    ))
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            referenced.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            referenced.add(node.module or "")
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
    return referenced


def test_the_sentiment_path_imports_no_news_relevance_function() -> None:
    refs = _module_references()
    assert not any("news_relevance" in r for r in refs), refs


def test_the_module_imports_no_other_score_engine() -> None:
    refs = _module_references()
    for other in ("news_score", "fundamental_score", "technical_score",
                  "event_score", "regime_score", "risk_score"):
        assert not any(other in r for r in refs), (other, refs)


def test_the_module_never_touches_the_sizing_or_gate_path() -> None:
    refs = _module_references()
    for forbidden in ("sizing", "risk.sizing", "risk_multiplier", "knife_guard",
                      "position_size", "decision_guardrail"):
        assert not any(forbidden in r for r in refs), (forbidden, refs)


def test_scale_table_is_symmetric_and_canonical_is_unit() -> None:
    assert CANONICAL_SCALE == (-1.0, 1.0)
    assert SCALE_UNIT == "unit"
    for name, (lo, hi) in SCALE_TABLE.items():
        assert lo < 0.0 < hi, name
        assert math.isclose(lo, -hi, abs_tol=1e-9), name


def test_the_composite_floor_is_below_the_full_category_set() -> None:
    assert len(CATEGORY_ORDER) >= COMPOSITE_MIN_COVERAGE
