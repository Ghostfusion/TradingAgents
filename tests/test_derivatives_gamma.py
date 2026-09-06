"""Derivatives-flow A1/A2 tests (derivatives_gamma.py): chain gamma profile
(GEX) + OPEX calendar."""

import pytest

from tradingagents.strategies.derivatives_gamma import (
    gamma_regime,
    gex_per_strike,
    opex_dates,
    opex_note,
    opex_status,
)

pytestmark = pytest.mark.timeout(60)


def _rows(call_oi=100.0, put_oi=100.0, spot=100.0, strikes=(90.0, 110.0)):
    rows = []
    for k in strikes:
        rows.append({"strike": k, "iv": 0.3, "oi": call_oi, "side": "call"})
        rows.append({"strike": k, "iv": 0.3, "oi": put_oi, "side": "put"})
    return rows, spot, 0.0833  # ~30d


def test_gex_walls_and_regime_call_dominated():
    # Heavier call OI -> POSITIVE dealer gamma (long) + call wall at the
    # higher call concentration (mainstream SpotGamma-style convention).
    rows, spot, T = _rows(call_oi=200.0, put_oi=50.0)
    prof = gex_per_strike(rows, spot, T)
    assert prof["net_gamma"] > 0
    assert prof["gamma_regime"] == "long"
    assert prof["call_wall"] is not None
    assert prof["put_wall"] is not None


def test_gex_regime_put_dominated_short():
    rows, spot, T = _rows(call_oi=50.0, put_oi=200.0)
    prof = gex_per_strike(rows, spot, T)
    assert prof["net_gamma"] < 0
    assert prof["gamma_regime"] == "short"


def test_gex_wall_prefers_high_oi_strike():
    # Two call strikes, one with far higher OI -> that strike is the wall.
    rows = [
        {"strike": 100.0, "iv": 0.3, "oi": 500.0, "side": "call"},
        {"strike": 120.0, "iv": 0.3, "oi": 10.0, "side": "call"},
        {"strike": 100.0, "iv": 0.3, "oi": 100.0, "side": "put"},
        {"strike": 80.0, "iv": 0.3, "oi": 100.0, "side": "put"},
    ]
    prof = gex_per_strike(rows, 100.0, 0.0833)
    assert prof["call_wall"] == 100.0


def test_gex_none_na_when_no_oi():
    rows = [{"strike": 100.0, "iv": 0.3, "oi": None, "side": "call"}]
    prof = gex_per_strike(rows, 100.0, 0.0833)
    assert prof["net_gamma"] == 0.0
    assert prof["gamma_regime"] == "flat"
    assert prof["call_wall"] is None


def test_gamma_regime_none_never_fabricates():
    assert gamma_regime(None) is None


def test_opex_dates_third_fridays():
    dates = opex_dates(2026)
    assert len(dates) == 12
    for d in dates:
        assert d.weekday() == 4  # Friday
        assert 15 <= d.day <= 21  # third Friday


def test_opex_status_friday_of_expiry():
    # 2026-09-18 is the third Friday (OPEX).
    from datetime import date

    status = opex_status(date(2026, 9, 18))
    assert status["next_opex"] == "2026-09-18"
    assert status["days_to_next"] == 0
    assert status["in_opex_week"] is True
    assert status["quarterly"] is True  # Sep


def test_opex_status_unwind_window_after_expiry():
    from datetime import date

    status = opex_status(date(2026, 9, 21))  # Monday after 9/18
    assert status["post_opex_unwind"] is True


def test_opex_status_not_week_elsewhere():
    from datetime import date

    status = opex_status(date(2026, 9, 4))
    assert status["in_opex_week"] is False
    assert status["post_opex_unwind"] is False


def test_opex_note_renders():
    from datetime import date

    status = opex_status(date(2026, 9, 4))
    note = opex_note(status)
    assert "next OPEX" in note and "18" in note

    status_week = opex_status(date(2026, 9, 16))
    assert "in OPEX week" in opex_note(status_week)
