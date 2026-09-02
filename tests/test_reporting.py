"""R1b unit tests: risk gate injected into reports; compact risk mode; TOC."""

from tradingagents.reporting import _slugify, write_report_tree


def _state(verdict="PASS", reasons=None, risk_ctx=None):
    return {
        "risk_debate_state": {
            "aggressive_history": "aggressive prose\n",
            "conservative_history": "conservative prose\n",
            "neutral_history": "neutral prose\n",
            "judge_decision": "**Rating**: Hold\n**Executive Summary**: x\n",
        },
        "risk_gate": {"verdict": verdict, "reasons": reasons or []},
        "risk_snapshot": f"verdict={verdict}; size=10.0%; cvar=1.00%",
        "position_contract": "size 10.0% @ stop 95.0 (kelly=0.100)",
        "trader_investment_plan": "Trader plan",
        "risk_context": risk_ctx or {},
    }


def test_risk_gate_injected_ahead_of_debate(tmp_path):
    path = write_report_tree(_state(verdict="REJECT", reasons=["size over cap"]), "TST", tmp_path)
    aggressive = (tmp_path / "4_risk" / "aggressive.md").read_text(encoding="utf-8")
    assert "### Risk Gate (computed)" in aggressive
    assert "REJECT" in aggressive
    assert "aggressive prose" in aggressive  # transcript still present (non-compact)
    report = path.read_text(encoding="utf-8")
    assert "## IV. Risk Management Team Decision" in report
    assert "Risk Gate (computed)" in report


def test_decision_mirrors_risk_gate(tmp_path):
    write_report_tree(_state(verdict="WARN", reasons=["near cap"]), "TST", tmp_path)
    decision = (tmp_path / "5_portfolio" / "decision.md").read_text(encoding="utf-8")
    assert "Risk Gate (computed)" in decision
    assert "WARN" in decision


def test_compact_mode_verdict_only(tmp_path):
    path = write_report_tree(_state("PASS"), "TST", tmp_path, config={"risk_compact_report": True})
    assert (tmp_path / "4_risk" / "verdict.md").exists()
    assert not (tmp_path / "4_risk" / "aggressive.md").exists()
    report = path.read_text(encoding="utf-8")
    assert "aggressive prose" not in report  # chat suppressed
    assert "Risk Gate (computed)" in report


def test_no_gate_no_changes(tmp_path):
    state = {
        "risk_debate_state": {
            "judge_decision": "decision",
            "aggressive_history": "a",
        }
    }
    path = write_report_tree(state, "TST", tmp_path)
    report = path.read_text(encoding="utf-8")
    assert "Risk Gate (computed)" not in report


def test_risk_gate_renders_both_cvars(tmp_path):
    state = _state(
        verdict="REJECT",
        reasons=["cvar 3.25% > budget 3.00%"],
        risk_ctx={"single_cvar": 0.0123, "book_cvar": 0.0325},
    )
    path = write_report_tree(state, "TST", tmp_path)
    decision = (tmp_path / "5_portfolio" / "decision.md").read_text(encoding="utf-8")
    assert "Analyzed-name CVaR: 1.23%" in decision
    assert "Portfolio (book) CVaR: 3.25% — this fed the gate" in decision
    report = path.read_text(encoding="utf-8")
    assert "Analyzed-name CVaR: 1.23%" in report


def test_iv_a_computed_decision_context_surfaces_in_report(tmp_path):
    """The advisory decision context is surfaced as IVa when a plan card is
    present (Phase A-E wiring; the context must reach final_state to render)."""
    state = {
        **_state(verdict="PASS"),
        "computed_decision_context": (
            "Computed regime gate (mean-reversion entry): verdict=clean pass=True "
            "vol_pct=0.4 fast_downtrend=False reasons=stable\n\n"
            "### Trade plan card: TST\n- Reference price: 100.0\n- Unified stop: 95.0\n"
        ),
    }
    path = write_report_tree(state, "TST", tmp_path)
    report = path.read_text(encoding="utf-8")
    assert "## IVa. Computed Decision Context (advisory)" in report
    assert "Trade plan card: TST" in report
    assert "verdict=clean" in report


