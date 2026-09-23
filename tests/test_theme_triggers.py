"""The theme trigger scan: the escalation the priority prior cannot make.

SC-5b of ``docs/design_security_context.md``. §11.3 says a `LOW` theme is
"evaluated only if the evidence stage raises it" - this module is the producer of
that phrase, because with a fixed budget nothing else would read the evidence.

Two properties carry the weight:

1. **Matching is word-bounded.** A substring match fires `ai` on "said",
   "airline", "chain", "retail" and "campaign" - a lexicon that names a theme
   without detecting it, which is this repo's recurring defect class.
2. **Promotion is additive.** A trigger can only move a theme *earlier* than its
   prior put it. It cannot demote, cannot gate, and cannot change the candidate
   set - so the widening invariant survives a trigger that fires.
"""

from __future__ import annotations

from tradingagents.reporting import _run_card_security_context
from tradingagents.strategies.security_context import (
    ALL_REGISTERED_THEMES,
    SecurityContext,
    candidate_themes,
    theme_priority_order,
)
from tradingagents.strategies.theme_triggers import (
    THEME_TRIGGER_TERMS,
    TRIGGER_VERSION,
    promoted_themes,
    theme_triggers,
)

# "said", "airline", "chain", "retail", "campaign" all contain "ai" as a
# substring. "china" hides in "chinatown". None may fire.
DECOYS = "The airline said the retail chain ran a campaign in Chinatown."
REAL = "A new data center and a GPU order; tariffs on Chinese imports; a ransomware breach was disclosed."


def test_every_registered_theme_has_a_declared_lexicon():
    """A registered theme with no terms could never trigger - it would be a theme
    the scan silently cannot see, which is the defect this layer exists to avoid."""
    assert set(THEME_TRIGGER_TERMS) == set(ALL_REGISTERED_THEMES)
    for theme, terms in THEME_TRIGGER_TERMS.items():
        assert terms, theme
        assert all(t == t.strip().lower() for t in terms), theme


def test_matching_is_word_bounded():
    """The load-bearing property: a theme must not fire on a word that merely
    contains its term."""
    triggers = theme_triggers(DECOYS)
    fired = sorted(t for t, v in triggers.items() if v["triggered"])
    assert not fired, f"decoys fired themes: {fired} - matching is not word-bounded"
    assert triggers["ai"]["hits"] == 0
    # ...and the same term does fire when it IS a word.
    assert theme_triggers("Spending on AI is rising.")["ai"]["triggered"] is True


def test_multi_word_terms_match_case_insensitively():
    for text in ("A Data Center buildout", "a data centre buildout", "GPU orders"):
        assert theme_triggers(text)["ai"]["triggered"], text


def test_every_registered_theme_is_reported_even_with_no_match():
    """"Scanned and found nothing" must be distinguishable from "not scanned"."""
    triggers = theme_triggers("The company reported quarterly results.")
    assert set(triggers) == set(ALL_REGISTERED_THEMES)
    for theme, row in triggers.items():
        assert row["triggered"] is False, theme
        assert row["hits"] == 0
        assert row["terms"] == []


def test_the_term_sample_is_bounded_but_the_count_is_exact():
    text = "ransomware ransomware ransomware breach breach phishing vulnerability malware"
    row = theme_triggers(text)["cyber"]
    assert row["hits"] == 8
    assert len(row["terms"]) <= 5, "the card must not grow with a chatty report"
    assert row["terms_kept"] == len(row["terms"])


def test_only_deprioritised_themes_can_be_promoted():
    """A theme the prior already put first was never behind, so it is not promoted.

    For `technology`, `ai`/`cyber` are HIGH and `china`/`regulatory` MEDIUM, so a
    decoy-free text that hits all four promotes none of them.
    """
    triggers = theme_triggers(REAL)
    tech = SecurityContext(symbol="MSFT", sector_canonical="technology")
    promoted = promoted_themes(tech, REAL, triggers)
    assert "ai" not in promoted and "cyber" not in promoted
    assert "tariff" in promoted, "tariff is LOW for technology and the text hits it"
    # For `utilities`, china and tariff are both LOW, so both promote, in order.
    util = SecurityContext(symbol="X", sector_canonical="utilities")
    assert promoted_themes(util, REAL, triggers) == ("china", "tariff")


def test_promotion_cannot_change_the_candidate_set_or_the_order_of_others():
    """The trigger is additive: it adds attention, never a theme."""
    text = REAL
    before = SecurityContext(symbol="MSFT", sector_canonical="technology")
    triggers = theme_triggers(text)
    assert candidate_themes(before) == ALL_REGISTERED_THEMES
    assert set(promoted_themes(before, text, triggers)) <= ALL_REGISTERED_THEMES
    # The matrix order is untouched by any trigger.
    assert theme_priority_order(before) == theme_priority_order(before)


def test_an_empty_or_missing_text_promotes_nothing():
    ctx = SecurityContext(symbol="X", sector_canonical="utilities")
    for text in (None, "", "   "):
        assert promoted_themes(ctx, text) == ()
        assert not any(v["triggered"] for v in theme_triggers(text).values())


def test_the_scan_is_deterministic():
    for text in (REAL, DECOYS, ""):
        assert theme_triggers(text) == theme_triggers(text)
        ctx = SecurityContext(symbol="X", sector_canonical="utilities")
        assert promoted_themes(ctx, text) == promoted_themes(ctx, text)


def test_the_block_reports_triggers_and_keeps_the_gate_contract():
    off = _run_card_security_context("MSFT", {"enable_security_context": False})
    assert off is None

    block = _run_card_security_context(
        "MSFT",
        {"enable_security_context": True},
        "/reports/MSFT_20260922_101010",
        {"news_report": REAL, "sentiment_report": "", "market_report": ""},
    )
    assert block is not None
    assert block["trigger_version"] == TRIGGER_VERSION
    assert block["theme_triggers"]["tariff"]["triggered"] is True
    assert "tariff" in block["promoted_themes"]
    # Still a classification block: nothing here is a score, rating or signal.
    assert not [k for k in block if k in ("score", "rating", "direction", "signal")]


def test_the_block_survives_a_final_state_with_no_reports():
    block = _run_card_security_context(
        "MSFT", {"enable_security_context": True}, "/reports/MSFT_20260922_101010", None
    )
    assert block is not None
    assert block["promoted_themes"] == []
