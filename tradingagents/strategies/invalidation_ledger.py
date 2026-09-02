"""Persistent decision-invalidation ledger (Vibe-Trading Hypothesis Registry).

The DSA phase-D rule (``report_disclosure.invalidation_conditions``) says
every decision carries >= 1 invalidation (stop-loss breach, take-profit
review, data staleness, else manual). This module makes those invalidations
PERSISTENT and auditable instead of discarded at render time:

- ``append`` records a decision's computed invalidation conditions + an
  optional annotation (source, note) as one JSONL row under
  ``<results_dir>/invalidations.jsonl``.
- ``invalidate`` flips a decision row's status to ``rejected`` with a note,
  PRESERVING prior invalidation notes (Vibe's invalidate semantics) — the
  ledger never loses history, it annotates it.
- ``rows`` reads rows back (ticker-filtered), newest first.

The ledger is advisory + append-only-safe: every write is one JSON line, a
corrupt tail is skipped on read, and reads never raise. Nothing here gates a
decision — it records what invalidates a thesis so the next review can see
why a stopped-out/target-hit/data-degraded call was retired.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

_LEDGER_NAME = "invalidations.jsonl"


def _ledger_path(results_dir: str | None) -> Path:
    base = results_dir or os.path.expanduser("~/.tradingagents/logs")
    return Path(base) / _LEDGER_NAME


def append(ticker: str, conditions: list[str], date: str = "",
           note: str = "", source: str = "manual", results_dir: str | None = None) -> dict:
    """Append one invalidation row; returns the row. Never raises on IO."""
    row = {
        "ticker": str(ticker or "").upper(),
        "date": date,
        "ts": time.time(),
        "status": "open",  # open -> rejected (via invalidate) | auto
        "conditions": [str(c) for c in (conditions or [])],
        "note": str(note or ""),
        "source": str(source or "manual"),
    }
    path = _ledger_path(results_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass  # advisory: never raise on a disk hiccup
    return row


def invalidate(ticker: str, date: str, note: str = "",
               results_dir: str | None = None) -> list[dict]:
    """Mark open rows for (ticker, date) as rejected, preserving prior notes.
    Returns the updated rows. No-op when no open row matches (never assumes)."""
    path = _ledger_path(results_dir)
    if not path.is_file():
        return []
    all_rows = []
    updated = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue  # corrupt tail: skip
        if (r.get("ticker") == str(ticker or "").upper() and r.get("date") == date
                and r.get("status") == "open"):
            r["status"] = "rejected"
            r["invalidated_at"] = time.time()
            prev = r.get("note") or ""
            r["note"] = (prev + " | " + note).strip(" |") if note else prev
            updated.append(r)
        all_rows.append(r)
    if not updated:
        return []  # nothing matched: leave the file untouched (never assumes)
    try:
        path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows),
            encoding="utf-8",
        )
    except OSError:
        return []
    return updated


def rows(ticker: str | None = None, results_dir: str | None = None) -> list[dict]:
    """Read ledger rows (ticker-filtered when given), newest first. Never raises."""
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
    if ticker:
        out = [r for r in out if r.get("ticker") == str(ticker).upper()]
    return sorted(out, key=lambda r: r.get("ts", 0.0), reverse=True)


__all__ = ["append", "invalidate", "rows", "_LEDGER_NAME"]
