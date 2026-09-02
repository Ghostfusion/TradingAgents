"""Pure factor-expression engine over OHLCV series (Qlib Alpha158-style subset).

Qlib pillar 1 + pillar 12/20 port: a small operator set over price/panel
series (``Ref/Delta/Mean/Std/ZScore/Rsi/Bias/Mom/Rank/Corr/AvgVol/
HighLowRange``), each a pure function returning ``list[float | None]`` with
leading ``None`` padding under min-observation, plus:

- ``alpha158_subset(ohlcv)`` — a ~16-feature Alpha158-flavored subset
  (momentum/reversal/volatility/value) computed off the run-level OHLCV cache.
- the **learn/infer processor split** (Qlib ``DataHandlerLP``): any
  cross-sectional transform (z-score / winsorize) declares ``fit_*`` /
  ``apply_*`` so the moments are FIT on the train segment only and applied to
  valid/test/live — the mechanical no-look-ahead rule.
- an **expression-string-keyed cache** (Qlib pillar 20: 7.4 s vs 184.4 s on
  a 14-feature build) layered on the caller's raw OHLCV dict, invalidated by
  the as-of window.

No-fabrication: under min-obs or degenerate input a factor is ``None`` /
``unavailable``, never a guessed number.
"""

from __future__ import annotations

import math

import numpy as np

_EXPR_CACHE: dict[tuple, list] = {}
_EXPR_CACHE_CAP = 512


def clear_expr_cache() -> None:
    """Drop the expression cache (tests / fresh runs)."""
    _EXPR_CACHE.clear()


def expr_cache_size() -> int:
    """Number of cached expression results (tests/debug)."""
    return len(_EXPR_CACHE)


def _cache_get(key: tuple) -> list | None:
    """Read a cache entry; a hit refreshes recency (dict is insertion-ordered)."""
    hit = _EXPR_CACHE.get(key)
    if hit is not None:
        _EXPR_CACHE.pop(key)
        _EXPR_CACHE[key] = hit
    return hit


def _cache_put(key: tuple, value: list) -> list:
    _EXPR_CACHE[key] = value
    while len(_EXPR_CACHE) > _EXPR_CACHE_CAP:
        _EXPR_CACHE.pop(next(iter(_EXPR_CACHE)))
    return value


def cached_expression(expr: str, symbol: str, days: int, date: str | None,
                      series: dict) -> list | dict:
    """Compute ``expr`` with an expression-string + instrument + range cache.

    The cache key includes the as-of ``date`` so a later window never reuses
    values computed on a different slice (PIT-safe at the expression level).
    ``expr`` is one of ``alpha158`` (-> the feature dict) or
    ``alpha158:<feature>`` (-> that feature's series); anything else falls
    through with no cache entry.
    """
    key = (expr, str(symbol).upper(), int(days), date)
    hit = _cache_get(key)
    if hit is not None:
        return hit
    if expr == "alpha158":
        return _cache_put(key, alpha158_subset(series))
    if expr.startswith("alpha158:"):
        name = expr.split(":", 1)[1]
        alpha = alpha158_subset(series)
        if name not in alpha:
            return []
        return _cache_put(key, alpha[name])
    return []


# ---------------------------------------------------------------------------
# Rolling helpers
# ---------------------------------------------------------------------------


def _roll_apply(values: list, k: int, fn) -> list:
    """Rolling ``fn(window) -> float`` over ``values``; leading None padding.

    Returns ``[None]*(k-1) + [float]*(n-k+1)`` when len(values) >= k, else
    a full-length list of None (min-observation rule).
    """
    if k < 1:
        return [None] * len(values)
    arr = np.asarray(values, dtype=float)
    if arr.size < k:
        return [None] * len(values)
    windows = np.lib.stride_tricks.sliding_window_view(arr, k)
    out = [None] * (k - 1)
    for w in windows:
        clean = w[np.isfinite(w)]
        if clean.size < k:  # missing values -> window not full -> unavailable
            out.append(None)
            continue
        try:
            v = fn(clean)
        except (ValueError, ZeroDivisionError, FloatingPointError):
            v = None
        out.append(float(v) if v is not None else None)
    return out


def _as_float(values: list) -> list[float | None]:
    """Finite-float clean with None holes preserved."""
    out: list[float | None] = []
    for v in values:
        try:
            f = float(v)
            out.append(f if math.isfinite(f) else None)
        except (TypeError, ValueError):
            out.append(None)
    return out


