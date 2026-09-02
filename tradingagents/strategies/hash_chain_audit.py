"""Hash-chained, tamper-evident JSONL audit ledger (Vibe-Trading audit_chain).

An append-only JSONL where every row carries the SHA-256 of the previous
row's canonical bytes — so a later row latches the entire prior history.
Tamper evidence: chain ``verify()`` recomputes each row's hash from the
previous row and reports the FIRST mismatching index (a single edited row
breaks every subsequent link).

- ``append`` writes one row to the ledger (prev_hash = hash of the raw
  previous line, so even the raw text bytes are pinned, not just the parsed
  JSON).
- ``verify`` walks the file and returns (ok, first_bad_index) — advisory
  integrity check; a corrupt tail is a mismatch, not a crash.
- Reads never raise; writes are atomic (temp + replace).

The risk trail uses this in place of a plain JSONL so an appended entry
cannot be silently edited without breaking the chain.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _line_hash(line: bytes) -> str:
    return hashlib.sha256(line).hexdigest()


def append(path: str | os.PathLike, record: dict) -> dict:
    """Append one record chained to the previous raw line; returns the row."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    prev_hash = ""
    if p.is_file():
        try:
            lines = p.read_bytes().splitlines()
            if lines:
                prev_hash = _line_hash(lines[-1])
        except OSError:
            prev_hash = ""
    row = dict(record)
    row["prev_hash"] = prev_hash
    line = json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
    with open(p, "ab") as fh:
        fh.write(line + b"\n")
    return row


def verify(path: str | os.PathLike) -> tuple[bool, int]:
    """Recompute the chain; returns (ok, first_bad_index) (index -1 when ok)."""
    p = Path(path)
    if not p.is_file():
        return True, -1
    try:
        lines = p.read_bytes().splitlines()
    except OSError:
        return False, 0
    prev = ""
    for i, line in enumerate(lines):
        try:
            row = json.loads(line)
        except ValueError:
            return False, i
        if row.get("prev_hash") != prev:
            return False, i
        prev = _line_hash(line)
    return True, -1


__all__ = ["append", "verify", "_line_hash"]
