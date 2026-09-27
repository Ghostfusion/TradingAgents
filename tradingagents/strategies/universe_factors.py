"""Phase-2 universe producers (``docs/scores/MASTER_PLAN.md`` §5, the ``UNIV-*``
rows) — the survey's single-system gaps that the tree has the *data* for but no
formula.

Everything here is a **pure function over a caller-supplied input**. None of
these functions fetches anything: the existing (and cached) readers live in
``dataflows/`` and the caller hands their parsed output in. That is the rule
this module exists to hold — no new vendor call, no network in a test, and no
fabricated fallback (``NA != 0``: a quantity that cannot be measured returns
``None`` **with a reason**, never ``0``).

Vendor-blocked survey systems (IV rank, ETF net flow, moat, governance, ESG,
multi-model consensus, AI adoption/threat) are deliberately **absent** here:
they are out of scope because no reachable source measures them, and a proxy
would be a fabricated number.

One open question is left open on purpose — ``_forecast_dispersion`` records
``ScoreUniverse.md`` D-15 (the survey files dispersion under *uncertainty* while
its canonical source, Diether/Malloy/Scherbina 2002, makes it a **return
signal**). This module builds the statistic and does not decide its placement.

**Every producer here is underscore-private on purpose.** Each is built and
tested but has no caller outside this module yet, and a leaf for this family
would mean a new analyst tool (a toolset plus a ``ScoreContextContract.md``
§13.3 contract change) — its own round, not something to fake here. Leading
underscore names are exempt from the wiring gate
(``tests/test_calc_agent_wiring.py::test_public_calc_reachable_or_whitelisted``),
so this keeps that gate honest rather than whitelisting. A later round promotes
each producer to a public name with its leaf in the same change; each docstring
names the ``MASTER_PLAN.md`` item it awaits.
"""

from __future__ import annotations

import math

from . import cross_section

# --- Stated floors (a floor is a policy; it is printed, never silent) -------

#: Fewest target levels ``_forecast_dispersion`` needs to measure a spread.
#: The vendor triple is mean/high/low; without both ends there is no range.
PRICE_TARGET_MIN_LEVELS = 2

#: Fewest names in a cross-section before ``_size_factor`` will winsorise-z it.
#: Below this the winsorised tails and the standard deviation are not stable.
SIZE_MIN_N = 5

#: Fewest annual growth observations before ``_earnings_acceleration`` differences
#: them. ``sane_eps_yoy`` / ``sane_revenue_yoy`` yield only 4-5 annual points, so
#: a single delta from 2 points is unverifiable against anything.
EARNINGS_ACCEL_MIN_PERIODS = 3

#: Fewest annual EPS levels before ``_earnings_persistence`` runs. 2 points give a
#: sigma, 3 give a lag-1 pair; the floor is 4 so the autocorrelation has more
#: than one pair and the sigma is not one observation.
PERSISTENCE_MIN_PERIODS = 4

#: Trailing window (observations) and the hard floor for ``_economic_sensitivity``.
#: A per-name macro beta is meaningless over a handful of aligned points.
MACRO_WINDOW = 60
MACRO_MIN_OBS = 20

#: Notional (USD) at or above which a print is treated as a block for
#: ``_block_flow``. A conventional large-print threshold; a hypothesis.
BLOCK_MIN_NOTIONAL = 1_000_000.0


def _num(value) -> float | None:
    """Finite float, or None for a missing / unparseable / non-finite value."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _stdev(values: list[float], *, ddof: int = 1) -> float | None:
    """Sample standard deviation, or None when there are too few points."""
    n = len(values)
    if n - ddof <= 0:
        return None
    m = sum(values) / n
    var = sum((v - m) ** 2 for v in values) / (n - ddof)
    return math.sqrt(var)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation of two equal-length series, or None on zero variance."""
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    mx = sum(xs[:n]) / n
    my = sum(ys[:n]) / n
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    vx = sum((xs[i] - mx) ** 2 for i in range(n))
    vy = sum((ys[i] - my) ** 2 for i in range(n))
    if vx <= 0 or vy <= 0:
        return None
    return cov / math.sqrt(vx * vy)


