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


def test_retry_chain_if_stub_reinvokes_and_returns_report():
    """A status-turn stub must be re-invoked once; the completion becomes the report."""
    chain = _fake_chain([_STATUS_TURN_STUB, _REAL_REPORT])
    out = structured.retry_chain_if_stub(chain, ["msg"], _STATUS_TURN_STUB, "Fundamentals Analyst")
    assert "HOLD" in out
    assert out == _REAL_REPORT
    assert chain.invoke.call_count == 2


def test_retry_chain_if_stub_no_retry_when_complete():
    chain = _fake_chain([])
    out = structured.retry_chain_if_stub(chain, ["msg"], _REAL_REPORT, "Market Analyst")
    assert out == _REAL_REPORT
    chain.invoke.assert_not_called()


def test_retry_chain_if_stub_unavailable_after_exhausted_retries():
    """Still a stub after the retry budget -> explicit unavailable, never an empty report."""
    chain = _fake_chain([_STATUS_TURN_STUB] * (structured._MAX_TRUNCATION_RETRIES + 1))
    out = structured.retry_chain_if_stub(chain, ["msg"], _STATUS_TURN_STUB, "News Analyst")
    assert out.startswith("**Report unavailable**")
    assert "stub" in out.lower()
    assert chain.invoke.call_count == structured._MAX_TRUNCATION_RETRIES


def test_retry_chain_if_stub_handles_chain_failure():
    chain = mock.MagicMock()
    chain.invoke.side_effect = RuntimeError("provider down")
    out = structured.retry_chain_if_stub(chain, ["msg"], _STATUS_TURN_STUB, "Fundamentals Analyst")
    # Still a stub and the retry failed -> explicit unavailable, never raises.
    assert out.startswith("**Report unavailable**")
    assert chain.invoke.call_count == 1
