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
    "eps ttm":(re.compile(r"\beps\s*(\(|\s)ttm\s*(?:\))?(?!\s*growth)", re.I), 0.01),
    "diluted eps": (re.compile(r"diluted\s*eps|eps\s*\(diluted\)", re.I), 0.005),
        # DELL 2026-09-10 news.md: body quoted 'EPS actual 7.04' and the
        # summary row 'EPS actual 7.00' (both labeled Finnhub, same quarter) —
        # a 0.6% dual value. Level-type metrics use a 0.5% bucket.


        "eps actual":(re.compile(r"\beps\s+actual\b", re.I), 0.005),
        "eps estimate":(re.compile(r"\beps\s+actual\b.*?\best(?:imate)?\b", re.I), 0.002),
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
    "ema20":(re.compile(r"\bema\s*20\b", re.I), 0.005),
        "atr":(re.compile(r"(?<![A-Za-z0-9\-])atr\b(?!\s*:\s*\d+\s*-)|average\s*true\s*range", re.I),0.005),
    # Exact price levels: a 0.35% target mismatch (T1 265.03 vs 265.97) is a
    # real conflict, so level-type metrics use a 0.1% bucket.
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

    "scenario dcf bear": (re.compile(r"(?i)(?:scenario[\s-]*dcf.{0,60}?bear\b|bear\s*(?:\||:|\$|\d))", re.I),0.001),
    "scenario dcf base": (re.compile(r"scenario[\s-]*dcf.{0,40}?base\b|base\s*(?:\||:|=|/|\$|\d|$)", re.I), 0.001),
    "scenario dcf bull": (re.compile(r"scenario[\s-]*dcf.{0,40}?bull\b|bull\s*(?:\||:|=|/|\$|\d|$)", re.I), 0.001),
    "beta": (re.compile(r"\bbeta\b", re.I), 0.05),
    "cash conversion": (re.compile(r"cash\s*conversion|cash_conversion|ocf\s*/\s*ni", re.I), 0.02),
    # WDC 2026-09-10 fundamentals review loop: current ratio 10.87
    # (get_balance_sheet_health) vs 1.329 (vendor currentRatio) in one
    # report - a computed-vs-provider ratio conflict must flag.
    "current ratio": (re.compile(r"current\s*ratio|\bcurrentRatio\b|\bCR\b", re.I), 0.20),
}

# A dollar figure in the report, with optional K/M/B suffix, e.g. "80.76",
# "$80.60", "79.78B", "5.7B". Used to extract the numeric value attached to a
# metric. Returns (value, unit_multiplier) or None.
_DOLLAR_RE = re.compile(r"(?<![\w])\$?\s*(\d+(?:\.\d+)?)\s*([KMBkmb])?")

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


