"""News-sentiment factor research (News_Sentiment.md §2-§7).

Pure, offline, deterministic estimators that validate whether a news-sentiment
signal predicts returns before the repo lets it influence sizing:

- lead/lag cross-correlation (sentiment leads/lags price),
- multi-horizon predictive OLS with Newey-West HAC errors (overlapping
  windows),
- sector / size neutralization (pure idiosyncratic signal),
- rolling Information Coefficient (IC) + IC-IR,
- IC term structure / alpha-decay half-life,
- quintile long/short backtest (long Q5 / short Q1, net of costs).

Conventions mirror ``statistical.py``: every function returns floats / dicts /
lists or explicit ``None`` on insufficient or degenerate input — never
fabricated. Panels are ``dict[str, list[float]]`` (ticker -> values aligned to
``dates``), which is how the Phase-4 eval script feeds them.

numpy + scipy only (no statsmodels / plotly — the repo's pure-NumPy precedent).
"""

from __future__ import annotations

import math

import numpy as _np
from scipy import stats as _st

__all__ = [
    "sentiment_lead_lag",
    "multi_horizon_sentiment_regression",
    "sector_neutral_z",
    "residualize_sentiment",
    "rolling_information_coefficient",
    "ic_term_structure",
    "quintile_long_short",
    "sentiment_factor_scale",
]


def _py(o):
    """Recursively convert numpy scalars/arrays to native Python so report
    rendering and ``json.dumps`` never choke on ``np.float64`` values."""
    if isinstance(o, _np.generic):
        return o.item()
    if isinstance(o, dict):
        return {k: _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_py(v) for v in o]
    return o


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


def sentiment_lead_lag(
    sentiment: list, returns: list, max_lags: int = 10, innovations: bool = False
) -> list[dict] | None:
    """Cross-correlation of sentiment vs forward returns (Pearson + Spearman).

    ``sentiment`` and ``returns`` are chronological and aligned; rows with a
    None on either side are dropped pairwise. ``innovations=True`` first
    differences the sentiment series (``S_t - S_{t-1}``) so the SMA's
    built-in autocorrelation does not inflate the correlation (News_Sentiment.md
    modeling caveat).

    Positive lag k = sentiment at t vs return at t+k (sentiment LEADS).
    Returns ``[{lag_days, pearson_corr, pearson_pval, spearman_corr,
    spearman_pval, sample_size}]`` or None with < 10 usable rows.
    """
    s = _clean(sentiment)
    r = _clean(returns)
    n = min(len(s), len(r))
    s, r = s[:n], r[:n]
    if innovations:
        s = [s[i] - s[i - 1] for i in range(1, n)]
        r = r[1:]
    if len(s) < 10:
        return None
    out = []
    for lag in range(-max_lags, max_lags + 1):
        x = s
        y = r[lag:] + [None] * lag if lag >= 0 else [None] * (-lag) + r
        x = x[: len(y)]
        paired = [(a, b) for a, b in zip(x, y, strict=False) if b is not None]
        if len(paired) < 10:
            continue
        a = [p[0] for p in paired]
        b = [p[1] for p in paired]
        try:
            pr, pp = _st.pearsonr(a, b)
            sr, sp = _st.spearmanr(a, b)
        except ValueError:
            continue
        out.append(
            {
                "lag_days": lag,
                "pearson_corr": round(float(pr), 4),
                "pearson_pval": round(float(pp), 4),
                "spearman_corr": round(float(sr), 4),
                "spearman_pval": round(float(sp), 4),
                "sample_size": len(paired),
            }
        )
    return _py(out) or None


