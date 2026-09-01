"""Phase 0 - cost-aware evaluation harness.

Pure helpers for measuring agent/screener outcomes honestly: net-of-cost
metrics, walk-forward splits and overfitting guards. Used by the memory-log
realized-return path and by per-phase validation.

Evaluation breadth (Lean L3): Sortino, downside deviation, beta/alpha/
Treynor/information-ratio, Probabilistic Sharpe, rolling beta and underwater
drawdown collection — so a strategy is judged on more than a single Sharpe +
max-drawdown (the classic overfit hole).

All functions are vectorized over simple sequences (lists) so they work
offline on synthetic data and on exported memory-log returns.
"""

from __future__ import annotations

import math


def _clean(values: list) -> list[float]:
    """Finite-float clean of a series (drops None / non-numeric / non-finite)."""
    out: list[float] = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def net_returns(
    returns: list[float],
    cost_bps: float = 10.0,
    illiq: float | None = None,
    illiq_cost_mult: float = 1e5,
) -> list[float | None]:
    """Subtract a per-trade cost (basis points) from each period return.

    Item 3 (liquidity-aware costs): when ``illiq`` (Amihud ILLIQ) is provided,
    scale cost up for illiquid names (mirrors ``exits.net_of_cost``). None
    ``illiq`` keeps the flat-cost behavior (backward compatible).
    """
    cost = cost_bps / 10000.0
    if illiq is not None:
        cost += float(illiq) * float(illiq_cost_mult) / 10000.0
    return [r - cost if r is not None else None for r in returns]


def total_return(returns: list[float]) -> float:
    """Compounded total return; None entries are treated as zero-return gaps."""
    prod = 1.0
    for r in returns:
        if r is not None:
            prod *= 1.0 + r
    return prod - 1.0


def cagr(returns: list[float], periods_per_year: float = 252.0) -> float:
    """Annualized compound growth over the return series."""
    n = sum(1 for r in returns if r is not None)
    if n <= 0:
        return 0.0
    years = n / periods_per_year
    if years <= 0:
        return 0.0
    return (1.0 + total_return(returns)) ** (1.0 / years) - 1.0


def volatility(returns: list[float], periods_per_year: float = 252.0) -> float:
    """Annualized standard deviation of returns."""
    vals = _clean(returns)
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return math.sqrt(var * periods_per_year)


def sharpe(returns: list[float], risk_free: float = 0.0,
           periods_per_year: float = 252.0) -> float:
    """Annualized Sharpe ratio."""
    vol = volatility(returns, periods_per_year)
    if vol <= 0:
        return 0.0
    return (cagr(returns, periods_per_year) - risk_free) / vol


def deflated_sharpe(returns: list[float], n_trials: int = 100,
                    risk_free: float = 0.0,
                    periods_per_year: float = 252.0) -> float:
    """Lopez de Prado style deflated Sharpe: penalize multi-trial tuning.

    The expected maximum Sharpe across n independent trials is approximated
    (Euler-Mascheroni-based) and subtracted from the observed Sharpe.
    """
    observed = sharpe(returns, risk_free, periods_per_year)
    if n_trials <= 1:
        return observed
    # Approximation of E[max Z] for standard normals under independence.
    expected_max = math.sqrt(2.0 * math.log(n_trials))
    return observed - expected_max


def max_drawdown(equity_curve: list[float]) -> float:
    """Maximum peak-to-trough drawdown of a cumulative equity curve."""
    peak = float("-inf")
    worst = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak if peak > 0 else 0.0
        worst = max(worst, dd)
    return worst


def equity_curve(returns: list[float], start: float = 100.0) -> list[float]:
    """Cumulative equity curve from period returns."""
    curve: list[float] = []
    level = start
    for r in returns:
        level *= 1.0 + (r if r is not None else 0.0)
        curve.append(level)
    return curve


def walk_forward_splits(returns: list[float], train_len: int, test_len: int):
    """Yield (train, test) return slices for walk-forward evaluation."""
    i = 0
    while i + train_len + test_len <= len(returns):
        yield returns[i:i + train_len], returns[i + train_len:i + train_len + test_len]
        i += test_len


def pbo_flag(results_by_trial: list[float], test_results: list[float],
             threshold: float = 0.0) -> bool:
    """Crude overfit flag: best-trial in-sample picks fail out-of-sample."""
    if not results_by_trial or not test_results:
        return False
    best_idx = max(range(len(results_by_trial)), key=lambda i: results_by_trial[i])
    return test_results[best_idx] < threshold


