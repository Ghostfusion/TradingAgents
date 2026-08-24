"""Computed-analysis tools (strategies-as-tools) - pure/offline tests.

Each tool is exercised with a mocked vendor chain so no network is touched.
The emphasis is on the honest-degradation contract: exact numbers when data
exists, explicit 'unavailable' text (never a fabricated figure) otherwise.
"""

import math
from unittest import mock

from tradingagents.agents.utils import analysis_tools as T, value_dip_tools as V


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
    out = T.get_allocation.invoke({"scores": {"A": 50, "B": 30, "C": 20, "D": 10}})
    assert "Allocation plan" in out
    # every weight <= 25% max_name cap
    import re

    pcts = [
        float(x)
        for x in re.findall(rb"- [A-Z]+: ([0-9.]+)%", out.encode() if isinstance(out, str) else out)
    ]
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
    fake = {
        "closes": _uptrend(260),
        "highs": _uptrend(260),
        "lows": _uptrend(260),
        "volumes": [100] * 260,
        "opens": _uptrend(260),
    }
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


# get_dcf_valuation resolves the financial background through
# statement_parsing.fetch_ticker (which routes via statement_parsing's own
# binding) AND calls route_to_vendor directly for the cashflow / macro inputs,
# so hermetic tests must patch both router bindings.
def _patch_dcf_vendors(monkeypatch, side):
    from tradingagents.dataflows import statement_parsing as _sp

    monkeypatch.setattr(T, "route_to_vendor", side)
    monkeypatch.setattr(_sp, "route_to_vendor", side)


def test_get_dcf_valuation_returns_fair_value(monkeypatch):
    _patch_dcf_vendors(monkeypatch, _dcf_side)
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [200.0, 205.0, 210.0]})
    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})
    assert "dcf AAPL" in out
    assert "fair_value=" in out
    assert "wacc=" in out


_CF_MD = """### Cash Flow (FY 2025)
| Item | FY2025 | FY2024 | FY2023 | FY2022 |
| --- | --- | --- | --- | --- |
| Operating Cash Flow | 110000000000 | 95000000000 | 85000000000 | 78000000000 |
| Capital Expenditure | -15000000000 | -12000000000 | -11000000000 | -10000000000 |
| Free Cash Flow | 95000000000 | 83000000000 | 69000000000 | 68000000000 |
"""


def _dcf_md_side(method, *a, **k):
    # moomoo-style per-period markdown cashflow (the default first vendor).
    return {
        "get_cashflow": _CF_MD,
        "get_fundamentals": "Beta: 1.35\nMarket Cap: 3000000000000",
        "get_balance_sheet": "Cash Cash Equivalents: 60000000000\nTotal Debt: 110000000000",
        "get_income_statement": "",
        "get_macro_indicators": "## FRED 10Y\nLatest: 4.2",
        "get_stock_data": "",
    }.get(method, "")


def test_get_dcf_valuation_moomoo_markdown_cashflow(monkeypatch):
    # The CSV-only FCF parser used to degrade DCF to "no usable free cash
    # flow" whenever moomoo (the default first vendor) served the cashflow;
    # the series must now come from the per-period markdown tables.
    _patch_dcf_vendors(monkeypatch, _dcf_md_side)
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [200.0, 205.0, 210.0]})
    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})
    assert "dcf AAPL" in out
    assert "fair_value=" in out


def test_get_dcf_valuation_no_fcf_degrades(monkeypatch):
    def side(method, *a, **k):
        if method == "get_cashflow":
            return "NO_DATA_AVAILABLE: ..."
        return "Beta: 1.1\nMarket Cap: 3000000000000"

    _patch_dcf_vendors(monkeypatch, side)
    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})
    assert "no usable free cash flow" in out


# --------------------------------------------------------------------------
# New decision-grounding tools (sector / quality / safety / composite / tail)
# --------------------------------------------------------------------------


def test_strategy_quality_explicit_returns():
    out = T.get_strategy_quality.invoke({"ticker": "AAPL", "returns": [0.01] * 50, "cost_bps": 0})
    assert "strategy quality AAPL" in out
    assert "net_cagr=" in out and "sharpe=" in out and "max_dd=" in out


