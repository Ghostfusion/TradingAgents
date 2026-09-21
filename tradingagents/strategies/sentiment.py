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
import math
import re
from datetime import date as _date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from tradingagents.strategies.news_relevance import is_official as _is_official


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


# Display-only crowd bands (TradingSim bull/bear survey convention). They never
# gate a decision: the survey source itself warns extremes persist for months.
_CROWD_BULL = 60.0
_CROWD_BEAR = 40.0


def crowd_ratio(bullish, bearish, neutrals: int = 0) -> dict | None:
    """Bull/bear ratio ``B/(B+BE)*100`` with display-only 40/60 bands.

    Neutrals are excluded from the denominator (the source's convention).
    ``B+BE == 0`` returns None - never a 50 fallback. Returns
    ``{"ratio", "net_share", "band", "basis"}`` (``basis`` names the source and
    the display-only caveat) or None when the ratio is undefined.
    """
    b = max(0, int(bullish or 0))
    be = max(0, int(bearish or 0))
    denom = b + be
    if denom <= 0:
        return None
    ratio = round(b / denom * 100.0, 4)
    if ratio >= _CROWD_BULL:
        band = "crowded-bullish"
    elif ratio <= _CROWD_BEAR:
        band = "crowded-bearish"
    else:
        band = "neutral"
    return {
        "ratio": ratio,
        "net_share": score_from_counts(b, be),
        "band": band,
        "basis": (
            "crowd ratio = bullish/(bullish+bearish)*100 from crowd counts "
            "(StockTwits/Reddit); neutrals excluded; bands >=60 crowded-bullish / "
            "<=40 crowded-bearish are display-only (not validated; the survey "
            "source warns extremes persist for months) and never a gate; "
            f"neutrals={max(0, int(neutrals or 0))} excluded from the denominator"
        ),
    }


def _weighted_modal_share(labels: list, weights: list) -> float | None:
    """Weighted share of the modal label bucket (generalises consensus_overlap)."""
    totals: dict = {}
    total = 0.0
    for label, w in zip(labels, weights, strict=False):
        totals[label] = totals.get(label, 0.0) + w
        total += w
    if total <= 0:
        return None
    return round(max(totals.values()) / total, 4)


def sentiment_dispersion(scores, weights=None, *, labels=None) -> dict | None:
    """Weighted population std of per-item polarity + modal agreement share.

    ``scores`` is a list of per-item polarity in [-1, 1] (None entries are
    dropped); ``weights`` defaults to equal weights. ``dispersion`` is
    ``sqrt(sum_i w_i (s_i - mean)^2 / sum_i w_i)``. When ``labels`` is given,
    ``agreement`` is the modal weight share - the weighted generalisation of
    ``consensus_overlap`` (equal weights reproduce it exactly). Returns
    ``{"dispersion", "agreement", "n", "basis"}`` or None when no scored item
    is present.
    """
    pairs: list = []
    if weights is None:
        for s in scores or []:
            if s is None:
                continue
            try:
                pairs.append((float(s), 1.0))
            except (TypeError, ValueError):
                continue
    else:
        for s, w in zip(scores or [], weights or [], strict=False):
            if s is None:
                continue
            try:
                pairs.append((float(s), float(w)))
            except (TypeError, ValueError):
                continue
    if not pairs:
        return None
    wsum = sum(w for _, w in pairs)
    if wsum <= 0:
        return None
    mean = sum(w * s for s, w in pairs) / wsum
    var = sum(w * (s - mean) ** 2 for s, w in pairs) / wsum
    agreement = None
    if labels:
        if weights is None:
            agreement = consensus_overlap(labels)
        else:
            kept = [(lbl, w) for lbl, w in zip(labels, weights, strict=False) if lbl is not None]
            if kept:
                agreement = _weighted_modal_share(
                    [lbl for lbl, _ in kept], [w for _, w in kept]
                )
    return {
        "dispersion": round(var**0.5, 4),
        "agreement": agreement,
        "n": len(pairs),
        "basis": (
            "weighted population std of per-item polarity (weights default "
            "equal); agreement = modal weight share (consensus_overlap semantics)"
        ),
    }


