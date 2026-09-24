"""K1 - a tail number that carries its quality and its uncertainty (2604.08765).

``book_risk.simple_var`` / ``cvar`` return a number and nothing else. This
module joins that number to the engine's data-quality verdict
(``data_quality.aggregate_quality``), its conformal band
(``conformal.quantile_band`` / ``rolling_band``) and its coverage test
(``book_risk.var_coverage_test``), and enforces the paper's one-directional
rule: input quality and estimation uncertainty may **widen** the band or
**withhold** the number - they may never narrow it. A red quality verdict is
``unavailable``, never a number presented as if it were fit to produce one.

This COMPOSES the existing producers; it re-implements none of them. The
uncertainty score comes from ensemble dispersion (two or more members),
an out-of-distribution distance and a recent breach-drift term. The breach
rate travels with the number, and the coverage test is reported beside it.

Behind ``enable_tail_risk_layer`` (default off): with the gate off the read is
refused, exactly as ``triadic_stress`` refuses, so a gate-off run is unchanged.
Advisory only - never a gate, never a size, never an order.
"""

from __future__ import annotations

import math

from tradingagents.strategies.book_risk import (
    cvar,
    normalize_book_weights,
    portfolio_cvar,
    portfolio_returns,
    simple_var,
    var_coverage_test,
)
from tradingagents.strategies.conformal import quantile_band, rolling_band
from tradingagents.strategies.data_quality import aggregate_quality

__all__ = ["tail_risk"]

#: Below this many usable returns the band's calibration has nothing to say.
MIN_OBS = 40

#: The quality tiers, mirroring ``data_quality``'s 0-100 verdict: green at/above
#: GREEN (the paper's "green"), amber down to AMBER (its "yellow"), and below
#: AMBER the verdict is red and the number is withheld.
GREEN = 80.0
AMBER = 65.0

#: Uncertainty at/above this also marks the read ``widened`` (the band is always
#: widened by uncertainty; the status flag picks up a materially uncertain read).
UNCERTAINTY_WIDEN = 0.5

#: The trailing fraction of the window over which the breach-drift term is read.
BREACH_WINDOW = 0.2

#: The out-of-distribution distance is scaled by this many standard deviations
#: before being clipped to 1 (a 3-sigma point is "far").
OOD_SIGMA = 3.0


