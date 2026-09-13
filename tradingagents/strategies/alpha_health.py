"""Alpha-health aggregation over emitted research decisions (the ledger).

The market-research material's key diagnostic: when a system stops emitting
Buy/Overweight, is that because the market got efficient (alpha vanished) or
because the scorer became too restrictive (score compression)? These are
pure, hermetic calculations over ledger rows already carrying forward returns
(see ``reporting.write_alpha_ledger`` + ``scripts/alpha_health.py``).

Every function takes/returns plain dicts - no I/O, no network. All labeling
thresholds are function parameters with advisory defaults (the materials'
calibration caution: never universal). Unmeasurable inputs return None / empty
dicts, never fabricated numbers.

Row shape (anything extra is ignored)::

    {"effective_date": "2026-09-04", "rating": "Hold", "score": 0,
     "wd_1": 0.001, "wd_5": 0.01, "wd_20": 0.03, "wd_60": 0.07}

``score`` is the numeric stance (Sell=-2 .. Buy=+2) attached by the
collector; forward-return columns ``wd_<horizon>`` are attached by
``attach_forward_returns``. Missing columns degrade to None.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone

RATING_ORDER = {"SELL": -2, "UNDERWEIGHT": -1, "HOLD": 0, "OVERWEIGHT": 1, "BUY": 2}
DEFAULT_HORIZONS = (1, 5, 20, 60)


def rating_to_number(rating) -> float | None:
    """Monotone numeric stance (SELL=-2 .. BUY=+2); None for unknown.

    Case-insensitive; used as ``score`` for rank IC / dispersion. None rows
    are dropped by every cross-sectional function (fail-closed).
    """
    if rating is None:
        return None
    return RATING_ORDER.get(str(rating).strip().upper())


def _f(a) -> float | None:
    """Finite float or None (never propagates non-finite / strings)."""
    try:
        v = float(a)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _mean(vals: Iterable | None) -> float | None:
    v = [_f(x) for x in (vals or [])]
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


def _std(vals, ddof: int = 1) -> float | None:
    v = [_f(x) for x in (vals or [])]
    v = [x for x in v if x is not None]
    if len(v) < 2:
        return None
    mu = sum(v) / len(v)
    return math.sqrt(sum((x - mu) ** 2 for x in v) / (len(v) - ddof))


def _quantile(sv: list[float], q: float) -> float:
    """Linear-interpolated quantile of a sorted sample."""
    if len(sv) == 1:
        return sv[0]
    pos = (len(sv) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sv) - 1)
    frac = pos - lo
    return sv[lo] * (1.0 - frac) + sv[hi] * frac


def _skew(vals: list[float]) -> float | None:
    n = len(vals)
    if n < 3:
        return None
    mu = sum(vals) / n
    s = math.sqrt(sum((x - mu) ** 2 for x in vals) / (n - 1))
    if not s:
        return None
    m3 = sum((x - mu) ** 3 for x in vals) / n
    return m3 / s ** 3


def score_distribution(rows: list[dict], score_key: str = "score") -> dict:
    """Distribution of the numeric stance across ``rows`` (doc layer 1).

    Compression check: if the interquartile range collapses toward one bucket
    (e.g. the whole universe sits at 0), the scorer cannot emit strong calls
    no matter what the market does.
    """
    v = [_f(r.get(score_key)) for r in rows]
    v = [x for x in v if x is not None]
    if not v:
        return {"n": 0}
    sv = sorted(v)
    n = len(sv)
    return {
        "n": n,
        "mean": sum(sv) / n,
        "std": _std(sv, ddof=0),
        "skew": _skew(sv),
        "min": sv[0],
        "p25": _quantile(sv, 0.25),
        "p50": _quantile(sv, 0.50),
        "p75": _quantile(sv, 0.75),
        "max": sv[-1],
    }


def cross_sectional_dispersion(
    rows: list[dict], score_key: str = "score", date_key: str = "effective_date"
) -> dict:
    """StdDev of numeric stance per date, then the mean of those stds (layer 3).

    Collapsing dispersion = "all stocks look increasingly similar" - a real
    scorer diagnostic, independent of market efficiency.
    """
    per_date: dict[str, list[float]] = {}
    for r in rows:
        s = _f(r.get(score_key))
        if s is None:
            continue
        per_date.setdefault(str(r.get(date_key) or ""), []).append(s)
    stss = []
    for d in sorted(per_date):
        st = _std(per_date[d], ddof=1)
        if st is not None:
            stss.append((d, st))
    if not stss:
        return {"mean_std": None, "per_date": {}}
    return {"mean_std": _mean([s for _, s in stss]), "per_date": dict(stss)}


def _rank_avg(vals: list[float | None]) -> list[float]:
    """Standard competition ranking with ties averaged (1-based)."""
    n = len(vals)
    order = sorted(range(n), key=lambda i: (vals[i] is None, vals[i]))
    out = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def _pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 2:
        return None
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if not sx or not sy:
        return None
    return cov / (sx * sy)


def rank_information_coefficient(
    rows: list[dict],
    horizon: int = 20,
    score_key: str = "score",
    fwd_key: str | None = None,
) -> float | None:
    """Rank IC between numeric stance and ``horizon``-day forward return.

    Spearman (average-tie ranks) - robust to the categorical stance scale.
    None when < 2 usable pairs. Layer 4 of the diagnostic doc.
    """
    if fwd_key is None:
        fwd_key = f"wd_{horizon}"
    pairs = []
    for r in rows:
        s = _f(r.get(score_key))
        f = _f(r.get(fwd_key))
        if s is None or f is None:
            continue
        pairs.append((s, f))
    if len(pairs) < 2:
        return None
    ra = _rank_avg([p[0] for p in pairs])
    rb = _rank_avg([p[1] for p in pairs])
    return _pearson(ra, rb)


def per_period_ic(
    rows: list[dict],
    horizon: int = 20,
    score_key: str = "score",
    period_key: str = "effective_date",
) -> dict:
    """Rank IC per period, then ICIR = mean(IC) / std(IC) (layer 4)."""
    per: dict[str, list[dict]] = {}
    for r in rows:
        per.setdefault(str(r.get(period_key) or ""), []).append(r)
    ics = []
    for d in sorted(per):
        ic = rank_information_coefficient(per[d], horizon, score_key)
        if ic is not None:
            ics.append((d, ic))
    if not ics:
        return {"per_period": {}, "icir": None, "mean_ic": None, "std_ic": None}
    vals = [ic for _, ic in ics]
    mu, sd = _mean(vals), _std(vals, ddof=1)
    # std at float-epsilon (identical per-period ICs) is unmeasurable, not inf
    icir = None if (mu is None or sd is None or sd < 1e-12) else (mu / sd)
    return {"per_period": dict(ics), "mean_ic": mu, "std_ic": sd, "icir": icir}


def horizon_alpha_curve(
    rows: list[dict],
    horizons=DEFAULT_HORIZONS,
    score_key: str = "score",
    long_min: float = 0.5,
) -> dict:
    """Alpha decay curve: E[fwd_h | long side] - E[fwd_h | all] per horizon.

    ``long_min`` marks the long side (numeric stance above it, i.e.
    Overweight/Buy). The excess over the unconditional mean isolates the
    signal's edge at each horizon - the doc's "when does my signal actually
    pay". Edge accruing with horizon (1d ~ 0, 20d > 0) means the edge is
    horizon-structured, not arbitraged by faster systems.
    """
    long_by_h: dict[int, list[float]] = {h: [] for h in horizons}
    all_by_h: dict[int, list[float]] = {h: [] for h in horizons}
    for r in rows:
        s = _f(r.get(score_key))
        for h in horizons:
            f = _f(r.get(f"wd_{h}"))
            if f is None:
                continue
            all_by_h[h].append(f)
            if s is not None and s > long_min:
                long_by_h[h].append(f)
    curve: dict[int, float | None] = {}
    for h in horizons:
        if not all_by_h[h]:
            curve[h] = None
            continue
        mu_all = sum(all_by_h[h]) / len(all_by_h[h])
        if not long_by_h[h]:
            curve[h] = None
            continue
        curve[h] = sum(long_by_h[h]) / len(long_by_h[h]) - mu_all
    return {
        "curve": curve,
        "long_n": {h: len(long_by_h[h]) for h in horizons},
        "all_n": {h: len(all_by_h[h]) for h in horizons},
    }


def win_rate_by_rating(
    rows: list[dict], horizon: int = 20, fwd_key: str | None = None
) -> dict:
    """Per rating band: n, mean forward return, win share (fwd > 0)."""
    if fwd_key is None:
        fwd_key = f"wd_{horizon}"
    by: dict[str, list[float]] = {}
    for r in rows:
        f = _f(r.get(fwd_key))
        if f is None:
            continue
        key = str(r.get("rating") or "UNKNOWN").upper()
        by.setdefault(key, []).append(f)
    out = {}
    for band in RATING_ORDER:
        v = by.get(band, [])
        if not v:
            continue
        out[band] = {
            "n": len(v),
            "mean": sum(v) / len(v),
            "win_share": sum(1 for x in v if x > 0) / len(v),
        }
    return out


def opportunity_counts(rows: list[dict]) -> dict:
    """Counts per rating band (the monitor box top section).

    Rows with no rating (None) - e.g. legacy artifacts the structured-PM
    validation rejected - are counted as ``n/a`` and never masquerade as a
    real rating band like UNKNOWN.
    """
    c = Counter(str(r.get("rating") or "n/a").upper() for r in rows)
    return {k: int(v) for k, v in sorted(c.items(),
            key=lambda kv: (0 if kv[0] == "N/A" else (RATING_ORDER.get(kv[0], 9)), kv[0]))}


def attach_forward_returns(
    rows: list[dict],
    dates: list[str],
    closes: list[float],
    horizons=DEFAULT_HORIZONS,
    date_key: str = "effective_date",
) -> list[dict]:
    """Attach ``wd_<h>`` forward returns to rows by matching ``date_key``.

    Alignment: the row's date is located in ``dates`` (sorted ascending) and
    the forward return uses the first bar at/after that date (a report's
    effective date may miss the vendor's bar list on holidays/partial days).
    Rows with an unmatched date get None forward returns - never synthetic.
    Returns new dicts; the inputs are untouched.
    """
    days = sorted(set(dates))
    index = {day: i for i, day in enumerate(days)}
    out = []
    for r in rows:
        row = dict(r)
        d = str(r.get(date_key) or "")
        idx = index.get(d)
        if idx is None:
            # first bar at/after the report date
            for i, day in enumerate(days):
                if day >= d:
                    idx = i
                    break
        for h in horizons:
            fk = f"wd_{h}"
            if idx is None:
                row[fk] = None
                continue
            j = idx + h
            if j < len(closes):
                c0 = closes[j - h]
                c1 = closes[j]
                row[fk] = (c1 / c0 - 1.0) if c0 else None
            else:
                row[fk] = None
        out.append(row)
    return out


def dispersion_label(mean_std: float | None, low: float = 0.5, high: float = 1.0) -> str:
    """Advisory label on the rating-space dispersion (bands are ±1 apart)."""
    if mean_std is None:
        return "UNKNOWN"
    if mean_std < low:
        return "LOW"
    if mean_std < high:
        return "MODERATE"
    return "HIGH"


def ic_label(ic: float | None, weak: float = 0.03, strong: float = 0.06) -> str:
    """Advisory label for a rank IC at one horizon (|ic|)."""
    if ic is None:
        return "UNKNOWN"
    a = abs(ic)
    if a < weak:
        return "WEAK"
    if a < strong:
        return "MODERATE"
    return "STRONG"


def alpha_decay_label(
    curve: dict, horizons=DEFAULT_HORIZONS, ratio: float = 1.5, tolerance: float = 1e-6
) -> str:
    """Advisory label: does edge accrue with horizon or is it front-loaded?

    Compares the mean excess at the longest vs the two shortest horizons with
    data. Advisory only - a curve built on < 20 signals is uninformative.
    """
    hs = [h for h in horizons if curve.get(h) is not None]
    if len(hs) < 2:
        return "UNKNOWN"
    short = max(curve[h] for h in hs if h <= max(horizons[:2]))
    long = curve[max(hs)]
    if abs(short) < tolerance:
        return "WEAK" if abs(long) < tolerance else "HORIZON-STRUCTURED"
    if long > short * (1.0 + ratio) and long > 0:
        return "HORIZON-STRUCTURED"
    if long < short * (1.0 - ratio):
        return "FRONT-LOADED/DECAYING"
    return "FLAT"


def alpha_health_report(
    rows: list[dict],
    horizons=DEFAULT_HORIZONS,
    score_key: str = "score",
    ic_horizon: int = 20,
) -> dict:
    """The monitor box: distributions, dispersion, rank IC, decay, win rates.

    ``rows`` should already carry ``wd_<h>`` columns (attach_forward_returns)
    and ``score`` (rating_to_number). Deterministic over its inputs.
    """
    dist = score_distribution(rows, score_key)
    disp = cross_sectional_dispersion(rows, score_key)
    ic = rank_information_coefficient(rows, ic_horizon, score_key)
    icr = per_period_ic(rows, ic_horizon, score_key)
    curve = horizon_alpha_curve(rows, horizons, score_key)
    ic_all = {
        h: rank_information_coefficient(rows, h, score_key) for h in horizons
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_signals": len(rows),
        "opportunity_counts": opportunity_counts(rows),
        "score_distribution": dist,
        "score_dispersion": {
            "mean_std": disp.get("mean_std"),
            "label": dispersion_label(disp.get("mean_std")),
            "per_date": disp.get("per_date", {}),
        },
        "rank_ic": {str(h): ic_all.get(h) for h in horizons},
        f"rank_ic_{ic_horizon}_label": ic_label(ic),
        "icir": icr.get("icir"),
        "alpha_decay": {
            "curve": {str(h): v for h, v in (curve.get("curve") or {}).items()},
            "long_n": curve.get("long_n"),
            "label": alpha_decay_label(curve.get("curve") or {}),
        },
        "horizon_win_rate": {str(h): win_rate_by_rating(rows, h) for h in horizons},
        "horizons": list(horizons),
    }


def _eval_unavailable(n: int, holding: int, reason: str) -> dict:
    """One evaluation row that could not be measured: count + reason."""
    return {"available": False, "n": int(n), "holding": int(holding), "reason": reason}


def score_evaluation_rows(
    scores_by_date: dict,
    prices: dict,
    holding: int = 5,
    n_buckets: int = 10,
    *,
    min_names: int = 4,
    min_obs: int = 5,
) -> dict:
    """Generic score-evaluation rows for any cross-sectional score.

    ``scores_by_date`` is ``{date: {ticker: score}}``; ``prices`` is
    ``{ticker: [close, ...]}`` whose index ``i`` is the ``i``-th date of
    ``sorted(scores_by_date)`` (a name with no bar at a date carries None).
    Pure and deterministic - no I/O, no network.

    Emits four rows, each stating its ``n`` and the ``holding`` period:

    * ``ic`` - mean cross-sectional rank IC + IC IR, computed by
      ``sentiment_research.rolling_information_coefficient`` (no second IC
      implementation);
    * ``deciles`` - mean ``holding``-day forward return per rank bucket (rank
      bucketing, the ``quintile_long_short`` semantics) + a monotonicity flag
      (Spearman of bucket index vs bucket mean), withheld until every bucket
      is populated;
    * ``coverage`` - scored names / universe, per date and pooled;
    * ``stability`` - mean rank autocorrelation of consecutive snapshots.

    A row is emitted only above ``min_obs`` periods; below that it is
    ``available=False`` with the observed count and the reason. These rows are
    inputs to the DSR/PBO multiple-testing check - never a standalone verdict.
    """
    from tradingagents.strategies.sentiment_research import (
        _bucket,
        _cross_section,
        _forward_returns,
        rolling_information_coefficient,
    )

    holding = max(1, int(holding))
    n_buckets = max(2, int(n_buckets))
    dates = sorted(scores_by_date) if isinstance(scores_by_date, dict) else []
    basis = (
        "score-evaluation rows are inputs to the DSR/PBO multiple-testing "
        "check, never a standalone verdict; each row states its n and the "
        f"{holding}d holding period, and a row below {min_obs} periods is "
        "unavailable"
    )
    meta = {
        "holding": holding,
        "n_buckets": n_buckets,
        "n_dates": len(dates),
        "min_names": min_names,
        "min_obs": min_obs,
        "basis": basis,
    }
    if not dates:
        return {
            **meta,
            "universe_n": 0,
            "ic": _eval_unavailable(0, holding, "no score snapshots"),
            "deciles": _eval_unavailable(0, holding, "no score snapshots"),
            "coverage": _eval_unavailable(0, holding, "no score snapshots"),
            "stability": _eval_unavailable(0, holding, "no score snapshots"),
        }

    def _sc(d, t):
        row = scores_by_date.get(d)
        return _f(row.get(t)) if isinstance(row, dict) else None

    panel = {
        t: [_sc(d, t) for d in dates]
        for t in sorted({t for d in dates for t in (scores_by_date.get(d) or {})})
    }
    px = (
        {t: list(prices[t]) for t in prices if isinstance(prices.get(t), (list, tuple))}
        if isinstance(prices, dict)
        else {}
    )
    universe = sorted(set(panel) | set(px))

    n_ret, fwd = _forward_returns(panel, px, holding)
    n_periods = max(0, n_ret - holding)

    def _usable(i: int) -> list:
        sig = _cross_section(panel, i)
        cs = _cross_section(fwd, i)
        return [t for t in sig if t in cs and cs[t] is not None]

    # --- IC: reuse the sentiment_research implementation ------------------
    usables = {i: _usable(i) for i in range(n_periods)}
    periods = sum(1 for names in usables.values() if len(names) >= min_names)
    if periods < 2:
        ic = _eval_unavailable(
            periods, holding,
            f"{periods} cross-sectional period(s) with >= {min_names} scored names",
        )
    elif periods < min_obs:
        ic = _eval_unavailable(
            periods, holding, f"{periods} cross-sectional periods < min_obs={min_obs}"
        )
    else:
        try:
            res = rolling_information_coefficient(
                panel, px, holding=holding, min_assets=min_names
            )
        except (ZeroDivisionError, ValueError, KeyError):
            res = None
        metrics = (res or {}).get("metrics") or {}
        if not metrics:
            ic = _eval_unavailable(periods, holding, "rank IC degenerate on this panel")
        else:
            ic = {
                "available": True,
                "n": int(metrics.get("periods") or periods),
                "holding": holding,
                "mean_rank_ic": metrics.get("mean_rank_ic"),
                "mean_pearson_ic": metrics.get("mean_pearson_ic"),
                "ic_ir": metrics.get("ic_ir"),
                "pct_positive": metrics.get("pct_positive"),
                "basis": f"cross-sectional Spearman rank IC vs {holding}d forward return",
            }

    # --- deciles: rank-bucketed mean forward returns ----------------------
    bucket_sum = [0.0] * n_buckets
    bucket_cnt = [0] * n_buckets
    obs = 0
    bucket_periods = 0
    for i in range(n_periods):
        names = usables.get(i) or []
        if len(names) < min_names:
            continue
        sig = _cross_section(panel, i)
        cs = _cross_section(fwd, i)
        xs = [sig[t] for t in names]
        bucket_periods += 1
        for t in names:
            b = _bucket(sig[t], xs, n_buckets)
            bucket_sum[b] += cs[t]
            bucket_cnt[b] += 1
            obs += 1
    bucket_means = [
        (bucket_sum[k] / bucket_cnt[k]) if bucket_cnt[k] else None
        for k in range(n_buckets)
    ]
    filled = sum(1 for m in bucket_means if m is not None)
    if filled == n_buckets:
        mono = _pearson(
            _rank_avg([float(k) for k in range(n_buckets)]),
            _rank_avg([float(m) for m in bucket_means]),
        )
    else:
        mono = None
    monotone = bool(mono is not None and mono >= 1.0 - 1e-9)
    if bucket_periods < min_obs or obs == 0:
        deciles = _eval_unavailable(
            obs, holding,
            f"{bucket_periods} period(s) / {obs} observation(s) < min_obs={min_obs}",
        )
    else:
        deciles = {
            "available": True,
            "n": obs,
            "periods": bucket_periods,
            "holding": holding,
            "n_buckets": n_buckets,
            "bucket_means": bucket_means,
            "bucket_counts": list(bucket_cnt),
            "buckets_filled": filled,
            "monotonicity": mono,
            "monotone": monotone,
            "basis": (
                f"rank-bucketed mean {holding}d forward return (bucket 1 = "
                "lowest score); monotonicity withheld until every bucket is "
                "populated"
            ),
        }

    # --- coverage: scored names / universe --------------------------------
    scored = 0
    universe_cells = 0
    cov_dates = 0
    per_date = {}
    for i, d in enumerate(dates):
        present = tot = 0
        for t in universe:
            p = px.get(t)
            if p is None or i >= len(p):
                continue
            if _f(p[i]) is None:
                continue
            tot += 1
            if _sc(d, t) is not None:
                present += 1
        per_date[d] = {"scored": present, "universe": tot}
        scored += present
        universe_cells += tot
        cov_dates += 1 if tot else 0
    ratio = (scored / universe_cells) if universe_cells else None
    if cov_dates < min_obs or universe_cells == 0:
        coverage = _eval_unavailable(
            universe_cells, holding,
            f"{cov_dates} date(s) with a priced universe < min_obs={min_obs}",
        )
    else:
        coverage = {
            "available": True,
            "n": universe_cells,
            "periods": cov_dates,
            "holding": holding,
            "scored": scored,
            "universe": universe_cells,
            "ratio": ratio,
            "per_date": per_date,
            "basis": (
                "scored names / universe (a name with a bar but no score "
                "counts against coverage)"
            ),
        }

    # --- stability: rank autocorrelation of consecutive snapshots ---------
    pairs = 0
    stab_sum = 0.0
    per_pair = {}
    for i in range(1, len(dates)):
        a = _cross_section(panel, i - 1)
        b = _cross_section(panel, i)
        common = [t for t in a if t in b]
        if len(common) < min_names:
            continue
        v = _pearson(
            _rank_avg([a[t] for t in common]), _rank_avg([b[t] for t in common])
        )
        if v is None:
            continue
        stab_sum += v
        per_pair[dates[i]] = v
        pairs += 1
    if pairs < min_obs:
        stability = _eval_unavailable(
            pairs, holding, f"{pairs} consecutive snapshot pair(s) < min_obs={min_obs}"
        )
    else:
        stability = {
            "available": True,
            "n": pairs,
            "holding": holding,
            "mean_rank_autocorr": stab_sum / pairs,
            "per_pair": per_pair,
            "basis": "mean Spearman rank autocorrelation of consecutive score snapshots",
        }

    return {
        **meta,
        "universe_n": len(universe),
        "ic": ic,
        "deciles": deciles,
        "coverage": coverage,
        "stability": stability,
    }


