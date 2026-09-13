"""Computed-analysis tools (strategies-as-tools) - pure/offline tests.

Each tool is exercised with a mocked vendor chain so no network is touched.
The emphasis is on the honest-degradation contract: exact numbers when data
exists, explicit 'unavailable' text (never a fabricated figure) otherwise.
"""

import io
import math
import re
from types import SimpleNamespace
from unittest import mock

import pandas as pd
import pytest

from tradingagents.agents.utils import analysis_tools as T, value_dip_tools as V


def _ohlcv_csv(closes, vols, start="2026-01-01", dates_daily=True):
    rows = ["Date,Open,High,Low,Close,Volume"]
    for i, (c, v) in enumerate(zip(closes, vols, strict=False)):
        # Monotone business-day dates so the analysis_tools._ohlcv order
        # normalization (ascending sort) does not collapse duplicate dates.
        day = (i // 21 + 1) % 12 + 1
        if dates_daily:
            rows.append(
                f"{start[:-2]}{day:02d},{c + 0.1:.2f},{c + 2:.2f},{c - 2:.2f},{c:.2f},{v}"
            )
        else:
            rows.append(
                f"2026-07-{day:02d},{c + 0.1:.2f},{c + 2:.2f},{c - 2:.2f},{c:.2f},{v}"
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



def _ohlcv_df(closes_map, vols=5_000_000):
    """Return a DataFrame for each ticker (the verified-source shape the
    _load_ohlcv_df seam now returns) instead of a CSV string."""

    def load(ticker):
        if ticker not in closes_map:
            return None
        csv = _ohlcv_csv(closes_map[ticker], [vols] * len(closes_map[ticker]))
        return pd.read_csv(io.StringIO(csv))

    return load

# ---------------------------------------------------------------------------
# get_position_sizing (pure)
# ---------------------------------------------------------------------------


def test_position_sizing_formula():
    out = T.get_position_sizing.invoke({"confidence": 0.62, "stop_dist_pct": 0.05})
    assert "6.0%" in out and "kelly=24.00%" in out and "risk_budget=20.0%" in out


def test_sector_rotation_curated_breadth_does_not_crash(monkeypatch):
    """Regression: the curated-industry breadth branch referenced ``_top_note``
    before assignment (UnboundLocalError) whenever it found constituents — the
    nxpi batch 2026-09-06 died on get_sector_rotation_screen. The curated
    branch must initialize ``_top_note`` exactly like the eodhd branch."""
    def _ohlcv_for(ticker):
        phase = sum(ord(c) for c in ticker) % 20
        closes = [100.0 + 0.5 * i + 8.0 * math.sin(i / 6 + phase) for i in range(260)]
        return {
            "closes": closes,
            "opens": closes,
            "highs": [c + 0.5 for c in closes],
            "lows": [c - 0.5 for c in closes],
            "volumes": [1_000_000.0] * 260,
        }

    monkeypatch.setattr(T, "_ohlcv", _ohlcv_for)
    out = T.get_sector_rotation_screen.func(
        enable_breadth=True, top_n=5, constituent_universe="curated"
    )
    assert "Sector Rotation Screen" in out
    # The curated branch completed (its constituent-screens block rendered) —
    # this is the exact path that raised UnboundLocalError before the fix.
    assert "### Constituent screens" in out


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


def test_composed_risk_gate_portfolio_drawdown_overrides_trade(monkeypatch):
    """The composed gate enforces PORTFOLIO gate > TRADE gate: a sustained
    dip (large realized book drawdown) must REJECT even a small, otherwise-
    fine trade size — the portfolio gate block outranks trade-level risk."""
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: _vdip_ohlcv())
    out = T.get_composed_risk_gate.invoke({"ticker": "AAPL", "size_pct": 0.02})
    assert "REJECT" in out
    assert "blocked by portfolio" in out
    assert "precedence=kill>portfolio>trade>liquidity>regime" in out


def test_composed_risk_gate_kill_switch_highest(monkeypatch):
    """A kill/halt input is the highest-precedence REJECT even when the book
    drawdown would also reject — the hierarchy reports the kill blocker."""
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: _vdip_ohlcv())
    out = T.get_composed_risk_gate.invoke(
        {"ticker": "AAPL", "size_pct": 0.02, "halt": True}
    )
    assert "REJECT" in out
    assert "blocked by kill_switch" in out


def test_composed_risk_gate_discloses_lack_of_drawdown_data(monkeypatch):
    """When the book drawdown can't be evaluated the tool says so (never
    silently pretends the portfolio gate passed)."""
    monkeypatch.setattr(
        T, "_ohlcv", lambda ticker: {"closes": [100.0] * 5, "highs": [100.0] * 5, "lows": [100.0] * 5}
    )
    out = T.get_composed_risk_gate.invoke({"ticker": "AAPL"})
    assert "drawdown unavailable" in out or "could not be evaluated" in out


# ---------------------------------------------------------------------------
# get_swing_set (needs the vendor chain)
# ---------------------------------------------------------------------------


def test_swing_set_returns_computed_read():
    closes = _uptrend()
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": closes, "SPY": [200.0] * len(closes)}),
    ):
        out = T.get_swing_set.invoke({"ticker": "AAPL"})
    assert "swing set AAPL:" in out
    assert "verdict=" in out and "trend:" in out and "rsi:" in out
    assert "structure_stop" in out or "targets" in out
    # The ATR feeding the structure stop / targets must be labeled ATR(14)
    # (AMZN 2026-09-09 review: ATR windows were confused).
    assert "ATR(14)" in out


def test_swing_set_insufficient_history():
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": [100.0] * 30}),
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
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": closes, "SPY": mkt}),
    ):
        out = T.get_relative_strength.invoke({"ticker": "AAPL"})
    assert "relative_strength AAPL:" in out
    assert "verdict=" in out


def test_relative_strength_no_benchmark():
    closes = _uptrend()
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": closes}),
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
    # Forward earnings 2026-08-24 sits inside the shipped hard-block window
    # (catalyst_hard_block_days default 5): the verdict is now the hard block,
    # not the legacy earnings-window soft scale. The HIGH macro event inside
    # 3d still scales x0.60 on top.
    assert "scale=" in out and "verdict=earnings-hard-block" in out
    assert "reasons:" in out


def test_fed_direction_classifies_against_current_rate():
    # IREN 2026-09-10 review loop: effective 3.63 -> current band 3.50-3.75,
    # so a modal 3.75-4.00% is a HIKE, not the 'hold' an earlier report
    # labeled. 3.50-3.75% would be a HOLD; a lower modal is a CUT.
    from tradingagents.strategies.catalyst import fed_direction

    assert fed_direction(3.63, "3.75-4.00%") == "HIKE"
    assert fed_direction(3.63, "3.50-3.75%") == "HOLD"
    assert fed_direction(4.00, "3.75-4.00%") == "CUT"
    assert fed_direction(3.13, "3.50-3.75%") == "HIKE"
    assert fed_direction(None, "3.75-4.00%") == "n/a"
    assert fed_direction(3.63, "") == "n/a"


def test_catalyst_scale_renders_modal_range_and_direction():
    # get_catalyst_scale must surface the modal target range, and when a
    # current_rate is supplied, the hold/hike/cut direction (IREN 2026-09-10).
    fake = {
        "earnings_calendar": [],
        "move_history": [],
        "economic_calendar": [],
        "fed_watch": [
            {"meeting_date": "2026-09-15", "target_range": "3.50-3.75%", "probability": 28.8},
            {"meeting_date": "2026-09-15", "target_range": "3.75-4.00%", "probability": 71.3},
        ],
    }
    with mock.patch("tradingagents.strategies.catalyst.fetch_catalyst_data", return_value=fake):
        out = T.get_catalyst_scale.invoke({
            "ticker": "IREN", "current_date": "2026-09-10", "current_rate": 3.63,
        })
    assert "modal_prob=0.7" in out or "modal_prob=71.3" in out
    assert "3.75-4.00%" in out
    assert "HIKE" in out


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
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": closes}),
    ):
        out = T.get_regime_read.invoke({"ticker": "AAPL"})
    assert "regime AAPL:" in out
    assert "regime=" in out and "position_scale=" in out and "momentum_60d=" in out


def test_regime_read_insufficient_history():
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": [100.0] * 30}),
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
    from tradingagents.dataflows.schema import VendorResult

    csv = _ohlcv_csv(closes, vols)

    def typed(method, *a, **k):
        if method == "get_stock_data":
            return VendorResult(results=csv, provider="test")
        return VendorResult(results="NO_DATA_AVAILABLE", error_kind="NoMarketDataError")

    with mock.patch(
        "tradingagents.dataflows.interface.route_to_vendor_typed",
        side_effect=typed,
    ):
        out = T.get_volatility_contraction.invoke({"ticker": "AAPL"})
    assert "vcp AAPL:" in out
    assert "candidate=" in out and "pullback_depths=" in out


def test_vcp_insufficient_history():
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": [100.0] * 40}),
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
    # Target is anchored at ENTRY (entry + 4*atr = 112), not close — anchoring
    # at the close made target_hit arithmetically impossible.
    assert "target=112.00" in out
    assert "action=stop" in out


