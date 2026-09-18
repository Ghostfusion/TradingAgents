"""The score-history store, and the movement rule (WP-12 `P12-8`).

`docs/scores/ResearchLayerWiring.md` §4.3 — *"the highest-value part, and the one
with no producer"*. A `TradeScore` that rose `61 → 76` is a different research
situation from one that fell `91 → 76`, and before this module the repository had
no way to say which had happened: there is a per-run memory log and the WP-10
panel cache, but nothing keyed on `(ticker, date)` holding prior engine scores.

The store is one JSONL row per scored run date under
``<data_cache_dir>/score_history/<TICKER>.jsonl``. Each row records the composite,
its coverage, and **the weight vector it scored under** — because a delta across a
weight change is not a delta.

**The rule the owner set (§9 D2), which this module enforces rather than
documents.** Deltas are held until the vector is measured, validated and promoted,
and the reason is *vector validity*, not `RESEARCH_ONLY`:

    no validated vector -> no delta -> no movement

Three conditions must hold before a delta is printed: a prior row exists, that row
scored under the **same** vector, and the vector is **validated**. Otherwise the
movement is `UNAVAILABLE` **with its reason** — never a manufactured delta, and
never a `0`. Research calculations may still be logged internally; what is
withheld is their presentation as movement.

`NA` rules, per master rule 2: no prior row means **no delta keys at all** in the
rendered block, not a zero. The delta is always printed against the date of the
previous scored observation — a delta against an unstated date is a disguised
fabrication.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = [
    "MOVEMENT_AVAILABLE",
    "MOVEMENT_UNAVAILABLE",
    "history_path",
    "read_history",
    "record_score",
    "score_movement",
    "vector_key",
    "vector_validated",
]

MOVEMENT_AVAILABLE = "AVAILABLE"
MOVEMENT_UNAVAILABLE = "UNAVAILABLE"

#: The rung at which a delta becomes legitimate (§4.6).
_VALIDATED_FROM = "VALIDATED"


def _cache_dir(data_cache_dir: Any = None) -> Path:
    """Where the history lives: the caller's cache dir, else the ambient one."""
    if data_cache_dir:
        return Path(str(data_cache_dir))
    try:
        from tradingagents.dataflows.config import get_config

        return Path(str((get_config() or {}).get("data_cache_dir") or "."))
    except Exception:  # noqa: BLE001 - a missing config is not a crash
        return Path(".")


def history_path(ticker: str, data_cache_dir: Any = None) -> Path:
    """The store's path for one ticker. One file per ticker, one row per date."""
    name = str(ticker).strip().upper()
    return _cache_dir(data_cache_dir) / "score_history" / f"{name}.jsonl"


def vector_key(composite: dict | None) -> str:
    """A stable identity for the weight vector a composite scored under.

    Includes ``weights_source`` because the same numbers from the owner's
    published vector and from a measured one are not the same claim.
    """
    comp = composite or {}
    weights = comp.get("weights") or {}
    parts = []
    for key in sorted(weights):
        try:
            parts.append(f"{key}={float(weights[key]):g}")
        except (TypeError, ValueError):
            parts.append(f"{key}={weights[key]!r}")
    return f"{comp.get('weights_source') or 'unknown'}|{','.join(parts)}"


def vector_validated(composite: dict | None) -> bool:
    """Whether the vector has reached the ladder rung that makes a delta honest."""
    try:
        from tradingagents.strategies.trade_score import PROMOTION_LADDER
    except Exception:  # noqa: BLE001
        return False
    status = (composite or {}).get("status")
    try:
        return PROMOTION_LADDER.index(status) >= PROMOTION_LADDER.index(_VALIDATED_FROM)
    except ValueError:
        return False


def read_history(ticker: str, data_cache_dir: Any = None) -> list[dict]:
    """Every recorded row for a ticker, oldest first. A corrupt line is skipped."""
    path = history_path(ticker, data_cache_dir)
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


def record_score(
    ticker: str,
    trade_date: str | None,
    composite: dict | None,
    data_cache_dir: Any = None,
) -> dict | None:
    """Append this run's observation, unless the date already has one.

    One row per scored run date: re-running the same date does not rewrite
    history, so an observation is never silently replaced by a later one. Returns
    the row written, or ``None`` when there is nothing to record.
    """
    score = (composite or {}).get("score")
    date = str(trade_date)[:10] if trade_date else None
    if score is None or not date:
        return None
    existing = {str(r.get("date")) for r in read_history(ticker, data_cache_dir)}
    if date in existing:
        return None
    row = {
        "date": date,
        "score": score,
        "coverage": (composite or {}).get("coverage"),
        "vector": vector_key(composite),
        "status": (composite or {}).get("status"),
    }
    path = history_path(ticker, data_cache_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:  # noqa: BLE001 - an advisory store must not break a run
        return None
    return row


def _prior_row(ticker: str, trade_date: str | None, data_cache_dir: Any) -> dict | None:
    """The most recent observation strictly before ``trade_date``."""
    date = str(trade_date)[:10] if trade_date else None
    if not date:
        return None
    earlier = [r for r in read_history(ticker, data_cache_dir) if str(r.get("date")) < date]
    return earlier[-1] if earlier else None


def score_movement(
    ticker: str,
    trade_date: str | None,
    composite: dict | None,
    data_cache_dir: Any = None,
) -> dict:
    """The delta against the previous scored observation, or why it is withheld.

    Returns ``{"movement", "reason", "prev", "prev_date", "delta"}``. Every
    withheld case names its reason, so a reader can tell *"nothing to compare"*
    from *"the vector is not validated yet"* — which is the difference between a
    quiet day and a rule doing its job.
    """
    out: dict = {
        "movement": MOVEMENT_UNAVAILABLE,
        "reason": None,
        "prev": None,
        "prev_date": None,
        "delta": None,
    }
    score = (composite or {}).get("score")
    if score is None:
        out["reason"] = "no composite was produced for this run"
        return out
    if not vector_validated(composite):
        out["reason"] = (
            "the weight vector is not validated yet, so a delta would claim both "
            "observations are legitimate when neither has been measured"
        )
        return out
    prior = _prior_row(ticker, trade_date, data_cache_dir)
    if not prior:
        out["reason"] = "no prior scored observation"
        return out
    if str(prior.get("vector")) != vector_key(composite):
        out["reason"] = "the vector changed between the two observations"
        return out
    prev = prior.get("score")
    if prev is None:
        out["reason"] = "the prior observation carried no composite"
        return out
    try:
        delta = float(score) - float(prev)
    except (TypeError, ValueError):
        out["reason"] = "the two observations are not both numeric"
        return out
    out.update(
        movement=MOVEMENT_AVAILABLE,
        reason=None,
        prev=prev,
        prev_date=str(prior.get("date")),
        delta=delta,
    )
    return out