# ---------------------------------------------------------------------------
# Operators (pure; lead with None padding)
# ---------------------------------------------------------------------------


def ref(values: list, k: int) -> list[float | None]:
    """Qlib ``Ref(k)``: value k periods ago (None in the first k slots)."""
    s = _as_float(values)
    if k <= 0:
        return s
    return [None] * min(k, len(s)) + s[: len(s) - k] if len(s) > k else [None] * len(s)


def delta(values: list, k: int) -> list[float | None]:
    """Qlib ``Delta(k)``: ``s - Ref(k)``."""
    s = _as_float(values)
    r = ref(s, k)
    return [None if a is None or b is None else a - b for a, b in zip(s, r, strict=True)]


def mean(values: list, k: int) -> list[float | None]:
    """Rolling mean over k observations."""
    return _roll_apply(_as_float(values), k, np.mean)


def std(values: list, k: int) -> list[float | None]:
    """Rolling sample standard deviation over k observations."""
    return _roll_apply(_as_float(values), k, lambda w: float(np.std(w, ddof=1)))


def zscore(values: list, k: int) -> list[float | None]:
    """Rolling z-score: ``(s - mean_k) / std_k``; None where std is ~0."""
    s = _as_float(values)
    if len(s) < k:
        return s

    def _z(w: np.ndarray) -> float | None:
        sdv = float(np.std(w, ddof=1))
        if sdv <= 1e-12:
            return None
        return float((w[-1] - float(np.mean(w))) / sdv)

    return _roll_apply(s, k, _z)


def rsi(values: list, k: int = 14) -> list[float | None]:
    """Relative Strength Index over daily changes (simple rolling gains/losses).

    All-up window -> 100; all-down -> 0; flat -> 50 (no-fabrication corner).
    """
    s = _as_float(values)
    if k < 1 or len(s) < k + 1:
        return [None] * len(s)
    diffs = [s[i] - s[i - 1] if s[i] is not None and s[i - 1] is not None else 0.0
             for i in range(1, len(s))]
    gains = np.asarray([d if d > 0 else 0.0 for d in diffs], dtype=float)
    losses = np.asarray([-d if d < 0 else 0.0 for d in diffs], dtype=float)

    def _rsi_level(avg_g: float, avg_l: float) -> float:
        if avg_l <= 1e-12:
            return 100.0
        if avg_g <= 1e-12:
            return 0.0
        return 100.0 - 100.0 / (1.0 + avg_g / avg_l)

    # RSI at close index k uses the first k daily diffs (Wilder-style renewal
    # afterwards), so lead with k Nones and land one value per close.
    out = [None] * k
    avg_g = float(np.mean(gains[:k]))
    avg_l = float(np.mean(losses[:k]))
    out.append(_rsi_level(avg_g, avg_l))
    for i in range(k, len(diffs)):
        avg_g = (avg_g * (k - 1) + gains[i]) / k
        avg_l = (avg_l * (k - 1) + losses[i]) / k
        out.append(_rsi_level(avg_g, avg_l))
    return out


def bias(values: list, k: int) -> list[float | None]:
    """Qlib ``Bias(k)``: ``s / Mean(k) - 1``."""
    s = _as_float(values)
    m = mean(s, k)
    return [None if a is None or b is None or b <= 0 else a / b - 1.0
            for a, b in zip(s, m, strict=True)]


def mom(values: list, k: int) -> list[float | None]:
    """Qlib ``Mom(k)``: ``s / Ref(k) - 1`` (k-period momentum)."""
    s = _as_float(values)
    r = ref(s, k)
    return [None if a is None or b is None or b <= 0 else a / b - 1.0
            for a, b in zip(s, r, strict=True)]


def corr(x: list, y: list, k: int) -> list[float | None]:
    """Rolling Pearson correlation of x vs y over k observations."""
    a = _as_float(x)
    b = _as_float(y)
    if len(a) != len(b):
        return [None] * len(a)

    def _c(wa: np.ndarray, wb: np.ndarray) -> float | None:
        if float(np.std(wa, ddof=1)) <= 1e-12 or float(np.std(wb, ddof=1)) <= 1e-12:
            return None
        return float(np.corrcoef(wa, wb)[0, 1])

    if len(a) < k:
        return [None] * len(a)
    aw = np.lib.stride_tricks.sliding_window_view(np.asarray(a, dtype=float), k)
    bw = np.lib.stride_tricks.sliding_window_view(np.asarray(b, dtype=float), k)
    out = [None] * (k - 1)
    for wa, wb in zip(aw, bw, strict=True):
        out.append(_c(wa, wb))
    return out


