"""Phase 1 - market-regime gate.

Deterministic features first: realized volatility (21d percentile vs a
reference window), 200-SMA trend, and a choppiness proxy (close/open vs
high-low proximity). An optional 2-3 state hidden Markov model (hmmlearn)
labels bull/bear/choppy when installed; the deterministic path is always
available and testable offline.

Wire-up: compute features from daily OHLCV in a pre-graph step, stash
`regime` in graph state, and let the risk node scale position size /
stop levels and analysts frame their lens (bull/bear context).
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


def vol_percentile(history: list[list[float]], current_window: int = 21) -> float:
    """Percentile rank (0-1) of the latest realized vol vs all history windows."""
    wins = []
    for close in history:
        wins.append(make_vol_series_of_closes(close, window=current_window))
    if not wins or len(wins) < 2:
        return 0.5
    recent = wins[-1]
    below = sum(1 for w in wins if w <= recent)
    return below / len(wins)


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
               lows: list | None = None, window: int = 14) -> float:
    """Canonical Choppiness Index (Dreiss 1990s), 0-100 scale.

    CHOP = 100 * log10(sum(ATR_i, n) / (HH(n) - LL(n))) / log10(n). High =
    ranging/choppy, low = trending. Requires OHLC; when only closes are given
    (no high/low) falls back to the 0-1 log-return-dispersion proxy so callers
    that only carry closes still get a bounded regime read. The old behavior
    (std of log returns on the 0-1 scale) was NOT the CHOP index and inverted
    the semantics (high = volatile instead of ranging).
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
    # fallback: 0-1 log-return dispersion proxy (close-only series)
    logrets = []
    prev = c[0] if c else None
    for p in c[1:]:
        if prev and prev > 0 and p > 0:
            logrets.append(math.log(p / prev))
        prev = p
    sample = logrets[-n:]
    if len(sample) < 3:
        return 0.5
    return float(pstdev(sample) or 0.5)


def regime_label(
    vol_pct: float,
    trend: float,
    chop: float,
    vol_hi: float = 0.75,
    vol_lo: float = 0.25,
    trend_threshold: float = 0.02,
    chop_threshold: float = 0.30,
) -> str:
    """Rule-based regime: high-vol | bull | bear | choppy (fallback neutral).

    Priority: volatility state first (risk gate), then trend, then choppiness.
    """
    if vol_pct >= vol_hi:
        return "high_vol"
    if vol_pct <= vol_lo and abs(trend) >= trend_threshold:
        return "bull" if trend > 0 else "bear"
    if chop <= chop_threshold:
        return "bull" if trend > 0 else "bear"
    return "neutral"


def hmm_regime(close: list[float], n_states: int = 2) -> str:
    """Optional HMM label; falls back to 'unknown' without hmmlearn."""
    try:
        import numpy as np
        from hmmlearn.hmm import GaussianHMM

        rets = np.array(close[1:]) / np.maximum(np.array(close[:-1]), 1e-9) - 1.0
        rets = rets[:, None]
        if len(rets) < 20 or np.ptp(rets) == 0:
            return "unknown"
        model = GaussianHMM(
            n_components=n_states, covariance_type="full", n_iter=50, random_state=7
        )
        model.fit(rets)
        state = model.predict(rets)[-1]
        means = model.means_.reshape(-1)
        # state with higher mean = bullish regime
        return "bull" if means[state] == max(means) else "bear"
    except Exception:
        return "unknown"




def _sma(series: list, n: int) -> float | None:
    if len(series) < n or n <= 0:
        return None
    return sum(float(x) for x in series[-n:]) / n


