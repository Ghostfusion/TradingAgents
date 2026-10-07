"""Complexity / entropy features of a price-return series (P3, advisory).

Complement to the volatility / trend / HMM regime reads: entropy measures the
*structural complexity* of the series — how much its ordinal pattern or
compressibility deviates from a fully random sequence. High complexity ~
closer to i.i.d. noise; low complexity ~ more structure (trend, cycles,
repetition). Pure / None-safe.
"""

from __future__ import annotations

import math
import random

# Minimum series length before a complexity statistic is reported at all. The
# finite-size bias of these estimators is positive and grows both as the series
# shortens and as it smooths (H -> 1): the source's own table measures +0.075 at
# H = 0.5 but +0.323 at H = 0.9 (arXiv 2512.02352v3, [16]). Below this floor the
# value is a finite-size artifact rather than a measurement, so the read returns
# None instead of a number a caller would threshold.
MIN_COMPLEXITY_BARS = 100


def _clean(series) -> list[float]:
    return [float(v) for v in series if v is not None]


def permutation_entropy(series: list, m: int = 3, delay: int = 1) -> float | None:
    """Normalized permutation entropy (Bandt-Pompe), 0..1.

    Ordinal patterns of length ``m`` over the series; PE = -sum p(pi) ln p(pi)
    / ln(m!). Low -> structured (few dominating patterns); ~1 -> random.
    Requires ``m`` in [2, 6] and at least :data:`MIN_COMPLEXITY_BARS`
    observations (below that the estimator's finite-size bias dominates the
    structure it would report); None otherwise.
    """
    vals = _clean(series)
    if m < 2 or m > 6 or delay < 1:
        return None
    # Need enough ordinal windows to estimate the pattern distribution
    # reliably, and enough of the series that the finite-size bias is not the
    # dominant term (MIN_COMPLEXITY_BARS).
    if len(vals) < max(MIN_COMPLEXITY_BARS, 20 + (m - 1) * delay):
        return None
    patterns: dict[tuple, int] = {}
    for i in range(0, len(vals) - (m - 1) * delay):
        window = vals[i:i + (m - 1) * delay + 1:delay]
        if len(window) < m:
            continue
        order = tuple(sorted(range(m), key=lambda j: window[j]))
        patterns[order] = patterns.get(order, 0) + 1
    n = sum(patterns.values())
    if n == 0:
        return None
    entropy = -sum((c / n) * math.log(c / n) for c in patterns.values())
    return entropy / math.log(math.factorial(m))


