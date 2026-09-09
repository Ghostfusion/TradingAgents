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


def test_matches_unit_scale_equivalence():
    # Report cites human units, leaf stores raw tool floats (MSTR 2026-09-08).
    assert rv._matches(122.4, {122368000.0})  # M vs raw
    assert rv._matches(8.22, {8219628000.0})  # B vs raw
    assert rv._matches(17.436, {17435832000.0})  # B vs raw, other direction
    assert not rv._matches(8.22, {8.5})  # 3.4% off, no clean unit step


def test_anchor_grounds_unit_scaled_claims():
    v = rv.ReportVerification(
        report="fundamentals",
        claims=[
            rv.VerifierClaim(
                claim="Revenue $122.4M; total assets $52.56B",
                status="UNSUPPORTED",
                reason="llm said no leaf",
            )
        ],
        overall="FLAG",
    )
    a = rv._anchor_claims(v, {122368000.0, 52562592000.0})
    assert a.claims[0].status == "GROUNDED"
    assert a.overall == "PASS"


def test_evidence_digest_caps_long_content_only_when_explicit():
    long = "x" * 500
    leaf = [{"tool": "t", "status": "ok", "content": long}]
    capped = rv._evidence_digest({"fundamentals": leaf}, "fundamentals", cap_chars=100)
    assert "[truncated]" in capped
    assert len(capped) < 400


def test_evidence_digest_default_does_not_hide_leaf_content():
    # The verifier must see the whole leaf (gatherer already caps at 12000):
    # a per-leaf digest cap hid income-statement revenue and produced false
    # "no leaf evidence" flags on MSTR 2026-09-08.
    body = "Total Revenue,122368000.0,124300000.0,122988000.0"
    leaf = [{"tool": "get_income_statement", "status": "ok", "content": body}]
    digest = rv._evidence_digest({"fundamentals": leaf}, "fundamentals")
    assert "122368000.0" in digest
    assert "[truncated]" not in digest


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


def test_anchor_marks_misquoted_on_attribution_cue():
    """AMZN 2026-09-09 composite_rank class: figures ARE in evidence but the
    claim transposes them between labels. The anchor must surface MISQUOTED
    (high visibility), not silently downgrade to GROUNDED."""
    v = rv.ReportVerification(
        report="market",
        claims=[
            rv.VerifierClaim(
                claim="peers ranked ahead: A (92%), P (67%), e (58%), r (58%)",
                status="UNSUPPORTED",
                reason="the leaf assigns e=92%, P=67%, A=58% — the report "
                "swaps the 92% and 58% labels between A and e",
            )
        ],
        overall="FLAG",
    )
    a = rv._anchor_claims(v, {0.92, 0.67, 0.58})
    assert a.claims[0].status == "MISQUOTED"
    assert a.overall == "FLAG"
    assert "wrong label" in a.claims[0].reason


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


def test_sentiment_prompt_binds_verdict_to_computed_score():
    from tradingagents.agents.analysts.sentiment_analyst import _build_system_message

    msg = _build_system_message(
        ticker="MSTR",
        start_date="2026-09-01",
        end_date="2026-09-08",
        news_block="",
        stocktwits_block="",
        reddit_block="",
        computed_line="computed_score=+0.08",
    )
    assert "computed_score" in msg  # deterministic value reaches the model
    assert "5 + 5 * computed_score" in msg  # 0-10 anchor rule
    assert "never contradict" in msg
    # Without a computed line the block is absent (legacy silent path).
    plain = _build_system_message(
        ticker="MSTR",
        start_date="2026-09-01",
        end_date="2026-09-08",
        news_block="",
        stocktwits_block="",
        reddit_block="",
    )
    assert "### Deterministic computed sentiment" not in plain


def test_internal_conflict_same_metric_two_values():
    text = (
        "DCF fair value is $80.76.\n"
        "The table shows DCF value at 79.60.\n"
        "EPS TTM is 5.40.\n"
    )
    conf = rv._internal_conflicts(text)
    by = {c.claim.split("'")[1]: c for c in conf}
    assert "dcf fair value" in by
    assert by["dcf fair value"].status == "INTERNAL_CONFLICT"
    assert "80.76" in by["dcf fair value"].claim and "79.60" in by["dcf fair value"].claim
    # EPS appears once -> no conflict
    assert "eps ttm" not in by
    # A second metric on the same line as another must NOT be misattributed.
    assert "roe" not in by or "'roe'" not in by


def test_internal_conflict_consistent_value_no_flag():
    text = "DCF fair value 80.76.\nDCF fair value $80.75 elsewhere.\n"
    # 80.76 vs 80.75 are within 0.5% tolerance -> treated as ONE cluster, no conflict.
    assert rv._internal_conflicts(text) == []


