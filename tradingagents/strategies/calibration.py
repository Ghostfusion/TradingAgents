"""G2 - confidence calibration from realized outcomes.

Buckets declared confidence into empirical win-rates and returns a
calibrated probability (identity when a bucket has too few samples). The PM
prompt consumes ``calibration_table_text`` so the LLM sees its own track
record; sizing (G1) uses ``calibrated_confidence``.
"""

from __future__ import annotations

#: (low, high) confidence buckets; high bound exclusive.
BUCKETS = ((0.00, 0.50), (0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 1.01))


def _bucket_of(p: float) -> "tuple | None":
    for lo, hi in BUCKETS:
        if lo <= p < hi:
            return (lo, hi)
    return None


def fit_buckets(entries: list) -> dict:
    """Bucket decision outcomes into empirical win-rates.

    Entry shape: {"confidence": float, "won": bool} (won = delta_r > 0).
    Returns {bucket: {"n": int, "win_rate": float|None}}.
    """
    table = {b: {"n": 0, "won": 0, "win_rate": None} for b in BUCKETS}
    for e in entries:
        p = e.get("confidence")
        if p is None:
            continue
        b = _bucket_of(float(p))
        if b is None:
            continue
        table[b]["n"] += 1
        if e.get("won"):
            table[b]["won"] += 1
    for cell in table.values():
        if cell["n"]:
            cell["win_rate"] = cell["won"] / cell["n"]
    return table


def calibrated_confidence(p: float, table: dict, min_n: int = 5) -> float:
    """Empirical win-rate of p's bucket; identity fallback below min samples."""
    b = _bucket_of(float(p))
    if b is None:
        return float(p)
    cell = table.get(b)
    if cell is None or cell["n"] < min_n or cell["win_rate"] is None:
        return float(p)
    # Never fully trust scarcity: shrink toward identity with sample size.
    trust = min(1.0, cell["n"] / (2 * min_n))
    return float(p + trust * (cell["win_rate"] - p))


def calibration_table_text(table: dict) -> str:
    """Human-readable calibration summary for the PM prompt."""
    lines = ["confidence calibration (from strategy ledger):"]
    for b in BUCKETS:
        cell = table.get(b)
        if not cell or cell["n"] == 0:
            continue
        wr = f"{cell['win_rate']:.0%}" if cell["win_rate"] is not None else "n/a"
        lo, hi = b
        lines.append(f"  declared {lo:.2f}-{hi:.2f}: n={cell['n']} won={cell['won']} realized={wr}")
    return "\n".join(lines) if len(lines) > 1 else "no calibration history yet"


def record_calibration_entry(ledger_path, analyst: str, ticker: str,
                             trade_date: str, confidence: float,
                             won: bool) -> None:
    """Append a confidence-tagged outcome; separate file to keep the ledger clean."""
    import json
    import time
    from pathlib import Path

    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "analyst": analyst, "ticker": ticker, "trade_date": trade_date,
        "confidence": float(confidence), "won": bool(won), "ts": time.time(),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


__all__ = [
    "BUCKETS", "fit_buckets", "calibrated_confidence",
    "calibration_table_text", "record_calibration_entry",
]