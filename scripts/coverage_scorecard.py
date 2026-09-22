#!/usr/bin/env python3
"""Field-level fill-rate scorecard across runs (P0 coverage measurement).

Every engine already publishes, per run, which of its declared fields it
measured and which it did not. Nothing reads that **across runs**, so a field
that is never populated is indistinguishable from a field that is populated on
most runs - both look like "some scores are not 100%".

This module answers one question per declared field: **was it measured, and if
not, why not?**

The declared universe comes from ``score_panel.engine_registry()`` - the one
place each engine's own component table (``COMPONENTS`` / ``SUBSCORE_FACTORS``)
is read - so this module never invents a second vocabulary for the same fields.

The classification is the point. A field with a zero fill rate is one of three
things, and only the middle one is a defect in this repo:

* ``unbuilt``    - the declared producer is empty: nobody has written it.
* ``unwired``    - a producer is named and has **no call site** on the live
                   path, so it can never run. This is the ``market_breadth``
                   class: a fully implemented, fully tested producer that no
                   caller ever reaches.
* ``structural`` - a producer is named and IS called, but returns nothing for
                   this instrument (semimonthly short interest, options on an
                   unlisted underlying, a panel this call does not fetch).

Fill rate alone cannot separate those three; the declared producer string plus
a call-site scan can. The call-site scan is AST-based, so a *citation* of a
producer (engines cite their producers as strings in their own component
tables) is not mistaken for a call to it.

Nothing here gates, scores or mutates. It reads ``run_card.json`` and prints.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.score_panel import engine_registry  # noqa: E402

#: Where ``batch.py`` writes its trees. Repo-relative, gitignored.
DEFAULT_REPORTS_DIR = "reports"

#: The per-tree card this reads. A tree without one is skipped and counted.
CARD_NAME = "run_card.json"

#: The live path scanned for producer call sites. ``tests`` is deliberately NOT
#: here: a producer referenced only by its own test is exactly the ``unwired``
#: case this module exists to catch. The sibling executor repo is included when
#: it is checked out, because several ``risk_score`` fields are produced there
#: (``pre_market``, ``options_surface``, ``liquidity_risk``) and reporting those
#: as unwired would be a false defect.
LIVE_ROOTS: tuple[str, ...] = ("tradingagents", "scripts", "../TradingExecution")

# --- Declared policy, printed in the output (never a measured coefficient) ---

#: At or above this fill rate a field is healthy.
FILL_OK = 0.95
#: At or above this (and below ``FILL_OK``) a field is intermittent.
FILL_MONITOR = 0.50
#: The float tolerance for "every measured value was zero".
ZERO_EPS = 1e-12

ACTION_OK = "none"
ACTION_MONITOR = "watch for drift"
ACTION_SPARSE = "investigate the sparse runs"
ACTION_UNBUILT = "no producer declared"
ACTION_UNWIRED = "the producer exists and nothing outside its module calls it"
ACTION_STRUCTURAL = "producer is reached; this run supplied no value"
ACTION_UNKNOWN = "cannot tell from the declaration - inspect by hand"


# ---------------------------------------------------------------------------
# Reading the trees
# ---------------------------------------------------------------------------


def load_cards(reports_dir: str, *, limit: int | None = None) -> list[tuple[str, dict]]:
    """``[(tree_name, run_card), ...]`` newest name first, skipping bad cards.

    A malformed or absent card is skipped rather than raising: this is an
    advisory read over a directory the operator points it at.
    """
    root = os.path.abspath(os.path.expanduser(str(reports_dir)))
    if not os.path.isdir(root):
        return []
    out: list[tuple[str, dict]] = []
    for name in sorted(os.listdir(root), reverse=True):
        path = os.path.join(root, name, CARD_NAME)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                card = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(card, dict):
            out.append((name, card))
        if limit is not None and len(out) >= int(limit):
            break
    return out


# ---------------------------------------------------------------------------
# Presence: every signal the run_card states explicitly
# ---------------------------------------------------------------------------
#
# Each engine publishes presence differently, and the difference is real - it is
# not a vocabulary this module may unify:
#
#   technical_score    category ``components``      (list of PRESENT names)
#   risk_score         category ``present``         (list of PRESENT names)
#   fundamental_score  subscore ``coverage.metrics``(list of PRESENT names)
#   regime_score       engine ``components``        (name -> {raw, aligned})
#   sentiment_score    nothing                      -> the complement of absent
#   news_score         nothing                      -> the complement of absent
#
# `declared - absent` is not a second producer for the last two: the engines
# themselves define `absent` as the complement of what they measured
# (`risk_score.score:543`), so reading it back is reading their own rule.


def _iter_categories(block: dict):
    """Every ``{name: category_entry}`` mapping in the block."""
    cats = block.get("categories")
    if isinstance(cats, dict):
        yield cats


def explicit_absent(block: dict) -> set[str]:
    """Every field the card states was NOT measured."""
    out: set[str] = set()
    absent = block.get("absent")
    if isinstance(absent, (list, tuple, set)):
        out.update(str(n) for n in absent)
    for cats in _iter_categories(block):
        for entry in cats.values():
            if not isinstance(entry, dict):
                continue
            if isinstance(entry.get("absent"), (list, tuple, set)):
                out.update(str(n) for n in entry["absent"])
    for sub in (block.get("subscores") or {}).values():
        if isinstance(sub, dict):
            na = sub.get("factors_NA")
            if isinstance(na, (list, tuple, set)):
                out.update(str(n) for n in na)
    comps = block.get("components")
    if isinstance(comps, dict):
        for name, spec in comps.items():
            if isinstance(spec, dict) and spec.get("raw") is None:
                out.add(str(name))
    return out


def explicit_present(block: dict) -> set[str]:
    """Every field the card states WAS measured, plus its measured value.

    A measured ``0.0`` is present - the value is a measurement, not a gap. Only
    an explicit absence or a ``None`` reading counts as missing.
    """
    out: set[str] = set()
    for cats in _iter_categories(block):
        for entry in cats.values():
            if not isinstance(entry, dict):
                continue
            for key in ("components", "present"):
                names = entry.get(key)
                if isinstance(names, (list, tuple, set, dict)):
                    out.update(str(n) for n in names)
    for sub in (block.get("subscores") or {}).values():
        if isinstance(sub, dict):
            cov = sub.get("coverage")
            if isinstance(cov, dict) and isinstance(cov.get("metrics"), (list, tuple, set)):
                out.update(str(n) for n in cov["metrics"])
    comps = block.get("components")
    if isinstance(comps, dict):
        for name, spec in comps.items():
            if isinstance(spec, dict):
                if spec.get("raw") is not None:
                    out.add(str(name))
            elif spec is not None and not isinstance(spec, dict):
                out.add(str(name))
    return out


def measured_values(block: dict) -> dict[str, float]:
    """``{field: value}`` where the card carries the number, not just the name."""
    out: dict[str, float] = {}
    comps = block.get("components")
    if isinstance(comps, dict):
        for name, spec in comps.items():
            val = spec.get("aligned") if isinstance(spec, dict) else spec
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out[str(name)] = float(val)
    return out


def field_states(block: dict, declared: dict) -> dict[str, str]:
    """``{field: "present" | "absent"}`` for the fields this card states.

    Fields the card says nothing about are OMITTED - they leave the denominator
    rather than being guessed at (the same rule ``breadth_with_gate`` applies to
    a panel below ``min_n``).
    """
    if not isinstance(block, dict):
        return {}
    absent = explicit_absent(block)
    present = explicit_present(block)
    has_absent_list = isinstance(block.get("absent"), (list, tuple, set))
    if not present and has_absent_list:
        # The complement rule, stated by the engines themselves. An EMPTY
        # `absent` list is the strongest form of it - nothing is missing, so
        # every declared field was measured.
        present = {f for f in declared if f not in absent}
    states: dict[str, str] = {}
    for f in present:
        states[f] = "present"
    for f in absent:
        states.setdefault(f, "absent")
    return states


# ---------------------------------------------------------------------------
# The call-site scan: is the declared producer ever reached?
# ---------------------------------------------------------------------------


def _module_file(module: str) -> str | None:
    """Resolve a dotted module tail (``news_relevance``) to a repo-relative file."""
    tail = module.rsplit(".", 1)[-1]
    if not tail:
        return None
    for root in LIVE_ROOTS:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if f"{tail}.py" in files:
                return os.path.join(dirpath, f"{tail}.py").replace("\\", "/")
    return None


def parse_producer(spec: str) -> tuple[str | None, tuple[str, ...]]:
    """``(own_file_or_None, (func, ...))`` from a declared producer string.

    Handles both declared shapes and the ``a + b`` two-producer form. Returns
    ``(None, ())`` when the string names no callable (a prose note, an empty
    producer, ``caller-supplied``).
    """
    text = str(spec or "").strip()
    if not text:
        return None, ()
    text = text.split("(")[0].strip()
    own: str | None = None
    funcs: list[str] = []
    for part in text.split("+"):
        part = part.strip()
        if not part:
            continue
        if "::" in part:
            head, rest = part.split("::", 1)
            head = head.strip()
            own = own or (head if head.endswith(".py") else _module_file(head))
        elif "." in part:
            head, rest = part.rsplit(".", 1)
            own = own or _module_file(head)
        else:
            # A bare ``name:line`` - the second half of a two-producer string
            # such as ``sentiment.mention_volume:43 + decayed_weight:91``. It
            # names a callable with no module of its own. Requiring the ``:line``
            # keeps a prose note ("caller-supplied", "no producer declared") from
            # being read as a function name.
            if not re.fullmatch(r"[A-Za-z_]\w*:\d+", part):
                continue
            rest = part
        m = re.match(r"\s*([A-Za-z_]\w*)", rest.split(":")[0])
        if m:
            funcs.append(m.group(1))
    return own, tuple(funcs)


def _called_names(path: str) -> set[str]:
    """Every function name called in one file, read from its AST.

    AST, not a text search: the engines cite their producers as string literals
    in their own component tables, and a citation is not a call.

    Import aliases are resolved, because the live path routinely renames a
    producer on import - ``from ...liquidity_risk import days_to_absorb as
    _dta`` then ``_dta(...)`` (``analysis_tools.get_liquidation_days``). Reading
    only the call node's own name would report that producer as never called,
    which is a manufactured defect.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (OSError, SyntaxError, ValueError):
        return set()
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.Import):
            for a in node.names:
                local = a.asname or a.name.split(".")[0]
                aliases[local] = a.name.rsplit(".", 1)[-1]
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        called: str | None = None
        if isinstance(fn, ast.Name):
            called = fn.id
        elif isinstance(fn, ast.Attribute):
            called = fn.attr
        if called:
            names.add(called)
            if called in aliases:
                names.add(aliases[called])
    return names


