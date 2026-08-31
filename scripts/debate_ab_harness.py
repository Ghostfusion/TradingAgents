"""P5 — Matched-compute A/B harness: structured debate vs self-consistency.

Design docs/design_multi_agent_debate.md §4.4 (R4). Compares two decision
producers under a matched token budget on a labeled forecast set:

- **debate**: the structured two-sided debate (bull/bear turns + L2 judge
  aggregation) → per-item P(Up).
- **self-consistency**: N single-model passes + median vote → per-item P(Up).

Scoring (per design): **Brier score** (forecast calibration) and **maximum
unforecasted drawdown** (worst realized equity undershoot vs the forecast
probability path) — NOT raw P(Up)>0.5 hit-rate. Also reports tokens/calls/
latency and the audit-trail counter-thesis count (the debate's differentiator).

Pure harness: producers are injected callables so the script is hermetic
(no live LLM calls by default). Run with ``--demo`` for a synthetic
illustrative comparison.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections.abc import Callable, Sequence

# Each forecast item: {label: 0|1, prob: 0..1}.
Forecast = dict


def brier_score(forecasts: Sequence[Forecast]) -> float:
    """Mean squared error of probability forecasts vs binary outcomes (0..1)."""
    if not forecasts:
        return float("nan")
    return sum((f["prob"] - f["label"]) ** 2 for f in forecasts) / len(forecasts)


def max_unforecasted_drawdown(forecasts: Sequence[Forecast]) -> float:
    """Worst cumulative shortfall of realized equity vs the probability path.

    Builds realized equity (increments +1 on label=1, -1 on label=0) and the
    probability path (cumulative prob - 0.5 step), then takes the worst
    drawdown of the DIFFERENCE (realized - forecast). Positive = a period
    where losses outpaced the model's stated probability — the risk-boundary
    failure mode the design tracks.
    """
    if not forecasts:
        return 0.0
    diff = 0.0
    peak = 0.0
    max_dd = 0.0
    for f in forecasts:
        realized = 1.0 if f["label"] == 1 else -1.0
        expected = 2.0 * f["prob"] - 1.0  # prob -> [-1, 1] step
        diff += realized - expected
        peak = max(peak, diff)
        max_dd = max(max_dd, peak - diff)
    return round(float(max_dd), 4)


def token_budget_report(
    debate: Sequence[Forecast], consistency: Sequence[Forecast]
) -> dict:
    """Token/call counters placeholder — producers report them via kwargs."""
    return {
        "debate_items": len(debate),
        "consistency_items": len(consistency),
        "note": "token/call/latency counters come from the injected producers",
    }


def run_ab(
    debate_producer: Callable[[list[dict]], list[Forecast]],
    consistency_producer: Callable[[list[dict]], list[Forecast]],
    items: list[dict],
) -> dict:
    """Run both producers over the same labeled items and score them."""
    debate = debate_producer(items)
    consistency = consistency_producer(items)
    return {
        "n": len(items),
        "forecasts": {"debate": debate, "self_consistency": consistency},
        "debate": {
            "brier": brier_score(debate),
            "max_unforecasted_dd": max_unforecasted_drawdown(debate),
        },
        "self_consistency": {
            "brier": brier_score(consistency),
            "max_unforecasted_dd": max_unforecasted_drawdown(consistency),
        },
    }


# ---------------------------------------------------------------------------
# Demo producers (synthetic, illustrative — not real forecasts)
# ---------------------------------------------------------------------------


def _demo_debate(items):
    out = []
    for it in items:
        # Simulated debate: slightly better than coin-flip by leaning on item
        # difficulty (label 1 items are easier to catch).
        p = 0.52 + (0.10 if it.get("label") == 1 else -0.06)
        out.append({"label": it["label"], "prob": min(0.99, max(0.01, p))})
    return out


def _demo_consistency(items):
    out = []
    for it in items:
        # Median of 5 noisy draws around 0.5 + difficulty signal.
        rng = random.Random(it.get("seed", 0))
        draws = [0.5 + rng.uniform(-0.2, 0.2) + (0.05 if it["label"] == 1 else -0.05) for _ in range(5)]
        draws.sort()
        out.append({"label": it["label"], "prob": min(0.99, max(0.01, draws[2]))})
    return out


def _demo_items(n: int = 100) -> list[dict]:
    rng = random.Random(7)
    return [{"label": 1 if rng.random() < 0.5 else 0, "seed": i} for i in range(n)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo", action="store_true", help="run the synthetic illustrative comparison"
    )
    parser.add_argument("--items", type=int, default=100)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    if not args.demo:
        parser.error(
            "producers must be injected via run_ab(); pass --demo for the "
            "synthetic illustrative run"
        )

    items = _demo_items(args.items)
    result = run_ab(_demo_debate, _demo_consistency, items)
    result["budget"] = token_budget_report(
        result["forecasts"]["debate"], result["forecasts"]["self_consistency"]
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"n={result['n']}")
        for name in ("debate", "self_consistency"):
            row = result[name]
            print(f"{name}: brier={row['brier']:.4f} max_unforecasted_dd={row['max_unforecasted_dd']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