def _ols_beta(xs: list[float], ys: list[float]) -> float | None:
    """Univariate OLS slope of ``ys`` on ``xs`` (``Cov/Var``), or None on a flat x."""
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    mx = sum(xs[:n]) / n
    my = sum(ys[:n]) / n
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / (n - 1)
    var = sum((xs[i] - mx) ** 2 for i in range(n)) / (n - 1)
    if var <= 0:
        return None
    return cov / var


# --- §4.2/§4.3 price-target upside, and §28 forecast dispersion -------------


def _forecast_dispersion(
    target_mean=None,
    target_high=None,
    target_low=None,
    *,
    target_median=None,
) -> dict:
    """Analyst target-price dispersion = ``(high - low) / mean`` for one name.

    Source: the vendor price-target triple the analyst-ratings leaf already
    fetches and prints (Finnhub ``targetMean``/``targetHigh``/``targetLow``;
    yfinance ``analyst_price_targets`` mean/high/low — ``dataflows/finnhub.py::
    get_analyst_ratings_finnhub`` and ``dataflows/y_finance.py::
    get_analyst_ratings_yfinance``). This is pure arithmetic over those numbers;
    the caller passes them in (the fetch is the cached one — no new vendor call).

    Scale/unit: a **fraction** (0.10 = the analyst range spans 10% of the mean
    target); a small positive number. ``target_median`` is accepted for context
    and counted in ``n`` but the range statistic uses high/low.

    Conventions:
    - ``None``-valued keys plus a ``reason`` when the spread cannot be measured
      (fewer than ``PRICE_TARGET_MIN_LEVELS`` of high/low present, a missing or
      zero mean, or a non-positive range).

    This is the per-name value; the **cross-sectional** use (§28) z-scores or
    ranks it over a panel of names — that panel is the caller's.

    **Open question (ScoreUniverse.md D-15, left undecided here):** the survey
    files forecast dispersion under *uncertainty*, but its canonical source
    (Diether, Malloy & Scherbina 2002) finds higher dispersion predicts *lower*
    future returns — a **return signal**, not a risk proxy. This function
    builds the statistic and does not decide where it belongs.

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-FDISPers.

    Returns ``{"dispersion", "n", "reason"}``.
    """
    hi = _num(target_high)
    lo = _num(target_low)
    mean = _num(target_mean)
    med = _num(target_median)
    n_levels = sum(1 for v in (mean, med, hi, lo) if v is not None)

    if hi is None or lo is None:
        return {
            "dispersion": None,
            "n": n_levels,
            "reason": (
                "target dispersion unmeasured: need both targetHigh and "
                "targetLow (the analyst range), vendor returned fewer than "
                f"{PRICE_TARGET_MIN_LEVELS} levels"
            ),
        }
    if mean is None or mean == 0:
        return {
            "dispersion": None,
            "n": n_levels,
            "reason": (
                "target dispersion unmeasured: no non-zero targetMean to scale "
                "the high-low range by"
            ),
        }
    if hi < lo:
        return {
            "dispersion": None,
            "n": n_levels,
            "reason": "target dispersion unmeasured: targetHigh < targetLow (inconsistent vendor triple)",
        }
    return {
        "dispersion": (hi - lo) / abs(mean),
        "n": n_levels,
        "reason": None,
    }


