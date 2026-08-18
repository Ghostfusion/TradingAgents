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


def realized_vol(close_prices: list[float], window: int = 21,
                 periods: float = FREQ_PER_DAY) -> float:
    """Annualized realized volatility over the last `window` daily closes."""
    prices = close_prices[-window:]
    if len(prices) < 3:
        return 0.0
    rets = []
    prev = prices[0]
    for p in prices[1:]:
        if prev:
            rets.append(math.log(max(p, 1e-12) / max(prev, 1e-12)))
        prev = p
    if len(rets) < 2:
        return 0.0
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


def regime_label(vol_pct: float, trend: float, chop: float,
                 vol_hi: float = 0.75, vol_lo: float = 0.25,
                 trend_threshold: float = 0.02, chop_threshold: float = 0.30) -> str:
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
        model = GaussianHMM(n_components=n_states, covariance_type="full",
                            n_iter=50, random_state=7)
        model.fit(rets)
        state = model.predict(rets)[-1]
        means = model.means_.reshape(-1)
        # state with higher mean = bullish regime
        return "bull" if means[state] == max(means) else "bear"
    except Exception:
        return "unknown"


__all__ = [
    "realized_vol", "vol_percentile", "trend_strength", "choppiness",
    "regime_label", "hmm_regime", "make_vol_series_of_closes",
]