"""Synthetic-null workflow falsification (H3; paper 2604.15531).

``tradingagents.strategies.falsification`` falsifies a **thesis** - numeric
invalidation levels bound to a claim. Nothing there falsifies a **pipeline**.
This module does: it runs a workflow's walk-forward winner over synthetic data
that contains no signal, and asks whether the workflow still reports some.

Two stages, per the paper:

* **Stage 1 - the null-environment harness.** Five reference classes - white
  noise, two-state regime-switching volatility, a bid-ask-bounce price bar, a
  single mean-zero factor plus noise, and GARCH(1,1) - each generated
  ``N = 1000`` times; the workflow's walk-forward winner is computed on every
  replication and the environment's empirical ``(1-alpha)`` quantile becomes
  the **null band**. A winner reported above that band is falsified: it found
  "signal" in data built to hold none.
* **Stage 2 - the inflation diagnostics** (:func:`evaluate.inflation_diagnostics`):
  ``Delta_Z = Z*_IS - Z*_WF`` and ``K_eff`` (the effective number of
  independent candidates), read once from the retained candidate matrix that
  H1's trial ledger is what makes possible.

The paper's headline is the one to carry alongside every reading: the
familywise false-positive probability of a search is **5.3% at K = 1 and 92.3%
at K = 50** - a search of fifty candidates will find something. It is stated in
:data:`FAMILYWISE_FALSE_POSITIVE`.

**OFFLINE by construction** (survey ground rule 8): ``5 x 1000`` full-pipeline
replays are prohibitive in-run, so this module MUST NOT be called from
``prepare_initial_state``, ``finalize_run`` or any agent tool. The first caller
is ``scripts/null_harness.py``.

**Caveat, carried from the paper.** This is a necessary-condition screen, not a
certification, and a pipeline can be tuned to pass it.
"""

from __future__ import annotations

import math
import random

from tradingagents.strategies.evaluate import z_statistic

#: The five reference classes the harness runs under, by name.
REFERENCE_CLASSES = (
    "white_noise",
    "regime_switching_volatility",
    "bid_ask_bounce",
    "single_factor",
    "garch11",
)

#: 2604.15531's own headline, carried verbatim: the familywise false-positive
#: probability of a search over ``K`` candidates. Not re-derived here - the point
#: is to state the risk the instrument exists to price.
FAMILYWISE_FALSE_POSITIVE = {1: 0.053, 50: 0.923}

_DEFAULT_N_OBS = 252
_DEFAULT_REPLICATIONS = 1000
_DEFAULT_ALPHA = 0.05
_BASE_SIGMA = 0.01

#: The momentum lookbacks the reference candidate set searches - a seven-candidate
#: zoo, enough that a search's in-sample maximum visibly exceeds one candidate's
#: walk-forward value while staying cheap enough to replay 1000 times.
_LOOKBACKS = (2, 3, 5, 8, 13, 21, 34)


def _white_noise(n: int, rng: random.Random) -> list[float]:
    return [rng.gauss(0.0, _BASE_SIGMA) for _ in range(n)]


def _regime_switching_volatility(n: int, rng: random.Random) -> list[float]:
    """Two-state Markov volatility: mean-zero returns, the *vol* switches."""
    low, high = _BASE_SIGMA * 0.5, _BASE_SIGMA * 2.0
    sigma = low
    out: list[float] = []
    for _ in range(n):
        if rng.random() < 0.05:
            sigma = high if sigma == low else low
        out.append(rng.gauss(0.0, sigma))
    return out


def _bid_ask_bounce(n: int, rng: random.Random) -> list[float]:
    """A random-walk efficient price observed through a flipping half-spread."""
    half = _BASE_SIGMA * 0.25
    mid = 0.0
    sign = 1.0
    prev: float | None = None
    out: list[float] = []
    for _ in range(n):
        mid += rng.gauss(0.0, _BASE_SIGMA)
        if rng.random() < 0.5:
            sign = -sign
        observed = mid + sign * half
        out.append(0.0 if prev is None else observed - prev)
        prev = observed
    return out


def _single_factor(n: int, rng: random.Random) -> list[float]:
    """One mean-zero common factor plus idiosyncratic noise - still unpredictable."""
    return [
        rng.gauss(0.0, _BASE_SIGMA) + rng.gauss(0.0, _BASE_SIGMA)
        for _ in range(n)
    ]


def _garch11(n: int, rng: random.Random) -> list[float]:
    omega = _BASE_SIGMA ** 2 * 0.1
    alpha, beta = 0.1, 0.8
    var = omega / (1.0 - alpha - beta)
    shock = 0.0
    out: list[float] = []
    for _ in range(n):
        var = omega + alpha * shock * shock + beta * var
        shock = math.sqrt(var) * rng.gauss(0.0, 1.0)
        out.append(shock)
    return out