def _price_target_read(
    target_mean=None,
    target_median=None,
    target_high=None,
    target_low=None,
    price=None,
) -> dict:
    """Price-target **upside** and **dispersion** from the vendor triple + close.

    UNIV-PTARGET (§4.2/§4.3). Source: the same cached analyst-target fetch as
    ``_forecast_dispersion`` (``dataflows/finnhub.py::get_analyst_ratings_finnhub``
    and ``dataflows/y_finance.py::get_analyst_ratings_yfinance`` print the
    mean/median/high/low consensus today and nothing consumed it), plus the
    latest close.

    - ``upside = (target - price) / price`` where ``target`` is the mean target
      when present, else the median. Unit: a **fraction** (+0.20 = 20% to target).
    - ``dispersion`` is ``_forecast_dispersion(...)`` for the same name.

    ``None``-valued keys plus a ``reason`` when the close or the target is
    missing / non-positive. Pure arithmetic; no vendor call.

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-PTARGET.

    Returns ``{"upside", "target", "target_kind", "dispersion", "n_levels",
    "reason", "basis"}``.
    """
    px = _num(price)
    mean = _num(target_mean)
    med = _num(target_median)
    if mean is not None:
        target, kind = mean, "mean"
    elif med is not None:
        target, kind = med, "median"
    else:
        target, kind = None, None

    disp = _forecast_dispersion(
        target_mean=target_mean,
        target_high=target_high,
        target_low=target_low,
        target_median=target_median,
    )

    reasons: list[str] = []
    upside = None
    if px is None:
        reasons.append("no close price supplied")
    elif px <= 0:
        reasons.append(f"non-positive close price ({px:g})")
    if target is None:
        reasons.append("no mean or median target supplied")
    if upside is None and px is not None and px > 0 and target is not None:
        upside = (target - px) / px
    if disp["reason"]:
        reasons.append(disp["reason"])

    return {
        "upside": upside,
        "target": target,
        "target_kind": kind,
        "dispersion": disp["dispersion"],
        "n_levels": disp["n"],
        "reason": "; ".join(reasons) if reasons else None,
        "basis": (
            f"_price_target_read: target={target} ({kind}); "
            f"upside=(target-price)/price over price={px}; "
            f"dispersion=(high-low)/|mean|; no fabricated fallback (NA != 0)"
        ),
    }


# --- §16 insider ratio + transaction-size abnormality -----------------------


def _insider_ratio(
    buys=None,
    sells=None,
    buy_value=None,
    sell_value=None,
) -> dict:
    """Insider buy/sell ratio (IBS) and average open-market transaction size.

    UNIV-INSIDER (§16). Source: the Form-4 open-market counts and dollar values
    the repo already reads in ``dataflows/massive.py::get_form4_insider_massive``
    (it separates transaction code ``P`` from ``S`` and sums ``transaction_value``
    today; this producer is the arithmetic it never did). The caller passes the
    counts/values in — no vendor call here.

    - ``ibs = buys / (buys + sells)`` — a **fraction** in [0, 1] (0.5 = balanced;
      >0.5 net accumulation). ``None`` with a reason when there are no
      open-market transactions (never ``0`` by default).
    - ``avg_txn_value`` = ``(buy_value + sell_value) / (buys + sells)`` — the
      window's average transaction size in **USD**. ``None`` with a reason when
      the counts exist but no dollar values were supplied.

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-INSIDER.

    Returns ``{"ibs", "avg_txn_value", "n_buys", "n_sells", "reason", "basis"}``.
    """
    nb = _num(buys)
    ns = _num(sells)
    bv = _num(buy_value)
    sv = _num(sell_value)
    total = None if (nb is None or ns is None) else nb + ns

    if nb is None or ns is None:
        return {
            "ibs": None,
            "avg_txn_value": None,
            "n_buys": nb,
            "n_sells": ns,
            "reason": "insider ratio unmeasured: Form-4 buy/sell counts not supplied",
            "basis": "_insider_ratio: buys/(buys+sells); avg_txn_value=(buy$+sell$)/(buys+sells)",
        }
    if total <= 0:
        return {
            "ibs": None,
            "avg_txn_value": None,
            "n_buys": nb,
            "n_sells": ns,
            "reason": "insider ratio unmeasured: no open-market Form-4 buys or sells in the window",
            "basis": "_insider_ratio: buys/(buys+sells); avg_txn_value=(buy$+sell$)/(buys+sells)",
        }
    avg = None
    if bv is not None and sv is not None:
        avg = (bv + sv) / total

    reasons = []
    if avg is None:
        reasons.append("average transaction size unmeasured: Form-4 dollar values not supplied")
    return {
        "ibs": nb / total,
        "avg_txn_value": avg,
        "n_buys": nb,
        "n_sells": ns,
        "reason": "; ".join(reasons) if reasons else None,
        "basis": "_insider_ratio: buys/(buys+sells); avg_txn_value=(buy$+sell$)/(buys+sells)",
    }


