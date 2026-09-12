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


# ---------------------------------------------------------------------------
# EVT / GPD extreme tail (six-pillar §4.23-4.24, master-catalog PART XX)
# ---------------------------------------------------------------------------


def _gpd_fit(exceedances: list[float]) -> tuple[float, float] | None:
    """Fit a Generalized Pareto Distribution to positive exceedances.

    ``G(y) = 1 - (1 + xi*y/beta)^(-1/xi)`` fit by maximum likelihood
    (Nelder-Mead, method-of-moments warm start). Returns ``(xi, beta)`` or
    None when the fit fails / is degenerate. The ``xi < 0`` (bounded tail),
    ``xi = 0`` (exponential) and ``xi > 0`` (fat tail) cases all fall out of
    the same likelihood; ``xi >= 1`` is rejected by the caller (mean
    undefined).
    """
    import numpy as _np
    from scipy.optimize import minimize

    y = _np.array(exceedances, dtype=float)
    n = len(y)
    if n < 2:
        return None
    mean = float(y.mean())
    var = float(y.var(ddof=0))
    if var <= 0 or mean <= 0:
        return None
    # Method-of-moments warm start.
    xi0 = 0.5 * (1.0 - mean * mean / var)
    b0 = 0.5 * mean * (1.0 + mean * mean / var)
    if b0 <= 0:
        return None

    def negll(p):
        xi, beta = float(p[0]), float(p[1])
        if beta <= 0 or xi <= -0.5:
            return 1e15
        t = 1.0 + xi * y / beta
        if (t <= 0).any():
            return 1e15
        if abs(xi) < 1e-8:
            return float(n * math.log(beta) + y.sum() / beta)
        return float(n * math.log(beta) + (1.0 + 1.0 / xi) * float(_np.log(t).sum()))

    try:
        res = minimize(negll, [xi0, b0], method="Nelder-Mead",
                       options={"maxiter": 2000, "xatol": 1e-8, "fatol": 1e-10})
        if res.success:
            xi, beta = float(res.x[0]), float(res.x[1])
        else:
            xi, beta = xi0, b0
    except Exception:  # noqa: BLE001 - no fabrication
        xi, beta = xi0, b0
    if not math.isfinite(xi) or not math.isfinite(beta) or beta <= 0:
        return None
    return xi, beta


def extreme_quantile_var(
    returns: list,
    alpha: float = 0.01,
    threshold_quantile: float = 0.90,
    min_exceed: int = 10,
) -> dict | None:
    """EVT extreme-quantile VaR / Expected Shortfall from a GPD tail fit.

    Peaks-over-threshold: take the loss series ``L = -returns``, set the
    threshold ``u`` at the ``threshold_quantile`` quantile of L, fit a GPD to
    the ``N_u`` exceedances, and read the extreme quantile
    ``VaR_p = u + (beta/xi)[(N_u/(N*p))^xi - 1]`` (``u + beta*ln(N_u/(N*p))``
    when ``xi = 0``) with the GPD Expected Shortfall
    ``ES_p = (VaR_p + beta - xi*u) / (1 - xi)`` (McNeil-Frey-Embrechts).

    VaR / ES are returned NEGATIVE (loss convention, matching ``simple_var`` /
    ``cvar``). Unlike the historical quantile, the GPD extrapolates beyond the
    observed worst day — a fat-tailed book reads a VaR beyond its sample
    maximum. Returns None when the series is too short, fewer than
    ``min_exceed`` exceedances fall above the threshold, or the fit is
    degenerate — never fabricated.
    """
    vals = [float(r) for r in returns if r is not None]
    n = len(vals)
    if n < 3 * min_exceed:
        return None
    alpha = float(alpha)
    q = float(threshold_quantile)
    if not 0.0 < alpha < 1.0 or not 0.5 < q < 1.0:
        return None
    losses = sorted(-v for v in vals)
    k = max(1, int(q * n))
    u = losses[k - 1]
    exceed = [e - u for e in losses if e > u]  # positive exceedances
    if len(exceed) < min_exceed:
        return None
    fit = _gpd_fit(exceed)
    if fit is None:
        return None
    xi, beta = fit
    if xi >= 1.0:
        return None
    nu = len(exceed)
    tail = nu / (n * alpha)
    if tail <= 0:
        return None
    var_pos = u + beta * math.log(tail) if abs(xi) < 1e-8 else u + (beta / xi) * (tail ** xi - 1.0)
    if not math.isfinite(var_pos) or var_pos <= u:
        return None
    es_pos = (var_pos + beta - xi * u) / (1.0 - xi)
    if not math.isfinite(es_pos) or es_pos < var_pos:
        return None
    return {
        "var": round(-var_pos, 6),
        "es": round(-es_pos, 6),
        "xi": round(xi, 6),
        "beta": round(beta, 6),
        "threshold": round(u, 6),
        "n_exceed": nu,
        "n": n,
        "alpha": alpha,
    }


