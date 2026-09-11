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
    return (
        "This is a very detailed market analysis with lots of numbers and " * 10 + "the regime is"
    )


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


def test_invoke_structured_or_freetext_retries_truncated_structured_render():
    """A structured-output call that parses but renders mid-sentence must be
    continued via the LLM exactly like the free-text path (regression: the
    structured-success path returned render() without truncation retry, so a
    max_tokens cut passed through to the report marker)."""
    structured_llm = mock.MagicMock()
    structured_llm.invoke.return_value = object()  # parsed schema instance
    plain_llm = mock.MagicMock()
    plain_llm.invoke.side_effect = [
        # 1st plain call: never reached (structured succeeded),
        # 2nd: the truncation continuation.
        mock.MagicMock(content=" and the trend is clearly down. Done."),
    ]
    out = structured.invoke_structured_or_freetext(
        structured_llm,
        plain_llm,
        "prompt",
        render=lambda _: _truncated_text(),
        agent_name="PM",
    )
    assert "the regime is" in out  # original truncated tail preserved
    assert "and the trend is clearly down. Done." in out  # continuation merged
    assert structured._looks_truncated(out) is False
    # Structured success path -> exactly one continuation call, no re-render.
    assert plain_llm.invoke.call_count == 1
    assert structured_llm.invoke.call_count == 1


def test_invoke_structured_or_freetext_no_retry_when_structured_render_complete():
    """A complete structured render must not trigger any plain-LLM call."""
    structured_llm = mock.MagicMock()
    structured_llm.invoke.return_value = object()
    plain_llm = mock.MagicMock()
    out = structured.invoke_structured_or_freetext(
        structured_llm,
        plain_llm,
        "prompt",
        render=lambda _: _complete_text(),
        agent_name="PM",
    )
    assert out == _complete_text()
    plain_llm.invoke.assert_not_called()


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


# --- backup LLM (TRADINGAGENTS_BACKUP_LLM) swap on truncation ---------------


def test_retry_if_truncated_uses_backup_llm():
    """A cut response is continued on the BACKUP model, not the one that cut."""
    llm = mock.MagicMock()
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content=" and the backup finished. Done.")
    out = structured._retry_if_truncated(llm, "prompt", _truncated_text(), backup_llm=backup)
    assert "the regime is" in out  # original tail preserved
    assert "and the backup finished. Done." in out  # backup continuation merged
    assert structured._looks_truncated(out) is False
    backup.invoke.assert_called_once()
    llm.invoke.assert_not_called()  # the truncated model is never re-paid


def test_retry_if_truncated_backup_same_object_no_swap():
    """backup == plain_llm must not double-invoke (identity guard)."""
    llm = mock.MagicMock()
    llm.invoke.return_value = mock.MagicMock(content=" and the trend is clearly down. Done.")
    out = structured._retry_if_truncated(llm, "prompt", _truncated_text(), backup_llm=llm)
    assert "and the trend is clearly down. Done." in out
    assert llm.invoke.call_count == 1


def test_retry_if_truncated_backup_also_truncated_gives_up():
    """Backup continuation ALSO cut -> bounded retries on the backup, then stop."""
    llm = mock.MagicMock()
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content="still cut off mid")
    out = structured._retry_if_truncated(llm, "prompt", _truncated_text(), backup_llm=backup)
    assert backup.invoke.call_count == structured._MAX_TRUNCATION_RETRIES
    assert llm.invoke.call_count == 0
    assert "still cut off mid" in out


def test_retry_if_truncated_backup_failure_degrades():
    """A failing backup degrades to the original text, never raises."""
    llm = mock.MagicMock()
    backup = mock.MagicMock()
    backup.invoke.side_effect = RuntimeError("backup provider down")
    out = structured._retry_if_truncated(llm, "prompt", _truncated_text(), backup_llm=backup)
    assert out == _truncated_text()


def test_retry_if_truncated_backup_unused_when_complete():
    """A complete response never touches the backup (no extra call)."""
    llm = mock.MagicMock()
    backup = mock.MagicMock()
    out = structured._retry_if_truncated(llm, "prompt", _complete_text(), backup_llm=backup)
    assert out == _complete_text()
    backup.invoke.assert_not_called()
    llm.invoke.assert_not_called()


def test_retry_chain_if_truncated_uses_backup_chain():
    """The analyst-chain path runs the continuation on the backup chain."""
    chain = mock.MagicMock()
    backup_chain = mock.MagicMock()
    backup_chain.invoke.return_value = mock.MagicMock(content=" and the backup setup is confirmed. End.")
    msgs = [mock.MagicMock()]
    out = structured.retry_chain_if_truncated(
        chain, msgs, _truncated_text(), backup_chain=backup_chain
    )
    assert "and the backup setup is confirmed. End." in out
    backup_chain.invoke.assert_called_once()
    chain.invoke.assert_not_called()