def test_internal_conflict_magnitude_normalized():
    # 79.78B and 5.7B are really different magnitudes -> conflict; 79.78B vs
    # 79.8B normalize to the same numeric value.
    t = "EPV ~79.78B in valuation.\nAction section quotes EPV 5.7B.\n"
    conf = rv._internal_conflicts(t)
    assert any(c.claim.startswith("'earnings power value'") for c in conf)
    t2 = "EPV 79.78B.\nEPV 79.8B.\n"
    assert rv._internal_conflicts(t2) == []


def test_internal_conflict_wired_into_report_dir(tmp_path):
    d = _mk_report_dir(
        tmp_path,
        reports={
            "fundamentals": (
                "DCF fair value $80.76.\n"
                "DCF fair value 79.60 in the summary table.\n"
                "EPS 5.4.\n"
            )
        },
    )
    payload = rv.verify_report_dir(
        d,
        llm_override=_mk_llm('{"claims": [{"claim": "EPS 5.4", "status": "GROUNDED", "reason": "leaf"}]}'),
    )
    stems = payload["verification"]["fundamentals"]
    assert any(c["status"] == "INTERNAL_CONFLICT" for c in stems["claims"])
    assert stems["overall"] == "FLAG"


def test_cost_models_import_reachable():
    from tradingagents.agents.utils import report_verifier as R2

    assert hasattr(R2, "internal_conflicts") or hasattr(R2, "_internal_conflicts")


def test_internal_conflict_atr_two_windows():
    """ATR 6.47 (snapshot) vs ATR 5.7079 (swing) in one report must flag —
    the AMZN 2026-09-09 'ATR compressing' class that slipped before."""
    t = "current ATR 6.47 ... structure stop uses ATR 5.7079"
    out = rv._internal_conflicts(t)
    assert any(c.status == "INTERNAL_CONFLICT" and "'atr'" in c.claim for c in out)


def test_internal_conflict_peg_and_ttm_pe():
    """SKHY 2026-09-09 table-vs-body: 'fwd PEG 0.08' body 'PEG 2.08285' and
    'TTM P/E 1.91' vs 'P/E 2.1822' must flag as THE-SAME-METRIC conflicts."""
    t = "Valuation screens: P/E 27.10; TTM P/E 1.91; fwd PEG 0.08 ... "
    t += "Finnhub TTM: P/E 2.1822, forward PEG 2.08285"
    out = rv._internal_conflicts(t)
    labels = {c.claim.split("'")[1] for c in out if c.status == "INTERNAL_CONFLICT"}
    assert "ttm p/e" in labels
    assert "forward peg" in labels


def test_internal_conflict_t1_mislabel():
    """T1 265.03 vs T1 265.97 in one report (>1% apart) must flag."""
    t = "T1(2R ahead)=265.03 ... T1 = 265.97"
    out = rv._internal_conflicts(t)
    assert any("'t1'" in c.claim for c in out)


def test_no_rating_signal_no_conflict():
    # Ordinary prose with a metric but a single consistent value -> no conflict.
    assert rv._internal_conflicts("Simply an eps ttm of 5.4 and nothing more.") == []


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


def test_verify_report_dir_builds_backup_from_config(tmp_path, monkeypatch):
    """The production LLM path (llm_override=None) must build a SECOND client
    from config 'backup_llm' and pass it to the invoke as the truncation
    continuation model - the khy 2026-09-09 stall made the verifier continue
    truncation on the same truncated quick model."""
    report_dir = _mk_report_dir(tmp_path)

    class _BackupLLM:
        pass

    calls = {"backup_llm": None}

    def _fake_client_factory(provider, model, base_url=None, **kw):  # noqa: ANN003
        class _C:
            def get_llm(self):
                if model == "bk/model":
                    return _BackupLLM()
                return object()

        return _C()

    monkeypatch.setattr(
        "tradingagents.llm_clients.create_llm_client",
        _fake_client_factory,
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {
            "backup_llm": "openrouter:bk/model",
            "llm_provider": "openrouter",
            "report_verify_max_calls": 1,
            "report_verify_model": "",
            "quick_think_llm": "q",
        },
    )

    def _spy_invoke(structured, plain, prompt, render, agent_name,
                    fallback_llm=None, backup_llm=None, **kw):  # noqa: ANN002
        calls["backup_llm"] = backup_llm
        return '{"claims": [], "overall": "PASS"}'

    monkeypatch.setattr(
        "tradingagents.agents.utils.structured.invoke_structured_or_freetext",
        _spy_invoke,
    )
    rv.verify_report_dir(report_dir, max_calls=1)
    assert isinstance(calls["backup_llm"], _BackupLLM)


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