# --- §1 size factor ----------------------------------------------------------


def _size_factor(
    market_caps: dict,
    *,
    min_n: int = SIZE_MIN_N,
    winsor_q: float = 0.05,
) -> dict:
    """Winsorised cross-sectional ``log(market_cap)`` size factor.

    UNIV-SIZE (§1). Source: a caller-supplied cross-section ``{ticker:
    market_cap}`` in the reporting **currency's absolute units** (e.g. USD).
    This replaces nothing — ``strategies/size.py`` is position *sizing*, and
    ``factor_schema`` carries no size category (that schema category would go
    with this factor; ``factor_schema.py`` is owned elsewhere).

    Pipeline: ``log`` of each positive cap -> winsorise at the ``winsor_q`` /
    ``1 - winsor_q`` quantiles (``cross_section.winsorize``) -> cross-sectional
    z-score (``cross_section.cross_sectional_z``). Sign convention: a **larger**
    cap gets a **positive** z (the small-cap/``Banz`` direction is a hypothesis
    the consumer applies, not one baked in here).

    ``None``-valued keys plus a ``reason`` when fewer than ``min_n`` names have
    a positive cap, or the cross-section has zero dispersion. The minimum
    cross-section size is stated: ``min_n`` (default ``SIZE_MIN_N``).

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-SIZE.

    Returns ``{"factor": {ticker: z} | None, "n", "min_n", "reason", "basis"}``.
    """
    caps = {
        str(t): v
        for t, raw in (market_caps or {}).items()
        if (v := _num(raw)) is not None and v > 0
    }
    n = len(caps)
    if n < int(min_n):
        return {
            "factor": None,
            "n": n,
            "min_n": int(min_n),
            "reason": (
                f"size factor unmeasured: cross-section has {n} name(s) with a "
                f"positive market cap, below the stated floor min_n={int(min_n)}"
            ),
            "basis": "_size_factor: z(winsorised log(market_cap))",
        }
    tickers = list(caps)
    logs = [math.log(caps[t]) for t in tickers]
    wins = cross_section.winsorize(logs, lower_q=winsor_q, upper_q=1.0 - winsor_q)
    pairs = [(t, w) for t, w in zip(tickers, wins, strict=False) if w is not None]
    z = cross_section.cross_sectional_z([w for _, w in pairs])
    if z is None:
        return {
            "factor": None,
            "n": n,
            "min_n": int(min_n),
            "reason": "size factor unmeasured: cross-section has zero dispersion in log(market_cap)",
            "basis": "_size_factor: z(winsorised log(market_cap))",
        }
    return {
        "factor": {t: zz for (t, _), zz in zip(pairs, z["z"], strict=False)},
        "n": n,
        "min_n": int(min_n),
        "reason": None,
        "basis": (
            f"_size_factor: {n} names, winsorised at {winsor_q:g}/{1 - winsor_q:g} "
            "quantiles, cross-sectional z of log(market_cap); positive = larger cap"
        ),
    }


# --- §3 earnings acceleration -----------------------------------------------


def _earnings_acceleration(
    growth_series,
    *,
    min_periods: int = EARNINGS_ACCEL_MIN_PERIODS,
) -> dict:
    """``Δ(growth)`` — the change in a YoY growth series over one annual period.

    UNIV-EARNACC (§3). Source: the ``sane_eps_yoy`` / ``sane_revenue_yoy``
    series (``dataflows/statement_parsing.py::sane_eps_yoy:1028`` /
    ``::sane_revenue_yoy:1048``). Those are YoY growth **fractions**; the caller
    supplies the annual series already ordered oldest -> newest.

    ``acceleration`` is the latest first difference of the growth series
    (a **fraction** delta, e.g. YoY 0.10 -> 0.14 gives +0.04). ``deltas`` is the
    full first-difference series.

    Stated floor: fewer than ``min_periods`` finite annual points
    (``EARNINGS_ACCEL_MIN_PERIODS`` = 3) — only 4-5 annual points exist, and a
    single delta from 2 points cannot be checked against a prior one. Below the
    floor the value is ``None`` with a reason.

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-EARNACC.

    Returns ``{"acceleration", "deltas", "n", "floor", "reason", "basis"}``.
    """
    series = [v for v in (_num(x) for x in (growth_series or [])) if v is not None]
    floor = int(min_periods)
    if len(series) < floor:
        return {
            "acceleration": None,
            "deltas": None,
            "n": len(series),
            "floor": floor,
            "reason": (
                f"earnings acceleration unmeasured: {len(series)} annual growth "
                f"point(s), below the stated floor of {floor}"
            ),
            "basis": "_earnings_acceleration: first difference of the annual YoY growth series",
        }
    deltas = [series[i] - series[i - 1] for i in range(1, len(series))]
    return {
        "acceleration": deltas[-1],
        "deltas": deltas,
        "n": len(series),
        "floor": floor,
        "reason": None,
        "basis": (
            f"_earnings_acceleration: Δ(growth) over {len(series)} annual points, "
            f"latest delta = growth[-1] - growth[-2]"
        ),
    }


