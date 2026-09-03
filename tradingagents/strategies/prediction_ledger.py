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
from pathlib import Path

_LEDGER_NAME = "predictions.jsonl"


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
    **extra,
) -> dict:
    """Append one immutable prediction row; returns it (never raises on IO)."""
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
    }
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


def score_all(closes_by_key: dict, results_dir: str | None = None) -> list[dict]:
    """Score every ledger row using ``closes_by_key[(ticker, date)]``."""
    out = []
    for r in rows(results_dir):
        key = (r.get("ticker"), r.get("date"))
        closes = closes_by_key.get(key)
        if closes is None:
            r = dict(r)
            r["outcome"] = None
        else:
            r = score_outcome(r, closes)
        out.append(r)
    return out


__all__ = ["log_decision", "rows", "outcome_metrics", "score_outcome",
           "score_all", "_LEDGER_NAME"]
