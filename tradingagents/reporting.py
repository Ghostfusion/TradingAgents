"""Reusable report-tree writer shared by the CLI and the programmatic API.

Writes a run's per-section markdown (analysts, research, trading, risk,
portfolio) plus a consolidated ``complete_report.md`` under ``save_path``. The
CLI and ``TradingAgentsGraph.save_reports`` both call this, so a headless / API
run produces the same on-disk report tree a CLI run does.

R1b (risk governance display): the computed risk gate (verdict + snapshot +
reasons) is injected ahead of the LLM risk debate minutes, the final decision
mirrors the gate, and ``risk_compact_report`` replaces the verbose 3-analyst
transcripts with a single verdict file (config-gated, off by default).
"""

import re
from datetime import datetime
from pathlib import Path


def _config(config):
    if config is not None:
        return config
    try:
        from tradingagents.dataflows.config import get_config

        return get_config()
    except Exception:
        return {}


def _shift_down(text: str, levels: int = 3) -> str:
    """Push every ATX heading inside ``text`` down by ``levels`` (cap at 6 '#').

    Embedded agent reports arrive with their own H1/H2/H3 outline; when they are
    joined into the consolidated report those headings must sit *under* the outer
    H2 team / H3 role markers. Default 3 levels gives strict nesting: an agent's
    H1 title becomes H4 (below the H3 role label), its H2 sections become H5 and
    its H3 subsections H6 — the role -> document -> section chain is unambiguous.
    (A 2-level shift would put the agent's H1 title at the same H3 as the role
    label, which is what made the older reports confusing.)
    """
    if levels <= 0:
        return text
    out = []
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            hashes, rest = m.group(1), m.group(2)
            new_n = min(6, len(hashes) + levels)
            out.append("#" * new_n + " " + rest)
        else:
            out.append(line)
    return "\n".join(out)


def _slugify(heading: str) -> str:
    """GitHub-style markdown anchor for a heading (lowercase, spaces->hyphens).

    ``## I. Analyst Team Reports`` -> ``#i-analyst-team-reports``
    ``### Market Analyst``        -> ``#market-analyst``
    """
    text = re.sub(r"[^\w\s-]", "", heading.lower()).strip()
    return text.replace(" ", "-")


def _build_toc(sections: list[str]) -> str:
    """Auto-generate the Table of Contents block from the rendered sections.

    Extracts each ``## <Team>`` header and the ``### <Role>`` markers under it
    (embedded agent content is demoted to ``####``+ and never matches), and
    renders nested markdown links.
    """
    lines = ["## Table of Contents", ""]
    for section in sections:
        team = None
        roles = []
        for ln in section.splitlines():
            if ln.startswith("## "):
                team = ln[3:].strip()
            elif ln.startswith("### ") and team:
                roles.append(ln[4:].strip())
        if team:
            lines.append(f"- [{team}](#{_slugify(team)})")
            for role in roles:
                lines.append(f"  - [{role}](#{_slugify(role)})")
    return "\n".join(lines) + "\n"


_TRUNCATION_MARKER = (
    "\n\n> ⚠️ **Section truncated at the LLM output cap** — the report ends "
    "mid-sentence, so the tail is missing. This is an LLM-layer cut "
    "(max_tokens), not a file error. Raise `max_output_tokens` / "
    "`max_output_tokens_deep` in default_config.py or split the section to "
    "capture the rest."
)


def _looks_truncated(text: str) -> bool:
    """Heuristic: does an LLM report end mid-sentence (max_tokens cut)?

    Conservative on purpose: only flags endings that are neither sentence
    punctuation nor a clean markdown construct (table row, bold/italic, code
    fence, heading, closing bracket/quote, or a bold-label line like
    ``**Consensus**: High``). A report ending in a bare lowercase word is
    almost always a cut — the model was stopped before it could finish the
    sentence. The minimum length keeps terse strings (test fixtures, one-line
    verdicts) from being mis-flagged: a real report that hit the cap is long.
    """
    t = (text or "").rstrip()
    if not t or len(t) < 120:
        return False
    last = t[-1]
    if last in ".!?;:":
        return False
    if last in "|*`#)]}>\"'":
        return False
    # A bold-label ending (``**Label**: value``) is a structured, complete
    # line — the PM/risk verdicts end this way and are not cuts.
    last_line = t.rsplit("\n", 1)[-1]
    if "**:" in last_line:
        return False
    # Real cuts end mid-word in lowercase (or a digit); an uppercase bare
    # ending is usually a deliberate verdict word, not a cut.
    return last.islower() or last.isdigit()