def _nw_ols(y: list[float], X: _np.ndarray, maxlags: int) -> dict:
    """OLS with Newey-West HAC covariance; returns dict or raises on degenerate.

    Classic Bartlett-kernel sandwich::

        cov = inv(X'X) @ S @ inv(X'X)
        S   = sum_t e_t^2 x_t x_t'
            + sum_{l=1..L} w_l * sum_{t>l} e_t e_{t-l} (x_t x_{t-l}' + x_{t-l} x_t')
        w_l = 1 - l / (L + 1)
    """
    yv = _np.array(y, dtype=float)
    n, k = X.shape
    beta, *_ = _np.linalg.lstsq(X, yv, rcond=None)
    e = yv - X @ beta
    xtx_inv = _np.linalg.pinv(X.T @ X)
    # Bartlett-kernel HAC covariance:
    # S = sum_t e_t^2 outer(x_t) + sum_{l=1..L} w_l sum_{t>l} e_t e_{t-l}
    #     (outer(x_t, x_{t-l}) + outer(x_{t-l}, x_t)),  w_l = 1 - l/(L+1).
    s = _np.zeros((k, k))
    for t in range(n):
        xt = X[t]
        s += e[t] ** 2 * _np.outer(xt, xt)
    for lag in range(1, maxlags + 1):
        w = 1.0 - lag / (maxlags + 1)
        for t in range(lag, n):
            xt = X[t]
            xm = X[t - lag]
            s += w * e[t] * e[t - lag] * (_np.outer(xt, xm) + _np.outer(xm, xt))
    cov = xtx_inv @ s @ xtx_inv
    se = _np.sqrt(_np.abs(_np.diag(cov)))
    t = beta / se
    df = n - k
    p = 2.0 * (1.0 - _st.t.cdf(_np.abs(t), df))
    ss_tot = float(((yv - yv.mean()) ** 2).sum())
    r2 = 1.0 - float((e**2).sum()) / ss_tot if ss_tot > 0 else 0.0
    k_eff = k - 1
    r2_adj = 1.0 - (1.0 - r2) * (n - 1) / max(1, n - k_eff - 1)
    return {"beta": list(beta), "se": list(se), "t": list(t), "p": list(p), "r2_adj": float(r2_adj), "n": n}


def multi_horizon_sentiment_regression(
    sentiment: list,
    close: list,
    volume: list | None = None,
    horizons: tuple = (1, 3, 5, 10, 20),
) -> list[dict] | None:
    """Multi-horizon predictive OLS with Newey-West HAC errors.

    Model (News_Sentiment.md)::

        R_{t->t+h} = a + b1 * Sent_t + b2 * R_{t-1} + b3 * dln(Vol_t) + e

    Overlapping forward windows induce MA(h-1) errors -> HAC covariance with
    ``maxlags = max(1, h+1)`` (Bartlett kernel). All series chronological and
    aligned; rows with any None are dropped. Returns per-horizon dicts
    ``{horizon_days, sent_coef, sent_tstat, sent_pval,
    control_ret_coef, control_ret_pval, control_vol_coef, control_vol_pval,
    r_squared_adj, observations}`` or None with < 30 usable rows.
    """
    s = _clean(sentiment)
    c = _clean(close)
    v = _clean(volume) if volume else [None] * min(len(s), len(c))
    n = min(len(s), len(c), len(v))
    if n < 30:
        return None
    s, c, v = s[:n], c[:n], v[:n]
    ret = [0.0] + [(c[i] / c[i - 1] - 1.0) if c[i - 1] else 0.0 for i in range(1, n)]
    ret_lag1 = [0.0] + ret[:-1]
    dvol = [0.0] + [
        (math.log(v[i] + 1.0) - math.log(v[i - 1] + 1.0)) if (v[i] is not None and v[i - 1]) else 0.0
        for i in range(1, n)
    ]
    out = []
    for h in horizons:
        h = int(h)
        fwd = [
            (c[i + h] / c[i] - 1.0) if i + h < n and c[i] else None for i in range(n)
        ]
        rows = [(i, fwd[i]) for i in range(n) if fwd[i] is not None and s[i] is not None]
        if len(rows) < 30:
            continue
        y = [r[1] for r in rows]
        X = _np.column_stack(
            [
                _np.ones(len(rows)),
                [s[i] for i, _ in rows],
                [ret_lag1[i] for i, _ in rows],
                [dvol[i] for i, _ in rows],
            ]
        )
        try:
            res = _nw_ols(y, X, maxlags=max(1, h + 1))
        except Exception:  # noqa: BLE001 - degenerate window degrades
            continue
        sent_idx = 1
        out.append(
            {
                "horizon_days": h,
                "sent_coef": round(res["beta"][sent_idx], 4),
                "sent_tstat": round(res["t"][sent_idx], 4),
                "sent_pval": round(res["p"][sent_idx], 3),
                "control_ret_coef": round(res["beta"][2], 4),
                "control_ret_pval": round(res["p"][2], 3),
                "control_vol_coef": round(res["beta"][3], 4),
                "control_vol_pval": round(res["p"][3], 3),
                "r_squared_adj": round(res["r2_adj"], 4),
                "observations": res["n"],
            }
        )
    return _py(out) or None


