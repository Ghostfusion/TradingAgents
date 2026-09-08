"""Per-analyst tool-call log: record which tools the LLM actually invoked.

The deterministic gatherer records what was *gathered* (tool_evidence.json),
but the model-pool tools (the ~40 that need model-supplied inputs) execute
only when the LLM calls them. Nothing journaled which of those were actually
requested, so "for the 40 callable tools, how many were called" was only
answerable live, not post-run.

This logger appends one JSONL line per model tool call, attributed to the
analyst node that made it, to ``<dir>/<SYMBOL>_tool_calls.jsonl`` where
``<dir>`` is the config key ``tool_call_log_dir`` (env
``TRADINGAGENTS_TOOL_CALL_LOG_DIR``; default ``<data_cache_dir>/tool_calls``).
Each line: ts, symbol, trade_date, analyst, tool, event
(``executed`` = hit the vendor / ``short_circuit`` = already gathered,
answered from the §Tool Evidence block), whether the name is in the
analyst's model pool, and the call args.

Advisory: never raises, never blocks the graph. Wired in
``evidence_gather.short_circuit_tool_calls``.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def _log_dir(cfg: dict | None) -> Path | None:
    cfg = cfg or {}
    explicit = str(cfg.get("tool_call_log_dir") or "").strip()
    if explicit:
        return Path(explicit)
    cache = cfg.get("data_cache_dir")
    if not cache:
        return None
    return Path(cache) / "tool_calls"


def log_tool_call(
    analyst: str,
    tool: str,
    event: str,
    args: dict | None = None,
    state: dict | None = None,
    in_model_pool: bool | None = None,
) -> None:
    """Append one tool-call line to the per-symbol tool-call log (advisory)."""
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001
        cfg = {}
    d = _log_dir(cfg)
    if d is None:
        return
    state = state or {}
    symbol = str(state.get("company_of_interest") or "unknown")
    trade_date = str(state.get("trade_date") or "")
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "symbol": symbol,
        "trade_date": trade_date,
        "analyst": analyst,
        "tool": tool,
        "event": event,
        "in_model_pool": in_model_pool,
        "args": args or {},
    }
    try:
        with _LOCK:
            d.mkdir(parents=True, exist_ok=True)
            with (d / f"{symbol}_tool_calls.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception as exc:  # noqa: BLE001 - must never break the graph
        logger.warning("tool_call_log: write failed for %s/%s: %s", symbol, tool, exc)  # noqa: TRY400

__all__ = ["log_tool_call"]
