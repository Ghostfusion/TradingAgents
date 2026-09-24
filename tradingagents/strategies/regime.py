"""Phase 1 - market-regime gate.

Deterministic features first: realized volatility (21d percentile vs a
reference window), 200-SMA trend, and choppiness on ONE scale (0-100,
high = ranging: canonical CHOP with OHLC, the inverted Kaufman efficiency
ratio on closes alone). A walk-forward Gaussian hidden Markov model - pure
NumPy, no optional dependency - gives FILTERED state probabilities
(P(S_t | x_1:t), the forward pass only) and a bull/neutral/bear label; the
deterministic path is always available and testable offline.

Wire-up: compute features from daily OHLCV in a pre-graph step, stash
`regime` in graph state, and let the risk node scale position size /
stop levels and analysts frame their lens (bull/bear context).

R3's per-panel spectral read (`spectral_change_read`, 2607.06373) is the one
read here that takes a cross-section rather than a series: gated off by default,
it reports the movement of the panel's correlation spectrum between two rolling
windows - the projector distance, the absorption ratio, the leading-eigenvalue
share - each beside the calibrated first-order null band it must clear before a
structural change is declared. A non-rejection reads "not detectable", never "no
change".
"""

from __future__ import annotations

import math
from statistics import pstdev

#: dimension of feature tuple: (vol_percentile, trend, choppiness)
FREQ_PER_DAY = 252.0

#: Posterior mass on run length 0 (the newest point begins a new segment) at
#: which BOCPD raises the change alarm. 0.5 is the Bayes cut under 0-1 loss:
#: "more likely a fresh segment than a continuation". Raise it for fewer false
#: alarms, lower it for a faster (noisier) reaction.
BOCPD_SHIFT_THRESHOLD = 0.5


def realized_vol(
    close_prices: list[float], window: int = 21, periods: float = FREQ_PER_DAY
) -> float:
    """Annualized realized volatility over the last `window` daily closes."""
    prices = close_prices[-window:]
    if len(prices) < 3:
        return None
    rets = []
    prev = prices[0]
    for p in prices[1:]:
        if prev:
            rets.append(math.log(max(p, 1e-12) / max(prev, 1e-12)))
        prev = p
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var * periods)


def vol_percentile(history: list[list[float]], current_window: int = 21) -> float | None:
    """Percentile rank (0-1) of the latest realized vol vs all history windows.

    Returns ``None`` when it cannot measure - fewer than two windows to rank
    against - and **never a fabricated 0.5**. The 0.5 this used to return on
    failure was a neutral that entered every caller as if volatility had been
    measured mid-band (master rule 1: `NA` is not `0`, and an absent component
    must leave the denominator with its reason). The reason is available to the
    caller without guessing: the rank is unmeasurable exactly when
    ``len(history) < 2``, and :func:`vol_percentile_read` returns it as a string
    for display.
    """
    wins = []
    for close in history:
        wins.append(make_vol_series_of_closes(close, window=current_window))
    if len(wins) < 2:
        return None
    recent = wins[-1]
    below = sum(1 for w in wins if w <= recent)
    return below / len(wins)


def vol_percentile_read(history: list[list[float]], current_window: int = 21) -> dict:
    """``vol_percentile`` plus the reason it could not measure (master rule 1).

    Returns ``{"percentile": 0-1 | None, "windows": int, "reason": str | None,
    "basis": str}``. One implementation: the rank is :func:`vol_percentile`'s, so
    a display path can print WHY the leg is absent instead of a value that was
    never measured.
    """
    windows = len(history or ())
    pct = vol_percentile(history, current_window=current_window)
    if pct is None:
        return {
            "percentile": None,
            "windows": windows,
            "reason": (
                f"{windows} window(s) of history, needs 2 to rank the latest "
                f"realized vol against its own past"
            ),
            "basis": (
                f"realized-vol percentile unmeasurable: {windows} window(s) of "
                f"history, needs 2 - never a fabricated 0.5"
            ),
        }
    return {
        "percentile": pct,
        "windows": windows,
        "reason": None,
        "basis": (
            f"latest realized vol at the {pct:.0%} percentile of {windows} "
            f"trailing window(s)"
        ),
    }


def make_vol_series_of_closes(closes: list[float], window: int = 21) -> float:
    """Realized vol of the most recent window (helper for percentile)."""
    logrets = []
    prev = closes[0]
    for p in closes[1:]:
        if p and prev:
            logrets.append(math.log(max(p, 1e-9) / max(prev, 1e-9)))
        prev = p
    if len(logrets) < 2:
        return 0.0
    mean = sum(logrets) / len(logrets)
    var = sum((r - mean) ** 2 for r in logrets) / (len(logrets) - 1)
    return math.sqrt(var * FREQ_PER_DAY)


def trend_strength(close: list[float], sma_window: int = 200) -> float:
    """Simple trend proxy in [-1, 1]: (price - SMA(x)) / SMA(x)."""
    if len(close) < sma_window:
        sma = sum(close) / len(close)
    else:
        sma = sum(close[-sma_window:]) / sma_window
    if sma <= 0:
        return 0.0
    return (close[-1] - sma) / sma


def choppiness(close: list[float], highs: list | None = None,
               lows: list | None = None, window: int = 14) -> float | None:
    """Choppiness, **always on the 0-100 scale**, high = ranging.

    Two branches, one unit, so that every caller compares against the same
    threshold:

    * OHLC present -> the canonical Choppiness Index (Dreiss 1990s),
      ``CHOP = 100 * log10(sum(TR_i, n) / (HH(n) - LL(n))) / log10(n)``.
    * Close-only -> ``100 * (1 - efficiency ratio)``, where
      ``ER = |c[-1] - c[-n-1]| / sum(|c[i] - c[i-1]|)``. The efficiency ratio
      is the standard close-only trending measure (Kaufman); inverting it puts
      it on the same axis and direction as CHOP.

    Returns ``None`` when there is not enough history to measure either - the
    previous 0.5/0.01 return values were a fabricated neutral and a
    volatility measure respectively, and callers on different scales could not
    both be right (``overlays`` passed a literal 0.4 against a 0.30 default
    threshold while ``get_regime_components`` passed 30.0).
    """
    n = max(2, int(window))
    h = [float(x) for x in (highs or []) if x is not None]
    lo = [float(x) for x in (lows or []) if x is not None]
    c = [float(x) for x in close if x is not None]
    if len(c) >= n + 1 and len(h) >= n and len(lo) >= n:
        # true-range sum over the last n bars
        tr_sum = 0.0
        for i in range(len(c) - n, len(c)):
            hi, lw, prev_c = h[i], lo[i], c[i - 1]
            tr_sum += max(hi - lw, abs(hi - prev_c), abs(lw - prev_c))
        hi_hi = max(h[-n:])
        lo_lo = min(lo[-n:])
        rng = hi_hi - lo_lo
        if rng > 0 and tr_sum > 0:
            return float(100.0 * math.log10(tr_sum / rng) / math.log10(n))
    if len(c) >= n + 1:
        # close-only: 100 * (1 - Kaufman efficiency ratio)
        path = 0.0
        for i in range(len(c) - n, len(c)):
            path += abs(c[i] - c[i - 1])
        if path <= 0:
            return 100.0  # no net movement at all = maximally non-trending
        er = abs(c[-1] - c[-n - 1]) / path
        return float(100.0 * (1.0 - min(er, 1.0)))
    return None


#: CHOP at or below this reads as "trending" (canonical CHOP is ~20-80 in
#: practice; 30/60 is the conventional trending/ranging split). This is the ONE
#: threshold both callers use - see `regime_label`.
CHOP_TREND_THRESHOLD = 30.0


def regime_label(
    vol_pct: float,
    trend: float,
    chop: float | None,
    vol_hi: float = 0.75,
    vol_lo: float = 0.25,
    trend_threshold: float = 0.02,
    chop_threshold: float = CHOP_TREND_THRESHOLD,
) -> str:
    """Rule-based regime: high-vol | bull | bear | neutral.

    Priority: volatility state first (risk gate), then trend, then choppiness.

    ``chop`` is on the 0-100 scale of :func:`choppiness` and ``chop_threshold``
    defaults to the same constant both callers use. The trend leg fires when
    the tape is measurably trending (low CHOP) **or** when the volatility
    percentile is in the low band; a ``None`` chop means "not measurable" and
    falls through to ``neutral`` rather than asserting a trend.

    A ``None`` ``vol_pct`` means the volatility percentile could not be measured
    (:func:`vol_percentile` returns ``None`` rather than a fabricated 0.5): like a
    ``None`` chop it is **not asserted**, so the volatility leg is skipped and the
    trend / choppiness legs decide. The label never claims a volatility state the
    caller did not measure.
    """
    if vol_pct is not None and vol_pct >= vol_hi:
        return "high_vol"
    if vol_pct is not None and vol_pct <= vol_lo and abs(trend) >= trend_threshold:
        return "bull" if trend > 0 else "bear"
    if chop is not None and chop <= chop_threshold:
        return "bull" if trend > 0 else "bear"
    return "neutral"


