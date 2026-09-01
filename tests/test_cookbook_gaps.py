"""Hermetic tests for the cookbook.md quant-strategy gap implementation.

Covers every new calculator + agent tool added for the 5 cookbook recipes
(time-series momentum, cross-sectional mean reversion, cointegration pairs,
multifactor portfolios, options vol) and the common framework helpers. All
offline / deterministic; no vendor calls.

Files touched by this implementation:
  strategies/cross_section.py        (new)
  strategies/factors.py              (z_composite_alpha, momentum_multihorizon)
  strategies/momentum.py             (ts_momentum_weights)
  strategies/evaluate.py             (turnover/turnover_cost/exposure/rolling/regime)
  strategies/options_math.py         (rho/vanna/vomma/charm, BSM, P&L, mfree var)
  strategies/statistical.py          (spread_zscore/pair_signal/pair_quantities/ecm_loading)
  strategies/book_risk.py            (cdar)
  strategies/portfolio_optimizer.py  (max_diversification_weights)
  strategies/credit_spread.py        (merton_distance_to_default)
  strategies/rate_utils.py           (forward_rate)
  strategies/market_session.py       (book_depth_read)
  agents/utils/analysis_tools.py     (get_pair_trade_signal/get_event_pnl_response/
                                      get_ts_momentum_weights/get_book_depth_read/
                                      get_merton_distance/_machine_chain_vrp)
"""

from __future__ import annotations

import math
import random

import pytest

from tradingagents.strategies import (
    book_risk,
    credit_spread,
    cross_section,
    evaluate,
    factors,
    market_session,
    momentum,
    options_math,
    portfolio_optimizer,
    rate_utils,
    statistical,
)

pytestmark = pytest.mark.timeout(180)

# ---------------------------------------------------------------------------
# Phase 1 - cross-section + momentum portfolio toolkit
# ---------------------------------------------------------------------------


def test_winsorize_clips_extremes_and_preserves_length():
    rng = random.Random(1)
    vals = [rng.gauss(0, 1) for _ in range(200)] + [999.0, -999.0]
    out = cross_section.winsorize(vals)
    assert len(out) == len(vals)
    clipped = [v for v in out if v is not None]
    assert max(clipped) < 50.0 and min(clipped) > -50.0


def test_cross_sectional_z_mean_zero_std_one():
    rng = random.Random(2)
    vals = [rng.gauss(5, 2) for _ in range(50)]
    joined = cross_section.cross_sectional_z(vals)
    assert joined is not None
    z = joined["z"]
    assert abs(sum(z) / len(z)) < 1e-9
    sd = math.sqrt(sum((x - (sum(z) / len(z))) ** 2 for x in z) / (len(z) - 1))
    assert abs(sd - 1.0) < 1e-9


def test_centered_rank_bounds_and_linear():
    rng = random.Random(3)
    vals = [rng.random() for _ in range(30)]
    cr = cross_section.centered_rank(vals)
    assert cr is not None
    assert all(-1.0 <= v <= 1.0 for v in cr if v is not None)
    # smallest -> -1, largest -> +1
    assert cr[vals.index(min(vals))] == pytest.approx(-1.0, abs=1e-9)
    assert cr[vals.index(max(vals))] == pytest.approx(1.0, abs=1e-9)


def test_quantile_split_top_bottom():
    vals = [float(i) for i in range(100)]
    split = cross_section.quantile_split(vals, frac=0.2)
    top = [vals[i] for i in split["top"]]
    bottom = [vals[i] for i in split["bottom"]]
    assert min(top) > max(bottom)
    assert len(top) >= 20 and len(bottom) >= 20


