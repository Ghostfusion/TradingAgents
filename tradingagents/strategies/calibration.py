"""Confidence calibration + AI analyst scorecard (W1-2, W1-4).

From the prediction ledger (W1-1) rows scored against realized outcomes:

- ``calibration_table`` — bin predicted-confidence vs actual success
  (ChatGPT's 50-60% -> 56% table): shows whether "90% confidence" really
  wins ~90% of the time.
- ``scorecard`` — per-agent measurement: predictions, hit rate, avg return,
  calibration error (|reported - actual| per bin, weighted), horizon-window
  contribution. This is what lets the system say "fundamentals analyst is
  historically more reliable at 3-6 months; market analyst better at 1-5d".

All inputs are SCORED ledger rows (dicts with `outcome`); all output is
counts/ratios, None when there is nothing to measure (honest).

The two paired-significance producers (`mcnemar_paired`, `diebold_mariano`) are
plain functions over two arms' per-row values - no ledger, no config - and
`excess_accuracy` calls them on the rows it already scored.
"""

from __future__ import annotations

import math

_BINS = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0001)]


def calibration_table(scored_rows: list[dict]) -> list[dict]:
    """Predicted-confidence bins vs actual hit rate (W1-2).

    Each row: {bin, n, predicted_mid, actual_hit_rate, calibration_gap}.
    Rows with no confidence or no outcome are excluded (not counted as 0).
    """
    out = []
    for lo, hi in _BINS:
        rows = [
            r for r in (scored_rows or [])
            if r.get("confidence") is not None and lo <= r["confidence"] < hi
            and isinstance(r.get("outcome"), dict) and r["outcome"].get("hit") is not None
        ]
        if not rows:
            continue
        n = len(rows)
        hit = sum(1 for r in rows if r["outcome"]["hit"])
        mid = (lo + hi) / 2.0
        rate = hit / n
        out.append({
            "bin": f"{lo:.0%}-{min(hi, 1.0):.0%}",
            "n": n,
            "predicted_mid": round(mid, 3),
            "actual_hit_rate": round(rate, 3),
            "calibration_gap": round(rate - mid, 3),
        })
    return out


def _calibration_error(rows: list[dict]) -> float | None:
    tab = calibration_table(rows)
    if not tab:
        return None
    total = sum(t["n"] for t in tab)
    if total <= 0:
        return None
    err = sum(abs(t["calibration_gap"]) * t["n"] for t in tab) / total
    return round(err, 4)


# ---------------------------------------------------------------------------
# G2 confidence calibration (decision_hardening_spec G2): an online ledger of
# {confidence, won} stamps, bucketed per _BINS, mapped back onto a declared
# confidence. Mirrors the PM calibration wiring in graph/trading_graph.py.
# ---------------------------------------------------------------------------


def fit_buckets(entries: list[dict]) -> dict:
    """Bin calibration-ledger rows ``{confidence, won}`` into ``_BINS``.

    Returns ``{(lo, hi): {'n', 'win_rate'}}`` for non-empty bins; ``won`` must
    be a real bool/0-1 (None rows dropped, never counted as losses). Empty
    entries -> ``{}``.
    """
    out: dict = {}
    for lo, hi in _BINS:
        rows = [
            r for r in (entries or [])
            if r.get("confidence") is not None and lo <= r["confidence"] < hi
            and r.get("won") is not None
        ]
        if not rows:
            continue
        wins = sum(1 for r in rows if bool(r["won"]))
        out[(lo, hi)] = {"n": len(rows), "win_rate": round(wins / len(rows), 4)}
    return out


def fit_buckets_by_regime(entries: list[dict]) -> dict:
    """Partition calibration rows by ``regime`` (str) into per-regime buckets.

    Returns ``{regime: fit_buckets(that regime's rows)}``. Rows without a
    regime key go into ``"_all"`` (so a regime-less history still calibrates
    the single-table path). Empty entries -> ``{}``.
    """
    out: dict = {}
    by_regime: dict[str, list] = {}
    for r in entries or []:
        rg = str(r.get("regime") or "_all")
        by_regime.setdefault(rg, []).append(r)
    for rg, rows in by_regime.items():
        out[rg] = fit_buckets(rows)
    return out