def _log_returns(closes) -> list:
    """Natural-log returns aligned to ``closes`` (index 0 is None)."""
    cs = []
    for c in closes or []:
        try:
            cs.append(float(c))
        except (TypeError, ValueError):
            cs.append(None)
    out: list = [None]
    for i in range(1, len(cs)):
        a, b = cs[i - 1], cs[i]
        out.append(math.log(b / a) if (a and b and a > 0 and b > 0) else None)
    return out


#: The emission families R2 (2606.23492) swaps into the ONE forward-backward
#: kernel: the Gaussian default plus three heavy-tailed families. Only the
#: density and the per-state M-step differ - the recursion is shared, and the
#: Gaussian branch is arithmetically identical to the pre-R2 path.
EMISSION_FAMILIES: tuple[str, ...] = ("gaussian", "student_t", "laplace", "ged")

#: Default degrees of freedom for the Student-t emission (the paper's low-dof
#: heavy tail). Fixed rather than fitted: fitting nu is an ECM iteration the
#: M-step here does not run, so a caller-chosen value is reported, not guessed.
EMISSION_NU = 5.0

#: Default shape for the GED emission (beta = 2 is Gaussian, < 2 is heavy-tailed).
EMISSION_BETA = 1.5


def _emission_logdens(x, means, covars, scales, family, nu, beta):
    """``(T, K)`` log emission densities for one family (pure NumPy).

    ``gaussian`` is the full-covariance multivariate normal - byte-identical in
    arithmetic to what ``_hmm_em`` computed before R2. ``student_t`` is the
    multivariate Student-t over the same covariance used as a scale matrix.
    ``laplace`` and ``ged`` are the independent per-dimension families the paper
    also fits: Laplace uses per-dimension scales ``b``; GED uses per-dimension
    standard deviations ``sigma`` mapped to its scale
    ``alpha = sigma * sqrt(Gamma(1/beta) / Gamma(3/beta))`` so the fitted scale
    has unit-variance standardisation.
    """
    import numpy as np

    n_rows, D = x.shape
    K = len(means)
    out = np.empty((n_rows, K))
    if family == "gaussian":
        for k in range(K):
            inv = np.linalg.inv(covars[k])
            det = max(float(np.linalg.det(covars[k])), 1e-300)
            d = x - means[k]
            quad = np.einsum("ij,jk,ik->i", d, inv, d)
            out[:, k] = -0.5 * (D * math.log(2.0 * math.pi) + math.log(det) + quad)
        return out
    if family == "student_t":
        for k in range(K):
            inv = np.linalg.inv(covars[k])
            det = max(float(np.linalg.det(covars[k])), 1e-300)
            d = x - means[k]
            quad = np.einsum("ij,jk,ik->i", d, inv, d)
            out[:, k] = (
                math.lgamma((nu + D) / 2.0) - math.lgamma(nu / 2.0)
                - 0.5 * D * math.log(nu * math.pi) - 0.5 * math.log(det)
                - 0.5 * (nu + D) * np.log1p(quad / nu)
            )
        return out
    if family == "laplace":
        for k in range(K):
            s = scales[k]
            d = np.abs(x - means[k]) / s
            out[:, k] = float(np.sum(-math.log(2.0) - np.log(s))) + np.sum(-d, axis=1)
        return out
    if family == "ged":
        a0 = math.sqrt(math.gamma(1.0 / beta) / math.gamma(3.0 / beta))
        c0 = math.log(beta) - math.log(2.0) - math.lgamma(1.0 / beta)
        for k in range(K):
            s = scales[k]
            d = np.abs(x - means[k]) / (s * a0)
            out[:, k] = D * c0 - float(np.sum(np.log(s))) + np.sum(-(d ** beta), axis=1)
        return out
    raise ValueError(f"unknown emission family {family!r}; known: {EMISSION_FAMILIES}")


def _emission_mstep(x, gamma, means, covars, scales, family, nu, beta):
    """One per-state M-step for the family, sharing the E-step's ``gamma``.

    ``gaussian`` is the weighted mean/covariance the pre-R2 path used, kept
    arithmetically identical. ``student_t`` adds the t's one-step EM weight
    ``u = (nu + D) / (nu + delta)`` to the mean/covariance. ``laplace`` uses the
    weighted mean and the mean absolute deviation as its scale; ``ged`` uses the
    weighted mean and the weighted standard deviation, with the fixed shape.
    """
    import numpy as np

    n_rows, D = x.shape
    K = len(means)
    w = gamma.sum(axis=0)
    if family == "gaussian":
        means = (gamma.T @ x) / np.maximum(w[:, None], 1e-300)
        for k in range(K):
            d = x - means[k]
            covars[k] = (d * gamma[:, k : k + 1]).T @ d / max(w[k], 1e-300) + np.eye(D) * 1e-8
        return means, covars, scales
    if family == "student_t":
        for k in range(K):
            inv = np.linalg.inv(covars[k])
            d = x - means[k]
            quad = np.einsum("ij,jk,ik->i", d, inv, d)
            gw = gamma[:, k] * ((nu + D) / (nu + quad))
            sw = max(float(gw.sum()), 1e-300)
            means[k] = (gw[:, None] * x).sum(axis=0) / sw
            d = x - means[k]
            covars[k] = (d * gw[:, None]).T @ d / sw + np.eye(D) * 1e-8
        return means, covars, scales
    w = np.maximum(w, 1e-300)
    means = (gamma.T @ x) / w[:, None]
    for k in range(K):
        d = x - means[k]
        if family == "laplace":
            scales[k] = (gamma[:, k : k + 1] * np.abs(d)).sum(axis=0) / w[k]
        else:  # ged
            scales[k] = np.sqrt((gamma[:, k : k + 1] * d * d).sum(axis=0) / w[k])
        covars[k] = (d * gamma[:, k : k + 1]).T @ d / w[k] + np.eye(D) * 1e-8
    return means, covars, scales


def _hmm_em(x, n_states: int, n_iter: int, seed: int, tol: float = 1e-4,
            family: str = "gaussian", nu: float = EMISSION_NU,
            beta: float = EMISSION_BETA) -> dict | None:
    """Baum-Welch (scaled forward-backward) on a ``(T, D)`` feature matrix.

    Pure NumPy - the same choice ``garch11_fit`` makes - so the filter has no
    optional dependency and is testable offline. Scaling (rather than log-space)
    keeps it readable: each alpha row is normalized by its own scale factor, and
    the log-likelihood is the sum of the log scale factors.

    R2 (2606.23492): ONE shared forward-backward kernel with only the emission
    density (``_emission_logdens``) and the per-state M-step
    (``_emission_mstep``) swapping across ``family``. With ``family="gaussian"``
    every arithmetic step is the pre-R2 one, so existing pins are unchanged.

    None on a degenerate fit (a singular covariance that cannot be regularized)
    or an unknown family.
    """
    import numpy as np

    if family not in EMISSION_FAMILIES:
        return None
    n_rows, D = x.shape
    if n_rows < n_states * 2:
        return None
    rng = np.random.default_rng(int(seed))
    idx = rng.permutation(n_rows)
    chunks = [c for c in np.array_split(idx, n_states) if len(c)]
    if len(chunks) < n_states:
        return None
    means = np.array([x[c].mean(axis=0) for c in chunks])
    covars = np.array([np.cov(x[c].T, ddof=0).reshape(D, D) + np.eye(D) * 1e-6 for c in chunks])
    scales = np.sqrt(np.maximum(np.array([np.diag(c) for c in covars]), 1e-12))
    pi = np.full(n_states, 1.0 / n_states)
    A = np.full((n_states, n_states), 1.0 / n_states)
    prev_ll = -np.inf
    ll = -np.inf
    try:
        for _ in range(int(n_iter)):
            if family == "gaussian":
                B = np.empty((n_rows, n_states))
                for k in range(n_states):
                    inv = np.linalg.inv(covars[k])
                    det = max(float(np.linalg.det(covars[k])), 1e-300)
                    d = x - means[k]
                    quad = np.einsum("ij,jk,ik->i", d, inv, d)
                    B[:, k] = np.exp(-0.5 * (D * math.log(2.0 * math.pi) + math.log(det) + quad))
            else:
                B = np.exp(_emission_logdens(x, means, covars, scales, family, nu, beta))
            B = np.clip(B, 1e-300, None)

            alpha = np.empty((n_rows, n_states))
            c = np.empty(n_rows)
            alpha[0] = pi * B[0]
            c[0] = alpha[0].sum() or 1e-300
            alpha[0] /= c[0]
            for t in range(1, n_rows):
                alpha[t] = (alpha[t - 1] @ A) * B[t]
                c[t] = alpha[t].sum() or 1e-300
                alpha[t] /= c[t]

            gamma = np.empty((n_rows, n_states))
            gamma[-1] = alpha[-1]
            xi = np.zeros((n_states, n_states))
            beta_ = np.ones(n_states)
            for t in range(n_rows - 2, -1, -1):
                beta_ = (A @ (B[t + 1] * beta_)) / c[t + 1]
                gamma[t] = alpha[t] * beta_
                s = gamma[t].sum() or 1e-300
                gamma[t] /= s
                xi += np.outer(alpha[t], B[t + 1] * beta_) / c[t + 1]

            ll = float(np.log(c).sum())
            pi = gamma[0] / (gamma[0].sum() or 1e-300)
            A = xi / np.maximum(xi.sum(axis=1, keepdims=True), 1e-300)
            if family == "gaussian":
                w = gamma.sum(axis=0)
                means = (gamma.T @ x) / np.maximum(w[:, None], 1e-300)
                for k in range(n_states):
                    d = x - means[k]
                    covars[k] = (d * gamma[:, k : k + 1]).T @ d / max(w[k], 1e-300) + np.eye(D) * 1e-8
                scales = np.sqrt(np.maximum(np.array([np.diag(covars[k]) for k in range(n_states)]), 1e-12))
            else:
                means, covars, scales = _emission_mstep(
                    x, gamma, means, covars, scales, family, float(nu), float(beta))
            if abs(ll - prev_ll) < tol:
                break
            prev_ll = ll
    except (np.linalg.LinAlgError, FloatingPointError, ValueError):
        return None
    if not np.isfinite(ll):
        return None
    return {"pi": pi, "A": A, "means": means, "covars": covars, "scales": scales,
            "family": family, "nu": float(nu), "beta": float(beta), "loglik": ll}


