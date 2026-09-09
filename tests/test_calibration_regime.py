"""Tests for per-regime confidence calibration (strategies/calibration.py).

Extends the existing G2 bucket calibration with regime partitioning so a
confidence declared under one market regime maps to THAT regime's realized
win-rate (falling back to the global/all table when the regime is thin).
Pure; no IO/LLM.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.calibration import (
    calibrated_confidence_by_regime,
    fit_buckets,
    fit_buckets_by_regime,
    isotonic_calibrate,
)


@pytest.mark.timeout(30)
class TestCalibrationRegime:
    def _entries(self, regime="risk_on"):
        # 10 stamps in the 0.8-0.9 bucket: 9 wins -> win_rate 0.9.
        return [
            {"confidence": 0.85, "won": True, "regime": regime}
            for _ in range(9)
        ] + [
            {"confidence": 0.85, "won": False, "regime": regime}
            for _ in range(1)
        ]

    def test_fit_buckets_by_regime_partitions(self):
        rows = self._entries("risk_on")
        tables = fit_buckets_by_regime(rows)
        assert "risk_on" in tables
        assert tables["risk_on"][(0.8, 0.9)]["n"] == 10
        assert tables["risk_on"][(0.8, 0.9)]["win_rate"] == pytest.approx(0.9)

    def test_regime_missing_rows_goes_to_all(self):
        rows = [{"confidence": 0.7, "won": True} for _ in range(6)]
        tables = fit_buckets_by_regime(rows)
        assert "_all" in tables
        assert tables["_all"][(0.7, 0.8)]["n"] == 6

    def test_calibrated_by_regime_prefers_regime(self):
        deep = {"deep": fit_buckets(self._entries("deep"))}
        # The regime table recalibrates 0.85 -> 0.9 (n=10 >= min_n=5).
        assert calibrated_confidence_by_regime(0.85, deep, regime="deep") == pytest.approx(0.9)

    def test_calibrated_by_regime_falls_back_to_all(self):
        # A thin regime (n < min_n) must not re-map; fall back to _all.
        tables = {
            "risk": {  # only 2 stamps -> below min_n
                (0.8, 0.9): {"n": 2, "win_rate": 0.5},
            },
            "_all": fit_buckets(self._entries("_all")),
        }
        p = calibrated_confidence_by_regime(0.85, tables, regime="risk", min_n=5)
        assert p == pytest.approx(0.9)  # from _all

    def test_isotonic_degrades_without_rows(self):
        assert isotonic_calibrate([]) is None
        assert isotonic_calibrate([{"confidence": 0.9, "won": True}]) is None

    def test_isotonic_returns_estimator_when_available(self):
        # sklearn optional: if installed this returns a fitted calibrator
        # usable via .predict; if not it returns None (never raises).
        iso = isotonic_calibrate(self._entries())
        if iso is not None:
            pred = [float(v) for v in iso.predict([0.1, 0.5, 0.9])]
            assert all(0.0 <= v <= 1.0 for v in pred)
            assert pred == sorted(pred)
