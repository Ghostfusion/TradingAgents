"""Tests for the shared rating heuristic and the SignalProcessor adapter.

The Portfolio Manager produces a typed PortfolioDecision via structured
output and renders it to markdown that always contains a ``**Rating**: X``
header.  The deterministic heuristic in ``tradingagents.agents.utils.rating``
is therefore sufficient to extract the rating downstream — no second LLM
call is needed — and SignalProcessor is now a thin adapter that delegates
to it.
"""

import pytest

from tradingagents.agents.utils.rating import RATINGS_5_TIER, parse_rating
from tradingagents.graph.signal_processing import SignalProcessor

# ---------------------------------------------------------------------------
# Heuristic parser
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseRating:
    def test_explicit_label_buy(self):
        assert parse_rating("Rating: Buy\nReasoning here.") == "Buy"

    def test_explicit_label_overweight(self):
        assert parse_rating("Rating: Overweight\nDetails.") == "Overweight"

    def test_explicit_label_with_markdown_bold_value(self):
        # Regression: Rating: **Sell** — markdown around the value.
        assert parse_rating("Rating: **Sell**\nExit immediately.") == "Sell"

    def test_explicit_label_with_markdown_bold_label(self):
        assert parse_rating("**Rating**: Underweight\nTrim exposure.") == "Underweight"

    def test_rendered_pm_markdown_shape(self):
        # The exact shape produced by render_pm_decision must always parse.
        text = (
            "**Rating**: Buy\n\n"
            "**Executive Summary**: Enter at $189-192, 6% portfolio cap.\n\n"
            "**Investment Thesis**: AI capex cycle intact; institutional flows constructive."
        )
        assert parse_rating(text) == "Buy"

    def test_explicit_label_wins_over_prose_with_markdown(self):
        text = (
            "The buy thesis is weakened by guidance.\n"
            "Rating: **Sell**\n"
            "Exit before earnings."
        )
        assert parse_rating(text) == "Sell"

    def test_no_rating_returns_default(self):
        assert parse_rating("No clear directional signal at this time.") == "Hold"

    def test_no_rating_custom_default(self):
        assert parse_rating("Plain prose.", default="Underweight") == "Underweight"

    def test_all_five_tiers_recognised(self):
        for r in RATINGS_5_TIER:
            assert parse_rating(f"Rating: {r}") == r

    def test_garbled_rating_surfaces_review_not_hold(self):
        # Upstream TradingAgents 0.4.0 #1170: an unparseable PM rating (e.g.
        # fullwidth-colon label with a non-tier value) must surface REVIEW
        # rather than silently degrade to a tradeable Hold.
        from tradingagents.agents.utils.rating import REVIEW_SENTINEL

        assert parse_rating("Rating：⭐⭐⭐\n待人工审阅") == REVIEW_SENTINEL
        assert parse_rating("**Rating**: Mekanell\nPosition: trim.") == REVIEW_SENTINEL
        # A genuine 5-tier value still parses through the same fullwidth label.
        assert parse_rating("Rating：Hold\nDetails.") == "Hold"
        # A word-only mention of "rating" in ordinary prose is NOT a garbled
        # rating label (no colon-separated value): stay with the default.
        assert parse_rating("The report offers no rating here.") == "Hold"

    def test_garbled_with_non_tradeable_default_stays_default(self):
        # Callers that already pass a non-tradeable fallback keep it; REVIEW is
        # only needed to protect a tradeable-tier fallback.
        assert parse_rating("Rating：⭐⭐⭐", default="n/a") == "n/a"

    def test_garbled_with_custom_tradeable_default_hardened(self):
        # Even an explicit tradeable default is hardened: garbage never
        # coerces to a tier the caller would act on.
        from tradingagents.agents.utils.rating import REVIEW_SENTINEL

        assert parse_rating("Rating：maybe", default="Underweight") == REVIEW_SENTINEL

    def test_signal_processor_surfaces_review(self):
        from tradingagents.agents.utils.rating import REVIEW_SENTINEL

        md = "**Rating**: pending confirmation\nDecision: await clearance."
        assert SignalProcessor().process_signal(md) == REVIEW_SENTINEL


# ---------------------------------------------------------------------------
# SignalProcessor: thin adapter over the heuristic
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSignalProcessor:
    def test_returns_rating_from_pm_markdown(self):
        sp = SignalProcessor()
        md = "**Rating**: Overweight\n\n**Executive Summary**: Build gradually."
        assert sp.process_signal(md) == "Overweight"

    def test_makes_no_llm_calls(self):
        """SignalProcessor must not invoke the LLM it was constructed with —
        the rating is parseable from the rendered PM markdown directly."""
        from unittest.mock import MagicMock

        llm = MagicMock()
        sp = SignalProcessor(llm)
        sp.process_signal("Rating: Buy\nDetails.")
        llm.invoke.assert_not_called()
        llm.with_structured_output.assert_not_called()

    def test_default_when_no_rating_present(self):
        sp = SignalProcessor()
        assert sp.process_signal("Plain prose without a recommendation.") == "Hold"