def _finalize_section(text: str) -> str:
    """Append a visible truncation marker when the LLM report was cut.

    The marker is a blockquote (not a heading), so it survives the
    ``_shift_down`` demotion in the consolidated report unchanged and tells
    the reader the mid-sentence ending is an LLM-layer cap, not a file bug.
    """
    if not text or not _looks_truncated(text):
        return text
    return text.rstrip() + _TRUNCATION_MARKER


def _collapse_repeated_tables(text: str) -> str:
    """Drop repeated markdown tables whose header repeats within a section.

    Debate agents (bull/bear researchers, risk debators) run in rounds and
    each round's message historically carried a summary table with the same
    header (e.g. ``| Signal | Data | Bull Read |``) but slightly re-derived
    rows - so a deep run rendered 4-6 near-identical tables per agent. This
    deterministic pass keeps ONLY the LAST table per distinct header (the
    final round's table is the sharpest) and removes the earlier duplicates,
    leaving all non-table text untouched. ``text`` may be any markdown blob
    (kept idempotent: no stateful assumptions).
    """
    if not text or "|" not in text:
        return text
    lines = text.split("\n")

    def _is_sep(line: str) -> bool:
        s = line.strip()
        return s.startswith("|") and "-" in s and set(s.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")).issubset("")

    def _is_header(line: str) -> bool:
        s = line.strip()
        return s.startswith("|") and s.endswith("|")

    # Locate tables: header line followed by a separator line.
    tables = []  # (index_of_header, header_key, body_lines, end_index)
    i = 0
    n = len(lines)
    while i < n:
        if _is_header(lines[i]) and i + 1 < n and _is_sep(lines[i + 1]):
            key = lines[i].strip().lower()
            start = i
            j = i + 2
            while j < n and lines[j].startswith("|"):
                j += 1
            tables.append((start, key, lines[i:j], j - 1))
            i = j
        else:
            i += 1
    if not tables:
        return text

    last_index = {}
    for idx, key, _body, _end in tables:
        last_index[key] = idx

    dropped = {key for key, idx in last_index.items() if sum(1 for _t in tables if _t[1] == key) > 1}
    if not dropped:
        return text

    keep = {idx for idx, key, _body, _end in tables if idx == last_index[key]}
    out: list[str] = []
    tidx = {t[0]: t for t in tables}
    i = 0
    while i < n:
        if i in tidx:
            start, _key, body, end = tidx[i]
            if start in keep:
                out.extend(body)
            i = end + 1
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def audit_decision_numbers(decision_text: str, refs: dict) -> str:
    """Claim-vs-computed audit of a PM decision (item 6).

    Deterministically extracts the decision's self-reported ``Stop Loss`` and
    ``Price Target`` and cross-checks them against the computed reference
    levels (the risk gate's contract stop / the price target from state).
    Only flags a discrepancy when BOTH the decision value and the computed
    reference are present AND the decision value deviates > 15% (avoids noise
    from prose numbers). Returns a short markdown audit note, or '' when there
    is nothing to flag. Never modifies the decision - it is advisory.
    """
    import re

    def _num(text, label):
        m = re.findall(rf"\*\*{label}\*\*[^0-9]*([0-9]+(?:\.[0-9]+)?)", decision_text)
        return float(m[0]) if m else None

    stop_dec = _num(decision_text, "Stop Loss")
    target_dec = _num(decision_text, "Price Target")
    stop_ref = refs.get("stop")
    target_ref = refs.get("target")
    notes = []
    if stop_dec is not None and stop_ref is not None and stop_ref > 0 and abs(stop_dec - stop_ref) / stop_ref > 0.15:
        notes.append(f"decision Stop Loss {stop_dec} deviates >15% from computed stop {stop_ref:.2f}")
    if (
        target_dec is not None
        and target_ref is not None
        and target_ref > 0
        and abs(target_dec - target_ref) / target_ref > 0.15
    ):
        notes.append(f"decision Price Target {target_dec} deviates >15% from computed target {target_ref:.2f}")
    if not notes:
        return ""
    return (
        "\n\n> **Claim audit**: " + "; ".join(notes) +
        " — verify against the computed values before acting."
    )

def _indent_needed(line: str) -> bool:
    """True when a non-blank prose line should be separated from its neighbour.

    Conservative: a line that is a markdown block (table row, fence, list,
    heading, or already-blank) is left untouched; only plain run-on prose
    lines are re-spaced so a single-`\n` concatenated debate reads as
    paragraphs instead of one wall of text.
    """
    st = line.strip()
    if not st:
        return False
    if st.startswith(("|", "#", "-", "*", ">", "```", "---", "**")):
        return False
    return not st.endswith(("|", "```"))


def _readable_section(text: str, role: str = "") -> str:
    """Make a dense LLM report as readable as the analyst reports.

    Debate/research/trader reports are generated as conversational prose and
    concatenated with single newlines, so they render as one unbroken wall of
    text (the analyst reports look good because their prompt emits structured
    markdown). This deterministic, content-preserving pass:

      1. Ensures blank-line paragraph spacing around plain prose (never touches
         tables, lists, code fences, headings, or existing blank lines).
      2. Promotes repeated round markers (``Role: ...``) into ``### Round N``
         headings so a multi-round debate is visually separated.

    All content is preserved verbatim; only whitespace/heading structure is
    added, mirroring the no-fabrication contract.
    """
    if not text:
        return text
    lines = text.split("\n")
    pat = (role + ":") if role else None
    occurrences = sum(1 for ln in lines if pat and ln.strip().startswith(pat))
    # Promote round markers only when the role repeats (a real debate), and
    # NEVER when the file is already formatted (idempotent: a re-render of an
    # on-disk report must not double the headings or stack blank lines).
    promote = occurrences >= 2
    rn = 0
    out: list[str] = []
    for i, ln in enumerate(lines):
        if promote and ln.strip().startswith(pat):
            rn += 1
            # Idempotency: if the *source* already has this "### Round N"
            # heading directly above the role line (a re-render of an
            # on-disk, already-formatted report), do NOT add it again.
            # Look back past blank lines to the previous non-blank source line
            # (an already-formatted report has "### Round N" then a blank then
            # the role line).
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            src_prev = lines[j].strip() if j >= 0 else ""
            if src_prev == f"### Round {rn}":
                out.append(ln)
                continue
            out.append(f"### Round {rn}")
            # ensure a blank line follows the heading (collapse doubles)
            out.append("")
            out.append(ln)
            continue
        out.append(ln)
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        # paragraph spacing between two plain prose lines; never stack blank
        # lines (collapse "\n\n" runs) and never insert before a heading/
        # list/table/code fence.
        if (
            _indent_needed(ln)
            and nxt
            and _indent_needed(nxt)
            and ln.strip()
            and nxt.strip()
            and out
            and out[-1].strip() != ""
        ):
            out.append("")
    # Collapse any accidental 3+ consecutive blank lines to one.
    cleaned: list[str] = []
    blanks = 0
    for ln in out:
        if not ln.strip():
            blanks += 1
            if blanks > 1:
                continue
        else:
            blanks = 0
        cleaned.append(ln)
    return "\n".join(cleaned)




def _risk_gate_block(final_state: dict) -> str:
    """Markdown block of the computed risk gate; '' when no gate ran."""
    gate = final_state.get("risk_gate") or {}
    if not gate:
        return ""
    parts = ["### Risk Gate (computed)", ""]
    verdict = gate.get("verdict", "?")
    parts.append(f"Verdict: **{verdict}**")
    snap = final_state.get("risk_snapshot")
    if snap:
        parts.append(f"Snapshot: {snap}")
    # Expose both the analyzed name's own daily-tail CVaR and (when a risk
    # basket is configured) the book-level CVaR that actually fed the gate - so
    # a reader can tell "this idea's tail" from "my book's tail".
    ctx = final_state.get("risk_context") or {}
    if ctx.get("single_cvar") is not None:
        parts.append(f"Analyzed-name CVaR: {ctx['single_cvar']:.2%}")
    if ctx.get("book_cvar") is not None:
        parts.append(f"Portfolio (book) CVaR: {ctx['book_cvar']:.2%} — this fed the gate")
    # Item 2: book-level correlated stress - the whole basket shocked together
    # (real firms stress the book, not just single names).
    if ctx.get("book_stress") is not None:
        parts.append(f"Book correlated stress: {ctx['book_stress']:.2%} (-10% correlated shock)")
    # Tranche fold: worst-case scale-in measures (config-frozen tranche plan)
    # that the gate sized/throttled against (Value_Dip_swing_Continue.md).
    tc = final_state.get("tranche_context") or {}
    if tc.get("peak_deployed_pct") is not None:
        parts.append(
            f"Tranche peak-deployed: {tc['peak_deployed_pct']:.1%} (cap-ok={tc.get('peak_ok')})"
        )
    if tc.get("capital_at_risk_pct") is not None:
        parts.append(f"Tranche capital-at-risk: {tc['capital_at_risk_pct']:.2%}")
    # risk2.md liquidity/ownership block (when enable_liquidity_gate computed
    # it): the ILLIQ / float-turnover / IWF verdict that fed the gate.
    liq = (ctx or {}).get("liquidity") or {}
    if liq.get("verdict"):
        parts.append(f"Liquidity verdict: **{liq['verdict'].upper()}**")
        if liq.get("illiq") is not None:
            parts.append(f"ILLIQ: {liq['illiq']:.2e}")
        if liq.get("float_turnover") is not None:
            parts.append(f"Float turnover: {liq['float_turnover']:.3%}")
        if liq.get("iwf") is not None:
            parts.append(f"IWF: {liq['iwf']:.2%}")
        if liq.get("dangers"):
            parts.append("Liquidity reasons: " + "; ".join(liq["dangers"]))
    reasons = gate.get("reasons") or []
    if reasons:
        parts.append("Reasons: " + "; ".join(reasons))
    contract = final_state.get("position_contract")
    if contract:
        parts.append(f"Position contract: {contract}")
    if final_state.get("risk_halt"):
        parts.append("**RISK HALT ACTIVE - escalation required**")
    return "\n".join(parts) + "\n"


def write_report_tree(
    final_state: dict, ticker: str, save_path, config: "dict | None" = None
) -> Path:
    """Save a completed run's reports to ``save_path``; return the complete-report path."""
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)
    cfg = _config(config)
    compact = bool(cfg.get("risk_compact_report", False))
    sections = []
    gate_block = _risk_gate_block(final_state)

    def prepend_block(text: str) -> str:
        return (gate_block + "\n\n" + text) if gate_block else text

    # 1. Analysts
    analysts_dir = save_path / "1_analysts"
    analyst_parts = []
    for key, name in (
        ("market_report", "Market Analyst"),
        ("sentiment_report", "Sentiment Analyst"),
        ("news_report", "News Analyst"),
        ("fundamentals_report", "Fundamentals Analyst"),
    ):
        text = final_state.get(key)
        if text:
            analysts_dir.mkdir(exist_ok=True)
            safe = key.replace("_report", "")
            # The analyst files are input evidence, not risk outputs: the
            # computed risk gate is NOT prepended here (it belongs in
            # 4_risk/ and 5_portfolio/decision.md, where it appears once).
            (analysts_dir / f"{safe}.md").write_text(
                _finalize_section(text), encoding="utf-8"
            )
            analyst_parts.append((name, _finalize_section(text)))
        else:
            # Empty-report guard: an analyst that produced no report (tool
            # loop wedged on a slow/hung vendor call) must still leave an
            # on-disk artifact with an explicit "unavailable" block, never
            # silently vanish - silent absence read as an analysis bug.
            analysts_dir.mkdir(exist_ok=True)
            safe = key.replace("_report", "")
            (analysts_dir / f"{safe}.md").write_text(
                f"## {name}: report unavailable\n\n"
                "No report was produced for this section in this run - the "
                "analyst may not have been selected, or its tool loop stalled "
                "on a slow or unreachable data source. No numbers are "
                "inferred or fabricated. Re-run to regenerate this section.\n",
                encoding="utf-8",
            )
            analyst_parts.append(
                (name, f"## {name}: report unavailable\n\nNo report produced.")
            )
    if analyst_parts:
        content = "\n\n---\n\n".join(
            f"### {name}\n\n{_shift_down(text)}" for name, text in analyst_parts
        )
        sections.append(f"## I. Analyst Team Reports\n\n{content}")

    # 2. Research
    if final_state.get("investment_debate_state"):
        research_dir = save_path / "2_research"
        debate = final_state["investment_debate_state"]
        research_parts = []
        for key, fname, name in (
            ("bull_history", "bull.md", "Bull Researcher"),
            ("bear_history", "bear.md", "Bear Researcher"),
        ):
            text = debate.get(key)
            if text:
                research_dir.mkdir(exist_ok=True)
                cleaned = _collapse_repeated_tables(text)
                (research_dir / fname).write_text(
                    _finalize_section(_readable_section(cleaned, role=name.split()[0])),
                    encoding="utf-8",
                )
                research_parts.append((name, _finalize_section(_readable_section(cleaned, role=name.split()[0]))))
        if debate.get("judge_decision"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "manager.md").write_text(
                _finalize_section(_readable_section(debate["judge_decision"], role="Research Manager")),
                encoding="utf-8",
            )
        elif debate.get("history"):
            # The research debate ran but the Manager produced no plan
            # (degenerate structured/free-text output). Emit an explicit
            # "unavailable" block instead of a 0-byte manager.md, so the
            # report always renders the section and no one reads absence as
            # a bug in the pipeline itself (SKHY 08-31: manager.md was empty
            # after a garbage-heavy bear history).
            research_dir.mkdir(exist_ok=True)
            _unavailable_mgr = (
                "## Research Manager: plan unavailable\n\n"
                "The research debate produced no usable manager plan this run "
                "(the manager's structured/free-text output was empty or "
                "degenerate). The bull/bear arguments and the analyst reports "
                "above stand; the Trader / risk team and Portfolio Manager "
                "continue on that evidence."
            )
            (research_dir / "manager.md").write_text(_unavailable_mgr, encoding="utf-8")
            research_parts.append(("Research Manager", _unavailable_mgr))
        # Structured-debate evidence block (opt-in enable_debate): judge
        # scores per anonymized candidate + the grounded claim ledger + the
        # L1 severity verdict. Absent when the structured path did not run.
        # scores per anonymized candidate + the grounded claim ledger + the
        sd = final_state.get("debate_state") or {}
        if sd.get("judge_scores") or sd.get("claim_ledger_md") or sd.get("l1"):
            research_dir.mkdir(exist_ok=True)
            sd_lines = ["## Structured debate evidence (deterministic)"]
            l1 = sd.get("l1")
            if l1:
                sd_lines.append(
                    f"- L1 verdict: {l1.get('severity_tier', '?')} / "
                    f"{l1.get('l1_action', '?')} (side={l1.get('side', '?')}, "
                    f"penalty={l1.get('penalty_score', 0)})"
                )
            judge = sd.get("judge_scores") or {}
            for alias, agg in judge.items():
                sd_lines.append(
                    f"- {alias}: mean {agg.get('mean', '-')} "
                    f"(scores: {agg.get('scores', {})})"
                )
            if sd.get("claim_ledger_md"):
                sd_lines.append(sd["claim_ledger_md"])
            evidence = _finalize_section(
                _readable_section("\n".join(sd_lines), role="Research Manager")
            )
            (research_dir / "structured_debate.md").write_text(evidence, encoding="utf-8")
            research_parts.append(("Structured debate evidence", evidence))
        if research_parts:
            content = "\n\n---\n\n".join(
                f"### {name}\n\n{_shift_down(text)}" for name, text in research_parts
            )
            sections.append(f"## II. Research Team Decision\n\n{content}")

    # 3. Trading
    if final_state.get("trader_investment_plan"):
        trading_dir = save_path / "3_trading"
        trading_dir.mkdir(exist_ok=True)
        trader_body = _readable_section(final_state["trader_investment_plan"], role="Trader")
        (trading_dir / "trader.md").write_text(
            _finalize_section(trader_body), encoding="utf-8"
        )
        sections.append(
            f"## III. Trading Team Plan\n\n### Trader\n\n{_shift_down(_finalize_section(trader_body))}"
        )

    # 4. Risk Management (debate transcripts + computed gate)
    if final_state.get("risk_debate_state"):
        risk_dir = save_path / "4_risk"
        risk = final_state["risk_debate_state"]
        risk_parts = []
        if compact and gate_block:
            risk_dir.mkdir(exist_ok=True)
            # Compact verdict = the computed risk gate ONLY (verdict, limits,
            # CVaRs, stress, liquidity, tranche, positions). The PM decision
            # prose is NOT duplicated here: it already lives once in
            # 5_portfolio/decision.md, so verdict.md carries the risk-specific
            # read without a byte-copy of the final call.
            verdict_md = gate_block + "\n"
            if risk.get("judge_decision"):
                verdict_md += (
                    "\n> The full Portfolio Manager decision (rating / thesis / "
                    "targets) is in 5_portfolio/decision.md.\n"
                )
            (risk_dir / "verdict.md").write_text(verdict_md, encoding="utf-8")
            risk_parts.append(("Risk Verdict (computed)", gate_block.strip()))
        else:
            for key, fname, name in (
                ("aggressive_history", "aggressive.md", "Aggressive Analyst"),
                ("conservative_history", "conservative.md", "Conservative Analyst"),
                ("neutral_history", "neutral.md", "Neutral Analyst"),
            ):
                text = risk.get(key)
                if text:
                    risk_dir.mkdir(exist_ok=True)
                    cleaned = _collapse_repeated_tables(text)
                    readable = _readable_section(cleaned, role=name.split()[0] + " Analyst")
                    (risk_dir / fname).write_text(
                        prepend_block(_finalize_section(readable)), encoding="utf-8"
                    )
                    risk_parts.append((name, _finalize_section(readable)))
        if risk_parts:
            content = "\n\n---\n\n".join(
                f"### {name}\n\n{_shift_down(text)}" for name, text in risk_parts
            )
            sections.append(f"## IV. Risk Management Team Decision\n\n{content}")
            # Phase A-E: surface the compiled deterministic context (regime
            # gate / plan card / risk snapshot) that the 5 decision agents were
            # given, so the report reader sees the hard numbers under the debate.
            cc = final_state.get("computed_decision_context") or ""
            if cc and "Trade plan card" in cc:
                sections.append(f"## IVa. Computed Decision Context (advisory)\n\n{cc}\n")

        # 5. Portfolio Manager (mirrors the risk gate)
        if risk.get("judge_decision"):
            portfolio_dir = save_path / "5_portfolio"
            portfolio_dir.mkdir(exist_ok=True)
            pm_decision = risk["judge_decision"]
            if cfg.get("enable_decision_audit"):
                try:
                    import re as _re

                    ref_stop = None
                    contract = final_state.get("position_contract")
                    if isinstance(contract, str):
                        m = _re.search(r"\bstop\s+([0-9.]+)", contract, _re.IGNORECASE)
                        if m:
                            ref_stop = float(m.group(1))
                    audit_note = audit_decision_numbers(pm_decision, {"stop": ref_stop})
                    if audit_note:
                        pm_decision = pm_decision.rstrip() + audit_note
                except Exception:  # noqa: BLE001 - audit is advisory, never blocks
                    pass
            wrapped = prepend_block(_finalize_section(pm_decision))
            (portfolio_dir / "decision.md").write_text(wrapped, encoding="utf-8")
            sections.append(
                f"## V. Portfolio Manager Decision\n\n### Portfolio Manager\n\n{_shift_down(prepend_block(_finalize_section(pm_decision)))}"
            )

    # Write consolidated report (auto Table of Contents above the teams)
    header = f"# Trading Analysis Report: {ticker}\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    body = "\n\n---\n\n".join(sections)
    toc = _build_toc(sections)
    # Fixed trailing newline: the last section (PM decision) ends without a \n,
    # making the report look truncated at the final byte even though it is
    # complete. rstrip + a single trailing newline removes that illusion.
    (save_path / "complete_report.md").write_text(
        (header + toc + "\n\n---\n\n" + body).rstrip() + "\n", encoding="utf-8"
    )
    return save_path / "complete_report.md"
