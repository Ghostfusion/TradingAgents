"""Complexity / entropy features of a price-return series (P3, advisory).

Complement to the volatility / trend / HMM regime reads: entropy measures the
*structural complexity* of the series — how much its ordinal pattern or
compressibility deviates from a fully random sequence. High complexity ~
closer to i.i.d. noise; low complexity ~ more structure (trend, cycles,
repetition). Pure / None-safe.
"""

from __future__ import annotations

import math


def _clean(series) -> list[float]:
    return [float(v) for v in series if v is not None]


def permutation_entropy(series: list, m: int = 3, delay: int = 1) -> float | None:
    """Normalized permutation entropy (Bandt-Pompe), 0..1.

    Ordinal patterns of length ``m`` over the series; PE = -sum p(pi) ln p(pi)
    / ln(m!). Low -> structured (few dominating patterns); ~1 -> random.
    Requires >= m! + m observations (each pattern needs a sample) and m in
    [2, 6]; None otherwise.
    """
    vals = _clean(series)
    if m < 2 or m > 6 or delay < 1:
        return None
    # Need enough ordinal windows to estimate the pattern distribution
    # reliably (m=3 -> 6 patterns; ~10x coverage needs ~60 windows).
    if len(vals) < 20 + (m - 1) * delay:
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
    standard rule of thumb). Higher = more irregular. None when too short or
    zero variance.
    """
    vals = _clean(series)
    if len(vals) < m + 5:
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
    ~ more structure. None when too short.
    """
    vals = _clean(series)
    n = len(vals)
    if n < 100 or alphabet < 2:
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


__all__ = ["permutation_entropy", "approximate_entropy", "lz_complexity"]
