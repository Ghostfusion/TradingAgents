"""One owner for the research -> execution artifact contract (v1.1.0).

The executor (``TradingExecution/signald/contracts.py``) reads
``research_decision.json`` as a **versioned envelope**: a declared
MAJOR.MINOR.PATCH, a UUIDv4 idempotency key, an offset-aware expiry, a producer
block, and two self-excluding hashes. This module is the single place in this
repo that knows those rules, so the emitter and the verifier cannot disagree
with each other - and so nothing here ever imports the execution layer (the two
repos share a published interface, not code; ``Master_deign.md`` section 2.2).

Three boundary facts drive it (evidence in the execution repo, plan section 0):

* a version-less artifact is read as 1.0.0 and still ingests, so declaring
  ``1.1.0`` is what makes provenance, expiry and the body hash checkable;
* the executor reserves ``trade_permission`` / ``binding_gate`` for its own
  gate, so the advisory label this repo emits is named ``binding_constraint``;
* a timestamp without a UTC offset is ambiguous and is **rejected**
  (``naive_timestamp``), never guessed at.

``artifacts/research_decision.json`` is advisory: this repo emits it and never
acts on it. Every unproducible value is ``null`` - the executor fails closed on
what it cannot validate, so a fabricated number is worse than a missing one.

Design + acceptance tests: ``docs/execution_v1_emitter_plan.md`` (R1-R5).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

# Kept in lockstep with the vendored copy of the executor's published schema
# (contracts/research_decision.v1.schema.json), which a test asserts against.
SCHEMA_VERSION = "1.1.0"
SERVICE = "tradingagents"

#: The last hour of a US session; an artifact must not be actionable after the
#: close of the session that follows it.
EXPIRY_HOUR_ET = 20

#: Fields the executor's gate owns. A producer-set ``trade_permission`` is a
#: dead-letter there (``producer_set_permission``); the others would collide
#: with gate-computed labels.
EXECUTOR_OWNED = ("trade_permission", "binding_gate", "permission_reason")

#: Governor numbers that are safe to publish as *advisory* context. An explicit
#: allow-list, not a passthrough: `final_state["risk_context"]` may grow keys
#: that are not ours to publish, and the executor never reads a number out of
#: this block (it computes its own).
ADVISORY_RISK_KEYS = (
    "book_drawdown",
    "drawdown_limit",
    "single_cvar",
    "book_cvar",
    "cvar_budget_pct",
    "liquidity",
    "regime",
)

_HASH_FIELDS = ("artifact_sha256", "decision_hash")


def hash_body(obj: Any) -> str:
    """Bare sha256 hex over ``obj`` - the recipe both repos share.

    ``sort_keys=True, default=str`` over the **body**, never the file bytes, so
    re-indenting cannot change a hash and either side can recompute it.
    """
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def body_of(doc: dict) -> dict:
    """The artifact minus both hashes (what ``artifact_sha256`` covers)."""
    return {k: v for k, v in doc.items() if k not in _HASH_FIELDS}


def seal(doc: dict) -> dict:
    """Pin both hashes in place, last thing before writing.

    ``artifact_sha256`` excludes both hash fields; ``decision_hash`` excludes
    only itself (so it covers ``artifact_sha256``). Both carry their own
    exclusions, which is why either can be computed first - the same
    self-exclusion idiom the mandate uses. Never post-edit a sealed artifact:
    the executor recomputes the body and dead-letters a mismatch.
    """
    doc.pop("artifact_sha256", None)
    doc.pop("decision_hash", None)
    doc["artifact_sha256"] = hash_body(body_of(doc))
    doc["decision_hash"] = "sha256:" + hash_body(
        {k: v for k, v in doc.items() if k != "decision_hash"}
    )
    return doc


def seal_problems(doc: dict) -> list[str]:
    """Why the declared hashes do not recompute (``[]`` when they do).

    Used by the report verifier; mirrors ``contracts.verify_artifact_hash`` and
    ``schema.parse_research_decision`` without importing them.
    """
    problems: list[str] = []
    declared = str(doc.get("artifact_sha256") or "").strip()
    if not declared:
        problems.append("artifact_sha256 is missing")
    elif declared.removeprefix("sha256:") != hash_body(body_of(doc)):
        problems.append("artifact_sha256 does not match the artifact body")
    declared_decision = doc.get("decision_hash")
    if declared_decision:
        expected = hash_body({k: v for k, v in doc.items() if k != "decision_hash"})
        if str(declared_decision).removeprefix("sha256:") != expected:
            problems.append("decision_hash does not match the artifact body")
    return problems


def parse_version(raw: dict) -> tuple[int, int, int]:
    """Declared MAJOR.MINOR.PATCH; missing/legacy (int ``1``) reads as 1.0.0."""
    value = raw.get("schema_version")
    if value is None:
        return (1, 0, 0)
    if isinstance(value, bool):  # bool is an int subclass; never a version
        return (1, 0, 0)
    if isinstance(value, int):
        return (value, 0, 0)
    parts = str(value).strip().split(".")
    if len(parts) != 3:
        return (1, 0, 0)
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return (1, 0, 0)


def is_v11(raw: dict) -> bool:
    """True when the artifact declares >= 1.1.0 (the stricter required set)."""
    return parse_version(raw) >= (1, 1, 0)


def git_sha() -> str:
    """Short HEAD sha of this repo, best-effort; ``""`` when git is unavailable.

    The executor requires a non-empty ``producer.service`` only, so a missing
    sha degrades the provenance without breaking the ingest.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:  # noqa: BLE001 - provenance is best-effort, never fatal
        return ""


