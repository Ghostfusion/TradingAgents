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
    assert any("'eps estimate'" in c.claim for c in out)


def test_internal_conflict_eps_single_value_clean():
    t = "EPS actual **7.04** vs estimate **5.012** (Finnhub)"
    assert rv._internal_conflicts(t) == []


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


def test_internal_conflict_ev_ebit_dual_values():
    # MU 2026-09-10 fundamentals: EV/EBIT quoted 65.2 (analyst verdict) and
    # 66.65 (get_ratios) - two values for one metric in one report.
    t = "EV/EBIT **65.2** (analyst verdict)  ...  EV/EBIT 66.65 (get_ratios)"
    out = rv._internal_conflicts(t)
    assert any("'ev/ebit'" in c.claim for c in out)


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
    assert payload["verification"]["fundamentals"]["overall"] == "UNKNOWN"


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
# MACRO MUSTS prompt pin was not enforced. The gate must flag these lines
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