def test_strategy_quality_derives_returns_from_ohlcv(monkeypatch):
    fake = {"closes": _uptrend(260), "opens": [], "highs": [], "lows": [], "volumes": []}
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: fake)
    out = T.get_strategy_quality.invoke({"ticker": "AAPL", "cost_bps": 5.0})
    assert "strategy quality AAPL" in out
    assert "n=" in out


def test_strategy_quality_too_few_returns_degrades(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [100.0, 101.0]})
    out = T.get_strategy_quality.invoke({"ticker": "AAPL"})
    assert "not enough price history" in out


def test_margin_of_safety_requires_intrinsic(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [90.0]})
    out = T.get_margin_of_safety.invoke({"ticker": "AAPL"})
    assert "pass a positive intrinsic estimate" in out


def test_margin_of_safety_computes_band(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [90.0]})
    out = T.get_margin_of_safety.invoke({"ticker": "AAPL", "intrinsic": 200.0})
    assert "margin of safety AAPL" in out
    assert "wide" in out  # (200-90)/200 = 55%


def test_margin_of_safety_negative_when_rich(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [150.0]})
    out = T.get_margin_of_safety.invoke({"ticker": "AAPL", "intrinsic": 100.0})
    assert "negative" in out


def test_composite_rank_requires_peers(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": _uptrend(260)})
    # finnhub peers unavailable -> only the ticker itself -> degrades
    with mock.patch(
        "tradingagents.dataflows.finnhub.get_company_peers_finnhub",
        return_value=[],
    ):
        out = T.get_composite_rank.invoke({"ticker": "AAPL"})
    assert "<2 comparable tickers" in out


def test_composite_rank_with_peers(monkeypatch):
    def _prices(t):
        if t == "MSFT":
            return {"closes": _uptrend(260)}
        return {"closes": [100.0 + 0.1 * i for i in range(260)]}

    monkeypatch.setattr(T, "_ohlcv", _prices)
    with mock.patch(
        "tradingagents.dataflows.finnhub.get_company_peers_finnhub",
        return_value=["MSFT", "ORCL"],
    ):
        out = T.get_composite_rank.invoke({"ticker": "AAPL"})
    assert "composite rank AAPL" in out
    assert "score=" in out


def test_tail_risk_computes_cvar(monkeypatch):
    n = 120
    closes = [100.0 + 0.5 * i + 20.0 * math.sin(i / 3) for i in range(n)]
    fake = {"closes": closes, "opens": [], "highs": [], "lows": [], "volumes": []}
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: fake)
    out = T.get_tail_risk.invoke({"ticker": "AAPL", "alpha": 0.05})
    assert "tail risk AAPL" in out
    assert "cvar=" in out and "stress_-10pct=" in out


def test_tail_risk_too_short_degrades(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [100.0, 101.0, 99.0]})
    out = T.get_tail_risk.invoke({"ticker": "AAPL"})
    assert "not enough price history" in out


def test_sector_rank_resolves_standing(monkeypatch):
    # SPDR ETFs all return an uptrend via _ohlcv; ticker sector known.
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": _uptrend(260)})

    def fake_fetch_sector(ticker):
        return "Technology" if ticker == "AAPL" else None

    with mock.patch(
        "tradingagents.dataflows.yfinance_sector.fetch_sector",
        side_effect=fake_fetch_sector,
    ):
        out = T.get_sector_rank.invoke({"ticker": "AAPL"})
    assert "sector rank AAPL" in out
    assert "top3_3m=" in out and "standing=" in out