def _expiry_zone():
    """The ET zone; a fixed -05:00 when tzdata is absent.

    Windows ships no system tz database, so ``zoneinfo`` can raise. The
    fallback is conservative in winter and one hour late in summer, which the
    executor's own ``ingest_window_hours`` backstops - never an ambient naive
    stamp (the executor rejects those outright).
    """
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("America/New_York")
    except Exception:  # noqa: BLE001 - optional tzdata; documented fallback
        return timezone(timedelta(hours=-5))


def next_session_expiry(effective: date) -> str:
    """The close (20:00 ET) of the session following ``effective``, in UTC.

    Policy (plan section 7.1): an artifact for one session must not be
    actionable after the next session's close. Weekends are skipped here; the
    exchange holiday calendar belongs to the executor, and its ingest window is
    the backstop. Always offset-aware.
    """
    day = effective + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    local = datetime.combine(day, time(EXPIRY_HOUR_ET), tzinfo=_expiry_zone())
    return local.astimezone(timezone.utc).isoformat()


def run_id_for(save_path: Any) -> str:
    """The stable, human-traceable run id: the report directory's name.

    The inbox keys on ``{service}:{run_id}:{artifact_sha256}``, so a run id that
    changes on a re-emit would turn a rebuild into a **second signal** for the
    same decision. The report directory name (``NVDA_20260912_005957``) is
    stable across re-emits and traceable; a uuid4 is the fallback when there is
    no directory to name (plan section 7.4).
    """
    try:
        name = Path(save_path).name
    except (TypeError, ValueError):  # pragma: no cover - defensive
        name = ""
    return name or str(uuid.uuid4())


def producer_block(run_id: str) -> dict:
    """The producer stanza; ``service`` is what the executor requires."""
    return {"service": SERVICE, "git_sha": git_sha(), "run_id": run_id}


def risk_advisory(final_state: dict) -> dict | None:
    """The governor numbers the executor may *record* (never read as data).

    Allow-listed from ``final_state["risk_context"]`` plus the gate verdict, so
    a key that is not ours to publish cannot leak by being added upstream.
    ``None`` when the governor did not run - an empty object would read as
    "governor ran, nothing to say".
    """
    ctx = final_state.get("risk_context") or {}
    if not isinstance(ctx, dict):
        ctx = {}
    out: dict[str, Any] = {
        key: ctx[key] for key in ADVISORY_RISK_KEYS if ctx.get(key) is not None
    }
    gate = final_state.get("risk_gate")
    if isinstance(gate, dict) and gate:
        out["risk_gate"] = {
            "verdict": gate.get("verdict"),
            "reasons": list(gate.get("reasons") or []),
        }
    return out or None


def opportunity_score() -> float | None:
    """Always ``None`` today - deliberately (plan section 7.2).

    ``opportunity_score`` is producer-owned 0..100 on the executor's side. This
    repo has no *deterministic* producer for "how attractive is this idea on its
    own merits": the only candidates in state are the debate judge's LLM rubric
    mean (stochastic between runs) and the PM's prose confidence. Publishing
    either under a numeric field the executor may rank on would dress an
    estimate up as a measurement - the same defect class as the number/label
    integrity fixes of 2026-09-12. The schema allows ``null``, so a missing
    score is honest and the artifact still ingests.
    """
    return None


