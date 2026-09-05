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
from contextlib import suppress
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
    # A short bold-verdict ending (``**Action**: Buy``, ``**Consensus**: High``)
    # is a structured, complete line — PM/risk verdicts end this way and are
    # not cuts. A LONG prose line that merely STARTS with a bold label (e.g.
    # ``**Executive Summary**: The bear case ... ``) is NOT exempt: a max_tokens
    # cut there still ends mid-word in lowercase.
    last_line = t.rsplit("\n", 1)[-1].strip()
    if last_line.startswith("**") and "**:" in last_line and len(last_line) <= 60:
        return False
    # Real cuts end mid-word in lowercase. A digit ending is a COMPLETE
    # measured value / indicator line (e.g. "DI- 25.1", "RS line 0.526",
    # "$287", a table cell) - not a cut. Treating a trailing digit as a cut
    # caused false "Section truncated" markers on otherwise complete analyst
    # reports (AVGO market.md ended "ADX 11.0 (no trend force), DI- 25.1" and
    # was wrongly flagged despite being only ~1.3k tokens at an 8k cap).
    return last.islower()


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


def write_research_decision(final_state: dict, ticker: str, save_path) -> None:
    """Emit the deterministic execution contract next to run_card.json.

    Subset of the plan schema (schema_version 1) consumed by the TradingExecution
    layer: ticker, effective_date, rating, deterministic position levels from the
    G1 position contract, data_quality/guardrail notes from the PM decision, and
    the risk_gate verdict. Every unproducible field is ``null`` — the daemon
    fails closed on anything it cannot validate. The artifact is hash-pinned
    (``decision_hash``) so the executor can verify and dedupe it. Advisory;
    never gates; never breaks a report write.
    """
    import hashlib as _hl
    import json as _rj
    from datetime import date as _date

    pm = final_state.get("pm_decision") or {}
    rg = final_state.get("risk_gate") or {}
    contract = final_state.get("position_contract")
    stop = target = size_pct = None
    if isinstance(contract, dict):
        stop = contract.get("stop_loss") or contract.get("stop")
        target = contract.get("target")
        size_pct = contract.get("size_pct")
    elif isinstance(contract, str):
        m = re.search(r"\bstop\s+([0-9.]+)", contract, re.IGNORECASE)
        if m:
            stop = float(m.group(1))
        m2 = re.search(r"\btarget\s+([0-9.]+)", contract, re.IGNORECASE)
        if m2:
            target = float(m2.group(1))
        m3 = re.search(r"\bsize[^0-9]*([0-9.]+)%?", contract, re.IGNORECASE)
        if m3:
            size_pct = float(m3.group(1)) / 100.0

    pm_rating = pm.get("rating") if isinstance(pm, dict) else None
    pm_dq = pm.get("data_quality") if isinstance(pm, dict) else None
    pm_gr = pm.get("guardrail_reason") if isinstance(pm, dict) else None
    rg_verdict = rg.get("verdict") if isinstance(rg, dict) else None
    rg_reasons = rg.get("reasons") or [] if isinstance(rg, dict) else []

    doc = {
        "schema_version": 1,
        "ticker": str(ticker).upper(),
        "effective_date": _date.today().isoformat(),
        "rating": pm_rating,
        "direction": None,  # derived by the executor from rating
        "thesis": pm.get("investment_thesis") if isinstance(pm, dict) else None,
        "rationale": pm.get("executive_summary") if isinstance(pm, dict) else None,
        "recommended_allocation_pct": None,  # PM position_size is prose; never parsed
        "position": {
            "target_notional": None,
            "stop_loss": stop,
            "take_profit": target,
            "size_pct_book": size_pct,
        },
        "data_quality": pm_dq or "unknown",
        "price_caliber": None,
        "invalidations": [],
        "guardrail_reason": pm_gr,
        "risk_gate": {"verdict": rg_verdict, "reasons": rg_reasons},
        "disclosure": {"sources_used": [], "sources_empty": []},
    }
    body = _rj.dumps(doc, sort_keys=True, default=str)
    doc["decision_hash"] = "sha256:" + _hl.sha256(body.encode("utf-8")).hexdigest()
    (Path(save_path) / "research_decision.json").write_text(
        _rj.dumps(doc, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )


def write_alpha_ledger(final_state: dict, ticker: str, save_path, config: "dict | None" = None) -> "Path | None":
    """Append one alpha-ledger row next to research_decision.json (default off).

    The market-research material's diagnostic ledger: each emitted decision is
    stamped (ticker, effective_date, rating, data_quality, guardrail note) so
    a later collector can join realized forward returns and answer "did the
    scorer stop finding opportunities, or did the market get efficient?".
    Gated by ``alpha_ledger_enable`` (default False). Pure append, one JSON
    line per row, hash-pinned like research_decision.json. Advisory: a
    failure here must never break the report tree.
    """
    import hashlib as _hl
    import json as _rj
    from datetime import date as _date, datetime as _dt, timezone as _tz

    cfg = _config(config)
    if not bool(cfg.get("alpha_ledger_enable")):
        return None
    pm = final_state.get("pm_decision") or {}
    rg = final_state.get("risk_gate") or {}
    body = {
        "schema_version": 1,
        "emitted_at": _dt.now(_tz.utc).isoformat(),
        "ticker": str(ticker).upper(),
        "effective_date": _date.today().isoformat(),
        "rating": pm.get("rating") if isinstance(pm, dict) else None,
        "data_quality": (pm.get("data_quality") if isinstance(pm, dict) else None) or "unknown",
        "guardrail_reason": pm.get("guardrail_reason") if isinstance(pm, dict) else None,
        "risk_gate_verdict": rg.get("verdict") if isinstance(rg, dict) else None,
    }
    doc = dict(body)
    doc["decision_hash"] = "sha256:" + _hl.sha256(_rj.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    p = Path(save_path) / "alpha_ledger.jsonl"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(_rj.dumps(doc, sort_keys=True, default=str) + "\n")
    return p


def _run_card_llm_cost_est() -> dict:
    """Advisory LLM cost block for run_card.json (llm_cost.py W1-8).

    Reports the provider rate-table entry per model (USD per 1M tokens) plus
    an upper-bound output-leg cost at the configured max-output cap. Token
    counts per run are not tracked, so the cap-bound figure is exactly that -
    labeled, never a billing claim.
    """
    try:
        from tradingagents.strategies.llm_cost import estimate_cost, rate_for

        cfg = _config(None)
        out = {}
        for key in ("deep_think_llm", "quick_think_llm"):
            model = cfg.get(key)
            if not model:
                continue
            rate = rate_for(model)
            cap = float(cfg.get("max_output_tokens_deep" if key == "deep_think_llm" else "max_output_tokens", 8000))
            out[key] = {
                "model": model,
                "rate_usd_per_1m": {"in": rate[0], "out": rate[1]} if rate else None,
                "max_output_leg_usd": (
                    estimate_cost(model, 0, int(cap)) if rate else None
                ),
                "note": "upper bound of the output leg at the configured max_output cap",
            }
        return out
    except Exception:  # noqa: BLE001 - advisory block degrades
        return {}


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
                if agg.get("unavailable"):
                    sd_lines.append(
                        f"- {alias}: mean UNAVAILABLE (judge did not run) "
                        f"{agg.get('reason', '')}".rstrip()
                    )
                else:
                    sd_lines.append(
                        f"- {alias}: mean {agg.get('mean', '-')} "
                        f"(scores: {agg.get('scores', {})})"
                    )
            if sd.get("claim_ledger_md"):
                sd_lines.append(sd["claim_ledger_md"])
            evidence = _finalize_section(
                _readable_section("\n".join(sd_lines), role="Research Manager")
            )
            # Evidence file stays on disk (structured_debate.md) but is NOT
            # appended to complete_report.md — it is a debug artifact, kept
            # out of the user-facing report (2026-09-01).
            (research_dir / "structured_debate.md").write_text(evidence, encoding="utf-8")
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
        # Structured risk-debate evidence (direction.md parity): judge scores
        # per anonymized candidate + grounded claim ledger + L1 verdict from
        # the structured_risk_state channel. Mirrors the research block.
        sr = final_state.get("structured_risk_state") or {}
        if sr.get("judge_scores") or sr.get("claim_ledger_md") or sr.get("l1"):
            risk_dir.mkdir(exist_ok=True)
            sd_lines = ["## Structured risk-debate evidence (deterministic)"]
            l1 = sr.get("l1")
            if l1:
                sd_lines.append(
                    f"- L1 verdict: {l1.get('severity_tier', '?')} / "
                    f"{l1.get('l1_action', '?')} (side={l1.get('side', '?')}, "
                    f"penalty={l1.get('penalty_score', 0)})"
                )
            judge = sr.get("judge_scores") or {}
            for alias, agg in judge.items():
                if agg.get("unavailable"):
                    sd_lines.append(
                        f"- {alias}: mean UNAVAILABLE (judge did not run) "
                        f"{agg.get('reason', '')}".rstrip()
                    )
                else:
                    sd_lines.append(
                        f"- {alias}: mean {agg.get('mean', '-')} "
                        f"(scores: {agg.get('scores', {})})"
                    )
            if sr.get("claim_ledger_md"):
                sd_lines.append(sr["claim_ledger_md"])
            evidence = _finalize_section(
                _readable_section("\n".join(sd_lines), role="Portfolio Manager")
            )
            # Evidence file stays on disk (structured_risk_debate.md) but is
            # NOT appended to complete_report.md (debug artifact; kept out of
            # the user-facing report).
            (risk_dir / "structured_risk_debate.md").write_text(
                evidence, encoding="utf-8"
            )
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
            # Truncation detection must see ONLY the LLM-produced decision text:
            # the audit note and disclosure block are computed appendages whose
            # lowercase tails (e.g. "models: n/a") would false-positive
            # _looks_truncated ("mid-sentence" marker on a complete decision).
            # Finalize the LLM body first, then append the computed blocks.
            decision_llm = risk["judge_decision"]
            pm_body = _finalize_section(decision_llm)
            # Computed reference levels from the position contract (shared by
            # the audit + disclosure blocks; parsed once, never fabricated).
            import re as _re

            ref_stop = None
            ref_target = None
            contract = final_state.get("position_contract")
            if isinstance(contract, str):
                m = _re.search(r"\bstop\s+([0-9.]+)", contract, _re.IGNORECASE)
                if m:
                    ref_stop = float(m.group(1))
                m2 = _re.search(r"\btarget\s+([0-9.]+)", contract, _re.IGNORECASE)
                if m2:
                    ref_target = float(m2.group(1))
            if cfg.get("enable_decision_audit"):
                try:
                    audit_note = audit_decision_numbers(decision_llm, {"stop": ref_stop})
                    if audit_note:
                        pm_body = pm_body.rstrip() + audit_note
                except Exception:  # noqa: BLE001 - audit is advisory, never blocks
                    pass
            # DSA phase D disclosure + invalidation advisory block (default off,
            # matches enable_report_attribution; computed only, never gates).
            if cfg.get("enable_report_attribution", False):
                try:
                    from tradingagents.strategies.report_disclosure import (
                        consensus_readout,
                        disclosure_footers,
                        invalidation_conditions,
                        signal_attribution,
                        watch_conditions,
                    )

                    # data_quality: the PM decision's own declared field when
                    # present (mirrors PortfolioDecision.data_quality), else
                    # honest "unknown" - never assumed fresh.
                    dq = "unknown"
                    m3 = _re.search(
                        r"data\s*quality[^0-9a-z]{0,6}(fresh|stale|partial|unknown)",
                        decision_llm, _re.IGNORECASE,
                    )
                    if m3:
                        dq = m3.group(1).lower()
                    invalids = invalidation_conditions(
                        stop_loss=ref_stop, take_profit=ref_target, data_quality=dq,
                    )
                    # Watch rows come from the computed risk gate (verdict +
                    # reasons + halt) - never narrated.
                    gate = final_state.get("risk_gate") or {}
                    watch = list(gate.get("reasons") or [])
                    verdict = str(gate.get("verdict") or "PASS")
                    if verdict != "PASS":
                        watch.insert(0, f"risk gate {verdict} active")
                    if final_state.get("risk_halt"):
                        watch.append("risk halt active - escalation required")
                    next_check = None
                    try:
                        from datetime import timedelta, timezone

                        from tradingagents.dataflows.effective_date import (
                            effective_trading_date,
                        )

                        nxt = effective_trading_date(
                            ref_utc=datetime.now(timezone.utc) + timedelta(days=1)
                        )
                        next_check = f"{nxt or 'today'} (next check, effective-date calendar)"
                    except Exception:  # noqa: BLE001 - computed calendar degrades
                        next_check = None
                    # Consensus (supporting/opposing) from the structured risk
                    # debate's L1 verdict side: the winning side supports the
                    # decision, the loser opposes (advisory, derived - not
                    # narrated by the LLM).
                    _supporting: list[str] = []
                    _opposing: list[str] = []
                    try:
                        _l1 = (final_state.get("structured_risk_state") or {}).get("l1") or {}
                        _side = str(_l1.get("side") or "").lower()
                        if _side in ("bull", "buy", "long"):
                            _supporting, _opposing = ["bull"], ["bear"]
                        elif _side in ("bear", "sell", "short"):
                            _supporting, _opposing = ["bear"], ["bull"]
                    except Exception:  # noqa: BLE001 - derived consensus degrades
                        pass
                    cons = consensus_readout(_supporting, _opposing)
                    wc = watch_conditions(watch, next_check)
                    attr = signal_attribution()
                    disc = disclosure_footers([], [], models_used=None)
                    # W3-1 decision-level data-quality score + W3-7 falsification
                    # conditions (advisory; computed, never guessed).
                    dq_line = "data quality: n/a"
                    fals_line = "falsification conditions: none recorded"
                    try:
                        from tradingagents.strategies.data_quality import aggregate_quality

                        dqo = aggregate_quality({})
                        if dqo["score"] is not None:
                            dq_line = (f"data quality: {dqo['score']:.0f}/100 ({dqo['tier']})"
                                       f" - per-input {dqo['inputs']}")
                    except Exception:  # noqa: BLE001 - advisory
                        pass
                    block = [
                        "### Decision disclosure (computed, advisory)",
                        "",
                        f"- invalidation conditions: {'; '.join(invalids)}",
                        f"- consensus: supporting={', '.join(cons['supporting']) or 'n/a'} · opposing={', '.join(cons['opposing']) or 'none'}",
                        f"- {dq_line}",
                        f"- {fals_line}",
                        f"- attribution weights: {attr['weights'] or 'n/a'} (missing: {', '.join(attr['missing'])})",
                        f"- watch conditions: {wc['watch_conditions'] or 'none'} · next check: {wc['next_check_time'] or 'n/a'}",
                        f"- data sources used: {', '.join(disc['sources_used']) or 'none'} · empty: {', '.join(disc['sources_empty']) or 'none'} · models: {', '.join(disc['models_used']) or 'n/a'}",
                    ]
                    pm_body = pm_body.rstrip() + "\n\n" + "\n".join(block)
                except Exception:  # noqa: BLE001 - disclosure advisory, never blocks
                    pass
            wrapped = prepend_block(pm_body)
            (portfolio_dir / "decision.md").write_text(wrapped, encoding="utf-8")
            sections.append(
                f"## V. Portfolio Manager Decision\n\n### Portfolio Manager\n\n{_shift_down(prepend_block(pm_body))}"
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
    # Vibe-Trading run_card.json reproducibility metadata (P2-5): one JSON file
    # per report tree with the config hash, commit, LLM setup, and the
    # computed decision summary, so a report folder is re-runnable/auditable
    # without digging through log blobs. Advisory; never gates.
    try:
        import hashlib
        import json as _json

        from tradingagents.default_config import DEFAULT_CONFIG

        cfg_hash = hashlib.sha256(
            _json.dumps(DEFAULT_CONFIG, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]
        commit = ""
        try:
            import subprocess as _sp

            commit = _sp.run(
                ["git", "-C", str(save_path.resolve().parents[1] if save_path.is_absolute() else save_path),
                 "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except Exception:  # noqa: BLE001 - commit is best-effort
            commit = ""
        from datetime import timezone as _card_tz

        verdict = (final_state.get("risk_gate") or {}).get("verdict")
        card = {
            "ticker": ticker,
            "generated": datetime.now(_card_tz.utc).isoformat(),
            "config_hash": cfg_hash,
            "commit": commit,
            "llm": {
                "provider": DEFAULT_CONFIG.get("llm_provider"),
                "deep_think_llm": DEFAULT_CONFIG.get("deep_think_llm"),
                "quick_think_llm": DEFAULT_CONFIG.get("quick_think_llm"),
            },
            "llm_cost_est": _run_card_llm_cost_est(),
            "decision": {
                "verdict": verdict,
                "risk_halt": bool(final_state.get("risk_halt")),
            },
            "sections": [],
        }
        (save_path / "run_card.json").write_text(
            _json.dumps(card, indent=2, default=str), encoding="utf-8"
        )
        # research_decision.json - deterministic execution contract for the
        # TradingExecution layer (Phase A daemon input). Advisory; never gates;
        # a failure here must never break the report tree.
        with suppress(Exception):  # noqa: BLE001 - advisory; never breaks the report
            write_research_decision(final_state, ticker, save_path)
        with suppress(Exception):  # noqa: BLE001 - advisory; never breaks the report
            write_alpha_ledger(final_state, ticker, save_path, cfg)
    except Exception:  # noqa: BLE001 - card is advisory
        pass
    return save_path / "complete_report.md"