def test_sector_rank_no_spdr_history_degrades(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": []})
    out = T.get_sector_rank.invoke({"ticker": "AAPL"})
    assert "no SPDR history" in out


def test_credit_spread_read_uses_oas_series(monkeypatch):
    # No FRED data -> explicit unavailable (no-fabrication).
    monkeypatch.setattr(T, "route_to_vendor", lambda *a, **k: "NO_DATA_AVAILABLE")
    out = T.get_credit_spread_read.invoke({"current_date": "2026-08-19"})
    assert "unavailable" in out


def test_credit_spread_read_band_from_latest(monkeypatch):
    def side(method, *a, **k):
        vals = {
            "hy_oas": "FRED: **Latest:** 3.90 (2026-08-19)",
            "ccc_oas": "FRED: **Latest:** 10.30 (2026-08-19)",
            "bb_oas": "FRED: **Latest:** 1.63 (2026-08-19)",
        }
        return vals.get(a[0], "NO_DATA_AVAILABLE")

    monkeypatch.setattr(T, "route_to_vendor", side)
    out = T.get_credit_spread_read.invoke({"current_date": "2026-08-19"})
    assert "level=moderate" in out
    assert "scale=0.85" in out
    assert "ccc_oas=10.30%" in out


def test_credit_spread_read_degrades_with_no_key(monkeypatch):
    monkeypatch.setattr(T, "route_to_vendor", lambda *a, **k: "NO_DATA_AVAILABLE")
    out = T.get_credit_spread_read.invoke({"current_date": "2026-08-19"})
    assert "FRED" in out or "unavailable" in out


# --------------------------------------------------------------------------
# get_session_discipline (market analyst) - session_flags + psych levels
# --------------------------------------------------------------------------


def test_session_discipline_reports_walk_away(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [100.0, 101.0, 102.0]})
    out = T.get_session_discipline.invoke({"ticker": "AAPL", "peak_pnl": 0.04, "current_pnl": 0.01})
    assert "session discipline AAPL" in out
    assert "walk_away=" in out
    assert "giveback_50=" in out  # 50% giveback (0.04 -> 0.01) should be True
    assert "max_daily_loss_hit=" in out


def test_session_discipline_past_optimal_window_flag(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [102.0]})
    out = T.get_session_discipline.invoke({"ticker": "AAPL"})
    assert "past_optimal_window=" in out
    assert "no_quality_setups=" in out