def test_iv_a_omitted_without_plan_card(tmp_path):
    """No plan card in the context -> the IVa section is not emitted."""
    state = {
        **_state(verdict="PASS"),
        "computed_decision_context": "Computed decision context: unavailable.",
    }
    path = write_report_tree(state, "TST", tmp_path)
    report = path.read_text(encoding="utf-8")
    assert "## IVa. Computed Decision Context" not in report


def _full_state():
    return {
        "market_report": "# MKT\n\n## 1. Price\n",
        "sentiment_report": "# SENT\n",
        "news_report": "# NEWS\n",
        "fundamentals_report": "# FUND\n",
        "trader_investment_plan": "Trader plan\n",
        "investment_debate_state": {
            "bull_history": "bull\n",
            "bear_history": "bear\n",
            "judge_decision": "decision\n",
        },
        "risk_debate_state": {
            "aggressive_history": "a\n",
            "conservative_history": "c\n",
            "neutral_history": "n\n",
            "judge_decision": "**Rating**: Hold\n",
        },
    }


def test_toc_present_and_links_anchors(tmp_path):
    """The consolidated report carries an auto Table of Contents with anchors."""
    report = write_report_tree(_full_state(), "TST", tmp_path).read_text(encoding="utf-8")
    toc = report.split("## Table of Contents\n", 1)[1].split("\n\n---\n\n## I.", 1)[0]
    assert "[I. Analyst Team Reports](#i-analyst-team-reports)" in toc
    assert "[Market Analyst](#market-analyst)" in toc
    assert "[Fundamentals Analyst](#fundamentals-analyst)" in toc
    assert "[Bull Researcher](#bull-researcher)" in toc
    assert "[Trader](#trader)" in toc
    assert "[Portfolio Manager](#portfolio-manager)" in toc
    # Embedded agent headings are demoted and must NOT leak into the TOC.
    assert "#mkt" not in toc
    assert "[1. Price]" not in toc


def test_slugify():
    assert _slugify("## I. Analyst Team Reports") == "i-analyst-team-reports"
    assert _slugify("### Market Analyst") == "market-analyst"
    assert _slugify("### Aggressive Analyst") == "aggressive-analyst"


def test_audit_decision_numbers_flags_mismatch():
    """Item 6: the claim-vs-computed audit flags a PM decision's Stop Loss
    that deviates >15% from the computed contract stop; matching values and
    missing refs produce no note."""
    from tradingagents.reporting import audit_decision_numbers

    md = "**Stop Loss**: 100.0\n**Price Target**: 150.0\n"
    # matching ref -> no note
    assert audit_decision_numbers(md, {"stop": 102.0, "target": 145.0}) == ""
    # far stop -> note
    note = audit_decision_numbers(md, {"stop": 80.0, "target": 145.0})
    assert "Claim audit" in note and "100.0" in note
    # no refs -> no note
    assert audit_decision_numbers(md, {}) == ""


def test_truncation_marker_appended_to_mid_sentence_sections(tmp_path):
    """A section that ends mid-sentence (LLM max_tokens cut) gets a visible
    marker in the saved file and the consolidated report, so the reader knows
    the tail is missing at the LLM layer rather than a file bug. Clean
    markdown endings (tables, **HOLD**, sentence punctuation) are untouched."""
    from tradingagents.reporting import _looks_truncated

    long_cut = (
        "The stock trades at a deep discount to its historical multiple and "
        "the balance sheet is clean, but the near-term catalyst is missing "
        "and the technicals are still rolling over, so the entry should wait "
        "for a confirmed reversal candle before any scale-in is justified "
        "and the thesis is incomplete and cut"
    )
    long_clean = (
        "The stock trades at a deep discount to its historical multiple and "
        "the balance sheet is clean, but the near-term catalyst is missing "
        "and the technicals are still rolling over, so the entry should wait "
        "for a confirmed reversal candle before any scale-in is justified "
        "and the thesis is complete."
    )
    # heuristic: bare lowercase endings are cuts; clean endings are not
    assert _looks_truncated(long_cut)
    assert not _looks_truncated(long_clean)
    assert not _looks_truncated("FINAL TRANSACTION PROPOSAL: **HOLD**")
    assert not _looks_truncated("| a | b |")
    assert not _looks_truncated("```python\nprint(1)\n```")
    assert not _looks_truncated("Trader plan")  # terse, not a real cut

    state = _full_state()
    state["market_report"] = "# MKT\n\n## 1. Price\n\n" + long_cut
    state["trader_investment_plan"] = "Trader plan"  # clean, no marker
    write_report_tree(state, "TST", tmp_path)
    mkt = (tmp_path / "1_analysts" / "market.md").read_text(encoding="utf-8")
    assert "Section truncated at the LLM output cap" in mkt
    trader = (tmp_path / "3_trading" / "trader.md").read_text(encoding="utf-8")
    assert "Section truncated" not in trader
    report = (tmp_path / "complete_report.md").read_text(encoding="utf-8")
    assert "Section truncated at the LLM output cap" in report


