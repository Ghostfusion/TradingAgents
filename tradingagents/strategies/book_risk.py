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


def normalize_book_weights(returns_by_name: dict, weights: dict | None = None) -> dict | None:
    """The book's weights under the cash-sleeve convention, or None.

    ONE implementation (ground rule 2): ``portfolio_cvar`` and
    ``book_correlated_stress`` each carried their own copy of these rules until
    2026-09-17 (P0-8d), so a change to the cash-sleeve convention could land in
    one path and silently miss the other. The rules:

    - weights summing to **1.0** -> the normalized relative book.
    - summing to **< 1.0** -> the RAW weights, so the remainder (1 - total) stays
      an implicit ZERO-RETURN CASH SLEEVE and dilutes the tail. This is how
      "include cash as overall portfolio" is honored.
    - summing to **> 1.0** (config error) -> normalized down to 1.0 to remain a
      valid portfolio.
    - no weights / all-zero -> equal weight across the provided names.

    Returns None below two names: a book needs two, and both callers treat that
    as "cannot be resolved" rather than inventing a sleeve.
    """
    names = list(returns_by_name or {})
    if len(names) < 2:
        return None
    w = weights or {}
    total = sum(float(w.get(n, 0.0) or 0.0) for n in names)
    if total <= 0:
        return dict.fromkeys(names, 1.0 / len(names))
    if total > 1.0:
        return {n: float(w.get(n, 0.0) or 0.0) / total for n in names}
    return {n: float(w.get(n, 0.0) or 0.0) for n in names}


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
    norm = normalize_book_weights(returns_by_name, weights)
    if norm is None:
        return None
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
    norm = normalize_book_weights(returns_by_name, weights)
    if norm is None:
        return None
    mixed = portfolio_returns(norm, returns_by_name)
    if not mixed:
        return None
    # tail loss: mean of the worst `shock`-fraction of weighted returns
    k = max(1, int(abs(float(shock)) * len(mixed)))
    worst = sorted(mixed)[:k]
    return -sum(worst) / len(worst) if worst else None


def net_beta(weights: dict, betas: dict) -> float | None:
    """Book net beta ``sum(w_i * beta_i)`` - the missing producer (RiskScore §3.3).

    ``weights`` is ``{name: weight}`` (the book's own weights, so a sum below
    1.0 leaves an implicit zero-beta cash sleeve) and ``betas`` is
    ``{name: beta}`` from a per-name producer such as ``etf_risk._beta:38``.
    The caller stores the result on the executor's ``BookState.net_beta`` - the
    field is ``None`` today and the dataclass is frozen, so it cannot be
    assigned after construction.

    ``NA`` is not ``0``: a name that carries weight but has no measured beta
    makes the book's beta **unknown**, so this returns ``None`` rather than a
    partial sum that would read as a flat book. An empty book is ``None`` too.
    """
    w = {n: float(v) for n, v in (weights or {}).items() if v is not None}
    weighted = {n: v for n, v in w.items() if v != 0.0}
    if not weighted:
        return None
    total = 0.0
    for name, weight in weighted.items():
        beta = (betas or {}).get(name)
        if beta is None:
            return None
        try:
            b = float(beta)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(b):
            return None
        total += weight * b
    return round(total, 6)


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


# The jump-share thresholds the tail read maps to a shape. They are thresholds
# on a PROXY (the V6 bipower proxy's share of the window's variance that no
# lag-1 cross-product carried), so they are named here rather than buried in a
# comparison: >= ONE_PRINT means more than half the window's variance arrived in
# jumps, <= DIFFUSE means at most a quarter did, anything between is `mixed`.
_ONE_PRINT_SHARE = 0.50
_DIFFUSE_SHARE = 0.25


