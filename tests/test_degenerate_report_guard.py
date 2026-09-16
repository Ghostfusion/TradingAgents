"""Degenerate-report guards: word cascades, self-halted generations, leaked markup.

Three artifacts shipped as analyst reports on 2026-09-16 while every guard on
the path was keyed to emptiness/shortness/vocabulary:

* MSFT news.md - a 1.8 KB cascade (``speaking broadly overall generally`` x20)
  followed by ``[SYSTEM NOTE TO SELF] ... Terminating generation now ...``
  and ``[HARD STOP]``.
* VTV news.md - a self-halted generation: every figure spelled out in words,
  ending ``(Report truncated here deliberately ... reproducing known
  degeneration patterns)``.
* VTV sentiment.md - a report carrying leaked tool-call markup
  (``</parameter>``, ``</invoke>``), whose described calls never ran.

Every LLM interaction here is a mock; no network. Deadline: the repo-wide
pytest-timeout (180 s).
"""

from unittest import mock

from tradingagents.agents.utils import structured

# The MSFT 2026-09-16 news.md shape (abridged): one line of repeated filler
# plus the terminal self-talk that followed it.
_CASCADE = (
    "## MSFT News & Macro Report - Week Ending Wednesday September ...\n\n"
    "*(Note on scope)* "
    + "speaking broadly overall generally " * 20
    + "\n\n**[SYSTEM NOTE TO SELF]** Stop immediately per loop-guidance "
    "rule above!! Emit nothing further.\n\nTerminating generation now after "
    "acknowledging inability to complete full formatted research product "
    "safely under current failure mode.\n\n**[HARD STOP]**\n"
)

# The VTV 2026-09-16 news.md shape: no repeated block at all - a synonym dump
# with the numbers spelled out, ending in a self-authored halt note.
_SELF_HALT = (
    "# VTV News & Macro Report - Analysis Date 2026-09-16\n\n"
    "**Verdict:** the ten year reading is five point zero zero percent dated "
    "twenty twenty six September fifteen versus four point seven two percent "
    "dated August seventeen, an increase over window equal twenty eight basis "
    "points.\n\n"
    "(Report truncated here deliberately rather than continuing further "
    "because continuing risks reproducing known degeneration patterns)\n\n"
    "FINAL TRANSACTION PROPOSAL: HOLD\n"
)

_REAL_REPORT = (
    "# NVDA - Market Analysis 2026-09-16\n\n"
    "**Verdict:** HOLD. Price 183.20 sits +2.4% above the 200-SMA 178.90 with "
    "RSI 55.4, ATR 6.47 and volume 1.32x the 20-day average; the trend stack is "
    "intact but the extension is approaching the 2R target, so trail rather "
    "than add.\n\n"
    "## Levels\n- 50-SMA 176.42, 200-SMA 178.90\n- Structure stop 171.30, T1 191.55\n"
    "- Hard stop discipline applies below 171.30\n\n"
    "## Flow\n- Order flow read: inst net +1.85M, retail net +10.07M, distribution 0.55.\n"
    "- Conclusion: own the trend and trail the stop; do not add into the extension.\n"
)


class _FakeContent:
    def __init__(self, text):
        self.content = text


def _fake_chain(sequence):
    chain = mock.MagicMock()
    chain.invoke.side_effect = [_FakeContent(t) for t in sequence]
    return chain


# --- detectors ---------------------------------------------------------------


def test_cascade_is_detected_and_real_prose_is_not():
    assert structured._looks_like_degenerate_loop(_CASCADE) is True
    assert structured._loop_repeat_run(_CASCADE) >= structured._DEGENERATE_LOOP_MIN_REPS
    # A real report repeats no word block, and trading vocabulary that LOOKS
    # like a halt ("hard stop") is not a generation halt.
    assert structured._looks_like_degenerate_loop(_REAL_REPORT) is False
    assert structured._loop_repeat_run(_REAL_REPORT) <= 2
    assert structured._looks_like_generation_self_halt(_REAL_REPORT) is False


def test_repeated_line_is_detected_as_a_loop():
    """MSFT 2026-09-16 (17:49) sentiment.md repeated one macro line 15x; VTV
    fundamentals.md repeated one line 12x. No word-block cascade - the repeat
    is a whole line."""
    repeated = (
        "# MSFT sentiment\n\n**Macro grounding**\n"
        + "FRED DGS10 leaf latest reading is exactly what matters here.\n\n" * 4
    )
    assert structured._looks_like_generation_self_halt(repeated) is False
    assert structured._looks_like_degenerate_loop(repeated) is True
    assert structured._degenerate_body_kind(repeated) == "loop"

    # A table separator or a short cell repeated is not a loop.
    table = "| Metric | Value |\n|---|---|\n|---|---|\n|---|---|\n|---|---|\n|---|---|\n"
    assert structured._looks_like_degenerate_loop(table) is False
    assert structured._looks_like_degenerate_loop(_REAL_REPORT) is False