def test_finalize_section_roundtrip():
    from tradingagents.reporting import _finalize_section

    assert _finalize_section("Complete.") == "Complete."
    out = _finalize_section(
        "The stock trades at a deep discount to its historical multiple and "
        "the balance sheet is clean, but the near-term catalyst is missing "
        "and the technicals are still rolling over, so the entry should wait "
        "for a confirmed reversal candle before any scale-in is justified "
        "and the thesis is incomplete and cut"
    )
    assert out.endswith("capture the rest.")
    assert "Section truncated" in out


def test_risk_gate_renders_tranche_worst_case(tmp_path):
    """When the tranche fold ran, the report surfaces the peak-deployed and
    capital-at-risk measures the gate sized/throttled against."""
    state = _state(verdict="WARN", reasons=["capital-at-risk near cap"])
    state["tranche_context"] = {
        "avg_entry": 283.26,
        "peak_deployed_pct": 0.1133,
        "capital_at_risk_pct": 0.0148,
        "peak_ok": True,
        "book_ok": True,
    }
    write_report_tree(state, "TST", tmp_path)
    decision = (tmp_path / "5_portfolio" / "decision.md").read_text(encoding="utf-8")
    assert "Tranche peak-deployed: 11.3% (cap-ok=True)" in decision
    assert "Tranche capital-at-risk: 1.48%" in decision
    # no tranche_context -> neither line (backward compatible)
    clean = write_report_tree(_state(verdict="WARN"), "TST2", tmp_path)
    assert "Tranche peak-deployed" not in clean.read_text(encoding="utf-8")


def test_complete_report_ends_with_trailing_newline(tmp_path):
    """complete_report.md must end with a single trailing newline so the final
    PM decision (which has no trailing \n) doesn't look cut off."""
    state = _state(verdict="WARN", reasons=["near cap"])
    path = write_report_tree(state, "TST", tmp_path)
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    # the last content line is the PM decision's final field (non-empty)
    assert text.rstrip().splitlines()[-1].strip() != ""
    assert "Executive Summary" in text.rstrip().splitlines()[-1]


def test_risk_gate_renders_liquidity_block(tmp_path):
    """When enable_liquidity_gate computed a verdict, the report surfaces the
    ILLIQ / float-turnover / IWF block that fed the gate."""
    state = _state(verdict="REJECT", reasons=["liquidity: ILLIQUID"])
    state["risk_context"]["liquidity"] = {
        "verdict": "illiquid",
        "illiq": 1.2e-6,
        "float_turnover": 0.02,
        "iwf": 0.3,
        "dangers": ["ILLIQ=0.0000 (high price impact)"],
    }
    write_report_tree(state, "TST", tmp_path)
    decision = (tmp_path / "5_portfolio" / "decision.md").read_text(encoding="utf-8")
    assert "Liquidity verdict: **ILLIQUID**" in decision
    assert "ILLIQ: 1.20e-06" in decision
    assert "Float turnover: 2.000%" in decision
    assert "IWF: 30.00%" in decision
    assert "Liquidity reasons: ILLIQ=0.0000 (high price impact)" in decision
    # no liquidity context -> no line (backward compatible)
    clean = write_report_tree(_state(verdict="WARN"), "TST2", tmp_path)
    assert "Liquidity verdict" not in clean.read_text(encoding="utf-8")


