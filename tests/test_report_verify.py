"""Regression tests for the LLM report verifier (tradingagents/agents/utils/report_verifier.py).

Covers the deterministic core (evidence digest, numeric anchoring, verdict
parse) and the degrade contract (provider failure -> UNKNOWN, never raises).
The LLM call itself is mocked; the numeric tolerance is shared with
``repro_check`` so the two gates cannot disagree about "same value".
"""

from __future__ import annotations

import json

from tradingagents.agents.utils import report_verifier as R

rv = R  # module alias (test files reference rv._helper for symmetry)

EVIDENCE_OK = {
    "fundamentals": [
        {
            "tool": "get_analyst_verdict",
            "status": "ok",
            "content": "EY 6.5 EV/EBIT 12.3 ROE 0.18 EPS 2.41",
        },
    ],
    "market": [],
}


def _mk_report_dir(tmp_path, *, evidence=EVIDENCE_OK, reports=None):
    (tmp_path / "1_analysts").mkdir(parents=True)
    if reports is None:
        reports = {
            "fundamentals": "ROE is 0.18 and EPS 2.41.\n",
        }
    for stem, text in reports.items():
        (tmp_path / "1_analysts" / f"{stem}.md").write_text(text, encoding="utf-8")
    (tmp_path / "tool_evidence.json").write_text(
        json.dumps(evidence), encoding="utf-8"
    )
    return tmp_path


def _mk_llm(verdict_json: str):
    """Fake LangChain-ish LLM returning a fixed structured JSON string."""

    class _LLM:
        def invoke(self, prompt):  # noqa: ANN001
            class _R:
                content = verdict_json
            return _R()

    return _LLM()


def _mk_structured(verdict_json: str):
    """Fake with_structured_output wrapper -> returns the parsed verdict."""

    class _LLM:
        def with_structured_output(self, schema, **kw):  # noqa: ANN001
            class _W:
                def __init__(self, llm):  # noqa: ANN001
                    self._llm = llm

                def invoke(self, prompt):  # noqa: ANN001
                    return json.loads(verdict_json)

            return _W(self)

    return _LLM()


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------


def test_float_tokens_distinct():
    assert rv._float_tokens("a 3.14 and 3.14 and 2.5") == {3.14, 2.5}


def test_matches_tolerance():
    assert rv._matches(3.1415, {3.1418})  # 0.01% off -> within 0.5%
    assert not rv._matches(3.14, {3.2})  # 2% off -> outside


def test_evidence_digest_caps_long_content():
    long = "x" * 500
    leaf = [{"tool": "t", "status": "ok", "content": long}]
    digest = rv._evidence_digest({"fundamentals": leaf}, "fundamentals")
    assert "[truncated]" in digest
    assert len(digest) < 400


def test_evidence_digest_empty():
    assert "(no evidence leaves" in rv._evidence_digest({}, "market")


def test_load_report_missing_stem(tmp_path):
    p = _mk_report_dir(tmp_path, reports={})
    assert rv._load_report(p, "missing") is None


# ---------------------------------------------------------------------------
# Numeric anchoring
# ---------------------------------------------------------------------------


def test_anchor_grounds_unsupported_with_matching_figures():
    v = rv.ReportVerification(
        report="fundamentals",
        claims=[
            rv.VerifierClaim(claim="ROE 0.18 and EPS 2.41", status="UNSUPPORTED", reason="llm missed")
        ],
        overall="FLAG",
    )
    a = rv._anchor_claims(v, {0.18, 2.41})
    assert a.claims[0].status == "GROUNDED"
    assert a.overall == "PASS"
    assert "anchored" in a.claims[0].reason


def test_anchor_keeps_unsupported_without_matching_figures():
    v = rv.ReportVerification(
        report="fundamentals",
        claims=[
            rv.VerifierClaim(claim="ROE 0.99", status="UNSUPPORTED", reason="no match")
        ],
        overall="FLAG",
    )
    a = rv._anchor_claims(v, {0.18})
    assert a.claims[0].status == "UNSUPPORTED"
    assert a.overall == "FLAG"


def test_anchor_downgrades_contradicted_with_matching_figures_to_unsupported():
    v = rv.ReportVerification(
        report="fundamentals",
        claims=[
            rv.VerifierClaim(claim="EPS 2.41", status="CONTRADICTED", reason="llm says sign off")
        ],
        overall="FLAG",
    )
    a = rv._anchor_claims(v, {2.41})
    assert a.claims[0].status == "UNSUPPORTED"
    assert a.overall == "FLAG"  # still flagged, but not as numeric contradiction


# ---------------------------------------------------------------------------
# Parse + orchestration (mocked LLM)
# ---------------------------------------------------------------------------


def test_parse_verdict_json():
    v = rv._parse_verdict(
        '{"claims": [{"claim": "x", "status": "UNSUPPORTED", "reason": "no"}]}',
        "fundamentals",
    )
    assert v.overall == "FLAG"
    assert v.claims[0].status == "UNSUPPORTED"


def test_parse_verdict_fence_fallback():
    v = rv._parse_verdict(
        '```json\n{"claims": [{"claim": "y", "status": "GROUNDED", "reason": "ok"}], '
        '"overall": "PASS"}\n```',
        "market",
    )
    assert v.overall == "PASS"
    assert v.claims[0].status == "GROUNDED"


def test_parse_verdict_garbage_is_unknown():
    v = rv._parse_verdict("not json at all", "news")
    assert v.overall == "UNKNOWN"
    assert v.claims == []


def test_verify_evidence_call_structured_path(tmp_path):
    report_dir = _mk_report_dir(tmp_path)
    text = (report_dir / "1_analysts" / "fundamentals.md").read_text()
    llm = _mk_llm('{"claims": [{"claim": "ROE 0.18", "status": "GROUNDED", "reason": "ev"}]}')
    structured = _mk_structured('{"claims": [{"claim": "ROE 0.18", "status": "GROUNDED", "reason": "ev"}]}')
    v = rv.verify_evidence_call(
        llm, structured, "fundamentals", text, EVIDENCE_OK
    )
    assert v.overall == "PASS"
    assert v.claims[0].status == "GROUNDED"


def test_verify_report_dir_llm_override_no_budget_exceeded(tmp_path):
    report_dir = _mk_report_dir(tmp_path)
    payload = rv.verify_report_dir(
        report_dir,
        llm_override=_mk_llm(
            '{"claims": [{"claim": "ROE 0.18", "status": "GROUNDED", "reason": "ev"}]}'
        ),
        max_calls=1,
    )
    assert payload["verification"]["fundamentals"]["overall"] == "PASS"
    # market report absent -> not in output
    assert "market" not in payload["verification"]


def test_verify_report_dir_provider_failure_degrades_unknown(tmp_path, monkeypatch):
    report_dir = _mk_report_dir(tmp_path)

    class _Boom:
        def invoke(self, prompt):  # noqa: ANN001
            raise RuntimeError("provider down")

    # Force the structured path to blow up and the free-text path to blow up
    # too, so invoke_structured_or_freetext degrades.
    monkeypatch.setattr(
        "tradingagents.agents.utils.structured.invoke_structured_or_freetext",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("provider down")),
    )
    payload = rv.verify_report_dir(report_dir, llm_override=_Boom(), max_calls=1)
    assert payload["verification"]["fundamentals"]["overall"] == "UNKNOWN"
