"""Truncation-retry enforcement tests (structured.py).

Covers the retry-on-truncation path: when an LLM response is cut at the
output cap (ends mid-sentence), the helper re-invokes with a continuation
prompt and merges, so the agent's report is never truncated. Hermetic: the
LLM is a MagicMock.
"""

from unittest import mock

import pytest

from tradingagents.agents.utils import structured

pytestmark = pytest.mark.timeout(180)


def _truncated_text() -> str:
    """A long report ending mid-sentence (the max_tokens cut signature)."""
    return "This is a very detailed market analysis with lots of numbers and " * 10 + "the regime is"


def _complete_text() -> str:
    return "This is a complete report with a proper ending sentence."


def test_looks_truncated_flags_mid_sentence():
    assert structured._looks_truncated(_truncated_text()) is True
    assert structured._looks_truncated(_complete_text()) is False
    assert structured._looks_truncated("short") is False  # too short
    assert structured._looks_truncated("**Consensus**: High") is False  # bold label


def test_retry_if_truncated_continues_and_merges():
    """A truncated response is re-invoked with a continuation and merged."""
    llm = mock.MagicMock()
    llm.invoke.return_value = mock.MagicMock(content=" and the trend is clearly down. Done.")
    out = structured._retry_if_truncated(llm, "prompt", _truncated_text())
    assert "the regime is" in out  # original tail preserved
    assert "and the trend is clearly down. Done." in out  # continuation merged
    assert structured._looks_truncated(out) is False  # now complete
    # One continuation call (the merged result is complete -> no second retry).
    assert llm.invoke.call_count == 1


def test_retry_if_truncated_no_retry_when_complete():
    llm = mock.MagicMock()
    out = structured._retry_if_truncated(llm, "prompt", _complete_text())
    assert out == _complete_text()
    llm.invoke.assert_not_called()


def test_retry_if_truncated_gives_up_after_max_retries():
    """If the continuation is ALSO truncated, retry up to the cap then stop."""
    llm = mock.MagicMock()
    llm.invoke.return_value = mock.MagicMock(content="still cut off mid")
    out = structured._retry_if_truncated(llm, "prompt", _truncated_text())
    assert llm.invoke.call_count == structured._MAX_TRUNCATION_RETRIES
    assert "still cut off mid" in out


def test_retry_if_truncated_handles_continuation_failure():
    llm = mock.MagicMock()
    llm.invoke.side_effect = RuntimeError("provider down")
    out = structured._retry_if_truncated(llm, "prompt", _truncated_text())
    assert out == _truncated_text()  # degrades to the original, never raises


def test_retry_chain_if_truncated_appends_human_message():
    """The chain path appends a HumanMessage continuation to the messages."""
    chain = mock.MagicMock()
    chain.invoke.return_value = mock.MagicMock(content=" and the setup is confirmed. End.")
    msgs = [mock.MagicMock()]
    out = structured.retry_chain_if_truncated(chain, msgs, _truncated_text())
    assert "and the setup is confirmed. End." in out
    # The continuation was invoked with the original messages + a HumanMessage.
    args = chain.invoke.call_args[0][0]
    assert len(args) == len(msgs) + 1
    from langchain_core.messages import HumanMessage

    assert isinstance(args[-1], HumanMessage)


def test_invoke_structured_or_freetext_retries_truncated_free_text():
    """The free-text fallback path now enforces completeness via retry."""
    from tradingagents.agents.utils.structured import invoke_structured_or_freetext

    llm = mock.MagicMock()
    llm.invoke.side_effect = [
        mock.MagicMock(content=_truncated_text()),
        mock.MagicMock(content=" and the conclusion is clear. Done."),
    ]
    out = invoke_structured_or_freetext(None, llm, "prompt", lambda r: r, "test")
    assert "and the conclusion is clear. Done." in out
    assert llm.invoke.call_count == 2