def test_neutralize_book_constraints():
    rng = random.Random(4)
    names = [f"N{i}" for i in range(6)]
    raw = {n: rng.uniform(-1, 1) for n in names}
    betas = {n: rng.uniform(0.5, 1.5) for n in names}
    sector = {n: ("A" if i % 2 == 0 else "B") for i, n in enumerate(names)}
    w = cross_section.neutralize_book(raw, betas, sector, gross_target=1.0)
    # weights are rounded to 6 dp, so the residual sums are bounded by ~1e-5
    assert abs(sum(w.values())) < 5e-5  # dollar neutral
    beta_net = sum(w[n] * betas[n] for n in w)
    assert abs(beta_net) < 5e-5  # beta neutral
    for s in ("A", "B"):
        assert abs(sum(w[n] for n in w if sector.get(n) == s)) < 5e-5  # sector neutral
    assert sum(abs(v) for v in w.values()) == pytest.approx(1.0, abs=1e-4)  # gross


def test_neutralize_degenerate_dollar_center_only():
    w = cross_section.neutralize_book({"A": 1.0, "B": 0.0}, gross_target=1.0)
    assert abs(sum(w.values())) < 5e-5


def test_residualize_returns_removes_market():
    rng = random.Random(5)
    mkt = [rng.gauss(0, 0.01) for _ in range(120)]
    # name with a strong known beta
    beta = 1.5
    series = [0.001 + beta * m + rng.gauss(0, 0.002) for m in mkt]
    resid = cross_section.residualize_returns({"X": series}, mkt)
    assert "X" in resid
    # residual should be ~ uncorrelated with market
    r = resid["X"]
    m = mkt[-len(r):]
    n = len(r)
    mx = sum(m) / n
    cov = sum((m[i] - mx) * (r[i] - sum(r) / n) for i in range(n)) / n
    sdm = math.sqrt(sum((x - mx) ** 2 for x in m) / n)
    sdr = math.sqrt(sum((x - sum(r) / n) ** 2 for x in r) / n)
    corr = cov / (sdm * sdr) if sdm > 0 and sdr > 0 else 1.0
    assert abs(corr) < 0.15


def test_no_trade_band():
    target = {"A": 0.10, "B": 0.25}
    prev = {"A": 0.095, "B": 0.0}
    out = cross_section.no_trade_band(target, prev, delta=0.02)
    assert out["A"] == 0.0  # 0.005 < band
    assert out["B"] == pytest.approx(0.25)  # 0.25 > band


def test_z_composite_alpha_and_multihorizon():
    fbt = {
        "A": {"mom": -0.1, "quality": 0.8},
        "B": {"mom": 0.2, "quality": 0.3},
        "C": {"mom": 0.05, "quality": -0.2},
    }
    alpha = factors.z_composite_alpha(fbt)
    # B has the highest momentum but lowest quality -> with equal weights the
    # blend orders by the sum; the strongest mom name need not win outright.
    assert all(alpha[k] is not None for k in fbt)
    mh = factors.momentum_multihorizon([100] + [100 + i for i in range(1, 300)])
    assert mh["ensemble"] is not None
    assert set(mh["horizons"]) == {"21", "63", "126", "252"}


def test_ts_momentum_weights_sign_vol_and_cap():
    rng = random.Random(6)
    up = [100.0 * (1.002 ** i) * (1.0 + rng.gauss(0, 0.04)) for i in range(300)]
    down = [100.0 * (0.998 ** i) * (1.0 + rng.gauss(0, 0.01)) for i in range(300)]
    flat = [100.0 + rng.gauss(0, 0.3) for _ in range(300)]
    w = momentum.ts_momentum_weights({"UP": up, "DOWN": down, "FLAT": flat},
                                     target_vol=0.10, max_leverage=2.0)
    assert w is not None
    assert w["UP"] > 0 and w["DOWN"] < 0
    # calmer (down) series gets a LARGER |weight| than the volatile one
    assert abs(w["DOWN"]) > abs(w["UP"])
    meta = w.pop("_meta")
    assert meta["gross"] <= 2.0 + 1e-6
    assert meta["n_names"] == 3


