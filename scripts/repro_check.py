"""Reproducibility check: run one symbol N times and measure verdict deviation.

The whole point of the D1-D3 work (judge ensemble, deterministic sampling,
free-text-fallback flag) is to collapse the same-data verdict flips (TSM
2026-09-07 produced Overweight -> Underweight -> Hold on identical 428.91
data). This script quantifies that deviation:

  - runs ``batch.analyze`` N times (same symbol/date, fresh graph each time),
  - extracts the parsed 5-tier rating from each produced decision,
  - prints every run's rating + the agreement / flip metrics.

Usage::
    py -3.12 scripts/repro_check.py --symbol tsm --runs 3 --workers 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from batch import analyze
from tradingagents.agents.utils.evidence_gather import MODEL_POOL_KEY

_CONFIG_HASH_CACHE: dict = {}


def _config_hash() -> str:
    """One stable hash of the run-affecting config, so 'same input' is provable."""
    key = ("n/a",)
    if key in _CONFIG_HASH_CACHE:
        return _CONFIG_HASH_CACHE[key]
    from tradingagents.default_config import DEFAULT_CONFIG

    relevant = {
        k: DEFAULT_CONFIG[k]
        for k in (
            "llm_provider",
            "deep_think_llm",
            "quick_think_llm",
            "backup_llm",
            "temperature",
            "debate_temperature",
            "debate_judge_ensemble",
            "debate_judge_model",
            "debate_bull_model",
            "debate_bear_model",
            "debate_max_rounds",
            "max_debate_rounds",
            "max_risk_discuss_rounds",
            "openrouter_reasoning_effort",
        )
        if k in DEFAULT_CONFIG
    }
    h = hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()[:12]
    _CONFIG_HASH_CACHE[key] = h
    return h


def _print_evidence_diff(report_dirs) -> None:
    """Print per-run forced-tool evidence + a cross-run composition/status diff.

    Reads ``tool_evidence.json`` from each run's report tree (persisted by
    ``tradingagents.reporting`` when the deterministic gatherer ran). When the
    config has no forced tools the file is absent everywhere — say so so the
    user knows the check needs ``analyst_forced_tools`` set.
    """
    evidence: list[dict] = []
    for d in report_dirs:
        p = Path(d) / "tool_evidence.json"
        if p.exists():
            with open(p, encoding="utf-8") as fh:
                evidence.append(json.load(fh))
        else:
            evidence.append(None)

    print("\n=== forced-tool evidence diff ===")
    if all(e is None for e in evidence):
        print("no tool_evidence.json in any run — analyst_forced_tools is off;")
        print("set it to diff the per-run tool composition.")
        return
    if any(e is None for e in evidence):
        print("WARNING: some runs have evidence, some don't — config changed mid-check?")

    # Build tool → {status: str, statuses per run} across analysts.
    from collections import Counter as _C

    rows: dict[str, list] = {}
    pools: dict[str, set] = {}
    for run_i, ev in enumerate(evidence):
        if ev is None:
            continue
        for analyst_key, payload in (ev or {}).items():
            if analyst_key.startswith("_"):
                # Metadata key (e.g. _model_pool); not a leaf list.
                continue
            for leaf in payload:
                key = f"{analyst_key}:{leaf['tool']}"
                row = rows.setdefault(key, [None] * len(evidence))
                row[run_i] = leaf.get("status")
        for analyst_key, names in (ev.get(MODEL_POOL_KEY) or {}).items():
            pools.setdefault(analyst_key, set()).update(names)

    if pools:
        print("\nMODEL-pool (not gathered; the agent LLM controls these):")
        for analyst_key in sorted(pools):
            print(f"  {analyst_key}: " + ", ".join(sorted(pools[analyst_key])))

    if not rows:
        print("evidence files exist but are empty.")
        return

    status_counts = {k: _C(r for r in v if r) for k, v in rows.items()}
    print(f"{'tool':<52} " + " ".join(f"run{i + 1}" for i in range(len(evidence))))
    differing = []
    for key in sorted(rows):
        statuses = rows[key]
        cells = [f"{s or '-':>6}" for s in statuses]
        print(f"{key:<52} " + " ".join(cells))
        if len(_C(s for s in statuses if s)) > 1:
            differing.append(key)
    if differing:
        print("\nDIFFERING STATUS ACROSS RUNS:")
        for key in differing:
            print("  ", key, status_counts[key])
    else:
        print("\nall tool statuses identical across runs (composition + status stable)")

    _figure_cross_check(report_dirs, evidence)


_DEC_RE = re.compile(r"\d+\.\d+")


def _float_tokens(text: str) -> set:
    """Distinct decimal numbers in ``text`` (the figures that carry signal;
    bare integers are too noisy for a cheap grounding check)."""
    out = set()
    for m in _DEC_RE.finditer(text):
        try:
            out.add(float(m.group()))
        except ValueError:
            continue
    return out


def _matches(flt: float, refs: set) -> bool:
    """Roughly same value as some evidence figure (<=0.5% relative)."""
    for ref in refs:
        denom = max(abs(ref), abs(flt), 1e-9)
        if abs(flt - ref) / denom <= 0.005:
            return True
    return False


def _figure_cross_check(report_dirs: list, evidence: list) -> None:
    """Advisory figure-grounding check: decimal numbers in each analyst
    report that have no matching value in the run's tool evidence are
    candidates for the copy-garble class seen on QCOM 2026-09-07 news.md
    ('303.9 -> 944B' for the TGA draw, '0.51%' for 10.51%, '7.6%' for 7.4%).
    Heuristic: tolerance-matched, so same-number different-formatting passes;
    integer deltas (e.g. '-5%' vs '-4%') are not covered - the analyst
    prompt's verbatim-citation rule is the primary guard, this is the cheap
    tripwire."""
    print("\n=== analyst-report figure cross-check (verbatim grounding) ===")
    for run_i, d in enumerate(report_dirs):
        ev = evidence[run_i]
        if ev is None:
            continue
        ev_dec: set = set()
        for analyst_key, payload in (ev or {}).items():
            if analyst_key.startswith("_"):
                continue
            for leaf in payload:
                ev_dec |= _float_tokens(str(leaf.get("content") or ""))
        md_dir = Path(d) / "1_analysts"
        if not md_dir.exists():
            print(f"  run{run_i + 1}: no 1_analysts/ dir, skipped")
            continue
        for md in sorted(md_dir.glob("*.md")):
            text = md.read_text(encoding="utf-8", errors="ignore")
            suspect = sorted(f for f in _float_tokens(text) if not _matches(f, ev_dec))
            if suspect:
                shown = ", ".join(f"{v:.6g}" for v in suspect[:25])
                print(
                    f"  run{run_i + 1} {md.stem}: {len(suspect)} figure(s) with no "
                    f"matching tool-output value: {shown}" + (" …" if len(suspect) > 25 else "")
                )
            else:
                print(f"  run{run_i + 1} {md.stem}: all decimal figures grounded in tool output")
    print("  (heuristic: ±0.5% tolerance; integers/pool-tool figures are not covered)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--analysts", nargs="+", default=["market", "social", "news", "fundamentals"])
    parser.add_argument("--depth", default="deep")
    parser.add_argument(
        "--evidence",
        action="store_true",
        help=(
            "print the per-run forced-tool evidence (tool_evidence.json) and a "
            "cross-run composition/status diff, so 'did every run see the same "
            "tool set' is answerable from the saved reports"
        ),
    )
    args = parser.parse_args()

    from batch import DEPTH_LEVELS

    depth = DEPTH_LEVELS[args.depth]
    analysts = tuple(args.analysts)
    cfg_hash = _config_hash()
    print(f"repro-check {args.symbol} x{args.runs} @ config_hash={cfg_hash}")

    results = []
    report_dirs: list[str] = []
    for i in range(args.runs):
        symbol, decision, report_dir, wall, rating = analyze(
            args.symbol,
            args.date or __import__("datetime").date.today().isoformat(),
            analysts,
            depth,
        )
        results.append(rating)
        report_dirs.append(report_dir)
        print(f"  run {i + 1}: rating={rating} | decision={decision!r} | {wall}s | {report_dir}")
        with open(Path(report_dir) / "run_card.json", encoding="utf-8") as fh:
            run_card = json.load(fh)
        print(f"    run_card config_hash={run_card.get('config_hash')}")

    if args.evidence:
        _print_evidence_diff(report_dirs)

    from collections import Counter as _C

    counts = _C(results)
    top, top_n = counts.most_common(1)[0]
    agreement = round(top_n / len(results), 4)
    print("\n=== repro summary ===")
    print(f"ratings: {results}")
    print(f"agreement (top / n): {agreement}  ({top_n}/{len(results)} on {top})")
    print(f"config_hash: {_config_hash()}")
    return 0 if agreement == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
