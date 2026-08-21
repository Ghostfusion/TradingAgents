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


# ---------------------------------------------------------------------------
# Finnhub-backed tools (get_basic_financials / get_insider_activity /
# get_company_peers)
# ---------------------------------------------------------------------------


def test_basic_financials_direct_call():

    with mock.patch(
        "tradingagents.dataflows.finnhub._client",
        return_value=_FakeFinnhubClient(),
    ):
        out = T.get_basic_financials.invoke({"ticker": "AAPL"})
    assert "Basic Financials" in out and "epsGrowthQuarterlyYoy" in out


def test_insider_activity_direct_call():

    with mock.patch(
        "tradingagents.dataflows.finnhub._client",
        return_value=_FakeFinnhubClient(),
    ):
        out = T.get_insider_activity.invoke({"ticker": "AAPL"})
    assert "Insider Sentiment" in out and "Trend:" in out


def test_company_peers_direct_call():

    with mock.patch(
        "tradingagents.dataflows.finnhub._client",
        return_value=_FakeFinnhubClient(),
    ):
        out = T.get_company_peers.invoke({"ticker": "AAPL"})
    assert "Peers:" in out


class _FakeFinnhubClient:
    """Minimal finnhub.Client stand-in for the free-tier methods we wrapped."""

    def company_basic_financials(self, symbol, metric_type):
        return {
            "symbol": symbol,
            "metric": {
                "epsGrowthQuarterlyYoy": 29.13,
                "revenueGrowthTTMYoy": 14.24,
                "roeTTM": 137.2,
                "marketCapitalization": 4430136,
            },
        }

    def stock_insider_sentiment(self, symbol, _from=None, to=None):
        return {
            "data": [
                {"year": 2026, "month": 2, "change": -1000, "mspr": -10.2},
                {"year": 2026, "month": 1, "change": -2000, "mspr": -8.1},
            ]
        }

    def company_peers(self, symbol):
        return ["DELL", "HPQ", "SMCI"]


# --------------------------------------------------------------------------
# Decision-grounding tools (P0/P1/P2) - hermetic
# --------------------------------------------------------------------------


def test_exit_check_returns_stop_target_action():
    out = T.get_exit_check.invoke({"entry": 100.0, "close": 95.0, "atr": 3.0})
    assert "breakeven_stop=103.00" in out
    assert "target=107.00" in out  # close + 4*atr
    assert "action=stop" in out


def test_exit_check_requires_positive_atr():
    out = T.get_exit_check.invoke({"entry": 100.0, "close": 95.0, "atr": 0.0})
    assert "atr must be > 0" in out


def test_allocation_caps_weight():
    out = T.get_allocation.invoke(
        {"scores": {"A": 50, "B": 30, "C": 20, "D": 10}}
    )
    assert "Allocation plan" in out
    # every weight <= 25% max_name cap
    import re

    pcts = [float(x) for x in re.findall(rb"- [A-Z]+: ([0-9.]+)%", out.encode() if isinstance(out, str) else out)]
    assert all(x <= 25.0 for x in pcts)


def test_consensus_high_when_aligned():
    out = T.get_consensus.invoke({"ratings": ["Buy", "Buy", "Buy"]})
    assert "level=high" in out


def test_consensus_low_when_split():
    out = T.get_consensus.invoke({"ratings": ["Buy", "Hold", "Sell"]})
    assert "level=low" in out


def test_beat_miss_sizing_side_mult():
    out = T.get_beat_miss_sizing.invoke({"side": "beat", "catalyst": 1.0})
    assert "position_mult=" in out


def test_regime_components_uses_ohlcv(monkeypatch):
    fake = {"closes": _uptrend(260), "highs": _uptrend(260), "lows": _uptrend(260),
            "volumes": [100] * 260, "opens": _uptrend(260)}
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: fake)
    out = T.get_regime_components.invoke({"ticker": "AAPL"})
    assert "label=" in out
    assert "vol_pct=" in out


def test_regime_components_short_history_degrades(monkeypatch):
    fake = {"closes": [100.0, 101.0], "opens": [], "highs": [], "lows": [], "volumes": []}
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: fake)
    out = T.get_regime_components.invoke({"ticker": "AAPL"})
    assert "not enough price history" in out


def test_momentum_detail_uses_ohlcv(monkeypatch):
    n = 70
    closes = [100.0 + i for i in range(n)]
    highs = [100.0 + i + 0.5 for i in range(n)]
    lows = [100.0 + i - 0.5 for i in range(n)]
    vols = [1000] * n
    opens = closes[:]
    fake = {"closes": closes, "opens": opens, "highs": highs, "lows": lows, "volumes": vols}
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: fake)
    out = T.get_momentum_detail.invoke({"ticker": "AAPL"})
    assert "momentum detail AAPL" in out
    assert "rvol=" in out


def test_momentum_detail_empty_history_degrades(monkeypatch):
    fake = {"closes": [], "opens": [], "highs": [], "lows": [], "volumes": []}
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: fake)
    out = T.get_momentum_detail.invoke({"ticker": "AAPL"})
    assert "unavailable" in out



# --------------------------------------------------------------------------
# DCF valuation tool - hermetic (mock route_to_vendor)
# --------------------------------------------------------------------------
_CF_CSV = """# Cash Flow data for AAPL (annual)

,2025-09-30,2024-09-30,2023-09-30,2022-09-30
Operating Cash Flow,110000000000,95000000000,85000000000,78000000000
Capital Expenditure,-15000000000,-12000000000,-11000000000,-10000000000
Free Cash Flow,95000000000,83000000000,69000000000,68000000000
"""


def _dcf_side(method, *a, **k):
    return {
        "get_cashflow": _CF_CSV,
        "get_fundamentals": "Beta: 1.1\nMarket Cap: 3000000000000",
        "get_balance_sheet": "Cash Cash Equivalents: 60000000000\nTotal Debt: 110000000000",
        "get_macro_indicators": "## FRED 10Y\nLatest: 4.2",
        "get_stock_data": "",
    }.get(method, "")


def test_get_dcf_valuation_returns_fair_value(monkeypatch):
    monkeypatch.setattr(T, "route_to_vendor", _dcf_side)
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [200.0, 205.0, 210.0]})
    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})
    assert "dcf AAPL" in out
    assert "fair_value=" in out
    assert "wacc=" in out


def test_get_dcf_valuation_no_fcf_degrades(monkeypatch):
    def side(method, *a, **k):
        if method == "get_cashflow":
            return "NO_DATA_AVAILABLE: ..."
        return "Beta: 1.1\nMarket Cap: 3000000000000"
    monkeypatch.setattr(T, "route_to_vendor", side)
    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})
    assert "no usable free cash flow" in out


