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

import contextlib
from datetime import date as _date
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def sentiment_velocity(sentiment_series: list, window: int = 5) -> float | None:
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
    return sum((xi - xm) * (yi - ym) for xi, yi in zip(x, sample, strict=True)) / den


def mention_volume(history: list, recent: int = 1) -> float | None:
    """Recent mentions vs historic per-day baseline (ratio, >=1 hot)."""
    if not history:
        return None
    base = max(
        1.0,
        float(sum(history[:-recent]) / len(history[:-recent])) if recent < len(history) else 1.0,
    )
    recent_sum = float(sum(history[-recent:]))
    return recent_sum / base


def consensus_overlap(verdicts: list, threshold: float = 0.5) -> float | None:
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
        weights = dict.fromkeys(names, 1.0)
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


def weighted_sentiment(messages: list) -> float | None:
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


def surprise_velocity(
    current_score: float | None, history: list, baseline_len: int = 30
) -> float | None:
    """z-score of current weighted sentiment vs its recent baseline."""
    if current_score is None:
        return None
    vals = [float(v) for v in history if v is not None]
    sample = vals[-baseline_len:] if baseline_len else vals
    if len(sample) < 8:
        return None
    mean = sum(sample) / len(sample)
    var = sum((v - mean) ** 2 for v in sample) / len(sample)
    std = var**0.5
    if std <= 1e-9:
        return 0.0
    return (current_score - mean) / std


def score_from_counts(bullish: int, bearish: int, unlabeled: int = 0) -> float | None:
    """Signed sentiment score in [-1, 1] from labeled counts; None when empty."""
    labeled = (bullish or 0) + (bearish or 0)
    if labeled <= 0:
        return None
    return round(((bullish or 0) - (bearish or 0)) / labeled, 4)


def _baseline_file(cache_dir, ticker) -> str:

    root = Path(cache_dir or "~/.tradingagents").expanduser()
    root.mkdir(parents=True, exist_ok=True)
    safe = ticker.replace(".", "_").upper()
    return str(root / f"sentiment_baseline_{safe}.jsonl")


def compute_social_scores(
    ticker: str, cache_dir: str | None = None, limit: int = 30
) -> dict | None:
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
                    with contextlib.suppress(ValueError):
                        history.append(float(ln))
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


# ---------------------------------------------------------------------------
# News-sentiment daily series (News_Sentiment.md §1)
# ---------------------------------------------------------------------------


def _parse_article_dt(raw: str) -> datetime | None:
    """Parse an article timestamp to an aware UTC datetime.

    Accepts Alpha Vantage ``YYYYMMDDTHHMMSS`` / ``...Z`` and ISO-8601 with an
    offset (EODHD / GDELT). Naive timestamps are treated as UTC.
    """
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%dT%H%M%SZ%z"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=ZoneInfo("UTC")) if dt.tzinfo is None else dt
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("UTC"))


def _ny_offset(dt_utc: datetime) -> timedelta:
    """America/New_York UTC offset: EST (-5) or EDT (-4) by the DST rule.

    DST: second Sunday of March 02:00 -> first Sunday of November 02:00.
    Pure-date rule so the series is deterministic and offline-testable.
    """
    y, m, d = dt_utc.year, dt_utc.month, dt_utc.day
    if m < 3 or m > 11:
        return timedelta(hours=-5)
    if m == 3:
        first = _date(y, 3, 1)
        second_sun = first + timedelta(days=(6 - first.weekday()) % 7 + 7)
        if d < second_sun.day:
            return timedelta(hours=-5)
        return timedelta(hours=-4)
    if m == 11:
        first = _date(y, 11, 1)
        first_sun = first + timedelta(days=(6 - first.weekday()) % 7)
        if d < first_sun.day:
            return timedelta(hours=-4)
        return timedelta(hours=-5)
    return timedelta(hours=-4)