def _hmm_filter_step(alpha, model, obs):
    """One filtered step: ``P(S_t | x_{1:t})`` from ``P(S_{t-1} | x_{1:t-1})``.

    This is the forward recursion - NOT ``predict_proba``, which runs the
    backward pass too and so conditions on observations after ``t``.
    """
    import numpy as np

    prior = np.asarray(alpha) @ model["A"]
    fam = model.get("family", "gaussian")
    if fam == "gaussian":
        d = obs - model["means"]
        dens = np.empty(len(model["means"]))
        for k in range(len(model["means"])):
            inv = np.linalg.inv(model["covars"][k])
            det = max(float(np.linalg.det(model["covars"][k])), 1e-300)
            dens[k] = math.exp(
                -0.5 * (len(obs) * math.log(2.0 * math.pi) + math.log(det) + d[k] @ inv @ d[k])
            )
    else:
        # Same forward recursion, R2's emission density: the filtered posterior
        # must use the family the parameters were fit under, or a refit would
        # silently revert to Gaussian.
        logd = _emission_logdens(
            np.asarray(obs, dtype=float)[None, :], model["means"], model["covars"],
            model["scales"], fam, model.get("nu", EMISSION_NU),
            model.get("beta", EMISSION_BETA),
        )
        dens = np.exp(logd[0])
    post = prior * np.clip(dens, 1e-300, None)
    total = post.sum()
    return post / total if total > 0 else prior


def _hmm_filter_series(model, x):
    """Filtered probabilities over a sequence: the last row is ``P(S | x_{1:T})``."""
    import numpy as np

    alpha = np.asarray(model["pi"], dtype=float).copy()
    out = np.empty((len(x), len(model["means"])))
    for t in range(len(x)):
        alpha = _hmm_filter_step(alpha, model, x[t])
        out[t] = alpha
    return out


def _hmm_canonical(model: dict) -> dict:
    """Reorder states by mean log return, descending - state 0 is the best drift.

    HMM state indices are arbitrary and Baum-Welch is non-convex, so the labels
    must be canonicalized or state 0 at one refit is a different regime at the
    next. Sorting on the return mean is deterministic and needs no division;
    the volatility shape is REPORTED (``vol_means``) rather than assumed, because
    the estimator does not guarantee it is monotone in the same order.
    """
    import numpy as np

    order = np.argsort(-np.asarray(model["means"])[:, 0], kind="stable")
    out = {
        "pi": model["pi"][order],
        "A": model["A"][np.ix_(order, order)],
        "means": model["means"][order],
        "covars": model["covars"][order],
        "loglik": model["loglik"],
        "order": [int(i) for i in order],
    }
    # Carry the R2 emission identity and per-dimension scales through the
    # reorder: the filter's density must use the same family after a refit.
    if "scales" in model:
        out["scales"] = model["scales"][order]
    for key in ("family", "nu", "beta"):
        if key in model:
            out[key] = model[key]
    return out