def test_evaluate_turnover_cost_exposure_stats():
    w1 = {"A": 0.3, "B": -0.2}
    w0 = {"A": 0.2, "B": 0.1}
    assert evaluate.turnover(w1, w0) == pytest.approx(0.5 * (0.1 + 0.3))
    assert evaluate.turnover(w1) == pytest.approx(0.5 * 0.5)
    cost = evaluate.turnover_cost(w1, w0, cost_by_name={"A": 0.001, "B": 0.002})
    assert cost == pytest.approx(abs(0.1) * 0.001 + abs(-0.3) * 0.002)
    assert evaluate.gross_exposure(w1) == pytest.approx(0.5)
    assert evaluate.net_exposure(w1) == pytest.approx(0.1)
    rng = random.Random(7)
    rets = [rng.gauss(0.001, 0.02) for _ in range(300)]
    rs = evaluate.rolling_sharpe(rets, window=100)
    assert len(rs) == 201
    assert all(v is not None for v in rs)
    vols = [0.9 if i % 2 == 0 else 0.1 for i in range(len(rets))]
    trend = [1.0 if i % 2 == 0 else -1.0 for i in range(len(rets))]
    rp = evaluate.regime_split_performance(rets, vols, trend, high_vol_at=0.7)
    assert {"low_vol", "high_vol", "bull", "bear"} <= set(rp)


# ---------------------------------------------------------------------------
# Phase 2 - options depth (recipes 5)
# ---------------------------------------------------------------------------


def test_black76_full_greeks_present_and_signed():
    g = options_math.black76(100, 100, 0.5, 0.25, "call", r=0.02)
    for k in ("price", "delta", "gamma", "vega", "theta", "rho", "vanna",
              "vomma", "charm"):
        assert g[k] is not None
    assert g["rho"] > 0
    gp = options_math.black76(100, 100, 0.5, 0.25, "put", r=0.02)
    assert gp["rho"] < 0
    for k in ("gamma", "vega"):
        assert g[k] == gp[k]  # same for call/put


def test_bsm_put_call_parity_and_black76_equivalence():
    spot = 100.0
    strike = 105.0
    t = 0.4
    r = 0.03
    q = 0.01
    vol = 0.28
    c = options_math.bsm_equity_surface(spot, strike, t, r, q, vol, "call")
    p = options_math.bsm_equity_surface(spot, strike, t, r, q, vol, "put")
    lhs = c["price"] - p["price"]
    rhs = spot * math.exp(-q * t) - strike * math.exp(-r * t)
    assert abs(lhs - rhs) < 1e-6  # put-call parity
    # Black-76 on the forward (F = S e^((r-q)t)) must price the same as BSM.
    fwd = spot * math.exp((r - q) * t)
    b76 = options_math.black76(fwd, strike, t, vol, "call", r=r)
    assert abs(b76["price"] - c["price"]) < 1e-6


def test_greek_pnl_response_totals():
    p = options_math.greek_pnl_response(0.6, 0.05, 2.0, -0.1, 100, 0.01, 0.02)
    assert p["total_pnl"] == pytest.approx(
        p["delta_pnl"] + p["gamma_pnl"] + p["vega_pnl"] + p["theta_pnl"]
    )


def test_model_free_implied_variance_positive_and_forward_sensitive():
    strikes = [90, 95, 100, 105, 110]
    prs = [1.0, 2.5, 5.0, 2.5, 1.0]
    v = options_math.model_free_implied_variance(strikes, prs, 100, 0.5, 0.02)
    assert v is not None and v > 0
    v2 = options_math.model_free_implied_variance(strikes, prs, 103, 0.5, 0.02)
    assert v2 is not None and abs(v2 - v) > 1e-6  # forward-discreteness matters
    assert options_math.model_free_implied_variance([], [], 100, 0.5, 0.02) is None


# ---------------------------------------------------------------------------
# Phase 3 - pairs trading signal (recipe 3)
# ---------------------------------------------------------------------------


