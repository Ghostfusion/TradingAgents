"""`SentimentScore` (WP-7) - the positioning read, and the confirmation quadrant.

The engine the owner's staged weights describe (`docs/scores/SentimentScore.md`
§0.1): news sentiment 15, momentum 15, breadth 10, institutional 15, analyst 10,
retail/social 10, options 10, short interest 5, dispersion 5, extreme/crowding 5.

Five rules this module exists to hold:

1. **The unit is pinned before anything is weighted.** The news-sentiment route
   carries **two scales behind one name**: EODHD/Alpha Vantage deliver -1..1, GDELT
   delivers **-100..100** (`gdelt.get_news_sentiment_gdelt`, routed untransformed),
   so a GDELT-sourced `sma_7d`/`innovation` is ~100x an EODHD one. Every tone leg
   therefore enters through ``normalise_sentiment`` on the canonical unit scale,
   and **two sources in one read are refused** rather than averaged (see
   ``SCALE_CONVENTION`` and ``SCALE_TABLE``).
2. **`NA` is not `0`** (master rule 1): an absent component is ``None`` and leaves
   the denominator; a category below its floor is withheld with the reason; the
   composite reports its coverage instead of scoring what it lacks.
3. **Attention and tone stay separate rows** (SentimentScore.md §0.2 point 3):
   ``mention_heat`` (attention) and ``weighted_tone`` (tone) are distinct
   components in distinct categories and are never summed into one number - they
   have opposite short-horizon signs.
4. **The quadrant is the headline output, not the score** (SentimentScore.md
   §0.3): ``confirmation_quadrant`` returns one of four distinct labels over
   ``Sign(abnormal return) x Sign(dSentiment)``, because *"don't assume positive
   sentiment is bullish"*.
5. **This engine never sizes** (owner Q10): ``sentiment_factor_scale`` stays a
   separate sizing multiplier; nothing here touches `risk/sizing.py`, a gate, or
   `decision_guardrail.SCORE_BANDS`.

The module imports **no cross-engine number**: no ``news_relevance`` (that is the
news path's own pipeline), no other score engine. One pure function over a flat
``{component: raw value}`` dict - every value is produced elsewhere by the
sentiment pipeline (`sentiment.aggregate_weighted_sentiment`,
`sentiment.daily_sentiment_sma`, `sentiment.sentiment_velocity`,
`sentiment.crowd_ratio`, `sentiment.compute_social_scores`, the options/short
producers) and assembled by the caller/leaf.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from .score_engine import align, band_label, combine, coverage_floor

# --- The scale, pinned first (SentimentScore.md §5.1) ---------------------- #

SCALE_UNIT = "unit"
CANONICAL_SCALE: tuple[float, float] = (-1.0, 1.0)

#: ``source -> (lo, hi)`` for every feed that reaches this engine.
#: ``unit`` is the canonical -1..1; ``eodhd``/``alpha_vantage`` are already on it;
#: ``gdelt`` is -100..100 (GDELT's own documentation: -100 extremely negative,
#: +100 extremely positive, most values in the -10..+10 band).
SCALE_TABLE: dict[str, tuple[float, float]] = {
    "unit": (-1.0, 1.0),
    "eodhd": (-1.0, 1.0),
    "alpha_vantage": (-1.0, 1.0),
    "av": (-1.0, 1.0),
    "gdelt": (-100.0, 100.0),
}

#: Printed beside every score so a reader can see the unit the number is in.
SCALE_CONVENTION = (
    "tone on the canonical unit scale (-1..1); eodhd/alpha_vantage/av are -1..1, "
    "gdelt is -100..100; each tone leg is normalised by normalise_sentiment and "
    "two sources in one read are REFUSED, never averaged together"
)

#: The components that carry a *tone* level and therefore need a declared source.
TONE_COMPONENTS: tuple[str, ...] = (
    "weighted_tone",
    "sma_7d",
    "tone_innovation",
    "tone_velocity",
)


def normalise_sentiment(value, source=SCALE_UNIT) -> dict:
    """Map one tone reading to the canonical unit scale (-1..1), or refuse it.

    Returns ``{"value", "source", "scale", "target", "basis"}``. ``value`` is
    ``None`` when the reading is missing, unreadable, non-finite, or the source is
    unknown - an unrecognised source is refused rather than guessed, because
    guessing the scale is exactly the defect this function exists to close.
    """
    src = str(source if source is not None else SCALE_UNIT).strip().lower()
    target = "unit (-1..1)"
    if src not in SCALE_TABLE:
        return {
            "value": None,
            "source": src,
            "scale": None,
            "target": target,
            "basis": (
                f"refused: unknown sentiment source {src!r} "
                f"(known {sorted(SCALE_TABLE)})"
            ),
        }
    lo, hi = SCALE_TABLE[src]
    scale_txt = f"{lo:g}..{hi:g}"
    if value is None:
        return {
            "value": None, "source": src, "scale": scale_txt, "target": target,
            "basis": f"no value ({src} {scale_txt})",
        }
    if isinstance(value, bool):
        return {
            "value": None, "source": src, "scale": scale_txt, "target": target,
            "basis": f"unreadable ({src} {scale_txt}): boolean is not a tone level",
        }
    try:
        v = float(value)
    except (TypeError, ValueError):
        return {
            "value": None, "source": src, "scale": scale_txt, "target": target,
            "basis": f"unreadable ({src} {scale_txt}): {value!r}",
        }
    if not math.isfinite(v):
        return {
            "value": None, "source": src, "scale": scale_txt, "target": target,
            "basis": f"unreadable ({src} {scale_txt}): non-finite",
        }
    norm = (2.0 * (v - lo) / (hi - lo) - 1.0) if hi != lo else v
    norm = max(-1.0, min(1.0, norm))
    return {
        "value": round(norm, 6),
        "source": src,
        "scale": scale_txt,
        "target": target,
        "basis": f"{v:g} on {src} {scale_txt} -> {norm:.4f} on unit (-1..1)",
    }


# --- The owner's weights (SentimentScore.md §0.1) -------------------------- #

CATEGORY_WEIGHTS: dict[str, float] = {
    "news_sentiment": 15.0,
    "momentum": 15.0,
    "breadth": 10.0,
    "institutional": 15.0,
    "analyst": 10.0,
    "retail_social": 10.0,
    "options": 10.0,
    "short_interest": 5.0,
    "dispersion": 5.0,
    "extreme_crowding": 5.0,
}

CATEGORY_ORDER: tuple[str, ...] = tuple(CATEGORY_WEIGHTS)

# Ramps: ``(lo, hi)`` mapped 0 -> 100 (inverted for ``lower_better``). Every edge
# is this engine's declared policy - the producer's own display bands (the crowd
# 40/60 constants, the 0.7/1.3 PCR split) are NOT reused as score edges, because
# they are display constants, not measured thresholds.
RAMPS: dict[str, tuple[float, float]] = {
    # tone legs are read on the canonical unit scale after normalisation
    "weighted_tone": (-0.5, 0.5),
    "sma_7d": (-0.5, 0.5),
    "tone_innovation": (-0.5, 0.5),
    "tone_velocity": (-0.05, 0.05),
    "bull_share": (0.2, 0.8),
    "neutral_share": (0.2, 0.8),
    "inst_flow_z": (-2.0, 2.0),
    "revision_ratio": (-0.5, 0.5),
    "analyst_agreement": (0.2, 0.8),
    "social_score": (-0.5, 0.5),
    "social_velocity": (-2.0, 2.0),
    "iv_skew": (0.8, 1.2),
    "put_call_ratio": (0.7, 1.3),
    "short_pct_float": (0.05, 0.25),
    "dispersion": (0.2, 0.8),
    "dispersion_agreement": (0.2, 0.8),
    "crowd_ratio": (20.0, 80.0),
    "mention_heat": (0.5, 3.0),
}


class Component(NamedTuple):
    """One component: its category, direction, producer and scale kind."""

    name: str
    category: str
    direction: str
    producer: str
    note: str = ""
    kind: str = "level"


def _c(name, category, direction, producer, note="", kind="level"):
    return Component(name, category, direction, producer, note, kind)


COMPONENTS: dict[str, Component] = {
    c.name: c
    for c in (
        # news sentiment (15)
        _c("weighted_tone", "news_sentiment", "higher_better",
           "sentiment.aggregate_weighted_sentiment:616 (weighted)",
           "tone - kept separate from attention", "tone"),
        _c("sma_7d", "news_sentiment", "higher_better",
           "sentiment.daily_sentiment_sma:501 (sma_7d)", "tone", "tone"),
        # momentum (15)
        _c("tone_innovation", "momentum", "higher_better",
           "sentiment.daily_sentiment_sma:501 (innovation)", "tone", "tone"),
        _c("tone_velocity", "momentum", "higher_better",
           "sentiment.sentiment_velocity:25 (OLS slope/day, canonical per Q4)",
           "tone", "tone"),
        # breadth (10)
        _c("bull_share", "breadth", "higher_better",
           "aggregate_weighted_sentiment per-article score (share > 0)"),
        _c("neutral_share", "breadth", "lower_better",
           "sentiment.aggregate_weighted_sentiment:616 (neutral_share)"),
        # institutional (15)
        _c("inst_flow_z", "institutional", "higher_better",
           "get_institution_holdings period-over-period change in % of float, "
           "z-scored (canonical per Q2)"),
        # analyst (10)
        _c("revision_ratio", "analyst", "higher_better",
           "analyst_revisions.revision_ratio:79"),
        _c("analyst_agreement", "analyst", "higher_better",
           "consensus.agreement_score:14"),
        # retail / social (10)
        _c("social_score", "retail_social", "higher_better",
           "sentiment.compute_social_scores:273 (computed_score)"),
        _c("social_velocity", "retail_social", "higher_better",
           "sentiment.compute_social_scores:273 (computed_velocity, z)"),
        # options (10)
        _c("iv_skew", "options", "lower_better",
           "options_surface.iv_skew:25", "puts rich = fear"),
        _c("put_call_ratio", "options", "lower_better",
           "options_surface.put_call_oi_concentration:34",
           "a positioning gauge, not a predictor (SentimentScore.md §0.2 point 4)"),
        # short interest (5)
        _c("short_pct_float", "short_interest", "lower_better",
           "yfinance_short_interest.get_short_interest_yfinance:37"),
        # dispersion (5)
        _c("dispersion", "dispersion", "lower_better",
           "sentiment.sentiment_dispersion:209",
           "higher disagreement predicts lower returns (Diether-Malloy-Scherbina)"),
        _c("dispersion_agreement", "dispersion", "higher_better",
           "sentiment.sentiment_dispersion:209 (agreement)"),
        # extreme / crowding (5)
        _c("crowd_ratio", "extreme_crowding", "lower_better",
           "sentiment.crowd_ratio:163 (0-100 ratio/percentile)",
           "scored on this engine's own edges; the producer's 40/60 are display "
           "constants, never this engine's score edges"),
        _c("mention_heat", "extreme_crowding", "lower_better",
           "sentiment.mention_volume:43",
           "ATTENTION, not tone - never summed with the tone legs (neglected-firm "
           "sign, plan §13 Q9)"),
    )
}

CATEGORY_COMPONENTS: dict[str, tuple[str, ...]] = {
    cat: tuple(c.name for c in COMPONENTS.values() if c.category == cat)
    for cat in CATEGORY_ORDER
}

# This engine's own advisory bands - never `decision_guardrail.SCORE_BANDS`.
SENTIMENT_BANDS: tuple = (
    (80.0, "bullish-positioned"),
    (65.0, "constructive"),
    (50.0, "neutral"),
    (35.0, "cautious"),
    (20.0, "bearish-positioned"),
    (0.0, "capitulating"),
)

STATUS_ADVISORY = "ADVISORY"

#: The four confirmation labels (SentimentScore.md §4) - never collapsed to two.
CONFIRMATION_QUADRANTS: tuple[str, ...] = (
    "confirm-up",
    "confirm-down",
    "diverge-up",
    "diverge-down",
)

# A category floor of 1 of its own components (institutional / short interest are
# single-component categories); the composite needs 3.
CATEGORY_MIN_COVERAGE = 1
COMPOSITE_MIN_COVERAGE = 3


# --- The confirmation quadrant (SentimentScore.md §0.3) -------------------- #

_UP_WORDS = frozenset({"up", "rising", "positive", "pos", "bullish", "bull",
                       "above", "confirm", "confirmed"})
_DOWN_WORDS = frozenset({"down", "falling", "negative", "neg", "bearish", "bear",
                         "below", "diverge", "divergent"})
_FLAT_WORDS = frozenset({"flat", "neutral", "mixed", "unchanged", "na", "n/a",
                         "none", "unknown", ""})
_READ_KEYS = ("sign", "direction", "value", "score", "innovation",
              "abnormal_return", "read")


def _read_sign(value):
    """``+1`` / ``-1`` / ``None`` for one read (number, word, dict, boolean)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else -1
    if isinstance(value, (int, float)):
        v = float(value)
        if not math.isfinite(v) or v == 0.0:
            return None
        return 1 if v > 0 else -1
    if isinstance(value, str):
        t = value.strip().lower()
        if t in _UP_WORDS:
            return 1
        if t in _DOWN_WORDS:
            return -1
        if t in _FLAT_WORDS:
            return None
        try:
            return _read_sign(float(t))
        except ValueError:
            return None
    if isinstance(value, dict):
        for k in _READ_KEYS:
            if k in value:
                return _read_sign(value[k])
        return None
    return None


