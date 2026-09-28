"""LangGraph checkpoint support for resumable analysis runs.

Per-ticker SQLite databases so concurrent tickers don't contend.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from tradingagents.dataflows.utils import safe_ticker_component

logger = logging.getLogger(__name__)


def _db_path(data_dir: str | Path, ticker: str) -> Path:
    """Return the SQLite checkpoint DB path for a ticker."""
    # Reject ticker values that would escape the checkpoints directory.
    safe = safe_ticker_component(ticker).upper()
    p = Path(data_dir) / "checkpoints"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{safe}.db"


def thread_id(ticker: str, date: str, signature: str = "", run_id: str = "") -> str:
    """Deterministic thread ID for a ticker+date pair.

    ``signature`` folds in graph-shape-affecting run choices so a resume under a
    different graph can't reuse this checkpoint (#1089); omitting it keeps the
    legacy ID.

    ``run_id`` namespaces the thread to one run of that ticker+date+shape.
    Without it, two concurrent runs of the same ticker+date share one
    checkpoint thread and each clears rows the other is still writing.
    Omitting it keeps the pre-run-scoped ID.
    """
    base = f"{ticker.upper()}:{date}"
    if signature:
        base = f"{base}:{signature}"
    if run_id:
        base = f"{base}:run={run_id}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def _run_marker_path(data_dir: str | Path, ticker: str, date: str, signature: str = "") -> Path:
    """Sidecar file recording the active run id for a ticker+date+graph shape."""
    db = _db_path(data_dir, ticker)
    tag = hashlib.sha256(f"{date}:{signature}".encode()).hexdigest()[:12]
    return db.parent / f"{db.stem}.{tag}.run"


def _write_run_marker(marker: Path, run_id: str) -> None:
    """Best-effort atomic write of the run marker (never breaks a run)."""
    tmp = marker.parent / f"{marker.name}.{os.getpid()}.tmp"
    try:
        tmp.write_text(run_id, encoding="utf-8")
        tmp.replace(marker)
    except OSError:
        with suppress(OSError):
            marker.write_text(run_id, encoding="utf-8")


def _book_marker_path(marker: Path) -> Path:
    """Sidecar beside the run marker holding the run's book fingerprint."""
    return marker.with_name(marker.name + ".book")


