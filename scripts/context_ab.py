#!/usr/bin/env python3
"""Context A/B: does sending MORE computed results make the agent more accurate?

Two paired experiments, scored per item so the two conditions are matched
(same items, same questions, only the context differs):

* **tools** -- tool selection with the full surface vs a shortlist. Items are
  (claim, tool) pairs taken from each tool's own schema text, so the intended
  tool is defined by the tool, not authored here. Condition A = the intended
  tool plus ``k-1`` distractors from the same surface; condition B = the whole
  surface. Score = did the model select the intended tool.
* **reads** -- does an injected computed block improve the answer? Items are
  questions whose ground truth is a number the block contains; the blocks are
  rendered by the same pure builders the graph uses (``trade_plan.measured_inputs``
  + ``build_trade_plan``, ``risk_governor.build_risk_snapshot``), and the expected
  numbers are parsed back out of the render, so the harness cannot drift from
  the real card. Condition A = block present, condition B = block absent. Score =
  the answer contains the block's numbers; a figure in the answer that appears in
  no block is counted as a fabrication.

Both report an exact McNemar test (paired, two-sided) plus the cost side -- tools
presented, characters of context -- which is the point of the exercise: accuracy
is not monotonic in context size, and the useful number is where it turns.

Hermetic by default, in the same shape as ``scripts/debate_ab_harness.py``: the
"producer" (the model call) is injected, so scoring can be exercised with no
vendor and no key. ``--demo`` uses synthetic producers and says so in the report;
``--live`` builds one from the repo's LLM client factory and needs an API key.

    py -3.12 scripts/context_ab.py --list
    py -3.12 scripts/context_ab.py --experiment tools --demo --limit 40
    py -3.12 scripts/context_ab.py --experiment both --live --provider deepseek \\
        --model deepseek-chat --limit 40 --json context_ab.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

# A producer answers one item under one condition. Tool producers get the
# candidate tool objects and return the chosen name (or None); read producers
# get the question plus the context text that condition allows, and return prose.
ToolProducer = Callable[[str, Sequence], "str | None"]
ReadProducer = Callable[[str, str], str]

TRIGGER_CLAIM_RE = re.compile(r"before any ['\"“]?([^'\"”.]{8,90})", re.IGNORECASE)
NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?%?")
CARD_STOP_RE = re.compile(r"Unified stop \(invalidation\): ([0-9][0-9.,]*)")
CARD_T1_RE = re.compile(r"Tiers: T1 ([0-9][0-9.,]*)")


# ---------------------------------------------------------------------------
# items
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolItem:
    surface: str
    tool: str
    claim: str
    question: str


@dataclass(frozen=True)
class ReadItem:
    name: str
    question: str
    block: str
    required: tuple[str, ...]

    def without_block(self) -> str:
        return self.question


@dataclass
class Outcome:
    """One item under both conditions."""

    item: str
    a_ok: bool
    b_ok: bool
    a_answer: str = ""
    b_answer: str = ""


@dataclass
class Experiment:
    name: str
    condition_a: str
    condition_b: str
    outcomes: list[Outcome] = field(default_factory=list)
    cost_a: int = 0
    cost_b: int = 0
    extra: dict = field(default_factory=dict)

    def b(self) -> int:
        return sum(1 for o in self.outcomes if o.a_ok and not o.b_ok)

    def c(self) -> int:
        return sum(1 for o in self.outcomes if o.b_ok and not o.a_ok)

    def accuracy(self, which: str) -> float:
        if not self.outcomes:
            return float("nan")
        return sum(o.a_ok if which == "a" else o.b_ok for o in self.outcomes) / len(self.outcomes)


def _surfaces() -> dict[str, list]:
    """The agent surfaces, as objects (the same source the binding gate reads)."""
    from tradingagents.agents.toolsets import analyst_toolset
    from tradingagents.agents.utils import risk_tool_loop

    risk_tool_loop._build_lists()
    return {
        "market": analyst_toolset("market"),
        "news": analyst_toolset("news"),
        "fundamentals": analyst_toolset("fundamentals"),
        "risk debators": risk_tool_loop.RISK_DEBATOR_TOOLS,
        "trader": risk_tool_loop.TRADER_TOOLS,
    }


def _claim_for(tool) -> str:
    """The claim class a tool's own schema text tells the model to cite it for."""
    text = (getattr(tool, "description", "") or "").strip().replace("\n", " ")
    text = text.replace(tool.name, "this read")
    m = TRIGGER_CLAIM_RE.search(text)
    if m:
        return m.group(1).strip().strip(".").strip()
    first = re.split(r"(?<=[.!?])\s", text)[0] if text else ""
    return (first[:110] or f"the read {tool.name} returns").strip()


def _purpose_for(tool) -> str:
    """The tool's own summary sentence, used as the selection question's premise.

    The tool's name is scrubbed: a question that names the answer would measure
    copying, not selection.
    """
    text = (getattr(tool, "description", "") or "").strip().replace("\n", " ")
    text = text.replace(tool.name, "this read")
    first = re.split(r"(?<=[.!?])\s", text)[0] if text else ""
    return (first[:150] or f"the read {tool.name} returns").strip()


def _question_for(tool, claim: str) -> str:
    return (
        f"A decision needs this read: {_purpose_for(tool)} "
        f"It has to support the claim: {claim}. "
        "Which single tool do you call first? Answer with the tool call only."
    )


def tool_items(limit: int = 25, seed: int = 7) -> list[ToolItem]:
    """Deterministic (claim, tool) items drawn from the live surfaces."""
    out: list[ToolItem] = []
    for surface, tools in _surfaces().items():
        for tool in tools:
            claim = _claim_for(tool)
            out.append(
                ToolItem(
                    surface=surface,
                    tool=tool.name,
                    claim=claim,
                    question=_question_for(tool, claim),
                )
            )
    rng = random.Random(seed)
    rng.shuffle(out)
    return out[:limit] if limit else out


def shortlist(tools: Sequence, intended: str, k: int = 8, seed: int = 7) -> list:
    """The intended tool plus k-1 distractors from the same surface."""
    names = [t.name for t in tools]
    assert intended in names, f"{intended} is not on this surface"
    rest = [n for n in names if n != intended]
    rng = random.Random(f"{seed}:{intended}")
    picked = rng.sample(rest, min(k - 1, len(rest)))
    picked.append(intended)
    picked.sort()
    return [t for t in tools if t.name in set(picked)]


def _fixture_closes() -> list[float]:
    rng = random.Random(11)
    closes = [100.0]
    for _ in range(160):
        closes.append(max(1.0, closes[-1] * (1 + rng.gauss(0, 0.012))))
    return closes