def test_exit_check_requires_positive_atr():
    out = T.get_exit_check.invoke({"entry": 100.0, "close": 95.0, "atr": 0.0})
    assert "atr must be > 0" in out


def test_exit_plan_breakeven_and_giveback():
    # entry 100, atr 3, stop 97 -> structure BE = 1R (stop=None) or 1R from stop:
    # be_after_confirmation uses 1R = entry + 1*(entry-stop); giveback: peak_gain
    # 30% * 0.7 keep = 21% remaining -> EXIT when current 120 > 121? no -> hold.
    out = T.get_exit_plan.invoke(
        {"entry": 100.0, "atr": 3.0, "current": 120.0, "peak": 130.0, "stop": 97.0}
    )
    assert "exit_plan" in out
    assert "breakeven_stop" in out
    assert "trigger=" in out
    assert "giveback_" in out


def test_scaleout_plan_returns_tiers():
    out = T.get_scaleout_plan.invoke({"entry": 100.0, "stop": 95.0})
    assert "scaleout_plan" in out
    assert "t1=110.00" in out  # 2R target
    assert "sell_t1_fraction=50%" in out
    assert "breakeven_after_t1=True" in out


def test_payoff_asymmetry_omega():
    out = T.get_payoff_asymmetry.invoke(
        {"ticker": "X", "returns": [0.02, -0.01, 0.03, -0.01, 0.01, -0.005, 0.02]}
    )
    assert "payoff asymmetry X" in out
    assert "omega=" in out


def test_book_correlation_two_names():
    out = T.get_book_correlation.invoke(
        {"returns_by_name": {"A": [1, 2, 3, 4, 5], "B": [1.1, 2.2, 3.1, 4.2, 5.1]}}
    )
    assert "book_correlation" in out
    assert "n=2" in out


def test_book_correlation_degrades_few_names():
    out = T.get_book_correlation.invoke({"returns_by_name": {"A": [1, 2]}})
    assert "unavailable" in out.lower()


def test_consensus_tool_high_when_aligned():
    out = T.get_consensus.invoke({"ratings": ["Buy", "Buy", "Buy"]})
    assert "level=high" in out


def test_sentiment_computed_degrades_without_data(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.strategies.sentiment.compute_social_scores",
        lambda *a, **k: {},
    )
    out = T.get_sentiment_computed.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower()


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


def _corr_returns():
    # A and B track a common factor tightly; C is independent (a diversifier).
    base = [1.0 + 0.1 * ((i * 7) % 5) for i in range(40)]
    return {
        "A": [b + 0.001 * i for i, b in enumerate(base)],
        "B": [b * 1.01 for b in base],
        "C": [0.5 + 0.1 * ((i * 3) % 5) for i in range(40)],
    }


def test_allocation_correlation_penalty_when_enabled():
    from tradingagents.dataflows.config import set_config

    set_config(
        {
            "enable_correlation_penalty": True,
            "correlation_threshold": 0.4,
            "correlation_penalty_frac": 0.5,
        }
    )
    out = T.get_allocation.invoke(
        {
            "scores": {"A": 50, "B": 30, "C": 20},
            "returns_by_name": _corr_returns(),
            "max_name": 0.5,
        }
    )
    assert "correlation-penalized" in out
    # A (avg corr ~0.50) was cut below its raw 50% share; C (corr ~0.00) rose
    # above its raw 20% share after renormalization.
    assert "- A: 4" in out  # 41.7%
    assert "- C: 3" in out  # 33.3%


def test_allocation_correlation_penalty_gate_off():
    # Default gate off: returns_by_name is accepted but never applied.
    out = T.get_allocation.invoke(
        {
            "scores": {"A": 50, "B": 30, "C": 20},
            "returns_by_name": _corr_returns(),
            "max_name": 0.5,
        }
    )
    assert "correlation-penalized" not in out
    assert "- A: 50.0%" in out


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


def test_get_dcf_valuation_negative_ttm_degrades(monkeypatch):
    """A NEGATIVE trailing-12M FCF must degrade the DCF (honest), not silently
    fall back to the stale positive ANNUAL FCF: AMZN case (FY2025 +$7.7B vs
    TTM -$2.5B) previously output a fair value off the wrong basis."""
    def side(method, *a, **k):
        if method == "get_cashflow":
            return _qf_markdown([-18.171, 0.332, 0.43, 14.937])  # TTM = -2.472B
        return "Beta: 1.35\nMarket Cap: 3000000000000"

    _patch_dcf_vendors(monkeypatch, side)
    out = T.get_dcf_valuation.invoke({"ticker": "AMZN", "current_date": "2026-09-09"})
    assert "dcf unavailable" in out
    assert "trailing-12M FCF is not positive" in out


def test_get_dcf_valuation_positive_ttm_preferred(monkeypatch):
    """A POSITIVE trailing-12M FCF feeds the DCF directly (no annual detour)."""
    def side(method, *a, **k):
        if method == "get_cashflow":
            return _qf_markdown([10, 8, 9, 7])  # TTM = 34B
        return "Beta: 1.35\nMarket Cap: 3000000000000"

    _patch_dcf_vendors(monkeypatch, side)
    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})
    assert "dcf AAPL" in out
    assert "fair_value=" in out


# --------------------------------------------------------------------------
# New decision-grounding tools (sector / quality / safety / composite / tail)
# --------------------------------------------------------------------------


def test_strategy_quality_explicit_returns():
    out = T.get_strategy_quality.invoke({"ticker": "AAPL", "returns": [0.01] * 50, "cost_bps": 0})
    assert "strategy quality AAPL" in out
    assert "net_cagr=" in out and "sharpe=" in out and "max_dd(backtest)=" in out


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


def test_gamma_profile_unavailable_without_chain(monkeypatch):
    # No usable chain -> explicit unavailable, never raises.
    monkeypatch.setattr(T, "_options_chain_rows_lambda", lambda t: None)
    out = T.get_gamma_profile.invoke({"ticker": "AAPL"})
    assert "unavailable" in out


def test_gamma_profile_renders_regime(monkeypatch):

    rows = []
    for k in (90.0, 110.0):
        rows.append({"strike": k, "iv": 0.3, "oi": 200.0, "side": "call"})
        rows.append({"strike": k, "iv": 0.3, "oi": 50.0, "side": "put"})
    monkeypatch.setattr(T, "_options_chain_rows_lambda", lambda t: (rows, 100.0, 0.0833))
    out = T.get_gamma_profile.invoke({"ticker": "AAPL"})
    assert "gamma regime: long" in out  # call-dominated -> long (mainstream GEX)
    assert "call wall" in out and "put wall" in out
    assert "heuristic" in out


def test_opex_read_renders_window():
    # 2026-09-18 is OPEX; 2026-09-16 is in the week.
    out = T.get_opex_read.invoke({"current_date": "2026-09-16"})
    assert "next OPEX: 2026-09-18" in out
    assert "in OPEX week: True" in out
    out2 = T.get_opex_read.invoke({"current_date": "2026-09-21"})
    assert "post-OPEX unwind window: True" in out2


def test_opex_read_bad_date_degrades():
    out = T.get_opex_read.invoke({"current_date": "not-a-date"})
    assert "unavailable" in out


def test_derivatives_flow_degrades_without_chain(monkeypatch):
    monkeypatch.setattr(T, "_options_chain_rows_lambda", lambda t: None)
    out = T.get_derivatives_flow.invoke({"ticker": "AAPL", "current_date": "2026-09-04"})
    assert "gamma: n/a" in out
    assert "OPEX" in out


def test_dupont_read_renders_roe():
    out = T.get_dupont_read.invoke({
        "net_margin": 0.2, "asset_turnover": 0.9, "equity_multiplier": 2.0,
    })
    assert "dupont ROE 36.0%" in out and "margin-led" in out


def test_dupont_read_renders_leverage_led():
    out = T.get_dupont_read.invoke({
        "net_margin": 0.5, "asset_turnover": 1.0, "equity_multiplier": 4.0,
    })
    assert "leverage-led" in out and "driver equity_multiplier" in out


def test_dupont_read_none_safe():
    out = T.get_dupont_read.invoke({"net_margin": None, "asset_turnover": 0.9})
    assert "n/a" in out


def test_scenario_dcf_renders_range():
    out = T.get_scenario_dcf.invoke({
        "fcf": 100.0, "wacc": 0.09, "shares": 10.0, "cash": 50.0, "debt": 100.0,
        "g_base": 0.03,
    })
    assert "scenario dcf:" in out and "bear=120.0" in out and "bull=245.0" in out


def test_scenario_dcf_renders_band_with_market_price():
    out = T.get_scenario_dcf.invoke({
        "fcf": 100.0, "wacc": 0.09, "shares": 10.0, "cash": 50.0, "debt": 100.0,
        "g_base": 0.03, "market_price": 160.0,
    })
    assert "vs market 160.0: bear-base (discounted)" in out and "mos vs base +1.0%" in out


