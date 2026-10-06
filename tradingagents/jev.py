"""The OpenRouter decisions API as a typed judge - one engine, three deciders.

The engine is model-agnostic: :data:`DECIDERS` names the judges that run over a
finished report tree (``typesafe/jev-1.13`` first, ``perplexity/pplx-decider-v1-27b``
second, ``respan/span-01`` third), each writing its own verdict file. The facts
below were established by probing rather than reading, and they hold for the
first two; the third's are its own, and they are not the same.

* ``typesafe/jev-1.13`` is a **decisions** model, not a chat model. Sent to
  ``/chat/completions`` it returns HTTP 400, and the error names the endpoint
  that does work: ``POST /api/alpha/decisions``.
* That endpoint takes ``{model, state, questions}`` - there is no ``messages``
  field, so a document is sent as ``state`` and the ask as ``questions``. A
  question is a discriminated union on ``type``: ``noul`` | ``choice`` |
  ``score``. ``choice`` takes a ``criteria`` **record** (label -> rubric or
  null), ``score`` takes a ``criteria`` **array** (lowest -> highest), ``noul``
  takes neither and answers with a **float, not prose**.
* Respan's decisions models (``respan/span-01``, and its ``-lite`` twin) are
  decisions models on the **same** route - sent to ``/chat/completions`` they
  400 with the same "use /api/alpha/decisions" message - but they accept
  **only** ``noul``, and only with no ``criteria`` key at all: the buy/hold/sell
  battery is refused with a 400 naming the question. That is why the third
  decider has its own battery (:data:`NOUL_QUESTIONS`) and its own recipe rather
  than the shared one. PROBED 2026-10-06, and it matters: its answers are
  **deterministic** (repeat calls identical to nine significant figures), they
  report ``output_tokens: 0`` (nothing is generated - the number is computed),
  ``span-01-lite`` is **byte-identical** to ``span-01`` on every input tried,
  and the number does **not** track the polarity it is asked for (a plainly
  bullish document scored 0.0177 and a plainly bearish one 0.0202, where
  ``typesafe/jev-1.13`` read the same pair as 0.84 vs 0.23). Read that file as a
  fixed document statistic, never as a rating.

So this is not a summariser: it is a typed judge over a document.

The CLI is ``scripts/jev_decide.py``; this module is the part the report
pipeline also uses. :func:`judge_tree` is the entry point for that - the
``--verdict`` recipe, written into the report tree that produced it.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import requests
from dotenv import dotenv_values


def _env_float(name: str, default: float) -> float:
    """A float from the environment, or ``default`` when the key is unset/blank.

    A key that IS set but unparseable raises here, at import: a typo'd timeout
    must not be silently replaced by the default. ``tradingagents/__init__.py``
    loads the project's ``.env`` into ``os.environ`` at package import, so a key
    declared there is already visible when this module is imported.
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name}={raw!r} is not a number") from exc


#: The model, its endpoint and the request timeout. Each is overridable from
#: ``.env`` (``TRADINGAGENTS_JEV_MODEL`` / ``TRADINGAGENTS_JEV_ENDPOINT`` /
#: ``TRADINGAGENTS_JEV_TIMEOUT``) so a model or host change needs no code edit;
#: an unset key keeps the literal this module was written against. The timeout
#: is seconds.
DEFAULT_MODEL = os.environ.get("TRADINGAGENTS_JEV_MODEL") or "typesafe/jev-1.13"
DEFAULT_ENDPOINT = (
    os.environ.get("TRADINGAGENTS_JEV_ENDPOINT")
    or "https://openrouter.ai/api/alpha/decisions"
)
DEFAULT_TIMEOUT = _env_float("TRADINGAGENTS_JEV_TIMEOUT", 300.0)

#: The SECOND decider: Perplexity's decisions model. Same endpoint and the same
#: request/response contract as the TypeSafe one - probed 2026-10-05, the alpha
#: route answers it as ``perplexity/pplx-decider-v1-27b-20261001`` (provider
#: ``Perplexity``) for all three question types (``choice``/``score``). Note the
#: endpoint the vendor page advertises for it, ``/api/v1/decisions``, is a **404**
#: - the live route is the alpha one above. Overridable from `.env` like the first.
PPLX_MODEL = (
    os.environ.get("TRADINGAGENTS_PPLX_DECIDER_MODEL")
    or "perplexity/pplx-decider-v1-27b"
)

