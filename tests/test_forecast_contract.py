"""Failing-first guards for the forecast contract (design doc §7, plan FL-1).

Every test here pins an invariant the contract enforces **at construction**, so
the mutation named in the plan's §6 table makes the test fail by name rather
than silently producing a plausible record. The two structural ones -
``test_a_forecast_record_has_no_evaluation_field`` and
``test_a_producer_cannot_construct_a_forecast_evaluation`` - are the P0 split
made executable: a record cannot be immutable and mutated.

Offline, pure, sub-second: no vendor, no config, no network.
"""

from __future__ import annotations

import dataclasses

import pytest

from tradingagents.strategies import forecast_contract as fc

pytestmark = pytest.mark.timeout(60)


def _target(**over):
    base = {
        "name": "realized_volatility",
        "definition": "next-session realized variance (sum of squared close-to-close log returns)",
        "definition_version": "realized_volatility.v2",
        "unit": "variance",
        "annualization": None,
    }
    base.update(over)
    return base


def _provenance(**over):
    base = {
        "data_snapshot_id": "TEST_SNAPSHOT_v1",
        "training_start": 1_700_000_000.0,
        "training_end": 1_750_000_000.0,
        "requested_window": 750,
        "effective_window": 750,
        "padded": False,
        "missing_obs": 0,
        "imputed_obs": 0,
        "adjusted_prices": True,
        "feature_version": "features.v1",
        "model_version": "har_rv.v1",
        "parameter_hash": "0" * 16,
        "code_revision": "deadbee",
        "calendar_id": "XNYS",
    }
    base.update(over)
    return base


def _interval(**over):
    base = {
        "low": 0.0001,
        "high": 0.0004,
        "nominal_coverage": 0.9,
        "method": "CQR",
        "calibration_ref": "H11-CQR-v2",
    }
    base.update(over)
    return base


def _record(**over):
    base = {
        "forecast_id": "fid-1",
        "producer_id": "forecast_pool.realized_volatility.v1",
        "implementation_ref": "strategies/long_memory.py::rv_forecast",
        "gate": "enable_long_memory",
        "target": _target(),
        "entity_scope": "single_asset",
        "frequency": "1d",
        "horizon_steps": 1,
        "forecast_origin": 1_750_000_000.0,
        "value": 0.0002,
        "status": "ok",
        "provenance": _provenance(),
        "interval": None,
        "reason_code": None,
        "reason_detail": None,
    }
    base.update(over)
    return base