def confidence_of(final_state: dict) -> float | None:
    """The PM's stated confidence (0..1), or ``None`` when unusable.

    Validated rather than clamped: an out-of-range value means the model broke
    its schema, and a clamped number would present a broken value as a sound one.
    """
    pm = final_state.get("pm_decision")
    if not isinstance(pm, dict):
        return None
    value = pm.get("confidence")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if 0.0 <= value <= 1.0 else None


def envelope_fields(
    final_state: dict,
    *,
    run_id: str,
    effective: date,
    now: datetime | None = None,
) -> dict:
    """The v1.1.0 additive fields, from state only (no new computation).

    ``produced_at``/``expires_at`` are always UTC-aware; ``producer`` and the
    idempotency key are minted per artifact; the advisory blocks are ``None``
    when their source did not run.
    """
    produced = now or datetime.now(timezone.utc)
    if produced.tzinfo is None:  # pragma: no cover - callers pass aware stamps
        produced = produced.replace(tzinfo=timezone.utc)
    return {
        "produced_at": produced.astimezone(timezone.utc).isoformat(),
        "expires_at": next_session_expiry(effective),
        "idempotency_key": str(uuid.uuid4()),
        "producer": producer_block(run_id),
        "opportunity_score": opportunity_score(),
        "confidence": confidence_of(final_state),
        "risk_context": risk_advisory(final_state),
    }


def integrity_problems(raw: dict, *, now: datetime) -> list[dict]:
    """v1.1.0 conformance problems for one artifact; ``[]`` when clean.

    Read-only and non-fatal by design: the report tree must still render when
    an artifact is malformed. Legacy artifacts (no version, or < 1.1) are
    **not** flagged - the executor accepts them as 1.0.0 and skips these checks,
    so flagging them here would mark 500+ historical trees as broken.
    """
    problems: list[dict] = []

    def bad(code: str, detail: str) -> None:
        problems.append({"code": code, "detail": detail})

    version = raw.get("schema_version")
    if isinstance(version, str) and len(version.strip().split(".")) != 3:
        bad("invalid_version", f"schema_version {version!r} is not MAJOR.MINOR.PATCH")
    if parse_version(raw)[0] != 1:
        bad("unknown_major", f"schema_version {version!r} has MAJOR != 1")
        return problems
    if not is_v11(raw):
        return problems

    for key in ("expires_at", "idempotency_key", "producer", "artifact_sha256"):
        if raw.get(key) in (None, "", {}):
            bad("missing_field", f"{key} is mandatory for schema_version {SCHEMA_VERSION}")

    for name in ("trade_permission", "binding_gate"):
        if raw.get(name) not in (None, ""):
            bad("producer_set_reserved_field", f"{name} is owned by the executor's gate")

    key = raw.get("idempotency_key")
    if key:
        try:
            parsed = uuid.UUID(str(key))
        except (TypeError, ValueError):
            parsed = None
        if parsed is None or parsed.version != 4 or str(parsed) != str(key).lower():
            bad("invalid_idempotency_key", f"idempotency_key {key!r} is not a UUIDv4")

    producer = raw.get("producer")
    if producer is not None and not isinstance(producer, dict):
        bad("invalid_producer", "producer is not an object")
    elif isinstance(producer, dict) and not str(producer.get("service") or "").strip():
        bad("invalid_producer", "producer.service is empty")

    stamps: dict[str, datetime] = {}
    for field in ("produced_at", "expires_at"):
        value = raw.get(field)
        if not value:
            continue
        try:
            parsed_dt = datetime.fromisoformat(str(value))
        except ValueError:
            bad("invalid_timestamp", f"{field} {value!r} is not ISO-8601")
            continue
        if parsed_dt.tzinfo is None or parsed_dt.utcoffset() is None:
            bad("naive_timestamp", f"{field} carries no UTC offset")
            continue
        stamps[field] = parsed_dt
    if "produced_at" in stamps and "expires_at" in stamps:
        if stamps["expires_at"] < stamps["produced_at"]:
            bad("invalid_timestamp", "expires_at is before produced_at")
        elif stamps["expires_at"] < now.astimezone(stamps["expires_at"].tzinfo):
            bad("expired", f"expires_at {stamps['expires_at'].isoformat()} is in the past")

    score = raw.get("opportunity_score")
    if score is not None:
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            bad("invalid_opportunity_score", f"opportunity_score {score!r} is not a number")
        elif not 0.0 <= float(score) <= 100.0:
            bad(
                "invalid_opportunity_score",
                f"opportunity_score {score!r} is outside 0..100",
            )

    if "artifact_sha256" in raw or "decision_hash" in raw:
        stale = seal_problems(raw)
        if stale:
            bad("artifact_hash_mismatch", "; ".join(stale))
    return problems
