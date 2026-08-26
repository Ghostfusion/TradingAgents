"""Action-Condition Judge: optional LLM verdict for report conditions the
deterministic checker could not fully resolve (design:
``scripts/action_report.py``).

The action report's primary path is deterministic (price levels, SMA /
volume / MACD / RSI refs checked against live OHLCV — never fabricated).
When a condition is UNKNOWN (e.g. "clean PUC decision", "stabilization",
"VDU trigger"), the ``--llm`` flag invokes this judge over the deep LLM with
a pre-built, number-only market snapshot. The judge reasons over the snapshot
only (no external tools) and must say UNKNOWN when the evidence is
insufficient — it is an advisory layer, never a fabrication source.
"""

from __future__ import annotations

from tradingagents.agents.schemas import (
    ActionConditionVerdict,
    render_action_condition_verdict,
)
from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.utils.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)


def create_action_condition_judge(llm):
    """Return a callable judging one condition against a market snapshot.

    ``snapshot`` is a compact text block of measured numbers (price, SMA50 /
    SMA200, volume ratio, RSI, MACD histogram) already computed
    deterministically. The judge must index it, never invent a value.
    """

    structured_llm = bind_structured(llm, ActionConditionVerdict, "Action-Condition Judge")

    def action_condition_judge(condition: str, snapshot: str) -> str:
        """Run one judgment; return the rendered verdict markdown."""
        prompt = f"""As the Action-Condition Judge, decide whether a report's stated condition is met by the current market snapshot.

**Condition from the report (the trigger for the action):**
{condition}

**Measured market snapshot (deterministic):**
{snapshot}

Verdict rules:
- **MET** — the snapshot satisfies the condition (e.g. price at/above the
  stated level, volume ratio above the stated threshold, RSI in the stated
  zone).
- **NOT_MET** — the snapshot contradicts the condition (e.g. price far below
  the stated level, volume thin).
- **UNKNOWN** — the condition references something the snapshot cannot
  measure (a regulatory decision, an earnings print, "stabilization" with no
  price anchor). Say UNKNOWN rather than guessing.

Every reason must cite a number from the snapshot. Never invent a price,
level, or ratio.

{NO_EXTERNAL_TOOLS}{get_language_instruction()}"""

        return invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_action_condition_verdict,
            "Action-Condition Judge",
        )

    return action_condition_judge