def test_session_discipline_no_price_degrades(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": []})
    out = T.get_session_discipline.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower()


# --------------------------------------------------------------------------
# get_earnings_quality (fundamentals analyst) - accruals + trap verdict
# --------------------------------------------------------------------------


def _eq_canonical():
    """Canonical line-items dict a mocked fetch_ticker would return."""
    return {
        "net_income": 100e6,
        "operating_cashflow": 45e6,
        "total_assets": 1.0e9,
        "revenue": 900e6,
        "current_assets": 300e6,
        "current_liabilities": 150e6,
        "retained_earnings": 200e6,
        "sector": "Technology",
    }


def test_earnings_quality_reports_accruals(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda ticker, date: _eq_canonical())
    out = T.get_earnings_quality.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "earnings quality AAPL" in out
    assert "accrual_ratio=" in out  # (100 - 45) / 1000 = 0.055 (moderate)
    assert "trap_risk=" in out


def test_earnings_quality_high_accruals_flagged(monkeypatch):
    from tradingagents.dataflows import statement_parsing as sp

    def fake_fetch(ticker, date):
        fin = _eq_canonical()
        fin["net_income"] = 200e6  # accrual = 155e6 / 1e9 = 0.155 (risk)
        return fin

    monkeypatch.setattr(sp, "fetch_ticker", fake_fetch)
    monkeypatch.setattr(sp, "screen_ticker", lambda ticker, fin: {})
    out = T.get_earnings_quality.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "0.155" in out
    assert "low-earnings-quality-risk" in out


def test_earnings_quality_no_data_degrades(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda ticker, date: {})
    out = T.get_earnings_quality.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "unavailable" in out.lower()


# --------------------------------------------------------------------------
# Value Dip + Swing hybrid tools (value_dip_tools) - computed signals
# --------------------------------------------------------------------------


def _vdip_ohlcv():
    """A sustained dip series: RSI <= 35, %b <= 0.10 (oversold)."""
    closes = []
    px = 140.0
    for i in range(60):
        drift = -1.2
        if i % 5 == 2:
            drift = 0.3
        px += drift
        closes.append(px)
    return {
        "closes": closes,
        "highs": [c + 1.0 for c in closes],
        "lows": [c - 1.0 for c in closes],
        "volumes": [1_000_000] * len(closes),
        "opens": closes[:],
        "dates": [f"2026-{i % 12 + 1:02d}-{(i % 27) + 1:02d}" for i in range(len(closes))],
    }


def _vdip_fundamentals_markdown():
    """Moomoo-style concatenated fundamentals markdown with 4 periods, each
    carrying Diluted EPS / Free Cash Flow / EBITDA rows (income+balance+cashflow
    concatenated into one payload, newest first)."""
    lines = ["## Income Statement — TEST", ""]
    for year, eps, fcf, ebitda in (
        ("2026", "5.00", "10.00B", "50.00B"),
        ("2025", "4.50", "9.00B", "45.00B"),
        ("2024", "4.00", "8.00B", "40.00B"),
        ("2023", "3.50", "7.00B", "35.00B"),
    ):
        lines.append(f"### {year}  (FY {year}, currency: USD)")
        lines += [
            "| Item | Value | YoY | QoQ |",
            "| --- | --- | --- | --- |",
            f"| Diluted EPS | {eps} | -- | -- |",
            f"| EBITDA | {ebitda} | -- | -- |",
            f"| Free Cash Flow | {fcf} | -- | -- |",
            "",
        ]
    return "\n".join(lines)


def test_bollinger_pct_b_computes_entry_zone(monkeypatch):
    monkeypatch.setattr(V, "_ohlcv", lambda ticker: _vdip_ohlcv())
    out = V.get_bollinger_pct_b.invoke({"ticker": "AAPL"})
    assert "bollinger %b AAPL" in out
    assert "entry-zone" in out or "lower-band" in out


def test_bollinger_pct_b_insufficient_history_degrades(monkeypatch):
    monkeypatch.setattr(V, "_ohlcv", lambda ticker: {"closes": [100.0, 101.0]})
    out = V.get_bollinger_pct_b.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower()


def test_tranche_plan_computes_levels(monkeypatch):
    monkeypatch.setattr(V, "_ohlcv", lambda ticker: _vdip_ohlcv())
    out = V.get_tranche_plan.invoke({"ticker": "AAPL"})
    assert "tranche plan AAPL" in out
    assert "P1=" in out and "P2=" in out and "P3=" in out
    assert "stop=" in out and "avg_entry=" in out
    assert "blended_rr=" in out and "risk_ok=" in out


def test_tranche_plan_bad_weights_degrade(monkeypatch):
    monkeypatch.setattr(V, "_ohlcv", lambda ticker: _vdip_ohlcv())
    out = V.get_tranche_plan.invoke({"ticker": "AAPL", "weights": "0.5,0.5"})
    assert "unavailable" in out.lower() or "weights" in out


def test_tranche_plan_no_price_degrades(monkeypatch):
    monkeypatch.setattr(V, "_ohlcv", lambda ticker: {"closes": []})
    out = V.get_tranche_plan.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower()


def test_trade_expectancy_computes(monkeypatch):
    out = V.get_trade_expectancy.invoke(
        {"p_win": 0.6, "avg_win": 200.0, "avg_loss": 100.0, "rr": 2.4}
    )
    assert "trade expectancy" in out
    assert "E=$80.00" in out
    assert "breakeven_win_rate=29.4%" in out


def test_trade_expectancy_missing_inputs_degrades():
    out = V.get_trade_expectancy.invoke({"p_win": 0.6, "avg_win": 200.0, "avg_loss": None})
    assert "unavailable" in out.lower()


def test_fcf_yield_computes(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d: {"market_cap": 1e11})
    monkeypatch.setattr(
        V,
        "route_to_vendor",
        lambda method, *a, **k: (
            _vdip_fundamentals_markdown() if method == "get_cashflow" else "NO_DATA_AVAILABLE"
        ),
    )
    out = V.get_fcf_yield.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "fcf yield AAPL" in out
    assert "10.00%" in out  # 10B / 100B


def test_fcf_yield_missing_data_degrades(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d: {})
    monkeypatch.setattr(V, "route_to_vendor", lambda *a, **k: "NO_DATA_AVAILABLE")
    out = V.get_fcf_yield.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "unavailable" in out.lower()


def test_valuation_z_score_computes(monkeypatch):
    monkeypatch.setattr(V, "_ohlcv", lambda ticker: _vdip_ohlcv())
    monkeypatch.setattr(
        V,
        "route_to_vendor",
        lambda method, *a, **k: (
            _vdip_fundamentals_markdown() if method == "get_fundamentals" else "NO_DATA_AVAILABLE"
        ),
    )
    out = V.get_valuation_z_score.invoke(
        {"ticker": "AAPL", "current_date": "2026-08-19", "multiple": "pe"}
    )
    assert "valuation z-score AAPL (pe)" in out
    assert "z=" in out


def test_valuation_z_score_too_few_periods_degrades(monkeypatch):
    monkeypatch.setattr(V, "_ohlcv", lambda ticker: _vdip_ohlcv())
    short = "\n".join(
        [
            "### 2026  (FY 2026, currency: USD)",
            "| Item | Value | YoY | QoQ |",
            "| --- | --- | --- | --- |",
            "| Diluted EPS | 5.00 | -- | -- |",
            "",
        ]
    )
    monkeypatch.setattr(
        V,
        "route_to_vendor",
        lambda method, *a, **k: short if method == "get_fundamentals" else "NO_DATA_AVAILABLE",
    )
    out = V.get_valuation_z_score.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "unavailable" in out.lower()


def test_value_dip_setup_reports_matrix(monkeypatch):
    monkeypatch.setattr(V, "_ohlcv", lambda ticker: _vdip_ohlcv())
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d: {"market_cap": 1e11})
    monkeypatch.setattr(
        V,
        "route_to_vendor",
        lambda method, *a, **k: (
            _vdip_fundamentals_markdown() if method == "get_cashflow" else "NO_DATA_AVAILABLE"
        ),
    )
    monkeypatch.setattr(V, "margin_of_safety_impl", lambda dcf_out, closes: 0.25)
    out = V.get_value_dip_setup.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "value dip setup AAPL" in out
    assert "value_floor" in out and "technical_entry" in out
    assert "candidate=" in out


