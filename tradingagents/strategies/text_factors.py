"""Disclosure text factors: tone, readability, and cross-document divergence.

Docs: ``docs/design_quant_formulas_research_round2.md`` item N6;
``docs/implementation_plan_quant_formula_additions.md`` phase Q6.

Why this exists: the analysis path reads filings, call transcripts and news, but
the only text signal it carries is a model/vendor sentiment number. A
dictionary-based tone count and a readability measure are *deterministic and
reproducible*, so they can (a) sit beside the LLM narrative read as a second,
non-model opinion and (b) give the report verifier something to check a
"management sounded confident" claim against.

Provenance: Loughran & McDonald (2011), *When Is a Liability Not a Liability?*,
Journal of Finance 66(1) - the finance-specific word lists that replaced generic
sentiment dictionaries; and the 2025 disclosure work finding that tone
*divergence* between earnings calls and 10-K/MD&A predicts returns (temporary),
while complexity/readability divergence is more persistent.

Honesty rules baked into the return shapes:
  * the dictionary version and the word counts are ALWAYS reported - no tone
    verdict without its counts;
  * a passage with no dictionary hits is reported as ``zero_hits`` with
    ``tone=None``, never as neutral (0.0 reads as "measured, balanced" when it
    only means "no signal found");
  * the two divergence channels are returned separately because the literature
    treats their persistence differently.

Pure functions over caller-supplied text: no vendor, no I/O, no randomness.
"""

from __future__ import annotations

import re

__all__ = [
    "lm_tone",
    "readability",
    "divergence",
    "DICTIONARY_VERSION",
    "NEGATIVE_WORDS",
    "POSITIVE_WORDS",
    "UNCERTAINTY_WORDS",
    "LITIGIOUS_WORDS",
]

#: Version tag for the word lists below. Bump it whenever the lists change, so a
#: stored tone count can be read back against the dictionary that produced it.
DICTIONARY_VERSION = "lm-seed-v1"


def _lexicon(blob: str) -> frozenset[str]:
    """Whitespace-separated word blob -> frozenset (keeps the lists readable)."""
    return frozenset(blob.split())

# A reduced Loughran-McDonald-style seed set. The published lists number in the
# thousands; this seed carries the highest-signal finance terms and is honest
# about being reduced (``basis`` names it), because the consumer's job is a
# reproducible second opinion, not a replication of the full dictionary. Pass a
# larger dictionary to the counters in future without changing this API.
NEGATIVE_WORDS = _lexicon(
    """
    abandon abandoned abandonment adverse adversely against allegation allegations
    antitrust breach breached breaches claim claims complaint complaints concern
    concerns default defaulted deficiency deficit delay delayed delinquent
    deteriorate deteriorated deterioration difficulty disclose disclosed disclosing
    disclosure downturn drop dropped declines declining declined decline defect
    defective defer deferred deficiency delinquencies disruption disruptions
    doubt doubtful downsizing fail failed failing fails failure failures fraud
    fraudulent harm harmed harming impairment impairments inadequate insolvency
    insolvent investigation investigations lawsuits litigation loss losses lost
    misstatement negative negatively penalty penalized probe probes recall recalls
    restatement restatements restated restructuring risk risks risky sanction
    sanctions shortfall shortfalls slowdown sluggish subpoena terminated termination
    unprofitable volatile volatility weak weakened weakness weaknesses writedown
    writedowns
    """
)

POSITIVE_WORDS = _lexicon(
    """
    achieve achieved achievement advantageous benefit benefited benefits best boost
    boosted confident confidence deliver delivered delivering dependable enhance
    enhanced enhancement exceeded exceeds excellent exceptional expansive favorable
    favorably gain gained gaining gains good great growth growths improve improved
    improvement improvements improving increase increased increases innovative
    leader leading opportunity opportunities outperform outperformed outperforming
    profitable profit profitability progress progresses record strength strengthen
    strengthened strong stronger success successful successfully superior upside
    """
)

UNCERTAINTY_WORDS = _lexicon(
    """
    anticipate anticipated approximately assume assumed assumption believe could
    depending estimate estimated estimates expect expected expects fluctuation
    fluctuate may maybe might possibly potential potentially predict predicted
    predicting preliminary preliminary probably projection projections roughly
    seek seeks seeking should suggest suggests uncertain uncertainty unclear
    unanticipated unknown unpredictable vary varies various
    """
)

LITIGIOUS_WORDS = _lexicon(
    """
    arbitration attorney attorneys claimant claimants court courts damages decree
    defendant defendants deposition discovery evidence injunction judge judgment
    judicial jurisdiction jury litigate litigating plaintiff plaintiffs ruling
    settle settled settlement settlements subpoena testify testimony trial verdict
    """
)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_SENTENCE_RE = re.compile(r"[.!?]+")
_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+")


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]


