"""Phase 1 - market-regime gate.

Deterministic features first: realized volatility (21d percentile vs a
reference window), 200-SMA trend, and a choppiness proxy (close/open vs
high-low proximity). An optional 2-3 state hidden Markov model (hmmlearn)
labels bull/bear/choppy when installed; the deterministic path is always
available and testable offline.

Wire-up: compute features from daily OHLCV in a pre-graph step, stash
`regime` in graph state, and let the risk node scale position size /
stop levels and analysts frame their lens (bull/bear context).
"""

from __future__ import annotations

import math
from statistics import pstdev

#: dimension of feature tuple: (vol_percentile, trend, choppiness)
FREQ_PER_DAY = 252.0


def realized_vol(
    close_prices: list[float], window: int = 21, periods: float = FREQ_PER_DAY
) -> float:
    """Annualized realized volatility over the last `window` daily closes."""
    prices = close_prices[-window:]
    if len(prices) < 3:
        return None
    rets = []
    prev = prices[0]
    for p in prices[1:]:
        if prev:
            rets.append(math.log(max(p, 1e-12) / max(prev, 1e-12)))
        prev = p
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var * periods)


def vol_percentile(history: list[list[float]], current_window: int = 21) -> float:
    """Percentile rank (0-1) of the latest realized vol vs all history windows."""
    wins = []
    for close in history:
        wins.append(make_vol_series_of_closes(close, window=current_window))
    if not wins or len(wins) < 2:
        return 0.5
    recent = wins[-1]
    below = sum(1 for w in wins if w <= recent)
    return below / len(wins)


def make_vol_series_of_closes(closes: list[float], window: int = 21) -> float:
    """Realized vol of the most recent window (helper for percentile)."""
    logrets = []
    prev = closes[0]
    for p in closes[1:]:
        if p and prev:
            logrets.append(math.log(max(p, 1e-9) / max(prev, 1e-9)))
        prev = p
    if len(logrets) < 2:
        return 0.0
    mean = sum(logrets) / len(logrets)
    var = sum((r - mean) ** 2 for r in logrets) / (len(logrets) - 1)
    return math.sqrt(var * FREQ_PER_DAY)


def trend_strength(close: list[float], sma_window: int = 200) -> float:
    """Simple trend proxy in [-1, 1]: (price - SMA(x)) / SMA(x)."""
    if len(close) < sma_window:
        sma = sum(close) / len(close)
    else:
        sma = sum(close[-sma_window:]) / sma_window
    if sma <= 0:
        return 0.0
    return (close[-1] - sma) / sma


def choppiness(close: list[float], window: int = 14) -> float:
    """0-1 proxy for trend vs range: high when price wanders (std of ln closes)."""
    logrets = []
    prev = close[0]
    for p in close[1:]:
        if prev:
            logrets.append(math.log(max(p, 1e-9) / max(prev, 1e-9)))
        prev = p
    sample = logrets[-window:]
    if len(sample) < 3:
        return 0.5
    return float(pstdev(sample) or 0.5)


def regime_label(
    vol_pct: float,
    trend: float,
    chop: float,
    vol_hi: float = 0.75,
    vol_lo: float = 0.25,
    trend_threshold: float = 0.02,
    chop_threshold: float = 0.30,
) -> str:
    """Rule-based regime: high-vol | bull | bear | choppy (fallback neutral).

    Priority: volatility state first (risk gate), then trend, then choppiness.
    """
    if vol_pct >= vol_hi:
        return "high_vol"
    if vol_pct <= vol_lo and abs(trend) >= trend_threshold:
        return "bull" if trend > 0 else "bear"
    if chop <= chop_threshold:
        return "bull" if trend > 0 else "bear"
    return "neutral"


def hmm_regime(close: list[float], n_states: int = 2) -> str:
    """Optional HMM label; falls back to 'unknown' without hmmlearn."""
    try:
        import numpy as np
        from hmmlearn.hmm import GaussianHMM

        rets = np.array(close[1:]) / np.maximum(np.array(close[:-1]), 1e-9) - 1.0
        rets = rets[:, None]
        if len(rets) < 20 or np.ptp(rets) == 0:
            return "unknown"
        model = GaussianHMM(
            n_components=n_states, covariance_type="full", n_iter=50, random_state=7
        )
        model.fit(rets)
        state = model.predict(rets)[-1]
        means = model.means_.reshape(-1)
        # state with higher mean = bullish regime
        return "bull" if means[state] == max(means) else "bear"
    except Exception:
        return "unknown"




