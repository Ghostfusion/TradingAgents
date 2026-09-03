"""Confidence calibration + AI analyst scorecard (W1-2, W1-4).

From the prediction ledger (W1-1) rows scored against realized outcomes:

- ``calibration_table`` — bin predicted-confidence vs actual success
  (ChatGPT's 50-60% -> 56% table): shows whether "90% confidence" really
  wins ~90% of the time.
- ``scorecard`` — per-agent measurement: predictions, hit rate, avg return,
  calibration error (|reported - actual| per bin, weighted), horizon-window
  contribution. This is what lets the system say "fundamentals analyst is
  historically more reliable at 3-6 months; market analyst better at 1-5d".

All inputs are SCORED ledger rows (dicts with `outcome`); all output is
counts/ratios, None when there is nothing to measure (honest).
"""

from __future__ import annotations

_BINS = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0001)]


def calibration_table(scored_rows: list[dict]) -> list[dict]:
    """Predicted-confidence bins vs actual hit rate (W1-2).

    Each row: {bin, n, predicted_mid, actual_hit_rate, calibration_gap}.
    Rows with no confidence or no outcome are excluded (not counted as 0).
    """
    out = []
    for lo, hi in _BINS:
        rows = [
            r for r in (scored_rows or [])
            if r.get("confidence") is not None and lo <= r["confidence"] < hi
            and isinstance(r.get("outcome"), dict) and r["outcome"].get("hit") is not None
        ]
        if not rows:
            continue
        n = len(rows)
        hit = sum(1 for r in rows if r["outcome"]["hit"])
        mid = (lo + hi) / 2.0
        rate = hit / n
        out.append({
            "bin": f"{lo:.0%}-{min(hi, 1.0):.0%}",
            "n": n,
            "predicted_mid": round(mid, 3),
            "actual_hit_rate": round(rate, 3),
            "calibration_gap": round(rate - mid, 3),
        })
    return out


def _calibration_error(rows: list[dict]) -> float | None:
    tab = calibration_table(rows)
    if not tab:
        return None
    total = sum(t["n"] for t in tab)
    if total <= 0:
        return None
    err = sum(abs(t["calibration_gap"]) * t["n"] for t in tab) / total
    return round(err, 4)


def scorecard(scored_rows: list[dict], agent_field: str = "agent") -> list[dict]:
    """Per-agent measurement (W1-4).

    Groups scored ledger rows by ``agent_field`` (analyst name, debate role,
    any stored field) and reports: predictions, hit rate, avg return, mean
    |return|, and calibration error. Sorted by hit rate desc.
    """
    from collections import defaultdict

    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in (scored_rows or []):
        a = str(r.get(agent_field) or "unknown")
        by_agent[a].append(r)
    out = []
    for agent, rows in sorted(by_agent.items()):
        scored = [r for r in rows if isinstance(r.get("outcome"), dict)]
        n = len(scored)
        if n == 0:
            out.append({"agent": agent, "predictions": len(rows), "hit_rate": None,
                        "avg_return_pct": None, "calibration_error": None})
            continue
        hits = sum(1 for r in scored if r["outcome"].get("hit"))
        rets = [r["outcome"]["return_pct"] for r in scored
                if r["outcome"].get("return_pct") is not None]
        avg_ret = sum(rets) / len(rets) if rets else None
        out.append({
            "agent": agent,
            "predictions": len(rows),
            "hit_rate": round(hits / n, 3) if n else None,
            "avg_return_pct": round(avg_ret, 3) if avg_ret is not None else None,
            "calibration_error": _calibration_error(rows),
        })
    return sorted(out, key=lambda o: (o["hit_rate"] is None, -(o["hit_rate"] or 0)))


__all__ = ["calibration_table", "scorecard", "_BINS"]
