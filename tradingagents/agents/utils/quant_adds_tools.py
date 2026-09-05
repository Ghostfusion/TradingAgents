"""Agent tools for today's quant adds: regime state, kalman spread, execution
multiplier, Black-Litterman allocation.

Each wraps a pure ``strategies/*`` calculation over the vendor-chain OHLCV
(shared ``_ohlcv`` cache) and returns a rendered read - advisory, no
fabrication, explicit "unavailable" on missing data. Bound to the analyst
tool lists + ToolNode like the other computed-analysis tools.
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool

from tradingagents.agents.utils.analysis_tools import _benchmark_closes, _ohlcv


@tool
def get_regime_state(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Multi-axis regime state for a ticker: Trend (EMA20-EMA50)/ATR14, Volatility
    ATR14/Median(ATR), Relative vs the market benchmark, Drawdown from the 252d
    high - each already-labeled (strategies/regime_state.py, the regime-gate
    material). Returns every dimension + the combined F_regime size factor
    (1.0 Bull/Normal .. 0.0 Crash). Call before any 'the regime is ...' claim
    that goes beyond the single label from get_regime_read. Advisory.
    """
    try:
        from tradingagents.strategies.regime_state import regime_state as _rs
    except Exception as exc:  # noqa: BLE001
        return f"regime state unavailable: {exc}"
    oh = _ohlcv(ticker)
    closes = oh.get("closes") or []
    if len(closes) < 60:
        return f"regime state unavailable for {ticker}: insufficient price history"
    bench = _benchmark_closes()
    try:
        rs = _rs(closes, oh.get("highs") or None, oh.get("lows") or None, benchmark=bench or None)
    except Exception as exc:  # noqa: BLE001 - advisory read degrades
        return f"regime state unavailable for {ticker}: {exc}"
    lb = rs["labels"]
    out = (
        f"regime state {ticker}: trend={lb['trend']} (score {rs['trend']['score']}), "
        f"volatility={lb['volatility']} (ratio {rs['volatility']['ratio']}), "
        f"relative={lb['relative']} ({rs['relative']['relative_ret']}), "
        f"drawdown={lb['drawdown']} ({rs['drawdown']['drawdown']}), "
        f"F_regime={rs['factor']} (crash={rs.get('crash')})"
    )
    # Optional HMM regime label (strategies/regime.hmm_regime): a 2-state
    # Gaussian-HMM macro regime - 'unknown' without hmmlearn (never a guess).
    try:
        from tradingagents.strategies.regime import hmm_regime

        out += f" | hmm={hmm_regime(closes, n_states=2)}"
    except Exception:  # noqa: BLE001 - advisory axis degrades
        pass
    return out


@tool
def get_kalman_spread(
    x_ticker: Annotated[str, "anchor ticker"],
    y_ticker: Annotated[str, "pair ticker"],
    process_noise: Annotated[float, "Q state noise (beta drift), default 1e-4"] = 1e-4,
    measurement_noise: Annotated[float, "R observation noise, default 1e-2"] = 1e-2,
) -> str:
    """Kalman-filter dynamic hedge-ratio spread for a pair (online, drifts with
    the data instead of a static rolling-OLS beta). Returns the adaptive beta,
    the model spread and a mean-reversion signal (+1/-1/0 on the last z). Call
    before any 'this pair is hedged at beta X / mean-reverting' claim. Advisory.
    """
    try:
        from tradingagents.strategies.statistical_kalman import kalman_spread
    except Exception as exc:  # noqa: BLE001
        return f"kalman spread unavailable: {exc}"
    x = _ohlcv(x_ticker).get("closes") or []
    y = _ohlcv(y_ticker).get("closes") or []
    if len(x) < 20 or len(y) < 20:
        return f"kalman spread unavailable for {x_ticker}/{y_ticker}: insufficient history"
    try:
        k = kalman_spread(x, y, process_noise=process_noise, measurement_noise=measurement_noise)
    except Exception as exc:  # noqa: BLE001
        return f"kalman spread unavailable for {x_ticker}/{y_ticker}: {exc}"
    if k["n"] < 5:
        return f"kalman spread unavailable for {x_ticker}/{y_ticker}: too few aligned obs"
    sig = {1: "LONG spread (z>1.5)", -1: "SHORT spread (z<-1.5)", 0: "neutral"}.get(k["signal"], "n/a")
    return (
        f"kalman spread {x_ticker}->{y_ticker}: beta={k['last_beta']} (n={k['n']}), "
        f"last_spread={k['last_spread']}, signal={sig} (mean-reversion)"
    )


@tool
def get_position_risk_multiplier(
    ticker: Annotated[str, "ticker symbol"],
    knife_factor: Annotated[float, "composite knife factor (0..1), default 1"] = 1.0,
    regime_factor: Annotated[float, "regime factor (0..1), default 1"] = 1.0,
    vol_cap_factor: Annotated[float, "vol-cap ladder factor (0..1), default 1"] = 1.0,
) -> str:
    """The execution multiplier over the two-tier soft/hard policy
    (strategies/risk_multiplier.py - the halve-not-block material): soft guards
    multiply exposure down, hard guards (halt / insufficient_liquidity /
    max_portfolio_risk / data_quality_failure / broker_safety) block to 0.
    Pass the computed factors; any hard guard name blocks regardless. Call
    before any 'the position should be sized X because of risk' claim. Advisory.
    """
    try:
        from tradingagents.strategies.risk_multiplier import RiskMultiplier, combine
    except Exception as exc:  # noqa: BLE001
        return f"risk multiplier unavailable: {exc}"
    try:
        kf = max(0.0, min(1.0, float(knife_factor)))
        rf = max(0.0, min(1.0, float(regime_factor)))
        vf = max(0.0, min(1.0, float(vol_cap_factor)))
    except (TypeError, ValueError):
        return f"risk multiplier unavailable for {ticker}: non-numeric factor"
    r = combine(RiskMultiplier(soft={"regime": rf, "vol_cap": vf, "knife": kf}))
    return (
        f"execution multiplier {ticker}: factor={r['factor']} "
        f"(regime {rf}, vol_cap {vf}, knife {kf}, blocked={r['blocked']})"
    )


