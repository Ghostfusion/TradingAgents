"""Tests for P1: 3rd-order Greeks (speed/zomma), vol-surface shape (RR/BF/TS),
put-call parity screen."""

import pytest

from tradingagents.strategies.options_math import black76
from tradingagents.strategies.options_surface import (
    parity_violation,
    surface_shape,
    term_structure_slope,
)

pytestmark = pytest.mark.timeout(60)


def _mk_rows(call_ivs: list[float], put_ivs: list[float], spot: float = 100.0,
             strikes: list[float] | None = None, days: int = 30) -> list[dict]:
    """Synthetic chain: strikes around spot, per-side IVs in order."""
    k = strikes or [80.0, 90.0, 100.0, 110.0, 120.0]
    rows = []
    for side, ivs in (("call", call_ivs), ("put", put_ivs)):
        for i, kk in enumerate(k):
            iv = ivs[i] if i < len(ivs) else ivs[-1]
            rows.append({"strike": kk, "iv": iv, "days_to_expiry": days,
                         "spot": spot, "side": side})
    return rows


# --- speed / zomma ---------------------------------------------------------


def test_black76_returns_speed_and_zomma():
    g = black76(100.0, 100.0, 0.25, 0.25, "call", 0.0)
    assert "speed" in g and "zomma" in g
    assert g["speed"] is not None and g["zomma"] is not None
    # speed = -gamma*(1+d1/(sig*sqrt(T)))/F ; d1 ~ 0 ATM -> near -gamma/F.
    assert g["speed"] < 0
    # zomma = gamma*(d1*d2-1)/sig ; ATM d1*d2 ~ -0.03 -> zomma ~ -gamma*~1/sig < 0.
    assert g["zomma"] < 0


def test_black76_speed_zomma_none_safe():
    g = black76(None, 100.0, 0.25, 0.25, "call", 0.0)
    assert g["speed"] is None and g["zomma"] is None
    g2 = black76(100.0, 100.0, 0.25, 0.0, "call", 0.0)
    assert g2["speed"] is None and g2["zomma"] is None


def test_speed_zomma_consistency():
    """Numeric: d(speed)/dS should approach zomma's scale; just check sign of
    gamma-vs-vol sensitivity: zomma = d(gamma)/d(vol) — increasing vol should
    decrease the (negative) ATM gamma magnitude -> zomma tracks that."""
    g1 = black76(100.0, 100.0, 0.25, 0.20, "call", 0.0)
    g2 = black76(100.0, 100.0, 0.25, 0.30, "call", 0.0)
    # gamma*vol roughly constant (ATM): zomma ~ (d2*d1-1)*gamma/sig < 0 and
    # gamma decreases with sig; verify gamma(20) > gamma(30).
    assert g1["gamma"] > g2["gamma"]


# --- surface shape ---------------------------------------------------------


def test_surface_shape_negative_rr_when_puts_rich():
    rows = _mk_rows(call_ivs=[0.22, 0.23, 0.25, 0.27, 0.30],
                    put_ivs=[0.30, 0.28, 0.26, 0.25, 0.24])
    s = surface_shape(rows)
    assert s["rr25"] is not None and s["rr25"] < 0  # puts rich -> RR negative
    assert s["bf25"] is not None
    assert s["n"] == len(rows)


def test_surface_shape_positive_rr_when_calls_rich():
    rows = _mk_rows(call_ivs=[0.30, 0.28, 0.26, 0.25, 0.24],
                    put_ivs=[0.22, 0.23, 0.25, 0.27, 0.30])
    s = surface_shape(rows)
    assert s["rr25"] is not None and s["rr25"] > 0


def test_surface_shape_degrade():
    # Single strike per side (spot 100, strike 80 = deep-ITM call) -> no
    # bracketing 25-delta pair -> None (never extrapolate).
    rows = _mk_rows(call_ivs=[0.25], put_ivs=[0.25], strikes=[80.0])
    s = surface_shape(rows)
    assert s["rr25"] is None and s["bf25"] is None
    assert s["n"] == 2


def test_term_structure_slope():
    assert term_structure_slope(0.20, 0.24) == pytest.approx(0.04)
    assert term_structure_slope(None, 0.24) is None


# --- parity ----------------------------------------------------------------


def test_parity_fair():
    # C - P = 5, S - K = 100 - 95 = 5 (t->0, r=0) -> no violation.
    v = parity_violation(5.0, 0.0, 100.0, 95.0, 1e-6, cost_bps=5.0)
    assert v["direction"] == "fair" and v["flag"] is False


def test_parity_call_rich():
    # C - P = 10 but parity says 5 -> call rich (conversion).
    v = parity_violation(10.0, 0.0, 100.0, 95.0, 1e-6, cost_bps=5.0)
    assert v["direction"] == "call_rich" and v["flag"] is True
    assert v["violation_bps"] == pytest.approx(500.0)  # 5/100 * 1e4


def test_parity_put_rich():
    # C - P = 2 vs parity 5 -> put rich (reversal).
    v = parity_violation(2.0, 0.0, 100.0, 95.0, 1e-6, cost_bps=5.0)
    assert v["direction"] == "put_rich"


def test_parity_cost_band_respect():
    # small violation under the band -> fair (not actionable).
    v = parity_violation(5.4, 0.0, 100.0, 95.0, 1e-6, cost_bps=50.0)
    assert v["direction"] == "fair"


def test_parity_none_safe():
    v = parity_violation(None, 0.0, 100.0, 95.0, 1e-6)
    assert v["violation_bps"] is None and v["direction"] is None