def confirmation_quadrant(price_read, fundamental_read) -> str | None:
    """One of four DISTINCT confirmation labels, or ``None`` when unreadable.

    The owner's rule (*"don't assume positive sentiment is bullish"*) is a 2x2
    between the **price read** and the read it should confirm. ``price_read`` is
    the market-adjusted (abnormal) return direction; ``fundamental_read`` is the
    second read (here the sentiment/positioning direction - `dSentiment`). The
    label's suffix names the *price* direction, so a reader can see at a glance
    which way the market moved:

    ====================  ==============  ===================
    price / second read   label           reading
    ====================  ==============  ===================
    up / up               ``confirm-up``  price confirms the read
    up / down             ``diverge-up``  price rose despite the read
    down / down           ``confirm-down`` price confirms the read
    down / up             ``diverge-down`` price fell despite the read
    ====================  ==============  ===================

    A flat or unavailable reading on either axis returns ``None`` - it never
    fabricates a quadrant by collapsing the four cells into two.
    """
    p = _read_sign(price_read)
    f = _read_sign(fundamental_read)
    if p is None or f is None:
        return None
    if p > 0:
        return "confirm-up" if f > 0 else "diverge-up"
    return "confirm-down" if f < 0 else "diverge-down"


# --- Alignment ------------------------------------------------------------- #