def test_screen_value_line_ev_ebit_artifact():
    # IREN 2026-09-10 review loop: EV/EBIT 270,761 with loss-making EBIT is
    # a near-zero-EBIT artifact - the negative multiple is the meaningful side.
    assert "ARTIFACT" in T.screen_value_line("ev_ebit", 270761.04, 270761.04)
    assert "ARTIFACT" in T.screen_value_line("earnings_yield", 0.0, 270761.04)
    assert "ARTIFACT" not in T.screen_value_line("ev_ebit", -18.29, -18.29)
    assert T.screen_value_line("ev_ebit", -18.29, -18.29) == "  EV/EBIT: -18.29"
    assert T.screen_value_line("altman_z", 1.28, None) == "  Altman Z: 1.28"


def test_surprise_basis_note_negative_actual():
    # IREN Q4 FY26: act -2.16 (GAAP) vs est -0.6058 - bases must be reconciled.
    assert "basis-unreconciled" in T.surprise_basis_note({"actual": -2.16, "estimate": -0.6058})
    assert T.surprise_basis_note({"actual": 1.11, "estimate": 0.94}) == ""
    assert T.surprise_basis_note({}) == ""


def test_earnings_quality_verdict_negative_ni_sign():
    # IREN 2026-09-10: cash conversion = OCF/NI = -2.99 with negative NI; the
    # <0.8 warning bands assume positive income, so this must NOT badge
    # "warning" - it must flag the sign-inverted read.
    out = T.get_earnings_quality_verdict.invoke({
        "net_income": -702.62e6, "ocf": 2100.0e6, "total_assets": 15.79e9,
        "fcf": -2350.52e6,
    })
    assert "negative NI - ratio sign inverted" in out
    assert "instead of the" in out


def test_earnings_quality_verdict_renders_level():
    out = T.get_earnings_quality_verdict.invoke({
        "net_income": 10.0, "ocf": 9.0, "total_assets": 100.0,
        "fcf": 4.0, "eps_growth": 0.2, "fcf_growth": -0.1,
    })
    assert "earnings quality concern: HIGH" in out and "cash_conversion=0.9" in out


def test_scenario_dcf_degrades_without_wacc():
    out = T.get_scenario_dcf.invoke({"fcf": 100.0, "wacc": 0.0})
    assert "n/a" in out


def test_option_breakeven_renders_full_read():
    # AVGO-style PMCC: breakeven + floor violation + intrinsic split + windows.
    out = T.get_option_breakeven.invoke({
        "long_strike": 300.0, "long_premium": 103.13,
        "short_strike": 390.0, "spot": 346.0, "short_ttm_days": 35.0,
        "delta": 0.8, "days_to_earnings": 6, "days_to_ex_div": 2,
    })
    assert "long breakeven = 403.13" in out
    assert "short-call floor" in out and "VIOLATES" in out
    assert "intrinsic 46.0" in out
    assert "deep-ITM" in out
    assert "30-45d" in out
    assert "earnings" in out and "assignment" in out


def test_option_breakeven_partial_renders_na():
    # Only the mandatory pair -> everything else n/a, never fabricated.
    out = T.get_option_breakeven.invoke({"long_strike": 300.0, "long_premium": 103.13})
    assert "long breakeven = 403.13" in out
    assert "short-call floor" not in out  # no short strike -> floor omitted
    assert "intrinsic" not in out


def test_options_iv_read_oi_convention_disclosed(monkeypatch):
    """SKHY 2026-09-09 review-loop: the IV-read tool reports put/call and
    must disclose the reciprocal (call/put) + the convention note so it is
    never compared to the chain's call/put as a conflicting fact."""
    # Reuse the hermetic yfinance fake from the VRP test (same shape).
    import pandas as _pd
    import yfinance as _yf

    calls = _pd.DataFrame({
        "strike": [105.0, 115.0, 125.0],
        "impliedVolatility": [0.32, 0.30, 0.28],
        "openInterest": [100.0, 50.0, 20.0],
        "bid": [1.0, 0.5, 0.2], "ask": [1.2, 0.6, 0.3], "lastPrice": [1.1, 0.55, 0.25],
    })
    puts = _pd.DataFrame({
        "strike": [95.0, 85.0, 75.0],
        "impliedVolatility": [0.34, 0.36, 0.38],
        "openInterest": [120.0, 60.0, 30.0],
        "bid": [1.0, 0.5, 0.2], "ask": [1.2, 0.6, 0.3], "lastPrice": [1.1, 0.55, 0.25],
    })

    class _FakeTk:
        options = ["260918", "260930", "261209"]
        def option_chain(self, expiry):
            return SimpleNamespace(calls=calls, puts=puts)

    n = 120
    closes = [100.0 + 0.02 * i for i in range(n)]
    monkeypatch.setattr(T, "_ohlcv", lambda ticker, days=320: {
        "dates": [f"2026-01-{i % 28 + 1:02d}" for i in range(n)],
        "closes": closes, "opens": closes,
        "highs": [c + 0.1 for c in closes], "lows": [c - 0.1 for c in closes],
        "volumes": [1_000_000.0] * n,
    })
    monkeypatch.setattr(_yf, "Ticker", lambda t: _FakeTk())
    out = T.get_options_iv_read.invoke({"ticker": "SKHY"})
    assert "put/call" in out
    assert "call/put" in out
    # put/call OI = 98,324/121,679 = 0.8081; reciprocal ~1.24 (the chain label).
    assert "0.81" in out or "1.24" in out


def test_put_call_oi_concentration_pure():
    """Pure reciprocal of the chain convention: put/call of 98,324/121,679
    = 0.808 (the chain's call/put = 1.24). The two tools are reciprocals."""
    from tradingagents.strategies.options_surface import put_call_oi_concentration
    r = put_call_oi_concentration(98_324.0, 121_679.0)
    assert r and abs(r - 0.8081) < 1e-3
    assert abs(1.0 / r - 1.2377) < 1e-3


def test_option_breakeven_never_aborts():
    # Invalid floats are schema-valid but math-None -> n/a render.
    out = T.get_option_breakeven.invoke({"long_strike": -1.0, "long_premium": -1.0})
    assert "long breakeven = n/a" in out


def test_options_iv_read_vrp_renders_pp_not_percent(monkeypatch):
    """ARM 2026-09-09 review-loop bug: volatility_risk_premium returns
    PERCENTAGE POINTS, but the render formatted it with '%' - multiplying by
    100 twice (ARM IV 67.97% - RV ~50.4% = +17.63pp showed as +1763%). The
    render must say 'pp (percentage points)', never double-percent."""
    import pandas as _pd
    import yfinance as _yf

    # Hermetic yfinance chain: spot ~ 100, ATM IV 0.32, puts slightly richer.
    calls = _pd.DataFrame({
        "strike": [105.0, 115.0, 125.0],
        "impliedVolatility": [0.32, 0.30, 0.28],
        "openInterest": [100, 50, 20],
        "bid": [1.0, 0.5, 0.2], "ask": [1.2, 0.6, 0.3], "lastPrice": [1.1, 0.55, 0.25],
    })
    puts = _pd.DataFrame({
        "strike": [95.0, 85.0, 75.0],
        "impliedVolatility": [0.34, 0.36, 0.38],
        "openInterest": [120, 60, 30],
        "bid": [1.0, 0.5, 0.2], "ask": [1.2, 0.6, 0.3], "lastPrice": [1.1, 0.55, 0.25],
    })

    class _FakeTk:
        options = ["260918", "260930", "261209"]
        def option_chain(self, expiry):
            return SimpleNamespace(calls=calls, puts=puts)

    n = 120
    closes = [100.0 + 0.02 * i for i in range(n)]  # small steady drift -> low RV
    monkeypatch.setattr(T, "_ohlcv", lambda ticker, days=320: {
        "dates": [f"2026-01-{i % 28 + 1:02d}" for i in range(n)],
        "closes": closes, "opens": closes,
        "highs": [c + 0.1 for c in closes], "lows": [c - 0.1 for c in closes],
        "volumes": [1_000_000.0] * n,
    })
    monkeypatch.setattr(_yf, "Ticker", lambda t: _FakeTk())
    out = T.get_options_iv_read.invoke({"ticker": "ARMT"})
    # NXPI 2026-09-09 review-loop: the VRP label must name the realized-vol
    # basis (20d log-close) so the reader can reconcile it against any other
    # vols the report lists — the old "ATM IV - realized vol" was ambiguous.
    assert "20d realized" in out
    assert "pp (percentage points; 20d log-close realized-vol basis)" in out
    # ATM IV 0.32, RV tiny (~0.02) -> VRP ≈ +30.0pp, nowhere near +3000.
    vrp_line = next(ln for ln in out.splitlines() if "VRP" in ln)
    val = vrp_line.split(":")[-1].strip().split("pp")[0]  # "+32.00"
    assert float(val) < 100.0


def test_cycle_tilt_renders_phase(monkeypatch):
    # FRED resolves all three signals -> mid + favored sectors.
    import tradingagents.dataflows.fred as _fred

    monkeypatch.setattr(
        _fred, "get_macro_value",
        lambda indicator, curr_date: {"pmi": 52.0, "10y_2y_spread": 0.40,
                                      "high_yield_spread": 3.5}.get(indicator),
    )
    out = T.get_cycle_tilt.invoke({"current_date": "2026-09-05"})
    assert "cycle tilt: mid" in out
    assert "Technology" in out