def avg_vol(volumes: list, k: int) -> list[float | None]:
    """Qlib ``AvgVol(k)``: rolling mean volume."""
    return _roll_apply(_as_float(volumes), k, np.mean)


def high_low_range(highs: list, lows: list, closes: list, k: int) -> list[float | None]:
    """Rolling mean of intraday range ``(high - low) / close``."""
    h = _as_float(highs)
    lo = _as_float(lows)
    c = _as_float(closes)
    if len(h) != len(lo) or len(h) != len(c):
        return [None] * len(h)
    spans = [None if (a is None or b is None or cc is None or cc <= 0)
             else (a - b) / cc for a, b, cc in zip(h, lo, c, strict=True)]
    return _roll_apply(spans, k, np.mean)


# ---------------------------------------------------------------------------
# Cross-sectional rank (panel per-date)
# ---------------------------------------------------------------------------


def cross_sectional_rank(panel: dict, i: int, min_assets: int = 3) -> dict[str, float] | None:
    """Per-date percentile rank (0..1) across a name->series panel at index i.

    Average-tie rank normalized to [0, 1]; ``None`` under min-observation
    breadth or when no asset at index ``i`` is finite (no fabrication).
    """
    vals: dict[str, float] = {}
    for name, series in panel.items():
        if series is None or i >= len(series) or series[i] is None:
            continue
        try:
            f = float(series[i])
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            vals[name] = f
    if len(vals) < min_assets:
        return None
    order = sorted(vals.items(), key=lambda kv: kv[1])
    ranks: dict[str, float] = {}
    n = len(order)
    j = 0
    while j < n:
        j2 = j
        while j2 + 1 < n and order[j2 + 1][1] == order[j][1]:
            j2 += 1
        avg_rank = (j + j2) / 2.0 + 1.0
        for kk in range(j, j2 + 1):
            ranks[order[kk][0]] = (avg_rank - 1.0) / (n - 1) if n > 1 else 1.0
        j = j2 + 1
    return ranks


# ---------------------------------------------------------------------------
# Learn/infer processor split (Qlib DataHandlerLP)
# ---------------------------------------------------------------------------


def fit_zscore(train: list) -> tuple[float, float] | None:
    """Fit z-score moments on the TRAIN segment only; None when degenerate."""
    vals = [float(v) for v in train if v is not None]
    if len(vals) < 2:
        return None
    sd = float(np.std(vals, ddof=1))
    if sd <= 1e-12:
        return None
    return (float(np.mean(vals)), sd)


def apply_zscore(values: list, moments: tuple[float, float] | None) -> list[float | None]:
    """Apply pre-fit z-score moments to any segment (valid/test/live)."""
    if moments is None:
        return [None] * len(values)
    mu, sd = moments
    return [None if v is None else (float(v) - mu) / sd for v in values]


def fit_winsorize(train: list, lo_q: float = 0.01, hi_q: float = 0.99) -> tuple[float, float] | None:
    """Fit clip bounds on the TRAIN segment only; None when degenerate."""
    vals = [float(v) for v in train if v is not None]
    if len(vals) < 2:
        return None
    arr = np.asarray(vals, dtype=float)
    lo, hi = float(np.quantile(arr, min(lo_q, hi_q))), float(np.quantile(arr, max(lo_q, hi_q)))
    return (lo, hi)


def apply_winsorize(values: list, bounds: tuple[float, float] | None) -> list[float | None]:
    """Apply pre-fit clip bounds to any segment."""
    if bounds is None:
        return [None] * len(values)
    lo, hi = bounds
    return [None if v is None else min(max(float(v), lo), hi) for v in values]


# ---------------------------------------------------------------------------
# Alpha158-style subset over an OHLCV cache dict
# ---------------------------------------------------------------------------

