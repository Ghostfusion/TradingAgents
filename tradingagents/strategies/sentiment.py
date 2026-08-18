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

from pathlib import Path


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


def decayed_weight(age_days: float, half_life: float = 7.0) -> float:
    """Exponential freshness weight: 0.5 after one half-life."""
    if age_days < 0:
        return 0.0
    return 0.5 ** (age_days / half_life)


def _score_from_label(label):
    text = (label or "").strip().lower()
    if text in ("bullish", "positive", "buy", "long"):
        return 1.0
    if text in ("bearish", "negative", "sell", "short"):
        return -1.0
    if text in ("neutral", "hold", "flat", ""):
        return 0.0
    return None


def weighted_sentiment(messages: list) -> "float | None":
    """Recency- and credibility-weighted mean sentiment in [-1, 1]."""
    total_w = 0.0
    acc = 0.0
    for m in messages or []:
        score = m.get("score")
        if score is None:
            score = _score_from_label(m.get("label"))
        if score is None:
            continue
        try:
            score = float(score)
        except (TypeError, ValueError):
            continue
        if not -1.0 <= score <= 1.0:
            continue
        weight = decayed_weight(m.get("age_days", 0.0)) * max(0.0, float(m.get("credibility", 1.0)))
        acc += score * weight
        total_w += weight
    return acc / total_w if total_w > 0 else None


def surprise_velocity(current_score: "float | None", history: list,
                      baseline_len: int = 30) -> "float | None":
    """z-score of current weighted sentiment vs its recent baseline."""
    if current_score is None:
        return None
    vals = [float(v) for v in history if v is not None]
    sample = vals[-baseline_len:] if baseline_len else vals
    if len(sample) < 8:
        return None
    mean = sum(sample) / len(sample)
    var = sum((v - mean) ** 2 for v in sample) / len(sample)
    std = var ** 0.5
    if std <= 1e-9:
        return 0.0
    return (current_score - mean) / std


def score_from_counts(bullish: int, bearish: int, unlabeled: int = 0) -> "float | None":
    """Signed sentiment score in [-1, 1] from labeled counts; None when empty."""
    labeled = (bullish or 0) + (bearish or 0)
    if labeled <= 0:
        return None
    return round(((bullish or 0) - (bearish or 0)) / labeled, 4)


def _baseline_file(cache_dir, ticker) -> str:
    import os

    root = Path(cache_dir or "~/.tradingagents").expanduser()
    root.mkdir(parents=True, exist_ok=True)
    safe = ticker.replace(".", "_").upper()
    return str(root / f"sentiment_baseline_{safe}.jsonl")


def compute_social_scores(ticker: str, cache_dir: "str | None" = None,
                          limit: int = 30) -> "dict | None":
    """Deterministic score + surprise velocity from StockTwits counts.

    Persists a rolling score baseline per ticker so ``surprise_velocity`` can
    z-score today's sentiment vs its own history. Returns None on any failure
    (the caller degrades silently).
    """
    try:
        from tradingagents.dataflows.stocktwits import stocktwits_counts

        counts = stocktwits_counts(ticker, limit=limit)
        if counts is None:
            return None
        bull, bear, unlabeled, total = counts
        score = score_from_counts(bull, bear, unlabeled)
        if score is None:
            return None
        path = _baseline_file(cache_dir, ticker)
        history = []
        if Path(path).exists():
            for ln in Path(path).read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    try:
                        history.append(float(ln))
                    except ValueError:
                        pass
        velocity = surprise_velocity(score, history[-30:])
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{score}\n")
        return {
            "computed_score": score,
            "computed_velocity": velocity,
            "sample_size": total,
            "bullish": bull,
            "bearish": bear,
            "unlabeled": unlabeled,
        }
    except Exception:
        return None


def computed_sentiment_line(result: dict) -> str:
    """Compact deterministic line to append to the sentiment report."""
    if not result:
        return ""
    parts = [f"computed_score={result['computed_score']:+.2f}"]
    if result.get("computed_velocity") is not None:
        parts.append(f"velocity={result['computed_velocity']:+.2f}sigma")
    parts.append(f"n={result.get('sample_size', 0)}")
    return "**Computed Sentiment (deterministic):** " + "; ".join(parts)


__all__ = [
    "sentiment_velocity", "mention_volume", "consensus_overlap",
    "consensus_verdict", "blended_score", "decayed_weight",
    "weighted_sentiment", "surprise_velocity", "score_from_counts",
    "compute_social_scores", "computed_sentiment_line",
]