def _baseline_file(cache_dir, ticker) -> str:

    root = Path(cache_dir or "~/.tradingagents").expanduser()
    root.mkdir(parents=True, exist_ok=True)
    safe = ticker.replace(".", "_").upper()
    return str(root / f"sentiment_baseline_{safe}.jsonl")


def compute_social_scores(
    ticker: str, cache_dir: str | None = None, limit: int = 30, record: bool = True
) -> dict | None:
    """Deterministic score + surprise velocity from StockTwits counts.

    Persists a rolling score baseline per ticker so ``surprise_velocity`` can
    z-score today's sentiment vs its own history. Returns None on any failure
    (the caller degrades silently).

    ``record`` controls the APPEND to that baseline, and it is the fix for a
    double-write: this function has two callers in one run - the sentiment
    analyst's prefetch and ``get_sentiment_computed`` (bound to the market
    analyst) - and both used to append. So one run wrote today's score TWICE,
    and the second call's ``surprise_velocity`` was z-scored against a history
    that already contained today's value. The prefetch is the designated
    RECORDER (``record=True``); every other caller is a READER and passes
    ``record=False``, so the baseline advances exactly once per run.
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
        if record:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"{score}\n")
        crowd = crowd_ratio(bull, bear, neutrals=unlabeled)
        n_bull = max(0, int(bull or 0))
        n_bear = max(0, int(bear or 0))
        n_unl = max(0, int(unlabeled or 0))
        polarity_rows = [1.0] * n_bull + [-1.0] * n_bear + [0.0] * n_unl
        label_rows = ["bullish"] * n_bull + ["bearish"] * n_bear + ["neutral"] * n_unl
        dispersion = sentiment_dispersion(polarity_rows, labels=label_rows)
        return {
            "computed_score": score,
            "computed_velocity": velocity,
            "sample_size": total,
            "bullish": bull,
            "bearish": bear,
            "unlabeled": unlabeled,
            "crowd_ratio": crowd,
            "crowd_dispersion": dispersion,
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


def _bucket_day(dt_utc: datetime, cutoff_h: int, cutoff_m: int) -> str:
    """Bucket an aware-UTC article time to its (next-session) trading day.

    America/New_York wall clock: an article stamped at or after the cutoff rolls
    to the next calendar day (the close-time look-ahead guard shared by
    ``aggregate_daily_sentiment`` and ``aggregate_weighted_sentiment``).
    """
    ny = dt_utc + _ny_offset(dt_utc)  # UTC -> America/New_York wall time
    if (ny.hour, ny.minute) >= (cutoff_h, cutoff_m):
        return (ny.date() + timedelta(days=1)).isoformat()
    return ny.date().isoformat()


def _article_polarity(art: dict, ticker: str, fallback_overall: bool):
    """(score, relevance, used_overall) for one article; score None if absent.

    The per-ticker score (-1..1) is preferred; the overall score is the flagged
    fallback when the article does not mention the ticker.
    """
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
    return score, relevance, used_overall


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
    for art in articles:
        if not isinstance(art, dict):
            continue
        score, relevance, used_overall = _article_polarity(art, ticker, fallback_overall)
        if score is None or not -1.0 <= score <= 1.0:
            continue
        dt = _parse_article_dt(art.get("time_published"))
        if dt is None:
            continue
        day = _bucket_day(dt, cutoff_h, cutoff_m)
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


_WEIGHTED_NEUTRAL_EPS = 0.05


def _weighted_basis(half_life, official_boost, min_n, neutral_eps) -> str:
    if half_life and float(half_life) > 0:
        decay = f"half_life={float(half_life):g}d"
    else:
        decay = "decay=off (2^(-age/HL)=1.0)"
    return (
        "weighted = sum(w*s)/sum(w) with w = (relevance/100) * 2^(-age/HL) * "
        f"official_boost [{decay}; official_boost={float(official_boost):g}]; "
        "relevance is an unsigned proxy for confidence, NOT a model probability; "
        "unweighted is the published per-day mean; dedupe by normalised headline; "
        f"neutral_share uses eps={float(neutral_eps):g}; weighted withheld (n/a) "
        f"below min_n={int(min_n)}"
    )


def _normalise_headline(title) -> str | None:
    """Syndication key: lower-cased, punctuation-free, whitespace-collapsed."""
    text = str(title or "").strip().lower()
    if not text:
        return None
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text).split())


def _article_url(art: dict) -> str:
    return str(art.get("url") or art.get("source_url") or "")


def aggregate_weighted_sentiment(
    articles: list,
    ticker: str = "",
    *,
    window: int | None = None,
    half_life: float | None = None,
    official_boost: float = 1.0,
    min_n: int = 2,
    day_cutoff_time: str = "16:00",
    fallback_overall: bool = True,
    neutral_eps: float = _WEIGHTED_NEUTRAL_EPS,
) -> list[dict] | None:
    """Signed per-article feed -> per-day unweighted + weighted sentiment.

    Additive sibling of ``aggregate_daily_sentiment`` (whose output is
    unchanged). Per calendar day it emits the published unweighted mean
    (``unweighted``), the relevance-weighted generalisation (``weighted`` =
    ``sum(w*s)/sum(w)`` with ``w = (relevance/100) * 2^(-age/HL) *
    official_boost``), the article count (``n``), the neutral share
    (``|s| < neutral_eps``), the weighted population ``dispersion`` and a
    ``basis`` line. Syndicated duplicates are dropped by normalised headline
    before counting, and the close-time -> next-session bucketing is kept.
    ``weighted`` is None below ``min_n`` so a single-article day is never read
    as a consensus. Returns rows chronologically, or None when no article has a
    usable score. Equal weights (no relevance, ``official_boost=1.0``, decay
    off) make ``weighted`` identical to ``unweighted``.
    """
    if not articles:
        return None
    try:
        cutoff_h, cutoff_m = (int(x) for x in str(day_cutoff_time).split(":"))
    except (ValueError, TypeError):
        cutoff_h, cutoff_m = 16, 0
    seen: set = set()
    by_day: dict = {}
    for art in articles:
        if not isinstance(art, dict):
            continue
        score, relevance, _ = _article_polarity(art, ticker, fallback_overall)
        if score is None or not -1.0 <= score <= 1.0:
            continue
        dt = _parse_article_dt(art.get("time_published"))
        if dt is None:
            continue
        key = _normalise_headline(art.get("title"))
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        day = _bucket_day(dt, cutoff_h, cutoff_m)
        pub_day = (dt + _ny_offset(dt)).date()
        age_days = max(0, (_date.fromisoformat(day) - pub_day).days)
        by_day.setdefault(day, []).append(
            {
                "score": score,
                "relevance": relevance,
                "age_days": age_days,
                "official": _is_official(_article_url(art)),
            }
        )
    if not by_day:
        return None
    days = sorted(by_day)
    if window and int(window) > 0:
        last_day = _date.fromisoformat(days[-1])
        days = [d for d in days if (last_day - _date.fromisoformat(d)).days < int(window)]
        if not days:
            return None
    basis = _weighted_basis(half_life, official_boost, min_n, neutral_eps)
    out = []
    for day in days:
        items = by_day[day]
        scores = [it["score"] for it in items]
        n = len(scores)
        weights = []
        for it in items:
            w = float(it["relevance"]) / 100.0 if it["relevance"] is not None else 1.0
            if half_life and float(half_life) > 0:
                w *= 2.0 ** (-float(it["age_days"]) / float(half_life))
            if it["official"]:
                w *= float(official_boost)
            weights.append(w)
        wsum = sum(weights)
        weighted = None
        if n >= int(min_n) and wsum > 0:
            weighted = round(
                sum(w * s for w, s in zip(weights, scores, strict=True)) / wsum, 4
            )
        dispersion = sentiment_dispersion(scores, weights=weights)
        out.append(
            {
                "date": day,
                "unweighted": round(sum(scores) / n, 4),
                "weighted": weighted,
                "n": n,
                "neutral_share": round(
                    sum(1 for s in scores if abs(s) < float(neutral_eps)) / n, 4
                ),
                "dispersion": dispersion["dispersion"] if dispersion else None,
                "eps": float(neutral_eps),
                "basis": basis,
            }
        )
    return out


def weighted_rolling_sentiment(
    points: list,
    window: int = 10,
    *,
    exponential: bool = True,
    min_history: int = 30,
) -> dict | None:
    """Exponentially recency-weighted rolling sentiment beside the 7d SMA.

    Reuses ``daily_sentiment_sma`` for the calendar reindexing and close-time
    cutoff, so the unweighted 7d SMA path stays byte-identical and both ship in
    one row. Weights are ``exp(linspace(0, 1, K))`` normalised over the last
    ``window`` calendar days (most recent = 1); a missing day carries no score
    (never a zero fill) and so contributes no weight. Below ``min_history``
    scored days the weighted value is withheld (``unavailable``) with the
    observed history length. Returns ``{"rows", "weighted", "unweighted_sma",
    "window", "exponential", "min_history", "n_history", "sufficient_history",
    "basis"}``, or None when ``points`` is empty.
    """
    if not points:
        return None
    base_rows = daily_sentiment_sma(points, window=7)
    scored_days = len(
        {
            str(p["date"])
            for p in points
            if isinstance(p, dict) and p.get("date") and p.get("score") is not None
        }
    )
    K = max(1, int(window))
    min_h = max(0, int(min_history))
    sufficient = scored_days >= min_h
    if base_rows is None:
        return {
            "rows": [],
            "weighted": None,
            "unweighted_sma": None,
            "window": K,
            "exponential": bool(exponential),
            "min_history": min_h,
            "n_history": scored_days,
            "sufficient_history": False,
            "basis": (
                f"weighted rolling sentiment unavailable: observed history "
                f"{scored_days} scored days < min_history={min_h} "
                "(the production contract's 30-day warm-up)"
                if not sufficient
                else "weighted rolling sentiment unavailable: too few scored days "
                "for the calendar-reindexed 7d SMA base"
            ),
        }
    order = [r["date"] for r in base_rows]
    scores_by_date = {r["date"]: r["score"] for r in base_rows}
    rows = []
    for i, base in enumerate(base_rows):
        slots = list(range(max(0, i - K + 1), i + 1))
        m = len(slots)
        if exponential:
            wts = [math.exp(k / (m - 1)) if m > 1 else 1.0 for k in range(m)]
        else:
            wts = [1.0] * m
        num = 0.0
        den = 0.0
        for k, idx in enumerate(slots):
            s = scores_by_date.get(order[idx])
            if s is None:
                continue
            num += wts[k] * s
            den += wts[k]
        row = dict(base)
        row["weighted"] = round(num / den, 4) if den > 0 else None
        rows.append(row)
    if not sufficient:
        for row in rows:
            row["weighted"] = None
    if sufficient:
        basis = (
            "weighted = sum(w*s)/sum(w), w = exp(linspace(0,1,K)) normalised over "
            f"the last {K} calendar days (most recent = 1, exponential="
            f"{bool(exponential)}); missing days carry no score (never "
            "zero-filled); the unweighted 7d SMA ships beside it; "
            f"n_history={scored_days} scored days (min_history={min_h})"
        )
    else:
        basis = (
            f"weighted rolling sentiment unavailable: observed history {scored_days} "
            f"scored days < min_history={min_h} (the production contract's 30-day warm-up)"
        )
    return {
        "rows": rows,
        "weighted": rows[-1]["weighted"],
        "unweighted_sma": rows[-1]["sma_7d"],
        "window": K,
        "exponential": bool(exponential),
        "min_history": min_h,
        "n_history": scored_days,
        "sufficient_history": sufficient,
        "basis": basis,
    }


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
    "crowd_ratio",
    "sentiment_dispersion",
    "compute_social_scores",
    "computed_sentiment_line",
    "aggregate_daily_sentiment",
    "aggregate_weighted_sentiment",
    "daily_sentiment_sma",
    "weighted_rolling_sentiment",
]
