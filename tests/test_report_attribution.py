"""H9: report influence attribution and the factor novelty screen.

`attribution` is a non-negative least squares projection of a thesis vector onto
the report vectors; `novelty` / `admit_factor` screen a newly proposed factor
against a held-out reference set. Both are descriptive of a completed run - no
look-ahead, no substituted zero for a measurement that cannot be made.
"""

from __future__ import annotations

import numpy as np
import pytest

from tradingagents.strategies.report_attribution import (
    GATE_NAME,
    NOVELTY_MAX_CORR,
    admit_factor,
    attribution,
    embed_reports,
    gate_on,
    novelty,
)

pytestmark = pytest.mark.timeout(120)


def _reference_zoo() -> dict:
    """A held-out reference set Z (the existing zoo), fixed for reproducibility."""
    rng = np.random.default_rng(7)
    n = 60
    return {
        "zoo/mom_12_1": list(rng.normal(size=n)),
        "zoo/value": list(rng.normal(size=n)),
        "zoo/quality": list(rng.normal(size=n)),
    }


# ---------------------------------------------------------------------------
# attribution
# ---------------------------------------------------------------------------


def test_attribution_weights_are_non_negative_and_sum_to_one():
    """A thesis that IS 0.5*market + 0.5*fundamentals must attribute to those two."""
    rng = np.random.default_rng(3)
    n = 40
    reports = {
        "market": list(rng.normal(size=n)),
        "sentiment": list(rng.normal(size=n)),
        "news": list(rng.normal(size=n)),
        "fundamentals": list(rng.normal(size=n)),
    }
    thesis = [0.5 * m + 0.5 * f for m, f in zip(reports["market"], reports["fundamentals"], strict=True)]

    out = attribution(reports, thesis)
    assert out["unavailable"] is None
    weights = out["weights"]
    assert set(weights) == set(reports)
    assert all(w >= 0.0 for w in weights.values())
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["market"] == pytest.approx(0.5, abs=1e-6)
    assert weights["fundamentals"] == pytest.approx(0.5, abs=1e-6)
    assert weights["sentiment"] == pytest.approx(0.0, abs=1e-6)
    assert weights["news"] == pytest.approx(0.0, abs=1e-6)


def test_attribution_reports_its_residual_and_row_count():
    rng = np.random.default_rng(13)
    reports = {"a": list(rng.normal(size=30)), "b": list(rng.normal(size=30))}
    thesis = [x + y for x, y in zip(reports["a"], reports["b"], strict=True)]
    out = attribution(reports, thesis)
    assert out["n_reports"] == 2
    assert out["n_rows"] == 30
    assert out["fit"] == pytest.approx(1.0, abs=1e-6)
    assert out["residual_norm"] == pytest.approx(0.0, abs=1e-6)


def test_attribution_refuses_ragged_input_rather_than_truncating():
    reports = {"a": [1.0, 2.0, 3.0, 4.0], "b": [1.0, 2.0]}  # unequal lengths
    out = attribution(reports, [1.0, 2.0, 3.0, 4.0])
    assert out["weights"] is None
    assert out["unavailable"]


def test_attribution_refuses_an_all_zero_projection():
    """A thesis the reports cannot explain (NNLS weight 0) is not attributed."""
    reports = {"a": [1.0, 1.0, 1.0, 1.0]}
    out = attribution(reports, [-1.0, -1.0, -1.0, -1.0])
    assert out["weights"] is None
    assert "orthogonal" in out["unavailable"]


# ---------------------------------------------------------------------------
# novelty + admission
# ---------------------------------------------------------------------------


def test_relabelled_factor_flagged():
    """A factor that is a relabelling of a zoo member is FLAGGED, not admitted.

    Removing the novelty screen in `admit_factor` (the ``max_abs_corr >=
    novelty_max_corr`` branch) admits this factor as new and fails this test by
    name.
    """
    zoo = _reference_zoo()
    relabelled = [2.0 * x + 5.0 for x in zoo["zoo/mom_12_1"]]  # a rescaling of mom_12_1

    out = admit_factor(
        "new_momentum", relabelled, zoo, productivity=0.7, performance=0.6
    )
    assert out["flagged"] is True
    assert out["admitted"] is False
    assert out["matched"] == "zoo/mom_12_1"
    assert out["max_abs_corr"] == pytest.approx(1.0)
    assert "relabelled" in out["reason"]


