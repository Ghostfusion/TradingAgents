"""Journal LLM failures that carry the provider's raw completion.

When a structured LLM invoke fails because the model hit the token limit,
the openai SDK raises ``LengthFinishReasonError`` with the FULL
``ChatCompletion`` attached (``e.completion``) — including the hidden
reasoning tokens that "disappeared" with the exception. The graph only logs
the usage line; the reasoning text is otherwise garbage-collected.

This module snapshots that completion to disk so a failed turn's output is
recoverable for diagnosis (observed live: a 9.3k-reasoning-token turn on
EIX 2026-09-07 whose content was cut at the length limit). Pure advisory:
never raises, never breaks the caller's fallback.

The journal is ON by default, writing to ``<data_cache_dir>/llm_failures``
(config key ``llm_failure_journal_dir`` overrides; empty = the default).
Set ``TRADINGAGENTS_LLM_FAILURE_JOURNAL_DIR`` to disable or redirect.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def _journal_dir(cfg: dict | None) -> Path | None:
    """Resolve the journal directory, or None when it cannot be determined."""
    cfg = cfg or {}
    explicit = str(cfg.get("llm_failure_journal_dir") or "").strip()
    if explicit:
        return Path(explicit)
    cache = cfg.get("data_cache_dir")
    if not cache:
        return None
    return Path(cache) / "llm_failures"


def _completion_payload(completion) -> dict | None:
    """Serialize a provider completion (openai ChatCompletion or similar)."""
    if completion is None:
        return None
    dump = getattr(completion, "model_dump", None)
    if callable(dump):
        try:
            out = dump()
            if isinstance(out, dict):
                return out
        except Exception:  # noqa: BLE001 - degraded dump is better than nothing
            pass
    # Fallbacks: pydantic v1 asdict / plain dict / repr.
    from dataclasses import asdict, is_dataclass

    if is_dataclass(completion):
        try:
            out = asdict(completion)  # type: ignore[arg-type]
            if isinstance(out, dict):
                return out
        except Exception:  # noqa: BLE001
            pass
    if isinstance(completion, dict):
        return completion
    return {"repr": str(completion)}


def journal_llm_failure(stage: str, exc: BaseException) -> None:
    """Persist one failed structured-LLM completion (advisory; never raises)."""
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001
        cfg = {}
    journal_dir = _journal_dir(cfg)
    if journal_dir is None:
        return
    try:
        journal_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # noqa: BLE001
        logger.debug("llm_failure_journal: cannot create %s: %s", journal_dir, exc)
        return
    completion = _completion_payload(getattr(exc, "completion", None))
    payload = {
        "ts": time.time(),
        "stage": stage,
        "exception": type(exc).__name__,
        "message": str(exc)[:2000],
        "usage": getattr(getattr(exc, "completion", None), "usage", None),
        "model": getattr(getattr(exc, "completion", None), "model", None),
        "completion": completion,
        "body": getattr(exc, "body", None),
    }
    name = f"llm_failure_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 100000}.json"
    try:
        (journal_dir / name).write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        logger.warning("llm_failure_journal: wrote %s/%s", journal_dir, name)
    except Exception as exc2:  # noqa: BLE001 - must never break the caller
        logger.warning("llm_failure_journal: write failed: %s", exc2)  # noqa: TRY400

__all__ = ["journal_llm_failure"]
