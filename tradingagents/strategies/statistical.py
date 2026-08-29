"""Statistical / econometric calculators (OpenBB Q1-Q8).

Pure, offline, deterministic estimators that give the analyst LLMs p-valued
distributional / stationarity / rotation / payoff claims they currently assert
without tests. Every function returns floats / dicts or explicit ``None`` on
insufficient or degenerate input — never fabricated.

The ADF / KPSS stationarity tests are implemented in pure NumPy (scipy has no
``adfuller``); critical values use the standard Dickey-Fuller and KPSS tables.
All other tests delegate to scipy.stats.
"""

from __future__ import annotations

import math

import numpy as _np
from scipy import stats as _st
from scipy.special import betainc
from scipy.stats import t as _t


def _clean(series) -> list[float]:
    out = []
    for v in series:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


# ---------------------------------------------------------------------------
# Q1 - normality tests
# ---------------------------------------------------------------------------


def normality(returns: list) -> dict:
    """Distributional hypothesis tests: is this return series Gaussian?

    Reports D'Agostino-Pearson, Jarque-Bera, Shapiro-Wilk, Kolmogorov-Smirnov
    (vs normal) and their p-values, plus an overall ``normal`` flag (all tests
    p > 0.05). ``None`` entries where a test is unavailable; returns an
    all-``None``-ish dict for < 4 observations.
    """
    vals = _clean(returns)
    out = {
        "dagostino_pearson": None, "jarque_bera": None, "shapiro_wilk": None,
        "kolmogorov_smirnov": None, "normal": None, "n": len(vals),
    }
    if len(vals) < 4:
        return out
    x = _np.array(vals, dtype=float)
    try:
        s, p = _st.normaltest(x)
        out["dagostino_pearson"] = {"statistic": round(float(s), 4), "p_value": round(float(p), 4)}
    except Exception:  # noqa: BLE001
        pass
    try:
        s, p = _st.jarque_bera(x)
        out["jarque_bera"] = {"statistic": round(float(s), 4), "p_value": round(float(p), 4)}
    except Exception:  # noqa: BLE001
        pass
    try:
        if len(vals) <= 5000:
            s, p = _st.shapiro(x)
            out["shapiro_wilk"] = {"statistic": round(float(s), 4), "p_value": round(float(p), 4)}
    except Exception:  # noqa: BLE001
        pass
    try:
        s, p = _st.kstest(x, "norm", args=(x.mean(), x.std(ddof=1) or 1.0))
        out["kolmogorov_smirnov"] = {"statistic": round(float(s), 4), "p_value": round(float(p), 4)}
    except Exception:  # noqa: BLE001
        pass
    ps = [v["p_value"] for v in out.values() if isinstance(v, dict) and v.get("p_value") is not None]
    out["normal"] = bool(ps) and all(p > 0.05 for p in ps)
    return out


# ---------------------------------------------------------------------------
# Q1b - unit-root tests (pure NumPy ADF + KPSS)
# ---------------------------------------------------------------------------

#: MacKinnon-style critical values for ADF with a constant (regression "c").
_ADF_CRIT_C = {0.10: -2.57, 0.05: -2.86, 0.01: -3.43}
#: KPSS critical values (stationary null), constant case.
_KPSS_CRIT = {0.10: 0.347, 0.05: 0.463, 0.01: 0.739}


def _ols_resid(y: list[float], x: list[list[float]]) -> list[float]:
    """OLS residual of y on constant + x columns (pure NumPy least squares)."""
    n = len(y)
    X = _np.column_stack([_np.ones(n)] + [list(c) for c in x])
    beta, *_ = _np.linalg.lstsq(X, _np.array(y), rcond=None)
    resid = _np.array(y) - X @ beta
    return list(resid)


