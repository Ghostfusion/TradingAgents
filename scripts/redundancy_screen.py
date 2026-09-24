#!/usr/bin/env python3
"""X2 redundancy screen runner: double-selection LASSO over the engine's components.

    py -3.12 scripts/redundancy_screen.py --input screen.json [--results-dir DIR]

Pure + offline, no LLM, no network. The input JSON carries the pane the screen
runs over::

    {"candidates": {"mom_20": [...], "rsi_14": [...]},
     "controls":   {"market_beta": [...]},
     "target":     [...],                 # the forward return to screen against
     "selection_window": [0, 120],        # fit the screen here
     "evaluation_window": [120, 300]}     # check the survivor list here

The windows MUST be disjoint (the screen raises otherwise): a selection that
overlaps its evaluation is in-sample. Every dropped component is one row in the
H7 refusal ledger when ``enable_refusal_ledger`` is on, naming this screen and
both windows - the screen's consumption is a *decision*, so the decision has to
be readable afterwards.

Offline by construction: nothing here is reachable from ``prepare_initial_state``,
``finalize_run`` or any agent tool (ground rule 8).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"no screen input {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", required=True,
                        help="JSON pane: candidates, controls, target, windows")
    parser.add_argument("--results-dir", default=None,
                        help="refusal-ledger directory (needs enable_refusal_ledger)")
    args = parser.parse_args(argv)

    from tradingagents.strategies.alpha_zoo import redundancy_screen

    try:
        pane = _load(args.input)
    except (OSError, ValueError) as exc:
        print(f"[err] {exc}", file=sys.stderr)
        return 2

    try:
        result = redundancy_screen(
            pane.get("candidates") or {},
            pane.get("controls") or {},
            pane.get("target") or [],
            selection_window=tuple(pane["selection_window"]),
            evaluation_window=tuple(pane["evaluation_window"]),
            results_dir=args.results_dir,
        )
    except (KeyError, TypeError, ValueError) as exc:
        print(f"[err] {exc}", file=sys.stderr)
        return 2

    print(f"== redundancy screen {result['window']} ==")
    if result["unavailable"]:
        print(f"[unavailable] {result['unavailable']}")
    print(f"kept ({len(result['kept'])}): {', '.join(result['kept']) or '-'}")
    print(f"dropped ({len(result['dropped'])}): {', '.join(result['dropped']) or '-'}")
    print(f"{'component':<24}{'selection':<12}{'t_sel':<10}{'evaluation':<12}{'t_eval':<10}")
    for name in sorted(result["coefficients"]):
        c = result["coefficients"][name]
        fmt = lambda v: "n/a" if v is None else f"{v:.4f}"  # noqa: E731
        print(f"{name:<24}{fmt(c['selection']):<12}{fmt(c['t_selection']):<10}"
              f"{fmt(c['evaluation']):<12}{fmt(c['t_evaluation']):<10}")
    print("(dropped components are logged in the refusal ledger when "
          "enable_refusal_ledger is on)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