def _repo_relative(path: str) -> str:
    return os.path.abspath(path).replace("\\", "/")


def _defines(path: str, funcs: tuple[str, ...]) -> bool:
    """Does this file define any of these top-level function names?"""
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (OSError, SyntaxError, ValueError):
        return False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in funcs:
            return True
    return False


def _resolve_own(own: str | None) -> str | None:
    """Resolve a producer's own file, which may be package-relative.

    The engines spell their producers the house way - ``strategies/
    market_breadth.py``, not ``tradingagents/strategies/market_breadth.py`` - so
    a bare relative path is tried as-is and then under each live root. This is
    the same two-candidate resolution ``test_regime_score`` applies to the same
    strings.
    """
    if not own:
        return None
    if os.path.isfile(own):
        return own
    for root in LIVE_ROOTS:
        cand = os.path.join(root, own)
        if os.path.isfile(cand):
            return cand
    return None


def has_call_site(producer: str, *, roots: tuple[str, ...] = LIVE_ROOTS) -> bool | None:
    """Is the declared producer called anywhere outside its own module?

    ``None`` - never a silent ``False`` - when the producer string cannot be
    tied to a function this layer can see. Three cases return ``None``: no
    callable is named at all; the named module resolves to no file here; or the
    resolved file does not actually define the named function (a same-named
    module in another checkout, e.g. ``book_risk``). Claiming ``unwired`` on any
    of those would manufacture a defect that does not exist.
    """
    own, funcs = parse_producer(producer)
    if not funcs:
        return None
    resolved = _resolve_own(own)
    if resolved is None:
        return None
    own_abs = _repo_relative(resolved)
    if not _defines(resolved, funcs):
        return None
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fname)
                if _repo_relative(path) == own_abs:
                    continue
                if _called_names(path) & set(funcs):
                    return True
    return False


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify(fill: float | None, producer: str, wired: bool | None,
             *, has_producer_column: bool = True) -> str:
    """The field's class, from its fill rate and whether its producer is reached.

    A healthy field is ``ok`` regardless of its producer string. A field that is
    never measured is only actionable once we know whether the producer exists
    and whether anything calls it.

    ``has_producer_column`` is False for an engine whose declaration carries no
    producer at all (``fundamental_score``, whose factors come from
    ``factor_schema.SUBSCORE_FACTORS``). An empty producer there says nothing
    about the field, so it is ``unknown`` rather than a manufactured ``unbuilt``.
    """
    if fill is None:
        return "unknown"
    if fill >= FILL_OK:
        return "ok"
    if fill >= FILL_MONITOR:
        return "monitor"
    if fill > 0.0:
        return "sparse"
    if not str(producer or "").strip():
        return "unbuilt" if has_producer_column else "unknown"
    if wired is True:
        return "structural"
    if wired is False:
        return "unwired"
    return "unknown"


