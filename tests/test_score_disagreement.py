"""The quant / LLM risk-disagreement detector (WP-12 `P12-9`).

Acceptance (`docs/scores/ResearchLayerWiring.md` §7, verbatim): *a fixture where
the risk debate reads favourable against `RiskScore` band `unfavourable` produces
the flag; a fixture where they agree produces none.*

What is actually load-bearing, and why each assertion exists:

- **It never changes anything.** §5's weak form exists because the LLM must not
  override the score and the score must not suppress the LLM. The detector returns
  a *flag*; a test asserts it carries no rating, size or score.
- **Both sides are read from what the run already produced** — `RiskScore`'s band
  from the snapshot, the debate's own words from the state. No new producer.
- **Only opposite stances are a contradiction.** A `moderate` on either side is a
  difference of degree, not a contradiction, so it does not fire.
- **An unreadable side produces no flag, with the reason recorded.** A guess would
  be a manufactured disagreement, which is worse than none.

Offline and deterministic: fixtures only.
"""

from __future__ import annotations

from tradingagents.strategies import score_disagreement as sd

#: RiskScore is INVERTED (100 = low risk), so a low score is a bad band.
QUANT_BAD = {"engines": {"risk": {"band": "high risk", "score": 20.0}}}
QUANT_GOOD = {"engines": {"risk": {"band": "low risk", "score": 85.0}}}
QUANT_MID = {"engines": {"risk": {"band": "moderate", "score": 55.0}}}


def _state(risk_text: str) -> dict:
    return {
        "risk_debate_state": {
            "aggressive_history": risk_text,
            "conservative_history": "",
            "neutral_history": "",
            "judge_decision": "**Rating**: Hold\n",
        }
    }


# ---------------------------------------------------------------------------
# the flag
# ---------------------------------------------------------------------------


def test_a_favourable_debate_against_an_unfavourable_band_fires():
    """§5's own example: *"Quant 35, LLM assessment favourable"*."""
    out = sd.risk_disagreement(QUANT_BAD, _state("the risk here is low risk\n"))
    assert out["flag"] is True
    assert out["quant_band"] == "high risk"
    assert out["quant_stance"] == "unfavourable"
    assert out["llm_stance"] == "favourable"
    assert "identify the evidence" in out["reason"]


def test_the_reverse_contradiction_also_fires():
    out = sd.risk_disagreement(QUANT_GOOD, _state("this is a high risk setup\n"))
    assert out["flag"] is True
    assert out["quant_stance"] == "favourable"
    assert out["llm_stance"] == "unfavourable"


def test_agreement_produces_no_flag():
    out = sd.risk_disagreement(QUANT_BAD, _state("severe risk, avoid\n"))
    assert out["flag"] is False
    assert out["reason"] == "both sides read unfavourable"


def test_a_difference_of_degree_is_not_a_contradiction():
    out = sd.risk_disagreement(QUANT_MID, _state("the setup is contained\n"))
    assert out["flag"] is False
    assert "difference of degree" in out["reason"]


def test_an_unreadable_debate_produces_no_flag_and_says_so():
    out = sd.risk_disagreement(QUANT_BAD, _state("the chart looks interesting\n"))
    assert out["flag"] is False
    assert out["llm_stance"] is None
    assert "named no risk band" in out["reason"]


def test_no_quant_band_produces_no_flag_and_says_so():
    out = sd.risk_disagreement({"engines": {"risk": {"band": None}}}, _state("low risk\n"))
    assert out["flag"] is False
    assert "RiskScore produced no band" in out["reason"]


def test_a_tie_between_stances_is_undetermined_not_a_guess():
    out = sd.risk_disagreement(
        QUANT_BAD, _state("low risk in one place, high risk in another\n")
    )
    assert out["flag"] is False
    assert out["llm_stance"] is None