def test_novelty_is_the_mean_of_the_max_abs_correlations():
    zoo = _reference_zoo()
    rng = np.random.default_rng(5)
    cand = {
        "relabel": [3.0 * x + 1.0 for x in zoo["zoo/value"]],
        "fresh": list(rng.normal(size=60)),
    }
    out = novelty(cand, zoo)
    assert out["unavailable"] is None
    assert out["n_reference"] == 3
    assert out["per_factor"]["relabel"]["max_abs_corr"] == pytest.approx(1.0)
    assert out["per_factor"]["relabel"]["matched"] == "zoo/value"
    expected = (1.0 + out["per_factor"]["fresh"]["max_abs_corr"]) / 2
    assert out["novelty"] == pytest.approx(expected)


def test_a_novel_factor_with_all_three_reads_is_admitted():
    zoo = _reference_zoo()
    fresh = list(np.random.default_rng(11).normal(size=60))
    out = admit_factor("fresh", fresh, zoo, productivity=0.4, performance=0.3)
    assert out["admitted"] is True
    assert out["flagged"] is False
    assert out["max_abs_corr"] < NOVELTY_MAX_CORR


def test_a_novel_factor_without_productivity_or_performance_is_not_admitted():
    """The three reads are required jointly - novelty alone is not enough."""
    zoo = _reference_zoo()
    fresh = list(np.random.default_rng(11).normal(size=60))
    out = admit_factor("fresh", fresh, zoo, productivity=0.4)  # no performance
    assert out["admitted"] is False
    assert out["flagged"] is False
    assert "performance" in out["reason"]


def test_novelty_refuses_without_a_reference_set():
    out = novelty({"a": [1.0, 2.0, 3.0, 4.0]}, {})
    assert out["novelty"] is None
    assert "reference set" in out["unavailable"]


def test_novelty_refuses_an_unmeasurable_factor():
    """A constant candidate correlates with nothing - refused, never scored 0."""
    zoo = _reference_zoo()
    out = novelty({"flat": [1.0] * 60}, zoo)
    assert out["novelty"] is None
    assert "flat" in out["unavailable"]


# ---------------------------------------------------------------------------
# the embedding stage, the gate, and the card surface
# ---------------------------------------------------------------------------


def test_embed_reports_refuses_without_a_backend():
    out = embed_reports({"market": "text"}, "thesis")
    assert out["reports"] is None
    assert out["thesis"] is None
    assert "no_embedding_backend" in out["unavailable"]


def test_embed_reports_uses_a_supplied_embedder():
    def _embed(text: str) -> list[float]:
        return [float(len(text)), float(len(text) % 3)]

    out = embed_reports({"market": "abcd", "news": "ab"}, "abc", embedder=_embed)
    assert out["unavailable"] is None
    assert out["reports"] == {"market": [4.0, 1.0], "news": [2.0, 2.0]}
    assert out["thesis"] == [3.0, 0.0]


def test_the_gate_ships_off_and_reads_its_env_key(monkeypatch):
    import tradingagents.default_config as dc
    from tradingagents.default_config import _ENV_OVERRIDES

    assert dc.DEFAULT_CONFIG[GATE_NAME] is False
    assert dict(_ENV_OVERRIDES)["TRADINGAGENTS_ENABLE_REPORT_INFLUENCE"] == GATE_NAME
    assert gate_on({}) is False
    assert gate_on({GATE_NAME: True}) is True
    monkeypatch.setenv("TRADINGAGENTS_ENABLE_REPORT_INFLUENCE", "true")
    try:
        out = dc._apply_env_overrides(dict(dc.DEFAULT_CONFIG))
        assert out[GATE_NAME] is True
    finally:
        monkeypatch.delenv("TRADINGAGENTS_ENABLE_REPORT_INFLUENCE", raising=False)


def test_the_card_gains_the_block_only_when_the_gate_is_on():
    """Gate off -> ``None`` (byte-identical card); gate on -> the honest block."""
    from tradingagents.reporting import _run_card_report_influence

    state = {
        "market_report": "m",
        "sentiment_report": "s",
        "news_report": "n",
        "fundamentals_report": "f",
        "final_trade_decision": "thesis",
    }
    assert _run_card_report_influence(state, {}) is None
    block = _run_card_report_influence(state, {GATE_NAME: True})
    assert block is not None
    assert "no_embedding_backend" in block["unavailable"]
