"""Regression tests for the LLM report verifier (tradingagents/agents/utils/report_verifier.py).

Covers the deterministic core (evidence digest, numeric anchoring, verdict
parse) and the degrade contract (provider failure -> UNKNOWN, never raises).
The LLM call itself is mocked; the numeric tolerance is shared with
``repro_check`` so the two gates cannot disagree about "same value".
"""

from __future__ import annotations

import json
import re

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


def test_sentiment_prompt_requires_verbatim_counts():
    """The verbatim-counts item governs the three figures the report cannot
    recompute: the message counts, the Reddit engagement totals, and the values
    of the deterministic computed block. Only the score half of that class has a
    deterministic backstop (`_anchor_claims` rescales and checks
    `computed_score`); a rounded or half-read count is undetectable after the
    fact, so the prompt is the whole control. The item is isolated before
    asserting so a neighbouring rule's wording cannot satisfy any of these, and
    located by its lead (not its number) so renumbering the list is free."""
    from tradingagents.agents.analysts.sentiment_analyst import _build_system_message

    msg = _build_system_message(
        ticker="NVDA",
        start_date="2026-09-01",
        end_date="2026-09-08",
        news_block="",
        stocktwits_block="",
        reddit_block="",
        computed_line="computed_score=+0.08",
    )
    m = re.search(
        r"\*\*Copy counts and quotes verbatim\.\*\*(.*?)(?=\n\s*\d+\.\s+\*\*)", msg, re.S
    )
    assert m, "the sentiment prompt dropped the verbatim-counts item"
    item = m.group(1)
    assert re.search(r"message counts", item, re.I)
    assert re.search(r"upvote/comment", item, re.I)
    assert re.search(r"computed block", item, re.I)
    assert re.search(r"never\s+rounded", item)
    # The rule exists to stop numbers drifting: it must state the obligation, not
    # merely name the figures.
    assert re.search(r"quoted exactly as given", item)


def test_sentiment_prompt_pins_macro_to_the_leaf():
    """SKHY 2026-09-14: the sentiment stem stated "US 10-year above 5%" while no
    macro leaf existed anywhere in its evidence (the news stem had one), so the
    verifier flagged the line as UNSUPPORTED. With the gated leaf present the
    prompt carries it and forbids recalled levels; without it the prompt is
    byte-identical to the pre-fix one."""
    from tradingagents.agents.analysts.sentiment_analyst import _build_system_message

    blocks = {
        "ticker": "SKHY",
        "start_date": "2026-09-07",
        "end_date": "2026-09-14",
        "news_block": "",
        "stocktwits_block": "",
        "reddit_block": "",
    }
    with_leaf = _build_system_message(
        **blocks, macro_block="**Latest:** 4.95 (2026-09-10) | Change +0.23"
    )
    assert "MACRO DATA PROVENANCE" in with_leaf
    assert "4.95" in with_leaf
    assert "must be quoted from the macro leaf above" in with_leaf

    without = _build_system_message(**blocks)
    assert "MACRO DATA PROVENANCE" not in without
    assert "Macro rate level" not in without
    assert without == _build_system_message(**blocks, macro_block="")


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


def test_internal_conflict_reads_comma_grouped_figures():
    # "$28,243,000,000" was read as "28" (the digits before the first comma),
    # so the EPS looked like a dual value against the net income.
    t = "| Net Income / Diluted EPS | $28,243,000,000 / $24.67 |\nDiluted EPS 24.67.\n"
    assert rv._internal_conflicts(t) == []


def test_internal_conflict_label_eats_no_leading_digit():
    # "bear 171.38" used to be read as 71.38, making one number look like two
    # conflicting scenarios (MU fundamentals.md 2026-09-14).
    t = (
        "- get_scenario_dcf: bear 171.38 / base 194.96 / bull 227.07\n"
        "| Scenario DCF | bear 171.38 / base 194.96 / bull 227.07 |\n"
    )
    labels = {c.claim.split("'")[1] for c in rv._internal_conflicts(t)}
    assert not {"scenario dcf bear", "scenario dcf base", "scenario dcf bull"} & labels


def test_internal_conflict_stochrsi_is_not_stochk():
    # The label "stoch" also matched "stochrsi", whose 0.0 then read as a
    # conflicting %K (MU market.md 2026-09-14).
    t = "- stochK **12.42** — oversold. `get_mean_reversion_tech`: stochrsi **0.0**\n"
    assert rv._internal_conflicts(t) == []


def test_internal_conflict_skips_thresholds_and_vif_rows():
    # ">= 1.3" is a threshold, and a VIF row reuses the indicator label for a
    # multicollinearity score (MU market.md L7/L83, 2026-09-14).
    t = "- rvol =0.6390 (mean-reversion). | VIF | rsi 5.8 HIGH, mom 5.8 HIGH |\n"
    assert rv._internal_conflicts(t) == []


def test_internal_conflict_level_metric_ignores_growth_percent():
    # "Diluted EPS +1368.5% YoY" is a growth rate, not a second EPS value.
    t = "Diluted EPS +1368.5% YoY.\nDiluted EPS $24.67.\n"
    assert rv._internal_conflicts(t) == []


def test_internal_conflict_twelve_month_window_is_not_twelve_million():
    # "Insider net 12m" is a window label; only a fraction scales in lower case.
    t = "| Insider net 12m | +1,504,467 shares |\nInsider net 1,504,467 shares.\n"
    assert rv._internal_conflicts(t) == []


def test_internal_conflict_scopes_multi_producer_r_targets():
    # Two swing frameworks quote their own T1/T2 by design (get_swing_set off
    # the structure stop, get_tranche_plan off an averaged entry).
    t = (
        "`get_swing_set`: T1(2R) 1042.0785, T2(3R) 1103.1328\n"
        "`get_tranche_plan`: T1 1060.63 / T2 1186.44\n"
    )
    labels = {c.claim.split("'")[1] for c in rv._internal_conflicts(t)}
    assert "t1" not in labels and "t2" not in labels


def test_expected_move_band_is_not_a_conformal_band():
    # get_expected_move's option-implied band has no calibration pairs, so it
    # owes no realized coverage (MU market.md 2026-09-14).
    assert rv._valuation_band_conflict(
        "- Last close 919.38; band [814.32, 1024.45] (±11.4%)\n"
    ) == []


def test_r_multiple_identity_binds_the_lines_own_pair():
    # The structure stop + the report's own spot resolve the swing targets, and
    # the tranche line states its own averaged entry and risk basis.
    text = (
        "price 919.97 ... structure_stop 858.9157 ... "
        "T1(2R) 1042.0785, T2(3R) 1103.1328\n"
        "`get_tranche_plan`: P1 919.97 / P2 876.29 / P3 832.60, stop 767.08, "
        "avg 871.92, risk/share 104.84, T1 1060.63 / T2 1186.44\n"
    )
    assert rv._r_multiple_identity(text) == []


def test_r_multiple_identity_reads_avg_entry_underscore_spelling():
    """get_tranche_plan's stdout spells the entry `avg_entry=` (underscore).

    The space-only reader missed that spelling, fell back to the report-wide
    spot price, and flagged the tool's own correct 1.8R/3.0R targets as two
    INTERNAL_CONFLICTs on a report that quoted it verbatim (AMZN market.md
    2026-09-14: T1 271.97 / T2 288.46 off avg_entry 247.24 with risk/share
    13.74). Both frameworks must stay clean.
    """
    text = (
        "- Verified close 253.54 (FORMING bar)\n"
        "- `get_tranche_plan`: P1=253.54, P2=247.81, P3=242.09, "
        "stop=233.50, avg_entry=247.24, risk/share=13.74, shares=109, "
        "T1=271.97 (1.8R), T2=288.46 (3.0R)\n"
    )
    assert rv._r_multiple_identity(text) == []


def test_internal_conflict_atr_two_windows():
    """ATR 6.47 (snapshot) vs ATR 5.7079 (swing) in one report must flag —
    the AMZN 2026-09-09 'ATR compressing' class that slipped before."""
    t = "current ATR 6.47 ... structure stop uses ATR 5.7079"
    out = rv._internal_conflicts(t)
    assert any(c.status == "INTERNAL_CONFLICT" and "'atr'" in c.claim for c in out)


def test_internal_conflict_peg_and_ttm_pe():
    """SKHY 2026-09-09 table-vs-body: 'fwd PEG 0.08' body 'PEG 2.08285' and
    two TTM P/E figures must flag as THE-SAME-METRIC conflicts. (Bare 'P/E'
    without a TTM qualifier is intentionally NOT merged - forward-vs-TTM P/E
    in one report is normal, not a defect.)"""
    t = "Valuation screens: TTM P/E 1.91; fwd PEG 0.08 ... "
    t += "Finnhub: TTM P/E 2.1822, forward PEG 2.08285"
    out = rv._internal_conflicts(t)
    labels = {c.claim.split("'")[1] for c in out if c.status == "INTERNAL_CONFLICT"}
    assert "ttm p/e" in labels
    assert "forward peg" in labels


def test_internal_conflict_t1_mislabel():
    """T1 265.03 vs T1 265.97 in one report (>1% apart) must flag."""
    t = "T1(2R ahead)=265.03 ... T1 = 265.97"
    out = rv._internal_conflicts(t)
    assert any("'t1'" in c.claim for c in out)


def test_internal_conflict_eps_actual_dual_values():
    # DELL 2026-09-10 news.md: body 'EPS actual 7.04'vs summary
    # 'EPS actual 7.00' (both Finnhub, same quarter) — 0.6% apart must flag.


    t = "EPS actual **7.04** vs estimate **5.012**  ...  EPS actual **7.00** vs est **5.03**"
    out = rv._internal_conflicts(t)
    assert any("'eps actual'" in c.claim for c in out)
    # The ESTIMATE leg is not compared by this pass: an estimate is only
    # comparable within one earnings date (AMZN 2026-09-16 news.md paired
    # 1.83 for the reported 2026-07-30 print with 2.03 for an upcoming one).
    assert not any("'eps estimate'" in c.claim for c in out)


def test_internal_conflict_eps_single_value_clean():
    t = "EPS actual **7.04** vs estimate **5.012** (Finnhub)"
    assert rv._internal_conflicts(t) == []


def test_sma200_values_that_print_identically_are_not_a_conflict():
    """AMZN 2026-09-16 market.md states the 200-SMA distance as +2.44% in one
    line and 2.4% in another - both render "+2.4%", and the claim read
    "+2.4% / +2.4%". One stated distance, not a conflict."""
    t = (
        "price sits **above** the 200-SMA **240.11** (+2.44%)\n"
        "the 200-SMA **240.1117** (2.4% below)"
    )
    assert rv._sma200_pct_identity(t) == []
    # Two genuinely different distances still flag.
    differing = "200-SMA +2.4% ... vs the 200-SMA +15.9% above"
    assert rv._sma200_pct_identity(differing)


def test_digit_masked_numbers_are_reported_and_never_read_as_values():
    """IEI 2026-09-16 market.md masked digits (146 tokens: ``rsi=23._15`` for
    the leaf's 23.15, ``pct_b=_0219``, ``GARCH cond **_._**04%``). The
    extractors read the surviving fragments as second values and produced
    three invented conflicts; the corruption itself is the defect."""
    masked = "dip technical rsi=23._15 pct_b=_0219 stochK=_46 GARCH cond **_._**04%"
    claims = rv._digit_obfuscation(masked)
    assert len(claims) == 1 and claims[0].status == "INTERNAL_CONFLICT"
    assert "digit-masked numbers" in claims[0].claim

    # A masked line yields no value at all - not "23" out of "23._15".
    rsi_re = re.compile(r"\brsi\b", re.I)
    assert rv._extract_metric_values(masked, rsi_re, "rsi") == []
    assert rv._extract_metric_values("dip technical rsi=23.15 pct_b=0.0219", rsi_re, "rsi")

    # A date RANGE is not a masked number (JCI/IEI news stems use "..").
    assert rv._digit_obfuscation("0 messages for 2026-09-07..2026-09-14") == []
    assert rv._digit_obfuscation("close_50_sma 116.30, rsi 23.15") == []

    # The dot/ellipsis placeholder variant (VTV 2026-09-16 sentiment.md).
    vtv = "labels +0..85 on n=30 maps to \u22489..25/10, AUM $16..39T, run on -026-09-15"
    assert rv._digit_obfuscation(vtv)