CARD_FACTS: tuple[tuple[str, str, str], ...] = (
    ("unified invalidation stop", r"Unified stop \(invalidation\): ([0-9][0-9.,]*)",
     "State the unified invalidation stop for this trade, as a number."),
    ("first tier target", r"Tiers: T1 ([0-9][0-9.,]*)",
     "State the first tier target for this trade, as a number."),
    ("second tier target", r"T2 ([0-9][0-9.,]*)",
     "State the second tier target for this trade, as a number."),
    ("weighted average entry", r"Weighted avg entry: ([0-9][0-9.,]*)",
     "State the weighted average entry for the scale-in plan, as a number."),
    ("first tranche price", r"P1 ([0-9][0-9.,]*)",
     "State the first tranche price, as a number."),
    ("capital at risk", r"capital-at-risk ([0-9.]+%|[0-9.]+) of account",
     "State the capital at risk as a share of the account."),
    ("breakeven trigger price", r"Breakeven rule \(([a-z]+)\): price ([0-9][0-9.,]*)",
     "State the price at which the stop moves to breakeven, as a number."),
)

SNAPSHOT_FACTS: tuple[tuple[str, str, str], ...] = (
    ("risk verdict", r"verdict=(\w+)", "State the risk verdict."),
    ("proposed size", r"size=([0-9.]+%)", "State the proposed position size."),
    ("book drawdown", r"dd=([0-9.]+%)", "State the book drawdown this decision is measured against."),
    ("stop distance", r"stop=([0-9.]+%)", "State the stop distance used for sizing."),
)


def _items_from_block(block: str, facts, prefix: str) -> list[ReadItem]:
    out: list[ReadItem] = []
    for name, pattern, question in facts:
        m = re.search(pattern, block)
        if not m:
            continue  # the render did not carry this row: nothing to measure
        required = tuple(g for g in m.groups() if g)
        out.append(ReadItem(name=f"{prefix}: {name}", question=question, block=block, required=required))
    return out


def read_items() -> list[ReadItem]:
    """Questions whose ground truth is a number the computed block contains.

    Every expected value is parsed back out of the rendered block, so the
    harness cannot drift from the card/snapshot the agents actually read.
    """
    from tradingagents.strategies.risk_governor import build_risk_snapshot
    from tradingagents.strategies.trade_plan import build_trade_plan, measured_inputs

    closes = _fixture_closes()
    cfg = {"tranche_account": 100_000.0}
    card = build_trade_plan(
        ticker="AB", price=closes[-1], config=cfg, **measured_inputs(closes, cfg)
    )
    snapshot = build_risk_snapshot(
        {"verdict": "WARN", "reasons": ["book drawdown over limit"]},
        size_pct=0.03,
        stop_pct=0.05,
        cvar_pct=0.021,
        drawdown_pct=0.042,
        capital_at_risk_pct=0.015,
    )
    return _items_from_block(card, CARD_FACTS, "card") + _items_from_block(
        snapshot, SNAPSHOT_FACTS, "snapshot"
    )


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------


def score_choice(chosen: str | None, intended: str) -> bool:
    return bool(chosen) and str(chosen).strip().lower() == intended.lower()


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower().replace(",", ""))


def _canon_number(token: str) -> str:
    """`4.20%` / `4.2%` / `4.2` compare equal; non-numbers pass through."""
    stripped = token.rstrip("%")
    try:
        value = float(stripped)
    except ValueError:
        return token
    suffix = "%" if token.endswith("%") else ""
    return f"{value:.4f}".rstrip("0").rstrip(".") + suffix


def _canon_text(text: str) -> str:
    return NUMBER_RE.sub(lambda m: _canon_number(m.group(0)), text or "")


def score_read(answer: str, required: Sequence[str]) -> bool:
    got = _norm(_canon_text(answer))
    return all(_norm(_canon_text(r)) in got for r in required)


def ungrounded_figures(answer: str, context: str) -> list[str]:
    """Figures asserted with nothing in ``context`` to ground them.

    The question carries no figures by construction, so every number in the
    answer must be findable in the context the model was given. In the
    block-absent condition that set is empty, which is the point: a number there
    can only have been guessed.
    """
    allowed = {_canon_number(tok) for tok in NUMBER_RE.findall(context or "")}
    return [tok for tok in NUMBER_RE.findall(answer or "") if _canon_number(tok) not in allowed]


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value over the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1))
    return min(1.0, 2 * tail / (2**n))


# ---------------------------------------------------------------------------
# experiments
# ---------------------------------------------------------------------------


def run_tools(items: Sequence[ToolItem], producer: ToolProducer, k: int = 8, seed: int = 7) -> Experiment:
    surfaces = _surfaces()
    exp = Experiment("tools", f"shortlist (k={k})", "full surface")
    cost_a = cost_b = 0
    for item in items:
        tools = surfaces[item.surface]
        small = shortlist(tools, item.tool, k=k, seed=seed)
        chosen_a = producer(item.question, small)
        chosen_b = producer(item.question, tools)
        exp.outcomes.append(
            Outcome(
                item=f"{item.surface}:{item.tool}",
                a_ok=score_choice(chosen_a, item.tool),
                b_ok=score_choice(chosen_b, item.tool),
                a_answer=str(chosen_a),
                b_answer=str(chosen_b),
            )
        )
        cost_a += len(small)
        cost_b += len(tools)
    n = max(1, len(items))
    exp.cost_a = round(cost_a / n)
    exp.cost_b = round(cost_b / n)
    return exp


def run_reads(items: Sequence[ReadItem], producer: ReadProducer) -> Experiment:
    exp = Experiment("reads", "block present", "block absent")
    ungrounded_with = ungrounded_without = 0
    chars = 0
    for item in items:
        fresh = producer(item.question, item.block)
        bare = producer(item.without_block(), "")
        ok_a = score_read(fresh, item.required)
        ok_b = score_read(bare, item.required)
        exp.outcomes.append(
            Outcome(item=item.name, a_ok=ok_a, b_ok=ok_b, a_answer=fresh, b_answer=bare)
        )
        if ungrounded_figures(fresh, item.block):
            ungrounded_with += 1
        if ungrounded_figures(bare, ""):
            ungrounded_without += 1
        chars += len(item.block)
    exp.cost_a = round(chars / max(1, len(items)))
    exp.cost_b = 0
    exp.extra = {"ungrounded_with": ungrounded_with, "ungrounded_without": ungrounded_without}
    return exp


# ---------------------------------------------------------------------------
# decision items (Phase 1: does context volume change the DECISION?)
# ---------------------------------------------------------------------------
#
# docs/design_decision_context.md section 12. Every existing item in this file is
# scored on ACCURACY or GROUNDING. Testing H1 needs a third type whose score is
# the DECISION CATEGORY, so this section adds one - it does not add a harness.
# mcnemar_exact, ungrounded_figures, the producers and the report are all reused.
#
# The 2x2 factorial, not four arms:
#
#              Compact            Large
#   prose      C1                 C2
#   packet     P1                 P2
#
#   C2 - C1  volume WITHIN the prose representation
#   P1 - C1  the representation effect at compact size
#
# C2 - C1 isolates volume ONLY to the extent that C1 preserves C2's evidence and
# differs primarily in length. That is a requirement on the CONSTRUCTION, so C1
# is built by a deterministic, information-preserving transformation with a known
# deletion rule - never by free summarization - and what it retained is measured
# and reported by retention_table().

ARMS: tuple[str, ...] = ("c1", "c2", "p1", "p2")
ARM_LABELS: dict[str, str] = {
    "c1": "C1 compact prose",
    "c2": "C2 large prose",
    "p1": "P1 compact packet",
    "p2": "P2 large packet",
}