def test_cycle_tilt_degrades_to_na_when_no_signal(monkeypatch):
    import tradingagents.dataflows.fred as _fred

    monkeypatch.setattr(_fred, "get_macro_value", lambda indicator, curr_date: None)
    out = T.get_cycle_tilt.invoke({"current_date": "2026-09-05"})
    assert "cycle tilt: n/a" in out


def test_cycle_tilt_rade_never_aborts(monkeypatch):
    import tradingagents.dataflows.fred as _fred

    def _boom(*a, **k):
        raise RuntimeError("FRED down")
    monkeypatch.setattr(_fred, "get_macro_value", _boom)
    out = T.get_cycle_tilt.invoke({"current_date": "2026-09-05"})
    assert "cycle tilt: n/a" in out


def _sector_ohlcv(step_map):
    def _impl(t):
        step = step_map.get(t, 0.2)
        return {"closes": [100.0 + step * i for i in range(260)]}
    return _impl


def test_sector_rank_multifactor_gated_render(monkeypatch):
    # P1: with enable_sector_multifactor on, the read adds score/accel lines.
    from tradingagents.dataflows.config import reset_config, set_config

    set_config({"enable_sector_multifactor": True})
    try:
        steps = {"XLK": 0.8, "XLF": 0.4, "SPY": 0.15}
        monkeypatch.setattr(T, "_ohlcv", _sector_ohlcv(steps))
        monkeypatch.setattr(T, "_benchmark_closes", lambda: [100.0 + 0.15 * i for i in range(260)])
        with mock.patch(
            "tradingagents.dataflows.yfinance_sector.fetch_sector",
            return_value="Technology",
        ):
            out = T.get_sector_rank.invoke({"ticker": "AAPL"})
        assert "mf XLK score=" in out
        assert "accel=" in out
    finally:
        reset_config()


def test_sector_rank_pipeline_gated_render(monkeypatch):
    # P2 + P3: industry layer + constituent breadth/leadership on for the
    # parent sector (XLK -> SOXX family).
    from tradingagents.dataflows.config import reset_config, set_config

    set_config({
        "enable_sector_multifactor": True,
        "enable_sector_industry": True,
        "enable_sector_breadth": True,
    })
    try:
        steps = {
            "XLK": 0.4, "XLF": 0.2, "SPY": 0.15,
            "SOXX": 0.9, "IGV": 0.5, "HACK": 0.3, "SMH": 0.2, "CLOU": 0.1,
            # SOXX constituents all above their MAs -> breadth 100%
            "NVDA": 0.6, "AMD": 0.6, "AVGO": 0.6, "MU": 0.6, "TSM": 0.6,
            "AMAT": 0.6, "LRCX": 0.6, "KLAC": 0.6, "MRVL": 0.6, "QCOM": 0.6,
        }
        monkeypatch.setattr(T, "_ohlcv", _sector_ohlcv(steps))
        monkeypatch.setattr(T, "_benchmark_closes", lambda: [100.0 + 0.15 * i for i in range(260)])
        with mock.patch(
            "tradingagents.dataflows.yfinance_sector.fetch_sector",
            return_value="Technology",
        ):
            out = T.get_sector_rank.invoke({"ticker": "AAPL"})
        assert "industry XLK: top=SOXX" in out
        assert "breadth SOXX:" in out
        assert "leadership SOXX:" in out
    finally:
        reset_config()


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
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda ticker, date, **kw: _eq_canonical())
    out = T.get_earnings_quality.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "earnings quality AAPL" in out
    assert "consensus_concern: HIGH" in out  # cc 0.45 warning + accrual 0.055 elevated
    assert "accrual=0.055" in out  # (100 - 45) / 1000
    assert "trap_risk=" in out


def test_earnings_quality_high_accruals_flagged(monkeypatch):
    from tradingagents.dataflows import statement_parsing as sp

    def fake_fetch(ticker, date):
        fin = _eq_canonical()
        fin["net_income"] = 200e6  # accrual = 155e6 / 1e9 = 0.155 (concerning)
        return fin

    monkeypatch.setattr(sp, "fetch_ticker", fake_fetch)
    monkeypatch.setattr(sp, "screen_ticker", lambda ticker, fin: {})
    out = T.get_earnings_quality.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "0.155" in out
    assert "concerning" in out
    assert "consensus_concern: HIGH" in out


def test_earnings_quality_capex_negative_fcf_red_flag(monkeypatch):
    """capex derives FCF = OCF - |capex|; negative FCF + positive NI = red flag
    (also verifies the sign-robustness: a negative GAAP-signed capex gives the
    same FCF as the positive magnitude)."""
    from tradingagents.dataflows import statement_parsing as sp

    def fake_fetch(ticker, date):
        fin = _eq_canonical()
        fin["operating_cashflow"] = 20e6
        fin["capex"] = 30e6  # FCF = 20 - 30 = -10e6
        return fin

    monkeypatch.setattr(sp, "fetch_ticker", fake_fetch)
    monkeypatch.setattr(sp, "screen_ticker", lambda ticker, fin: {})
    out = T.get_earnings_quality.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "negative FCF with positive NI" in out

    # GAAP-outflow sign: capex = -30e6 must give the SAME -10e6 FCF.
    def fake_fetch_neg(ticker, date):
        fin = _eq_canonical()
        fin["operating_cashflow"] = 20e6
        fin["capex"] = -30e6
        return fin

    monkeypatch.setattr(sp, "fetch_ticker", fake_fetch_neg)
    out = T.get_earnings_quality.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "negative FCF with positive NI" in out


def test_earnings_quality_no_data_degrades(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda ticker, date, **kw: {})
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
    assert "stop=" in out and "avg_entry(" in out
    assert "size-weighted" in out  # avg_entry is weighted by the tranche weights, not a simple mean
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
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d, **kw: {"market_cap": 1e11})
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
    # The raw fcf/market_cap carry NO "$" prefix and say "raw vendor units" -
    # a KRW reporter (SKHY 2026-09-09) must not be relabeled as USD.
    assert "$" not in out.split("fcf yield")[1]
    assert "raw vendor units" in out


def test_fcf_yield_missing_data_degrades(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d, **kw: {})
    monkeypatch.setattr(V, "route_to_vendor", lambda *a, **k: "NO_DATA_AVAILABLE")
    out = V.get_fcf_yield.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "unavailable" in out.lower()


def _qf_markdown(fcfs_b):
    """Quarterly-shaped moomoo cashflow markdown, newest period first."""
    labels = ["Q3 2026", "Q2 2026", "Q1 2026", "Q4 2025", "Q3 2025"]
    parts = ["## Cash Flow (quarterly)"]
    for lab, f in zip(labels[: len(fcfs_b)], fcfs_b, strict=False):
        parts += [
            f"### {lab}  (FY 2026, currency: USD)",
            "| Item | Value | YoY | QoQ |",
            "| --- | --- | --- | --- |",
            f"| Free Cash Flow | {f}B | -- | -- |",
            "",
        ]
    return "\n".join(parts)


def test_fcf_yield_uses_trailing_ttm_not_annual(monkeypatch):
    """The value floor must anchor on the trailing-12M FCF (sum of the newest
    4 quarters), not the latest ANNUAL fiscal-year FCF: an annual FYxx is
    silently stale when the capex/OCF is swinging (AMZN FY2025 +$7.7B vs TTM
    -$2.5B case). Quarter sum = -18.171+0.332+0.43+14.937 = -2.472B."""
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: {"market_cap": 2721e9},
    )
    monthly = lambda *a, **k: _qf_markdown([-18.171, 0.332, 0.43, 14.937])  # noqa: E731
    monkeypatch.setattr(V, "route_to_vendor", monthly)
    out = V.get_fcf_yield.invoke({"ticker": "AMZN", "current_date": "2026-09-09"})
    assert "fcf yield AMZN" in out
    assert "basis=ttm" in out
    assert "-0.09%" in out  # -2.472B / 2.721T
    # The stale annual anchor (+7.695B / 2.721T = +0.28%) must NOT appear.
    assert "+0.28%" not in out


def test_fcf_yield_positive_ttm_still_renders(monkeypatch):
    """A positive trailing-12M FCF is used as-is; positive TTM => floor check."""
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: {"market_cap": 100e9},
    )
    monkeypatch.setattr(V, "route_to_vendor", lambda *a, **k: _qf_markdown([10, 8, 9, 7]))
    out = V.get_fcf_yield.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "basis=ttm" in out
    assert "34.00%" in out  # (10+8+9+7)B / 100B


def test_fcf_yield_falls_back_to_annual_basis(monkeypatch):
    """When the quarterly payload is absent/not quarterly-shaped, the value
    floor falls back to the latest annual FCF and says so."""
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: {"market_cap": 100e9},
    )
    monkeypatch.setattr(V, "route_to_vendor", lambda *a, **k: _vdip_fundamentals_markdown())
    out = V.get_fcf_yield.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "basis=annual" in out
    assert "10.00%" in out


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
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d, **kw: {"market_cap": 1e11})
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
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d, **kw: {})
    out = V.get_value_dip_setup.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "unavailable" in out.lower()