def lm_tone(text: str) -> dict | None:
    """Loughran-McDonald-style tone counts over ``text``.

    Returns ``{"negative", "positive", "uncertainty", "litigious", "hits",
    "words", "tone", "zero_hits", "dictionary", "basis"}`` or ``None`` for
    empty/blank text.

    ``tone = (positive - negative) / words`` - an LM-style polarity in roughly
    [-1, 1]. It is ``None`` when the text contains no dictionary hit at all
    (``zero_hits=True``): absence of signal is not neutrality, and rendering it
    as 0.0 would read as "measured, balanced".
    """
    if not text or not text.strip():
        return None
    words = _words(text)
    if not words:
        return None
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    unc = sum(1 for w in words if w in UNCERTAINTY_WORDS)
    lit = sum(1 for w in words if w in LITIGIOUS_WORDS)
    hits = neg + pos + unc + lit
    return {
        "negative": neg,
        "positive": pos,
        "uncertainty": unc,
        "litigious": lit,
        "hits": hits,
        "words": len(words),
        "tone": None if hits == 0 else (pos - neg) / len(words),
        "zero_hits": hits == 0,
        "dictionary": DICTIONARY_VERSION,
        "basis": f"{DICTIONARY_VERSION}; counts over {len(words)} words",
    }


def _syllables(word: str) -> int:
    """Deterministic vowel-group syllable estimate (reads aloud approx.)."""
    w = word.lower().strip("'\"")
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    groups = len(_VOWEL_GROUP_RE.findall(w))
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")):
        groups -= 1
    return max(1, groups)


def readability(text: str) -> dict | None:
    """Flesch reading ease, Flesch-Kincaid grade and Gunning fog for ``text``.

    Returns ``{"reading_ease", "fk_grade", "fog", "words", "sentences",
    "syllables", "basis"}`` or ``None`` for empty/blank text. A text with no
    sentence terminator is treated as one sentence (documented, not guessed at).
    """
    if not text or not text.strip():
        return None
    words = _words(text)
    if not words:
        return None
    sentences = max(1, len(_SENTENCE_RE.findall(text)))
    syllables = sum(_syllables(w) for w in words)
    wps = len(words) / sentences
    spw = syllables / len(words)
    complex_words = sum(1 for w in words if _syllables(w) >= 3)
    return {
        "reading_ease": 206.835 - 1.015 * wps - 84.6 * spw,
        "fk_grade": 0.39 * wps + 11.8 * spw - 15.59,
        "fog": 0.4 * (wps + 100.0 * complex_words / len(words)),
        "words": len(words),
        "sentences": sentences,
        "syllables": syllables,
        "basis": f"{len(words)} words / {sentences} sentences; syllable heuristic",
    }


def divergence(a_text: str, b_text: str) -> dict | None:
    """Tone and complexity divergence between two documents of the same period.

    Intended for a pair the engine already holds for one firm-period (e.g. an
    earnings-call transcript vs the 10-K/MD&A). Returns ``{"tone_gap",
    "complexity_gap", "tone_direction", "complexity_direction", "a", "b",
    "basis"}`` or ``None`` when either side is unusable or either tone is
    ``None`` (a gap needs two measured tones - one side silently missing a
    signal must not read as "the two documents agree").

    The two channels are separate on purpose: the 2025 disclosure evidence finds
    tone divergence's return predictability temporary while the complexity
    channel persists. ``complexity_gap`` is the fog-index difference;
    positive ``tone_gap`` means the first document reads more positive.
    """
    ta = lm_tone(a_text)
    tb = lm_tone(b_text)
    ra = readability(a_text)
    rb = readability(b_text)
    if not ta or not tb or not ra or not rb:
        return None
    if ta["tone"] is None or tb["tone"] is None:
        return None
    tone_gap = ta["tone"] - tb["tone"]
    complexity_gap = ra["fog"] - rb["fog"]
    return {
        "tone_gap": tone_gap,
        "complexity_gap": complexity_gap,
        "tone_direction": "a_more_positive" if tone_gap > 0 else ("b_more_positive" if tone_gap < 0 else "equal"),
        "complexity_direction": "a_more_complex" if complexity_gap > 0 else ("b_more_complex" if complexity_gap < 0 else "equal"),
        "a": {"tone": ta["tone"], "fog": ra["fog"], "words": ta["words"]},
        "b": {"tone": tb["tone"], "fog": rb["fog"], "words": tb["words"]},
        "basis": f"fog delta; tones from {ta['dictionary']}",
    }
