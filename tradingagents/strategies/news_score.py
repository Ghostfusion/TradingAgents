"""`NewsScore` (WP-6) - what new information arrived, and how material is it?

The owner's nine categories (`docs/scores/NewsScore.md` §0.1) as this engine can
honestly build them today: relevance & materiality 20, novelty 15, fundamental
impact 20, earnings & guidance 15, corporate events 10, regulatory & legal 5,
analyst & rating 5, macro & industry 5, persistence 5. **Five of the eleven
components below are absent on the default path** and print `NA` **with the
reason**, never 0: three have no producer anywhere (`fundamental_impact`,
`regulatory_legal`, `industry_shock`), `guidance_change` has one behind a
default-off vendor gate, and `materiality` is caller-supplied (owner Q6).

The rules this module exists to hold:

1. **The boundary is enforced by naming** (`NewsScore.md` §0.3). This engine reads
   the **news pipeline** (`news_relevance`, `events`, `text_factors`, SEC form
   typing, the analyst revision index). It imports **no `sentiment.py`
   aggregation** - where the two engines share a source (the article set) they
   must not share a *number*.
2. **Relevance is not materiality** (`NewsScore.md` §0.2). They are two separate,
   independent components; relevance alone cannot raise the composite, and
   materiality is never inferred from it.
3. **Materiality is caller-supplied** (owner decision Q6): `EventScore` owns the
   expected-move / materiality number, so this engine **consumes** it as an input
   argument rather than building a second estimate. This module imports no event
   code.
4. **Novelty has a recipe and a sign** (`NewsScore.md` §0.4): the first-seen
   share of the article set within the window, so a repeated headline scores
   lower than a first-seen one (stale news reverses).
5. **`NA` is not `0`** (master rule 1): an absent component leaves the
   denominator, the composite reports its coverage, and nothing is substituted
   with a neutral 50 or a punitive 0.
6. **Nothing here sizes or gates.** No `risk/sizing.py`, no gate, no
   `decision_guardrail.SCORE_BANDS`; this engine's bands are its own advisory
   labels.
7. **The declared tables are policy, not measurement.** ``RAMPS``,
   ``NEWS_BANDS``, ``FORM_EVENT_SCORES`` and ``GUIDANCE_RAMP`` are declared
   edges the engine carries (like every other engine's ramp); each is printed
   beside the number and none is presented as a fitted estimate. `FORM_EVENT_SCORES`
   in particular is the form->event-class mapping the ``corporate_events``
   declaration used to cite without one existing (`D-2`).

One pure function over a flat ``{component: raw value}`` dict - every value is
produced elsewhere and assembled by the caller/leaf. The producers this module
owns are pure functions over the raw series/rows the caller already holds:
``news_novelty`` (headlines), ``news_volume_acceleration`` and
``news_persistence`` (the per-day count/sentiment rows ``daily_sentiment_sma``
returns), ``news_confidence`` (a sample size), ``corporate_events_score`` (the
form types a filings read returned) and ``guidance_change_score`` (the guidance
revision rows).
"""

from __future__ import annotations

import math
from typing import NamedTuple

from .score_engine import align, band_label, combine, coverage_floor

# --- The owner's weights (NewsScore.md §0.1) ------------------------------- #
#
# The two partial categories are split into their present leg and their absent
# leg, so the absent leg carries weight and lowers coverage rather than hiding
# inside a present row: relevance/materiality 10/10, earnings/guidance 10/5.

COMPONENT_WEIGHTS: dict[str, float] = {
    # relevance & materiality (20)
    "relevance": 10.0,
    "materiality": 10.0,
    # novelty (15)
    "novelty": 15.0,
    # fundamental impact (20)
    "fundamental_impact": 20.0,
    # earnings & guidance (15)
    "earnings_surprise": 10.0,
    "guidance_change": 5.0,
    # corporate events (10)
    "corporate_events": 10.0,
    # regulatory & legal (5)
    "regulatory_legal": 5.0,
    # analyst & rating (5)
    "analyst_revision": 5.0,
    # macro & industry (5)
    "industry_shock": 5.0,
    # persistence (5)
    "persistence": 5.0,
}

COMPONENT_ORDER: tuple[str, ...] = tuple(COMPONENT_WEIGHTS)

#: The five components with no producer on this path - each prints `NA` with the
#: reason below. `materiality` is the caller-supplied one (owner Q6): absent until
#: the caller passes EventScore's number.
ABSENT_COMPONENTS: tuple[str, ...] = (
    "materiality",
    "fundamental_impact",
    "guidance_change",
    "regulatory_legal",
    "industry_shock",
)

ABSENT_REASONS: dict[str, str] = {
    "materiality": (
        "EventScore owns the materiality / expected-move number (owner Q6): "
        "analysis_tools._news_components supplies it from the catalyst snapshot's "
        "`implied_move` - the same figure the event engine reads, never a second "
        "estimate; NA when that snapshot carries no implied move, and NEVER "
        "approximated by relevance"
    ),
    "fundamental_impact": (
        "no revenue/margin-impact producer exists; the honest answer is NA"
    ),
    "guidance_change": (
        "the guidance source EXISTS but is behind its default-off gate: "
        "benzinga_tools.get_guidance_revisions (toolsets.py:411; "
        "enable_benzinga_surface off by default) is consumed by "
        "news_score.guidance_change_score, which the news leaf now calls - so the "
        "component is NA either because that gate is off (its default) or because "
        "the read carried no differencable row (a forward-only read cannot show a "
        "change); never fake it from the EPS estimate"
    ),
    "regulatory_legal": (
        "no regulatory-action classifier; only an unscaled, undirected litigious "
        "word count exists, so the category is withheld rather than scored"
    ),
    "industry_shock": (
        "no per-name industry-shock producer; market/sector breadth is a "
        "market-level read, not an industry shock"
    ),
}