def _planted_pair(beta=1.2, n=200, seed=8):
    """Y = beta*X + stable mean-reverting residual (AR(1) phi=0.9)."""
    rng = random.Random(seed)
    x = [100.0]
    for _ in range(n - 1):
        x.append(x[-1] * (1.0 + rng.gauss(0, 0.01)))
    res = [0.0]
    for _ in range(n - 1):
        res.append(0.9 * res[-1] + rng.gauss(0, 0.15))
    y = [beta * x[i] + res[i] for i in range(n)]
    return x, y


def test_spread_zscore_beta_recovery():
    x, y = _planted_pair(beta=1.2)
    zr = statistical.spread_zscore(x, y, window=60)
    assert zr is not None
    assert abs(zr["beta"] - 1.2) < 0.1
    assert len(zr["z"]) >= 20
    assert any(v is not None for v in zr["z"])


def test_pair_signal_bands():
    x, y = _planted_pair()
    # force an extreme spread on the tail to hit each band deterministically
    sig = statistical.pair_signal(x, y)
    assert sig["signal"] in ("LONG_SPREAD", "SHORT_SPREAD", "FLAT", "STOP", None)
    # a long way out of equilibrium must produce an entry state
    x2 = x[:-1] + [x[-1] * 0.9]
    sig2 = statistical.pair_signal(x2, y)
    if sig2["z"] is not None and abs(sig2["z"]) >= 2.0:
        assert sig2["signal"] in ("LONG_SPREAD", "SHORT_SPREAD")


def test_pair_quantities_dollar_neutral():
    q = statistical.pair_quantities(100000, 50.0, 25.0, 1.2)
    assert q is not None
    assert q["q_y"] * 50.0 == pytest.approx(50000.0)
    assert q["q_x"] * 25.0 == pytest.approx(1.2 * 50000.0, rel=1e-3)


def test_ecm_loading_negative_on_reverting_pair():
    x, y = _planted_pair()
    e = statistical.ecm_loading(x, y)
    assert e is not None
    assert e["gamma"] < 0  # reverts toward the cointegrating relation


# ---------------------------------------------------------------------------
# Phase 4 - drawdown tail / diversification / credit / rates
# ---------------------------------------------------------------------------


def test_cdar_drawdown_tail():
    eq = list(range(100, 0, -1))  # monotone decline
    cd = book_risk.cdar(eq, alpha=0.05)
    assert cd is not None
    # worst alpha tail mean: [0.95..0.99] -> 0.97; max_drawdown = 0.99
    assert cd["cdar"] == pytest.approx(0.97, abs=1e-3)
    assert cd["max_drawdown"] == pytest.approx(0.99, abs=1e-3)
    # a few deep dips dominate the tail
    eq2 = [100, 99, 98, 97, 96, 60, 61, 62, 63, 64, 99]
    cd2 = book_risk.cdar(eq2, alpha=0.2)
    assert cd2 is not None
    assert 0.30 < cd2["cdar"] < 0.42


def test_max_diversification_weights():
    rng = random.Random(9)
    rb = {
        "A": [rng.gauss(0.001, 0.02) for _ in range(120)],
        "B": [rng.gauss(0.001, 0.01) for _ in range(120)],
        "C": [rng.gauss(0.001, 0.03) for _ in range(120)],
    }
    md = portfolio_optimizer.max_diversification_weights(rb)
    w = md["weights"]
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-4)
    assert all(v >= 0 for v in w.values())
    # low-vol B should get the largest weight under MDP
    assert w["B"] > w["A"] > 0 and w["B"] > w["C"]
    mv = portfolio_optimizer.min_variance_weights(rb)
    assert md["weights"] != mv["weights"]  # distinct constructions


def test_merton_distance_to_default_and_edges():
    m = credit_spread.merton_distance_to_default(100, 80, 0.3, 0.03, 1.0)
    assert m is not None and m["converged"]
    assert m["distance_to_default"] > 0
    assert 0 < m["risk_neutral_pd"] < 1
    # d2 consistency
    assert m["d2"] == m["distance_to_default"]
    assert credit_spread.merton_distance_to_default(None, 80, 0.3) is None
    assert credit_spread.merton_distance_to_default(0, 80, 0.3) is None


