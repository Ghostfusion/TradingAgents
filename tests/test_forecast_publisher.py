"""The publisher that gives FL-5 a record to write (plan FL-9).

Every test here is about one claim: the publisher never invents a provenance
value, and when it cannot state one truthfully it publishes nothing at all.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from tradingagents.strategies import forecast_publisher as fp, forecast_registry as fr


def _series(n=300, seed=1234, start=date(2020, 1, 1), bad=()):
    """A dated return series; ``bad`` marks positions carrying a NaN."""
    rng = random.Random(seed)
    return [
        (
            start + timedelta(days=i),
            float("nan") if i in bad else rng.gauss(0.0, 0.01),
        )
        for i in range(n)
    ]


def _kwargs(**over) -> dict:
    base = {
        "data_snapshot_id": "TEST_2026-10-03:abc123",
        "price_caliber": "adjusted",
        "market": "US",
        "code_revision": "deadbee",
    }
    base.update(over)
    return base


def test_the_identity_is_read_from_the_registry_row():
    """The record's identity is the ROW's - the publisher restates no literal."""
    row = next(r for r in fr.FORECAST_REGISTRY if r.producer_id == fp.RV_PRODUCER_ID)

    rec = fp.publish_realized_volatility_forecast(_series(), **_kwargs())

    assert rec.target == row.target
    assert rec.entity_scope == row.entity_scope
    assert rec.frequency == row.frequency
    assert rec.horizon_steps == row.horizon_steps
    assert rec.producer_id == row.producer_id
    assert rec.implementation_ref == row.implementation_ref
    assert rec.gate == row.gate


@pytest.mark.parametrize(
    "over",
    [
        {"data_snapshot_id": "   "},
        {"market": "XX"},
        {"price_caliber": "unknown"},
        {"price_caliber": None},
        {"code_revision": ""},
    ],
)
def test_an_identity_is_never_invented(over):
    """No true value for a mandatory field -> no record, not a plausible one."""
    with pytest.raises(fp.PublishRefusal):
        fp.publish_realized_volatility_forecast(_series(), **_kwargs(**over))


def test_an_unauthorized_producer_cannot_be_published():
    with pytest.raises(fp.PublishRefusal):
        fp.publish_realized_volatility_forecast(
            _series(), producer_id="nope.realized_volatility.v1", **_kwargs()
        )


def test_a_non_datable_label_yields_no_record():
    """Positions are not timestamps; `training_start` cannot be honestly filled."""
    with pytest.raises(fp.PublishRefusal):
        fp.publish_realized_volatility_forecast([0.01] * 300, **_kwargs())


def test_the_gate_off_row_is_a_named_absence():
    """The gate being off is recorded as a code, never as a missing row."""
    rec = fp.publish_realized_volatility_forecast(
        _series(), config={"enable_long_memory": False}, **_kwargs()
    )

    assert rec.status == "unavailable"
    assert rec.value is None
    assert rec.reason_code == "GATE_OFF"
    assert rec.provenance.effective_window == 0
    # Still fully provenanced: an absence has to be as reproducible as a value.
    assert rec.provenance.data_snapshot_id == "TEST_2026-10-03:abc123"
    assert rec.provenance.calendar_id == "XNYS"


def test_the_fitted_row_carries_a_real_parameter_hash():
    on = {"enable_long_memory": True}

    rec = fp.publish_realized_volatility_forecast(_series(), config=on, **_kwargs())
    other = fp.publish_realized_volatility_forecast(
        _series(seed=99), config=on, **_kwargs()
    )

    assert rec.status == "ok"
    assert isinstance(rec.value, float)
    assert rec.reason_code is None
    assert rec.provenance.effective_window >= 64
    assert rec.provenance.parameter_hash != other.provenance.parameter_hash


def test_dropped_observations_survive_into_provenance():
    """The engine drops non-finite pairs; the count still reaches the record."""
    rec = fp.publish_realized_volatility_forecast(
        _series(bad=(280, 285)), config={"enable_long_memory": True}, **_kwargs()
    )

    assert rec.provenance.missing_obs == 2
    assert rec.provenance.imputed_obs == 0
    assert rec.provenance.padded is False


@pytest.mark.parametrize(
    ("caliber", "expected"),
    [("adjusted", True), ("split_adjusted", False), ("raw", False)],
)
def test_adjusted_prices_follows_the_caliber_table(caliber, expected):
    """A return carries dividends or it does not - a split is not a dividend."""
    rec = fp.publish_realized_volatility_forecast(
        _series(), **_kwargs(price_caliber=caliber)
    )

    assert rec.provenance.adjusted_prices is expected
