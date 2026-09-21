"""The TypeSafe decisions model (``typesafe/jev-1.13``) as a typed judge.

Two facts this module encodes, both established by probing rather than reading:

* ``typesafe/jev-1.13`` is a **decisions** model, not a chat model. Sent to
  ``/chat/completions`` it returns HTTP 400, and the error names the endpoint
  that does work: ``POST /api/alpha/decisions``.
* That endpoint takes ``{model, state, questions}`` - there is no ``messages``
  field, so a document is sent as ``state`` and the ask as ``questions``. A
  question is a discriminated union on ``type``: ``noul`` | ``choice`` |
  ``score``. ``choice`` takes a ``criteria`` **record** (label -> rubric or
  null), ``score`` takes a ``criteria`` **array** (lowest -> highest), ``noul``
  takes neither and answers with a **float, not prose**.

So this is not a summariser: it is a typed judge over a document.

The CLI is ``scripts/jev_decide.py``; this module is the part the report
pipeline also uses. :func:`judge_tree` is the entry point for that - the
``--verdict`` recipe, written into the report tree that produced it.
"""

from __future__ import annotations

import json
import pathlib
import re
import time
from collections.abc import Callable, Sequence

import requests
from dotenv import dotenv_values

DEFAULT_MODEL = "typesafe/jev-1.13"
DEFAULT_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_TIMEOUT = 300.0

#: The four analyst report stems, in the order the run produces them.
ANALYST_STEMS: tuple[str, ...] = ("fundamentals", "market", "news", "sentiment")

#: The tree's staged directories, in pipeline order. The trailing "" is the
#: tree-root roll-up (``complete_report.md``), which comes last.
STAGE_ORDER: tuple[str, ...] = (
    "1_analysts",
    "2_research",
    "3_trading",
    "4_risk",
    "5_portfolio",
    "",
)

#: Where a bare analyst stem resolves. The majority of reads are analyst reports.
ANALYST_DIR = STAGE_ORDER[0]

#: The endpoint's question discriminators. Anything else is a 400.
QUESTION_TYPES = frozenset({"noul", "choice", "score"})

#: Recommendation language that would anchor a judge on the report's OWN verdict
#: instead of on its evidence. Matched case-insensitively on word boundaries, so
#: ``buy`` does not touch ``buyback`` and ``hold`` does not touch
#: ``shareholders`` or ``holdings``.
#:
#: Deliberately EXCLUDES ``long``, ``short``, ``add``, ``reduce``, ``trim`` and
#: ``neutral``: each is ordinary English in a market report (``long-term``,
#: ``short interest``, ``adds to risk``, ``reduces margin``, ``neutral rate``),
#: so stripping them removes EVIDENCE rather than bias. Extend this tuple if a
#: report family needs more - not the regex.
POSITION_WORDS: tuple[str, ...] = (
    "strong buy",
    "strong sell",
    "market outperform",
    "market underperform",
    "equal weight",
    "equal-weight",
    "market weight",
    "market-weight",
    "overweight",
    "underweight",
    "outperform",
    "underperform",
    "accumulate",
    "distribute",
    "buy",
    "sell",
    "hold",
)

#: What a stripped position becomes. A MARKER, not a deletion: a judge told a
#: position WAS stated but not WHICH cannot adopt it, and the substitution stays
#: auditable - the per-report count is printed.
POSITION_MARKER = "[POSITION]"

# Longest first, so ``strong buy`` is consumed whole instead of leaving ``strong``
# beside a marker.
_POSITION_RE = re.compile(
    r"(?<![A-Za-z])(?:"
    + "|".join(sorted((re.escape(w) for w in POSITION_WORDS), key=len, reverse=True))
    + r")(?![A-Za-z])",
    re.IGNORECASE,
)


def neutralize_positions(text: str) -> tuple[str, int]:
    """Replace the report's own recommendation language with a marker.

    Returns ``(text, replacements)``. This is what lets a judge read the
    evidence without being handed the conclusion - the analyst reports state a
    rating, and a rating is exactly what is being asked for.
    """
    return _POSITION_RE.subn(POSITION_MARKER, text)

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