def aggregate_daily_sentiment(
    articles: list,
    ticker: str = "",
    day_cutoff_time: str = "16:00",
    fallback_overall: bool = True,
) -> list[dict] | None:
    """Alpha Vantage NEWS_SENTIMENT feed -> chronological daily mean scores.

    Each article is expected in the AV feed shape: ``time_published``
    (``YYYYMMDDTHHMMSS`` UTC), ``ticker_sentiment`` (list of
    ``{"ticker", "ticker_sentiment_score", "relevance_score"}``) and
    ``overall_sentiment_score``. The per-ticker score (-1..1) is preferred;
    the overall score is used as a flagged fallback when the article does not
    mention the ticker (``fallback_overall``).

    Look-ahead guard: an article published after ``day_cutoff_time``
    (America/New_York) is bucketed to the NEXT calendar day, so a close-time
    signal never reads same-day post-close news. Returns
    ``[{"date", "score", "n", "relevance_mean", "used_overall"}]``
    chronologically, or None when fewer than two articles have a usable score.
    """
    if not articles:
        return None
    try:
        cutoff_h, cutoff_m = (int(x) for x in str(day_cutoff_time).split(":"))
    except (ValueError, TypeError):
        cutoff_h, cutoff_m = 16, 0
    by_day: dict[str, dict] = {}
    fb: dict[str, int] = {}
    for art in articles:
        if not isinstance(art, dict):
            continue
        score = None
        relevance = None
        used_overall = False
        ts = art.get("ticker_sentiment") or []
        if ticker:
            want = str(ticker).upper()
            for row in ts:
                if str(row.get("ticker", "")).upper() == want:
                    try:
                        score = float(row.get("ticker_sentiment_score"))
                    except (TypeError, ValueError):
                        score = None
                    try:
                        relevance = float(row.get("relevance_score"))
                    except (TypeError, ValueError):
                        relevance = None
                    break
            if score is None and fallback_overall:
                try:
                    score = float(art.get("overall_sentiment_score"))
                    used_overall = True
                except (TypeError, ValueError):
                    score = None
        else:
            try:
                score = float(art.get("overall_sentiment_score"))
                used_overall = True
            except (TypeError, ValueError):
                score = None
        if score is None or not -1.0 <= score <= 1.0:
            continue
        dt = _parse_article_dt(art.get("time_published"))
        if dt is None:
            continue
        ny = dt + _ny_offset(dt)  # UTC -> America/New_York wall time
        day = ny.date().isoformat()
        if (ny.hour, ny.minute) >= (cutoff_h, cutoff_m):
            day = (ny.date() + timedelta(days=1)).isoformat()
        entry = by_day.setdefault(day, {"scores": [], "rels": [], "overall": 0})
        entry["scores"].append(score)
        if relevance is not None:
            entry["rels"].append(relevance)
        if used_overall:
            entry["overall"] += 1
    if not by_day:
        return None
    out = []
    for day in sorted(by_day):
        e = by_day[day]
        out.append(
            {
                "date": day,
                "score": round(sum(e["scores"]) / len(e["scores"]), 4),
                "n": len(e["scores"]),
                "relevance_mean": (
                    round(sum(e["rels"]) / len(e["rels"]), 4) if e["rels"] else None
                ),
                "used_overall": e["overall"],
            }
        )
    return out


def daily_sentiment_sma(
    points: list, window: int = 7, min_score_days: int = 3
) -> list[dict] | None:
    """Calendar-reindexed daily sentiment + 7-day SMA + innovation.

    ``points`` is a chronological list of ``{"date": "YYYY-MM-DD",
    "score": float | None, "n": int}`` (a `aggregate_daily_sentiment` slice,
    or an EODHD ``/sentiments`` daily series with ``normalized`` centered to
    [-1, 1]). Missing calendar days are reindexed as ``score=None`` so the
    SMA spans real calendar days, not active news days.

    Returns one dict per calendar day in the range: ``{"date", "score",
    "sma_7d", "innovation", "n"}`` where ``sma_7d`` is the window-7 rolling
    mean (min_periods=1) and ``innovation = score_t - sma_7d_{t-1}`` (the raw
    daily sentiment shock). None when fewer than ``min_score_days`` days have
    a measured score.
    """
    if not points:
        return None
    rows: dict[str, dict] = {}
    for p in points:
        if not isinstance(p, dict) or not p.get("date"):
            continue
        try:
            score = None if p.get("score") is None else float(p["score"])
        except (TypeError, ValueError):
            score = None
        try:
            n = int(p.get("n") or 0)
        except (TypeError, ValueError):
            n = 0
        rows[str(p["date"])] = {"score": score, "n": n}
    try:
        day0 = _date.fromisoformat(min(rows))
        day1 = _date.fromisoformat(max(rows))
    except ValueError:
        return None
    if day1 < day0:
        day0, day1 = day1, day0
    scored = sum(1 for r in rows.values() if r["score"] is not None)
    if scored < min_score_days:
        return None

    order: list[str] = []
    cur = day0
    while cur <= day1:
        order.append(cur.isoformat())
        cur += timedelta(days=1)

    sma_vals: list[float | None] = []
    acc = 0.0
    count = 0
    for i, day in enumerate(order):
        score = rows.get(day, {}).get("score")
        if score is not None:
            acc += score
            count += 1
        window_low = max(0, i - window + 1)
        if window_low > 0:
            old_day = order[window_low - 1]
            old = rows.get(old_day, {}).get("score")
            if old is not None:
                acc -= old
                count -= 1
        sma_vals.append(round(acc / count, 4) if count else None)

    out = []
    for i, day in enumerate(order):
        score = rows.get(day, {}).get("score")
        prev_sma = sma_vals[i - 1] if i > 0 else None
        innovation = None
        if score is not None and prev_sma is not None:
            innovation = round(score - prev_sma, 4)
        out.append(
            {
                "date": day,
                "score": score,
                "sma_7d": sma_vals[i],
                "innovation": innovation,
                "n": rows.get(day, {}).get("n", 0),
            }
        )
    return out


__all__ = [
    "sentiment_velocity",
    "mention_volume",
    "consensus_overlap",
    "consensus_verdict",
    "blended_score",
    "decayed_weight",
    "weighted_sentiment",
    "surprise_velocity",
    "score_from_counts",
    "compute_social_scores",
    "computed_sentiment_line",
    "aggregate_daily_sentiment",
    "daily_sentiment_sma",
]
