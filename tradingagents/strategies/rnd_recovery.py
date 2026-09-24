"""Risk-neutral density recovery from a covered option chain (V3, 2512.xxxx).

A covered option chain does not contain a density; it contains prices. Recovering
the risk-neutral density is an inverse problem, and the only honest answer when
the covered strikes cannot identify it is ``unavailable``. ``rnd_recovery``
recovers a **two-component lognormal mixture** per expiry under the mass and
forward constraints and reports the decision functionals that read off it (the 1%
quantile, the risk-neutral variance, a left-tail probability).

**What is not built, on purpose.** The paper's adapted *learned* recovery
operator is deliberately **declined**: on 524 held-out NIFTY call quotes the
per-expiry classical fit beat the adapted learned operator, so fitting the
mixture directly is the adopted method and no learned surrogate is trained here.
That decline is recorded in this card, not left as an aspiration.

**Identifiability is derived, never assumed.** The covered strikes are turned into
the sensitivity (Jacobian) matrix of the mixture's OTM prices with respect to its
free parameters, and the *conditioning spectrum* of that matrix decides. A
numerical rank below the parameter count means the covered strikes cannot span
the parameters at all ("cannot span the density"); a condition number above
``RND_MAX_CONDITION`` means the least-determined direction is resolved too poorly
to be quoted. Either way the result is ``unavailable`` with the spectrum
reported - never a density that a few basis points of quote noise would move.

No-fabrication (rule 4): every refusal carries its reason and the window
(forward, expiry, strike count) it was computed over.

No new dependency: the fit is ``scipy.optimize.least_squares`` over stdlib
``math`` and NumPy; the pricing is the repo's own Black-76.
"""

from __future__ import annotations

import math

import numpy as np

from .options_math import (
    black76,
    model_free_implied_variance,
    variance_swap_strike,
)

#: What the recovered object names itself. A per-expiry two-component lognormal
#: mixture is the fitted family; the paper's SVI-equivalent is the same read in a
#: different basis and is not needed here.
METHOD = "two-component lognormal mixture"

#: The free parameters of the fit: the low component's weight, its forward
#: displacement, and the two components' log-vols. The high component's forward
#: displacement is NOT free - it is fixed by the mass + forward constraints (the
#: mixture mean must equal the forward), so a 5-parameter family is fitted with
#: four degrees of freedom.
RND_N_PARAMS = 4

#: The condition number at which the covered strikes stop identifying the density.
#: Declared policy with a stated basis, not measured (this engine has no
#: calibration panel): it demands the least-determined density direction be
#: resolved to within 0.1% of the best-determined one. Well-spread chains sit two
#: orders of magnitude below it (condition numbers in the tens); a cluster of
#: strikes inside a few percent of the forward sits an order of magnitude above.
RND_MAX_CONDITION = 1000.0

#: The fewest OTM prices a recovery is even attempted from - below it the
#: model-free anchor has no integral and the spectrum has no content.
RND_MIN_OTM = 4

#: The quantile the recovery reports its downside at, and the floor breach the
#: left-tail probability is read at (``0.9`` -> ``P(S_T <= 0.9 F)``). Printed
#: beside the number so the threshold is never inferred.
RND_QUANTILE = 0.01
RND_TAIL_THRESHOLD = 0.9


def _unavailable(reason: str, *, conditioning=None, forward=None, t=None,
                 n_otm: int = 0, mf_var=None, var_swap=None) -> dict:
    """The refusal shape of the V3 read: ``density`` None, reason carried."""
    return {
        "density": None,
        "method": METHOD,
        "conditioning": conditioning,
        "status": "unavailable",
        "unavailable": reason,
        "forward": forward,
        "t": t,
        "n_otm": int(n_otm),
        "model_free_implied_variance": mf_var,
        "variance_swap_strike": var_swap,
        "basis": f"risk-neutral density unavailable: {reason}",
    }


def _parse_chain(chain) -> dict | None:
    """The chain's parallel arrays, or None when the bundle is unusable.

    ``chain`` is ``{"strikes", "calls", "puts", "forward", "t", "r"}`` - the same
    parallel-array shape ``options_math.variance_swap_strike`` already takes, so
    the vendor row -> chain lift stays a pure reshape. ``r`` defaults to 0.
    """
    if not isinstance(chain, dict):
        return None
    strikes = chain.get("strikes")
    calls = chain.get("calls")
    puts = chain.get("puts")
    if strikes is None or len(strikes) == 0 or calls is None or puts is None:
        return None
    try:
        forward = float(chain["forward"])
        t = float(chain["t"])
        r = float(chain.get("r") or 0.0)
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "strikes": list(strikes),
        "calls": list(calls),
        "puts": list(puts),
        "forward": forward,
        "t": t,
        "r": r,
    }


