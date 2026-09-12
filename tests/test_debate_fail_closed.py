"""R1'/R3 fail-closed wiring for the structured debate.

Both flags were decorative before this (2026-09-12, a live NVDA run):
``debate_require_capability_matrix`` printed an "ERROR:" line and the run
continued, and ``debate_baseline_fallback`` existed in the config but was read
by nothing. A flag that cannot stop a run is a gate that cannot fire, so each
one is now asserted here in *both* directions: off/default keeps the
established degradation, on stops the run with a named error.
"""

import pytest

from tradingagents.agents.researchers.structured_debate import (
    DebateBaselineFallbackError,
    create_debate_l1,
)
from tradingagents.agents.schemas import DebaterTurnPayload
from tradingagents.strategies.debate_capability import (
    DebateCapabilityError,
    check_debate_capabilities,
)

pytestmark = pytest.mark.timeout(60)

# A provider the capability matrix has no evidence for: not in the structured
# set, not in the tool-binding set. Only the judge role is assessed here (it is
# the only role with an explicit debate_*_model), and the judge floor requires
# structured output.
_INCAPABLE = {
    "llm_provider": "unknown",
    "quick_think_llm": "m",
    "deep_think_llm": "m",
    "debate_judge_model": "unknown:some-model",
}

_CAPABLE = {
    "llm_provider": "openrouter",
    "quick_think_llm": "m",
    "deep_think_llm": "m",
    "debate_bull_model": "openrouter:deepseek/deepseek-v4.1-flash",
    "debate_bear_model": "openrouter:deepseek/deepseek-v4.1-flash",
    "debate_judge_model": "openrouter:deepseek/deepseek-v4.1-flash",
    "debate_neutral_model": "openrouter:deepseek/deepseek-v4.1-flash",
}


class TestCapabilityMatrixFailsClosed:
    def test_incapable_role_raises_when_required(self):
        cfg = {**_INCAPABLE, "debate_require_capability_matrix": True}
        with pytest.raises(DebateCapabilityError) as exc:
            check_debate_capabilities(cfg)
        assert "judge" in str(exc.value)

    def test_same_config_only_warns_when_not_required(self):
        """The default stays advisory: a warning, never a refusal."""
        cfg = {**_INCAPABLE, "debate_require_capability_matrix": False}
        messages = check_debate_capabilities(cfg)
        assert messages and all(m.startswith("WARNING: ") for m in messages)

    def test_capable_config_is_silent_under_require(self):
        cfg = {**_CAPABLE, "debate_require_capability_matrix": True}
        assert check_debate_capabilities(cfg) == []

    def test_roles_without_an_explicit_model_are_not_assessed(self):
        """Documented coverage limit: a role with no ``debate_*_model`` is
        skipped, so the matrix refuses only on evidence for the explicitly
        routed roles (the tier fallback is outside it)."""
        cfg = {**_INCAPABLE, "debate_require_capability_matrix": True}
        assert check_debate_capabilities(cfg, roles=("bull",)) == []


class TestBaselineFallbackFailsClosed:
    """R1': a debate that cannot be verified either degrades to the baseline
    stances (default) or stops the run - never silently."""

    # round_index is bounded (ge=1, le=5): out of range cannot be sanitized
    # away by the payload's ragged-input validators, so model_validate raises
    # -> the L1 schema-hard-breach path.
    _BAD_TURN = {
        "bull": {
            "round_index": 99,
            "stance": "BULL",
            "core_thesis": "t",
            "recommended_allocation_pct": 10,
        }
    }

    @staticmethod
    def _state(records, **extra):
        return {"debate_state": {"round_records": records, "last_side": "bull", **extra}}

    def test_default_degrades_to_the_baseline(self):
        node = create_debate_l1(lambda s: {"fcf_yield": 7.41}, {})
        ds = node(self._state([self._BAD_TURN]))["debate_state"]
        assert ds["terminated"] is True
        assert ds["reason"] == "schema hard breach; baseline fallback"

    def test_schema_breach_fails_closed_when_the_flag_is_off(self):
        node = create_debate_l1(
            lambda s: {"fcf_yield": 7.41}, {"debate_baseline_fallback": False}
        )
        with pytest.raises(DebateBaselineFallbackError) as exc:
            node(self._state([self._BAD_TURN]))
        assert "schema hard breach" in str(exc.value)

    def test_no_turns_fails_closed_when_the_flag_is_off(self):
        node = create_debate_l1(lambda s: {}, {"debate_baseline_fallback": False})
        with pytest.raises(DebateBaselineFallbackError) as exc:
            node(self._state([]))
        assert "no turns" in str(exc.value)

    def test_l1_hard_breach_fails_closed_when_the_flag_is_off(self):
        """A violated claim with the regen budget spent -> ABORT_TO_BASELINE."""
        payload = DebaterTurnPayload.model_validate(
            {
                "round_index": 1,
                "stance": "BULL",
                "core_thesis": "t",
                "quantitative_claims": [
                    {
                        "metric_name": "fcf",
                        "asserted_value": 99.0,
                        "ground_truth_key": "fcf_yield",
                        "source": "x",
                    }
                ],
                "recommended_allocation_pct": 10,
            }
        )
        cfg = {"debate_baseline_fallback": False, "debate_regen_max": 1}
        node = create_debate_l1(lambda s: {"fcf_yield": 7.41}, cfg)
        state = self._state([{"bull": payload.model_dump()}], regen_count=1)
        with pytest.raises(DebateBaselineFallbackError) as exc:
            node(state)
        assert "L1 hard breach" in str(exc.value)

    def test_risk_section_shares_the_flag(self):
        node = create_debate_l1(
            lambda s: {}, {"debate_baseline_fallback": False}, section="risk"
        )
        with pytest.raises(DebateBaselineFallbackError):
            node({"structured_risk_state": {"round_records": []}})
