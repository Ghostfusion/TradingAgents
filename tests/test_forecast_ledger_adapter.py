"""Failing-first guards for the forecast ledger adapter (plan FL-5).

The prediction ledger is the ONLY writer of ``ForecastEvaluation`` and it
stores ``ForecastRecord`` rows append-only. These two tests pin the split the
contract buys: a producer cannot populate its own evaluation, and a later
evaluation never rewrites the production record it scores.

Offline, pure, sub-second: no vendor, no config, no network.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from tradingagents.strategies import forecast_contract as fc, prediction_ledger as ledger

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


def _record(**over):
    base = {
        "forecast_id": "fid-ledger-1",
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
        "forecast_id": "fid-ledger-1",
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


def _record_line(path, forecast_id):
    """The raw serialised text of the ``kind == "record"`` row for ``forecast_id``."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "record" and row.get("record", {}).get("forecast_id") == forecast_id:
            return line
    raise AssertionError(f"no record row for {forecast_id!r} in {path}")


def test_the_producer_cannot_populate_its_own_evaluation(tmp_path):
    # (a) a producer holding no ledger terminal cannot construct an evaluation.
    with pytest.raises(fc.ForecastContractError):
        fc.ForecastEvaluation(**_evaluation())

    # (b) a recorded forecast carries no evaluation surface at all.
    ledger.record_forecast(fc.ForecastRecord(**_record()), results_dir=str(tmp_path))
    stored = ledger.forecast_rows(str(tmp_path))
    assert len(stored) == 1
    row = stored[0]
    assert row["kind"] == "record"
    payload = row["record"]
    for forbidden in ("evaluation", "evaluations", "_writer"):
        assert forbidden not in payload
        assert forbidden not in row
    assert "evaluation" not in {f.name for f in dataclasses.fields(fc.ForecastRecord)}


def test_the_record_is_unchanged_by_a_later_evaluation(tmp_path):
    forecast_id = "fid-ledger-1"
    ledger.record_forecast(
        fc.ForecastRecord(**_record(forecast_id=forecast_id)), results_dir=str(tmp_path)
    )
    path = tmp_path / "forecasts.jsonl"
    before = _record_line(path, forecast_id)

    ledger.evaluate_forecast(
        forecast_id=forecast_id,
        realized_outcome=0.0003,
        evaluated_as_of=1_750_100_000.0,
        n_observations=1,
        scoring_rule="QLIKE",
        score=0.11,
        benchmark_ref="volatility.har_rv",
        benchmark_score=0.14,
        results_dir=str(tmp_path),
    )

    after = _record_line(path, forecast_id)
    # Byte-for-byte: the serialised record row text was not rewritten.
    assert after == before

    evaluations = [r for r in ledger.forecast_rows(str(tmp_path)) if r.get("kind") == "evaluation"]
    assert len(evaluations) == 1
    assert evaluations[0]["evaluation"]["forecast_id"] == forecast_id
    assert "_writer" not in evaluations[0]["evaluation"]
