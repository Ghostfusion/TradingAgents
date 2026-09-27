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


def _legacy_vol_bucket(logrets: list) -> float | None:
    """The pre-REG-1 3-valued ``vol_pct`` proxy, kept only to record a label move.

    ``vol_pct`` was one of {0.1, 0.5, 0.9} from ``vol_now`` (21d rms) against
    ``vol_all`` (trailing 252d rms), with ``vol_all`` forced to 0.0 below 252
    bars - so every 60-251-bar history read 0.5 and the label could not move on
    volatility (RegimeScore.md §3 defect 2 / REG-1). Nothing consumes this value
    except the overlay's ``basis`` string, which names the label the legacy read
    would have produced when it differs from the measured one.
    """
    if len(logrets) < 10:
        return None
    recent = 0.0
    for r in logrets[-21:]:
        recent += r * r
    vol_now = (recent / len(logrets[-21:])) ** 0.5
    recent2 = 0.0
    for r in logrets[-252:]:
        recent2 += r * r
    vol_all = (recent2 / len(logrets[-252:])) ** 0.5 if len(logrets) >= 252 else 0.0
    if vol_now and vol_all and vol_now > 1.5 * vol_all:
        return 0.9
    if vol_all > 0 and vol_now < 0.5 * vol_all:
        return 0.1
    return 0.5