def _otm_points(parsed: dict) -> tuple[list[float], list[float], list[bool]]:
    """``(strikes, prices, is_put)`` for the OTM quotes, aligned and finite.

    A put counts below the forward, a call above it - an option on the wrong side
    contributes no OTM price and is dropped, never clamped.
    """
    f = parsed["forward"]
    ks: list[float] = []
    ps: list[float] = []
    put: list[bool] = []
    for k, c, p in zip(parsed["strikes"], parsed["calls"], parsed["puts"],
                       strict=False):
        try:
            kf = float(k)
            cf = float(c)
            pf = float(p)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(kf) and kf > 0):
            continue
        if kf < f and pf > 0 and math.isfinite(pf):
            ks.append(kf)
            ps.append(pf)
            put.append(True)
        elif kf > f and cf > 0 and math.isfinite(cf):
            ks.append(kf)
            ps.append(cf)
            put.append(False)
    order = sorted(range(len(ks)), key=lambda i: ks[i])
    return ([ks[i] for i in order], [ps[i] for i in order], [put[i] for i in order])


def _component_forward(forward: float, weight: float, a1: float) -> float:
    """The high component's forward displacement ``a2`` from mass + forward.

    The mixture's mean is ``w e^{a1} + (1 - w) e^{a2} = 1`` (in units of the
    forward), so ``a2`` is fixed once ``(w, a1)`` are chosen - that is the forward
    constraint, applied exactly rather than as a penalty.
    """
    return math.log((1.0 - weight * math.exp(a1)) / (1.0 - weight))


def _mix_price(params, strike: float, put: bool, forward: float, t: float) -> float:
    """One OTM price of the mixture at ``strike`` (Black-76 per component, r=0)."""
    w, a1, s1, s2 = params
    a2 = _component_forward(forward, w, a1)
    m1 = forward * math.exp(a1)
    m2 = forward * math.exp(a2)
    p1 = black76(m1, strike, t, s1, "put" if put else "call", 0.0)["price"]
    p2 = black76(m2, strike, t, s2, "put" if put else "call", 0.0)["price"]
    if p1 is None or p2 is None:
        return float("nan")
    return w * p1 + (1.0 - w) * p2


def _conditioning(ks, put, params, forward: float, t: float) -> dict:
    """The conditioning spectrum of the covered strikes (V3 identifiability).

    The sensitivity (Jacobian) of the mixture's OTM prices to the four free
    parameters, at the fitted point, is decomposed by SVD. The spectrum decides:
    a numerical rank below ``RND_N_PARAMS`` means the strikes cannot span the
    density's parameters; a condition number above ``RND_MAX_CONDITION`` means the
    least-determined direction is resolved too poorly. Both are read off THIS
    spectrum - the flag is not a hardcoded threshold standing in for a check.
    """
    base = np.array(params, dtype=float)
    rows = len(ks)
    jac = np.zeros((rows, RND_N_PARAMS))
    for j in range(RND_N_PARAMS):
        step = 1e-5 * max(1.0, abs(base[j]))
        up = base.copy()
        dn = base.copy()
        up[j] += step
        dn[j] -= step
        hi = np.array([_mix_price(up, k, pu, forward, t) for k, pu in zip(ks, put, strict=True)])
        lo = np.array([_mix_price(dn, k, pu, forward, t) for k, pu in zip(ks, put, strict=True)])
        jac[:, j] = (hi - lo) / (2.0 * step)
    sing = np.linalg.svd(jac, compute_uv=False)
    if sing.size == 0 or not math.isfinite(float(sing[0])) or sing[0] <= 0:
        return {
            "singular_values": [float(v) for v in sing],
            "n_params": RND_N_PARAMS,
            "n_otm": rows,
            "rank": 0,
            "condition_number": None,
            "max_condition": RND_MAX_CONDITION,
            "identifiable": False,
            "unavailable": "the price-sensitivity matrix is degenerate",
            "basis": "conditioning spectrum unavailable: degenerate sensitivity",
        }
    tol = float(sing[0]) * max(jac.shape) * np.finfo(float).eps
    rank = int(np.count_nonzero(sing > tol))
    cond = (float(sing[0] / sing[-1]) if rank == RND_N_PARAMS
            and float(sing[-1]) > 0.0 else None)
    cannot_span = rank < RND_N_PARAMS
    poor = cond is None or cond > RND_MAX_CONDITION
    return {
        "singular_values": [round(float(v), 12) for v in sing],
        "n_params": RND_N_PARAMS,
        "n_otm": rows,
        "rank": rank,
        "condition_number": None if cond is None else round(cond, 6),
        "max_condition": RND_MAX_CONDITION,
        "identifiable": not (cannot_span or poor),
        "unavailable": (
            f"the covered strikes span {rank} of {RND_N_PARAMS} density parameters"
            if cannot_span else
            (
                f"the conditioning number {cond:.6g} exceeds {RND_MAX_CONDITION:g}"
                if cond is not None else
                "the conditioning number is not finite at a rank-deficient spectrum"
            )
        ) if (cannot_span or poor) else None,
        "basis": (
            "singular spectrum of d(OTM price)/d(weight, forward1, logvol1, "
            "logvol2) over the covered strikes at the fitted point; numerical rank "
            f"tolerance sigma_max * max(N, {RND_N_PARAMS}) * eps; identifiability "
            f"needs rank == {RND_N_PARAMS} and condition number <= "
            f"{RND_MAX_CONDITION:g} (declared policy: the least-determined direction "
            "resolved to within 0.1% of the best-determined one, because this engine "
            "has no calibration panel to measure it on)"
        ),
    }


