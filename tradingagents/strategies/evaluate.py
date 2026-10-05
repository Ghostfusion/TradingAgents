"""Phase 0 - cost-aware evaluation harness.

Pure helpers for measuring agent/screener outcomes honestly: net-of-cost
metrics, walk-forward splits and overfitting guards. Used by the memory-log
realized-return path and by per-phase validation.

Evaluation breadth (Lean L3): Sortino, downside deviation, beta/alpha/
Treynor/information-ratio, Probabilistic Sharpe, rolling beta and underwater
drawdown collection — so a strategy is judged on more than a single Sharpe +
max-drawdown (the classic overfit hole).

All functions are vectorized over simple sequences (lists) so they work
offline on synthetic data and on exported memory-log returns.
"""

from __future__ import annotations

import math
import random


def _clean(values: list) -> list[float]:
    """Finite-float clean of a series (drops None / non-numeric / non-finite)."""
    out: list[float] = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def net_returns(
    returns: list[float],
    cost_bps: float = 10.0,
    illiq: float | None = None,
    illiq_cost_mult: float = 1e5,
) -> list[float | None]:
    """Subtract a per-trade cost (basis points) from each period return.

    Item 3 (liquidity-aware costs): when ``illiq`` (Amihud ILLIQ) is provided,
    scale cost up for illiquid names (mirrors ``exits.net_of_cost``). None
    ``illiq`` keeps the flat-cost behavior (backward compatible).
    """
    cost = cost_bps / 10000.0
    if illiq is not None:
        cost += float(illiq) * float(illiq_cost_mult) / 10000.0
    return [r - cost if r is not None else None for r in returns]


def total_return(returns: list[float]) -> float:
    """Compounded total return; None entries are treated as zero-return gaps."""
    prod = 1.0
    for r in returns:
        if r is not None:
            prod *= 1.0 + r
    return prod - 1.0


def cagr(returns: list[float], periods_per_year: float = 252.0) -> float:
    """Annualized compound growth over the return series.

    A compounding base at or below zero has no real growth rate: ``base **
    (1/years)`` is **complex** for a negative base, and this function promises a
    float. A total loss (``base == 0``) is exactly -100%/yr; a base below zero is
    not a return series at all (a decile long-short SPREAD can lose more than
    100% of notional in one period, which is how a panel's spread series reaches
    this branch), so it returns ``nan`` rather than a complex number.
    """
    n = sum(1 for r in returns if r is not None)
    if n <= 0:
        return 0.0
    years = n / periods_per_year
    if years <= 0:
        return 0.0
    base = 1.0 + total_return(returns)
    if base <= 0.0:
        return -1.0 if base == 0.0 else float("nan")
    return base ** (1.0 / years) - 1.0


def volatility(returns: list[float], periods_per_year: float = 252.0) -> float:
    """Annualized standard deviation of returns."""
    vals = _clean(returns)
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return math.sqrt(var * periods_per_year)


def sharpe(returns: list[float], risk_free: float = 0.0,
           periods_per_year: float = 252.0) -> float:
    """Annualized Sharpe ratio."""
    vol = volatility(returns, periods_per_year)
    if vol <= 0:
        return 0.0
    return (cagr(returns, periods_per_year) - risk_free) / vol


#: Euler-Mascheroni g, the weight on the second-order term of the expected
#: maximum of N standard normals (Bailey & Lopez de Prado).
_EULER_MASCHERONI = 0.5772156649015328606


def _trial_ledger_gate_on() -> bool:
    """Is ``enable_trial_ledger`` on? A missing config/import is off, not a crash."""
    try:
        from tradingagents.strategies.trial_ledger import gate_on

        return bool(gate_on())
    except Exception:  # noqa: BLE001 - an unreadable gate is an off gate
        return False


def _dispersion_threshold(n_trials: int, sharpe_dispersion: float) -> float | None:
    """SR*_0 for N trials whose Sharpe ratios have variance V.

    ``SR*_0 = sqrt(V) * [(1-g)*Phi^-1(1 - 1/N) + g*Phi^-1(1 - 1/(N*e))]`` with g
    Euler-Mascheroni. ``None`` when N < 2 or V is not a non-negative finite
    number: the closed form has no value there.
    """
    if n_trials < 2:
        return None
    try:
        var = float(sharpe_dispersion)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(var) or var < 0.0:
        return None
    from statistics import NormalDist

    nd = NormalDist()
    first = nd.inv_cdf(1.0 - 1.0 / n_trials)
    second = nd.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(var) * ((1.0 - _EULER_MASCHERONI) * first
                             + _EULER_MASCHERONI * second)


def _selection_threshold(n_trials: int,
                         sharpe_dispersion: float | None) -> tuple[float | None, str]:
    """``(threshold, provenance)`` for one deflation; provenance is the tag.

    ``"measured"`` when the ledger's Sharpe dispersion entered the standard
    closed form, ``"assumed"`` when the independence approximation was used
    instead (no dispersion, the gate off, or N < 2). One producer of the
    threshold, so the number and its tag cannot disagree.
    """
    if n_trials <= 1:
        return None, "assumed"
    if sharpe_dispersion is not None and _trial_ledger_gate_on():
        threshold = _dispersion_threshold(n_trials, sharpe_dispersion)
        if threshold is not None:
            return threshold, "measured"
    # Approximation of E[max Z] for standard normals under independence.
    return math.sqrt(2.0 * math.log(n_trials)), "assumed"


def deflated_sharpe(returns: list[float], n_trials: int = 100,
                    risk_free: float = 0.0,
                    periods_per_year: float = 252.0,
                    sharpe_dispersion: float | None = None) -> float:
    """Lopez de Prado style deflated Sharpe: penalize multi-trial tuning.

    The expected maximum Sharpe across n independent trials is approximated
    (Euler-Mascheroni-based) and subtracted from the observed Sharpe.

    With ``sharpe_dispersion`` supplied - V, the variance of the trials' Sharpe
    ratios, read back from the trial ledger - the selection threshold is the
    standard closed form instead of the independence approximation, so a tightly
    clustered search and a wildly dispersed one are penalised differently::

        SR*_0 = sqrt(V) * [(1-g)*Phi^-1(1 - 1/N) + g*Phi^-1(1 - 1/(N*e))]

    That path is behind ``enable_trial_ledger`` (default off): with the gate off
    the argument is ignored and the result is the pre-existing approximation bit
    for bit. ``deflated_sharpe_report`` returns the same number beside its N and
    whether the dispersion was measured or assumed.

    **Unit caveat (known limitation, 2026-10-04).** ``observed`` here is
    ``sharpe``'s **annualized** CAGR-based Sharpe, while the *assumed* threshold
    ``sqrt(2*ln(N))`` is the expected maximum of ``N`` standard-normal draws -
    a **per-observation** quantity. Those are different scales, so the assumed
    path's difference is dimensionally mixed. The measured path is consistent
    (the ledger's V is annualized too, so both sides match). For the
    scale-correct statistic use :func:`deflated_sharpe_ratio`, which applies the
    paper's Eq. (2) in per-observation units and returns a probability; this
    function is retained unchanged because the G5 gate publishes its number and
    its docstring promised the pre-existing result bit for bit.
    """
    observed = sharpe(returns, risk_free, periods_per_year)
    threshold, _ = _selection_threshold(n_trials, sharpe_dispersion)
    if threshold is None:
        return observed
    return observed - threshold


def deflated_sharpe_report(returns: list[float], n_trials: int = 100,
                           risk_free: float = 0.0,
                           periods_per_year: float = 252.0,
                           sharpe_dispersion: float | None = None) -> dict:
    """The deflated Sharpe WITH the N it was deflated by, and its provenance.

    ``dispersion`` is ``"measured"`` when the ledger's Sharpe dispersion entered
    the closed-form threshold and ``"assumed"`` when the independence
    approximation was used instead - so a published deflated number can never be
    read without knowing which search, and which dispersion, it was deflated
    against. ``value`` is exactly ``deflated_sharpe``'s return.
    """
    observed = sharpe(returns, risk_free, periods_per_year)
    threshold, provenance = _selection_threshold(n_trials, sharpe_dispersion)
    return {
        "value": observed if threshold is None else observed - threshold,
        "ratio": deflated_sharpe_ratio(
            returns, n_trials=n_trials, risk_free=risk_free,
            periods_per_year=periods_per_year, sharpe_dispersion=sharpe_dispersion,
        ),
        "min_track_record": min_track_record_length(
            returns, periods_per_year=periods_per_year,
        ),
        "n_trials": max(1, int(n_trials)),
        "sharpe_dispersion": float(sharpe_dispersion)
        if provenance == "measured" else None,
        "dispersion": provenance,
        "threshold": threshold,
        "observed_sharpe": observed,
        "basis": (
            "the observed Sharpe minus the multiple-testing selection threshold "
            + ("(sqrt(V) * [(1-g)*Phi^-1(1 - 1/N) + g*Phi^-1(1 - 1/(N*e))], V and N "
               "read back from the trial ledger)" if provenance == "measured"
               else "(sqrt(2*ln(N)) independence approximation; the trials' Sharpe "
                    "dispersion was not measured)")
            + f"; n_trials={max(1, int(n_trials))}"
        ),
    }


