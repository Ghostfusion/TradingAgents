"""`NewsScore` (WP-6) - what new information arrived, and how material is it?

The owner's nine categories (`docs/scores/NewsScore.md` §0.1) as this engine can
honestly build them today: relevance & materiality 20, novelty 15, fundamental
impact 20, earnings & guidance 15, corporate events 10, regulatory & legal 5,
analyst & rating 5, macro & industry 5, persistence 5. **Five of the eleven
components below have no producer** and print `NA` **with the reason**, never 0.

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

One pure function over a flat ``{component: raw value}`` dict - every value is
produced elsewhere and assembled by the caller/leaf.
"""

from __future__ import annotations

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
        "EventScore owns the materiality / expected-move number (owner Q6) and it "
        "is caller-supplied; NA until the caller passes it - NEVER approximated by "
        "relevance"
    ),
    "fundamental_impact": (
        "no revenue/margin-impact producer exists; the honest answer is NA"
    ),
    "guidance_change": (
        "no guidance source (get_earnings_calendar carries an EPS estimate only); "
        "do not fake it from the EPS estimate"
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
    "guidance_change": (-0.05, 0.05),   # (no producer)
    "corporate_events": (0.0, 1.0),     # SEC form typing -> event-class score
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
           "news_relevance.score_news_article:53",
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
        _c("guidance_change", "earnings_guidance", "higher_better", None, None),
        _c("corporate_events", "corporate_events", "higher_better",
           "sec_edgar._FORM_LABELS:36",
           "form typing mapped by the caller to an event-class score"),
        _c("regulatory_legal", "regulatory_legal", "lower_better", None,
           "text_factors.lm_tone:121 gives a litigious count only; no classifier"),
        _c("analyst_revision", "analyst_rating", "higher_better",
           "analyst_revisions.revision_ratio:79",
           "the binding moves to the news surface (Q4)"),
        _c("industry_shock", "macro_industry", "higher_better", None, None),
        _c("persistence", "persistence", "lower_better",
           "sentiment.mention_volume:43 + decayed_weight:91",
           "neglected-firm sign (plan §13 Q9): lower abnormal coverage is positive"),
    )
}

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
    "event typing 0-1; analyst revision -1..1; persistence a mention ratio"
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
               min_coverage=COMPOSITE_MIN_COVERAGE) -> dict:
    """The eleven components and their weighted composite, or withheld with a reason.

    ``components`` is ``{component: raw value}`` over ``COMPONENTS``. The five
    ``ABSENT_COMPONENTS`` print ``NA`` with the reason from ``ABSENT_REASONS``
    unless the caller supplies a value (only ``materiality`` is ever supplyable -
    EventScore owns it, owner Q6).

    A repeated headline lowers ``novelty`` (feed the value from ``news_novelty``).
    Relevance and materiality are independent rows; relevance alone cannot raise
    the composite, and materiality is never inferred from it.

    Returns ``{"score", "coverage", "components", "aligned", "bands",
    "weights", "status", "withheld", "measured", "absent", "absent_reasons",
    "scale", "basis"}``. ``score`` is ``None`` - never 0, never 50 - when the
    composite is below its floor; with the five absent components fed ``None`` the
    coverage is 0 and the score is ``None``.
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

    measured = [name for name in COMPONENT_ORDER if aligned.get(name) is not None]
    absent = [name for name in COMPONENT_ORDER if aligned.get(name) is None]
    # Only the declared-absent five carry a producer-gap reason; the rest are
    # simply not supplied on this call.
    absent_reasons = {
        name: ABSENT_REASONS[name] for name in absent if name in ABSENT_REASONS
    }
    basis = (
        f"NewsScore: {len(measured)} of {len(COMPONENT_ORDER)} component(s) measured "
        f"-> {_weight_basis(weights)}; "
        f"coverage {combined.get('coverage')}; "
        f"{len(absent_reasons)} absent with a reason "
        f"({', '.join(sorted(absent_reasons))}); "
        f"relevance and materiality are independent rows (relevance is not "
        f"materiality); scale: {SCALE_CONVENTION}; "
        f"advisory only - never a gate, never a size"
    )
    return {
        "score": combined.get("score"),
        "coverage": combined.get("coverage"),
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
    "STATUS_ADVISORY",
    "COMPOSITE_MIN_COVERAGE",
    "SCALE_CONVENTION",
    "news_novelty",
    "align_components",
    "news_score",
    "component_weight_share",
]