@tool
def get_no_trade_guard_band(
    ticker: Annotated[str, "ticker symbol"],
    cost_bps: Annotated[float, "proportional transaction cost in bps, default 10"] = 10.0,
    risk_aversion: Annotated[float, "gamma in the guard-band formula, default 1.0"] = 1.0,
    target_weight: Annotated[float | None, "target portfolio weight (0..1), optional"] = None,
    current_weight: Annotated[float | None, "current portfolio weight (0..1), optional"] = None,
) -> str:
    """No-trade guard band (Davis-Norman / Shreve-Soner): the half-width h of
    the rebalancing inaction zone for a position, ``h = (1.5*lambda*sigma^2/
    gamma)^(1/3)`` over the ticker's daily returns. A target-weight drift
    smaller than h does not justify paying transaction costs - rebalance only
    beyond the band edge. Give ``target_weight``/``current_weight`` for the
    actual rebalance decision. Call before any 'should we rebalance X' claim.
    Advisory.
    """
    try:
        from tradingagents.strategies.knife_guard import (
            guard_band_halfwidth,
            should_trade,
        )
    except Exception as exc:  # noqa: BLE001
        return f"no-trade guard band unavailable: {exc}"
    closes = _ohlcv(ticker).get("closes") or []
    if len(closes) < 30:
        return f"no-trade guard band unavailable for {ticker}: insufficient history"
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    sigma = (sum((r - sum(rets) / len(rets)) ** 2 for r in rets) / len(rets)) ** 0.5
    lam = float(cost_bps) / 10_000.0
    h = guard_band_halfwidth(lam, sigma, float(risk_aversion))
    if h is None:
        return f"no-trade guard band unavailable for {ticker}: degenerate inputs"
    out = (
        f"no-trade guard band {ticker}: h={h:.4f} (cost {cost_bps:.0f}bps, "
        f"sigma={sigma:.4f}, gamma={float(risk_aversion):.2f})"
    )
    if target_weight is not None and current_weight is not None:
        drift = abs(float(target_weight) - float(current_weight))
        goes = should_trade(drift, h)
        out += (
            f"; decision: {'REBALANCE' if goes else 'NO-TRADE'} "
            f"(w_target={float(target_weight):.3f}, w_current={float(current_weight):.3f}, "
            f"drift {drift:.3f} vs h {h:.3f})"
        )
    else:
        out += " - rebalance only when |w_target-w_current| > h"
    return out


@tool
def get_allocation_black_litterman(
    tickers: Annotated[list, "names to allocate (market-cap weighted prior)"],
    view_long: Annotated[str, "ticker of a long view, None to skip"] = "",
    view_long_q: Annotated[float, "expected excess return of the long view, default 0.05"] = 0.05,
    market_caps: Annotated[dict, "name -> market cap (USD), default {}"] = None,
) -> str:
    """Black-Litterman allocation: market-implied equilibrium prior
    (Pi = lambda*Cov*w_mkt) blended with one investor view toward the posterior
    (the six-pillar formula, maximized to weights). Pass ``view_long`` for a
    single bullish view (the tool builds P=[-1..+1] and Q) or leave it empty for
    pure equilibrium. Call before any 'allocation to X given the analysts'
    views' claim. Advisory.
    """
    try:
        from tradingagents.strategies.portfolio_optimizer import black_litterman_weights
    except Exception as exc:  # noqa: BLE001
        return f"black-litterman unavailable: {exc}"
    names = [str(t).upper() for t in (tickers or [])]
    if len(names) < 2:
        return "black-litterman unavailable: need at least two names"
    rets = {}
    caps = dict(market_caps or {})
    for nm in names:
        c = _ohlcv(nm).get("closes") or []
        if len(c) < 30:
            return f"black-litterman unavailable for {nm}: insufficient history"
        rets[nm] = [c[i] / c[i - 1] - 1.0 for i in range(1, len(c))]
        if nm not in caps:
            caps[nm] = 1.0  # per-name cap degrades to 1 (equal prior)
    p = q = om = None
    if view_long and view_long.upper() in names:
        k = names.index(view_long.upper())
        p = [[-1.0 if i != k else (len(names) - 1) for i in range(len(names))]]
        q = [float(view_long_q)]
        om = [0.05 ** 2]
    try:
        r = black_litterman_weights(rets, caps, views_p=p, views_q=q, view_uncertainty_omega=om)
    except Exception as exc:  # noqa: BLE001
        return f"black-litterman unavailable: {exc}"
    w = r.get("weights") or {}
    line = "black-litterman allocation: " + "; ".join(f"{nm}={w.get(nm):.1%}" for nm in names if nm in w)
    if r.get("note"):
        line += f"  ({r['note']})"
    return line