def max_drawdown(equity_curve: list[float]) -> float:
    """Maximum peak-to-trough drawdown of a cumulative equity curve."""
    peak = float("-inf")
    worst = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak if peak > 0 else 0.0
        worst = max(worst, dd)
    return worst


def equity_curve(returns: list[float], start: float = 100.0) -> list[float]:
    """Cumulative equity curve from period returns."""
    curve: list[float] = []
    level = start
    for r in returns:
        level *= 1.0 + (r if r is not None else 0.0)
        curve.append(level)
    return curve


def deflated_sharpe_ratio(returns: list[float], n_trials: int = 100,
                          risk_free: float = 0.0,
                          periods_per_year: float = 252.0,
                          sharpe_dispersion: float | None = None) -> float | None:
    """Bailey & Lopez de Prado's Deflated Sharpe Ratio (2014), Eq. (2).

    ``DSR = Z[(SR_hat - SR*_0) * sqrt(T-1) / sqrt(1 - g3*SR_hat + ((g4-1)/4)*SR_hat^2)]``
    - the Probabilistic Sharpe Ratio with its rejection threshold raised to the
    expected MAXIMUM of ``n_trials`` independent trials. The answer is the
    confidence that the selected strategy's true SR beats the best a search of
    that size finds on noise alone: a probability in ``[0, 1]``. ``None`` when
    the estimator is degenerate (``n_trials < 2``, under four observations, a
    zero/negative dispersion or a non-positive variance estimate).

    **Everything is per-observation, which is the paper's own scale.** Its worked
    example converts an annualized 2.5 to a non-annualized ``sqrt(2/250)`` before
    applying Eq. (2); ``SR*_0`` is built from the trials' *per-observation*
    Sharpes. This function composes the two pieces the module already owns -
    the selection threshold and ``probabilistic_sharpe``'s moment-corrected
    standard error - instead of re-deriving either.

    ``sharpe_dispersion`` is V **as the ledger records it**: the variance of the
    trials' *annualized* Sharpe ratios, because ``trial_ledger.trial_stats``
    records ``evaluate.sharpe``'s output. It is therefore divided by
    ``periods_per_year`` before entering the threshold. That conversion is exact
    when the annualized Sharpe is the per-observation one scaled by
    ``sqrt(periods_per_year)`` - true for the mean/std estimator composed below,
    an **approximation** for ``sharpe``'s CAGR-based one. Pass a
    per-observation V with ``periods_per_year=1.0`` when you already hold one.
    """
    if n_trials < 2:
        return None
    if sharpe_dispersion is None:
        # Unit-variance per-observation trials: E[max Z] under independence.
        threshold = math.sqrt(2.0 * math.log(n_trials))
    else:
        try:
            var = float(sharpe_dispersion)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(var) or var <= 0.0:
            return None
        threshold = _dispersion_threshold(n_trials, var / periods_per_year)
        if threshold is None:
            return None
    excess = returns
    if risk_free:
        per_period = risk_free / periods_per_year
        excess = [r - per_period if r is not None else None for r in returns]
    return probabilistic_sharpe(excess, benchmark_sharpe=threshold)


def _mintrl_observations(observed: float, benchmark: float, skew: float,
                         kurtosis: float, z: float) -> float | None:
    """Bailey & Lopez de Prado's closed form, in per-observation units.

    ``MinTRL = 1 + [1 - g3*SR + ((g4 - 1)/4)*SR^2] * (z / (SR - SR*))^2``, the
    paper's Eq. (13). ``g4`` is the STANDARDIZED kurtosis (3 for a normal, not
    the excess) - the same moment convention ``probabilistic_sharpe`` uses, for
    the same reason. ``None`` when ``SR <= SR*``: no finite record can reject
    the hypothesis, so any length would be a fabrication.
    """
    spread = observed - benchmark
    if spread <= 0:
        return None
    bracket = 1.0 - skew * observed + ((kurtosis - 1.0) / 4.0) * observed * observed
    if not math.isfinite(bracket) or bracket <= 0:
        return None
    return 1.0 + bracket * (z / spread) ** 2


def min_track_record_length(returns: list[float], benchmark_sharpe: float = 0.0,
                            alpha: float = 0.05,
                            periods_per_year: float = 252.0) -> dict | None:
    """E2: the minimum track record length (MinTRL) for the measured Sharpe.

    Bailey & Lopez de Prado, "The Sharpe Ratio Efficient Frontier" (2012) - the
    record length at which the measured Sharpe would exceed ``benchmark_sharpe``
    at confidence ``1 - alpha``, given the record's own skewness and kurtosis.
    The inverse question to :func:`probabilistic_sharpe`: that one asks "does
    this record clear the bar", this one asks "how long would it have to be".

    **Units (the paper's own words):** *"MinTRL is expressed in terms of number
    of observations, not annual or calendar terms"* - so ``observed_sharpe`` and
    ``benchmark_sharpe`` are BOTH the per-observation ``mean/std`` Sharpe, the
    same estimator and scale ``probabilistic_sharpe`` uses. The paper's three
    published worked examples reproduce exactly under that convention, with the
    normal moments ``g3 = 0, g4 = 3``: daily needs 688.2 observations (2.73
    years) for an annualized Sharpe of 2 to clear 1 at 95%, weekly 147.1 (2.83)
    and monthly 38.9 (3.24).

    Returns ``{"min_track_record", "min_track_record_years", "observed_sharpe",
    "benchmark_sharpe", "alpha", "confidence", "skewness", "kurtosis", "n",
    "basis"}``, or ``None`` for < 4 observations, a degenerate (zero-variance)
    series, an ``alpha`` outside ``(0, 1)``, a non-finite moment, or
    ``observed_sharpe <= benchmark_sharpe`` - the paper's own case where no
    length suffices.

    A *length*, never a verdict: it says how much record the claim would need,
    not whether the strategy is any good. It assumes the record is IID enough
    for the estimator's asymptotic distribution (the paper trusts the CLT above
    30 observations).
    """
    if not 0.0 < float(alpha) < 1.0:
        return None
    vals = _clean(returns)
    if len(vals) < 4:
        return None
    mean = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))
    if sd <= 0:
        return None
    observed = mean / sd
    g3 = skewness(vals)
    g4 = kurtosis(vals)
    if g3 is None or g4 is None:
        return None
    from statistics import NormalDist

    z = NormalDist().inv_cdf(1.0 - float(alpha))
    obs = _mintrl_observations(observed, float(benchmark_sharpe), g3, g4, z)
    if obs is None:
        return None
    years = obs / float(periods_per_year) if periods_per_year else None
    return {
        "min_track_record": obs,
        "min_track_record_years": years,
        "observed_sharpe": observed,
        "benchmark_sharpe": float(benchmark_sharpe),
        "alpha": float(alpha),
        "confidence": 1.0 - float(alpha),
        "skewness": g3,
        "kurtosis": g4,
        "n": len(vals),
        "basis": (
            f"MinTRL {obs:.1f} observation(s) at {1.0 - float(alpha):.0%} confidence for a "
            f"per-observation Sharpe of {observed:.6f} to clear {float(benchmark_sharpe):.6f} "
            f"(return skewness {g3:.3f}, standardized kurtosis {g4:.3f}, n={len(vals)}): "
            "Bailey & Lopez de Prado (2012) Eq. (13), in observations not calendar terms - "
            "a length, not a verdict"
        ),
    }


def walk_forward_splits(returns: list[float], train_len: int, test_len: int):
    """Yield (train, test) return slices for walk-forward evaluation."""
    i = 0
    while i + train_len + test_len <= len(returns):
        yield returns[i:i + train_len], returns[i + train_len:i + train_len + test_len]
        i += test_len


def _default_hac_lags(n: int) -> int:
    """Newey-West's data-dependent lag rule ``floor(4*(T/100)^(2/9))``, floor 1."""
    return max(1, int(4.0 * (n / 100.0) ** (2.0 / 9.0)))


def z_statistic(series: list[float], *, max_lag: int | None = None) -> float | None:
    """H3 (2604.15531): ``Z = Rbar / sqrt(VHAC(Rbar))`` - the HAC-standardised mean.

    The paper's ``Z_IS,k`` / ``Z_WF,k``: a candidate's mean return divided by its
    **HAC standard error**, so a serially correlated statistic is not read as if
    its observations were independent. The long-run variance is the Bartlett
    (Newey-West) kernel sum ``s = g0 + 2*sum_l w_l*g_l`` with weights
    ``1 - l/(L+1)``, and ``VHAC(Rbar) = s / n``; ``max_lag`` defaults to the
    data-dependent rule ``floor(4*(T/100)^(2/9))`` (floor 1).

    ``None`` on fewer than two usable observations or a non-positive /
    non-finite long-run variance: the ratio has no value there. An honest
    (out-of-sample) series returns a small number; an inflation-peeking one
    returns a large one - which is what :func:`inflation_diagnostics` measures.
    """
    vals = _clean(series)
    n = len(vals)
    if n < 2:
        return None
    mean = sum(vals) / n
    dev = [v - mean for v in vals]
    lag = n - 1 if max_lag is None else max(0, min(int(max_lag), n - 1))
    if max_lag is None:
        lag = min(lag, _default_hac_lags(n))
    var = sum(d * d for d in dev) / n
    for step in range(1, lag + 1):
        weight = 1.0 - step / (lag + 1.0)
        cov = sum(dev[t] * dev[t - step] for t in range(step, n)) / n
        var += 2.0 * weight * cov
    if var <= 0.0 or not math.isfinite(var):
        return None
    return mean / math.sqrt(var / n)


