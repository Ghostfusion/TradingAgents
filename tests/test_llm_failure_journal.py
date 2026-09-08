"""Hermetic tests for llm_failure_journal (LLM failure completion snapshots).

Regression (EIX 2026-09-07): a structured debate turn raised
LengthFinishReasonError with the full ChatCompletion (incl. 9.3k reasoning
tokens) attached, but the graph only logged the usage line — the content was
garbage-collected. The journal must persist the attached completion to the
default <data_cache_dir>/llm_failures (or the config override) so a failed
turn's output is recoverable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from tradingagents.agents.utils import llm_failure_journal as J

pytestmark = pytest.mark.timeout(120)


@dataclass
class _FakeCompletion:
    """Stand-in for an openai ChatCompletion without pydantic models.

    A dataclass so ``_completion_payload``'s asdict fallback (the
    pydantic-model_dump path is exercised by real SDK objects) serializes
    the attached reasoning tokens.
    """

    choices: list = field(
        default_factory=lambda: [
            {
                "message": {
                    "content": "",
                    "reasoning_content": "hidden reasoning tokens " * 50,
                }
            }
        ]
    )
    usage: dict = field(default_factory=lambda: {"completion_tokens": 16000, "prompt_tokens": 2331})
    model: str = "deepseek/deepseek-v4-flash"


def _exc_with_completion() -> BaseException:
    e = Exception("Could not parse response content as the length limit was reached")
    e.completion = _FakeCompletion()  # type: ignore[attr-defined]
    return e


class TestJournalWritesCompletion:
    def test_written_to_default_cache_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "tradingagents.dataflows.config.get_config",
            lambda: {"data_cache_dir": str(tmp_path), "llm_failure_journal_dir": ""},
        )
        J.journal_llm_failure("debate/structured_turn", _exc_with_completion())
        files = list((tmp_path / "llm_failures").glob("*.json"))
        assert files, "journaled file not written"
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["stage"] == "debate/structured_turn"
        reasoning = data["completion"]["choices"][0]["message"]["reasoning_content"]
        # The attached completion is what makes the payload valuable.
        assert len(reasoning) > 100

    def test_uses_explicit_config_dir(self, tmp_path, monkeypatch):
        custom = tmp_path / "custom"
        monkeypatch.setattr(
            "tradingagents.dataflows.config.get_config",
            lambda: {
                "data_cache_dir": str(tmp_path),
                "llm_failure_journal_dir": str(custom),
            },
        )
        J.journal_llm_failure("x", _exc_with_completion())
        files = list(custom.glob("*.json"))
        assert len(files) == 1

    def test_none_completion_is_handled(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "tradingagents.dataflows.config.get_config",
            lambda: {"data_cache_dir": str(tmp_path)},
        )
        # No completion attached -> still writes a payload with a null completion.
        J.journal_llm_failure("stage", Exception("plain"))
        files = list((tmp_path / "llm_failures").glob("*.json"))
        assert files
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["completion"] is None
