"""P0-8: an unavailable/failed decision must never become a tradeable action.

``parse_rating`` used to fall back to ``"Hold"`` when nothing parsed, so a
degenerate PM response (empty text, an "unavailable" notice) was stored in the
memory log and acted on as a genuine tradeable Hold. Nothing-parseable now
returns the ``REVIEW`` sentinel and the memory log refuses to record it.
"""

from __future__ import annotations

import pytest

from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.agents.utils.rating import (
    RATINGS_5_TIER,
    REVIEW_SENTINEL,
    parse_rating,
)
from tradingagents.graph.signal_processing import SignalProcessor

TRADEABLE_RATINGS = set(RATINGS_5_TIER)

UNAVAILABLE_DECISIONS = [
    "",
    "**Decision**: unavailable - the model returned an incomplete response.",
    "Decision unavailable: the model call timed out before a verdict.",
    "No clear directional signal at this time.",
]

UNAVAILABLE_PM_RESPONSE = (
    "**Decision**: unavailable - the model returned an incomplete response."
)


@pytest.mark.unit
class TestUnavailableDecisionIsNotTradeable:
    @pytest.mark.parametrize("text", UNAVAILABLE_DECISIONS)
    def test_no_rating_found_is_not_a_tradeable_tier(self, text):
        assert parse_rating(text) not in TRADEABLE_RATINGS

    def test_unavailable_notice_yields_review_sentinel(self):
        assert parse_rating(UNAVAILABLE_PM_RESPONSE) == REVIEW_SENTINEL

    def test_signal_processor_does_not_emit_a_tradeable_rating(self):
        assert SignalProcessor().process_signal(UNAVAILABLE_PM_RESPONSE) not in TRADEABLE_RATINGS

    def test_genuine_hold_still_parses_as_hold(self):
        assert parse_rating("**Rating**: Hold\nMaintain the position.") == "Hold"
        assert SignalProcessor().process_signal("**Rating**: Hold") == "Hold"

    def test_garbled_label_still_yields_review_sentinel(self):
        assert parse_rating("Rating：⭐⭐⭐\n待人工审阅") == REVIEW_SENTINEL
        assert parse_rating("**Rating**: Mekanell\nPosition: trim.") == REVIEW_SENTINEL

    def test_explicit_default_is_still_honoured(self):
        # Only the *implicit* tradeable fallback was hardened: a caller that
        # deliberately passes a fallback keeps it.
        assert parse_rating("Plain prose.", default="n/a") == "n/a"
        assert parse_rating("Plain prose.", default="Underweight") == "Underweight"


@pytest.mark.unit
class TestMemoryLogUnavailableDecision:
    def _make_log(self, tmp_path):
        return TradingMemoryLog({"memory_log_path": str(tmp_path / "trading_memory.md")})

    def test_unavailable_decision_is_not_recorded(self, tmp_path):
        log = self._make_log(tmp_path)
        log.store_decision("NVDA", "2026-01-10", UNAVAILABLE_PM_RESPONSE)
        # Nothing pending -> get_pending_entries() (the reflection feed) and the
        # decision-resolution path can never treat this as a tradeable Hold.
        assert log.load_entries() == []
        assert log.get_pending_entries() == []

    def test_genuine_hold_is_still_recorded_as_tradeable(self, tmp_path):
        log = self._make_log(tmp_path)
        log.store_decision("NVDA", "2026-01-10", "**Rating**: Hold\nMaintain the position.")
        entries = log.load_entries()
        assert [e["rating"] for e in entries] == ["Hold"]
        assert entries[0]["pending"] is True
        assert len(log.get_pending_entries()) == 1
