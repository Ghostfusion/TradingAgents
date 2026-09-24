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
- ``availability_gate(expr, ...)`` — the H2 registration-time AST gate that
  refuses a forward shift or a field whose declared observability is later than
  the decision date, so look-ahead is inexpressible rather than discouraged.

No-fabrication: under min-obs or degenerate input a factor is ``None`` /
``unavailable``, never a guessed number.
"""

from __future__ import annotations

import ast
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
    """Daily close-to-close returns aligned 1:1 with closes (index 0 = None).

    r_t = c_t/c_{t-1} - 1 (positive when the price rose; the old prev/c - 1
    was sign-inverted, swapping the up/down volume-volatility features).
    """
    out: list[float | None] = []
    prev: float | None = None
    for c in closes:
        if c is None:
            out.append(None)
            prev = None
            continue
        out.append(c / prev - 1.0 if prev else None)
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


# ---------------------------------------------------------------------------
# Availability gate (H2): refuse look-ahead at registration, not at the score
# ---------------------------------------------------------------------------
#
# The DSL is bounded and the purity gate makes an expression *pure*, but pure is
# not causal: a side-effect-free expression can still reference a field that was
# not observable at the decision date, or shift a series forward. H2 makes both
# inexpressible rather than discouraged - a static AST check at registration
# time, so the cost is paid once at admission and never per run.

#: Operators whose second argument is a shift. A negative ``k`` reads the
#: future: ``ref(close, -1)`` is tomorrow's close, ``delta(close, -1)`` a
#: forward difference, ``pct_change(close, -1)`` a forward return.
_SHIFT_OPERATORS = {"ref", "delta", "pct_change"}


def _availability_gate_on(cfg: dict | None) -> bool:
    """Is the availability gate on? Default off (``enable_factor_availability_gate``).

    The key is read by its literal name in the ``cfg.get("...")`` idiom: the
    gate registry's read-site scan looks for a quoted key in an access idiom,
    and a gate read through a variable is a gate the registry cannot see. The
    read works with the key absent (``DEFAULT_CONFIG`` is the integrator's), so
    an unregistered gate is inert and today's behaviour is unchanged.
    """
    if cfg is None:
        try:
            from tradingagents.dataflows.config import get_config

            cfg = get_config() or {}
        except Exception:  # noqa: BLE001 - a missing config is an ungated read
            cfg = {}
    return bool(cfg.get("enable_factor_availability_gate", False))


def _is_negative_literal(node) -> bool:
    """True when an AST node is a negative numeric literal (``-1``, ``-7.0``)."""
    return (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
        and not isinstance(node.operand.value, bool)
        and node.operand.value > 0
    )


def _forward_shifts(tree) -> list[str]:
    """The forward-shifting calls in an expression, spelled for the refusal."""
    hits: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id not in _SHIFT_OPERATORS:
            continue
        if len(node.args) >= 2 and _is_negative_literal(node.args[1]):
            hits.append(f"{node.func.id}(..., {ast.unparse(node.args[1])})")
    return hits


def _referenced_fields(tree, fields: set) -> list[str]:
    """The data fields an expression references, in first-appearance order."""
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in fields and node.id not in out:
            out.append(node.id)
    return out


def _declared_observability(field: str, declared: dict | None):
    """The declaration for ``field``: the caller's, else the record's own.

    The caller's map wins (a registration may date one field differently), then
    the ``factor_schema`` record answers for its factor, then the table's
    general lookup. Anything left is undeclared and fails closed downstream.
    """
    if declared and field in declared:
        return declared[field]
    from tradingagents.strategies.factor_schema import FACTOR_SCHEMA, observability_for

    if field in FACTOR_SCHEMA:
        return FACTOR_SCHEMA[field].observability
    return observability_for(field)


def _observable_at(field: str, decl, decision_date: str | None,
                   pit_root: str | None = None) -> tuple[bool, str]:
    """Is ``field`` observable at ``decision_date``, given its declaration? ``(ok, reason)``

    ``decl`` is an observability class string, or ``{"class": ..., "as_of": ...,
    "symbol": ...}``. The dated classes are bound to the producers that already
    know the answer: ``data_quality.fundamentals_pit_ok`` decides a filing/macro
    date against the decision date, and, when the declaration names a symbol,
    ``dataflows.pit_registry.read_as_of`` must carry a vintage visible at the
    decision date or the declaration cannot be corroborated.

    Fail closed throughout: an undeclared field, a class that needs a date and
    has none, a decision date to measure against that was not supplied, or a
    vintage the registry cannot place is refused with its reason - never assumed
    safe (H8's per-field lag table is not built, and no lag is invented here).
    """
    from tradingagents.strategies.factor_schema import (
        NEXT_SESSION,
        OBSERVABILITY_CLASSES,
        SESSION_CLOSE,
    )

    if decl is None:
        return False, (
            f"field {field!r} has no declared observability class; refused "
            "(fail closed: no publication lag is invented here - H8's "
            "per-field lag table is not built)"
        )
    cls = decl.get("class") if isinstance(decl, dict) else decl
    if cls not in OBSERVABILITY_CLASSES:
        return False, f"field {field!r} declares unknown observability class {cls!r}"
    if cls == SESSION_CLOSE:
        return True, ""
    if cls == NEXT_SESSION:
        return False, (
            f"field {field!r} is declared {NEXT_SESSION!r}: not observable until "
            "the next session, i.e. after a decision taken at this session's close"
        )
    as_of = decl.get("as_of") if isinstance(decl, dict) else None
    if not as_of:
        return False, (
            f"field {field!r} is declared {cls!r} with no as_of date; refused "
            "(fail closed)"
        )
    if not decision_date:
        return False, (
            f"field {field!r} is declared {cls!r} but no decision date was "
            "supplied to measure it against; refused (fail closed)"
        )
    from tradingagents.strategies.data_quality import fundamentals_pit_ok

    if not fundamentals_pit_ok(str(as_of), str(decision_date)):
        return False, (
            f"field {field!r} dates from {as_of} ({cls}), later than the decision "
            f"date {decision_date}: look-ahead refused"
        )
    symbol = decl.get("symbol") if isinstance(decl, dict) else None
    if symbol:
        from tradingagents.dataflows.pit_registry import read_as_of

        if read_as_of(str(symbol), str(decision_date), root=pit_root) is None:
            return False, (
                f"field {field!r} has no PIT snapshot for {symbol!r} visible at "
                f"{decision_date}; the vintage is unverifiable (refused, fail closed)"
            )
    return True, ""


def availability_gate(expr: str, *, declared: dict | None = None,
                      decision_date: str | None = None,
                      pit_root: str | None = None,
                      cfg: dict | None = None) -> tuple[bool, str]:
    """Registration-time AST gate: refuse a look-ahead expression. ``(ok, reason)``

    Runs the zoo's ``purity_gate`` first and unchanged, then adds H2's two
    refusals, so a pure expression that is not *causal* is refused before it can
    run:

    * any **forward shift** - a negative ``k`` in ``ref`` / ``delta`` /
      ``pct_change`` reads the future;
    * any referenced **field whose declared availability is later than the
      decision date** - the class comes from the ``factor_schema`` record (or a
      caller's ``declared`` map) and is measured by
      ``data_quality.fundamentals_pit_ok`` and ``pit_registry.read_as_of``.

    ``declared`` maps a field name to an observability class or to
    ``{"class": ..., "as_of": ..., "symbol": ...}``; it also widens the
    expression's field vocabulary, because the schema's factors are not OHLCV
    columns. Static analysis only - no evaluation, no per-run cost.

    Behind ``enable_factor_availability_gate`` (default off). With the gate off
    this returns the unchanged ``purity_gate`` verdict, so the zoo behaves
    exactly as it did before H2 existed. Fail closed: a field with no declared
    availability is refused with its reason, never assumed safe.
    """
    from tradingagents.strategies.alpha_zoo import purity_gate

    if not _availability_gate_on(cfg):
        return purity_gate(expr)
    from tradingagents.strategies.factor_schema import FACTOR_SCHEMA, MARKET_CLOSE_FIELDS

    fields = set(MARKET_CLOSE_FIELDS) | set(declared or {}) | set(FACTOR_SCHEMA)
    ok, reason = purity_gate(expr, extra_fields=fields)
    if not ok:
        return False, reason
    try:
        tree = ast.parse(str(expr or "").strip(), mode="eval")
    except SyntaxError as ex:  # unreachable after purity_gate, kept fail-closed
        return False, f"invalid syntax: {ex}"
    shifts = _forward_shifts(tree)
    if shifts:
        return False, "forward shift refused (reads the future): " + ", ".join(shifts)
    for field in _referenced_fields(tree, fields):
        observable, why = _observable_at(
            field, _declared_observability(field, declared), decision_date, pit_root,
        )
        if not observable:
            return False, why
    return True, ""


__all__ = [
    "ref", "delta", "mean", "std", "zscore", "rsi", "bias", "mom", "corr",
    "avg_vol", "high_low_range", "cross_sectional_rank",
    "fit_zscore", "apply_zscore", "fit_winsorize", "apply_winsorize",
    "alpha158_subset", "cached_expression", "clear_expr_cache", "expr_cache_size",
    "availability_gate", "_ALPHA158_SUBSET",
]
