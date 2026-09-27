"""Phase 6 - alternative-data velocity, dynamics and positioning.

- ``sentiment_velocity(series)``: the OLS slope of sentiment over the recent
  window (per day) - the canonical direction and rate (owner Q4). It is never
  replaced by a second 20-day delta producer.
- ``sentiment_dynamics(series)``: the additions beside that slope - the
  three-point second difference, the AR(1) ``phi`` and its half-life, the
  mean-reversion speed and the lag-1 persistence (library §65/§75/§122-§125).
- ``mention_volume(series, recent)``: the ratio of recent mentions to the
  historic per-day baseline - the ATTENTION leg, never summed with tone.
- ``crowd_ratio(bullish, bearish, neutrals)``: the bull/bear ratio. Its band is
  a percentile over the name's OWN history once enough history exists, with the
  display-only 40/60 constants as the documented fallback.
- ``aggregate_daily_sentiment`` / ``aggregate_weighted_sentiment`` /
  ``daily_sentiment_sma`` / ``weighted_rolling_sentiment``: the per-day series
  the score engines read.

The three dead seams the SentimentScore review named (``weighted_sentiment``,
``blended_score``, ``consensus_verdict``) were deleted rather than kept: no
production path can reach any of them (the recency/credibility blend is
``aggregate_weighted_sentiment``'s job, the seed consensus has no multi-seed
run, and the verdict blend has no caller).
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


#: The floor below which ``sentiment_dynamics`` refuses to measure. Three points
#: are the minimum for the second difference; five is the smallest sample on
#: which an AR(1) regression and a lag-1 correlation are not noise. Declared
#: here so the refusal is a stated policy rather than a silent one.
SENTIMENT_DYNAMICS_MIN_POINTS = 5


def _ols_slope(xs: list[float], ys: list[float]) -> float | None:
    """OLS slope of ``ys`` on ``xs``, or None when it is undefined."""
    n = len(xs)
    if n < 2:
        return None
    xm = sum(xs) / n
    ym = sum(ys) / n
    den = sum((x - xm) ** 2 for x in xs)
    if den <= 1e-12:
        return None
    return sum((x - xm) * (y - ym) for x, y in zip(xs, ys, strict=True)) / den


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation of ``xs`` and ``ys``, or None when either is flat."""
    n = len(xs)
    if n < 2:
        return None
    xm = sum(xs) / n
    ym = sum(ys) / n
    dx = sum((x - xm) ** 2 for x in xs)
    dy = sum((y - ym) ** 2 for y in ys)
    if dx <= 1e-12 or dy <= 1e-12:
        return None
    return sum((x - xm) * (y - ym) for x, y in zip(xs, ys, strict=True)) / (dx * dy) ** 0.5