# --- §27 earnings persistence -----------------------------------------------


def _earnings_persistence(
    eps_series,
    *,
    min_periods: int = PERSISTENCE_MIN_PERIODS,
) -> dict:
    """``σ(ΔEPS)`` and the lag-1 autocorrelation of an annual EPS series.

    UNIV-PERSIST (§27). Source: an annual EPS **level** series (currency per
    share), ordered oldest -> newest. Accrual *quality* already exists (Sloan /
    Dechow-Dichev in ``strategies/earnings_quality.py``); this persistence
    statistic had no producer.

    - ``sigma_delta_eps``: sample standard deviation (``ddof=1``) of the
      first differences of EPS, in **currency per share**. A large value means
      the earnings stream jumps year to year.
    - ``autocorr_lag1``: Pearson correlation of ``eps[t]`` with ``eps[t+1]``
      (dimensionless, [-1, 1]). Positive = persistent level.

    Stated floor: fewer than ``min_periods`` finite annual levels
    (``PERSISTENCE_MIN_PERIODS`` = 4) — 2 points cannot give both a stable sigma
    and a lag-1 pair. Below the floor the values are ``None`` with a reason.

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-PERSIST.

    Returns ``{"sigma_delta_eps", "autocorr_lag1", "n", "floor", "reason",
    "basis"}``.
    """
    series = [v for v in (_num(x) for x in (eps_series or [])) if v is not None]
    floor = int(min_periods)
    if len(series) < floor:
        return {
            "sigma_delta_eps": None,
            "autocorr_lag1": None,
            "n": len(series),
            "floor": floor,
            "reason": (
                f"earnings persistence unmeasured: {len(series)} annual EPS "
                f"level(s), below the stated floor of {floor}"
            ),
            "basis": "_earnings_persistence: σ(ΔEPS) and lag-1 EPS autocorrelation",
        }
    deltas = [series[i] - series[i - 1] for i in range(1, len(series))]
    sigma = _stdev(deltas, ddof=1)
    ac = _pearson(series[:-1], series[1:])
    reasons = []
    if sigma is None:
        reasons.append("σ(ΔEPS) unmeasured: too few deltas")
    if ac is None:
        reasons.append("lag-1 autocorrelation unmeasured: zero-variance EPS level series")
    return {
        "sigma_delta_eps": sigma,
        "autocorr_lag1": ac,
        "n": len(series),
        "floor": floor,
        "reason": "; ".join(reasons) if reasons else None,
        "basis": (
            f"_earnings_persistence over {len(series)} annual EPS levels: "
            f"sample σ(ΔEPS), Pearson corr(eps[:-1], eps[1:])"
        ),
    }


# --- §18 reinvestment rate (the level-ROIC convention is another owner's) ---


