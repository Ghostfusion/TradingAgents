"""The model-knowledge cutoff check (H12): was a replay inside the model's window?

Pure and offline: the declared table, the served-snapshot derivation, the
fail-closed statuses, and the annotation ``tradingagents/jev.py`` writes into
every verdict payload. No network, no key.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tradingagents.jev as jev
from tradingagents.strategies import knowledge_cutoff as kc

pytestmark = pytest.mark.timeout(60)

SERVED = "openai/gpt-6-luna-decisions-20261006"


def test_the_served_snapshot_date_is_the_conservative_cutoff(monkeypatch):
    """The decisions API returns a dated snapshot; its freeze date is the bound
    the run's own recorded response supplies, with no declared table needed."""
    monkeypatch.delenv(kc.ENV_OVERRIDE, raising=False)
    out = kc.contamination_verdict(as_of="2024-06-01", models=[SERVED])
    assert out["status"] == "CONTAMINATED"
    assert out["offenders"] == [SERVED]
    assert out["models"][SERVED] == {
        "cutoff": "2026-10-06", "provenance": "served-snapshot", "verdict": "contaminated",
    }


def test_a_cutoff_equal_to_the_analysis_date_is_clean(monkeypatch):
    """A model frozen that day cannot have trained on that day's outcome."""
    monkeypatch.delenv(kc.ENV_OVERRIDE, raising=False)
    out = kc.contamination_verdict(as_of="2026-10-06", models=[SERVED])
    assert out["status"] == "CLEAN" and out["offenders"] == []


def test_a_declared_cutoff_wins_over_the_served_snapshot(monkeypatch):
    """The true training cutoff is NARROWER than the freeze date, so a
    declaration overrides the derivation - and it can flip the verdict: the
    freeze date (2026-10-06) puts a 2025 analysis inside the window, while a
    declared 2025-01-01 cutoff puts it after the model's knowledge ends."""
    out_derived = kc.contamination_verdict(as_of="2025-06-01", models=[SERVED])
    assert out_derived["status"] == "CONTAMINATED"  # 2026-10-06 > 2025-06-01

    monkeypatch.setenv(kc.ENV_OVERRIDE, "openai/gpt-6=2025-01-01")
    out = kc.contamination_verdict(as_of="2025-06-01", models=[SERVED])
    assert out["status"] == "CLEAN"
    assert out["models"][SERVED]["cutoff"] == "2025-01-01"
    assert out["models"][SERVED]["provenance"].startswith("declared")


def test_the_longest_declared_prefix_wins(monkeypatch):
    monkeypatch.setenv(kc.ENV_OVERRIDE, "openai=2024-01-01;openai/gpt-6-luna=2025-06-01")
    out = kc.contamination_verdict(as_of="2025-07-01", models=[SERVED])
    assert out["models"][SERVED]["cutoff"] == "2025-06-01"
    assert out["status"] == "CLEAN"


def test_an_undeclared_model_fails_closed(monkeypatch):
    """An unmeasured window is UNKNOWN, never clean - and the basis names the
    lever that would resolve it."""
    monkeypatch.delenv(kc.ENV_OVERRIDE, raising=False)
    out = kc.contamination_verdict(as_of="2026-10-09", models=["mystery/model"])
    assert out["status"] == "UNKNOWN"
    assert out["unresolved"] == ["mystery/model"]
    assert kc.ENV_OVERRIDE in out["basis"]


def test_a_version_shaped_id_is_not_read_as_a_date(monkeypatch):
    monkeypatch.delenv(kc.ENV_OVERRIDE, raising=False)
    out = kc.contamination_verdict(as_of="2026-10-09", models=["typesafe/jev-1.13"])
    assert out["status"] == "UNKNOWN"
    assert out["models"]["typesafe/jev-1.13"]["cutoff"] is None


def test_an_impossible_snapshot_stamp_is_refused(monkeypatch):
    """A 13th month is not a date: the derivation refuses rather than
    normalising it into one."""
    monkeypatch.delenv(kc.ENV_OVERRIDE, raising=False)
    out = kc.contamination_verdict(as_of="2026-10-09", models=["vendor/model-20261399"])
    assert out["models"]["vendor/model-20261399"]["cutoff"] is None


def test_no_analysis_date_is_unknown(monkeypatch):
    monkeypatch.delenv(kc.ENV_OVERRIDE, raising=False)
    assert kc.contamination_verdict(as_of=None, models=[SERVED])["status"] == "UNKNOWN"
    assert kc.contamination_verdict(as_of="not-a-date", models=[SERVED])["status"] == "UNKNOWN"


