"""R2 - book & tail risk: VaR/CVaR, scenario shocks, drawdown governor.

Pure helpers over return series and weights; deterministic and offline.
"""

import math


def simple_var(returns: list, alpha: float = 0.05) -> float | None:
    """Historical VaR: alpha-quantile of returns (negative = loss)."""
    vals = sorted([float(r) for r in returns if r is not None])
    if not vals:
        return None
    k = max(1, int(alpha * len(vals)))
    return vals[k - 1]


def cvar(returns: list, alpha: float = 0.05) -> float | None:
    """Historical CVaR: mean of the worst alpha tail (negative = loss)."""
    vals = sorted([float(r) for r in returns if r is not None])
    if not vals:
        return None
    k = max(1, int(alpha * len(vals)))
    tail = vals[:k]
    return sum(tail) / len(tail)


def portfolio_cvar(
    returns_by_name: dict,
    weights: dict | None = None,
    alpha: float = 0.05,
) -> float | None:
    """Portfolio CVaR from one return series per name (aligned by index).

    Mixes the per-name daily return series with ``weights`` via
    :func:`portfolio_returns`, then takes the historical CVaR of the weighted
    book series. Semantics:

    - weights summing to **1.0** -> the normalized relative book (historical
      behavior).
    - weights summing to **< 1.0** -> the remainder is implicitly a **zero
      -return cash sleeve** (e.g. money market / cash in the account): the
      mixed series uses the raw (un-normalized) weights, so the daily returns
      are scaled by the invested fraction and the CVaR is diluted by cash
      holding. This is how "include cash as overall portfolio" is honored.
    - weights summing to **> 1.0** (config error) -> normalized down to 1.0
      to remain a valid portfolio.
    - no weights / all-zero -> equal weight across the provided names.

    Returns None when the series cannot be aligned (fewer than two names, or a
    name whose series is missing/short so no common index exists).
    """
    names = list(returns_by_name or {})
    if len(names) < 2:
        return None
    w = weights or {}
    total = sum(float(w.get(n, 0.0) or 0.0) for n in names)
    if total <= 0:
        # No weights given (or all zero): equal share per name.
        share = 1.0 / len(names)
        norm = dict.fromkeys(names, share)
    elif total > 1.0:
        # Over-allocated config: clamp to a valid portfolio (normalize down).
        norm = {n: float(w.get(n, 0.0) or 0.0) / total for n in names}
    else:
        # total in (0, 1]: use the raw weights so the remainder (1 - total)
        # stays as an implicit zero-return cash sleeve (dilutes the tail).
        norm = {n: float(w.get(n, 0.0) or 0.0) for n in names}
    mixed = portfolio_returns(norm, returns_by_name)
    if not mixed:
        return None
    return cvar(mixed, alpha)


def portfolio_returns(weights: dict, returns_by_name: dict) -> list:
    """Weighted aggregate portfolio return series (names aligned by index)."""
    keys = list(weights)
    series = [returns_by_name.get(k) for k in keys]
    if any(s is None for s in series):
        return []
    n = len(series[0])
    out = []
    for i in range(n):
        row = 0.0
        ok = True
        for w, s in zip([weights[k] for k in keys], series, strict=True):
            if i >= len(s):
                ok = False
                break
            v = s[i]
            if v is None:
                ok = False
                break
            row += float(w) * float(v)
        if ok:
            out.append(row)
    return out


def portfolio_drawdown(weights: dict, returns_by_name: dict) -> float | None:
    """Maximum drawdown of the weighted book equity curve (positive magnitude).

    ``portfolio_returns`` mixed to a cumulative equity curve, then the max
    peak-to-trough drop (``evaluate.max_drawdown``). None when the mix is
    unmeasurable (missing names / short series) - callers treat None as
    "unknown, never fails the gate".
    """
    if not weights:
        return None
    mixed = portfolio_returns(weights, returns_by_name)
    if not mixed:
        return None
    from tradingagents.strategies.evaluate import max_drawdown

    eq = []
    acc = 1.0
    for r in mixed:
        acc *= 1.0 + r
        eq.append(acc)
    return max_drawdown(eq) if eq else None


