"""Second-layer report verification against the tool evidence (advisory).

The deterministic ``--evidence`` cross-check (``scripts/repro_check.py``)
verifies decimal figures in each analyst report against
``tool_evidence.json`` leaves. This module adds a *qualitative* pass over the
SAME evidence: one LLM call per analyst report reads the finished markdown +
the report's evidence leaves and returns per-claim verdicts
(``GROUNDED | UNSUPPORTED | CONTRADICTED``).

Design: docs/design_report_verification_llm.md

Deterministic numeric anchoring runs AFTER the LLM (``_anchor_claims``)
so number-matching verdicts never depend on the model's arithmetic: a
decimal the evidence actually contains downgrades UNSUPPORTED to GROUNDED;
a CONTRADICTED claim whose figure matches evidence is downgraded to
UNSUPPORTED. The tolerance is shared with ``repro_check._matches`` (<=0.5%).

Advisory by contract: never edits reports, never blocks delivery. A
provider failure degrades to "verifier unavailable" (the caller returns 0 and
the stem reports the deterministic half it could still produce: ``NUMERIC_ONLY``
when the figures were checked, ``UNKNOWN`` when there was nothing to check),
exactly like ``llm_failure_journal`` degrades the structured-invoke path — one
failed call must never kill a run.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from tradingagents.agents.utils.evidence_gather import RENDERED_BLOCK_KEY
from tradingagents.agents.utils.tool_call_markup import TOOL_CALL_MARKUP_RE

logger = logging.getLogger(__name__)

# Analyst report stems this pass covers (1_analysts/ in each report tree).
REPORT_STEMS = ("fundamentals", "market", "news", "sentiment")

# Canonical figure-matching helpers, shared with scripts/repro_check.py (which
# imports these) so the numeric anchor and the deterministic cross-check use
# the SAME tolerance and unit handling — they can never disagree about
# "same value".
_DEC_RE = re.compile(r"\d+\.\d+")

# Unit-magnitude equivalence: evidence leaves store raw tool floats
# (e.g. 122368000.0) while reports cite human units (122.4M). A figure
# matches when the raw pair is within tolerance OR differs by a clean unit
# step (K/M/B/T) — the MSTR 2026-09-08 batch flagged every unit-reformatted
# figure as UNSUPPORTED before this.
_UNIT_SCALES = (1.0, 1e2, 1e3, 1e6, 1e9, 1e12)

# A bare-integer figure that carries signal when expressed as a percent:
# "A (92%)" vs an evidence leaf storing 0.92 as a fraction. Bare ints are
# otherwise too noisy for grounding, so only percent-marked ints count.
_PCT_INT_RE = re.compile(r"(?<![.\d])(\d+(?:\.\d+)?)\s*%")


def _float_tokens(text: str) -> set:
    """Distinct decimal numbers in ``text`` (the figures that carry signal;
    bare integers are too noisy for a cheap grounding check)."""
    out = set()
    for m in _DEC_RE.finditer(text):
        try:
            out.add(float(m.group()))
        except ValueError:
            continue
    # Explicit percents written as bare integers ("92%") are signal, not
    # noise - collect them so the anchor sees the composite-rank transposition
    # class (report "A (92%)" vs a leaf storing 0.92 fraction) instead of
    # silently missing integer figures.
    for m in _PCT_INT_RE.finditer(text):
        try:
            out.add(float(m.group(1)))
        except ValueError:
            continue
    return out


def _matches(flt: float, refs: set) -> bool:
    """Roughly same value as some evidence figure, unit-aware.

    Accepts a <=0.5% relative difference (the repro_check tolerance), OR an
    exact K/M/B/T magnitude step (report says 122.4M, leaf stores 122368000.0).
    """
    for ref in refs:
        denom = max(abs(ref), abs(flt), 1e-9)
        if abs(flt - ref) / denom <= 0.005:
            return True
        # unit reformatting: same digits different scale (12.24 -> 122368000)
        for scale in _UNIT_SCALES[1:]:
            scaled = flt / scale
            denom2 = max(abs(ref), abs(scaled), 1e-9)
            if abs(scaled - ref) / denom2 <= 0.005:
                return True
            scaled = flt * scale
            denom3 = max(abs(ref), abs(scaled), 1e-9)
            if abs(scaled - ref) / denom3 <= 0.005:
                return True
    return False


# ---------------------------------------------------------------------------
# Verdict schema (pydantic; mirrors schemas.py conventions)
# ---------------------------------------------------------------------------


class VerifierClaim(BaseModel):
    """One extracted claim + its grounding verdict."""

    claim: str = Field(description="The sentence/claim as written in the report.")
    status: Literal[
        "GROUNDED", "UNSUPPORTED", "CONTRADICTED", "MISQUOTED", "INTERNAL_CONFLICT"
    ] = Field(
        ...,
        description=(
            "GROUNDED: the claim's specifics (figures, direction, state) are "
            "present in the evidence leaves; UNSUPPORTED: the claim asserts "
            "specifics the evidence does not contain; CONTRADICTED: evidence "
            "contains an opposing value/state; MISQUOTED: the claim's figures "
            "ARE present in the evidence but attached to the wrong label / "
            "subject / context (e.g. a 92% and 58% transposed between two "
            "peers) - the deterministic anchor detected the misuse rather than "
            "silently grounding it; INTERNAL_CONFLICT: the same metric is "
            "reported at conflicting values within this one report."
        ),
    )
    reason: str = Field(
        ...,
        description="One line: which leaf tool/value supports or refutes the claim, or 'no leaf evidence'.",
    )


class BasisAssertion(BaseModel):
    """A typed ``(metric, value, basis)`` triple the deterministic layer resolved.

    The checks in this module are regexes over prose; this is the same
    extraction emitted as data, per run, so two runs of one ticker can be
    compared mechanically. The drift that motivated it leaves no prose trace to
    diff: the same ``(AMZN, 2026-09-14)`` call returned FY-annual flows at
    22:5xZ and TTM quarters at 19:08Z (EV/EBIT 32.79 -> -30551.06), and the
    same metric is quoted at 5.50 vs 4.40 (LULU), 0.30 vs 0.4220 (MSFT rvol),
    1.81 vs 5.76 (LRCX diluted EPS) across runs.

    ``basis`` is the period token the report itself prints beside the value
    (``_period_tag``), else the metric's unit class - never a guess: a number
    with no stated period is recorded as ``level``/``ratio``/``percent``/
    ``multiple``, which is exactly the distinction a comparison must respect.
    """

    metric: str
    value: float
    basis: str
    source: Literal["evidence", "report"] = Field(
        ...,
        description=(
            "evidence = the value resolves to a tool leaf within the metric's "
            "tolerance; report = it appears only in the prose."
        ),
    )


class ReportVerification(BaseModel):
    """Verdicts for one analyst report."""

    report: str = Field(..., description="Analyst key, e.g. 'fundamentals'.")
    claims: list[VerifierClaim] = Field(default_factory=list)
    overall: Literal["PASS", "FLAG", "UNKNOWN", "NUMERIC_ONLY"] = Field(
        ...,
        description=(
            "PASS = every claim grounded; FLAG = any UNSUPPORTED/CONTRADICTED/"
            "MISQUOTED/INTERNAL_CONFLICT; NUMERIC_ONLY = the LLM half could "
            "not run (or was unparsed) but the deterministic families DID run "
            "and found nothing - the prose is unverified, the figures are not; "
            "UNKNOWN = nothing ran at all."
        ),
    )


# ---------------------------------------------------------------------------
# Evidence digest + claim anchoring (pure, deterministic)
# ---------------------------------------------------------------------------


def _evidence_decimals(evidence: dict, analyst_key: str) -> set:
    """All decimal figures across the leaves of one analyst's evidence."""
    out: set = set()
    leaves = evidence.get(analyst_key) or []
    if not isinstance(leaves, list):
        return out
    for leaf in leaves:
        if not isinstance(leaf, dict):
            continue
        out |= _float_tokens(str(leaf.get("content") or ""))
    # The reference-price line is evidence too (see _reference_price_line): the
    # anchor layer must treat its figure as present, or it downgrades every
    # claim quoting it.
    out |= _float_tokens(_reference_price_line(evidence, analyst_key))
    out |= _float_tokens(_instrument_identity_line(evidence, analyst_key))
    return out


_REFERENCE_LINE_RE = re.compile(r"(?m)^\*\*Reference price:.*$")
# The resolved instrument identity is the SECOND prompt-level fact prepended to
# every analyst's evidence block (see evidence_gather._instrument_identity_line):
# "Resolved identity: Company: X; Exchange: Y". A report naming its venue is
# quoting the prompt, so the line is evidence too - without it, IEI 2026-09-16
# and VTV 2026-09-16 both had a true venue flagged as fabrication.
_IDENTITY_LINE_RE = re.compile(r"(?m)^\*\*Instrument identity.*$")

# The 0-10 headline sentiment score is a PROMPT contract, not a leaf value: the
# sentiment analyst must map ``computed_score`` in [-1, 1] to
# ``5 + 5 * computed_score`` and stay within +/-0.5 (sentiment_analyst's system
# prompt; the 0-10 bounds are documented in agents/schemas.py::SentimentReport).
# On 2026-09-16 the LLM verifier applied that rule inconsistently - AMZN's
# 9.5/10 (anchor 10.0) and IEI's ~0/10 (anchor 0.0) were flagged UNSUPPORTED,
# while MSFT's 3.75 and VTV's 9.25/9.00 were accepted as the rescaled form - so
# the band is now checked deterministically, before the LLM verdict is trusted.
_SENTIMENT_SCORE_RE = re.compile(r"computed_score\s*=\s*([+-]?\d+(?:\.\d+)?)")
_SENTIMENT_BAND = 0.5
_SENTIMENT_SCORE_CLAIM_RE = re.compile(r"(?i)score|sentiment|/\s?10\b")
# The score a claim STATES: the number bound to its own score word / equals
# sign, so a date or a message count elsewhere in the line cannot disqualify it.
_SENTIMENT_CLAIM_NUM_RE = re.compile(
    r"(?:score[^\d\n]{0,12}|[=\u2248]\s*)([+-]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def _sentiment_claim_numbers(claim: str) -> list[float]:
    """The 0-10 score figures a claim states (empty when it states none)."""
    out: list[float] = []
    for m in _SENTIMENT_CLAIM_NUM_RE.finditer(claim or ""):
        try:
            out.append(float(m.group(1)))
        except ValueError:  # pragma: no cover - regex guarantees a float
            continue
    return out


def _sentiment_anchor(evidence: dict, analyst_key: str) -> float | None:
    """The prompt-mandated 0-10 anchor for this stem, from computed_score."""
    for leaf in evidence.get(analyst_key) or []:
        if not isinstance(leaf, dict):
            continue
        m = _SENTIMENT_SCORE_RE.search(str(leaf.get("content") or ""))
        if m:
            try:
                return 5.0 + 5.0 * float(m.group(1))
            except ValueError:  # pragma: no cover - regex guarantees a float
                continue
    return None


def _reference_price_line(evidence: dict, analyst_key: str) -> str:
    """The run's reference-price line as the analyst received it ("" if none).

    It is not a tool leaf - ``evidence_gather._render_evidence`` PREPENDS it to
    every stem's evidence block - so without this the verifier read every
    "reference price X (..., FORMING intraday bar)" claim as fabrication: TSM
    2026-09-15 news.md (413.23, "no leaf prints it") and AMZN 2026-09-15
    news.md, which named its own source as "prompt".
    """
    blocks = evidence.get(RENDERED_BLOCK_KEY)
    if not isinstance(blocks, list):
        return ""
    for entry in blocks:
        if not isinstance(entry, dict) or entry.get("analyst") != analyst_key:
            continue
        match = _REFERENCE_LINE_RE.search(str(entry.get("block") or ""))
        if match:
            return match.group(0).strip()
    return ""


def _instrument_identity_line(evidence: dict, analyst_key: str) -> str:
    """The resolved-identity line as the analyst received it ("" if none).

    Same shape as ``_reference_price_line``: a prompt-level fact prepended to
    the evidence block, not a tool leaf, so a venue/name claim in the report is
    grounded only if the verifier can see it.
    """
    blocks = evidence.get(RENDERED_BLOCK_KEY)
    if not isinstance(blocks, list):
        return ""
    for entry in blocks:
        if not isinstance(entry, dict) or entry.get("analyst") != analyst_key:
            continue
        match = _IDENTITY_LINE_RE.search(str(entry.get("block") or ""))
        if match:
            return match.group(0).strip()
    return ""


def _evidence_digest(evidence: dict, analyst_key: str, cap_chars: int | None = None) -> str:
    """Compact per-stem rendering of one analyst's evidence leaves.

    No extra truncation by default: the gatherer already caps each leaf at
    ``summary_window`` (default 12000), so the digest shows exactly what the
    analyst reduced from. A per-leaf cap WILL hide the cited figures — the
    MSTR 2026-09-08 batch flagged the income-statement revenue as "no leaf
    evidence" because an old 200-char digest cut to the column header; the
    revenue row sits at the leaf's end (~4.4k chars in).
    """
    leaves = evidence.get(analyst_key) or []
    lines: list[str] = []
    identity = _instrument_identity_line(evidence, analyst_key)
    if identity:
        lines.append(f"- instrument_identity [ok]: {identity}")
    reference = _reference_price_line(evidence, analyst_key)
    if reference:
        lines.append(f"- reference_price [ok]: {reference}")
    if isinstance(leaves, list):
        for leaf in leaves:
            if not isinstance(leaf, dict):
                continue
            tool = str(leaf.get("tool") or "?")
            status = str(leaf.get("status") or "?")
            content = str(leaf.get("content") or "")
            if cap_chars and len(content) > cap_chars:
                content = content[:cap_chars] + " [truncated]"
            lines.append(f"- {tool} [{status}]: {content}")
    return "\n".join(lines) if lines else "(no evidence leaves for this analyst)"


def _load_report(report_dir: Path, stem: str) -> str | None:
    p = report_dir / "1_analysts" / f"{stem}.md"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="ignore")


