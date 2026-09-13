"""Acceptance tests T1-T6 for the research -> execution envelope (v1.1.0).

Hermetic: no network, no execution repo import. The vendored schema is the
published interface (a copy by design - the two repos share a contract, not
code), so a change on either side fails here rather than in a live run.

Authority: ``docs/execution_v1_emitter_plan.md`` sections 2 and 4.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from tradingagents import execution_contract as ec
from tradingagents.reporting import write_research_decision

pytestmark = pytest.mark.timeout(120)

_REPO = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (_REPO / "contracts" / "research_decision.v1.schema.json").read_text(encoding="utf-8")
)


# --------------------------------------------------------------------------
# T1 - the artifact validates against the vendored published contract
# --------------------------------------------------------------------------
def _type_ok(value: object, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    raise AssertionError(f"validator does not implement {name!r}")  # schema drift caught here


def _schema_problems(doc: dict, schema: dict) -> list[str]:
    """The subset of JSON Schema the vendored contract actually uses.

    Hand-rolled on purpose: this repo does not depend on ``jsonschema``, and an
    unimplemented keyword raises rather than silently passing.
    """
    problems: list[str] = []
    props = schema.get("properties") or {}
    for key in schema.get("required") or []:
        if key not in doc:
            problems.append(f"missing required key {key!r}")
    for key, spec in props.items():
        if key not in doc:
            continue
        value = doc[key]
        declared = spec.get("type")
        names = [declared] if isinstance(declared, str) else list(declared or [])
        if names and not any(_type_ok(value, name) for name in names):
            problems.append(f"{key}: {value!r} is not {names}")
            continue
        if value is None:
            continue
        if "enum" in spec and value not in spec["enum"]:
            problems.append(f"{key}: {value!r} is outside {spec['enum']}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in spec and value < spec["minimum"]:
                problems.append(f"{key}: {value} < {spec['minimum']}")
            if "maximum" in spec and value > spec["maximum"]:
                problems.append(f"{key}: {value} > {spec['maximum']}")
        if isinstance(value, str):
            if "minLength" in spec and len(value) < spec["minLength"]:
                problems.append(f"{key}: shorter than {spec['minLength']}")
            if "pattern" in spec and not re.search(spec["pattern"], value):
                problems.append(f"{key}: {value!r} does not match {spec['pattern']}")
            if spec.get("format") == "date-time":
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is None:
                    problems.append(f"{key}: {value!r} carries no UTC offset")
            elif spec.get("format") == "date":
                date.fromisoformat(value)
        if isinstance(value, dict) and spec.get("required"):
            for sub in spec["required"]:
                if sub not in value:
                    problems.append(f"{key}.{sub} is required")
    for condition, keys in (schema.get("x-required-when") or {}).items():
        target, _, floor = condition.partition(">=")
        if target != "schema_version":
            raise AssertionError(f"validator does not implement condition {condition!r}")
        floor_parts = tuple(int(p) for p in floor.split("."))
        if ec.parse_version(doc) >= floor_parts:
            for key in keys:
                if doc.get(key) is None:
                    problems.append(f"{key} is required from version {floor}")
    return problems


def _emit(tmp_path, **fs_overrides):
    Path(tmp_path).mkdir(parents=True, exist_ok=True)
    fs = {
        "pm_decision": {
            "rating": "Underweight",
            "confidence": 0.8,
            "data_quality": "fresh",
            "investment_thesis": "Bear case won.",
            "executive_summary": "Reduce on strength.",
        },
        "risk_gate": {"verdict": "PASS", "reasons": []},
        "position_contract": {"stop_loss": 429.0, "target": 460.0, "size_pct": 0.0242},
    }
    fs.update(fs_overrides)
    write_research_decision(fs, "avgo", tmp_path)
    return json.loads((tmp_path / "research_decision.json").read_text(encoding="utf-8"))


def test_the_artifact_validates_against_the_vendored_contract(tmp_path):
    doc = _emit(tmp_path)

    assert _schema_problems(doc, SCHEMA) == []
    assert doc["schema_version"] == ec.SCHEMA_VERSION


def test_the_vendored_copy_matches_the_executors_published_schema():
    """Drift guard: refresh the copy when the executor's contract changes.

    Skipped when the sibling repo is absent (this repo must stand alone).
    """
    published = _REPO.parent / "TradingExecution" / "contracts" / "research_decision.v1.schema.json"
    if not published.exists():
        pytest.skip("execution repo not present; the copy cannot be diffed")
    assert json.loads(published.read_text(encoding="utf-8")) == SCHEMA


# --------------------------------------------------------------------------
# T2 - both hashes recompute (and the check can fail)
# --------------------------------------------------------------------------
def test_the_two_hashes_recompute_from_the_body(tmp_path):
    doc = _emit(tmp_path)

    body = {k: v for k, v in doc.items() if k not in ("artifact_sha256", "decision_hash")}
    assert doc["artifact_sha256"] == hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    with_artifact = {k: v for k, v in doc.items() if k != "decision_hash"}
    assert doc["decision_hash"] == "sha256:" + hashlib.sha256(
        json.dumps(with_artifact, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    assert ec.seal_problems(doc) == []


def test_editing_a_sealed_artifact_is_detected(tmp_path):
    """The executor recomputes the body; a post-edit must not look valid."""
    doc = _emit(tmp_path)
    doc["rating"] = "Overweight"

    problems = ec.seal_problems(doc)
    assert any("artifact_sha256" in p for p in problems)
    assert any("decision_hash" in p for p in problems)


# --------------------------------------------------------------------------
# T3 - the expiry is offset-aware and covers the next session
# --------------------------------------------------------------------------
def test_the_expiry_is_aware_and_after_the_production_stamp(tmp_path):
    doc = _emit(tmp_path)
    produced = datetime.fromisoformat(doc["produced_at"])
    expires = datetime.fromisoformat(doc["expires_at"])

    assert produced.utcoffset() is not None and expires.utcoffset() is not None
    assert expires > produced


def test_the_expiry_covers_the_next_session_and_skips_the_weekend():
    # 2026-09-10 is a Thursday: the next session closes Friday 20:00 ET.
    assert ec.next_session_expiry(date(2026, 9, 10)) == "2026-09-12T00:00:00+00:00"
    # Friday -> Monday; Saturday (no session) -> Monday too.
    assert ec.next_session_expiry(date(2026, 9, 11)) == "2026-09-15T00:00:00+00:00"
    assert ec.next_session_expiry(date(2026, 9, 12)) == "2026-09-15T00:00:00+00:00"
    # Winter (EST, -05:00) rather than a fixed daylight offset.
    assert ec.next_session_expiry(date(2026, 12, 10)) == "2026-12-12T01:00:00+00:00"


# --------------------------------------------------------------------------
# T4 - the idempotency key and the run id
# --------------------------------------------------------------------------
def test_the_idempotency_key_is_a_fresh_uuid4_per_artifact(tmp_path):
    first = _emit(tmp_path / "a")
    second = _emit(tmp_path / "b")

    for doc in (first, second):
        parsed = uuid.UUID(doc["idempotency_key"])
        assert parsed.version == 4 and str(parsed) == doc["idempotency_key"]
    assert first["idempotency_key"] != second["idempotency_key"]


def test_the_run_id_is_the_report_directory_name(tmp_path):
    run_dir = tmp_path / "NVDA_20260912_005957"
    run_dir.mkdir()
    doc = _emit(run_dir)

    # Stable across a re-emit: the inbox keys on service:run_id:artifact_sha256,
    # so a run id that changed would turn a rebuild into a second signal.
    assert doc["producer"]["run_id"] == "NVDA_20260912_005957"
    assert doc["producer"]["service"] == "tradingagents"


def test_the_unusable_pm_confidence_is_dropped_not_clamped(tmp_path):
    assert _emit(tmp_path / "a", pm_decision={"rating": "Hold", "confidence": 3.0})[
        "confidence"
    ] is None
    assert _emit(tmp_path / "b", pm_decision={"rating": "Hold", "confidence": 0.4})[
        "confidence"
    ] == 0.4


# --------------------------------------------------------------------------
# T5 - the producer-owned score is honest
# --------------------------------------------------------------------------
def test_the_opportunity_score_is_null_or_in_range(tmp_path):
    doc = _emit(tmp_path)

    # No deterministic producer exists in this repo (plan section 7.2): the only
    # candidates are stochastic (the debate judge's rubric mean) or prose (the
    # PM's confidence), so the field stays null rather than dressing an estimate
    # up as a measurement. The schema allows null and the artifact still ingests.
    assert doc["opportunity_score"] is None


def test_an_out_of_range_score_is_flagged_by_the_verifier(tmp_path):
    doc = _emit(tmp_path)
    doc["opportunity_score"] = 142.0
    ec.seal(doc)

    codes = [p["code"] for p in ec.integrity_problems(doc, now=datetime.now(timezone.utc))]
    assert codes == ["invalid_opportunity_score"]


# --------------------------------------------------------------------------
# T6 - the executor's reserved keys are not the producer's to set
# --------------------------------------------------------------------------
def test_the_artifact_does_not_set_executor_owned_fields(tmp_path):
    doc = _emit(tmp_path)

    assert [k for k in ec.EXECUTOR_OWNED if k in doc] == []
    # The advisory label keeps its own name: it explains the *research* verdict.
    assert doc["binding_constraint"] in (None, "halt", "book_drawdown", "analyzed_name_cvar", "risk_gate")


def test_the_risk_context_is_an_allow_listed_advisory_block(tmp_path):
    doc = _emit(
        tmp_path,
        risk_context={
            "book_drawdown": 0.0724,
            "drawdown_limit": 0.10,
            "single_cvar": 0.0483,
            "cvar_budget_pct": 0.03,
            "internal_notes": "must not be published",
            "broker_key": "must not be published",
        },
    )

    assert doc["risk_context"]["book_drawdown"] == 0.0724
    assert set(doc["risk_context"]) == {
        "book_drawdown",
        "drawdown_limit",
        "single_cvar",
        "cvar_budget_pct",
        "risk_gate",
    }


def test_the_context_carries_only_what_actually_ran(tmp_path):
    """Null when nothing ran; never an empty object, never an invented number."""
    doc = _emit(tmp_path)
    # The base fixture ran the gate but not the governor: the verdict travels,
    # no risk number is fabricated.
    assert doc["risk_context"] == {"risk_gate": {"verdict": "PASS", "reasons": []}}
    assert _emit(tmp_path / "empty", risk_gate={}, risk_context={})["risk_context"] is None