def max_abs_z(candidate_matrix: list[list[float]], *,
              max_lag: int | None = None) -> float | None:
    """``Z* = max_k |Z_k|`` over a candidate statistic matrix (H3).

    The matrix is one row per candidate (the per-period series it produced), so
    the winner is the strongest |HAC z| the search could surface. ``None`` when
    no candidate has a computable ``z_statistic``.
    """
    zs = [abs(z) for row in (candidate_matrix or [])
          if (z := z_statistic(row, max_lag=max_lag)) is not None]
    return max(zs) if zs else None


def effective_candidates(candidate_matrix: list[list[float]]) -> float | None:
    """``K_eff = (sum lambda_i)^2 / sum lambda_i^2`` from the candidate corr matrix.

    H3's effective number of **independent** candidates: the eigenvalues of the
    candidate correlation matrix (rows = candidates, columns = periods). A set of
    ``K`` independent candidates gives ``K_eff = K`` (every ``lambda_i = 1``); a
    set that is really one candidate repeated gives ``1`` (one eigenvalue ``K``,
    the rest zero). It is the number a naive trial count overstates - fifty
    near-identical candidates are not fifty trials.

    ``None`` on fewer than two candidates/periods, a degenerate row (zero
    variance), or a non-finite spectrum.
    """
    rows = [[float(v) for v in row] for row in (candidate_matrix or [])]
    k = len(rows)
    if k < 2:
        return None
    width = min(len(row) for row in rows)
    if width < 2:
        return None
    try:
        import numpy as np

        m = np.asarray([row[:width] for row in rows], dtype=float)
        if not np.all(np.isfinite(m)):
            return None
        std = m.std(axis=1)
        if np.any(std <= 0.0):
            return None
        corr = np.corrcoef(m)
        if not np.all(np.isfinite(corr)):
            return None
        eig = np.linalg.eigvalsh(corr)
    except Exception:  # noqa: BLE001 - a degenerate spectrum is a refusal, not a crash
        return None
    total = float(eig.sum())
    sq = float((eig * eig).sum())
    if sq <= 0.0 or not math.isfinite(sq):
        return None
    return (total * total) / sq


def inflation_diagnostics(is_matrix: list[list[float]],
                          wf_matrix: list[list[float]] | None = None, *,
                          max_lag: int | None = None) -> dict:
    """H3 Stage 2: ``Z*_IS``, ``Z*_WF``, ``Delta_Z`` and ``K_eff`` from the matrix.

    ``is_matrix`` is the retained candidate matrix as evaluated **in-sample**,
    ``wf_matrix`` the **walk-forward winner's** series (the one candidate the
    honest procedure selected, carried out-of-sample - a single row).
    ``Delta_Z = Z*_IS - Z*_WF`` is the inflation the in-sample search bought -
    the paper reports a mean ``|Z*_IS|`` of 2.79 at K=100 against 0.80 for the
    walk-forward winner, so a large positive ``Delta_Z`` is the overfit signal.
    ``K_eff`` is :func:`effective_candidates` over the candidate series.

    Every field is independently ``None`` when its input is missing or degenerate
    - a refused leg is never reported as zero.
    """
    z_is = max_abs_z(is_matrix, max_lag=max_lag)
    z_wf = max_abs_z(wf_matrix, max_lag=max_lag) if wf_matrix is not None else None
    delta_z = (z_is - z_wf) if (z_is is not None and z_wf is not None) else None
    k_eff = effective_candidates(is_matrix)
    return {
        "z_is_star": z_is,
        "z_wf_star": z_wf,
        "delta_z": delta_z,
        "k_eff": k_eff,
        "n_candidates": len(is_matrix or []),
        "basis": (
            "H3 (2604.15531) Stage 2: Z* = max_k |Z_k| with Z_k the HAC-standardised "
            f"mean; Z*_IS {z_is}, Z*_WF {z_wf}, Delta_Z {delta_z}; K_eff {k_eff} from "
            "the candidate correlation matrix - the inflation an in-sample search "
            "bought, and the number of independent candidates it really was"
        ),
    }


def _exposure_matched(benchmark_returns, exposure) -> list[float] | None:
    """Benchmark replayed on the strategy's own in-market bars (H6).

    ``exposure`` is the strategy's binary position series, one flag per
    benchmark bar: the benchmark's return is taken on a bar the strategy was
    **in**, and zero (cash) on a bar it was flat. Cost-free by construction -
    this arm isolates *when in market* from *what was held in market*, which a
    common-window comparison cannot: a strategy that is out of the market on the
    benchmark's best days is not measuring the same thing as one that held
    through them.

    ``None`` (the row is dropped, not guessed) when the exposure series does not
    align one-for-one with the benchmark, or holds a non-numeric flag.
    """
    if not isinstance(exposure, (list, tuple)):
        return None
    if len(exposure) != len(benchmark_returns):
        return None
    out: list[float] = []
    for ret, flag in zip(benchmark_returns, exposure, strict=False):
        if flag is None:
            return None
        try:
            on = float(flag) != 0.0
        except (TypeError, ValueError):
            return None
        out.append(ret if on else 0.0)
    return out


def benchmark_table(strategy_returns: list[float], benchmark_returns: list[float],
                     simple: dict | None = None,
                     periods_per_year: float = 252.0,
                     exposure: list | None = None) -> dict:
    """Benchmark hierarchy (W1-6): the strategy vs a market benchmark and
    (optional) simple strategies, aligned on the common window.

    Returns rows: name, total_return, cagr, sharpe, max_drawdown — computed
    from the supplied series only (honest: no fetched data, all None when the
    series is too short). ``simple`` may be {name: returns} for buy&hold /
    equal-weight / momentum / MA / vol-target comparators.

    With ``exposure`` (the strategy's binary position series, one flag per
    benchmark bar) a **time-in-market-matched** row is appended: the benchmark
    replayed on exactly the bars the strategy held and flat (cash) elsewhere,
    cost-free. Without it the table compares on a common window that does not
    match time in market, and no ``exposure_matched`` row is emitted — the
    default path is unchanged.
    """
    def _stats(name, rets):
        if not rets or len(rets) < 2:
            return {"name": name, "total_return": None, "cagr": None,
                    "sharpe": None, "max_drawdown": None}
        eq = equity_curve(rets)
        row = {
            "name": name,
            "total_return": round(total_return(rets), 4),
            "cagr": round(cagr(rets, periods_per_year), 4),
            "sharpe": round(sharpe(rets, periods_per_year), 3),
            "max_drawdown": round(max_drawdown(eq), 4),
        }
        if _drawdown_envelope_gate_on():
            # K2 (2608.00127): the EXPECTED drawdown envelope beside the realized
            # ``max_drawdown`` already on the row, so the engine can say how deep
            # and how long a drawdown at this Sharpe should run. REPORT-ONLY -
            # the T^(H-1/2) rescaling is deliberately NOT wired into any governor.
            from tradingagents.strategies.book_risk import drawdown_envelope
            from tradingagents.strategies.mean_reversion import hurst_exponent

            row["drawdown_envelope"] = drawdown_envelope(
                row["sharpe"], len(rets), skewness(rets), kurtosis(rets),
                hurst_exponent(rets),
            )
        return row

    n = min(len(strategy_returns), len(benchmark_returns))
    rows = [_stats("strategy", list(strategy_returns[-n:])),
            _stats("benchmark", list(benchmark_returns[-n:]))]
    if exposure is not None:
        matched = _exposure_matched(benchmark_returns, exposure)
        if matched is not None:
            rows.append(_stats("exposure_matched", matched[-n:]))
    for name, rets in (simple or {}).items():
        rows.append(_stats(name, list(rets[-n:]) if len(rets) >= n else rets))
    return {"window": n, "rows": rows}