_GENERATORS = {
    "white_noise": _white_noise,
    "regime_switching_volatility": _regime_switching_volatility,
    "bid_ask_bounce": _bid_ask_bounce,
    "single_factor": _single_factor,
    "garch11": _garch11,
}


def generate_null(reference_class: str, n_obs: int = _DEFAULT_N_OBS, *,
                  seed: int = 0) -> list[float]:
    """One synthetic null sample of ``n_obs`` mean-zero returns.

    Deterministic given ``seed``. Raises ``ValueError`` on an unknown class so a
    typo names itself rather than silently falling back to a default.
    """
    if reference_class not in _GENERATORS:
        raise ValueError(
            f"unknown reference class {reference_class!r}; "
            f"choose from {', '.join(REFERENCE_CLASSES)}"
        )
    return _GENERATORS[reference_class](int(n_obs), random.Random(seed))


def empirical_null_band(samples: list[float],
                        alpha: float = _DEFAULT_ALPHA) -> dict:
    """The environment's empirical ``(1-alpha)`` quantile over ``samples``.

    The quantile is the inverted-empirical-CDF order statistic
    ``sorted[ceil((1-alpha)*n) - 1]``, clamped into range - the value the paper
    compares a winner against. Returns ``quantile=None`` with ``n_usable`` on an
    empty or all-non-finite input: a band with no samples is a refusal, not zero.
    """
    vals = sorted(float(v) for v in samples if _finite(v))
    n = len(vals)
    if n == 0:
        return {"quantile": None, "n_usable": 0, "alpha": float(alpha)}
    rank = max(1, min(n, math.ceil((1.0 - float(alpha)) * n)))
    return {"quantile": vals[rank - 1], "n_usable": n, "alpha": float(alpha)}


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def run_null_harness(pipeline, *, reference_class: str = "white_noise",
                     n_replications: int = _DEFAULT_REPLICATIONS,
                     alpha: float = _DEFAULT_ALPHA,
                     n_obs: int = _DEFAULT_N_OBS, seed: int = 0) -> dict:
    """Stage 1: the null band for ``pipeline`` under one reference class.

    ``pipeline(returns) -> float`` is the workflow's walk-forward winner: a
    caller passes the procedure that reports the strongest statistic a search
    surfaced. The harness draws ``n_replications`` null samples (seeds
    ``seed .. seed+n-1``), evaluates the winner on each, and returns the
    environment's ``(1-alpha)`` quantile beside the distribution's location and
    spread. The band is what noise alone produces; a workflow that reports above
    it has been falsified (:func:`falsify_workflow`).

    A pipeline that raises on a draw is skipped, never read as zero, and
    ``n_usable`` reports how many draws actually counted.
    """
    stats: list[float] = []
    for i in range(int(n_replications)):
        data = generate_null(reference_class, n_obs, seed=int(seed) + i)
        try:
            value = float(pipeline(data))
        except Exception:  # noqa: BLE001 - one bad draw is skipped, not fatal
            continue
        if math.isfinite(value):
            stats.append(value)
    band = empirical_null_band(stats, alpha)
    n = len(stats)
    mean = sum(stats) / n if n else None
    stdev = (math.sqrt(sum((s - mean) ** 2 for s in stats) / (n - 1))
             if n > 1 and mean is not None else None)
    return {
        "reference_class": reference_class,
        "n_replications": int(n_replications),
        "n_usable": n,
        "alpha": float(alpha),
        "quantile": band["quantile"],
        "mean": mean,
        "stdev": stdev,
        "min": min(stats) if n else None,
        "max": max(stats) if n else None,
        "familywise_false_positive": dict(FAMILYWISE_FALSE_POSITIVE),
        "basis": (
            f"H3 (2604.15531) Stage 1 null band: {n} usable of "
            f"{int(n_replications)} replays under {reference_class} "
            f"(n_obs={int(n_obs)}, seed={int(seed)}); the empirical "
            f"{1.0 - float(alpha):.0%} quantile of the walk-forward winner is "
            f"{band['quantile']}; a winner above it is a false positive - the "
            "familywise rate is 5.3% at K=1 and 92.3% at K=50"
        ),
    }


