"""Decision-level data quality + cross-vendor disagreement + PIT invariant
(W3-1, W3-2, W3-4).

- ``aggregate_quality`` — weights per-input quality scores (0-100) into an
  overall decision score + a confidence tier (full/normal/reduced/none) that
  mirrors the remediation plan's table (91-100 full, 80-90 normal, 65-79
  reduced, <65 no strong recommendation). Always honest: an unmeasured input
  is excluded from the weight (never counted as 0).
- ``disagreement_flag`` — given several measured values of the SAME metric
  across vendors (e.g. EPS), report the cross-vendor spread % and flag when
  it exceeds a threshold: DATA CONFLICT rather than silently picking a vendor.
- ``fundamentals_pit_ok`` — W3-4: a fundamental read is only usable in a
  decision whose effective date is >= the fundamental's period/as-of date;
  otherwise fail-closed (refuse the leak of a future restated/dated value).
- ``panel_statistic`` — H10: a panel statistic computed over a window is
  refused (``unavailable``) when that window is padded by positions before the
  symbol's first valid observation. ``coverage_window`` reads the window; this
  is where the refusal is applied, and the dense-frame result is unchanged.

All pure + deterministic; advisory only (reports a score/flag, never gates a
hard rule by itself).
"""

from __future__ import annotations

from tradingagents.strategies.coverage_window import coverage_window

# Per-input quality weight (sums to 100 over the standard set). Missing
# inputs are excluded and the remaining weights renormalized.
_INPUT_WEIGHT = {
    "price": 22.0,
    "volume": 15.0,
    "fundamentals": 22.0,
    "news": 14.0,
    "options": 12.0,
    "macro": 15.0,
}

_QUALITY_TIERS = [
    (91.0, "full"),
    (80.0, "normal"),
    (65.0, "reduced"),
]


def aggregate_quality(input_scores: dict) -> dict:
    """Weighted overall data-quality score (0-100) + confidence tier.

    ``input_scores``: {input_name: 0-100} (e.g. price=95, fundamentals=70).
    Unmeasured inputs are dropped and weights renormalized over the present
    set (honest: absence is not a 0).
    Returns {score, tier, inputs, weight_used}.
    """
    weights = dict(_INPUT_WEIGHT)
    drop = [k for k in weights if k not in (input_scores or {})]
    for k in drop:
        weights.pop(k, None)
    present = [k for k in (input_scores or {}) if k in _INPUT_WEIGHT]
    if not present or not weights:
        return {"score": None, "tier": "unknown", "inputs": {}, "weight_used": 0.0}
    total_w = sum(weights.values())
    score = sum(
        float(input_scores[k]) * weights[k] / total_w for k in present
    ) if total_w > 0 else None
    tier = "unknown"
    for thr, label in _QUALITY_TIERS:
        if score is not None and score >= thr:
            tier = label
            break
    if score is not None and score < 65.0:
        tier = "none"
    return {
        "score": round(score, 1) if score is not None else None,
        "tier": tier,
        "inputs": {k: float(input_scores[k]) for k in present},
        "weight_used": total_w,
    }


def disagreement_flag(values: list, threshold_pct: float = 5.0) -> dict:
    """Cross-vendor spread on one metric (W3-2).

    ``values``: measured values of the same metric across vendors. Returns
    {consistent, spread_pct, min, max, count}. A spread beyond ``threshold_pct``
    (relative to the mean) flags DATA CONFLICT instead of silently trusting
    one vendor. Nones / <2 values -> no claim (consistent, spread None).
    """
    vals = [float(v) for v in (values or []) if v is not None]
    if len(vals) < 2:
        return {"consistent": True, "spread_pct": None,
                "min": min(vals) if vals else None,
                "max": max(vals) if vals else None, "count": len(vals)}
    mean = sum(vals) / len(vals)
    spread = (max(vals) - min(vals)) / mean * 100.0 if mean else 0.0
    return {
        "consistent": spread <= threshold_pct,
        "spread_pct": round(spread, 2),
        "min": min(vals), "max": max(vals), "count": len(vals),
    }


def fundamentals_pit_ok(period_date: str | None, effective_date: str | None) -> bool:
    """W3-4: is a fundamental read with as-of/period ``period_date`` usable at
    ``effective_date``? True only when period <= effective (not future).
    Any unparseable/missing side -> False (fail-closed: don't leak a future
    value into an earlier decision)."""
    if not period_date or not effective_date:
        return False
    try:
        return str(period_date) <= str(effective_date)
    except Exception:  # noqa: BLE001 - malformed -> fail closed
        return False


def _valid_values(series) -> list[float]:
    """Every finite (non-missing, non-NaN) observation in ``series`` as float."""
    if series is None:
        return []
    values = series.tolist() if hasattr(series, "tolist") else list(series)
    out: list[float] = []
    for value in values:
        if value is None:
            continue
        try:
            f = float(value)
        except (TypeError, ValueError):
            continue
        if f == f:  # not NaN
            out.append(f)
    return out


def _coverage_gate() -> bool:
    """Is the H10 coverage-window refusal switched on? (``enable_coverage_window``)

    Off by default, so a gate-off caller computes the statistic exactly as it
    did before the window existed. A config read must never break the read it
    guards: an unreadable config leaves the gate off.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_coverage_window", False))


def panel_statistic(series, *, alignment: str | None = None) -> dict:
    """H10: a panel statistic guarded by its coverage window.

    ``series`` is the already-loaded, calendar-aligned panel for one symbol. Its
    window is read first by :func:`coverage_window` (a reader of the frame, never
    a second data-quality authority). When that window is **padded** - there are
    positions before the first valid observation - the statistic is reported
    ``unavailable`` rather than computed, because a mean over a padded window
    averages histories that did not trade together.

    Returns ``{statistic, n, window, unavailable}``. On the dense window the
    statistic is the plain mean of the valid observations, computed the same way
    the unwindowed path would, so the dense result is unchanged. With the gate
    off the window is not read at all: the statistic is that same plain mean and
    ``window`` is ``None``, which is what a caller did before H10 existed.
    """
    if not _coverage_gate():
        values = _valid_values(series)
        return {
            "statistic": (sum(values) / len(values)) if values else None,
            "n": len(values),
            "window": None,
            "unavailable": None,
        }
    window = coverage_window(series, alignment=alignment)
    if window["padded_days"] > 0:
        return {
            "statistic": None,
            "n": window["n_bars"],
            "window": window,
            "unavailable": (
                f"panel statistic refused: {window['padded_days']} padded "
                f"position(s) before the first valid observation "
                f"({window['first_valid']} first_valid, alignment "
                f"{window['alignment']}); a statistic over a padded window "
                "averages histories that did not trade together"
            ),
        }
    if window["unavailable"] is not None:
        return {
            "statistic": None,
            "n": 0,
            "window": window,
            "unavailable": f"panel statistic unavailable: {window['unavailable']}",
        }
    values = _valid_values(series)
    if not values:
        return {
            "statistic": None,
            "n": 0,
            "window": window,
            "unavailable": "panel statistic unavailable: no valid observation",
        }
    return {
        "statistic": sum(values) / len(values),
        "n": len(values),
        "window": window,
        "unavailable": None,
    }


__all__ = ["aggregate_quality", "disagreement_flag", "fundamentals_pit_ok",
           "panel_statistic", "_INPUT_WEIGHT", "_QUALITY_TIERS"]