def test_value_dip_setup_no_data_degrades(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d: {})
    out = V.get_value_dip_setup.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "unavailable" in out.lower()


# --------------------------------------------------------------------------
# Value Dip gap tools: balance sheet, MACD divergence, VDU ladder, support,
# decline driver
# --------------------------------------------------------------------------


def test_balance_sheet_health_computes(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d: {
            "total_debt": 400e6,
            "total_equity": 1e9,
            "current_assets": 800e6,
            "current_liabilities": 300e6,
        },
    )
    out = V.get_balance_sheet_health.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "balance sheet health AAPL" in out
    assert "pass=True" in out  # d_e 0.4 < 1, cr 2.67 > 1.5
    assert "d_e=0.40" in out


def test_balance_sheet_health_degrades(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d: {})
    out = V.get_balance_sheet_health.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "unavailable" in out.lower()


def test_macd_divergence_reports_verdict(monkeypatch):
    closes, highs, lows, vols = _vdip_dip_trigger()
    monkeypatch.setattr(
        V,
        "_ohlcv",
        lambda ticker: {
            "closes": closes,
            "lows": lows,
            "highs": highs,
            "volumes": vols,
            "opens": closes,
        },
    )
    out = V.get_macd_divergence.invoke({"ticker": "AAPL"})
    assert "macd divergence AAPL" in out
    assert "verdict=" in out and "bullish=" in out


def test_macd_divergence_short_history_degrades(monkeypatch):
    monkeypatch.setattr(
        V, "_ohlcv", lambda ticker: {"closes": [100.0, 101.0], "lows": [99.0, 100.0]}
    )
    out = V.get_macd_divergence.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower()


