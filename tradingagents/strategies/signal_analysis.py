"""IC / quantile signal-analysis surface, generic over ANY score series.

Qlib pillar 4 + 15 port (`contrib/eva/alpha.py` family): rank IC, IC-IR,
quantile long-short decomposition, IC decay half-life, prediction
autocorrelation (is the forecast itself sticky?), and the with/without-cost
excess-return table — the standard Qlib backtest report. Generalizes the
``sentiment_research`` IC machinery to any ``(signal, forward_return)`` pair
(no sentiment coupling), and renders upstream of ``strategy_quality_report``.

No-fabrication: ``None``/``unavailable`` under min-observation or degenerate
input; never a guessed number.
"""

from __future__ import annotations

import math


def _clean_pair(signal: list, forward: list) -> tuple[list[float], list[float]]:
    """Aligned finite pairs; empty when alignment is impossible."""
    out_s: list[float] = []
    out_f: list[float] = []
    for s, f in zip(signal, forward, strict=True):
        try:
            fs = float(s)
            ff = float(f)
        except (TypeError, ValueError):
            continue
        if math.isfinite(fs) and math.isfinite(ff):
            out_s.append(fs)
            out_f.append(ff)
    return out_s, out_f


def _pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) != len(b) or len(a) < 3:
        return None
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    denom = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    if denom <= 1e-12:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True)) / denom


def _ranked(xs: list[float]) -> list[float]:
    """Average-tie ranks normalized to [0, 1] (Spearman input)."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    j = 0
    n = len(xs)
    while j < n:
        j2 = j
        while j2 + 1 < n and xs[order[j2 + 1]] == xs[order[j]]:
            j2 += 1
        avg_rank = (j + j2) / 2.0 + 1.0
        for k in range(j, j2 + 1):
            ranks[order[k]] = (avg_rank - 1.0) / (n - 1) if n > 1 else 1.0
        j = j2 + 1
    return ranks


def rank_ic(signal: list, forward_returns: list, min_obs: int = 10) -> float | None:
    """Cross-sectional rank IC between a score and its forward returns.

    Spearman-style: Pearson on average-tie ranks. ``None`` under min-obs or
    when either side is constant (no fabrication).
    """
    s, f = _clean_pair(signal, forward_returns)
    if len(s) < min_obs:
        return None
    rs, rf = _ranked(s), _ranked(f)
    return _pearson(rs, rf)


def icir(ic_series: list, periods_per_year: float = 252.0) -> float | None:
    """Information ratio of an IC series: mean / std * sqrt(n)."""
    ics = [float(x) for x in ic_series if x is not None]
    if len(ics) < 2:
        return None
    mu = sum(ics) / len(ics)
    sd = math.sqrt(sum((x - mu) ** 2 for x in ics) / (len(ics) - 1))
    if sd <= 1e-12:
        return None
    return mu / sd * math.sqrt(len(ics))


def quantile_long_short(
    signal: list, forward_returns: list, n_buckets: int = 5,
    cost_bps: float = 10.0, min_obs: int = 10,
) -> dict | None:
    """Quantile long-short decomposition of one (signal, forward) cross-section.

    Ranks by signal into ``n_buckets``, averages the forward return per
    bucket, and reports the top-minus-bottom spread net of one-way round-trip
    cost, monotonicity (share of adjacent pairs that are monotone increasing),
    and the ``(r_long - r_short) / 2`` decomposition.
    """
    s, f = _clean_pair(signal, forward_returns)
    if len(s) < min_obs or n_buckets < 2:
        return None
    order = sorted(range(len(s)), key=lambda i: s[i])
    buckets: list[list[float]] = [[] for _ in range(n_buckets)]
    for idx, i in enumerate(order):
        buckets[min(n_buckets - 1, idx * n_buckets // len(order))].append(f[i])
    means = [sum(b) / len(b) if b else None for b in buckets]
    q_lo = means[0]
    q_hi = means[-1]
    costs = 2.0 * float(cost_bps) / 10000.0
    ls_net = (q_hi - q_lo - costs) if q_hi is not None and q_lo is not None else None
    ls_return = ((q_hi - q_lo) / 2.0) if q_hi is not None and q_lo is not None else None
    r_avg = ((q_hi + q_lo) / 2.0) if q_hi is not None and q_lo is not None else None
    mono_pairs = 0
    mono_total = 0
    for j in range(len(means) - 1):
        if means[j] is None or means[j + 1] is None:
            continue
        mono_total += 1
        if means[j + 1] >= means[j] - 1e-12:
            mono_pairs += 1
    return {
        "n": len(s),
        "buckets": [{"q": j + 1, "mean_fwd": (round(m, 6) if m is not None else None),
                     "count": len(buckets[j])} for j, m in enumerate(means)],
        "long_short_net": round(ls_net, 6) if ls_net is not None else None,
        "long_short_return": round(ls_return, 6) if ls_return is not None else None,
        "r_avg": round(r_avg, 6) if r_avg is not None else None,
        "monotonicity": round(mono_pairs / mono_total, 3) if mono_total else None,
        "cost_bps": float(cost_bps),
    }


def long_short_return(r_long: float, r_short: float) -> tuple[float, float]:
    """Qlib's ``(r_long - r_short)/2`` decomposition + the pair average."""
    return ((r_long - r_short) / 2.0, (r_long + r_short) / 2.0)