def _debate_degradation(report_dir: Path) -> dict:
    """Tree-level check: did the advertised structured debate actually run?

    ``enable_debate`` promises the claim-verified debate, and ``run_card.json``
    (written by ``reporting.write_report_tree``) records whether it happened. A
    tree that says enabled with no ``2_research/structured_debate.md`` ran the
    baseline / legacy path instead - the report looks normal and only the prose
    differs (NVDA 2026-09-12), which is why this is a flag rather than a note.

    Pure file inspection: no config, no LLM, no live run. Returns
    ``{enabled, evidence, degraded, reason}``. ``enabled`` is None for a tree
    written before the run-card block existed, and an unknown is NOT a
    degradation - only a tree that positively claims the structured debate
    while lacking its evidence is flagged. ``evidence`` complements the run
    card's own record (a tree can carry the artifact without the card).
    """
    tree = Path(report_dir)
    evidence = (tree / "2_research" / "structured_debate.md").exists()
    card: dict = {}
    try:
        card_path = tree / "run_card.json"
        if card_path.exists():
            loaded = json.loads(card_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                card = loaded.get("debate") or {}
    except (OSError, ValueError) as exc:
        logger.warning("report_verifier: cannot read %s: %s", tree / "run_card.json", exc)
    if not isinstance(card, dict):  # older/odd shape: fall back to the artifact
        card = {}
    enabled = card.get("enabled")
    enabled = bool(enabled) if enabled is not None else None
    # The run card is authoritative when it carries the verdict (it was
    # computed with the config in hand); otherwise derive from the artifact -
    # a tree that positively claims the structured debate while lacking its
    # evidence is degraded, an unknown is not.
    degraded = (
        bool(card["degraded"])
        if "degraded" in card
        else (enabled is True and not evidence)
    )
    return {
        "enabled": enabled,
        "evidence": evidence,
        "degraded": degraded,
        "reason": str(card.get("reason") or ""),
    }


def _envelope_integrity(report_dir: Path) -> dict:
    """Tree-level check: does ``research_decision.json`` satisfy its own contract?

    The executor treats the artifact as a versioned envelope and dead-letters
    what it cannot validate (missing expiry, a naive timestamp, a body hash that
    does not recompute, an out-of-range ``opportunity_score``) — failures that
    are invisible in the report prose, and that a rebuild or a hand edit can
    introduce after the fact. Pure file inspection, no LLM, no live run.

    Legacy artifacts (no version, or < 1.1) are **not** flagged: the executor
    reads them as 1.0.0 and skips the stricter checks, so flagging them would
    mark every historical tree as broken. The rules themselves live in
    ``tradingagents.execution_contract`` — one owner, shared with the emitter, so
    the two cannot drift. Returns ``{present, version, strict, problems}``.
    """
    from datetime import datetime, timezone

    from tradingagents.execution_contract import integrity_problems, is_v11, parse_version

    path = Path(report_dir) / "research_decision.json"
    if not path.exists():
        return {"present": False, "version": None, "strict": False, "problems": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("report_verifier: cannot read %s: %s", path, exc)
        return {
            "present": True,
            "version": None,
            "strict": False,
            "problems": [{"code": "unreadable", "detail": str(exc)}],
        }
    if not isinstance(raw, dict):
        return {
            "present": True,
            "version": None,
            "strict": False,
            "problems": [
                {"code": "invalid_artifact", "detail": "the artifact root is not an object"}
            ],
        }
    version = ".".join(str(part) for part in parse_version(raw))
    return {
        "present": True,
        "version": version,
        "strict": is_v11(raw),
        "problems": integrity_problems(raw, now=datetime.now(timezone.utc)),
    }


# ---------------------------------------------------------------------------
# LLM pass (reuses the repo's structured-invoke hardening)
# ---------------------------------------------------------------------------


_VERIFY_INSTRUCTIONS = """\
You are a report-grounding verifier. Below is (1) an analyst report and
(2) the tool evidence that analyst was allowed to cite — the leaves of
tool_evidence.json (tool name, status, content).

Judge EVERY claim that asserts a specific fact. Output one verdict per
claim:
- GROUNDED: the claim's substance (including every number it cites) is
  present in the evidence leaves, or is a narrow synthesis of leaves it
  cites.
- UNSUPPORTED: the claim asserts figures, directions, or states the
  evidence does not contain (this is the fabrication class the gate
  exists to catch).
- CONTRADICTED: the evidence contains an opposing value or state (e.g.
  claim says +8% EPS, evidence says -3%).
- MISQUOTED: the figures you cite ARE in the evidence, but attached to the
  wrong label / subject / context (e.g. a 92% and 58% belonging to different
  peers are transposed; a T1 target is mislabeled). If the number matches a
  leaf but the claim uses it wrongly (wrong metric, wrong sign attribution,
  wrong entity), say MISQUOTED and name the correct mapping in `reason`.

Rules:
- Base every verdict on the evidence block ONLY. Do not use outside
  knowledge to rescue or condemn a claim.
- Two lines in the block are prompt-level facts rather than tool leaves and
  are equally valid evidence: `instrument_identity` (the ticker's resolved
  company/fund name, sector and listing venue) and `reference_price` (the
  run's price basis, with the intraday FORMING flag). A report naming its
  venue or its price basis is quoting what it was given, not fabricating.
- A number must match an evidence number (same value, sign matters).
  If the report says a figure the evidence lacks, that claim is
  UNSUPPORTED even if the rest sounds plausible.
- Qualitative framing ("strong momentum", "compelling") is not a fact;
  do not flag it.
- A stated WEIGHTING is not a claim about the world: when the report names
  the signals it weighed and says which it favoured and why (the mandated
  SIGNAL SYNTHESIS line), that sentence is GROUNDED - no leaf could hold it.
  The exemption covers the weighting statement itself, never the figures it
  cites: a figure the evidence lacks stays UNSUPPORTED.
- A sentiment SCORE on the 0-10 scale is not a leaf value: the sentiment
  analyst is required to map ``computed_score`` in [-1, 1] to
  ``5 + 5 * computed_score`` and stay within +/-0.5 of that anchor. A headline
  score inside the band is GROUNDED against the leaf that supplies
  ``computed_score`` - never UNSUPPORTED for lack of a 0-10 leaf.
- Cite the supporting/refuting evidence in `reason` via the tool name and
  value (e.g. "get_analyst_verdict [ok]: EY ..."). When no leaf supports
  it, say "no leaf evidence".
"""


def _build_prompt(report_name: str, report_text: str, digest: str) -> str:
    return (
        _VERIFY_INSTRUCTIONS
        + "\n\n"
        + f"REPORT ({report_name}):\n"
        + "---\n"
        + report_text
        + "\n---\n\n"
        + f"TOOL EVIDENCE ({report_name}):\n"
        + "---\n"
        + digest
        + "\n---\n"
    )


def _overall_from_claims(claims: list) -> Literal["PASS", "FLAG", "UNKNOWN"]:
    """Derive the report-level verdict from per-claim statuses."""
    if any(
        c.get("status")
        in ("UNSUPPORTED", "CONTRADICTED", "MISQUOTED", "INTERNAL_CONFLICT")
        for c in claims
    ):
        return "FLAG"
    return "PASS"


# Cues in an LLM "UNSUPPORTED" reason that say "the figures exist but the
# claim attaches them to the wrong thing" — the deterministic anchor must
# surface these as MISQUOTED instead of silently grounding them (AMZN
# 2026-09-09: composite_rank "swaps the 92% and 58% labels between A and e";
# T1 265.03 vs the 265.97 the same report cites).
_MISQUOTE_CUES = re.compile(
    r"transpos|swap(s|ped|ping)?|attribut|belongs?|not the (metric|same|right)|"
    r"actually (the|belongs)|revers|confus|mislabel|wrong (label|metric|name|"
    r"entity|subject)|really (the|belongs)|the report (mixes|flips|confus)",
    re.I,
)
# A claim that ASSERTS a series is unavailable is supported by that series'
# absence: "the effective fed funds rate / RRP series returned no fresh
# evidence this run, so both are unavailable" was flagged UNSUPPORTED for
# having no EFFR/RRP leaf - but the prompt REQUIRES saying "unavailable"
# instead of quoting a recalled value, so the absence IS the support (AMKR
# 2026-09-14 news.md, same shape on AMZN).
_UNAVAILABLE_CUES = re.compile(
    r"unavailable|no fresh evidence|not surfaced|no data|no leaf|could not be"
    r"|did not surface|absent from the",
    re.I,
)

# The mandated SIGNAL SYNTHESIS rule (all four analyst prompts) requires the
# report to name the signals it weighed, say which it favoured and why. That is
# a methodological judgment, not a claim about the external world - no leaf can
# hold it - so the LLM pass flags it UNSUPPORTED (MSFT 2026-09-16 17:49 news.md:
# "note inputs were analyst-supplied fractions so treat directionally advisory
# only"). The exemption is deliberately narrow: the weighting verb must take one
# of the analyst's OWN signals as its object AND sit beside a comparative or
# explanatory token, so a world-claim that merely contains the word is untouched
# ("risk-weighted assets are higher this quarter", "the index is cap-weighted
# toward tech"). "risk" is left out of the objects for exactly that reason.
_WEIGHT_VERB_RE = re.compile(r"(?i)\bweigh(?:ed|ing|s)?\b|\bweight(?:ed|ing|s)?\b")
_SIGNAL_OBJECT_RE = re.compile(
    r"(?i)\b(?:signals?|factors?|evidence|technicals?|fundamentals?|news|"
    r"sentiment|regime|catalysts?|momentum|valuation|quality|flow|breadth|"
    r"thesis|inputs?|reads?)\b"
)
_WEIGHT_COMPARATIVE_RE = re.compile(
    r"(?i)\b(?:more|most|less|least|greater|greatest|higher|heaviest|heavier|"
    r"over|toward|towards|because|since|given|favou?r\w*|prioriti[sz]\w*|"
    r"dominant|primary|secondary|emphasis|emphasi[sz]\w*|leaned)\b"
)
_WEIGHTING_WINDOW = 60


def _is_weighting_statement(claim: str) -> bool:
    """Is this claim the mandated statement of which signal was weighted, why?"""
    text = claim or ""
    for m in _WEIGHT_VERB_RE.finditer(text):
        window = text[max(0, m.start() - _WEIGHTING_WINDOW): m.end() + _WEIGHTING_WINDOW]
        if _SIGNAL_OBJECT_RE.search(window) and _WEIGHT_COMPARATIVE_RE.search(window):
            return True
    return False


def _parse_verdict(text: str, report_name: str) -> ReportVerification:
    """Parse the rendered/tool response into a ReportVerification."""
    if not text or not text.strip():
        return ReportVerification(report=report_name, overall="UNKNOWN")

    def _build(data: dict) -> ReportVerification:
        claims = data.get("claims") if isinstance(data.get("claims"), list) else []
        if "overall" not in data or data["overall"] not in ("PASS", "FLAG", "UNKNOWN"):
            data["overall"] = _overall_from_claims(claims)
        return ReportVerification.model_validate({"report": report_name, **data})

    try:
        data = json.loads(text)
        if isinstance(data, dict) and "claims" in data:
            return _build(data)
    except (ValueError, TypeError):
        pass
    # Free-text fallback: a markdown-fence JSON (the same repair the
    # structured path uses when the provider answers in plain text).
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        try:
            return _build(json.loads(m.group(1)))
        except (ValueError, TypeError):
            pass
    logger.warning("report_verifier: could not parse verdict for %s", report_name)
    return ReportVerification(report=report_name, overall="UNKNOWN")


# ---------------------------------------------------------------------------
# Numeric anchoring (post-LLM, deterministic; shared tolerance w/ repro_check)
# ---------------------------------------------------------------------------


def _anchor_claims(
    verification: ReportVerification,
    evidence_dec: set,
    sentiment_anchor: float | None = None,
) -> ReportVerification:
    """Reconcile claim verdicts with the deterministic figure check.

    The LLM's number-matching is unreliable (verbatim-vs-tolerance); the
    anchor makes the verdicts agree with ``repro_check --evidence``:
    - UNSUPPORTED whose figures ARE in evidence -> GROUNDED (LLM missed it).
    - CONTRADICTED whose figures are ALL in evidence -> UNSUPPORTED (the
      numeric layer would not call it a contradiction; keeps the flag, at
      lower severity).
    - CONTRADICTED with a figure absent from evidence stays CONTRADICTED
      (a genuine value mismatch).
    Non-numeric claims are left to the LLM verdict (the deterministic
    layer cannot judge them).
    """
    anchored: list[VerifierClaim] = []
    for c in verification.claims:
        decs = _float_tokens(c.claim)
        if c.status == "UNSUPPORTED" and _UNAVAILABLE_CUES.search(c.claim or ""):
            # The claim says a series is absent - the missing leaf is the
            # support, not a gap in it.
            anchored.append(
                VerifierClaim(
                    claim=c.claim,
                    status="GROUNDED",
                    reason=(c.reason or "") + " [anchored: the claim asserts the series is unavailable, which the absent leaf corroborates]",
                )
            )
            continue
        score_nums = _sentiment_claim_numbers(c.claim or "") or list(decs)
        if (
            c.status == "UNSUPPORTED"
            and sentiment_anchor is not None
            and score_nums
            and _SENTIMENT_SCORE_CLAIM_RE.search(c.claim or "")
            and all(abs(d - sentiment_anchor) <= _SENTIMENT_BAND for d in score_nums)
        ):
            # The 0-10 headline score is the prompt's own rescale of
            # computed_score, so no leaf prints it (AMZN 9.5/10 against an
            # anchor of 10.0; IEI ~0/10 against 0.0).
            anchored.append(
                VerifierClaim(
                    claim=c.claim,
                    status="GROUNDED",
                    reason=c.reason
                    + " [anchored: the prompt's mandated 0-10 rescale of "
                    f"computed_score is {sentiment_anchor:.1f} +/-{_SENTIMENT_BAND}]",
                )
            )
            continue
        if c.status == "UNSUPPORTED" and not decs and _is_weighting_statement(c.claim):
            # A stated weighting is a methodological judgment, not a claim about
            # the world (the owner's decision, 2026-09-17). Only the statement
            # itself is exempt: a weighting claim that also cites figures the
            # evidence lacks keeps its flag.
            anchored.append(
                VerifierClaim(
                    claim=c.claim,
                    status="GROUNDED",
                    reason=(c.reason or "")
                    + " [anchored: a stated weighting is a methodological "
                    "judgment, not a claim about the external world]",
                )
            )
            continue
        if c.status == "UNSUPPORTED" and decs and all(_matches(d, evidence_dec) for d in decs):
            if _MISQUOTE_CUES.search(c.reason or ""):
                # The figures exist but the LLM said the claim misuses them
                # (wrong label / subject / transposition). Keep it highly
                # visible instead of silently grounding a misuse.
                anchored.append(
                    VerifierClaim(
                        claim=c.claim,
                        status="MISQUOTED",
                        reason=c.reason
                        + " [anchored: figures ARE in tool evidence but the "
                        "claim may attach them to the wrong label/context - "
                        "verify attribution]",
                    )
                )
                continue
            anchored.append(
                VerifierClaim(
                    claim=c.claim,
                    status="GROUNDED",
                    reason=c.reason + " [anchored: figures match tool evidence]",
                )
            )
            continue
        if c.status == "CONTRADICTED" and decs and all(_matches(d, evidence_dec) for d in decs):
            anchored.append(
                VerifierClaim(
                    claim=c.claim,
                    status="UNSUPPORTED",
                    reason=c.reason
                    + " [anchored: figures ARE in tool evidence; not a numeric contradiction]",
                )
            )
            continue
        anchored.append(c)
    if verification.overall == "UNKNOWN":
        # No claims / verifier could not run: never upgrade to a verdict.
        return ReportVerification(report=verification.report, claims=anchored, overall="UNKNOWN")
    overall = (
        "FLAG"
        if any(
            c.status in ("UNSUPPORTED", "CONTRADICTED", "MISQUOTED", "INTERNAL_CONFLICT")
            for c in anchored
        )
        else "PASS"
    )
    return ReportVerification(report=verification.report, claims=anchored, overall=overall)


def _stem_overall(
    anchored: ReportVerification,
    claims: list[VerifierClaim],
    *,
    deterministic_triples: int = 0,
) -> Literal["PASS", "FLAG", "UNKNOWN", "NUMERIC_ONLY"]:
    """The stem's verdict, keeping the deterministic half visible.

    ``UNKNOWN`` must mean "nothing ran". When the LLM verdict could not be
    produced or parsed but the deterministic layer DID examine the report's
    figures - ``deterministic_triples`` is the size of the typed registry it
    extracted - the honest label is ``NUMERIC_ONLY``: the prose is unverified,
    the figures are not. Measured 2026-09-16 on a 4-symbol batch: market came
    back UNKNOWN on two symbols whose figures HAD been extracted and found
    consistent, and a consumer could not tell that from a verifier that never
    started. A stem with no extractable figure stays UNKNOWN: there the
    numeric layer really has nothing to say.

    The LLM's own verdict is never upgraded here: ``_anchor_claims`` already
    refuses to turn UNKNOWN into a verdict, and this only names the provenance
    of the checks that did run.
    """
    if any(
        c.status in ("UNSUPPORTED", "CONTRADICTED", "INTERNAL_CONFLICT")
        for c in claims
    ):
        return "FLAG"
    if anchored.overall == "UNKNOWN":
        return "NUMERIC_ONLY" if deterministic_triples else "UNKNOWN"
    return anchored.overall


# ---------------------------------------------------------------------------
# Internal-consistency (cross-claim) check — deterministic
# ---------------------------------------------------------------------------

# Metric label -> regex to locate its numeric value(s) in text. Covers the
# load-bearing metrics the analyst may quote from multiple vendors (the JPM/
# GS/TJX 2026-09-08 batch: DCF fair value 80.76 vs 80.71, EPS 5.81 vs 4.79,
# market cap 141.8B vs 145.3B, ROE 53.92 vs 59.77 — all "matched some leaf"
# individually, so the per-claim anchor could not see the conflict).
def _cluster_value_tokens(raw: list[str], rel: float = 0.001) -> set[str]:
    """Distinct values behind printed tokens, merging reprints within ``rel``.

    One number printed at two precisions is ONE number: LRCX 2026-09-14
    market.md carries the chandelier stop as 306.033 (body) and 306.0336
    (summary), a 0.0002% drift that an exact-string set read as two
    conflicting stops.
    """
    clusters: list[float] = []
    out: set[str] = set()
    for tok in sorted(raw, key=lambda t: float(t) if _is_number(t) else 0.0):
        try:
            value = float(tok)
        except ValueError:
            out.add(tok)
            continue
        if clusters and abs(value - clusters[-1]) / max(abs(clusters[-1]), 1e-9) <= rel:
            continue
        clusters.append(value)
        out.add(tok)
    return out


def _is_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def _value_in(raw: str, line: str) -> bool:
    """Is this figure in the line as a figure (not a substring of another)?

    Plain ``raw in line`` matches '22.1' inside '122.15', which let a
    disclosure about one block satisfy the check for a value from another.
    """
    if not raw:
        return False
    return re.search(rf"(?<![\d.]){re.escape(raw)}(?![\d])", line) is not None


# A line that names the difference between two quoted values. The verifier
# exempts a same-metric pair only when such a line also carries one of the
# flagged values - i.e. the report flagged the conflict itself.
# The bare word "conflict" is NOT a marker: a report that says its two
# current-ratio values conflict (WDC 2026-09-10, 10.87 vs 1.329) has flagged a
# real discrepancy, not explained one away. Only a stated BASIS difference
# exempts - that is a legitimate pair, not an error.
_DISCLOSURE_MARKERS = re.compile(
    r"(?i)\bdiffers?\b|\bdifferent\b[^.\n]{0,24}\bbasis\b"
    r"|\bdo\s+not\s+(?:mix|combine)\b|\bnot\s+be\s+combined\b"
    r"|\bquote\s+(?:both|each)\b|\blabel\s+(?:each|them|separately)\b"
    r"|\blabel basis\b|\bbasis differs\b|\bseparate(?:ly)?\s+basis\b"
    r"|\btreat\s+as\s+a\s+range\b|\bunit[- ]mixed\b|\bcross-?currency\b"
    r"|\bnot conflicting\b|\bdifferent\b[^.\n]{0,20}\bframeworks?\b"
    r"|simple\s+mean\s+of\s+TR|\bswing\s+(?:tool|model)s?\b|\bheadline\s+ATR\b"
    r"|\bverified\s+snapshot\b"
    # "separate ATR basis" (JCI), "conflicting bases" (JCI ROE row),
    # "as printed" / "history" (AMKR's FY series beside the latest quarter)
    r"|\bseparate\b[^.\n]{0,20}\bbasis\b|conflicting\s+bases|\bas\s+printed\b|\bhistory\b"
    # A report that STATES the disagreement has done its job (the analyst
    # prompt requires quoting both producers and flagging it): SKHY 2026-09-14
    # "This conflicts with get_ratios ROE 35.57%". Generalised count too -
    # SKHY/VST print three bases, not two.
    r"|\bconflicts?\s+with\b|\b(?:two|three|four|five|six)\b[^.\n]{0,20}\bbases?\b"
    # A report that names the CAUSE and says which value is right has
    # reconciled: MSFT 2026-09-15 fundamentals.md writes "Same metric, two
    # values (conflict): current ratio 3.74 ... vs 1.23 ... The 3.74 is the
    # non-current-row artifact; 1.23 is the correct current-row basis" - the
    # vendor tool passed the wrong balance-sheet rows.
    r"|\bmislabell?ed\b|\bnon[- ]current\b|\bwrong\s+row\b"
)

def _marker_beside_a_value(para: str, flagged: set[str]) -> bool:
    """Is a disclosure marker printed in the same unit as a flagged value?

    Paragraph scope alone is too coarse: a summary TABLE is one paragraph, so a
    marker on its current-ratio row exempted the ROE quartet in the same table
    (MSFT 2026-09-15 fundamentals.md, where the report names the cause for the
    ratio and, two rows later, says "quote all four; no reconciliation
    offered" for ROE). A character window is too fine the other way - a prose
    reconciliation clause names the values first and the basis at the end of a
    long sentence. The unit is the sentence (or the table row), which is where
    a reader sees the disclosure sitting next to the figures it explains.
    """
    if "|" not in para:
        # Prose: the reconciliation clause and the figures it covers are one
        # statement, however long the sentence runs.
        return bool(_DISCLOSURE_MARKERS.search(para))
    # A TABLE is one paragraph but many statements: the marker must share the
    # ROW with the value it explains. Cells are not units - the summary row
    # "| ROE | 31.57% / 34.88% / ... | five bases - quote all |" puts the label,
    # the values and the disclosure in three different cells (SIMO 2026-09-14
    # fundamentals.md).
    for row in para.splitlines():
        if _DISCLOSURE_MARKERS.search(row) and any(_value_in(f, row) for f in flagged):
            return True
    return False


# A metric's value can sit inside ANOTHER metric's list: SMCI 2026-09-14
# market.md quotes `get_vif_read`'s "rsi 5.4 HIGH>5" - a VIF SCORE, not an RSI
# reading - beside the real RSI 50.71, and the rsi pair reader saw two RSI
# values. A value whose every occurrence sits in the foreign context is not a
# reading of this metric.
_METRIC_CONTEXT_REJECT: dict[str, re.Pattern] = {
    # `\bvif\b` alone cannot match inside `get_vif_read` (the underscore is a
    # word char) - the same trap `_VIF_MARKER_RE` documents.
    "rsi": re.compile(r"(?i)\bvif\b|\bvif[\s_]*read\b|get_vif_read"),
}


def _value_context_rejected(label: str, raw: str, line: str) -> bool:
    """Is every occurrence of this value sitting in another metric's context?"""
    rx = _METRIC_CONTEXT_REJECT.get(label)
    if rx is None or not line or not raw:
        return False
    occurrences = list(re.finditer(re.escape(raw.strip()), line))
    if not occurrences:
        return False
    return all(
        # 80 chars, not 40: the tool name starts the clause -
        # "`get_vif_read` on [rsi, mom, std, vol, range] returns **rsi 5.4 ..."
        # is 50-odd chars before the score.
        rx.search(line[max(0, m.start() - 80): m.start()]) for m in occurrences
    )


def _disclosed_pair(report_text: str, regex: re.Pattern, flagged: set[str]) -> bool:
    """Did the report flag this difference itself?

    Scoped to the PARAGRAPH (a blank-line block), not the line: the
    disclosure is usually a sentence right beside the figures ("Do not mix
    their targets or stops", HPE market.md; "Label basis: ...", AMAT
    market.md), and a line-only scope missed those. A stated range
    ("0.1187–0.12") or a bracketed alternate ("19.97 (21.12)") is disclosure
    too - the report presents the two readings as one value with a spread.
    """
    for para in re.split(r"\n\s*\n", report_text):
        if not (regex.search(para) and any(_value_in(f, para) for f in flagged)):
            continue
        if _marker_beside_a_value(para, flagged):
            return True
        pair = sorted(flagged)
        for i, a in enumerate(pair):
            for b in pair[i + 1:]:
                dash = rf"(?<![\d.]){re.escape(a)}[\s]*[\u2013-][\s]*{re.escape(b)}(?![\d])"
                paren = rf"(?<![\d.]){re.escape(a)}\s*\(\s*{re.escape(b)}\s*\)"
                if re.search(dash, para) or re.search(paren, para):
                    return True
    return False


# Metrics whose producers print DIFFERENT UNITS for the same name. Two unit
# classes are two constructs; only same-unit values are claims about each other.
_UNIT_SCOPED_METRICS = frozenset({"vrp"})


def _unit_after(line: str, raw: str) -> str:
    """The unit token printed immediately after a value, "" when none."""
    if not line or not raw:
        return ""
    m = re.search(re.escape(raw.strip()) + r"\s*(%|pp\b|\u00d7|x\b)?", line, re.I)
    return (m.group(1) or "").lower() if m else ""


_INTERNAL_CONFLICT_METRICS: dict[str, tuple[re.Pattern, float]] = {
    # Default tolerance 1%: vendor-consensus rounding (80.76 vs 80.75) is ONE
    # cluster; a real ratio conflict (ROE 53.92 vs 59.77) is TWO.
    "dcf fair value": (re.compile(r"dcf\s*(?:fair\s*)?value", re.I), 0.01),
    "eps ttm":(re.compile(r"\beps\s*(\(|\s)ttm\s*(?:\))?(?!\s*growth)", re.I), 0.01),
    "diluted eps": (re.compile(r"diluted\s*eps|eps\s*\(diluted\)", re.I), 0.005),
        # DELL 2026-09-10 news.md: body quoted 'EPS actual 7.04' and the
        # summary row 'EPS actual 7.00' (both labeled Finnhub, same quarter) —
        # a 0.6% dual value. Level-type metrics use a 0.5% bucket.


        "eps actual":(re.compile(r"\beps\s+actual\b", re.I), 0.005),
        # NO generic "eps estimate" entry: an EPS estimate is only comparable
        # within ONE earnings date, and this pass keys on the label alone. AMZN
        # 2026-09-16 news.md quotes 1.83 for the already-reported 2026-07-30
        # print beside 2.03 (Zacks, upcoming) and 1.95 (calendar,
        # 2026-10-29) - three estimates for two dates, each stated with its
        # own period - and the label-keyed pass paired 1.83 with 2.03 as a
        # conflict. The date-scoped ``_eps_estimate_duals`` is the check that
        # owns this metric: it flags two DIFFERENT estimates anchored to the
        # SAME date (MSFT 2026-09-10: 4.72 in the table vs 4.16 in the forward
        # calendar, both 2026-10-28) and stays silent across dates.
    "earnings power value": (re.compile(r"earnings\s*power\s*value|epv", re.I), 0.01),
    "market cap": (re.compile(r"market\s*cap|market\s*capitali[sz]ation", re.I), 0.01),
    "roe": (re.compile(r"\broe\b|return\s*on\s*equity", re.I), 0.01),
    "debt/equity": (re.compile(r"debt[-\s/]equity|\bd/e\b|debt\s*to\s*equity", re.I), 0.01),
                "200-day sma": (re.compile(r"(?<![\w-])close_200_sma(?!\s*\|)|200[-\s]?day\s+sma(?!\s*\|)", re.I), 0.01),
    "insider net": (re.compile(r"insider.{0,30}net|net.{0,15}(?:insider|buying|shares)", re.I), 0.01),
    "dividend yield": (re.compile(r"dividend\s*yield", re.I), 0.01),
    "book value": (re.compile(r"book\s*value|book\s*value/share|bvps", re.I), 0.01),
    # AMZN 2026-09-09 review-loop metrics. EXACT/price-level metrics (T1/RSI/
    # ATR/bands/surprise) use a tighter 0.5% so a real target mismatch (T1
    # 265.03 vs 265.97, a 0.35% diff masked by the 1% bucket, or macdh -1.36
    # vs -1.15) still flags.
    # The qualifier is part of the label ("EMA20 trail 481.74"): leaving it in
    # the label-to-value gap would make the value look like prose.
    "ema20": (re.compile(r"\bema\s*20\b(?:\s*(?:trail|line|band|value))?", re.I), 0.005),
        "atr":(re.compile(r"(?<![A-Za-z0-9\-])atr\b(?!\s*:\s*\d+\s*-)|average\s*true\s*range", re.I),0.005),
    # Exact price levels: a 0.35% target mismatch (T1 265.03 vs 265.97) is a
    # real conflict, so level-type metrics use a 0.1% bucket. Their values come
    # from the pair-aware reader (_METRIC_VALUE_READERS); these patterns are the
    # fallback for the "2xR" / "T 1(2R)" spellings.
    "t1": (re.compile(r"\bT1\b|2R|2xR|T\s*1\s*(?:\(|2R)", re.I), 0.0005),
    "t2": (re.compile(r"\bT2\b|3R|3xR", re.I), 0.001),
    # MU 2026-09-10 fundamentals review loop: EV/EBIT quoted at 65.2 (analyst verdict) and 66.65 (get_ratios) while the leaves show 113.91 / 113.80 - the pair must surface as one conflict.
    "ev/ebit": (re.compile(r"ev[/\s-]?ebit(?!da)", re.I), 0.01),
    "ev/ebitda": (re.compile(r"ev[/\s-]?ebitda", re.I), 0.01),
    # MU 2026-09-10 market review loop: put/call OI 3.99 (body) vs 3.39
    # (summary row) - same metric, dual value; and VRP quoted -5.24pp
    # while the summary labels it "positive".
    "pcr oi": (re.compile(r"put[/\s-]?call[^0-9]{0,12}|PCR\s*OI", re.I), 0.02),
    "vrp": (re.compile(r"VRP", re.I), 0.05),
    "macd histogram": (re.compile(r"macd\s*h|macdh|histogram", re.I), 0.005),
    "rvol": (re.compile(r"\brvol\b|relative\s*volume", re.I), 0.005),
    "williams_r": (re.compile(r"williams", re.I), 0.005),
    # "stoch" alone also matched "stochrsi" (a different oscillator) and read
    # its 0.0 as a %K conflict against the real stochK 12.42 (MU market.md
    # 2026-09-14). Only the %K spellings are the same metric.
    "stochastic": (re.compile(r"\bstoch(?:k|astic)\b(?:\s*%?\s*k)?", re.I), 0.005),
    "rsi": (re.compile(r"\brsi\b|relative\s*strength\s*index", re.I), 0.005),
    "aws growth": (re.compile(r"aws.{0,10}(?:growth|yoy)|yoy.{0,10}aws", re.I), 0.005),
    "hy oas": (re.compile(r"hy[-\s]?oas|high\s*yield.{0,20}oas", re.I), 0.005),
    "forward peg": (re.compile(r"peg|forward\s*p/e.{0,6}growth|price.{0,6}earnings.{0,6}growth", re.I), 0.005),
    "ttm p/e": (re.compile(r"ttm\s*p/e|p/e\s*ttm|pe\s*ttm", re.I), 0.005),
    # MU 2026-09-09 review-loop metrics: Altman Z 24.60 (body) vs 25.70
    # (summary + get_analyst_verdict leaf 25.70) — a provider-sourced score
    # must not be quoted at two values in one report.
    "altman z": (re.compile(r"\baltman\s*z\b|altman\s*z-score", re.I), 0.005),
    # IGV 2026-09-09 review loop: the news.md asserted both "Yes 0%" and
    # "Yes 93%" for the same "Fed rate cuts in 2026" Polymarket event, with
    # no prediction-market leaf. A market-implied probability must not be
    # quoted at two values in one report.
    "fed cuts 2026": (re.compile(r"fed\s*rate?\s*cuts?\s+in\s+2026|no\s*fed\s*rate\s*cuts|will\s*fed\s*rate\s*cuts", re.I), 0.02),
# DELL 2026-09-10 review loop: scenario-DCF bear was quoted as 87.75
    # in the body and87.60 in the summary table — a transcription slip, not a real
    # scenario shift. Level-type (exact price) metrics use a 0.1% bucket
    # Only the "bear" label is pair-safe — "bear" is the FIRST leg of the slash list,
    # so "bear": $N  is the same dollar in both the body and the summary row.

    # The trailing "\d" used to be consumed by the label match itself, so the
    # value lost its leading digit: "bear 171.38" was read as "71.38" and the
    # same number then looked like two conflicting scenarios (MU fundamentals.md
    # 2026-09-14: 71.38/171.38, 94.96/194.96, 27.07/227.07). A lookahead keeps
    # the digit in the value.
    "scenario dcf bear": (re.compile(r"(?i)(?:scenario[\s-]*dcf.{0,60}?bear\b|bear\s*(?:\||:|\$|(?=\d)))", re.I),0.001),
    "scenario dcf base": (re.compile(r"scenario[\s-]*dcf.{0,40}?base\b|base\s*(?:\||:|=|/|\$|(?=\d)|$)", re.I), 0.001),
    # The bare "bull" alternative needs a scenario neighbour: a REGIME row
    # ("| Regime | BULL 0.7255, vol NORMAL ... |") also carries the word, and
    # its state score was read as a second scenario-DCF bull (MU/SNDK/DELL
    # fundamentals.md 2026-09-14).
    "scenario dcf bull": (re.compile(r"scenario[\s-]*dcf.{0,40}?bull\b|(?:bear|base)[^\n]{0,40}?bull\s*(?:\||:|=|/|\$|(?=\d)|$)", re.I), 0.001),
    "beta": (re.compile(r"\bbeta\b", re.I), 0.05),
    "cash conversion": (re.compile(r"cash\s*conversion|cash_conversion|ocf\s*/\s*ni", re.I), 0.02),
    # WDC 2026-09-10 fundamentals review loop: current ratio 10.87
    # (get_balance_sheet_health) vs 1.329 (vendor currentRatio) in one
    # report - a computed-vs-provider ratio conflict must flag.
    "current ratio": (re.compile(r"current\s*ratio|\bcurrentRatio\b|\bCR\b", re.I), 0.20),
}

# A figure in the report, with optional K/M/B/T suffix, e.g. "80.76",
# "$80.60", "79.78B", "5.7B", "1,166,000,000". Used to extract the numeric
# value attached to a metric. Three hard-won details (MU/SNDK/DELL/SKHY
# 2026-09-14 verifier run, 78 INTERNAL_CONFLICT rows of which the majority
# were capture artifacts):
#   * THOUSANDS SEPARATORS count as one figure. Without them "$28,243,000,000"
#     was read as "28" (the digits before the first comma), which is how
#     'diluted eps' came to "conflict" at 24.67 vs 28 and 'market cap' at
#     "**1" — a fragment of "$1,166,000,000,000".
#   * A digit carrying an R-multiple suffix ("3R", "2xR") is NOT a figure:
#     reading the "3" of "3R targets ..." as a price is what let a wrong 3R go
#     uncompared (MU 2026-09-09 review loop). A unit suffix must end its token,
#     so "1.25Tonnes" is not 1.25T.
#   * The boundary check belongs on the UNIT, not on the number: requiring a
#     non-letter after the figure made "10.52pp" backtrack into "10" (the
#     SNDK/SKHY VRP prints).
_DOLLAR_RE = re.compile(
    r"(?<![\w,.])\$?\s*(\d[\d,]*(?:\.\d+)?)(?:\s*([KMBkmbt])(?![A-Za-z]))?(?![xX]?R\b)"
)

# Unit suffix -> multiplier. T joined the set because the reports write
# "$1.25T" beside "$1,250,373,926,912" and the two must land in ONE cluster.
_DOLLAR_UNITS = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}

# Formatting plus a bounded vocabulary of LINK words may sit between a metric
# label and its OWN figure. Anything else is prose or another metric's label, so
# the figure after it belongs to that other thing: "...$24.67 diluted EPS; price
# 919.97 is a forming bar" must not read the price as the EPS ("price" is not a
# link word), while "DCF fair value is $80.76", "DCF value at 79.60" and
# "Current ratio vendor 1.329" must still read their values ("is", "at",
# "vendor" are).
_FILLER_CHARS = r"[\s*_`:=~$|()\[\]{},/+\-\u2013\u2014]*"
_VALUE_LINK_WORDS = (
    r"(?:is|are|was|were|be|at|of|to|for|near|about|around|approx|approximately|"
    r"reached|printed|quoted|quotes|reads|read|sits|stood|estimated|"
    r"vendor|vendors|provider|finnhub|fmp|consensus|screener|company|reported|"
    r"per|from|as|tool|leaf|source|basis)"
)
_LABEL_TO_VALUE_FILLER_RE = re.compile(
    rf"^{_FILLER_CHARS}(?:{_VALUE_LINK_WORDS}{_FILLER_CHARS}){{0,2}}$", re.I
)

# A figure introduced by a comparison is a THRESHOLD, not the metric's value:
# "rvol 0.6390 ... (>= 1.3 = high)" must not read 1.3 as a second RVOL print.
_THRESHOLD_BEFORE_RE = re.compile(r"[<>\u2264\u2265]\s*$")

# A figure that is really part of a DATE must not read as the metric's value:
# "(09-21)" gave vrp a third cluster of 9.0 and "2026-06-30" gave ROE one of
# 6.0 (AMZN market.md / SMCI fundamentals.md 2026-09-14), each splitting one
# real value into a phantom conflict.
_DATE_TAIL_BEFORE_RE = re.compile(r"\d{2,4}-\d{0,2}$")
_DATE_HEAD_AFTER_RE = re.compile(r"^-\d{2}(?!\d)")


def _date_fragment_around(gap: str, after: str) -> bool:
    """Is the value about to be read a fragment of a YYYY-MM-DD / MM-DD token?"""
    return bool(_DATE_TAIL_BEFORE_RE.search(gap) or _DATE_HEAD_AFTER_RE.match(after))


def _is_date_fragment_in(raw: str, line: str) -> bool:
    """Is this figure a component of a date token elsewhere in the line?

    The table-cell / slash-pair readers return before the gap-based guard can
    run, so "| P/E / P/B / ROE | 10.82 / 1.67 / 15.40% (TTM 2026-06-30) |"
    handed ROE a second value of 6.0 read out of the date (SMCI
    fundamentals.md 2026-09-14) and split one ROE into a phantom conflict.
    """
    if not raw or not raw.isdigit():
        return False
    return bool(
        re.search(rf"\d{{2,4}}-{re.escape(raw)}(?!\d)", line)
        or re.search(rf"(?<!\d){re.escape(raw)}-\d{{2}}(?!\d)", line)
    )

# Metrics a report routinely quotes for a PEER in the same breath as the
# subject: "AMKR ... PEG 0.59 ... vs NVMI forward P/E 32.93, PEG 1.88". The
# comparand's figure is not a second reading of the subject's (AMKR
# 2026-09-14 news.md), so for these the line is cut at the comparison marker
# before values are read.
_COMPARISON_METRICS = frozenset({"forward peg", "market cap", "ttm p/e", "ev/ebit"})
_COMPARAND_SPLIT_RE = re.compile(
    r"(?i)\bvs\.?\b|\bversus\b|\bcompared\s+(?:to|with)\b|\bpeers?\b"
)
_MAG_SUFFIX_RE = re.compile(r"([BMKT])$")


def _same_with_dropped_unit(a_val: float, a_raw: str, b_val: float, b_raw: str) -> bool:
    """Same reading once a dropped magnitude suffix is restored.

    "market cap $87.8B" beside "market cap 87.8" is one figure captured twice,
    once without its unit - not two market caps (JCI 2026-09-14 sentiment.md).
    Only a suffixed/bare PAIR qualifies, so a genuine "$87.8M vs $87.8B" mix
    (both suffixed, different units) still flags.
    """
    sa = _MAG_SUFFIX_RE.search(a_raw or "")
    sb = _MAG_SUFFIX_RE.search(b_raw or "")
    if bool(sa) == bool(sb):
        return False
    bare, suffixed = (a_val, b_val) if not sa else (b_val, a_val)
    unit = _DOLLAR_UNITS.get((sb or sa).group(1).upper(), 1.0)
    return abs(bare * unit - suffixed) / max(abs(suffixed), 1e-9) <= 0.01


# A VIF (multicollinearity) row reuses the indicator label for a variance
# inflation factor — "| VIF | rsi 5.8 HIGH, mom 5.8 HIGH |" — and that number
# is not the oscillator's level (MU market.md 2026-09-14, rows 7 and 83).
_VIF_MARKER_RE = re.compile(r"\bvif\b|\bvif[\s_]*(?:read|factor)?\b|get_vif_read", re.I)

# Metrics whose value is a LEVEL (a price, a per-share figure, a dollar
# amount) rather than a rate: a percentage printed after the label is that
# metric's GROWTH or yield, not its value ("Diluted EPS +1368.5% YoY",
# "market cap +2.1% w/w").
_LEVEL_METRICS = frozenset({
    "diluted eps", "eps ttm", "eps actual", "eps estimate", "book value",
    "dcf fair value", "scenario dcf bear", "scenario dcf base",
    "scenario dcf bull", "market cap", "insider net", "200-day sma", "ema20",
})

# A label whose SAME spelling is reused by a neighbouring quantity on the same
# line, keyed to the context that gives it away: "put/call **1.49**" is the OI
# ratio while "call/put volume **0.97** (put/call **1.03**)" is the volume
# ratio, and "the 10-02 chain reads put/call 1.29" is ANOTHER expiry's ratio —
# none of them is a dual print of the first (MU market.md L30, DELL market.md
# L21, 2026-09-14).
_LABEL_CONTEXT_REJECT: dict[str, re.Pattern] = {
    "pcr oi": re.compile(r"(?i)\b(?:volume|chain)\b"),
}

# A period-qualified level metric is scoped to that period, not a second
# quoting of the same number: "Prior quarter (2026-04-30): ... Diluted EPS
# $5.24. Year-ago quarter (2025-07-31): ... Diluted EPS $1.70" are three
# quarters, and comparing them flagged DELL fundamentals.md 2026-09-14.
_PERIOD_QUALIFIER_RE = re.compile(
    r"(?i)\b(?:prior|previous|year[\s-]?ago|quarter|q[1-4]\b|fy\s*\d|ttm|yoy|qoq)\b"
)


def _segment_before(line: str, pos: int) -> str:
    """The clause the label opens, since the last sentence/segment boundary.

    A period qualifier scopes the values in ITS clause: "Prior quarter ...:
    Revenue $43,842M, Diluted EPS $5.24." qualifies that EPS, while the trailing
    "(leaf, FY26 Q4)" of an earlier clause must not reach across the ";" to
    disqualify the next one.
    """
    seg = line[:pos]
    cut = max(seg.rfind(". "), seg.rfind("; "), seg.rfind(";"), seg.rfind("|"))
    return seg[cut + 1:]

# ---------------------------------------------------------------------------
# Macro-authority gate (deterministic; SKHY 2026-09-09 review loop)
# ---------------------------------------------------------------------------
# Market-implied probabilities / macro levels must carry a TOOL leaf: the
# news-analyst prompt pins prediction markets + macro tools, but prompt-only
# is not enforced — the SKHY news.md quoted "Polymarket: no Fed rate cuts in
# 2026 = Yes 93%", "10Y at 4.78 (latest FRED print)", "RRP at 0.432B",
# "WTI 91.48" with NO get_prediction_markets / get_macro_indicators leaf in
# the tree. This gate flags a report line citing one of these authorities
# when the report-term's evidence has no leaf from the pinned tool group
# (and no leaf content carries the term).
#
# Requirement: (phrases) -> (tools that satisfy the line) -> (extra leaf terms
# that also satisfy it). Any line containing a listed phrase must have at least
# one leaf whose tool is in the set, or a leaf whose content contains a listed
# phrase (or one of the group's carriers). Otherwise the line is UNSUPPORTED -
# deterministic, independent of the LLM pass.
_MACRO_AUTHORITY_PHRASES_TOOLS: tuple[
    tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...
] = (
    (("polymarket", "prediction market"), ("get_prediction_markets",), ()),
    (
        ("no rate cuts", "no fed rate cuts", "cut probability", "hike probability",
         "fed watch"),
        ("get_prediction_markets", "get_fed_watch"),
        (),
    ),
    # The MEETING is not a market-implied figure: a dated Fed-decision line is
    # anchored by the central bank itself, which the analyst's own news leaves
    # name. IEI 2026-09-15 sentiment.md's "FOMC decision on 2026-09-16" was
    # flagged while that analyst's news_headlines leaf holds UBS's "expects the
    # Federal Reserve to raise its policy rate by 25 basis points on September
    # 16" and Apollo's "expects the Federal Open Market Committee to raise
    # interest rates at its mid-September meeting". A PROBABILITY/strike-price
    # claim stays in the strict group above - those still need the pinned tool.
    (
        ("fomc",),
        ("get_prediction_markets", "get_fed_watch"),
        ("federal open market committee", "federal reserve", "fed decision",
         "fed meeting"),
    ),
    # TGA balance != RRP: a get_tga_balance leaf must not satisfy an RRP
    # claim (SKHY 2026-09-09: "RRP at 0.432B" passed the old mapping because
    # TGA was called). RRP/reverse-repo need get_macro_indicators or a leaf
    # whose content actually carries the term.
    (("rrp", "reverse repo"), ("get_macro_indicators",), ()),
    (("10y", "10-year"), ("get_macro_indicators", "get_treasury_curve"), ()),
    (("wti", "oil price", "crude"), ("get_macro_indicators", "get_economic_calendar"), ()),
)


# Extra scale: a *_window / (18) / 30d -style label can sit between a metric
# label and its value; 1 line = up to 40 chars after the label.
_METRIC_WINDOW = 40


def _macro_authority_gate(report_text: str, evidence: dict, analyst_key: str) -> list[VerifierClaim]:
    """Deterministic: market-implied/macro terms need a matching tool leaf.

    The news prompt's MACRO DATA PROVENANCE pins (the sentiment prompt pins the
    same header for its 10-year leaf) put the tools in policy, but prompt policy
    alone is not enforced: the SKHY 2026-09-09 news.md carried Polymarket 93%
    no-cut, 10Y 4.78 FRED print and WTI 91.48 with no
    ``get_prediction_markets`` / ``get_macro_indicators`` leaf anywhere in the
    document. The LLM pass may ground the wording against other leaves; this
    gate holds each such line to the pinned tool group regardless. Advisory:
    adds UNSUPPORTED claims, never edits the report.
    """
    if not report_text:
        return []
    leaves = evidence.get(analyst_key) or []
    if not isinstance(leaves, list):
        leaves = []
    leaf_tools = {str(leaf.get("tool") or "") for leaf in leaves if isinstance(leaf, dict)}
    leaf_text = "\n".join(str(leaf.get("content") or "") for leaf in leaves if isinstance(leaf, dict))
    leaf_text_low = leaf_text.lower()
    out: list[VerifierClaim] = []
    for line in report_text.splitlines():
        low = line.strip().lower()
        for phrases, tools, carriers in _MACRO_AUTHORITY_PHRASES_TOOLS:
            present = [p for p in phrases if p in low]
            if not present:
                continue
            # Satisfied when a pinned tool leaf exists, OR a leaf content
            # itself carries a listed phrase (e.g. a fetched article) or one of
            # the group's carrier terms.
            satisfied = bool(leaf_tools & set(tools)) or any(
                p in leaf_text_low for p in (*present, *carriers)
            )
            if not satisfied:
                out.append(
                    VerifierClaim(
                        claim=line.strip(),
                        status="UNSUPPORTED",
                        reason=(
                            f"cites '{present[0]}' without a {sorted(tools)} leaf (tool not "
                            "called, term absent from this analyst's evidence) - recalled "
                            "macro figure (SKHY 2026-09-09 review loop)."
                        ),
                    )
                )
            break  # one authority class per line is enough
    return out


def _table_legs(cell: str) -> list[str]:
    """Split a table cell into its ``/``-separated legs.

    **One separator rule, applied to BOTH cells of a row.** The ordinal that
    selects a value only means anything if the label cell and the value cell are
    cut the same way, so the choice is made once, from the label cell's own
    shape, and reused.

    A spaced ``/`` is the separator these tables use; a bare ``/`` inside a label
    is part of the label. Splitting ``P/E / EV/EBIT / EV/EBITDA`` on every ``/``
    would make ``P/E`` two labels and shift every ordinal after it - which is
    exactly the defect this fixes: the EV/EBITDA value was read as EV/EBIT on
    LULU 2026-09-15. When no spaced separator exists the cell is cut on the bare
    ``/`` (``bear/base/bull``), which is the other shape these rows use.
    """
    parts = [p for p in re.split(r"\s+/\s+", cell)]
    if len(parts) < 2:
        parts = cell.split("/")
    return [p.strip() for p in parts]


def _table_cell_pair_value(line: str, m: re.Match) -> tuple[str, float] | None:
    """The label's own leg when its table cell holds no figure of its own.

    A two-cell row such as ``| Net Income / Diluted EPS | $28,243,000,000 /
    $24.67 |`` lists the labels in one cell and their values, in the same
    order, in the next. Reading the first figure of the value cell would bind
    the net income to the EPS, so the label's ordinal inside its own cell
    selects the matching leg.

    **The ordinal is the label's POSITION among the label cell's legs**, not the
    number of ``/`` before the match. Those differ in three ways, each of which
    produced a false INTERNAL_CONFLICT on a real tree:

    * a ``/`` inside a label (``P/E``) is not a separator, and counting it
      shifted EV/EBIT onto the EV/EBITDA value (LULU 2026-09-15: 5.50 read
      beside 4.40);
    * a label phrase that spans two legs (``Scenario DCF bear/base``) matched
      with nothing before it, so the ordinal came out 0 and ``base`` was read
      as the BEAR value (LULU 2026-09-15: 173.58 read beside 132.5);
    * a value leg naming a second metric (``2.90 (grey); Ohlson -7.2461``)
      handed over that metric's number (JCI 2026-09-17: Altman Z 2.90 read
      beside the Ohlson score 7.2461).

    So: cut both cells the same way, take the leg the label occupies, and read
    **its first figure** - a leg that names another metric cannot donate it.
    """
    if "|" not in line:
        return None
    cells = line.split("|")
    pos = 0
    for idx, cell in enumerate(cells):
        if pos <= m.start() and m.end() <= pos + len(cell):
            if _DOLLAR_RE.search(cell):
                return None  # the label cell has its own figure: normal path
            if idx + 1 >= len(cells):
                return None
            label_legs = _table_legs(cell)
            if len(label_legs) < 2:
                return None
            # Which leg the label occupies. The match's LAST character decides,
            # because these phrases read `<context> <label>`: the regex
            # `scenario[\s-]*dcf.{0,40}?bull` legitimately matches the whole
            # `Scenario DCF bear/base/bull` cell, and the metric named is the
            # TAIL - `bull` (leg 2), not the `bear` it started on. Reading the
            # span's start bound `base`/`bull` to the BEAR value on LULU
            # 2026-09-15 (173.58 beside 132.5, and 249.05 beside 132.5).
            #
            # The span is shifted into CELL coordinates: `m` indexes the whole
            # LINE, and `pos` is where this cell starts in it.
            m_end = m.end() - pos - 1
            ordinal = None
            cursor = 0
            for i, leg in enumerate(label_legs):
                start = cell.find(leg, cursor)
                if start < 0:
                    continue
                end = start + len(leg)
                cursor = end
                if start <= m_end < end:
                    ordinal = i
                    break
            if ordinal is None:
                return None
            value_legs = _table_legs(cells[idx + 1])
            if len(value_legs) < 2:
                return None
            ordinal = min(ordinal, len(value_legs) - 1)
            leg = value_legs[ordinal]
            # The FIRST figure of the leg: a later one belongs to whatever the
            # leg goes on to name. A date fragment is not a figure.
            for x in _DOLLAR_RE.finditer(leg):
                raw = x.group(0)
                if _is_date_fragment_in(raw, line):
                    continue
                try:
                    return raw, float(raw.replace(",", ""))
                except ValueError:
                    continue
            return None
        pos += len(cell) + 1
    return None


# Digits replaced by a placeholder glyph instead of being written. Two
# variants reached the 2026-09-16 batch:
#   IEI market.md (146 tokens) - an underscore: "rsi=23._15" for the leaf's
#   rsi=23.15, "pct_b=_0219" for 0.0219, "GARCH cond **_._**04%" for 3.04%.
#   VTV sentiment.md (20 tokens) - dots/ellipsis: "+0..85", "≈9..25/10",
#   "-026-09-15" for 2026-09-15, "AUM $16..39T".
# The lookbehind keeps tool names out ("close_50_sma" is not masked), and a
# ".." between digits is only a placeholder when no ISO date sits beside it -
# "2026-09-07..2026-09-14" is a news RANGE (JCI/IEI news stems).
_DIGIT_MASKED_NUMBER_RE = re.compile(
    r"(?:\._\d|_\.\d|(?<![\w])_\d[\d.,]*(?![\w])"
    r"|[=\u2248+\-\u2212]\s*[\.\u2026]{1,3}\d"
    r"|\d[\.\u2026]{2,3}\d)"
)
_ISO_DATE_RANGE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _masked_numbers(text: str) -> list[str]:
    """Digit-placeholder tokens, excluding ISO date ranges."""
    out: list[str] = []
    src = text or ""
    for m in _DIGIT_MASKED_NUMBER_RE.finditer(src):
        token = m.group(0)
        if ".." in token and _ISO_DATE_RANGE_RE.search(
            src[max(0, m.start() - 30): m.end() + 30]
        ):
            continue
        out.append(token)
    return out


# A label run joined by slashes ("bear/base/bull") binds, in order, to the
# value run that follows it ("$87.75 / $115.51 / $240.53"): the DELL
# 2026-09-14 fundamental body quoted the same scenario set twice, and reading
# the first figure of the value list for every label made all three look like
# conflicts with themselves.
_SLASH_LABEL_TAIL_RE = re.compile(r"([A-Za-z%][\w%]*)\s*/\s*$")
_SLASH_HEAD_RE = re.compile(r"\s*/\s*")


def _slash_pair_value(line: str, m: re.Match) -> tuple[str, float] | None:
    """The label's own leg when labels and values are both slash-separated."""
    before = line[:m.start()]
    ordinal = 0
    cell_start = before.rfind("|") if "|" in line else -1
    if cell_start >= 0:
        # In a table row the label cell IS the slash list, so the ordinal is
        # simply how many labels precede this one in that cell. The tail
        # regex below needed the preceding label to look like a label and
        # silently returned ordinal 0 for "| Tranche stop / T1 / T2 |",
        # handing T1 the stop's value (SKHY 2026-09-14 market.md: 145.51 read
        # as a T1 target alongside the real 203.34).
        ordinal = before.count("/", cell_start)
    else:
        pos = len(before)
        while True:
            mm = _SLASH_LABEL_TAIL_RE.search(before[:pos])
            if mm is None:
                break
            pos = mm.start(1)
            ordinal += 1
    after = line[m.end():]
    if "|" in line:
        # A table row: the figures that follow belong to the cell AFTER the
        # label's own ("| RSI / MACD / ATR(14) | 60.16 / ... |" — the 14 of
        # ATR(14) is not the RSI leg).
        rest_of_line = line[m.end():]
        bar = rest_of_line.find("|")
        if bar >= 0:
            after = rest_of_line[bar:]
    if ordinal == 0 and not _SLASH_HEAD_RE.match(after):
        return None
    legs: list[tuple[str, float]] = []
    rest = after
    for idx in range(ordinal + 1):
        mm = _DOLLAR_RE.search(rest)
        if mm is None:
            return None
        num_s, unit = mm.group(1), (mm.group(2) or "")
        try:
            value = float(num_s.replace(",", "")) * _DOLLAR_UNITS.get(unit.upper(), 1.0)
        except ValueError:
            return None
        legs.append((num_s + unit, value))
        rest = rest[mm.end():]
        if idx < ordinal and not _SLASH_HEAD_RE.match(rest):
            return None
    return legs[ordinal]


def _extract_metric_values(
    text: str, regex: re.Pattern, label: str = "", *, with_lines: bool = False
) -> list:
    """All ``(raw_value_str, numeric_value)`` occurrences for one metric label.

    Considers EVERY match of the label on a line (not just the first) so a
    same-line pair like "current ATR 6.47 ... structure stop uses ATR 5.7079"
    yields both values (AMZN 2026-09-09 ATR-window conflict). The value is
    read from the window after the label so a number belonging to a *different*
    metric nearby is not misattributed (e.g. "ROE 0.18 and EPS 2.41" must not
    attach 2.41 to ROE). Dollar magnitudes normalise to plain units
    (79.78B -> 7.978e10) so 79.78B and 5.7B compare at one scale.
    """
    out: list[tuple[str, float]] = []
    # Line provenance, only needed by the same-metric conflict scan: a value
    # whose line discloses its own period is not an undisclosed conflict.
    lines_out: list[str] = []
    level_metric = label in _LEVEL_METRICS
    reject_before = _LABEL_CONTEXT_REJECT.get(label)
    for line in text.splitlines():
        if _masked_numbers(line):
            # A line whose digits are masked yields no quotable value: reading
            # the surviving fragment ("23" from "rsi=23._15", "91" from
            # "_._91") invented the IEI 2026-09-16 pcr/rsi/GARCH conflicts.
            # The corruption itself is reported by ``_digit_obfuscation``.
            continue
        if label in _COMPARISON_METRICS:
            line = _COMPARAND_SPLIT_RE.split(line)[0]
        for m in regex.finditer(line):
            # The label must be a whole token: "stoch" inside "stochrsi" is a
            # different indicator (MU market.md L18) and "beta" inside "betas"
            # is a different noun.
            if (
                line[m.end():m.end() + 1].isalpha()
                and line[m.end() - 1].isalnum()
            ):
                continue
            if reject_before is not None and reject_before.search(
                line[max(0, m.start() - 32):m.start()]
            ):
                continue
            # A label cell with no figure of its own hands its value over from
            # the NEXT table cell, where a "/"-separated list keeps the label
            # order: "| Net Income / Diluted EPS | $28,243,000,000 / $24.67 |"
            # gives the EPS 24.67, not the net income.
            cell_pair = _table_cell_pair_value(line, m)
            if cell_pair is not None and not _is_date_fragment_in(cell_pair[0], line):
                out.append(cell_pair)
                lines_out.append(line)
                continue
            slash_pair = _slash_pair_value(line, m)
            if slash_pair is not None:
                if _is_date_fragment_in(slash_pair[0], line):
                    continue
                out.append(slash_pair)
                lines_out.append(line)
                continue
            # Skip a label immediately followed by a parenthetical multiplier
            # like "T1(2R)" — 2R is a reward multiple, not the metric's value.
            tail = line[m.end():m.end() + _METRIC_WINDOW]
            stripped = re.sub(r"^\([^)]*\)", "", tail.strip())
            mnum = _DOLLAR_RE.search(stripped)
            if mnum is None:
                continue
            gap = stripped[:mnum.start()]
            if not _LABEL_TO_VALUE_FILLER_RE.match(gap):
                continue
            if _THRESHOLD_BEFORE_RE.search(gap):
                continue
            if _date_fragment_around(gap, stripped[mnum.end():]):
                continue
            if _VIF_MARKER_RE.search(
                line[max(0, m.start() - 24):m.start()]
                + gap
                + stripped[mnum.end():mnum.end() + 24]
            ):
                continue
            if level_metric and stripped[mnum.end():mnum.end() + 1] == "%":
                continue
            num_s, unit = mnum.group(1), (mnum.group(2) or "")
            # "12m" is a twelve-month window, not twelve million: reports write
            # integer magnitudes in upper case ("122M", "5.9B") and only scale a
            # fraction the other way ("1.2m").
            if unit and unit.islower() and "." not in num_s:
                continue
            if level_metric and _PERIOD_QUALIFIER_RE.search(
                _segment_before(line, m.start())[-80:] + gap
            ):
                continue
            try:
                num = float(num_s.replace(",", ""))
            except ValueError:
                continue
            out.append((num_s + unit, num * _DOLLAR_UNITS.get(unit.upper(), 1.0)))
            lines_out.append(line)
    if with_lines:
        # ``lines_out`` runs parallel to ``out``: every append above records
        # its source line, so the pairing is positional for both the two-value
        # returns (cell/slash pairs count as ONE entry in each list).
        return [(*pair, source) for pair, source in zip(out, lines_out, strict=False)]
    return out


# R-multiple labels as a swing line writes them: a chained pair sharing one
# target list ("2R/3R targets **1357.69 / 1521.68**" — the lead label owns the
# first value, the trailing label the second) or a lone label with its own
# value ("T1 611.85"). The window reader above cannot bind the chained form
# (the "2R" is followed by "/3R", not by a number), so it read the "3" of
# "3R" as T1 and the 2R price as T2 — a genuinely wrong 3R was never compared
# against its twin (MU 2026-09-09 review loop).
_R_LABEL_PAIR_RE = re.compile(
    r"\b(?:(2R|2xR|3R|3xR|T1|T2)\s*/\s*)?(2R|2xR|3R|3xR|T1|T2)\b"
    r"[^0-9]{0,8}\s*:?\s*\$?\s*\**\s*(\d[\d,]*\.\d+)(?:\s*/\s*(\d[\d,]*\.\d+))?"
)


# Labels whose value is the SECOND leg of a quoted pair.
_R_SECOND_LEG = {"3R", "3XR", "T2"}


def _rmult_metric_values(text: str, labels: tuple[str, ...]) -> list[tuple[str, float]]:
    """``(raw, value)`` for the R-label legs named in ``labels`` (pair-aware)."""
    out: list[tuple[str, float]] = []
    for line in text.splitlines():
        for m in _R_LABEL_PAIR_RE.finditer(line):
            lead, trail, first, second = m.groups()
            for label in (lead, trail):
                if not label or label.upper() not in labels:
                    continue
                # The 3R/T2-style label owns the second leg of a quoted pair
                # ("3R targets A / B"); every other spelling owns the first
                # (also when no pair is present at all).
                raw = second if second and label.upper() in _R_SECOND_LEG else first
                out.append((raw, float(raw.replace(",", ""))))
    return out


# Per-metric value reader: t1/t2 are R-multiple legs whose values only make
# sense under the pair semantics above ("xR" is the same label as "R").
_METRIC_VALUE_READERS = {
    "t1": lambda text: _rmult_metric_values(text, ("2R", "2XR", "T1")),
    "t2": lambda text: _rmult_metric_values(text, ("3R", "3XR", "T2")),
}


_FED_CUTS_LABEL_RE = re.compile(r"(?i)fed\s*rate?\s*cuts?\s+in\s+2026|will\s*fed\s*rate\s*cuts?|no\s*fed\s*rate\s*cuts|fed\s*cuts\s+2026|no\s*rate\s*cuts")
_PCT_OF = re.compile(r"\b(Yes|No)\b[^0-9]{0,14}?(\d{1,3})%?")


def _fed_cuts_contradiction(report_text: str) -> list[VerifierClaim]:
    """Same 'Fed rate cuts in 2026' event quoted at two probabilities.

    IGV 2026-09-09 review loop: news.md asserted 'Yes 0%' (no cuts, settled)
    and 'Yes 93%' (no-cut comfort) for the same Polymarket event — both
    recalled with no prediction-market leaf. This flags the pair.
    """
    if not report_text:
        return []
    labels = list(_FED_CUTS_LABEL_RE.finditer(report_text))
    if not labels:
        return []
    probs: set[float] = set()
    for m in labels:
        window = report_text[m.end():m.end() + 120]
        for pm in _PCT_OF.finditer(window):
            try:
                probs.add(float(pm.group(2)))
            except ValueError:
                continue
    # a 0% and a >50% on the same event -> contradiction
    if len(probs) >= 2 and min(probs) <= 2.0 and max(probs) >= 50.0:
        p = ", ".join(f"{x:.0f}%" for x in sorted(probs))
        return [VerifierClaim(
            claim="'fed cuts 2026' cited at conflicting probabilities: " + p,
            status="INTERNAL_CONFLICT",
            reason=(
                "The same 'Fed rate cuts in 2026' event is asserted at two "
                "materially different probabilities in this report with no "
                "prediction-market leaf. Resolve to one tool-sourced value "
                "(rule pinned by the IGV 2026-09-09 review loop)."
            ),
        )]
    return []


# A period/basis tag ON THE SAME LINE as a metric value. Two values for one
# metric are a CONFLICT only when the report left the difference undisclosed:
# a report that labels one cluster "Q2 FY26" and the other "Q1 FY26" has made
# a period statement (AMZN 2026-09-14: diluted EPS 5.75 (2026-06-30)") and
# 2.78 (2026-03-31"), which the blanket scan read as a conflict).
_PERIOD_TAG_RES: tuple[tuple[re.Pattern, str], ...] = (
    # "FY2026 Q1" (the vendor header spelling) and "Q1 FY26" are the same
    # statement; both must read as their own period, or two labelled quarters
    # look like one metric at two values (AMZN 2026-09-14 diluted EPS).
    (re.compile(r"\bFY\s*\d{2,4}\s*[- ]?Q[1-4]\b", re.I), "fq"),
    (re.compile(r"\bQ[1-4]\s*FY\s*\d{2,4}\b", re.I), "q"),
    (re.compile(r"\bFY\s*\d{2,4}\b|\b\d{4}\s*/\s*FY\b", re.I), "fy"),
    # The vendor's year/quarter spelling ("2026/Q3", QCOM 2026-09-20). Without
    # it the only token on the line is the OTHER period, so a disclosed pair
    # reads as one period and cannot be suppressed.
    (re.compile(r"\b\d{4}\s*/\s*Q[1-4]\b", re.I), "q"),
    (re.compile(r"\b20\d{2}-\d{2}-\d{2}\b"), "date"),
    (re.compile(r"\bTTM\b|\btrailing\s+twelve\b", re.I), "ttm"),
    # A stated reporting PERIOD is a basis statement in prose form: AMZN
    # 2026-09-15 fundamentals.md quotes get_ratios' D/E 0.37 "(balance-sheet
    # data dated 2025-12-31)" against get_basic_financials' "quarterly total
    # debt/equity 0.2816". Two lines tagged with two different periods are two
    # measurements, not one metric at two values.
    (re.compile(r"\bquarter(?:ly|s)\b", re.I), "period"),
    (re.compile(r"\bannual(?:ized)?\b|\bfiscal\s+year\b", re.I), "period"),
    (re.compile(r"\bFQ[1-4]\b", re.I), "fq"),
)


def _period_tag(line: str) -> str | None:
    """The period/basis token this line discloses for its figures, if any."""
    for regex, kind in _PERIOD_TAG_RES:
        m = regex.search(line)
        if m:
            # The substitution is hoisted out of the f-string: a backslash
            # inside an f-string expression is PEP 701 syntax (3.12+), and
            # pyproject declares requires-python >=3.10 - inlined, this line
            # made the whole module unparseable below 3.12.
            token = re.sub(r"\s+", "", m.group(0)).lower()
            return f"{kind}:{token}"
    return None


def _line_carrying(text: str, raw: str) -> str:
    """The line of ``text`` that carries ``raw``, or ``""``.

    The ``_METRIC_VALUE_READERS`` path returns ``(raw, value)`` pairs with no
    provenance, which left ``line`` empty and made the disclosed-basis test in
    ``_internal_conflicts`` unreachable for every metric that has a reader.
    Recovering the line here is cheaper and safer than widening the readers'
    contract, and it is what the fallback extractor already supplies.
    """
    if not raw:
        return ""
    for line in text.splitlines():
        if raw in line:
            return line
    return ""


def _period_tag_near(line: str, raw: str) -> str | None:
    """The period/basis token disclosed nearest THIS figure, not the line's first.

    ``_period_tag`` reads **one tag per line**. A line carrying two labelled
    bases therefore hands both figures the same tag, the disjointness test in
    ``_internal_conflicts`` sees one shared period, and two *disclosed*
    measurements are reported as one metric at two values:

    * JCI 2026-09-17 ``| EV/EBIT | 26.29 (TTM 2026-06-30) / 33.57 (2025-09-30) |``
    * QCOM 2026-09-20 ``Diluted EPS $1.87 (2026/Q3) ... diluted EPS $5.01`` (FY2025)
    * LULU 2026-09-15 ``| D/E | 0.36 ... 2026-01-31 | 2026-07-31 ... 0.45 |``

    Binding to the nearest token is the same rule ``_tool_scoped_values`` already
    applies to producers. **Distance decides first; ``_PERIOD_TAG_RES``' own
    order is only the tie-break** - iterating the regexes in precedence order and
    returning the first kind that matched anywhere gave a DISTANT ``FY2025``
    precedence over the ``2026/Q3`` sitting immediately beside the figure, so
    both figures on the QCOM line still came out with one shared tag. Falls back
    to the line's own tag when the figure's text cannot be located.
    """
    at = line.find(raw)
    if at < 0:
        return _period_tag(line)
    end = at + len(raw)
    best: tuple[int, int, str, str] | None = None
    for prec, (regex, kind) in enumerate(_PERIOD_TAG_RES):
        for m in regex.finditer(line):
            # Distance between the two spans; 0 when they touch or overlap.
            gap = max(m.start() - end, at - m.end(), 0)
            token = re.sub(r"\s+", "", m.group(0)).lower()
            cand = (gap, prec, kind, token)
            if best is None or cand < best:
                best = cand
    if best is None:
        return None
    return f"{best[2]}:{best[3]}"


def _internal_conflicts(report_text: str) -> list[VerifierClaim]:
    """Find the same-asserted-metric-at-different-values within ONE report.

    The per-claim anchor checks each claim against the tool evidence, so it
    cannot see that claim A says "DCF 80.76" and claim B says "DCF 80.60" —
    both individually "grounded in some leaf". This pass pairs occurrences of
    the same metric label and flags materially different values (>1%
    relative) as an INTERNAL_CONFLICT. Advisory; never rewrites.
    """
    if not report_text:
        return []
    conflicts: list[VerifierClaim] = []
    for label, (regex, tol) in _INTERNAL_CONFLICT_METRICS.items():
        # R-multiple legs (t1/t2) read the value bound to their own label; the
        # label regex stays as the fallback for its other spellings.
        reader = _METRIC_VALUE_READERS.get(label)
        if reader is not None and label in _MULTI_PRODUCER_METRICS:
            groups = [[(raw, v, None) for raw, v in g]
                      for g in _tool_scoped_values(report_text, label)]
        elif reader is not None:
            groups = [[(raw, v, None) for raw, v in reader(report_text)]]
        else:
            groups = []
        if not any(groups):
            groups = [_extract_metric_values(report_text, regex, label, with_lines=True)]
        for vals in groups:
            if not vals:
                continue
            # Group near-equal values; flag when >1 distinct cluster.
            distinct: list[list] = []  # [value, first_raw, {period tags}]
            for raw, v, line in vals:
                if _value_context_rejected(label, raw, line or ""):
                    continue
                bucket = next(
                    (
                        b
                        for b in distinct
                        if abs(b[0] - v) / max(abs(b[0]), abs(v), 1e-9) <= tol
                        or _same_with_dropped_unit(b[0], b[1], v, raw)
                    ),
                    None,
                )
                if bucket is None:
                    bucket = [v, raw, set(), line or ""]
                    distinct.append(bucket)
                if not line:
                    # The `_METRIC_VALUE_READERS` path carries no line, so the
                    # disclosed-basis test below was SILENTLY INERT for every
                    # metric that has a reader - which is most of them. QCOM
                    # 2026-09-20 `Diluted EPS $1.87 (2026/Q3) ... diluted EPS
                    # $5.01` (FY2025) is two labelled bases on one line and was
                    # flagged as a conflict for exactly this reason.
                    line = _line_carrying(report_text, raw)
                if line:
                    bucket[3] = line
                    # Nearest-token, not the line's first: a line stating two
                    # bases must tag each figure with its own, or the
                    # disjointness test below sees one shared period and the
                    # disclosed pair is reported as a conflict.
                    tag = _period_tag_near(line, raw)
                    if tag:
                        bucket[2].add(tag)
            if len(distinct) < 2:
                continue
            # A DISCLOSED basis difference is not a conflict. When every
            # cluster carries its own period tag and no two clusters share a
            # tag, the report has said which period each value belongs to
            # (AMZN 2026-09-14: diluted EPS 2.78 for 2026-03-31 beside 5.75 for
            # 2026-06-30 - two quarters, both labelled, not one metric). An
            # unlabelled cluster, or two clusters on the SAME stated period, is
            # still a conflict (the same run's ROE 30.56 / 22.09 / 18.89 and
            # EV/EBIT 35.02 vs 32.79 stayed unflagged and undated in the prose).
            tags = [b[2] for b in distinct]
            if all(tags) and all(
                tags[i].isdisjoint(tags[j])
                for i in range(len(tags))
                for j in range(i + 1, len(tags))
            ):
                continue
            # A DISCLOSED difference is not a defect either. The analyst
            # prompt REQUIRES quoting both values with their producers and
            # flagging the conflict; a report that does so has done its job,
            # and flagging it punishes compliance (every 2026-09-14 tree did
            # exactly this for the two ATR bases, and the TSM/AMAT/WDC pairs
            # are labelled "Conflict:" / "do not mix" next to the values).
            # Naming the producers ALONE is not enough - that is the
            # attribution-without-reconciliation case a fact-check still
            # counts as a defect (AMZN 2026-09-14 ROE 30.56/22.09/18.89).
            flagged = {b[1].strip() for b in distinct if b[1]}
            if flagged and _disclosed_pair(report_text, regex, flagged):
                continue
            # A quoted UNIT is a quoted basis: `get_options_iv_read` prints VRP
            # as a percentage-point spread while `get_variance_premium` prints
            # it as a variance ratio (AMZN 2026-09-15 market.md: +2.10pp vs
            # +0.0490, each beside its own tool). Two unit classes are two
            # constructs, not one metric at two values.
            if label in _UNIT_SCOPED_METRICS and len(
                {_unit_after(b[3], b[1]) for b in distinct}
            ) > 1:
                continue
            # Different frameworks quote their own T1/T2 by design
            # (get_swing_set off the structure stop, get_swing_exits off the
            # chandelier, get_tranche_plan off an averaged entry), and HPE
            # 2026-09-14 market.md says so outright. Only values quoted in the
            # SAME paragraph are claims about one another; a transcription
            # slip inside one framework still pairs up and flags.
            if label in _MULTI_PRODUCER_METRICS:
                paras = [p for p in re.split(r"\n\s*\n", report_text) if regex.search(p)]
                paired = any(
                    sum(1 for b in distinct if _value_in(b[1].strip(), p)) >= 2
                    for p in paras
                )
                if not paired:
                    continue
            shown = "; ".join(f"{b[1]}" for b in distinct)
            conflicts.append(
                VerifierClaim(
                    claim=f"'{label}' cited at conflicting values: {shown}",
                    status="INTERNAL_CONFLICT",
                    reason=(
                        "The same metric appears at different values in this report — "
                        "likely quoted from different data tools/vendors and never "
                        "reconciled. Resolve to one value (pick a vendor or average) "
                        "before relying on the figure."
                    ),
                )
            )
    return conflicts


# ---------------------------------------------------------------------------
# Valuation-identity checks (deterministic; MU 2026-09-09 review loop)
# ---------------------------------------------------------------------------
# The MU fundamentals.md mixed basis and broke identities the same report
# asserted: "P/E 135.94" (provider, annual-EPS basis) vs "TTM EPS $44.17" +
# price $1,027.77 (=> P/E 23.3); "RoE ~35%" decomposed from inputs that
# multiply to 66.5%; "EV $1.166T" while "net CASH $19.65B" with
# "Market cap $1.16T" (EV must be below the cap). These are not
# number-vs-vendor conflicts — they are internal identities broken inside
# ONE report. Deterministic identity checks below; advisory, never rewrite.

_PE_RE = re.compile(r"\bP\s*/\s*E\b\s*:?\s*\**\s*(\d[\d,]*(?:\.\d+)?)")
_PRICE_RE = re.compile(r"(?i)(?:last|price|latest close)\s*:?\s*\**\s*\$?\s*\**\s*(\d[\d,]*\.\d{2})|at\s+\$(\d[\d,]*\.\d{2})")
_TTM_EPS_RE = re.compile(r"(?i)\beps\b[^0-9]{0,40}ttm[^0-9]{0,40}\$\s*\**\s*(\d[\d,]*(?:\.\d+)?)")
# A "[\d.]+" capture swallows a sentence-ending period, and float() then
# raises: "equity_multiplier 1.5286. Margin-led" made the whole DuPont check
# record a metric error instead of a verdict (MU fundamentals.md 2026-09-14).
_ROE_RE = re.compile(r"\bROE\b\s*\**\s*~?\s*(\d+(?:\.\d+)?)\s*%")
_NET_MARGIN_RE = re.compile(r"net_margin\s*\**\s*(\d+(?:\.\d+)?)")
_AT_RE = re.compile(r"asset_turnover\s*\**\s*(\d+(?:\.\d+)?)")
_EM_RE = re.compile(r"equity_multiplier\s*\**\s*(\d+(?:\.\d+)?)")
_EV_RE = re.compile(r"\bEV\b(?!\s*/)[::]?\s*\**\s*\$?\s*\**\s*(\d[\d,]*)")
_MCAP_RE = re.compile(r"(?i)market\s*cap[^0-9]{0,45}\$?\s*\**\s*(\d[\d,]*)")
_NET_CASH_RE = re.compile(r"(?i)net\s*cash[^0-9]{0,20}\$?\s*([\d.]+)\s*B")


def _dupont_identity(report_text: str) -> list[VerifierClaim]:
    """ROE = net_margin x asset_turnover x equity_multiplier, when quoted.

    The comparison targets the ROE on the SAME line as the decomposition
    inputs — a report may legitimately quote several ROE bases (DuPont on
    TTM, analyst screen 19.3% on another period), and only the pair attached
    to the decomposition is an identity to check (NXPI 2026-09-09: the
    on-line DuPont ROE 26.1% matched; a different screen's 19.34% was NOT a
    conflict).
    """
    if not report_text:
        return []
    nm = _NET_MARGIN_RE.search(report_text)
    at = _AT_RE.search(report_text)
    em = _EM_RE.search(report_text)
    if not (nm and at and em):
        return []
    product_pct = float(nm.group(1)) * float(at.group(1)) * float(em.group(1)) * 100.0
    # Same line as any decomposition input carries the checked ROE.
    for line in report_text.splitlines():
        if not (_NET_MARGIN_RE.search(line) or _AT_RE.search(line) or _EM_RE.search(line)):
            continue
        # Only the ROE ATTACHED to the decomposition is an identity to check:
        # a line may name the other bases it disagrees with (SKHY 2026-09-14
        # fundamentals.md: "ROE 134.2% (leverage-led ...) - net_margin 0.8562,
        # asset_turnover 1.0742, equity_multiplier 1.4595 ... This conflicts
        # with get_ratios ROE 35.57%"), and reading the disclosed comparison
        # value as a second identity failure inverts the intent.
        for m in list(_ROE_RE.finditer(line))[:1]:
            roe = float(m.group(1))
            if roe <= 0:
                continue
            if _DISCLOSURE_MARKERS.search(line):
                continue
            if abs(product_pct - roe) / max(abs(roe), 1e-9) > 0.2:
                return [
                    VerifierClaim(
                        claim="DuPont identity: net_margin x asset_turnover x equity_multiplier "
                              f"= {product_pct:.1f}% but ROE quoted at {roe:.1f}% on the same line",
                        status="INTERNAL_CONFLICT",
                        reason=(
                            "The decomposition inputs on the DuPont line do not multiply to "
                            "the ROE the same line states. Fix the decomposed value or "
                            "label it a fuzzy estimate (rule pinned by the MU 2026-09-09 "
                            "review loop)."
                        ),
                    )
                ]
    return []


def _pe_basis_conflict(report_text: str) -> list[VerifierClaim]:
    """P/E quoted must be consistent with a quoted TTM EPS at the quoted price."""
    if not report_text:
        return []
    pes = [float(m.group(1).replace(",", "")) for m in _PE_RE.finditer(report_text)]
    ttm_eps = None
    m = _TTM_EPS_RE.search(report_text)
    if m:
        ttm_eps = float(m.group(1).replace(",", ""))
    price = None
    mp = _PRICE_RE.search(report_text)
    if mp:
        price = float((mp.group(1) or mp.group(2)).replace(",", ""))
    if not (pes and ttm_eps and price):
        return []
    implied = price / ttm_eps
    for pe in pes:
        if pe <= 0:
            continue
        if abs(pe - implied) / max(implied, 1e-9) > 0.5:
            return [
                VerifierClaim(
                    claim=f"P/E quoted at {pe:.2f} vs {price:,.2f} / TTM EPS {ttm_eps:.2f} "
                          f"= {implied:.2f}",
                    status="INTERNAL_CONFLICT",
                    reason=(
                        "The P/E basis does not match the TTM EPS basis the report itself "
                        "quotes (a provider P/E may sit on annual EPS while the report "
                        "cites TTM EPS). Reconcile the basis (rule pinned by the MU "
                        "2026-09-09 review loop)."
                    ),
                )
            ]
    return []


def _ev_net_cash_conflict(report_text: str) -> list[VerifierClaim]:
    """EV must be below market cap when the report asserts net cash."""
    if not report_text:
        return []
    ev_m = _EV_RE.search(report_text)
    mcap_m = _MCAP_RE.search(report_text)
    nc_m = _NET_CASH_RE.search(report_text)
    if not (ev_m and mcap_m and nc_m):
        return []
    ev = float(ev_m.group(1).replace(",", ""))
    mcap = float(mcap_m.group(1).replace(",", ""))
    net_cash = float(nc_m.group(1)) * 1e9
    # EV = mcap - net_cash is the identity; allow unit noise (2% of mcap).
    expected = mcap - net_cash
    if ev > mcap and abs(ev - expected) / max(abs(expected), 1e-9) > 0.02:
        return [
            VerifierClaim(
                claim=f"EV {ev:,.0f} > market cap {mcap:,.0f} while report asserts "
                      f"net cash ${net_cash/1e9:.2f}B",
                status="INTERNAL_CONFLICT",
                reason=(
                    "A net-cash balance sheet must price EV below (or around) market cap. "
"The quoted EV uses a different debt/cash/lease basis than the "
                        "balance-sheet row. Reconcile EV to one basis (rule pinned by "
                        "the MU 2026-09-09 review loop)."
                ),
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Basis-identity checks (NVDA 2026-09-12 review loop: D5/D7 + ratio bases)
# ---------------------------------------------------------------------------
# The NVDA 2026-09-12 fundamentals reports printed a net-debt line, a current
# ratio and a ROA on bases that disagree with the other numbers the SAME
# report quotes, and bound one fiscal-quarter label to the wrong ISO date.
# These are basis/identity breaks inside ONE report (never renderer bugs), so
# they are checked deterministically here and reported as advisory conflicts.

# A dollar figure with an optional K/M/B/T suffix; a bare number is read as
# raw dollars (so "62,469" -> 6.2e-5 B) which keeps unlike scales apart.
_MONEY_SUFFIX_EXP = {"": 1e-9, "k": 1e-6, "m": 1e-3, "b": 1.0, "t": 1e3}

_CASH_STI_RE = re.compile(
    r"(?i)cash\s*(?:\+|and|&)\s*(?:st\b|short[-\s]?term)\s+investments?"
    # The gap must not bridge into another noun phrase: NFLX 2026-09-15
    # fundamentals.md writes "a -25.7% QoQ drop in cash + ST investments and a
    # 4,714,403,000 buyback quarter", and a 12-char gap handed the BUYBACK to
    # the cash leg (the same class as the stripped-unit captures).
    r"[\s|:*=]{0,4}\$?\s*([\d][\d,]*(?:\.\d+)?)\s*([KMBTkmbt]?)(?![A-Za-z])"
)
# The OTHER cash basis, and the one a vendor's "Net Debt" row is usually on.
# QCOM 2026-06-30 fundamentals.md prints BOTH on one line —
#   Total Debt 15,270,000,000; Net Debt 10,737,000,000;
#   Cash And Cash Equivalents 4,533,000,000; Cash + ST Investments 8,304,000,000
# — and 15,270 - 4,533 = 10,737 EXACTLY. Pairing that correct vendor row
# against cash+ST investments (8,304 => 6,966) read a true report as a 35%
# contradiction. The net line must resolve from EITHER basis the report
# prints, not from one the checker prefers.
_CASH_CE_RE = re.compile(
    r"(?i)cash\s*(?:and|&)\s*(?:cash\s+)?equivalents?"
    r"[\s|:*=]{0,4}\$?\s*([\d][\d,]*(?:\.\d+)?)\s*([KMBTkmbt]?)(?![A-Za-z])"
)
# "total debt ... = $38.35B" (R1 spells the current + long-term legs first) or
# the plain table row "Total Debt | $38.35B" (R2).
_TOTAL_DEBT_EQ_RE = re.compile(
    r"(?i)total\s+debt\b[^\n]{0,90}?=\s*\**\s*\$?\s*([\d][\d,]*(?:\.\d+)?)\s*([KMBTkmbt]?)(?![A-Za-z])"
)
_TOTAL_DEBT_RE = re.compile(
    r"(?i)total\s+debt\b[^\n\d$]{0,14}\$?\s*([\d][\d,]*(?:\.\d+)?)\s*([KMBTkmbt]?)(?![A-Za-z])"
)
_NET_FIGURE_RE = re.compile(
    r"(?i)net\s+(debt|cash)\b[\s:;,|=/~*\-]*\$?\s*([\d][\d,]*(?:\.\d+)?)\s*([KMBTkmbt]?)(?![A-Za-z])"
)
# A line that names a quoted net row as WRONG rejects it as the report's own
# figure (the row is quoted to be corrected, not asserted). Narrow on purpose:
# the cue needs an explicit defect word next to the figure.
_NET_FIGURE_REJECT_RE = re.compile(
    r"(?i)\bmis-?sign|\bwrong\s+sign|\bnot\s+quot|\bdo(?:es)?\s+not\s+(?:quote|use|rely)"
    r"|\bunreliable\b|\bmislabel|\bstale\b"
)


def _money_billions(raw: str, suffix: str | None) -> float | None:
    """A dollar figure -> billions, honouring a K/M/B/T suffix ('' = raw $)."""
    try:
        value = float(raw.replace(",", ""))
    except (ValueError, AttributeError):
        return None
    scale = _MONEY_SUFFIX_EXP.get((suffix or "").lower())
    if scale is None:
        return None
    return value * scale


def _net_debt_identity(report_text: str) -> list[VerifierClaim]:
    """Cash+ST investments minus total debt must match the quoted net figure.

    Pins the NVDA 2026-09-12 (R2) defect: the report quoted cash+ST
    investments $62.47B and total debt $38.35B (=> ~$24.1B net CASH) while also
    printing "net debt of $10.9B" — the quoted net line disagrees with the
    balance-sheet legs by a full sign and ~145% of the larger leg.
    """
    if not report_text:
        return []
    debt_m = _TOTAL_DEBT_EQ_RE.search(report_text) or _TOTAL_DEBT_RE.search(report_text)
    # A slash-list label cell pairs its values by ORDINAL: the row
    # "| Total Debt / Net Debt | 14,309,306,000 / 5,210,074,000 |" (NFLX
    # 2026-09-15 fundamentals.md) otherwise hands the TOTAL DEBT to the net
    # leg, and the check then read a correct report as a $9.59B contradiction.
    net_matches = []
    for m in _NET_FIGURE_RE.finditer(report_text):
        line_start = report_text.rfind("\n", 0, m.start()) + 1
        line_end = report_text.find("\n", m.end())
        line = report_text[line_start: line_end if line_end != -1 else len(report_text)]
        # A vendor row the report names as wrong is QUOTED, not asserted: MSFT
        # 2026-09-16 fundamentals.md wrote 'the vendor "Net Debt
        # 19,359,000,000" row is mis-signed and I do not quote it as debt'
        # beside its own +19,825,000,000 net cash, and the checker read the
        # rejected row as the report's net figure (same shape: MSFT 11:30, AMAT
        # 2026-09-14 'the vendor's "Net Debt" row is a mislabel').
        if _NET_FIGURE_REJECT_RE.search(line):
            continue
        pair = _table_cell_pair_value(line, m)
        net_matches.append((m, pair[0] if pair else m.group(2), pair[1] if pair else None))
    if not net_matches:
        return []
    debts = [x for x in net_matches if x[0].group(1).lower() == "debt"]
    net_m, net_raw, net_value = (debts or net_matches)[-1]
    if not debt_m:
        return []
    debt = _money_billions(debt_m.group(1), debt_m.group(2))
    quoted = (
        net_value
        if net_value is not None
        else _money_billions(net_raw, net_m.group(3))
    )
    if debt is None or quoted is None:
        return []
    is_debt = net_m.group(1).lower() == "debt"
    if not is_debt:
        quoted = -quoted
    # Every cash basis this report prints is a legitimate basis for its own net
    # line; the check may not pick one and call the other a contradiction.
    bases: list[tuple[str, float]] = []
    for label, rx in (
        ("cash+ST investments", _CASH_STI_RE),
        ("cash and cash equivalents", _CASH_CE_RE),
    ):
        m = rx.search(report_text)
        if not m:
            continue
        value = _money_billions(m.group(1), m.group(2))
        if value is not None:
            bases.append((label, value))
    if not bases:
        return []
    for _basis, cash in bases:
        expected = debt - cash
        if abs(quoted - expected) / max(abs(quoted), abs(expected), 1e-9) <= 0.05:
            return []
    basis, cash = bases[0]
    expected = debt - cash
    implied_word = "net cash" if expected < 0 else "net debt"
    tried = " or ".join(f"{b} ${v:.2f}B" for b, v in bases)
    return [
        VerifierClaim(
            claim=(
                f"{basis} ${cash:.2f}B - total debt ${debt:.2f}B = "
                f"{implied_word} ${abs(expected):.2f}B, but report quotes "
                f"{'net debt' if is_debt else 'net cash'} ${abs(quoted):.2f}B"
            ),
            status="INTERNAL_CONFLICT",
            reason=(
                "The quoted net debt / net cash figure does not resolve from "
                f"either cash basis the same report prints ({tried}) against its "
                "total debt row. Reconcile the net line to those legs (rule "
                "pinned by the NVDA 2026-09-12 review loop)."
            ),
        )
    ]


_CURRENT_RATIO_RE = re.compile(r"(?i)\b(?:current\s+ratio|CR)\b[^0-9\n]{0,12}?(\d+(?:\.\d+)?)")
_CA_CL_PAIR_RE = re.compile(
    r"(?i)current\s+assets\b[^0-9\n]{0,16}?current\s+liabilit(?:ies|y)\b"
    r"[^0-9]{0,24}\$?\s*([\d][\d,]*(?:\.\d+)?)\s*([KMBTkmbt]?)(?![A-Za-z])"
    r"[^0-9]{0,12}\$?\s*([\d][\d,]*(?:\.\d+)?)\s*([KMBTkmbt]?)(?![A-Za-z])"
)


def _current_ratio_identity(report_text: str) -> list[VerifierClaim]:
    """A quoted current ratio must match the report's own CA/CL pair.

    Pins the NVDA 2026-09-12 (R1) defect: the report printed current assets /
    current liabilities $197.41B / $43.02B (= 4.588) while the quoted provider
    current ratio was 4.6808 — a 2% basis break inside one report.
    """
    if not report_text:
        return []
    cr_m = _CURRENT_RATIO_RE.search(report_text)
    pair = _CA_CL_PAIR_RE.search(report_text)
    if not (cr_m and pair):
        return []
    ca = _money_billions(pair.group(1), pair.group(2))
    cl = _money_billions(pair.group(3), pair.group(4))
    try:
        quoted = float(cr_m.group(1))
    except ValueError:
        return []
    if not (ca and cl and quoted):
        return []
    computed = ca / cl
    if abs(computed - quoted) / max(abs(computed), 1e-9) <= 0.02:
        return []
    return [
        VerifierClaim(
            claim=(
                f"current ratio quoted {quoted:.4f} vs current assets ${ca:.2f}B / "
                f"current liabilities ${cl:.2f}B = {computed:.4f}"
            ),
            status="INTERNAL_CONFLICT",
            reason=(
                "The quoted current ratio does not resolve from the current "
                "assets / current liabilities pair the same report prints. "
                "Reconcile to one balance-sheet basis (rule pinned by the NVDA "
                "2026-09-12 review loop)."
            ),
        )
    ]


_ROA_RE = re.compile(r"(?i)\bROA\b[^\n0-9]{0,20}?(\d+(?:\.\d+)?)\s*%")
# The DuPont decomposition inputs; accept the underscore tool form and the
# spaced prose form ("net margin 0.637" / "net_margin 0.637").
_ROA_NET_MARGIN_RE = re.compile(r"(?i)net[_\s]?margin\s*\**\s*[:=]?\s*(\d+(?:\.\d+)?)")
_ROA_ASSET_TURNOVER_RE = re.compile(r"(?i)asset[_\s]?turnover\s*\**\s*[:=]?\s*(\d+(?:\.\d+)?)")


def _roa_consistency(report_text: str) -> list[VerifierClaim]:
    """A quoted ROA must agree with the report's net margin x asset turnover.

    Pins the NVDA 2026-09-12 (R1) defect: ROA TTM 81.41% was a provider
    passthrough while the same report's DuPont inputs (net margin 0.637 x
    asset turnover 0.946 = 60.3%) never produced it.
    """
    if not report_text:
        return []
    # Compare only within ONE paragraph: the identity is the report's own claim
    # only where it prints the ROA and its decomposition together. TSM
    # 2026-09-15 fundamentals.md quotes get_fundamentals' ROA 19.00% several
    # bullets away from get_dupont_read's net_margin 0.4992 x asset_turnover
    # 0.5598, and VST 2026-09-15 splits the two the same way - the old
    # whole-report search crossed producers and read a report that discloses
    # every basis it uses as a contradiction (AMZN 2026-09-15: "the ROE, ROA,
    # current-ratio, and FCF readings vary by basis").
    block = ""
    for block in re.split(r"\n\s*\n", report_text):
        roa_m = _ROA_RE.search(block)
        margin_m = _ROA_NET_MARGIN_RE.search(block)
        turnover_m = _ROA_ASSET_TURNOVER_RE.search(block)
        if roa_m and margin_m and turnover_m:
            break
    else:
        return []

    # A stated basis difference is exempt everywhere else in this module and
    # is exempt here too: AMAT/VST 2026-09-14 carry a dated reconciliation
    # clause naming each ROA basis ("three ROA bases (2.27% ratios / 5.89%
    # fundamentals / 5.34% DuPont-implied)").
    if _DISCLOSURE_MARKERS.search(block):
        return []
    try:
        roa = float(roa_m.group(1))
        margin = float(margin_m.group(1))
        turnover = float(turnover_m.group(1))
    except ValueError:
        return []
    if roa <= 0 or margin <= 0 or turnover <= 0:
        return []
    margin_pct = margin * 100.0 if margin <= 1.0 else margin
    implied = margin_pct * turnover
    if abs(implied - roa) / max(abs(roa), 1e-9) <= 0.2:
        return []
    # The product must be one of the report's own ROA readings for the
    # comparison to be about anything: AMZN 2026-09-15 prints three provider
    # ROAs (6.59 / 15.21 / 11.10) and the DuPont product IS get_ratios' 11.10,
    # so the report is showing bases, not contradicting itself. A single
    # quoted ROA the report's own decomposition does not produce is the defect
    # R1 pinned (NVDA 2026-09-12: ROA 81.41% vs margin 0.637 x turnover 0.946
    # = 60.3%).
    quoted_roa = [float(v) for v in _ROA_RE.findall(report_text)]
    if len(quoted_roa) > 1 and any(
        q > 0 and abs(implied - q) / q <= 0.05 for q in quoted_roa
    ):
        return []
    return [
        VerifierClaim(
            claim=(
                f"ROA quoted {roa:.2f}% vs net margin {margin_pct:.2f}% x asset "
                f"turnover {turnover:.3f} = {implied:.2f}%"
            ),
            status="INTERNAL_CONFLICT",
            reason=(
                "The quoted ROA does not resolve from the net margin x asset "
                "turnover pair the same report prints (a provider ROA on another "
                "basis). Reconcile to one basis (rule pinned by the NVDA "
                "2026-09-12 review loop)."
            ),
        )
    ]


# A markdown table header cell bound to one fiscal quarter, and one bound to
# an ISO period-end date. Cross-table column index is how the two bind: R2's
# balance-sheet date header aligns under its income / cash-flow quarter labels.
_FQ_LABEL_RE = re.compile(r"^Q\s*([1-4])\s*FY\s*(\d{2,4})$", re.I)
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _table_cells(line: str) -> list[str]:
    """Cells of a markdown table row, or [] when the line is not one."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    cells = [c.strip().strip("*").strip() for c in stripped.strip("|").split("|")]
    return cells if len(cells) >= 2 else []


def _parse_fq_label(label: str) -> tuple[int, int] | None:
    """(quarter, fiscal_year) from a "Qn FYyy[yy]" cell label."""
    m = _FQ_LABEL_RE.match(label)
    if not m:
        return None
    fiscal_year = int(m.group(2))
    if fiscal_year < 100:
        fiscal_year += 2000
    return int(m.group(1)), fiscal_year


def _fq_quarter(date_str: str) -> tuple[int, int] | None:
    """(quarter, fiscal_year) an ISO date-end sits in, for a Jan-end year."""
    m = _ISO_DATE_RE.match(date_str)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    quarter = ((month - 2) % 12) // 3 + 1
    return quarter, year + 1 if month >= 2 else year


def _quarter_label_consistency(report_text: str) -> list[VerifierClaim]:
    """Fiscal-quarter column labels must not contradict the ISO dates.

    Pins the NVDA 2026-09-12 (R2) defect: 2025-07-31 appeared as the "Q1 FY26"
    column of the income/balance tables but as "Q2 FY26" in the cash-flow
    table. Two cases fire, both from the report's own tables:
    (a) one ISO date bound (by column index) to two different quarter labels;
    (b) a quarter label that the Jan-end calendar does not assign to its bound
        date. (b) only runs when some other column in the report IS consistent,
        so the calendar is derived from the report, never assumed; a non-Jan
        fiscal-year reporter therefore never triggers (b).
    """
    if not report_text:
        return []
    date_headers: list[list[str]] = []
    label_headers: list[list[str]] = []
    for line in report_text.splitlines():
        cells = _table_cells(line)
        if not cells:
            continue
        if sum(1 for c in cells if _ISO_DATE_RE.match(c)) >= 2:
            date_headers.append(cells)
        elif sum(1 for c in cells if _FQ_LABEL_RE.match(c)) >= 2:
            label_headers.append(cells)
    if not (date_headers and label_headers):
        return []
    bound: dict[str, list[str]] = {}
    for header in date_headers:
        for idx, cell in enumerate(header):
            if not _ISO_DATE_RE.match(cell):
                continue
            labels = bound.setdefault(cell, [])
            for label_header in label_headers:
                if idx < len(label_header) and _FQ_LABEL_RE.match(label_header[idx]):
                    norm = " ".join(label_header[idx].upper().split())
                    if norm not in labels:
                        labels.append(norm)
    claims: list[VerifierClaim] = []
    # (a) one ISO date carrying two different fiscal-quarter labels.
    for date, labels in bound.items():
        if len(labels) >= 2:
            claims.append(
                VerifierClaim(
                    claim=f"date {date} labelled {labels[0]} and {labels[1]} in one report",
                    status="INTERNAL_CONFLICT",
                    reason=(
                        "Two different fiscal-quarter columns carry the same period-end "
                        "date, so at least one is mislabelled (rule pinned by the NVDA "
                        "2026-09-12 review loop)."
                    ),
                )
            )
    # (b) a label the Jan-end calendar does not assign to its bound date.
    any_consistent = any(
        _parse_fq_label(label) == _fq_quarter(date)
        for date, labels in bound.items()
        for label in labels
    )
    if any_consistent:
        for date, labels in bound.items():
            derived = _fq_quarter(date)
            if derived is None:
                continue
            for label in labels:
                parsed = _parse_fq_label(label)
                if parsed and parsed != derived:
                    quarter, fiscal_year = derived
                    claims.append(
                        VerifierClaim(
                            claim=(f"date {date} bound to {label} but its fiscal quarter is "
                                   f"Q{quarter} FY{fiscal_year}"),
                            status="INTERNAL_CONFLICT",
                            reason=(
                                "The column header binds this ISO period-end date to a "
                                "fiscal quarter the Jan-end fiscal calendar does not assign "
                                "to it. Non-Jan fiscal-year reporters are out of scope for "
                                "this check (rule pinned by the NVDA 2026-09-12 review "
                                "loop)."
                            ),
                        )
                    )
    return claims


_DRAWDOWN_RE = re.compile(
    r"(?i)[~\-]?\s*(\d+(?:\.\d+)?)\s*%\s*(?:below|off)\s+"
    r"(?:its\s+|the\s+)?(?:52[-\s]?week\s+)?(?:high|top)"
)
# A 52-week high with its value on the SAME line (never crosses a newline, so
# "52-week high" at end of line cannot latch onto the next line's "52"):
_52W_HIGH_RE = re.compile(
    r"(?i)\b52[-\s]?week\s+high\s*[:=-]?\s*\$?\s*(\d{2,}(?:[.,]\d+)?)\b"
)


def _dd_price(report_text: str) -> float | None:
    """A per-line price/close/last figure (1+ decimals), checked line-wise."""
    for line in report_text.splitlines():
        m = re.search(r"(?i)(?:last|price|close|nav)\s*:?[=\s]*\$?\s*(\d[\d,]*(?:\.\d+)?)", line)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def _drawdown_identity(report_text: str) -> list[VerifierClaim]:
    """A 'X% below 52-week high' claim must match price/high - 1.

    SOXX 2026-09-09 review loop: the fundamentals.md asserted "NAV ~$532 is
    at ~39% below its 52-week high" while the same report quotes price 532
    and 52w high 655.95 (=> 18.9%). The mid-sentence self-correction
    ('...actually -18.8%') is the kind of stale-draft artifact this catches
    deterministically.
    """
    if not report_text:
        return []
    out = []
    for m in _DRAWDOWN_RE.finditer(report_text):
        claimed = abs(float(m.group(1)))
        high_m = _52W_HIGH_RE.search(report_text)
        price = _dd_price(report_text)
        if not (high_m and price is not None):
            continue
        try:
            high = float(high_m.group(1).replace(",", ""))
        except ValueError:
            continue
        if high <= 0 or abs(claimed) <= 1:
            continue
        implied = (price - high) / high * 100.0
        if abs(claimed - abs(implied)) / max(abs(implied), 1e-9) > 0.2:
            out.append(VerifierClaim(
                claim=f"'{claimed:.0f}% below 52-week high' vs price {price:,.2f} / "
                      f"high {high:,.2f} = {implied:.1f}%",
                status="INTERNAL_CONFLICT",
                reason=(
                    "Claimed 'X% below 52-week high' does not match (price - "
                    "52w high)/52w high computed from the same report - "
                    "recompute the drawdown (rule pinned by the SOXX 2026-09-09 "
                    "review loop)."
                ),
            ))
            break  # one drawdown claim per report is enough
    return out


# ---------------------------------------------------------------------------
# Beat-streak identity (DELL 2026-09-10 review loop)
# ---------------------------------------------------------------------------
# A claim "N straight >K% EPS beats" must match the consecutive count from the
# earnings-surprise table (newest quarter first, Surprise% column): only the
# latest two quarters (+44.0, +100.8) exceed 40%, so "three straight >40%"
# would be an overcount.
_DPS_RE = re.compile(r"(?i)dividend(?:s)?\s+per\s+share[^0-9]{0,8}\$?\s*([0-9.]+)")
_DIV_YIELD_RE = re.compile(r"(?i)(?:dividend\s*yield|ttm\s*yield)[^0-9]{0,14}\s*([0-9.]+)\s*%")
# Fund distribution lists (QQQI 2026-09-13 review loop). A fund reports its
# per-share payments as a dated series ("2026-04-22 $0.6297; 2026-05-20
# $0.6589; ...") or as a slash list in a table row, not as the single
# "dividend per share" the DPS regex expects - so the yield sanity check
# bailed out and let "Dividend yield: 9.00%" stand five lines above its own
# distribution table paying ~14%. Dated prints let the cadence be INFERRED
# (a 26-33 day median gap is monthly, 80-100 quarterly) instead of assumed,
# which is what keeps a quarterly payer from being annualized x12.
_DIST_DATED_RE = re.compile(
    r"(?i)(20\d\d-\d\d-\d\d)[^\n$%]{0,12}\$\s*([0-9]+\.[0-9]{2,4})"
)
_DIST_AMOUNTS_RE = re.compile(r"\$\s*([0-9]+\.[0-9]{2,4})")
_DIST_CADENCE_RE = re.compile(r"(?i)\b(monthly|quarterly)\b")


_FCF_AMT = re.compile(
    r"(?i)\bfcf\b[^0-9$]{0,12}\$?\s*(\d[\d,]*(?:\.\d+)?)\s*([KMBkmb]?)(?![A-Za-z])"
)
_FCF_AMT_FE = re.compile(
    r"(?i)free\s+cash\s+flow[^0-9$]{0,12}\$?\s*(\d[\d,]*(?:\.\d+)?)\s*([KMBkmb]?)(?![A-Za-z])"
)


def _fcf_unit_slip(report_text: str) -> list[VerifierClaim]:
    """FCF amounts in one report must share the same unit scale.

    WDC 2026-09-10 fundamentals review loop: the summary says 'FCF $4.1B TTM'
    and the risk ladder says 'stated FCF $3.10M TTM' - a unit slip (the FY26
    FCF leaf is 3,511,000,000). A sub-$1B FCF quote next to an FCF quote
    >= $1B in the SAME report is an INTERNAL_CONFLICT (M-vs-B typo class).
    """
    if not report_text:
        return []
    vals = []
    for rx in (_FCF_AMT, _FCF_AMT_FE):
        for m in rx.finditer(report_text):
            try:
                num = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            unit = (m.group(2) or "").upper()
            mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(unit, 1.0)
            val = num * mult
            if val <= 0:
                continue
            # Non-money contexts ("FCF yield ~1.7%", "FCF = 274.97+347.27..",
            # "FCF ~1.42x TTM NI") are not dollar totals: require a money
            # unit ($/B/M/K) or a large raw exact figure.
            if not unit and num < 1e6:
                continue
            vals.append(val)
    if len(vals) < 2:
        return []
    small = [v for v in vals if v <= 1e9]
    big = [v for v in vals if v > 1e9]
    if not (small and big):
        return []
    worst = max(big) / max(small)
    if worst >= 100.0:
        return [VerifierClaim(
            claim=f"FCF quoted at {max(small)/1e6:,.1f}M and "
                  f"{max(big)/1e9:,.2f}B in one report (unit slip)",
            status="INTERNAL_CONFLICT",
            reason=(
                "FCF amounts span a unit-scale range in the same report "
                "(WDC 2026-09-10: $3.10M vs $3.5B - the FY26 FCF is "
                "3,511M). Quote cash-flow totals on one unit scale."
            ),
        )]
    return []

_VRP_PP = re.compile(r"vrp\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*(?:pp)?", re.I)
_VRP_SIGN_LABEL = re.compile(r"vrp\s*positive", re.I)


def _vrp_sign_label(report_text: str) -> list[VerifierClaim]:
    """A 'VRP positive' label must not coexist with a quoted negative VRP."

    MU 2026-09-10 market review loop: body quoted 'VRP -5.24pp (IV below
    realized)' while the summary table labeled 'VRP positive => vols cheap'
    - a sign flip between sections. A negative number quoted anywhere + a
    'positive' label = INTERNAL_CONFLICT.
    """
    if not report_text:
        return []
    text = report_text.replace("\u2212", "-")  # unicode minus -> ASCII
    if not _VRP_SIGN_LABEL.search(text):
        return []
    negs = [float(m.group(1)) for m in _VRP_PP.finditer(text) if m.group(1).startswith("-")]
    if not negs:
        return []
    return [VerifierClaim(
        claim=f"VRP labeled positive while quoted at {negs[0]:.2f}pp",
        status="INTERNAL_CONFLICT",
        reason=(
            "A 'VRP positive' label conflicts with a quoted negative VRP value "
            "(MU 2026-09-10: -5.24pp labeled positive in the summary)."
        ),
    )]


# ---------------------------------------------------------------------------
# Round-2 formula families (docs/implementation_plan_quant_formula_additions.md)
# ---------------------------------------------------------------------------
# Q6: a qualitative tone claim about a disclosure must agree with the cited
# deterministic tone read. Only sentences that attribute a tone to a document
# count, so generic prose ("we are confident in the dip thesis") never fires.
_TONE_CITED_RE = re.compile(r"tone=(zero_hits|[+-]?\d+\.\d+)")
_DISCLOSURE_WORD_RE = re.compile(
    r"disclosure|filing|10-k|10-q|transcript|call|language|tone|management sounded", re.I
)
_POSITIVE_TONE_CLAIM_RE = re.compile(
    r"confiden|optimis|upbeat|positive tone|reassur|bullish language", re.I
)
_NEGATIVE_TONE_CLAIM_RE = re.compile(
    r"cautious|wary|pessimis|downbeat|negative tone|defensive|hedged language", re.I
)
# Q3: a quoted conformal band must carry its realized coverage, and the
# INSIDE/OUTSIDE verdict printed next to a point value must be arithmetically
# true against the band bounds on the same line.
_BAND_PAIR_RE = re.compile(r"\[\s*([\d.,]+)\s*,\s*([\d.,]+)\s*\]")
_BAND_NOMINAL_RE = re.compile(r"nominal\s+(\d+(?:\.\d+)?)\s*%")
_BAND_REALIZED_RE = re.compile(r"realized\s+(\d+(?:\.\d+)?)\s*%")
_BAND_POINT_RE = re.compile(r"point value\s+([\d.,]+)\s+is\s+(INSIDE|OUTSIDE)")
_BAND_COVERAGE_SLACK = 0.25
# Only a CONFORMAL band carries a coverage promise. An option-implied
# expected-move band ("band [814.32, 1024.45] (±11.4%)") is a different object
# with no calibration pairs at all, and demanding coverage for it flagged MU
# market.md twice on the 2026-09-14 batch.
_CONFORMAL_BAND_RE = re.compile(
    r"(?i)\b(?:valuation|conformal)\s+band\b|\bnominal\s+\d+(?:\.\d+)?\s*%"
)


def _tone_claim_conflict(report_text: str) -> list[VerifierClaim]:
    """A disclosure tone claim must agree with the cited tone read (Q6).

    The prompt rule requires the analyst to cite `get_disclosure_tone` before
    a 'management sounded confident / the language turned cautious' claim, so
    the two can be checked against each other. A zero-hit read is NO SIGNAL:
    asserting a direction on top of it is the same conflict as a sign flip.
    """
    if not report_text:
        return []
    text = report_text.replace("\u2212", "-")
    cited_match = _TONE_CITED_RE.search(text)
    if not cited_match:
        return []
    raw = cited_match.group(1)
    cited = None if raw == "zero_hits" else float(raw)
    out: list[VerifierClaim] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        if not _DISCLOSURE_WORD_RE.search(sentence):
            continue
        positive = bool(_POSITIVE_TONE_CLAIM_RE.search(sentence))
        negative = bool(_NEGATIVE_TONE_CLAIM_RE.search(sentence))
        if positive == negative:
            continue
        if cited is None:
            out.append(VerifierClaim(
                claim="a disclosure tone direction asserted over a zero-hit tone read",
                status="INTERNAL_CONFLICT",
                reason=(
                    "The cited disclosure-tone read reports zero dictionary hits "
                    "(no signal found), so no direction is supported. State the "
                    "counts, or cite a document that carries tone words."
                ),
            ))
            continue
        if positive and cited < 0:
            out.append(VerifierClaim(
                claim=f"disclosure described as confident while the cited tone is {cited:+.4f}",
                status="INTERNAL_CONFLICT",
                reason=(
                    "A positive tone claim cannot stand on a negative cited tone "
                    "(Q6: the deterministic read is the second opinion the claim "
                    "must be consistent with)."
                ),
            ))
        elif negative and cited > 0:
            out.append(VerifierClaim(
                claim=f"disclosure described as cautious while the cited tone is {cited:+.4f}",
                status="INTERNAL_CONFLICT",
                reason=(
                    "A negative tone claim cannot stand on a positive cited tone "
                    "(Q6: the deterministic read is the second opinion the claim "
                    "must be consistent with)."
                ),
            ))
    return out


def _valuation_band_conflict(report_text: str) -> list[VerifierClaim]:
    """A quoted valuation band must carry its realized coverage and be
    arithmetically true about the point value it places (Q3)."""
    if not report_text:
        return []
    out: list[VerifierClaim] = []
    for line in report_text.splitlines():
        if "band" not in line.lower():
            continue
        if not _CONFORMAL_BAND_RE.search(line):
            continue
        pair = _BAND_PAIR_RE.search(line)
        if not pair:
            continue
        low, high = (float(v.replace(",", "")) for v in pair.groups())
        realized = _BAND_REALIZED_RE.search(line)
        if not realized:
            out.append(VerifierClaim(
                claim=f"valuation band [{low:g}, {high:g}] quoted without realized coverage",
                status="INTERNAL_CONFLICT",
                reason=(
                    "A conformal band without its realized coverage overclaims: the "
                    "coverage guarantee is marginal and only under exchangeability, "
                    "so the measured coverage must be printed beside the nominal level."
                ),
            ))
            continue
        nominal = _BAND_NOMINAL_RE.search(line)
        cov = float(realized.group(1)) / 100.0
        if nominal is not None:
            nom = float(nominal.group(1)) / 100.0
            if cov < nom - _BAND_COVERAGE_SLACK:
                out.append(VerifierClaim(
                    claim=f"valuation band nominal {nom:.0%} but realized coverage {cov:.1%}",
                    status="INTERNAL_CONFLICT",
                    reason=(
                        "The measured coverage is far below the nominal level; the "
                        "band is not doing what its label claims on this name."
                    ),
                ))
        pt = _BAND_POINT_RE.search(line)
        if pt:
            value = float(pt.group(1).replace(",", ""))
            verdict = pt.group(2)
            truth = low <= value <= high
            if truth != (verdict == "INSIDE"):
                out.append(VerifierClaim(
                    claim=(
                        f"point value {value:g} labeled {verdict} a band "
                        f"[{low:g}, {high:g}]"
                    ),
                    status="INTERNAL_CONFLICT",
                    reason=("The INSIDE/OUTSIDE verdict contradicts the band bounds on the same line."),
                ))
    return out


def _distribution_annual_per_share(report_text: str) -> tuple[float, str] | None:
    """Annualized per-share distribution rate from the report's OWN payment
    list, plus a one-line provenance note; None when no list is usable.

    Cadence comes from the dates when they are printed (median gap), else from
    an explicit monthly/quarterly word next to the amounts; a list whose
    cadence cannot be established is skipped rather than annualized x12.
    """
    pairs = _DIST_DATED_RE.findall(report_text)
    if len(pairs) >= 3:
        amounts = [float(a) for _d, a in pairs]
        try:
            dates = sorted(datetime.strptime(d, "%Y-%m-%d") for d, _a in pairs)
        except ValueError:
            dates = []
        if len(dates) == len(pairs) and len(dates) >= 3:
            gaps = sorted((b - a).days for a, b in zip(dates, dates[1:], strict=False))
            gap = gaps[len(gaps) // 2]
            per_year = 12.0 if 26 <= gap <= 33 else 4.0 if 80 <= gap <= 100 else None
            if per_year:
                mean = sum(amounts) / len(amounts)
                return (
                    mean * per_year,
                    f"{len(amounts)} dated prints, mean {mean:.4f}/share x{per_year:.0f} "
                    f"(median gap {gap}d)",
                )
    # Undated list: only when a cadence word appears with the amounts.
    for line in report_text.splitlines():
        if "distribution" not in line.lower():
            continue
        amounts = [float(a) for a in _DIST_AMOUNTS_RE.findall(line)]
        if len(amounts) < 3:
            continue
        cad = _DIST_CADENCE_RE.search(line) or _DIST_CADENCE_RE.search(report_text)
        per_year = {"monthly": 12.0, "quarterly": 4.0}.get(cad.group(1).lower()) if cad else None
        if per_year:
            mean = sum(amounts) / len(amounts)
            return (
                mean * per_year,
                f"{len(amounts)} prints, mean {mean:.4f}/share x{per_year:.0f} "
                f"({cad.group(1).lower()} cadence)",
            )
    return None


def _dividend_yield_sanity(report_text: str) -> list[VerifierClaim]:
    """A quoted dividend yield must not contradict the same report's own
    per-share payments and price.

    Two payment shapes are recognized: one "dividend per share $X" amount
    (annualized x4, the quarterly convention - the MU 2026-09-10 review loop
    quoted 'TTM yield 4.91%' against a $0.15/quarter record implying 0.061%)
    and a fund's dated distribution list (annualized by its own cadence - the
    QQQI 2026-09-13 loop quoted 9.00% while its prints pay ~14%). Both an
    overstated (>5x) and an understated (>1.4x) quote are conflicts: the
    vendor field can be wrong in either direction.
    """
    if not report_text:
        return []
    price = _dd_price(report_text)
    if price is None or price <= 0:
        return []
    annual: float | None = None
    evidence = ""
    dps_m = _DPS_RE.search(report_text)
    if dps_m:
        try:
            dps = float(dps_m.group(1))
        except ValueError:
            dps = 0.0
        if dps > 0:
            annual = 4.0 * dps
            evidence = f"{dps:.4f}/share x4 (quarterly convention)"
    if annual is None:
        dist = _distribution_annual_per_share(report_text)
        if dist is not None:
            annual, evidence = dist
    if annual is None or annual <= 0:
        return []
    implied = annual / price * 100.0
    if implied <= 0 or implied > 60.0:
        # A >60% implied rate means the price parse is wrong, not the yield:
        # the first "price|close|last" line of a long report is not always the
        # reference price. A claim carrying an absurd implied % costs more than
        # the missed flag, so fail closed.
        return []
    for m in _DIV_YIELD_RE.finditer(report_text):
        try:
            quoted = float(m.group(1))
        except ValueError:
            continue
        overstated = quoted > 5.0 * implied
        understated = implied > 1.4 * quoted
        if not (overstated or understated):
            continue
        return [VerifierClaim(
            claim=f"dividend yield {quoted:.2f}% vs {annual:.3f}/share / price "
                  f"{price:,.2f} => {implied:.3f}% implied ({evidence})",
            status="INTERNAL_CONFLICT",
            reason=(
                "Quoted dividend yield is "
                + ("above" if overstated else "below")
                + " the rate this report's own per-share payments imply - a stale/"
                "unit-scaled vendor field (MU 2026-09-10: 4.91% vs 0.061% implied) or an "
                "understated fund yield field (QQQI 2026-09-13: 9.00% vs 14.02% implied "
                "by its monthly distribution list)."
            ),
        )]
    return []


_DD_CLAIM = re.compile(
    r"\b(?:the\s+)?(\d+|[a-z]+)\s+(?:straight|consecutive)\s+"
    r"double[- ]digit\s+(?:eps\s+)?beats?\b", re.I)
# Shared word->count map for streak claims ('seven straight >40% beats' must
# parse the same way 'the seventh consecutive double-digit beat' does). An
# unparsed word silently disables the check, so cover at least two..ten.
_COUNT_WORDS = {
    "two": 2, "second": 2, "three": 3, "third": 3, "four": 4, "fourth": 4,
    "five": 5, "fifth": 5, "six": 6, "sixth": 6, "seven": 7, "seventh": 7,
    "eight": 8, "eighth": 8, "nine": 9, "ninth": 9, "ten": 10, "tenth": 10,
}
_DD_PCT = re.compile(r"surprise_pct\s*=\s*([\d.]+)|\+\s*([\d.]+)%")


def _parse_dd_count(raw: str) -> int | None:
    if raw.isdigit():
        return int(raw)
    return _COUNT_WORDS.get(raw.lower())


def _double_digit_streak_identity(report_text: str) -> list[VerifierClaim]:
    """'N consecutive double-digit beats' must match the >=10% surprise run.

    MU 2026-09-10 news.md claimed 'the fifth consecutive double-digit beat
    (Mar-26 +33.21%, Dec-25 +20.58%, Sep-25 +5.94%)' while the earnings
    calendar shows 21.39 / 33.21 / 20.58 / 5.94 - only THREE consecutive
    >=10% surprises (Sep-25 5.94 breaks the run).
    """
    if not report_text:
        return []
    claims = list(_DD_CLAIM.finditer(report_text))
    if not claims:
        return []
    lines = [ln for ln in report_text.splitlines()
             if "surprise_pct" in ln or "Straight" in ln]
    merged = "\n".join(lines)
    pcts = []
    for m in _DD_PCT.finditer(merged):
        try:
            v = float(m.group(1) or m.group(2))
        except (TypeError, ValueError):
            continue
        pcts.append(v)
    streak = 0
    for v in pcts:
        if v < 10.0:
            break
        streak += 1
    out = []
    for m in claims:
        claimed = _parse_dd_count(m.group(1))
        if claimed is None or claimed == streak:
            continue
        out.append(VerifierClaim(
            claim=f"'{m.group(0).strip()}' vs {streak} consecutive "
                  f">=10% surprises in calendar",
            status="INTERNAL_CONFLICT",
            reason=(
                "Claimed consecutive double-digit-beat count does not match "
                "the calendar's >=10% run (MU 2026-09-10: 'fifth' vs 3 - "
                "Sep-25 +5.94% breaks it)."
            ),
        ))
    return out


_INS_SOLD_LINE = re.compile(
    r"(?i)\bsold\s+(\d[\d,]*)\s*(?:sh|shares|shs)?[\s\S]{0,30}?"
    r"\bat\s+([\d.]+)\s*(?:[-\u2013]\s*([\d.]+))?"
    r"\s*(?:\(|\s)(?:value\s*)?[$]?\s*"
    r"(\d[\d,]*(?:\.\d+)?)\s*([kmb]?)\b"
)


def _insider_sold_value_identity(report_text: str) -> list[VerifierClaim]:
    """A 'sold N sh at lo[-hi] (value V)' must satisfy V ~= N x price."""
    if not report_text:
        return []
    out = []
    for m in _INS_SOLD_LINE.finditer(report_text):
        try:
            sh = float(m.group(1).replace(",", ""))
            lo = float(m.group(2))
            hi = float(m.group(3)) if m.group(3) else lo
            val = float(m.group(4).replace(",", ""))
        except (TypeError, ValueError):
            continue
        mult = {"k": 1e3, "m": 1e6, "b": 1e9}.get((m.group(5) or "").lower(), 1.0)
        val *= mult
        if val <= 0:
            continue
        implied = sh * (lo + hi) / 2.0
        ratio = implied / val
        if ratio < 0.8 or ratio > 1.25:
            out.append(VerifierClaim(
                claim=f"sold {sh:,.0f} sh at {lo:,.2f}-{hi:,.2f} vs value {val:,.0f}",
                status="INTERNAL_CONFLICT",
                reason=(
                    "Shares x price range does not reconcile to the quoted value "
                    "(MU 2026-09-10 summary: 30,000 x ~974 = $29M vs $38.8M; "
                    "the leaf shows the sale as 40,000 sh / 38,756,162)."
                ),
            ))
    return out


_SMA200_VAL_RE = re.compile(r"(?i)200[-\s]?day[^0-9]{0,14}?(\d[\d,]*(?:\.\d+)?)")
_SMA_PCT_RE = re.compile(
    r"(?i)(\d+(?:\.\d+)?)\s*%\s*(above|below)\s+(?:the\s+)?"
    r"(price\b|200[-\s]?day\b)")


def _sma200_identity(report_text: str) -> list[VerifierClaim]:
    """A 'X% above/below (the price|the 200-day)' claim must match the same
    report's 200-day value and price.

    SNDK 2026-09-10 fundamentals review loop: 'is 65% below price' while
    the value-dip tool says dist_sma200=65.5% (price ABOVE the 200-day);
    price 1698.41 / sma 1026.54 => the 200-day is only 39.6% below price.
    """
    if not report_text:
        return []
    m = _SMA200_VAL_RE.search(report_text)
    price = _dd_price(report_text)
    if not (m and price is not None):
        return []
    try:
        sma = float(m.group(1).replace(",", ""))
    except ValueError:
        return []
    if sma <= 0:
        return []
    out = []
    for cm in _SMA_PCT_RE.finditer(report_text):
        try:
            pct = float(cm.group(1))
        except ValueError:
            continue
        dir_, obj = cm.group(2).lower(), cm.group(3).lower()
        if obj.startswith("200"):
            implied = (price - sma) / sma * 100.0 if dir_ == "above" else (sma - price) / sma * 100.0
        else:
            implied = (sma - price) / price * 100.0 if dir_ == "above" else (price - sma) / price * 100.0
        if abs(implied) <= 0.5:
            continue
        if abs(pct - abs(implied)) / abs(implied) > 0.2:
            out.append(VerifierClaim(
                claim=f"'{pct:.0f}% {dir_} {obj}' vs price {price:,.2f} / "
                      f"200-day {sma:,.2f} => {implied:.1f}%",
                status="INTERNAL_CONFLICT",
                reason=(
                    "Claimed distance from the 200-day does not match price/sma "
                    "- direction or basis flipped (SNDK 2026-09-10: '65% below "
                    "price' vs 39.6% below; the 65.5% is price ABOVE the sma)."
                ),
            ))
    return out

# A separator ("=", ":", "is", "at") may sit between the label and the value:
# "10-EMA = 54.66" is the common written form and the old pattern only matched
# the space/paren shapes ("10-EMA 54.66", "10-EMA (graph 55.54)"), so a report
# that quoted the 10-EMA as "= NN.NN" never entered the identity check at all.
_TEMA_VAL = re.compile(
    r"10\s*-?\s*EMA\s*(?:=|:|is|at)?\s*\(?(?:graph\s*)?([0-9]+\.?[0-9]+)", re.I
)
_TRAIL_VAL = re.compile(r"EMA\s*-?\s?trail[^0-9]{0,12}?([0-9]+\.?[0-9]*)", re.I)
# A dated series is one value CHANGING, not two competing readings: IEI
# 2026-09-15 market.md quotes "10 EMA 116.1043 -> **115.0450**" (moomoo, 08-17
# to 09-15) beside the verified "10 EMA 115.20". Neither leg of a series is a
# competing canonical value, so the dual-value check must not read one.
_EMA_SERIES_AFTER_RE = re.compile(r"^\s*(?:\u2192|->|=>|to)\s*\**\s*[\d.]")
_EMA_SERIES_BEFORE_RE = re.compile(r"[\d.]+\s*(?:\u2192|->|=>)\s*\**\s*$")


def _ema_identity(report_text: str) -> list[VerifierClaim]:
    """Conflicting 10-EMA values in one report.

    HPE 2026-09-10 market.md: trend section quotes the 10-EMA as 54.66
    (+1.5% above it), but the summary calls for 'retake of the 10-EMA (graph
    55.54)'. Same indicator, two values.
    """
    if not report_text:
        return []
    vals: set[str] = set()
    for m in _TEMA_VAL.finditer(report_text):
        if _EMA_SERIES_AFTER_RE.match(report_text[m.end(1): m.end(1) + 16]):
            continue
        if _EMA_SERIES_BEFORE_RE.search(report_text[max(0, m.start(1) - 16): m.start(1)]):
            continue
        vals.add(m.group(1))
    if len(vals) <= 1:
        return []
    return [VerifierClaim(
        claim="10-EMA cited at conflicting values: " + " / ".join(sorted(vals)),
        status="INTERNAL_CONFLICT",
        reason=(
            "The report quotes two different 10-EMA values (HPE 2026-09-10: "
            "54.66 in the trend section vs 55.54 in the summary). Keep one "
            "canonical 10-EMA per report and label the source."
        ),
    )]


def _ema_trail_identity(report_text: str) -> list[VerifierClaim]:
    """Conflicting EMA-trail stop values in one report.

    HPE 2026-09-10 market.md: body '20d EMA trail = 53.91' vs summary
    'ema-trail 59.02' - the same labeled stop at two values; a stop level a
    trader acts on must be single-valued.
    """
    if not report_text:
        return []
    vals: set[str] = set()
    for m in _TRAIL_VAL.finditer(report_text):
        # "| Chandelier / 20-EMA trail | 414.0586 (exit) / 422.0031 |": the
        # label is the SECOND leg of a slash list whose values pair by
        # position, so the cell value before the slash belongs to the
        # chandelier - reading it as a second EMA trail invented a stop
        # conflict on a row that labels both tools (TSM 2026-09-15 market.md).
        if re.search(r"(?i)chandelier\s*(?:stop)?\s*/", report_text[max(0, m.start() - 40): m.start()]):
            continue
        vals.add(m.group(1))
    vals = _cluster_value_tokens(sorted(vals))
    if len(vals) <= 1:
        return []
    return [VerifierClaim(
        claim="EMA-trail stop cited at conflicting values: " + " / ".join(sorted(vals)),
        status="INTERNAL_CONFLICT",
        reason=(
            "The report quotes more than one EMA-trail stop value (HPE "
            "2026-09-10: body 53.91 vs summary 59.02). One canonical stop "
            "per methodology, explicitly labeled."
        ),
    )]


_SMA200_PCT = re.compile(r"200\s*-?\s*SMA[^\n]{0,60}?([+]?\d+(?:\.\d+)?)%", re.I)
# ...but a percent inside that window belongs to the 200-SMA only when no
# other metric introduces it. IEI 2026-09-15 market.md states its distance
# once ("1.6% under the 200-SMA") and the reader still reported two: the 4.9%
# of "no short thesis at 200-SMA support with 4.8-4.9% 5-7y yields" (a YIELD)
# and the Bollinger "%b -6.22%" two clauses later.
_FOREIGN_PCT_LABEL_RE = re.compile(
    r"(?i)\b(?:rsi|stoch\w*|mfi|kst|atr|adx|yields?|coupon|vwap|skew|hist|"
    r"macd|ema|sma|boll(?:inger)?|vol(?:ume)?|iv|odds|probability)\b"
)
# A value that is the SECOND leg of a range ("4.8-4.9%") is not a distance.
_RANGE_DASH_RE = re.compile(r"\d\s*[-\u2013\u2014~]\s*$")
_SMA_LABEL_STRIP_RE = re.compile(r"(?i)\b200\s*-?\s*(?:day\s*)?sma\b")


def _sma200_pct_is_foreign(line: str, m: re.Match) -> bool:
    """True when the % in this match is some other metric's, not the SMA's."""
    window = _SMA_LABEL_STRIP_RE.sub(" ", line[max(0, m.start(1) - 22): m.start(1)])
    return bool(_FOREIGN_PCT_LABEL_RE.search(window) or _RANGE_DASH_RE.search(window))


_GARCH_COND = re.compile(r"garch[^\n]{0,40}?\bcond(?:itional)?[^0-9]{0,8}(\d+(?:\.\d+)?)%", re.I)
# The `(n x ATR)` leg is not the stop: "chandelier 486.7536 (= 3x10.3422 below
# the 22-bar anchor high 517.78)" read the 3 as a second chandelier value
# (MSFT 2026-09-16 13:04 market.md).
_CHANDELIER_MULTIPLE_AFTER = r"(?!\s*[x\u00d7X])(?!\s*ATR)"
# The `=` form's gap may carry prose ("chandelier 3xATR below 22-bar high =
# 54.11") but never ANOTHER metric's assignment: "... chandelier 485.9179 (3x
# ATR below the 22-bar high), 1R=4.3821" is the 1R's value, and the gap ends in
# its label (a label sitting next to a figure carries a digit - 1R, t1, t2 -
# where prose does not: high, stop, level). MSFT 2026-09-16 23:14 market.md was
# flagged INTERNAL_CONFLICT on 4.3821 vs 485.9179 by exactly that grab.
_CHANDELIER_EQ = re.compile(
    rf"chandelier([^=\n]*)=\s*\**\s*(\d+(?:\.\d+)?){_CHANDELIER_MULTIPLE_AFTER}", re.I
)
_CHANDELIER_GAP_FOREIGN_RE = re.compile(r"\d\S*\s*$")
# The space form tolerates the word "stop" between label and value: the old
# reader demanded a digit straight after "chandelier ", so "chandelier stop
# 486.3121" (MSFT 2026-09-15 14:02 market.md) was invisible to it.
_CHANDELIER_SPACE = re.compile(
    rf"chandelier\s*(?:stop)?\s+(\d+(?:\.\d+)?){_CHANDELIER_MULTIPLE_AFTER}", re.I
)


def _chandelier_values(report_text: str) -> list[str]:
    """Chandelier stop figures, from both printed forms.

    ``=`` form: the gap may hold prose, but a gap ending in another label
    (``1R=``) is that other quantity, not this stop. ``space`` form: an
    optional "stop" between label and value, never the ``(n x ATR)`` leg.
    """
    return [
        m.group(2)
        for m in _CHANDELIER_EQ.finditer(report_text)
        if not _CHANDELIER_GAP_FOREIGN_RE.search(m.group(1))
    ] + [m.group(1) for m in _CHANDELIER_SPACE.finditer(report_text)]


_PRIMARY_PRICE = re.compile(
    # The spot price, never the SESSION IT BEGAN FROM: TSM 2026-09-15 market.md
    # opens with "Verified OHLCV ... C 413.23" and the very next sentence quotes
    # "Prev close 418.01", which the fallback entry picked - inventing a 2R/3R
    # mismatch against the swing-set stop (AMZN 2026-09-15: "Prior close
    # 253.54").
    # The leading \b is load-bearing: without it the alternation matched the
    # "at" INSIDE an ordinary word, so IEI 2026-09-15 market.md's own caveat
    # sentence - '... do not reconcile as a true print."* Treat 114.33 as
    # unverified.' - handed back the DISOWNED live print as the report's spot
    # price. The swing-set row's 2R/3R targets were then re-derived off the day
    # low plus ATR (114.33 + 2*0.2939 = 114.92 vs the quoted 115.2778) and two
    # targets that are verbatim tool output were flagged. "Treat" is not "at".
    r"(?i)(?<!prev\s)(?<!previous\s)(?<!prior\s)\b(?:at|close|price|spot)[\s:$]{0,3}\$?\s*([0-9]+\.[0-9]{2})"
)


def _primary_price(report_text: str) -> float | None:
    """First the-stated spot price in a single-ticker report.

    Matches 'at / X.XX' / 'close X.XX' / 'price $X.XX' so a DCF, stop,
    or price target is NOT picked up.
    """
    m = _PRIMARY_PRICE.search(report_text or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except (TypeError, ValueError):
        return None


_SMA_ABOVE_RE = re.compile(r"([+]?-?\d+(?:\.\d+)?)%\s*(?:above|below)\s+the\s+200\s*-?\s*SMA\b[^\n:!]{0,16}?([0-9]+\.?[0-9]*)", re.I)


_SMA_LABEL_RE = re.compile(r"\b(?:10|20|50|200)\s*-?\s*(?:day\s*)?SMA\b", re.I)
_PCT_TOKEN_RE = re.compile(r"[+-]?\d+(?:\.\d+)?%")


def _sma200_percent_values(report_text: str) -> list[str]:
    """The % figures the report ties to the 200-SMA, table rows included.

    A table row lists its labels in one cell and their values, in the same
    order, elsewhere in the row - MSFT 2026-09-15 market.md writes
    ``| 50-SMA / 200-SMA | 457.68 / 429.95 | Stacked, rising; +8.9% / +15.9% above |``,
    where +8.9% is the 50-SMA's distance. Reading it as a second 200-SMA
    distance invented a conflict on a row that labels both; the label's
    ordinal in its slash list selects the matching value.
    """
    out: list[str] = []
    for line in report_text.splitlines():
        for m in _SMA200_PCT.finditer(line):
            if _sma200_pct_is_foreign(line, m):
                continue
            if "|" not in line:
                out.append(m.group(1))
                continue
            pos = 0
            for idx, cell in enumerate(line.split("|")):
                if pos <= m.start() < pos + len(cell):
                    labels = list(_SMA_LABEL_RE.finditer(cell))
                    value_cell = next(
                        (c for c in line.split("|")[idx + 1:]
                         if len(_PCT_TOKEN_RE.findall(c)) >= 2),
                        None,
                    )
                    if len(labels) > 1 and value_cell is not None:
                        ordinal = sum(
                            1 for lm in labels if lm.start() <= m.start() - pos
                        )
                        pcts = _PCT_TOKEN_RE.findall(value_cell)
                        if 1 <= ordinal <= len(pcts):
                            out.append(pcts[ordinal - 1].rstrip("%"))
                    else:
                        out.append(m.group(1))
                    break
                pos += len(cell) + 1
    return out


def _sma200_pct_identity(report_text: str) -> list[VerifierClaim]:
    """Conflicting (or mislabeled) price-vs-200-SMA percentages in one report.

    1) Two differently stated % distances to the 200-SMA (HPE 2026-09-10:
       body '+64.7%' = 55.46/33.68-1 vs table '+184.7%').
    2) A single '% above/below the 200-SMA' that does NOT recompute from the
       report's own price + 200-SMA values (MSFT 2026-09-10 decision.md:
       'price +8.8% above the 200-SMA 429.51' while the same text's ~490.50
       price implies +14.2% - the +8.8% is the 50-SMA distance mislabeled).
    """
    if not report_text:
        return []
    out: list[VerifierClaim] = []

    def _pct(v: str) -> float | None:
        try:
            return float(v.rstrip("%").strip("+"))
        except (TypeError, ValueError):
            return None

    # 1) pairwise conflicts between distinct stated percents. Two raw values
    #    that PRINT identically are not two distances: AMZN 2026-09-16
    #    market.md states 2.35 and 2.44, both of which render "+2.4%" - the
    #    claim read "+2.4% / +2.4%" and invented a conflict the report does
    #    not contain. Compare at the precision the claim prints.
    vals = sorted({round(v, 1) for raw in _sma200_percent_values(report_text)
                   if (v := _pct(raw)) is not None})
    if len(vals) > 1:
        out.append(VerifierClaim(
            claim="200-SMA distance cited at different values: "
                  + " / ".join(f"{v:+.1f}%" for v in vals),
            status="INTERNAL_CONFLICT",
            reason=(
                "The report quotes differing % distances to the 200-SMA "
                "(HPE 2026-09-10: +64.7% body = 55.46/33.68-1 vs +184.7% "
                "summary table - the extra value matches no leaf). Keep one "
                "canonical distance per report."
            ),
        ))

    # 2) mislabeled-%-as-200-SMA: the claim line ALSO carries a 50-SMA value
    #    and the stated % is objectively the 50-SMA distance, not the 200-SMA
    #    distance (MSFT 2026-09-10: '+8.8% above the 200-SMA 429.51 and above
    #    the rising 50-SMA 450.83' at ~490.50: the 200-SMA distance is ~+14%
    #    and +8.8% is the 50-SMA distance).
    m = _SMA_ABOVE_RE.search(report_text)
    if m:
        claimed = _pct(m.group(1))
        sma200 = m.group(2)
        if claimed is not None and sma200:
            line = report_text[m.start():].split("\n", 1)[0]
            m50 = re.search(r"50\s*-?\s*SMA\b[^\n:!]{0,20}?([0-9]+\.?[0-9]+)", line, re.I)
            price = _primary_price(report_text)
            if m50 and price is not None:
                s200 = float(sma200)
                s50 = float(m50.group(1))
                if s200 > 0 and s50 > 0 and abs(s50 - s200) / s200 > 0.02:
                    d200 = (price - s200) / s200 * 100.0
                    d50 = (price - s50) / s50 * 100.0
                    d200_rel = abs(claimed - d200) / max(abs(d200), 1e-9)
                    d50_rel = abs(claimed - d50) / max(abs(d50), 1e-9)
                    if d200_rel > 0.2 and d50_rel <= 0.1:
                        out.append(VerifierClaim(
                            claim=(
                                f"stated {claimed:+.1f}% as the 200-SMA distance "
                                f"({sma200}) is actually the 50-SMA distance "
                                f"({s50}): at price {price:.2f} the 200-SMA is "
                                f"{d200:+.1f}%, the 50-SMA {d50:+.1f}%"
                            ),
                            status="INTERNAL_CONFLICT",
                            reason=(
                                "A % quoted 'above/below the 200-SMA' is, by the "
                                "report's own numbers, the 50-SMA distance - the "
                                "label was swapped (MSFT 2026-09-10 decision.md: "
                                "+8.8% above the 200-SMA 429.51 at ~490.50 is "
                                "+14.2% on the 200-SMA and +8.8% on the 50-SMA "
                                "450.83). Recompute from the paired SMA values."
                            ),
                        ))
    return out


def _garch_cond_identity(report_text: str) -> list[VerifierClaim]:
    """Conflicting GARCH conditional-volatility values in one report.

    HPE 2026-09-10 market.md: body 'GARCH ... conditional 58.90%' vs summary
    'GARCH cond 65.90%' - same labeled estimator, two values.
    """
    if not report_text:
        return []
    vals = _cluster_value_tokens([m.group(1) for m in _GARCH_COND.finditer(report_text)])
    if len(vals) <= 1:
        return []
    return [VerifierClaim(
        claim="GARCH conditional vol cited at conflicting values: "
              + " / ".join(sorted(vals)),
        status="INTERNAL_CONFLICT",
        reason=(
            "The report quotes two GARCH conditional-volatility values for "
            "the same estimator (HPE 2026-09-10: body 58.90% vs table "
            "65.90%). Keep one canonical GARCH cond print."
        ),
    )]


def _chandelier_identity(report_text: str) -> list[VerifierClaim]:
    """Conflicting chandelier stop values in one report.

    HPE 2026-09-10 market.md: chandelier 54.11 (body, 3xATR below 22-bar
    high), 'chandelier/EMA trails 54.11/53.91', summary 'chandelier
    58.2/ema-trail 59.02' and 'exit below 58.11 (chand)' - three labeled
    chandelier values from different calc windows. One canonical stop.
    """
    if not report_text:
        return []
    raw = _chandelier_values(report_text)
    vals = _cluster_value_tokens(raw)
    if len(vals) <= 1:
        return []
    return [VerifierClaim(
        claim="chandelier stop cited at conflicting values: "
              + " / ".join(sorted(vals)),
        status="INTERNAL_CONFLICT",
        reason=(
            "The report quotes more than one chandelier stop value without "
            "labeling the differing calculations (HPE 2026-09-10: 54.11 in "
            "the swing trail vs 58.2 / 58.11 in the summary). One canonical "
            "stop per methodology, explicitly labeled."
        ),
    )]


_SUM_LINE = re.compile(
    r"([0-9][0-9,]*\.?[0-9]*(?:\s*\+\s*[0-9][0-9,]*\.?[0-9]*){2,})\s*=\s*\$?\s*(\d[\d,]*(?:\.\d+)?)"
)


def _sum_identity(report_text: str) -> list[VerifierClaim]:
    """Flag a quoted additive sum whose arithmetic is wrong.

    ADBE 2026-09-10 fundamentals.md wrote 'TTM OCF = $2.165+2.958+3.160+2.198
    = $10.62B' but 2.165+2.958+3.160+2.198 = 10.481B. A report that states
    the addends and a total must present arithmetic that matches; a >0.5%
    discrepancy is a transcription/derivation slip.
    """
    if not report_text:
        return []
    for m in _SUM_LINE.finditer(report_text):
        raw = m.group(1)
        total = float(m.group(2).replace(",", ""))
        addends = [float(x.replace(",", "")) for x in re.findall(r"[0-9][0-9,]*\.?[0-9]*", raw)]
        if len(addends) < 3:
            continue
        s = sum(addends)
        if abs(s) < 1e-9:
            continue
        # The addends and the total may be quoted on different SCALES: WDC
        # 2026-09-14 fundamentals.md writes the four buyback quarters as
        # millions and the total in dollars ("672+752+615+553 =
        # $2,592,000,000") - the arithmetic is right, the units are implicit.
        if abs(s - total) / abs(s) > 0.005 and not any(
            abs(s * scale - total) / abs(s * scale) <= 0.005
            for scale in (1e3, 1e6, 1e9, 1e12)
        ):
            expr = "+".join(str(x) for x in addends)
            return [VerifierClaim(
                claim=f"quoted sum {expr} = {total:g} (as written) sums to {s:g}",
                status="INTERNAL_CONFLICT",
                reason=(
                    "The report states addends and a total whose "
                    "arithmetic does not match (ADBE 2026-09-10: TTM OCF "
                    "2.165+2.958+3.160+2.198 written as $10.62B but "
                    "summing to 10.481B). Re-add from the verbatim "
                    "addends."
                ),
            )]
    return []


_PT_CONTEXT_REJECT = re.compile(r"(?i)\bvs\b|z-?score|\bstd\b|deviation|\bn\s*=\s*\d|\.\.\.")

_PRICE_TARGET = re.compile(
    # A price target is never a percentage: without the lookahead, "call IV mean
    # 151.3%, put IV mean 184.7%" read as two conflicting mean PTs (JCI
    # 2026-09-14 market.md), and the same shape hit AMZN (102.8/91.3).
    r"\bmean\s+(?:PT\s*)?\$?(\d[\d,]*(?:\.\d+)?)(?![\d.])(?!\s*%)",
    re.I,
)


def _price_target_identity(report_text: str) -> list[VerifierClaim]:
    """Conflicting 'mean price target' values in one report.

    HPE 2026-09-10 fundamentals.md: get_analyst_ratings returned mean PT
    69.38, the body quoted 69.38 (high 88 / low 54), but the summary table
    wrote 'mean PT $58.38' and 'mean 58.97, high 69.38'. A report must use
    one mean-PT per dataset and label the source; three distinct means with
    no label is a defect.
    """
    if not report_text:
        return []
    vals = set()
    for line in report_text.splitlines():
        for m in _PRICE_TARGET.finditer(line):
            # "current 1.2770 vs mean 1.9691, std 0.5373" is a z-score series'
            # mean, not a consensus target (TSM 2026-09-14 fundamentals.md).
            if _PT_CONTEXT_REJECT.search(line[max(0, m.start() - 30): m.start()]):
                continue
            vals.add(m.group(1))
    if len(vals) <= 1:
        return []
    return [VerifierClaim(
        claim="mean price target cited at conflicting values: "
              + " / ".join(sorted(vals)),
        status="INTERNAL_CONFLICT",
        reason=(
            "The report quotes more than one distinct 'mean PT' figure "
            "without labeling the datasets (HPE 2026-09-10: leaf 69.38 vs "
            "table 58.38 / 58.97). Quote the consensus mean once - body and "
            "summary must agree - and name the tool that produced it."
        ),
    )]


_MONEY_ELLIPSIS = re.compile(r"\$\s*\d[\d,]*\.?\d*\s*[BMK]?\s*\.\.\.")
_SELF_CORRECTION = re.compile(
    r"(?:\bcorrected?\s*:|\bcorrection\s*[\u2014-]|\b\.\.\.\s*(?:corrected?|correction))"
)
# A generation that gave up and re-emitted itself, or that says so out loud.
# HPE 2026-09-14 fundamentals.md shipped a whole report that degenerated:
# "Wait correction needed below", "This is degenerating", a 10x repeated
# "Inventory series:" line, then "I am stuck repeating myself due an internal
# glitch. Please disregard this draft attempt entirely. I will restart
# cleanly below" followed by a second, space-stripped copy of the report -
# and the deterministic pass flagged none of it (only bogus figure conflicts
# read out of the mangled digits).
_DEGENERATION_MARKERS = re.compile(
    r"(?:\brestarts?\s+cleanly|\brestarting\s+cleanly|\bdisregard\s+(?:this|the)\s+draft"
    r"|\binternal\s+glitch|\bstuck\s+repeating|\bthis\s+is\s+degenerating"
    r"|\bwait,?\s+correction\s+needed)",
    re.I,
)
_FINAL_PROPOSAL = re.compile(r"\bFINAL\s+TRANSACTION\s+PROPOSAL\b", re.I)
# The verdict token on a proposal line, to tell a repeated conclusion from a
# restarted one: two HOLD lines is a style habit, HOLD then SELL is a restart.
_FINAL_VERDICT = re.compile(
    r"FINAL\s+TRANSACTION\s+PROPOSAL\s*:?\s*\**\s*([A-Za-z]+)", re.I
)
# Leaked tool-call markup: an unexecuted call transcript written as the report
# (wdc 2026-09-14 market_report.md is 25 lines of invoke-tag markup and nothing
# else - the model emitted XML tool syntax, no tool ran, and the raw text was
# saved as the analyst's market read; NFLX and NVDA 2026-09-15 wrote the same
# block under the trader's "Computed verification" heading). The vocabulary is
# shared with the tool loop that now PARSES and executes it
# (``tool_call_markup.TOOL_CALL_MARKUP_RE``), so the producer and this detector
# cannot drift - including the spelling that lost its ``tool_`` prefix.
_TOOL_CALL_MARKUP = TOOL_CALL_MARKUP_RE
# A run of non-whitespace this long is text that lost its spaces: the restart
# copy above had 300+ character tokens ("terminalshare64WACC121beta144...").
_GLUED_RUN = re.compile(r"\S{200,}")
_REPETITION_MIN = 4
_REPETITION_MIN_CHARS = 16


def _repetition_loops(report_text: str) -> list[str]:
    """Lines repeated verbatim at least ``_REPETITION_MIN`` times.

    Table rules and short cells are excluded: a markdown separator repeated
    four times is a table, not a stuck decoder. Returns one sample per loop.
    """
    counts: dict[str, int] = {}
    for ln in report_text.splitlines():
        s = ln.strip()
        if len(s) < _REPETITION_MIN_CHARS or set(s) <= set("-|: _"):
            continue
        counts[s] = counts.get(s, 0) + 1
    return sorted(
        (s for s, n in counts.items() if n >= _REPETITION_MIN),
        key=lambda s: -counts[s],
    )



def _digit_obfuscation(report_text: str) -> list[VerifierClaim]:
    """Numbers whose digits were replaced by underscores - unreadable text.

    IEI 2026-09-16 market.md carried 146 of them ("rsi=23._15" for the leaf's
    rsi=23.15, "pct_b=_0219", "GARCH cond **_._**04%" for 3.04%, "boll _56 ub
    _00 lb _12"). The value extractors then read the surviving fragments as
    if they were second values - that one corruption produced all three
    INTERNAL_CONFLICT rows the stem carried (pcr oi "91; 2.91" from
    "_._91", rsi "23; 23.15" from "23._15", GARCH "04; 3.04" from
    "_.04%"). The digits are unrecoverable from the text alone, so the
    figures cannot be checked at all: that is the defect, and it is reported
    as one claim instead of as three invented conflicts.
    """
    if not report_text:
        return []
    hits = _masked_numbers(report_text)
    if not hits:
        return []
    sample = ", ".join(sorted({h.strip() for h in hits})[:5])
    return [VerifierClaim(
        claim=f"digit-masked numbers in report text ({len(hits)}): {sample}",
        status="INTERNAL_CONFLICT",
        reason=(
            "Digits were replaced by underscores, so the figures cannot be "
            "read - and any value extracted from the fragment is invented "
            "(IEI 2026-09-16 market.md: 'rsi=23._15' for the leaf's 23.15, "
            "'GARCH cond **_._**04%' for 3.04%). Emit real digits; a masked "
            "number is neither quotable nor checkable."
        ),
    )]


def _self_correction_artifacts(report_text: str) -> list[VerifierClaim]:
    """Mid-sentence self-repair text should not reach a final report.

    HPE 2026-09-10 news.md: '10Y at 4.78 (2026-08-09, latest print 09-08:
    9.87 ... corrected: latest 4.8' and 'USD/JPY 172.346 ... correction -
    USD/JPY 154.3360' - the verbatim-fidelity pin leaked the model's own
    retyping (wrong value, then inline correction) into the artifact. A final
    report must contain the corrected value only; 'corrected:' /
    'correction --' inside a claim marks the editing process leaking through.
    """
    if not report_text:
        return []
    markers = []
    for ln in report_text.splitlines():
        m = _SELF_CORRECTION.search(ln)
        if m:
            markers.append(m.group(0))
        if _MONEY_ELLIPSIS.search(ln):
            markers.append("money-ellipsis")
    out: list[VerifierClaim] = []
    if markers:
        out.append(VerifierClaim(
            claim="self-correction artifacts present in report text: "
                  + ", ".join(sorted(set(markers))),
            status="INTERNAL_CONFLICT",
            reason=(
                "The report contains inline self-correction markers (e.g. "
                "'9.87 ... corrected: 4.8', '278.346 ... correction - 154.3360', "
                "'Total debt $8.22B... verbatim'); these are the model retyping a "
                "figure mid-generation and leaking the repair into the artifact. "
                "Emit only the final corrected value; never include the wrong "
                "value with a caveat (HPE 2026-09-10)."
            ),
        ))

    # A generation that restarted, looped, or lost its spacing is not a
    # readable report and must not pass as one (HPE 2026-09-14 fundamentals).
    degeneration = sorted({m.group(0).strip() for m in _DEGENERATION_MARKERS.finditer(report_text)})
    if degeneration:
        out.append(VerifierClaim(
            claim="generation-degeneration markers present: "
                  + ", ".join(f"'{d}'" for d in degeneration),
            status="INTERNAL_CONFLICT",
            reason=(
                "The text announces that it is restarting/discarding itself "
                "('I am stuck repeating myself ... I will restart cleanly', "
                "'This is degenerating', 'Wait correction needed'). Everything "
                "after such a marker is a SECOND, unreviewed copy of the "
                "report - treat neither copy as analysis (HPE 2026-09-14 "
                "fundamentals.md). Regenerate the report."
            ),
        ))
    loops = _repetition_loops(report_text)
    if loops:
        out.append(VerifierClaim(
            claim="repetition loop in report text: "
                  + "; ".join(f"{ln[:60]!r}" for ln in loops[:3]),
            status="INTERNAL_CONFLICT",
            reason=(
                "A line repeated four or more times is decoder repetition, not "
                "prose - the report stopped making progress (HPE 2026-09-14 "
                "fundamentals.md repeated one 'Inventory series:' line ten "
                "times). Regenerate the report."
            ),
        ))
    glued = _GLUED_RUN.search(report_text)
    if glued:
        out.append(VerifierClaim(
            claim=f"degenerate run ({len(glued.group(0))} chars with no whitespace) in report text",
            status="INTERNAL_CONFLICT",
            reason=(
                "A 200+ character run with no whitespace is either text that lost "
                "its spacing - labels and figures glued together, decimals gone, "
                "so neither the numbers nor any conflict read out of them can be "
                "trusted ('DCFFairValue194EV440527404343', HPE 2026-09-14 "
                "fundamentals.md) - or a stuck decoder repeating one unit "
                "('Stop_loss_loss_loss_...', MSFT 2026-09-03 "
                "final_trade_decision.md). Either way the passage is unreadable."
            ),
        ))
    verdicts = {m.group(1).strip().upper() for m in _FINAL_VERDICT.finditer(report_text)}
    if len(verdicts) > 1:
        out.append(VerifierClaim(
            claim="conflicting 'FINAL TRANSACTION PROPOSAL' verdicts in one report: "
                  + ", ".join(sorted(verdicts)),
            status="INTERNAL_CONFLICT",
            reason=(
                "A report concludes once. Two DIFFERENT verdicts means a restart "
                "left both bodies in the artifact, and the downstream reader "
                "cannot tell which one was meant. (Two identical proposal lines "
                "are a style habit, not flagged here.)"
            ),
        ))
    markup = [m.group(0) for m in _TOOL_CALL_MARKUP.finditer(report_text)]
    if markup:
        # A whole file of call markup is the worst case: no report at all.
        prose_lines = sum(
            1
            for ln in report_text.splitlines()
            if ln.strip() and not _TOOL_CALL_MARKUP.search(ln)
        )
        what = (
            "the whole artifact is a call transcript with no report text"
            if prose_lines <= 2
            else "a call transcript leaked into the report"
        )
        out.append(VerifierClaim(
            claim=f"unexecuted tool-call markup in report text ({len(markup)} tags): "
                  + ", ".join(sorted({m[:40] for m in markup})[:3]),
            status="INTERNAL_CONFLICT",
            reason=(
                f"{what}: the model emitted XML tool syntax instead of prose and "
                "the raw text was saved as the analyst's report, so the calls it "
                "describes never ran and no evidence backs the section (wdc "
                "2026-09-14 market_report.md is 25 lines of <invoke name=...> and "
                "nothing else). Regenerate the report."
            ),
        ))
    return out


_BOLL_PAIR = re.compile(
    r"(?:upper|wide)\s*=\s*(\d+(?:\.\d+)?)[^\n]{0,40}?(?:lower|low)\s*=\s*(\d+(?:\.\d+)?)"
    r"|(?:lower|low)\s*=\s*(\d+(?:\.\d+)?)[^\n]{0,40}?(?:upper|wide)\s*=\s*(\d+(?:\.\d+)?)"
    r"|wide\s+(\d+(?:\.\d+)?)\s*/\s*low\s+(\d+(?:\.\d+)?)"
)
_SECTOR_RANK = re.compile(r"\b([A-Z]{2,6})\s+rank\s*#?\s*(\d{1,2})\b", re.I)


def _bollinger_band_identity(report_text: str) -> list[VerifierClaim]:
    """Two distinct Bollinger (upper, lower) band sets in one report.

    TSM 2026-09-10 market.md: the body quoted lower=405.14 upper=438.16
    mid=421.65 (the canonical get_bollinger_pct_b print) while the summary
    table quoted 'wide 438.59 / low 404.71' - a second band pair with no
    source label, and the table's %b 0.7394 is only true for the body pair.
    One canonical band set per report, or label the alternate source.
    """
    if not report_text:
        return []
    pairs = set()
    for m in _BOLL_PAIR.finditer(report_text):
        if m.group(5) is not None:
            pairs.add((m.group(5), m.group(6)))
        elif m.group(3) is not None:
            pairs.add((m.group(3), m.group(4)))
        elif m.group(1) is not None:
            pairs.add((m.group(1), m.group(2)))
    if len(pairs) <= 1:
        return []
    shown = ", ".join(f"({u}/{low})" for u, low in sorted(pairs))
    return [VerifierClaim(
        claim=f"bollinger bands cited at conflicting sets: {shown}",
        status="INTERNAL_CONFLICT",
        reason=(
            "The report quotes more than one Bollinger (upper/lower) pair "
            "without labeling the alternate source/calculation; %b is only "
            "consistent with one of them (TSM 2026-09-10: body 438.16/405.14 "
            "vs table wide 438.59/404.71). Keep one canonical band set."
        ),
    )]


def _sector_rank_identity(report_text: str) -> list[VerifierClaim]:
    """Conflicting numeric ranks for the same sector ticker.

    TSM 2026-09-10 market.md: body said 'XLK rank #4 (tracking)' (both
    get_sector_rank and get_sector_rotation_screen return 4) but the summary
    table wrote 'XLK rank5 (Weakening)'. Rank tags must match.
    """
    if not report_text:
        return []
    per_sector: dict[str, set[str]] = {}
    for m in _SECTOR_RANK.finditer(report_text):
        sec, rk = m.group(1).upper(), m.group(2)
        per_sector.setdefault(sec, set()).add(rk)
    claims = []
    for sec, rks in sorted(per_sector.items()):
        if len(rks) > 1:
            claims.append(VerifierClaim(
                claim=f"{sec} cited at conflicting sector ranks: "
                      f"{' / '.join(sorted(rks))}",
                status="INTERNAL_CONFLICT",
                reason=(
                    "The report quotes two different numeric ranks for the "
                    "same sector; the sector-rank tool returns exactly one "
                    "rank (TSM 2026-09-10: XLK rank 4 in two tools vs rank5 "
                    "in the summary table)."
                ),
            ))
    return claims


_EPS_EST_DATE = re.compile(
    r"(20\d{2}-\d{2}-\d{2})[^\n]{0,80}?est(?:imate)?[^\d]{0,30}(\d+(?:\.\d+)?)"
)


def _eps_estimate_duals(report_text: str) -> list[VerifierClaim]:
    """Two different EPS estimates anchored to the SAME earnings date.

    MSFT 2026-09-10 news.md: the summary table and headline both cite
    "2026-10-28 (est EPS 4.72)" while the forward-calendar section wrote
    "MSFT earnings 2026-10-28 (est 4.16)". The earnings-calendar leaf said
    estimate=4.72, so 4.16 was a conflicting second figure. Same-print
    estimates must agree; flag differing values for one date.
    """
    if not report_text:
        return []
    claims: list[VerifierClaim] = []
    per_date: dict[str, set[str]] = {}
    for m in _EPS_EST_DATE.finditer(report_text):
        d, v = m.group(1), m.group(2)
        per_date.setdefault(d, set()).add(v)
    for d, vals in sorted(per_date.items()):
        if len(vals) > 1:
            claims.append(VerifierClaim(
                claim=f"eps estimate for {d} cited at conflicting values: "
                      f"{' / '.join(sorted(vals))}",
                status="INTERNAL_CONFLICT",
                reason=(
                    "The report quotes more than one EPS estimate for the same "
                    "earnings date; the earnings-calendar leaf supplies exactly "
                    "one estimate per print. Keep one value per date (MSFT "
                    "2026-09-10: 4.72 in the table vs 4.16 in the forward "
                    "calendar for 2026-10-28)."
                ),
            ))
    return claims


_BAND_ZERO = re.compile(r"[±–—-]\s*\$\s*0(?:\.00)?\b", re.I)


def _expected_band_identity(report_text: str) -> list[VerifierClaim]:
    """A stated expected-move % must carry a NONZERO dollar band.

    MSFT 2026-09-10 market review loop: the report quoted an expected earnings
    move of 6.6% but rendered the band as "+-$0.00" - at ~$490 a 6.6% move
    implies a ~$32 band ([458, 523]), so a zero-dollar band is a fabrication
    (the analyst dropped the vendor band and wrote $0.00). Any literal
    "+-$0.00"-class band is flagged.
    """
    if not report_text:
        return []
    m = _BAND_ZERO.search(report_text)
    if not m:
        return []
    # A line that DISCLAIMS the zero band is not quoting one: SIMO 2026-09-14
    # market.md wrote "no earnings-implied move / dollar band is available -
    # dollar band unavailable, not +-$0.00", and the literal in the disclaimer
    # was read as the fabrication this check exists to catch.
    ls = report_text.rfind("\n", 0, m.start()) + 1
    le = report_text.find("\n", m.end())
    line = report_text[ls: le if le != -1 else len(report_text)]
    if re.search(r"(?i)unavailable|no[_ ]data|not\s*[\u00b1+-]", line):
        return []
    return [VerifierClaim(
                claim="expected-move dollar band quoted as +/-$0.00 (impossible for a positive move)",
        status="INTERNAL_CONFLICT",
        reason=(
            "An expected-move percentage was rendered with a +/-$0.00 dollar "
            "band - impossible for a positive move at a nonzero price "
            "(MSFT 2026-09-10: 6.6% would be a ~$32 band; quote the vendor "
            "band or write 'unavailable', never $0.00)."
        ),
    )]


_BEAT_STREAK_RE = re.compile(r"(?i)(\d+|[a-z]+)\s*straight\s*>(\d+(?:\.\d+)?)\s*%")
_SURPRISE_ROW = re.compile(r"(?im)^\|\s*\d{4}/Q\d\s*\|")

_INLINE_SURPRISE_RE = re.compile(r"(?i)\b(\d{4}/Q\d)\b[^()]*\(([+\-]?\d+(?:\.\d+)?)%")

def _inline_surprise_streak(text: str, threshold: float) -> int:
    streak = 0
    for m in _INLINE_SURPRISE_RE.finditer(text):
        try:
            pct = float(m.group(2))
        except ValueError:
            break
        if pct >= threshold:
            streak += 1
        else:
            break
    return streak



def _beat_streak_identity(report_text: str) -> list[VerifierClaim]:
    """Claimed 'N straight >K% EPS beats' must match the surprise-table streak."""
    if not report_text:
        return []
    m = _BEAT_STREAK_RE.search(report_text)
    if not m:
        return []
    g = m.group(1)
    claimed = int(g) if g.isdigit() else _COUNT_WORDS.get(g.lower())
    if claimed is None:
        return []
    threshold = float(m.group(2))
    streak = 0
    rows_seen = 0
    for line in report_text.splitlines():
        if not _SURPRISE_ROW.match(line):
            continue
        rows_seen += 1
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 5:
            continue
        try:
            pct = float(parts[4].rstrip("%"))
        except ValueError:
            break
        if pct >= threshold:
            streak += 1
        else:
                break
    if rows_seen == 0:
        streak = _inline_surprise_streak(report_text, threshold)
    if streak == claimed:
        return []
    return [VerifierClaim(
        claim=f"'{claimed} straight >{threshold:.0f}% beats' vs surprise table gives "
              f"{streak} consecutive",
        status="INTERNAL_CONFLICT",
        reason=(
            "Claimed beat-streak length does not match the consecutive >threshold "
            "surprises in the earnings-surprise table (DELL 2026-09-10 review "
            "loop: 'three straight >40%' vs +44.0/+100.8/+14.6 — only two)."
        ),
    )]


# --- R-multiple (2R/3R target) identity — market-side. ---------------------
# A swing framework should quote 2R/3R targets that satisfy
#     targetN = entry + N * (entry - stop)
# from the SAME entry/stop pair. The MU 2026-09-09 market.md quoted
# "2R/3R targets 1357.69 / 1521.68" while get_swing_set (evidence) gives
# entry 1027.77 / stop 862.81 / 2R 1357.6891 / 3R 1522.6486 — the quoted
# 3R is a 0.06% offset typo (1521.68 vs 1522.65). Catch it deterministically.
_ENTRY_RE = re.compile(r"(?i)\bentry\b[^0-9]{0,12}\$?\s*\**\s*(\d[\d,]*\.\d+)")
_STOP_RE = re.compile(
    r"(?i)\b(?:struct(?:ure)?[\s_]*)?stop\b[^0-9]{0,12}\$?\s*\**\s*(\d[\d,]*\.\d+)"
)
# "stop: swing_low **134.9000**, structure_stop **129.9781**" fits the 12-char
# gap exactly, so the reader took the swing LOW as the stop and reported the
# report's own correct 2R target as wrong (VST 2026-09-14 market.md: T1(2R)
# 162.2338 resolves from 140.73 / 129.9781). A number introduced by another
# metric's label is not the stop.
_STOP_GAP_REJECT = re.compile(
    r"(?i)swing[\s_]*(?:low|high)|\bentry\b|\bavg\b|\btarget\b|\bbase\b"
)
# ... and the value may be followed by a parenthetical naming another metric.
_STOP_TAIL_REJECT = re.compile(
    r"^\s*\(\s*[^)]{0,24}?(?:sma|ema|vwma|atr|wall|mid|band|sma50|sma200)[^)]{0,12}\)",
    re.I,
)
# A line quoting a scale-in ladder: its targets come off the plan's averaged
# entry, so the report-wide spot price is not their basis.
_TRANCHE_LINE_RE = re.compile(r"(?i)\btranche\b|\bP1\b[^\n]{0,40}\bP3\b")
# "2R" / "3R" / "T1(2R)" / "T2(3R)" label followed by its value(s). A swing
# line often quotes a pair "2R/3R targets 1357.69 / 1521.68" — group 2 is the
# label-specific value (the one after "/" for the 3R in a "A / B" pair).
_RMULT_RE = re.compile(
    r"\b(2R|3R|T1|T2)\b[^0-9]{0,8}\s*:?\s*\$?\s*\**\s*(\d[\d,]*\.\d+)(?:\s*/\s*(\d[\d,]*\.\d+))?"
)

_RMULT_TOL = 0.002  # 0.2% — a real typo (0.06%) is far under; framework drift is not.

# An entry stated as an average (a tranche plan's size-weighted entry), and a
# risk stated per share. A line carrying both owns its own basis, so the
# label's implied 2R/3R multiple no longer governs (get_tranche_plan: 1.8R /
# 3.0R off avg 871.92 with risk/share 104.84 — MU market.md 2026-09-14).
_ENTRY_AVG_RE = re.compile(
    # ``[\s_]+entry``: get_tranche_plan's own stdout spells it ``avg_entry=``
    # (with an underscore), which the space-only form missed — so a report
    # quoting the tool verbatim fell back to the report-wide spot price and
    # flagged the tool's own correct 1.8R/3.0R targets (AMZN market.md
    # 2026-09-14, T1 271.97 / T2 288.46).
    r"(?i)\b(?:avg|average)(?:[\s_]+entry)?\s*[:=]?\s*\**\s*\$?\s*(\d[\d,]*\.\d+)"
)
_RISK_PER_SHARE_RE = re.compile(
    r"(?i)\brisk(?:\s*/\s*share)?\s*[:=]?\s*\**\s*\$?\s*\**\s*(\d[\d,]*\.\d+)"
)
# A stated reward multiple beside its own target. The decimal point is what
# separates a written multiple ("T1 1857.88 (1.8R)") from the label itself
# ("2R/3R targets"), which is not a claim about the basis.
_RMULT_STATED_RE = re.compile(r"(?i)\b(\d\.\d+)\s*R\b")
# The same statement in its other printed form: "targets T1(2R) 444.2039,
# T2(3R) 459.6909" (TSM 2026-09-15 market.md). Those targets come off the
# swing-set's own swing-low/ATR basis, not off any quoted entry, so the
# report-wide spot fallback must not be used to re-derive them. Parenthesized
# ONLY: a bare "2R/3R targets" phrase names the labels, not a basis.
_RMULT_STATED_LABEL_RE = re.compile(r"(?i)\(\s*\d+(?:\.\d+)?\s*R\s*\)")

# The same R-label is quoted by DIFFERENT producers in one market report
# (get_swing_set off the structure stop, get_swing_exits off the chandelier,
# get_tranche_plan off an averaged entry). Two of those are two numbers by
# design, so the pair reader compares only values quoted against the SAME tool
# scope — the tool named on their own line. A report that names no tool keeps
# the plain report-wide comparison.
_MULTI_PRODUCER_METRICS = frozenset({"t1", "t2"})
_TOOL_SCOPE_RE = re.compile(r"`?((?:get|compute|read|fetch)_[a-z0-9_]+)`?")
# A summary row names its producer in a LABEL, not in a tool call: "| Swing set
# | stop 114.0361, T1 115.2778, T2 115.6917 |" sits beside "| Tranche plan |
# ... T1 115.40 ... |". Those rows quote two frameworks' own targets by
# design, and with no tool name on the line both landed in one scope key, so
# the tranche plan's T1 flagged the swing set's (IEI 2026-09-15 market.md).
# Framework labels only - a generic "structure stop" is a basis, not a
# producer, and two MU-style target sets read as one under it.
_METHOD_SCOPE_RE = re.compile(
    r"(?i)\b(swing\s*-?\s*set|tranche\s*plan|chandelier|ema\s*-?\s?(?:20|trail))\b"
)


def _tool_scoped_values(text: str, label: str) -> list[list[tuple[str, float]]]:
    """Metric values grouped by the producer named nearest them.

    Scoping is per SEGMENT, not per line: a line naming two producers
    ("`get_tranche_plan`: ... T1=115.40 ... `get_swing_set` ... T1 **115.2778**",
    IEI 2026-09-15 market.md) binds each value to the producer named closest
    before it. A line naming none falls back to its framework label, and
    failing that to the report-wide "" scope.
    """
    groups: dict[str, list[tuple[str, float]]] = {}
    reader = _METRIC_VALUE_READERS[label]
    for line in text.splitlines():
        marks = list(_TOOL_SCOPE_RE.finditer(line))
        method = _METHOD_SCOPE_RE.search(line)
        fallback = f"method:{method.group(1).lower()}" if method else ""
        bounds = [m.start() for m in marks] + [len(line)]
        # Whatever precedes the first producer name belongs to no tool ON THIS
        # LINE: it keeps the framework-label (or report-wide) scope.
        segments = [("", line[: bounds[0]])]
        segments += [
            (mark.group(1), line[bounds[i]: bounds[i + 1]])
            for i, mark in enumerate(marks)
        ]
        for tool, segment in segments:
            if not segment:
                continue
            vals = reader(segment)
            if vals:
                groups.setdefault(tool or fallback, []).extend(vals)
    return list(groups.values())


def _rmult_value(m: re.Match) -> float | None:
    """Choose the value belonging to this R-label, honoring a '/'-pair.

    For "3R targets 1357.69 / 1521.68" the 3R value is 1521.68 (after '/').
    """
    label = m.group(1).upper()
    first = m.group(2)
    second = m.group(3)
    if label in ("3R", "T2"):
        # carry the "/"-separated partner when the 3R label precedes a pair
        return float((second or first).replace(",", ""))
    return float(first.replace(",", ""))


def _r_multiple_identity(report_text: str) -> list[VerifierClaim]:
    """2R/3R targets must equal entry+N*(entry-stop) for the SAME pair.

    R-multiples are bound to the stop on their own line (each swing framework
    quotes "stop S, 2R/3R targets A/B" together), so a report that legitimately
    presents two frameworks — e.g. MU 2026-09-09 structure stop 862.81 ->
    1357.69/1522.65 vs chandelier stop 910.16 -> 1262.99/1380.60 — is checked
    pair-wise, not crossed. Falls back to the first stop in the report only
    when a line has none.
    """
    if not report_text:
        return []
    out: list[VerifierClaim] = []
    spot = _primary_price(report_text)
    for line in report_text.splitlines():
        rs = list(_RMULT_RE.finditer(line))
        if not rs:
            continue
        # Bind the pair on THIS line only. The report-wide first "entry ..."
        # belongs to whichever tool quoted it first, and crossing it with
        # another tool's stop invented five flags per symbol on the 2026-09-14
        # batch while every quoted target was verbatim tool output.
        line_stop = None
        for cand in _STOP_RE.finditer(line):
            if _STOP_GAP_REJECT.search(cand.group(0)[: cand.start(1) - cand.start(0)]):
                continue
            # The candidate value may itself be another metric wearing a
            # parenthetical: "puts 386.51 (structure stop) and 381.68
            # (200-SMA) in play" (WDC 2026-09-15 market.md) bound the 200-SMA
            # as the stop and flagged a correct 2R target.
            if _STOP_TAIL_REJECT.match(line[cand.end(1): cand.end(1) + 24]):
                continue
            line_stop = float(cand.group(1).replace(",", ""))
            break
        if line_stop is None:
            continue
        em = _ENTRY_RE.search(line) or _ENTRY_AVG_RE.search(line)
        if em is not None:
            entry = float(em.group(1).replace(",", ""))
        elif (
            spot is not None
            and not _RMULT_STATED_RE.search(line)
            and not _RMULT_STATED_LABEL_RE.search(line)
            # A summary row quoting a tranche plan's targets names no entry of
            # its own: those targets are measured off the plan's averaged
            # entry, so the quote is not their basis (TSM 2026-09-14
            # market.md, "| Tranche plan | stop 382.56; T1 450.62; R:R 2.40 |").
            and not _TRANCHE_LINE_RE.search(line)
        ):
            entry = spot
        else:
            # The line states its own multiplier ("T1 55.27 (1.8R)") but not
            # the entry it is measured from - the tranche plan's averaged
            # entry, not the quote. Falling back to the report-wide spot price
            # asserted a risk the line never claimed and flagged the tool's own
            # output (AMKR 2026-09-14 market.md).
            continue
        risk = entry - line_stop
        if risk <= 0:
            continue
        # A plan line states its own risk basis and its own multipliers:
        # get_tranche_plan scales T1/T2 off a size-weighted average entry at
        # 1.8R / 3.0R, not off the label's implied 2R/3R.
        stated = _RISK_PER_SHARE_RE.search(line)
        own_basis = (
            _ENTRY_AVG_RE.search(line) is not None
            or _RMULT_STATED_RE.search(line) is not None
            or _RMULT_STATED_LABEL_RE.search(line) is not None
            or (
                stated is not None
                and abs(float(stated.group(1).replace(",", "")) - risk) / risk <= 0.01
            )
        )
        stated_mults = [float(x) for x in _RMULT_STATED_RE.findall(line)]
        for m in rs:
            quoted = _rmult_value(m)
            mult = 2 if m.group(1).upper() in ("2R", "T1") else 3
            if own_basis:
                implied = (quoted - entry) / risk
                # Consistent with the multiple the LINE states (1.8R / 3.0R
                # round-trips as 1.798 / 2.999 from the tool's own rounded
                # inputs - a 1.1% drift, which the old "clean decimal" test
                # rejected and so flagged the tool's verbatim output on JCI
                # and AMKR 2026-09-14).
                if stated_mults and any(
                    abs(implied - m) / m <= 0.05 for m in stated_mults
                ):
                    continue
                # A plan line that states avg entry + risk/share but drops the
                # tool's "(1.8R)" parenthetical still implies a clean multiple:
                # 149.07 from 133.90 / 8.43 is 1.798 = 1.8R with the tool's own
                # rounding (JCI 2026-09-14 market.md). 3% of a tenth still
                # rejects a real mis-binding (2.5R quoted for a 2R pair).
                if 1.0 <= implied <= 4.0 and abs(implied * 10 - round(implied * 10)) / implied <= 0.03:
                    continue
            if any(
                target > 0 and abs(quoted - target) / target <= _RMULT_TOL
                for target in (entry + k * risk for k in stated_mults)
            ):
                continue
            expected = entry + mult * risk
            if expected <= 0:
                continue
            if abs(quoted - expected) / expected > _RMULT_TOL:
                out.append(
                    VerifierClaim(
                        claim=f"{mult}R target {quoted:,.2f} != entry {entry:,.2f} + "
                              f"{mult}*risk ({risk:,.2f}) = {expected:,.2f}",
                        status="INTERNAL_CONFLICT",
                        reason=(
                            "The quoted R-multiple target does not resolve from the "
                            "entry/stop pair on its own line. Re-derive from that "
                            "pair (rule pinned by the MU 2026-09-09 review loop)."
                        ),
                    )
                )
    return out


_DAYS_OUT_RE = re.compile(
    r"(?P<count>\d{1,4})\s*days?\s*(?P<dir>out|away|ago|until|from now|later|hence)",
    re.IGNORECASE,
)
_ANY_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Only countdown/elapsed phrasings whose direction is unambiguous. A bare
# "in N days" is NOT one: "worst in 30 days" is a lookback window, and reading
# it as a countdown flagged TSM 2026-09-09 news.md (30 days vs the -3 it would
# imply). _text_metrics must never cry wolf.
_PAST_DIRECTIONS = frozenset({"ago"})


def _report_as_of(report_dir) -> str | None:
    """The analysis date encoded in a run directory name (TICKER_YYYYMMDD_HHMMSS).

    The countdown check needs an anchor and the run directory is the only place
    that date is recorded verbatim. No anchor -> the check does not run: it must
    never guess, because a guessed anchor manufactures findings.
    """
    m = re.search(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", Path(report_dir).name)
    if not m:
        return None
    try:
        return datetime(  # noqa: DTZ001 - a calendar date, not an instant
            int(m.group(1)), int(m.group(2)), int(m.group(3))
        ).date().isoformat()
    except ValueError:
        return None


def _days_countdown_identity(
    report_text: str, as_of: str | None = None
) -> list[VerifierClaim]:
    """A stated day-count that does not follow from its own two dates.

    NVDA 2026-09-12 news.md: "NVDA's earnings optionality is 83 days away" and
    the summary row "2026-11-17 ... 83 days out". 83 is the gap from the PRIOR
    print (2026-08-26 -> 2026-11-17); from the analysis date the count was 66,
    and no tool printed 83 - the model computed it on the wrong base and nothing
    checked it.

    Runs only with an ``as_of`` anchor and only where one line carries both an
    ISO date and a spelled-out day count. Tolerance is +/-1 day: the anchor is
    the run date while a report may date its data to the prior close, and a
    false positive costs more here than a missed one-day slip (_text_metrics
    must not cry wolf).
    """
    if not report_text or not as_of:
        return []
    try:
        anchor = datetime.strptime(str(as_of), "%Y-%m-%d").date()  # noqa: DTZ007
    except (TypeError, ValueError):
        return []
    claims: list[VerifierClaim] = []
    seen: set[tuple[str, int, bool]] = set()
    for m in _DAYS_OUT_RE.finditer(report_text):
        stated = int(m.group("count"))
        direction = m.group("dir").lower()
        future = direction not in _PAST_DIRECTIONS
        # The date may sit on EITHER side of the count, and the line may carry
        # several dates (the next print and the last one). Bind the count to
        # the date that fits it: reading only a trailing date made AMZN
        # 2026-09-14 news.md look like it claimed "45 days away" for the
        # 2026-07-30 print, when the 45 belonged to the 2026-10-29 one.
        ls = report_text.rfind("\n", 0, m.start()) + 1
        le = report_text.find("\n", m.end())
        line = report_text[ls: le if le != -1 else len(report_text)]
        best: tuple[str, int, int] | None = None
        for dm in _ANY_ISO_DATE_RE.finditer(line):
            ds = dm.group(0)
            try:
                target = datetime.strptime(ds, "%Y-%m-%d").date()  # noqa: DTZ007
            except ValueError:
                continue
            expected = (target - anchor).days if future else (anchor - target).days
            # A count's direction rules out one side of the anchor: a past date
            # cannot be "45 days away" and a future date cannot be "45 days
            # ago". The only dates AMZN 2026-09-14 news.md printed next to its
            # forward count were the PRIOR print's (2026-07-30, and the
            # 2026-10-29 next print was not on the line), so the check read a
            # correct forward count as a wrong one. Wrong-side dates carry no
            # information - skip them, and only flag when no date fits.
            if expected < 0:
                continue
            if abs(stated - expected) <= 1:
                best = None
                break
            if best is None or abs(stated - expected) < best[1]:
                best = (ds, abs(stated - expected), expected)
        if best is None:
            continue
        key = (best[0], stated, future)
        if key in seen:
            continue
        seen.add(key)
        claims.append(VerifierClaim(
            claim=(
                f"day count does not follow from its own dates: '{stated} days "
                f"{direction}' for {best[0]} is {best[2]} days from "
                f"{as_of}"
            ),
            status="INTERNAL_CONFLICT",
            reason=(
                "The report states both dates and a day count, and the count "
                "does not follow from them. Quote the tool's own countdown "
                "(`in Nd` from get_earnings_calendar) instead of computing it: a "
                "wrong base date - the prior print instead of today - shifts it "
                "silently (NVDA 2026-09-12: 83 days quoted, 66 true; 83 was the "
                "gap from the 2026-08-26 print)."
            ),
        ))
    return claims


def _valuation_identity_checks(
    report_text: str, as_of: str | None = None
) -> list[VerifierClaim]:
    """Run all identity checks (DuPont, P/E, EV/net-cash, R-multiple, ratios).

    The basis-identity family (net debt, current ratio, ROA, quarter labels)
    joins the MU-origin valuation identities; each is additive and advisory.
    ``as_of`` (the run date, from the report directory) enables the date-count
    check; without it that one check is skipped, never guessed.
    """
    return (
        _dupont_identity(report_text)
        + _pe_basis_conflict(report_text)
        + _ev_net_cash_conflict(report_text)
        + _r_multiple_identity(report_text)
        + _net_debt_identity(report_text)
        + _current_ratio_identity(report_text)
        + _roa_consistency(report_text)
        + _quarter_label_consistency(report_text)
        + _days_countdown_identity(report_text, as_of)
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


# The second line every replaced-stem note carries ("# TICKER - Stem: SECTION
# UNUSABLE (generation degenerated)"); the verifier reports those stems as such
# rather than judging the note's own sentences as report claims.
_UNUSABLE_SENTINEL = "SECTION UNUSABLE"


def _unusable_note(report_text: str) -> bool:
    """Is this stem the replacement note for a degenerated generation?"""
    return bool(report_text) and _UNUSABLE_SENTINEL in report_text[:400]


def verify_evidence_call(
    llm: object,
    structured_llm: object | None,
    report_name: str,
    report_text: str,
    evidence: dict,
    backup_llm: object | None = None,
) -> ReportVerification:
    """Run the LLM pass for one analyst report (structured-aware).

    ``llm``/``structured_llm`` are LangChain-compatible instances from the
    caller (usually built via ``create_llm_client``). Reuses
    ``invoke_structured_or_freetext`` so journaling, truncation merge and
    stub retry behave exactly like the analyst path.
    """
    from tradingagents.agents.utils.structured import invoke_structured_or_freetext

    digest = _evidence_digest(evidence, report_name)
    prompt = _build_prompt(report_name, report_text, digest)

    def _render(r: ReportVerification) -> str:
        return r.model_dump_json()

    text = invoke_structured_or_freetext(
        structured_llm,
        llm,
        prompt,
        render=_render,
        agent_name=f"report_verify/{report_name}",
        backup_llm=backup_llm,
    )
    return _parse_verdict(text, report_name)


def _text_metrics(
    report_text: str, as_of: str | None = None
) -> tuple[list[VerifierClaim], list[str]]:
    """Run every text-only metric family; return (claims, errors).

    One implementation per metric, shared by the per-section pass and any
    later caller. Each family is isolated: a parser bug in one metric must
    not delete the whole verification payload (the comma-only ``[\\d,]+``
    capture — "sub-30 P/E, cheap" in a sentiment report — raised out of
    ``verify_report_dir`` and left 30 of 35 report trees with no
    ``verify_flags.json`` at all). A failing family is logged and recorded in
    the payload's ``metric_errors`` so the degradation is visible, never
    silent.
    """
    metrics = (
        ("internal_conflicts", _internal_conflicts),
        ("valuation_identity", lambda t: _valuation_identity_checks(t, as_of)),
        ("fed_cuts_contradiction", _fed_cuts_contradiction),
        ("drawdown_identity", _drawdown_identity),
        ("beat_streak_identity", _beat_streak_identity),
        ("dividend_yield_sanity", _dividend_yield_sanity),
        ("sma200_identity", _sma200_identity),
        ("fcf_unit_slip", _fcf_unit_slip),
        ("expected_band_identity", _expected_band_identity),
        ("eps_estimate_duals", _eps_estimate_duals),
        ("bollinger_band_identity", _bollinger_band_identity),
        ("sector_rank_identity", _sector_rank_identity),
        ("self_correction_artifacts", _self_correction_artifacts),
        ("price_target_identity", _price_target_identity),
        ("digit_obfuscation", _digit_obfuscation),
        ("sma200_pct_identity", _sma200_pct_identity),
        ("garch_cond_identity", _garch_cond_identity),
        ("chandelier_identity", _chandelier_identity),
        ("sum_identity", _sum_identity),
        ("ema_identity", _ema_identity),
        ("ema_trail_identity", _ema_trail_identity),
        ("double_digit_streak_identity", _double_digit_streak_identity),
        ("insider_sold_value_identity", _insider_sold_value_identity),
        ("vrp_sign_label", _vrp_sign_label),
        ("tone_claim_conflict", _tone_claim_conflict),
        ("valuation_band_conflict", _valuation_band_conflict),
    )
    claims: list[VerifierClaim] = []
    errors: list[str] = []
    for name, fn in metrics:
        try:
            claims.extend(fn(report_text))
        except Exception as exc:  # noqa: BLE001 - advisory metric: record, never raise
            logger.warning(
                "report_verifier: metric %s failed on this report (%s); "
                "claim checks from it are unavailable",
                name, exc,
            )
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    return claims, errors


def _basis_of(line: str, metric: str, raw: str) -> str:
    """The basis this printed value carries: a stated period, else its unit class.

    A period token the report prints on the same line (``_period_tag``) is the
    only basis a comparison may rely on - it is what the report itself claims.
    Without one the value is recorded as its unit class, which is the weaker
    claim a reader can still compare against another run ON THE SAME CLASS.

    Deliberately not a fraction/percent dichotomy: a ratio above 1 is ordinary
    here (P/E 135.94, EV/EBIT 32.79), so ``ratio`` carries no bound and a
    ``fraction_0_1``-style vocabulary would mislabel the common case.
    """
    tag = _period_tag(line) if line else None
    if tag:
        return tag
    if metric in _LEVEL_METRICS:
        return "level"
    unit = _unit_after(line, raw) if line else ""
    if unit == "%":
        return "percent"
    if unit in {"x", "\u00d7"}:
        return "multiple"
    return "ratio"


def _basis_registry(report_text: str, evidence_dec: set) -> list[BasisAssertion]:
    """The typed ``(metric, value, basis)`` triples this report asserts.

    Deterministic and additive: the same metric table the conflict checks use,
    the period token on the value's own line, and whether the number resolves
    to a tool leaf within the metric's tolerance. Emitted per run so two runs
    of one ticker are comparable mechanically - prose cannot be diffed for a
    basis change, because the sentences are new every time (AMZN ev/ebit 32.79
    vs -30551.06 on 2026-09-14; LULU 5.50 vs 4.40; MSFT rvol 0.30 vs 0.4220).
    """
    out: list[BasisAssertion] = []
    seen: set[tuple[str, float, str]] = set()
    for metric, (regex, _tol) in sorted(_INTERNAL_CONFLICT_METRICS.items()):
        try:
            rows = _extract_metric_values(report_text, regex, metric, with_lines=True)
        except Exception as exc:  # noqa: BLE001 - advisory: never break the payload
            logger.warning("report_verifier: basis registry skipped %s (%s)", metric, exc)
            continue
        for row in rows:
            if len(row) < 3:
                continue
            raw, value, line = row[0], row[1], row[2]
            try:
                flt = float(value)
            except (TypeError, ValueError):
                continue
            basis = _basis_of(str(line), metric, str(raw))
            key = (metric, round(flt, 6), basis)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                BasisAssertion(
                    metric=metric,
                    value=flt,
                    basis=basis,
                    source="evidence" if _matches(flt, evidence_dec) else "report",
                )
            )
    return out


def verify_report_dir(
    report_dir: str | Path,
    *,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    max_calls: int | None = None,
    stems: tuple[str, ...] | list[str] | None = None,
    llm_override: object | None = None,
    backup_llm_override: object | None = None,
) -> dict:
    """Verify every present analyst report in a report tree.

    Returns a JSON-serializable dict (the persisted ``report_verify.json``
    shape): ``{"report_dir", "verification": {stem: {overall, claims}}}``.
    ``stems`` filters which reports to run (passed for parallel per-stem
    invocation or spot-checks); a narrow run's payload only holds those
    stems. ``llm_override`` exists for tests; production builds the LLM from
    config (``TRADINGAGENTS_VERIFY_MODEL`` or the quick tier). Never raises
    for a provider failure — the affected report degrades to OVERALL UNKNOWN.
    """
    from tradingagents.agents.utils.structured import bind_structured
    from tradingagents.dataflows.config import get_config
    from tradingagents.llm_clients import create_llm_client

    cfg = get_config()
    if max_calls is None:
        try:
            max_calls = int(cfg.get("report_verify_max_calls") or 12)
        except (TypeError, ValueError):
            max_calls = 12
    if llm_override is None:
        resolve_provider = provider or str(cfg.get("llm_provider") or "")
        resolve_model = model or str(cfg.get("report_verify_model") or "") or str(
            cfg.get("quick_think_llm") or ""
        )
        client = create_llm_client(
            provider=resolve_provider,
            model=resolve_model,
            base_url=base_url or cfg.get("backend_url"),
        )
        llm = client.get_llm()
    else:
        llm = llm_override

    # Truncation-continuation backup: TRADINGAGENTS_BACKUP_LLM (or the
    # explicit override). The verifier's continuation retries must fall back
    # to the backup model like every other LLM path, not re-pay the truncated
    # quick/dirty tier (the khy 2026-09-09 stall surfaced a verifier that
    # silently continued on the same model).
    backup_llm = backup_llm_override
    if backup_llm is None and not llm_override:
        _backup_spec = str(cfg.get("backup_llm") or "").strip()
        if _backup_spec:
            try:
                _bp = provider or str(cfg.get("llm_provider") or "")
                _bm = _backup_spec
                if ":" in _backup_spec:
                    _bp, _bm = _backup_spec.split(":", 1)
                    _bp, _bm = _bp.strip(), _bm.strip()
                _bclient = create_llm_client(
                    provider=_bp,
                    model=_bm,
                    base_url=base_url or cfg.get("backend_url"),
                )
                backup_llm = _bclient.get_llm()
            except Exception as exc:  # noqa: BLE001 - advisory; degrade to same-model
                logger.warning("report_verifier: backup LLM build failed: %s", exc)
                backup_llm = None

    evidence_path = Path(report_dir) / "tool_evidence.json"
    if not evidence_path.exists():
        evidence_path = Path(report_dir) / "evidence.json"
    evidence: dict = {}
    if evidence_path.exists():
        try:
            with open(evidence_path, encoding="utf-8") as fh:
                evidence = json.load(fh)
        except (OSError, ValueError) as exc:
            logger.warning("report_verifier: cannot read %s: %s", evidence_path, exc)

    as_of = _report_as_of(report_dir)
    stem_succeeded = 0
    outcomes: dict[str, dict] = {}
    selected = tuple(stems) if stems else REPORT_STEMS
    for stem in selected:
        if stem.startswith("_"):
            continue
        report_text = _load_report(Path(report_dir), stem)
        if report_text is None:
            continue
        if stem_succeeded >= max_calls:
            outcomes[stem] = {
                "overall": "UNKNOWN",
                "claims": [],
                "reason": "max_calls budget exhausted",
                # Uniform payload shape: a consumer never has to guess whether
                # the key exists before iterating it.
                "basis": [],
            }
            continue
        if _unusable_note(report_text):
            # A stem that was REPLACED by a "SECTION UNUSABLE" note is not a
            # report to judge: its sentences describe the lost generation, so
            # every one of them reads as an unsupported claim (HPE 2026-09-14
            # fundamentals, NVDA 2026-09-15 market) and the provider call is
            # spent on prose that no analyst wrote. Report the state instead.
            outcomes[stem] = {
                "overall": "FLAG",
                "claims": [
                    VerifierClaim(
                        claim="stem replaced by an unusable-generation note",
                        status="INTERNAL_CONFLICT",
                        reason=(
                            "The generation degenerated and the stem was replaced by a "
                            "note describing what it contained (see the file). "
                            "Regenerate this stem; the deterministic evidence for it "
                            "is intact in tool_evidence.json."
                        ),
                    ).model_dump()
                ],
                "reason": "unusable-generation note",
                "basis": [],  # nothing to extract: no analyst prose in this stem
            }
            stem_succeeded += 1
            continue
        try:
            verification = verify_evidence_call(
                llm,
                bind_structured(llm, ReportVerification, "report_verify"),
                stem,
                report_text,
                evidence,
                backup_llm=backup_llm,
            )
        except Exception as exc:  # noqa: BLE001 — advisory: never raise mid-run
            logger.warning("report_verifier: report %s failed (%s); degrading to UNKNOWN", stem, exc)
            verification = ReportVerification(report=stem, overall="UNKNOWN")
        evidence_dec = _evidence_decimals(evidence, stem)
        anchored = _anchor_claims(
            verification, evidence_dec, _sentiment_anchor(evidence, stem)
        )
        text_claims, metric_errors = _text_metrics(report_text, as_of=as_of)
        all_claims = [
            *anchored.claims,
            *_macro_authority_gate(report_text, evidence, stem),
            *text_claims,
        ]
        basis = _basis_registry(report_text, evidence_dec)
        entry: dict = {
            "overall": _stem_overall(
                anchored, all_claims, deterministic_triples=len(basis)
            ),
            "claims": [c.model_dump() for c in all_claims],
            # The typed (metric, value, basis) triples this report asserts, so
            # two runs of one ticker are comparable without diffing prose.
            "basis": [b.model_dump() for b in basis],
        }
        if metric_errors:
            # A metric that cannot parse the report is recorded, never silent:
            # a comma-only regex capture ("P/E," in prose) used to raise out of
            # this function and lose the WHOLE payload for every section (30 of
            # 35 report trees had no verify_flags.json).
            entry["metric_errors"] = metric_errors
        outcomes[stem] = entry
        stem_succeeded += 1

    return {
        "report_dir": str(report_dir),
        "model": model or str(cfg.get("report_verify_model") or "") or str(
            cfg.get("quick_think_llm") or ""
        ),
        # Tree-level (no LLM): did the advertised structured debate actually
        # run? A degraded tree must be visible in verify_flags.json, not only
        # inferable from the prose.
        "debate": _debate_degradation(Path(report_dir)),
        # Tree-level (no LLM): does the execution contract still satisfy the
        # envelope rules the executor enforces? Legacy 1.0.0 trees are exempt.
        "envelope": _envelope_integrity(Path(report_dir)),
        "verification": outcomes,
    }
