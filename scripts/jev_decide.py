#!/usr/bin/env python3
"""TypeSafe decisions-model utility (``typesafe/jev-1.13`` on OpenRouter).

Two facts this script encodes, both established by probing rather than reading:

* ``typesafe/jev-1.13`` is a **decisions** model, not a chat model. Sent to
  ``/chat/completions`` it returns HTTP 400, and the error names the endpoint
  that does work: ``POST /api/alpha/decisions``.
* That endpoint takes ``{model, state, questions}`` - there is no ``messages``
  field, so a document is sent as ``state`` and the ask as ``questions``. A
  question is a discriminated union on ``type``: ``noul`` | ``choice`` |
  ``score``. ``choice`` takes a ``criteria`` **record** (label -> rubric or
  null), ``score`` takes a ``criteria`` **array** (lowest -> highest), ``noul``
  takes neither and answers with a **float, not prose**.

So this is not a summariser: it is a typed judge over a document. The default
battery asks only about the report itself (stance, evidence strength, horizon)
and encodes no trading policy. Override it with ``--questions FILE``.

The key is resolved with ``python-dotenv``, the same loader the engine uses.
A hand-rolled byte parser mis-reads it: the value is quoted in ``.env``, so the
quote characters end up inside the token and every call 401s with
``Missing Authentication header`` - which reads like a missing header rather
than a malformed token.

    py -3.12 scripts/jev_decide.py
    py -3.12 scripts/jev_decide.py --tree reports/MSFT_20260920_145644
    py -3.12 scripts/jev_decide.py --stems market,news --json jev.json
    py -3.12 scripts/jev_decide.py --state-file notes.md
    py -3.12 scripts/jev_decide.py --questions my_questions.json

Exit code: 0 = every call answered; 1 = at least one call failed (the failure
is printed with the vendor's own message, never swallowed).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from collections.abc import Callable, Iterable, Sequence

import requests
from dotenv import dotenv_values

DEFAULT_MODEL = "typesafe/jev-1.13"
DEFAULT_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_TIMEOUT = 300.0

#: The four analyst report stems, in the order the run produces them.
ANALYST_STEMS: tuple[str, ...] = ("fundamentals", "market", "news", "sentiment")

#: The endpoint's question discriminators. Anything else is a 400.
QUESTION_TYPES = frozenset({"noul", "choice", "score"})

#: The default battery. Every question is about the document, not about what to
#: trade - the caller owns that policy.
DEFAULT_QUESTIONS: dict[str, dict] = {
    "stance": {
        "type": "choice",
        "instructions": "What is the report's overall directional stance on the ticker?",
        "criteria": {"bullish": None, "neutral": None, "bearish": None},
    },
    "evidence": {
        "type": "score",
        "instructions": "How strong is the evidence behind that stance?",
        "criteria": ["none", "weak", "moderate", "strong", "very strong"],
    },
    "horizon": {
        "type": "choice",
        "instructions": "What horizon does the report's thesis address?",
        "criteria": {"short": None, "medium": None, "long": None},
    },
}

#: One network boundary, injectable, so the parsing and the CLI are testable
#: with no vendor and no key. Returns ``(status_code, body_text)``.
Poster = Callable[[str, dict, dict, float], "tuple[int, str]"]


# ---------------------------------------------------------------------------
# key + inputs
# ---------------------------------------------------------------------------


def resolve_key(env_path: pathlib.Path | str, name: str = "OPENROUTER_API_KEY") -> str:
    """Resolve an API key the way the engine does, quoting included.

    ``dotenv_values`` strips the surrounding quotes a hand-rolled parser keeps.
    """
    values = dotenv_values(str(env_path))
    return (values.get(name) or "").strip()


def newest_tree(reports_dir: pathlib.Path | str) -> pathlib.Path:
    """The newest report tree under ``reports/`` (by name, which is timestamped)."""
    root = pathlib.Path(reports_dir)
    trees = sorted(d for d in root.iterdir() if d.is_dir() and (d / "1_analysts").is_dir())
    if not trees:
        raise FileNotFoundError(f"no report tree with 1_analysts/ under {root}")
    return trees[-1]


def report_states(tree: pathlib.Path | str, stems: Sequence[str]) -> list[tuple[str, str]]:
    """``[(label, text)]`` for the stems present in ``tree``, in ``stems`` order.

    A missing stem is skipped rather than sent as an empty state - an empty
    state would be judged as if it were a document.
    """
    root = pathlib.Path(tree) / "1_analysts"
    out: list[tuple[str, str]] = []
    for stem in stems:
        path = root / f"{stem}.md"
        if path.exists():
            out.append((stem, path.read_text(encoding="utf-8", errors="replace")))
    return out


def validate_questions(questions: dict) -> None:
    """Enforce the endpoint's own contract before spending a request on it.

    Only the *required* side is checked, because only that side was verified
    against the live endpoint.
    """
    if not questions:
        raise ValueError("questions is empty - the endpoint requires at least one")
    for qid, spec in questions.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{qid}: question must be an object, got {type(spec).__name__}")
        kind = spec.get("type")
        if kind not in QUESTION_TYPES:
            allowed = " | ".join(sorted(QUESTION_TYPES))
            raise ValueError(f"{qid}: type {kind!r} is not one of {allowed}")
        if not spec.get("instructions"):
            raise ValueError(f"{qid}: instructions is required")
        criteria = spec.get("criteria")
        if kind == "choice" and not isinstance(criteria, dict):
            raise ValueError(f"{qid}: choice requires criteria as a record (label -> rubric)")
        if kind == "score" and not isinstance(criteria, list):
            raise ValueError(f"{qid}: score requires criteria as an array (lowest -> highest)")


def build_payload(model: str, state: str, questions: dict) -> dict:
    """The request body. Note there is no ``messages`` key - this is not chat."""
    validate_questions(questions)
    return {"model": model, "state": state, "questions": questions}


# ---------------------------------------------------------------------------
# network
# ---------------------------------------------------------------------------


def post_json(url: str, headers: dict, payload: dict, timeout: float) -> tuple[int, str]:
    """The real transport. The only function here that touches the network."""
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    return resp.status_code, resp.text


def auth_headers(key: str) -> dict:
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Title": "TradingAgents jev_decide",
    }


def decide(
    state: str,
    questions: dict,
    *,
    key: str,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT,
    poster: Poster | None = None,
) -> tuple[int, str, float]:
    """One decision call. Returns ``(status, body_text, elapsed_seconds)``.

    ``poster`` resolves to :func:`post_json` at call time, not at def time, so a
    test can substitute the transport by patching the module attribute.
    """
    payload = build_payload(model, state, questions)
    send = poster or post_json
    started = time.time()
    status, body = send(endpoint, auth_headers(key), payload, timeout)
    return status, body, time.time() - started


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def answer_lines(qid: str, answer: dict) -> list[str]:
    """Render one answer as console lines, including the probability spread.

    The spread is the point: a ``choice`` of ``neutral`` at confidence 0.99 and
    the same choice at 0.34 are different findings.
    """
    kind = answer.get("type")
    pad = " " * len(qid)
    if kind == "choice":
        probs = answer.get("probabilities") or {}
        ordered = sorted(probs.items(), key=lambda kv: -kv[1])
        spread = "  ".join(f"{k}={v:g}" for k, v in ordered)
        return [
            f"  {qid}  choice = {answer.get('choice')}  confidence={answer.get('confidence')}",
            f"  {pad}  {spread}",
        ]
    if kind == "score":
        legend = answer.get("legend") or {}
        probs = answer.get("probabilities") or {}
        spread = "  ".join(
            f"{legend.get(k, k)}={v:g}"
            for k, v in sorted(probs.items(), key=lambda kv: int(kv[0]))
        )
        return [
            f"  {qid}  score  = {answer.get('score')}  confidence={answer.get('confidence')}",
            f"  {pad}  {spread}",
        ]
    # noul answers with a number, not text - render it as one.
    return [f"  {qid}  {kind}   = {answer.get(kind)}"]


def result_lines(data: dict, questions: dict) -> list[str]:
    """The header + per-question lines for one successful response."""
    usage = data.get("usage") or {}
    cost = usage.get("cost") or 0.0
    lines = [
        f"served by {data.get('provider')} as {data.get('model')}",
        f"tokens: in={usage.get('input_tokens')} out={usage.get('output_tokens')} "
        f"cost=${cost:.6f}",
        "RESULT:",
    ]
    answers = data.get("answers") or {}
    for qid in questions:
        answer = answers.get(qid)
        lines += [f"  {qid}  <missing>"] if answer is None else answer_lines(qid, answer)
    return lines


def _load_questions(path: pathlib.Path | str) -> dict:
    questions = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    validate_questions(questions)
    return questions


def _parse_args(argv: Iterable[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="jev_decide.py",
        description="Judge a document with the TypeSafe decisions model "
                    "(typesafe/jev-1.13) on OpenRouter.",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--tree", help="report tree (default: newest under reports/)")
    src.add_argument("--state-file", help="send this file as the state instead of a tree")
    src.add_argument("--state", help="send this literal text as the state")
    p.add_argument("--stems", default=",".join(ANALYST_STEMS),
                   help=f"comma-separated report stems (default: {','.join(ANALYST_STEMS)})")
    p.add_argument("--questions", help="JSON file overriding the default battery")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument("--env-file", default=".env")
    p.add_argument("--json", dest="json_out", help="write the raw responses here")
    return p.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = _parse_args(argv)

    repo = pathlib.Path(__file__).resolve().parent.parent
    key = resolve_key(repo / args.env_file)
    if not key:
        print(f"OPENROUTER_API_KEY not found in {args.env_file}", file=sys.stderr)
        return 1

    questions = _load_questions(args.questions) if args.questions else DEFAULT_QUESTIONS

    if args.state_file:
        path = pathlib.Path(args.state_file)
        states = [(path.stem, path.read_text(encoding="utf-8", errors="replace"))]
        origin = str(path)
    elif args.state:
        states = [("state", args.state)]
        origin = "<literal>"
    else:
        tree = pathlib.Path(args.tree) if args.tree else newest_tree(repo / "reports")
        stems = [s.strip() for s in args.stems.split(",") if s.strip()]
        states = report_states(tree, stems)
        origin = tree.name
        if not states:
            print(f"no matching reports in {tree}/1_analysts", file=sys.stderr)
            return 1

    print(f"origin  : {origin}")
    print(f"model   : {args.model}")
    print(f"endpoint: {args.endpoint}")
    print(f"states  : {[name for name, _ in states]}")
    print(f"key     : present ({len(key)} chars)")

    raw: list[dict] = []
    spent = 0.0
    failures = 0
    for name, state in states:
        print("\n" + "=" * 78)
        print(f"### {name}  ({len(state)} chars)")
        print("=" * 78)
        try:
            status, body, elapsed = decide(
                state, questions, key=key, model=args.model,
                endpoint=args.endpoint, timeout=args.timeout,
            )
        except Exception as exc:  # noqa: BLE001 - report and continue to the next state
            print(f"REQUEST FAILED: {type(exc).__name__}: {exc}")
            failures += 1
            continue
        print(f"HTTP {status}  {elapsed:.1f}s")
        if status != 200:
            # The vendor's own message is the diagnosis; never summarise it away.
            print(body[:2000])
            failures += 1
            continue
        data = json.loads(body)
        spent += (data.get("usage") or {}).get("cost") or 0.0
        for line in result_lines(data, questions):
            print(line)
        raw.append({"state": name, "response": data})

    print("\n" + "=" * 78)
    print(f"total cost: ${spent:.6f}")
    if args.json_out:
        pathlib.Path(args.json_out).write_text(
            json.dumps(raw, indent=1), encoding="utf-8"
        )
        print(f"wrote {args.json_out}")
    print("JEV-DECIDE-" + ("FAILED" if failures else "COMPLETE"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
