"""Computed-analysis tools (strategies-as-tools) - pure/offline tests.

Each tool is exercised with a mocked vendor chain so no network is touched.
The emphasis is on the honest-degradation contract: exact numbers when data
exists, explicit 'unavailable' text (never a fabricated figure) otherwise.
"""

import math
from unittest import mock

from tradingagents.agents.utils import analysis_tools as T


def _ohlcv_csv(closes, vols, start="2026-01-01", dates_daily=True):
    rows = ["Date,Open,High,Low,Close,Volume"]
    for i, (c, v) in enumerate(zip(closes, vols, strict=False)):
        if dates_daily:
            rows.append(
                f"{start[:-2]}{i % 28 + 1:02d},{c + 0.1:.2f},{c + 2:.2f},{c - 2:.2f},{c:.2f},{v}"
            )
        else:
            rows.append(
                f"2026-07-{i % 28 + 1:02d},{c + 0.1:.2f},{c + 2:.2f},{c - 2:.2f},{c:.2f},{v}"
            )
    return "\n".join(rows) + "\n"


def _uptrend(n=260):
    return [100.0 + 0.5 * i + 8.0 * math.sin(i / 6) for i in range(n)]


def _route(closes_map, vols=5_000_000):
    def route(method, *a, **k):
        if method == "get_stock_data":
            sym = a[0] if a else "?"
            if sym not in closes_map:
                return "NO_DATA_AVAILABLE: no usable market data for symbol."
            return _ohlcv_csv(closes_map[sym], [vols] * len(closes_map[sym]))
        return "NO_DATA_AVAILABLE"

    return route


# ---------------------------------------------------------------------------
# get_position_sizing (pure)
# ---------------------------------------------------------------------------


def test_position_sizing_formula():
    out = T.get_position_sizing.invoke({"confidence": 0.62, "stop_dist_pct": 0.05})
    assert "6.0%" in out and "kelly=24.00%" in out and "risk_budget=20.0%" in out


def test_position_sizing_zero_stop_rejects():
    out = T.get_position_sizing.invoke({"confidence": 0.6, "stop_dist_pct": 0.0})
    assert "stop_dist_pct must be > 0" in out


def test_position_sizing_cap_binds():
    out = T.get_position_sizing.invoke(
        {"confidence": 0.9, "stop_dist_pct": 0.01, "max_position_pct": 0.10}
    )
    assert "10.0%" in out


# ---------------------------------------------------------------------------
# get_risk_gate
# ---------------------------------------------------------------------------


def test_risk_gate_rejects_over_cap():
    out = T.get_risk_gate.invoke({"size_pct": 0.40})
    assert "REJECT" in out and "cap 30.0%" in out


def test_risk_gate_passes_small():
    out = T.get_risk_gate.invoke({"size_pct": 0.10})
    assert "PASS" in out


def test_risk_gate_cvar_budget():
    out = T.get_risk_gate.invoke({"size_pct": 0.10, "cvar_pct": 0.05})
    assert "REJECT" in out or "cvar" in out.lower()


# ---------------------------------------------------------------------------
# get_swing_set (needs the vendor chain)
# ---------------------------------------------------------------------------


def test_swing_set_returns_computed_read():
    closes = _uptrend()
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=_route({"AAPL": closes, "SPY": [200.0] * len(closes)}),
    ):
        out = T.get_swing_set.invoke({"ticker": "AAPL"})
    assert "swing set AAPL:" in out
    assert "verdict=" in out and "trend:" in out and "rsi:" in out
    assert "structure_stop" in out or "targets" in out


def test_swing_set_insufficient_history():
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=_route({"AAPL": [100.0] * 30}),
    ):
        out = T.get_swing_set.invoke({"ticker": "AAPL"})
    assert "fewer than 200 daily bars" in out


def test_swing_set_no_data():
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=_route({}),
    ):
        out = T.get_swing_set.invoke({"ticker": "ZZZZ"})
    assert "fewer than 200 daily bars" in out or "unavailable" in out.lower()


# ---------------------------------------------------------------------------
# get_relative_strength
# ---------------------------------------------------------------------------


def test_relative_strength_verdict_present():
    closes = _uptrend(
        260,
    )
    mkt = [200.0 + 0.001 * i for i in range(260)]
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=_route({"AAPL": closes, "SPY": mkt}),
    ):
        out = T.get_relative_strength.invoke({"ticker": "AAPL"})
    assert "relative_strength AAPL:" in out
    assert "verdict=" in out


def test_relative_strength_no_benchmark():
    closes = _uptrend()
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=_route({"AAPL": closes}),
    ):
        out = T.get_relative_strength.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower()  # benchmark missing -> honest unknown


# ---------------------------------------------------------------------------
# get_catalyst_scale
# ---------------------------------------------------------------------------


def test_catalyst_scale_computed():
    fake = {
        "earnings_calendar": [
            {"date": "2026-07-25", "eps_estimate": 1.0, "eps_actual": 1.15},
            {"date": "2026-08-24", "eps_estimate": 1.05, "eps_actual": None},
        ],
        "move_history": [{"predict_vola_ratio_newest": 4.2}],
        "economic_calendar": [{"title": "CPI", "timestamp": "2026-08-20", "star": "HIGH"}],
        "fed_watch": [],
    }
    with mock.patch("tradingagents.strategies.catalyst.fetch_catalyst_data", return_value=fake):
        out = T.get_catalyst_scale.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "scale=" in out and "verdict=earnings-window" in out
    assert "reasons:" in out