# Ramps: ``(lo, hi)`` mapped 0 -> 100 (inverted for ``lower_better``). Every edge
# is this engine's declared policy, printed in the basis and measured later.
RAMPS: dict[str, tuple[float, float]] = {
    "relevance": (20.0, 80.0),          # news_relevance 0-100
    "materiality": (0.01, 0.10),        # |expected/implied move| fraction
    "novelty": (0.0, 1.0),              # first-seen share
    "fundamental_impact": (0.0, 1.0),   # (no producer)
    "earnings_surprise": (-0.05, 0.05),  # signed ratio (actual-estimate)/|estimate|
    "guidance_change": (-0.05, 0.05),   # (gate-off producer: guidance_change_score)
    "corporate_events": (0.0, 100.0),   # FORM_EVENT_SCORES form->event-class score
    "regulatory_legal": (0.0, 0.05),    # (no producer)
    "analyst_revision": (-0.5, 0.5),    # weighted up/down ratio
    "industry_shock": (-0.10, 0.10),    # sector-relative move (no producer)
    "persistence": (0.5, 3.0),          # attention ratio; neglected-firm sign (Q9)
}


class Component(NamedTuple):
    """One component: its owner category, direction, producer, note."""

    name: str
    category: str
    direction: str
    producer: str
    note: str = ""


def _c(name, category, direction, producer, note=""):
    return Component(name, category, direction, producer, note)


COMPONENTS: dict[str, Component] = {
    c.name: c
    for c in (
        _c("relevance", "relevance_materiality", "higher_better",
           "news_relevance.score_news_article:56",
           "0-100; the article set is the source shared with SentimentScore, the "
           "number is not"),
        _c("materiality", "relevance_materiality", "higher_better",
           "caller-supplied (EventScore, owner Q6)",
           "separate and independent from relevance; never inferred from it"),
        _c("novelty", "novelty", "higher_better", "news_score.news_novelty (this module)",
           "first-seen share of the window; a repeat scores lower"),
        _c("fundamental_impact", "fundamental_impact", "higher_better", None,
           "needs an estimate history the engine does not hold"),
        _c("earnings_surprise", "earnings_guidance", "higher_better",
           "events.surprise_score:17",
           "surfaced by catalyst.last_earnings_surprise:70"),
        _c("guidance_change", "earnings_guidance", "higher_better",
           "news_score.guidance_change_score (this module) over the rows "
           "benzinga_tools.get_guidance_revisions returns; the gate "
           "(enable_benzinga_surface) is off by default, so the component stays "
           "NA with that reason",
           "raised guidance midpoint scores above 50, a cut below (GUIDANCE_RAMP); "
           "never a neutral 50 when the gate is off"),
        _c("corporate_events", "corporate_events", "higher_better",
           "news_score.corporate_events_score (this module) over the declared "
           "FORM_EVENT_SCORES form->event-class table; the form vocabulary is "
           "sec_edgar._FORM_LABELS:39",
           "a DECLARED mapping, unvalidated like RAMPS; an unknown form is "
           "ignored, never defaulted to a neutral 50"),
        _c("regulatory_legal", "regulatory_legal", "lower_better", None,
           "text_factors.lm_tone:121 gives a litigious count only; no classifier"),
        _c("analyst_revision", "analyst_rating", "higher_better",
           "analyst_revisions.revision_ratio:79",
           "the binding moves to the news surface (Q4)"),
        _c("industry_shock", "macro_industry", "higher_better", None, None),
        _c("persistence", "persistence", "lower_better",
           "sentiment.mention_volume:43 (the level ratio - the WIRED half)",
           "neglected-firm sign (plan §13 Q9): lower abnormal coverage is positive. "
           "No unwired half is cited: `sentiment.decayed_weight` has no call site on "
           "this path (D-9, fixed 2026-09-27), and the library's own persistence "
           "quantity (`news_score.news_persistence`: positive-period share and a "
           "multi-lambda decay) is a DIFFERENT measure with the opposite direction, "
           "so it is not this component's producer either"),
    )
}

# --- The nine owner categories (NewsScore.md §0.1) ------------------------- #
#
# `COMPONENT_WEIGHTS` splits the two partial categories so the absent leg carries
# weight; the CATEGORY weight is the owner's unsplit total. `news_score()` returns
# one block per category in the same shape `sentiment_score()` uses, so the two
# renderers that read `categories` - `analysis_tools._render_news_score:6804` and
# `reporting._run_card_news_score:1630` - can print the breakdown (defect D-1:
# the key did not exist, so both printed an empty section).

NEWS_CATEGORY_ORDER: tuple[str, ...] = tuple(
    dict.fromkeys(c.category for c in COMPONENTS.values())
)

NEWS_CATEGORIES: dict[str, tuple[str, ...]] = {
    cat: tuple(name for name in COMPONENT_ORDER if COMPONENTS[name].category == cat)
    for cat in NEWS_CATEGORY_ORDER
}

NEWS_CATEGORY_WEIGHTS: dict[str, float] = {
    cat: sum(COMPONENT_WEIGHTS[name] for name in names)
    for cat, names in NEWS_CATEGORIES.items()
}