def _jump_read(ohlc, config: dict | None) -> dict | None:
    """The V6 jump leg beside the EVT tail read, or None when it is gated off.

    The GPD fit above extrapolates a tail from the loss distribution; it says
    nothing about whether that tail arrived in ONE print. The bipower proxy
    answers that: a jump share near 1 means the tail is a jump (a single-print
    gap a variance level cannot separate from a diffusion), near 0 means the
    variance arrived diffusively. The quarticity proxy is reported beside it as
    the fourth-moment scale.

    Gated by ``enable_jump_robust_proxies`` (default off). With the gate off -
    or with no bars supplied - this returns None and the tail record is exactly
    what it was before V6, so a gate-off read is byte-identical.
    """
    if ohlc is None:
        return None
    from tradingagents.strategies.volatility_models import (
        bipower_proxy,
        jump_robust_proxies_enabled,
        quarticity_proxy,
    )

    if not jump_robust_proxies_enabled(config):
        return None
    bp = bipower_proxy(ohlc)
    rq = quarticity_proxy(ohlc)
    share = bp.get("jump_share_proxy")
    if share is None:
        return {
            "tail_shape": "unavailable",
            "jump_share_proxy": None,
            "bipower_proxy": None,
            "quarticity_proxy": None,
            "n": bp.get("n"),
            "basis": bp.get("basis"),
        }
    if share >= _ONE_PRINT_SHARE:
        shape = "one_print"
    elif share <= _DIFFUSE_SHARE:
        shape = "diffuse"
    else:
        shape = "mixed"
    return {
        "tail_shape": shape,
        "jump_share_proxy": share,
        "bipower_proxy": bp.get("bipower_proxy"),
        "quarticity_proxy": rq.get("quarticity_proxy"),
        "n": bp.get("n"),
        "basis": (
            f"{shape}: jump share {share:.4f} of the window's variance arrived in "
            f"returns no lag-1 cross-product carried (bipower proxy); quarticity "
            f"proxy {rq.get('quarticity_proxy')}; a PROXY read of one-print risk, "
            f"not a realized measure"
        ),
    }