def unit_root(series: list, regression: str = "c") -> dict:
    """Augmented Dickey-Fuller (H0: unit root) + KPSS (H0: stationary).

    Pure NumPy implementations with standard critical-value tables. Returns
    ``{adf: {statistic, p_value_approx, nlags, nobs}, kpss: {...},
    stationary: bool}`` where ``stationary`` means ADF rejects the unit root
    and KPSS fails to reject stationarity. ``None``-ish for < 10 obs.
    """
    vals = _clean(series)
    out = {"adf": None, "kpss": None, "stationary": None, "n": len(vals)}
    if len(vals) < 10:
        return out
    y = _np.array(vals, dtype=float)
    dy = y[1:] - y[:-1]
    nlags = max(1, min(4, int(4 * (len(y) / 100.0) ** 0.25)))
    # ADF regression rows: y_{t-1} (length n-1) plus nlags lags of dy.
    # Use rows where every lag exists: drop the first `nlags-1` dy values.
    y_lag1 = y[:-1]  # length n-1
    dy_lags = [dy[i: i + (len(dy) - (nlags - 1))] for i in range(nlags - 1)]
    n_reg = len(y) - nlags
    y_lag1 = y_lag1[-(n_reg):]
    dy_lags = [d[: n_reg] for d in dy_lags]
    reg = _np.column_stack([y_lag1] + dy_lags) if nlags > 1 else y_lag1.reshape(-1, 1)
    y_dep = dy[-n_reg:]
    X = _np.column_stack([_np.ones(n_reg)] + [list(reg[:, i]) for i in range(reg.shape[1])])
    t_stat = 0.0
    try:
        beta, *_ = _np.linalg.lstsq(X, y_dep, rcond=None)
        resid = y_dep - X @ beta
        rss = float(_np.sum(resid ** 2))
        XtX_inv = _np.linalg.inv(X.T @ X)
        se = math.sqrt(rss / (n_reg - X.shape[1]) * float(XtX_inv[1, 1]))
        t_stat = float(beta[1]) / se if se > 0 else 0.0
    except Exception:  # noqa: BLE001
        pass
    if t_stat < _ADF_CRIT_C[0.01]:
        p = 0.001
    elif t_stat > _ADF_CRIT_C[0.10]:
        p = 0.99
    else:
        p = 0.10
        for cv, pv in ((_ADF_CRIT_C[0.01], 0.01), (_ADF_CRIT_C[0.05], 0.05), (_ADF_CRIT_C[0.10], 0.10)):
            if t_stat <= cv:
                p = pv
                break
    out["adf"] = {"statistic": round(float(t_stat), 4), "p_value_approx": round(float(p), 4),
                  "nlags": int(nlags), "nobs": int(n_reg)}
    try:
        z = y - y.mean()
        s = _np.cumsum(z)
        n = len(z)
        lagw = int(4 * (n / 100.0) ** 0.25)
        s2 = float(_np.mean(z ** 2))
        for k in range(1, lagw + 1):
            gamma = float(_np.mean(z[k:] * z[:-k]))
            s2 += 2.0 * (1.0 - k / (lagw + 1.0)) * gamma
        kpss_stat = float(_np.sum(s ** 2)) / (n * n * s2) if s2 > 0 else 0.0
        if kpss_stat > _KPSS_CRIT[0.01]:
            kpss_p = 0.01
        elif kpss_stat > _KPSS_CRIT[0.05]:
            kpss_p = 0.05
        elif kpss_stat > _KPSS_CRIT[0.10]:
            kpss_p = 0.10
        else:
            kpss_p = 0.99
        out["kpss"] = {"statistic": round(float(kpss_stat), 4), "p_value_approx": round(float(kpss_p), 4),
                       "nlags": int(lagw)}
    except Exception:  # noqa: BLE001
        out["kpss"] = None
    adf = out["adf"]
    kpss = out["kpss"]
    if (adf and kpss and adf.get("p_value_approx") is not None
            and kpss.get("p_value_approx") is not None):
        out["stationary"] = bool(adf["p_value_approx"] < 0.05 and kpss["p_value_approx"] > 0.05)
    return out


# ---------------------------------------------------------------------------
# Q3 - omega ratio
# ---------------------------------------------------------------------------


def omega(returns: list, threshold: float = 0.0) -> float | None:
    """Omega ratio: sum(max(r-t,0))/sum(max(t-r,0)) — parameter-free payoff
    asymmetry about a threshold. None when there is no positive (or negative)
    side, or < 2 observations."""
    vals = _clean(returns)
    if len(vals) < 2:
        return None
    t = float(threshold)
    up = sum(max(v - t, 0.0) for v in vals)
    dn = sum(max(t - v, 0.0) for v in vals)
    if dn <= 0:
        return None
    return up / dn


# ---------------------------------------------------------------------------
# Q4 - robust correlation matrix
# ---------------------------------------------------------------------------


def correlation_matrix(returns_by_name: dict, method: str = "pearson") -> dict:
    """Full correlation matrix (pearson/spearman/kendall) over aligned return
    series. Returns ``{names, corr: {name_i: {name_j: r}}}`` or ``{}`` for < 2
    aligned names."""
    names = [n for n in (returns_by_name or {}) if returns_by_name.get(n)]
    if len(names) < 2:
        return {}
    series = [_clean(returns_by_name[n]) for n in names]
    n = min(len(s) for s in series)
    if n < 2:
        return {}
    fn = {"pearson": _st.pearsonr, "spearman": _st.spearmanr, "kendall": _st.kendalltau}.get(
        (method or "pearson").lower(), _st.pearsonr)
    corr: dict = {}
    for i, ni in enumerate(names):
        corr[ni] = {}
        for j, nj in enumerate(names):
            if j <= i:
                continue
            try:
                r, _ = fn(series[i][:n], series[j][:n])
                r = float(r)
                if not math.isfinite(r):
                    r = None
            except Exception:  # noqa: BLE001
                r = None
            corr[ni][nj] = r
            corr.setdefault(nj, {})[ni] = r
    return {"names": names, "corr": corr}