def sentiment_dynamics(
    series: list, *, min_points: int = SENTIMENT_DYNAMICS_MIN_POINTS
) -> dict | None:
    """The dynamics beyond the slope, over one sentiment series (SENT-8).

    ``series`` is the chronological daily sentiment the engine already holds
    (the ``score`` column of ``daily_sentiment_sma``); ``None`` entries are
    dropped, and a non-finite value is dropped too. Owner Q4 fixes
    ``sentiment_velocity``'s OLS slope as the canonical direction, so these are
    ADDITIONS beside it, never a replacement.

    Returns ``{"second_difference", "ar1_phi", "half_life",
    "mean_reversion_speed", "persistence", "n", "min_points", "basis"}``, or
    ``None`` below ``min_points`` usable observations (the stated floor).

    The four quantities, each with its library section and estimator:

    - ``second_difference`` = ``S_t - 2 S_{t-1} + S_{t-2}``, the three-point
      second difference (§65), the discrete acceleration of sentiment.
    - ``ar1_phi`` = the OLS slope of ``S_t`` on ``S_{t-1}`` in
      ``S_t = c + phi S_{t-1}`` (§75, §122). ``None`` when the lagged series is
      flat (no slope is defined).
    - ``half_life`` = ``-ln2 / ln|phi|`` (§75, §124), in the same per-period
      unit as the series. ``None`` unless ``0 < |phi| < 1`` - a phi of 1 is a
      random walk (no decay) and ``|phi| > 1`` is explosive, so neither has a
      half-life.
    - ``mean_reversion_speed`` = the OLS slope ``kappa`` of ``dS_t`` on
      ``(mu - S_{t-1})`` in ``dS_t = kappa (mu - S_{t-1}) + e`` (§123), with
      ``mu`` the sample mean. Positive means sentiment pulls back toward its
      mean.
    - ``persistence`` = the lag-1 autocorrelation ``Corr(S_t, S_{t-1})`` (§125).
      This is the correlation form, deliberately NOT a second copy of the AR(1)
      slope ``ar1_phi`` (§122's "persistence coefficient" is that same phi):
      one quantity has one producer (master rule 15).
    """
    vals: list[float] = []
    for v in series or []:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            vals.append(f)
    floor = max(3, int(min_points))
    if len(vals) < floor:
        return None
    n = len(vals)
    lag_x, lag_y = vals[:-1], vals[1:]
    second = vals[-1] - 2.0 * vals[-2] + vals[-3]
    phi = _ols_slope(lag_x, lag_y)
    half_life = None
    if phi is not None and 1e-12 < abs(phi) < 1.0:
        half_life = -math.log(2.0) / math.log(abs(phi))
    mu = sum(vals) / n
    mr = _ols_slope(
        [mu - v for v in lag_x],
        [lag_y[i] - lag_x[i] for i in range(len(lag_x))],
    )
    persistence = _pearson(lag_x, lag_y)
    return {
        "second_difference": round(second, 6),
        "ar1_phi": round(phi, 6) if phi is not None else None,
        "half_life": round(half_life, 4) if half_life is not None else None,
        "mean_reversion_speed": round(mr, 6) if mr is not None else None,
        "persistence": round(persistence, 6) if persistence is not None else None,
        "n": n,
        "min_points": floor,
        "basis": (
            "second_difference = S_t-2S_{t-1}+S_{t-2} (library §65); "
            "ar1_phi = OLS slope of S_t on S_{t-1} (§75/§122); "
            "half_life = -ln2/ln|phi| (§75/§124, requires 0<|phi|<1); "
            "mean_reversion_speed = OLS slope of dS_t on (mu-S_{t-1}) (§123); "
            "persistence = lag-1 autocorrelation Corr(S_t,S_{t-1}) (§125), not a "
            "second copy of ar1_phi; the canonical direction stays "
            "sentiment_velocity's OLS slope (owner Q4); "
            f"n={n} usable observation(s), floor {floor}"
        ),
    }


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


def decayed_weight(age_days: float, half_life: float = 7.0) -> float:
    """Exponential freshness weight: 0.5 after one half-life."""
    if age_days < 0:
        return 0.0
    return 0.5 ** (age_days / half_life)


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
# They are now the DOCUMENTED FALLBACK: when the name has enough of its own
# crowd-ratio history the band is a percentile of that history (owner Q5).
_CROWD_BULL = 60.0
_CROWD_BEAR = 40.0

#: Percentile thresholds are CONFIGURATION, not hard-coded methodology (owner
#: Q5): the 20/80 split is the default and is overridable per call.
_CROWD_PCT_LOW = 20.0
_CROWD_PCT_HIGH = 80.0

#: Below this many prior crowd ratios there is no distribution to rank against,
#: so the 40/60 constants are used instead - with the method named in the basis.
_CROWD_MIN_HISTORY = 20