def test_self_halt_is_detected_without_any_repetition():
    assert structured._looks_like_generation_self_halt(_SELF_HALT) is True
    # No repeated block: this is the class the cascade detector cannot see.
    assert structured._looks_like_degenerate_loop(_SELF_HALT) is False


def test_kind_classification_covers_every_non_deliverable():
    assert structured._degenerate_body_kind(_CASCADE) == "loop"
    assert structured._degenerate_body_kind(_SELF_HALT) == "self_halt"
    assert structured._degenerate_body_kind(
        "I keep typing the level wrong. Note to self: try again."
    ) == "monologue"
    assert structured._degenerate_body_kind(_REAL_REPORT) is None


# --- analyst chain path (retry_chain_if_stub) --------------------------------


def test_analyst_chain_never_ships_a_cascade():
    """The MSFT news artifact: a non-empty cascade is re-asked on the backup
    chain, and the repaired report is what reaches the report tree."""
    chain = _fake_chain([])
    backup = _fake_chain([_REAL_REPORT])
    out = structured.retry_chain_if_stub(
        chain, ["msg"], _CASCADE, "News Analyst", backup_chain=backup
    )
    assert out == _REAL_REPORT
    chain.invoke.assert_not_called()
    backup.invoke.assert_called_once()


def test_analyst_chain_replaces_a_self_halted_report_with_the_notice():
    chain = _fake_chain([])
    backup = _fake_chain([_SELF_HALT] * structured._MAX_TRUNCATION_RETRIES)
    out = structured.retry_chain_if_stub(
        chain, ["msg"], _SELF_HALT, "News Analyst", backup_chain=backup
    )
    assert out.startswith("**Report unavailable**")
    assert "self-narrated generation failure" in out
    assert "degeneration patterns" not in out


def test_leaked_tool_markup_is_stripped_but_a_markup_only_report_is_not_shipped():
    leaked = _REAL_REPORT + "\n\nrate path tied to DGS10 at ....00%)</parameter>\n</invoke>\n"
    cleaned = structured._sanitize_report_markup(leaked, "Sentiment Analyst")
    assert "</invoke>" not in cleaned and "</parameter>" not in cleaned
    assert "200-SMA 178.90" in cleaned  # the prose survives the strip

    only_markup = "</invoke>\n</parameter>\n"
    chain = _fake_chain([])
    out = structured.retry_chain_if_stub(
        chain, ["msg"], only_markup, "Sentiment Analyst"
    )
    # One shared wording for "the answer WAS the transcript" (the risk loop's
    # own contract), so no caller reads it as prose or as an empty turn.
    assert out == structured.MARKUP_UNAVAILABLE
    assert out.startswith("unavailable")


# --- cap-forced terminal turn (finalize_messages) ----------------------------


def _cap_messages():
    """A pool whose last turn still carries a tool call (the cap trigger)."""
    from langchain_core.messages import AIMessage

    return [
        AIMessage(
            content="",
            tool_calls=[{"name": "get_stock_data", "args": {"symbol": "MSFT"}, "id": "tc-1"}],
        )
    ]


def test_cap_turn_repairs_a_cascade_on_the_backup_chain():
    from langchain_core.messages import AIMessage

    from tradingagents.agents.utils.structured import finalize_messages

    chain = mock.MagicMock()
    chain.invoke.return_value = mock.MagicMock(content=_CASCADE)
    result = AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "tc-1"}])
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content=_REAL_REPORT)

    out = finalize_messages(
        chain, _cap_messages(), result, backup_chain=backup, agent_name="News Analyst"
    )
    assert out.strip() == _REAL_REPORT.strip()
    assert "broadly overall generally" not in out


def test_cap_turn_degrades_to_the_notice_when_every_retry_cascades():
    from langchain_core.messages import AIMessage

    from tradingagents.agents.utils.structured import finalize_messages

    chain = mock.MagicMock()
    chain.invoke.return_value = mock.MagicMock(content=_CASCADE)
    result = AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "tc-1"}])
    backup = mock.MagicMock()
    backup.invoke.return_value = mock.MagicMock(content=_CASCADE)

    out = finalize_messages(
        chain, _cap_messages(), result, backup_chain=backup, agent_name="News Analyst"
    )
    assert out.startswith("**Report unavailable**")
    assert "broadly overall generally" not in out