# --------------------------------------------------------------------------
# Value Dip gap tools: balance sheet, MACD divergence, VDU ladder, support,
# decline driver
# --------------------------------------------------------------------------


def test_balance_sheet_health_computes(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: {
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


def test_balance_sheet_health_names_the_rows_it_divided(monkeypatch):
    """D2 (NVDA 2026-09-12): the report showed `current ratio 4.6808` beside a
    $197.41B/$43.02B pair it never used, and nothing could reconcile the two
    because the tool did not print its own inputs. The basis line now names
    all four canonical rows, so the tool's number is self-consistent."""
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: {
            "total_debt": 11_040_000_000,
            "total_equity": 157_290_000_000,
            "current_assets": 234_000_000_000,
            "current_liabilities": 50_000_000_000,
        },
    )
    out = V.get_balance_sheet_health.invoke({"ticker": "NVDA", "current_date": "2026-09-12"})
    assert "current_ratio=4.68" in out
    assert "current_assets=234,000,000,000" in out
    assert "current_liabilities=50,000,000,000" in out
    assert "total_debt=11,040,000,000" in out and "total_equity=157,290,000,000" in out
    assert "basis: canonical merged rows" in out


def test_balance_sheet_health_degrades(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d, **kw: {})
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


def test_support_structure_renders_sma200_basis(monkeypatch):
    """Regression (QCOM 2026-09-07): the tool printed distance_to_sma200
    (0.2%) without its sma200 basis, so the analyst spliced a foreign
    200-day average onto it. The rendered line must carry both."""
    closes, highs, lows, vols = _vdip_dip_trigger()
    closes = closes + [x + 5 for x in range(60)]  # ≥ 205 bars
    lows2 = lows + lows[:60]
    highs2 = highs + highs[:60]
    monkeypatch.setattr(
        V,
        "_ohlcv",
        lambda ticker: {
            "closes": closes,
            "lows": lows2,
            "highs": highs2,
            "volumes": vols + [1e6] * 60,
            "opens": closes,
        },
    )
    out = V.get_support_structure.invoke({"ticker": "AAPL"})
    assert "sma200=" in out
    assert "distance_to_sma200=" in out
    assert out.split("sma200=")[1].split(" ")[0] not in ("", "n/a")


def test_decline_driver_suppresses_degenerate_eps_yoy(monkeypatch):
    """Regression (QCOM 2026-09-07): EPS YoY -2280% is a denominator
    artifact (prior-year EPS base near $0), not a real 'severe earnings
    decline'. The tool must not emit it as a flag."""
    fin = {
        "market_cap": 1e11,
        "total_equity": 1e9,
        "net_income": 150e6,
        "total_debt": 300e6,
        "current_assets": 800e6,
        "current_liabilities": 300e6,
        "eps": {"current": 0.75, "prior": 0.0},
        "eps_yoy": -22.8,  # vendor artifact: -2280%
    }
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d, **kw: fin)
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
    assert "severe earnings decline" not in out
    assert "verdict=" in out


def test_decline_driver_reports_verdict(monkeypatch):
    fin = {
        "market_cap": 1e11,
        "total_equity": 1e9,
        "net_income": 150e6,
        "total_debt": 300e6,
        "current_assets": 800e6,
        "current_liabilities": 300e6,
    }
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d, **kw: fin)
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
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: (fin, {}) if kw.get("with_provenance") else fin,
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.trailing_twelve_months",
        lambda t, d, periods=4: {"periods": [], "source": None, "complete": False},
    )
    out = T.get_ratios.invoke({"ticker": "AAPL", "current_date": "2026-08-24"})
    assert "Ratios (computed)" in out
    assert "EV/EBITDA: 7.67" in out
    assert "ROE: 16.00%" in out
    assert "P/E: 12.50" in out
    assert "Quick: 1.60" in out


def test_get_ratios_degrades_when_no_data(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: ({}, {}) if kw.get("with_provenance") else {},
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.trailing_twelve_months",
        lambda t, d, periods=4: {"periods": [], "source": None, "complete": False},
    )
    out = T.get_ratios.invoke({"ticker": "AAPL", "current_date": "2026-08-24"})
    assert "unavailable" in out.lower()
    assert "fabricate" in out.lower()


def test_get_ratios_uses_the_ttm_basis_and_names_it(monkeypatch):
    """D1 (NVDA 2026-09-12): the block divided a current market cap by the
    FY-ANNUAL net income and printed `P/E 43.90` with no period, while the TTM
    basis was 27.63. The TTM flow now wins and the basis leads the block."""
    annual = {
        "market_cap": 1000e6, "total_assets": 800e6, "total_equity": 500e6,
        "net_income": 80e6, "revenue": 900e6,
    }
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: (
            (annual, {"total_assets": {"period": "2026-07-31", "basis": "annual"}})
            if kw.get("with_provenance") else annual
        ),
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.trailing_twelve_months",
        lambda t, d, periods=4: {
            "periods": ["2026-07-31", "2026-04-30", "2026-01-31", "2025-10-31"],
            "source": "get_income_statement (quarterly)", "complete": True,
            "net_income_ttm": 40e6, "revenue_ttm": 1000e6,
        },
    )
    out = T.get_ratios.invoke({"ticker": "AAPL", "current_date": "2026-08-24"})
    assert "- basis: flows TTM (4 quarters ending 2026-07-31); balance sheet 2026-07-31" in out
    assert "P/E: 25.00" in out      # 1000 / 40 TTM, not 1000 / 80 annual
    assert "P/S: 1.00" in out


def test_dupont_read_derives_one_payload_and_labels_its_basis(monkeypatch):
    """D4 (NVDA 2026-09-12): the tool took three bare floats and emitted no
    period, so `DuPont on the latest quarter` labelled a TTM margin. Passing a
    ticker derives all three legs from ONE payload, period-consistent."""
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: (
            ({"total_assets": 800e6, "total_equity": 500e6},
             {"total_assets": {"period": "2026-07-31", "basis": "annual"}})
            if kw.get("with_provenance") else {"total_assets": 800e6, "total_equity": 500e6}
        ),
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.trailing_twelve_months",
        lambda t, d, periods=4: {
            "periods": ["2026-07-31"], "complete": True,
            "net_income_ttm": 80e6, "revenue_ttm": 900e6,
        },
    )
    out = T.get_dupont_read.invoke({"ticker": "AAPL", "curr_date": "2026-08-24"})
    assert "16.0%" in out                      # 8.89% margin x 1.125 x 1.6
    assert "derived from one payload" in out and "2026-07-31" in out


def test_dupont_read_labels_caller_supplied_legs_as_unverified():
    out = T.get_dupont_read.invoke(
        {"net_margin": 0.637, "asset_turnover": 0.946, "equity_multiplier": 1.399}
    )
    assert "84.3%" in out
    assert "caller-supplied legs" in out and "period unstated" in out


# --------------------------------------------------------------------------
# Liquidity / ownership tools (Strategies/risk2.md) - hermetic
# --------------------------------------------------------------------------


def test_get_liquidity_risk_computes(monkeypatch):
    from tradingagents.agents.utils import market_position_tools as MPT

    closes = [100.0 + i for i in range(40)]
    vols = [1_000_000] * 40
    fake = {"closes": closes, "opens": closes, "highs": [c + 1 for c in closes],
            "lows": [c - 1 for c in closes], "volumes": vols}
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: fake)
    monkeypatch.setattr(
        "tradingagents.dataflows.float_shares.fetch_float_shares", lambda t: 30e6
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: {"shares": {"current": 100e6, "prior": 100e6}},
    )
    out = MPT.get_liquidity_risk.invoke({"ticker": "AAPL", "current_date": "2026-08-24"})
    assert "liquidity risk AAPL" in out
    assert "verdict=" in out
    assert "illiq=" in out and "float_turnover=" in out and "iwf=" in out


def test_get_liquidity_risk_missing_data_degrades(monkeypatch):
    from tradingagents.agents.utils import market_position_tools as MPT

    monkeypatch.setattr(T, "_ohlcv", lambda ticker: {"closes": [], "volumes": []})
    monkeypatch.setattr(
        "tradingagents.dataflows.float_shares.fetch_float_shares", lambda t: None
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d, **kw: {}
    )
    out = MPT.get_liquidity_risk.invoke({"ticker": "AAPL", "current_date": "2026-08-24"})
    assert "liquidity risk AAPL" in out
    assert "n/a" in out  # honest degrade, never fabricated


def test_get_ownership_concentration_computes(monkeypatch):
    from tradingagents.agents.utils import analysis_tools as AT

    monkeypatch.setattr(
        "tradingagents.dataflows.float_shares.fetch_float_shares", lambda t: 30e6
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: {"shares": {"current": 100e6, "prior": 100e6}},
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.interface.route_to_vendor",
        lambda *a, **k: "| 2025-Q4 | 5123 | 8.42B | 71.2% | +0.8pp |",
    )
    out = AT.get_ownership_concentration.invoke({"ticker": "AAPL", "current_date": "2026-08-24"})
    assert "ownership concentration AAPL" in out
    assert "iwf=30.00%" in out  # 30M / 100M
    assert "hhi=" in out


