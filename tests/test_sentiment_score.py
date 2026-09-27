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


# ---------------------------------------------------------------------------
# The assembler leg this engine declares: mention_heat
# ---------------------------------------------------------------------------


def _points(*pairs):
    return [{"date": d, "score": 0.1, "n": n} for d, n in pairs]


def test_mention_heat_is_assembled_from_the_per_day_count_series(monkeypatch) -> None:
    """`sentiment.mention_volume` takes a per-day mention COUNT history, and
    `daily_sentiment_sma` already carries one (`n`, 0 on a calendar day with no
    articles). The component was declared on every run and assembled on none."""
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.strategies import sentiment as sent

    points = _points(("2026-09-01", 3), ("2026-09-02", 3),
                     ("2026-09-03", 3), ("2026-09-04", 9))
    monkeypatch.setattr(at, "_sentiment_points_with_source",
                        lambda *a, **k: (points, "eodhd"))
    monkeypatch.setattr(at, "_av_news_articles", lambda *a, **k: [])
    monkeypatch.setattr(sent, "compute_social_scores", lambda *a, **k: {})
    # The assembler's other legs are vendor reads; this test is about the
    # attention ratio, and a unit test must not open a chain or an info blob.
    monkeypatch.setattr(at, "_options_chain_rows", lambda *a, **k: (None, "test", {}))
    monkeypatch.setattr(
        "tradingagents.dataflows.yfinance_short_interest.short_interest_fields",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.moomoo.institution_holdings_rows",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.yfinance_sector.fetch_rating_actions",
        lambda *a, **k: None,
    )

    vals, _source = at._sentiment_components("HEAT", "2026-09-04")
    # 9/1..9/3 average 3 mentions/day; the last day is 9 -> ratio 3.0
    assert vals["mention_heat"] == pytest.approx(3.0)


def test_mention_heat_stays_absent_without_a_mention_series(monkeypatch) -> None:
    """NA is not 0: no daily points means no attention ratio."""
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.strategies import sentiment as sent

    monkeypatch.setattr(at, "_sentiment_points_with_source", lambda *a, **k: ([], "unit"))
    monkeypatch.setattr(at, "_av_news_articles", lambda *a, **k: [])
    monkeypatch.setattr(sent, "compute_social_scores", lambda *a, **k: {})
    monkeypatch.setattr(at, "_options_chain_rows", lambda *a, **k: (None, "test", {}))
    monkeypatch.setattr(
        "tradingagents.dataflows.yfinance_short_interest.short_interest_fields",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.moomoo.institution_holdings_rows",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.yfinance_sector.fetch_rating_actions",
        lambda *a, **k: None,
    )

    vals, _source = at._sentiment_components("HEAT", "2026-09-04")
    assert "mention_heat" not in vals


# ---------------------------------------------------------------------------
# SENT-1: the positive share the `bull_share` declaration names
# ---------------------------------------------------------------------------


def _w_art(title, score, ticker="TEST", rel=80.0):
    return {
        "title": title,
        "time_published": "20260916T120000",
        "ticker_sentiment": [
            {"ticker": ticker, "ticker_sentiment_score": score,
             "relevance_score": rel}
        ],
    }


def test_bull_share_is_the_positive_fraction_of_the_days_articles() -> None:
    from tradingagents.strategies.sentiment import aggregate_weighted_sentiment

    pos = aggregate_weighted_sentiment([_w_art(f"P{i}", 0.4) for i in range(3)], "TEST")
    assert pos[-1]["bull_share"] == pytest.approx(1.0)
    neg = aggregate_weighted_sentiment([_w_art(f"N{i}", -0.4) for i in range(3)], "TEST")
    assert neg[-1]["bull_share"] == pytest.approx(0.0)
    # |s| < eps (the row's own 0.05) is neutral, so it is NOT positive
    neutral = aggregate_weighted_sentiment(
        [_w_art("U0", 0.01), _w_art("U1", -0.01), _w_art("U2", 0.0)], "TEST"
    )
    assert neutral[-1]["bull_share"] == pytest.approx(0.0)
    assert neutral[-1]["neutral_share"] == pytest.approx(1.0)


def test_bull_share_uses_the_rows_own_eps_and_denominator() -> None:
    from tradingagents.strategies.sentiment import aggregate_weighted_sentiment

    rows = aggregate_weighted_sentiment(
        [_w_art("M0", 0.4), _w_art("M1", -0.4), _w_art("M2", 0.2)],
        "TEST", neutral_eps=0.10,
    )
    assert rows[-1]["n"] == 3
    # 0.4 and 0.2 clear +0.10; -0.4 does not -> 2 of 3
    assert rows[-1]["bull_share"] == pytest.approx(2 / 3, abs=1e-4)


def test_an_empty_feed_has_no_row_and_no_bull_share() -> None:
    from tradingagents.strategies.sentiment import aggregate_weighted_sentiment

    # a day only exists when an article was accepted, so an empty feed is a
    # refusal (None), never a row with bull_share 0
    assert aggregate_weighted_sentiment([], "TEST") is None