def test_pm_prompt_injects_liquidity_line():
    """The PM prompt (printed at agent creation) names the liquidity verdict
    ground rule when the state carries a computed liquidity block."""


    # The prompt template contains the literal placeholder; assert the source
    # includes the computed-liquidity directive so the wiring can't be lost.
    from pathlib import Path

    src = Path("tradingagents/agents/managers/portfolio_manager.py").read_text(
        encoding="utf-8"
    )
    assert "Computed liquidity" in src
    assert "liq_line" in src
    assert "{liq_line}" in src


def test_collapse_repeated_tables_keeps_last_per_header():
    """Debate round streams carry the same summary table per round; the
    collapse keeps ONLY the final table per header and drops earlier ones."""
    from tradingagents.reporting import _collapse_repeated_tables

    blob = (
        "Round 1.\n\n"
        "| Signal | Data | Bull Read |\n|---|---|---|\n| Q2 EPS | a | x |\n\n"
        "Round 2 prose.\n\n"
        "| Signal | Data | Bull Read |\n|---|---|---|\n| Q2 EPS | b | y |\n\n"
        "Final round.\n\n"
        "| Signal | Data | Bull Read |\n|---|---|---|\n| Q2 EPS | c | z |\n"
    )
    out = _collapse_repeated_tables(blob)
    assert out.count("|---|---|---|") == 1
    assert "| Q2 EPS | c | z |" in out   # final table kept
    assert "| Q2 EPS | a | x |" not in out
    assert "Round 1." in out and "Round 2 prose." in out and "Final round." in out


def test_collapse_repeated_tables_keeps_distinct_headers():
    """A genuinely distinct table (different header) is never dropped."""
    from tradingagents.reporting import _collapse_repeated_tables

    blob = (
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "| Signal | Data | Bull Read |\n|---|---|---|\n| Q2 | x |\n\n"
        "| A | B |\n|---|---|\n| 3 | 4 |\n"
    )
    out = _collapse_repeated_tables(blob)
    assert sum(1 for ln in out.splitlines() if ln.strip() == "|---|---|") == 1  # A|B collapsed to last
    assert sum(1 for ln in out.splitlines() if ln.strip() == "|---|---|---|") == 1  # distinct kept
    assert "| 3 | 4 |" in out and "| 1 | 2 |" not in out
    assert "| Q2 | x |" in out


def test_collapse_repeated_tables_idempotent_and_prose_safe():
    from tradingagents.reporting import _collapse_repeated_tables

    blob = "Just prose, no tables.\n\n| not a table header line"
    assert _collapse_repeated_tables(blob) == blob
    one = "| K | V |\n|---|---|\n| a | 1 |\n"
    assert _collapse_repeated_tables(one) == one
    # already-collapsed stays collapsed
    twice = _collapse_repeated_tables(
        "| K | V |\n|---|---|\n| a | 1 |\n\n| K | V |\n|---|---|\n| b | 2 |\n"
    )
    assert _collapse_repeated_tables(twice) == twice


# ---------------------------------------------------------------------------
# Empty-report guard: an analyst that produced no report must leave an
# on-disk "report unavailable" artifact, never silently vanish (the NVDA
# empty-market_report defect looked like a missing market.md with no error).
# ---------------------------------------------------------------------------


def _guard_state(market="", news="news prose", fundamentals="fund prose", sentiment="sent prose"):
    return {
        "risk_debate_state": {
            "judge_decision": "**Rating**: Hold\n**Executive Summary**: x\n",
        },
        "trader_investment_plan": "Trader plan",
        "market_report": market,
        "news_report": news,
        "fundamentals_report": fundamentals,
        "sentiment_report": sentiment,
    }


def test_empty_market_report_writes_unavailable_block(tmp_path):
    write_report_tree(_guard_state(market=""), "TST", tmp_path)
    market_md = (tmp_path / "1_analysts" / "market.md").read_text(encoding="utf-8")
    assert "report unavailable" in market_md
    assert "No report was produced" in market_md