def calibrated_confidence_by_regime(
    declared: float | None,
    tables_by_regime: dict,
    regime: str | None = None,
    min_n: int = 5,
    fallback_to_all: bool = True,
) -> float | None:
    """Map a declared confidence onto its regime's bucket win rate.

    Prefers the regime-specific table; when the regime has no rows / not
    enough stamps, falls back to ``"_all"`` (then identity). This is how the
    field's "calibration differs by market regime" guidance is applied while
    keeping a thin regime from being silently unconvered.
    """
    if declared is None:
        return None
    tables = tables_by_regime or {}
    if regime is not None:
        t = tables.get(str(regime))
        mapped = calibrated_confidence(declared, t, min_n=min_n)
        # Only use the regime result when it actually re-calibrated (i.e. the
        # bucket had >= min_n stamps); else fall through to the global.
        r_win = None
        if t:
            for (lo, hi), b in t.items():
                if lo <= float(declared) < hi:
                    r_win = b if b.get("n", 0) >= int(min_n) else None
                    break
        if r_win is not None and mapped is not None and mapped != float(declared):
            return mapped
    if fallback_to_all:
        t_all = tables.get("_all") or {}
        return calibrated_confidence(declared, t_all, min_n=min_n)
    return calibrated_confidence(declared, tables.get("_all") or {}, min_n=min_n)


def isotonic_calibrate(entries: list[dict]) -> object | None:
    """Fit an isotonic-regression calibrator over ``{confidence, won}``.

    Returns a scikit-learn ``IsotonicRegression`` object when scikit-learn is
    importable and there are >= 2 rows; else None (callers degrade to the
    bucket path). Lazy import keeps the plain-bucket pipeline hermetic.
    """
    try:
        from sklearn.isotonic import IsotonicRegression
    except Exception:  # noqa: BLE001 - sklearn optional
        return None
    rows = [
        (float(r["confidence"]), float(bool(r["won"])))
        for r in (entries or [])
        if r.get("confidence") is not None and r.get("won") is not None
    ]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    ys = [r[1] for r in rows]
    try:
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(xs, ys)
        return iso
    except Exception:  # noqa: BLE001 - fit can fail for malformed data
        return None


def calibrated_confidence(declared: float | None, table: dict,
                          min_n: int = 5) -> float | None:
    """Map a declared confidence onto its bucket's realized win rate.

    Returns the bucket ``win_rate`` when the bucket has >= ``min_n`` stamps,
    else the identity (``declared``) — a thin sample cannot re-calibrate.
    None when ``declared`` is None.
    """
    if declared is None:
        return None
    try:
        d = float(declared)
    except (TypeError, ValueError):
        return None
    for (lo, hi), b in (table or {}).items():
        if lo <= d < hi:
            if b.get("n", 0) >= int(min_n):
                return b.get("win_rate")
            return d
    return d  # no bucket for this confidence -> identity (honest)


def calibration_table_text(table: dict) -> str:
    """Render a ``fit_buckets`` table as a compact line. Empty table ->
    ``"no calibration history yet"`` (the graph uses that exact string to
    suppress the box).
    """
    if not table:
        return "no calibration history yet"
    parts = []
    for (lo, hi), b in sorted(table.items()):
        parts.append(
            f"{lo:.0%}-{hi:.0%}: n={b['n']} win_rate={b['win_rate']:.1%}"
        )
    return "calibration table | " + " | ".join(parts)


