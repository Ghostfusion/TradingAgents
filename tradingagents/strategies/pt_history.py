"""A persisted price-target consensus series, and the revision it implies.

NEWS-6. Every analyst-ratings vendor returns a **current** consensus only - the
documented position of ``finnhub.py:148-166``, ``y_finance.py:912-922`` and
``moomoo.py:1355`` - so a price-target *revision* is not observable from any
single call. It becomes observable only by accumulating snapshots over time.

This is the store and the forward-accumulation policy. It is written by the
tool/orchestration layer, never by a vendor: the existing ``score_history``
store is written from ``graph/trading_graph.py:749``, and this follows that
split so a dataflow call stays free of side effects. It is purely advisory - a
store failure returns ``None`` and never breaks a run.

The revision MATHS over a supplied history already exists in
``strategies/analyst_revisions.py``; what was missing was a history to supply.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = [
    "pt_history_path",
    "pt_revision",
    "read_pt_history",
    "record_pt_snapshot",
]

#: The consensus fields a row carries. A row is only written when a target
#: level exists, so a store never fills with empty observations.
_FIELDS = ("mean", "median", "high", "low", "current", "count", "source")


def _cache_dir(data_cache_dir: Any = None) -> Path:
    """Where the history lives: the caller's cache dir, else the ambient one."""
    if data_cache_dir:
        return Path(str(data_cache_dir))
    try:
        from tradingagents.dataflows.config import get_config

        return Path(str((get_config() or {}).get("data_cache_dir") or "."))
    except Exception:  # noqa: BLE001 - a missing config is not a crash
        return Path(".")


def pt_history_path(ticker: str, data_cache_dir: Any = None) -> Path:
    """The store's path for one ticker. One file per ticker, one row per date."""
    name = str(ticker).strip().upper()
    return _cache_dir(data_cache_dir) / "pt_history" / f"{name}.jsonl"


def read_pt_history(ticker: str, data_cache_dir: Any = None) -> list[dict]:
    """Every recorded row for a ticker, oldest first. A corrupt line is skipped."""
    path = pt_history_path(ticker, data_cache_dir)
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:  # noqa: BLE001 - one bad line must not lose the history
            continue
        if isinstance(row, dict) and row.get("date"):
            rows.append(row)
    rows.sort(key=lambda r: str(r.get("date")))
    return rows


def record_pt_snapshot(
    ticker: str,
    snapshot: dict | None,
    trade_date: str | None = None,
    data_cache_dir: Any = None,
) -> dict | None:
    """Append this observation, unless the date already has one.

    One row per date: re-running the same day does not rewrite history, so an
    observation is never silently replaced by a later one - the accumulation
    policy that makes a revision mean something. Returns the row written, or
    ``None`` when there is nothing to record.
    """
    snap = snapshot or {}
    if snap.get("mean") is None and snap.get("median") is None:
        return None
    date = str(trade_date)[:10] if trade_date else datetime.now().strftime("%Y-%m-%d")
    if not date:
        return None
    if date in {str(r.get("date")) for r in read_pt_history(ticker, data_cache_dir)}:
        return None
    row: dict = {"date": date}
    for field in _FIELDS:
        row[field] = snap.get(field)
    path = pt_history_path(ticker, data_cache_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:  # noqa: BLE001 - an advisory store must not break a run
        return None
    return row


def pt_revision(ticker: str, data_cache_dir: Any = None) -> dict:
    """The revision the accumulated series implies, with its basis.

    ``revision`` is the step from the previous observation to the latest and is
    ``None`` **with a reason** until two observations with a mean target exist -
    a single snapshot is not a revision, and this never fabricates one from a
    vendor's ``prior`` field.
    """
    rows = [r for r in read_pt_history(ticker, data_cache_dir) if r.get("mean") is not None]
    out: dict = {
        "revision": None,
        "revision_pct": None,
        "revision_since_first": None,
        "direction": None,
        "observations": len(rows),
        "span": None,
        "latest_date": None,
        "prior_date": None,
        "latest_mean": None,
        "source": None,
        "reason": None,
    }
    if rows:
        out["latest_mean"] = rows[-1].get("mean")
        out["source"] = rows[-1].get("source")
    if len(rows) < 2:
        out["reason"] = (
            f"{len(rows)} observation(s) with a mean target; two are needed "
            f"before a revision exists"
        )
        return out
    first, prior, latest = rows[0], rows[-2], rows[-1]
    out["span"] = (first["date"], latest["date"])
    out["latest_date"] = latest["date"]
    out["prior_date"] = prior["date"]
    base = float(prior["mean"])
    delta = float(latest["mean"]) - base
    out["revision"] = round(delta, 4)
    out["revision_pct"] = round(100.0 * delta / base, 4) if base else None
    out["direction"] = "up" if delta > 0 else "down" if delta < 0 else "flat"
    out["revision_since_first"] = round(float(latest["mean"]) - float(first["mean"]), 4)
    return out