_FCF_AMT = re.compile(
    r"(?i)\bfcf\b[^0-9$]{0,12}\$?\s*([\d,]+(?:\.\d+)?)\s*([KMBkmb]?)"
)
_FCF_AMT_FE = re.compile(
    r"(?i)free\s+cash\s+flow[^0-9$]{0,12}\$?\s*([\d,]+(?:\.\d+)?)\s*([KMBkmb]?)"
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


def _dividend_yield_sanity(report_text: str) -> list[VerifierClaim]:
    """A quoted dividend yield must not contradict the same report's
    dividend-per-share and price.

    MU 2026-09-10 fundamentals review loop: the report quoted 'TTM yield 4.91%
    per get_basic_financials' while its own dividend-per-share $0.15 and price
    ~$983 imply 0.061% (4 x 0.15 / 982.95) - a stale/unit-scaled vendor field.
    A >5x deviation is an INTERNAL_CONFLICT (quarterly-payment convention).
    """
    if not report_text:
        return []
    dps_m = _DPS_RE.search(report_text)
    price = _dd_price(report_text)
    if not (dps_m and price is not None):
        return []
    try:
        dps = float(dps_m.group(1))
    except ValueError:
        return []
    annual = 4.0 * dps
    implied = annual / price * 100.0
    if implied <= 0 or annual <= 0:
        return []
    for m in _DIV_YIELD_RE.finditer(report_text):
        try:
            quoted = float(m.group(1))
        except ValueError:
            continue
        if quoted > 5.0 * implied:
            return [VerifierClaim(
                claim=f"dividend yield {quoted:.2f}% vs {annual:.2f}/share / price "
                      f"{price:,.2f} => {implied:.3f}% implied",
                status="INTERNAL_CONFLICT",
                reason=(
                    "Quoted dividend yield contradicts the same report's dividend-per-share "
                    "and price - stale/unit-scaled vendor field (MU 2026-09-10: 4.91% vs "
                    "0.061% implied)."
                ),
            )]
    return []


_DD_CLAIM = re.compile(
    r"\b(?:the\s+)?(\d+|[a-z]+)\s+(?:straight|consecutive)\s+"
    r"double[- ]digit\s+(?:eps\s+)?beats?\b", re.I)
_DD_WORDS = {"three": 3, "third": 3, "four": 4, "fourth": 4,
             "five": 5, "fifth": 5, "six": 6, "sixth": 6,
             "seven": 7, "seventh": 7, "eight": 8, "eighth": 8}
_DD_PCT = re.compile(r"surprise_pct\s*=\s*([\d.]+)|\+\s*([\d.]+)%")


def _parse_dd_count(raw: str) -> int | None:
    if raw.isdigit():
        return int(raw)
    return _DD_WORDS.get(raw.lower())


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
    r"(?i)\bsold\s+([\d,]+)\s*(?:sh|shares|shs)?[\s\S]{0,30}?"
    r"\bat\s+([\d.]+)\s*(?:[-\u2013]\s*([\d.]+))?"
    r"\s*(?:\(|\s)(?:value\s*)?[$]?\s*"
    r"([\d,]+(?:\.\d+)?)\s*([kmb]?)\b"
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


_SMA200_VAL_RE = re.compile(r"(?i)200[-\s]?day[^0-9]{0,14}?([\d,]+(?:\.\d+)?)")
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

_SELF_CORRECTION = re.compile(
    r"(?:\bcorrected?\s*:|\bcorrection\s*[\u2014-]|\b\.\.\.\s*(?:corrected?|correction))"
)


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
    hits = [_SELF_CORRECTION.search(ln) for ln in report_text.splitlines()]
    found = [m.group(0) for m in hits if m]
    if not found:
        return []
    return [VerifierClaim(
        claim="self-correction artifacts present in report text: "
              + ", ".join(sorted(set(found))),
        status="INTERNAL_CONFLICT",
        reason=(
            "The report contains inline self-correction markers (e.g. "
            "'9.87 ... corrected: 4.8', '172.346 ... correction - 154.3360'); "
            "these are the model retyping a figure mid-generation and leaking "
            "the repair into the artifact. Emit only the final corrected value; "
            "never include the wrong value with a 'corrected:' caveat (HPE "
            "2026-09-10)."
        ),
    )]


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
    if not _BAND_ZERO.search(report_text):
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
    _NUM_WORDS = {"two":2,"three":3,"four":4,"five":5,"six":6}
    g = m.group(1)
    claimed = int(g) if g.isdigit() else _NUM_WORDS.get(g.lower())
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
                            "entry/stop pair on its own line. Re-derive from that "
                            "pair (rule pinned by the MU 2026-09-09 review loop)."
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
        fed_cuts = _fed_cuts_contradiction(report_text)
        drawdown = _drawdown_identity(report_text)
        beat_streak = _beat_streak_identity(report_text)
        dividend_check = _dividend_yield_sanity(report_text)
        sma200 = _sma200_identity(report_text)
        fcf_slip = _fcf_unit_slip(report_text)
        expected_band = _expected_band_identity(report_text)
        eps_duals = _eps_estimate_duals(report_text)
        boll_bands = _bollinger_band_identity(report_text)
        sector_rank = _sector_rank_identity(report_text)
        self_corr = _self_correction_artifacts(report_text)
        dd_streak = _double_digit_streak_identity(report_text)
        insider_value = _insider_sold_value_identity(report_text)
        vrp_check = _vrp_sign_label(report_text)
        all_claims = anchored.claims + conflicts + macro_gate + identities + fed_cuts + drawdown + beat_streak + dividend_check + vrp_check + sma200 + fcf_slip + expected_band + eps_duals + boll_bands + sector_rank + self_corr + dd_streak + insider_value
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
