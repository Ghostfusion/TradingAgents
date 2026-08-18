"""G2/G3 calibration + consensus unit tests (offline)."""

import pytest

from tradingagents.strategies.calibration import (
    fit_buckets, calibrated_confidence, calibration_table_text,
)
from tradingagents.strategies.consensus import (
    rating_to_number, agreement_score, consensus_from_score,
)


def test_fit_buckets():
    entries = [
        {"confidence": 0.65, "won": True},
        {"confidence": 0.65, "won": False},
        {"confidence": 0.72, "won": True},
        {"confidence": 0.72, "won": True},
    ]
    t = fit_buckets(entries)
    assert t[(0.60, 0.70)]["n"] == 2
    assert t[(0.60, 0.70)]["win_rate"] == 0.5
    assert t[(0.70, 0.80)]["win_rate"] == 1.0


def test_calibrated_identity_below_min():
    t = fit_buckets([{"confidence": 0.65, "won": True}])
    assert calibrated_confidence(0.65, t, min_n=5) == pytest.approx(0.65)


def test_calibrated_uses_bucket():
    t = fit_buckets([{"confidence": 0.65, "won": True},
                     {"confidence": 0.65, "won": False}] * 5)
    p = calibrated_confidence(0.65, t, min_n=5)
    assert p < 0.65  # realized 0.5 drags the declared 0.65 toward it


def test_calibration_text_nonempty():
    t = fit_buckets([{"confidence": 0.65, "won": True}])
    assert "calibration" in calibration_table_text(t).lower()
    assert "no calibration history" in calibration_table_text({}).lower()


def test_rating_to_number_and_agreement():
    assert rating_to_number("Buy") == 1.0
    assert rating_to_number("Sell") == -1.0
    assert rating_to_number("Hold") == 0.0
    assert rating_to_number("Nonsense") is None
    assert agreement_score(["Buy", "Sell"]) == 0.0
    assert agreement_score(["Buy", "Buy", "Overweight"]) == pytest.approx(0.75)
    assert agreement_score(["Buy"]) is None
    assert consensus_from_score(0.8) == "high"
    assert consensus_from_score(0.5) == "low"
    assert consensus_from_score(None) == "unknown"
