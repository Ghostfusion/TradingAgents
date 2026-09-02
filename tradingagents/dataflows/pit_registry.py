"""Point-in-time (PIT) snapshot registry (Qlib PIT pillar 1b port).

Append-only per-symbol JSONL store keyed by ``(symbol, as_of)`` so any later
re-analysis (reports, backtests, the factor loop, the fast path) reads the
SAME point-in-time view the original run used. Every read surfaces the
as-of; ``read_as_of`` masks anything dated after the as-of (reuses
``dataflows.date_window`` UTC semantics). Also hosts:

- ``put_moments`` / ``get_moments`` — the learn/infer fitted normalization
  stats (mean/std/winsorize bounds) stored per snapshot so a later run
  reuses the same train-fitted moments (Qlib ``DataHandlerLP`` split).
- ``markup_label`` — the Alpha158/360 label convention:
  ``Ref($close,-2)/Ref($close,-1) - 1``, the next-execution-day return with a
  one-day buffer (features at t, label = return realized AFTER the close the
  signal could trade at). The registry records the label + its as-of day so
  backtests and the factor loop never align a signal with a same-day return.

No-fabrication: ``None`` under as-of masking or missing data; raw payloads
stored by reference (never re-derived).
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

_LOCK = threading.Lock()


def _default_dir() -> str:
    try:
        from tradingagents.dataflows.config import get_config

        cache = get_config().get("data_cache_dir")
        if cache:
            return os.path.join(str(cache), "pit_registry")
    except Exception:  # noqa: BLE001 - degraded config -> home fallback
        pass
    return os.path.join(os.path.expanduser("~/.tradingagents"), "cache", "pit_registry")


def _path(symbol: str, root: str | None = None) -> str:
    r = root or _default_dir()
    return os.path.join(r, f"{str(symbol).upper()}.jsonl")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def store_snapshot(symbol: str, as_of: str, payload: dict, root: str | None = None) -> str | None:
    """Append one PIT snapshot ``{symbol, as_of, stored_at, payload}``.

    Returns the row's ``stored_at`` timestamp or None on failure. Thread-safe
    single-line append (O_APPEND semantics via ``a`` mode). ``as_of`` is the
    decision/fundamental date the payload was true on.
    """
    try:
        path = _path(symbol, root)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        stored_at = _iso_now()
        row = {"symbol": str(symbol).upper(), "as_of": str(as_of),
               "stored_at": stored_at, "payload": payload}
        with _LOCK, open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return stored_at
    except Exception:  # noqa: BLE001 - persistence degrades, never raises
        return None


def read_snapshot(symbol: str, as_of: str | None = None, root: str | None = None) -> dict | None:
    """Most recent snapshot for a symbol; ``as_of`` selects the newest row
    with ``as_of <= requested`` (exact-match when omitted returns the last)."""
    rows = _read_all(symbol, root)
    if not rows:
        return None
    if as_of is None:
        return rows[-1]
    selected = [r for r in rows if str(r["as_of"]) <= str(as_of)]
    return selected[-1] if selected else None


def read_as_of(symbol: str, as_of: str, root: str | None = None) -> dict | None:
    """Strict point-in-time read: the newest row with ``as_of <= requested``.

    A record dated AFTER the requested as-of is NEVER visible (the masking
    rule; the acceptance test in design §8-5). Returns the payload dict or
    None.
    """
    snap = read_snapshot(symbol, as_of, root)
    return snap["payload"] if snap else None


def read_all(symbol: str, as_of: str | None = None, root: str | None = None) -> list[dict]:
    """All snapshots for a symbol, oldest-first; ``as_of`` masks later rows."""
    rows = _read_all(symbol, root)
    if as_of is not None:
        rows = [r for r in rows if str(r["as_of"]) <= str(as_of)]
    return rows


def _read_all(symbol: str, root: str | None) -> list[dict]:
    path = _path(symbol, root)
    if not os.path.exists(path):
        return []
    out: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # a partial line degrades, never blocks
    except OSError:
        return []
    return out


def put_moments(symbol: str, as_of: str, moments: dict, root: str | None = None) -> str | None:
    """Store learn/infer fitted moments per snapshot (train-only stats)."""
    return store_snapshot(symbol, as_of, {"kind": "moments", **moments}, root)


def get_moments(symbol: str, as_of: str | None = None, root: str | None = None) -> dict | None:
    """Latest ``moments`` payload for a symbol (masked by as-of when given)."""
    snap = read_snapshot(symbol, as_of, root)
    if snap is None:
        return None
    payload = snap.get("payload") or {}
    return payload if payload.get("kind") == "moments" else None


def markup_label(closes: list) -> float | None:
    """Alpha158/360 label convention: ``Ref($close,-2)/Ref($close,-1) - 1``.

    The next-execution-day return with a one-day buffer: the return realized
    AFTER the close the signal could trade at. Requires >= 3 closes; None
    when the reference close is unusable (no fabrication).
    """
    if not closes or len(closes) < 3:
        return None
    try:
        c1 = float(closes[-2])
        c2 = float(closes[-1])
    except (TypeError, ValueError):
        return None
    if c1 <= 0 or c2 <= 0:
        return None
    return c2 / c1 - 1.0


__all__ = [
    "store_snapshot",
    "read_snapshot",
    "read_as_of",
    "read_all",
    "put_moments",
    "get_moments",
    "markup_label",
]