def test_the_sentiment_rescale_anchor_is_checked_deterministically():
    """The 0-10 headline score is the prompt's own rescale of computed_score
    (5 + 5*score, +/-0.5). The LLM verifier applied that inconsistently on
    2026-09-16 - AMZN's 9.5/10 and IEI's ~0/10 were flagged while MSFT's and
    VTV's were accepted - so the band is anchored in code."""
    def _v(*claims):
        return rv.ReportVerification(
            report="sentiment",
            overall="FLAG",
            claims=[rv.VerifierClaim(claim=c, status="UNSUPPORTED", reason="no leaf") for c in claims],
        )

    amzn = rv._anchor_claims(_v("Overall Sentiment: Bullish (Score: 9.5/10)"), set(), 10.0)
    assert amzn.claims[0].status == "GROUNDED"
    assert "0-10 rescale" in amzn.claims[0].reason

    iei = rv._anchor_claims(_v("overall score \u2248 0 / Bearish"), set(), 0.0)
    assert iei.claims[0].status == "GROUNDED"

    # Outside the band it stays UNSUPPORTED, and with no anchor the rule is off.
    off = rv._anchor_claims(_v("Overall Sentiment (Score: 7.5/10)"), set(), 10.0)
    assert off.claims[0].status == "UNSUPPORTED"
    no_anchor = rv._anchor_claims(_v("Overall Sentiment (Score: 9.5/10)"), set())
    assert no_anchor.claims[0].status == "UNSUPPORTED"


def test_eps_estimates_for_different_dates_are_not_a_conflict():
    """AMZN 2026-09-16 news.md: 1.83 for the already-reported 2026-07-30
    print beside 2.03 (Zacks, upcoming) and 1.95 (calendar, 2026-10-29).
    Three estimates, two dates, each stated with its own period - the
    label-keyed pass paired 1.83 with 2.03 and invented a conflict. Only two
    estimates anchored to the SAME date are one (``_eps_estimate_duals``)."""
    t = (
        "Last reported print 2026-07-30: estimate=1.83, reported=5.75.\n"
        "Zacks cites upcoming earnings of $2.03 per share; get_earnings_calendar "
        "shows the 2026-10-29 estimate=1.95.\n"
        "| Conflicting next-EPS estimate | $2.03 (Zacks) vs 1.95 (calendar) |"
    )
    assert rv._internal_conflicts(t) == []
    # The same date with two values is still a conflict.
    same_date = (
        "2026-10-28 (est EPS 4.72) in the table; forward calendar lists "
        "2026-10-28 est 4.16."
    )
    assert rv._eps_estimate_duals(same_date)


def test_internal_conflict_close_200_sma_dual_values():
    # DELL 2026-09-10 market.md: body 258.98 vs summary 238.98 ona
    # the SAME 'close_200_sma' label must flag (not hidden by the missing
    # '200-day' prose form).
    t = "close_200_sma = 258.98 ... close_200_sma = 238.98"
    out = rv._internal_conflicts(t)
    assert any("'200-day sma'" in c.claim for c in out)


def test_internal_conflict_ema20_trail_dual_values():
    # DELL 2026-09-10 market.md: body 'EMA20 trail 481.74' vs
    # execution 'EMA20 503.74' — a $22 slip that must flag.

    t = "chandelier 475.72, EMA20 trail 481.74 ... EMA20 503.74"
    out = rv._internal_conflicts(t)
    assert any("'ema20'" in c.claim for c in out)


def test_internal_conflict_t1_transcription_slip():
    # DELL 2026-09-10: tranche plan T1=611..85 (evidence); the body's
    # 611.43 is a 0.07% slip — sub-0.1% so it used to pass.the
    # tightened 0.05% bucket now flags it, but genuine integer rounding
    # (611.85 vs  .,612.00) stays clean.

    t = "T1 611.43 ... T1 611.85"
    out = rv._internal_conflicts(t)
    assert any("'t1'" in c.claim for c in out)
    assert rv._internal_conflicts("T1 611.85 ... T1 612.00") == []


def test_internal_conflict_t2_pair_leg_not_2r_price():
    # The "2R/3R targets **A / B**" shape (bold, as the repo's own market.md
    # writes it): the 3R leg is the value AFTER '/', not the first number in the
    # window. Before this, t1 read the "3" of "3R" and t2 read the 2R price
    # (1357.69), so an inconsistent 3R in the summary was never compared
    # (MU 2026-09-09 review loop).
    body = "entry 1027.77, structure stop 862.81, 2R/3R targets **1357.69 / 1521.68**"
    hit = [
        c
        for c in rv._internal_conflicts(
            body + "\nsummary 2R/3R targets **1357.69 / 1541.68**"
        )
        if "'t2'" in c.claim
    ]
    assert hit and hit[0].status == "INTERNAL_CONFLICT"
    assert "1521.68" in hit[0].claim and "1541.68" in hit[0].claim
    # The same pair in body and summary is ONE cluster -> no false positive.
    assert rv._internal_conflicts(
        body + "\nsummary 2R/3R targets **1357.69 / 1521.68**"
    ) == []
    # The "xR" spelling is the same label, and a lone 3xR with its own value is
    # still compared against the pair's 3R leg.
    assert any(
        "'t2'" in c.claim
        for c in rv._internal_conflicts("2xR/3xR targets 120.00 / 130.00\n3xR = 125.00")
    )


def test_internal_conflict_ev_ebit_dual_values():
    # MU 2026-09-10 fundamentals: EV/EBIT quoted 65.2 (analyst verdict) and
    # 66.65 (get_ratios) - two values for one metric in one report.
    t = "EV/EBIT **65.2** (analyst verdict)  ...  EV/EBIT 66.65 (get_ratios)"
    out = rv._internal_conflicts(t)
    assert any("'ev/ebit'" in c.claim for c in out)


def test_internal_conflict_ignores_period_labelled_pairs():
    # AMZN 2026-09-14 fundamentals: diluted EPS 2.78 (2026-03-31, FY2026 Q1) and
    # 5.75 (2026-06-30, FY2026 Q2) are two LABELLED quarters, not one metric at
    # two values - the blanket scan called that pair a conflict.
    t = (
        "Income statement: the latest populated diluted EPS **2.78** for "
        "2026-03-31 (FY2026 Q1)\n"
        "The 2026-06-30 (FY2026 Q2) column reports diluted EPS of **5.75**\n"
    )
    assert not any("'diluted eps'" in c.claim for c in rv._internal_conflicts(t))


def test_internal_conflict_flags_undisclosed_roe_and_ev_ebit():
    # Same AMZN 2026-09-14 report: ROE at 30.56% (feed) / 22.09% (ratios) /
    # 18.89% (verdict) and EV/EBIT at 35.02 (verdict) vs 32.79 (ratios). Only the
    # ratios cluster names a basis, so these are undisclosed differences and
    # must still flag (the period-labelled exemption above must not swallow
    # them).
    text = (
        "Verdict headline: DuPont ROE 22.1% margin-led\n"
        "The deterministic analyst verdict reports EY: 2.86%, EV/EBIT: 35.02, "
        "Altman Z: 5.87, ROE: 18.89%\n"
        "Computed ratios use flows TTM: EV/EBIT 32.79, ROE 22.09%\n"
        "The same feed reports ROE of 30.56%\n"
    )
    claims = [c.claim for c in rv._internal_conflicts(text)]
    assert any("'roe'" in c for c in claims)
    assert any("'ev/ebit'" in c for c in claims)