def skewness(returns: list[float]) -> float | None:
    """Standardized skewness (γ3); None for <3 finite observations."""
    vals = _clean(returns)
    if len(vals) < 3:
        return None
    n = len(vals)
    mean = sum(vals) / n
    m2 = sum((v - mean) ** 2 for v in vals) / n
    if m2 == 0:
        return None
    m3 = sum((v - mean) ** 3 for v in vals) / n
    return m3 / (m2 ** 1.5)


def kurtosis(returns: list[float]) -> float | None:
    """Standardized kurtosis (γ4, normal = 3); None for <4 observations."""
    vals = _clean(returns)
    if len(vals) < 4:
        return None
    n = len(vals)
    mean = sum(vals) / n
    m2 = sum((v - mean) ** 2 for v in vals) / n
    if m2 == 0:
        return None
    m4 = sum((v - mean) ** 4 for v in vals) / n
    return m4 / (m2 ** 2)


def downside_deviation(returns: list[float], mar: float = 0.0,
                       periods_per_year: float = 252.0) -> float | None:
    """Annualized downside deviation about a minimum-return target (MAR).

    Only observations below the target contribute (Lean's Sortino
    denominator); None for an empty/short series.
    """
    vals = _clean(returns)
    if not vals:
        return None
    dd = sum(max(mar - v, 0.0) ** 2 for v in vals) / len(vals)
    return math.sqrt(dd * periods_per_year)


def sortino(returns: list[float], mar: float = 0.0,
            periods_per_year: float = 252.0) -> float | None:
    """Annualized Sortino: excess CAGR over target per unit of downside dev."""
    ddev = downside_deviation(returns, mar, periods_per_year)
    if ddev is None or ddev <= 0:
        return None
    return (cagr(returns, periods_per_year) - mar) / ddev


def tracking_error(returns: list[float], benchmark: list[float],
                   periods_per_year: float = 252.0) -> float | None:
    """Annualized std dev of (algo - benchmark) period returns."""
    r = _clean(returns)
    b = _clean(benchmark)
    n = min(len(r), len(b))
    if n < 2:
        return None
    diff = [r[i] - b[i] for i in range(n)]
    md = sum(diff) / n
    var = sum((d - md) * (d - md) for d in diff) / (n - 1)
    return math.sqrt(var * periods_per_year)


def information_ratio(returns: list[float], benchmark: list[float],
                      periods_per_year: float = 252.0) -> float | None:
    """Annualized excess return per unit of tracking error."""
    te = tracking_error(returns, benchmark, periods_per_year)
    if te is None or te <= 0:
        return None
    return (cagr(returns, periods_per_year) - cagr(benchmark, periods_per_year)) / te


def beta(returns: list[float], benchmark: list[float],
         periods_per_year: float = 252.0) -> float | None:
    """Algo beta vs benchmark: cov(algo, bench) / var(bench)."""
    r = _clean(returns)
    b = _clean(benchmark)
    n = min(len(r), len(b))
    if n < 2:
        return None
    rb = r[:n]
    bb = b[:n]
    mr = sum(rb) / n
    mb = sum(bb) / n
    varb = sum((x - mb) ** 2 for x in bb) / (n - 1)
    if varb <= 0:
        return None
    cov = sum((rb[i] - mr) * (bb[i] - mb) for i in range(n)) / (n - 1)
    return cov / varb


def alpha(returns: list[float], benchmark: list[float], risk_free: float = 0.0,
          periods_per_year: float = 252.0) -> float | None:
    """Jensen's alpha: annPerf - (rf + beta*(benchAnnPerf - rf))."""
    b = beta(returns, benchmark, periods_per_year)
    if b is None:
        return None
    return (cagr(returns, periods_per_year) - risk_free
            - b * (cagr(benchmark, periods_per_year) - risk_free))


def treynor(returns: list[float], benchmark: list[float], risk_free: float = 0.0,
            periods_per_year: float = 252.0) -> float | None:
    """Excess annual return per unit of beta."""
    b = beta(returns, benchmark, periods_per_year)
    if b is None or b == 0:
        return None
    return (cagr(returns, periods_per_year) - risk_free) / b


def rolling_beta(returns: list[float], benchmark: list[float],
                 window: int = 132) -> list[float | None]:
    """Per-window beta series over aligned returns (Lean window 132 default)."""
    r = _clean(returns)
    b = _clean(benchmark)
    out: list[float | None] = []
    for end in range(window, min(len(r), len(b)) + 1):
        out.append(beta(r[end - window:end], b[end - window:end]))
    return out