def falsify_workflow(observed_statistic: float, band: dict) -> dict:
    """Stage 1 verdict: is ``observed_statistic`` inside the null band?

    ``falsified`` is ``True`` when a workflow's reported winner exceeds the
    environment's empirical ``(1-alpha)`` quantile - it produced "skill" from
    data with no signal in it. A missing band (``quantile is None``) is a refusal
    (``verdict="unavailable"``), never a pass.
    """
    quantile = band.get("quantile") if isinstance(band, dict) else None
    observed = float(observed_statistic)
    if quantile is None or not math.isfinite(observed):
        return {
            "falsified": None,
            "verdict": "unavailable",
            "observed": observed if math.isfinite(observed) else None,
            "quantile": quantile,
            "alpha": band.get("alpha") if isinstance(band, dict) else None,
            "basis": "H3: no usable null band to compare against",
        }
    quantile = float(quantile)
    falsified = observed > quantile
    return {
        "falsified": falsified,
        "verdict": "exceeds_null_band" if falsified else "inside_null_band",
        "observed": observed,
        "quantile": quantile,
        "alpha": band.get("alpha"),
        "reference_class": band.get("reference_class"),
        "basis": (
            f"H3 (2604.15531): walk-forward winner {observed:.4f} vs the "
            f"{band.get('reference_class')} null band {quantile:.4f} "
            f"(alpha={band.get('alpha')}); "
            + ("OUTSIDE - a false positive, the pipeline reports signal in noise"
               if falsified else "inside - consistent with no signal")
        ),
    }


def _rule_returns(returns: list[float], lookback: int) -> list[float]:
    """A momentum rule's per-period return: sign(trailing mean over L) * r_t."""
    out: list[float] = []
    for t in range(len(returns)):
        if t < lookback:
            out.append(0.0)
            continue
        past = returns[t - lookback:t]
        signal = 1.0 if sum(past) > 0.0 else -1.0
        out.append(signal * returns[t])
    return out


def reference_pipeline(returns: list[float], *,
                       lookbacks: tuple[int, ...] = _LOOKBACKS) -> float:
    """The honest walk-forward winner: select on IS, report that candidate's OOS.

    The candidate with the strongest in-sample ``|Z_IS,k|`` is chosen on the
    first half, and the statistic reported is **that one candidate's**
    out-of-sample ``|Z_WF|`` - a single value, not the out-of-sample maximum.
    This is the asymmetry the paper measures: honest selection lands on a
    candidate whose OOS z is ordinary (their walk-forward mean is 0.80), while a
    workflow that reports the in-sample maximum shows its search's inflation
    (their in-sample mean is 2.79 at K=100). Under a null the honest winner sits
    inside the band; :func:`leaky_pipeline` reports the inflated maximum.
    """
    vals = [float(v) for v in returns if _finite(v)]
    half = len(vals) // 2
    chosen: int | None = None
    best = -1.0
    for lb in lookbacks:
        z = z_statistic(_rule_returns(vals, lb)[:half])
        if z is not None and abs(z) > best:
            best = abs(z)
            chosen = lb
    if chosen is None:
        return 0.0
    out = z_statistic(_rule_returns(vals, chosen)[half:])
    return abs(out) if out is not None else 0.0


def leaky_pipeline(returns: list[float], *,
                   lookbacks: tuple[int, ...] = _LOOKBACKS) -> float:
    """The planted leak: ``max_k |Z_IS,k|`` - selection and report both in-sample.

    A workflow that selects its candidate on the in-sample half and reports that
    same in-sample statistic is showing inflation, not skill. Under a null its
    winner exceeds the band, which is the failing-first proof the H3 card names.
    """
    vals = [float(v) for v in returns if _finite(v)]
    half = len(vals) // 2
    zs = [abs(z) for lb in lookbacks
          if (z := z_statistic(_rule_returns(vals, lb)[:half])) is not None]
    return max(zs) if zs else 0.0


def candidate_matrix(returns: list[float], *,
                     lookbacks: tuple[int, ...] = _LOOKBACKS
                     ) -> tuple[list[list[float]], list[list[float]]]:
    """The Stage-2 ``(in_sample, walk_forward_winner)`` series matrices.

    ``in_sample`` is one row per candidate: the rule's per-period return series
    over the first half. ``walk_forward_winner`` is a **single** row - the
    candidate the honest procedure selects on the first half, carried over the
    second half. These are the two matrices :func:`evaluate.inflation_diagnostics`
    reads ``Delta_Z`` from, and the asymmetry is the point: the search's
    in-sample maximum is compared against the **one** candidate it selected,
    walk-forward - the retained candidate matrix the H1 ledger makes possible.
    """
    vals = [float(v) for v in returns if _finite(v)]
    half = len(vals) // 2
    is_rows: list[list[float]] = []
    best = -1.0
    chosen = lookbacks[0] if lookbacks else None
    for lb in lookbacks:
        series = _rule_returns(vals, lb)
        is_rows.append(series[:half])
        z = z_statistic(series[:half])
        if z is not None and abs(z) > best:
            best = abs(z)
            chosen = lb
    wf_rows: list[list[float]] = []
    if chosen is not None:
        wf_rows.append(_rule_returns(vals, chosen)[half:])
    return is_rows, wf_rows


__all__ = [
    "REFERENCE_CLASSES",
    "FAMILYWISE_FALSE_POSITIVE",
    "generate_null",
    "empirical_null_band",
    "run_null_harness",
    "falsify_workflow",
    "reference_pipeline",
    "leaky_pipeline",
    "candidate_matrix",
]
