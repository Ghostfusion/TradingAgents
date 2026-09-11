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
# producers
# ---------------------------------------------------------------------------


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
    parser.add_argument("--experiment", choices=("tools", "reads", "both"), default="both")
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
    args = parser.parse_args(argv)

    tools_items = tool_items(limit=args.limit, seed=args.seed)
    reads_items = read_items()
    if args.list:
        print(f"tool items: {len(tools_items)} (claim, intended tool) pairs drawn from the surfaces")
        for item in tools_items[:5]:
            print(f"   [{item.surface}] {item.tool}: {item.claim[:70]}")
        print(f"read items: {len(reads_items)}")
        for item in reads_items:
            print(f"   {item.name}: expects {item.required}")
        return 0

    synthetic = not args.live
    if args.live:
        if not (args.provider and args.model):
            print("--live needs --provider and --model", file=sys.stderr)
            return 2
        tool_producer, read_producer, live_errors = live_producers(
            args.provider, args.model, args.base_url
        )
        label = f"live: {args.provider}/{args.model}"
    else:
        tool_producer = demo_tool_producer(tools_items, seed=args.seed)
        read_producer = demo_read_producer(seed=args.seed)
        label = "demo producers: synthetic, not a measurement"

    experiments: list[Experiment] = []
    if args.experiment in ("tools", "both"):
        experiments.append(run_tools(tools_items, tool_producer, k=args.k, seed=args.seed))
    if args.experiment in ("reads", "both"):
        experiments.append(run_reads(reads_items, read_producer))
    if args.live:
        for exp in experiments:
            exp.extra["errors"] = live_errors.get(exp.name, 0)

    print(format_report(experiments, label))
    print("\n" + verdict(experiments, synthetic))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(
                {
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
                },
                fh,
                indent=2,
            )
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