#: The buy/hold/sell battery (``--rating``). Same evidence and horizon questions
#: as the default, with the directional one replaced by the three-way call the
#: reports are actually read for. Use it WITH ``--neutralize``: asking for a
#: rating while the document already states one measures agreement with the
#: document, not the evidence.
RATING_QUESTIONS: dict[str, dict] = {
    "rating": {
        "type": "choice",
        "instructions": (
            "On the evidence in this report alone, rate the ticker. Answer buy, "
            "hold or sell."
        ),
        "criteria": {"buy": None, "hold": None, "sell": None},
    },
    "evidence": {
        "type": "score",
        "instructions": "How strong is the evidence behind that rating?",
        "criteria": ["none", "weak", "moderate", "strong", "very strong"],
    },
    "horizon": DEFAULT_QUESTIONS["horizon"],
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


def _resolve_spec(tree: pathlib.Path, spec: str) -> pathlib.Path | None:
    """Resolve one ``--stems`` spec to a report inside ``tree``, or ``None``.

    Two forms, because a tree is staged:

    * ``market`` - a BARE name, tried as an analyst report first
      (``1_analysts/market.md``) and then as a tree-root report, so
      ``complete_report`` resolves too;
    * ``2_research/bull`` - a SLASH means a path relative to the tree, which is
      how the research, trading, risk and portfolio reports are reached. They
      are not under ``1_analysts/``, so a stem list could never name them.

    A candidate outside the tree is refused: the argument names a report tree,
    so ``--stems ../../etc/passwd`` is a bug rather than a feature.
    ``--state-file`` is the flag that deliberately takes any file.
    """
    spec = spec.strip()
    if not spec:
        return None
    name = spec if spec.endswith(".md") else f"{spec}.md"
    if "/" in spec or "\\" in spec:
        candidates = [tree / name]
    else:
        candidates = [tree / ANALYST_DIR / name, tree / name]
    root = tree.resolve()
    for cand in candidates:
        resolved = cand.resolve()
        if resolved != root and root not in resolved.parents:
            continue
        if resolved.is_file():
            return resolved
    return None


def report_states(tree: pathlib.Path | str, stems: Sequence[str]) -> list[tuple[str, str]]:
    """``[(label, text)]`` for the stems present in ``tree``, in ``stems`` order.

    A missing stem is skipped rather than sent as an empty state - an empty
    state would be judged as if it were a document. The label keeps the spec's
    own spelling (``news``, ``2_research/bull``), so a run's output names the
    file a reader would go and open.
    """
    tree = pathlib.Path(tree)
    out: list[tuple[str, str]] = []
    for spec in stems:
        path = _resolve_spec(tree, spec)
        if path is None:
            continue
        label = spec.strip()
        if label.endswith(".md"):
            label = label[:-3]
        out.append((label, path.read_text(encoding="utf-8", errors="replace")))
    return out


def all_report_states(tree: pathlib.Path | str) -> list[tuple[str, str]]:
    """Every report in ``tree``, in pipeline order.

    The staged directories first (analysts -> research -> trading -> risk ->
    portfolio), then the tree-root roll-up, so a read-out follows the run rather
    than the alphabet. ``--stems`` cannot express this: it names reports one at
    a time and a tree's report set grows as the pipeline gains stages.
    """
    tree = pathlib.Path(tree)
    paths = [p for p in tree.rglob("*.md") if p.is_file()]

    def order(p: pathlib.Path) -> tuple[int, str]:
        rel = p.relative_to(tree)
        stage = rel.parts[0] if len(rel.parts) > 1 else ""
        idx = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else len(STAGE_ORDER)
        return (idx, str(rel).replace("\\", "/"))

    return [
        (
            str(p.relative_to(tree)).replace("\\", "/")[:-3],
            p.read_text(encoding="utf-8", errors="replace"),
        )
        for p in sorted(paths, key=order)
    ]


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


# ---------------------------------------------------------------------------
# the post-run verdict: what the report pipeline writes into its own tree
# ---------------------------------------------------------------------------

#: Where the verdict lands inside a report tree.
VERDICT_FILENAME = "jev_verdict.json"


def verdict_for_tree(
    tree: pathlib.Path | str,
    *,
    key: str,
    stems: Sequence[str] = ANALYST_STEMS,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT,
    poster: Poster | None = None,
) -> dict:
    """The ``--verdict`` recipe over one tree: analyst reports only, position
    language neutralised, the buy/hold/sell battery.

    Never raises for a vendor failure - a failed call is recorded with the
    vendor's own message and counted. A post-run annotation must not be able to
    fail the run that produced it.
    """
    states = report_states(tree, stems)
    payload: dict = {
        "origin": pathlib.Path(tree).name,
        "model": model,
        "endpoint": endpoint,
        "battery": list(RATING_QUESTIONS),
        "stems": [name for name, _ in states],
        "neutralized": {},
        "ratings": {},
        "results": [],
        "failures": 0,
        "cost": 0.0,
    }
    for name, state in states:
        clean, hits = neutralize_positions(state)
        payload["neutralized"][name] = hits
        try:
            status, body, elapsed = decide(
                clean, RATING_QUESTIONS, key=key, model=model,
                endpoint=endpoint, timeout=timeout, poster=poster,
            )
        except Exception as exc:  # noqa: BLE001 - recorded, never raised
            payload["failures"] += 1
            payload["results"].append(
                {"state": name, "error": f"{type(exc).__name__}: {exc}"}
            )
            continue
        if status != 200:
            payload["failures"] += 1
            payload["results"].append(
                {"state": name, "status": status, "error": body[:2000]}
            )
            continue
        data = json.loads(body)
        payload["cost"] += (data.get("usage") or {}).get("cost") or 0.0
        payload["results"].append(
            {"state": name, "status": status, "elapsed_s": round(elapsed, 3),
             "response": data}
        )
        answers = data.get("answers") or {}
        rating = answers.get("rating") or {}
        evidence = answers.get("evidence") or {}
        horizon = answers.get("horizon") or {}
        payload["ratings"][name] = {
            "rating": rating.get("choice"),
            "confidence": rating.get("confidence"),
            "probabilities": rating.get("probabilities"),
            "evidence": evidence.get("score"),
            "horizon": horizon.get("choice"),
        }
    return payload


def write_verdict(
    tree: pathlib.Path | str,
    payload: dict,
    name: str = VERDICT_FILENAME,
) -> pathlib.Path:
    """Write the payload into the report tree that produced it."""
    path = pathlib.Path(tree) / name
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


def judge_tree(tree: pathlib.Path | str, *, key: str, **kwargs) -> tuple[pathlib.Path, dict]:
    """Judge ``tree`` and write the verdict into it. Returns ``(path, payload)``.

    One call, so a caller cannot judge without storing - the point of the step is
    that the verdict travels with the report it is about.
    """
    payload = verdict_for_tree(tree, key=key, **kwargs)
    return write_verdict(tree, payload), payload