def record_calibration_entry(path: str, source: str, ticker: str,
                             date: str, confidence: float | None,
                             won: bool | None) -> None:
    """Append one ``{source, ticker, date, confidence, won}`` row to the JSONL
    ledger at ``path`` (best-effort; caller guards the try/except). No row is
    written when ``confidence``/``won`` are None (never fabricate)."""
    if confidence is None or won is None or not path:
        return
    import json as _json
    import os

    row = {
        "source": source,
        "ticker": str(ticker),
        "date": str(date),
        "confidence": round(float(confidence), 4),
        "won": bool(won),
    }
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(_json.dumps(row) + "\n")
    except OSError:
        return


def scorecard(scored_rows: list[dict], agent_field: str = "agent") -> list[dict]:
    """Per-agent measurement (W1-4).

    Groups scored ledger rows by ``agent_field`` (analyst name, debate role,
    any stored field) and reports: predictions, hit rate, avg return, mean
    |return|, and calibration error. Sorted by hit rate desc.
    """
    from collections import defaultdict

    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in (scored_rows or []):
        a = str(r.get(agent_field) or "unknown")
        by_agent[a].append(r)
    out = []
    for agent, rows in sorted(by_agent.items()):
        scored = [r for r in rows if isinstance(r.get("outcome"), dict)]
        n = len(scored)
        if n == 0:
            out.append({"agent": agent, "predictions": len(rows), "hit_rate": None,
                        "avg_return_pct": None, "calibration_error": None})
            continue
        hits = sum(1 for r in scored if r["outcome"].get("hit"))
        rets = [r["outcome"]["return_pct"] for r in scored
                if r["outcome"].get("return_pct") is not None]
        avg_ret = sum(rets) / len(rets) if rets else None
        out.append({
            "agent": agent,
            "predictions": len(rows),
            "hit_rate": round(hits / n, 3) if n else None,
            "avg_return_pct": round(avg_ret, 3) if avg_ret is not None else None,
            "calibration_error": _calibration_error(rows),
        })
    return sorted(out, key=lambda o: (o["hit_rate"] is None, -(o["hit_rate"] or 0)))


# ---------------------------------------------------------------------------
# H4 excess accuracy (paper-survey honest-evaluation). Every hit rate this
# module and `alpha_eval.alpha_score` publish is quoted with no reference to
# what it is worth on the same rows: a 58% directional hit rate means nothing
# until the always-up base rate over the identical window is beside it. This
# reports the difference, per walk-forward fold, with the interval H11 earns.
# ---------------------------------------------------------------------------

#: Below this many usable rows the excess-accuracy report is refused.
EXCESS_MIN_N = 40
#: Sequential walk-forward folds the per-fold table is cut into.
EXCESS_FOLDS = 5


