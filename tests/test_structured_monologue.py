"""Drafting-monologue guard: hermetic tests.

Covers the free-text pathology where the model answers with its *private*
drafting monologue instead of the deliverable: it plans the answer, argues with
itself about markdown, re-drafts the same opening and only then writes the
report. Observed live on MU 2026-09-13: the Research Manager's structured call
missed, the free-text fallback returned 5.6 KB of "why does my decimal become
asterisks" self-talk, and the whole monologue landed ahead of the plan in
``2_research/manager.md`` (and in every downstream prompt that reads
``investment_plan``). Every LLM interaction here is a mock; no network.

The detector's thresholds are pinned against a measured corpus: over the 599
markdown files under ``reports/`` on 2026-09-13 the composition vocabulary
matched ONLY that leaked monologue. ``_VERBATIM_SCRATCHPAD`` is an unedited
slice of it.
"""

from unittest import mock

from tradingagents.agents.utils import structured

# Unedited slice of the leaked MU 2026-09-13 monologue (decimals, backticks and
# the model's own typos left exactly as produced).
_VERBATIM_SCRATCHPAD = (
    "**MU — Micron Technology Inc., Technology/Semiconductors, NMS**\n\n"
    "**Rating — Hold**\n\n"
    "| Item | Plan |\n|---|---|\n"
    "| New full-size long at reference **975.***26*? No — wait reference "
    "**975.***26* is invalid formatting |\n"
    "Use correct **975.***26* -> **975.***26* hmm decimal point issue due "
    "markdown bold asterisks causing weirdness Avoid bold around decimals "
    "Use code ticks around all numbers e.g., `975.***26` actually code "
    "preserves asterisks. Why did I type three asterisks Because markdown "
    "bold closing then decimal got eaten Let me slow type backtick nine "
    "seven five period two six backtick.\n"
)

_HEADER = "**MU — Micron Technology Inc., Technology/Semiconductors, NMS**"

# The monologue's own final draft: the real answer, which the salvage keeps.
_DELIVERABLE = (
    f"{_HEADER}\n\n"
    "**Rating — Hold**\n\n"
    "| Factor | Assessment |\n|---|---|\n"
    "| Business outlook | Positive long-term demand from AI servers and HBM |\n"
    "| Near-term setup | Strong expectations are already embedded |\n\n"
    "**Rationale**\n"
    "- Structural demand is attractive through HBM and AI memory content.\n"
    "- The name stays sensitive to pricing, inventory and the memory cycle, so "
    "a Hold balances the secular thesis against cyclicality.\n\n"
    "**Actionable plan**\n"
    "- If already owned: hold; do not materially increase before guidance.\n"
    "- If not owned: starter allocation of 1-2% after a pullback.\n"
)

# A monologue with no final draft: nothing to salvage, so it must be re-asked.
_SCRATCHPAD_NO_DRAFT = (
    "Let me think about how to write this. Hmm, my backtick handling keeps "
    "breaking the decimal, and I keep typing asterisks instead of a period. "
) * 8

_REAL_REPORT = (
    "# NVDA — Fundamental Analysis 2026-09-02\n\n"
    "**Verdict:** HOLD. Revenue $215.94B (+65.5%), net margin 55.6%, ROE 111%\n"
    "but EV/EBIT 595x, DCF fair value $44 vs $183 price (MoS -315%).\n\n"
    "## Valuation\n- FCF yield 1.78% (below the 6% floor)\n"
    "- P/E 45.2, P/B 34.5, EV/EBITDA 452.8\n\n"
) * 3


class _FakeContent:
    def __init__(self, text):
        self.content = text


def _fake_llm(sequence, name="fake/model"):
    llm = mock.MagicMock()
    llm.model_name = name
    llm.invoke.side_effect = [_FakeContent(t) for t in sequence]
    return llm


def _invoke(plain, backup=None):
    return structured.invoke_structured_or_freetext(
        None, plain, "PROMPT+EVIDENCE", str, "Research Manager", backup_llm=backup
    )


# --- detector ---------------------------------------------------------------

def test_detector_flags_the_captured_monologue():
    assert structured._looks_like_drafting_monologue(_VERBATIM_SCRATCHPAD) is True
    assert structured._looks_like_drafting_monologue(
        _VERBATIM_SCRATCHPAD + _DELIVERABLE
    ) is True


def test_detector_flags_self_correction_without_formatting_talk():
    assert structured._looks_like_drafting_monologue(_SCRATCHPAD_NO_DRAFT) is True
    # Two self-correction markers are already decisive: no clean report on disk
    # carries more than one.
    assert structured._looks_like_drafting_monologue(
        "The read stands. No — wait, that stop is wrong. I keep typing the level wrong."
    ) is True


def test_detector_passes_real_reports():
    assert structured._looks_like_drafting_monologue(_REAL_REPORT) is False
    assert structured._looks_like_drafting_monologue(_DELIVERABLE) is False
    # A report may legitimately use first-person planning prose and the word
    # "asterisk" once - neither is decisive on its own.
    prose = (
        "Let's examine the risk. " + _REAL_REPORT + "\nThe asterisk marks a stale\n"
    )
    assert structured._looks_like_drafting_monologue(prose) is False