def test_get_ownership_concentration_no_holder_data(monkeypatch):
    from tradingagents.agents.utils import analysis_tools as AT

    monkeypatch.setattr(
        "tradingagents.dataflows.float_shares.fetch_float_shares", lambda t: 30e6
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d, **kw: {"shares": {"current": 100e6, "prior": 100e6}},
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.interface.route_to_vendor", lambda *a, **k: "NO_DATA_AVAILABLE"
    )
    out = AT.get_ownership_concentration.invoke({"ticker": "AAPL", "current_date": "2026-08-24"})
    assert "ownership concentration AAPL" in out
    assert "iwf=30.00%" in out
    assert "hhi=n/a" in out  # best-effort: no per-holder breakdown


# --------------------------------------------------------------------------
# Swing exits + dip technical tools (Phases 3) - hermetic
# --------------------------------------------------------------------------


def _uptrend_ohlcv(n=260):
    closes = [100.0 + 0.5 * i + 8.0 * math.sin(i / 6) for i in range(n)]
    return {
        "closes": closes,
        "highs": [c + 1 for c in closes],
        "lows": [c - 1 for c in closes],
        "volumes": [1_000_000] * n,
        "opens": closes,
    }


def test_get_swing_exits_computes(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: _uptrend_ohlcv())
    out = T.get_swing_exits.invoke({"ticker": "AAPL"})
    assert "swing exits AAPL" in out
    assert "chandelier stop=" in out
    assert "ema20=" in out


def test_get_swing_exits_insufficient_history(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: {"closes": [100.0] * 50,
        "highs": [101.0] * 50, "lows": [99.0] * 50, "volumes": [1e6] * 50})
    out = T.get_swing_exits.invoke({"ticker": "AAPL"})
    assert "fewer than 200" in out


def test_get_dip_technical_computes(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: _uptrend_ohlcv())
    out = T.get_dip_technical.invoke({"ticker": "AAPL"})
    assert "dip technical AAPL" in out
    assert "rsi=" in out and "stochK=" in out and "mfi=" in out and "kst=" in out


def test_get_dip_technical_insufficient(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: {"closes": [100.0] * 10,
        "highs": [101.0] * 10, "lows": [99.0] * 10, "volumes": [1e6] * 10})
    out = T.get_dip_technical.invoke({"ticker": "AAPL"})
    assert "fewer than 30" in out


def test_get_mean_reversion_tech_computes(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: _uptrend_ohlcv())
    out = T.get_mean_reversion_tech.invoke({"ticker": "AAPL"})
    assert "mean reversion tech AAPL" in out
    assert "stochrsi=" in out and "keltner" in out and "obv_up=" in out


def test_get_mean_reversion_tech_insufficient(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [100.0] * 10,
        "highs": [101.0] * 10, "lows": [99.0] * 10, "volumes": [1e6] * 10})
    out = T.get_mean_reversion_tech.invoke({"ticker": "AAPL"})
    assert "fewer than 30" in out


def test_get_value_floors_computes(monkeypatch):
    from tradingagents.agents.utils import value_dip_tools as VDT

    fin = {
        "eps": {"current": 4.0, "prior": 3.5},
        "total_equity": {"current": 3e9, "prior": 2.8e9},
        "shares": {"current": 1e8, "prior": 1e8},
        "current_assets": {"current": 1e9, "prior": 9e8},
        "total_liabilities": {"current": 4e8, "prior": 3.5e8},
        "operating_income": {"current": 2e8, "prior": 1.8e8},
        "tax_expense": {"current": 4e7, "prior": 3.6e7},
        "total_assets": {"current": 5e9, "prior": 4.5e9},
        "beta": {"current": 1.1, "prior": 1.0},
    }
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d, **kw: fin)
    monkeypatch.setattr(T, "_ohlcv", lambda t: _uptrend_ohlcv())
    out = VDT.get_value_floors.invoke({"ticker": "AAPL", "current_date": "2026-08-19"})
    assert "value floors AAPL" in out
    assert "graham_number=" in out
    assert "ncav_per_share=" in out
    assert "epv=" in out


# ---------------------------------------------------------------------------
# New Phase-1 tools: technical factors / book tail / liquidation / premarket
# ---------------------------------------------------------------------------


def test_technical_factors_computes_all_reads():
    """get_technical_factors wraps ADX/pivots/Aroon/Fisher/Chaikin/Elder-Ray/
    Supertrend/volume-profile in one call (shares the run-level OHLCV cache)."""
    closes = _uptrend(260)
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": closes}),
    ):
        out = T.get_technical_factors.invoke({"ticker": "AAPL"})
    assert "technical factors AAPL" in out
    assert "adx=" in out and "pivots:" in out and "aroon:" in out
    assert "fisher=" in out and "chaikin=" in out and "elder_ray:" in out
    assert "supertrend:" in out and "volume_profile:" in out


def test_technical_factors_insufficient_history():
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": [100.0] * 20}),
    ):
        out = T.get_technical_factors.invoke({"ticker": "AAPL"})
    assert "fewer than 30 bars" in out


def test_book_tail_risk_computes(monkeypatch):
    """get_book_tail_risk wraps portfolio CVaR + correlated stress + drawdown,
    and says which book the mix came from (the configured basket, not the
    analyzed name - NVDA 2026-09-12 reported 20.21% as the book)."""
    closes = _uptrend(260)
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: {"closes": closes})
    out = T.get_book_tail_risk.invoke({"ticker": "AAPL"})
    assert "book tail risk AAPL" in out
    assert "portfolio_cvar=" in out and "correlated_stress_-10pct=" in out
    assert "mix=configured basket (8/8 names)" in out
    assert "drawdown(realized book)=" in out and "source=" in out
    assert "drawdown_gate=" in out


def test_book_tail_risk_no_series(monkeypatch):
    """No series anywhere -> unavailable, never an invented number."""
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: {"closes": []})
    with mock.patch(
        "tradingagents.dataflows.config.get_config",
        lambda: {"risk_basket_tickers": ["AAA", "BBB"], "risk_basket_weights": {}},
    ):
        out = T.get_book_tail_risk.invoke({"ticker": "ZZZZ"})
    assert "unavailable" in out.lower()


def test_liquidation_days_computes(monkeypatch):
    """get_liquidation_days wraps days_to_absorb with float + ADV."""
    closes = _uptrend(260)
    monkeypatch.setattr(
        "tradingagents.dataflows.float_shares.fetch_float_shares", lambda t: 1e8
    )
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": closes}),
    ):
        out = T.get_liquidation_days.invoke({"ticker": "AAPL"})
    assert "liquidation days AAPL" in out
    assert "days to absorb" in out
    # NXPI 2026-09-09 review loop: the output must disclose the 15%
    # participation figure separately from the ADV — the old label printed
    # the ADV (3,765,685/day) as if it were the 15% participation, making
    # 445.6 days look internally inconsistent. New format names both.
    import re as _re

    assert "15% of ADV" in out
    m = _re.search(r"\(\d[\d,]*/day \(15% of ADV \d[\d,]*/day\)\)", out)
    assert m is not None, out


def test_liquidation_days_missing_adv():
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": [100.0] * 5}),
    ):
        out = T.get_liquidation_days.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower()


def test_premarket_review_confirm_when_no_deltas():
    """No quote -> CONFIRM (never fabricate a REVISE/REJECT)."""
    closes = _uptrend(260)
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": closes}),
    ):
        out = T.get_premarket_review.invoke({"ticker": "AAPL"})
    assert "premarket review AAPL" in out
    assert "verdict=" in out


def test_premarket_review_rejects_through_stop():
    """Open beyond the prior stop (long: open < stop) -> REJECT (gap risk
    realized). Requires entry_price to infer the long/short direction."""
    closes = _uptrend(260)
    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df",
        side_effect=_ohlcv_df({"AAPL": closes}),
    ):
        out = T.get_premarket_review.invoke(
            {
                "ticker": "AAPL",
                "prior_close": 100.0,
                "open_price": 80.0,
                "prior_stop": 90.0,
                "entry_price": 105.0,
            }
        )
    assert "REJECT" in out


def test_ohlcv_cache_serves_one_fetch_per_ticker():
    """The run-level OHLCV cache must serve ONE vendor fetch per (ticker, days)
    so multiple tools sharing the series never re-fetch (no duplicate data)."""
    T._clear_ohlcv_cache()
    calls = []

    def load(ticker):
        calls.append(ticker)
        return _ohlcv_df({}) and None if False else _load_ohlcv_df_for([100.0 + i for i in range(60)])

    def _load_ohlcv_df_for(closes):
        csv = _ohlcv_csv(closes, [5_000_000] * 60)
        import io
        return pd.read_csv(io.StringIO(csv))

    with mock.patch("tradingagents.agents.utils.analysis_tools._load_ohlcv_df", side_effect=load):
        T._ohlcv("AAPL")
        T._ohlcv("AAPL")
        T._ohlcv("AAPL", days=60)
    assert calls.count("AAPL") == 2  # 320-day (default) + 60-day (different keys), not 3
    T._clear_ohlcv_cache()