def test_invoke_structured_or_freetext_uses_backup_on_free_text_cut():
    """The free-text path forwards backup_llm to the truncation retry."""
    llm = mock.MagicMock()
    llm.invoke.side_effect = [mock.MagicMock(content=_truncated_text())]
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content=" and the backup concludes. Done.")
    out = structured.invoke_structured_or_freetext(
        None, llm, "prompt", lambda r: r, "test", backup_llm=backup
    )
    assert "and the backup concludes. Done." in out
    assert llm.invoke.call_count == 1  # only the original cut call
    backup.invoke.assert_called_once()


def test_invoke_structured_or_freetext_uses_backup_on_structured_render_cut():
    """A structured render cut mid-sentence continues on the backup model."""
    structured_llm = mock.MagicMock()
    structured_llm.invoke.return_value = object()
    plain_llm = mock.MagicMock()
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content=" and the backup finishes the render. Done.")
    out = structured.invoke_structured_or_freetext(
        structured_llm,
        plain_llm,
        "prompt",
        render=lambda _: _truncated_text(),
        agent_name="PM",
        backup_llm=backup,
    )
    assert "and the backup finishes the render. Done." in out
    assert plain_llm.invoke.call_count == 0  # never re-paid
    backup.invoke.assert_called_once()


def _fake_llm_client(seen):
    class _FakeClient:
        def __init__(self, *a, **k):
            seen.append(k)

        def get_llm(self):
            return mock.MagicMock()

    return _FakeClient


def test_graph_builds_backup_llm_from_config(monkeypatch):
    """TradingAgentsGraph resolves backup_llm into a backup client and threads
    it into GraphSetup so every node's truncation retry can swap models."""
    seen = []
    monkeypatch.setattr(
        "tradingagents.graph.trading_graph.create_llm_client",
        _fake_llm_client(seen),
    )
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    cfg = dict(DEFAULT_CONFIG)
    cfg["backup_llm"] = "openrouter:deepseek/deepseek-chat"
    ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
    assert ta.backup_thinking_llm is not None
    assert ta.graph_setup.backup_llm is ta.backup_thinking_llm
    # 3 clients: deep + quick + backup; the backup carries the spec model.
    models = [k.get("model", "") for k in seen]
    assert any("deepseek-chat" in str(m) for m in models), f"backup model missing: {models}"


def test_graph_no_backup_when_unset(monkeypatch):
    """No TRADINGAGENTS_BACKUP_LLM -> no backup client, legacy behavior."""
    seen = []
    monkeypatch.setattr(
        "tradingagents.graph.trading_graph.create_llm_client",
        _fake_llm_client(seen),
    )
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    cfg = dict(DEFAULT_CONFIG)
    cfg["backup_llm"] = ""
    ta = TradingAgentsGraph(config=cfg, selected_analysts=("market",))
    assert ta.backup_thinking_llm is None
    assert ta.graph_setup.backup_llm is None
    # No client is ever created for a backup spec (deep/quick + debate roles
    # are all the clients this environment's config produces).
    models = [k.get("model", "") for k in seen]
    assert all("backup" not in str(m) for m in models)


def test_integrity_retry_rebuilds_a_cut_mandatory_field():
    """GOOG 2026-09-11 trader.md: the TraderProposal's `reasoning` was cut
    mid-word ("…is elite — so t") and the rendered-text truncation guard never
    saw it — the render ends with the mandatory FINAL TRANSACTION PROPOSAL banner
    and a single-line field starts with its own "**Reasoning**:" label, both of
    which `_looks_truncated` exempts. Probing the FIELD value detects the cut, so
    the per-field integrity retry must rebuild it."""
    from unittest import mock

    from tradingagents.agents.schemas import TraderAction, TraderProposal, render_trader_proposal
    from tradingagents.agents.utils.structured import (
        _looks_truncated,
        retry_structured_missing_fields,
    )

    cut_text = (
        "The bear won the round on the load-bearing variable - price - and the "
        "composed risk gate is REJECT with a 20.75% portfolio drawdown, so the "
        "balance sheet is genuinely elite (ROE 31.83%) but so"
    )
    complete_text = (
        "The bear won the round on price and the composed risk gate is REJECT; "
        "trim to a residual 1.0% and exit on a daily close below 335.1665."
    )
    cut = TraderProposal(action=TraderAction.SELL, reasoning=cut_text)
    fixed = TraderProposal(action=TraderAction.SELL, reasoning=complete_text)
    rendered = render_trader_proposal(cut)
    # The rendered artifact ends with the banner -> the cut is invisible there.
    assert not _looks_truncated(rendered)

    structured = mock.MagicMock()
    structured.invoke.return_value = fixed
    out = retry_structured_missing_fields(
        structured, "prompt", cut, render_trader_proposal, "Trader",
        ("action", "reasoning"),
    )
    assert structured.invoke.call_count == 1, "a cut mandatory field must trigger the rebuild"
    assert complete_text[:60] in out
    assert "so\n\nFINAL TRANSACTION PROPOSAL" not in out