def _cross_section(panel: dict, i: int) -> dict:
    out = {}
    for t, vals in panel.items():
        if vals is not None and i < len(vals):
            v = vals[i]
            if v is not None and math.isfinite(float(v)):
                out[t] = float(v)
    return out


def sector_neutral_z(
    panel: dict, sector_map: dict, min_assets: int = 3, winsorize: float = 3.0
) -> dict:
    """Per-date z-score of sentiment within each sector (universe fallback).

    For each date i, every ticker's value is standardized against the mean/std
    of its sector (``min_assets`` names required per sector, else the
    universe-wide stats) and clipped to ``[-winsorize, +winsorize]`` —
    removes the systematic sector tilt (News_Sentiment.md §5).
    """
    n_dates = max((len(v) for v in panel.values() if v), default=0)
    out: dict = {t: [None] * n_dates for t in panel}
    for i in range(n_dates):
        cs = _cross_section(panel, i)
        if not cs:
            continue
        univ = list(cs.values())
        uv_mean = sum(univ) / len(univ)
        uv_std = (sum((x - uv_mean) ** 2 for x in univ) / len(univ)) ** 0.5 or 1.0
        grouped: dict = {}
        for t, v in cs.items():
            grouped.setdefault(str(sector_map.get(t, "Unknown")), []).append((t, v))
        for rows in grouped.values():
            vals = [r[1] for r in rows]
            if len(vals) >= min_assets:
                m = sum(vals) / len(vals)
                sd = (sum((x - m) ** 2 for x in vals) / len(vals)) ** 0.5
            else:
                m, sd = uv_mean, uv_std
            if sd <= 1e-8:
                sd = 1.0 if m == 0 else abs(m) * 1e-3 or 1.0
            for t, v in rows:
                z = max(-winsorize, min(winsorize, (v - m) / sd))
                out[t][i] = round(z, 4)
    return _py(out)


def residualize_sentiment(
    panel: dict, mcap: dict, sector_map: dict, min_assets: int = 15, winsorize: float = 3.0
) -> dict:
    """Cross-sectional OLS of sentiment on log-mcap + sector dummies.

    Per date i: regression ``S = a + b*ln(mcap) + sector dummies``
    (``drop_first``, one sector omitted), standardized residuals =
    the pure idiosyncratic sentiment signal (News_Sentiment.md §5). None for
    dates with fewer than ``min_assets`` aligned names.
    """
    n_dates = max((len(v) for v in panel.values() if v), default=0)
    out: dict = {t: [None] * n_dates for t in panel}
    sectors = sorted({str(s) for s in sector_map.values()})
    base = sectors[0] if sectors else ""
    for i in range(n_dates):
        cs = _cross_section(panel, i)
        rows = []
        for t, v in cs.items():
            mv = mcap.get(t)
            mval = mv[i] if isinstance(mv, list) and i < len(mv) and mv[i] is not None else None
            if mval is None or float(mval) <= 0:
                continue
            rows.append((t, v, math.log(float(mval)), str(sector_map.get(t, "Unknown"))))
        if len(rows) < min_assets:
            continue
        ys = [r[1] for r in rows]
        X = _np.column_stack(
            [_np.ones(len(rows)), [r[2] for r in rows]]
            + [
                [1.0 if r[3] == sec else 0.0 for r in rows]
                for sec in sectors
                if sec != base
            ]
        )
        try:
            beta, *_ = _np.linalg.lstsq(X, _np.array(ys), rcond=None)
            resid = _np.array(ys) - X @ beta
        except Exception:  # noqa: BLE001 - singular date degrades
            continue
        sd = float(resid.std())
        if sd <= 1e-8:
            continue
        norm = ((resid - resid.mean()) / sd).tolist()
        for j, (t, _, _, _) in enumerate(rows):
            out[t][i] = round(max(-winsorize, min(winsorize, norm[j])), 4)
    return _py(out)


