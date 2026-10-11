"""Baseline-relative evaluation surface (FinRL 8; ``docs/design_finrl_integration.md`` §6.4).

A raw single curve is not a result. This module measures a strategy arm and every
baseline arm on **one shared window with one stated cost schedule**, and reports
each arm on ten metrics: the six the engine already reports (cumulative return,
CAGR, annualized vol, Sharpe, max drawdown, Calmar) beside the four a
baseline-relative comparison is read on - mean, variance, loss-side CVaR and
``P(return >= threshold)``.

**One producer per metric.** The classic six come from
``evaluate.benchmark_table`` - the engine's existing baseline-row producer, whose
positional benchmark row is reported here under the caller's own name for it -
and the loss-side four come from ``book_risk.cvar`` and ``book_risk.prob_loss``.
Nothing below re-implements a statistic.

**Cost.** ``cost_bps`` is charged to the strategy arm, ``baseline_cost_bps``
(default ``0.0``) to the baselines. The asymmetric default is the
*anti-flattering* direction on purpose: a cost-free baseline makes the comparison
harder for the strategy, so a strategy that still wins net of cost was not
flattered into that win. Charging both sides is one argument away.

**Window and refusals.** The shared window is the common tail of every arm, so a
short arm truncates the read rather than being right-padded; no strategy
observations, an unusable arm, or no baseline at all is a named refusal - never a
zero-filled row that reads as a flat curve, and never a strategy row presented
without the baselines it is relative to.
"""

from __future__ import annotations

import math
from statistics import pvariance

__all__ = ["DEFAULT_CVAR_ALPHA", "benchmark_rows", "benchmark_surface"]

#: The tail level the loss-side CVaR column reports (``book_risk.cvar``'s own default).
DEFAULT_CVAR_ALPHA = 0.05

#: The metrics ``benchmark_surface`` differences against each baseline. One list,
#: so a caller and the renderer cannot disagree about what "the deltas" are.
DELTA_METRICS = (
    "total_return",
    "cagr",
    "ann_vol",
    "sharpe",
    "max_drawdown",
    "calmar",
    "mean",
    "variance",
    "cvar",
    "prob_ge_threshold",
)


def _finite(series) -> list[float]:
    """The finite numeric observations of a series, order preserved.

    Non-numeric and non-finite points are dropped, never coerced to zero.
    """
    out: list[float] = []
    for v in series or []:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def _refusal(reason: str, **extra) -> dict:
    """The one refusal shape: no rows, the reason, and the call's own schedule."""
    out = {
        "window": 0,
        "rows": [],
        "baselines": [],
        "baseline_available": False,
        "unavailable": reason,
    }
    out.update(extra)
    return out


def _row(name: str, rets: list[float], classic: dict, *, cost_bps: float,
         periods_per_year: float, cvar_alpha: float, threshold: float) -> dict:
    """One arm's row: the classic six from ``benchmark_table`` plus the loss-side four.

    ``classic`` is the arm's row as ``evaluate.benchmark_table`` computed it (its
    ``None``s are the producer's own refusals and are passed through untouched).
    """
    from tradingagents.strategies.book_risk import cvar, prob_loss

    n = len(rets)
    mean = sum(rets) / n
    p_loss = prob_loss(rets, threshold)
    return {
        "name": name,
        "n": n,
        "cost_bps": cost_bps,
        "total_return": (classic or {}).get("total_return"),
        "cagr": (classic or {}).get("cagr"),
        "ann_vol": round(_ann_vol(rets, periods_per_year), 6),
        "sharpe": (classic or {}).get("sharpe"),
        "max_drawdown": (classic or {}).get("max_drawdown"),
        "calmar": _calmar(rets, periods_per_year),
        "mean": round(mean, 8),
        "variance": round(float(pvariance(rets)), 10),
        "cvar": cvar(rets, cvar_alpha),
        # P(R >= threshold) is the complement of book_risk.prob_loss's strict
        # inequality, so a tie at the threshold counts as a loss - stated, not fixed
        # silently here (the loss frequency owns that convention).
        "prob_ge_threshold": (1.0 - p_loss) if p_loss is not None else None,
    }


def _ann_vol(rets: list[float], periods_per_year: float) -> float:
    """Annualized sample stdev via ``evaluate.volatility`` (the engine's estimator).

    ``volatility`` is total: it returns ``0.0`` for a series too short to carry a
    stdev, so a row's ``ann_vol`` is always a number on a row that exists.
    """
    from tradingagents.strategies.evaluate import volatility

    return float(volatility(rets, periods_per_year))


def _calmar(rets: list[float], periods_per_year: float) -> float | None:
    """Calmar via ``evaluate.calmar_ratio`` (CAGR / max-drawdown magnitude)."""
    from tradingagents.strategies.evaluate import calmar_ratio

    value = calmar_ratio(rets, periods_per_year)
    return round(float(value), 4) if value is not None else None