# ---------------------------------------------------------------------------
# Minimum-CVaR sizing + copula scenarios (quants.md N5 / C4)
# ---------------------------------------------------------------------------


def _align_finite_series(returns_by_name: dict) -> tuple[list[str], list[list[float]], int]:
    """Usable names + finite return lists aligned to their common tail length.

    Non-finite/non-numeric points are dropped (never fabricated), each name
    needs at least two points, and every retained series is truncated to the
    shortest so ``returns_by_name`` may be ragged without raising.
    """
    usable: dict[str, list[float]] = {}
    for name, series in (returns_by_name or {}).items():
        vals: list[float] = []
        for v in series or []:
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if math.isfinite(f):
                vals.append(f)
        if len(vals) >= 2:
            usable[str(name)] = vals
    names = list(usable)
    if len(names) < 2:
        return [], [], 0
    t = min(len(v) for v in usable.values())
    return names, [usable[n][-t:] for n in names], t


def _project_box_simplex(v: list[float], lo: list[float], hi: list[float],
                         total: float = 1.0) -> list[float]:
    """Euclidean projection of ``v`` onto ``{sum=total, lo <= w <= hi}``.

    Bisection on the shift ``tau`` (``w_i = clip(v_i - tau, lo_i, hi_i)``,
    sum monotone decreasing in ``tau``) - deterministic, no RNG.
    """
    a = max(v[i] - hi[i] for i in range(len(v)))
    b = min(v[i] - lo[i] for i in range(len(v)))
    for _ in range(80):
        mid = 0.5 * (a + b)
        s = sum(min(hi[i], max(lo[i], v[i] - mid)) for i in range(len(v)))
        if s > total:
            a = mid
        else:
            b = mid
    tau = 0.5 * (a + b)
    return [min(hi[i], max(lo[i], v[i] - tau)) for i in range(len(v))]


def _min_cvar_fallback(y: list[list[float]], alpha: float, lo: list[float],
                       hi: list[float], iters: int = 3000) -> list[float]:
    """Deterministic projected subgradient solver for :func:`min_cvar_weights`.

    Used only when scipy is unavailable. Fixed start (the box/simplex
    projection of equal weight) and a decaying step ``0.5/sqrt(k+1)`` on the
    CVaR subgradient; no RNG, so reruns are identical.
    """
    k = len(y)
    t = len(y[0])
    share = 1.0 / ((1.0 - alpha) * t)
    w = _project_box_simplex([1.0 / k] * k, lo, hi)
    ktail = max(1, int(alpha * t))
    for it in range(iters):
        losses = sorted(-sum(y[i][s] * w[i] for i in range(k)) for s in range(t))
        zeta = losses[t - ktail]
        grad = [0.0] * k
        for s in range(t):
            loss = -sum(y[i][s] * w[i] for i in range(k))
            if loss > zeta:
                for i in range(k):
                    grad[i] -= y[i][s]
        step = 0.5 / math.sqrt(it + 1.0)
        w = _project_box_simplex(
            [w[i] - step * share * grad[i] for i in range(k)], lo, hi)
    return w


def _solve_min_cvar(y: list[list[float]], alpha: float, lo: list[float],
                    hi: list[float]) -> tuple[list[float] | None, str]:
    """Rockafellar-Uryasev sample-average LP, HiGHS when scipy is importable."""
    k = len(y)
    t = len(y[0])
    try:
        import numpy as np
        from scipy.optimize import linprog
    except ImportError:
        return _min_cvar_fallback(y, alpha, lo, hi), "projected subgradient fallback"
    # Variables: w (k), zeta, u_t (t). Constraint
    # u_t + sum_i r_it w_i + zeta >= 0  ->  -sum_i r_it w_i - zeta - u_t <= 0.
    c = np.zeros(k + 1 + t)
    c[k] = 1.0
    c[k + 1:] = 1.0 / ((1.0 - alpha) * t)
    a_ub = np.zeros((t, k + 1 + t))
    for s in range(t):
        for i in range(k):
            a_ub[s, i] = -y[i][s]
        a_ub[s, k] = -1.0
        a_ub[s, k + 1 + s] = -1.0
    a_eq = np.zeros((1, k + 1 + t))
    a_eq[0, :k] = 1.0
    bounds = [(lo[i], hi[i]) for i in range(k)] + [(None, None)] + [(0.0, None)] * t
    try:
        res = linprog(c, A_ub=a_ub, b_ub=np.zeros(t), A_eq=a_eq, b_eq=np.array([1.0]),
                      bounds=bounds, method="highs")
    except Exception:  # noqa: BLE001 - a solver failure must not fabricate weights
        return None, ""
    if not res.success or res.x is None:
        return None, ""
    return [float(x) for x in res.x[:k]], "scipy.optimize.linprog (HiGHS)"