def stress_loss(weights: dict, shock: float = -0.10) -> float:
    """Uniform shock loss (positive number) under given weights."""
    return -float(shock) * sum(max(0.0, float(w)) for w in weights.values())


def book_correlated_stress(
    returns_by_name: dict,
    weights: dict | None = None,
    shock: float = -0.10,
) -> float | None:
    """Book-level correlated stress loss (positive number), or None.

    Real firms shock the whole book together (a macro event moves every
    position at once), not just single names. This computes the weighted
    portfolio return series (names aligned by index, via
    :func:`portfolio_returns`) and measures the historical tail loss under a
    uniform ``shock`` using the worst ``shock``-fraction of the mixed series
    (CVaR-style), so positions that move together are captured - not just a
    flat -10% arithmetic loss.

    Semantics: ``weights`` follow :func:`portfolio_cvar` (sum <= 1 leaves a
    cash sleeve; all-zero -> equal weight; > 1 -> normalized). Returns None
    when the book cannot be resolved (fewer than two aligned names).
    """
    names = list(returns_by_name or {})
    if len(names) < 2:
        return None
    w = weights or {}
    total = sum(float(w.get(n, 0.0) or 0.0) for n in names)
    if total <= 0:
        norm = dict.fromkeys(names, 1.0 / len(names))
    elif total > 1.0:
        norm = {n: float(w.get(n, 0.0) or 0.0) / total for n in names}
    else:
        norm = {n: float(w.get(n, 0.0) or 0.0) for n in names}
    mixed = portfolio_returns(norm, returns_by_name)
    if not mixed:
        return None
    # tail loss: mean of the worst `shock`-fraction of weighted returns
    k = max(1, int(abs(float(shock)) * len(mixed)))
    worst = sorted(mixed)[:k]
    return -sum(worst) / len(worst) if worst else None


def drawdown_gate(drawdown_pct: float | None, limit_pct: float = 0.10) -> bool:
    """True = new risk blocked while realized drawdown exceeds the limit."""
    if drawdown_pct is None:
        return False
    return float(drawdown_pct) > float(limit_pct)


def cdar(equity: list, alpha: float = 0.05) -> dict | None:
    """Conditional Drawdown at Risk (Chekhlov-Uryasev-Zabarankin): the mean of
    the worst ``alpha`` tail of the drawdown process.

    ``CDaR_alpha = E[D_t | D_t >= DVaR_alpha]`` from the drawdown series
    ``D_t = (M_t - P_t) / M_t`` (running peak). A coherent drawdown-tail risk
    read that complements ``max_drawdown`` (single worst) and ``ulcer_index``
    (RMS of all drawdowns). Returns ``{'cdar', 'dvar', 'max_drawdown','n'}``
    (positive loss fractions) or None below 2 valid equity points.
    """
    vals = [float(v) for v in equity if v is not None]
    if len(vals) < 2:
        return None
    peak = vals[0]
    dds: list[float] = []
    for v in vals:
        if v > peak:
            peak = v
        if peak > 0:
            dds.append((peak - v) / peak)
    if len(dds) < 2:
        return None
    dds_sorted = sorted(dds)
    k = max(1, int(math.ceil(alpha * len(dds_sorted))))
    tail = dds_sorted[-k:]
    dvar = tail[0]
    cdar_v = sum(tail) / len(tail)
    return {
        "cdar": round(float(cdar_v), 6),
        "dvar": round(float(dvar), 6),
        "max_drawdown": round(float(dds_sorted[-1]), 6),
        "n": len(dds),
    }


# ---------------------------------------------------------------------------
# Tail decomposition: incremental + component VaR (quants.md §Risk)
# ---------------------------------------------------------------------------


def _book_var(weights: dict, returns_by_name: dict, alpha: float = 0.05) -> float | None:
    """Historical VaR of the weighted book (negative = loss) or None."""
    mixed = portfolio_returns(weights, returns_by_name)
    if not mixed:
        return None
    return simple_var(mixed, alpha)