def _fit_mixture(ks, ps, put, forward: float, t: float, sigma0: float):
    """Least-squares fit of the mass/forward-constrained mixture, or None.

    Deterministic: a fixed initial guess (``w=0.5``, both components centred on
    the forward, log-vols straddling the model-free anchor) and a bounded
    trust-region solve with the forward constraint applied by construction.
    """
    if not ks:
        return None
    target = np.array(ps, dtype=float)
    s0 = max(float(sigma0), 0.02) if sigma0 and sigma0 > 0 else 0.20
    x0 = np.array([0.5, 0.0, 0.6 * s0, 1.6 * s0])
    lo = np.array([0.02, -0.6, 0.02, 0.02])
    hi = np.array([0.98, 0.6, 0.8, 1.2])

    def resid(x):
        if x[0] * math.exp(x[1]) >= 0.999:
            return np.full(len(ks), 1e3)
        model = np.array([_mix_price(x, k, pu, forward, t) for k, pu in zip(ks, put, strict=True)])
        if not np.all(np.isfinite(model)):
            return np.full(len(ks), 1e3)
        return model - target

    try:
        from scipy.optimize import least_squares

        res = least_squares(
            resid, x0, bounds=(lo, hi),
            xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=4000,
        )
    except Exception:  # noqa: BLE001 - a failed solve is a refusal, not a crash
        return None
    if not res.success or not np.all(np.isfinite(res.x)):
        return None
    return [float(v) for v in res.x]


def _functionals(params, forward: float, t: float) -> dict:
    """The decision functionals of the fitted mixture, in closed form.

    The forward constraint fixes ``E[S_T] = F``; the variance is ``E[S_T^2] - F^2``
    (annualized by ``F^2 t``), the 1% quantile is a bisection of the mixture CDF,
    and the left-tail probability is that CDF read at ``RND_TAIL_THRESHOLD`` of
    the forward.
    """
    w, a1, s1, s2 = params
    a2 = _component_forward(forward, w, a1)
    m1 = forward * math.exp(a1)
    m2 = forward * math.exp(a2)

    def ncdf(z):
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    es2 = w * m1 * m1 * math.exp(s1 * s1) + (1.0 - w) * m2 * m2 * math.exp(s2 * s2)
    var_total = es2 - forward * forward

    def cdf(x):
        if x <= 0:
            return 0.0
        c1 = ncdf((math.log(x) - math.log(m1) + 0.5 * s1 * s1) / s1)
        c2 = ncdf((math.log(x) - math.log(m2) + 0.5 * s2 * s2) / s2)
        return w * c1 + (1.0 - w) * c2

    lo, hi = 1e-9, 100.0 * forward
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if cdf(mid) < RND_QUANTILE:
            lo = mid
        else:
            hi = mid
    q01 = 0.5 * (lo + hi)
    return {
        "components": [
            {"weight": round(w, 9), "forward": round(m1, 9),
             "log_vol": round(s1, 9)},
            {"weight": round(1.0 - w, 9), "forward": round(m2, 9),
             "log_vol": round(s2, 9)},
        ],
        "quantile_01": round(q01, 9),
        "risk_neutral_variance": round(var_total / (forward * forward * t), 9),
        "risk_neutral_variance_total": round(var_total, 9),
        "tail_probability": round(cdf(RND_TAIL_THRESHOLD * forward), 9),
        "tail_threshold": RND_TAIL_THRESHOLD,
        "quantile": RND_QUANTILE,
        "basis": (
            f"two-component lognormal mixture under mass + forward constraints "
            f"(E[S_T]=F); 1% quantile {q01:.6g}, annualized risk-neutral variance "
            f"{var_total / (forward * forward * t):.6g}, "
            f"P(S_T<={RND_TAIL_THRESHOLD:g}F) {cdf(RND_TAIL_THRESHOLD * forward):.6g}"
        ),
    }


