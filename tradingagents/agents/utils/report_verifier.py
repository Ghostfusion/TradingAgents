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


class ReportVerification(BaseModel):
    """Verdicts for one analyst report."""

    report: str = Field(..., description="Analyst key, e.g. 'fundamentals'.")
    claims: list[VerifierClaim] = Field(default_factory=list)
    overall: Literal["PASS", "FLAG", "UNKNOWN"] = Field(
        ...,
        description=(
            "PASS = every claim grounded; FLAG = any UNSUPPORTED/CONTRADICTED/"
            "MISQUOTED/INTERNAL_CONFLICT; UNKNOWN = verifier could not run."
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
- MISQUOTED: the figures you cite ARE in the evidence, but attached to the
  wrong label / subject / context (e.g. a 92% and 58% belonging to different
  peers are transposed; a T1 target is mislabeled). If the number matches a
  leaf but the claim uses it wrongly (wrong metric, wrong sign attribution,
  wrong entity), say MISQUOTED and name the correct mapping in `reason`.

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


# ---------------------------------------------------------------------------
# Internal-consistency (cross-claim) check — deterministic
# ---------------------------------------------------------------------------

# Metric label -> regex to locate its numeric value(s) in text. Covers the
# load-bearing metrics the analyst may quote from multiple vendors (the JPM/
# GS/TJX 2026-09-08 batch: DCF fair value 80.76 vs 80.71, EPS 5.81 vs 4.79,
# market cap 141.8B vs 145.3B, ROE 53.92 vs 59.77 — all "matched some leaf"
# individually, so the per-claim anchor could not see the conflict).
_INTERNAL_CONFLICT_METRICS: dict[str, tuple[re.Pattern, float]] = {
    # Default tolerance 1%: vendor-consensus rounding (80.76 vs 80.75) is ONE
    # cluster; a real ratio conflict (ROE 53.92 vs 59.77) is TWO.
    "dcf fair value": (re.compile(r"dcf\s*(?:fair\s*)?value", re.I), 0.01),
    "eps ttm": (re.compile(r"\beps\s*(?:ttm)?\b", re.I), 0.01),
    "earnings power value": (re.compile(r"earnings\s*power\s*value|epv", re.I), 0.01),
    "market cap": (re.compile(r"market\s*cap|market\s*capitali[sz]ation", re.I), 0.01),
    "roe": (re.compile(r"\broe\b|return\s*on\s*equity", re.I), 0.01),
    "debt/equity": (re.compile(r"debt[-\s/]equity|\bd/e\b|debt\s*to\s*equity", re.I), 0.01),
    "200-day sma": (re.compile(r"200[-\s]?day\s*(?:sma|ma|moving)", re.I), 0.01),
    "insider net": (re.compile(r"insider.{0,30}net|net.{0,15}(?:insider|buying|shares)", re.I), 0.01),
    "dividend yield": (re.compile(r"dividend\s*yield", re.I), 0.01),
    "book value": (re.compile(r"book\s*value|book\s*value/share|bvps", re.I), 0.01),
    # AMZN 2026-09-09 review-loop metrics. EXACT/price-level metrics (T1/RSI/
    # ATR/bands/surprise) use a tighter 0.5% so a real target mismatch (T1
    # 265.03 vs 265.97, a 0.35% diff masked by the 1% bucket, or macdh -1.36
    # vs -1.15) still flags.
    "atr": (re.compile(r"\batr\b|average\s*true\s*range", re.I), 0.005),
    # Exact price levels: a 0.35% target mismatch (T1 265.03 vs 265.97) is a
    # real conflict, so level-type metrics use a 0.1% bucket.
    "t1": (re.compile(r"\bT1\b|2R|2xR|T\s*1\s*(?:\(|2R)", re.I), 0.001),
    "t2": (re.compile(r"\bT2\b|3R|3xR", re.I), 0.001),
    "macd histogram": (re.compile(r"macd\s*h|macdh|histogram", re.I), 0.005),
    "rvol": (re.compile(r"\brvol\b|relative\s*volume", re.I), 0.005),
    "williams_r": (re.compile(r"williams", re.I), 0.005),
    "stochastic": (re.compile(r"stoch", re.I), 0.005),
    "rsi": (re.compile(r"\brsi\b|relative\s*strength\s*index", re.I), 0.005),
    "aws growth": (re.compile(r"aws.{0,10}(?:growth|yoy)|yoy.{0,10}aws", re.I), 0.005),
    "hy oas": (re.compile(r"hy[-\s]?oas|high\s*yield.{0,20}oas", re.I), 0.005),
    "forward peg": (re.compile(r"peg|forward\s*p/e.{0,6}growth|price.{0,6}earnings.{0,6}growth", re.I), 0.005),
    "ttm p/e": (re.compile(r"ttm\s*p/e|p/e\s*ttm|pe\s*ttm", re.I), 0.005),
    # MU 2026-09-09 review-loop metrics: Altman Z 24.60 (body) vs 25.70
    # (summary + get_analyst_verdict leaf 25.70) — a provider-sourced score
    # must not be quoted at two values in one report.
    "altman z": (re.compile(r"\baltman\s*z\b|altman\s*z-score", re.I), 0.005),
}

# A dollar figure in the report, with optional K/M/B suffix, e.g. "80.76",
# "$80.60", "79.78B", "5.7B". Used to extract the numeric value attached to a
# metric. Returns (value, unit_multiplier) or None.
_DOLLAR_RE = re.compile(r"(?<![\(\w])\$?\s*(\d+(?:\.\d+)?)\s*([KMBkmb])?")

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
# Requirement: (phrases) -> (tools that satisfy the line). Any line
# containing a listed phrase must have at least one leaf whose tool is in
# the set, or a leaf whose content contains a listed phrase. Otherwise the
# line is UNSUPPORTED — deterministic, independent of the LLM pass.
_MACRO_AUTHORITY_PHRASES_TOOLS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("polymarket", "prediction market"), ("get_prediction_markets",)),
    (
        ("no rate cuts", "no fed rate cuts", "cut probability", "hike probability",
         "fomc", "fed watch"),
        ("get_prediction_markets", "get_fed_watch"),
    ),
    # TGA balance ≠ RRP: a get_tga_balance leaf must not satisfy an RRP
    # claim (SKHY 2026-09-09: "RRP at 0.432B" passed the old mapping because
    # TGA was called). RRP/reverse-repo need get_macro_indicators or a leaf
    # whose content actually carries the term.
    (("rrp", "reverse repo"), ("get_macro_indicators",)),
    (("10y", "10-year"), ("get_macro_indicators", "get_treasury_curve")),
    (("wti", "oil price", "crude"), ("get_macro_indicators", "get_economic_calendar")),
)


