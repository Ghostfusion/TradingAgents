"""Hermetic tests for the repetition-loop guard in the truncation-retry path.

The max_tokens-padding failure mode (autoregressive attractor loop) emits the
same block repeatedly until the output cap. The guard trims the repeated run
BEFORE the continuation prompt so the loop is never re-fed as context.
"""

from __future__ import annotations

import pytest

from tradingagents.agents.utils.structured import (
    _continuation_prompt,
    _repetition_loop_cut,
    _retry_if_truncated,
)

pytestmark = pytest.mark.timeout(120)

_LOOP_LINE = "The stock remains under pressure from the same macro headwinds."


def _looped_text(reps: int = 4) -> str:
    """A truncated-looking report whose tail is a repeated block."""
    intro = (
        "QCOM closed at 168.74 after a choppy session. Fundamentals remain "
        "mixed and the tape is consolidating near support levels while "
        "institutions distribute into strength."
    )
    return intro + "\n\n" + ("\n".join([_LOOP_LINE] * reps)) + "\n the cut"


class TestRepetitionLoopCut:
    def test_removes_3plus_repeated_block_keeps_prefix(self):
        text = _looped_text(4)
        cut, flag = _repetition_loop_cut(text)
        assert flag is True
        assert _LOOP_LINE not in cut
        assert cut.startswith("QCOM closed at 168.74")
        assert "the cut" not in cut  # everything after the run is dropped too

    def test_two_repeats_untouched(self):
        text = "Intro line.\n\n" + "\n".join([_LOOP_LINE] * 2)
        cut, flag = _repetition_loop_cut(text)
        assert flag is False
        assert cut == text

    def test_normal_report_with_repeated_headers_untouched(self):
        # Legitimate repeated structure (section headers with different bodies)
        # must never be flagged as a loop.
        text = (
            "## Section A\nbody one\n## Section B\nbody two\n"
            "## Section C\nbody three\n## Section D\nbody four"
        )
        cut, flag = _repetition_loop_cut(text)
        assert flag is False
        assert cut == text


class TestRetryIfTruncatedGuard:
    def test_loop_trimmed_before_continuation(self):
        """A looped, truncated response must be trimmed so the continuation
        prompt never contains the repeated block, and the final text is
        loop-free."""
        calls = []

        class _FakeLLM:
            def invoke(self, prompt):
                calls.append(prompt)
                return type("R", (), {"content": " continuation completes the report."})()

        out = _retry_if_truncated(_FakeLLM(), "orig", _looped_text(4))
        assert _LOOP_LINE not in out
        # The continuation prompt (if any) must not re-feed the loop.
        for prompt in calls:
            assert _LOOP_LINE not in prompt
        assert "continuation completes" in out

    def test_continuation_prompt_uses_clean_tail(self):
        tail = _continuation_prompt("clean prefix text that was cut mid")
        assert "cut mid" in tail
        assert _LOOP_LINE not in tail