def build_strategy_overlays(config: Mapping, closes: list) -> dict | None:
    """Compute regime + scale + momentum context from closing prices.

    The regime label's volatility leg is a **measured** realized-vol percentile
    (`regime.vol_percentile` over the tape's own OVERLAPPING 21-bar windows),
    not the 3-valued proxy that pinned every 60-251-bar history at 0.5
    (RegimeScore.md §3 defect 2 / REG-1). When ``volatility_estimator`` is
    ``ewma``/``garch`` its annualized vol is ranked on the same scale
    (`regime.vol_percentile_of`) and enters the label too, instead of moving
    only ``position_scale`` (defect 4 / REG-2).

    Returns ``None`` when overlays are disabled or data is insufficient, so the
    graph treats it as a no-op. Otherwise ``{"regime", "position_scale",
    "momentum60", "high_distance", "vol_pct", "basis", "context"}``: ``vol_pct``
    is the percentile the label actually used (``None`` when the tape carries
    too few windows), and ``basis`` prints the window count, which read supplied
    the rank, and - when they differ - the label the legacy 3-bucket read would
    have produced.
    """
    if not config.get("enable_strategy_overlays"):
        return None
    if not closes or len(closes) < 60:
        return None
    from .factors import high_distance, momentum
    from .regime import (
        choppiness,
        regime_label,
        trend_strength,
        vol_percentile,
        vol_percentile_of,
    )
    from .size import volatility_target_scale

    closes_f = [float(c) for c in closes]
    logrets = []
    for i in range(1, len(closes_f)):
        if closes_f[i - 1] > 0 and closes_f[i] > 0:
            import math

            logrets.append(math.log(closes_f[i] / closes_f[i - 1]))
    # Measured realized-vol percentile over the tape's own overlapping windows:
    # `vol_percentile` ranks the latest window against every window the caller
    # supplies, so the overlap is what makes the rank granular (the old proxy
    # had three values and needed 252 bars before it moved at all).
    vol_window = 21
    windows = [
        closes_f[end - vol_window:end] for end in range(vol_window, len(closes_f) + 1)
    ]
    vol_pct = vol_percentile(windows, current_window=vol_window)
    trend = trend_strength(closes_f, sma_window=min(200, len(closes_f) // 2))
    # Measured, not a literal: this call used to pass a hardcoded 0.4 against
    # regime_label's 0.30 default on a 0-1 scale, so the choppiness branch was
    # unreachable and the label was `neutral` for every mid-volatility tape
    # regardless of trend. `choppiness` now returns 0-100 for both its OHLC and
    # close-only branches, and this path is close-only.
    chop = choppiness(closes_f, window=14)
    # `volatility_estimator` switch (default close): ewma / garch use only the
    # closing series (parkinson / garman_klass need OHLC -> tool-only).
    vol_override = None
    estimator = config.get("volatility_estimator", "close")
    try:
        if estimator == "ewma" and len(logrets) >= 20:
            from .volatility_models import ewma_vol

            vol_override = ewma_vol(logrets)
        elif estimator == "garch" and len(logrets) >= 60:
            from .volatility_models import garch11_fit

            fit = garch11_fit(logrets)
            vol_override = (fit or {}).get("long_run_vol")
    except Exception:  # noqa: BLE001 - a bad estimator degrades to close
        vol_override = None
    # REG-2: the estimator's annualized vol is on the same scale as the window
    # vols, so it enters the LABEL through the same measured percentile (falling
    # back to the realized percentile when the estimator cannot measure).
    label_pct = vol_pct
    estimator_pct = None
    if vol_override is not None:
        estimator_pct = vol_percentile_of(
            vol_override, windows, current_window=vol_window
        )
        if estimator_pct is not None:
            label_pct = estimator_pct
    label = regime_label(label_pct, trend, chop)
    scale = volatility_target_scale(
        logrets,
        target_vol=config.get("target_vol", 0.15),
        vol_override=vol_override,
    )
    scale = 1.0 if scale <= 0 else round(min(scale, 1.5), 2)
    mom = momentum(closes_f, lookback=60, skip=0)
    dist = high_distance(closes_f, window=min(252, len(closes_f)))
    notes = []
    if mom is not None:
        notes.append(f"mom60={mom:+.1%}")
    if dist is not None:
        notes.append(f"52w_dist={dist:+.1%}")
    basis = (
        f"vol_pct={label_pct if label_pct is None else round(label_pct, 4)} from "
        + (
            f"the {estimator} estimator ranked against"
            if estimator_pct is not None
            else "the latest window ranked against"
        )
        + f" {len(windows)} overlapping {vol_window}-bar window(s) "
        + "(strictly-below rank, floor 0)"
    )
    if label_pct is None:
        basis += "; too few windows to rank, so the volatility leg is not asserted"
    legacy_pct = _legacy_vol_bucket(logrets)
    if legacy_pct is not None:
        legacy_label = regime_label(legacy_pct, trend, chop)
        basis += f"; the legacy 3-bucket read {legacy_pct} would label {legacy_label}"
        if legacy_label != label:
            basis += f", so the measured percentile moved the label to {label}"
    return {
        "regime": label,
        "position_scale": scale,
        "momentum60": round(mom, 4) if mom is not None else None,
        "high_distance": round(dist, 4) if dist is not None else None,
        "vol_pct": round(label_pct, 4) if label_pct is not None else None,
        "basis": basis,
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

    ``sentiment_ctx`` = ``{"self_lead_lag": float|None, "innovation": float|None,
    "sma_7d": float|None, "source": str}`` measured at run time
    (``trading_graph._sentiment_factor_read``). ``self_lead_lag`` is the name's
    own sentiment↔own-forward-return lead/lag — a single-name self-correlation,
    deliberately not named ``rank_ic`` (no cross-sectional IC is computed here).
    The ``position_scale`` only moves when that measured direction clears
    ``min_ic``; otherwise the fold is a neutral 1.0 (never blocks — matches the
    catalyst's neutral default). The read is attached to the overlay for audit,
    with the source labeled.
    """
    updated = dict(overlay or {})
    if not sentiment_ctx:
        updated.setdefault("context", "")
        return updated
    from .sentiment_research import sentiment_factor_scale

    scale = sentiment_factor_scale(
        sentiment_ctx.get("self_lead_lag"),
        sentiment_ctx.get("innovation"),
        min_ic=min_ic,
        max_scale=max_scale,
        min_scale=min_scale,
    )
    base = float(updated.get("position_scale", 1.0))
    updated["position_scale"] = round(base * scale, 3)
    updated["news_sentiment"] = {
        "scale": scale,
        "self_lead_lag": sentiment_ctx.get("self_lead_lag"),
        "innovation": sentiment_ctx.get("innovation"),
        "sma_7d": sentiment_ctx.get("sma_7d"),
        "source": sentiment_ctx.get("source", ""),
    }
    note = (
        f"news-sentiment scale {scale}x "
        f"(self_lead_lag={sentiment_ctx.get('self_lead_lag')}, "
        f"source {sentiment_ctx.get('source', '')})"
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