def _forward_returns(panel: dict, prices: dict, holding: int) -> tuple[int, dict]:
    n = max((len(v) for v in prices.values() if v), default=0)
    fwd_map: dict = {}
    for t, vals in prices.items():
        if not vals:
            continue
        fwd_map[t] = [
            (vals[i + holding] / vals[i] - 1.0) if i + holding < len(vals) and vals[i] else None
            for i in range(len(vals))
        ]
    return n, fwd_map


def rolling_information_coefficient(
    panel: dict, prices: dict, holding: int = 5, window: int = 12, min_assets: int = 15
) -> dict | None:
    """Per-date cross-sectional Pearson + Rank IC vs forward holding return.

    Returns ``{dates, pearson_ic, rank_ic, p_value, rolling_rank_ic,
    metrics}`` or None with no usable date. ``metrics`` = mean rank IC,
    IC-IR (annualized by sqrt(252/holding)), positive-IC ratio, t-stat/p.
    """
    n, fwd = _forward_returns(panel, prices, holding)
    recs = []
    for i in range(n - holding):
        cs = _cross_section(fwd, i)
        sig = _cross_section(panel, i)
        common = [t for t in sig if t in cs and cs[t] is not None]
        if len(common) < min_assets:
            continue
        a = [sig[t] for t in common]
        b = [cs[t] for t in common]
        try:
            pr, _ = _st.pearsonr(a, b)
            sr, sp = _st.spearmanr(a, b)
        except ValueError:
            continue
        recs.append({"i": i, "pearson_ic": float(pr), "rank_ic": float(sr), "p_value": float(sp), "n": len(common)})
    if not recs:
        return None
    rank_ics = [r["rank_ic"] for r in recs]
    mean = sum(rank_ics) / len(rank_ics)
    sd = (sum((x - mean) ** 2 for x in rank_ics) / (len(rank_ics) - 1)) ** 0.5 or 1e-9
    ir = mean / sd * math.sqrt(252.0 / max(1, holding))
    tstat = mean / (sd / (len(rank_ics) ** 0.5))
    p = 2.0 * (1.0 - _st.t.cdf(abs(tstat), len(rank_ics) - 1))
    rolling = [None] * max(0, window - 1)
    for i in range(window - 1, len(rank_ics)):
        seg = rank_ics[i - window + 1 : i + 1]
        rolling.append(round(sum(seg) / len(seg), 4))
    return _py(
        {
            "dates": [r["i"] for r in recs],
            "pearson_ic": [round(r["pearson_ic"], 4) for r in recs],
            "rank_ic": [round(r["rank_ic"], 4) for r in recs],
            "p_value": [round(r["p_value"], 4) for r in recs],
            "rolling_rank_ic": rolling,
            "metrics": {
                "mean_rank_ic": round(mean, 4),
                "mean_pearson_ic": round(sum(r["pearson_ic"] for r in recs) / len(recs), 4),
                "ic_ir": round(ir, 2),
                "pct_positive": round(sum(1 for x in rank_ics if x > 0) / len(rank_ics), 3),
                "t_stat": round(tstat, 2),
                "p_value": round(p, 4),
                "periods": len(recs),
            },
        }
    )