def test_get_value_floors_no_tax_does_not_crash(monkeypatch):
    """Regression: get_value_floors must not crash when ebit is present but
    tax_expense is missing (None) - tax None -> tax_rate None, epv/roic degrade
    to None instead of a NoneType / float TypeError."""
    from tradingagents.agents.utils import value_dip_tools as VDT

    fin = {
        "eps": {"current": 4.0, "prior": 3.5},
        "total_equity": {"current": 3e9, "prior": 2.8e9},
        "shares": {"current": 1e8, "prior": 1e8},
        "current_assets": {"current": 1e9, "prior": 9e8},
        "total_liabilities": {"current": 4e8, "prior": 3.5e8},
        "operating_income": {"current": 2e8, "prior": 1.8e8},
        # tax_expense intentionally absent (None)
        "total_assets": {"current": 5e9, "prior": 4.5e9},
        "beta": {"current": 1.1, "prior": 1.0},
    }
    monkeypatch.setattr("tradingagents.dataflows.statement_parsing.fetch_ticker", lambda t, d, **kw: fin)
    monkeypatch.setattr(T, "_ohlcv", lambda t: _uptrend_ohlcv())
    out = VDT.get_value_floors.invoke({"ticker": "X", "current_date": "2026-08-19"})
    assert "value floors X" in out  # no crash


# ---------------------------------------------------------------------------
# get_extended_indicators / get_candlestick_patterns (Phase 1 indicator gap)
# ---------------------------------------------------------------------------


def test_extended_indicators_computes_all_reads(monkeypatch):
    """The extended group wraps Ichimoku/CCI/ROC/momentum/TRIX/Force/A-D/VPT/
    CMF/anchored VWAP + golden cross in one call (shares the OHLCV cache)."""
    closes = _uptrend(260)
    fake = {
        "closes": closes,
        "opens": [c - 1 for c in closes],
        "highs": [c + 3 for c in closes],
        "lows": [c - 3 for c in closes],
        "volumes": [5_000_000.0] * 260,
    }
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: fake)
    out = T.get_extended_indicators.invoke({"ticker": "AAPL"})
    assert "extended indicators AAPL" in out
    for token in ("ichimoku:", "cci=", "roc=", "trix=", "force_index=",
                  "accumulation_distribution=", "vpt=", "cmf=",
                  "anchored_vwap=", "golden/death cross"):
        assert token in out


def test_extended_indicators_insufficient_history(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [100.0] * 20,
        "highs": [101.0] * 20, "lows": [99.0] * 20, "volumes": [1e6] * 20})
    out = T.get_extended_indicators.invoke({"ticker": "AAPL"})
    assert "fewer than 60" in out


def test_extended_indicators_no_ohlcv_degrades(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [], "highs": [],
        "lows": [], "volumes": []})
    out = T.get_extended_indicators.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower() or "fewer than 60" in out


def test_candlestick_patterns_computes(monkeypatch):
    closes = _uptrend(60)
    fake = {
        "closes": closes,
        "opens": [c - 0.5 for c in closes],
        "highs": [c + 1 for c in closes],
        "lows": [c - 1 for c in closes],
        "volumes": [5_000_000.0] * 60,
    }
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: fake)
    out = T.get_candlestick_patterns.invoke({"ticker": "AAPL"})
    assert "candlestick patterns AAPL" in out
    assert "detected:" in out


def test_candlestick_patterns_no_ohlcv_degrades(monkeypatch):
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [], "opens": [],
        "highs": [], "lows": [], "volumes": []})
    out = T.get_candlestick_patterns.invoke({"ticker": "AAPL"})
    assert "unavailable" in out.lower()


def test_indicator_tools_bound_to_market_analyst():
    """Both new tools must be importable via agent_utils and present in the
    market analyst's bound toolset (wiring Phase 3)."""
    from tradingagents.agents.toolsets import market_tools
    from tradingagents.agents.utils.agent_utils import (
        get_candlestick_patterns as gcp,
        get_extended_indicators as gei,
    )
    assert callable(getattr(gei, "invoke", None))
    assert callable(getattr(gcp, "invoke", None))

    # The analyst binds market_tools() and the graph builds its ToolNode from
    # the same function, so presence here is the observable binding contract.
    bound = {getattr(t, "name", None) for t in market_tools()}
    assert {"get_extended_indicators", "get_candlestick_patterns"} <= bound


def test_signal_quality_computes_metrics():
    """New agent tool: rank IC / ICIR / long-short precision / CPCV paths."""
    sig = list(range(60))
    fwd = [i * 0.001 for i in range(60)]
    out = T.get_signal_quality.invoke({"signal": sig, "forward_returns": fwd})
    assert "rank_ic: 1.0000" in out
    assert "long_short_precision" in out
    assert "CPCV train/test paths" in out
    # short input degrades cleanly
    assert "n/a" in T.get_signal_quality.invoke(
        {"signal": [0.1, 0.2], "forward_returns": [0.0, 0.0]}
    )


def test_bsm_option_quote_renders_model_quote():
    """New agent tool: BSM spot-surface price + greeks."""
    out = T.get_bsm_option_quote.invoke(
        {"spot": 100.0, "strike": 105.0, "t_years": 0.5, "vol": 0.3,
         "option_type": "call", "r": 0.04, "q": 0.02}
    )
    assert "BSM option quote" in out
    assert "price: 6.7120" in out and "charm: -0.1416" in out
    assert "advisory - not a market price" in out
    assert "unavailable" in T.get_bsm_option_quote.invoke(
        {"spot": -1.0, "strike": 105.0, "t_years": 0.5, "vol": 0.3}
    )


def test_constituent_cap_weights_exact_ceiling():
    """New agent tool: exact-ceiling cap + degenerate-flag note."""
    w = [0.060, 0.050, 0.040, 0.030] + [0.02] * 7 + [0.01] * 68
    out = T.get_constituent_cap_weights.invoke({"weights": w})
    assert "ceiling 3.5% exact" in out
    assert "3.5000%" in out
    assert "2.1098%" in out  # sub-cap names absorbed the excess
    # all-violator book flags the degenerate fallback
    out2 = T.get_constituent_cap_weights.invoke(
        {"weights": [0.06, 0.04, 0.02]}
    )
    assert "ceiling not enforceable" in out2


# --------------------------------------------------------------------------
# Price-scale / staleness advisory (INTU 2026-09-08 stale-close contamination)
# --------------------------------------------------------------------------


def test_scale_note_warns_on_stale_close(monkeypatch):
    """An OHLCV tool whose latest close differs from the verified close must
    append a PRICE-SCALE WARNING so actionable levels are not trusted."""
    from tradingagents.agents.utils.price_consistency import set_verified_close

    set_verified_close("INTU", 314.12)
    note = T._scale_note("INTU", [410.0, 332.70])  # stale 9/4 close
    assert "PRICE-SCALE WARNING" in note
    assert "UNRELIABLE" in note
    set_verified_close("INTU", None)  # keep no cache for other tests
    from tradingagents.agents.utils.price_consistency import clear_verified_close_cache

    clear_verified_close_cache()


def test_scale_note_empty_when_agreeing(monkeypatch):
    from tradingagents.agents.utils.price_consistency import (
        clear_verified_close_cache,
        set_verified_close,
    )

    set_verified_close("INTU", 314.12)
    assert T._scale_note("INTU", [300.0, 314.12]) == ""
    clear_verified_close_cache()


def test_sentiment_lead_lag_strongest_corr_spans_both_metrics(monkeypatch):
    """Regression (INTU 2026-09-08): the tool reported 'strongest |corr| 0.206'
    while a pearson -0.278 existed at another lag (|0.278| > 0.206) because
    only spearman was scanned. The strongest-|corr| must span both metrics and
    report lag + metric."""
    import tradingagents.strategies.sentiment_research as sr_mod

    rows = [
        {"lag_days": -6, "pearson_corr": 0.10, "pearson_pval": 0.3,
         "spearman_corr": 0.20, "spearman_pval": 0.3, "sample_size": 50},
        {"lag_days": 6, "pearson_corr": -0.278, "pearson_pval": 0.001,
         "spearman_corr": 0.206, "spearman_pval": 0.02, "sample_size": 50},
    ]
    monkeypatch.setattr(sr_mod, "sentiment_lead_lag", lambda *a, **k: rows)
    monkeypatch.setattr(
        "tradingagents.dataflows.eodhd._sentiment_points_eodhd",
        lambda *a, **k: [{"date": "2026-09-01", "score": 0.5}] * 40,
    )
    monkeypatch.setattr(
        T, "_ohlcv",
        lambda *a, **k: {"closes": [100.0] * 40, "dates": ["2026-09-01"] * 40,
                          "highs": [], "lows": [], "volumes": [], "opens": []},
    )
    out = T.get_sentiment_lead_lag.invoke({"ticker": "TST"})
    # Strongest is the pearson 0.278 at lag +6, not the spearman 0.206.
    assert "strongest |corr|: 0.278" in out
    assert "pearson" in out and "lag +6" in out


