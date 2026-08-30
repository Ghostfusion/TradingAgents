"""Option-A hybrid: independent pre-debate stances (independent_vote.py).

The stance pass samples each decision role's opinion BEFORE any debate
cross-talk, so G3 agreement/consensus (and the PM's dissent flag) is not
contaminated by conformity or adversarial persuasion. These tests pin the
INDEPENDENCE INVARIANT — the stance prompt must never carry debate history or
opponents' responses — plus the deterministic agreement/consensus math and the
graph-node wiring.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tradingagents.agents.schemas import IndependentStance, PortfolioRating, render_stance
from tradingagents.agents.utils.independent_vote import (
    RISK_ROLES,
    build_independent_vote_summary,
    build_stance_prompt,
    create_independent_stance_node,
    independent_agreement,
)
from tradingagents.dataflows.config import set_config


def _base_state() -> dict:
    return {
        "company_of_interest": "NVDA",
        "trade_date": "2026-08-19",
        "instrument_context": "NVDA (NVIDIA Corp, Semiconductors, NASDAQ)",
        "market_report": "close 200.0, RSI 31, %b 0.08",
        "sentiment_report": "neutral",
        "news_report": "earnings beats estimates +12%",
        "fundamentals_report": "ROE 55%, FCF yield 4%",
        "trader_investment_plan": "Buy 3% at 195, stop 188",
        "computed_decision_context": "regime=mean-reversion; value-dip row: pass",
    }


def _stance_llm():
    """Fake LLM returning a structured IndependentStance per role."""
    structured = MagicMock()
    by_role = {
        "aggressive": PortfolioRating.BUY,
        "conservative": PortfolioRating.SELL,
        "neutral": PortfolioRating.HOLD,
        "bull": PortfolioRating.BUY,
        "bear": PortfolioRating.SELL,
    }

    def make_result(prompt):
        # Identify the role from the persona line in the prompt.
        role = "neutral"
        if "Aggressive" in prompt:
            role = "aggressive"
        elif "Conservative" in prompt:
            role = "conservative"
        elif "Bull" in prompt:
            role = "bull"
        elif "Bear" in prompt:
            role = "bear"
        return IndependentStance(
            rating=by_role[role], confidence=0.6, strength=60, reason="test"
        )

    structured.invoke.side_effect = make_result
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


@pytest.mark.unit
@pytest.mark.parametrize("role", RISK_ROLES)
def test_risk_stance_prompt_has_no_debate_crosstalk(role):
    """The independence invariant: no transcript, no opponent responses, no speaker prefixes."""
    text = build_stance_prompt(role, _base_state())
    assert "risk_debate_state" not in text
    assert "investment_debate_state" not in text
    for leaked in ("latest_speaker", "current_conservative_response", "current_neutral_response"):
        assert leaked not in text
    if role == "aggressive":
        assert "Conservative Analyst" not in text
        assert "Neutral Analyst" not in text
    elif role == "conservative":
        assert "Aggressive Analyst" not in text
        assert "Neutral Analyst" not in text
    else:  # neutral
        assert "Aggressive Analyst" not in text
        assert "Conservative Analyst" not in text
    own = {"aggressive": "Aggressive", "conservative": "Conservative", "neutral": "Neutral"}[role]
    assert f"{own} Risk Analyst" in text


@pytest.mark.unit
def test_researcher_stance_prompt_has_no_debate_crosstalk():
    text = build_stance_prompt("bull", _base_state())
    assert "investment_debate_state" not in text
    assert "current_response" not in text
    assert "Bear" not in text  # never references the opponent
    assert "Bull Researcher" in text


@pytest.mark.unit
def test_stance_prompt_grounds_in_computed_context_and_reports():
    text = build_stance_prompt("aggressive", _base_state())
    assert "Market research report" in text
    assert "regime=mean-reversion" in text


@pytest.mark.unit
def test_render_stance_roundtrip():
    s = IndependentStance(
        rating=PortfolioRating.HOLD,
        confidence=0.6,
        strength=55,
        reason="fair value close to market",
    )
    md = render_stance(s)
    assert "**Rating**: Hold" in md
    assert "**Confidence**: 0.60" in md
    assert "**Strength**: 55/100" in md


@pytest.mark.unit
def test_independent_agreement_math():
    # Full agreement -> 1.0
    assert independent_agreement(
        {"aggressive": {"rating": "Buy"}, "conservative": {"rating": "Buy"}, "neutral": {"rating": "Buy"}}
    ) == 1.0
    # Buy vs Sell -> 0.0 (max spread)
    assert (
        independent_agreement(
            {"aggressive": {"rating": "Buy"}, "conservative": {"rating": "Sell"}, "neutral": {"rating": "Sell"}}
        )
        == 0.0
    )
    # Split Buy/Buy/Hold -> range 1.0 -> agreement 0.5 (mid-range)
    s = independent_agreement(
        {"aggressive": {"rating": "Buy"}, "conservative": {"rating": "Buy"}, "neutral": {"rating": "Hold"}}
    )
    assert s is not None and 0.0 < s < 1.0
    # < 2 valid ratings -> None (no fabrication)
    assert independent_agreement({"aggressive": {"rating": "Buy"}}) is None


@pytest.mark.unit
def test_independent_vote_summary_renders_role_lines_and_consensus():
    summary = build_independent_vote_summary(
        {
            "aggressive": {"rating": "Buy", "confidence": 0.8, "strength": 80},
            "conservative": {"rating": "Sell", "confidence": 0.7, "strength": 70},
            "neutral": {"rating": "Hold", "confidence": 0.5, "strength": 50},
        },
        {
            "bull": {"rating": "Buy", "strength": 60, "reason": "moat intact"},
            "bear": {"rating": "Sell"},
        },
    )
    assert "**Independent agreement**" in summary
    assert "agreement=" in summary
    # Disagreement Buy..Sell is NOT 'high'
    assert "label=low" in summary
    assert "- **Aggressive**: Buy" in summary
    assert "Independent researcher reads" in summary


@pytest.mark.unit
def test_independent_vote_summary_unavailable_when_sparse():
    s = build_independent_vote_summary({"aggressive": {"rating": "Buy"}}, {})
    assert "agreement=unavailable" in s


@pytest.mark.unit
def test_node_noops_when_flag_off():
    set_config({"enable_independent_vote": False})
    llm = _stance_llm()
    structured = llm.with_structured_output.return_value
    node = create_independent_stance_node(RISK_ROLES, llm)
    out = node(_base_state())
    assert out == {}
    # Bind happens at graph-build time (harmless); the LLM is never invoked.
    structured.invoke.assert_not_called()


@pytest.mark.unit
def test_risk_node_writes_stances_and_vote_summary():
    set_config({"enable_independent_vote": True})
    llm = _stance_llm()
    node = create_independent_stance_node(RISK_ROLES, llm)
    out = node(_base_state())
    stances = out["risk_independent_stances"]
    assert set(stances) == set(RISK_ROLES)
    for _role, s in stances.items():
        assert s["rating"] in {"Buy", "Overweight", "Hold", "Underweight", "Sell"}
    assert "agreement=" in out["computed_independent_vote"]


@pytest.mark.unit
def test_researcher_node_writes_stances():
    set_config({"enable_independent_vote": True})
    llm = _stance_llm()
    node = create_independent_stance_node(("bull", "bear"), llm)
    out = node(_base_state())
    assert set(out["researcher_independent_stances"]) == {"bull", "bear"}