def purged_cpcv_splits(n: int, n_splits: int = 5, embargo: int = 0):
    """Naive-Combinatorial purged cross-validation (CPCV) fold indices (W2-2).

    Yields (train_idx, test_idx) for every (test-group, train-complement)
    combination: for each test group g, the train set is each NON-EMPTY
    subset of the remaining groups (both orders -- groups before and after g),
    with the ``embargo``-bar purge gap around the test block applied to the
    train members. This gives C(N-1, k) paths per test group (not one lucky
    k-fold cut), matching Lopez de Prado's combinatorial CPCV: a factor must
    survive on MANY train/test cuts. Degenerates to plain k-fold when
    ``n_splits <= 2`` (only the full-complement cut exists).
    """
    if n <= 0 or n_splits <= 1:
        return
    size = max(1, n // n_splits)
    groups = [list(range(g * size, min(n, (g + 1) * size))) for g in range(n_splits)]
    groups = [g for g in groups if g]
    for g, test in enumerate(groups):
        others = [grp for i, grp in enumerate(groups) if i != g]
        lo = min(test) - embargo if embargo else min(test)
        hi = max(test) + 1 + embargo if embargo else max(test) + 1
        # iterate over all non-empty subsets of the other groups (both orders)
        m = len(others)
        for mask in range(1, 1 << m):
            chosen = []
            for i, grp in enumerate(others):
                if mask & (1 << i):
                    chosen.extend(grp)
            train = [idx for idx in chosen if not (lo <= idx < hi)]
            if train:
                yield list(train), list(test)


def cpcv_overfit_mask(ipcs: list[float], oopcs: list[float],
                      threshold: float = 0.0) -> bool:
    """CPCV overfitting signal (W2-2): a factor that wins in-sample (best IPC)
    but fails out-of-sample will have its best-IPC fold show a poor OOPC. """
    if not ipcs or not oopcs or len(ipcs) != len(oopcs):
        return False
    best = max(range(len(ipcs)), key=lambda i: ipcs[i])
    return oopcs[best] < threshold


def oos_split(signal: list, forward: list, train_frac: float = 0.7):
    """(W2-4) leading-train / trailing-out-of-sample split; yields the OOS
    (signal, forward) slices after a leading ``train_frac`` training band, so
    an IC measured OOS never uses the same rows the parameters saw."""
    n = len(signal)
    cut = int(n * train_frac)
    if cut <= 0 or cut >= n:
        return [], []
    return signal[cut:], forward[cut:]


def pbo_flag(results_by_trial: list[float], test_results: list[float],
             threshold: float = 0.0) -> bool:
    """Crude overfit flag: best-trial in-sample picks fail out-of-sample.

    The single-index degraded path; :func:`cscv_pbo` is the literature's
    probability over the full candidate x fold matrix, and is preferred whenever
    that matrix is available.
    """
    if not results_by_trial or not test_results:
        return False
    best_idx = max(range(len(results_by_trial)), key=lambda i: results_by_trial[i])
    return test_results[best_idx] < threshold


def cscv_pbo(performance_by_candidate: list[list[float]], S: int = 8) -> dict | None:
    """E1: the Combinatorially Symmetric Cross-Validation PBO - a PROBABILITY.

    ``pbo_flag`` above is the crude boolean: it picks the single best in-sample
    trial and asks whether THAT trial failed out-of-sample. The literature's
    Probability of Backtest Overfitting is a probability over the whole
    candidate x fold matrix (Bailey, Borwein, Lopez de Prado & Zhu): partition
    the ``T`` periods into ``S`` contiguous blocks, and for each of the
    ``C(S, S/2)`` symmetric ways to split them into in-sample/out-of-sample
    halves, find the in-sample-best candidate and take its OUT-OF-SAMPLE rank
    among the candidates. PBO is the fraction of splits in which that winner
    lands at or below the out-of-sample median - the chance a search's winner is
    a fluke rather than an edge.

    ``S = 8`` is the H1 card's own directive (16 is 12,870 recombinations). The
    ``pbo_flag`` is kept as the documented degraded path when no candidate
    matrix is available. ``None`` on fewer than two candidates, fewer than two
    periods, an odd ``S``, ``S`` exceeding the periods, or a candidate too short
    to give every block a period.
    """
    rows = [[float(v) for v in row] for row in (performance_by_candidate or [])]
    k = len(rows)
    if k < 2:
        return None
    t = min(len(r) for r in rows)
    blocks = int(S)
    if t < 2 or blocks < 2 or blocks % 2 or blocks > t:
        return None
    rows = [r[:t] for r in rows]
    # Contiguous blocks, as equal as the period count allows.
    edges = [round(i * t / blocks) for i in range(blocks + 1)]
    block_idx = [list(range(edges[i], edges[i + 1])) for i in range(blocks)]
    if any(not b for b in block_idx):
        return None
    from itertools import combinations

    half = blocks // 2
    n_splits = 0
    overfit = 0
    for chosen in combinations(range(blocks), half):
        is_cols = [c for i in chosen for c in block_idx[i]]
        oos_cols = [c for i in range(blocks) if i not in chosen for c in block_idx[i]]
        if not is_cols or not oos_cols:
            continue
        is_perf = [sum(r[c] for c in is_cols) / len(is_cols) for r in rows]
        oos_perf = [sum(r[c] for c in oos_cols) / len(oos_cols) for r in rows]
        winner = max(range(k), key=lambda i: is_perf[i])
        # Relative OOS rank of the in-sample winner (1 = worst); <= 0.5 of the
        # rank scale is the logit-rank <= 0 event the PBO counts.
        rank = sum(1 for x in oos_perf if x <= oos_perf[winner])
        n_splits += 1
        if rank / (k + 1) <= 0.5:
            overfit += 1
    if n_splits == 0:
        return None
    pbo = overfit / n_splits
    return {
        "pbo": round(pbo, 4),
        "n_splits": n_splits,
        "S": blocks,
        "n_candidates": k,
        "n_obs": t,
        "basis": (
            f"CSCV PBO (Bailey-Lopez de Prado) over {n_splits} symmetric "
            f"{half}-of-{blocks} block split(s), {k} candidate(s) x {t} period(s), "
            f"S={blocks}: the in-sample winner's out-of-sample rank fell at or "
            f"below the median in {overfit} split(s) -> PBO {pbo:.4f}; "
            "pbo_flag is the single-index degraded path"
        ),
    }


def _mean_var(values: list[float]) -> tuple[float, float]:
    n = len(values)
    m = sum(values) / n
    if n < 2:
        return m, 0.0
    return m, sum((v - m) ** 2 for v in values) / (n - 1)


def _rc_metric(values: list[float], metric: str) -> float:
    """Per-period performance of a relative series: mean or mean/std."""
    m, var = _mean_var(values)
    if metric == "sharpe":
        sd = math.sqrt(var)
        return m / sd if sd > 0 else 0.0
    return m


def _rc_prepare(candidates, benchmark, block_len) -> tuple | None:
    """Align candidates vs benchmark; None on any degrading condition.

    Degrades when there are fewer than 2 candidates, any series is ragged or
    holds a non-finite value, the window (``len(benchmark)``) is shorter than
    ``2 * block_len``, or every candidate has zero variance (a flat universe
    cannot be distinguished from anything).
    """
    if not isinstance(candidates, dict) or len(candidates) < 2:
        return None
    if not isinstance(benchmark, (list, tuple)) or int(block_len) < 1:
        return None
    n = len(benchmark)
    if n < int(block_len) * 2:
        return None
    bench = _clean(benchmark)
    if len(bench) != n:
        return None
    names: list[str] = []
    rel: list[list[float]] = []
    any_variance = False
    for name, series in candidates.items():
        if not isinstance(series, (list, tuple)) or len(series) != n:
            return None
        vals = _clean(series)
        if len(vals) != n:
            return None
        if _mean_var(vals)[1] > 0.0:
            any_variance = True
        names.append(str(name))
        rel.append([vals[i] - bench[i] for i in range(n)])
    if not any_variance:
        return None
    return names, rel, n


def _stationary_indices(n: int, block_len: int, rng: random.Random) -> list[int]:
    """Index draw for the stationary (polychromatic) bootstrap: geometric
    blocks of mean length ``block_len`` with wraparound, preserving serial
    dependence that an i.i.d. draw would destroy."""
    p = 1.0 / max(1, int(block_len))
    idx = [rng.randrange(n)]
    while len(idx) < n:
        if rng.random() < p:
            idx.append(rng.randrange(n))
        else:
            idx.append((idx[-1] + 1) % n)
    return idx


def reality_check(candidates, benchmark, n_boot: int = 1000, block_len: int = 5,
                  seed: int = 0, metric: str = "mean") -> dict | None:
    """White's Reality Check over a universe of candidates vs one benchmark.

    The null is that the best candidate's relative performance does not exceed
    the benchmark's: the statistic is ``max_k`` of the (bootstrap-centred)
    relative mean (or Sharpe when ``metric="sharpe"``), and the p-value is the
    share of stationary-bootstrap maxima at least as large. ``candidates`` is a
    ``{name: [returns]}`` mapping aligned with ``benchmark``. None on <2
    candidates, ragged/non-finite series, a window under ``2*block_len``, or
    zero variance in every candidate. Deterministic given ``seed``.
    """
    prepared = _rc_prepare(candidates, benchmark, block_len)
    if prepared is None or metric not in ("mean", "sharpe"):
        return None
    names, rel, n = prepared
    observed = [_rc_metric(row, metric) for row in rel]
    stat = max(observed)
    n_boot = int(n_boot)
    rng = random.Random(seed)
    exceed = 0
    for _ in range(n_boot):
        idx = _stationary_indices(n, block_len, rng)
        boot_max = max(_rc_metric([row[j] for j in idx], metric) - observed[k]
                       for k, row in enumerate(rel))
        if boot_max >= stat:
            exceed += 1
    basis = (f"white reality check (stationary bootstrap, mean block {block_len}, "
             f"n_boot={n_boot}, seed={seed}, metric={metric}) on "
             f"{len(names)} candidates x {n} obs")
    return {
        "stat": round(stat, 6),
        "p_value": round((1.0 + exceed) / (n_boot + 1.0), 6),
        "block_len": int(block_len),
        "n_candidates": len(names),
        "n_obs": n,
        "basis": basis,
    }


def spa(candidates, benchmark, n_boot: int = 1000, block_len: int = 5,
        seed: int = 0) -> dict | None:
    """Hansen's studentised SPA test over a universe vs one benchmark.

    Same null and stationary bootstrap as ``reality_check`` but the statistic
    is studentised (``sqrt(n) * mean / std``) and candidates whose relative
    mean is significantly below the benchmark (below ``-sqrt(2 log log n / n)``
    standard errors) are recentred to zero in the null, so only plausible
    contenders set the critical value. The ``recentring`` key counts the
    candidates recentred. Same degradation rules as ``reality_check``.
    """
    prepared = _rc_prepare(candidates, benchmark, block_len)
    if prepared is None:
        return None
    names, rel, n = prepared
    stats: list[tuple[float, float]] = []
    for row in rel:
        m, var = _mean_var(row)
        sd = math.sqrt(var)
        if sd > 0:
            stats.append((m, sd))
    if not stats:
        return None
    root_n = math.sqrt(n)
    t_obs = max(root_n * m / sd for m, sd in stats)
    a_n = 2.0 * math.log(math.log(n)) if n > math.e else 0.0
    cutoff = -math.sqrt(a_n / n)
    mus: list[float] = []
    recentred = 0
    for m, sd in stats:
        if m / sd < cutoff:
            mus.append(0.0)
            recentred += 1
        else:
            mus.append(m)
    n_boot = int(n_boot)
    rng = random.Random(seed)
    student_rows = [(rel[k], stats[k][1], mus[k]) for k in range(len(stats))]
    exceed = 0
    for _ in range(n_boot):
        idx = _stationary_indices(n, block_len, rng)
        boot_max = float("-inf")
        for row, sd, mu in student_rows:
            t = root_n * (_rc_metric([row[j] for j in idx], "mean") - mu) / sd
            if t > boot_max:
                boot_max = t
        if boot_max >= t_obs:
            exceed += 1
    basis = (f"hansen spa (stationary bootstrap, studentised, mean block "
             f"{block_len}, n_boot={n_boot}, seed={seed}) on {len(names)} "
             f"candidates x {n} obs, {recentred} recentred")
    return {
        "stat": round(t_obs, 6),
        "p_value": round((1.0 + exceed) / (n_boot + 1.0), 6),
        "block_len": int(block_len),
        "n_candidates": len(names),
        "n_obs": n,
        "recentring": recentred,
        "basis": basis,
    }


# ---------------------------------------------------------------------------
# H6 - the three-way materiality verdict, the family-level FDR, and the
# exposure-matched benchmark arm
# ---------------------------------------------------------------------------
#
# A non-significant result is not evidence of no effect. A published claim is
# therefore classified into three buckets, not two: SUPPORTED when its interval
# clears the threshold, REFUTED only when the interval lies entirely below it,
# and INCONCLUSIVE when the interval straddles it. The last bucket means
# *unresolved* - an underpowered test is not a null result - and collapsing
# INCONCLUSIVE into REFUTED is the one failure this vocabulary exists to
# prevent.
#
# The thresholds are pre-declared config VALUES, chosen before any result is
# seen (never after it):
#
#     materiality_delta_s = 0.20   annualised Sharpe excess, the S axis
#     materiality_delta_r = 0.01   per-period return excess, the R axis
#
# They are values, not gates: nothing switches on, no ``_ENV_OVERRIDES`` row
# exists, and no env var reaches them.

#: The verdict vocabulary, in the order of the paper's rule. ``INCONCLUSIVE``
#: is a verdict, not a placeholder: a straddling interval is unresolved.
MATERIALITY_VERDICTS = ("SUPPORTED", "REFUTED", "INCONCLUSIVE")

#: Declared defaults, mirroring ``DEFAULT_CONFIG`` so an unreadable config
#: never changes the threshold a claim was judged against.
MATERIALITY_DELTA_S_DEFAULT = 0.20
MATERIALITY_DELTA_R_DEFAULT = 0.01


def _materiality_delta(key: str, default: float) -> float:
    """A pre-declared materiality threshold, read from config by its key.

    Values, not gates: nothing is switched on, so there is no registry entry and
    no env row. An unreadable config (or a non-finite stored value) falls back to
    the declared default, never to a different number.
    """
    try:
        from tradingagents.dataflows.config import get_config

        raw = (get_config() or {}).get(key, default)
    except Exception:  # noqa: BLE001 - a config read must never break the read
        return float(default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float(default)
    return value if math.isfinite(value) else float(default)


def _materiality_gate_on() -> bool:
    """Is the H6 materiality instrument switched on? (``enable_materiality_verdict``)

    Off by default, so with it off the family is not FDR-corrected and the
    verdict vocabulary is not published: a caller sees exactly the pre-H6
    behaviour. ``materiality_verdict`` itself is a pure classifier, not a
    switch - the gate decides whether the instrument that uses it runs. A config
    read must never break the read it guards, and the key is read literally so
    the gate registry's read-site scan can see it.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_materiality_verdict", False))


def _drawdown_envelope_gate_on() -> bool:
    """Is K2's drawdown expectation switched on? (``enable_drawdown_envelope``)

    Off by default: with it off a strategy row carries exactly the keys it had
    before K2 landed, so no existing consumer moves. The key is read literally
    so the gate registry's read-site scan can see it, and a config read must
    never break the read it guards.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_drawdown_envelope", False))


def materiality_verdict(stat: float, ci_low: float, ci_high: float,
                        delta: float) -> str:
    """The three-way materiality verdict for one threshold on one interval.

    The paper's rule, on a single axis::

        REFUTED      iff U < delta
        SUPPORTED    iff L > delta
        INCONCLUSIVE iff the interval straddles the threshold

    (the full rule composes two axes - ``delta_S`` on the Sharpe excess and
    ``delta_R`` on the return excess - plus a separate survival test; this is the
    single-axis piece each axis is classified by, and :func:`family_materiality`
    composes both across a family.)

    **INCONCLUSIVE is never REFUTED.** A straddling interval is *unresolved*,
    not evidence of no edge: an underpowered test is not a null result, and the
    failure this function exists to prevent is a reader taking "we could not
    show it" for "we showed it is not there". A point estimate below the
    threshold whose interval still contains it is exactly that case, and it
    returns INCONCLUSIVE.

    ``stat`` is the point estimate the interval was built around; it is validated
    (finite) so a garbage statistic cannot produce a verdict, and it never
    overrides the interval. Missing or non-finite inputs return ``unavailable`` -
    a missing interval is not a verdict, and it is never reported as REFUTED.
    """
    try:
        point = float(stat)
        lo = float(ci_low)
        hi = float(ci_high)
        bar = float(delta)
    except (TypeError, ValueError):
        return "unavailable"
    if not all(math.isfinite(v) for v in (point, lo, hi, bar)):
        return "unavailable"
    if lo > hi:
        lo, hi = hi, lo
    if lo > bar:
        return "SUPPORTED"
    if hi < bar:
        return "REFUTED"
    return "INCONCLUSIVE"


def benjamini_yekutieli(p_values: list[float], alpha: float = 0.05,
                        *, independent: bool = False) -> dict | None:
    """The one producer of the family false-discovery step-up.

    Benjamini-Yekutieli (2001) by default: find the largest rank ``r`` with
    ``p_(r) <= (r / K) * alpha / H_K`` (``H_K`` the K-th harmonic number) and
    reject that p-value together with every smaller one. ``H_K`` is 1 only at
    ``K == 1``, so this is the conservative correction that stays valid for
    arbitrarily dependent p-values - which is what a family of candidate signals
    is, since they are computed from the same returns. ``independent=True``
    switches to Benjamini-Hochberg (``H_K = 1``), valid only under independence
    or PRDS; the caller has to be able to say which it is, so the method travels
    with the result.

    Returns ``{"surviving", "reject", "cut_rank", "k", "alpha", "harmonic",
    "method", "basis"}``, or ``None`` when handed no p-values. ``surviving`` is
    positional - one bool per input - so a caller cannot mis-align it against a
    re-sorted list.

    ``family_materiality`` and ``calibration.excess_accuracy`` both read this:
    with two copies of the arithmetic, two families would be corrected by
    different sums and both numbers would look authoritative.
    """
    raw = list(p_values or [])
    if not raw or any(p is None for p in raw):
        # A None would silently drop out of a positional `surviving` list and
        # mis-align every caller that zips it back to its own rows.
        return None
    ps = [float(p) for p in raw]
    k = len(ps)
    if k == 0:
        return None
    harmonic = 1.0 if independent else sum(1.0 / i for i in range(1, k + 1))
    order = sorted(range(k), key=lambda j: ps[j])
    cut = 0
    for rank, j in enumerate(order, start=1):
        if ps[j] <= (rank / k) * alpha / harmonic:
            cut = rank
    surviving = [False] * k
    for rank, j in enumerate(order, start=1):
        if rank <= cut:
            surviving[j] = True
    return {
        "surviving": surviving,
        "reject": [ps[j] for j in order[:cut]],
        "cut_rank": cut,
        "k": k,
        "alpha": float(alpha),
        "harmonic": harmonic,
        "method": "BH" if independent else "BY",
        "basis": (
            f"{'Benjamini-Hochberg' if independent else 'Benjamini-Yekutieli'} step-up "
            f"over {k} p-value(s) at alpha={alpha}: every p-value at or below the largest "
            f"rank r with p_(r) <= (r/{k})*alpha/{harmonic:g} is rejected, together with "
            "every smaller one"
        ),
    }


def family_materiality(candidates, benchmark, *, delta_s: float | None = None,
                       delta_r: float | None = None, alpha: float = 0.05,
                       n_boot: int = 1000, block_len: int = 5,
                       seed: int = 0, min_n: int | None = None) -> dict | None:
    """H6: a family-level FDR over a batch of candidate signals.

    One producer of the family adjustment. The stationary-bootstrap machinery
    ``reality_check`` / ``spa`` are built from (``_rc_prepare``,
    ``_stationary_indices``, ``_rc_metric``) supplies each candidate's one-sided
    p-value against the benchmark, and Benjamini-Yekutieli's step-up
    (``p_(i) <= (i/K) * alpha / H_K``, ``H_K`` the K-th harmonic number) turns
    the batch into a family-level false-discovery rate. ``reality_check`` and
    ``spa`` are reported beside it, so the family carries the familywise scalars
    and is corrected once rather than once per candidate by each caller.

    Each candidate is then classified on the R axis - its mean relative return
    against ``delta_r``, with its interval from H11's
    ``conformal.block_bootstrap_interval`` - and the declared S bar (its
    relative Sharpe against ``delta_s``) is reported as a named necessary
    condition. A candidate that clears the R threshold but does not survive the
    FDR is demoted to ``INCONCLUSIVE``, **never** to ``REFUTED``: failing a
    family correction is a statement about power, and this module refuses to read
    power as refutation. (The paper's separate ruin/survival Monte Carlo is not
    computed here; the ``survives`` key in the output is the FDR's, and is named
    as such.)

    ``delta_s`` / ``delta_r`` default to the pre-declared config values
    ``materiality_delta_s`` / ``materiality_delta_r``. ``min_n`` overrides H11's
    observation floor for the per-candidate interval (the default keeps H11's
    own floor; a caller whose series *is* the whole sample may lower it).
    ``None`` under ``reality_check``'s degradation rules (fewer than two
    candidates, ragged or non-finite series, a window under ``2*block_len``, or
    zero variance in every candidate), and ``None`` when
    ``enable_materiality_verdict`` is off (default) - the instrument is not run
    at all with the gate off. Deterministic given ``seed``.
    """
    if not _materiality_gate_on():
        return None
    prepared = _rc_prepare(candidates, benchmark, block_len)
    if prepared is None:
        return None
    names, rel, n = prepared
    ds = (_materiality_delta("materiality_delta_s", MATERIALITY_DELTA_S_DEFAULT)
          if delta_s is None else float(delta_s))
    dr = (_materiality_delta("materiality_delta_r", MATERIALITY_DELTA_R_DEFAULT)
          if delta_r is None else float(delta_r))
    k = len(names)
    n_boot = max(1, int(n_boot))
    observed = [_rc_metric(row, "mean") for row in rel]
    rng = random.Random(seed)
    exceed = [0] * k
    for _ in range(n_boot):
        idx = _stationary_indices(n, block_len, rng)
        for j, row in enumerate(rel):
            boot = _rc_metric([row[i] for i in idx], "mean")
            if boot - observed[j] >= observed[j]:
                exceed[j] += 1
    p_values = [(1.0 + e) / (n_boot + 1.0) for e in exceed]
    fdr = benjamini_yekutieli(p_values, alpha)
    if fdr is None:  # unreachable (k >= 2 above), but never a silent default
        return None
    surviving = {j for j, ok in enumerate(fdr["surviving"]) if ok}
    from tradingagents.strategies.conformal import block_bootstrap_interval

    rows = []
    for j, name in enumerate(names):
        interval = (block_bootstrap_interval(rel[j], seed=seed) if min_n is None
                    else block_bootstrap_interval(rel[j], seed=seed, min_n=min_n))
        verdict = ("unavailable" if interval is None
                   else materiality_verdict(observed[j], interval["low"],
                                            interval["high"], dr))
        sharpe_excess = sharpe(rel[j])
        survives = j in surviving
        if verdict == "SUPPORTED" and (not survives or sharpe_excess <= ds):
            # Refusing to promote on a family-corrected or sub-bar read is the
            # demotion to unresolved; a REFUTED here would be the collapse this
            # vocabulary exists to prevent.
            verdict = "INCONCLUSIVE"
        rows.append({
            "name": name,
            "relative_mean": round(observed[j], 6),
            "p_value": round(p_values[j], 6),
            "survives": survives,
            "sharpe_excess": round(sharpe_excess, 4),
            "sharpe_above_declared_bar": bool(sharpe_excess > ds),
            "interval": interval,
            "verdict": verdict,
        })
    basis = (
        f"family materiality: Benjamini-Yekutieli FDR over {k} candidates x {n} "
        f"obs (stationary bootstrap, mean block {block_len}, n_boot={n_boot}, "
        f"seed={seed}, alpha={alpha}); R axis = relative mean vs delta_r={dr}, "
        f"S axis = relative Sharpe vs delta_s={ds}; intervals from "
        "conformal.block_bootstrap_interval"
    )
    return {
        "n_candidates": k,
        "n_obs": n,
        "alpha": float(alpha),
        "delta_s": ds,
        "delta_r": dr,
        "surviving": len(surviving),
        "reality_check": reality_check(candidates, benchmark, n_boot=n_boot,
                                       block_len=block_len, seed=seed),
        "spa": spa(candidates, benchmark, n_boot=n_boot, block_len=block_len,
                   seed=seed),
        "candidates": rows,
        "basis": basis,
    }


def skewness(returns: list[float]) -> float | None:
    """Standardized skewness (γ3); None for <3 finite observations."""
    vals = _clean(returns)
    if len(vals) < 3:
        return None
    n = len(vals)
    mean = sum(vals) / n
    m2 = sum((v - mean) ** 2 for v in vals) / n
    if m2 == 0:
        return None
    m3 = sum((v - mean) ** 3 for v in vals) / n
    return m3 / (m2 ** 1.5)


def kurtosis(returns: list[float]) -> float | None:
    """Standardized kurtosis (γ4, normal = 3); None for <4 observations."""
    vals = _clean(returns)
    if len(vals) < 4:
        return None
    n = len(vals)
    mean = sum(vals) / n
    m2 = sum((v - mean) ** 2 for v in vals) / n
    if m2 == 0:
        return None
    m4 = sum((v - mean) ** 4 for v in vals) / n
    return m4 / (m2 ** 2)


def downside_deviation(returns: list[float], mar: float = 0.0,
                       periods_per_year: float = 252.0) -> float | None:
    """Annualized downside deviation about a minimum-return target (MAR).

    Only observations below the target contribute (Lean's Sortino
    denominator); None for an empty/short series.
    """
    vals = _clean(returns)
    if not vals:
        return None
    dd = sum(max(mar - v, 0.0) ** 2 for v in vals) / len(vals)
    return math.sqrt(dd * periods_per_year)


def sortino(returns: list[float], mar: float = 0.0,
            periods_per_year: float = 252.0) -> float | None:
    """Annualized Sortino: excess CAGR over target per unit of downside dev."""
    ddev = downside_deviation(returns, mar, periods_per_year)
    if ddev is None or ddev <= 0:
        return None
    return (cagr(returns, periods_per_year) - mar) / ddev


def tracking_error(returns: list[float], benchmark: list[float],
                   periods_per_year: float = 252.0) -> float | None:
    """Annualized std dev of (algo - benchmark) period returns."""
    r = _clean(returns)
    b = _clean(benchmark)
    n = min(len(r), len(b))
    if n < 2:
        return None
    diff = [r[i] - b[i] for i in range(n)]
    # A constant difference series - exact tracking, or a flat per-period cost
    # offset - leaves only floating-point residue, and the std of ~1e-19
    # residuals annualizes to a TE around 1e-18, which then divides into a
    # meaningless ratio (IEI 2026-09-16 surfaced te=7.7e-19 -> ir=-2.9e17 in
    # an analyst prompt). A spread that is within float precision of the
    # values themselves IS zero tracking error.
    spread = max(diff) - min(diff)
    if spread <= max(abs(x) for x in diff) * 1e-12:
        return 0.0
    md = sum(diff) / n
    var = sum((d - md) * (d - md) for d in diff) / (n - 1)
    return math.sqrt(var * periods_per_year)


def information_ratio(returns: list[float], benchmark: list[float],
                      periods_per_year: float = 252.0) -> float | None:
    """Annualized excess return per unit of tracking error."""
    te = tracking_error(returns, benchmark, periods_per_year)
    if te is None or te <= 0:
        return None
    return (cagr(returns, periods_per_year) - cagr(benchmark, periods_per_year)) / te


def beta(returns: list[float], benchmark: list[float],
         periods_per_year: float = 252.0) -> float | None:
    """Algo beta vs benchmark: cov(algo, bench) / var(bench)."""
    r = _clean(returns)
    b = _clean(benchmark)
    n = min(len(r), len(b))
    if n < 2:
        return None
    rb = r[:n]
    bb = b[:n]
    mr = sum(rb) / n
    mb = sum(bb) / n
    varb = sum((x - mb) ** 2 for x in bb) / (n - 1)
    if varb <= 0:
        return None
    cov = sum((rb[i] - mr) * (bb[i] - mb) for i in range(n)) / (n - 1)
    return cov / varb


def alpha(returns: list[float], benchmark: list[float], risk_free: float = 0.0,
          periods_per_year: float = 252.0) -> float | None:
    """Jensen's alpha: annPerf - (rf + beta*(benchAnnPerf - rf))."""
    b = beta(returns, benchmark, periods_per_year)
    if b is None:
        return None
    return (cagr(returns, periods_per_year) - risk_free
            - b * (cagr(benchmark, periods_per_year) - risk_free))


def treynor(returns: list[float], benchmark: list[float], risk_free: float = 0.0,
            periods_per_year: float = 252.0) -> float | None:
    """Excess annual return per unit of beta."""
    b = beta(returns, benchmark, periods_per_year)
    if b is None or b == 0:
        return None
    return (cagr(returns, periods_per_year) - risk_free) / b


def rolling_beta(returns: list[float], benchmark: list[float],
                 window: int = 132) -> list[float | None]:
    """Per-window beta series over aligned returns (Lean window 132 default)."""
    r = _clean(returns)
    b = _clean(benchmark)
    out: list[float | None] = []
    for end in range(window, min(len(r), len(b)) + 1):
        out.append(beta(r[end - window:end], b[end - window:end]))
    return out


def probabilistic_sharpe(returns: list[float], benchmark_sharpe: float = 0.0,
                         periods_per_year: float = 252.0) -> float | None:
    """Bailey & Lopez de Prado Probabilistic Sharpe Ratio.

    Uses the NON-annualized per-observation Sharpe (mean/std) as the point
    estimate, with skewness/kurtosis correction inside the estimator's
    standard error — PSR = Phi((SR_obs - SR_bench) /
    sqrt((1 - g3*SR + (g4-1)/4*SR^2)/(n-1))). None for <4 observations or a
    degenerate estimator variance. Advisory significance, not a mandate.
    """
    vals = _clean(returns)
    if len(vals) < 4:
        return None
    mean = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))
    if sd <= 0:
        return None
    sr = mean / sd
    g3 = skewness(vals)
    g4 = kurtosis(vals)  # standardized kurtosis, normal = 3
    if g3 is None or g4 is None:
        return None
    var_est = (1 - g3 * sr + (g4 - 1) / 4 * sr ** 2) / (len(vals) - 1)
    if var_est <= 0:
        return None
    z = (sr - benchmark_sharpe) / math.sqrt(var_est)
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def underwater_drawdowns(equity: list[float]) -> list[dict]:
    """Sequence of peak-to-trough-to-recovery drawdown events.

    Each event: ``{'peak','trough','depth','recovery'}`` where ``recovery`` is
    the number of bars to get back to the prior peak (None if still underwater
    at series end). Complement to the single ``max_drawdown`` scalar.
    """
    vals = _clean(equity)
    events: list[dict] = []
    if len(vals) < 2:
        return events
    peak = vals[0]
    trough = vals[0]
    trough_i = 0
    for i, v in enumerate(vals[1:], start=1):
        if v >= peak:
            if trough < peak:
                events.append({
                    "peak": peak,
                    "trough": trough,
                    "depth": (peak - trough) / peak if peak > 0 else 0.0,
                    "recovery": i - trough_i,
                })
            peak = v
            trough = v
            trough_i = i
        elif v < trough:
            trough = v
            trough_i = i
    if trough < peak:
        events.append({
            "peak": peak,
            "trough": trough,
            "depth": (peak - trough) / peak if peak > 0 else 0.0,
            "recovery": None,
        })
    return events