def incremental_var(
    returns_by_name: dict,
    weights: dict,
    alpha: float = 0.05,
    delta: float = 0.01,
) -> dict | None:
    """Per-name incremental VaR: ``VaR(w + d_i) - VaR(w)`` for each name.

    IVaR_i answers "how much does the book tail widen if I add delta weight
    to name i (cash-neutral pull from the others)". Positive = riskier.
    Returns ``{"total_var": float, "incremental": {name: float}, "alpha",
    "delta"}`` or None when the book cannot be aligned.
    """
    names = list(returns_by_name or {})
    if len(names) < 3 or not weights:
        return None
    base = _book_var(weights, returns_by_name, alpha)
    if base is None:
        return None
    out = {}
    for n in names:
        if weights.get(n, 0.0) == 0.0:
            continue
        # Add delta to n, scale the others proportionally so weights sum 1.
        w_adj = {k: float(v) * (1.0 - delta) for k, v in weights.items() if k != n}
        w_adj[n] = float(weights.get(n, 0.0)) + delta
        v = _book_var(w_adj, returns_by_name, alpha)
        if v is not None:
            out[n] = round(v - base, 6)
    if not out:
        return None
    return {"total_var": round(base, 6), "incremental": out, "alpha": alpha, "delta": delta}


def component_var(
    returns_by_name: dict,
    weights: dict,
    alpha: float = 0.05,
) -> dict | None:
    """Per-name component VaR via the normal-covariance decomposition.

    Under joint normality ``CVaR_i = w_i * (Sigma w)_i / sqrt(w' Sigma w)``
    scaled to the book's historical VaR so the components **sum to the total
    book VaR** (the standard MCR-based decomposition). Answers "which name is
    the tail". Returns ``{"total_var", "components": {name: float}, "coverage"
    }`` (coverage = sum(components)/total) or None when degenerate.
    """
    names = [n for n in (returns_by_name or {}) if returns_by_name.get(n)]
    if len(names) < 3 or not weights:
        return None
    import numpy as _np

    series = []
    for n in names:
        s = [float(x) for x in returns_by_name[n] if x is not None]
        if len(s) < 2:
            return None
        series.append(s)
    n = min(len(s) for s in series)
    mat = _np.array([s[-n:] for s in series], dtype=float)
    w = _np.array([float(weights.get(nn, 0.0)) for nn in names], dtype=float)
    if w.sum() <= 0:
        w = _np.ones(len(names)) / len(names)
    mean = mat.mean(axis=1)
    demeaned = mat - mean[:, None]
    Sigma = (demeaned @ demeaned.T) / (n - 1)
    port_var = float(w @ Sigma @ w)
    if port_var <= 1e-12:
        return None
    mcrs = (Sigma @ w) / (port_var ** 0.5)
    c = w * mcrs
    total_hist = _book_var(dict(zip(names, w, strict=False)), returns_by_name, alpha)
    if total_hist is None:
        return None
    scale = total_hist / c.sum() if abs(c.sum()) > 1e-12 else 1.0
    comps = {nn: round(float(v) * scale, 6) for nn, v in zip(names, c, strict=False)}
    return {
        "total_var": round(total_hist, 6),
        "components": comps,
        "coverage": round(float((c * scale).sum()) / total_hist, 4) if total_hist else None,
    }


# ---------------------------------------------------------------------------
# Horizon risk + i.i.d. gate (QuantLib Q1/Q4)
# ---------------------------------------------------------------------------


