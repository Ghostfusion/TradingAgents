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
            (analysts_dir / f"{safe}.md").write_text(
                prepend_block(_finalize_section(text)), encoding="utf-8"
            )
            analyst_parts.append((name, _finalize_section(text)))
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
                (research_dir / fname).write_text(_finalize_section(text), encoding="utf-8")
                research_parts.append((name, _finalize_section(text)))
        if debate.get("judge_decision"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "manager.md").write_text(
                _finalize_section(debate["judge_decision"]), encoding="utf-8"
            )
            research_parts.append(("Research Manager", _finalize_section(debate["judge_decision"])))
        if research_parts:
            content = "\n\n---\n\n".join(
                f"### {name}\n\n{_shift_down(text)}" for name, text in research_parts
            )
            sections.append(f"## II. Research Team Decision\n\n{content}")

    # 3. Trading
    if final_state.get("trader_investment_plan"):
        trading_dir = save_path / "3_trading"
        trading_dir.mkdir(exist_ok=True)
        (trading_dir / "trader.md").write_text(
            _finalize_section(final_state["trader_investment_plan"]), encoding="utf-8"
        )
        sections.append(
            f"## III. Trading Team Plan\n\n### Trader\n\n{_shift_down(_finalize_section(final_state['trader_investment_plan']))}"
        )

    # 4. Risk Management (debate transcripts + computed gate)
    if final_state.get("risk_debate_state"):
        risk_dir = save_path / "4_risk"
        risk = final_state["risk_debate_state"]
        risk_parts = []
        if compact and gate_block:
            risk_dir.mkdir(exist_ok=True)
            verdict_md = gate_block + "\n"
            if risk.get("judge_decision"):
                verdict_md += "\n**Risk Judge Decision**\n\n" + _finalize_section(risk["judge_decision"]) + "\n"
            (risk_dir / "verdict.md").write_text(verdict_md, encoding="utf-8")
            risk_parts.append(("Risk Verdict (computed)", gate_block.strip()))
            if risk.get("judge_decision"):
                risk_parts.append(("Risk Analyst Verdict", _finalize_section(risk["judge_decision"])))
        else:
            for key, fname, name in (
                ("aggressive_history", "aggressive.md", "Aggressive Analyst"),
                ("conservative_history", "conservative.md", "Conservative Analyst"),
                ("neutral_history", "neutral.md", "Neutral Analyst"),
            ):
                text = risk.get(key)
                if text:
                    risk_dir.mkdir(exist_ok=True)
                    (risk_dir / fname).write_text(
                        prepend_block(_finalize_section(text)), encoding="utf-8"
                    )
                    risk_parts.append((name, _finalize_section(text)))
        if risk_parts:
            content = "\n\n---\n\n".join(
                f"### {name}\n\n{_shift_down(text)}" for name, text in risk_parts
            )
            sections.append(f"## IV. Risk Management Team Decision\n\n{content}")

        # 5. Portfolio Manager (mirrors the risk gate)
        if risk.get("judge_decision"):
            portfolio_dir = save_path / "5_portfolio"
            portfolio_dir.mkdir(exist_ok=True)
            wrapped = prepend_block(_finalize_section(risk["judge_decision"]))
            (portfolio_dir / "decision.md").write_text(wrapped, encoding="utf-8")
            sections.append(
                f"## V. Portfolio Manager Decision\n\n### Portfolio Manager\n\n{_shift_down(prepend_block(_finalize_section(risk['judge_decision'])))}"
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
