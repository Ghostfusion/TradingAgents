"""Point-in-time (PIT) snapshot registry (Qlib PIT pillar 1b port).

Append-only per-symbol JSONL store keyed by ``(symbol, as_of)`` so any later
re-analysis (reports, backtests, the factor loop, the fast path) reads the
SAME point-in-time view the original run used. Every read surfaces the
as-of; ``read_as_of`` masks anything dated after the as-of (reuses
``dataflows.date_window`` UTC semantics). Also hosts:

- ``put_moments`` / ``get_moments`` — the learn/infer fitted normalization
  stats (mean/std/winsorize bounds) stored per snapshot so a later run
  reuses the same train-fitted moments (Qlib ``DataHandlerLP`` split).
- ``universe_exit_marks`` — the exit return for the names that had LEFT the
  universe by an as-of date, read off the same registry row
  (``delisting_return`` / ``dlret``). ``universe_membership`` says *that* a name
  delisted; a bar series cannot show what the exit was (cash, M&A, zero), so a
  panel that ends the series at the last observed price silently marks a
  wiped-out name as flat. An UNKNOWN exit is absent, never ``0.0``.
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


def universe_membership(symbols: list[str], as_of: str,
                        registry: dict | None = None) -> dict:
    """W2-10 survivorship guard: which of ``symbols`` were alive as-of a date.

    ``registry`` maps symbol -> {first_active, last_active} (or any snapshot
    dict with those keys). A symbol is "in universe" at ``as_of`` when
    first_active <= as_of <= last_active (or last_active missing = still
    listed). Unmeasured symbols return "unknown" (never assumed present).
    """
    out: dict[str, str] = {}
    for sym in (symbols or []):
        r = (registry or {}).get(sym)
        sym = str(sym).upper()
        if not r:
            out[sym] = "unknown"
            continue
        first = str(r.get("first_active") or "")
        last = str(r.get("last_active") or "")
        if first and as_of < first:
            out[sym] = "not_yet_listed"
        elif last and as_of > last:
            out[sym] = "delisted"
        else:
            out[sym] = "listed"
    return out


#: The registry-row keys an exit return may be declared under, in precedence
#: order. ``dlret`` is the CRSP/Alpha158 spelling; ``delisting_return`` the long
#: form.
_EXIT_RETURN_KEYS = ("delisting_return", "dlret")


def _delisting_return(row: dict | None) -> float | None:
    """The declared return to apply at a name's exit, or ``None``.

    A delisted name's panel return is not the last observed price back to
    itself: the exit is cash, an M&A consideration or zero, and it is a return
    the bar series cannot show. Reads the first numeric value under
    :data:`_EXIT_RETURN_KEYS` (a numeric string parses). ``None`` when the row
    declares none - an UNKNOWN exit is never read as ``0.0``, which would mark a
    wiped-out name as flat.
    """
    for key in _EXIT_RETURN_KEYS:
        raw = (row or {}).get(key)
        if raw is None or raw == "":
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def membership_registry(symbols: list[str], as_of: str | None = None,
                        root: str | None = None) -> dict[str, dict]:
    """Assemble a ``universe_membership`` registry from the STORED rows.

    A membership row is a payload stored under ``kind: "membership"`` carrying
    ``first_active`` / ``last_active`` and, when known, the exit return
    (``delisting_return`` / ``dlret``) - the shape :func:`universe_membership`
    and :func:`universe_exit_marks` read. This is the READER that lets those two
    work off the PIT store instead of only off a caller-built dict; the writer is
    the existing :func:`store_snapshot`, so any vendor's delisted-symbol list
    lands here without a second store.

    The read is masked: with an ``as_of``, only rows visible at that date are
    considered (:func:`read_all`'s rule), so a later correction cannot rewrite
    the past. A symbol with no stored membership row is ABSENT - the status read
    then reports ``"unknown"``, exactly as it did before.
    """
    out: dict[str, dict] = {}
    for sym in symbols or []:
        key = str(sym).upper()
        for row in reversed(read_all(key, as_of, root)):
            payload = row.get("payload") or {}
            if payload.get("kind") == "membership":
                out[key] = payload
                break
    return out


def universe_exit_marks(symbols: list[str], as_of: str,
                        registry: dict | None = None) -> dict[str, float]:
    """The declared exit return for each of ``symbols`` delisted by ``as_of``.

    ``universe_membership`` answers *that* a name left the universe;
    :func:`_delisting_return` answers what the exit was worth. This joins the
    two: ``{SYMBOL: return}`` for the delisted names only, from the same registry
    row :func:`universe_membership` reads its ``first_active``/``last_active``
    from. A name that is listed, not yet listed or unmeasured is ABSENT, never
    ``0.0`` - the absent key is the "unknown exit" signal a panel must handle.

    The registry field is where a delisted-symbol feed lands. Whether to buy that
    feed (EODHD's ``exchange-symbol-list/{EX}?delisted=1``) is the owner's open
    decision, so this is the arithmetic and the seam, not the fetch.
    """
    status = universe_membership(symbols, as_of, registry)
    rows = {str(k).upper(): v for k, v in (registry or {}).items()}
    out: dict[str, float] = {}
    for sym in symbols or []:
        key = str(sym).upper()
        if status.get(key) != "delisted":
            continue
        value = _delisting_return(rows.get(key))
        if value is not None:
            out[key] = value
    return out


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
    "membership_registry",
    "universe_exit_marks",
]