def regime_gate_read(
    closes: list,
    cfg: dict | None = None,
    catalyst_window: bool = False,
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
    * ``catalyst_window`` - caller-supplied (events/catalyst overlay).
    * ``pass`` - False when high-vol (``value_dip_regime_vol_cap``, default
      0.8) OR fast_downtrend OR catalyst_window. ADVISORY: this function never
      blocks anything; hard-gating is opt-in at the caller via ``require_regime``
      so existing scans keep their behaviour.
    """
    cfg = cfg or {}
    vol_cap = float(cfg.get("value_dip_regime_vol_cap", 0.8))
    band = float(cfg.get("value_dip_regime_downtrend_band", 0.08))
    if not closes or len(closes) < 60:
        return {
            "pass": None, "verdict": "unknown", "vol_pct": None,
            "fast_downtrend": None, "above_sma200": None, "sma50_rising": None,
            "index_vol_pct": None, "market_stress": None,
            "catalyst_window": bool(catalyst_window), "reasons": ["insufficient history"],
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
    blocked = bool(high_vol or fast_downtrend or market_stress or catalyst_window)
    verdict = (
        "high-vol"
        if high_vol
        else ("fast-downtrend" if fast_downtrend else ("catalyst-window" if catalyst_window else "tradable"))
    )
    reasons = []
    if high_vol:
        reasons.append(f"vol_pct {vol_pct:.2f} > cap {vol_cap:.2f}")
    if fast_downtrend:
        reasons.append(f"price {band:.0%}+ below falling 200-SMA (knife guard)")
    if market_stress:
        reasons.append(f"market stress: index_vol_pct {index_vol_pct:.2f} > cap {market_vol_cap:.2f}")
    if catalyst_window:
        reasons.append("catalyst window open")
    if not blocked:
        reasons.append("volatility contained + no fast downtrend + no catalyst")
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
        "catalyst_window": bool(catalyst_window),
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


def bocpd(
    series: list,
    hazard: float = 1.0 / 60.0,
    mu_prior: float = 0.0,
    kappa: float = 1.0,
    alpha_prior: float = 1.0,
    beta_prior: float = 1.0,
    warmup: int = 20,
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

    Returns ``{zero_run_prob, map_run_length, expected_run_length, shift, n,
    hazard, basis}`` or ``None`` for degenerate input (fewer than ``warmup``
    points, non-positive hazard, or a zero-variance warmup baseline).
    """
    vals = [float(v) for v in series if v is not None]
    n = len(vals)
    h = float(hazard)
    if int(warmup) < 2 or n < int(warmup) or not (0.0 < h < 1.0):
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
    probs = {0: 1.0}
    params = {0: prior}
    for x in z:
        grown_probs: dict[int, float] = {}
        grown_params: dict[int, tuple[float, float, float, float]] = {}
        change_mass = h * _student_t_pdf(x, prior_df, mu_prior, prior_scale)
        for r, p in probs.items():
            mu, kap, alpha, beta = params[r]
            df = 2.0 * alpha
            scale = math.sqrt(beta * (kap + 1.0) / (alpha * kap))
            pred = _student_t_pdf(x, df, mu, scale)
            if pred <= 0.0:
                continue
            growth = p * pred * (1.0 - h)
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

    zero_run_prob = float(probs.get(0, 0.0))
    map_run_length = max(probs, key=probs.get)
    expected_run_length = sum(r * p for r, p in probs.items())
    basis = (
        f"Adams-MacKay BOCPD, NIG prior mu={mu_prior},kappa={kappa},"
        f"alpha={alpha_prior},beta={beta_prior}, hazard={h:.6g}; "
        f"{n} standardized returns (baseline mean/std from first {int(warmup)} obs)"
    )
    return {
        "zero_run_prob": round(zero_run_prob, 6),
        "map_run_length": int(map_run_length),
        "expected_run_length": round(float(expected_run_length), 4),
        "shift": bool(zero_run_prob >= BOCPD_SHIFT_THRESHOLD),
        "n": n,
        "hazard": h,
        "basis": basis,
    }


__all__ = [
    "realized_vol",
    "vol_percentile",
    "trend_strength",
    "choppiness",
    "regime_label",
    "hmm_regime",
    "make_vol_series_of_closes",
    "regime_gate_read",
    "regime_state",
    "regime_factor",
    "cusum",
    "ewma_control",
    "bocpd",
    "BOCPD_SHIFT_THRESHOLD",
]


def _lazy_regime_state():
    """Late import: regime_state lives in regime_state.py (mirrors re-export)."""
    from tradingagents.strategies.regime_state import regime_factor, regime_state
    return regime_factor, regime_state


regime_factor, regime_state = _lazy_regime_state()