def _coerce(value):
    """Booleans become 1.0/0.0 (a boolean is a measurement, not a gap)."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return value


def _resolve_sources(components: dict, source) -> tuple[dict, str | None]:
    """The source per present tone leg, and a refusal when two disagree."""
    present = [n for n in TONE_COMPONENTS if (components or {}).get(n) is not None]
    if not present:
        return {}, None
    if isinstance(source, dict):
        srcs = {
            n: str(source.get(n, SCALE_UNIT) or SCALE_UNIT).strip().lower()
            for n in present
        }
    else:
        s = str(source if source is not None else SCALE_UNIT).strip().lower()
        srcs = {n: s for n in present}
    distinct = sorted(set(srcs.values()))
    if len(distinct) > 1:
        return srcs, (
            "refuses to mix tone sources " + ", ".join(distinct)
            + " (a gdelt -100..100 series is not the same unit as an eodhd/AV "
            "-1..1 series; normalise one source, do not average two)"
        )
    return srcs, None


def normalise_components(components: dict, *, source=None) -> tuple[dict, dict, str | None]:
    """Normalise the tone legs to the unit scale; return ``(values, info, refusal)``."""
    comps = dict(components or {})
    srcs, refusal = _resolve_sources(comps, source)
    if refusal:
        return comps, {}, refusal
    out = dict(comps)
    info: dict[str, dict] = {}
    for name in TONE_COMPONENTS:
        if name not in out:
            continue
        res = normalise_sentiment(out.get(name), srcs.get(name, SCALE_UNIT))
        out[name] = res["value"]
        info[name] = res
    return out, info, None


def align_components(values: dict) -> dict[str, float | None]:
    """``{component: raw}`` -> ``{component: 0-100 favourable | None}``.

    Tone legs are expected on the canonical unit scale (normalise first via
    ``normalise_components``); an unknown key is ignored, and a declared component
    with no value is ``None`` rather than a neutral 50.
    """
    out: dict[str, float | None] = {}
    for name, comp in COMPONENTS.items():
        if name not in (values or {}):
            out[name] = None
            continue
        raw = _coerce(values.get(name))
        if raw is None:
            out[name] = None
            continue
        lo, hi = RAMPS[name]
        out[name] = align(raw, direction=comp.direction, lo=lo, hi=hi)
    return out


def category_score(category: str, aligned: dict, *, min_coverage=CATEGORY_MIN_COVERAGE) -> dict:
    """One category's 0-100 over its own components, or withheld with a reason."""
    if category not in CATEGORY_COMPONENTS:
        raise KeyError(f"unknown category {category!r}; known: {list(CATEGORY_ORDER)}")
    names = CATEGORY_COMPONENTS[category]
    comps = {name: aligned.get(name) for name in names}
    floor = coverage_floor(min_coverage, len(names))
    res = combine(comps, min_coverage=min(floor, len(names)))
    res["category"] = category
    res["weight"] = CATEGORY_WEIGHTS[category]
    res["band"] = band_label(res.get("score"), SENTIMENT_BANDS)
    res["raw_directions"] = {name: COMPONENTS[name].direction for name in names}
    return res