def probabilistic_sharpe(returns: list[float], benchmark_sharpe: float = 0.0,
                         periods_per_year: float = 252.0) -> float | None:
    """Bailey & Lopez de Prado Probabilistic Sharpe Ratio.

    Uses the NON-annualized per-observation Sharpe (mean/std) as the point
    estimate, with skewness/kurtosis correction inside the estimator's
    standard error — PSR = Phi((SR_obs - SR_bench) /
    sqrt((1 - g3*SR + (g4-1)/4*SR^2)/(n-1))). None for <4 observations or a
    degenerate estimator variance. Advisory significance, not a mandate.
    """
    vals = _clean(returns)
    if len(vals) < 4:
        return None
    mean = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))
    if sd <= 0:
        return None
    sr = mean / sd
    g3 = skewness(vals)
    g4 = kurtosis(vals)  # standardized kurtosis, normal = 3
    if g3 is None or g4 is None:
        return None
    var_est = (1 - g3 * sr + (g4 - 1) / 4 * sr ** 2) / (len(vals) - 1)
    if var_est <= 0:
        return None
    z = (sr - benchmark_sharpe) / math.sqrt(var_est)
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def underwater_drawdowns(equity: list[float]) -> list[dict]:
    """Sequence of peak-to-trough-to-recovery drawdown events.

    Each event: ``{'peak','trough','depth','recovery'}`` where ``recovery`` is
    the number of bars to get back to the prior peak (None if still underwater
    at series end). Complement to the single ``max_drawdown`` scalar.
    """
    vals = _clean(equity)
    events: list[dict] = []
    if len(vals) < 2:
        return events
    peak = vals[0]
    trough = vals[0]
    trough_i = 0
    for i, v in enumerate(vals[1:], start=1):
        if v >= peak:
            if trough < peak:
                events.append({
                    "peak": peak,
                    "trough": trough,
                    "depth": (peak - trough) / peak if peak > 0 else 0.0,
                    "recovery": i - trough_i,
                })
            peak = v
            trough = v
            trough_i = i
        elif v < trough:
            trough = v
            trough_i = i
    if trough < peak:
        events.append({
            "peak": peak,
            "trough": trough,
            "depth": (peak - trough) / peak if peak > 0 else 0.0,
            "recovery": None,
        })
    return events


def calmar_ratio(returns: list[float], periods_per_year: float = 252.0) -> float | None:
    """Calmar ratio = annualized CAGR / max drawdown magnitude.

    0/positive-drawdown edge returns None (no meaningful risk ratio). Guards
    on <2 observations like the other CAGR-based stats.
    """
    vals = _clean(returns)
    if len(vals) < 2:
        return None
    eq = equity_curve(vals)
    mdd = max_drawdown(eq)
    if mdd <= 0:
        return None
    c = cagr(vals, periods_per_year)
    if c is None:
        return None
    return c / mdd


def ulcer_index(returns: list[float]) -> float | None:
    """Ulcer index = sqrt(mean(periodic drawdown^2)) over the equity curve.

    Penalizes sustained, not just the deepest, drawdowns (a Nautilus
    ready-made stat). None on <2 observations.
    """
    vals = _clean(returns)
    if len(vals) < 2:
        return None
    eq = equity_curve(vals)
    peak = eq[0]
    dds: list[float] = []
    for v in eq:
        peak = max(peak, v)
        dds.append((peak - v) / peak if peak > 0 else 0.0)
    mean_sq = sum(d * d for d in dds) / len(dds)
    return math.sqrt(mean_sq)


def capture_ratio(returns: list[float], benchmark: list[float], up: bool = True) -> float | None:
    """Up/down capture: average of (algo / benchmark) moves in up (or down) periods.

    Up capture = geometric mean of (1+r_algo)/(1+r_bench) over periods the
    benchmark rose; down capture over periods it fell. A value > 1.0 means the
    algo captured more of that direction than the benchmark. None when fewer
    than 2 aligned periods exist in that direction, or benchmark is flat.
    """
    a = _clean(returns)
    b = _clean(benchmark)
    n = min(len(a), len(b))
    if n < 2:
        return None
    ratios: list[float] = []
    for i in range(n):
        r_algo = a[i]
        r_bench = b[i]
        if r_bench is None or r_algo is None:
            continue
        is_up = r_bench > 0
        if is_up != up:
            continue
        try:
            ratios.append((1.0 + r_algo) / (1.0 + r_bench))
        except ZeroDivisionError:
            continue
    if not ratios:
        return None
    prod = 1.0
    for r in ratios:
        prod *= r
    return prod ** (1.0 / len(ratios)) - 1.0


