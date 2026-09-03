"""LLM-proposed factor candidates, deterministic math decides (RD-Agent *pattern*).

Qlib pillar 11 port — the RD-Agent loop WITHOUT the dependency: the repo's
own LLM client drafts candidate factor expressions from the
``factor_expressions`` operator menu + a short "current factors / recent IC"
prompt; each candidate is evaluated deterministically (rank IC/ICIR/decay
via ``signal_analysis`` on PIT-labeled data), then the walk-forward+PBO gate
(``evaluate_config_gate``) applies. Only gated survivors may be adopted as
extra ``get_factor_profile`` rows (default OFF via ``factor_proposal_*``
config). Every number in the candidate sheet is computed, never narrated.

The evaluation pipeline is fully hermetic and LLM-optional:
``evaluate_candidates(proposals, data, ...)`` takes the proposal list
directly; the CLI wires the LLM, tests inject proposals.

Usage:
    py -3.12 scripts/factor_proposal_loop.py --records data/records.jsonl \\
        --out data/candidates.jsonl [--proposals 'mom_5,rsi_14']
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_records(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _score_series(records: list[dict], factor: str) -> tuple[list, list] | None:
    """(signal, forward_return) aligned lists for one factor over the records.

    Records are ``{name, as_of, features: {factor: v}, fwd_return}`` (the PIT
    ledger shape; fwd_return is the one-buffer label). Align by index across
    all records — a cross-sectional-ish pane for a single-name or a small
    universe. None when too few non-null pairs.
    """
    sig: list = []
    fwd: list = []
    for r in records:
        feat = r.get("features") or {}
        v = feat.get(factor)
        f = r.get("fwd_return")
        if v is None or f is None:
            continue
        try:
            sig.append(float(v))
            fwd.append(float(f))
        except (TypeError, ValueError):
            continue
    if len(sig) < 10:
        return None
    return sig, fwd


def evaluate_candidates(proposals: list[str], records: list[dict],
                        min_ic: float = 0.02, cost_bps: float = 10.0) -> dict:
    """Deterministic evaluation of each proposed factor expression.

    Returns ``{candidate: {ic, icir, ls_return, n, gated, adopted}}`` where
    ``gated`` is the walk-forward+PBO verdict over the directional series and
    ``adopted`` = (ic passes ``min_ic`` AND gated) — the promotion rule. A
    random-noise proposal is honestly rejected (low ic / ungated).
    """
    from scripts.evaluate_config_gate import gate_verdict
    from tradingagents.strategies.signal_analysis import (
        icir,
        quantile_long_short,
        rank_ic,
    )

    out: dict = {}
    for factor in proposals:
        pair = _score_series(records, factor)
        if pair is None:
            out[factor] = {"ic": None, "icir": None, "ls_return": None,
                           "n": 0, "gated": False, "adopted": False,
                           "reason": "too few aligned rows"}
            continue
        sig, fwd = pair
        ic = rank_ic(sig, fwd)
        # W2-4 OOS enforcement: rank IC on the trailing OOS band (leading
        # 70% is the implicit training band). A candidate is not promoted on
        # the in-sample IC alone.
        from tradingagents.strategies.evaluate import oos_split

        sig_oos, fwd_oos = oos_split(sig, fwd, train_frac=0.7)
        oos_ic = rank_ic(sig_oos, fwd_oos) if sig_oos and any(v is not None for v in fwd_oos) else None
        ir = icir([ic]) if ic is not None else None  # single-IC IR proxy
        ls = quantile_long_short(sig, fwd, n_buckets=5, cost_bps=cost_bps)
        ls_ret = ls["long_short_return"] if ls else None
        # directional series for the gate: sign(signal) * fwd
        dir_series = [float(sig[i] * fwd[i]) for i in range(len(sig))]
        verdict = gate_verdict(dir_series)
        gated = bool(verdict.get("ok"))
        adopted = bool(ic is not None and abs(ic) >= min_ic and gated
                      and (oos_ic is None or abs(oos_ic) >= min_ic * 0.5))
        out[factor] = {
            "ic": round(ic, 4) if ic is not None else None,
            "oos_ic": round(oos_ic, 4) if oos_ic is not None else None,
            "icir": round(ir, 3) if ir is not None else None,
            "ls_return": round(ls_ret, 5) if ls_ret is not None else None,
            "n": len(sig),
            "gated": gated,
            "adopted": adopted,
            "gate_reason": verdict.get("reason"),
        }
    return out


def _llm_propose(client, prompt: str, factor_menu: str) -> list[str]:
    """Draft candidate expressions via the repo LLM client; empty on failure."""
    try:
        text = client.invoke(prompt + "\n\nAvailable operators: " + factor_menu)
        out = []
        for chunk in str(text).split(","):
            name = "".join(ch for ch in chunk.strip() if ch.isalnum() or ch == "_")
            if name and name not in out:
                out.append(name)
        return out
    except Exception:  # noqa: BLE001 - LLM failure degrades to no proposals
        return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--records", required=True, help="JSONL PIT records")
    parser.add_argument("--out", required=True, help="candidate sheet JSONL")
    parser.add_argument("--proposals", default=None,
                        help="comma list of factor expressions (skip the LLM)")
    parser.add_argument("--min-ic", type=float, default=0.02)
    args = parser.parse_args(argv)

    records = _load_records(args.records)
    if not records:
        print(json.dumps({"ok": False, "error": "no records"}))
        return 2

    if args.proposals:
        proposals = [p.strip() for p in args.proposals.split(",") if p.strip()]
    else:
        try:
            from tradingagents.llm_clients import get_client

            client = get_client()
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": f"LLM client unavailable: {exc}"}))
            return 3
        from tradingagents.strategies.factor_expressions import _ALPHA158_SUBSET

        proposals = _llm_propose(client, "Propose 3-5 factor expressions from "
                                          "the operator menu (comma-separated).",
                                 ", ".join(_ALPHA158_SUBSET))

    results = evaluate_candidates(proposals, records, min_ic=args.min_ic)
    adopted = [f for f, r in results.items() if r["adopted"]]

    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            for factor, res in results.items():
                fh.write(json.dumps({"candidate": factor, **res}) + "\n")
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"write failed: {exc}"}))
        return 4

    print(json.dumps({"ok": True, "n_candidates": len(results),
                      "adopted": adopted, "out": args.out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