_ALPHA158_SUBSET = [
    "mom_5", "mom_10", "mom_20", "mom_60",
    "rsi_14", "bias_20", "zscore_20",
    "std_20", "return_std_10", "high_low_range_20", "avg_vol_20",
    "corr_ret_vol_20", "max_high_20", "min_low_20", "up_vol_10", "down_vol_10",
]


def _returns(closes: list) -> list[float | None]:
    """Daily close-to-close returns aligned 1:1 with closes (index 0 = None)."""
    out: list[float | None] = []
    prev: float | None = None
    for c in closes:
        if c is None:
            out.append(None)
            prev = None
            continue
        out.append(prev / c - 1.0 if prev else None)
        prev = float(c)
    return out


def alpha158_subset(ohlcv: dict) -> dict[str, list[float | None]]:
    """~16-feature Alpha158-style subset off an ``{closes, opens, highs,
    lows, volumes}`` dict (the ``_RUN_OHLCV_CACHE`` shape).

    Momentum/reversal/volatility/value families; every list is the same length
    as the closes with leading ``None`` padding. Advisory: computed numbers
    for the LLM to cite, never gates.
    """
    closes = ohlcv.get("closes") or []
    highs = ohlcv.get("highs") or []
    lows = ohlcv.get("lows") or []
    volumes = ohlcv.get("volumes") or []
    n = len(closes)
    if n == 0:
        return {f: [] for f in _ALPHA158_SUBSET}
    rets = _returns(closes)
    pad = lambda s: (s + [None] * (n - len(s))) if len(s) < n else s  # noqa: E731
    features: dict[str, list[float | None]] = {
        "mom_5": pad(mom(closes, 5)),
        "mom_10": pad(mom(closes, 10)),
        "mom_20": pad(mom(closes, 20)),
        "mom_60": pad(mom(closes, 60)),
        "rsi_14": pad(rsi(closes, 14)),
        "bias_20": pad(bias(closes, 20)),
        "zscore_20": pad(zscore(closes, 20)),
        "std_20": pad(std(closes, 20)),
        "return_std_10": pad(std(rets, 10)),
        "high_low_range_20": pad(high_low_range(highs, lows, closes, 20)),
        "avg_vol_20": pad(avg_vol(volumes, 20)),
        "corr_ret_vol_20": pad(corr(closes, volumes, 20)),
        "max_high_20": pad(_max_high(highs, 20, closes)),
        "min_low_20": pad(_min_low(lows, 20, closes)),
        "up_vol_10": pad(_side_vol(rets, 10, up=True)),
        "down_vol_10": pad(_side_vol(rets, 10, up=False)),
    }
    return features


def _max_high(highs: list, k: int, closes: list) -> list[float | None]:
    s = _as_float(highs)
    c = _as_float(closes)
    if not s or len(s) != len(c):
        return [None] * len(c)
    return [None if (hi is None or cc is None or cc <= 0) else hi / cc - 1.0
            for hi, cc in zip(_roll_max(s, k), c, strict=True)]


def _min_low(lows: list, k: int, closes: list) -> list[float | None]:
    s = _as_float(lows)
    c = _as_float(closes)
    if not s or len(s) != len(c):
        return [None] * len(c)
    return [None if (lo is None or cc is None or lo <= 0) else cc / lo - 1.0
            for lo, cc in zip(_roll_min(s, k), c, strict=True)]


def _roll_max(values: list, k: int) -> list[float | None]:
    return _roll_apply(values, k, np.max)


def _roll_min(values: list, k: int) -> list[float | None]:
    return _roll_apply(values, k, np.min)


def _side_vol(rets: list, k: int, up: bool) -> list[float | None]:
    """Std dev of positive (up) or negative (down) returns in a k-window."""
    vals = [v for v in rets if v is not None]

    def _f(w: np.ndarray) -> float | None:
        selected = w[w > 0] if up else w[w < 0]
        if selected.size < 2:
            return None
        return float(np.std(selected, ddof=1))

    return _roll_apply(vals, k, _f)


__all__ = [
    "ref", "delta", "mean", "std", "zscore", "rsi", "bias", "mom", "corr",
    "avg_vol", "high_low_range", "cross_sectional_rank",
    "fit_zscore", "apply_zscore", "fit_winsorize", "apply_winsorize",
    "alpha158_subset", "cached_expression", "clear_expr_cache", "expr_cache_size",
    "_ALPHA158_SUBSET",
]