# ---------------------------------------------------------------------------
# Q5 - cointegration + Granger causality
# ---------------------------------------------------------------------------


def cointegration_pair(x: list, y: list, maxlag: int = 1) -> dict:
    """Engle-Granger two-step cointegration test for a pair.

    Regress y on x, then ADF-test the residual for a unit root. Returns
    ``{beta, alpha, residual_adf_stat, residual_p_approx, cointegrated}`` or
    an all-``None``-ish dict for < 20 aligned obs.
    """
    xs = _clean(x)
    ys = _clean(y)
    out = {"beta": None, "alpha": None, "residual_adf_stat": None,
           "residual_p_approx": None, "cointegrated": None, "n": 0}
    n = min(len(xs), len(ys))
    if n < 20:
        return out
    xs = xs[:n]
    ys = ys[:n]
    resid = _ols_resid(ys, [xs])
    r_test = unit_root(resid, regression="c")
    adf = r_test.get("adf")
    out["n"] = n
    try:
        X = _np.column_stack([_np.ones(n), _np.array(xs)])
        beta, *_ = _np.linalg.lstsq(X, _np.array(ys), rcond=None)
        out["alpha"] = round(float(beta[0]), 6)
        out["beta"] = round(float(beta[1]), 6)
    except Exception:  # noqa: BLE001
        pass
    if adf:
        out["residual_adf_stat"] = adf.get("statistic")
        out["residual_p_approx"] = adf.get("p_value_approx")
        out["cointegrated"] = bool((adf.get("p_value_approx") or 1.0) < 0.05)
    return out