def min_cvar_weights(
    returns_by_name: dict,
    alpha: float = 0.05,
    cap: float = 0.30,
    max_delta: float = 0.05,
    current: dict | None = None,
    min_scenarios: int = 60,
) -> dict | None:
    """Minimum-CVaR long-only sizing (Rockafellar-Uryasev sample-average LP).

    Solves ``min_{w,zeta} zeta + 1/((1-alpha)T) * sum_t max(L_t(w) - zeta, 0)``
    with ``L_t(w) = -sum_i w_i r_it``, fully invested (``sum_i w_i = 1``),
    long-only (``0 <= w_i <= cap``) and, when ``current`` is supplied, within
    ``max_delta`` of the current book.

    Returns ``{"weights", "cvar", "cdar", "binding", "n", "alpha", "basis"}``
    with ``cvar`` the resulting book CVaR as a **positive loss fraction** and
    ``binding`` naming the active constraint (``'cap'`` / ``'max_delta'`` /
    ``'unconstrained'`` / ``'min_cvar'``). Returns None - never fabricated
    weights - below the ``min_scenarios`` floor, with fewer than two usable
    series, when ``sum_i w_i = 1`` is infeasible under ``cap``/``max_delta``,
    or for ``cap <= 0`` / ``alpha`` outside (0, 1) / non-finite parameters.

    **Advisory sizing only**: these are numbers to reason about, never an
    order, ticket or trade instruction.
    """
    try:
        alpha = float(alpha)
        cap = float(cap)
        max_delta = float(max_delta)
        min_scenarios = int(min_scenarios)
    except (TypeError, ValueError):
        return None
    if not (0.0 < alpha < 1.0) or not math.isfinite(cap) or cap <= 0.0:
        return None
    if not math.isfinite(max_delta) or max_delta <= 0.0 or min_scenarios < 2:
        return None
    names, y, t = _align_finite_series(returns_by_name)
    if len(names) < 2 or t < min_scenarios:
        return None
    k = len(names)
    if cap * k < 1.0:
        return None  # sum_i w_i = 1 infeasible under the per-name cap
    lo = [0.0] * k
    hi = [cap] * k
    cur: list[float] | None = None
    if current is not None:
        if not isinstance(current, dict):
            return None
        try:
            cur = [float(current.get(name, 0.0)) for name in names]
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(c) for c in cur):
            return None
        lo = [max(0.0, cur[i] - max_delta) for i in range(k)]
        hi = [min(cap, cur[i] + max_delta) for i in range(k)]
        if any(lo[i] > hi[i] + 1e-12 for i in range(k)):
            return None
        if sum(lo) > 1.0 + 1e-9 or sum(hi) < 1.0 - 1e-9:
            return None
    wv, method = _solve_min_cvar(y, alpha, lo, hi)
    if wv is None:
        return None
    mixed = [sum(wv[i] * y[i][s] for i in range(k)) for s in range(t)]
    cv = cvar(mixed, alpha)
    if cv is None:
        return None
    eq = []
    acc = 1.0
    for r in mixed:
        acc *= 1.0 + r
        eq.append(acc)
    dd = cdar(eq, alpha)
    tol = 1e-6
    if any(wv[i] >= cap - tol for i in range(k)):
        binding = "cap"
    elif cur is not None and any(abs(wv[i] - cur[i]) >= max_delta - tol for i in range(k)):
        binding = "max_delta"
    elif cur is not None and all(abs(wv[i] - cur[i]) <= tol for i in range(k)):
        binding = "unconstrained"
    else:
        binding = "min_cvar"
    return {
        "weights": {names[i]: round(wv[i], 6) for i in range(k)},
        "cvar": round(-cv, 6),
        "cdar": round(dd["cdar"], 6) if dd else None,
        "binding": binding,
        "n": t,
        "alpha": alpha,
        "basis": (f"sample-average min-CVaR LP ({method}); T={t} aligned daily "
                  f"returns, alpha={alpha}, cap={cap}, max_delta={max_delta}"),
    }