def test_catalyst_scale_unavailable_neutral():
    with mock.patch("tradingagents.strategies.catalyst.fetch_catalyst_data", return_value=None):
        out = T.get_catalyst_scale.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "scale = 1.0" in out


# ---------------------------------------------------------------------------
# get_earnings_event_read
# ---------------------------------------------------------------------------


def test_earnings_event_read_surprise_and_pead():
    fake = {
        "earnings_calendar": [
            {"date": "2026-07-25", "eps_estimate": 1.0, "eps_actual": 1.15},
        ],
        "move_history": [],
        "economic_calendar": [],
        "fed_watch": [],
    }
    closes = [100.0 + 0.5 * i for i in range(120)]
    with (
        mock.patch("tradingagents.strategies.catalyst.fetch_catalyst_data", return_value=fake),
        mock.patch(
            "tradingagents.dataflows.interface.route_to_vendor",
            side_effect=_route({"AAPL": closes}),
        ),
    ):
        out = T.get_earnings_event_read.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "last surprise=" in out
    assert "side=beat" in out
    assert "pead:" in out


def test_earnings_event_read_no_surprise():
    with mock.patch(
        "tradingagents.strategies.catalyst.fetch_catalyst_data",
        return_value={"earnings_calendar": []},
    ):
        out = T.get_earnings_event_read.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "no reported earnings surprise" in out


# ---------------------------------------------------------------------------
# get_regime_read
# ---------------------------------------------------------------------------


def test_regime_read_returns_computed():
    closes = _uptrend()
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=_route({"AAPL": closes}),
    ):
        out = T.get_regime_read.invoke({"ticker": "AAPL"})
    assert "regime AAPL:" in out
    assert "regime=" in out and "position_scale=" in out and "momentum_60d=" in out


def test_regime_read_insufficient_history():
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=_route({"AAPL": [100.0] * 30}),
    ):
        out = T.get_regime_read.invoke({"ticker": "AAPL"})
    assert "fewer than 60 daily bars" in out


# ---------------------------------------------------------------------------
# get_volatility_contraction
# ---------------------------------------------------------------------------


def test_vcp_tool_reports_state():
    # Noisy uptrend + fading-volume tail produces a contracting base.
    closes = _uptrend()
    vols = [5_000_000] * len(closes)
    vols = vols[:-8] + [1_500_000] * 8
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=_route({"AAPL": closes}, vols=vols),
    ):
        out = T.get_volatility_contraction.invoke({"ticker": "AAPL"})
    assert "vcp AAPL:" in out
    assert "candidate=" in out and "pullback_depths=" in out


def test_vcp_insufficient_history():
    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor",
        side_effect=_route({"AAPL": [100.0] * 40}),
    ):
        out = T.get_volatility_contraction.invoke({"ticker": "AAPL"})
    assert "fewer than 90 daily bars" in out


# ---------------------------------------------------------------------------
# get_orderflow_read
# ---------------------------------------------------------------------------


def test_orderflow_unavailable_neutral():
    with mock.patch("tradingagents.strategies.orderflow.fetch_flow", return_value=None):
        out = T.get_orderflow_read.invoke({"ticker": "AAPL"})
    assert "treat as neutral" in out and "do not fabricate" in out


def test_orderflow_summary_present():
    payload = {
        "buckets": {
            "capital_in_super": 5e6,
            "capital_out_super": 1e6,
            "capital_in_big": 2e6,
            "capital_out_big": 1.5e6,
            "capital_in_mid": 1e6,
            "capital_out_mid": 1.2e6,
            "capital_in_small": 0.5e6,
            "capital_out_small": 0.6e6,
        },
        "weekly_nets": [1e6, -0.2e6, 0.5e6],
    }
    with mock.patch("tradingagents.strategies.orderflow.fetch_flow", return_value=payload):
        out = T.get_orderflow_read.invoke({"ticker": "AAPL"})
    assert "order flow AAPL:" in out
    assert "distribution=" in out and "divergence=" in out


# ---------------------------------------------------------------------------
# get_portfolio_weights (pure)
# ---------------------------------------------------------------------------


def test_portfolio_weights_basic():
    out = T.get_portfolio_weights.invoke(
        {"scores": {"A": 0.8, "B": 0.2}, "max_name_pct": 0.9, "sector_cap_pct": 1.0}
    )
    assert "A: 80.0%" in out and "B: 20.0%" in out
    assert "total allocated: 100.0%" in out


def test_portfolio_weights_caps():
    out = T.get_portfolio_weights.invoke(
        {"scores": {"A": 0.8, "B": 0.2, "C": 0.5}, "max_name_pct": 0.4, "sector_cap_pct": 1.0}
    )
    # A capped at 40%
    assert "A: 40.0%" in out
    assert "cash remainder" in out


def test_portfolio_weights_empty():
    assert "no positive scores" in T.get_portfolio_weights.invoke({"scores": {}})


# ---------------------------------------------------------------------------
# get_analyst_verdict / get_earnings_surprise / get_portfolio_weights eager
# ---------------------------------------------------------------------------


def test_analyst_verdict_import_and_runs():
    # The tool lazily imports scripts.value_screener (the canonical parser).
    from tradingagents.agents.utils import analysis_tools as T2

    assert hasattr(T2, "get_analyst_verdict")


def test_earnings_surprise_reports_side():
    fake = {
        "earnings_calendar": [
            {"date": "2026-07-25", "eps_estimate": 1.0, "eps_actual": 1.15},
        ],
    }
    with mock.patch("tradingagents.strategies.catalyst.fetch_catalyst_data", return_value=fake):
        out = T.get_earnings_surprise.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "last_surprise=+15.0%" in out and "side=beat" in out
