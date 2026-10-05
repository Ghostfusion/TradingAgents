"""Decision prediction ledger + outcome scoring (W1-1, W1-3).

Every analysis decision becomes an immutable prediction row: rating,
direction, entry/target/stop levels, confidence, horizon. Later, a
deterministic scorer joins the row with the realized close series and
computes the outcome — hit/return, target reached, stop hit, and the
MAE/MFE excursion metrics (W1-3). This is the foundation for the whole
measurement workstream: scorecard, calibration, regime-conditional,
ablation.

Append-only JSONL (like the invalidation ledger): rows are immutable once
written; scoring is a pure read that never mutates them.

All honest: a missing level is None, never assumed; a series shorter than
the horizon scores with what exists; no data -> no outcome.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path

from tradingagents.strategies.forecast_contract import (
    ForecastEvaluation,
    ForecastRecord,
    _ledger_writer_token,
)

_LEDGER_NAME = "predictions.jsonl"
_FORECAST_LEDGER_NAME = "forecasts.jsonl"


def _ledger_path(results_dir: str | None) -> Path:
    base = results_dir or os.path.expanduser("~/.tradingagents/logs")
    return Path(base) / _LEDGER_NAME


def log_decision(
    ticker: str,
    date: str,
    rating: str,
    direction: str = "",
    entry: float | None = None,
    target: float | None = None,
    stop: float | None = None,
    confidence: float | None = None,
    horizon_days: int = 60,
    data_quality: str = "unknown",
    results_dir: str | None = None,
    prompt_condition: str | None = None,
    closes: list | None = None,
    **extra,
) -> dict:
    """Append one immutable prediction row; returns it (never raises on IO).

    ``prompt_condition`` (N5) is the prompt-condition arm the run was produced
    under, recorded as a first-class column: a run that did not record one
    carries an explicit ``None``, which the A/B harness reports as
    *unattributed* rather than pooling it into an arm. Nothing here changes the
    prompt strings - the column only makes a prompt edit attributable.
    """
    row = {
        "ticker": str(ticker or "").upper(),
        "date": date,
        "ts": time.time(),
        "rating": str(rating or ""),
        "direction": str(direction or ""),
        "entry": entry,
        "target": target,
        "stop": stop,
        "confidence": confidence,
        "horizon_days": int(horizon_days or 0),
        "data_quality": str(data_quality or "unknown"),
        "prompt_condition": str(prompt_condition) if prompt_condition else None,
    }
    # W1-5: when the caller supplies the close series the row also carries the
    # QUANT-ONLY baseline beside the LLM rating, so the ledger can be scored
    # quant-only vs quant+LLM vs LLM-only - the comparison the baseline module
    # exists for. Absent closes -> the keys are simply not written, never a
    # guessed 0.
    if closes:
        try:
            from tradingagents.strategies.quant_baseline import (
                baseline_rating,
                quant_signal,
            )

            sig = quant_signal(list(closes))
            row["quant_baseline"] = sig.get("score")
            row["quant_rating"] = baseline_rating(sig.get("score"))
        except Exception:  # noqa: BLE001 - baseline is advisory metadata
            row["quant_baseline"] = None
            row["quant_rating"] = None
    for k, v in (extra or {}).items():
        if k not in row:
            row[k] = v
    path = _ledger_path(results_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


def rows(results_dir: str | None = None) -> list[dict]:
    """Read all ledger rows (ticker-sorted by ts); never raises."""
    path = _ledger_path(results_dir)
    if not path.is_file():
        return []
    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        return []
    return sorted(out, key=lambda r: r.get("ts", 0.0))


def outcome_metrics(closes: list[float | None], entry: float | None,
                    stop: float | None = None, target: float | None = None,
                    direction: str = "long") -> dict:
    """MAE/MFE + stop/target hits over a realized close series (W1-3).

    Max Adverse / Favorable Excursion are the extreme % moves against/with
    the position after entry, computed from the supplied closes only.
    All None when there is no entry or no series.
    """
    vals = [c for c in (closes or []) if c is not None]
    if entry is None or entry <= 0 or not vals:
        return {"mae_pct": None, "mfe_pct": None, "stop_hit": False,
                "target_hit": False, "n_bars": 0}
    sign = 1.0 if str(direction).lower() in ("long", "buy") else -1.0
    mae = 0.0
    mfe = 0.0
    stop_hit = False
    target_hit = False
    for c in vals:
        move = sign * (c / entry - 1.0)
        mae = min(mae, move)
        mfe = max(mfe, move)
        if stop is not None and sign * (c - stop) <= 0:
            stop_hit = True
        if target is not None and sign * (c - target) >= 0:
            target_hit = True
    return {"mae_pct": mae * 100.0, "mfe_pct": mfe * 100.0,
            "stop_hit": bool(stop_hit), "target_hit": bool(target_hit),
            "n_bars": len(vals)}


def score_outcome(row: dict, closes: list[float | None]) -> dict:
    """Score ONE ledger row against realized closes (W1-1 outcome).

    Returns the row plus an ``outcome`` dict: return_pct (entry -> last
    close at/before horizon), hit (direction sign matches return),
    plus the excursion metrics. Honest Nones when unmeasurable.
    """
    entry = row.get("entry")
    closes = [c for c in (closes or []) if c is not None]
    horizon = row.get("horizon_days") or 60
    window = closes[:max(1, int(horizon))]
    ret_pct = None
    hit = None
    if entry and window:
        last = window[-1]
        if last:
            sign = 1.0 if str(row.get("direction") or "").lower() in ("long", "buy") else -1.0
            ret_pct = sign * (last / entry - 1.0) * 100.0
            hit = ret_pct > 0
    om = outcome_metrics(window, entry, row.get("stop"), row.get("target"),
                         row.get("direction") or "long")
    row = dict(row)
    row["outcome"] = {
        "return_pct": ret_pct,
        "hit": hit,
        "n_scored": len(window),
        **om,
    }
    return row


def score_all(closes_by_key: dict, results_dir: str | None = None,
             auto_invalidate: bool = False) -> list[dict]:
    """Score every ledger row using ``closes_by_key[(ticker, date)]``.

    ``auto_invalidate`` (W1-7): when a scored outcome hit the stop loss, an
    invalidation row is appended to the persistent invalidation ledger (and
    the scorecard feedback loop sees it) — a stopped-out thesis is recorded
    as retired, not silently forgotten.
    """
    from tradingagents.strategies.invalidation_ledger import append as _inv_append

    out = []
    for r in rows(results_dir):
        key = (r.get("ticker"), r.get("date"))
        closes = closes_by_key.get(key)
        if closes is None:
            r = dict(r)
            r["outcome"] = None
        else:
            r = score_outcome(r, closes)
            oc = r.get("outcome") or {}
            if auto_invalidate and oc.get("stop_hit") and r.get("stop") is not None:
                _inv_append(
                    r.get("ticker"),
                    [f"price_stop_loss: hit {r['stop']:g} (ledger outcome)"],
                    date=r.get("date"),
                    note="auto-invalidation from prediction outcome (W1-7)",
                    source="prediction_ledger",
                    results_dir=results_dir,
                )
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# FL-5 - the forecast ledger: the ONLY writer of ForecastEvaluation
# ---------------------------------------------------------------------------
# Same append-only JSONL discipline as the decision ledger above: rows are
# immutable once written, reads never mutate them, and IO never raises. One
# file holds both row kinds, tagged by ``kind``: ``"record"`` (the production
# ``ForecastRecord``) and ``"evaluation"`` (the post-hoc ``ForecastEvaluation``
# the ledger alone may append). The record is never rewritten by a later
# evaluation - that separation is the whole point of the contract's one-way
# gate (``forecast_contract.ForecastEvaluation._writer``).


def _forecast_ledger_path(results_dir: str | None) -> Path:
    base = results_dir or os.path.expanduser("~/.tradingagents/logs")
    return Path(base) / _FORECAST_LEDGER_NAME


def record_forecast(record: ForecastRecord, results_dir: str | None = None) -> dict:
    """Append one immutable ``ForecastRecord`` row; returns it (never raises on IO).

    Idempotent by ``record.forecast_id``: if a ``kind == "record"`` row already
    carries that id, the existing row is returned unchanged and nothing is
    appended. A write failure still returns the row (the in-memory record is
    the caller's), matching ``log_decision``.
    """
    if not isinstance(record, ForecastRecord):
        raise TypeError(
            f"record_forecast expects a ForecastRecord, got {type(record).__name__}"
        )
    for existing in forecast_rows(results_dir):
        if existing.get("kind") != "record":
            continue
        if (existing.get("record") or {}).get("forecast_id") == record.forecast_id:
            return existing
    row = {"kind": "record", "ts": time.time(), "record": asdict(record)}
    path = _forecast_ledger_path(results_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


def forecast_rows(results_dir: str | None = None) -> list[dict]:
    """Read every forecast-ledger row (ts-sorted); broken lines are skipped, never raises."""
    path = _forecast_ledger_path(results_dir)
    if not path.is_file():
        return []
    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    except OSError:
        return []
    return sorted(out, key=lambda r: r.get("ts", 0.0))


def evaluate_forecast(
    *,
    forecast_id: str,
    realized_outcome: float,
    evaluated_as_of: float,
    n_observations: int,
    scoring_rule: str,
    score: float,
    benchmark_ref: str,
    benchmark_score: float,
    results_dir: str | None = None,
    realized_coverage: float | None = None,
) -> dict:
    """Append the ONE ``ForecastEvaluation`` for ``forecast_id``; returns the row.

    This module is the only importer of the contract's ``_ledger_writer_token``,
    so this is the only place a ``ForecastEvaluation`` can be constructed: a
    producer has no write path to its own score (design doc §7.1/§8.1).

    Sign convention: ``benchmark_delta = benchmark_score - score``. All four
    ``SCORING_RULES`` (CRPS, QLIKE, RMSE, MAE) are **lower-is-better**, so a
    **POSITIVE delta means the forecast beat the benchmark**.

    An evaluation that keys to no recorded ``kind == "record"`` row is a
    defect, not a row, and raises ``ValueError`` naming the id. The ledger's
    terminal is dropped before serialisation: the stored row carries no writer
    object and no ``_writer`` key. IO never raises.
    """
    known = False
    for row in forecast_rows(results_dir):
        if row.get("kind") == "record" and (
            (row.get("record") or {}).get("forecast_id") == forecast_id
        ):
            known = True
            break
    if not known:
        raise ValueError(
            f"evaluate_forecast: no recorded ForecastRecord carries forecast_id "
            f"{forecast_id!r}; an evaluation that keys to nothing is a defect, not a row"
        )
    evaluation = ForecastEvaluation(
        forecast_id=forecast_id,
        realized_outcome=realized_outcome,
        evaluated_as_of=evaluated_as_of,
        n_observations=n_observations,
        scoring_rule=scoring_rule,
        score=score,
        benchmark_ref=benchmark_ref,
        benchmark_score=benchmark_score,
        benchmark_delta=benchmark_score - score,
        realized_coverage=realized_coverage,
        _writer=_ledger_writer_token(),
    )
    payload = asdict(evaluation)
    payload.pop("_writer", None)
    row = {"kind": "evaluation", "ts": time.time(), "evaluation": payload}
    path = _forecast_ledger_path(results_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


__all__ = ["log_decision", "rows", "outcome_metrics", "score_outcome",
           "score_all", "record_forecast", "forecast_rows", "evaluate_forecast",
           "_LEDGER_NAME"]