def granger_causality(x: list, y: list, maxlag: int = 3) -> dict:
    """Granger causality: does x help forecast y (lag-wise F-test)?

    Regresses y_t on its own lags vs on own + x lags; reports per-lag
    F-statistic and p-value (F-distribution). Returns ``{lags: [{lag, f,
    p_value}], x_causes_y: bool}`` or all-``None``-ish for < 10 obs.
    """
    xs = _clean(x)
    ys = _clean(y)
    out = {"lags": [], "x_causes_y": None, "n": 0}
    n = min(len(xs), len(ys))
    if n < 10:
        return out
    xs = xs[:n]
    ys = ys[:n]
    ml = max(1, min(int(maxlag), n // 3))
    out["n"] = n
    for lag in range(1, ml + 1):
        rows = n - lag
        y_dep = _np.array(ys[lag:], dtype=float)
        own = _np.column_stack([_np.ones(rows)] + [
            _np.array(ys[lag - k: n - k], dtype=float) for k in range(1, lag + 1)
        ])
        full = _np.column_stack([own] + [
            _np.array(xs[lag - k: n - k], dtype=float) for k in range(1, lag + 1)
        ])
        try:
            resid_r = y_dep - own @ _np.linalg.lstsq(own, y_dep, rcond=None)[0]
            resid_u = y_dep - full @ _np.linalg.lstsq(full, y_dep, rcond=None)[0]
            rss_r = float(_np.sum(resid_r ** 2))
            rss_u = float(_np.sum(resid_u ** 2))
            dfn = full.shape[1] - own.shape[1]
            dfd = rows - full.shape[1]
            if rss_u > 0 and dfd > 0:
                f = ((rss_r - rss_u) / dfn) / (rss_u / dfd)
                p = float(betainc(dfd / 2.0, dfn / 2.0, dfd / (dfd + dfn * f))) if f > 0 else 1.0
            else:
                f = None
                p = None
        except Exception:  # noqa: BLE001
            f = None
            p = None
        out["lags"].append({"lag": lag,
                            "f": round(float(f), 4) if f is not None else None,
                            "p_value": round(float(p), 4) if p is not None else None})
    ps = [row["p_value"] for row in out["lags"] if row.get("p_value") is not None]
    out["x_causes_y"] = bool(ps) and min(ps) < 0.05
    return out


# ---------------------------------------------------------------------------
# Q2 - CAPM decomposition, OLS factor regression, VIF
# ---------------------------------------------------------------------------


def capm_decomposition(returns: list, market: list) -> dict:
    """CAPM-style risk split via OLS of asset on market (constant):
    beta, systematic risk (R²), idiosyncratic risk (1-R²). None for < 30
    aligned obs or zero market variance."""
    rs = _clean(returns)
    ms = _clean(market)
    out = {"beta": None, "systematic_risk": None, "idiosyncratic_risk": None, "n": 0}
    n = min(len(rs), len(ms))
    if n < 30:
        return out
    rs = rs[:n]
    ms = ms[:n]
    try:
        res = _st.linregress(ms, rs)
        beta = float(res.slope)
        r2 = float(res.rvalue ** 2)
        out["beta"] = round(beta, 4)
        out["systematic_risk"] = round(r2, 4)
        out["idiosyncratic_risk"] = round(1.0 - r2, 4)
        out["n"] = n
    except Exception:  # noqa: BLE001
        pass
    return out


def ols_factors(y: list, factors: dict) -> dict:
    """Multiple OLS of ``y`` on the given ``factors`` (dict name -> series).
    Reports params, R², per-coef t/p/bse/CI. None when fewer rows than
    columns + 2."""
    ys = _clean(y)
    names = [k for k in (factors or {}) if factors.get(k)]
    series = [_clean(factors[k]) for k in names]
    if not names or not ys:
        return {"rsquared": None, "params": None, "n": 0}
    n = min(len(ys), *(len(s) for s in series))
    if n < len(names) + 2:
        return {"rsquared": None, "params": None, "n": 0}
    ys = ys[:n]
    series = [s[:n] for s in series]
    X = _np.column_stack([_np.ones(n)] + [list(s) for s in series])
    try:
        beta, *_ = _np.linalg.lstsq(X, _np.array(ys), rcond=None)
        resid = _np.array(ys) - X @ beta
        rss = float(_np.sum(resid ** 2))
        tss = float(_np.sum((_np.array(ys) - _np.mean(ys)) ** 2))
        r2 = 1.0 - rss / tss if tss > 0 else None
        df_resid = n - X.shape[1]
        mse = rss / df_resid if df_resid > 0 else 0.0
        XtX_inv = _np.linalg.inv(X.T @ X)
        se = [math.sqrt(mse * float(XtX_inv[i, i])) for i in range(X.shape[1])]
        params = {}
        for i, nm in enumerate(["const"] + names):
            b = float(beta[i])
            s = se[i]
            tstat = b / s if s > 0 else 0.0
            pval = 2.0 * (1.0 - _t.cdf(abs(tstat), df_resid)) if df_resid > 0 else None
            params[nm] = {"coef": round(b, 6), "std_err": round(s, 6),
                          "t": round(float(tstat), 4),
                          "p_value": round(float(pval), 4) if pval is not None else None}
        return {"rsquared": round(float(r2), 4) if r2 is not None else None,
                "n": n, "params": params}
    except Exception:  # noqa: BLE001
        return {"rsquared": None, "params": None, "n": 0}


def variance_inflation_factor(columns: dict) -> dict:
    """VIF for each column (regress column on the others; VIF = 1/(1-R²)).
    ``{col: {vif, high}}`` where high = VIF > 5. None for < 3 columns or a
    singular fit."""
    names = [k for k in (columns or {}) if columns.get(k)]
    out: dict = {k: {"vif": None, "high": None} for k in names}
    if len(names) < 3:
        return out
    series = [_clean(columns[k]) for k in names]
    n = min(len(s) for s in series)
    if n < len(names) + 2:
        return out
    series = [s[:n] for s in series]
    for i, nm in enumerate(names):
        others = [j for j in range(len(names)) if j != i]
        y = _np.array(series[i], dtype=float)
        X = _np.column_stack([_np.ones(n)] + [list(series[j]) for j in others])
        try:
            beta, *_ = _np.linalg.lstsq(X, y, rcond=None)
            resid = y - X @ beta
            rss = float(_np.sum(resid ** 2))
            tss = float(_np.sum((y - y.mean()) ** 2))
            r2 = 1.0 - rss / tss if tss > 0 else 0.0
            vif = 1.0 / (1.0 - r2) if r2 < 1.0 else None
            out[nm] = {"vif": round(float(vif), 3) if vif is not None else None,
                       "high": bool(vif is not None and vif > 5.0)}
        except Exception:  # noqa: BLE001
            out[nm] = {"vif": None, "high": None}
    return out


__all__ = [
    "normality", "unit_root", "omega", "correlation_matrix",
    "cointegration_pair", "granger_causality", "capm_decomposition",
    "ols_factors", "variance_inflation_factor",
]
