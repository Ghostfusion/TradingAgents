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
provider failure degrades to "verifier unavailable" (the caller reports
UNKNOWN and returns 0), exactly like ``llm_failure_journal`` degrades the
structured-invoke path — one failed call must never kill a run.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

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
_UNIT_SCALES = (1.0, 1e3, 1e6, 1e9, 1e12)


def _float_tokens(text: str) -> set:
    """Distinct decimal numbers in ``text`` (the figures that carry signal;
    bare integers are too noisy for a cheap grounding check)."""
    out = set()
    for m in _DEC_RE.finditer(text):
        try:
            out.add(float(m.group()))
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
    status: Literal["GROUNDED", "UNSUPPORTED", "CONTRADICTED", "INTERNAL_CONFLICT"] = Field(
        ...,
        description=(
            "GROUNDED: the claim's specifics (figures, direction, state) are "
            "present in the evidence leaves; UNSUPPORTED: the claim asserts "
            "specifics the evidence does not contain; CONTRADICTED: evidence "
            "contains an opposing value/state; INTERNAL_CONFLICT: the same "
            "metric is asserted at conflicting values within this one report."
        ),
    )
    reason: str = Field(
        ...,
        description="One line: which leaf tool/value supports or refutes the claim, or 'no leaf evidence'.",
    )


