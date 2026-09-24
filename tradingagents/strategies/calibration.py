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
"""

from __future__ import annotations

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


def excess_accuracy(pred, realized, baseline: str = "always_up", *,
                    folds: int = EXCESS_FOLDS, alpha: float = 0.1,
                    min_n: int = EXCESS_MIN_N) -> dict:
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
    interval, baseline, basis, unavailable}``. Missing, thin or unknown input —
    under ``min_n`` usable rows, an unknown ``baseline``, the gate off — is
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
        per.append({
            "fold": i + 1,
            "n": len(block),
            "model_hit_rate": round(model, 4),
            "baseline_hit_rate": round(base, 4),
            "excess": round(model - base, 4),
        })
    rec["per_fold"] = per
    try:
        from tradingagents.strategies.conformal import block_bootstrap_interval

        rec["interval"] = block_bootstrap_interval(diffs, alpha=alpha)
    except Exception:  # noqa: BLE001 - an interval is never worth breaking the read
        rec["interval"] = None
    rec["basis"] = (
        f"excess accuracy {rec['excess']:+.4f} over {len(rows)} row(s) on "
        f"identical rows: model hit rate {rec['model_hit_rate']:.4f} minus "
        f"always-up {rec['baseline_hit_rate']:.4f}; {k} sequential walk-forward "
        f"fold(s); the interval is a moving-block bootstrap over the paired "
        f"per-row differences, so read the realized block length, never the "
        f"nominal level alone"
    )
    return rec


__all__ = ["calibration_table", "scorecard", "_BINS", "fit_buckets",
           "fit_buckets_by_regime", "calibrated_confidence",
           "calibrated_confidence_by_regime", "isotonic_calibrate",
           "calibration_table_text", "record_calibration_entry",
           "excess_accuracy", "EXCESS_FOLDS", "EXCESS_MIN_N"]