def ic_term_structure(
    panel: dict, prices: dict, max_horizon: int = 30, min_assets: int = 15
) -> list[dict] | None:
    """Mean cross-sectional Rank IC across h in [1, max_horizon] + half-life.

    Fits ``IC(h) = IC0 * exp(-lambda*h)`` (scipy.optimize.curve_fit) and
    reports ``half_life`` = ln(2)/lambda (None when the fit is degenerate).
    Alpha decays fast for news — the half-life selects the rebalance cadence
    (News_Sentiment.md §6-§7).
    """
    out = []
    ics = []
    for h in range(1, max_horizon + 1):
        n, fwd = _forward_returns(panel, prices, h)
        per_h = []
        for i in range(n - h):
            cs = _cross_section(fwd, i)
            sig = _cross_section(panel, i)
            common = [t for t in sig if t in cs and cs[t] is not None]
            if len(common) < min_assets:
                continue
            try:
                sr, _ = _st.spearmanr([sig[t] for t in common], [cs[t] for t in common])
            except ValueError:
                continue
            per_h.append(float(sr))
        if not per_h:
            continue
        mean = sum(per_h) / len(per_h)
        sd = (sum((x - mean) ** 2 for x in per_h) / (len(per_h) - 1)) ** 0.5 or 1e-9
        tstat = mean / (sd / (len(per_h) ** 0.5))
        ics.append((h, mean))
        out.append(
            {
                "horizon_days": h,
                "mean_rank_ic": round(mean, 4),
                "std_rank_ic": round(sd, 4),
                "ic_ir": round(mean / sd * math.sqrt(252.0 / h), 2),
                "t_stat": round(tstat, 2),
                "p_value": round(2.0 * (1.0 - _st.t.cdf(abs(tstat), len(per_h) - 1)), 4),
                "pct_positive": round(sum(1 for x in per_h if x > 0) / len(per_h), 3),
                "periods": len(per_h),
            }
        )
    if not out:
        return None
    try:
        from scipy.optimize import curve_fit

        xs = _np.array([r[0] for r in ics], dtype=float)
        ys = _np.array([r[1] for r in ics], dtype=float)
        popt, *_ = curve_fit(
            lambda xx, ic0, lam: ic0 * _np.exp(-lam * xx),
            xs,
            ys,
            p0=[max(ys[0], 1e-6), 0.05],
            maxfev=2000,
        )
        half_life = math.log(2) / popt[1] if popt[1] > 1e-9 else None
        out.append({"half_life_days": round(half_life, 1) if half_life else None})
    except Exception:  # noqa: BLE001 - degenerate fit -> no half-life
        out.append({"half_life_days": None})
    return _py(out)


def _bucket(x: float, xs: list[float], n_buckets: int = 5) -> int:
    """Deterministic rank-based bucket 0..n_buckets-1 for a cross-section."""
    lo = min(xs)
    hi = max(xs)
    if hi - lo <= 1e-12:
        return n_buckets // 2
    below = sum(1 for v in xs if v < x)
    above = sum(1 for v in xs if v > x)
    eq = len(xs) - below - above
    rank = below + eq / 2.0
    return min(n_buckets - 1, int(rank * n_buckets / len(xs)))