def book_fingerprint(portfolio_context: Any) -> str:
    """Stable digest of a caller book, so a changed one cannot resume a stale run.

    ``""`` when no book was supplied - no context is NOT a flat book, and the
    empty string is distinct from the digest of a supplied-but-empty book
    (``{"positions": []}``). The digest is order-insensitive: positions are
    sorted, so two books differing only in position order hash the same, while
    any change to cash, currency, or a position's quantity/weight/price
    changes it. Twelve hex chars, matching the run-id convention.
    """
    if not portfolio_context:
        return ""
    ctx = portfolio_context if isinstance(portfolio_context, dict) else {}
    positions = []
    for p in ctx.get("positions") or []:
        if not isinstance(p, dict):
            continue
        positions.append(
            {
                "ticker": str(p.get("ticker", "")).strip().upper(),
                "quantity": p.get("quantity"),
                "weight": p.get("weight"),
                "average_price": p.get("average_price"),
            }
        )
    positions.sort(key=lambda p: p["ticker"])
    canonical = json.dumps(
        {"cash": ctx.get("cash"), "currency": ctx.get("currency"), "positions": positions},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _read_book_fingerprint(marker: Path) -> str | None:
    """Recorded book fingerprint for a run, or None when none was recorded.

    None (legacy marker with no sidecar) is deliberately distinct from ``""``
    (a run that recorded "no book"), so a pre-fingerprint checkpoint is never
    mistaken for a changed book.
    """
    sidecar = _book_marker_path(marker)
    try:
        if sidecar.exists():
            return sidecar.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return None


def _write_book_fingerprint(marker: Path, fingerprint: str) -> None:
    """Best-effort write of the run's book fingerprint (never breaks a run)."""
    sidecar = _book_marker_path(marker)
    with suppress(OSError):
        sidecar.write_text(fingerprint, encoding="utf-8")


def resume_book_conflict(
    data_dir: str | Path,
    ticker: str,
    date: str,
    signature: str = "",
    portfolio_context: Any = None,
) -> str | None:
    """Why a resume against the current book must not proceed, or None.

    A checkpoint whose run started against a DIFFERENT book must not silently
    continue: this returns a human-readable message when the book digest
    recorded with the run marker differs from the currently supplied book's
    digest. An identical book, or a legacy run with no digest recorded,
    returns None.
    """
    marker = _run_marker_path(data_dir, ticker, date, signature)
    recorded = _read_book_fingerprint(marker)
    if recorded is None:
        return None
    current = book_fingerprint(portfolio_context)
    if recorded == current:
        return None
    return (
        "checkpoint book fingerprint mismatch: the run was started with book "
        f"{recorded or 'none'}, but the current book is {current or 'none'}. "
        "Refusing to resume a stale run against a different book - starting a "
        "fresh run instead."
    )


def resolve_run_id(
    data_dir: str | Path,
    ticker: str,
    date: str,
    signature: str = "",
    run_id: str = "",
    portfolio_context: Any = None,
) -> str:
    """Run id to checkpoint under for this run.

    An explicit ``run_id`` wins (callers that manage resume themselves).
    Otherwise an unfinished run for the same ticker+date+graph shape is
    resumed by reusing its recorded id; with nothing to resume, a fresh id is
    minted and recorded. Ids never come from the wall clock, so tests can pin
    them.

    ``portfolio_context`` is the caller's book. Its digest is recorded with the
    run marker, and a resume whose book digest differs from the recorded one
    does NOT silently continue: a fresh run id is minted (so the stale
    checkpoint is not resumed) and the mismatch is surfaced via the logger and
    :func:`resume_book_conflict`.
    """
    if run_id:
        return run_id
    marker = _run_marker_path(data_dir, ticker, date, signature)
    existing: str | None = None
    try:
        if marker.exists():
            existing = marker.read_text(encoding="utf-8").strip() or None
    except OSError:
        existing = None
    if existing and checkpoint_step(data_dir, ticker, date, signature, existing) is not None:
        conflict = resume_book_conflict(data_dir, ticker, date, signature, portfolio_context)
        if conflict is None:
            return existing
        logger.warning(conflict)
    new_id = uuid.uuid4().hex[:12]
    _write_run_marker(marker, new_id)
    _write_book_fingerprint(marker, book_fingerprint(portfolio_context))
    return new_id


def forget_run(
    data_dir: str | Path, ticker: str, date: str, signature: str = "", run_id: str = ""
) -> None:
    """Drop the run marker after a completed run (its checkpoint is cleared)."""
    marker = _run_marker_path(data_dir, ticker, date, signature)
    sidecar = _book_marker_path(marker)
    try:
        if not marker.exists():
            # A completed run may leave its fingerprint sidecar behind.
            if sidecar.exists():
                sidecar.unlink()
            return
        recorded = marker.read_text(encoding="utf-8").strip()
        if not run_id or recorded == run_id:
            marker.unlink()
            with suppress(OSError):
                sidecar.unlink()
    except OSError:
        pass


@contextmanager
def get_checkpointer(data_dir: str | Path, ticker: str) -> Generator[SqliteSaver, None, None]:
    """Context manager yielding a SqliteSaver backed by a per-ticker DB."""
    db = _db_path(data_dir, ticker)
    conn = sqlite3.connect(str(db), check_same_thread=False)
    try:
        saver = SqliteSaver(conn)
        saver.setup()
        yield saver
    finally:
        conn.close()


def has_checkpoint(
    data_dir: str | Path, ticker: str, date: str, signature: str = "", run_id: str = ""
) -> bool:
    """Check whether a resumable checkpoint exists for ticker+date (and run)."""
    return checkpoint_step(data_dir, ticker, date, signature, run_id) is not None


def checkpoint_step(
    data_dir: str | Path, ticker: str, date: str, signature: str = "", run_id: str = ""
) -> int | None:
    """Return the step number of the latest checkpoint, or None if none exists."""
    db = _db_path(data_dir, ticker)
    if not db.exists():
        return None
    tid = thread_id(ticker, date, signature, run_id)
    with get_checkpointer(data_dir, ticker) as saver:
        config = {"configurable": {"thread_id": tid}}
        cp = saver.get_tuple(config)
        if cp is None:
            return None
        return cp.metadata.get("step")


def clear_all_checkpoints(data_dir: str | Path) -> int:
    """Remove all checkpoint DBs and run markers. Returns number of DBs deleted.

    The SQLite ``-wal``/``-shm`` sidecars are removed with each DB. In WAL mode
    committed pages live in the ``-wal`` until a checkpoint folds them into the
    main file, so deleting only the ``.db`` can leave a "cleared" checkpoint
    whose state is still recoverable from the sidecar.
    """
    cp_dir = Path(data_dir) / "checkpoints"
    if not cp_dir.exists():
        return 0
    dbs = list(cp_dir.glob("*.db"))
    for db in dbs:
        db.unlink()
        for sidecar in (db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
            if sidecar.exists():
                with suppress(OSError):
                    sidecar.unlink()
    for marker in cp_dir.glob("*.run*"):
        with suppress(OSError):
            marker.unlink()
    return len(dbs)


def clear_checkpoint(
    data_dir: str | Path, ticker: str, date: str, signature: str = "", run_id: str = ""
) -> None:
    """Remove checkpoint for a specific ticker+date by deleting the thread's rows.

    ``run_id`` scopes the delete to the caller's own run thread so a concurrent
    run of the same ticker+date never has its rows deleted from under it.
    Omitting it keeps the pre-run-scoped (shared) thread.

    Prefers ``SqliteSaver.delete_thread`` — the saver owns its schema, and the
    table layout changed across langgraph-checkpoint-sqlite versions (older
    builds used ``checkpoint_writes``/``checkpoint_blobs``/``checkpoints``,
    newer builds use ``checkpoints`` + ``writes``). The saver's method deletes
    both checkpoint rows and pending writes for the thread atomically.

    Falls back to a runtime-discovered per-table delete for builds without
    ``delete_thread``. Each table is handled independently so a missing table
    on one build never aborts the remaining deletes (the old code wrapped the
    whole loop in one try/except, so the first missing table silently skipped
    the ``checkpoints`` delete and the commit entirely — stale checkpoints
    were never actually cleared).
    """
    db = _db_path(data_dir, ticker)
    if not db.exists():
        return
    tid = thread_id(ticker, date, signature, run_id)
    with get_checkpointer(data_dir, ticker) as saver:
        delete_thread = getattr(saver, "delete_thread", None)
        if delete_thread is not None:
            delete_thread(tid)
            return

        # Legacy fallback for old langgraph-checkpoint-sqlite builds without
        # delete_thread: discover the tables actually present in this DB and
        # delete from each candidate independently.
        conn = saver.conn
        try:
            tables = {
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints", "writes"):
                if table not in tables:
                    continue
                try:
                    conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (tid,))
                except sqlite3.OperationalError as exc:
                    if "no such table" not in str(exc).lower():
                        raise
            conn.commit()
        finally:
            conn.close()