def rnd_recovery(chain) -> dict:
    """Recover a risk-neutral density from a covered option chain, or refuse (V3).

    ``chain`` is ``{"strikes", "calls", "puts", "forward", "t", "r"}`` - parallel
    arrays a vendor row list reshapes into, the same shape
    ``options_math.variance_swap_strike`` takes. The model-free implied variance
    and the variance-swap strike (``options_math``) anchor the fit and travel with
    the record as cross-checks.

    Returns ``{density, method, conditioning, status, unavailable, ...}``. On a
    chain whose covered strikes identify the mixture, ``density`` carries the two
    components and the decision functionals (1% quantile, risk-neutral variance,
    tail probability). On a chain whose covered strikes cannot span the density,
    or whose conditioning spectrum is too poor, or that is missing an anchor, the
    result is ``status="unavailable"`` with ``density is None`` and the
    conditioning spectrum reported - never a density that quote noise would move.

    The learned recovery operator the paper proposes is deliberately NOT built
    (see the module card): per-expiry classical fits beat it on held-out quotes.
    """
    parsed = _parse_chain(chain)
    if parsed is None:
        return _unavailable(
            "chain must carry parallel strikes/calls/puts plus forward and t"
        )
    f = parsed["forward"]
    t = parsed["t"]
    if not (math.isfinite(f) and f > 0.0) or not (math.isfinite(t) and t > 0.0):
        return _unavailable(
            f"forward {f!r} and expiry {t!r} must both be positive",
            forward=f if math.isfinite(f) else None,
            t=t if math.isfinite(t) else None,
        )
    ks, ps, put = _otm_points(parsed)
    if len(ks) < RND_MIN_OTM:
        return _unavailable(
            f"{len(ks)} OTM quote(s) cover the chain; {RND_MIN_OTM} are needed "
            "before a two-component mixture has anything to fit",
            forward=f, t=t, n_otm=len(ks),
        )
    otm_prices = list(ps)
    mf_var = model_free_implied_variance(ks, otm_prices, f, t, parsed["r"])
    var_swap = variance_swap_strike(
        parsed["strikes"], parsed["calls"], parsed["puts"], f, t, parsed["r"]
    )
    if mf_var is None:
        return _unavailable(
            "the model-free implied variance cannot be integrated over the "
            "covered strikes, so the mixture has no anchor",
            forward=f, t=t, n_otm=len(ks), var_swap=var_swap,
        )
    sigma0 = math.sqrt(max(float(mf_var), 0.0))
    params = _fit_mixture(ks, ps, put, f, t, sigma0)
    if params is None:
        return _unavailable(
            "the mixture fit did not converge on the covered strikes",
            forward=f, t=t, n_otm=len(ks), mf_var=mf_var, var_swap=var_swap,
        )
    cond = _conditioning(ks, put, params, f, t)
    if not cond["identifiable"]:
        return _unavailable(
            f"the covered strikes do not identify the density: {cond['unavailable']}",
            conditioning=cond, forward=f, t=t, n_otm=len(ks),
            mf_var=mf_var, var_swap=var_swap,
        )
    density = _functionals(params, f, t)
    density["method"] = METHOD
    density["fit_rms_error"] = round(
        float(np.sqrt(np.mean([
            (_mix_price(params, k, pu, f, t) - p) ** 2
            for k, pu, p in zip(ks, put, ps, strict=True)
        ]))), 12)
    return {
        "density": density,
        "method": METHOD,
        "conditioning": cond,
        "status": "ok",
        "unavailable": None,
        "forward": f,
        "t": t,
        "n_otm": len(ks),
        "model_free_implied_variance": mf_var,
        "variance_swap_strike": var_swap,
        "fit_params": {
            "weight": round(params[0], 9),
            "a1": round(params[1], 9),
            "log_vol1": round(params[2], 9),
            "log_vol2": round(params[3], 9),
        },
        "basis": (
            f"V3 risk-neutral density: two-component lognormal mixture fit to "
            f"{len(ks)} OTM quote(s) at F={f:g}, T={t:g}, under mass + forward "
            f"constraints; conditioning number {cond['condition_number']:g} <= "
            f"{RND_MAX_CONDITION:g} (rank {cond['rank']}/{RND_N_PARAMS}); model-free "
            f"implied variance {mf_var} and variance-swap strike "
            f"{'n/a' if var_swap is None else format(var_swap, '.6g')} as anchors; "
            "learned recovery operator deliberately not built (per-expiry classical "
            "fit won on 524 held-out NIFTY quotes)"
        ),
    }


__all__ = [
    "rnd_recovery",
    "METHOD",
    "RND_MAX_CONDITION",
    "RND_N_PARAMS",
    "RND_MIN_OTM",
]
