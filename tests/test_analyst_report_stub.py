"""Analyst report-stub guard: hermetic tests.

Covers the analyst-chain pathology where a model answers a tool loop with a
bare *status turn* ("Good progress. Now let me gather the remaining signals
...") instead of the report. No tool_calls remain, so the router treats it as
final and the stub would land verbatim in ``*_report`` (observed: a 217-byte
NVDA fundamentals report 2026-09-02). Every LLM interaction is a mock; no
network. Inherits the pytest-timeout deadline.
"""

from unittest import mock

from tradingagents.agents.utils import structured

# The exact degenerate report captured from the NVDA 2026-09-02 CLI run.
_STATUS_TURN_STUB = (
    "Good progress. Now let me gather the remaining signals — smart money, "
    "institutional holdings, insiders, peers, valuation screens, and value"
    "Now the remaining valuation, ownership, and value-dip screens in parallel."
)

_REAL_REPORT = (
    "# NVDA — Fundamental Analysis 2026-09-02\n\n"
    "**Verdict:** HOLD. Revenue $215.94B (+65.5%), net margin 55.6%, ROE 111%\n"
    "but EV/EBIT 595x, DCF fair value $44 vs $183 price (MoS -315%), insiders\n"
    "net sellers, trap risk HIGH. Own the operating story; do not chase it as\n"
    "a value entry.\n\n"
    "## Valuation\n- FCF yield 1.78% (far below the 6% floor)\n"
    "- P/E 45.2, P/B 34.5, EV/EBITDA 452.8\n"
    "- Value-dip candidate: False (value floor FAIL, technical entry FAIL)\n\n"
    "## Balance sheet\n- D/E 0.06, current ratio 3.91, cash $62.6B\n\n"
) * 3  # comfortably over the stub-length floor, still a real report


class _FakeContent:
    def __init__(self, text):
        self.content = text


def _fake_chain(sequence):
    chain = mock.MagicMock()
    chain.invoke.side_effect = [_FakeContent(t) for t in sequence]
    return chain


def test_looks_report_stub_flags_status_turn():
    assert structured._looks_report_stub(_STATUS_TURN_STUB) is True


def test_looks_report_stub_flags_bare_stub():
    assert structured._looks_report_stub("") is True
    assert structured._looks_report_stub("**Decision**") is True
    assert structured._looks_report_stub("Let me now gather more data.") is True


def test_looks_report_stub_passes_real_report():
    assert structured._looks_report_stub(_REAL_REPORT) is False
    # A long report may legitimately contain progress words; length + substance wins.
    long_with_progress = "We made great progress analyzing this name. " + _REAL_REPORT
    assert structured._looks_report_stub(long_with_progress) is False


# The exact degenerate market report captured from the NTR 2026-09-21 batch run:
# the model answered the tool loop with its one-line verdict and nothing else.
# The engine-score block that follows in the saved file is appended by
# ``report_hygiene.engine_report_section`` AFTER this guard runs, so the guard
# sees 36 chars while the artefact on disk is 1,843 bytes.
_BARE_VERDICT_STUB = "FINAL TRANSACTION PROPOSAL: **HOLD**"


def test_looks_report_stub_flags_a_bare_verdict_line():
    """A one-line verdict is not a report, even though it is not a status turn.

    The guard used to be ``len(t) < 400 and _ANALYST_STATUS_TURN_RE.search(t)``.
    That regex matches progress announcements ("progress", "let me gather ...")
    and a verdict line matches none of them, so the length clause could never
    fire for this shape and NTR 2026-09-21 market.md shipped as exactly this.
    """
    assert structured._looks_report_stub(_BARE_VERDICT_STUB) is True
    # and the retry path must replace it, never ship it as the report
    chain = _fake_chain([])
    out = structured.retry_chain_if_stub(chain, ["msg"], _BARE_VERDICT_STUB, "Market Analyst")
    assert out.startswith("**Report unavailable**")


def test_looks_report_stub_passes_a_report_just_over_the_floor():
    """The floor must not discard a short-but-real report."""
    real = "## Technical Read\n\n" + ("Price is below all three moving averages. " * 12)
    assert len(real) > structured._REPORT_STUB_MIN_CHARS
    assert structured._looks_report_stub(real) is False


def test_retry_chain_if_stub_reinvokes_on_backup_and_returns_report():
    """A status-turn stub must be re-invoked once on the BACKUP chain (the
    original model that produced the stub is never re-paid); the completion
    becomes the report."""
    chain = _fake_chain([])
    backup = _fake_chain([_REAL_REPORT])
    out = structured.retry_chain_if_stub(
        chain, ["msg"], _STATUS_TURN_STUB, "Fundamentals Analyst", backup_chain=backup
    )
    assert "HOLD" in out
    assert out == _REAL_REPORT
    assert backup.invoke.call_count == 1
    # the flaky original chain is never re-invoked
    chain.invoke.assert_not_called()


def test_retry_chain_if_stub_no_retry_when_complete():
    chain = _fake_chain([])
    out = structured.retry_chain_if_stub(chain, ["msg"], _REAL_REPORT, "Market Analyst")
    assert out == _REAL_REPORT
    chain.invoke.assert_not_called()


def test_retry_chain_if_stub_unavailable_after_exhausted_retries():
    """Still a stub after the retry budget -> explicit unavailable, never an empty report."""
    chain = _fake_chain([])
    backup = _fake_chain([_STATUS_TURN_STUB] * structured._MAX_TRUNCATION_RETRIES)
    out = structured.retry_chain_if_stub(
        chain, ["msg"], _STATUS_TURN_STUB, "News Analyst", backup_chain=backup
    )
    assert out.startswith("**Report unavailable**")
    assert "stub" in out.lower()
    assert backup.invoke.call_count == structured._MAX_TRUNCATION_RETRIES


def test_retry_chain_if_stub_no_backup_no_retry_unavailable():
    """Without a configured backup chain a stub is reported unavailable, never
    re-invoking the flaky original (661d879: never re-pay the same model)."""
    chain = _fake_chain([])
    out = structured.retry_chain_if_stub(chain, ["msg"], _STATUS_TURN_STUB, "News Analyst")
    assert out.startswith("**Report unavailable**")
    assert "stub" in out.lower()
    chain.invoke.assert_not_called()


def test_retry_chain_if_stub_handles_chain_failure():
    chain = _fake_chain([])
    backup = mock.MagicMock()
    backup.invoke.side_effect = RuntimeError("provider down")
    out = structured.retry_chain_if_stub(
        chain, ["msg"], _STATUS_TURN_STUB, "Fundamentals Analyst", backup_chain=backup
    )
    # Still a stub and the retry failed -> explicit unavailable, never a raise.
    assert out.startswith("**Report unavailable**")
    assert backup.invoke.call_count == 1