def calmar_ratio(returns: list[float], periods_per_year: float = 252.0) -> float | None:
    """Calmar ratio = annualized CAGR / max drawdown magnitude.

    0/positive-drawdown edge returns None (no meaningful risk ratio). Guards
    on <2 observations like the other CAGR-based stats.
    """
    vals = _clean(returns)
    if len(vals) < 2:
        return None
    eq = equity_curve(vals)
    mdd = max_drawdown(eq)
    if mdd <= 0:
        return None
    c = cagr(vals, periods_per_year)
    if c is None:
        return None
    return c / mdd


def ulcer_index(returns: list[float]) -> float | None:
    """Ulcer index = sqrt(mean(periodic drawdown^2)) over the equity curve.

    Penalizes sustained, not just the deepest, drawdowns (a Nautilus
    ready-made stat). None on <2 observations.
    """
    vals = _clean(returns)
    if len(vals) < 2:
        return None
    eq = equity_curve(vals)
    peak = eq[0]
    dds: list[float] = []
    for v in eq:
        peak = max(peak, v)
        dds.append((peak - v) / peak if peak > 0 else 0.0)
    mean_sq = sum(d * d for d in dds) / len(dds)
    return math.sqrt(mean_sq)


def burke_ratio(returns: list[float], periods_per_year: float = 252.0,
                risk_free: float = 0.0) -> float | None:
    """Burke ratio = annualized excess return / sqrt(sum of squared drawdowns).

    Penalizes the *frequency+size* of drawdown events (via underwater_drawdowns
    event DEPTHS), unlike max-drawdown which only sees the worst. None when no
    drawdown events or <2 obs.
    """
    vals = _clean(returns)
    if len(vals) < 2:
        return None
    eq = equity_curve(vals)
    events = underwater_drawdowns(eq)
    if not events:
        return None
    annual_c = cagr(vals, periods_per_year)
    if annual_c is None:
        return None
    denom = math.sqrt(sum((e["depth"] ** 2 for e in events), 0.0))
    if denom <= 0:
        return None
    return (annual_c - risk_free) / denom


