"""Shared 5-tier rating vocabulary and a deterministic heuristic parser.

The same five-tier scale (Buy, Overweight, Hold, Underweight, Sell) is used by:
- The Research Manager (investment plan recommendation)
- The Portfolio Manager (final position decision)
- The signal processor (rating extracted for downstream consumers)
- The memory log (rating tag stored alongside each decision entry)

Centralising it here avoids drift between those call sites.

Garbled ratings never coerce to a tradeable tier: when the text contains
rating-like content but its value does not parse as one of the five tiers, the
parser returns the ``REVIEW`` sentinel instead of silently defaulting
(upstream TradingAgents 0.4.0 #1170 — an unparseable Portfolio Manager rating
used to degrade to a tradeable Hold). Callers that pass an explicit
non-tradeable default (e.g. ``"n/a"``) keep it: only the implicit tradeable
``Hold`` fallback is hardened.
"""

from __future__ import annotations

import re

# Canonical, ordered 5-tier scale (most bullish to most bearish).
RATINGS_5_TIER: tuple[str, ...] = (
    "Buy", "Overweight", "Hold", "Underweight", "Sell",
)

# "REVIEW" — human review needed: the text has rating-like content but no
# 5-tier value parses. NEVER a tradeable tier; consumers that act on a rating
# must treat REVIEW as "do not trade on this decision".
REVIEW_SENTINEL = "REVIEW"

_RATING_SET = {r.lower() for r in RATINGS_5_TIER}

# Matches "Rating: X" / "rating - X" / "Rating: **X**" — tolerates markdown
# bold wrappers and either a colon or hyphen separator (incl. fullwidth colon).
_RATING_LABEL_RE = re.compile(r"rating.*?[:\-：—][\s*]*(\w+)", re.IGNORECASE)


# Matches the ``rating`` prefix up to and including the colon/hyphen separator
# (used to isolate the label's value for garbled-detection, including values
# that contain no word characters at all, e.g. "Rating：⭐⭐⭐").
_RATING_PREFIX_RE = re.compile(r"rating.*?[:\-：—]\s*", re.IGNORECASE)


def _has_garbled_rating_label(text: str) -> bool:
    """True when the text attempts a ``Rating: <value>`` label but the value
    is not one of the five tiers — i.e. the author intended a rating and the
    value failed to parse. Word-only mentions of "rating"/"recommendation"
    in ordinary prose do NOT count (that avoids the false-positive REVIEW class).
    """
    for line in text.splitlines():
        m = _RATING_PREFIX_RE.search(line)
        if not m:
            continue
        rest = line[m.end():].strip()
        if not rest:
            continue  # "Rating:" with an empty value: no intent to contradict
        rest_words = re.findall(r"\w+", rest)
        if any(w.lower() in _RATING_SET for w in rest_words):
            continue  # a real tier value is present (parsed by pass 1/2)
        return True  # value present but unparseable -> garbled intent
    return False


def parse_rating(text: str, default: str | None = None) -> str:
    """Heuristically extract a 5-tier rating from prose text.

    Two-pass strategy:
    1. Look for an explicit ``Rating: X`` label (tolerant of markdown bold).
    2. Fall back to the first 5-tier rating word found anywhere in the text.

    Returns a Title-cased rating string. When ``text`` contains rating-like
    content but no 5-tier value parses, returns ``REVIEW_SENTINEL`` instead of
    the default (never a silent tradeable Hold). When ``text`` has no
    rating-like content at all, returns ``default``, or ``"Hold"`` when
    ``default`` is not given.
    """
    value = None
    for line in text.splitlines():
        m = _RATING_LABEL_RE.search(line)
        if m and m.group(1).lower() in _RATING_SET:
            value = m.group(1).capitalize()
            break

    if value is None:
        for line in text.splitlines():
            for word in line.lower().split():
                clean = word.strip("*:.,")
                if clean in _RATING_SET:
                    value = clean.capitalize()
                    break
            if value is not None:
                break

    if value is not None:
        return value

    resolved_default = "Hold" if default is None else default
    if _has_garbled_rating_label(text) and resolved_default.lower() in _RATING_SET:
        return REVIEW_SENTINEL
    return resolved_default