def approximate_entropy(series: list, m: int = 2, r: float | None = None) -> float | None:
    """Approximate entropy ApEn(m, r): distinguishes regular from irregular.

    ApEn = Phi^m(r) - Phi^(m+1)(r), where Phi^m = mean over i of
    ln(C_i^m(r)) and C_i^m counts length-m template vectors within tolerance
    r of vector i (Chebyshev distance). Default ``r`` = 0.2 * sigma (the
    standard rule of thumb). Higher = more irregular. None when shorter than
    :data:`MIN_COMPLEXITY_BARS` or of zero variance.
    """
    vals = _clean(series)
    if len(vals) < max(MIN_COMPLEXITY_BARS, m + 5):
        return None
    mu = sum(vals) / len(vals)
    sig = (sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
    if sig <= 1e-12:
        return None
    rr = 0.2 * sig if r is None else float(r)

    def _phi(dim: int) -> float:
        n = len(vals) - dim + 1
        if n <= 0:
            return 0.0
        counts = []
        for i in range(n):
            vec_i = vals[i:i + dim]
            c = 0
            for j in range(n):
                vec_j = vals[j:j + dim]
                if all(abs(a - b) <= rr for a, b in zip(vec_i, vec_j, strict=True)):
                    c += 1
            counts.append(c / n)
        return sum(math.log(c) for c in counts) / n

    try:
        return _phi(m) - _phi(m + 1)
    except (ValueError, ZeroDivisionError):
        return None


def lz_complexity(series: list, alphabet: int = 32) -> float | None:
    """Normalized Lempel-Ziv complexity on the discretized series.

    ``alphabet`` = number of bins for symbolization (default 32). c(n) = the
    number of distinct phrases in the LZ-78 parse; normalized C = c(n) *
    log_alphabet(n) / n. Values near 1 ~ maximal complexity (random), lower
    ~ more structure. None below :data:`MIN_COMPLEXITY_BARS` or when the series
    is constant.
    """
    vals = _clean(series)
    n = len(vals)
    if n < MIN_COMPLEXITY_BARS or alphabet < 2:
        return None
    lo, hi = min(vals), max(vals)
    if hi - lo <= 1e-12:
        return None
    seq = [min(int((v - lo) / (hi - lo) * alphabet), alphabet - 1) for v in vals]

    def _lz_parse(s: list) -> int:
        i = 0
        phrases = set()
        while i < len(s):
            j = i
            while j < len(s) and tuple(s[i:j + 1]) in phrases:
                j += 1
            phrases.add(tuple(s[i:j + 1]))
            i = j + 1 if j == i else j
        return len(phrases)

    c = _lz_parse(seq)
    return c * math.log(n) / (math.log(alphabet) * n) if c else None


def complexity_null_band(
    series: list,
    *,
    statistic: str = "lz",
    n_surrogates: int = 64,
    seed: int = 0,
    tail: float = 0.05,
) -> dict | None:
    """A complexity statistic beside an i.i.d. null band at the SAME length (C1).

    A normalized complexity statistic is interpretable only against a null: its
    value at any length carries a positive finite-size bias, so a fixed cut (the
    ``lzc > 0.9`` this exists to replace) is a claim about the sample, not about
    structure. The null here is the series' own i.i.d. surrogate - the observed
    values randomly permuted, which destroys temporal order while keeping the
    marginal distribution and the length - so the band answers "is this series
    more structured than a shuffle of itself?".

    ``statistic`` selects ``"lz"`` (:func:`lz_complexity`), ``"permutation"``
    (:func:`permutation_entropy`) or ``"approximate"`` (:func:`approximate_entropy`).
    ``n_surrogates`` surrogates are drawn from ``random.Random(seed)`` (seeded, so
    the band is reproducible run-to-run); the band is the ``tail``-central
    quantile range of the surviving null draws, and ``z`` is the observed value's
    standardised distance from the null mean.

    Returns ``{"statistic", "value", "null_mean", "null_lo", "null_hi", "z", "n",
    "n_surrogates", "tail"}`` - or ``None`` below :data:`MIN_COMPLEXITY_BARS`,
    for an unknown statistic, or when fewer than 8 surrogates are defined.
    """
    fn = {
        "lz": lz_complexity,
        "permutation": permutation_entropy,
        "approximate": approximate_entropy,
    }.get(str(statistic).strip().lower())
    if fn is None:
        return None
    vals = _clean(series)
    n = len(vals)
    if n < MIN_COMPLEXITY_BARS:
        return None
    observed = fn(vals)
    if observed is None:
        return None
    rng = random.Random(seed)
    draw = list(vals)
    nulls: list[float] = []
    for _ in range(max(8, int(n_surrogates))):
        rng.shuffle(draw)
        value = fn(draw)
        if value is not None:
            nulls.append(value)
    if len(nulls) < 8:
        return None
    nulls.sort()
    null_mean = sum(nulls) / len(nulls)
    var = sum((x - null_mean) ** 2 for x in nulls) / (len(nulls) - 1)
    sd = math.sqrt(var) if var > 0 else 0.0
    lo = nulls[int(tail / 2 * len(nulls))]
    hi = nulls[min(len(nulls) - 1, int((1.0 - tail / 2) * len(nulls)))]
    return {
        "statistic": str(statistic).strip().lower(),
        "value": observed,
        "null_mean": null_mean,
        "null_lo": lo,
        "null_hi": hi,
        "z": (observed - null_mean) / sd if sd > 0 else None,
        "n": n,
        "n_surrogates": len(nulls),
        "tail": tail,
    }


__all__ = [
    "permutation_entropy",
    "approximate_entropy",
    "lz_complexity",
    "complexity_null_band",
]