def _clean(values) -> list[float]:
    """Finite-float clean of a series (drops None / non-numeric / non-finite)."""
    out: list[float] = []
    for v in values or []:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def _gate_on() -> bool:
    """Is K1's tail-risk layer switched on? (``enable_tail_risk_layer``, default off).

    The key is read by its literal name so the gate registry's read-site scan
    finds it; an unreadable config leaves the gate off - a config read must
    never break the read it guards.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_tail_risk_layer", False))


def _widen_from_quality(q_score: float) -> float:
    """The quality-driven widening fraction (0 at green, >=1 at red).

    Monotone non-increasing in ``q_score``: 0 for a green verdict, ramping to 1
    at the amber floor, then past 1 into the red band. It is added to 1.0 when
    the half-width is scaled, so quality can only ever move the band OUTWARD.
    """
    if q_score >= GREEN:
        return 0.0
    if q_score >= AMBER:
        return (GREEN - float(q_score)) / (GREEN - AMBER)
    return 1.0 + (AMBER - float(q_score)) / AMBER


def _uncertainty(vals: list[float], members, alpha: float,
                 base_var: float) -> dict:
    """The estimation-uncertainty score (ensemble dispersion + OOD + breach drift).

    Each term is in ``[0, 1]``; the score is their mean over the terms that could
    be measured. Ensemble dispersion needs two or more members (``members`` are
    return series) and is reported ``None`` - never 0 - when fewer are supplied,
    because a single member has no dispersion to measure. Nothing here can lower
    the score below the measurable terms' mean in a way that would narrow a band.
    """
    member_vars = [_member_var(m, alpha) for m in (members or [])]
    member_vars = [v for v in member_vars if v is not None]
    dispersion = None
    if len(member_vars) >= 2:
        mu = sum(member_vars) / len(member_vars)
        if abs(mu) > 1e-12:
            sd = math.sqrt(
                sum((v - mu) ** 2 for v in member_vars) / len(member_vars)
            )
            dispersion = min(1.0, sd / abs(mu))
    n = len(vals)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1) if n > 1 else 0.0
    ood = min(1.0, abs(vals[-1] - mean) / math.sqrt(var) / OOD_SIGMA) if var > 0 else None
    k = max(1, int(n * BREACH_WINDOW))
    recent = vals[-k:]
    breaches = sum(1 for r in recent if r < base_var)
    drift = None
    if alpha > 0:
        rate = breaches / len(recent)
        drift = min(1.0, max(0.0, (rate - alpha) / alpha))
    measured = [v for v in (dispersion, ood, drift) if v is not None]
    score = sum(measured) / len(measured) if measured else 0.0
    return {
        "score": round(float(score), 6),
        "dispersion": None if dispersion is None else round(float(dispersion), 6),
        "ood_distance": None if ood is None else round(float(ood), 6),
        "breach_drift": None if drift is None else round(float(drift), 6),
        "members": len(member_vars),
        "basis": (
            "uncertainty = mean of the measurable terms (ensemble dispersion "
            "over >=2 members, out-of-distribution distance of the latest "
            "return, trailing breach drift above the stated tail); a term that "
            "could not be measured is excluded, never counted as 0"
        ),
    }


def _member_var(series, alpha: float) -> float | None:
    """A member's own historical VaR (the dispersion term's unit)."""
    return simple_var(_clean(series), alpha)


def _refusal(reason: str, *, n: int = 0, window: dict | None = None,
             quality: dict | None = None) -> dict:
    """The refusal record: no number, the reason, and the window it was asked on."""
    return {
        "var": None,
        "cvar": None,
        "q_score": (quality or {}).get("score"),
        "uncertainty": None,
        "band": None,
        "status": "unavailable",
        "breach_rate": None,
        "coverage": None,
        "quality": quality,
        "window": window or {"n": n},
        "basis": reason,
    }


def tail_risk(
    returns: list,
    quality: dict | None = None,
    *,
    members: list | None = None,
    weights: dict | None = None,
    alpha: float = 0.05,
    window: int = 250,
    min_n: int = MIN_OBS,
) -> dict:
    """A VaR/CVaR that travels with its quality, uncertainty and coverage (K1).

    ``returns`` is the book's return sample - a flat series, or a
    ``{name: series}`` dict in which case the book is mixed with
    ``book_risk.portfolio_returns`` / ``book_risk.normalize_book_weights`` and
    the CVaR leg is ``book_risk.portfolio_cvar`` (cash-sleeve semantics). The mix
    is reported in ``window["book"]``. ``quality`` is the
    ``data_quality.aggregate_quality`` input dict (``{"price": 95, ...}``), whose
    weighted 0-100 verdict widens the band or refuses the number. ``members``
    (optional) are two or more return series whose VaR dispersion is the
    ensemble-dispersion uncertainty term.

    Returns ``{"var", "cvar", "q_score", "uncertainty", "band", "status",
    "breach_rate", "coverage", "quality", "window", "widen", "basis"}`` with
    ``status in {ok, widened, unavailable}``. The number is ``var``/``cvar`` in
    ``simple_var``'s convention (negative = loss), the band is the conformal
    interval WIDENED (never narrowed) by quality and uncertainty, the breach
    rate and the Kupiec/Christoffersen coverage test are reported beside it, and
    a red quality verdict or a gate-off run is ``unavailable``.
    """
    book_cvar = None
    is_book = isinstance(returns, dict)
    if is_book:
        norm = normalize_book_weights(returns, weights)
        vals = _clean(portfolio_returns(norm, returns)) if norm else []
        book_cvar = portfolio_cvar(returns, weights, alpha) if norm else None
    else:
        vals = _clean(returns)
    n = len(vals)
    if not _gate_on():
        return _refusal(
            "enable_tail_risk_layer is off (default): the read is not produced "
            "on a gate-off run",
            n=n,
        )
    floor = max(MIN_OBS, int(min_n))
    if n < floor:
        return _refusal(
            f"only {n} usable return(s), below the {floor}-observation floor: a "
            "tail band cannot be calibrated on a window this thin (master rule 1 "
            "- missing data is unavailable, never zero)",
            n=n, window={"n": n, "min_n": floor, "alpha": alpha},
        )
    q = aggregate_quality(quality or {})
    q_score = q["score"]
    if q_score is None:
        return _refusal(
            "no quality input was measured, so the number cannot be certified "
            "fit to produce: refused rather than published unlabelled",
            n=n, window={"n": n, "alpha": alpha}, quality=q,
        )
    base_var = simple_var(vals, alpha)
    base_cvar = book_cvar if book_cvar is not None else cvar(vals, alpha)
    if base_var is None or base_cvar is None:
        return _refusal(
            f"no finite historical VaR/CVaR at alpha={alpha}",
            n=n, window={"n": n, "alpha": alpha}, quality=q,
        )
    # Conformal band over an expanding historical VaR (strictly-past inputs), so
    # the interval's width is measured, not assumed.
    burn = max(20, floor // 2)
    preds: list[float] = []
    scores: list[float] = []
    pairs: list[tuple[float, float]] = []
    for t in range(burn, n):
        p = simple_var(vals[:t], alpha)
        if p is None:
            continue
        preds.append(p)
        scores.append(abs(vals[t] - p))
        pairs.append((p, vals[t]))
    band = rolling_band(pairs, window=int(window), alpha=alpha, min_n=floor) if pairs else None
    if band is None:
        band = quantile_band(preds, alpha, scores) if preds else None
    if band is None or "low" not in band or "high" not in band:
        return _refusal(
            "no usable conformal band: the calibration window had too few "
            "usable pairs",
            n=n, window={"n": n, "min_n": floor, "alpha": alpha}, quality=q,
        )
    centre = preds[-1] if preds else base_var
    raw_half = max(0.0, (float(band["high"]) - float(band["low"])) / 2.0)
    unc = _uncertainty(vals, members, alpha, base_var)
    q_widen = _widen_from_quality(float(q_score))
    total_widen = q_widen + float(unc["score"])
    half = raw_half * (1.0 + total_widen)
    extra = max(0.0, half - raw_half)  # >= 0 by construction: only outward
    var = centre - extra
    var_cvar = base_cvar - extra
    red = float(q_score) < AMBER
    if red:
        status = "unavailable"
    elif q_widen > 0.0 or float(unc["score"]) >= UNCERTAINTY_WIDEN:
        status = "widened"
    else:
        status = "ok"
    if red:
        var = None
        var_cvar = None
    coverage = var_coverage_test(vals, alpha=alpha, var_series=preds)
    breach_rate = coverage["kupiec"]["hit_rate"]
    return {
        "var": var,
        "cvar": var_cvar,
        "q_score": q_score,
        "uncertainty": unc,
        "band": {
            "low": centre - half,
            "high": centre + half,
            "width": 2.0 * half,
            "raw_width": 2.0 * raw_half,
            "nominal": band.get("nominal"),
            "realized_coverage": band.get("realized_coverage"),
            "widening": extra,
        },
        "status": status,
        "breach_rate": breach_rate,
        "coverage": coverage,
        "quality": q,
        "window": {"n": n, "burn_in": burn, "conformal_window": int(window),
                   "alpha": alpha, "min_n": floor, "book": is_book},
        "widen": {"quality": round(q_widen, 6), "uncertainty": unc["score"],
                  "total": round(total_widen, 6)},
        "basis": (
            f"tail risk (2604.08765): historical VaR/CVaR at alpha={alpha} over "
            f"{n} return(s), conformal band widened outward by quality "
            f"(q_score={q_score}, tier={q['tier']} -> {q_widen:.3f}) and "
            f"uncertainty ({unc['score']:.3f}); breach rate {breach_rate}; "
            f"coverage verdict {coverage['verdict']}; status {status}; "
            f"RELIABILITY layer, not a calibrated VaR - the producer's own VaR "
            f"still fails the Kupiec test, so the coverage test is reported "
            f"beside the number and never suppressed"
        ),
    }
