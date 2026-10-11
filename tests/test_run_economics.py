"""The per-run quality x cost join: cap-bound cost, read-not-derived quality."""

import pytest

from tradingagents.strategies.run_economics import run_economics

pytestmark = pytest.mark.timeout(30)


def _card(leg_cost=0.25, leg_model="m1", unpriced=False):
    legs = {
        "quick_think_llm": {
            "model": leg_model,
            "rate_usd_per_1m": {"in": 1.0, "out": 2.0},
            "max_output_leg_usd": None if unpriced else leg_cost,
        }
    }
    return {"ticker": "AAA", "generated": "2026-01-01T00:00:00+00:00", "llm_cost_est": legs}


def _flags(stems=("market", "news"), flagged=("news",), prose_flagged=()):
    payload = {
        "verification": {s: {"overall": "FLAG" if s in flagged else "PASS"} for s in stems},
        "prose": {
            "overall": "FLAG" if prose_flagged else "PASS",
            "reports": {p: {"overall": "FLAG"} for p in prose_flagged},
        },
    }
    return payload


def test_the_join_reports_the_cap_bound_and_the_flagged_blocks():
    out = run_economics(_card(leg_cost=0.25), verify_flags=_flags())
    assert out["available"] is True
    assert out["cost_upper_usd"] == pytest.approx(0.25)
    assert out["quality"]["flags_count"] == 1
    assert out["quality"]["flagged_stems"] == ["news"]
    assert out["flags_per_usd"] == pytest.approx(4.0)
    assert out["depth"] is None and "research-depth knob" in out["depth_unavailable"]
    assert "UPPER BOUND" in out["caveat"]


def test_an_unpriced_leg_is_named_never_zeroed():
    out = run_economics(_card(unpriced=True), verify_flags=_flags())
    assert out["cost_upper_usd"] is None
    assert out["cost_unpriced_legs"] == ["quick_think_llm"]
    assert out["flags_per_usd"] is None


def test_no_verifier_run_is_not_a_perfect_score():
    out = run_economics(_card(), verify_flags=None)
    assert out["quality"] is None
    assert out["flags_per_usd"] is None
    assert out["available"] is True  # the cost leg still measures


def test_prose_flags_count_beside_the_stems():
    out = run_economics(_card(), verify_flags=_flags(prose_flagged=("2_research/bull.md",)))
    assert out["quality"]["flags_count"] == 2
    assert out["quality"]["flagged_prose"] == ["2_research/bull.md"]


def test_a_zero_bound_has_no_cost_efficiency():
    out = run_economics(_card(leg_cost=0.0), verify_flags=_flags())
    assert out["cost_upper_usd"] == 0.0
    assert out["flags_per_usd"] is None  # not inf, not a division
    assert "zero denominator" in out["basis"]


def test_an_empty_card_refuses_with_the_reason():
    out = run_economics(None)
    assert out["available"] is False
    assert out["unavailable"] == "no run_card payload"