def _reinvestment_rate(
    nopat=None,
    invested_capital=None,
    *,
    prior_invested_capital=None,
    growth=None,
) -> dict:
    """Reinvestment rate = the share of NOPAT ploughed back into the capital base.

    UNIV-CAPALLOC (§18), the **reinvestment rate only** (level ROIC and
    shareholder yield are another owner's, in ``strategies/ratios.py``).

    Source: caller-supplied ``nopat`` (currency units), ``invested_capital``
    (currency units), and **one** of:

    - ``prior_invested_capital`` -> ``rate = (IC - prior_IC) / NOPAT``
      (method ``delta_ic_over_nopat``), or
    - ``growth`` (the invested-capital growth fraction) ->
      ``rate = growth × IC / NOPAT`` (method ``growth_times_ic_over_nopat``).

    Scale: a fraction (0.25 = 25% of NOPAT reinvested). ``None`` with a reason
    on a non-positive / missing capital base, a non-positive / missing NOPAT, or
    neither a prior base nor a growth rate supplied.

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-CAPALLOC.

    Returns ``{"_reinvestment_rate", "method", "reason", "basis"}``.
    """
    npat = _num(nopat)
    ic = _num(invested_capital)
    base = "_reinvestment_rate = ΔIC/NOPAT or growth × IC/NOPAT"
    if ic is None or ic <= 0:
        return {
            "_reinvestment_rate": None,
            "method": None,
            "reason": "reinvestment rate unmeasured: invested capital is missing or non-positive",
            "basis": base,
        }
    if npat is None or npat <= 0:
        return {
            "_reinvestment_rate": None,
            "method": None,
            "reason": "reinvestment rate unmeasured: NOPAT is missing or non-positive (no base to reinvest against)",
            "basis": base,
        }
    prior = _num(prior_invested_capital)
    g = _num(growth)
    if prior is not None:
        return {
            "_reinvestment_rate": (ic - prior) / npat,
            "method": "delta_ic_over_nopat",
            "reason": None,
            "basis": f"{base}; used ΔIC = IC({ic:g}) - prior_IC({prior:g}) over NOPAT({npat:g})",
        }
    if g is not None:
        return {
            "_reinvestment_rate": g * ic / npat,
            "method": "growth_times_ic_over_nopat",
            "reason": None,
            "basis": f"{base}; used growth({g:g}) × IC({ic:g}) over NOPAT({npat:g})",
        }
    return {
        "_reinvestment_rate": None,
        "method": None,
        "reason": "reinvestment rate unmeasured: supply prior_invested_capital or growth",
        "basis": base,
    }


# --- §22 economic sensitivity (per-name macro beta) -------------------------


def _economic_sensitivity(
    stock_returns: dict,
    macro_series: dict,
    *,
    window: int = MACRO_WINDOW,
    min_obs: int = MACRO_MIN_OBS,
) -> dict:
    """Per-name OLS beta on date-aligned macro series (rates, inflation, USD, commodity).

    UNIV-ECONSENS (§22). Source: ``stock_returns`` is ``{date: return}`` for the
    name; ``macro_series`` is ``{macro_name: {date: value}}`` (a rate's change, an
    inflation print, a USD index move, …). **The caller fetches** — FRED is
    reachable (``dataflows/fred.py::get_series_values`` returns ``(date, value)``
    pairs) but is a network read, so this function takes the series as arguments
    rather than calling it (the choice the task allowed).

    Alignment is by **date string intersection**, newest-first truncated to the
    trailing ``window`` observations. Beta = ``Cov(stock, macro) / Var(macro)``
    (a slope: units are stock-return per macro-return). A macro with fewer than
    ``min_obs`` aligned points (``MACRO_MIN_OBS``) or a flat macro series is
    ``None`` for that macro, with the aligned ``n`` reported.

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-ECONSENS.

    Returns ``{"betas": {macro: float | None}, "aligned_n": {macro: int},
    "window": int, "min_obs": int, "reason", "basis"}``.
    """
    sr = {str(d): v for d, raw in (stock_returns or {}).items() if (v := _num(raw)) is not None}
    macros = macro_series or {}
    win = int(window)
    floor = int(min_obs)
    betas: dict[str, float | None] = {}
    aligned_n: dict[str, int] = {}
    if not sr or not macros:
        return {
            "betas": {},
            "aligned_n": {},
            "window": win,
            "min_obs": floor,
            "reason": "economic sensitivity unmeasured: supply stock_returns and at least one macro series",
            "basis": "_economic_sensitivity: OLS beta of stock returns on each aligned macro series",
        }
    for name, series in macros.items():
        clean = {str(d): v for d, raw in (series or {}).items() if (v := _num(raw)) is not None}
        common = sorted(set(sr) & set(clean))[-win:]
        aligned_n[str(name)] = len(common)
        if len(common) < floor:
            betas[str(name)] = None
            continue
        xs = [clean[d] for d in common]
        ys = [sr[d] for d in common]
        betas[str(name)] = _ols_beta(xs, ys)
    return {
        "betas": betas,
        "aligned_n": aligned_n,
        "window": win,
        "min_obs": floor,
        "reason": None,
        "basis": (
            f"_economic_sensitivity: OLS beta Cov(stock,macro)/Var(macro), "
            f"trailing window={win}, min aligned obs={floor}; "
            f"caller supplied {len(macros)} macro series"
        ),
    }