def _hmm_heavy_tails_enabled() -> bool:
    """Is R2's heavy-tailed emission path switched on? (``enable_hmm_heavy_tails``)

    Off by default. The key is read by its literal name so the gate registry's
    read-site scan finds it, and an unreadable config leaves the gate off - a
    config read must never break the read it guards. With the gate off a
    requested non-Gaussian emission falls back to Gaussian, so a gate-off
    ``hmm_filtered_regime`` is byte-identical to the pre-R2 one.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_hmm_heavy_tails", False))


def hmm_filtered_regime(
    opens,
    highs,
    lows,
    closes,
    *,
    n_states: int = 3,
    vol_window: int = 10,
    min_train: int = 252,
    refit_every: int = 20,
    n_iter: int = 60,
    restarts: int = 3,
    seed: int = 7,
    emission: str = "gaussian",
    nu: float = EMISSION_NU,
    beta: float = EMISSION_BETA,
) -> dict | None:
    """Walk-forward HMM whose probabilities are FILTERED, not smoothed.

    One shared forward-backward kernel (``_hmm_em``); R2 (2606.23492) swaps in a
    heavy-tailed emission family - ``gaussian`` (the default, unchanged),
    ``student_t``, ``laplace`` or ``ged`` - behind ``enable_hmm_heavy_tails``
    (default off). With the gate off a non-Gaussian ``emission`` silently falls
    back to Gaussian and the record says so, so a gate-off caller's ``probs``
    are byte-identical to the pre-R2 run. ``n_states`` (the paper's ``K``) is
    selectable; the ``selection`` field reports the criterion used.

    A regime model used live may only condition on data it has. ``predict_proba``
    in hmmlearn runs the forward AND backward passes, so its rows are
    ``P(S_t | x_{1:T})`` - they use the future. This runs the forward recursion
    only, so row ``t`` is ``P(S_t | x_{1:t})``: the value available at that bar's
    close.

    Two further leaks are closed by construction. Parameters are refit on
    ``x[:t]`` - strictly past data - every ``refit_every`` bars, and after each
    refit the filter is re-run over that same past window so the carried state
    is the new model's own posterior, not the previous model's. States are
    canonicalized by mean return at every refit (``_hmm_canonical``), so the
    columns keep their meaning across refits even though the raw indices do not.

    Features are ``[log return, volatility]`` where the volatility leg is
    ``volatility_models.yang_zhang_vol_series`` - the drift-independent,
    gap-aware estimator (master rule 15: no second volatility producer). Passing
    closes alone for OHLC collapses Yang-Zhang to close-to-close volatility,
    which is why ``hmm_regime`` can delegate here.

    Returns ``{"states", "probs", "n_states", "n", "first_index", "last",
    "params", "refits", "basis"}`` or None when the history is too short or no
    fit converged. ``probs`` and ``states`` are BAR-ALIGNED to ``closes``, the
    same convention ``yang_zhang_vol_series`` uses: index them with the bar
    index you use on the closes, ``None`` / ``-1`` before ``first_index``,
    which is the first bar carrying a filtered read.
    """
    import numpy as np

    from .volatility_models import yang_zhang_vol_series

    if int(n_states) < 2:
        return None
    fam = str(emission).lower()
    if fam not in EMISSION_FAMILIES:
        return None
    gate_off_fallback = fam != "gaussian" and not _hmm_heavy_tails_enabled()
    if gate_off_fallback:
        fam = "gaussian"
    cs = [float(c) for c in (closes or [])]
    if len(cs) < 3:
        return None
    yz = yang_zhang_vol_series(opens, highs, lows, closes, int(vol_window))
    vol_series = yz["series"]
    rets = _log_returns(closes)
    rows = []
    for i in range(len(cs)):
        r = rets[i]
        v = vol_series[i] if i < len(vol_series) else None
        if r is not None and v is not None:
            rows.append((i, r, v))
    if len(rows) < int(min_train) + 2:
        return None
    bar_index = [i for i, _, _ in rows]
    x = np.array([[r, v] for _, r, v in rows], dtype=float)

    k_states = int(n_states)
    n_bars = len(cs)
    probs: list = [None] * n_bars
    states = [-1] * n_bars
    model = None
    alpha = None
    refits = 0
    for t in range(int(min_train), len(x)):
        if model is None or (t - int(min_train)) % int(refit_every) == 0:
            best = None
            for j in range(max(1, int(restarts))):
                cand = _hmm_em(x[:t], k_states, int(n_iter), int(seed) + 17 * j,
                               family=fam, nu=float(nu), beta=float(beta))
                if cand is None:
                    continue
                if best is None or cand["loglik"] > best["loglik"]:
                    best = cand
            if best is None:
                return None
            model = _hmm_canonical(best)
            refits += 1
            # Re-run the filter over the past window under the NEW parameters, so
            # the carried state is this model's posterior in ITS canonical order.
            # All of x[:t] is past, so this is not a leak.
            alpha = _hmm_filter_series(model, x[:t])[-1]
        alpha = _hmm_filter_step(alpha, model, x[t])
        # Bar-aligned, like ``yang_zhang_vol_series``: index it with the same
        # bar index you use on ``closes``.
        probs[bar_index[t]] = [round(float(p), 6) for p in alpha]
        states[bar_index[t]] = int(np.argmax(alpha))

    measured = sum(1 for p in probs if p is not None)
    if not measured:
        return None
    first_index = bar_index[int(min_train)]
    last_probs = probs[bar_index[-1]]
    last_state = states[bar_index[-1]] if states[bar_index[-1]] >= 0 else 0
    means = model["means"]
    label = (
        ("bull" if last_state == 0 else "bear")
        if k_states == 2
        else ("bull" if last_state == 0 else "bear" if last_state == k_states - 1 else "neutral")
    )
    n_obs = int(len(x))
    dim = int(x.shape[1])
    n_params = (
        k_states * k_states          # transition matrix
        + (k_states - 1)             # initial distribution
        + k_states * dim             # per-state means
        + k_states * (dim * (dim + 1) // 2)  # per-state covariances
    )
    if fam == "student_t":
        n_params += 1                # degrees of freedom
    elif fam == "ged":
        n_params += 1 + k_states * dim   # shape + per-state scales
    elif fam == "laplace":
        n_params += k_states * dim       # per-state scales
    return {
        "states": states,
        "probs": probs,
        "n_states": k_states,
        "n": n_bars,
        "measured": measured,
        "first_index": first_index,
        "last": {
            "state": last_state,
            "label": label,
            "probs": [round(float(p), 6) for p in last_probs],
            "mean_log_return": round(float(means[last_state][0]), 8),
            "mean_vol": round(float(means[last_state][1]), 8),
        },
        "params": {
            "means": [[round(float(v), 8) for v in row] for row in means],
            "vol_means": [round(float(m[1]), 8) for m in means],
            "transmat": [[round(float(v), 6) for v in row] for row in model["A"]],
        },
        "refits": refits,
        "emission": {
            "family": fam,
            "requested": str(emission).lower(),
            "gate_off_fallback": gate_off_fallback,
            "nu": float(nu) if fam == "student_t" else None,
            "beta": float(beta) if fam == "ged" else None,
            "means": [round(float(means[k][0]), 8) for k in range(k_states)],
            "vol_means": [round(float(means[k][1]), 8) for k in range(k_states)],
            "scales": [round(float(model["scales"][k][0]), 8) for k in range(k_states)],
        },
        "selection": {
            "k": k_states,
            "criterion": (
                "supplied by the caller (K is a parameter; no held-out "
                "log-likelihood/BIC search is run here)"
            ),
            "loglik": round(float(model["loglik"]), 4),
            "bic": round(-2.0 * float(model["loglik"]) + n_params * math.log(max(1, n_obs)), 4),
            "n_obs": n_obs,
            "n_params": n_params,
        },
        "basis": (
            f"{k_states}-state {fam} HMM over [log return, "
            f"yang_zhang_vol({int(vol_window)})] on {len(x)} feature rows, output "
            f"BAR-ALIGNED to the {n_bars} closes; "
            f"FILTERED probabilities P(S_t | x_1:t) - the forward pass only, no "
            f"backward pass; parameters refit on the strictly-past prefix every "
            f"{int(refit_every)} bars ({refits} refit(s)), states canonicalized by "
            f"mean return; {measured} of {n_bars} bars carry a filtered read, "
            f"first at bar {first_index}"
            + (
                f"; requested emission {str(emission).lower()} fell back to "
                f"gaussian because enable_hmm_heavy_tails is off (default)"
                if gate_off_fallback else ""
            )
        ),
    }


def hmm_regime(close: list[float], n_states: int = 2) -> str:
    """Walk-forward HMM regime label: 'bull', 'bear' (2 states) or 'neutral'.

    Delegates to ``hmm_filtered_regime`` so there is ONE HMM producer: this is
    the label view of the same filter, not a second implementation. Closes alone
    are passed as the OHLC input, which collapses the Yang-Zhang volatility leg
    to close-to-close - a real estimator on that input, not a fallback.

    Returns 'unknown' when the history is too short for the walk-forward fit or
    no fit converged - a named gap, never a guessed label. Needs roughly
    ``min_train`` (252) usable bars.
    """
    try:
        res = hmm_filtered_regime(
            close, close, close, close, n_states=int(n_states)
        )
    except Exception:  # noqa: BLE001 - advisory axis degrades
        return "unknown"
    if not res or not res.get("last"):
        return "unknown"
    return str(res["last"]["label"])


def _emission_cdf(z, family: str, nu: float, beta: float):
    """Elementwise CDF of the standardized emission family (scipy, deterministic)."""
    from scipy import stats

    if family == "gaussian":
        return stats.norm.cdf(z)
    if family == "student_t":
        return stats.t.cdf(z, float(nu))
    if family == "laplace":
        return stats.laplace.cdf(z)
    if family == "ged":
        return stats.gennorm.cdf(z, float(beta))
    raise ValueError(f"unknown emission family {family!r}; known: {EMISSION_FAMILIES}")


def regime_conditional_var(posteriors, emissions: dict, q: float = 0.05) -> list:
    """Regime-conditional VaR from the running posterior times each state's CDF.

    R2 (2606.23492). At each bar the mixture distribution of the next return is
    ``F_t(x) = sum_k p_{t,k} F_k(x)``, with ``p_t`` the FILTERED state posterior
    (``hmm_filtered_regime``'s ``probs`` row) and ``F_k`` the state-k emission
    CDF at the requested ``q``. The VaR is the ``q``-quantile of that mixture,
    found by bisection - reported in ``simple_var``'s convention (negative =
    loss), so it can be handed straight to ``book_risk.var_coverage_test``.

    ``emissions`` is the identity/hygiene record ``hmm_filtered_regime``
    returns: ``{"family", "means", "scales", "nu", "beta"}`` where ``means`` /
    ``scales`` are the per-state 1-D **return** location and family-native scale
    (dimension 0 of the fitted features). ``posteriors`` is a list of ``K``-row
    probability vectors (a ``None`` row yields ``None`` - a named gap, never 0).
    Returns one VaR per posterior row, in the input's order.
    """
    import numpy as np

    fam = str(emissions.get("family", "gaussian")).lower()
    if fam not in EMISSION_FAMILIES:
        raise ValueError(f"unknown emission family {fam!r}; known: {EMISSION_FAMILIES}")
    means = np.asarray([float(m) for m in emissions["means"]], dtype=float)
    scales = np.asarray([float(s) for s in emissions["scales"]], dtype=float)
    k = len(means)
    nu = float(emissions.get("nu") or EMISSION_NU)
    beta = float(emissions.get("beta") or EMISSION_BETA)
    rows = list(posteriors or [])
    n = len(rows)
    out: list = [None] * n
    valid = np.zeros(n, dtype=bool)
    P = np.zeros((n, k))
    for i, row in enumerate(rows):
        if row is None:
            continue
        try:
            vals = [float(x) for x in row]
        except (TypeError, ValueError):
            continue
        if len(vals) != k or any(not math.isfinite(v) for v in vals):
            continue
        P[i] = vals
        valid[i] = True
    if not valid.any():
        return out
    lo = np.full(n, float(np.min(means - 12.0 * scales)))
    hi = np.full(n, float(np.max(means + 12.0 * scales)))
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        z = (mid[:, None] - means[None, :]) / scales[None, :]
        c = (P * _emission_cdf(z, fam, nu, beta)).sum(axis=1)
        over = c > float(q)
        hi = np.where(over, mid, hi)
        lo = np.where(over, lo, mid)
    vals = 0.5 * (lo + hi)
    for i in range(n):
        if valid[i]:
            out[i] = float(vals[i])
    return out




def _sma(series: list, n: int) -> float | None:
    if len(series) < n or n <= 0:
        return None
    return sum(float(x) for x in series[-n:]) / n


def regime_gate_read(
    closes: list,
    cfg: dict | None = None,
    catalyst_window: bool | None = None,
    index_closes: list | None = None,
) -> dict:
    """Deterministic tradability regime for MEAN-REVERSION entries (advisory).

    Institutions gate counter-trend fades: allow a dip-buy only when volatility
    is contained, the market is not in a fast downtrend, and no catalyst window
    (earnings/Fed/high-macro) is open. Pure read over the close series + an
    optional catalyst flag:

    * ``vol_pct`` - percentile rank of the latest 21d realized vol vs its own
      trailing history (the volatility-regime-first rule).
    * ``fast_downtrend`` - price >= ``value_dip_regime_downtrend_band`` (default
      8%) below the 200-SMA while the 50-SMA is under the 200-SMA (falling
      knife guard).
    * ``catalyst_window`` - the caller's **explicit event fact**, tri-state.
      ``True``/``False`` are the caller's measured answer; ``None`` means the
      caller supplied none, and the axis is then reported **unmeasured** rather
      than assumed clear - the gate neither vetoes nor claims "no catalyst".
      It is never coerced to ``False``, because that asserts a measurement
      nobody made (D-11: the pre-graph context holds no event fact).
    * ``pass`` - False when high-vol (``value_dip_regime_vol_cap``, default
      0.8) OR fast_downtrend OR catalyst_window. ADVISORY: this function never
      blocks anything; hard-gating is opt-in at the caller via ``require_regime``
      so existing scans keep their behaviour.
    """
    cfg = cfg or {}
    # D-11: the tri-state, computed once so both returns and the veto agree.
    cat_flag: bool | None = None if catalyst_window is None else bool(catalyst_window)
    vol_cap = float(cfg.get("value_dip_regime_vol_cap", 0.8))
    band = float(cfg.get("value_dip_regime_downtrend_band", 0.08))
    if not closes or len(closes) < 60:
        return {
            "pass": None, "verdict": "unknown", "vol_pct": None,
            "fast_downtrend": None, "above_sma200": None, "sma50_rising": None,
            "index_vol_pct": None, "market_stress": None,
            "catalyst_window": cat_flag, "reasons": ["insufficient history"],
        }
    price = float(closes[-1])
    sma200 = _sma(closes, 200)
    sma50 = _sma(closes, 50)
    sma50_prev = _sma(closes[:-5], 50) if len(closes) > 55 else None
    above_200 = sma200 is not None and price >= sma200
    sma50_rising = sma50_prev is not None and sma50 is not None and sma50 >= sma50_prev
    fast_downtrend = bool(
        sma200 is not None
        and sma50 is not None
        and price < sma200 * (1.0 - band)
        and sma50 < sma200
    )

    # Market-level stress leg (mean-reversion value-trap defense): when an
    # index close series is supplied, its latest-21d realized-vol percentile
    # vs its own history is screened against market_stress_vol_cap. A stressed
    # tape (SPX/VIX-like) queers stock-specific dip entries - the book dries
    # up across names. ADVISORY: flags market_stress, never blocks by itself.
    index_vol_pct = None
    index_fast_downtrend = None
    if index_closes and len(index_closes) >= 60:
        idx_price = float(index_closes[-1])
        idx_sma200 = _sma(index_closes, 200)
        idx_sma50 = _sma(index_closes, 50)
        idx_vols = [
            realized_vol(index_closes[: i + 1], window=21)
            for i in range(20, len(index_closes))
        ]
        idx_vols = [v for v in idx_vols if v is not None]
        if idx_vols:
            recent = idx_vols[-1]
            hist = idx_vols[:-1] or [recent]
            index_vol_pct = round(sum(1 for v in hist if v <= recent) / len(hist), 4)
        index_fast_downtrend = bool(
            idx_sma200 is not None
            and idx_sma50 is not None
            and idx_price < idx_sma200 * (1.0 - band)
            and idx_sma50 < idx_sma200
        )
    market_vol_cap = float(cfg.get("market_stress_vol_cap", 0.85))
    market_stress = bool(index_vol_pct is not None and index_vol_pct > market_vol_cap)
    vols = [realized_vol(closes[: i + 1], window=21) for i in range(20, len(closes))]
    vols = [v for v in vols if v is not None]
    vol_pct = None
    if vols:
        recent = vols[-1]
        hist = vols[:-1] or [recent]
        vol_pct = round(sum(1 for v in hist if v <= recent) / len(hist), 4)
    high_vol = bool(vol_pct is not None and vol_pct > vol_cap)
    blocked = bool(high_vol or fast_downtrend or market_stress or cat_flag)
    verdict = (
        "high-vol"
        if high_vol
        else ("fast-downtrend" if fast_downtrend else ("catalyst-window" if cat_flag else "tradable"))
    )
    reasons = []
    if high_vol:
        reasons.append(f"vol_pct {vol_pct:.2f} > cap {vol_cap:.2f}")
    if fast_downtrend:
        reasons.append(f"price {band:.0%}+ below falling 200-SMA (knife guard)")
    if market_stress:
        reasons.append(f"market stress: index_vol_pct {index_vol_pct:.2f} > cap {market_vol_cap:.2f}")
    if cat_flag:
        reasons.append("catalyst window open")
    if not blocked:
        # D-11: "no catalyst" is a CLAIM, and it may only be made when the caller
        # actually supplied the fact. With no fact the axis is named as
        # unmeasured instead - this false trailer is what the model repeated back
        # as measured ("...no catalyst", AMKR 2026-09-17).
        reasons.append(
            "volatility contained + no fast downtrend (catalyst window not measured)"
            if cat_flag is None
            else "volatility contained + no fast downtrend + no catalyst"
        )
    return {
        "pass": not blocked,
        "verdict": verdict,
        "vol_pct": vol_pct,
        "fast_downtrend": fast_downtrend,
        "index_vol_pct": index_vol_pct,
        "index_fast_downtrend": index_fast_downtrend,
        "market_stress": market_stress,

        "above_sma200": above_200,
        "sma50_rising": sma50_rising,
        "catalyst_window": cat_flag,
        "thresholds": {"vol_cap": vol_cap, "downtrend_band": band},
        "reasons": reasons,
    }


def cusum(series: list, k: float | None = None, h: float | None = None,
          calib: int = 30) -> dict:
    """Tabular CUSUM: detect small sustained mean shifts in a series.

    C_t^+ = max(0, C^+_{t-1} + x_t - mu0 - k), C_t^- = max(0, C^-_{t-1} + mu0
    - k - x_t); signal when C^+ > h or C^- > h. ``mu0``/``sigma`` are
    calibrated on the first ``calib`` bars (the pre-shift baseline — the
    standard change-detection anchor), so a mean shift AFTER that window is
    detected as a genuine up/down shift rather than the base registering as
    "down" against the full-series mean. ``k = delta*sigma/2``,
    ``h = 5*sigma`` when not given (delta=1 shift). Returns
    ``{'mu0', 'sigma', 'k', 'h', 'signal', 'signal_at', 'max_cusum'}``;
    ``signal`` is ``up`` / ``down`` / ``None``.
    """
    vals = [float(v) for v in series if v is not None]
    if len(vals) < 20:
        return {"mu0": None, "sigma": None, "k": None, "h": None,
                "signal": None, "signal_at": None, "max_cusum": None}
    cal = max(10, min(int(calib), len(vals) // 3))
    base = vals[:cal]
    mu0 = sum(base) / len(base)
    sig = (sum((v - mu0) ** 2 for v in base) / (len(base) - 1)) ** 0.5 if len(base) > 1 else 0.0
    if sig <= 1e-12:
        return {"mu0": round(mu0, 6), "sigma": 0.0, "k": 0.0, "h": 0.0,
                "signal": None, "signal_at": None, "max_cusum": 0.0}
    kk = 0.5 * sig if k is None else float(k)
    hh = 5.0 * sig if h is None else float(h)
    cup = cdn = 0.0
    signal = None
    signal_at = None
    max_c = 0.0
    for i, x in enumerate(vals):
        cup = max(0.0, cup + x - mu0 - kk)
        cdn = max(0.0, cdn + mu0 - kk - x)
        max_c = max(max_c, cup, cdn)
        if signal is None:
            if cup > hh:
                signal, signal_at = "up", i
            elif cdn > hh:
                signal, signal_at = "down", i
    return {"mu0": round(mu0, 6), "sigma": round(sig, 6), "k": round(kk, 6),
            "h": round(hh, 6), "signal": signal, "signal_at": signal_at,
            "max_cusum": round(max_c, 6)}


def ewma_control(series: list, lambd: float = 0.2, l_width: float = 3.0) -> dict:
    """EWMA control chart: z_t = lambda*x_t + (1-lambda)*z_{t-1} with
    time-varying control limits mu0 +/- L*sigma*sqrt(lambda/(2-lambda) *
    (1 - (1-lambda)^(2t))). Detects slow drifts / small persistent shifts.

    ``lambd`` in (0, 1]; ``l`` = the control-limit width in sigma units.
    Returns ``{'mu0', 'sigma', 'lambda', 'L', 'signal', 'signal_at',
    'last_z'}``; ``signal`` = ``up``/``down``/``None``.
    """
    vals = [float(v) for v in series if v is not None]
    if len(vals) < 10 or not (0 < float(lambd) <= 1):
        return {"mu0": None, "sigma": None, "signal": None, "signal_at": None, "last_z": None}
    mu0 = sum(vals) / len(vals)
    sig = (sum((v - mu0) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
    if sig <= 1e-12:
        return {"mu0": round(mu0, 6), "sigma": 0.0, "signal": None,
                "signal_at": None, "last_z": mu0}
    lam = float(lambd)
    L = float(l_width)
    z = mu0
    signal = None
    signal_at = None
    for i, x in enumerate(vals, start=1):
        z = lam * x + (1.0 - lam) * z
        lim = L * sig * (lam / (2.0 - lam) * (1.0 - (1.0 - lam) ** (2 * i))) ** 0.5
        if signal is None:
            if z > mu0 + lim:
                signal, signal_at = "up", i - 1
            elif z < mu0 - lim:
                signal, signal_at = "down", i - 1
    return {"mu0": round(mu0, 6), "sigma": round(sig, 6), "lambda": lam, "L": L,
            "signal": signal, "signal_at": signal_at, "last_z": round(z, 6)}


def _student_t_pdf(x: float, df: float, loc: float, scale: float) -> float:
    """Student-t density (the Normal-Inverse-Gamma predictive law)."""
    if df <= 0.0 or scale <= 0.0:
        return 0.0
    z = (x - loc) / scale
    log_pdf = (
        math.lgamma((df + 1.0) / 2.0)
        - math.lgamma(df / 2.0)
        - 0.5 * math.log(df * math.pi)
        - math.log(scale)
        - ((df + 1.0) / 2.0) * math.log1p(z * z / df)
    )
    return math.exp(log_pdf)


#: Duration laws ``bocpd`` compiles a run-length-dependent hazard from.
#: ``constant`` is today's behaviour (a geometric run-length prior); the other
#: three are fitted to the segment lengths observed so far and re-estimated on
#: the expanding window. Anything else is refused (``None``), never guessed.
_HAZARD_MODES = ("constant", "lognormal", "pareto", "geometric")


def _fit_duration_law(mode: str, durations: list[int]) -> dict | None:
    """MLE duration-law parameters from observed segment lengths.

    ``durations`` must hold at least two observed lengths (the recursion only
    compiles once two runs exist). Returns ``None`` for a **degenerate** fit: a
    non-finite parameter, a zero-spread log-normal or Pareto (every observed run
    the same length, so the fit is a point mass rather than a duration
    distribution), or a geometric success probability outside ``(0, 1)``. The
    caller refuses the whole read on ``None``; the constant hazard is never
    substituted for it.
    """
    n = len(durations)
    d = [float(v) for v in durations]
    if mode == "lognormal":
        logs = [math.log(v) for v in d]
        mu = sum(logs) / n
        sigma = math.sqrt(sum((v - mu) ** 2 for v in logs) / n)
        if not (math.isfinite(mu) and math.isfinite(sigma)) or sigma <= 0.0:
            return None
        return {"law": "lognormal", "n_runs": n, "mu": mu, "sigma": sigma}
    if mode == "pareto":
        x_m = min(d)
        spread = sum(math.log(v / x_m) for v in d)
        if not (x_m > 0.0 and spread > 0.0):
            return None
        alpha = n / spread
        if not math.isfinite(alpha) or alpha <= 0.0:
            return None
        return {"law": "pareto", "n_runs": n, "x_m": x_m, "alpha": alpha}
    if mode == "geometric":
        p = n / sum(d)
        if not math.isfinite(p) or not (0.0 < p < 1.0):
            return None
        return {"law": "geometric", "n_runs": n, "p": p}
    return None


def _law_survival(fit: dict, x: float) -> float:
    """``P(D > x)`` of a fitted duration law (integer durations ``D >= 1``)."""
    if fit["law"] == "lognormal":
        if x <= 0.0:
            return 1.0
        z = (math.log(x) - fit["mu"]) / (fit["sigma"] * math.sqrt(2.0))
        return 0.5 * math.erfc(z)
    if fit["law"] == "pareto":
        if x <= fit["x_m"]:
            return 1.0
        return (fit["x_m"] / x) ** fit["alpha"]
    return (1.0 - fit["p"]) ** x


def _law_hazard(fit: dict, run_length: int) -> float:
    """Discrete hazard of a fitted duration law at a run length.

    ``P(D = r + 1 | D >= r + 1)`` - the probability that a segment which has
    reached ``r`` steps ends on the next one. ``0`` means the law forbids ending
    yet and ``1`` that it certainly ends, so the run-length prior stops
    asserting one constant chance of ending whatever the age. The ``1.0`` at a
    zero survival is the limit, not a floor; the clamp only absorbs rounding.
    """
    if fit["law"] == "geometric":
        return fit["p"]
    surv = _law_survival(fit, float(run_length))
    if surv <= 0.0:
        return 1.0
    h = 1.0 - _law_survival(fit, float(run_length) + 1.0) / surv
    return min(1.0, max(0.0, h))


def _segment_lengths(map_trace: list[int]) -> list[int]:
    """Segment lengths read off a MAP run-length trajectory.

    ``map_trace[t]`` is the posterior mode of the run length after point ``t``;
    a ``0`` means point ``t`` opened a fresh segment, so the zeros are the
    boundaries. A series that never restarts yields one segment of the full
    sample.
    """
    bounds = [i for i, r in enumerate(map_trace) if r == 0]
    if not bounds or bounds[0] != 0:
        bounds = [0, *bounds]
    return [
        (bounds[i + 1] if i + 1 < len(bounds) else len(map_trace)) - start
        for i, start in enumerate(bounds)
    ]


def _covering_metric(predicted: list[int], reference: list[int]) -> float | None:
    """Length-weighted Jaccard covering of two segmentations of one sample.

    Arbelaez-style covering, the metric the duration-law paper assesses with:
    every reference segment is weighted by its length and scored by its best
    per-pair Jaccard overlap against the predicted segmentation, and the score
    is the symmetric mean of both directions. ``1.0`` = the two segmentations
    agree everywhere, ``0.0`` = no segment pair overlaps; ``None`` when a side
    is empty and there is nothing to cover.
    """
    def _bounds(lengths: list[int]) -> list[tuple[int, int]]:
        out = []
        start = 0
        for length in lengths:
            out.append((start, start + length))
            start += length
        return out

    def _one_way(cover: list, target: list) -> float | None:
        total = sum(e - s for s, e in target)
        if total <= 0:
            return None
        acc = 0.0
        for s, e in target:
            span = e - s
            best = 0.0
            for s2, e2 in cover:
                overlap = min(e, e2) - max(s, s2)
                if overlap <= 0:
                    continue
                best = max(best, overlap / (span + (e2 - s2) - overlap))
            acc += span * best
        return acc / total

    forward = _one_way(_bounds(predicted), _bounds(reference))
    reverse = _one_way(_bounds(reference), _bounds(predicted))
    if forward is None or reverse is None:
        return None
    return 0.5 * (forward + reverse)


def _bocpd_recursion(
    z: list[float],
    prior: tuple,
    hazard: float,
    mu_prior: float,
    prior_df: float,
    prior_scale: float,
    law_mode: str | None,
    track: bool,
) -> tuple[dict, list[int], dict | None] | None:
    """One Adams-MacKay run-length pass over the standardised series ``z``.

    ``law_mode`` is ``None`` for the constant hazard ``hazard``. Otherwise the
    duration law is re-fitted at every step from the segment lengths observed so
    far - the completed runs plus the open run's age, a right-censored
    observation that extends as the window grows - and its compiled hazard
    drives the same recursion: an ``O(#runs)`` compile per step, an ``O(t)``
    step, and no sampling. Returns ``(posterior, map_trace, fit)``, or ``None``
    when a duration-law fit is degenerate, which the caller refuses on.
    ``map_trace`` is empty unless ``track`` is set; ``fit`` is the law in force
    at the last step, ``None`` while it is unidentified.
    """
    probs = {0: 1.0}
    params = {0: prior}
    trace: list[int] = []
    completed: list[int] = []
    prev_map: int | None = None
    fit: dict | None = None
    for x in z:
        active: dict | None = None
        if law_mode is not None and len(completed) + (prev_map is not None) >= 2:
            active = _fit_duration_law(law_mode, completed + [prev_map + 1])
            if active is None:
                return None
            fit = active
        if active is None:
            change_mass = hazard * _student_t_pdf(x, prior_df, mu_prior, prior_scale)
        else:
            change_mass = sum(
                p * _law_hazard(active, r) for r, p in probs.items()
            ) * _student_t_pdf(x, prior_df, mu_prior, prior_scale)
        grown_probs: dict[int, float] = {}
        grown_params: dict[int, tuple[float, float, float, float]] = {}
        for r, p in probs.items():
            hr = hazard if active is None else _law_hazard(active, r)
            mu, kap, alpha, beta = params[r]
            df = 2.0 * alpha
            scale = math.sqrt(beta * (kap + 1.0) / (alpha * kap))
            pred = _student_t_pdf(x, df, mu, scale)
            if pred <= 0.0:
                continue
            growth = p * pred * (1.0 - hr)
            new_kappa = kap + 1.0
            new_mu = (kap * mu + x) / new_kappa
            new_beta = beta + kap * (x - mu) ** 2 / (2.0 * new_kappa)
            grown_probs[r + 1] = grown_probs.get(r + 1, 0.0) + growth
            grown_params[r + 1] = (new_mu, new_kappa, alpha + 0.5, new_beta)
        grown_probs[0] = change_mass
        grown_params[0] = prior
        total = sum(grown_probs.values())
        if total <= 0.0:
            probs = {0: 1.0}
            params = {0: prior}
            continue
        probs = {r: p / total for r, p in grown_probs.items()}
        params = grown_params
        if track:
            current = max(probs, key=probs.get)
            if current == 0 and prev_map is not None:
                completed.append(prev_map + 1)
            prev_map = current
            trace.append(current)
    return probs, trace, fit


def _rounded_law(fit: dict | None) -> dict | None:
    """The duration-law parameters as reported (6dp), ``None`` if unidentified."""
    if fit is None:
        return None
    out: dict = {"law": fit["law"], "n_runs": fit["n_runs"]}
    for key in ("mu", "sigma", "x_m", "alpha", "p"):
        if key in fit:
            out[key] = round(float(fit[key]), 6)
    return out


def bocpd(
    series: list,
    hazard: float = 1.0 / 60.0,
    mu_prior: float = 0.0,
    kappa: float = 1.0,
    alpha_prior: float = 1.0,
    beta_prior: float = 1.0,
    warmup: int = 20,
    hazard_mode: str = "constant",
) -> dict | None:
    """Bayesian online change-point detection (Adams & MacKay 2007, arXiv:0710.3742).

    Models the series as piecewise i.i.d. Normal with an unknown mean and
    variance per segment; conjugate Normal-Inverse-Gamma prior
    ``NIG(mu_prior, kappa, alpha_prior, beta_prior)`` with a constant hazard
    ``1/hazard`` expected run length. Predictives are Student-t; the run-length
    posterior is updated online in O(n^2) time, deterministically (no sampling).

    Units: the input is standardised *internally* against the first ``warmup``
    observations (``z = (x - mean) / pstdev``) and BOCPD runs on those z-scores.
    This is causal (baseline uses only past points, never future ones) and lets
    the unit-scale NIG defaults apply unchanged to raw returns of any small
    magnitude; without it the diffuse default prior cannot see a mean shift in
    a percent-scale return series. Pass returns, not prices: the i.i.d.-within-
    segment assumption is what makes the level shift meaningful.

    ``shift`` is ``zero_run_prob >= BOCPD_SHIFT_THRESHOLD`` (module constant,
    0.5). A ``True`` read invalidates window-based statistics for the NEXT read:
    Hurst, variance-ratio and half-life are estimated on a window that straddles
    the break, so recompute them after the segment restarts (this function does
    not touch them).

    ``hazard_mode`` selects the run-length prior's hazard. ``constant`` (the
    default) is the constant hazard above, unchanged. ``lognormal``, ``pareto``
    or ``geometric`` compile it from an explicit duration law whose parameters
    are re-estimated on an expanding window from the segment lengths observed so
    far - the completed runs plus the open run's age - so a regime stops being
    as likely to end on its first day as on its hundredth. The law is
    unidentified until two run lengths have been observed and the declared
    scalar ``hazard`` (its geometric prior) governs until then; a **degenerate**
    fit - zero spread, a non-finite parameter, a geometric ``p`` outside
    ``(0, 1)`` - returns ``None`` exactly as an out-of-range ``hazard`` does,
    never the constant hazard. A duration-law mode also reports the
    ``duration_params`` in force, the compiled ``hazard_curve`` per run length
    that was actually applied, and ``covering``: the length-weighted Jaccard
    covering of this read's segmentation against the constant-hazard
    segmentation of the same series - no labelled segmentation exists in-run,
    so the reference is the read this one replaces, and the metric is what lets
    a change in hazard be judged rather than assumed.

    Returns ``{zero_run_prob, map_run_length, expected_run_length, shift, n,
    hazard, basis, hazard_mode}`` - plus ``duration_params``, ``hazard_curve``
    and ``covering`` for a duration-law mode - or ``None`` for degenerate input
    (fewer than ``warmup`` points, non-positive hazard, an unknown
    ``hazard_mode``, a degenerate duration-law fit, or a zero-variance warmup
    baseline).
    """
    vals = [float(v) for v in series if v is not None]
    n = len(vals)
    h = float(hazard)
    if int(warmup) < 2 or n < int(warmup) or not (0.0 < h < 1.0):
        return None
    if hazard_mode not in _HAZARD_MODES:
        return None
    base = vals[: int(warmup)]
    b_mean = sum(base) / len(base)
    b_std = pstdev(base)
    if b_std <= 1e-12:
        return None
    z = [(v - b_mean) / b_std for v in vals]

    prior = (float(mu_prior), float(kappa), float(alpha_prior), float(beta_prior))
    # prior predictive of the first point of a fresh segment (no data yet)
    prior_df = 2.0 * alpha_prior
    prior_scale = math.sqrt(beta_prior * (kappa + 1.0) / (alpha_prior * kappa))
    law_mode = None if hazard_mode == "constant" else hazard_mode
    run = _bocpd_recursion(
        z, prior, h, mu_prior, prior_df, prior_scale, law_mode, law_mode is not None
    )
    if run is None:
        return None
    probs, map_trace, fit = run

    zero_run_prob = float(probs.get(0, 0.0))
    map_run_length = max(probs, key=probs.get)
    expected_run_length = sum(r * p for r, p in probs.items())
    basis = (
        f"Adams-MacKay BOCPD, NIG prior mu={mu_prior},kappa={kappa},"
        f"alpha={alpha_prior},beta={beta_prior}, hazard={h:.6g}; "
        f"{n} standardized returns (baseline mean/std from first {int(warmup)} obs)"
    )
    out = {
        "zero_run_prob": round(zero_run_prob, 6),
        "map_run_length": int(map_run_length),
        "expected_run_length": round(float(expected_run_length), 4),
        "shift": bool(zero_run_prob >= BOCPD_SHIFT_THRESHOLD),
        "n": n,
        "hazard": h,
        "basis": basis,
        "hazard_mode": hazard_mode,
    }
    if law_mode is not None:
        runs = fit["n_runs"] if fit else 0
        out["basis"] = basis + (
            f"; hazard_mode={law_mode} (duration law from {runs} observed run"
            f"{'s' if runs != 1 else ''}; the scalar hazard is its prior until "
            f"two run lengths are observed)"
        )
        out["duration_params"] = _rounded_law(fit)
        out["hazard_curve"] = {
            int(r): round(h if fit is None else _law_hazard(fit, r), 6)
            for r in sorted(probs)
        }
        # No labelled segmentation exists in-run, so the covering metric is
        # taken against the constant-hazard segmentation of the same series -
        # the read this one replaces.
        reference = _bocpd_recursion(
            z, prior, h, mu_prior, prior_df, prior_scale, None, True
        )
        covered = _covering_metric(
            _segment_lengths(map_trace), _segment_lengths(reference[1])
        )
        out["covering"] = {
            "metric": "length_weighted_jaccard",
            "reference": "constant_hazard",
            "value": None if covered is None else round(covered, 6),
        }
    return out


# --- R3: the spectral null band (2607.06373) -------------------------------
#
# A spectrum estimated from a finite window moves on its own, so a move in the
# cross-section's eigenspace is only a regime signal when it exceeds the
# first-order null band 2607.06373 derives for a shrinkage estimator. The
# arithmetic lives beside the estimators it reads (`covariance_models.
# panel_spectrum` / `eigen_projector_distance` / `spectral_functionals`); what
# belongs HERE is the gated per-PANEL entry point, its coverage report and the
# wording of its verdicts.

#: R3's gate. Off by default: with it off ``spectral_change_read`` returns
#: ``None`` and no caller carries an extra key, so a gate-off run is
#: byte-identical to the run before the read existed.
#:
#: The gate is read by its **literal** key in :func:`_spectral_band_gate`
#: (docs/gate_registry.md §8): a read through this constant scans as "read by
#: nothing". The constant exists for the messages.
SPECTRAL_GATE_NAME = "enable_spectral_null_band"


def _spectral_band_gate(cfg: dict | None = None) -> bool:
    """Is R3's spectral null-band read switched on? (``enable_spectral_null_band``)

    Off by default, so a gate-off caller computes nothing new. An unreadable
    config leaves the gate off - a config read must never break the read it
    guards (the house shape: ``data_quality._coverage_gate``).
    """
    if cfg is None:
        try:
            from tradingagents.dataflows.config import get_config

            cfg = get_config() or {}
        except Exception:  # noqa: BLE001 - a config read must never break the read
            cfg = {}
    return bool((cfg or {}).get("enable_spectral_null_band", False))


def spectral_change_read(
    prev_window: dict,
    curr_window: dict,
    *,
    k: int = 1,
    min_n: int | None = None,
    shrinkage: float = 0.0,
    cfg: dict | None = None,
) -> dict | None:
    """R3: did the cross-section's eigenspace move further than estimation noise?

    2607.06373's finding is that a spectrum estimated from a finite window moves
    on its own - shrink an estimator and its leading eigenspace wanders - so
    reading a spectral move as structural change requires a calibrated null.
    This is the gated per-PANEL entry point, and the two windows are
    ``{name: [return, ...]}`` over the tracked cross-section: **never one
    symbol**, because the read needs a panel (and R3's bands are widest exactly
    where the book is smallest).

    ``None`` when ``enable_spectral_null_band`` is off (its default). Otherwise a
    record carrying three movements - the projector distance of the dominant
    ``k``-dimensional eigenspace, the absorption ratio, the leading-eigenvalue
    share - each beside **its own calibrated first-order null band**, plus:

    * ``flag`` - the read's single answer, and the only thing that feeds
      ``regime_score``. ``True`` when ANY leg's move exceeds its band, ``False``
      when every leg was measured and none did, and ``None`` when the panel could
      not be read.
    * ``window`` - ``n_obs`` / ``n_names`` / ``min_n``, reported beside the
      numbers. A window too thin to support a spectrum, a name set that changed
      between the two windows, or an unmeasurable shrinkage intensity is refused
      with its reason in ``unavailable`` (rule 4) - never a zero.
    * ``reading`` - ``"change detected"``, or ``"not detectable"`` with the
      paper's own caveat: a non-rejection partly reflects a wide null band, so it
      is **not** a statement that nothing changed.
    * ``band_calibration`` - the (window length, shrinkage intensity) pair the
      whole read is cut at, which is what makes the same length and intensity
      carry the same band on any panel.
    * ``shrinkage`` - the intensity the band was calibrated at (``0.0`` by
      default: the engine's correlation matrix read raw), and
      ``engine_shrinkage`` - the intensity the engine's OWN Ledoit-Wolf estimator
      applies to these windows, reported beside it and never folded into it. This
      engine's estimator saturates at ``1.0`` on every panel it has been asked
      about, and a band of zero is refused with its reason rather than flagging
      every move (see ``covariance_models._band_refusal``).

    ONE eigendecomposition per window: both windows are decomposed once, here,
    and the spectra are handed to every leg, so a rolling read costs two
    decompositions rather than one per functional.
    """
    if not _spectral_band_gate(cfg):
        return None
    from .covariance_models import (
        SPECTRAL_DETECTED,
        SPECTRAL_MIN_OBS,
        SPECTRAL_NOT_DETECTABLE_REASON,
        SPECTRAL_NULL_Z,
        SPECTRAL_UNAVAILABLE,
        _engine_shrinkage,
        eigen_projector_distance,
        panel_spectrum,
        spectral_functionals,
        spectral_null_band,
    )

    floor = SPECTRAL_MIN_OBS if min_n is None else int(min_n)
    prev = panel_spectrum(prev_window or {}, min_n=floor)
    curr = panel_spectrum(curr_window or {}, min_n=floor)
    projector = eigen_projector_distance(
        k=k,
        shrinkage=shrinkage,
        min_n=floor,
        prev_spectrum=prev,
        curr_spectrum=curr,
    )
    scalars = spectral_functionals(
        shrinkage=shrinkage,
        min_n=floor,
        prev_spectrum=prev,
        curr_spectrum=curr,
    )
    legs = (projector, scalars["absorption_ratio"], scalars["leading_share"])
    n_names = int(prev.get("n_names") or 0)
    n_obs = min(int(prev.get("n_obs") or 0), int(curr.get("n_obs") or 0))
    engine_shrinkage = _engine_shrinkage(prev, curr)
    delta = 0.0 if shrinkage is None else float(shrinkage)
    band = spectral_null_band(n_obs, delta)
    measured = all(leg.get("exceeds") is not None for leg in legs)
    flag = None
    reading = SPECTRAL_UNAVAILABLE
    unavailable = None
    if measured:
        flag = any(bool(leg["exceeds"]) for leg in legs)
        reading = SPECTRAL_DETECTED if flag else SPECTRAL_NOT_DETECTABLE_REASON
    else:
        unavailable = "; ".join(
            str(leg["unavailable"]) for leg in legs if leg.get("unavailable")
        ) or "the panel could not be read"
    return {
        "projector_distance": projector,
        "absorption_ratio": scalars["absorption_ratio"],
        "leading_share": scalars["leading_share"],
        "flag": flag,
        "reading": reading,
        "window": {"n_obs": n_obs, "n_names": n_names, "min_n": floor},
        "n_obs": n_obs,
        "n_names": n_names,
        "band_calibration": band,
        "shrinkage": delta,
        "engine_shrinkage": engine_shrinkage,
        "k": projector.get("k"),
        "status": "ADVISORY",
        "unavailable": unavailable,
        "basis": (
            f"R3 spectral null band (2607.06373): {n_names} name(s) x {n_obs} "
            f"observation(s), {len(legs)} movement(s) cut at one calibrated "
            f"first-order band {band if band is None else round(band, 6)} "
            f"(z={SPECTRAL_NULL_Z}, shrinkage {delta:.6g}); this band is a "
            f"function of the window length and the shrinkage intensity alone; "
            f"the engine's own Ledoit-Wolf intensity here is "
            f"{'-' if engine_shrinkage is None else format(engine_shrinkage, '.6f')} "
            f"(reported, not the band); flag={flag} ({reading}); the flag is what "
            f"`regime_score` takes - the absorption ratio and the projector "
            f"distance feed nothing"
        ),
    }


__all__ = [
    "realized_vol",
    "vol_percentile",
    "vol_percentile_read",
    "trend_strength",
    "choppiness",
    "CHOP_TREND_THRESHOLD",
    "regime_label",
    "hmm_regime",
    "hmm_filtered_regime",
    "regime_conditional_var",
    "EMISSION_FAMILIES",
    "EMISSION_NU",
    "EMISSION_BETA",
    "make_vol_series_of_closes",
    "regime_gate_read",
    "regime_state",
    "regime_factor",
    "cusum",
    "ewma_control",
    "bocpd",
    "BOCPD_SHIFT_THRESHOLD",
    "SPECTRAL_GATE_NAME",
    "spectral_change_read",
]


def _lazy_regime_state():
    """Late import: regime_state lives in regime_state.py (mirrors re-export)."""
    from tradingagents.strategies.regime_state import regime_factor, regime_state
    return regime_factor, regime_state


regime_factor, regime_state = _lazy_regime_state()