#: A category scores from one of its own components. The two two-component
#: categories (relevance/materiality, earnings/guidance) are why this is 1: one
#: measured leg is a category read, and the absent leg still lowers its coverage.
NEWS_CATEGORY_MIN_COVERAGE = 1


def _category_score(
    category: str, aligned: dict, *, min_coverage=NEWS_CATEGORY_MIN_COVERAGE
) -> dict:
    """One owner category's 0-100 over its own components, or withheld with a reason.

    Same key shape as ``sentiment_score.category_score`` - ``score``, ``coverage``,
    ``floor``, ``withheld``, ``band``, ``weight``, ``category``, ``raw_directions``
    - so both renderers print the news rows the same way. One difference: the news
    engine carries a per-component weight vector, so a category's components are
    combined with their owner weights (SentimentScore's categories have no
    per-component weights and use equal ones). An absent component leaves the
    category's denominator, never a 0, and a category below its floor carries the
    ``withheld`` reason.
    """
    if category not in NEWS_CATEGORIES:
        raise KeyError(
            f"unknown category {category!r}; known: {list(NEWS_CATEGORY_ORDER)}"
        )
    names = NEWS_CATEGORIES[category]
    res = combine(
        {name: aligned.get(name) for name in names},
        weights={name: COMPONENT_WEIGHTS[name] for name in names},
        min_coverage=min(coverage_floor(min_coverage, len(names)), len(names)),
    )
    res["category"] = category
    res["weight"] = NEWS_CATEGORY_WEIGHTS[category]
    res["band"] = band_label(res.get("score"), NEWS_BANDS)
    res["raw_directions"] = {name: COMPONENTS[name].direction for name in names}
    return res


# This engine's own advisory bands - never `decision_guardrail.SCORE_BANDS`.
NEWS_BANDS: tuple = (
    (80.0, "high-information"),
    (65.0, "informative"),
    (50.0, "mixed"),
    (35.0, "quiet"),
    (20.0, "stale"),
    (0.0, "no-signal"),
)

STATUS_ADVISORY = "ADVISORY"

#: The smallest composite: two of eleven present components (10 + 10 weight).
COMPOSITE_MIN_COVERAGE = 2

#: Printed beside the score: what each component's number is measured in.
SCALE_CONVENTION = (
    "relevance 0-100; novelty 0-1 (first-seen share); materiality |expected/implied "
    "move| fraction (caller-supplied); earnings surprise a signed ratio; corporate "
    "event typing 0-100 (FORM_EVENT_SCORES); analyst revision -1..1; persistence a "
    "mention ratio; guidance change a signed relative midpoint change"
)


# --- Novelty (NewsScore.md §0.4 / §5.1 item 1) ----------------------------- #


def _normalise_headline(title) -> str | None:
    """Syndication key: lower-cased, punctuation-free, whitespace-collapsed.

    A local copy of the normaliser the sentiment pipeline uses for its syndication
    dedupe. It is duplicated rather than imported: `NewsScore.md` §0.3 forbids the
    news path from importing a `sentiment.py` function, and a private key helper
    copied here keeps the boundary visible rather than crossing it.
    """
    text = str(title or "").strip().lower()
    if not text:
        return None
    out = []
    for ch in text:
        out.append(ch if (ch.isalnum() or ch.isspace()) else " ")
    return " ".join("".join(out).split()) or None


def news_novelty(articles, *, window: int | None = None) -> dict:
    """First-seen share of an article set - the novelty recipe (`NewsScore.md`
    §0.4 point 1): the similarity of a story to the stories already seen about
    the firm, in the count form the engine already holds.

    ``articles`` is a list of dicts (``title``/``headline``, optional
    ``timestamp``/``time_published`` ISO strings) or of plain headline strings.
    When ``window`` is given and articles carry timestamps, only articles within
    ``window`` days of the latest timestamp count (a repeated headline *within the
    window* is a repeat; older ones are out of scope).

    ``novelty`` is ``first_seen / n`` - a repeated headline lowers it. Returns
    ``None`` for the value when there is nothing to score; never 0 for a gap.
    """
    rows = []
    for art in articles or []:
        if isinstance(art, dict):
            title = art.get("title") or art.get("headline")
            ts = art.get("timestamp") or art.get("time_published")
        else:
            title, ts = art, None
        key = _normalise_headline(title)
        if key is None:
            continue
        rows.append((key, _parse_ts(ts)))
    if not rows:
        return {
            "novelty": None, "n": 0, "first_seen": 0, "repeats": [],
            "window": window, "basis": "no usable headline in the article set",
        }
    stamps = [ts for _, ts in rows if ts is not None]
    if window and int(window) > 0 and stamps:
        latest = max(stamps)
        cutoff = latest - int(window) * 86400.0
        rows = [(k, ts) for k, ts in rows if ts is None or ts >= cutoff]
    seen: set[str] = set()
    first_seen = 0
    repeats: list[str] = []
    for key, _ in rows:
        if key in seen:
            repeats.append(key)
        else:
            seen.add(key)
            first_seen += 1
    n = len(rows)
    novelty = first_seen / n if n else None
    return {
        "novelty": round(novelty, 4) if novelty is not None else None,
        "n": n,
        "first_seen": first_seen,
        "repeats": repeats,
        "window": window,
        "basis": (
            f"{first_seen} first-seen of {n} article(s)"
            + (f" within {window}d" if window else "")
            + (f"; {len(repeats)} repeat(s)" if repeats else "")
        ),
    }


