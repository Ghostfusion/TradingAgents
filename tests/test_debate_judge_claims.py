"""W4 — the debate judge sees per-claim rows, not only per-role counts.

The judge's rubric demands empirical grounding and distrust of unverifiable
numbers, but the prompt carried only ``valid=2 violated=0 …`` per role. It now
renders one row per claim: metric, asserted value, ground-truth key, true
value (from the persisted ground-truth registry - the debate's single
producer) and L1 status.

Hermetic: ``invoke_structured_turn`` is stubbed; no LLM, no network.
"""

from __future__ import annotations

import tradingagents.agents.arbiters.debate_judge as dj_mod


class _Rubric:
    """Minimal stand-in for ``L2JudgeDimensionedRubric``."""

    def __init__(self):
        self.scores = [
            {"dimension": "empirical_grounding", "score": 6},
            {"dimension": "downside_tail_risk_weight", "score": 5},
            {"dimension": "catalyst_clarity", "score": 7},
            {"dimension": "assumption_sensitivity", "score": 6},
        ]
        self.evaluated_agent_alias = None
        self.rationale = "judged"


def _debate_state() -> dict:
    return {
        "round_records": [
            {
                "bull": {
                    "core_thesis": "up",
                    "quantitative_claims": [],
                    "risk_factors": [],
                    "recommended_allocation_pct": 30,
                },
                "bear": {
                    "core_thesis": "down",
                    "quantitative_claims": [],
                    "risk_factors": [],
                    "recommended_allocation_pct": 20,
                },
            }
        ],
        "ground_truth_registry": {"keys": {"pe_ttm": 15.2}},
        "claim_ledger": [
            {
                "role": "bull",
                "round": 1,
                "claim_id": "bull_1_0",
                "kind": "quantitative",
                "value": 18.7,
                "metric_name": "Forward P/E",
                "ground_truth_key": "pe_ttm",
                "source": "analyst_report",
                "status": "unverified",
            },
            {
                "role": "bear",
                "round": 1,
                "claim_id": "bear_1_0",
                "kind": "quantitative",
                "value": 152.65,
                "metric_name": "DCF value",
                "ground_truth_key": "dcf_value",
                "source": "dcf_tool",
                "status": "violated",
            },
        ],
    }


def test_judge_prompt_carries_per_claim_rows(monkeypatch):
    captured: list[str] = []

    def _fake_invoke(structured_llm, plain_llm, prompt, schema, backup_llm=None):
        captured.append(prompt)
        return _Rubric(), None, "structured"

    monkeypatch.setattr(dj_mod, "invoke_structured_turn", _fake_invoke)

    node = dj_mod.create_debate_judge(object(), section="research", cfg={})
    out = node({"debate_state": _debate_state()})

    assert captured, "judge never invoked"
    prompt = captured[0]
    # The specific unverified claim is visible, with its ground truth.
    assert "Forward P/E=18.7" in prompt
    assert "ground_truth_key=pe_ttm" in prompt
    assert "true=15.2" in prompt
    assert "status=unverified" in prompt
    # A claim with no resolvable ground truth renders '-' rather than a number.
    assert "DCF value=152.65" in prompt
    assert "ground_truth_key=dcf_value" in prompt
    assert "true=-" in prompt
    assert "status=violated" in prompt
    # Per-role counts still precede the rows.
    assert "bull: valid=0 violated=0 unverified=1 abstain=0" in prompt
    assert out["debate_state"]["judge_scores"]
