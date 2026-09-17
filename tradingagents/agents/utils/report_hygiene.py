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

__all__ = ["REPORT_HYGIENE_RULES"]