def _weight_basis(weights) -> str:
    if weights is None:
        return "owner weights " + ", ".join(
            f"{k}={v:g}" for k, v in sorted(CATEGORY_WEIGHTS.items())
        )
    return "supplied weights " + ", ".join(f"{k}={float(v):g}" for k, v in sorted(weights.items()))


def sentiment_score(
    components: dict,
    *,
    weights: dict | None = None,
    min_coverage=COMPOSITE_MIN_COVERAGE,
    category_min_coverage=CATEGORY_MIN_COVERAGE,
    source=None,
    price_read=None,
) -> dict:
    """The ten category sub-scores, their composite, and the confirmation quadrant.

    ``components`` is ``{component: raw value}`` over ``COMPONENTS``; tone legs are
    normalised from ``source`` (a source name, or a ``{component: source}`` map)
    onto the canonical unit scale first. ``source`` is **not** an optional nicety:
    a read that mixes two tone sources is **refused** (the score is withheld with
    the reason) rather than silently averaged across the GDELT / EODHD scales.

    ``price_read`` is optional: when given, ``quadrant`` carries
    ``confirmation_quadrant(price_read, tone_innovation)``.

    Returns ``{"score", "coverage", "categories", "components", "aligned",
    "bands", "weights", "status", "withheld", "measured", "absent", "scale",
    "quadrant", "basis"}``. ``score`` is ``None`` (never 0, never 50) when the
    composite is below its floor, including always when the sources are mixed.
    """
    comps = dict(components or {})
    norm, scale_info, refusal = normalise_components(comps, source=source)
    w = dict(weights) if weights is not None else dict(CATEGORY_WEIGHTS)
    scale_out = {
        "convention": SCALE_CONVENTION,
        "canonical": "unit (-1..1)",
        "table": {k: list(v) for k, v in sorted(SCALE_TABLE.items())},
        "sources": {n: scale_info[n].get("source") for n in scale_info},
        "detail": {n: scale_info[n].get("basis") for n in scale_info},
    }
    if refusal:
        return {
            "score": None,
            "coverage": 0.0,
            "categories": {},
            "components": {},
            "aligned": {},
            "bands": None,
            "weights": w if weights is not None else None,
            "status": STATUS_ADVISORY,
            "withheld": refusal,
            "refused": True,
            "measured": [],
            "absent": sorted(comps),
            "scale": scale_out,
            "quadrant": None,
            "basis": f"SentimentScore withheld: {refusal}",
        }

    aligned = align_components(norm)
    cats = {
        cat: category_score(cat, aligned, min_coverage=category_min_coverage)
        for cat in CATEGORY_ORDER
    }
    cat_scores = {cat: cats[cat].get("score") for cat in CATEGORY_ORDER}
    combined = combine(cat_scores, weights=w, min_coverage=min_coverage, bands=SENTIMENT_BANDS)

    measured = [name for name, v in aligned.items() if v is not None]
    absent = [name for name, v in aligned.items() if v is None]
    read = norm.get("tone_innovation")
    quadrant = None
    if price_read is not None and read is not None:
        quadrant = confirmation_quadrant(price_read, read)

    sources_used = sorted({v.get("source") for v in scale_info.values() if v.get("source")})
    basis = (
        f"SentimentScore: {len(measured)} of {len(COMPONENTS)} component(s) measured "
        f"-> {sum(1 for c in cats.values() if c.get('score') is not None)} of "
        f"{len(CATEGORY_ORDER)} category sub-scores -> "
        f"{_weight_basis(weights)}; "
        f"tone normalised to unit (-1..1) from {sources_used or ['unit']}; "
        f"coverage {combined.get('coverage')}; "
        f"quadrant {quadrant or 'n/a'}; "
        f"attention (mention_heat) and tone (weighted_tone) are separate rows; "
        f"advisory only - never a gate, never a size, never a forecast"
    )
    return {
        "score": combined.get("score"),
        "coverage": combined.get("coverage"),
        "categories": cats,
        "components": {
            name: {
                "raw": comps.get(name),
                "normalised": norm.get(name),
                "aligned": aligned.get(name),
                "direction": COMPONENTS[name].direction,
                "category": COMPONENTS[name].category,
                "producer": COMPONENTS[name].producer,
                "scale": scale_info.get(name, {}).get("basis"),
                "note": COMPONENTS[name].note,
            }
            for name in COMPONENTS
        },
        "aligned": aligned,
        "bands": band_label(combined.get("score"), SENTIMENT_BANDS),
        "weights": w if weights is not None else None,
        "status": STATUS_ADVISORY,
        "withheld": combined.get("withheld"),
        "refused": False,
        "measured": measured,
        "absent": absent,
        "scale": scale_out,
        "quadrant": quadrant,
        "basis": basis,
    }


def category_weight_share(weights: dict | None = None) -> dict[str, float]:
    """``{category: weight}`` actually used, so a reader can renormalise."""
    w = dict(weights) if weights is not None else dict(CATEGORY_WEIGHTS)
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


__all__ = [
    "SCALE_UNIT",
    "CANONICAL_SCALE",
    "SCALE_TABLE",
    "SCALE_CONVENTION",
    "TONE_COMPONENTS",
    "CATEGORY_WEIGHTS",
    "CATEGORY_ORDER",
    "CATEGORY_COMPONENTS",
    "COMPONENTS",
    "Component",
    "RAMPS",
    "SENTIMENT_BANDS",
    "STATUS_ADVISORY",
    "CONFIRMATION_QUADRANTS",
    "CATEGORY_MIN_COVERAGE",
    "COMPOSITE_MIN_COVERAGE",
    "normalise_sentiment",
    "normalise_components",
    "align_components",
    "category_score",
    "confirmation_quadrant",
    "sentiment_score",
    "category_weight_share",
]
