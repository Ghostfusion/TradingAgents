"""Wiring layer: pure, config-guarded overlays for the graph.

Everything here is deterministic and unit-testable offline; the graph calls
these under try/except so a failure is a silent no-op (config off by default).

  build_strategy_overlays(config, closes)  -> dict | None (regime label,
      position scale, momentum note, audit text)
  apply_overlay_to_state(state, overlays)  -> state (+ strategy_overlays)
  record_reflection_outcome(..)            -> None (ledger write, guarded)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

logger = logging.getLogger(__name__)


def build_strategy_overlays(config: Mapping, closes: list) -> dict | None:
    """Compute regime + scale + momentum context from closing prices.

    Returns None when overlays are disabled or data is insufficient, so the
    graph treats it as a no-op.
    """
    if not config.get("enable_strategy_overlays"):
        return None
    if not closes or len(closes) < 60:
        return None
    from .factors import high_distance, momentum
    from .regime import regime_label, trend_strength
    from .size import volatility_target_scale

    closes_f = [float(c) for c in closes]
    logrets = []
    for i in range(1, len(closes_f)):
        if closes_f[i - 1] > 0 and closes_f[i] > 0:
            import math

            logrets.append(math.log(closes_f[i] / closes_f[i - 1]))
    vol_pct = 0.5
    if len(logrets) >= 10:
        recent = 0.0
        for r in logrets[-21:]:
            recent += r * r
        vol_now = (recent / len(logrets[-21:])) ** 0.5
        recent2 = 0.0
        for r in logrets[-252:]:
            recent2 += r * r
        vol_all = (recent2 / len(logrets[-252:])) ** 0.5 if len(logrets) >= 252 else 0.0
        vol_pct = (
            0.9
            if (vol_now and vol_all and vol_now > 1.5 * vol_all)
            else (0.1 if vol_all > 0 and vol_now < 0.5 * vol_all else 0.5)
        )
    trend = trend_strength(closes_f, sma_window=min(200, len(closes_f) // 2))
    label = regime_label(vol_pct, trend, 0.4)
    scale = volatility_target_scale(logrets, target_vol=config.get("target_vol", 0.15))
    scale = 1.0 if scale <= 0 else round(min(scale, 1.5), 2)
    mom = momentum(closes_f, lookback=60, skip=0)
    dist = high_distance(closes_f, window=min(252, len(closes_f)))
    notes = []
    if mom is not None:
        notes.append(f"mom60={mom:+.1%}")
    if dist is not None:
        notes.append(f"52w_dist={dist:+.1%}")
    return {
        "regime": label,
        "position_scale": scale,
        "momentum60": round(mom, 4) if mom is not None else None,
        "high_distance": round(dist, 4) if dist is not None else None,
        "context": (f"regime={label}; position_scale={scale}x; " + "; ".join(notes)),
    }


def fold_flow_into_overlay(overlay: dict, flow: dict | None, threshold: float = 0.7) -> dict:
    """Fold order-flow signals into a strategy overlay (L3).

    ``flow`` is the summary dict from ``orderflow.summarize``. The overlay's
    ``position_scale`` is multiplied by ``max(0, 1 - distribution_score)`` and
    the flow context + warning flag are attached, so downstream risk sees it.
    """
    if flow is None:
        return overlay
    dist = float(flow.get("distribution_score", 0.5))
    scale = 1.0 - dist
    base = float(overlay.get("position_scale", 1.0))
    updated = dict(overlay)
    updated["position_scale"] = round(base * max(0.0, min(scale, 1.0)), 3)
    updated["flow"] = {
        "distribution_score": dist,
        "flag": flow.get("flag"),
        "divergence": flow.get("divergence"),
        "warning": dist >= threshold,
    }
    note = flow.get("text", "")
    updated["context"] = overlay.get("context", "") + " | " + note
    return updated


def fold_sentiment_into_overlay(
    overlay: dict,
    sentiment_ctx: dict | None,
    min_ic: float = 0.02,
    max_scale: float = 0.2,
    min_scale: float = 0.5,
) -> dict:
    """Fold the news-sentiment factor into a strategy overlay (opt-in).

    ``sentiment_ctx`` = ``{"rank_ic": float|None, "innovation": float|None,
    "sma_7d": float|None, "source": str}`` measured at run time. The
    ``position_scale`` only moves when the name's measured predictive
    direction clears ``min_ic``; otherwise the fold is a neutral 1.0 (never
    blocks — matches the catalyst's neutral default). The read is attached to
    the overlay for audit, with the source labeled.
    """
    updated = dict(overlay or {})
    if not sentiment_ctx:
        updated.setdefault("context", "")
        return updated
    from .sentiment_research import sentiment_factor_scale

    scale = sentiment_factor_scale(
        sentiment_ctx.get("rank_ic"),
        sentiment_ctx.get("innovation"),
        min_ic=min_ic,
        max_scale=max_scale,
        min_scale=min_scale,
    )
    base = float(updated.get("position_scale", 1.0))
    updated["position_scale"] = round(base * scale, 3)
    updated["news_sentiment"] = {
        "scale": scale,
        "rank_ic": sentiment_ctx.get("rank_ic"),
        "innovation": sentiment_ctx.get("innovation"),
        "sma_7d": sentiment_ctx.get("sma_7d"),
        "source": sentiment_ctx.get("source", ""),
    }
    note = (
        f"news-sentiment scale {scale}x "
        f"(ic={sentiment_ctx.get('rank_ic')}, source {sentiment_ctx.get('source', '')})"
    )
    updated["context"] = (updated.get("context", "") + " | " + note).strip(" |")
    return updated


def apply_overlay_to_state(state: dict, overlay: dict | None) -> dict:
    """Attach overlay to graph state (copy, never mutate caller's object)."""
    if overlay is None:
        return state
    updated = dict(state)
    updated["strategy_overlays"] = overlay
    return updated


def record_reflection_outcome(
    config, ledger_path, analyst: str, ticker: str, trade_date: str, alpha_return: float | None
) -> None:
    """Write a realized outcome to the reflection ledger; guarded + silent."""
    if not config.get("enable_reflection"):
        return
    if alpha_return is None:
        return
    try:
        from .reflection import ReflectionLedger

        store = ReflectionLedger(path=ledger_path)
        store.record_outcome(analyst, ticker, trade_date, float(alpha_return))
    except Exception as exc:  # noqa: BLE001
        logger.warning("reflection ledger skipped: %s", exc)


__all__ = [
    "build_strategy_overlays",
    "fold_flow_into_overlay",
    "fold_sentiment_into_overlay",
    "apply_overlay_to_state",
    "record_reflection_outcome",
]
