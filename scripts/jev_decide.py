"""TypeSafe decisions-model CLI (``typesafe/jev-1.13`` on OpenRouter).

The model client and the judgement recipes live in ``tradingagents/jev.py`` -
the report pipeline uses the same code through :func:`tradingagents.jev.judge_tree`,
so this file is only the argument surface and the read-out.

    py -3.12 scripts/jev_decide.py
    py -3.12 scripts/jev_decide.py --tree reports/MSFT_20260920_145644
    py -3.12 scripts/jev_decide.py --stems market,news --json jev.json
    py -3.12 scripts/jev_decide.py --stems 2_research/bull,5_portfolio/decision
    py -3.12 scripts/jev_decide.py --all
    py -3.12 scripts/jev_decide.py --state-file notes.md
    py -3.12 scripts/jev_decide.py --questions my_questions.json

    # the standard "judge this symbol's reports" recipe
    py -3.12 scripts/jev_decide.py --tree reports/NVDA_20260921_114014 --verdict

``--verdict`` is the three things that recipe needs, in one flag: the four
ANALYST reports only (never the research/risk/portfolio documents, which already
carry a conclusion), their position language neutralised, and the buy/hold/sell
battery. The pieces are available alone - ``--neutralize``, ``--rating``.

A tree is STAGED, so a stem is not always an analyst report. ``--stems`` takes a
bare analyst stem (``market`` -> ``1_analysts/market.md``), a stage-qualified
path (``2_research/bull``), or a tree-root report (``complete_report``).
``--all`` sends every report in the tree in pipeline order.

Exit code: 0 = every call answered; 1 = at least one call failed (the failure
is printed with the vendor's own message, never swallowed).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Iterable

from tradingagents.jev import (
    ANALYST_STEMS,
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    DEFAULT_QUESTIONS,
    DEFAULT_TIMEOUT,
    POSITION_MARKER,
    RATING_QUESTIONS,
    all_report_states,
    decide,
    neutralize_positions,
    newest_tree,
    report_states,
    resolve_key,
    result_lines,
    validate_questions,
)


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
    p.add_argument("--stems", default=None,
                   help="comma-separated reports: a bare analyst stem (`market`), a "
                        "stage-qualified path (`2_research/bull`, `5_portfolio/decision`) "
                        "or a tree-root report (`complete_report`). "
                        f"Default: {','.join(ANALYST_STEMS)}")
    scope = p.add_mutually_exclusive_group()
    scope.add_argument("--all", dest="all_reports", action="store_true",
                       help="send every report in the tree, in pipeline order")
    p.add_argument("--neutralize", action="store_true",
                   help="replace the report's own position language (buy/sell/hold, "
                        "overweight/underweight, ...) with a marker before sending, so "
                        "the judge reads the evidence and not the conclusion")
    p.add_argument("--rating", action="store_true",
                   help="judge with the buy/hold/sell battery instead of "
                        "stance/evidence/horizon")
    scope.add_argument("--verdict", action="store_true",
                       help="the standard recipe for 'judge this symbol's reports': the "
                            "four ANALYST reports only, position language neutralised, "
                            "judged for a buy/hold/sell rating (implies --neutralize "
                            "--rating)")
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

    want_rating = args.rating or args.verdict
    questions = (
        _load_questions(args.questions) if args.questions
        else RATING_QUESTIONS if want_rating
        else DEFAULT_QUESTIONS
    )

    if args.state_file:
        path = pathlib.Path(args.state_file)
        states = [(path.stem, path.read_text(encoding="utf-8", errors="replace"))]
        origin = str(path)
    elif args.state:
        states = [("state", args.state)]
        origin = "<literal>"
    else:
        tree = pathlib.Path(args.tree) if args.tree else newest_tree(repo / "reports")
        if args.all_reports:
            states = all_report_states(tree)
        else:
            raw_stems = args.stems or ",".join(ANALYST_STEMS)
            states = report_states(tree, [s.strip() for s in raw_stems.split(",") if s.strip()])
        origin = tree.name
        if not states:
            print(f"no matching reports in {tree}", file=sys.stderr)
            return 1

    if args.verdict or args.neutralize:
        cleaned: list[tuple[str, str]] = []
        stripped = 0
        for name, state in states:
            text, hits = neutralize_positions(state)
            stripped += hits
            print(f"neutralize: {name}: {hits} position term(s) -> {POSITION_MARKER}")
            cleaned.append((name, text))
        states = cleaned
        print(f"neutralize: {stripped} replacement(s) across {len(states)} report(s)")

    print(f"origin  : {origin}")
    print(f"model   : {args.model}")
    print(f"endpoint: {args.endpoint}")
    print(f"states  : {[name for name, _ in states]}")
    print(f"battery : {','.join(questions)}")
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