# --- salvage ----------------------------------------------------------------

def test_salvage_keeps_the_final_draft():
    out = structured._salvage_final_draft(_VERBATIM_SCRATCHPAD + _DELIVERABLE)
    assert out is not None
    assert out.startswith(_HEADER)
    assert "Let me slow type" not in out
    assert out.rstrip().endswith("starter allocation of 1-2% after a pullback.")


def test_salvage_needs_a_repeated_opening_line():
    assert structured._salvage_final_draft(_SCRATCHPAD_NO_DRAFT) is None


def test_salvage_rejects_a_tail_that_is_still_a_monologue():
    tail = _HEADER + "\n\nUse code ticks around all numbers, but my backticks " * 8
    assert structured._salvage_final_draft(_VERBATIM_SCRATCHPAD + tail) is None


# --- decision path (invoke_structured_or_freetext) --------------------------

def test_monologue_is_salvaged_without_an_extra_call():
    plain = _fake_llm([_VERBATIM_SCRATCHPAD + _DELIVERABLE])
    out = _invoke(plain)
    assert out == structured._salvage_final_draft(_VERBATIM_SCRATCHPAD + _DELIVERABLE)
    assert plain.invoke.call_count == 1


def test_monologue_without_a_draft_retries_on_backup():
    plain = _fake_llm([_SCRATCHPAD_NO_DRAFT])
    backup = _fake_llm([_DELIVERABLE], name="backup/luna")
    out = _invoke(plain, backup=backup)
    assert out == _DELIVERABLE
    assert plain.invoke.call_count == 1          # the monologuing model is not re-paid
    assert backup.invoke.call_count == 1


def test_monologue_never_reaches_the_caller():
    plain = _fake_llm([_SCRATCHPAD_NO_DRAFT])
    backup = _fake_llm([_SCRATCHPAD_NO_DRAFT], name="backup/luna")
    out = _invoke(plain, backup=backup)
    assert out.startswith("**Decision**: unavailable")
    assert "backtick" not in out


def test_monologue_retry_that_is_also_a_monologue_keeps_its_draft():
    plain = _fake_llm([_SCRATCHPAD_NO_DRAFT])
    backup = _fake_llm([_VERBATIM_SCRATCHPAD + _DELIVERABLE], name="backup/luna")
    out = _invoke(plain, backup=backup)
    assert out.startswith(_HEADER)
    assert "Let me slow type" not in out


def test_clean_response_is_untouched():
    plain = _fake_llm([_DELIVERABLE])
    backup = _fake_llm([], name="backup/luna")
    out = _invoke(plain, backup=backup)
    assert out == _DELIVERABLE
    assert plain.invoke.call_count == 1
    backup.invoke.assert_not_called()


def test_monologue_is_journaled():
    plain = _fake_llm([_VERBATIM_SCRATCHPAD + _DELIVERABLE])
    with mock.patch(
        "tradingagents.agents.utils.llm_failure_journal.journal_llm_note"
    ) as note:
        _invoke(plain)
    assert note.call_count == 1
    assert note.call_args.kwargs["salvaged"] is True


# --- analyst chain path (retry_chain_if_stub) -------------------------------

def test_chain_path_salvages_the_final_draft():
    chain = _fake_llm([])
    out = structured.retry_chain_if_stub(
        chain, ["msg"], _VERBATIM_SCRATCHPAD + _DELIVERABLE, "News Analyst"
    )
    assert out.startswith(_HEADER)
    assert "Let me slow type" not in out
    chain.invoke.assert_not_called()


def test_chain_path_marks_a_monologue_unavailable_and_retries():
    chain = _fake_llm([])
    backup = _fake_llm([_SCRATCHPAD_NO_DRAFT] * structured._MAX_TRUNCATION_RETRIES,
                       name="backup/luna")
    out = structured.retry_chain_if_stub(
        chain, ["msg"], _SCRATCHPAD_NO_DRAFT, "Fundamentals Analyst",
        backup_chain=backup,
    )
    assert out.startswith("**Report unavailable**")
    assert "returned a drafting monologue (" in out
    assert backup.invoke.call_count == structured._MAX_TRUNCATION_RETRIES
    chain.invoke.assert_not_called()


# --- debate-turn path (retry_llm_if_truncated) ------------------------------

def test_debate_turn_path_salvages_a_monologue():
    llm = _fake_llm([])
    out = structured.retry_llm_if_truncated(
        llm, "PROMPT", _VERBATIM_SCRATCHPAD + _DELIVERABLE,
        agent_name="Bull Researcher",
    )
    assert out.startswith(_HEADER)
    assert "Let me slow type" not in out
    # The salvage is free: the monologue already contained the finished
    # argument, so no model is re-invoked.
    llm.invoke.assert_not_called()


def test_debate_turn_path_retries_on_backup_without_a_draft():
    llm = _fake_llm([_SCRATCHPAD_NO_DRAFT])
    backup = _fake_llm([_DELIVERABLE], name="backup/luna")
    out = structured.retry_llm_if_truncated(
        llm, "PROMPT", _SCRATCHPAD_NO_DRAFT, backup_llm=backup,
        agent_name="Aggressive Analyst",
    )
    assert out == _DELIVERABLE
    assert backup.invoke.call_count == 1