def test_empty_fundamentals_report_writes_unavailable_block(tmp_path):
    write_report_tree(_guard_state(fundamentals=""), "TST", tmp_path)
    fund_md = (tmp_path / "1_analysts" / "fundamentals.md").read_text(encoding="utf-8")
    assert "report unavailable" in fund_md
    assert "No report was produced" in fund_md
    # Non-empty reports never get the placeholder.
    news_md = (tmp_path / "1_analysts" / "news.md").read_text(encoding="utf-8")
    assert "report unavailable" not in news_md
    assert "news prose" in news_md


def test_research_manager_no_plan_writes_unavailable_block(tmp_path):
    """When the research debate ran but the Manager produced no plan, the
    report emits an explicit 'plan unavailable' block (never a 0-byte
    manager.md) so the section always renders (SKHY 08-31)."""
    from tradingagents.reporting import write_report_tree as _wrt

    state = {
        "investment_debate_state": {
            "history": "\nBull Analyst: bull argues.\nBear Analyst: bear argues.\n",
            "bull_history": "Bull Analyst: bull argues.\n",
            "bear_history": "Bear Analyst: bear argues.\n",
            "judge_decision": "",
            "current_response": "",
            "count": 1,
        }
    }
    path = _wrt(state, "TST", tmp_path)
    mgr = (tmp_path / "2_research" / "manager.md").read_text(encoding="utf-8")
    assert "plan unavailable" in mgr
    assert "bull/bear arguments and the analyst reports" in mgr
    report = path.read_text(encoding="utf-8")
    assert "## II. Research Team Decision" in report
    assert "Research Manager: plan unavailable" in report


def test_all_reports_present_no_unavailable_blocks(tmp_path):
    write_report_tree(
        _guard_state(
            market="market prose",
            news="news prose",
            fundamentals="fund prose",
            sentiment="sent prose",
        ),
        "TST",
        tmp_path,
    )
    for f in ("market", "news", "fundamentals", "sentiment"):
        text = (tmp_path / "1_analysts" / f"{f}.md").read_text(encoding="utf-8")
        assert "report unavailable" not in text
def test_disclosure_block_does_not_false_mark_truncation(tmp_path):
    """Phase D regression: the computed disclosure footer ends in lowercase
    ("models: n/a") - it must NOT trigger the LLM-cap truncation marker when
    the decision text itself is complete (see MSFT 20260902 decision.md)."""
    judge = (
        "**Rating**: Underweight\n**Executive Summary**: The bear case won on "
        "empirical grounding and catalyst clarity, while the franchise remains "
        "durable and the verified close conflicts with the adverse tape, which "
        "further argues against a full Sell."
    )
    state = {
        "risk_debate_state": {"judge_decision": judge},
        "risk_gate": {"verdict": "PASS", "reasons": []},
        "risk_snapshot": "verdict=PASS",
    }
    assert write_report_tree(state, "TST", tmp_path, config={"enable_report_attribution": True}).exists()
    decision = (tmp_path / "5_portfolio" / "decision.md").read_text(encoding="utf-8")
    assert "### Decision disclosure (computed, advisory)" in decision
    assert "Section truncated at the LLM output cap" not in decision
    assert decision.rstrip().endswith("models: n/a")


def test_genuine_truncation_marked_before_disclosure(tmp_path):
    """A real mid-sentence LLM cut is still marked, and the marker sits after
    the cut text but before the computed disclosure block."""
    judge = (
        "**Rating**: Underweight\n**Executive Summary**: The bear case won the "
        "debate and the momentum has clearly broken, so the position should "
        "be reduced toward the lower bound of the normal weight range wh"
    )  # ends mid-word (lowercase), >120 chars
    state = {
        "risk_debate_state": {"judge_decision": judge},
        "risk_gate": {"verdict": "PASS", "reasons": []},
        "risk_snapshot": "verdict=PASS",
    }
    assert write_report_tree(state, "TST", tmp_path, config={"enable_report_attribution": True}).exists()
    decision = (tmp_path / "5_portfolio" / "decision.md").read_text(encoding="utf-8")
    assert "Section truncated at the LLM output cap" in decision
    assert decision.index("Section truncated") < decision.index("### Decision disclosure")