def action_for(klass: str) -> str:
    """The one-line action for a class, so the report is a to-do list."""
    return {
        "ok": ACTION_OK,
        "monitor": ACTION_MONITOR,
        "sparse": ACTION_SPARSE,
        "unbuilt": ACTION_UNBUILT,
        "unwired": ACTION_UNWIRED,
        "structural": ACTION_STRUCTURAL,
        "unknown": ACTION_UNKNOWN,
    }.get(klass, ACTION_UNKNOWN)


# ---------------------------------------------------------------------------
# The scorecard
# ---------------------------------------------------------------------------


def build_scorecard(reports_dir: str = DEFAULT_REPORTS_DIR, *, limit: int | None = None,
                    engines: tuple[str, ...] | None = None) -> dict:
    """Per-field fill rates over every tree under ``reports_dir``.

    The denominator for a field is the number of trees where its engine was
    **measured** - an engine whose gate was off is not part of the scorecard, so
    it cannot drag a field's fill rate down (master rule 3).
    """
    registry = engine_registry()
    cards = load_cards(reports_dir, limit=limit)
    wanted = tuple(engines) if engines else tuple(
        name for name, ent in registry.items() if ent.get("available")
    )

    engines_out: dict[str, dict] = {}
    for engine in wanted:
        ent = registry.get(engine) or {}
        declared = {str(k): (v or {}) for k, v in (ent.get("factors") or {}).items()}
        if not declared:
            continue
        counts: dict[str, int] = dict.fromkeys(declared, 0)
        zeros: dict[str, int] = dict.fromkeys(declared, 0)
        stated: dict[str, int] = dict.fromkeys(declared, 0)
        trees_measured = 0
        for _name, card in cards:
            block = card.get(engine)
            if not isinstance(block, dict) or block.get("score") is None:
                # The engine was not part of this tree's scorecard.
                continue
            trees_measured += 1
            states = field_states(block, declared)
            values = measured_values(block)
            for field, state in states.items():
                if field not in counts:
                    continue
                stated[field] += 1
                if state == "present":
                    counts[field] += 1
                    if abs(values.get(field, 1.0)) <= ZERO_EPS and field in values:
                        zeros[field] += 1
        fields: dict[str, dict] = {}
        producer_column = any(
            str((spec or {}).get("producer") or "").strip() for spec in declared.values()
        )
        for field, spec in declared.items():
            denom = stated[field]
            fill = (counts[field] / denom) if denom else None
            producer = str((spec or {}).get("producer") or "")
            wired = has_call_site(producer) if (fill == 0.0) else None
            klass = classify(fill, producer, wired, has_producer_column=producer_column)
            fields[field] = {
                "category": str((spec or {}).get("category") or ""),
                "producer": producer,
                "measured": counts[field],
                "stated": denom,
                "fill_rate": fill,
                "wired": wired,
                "class": klass,
                "action": action_for(klass),
                "flat_zero": (zeros[field] if zeros[field] else 0),
            }
        engines_out[engine] = {
            "module": ent.get("module", ""),
            "trees_measured": trees_measured,
            "declared": len(declared),
            "fields": fields,
        }

    return {
        "reports_dir": os.path.abspath(os.path.expanduser(str(reports_dir))),
        "trees": len(cards),
        "trees_with_cards": len(cards),
        "engines": engines_out,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _tally(fields: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in fields.values():
        out[f["class"]] = out.get(f["class"], 0) + 1
    return out


def render_text(report: dict) -> str:
    """The human-readable scorecard: per engine, worst fields first."""
    engines = report.get("engines") or {}
    lines = [
        "## Field coverage scorecard (advisory)",
        f"trees read: {report.get('trees', 0)} | "
        f"engines measured: {len(engines)} | "
        f"thresholds: ok >= {FILL_OK}, monitor >= {FILL_MONITOR}",
    ]
    if not engines or not report.get("trees"):
        lines.append("no trees with a run_card.json under the reports dir")
        return "\n".join(lines)

    total = {"ok": 0, "monitor": 0, "sparse": 0, "unbuilt": 0,
             "unwired": 0, "structural": 0, "unknown": 0}
    for engine in sorted(engines):
        ent = engines[engine]
        tally = _tally(ent["fields"])
        for k, v in tally.items():
            total[k] = total.get(k, 0) + v
        lines.append("")
        lines.append(f"### {engine}  (module {ent['module']}; "
                     f"trees measured {ent['trees_measured']}; "
                     f"declared {ent['declared']})")
        lines.append(f"  {tally}")
        rows = sorted(
            ent["fields"].items(),
            key=lambda kv: (kv[1]["fill_rate"] if kv[1]["fill_rate"] is not None else 1.0,
                            kv[0]),
        )
        for field, f in rows:
            fill = f["fill_rate"]
            shown = "  n/a" if fill is None else f"{fill * 100:5.1f}%"
            mark = {"ok": "  ", "monitor": "! ", "sparse": "! ",
                    "unbuilt": "X ", "unwired": "X ", "structural": "x "}.get(f["class"], "? ")
            lines.append(
                f"  {mark}{shown} {field:<28} {f['measured']:>3}/{f['stated']:<3} "
                f"{f['class']:<11} {f['action']}"
            )
            if f["producer"]:
                lines.append(f"       producer: {f['producer']}")
            if f["flat_zero"]:
                lines.append(f"       flat_zero: measured {f['flat_zero']} time(s), "
                             f"always 0.0 - check for a placeholder")

    lines.append("")
    lines.append(f"totals: {total}")
    lines.append("legend: X = actionable gap (unbuilt/unwired), "
                 "x = structural (producer runs, data absent), ! = partial")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--reports-dir", default=DEFAULT_REPORTS_DIR,
                        help="dir holding the run trees (default: reports)")
    parser.add_argument("--limit", type=int, default=None,
                        help="read at most N trees, newest first")
    parser.add_argument("--engine", action="append", default=None,
                        help="restrict to an engine (repeatable)")
    parser.add_argument("--json", action="store_true", help="emit JSON, not text")
    parser.add_argument("--actionable", action="store_true",
                        help="print only the unbuilt/unwired fields")
    args = parser.parse_args(argv)

    report = build_scorecard(args.reports_dir, limit=args.limit,
                             engines=tuple(args.engine) if args.engine else None)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if args.actionable:
        for engine in sorted(report.get("engines") or {}):
            for field, f in sorted((report["engines"][engine]["fields"]).items()):
                if f["class"] in ("unbuilt", "unwired"):
                    print(f"{engine:<20} {field:<28} {f['class']:<9} "
                          f"{f['producer'] or '(no producer declared)'}")
        return 0
    print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ACTION_MONITOR",
    "ACTION_OK",
    "ACTION_SPARSE",
    "ACTION_STRUCTURAL",
    "ACTION_UNBUILT",
    "ACTION_UNKNOWN",
    "ACTION_UNWIRED",
    "DEFAULT_REPORTS_DIR",
    "FILL_MONITOR",
    "FILL_OK",
    "LIVE_ROOTS",
    "action_for",
    "build_scorecard",
    "classify",
    "explicit_absent",
    "explicit_present",
    "field_states",
    "has_call_site",
    "load_cards",
    "main",
    "measured_values",
    "parse_producer",
    "render_text",
]