def benchmark_rows(
    strategy_returns,
    benchmarks: dict | None = None,
    *,
    cost_bps: float = 0.0,
    baseline_cost_bps: float = 0.0,
    periods_per_year: float = 252.0,
    cvar_alpha: float = DEFAULT_CVAR_ALPHA,
    threshold: float = 0.0,
) -> dict:
    """One metric row per arm over the arms' common tail window.

    ``benchmarks`` is ``{name: return series}``. The strategy arm is always
    reported first, then the baselines in the order given. Cost is applied to the
    strategy at ``cost_bps`` and to each baseline at ``baseline_cost_bps`` before
    anything is measured, so every row is a *net* row under one stated schedule
    (``evaluate.net_returns`` - the same one-way convention the rest of the engine
    uses).

    Returns ``{"window", "rows", "baselines", "baseline_available", "cost_bps",
    "baseline_cost_bps", "cvar_alpha", "threshold", "unavailable", "basis"}``.
    ``unavailable`` names the refusal and ``rows`` is empty when nothing could be
    measured; it stays ``None`` on a successful read.
    """
    try:
        cost_bps = float(cost_bps)
        baseline_cost_bps = float(baseline_cost_bps)
        periods_per_year = float(periods_per_year)
        cvar_alpha = float(cvar_alpha)
        threshold = float(threshold)
    except (TypeError, ValueError):
        return _refusal("a non-numeric cost/period/alpha argument")

    arms = {"strategy": _finite(strategy_returns)}
    for name, series in (benchmarks or {}).items():
        arms[str(name)] = _finite(series)
    baselines = [k for k in arms if k != "strategy"]
    if len(arms["strategy"]) < 2:
        return _refusal(
            "the strategy arm carries fewer than two finite observations",
            baselines=baselines,
        )
    for name in baselines:
        if len(arms[name]) < 2:
            return _refusal(
                f"baseline {name!r} carries fewer than two finite observations",
                baselines=baselines,
            )

    from tradingagents.strategies.evaluate import benchmark_table, net_returns

    priced: dict[str, list[float]] = {}
    for name, series in arms.items():
        charged = cost_bps if name == "strategy" else baseline_cost_bps
        # net_returns is None-preserving by construction; _finite re-cleans because
        # these series already were (and so the rows stay list[float]).
        priced[name] = _finite(net_returns(series, cost_bps=charged)) if charged else series
    n = min(len(v) for v in priced.values())
    if n < 2:
        return _refusal(
            f"the arms share only {n} observation(s) once cost is applied",
            baselines=baselines,
        )
    window = {name: values[-n:] for name, values in priced.items()}

    # One call to the engine's own row producer: the first baseline rides its
    # positional ``benchmark`` slot (reported below under the caller's name for
    # it), every other baseline rides ``simple``.
    first = baselines[0] if baselines else "strategy"
    table = benchmark_table(
        window["strategy"],
        window[first],
        simple={k: window[k] for k in baselines[1:]} or None,
        periods_per_year=periods_per_year,
    )
    order = ["strategy", *baselines]
    classic = dict(zip(order, table["rows"], strict=False))
    rows = [
        _row(
            name,
            window[name],
            classic.get(name) or {},
            cost_bps=cost_bps if name == "strategy" else baseline_cost_bps,
            periods_per_year=periods_per_year,
            cvar_alpha=cvar_alpha,
            threshold=threshold,
        )
        for name in order
    ]
    basis = (
        f"baseline-relative rows over {n} shared observation(s) "
        f"(FinRL 8, design_finrl_integration §6.4); the classic columns are "
        f"evaluate.benchmark_table's, the loss-side four are book_risk.cvar / "
        f"prob_loss; cost {cost_bps}bps on the strategy arm and "
        f"{baseline_cost_bps}bps on the baselines; cvar_alpha={cvar_alpha}, "
        f"threshold={threshold} (P(return >= threshold) is prob_loss's complement)"
    )
    return {
        "window": n,
        "rows": rows,
        "baselines": baselines,
        "baseline_available": bool(baselines),
        "cost_bps": cost_bps,
        "baseline_cost_bps": baseline_cost_bps,
        "cvar_alpha": cvar_alpha,
        "threshold": threshold,
        "unavailable": None,
        "basis": basis,
    }


def benchmark_surface(
    strategy_returns,
    benchmarks: dict | None = None,
    *,
    delta_metrics: tuple[str, ...] = DELTA_METRICS,
    **kwargs,
) -> dict:
    """The surface: the rows plus each baseline's metric deltas against the strategy.

    A strategy-only call is a **refusal, not a surface**: with no baseline series
    there is nothing to be relative to, so the result carries the strategy row,
    ``baseline_available=False`` and the reason - the point of the design row is
    that a raw single curve is never the deliverable, so the artifact says so
    rather than printing one.

    Deltas are ``strategy - baseline`` per metric (positive = the strategy is
    ahead), reported only where both sides are numeric; a metric either side
    refuses is omitted rather than zeroed.
    """
    rows = benchmark_rows(strategy_returns, benchmarks, **kwargs)
    baselines = list(rows.get("baselines") or [])
    out = dict(rows)
    out["strategy"] = "strategy"
    out["delta_metrics"] = list(delta_metrics)
    if not baselines or rows.get("unavailable"):
        out["delta_vs_baseline"] = {}
        if not baselines:
            out["reason"] = (
                "no baseline series supplied: a raw single curve is not a result "
                "(pass buy&hold / equal-weight / MVO arms to make it relative)"
            )
        else:
            out["reason"] = rows.get("unavailable")
        return out

    by_name = {row["name"]: row for row in rows["rows"]}
    strategy_row = by_name.get("strategy") or {}
    deltas: dict[str, dict] = {}
    for name in baselines:
        base = by_name.get(name) or {}
        per_metric = {}
        for metric in delta_metrics:
            a, b = strategy_row.get(metric), base.get(metric)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                per_metric[metric] = round(float(a) - float(b), 6)
        deltas[name] = per_metric
    out["delta_vs_baseline"] = deltas
    out["reason"] = None
    return out