def long_short_precision(predicted: list, realized: list, quantile: float = 0.8) -> float | None:
    """Of the top ``quantile`` by predicted, the share also in the top
    ``quantile`` by realized outcome (Qlib long-short precision)."""
    p, r = _clean_pair(predicted, realized)
    if len(p) < 5:
        return None
    p_cut = sorted(p)[int(math.ceil((1.0 - quantile) * len(p))) - 1]
    r_cut = sorted(r)[int(math.ceil((1.0 - quantile) * len(r))) - 1]
    pred_top = [pi for pi, ri in zip(p, r, strict=True) if pi >= p_cut]
    hit = [1 for pi, ri in zip(p, r, strict=True) if pi >= p_cut and ri >= r_cut]
    if not pred_top:
        return None
    return len(hit) / len(pred_top)


def pred_autocorr(signal: list, lag: int = 1) -> float | None:
    """Prediction autocorrelation: is the forecast itself sticky?

    Pearson of ``s[t]`` vs ``s[t-lag]`` — the signal-side twin of
    ``return_autocorrelation``. High stickiness + low realized IC = a stale
    signal whose rank barely moves.
    """
    s, _ = _clean_pair(signal, signal)
    if lag <= 0 or len(s) < lag + 3:
        return None
    return _pearson(s[:-lag], s[lag:])


def ic_decay_half_life(ic_by_horizon: list) -> float | None:
    """Half-life (days) of IC decay across horizons.

    ``ic_by_horizon`` = ``[(horizon_days, mean_ic), ...]``. Fits
    ``IC(h) = IC0 * exp(-lambda*h)`` via OLS on ln(IC); half-life =
    ``ln(2)/lambda``. None when the fit is degenerate (lambda <= 0 or IC <= 0).
    """
    pts = [(float(h), float(ic)) for h, ic in ic_by_horizon
           if ic is not None and ic > 0 and h > 0]
    if len(pts) < 2:
        return None
    xs = [h for h, _ in pts]  # IC(h) = IC0*exp(-lambda h) -> ln IC linear in h
    ys = [math.log(ic) for _, ic in pts]
    n = len(pts)
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom <= 1e-12:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / denom
    if slope >= 0:  # no decay -> no half-life
        return None
    return round(math.log(2.0) / (-slope), 1)


def with_without_cost_table(returns: list, cost_bps: float = 10.0) -> dict:
    """Excess-return report with/without cost (Qlib backtest-report table).

    Annualized return, Sharpe, max drawdown for the raw series and the
    net-of-cost series; ``None`` metrics stay honest under short history.
    """
    from tradingagents.strategies.evaluate import (
        cagr,
        equity_curve,
        max_drawdown,
        net_returns,
        sharpe,
    )

    def _row(series: list) -> dict:
        eq = equity_curve(series) if series else []
        return {
            "cagr": round(cagr(series), 4) if series else None,
            "sharpe": round(sharpe(series), 3) if len(series) >= 2 else None,
            "max_drawdown": round(max_drawdown(eq), 4) if eq else None,
        }

    raw = [float(r) for r in returns if r is not None]
    net = net_returns(raw, cost_bps=cost_bps)
    return {
        "without_cost": _row(raw),
        "with_cost": _row([r for r in net if r is not None]),
        "cost_bps": float(cost_bps),
        "n": len(raw),
    }


__all__ = [
    "rank_ic",
    "icir",
    "quantile_long_short",
    "long_short_return",
    "long_short_precision",
    "pred_autocorr",
    "ic_decay_half_life",
    "with_without_cost_table",
]
