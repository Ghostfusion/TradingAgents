"""Hermetic tests for the research_decision.json execution contract emitter.

The artifact is the ONLY input contract of the TradingExecution daemon (Phase
A): it must be hash-pinned, deterministic, and carry nulls for anything
unproducible (fail closed). No network.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from tradingagents.reporting import write_research_decision

pytestmark = pytest.mark.timeout(120)


def _final_state(**overrides):
    fs = {
        "pm_decision": {
            "rating": "Underweight",
            "confidence": 0.8,
            "data_quality": "fresh",
            "guardrail_reason": None,
            "investment_thesis": "Bear debate won.",
            "executive_summary": "Reduce on strength.",
        },
        "risk_gate": {"verdict": "PASS", "reasons": []},
        "position_contract": {"stop_loss": 429.0, "target": 460.0, "size_pct": 0.0242},
    }
    fs.update(overrides)
    return fs


def _read(tmp_path):
    return json.loads((tmp_path / "research_decision.json").read_text(encoding="utf-8"))


def test_emits_hash_pinned_contract(tmp_path):
    write_research_decision(_final_state(), "avgo", tmp_path)
    doc = _read(tmp_path)
    assert doc["ticker"] == "AVGO"
    assert doc["position"]["stop_loss"] == 429.0
    assert doc["position"]["size_pct_book"] == 0.0242
    assert doc["data_quality"] == "fresh"
    body = {k: v for k, v in doc.items() if k != "decision_hash"}
    expected = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    assert doc["decision_hash"] == expected


def test_unproducible_fields_are_null(tmp_path):
    write_research_decision(_final_state(), "avgo", tmp_path)
    doc = _read(tmp_path)
    assert doc["direction"] is None
    assert doc["recommended_allocation_pct"] is None
    assert doc["position"]["target_notional"] is None
    # invalidations are produced from the contract levels (>= 1 by
    # construction: stop breach / degraded data quality / manual reassessment),
    # never left as an empty placeholder.
    assert doc["invalidations"] and any("stop_loss" in s for s in doc["invalidations"])


def test_evidence_fields_come_from_the_forced_tool_leaves(tmp_path):
    """data_quality/sources are derived from the evidence that actually ran;
    the artifact is the executor's only input, so placeholders are unusable."""
    fs = _final_state()
    fs["pm_decision"].pop("data_quality")
    fs["tool_evidence"] = {
        "market": [
            {"tool": "get_swing_exits", "status": "ok"},
            {"tool": "get_orderflow_read", "status": "ok"},
        ],
        "news": [{"tool": "get_news", "status": "timeout"}],
    }
    write_research_decision(fs, "nvda", tmp_path)
    doc = _read(tmp_path)
    assert doc["data_quality"] == "partial"
    assert doc["disclosure"]["sources_used"] == ["get_orderflow_read", "get_swing_exits"]
    assert doc["disclosure"]["sources_empty"] == ["get_news"]


def test_all_ok_evidence_is_fresh_quality(tmp_path):
    fs = _final_state()
    fs["pm_decision"].pop("data_quality")
    fs["tool_evidence"] = {"market": [{"tool": "get_swing_exits", "status": "ok"}]}
    write_research_decision(fs, "nvda", tmp_path)
    assert _read(tmp_path)["data_quality"] == "fresh"


def test_risk_context_sets_the_binding_constraint(tmp_path):
    fs = _final_state()
    fs["risk_context"] = {"book_drawdown": 0.2021, "drawdown_limit": 0.10}
    write_research_decision(fs, "nvda", tmp_path)
    doc = _read(tmp_path)
    assert doc["binding_constraint"] == "book_drawdown"
    assert doc["action_basis"] == "risk_reduction"
    assert "20.21%" in doc["binding_reason"]


def test_rating_from_dict_contract(tmp_path):
    fs = _final_state()
    fs["position_contract"] = "stop 429.0 | target 460.0 | size 2.42%"
    write_research_decision(fs, "avgo", tmp_path)
    doc = _read(tmp_path)
    assert doc["position"]["stop_loss"] == 429.0
    assert doc["position"]["take_profit"] == 460.0
    assert doc["position"]["size_pct_book"] == pytest.approx(0.0242)


def test_guardrail_and_risk_gate_carried(tmp_path):
    fs = _final_state()
    fs["pm_decision"]["guardrail_reason"] = "risk-cap: high-severity risk caps at Hold"
    fs["risk_gate"]["verdict"] = "WARN"
    fs["risk_gate"]["reasons"] = ["liquidity CAUTION"]
    write_research_decision(fs, "avgo", tmp_path)
    doc = _read(tmp_path)
    assert doc["guardrail_reason"].startswith("risk-cap")
    assert doc["risk_gate"]["verdict"] == "WARN"
    assert doc["risk_gate"]["reasons"] == ["liquidity CAUTION"]


def test_missing_pm_defaults_unknown_data_quality(tmp_path):
    write_research_decision({}, "nope", tmp_path)
    doc = _read(tmp_path)
    assert doc["data_quality"] == "unknown"  # daemon fails closed on this
    assert doc["rating"] is None


def test_emitter_survives_the_gatherers_run_level_evidence_keys(tmp_path):
    """`_model_pool` is a mapping of tool-name lists, not a leaf list.

    Regression (2026-09-15): the source walk read every ``tool_evidence``
    value as a leaf list, so ``_model_pool``'s name strings raised
    ``AttributeError: 'str' object has no attribute 'get'``, and
    ``write_report_tree`` suppresses exactly that exception - so no run that
    gathered evidence ever wrote ``research_decision.json``, the executor
    daemon's only input contract. The walk now matches on shape: a value that
    is not a list of dicts is not a leaf list: the reserved keys are skipped
    wholesale, and a row without a ``tool`` key is still skipped row-wise.
    """
    fs = _final_state(
        tool_evidence={
            "market": [{"tool": "get_indicators", "status": "ok"}],
            "news": [{"tool": "get_news", "status": "error"}],
            "_model_pool": {
                "market": ["get_indicators", "get_swing_set"],
                "news": ["get_news"],
            },
            "_rendered_block": [{"analyst": "market", "block": "..."}],
            "_symmetry": [{"basis": "2 pair(s)", "differs_on": []}],
        }
    )
    # The PM's own declaration wins, so clear it and let the evidence decide.
    fs["pm_decision"]["data_quality"] = None
    write_research_decision(fs, "avgo", tmp_path)  # must not raise
    doc = _read(tmp_path)
    assert doc["disclosure"]["sources_used"] == ["get_indicators"]
    assert doc["disclosure"]["sources_empty"] == ["get_news"]
    assert doc["data_quality"] == "partial"