# The three-class directional projection of a 5-tier rating. Buy/Overweight are
# one class, Underweight/Sell another, Hold its own - the same collapse the
# experiment's "directional -> hold" transition is defined over.
BULLISH_RATINGS = ("Buy", "Overweight")
BEARISH_RATINGS = ("Underweight", "Sell")
NEUTRAL_RATINGS = ("Hold",)

# Mechanical markers for the retention table's fact rows. They are proxies, and
# they are DOCUMENTED as proxies: the table's job is to show whether the
# compaction dropped evidence of a KIND, not to adjudicate what counts as a
# bullish fact.
BULLISH_MARKERS = ("beat", "beats", "upside", "raise", "raised", "outperform",
                   "above consensus", "tailwind", "accelerat", "strong", "improving",
                   "expand", "growth", "record")
BEARISH_MARKERS = ("miss", "misses", "downside", "cut", "lowered", "underperform",
                   "below consensus", "headwind", "decelerat", "weak", "deteriorat",
                   "contract", "decline", "impair", "warning")
UNCERTAINTY_MARKERS = ("unavailable", "unknown", "not measured", "no data", "unmeasured",
                       "cannot", "insufficient", "n/a", "unresolved", "conflict",
                       "stale", "partial", "estimate only")


@dataclass(frozen=True)
class DecisionItem:
    """One snapshot, rendered four ways, with the identity it was built from."""

    name: str
    ticker: str
    as_of: str
    arms: dict[str, str]        # arm -> the context text that arm presents
    snapshot: dict              # data/engine/model hashes (section 12.3)

    def context(self, arm: str) -> str:
        return self.arms.get(arm, "")


@dataclass
class DecisionRecord:
    """One item under all four arms, plus what each arm decided."""

    item: str
    per_arm: dict[str, dict] = field(default_factory=dict)
    invalid: bool = False
    invalid_reason: str = ""
    unverifiable: bool = False


DecisionProducer = Callable[[DecisionItem, str], dict]


def compact_prose(text: str, head: int = 2, tail: int = 2, mode: str = "evidence") -> str:
    """C1: the same EVIDENCE, less presentation volume.

    The doc's requirement is exact: *"C1 must be built from C2 by a
    deterministic, information-preserving transformation"* so that ``C2 - C1``
    isolates volume. Two constructions satisfy different halves of that, and the
    difference matters:

    ``mode="bounded"``
        The doc's literal sketch - *"the same evidence CLASSES, bounded to
        first/last/representative rows"*. It preserves the SHAPE of the evidence
        and drops rows. Measured on the fixture it retained **50%** of the
        bullish facts and **56%** of the figures, i.e. it is a content reduction,
        and the retention table correctly refuses to call the contrast a volume
        effect. Kept because it is the construction the doc names.

    ``mode="evidence"`` (default)
        Drops only lines that carry NO evidence - prose filler, blank runs,
        separator rules - and collapses whitespace. Every line carrying a figure
        or a ``key=value`` metric survives, so retention is 100% by construction
        and the length drop is presentation, not information. This is the
        construction that makes the volume contrast testable at all.

    The default is ``evidence`` because a contrast that can never be a volume
    effect cannot answer H1a. The retention table is what proves it, and it is
    reported either way - if the construction fails to preserve, the finding is
    named a content-retention effect rather than a volume one.
    """
    if mode == "bounded":
        out: list[str] = []
        block: list[str] = []

        def flush() -> None:
            if not block:
                return
            if len(block) <= head + tail:
                out.extend(block)
            else:
                dropped = len(block) - head - tail
                out.extend(block[:head])
                out.append(f"[... {dropped} row(s) elided by the C1 compaction ...]")
                out.extend(block[-tail:])
            block.clear()

        for line in (text or "").splitlines():
            if line.strip():
                block.append(line)
            else:
                flush()
                out.append(line)
        flush()
        return "\n".join(out)

    # mode == "evidence": keep everything evidential, drop the rest.
    kept: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue                                   # blank run: pure volume
        if re.fullmatch(r"[-=_*~#\s]{3,}", stripped):
            continue                                   # separator rule
        has_figure = bool(NUMBER_RE.search(stripped))
        has_metric = bool(_LABEL_RE.match(line))
        is_section = bool(_SECTION_RE.match(line))
        if has_figure or has_metric or is_section:
            kept.append(line.rstrip())
    return "\n".join(kept)


def _figures(text: str) -> set[str]:
    return {_canon_number(tok) for tok in NUMBER_RE.findall(text or "")}


_LABEL_RE = re.compile(r"^\s*[-*|]?\s*([A-Za-z][A-Za-z0-9 /()_%.-]{2,44}?)\s*[:=]", re.M)
_SECTION_RE = re.compile(r"^\s*(?:#{1,6}\s+.+|\[[A-Z][^\]]{2,60}\])\s*$", re.M)


def _facts(text: str, markers: Sequence[str]) -> int:
    low = (text or "").lower()
    return sum(1 for line in low.splitlines() if any(m in line for m in markers))


def retention_table(c2: str, c1: str) -> dict:
    """What the C1 compaction kept, per section 12.1's six rows.

    ``retained_pct`` is per row. A row at 100% means the compaction did not touch
    that kind of evidence; materially below it means the C1/C2 contrast measures
    content retention as well as length, and must be reported as such.
    """
    rows = {
        "unique_metrics": (set(_LABEL_RE.findall(c2 or "")), set(_LABEL_RE.findall(c1 or ""))),
        "unique_figures": (_figures(c2), _figures(c1)),
        "bullish_facts": (None, None),
        "bearish_facts": (None, None),
        "uncertainty_facts": (None, None),
        "source_sections": (set(_SECTION_RE.findall(c2 or "")), set(_SECTION_RE.findall(c1 or ""))),
    }
    table: dict = {}
    for name, (a, b) in rows.items():
        if name == "bullish_facts":
            n2, n1 = _facts(c2, BULLISH_MARKERS), _facts(c1, BULLISH_MARKERS)
        elif name == "bearish_facts":
            n2, n1 = _facts(c2, BEARISH_MARKERS), _facts(c1, BEARISH_MARKERS)
        elif name == "uncertainty_facts":
            n2, n1 = _facts(c2, UNCERTAINTY_MARKERS), _facts(c1, UNCERTAINTY_MARKERS)
        else:
            n2, n1 = len(a), len(b)
        table[name] = {
            "c2": n2,
            "c1": n1,
            "retained_pct": (100.0 * n1 / n2) if n2 else None,
        }
    table["_chars"] = {
        "c2": len(c2 or ""),
        "c1": len(c1 or ""),
        "retained_pct": (100.0 * len(c1 or "") / len(c2)) if c2 else None,
    }
    return table