# --- §? block flow (large-print detection beside the dark-pool raw flow) ----


def _block_flow(
    prints=None,
    *,
    min_block_notional: float = BLOCK_MIN_NOTIONAL,
) -> dict:
    """Block-flow share from **per-print** notionals (large-print detection).

    UNIV-BLOCKFLOW. The existing dark-pool read (``dataflows/finra.py::
    get_dark_pool_flow:109``) returns FINRA OTC Transparency *weekly aggregates*
    per MPID (shares / trades / notional) — it cannot separate a block from
    retail. This function therefore takes per-print rows (each a mapping with a
    ``notional`` in USD) and reports the share of notional at or above
    ``min_block_notional``:

    - ``block_share`` = block notional / total notional (fraction),
    - ``block_notional`` / ``total_notional`` (USD), ``n_prints`` / ``n_blocks``.

    **Refusal (the honest default):** if the source can only supply *aggregate*
    weekly flow (or any row without a per-print ``notional``), this returns
    ``None`` with that reason rather than a proxy — an average trade size from
    weekly aggregates does not identify blocks. ``None`` also when no prints are
    supplied or none carry a usable notional.

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-BLOCKFLOW.

    Returns ``{"block_share", "block_notional", "total_notional", "n_prints",
    "n_blocks", "reason", "basis"}``.
    """
    base = (
        "_block_flow: share of per-print notional >= "
        f"{min_block_notional:g} USD; FINRA weeklySummary aggregates cannot feed this"
    )
    if not prints:
        return {
            "block_share": None,
            "block_notional": None,
            "total_notional": None,
            "n_prints": 0,
            "n_blocks": 0,
            "reason": (
                "block flow unmeasured: no per-print rows supplied (FINRA weeklySummary "
                "publishes weekly aggregates only, so block vs retail cannot be separated)"
            ),
            "basis": base,
        }
    rows = list(prints)
    notionals = []
    for row in rows:
        val = row.get("notional") if isinstance(row, dict) else None
        n = _num(val)
        if n is None:
            return {
                "block_share": None,
                "block_notional": None,
                "total_notional": None,
                "n_prints": len(rows),
                "n_blocks": 0,
                "reason": (
                    "block flow unmeasured: print rows carry no per-print notional "
                    "(weekly aggregates cannot separate block from retail)"
                ),
                "basis": base,
            }
        notionals.append(n)
    total = sum(notionals)
    if total <= 0:
        return {
            "block_share": None,
            "block_notional": None,
            "total_notional": total,
            "n_prints": len(notionals),
            "n_blocks": 0,
            "reason": "block flow unmeasured: total print notional is non-positive",
            "basis": base,
        }
    blocks = [n for n in notionals if n >= float(min_block_notional)]
    return {
        "block_share": sum(blocks) / total,
        "block_notional": sum(blocks),
        "total_notional": total,
        "n_prints": len(notionals),
        "n_blocks": len(blocks),
        "reason": None,
        "basis": base,
    }


# --- §25/§26 dilution rate and buyback yield --------------------------------