def crowd_band_percentile(
    ratio,
    history,
    *,
    low_pct: float = _CROWD_PCT_LOW,
    high_pct: float = _CROWD_PCT_HIGH,
    min_history: int = _CROWD_MIN_HISTORY,
) -> dict:
    """Rank a crowd ratio inside the name's OWN history, or fall back to 40/60.

    ``ratio`` is today's ``crowd_ratio`` value (0-100); ``history`` is the
    name's prior ratios, oldest -> newest (the per-name baseline the store at
    ``_crowd_baseline_file`` accumulates). ``percentile`` is the share of the
    history at or below ``ratio`` (0-100).

    The band is ``crowded-bullish`` at or above ``high_pct``, ``crowded-bearish``
    at or below ``low_pct``, ``neutral`` between them. **Below ``min_history``
    prior ratios the percentile is not measurable**, so the band falls back to
    the display-only 40/60 constants and the basis says which method was used:
    a percentile over three points would be a fabricated rank, and the constants
    are the documented fallback (owner Q5), not a silent substitute.

    Returns ``{"ratio", "percentile", "band", "method", "n_history",
    "thresholds", "basis"}``. ``method`` is ``"percentile"``,
    ``"constant-fallback"`` (too little history), or ``"unavailable"`` (no
    ratio to band). ``thresholds`` carries the configuration actually used.
    """
    thresholds = {
        "low_pct": float(low_pct),
        "high_pct": float(high_pct),
        "min_history": int(min_history),
    }
    hist: list[float] = []
    for v in history or []:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            hist.append(f)
    if ratio is None:
        return {
            "ratio": None,
            "percentile": None,
            "band": None,
            "method": "unavailable",
            "n_history": len(hist),
            "thresholds": thresholds,
            "basis": "no crowd ratio to band (the producer returned None)",
        }
    r = float(ratio)
    if len(hist) < thresholds["min_history"]:
        band = (
            "crowded-bullish" if r >= _CROWD_BULL
            else "crowded-bearish" if r <= _CROWD_BEAR
            else "neutral"
        )
        return {
            "ratio": r,
            "percentile": None,
            "band": band,
            "method": "constant-fallback",
            "n_history": len(hist),
            "thresholds": thresholds,
            "basis": (
                f"{len(hist)} prior ratio(s) held, {thresholds['min_history']} "
                "needed for a percentile of this name's own history; fell back to "
                "the display-only 40/60 constants (never a gate)"
            ),
        }
    pct = round(sum(1 for h in hist if h <= r) / len(hist) * 100.0, 4)
    band = (
        "crowded-bullish" if pct >= thresholds["high_pct"]
        else "crowded-bearish" if pct <= thresholds["low_pct"]
        else "neutral"
    )
    return {
        "ratio": r,
        "percentile": pct,
        "band": band,
        "method": "percentile",
        "n_history": len(hist),
        "thresholds": thresholds,
        "basis": (
            f"percentile of this name's own crowd-ratio history: {pct:.1f} of "
            f"{len(hist)} prior ratio(s); bands <= {thresholds['low_pct']:g} "
            f"crowded-bearish / >= {thresholds['high_pct']:g} crowded-bullish "
            "(thresholds are configuration, owner Q5; never a gate)"
        ),
    }