def retention_verdict(table: dict, floor_pct: float = 95.0, min_drop_pct: float = 5.0) -> str:
    """Name the contrast from what was retained (section 12.1's three-way table).

    TWO conditions must hold before a contrast may be called a volume effect:

    1. the evidence survived - every evidence row at or above ``floor_pct``; and
    2. the context actually SHRANK - chars down by at least ``min_drop_pct``.

    Condition 2 exists because the first draft of this function checked only
    condition 1 and cheerfully reported a "context-volume effect" for a C1 that
    was **2 characters smaller** than C2. A contrast between two identical-size
    contexts measures nothing, and calling it a volume effect is precisely the
    vacuous result section 12.1 warns about. No ablation is a finding too, and
    it is reported as one.
    """
    worst = None
    for row, vals in table.items():
        if row.startswith("_"):
            continue
        pct = vals.get("retained_pct")
        if pct is None:
            continue
        if worst is None or pct < worst[1]:
            worst = (row, pct)
    chars = table.get("_chars", {})
    char_pct = chars.get("retained_pct")

    if char_pct is None:
        return "unmeasurable (no comparable evidence)"
    drop = 100.0 - char_pct
    if drop < min_drop_pct:
        return (
            f"NO VOLUME ABLATION AVAILABLE (chars retained {char_pct:.0f}%, a "
            f"{drop:.1f}% reduction - below the {min_drop_pct:.0f}% floor). The two "
            "arms are effectively the same context size, so this contrast measures "
            "nothing. Reduce evidence, or rebuild C1."
        )
    if worst is None:
        return (
            f"context-volume effect ({drop:.0f}% shorter) - no comparable evidence "
            "rows to check retention against"
        )
    if worst[1] < floor_pct:
        return (
            f"content-retention effect ({drop:.0f}% shorter but {worst[0]} retained "
            f"{worst[1]:.0f}%, below the {floor_pct:.0f}% floor)"
        )
    return f"context-volume effect ({drop:.0f}% shorter, all evidence rows retained)"


def _class(rating: str | None) -> str:
    """buy / hold / sell for a 5-tier rating. Unknown -> 'unknown'."""
    r = str(rating or "").strip().capitalize()
    if r in BULLISH_RATINGS:
        return "buy"
    if r in BEARISH_RATINGS:
        return "sell"
    if r in NEUTRAL_RATINGS:
        return "hold"
    return "unknown"


def transition_matrix(pairs: Sequence[tuple[str, str]]) -> dict:
    """Paired rating -> rating moves between two arms.

    Reported as a matrix AND as the four directional moves the doc names, because
    the aggregate distribution cannot tell a systematic directional -> hold drift
    from unrelated churn in both directions.
    """
    matrix: dict[str, int] = {}
    directional = {"directional_to_hold": 0, "hold_to_directional": 0,
                   "bullish_to_bearish": 0, "bearish_to_bullish": 0}
    for before, after in pairs:
        a, b = str(before or "").capitalize(), str(after or "").capitalize()
        if not a or not b:
            continue
        matrix[f"{a} -> {b}"] = matrix.get(f"{a} -> {b}", 0) + 1
        ca, cb = _class(a), _class(b)
        if ca in ("buy", "sell") and cb == "hold":
            directional["directional_to_hold"] += 1
        elif ca == "hold" and cb in ("buy", "sell"):
            directional["hold_to_directional"] += 1
        elif ca == "buy" and cb == "sell":
            directional["bullish_to_bearish"] += 1
        elif ca == "sell" and cb == "buy":
            directional["bearish_to_bullish"] += 1
    return {"matrix": matrix, "directional": directional}


