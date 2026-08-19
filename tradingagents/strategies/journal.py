"""Momentum trade journal + win/loss analytics (phase 5 of the playbook).

A JSON-lines ledger, one row per (simulated) momentum trade. Rows record the
five pillars, the first-pullback flags, order-level numbers (stop / R:R),
session walk-away flags, and a later-applied exit class ("win"/"loss" or
"signal" for a rules-based exit). ``momentum_stats`` turns the ledger into
the win vs loss / discipline analytics the playbook step 5 asks for.

Design notes:
- Analysis-only: the ledger is a paper journal, never an execution record.
- Deterministic & offline: pure functions over the ledger file.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def _load(path: str) -> list:
    p = Path(path)
    rows = []
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def record_momentum_trade(path: str, ticker: str, date: str | None = None, *,
                          pillars: dict | None = None,
                          pullback: dict | None = None,
                          session: dict | None = None,
                          price: float | None = None,
                          exit_class: str | None = None,
                          fomo: bool = False,
                          note: str | None = None) -> dict:
    """Append one momentum trade row to the JSONL journal and return it.

    ``exit_class``: None (open), "win", "loss" (hard stop / R-based), or
    "signal" (walk-away / rules-based exit). ``fomo`` marks the classic
    post-window chase the playbook flags as the #1 mistake.
    """
    from datetime import date as _date

    row = {
        "ts": time.time(),
        "ticker": str(ticker).upper(),
        "date": date or _date.today().isoformat(),
        "price": price,
        "pillars": {k: (v is True) for k, v in (pillars or {}).items()
                    if v is not None},
        "pullback": {
            "candidate": bool((pullback or {}).get("candidate")),
            "rr": (pullback or {}).get("rr"),
            "stop": (pullback or {}).get("stop"),
        },
        "session": {
            k: v for k, v in (session or {}).items() if v is not None
        },
        "exit_class": exit_class,
        "fomo": bool(fomo),
        "note": note,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


def momentum_stats(path: str) -> dict:
    """Win/loss + discipline summary over the journal at ``path``."""
    rows = _load(path)
    total = len(rows)
    candidates = sum(1 for r in rows if r.get("pullback", {}).get("candidate"))
    # Pillar pass rates across rows that actually measured the pillar.
    passes: dict = {}
    for key in ("rvol", "high_volume", "gap", "price_band", "float"):
        measured = [r for r in rows if key in (r.get("pillars") or {})]
        passes[key] = (sum(1 for r in measured
                           if r.get("pillars", {}).get(key)) / len(measured)
                       if measured else None)
    wins = sum(1 for r in rows if r.get("exit_class") == "win")
    losses = sum(1 for r in rows if r.get("exit_class") == "loss")
    resolved = wins + losses
    rr_values = [r["pullback"]["rr"] for r in rows
                 if (r.get("pullback") or {}).get("rr") is not None]
    session_keys = ("giveback_50", "max_daily_loss_hit",
                    "past_optimal_window", "no_quality_setups")
    session_hits = {k: sum(1 for r in rows
                           if (r.get("session") or {}).get(k) is True)
                    for k in session_keys}
    return {
        "trades": total,
        "candidates": candidates,
        "pillar_pass_rate": {k: (round(v, 3) if v is not None else None)
                             for k, v in passes.items()},
        "win_rate": (wins / resolved) if resolved else None,
        "wins": wins,
        "losses": losses,
        "avg_rr": (round(sum(rr_values) / len(rr_values), 2) if rr_values
                   else None),
        "session_flag_hits": session_hits,
        "fomo_count": sum(1 for r in rows if r.get("fomo")),
        "path": str(Path(path).resolve()),
    }


def format_summary(stats: dict) -> str:
    """Human-readable one-block summary of ``momentum_stats`` output."""
    lines = [
        f"momentum journal: {stats['path']}",
        f"  trades={(stats['trades'])} candidates={stats['candidates']}",
        f"  resolved={stats['wins'] + stats['losses']} "
        f"win_rate={(stats['win_rate'] * 100 if stats['win_rate'] is not None else 'n/a')}",
        f"  avg_rr={stats['avg_rr']} fomo={stats['fomo_count']}",
    ]
    for key, val in stats["session_flag_hits"].items():
        lines.append(f"  {key} hits={val}")
    pill = ", ".join(f"{k}={v}" for k, v in stats["pillar_pass_rate"].items())
    if pill:
        lines.append(f"  pillar pass rates: {pill}")
    return "\n".join(lines)


__all__ = ["record_momentum_trade", "momentum_stats", "format_summary"]