def test_the_detector_changes_nothing_it_reads():
    """§5: it never changes a score, a rating, a size or a gate."""
    snapshot = {
        "engines": {
            "risk": {"band": "high risk", "score": 20.0, "coverage": 0.45},
            "trade": {"score": 67.9},
        },
        "present": ["risk", "trade"],
    }
    before = repr(snapshot)
    out = sd.risk_disagreement(snapshot, _state("low risk\n"))
    assert repr(snapshot) == before
    assert set(out) == {
        "flag",
        "reason",
        "quant_band",
        "quant_stance",
        "llm_stance",
        "llm_bands",
    }
    for forbidden in ("rating", "size", "position_size", "score", "gate"):
        assert forbidden not in out


# ---------------------------------------------------------------------------
# reading the debate's own vocabulary
# ---------------------------------------------------------------------------


def test_the_scan_uses_riskscores_own_band_words():
    assert sd.risk_band_stance("low risk") == "favourable"
    assert sd.risk_band_stance("contained") == "favourable"
    assert sd.risk_band_stance("moderate") == "neutral"
    assert sd.risk_band_stance("elevated") == "neutral"
    assert sd.risk_band_stance("high") == "unfavourable"
    assert sd.risk_band_stance("severe") == "unfavourable"
    assert sd.risk_band_stance(None) is None
    assert sd.risk_band_stance("banana") is None


def test_a_longer_phrase_is_not_double_counted():
    """"high risk" must not also count as "high"."""
    stance, counts = sd.llm_risk_stance("high risk")
    assert counts == {"high risk": 1}
    assert stance == "unfavourable"


def test_the_counts_are_returned_so_the_classification_is_checkable():
    _, counts = sd.llm_risk_stance("low risk twice: low risk, and contained")
    assert counts == {"low risk": 2, "contained": 1}


def test_the_structured_path_is_preferred_when_it_ran():
    state = {
        "structured_risk_state": {"rounds": "the read is low risk\n"},
        "risk_debate_state": {"aggressive_history": "high risk\n"},
    }
    out = sd.risk_disagreement(QUANT_BAD, state)
    assert out["llm_stance"] == "favourable"
    assert out["flag"] is True


# ---------------------------------------------------------------------------
# the two surfaces
# ---------------------------------------------------------------------------


def test_the_card_gains_the_flag_only_when_the_gate_is_on():
    from tradingagents.reporting import _run_card_risk_disagreement

    state = {"quant_scorecard": QUANT_BAD, **_state("low risk\n")}
    assert _run_card_risk_disagreement(state, {}) is None
    block = _run_card_risk_disagreement(state, {"enable_quant_scorecard": True})
    assert block is not None and block["flag"] is True


def test_the_report_gains_a_section_only_when_the_flag_fires(tmp_path):
    from tradingagents.reporting import write_report_tree

    cfg = {"enable_quant_scorecard": True}
    disagreeing = {
        "risk_debate_state": {
            "aggressive_history": "this is low risk\n",
            "conservative_history": "",
            "neutral_history": "",
            "judge_decision": "**Rating**: Hold\n",
        },
        "quant_scorecard": QUANT_BAD,
    }
    path = write_report_tree(disagreeing, "TST", tmp_path / "a", config=cfg)
    report = path.read_text(encoding="utf-8")
    assert "IVb. Quant / LLM risk disagreement" in report
    assert "high risk" in report
    assert "neither side is changed" in report.lower()

    agreeing = {
        **disagreeing,
        "risk_debate_state": {
            **disagreeing["risk_debate_state"],
            "aggressive_history": "high risk\n",
        },
    }
    clean = write_report_tree(agreeing, "TST", tmp_path / "b", config=cfg)
    assert "IVb." not in clean.read_text(encoding="utf-8")


def test_the_report_gains_no_section_when_the_gate_is_off(tmp_path):
    from tradingagents.reporting import write_report_tree

    state = {
        "risk_debate_state": {
            "aggressive_history": "this is low risk\n",
            "conservative_history": "",
            "neutral_history": "",
            "judge_decision": "**Rating**: Hold\n",
        },
        "quant_scorecard": QUANT_BAD,
    }
    path = write_report_tree(state, "TST", tmp_path, config={})
    assert "IVb." not in path.read_text(encoding="utf-8")