#: The THIRD decider: Respan's ``span-01``. Same decisions route, but a
#: **different contract** - probed 2026-10-06, it answers ``noul`` only (a
#: ``choice`` or ``score`` battery is a 400 naming the question) and refuses a
#: ``criteria`` key on a ``noul`` question too, so it is asked
#: :data:`NOUL_QUESTIONS` through :func:`noul_verdict_for_tree` rather than the
#: shared buy/hold/sell battery. Overridable from `.env`
#: (``TRADINGAGENTS_NOUL_DECIDER_MODEL``). Probed byte-identical to
#: ``respan/span-01-lite`` (which reports ``cost: 0``) on every document tried,
#: so this key is also the lever between the paid and the free one.
NOUL_MODEL = (
    os.environ.get("TRADINGAGENTS_NOUL_DECIDER_MODEL")
    or "respan/span-01"
)

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

#: The noul-only battery: the THIRD decider's ask, and the only shape Respan's
#: decisions models accept. Both ``choice`` and ``score`` are a 400 there (the
#: vendor's message names the offending question), so the buy/hold/sell battery
#: cannot be asked of those models at all - and a ``noul`` question takes no
#: ``criteria``, so the *instructions* are the only channel a scale has.
#:
#: Read the answers as a document statistic, not as a rating: probed 2026-10-06,
#: they are deterministic, they report ``output_tokens: 0``, and they do not
#: follow the polarity written here (a plainly bullish document scored below a
#: plainly bearish one). The instructions are still worth stating - they do move
#: the number - but they do not make it a buy/hold/sell call.
NOUL_QUESTIONS: dict[str, dict] = {
    "rating": {
        "type": "noul",
        "instructions": (
            "On the evidence in this report alone, rate the ticker on a 0 to 1 "
            "scale, where 0 means sell, 0.5 means hold and 1 means buy. Answer "
            "with a single number."
        ),
    },
    "evidence": {
        "type": "noul",
        "instructions": (
            "How strong is the evidence in this report? Answer with a single "
            "number from 0 (no evidence) to 1 (very strong evidence)."
        ),
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

#: Where each decider's verdict lands inside a report tree. One file per
#: decider, so a tree that ran both carries both and neither overwrites the other.
VERDICT_FILENAME = "jev_verdict.json"
PPLX_VERDICT_FILENAME = "pplx_verdict.json"
NOUL_VERDICT_FILENAME = "noul_verdict.json"


@dataclass(frozen=True)
class Decider:
    """One decisions-API judge: its label, its model, its verdict filename, and
    the question recipe that model will actually answer."""

    label: str
    model: str
    filename: str
    #: Which battery this model accepts, and therefore which recipe asks it.
    #: ``"rating"`` is the endpoint's full contract - a ``choice`` buy/hold/sell
    #: plus ``score`` evidence and horizon (:data:`RATING_QUESTIONS`).
    #: ``"noul"`` is the noul-only contract Respan's decisions models enforce:
    #: they refuse ``choice`` and ``score`` outright, so the buy/hold/sell battery
    #: cannot be asked of them and :data:`NOUL_QUESTIONS` is used instead.
    recipe: str = "rating"


#: The deciders, in the order they run after a finished tree is written. The
#: TypeSafe one first (it is what the hook was built for), Perplexity's second -
#: same endpoint, same battery, same position neutralisation, a different model -
#: and Respan's third, same endpoint and same neutralisation but a noul-only
#: battery, because it refuses the shared one.
DECIDERS: tuple[Decider, ...] = (
    Decider(label="jev", model=DEFAULT_MODEL, filename=VERDICT_FILENAME),
    Decider(label="pplx", model=PPLX_MODEL, filename=PPLX_VERDICT_FILENAME),
    Decider(
        label="noul",
        model=NOUL_MODEL,
        filename=NOUL_VERDICT_FILENAME,
        recipe="noul",
    ),
)


def _battery_over_tree(
    tree: pathlib.Path | str,
    *,
    key: str,
    stems: Sequence[str],
    questions: dict,
    rollup: str,
    model: str,
    endpoint: str,
    timeout: float,
    poster: Poster | None,
) -> tuple[dict, list[tuple[str, dict]]]:
    """The body both recipes share: ask ``questions`` of every report in ``tree``.

    Returns ``(payload, answers)``, where ``answers`` is ``[(state_name, answers),
    ...]`` for the calls that came back - the recipe owns what those answers mean,
    because a noul float and a choice/score record do not summarise the same way.
    ``rollup`` names the payload key the caller fills with that summary.

    Never raises for a vendor failure - a failed call is recorded with the
    vendor's own message and counted. A post-run annotation must not be able to
    fail the run that produced it.
    """
    states = report_states(tree, stems)
    payload: dict = {
        "origin": pathlib.Path(tree).name,
        "model": model,
        "endpoint": endpoint,
        "battery": list(questions),
        "stems": [name for name, _ in states],
        "neutralized": {},
        rollup: {},
        "results": [],
        "failures": 0,
        "cost": 0.0,
    }
    answered: list[tuple[str, dict]] = []
    for name, state in states:
        clean, hits = neutralize_positions(state)
        payload["neutralized"][name] = hits
        try:
            status, body, elapsed = decide(
                clean, questions, key=key, model=model,
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
        answered.append((name, data.get("answers") or {}))
    return payload, answered


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

    The per-stem roll-up is ``payload["ratings"][stem]``. A vendor failure is
    recorded and counted, never raised - see :func:`_battery_over_tree`.
    """
    payload, answered = _battery_over_tree(
        tree, key=key, stems=stems, questions=RATING_QUESTIONS, rollup="ratings",
        model=model, endpoint=endpoint, timeout=timeout, poster=poster,
    )
    for name, answers in answered:
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


def noul_verdict_for_tree(
    tree: pathlib.Path | str,
    *,
    key: str,
    stems: Sequence[str] = ANALYST_STEMS,
    model: str = NOUL_MODEL,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT,
    poster: Poster | None = None,
) -> dict:
    """The noul-only recipe: the same reports, neutralised the same way, but
    asked :data:`NOUL_QUESTIONS` - because Respan's decisions models refuse every
    other question type, so the shared battery is a 400 rather than a worse
    answer.

    The per-stem roll-up is ``payload["scores"][stem]``, one float per question
    keyed by question id. Deliberately NOT a ``ratings`` block: a noul answer is a
    computed document statistic, not a buy/hold/sell call, and one key for both
    would invite reading it as one.
    """
    payload, answered = _battery_over_tree(
        tree, key=key, stems=stems, questions=NOUL_QUESTIONS, rollup="scores",
        model=model, endpoint=endpoint, timeout=timeout, poster=poster,
    )
    for name, answers in answered:
        payload["scores"][name] = {
            qid: (answers.get(qid) or {}).get("noul") for qid in NOUL_QUESTIONS
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


def judge_tree(
    tree: pathlib.Path | str,
    *,
    key: str,
    decider: Decider = DECIDERS[0],
    **kwargs,
) -> tuple[pathlib.Path, dict]:
    """Judge ``tree`` with ``decider`` and write the verdict into it.

    Returns ``(path, payload)``. One call, so a caller cannot judge without
    storing - the point of the step is that the verdict travels with the report
    it is about. ``decider`` defaults to :data:`DECIDERS`'s first entry, so an
    existing caller's behaviour is unchanged. ``kwargs`` (``stems``, ``timeout``,
    ``poster``, ...) pass through; ``model`` overrides the decider's own.

    The recipe follows the decider: a ``"noul"`` decider is asked
    :data:`NOUL_QUESTIONS` through :func:`noul_verdict_for_tree` because its model
    refuses the shared battery, and every other decider gets
    :func:`verdict_for_tree`.
    """
    options = {"model": decider.model, **kwargs}
    recipe = noul_verdict_for_tree if decider.recipe == "noul" else verdict_for_tree
    payload = recipe(tree, key=key, **options)
    return write_verdict(tree, payload, name=decider.filename), payload


def judge_tree_all(
    tree: pathlib.Path | str,
    *,
    key: str,
    deciders: Sequence[Decider] = DECIDERS,
) -> list[tuple[Decider, pathlib.Path, dict]]:
    """Run every decider over one tree, in order.

    Returns ``[(decider, path, payload), ...]``. Each decider writes its own
    file, so a later judge accumulates beside the earlier ones rather than
    replacing them - which is what makes the verdicts comparable after the fact.
    """
    return [(d, *judge_tree(tree, key=key, decider=d)) for d in deciders]
