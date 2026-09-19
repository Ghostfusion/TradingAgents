"""The report-hygiene rules every analyst prompt carries, defined once.

Two failure modes reached the report trees and were shipped as deliverables,
because nothing on the path could see them as defects:

- **Inline self-correction.** The model retypes a figure, notices, and leaves
  the repair in the artifact: "Corrected positioning bullet: ...", "Levels
  bullet corrected: ...", a value followed by "corrected: <other value>"
  (VTV 2026-09-16 market.md; HPE 2026-09-10 news.md leaked "9.87 ... corrected:
  4.8" and "172.346 ... correction - 154.3360").
- **Restart / re-emit.** The model narrates its own degeneration and emits the
  body again: "I will restart cleanly", "disregard this draft", "I am stuck
  repeating myself" (HPE 2026-09-14 fundamentals.md; MSFT 2026-09-16 news.md,
  which ended "[HARD STOP]"; VTV 2026-09-16 news.md, which ended "(Report
  truncated here deliberately ... reproducing known degeneration patterns)").

The news analyst carried both clauses; the market and fundamentals analysts
carried only the restart half and the sentiment analyst neither, so the VTV
market artifact leaked the self-correction form into a stem that was otherwise
a report. One constant, appended by every analyst node, keeps a single
convention - and `tests/test_analyst_evidence_wiring.py` checks the wiring.

The runtime guards in ``structured`` are the net under this: they classify a
cascade, a repeated line or a self-narrated failure as a non-deliverable and
repair or replace it. This text is what keeps the model from writing one.
"""

from __future__ import annotations

REPORT_HYGIENE_RULES = (
    " NO SELF-CORRECTION ARTIFACTS: never leave a value in the report with an"
    " inline (corrected: / correction -) caveat, and never label a bullet"
    " 'corrected'. If you catch a retype mid-edit, rewrite cleanly - a final"
    " artifact must never contain a wrong value plus a correction marker"
    " (HPE 2026-09-10 news.md leaked '9.87 ... corrected: 4.8'; VTV 2026-09-16"
    " market.md shipped 'Corrected positioning bullet:' and 'Levels bullet"
    " corrected:')."
    " NEVER RESTART OR RE-EMIT: if you notice a repeated line, a mistyped"
    " figure, or that the answer is unravelling, finish the current sentence"
    " and STOP. Never write 'correction needed', 'this is degenerating', 'I am"
    " stuck repeating myself', 'disregard this draft' or 'I will restart"
    " cleanly', and never emit a second copy of the body. One report = ONE body"
    " and ONE 'FINAL TRANSACTION PROPOSAL' line; a repetition loop or a restart"
    " leaves the whole stem unusable (HPE 2026-09-14 fundamentals.md: a line"
    " repeated twelve times, a self-disavowal, then a space-stripped second"
    " copy - the stem had to be discarded)."
)

__all__ = ["REPORT_HYGIENE_RULES", "engine_score_block"]


def _engine_label(engine: str) -> str:
    """The engine's printed name, matching `quant_scorecard.format_engine_detail`."""
    return "EventState" if engine == "event" else f"{engine.capitalize()}Score"


def _call_engine(tool_name: str, ticker: str, trade_date: str | None) -> str:
    """Run one engine's own reader. Never raises - an engine that cannot be
    measured yields an explicit unavailable line, never a zero."""
    from tradingagents.agents.utils import analysis_tools

    fn = getattr(analysis_tools, tool_name, None)
    if fn is None:
        return f"{tool_name}: unavailable (reader not found)"
    fn = getattr(fn, "func", fn)
    try:
        return str(fn(ticker, trade_date))
    except TypeError:
        try:
            return str(fn(ticker))
        except Exception as exc:  # noqa: BLE001
            return f"{tool_name}: unavailable ({type(exc).__name__})"
    except Exception as exc:  # noqa: BLE001
        return f"{tool_name}: unavailable ({type(exc).__name__})"


def engine_score_block(
    analyst_key: str,
    ticker: str,
    trade_date: str | None = None,
    cfg: dict | None = None,
) -> str:
    """The score-engine instruction for one analyst, WITH the numbers supplied.

    **Built from `quant_scorecard.ENGINE_SECTIONS` - the one ownership map - so
    the prompt, the tool binding and the report placement are three readings of
    one table and cannot drift apart.**

    Two design points this encodes:

    * **The result is PRE-COMPUTED and handed over**, not merely offered as a
      tool. The owner's invariant is that the model *"may interpret an engine
      result, but does not decide whether or where the authoritative engine
      result appears"* - a tool the model may or may not call does not satisfy
      that. The number is in the prompt either way.
    * **It works for an analyst that binds no tools at all.** The sentiment
      analyst pre-fetches its data and has no ToolNode, so a "call
      `get_sentiment_score`" instruction there would invite a hallucinated call
      (`NO_EXTERNAL_TOOLS`). Supplying the text is the only route that reaches
      that report.

    Returns ``""`` when the master gate is off, when the analyst owns no engine,
    or when every owned engine is unmeasurable - so a gate-off prompt is
    byte-identical to a pre-scorecard one.
    """
    try:
        from tradingagents.strategies.quant_scorecard import (
            ENGINE_GATES,
            ENGINE_TOOLS,
            engines_for_analyst,
        )
    except Exception:  # noqa: BLE001 - no map means no block
        return ""
    config = cfg or {}
    if not config.get("enable_quant_scorecard"):
        return ""
    owned = engines_for_analyst(analyst_key)
    if not owned:
        return ""

    sections: list[str] = []
    for engine in owned:
        if not config.get(ENGINE_GATES[engine]):
            continue
        text = _call_engine(ENGINE_TOOLS[engine], ticker, trade_date).strip()
        if not text:
            continue
        sections.append(text)
    if not sections:
        return ""

    labels = ", ".join(_engine_label(e) for e in owned if config.get(ENGINE_GATES[e]))
    body = "\n\n".join(sections)
    return (
        "\n\nSCORE ENGINE — YOURS TO REPORT. The "
        f"{labels} result belongs to THIS report; the ownership map assigns "
        f"{'/'.join(owned)} to the {analyst_key} analyst. It is already computed "
        "and supplied below — DO NOT re-derive it, recompute it, or substitute "
        "your own number.\n\n"
        "Report it under a subsection headed "
        f"'## {_engine_label(owned[0])} (engine score)', quoting the score, its "
        "COVERAGE and its band VERBATIM. Coverage travels with the number: "
        "'72 at coverage 68%' means 72 over 68% of the intended evidence, so "
        "never drop it, and never present a partial score as a complete one. "
        "Where a category is reported NA it was withheld below its floor — "
        "report it as withheld, never as zero. The engine is the highest-level "
        "quantitative evidence summary for a human reviewer: it is NOT an "
        "order, NOT a position size and NOT a gate. Interpret it — say what it "
        "supports and what it argues against — but do not restate it as your "
        "recommendation.\n\n"
        "--- engine evidence (authoritative) ---\n"
        f"{body}\n"
        "--- end engine evidence ---"
    )