def tail_ratio(returns: list[float]) -> float | None:
    """Tail ratio = average winning return / |average losing return|.

    A summary of payoff asymmetry (the Losses/Hits magnitude split Nautilus
    reports as winner_avg/loser_avg). None when there are no winners or no
    losers (>0 no positive mass guard).
    """
    vals = _clean(returns)
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v < 0]
    if not wins or not losses:
        return None
    avg_win = sum(wins) / len(wins)
    avg_loss = abs(sum(losses) / len(losses))
    if avg_loss <= 0:
        return None
    return avg_win / avg_loss


def expectancy_stats(wins: list[float], losses: list[float]) -> dict | None:
    """Trade-outcome summary: win rate, profit factor, expectancy, tail ratio.

    All sourced from the caller's win/loss per-trade lists (not the return
    series), the shape the pre-market paper ledger already records. Returns a
    dict of floats, or None when both lists are empty.
    """
    w = [float(x) for x in wins if x is not None]
    losses_f = [float(x) for x in losses if x is not None]
    if not w and not losses_f:
        return None
    n = len(w) + len(losses_f)
    win_rate = len(w) / n if n else 0.0
    gw = sum(w) if w else 0.0
    gl = abs(sum(losses_f)) if losses_f else 0.0
    profit_factor = (gw / gl) if gl > 0 else (float("inf") if gw > 0 else 0.0)
    avg_win = (sum(w) / len(w)) if w else 0.0
    avg_loss = (abs(sum(losses_f)) / len(losses_f)) if losses_f else 0.0
    tail = (avg_win / avg_loss) if (w and losses_f and avg_loss > 0) else None
    # Expectancy E = P(win)*avg_win - P(loss)*avg_loss (matches value_dip.expectancy).
    expectancy_v = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss)
    return {
        "n_trades": n,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy_v,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "tail_ratio": tail,
    }


def turnover(new_weights: dict, prev_weights: dict | None = None) -> float | None:
    """One-period portfolio turnover: ``1/2 * sum_i |w_i,t - w_i,t-1|``.

    Cookbook common-framework turnover. With ``prev_weights`` None the
    previous period is assumed zero (fresh book), so turnover is simply
    ``1/2 * gross``. None for an empty target book.
    """
    if not new_weights:
        return None
    names = set(new_weights) | set(prev_weights or {})
    acc = 0.0
    for n in names:
        t = new_weights.get(n, 0.0)
        p = (prev_weights or {}).get(n, 0.0)
        try:
            tf = float(t)
            pf = float(p)
        except (TypeError, ValueError):
            continue
        if math.isfinite(tf) and math.isfinite(pf):
            acc += abs(tf - pf)
    return 0.5 * acc


def turnover_cost(
    new_weights: dict, prev_weights: dict, cost_by_name: dict | None = None,
    base_cost: float = 0.001,
) -> float | None:
    """Cookbook cost approximation: ``sum_i |w_i,t - w_i,t-1| * c_i``.

    ``cost_by_name`` is a per-name one-way cost fraction (spread + commission
    + slippage); names without an entry use ``base_cost``. None when the
    target book is empty.
    """
    if not new_weights:
        return None
    names = set(new_weights) | set(prev_weights)
    acc = 0.0
    for n in names:
        t = new_weights.get(n, 0.0)
        p = prev_weights.get(n, 0.0)
        try:
            tf = float(t)
            pf = float(p)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(tf) or not math.isfinite(pf):
            continue
        c = cost_by_name.get(n, base_cost) if cost_by_name else base_cost
        acc += abs(tf - pf) * float(c)
    return acc


def gross_exposure(weights: dict) -> float | None:
    """Gross exposure ``sum_i |w_i|`` (leverage); None for an empty book."""
    if not weights:
        return None
    acc = 0.0
    for v in weights.values():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            acc += abs(f)
    return acc


def net_exposure(weights: dict) -> float | None:
    """Net exposure ``sum_i w_i`` (dollar neutrality check); None for empty."""
    if not weights:
        return None
    acc = 0.0
    for v in weights.values():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            acc += f
    return acc


def rolling_sharpe(returns: list, window: int = 252,
                   risk_free: float = 0.0, periods_per_year: float = 252.0) -> list:
    """Rolling-window annualized Sharpe (cookbook reporting checklist).

    One value per completed window, oldest first; the cookbook's
    rolling-12m-sharpe style trajectory for trend-stability checks. Empty
    when fewer than ``window`` observations.
    """
    vals = _clean(returns)
    out: list[float | None] = []
    for end in range(window, len(vals) + 1):
        out.append(sharpe(vals[end - window:end], risk_free, periods_per_year))
    return out