def _parse_ts(raw) -> float | None:
    """An ISO-8601-ish timestamp to epoch seconds, or ``None``."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw).strip()
    if not text:
        return None
    from datetime import datetime, timezone

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                "%Y%m%dT%H%M%S"):
        try:
            dt = datetime.strptime(text[: len(fmt) + 6][: len(fmt)], fmt)
        except ValueError:
            continue
        return dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


# --- The producers this module owns (NEWS-3/4/8/10/11) --------------------- #


def _series_from_rows(points, key: str) -> list[float]:
    """The numeric column ``key`` from a per-day row list, or the list itself.

    ``points`` is what ``sentiment.daily_sentiment_sma`` returns - a list of
    ``{"date", "score", "sma_7d", "innovation", "n"}`` - or a bare numeric list.
    Rows whose ``key`` is None or unreadable are skipped, never zero-filled, and
    a non-finite value is skipped too.
    """
    out: list[float] = []
    for p in points or []:
        raw = p.get(key) if isinstance(p, dict) else p
        if raw is None:
            continue
        try:
            f = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def news_volume_acceleration(points, *, window: int | None = None) -> dict | None:
    """The first difference of the per-day mention counts (NEWS-8, library §44).

    ``points`` is the row list ``sentiment.daily_sentiment_sma`` returns (its
    ``n`` is the per-day mention count) or a bare count series, oldest -> newest.
    ``window`` keeps only the last N days before differencing.

    ``acceleration`` is ``V_t - V_{t-1}`` - the first difference the owner's
    weight table calls "news volume acceleration", distinct from the LEVEL ratio
    currently wired as ``persistence``. A FLAT count series scores
    ``acceleration == 0.0``: exactly zero, not ``None``, because "the volume did
    not accelerate" is a measurement and not a gap. ``normalized`` is
    ``acceleration / sigma_V`` with ``sigma_V`` the series' population standard
    deviation, and is ``None`` when ``sigma_V == 0`` - a flat series has no scale
    to normalise by, and dividing by zero is not a measurement.

    Returns ``{"acceleration", "normalized", "sigma", "n", "window", "basis"}``,
    or ``None`` below two usable counts.
    """
    counts = _series_from_rows(points, "n")
    if window and int(window) > 0:
        counts = counts[-int(window):]
    if len(counts) < 2:
        return None
    acceleration = counts[-1] - counts[-2]
    mean = sum(counts) / len(counts)
    sigma = (sum((c - mean) ** 2 for c in counts) / len(counts)) ** 0.5
    return {
        "acceleration": round(acceleration, 6),
        "normalized": round(acceleration / sigma, 6) if sigma > 1e-12 else None,
        "sigma": round(sigma, 6),
        "n": len(counts),
        "window": int(window) if window and int(window) > 0 else None,
        "basis": (
            "news volume acceleration = V_t - V_{t-1} over the per-day mention "
            "counts (library §44); normalized = acceleration / sigma_V (None when "
            "the series is flat, sigma_V = 0); a flat series is 0.0 acceleration - "
            f"a measurement, not a gap; n={len(counts)} count(s)"
        ),
    }


#: The multi-lambda decay of library §12, as used by §49's persistence form:
#: three half-lives in DAYS with weights that sum to 1. Declared, like ``RAMPS``.
PERSISTENCE_HALF_LIVES: tuple[float, ...] = (7.0, 14.0, 30.0)
PERSISTENCE_WEIGHTS: tuple[float, ...] = (0.5, 0.3, 0.2)

#: Below this many scored periods the share is not a persistence measure - a
#: "share of positive periods" over two days is noise. Stated, not silent.
PERSISTENCE_MIN_PERIODS = 5


def news_persistence(
    points, *, min_periods: int = PERSISTENCE_MIN_PERIODS
) -> dict | None:
    """The persistence quantity the library names, over the sentiment series.

    ``points`` is the row list ``sentiment.daily_sentiment_sma`` returns (its
    ``score`` column) or a bare series, oldest -> newest. Two quantities:

    - ``positive_share`` = ``#{S_t > 0} / n`` - §49's first form, the share of
      positive periods. Exactly 0.0 is a measurement ("no positive period"),
      never ``None``.
    - ``decayed_persistence`` = the same indicator weighted by the multi-lambda
      kernel of §12 - ``sum_k K(k) * I(S_{t-k} > 0) / sum_k K(k)`` with
      ``K(k) = sum_j w_j * 2^(-k / h_j)`` over ``PERSISTENCE_HALF_LIVES`` /
      ``PERSISTENCE_WEIGHTS`` - so a positive period near the end of the series
      counts for more than an old one. Normalised by the kernel sum, so it stays
      in [0, 1].

    This is NOT the inverted attention ratio the wired ``persistence`` component
    carries: it is a property of the SENTIMENT series (positive periods), the
    quantity `NewsScore.md` §8.2 names, and its direction is the opposite one.

    Returns ``{"positive_share", "decayed_persistence", "n_periods",
    "min_periods", "half_lives", "weights", "basis"}``, or ``None`` below
    ``min_periods`` scored periods (the stated floor).
    """
    vals = _series_from_rows(points, "score")
    floor = max(1, int(min_periods))
    if len(vals) < floor:
        return None
    n = len(vals)
    positives = [1.0 if v > 0.0 else 0.0 for v in vals]
    kernel = [
        sum(
            w * 0.5 ** (k / h)
            for w, h in zip(PERSISTENCE_WEIGHTS, PERSISTENCE_HALF_LIVES, strict=True)
        )
        for k in range(n)
    ]
    ksum = sum(kernel)
    decayed = (
        sum(kernel[k] * positives[n - 1 - k] for k in range(n)) / ksum
        if ksum > 0
        else None
    )
    return {
        "positive_share": round(sum(positives) / n, 6),
        "decayed_persistence": round(decayed, 6) if decayed is not None else None,
        "n_periods": n,
        "min_periods": floor,
        "half_lives": list(PERSISTENCE_HALF_LIVES),
        "weights": list(PERSISTENCE_WEIGHTS),
        "basis": (
            "positive_share = #{S_t>0}/n (library §49); decayed_persistence = "
            "sum_k K(k) I(S_{t-k}>0) / sum_k K(k) with the multi-lambda kernel "
            "K(k)=sum_j w_j 2^(-k/h_j), h=(7,14,30)d, w=(0.5,0.3,0.2) (§12/§49), "
            "normalised to [0,1]; this is a property of the SENTIMENT series, not "
            f"the attention ratio; n_periods={n}, floor {floor}"
        ),
    }


#: The sample-size constant of the library's ``C_N = 1 - e^(-N/k)`` (§41) and
#: the Wilson z for a 95% interval (§43). Declared, overridable per call.
CONFIDENCE_SAMPLE_K = 10.0
CONFIDENCE_Z = 1.96


def news_confidence(
    positive,
    total,
    *,
    k: float = CONFIDENCE_SAMPLE_K,
    z: float = CONFIDENCE_Z,
    alpha: float = 1.0,
    beta: float = 1.0,
) -> dict | None:
    """A first-class news confidence from sample size, Wilson and a Beta prior.

    ``positive`` is the count of positive-news observations and ``total`` the
    sample size they came from (the day's accepted article count is the natural
    input). ``total <= 0`` returns ``None`` - an empty sample has no confidence,
    and 0.0 would read as "certainly no signal".

    The recipe, named here because the library lists its parts separately:

    - ``c_n`` = ``1 - e^(-N/k)`` - the sample-size confidence (§41/§112), so one
      article cannot buy 99% confidence.
    - ``wilson_low``/``wilson_high`` - the Wilson score interval on
      ``p_hat = positive / total`` at ``z`` (§43); ``wilson_width`` its width.
    - ``confidence`` = ``c_n * (1 - wilson_width)`` - the interval width used as
      the confidence PENALTY (§43's own suggestion), clamped to [0, 1].
    - ``bayesian_mean`` = ``(alpha + positive) / (alpha + beta + total)`` - the
      ``Beta(alpha, beta)`` posterior mean (§42), useful on thin coverage.

    This is NOT the weight-share ``coverage`` the score result carries: coverage
    says how much of the declared weight was measured, confidence says how much
    the measured sample can support. Different units, different keys.

    Returns ``{"confidence", "sample_size", "positive", "negative",
    "positive_share", "c_n", "wilson_low", "wilson_high", "wilson_width",
    "bayesian_mean", "k", "z", "alpha", "beta", "basis"}``, or ``None`` when the
    sample is empty.
    """
    try:
        n = int(total)
        x = int(positive)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    x = max(0, min(x, n))
    p = x / n
    kf = float(k) if float(k) > 0 else CONFIDENCE_SAMPLE_K
    zf = float(z)
    c_n = 1.0 - math.exp(-n / kf)
    denom = 1.0 + zf * zf / n
    centre = (p + zf * zf / (2.0 * n)) / denom
    half = (zf / denom) * math.sqrt(p * (1.0 - p) / n + zf * zf / (4.0 * n * n))
    low = max(0.0, centre - half)
    high = min(1.0, centre + half)
    width = high - low
    confidence = max(0.0, min(1.0, c_n * (1.0 - width)))
    bayes = (float(alpha) + x) / (float(alpha) + float(beta) + n)
    return {
        "confidence": round(confidence, 6),
        "sample_size": n,
        "positive": x,
        "negative": n - x,
        "positive_share": round(p, 6),
        "c_n": round(c_n, 6),
        "wilson_low": round(low, 6),
        "wilson_high": round(high, 6),
        "wilson_width": round(width, 6),
        "bayesian_mean": round(bayes, 6),
        "k": kf,
        "z": zf,
        "alpha": float(alpha),
        "beta": float(beta),
        "basis": (
            f"confidence = C_N * (1 - Wilson width) = {c_n:.4f} * (1 - {width:.4f}); "
            f"C_N = 1 - e^(-N/k) with N={n}, k={kf:g} (library §41); Wilson {zf:g} "
            f"interval on p_hat={p:.4f} (§43); Beta({float(alpha):g},{float(beta):g}) "
            f"posterior mean {bayes:.4f} (§42); sample size {n}; this is NOT the "
            "weight-share coverage - coverage measures weight present, confidence "
            "measures what the sample supports"
        ),
    }


#: The DECLARED form -> event-class score table (`D-2` / NEWS-4). A mapping the
#: engine carries, exactly like ``RAMPS`` and ``NEWS_BANDS``: it states the sign
#: and rough size each SEC form type signals on the 0-100 ``higher_better`` scale
#: ``COMPONENTS["corporate_events"]`` declares. It is NOT measured or validated -
#: no event study or IC backs these edges - and the form vocabulary is
#: ``dataflows.sec_edgar._FORM_LABELS:39``. A form absent from this table is
#: IGNORED, never defaulted to a neutral 50.
FORM_EVENT_SCORES: dict[str, float] = {
    "8-K": 75.0,      # material event: M&A, guidance, restatement
    "SC 13D": 70.0,   # activist / 5%+ stake
    "DEF 14A": 55.0,  # proxy / governance
    "SC 13G": 55.0,   # institutional 5%+ stake (passive)
    "S-1": 50.0,      # IPO / primary raise
    "10-K": 45.0,     # annual report (routine)
    "S-3": 40.0,      # shelf / secondary offering (dilution)
    "10-Q": 35.0,     # quarterly report (routine)
}


def _form_rows(forms) -> list[dict]:
    """``forms`` as ``[{"form", "date"}]`` - a bare string is a form with no date."""
    rows = []
    for f in forms or []:
        if isinstance(f, dict):
            name = f.get("form") or f.get("type") or f.get("form_type")
            date = f.get("date") or f.get("filing_date") or f.get("filed")
        else:
            name, date = f, None
        if name is None:
            continue
        rows.append({"form": str(name).strip().upper(), "date": _parse_ts(date)})
    return rows


def corporate_events_score(forms, *, window_days: int | None = None) -> dict:
    """The ``corporate_events`` value from the forms a filings read returned.

    ``forms`` is a list of form-type strings (``"8-K"``) or of dicts carrying
    ``form``/``type`` and an optional ``date``. ``window_days`` keeps only the
    filings within that many days of the latest dated one; undated rows are kept,
    and a bare string list has nothing to window (the basis says so).

    The value is the **maximum** ``FORM_EVENT_SCORES`` over the recognised forms:
    a filing set is read by its most material filing, not by its average, and the
    mean is reported beside it for a reader who wants it. Unknown forms are
    **ignored, not defaulted**; when every form is unknown - or the list is
    empty - ``score`` is ``None`` with ``reason``, never a neutral 50.

    Returns ``{"score", "forms", "ignored", "mean", "n", "window_days", "reason",
    "basis"}``. A refusal is this dict with ``score=None`` and the reason, so the
    caller can print WHY, rather than a bare ``None`` that loses the reason.
    """
    rows = _form_rows(forms)
    if not rows:
        return {
            "score": None, "forms": [], "ignored": [], "mean": None, "n": 0,
            "window_days": window_days,
            "reason": "no filed forms in the read",
            "basis": "corporate_events_score: no filed forms in the read",
        }
    windowed = False
    if window_days and int(window_days) > 0:
        stamps = [r["date"] for r in rows if r["date"] is not None]
        if stamps:
            cutoff = max(stamps) - int(window_days) * 86400.0
            rows = [r for r in rows if r["date"] is None or r["date"] >= cutoff]
            windowed = True
    known, ignored = [], []
    for r in rows:
        if r["form"] in FORM_EVENT_SCORES:
            known.append(r["form"])
        else:
            ignored.append(r["form"])
    if not known:
        return {
            "score": None, "forms": [], "ignored": sorted(set(ignored)), "mean": None,
            "n": len(rows), "window_days": window_days,
            "reason": (
                "no recognised SEC form: "
                + ", ".join(sorted(set(ignored)) or ["<none>"])
                + f" (known: {', '.join(sorted(FORM_EVENT_SCORES))})"
            ),
            "basis": (
                "corporate_events_score: every form was unknown to the declared "
                "FORM_EVENT_SCORES table, so the component is withheld rather than "
                "defaulted to a neutral 50"
            ),
        }
    scores = [FORM_EVENT_SCORES[f] for f in known]
    window_note = (
        f"; window_days={int(window_days)} applied to dated rows"
        if windowed
        else (
            f"; window_days={int(window_days)} given but no dated row to apply it to"
            if window_days and int(window_days) > 0
            else ""
        )
    )
    return {
        "score": max(scores),
        "forms": known,
        "ignored": sorted(set(ignored)),
        "mean": round(sum(scores) / len(scores), 4),
        "n": len(rows),
        "window_days": int(window_days) if window_days and int(window_days) > 0 else None,
        "reason": None,
        "basis": (
            f"corporate_events = max(FORM_EVENT_SCORES) = {max(scores):g} over "
            f"{len(known)} recognised form(s) ({', '.join(known)})"
            + (
                f"; ignored (unknown, never defaulted): {', '.join(sorted(set(ignored)))}"
                if ignored
                else ""
            )
            + window_note
            + "; the table is DECLARED, not measured (D-2), on the 0-100 "
            "higher_better scale the component declares"
        ),
    }


#: The DECLARED ramp for a guidance revision: the signed relative change of the
#: midpoint saturates at +/-10%. Mapped 0 -> 50, +0.10 -> 100, -0.10 -> 0 by
#: ``score_engine.align``, so a RAISED midpoint scores above 50 and a CUT below.
#: Declared and unvalidated, like ``RAMPS``; it is the magnitude rule this
#: producer states rather than invents.
GUIDANCE_RAMP: tuple[float, float] = (-0.10, 0.10)


def _range_midpoint(lo, hi, est) -> float | None:
    """The range midpoint, or the point estimate when the range is absent."""
    try:
        lof = None if lo is None else float(lo)
        hif = None if hi is None else float(hi)
        estf = None if est is None else float(est)
    except (TypeError, ValueError):
        return None
    if lof is not None and hif is not None:
        return (lof + hif) / 2.0
    return estf


def _relative_change(new, prior) -> float | None:
    """``(new - prior) / |prior|``, or None when either side is missing or zero."""
    if new is None or prior is None or prior == 0.0:
        return None
    return (new - prior) / abs(prior)


def guidance_change_score(rows) -> dict:
    """The ``guidance_change`` value from guidance revision rows.

    ``rows`` is what ``benzinga_tools.get_guidance_revisions`` returns: one dict
    per revision, with the forward range (``revenue_guidance_min``/``max``/
    ``est``, ``eps_guidance_min``/``max``/``est``) and the prior range
    (``revenue_guidance_prior_min``/``prior_max``,
    ``eps_guidance_prior_min``/``prior_max``).

    **Direction and magnitude rule (declared):** per metric the signed relative
    change of the midpoint is ``(new_mid - prior_mid) / |prior_mid|``, and
    ``score = align(mean_change, lo=-0.10, hi=0.10)`` - a RAISED midpoint scores
    above 50, a CUT below, an unchanged midpoint exactly 50, and a change of
    +/-10% or more saturates at 100/0. ``GUIDANCE_RAMP`` is that declared ramp;
    it is not a fitted estimate. The mean is taken over the metrics that carry
    BOTH a new and a prior range (revenue and/or EPS), pooled across rows.

    A row with no prior range contributes nothing - it cannot be differenced -
    and when NO row yields a usable change (the default-off case, or a read that
    carries only forward figures) ``score`` is ``None`` with ``reason``, never a
    neutral 50.

    Returns ``{"score", "signed_change", "revenue_change", "eps_change",
    "n_rows", "n_used", "ramp", "reason", "basis"}``.
    """
    usable_rev: list[float] = []
    usable_eps: list[float] = []
    n_rows = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        n_rows += 1
        rev = _relative_change(
            _range_midpoint(
                row.get("revenue_guidance_min"),
                row.get("revenue_guidance_max"),
                row.get("revenue_guidance_est"),
            ),
            _range_midpoint(
                row.get("revenue_guidance_prior_min"),
                row.get("revenue_guidance_prior_max"),
                None,
            ),
        )
        eps = _relative_change(
            _range_midpoint(
                row.get("eps_guidance_min"),
                row.get("eps_guidance_max"),
                row.get("eps_guidance_est"),
            ),
            _range_midpoint(
                row.get("eps_guidance_prior_min"),
                row.get("eps_guidance_prior_max"),
                None,
            ),
        )
        if rev is not None:
            usable_rev.append(rev)
        if eps is not None:
            usable_eps.append(eps)
    changes = usable_rev + usable_eps
    if not changes:
        return {
            "score": None, "signed_change": None, "revenue_change": None,
            "eps_change": None, "n_rows": n_rows, "n_used": 0,
            "ramp": list(GUIDANCE_RAMP),
            "reason": (
                "no row carries a prior range to difference (the guidance gate is "
                "off by default, and a forward-only read cannot show a change)"
            ),
            "basis": (
                "guidance_change_score: no differencable guidance row, so the "
                "component is withheld rather than defaulted to a neutral 50"
            ),
        }
    rev_mean = sum(usable_rev) / len(usable_rev) if usable_rev else None
    eps_mean = sum(usable_eps) / len(usable_eps) if usable_eps else None
    signed = sum(changes) / len(changes)
    lo, hi = GUIDANCE_RAMP
    return {
        "score": align(signed, direction="higher_better", lo=lo, hi=hi),
        "signed_change": round(signed, 6),
        "revenue_change": round(rev_mean, 6) if rev_mean is not None else None,
        "eps_change": round(eps_mean, 6) if eps_mean is not None else None,
        "n_rows": n_rows,
        "n_used": len(changes),
        "ramp": [lo, hi],
        "reason": None,
        "basis": (
            "guidance change = mean signed relative midpoint change "
            f"{signed:+.4f} over {len(changes)} metric(s), mapped by the DECLARED "
            f"ramp ({lo:g} -> 0, {hi:g} -> 100): a raised midpoint scores above 50, "
            "a cut below; revenue_change="
            f"{round(rev_mean, 6) if rev_mean is not None else 'n/a'}, "
            f"eps_change={round(eps_mean, 6) if eps_mean is not None else 'n/a'}; "
            "the ramp is declared, not fitted"
        ),
    }


# --- Alignment ------------------------------------------------------------- #


def _coerce(value):
    """Booleans become 1.0/0.0 (a boolean is a measurement, not a gap)."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return value


def align_components(values: dict) -> dict[str, float | None]:
    """``{component: raw}`` -> ``{component: 0-100 favourable | None}``."""
    out: dict[str, float | None] = {}
    for name in COMPONENT_ORDER:
        if name not in (values or {}):
            out[name] = None
            continue
        raw = _coerce(values.get(name))
        if raw is None:
            out[name] = None
            continue
        lo, hi = RAMPS[name]
        out[name] = align(raw, direction=COMPONENTS[name].direction, lo=lo, hi=hi)
    return out


def _weight_basis(weights) -> str:
    if weights is None:
        return "owner weights " + ", ".join(
            f"{k}={v:g}" for k, v in sorted(COMPONENT_WEIGHTS.items())
        )
    return "supplied weights " + ", ".join(f"{k}={float(v):g}" for k, v in sorted(weights.items()))


def news_score(components: dict, *, weights: dict | None = None,
               min_coverage=COMPOSITE_MIN_COVERAGE, confidence: dict | None = None) -> dict:
    """The eleven components and their weighted composite, or withheld with a reason.

    ``components`` is ``{component: raw value}`` over ``COMPONENTS``. The five
    ``ABSENT_COMPONENTS`` print ``NA`` with the reason from ``ABSENT_REASONS``
    unless the caller supplies a value (only ``materiality`` is ever supplyable -
    EventScore owns it, owner Q6).

    A repeated headline lowers ``novelty`` (feed the value from ``news_novelty``).
    Relevance and materiality are independent rows; relevance alone cannot raise
    the composite, and materiality is never inferred from it.

    ``confidence`` is the optional ``news_confidence`` result (sample size /
    Wilson interval / Bayesian). It is returned under its own ``confidence`` key
    and is **not** the ``coverage`` value: coverage is the weight share measured,
    confidence is what the sample can support. ``None`` when the caller has no
    sample, and the basis says so.

    Returns ``{"score", "coverage", "floor", "categories", "components",
    "aligned", "bands", "weights", "status", "withheld", "measured", "absent",
    "absent_reasons", "confidence", "scale", "basis"}``. ``categories`` is one
    block per owner category, the same shape ``sentiment_score`` returns (so both
    renderers can print the breakdown). ``score`` is ``None`` - never 0, never 50
    - when the composite is below its floor; with the five absent components fed
    ``None`` the coverage is 0 and the score is ``None``.
    """
    comps = {name: (components or {}).get(name) for name in COMPONENT_ORDER}
    supplied = {name for name in COMPONENT_ORDER if name in (components or {})}
    w = dict(weights) if weights is not None else dict(COMPONENT_WEIGHTS)
    aligned = align_components({name: v for name, v in comps.items() if v is not None})
    combined = combine(
        {name: aligned.get(name) for name in COMPONENT_ORDER},
        weights=w,
        min_coverage=coverage_floor(min_coverage, len(COMPONENT_ORDER)),
        bands=NEWS_BANDS,
    )
    categories = {
        cat: _category_score(cat, aligned, min_coverage=NEWS_CATEGORY_MIN_COVERAGE)
        for cat in NEWS_CATEGORY_ORDER
    }
    conf = dict(confidence) if isinstance(confidence, dict) else None

    measured = [name for name in COMPONENT_ORDER if aligned.get(name) is not None]
    absent = [name for name in COMPONENT_ORDER if aligned.get(name) is None]
    # Only the declared-absent five carry a producer-gap reason; the rest are
    # simply not supplied on this call.
    absent_reasons = {
        name: ABSENT_REASONS[name] for name in absent if name in ABSENT_REASONS
    }
    if conf is not None and conf.get("confidence") is not None:
        conf_txt = (
            f"confidence {conf['confidence']:.4f} from news_confidence "
            f"(sample size {conf.get('sample_size')}; C_N x (1 - Wilson width)); "
            f"coverage {combined.get('coverage')} is a WEIGHT SHARE, a different "
            f"quantity"
        )
    else:
        conf_txt = (
            "confidence not supplied (news_confidence: sample size / Wilson / "
            "Bayesian); coverage is a weight share, not a confidence"
        )
    basis = (
        f"NewsScore: {len(measured)} of {len(COMPONENT_ORDER)} component(s) measured "
        f"-> {_weight_basis(weights)}; "
        f"coverage {combined.get('coverage')}; "
        f"{len(absent_reasons)} absent with a reason "
        f"({', '.join(sorted(absent_reasons))}); "
        f"relevance and materiality are independent rows (relevance is not "
        f"materiality); {conf_txt}; scale: {SCALE_CONVENTION}; "
        f"advisory only - never a gate, never a size"
    )
    return {
        "score": combined.get("score"),
        "coverage": combined.get("coverage"),
        "floor": combined.get("floor"),
        "categories": categories,
        "components": {
            name: {
                "raw": comps.get(name),
                "aligned": aligned.get(name),
                "direction": COMPONENTS[name].direction,
                "producer": COMPONENTS[name].producer,
                "note": COMPONENTS[name].note,
                "reason": (
                    ABSENT_REASONS[name]
                    if aligned.get(name) is None and name in ABSENT_REASONS
                    else ("not supplied" if name not in supplied else "unreadable")
                ),
            }
            for name in COMPONENT_ORDER
        },
        "aligned": aligned,
        "bands": band_label(combined.get("score"), NEWS_BANDS),
        "weights": w if weights is not None else None,
        "status": STATUS_ADVISORY,
        "withheld": combined.get("withheld"),
        "measured": measured,
        "absent": absent,
        "absent_reasons": absent_reasons,
        "confidence": conf,
        "scale": SCALE_CONVENTION,
        "basis": basis,
    }


def component_weight_share(weights: dict | None = None) -> dict[str, float]:
    """``{component: weight}`` actually used, so a reader can renormalise."""
    w = dict(weights) if weights is not None else dict(COMPONENT_WEIGHTS)
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


__all__ = [
    "COMPONENT_WEIGHTS",
    "COMPONENT_ORDER",
    "COMPONENTS",
    "Component",
    "ABSENT_COMPONENTS",
    "ABSENT_REASONS",
    "RAMPS",
    "NEWS_BANDS",
    "NEWS_CATEGORY_ORDER",
    "NEWS_CATEGORIES",
    "NEWS_CATEGORY_WEIGHTS",
    "NEWS_CATEGORY_MIN_COVERAGE",
    "STATUS_ADVISORY",
    "COMPOSITE_MIN_COVERAGE",
    "SCALE_CONVENTION",
    "FORM_EVENT_SCORES",
    "GUIDANCE_RAMP",
    "PERSISTENCE_HALF_LIVES",
    "PERSISTENCE_WEIGHTS",
    "PERSISTENCE_MIN_PERIODS",
    "CONFIDENCE_SAMPLE_K",
    "CONFIDENCE_Z",
    "news_novelty",
    "news_volume_acceleration",
    "news_persistence",
    "news_confidence",
    "corporate_events_score",
    "guidance_change_score",
    "align_components",
    "news_score",
    "component_weight_share",
]