def _copula_uniforms(mat, rng, fam: str, nu: int, k: int, n: int, t: int):
    """Simulated copula uniforms (n x k) for the requested family, or None."""
    import numpy as np

    if fam == "independent":
        return rng.random((n, k))
    ranks = (np.argsort(np.argsort(mat, axis=1), axis=1) + 1.0) / (t + 1.0)
    if fam == "clayton":
        try:
            from scipy.stats import kendalltau
        except ImportError:
            return None
        taus = []
        for i in range(k):
            for j in range(i + 1, k):
                tau = kendalltau(mat[i], mat[j]).statistic
                if tau is not None and math.isfinite(float(tau)):
                    taus.append(float(tau))
        tau = sum(taus) / len(taus) if taus else 0.0
        theta = 2.0 * tau / (1.0 - tau) if 0.0 < tau < 1.0 else 1e-4
        v = rng.gamma(1.0 / theta, 1.0, size=n)
        e = rng.exponential(1.0, size=(n, k))
        return (1.0 + e / v[:, None]) ** (-1.0 / theta)
    try:
        from scipy import stats
    except ImportError:
        return None
    z = stats.t.ppf(ranks, nu) if fam == "t" else stats.norm.ppf(ranks)
    corr = np.atleast_2d(np.corrcoef(z)) + np.eye(k) * 1e-8
    try:
        chol = np.linalg.cholesky(corr)
    except np.linalg.LinAlgError:
        vals, vecs = np.linalg.eigh(corr)
        chol = vecs @ np.diag(np.sqrt(np.clip(vals, 1e-10, None)))
    zs = rng.standard_normal((n, k)) @ chol.T
    if fam == "t":
        chi = rng.chisquare(nu, size=n)
        return stats.t.cdf(zs * np.sqrt(nu / chi)[:, None], nu)
    return stats.norm.cdf(zs)


def _tail_dependence(u, names: list[str], quantile: float) -> dict:
    """Empirical lower-tail dependence at ``quantile`` (per pair + aggregate)."""
    k = u.shape[1]
    pairs = {}
    vals = []
    for i in range(k):
        mask = u[:, i] <= quantile
        if not mask.any():
            continue
        for j in range(i + 1, k):
            v = float((u[mask, j] <= quantile).mean())
            pairs[f"{names[i]}|{names[j]}"] = round(v, 6)
            vals.append(v)
    return {
        "quantile": quantile,
        "aggregate": round(sum(vals) / len(vals), 6) if vals else None,
        "pairs": pairs,
    }


def copula_scenarios(
    returns_by_name: dict,
    n: int = 2000,
    nu: int = 5,
    family: str = "t",
    seed: int = 0,
) -> dict | None:
    """Joint daily scenario returns from an empirical-marginal copula.

    Fits each marginal **empirically** (the sorted return sample), fits a rank
    copula - Student-t (``family='t'``, dof ``nu``), Gaussian
    (``'gaussian'``), Clayton (``'clayton'``) or independence
    (``'independent'``) - and draws ``n`` joint daily scenarios remapped
    through the marginals. ``scenarios`` is a list of ``{name: daily_return}``
    rows (loss = ``-return``).

    ``tail_dependence`` reports the empirical lower-tail dependence at
    ``quantile=0.1``: ``aggregate`` = mean over name pairs of
    ``P(U_j <= q | U_i <= q)``, plus the per-pair values. A low-``nu`` t or
    Clayton copula on a dependent input reads well above the ``q`` (= 0.1)
    independence baseline; Gaussian / independent inputs sit at it.

    Deterministic for a given ``seed``. Returns None with fewer than two
    usable series or a common length below two - never fabricated scenarios.
    """
    try:
        n = int(n)
        nu = int(nu)
        seed = int(seed)
    except (TypeError, ValueError):
        return None
    fam = str(family).lower()
    if fam not in ("t", "gaussian", "clayton", "independent") or n < 1 or nu < 1:
        return None
    names, y, t = _align_finite_series(returns_by_name)
    if len(names) < 2 or t < 2:
        return None
    import numpy as np

    k = len(names)
    mat = np.array(y, dtype=float)
    rng = np.random.default_rng(seed)
    u = _copula_uniforms(mat, rng, fam, nu, k, n, t)
    if u is None:
        return None
    sorted_ret = [np.sort(row) for row in mat]
    cols = [np.quantile(sorted_ret[i], u[:, i]) for i in range(k)]
    scenarios = [
        {names[i]: float(cols[i][j]) for i in range(k)} for j in range(n)
    ]
    nu_out = nu if fam == "t" else None
    basis = (f"{fam}-copula on empirical marginals; T={t} aligned daily returns, "
             f"n={n} scenarios, seed={seed}")
    if nu_out is not None:
        basis += f", nu={nu_out}"
    return {
        "scenarios": scenarios,
        "family": fam,
        "nu": nu_out,
        "n": n,
        "tail_dependence": _tail_dependence(u, names, 0.1),
        "basis": basis,
    }


__all__ = ["simple_var", "cvar", "portfolio_cvar", "portfolio_returns", "stress_loss", "book_correlated_stress", "drawdown_gate",
           "cdar", "return_autocorrelation", "var_cvar_horizon", "incremental_var", "component_var", "extreme_quantile_var",
           "min_cvar_weights", "copula_scenarios"]