def _ceiling_gate() -> bool:
    """Is the H4 accuracy-ceiling instrument switched on? (``enable_accuracy_ceiling``)

    The same gate as ``alpha_eval.ceiling_ratio``: both are the one accuracy
    instrument. Off by default, so a gate-off caller reads exactly what it read
    before the excess existed. A config read must never break the read it guards.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_accuracy_ceiling", False))


def mcnemar_paired(correct_a: list, correct_b: list) -> dict | None:
    """McNemar's paired test on two arms' per-row correctness (H4).

    ``correct_a`` / ``correct_b`` are the two arms' hit booleans on the IDENTICAL
    rows, in order - the pairing is the whole test, and comparing two hit rates
    as if they were independent throws away the correspondence between them.
    Only the DISCORDANT pairs carry information:

    ``b`` = A right and B wrong, ``c`` = A wrong and B right. Under the null of
    no difference each discordant pair is a fair coin, so the exact two-sided
    p-value is ``min(1, 2 * P(X <= min(b, c)))`` for ``X ~ Binomial(b + c, 0.5)``.
    The exact binomial is used rather than the asymptotic chi-square because a
    paired hit test at these sample sizes is routinely too small for it, and an
    approximate p-value inside a significance claim is the thing these
    instruments exist to avoid.

    Returns ``{"agree_both", "agree_neither", "b", "c", "n_pairs",
    "n_discordant", "p_value", "method", "basis"}``, or ``None`` when the arms
    are not the same length or there are no rows. Nothing discordant reads
    ``p_value = 1.0``: two arms that agreed on every row are not evidence of a
    difference.
    """
    arm_a = list(correct_a or [])
    arm_b = list(correct_b or [])
    if not arm_a or len(arm_a) != len(arm_b):
        return None
    agree_both = agree_neither = b = c = 0
    for x, y in zip(arm_a, arm_b, strict=True):
        xv, yv = bool(x), bool(y)
        if xv and yv:
            agree_both += 1
        elif not xv and not yv:
            agree_neither += 1
        elif xv:
            b += 1
        else:
            c += 1
    discordant = b + c
    if discordant == 0:
        p_value = 1.0
        method = "exact_binomial (no discordant pair)"
    else:
        lower = min(b, c)
        tail = sum(math.comb(discordant, i) for i in range(lower + 1)) / (2.0 ** discordant)
        p_value = min(1.0, 2.0 * tail)
        method = "exact_binomial"
    return {
        "agree_both": agree_both,
        "agree_neither": agree_neither,
        "b": b,
        "c": c,
        "n_pairs": len(arm_a),
        "n_discordant": discordant,
        "p_value": p_value,
        "method": method,
        "basis": (
            f"McNemar on {len(arm_a)} paired row(s): {b} row(s) only A got right, "
            f"{c} only B; the exact two-sided binomial p over the {discordant} "
            "discordant pair(s), which is where all the information is"
        ),
    }


def mz_regression(actual: list, forecast: list, *, alpha: float = 0.05) -> dict | None:
    """E6: the Mincer-Zarnowitz calibration regression ``actual = a + b*forecast``.

    Regresses the realized value on the forecast: a *calibrated* forecast has
    ``a = 0`` and ``b = 1`` (the forecast is an unbiased, unit-slope predictor).
    Reports the OLS slope/intercept with their standard errors, R-squared, and
    the joint F-test of ``(a, b) = (0, 1)`` (the restricted model is
    ``actual = forecast``); ``calibrated`` is whether that joint null is NOT
    rejected at ``alpha`` - the MZ diagnostic the Diebold-Mariano test does not
    provide (DM says which arm is better, MZ says whether the forecast is even
    the right scale).

    ``None`` on fewer than three usable pairs, a forecast with no variance (the
    slope is undefined), or a constant actual. A perfect fit (``actual ==
    forecast``) is ``calibrated`` with ``f_stat`` ``None`` - there is no residual
    variance to test against.
    """
    pairs = []
    for a, f in zip(actual or [], forecast or [], strict=False):
        try:
            pairs.append((float(a), float(f)))
        except (TypeError, ValueError):
            continue
    n = len(pairs)
    if n < 3:
        return None
    xs = [f for _a, f in pairs]
    ys = [a for a, _f in pairs]
    xm = sum(xs) / n
    ym = sum(ys) / n
    sxx = sum((x - xm) ** 2 for x in xs)
    tss = sum((y - ym) ** 2 for y in ys)
    if sxx <= 0.0 or tss <= 0.0:
        return None
    slope = sum((x - xm) * (y - ym) for x, y in pairs) / sxx
    intercept = ym - slope * xm
    rss = sum((y - (intercept + slope * x)) ** 2 for x, y in pairs)
    df = n - 2
    r2 = 1.0 - rss / tss
    calibrated = True
    f_stat = None
    p_value = None
    se_slope = None
    se_intercept = None
    if rss > 0.0 and df >= 1:
        s2 = rss / df
        se_slope = math.sqrt(s2 / sxx)
        se_intercept = math.sqrt(s2 * (1.0 / n + xm * xm / sxx))
        # Joint F of (a, b) = (0, 1): restricted residual sum is (y - x)^2.
        rss_r = sum((y - x) ** 2 for x, y in pairs)
        f_stat = ((rss_r - rss) / 2.0) / s2
        try:
            from scipy import stats as _st

            p_value = float(_st.f.sf(f_stat, 2, df))
            calibrated = p_value > float(alpha)
        except Exception:  # noqa: BLE001 - a missing p is not a fabricated one
            p_value = None
            calibrated = False
    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r2,
        "se_slope": se_slope,
        "se_intercept": se_intercept,
        "f_stat": f_stat,
        "p_value": p_value,
        "n": n,
        "calibrated": calibrated,
        "alpha": float(alpha),
        "basis": (
            f"Mincer-Zarnowitz OLS actual = {intercept:+.6f} + {slope:.6f}*forecast "
            f"over {n} pair(s), R^2 {r2:.4f}; a calibrated forecast has "
            f"(intercept, slope) = (0, 1) - the joint F "
            f"{'n/a (perfect fit)' if f_stat is None else f'{f_stat:.4f}'} "
            f"p {'n/a' if p_value is None else f'{p_value:.6f}'} "
            f"-> {'calibrated' if calibrated else 'NOT calibrated'} at {float(alpha):.0%}"
        ),
    }


def diebold_mariano(losses_a: list, losses_b: list, *, max_lag: int = 0,
                    alpha: float = 0.05) -> dict | None:
    """Diebold-Mariano test on two loss series over the same forecast origins.

    ``losses_a`` / ``losses_b`` are per-origin losses (lower is better) for the
    two forecasts on the IDENTICAL origins, in order. The test is on the mean
    loss differential ``d_t = a_t - b_t``: the statistic is
    ``mean(d) / sqrt(HAC_var(d) / n)`` with a Newey-West Bartlett kernel of
    ``max_lag`` lags and weights ``1 - L/(max_lag + 1)``. The HAC variance is
    what makes the test valid when the differentials are serially correlated -
    overlapping forecast windows make them so, and ``max_lag = h - 1`` is the
    standard choice for an ``h``-step horizon (``0`` for one-step, which
    degenerates to a t-test on the mean). It is also what McNemar does not do:
    that test's exact p assumes independent pairs.

    The p-value is two-sided from the normal (DM's own asymptotic result;
    Harvey-Leybourne-Newbold's small-sample ``t_{n-1}`` refinement is NOT
    applied, and the basis says so).

    Returns ``{"mean_differential", "statistic", "p_value", "hac_variance",
    "max_lag", "n", "favours", "significant", "alpha", "method", "basis"}`` or
    ``None`` for fewer than 3 paired losses or a non-positive HAC variance.
    ``favours`` names the arm the SIGN points to (``"a"`` when A's mean loss is
    lower, ``"b"`` when B's is, ``"neither"`` on an exact tie), so the direction
    never rests on a sign convention.
    """
    arm_a = [float(x) for x in (losses_a or [])]
    arm_b = [float(x) for x in (losses_b or [])]
    n = min(len(arm_a), len(arm_b))
    if n < 3:
        return None
    diffs = [arm_a[i] - arm_b[i] for i in range(n)]
    mean = sum(diffs) / n
    dev = [d - mean for d in diffs]
    lag = max(0, int(max_lag))
    hac = sum(d * d for d in dev) / n
    for step in range(1, min(lag, n - 1) + 1):
        weight = 1.0 - step / (lag + 1.0)
        cov = sum(dev[t] * dev[t - step] for t in range(step, n)) / n
        hac += 2.0 * weight * cov
    if hac <= 0.0 or not math.isfinite(hac):
        return None
    statistic = mean / math.sqrt(hac / n)
    from statistics import NormalDist

    p_value = 2.0 * (1.0 - NormalDist().cdf(abs(statistic)))
    if mean < 0.0:
        favours = "a"
    elif mean > 0.0:
        favours = "b"
    else:
        favours = "neither"
    return {
        "mean_differential": mean,
        "statistic": statistic,
        "p_value": p_value,
        "hac_variance": hac,
        "max_lag": lag,
        "n": n,
        "favours": favours,
        "significant": bool(p_value <= float(alpha)),
        "alpha": float(alpha),
        "method": "normal (DM asymptotic; no HLN t refinement)",
        "basis": (
            f"Diebold-Mariano on {n} paired loss(es), Newey-West Bartlett kernel with "
            f"{lag} lag(s); mean loss differential {mean:+.6f} (negative = A's loss is "
            f"lower), statistic {statistic:+.4f}, two-sided normal p {p_value:.6f}"
        ),
    }


def excess_accuracy(pred, realized, baseline: str = "always_up", *,
                    folds: int = EXCESS_FOLDS, alpha: float = 0.1,
                    min_n: int = EXCESS_MIN_N, dm_max_lag: int = 0) -> dict:
    """H4: the model's hit rate minus the always-up baseline's, on the same rows.

    ``pred`` and ``realized`` are the forecast and the realized return on the
    same rows, in order. The model calls the sign of ``pred``; the ``always_up``
    baseline calls +1 on every row, so its hit rate over a window is just the
    share of positive realized returns. Both are scored on the *identical*
    rows — a row with a zero return or no forecast sign carries no direction and
    is excluded from both counts, never counted as a miss for either arm.

    ``per_fold`` cuts the rows into ``folds`` sequential walk-forward blocks and
    reports each arm's hit rate and the difference, so one lucky block is
    visible rather than averaged away. ``interval`` is H11's moving-block
    bootstrap over the paired per-row differences (``model_hit - base_hit``),
    whose block length comes from the series' own autocorrelation: the excess
    is a mean over adjacent observations, and an IID interval under-covers it.

    Returns ``{n, folds, per_fold, model_hit_rate, baseline_hit_rate, excess,
    interval, mcnemar, diebold_mariano, baseline, basis, unavailable}``.
    ``mcnemar`` is the paired whole-series hit test and ``diebold_mariano`` the
    paired test on the per-row 0/1 miss loss (so both judge the same object; the
    DM carries the HAC correction the exact McNemar, which assumes independent
    pairs, cannot). ``per_fold`` carries each fold's McNemar p and whether it
    survives the family correction over the folds. Missing, thin or unknown input
    — under ``min_n`` usable rows, an unknown ``baseline``, the gate off — is
    ``unavailable`` with the reason, never a zero.
    """
    rec = {
        "n": 0,
        "folds": int(folds),
        "per_fold": [],
        "model_hit_rate": None,
        "baseline_hit_rate": None,
        "excess": None,
        "interval": None,
        "mcnemar": None,
        "diebold_mariano": None,
        "baseline": baseline,
        "basis": None,
        "unavailable": None,
    }
    if not _ceiling_gate():
        rec["unavailable"] = "excess accuracy off (enable_accuracy_ceiling)"
        return rec
    if baseline != "always_up":
        rec["unavailable"] = (
            f"excess accuracy unavailable: unknown baseline {baseline!r} "
            f"(only 'always_up' is defined)"
        )
        return rec
    rows: list[tuple[float, float]] = []
    for p, r in zip(pred or [], realized or [], strict=False):
        try:
            pv = float(p)
            rv = float(r)
        except (TypeError, ValueError):
            continue
        if pv == 0.0 or rv == 0.0:
            continue  # no direction on one side: not a miss for either arm
        rows.append((pv, rv))
    rec["n"] = len(rows)
    if len(rows) < max(2, int(min_n)):
        rec["unavailable"] = (
            f"excess accuracy unavailable: {len(rows)} usable row(s) below the "
            f"{int(min_n)}-row floor"
        )
        return rec
    diffs = [
        (1.0 if pv * rv > 0.0 else 0.0) - (1.0 if rv > 0.0 else 0.0)
        for pv, rv in rows
    ]
    rec["model_hit_rate"] = sum(1.0 for pv, rv in rows if pv * rv > 0.0) / len(rows)
    rec["baseline_hit_rate"] = sum(1.0 for _, rv in rows if rv > 0.0) / len(rows)
    rec["excess"] = sum(diffs) / len(diffs)
    k = max(1, min(int(folds), len(rows)))
    rec["folds"] = k
    per = []
    for i in range(k):
        start = i * len(rows) // k
        stop = (i + 1) * len(rows) // k
        block = rows[start:stop]
        if not block:
            continue
        model = sum(1.0 for pv, rv in block if pv * rv > 0.0) / len(block)
        base = sum(1.0 for _, rv in block if rv > 0.0) / len(block)
        fold_test = mcnemar_paired(
            [pv * rv > 0.0 for pv, rv in block],
            [rv > 0.0 for _pv, rv in block],
        )
        per.append({
            "fold": i + 1,
            "n": len(block),
            "model_hit_rate": round(model, 4),
            "baseline_hit_rate": round(base, 4),
            "excess": round(model - base, 4),
            "mcnemar_p": None if fold_test is None else round(fold_test["p_value"], 6),
            "survives": False,
        })
    # The fold tests are corrected as a family. What the family IS is stated
    # rather than implied: these are sequential blocks of ONE series, so the
    # correction covers looking at the same sample k times - not the number of
    # candidates searched across a population (that family is the score panel's).
    from tradingagents.strategies.evaluate import benjamini_yekutieli

    fold_fdr = benjamini_yekutieli([p["mcnemar_p"] for p in per], alpha)
    if fold_fdr is not None:
        for row, survives in zip(per, fold_fdr["surviving"], strict=True):
            row["survives"] = bool(survives)
    rec["per_fold"] = per
    # The whole-series paired tests on the SAME object - the per-row hit / its
    # 0/1 miss loss. The DM carries the HAC correction for serially correlated
    # differentials, which is precisely what McNemar's exact p cannot do.
    rec["mcnemar"] = mcnemar_paired(
        [pv * rv > 0.0 for pv, rv in rows], [rv > 0.0 for _pv, rv in rows],
    )
    rec["diebold_mariano"] = diebold_mariano(
        [0.0 if pv * rv > 0.0 else 1.0 for pv, rv in rows],
        [0.0 if rv > 0.0 else 1.0 for _pv, rv in rows],
        max_lag=int(dm_max_lag), alpha=alpha,
    )
    try:
        from tradingagents.strategies.conformal import block_bootstrap_interval

        rec["interval"] = block_bootstrap_interval(diffs, alpha=alpha)
    except Exception:  # noqa: BLE001 - an interval is never worth breaking the read
        rec["interval"] = None
    rec["basis"] = (
        f"excess accuracy {rec['excess']:+.4f} over {len(rows)} row(s) on "
        f"identical rows: model hit rate {rec['model_hit_rate']:.4f} minus "
        f"always-up {rec['baseline_hit_rate']:.4f}; {k} sequential walk-forward "
        f"fold(s), their McNemar p-values corrected as a family "
        f"({fold_fdr['method'] if fold_fdr else 'uncorrected - FDR unavailable'}); "
        f"paired whole-series McNemar and Diebold-Mariano (max_lag={int(dm_max_lag)}) "
        f"judge the same per-row miss object; the interval is a moving-block "
        f"bootstrap over the paired per-row differences, so read the realized "
        f"block length, never the nominal level alone"
    )
    return rec


__all__ = ["calibration_table", "scorecard", "_BINS", "fit_buckets",
           "fit_buckets_by_regime", "calibrated_confidence",
           "calibrated_confidence_by_regime", "isotonic_calibrate",
           "calibration_table_text", "record_calibration_entry",
           "excess_accuracy", "EXCESS_FOLDS", "EXCESS_MIN_N",
           "mcnemar_paired", "diebold_mariano", "mz_regression"]
