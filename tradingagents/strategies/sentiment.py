"""Phase 6 - alternative-data velocity & analyst consensus.

  - sentiment_velocity(series): rate of change in sentiment (e.g. daily
    polarity means) over a small window - catching accelerating interest.
  - mention_spike(series, recent, history): ratio of recent mentions to
    baseline; flags news/social heat.
  - consensus_over_seeds(verdicts): majority threshold over N LLM samples
    (FLAG-trader style diversified reasoning; used when analysts run with
    multiple seeds).
  - agree_rate(verdicts) helper: fraction of seeds in the majority bucket.
"""

from __future__ import annotations


def sentiment_velocity(sentiment_series: list, window: int = 5) -> "float | None":
    """OLS-ish slope of sentiment over the recent window -> /day change."""
    vals = [v for v in sentiment_series if v is not None]
    if len(vals) < 3:
        return None
    sample = vals[-window:]
    if len(sample) < 2:
        return None
    x = list(range(len(sample)))
    n = len(sample)
    xm = sum(x) / n
    ym = sum(sample) / n
    den = sum((xi - xm) ** 2 for xi in x)
    if den == 0:
        return None
    return sum((xi - xm) * (yi - ym) for xi, yi in zip(x, sample)) / den


def mention_volume(history: list, recent: int = 1) -> "float | None":
    """Recent mentions vs historic per-day baseline (ratio, >=1 hot)."""
    if not history:
        return None
    base = max(1.0, float(sum(history[:-recent]) / len(history[:-recent])) if recent < len(history) else 1.0)
    recent_sum = float(sum(history[-recent:]))
    return recent_sum / base


def consensus_overlap(verdicts: list, threshold: float = 0.5) -> "float | None":
    """Share of verdicts matching the majority bucket; None when empty."""
    if not verdicts:
        return None
    counts: dict = {}
    for v in verdicts:
        counts[v] = counts.get(v, 0) + 1
    top = max(counts.values())
    return top / len(verdicts)


def consensus_verdict(verdicts: list, threshold: float = 0.5):
    """Majority verdict if it clears the threshold, else 'mixed'."""
    if not verdicts:
        return None
    agree = consensus_overlap(verdicts, threshold)
    if agree is None or agree < threshold:
        return "mixed"
    counts: dict = {}
    for v in verdicts:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.get)


def blended_score(verdict_map: dict, weights: dict = None) -> float:
    """Blend numeric scores (e.g. sentiment -1..1) by weights -> [-1, 1]."""
    names = [k for k, v in verdict_map.items() if v is not None]
    if not names:
        return 0.0
    if weights is None:
        weights = {n: 1.0 for n in names}
    total = sum(weights.get(n, 1.0) * verdict_map[n] for n in names)
    weight_sum = sum(weights.get(n, 1.0) for n in names)
    return total / weight_sum if weight_sum else 0.0


__all__ = [
    "sentiment_velocity", "mention_volume", "consensus_overlap",
    "consensus_verdict", "blended_score",
]