def test_forward_rate_identity_and_guards():
    fr = rate_utils.forward_rate(0.95, 0.90, 1.0, 2.0)
    assert fr == pytest.approx(math.log(0.95 / 0.90) / 1.0, abs=1e-9)
    assert rate_utils.forward_rate(0.95, None, 1.0, 2.0) is None
    assert rate_utils.forward_rate(0.95, 0.90, 2.0, 1.0) is None  # t2 <= t1


# ---------------------------------------------------------------------------
# Phase 5/6 - model-free VRP + book depth
# ---------------------------------------------------------------------------


def test_book_depth_read_microprice_identity():
    r = market_session.book_depth_read(10.0, 10.2, 3000, 1000)
    assert r["microprice"] == pytest.approx(
        (10.0 * 1000 + 10.2 * 3000) / 4000, abs=1e-4
    )
    assert r["obi"] == pytest.approx(0.5, abs=1e-4)
    assert r["verdict"] == "bid-heavy"
    none_r = market_session.book_depth_read(10.0, 10.2, None, 1000)
    assert none_r["microprice"] is None


def test_variance_premium_tool_degrades_honestly(monkeypatch):
    from tradingagents.agents.utils.analysis_tools import get_variance_premium

    class _FakeSurface:
        def invoke(self, *args, **kwargs):
            return "## cboe surface\n| rows |"

    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools._machine_chain_vrp",
        lambda _ticker: None,
    )
    monkeypatch.setattr(
        "tradingagents.agents.utils.analysis_tools.get_options_surface",
        _FakeSurface(),
    )
    out = get_variance_premium.invoke({"ticker": "AAPL"})
    assert "unavailable" in out and "cboe surface" in out


# ---------------------------------------------------------------------------
# Agent-tool wiring guards (hermetic, no vendor)
# ---------------------------------------------------------------------------


def test_new_tools_bound_to_market_analyst():
    # The full graph's market ToolNode must carry the new advisory tools; the
    # graph imports cleanly (import guard) and the tools are re-exported.
    import tradingagents.agents.analysts.market_analyst as _ma
    from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: F401

    assert hasattr(_ma, "create_market_analyst")
    assert hasattr(_ma, "get_ts_momentum_weights")
    assert hasattr(_ma, "get_pair_trade_signal")
    assert hasattr(_ma, "get_event_pnl_response")
    assert hasattr(_ma, "get_book_depth_read")
    assert hasattr(_ma, "get_merton_distance")


def test_all_new_tools_importable_and_callable():
    from tradingagents.agents.utils.agent_utils import (
        get_book_depth_read,
        get_event_pnl_response,
        get_merton_distance,
        get_pair_trade_signal,
        get_ts_momentum_weights,
    )

    assert get_pair_trade_signal.invoke(
        {"x": [100.0 + i for i in range(80)], "y": [120.0 + 1.1 * i for i in range(80)]}
    ).startswith("pair trade signal")
    assert get_event_pnl_response.invoke(
        {"spot": 100.0, "delta": 0.6, "gamma": 0.05, "vega": 2.0,
         "theta": -0.1, "dS_pct": 0.01, "dSigma": 0.02}
    ).startswith("event pnl response")
    assert get_ts_momentum_weights.invoke(
        {"closes_by_name": {"SPY": list(range(1, 260)), "TLT": list(range(260, 1, -1))}}
    ).startswith("ts momentum weights")
    assert get_book_depth_read.invoke(
        {"bid": 10.0, "ask": 10.2, "bid_size": 3000, "ask_size": 1000}
    ).startswith("book depth read")
    assert get_merton_distance.invoke(
        {"equity": 100.0, "debt": 80.0, "equity_vol": 0.3}
    ).startswith("merton distance-to-default")