def _evaluation(**over):
    base = {
        "forecast_id": "fid-1",
        "realized_outcome": 0.0003,
        "evaluated_as_of": 1_750_100_000.0,
        "n_observations": 1,
        "scoring_rule": "QLIKE",
        "score": 0.11,
        "benchmark_ref": "volatility.har_rv",
        "benchmark_score": 0.14,
        "benchmark_delta": -0.03,
        "realized_coverage": None,
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# rule 1 - a refusal is never a zero
# ---------------------------------------------------------------------------


def test_a_refusal_cannot_carry_a_zero():
    with pytest.raises(fc.ForecastContractError) as excinfo:
        fc.ForecastRecord(**_record(status="unavailable", value=0.0, reason_code="GATE_OFF"))
    assert "0.0" in str(excinfo.value)
    assert "value=None" in str(excinfo.value)

    # The honest form of the same record constructs, and keeps value None.
    ok = fc.ForecastRecord(**_record(status="unavailable", value=None, reason_code="GATE_OFF"))
    assert ok.value is None and ok.status == "unavailable"


# ---------------------------------------------------------------------------
# rule 6 - a state read is not a forecast
# ---------------------------------------------------------------------------


def test_a_state_read_is_not_a_forecast():
    with pytest.raises(fc.ForecastContractError) as excinfo:
        fc.ForecastRecord(**_record(horizon_steps=0))
    message = str(excinfo.value)
    assert "horizon_steps" in message
    assert "state read" in message


# ---------------------------------------------------------------------------
# rule 5 - the interval is all-or-nothing, and carries no realized coverage
# ---------------------------------------------------------------------------


def test_the_interval_is_all_or_nothing():
    with pytest.raises(fc.ForecastContractError) as excinfo:
        fc.ForecastRecord(**_record(interval={"low": 0.0001, "high": 0.0004}))
    message = str(excinfo.value)
    assert "partially populated" in message
    for missing in ("nominal_coverage", "method", "calibration_ref"):
        assert missing in message

    complete = fc.ForecastRecord(**_record(interval=_interval()))
    assert complete.interval is not None
    assert complete.interval.method == "CQR"


def test_the_interval_carries_no_realized_coverage():
    with pytest.raises(fc.ForecastContractError) as excinfo:
        fc.ForecastRecord(**_record(interval=_interval(realized_coverage=0.88)))
    message = str(excinfo.value)
    assert "realized_coverage" in message
    assert "ForecastEvaluation" in message
    assert "realized_coverage" not in {f.name for f in dataclasses.fields(fc.Interval)}


# ---------------------------------------------------------------------------
# the P0 split - production record vs post-hoc evaluation
# ---------------------------------------------------------------------------


def test_a_forecast_record_has_no_evaluation_field():
    names = {f.name for f in dataclasses.fields(fc.ForecastRecord)}
    assert "evaluation" not in names
    record = fc.ForecastRecord(**_record())
    assert not hasattr(record, "evaluation")
    assert fc.ForecastEvaluation is not fc.ForecastRecord


def test_a_producer_cannot_construct_a_forecast_evaluation():
    # No terminal at all, and a terminal the producer minted itself: both refused.
    with pytest.raises(fc.ForecastContractError):
        fc.ForecastEvaluation(**_evaluation())
    with pytest.raises(fc.ForecastContractError) as excinfo:
        fc.ForecastEvaluation(**_evaluation(), _writer=object())
    assert "prediction ledger only" in str(excinfo.value)

    # With the ledger's terminal the same payload constructs.
    minted = fc.ForecastEvaluation(**_evaluation(), _writer=fc._ledger_writer_token())
    assert minted.forecast_id == "fid-1"
    assert minted._writer is fc._ledger_writer_token()


# ---------------------------------------------------------------------------
# rules 3-4 - the closed reason-code vocabulary
# ---------------------------------------------------------------------------


def test_a_non_ok_row_carries_a_closed_vocabulary_code():
    for bad in ("", None, "because the model was unsure"):
        with pytest.raises(fc.ForecastContractError):
            fc.ForecastRecord(**_record(status="unavailable", value=None, reason_code=bad))

    # A declined row cannot borrow an `unavailable` code, and vice versa.
    with pytest.raises(fc.ForecastContractError) as excinfo:
        fc.ForecastRecord(**_record(status="declined", value=None, reason_code="GATE_OFF"))
    assert "closed" in str(excinfo.value)
    with pytest.raises(fc.ForecastContractError):
        fc.ForecastRecord(
            **_record(status="unavailable", value=None, reason_code="RETURN_LEVEL_NOT_ADMITTED")
        )

    declined = fc.ForecastRecord(
        **_record(status="declined", value=None, reason_code="RETURN_RANK_NOT_ADMITTED")
    )
    assert declined.value is None
    assert declined.reason_code in fc.DECLINED_REASON_CODES


# ---------------------------------------------------------------------------
# rules 8-9 - identity, location, and mandatory provenance
# ---------------------------------------------------------------------------


def test_producer_id_is_not_a_code_path_and_differs_from_implementation_ref():
    with pytest.raises(fc.ForecastContractError):
        fc.ForecastRecord(**_record(producer_id="strategies/long_memory.py::rv_forecast"))
    with pytest.raises(fc.ForecastContractError):
        fc.ForecastRecord(
            **_record(
                producer_id="strategies/long_memory.py::rv_forecast",
                implementation_ref="strategies/long_memory.py::rv_forecast",
            )
        )
    with pytest.raises(fc.ForecastContractError):
        fc.ForecastRecord(**_record(implementation_ref="strategies/long_memory.py"))


def test_provenance_is_mandatory_with_no_default():
    required = {"data_snapshot_id", "padded", "calendar_id"}
    fields = {f.name: f for f in dataclasses.fields(fc.Provenance)}
    for name in required:
        assert fields[name].default is dataclasses.MISSING
        assert fields[name].default_factory is dataclasses.MISSING

    partial = _provenance()
    del partial["padded"]
    with pytest.raises(fc.ForecastContractError) as excinfo:
        fc.ForecastRecord(**_record(provenance=partial))
    assert "padded" in str(excinfo.value)

    with pytest.raises(fc.ForecastContractError):
        fc.ForecastRecord(**_record(target=_target(unit=None)))
