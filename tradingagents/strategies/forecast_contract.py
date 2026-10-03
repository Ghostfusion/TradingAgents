"""The forecast contract - three records, two of them immutable (design doc §7).

A **declaration**, not a calculator: this module computes nothing, reads no
config, adds no gate, imports no vendor and touches no network. It fixes the
shapes a *producer* publishes and the shape the *ledger* appends, and it
enforces the design doc's §7.2 rules **at construction** so a violation fails
where it is made rather than in a report a reader has to audit.

The split, and the invariant it buys (design doc §7.1)::

    a forecast cannot change because a later evaluation changed.

``ForecastRecord`` therefore carries **no evaluation field at all** - not a
``None``-valued one, none - and ``ForecastEvaluation`` is a separate object the
ledger appends, keyed by ``forecast_id``. ``CandidateForecast`` is a pool
*member*: never authoritative, never published, never a ledger row (FD-1 §3.2,
design doc §3.2/§7.4).

Why enforcement lives here
--------------------------
The repo already carries nine distinct volatility concepts
(``ewma_vol``/``parkinson_vol``/``garman_klass_vol``/``yang_zhang_vol``/
``garch11_fit``/realized vol/``semivariance``/``bipower_proxy``/
``quarticity_proxy``), so a forecast of one is not interchangeable with a
forecast of another; and ``NA != 0`` is a standing rule of this codebase. Both
become constructor errors instead of review comments:

- ``value is None`` **iff** ``status != "ok"`` - a refusal can never carry
  ``0.0`` (§7.2 rule 1);
- ``status`` is ``ok``/``unavailable``/``declined``, and a non-``ok`` row
  carries a ``reason_code`` from the closed vocabulary, matched to its status
  (§7.2 rules 3-4);
- ``horizon_steps >= 1`` - a state read is not a forecast (§7.2 rule 6);
- ``target.name``/``definition``/``definition_version``/``unit``,
  ``entity_scope``, ``frequency``, ``horizon_steps`` and ``forecast_origin`` are
  mandatory (§7.2 rule 7);
- ``interval`` is optional and **all-or-nothing**, and can never carry
  ``realized_coverage`` - that is post-hoc evidence, not production metadata
  (§7.2 rule 5);
- ``producer_id`` (stable semantic owner) and ``implementation_ref`` (current
  code location) are different fields and must differ (§7.2 rule 8);
- provenance is mandatory, with ``padded``/``data_snapshot_id``/``calendar_id``
  required and defaulted by nothing (§7.2 rule 9).

The vocabularies below are the design doc's, restated once so the registry and
the tests read the same list. They are **not enforced against arbitrary
producers** (only the closed ``reason_code`` vocabulary is): the design doc
declares them so ``producer_id`` stays a name rather than a semantic soup, and a
producer that needs a term outside this list is making a design decision, not a
typo.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------
# The declared vocabularies (design doc §7.2 rules 3-4, §7.3)
# --------------------------------------------------------------------------

#: ``ForecastRecord.status`` - the three states of a forecast (§7.2 rule 3).
FORECAST_STATUSES = ("ok", "unavailable", "declined")

#: Authorized, not currently producible. A *gap* - never a zero.
UNAVAILABLE_REASON_CODES = (
    "INSUFFICIENT_HISTORY",
    "MISSING_VENDOR_SERIES",
    "MODEL_FIT_FAILURE",
    "COVERAGE_FAILURE",
    "GATE_OFF",
)

#: A cited, **reversible policy statement**: the engine intentionally does not
#: produce this quantity. Distinct from ``unavailable`` - the refusal is the
#: output, and an absent row is an invitation rather than a policy.
DECLINED_REASON_CODES = (
    "RETURN_LEVEL_NOT_ADMITTED",
    "RETURN_RANK_NOT_ADMITTED",
    "TARGET_NOT_ADMITTED",
)

#: The closed vocabulary, per status.
REASON_CODES_BY_STATUS = {
    "unavailable": UNAVAILABLE_REASON_CODES,
    "declined": DECLINED_REASON_CODES,
}

#: Every code, both families - the flat form a reader greps for.
REASON_CODES = UNAVAILABLE_REASON_CODES + DECLINED_REASON_CODES

#: ``target.name`` (design doc §7.3). ``realized_volatility`` is used by §7.3's
#: own key examples and by the §6.1 ownership table, though §7.3's bullet list
#: omits it - recorded here so the registry and the tests agree; the list's
#: omission is reported, not silently repaired (design doc §11.0).
TARGET_NAMES = (
    "absolute_return",
    "relative_return",
    "return_rank",
    "residual_return",
    "realized_volatility",
    "volatility",
    "variance",
    "volatility_rank",
    "regime_probability",
    "regime_stress_probability",
)

#: ``entity_scope`` - part of the forecast's identity (§7.2 rule 2): a
#: ``single_asset`` read and a ``cross_section`` read are different forecasts.
ENTITY_SCOPES = ("single_asset", "sector", "portfolio", "index", "cross_section")

#: ``target.unit`` (design doc §7.3).
TARGET_UNITS = (
    "annualized_vol",
    "variance",
    "probability",
    "rank_decile",
    "pct",
    "raw_return_bps",
)

#: The interval's production metadata, all-or-nothing (§7.2 rule 5).
INTERVAL_FIELDS = ("low", "high", "nominal_coverage", "method", "calibration_ref")

#: ``ForecastEvaluation.scoring_rule`` - point rules and distributional rules.
SCORING_RULES = ("CRPS", "QLIKE", "RMSE", "MAE")

_TARGET_FIELDS = ("name", "definition", "definition_version", "unit", "annualization")

_PROVENANCE_FIELDS = (
    "data_snapshot_id",
    "training_start",
    "training_end",
    "requested_window",
    "effective_window",
    "padded",
    "missing_obs",
    "imputed_obs",
    "adjusted_prices",
    "feature_version",
    "model_version",
    "parameter_hash",
    "code_revision",
    "calendar_id",
)


class ForecastContractError(ValueError):
    """A forecast record violated a construction invariant of design doc §7.2."""


# --------------------------------------------------------------------------
# Coercion / validation helpers
# --------------------------------------------------------------------------


def _as_float(value: Any, where: str) -> float:
    if isinstance(value, bool):
        raise ForecastContractError(f"{where} must be a number, got a bool ({value!r})")
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ForecastContractError(f"{where} must be a number, got {value!r}") from exc
    if not math.isfinite(out):
        raise ForecastContractError(f"{where} must be finite, got {value!r}")
    return out


def _as_str(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ForecastContractError(f"{where} is mandatory and must be a non-empty string, got {value!r}")
    return value


def _as_count(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ForecastContractError(f"{where} must be an int, got {value!r}")
    if value < 0:
        raise ForecastContractError(f"{where} must be >= 0, got {value!r}")
    return value


def _as_flag(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise ForecastContractError(f"{where} must be a bool, got {value!r}")
    return value


def _as_horizon(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ForecastContractError(f"{where} must be an int, got {value!r}")
    if value < 1:
        raise ForecastContractError(
            f"{where} must be >= 1, got {value!r}: horizon_steps=0 is a state read, and a state "
            "read is not a forecast (design doc §7.2 rule 6)"
        )
    return value


def _as_origin(value: Any, where: str) -> float:
    out = _as_float(value, where)
    if out <= 0.0:
        raise ForecastContractError(
            f"{where} must be a positive timestamp (epoch seconds), got {value!r}: it is WHEN all "
            "information available to the forecast is frozen (design doc §7.1)"
        )
    return out


def _reject_unknown(mapping: Mapping, allowed: tuple[str, ...], where: str) -> None:
    unknown = sorted(k for k in mapping if k not in allowed)
    if unknown:
        raise ForecastContractError(
            f"{where} carries field(s) {unknown} that are not part of the declared shape {list(allowed)}"
        )


def _coerce_target(value: Any, where: str) -> TargetRef:
    if isinstance(value, TargetRef):
        return value
    if not isinstance(value, Mapping):
        raise ForecastContractError(
            f"{where}.target must be a TargetRef or a mapping, got {type(value).__name__}"
        )
    _reject_unknown(value, _TARGET_FIELDS, f"{where}.target")
    missing = [k for k in _TARGET_FIELDS if value.get(k) is None and k != "annualization"]
    if missing:
        raise ForecastContractError(
            f"{where}.target is missing {sorted(missing)}: no forecast without a target definition "
            "(design doc §7.2 rule 7)"
        )
    return TargetRef(**{k: value[k] for k in _TARGET_FIELDS if k in value})


def _coerce_provenance(value: Any, where: str) -> Provenance:
    if isinstance(value, Provenance):
        return value
    if not isinstance(value, Mapping):
        raise ForecastContractError(
            f"{where}.provenance must be a Provenance or a mapping, got {type(value).__name__}"
        )
    _reject_unknown(value, _PROVENANCE_FIELDS, f"{where}.provenance")
    missing = [k for k in _PROVENANCE_FIELDS if value.get(k) is None]
    if missing:
        raise ForecastContractError(
            f"{where}.provenance is missing {sorted(missing)}: provenance is mandatory and "
            "`padded` / `data_snapshot_id` / `calendar_id` are required with no default "
            "(design doc §7.2 rule 9)"
        )
    return Provenance(**{k: value[k] for k in _PROVENANCE_FIELDS})


def _coerce_interval(value: Any, where: str) -> Interval | None:
    if value is None:
        return None
    if isinstance(value, Interval):
        return value
    if not isinstance(value, Mapping):
        raise ForecastContractError(
            f"{where}.interval must be an Interval, a mapping or None, got {type(value).__name__}"
        )
    unknown = sorted(k for k in value if k not in INTERVAL_FIELDS)
    if unknown:
        raise ForecastContractError(
            f"{where}.interval carries field(s) {unknown}; the interval is production metadata only "
            "and `realized_coverage` is never production metadata - it belongs to "
            "ForecastEvaluation (design doc §7.2 rule 5)"
        )
    missing = [k for k in INTERVAL_FIELDS if value.get(k) is None]
    if missing:
        raise ForecastContractError(
            f"{where}.interval is partially populated: missing {sorted(missing)}. The interval is "
            "all-or-nothing - a partially populated one is a defect, not a low-confidence band "
            "(design doc §7.2 rule 5)"
        )
    return Interval(**{k: value[k] for k in INTERVAL_FIELDS})


def _validate_status_value_reason(status: Any, value: Any, reason_code: Any, where: str) -> None:
    if status not in FORECAST_STATUSES:
        raise ForecastContractError(
            f"{where}.status must be one of {list(FORECAST_STATUSES)}, got {status!r}"
        )
    if status == "ok":
        if value is None:
            raise ForecastContractError(
                f"{where}: status='ok' requires a value; a produced forecast is never None"
            )
        _as_float(value, f"{where}.value")
        if reason_code is not None:
            raise ForecastContractError(
                f"{where}: status='ok' carries no reason_code, got {reason_code!r}: a produced "
                "forecast is not a refusal"
            )
        return
    if value is not None:
        raise ForecastContractError(
            f"{where}: status={status!r} must carry value=None, got {value!r}. A refusal is never a "
            "zero and never a shrunk-to-zero pseudo-number (design doc §7.2 rule 1)"
        )
    if not isinstance(reason_code, str) or not reason_code:
        raise ForecastContractError(
            f"{where}: status={status!r} requires a non-empty reason_code from the closed "
            f"vocabulary {list(REASON_CODES_BY_STATUS[status])} - free prose is not a code "
            "(design doc §7.2 rule 4)"
        )
    allowed = REASON_CODES_BY_STATUS[status]
    if reason_code not in allowed:
        raise ForecastContractError(
            f"{where}: reason_code {reason_code!r} is not in the closed {status!r} vocabulary "
            f"{list(allowed)} (design doc §7.2 rules 3-4)"
        )


# --------------------------------------------------------------------------
# The records
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class Interval:
    """A forecast's production-time band - and nothing post-hoc (§7.2 rule 5).

    ``realized_coverage`` deliberately has no home here: coverage is measured
    after the outcome resolves and lives on ``ForecastEvaluation``. A band whose
    realized coverage sits beside its nominal level is the bug this split
    removes.
    """

    low: float
    high: float
    nominal_coverage: float
    method: str
    calibration_ref: str

    def __post_init__(self) -> None:
        low = _as_float(self.low, "Interval.low")
        high = _as_float(self.high, "Interval.high")
        coverage = _as_float(self.nominal_coverage, "Interval.nominal_coverage")
        if low > high:
            raise ForecastContractError(
                f"Interval.low ({low}) is above Interval.high ({high})"
            )
        if not 0.0 < coverage < 1.0:
            raise ForecastContractError(
                f"Interval.nominal_coverage must lie strictly inside (0, 1), got {coverage}"
            )
        _as_str(self.method, "Interval.method")
        _as_str(self.calibration_ref, "Interval.calibration_ref")


@dataclass(frozen=True, kw_only=True)
class TargetRef:
    """The measured quantity, spelled out - one name is not another (§7.2 rule 7)."""

    name: str
    definition: str
    definition_version: str
    unit: str
    annualization: int | None = None

    def __post_init__(self) -> None:
        _as_str(self.name, "TargetRef.name")
        _as_str(self.definition, "TargetRef.definition")
        _as_str(self.definition_version, "TargetRef.definition_version")
        _as_str(self.unit, "TargetRef.unit")
        if self.annualization is not None:
            _as_count(self.annualization, "TargetRef.annualization")
            if self.annualization == 0:
                raise ForecastContractError(
                    "TargetRef.annualization must be a positive period count or None, got 0"
                )


@dataclass(frozen=True, kw_only=True)
class Provenance:
    """What the forecast was made from - required, defaulted by nothing (§7.2 rule 9).

    ``padded`` is the load-bearing one: a padded window *suppresses measured
    volatility in a known direction*, so it is biased rather than merely
    uncertain. ``adjusted_prices`` changes the economic meaning of a return
    series while leaving the arithmetic reproducible.
    """

    data_snapshot_id: str
    training_start: float
    training_end: float
    requested_window: int
    effective_window: int
    padded: bool
    missing_obs: int
    imputed_obs: int
    adjusted_prices: bool
    feature_version: str
    model_version: str
    parameter_hash: str
    code_revision: str
    calendar_id: str

    def __post_init__(self) -> None:
        _as_str(self.data_snapshot_id, "Provenance.data_snapshot_id")
        start = _as_float(self.training_start, "Provenance.training_start")
        end = _as_float(self.training_end, "Provenance.training_end")
        if end < start:
            raise ForecastContractError(
                f"Provenance.training_end ({end}) precedes training_start ({start})"
            )
        requested = _as_count(self.requested_window, "Provenance.requested_window")
        effective = _as_count(self.effective_window, "Provenance.effective_window")
        if effective > requested:
            raise ForecastContractError(
                f"Provenance.effective_window ({effective}) exceeds requested_window ({requested})"
            )
        _as_flag(self.padded, "Provenance.padded")
        missing = _as_count(self.missing_obs, "Provenance.missing_obs")
        if missing > requested:
            raise ForecastContractError(
                f"Provenance.missing_obs ({missing}) exceeds requested_window ({requested})"
            )
        imputed = _as_count(self.imputed_obs, "Provenance.imputed_obs")
        if imputed > effective:
            raise ForecastContractError(
                f"Provenance.imputed_obs ({imputed}) exceeds effective_window ({effective})"
            )
        _as_flag(self.adjusted_prices, "Provenance.adjusted_prices")
        _as_str(self.feature_version, "Provenance.feature_version")
        _as_str(self.model_version, "Provenance.model_version")
        _as_str(self.parameter_hash, "Provenance.parameter_hash")
        _as_str(self.code_revision, "Provenance.code_revision")
        _as_str(self.calendar_id, "Provenance.calendar_id")


@dataclass(frozen=True, kw_only=True)
class CandidateForecast:
    """A pool MEMBER - never authoritative, never published, never a ledger row.

    FD-1 §3.2 (design doc §3.2): several models may each produce a value for the
    same semantic target; those are candidates. Only the pool/selector publishes
    the authoritative ``ForecastRecord``, so the one-producer rule binds the
    pool and never its members.
    """

    candidate_id: str
    target: TargetRef
    frequency: str
    horizon_steps: int
    forecast_origin: float
    model_id: str
    model_version: str
    value: float
    interval: Interval | None = None

    def __post_init__(self) -> None:
        _as_str(self.candidate_id, "CandidateForecast.candidate_id")
        object.__setattr__(self, "target", _coerce_target(self.target, "CandidateForecast"))
        object.__setattr__(self, "interval", _coerce_interval(self.interval, "CandidateForecast"))
        _as_str(self.frequency, "CandidateForecast.frequency")
        _as_horizon(self.horizon_steps, "CandidateForecast.horizon_steps")
        _as_origin(self.forecast_origin, "CandidateForecast.forecast_origin")
        _as_str(self.model_id, "CandidateForecast.model_id")
        _as_str(self.model_version, "CandidateForecast.model_version")
        _as_float(self.value, "CandidateForecast.value")


@dataclass(frozen=True, kw_only=True)
class ForecastRecord:
    """PRODUCTION-TIME IMMUTABLE. One per authoritative key (§7.2 rule 2).

    **There is no evaluation field, and there never will be.** What the model
    knew at ``forecast_origin`` is exactly reproducible, and the evaluation is a
    separate append-only event keyed to it (``ForecastEvaluation``).
    """

    forecast_id: str
    producer_id: str
    implementation_ref: str
    gate: str | None
    target: TargetRef
    entity_scope: str
    frequency: str
    horizon_steps: int
    forecast_origin: float
    value: float | None
    status: str
    provenance: Provenance
    interval: Interval | None = None
    reason_code: str | None = None
    reason_detail: str | None = None

    def __post_init__(self) -> None:
        _as_str(self.forecast_id, "ForecastRecord.forecast_id")
        _as_str(self.producer_id, "ForecastRecord.producer_id")
        _as_str(self.implementation_ref, "ForecastRecord.implementation_ref")
        if self.producer_id == self.implementation_ref:
            raise ForecastContractError(
                "ForecastRecord.producer_id and implementation_ref are different fields: "
                "producer_id is the STABLE semantic owner, implementation_ref is the CURRENT code "
                "location, and code paths move during refactoring (design doc §7.2 rule 8)"
            )
        if ".py" in self.producer_id or "::" in self.producer_id:
            raise ForecastContractError(
                f"ForecastRecord.producer_id {self.producer_id!r} looks like a code path; it is the "
                "stable semantic owner (e.g. 'forecast_pool.realized_volatility.v1'), not a module "
                "or symbol (design doc §7.2 rule 8)"
            )
        if "::" not in self.implementation_ref:
            raise ForecastContractError(
                f"ForecastRecord.implementation_ref {self.implementation_ref!r} is not a resolvable "
                "repo path: it is written 'strategies/<module>.py::<symbol>' and resolves by the "
                "fixed transform of design doc §7.2 rule 8"
            )
        if self.gate is not None:
            _as_str(self.gate, "ForecastRecord.gate")
            if not self.gate.startswith("enable_"):
                raise ForecastContractError(
                    f"ForecastRecord.gate {self.gate!r} is not an `enable_*` switch; a gate name "
                    "either names a real config key or is None"
                )
        object.__setattr__(self, "target", _coerce_target(self.target, "ForecastRecord"))
        object.__setattr__(
            self, "provenance", _coerce_provenance(self.provenance, "ForecastRecord")
        )
        object.__setattr__(self, "interval", _coerce_interval(self.interval, "ForecastRecord"))
        _as_str(self.entity_scope, "ForecastRecord.entity_scope")
        _as_str(self.frequency, "ForecastRecord.frequency")
        _as_horizon(self.horizon_steps, "ForecastRecord.horizon_steps")
        _as_origin(self.forecast_origin, "ForecastRecord.forecast_origin")
        _validate_status_value_reason(
            self.status, self.value, self.reason_code, "ForecastRecord"
        )
        if self.reason_detail is not None:
            _as_str(self.reason_detail, "ForecastRecord.reason_detail")


#: The ledger's terminal. A producer never holds it, so a producer cannot
#: construct an evaluation; ``strategies/prediction_ledger.py`` is the only
#: importer (FL-5, design doc §8.1). Private on purpose - the published contract
#: offers no producer-facing way to write an evaluation.
_LEDGER_WRITER = object()


def _ledger_writer_token() -> Any:
    """The terminal the prediction ledger passes to ``ForecastEvaluation``."""
    return _LEDGER_WRITER


@dataclass(frozen=True, kw_only=True)
class ForecastEvaluation:
    """POST-HOC IMMUTABLE, appended by the ledger. Never writable by a producer.

    One-way by construction (design doc §8.1): the ledger scores the producer,
    the producer never scores itself. Construction requires the ledger's
    terminal, so an arbitrary caller cannot mint one.
    """

    forecast_id: str
    realized_outcome: float
    evaluated_as_of: float
    n_observations: int
    scoring_rule: str
    score: float
    benchmark_ref: str
    benchmark_score: float
    benchmark_delta: float
    realized_coverage: float | None = None
    _writer: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._writer is not _LEDGER_WRITER:
            raise ForecastContractError(
                "ForecastEvaluation is appended by the prediction ledger only; a producer has no "
                "write path to an evaluation (design doc §7.1/§8.1). The ledger passes the "
                "terminal it alone holds."
            )
        _as_str(self.forecast_id, "ForecastEvaluation.forecast_id")
        _as_float(self.realized_outcome, "ForecastEvaluation.realized_outcome")
        _as_origin(self.evaluated_as_of, "ForecastEvaluation.evaluated_as_of")
        n_obs = _as_count(self.n_observations, "ForecastEvaluation.n_observations")
        if n_obs < 1:
            raise ForecastContractError(
                "ForecastEvaluation.n_observations must be >= 1: an evaluation with no observations "
                "is not an evaluation"
            )
        rule = _as_str(self.scoring_rule, "ForecastEvaluation.scoring_rule")
        if rule not in SCORING_RULES:
            raise ForecastContractError(
                f"ForecastEvaluation.scoring_rule {rule!r} is not one of {list(SCORING_RULES)}"
            )
        _as_float(self.score, "ForecastEvaluation.score")
        _as_str(self.benchmark_ref, "ForecastEvaluation.benchmark_ref")
        _as_float(self.benchmark_score, "ForecastEvaluation.benchmark_score")
        _as_float(self.benchmark_delta, "ForecastEvaluation.benchmark_delta")
        if self.realized_coverage is not None:
            coverage = _as_float(self.realized_coverage, "ForecastEvaluation.realized_coverage")
            if not 0.0 <= coverage <= 1.0:
                raise ForecastContractError(
                    f"ForecastEvaluation.realized_coverage must lie in [0, 1], got {coverage}"
                )


__all__ = [
    "CandidateForecast",
    "DECLINED_REASON_CODES",
    "ENTITY_SCOPES",
    "FORECAST_STATUSES",
    "ForecastContractError",
    "ForecastEvaluation",
    "ForecastRecord",
    "INTERVAL_FIELDS",
    "Interval",
    "Provenance",
    "REASON_CODES",
    "REASON_CODES_BY_STATUS",
    "SCORING_RULES",
    "TARGET_NAMES",
    "TARGET_UNITS",
    "TargetRef",
    "UNAVAILABLE_REASON_CODES",
]
