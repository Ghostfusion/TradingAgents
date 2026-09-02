"""Tests for strategy-skill overlays (DSA phase C; design §6-3).

- YAML load + schema reject on missing name
- regime-from-opinion thresholds (>=70 / <=30 / 35-65 / fail-open)
- router precedence (user-requested > regime > priority-default), cap
- score adjustments bounded +/-20 (advisory)
"""

import pytest

from tradingagents.strategies import skills as sk

pytestmark = pytest.mark.timeout(30)


class TestParseAndLoad:
    def test_parse_minimal_skill(self):
        s = sk.parse_skill({"name": "x", "instructions": "do X"})
        assert s is not None and s.name == "x" and s.category == "framework"
        assert s.default_priority == 100 and s.bounded_adjustments == {}

    def test_parse_missing_name_none(self):
        assert sk.parse_skill({"instructions": "no name"}) is None
        assert sk.parse_skill({}) is None
        assert sk.parse_skill(None) is None

    def test_load_bundled(self):
        loaded = sk.load_skills(sk._DEFAULT_SKILL_DIR)
        assert set(loaded) >= {"ma_bull_trend", "volume_breakout", "shrink_pullback"}
        assert loaded["volume_breakout"].score_adjustments["breakout"] == 12.0

    def test_custom_dir_overrides(self, tmp_path):
        (tmp_path / "ma_bull_trend.yaml").write_text(
            "name: ma_bull_trend\ndisplay_name: Custom\ninstructions: hi\n", encoding="utf-8")
        loaded = sk.load_skills(str(tmp_path))
        assert loaded["ma_bull_trend"].display_name == "Custom"


class TestRegimeFromOpinion:
    def test_thresholds(self):
        assert sk.regime_from_opinion({"ma_alignment": "bullish", "trend_score": 80}) == "trending_up"
        assert sk.regime_from_opinion({"ma_alignment": "bearish", "trend_score": 10}) == "trending_down"
        assert sk.regime_from_opinion({"ma_alignment": "neutral", "trend_score": 50}) == "sideways"
        assert sk.regime_from_opinion({"ma_alignment": "mixed", "trend_score": 40}) == "sideways"

    def test_fail_open(self):
        assert sk.regime_from_opinion(None) is None
        assert sk.regime_from_opinion({}) is None
        assert sk.regime_from_opinion({"ma_alignment": "bullish"}) is None  # no score
        assert sk.regime_from_opinion({"trend_score": "abc"}) is None


class TestRouter:
    def test_user_requested_wins(self):
        loaded = sk.load_skills(sk._DEFAULT_SKILL_DIR)
        out = sk.select_skills(loaded, "trending_up", requested=["shrink_pullback"])
        assert out == ["shrink_pullback"]

    def test_regime_match(self):
        loaded = sk.load_skills(sk._DEFAULT_SKILL_DIR)
        assert sk.select_skills(loaded, "trending_up", max_count=5)[0] == "ma_bull_trend"

    def test_priority_fallback(self):
        loaded = sk.load_skills(sk._DEFAULT_SKILL_DIR)
        out = sk.select_skills(loaded, "volatile", max_count=5)
        assert out  # some deterministic default order

    def test_cap(self):
        loaded = sk.load_skills(sk._DEFAULT_SKILL_DIR)
        out = sk.select_skills(loaded, "trending_up", max_count=1)
        assert len(out) == 1

    def test_empty_skills(self):
        assert sk.select_skills({}, "trending_up") == []


class TestAdjustments:
    def test_bounded(self):
        s = sk.parse_skill({"name": "x", "score_adjustments": {"a": 50.0, "b": -30.0, "c": 5.0}})
        assert s is not None
        adj = s.bounded_adjustments
        assert adj["a"] == 20.0 and adj["b"] == -20.0 and adj["c"] == 5.0

    def test_non_numeric_dropped(self):
        s = sk.parse_skill({"name": "x", "score_adjustments": {"a": "big"}})
        assert s is not None and s.bounded_adjustments == {}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