def return_autocorrelation(returns: list, max_lag: int = 5) -> dict:
    """Return autocorrelation (lag-1..max_lag) + Ljung-Box style Q stat.

    QuantLib gate: momentum books carry lag-1 autocorrelation, so naive
    sqrt(T) scaling (in :func:`var_cvar_horizon`) *understates* multi-day
    risk. ``'is_iidish'`` is True only when lag-1 |ACF| is small and there are
    enough samples. Returns dict, or ``{'acf': [], 'q_stat': None,
    'is_iidish': False}`` for an empty/short series — never fabricated.
    """
    vals = [float(r) for r in returns if r is not None]
    out = {"acf": [], "q_stat": None, "is_iidish": False}
    n = len(vals)
    if n < 32:
        return out
    mean = sum(vals) / n
    denom = sum((v - mean) ** 2 for v in vals)
    if denom <= 0:
        return out
    ml = max(1, min(int(max_lag), n - 2))
    acf: list[float] = []
    for lag in range(1, ml + 1):
        num = sum((vals[i] - mean) * (vals[i + lag] - mean) for i in range(n - lag))
        acf.append(num / denom)
    # Ljung-Box: Q = n(n+2) * sum(acf_k^2 / (n-k))
    q = (n * (n + 2.0) * sum(a * a / (n - k) for k, a in enumerate(acf, start=1))
         if acf else None)
    is_iidish = bool(acf) and abs(acf[0]) < 0.2 and (q is not None and q < 10.0)
    return {"acf": [round(a, 4) for a in acf], "q_stat": round(q, 2) if q else None,
            "is_iidish": is_iidish}


def var_cvar_horizon(returns: list, horizon_days: int, alpha: float = 0.95,
                     method: str = "empirical") -> dict:
    """Value-at-Risk / CVaR at a multi-day horizon (QuantLib Q1).

    - ``empirical``: scale the historical daily VaR/CVaR quantile by sqrt(T)
      (variance-additive under i.i.d.).
    - ``parametric``: assume daily returns ~ N(mu, sigma^2); the T-day return
      is N(T*mu, T*sigma^2) and VaR/CVaR come from the Normal tail.

    Returns dict with float-or-None entries and an ``'scaling_valid'`` flag
    (False when the series is autocorrelated/short so sqrt(T) is unreliable).
    """
    vals = [float(r) for r in returns if r is not None]
    out = {"emp_var": None, "emp_cvar": None, "param_var": None,
           "param_cvar": None, "scaling_valid": False, "n": len(vals)}
    T = max(1, int(horizon_days))
    n = len(vals)
    if n < 2:
        return out
    alpha = float(alpha)
    q = 1.0 - alpha  # left-tail probability
    asc = sorted(vals)
    k = max(1, int(q * n))
    daily_var = asc[k - 1]                      # negative (loss)
    daily_cvar = sum(asc[:k]) / k               # negative (loss)
    # empirical sqrt(T) scaling
    out["emp_var"] = daily_var * math.sqrt(T)
    out["emp_cvar"] = daily_cvar * math.sqrt(T)
    # parametric (normal)
    mean = sum(vals) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
    if sd > 0:
        z = 1.959964  # N(0,1) quantile at 2.5%, adjust to (1-alpha)
        # two-sided-ish mapping: map q to z via inverse normal approx
        import statistics as _st
        try:
            z = _st.NormalDist().inv_cdf(q)
        except Exception:  # noqa: BLE001 - fall back to 1.96
            z = 1.959964
        mu_T = mean * T
        sigma_T = sd * math.sqrt(T)
        out["param_var"] = mu_T + z * sigma_T
        # Normal left-tail CVaR = mu_T - sigma_T * phi(z) / q, where
        # q = 1 - alpha is the tail probability and phi is the standard normal
        # PDF at the alpha quantile z. (Previously divided by alpha and negated
        # mu, which returned a wrong-sign, ~19x-too-small "gain".)
        out["param_cvar"] = mu_T - sigma_T * math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi) / q
    # validity gate: sqrt(T) safe only near-i.i.d. with enough samples
    acf = return_autocorrelation(vals)["acf"]
    out["scaling_valid"] = len(vals) >= 32 and (not acf or abs(acf[0]) < 0.2)
    return out


__all__ = ["simple_var", "cvar", "portfolio_cvar", "portfolio_returns", "stress_loss", "book_correlated_stress", "drawdown_gate",
           "cdar", "return_autocorrelation", "var_cvar_horizon", "incremental_var", "component_var"]