class ReportVerification(BaseModel):
    """Verdicts for one analyst report."""

    report: str = Field(..., description="Analyst key, e.g. 'fundamentals'.")
    claims: list[VerifierClaim] = Field(default_factory=list)
    overall: Literal["PASS", "FLAG", "UNKNOWN"] = Field(
        ...,
        description=(
            "PASS = every claim grounded; FLAG = any UNSUPPORTED/CONTRADICTED; "
            "UNKNOWN = verifier could not run."
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
    return out


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

Rules:
- Base every verdict on the evidence block ONLY. Do not use outside
  knowledge to rescue or condemn a claim.
- A number must match an evidence number (same value, sign matters).
  If the report says a figure the evidence lacks, that claim is
  UNSUPPORTED even if the rest sounds plausible.
- Qualitative framing ("strong momentum", "compelling") is not a fact;
  do not flag it.
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
    if any(c.get("status") in ("UNSUPPORTED", "CONTRADICTED") for c in claims):
        return "FLAG"
    return "PASS"


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


def _anchor_claims(verification: ReportVerification, evidence_dec: set) -> ReportVerification:
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
        if c.status == "UNSUPPORTED" and decs and all(_matches(d, evidence_dec) for d in decs):
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
        if any(c.status in ("UNSUPPORTED", "CONTRADICTED", "INTERNAL_CONFLICT") for c in anchored)
        else "PASS"
    )
    return ReportVerification(report=verification.report, claims=anchored, overall=overall)


# ---------------------------------------------------------------------------
# Internal-consistency (cross-claim) check — deterministic
# ---------------------------------------------------------------------------

# Metric label -> regex to locate its numeric value(s) in text. Covers the
# load-bearing metrics the analyst may quote from multiple vendors (the JPM/
# GS/TJX 2026-09-08 batch: DCF fair value 80.76 vs 80.71, EPS 5.81 vs 4.79,
# market cap 141.8B vs 145.3B, ROE 53.92 vs 59.77 — all "matched some leaf"
# individually, so the per-claim anchor could not see the conflict).
_INTERNAL_CONFLICT_METRICS: dict[str, re.Pattern] = {
    "dcf fair value": re.compile(r"dcf\s*(?:fair\s*)?value", re.I),
    "eps ttm": re.compile(r"\beps\s*(?:ttm)?\b", re.I),
    "earnings power value": re.compile(r"earnings\s*power\s*value|epv", re.I),
    "market cap": re.compile(r"market\s*cap|market\s*capitali[sz]ation", re.I),
    "roe": re.compile(r"\broe\b|return\s*on\s*equity", re.I),
    "debt/equity": re.compile(r"debt[-\s/]equity|\bd/e\b|debt\s*to\s*equity", re.I),
    "200-day sma": re.compile(r"200[-\s]?day\s*(?:sma|ma|moving)", re.I),
    "insider net": re.compile(r"insider.{0,30}net|net.{0,15}(?:insider|buying|shares)", re.I),
    "dividend yield": re.compile(r"dividend\s*yield", re.I),
    "book value": re.compile(r"book\s*value|book\s*value/share|bvps", re.I),
}

# A dollar figure in the report, with optional K/M/B suffix, e.g. "80.76",
# "$80.60", "79.78B", "5.7B". Used to extract the numeric value attached to a
# metric. Returns (value, unit_multiplier) or None.
_DOLLAR_RE = re.compile(r"\$?\s*(\d+(?:\.\d+)?)\s*([KMBkmb])?")


def _extract_metric_values(text: str, regex: re.Pattern) -> list[tuple[str, float]]:
    """All ``(raw_value_str, numeric_value)`` occurrences for one metric label.

    The value is read from the window immediately surrounding the metric
    label (up to 24 chars each side) so a number belonging to a *different*
    metric on the same line is not misattributed (e.g. "ROE 0.18 and EPS 2.41"
    must not attach 2.41 to ROE). Dollar magnitudes are normalised to plain
    units (79.78B -> 7.978e10) so 79.78B and 5.7B compare at one scale.
    """
    out: list[tuple[str, float]] = []
    for line in text.splitlines():
        m = regex.search(line)
        if not m:
            continue
        # Prefer the first number after the metric label (the metric's value).
        tail = line[m.end():m.end() + 24]
        for mnum in _DOLLAR_RE.finditer(tail):
            num_s, unit = mnum.group(1), (mnum.group(2) or "")
            try:
                num = float(num_s)
            except ValueError:
                continue
            mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(unit.upper(), 1.0)
            out.append((tail[max(0, mnum.start() - 6):mnum.end()].strip(), num * mult))
            break
    return out


def _internal_conflicts(report_text: str) -> list[VerifierClaim]:
    """Find the same metric asserted at conflicting values within ONE report.

    The per-claim anchor checks each claim against the tool evidence, so it
    cannot see that claim A says "DCF 80.76" and claim B says "DCF 80.60" —
    both individually "grounded in some leaf". This pass pairs occurrences of
    the same metric label and flags materially different values (>1%
    relative) as an INTERNAL_CONFLICT. Advisory; never rewrites.
    """
    if not report_text:
        return []
    conflicts: list[VerifierClaim] = []
    for label, regex in _INTERNAL_CONFLICT_METRICS.items():
        vals = _extract_metric_values(report_text, regex)
        # Group near-equal values; flag when >1 distinct cluster.
        distinct: list[tuple[float, str]] = []
        for raw, v in vals:
            bucket = next(
                (b for b in distinct if abs(b[0] - v) / max(abs(b[0]), abs(v), 1e-9) <= 0.01),
                None,
            )
            if bucket is None:
                distinct.append((v, raw))
            else:
                # keep the first raw string for the group
                pass
        if len(distinct) >= 2:
            shown = "; ".join(f"{raw}" for _, raw in distinct)
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
# Orchestration
# ---------------------------------------------------------------------------


def verify_evidence_call(
    llm: object,
    structured_llm: object | None,
    report_name: str,
    report_text: str,
    evidence: dict,
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
    )
    return _parse_verdict(text, report_name)


def verify_report_dir(
    report_dir: str | Path,
    *,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    max_calls: int | None = None,
    stems: tuple[str, ...] | list[str] | None = None,
    llm_override: object | None = None,
) -> dict:
    """Verify every present analyst report in a report tree.

    Returns a JSON-serializable dict (the persisted ``report_verify.json``
    shape): ``{"report_dir", "verification": {stem: {overall, claims}}}``.
    ``stems`` filters which reports run (passed for parallel per-stem
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
            }
            continue
        try:
            verification = verify_evidence_call(
                llm,
                bind_structured(llm, ReportVerification, "report_verify"),
                stem,
                report_text,
                evidence,
            )
        except Exception as exc:  # noqa: BLE001 — advisory: never raise mid-run
            logger.warning("report_verifier: report %s failed (%s); degrading to UNKNOWN", stem, exc)
            verification = ReportVerification(report=stem, overall="UNKNOWN")
        anchored = _anchor_claims(verification, _evidence_decimals(evidence, stem))
        conflicts = _internal_conflicts(report_text)
        all_claims = anchored.claims + conflicts
        overall = (
            "FLAG"
            if any(c.status in ("UNSUPPORTED", "CONTRADICTED", "INTERNAL_CONFLICT") for c in all_claims)
            else anchored.overall
        )
        outcomes[stem] = {
            "overall": overall,
            "claims": [c.model_dump() for c in all_claims],
        }
        stem_succeeded += 1

    return {
        "report_dir": str(report_dir),
        "model": model or str(cfg.get("report_verify_model") or "") or str(
            cfg.get("quick_think_llm") or ""
        ),
        "verification": outcomes,
    }