def _sma(series: list, n: int) -> float | None:
    if len(series) < n or n <= 0:
        return None
    return sum(float(x) for x in series[-n:]) / n


def regime_gate_read(
    closes: list,
    cfg: dict | None = None,
    catalyst_window: bool = False,
) -> dict:
    """Deterministic tradability regime for MEAN-REVERSION entries (advisory).

    Institutions gate counter-trend fades: allow a dip-buy only when volatility
    is contained, the market is not in a fast downtrend, and no catalyst window
    (earnings/Fed/high-macro) is open. Pure read over the close series + an
    optional catalyst flag:

    * ``vol_pct`` - percentile rank of the latest 21d realized vol vs its own
      trailing history (the volatility-regime-first rule).
    * ``fast_downtrend`` - price >= ``value_dip_regime_downtrend_band`` (default
      8%) below the 200-SMA while the 50-SMA is under the 200-SMA (falling
      knife guard).
    * ``catalyst_window`` - caller-supplied (events/catalyst overlay).
    * ``pass`` - False when high-vol (``value_dip_regime_vol_cap``, default
      0.8) OR fast_downtrend OR catalyst_window. ADVISORY: this function never
      blocks anything; hard-gating is opt-in at the caller via ``require_regime``
      so existing scans keep their behaviour.
    """
    cfg = cfg or {}
    vol_cap = float(cfg.get("value_dip_regime_vol_cap", 0.8))
    band = float(cfg.get("value_dip_regime_downtrend_band", 0.08))
    if not closes or len(closes) < 60:
        return {
            "pass": None, "verdict": "unknown", "vol_pct": None,
            "fast_downtrend": None, "above_sma200": None, "sma50_rising": None,
            "catalyst_window": bool(catalyst_window), "reasons": ["insufficient history"],
        }
    price = float(closes[-1])
    sma200 = _sma(closes, 200)
    sma50 = _sma(closes, 50)
    sma50_prev = _sma(closes[:-5], 50) if len(closes) > 55 else None
    above_200 = sma200 is not None and price >= sma200
    sma50_rising = sma50_prev is not None and sma50 is not None and sma50 >= sma50_prev
    fast_downtrend = bool(
        sma200 is not None
        and sma50 is not None
        and price < sma200 * (1.0 - band)
        and sma50 < sma200
    )
    vols = [realized_vol(closes[: i + 1], window=21) for i in range(20, len(closes))]
    vols = [v for v in vols if v is not None]
    vol_pct = None
    if vols:
        recent = vols[-1]
        hist = vols[:-1] or [recent]
        vol_pct = round(sum(1 for v in hist if v <= recent) / len(hist), 4)
    high_vol = bool(vol_pct is not None and vol_pct > vol_cap)
    blocked = bool(high_vol or fast_downtrend or catalyst_window)
    verdict = (
        "high-vol"
        if high_vol
        else ("fast-downtrend" if fast_downtrend else ("catalyst-window" if catalyst_window else "tradable"))
    )
    reasons = []
    if high_vol:
        reasons.append(f"vol_pct {vol_pct:.2f} > cap {vol_cap:.2f}")
    if fast_downtrend:
        reasons.append(f"price {band:.0%}+ below falling 200-SMA (knife guard)")
    if catalyst_window:
        reasons.append("catalyst window open")
    if not blocked:
        reasons.append("volatility contained + no fast downtrend + no catalyst")
    return {
        "pass": not blocked,
        "verdict": verdict,
        "vol_pct": vol_pct,
        "fast_downtrend": fast_downtrend,
        "above_sma200": above_200,
        "sma50_rising": sma50_rising,
        "catalyst_window": bool(catalyst_window),
        "thresholds": {"vol_cap": vol_cap, "downtrend_band": band},
        "reasons": reasons,
    }


__all__ = [
    "realized_vol",
    "vol_percentile",
    "trend_strength",
    "choppiness",
    "regime_label",
    "hmm_regime",
    "make_vol_series_of_closes",    "regime_gate_read",
]