def crowd_ratio(
    bullish,
    bearish,
    neutrals: int = 0,
    *,
    history=None,
    low_pct: float = _CROWD_PCT_LOW,
    high_pct: float = _CROWD_PCT_HIGH,
    min_history: int = _CROWD_MIN_HISTORY,
) -> dict | None:
    """Bull/bear ratio ``B/(B+BE)*100`` with percentile-or-fallback bands.

    Neutrals are excluded from the denominator (the source's convention).
    ``B+BE == 0`` returns None - never a 50 fallback.

    ``history`` is the name's own prior crowd ratios (oldest -> newest). When it
    holds at least ``min_history`` values the band is a **percentile of that
    history** (``crowd_band_percentile``); otherwise the display-only 40/60
    constants are the documented fallback and ``band_method`` says so. The
    percentile thresholds are configuration (owner Q5), never hard-coded
    methodology.

    Returns ``{"ratio", "net_share", "band", "percentile", "band_method",
    "basis"}`` (``basis`` names the source and the display-only caveat) or None
    when the ratio is undefined.
    """
    b = max(0, int(bullish or 0))
    be = max(0, int(bearish or 0))
    denom = b + be
    if denom <= 0:
        return None
    ratio = round(b / denom * 100.0, 4)
    banded = crowd_band_percentile(
        ratio, history, low_pct=low_pct, high_pct=high_pct, min_history=min_history
    )
    return {
        "ratio": ratio,
        "net_share": score_from_counts(b, be),
        "band": banded["band"],
        "percentile": banded["percentile"],
        "band_method": banded["method"],
        "basis": (
            "crowd ratio = bullish/(bullish+bearish)*100 from crowd counts "
            "(StockTwits/Reddit); neutrals excluded; "
            + banded["basis"]
            + "; the bands are display-only (not validated; the survey source "
            "warns extremes persist for months) and never a gate; "
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


def _crowd_baseline_file(cache_dir, ticker) -> str:
    """Per-name crowd-RATIO history, the distribution the percentile ranks in.

    A separate file from ``_baseline_file``: that one holds the signed sentiment
    score ``surprise_velocity`` z-scores, while the crowd percentile needs the
    0-100 bull/bear ratio series (a different unit and a different question).
    """
    root = Path(cache_dir or "~/.tradingagents").expanduser()
    root.mkdir(parents=True, exist_ok=True)
    safe = ticker.replace(".", "_").upper()
    return str(root / f"crowd_baseline_{safe}.jsonl")


def _read_float_history(path) -> list[float]:
    """One float per non-blank line; unparseable lines are skipped, not zeroed."""
    out: list[float] = []
    if Path(path).exists():
        for ln in Path(path).read_text(encoding="utf-8").splitlines():
            if ln.strip():
                with contextlib.suppress(ValueError):
                    out.append(float(ln))
    return out


def compute_social_scores(
    ticker: str, cache_dir: str | None = None, limit: int = 30, record: bool = True
) -> dict | None:
    """Deterministic score + surprise velocity from StockTwits counts.

    Persists a rolling score baseline per ticker so ``surprise_velocity`` can
    z-score today's sentiment vs its own history, and a rolling crowd-RATIO
    baseline so ``crowd_ratio``'s band can be a percentile of the name's own
    history (owner Q5) instead of only the 40/60 constants. Returns None on any
    failure (the caller degrades silently).

    ``record`` controls the APPEND to that baseline, and it is the fix for a
    double-write: this function has two callers in one run - the sentiment
    analyst's prefetch and ``get_sentiment_computed`` (bound to the market
    analyst) - and both used to append. So one run wrote today's score TWICE,
    and the second call's ``surprise_velocity`` was z-scored against a history
    that already contained today's value. The prefetch is the designated
    RECORDER (``record=True``); every other caller is a READER and passes
    ``record=False``, so the baseline advances exactly once per run. The crowd
    ratio follows the same rule: it is read before today's value is appended, so
    today never ranks inside its own baseline.
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
        history = _read_float_history(path)
        velocity = surprise_velocity(score, history[-30:])
        if record:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"{score}\n")
        crowd_path = _crowd_baseline_file(cache_dir, ticker)
        crowd_history = _read_float_history(crowd_path)
        crowd = crowd_ratio(bull, bear, neutrals=unlabeled, history=crowd_history)
        if record and crowd is not None and crowd.get("ratio") is not None:
            with open(crowd_path, "a", encoding="utf-8") as fh:
                fh.write(f"{crowd['ratio']}\n")
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
    (``|s| < neutral_eps``), the positive share (``bull_share``: the fraction of
    the day's accepted, scored articles with ``s > +neutral_eps`` - strictly
    above the SAME epsilon the row reports, so "positive" means the same thing
    here as "not neutral" does, and ``n`` is the denominator), the weighted
    population ``dispersion`` and a ``basis`` line. Syndicated duplicates are
    dropped by normalised headline before counting, and the close-time ->
    next-session bucketing is kept. ``weighted`` is None below ``min_n`` so a
    single-article day is never read as a consensus; ``bull_share`` is None -
    never 0 - when the day has no accepted scored article. Returns rows
    chronologically, or None when no article has a usable score. Equal weights
    (no relevance, ``official_boost=1.0``, decay off) make ``weighted``
    identical to ``unweighted``.
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
                # `decayed_weight` is the ONE producer of the freshness weight;
                # the inline `2.0 ** (-age / half_life)` copy that stood here was
                # a second one. It agreed ONLY because `age_days` is clamped to
                # >= 0 above, so it inherited the producer's `age_days < 0 -> 0.0`
                # guard by accident: drop that clamp and the copy weights a
                # future-dated article ABOVE 1.0 while the producer answers 0.0
                # (master rule 15: one quantity, one producer).
                w *= decayed_weight(float(it["age_days"]), float(half_life))
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
                "bull_share": (
                    round(sum(1 for s in scores if s > float(neutral_eps)) / n, 4)
                    if n
                    else None
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
    "sentiment_dynamics",
    "SENTIMENT_DYNAMICS_MIN_POINTS",
    "mention_volume",
    "consensus_overlap",
    "decayed_weight",
    "surprise_velocity",
    "score_from_counts",
    "crowd_ratio",
    "crowd_band_percentile",
    "sentiment_dispersion",
    "compute_social_scores",
    "computed_sentiment_line",
    "aggregate_daily_sentiment",
    "aggregate_weighted_sentiment",
    "daily_sentiment_sma",
    "weighted_rolling_sentiment",
]