# Extra scale: a *_window / (18) / 30d -style label can sit between a metric
# label and its value; 1 line = up to 40 chars after the label.
_METRIC_WINDOW = 40


def _macro_authority_gate(report_text: str, evidence: dict, analyst_key: str) -> list[VerifierClaim]:
    """Deterministic: market-implied/macro terms need a matching tool leaf.

    The MACRO MUSTS prompt pins the tools, but prompt policy alone is not
    enforced: the SKHY 2026-09-09 news.md carried Polymarket 93% no-cut,
    10Y 4.78 FRED print and WTI 91.48 with no ``get_prediction_markets`` /
    ``get_macro_indicators`` leaf anywhere in the document. The LLM pass may
    ground the wording against other leaves; this gate holds each such line
    to the pinned tool group regardless. Advisory: adds UNSUPPORTED claims,
    never edits the report.
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
        for phrases, tools in _MACRO_AUTHORITY_PHRASES_TOOLS:
            present = [p for p in phrases if p in low]
            if not present:
                continue
            # Satisfied when a pinned tool leaf exists, OR a leaf content
            # itself carries a listed phrase (e.g. a fetched article).
            satisfied = bool(leaf_tools & set(tools)) or any(p in leaf_text_low for p in present)
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


def _extract_metric_values(text: str, regex: re.Pattern) -> list[tuple[str, float]]:
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
    for line in text.splitlines():
        for m in regex.finditer(line):
            # Skip a label immediately followed by a parenthetical multiplier
            # like "T1(2R)" — 2R is a reward multiple, not the metric's value.
            tail = line[m.end():m.end() + _METRIC_WINDOW]
            stripped = re.sub(r"^\([^)]*\)", "", tail.strip())
            for mnum in _DOLLAR_RE.finditer(stripped):
                num_s, unit = mnum.group(1), (mnum.group(2) or "")
                try:
                    num = float(num_s)
                except ValueError:
                    continue
                mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(unit.upper(), 1.0)
                out.append((stripped[max(0, mnum.start() - 6):mnum.end()].strip(), num * mult))
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
    for label, (regex, tol) in _INTERNAL_CONFLICT_METRICS.items():
        vals = _extract_metric_values(report_text, regex)
        # Group near-equal values; flag when >1 distinct cluster.
        distinct: list[tuple[float, str]] = []
        for raw, v in vals:
            bucket = next(
                (b for b in distinct if abs(b[0] - v) / max(abs(b[0]), abs(v), 1e-9) <= tol),
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
# Valuation-identity checks (deterministic; MU 2026-09-09 review loop)
# ---------------------------------------------------------------------------
# The MU fundamentals.md mixed basis and broke identities the same report
# asserted: "P/E 135.94" (provider, annual-EPS basis) vs "TTM EPS $44.17" +
# price $1,027.77 (=> P/E 23.3); "RoE ~35%" decomposed from inputs that
# multiply to 66.5%; "EV $1.166T" while "net CASH $19.65B" with
# "Market cap $1.16T" (EV must be below the cap). These are not
# number-vs-vendor conflicts — they are internal identities broken inside
# ONE report. Deterministic identity checks below; advisory, never rewrite.

_PE_RE = re.compile(r"\bP\s*/\s*E\b\s*:?\s*\**\s*([\d,]+(?:\.\d+)?)")
_PRICE_RE = re.compile(r"(?i)(?:last|price|latest close)\s*:?\s*\**\s*\$?\s*\**\s*([\d,]+\.\d{2})|at\s+\$([\d,]+\.\d{2})")
_TTM_EPS_RE = re.compile(r"(?i)\beps\b[^0-9]{0,40}ttm[^0-9]{0,40}\$\s*\**\s*([\d,]+(?:\.\d+)?)")
_ROE_RE = re.compile(r"\bROE\b\s*\**\s*~?\s*([\d.]+)\s*%")
_NET_MARGIN_RE = re.compile(r"net_margin\s*\**\s*([\d.]+)")
_AT_RE = re.compile(r"asset_turnover\s*\**\s*([\d.]+)")
_EM_RE = re.compile(r"equity_multiplier\s*\**\s*([\d.]+)")
_EV_RE = re.compile(r"\bEV\b(?!\s*/)[::]?\s*\**\s*\$?\s*\**\s*([\d,]+)")
_MCAP_RE = re.compile(r"(?i)market\s*cap[^0-9]{0,45}\$?\s*\**\s*([\d,]+)")
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
        for m in _ROE_RE.finditer(line):
            roe = float(m.group(1))
            if roe <= 0:
                continue
            if abs(product_pct - roe) / max(abs(roe), 1e-9) > 0.2:
                return [
                    VerifierClaim(
                        claim="DuPont identity: net_margin x asset_turnover x equity_multiplier "
                              f"= {product_pct:.1f}% but ROE quoted at {roe:.1f}% on the same line",
                        status="INTERNAL_CONFLICT",
                        reason=(
                            "The decomposition inputs on the DuPont line do not multiply to "
                            "the ROE the same line states (MU 2026-09-09: inputs give 66.4% "
                            "while text claimed ~35%). Fix the decomposed value or label it "
                            "a fuzzy estimate."
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
                        "quotes (MU 2026-09-09: provider P/E 135.9 is on annual FY25 EPS, "
                        "not the $44.17 TTM the report cites). Reconcile the basis."
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
                    "balance-sheet row (MU 2026-09-09: EV 1.17T vs expected 1.14T). "
                    "Reconcile EV to one basis."
                ),
            )
        ]
    return []


# --- R-multiple (2R/3R target) identity — market-side. ---------------------
# A swing framework should quote 2R/3R targets that satisfy
#     targetN = entry + N * (entry - stop)
# from the SAME entry/stop pair. The MU 2026-09-09 market.md quoted
# "2R/3R targets 1357.69 / 1521.68" while get_swing_set (evidence) gives
# entry 1027.77 / stop 862.81 / 2R 1357.6891 / 3R 1522.6486 — the quoted
# 3R is a 0.06% offset typo (1521.68 vs 1522.65). Catch it deterministically.
_ENTRY_RE = re.compile(r"(?i)\bentry\b[^0-9]{0,12}\$?\s*\**\s*([\d,]+\.\d+)")
_STOP_RE = re.compile(r"(?i)\b(?:struct(?:ure)?\s*)?stop\b[^0-9]{0,12}\$?\s*\**\s*([\d,]+\.\d+)")
# "2R" / "3R" / "T1(2R)" / "T2(3R)" label followed by its value(s). A swing
# line often quotes a pair "2R/3R targets 1357.69 / 1521.68" — group 2 is the
# label-specific value (the one after "/" for the 3R in a "A / B" pair).
_RMULT_RE = re.compile(
    r"\b(2R|3R|T1|T2)\b[^0-9]{0,8}\s*:?\s*\$?\s*\**\s*([\d,]+\.\d+)(?:\s*/\s*([\d,]+\.\d+))?"
)

_RMULT_TOL = 0.002  # 0.2% — a real typo (0.06%) is far under; framework drift is not.


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
    en = _ENTRY_RE.search(report_text)
    if not en:
        return []
    entry = float(en.group(1).replace(",", ""))
    global_stop: float | None = None
    gs = _STOP_RE.search(report_text)
    if gs:
        global_stop = float(gs.group(1).replace(",", ""))
    out: list[VerifierClaim] = []
    for line in report_text.splitlines():
        rs = list(_RMULT_RE.finditer(line))
        if not rs:
            continue
        ls = _STOP_RE.search(line)
        if ls:
            line_stop = float(ls.group(1).replace(",", ""))
        elif global_stop is not None:
            line_stop = global_stop
        else:
            continue
        risk = entry - line_stop
        if risk <= 0:
            continue
        for m in rs:
            quoted = _rmult_value(m)
            mult = 2 if m.group(1).upper() in ("2R", "T1") else 3
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
                            "entry/stop pair on its own line (MU 2026-09-09: 3R 1521.68 "
                            "vs get_swing_set 1522.65 for structure stop 862.81). "
                            "Re-derive from that pair."
                        ),
                    )
                )
    return out


def _valuation_identity_checks(report_text: str) -> list[VerifierClaim]:
    """Run all identity checks (DuPont, P/E basis, EV/net-cash, R-multiple)."""
    return (
        _dupont_identity(report_text)
        + _pe_basis_conflict(report_text)
        + _ev_net_cash_conflict(report_text)
        + _r_multiple_identity(report_text)
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


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
                backup_llm=backup_llm,
            )
        except Exception as exc:  # noqa: BLE001 — advisory: never raise mid-run
            logger.warning("report_verifier: report %s failed (%s); degrading to UNKNOWN", stem, exc)
            verification = ReportVerification(report=stem, overall="UNKNOWN")
        anchored = _anchor_claims(verification, _evidence_decimals(evidence, stem))
        conflicts = _internal_conflicts(report_text)
        macro_gate = _macro_authority_gate(report_text, evidence, stem)
        identities = _valuation_identity_checks(report_text)
        all_claims = anchored.claims + conflicts + macro_gate + identities
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