def test_composite_rank_lists_ranked_peers(monkeypatch):
    """Regression (INTU 2026-09-08): the report listed 10 company peers while
    the composite said 'vs 4 peers'. The tool must surface WHICH tickers it
    actually ranked so the sample is auditable."""
    import tradingagents.strategies.factors as factors_mod

    def fake_composite(factors, weights=None):
        out = {}
        for i, t in enumerate(sorted(factors)):
            out[t] = 1.0 - i * 0.1
        return out

    monkeypatch.setattr(factors_mod, "composite_score", fake_composite)
    monkeypatch.setattr(factors_mod, "momentum", lambda closes: 0.1)
    monkeypatch.setattr(factors_mod, "high_distance", lambda closes: 0.05)
    monkeypatch.setattr(
        T, "_ohlcv",
        lambda t, days=320: {"closes": [100.0] * 64, "highs": [], "lows": []},
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.finnhub.get_company_peers_finnhub",
        lambda t: ["PLTR", "CRM", "APP", "ADBE", "CDNS", "SNPS", "DDOG", "MSTR", "ADSK", "ROP"],
    )
    out = T.get_composite_rank.invoke({"ticker": "INTU"})
    assert "peers_ranked:" in out
    assert "INTU" not in out.split("peers_ranked:")[1].split(",")[0]  # ticker excluded
    assert "PLTR" in out or "CRM" in out


def test_drawdown_measures_labeled_distinct():
    """Regression (INTU 2026-09-08): three unlabeled 'drawdown' numbers
    (regime 52w, book realized, strategy backtest) could be conflated. Each
    tool's output must carry a distinct label."""
    from pathlib import Path

    from tradingagents.agents.utils import analysis_tools as _T
    src = Path(_T.__file__).read_text(encoding='utf-8')
    assert "52w_distance(drawdown vs 52-wk high)" in src
    assert "drawdown(realized book)=" in src
    assert "max_dd(backtest)" in src


def test_credit_default_prob_decimal_conversion(monkeypatch):
    """Regression (INTU 2026-09-08): hazard_from_spread expects a DECIMAL
    spread but the tool passed the percentage (2.68 -> hazard 4.467, PD 98.9%
    instead of ~4.4%). The tool must convert % -> decimal before computing."""
    import tradingagents.strategies.credit_spread as cs

    res = {"level": "moderate", "scale": 0.85, "reasons": ["hy_oas=2.68% (low)"]}
    monkeypatch.setattr(cs, "credit_stress_level", lambda *a, **k: res)
    monkeypatch.setattr("tradingagents.agents.utils.analysis_tools._fred_latest_pct", lambda payload: 2.68)

    out = T.get_credit_spread_read.invoke({"current_date": "2026-09-08"})
    # Correct: 2.68% / (1-0.40) = 4.47% hazard; PD ~ 1-e^-0.0447 ~ 4.4%.
    assert "implied 1y default prob (HY, RR=0.40): 4.4%" in out
    assert "hazard 0.045" in out
    # The broken 98.9% is gone.
    assert "98.9%" not in out


def test_dcf_sanity_gate_unit_mix_ratio():
    # TSM 2026-09-10: vendor DCF fair_value 2933.52 vs price 429.55 is 6.8x -
    # a unit-mixed/share-basis-inconsistent output. The gate must fire at
    # >5x and stay off for a sane ~1.2x ratio (regression from the TSM
    # fundamentals review loop).
    res_price, price = 2933.52, 429.55
    assert res_price / price > 5.0
    assert res_price / price == pytest.approx(6.83, abs=0.01)
    sane = 520.0 / 429.55
    assert not (sane > 5.0)


def test_tail_risk_var_is_rendered_on_the_cvar_scale(monkeypatch):
    """`var` must be a percent like its siblings on the same line.

    It printed "cvar=4.53% var=0.03732170883628583" - a raw unrounded
    fraction beside percents, so any reader comparing the two sees a 100x
    gap (NVDA 2026-09-12 market.md quoted only cvar, which is why it slipped
    through).
    """
    n = 120
    closes = [100.0 + 0.5 * i + 20.0 * math.sin(i / 3) for i in range(n)]
    fake = {"closes": closes, "opens": [], "highs": [], "lows": [], "volumes": []}
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: fake)
    out = T.get_tail_risk.invoke({"ticker": "AAPL", "alpha": 0.05})
    cvar = re.search(r"(?<![_a-z])cvar=(-?\d+\.\d+)%", out)
    var = re.search(r"(?<![_a-z])var=(-?\d+\.\d+)%", out)
    assert cvar and var, out
    assert float(var.group(1)) <= float(cvar.group(1))  # CVaR is the worse tail
    assert re.search(r"(?<![_a-z])var=-?\d+\.\d{3,}", out) is None


def test_swing_set_labels_the_stop_risk_unit(monkeypatch):
    """One tool prints two `risk=` fields with different units - the stop
    distance as a fraction of the close (0.0508, rendered as 5.08%) and the
    targets' 1R in price units (11.0976). Each must carry its unit."""
    closes = _uptrend()
    entry = closes[-1]

    # Monotone business dates: _ohlcv re-sorts by date, so a cycling fixture
    # would silently hand the tool a different "last" row than closes[-1].
    def _load(ticker):
        cl = {"AAPL": closes, "SPY": [200.0] * len(closes)}.get(ticker)
        if cl is None:
            return None
        return pd.DataFrame({
            "Date": pd.bdate_range("2025-01-01", periods=len(cl)).strftime("%Y-%m-%d"),
            "Open": cl,
            "High": [c + 2 for c in cl],
            "Low": [c - 2 for c in cl],
            "Close": cl,
            "Volume": [1_000_000] * len(cl),
        })

    with mock.patch(
        "tradingagents.agents.utils.analysis_tools._load_ohlcv_df", side_effect=_load
    ):
        out = T.get_swing_set.invoke({"ticker": "AAPL"})
    assert f"entry={entry:.4f}" in out, out
    m = re.search(
        r"structure_stop: swing_low=([\d.]+) stop=([\d.]+) risk=([\d.]+)% of close", out
    )
    assert m, out
    swing_low, stop, risk_pct = (float(x) for x in m.groups())
    assert risk_pct == pytest.approx((entry - stop) / entry * 100, abs=0.01)
    atr_m = re.search(r"ATR\(14, simple mean of TR\)=([\d.]+)", out)
    assert atr_m, out
    assert swing_low - stop == pytest.approx(float(atr_m.group(1)), abs=1e-3)
    # The targets line keeps its price-unit 1R and must not read as a percent.
    targets = [ln for ln in out.splitlines() if ln.strip().startswith("targets:")]
    assert len(targets) == 1 and "risk=" in targets[0] and "%" not in targets[0]


def test_swing_exits_names_the_r_reference(monkeypatch):
    """The 2R/3R targets are measured to THIS tool's stop reference (the
    chandelier), not to get_swing_set's structure stop: NVDA 2026-09-12
    printed 1R=6.7941 here vs 11.0976 there, from the same close. The line
    must name the reference, and R must be the distance to it."""
    monkeypatch.setattr(T, "_ohlcv", lambda ticker: _uptrend_ohlcv())
    out = T.get_swing_exits.invoke({"ticker": "AAPL"})
    ch = re.search(r"chandelier stop=([\d.]+)", out)
    ref = re.search(r"\(R vs chandelier stop ([\d.]+): 1R=([\d.]+)\)", out)
    t1 = re.search(r"t1=([\d.]+)", out)
    assert ch and ref and t1, out
    close = _uptrend_ohlcv()["closes"][-1]
    assert float(ref.group(1)) == pytest.approx(float(ch.group(1)))
    assert float(ref.group(2)) == pytest.approx(close - float(ch.group(1)), abs=1e-4)
    assert float(t1.group(1)) == pytest.approx(close + 2 * float(ref.group(2)), abs=1e-3)


def test_bollinger_pct_b_names_the_sd_convention(monkeypatch):
    """The deterministic band is the population SD; a vendor band built on the
    sample SD is sqrt(20/19)=1.026x wider (NVDA 2026-09-12: 231.83/208.05 vs
    232.14/207.74). The label must match the arithmetic."""
    closes = _uptrend()
    monkeypatch.setattr(V, "_ohlcv", lambda ticker: {"closes": closes})
    out = V.get_bollinger_pct_b.invoke({"ticker": "AAPL"})
    assert "population SD" in out
    mid = sum(closes[-20:]) / 20
    pop_sd = math.sqrt(sum((c - mid) ** 2 for c in closes[-20:]) / 20)
    m = re.search(r"lower=([\d.]+) upper=([\d.]+) mid=([\d.]+)", out)
    assert m, out
    lo, up, mid_out = (float(x) for x in m.groups())
    # The tool prints 2dp, so compare at that precision; the band half-width
    # is the population SD (a sample-SD band would be 2.6% wider here).
    assert mid_out == pytest.approx(mid, abs=5e-3)
    assert (up - mid_out) / 2 == pytest.approx(pop_sd, abs=5e-3)