def quintile_long_short(
    panel: dict,
    prices: dict,
    rebalance: str = "weekly",
    cost_bps: float = 10.0,
    oos_split: float | None = None,
) -> dict | None:
    """Weekly-rebalanced dollar-neutral quintile backtest (long Q5 / short Q1).

    Ranking uses the signal observed at rebalance date i; the forward return
    is the next rebalance-to-rebalance percentage change. One-way
    ``cost_bps`` is charged on both legs. ``oos_split`` (0..1) trims the
    first that fraction of periods as in-sample. Returns
    ``{dates, q1..q5, ls_net, metrics, monotonicity, turnover}`` or None.
    """
    n, fwd = _forward_returns(panel, prices, 1)
    if rebalance == "weekly":
        step = 5
    elif rebalance == "monthly":
        step = 21
    else:
        step = 1
    i = 0
    dates: list[int] = []
    q_rets: dict[str, list] = {f"q{k}": [] for k in range(1, 6)}
    ls: list[float] = []
    costs = 2.0 * float(cost_bps) / 10000.0
    prev_top = None
    turnovers: list[float] = []
    while i < n - 1:
        sig = _cross_section(panel, i)
        if len(sig) >= 10:
            xs = list(sig.values())
            buckets: dict = {t: _bucket(v, xs) for t, v in sig.items()}
            groups: dict = {k: [] for k in range(5)}
            for t, b in buckets.items():
                fv = fwd[t][i] if fwd.get(t) and i < len(fwd[t]) and fwd[t][i] is not None else None
                if fv is not None:
                    groups[b].append((t, fv))
            whole = {}
            for k in range(5):
                vals = [v for _, v in groups[k]]
                whole[f"q{k + 1}"] = sum(vals) / len(vals) if vals else 0.0
            cur_top = sorted(buckets)
            if prev_top is not None:
                turnovers.append(len(set(prev_top) ^ set(cur_top)) / max(1, len(cur_top)))
            prev_top = cur_top
            ls_net = whole["q5"] - whole["q1"] - costs
            for k in range(5):
                q_rets[f"q{k + 1}"].append(whole[f"q{k + 1}"])
            ls.append(ls_net)
            dates.append(i)
        i += step
    if not ls:
        return None
    pre = int(len(ls) * oos_split) if oos_split else 0
    ls_oos = ls[pre:]
    mu = sum(ls_oos) / len(ls_oos)
    sd = (sum((x - mu) ** 2 for x in ls_oos) / (len(ls_oos) - 1)) ** 0.5 or 1e-9
    ann = (252 / step) ** 0.5
    cum = 1.0
    peak = 1.0
    max_dd = 0.0
    for x in ls_oos:
        cum *= 1.0 + x
        peak = max(peak, cum)
        max_dd = min(max_dd, cum / peak - 1.0)
    mono_ok = 0
    for k in range(len(ls)):
        row = [q_rets[f"q{k2 + 1}"][k] for k2 in range(5)]
        mono = 1
        for j in range(4):
            if row[j + 1] < row[j] - 1e-12:
                mono = 0
                break
        mono_ok += mono
    return _py(
        {
            "dates": dates,
            "q1": [round(x, 4) for x in q_rets["q1"]],
            "q2": [round(x, 4) for x in q_rets["q2"]],
            "q3": [round(x, 4) for x in q_rets["q3"]],
            "q4": [round(x, 4) for x in q_rets["q4"]],
            "q5": [round(x, 4) for x in q_rets["q5"]],
            "ls_net": [round(x, 4) for x in ls],
            "metrics": {
                "annualized_return": round(mu * (252 / step), 4),
                "annualized_vol": round(sd * ann, 4),
                "sharpe": round(mu / sd * ann, 2),
                "max_drawdown": round(max_dd, 4),
                "periods": len(ls_oos),
            },
            "monotonicity": round(mono_ok / len(ls), 3) if ls else None,
            "turnover": round(sum(turnovers) / len(turnovers), 3) if turnovers else None,
        }
    )


def sentiment_factor_scale(
    rank_ic: float | None,
    innovation: float | None,
    min_ic: float = 0.02,
    max_scale: float = 0.2,
    min_scale: float = 0.5,
) -> float:
    """Sentiment overlay scale in [min_scale, 1 + max_scale].

    The signal only scales when the name's measured predictive direction
    (``rank_ic``) clears ``min_ic`` in magnitude; otherwise neutral 1.0.
    ``innovation`` is the latest daily sentiment shock: scaled up when the
    shock aligns with the historical predictive direction, down otherwise.
    """
    if rank_ic is None or innovation is None:
        return 1.0
    if abs(rank_ic) < min_ic:
        return 1.0
    direction = 1.0 if (rank_ic > 0) == (innovation > 0) else -1.0
    scale = 1.0 + max_scale * direction
    return max(min_scale, round(scale, 4))