def martin_ratio(returns: list[float], periods_per_year: float = 252.0,
                 risk_free: float = 0.0) -> float | None:
    """Martin ratio / Ulcer Performance Index = annualized excess return / Ulcer
    index. Ulcer penalizes *sustained* drawdowns; this is the UI- adjusted
    return. None when ulcer is 0 or <2 obs.
    """
    vals = _clean(returns)
    if len(vals) < 2:
        return None
    ui = ulcer_index(vals)
    if ui is None or ui <= 0:
        return None
    annual_c = cagr(vals, periods_per_year)
    if annual_c is None:
        return None
    return (annual_c - risk_free) / ui


def pain_index(returns: list[float]) -> float | None:
    """Pain index = mean periodic drawdown depth over the equity curve (a
    sustained-drawdown measure like ulcer, but arithmetic not RMS). None on <2
    obs.
    """
    vals = _clean(returns)
    if len(vals) < 2:
        return None
    eq = equity_curve(vals)
    peak = eq[0]
    dds: list[float] = []
    for v in eq:
        peak = max(peak, v)
        dds.append((peak - v) / peak if peak > 0 else 0.0)
    return sum(dds) / len(dds)


def pain_ratio(returns: list[float], periods_per_year: float = 252.0,
               risk_free: float = 0.0) -> float | None:
    """Pain ratio = annualized excess return / pain index. None when pain is
    0 or <2 obs.
    """
    vals = _clean(returns)
    if len(vals) < 2:
        return None
    pi = pain_index(vals)
    if pi is None or pi <= 0:
        return None
    annual_c = cagr(vals, periods_per_year)
    if annual_c is None:
        return None
    return (annual_c - risk_free) / pi