def extreme_quantile_var(
    returns: list,
    alpha: float = 0.01,
    threshold_quantile: float = 0.90,
    min_exceed: int = 10,
    ohlc=None,
    config: dict | None = None,
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

    **The jump leg (V6).** A GPD tail fit reads how fat the tail is, never
    whether the tail arrived in ONE print — a single-print gap and a diffuse
    stretch of the same variance fit the same shape. Pass ``ohlc`` (the same
    bar window the returns came from, in either shape ``volatility_models``
    accepts) with the ``enable_jump_robust_proxies`` gate on and the record
    gains a ``"jump"`` leg: the bipower proxy's jump share, its quarticity
    proxy companion, and a ``tail_shape`` verdict (``one_print`` / ``mixed`` /
    ``diffuse``; ``unavailable`` - never a number - below the proxy floor).
    With the gate off or no bars supplied the record is byte-identical to the
    pre-V6 one.
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
    out = {
        "var": round(-var_pos, 6),
        "es": round(-es_pos, 6),
        "xi": round(xi, 6),
        "beta": round(beta, 6),
        "threshold": round(u, 6),
        "n_exceed": nu,
        "n": n,
        "alpha": alpha,
    }
    jump = _jump_read(ohlc, config)
    if jump is not None:
        out["jump"] = jump
    return out


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


# ---------------------------------------------------------------------------
# VaR coverage tests: Kupiec POF + Christoffersen joint conditional coverage
# (R2, 2606.23492 - the coverage test IS the deliverable)
# ---------------------------------------------------------------------------
#
# A VaR is a claim about a breach probability, and a claim is only usable when
# its breaches are consistent with it. Two classical tests are reported together:
#
#   * Kupiec (1995) proportion-of-failures: is the observed hit rate equal to
#     the stated tail probability? (two-sided: over- and under-coverage both
#     reject, because a VaR that never breaches is not thereby a good VaR).
#   * Christoffersen (1998) independence + joint conditional coverage: are the
#     hits i.i.d. through time, or do they cluster (a VaR that is silent until a
#     regime turns and then breaches in runs)? The joint statistic is the sum of
#     the POF and independence likelihood ratios, chi-square on 2 degrees of
#     freedom.
#
# The chi-square survival functions needed are closed form on 1 and 2 degrees of
# freedom (``erfc(sqrt(x/2))`` and ``exp(-x/2)``), so the test stays stdlib only -
# no scipy import, deterministic to the last bit.

#: Below this many held-out observations the coverage test cannot speak: a 5%
#: tail needs enough trials for a proportion to mean anything.
VAR_COVERAGE_MIN_N = 60

#: The p-value at or above which a VaR's breach behaviour is read as consistent
#: with its stated level (the conventional 5% test level).
VAR_COVERAGE_LEVEL = 0.05


def _chi2_sf(stat: float, df: int) -> float:
    """Chi-square survival ``P(X > stat)`` for ``df`` in {1, 2} (closed form)."""
    if stat is None or not math.isfinite(float(stat)) or float(stat) <= 0.0:
        return 1.0
    x = float(stat)
    if df == 1:
        return math.erfc(math.sqrt(x / 2.0))
    if df == 2:
        return math.exp(-x / 2.0)
    raise ValueError(f"only df 1 and 2 are closed form here, got {df!r}")


def _kupiec_pof(n: int, hits: int, p: float) -> tuple[float | None, float | None]:
    """``(LR_pof, p_value)``: the proportion-of-failures likelihood ratio.

    The null is ``hit rate = p``. ``0**0`` is taken as 1 (the boundary cases
    ``hits == 0`` and ``hits == n`` are handled explicitly), so a VaR that never
    (or always) breaches still yields a finite statistic - and a rejection.
    """
    if n <= 0 or not 0.0 < p < 1.0:
        return None, None
    if hits <= 0:
        ln_null, ln_alt = n * math.log(1.0 - p), 0.0
    elif hits >= n:
        ln_null, ln_alt = n * math.log(p), 0.0
    else:
        pi = hits / n
        ln_null = (n - hits) * math.log(1.0 - p) + hits * math.log(p)
        ln_alt = (n - hits) * math.log(1.0 - pi) + hits * math.log(pi)
    lr = -2.0 * (ln_null - ln_alt)
    return lr, _chi2_sf(lr, 1)


def _christoffersen_independence(
    n00: int, n01: int, n10: int, n11: int
) -> tuple[float | None, float | None]:
    """``(LR_ind, p_value)``: are the breaches i.i.d. through time?

    First-order Markov chain on the hit sequence: ``pi01 = P(hit | no hit)``,
    ``pi11 = P(hit | hit)``. Independence is ``pi01 = pi11``. Returns
    ``(None, None)`` when the chain has no transitions to test (all-hit or
    all-quiet), where the statistic is not defined - never a fabricated pass.
    """
    n0, n1 = n00 + n01, n10 + n11
    total = n0 + n1
    if n0 == 0 or n1 == 0 or total == 0:
        return None, None
    pi01 = n01 / n0
    pi11 = n11 / n1
    pi = (n01 + n11) / total

    def _ll(prob: float, k: int, m: int) -> float | None:
        if k < 0 or m < 0:
            return None
        if k == 0 and m == 0:
            return 0.0
        if prob <= 0.0 or prob >= 1.0:
            # a boundary MLE makes the log-likelihood finite only when the
            # corresponding count is zero (0*log(0) := 0)
            if prob <= 0.0 and k == 0:
                return m * math.log(1.0)
            if prob >= 1.0 and m == 0:
                return k * math.log(1.0)
            return None
        return k * math.log(prob) + m * math.log(1.0 - prob)

    ln_null = _ll(pi, n01 + n11, n00 + n10)
    a = _ll(pi01, n01, n00)
    b = _ll(pi11, n11, n10)
    if ln_null is None or a is None or b is None:
        return None, None
    lr = -2.0 * (ln_null - (a + b))
    return lr, _chi2_sf(lr, 1)


def var_coverage_test(
    returns: list,
    *,
    alpha: float = 0.05,
    var_series: list | None = None,
    min_window: int = VAR_COVERAGE_MIN_N,
) -> dict:
    """Kupiec + Christoffersen joint conditional coverage of a VaR series (R2).

    ``returns`` are the **held-out** realized returns; ``var_series`` is the
    predicted VaR aligned to them (negative = loss, ``simple_var``'s convention)
    - typically the regime-conditional VaR from
    ``regime.regime_conditional_var``, which is what this instrument exists to
    test. When ``var_series`` is omitted an expanding-window historical VaR is
    built from strictly-past returns (``simple_var``), so the test is usable
    standalone; the provenance is named in ``basis`` either way.

    A breach is ``return < VaR``. Returns
    ``{"kupiec": {...}, "christoffersen": {...}, "verdict", "n", "window",
    "coverage_level", "basis"}``. ``verdict`` is ``pass`` / ``fail`` at
    ``VAR_COVERAGE_LEVEL`` on the joint statistic (falling back to the POF
    statistic when the hit sequence has no transitions to test), or the
    ``unavailable`` refusal when the held-out window is thinner than
    ``min_window`` - never a fabricated pass.
    """
    rets = [float(r) for r in (returns or []) if r is not None]
    n_rets = len(rets)
    try:
        a = float(alpha)
        floor = int(min_window)
    except (TypeError, ValueError):
        a, floor = 0.05, VAR_COVERAGE_MIN_N
    window = {
        "held_out": n_rets,
        "var_points": len(var_series) if var_series is not None else 0,
        "n": 0,
        "min_window": floor,
        "first": None,
        "last": None,
    }
    if not 0.0 < a < 1.0:
        return _coverage_refusal(
            f"alpha={alpha!r} is outside (0, 1): a tail probability is not a level",
            window, a,
        )
    if var_series is None:
        burn = max(30, floor // 2)
        vs: list = [None] * n_rets
        for t in range(burn, n_rets):
            vs[t] = simple_var(rets[:t], a)
        source = (
            f"expanding-window historical VaR (simple_var over strictly-past "
            f"returns, {burn}-bar burn-in)"
        )
    else:
        vs = list(var_series)
        source = "supplied VaR series"
    n = min(n_rets, len(vs))
    window["n"] = n
    usable = [t for t in range(n) if vs[t] is not None]
    if n < floor or len(usable) < floor:
        return _coverage_refusal(
            f"held-out window of {len(usable)} usable observation(s) is below the "
            f"{floor}-observation floor: a tail proportion is not measurable here "
            f"(master rule 1 - missing data is unavailable, never zero)",
            window, a,
        )
    window["first"] = usable[0]
    window["last"] = usable[-1]
    hits = [1 if rets[t] < float(vs[t]) else 0 for t in usable]
    x = sum(hits)
    lr_pof, p_pof = _kupiec_pof(len(hits), x, a)
    n00 = n01 = n10 = n11 = 0
    for i in range(1, len(hits)):
        prev, cur = hits[i - 1], hits[i]
        if prev == 0 and cur == 0:
            n00 += 1
        elif prev == 0 and cur == 1:
            n01 += 1
        elif prev == 1 and cur == 0:
            n10 += 1
        else:
            n11 += 1
    lr_ind, p_ind = _christoffersen_independence(n00, n01, n10, n11)
    joint_stat = joint_p = None
    if lr_pof is not None and lr_ind is not None:
        joint_stat = lr_pof + lr_ind
        joint_p = _chi2_sf(joint_stat, 2)
    if joint_p is not None:
        verdict = "pass" if joint_p >= VAR_COVERAGE_LEVEL else "fail"
        judged_on = "christoffersen joint conditional coverage (LR_cc ~ chi2_2)"
    elif p_pof is not None:
        verdict = "pass" if p_pof >= VAR_COVERAGE_LEVEL else "fail"
        judged_on = "kupiec POF (no transitions to test independence)"
    else:
        verdict = "unavailable"
        judged_on = "nothing"
    return {
        "kupiec": {
            "stat": lr_pof,
            "p_value": p_pof,
            "n": len(hits),
            "hits": x,
            "hit_rate": x / len(hits),
            "expected": a,
            "level": VAR_COVERAGE_LEVEL,
        },
        "christoffersen": {
            "stat": lr_ind,
            "p_value": p_ind,
            "joint_stat": joint_stat,
            "joint_p_value": joint_p,
            "n00": n00,
            "n01": n01,
            "n10": n10,
            "n11": n11,
        },
        "verdict": verdict,
        "judged_on": judged_on,
        "n": len(hits),
        "coverage_level": round(1.0 - a, 6),
        "window": window,
        "basis": (
            f"VaR coverage test on {len(hits)} held-out observation(s) "
            f"(window [{usable[0]}, {usable[-1]}]): {x} breach(es) at the "
            f"{(1.0 - a):.1%} VaR (expected {a:.1%}); {source}; verdict {verdict} "
            f"on {judged_on}"
        ),
    }


def _coverage_refusal(reason: str, window: dict, alpha: float) -> dict:
    """The refusal record: no verdict, the reason, and the window it was asked on."""
    return {
        "kupiec": {"stat": None, "p_value": None, "n": 0, "hits": 0,
                   "hit_rate": None, "expected": alpha, "level": VAR_COVERAGE_LEVEL},
        "christoffersen": {"stat": None, "p_value": None, "joint_stat": None,
                           "joint_p_value": None, "n00": 0, "n01": 0, "n10": 0,
                           "n11": 0},
        "verdict": "unavailable",
        "judged_on": "nothing",
        "n": 0,
        "coverage_level": round(1.0 - alpha, 6),
        "window": window,
        "basis": reason,
    }


def _regime_var_coverage(
    returns: list,
    posteriors: list,
    emissions: dict,
    *,
    q: float = 0.05,
    min_window: int = VAR_COVERAGE_MIN_N,
) -> dict:
    """R2's VaR consumer: regime-conditional VaR handed to the coverage test.

    ``regime.regime_conditional_var`` builds the mixture quantile from the
    running state posterior and each state's CDF; this aligns it to the
    held-out returns and runs :func:`var_coverage_test` at the same tail
    probability. A VaR without a coverage test is a number, so this is the only
    form in which the regime VaR is reported. The public instrument R2 shares
    with K1 is :func:`var_coverage_test` itself.
    """
    from tradingagents.strategies.regime import regime_conditional_var

    var_series = regime_conditional_var(posteriors, emissions, q)
    out = var_coverage_test(returns, alpha=float(q), var_series=var_series,
                            min_window=min_window)
    out["var_series"] = var_series
    out["q"] = float(q)
    return out


# ---------------------------------------------------------------------------
# K2 - four drawdown expectations and the right time-scaling (2608.00127)
# ---------------------------------------------------------------------------
#
# The engine measures the drawdown that HAPPENED (``evaluate.max_drawdown``,
# ``book_risk.drawdown_gate``); it cannot say how deep or how long a drawdown at
# a given Sharpe should run. This computes the four expectations the paper
# separates - maximum drawdown, maximum loss, time under water and longest
# recovery - as a Monte-Carlo table over standardized higher moments, so a
# book's own skewness and kurtosis move them independently (no single Gaussian
# table reproduces all four).
#
# The paper's corrected scaling: under long memory the apparent amplification of
# drawdown risk is, for maximum-drawdown depth, almost entirely self-similar
# dispersion scaling ``T^(H - 1/2)`` rather than path geometry. So the depth
# measures are rescaled by exactly that factor when a Hurst estimate exists; with
# no Hurst estimate the square-root-of-time convention is used and the record
# says ``hurst: "assumed"``. Duration measures keep the horizon's own
# convention - the paper's closed form is about depth.
#
# REPORT-ONLY. Nothing here is wired into ``risk_governor`` / ``govern`` /
# ``drawdown_gate``: the mandate answer on letting the ``T^(H-1/2)`` rescaling
# reach the governor is still open, so the envelope is reported beside the
# realized ``max_drawdown`` it is meant to be read with.

#: Monte-Carlo paths per envelope (reduced automatically as the horizon grows;
#: the total work is bounded so the read stays cheap inside an evaluation loop).
DRAWDOWN_ENVELOPE_PATHS = 2000

#: Fixed seed: the envelope must be identical across runs (it is a table, not a
#: draw), so a published expectation does not move between two reads of the same
#: book.
DRAWDOWN_ENVELOPE_SEED = 20260924

#: Per-read work ceiling: ``paths * horizon`` never exceeds this.
DRAWDOWN_ENVELOPE_CELLS = 2_000_000


def _sharpe_uncertainty(sharpe: float, n: int) -> dict:
    """The Sharpe's estimation uncertainty (Lo 2002), reported with the envelope.

    ``SE(SR) = sqrt((1 + SR^2 / 2) / n)`` for ``n`` independent observations.
    The paper's own point is that Sharpe-*estimation* uncertainty changes the
    drawdown answer, so the envelope may never be printed without it.
    """
    se = math.sqrt((1.0 + 0.5 * float(sharpe) ** 2) / max(1, int(n)))
    return {
        "se": se,
        "n": int(n),
        "ci95": [float(sharpe) - 1.959964 * se, float(sharpe) + 1.959964 * se],
        "method": "Lo (2002) SE(SR) = sqrt((1 + SR^2 / 2) / n)",
    }


def drawdown_envelope(
    sharpe: float,
    horizon: int,
    skew: float | None = None,
    kurtosis: float | None = None,
    hurst: float | None = None,
    *,
    n_paths: int = DRAWDOWN_ENVELOPE_PATHS,
    seed: int = DRAWDOWN_ENVELOPE_SEED,
    periods_per_year: float = 252.0,
) -> dict:
    """Four drawdown expectations for a Sharpe over ``horizon`` periods (K2).

    Simulates standardized returns at the given annualized ``sharpe`` (a
    Cornish-Fisher draw matched to ``skew`` and ``kurtosis``; the location and
    scale are carried in units of the book's own annualized volatility, so no
    volatility parameter is needed) and reads four separate measures:

    - ``mdd_median`` / ``mdd_p90``: maximum peak-to-trough drawdown.
    - ``max_loss``: worst cumulative shortfall from the starting capital.
    - ``time_under_water``: fraction of the horizon below the running peak.
    - ``longest_recovery``: longest consecutive underwater run, in periods.

    The ``p90`` of each duration/depth measure is the headline (a conservative
    expectation). Depth measures are rescaled by ``horizon ** (hurst - 1/2)``
    when a Hurst estimate is supplied - without one the square-root-of-time
    convention is used and ``hurst`` reads ``"assumed"``. The Sharpe's
    estimation uncertainty (``sharpe_uncertainty``) is always reported when a
    Sharpe is. Deterministic for a given ``seed``; ``status`` is ``ok`` or the
    ``unavailable`` refusal when the Sharpe is missing/non-finite.
    """
    try:
        T = int(horizon)
    except (TypeError, ValueError):
        T = 0
    h_ok = sharpe is not None and math.isfinite(float(sharpe))
    if T < 2 or not h_ok:
        return {
            "status": "unavailable",
            "mdd_median": None, "mdd_p90": None, "max_loss": None,
            "time_under_water": None, "longest_recovery": None,
            "hurst": hurst if hurst is not None else "assumed",
            "hurst_exponent": None, "hurst_scale": None,
            "sharpe_uncertainty": None,
            "horizon": T if T >= 0 else None,
            "basis": (
                "drawdown envelope unavailable: "
                + ("horizon < 2 periods" if T < 2 else "no finite Sharpe supplied")
                + " (master rule 1 - no number is invented for an unmeasured input)"
            ),
        }
    import numpy as np

    S = float(sharpe)
    mu_p = S / float(periods_per_year)
    sig_p = 1.0 / math.sqrt(float(periods_per_year))
    g1 = float(skew) if (skew is not None and math.isfinite(float(skew))) else 0.0
    g2 = (float(kurtosis) - 3.0
          if (kurtosis is not None and math.isfinite(float(kurtosis))) else 0.0)
    paths = max(200, min(int(n_paths), max(1, DRAWDOWN_ENVELOPE_CELLS // T)))
    rng = np.random.default_rng(int(seed))
    z = rng.standard_normal((paths, T))
    # Cornish-Fisher expansion to the requested skew / excess kurtosis.
    z = (z + (g1 / 6.0) * (z * z - 1.0) + (g2 / 24.0) * (z ** 3 - 3.0 * z)
         - (g1 * g1 / 36.0) * (2.0 * z ** 3 - 5.0 * z))
    eq = np.cumprod(1.0 + mu_p + sig_p * z, axis=1)
    peak = np.maximum.accumulate(eq, axis=1)
    dd = (peak - eq) / peak
    mdd = dd.max(axis=1)
    loss = (1.0 - eq).max(axis=1)
    under = (eq < peak).astype(float)
    tuw = under.mean(axis=1)
    run = np.zeros(len(eq))
    longest = np.zeros(len(eq))
    for t in range(T):
        run = np.where(under[:, t] > 0.0, run + 1.0, 0.0)
        longest = np.maximum(longest, run)
    h_val = (float(hurst)
             if (hurst is not None and math.isfinite(float(hurst))) else None)
    exponent = 0.0 if h_val is None else (h_val - 0.5)
    scale = 1.0 if h_val is None else float(T) ** exponent
    return {
        "status": "ok",
        "mdd_median": float(np.median(mdd)) * scale,
        "mdd_p90": float(np.quantile(mdd, 0.9)) * scale,
        "max_loss": float(np.quantile(loss, 0.9)) * scale,
        "time_under_water": float(np.quantile(tuw, 0.9)),
        "time_under_water_median": float(np.median(tuw)),
        "longest_recovery": float(np.quantile(longest, 0.9)),
        "longest_recovery_median": float(np.median(longest)),
        "hurst": h_val if h_val is not None else "assumed",
        "hurst_exponent": exponent,
        "hurst_scale": scale,
        "sharpe_uncertainty": _sharpe_uncertainty(S, T),
        "horizon": T,
        "paths": paths,
        "seed": int(seed),
        "periods_per_year": float(periods_per_year),
        "basis": (
            f"drawdown envelope (2608.00127): {paths} Monte-Carlo path(s) over "
            f"T={T} period(s) at annualized Sharpe {S:.4g} and unit annualized "
            f"volatility, standardized skew {g1:.3g} / excess kurtosis {g2:.3g}; "
            f"depth measures rescaled by T^(H-1/2) = {scale:.6g} "
            + (f"(H={h_val:.4g} measured)" if h_val is not None
               else "(H assumed 0.5: the square-root-of-time convention)")
            + "; durations keep the horizon's own convention; REPORT-ONLY - the "
            "rescaling is deliberately not wired into any governor"
        ),
    }


__all__ = ["simple_var", "cvar", "normalize_book_weights", "portfolio_cvar", "portfolio_returns", "stress_loss", "book_correlated_stress", "net_beta", "drawdown_gate",
           "cdar", "return_autocorrelation", "var_cvar_horizon", "incremental_var", "component_var", "extreme_quantile_var",
           "min_cvar_weights", "copula_scenarios",
           "var_coverage_test", "VAR_COVERAGE_MIN_N", "VAR_COVERAGE_LEVEL",
           "drawdown_envelope"]