def regime_split_performance(
    returns: list,
    vol_percentile: list | None = None,
    trend: list | None = None,
    high_vol_at: float = 0.7,
    risk_free: float = 0.0,
) -> dict:
    """Performance by regime (cookbook reporting checklist).

    Splits the return series into low/high-volatility (``vol_percentile``
    series aligned to ``returns``) and bull/bear trend (``trend`` sign, or
    ``None`` = skipped) buckets and reports n / CAGR / Sharpe / max-drawdown
    per bucket. Pure, no fabrication: a missing regime input just skips that
    split.
    """
    vals = _clean(returns)
    out: dict = {}
    if len(vals) < 2:
        return out
    if vol_percentile:
        vols = [v for v in vol_percentile if v is not None]
        if len(vols) >= 2:
            lobes = {"low_vol": [], "high_vol": []}
            for r, v in zip(vals, vol_percentile, strict=False):
                if v is None:
                    continue
                lobes["high_vol" if float(v) >= high_vol_at else "low_vol"].append(r)
            for k, series in lobes.items():
                out[k] = _perf_block(series, risk_free)
    if trend:
        tvals = [t for t in trend if t is not None]
        if len(tvals) >= 2:
            lobes = {"bull": [], "bear": []}
            for r, t in zip(vals, trend, strict=False):
                if t is None:
                    continue
                lobes["bull" if float(t) >= 0 else "bear"].append(r)
            for k, series in lobes.items():
                out[k] = _perf_block(series, risk_free)
    return out


def _perf_block(returns: list, risk_free: float) -> dict:
    eq = equity_curve(returns)
    return {
        "n": len(returns),
        "cagr": round(cagr(returns), 6),
        "sharpe": round(sharpe(returns, risk_free), 4),
        "max_drawdown": round(max_drawdown(eq), 6),
    }


def implementation_shortfall(
    decision_price: float | None,
    arrival_price: float | None,
    fill_price: float | None,
    quantity: float | None = None,
    final_price: float | None = None,
    opportunity_days: float = 0.0,
) -> dict | None:
    """Implementation shortfall (TCA) on the paper ledger.

    ``IS = (fill - decision) - (final - decision) * outstanding/expected``
    simplified for a fully-filled order:
       explicit   = (fill - arrival) * qty         (slippage vs arrival)
       market     = (arrival - decision) * qty     (delay/momentum to arrival)
       opportunity = (final - decision) * qty * opportunity_frac
       IS$/notional = (explicit + market + opportunity) / (decision * qty)
    All prices must be > 0; ``quantity`` defaults to 1 (per-share IS).
    Returns ``{"explicit", "market_impact", "opportunity", "implementation_shortfall_bp",
    "notional", "n"}`` or None on missing inputs. Positive IS = cost/worse fill.
    """
    try:
        d = float(decision_price)
        a = float(arrival_price)
        fh = float(fill_price)
    except (TypeError, ValueError):
        return None
    if d <= 0 or a <= 0 or fh <= 0:
        return None
    qty = 1.0 if quantity is None else float(quantity)
    if qty <= 0:
        return None
    explicit = (fh - a) * qty
    market = (a - d) * qty
    opp = 0.0
    if final_price is not None:
        raw_final = float(final_price)
        if raw_final > 0:
            opp = (raw_final - d) * qty * max(0.0, float(opportunity_days))
    total = explicit + market + opp
    notional = d * qty
    return {
        "explicit": round(explicit, 4),
        "market_impact": round(market, 4),
        "opportunity": round(opp, 4),
        "implementation_shortfall_bp": round(total / notional * 1e4, 2),
        "notional": round(notional, 4),
    }


__all__ = [
    "net_returns", "total_return", "cagr", "volatility", "sharpe",
    "deflated_sharpe", "max_drawdown", "equity_curve", "walk_forward_splits",
    "pbo_flag",
    "skewness", "kurtosis", "downside_deviation", "sortino",
    "tracking_error", "information_ratio", "beta", "alpha", "treynor",
    "rolling_beta", "probabilistic_sharpe", "underwater_drawdowns",
    "calmar_ratio", "ulcer_index", "capture_ratio", "tail_ratio",
    "expectancy_stats", "implementation_shortfall",
    "turnover", "turnover_cost", "gross_exposure", "net_exposure",
    "rolling_sharpe", "regime_split_performance",
]