def capture_ratio(returns: list[float], benchmark: list[float], up: bool = True) -> float | None:
    """Up/down capture: average of (algo / benchmark) moves in up (or down) periods.

    Up capture = geometric mean of (1+r_algo)/(1+r_bench) over periods the
    benchmark rose; down capture over periods it fell. A value > 1.0 means the
    algo captured more of that direction than the benchmark. None when fewer
    than 2 aligned periods exist in that direction, or benchmark is flat.
    """
    a = _clean(returns)
    b = _clean(benchmark)
    n = min(len(a), len(b))
    if n < 2:
        return None
    ratios: list[float] = []
    for i in range(n):
        r_algo = a[i]
        r_bench = b[i]
        if r_bench is None or r_algo is None:
            continue
        is_up = r_bench > 0
        if is_up != up:
            continue
        try:
            ratios.append((1.0 + r_algo) / (1.0 + r_bench))
        except ZeroDivisionError:
            continue
    if not ratios:
        return None
    prod = 1.0
    for r in ratios:
        prod *= r
    return prod ** (1.0 / len(ratios)) - 1.0


def tail_ratio(returns: list[float]) -> float | None:
    """Tail ratio = average winning return / |average losing return|.

    A summary of payoff asymmetry (the Losses/Hits magnitude split Nautilus
    reports as winner_avg/loser_avg). None when there are no winners or no
    losers (>0 no positive mass guard).
    """
    vals = _clean(returns)
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v < 0]
    if not wins or not losses:
        return None
    avg_win = sum(wins) / len(wins)
    avg_loss = abs(sum(losses) / len(losses))
    if avg_loss <= 0:
        return None
    return avg_win / avg_loss