def test_dividend_yield_sanity_flags_stale_vendor_field():
    # MU 2026-09-10: 'TTM yield 4.91%' vs the same report's $0.15/share and
    # price ~983 -> implied 0.061%; a 4.91% quote is a unit-scaled vendor field.
    t = (
        "dividend per share $0.15 (+30.43% QoQ)\n"
        "latest price $982.95; the market is paying ~5.7x\n"
        "TTM yield 4.91% per get_basic_financials"
    )
    cs = rv._dividend_yield_sanity(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "0.061%" in cs[0].claim


def test_dividend_yield_sanity_clean_when_honest():
    t = "dividend per share $0.50; latest price 100.00 => ttm yield 2.00%"
    assert rv._dividend_yield_sanity(t) == []
    assert rv._dividend_yield_sanity("ttm yield 12.0% but no dividend/share") == []


def test_dividend_yield_sanity_flags_understated_fund_yield():
    # QQQI 2026-09-13: 'Dividend yield: 9.00%' from the vendor field, five lines
    # above the fund's own dated distribution list (5 monthly prints, mean
    # 0.6464/share) which annualizes to 14.22% on the same reference price.
    t = (
        "**Reference price 54.56 is the 2026-09-11 settled close**\n"
        "- Distribution cadence is monthly and consistent: 2026-04-22 $0.6297; "
        "2026-05-20 $0.6589; 2026-06-16 $0.6572; 2026-07-22 $0.6346; "
        "2026-08-19 $0.6518 USD\n"
        "- Dividend yield: 9.00%\n"
    )
    cs = rv._dividend_yield_sanity(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "14.218% implied" in cs[0].claim
    assert "9.00%" in cs[0].claim


def test_dividend_yield_sanity_distribution_cadence_is_inferred():
    # Quarterly prints annualized x4 (0.50 x4 = 2.00) match the quote, while a
    # x12 assumption would have flagged a false conflict; an undated list with
    # no cadence word is not annualized at all.
    quarterly = (
        "price 100.00; dividends 2026-03-31 $0.50; 2026-06-30 $0.50; "
        "2026-09-30 $0.50; ttm yield 2.00%"
    )
    assert rv._dividend_yield_sanity(quarterly) == []
    no_cadence = (
        "price 100.00; distributions $0.50 / $0.52 / $0.49 / $0.51; ttm yield 2.00%"
    )
    assert rv._dividend_yield_sanity(no_cadence) == []


def test_dividend_yield_sanity_flags_undated_monthly_list():
    # Same list with an explicit monthly word: 0.1667 x12 = 2.00 versus a quoted
    # 0.50% is a 4x understatement.
    t = "price 100.00; distributions (monthly) $0.166 / $0.167 / $0.167; ttm yield 0.50%"
    cs = rv._dividend_yield_sanity(t)
    assert len(cs) == 1
    assert "2.000% implied" in cs[0].claim


def test_internal_conflict_pcr_oi_dual_values():
    # MU 2026-09-10 market.md: put/call OI 4.99-equivalent (3.99) in body vs
    # 3.39 in the summary - same metric, dual value.
    t = "put/call OI 3.99 (body) ... | PCR OI | 3.39 (put/call) |"
    out = rv._internal_conflicts(t)
    assert any("'pcr oi'" in c.claim for c in out)


def test_vrp_sign_label_flags_negative_quoted_positive():
    # MU 2026-09-10: body says VRP -5.24pp (IV below realized); summary
    # labels it "VRP positive => vols cheap" - a sign flip.
    t = "VRP \u22125.24pp (IV below realized) ... VRP positive"
    cs = rv._vrp_sign_label(t)
    assert len(cs) == 1
    assert "-5.24pp" in cs[0].claim
    assert cs[0].status == "INTERNAL_CONFLICT"


def test_vrp_sign_label_clean_when_consistent():
    assert rv._vrp_sign_label("VRP -5.24pp (IV below realized)") == []
    assert rv._vrp_sign_label("VRP positive 2.1pp ... IV above realized") == []


def test_double_digit_streak_identity_flags_overcount():
    # MU 2026-09-10 news.md: claimed 'the fifth consecutive double-digit beat'
    # with (Mar-26 +33.21%, Dec-25 +20.58%, Sep-25 +5.94%) + surprise_pct=21.39 -
    # only THREE consecutive >=10% surprises (Sep-25 5.94 breaks).
    text = (
        "Last reported (2026-06-24): estimate 20.69, reported 25.11, "
        "surprise_pct=21.39 - the fifth consecutive double-digit beat "
        "(Mar-26 +33.21%, Dec-25 +20.58%, Sep-25 +5.94%)\n"
    )
    cs = rv._double_digit_streak_identity(text)
    assert len(cs) == 1
    assert "3 consecutive" in cs[0].claim


def test_double_digit_streak_identity_clean_when_accurate():
    text = (
        "estimate 20.69, reported 25.11, surprise_pct=21.39, "
        "then Mar-26 +33.21%, Dec-25 +20.58%, Sep-25 +5.94% - "
        "3 consecutive double-digit beats"
    )
    assert rv._double_digit_streak_identity(text) == []


def test_insider_sold_value_identity_flags_share_mismatch():
    # MU 2026-09-10: summary 'CEO sold 30,000 sh at 959.14-989.59 ($38.8M)'
    # vs the leaf's 40,000 sh / value 38,756,162 - shares don't reconcile.
    text = "CEO sold 30,000 sh at 959.14-989.59 ($38.8M)"
    cs = rv._insider_sold_value_identity(text)
    assert len(cs) == 1
    assert "30,000" in cs[0].claim


def test_insider_sold_value_identity_clean_when_consistent():
    text = "sold 40,000 shares at 959.14-989.59 (value 38,756,162)"
    assert rv._insider_sold_value_identity(text) == []


def test_scenario_dcf_bear_scoped_no_bear_prose_hit():
    # 'Bear-side framing' prose must not trigger the scenario-dcf metric.
    t = "Bear-side framing: 'From $8.7B Profit to $5.8B Loss' ... (10Y 4.8)"
    assert rv._internal_conflicts(t) == []


def test_internal_conflict_beta_dual_values():
    # SNDK 2026-09-10 fundamentals: Finnhub beta 3.868 vs 'beta 1.87' (risk)
    # in the same report - two different betas presented as the beta.
    t = "Finnhub beta is 3.868 - an extremely high-beta tape ... keep position sizing defensive (beta 1.87)"
    out = rv._internal_conflicts(t)
    assert any("'beta'" in c.claim for c in out)


def test_internal_conflict_scenario_dcf_base_dual_values():
    # SNDK 2026-09-10: body scenario base 1,388.45 vs summary base 1,476.2.
    t = "bear 834.55 / base 1,388.45 / bull 4,404.12 ... | scenario bear 834.6/base 1,476.2/bull (band)"
    out = rv._internal_conflicts(t)
    assert any("'scenario dcf base'" in c.claim for c in out)


def test_sma200_identity_flags_direction_flip():
    # SNDK 2026-09-10: '65% below price' while price 1,698.41 / sma 1,026.54
    # => the 200-day is 39.6% below price (65.5% is price ABOVE the sma).
    t = ("200-day (approx 1,026.54 area is 65% below price currently per value-dip tool); "
         "price 1,698.41")
    cs = rv._sma200_identity(t)
    assert len(cs) == 1
    assert "39.6%" in cs[0].claim


def test_sma2000_identity_clean_when_correct():
    t = "price 1,698.41; the value-dip says dist_sma200=65.5% (price above 200-day 1,026.54)"
    assert rv._sma200_identity(t) == []


def test_internal_conflict_current_ratio_dual_values():
    # WDC 2026-09-10 fundamentals: current ratio 10.87 (balance-sheet
    # health) vs vendored 1.329 in one report - an 8x computed-vs-provider
    # conflict that must flag.
    t = ("get_balance_sheet_health pass=True (D/E 0.12<1.0, CR 10.87>1.5); "
         "Current ratio vendor 1.329 vs get_ratios 10.87 - conflict")
    out = rv._internal_conflicts(t)
    assert any("'current ratio'" in c.claim for c in out)


def test_fcf_unit_slip_flags_m_vs_b():
    # WDC 2026-09-10: 'FCF $3.10M TTM' alongside 'FCF $4.1B TTM' - a unit
    # slip (FY26 FCF is 3,511M) that must flag.
    t = "FCF $4.1B TTM ... stated FCF $3.10M TTM"
    cs = rv._fcf_unit_slip(t)
    assert len(cs) == 1
    assert "3.1M" in cs[0].claim


def test_fcf_unit_slip_clean_when_same_scale():
    # Quarterly-vs-annual FCF within one scale must NOT flag (1.28B vs 3.5B).
    t = "quarterly FCF 1,281M ... FY26 FCF $3.51B"
    assert rv._fcf_unit_slip(t) == []


def test_internal_conflict_scenario_dcf_base_dollar_form():
    # WDC 2026-09-10: 'scenario base $93.05' vs the band's base 80.18 - the
    # dollar-prefixed base must be caught by the metric.
    t = "scenario base $93.05 ... bear/base/bull 57.28/80.18/156.55"
    out = rv._internal_conflicts(t)
    assert any("'scenario dcf base'" in c.claim for c in out)


def test_internal_conflict_macd_dual_value():
    # WDC 2026-09-10 market.md: body (verified snapshot) MACD -9.32 / hist
    # +8.37 vs the summary row macd/macdh -0.32/+0.25 - one metric at two
    # values in one report.
    t = ("macd -9.32 (verified) ... histogram +8.37 ... | macd / macdh "
         "| -0.32 / +0.25 (verified) |")
    out = rv._internal_conflicts(t)
    assert any("'macd histogram'" in c.claim for c in out)


def test_internal_conflict_scenario_dcf_bull_dual_values():
    # MSFT 2026-09-10 fundamentals: body bull 231.62 vs summary bull $201 -
    # a 13% contradiction, not rounding.
    t = "Scenario DCF (fcf 66.99B, wacc 10.34%): bear $114.31, base $158.53, bull $231.62 ... | Scenario DCF | bear $114, base $159, bull $201 |"
    out = rv._internal_conflicts(t)
    assert any("'scenario dcf bull'" in c.claim for c in out)


def test_internal_conflict_diluted_eps_dual_values():
    # MSFT 2026-09-10 class: a diluted-eps label quoted at two values in one
    # report (body 4.81 vs a later 4.84 on the same label) must flag.
    t = "Diluted EPS $4.81 (leaf, FY26 Q4); diluted EPS 4.84 in the summary"
    out = rv._internal_conflicts(t)
    assert any("'diluted eps'" in c.claim for c in out)


def test_margin_of_safety_bases_distinct_conventions():
    # MSFT 2026-09-10 review: (FV-P)/FV (-333.7%) vs (FV-P)/P (-76.9%) - the
    # two bases must NOT collapse to the same number (regression: the first
    # impl computed price_basis as -(P/IV - 1), which equals the FV basis).
    from tradingagents.strategies.normalized import margin_of_safety_bases

    b = margin_of_safety_bases(490.50, 113.09)
    assert abs(b["fv_basis"] - (-3.3373)) < 0.01
    assert abs(b["price_basis"] - (-0.7693)) < 0.01
    assert abs(b["price_to_intrinsic"] - 4.337) < 0.02
    assert b["fv_basis"] != b["price_basis"]
    c = margin_of_safety_bases(80.0, 100.0)
    assert abs(c["price_basis"] - 0.25) < 1e-9


def test_expected_band_identity_flags_zero_dollar():
    # MSFT 2026-09-10 market.md: expected move 6.6% rendered as "+-$0.00"
    # instead of the vendor band [458, 523] - a fabrication-class slip.
    t = "expected earnings move 6.6% (\u00b1$0.00 band), 20d realized 21.84%"
    cs = rv._expected_band_identity(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"


def test_eps_estimate_duals_conflict_same_date():
    # MSFT 2026-09-10 news.md: 2026-10-28 cited as est 4.72 in the headline
    # and table but est 4.16 in the forward-calendar line - same print, two
    # estimates; leaf said 4.72.
    t = ("next print 2026-10-28 (est EPS 4.72; last reported 4.74)\n"
         "MSFT earnings 2026-10-28 (est 4.16)")
    cs = rv._eps_estimate_duals(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "2026-10-28" in cs[0].claim and "4.16" in cs[0].claim


def test_bollinger_band_identity_conflicting_sets():
    # TSM 2026-09-10 market.md: body lower=405.14 upper=438.16 (canonical
    # get_bollinger_pct_b) vs summary 'wide 438.59 / low 404.71' - a second
    # band set; %b 0.7394 is only true for the body pair.
    t = ("%b at 73.94% (mid/high zone, lower=405.14 upper=438.16)\n"
         "| Bollinger %b | 0.7394 (mid/high; wide 438.59 / low 404.71) |")
    cs = rv._bollinger_band_identity(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "438.59" in cs[0].claim


def test_bollinger_band_identity_clean_single_set():
    assert rv._bollinger_band_identity("lower=405.14 upper=438.16 mid=421.65 %b=73.94%") == []
    assert rv._bollinger_band_identity("wide 438.59 / low 404.71, %b 0.7394") == []


def test_sector_rank_identity_conflicting_ranks():
    # TSM 2026-09-10 market.md: body XLK rank #4 (both tools) vs table rank5.
    t = "XLK rank #4 (tracking), quadrant Weakening\n| XLK rank5 (Weakening) |"
    cs = rv._sector_rank_identity(t)
    assert len(cs) == 1
    assert "4 / 5" in cs[0].claim
    assert cs[0].status == "INTERNAL_CONFLICT"


def test_self_correction_artifacts_hpe():
    # HPE 2026-09-10 news.md leaked the model's retyping into the artifact:
    # '9.87 ... corrected: 4.8' and '172.346 ... correction - 154.3360'.
    t = ("10Y at 4.78 (2026-08-09, latest print 09-08: 9.87 ... corrected: "
         "latest 4.8); FX USD/JPY 172.346 ... correction: 154.3360")
    cs = rv._self_correction_artifacts(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"


def test_price_target_identity_hpe_triple():
    # HPE 2026-09-10 fundamentals.md: leaf mean 69.38, body 69.38, but the
    # table wrote mean PT 58.38 and mean 58.97 - three distinct means.
    t = ("mean PT $69.38 (high 88, low 54)\n"
         "| Verdict | BUY | mean PT $58.38 |\n"
         "| Analyst target | mean 58.97, high 69.38 |")
    cs = rv._price_target_identity(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "58.38" in cs[0].claim and "58.97" in cs[0].claim


def test_price_target_identity_clean_single():
    assert rv._price_target_identity("mean PT $69.38 (high 88, low 54)") == []
    assert rv._price_target_identity("mean 69.38 from get_analyst_ratings") == []


def test_sma200_pct_identity_hpe():
    # HPE 2026-09-10 market.md: body +64.7% (55.46/33.68-1) vs table +184.7%.
    t = ("price 55.46 vs 200-SMA 33.68 = +64.7%;\n"
         "| price vs 200-SMA +184.7% (verified) |")
    cs = rv._sma200_pct_identity(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "+64.7" in cs[0].claim and "184.7" in cs[0].claim


def test_sma200_mislabel_recompute_msft():
    # MSFT 2026-09-10 decision.md: 'price +8.8% above the 200-SMA 429.51'
    # with the same line's 50-SMA 450.83: at 490.50 the 200-SMA distance is
    # +14.2% and +8.8% is the 50-SMA distance - a mislabeled label.
    t = ("Stay flat on msft at 491.65. ... STRONG_BULL regime (F=0.75), "
         "price +8.8% above the 200-SMA 429.51 and above the rising 50-SMA 450.83")
    cs = rv._sma200_pct_identity(t)
    assert len(cs) == 1
    assert "50-SMA distance" in cs[0].claim
    assert cs[0].status == "INTERNAL_CONFLICT"


def test_sma200_mislabel_clean_when_correct():
    t = "price 490.50 above the 200-SMA 429.51 (+14.2%)"
    assert rv._sma200_pct_identity(t) == []


def test_sma200_pct_identity_clean():
    assert rv._sma200_pct_identity("price vs 200-SMA +64.7%") == []


def test_garch_cond_identity_hpe():
    # HPE 2026-09-10: body 'GARCH long-run 50.71%, conditional 58.90%' vs
    # summary 'GARCH cond 65.90%'.
    t = ("GARCH long-run 50.71%, conditional 58.90%;\n"
         "| GARCH cond 65.90% |")
    cs = rv._garch_cond_identity(t)
    assert len(cs) == 1
    assert "58.90" in cs[0].claim and "65.90" in cs[0].claim


def test_garch_cond_identity_clean():
    t = "GARCH long-run 50.71%, conditional 58.90%"
    assert rv._garch_cond_identity(t) == []


def test_chandelier_identity_hpe():
    # HPE 2026-09-10: body 54.11 (3xATR below 22-bar high) vs table 58.2.
    t = ("chandelier 3xATR below 22-bar high = 54.11 (exit=False)\n"
         "| chandelier 58.2/ema-trail 59.02 for exits |")
    cs = rv._chandelier_identity(t)
    assert len(cs) == 1
    assert "54.11" in cs[0].claim and "58.2" in cs[0].claim


def test_sum_identity_adbe_missum():
    # ADBE 2026-09-10 fundamentals.md: TTM OCF written as
    # 2.165+2.958+3.160+2.198 = $10.62B but the addends sum to 10.481B.
    t = ("TTM OCF = $2.165+2.958+3.160+2.198 = $10.62B; TTM FCF = $10.28B")
    cs = rv._sum_identity(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "10.62" in cs[0].claim and "10.481" in cs[0].claim


def test_sum_identity_clean_when_math_right():
    assert rv._sum_identity("TTM OCF = 2.165+2.958+3.160+2.198 = $10.481B") == []
    assert rv._sum_identity("TTM repurchases 2.111+2.478+2.474+2.057 = $9.12B") == []
    assert rv._sum_identity("TTM OCF = 2.165+2.958+3.160 = $8.283B") == []


def test_ema_identity_hpe_dual():
    # HPE 2026-09-10 market.md: trend section 10-EMA 54.66 vs summary
    # 'retake of the 10-EMA (graph 55.54)'.
    t = ("Above the 10-EMA 54.66 (+1.5%)\n"
         "Watch for retake of the 10-EMA (graph 55.54)")
    cs = rv._ema_identity(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "54.66" in cs[0].claim and "55.54" in cs[0].claim


def test_ema_identity_clean_single_value():
    assert rv._ema_identity("Above the 10-EMA 54.66 (+1.5%)") == []
    assert rv._ema_identity("retake of the 10-EMA (graph 55.54)") == []


def test_ema_identity_equals_form_dual_values():
    # The "10-EMA = NN.NN" form is the common written shape, but the old
    # pattern only bound the space/paren forms, so a report quoting the 10-EMA
    # at two values this way produced no claim at all and the report passed.
    t = "The 10-EMA = 54.66 caps the tape.\nSummary: 10-EMA = 55.54 - retake needed."
    cs = rv._ema_identity(t)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "54.66" in cs[0].claim and "55.54" in cs[0].claim
    # The other separator spellings bind the value too.
    cs3 = rv._ema_identity("10-EMA: 1.11 / the 10-EMA is 2.22 / the 10-EMA at 3.33")
    assert "1.11" in cs3[0].claim and "2.22" in cs3[0].claim and "3.33" in cs3[0].claim
    # One value, however spelled, stays clean.
    assert rv._ema_identity("the 10-EMA is 54.66 all session") == []


def test_ema_conflict_flags_report_dir_overall(tmp_path):
    # The identity check must reach the reported verdict: a market report whose
    # body and summary disagree on the 10-EMA cannot come back PASS.
    d = _mk_report_dir(
        tmp_path,
        reports={
            "market": (
                "Above the 10-EMA = 54.66 (+1.5%).\n"
                "Summary: retake of the 10-EMA = 55.54 first.\n"
            )
        },
    )
    payload = rv.verify_report_dir(
        d,
        stems=("market",),
        llm_override=_mk_llm('{"claims": [], "overall": "PASS"}'),
    )
    market = payload["verification"]["market"]
    assert market["overall"] == "FLAG"
    assert any(c["status"] == "INTERNAL_CONFLICT" for c in market["claims"])


def test_ema_trail_identity_hpe_dual():
    # HPE 2026-09-10: body '20d EMA trail = 53.91' vs table 'ema-trail 59.02'.
    t = ("20d EMA trail = 53.91 (not hit)\n"
         "| chandelier 58.2/ema-trail 59.02 for exits |")
    cs = rv._ema_trail_identity(t)
    assert len(cs) == 1
    assert "53.91" in cs[0].claim and "59.02" in cs[0].claim


def test_ema_trail_identity_clean():
    assert rv._ema_trail_identity("20d EMA trail = 53.91 (not hit)") == []


def test_sum_identity_three_term_wrong():
    cs = rv._sum_identity("TTM OCF = 2.165+2.958+3.160 = $9.1B")
    assert len(cs) == 1
    assert "8.283" in cs[0].claim


def test_chandelier_identity_clean():
    t = "chandelier 3xATR below 22-bar high = 54.11"
    assert rv._chandelier_identity(t) == []


def test_chandelier_identity_ignores_a_neighbouring_metrics_assignment():
    # MSFT 2026-09-16 23:14 market.md: the chandelier is 485.9179 and the
    # "1R=4.3821" printed beside it belongs to the R-multiple read. The loose
    # "=" reader walked past the 22-bar-high parenthetical to that "=" and
    # flagged 4.3821 as a second chandelier stop.
    t = ("- `get_swing_exits`: chandelier 485.9179 (3x ATR below the 22-bar "
         "high), 1R=4.3821, t1=499.0642, t2=503.4463.")
    assert rv._chandelier_values(t) == ["485.9179"]
    assert rv._chandelier_identity(t) == []


def test_chandelier_identity_reads_the_stop_after_the_word_stop():
    # "chandelier stop 486.3121" was invisible to the space reader (it wanted a
    # digit straight after the label) while the "=" reader took the
    # "t1=522.6358" two clauses later as the stop (MSFT 2026-09-15 14:02).
    t = ("- `get_swing_exits`: **chandelier stop 486.3121** (3x ATR below the "
         "22-bar high), ema20 trail 492.9986, **t1=522.6358, t2=534.7438, "
         "1R=12.1079**.")
    assert rv._chandelier_values(t) == ["486.3121"]
    assert rv._chandelier_identity(t) == []


def test_chandelier_identity_ignores_the_atr_multiple_leg():
    # "chandelier 486.7536 (= 3x10.3422 below the 22-bar anchor high 517.78)"
    # read the 3 of the ATR multiple as a second chandelier value (MSFT
    # 2026-09-16 13:04), flagging one stop against itself.
    t = ("Swing exits: chandelier 486.7536 (= 3x10.3422 below the 22-bar anchor "
         "high 517.78), exit=False; EMA20 trail 492.9439.\n"
         "| Stop / targets | structure stop 475.6578; chandelier 486.7536 |")
    assert rv._chandelier_identity(t) == []


def test_money_ellipsis_flagged_as_artifact():
    # HPE 2026-09-10: 'Total debt $8.22B... verbatim $20.24B' leaks a
    # mid-edit dollar value into the final report.
    t = ("Total debt $8.22B... verbatim from get_balance_sheet: Total Debt "
         "$20.24B, Cash $6.22B")
    cs = rv._self_correction_artifacts(t)
    assert len(cs) == 1
    assert "money-ellipsis" in cs[0].claim
    assert rv._self_correction_artifacts("Total debt $20.24B, net debt $14.03B") == []


def test_self_correction_artifacts_clean():
    assert rv._self_correction_artifacts("10Y 4.8 (09-08); USD/JPY 154.33") == []
    assert rv._self_correction_artifacts("correction factor 0.99 applied daily") == []


def test_self_correction_artifacts_detects_degeneration():
    """HPE 2026-09-14 fundamentals.md shipped a report that gave up on itself:
    'Wait correction needed', 'This is degenerating', a repeated line, then a
    'I will restart cleanly' second copy in space-stripped text."""
    t = (
        "Inventory series:** ``635200`. **\n"
        "Inventory series:** ``635200`. **\n"
        "Inventory series:** ``635200`. **\n"
        "Inventory series:** ``635200`. **\n"
        "I am stuck repeating myself due an internal glitch. Please disregard "
        "this draft attempt entirely. I will restart cleanly below.\n"
        + ("DCFFairValue194EV440527404343terminalshare64WACC121beta144" * 8)
    )
    claims = rv._self_correction_artifacts(t)
    texts = " | ".join(c.claim for c in claims)
    assert all(c.status == "INTERNAL_CONFLICT" for c in claims)
    assert "generation-degeneration markers" in texts
    assert "repetition loop" in texts
    assert "degenerate run" in texts


def test_self_correction_artifacts_detects_leaked_tool_markup():
    """wdc 2026-09-14 market_report.md is an unexecuted call transcript."""
    all_markup = (
        "<tool_calls>\n"
        '<invoke name="get_indicators">\n'
        '<parameter name="ticker">WDC</parameter>\n'
        "</invoke>\n"
    )
    claims = rv._self_correction_artifacts(all_markup)
    assert len(claims) == 1
    assert "tool-call markup" in claims[0].claim
    assert "no report text" in claims[0].reason
    # the DSML-wrapped spelling counts too (the wdc run wrote exactly this)
    dsml = "</\uff5cDSML\uff5c invoke>"
    assert any(
        "tool-call markup" in c.claim
        for c in rv._self_correction_artifacts(dsml)
    )
    # ...including the spelling whose block word lost its "tool_" prefix, and
    # both wrapper widths: NFLX and NVDA on 2026-09-15 wrote " calls"/" invoke"
    # (single and double wrapped) as the trader's "Computed verification".
    for edge in ("\uff5cDSML\uff5c", "\uff5c\uff5cDSML\uff5c\uff5c"):
        field_spelling = (
            "<" + edge + " calls>"
            + "<" + edge + ' invoke name="get_risk_gate">'
        )
        assert any(
            "tool-call markup" in c.claim
            for c in rv._self_correction_artifacts(field_spelling)
        ), edge


def test_ema20_does_not_cross_table_pipe():
    # IREN 2026-09-10 market.md: 'Chandelier / EMA20 trail | 39.8302 / 41.7342'
    # - the chandelier (39.83) is a DIFFERENT level from EMA20 (41.73); the
    # ema20 metric must not attribute the chandelier value across the row.
    t = ("get_swing_exits: chandelier stop **39.8302** (exit=False), EMA20 "
         "trail **41.7342** (trail_exit=False)\n"
         "| Chandelier / EMA20 trail | 39.8302 / 41.7342 |")
    cs = rv._internal_conflicts(t)
    assert not any("ema20" in c.claim for c in cs)


def test_atr_stop_basis_dual_flags():
    # IREN 2026-09-10: headline ATR 3.38 vs the swing-set's 3.1533 used for
    # the structure stop (34.81 - 3.1533 = 31.6567, not 34.81 - 3.38).
    t = ("ATR 3.38 as stop yardstick; get_swing_set structure_stop uses "
         "ATR 3.1533 below swing low 34.81")
    cs = rv._internal_conflicts(t)
    assert any("atr" in c.claim for c in cs)


def test_sector_rank_identity_clean_single_value():
    assert rv._sector_rank_identity("XLK rank #4 (tracking)") == []
    assert rv._sector_rank_identity("XLK rank4, XLE rank1") == []


def test_eps_estimate_duals_clean_when_single_value():
    t = "next print 2026-10-28 (est EPS 4.72); forward table 2026-10-28 est 4.72"
    assert rv._eps_estimate_duals(t) == []


def test_expected_band_identity_clean_when_real_band():
    t = "expected earnings move 6.6%; band [458.04, 522.90]"
    assert rv._expected_band_identity(t) == []
    assert rv._expected_band_identity("expected move 6.6%") == []


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
    # The provider is down, so the PROSE is unverified - but the deterministic
    # layer read the report's figures, so the honest label is NUMERIC_ONLY, not
    # UNKNOWN (which now means "nothing ran at all"). The degrade contract is
    # unchanged where it matters: never raise, and never upgrade the LLM verdict.
    assert payload["verification"]["fundamentals"]["overall"] == "NUMERIC_ONLY"


def test_verify_report_dir_unknown_when_there_is_no_figure_to_check(tmp_path, monkeypatch):
    """A stem with no extractable figure stays UNKNOWN under a dead provider."""
    report_dir = _mk_report_dir(tmp_path, reports={"fundamentals": "Prose with no figures at all.\n"})
    monkeypatch.setattr(
        "tradingagents.agents.utils.structured.invoke_structured_or_freetext",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("provider down")),
    )
    payload = rv.verify_report_dir(report_dir, llm_override=_NoopLLM(), max_calls=1)
    assert payload["verification"]["fundamentals"]["overall"] == "UNKNOWN"
    assert payload["verification"]["fundamentals"]["basis"] == []


class _NoopLLM:
    def invoke(self, prompt):  # noqa: ANN001
        class _R:
            content = ""
        return _R()


# ---------------------------------------------------------------------------
# Valuation-identity checks (MU 2026-09-09 review loop)
# ---------------------------------------------------------------------------


def test_dupont_identity_flags_numerator_product_mismatch():
    text = (
        "DuPont: ROE ~35% decomposed as margin-led — net_margin 0.5591, "
        "asset_turnover 0.8929, equity_multiplier 1.3315"
    )
    claims = rv._dupont_identity(text)
    assert len(claims) == 1
    assert claims[0].status == "INTERNAL_CONFLICT"


def test_dupont_identity_clean():
    text = "ROE 20.0% (net_margin 0.50 asset_turnover 1.00 equity_multiplier 0.40)"
    assert rv._dupont_identity(text) == []


def test_dupont_identity_scoped_to_same_line():
    # NXPI 2026-09-09: on-line DuPont ROE 26.1% correctly equals the product
    # of its quoted inputs; a DIFFERENT screen's ROE 19.34% (analyst verdict,
    # another period) is NOT a conflict. The check must not compare the
    # product against the first ROE in the whole document.
    text = (
        "DuPont ROE 26.1% — margin-led (net_margin 0.2256, asset_turnover "
        "0.4943, equity_multiplier 2.339): quality-driven\n"
        "get_analyst_verdict ROE 19.34%"
    )
    assert rv._dupont_identity(text) == []


def test_dupont_identity_flags_offline_inputs_even_with_other_roe():
    # A genuine contradiction is still caught when the product is wildly off
    # the on-line ROE (MU 2026-09-09 case: 66.4% vs stated 35%).
    text = (
        "DuPont ROE 35% decomposed as margin-led (net_margin 0.5591, "
        "asset_turnover 0.8929, equity_multiplier 1.3315)"
    )
    cs = rv._dupont_identity(text)
    assert any(c.status == "INTERNAL_CONFLICT" and "66" in c.claim for c in cs)


def test_pe_basis_conflict_catches_annual_vs_ttm():
    text = (
        "P/E: 135.94\nDiluted EPS | TTM $44.17\n"
        "latest price $1,027.77"
    )
    claims = rv._pe_basis_conflict(text)
    assert len(claims) == 1
    assert claims[0].status == "INTERNAL_CONFLICT"
    # 1027.77 / 44.17 = 23.27, not 135.94
    assert "23.27" in claims[0].claim


def test_pe_basis_clean_when_consistent():
    text = "P/E 12.5\nEPS ttm $4.00\nprice $50.00"
    assert rv._pe_basis_conflict(text) == []


def test_ev_net_cash_conflict_flags_ev_above_mcap():
    text = (
        "- EV: 1,166,392,461,568\n"
        "- Market cap: 1,160,756,461,568\n"
        "net CASH ≈ $19.65B (cash 26.02B - debt 6.38B)"
    )
    claims = rv._ev_net_cash_conflict(text)
    assert len(claims) == 1
    assert claims[0].status == "INTERNAL_CONFLICT"


def test_ev_net_cash_clean_when_consistent():
    text = "- EV: 1,140,000,000,000\n- Market cap: 1,160,000,000,000\nnet CASH $19.65B"
    assert rv._ev_net_cash_conflict(text) == []


# --- NVDA 2026-09-12 review loop: basis identities (D5/D7 + ratio bases) ----


def test_net_debt_identity_flags_r2_sign_flip():
    # Verbatim R2 rows: cash+ST investments $62.47B, total debt $38.35B
    # (=> ~$24.1B net CASH) yet the report prints "net debt of $10.9B".
    text = (
        "| Item | 2026-07-31 |\n"
        "| Cash + ST Investments | $62.47B |\n"
        "| Total Debt | **$38.35B** |\n"
        "| Net Debt | $10.92B | net cash | net cash |\n"
        "\n**Total debt jumped from $12.35B to $38.35B** (+$26B in one quarter), "
        "flipping the company to **net debt of $10.9B**.\n"
    )
    cs = rv._net_debt_identity(text)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "62.47" in cs[0].claim and "38.35" in cs[0].claim


def test_net_debt_identity_clean_when_net_cash_agrees():
    text = (
        "Cash + ST Investments $62.47B; Total Debt $38.35B; net cash of $24.12B."
    )
    assert rv._net_debt_identity(text) == []


def test_net_debt_identity_ignores_a_vendor_row_the_report_rejects():
    # MSFT 2026-09-16 fundamentals.md quotes the vendor "Net Debt
    # 19,359,000,000" row in order to correct it ("mis-signed and I do not
    # quote it as debt") beside its own +19,825,000,000 net cash. The quoted
    # row is not the report's figure, so there is nothing to reconcile.
    row = "the vendor \"Net Debt 19,359,000,000\" row {0}."
    body = ("**Net cash**: cash + ST investments 76,651,000,000 vs total debt "
            "56,826,000,000 = **+19,825,000,000 net cash**; ")
    rejected = body + row.format("is mis-signed and I do not quote it as debt")
    assert rv._net_debt_identity(rejected) == []
    # ...and the cue is what suppresses it: quoted as-is, the same row is read
    # as the report's net figure and the identity check fires (19.36 vs 19.83).
    quoted = body + row.format("is carried beside it")
    cs = rv._net_debt_identity(quoted)
    assert len(cs) == 1 and "19.36" in cs[0].claim


def test_current_ratio_identity_flags_r1_cr_vs_pair():
    # Verbatim R1: CA/CL $197.41B / $43.02B (= 4.588) against quoted CR 4.6808.
    text = (
        "Current Assets/Current Liabilities = $197.41B / $43.02B. "
        "get_balance_sheet_health: **pass** (D/E 0.0702 < 1.0; "
        "current ratio 4.6808 > 1.5)."
    )
    cs = rv._current_ratio_identity(text)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "4.6808" in cs[0].claim and "4.588" in cs[0].claim


def test_current_ratio_identity_clean_when_consistent():
    text = "Current Assets/Current Liabilities = $197.41B / $43.02B; current ratio 4.59."
    assert rv._current_ratio_identity(text) == []


def test_roa_consistency_flags_r1_provider_passthrough():
    # Verbatim R1: ROA TTM 81.41% vs net margin 0.637 x asset turnover 0.946.
    text = (
        "TTM (Finnhub basic financials): gross margin 74.67%, net margin 63.66%, "
        "ROA TTM 81.41%. DuPont on the latest quarter (net margin 0.637, "
        "asset turnover 0.946, equity multiplier 1.399): **ROE 84.3%, margin-led**."
    )
    cs = rv._roa_consistency(text)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "81.41" in cs[0].claim and "60.2" in cs[0].claim


def test_roa_consistency_clean_when_product_matches():
    text = "ROA 65.0% with net margin 0.65 and asset turnover 1.00."
    assert rv._roa_consistency(text) == []


def test_quarter_label_consistency_flags_r2_same_date_two_quarters():
    # Verbatim R2 headers: 2025-07-31 is the 4th column, labelled Q1 FY26 by the
    # income table but Q2 FY26 by the cash-flow table (FY26 ends 2026-01).
    text = (
        "| Metric | Q2 FY27 | Q1 FY27 | Q4 FY26 | Q1 FY26 |\n"
        "|---|---|---|---|---|\n"
        "| Revenue | $96.22B | $81.62B | $68.13B | $46.74B |\n"
        "| Item | 2026-07-31 | 2026-04-30 | 2026-01-31 | 2025-07-31 |\n"
        "| Metric | Q2 FY27 | Q1 FY27 | Q4 FY26 | Q2 FY26 |\n"
    )
    cs = rv._quarter_label_consistency(text)
    assert any(
        c.status == "INTERNAL_CONFLICT" and "2025-07-31" in c.claim
        and "Q1 FY26" in c.claim and "Q2 FY26" in c.claim
        for c in cs
    )


def test_quarter_label_consistency_clean_when_labels_agree():
    text = (
        "| Metric | Q2 FY27 | Q1 FY27 |\n"
        "|---|---|---|\n"
        "| Item | 2026-07-31 | 2026-04-30 |\n"
        "| Revenue | $96.22B | $81.62B |\n"
    )
    assert rv._quarter_label_consistency(text) == []
    # No date/label binding supplied by the report -> nothing to check.
    assert rv._quarter_label_consistency("Report has no tables at all.") == []


def test_internal_conflicts_altman_z_pair():
    text = "Altman Z 24.2 (body)\n| Altman Z | 25.70 |"
    cs = rv._internal_conflicts(text)
    assert any(c.status == "INTERNAL_CONFLICT" and c.claim.startswith("'altman z'") for c in cs)


def test_fed_cuts_contradiction_flags_0_vs_93():
    # IGV 2026-09-09: news.md asserted the same Polymarket event at "Yes 0%"
    # (line 11) and "Yes 93%" (summary table), with no prediction-market leaf.
    text = (
        'Polymarket: "Will Fed rate cuts happen in 2026?" **Yes 0%** — settled.\n'
        "| Fed cuts 2026 | Yes 93% (Polymarket) |"
    )
    cs = rv._fed_cuts_contradiction(text)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "0%" in cs[0].claim and "93%" in cs[0].claim


def test_fed_cuts_contradiction_clean_single_value():
    assert rv._fed_cuts_contradiction('Will Fed rate cuts happen in 2026? Yes 0%.') == []
    assert rv._fed_cuts_contradiction("Fed cuts 2026: Yes 93%.") == []


def test_drawdown_identity_flags_mismatch():
    # SOXX 2026-09-09: claimed "~39% below 52-week high" with price 532 /
    # high 655.95 => 18.9%. The drawdown must match price/high - 1.
    text = (
        "NAV ≈ $532 is at ~39% below its 52-week high.\n"
        "52-week high 655.95, latest price $532.00"
    )
    cs = rv._drawdown_identity(text)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "18.9%" in cs[0].claim or "18.8%" in cs[0].claim


def test_drawdown_identity_clean_when_consistent():
    text = "price 532.00, 52-week high 655.95 ->  .,18.9% below the high."
    assert rv._drawdown_identity(text) == []


def test_beat_streak_identity_flags_overcount():
    # DELL 2026-09-10: claimed "three straight >40% EPS beats" but
    # the surprise table shows +44.0 / +100.8 / +14..6 / +15.7 — only two
    # consecutive quarters exceed 40%.
    text = (
        "Momentum: three straight >40% EPS beats.\n"
        "| Period | Date | EPS est | EPS act | Surprise% | Day move | Implied |\n"
        "| 2027/Q2 |2026-09-01 |4.4029 |6.34 |+44.0 |+15.8% |10.9% |\n"
        "| 2027/Q1 |2026-05-28 |2.61 |5.24 |+100.8 |+32.8% |12.5% |\n"
        "| 2026/Q4 |2026-02-26 |2.94 |3.37 |+14.6 |+21.9% |9.5% |\n"
    )
    cs = rv._beat_streak_identity(text)
    assert len(cs) == 1
    assert cs[0].status == "INTERNAL_CONFLICT"
    assert "2 consecutive" in cs[0].claim


def test_beat_streak_identity_clean_when_matches():
    text = (
        "Surprise streak: 2 straight >40% EPS beats.\n"
        "| 2027/Q2 |2026-09-01 |4.4029 |6.34 |+44.0 |+15.8% |10.9% |\n"
        "| 2027/Q1 |2026-05-28 |2.61 |5.24 |+100.8 |+32.8% |12.5% |\n"
    )
    assert rv._beat_streak_identity(text) == []


def test_internal_conflicts_scenario_dcf_bear_dual_values():
    # DELL 2026-09-10: body quotes scenario-DCF bear 87.75, summary
    # table 87.60 — a transcription slip that must flag.

    text = (
        "Scenario DCF (bear/base/bull): **$87.75 / $115.51 / $240.53**\n"
        "| Scenario DCF | Above bull | bear 87.60 / base 115.51 / bull 240.53 |\n"
    )
    cs = rv._internal_conflicts(text)
    assert any(c.status == "INTERNAL_CONFLICT" for c in cs)
    assert any("scenario dcf bear" in c.claim for c in cs)


# --- R-multiple (2R/3R) identity — market-side(MU 2026-09-09 review loop)


def test_r_multiple_identity_flags_wrong_3r():
    # Generating the classic "swap" is outside tolerance only for a real
    # framework error; a 0.06% transcription typo stays under (evidence anchor
    # catches that class). Here the 3R is genuinely mis-bound.
    text = (
        "entry 100.00, structure stop 90.00, 2R/3R targets 120.00 / 130.00"
    )  # 2R=120 ✓, 3R=130 vs correct 100+3*10=130 → clean
    assert rv._r_multiple_identity(text) == []


def test_r_multiple_identity_flags_genuine_error():
    text = "entry 100.00, structure stop 90.00, 2R/3R targets 120.00 / 125.00"
    cs = rv._r_multiple_identity(text)
    assert any("3R" in c.claim and "125.00" in c.claim for c in cs)


def test_r_multiple_identity_respects_two_frameworks():
    # Structure stop 90 -> 2R 120 / 3R 130; chandelier stop 95 -> 2R 110 / 3R 115.
    # A single-pair check must NOT cross them (MU 2026-09-09 structure vs chandelier).
    text = (
        "entry 100.00 | structure stop 90.00, 2R/3R targets 120.00 / 130.00\n"
        "chandelier stop 95.00, 2R/3R targets 110.00 / 115.00"
    )
    assert rv._r_multiple_identity(text) == []


def test_r_multiple_compound_4digit_3r_captured():
    # The MU pattern: "2R/3R targets **1357.69 / 1521.68**" — 3R reads the
    # value after '/' even when the number has 4 leading digits.
    m = rv._RMULT_RE.search("3R targets **1357.69 / 1521.68**")
    assert m is not None
    assert rv._rmult_value(m) == 1521.68


# ---------------------------------------------------------------------------
# Macro-authority gate (SKHY 2026-09-09 review loop)
# ---------------------------------------------------------------------------
# news.md quoted "Polymarket: no Fed rate cuts in 2026 = Yes 93%", "10Y at
# 4.78 FRED print", "RRP at 0.432B", "WTI 91.48" with NO
# get_prediction_markets / get_macro_indicators leaf in the tree — the
# macro-provenance prompt pin (then headed MACRO MUSTS, now MACRO DATA
# PROVENANCE) was not enforced. The gate must flag these lines
# independent of the LLM verdict.

_SKHY_STYLE_NEWS = (
    "- FOMC 2026-09-15: market prices 3.75-4.00% at 60.2% (get_fed_watch). "
    "Polymarket: no Fed rate cuts in 2026 = Yes 93% - cut probability is negligible.\n"
    "- Liquidity: RRP at 0.432B (2026-09-09), drained to floor; WTI 91.48 +9.22% window.\n"
)


def test_macro_gate_flags_recalled_polymarket_without_prediction_leaf():
    evidence = {"news": [{"tool": "get_fed_watch", "status": "ok", "content": "| 2026-09-15 | 60.2%"}]}
    claims = rv._macro_authority_gate(_SKHY_STYLE_NEWS, evidence, "news")
    flagged = [c for c in claims if c.status == "UNSUPPORTED"]
    # Both lines fail: no get_prediction_markets / get_macro_indicators leaf.
    assert len(flagged) == 2
    # The Polymarket line names the missing pinned tool in its reason.
    assert any("get_prediction_markets" in c.reason for c in flagged)


def test_macro_gate_passes_with_full_pinned_tool_set():
    evidence = {
        "news": [
            {"tool": "get_fed_watch", "status": "ok", "content": "| 2026-09-15 | 60.2%"},
            {"tool": "get_prediction_markets", "status": "ok", "content": "no Fed rate cuts in 2026 Yes 93%"},
            {"tool": "get_macro_indicators", "status": "ok", "content": "RRP 0.432B WTI oil 91.48"},
        ]
    }
    claims = rv._macro_authority_gate(_SKHY_STYLE_NEWS, evidence, "news")
    assert claims == []


def test_macro_gate_passes_fomc_line_but_flags_rrp_without_macro_leaf():
    # fed_watch/prediction leaves ground the FOMC line; absent
    # get_macro_indicators, the RRP/WTI line remains recalled.
    evidence = {
        "news": [
            {"tool": "get_fed_watch", "status": "ok", "content": "| 2026-09-15 | 60.2%"},
            {"tool": "get_prediction_markets", "status": "ok", "content": "no Fed rate cuts in 2026 Yes 93%"},
        ]
    }
    claims = rv._macro_authority_gate(_SKHY_STYLE_NEWS, evidence, "news")
    unsupported = [c for c in claims if c.status == "UNSUPPORTED"]
    assert len(unsupported) == 1
    assert "RRP" in unsupported[0].claim


def test_macro_gate_passes_when_macro_leaf_carries_term():
    # The term is present in a macro leaf's content even without the exact
    # tool name -> the line is grounded (e.g. WTI from an economic calendar).
    evidence = {
        "news": [
            {"tool": "get_economic_calendar", "status": "ok", "content": "WTI crude 91.2 rescheduled"},
        ]
    }
    claims = rv._macro_authority_gate(_SKHY_STYLE_NEWS, evidence, "news")
    unsupported = [c for c in claims if c.status == "UNSUPPORTED"]
    # Two macro lines remain flagged; the WTI-bearing economic-calendar line
    # is grounded by content, but the Polymarket/10Y line still has no leaf.
    assert any("Polymarket" in c.claim for c in unsupported)


# --- the comma-only capture that killed the whole verifier -----------------
# GOOG 2026-09-11: sentiment.md writes "sub-30 P/E, cheap vs Costco/Meta". The
# regex family `([\d,]+...)` matched a COMMA-ONLY capture, `float("," .replace)`
# raised ValueError out of _pe_basis_conflict, and verify_report_dir lost the
# entire payload for every section — 30 of 35 report trees have no
# verify_flags.json. Two guards now: every number capture requires a digit, and
# each metric family is isolated (recorded in metric_errors, never silently).


def test_pe_capture_requires_a_digit(tmp_path):
    """The exact prose that crashed the gate must parse to nothing, not raise."""
    t = (
        "StockTwits bull case (sub-30 P/E, cheap vs Costco/Meta) is the same "
        "argument.\nLast: 336.37; EPS TTM $12.34.\n"
    )
    assert rv._pe_basis_conflict(t) == []          # would raise ValueError before
    assert rv._text_metrics(t)[1] == []            # no metric errored


def test_verify_report_dir_survives_a_comma_only_pe_capture(tmp_path):
    """A report tree containing that prose must still yield a payload."""
    d = _mk_report_dir(
        tmp_path,
        reports={
            "sentiment": "Bull case: sub-30 P/E, cheap vs Costco/Meta.\n",
            "fundamentals": "P/E 17 vs META 23; EPS TTM $12.34 at price 336.37.\n",
        },
    )
    payload = rv.verify_report_dir(d, llm_override=_mk_llm('{"claims": [], "overall": "PASS"}'))
    assert set(payload["verification"]) == {"sentiment", "fundamentals"}
    for entry in payload["verification"].values():
        assert "metric_errors" not in entry, entry.get("metric_errors")


def test_verify_report_dir_records_a_failing_metric(tmp_path, monkeypatch):
    """A metric that cannot parse a report is recorded, not fatal: the other
    metrics' claims and the section entry still land in the payload."""
    def _boom(_text):
        raise ValueError("could not convert string to float: ''")

    monkeypatch.setitem(rv._text_metrics.__globals__, "_sma200_identity", _boom)
    d = _mk_report_dir(tmp_path, reports={"market": "200-day 335.17.\n"})
    payload = rv.verify_report_dir(d, llm_override=_mk_llm('{"claims": [], "overall": "PASS"}'))
    entry = payload["verification"]["market"]
    assert entry["overall"] in ("PASS", "UNKNOWN", "FLAG")
    assert any(e.startswith("sma200_identity: ValueError") for e in entry["metric_errors"])


# ---------------------------------------------------------------------------
# Tree-level debate check (no LLM): did the advertised structured debate run?
# ---------------------------------------------------------------------------


def _write_card(tmp_path, debate):
    (tmp_path / "run_card.json").write_text(
        json.dumps({"ticker": "TST", "debate": debate}), encoding="utf-8"
    )


def test_debate_flag_fires_on_a_degraded_tree(tmp_path):
    """enable_debate on + no evidence file -> FLAG (NVDA 2026-09-12: the tree
    looked normal while the structured debate had fallen back to the legacy
    path, and nothing in verify_flags.json said so)."""
    _write_card(
        tmp_path,
        {"enabled": True, "degraded": True, "reason": "L1 hard breach; baseline fallback"},
    )
    out = rv._debate_degradation(tmp_path)
    assert out["degraded"] is True
    assert out["evidence"] is False
    assert "baseline fallback" in out["reason"]


def test_debate_flag_ok_when_the_evidence_is_on_disk(tmp_path):
    (tmp_path / "2_research").mkdir(parents=True)
    (tmp_path / "2_research" / "structured_debate.md").write_text("## x\n", encoding="utf-8")
    _write_card(tmp_path, {"enabled": True, "degraded": False, "reason": "hard cap (5 rounds)"})
    out = rv._debate_degradation(tmp_path)
    assert out["degraded"] is False
    assert out["evidence"] is True


def test_debate_flag_is_silent_when_debate_was_disabled(tmp_path):
    """The legacy path is not a degradation when the SD debate was never asked
    for - the flag must not fire on every non-debate tree."""
    _write_card(tmp_path, {"enabled": False, "degraded": False, "reason": ""})
    assert rv._debate_degradation(tmp_path)["degraded"] is False


def test_debate_flag_ignores_a_tree_without_the_run_card_block(tmp_path):
    """A tree written before the run-card block existed has no verdict to
    check: unknown is not a degradation, and the artifact still counts."""
    out = rv._debate_degradation(tmp_path)
    assert out == {"enabled": None, "evidence": False, "degraded": False, "reason": ""}


def test_debate_flag_falls_back_to_the_artifact_when_the_card_lacks_the_verdict(tmp_path):
    """A card with `enabled` but no `degraded` (an older writer, or a hand-made
    card) is judged on the artifact itself."""
    (tmp_path / "2_research").mkdir(parents=True)
    (tmp_path / "2_research" / "structured_debate.md").write_text("## x\n", encoding="utf-8")
    _write_card(tmp_path, {"enabled": True})
    assert rv._debate_degradation(tmp_path)["degraded"] is False
    (tmp_path / "2_research" / "structured_debate.md").unlink()
    assert rv._debate_degradation(tmp_path)["degraded"] is True


def test_verify_report_dir_carries_the_debate_block(tmp_path):
    d = _mk_report_dir(tmp_path)
    _write_card(d, {"enabled": True, "degraded": True, "reason": "no turns"})
    payload = rv.verify_report_dir(d, llm_override=_mk_llm('{"claims": [], "overall": "PASS"}'))
    assert payload["debate"]["degraded"] is True
    assert payload["debate"]["reason"] == "no turns"


# --- the v1.1 execution envelope (plan R3 / T9) ----------------------------
# The artifact is the executor's only input, and it dead-letters what it cannot
# validate. These checks are pure file inspection: no LLM, no config, no run.


def _sealed_decision(**overrides):
    """A conformant 1.1.0 artifact; overrides are applied before sealing.

    The artifact is built from TODAY's effective date with ``produced_at``
    pinned to that session's start. A fixture with a hard-coded historical date
    is not stable: ``expires_at`` is derived from ``effective``, so once the real
    clock moved past it the artifact was first self-inconsistent
    (``invalid_timestamp``: expires_at before the wall-clock produced_at) and
    then ``expired`` — which is how all four envelope tests went red on
    2026-09-15 with no product change. Pinning produced_at inside the fixture's
    own window keeps them ordered for every clock.
    """
    from datetime import date, datetime, time, timezone

    from tradingagents import execution_contract as ec

    run_date = date.today()
    doc = {
        "schema_version": ec.SCHEMA_VERSION,
        "ticker": "NVDA",
        "effective_date": run_date.isoformat(),
    }
    doc.update(
        ec.envelope_fields(
            {},
            run_id=f"NVDA_{run_date.strftime('%Y%m%d')}_005957",
            effective=run_date,
            now=datetime.combine(run_date, time.min, tzinfo=timezone.utc),
        )
    )
    doc.update(overrides)
    return ec.seal(doc)


def _write_decision(tree, doc):
    (tree / "research_decision.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8"
    )
    return tree


def test_envelope_block_is_ok_for_a_conformant_artifact(tmp_path):
    _write_decision(tmp_path, _sealed_decision())

    out = R._envelope_integrity(tmp_path)
    assert out["problems"] == []
    assert out["version"] == "1.1.0" and out["strict"] is True


def test_envelope_flags_a_missing_expiry(tmp_path):
    from tradingagents import execution_contract as ec

    doc = _sealed_decision()
    doc.pop("expires_at")
    _write_decision(tmp_path, ec.seal(doc))

    codes = [p["code"] for p in R._envelope_integrity(tmp_path)["problems"]]
    assert "missing_field" in codes


def test_envelope_flags_an_artifact_whose_session_has_closed(tmp_path):
    from datetime import date, datetime, timezone

    from tradingagents import execution_contract as ec

    doc = {
        "schema_version": ec.SCHEMA_VERSION,
        "ticker": "NVDA",
        "effective_date": "2026-09-01",
    }
    doc.update(
        ec.envelope_fields(
            {},
            run_id="NVDA_20260901_005957",
            effective=date(2026, 9, 1),
            now=datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc),
        )
    )
    _write_decision(tmp_path, ec.seal(doc))

    codes = [p["code"] for p in R._envelope_integrity(tmp_path)["problems"]]
    assert codes == ["expired"]


def test_envelope_flags_a_body_edited_after_the_seal(tmp_path):
    doc = _sealed_decision()
    doc["rating"] = "Overweight"  # a rebuild or a hand edit, after the hashes
    _write_decision(tmp_path, doc)

    codes = [p["code"] for p in R._envelope_integrity(tmp_path)["problems"]]
    assert codes == ["artifact_hash_mismatch"]


def test_envelope_flags_a_reserved_field_and_an_out_of_range_score(tmp_path):
    _write_decision(tmp_path, _sealed_decision(binding_gate="halt", opportunity_score=142.0))

    codes = sorted(p["code"] for p in R._envelope_integrity(tmp_path)["problems"])
    assert codes == ["invalid_opportunity_score", "producer_set_reserved_field"]


def test_envelope_does_not_flag_a_legacy_artifact(tmp_path):
    """The executor reads a version-less artifact as 1.0.0 and skips the stricter
    checks - so flagging it here would mark every historical tree as broken."""
    _write_decision(tmp_path, {"schema_version": 1, "ticker": "NVDA", "rating": "Hold"})

    out = R._envelope_integrity(tmp_path)
    assert out == {"present": True, "version": "1.0.0", "strict": False, "problems": []}


def test_envelope_reports_a_missing_artifact_without_flagging(tmp_path):
    assert R._envelope_integrity(tmp_path)["present"] is False


def test_envelope_survives_an_unreadable_artifact(tmp_path):
    """A malformed file is a flag, never an exception: the tree must still render."""
    (tmp_path / "research_decision.json").write_text("{not json", encoding="utf-8")

    out = R._envelope_integrity(tmp_path)
    assert [p["code"] for p in out["problems"]] == ["unreadable"]


def test_verify_report_dir_carries_the_envelope_block(tmp_path):
    d = _mk_report_dir(tmp_path)
    _write_decision(d, _sealed_decision(binding_gate="halt"))

    payload = R.verify_report_dir(d, llm_override=_mk_llm('{"claims": [], "overall": "PASS"}'))
    assert payload["envelope"]["strict"] is True
    assert [p["code"] for p in payload["envelope"]["problems"]] == [
        "producer_set_reserved_field"
    ]


def test_the_cli_counts_an_envelope_flag_in_its_exit_code(tmp_path, monkeypatch, capsys):
    import scripts.report_verify as rvc

    _write_decision(tmp_path, _sealed_decision(opportunity_score=-1.0))
    payload = R.verify_report_dir(
        tmp_path, llm_override=_mk_llm('{"claims": [], "overall": "PASS"}')
    )
    monkeypatch.setattr(rvc, "verify_report_dir", lambda *a, **k: payload)
    monkeypatch.setattr("sys.argv", ["report_verify.py", "--report-dir", str(tmp_path)])

    assert rvc.main() == 1
    printed = capsys.readouterr().out
    assert "envelope      FLAG" in printed and "invalid_opportunity_score" in printed


def test_the_identity_fan_out_registers_the_basis_checks():
    """The four basis identities must be REGISTERED, not merely defined.

    Each has its own unit test above, so dropping one from
    ``_valuation_identity_checks`` (the fan-out the run card and the CLI both
    call) would leave every unit test green while the check stopped running -
    the exact failure mode that let these defects ship unnoticed.
    """
    net_debt = (
        "Cash + ST Investments: $62.47B\n"
        "Total Debt: $38.35B\n"
        "Net Debt: $10.92B\n"
    )
    assert any("net cash" in c.claim.lower() for c in rv._valuation_identity_checks(net_debt))

    labels = (
        "| Metric | Q2 FY27 | Q1 FY27 | Q4 FY26 | Q1 FY26 |\n"
        "|---|---|---|---|---|\n"
        "| Revenue | $96.22B | $81.62B | $68.13B | $46.74B |\n"
        "| Item | 2026-07-31 | 2026-04-30 | 2026-01-31 | 2025-07-31 |\n"
        "| Metric | Q2 FY27 | Q1 FY27 | Q4 FY26 | Q2 FY26 |\n"
    )
    assert any(
        "2025-07-31" in c.claim for c in rv._valuation_identity_checks(labels)
    )

    ratio = (
        "Current Assets/Current Liabilities = $197.41B / $43.02B\n"
        "current ratio 4.6808\n"
    )
    assert any("4.6808" in c.claim for c in rv._valuation_identity_checks(ratio))

    roa = "ROA TTM 81.41% vs net_margin 0.637 asset_turnover 0.946\n"
    assert any("81.41" in c.claim for c in rv._valuation_identity_checks(roa))

    # The date-count identity is only enabled by the anchor the caller passes
    # (the run date), so its registration is checked with one.
    dated = "| Next earnings | 2026-11-17 | get_earnings_calendar | 83 days out |"
    assert any(
        "83 days out" in c.claim
        for c in rv._valuation_identity_checks(dated, as_of="2026-09-12")
    )


# ---------------------------------------------------------------------------
# Date-count identity (NVDA 2026-09-12 news.md)
# ---------------------------------------------------------------------------


def test_days_countdown_identity_flags_the_nvda_83_day_error():
    """The report's own two dates contradict its day count.

    "2026-11-17 estimate=2.47 ... 83 days out" - 83 is the gap from the PRIOR
    print (2026-08-26 -> 2026-11-17); from the analysis date (2026-09-12) the
    count was 66, and no tool printed 83.
    """
    row = (
        "| Next earnings | 2026-11-17 estimate=2.47 (vendor-estimated) | "
        "get_earnings_calendar | 83 days out; not a near catalyst |"
    )
    claims = rv._days_countdown_identity(row, "2026-09-12")
    assert len(claims) == 1
    assert claims[0].status == "INTERNAL_CONFLICT"
    assert "83 days out" in claims[0].claim and "66 days" in claims[0].claim


def test_days_countdown_identity_needs_the_anchor():
    """No anchor, no claim: an inferred anchor would manufacture findings."""
    assert rv._days_countdown_identity("2026-11-17 ... 83 days out") == []
    assert rv._days_countdown_identity("2026-11-17 ... 83 days out", None) == []
    assert rv._days_countdown_identity("", "2026-09-12") == []
    # A malformed anchor is as unusable as a missing one: falling back to
    # "today" would manufacture findings from a caller bug.
    assert rv._days_countdown_identity("2026-11-17 ... 83 days out", "2026-13-01") == []
    assert rv._days_countdown_identity("2026-11-17 ... 83 days out", "junk") == []


def test_days_countdown_identity_tolerates_one_day():
    """The anchor is the run date while a report may date its data to the prior
    close, so a one-day offset is not a defect; two days is."""
    for stated in (65, 66, 67):
        assert rv._days_countdown_identity(
            f"2026-11-17 is {stated} days out", "2026-09-12"
        ) == [], stated
    assert rv._days_countdown_identity("2026-11-17 is 68 days out", "2026-09-12")


def test_days_countdown_identity_ignores_lookback_windows():
    """Regression: "worst in 30 days" is a lookback, not a countdown (reading
    it as one flagged the clean TSM 2026-09-09 news.md)."""
    t = (
        "EODHD daily news sentiment: 2026-09-06 printed -0.82 with innovation "
        "-1.40 (worst in 30 days, 7d SMA fell to +0.33)"
    )
    assert rv._days_countdown_identity(t, "2026-09-09") == []


def test_days_countdown_identity_reads_elapsed_counts():
    """An "ago" count answers to the same arithmetic, in the other direction."""
    assert rv._days_countdown_identity("2026-08-26 print, 17 days ago", "2026-09-12") == []
    claims = rv._days_countdown_identity("2026-08-26 print, 83 days ago", "2026-09-12")
    assert len(claims) == 1 and "17 days" in claims[0].claim


def test_days_countdown_identity_ignores_wrong_side_dates():
    """A count's direction rules out one side of the anchor.

    AMZN 2026-09-14 news.md quoted the prior print's date (2026-07-30) on the
    same line as a forward count for the NEXT print (2026-10-29, not on the
    line); the past date carried no information and the check read a correct
    "45 days away" as a wrong one.
    """
    prior = (
        "get_earnings_catalyst (2026/Q2, pub 2026-07-30): implied move 8.2% - "
        "historically a major single-day event, but it is 45 days away."
    )
    assert rv._days_countdown_identity(prior, "2026-09-14") == []
    # The mirror case: a future date cannot be an elapsed count either.
    assert rv._days_countdown_identity(
        "the 2026-11-17 print is 45 days ago", "2026-09-14"
    ) == []
    # A same-side date that does not fit still flags (the check is not off).
    claims = rv._days_countdown_identity(
        "the 2026-11-17 print is 83 days away", "2026-09-14"
    )
    assert len(claims) == 1 and "64 days" in claims[0].claim


def test_primary_price_ignores_the_prior_session_close():
    """The spot price, not the close the session began from.

    TSM 2026-09-15 market.md opens with "Verified OHLCV ... C 413.23" and the
    next sentence quotes "Prev close 418.01"; the fallback entry took the
    latter and invented a 2R/3R mismatch against the swing-set stop.
    """
    line = "Massive.com snapshot: Last 414, Prev close 418.01, -4.01 (-0.96%)"
    assert rv._primary_price(line) is None
    assert rv._primary_price("Prior close 253.54 then Price 249.14") == 249.14


def test_primary_price_ignores_a_word_ending_in_at():
    """The report's spot price, not a number an ordinary word happens to precede.

    IEI 2026-09-15 market.md caveats its Alpaca live print with '... do not
    reconcile as a true print."* Treat 114.33 as unverified.' The alternation
    matched the "at" INSIDE "Treat", so the report-wide fallback entry was the
    price the report had just disowned - and the swing-set summary row's 2R/3R
    targets were then re-derived off the day low plus ATR (114.33 + 2*0.2939 =
    114.92 vs the quoted 115.2778), flagging two targets that are verbatim
    get_swing_set output.
    """
    text = (
        '"...do not reconcile as a true print."* Treat 114.33 as unverified. '
        "**Trend.** Close 114.45 sits below the 10 EMA.\n"
        "| Swing set | stop 114.0361, T1 115.2778, T2 115.6917, risk 0.36% | "
        "Structure stop basis |\n"
    )
    assert rv._primary_price(text) == 114.45
    assert rv._r_multiple_identity(text) == []


def test_reference_price_line_is_evidence_for_every_stem():
    """The run's reference-price line is prepended to each analyst's block, so
    a report citing it is grounded (TSM/AMZN 2026-09-15 news.md were flagged
    for quoting a price that no leaf carries)."""

    ref = "**Reference price: 413.23** (2026-09-15, FORMING intraday bar - provisional)"
    ev = {
        "news": [{"tool": "get_news", "status": "ok", "content": "px 416.60"}],
        rv.RENDERED_BLOCK_KEY: [
            {"analyst": "news", "block": ref + "\n\n## Tool Evidence"}
        ],
    }
    assert rv._reference_price_line(ev, "news") == ref
    assert rv._reference_price_line(ev, "market") == ""
    assert any(abs(d - 413.23) < 1e-9 for d in rv._evidence_decimals(ev, "news"))


def test_instrument_identity_line_is_evidence_for_every_stem():
    """The resolved-identity line ("Resolved identity: Company: X; Exchange: Y")
    reaches every analyst in its system message, so a report naming its venue is
    quoting the prompt - IEI 2026-09-16 and VTV 2026-09-16 both had a true
    venue flagged as fabrication. It is prepended beside the reference price
    and is evidence in the digest."""
    ident = (
        "**Instrument identity (resolved at run start):** "
        "Company: iShares 3-7 Year Treasury Bond ETF; Exchange: NGM"
    )
    ev = {
        "fundamentals": [{"tool": "get_fundamentals", "status": "ok", "content": "Name: x"}],
        rv.RENDERED_BLOCK_KEY: [
            {"analyst": "fundamentals", "block": ident + "\n\n## Tool Evidence"}
        ],
    }
    assert rv._instrument_identity_line(ev, "fundamentals") == ident
    assert rv._instrument_identity_line(ev, "news") == ""
    digest = rv._evidence_digest(ev, "fundamentals")
    assert "instrument_identity [ok]" in digest and "Exchange: NGM" in digest


def test_r_multiple_ignores_a_line_that_labels_its_own_multiple():
    """"targets T1(2R) 444.2039, T2(3R) 459.6909" off the swing set's own
    swing-low/ATR basis: with no entry on the line the report-wide spot is not
    their basis (TSM 2026-09-15 market.md)."""
    t = (
        "Price 413.23. `get_swing_set` structure stop 397.7429, risk 3.75% of "
        "close; targets T1(2R) 444.2039, T2(3R) 459.6909."
    )
    assert rv._r_multiple_identity(t) == []


def test_stop_candidate_rejects_a_parenthesised_metric_tail():
    """"puts 386.51 (structure stop) and 381.68 (200-SMA) in play" must not
    bind the SMA as the stop (WDC 2026-09-15 market.md flagged a correct 2R)."""
    t = (
        "Price 413.53. A close under 410.85 with volume puts 386.51 (structure "
        "stop) and 381.68 (200-SMA) in play toward T1 467.57."
    )
    assert rv._r_multiple_identity(t) == []


def test_vrp_unit_scoped_pair_is_not_a_conflict():
    """A percentage-point VRP and a variance-ratio VRP are two constructs
    (AMZN 2026-09-15 market.md: +2.10pp beside +0.0490)."""
    t = "Options: VRP +2.10pp (iv_read); vrp +0.0490 (variance_premium, IV 34.77% vs realized 26.82%)"
    assert rv._internal_conflicts(t) == []
    same = "VRP +2.10pp (iv_read) vs VRP +4.90pp (variance_premium)"
    assert rv._internal_conflicts(same)


def test_sum_identity_reads_a_unit_scaled_total():
    """Addends in millions with a total in dollars are one statement, not a
    slip (WDC 2026-09-15: 672+752+615+553 = $2,592,000,000)."""
    assert rv._sum_identity("Buybacks: 672+752+615+553 = $2,592,000,000") == []
    assert rv._sum_identity("OCF = 2.165+2.958+3.160+2.198 = $10.62B")


def test_chandelier_reprints_at_two_precisions_are_one_stop():
    """306.033 and 306.0336 are one stop printed twice (LRCX 2026-09-14)."""
    assert rv._chandelier_identity("chandelier 306.033 ... chandelier 306.0336") == []
    assert rv._chandelier_identity("chandelier 54.11 ... chandelier 58.2")


def test_dupont_identity_reads_only_the_decompositions_own_roe():
    """A line that names the bases it disagrees with is not a second failure
    (SKHY 2026-09-14: ROE 134.2% from the inputs, "This conflicts with
    get_ratios ROE 35.57%")."""
    t = (
        "get_dupont_read: ROE 134.2% - net_margin 0.8562, asset_turnover "
        "1.0742, equity_multiplier 1.4595. This conflicts with get_ratios "
        "ROE 35.57%."
    )
    assert rv._dupont_identity(t) == []


def test_roa_identity_needs_one_paragraph_and_one_basis():
    """The ROA and its decomposition must be the report's own claim, printed
    together: TSM/AMZN 2026-09-15 print them under different producers."""
    split = (
        "- get_fundamentals reports ROA 19.00% and Profit Margin 49.92%.\n"
        "\n"
        "- get_dupont_read: net_margin 0.4992, asset_turnover 0.5598.\n"
    )
    assert rv._roa_consistency(split) == []
    single = "ROA TTM 81.41% beside net margin 0.637 x asset turnover 0.946."
    assert rv._roa_consistency(single)


def test_internal_conflict_reads_a_stated_period_as_a_basis():
    """"D/E 0.37 (balance sheet 2025-12-31)" against "quarterly total
    debt/equity 0.2816" is a period difference, stated (AMZN 2026-09-15)."""
    t = (
        "- get_ratios reports D/E 0.37, balance-sheet data dated 2025-12-31.\n"
        "\n"
        "- get_basic_financials reports quarterly total debt/equity of 0.2816.\n"
    )
    assert rv._internal_conflicts(t) == []
    same = "get_ratios D/E 0.37 quarterly; get_basic_financials D/E 0.2816 quarterly"
    assert rv._internal_conflicts(same)


def test_unusable_note_stems_are_reported_not_judged():
    """A replaced-stem note is not a report: its own sentences describe the
    lost generation, so judging them produced one UNSUPPORTED flag per sentence
    (HPE 2026-09-14 fundamentals, NVDA 2026-09-15 market)."""
    assert rv._unusable_note("# NVDA - Market Analyst: SECTION UNUSABLE (generation degenerated)\n\n> ...")
    assert not rv._unusable_note("## NVDA - Market\n\n**Verdict:** ...")


def test_report_as_of_reads_the_run_directory_name():
    assert rv._report_as_of("reports/NVDA_20260912_160416") == "2026-09-12"
    assert rv._report_as_of("reports/NVDA_20261312_160416") is None  # month 13
    assert rv._report_as_of("reports/scratch") is None


# ---------------------------------------------------------------------------
# Typed basis registry + verdict provenance (2026-09-16)
# ---------------------------------------------------------------------------
# The checks here are regexes over prose; the registry is that same extraction
# emitted as data, so two runs of one ticker are comparable mechanically. The
# drift that motivated it leaves no prose trace to diff: the same
# (AMZN, 2026-09-14) call returned FY-annual flows at 22:5xZ and TTM quarters at
# 19:08Z (EV/EBIT 32.79 -> -30551.06), and one metric is quoted at two values
# across runs (LULU 5.50/4.40, MSFT rvol 0.30/0.4220, LRCX EPS 1.81/5.76).


def test_basis_of_prefers_the_stated_period():
    # The report's OWN period token is the only basis a comparison may rely on.
    assert rv._basis_of("EV/EBIT 32.79 (TTM)", "ev/ebit", "32.79") == "ttm:ttm"


def test_basis_of_falls_back_to_the_unit_class():
    assert rv._basis_of("Diluted EPS $24.67", "diluted eps", "24.67") == "level"
    assert rv._basis_of("ROE 22.09%", "roe", "22.09") == "percent"
    assert rv._basis_of("chandelier 3.0x below the high", "chandelier", "3.0") == "multiple"
    # A bare ratio carries no bound: it may exceed 1 (P/E 135.94 is ordinary).
    assert rv._basis_of("P/E 135.94", "p/e", "135.94") == "ratio"


def test_basis_registry_emits_deduped_typed_triples_with_provenance():
    reg = rv._basis_registry(
        "Diluted EPS $24.67 (leaf).\nDiluted EPS 24.67 again.\n", {24.67}
    )
    assert [(b.metric, b.value, b.basis, b.source) for b in reg] == [
        ("diluted eps", 24.67, "level", "evidence")
    ]


def test_basis_registry_marks_a_value_no_leaf_carries():
    reg = rv._basis_registry("Diluted EPS $24.67", set())
    assert [(b.value, b.source) for b in reg] == [(24.67, "report")]


def test_basis_registry_separates_two_stated_periods():
    """Two labelled quarters are two bases, not one metric at two values."""
    reg = rv._basis_registry(
        "Diluted EPS 2.78 (2026-03-31)\nDiluted EPS 5.75 (2026-06-30)\n", set()
    )
    bases = sorted(b.basis for b in reg)
    assert len(bases) == 2 and all(b.startswith("date:2026-") for b in bases), bases


def test_stem_overall_names_numeric_only_when_the_llm_half_failed():
    """UNKNOWN must mean "nothing ran" - not "the figures were checked clean"."""
    claims = [
        rv.VerifierClaim(
            claim="P/E 12.5 = price 50.00 / EPS 4.00", status="GROUNDED", reason="evidence"
        )
    ]
    anchored = rv.ReportVerification(report="market", claims=[], overall="UNKNOWN")
    # The signal is what was CHECKED, not what was found: a clean extraction is
    # still evidence that the figures were examined (this is the batch case -
    # market on two symbols had no conflict and no LLM verdict).
    assert rv._stem_overall(anchored, claims, deterministic_triples=2) == "NUMERIC_ONLY"
    assert rv._stem_overall(anchored, claims) == "UNKNOWN"
    assert rv._stem_overall(anchored, []) == "UNKNOWN"


def test_stem_overall_flags_on_a_deterministic_claim():
    claims = [
        rv.VerifierClaim(
            claim="current ratio 10.87 vs 1.329", status="INTERNAL_CONFLICT", reason="x"
        )
    ]
    anchored = rv.ReportVerification(report="fundamentals", claims=[], overall="UNKNOWN")
    assert rv._stem_overall(anchored, claims) == "FLAG"


def test_stem_overall_passes_the_llm_verdict_through():
    anchored = rv.ReportVerification(report="news", claims=[], overall="PASS")
    assert rv._stem_overall(anchored, []) == "PASS"


def test_verify_report_dir_carries_the_basis_registry(tmp_path):
    """The payload's machine-readable half: typed triples per stem."""
    d = _mk_report_dir(
        tmp_path,
        evidence={
            "market": [
                {
                    "tool": "get_ratios",
                    "status": "ok",
                    "content": "EV/EBIT 32.79 diluted EPS 24.67",
                }
            ]
        },
        reports={"market": "EV/EBIT 32.79 (TTM)\nDiluted EPS $24.67\n"},
    )
    payload = rv.verify_report_dir(d, llm_override=_mk_llm("not json at all"))
    entry = payload["verification"]["market"]
    assert entry["overall"] == "NUMERIC_ONLY", entry
    triples = {(b["metric"], b["value"], b["basis"], b["source"]) for b in entry["basis"]}
    assert ("diluted eps", 24.67, "level", "evidence") in triples, triples
    assert ("ev/ebit", 32.79, "ttm:ttm", "evidence") in triples, triples