def test_no_models_is_unknown(monkeypatch):
    monkeypatch.delenv(kc.ENV_OVERRIDE, raising=False)
    assert kc.contamination_verdict(as_of="2026-10-09", models=[])["status"] == "UNKNOWN"


def test_a_malformed_declaration_is_skipped_not_raised():
    """A typo in the diagnostic declaration must not take a run down."""
    assert kc._parse_declarations("a=2025-01-01;oops;b=not-a-date;c=2025-02-02") == {
        "a": "2025-01-01", "c": "2025-02-02",
    }
    assert kc._parse_declarations(None) == {}


def test_one_known_offender_beats_another_unresolved_model(monkeypatch):
    """CONTAMINATED is not downgraded to UNKNOWN by a second model whose cutoff
    is undeclared - the run is already known to be inside a window."""
    monkeypatch.delenv(kc.ENV_OVERRIDE, raising=False)
    out = kc.contamination_verdict(as_of="2024-06-01", models=[SERVED, "mystery/model"])
    assert out["status"] == "CONTAMINATED"
    assert out["unresolved"] == ["mystery/model"]


# ---------------------------------------------------------------------------
# the annotation the verdict file carries
# ---------------------------------------------------------------------------


def _tree_with_decision(tmp_path: Path, effective_date: str) -> Path:
    (tmp_path / "1_analysts").mkdir()
    (tmp_path / "1_analysts" / "market.md").write_text("body", encoding="utf-8")
    (tmp_path / "research_decision.json").write_text(
        json.dumps({"effective_date": effective_date}), encoding="utf-8"
    )
    return tmp_path


class _Serving:
    """A transport answering with a dated served-snapshot model."""

    def __init__(self, model: str):
        self.model = model
        self.calls: list[dict] = []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append(payload)
        return 200, json.dumps({
            "provider": "OpenAI" if "openai" in self.model else "TypeSafe",
            "model": self.model,
            "answers": {
                "rating": {"type": "choice", "choice": "hold", "confidence": 0.7,
                           "probabilities": {"buy": 0.2, "hold": 0.7, "sell": 0.1}},
                "evidence": {"type": "score", "score": 3.0},
                "horizon": {"type": "choice", "choice": "short"},
            },
            "usage": {"input_tokens": 5, "output_tokens": 0, "cost": 0.0},
        })


def test_the_verdict_block_reads_the_trees_effective_date(tmp_path):
    """The as-of comes from the tree's own `research_decision.json`, and the
    block names that source rather than substituting a date silently."""
    tree = _tree_with_decision(tmp_path, "2024-06-01")
    path, payload = jev.judge_tree(
        tree, key="k", poster=_Serving(SERVED),
    )
    block = payload["knowledge_cutoff"]
    assert block["status"] == "CONTAMINATED"
    assert block["as_of"] == "2024-06-01"
    assert block["date_source"] == "research_decision.effective_date"
    assert block["offenders"] == [SERVED]
    # the artefact on disk carries the same block, not just the returned payload
    assert json.loads(path.read_text(encoding="utf-8"))["knowledge_cutoff"] == block


def test_the_verdict_block_reports_unknown_without_an_as_of(tmp_path):
    """No dated artefact and no name stamp is UNKNOWN, never CLEAN."""
    (tmp_path / "1_analysts").mkdir()
    (tmp_path / "1_analysts" / "market.md").write_text("body", encoding="utf-8")
    _, payload = jev.judge_tree(tmp_path, key="k", poster=_Serving("mystery/model"))
    assert payload["knowledge_cutoff"]["status"] == "UNKNOWN"
    assert payload["knowledge_cutoff"]["basis"]


def test_a_vendor_failure_still_writes_a_block(tmp_path):
    """The block is an annotation on a diagnostic artifact; a failed call must
    not remove it (the models then fall back to the configured name)."""
    (tmp_path / "1_analysts").mkdir()
    (tmp_path / "1_analysts" / "market.md").write_text("body", encoding="utf-8")

    def _boom(url, headers, payload, timeout):
        return 429, "rate limited"

    _, payload = jev.judge_tree(tmp_path, key="k", poster=_boom)
    block = payload["knowledge_cutoff"]
    assert block["status"] == "UNKNOWN"  # `typesafe/jev-1.13` has no dated stamp
    assert list(block["models"]) == [jev.DEFAULT_MODEL]