def _dilution_rate(
    shares_issued=None,
    prior_shares=None,
) -> dict:
    """``DilutionRate`` from the share-count change over the prior share count.

    UNIV-DILUTE (§25). Source: ``shares_issued`` is the net share change the repo
    already derives in ``dataflows/statement_parsing.py::enrich_screen_ratios``
    (``shares_issued = current_shares - prior_shares``); ``prior_shares`` is the
    prior-period share count. The caller passes both in.

    ``_dilution_rate = shares_issued / prior_shares`` — a **fraction** (positive =
    net issuance, negative = net buyback; 0.02 = 2% dilution).

    ``None`` with a reason when the change is missing or ``prior_shares`` is
    missing / non-positive (the change alone cannot be turned into a rate).

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-DILUTE.

    Returns ``{"_dilution_rate", "shares_issued", "prior_shares", "reason",
    "basis"}``.
    """
    issued = _num(shares_issued)
    prior = _num(prior_shares)
    base = "_dilution_rate = shares_issued / prior_shares"
    if issued is None:
        return {
            "_dilution_rate": None,
            "shares_issued": None,
            "prior_shares": prior,
            "reason": "dilution rate unmeasured: no share-count change (shares_issued) supplied",
            "basis": base,
        }
    if prior is None or prior <= 0:
        return {
            "_dilution_rate": None,
            "shares_issued": issued,
            "prior_shares": prior,
            "reason": "dilution rate unmeasured: prior share count is missing or non-positive",
            "basis": base,
        }
    return {
        "_dilution_rate": issued / prior,
        "shares_issued": issued,
        "prior_shares": prior,
        "reason": None,
        "basis": base,
    }


def _buyback_yield(
    repurchase_spend=None,
    *,
    market_cap=None,
) -> dict:
    """``BuybackYield`` = repurchase spend / market cap (a **dollar** yield).

    UNIV-DILUTE (§26). Source: ``repurchase_spend`` is the period's cash spent on
    buybacks (currency units), already read by the ratios path. The standard
    yield needs a **price** denominator; the repo has no repurchase-*price* feed
    (``shares × price`` is unavailable), so the caller must supply ``market_cap``
    (the unambiguous denominator) explicitly.

    ``_buyback_yield = repurchase_spend / market_cap`` — a **fraction** (0.03 =
    3% of market cap returned via buybacks).

    ``None`` with a reason when the spend is missing, or when ``market_cap`` is
    missing / non-positive (the dollar yield is denominator-limited — a wrong
    denominator is refused rather than guessed).

    Built and tested; **awaiting its leaf** — underscore-private so the
    wiring gate stays honest. ``MASTER_PLAN.md`` item UNIV-DILUTE.

    Returns ``{"_buyback_yield", "denominator", "reason", "basis"}``.
    """
    spend = _num(repurchase_spend)
    cap = _num(market_cap)
    base = "_buyback_yield = repurchase_spend / market_cap"
    if spend is None:
        return {
            "_buyback_yield": None,
            "denominator": None,
            "reason": "buyback yield unmeasured: no repurchase spend supplied",
            "basis": base,
        }
    if cap is None or cap <= 0:
        return {
            "_buyback_yield": None,
            "denominator": None,
            "reason": (
                "buyback yield unmeasured: no positive market-cap denominator "
                "supplied (no repurchase-price feed exists, so spend alone cannot form the yield)"
            ),
            "basis": base,
        }
    return {
        "_buyback_yield": spend / cap,
        "denominator": "market_cap",
        "reason": None,
        "basis": f"{base} with denominator=market_cap({cap:g})",
    }


# The producers are underscore-private pending their leaves (see the module
# docstring); the constants below are the stated floors.
__all__ = [
    "PRICE_TARGET_MIN_LEVELS",
    "SIZE_MIN_N",
    "EARNINGS_ACCEL_MIN_PERIODS",
    "PERSISTENCE_MIN_PERIODS",
    "MACRO_WINDOW",
    "MACRO_MIN_OBS",
    "BLOCK_MIN_NOTIONAL",
    "_forecast_dispersion",
    "_price_target_read",
    "_insider_ratio",
    "_size_factor",
    "_earnings_acceleration",
    "_earnings_persistence",
    "_reinvestment_rate",
    "_economic_sensitivity",
    "_block_flow",
    "_dilution_rate",
    "_buyback_yield",
]
