"""Decision-surface contract: the action-condition judge can import and render.

Regression guard for P0-3. ``tradingagents/agents/overrides/action_condition_judge.py``
imports ``render_action_condition_verdict`` from ``tradingagents.agents.schemas``,
but an unrelated merge (the structured-debate schema insertion) dropped the
renderer from that module. Importing the judge therefore raised ImportError and
``scripts/action_report.py`` degraded every ``--llm`` call to
"judge unavailable: ...", so the advisory action-condition judge could never run.

The tests below import the exact symbols the report path imports and assert the
renderer reports the verdict and every reason, and never claims a MET/NOT_MET
result for an UNKNOWN condition. No network, no LLM: the end-to-end case uses a
minimal provider stub.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytestmark = pytest.mark.timeout(60)


def _import_surface():
    """Import the symbols the report path uses.

    Imported per-test rather than at module scope so the pre-fix ImportError
    surfaces as a test failure instead of a collection error that hides which
    behaviour regressed.
    """
    from tradingagents.agents.overrides.action_condition_judge import (
        create_action_condition_judge,
    )
    from tradingagents.agents.schemas import (
        ActionConditionVerdict,
        render_action_condition_verdict,
    )

    return create_action_condition_judge, ActionConditionVerdict, render_action_condition_verdict


_REASONS = {
    "MET": [
        "last close 158.10 is above the 150.00 level",
        "RSI 58 sits inside the 40-70 zone",
    ],
    "NOT_MET": ["volume ratio 0.42x is below the 1.30x threshold"],
    "UNKNOWN": [
        "the snapshot carries no input for a regulatory decision",
        "no price anchor is stated for stabilization",
    ],
}


def test_action_condition_judge_module_imports():
    """P0-3: the import ``scripts/action_report.py`` performs must not raise."""
    factory, _, renderer = _import_surface()
    assert callable(factory)
    assert callable(renderer)


@pytest.mark.parametrize("verdict", ["MET", "NOT_MET", "UNKNOWN"])
def test_render_reports_verdict_and_every_reason(verdict):
    _, ActionConditionVerdict, render = _import_surface()
    reasons = _REASONS[verdict]

    out = render(ActionConditionVerdict(verdict=verdict, reasons=reasons))

    assert out
    assert out.splitlines()[0] == f"**Verdict**: {verdict}"
    assert f"**Reasons**: {'; '.join(reasons)}" in out


def test_unknown_verdict_never_claims_met():
    """An UNKNOWN render must not assert the condition was met (never fabricate).

    The token check covers NOT_MET too: it contains MET.
    """
    _, ActionConditionVerdict, render = _import_surface()

    out = render(ActionConditionVerdict(verdict="UNKNOWN", reasons=_REASONS["UNKNOWN"]))

    assert out.splitlines()[0] == "**Verdict**: UNKNOWN"
    assert "MET" not in out


def test_unknown_verdict_without_reasons_invents_nothing():
    """No reasons means no reason line — the renderer never fills in a placeholder."""
    _, ActionConditionVerdict, render = _import_surface()

    out = render(ActionConditionVerdict(verdict="UNKNOWN"))

    assert out == "**Verdict**: UNKNOWN"


class _FakeStructured:
    def __init__(self, result):
        self._result = result

    def invoke(self, prompt):
        return self._result


class _FakeJudgeLLM:
    """Minimal provider stub: structured binding parses, plain invoke is a miss."""

    def __init__(self, result):
        self._result = result

    def with_structured_output(self, schema):
        return _FakeStructured(self._result)

    def invoke(self, prompt):
        return SimpleNamespace(content="")


def test_judge_callable_renders_a_structured_verdict():
    """The judge factory's returned callable runs and renders a real verdict."""
    create_action_condition_judge, ActionConditionVerdict, _ = _import_surface()
    verdict = ActionConditionVerdict(
        verdict="MET",
        reasons=["the 150.00 level is met at 158.10."],
    )

    judge = create_action_condition_judge(_FakeJudgeLLM(verdict))
    out = judge("price above 150.00", "close=158.10, sma50=150.00")

    assert "**Verdict**: MET" in out
    assert "the 150.00 level is met at 158.10." in out