def test_vdu_entry_setup_reports_candidate(monkeypatch):
    closes, highs, lows, vols = _vdip_dip_trigger()
    monkeypatch.setattr(
        V,
        "_ohlcv",
        lambda ticker: {
            "closes": closes,
            "lows": lows,
            "highs": highs,
            "volumes": vols,
            "opens": closes,
        },
    )
    out = V.get_vdu_entry_setup.invoke({"ticker": "AAPL"})
    assert "vdu entry setup AAPL" in out
    assert "candidate=" in out


def test_support_structure_requires_history(monkeypatch):
    monkeypatch.setattr(
        V,
        "_ohlcv",
        lambda ticker: {
            "closes": [1.0] * 50,
            "lows": [1.0] * 50,
            "highs": [1.0] * 50,
            "volumes": [1] * 50,
        },
    )
    out = V.get_support_structure.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower() or "need 200+ closes" in out


def test_decline_driver_reports_verdict(monkeypatch):
    fin = {
        "market_cap": 1e11,
        "total_equity": 1e9,
        "net_income": 150e6,
        "total_debt": 300e6,
        "current_assets": 800e6,
        "current_liabilities": 300e6,
    }
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d: fin)
    monkeypatch.setattr(V, "route_to_vendor", lambda *a, **k: "NO_DATA_AVAILABLE")
    monkeypatch.setattr(
        V,
        "_ohlcv",
        lambda ticker: {
            "closes": _vdip_closes(),
            "lows": _vdip_closes(),
            "highs": [c + 1 for c in _vdip_closes()],
            "volumes": [1e6] * len(_vdip_closes()),
            "opens": _vdip_closes(),
        },
    )
    monkeypatch.setattr(V, "_trap_level_from_fin", lambda *a, **k: None)
    monkeypatch.setattr(V, "_accrual_from_fin", lambda *a, **k: None)
    out = V.get_decline_driver_check.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "decline driver AAPL" in out
    assert "verdict=" in out


def _vdip_closes():
    closes = []
    px = 100.0
    for i in range(160):
        px += -0.3 + 0.8 * math.sin(i / 7)
        closes.append(px)
    return closes


def _vdip_dip_trigger():
    closes, highs, lows = [], [], []
    px = 200.0
    for n, drift in [(100, -0.15), (13, -1.2), (5, 0.4), (7, -0.2), (14, 0.6), (4, -0.4), (7, 0.3)]:
        for _ in range(n):
            px += drift
            closes.append(px)
            highs.append(px + 1.0)
            lows.append(px - 1.0)
    closes.append(px + 4.0)
    highs.append(px + 5.0)
    lows.append(px - 0.5)
    vols = [2_000_000] * len(closes)
    for i in range(len(closes) - 8, len(closes) - 1):
        vols[i] = 300_000
    vols[-1] = 4_500_000
    return closes, highs, lows, vols


# --------------------------------------------------------------------------
# get_ratios (computed, free) - local derivation, no paid plan
# --------------------------------------------------------------------------


def test_get_ratios_returns_computed_block(monkeypatch):
    fin = {
        "market_cap": 1000e6, "total_debt": 200e6, "cash": 50e6,
        "operating_income": 120e6, "depreciation": 30e6, "revenue": 900e6,
        "net_income": 80e6, "total_equity": 500e6, "total_assets": 800e6,
        "operating_cashflow": 90e6, "capex": 30e6,
        "current_assets": 300e6, "current_liabilities": 150e6, "inventory": 60e6,
        "dividends_paid": 20e6,
    }
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d: fin)
    out = T.get_ratios.invoke({"ticker": "AAPL", "current_date": "2026-08-24"})
    assert "Ratios (computed)" in out
    assert "EV/EBITDA: 7.67" in out
    assert "ROE: 16.00%" in out
    assert "P/E: 12.50" in out
    assert "Quick: 1.60" in out


def test_get_ratios_degrades_when_no_data(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d: {})
    out = T.get_ratios.invoke({"ticker": "AAPL", "current_date": "2026-08-24"})
    assert "unavailable" in out.lower()
    assert "fabricate" in out.lower()