def expectancy_stats(wins: list[float], losses: list[float]) -> dict | None:
    """Trade-outcome summary: win rate, profit factor, expectancy, tail ratio.

    All sourced from the caller's win/loss per-trade lists (not the return
    series), the shape the pre-market paper ledger already records. Returns a
    dict of floats, or None when both lists are empty.
    """
    w = [float(x) for x in wins if x is not None]
    losses_f = [float(x) for x in losses if x is not None]
    if not w and not losses_f:
        return None
    n = len(w) + len(losses_f)
    win_rate = len(w) / n if n else 0.0
    gw = sum(w) if w else 0.0
    gl = abs(sum(losses_f)) if losses_f else 0.0
    profit_factor = (gw / gl) if gl > 0 else (float("inf") if gw > 0 else 0.0)
    avg_win = (sum(w) / len(w)) if w else 0.0
    avg_loss = (abs(sum(losses_f)) / len(losses_f)) if losses_f else 0.0
    tail = (avg_win / avg_loss) if (w and losses_f and avg_loss > 0) else None
    # Expectancy E = P(win)*avg_win - P(loss)*avg_loss (matches value_dip.expectancy).
    expectancy_v = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss)
    return {
        "n_trades": n,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy_v,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "tail_ratio": tail,
    }


def turnover(new_weights: dict, prev_weights: dict | None = None) -> float | None:
    """One-period portfolio turnover: ``1/2 * sum_i |w_i,t - w_i,t-1|``.

    Cookbook common-framework turnover. With ``prev_weights`` None the
    previous period is assumed zero (fresh book), so turnover is simply
    ``1/2 * gross``. None for an empty target book.
    """
    if not new_weights:
        return None
    names = set(new_weights) | set(prev_weights or {})
    acc = 0.0
    for n in names:
        t = new_weights.get(n, 0.0)
        p = (prev_weights or {}).get(n, 0.0)
        try:
            tf = float(t)
            pf = float(p)
        except (TypeError, ValueError):
            continue
        if math.isfinite(tf) and math.isfinite(pf):
            acc += abs(tf - pf)
    return 0.5 * acc


def turnover_cost(
    new_weights: dict, prev_weights: dict, cost_by_name: dict | None = None,
    base_cost: float = 0.001,
) -> float | None:
    """Cookbook cost approximation: ``sum_i |w_i,t - w_i,t-1| * c_i``.

    ``cost_by_name`` is a per-name one-way cost fraction (spread + commission
    + slippage); names without an entry use ``base_cost``. None when the
    target book is empty.
    """
    if not new_weights:
        return None
    names = set(new_weights) | set(prev_weights)
    acc = 0.0
    for n in names:
        t = new_weights.get(n, 0.0)
        p = prev_weights.get(n, 0.0)
        try:
            tf = float(t)
            pf = float(p)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(tf) or not math.isfinite(pf):
            continue
        c = cost_by_name.get(n, base_cost) if cost_by_name else base_cost
        acc += abs(tf - pf) * float(c)
    return acc


def gross_exposure(weights: dict) -> float | None:
    """Gross exposure ``sum_i |w_i|`` (leverage); None for an empty book."""
    if not weights:
        return None
    acc = 0.0
    for v in weights.values():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            acc += abs(f)
    return acc


def net_exposure(weights: dict) -> float | None:
    """Net exposure ``sum_i w_i`` (dollar neutrality check); None for empty."""
    if not weights:
        return None
    acc = 0.0
    for v in weights.values():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            acc += f
    return acc


def rolling_sharpe(returns: list, window: int = 252,
                   risk_free: float = 0.0, periods_per_year: float = 252.0) -> list:
    """Rolling-window annualized Sharpe (cookbook reporting checklist).

    One value per completed window, oldest first; the cookbook's
    rolling-12m-sharpe style trajectory for trend-stability checks. Empty
    when fewer than ``window`` observations.
    """
    vals = _clean(returns)
    out: list[float | None] = []
    for end in range(window, len(vals) + 1):
        out.append(sharpe(vals[end - window:end], risk_free, periods_per_year))
    return out


def regime_split_performance(
    returns: list,
    vol_percentile: list | None = None,
    trend: list | None = None,
    high_vol_at: float = 0.7,
    risk_free: float = 0.0,
) -> dict:
    """Performance by regime (cookbook reporting checklist).

    Splits the return series into low/high-volatility (``vol_percentile``
    series aligned to ``returns``) and bull/bear trend (``trend`` sign, or
    ``None`` = skipped) buckets and reports n / CAGR / Sharpe / max-drawdown
    per bucket. Pure, no fabrication: a missing regime input just skips that
    split.
    """
    vals = _clean(returns)
    out: dict = {}
    if len(vals) < 2:
        return out
    if vol_percentile:
        vols = [v for v in vol_percentile if v is not None]
        if len(vols) >= 2:
            lobes = {"low_vol": [], "high_vol": []}
            for r, v in zip(vals, vol_percentile, strict=False):
                if v is None:
                    continue
                lobes["high_vol" if float(v) >= high_vol_at else "low_vol"].append(r)
            for k, series in lobes.items():
                out[k] = _perf_block(series, risk_free)
    if trend:
        tvals = [t for t in trend if t is not None]
        if len(tvals) >= 2:
            lobes = {"bull": [], "bear": []}
            for r, t in zip(vals, trend, strict=False):
                if t is None:
                    continue
                lobes["bull" if float(t) >= 0 else "bear"].append(r)
            for k, series in lobes.items():
                out[k] = _perf_block(series, risk_free)
    return out


def _perf_block(returns: list, risk_free: float) -> dict:
    eq = equity_curve(returns)
    return {
        "n": len(returns),
        "cagr": round(cagr(returns), 6),
        "sharpe": round(sharpe(returns, risk_free), 4),
        "max_drawdown": round(max_drawdown(eq), 6),
    }


def implementation_shortfall(
    decision_price: float | None,
    arrival_price: float | None,
    fill_price: float | None,
    quantity: float | None = None,
    final_price: float | None = None,
    opportunity_days: float = 0.0,
) -> dict | None:
    """Implementation shortfall (TCA) on the paper ledger.

    ``IS = (fill - decision) - (final - decision) * outstanding/expected``
    simplified for a fully-filled order:
       explicit   = (fill - arrival) * qty         (slippage vs arrival)
       market     = (arrival - decision) * qty     (delay/momentum to arrival)
       opportunity = (final - decision) * qty * opportunity_frac
       IS$/notional = (explicit + market + opportunity) / (decision * qty)
    All prices must be > 0; ``quantity`` defaults to 1 (per-share IS).
    Returns ``{"explicit", "market_impact", "opportunity", "implementation_shortfall_bp",
    "notional", "n"}`` or None on missing inputs. Positive IS = cost/worse fill.
    """
    try:
        d = float(decision_price)
        a = float(arrival_price)
        fh = float(fill_price)
    except (TypeError, ValueError):
        return None
    if d <= 0 or a <= 0 or fh <= 0:
        return None
    qty = 1.0 if quantity is None else float(quantity)
    if qty <= 0:
        return None
    explicit = (fh - a) * qty
    market = (a - d) * qty
    opp = 0.0
    if final_price is not None:
        raw_final = float(final_price)
        if raw_final > 0:
            opp = (raw_final - d) * qty * max(0.0, float(opportunity_days))
    total = explicit + market + opp
    notional = d * qty
    return {
        "explicit": round(explicit, 4),
        "market_impact": round(market, 4),
        "opportunity": round(opp, 4),
        "implementation_shortfall_bp": round(total / notional * 1e4, 2),
        "notional": round(notional, 4),
    }


__all__ = [
    "net_returns", "total_return", "cagr", "volatility", "sharpe",
    "deflated_sharpe", "deflated_sharpe_report", "deflated_sharpe_ratio",
    "min_track_record_length",
    "max_drawdown", "equity_curve", "walk_forward_splits",
    "z_statistic", "max_abs_z", "effective_candidates", "inflation_diagnostics",
    "pbo_flag",
    "cscv_pbo", "purged_cpcv_splits", "cpcv_overfit_mask", "oos_split",
    "reality_check", "spa",
    "benchmark_table",
    "materiality_verdict", "family_materiality", "benjamini_yekutieli",
    "skewness", "kurtosis", "downside_deviation", "sortino",
    "tracking_error", "information_ratio", "beta", "alpha", "treynor",
    "rolling_beta", "probabilistic_sharpe", "underwater_drawdowns",
    "calmar_ratio", "ulcer_index", "capture_ratio", "tail_ratio",
    "expectancy_stats", "implementation_shortfall",
    "turnover", "turnover_cost", "gross_exposure", "net_exposure",
    "rolling_sharpe", "regime_split_performance",
    "burke_ratio", "martin_ratio", "pain_index", "pain_ratio",
]
