"""Report disclosure + invalidation conditions (DSA research §3.7, pillars 12-14).

Pure helpers the report renderers consume:

- ``signal_attribution`` — computed driver weights (technical / news /
  fundamental / market) that sum to 100 when all four are provided, plus the
  strongest bull/bear computed signal names. NEVER narrated — a caller passes
  the computed reads; this just normalizes + proves the sum (no fabrication).
- ``consensus_readout`` — supporting/opposing lists (from the debate + skill
  overlays) rendered as advisory rows.
- ``watch_conditions`` / ``next_check_time`` — the PM card's "why HOLD / when
  to re-check" rows (feeds the fast-path T1/T2 cadence).
- ``invalidation_conditions`` — the decision-artifact rule: every decision
  carries >= 1 invalidation (stop-loss breach, take-profit review,
  data-staleness thresholds, else ``manual:thesis_reassessment``).
- ``disclosure_footers`` — which data sources contributed vs empty + models,
  from the VendorResult honesty fields (phase B).

All pure + deterministic; advisory only (never gates).
"""

from __future__ import annotations


def signal_attribution(technical: float | None = None, news: float | None = None,
                       fundamental: float | None = None, market: float | None = None,
                       strongest_bullish: str = "", strongest_bearish: str = "") -> dict:
    """Computed driver weights (sum 100 when all four given); else normalized
    over the provided set with an explicit ``missing`` note (no-fabrication)."""
    weights = {
        "technical_indicators": technical,
        "news_sentiment": news,
        "fundamentals": fundamental,
        "market_conditions": market,
    }
    provided = {k: float(v) for k, v in weights.items() if v is not None}
    if not provided:
        return {"weights": {}, "sum": 0, "missing": list(weights)}
    total = sum(provided.values())
    if total <= 0:
        return {"weights": dict.fromkeys(provided, None), "sum": 0,
                "missing": [k for k in weights if k not in provided]}
    normalized = {k: round(v / total * 100.0, 1) for k, v in provided.items()}
    return {
        "weights": normalized,
        "sum": round(sum(normalized.values()), 1),
        "missing": [k for k in weights if k not in provided],
        "strongest_bullish": strongest_bullish or None,
        "strongest_bearish": strongest_bearish or None,
    }


def consensus_readout(supporting: list[str], opposing: list[str]) -> dict:
    """Supporting/opposing per-side readout (debate + skill overlays)."""
    return {
        "supporting": [str(s) for s in (supporting or [])],
        "opposing": [str(o) for o in (opposing or [])],
        "disagreement": bool(opposing),
    }


def watch_conditions(reasons: list[str], next_check: str | None) -> dict:
    """The PM card's 'why HOLD / when to re-check' rows (fast-path T1/T2)."""
    return {
        "watch_conditions": [str(r) for r in (reasons or [])],
        "next_check_time": next_check,
    }


def invalidation_conditions(stop_loss: float | None = None, take_profit: float | None = None,
                            data_quality: str | None = None, extra: list[str] | None = None) -> list[str]:
    """>= 1 invalidation per decision (DSA ResearchArtifact rule).

    stop-loss breach -> "price_stop_loss" (with the level); take-profit
    review -> "price_take_profit_status"; degraded data quality ->
    "data_quality"; else ``manual:thesis_reassessment``. Always non-empty.
    """
    out: list[str] = []
    if stop_loss is not None:
        out.append(f"price_stop_loss: breach below {float(stop_loss):g}")
    if take_profit is not None:
        out.append(f"price_take_profit_status: re-review at/above {float(take_profit):g}")
    if data_quality and data_quality != "fresh":
        out.append(f"data_quality: {data_quality} - thesis inputs degraded")
    out.extend(str(e) for e in (extra or []) if e)
    if not out:
        out.append("manual:thesis_reassessment")
    return out


def disclosure_footers(sources_used: list[str], sources_empty: list[str],
                       models_used: list[str] | None = None,
                       calibers: dict | None = None) -> dict:
    """Report honesty footers: which sources contributed vs empty, which model,
    and (when passed) each source's served price caliber (Vibe-Trading
    calibration honesty; None values render as 'unknown', never assumed)."""
    return {
        "sources_used": list(sources_used),
        "sources_empty": list(sources_empty),
        "models_used": list(models_used or []),
        "price_calibers": {str(k): v for k, v in (calibers or {}).items()},
    }


__all__ = [
    "signal_attribution",
    "consensus_readout",
    "watch_conditions",
    "invalidation_conditions",
    "disclosure_footers",
]
