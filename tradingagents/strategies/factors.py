"""Phase 3 - value + momentum factor composite.

Cross-sectional style factors computed from price histories, folding the
value screens (scripts/value_screener.py) into one composite rank:

  momentum = total return over (lookback) with (skip) days skipped
  52w distance = price / 52-week high
  vol-adjusted = momentum / realized vol (risk-normalized)

Composite rank uses percentile ranks so factors are comparable across
different magnitude scales; missing factors are skipped (never fabricated).
"""

from __future__ import annotations


def momentum(closes: list[float], lookback: int = 252, skip: int = 21) -> "float | None":
    """Cross-sectional momentum (12-1m by default): return over [lookback, skip]."""
    if len(closes) <= lookback + skip:
        return None
    start = closes[-lookback - skip]
    end = closes[-1] if skip == 0 else closes[-skip]
    if start <= 0:
        return None
    return end / start - 1.0


def high_distance(closes: list[float], window: int = 252) -> "float | None":
    """Distance from 52-week high: price / trailing high - 1 (<= 0 for losers)."""
    sample = closes[-window:]
    if not sample:
        return None
    hi = max(sample)
    if hi <= 0:
        return None
    return sample[-1] / hi - 1.0


def vol_adjusted_momentum(closes: list[float], lookback: int = 126,
                          vol_window: int = 21) -> "float | None":
    """Momentum divided by realized vol (risk-normalized alpha)."""
    from tradingagents.strategies.regime import realized_vol

    mom = momentum(closes, lookback=lookback, skip=0)
    vol = realized_vol(closes, window=vol_window)
    if mom is None or vol <= 0:
        return None
    return mom / vol


def percentile_rank(value, values) -> float:
    """Percentile rank (0-1) of `value` within `values`; 0.5 when unknown."""
    valid = [v for v in values if v is not None]
    if not valid:
        return 0.5
    below = sum(1 for v in valid if v <= value)
    return below / len(valid)


def composite_score(factors_by_ticker: dict, weights: dict = None) -> dict:
    """Composite (0-1) per ticker from factor dicts via cross-sectional ranks.

    factors_by_ticker: {ticker: {factor_name: value, ...}}
    weights: {factor_name: weight} (defaults equal weight; negative weights
    are allowed, e.g. {'ev_ebit': -1} for the Acquirer multiple).
    """
    names: set = set()
    for f in factors_by_ticker.values():
        names.update(k for k, v in f.items() if v is not None)
    names = sorted(names)
    if weights is None:
        weights = {n: 1.0 for n in names}
    scores: dict = {}
    for ticker, factors in factors_by_ticker.items():
        acc = 0.0
        used = 0
        for name in names:
            value = factors.get(name)
            if value is None:
                continue
            rank = percentile_rank(value, [f.get(name) for f in factors_by_ticker.values()])
            acc += (weights.get(name, 1.0) * rank if weights.get(name, 1.0) >= 0
                    else weights.get(name, 1.0) * (1.0 - rank))
            used += 1
        scores[ticker] = acc / used if used else 0.5
    return scores


__all__ = [
    "momentum", "high_distance", "vol_adjusted_momentum", "percentile_rank",
    "composite_score",
]