def _entropy(counts: Sequence[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    out = 0.0
    for n in counts:
        if n > 0:
            p = n / total
            out -= p * math.log2(p)
    return out


def decision_distribution(records: Sequence[dict]) -> dict:
    """The full distribution, not only the CCI (section 12.2).

    CCI alone cannot distinguish "more directional" from "more volatile": two
    runs with the same CCI can have very different BUY/HOLD/SELL spreads, so the
    distribution is the primary output.
    """
    ratings = [str(r.get("llm_rating") or "").capitalize() for r in records]
    valid = [r for r in ratings if r]
    n = len(valid) or 1
    classes = [_class(r) for r in valid]
    confs = [r.get("llm_confidence") for r in records if isinstance(r.get("llm_confidence"), (int, float))]
    ev = 0.0
    for c in classes:
        ev += 1.0 if c == "buy" else -1.0 if c == "sell" else 0.0
    # The ONE tier vocabulary (rating.RATINGS_5_TIER); a second copy here would be
    # a second producer of the canonical scale (master rule 15).
    from tradingagents.agents.utils.rating import RATINGS_5_TIER

    return {
        "n": len(valid),
        "buy": sum(1 for c in classes if c == "buy"),
        "hold": sum(1 for c in classes if c == "hold"),
        "sell": sum(1 for c in classes if c == "sell"),
        "p_action": (sum(1 for c in classes if c in ("buy", "sell"))) / n,
        "p_no_trade": sum(1 for c in classes if c == "hold") / n,
        "decision_entropy": _entropy([sum(1 for r in valid if r == t) for t in RATINGS_5_TIER]),
        "directional_entropy": _entropy([
            sum(1 for c in classes if c == "buy"),
            sum(1 for c in classes if c == "hold"),
            sum(1 for c in classes if c == "sell"),
        ]),
        "confidence": (sum(confs) / len(confs)) if confs else None,
        "expected_value_direction": ev / n,
    }


@dataclass
class DecisionExperiment:
    name: str = "decision"
    records: list[DecisionRecord] = field(default_factory=list)
    retention: dict = field(default_factory=dict)
    invalid: list[str] = field(default_factory=list)
    errors: int = 0
    synthetic: bool = False

    def arm_records(self, arm: str) -> list[dict]:
        return [r.per_arm[arm] for r in self.records if arm in r.per_arm and not r.invalid]

    def distribution(self, arm: str) -> dict:
        return decision_distribution(self.arm_records(arm))

    def transitions(self, from_arm: str, to_arm: str, field: str = "llm_rating") -> dict:
        pairs = [
            (r.per_arm[from_arm].get(field), r.per_arm[to_arm].get(field))
            for r in self.records
            if not r.invalid and from_arm in r.per_arm and to_arm in r.per_arm
        ]
        return transition_matrix(pairs)

    def flip_rate(self, from_arm: str, to_arm: str, field: str = "llm_rating") -> float | None:
        pairs = [
            (r.per_arm[from_arm].get(field), r.per_arm[to_arm].get(field))
            for r in self.records
            if not r.invalid and from_arm in r.per_arm and to_arm in r.per_arm
        ]
        pairs = [(a, b) for a, b in pairs if a and b]
        if not pairs:
            return None
        return sum(1 for a, b in pairs if str(a).capitalize() != str(b).capitalize()) / len(pairs)

    def grounding(self, arm: str) -> int:
        """Items whose answer carried a figure the arm's own context cannot ground."""
        n = 0
        for r in self.records:
            if r.invalid or arm not in r.per_arm:
                continue
            rec = r.per_arm[arm]
            if ungrounded_figures(rec.get("answer", ""), rec.get("context", "")):
                n += 1
        return n


IDENTITY_KEYS: tuple[str, ...] = (
    "data_snapshot_hash", "engine_output_hash", "model_parameters_hash",
)


def _snapshot_check(expected: dict, got: dict) -> str:
    """Section 12.3's invariant, as three outcomes rather than two.

    ``"match"``        every identity key is EQUAL - including when both sides are
                       ``None``.
    ``"mismatch"``     a key differs, or one side has a hash the other lacks. This
                       is a real disagreement about the evidence, and it invalidates
                       the pair.
    ``"unverifiable"`` every key is ``None`` on both sides: there is no identity to
                       compare at all. The arms agree, but the agreement carries no
                       information, so it is counted and reported rather than
                       silently accepted.

    The first draft collapsed ``None == None`` into a mismatch, which invalidated
    **8 of 12 real snapshots** whose runs predate the scorecard gate and therefore
    have no ``engine_output_hash``. All four arms had consumed the same evidence;
    the check was asking the snapshot to be RICH, when the invariant only requires
    it to be the SAME. An over-strict invariant is not a safe one - it discards
    valid pairs and calls the loss rigour.
    """
    any_compared = False
    for key in IDENTITY_KEYS:
        e, g = (expected or {}).get(key), (got or {}).get(key)
        if e != g:
            return "mismatch"
        if e is not None:
            any_compared = True
    return "match" if any_compared else "unverifiable"


def run_decisions(items: Sequence[DecisionItem], producer: DecisionProducer) -> DecisionExperiment:
    """Every item under all four arms, with the identity invariant enforced."""
    exp = DecisionExperiment()
    for item in items:
        rec = DecisionRecord(item=item.name)
        for arm in ARMS:
            context = item.context(arm)
            if not context:
                continue
            try:
                out = producer(item, arm) or {}
            except Exception as exc:  # noqa: BLE001 - recorded, then scored as a miss
                exp.errors += 1
                print(f"  [decision call failed for {item.name}/{arm}: "
                      f"{type(exc).__name__}: {exc}]", file=sys.stderr)
                out = {}
            out.setdefault("context", context)
            verdict = _snapshot_check(item.snapshot, out.get("snapshot") or {})
            if verdict == "mismatch":
                rec.invalid = True
                rec.invalid_reason = (
                    f"arm {arm} did not consume the item's evidence snapshot "
                    f"(section 12.3) - the pair is invalid, not a footnote"
                )
            elif verdict == "unverifiable":
                rec.unverifiable = True
            rec.per_arm[arm] = out
        exp.records.append(rec)
        if rec.invalid:
            exp.invalid.append(item.name)
    if items:
        exp.retention = retention_table(items[0].context("c2"), items[0].context("c1"))
    return exp





def demo_tool_producer(items: Sequence[ToolItem], p_full: float = 0.70, p_short: float = 0.95,
                       seed: int = 3) -> ToolProducer:
    """Synthetic: pretends accuracy falls as the presented surface grows.

    The intended tool is looked up from the item set (a synthetic producer is
    allowed to know it; a live one never is) and the hit probability depends on
    how many tools the condition presented.
    """
    intended_by_question = {item.question: item.tool for item in items}

    def produce(question: str, tools: Sequence) -> str | None:
        intended = intended_by_question.get(question)
        if intended is None:
            return tools[0].name if tools else None
        rng = random.Random(f"{seed}:{question}:{len(tools)}")
        p = p_short if len(tools) <= 8 else p_full
        if rng.random() < p:
            return intended
        others = [t.name for t in tools if t.name != intended]
        return rng.choice(others) if others else intended

    return produce


def demo_read_producer(p_with: float = 0.90, p_lucky: float = 0.05, seed: int = 5) -> ReadProducer:
    """Synthetic: with the block the model copies it; without it guesses."""

    def produce(question: str, context: str) -> str:
        rng = random.Random(f"{seed}:{question}:{bool(context)}")
        if not context:
            lucky = random.Random(f"{seed}:{question}:guess")
            if lucky.random() < p_lucky:
                return "stop 105.20 / target 123.80 / size 3.0%"
            return f"roughly {round(lucky.uniform(1, 200), 2)} (estimated, not computed)"
        if rng.random() < p_with:
            return f"The computed block states:\n{context}"
        # A partial copy: the first figure is dropped, as a truncated read would.
        tokens = NUMBER_RE.findall(context)
        clipped = context.replace(tokens[0], "n/a", 1) if tokens else context
        return f"The computed block states:\n{clipped}"

    return produce


def live_producers(
    provider: str, model: str, base_url: str | None = None
) -> tuple[ToolProducer, ReadProducer, dict]:
    """Real producers built from the repo's LLM client.

    Returns the two producers plus a shared error counter: a failed API call is
    recorded and reported rather than silently scored as a wrong answer.
    """
    from langchain_core.messages import HumanMessage

    from tradingagents.llm_clients.factory import create_llm_client

    llm = create_llm_client(provider=provider, model=model, base_url=base_url).get_llm()
    errors = {"tools": 0, "reads": 0}

    def _text(response) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, list):  # provider block format
            content = " ".join(
                str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in content
            )
        return str(content)

    def tool_producer(question: str, tools: Sequence) -> str | None:
        try:
            response = llm.bind_tools(list(tools)).invoke([HumanMessage(content=question)])
        except Exception as exc:  # noqa: BLE001 - recorded, then scored as a miss
            errors["tools"] += 1
            print(f"  [tool call failed: {type(exc).__name__}: {exc}]", file=sys.stderr)
            return None
        calls = getattr(response, "tool_calls", None) or []
        if not calls:
            return None
        first = calls[0] or {}
        return first.get("name") if isinstance(first, dict) else getattr(first, "name", None)

    def read_producer(question: str, context: str) -> str:
        prompt = question if not context else (
            "Computed context (deterministic, from the pipeline):\n"
            f"{context}\n\n{question}\nAnswer only from the context above."
        )
        try:
            return _text(llm.invoke([HumanMessage(content=prompt)]))
        except Exception as exc:  # noqa: BLE001 - recorded, then scored as a miss
            errors["reads"] += 1
            print(f"  [read call failed: {type(exc).__name__}: {exc}]", file=sys.stderr)
            return ""

    return tool_producer, read_producer, errors


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


DECISION_PROMPT = """You are the Portfolio Manager. Decide on {ticker} as of {as_of}.

The evidence below is everything you have. Give ONE rating from exactly these five:
Buy / Overweight / Hold / Underweight / Sell.

Answer in exactly this shape and nothing else:
Rating: <one of the five>
Confidence: <0.0-1.0>
Reason: <one sentence citing the evidence above>

=== EVIDENCE ===
{context}
=== END EVIDENCE ==="""

_RATING_LINE_RE = re.compile(r"^\s*Rating\s*:\s*\**\s*([A-Za-z]+)", re.M | re.IGNORECASE)
_CONF_LINE_RE = re.compile(r"^\s*Confidence\s*:\s*\**\s*([0-9]*\.?[0-9]+)", re.M | re.IGNORECASE)


def parse_decision(text: str) -> dict:
    """Pull the rating and confidence out of a producer's answer.

    The rating is the OUTCOME VARIABLE, so an unparseable answer is recorded as
    no rating rather than defaulted to Hold - a silent Hold default would
    manufacture exactly the conservatism the experiment is trying to measure.
    """
    rating = None
    m = _RATING_LINE_RE.search(text or "")
    if m:
        from tradingagents.agents.utils.rating import RATINGS_5_TIER

        word = m.group(1).strip().capitalize()
        rating = word if word in RATINGS_5_TIER else None
    conf = None
    mc = _CONF_LINE_RE.search(text or "")
    if mc:
        try:
            conf = float(mc.group(1))
        except ValueError:
            conf = None
    return {"llm_rating": rating, "llm_confidence": conf}


def demo_decision_producer(p_large_conservative: float = 0.25, seed: int = 13) -> DecisionProducer:
    """Synthetic: the LARGE arms drift directional -> Hold more often than compact.

    It encodes H1a so the plumbing can be exercised end to end with no vendor:
    the effect is present by construction, and the report says SYNTHETIC. It is
    a test of the instrument, never a measurement of the model.
    """

    def produce(item: DecisionItem, arm: str) -> dict:
        rng = random.Random(f"{seed}:{item.name}:{arm}")
        large = arm in ("c2", "p2")
        if large and rng.random() < p_large_conservative:
            rating = "Hold"
        else:
            rating = rng.choice(["Buy", "Overweight", "Hold", "Underweight", "Sell"])
        conf = round(rng.uniform(0.45, 0.85), 2)
        return {
            "llm_rating": rating,
            "llm_confidence": conf,
            "answer": f"Rating: {rating}\nConfidence: {conf}\nReason: synthetic.",
            "snapshot": dict(item.snapshot),
        }

    return produce


def live_decision_producer(
    provider: str, model: str, base_url: str | None = None, errors: dict | None = None
) -> DecisionProducer:
    """Real producer: one model call per item per arm, on that arm's context.

    The same model, the same prompt, the same snapshot - only the context
    rendering changes. That is what makes the four arms paired.
    """
    from langchain_core.messages import HumanMessage

    from tradingagents.llm_clients.factory import create_llm_client

    llm = create_llm_client(provider=provider, model=model, base_url=base_url).get_llm()
    counter = errors if errors is not None else {}

    def produce(item: DecisionItem, arm: str) -> dict:
        prompt = DECISION_PROMPT.format(
            ticker=item.ticker, as_of=item.as_of, context=item.context(arm)
        )
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
        except Exception as exc:  # noqa: BLE001 - recorded, then scored as a miss
            counter["decision"] = counter.get("decision", 0) + 1
            print(f"  [decision call failed for {item.name}/{arm}: "
                  f"{type(exc).__name__}: {exc}]", file=sys.stderr)
            return {"answer": "", "snapshot": dict(item.snapshot)}
        content = getattr(response, "content", response)
        if isinstance(content, list):  # provider block format
            content = " ".join(
                str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in content
            )
        text = str(content)
        out = parse_decision(text)
        out["answer"] = text
        out["snapshot"] = dict(item.snapshot)
        return out

    return produce


def format_decision_report(exp: DecisionExperiment, producer_label: str) -> str:
    """The section 12 output order: transitions FIRST, then distribution, then CCI."""
    lines = [f"== decision factorial ({producer_label}) =="]
    n_valid = sum(1 for r in exp.records if not r.invalid)
    n_unver = sum(1 for r in exp.records if r.unverifiable and not r.invalid)
    lines.append(
        f"items={len(exp.records)}  paired={n_valid}  invalidated={len(exp.invalid)}"
    )
    if n_unver:
        lines.append(
            f"  {n_unver} pair(s) matched but carried NO identity hash to compare "
            "(no engine output in that run) - the invariant held trivially, so the "
            "pair is kept and the partial check is stated rather than implied"
        )
    if exp.invalid:
        lines.append(
            "  INVALIDATED (section 12.3 - the arms did not consume the same evidence "
            f"snapshot): {', '.join(exp.invalid)}"
        )
    if exp.errors:
        lines.append(
            f"  ATTENTION: {exp.errors} call(s) failed and were scored as misses - "
            "the comparison is confounded, re-run"
        )

    # 1. The paired transitions - the doc's primary output.
    lines.append("")
    lines.append("-- paired transitions (LLM output, before any gate) --")
    for a, b in (("c1", "c2"), ("p1", "p2"), ("c1", "p1")):
        t = exp.transitions(a, b)
        fr = exp.flip_rate(a, b)
        if fr is None:
            lines.append(f"  {ARM_LABELS[a]} -> {ARM_LABELS[b]}: no paired observations")
            continue
        lines.append(f"  {ARM_LABELS[a]} -> {ARM_LABELS[b]}   flip_rate={fr:.3f}")
        for move, count in sorted(t["matrix"].items()):
            if count:
                lines.append(f"      {move:24s} {count}")
        d = t["directional"]
        lines.append(
            f"      directional->hold {d['directional_to_hold']}   "
            f"hold->directional {d['hold_to_directional']}   "
            f"bullish->bearish {d['bullish_to_bearish']}   "
            f"bearish->bullish {d['bearish_to_bullish']}"
        )

    # 2. The distribution - CCI alone cannot separate directional from volatile.
    lines.append("")
    lines.append("-- distribution --")
    hdr = f"  {'metric':24s}" + "".join(f"{ARM_LABELS[a]:>18s}" for a in ARMS)
    lines.append(hdr)
    dists = {a: exp.distribution(a) for a in ARMS}
    for key in ("n", "buy", "hold", "sell", "p_action", "p_no_trade",
                "decision_entropy", "directional_entropy", "confidence",
                "expected_value_direction"):
        row = f"  {key:24s}"
        for a in ARMS:
            v = dists[a].get(key)
            row += f"{'--' if v is None else (f'{v:.3f}' if isinstance(v, float) else str(v)):>18s}"
        lines.append(row)

    # 3. Grounding - a budget that buys decisiveness with fabrication is a regression.
    lines.append("")
    lines.append("-- grounding (answers carrying an ungrounded figure) --")
    for a in ARMS:
        recs = exp.arm_records(a)
        lines.append(f"  {ARM_LABELS[a]:18s} {exp.grounding(a)}/{len(recs)}")

    # 4. Execution conservatism - the same transitions AFTER the gates.
    lines.append("")
    lines.append("-- execution (final action, after the gates) --")
    for a, b in (("c1", "c2"), ("p1", "p2")):
        fr = exp.flip_rate(a, b, field="final_action")
        lines.append(
            f"  {ARM_LABELS[a]} -> {ARM_LABELS[b]}: "
            + ("no paired observations" if fr is None else f"flip_rate={fr:.3f}")
        )

    # 5. What C1 kept - without it the first contrast is uninterpretable.
    if exp.retention:
        lines.append("")
        lines.append("-- retention (C1 vs C2) --")
        for row, vals in exp.retention.items():
            if row.startswith("_"):
                continue
            pct = vals.get("retained_pct")
            lines.append(
                f"  {row:20s} C2={vals['c2']:>5}  C1={vals['c1']:>5}  "
                + ("n/a" if pct is None else f"{pct:.0f}%")
            )
        ch = exp.retention.get("_chars", {})
        lines.append(
            f"  {'chars':20s} C2={ch.get('c2', 0):>5}  C1={ch.get('c1', 0):>5}  "
            + ("n/a" if ch.get("retained_pct") is None else f"{ch['retained_pct']:.0f}%")
        )
        lines.append(f"  => C2 - C1 is a {retention_verdict(exp.retention)}")
    return "\n".join(lines)


def decision_verdict(exp: DecisionExperiment) -> str:
    """State the finding under its correct name, per section 12.1."""
    if not exp.records:
        return "no decision items - nothing measured."
    fr = exp.flip_rate("c1", "c2")
    prefix = "SYNTHETIC producers - plumbing check, not a measurement. " if exp.synthetic else ""
    if fr is None:
        return prefix + "no paired C1/C2 observations."
    t = exp.transitions("c1", "c2")["directional"]
    kind = retention_verdict(exp.retention) if exp.retention else "unmeasured retention"
    return (
        f"{prefix}compact -> large prose flips the LLM rating on {fr:.0%} of paired "
        f"snapshots (directional->hold {t['directional_to_hold']}, "
        f"hold->directional {t['hold_to_directional']}). Read as a {kind}."
    )


def _packet_stand_in(card: dict) -> str:
    """A deterministic STRUCTURED rendering of the same run, for the P arms.

    Phase 1 runs BEFORE the Decision Packet exists (section 13), so the
    representation axis needs a stand-in. This builds one from the run's own
    deterministic blocks - the engine scores, the trade score, the risk
    disagreement flag and the decision telemetry - in a fixed key/value shape.
    It is NOT the packet: it has no budget, no uncertainty vocabulary and no
    conflict ledger. The report labels it a stand-in so a representation effect
    measured here is not read as a measurement of the packet.
    """
    lines: list[str] = ["[RUN STRUCTURE]", ""]
    for key in ("fundamental_score", "technical_score", "regime_score", "risk_score",
                "sentiment_score", "news_score", "event_state", "trade_score"):
        block = card.get(key)
        if not isinstance(block, dict):
            continue
        lines.append(f"[{key.upper()}]")
        for k, v in sorted(block.items()):
            if isinstance(v, (str, int, float, bool)) or v is None:
                lines.append(f"  {k}: {v}")
        lines.append("")
    dc = card.get("decision_context") or {}
    if dc:
        lines.append("[DECISION CONTEXT]")
        for section in ("llm_output", "deterministic_postprocess", "execution", "evidence"):
            payload = dc.get(section)
            if isinstance(payload, dict):
                for k, v in sorted(payload.items()):
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        lines.append(f"  {section}.{k}: {v}")
    return "\n".join(lines)


def decision_items_from_tree(tree, ticker: str | None = None, as_of: str | None = None,
                             limit: int = 0) -> list[DecisionItem]:
    """Build the four arms from a real report tree.

    C2 is the prose evidence the analysts actually received (rendered from the
    tree's ``tool_evidence.json`` by the same gatherer the graph uses), so the
    prose axis cannot drift from the real prompt. The P arms are the structured
    stand-in above. Snapshot identity is computed with the SAME function Phase 0
    writes into the card, so the invariant is checked against the run's own
    hashes rather than a parallel notion of identity.
    """
    import pathlib as _pathlib

    from tradingagents.agents.utils.prompt_metrics import snapshot_identity

    tree = _pathlib.Path(tree)
    evidence_path = tree / "tool_evidence.json"
    card_path = tree / "run_card.json"
    if not evidence_path.exists() or not card_path.exists():
        return []
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    card = json.loads(card_path.read_text(encoding="utf-8"))

    prose = ""
    try:
        from tradingagents.agents.utils.evidence_gather import RENDERED_BLOCK_KEY

        rendered = evidence.get(RENDERED_BLOCK_KEY)
        if isinstance(rendered, list) and rendered:
            # The render is a list of {analyst, block} DICTS, not strings -
            # joining str(dict) would have measured the Python repr, the exact
            # error the telemetry module already had to fix once.
            parts = []
            for entry in rendered:
                if isinstance(entry, dict):
                    parts.append(str(entry.get("block") or ""))
                else:
                    parts.append(str(entry))
            prose = "\n\n".join(p for p in parts if p)
    except Exception:  # noqa: BLE001 - fall back to the raw leaves
        prose = ""
    if not prose:
        prose = json.dumps(evidence, indent=2, sort_keys=True, default=str)

    structured = _packet_stand_in(card)
    ticker = ticker or card.get("ticker") or tree.name.split("_")[0]
    as_of = as_of or (card.get("generated") or "")[:10]
    snap = snapshot_identity(
        {},
        {
            "company_of_interest": ticker,
            "trade_date": as_of,
            "quant_scorecard": card.get("quant_scorecard"),
        },
    )
    # The card carries no data_snapshot_hash of its own (Phase 0 computes it at
    # report time), so the identity is recomputed here from the same inputs.
    items = [DecisionItem(
        name=tree.name,
        ticker=str(ticker),
        as_of=str(as_of),
        arms={
            "c2": prose,
            "c1": compact_prose(prose),
            "p2": structured,
            "p1": compact_prose(structured),
        },
        snapshot=snap,
    )]
    return items[:limit] if limit else items


def _fixture_evidence() -> str:
    """A hermetic evidence block in the shape the gatherer renders.

    Used by ``--demo`` so the factorial can be exercised with no tree, no vendor
    and no key. It carries the same section/row structure the real render has,
    which is what the retention table measures.
    """
    rows = []
    for i in range(1, 13):
        rows.append(
            f"  {i:02d}. revenue_growth={0.05 + i * 0.01:.2f}%  "
            f"note: {'beat' if i % 3 else 'miss'} vs consensus"
        )
    return (
        "[MARKET EVIDENCE]\n" + "\n".join(rows[:6]) + "\n\n"
        "[FUNDAMENTAL EVIDENCE]\n" + "\n".join(rows[6:]) + "\n\n"
        "[RISK EVIDENCE]\n  liquidity=unavailable  cvar=2.10%  note: partial data\n"
    )


def decision_items(trees: Sequence[str] = (), limit: int = 0) -> list[DecisionItem]:
    """The decision items: real trees when given, else the hermetic fixture."""
    items: list[DecisionItem] = []
    for tree in trees:
        items.extend(decision_items_from_tree(tree, limit=limit))
    if items:
        return items
    prose = _fixture_evidence()
    structured = (
        "[RUN STRUCTURE]\n\n[TRADE_SCORE]\n  trade_score: 59.46\n  coverage: 0.68\n"
        "\n[RISK_SCORE]\n  risk_score: 67.90\n  coverage: 0.45\n"
        "\n[DECISION CONTEXT]\n  llm_output.rating: Hold\n  execution.final_action: HOLD\n"
    )
    return [DecisionItem(
        name="fixture",
        ticker="FIX",
        as_of="2026-09-20",
        arms={
            "c2": prose,
            "c1": compact_prose(prose),
            "p2": structured,
            "p1": compact_prose(structured),
        },
        snapshot={
            "snapshot_id": "FIX_2026-09-20",
            "data_snapshot_hash": "fixture-data",
            "engine_output_hash": "fixture-engine",
            "model_parameters_hash": "fixture-model",
        },
    )]


def format_report(experiments: Sequence[Experiment], producer_label: str) -> str:
    lines = [f"== context A/B ({producer_label}) =="]
    for exp in experiments:
        acc_a, acc_b = exp.accuracy("a"), exp.accuracy("b")
        b, c = exp.b(), exp.c()
        p = mcnemar_exact(b, c)
        lines.append(
            f"{exp.name:6s} {exp.condition_a}: {acc_a:.3f}   {exp.condition_b}: {acc_b:.3f}"
            f"   (n={len(exp.outcomes)}, b={b}, c={c}, McNemar p={p:.4f})"
        )
        lines.append(
            f"       cost: {exp.cost_a} vs {exp.cost_b} "
            f"(mean per item; tools presented for the tool experiment, chars of "
            f"context for the reads)"
        )
        if exp.extra.get("errors"):
            lines.append(
                f"       ATTENTION: {exp.extra['errors']} call(s) failed and were scored as "
                "misses - the comparison is confounded, re-run"
            )
        if exp.name == "reads":
            lines.append(
                f"       answers carrying an ungrounded figure: "
                f"with block={exp.extra.get('ungrounded_with')} "
                f"without={exp.extra.get('ungrounded_without')}"
            )
    return "\n".join(lines)


def verdict(experiments: Sequence[Experiment], synthetic: bool) -> str:
    parts = []
    for exp in experiments:
        delta = (exp.accuracy("a") - exp.accuracy("b")) * 100
        p = mcnemar_exact(exp.b(), exp.c())
        direction = "raised" if delta > 0 else "lowered" if delta < 0 else "did not change"
        parts.append(
            f"{exp.condition_a} {direction} {exp.name} accuracy by {abs(delta):.1f} points "
            f"vs {exp.condition_b} (p={p:.4f})"
        )
    for exp in experiments:
        if exp.name == "reads":
            parts.append(
                f"ungrounded figures on {exp.extra.get('ungrounded_with')} item(s) with the "
                f"block vs {exp.extra.get('ungrounded_without')} without it"
            )
    prefix = "SYNTHETIC producers - plumbing check, not a measurement. " if synthetic else ""
    return prefix + "; ".join(parts) + "."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--experiment", choices=("tools", "reads", "decision", "both", "all"),
                        default="both")
    parser.add_argument("--limit", type=int, default=25, help="items per experiment")
    parser.add_argument("--k", type=int, default=8, help="shortlist size (tools experiment)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--demo", action="store_true", help="synthetic producers (no vendor)")
    parser.add_argument("--live", action="store_true", help="real producers (needs an API key)")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--list", action="store_true", help="show the measured item sets and exit")
    parser.add_argument("--json", default=None, help="write the full report as JSON")
    # Phase 1 (design doc section 12): the decision factorial. Point --trees at
    # real report trees to build the arms from real evidence; without it the
    # hermetic fixture is used and the report says so.
    parser.add_argument("--trees", nargs="*", default=[],
                        help="report trees to build decision items from")
    args = parser.parse_args(argv)

    tools_items = tool_items(limit=args.limit, seed=args.seed)
    reads_items = read_items()
    decision_items_list = decision_items(tuple(args.trees), limit=args.limit)
    if args.list:
        print(f"tool items: {len(tools_items)} (claim, intended tool) pairs drawn from the surfaces")
        for item in tools_items[:5]:
            print(f"   [{item.surface}] {item.tool}: {item.claim[:70]}")
        print(f"read items: {len(reads_items)}")
        for item in reads_items:
            print(f"   {item.name}: expects {item.required}")
        print(f"decision items: {len(decision_items_list)}")
        for item in decision_items_list:
            print(f"   {item.name} ({item.ticker} {item.as_of}): "
                  + "  ".join(f"{a}={len(item.context(a))}ch" for a in ARMS))
        return 0

    synthetic = not args.live
    if args.live:
        if not (args.provider and args.model):
            print("--live needs --provider and --model", file=sys.stderr)
            return 2
        tool_producer, read_producer, live_errors = live_producers(
            args.provider, args.model, args.base_url
        )
        decision_producer = live_decision_producer(
            args.provider, args.model, args.base_url, errors=live_errors
        )
        label = f"live: {args.provider}/{args.model}"
    else:
        tool_producer = demo_tool_producer(tools_items, seed=args.seed)
        read_producer = demo_read_producer(seed=args.seed)
        decision_producer = demo_decision_producer(seed=args.seed)
        label = "demo producers: synthetic, not a measurement"

    wants_decision = args.experiment in ("decision", "all")
    wants_legacy = args.experiment in ("tools", "reads", "both", "all")

    experiments: list[Experiment] = []
    if wants_legacy and args.experiment in ("tools", "both", "all"):
        experiments.append(run_tools(tools_items, tool_producer, k=args.k, seed=args.seed))
    if wants_legacy and args.experiment in ("reads", "both", "all"):
        experiments.append(run_reads(reads_items, read_producer))
    if args.live:
        for exp in experiments:
            exp.extra["errors"] = live_errors.get(exp.name, 0)

    dec_exp: DecisionExperiment | None = None
    if wants_decision:
        dec_exp = run_decisions(decision_items_list, decision_producer)
        dec_exp.synthetic = synthetic
        if args.live:
            dec_exp.errors += live_errors.get("decision", 0)

    if experiments:
        print(format_report(experiments, label))
        print("\n" + verdict(experiments, synthetic))
    if dec_exp is not None:
        print("\n" + format_decision_report(dec_exp, label))
        print("\n" + decision_verdict(dec_exp))

    if args.json:
        payload = {
            "producer": label,
            "synthetic": synthetic,
            "experiments": [
                {
                    "name": e.name,
                    "condition_a": e.condition_a,
                    "condition_b": e.condition_b,
                    "accuracy_a": e.accuracy("a"),
                    "accuracy_b": e.accuracy("b"),
                    "b": e.b(),
                    "c": e.c(),
                    "p_value": mcnemar_exact(e.b(), e.c()),
                    "cost_a": e.cost_a,
                    "cost_b": e.cost_b,
                    "extra": e.extra,
                    "items": [o.__dict__ for o in e.outcomes],
                }
                for e in experiments
            ],
        }
        if dec_exp is not None:
            payload["decision"] = {
                "items": [
                    {"name": r.item, "invalid": r.invalid, "reason": r.invalid_reason,
                     "per_arm": r.per_arm}
                    for r in dec_exp.records
                ],
                "retention": dec_exp.retention,
                "retention_verdict": (
                    retention_verdict(dec_exp.retention) if dec_exp.retention else None
                ),
                "invalidated": dec_exp.invalid,
                "errors": dec_exp.errors,
                "distributions": {a: dec_exp.distribution(a) for a in ARMS},
                "transitions": {
                    f"{a}->{b}": {
                        "llm_rating": dec_exp.transitions(a, b),
                        "flip_rate": dec_exp.flip_rate(a, b),
                        "final_action_flip_rate": dec_exp.flip_rate(a, b, field="final_action"),
                    }
                    for a, b in (("c1", "c2"), ("p1", "p2"), ("c1", "p1"))
                },
                "grounding": {a: dec_exp.grounding(a) for a in ARMS},
                "verdict": decision_verdict(dec_exp),
            }
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
