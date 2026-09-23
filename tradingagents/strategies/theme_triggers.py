"""The cheap theme trigger scan - the escalation the priority prior cannot make.

Design: ``docs/design_security_context.md`` §11.3 (SC-5b). The priority matrix
orders evidence-gathering effort, and it can only ever *add* attention: a `LOW`
theme stays a candidate but is evaluated last. That leaves a gap the design named
and did not fill -

    LOW -> evaluate only if the evidence stage raises it

- because with a fixed budget nothing would ever read the evidence that should
raise it. This module is the producer of that phrase.

**What this is not.** It is not an overlay, not an analysis and not a judgement.
It scans text the run *already holds* for a small declared lexicon and reports
which themes were mentioned. The overlay framework (the parent design's §18
registry) does not exist yet, so nothing consumes a promotion as a decision: the
result is recorded in the run card, and that is all. It cannot demote a theme and
cannot gate - it only ever moves a theme *earlier* than its prior put it, which is
the same direction as the widening invariant.

**No new fetch, no LLM.** The text is the run's own analyst reports.

**Matching is word-bounded, and that is load-bearing.** A substring match would
fire `ai` on "said", "airline", "chain" and "retail" - the repo's recurring
"a name that promises more than it measures" defect, in a lexicon. Every term is
matched as a whole word (or whole phrase for multi-word terms), case-insensitively.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from tradingagents.strategies.security_context import (
    ALL_REGISTERED_THEMES,
    HIGH,
    LOW,
    MEDIUM,
    THEME_PRIORITY_MATRIX,
    SecurityContext,
)

#: The declared lexicon, versioned like every other prior in this repo.
#:
#: Deliberately small and literal: these are *cheap detectors*, and a term earns
#: its place by being a phrase a human would actually use to name the theme. It is
#: declared policy - revisited by bumping :data:`TRIGGER_VERSION`, never by
#: drifting term-by-term.
TRIGGER_VERSION = "2026-09-22.1"

THEME_TRIGGER_TERMS: dict[str, tuple[str, ...]] = {
    "ai": (
        "artificial intelligence",
        "generative ai",
        "machine learning",
        "large language model",
        "data center",
        "data centre",
        "gpu",
        "inference",
        "ai",
    ),
    "tariff": (
        "tariff",
        "tariffs",
        "import duty",
        "import duties",
        "trade barrier",
        "trade barriers",
        "trade war",
        "section 301",
        "section 232",
    ),
    "china": (
        "china",
        "chinese",
        "beijing",
        "prc",
        "hong kong",
        "export control",
        "export controls",
        "entity list",
    ),
    "regulatory": (
        "regulator",
        "regulators",
        "regulatory",
        "regulation",
        "regulations",
        "antitrust",
        "compliance order",
        "consent decree",
        "fine",
        "sanction",
        "sanctions",
    ),
    "commodity": (
        "commodity",
        "commodities",
        "crude",
        "brent",
        "wti",
        "natural gas",
        "copper",
        "aluminium",
        "aluminum",
        "steel",
        "lithium",
        "spot price",
    ),
    "cyber": (
        "cyber",
        "cyberattack",
        "cyber attack",
        "ransomware",
        "data breach",
        "breach",
        "vulnerability",
        "zero-day",
        "phishing",
        "malware",
    ),
}

#: How many matched terms to keep per theme in the report. The count is exact; the
#: list is a bounded sample, so a chatty report cannot bloat the card.
_MAX_TERMS_KEPT = 5


def _bounded_pattern(term: str) -> re.Pattern[str]:
    """A word-bounded, case-insensitive pattern for one term.

    ``\\b`` on both ends is what stops ``ai`` matching ``said`` and ``chain``.
    """
    return re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)


_PATTERNS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    theme: tuple((t, _bounded_pattern(t)) for t in terms)
    for theme, terms in THEME_TRIGGER_TERMS.items()
}


def theme_triggers(text: str | None) -> dict[str, dict[str, Any]]:
    """Which registered themes the text mentions, and with which terms.

    Returns one entry per REGISTERED theme - including the themes with no match -
    so a reader can tell "scanned and found nothing" from "not scanned", which is
    the distinction the rest of this layer is careful about.

    ``hits`` counts every occurrence; ``terms`` keeps a bounded sample of the
    matched terms so the report stays small and a reader can audit the match.
    """
    blob = text or ""
    out: dict[str, dict[str, Any]] = {}
    for theme in sorted(ALL_REGISTERED_THEMES):
        matched: list[str] = []
        hits = 0
        for term, pattern in _PATTERNS.get(theme, ()):
            found = len(pattern.findall(blob))
            if found:
                hits += found
                if len(matched) < _MAX_TERMS_KEPT:
                    matched.append(term)
        out[theme] = {
            "triggered": hits > 0,
            "hits": hits,
            "terms": matched,
            "terms_kept": len(matched),
        }
    return out


def promoted_themes(
    context: SecurityContext | None,
    text: str | None,
    triggers: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[str, ...]:
    """Themes a trigger scan moves AHEAD of the prior that put them last.

    Only themes the prior deprioritised can be promoted - ``LOW``, or a theme with
    no prior at all because the sector is unclassified. That is the whole point of
    §11.3's third line: the prior orders effort, and this is what stops a `LOW`
    theme from being unreachable in a budget-constrained run.

    Promotion is **additive by construction**: a theme that is already ``HIGH`` or
    ``MEDIUM`` is not "promoted" (it was never behind), and nothing here can move a
    theme later. Returns theme ids in priority order, then id, so the result is
    deterministic.
    """
    if triggers is None:
        triggers = theme_triggers(text)
    sector = ((context.sector_canonical if context is not None else None) or "").strip().lower()
    cells = THEME_PRIORITY_MATRIX.get(sector, {})
    ranked = {
        HIGH: 0,
        MEDIUM: 1,
        LOW: 2,
    }
    behind = [t for t in ALL_REGISTERED_THEMES if ranked.get(cells.get(t, ""), 2) >= 2]
    fired = [t for t in behind if triggers.get(t, {}).get("triggered")]
    cells_order = {t: ranked.get(cells.get(t, ""), 2) for t in fired}
    return tuple(sorted(fired, key=lambda t: (cells_order[t], t)))