# ---------------------------------------------------------------------------
# SENT-6: crowd bands as a percentile over the name's own history
# ---------------------------------------------------------------------------


def _crowd_history():
    # 25 prior ratios spread 30..54
    return [float(v) for v in range(30, 55)]


def test_crowd_percentile_bands_over_own_history() -> None:
    from tradingagents.strategies.sentiment import crowd_band_percentile

    hist = _crowd_history()
    top = crowd_band_percentile(60.0, hist)
    assert top["method"] == "percentile"
    assert top["percentile"] == pytest.approx(100.0)
    assert top["band"] == "crowded-bullish"
    assert crowd_band_percentile(30.0, hist)["band"] == "crowded-bearish"
    mid = crowd_band_percentile(45.0, hist)
    assert mid["method"] == "percentile"
    assert mid["band"] == "neutral"


def test_crowd_bands_fall_back_to_the_constants_without_history() -> None:
    from tradingagents.strategies.sentiment import crowd_band_percentile

    short = crowd_band_percentile(70.0, [50.0, 51.0])
    assert short["method"] == "constant-fallback"
    assert short["percentile"] is None
    assert short["band"] == "crowded-bullish"
    assert "fell back" in short["basis"]
    assert crowd_band_percentile(30.0, [])["band"] == "crowded-bearish"
    assert crowd_band_percentile(50.0, [])["band"] == "neutral"


def test_crowd_percentile_thresholds_are_configuration() -> None:
    from tradingagents.strategies.sentiment import crowd_band_percentile

    hist = _crowd_history()
    default = crowd_band_percentile(45.0, hist)
    tight = crowd_band_percentile(45.0, hist, low_pct=40.0, high_pct=60.0)
    assert default["percentile"] == pytest.approx(64.0)
    assert default["band"] == "neutral"
    assert tight["band"] == "crowded-bullish"
    assert tight["thresholds"]["high_pct"] == 60.0
    assert default["thresholds"]["high_pct"] == 80.0


def test_crowd_ratio_uses_the_percentile_when_history_is_given() -> None:
    from tradingagents.strategies.sentiment import crowd_ratio

    hist = _crowd_history()
    pct = crowd_ratio(60, 40, history=hist)
    assert pct["band_method"] == "percentile"
    assert pct["band"] == "crowded-bullish"
    assert pct["percentile"] == pytest.approx(100.0)
    const = crowd_ratio(60, 40)
    assert const["band_method"] == "constant-fallback"
    assert const["band"] == "crowded-bullish"  # 60 clears the 60 constant


# ---------------------------------------------------------------------------
# SENT-8: the dynamics beside the canonical slope
# ---------------------------------------------------------------------------


def test_dynamics_second_difference_and_ar1_phi() -> None:
    from tradingagents.strategies.sentiment import sentiment_dynamics

    # geometric decay S_t = 0.5 S_{t-1}: phi 0.5, half-life -ln2/ln0.5 = 1
    geo = [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125]
    out = sentiment_dynamics(geo)
    assert out is not None
    assert out["second_difference"] == pytest.approx(geo[-1] - 2 * geo[-2] + geo[-3])
    assert out["ar1_phi"] == pytest.approx(0.5, abs=1e-6)
    assert out["half_life"] == pytest.approx(1.0, abs=1e-4)
    assert out["persistence"] == pytest.approx(1.0, abs=1e-6)
    assert out["n"] == 6


def test_dynamics_second_difference_matches_the_three_point_formula() -> None:
    from tradingagents.strategies.sentiment import sentiment_dynamics

    out = sentiment_dynamics([0.0, 0.0, 1.0, 3.0, 6.0])
    assert out is not None
    assert out["second_difference"] == pytest.approx(1.0)


def test_dynamics_refuses_below_the_stated_floor() -> None:
    from tradingagents.strategies.sentiment import sentiment_dynamics

    assert sentiment_dynamics([0.1, 0.2, 0.3, 0.4]) is None
    assert sentiment_dynamics([]) is None
    assert sentiment_dynamics([None] * 9) is None


def test_dynamics_half_life_absent_when_phi_has_no_decay() -> None:
    from tradingagents.strategies.sentiment import sentiment_dynamics

    # a perfectly linear rise has phi == 1 (a random walk): no half-life, no
    # mean reversion - the quantities are None, never a fabricated number
    out = sentiment_dynamics([0.1, 0.2, 0.3, 0.4, 0.5])
    assert out is not None
    assert out["ar1_phi"] == pytest.approx(1.0)
    assert out["half_life"] is None
    assert out["mean_reversion_speed"] == pytest.approx(0.0, abs=1e-9)


def test_dynamics_are_additions_not_a_replacement_for_velocity() -> None:
    from tradingagents.strategies.sentiment import (
        sentiment_dynamics,
        sentiment_velocity,
    )

    series = [0.1, 0.2, 0.15, 0.3, 0.25, 0.4]
    assert sentiment_velocity(series) is not None
    assert sentiment_dynamics(series) is not None
