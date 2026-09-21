"""The post-run TypeSafe verdict: the gate, and the artefact it writes.

Two contracts, both enforced here with no vendor and no key:

* ``enable_jev_verdict`` controls the hook. Off means the judge is never called,
  so a gate-off run produces exactly the tree it produced before the gate
  existed; on means it is. ``docs/gate_registry.md`` §8 requires a test that
  fails when the gate is ignored, which is what the two call-site tests are.
* the verdict LANDS IN THE REPORT TREE. The point of the step is that the
  judgement travels with the report it is about, so the file path is asserted,
  not just the payload.

It is best-effort by design: a judge that annotates a finished run must never
fail it, so a missing key and a vendor failure are both asserted to be quiet.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import batch
import tradingagents.jev as jev

REPO = Path(__file__).resolve().parents[1]
ANALYST_STEMS = ("fundamentals", "market", "news", "sentiment")


def _shipped_default(key: str):
    """The value in the ``DEFAULT_CONFIG`` literal, before any env override.

    Read structurally (AST), so it is the shipped default and not a copy of the
    source line. This is the only way to assert a default honestly on a machine
    whose ``.env`` flips gates: ``DEFAULT_CONFIG`` is post-override.
    """
    import ast

    tree = ast.parse((REPO / "tradingagents" / "default_config.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not any(
            getattr(t, "id", None) == "DEFAULT_CONFIG" for t in node.targets
        ):
            continue
        call = node.value
        assert isinstance(call, ast.Call)
        literal = call.args[0]
        assert isinstance(literal, ast.Dict)
        for k, v in zip(literal.keys, literal.values, strict=True):
            if isinstance(k, ast.Constant) and k.value == key:
                return ast.literal_eval(v)
    raise AssertionError(f"{key!r} is not in the DEFAULT_CONFIG literal")


def _tree(tmp_path: Path) -> Path:
    """A minimal but real report tree: the four analyst reports, nothing else."""
    for stem in ANALYST_STEMS:
        (tmp_path / "1_analysts").mkdir(exist_ok=True)
        (tmp_path / "1_analysts" / f"{stem}.md").write_text(
            f"{stem} body. We recommend a Buy.", encoding="utf-8"
        )
    return tmp_path


class _Recorder:
    """A transport that answers every state and records what it was sent."""

    def __init__(self, status: int = 200, body: str | None = None):
        self.status = status
        self.body = body or json.dumps({
            "provider": "TypeSafe",
            "answers": {
                "rating": {"type": "choice", "choice": "hold", "confidence": 0.8,
                           "probabilities": {"buy": 0.1, "hold": 0.8, "sell": 0.1}},
                "evidence": {"type": "score", "score": 3.0},
                "horizon": {"type": "choice", "choice": "short"},
            },
            "usage": {"input_tokens": 10, "output_tokens": 5, "cost": 0.0002},
        })
        self.calls: list[dict] = []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append(payload)
        return self.status, self.body


@pytest.fixture
def _keyed(monkeypatch):
    """A present key and a fake transport, so no test touches the network."""
    poster = _Recorder()
    monkeypatch.setattr(jev, "resolve_key", lambda *a, **k: "sk-or-v1-test")
    monkeypatch.setattr(jev, "post_json", poster)
    return poster


# ---------------------------------------------------------------------------
# the gate controls the hook
# ---------------------------------------------------------------------------


def test_the_gate_ships_off_by_default():
    """Off is what keeps a run from paying for a judge nobody asked for.

    Asserts the CODE default - the `DEFAULT_CONFIG` literal - and not
    `DEFAULT_CONFIG` itself. That dict is the default *after*
    `_apply_env_overrides`, so asserting it asserts the developer's `.env`:
    the test would pass on one machine and fail on the next. (The owner's `.env`
    sets this gate true, which is the point of the gate.)
    """
    assert _shipped_default("enable_jev_verdict") is False


def test_gate_off_never_calls_the_judge(monkeypatch, tmp_path):
    monkeypatch.setattr(batch, "DEFAULT_CONFIG", {"enable_jev_verdict": False})
    called: list = []
    monkeypatch.setattr(batch, "_batch_jev_verdict", lambda d: called.append(d))

    batch._post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert called == [], "the gate was ignored - the judge ran while switched off"


def test_gate_on_calls_the_judge(monkeypatch, tmp_path):
    monkeypatch.setattr(batch, "DEFAULT_CONFIG", {"enable_jev_verdict": True})
    called: list = []
    monkeypatch.setattr(batch, "_batch_jev_verdict", lambda d: called.append(d))

    batch._post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert called == [tmp_path]


def test_the_two_post_save_gates_are_independent(monkeypatch, tmp_path):
    """Enabling the verdict must not drag the pre-market check along."""
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": True, "enable_pre_market_review": False},
    )
    pre: list = []
    monkeypatch.setattr(batch, "_batch_pre_market_check", lambda *a: pre.append(a))
    monkeypatch.setattr(batch, "_batch_jev_verdict", lambda d: None)

    batch._post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert pre == []


# ---------------------------------------------------------------------------
# the artefact lands in the tree
# ---------------------------------------------------------------------------


def test_the_verdict_is_written_into_the_report_tree(tmp_path, _keyed):
    tree = _tree(tmp_path)

    batch._batch_jev_verdict(tree)

    out = tree / "jev_verdict.json"
    assert out.is_file(), "the verdict did not travel with its report"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["origin"] == tree.name
    assert sorted(payload["ratings"]) == sorted(ANALYST_STEMS)
    assert payload["ratings"]["market"]["rating"] == "hold"
    assert payload["failures"] == 0


def test_the_hook_sends_analyst_reports_neutralised(tmp_path, _keyed):
    """The recipe, asserted at the hook rather than only at the CLI."""
    tree = _tree(tmp_path)

    batch._batch_jev_verdict(tree)

    assert len(_keyed.calls) == 4, "one call per analyst report"
    for payload in _keyed.calls:
        assert jev.POSITION_MARKER in payload["state"]
        assert "Buy" not in payload["state"], "the report's own call was sent"
        assert set(payload["questions"]) == {"rating", "evidence", "horizon"}


def test_no_other_report_reaches_the_judge(tmp_path, _keyed):
    tree = _tree(tmp_path)
    (tree / "2_research").mkdir()
    (tree / "2_research" / "bull.md").write_text("BULL", encoding="utf-8")

    batch._batch_jev_verdict(tree)

    assert all(p["state"] != "BULL" for p in _keyed.calls)


# ---------------------------------------------------------------------------
# best-effort: never fail the run that produced the report
# ---------------------------------------------------------------------------


def test_a_missing_key_skips_quietly(monkeypatch, tmp_path, capsys):
    tree = _tree(tmp_path)
    monkeypatch.setattr(jev, "resolve_key", lambda *a, **k: "")

    batch._batch_jev_verdict(tree)   # must not raise

    assert not (tree / "jev_verdict.json").exists()
    assert "OPENROUTER_API_KEY not set" in capsys.readouterr().out


def test_a_vendor_failure_is_recorded_and_not_raised(monkeypatch, tmp_path):
    tree = _tree(tmp_path)
    monkeypatch.setattr(jev, "resolve_key", lambda *a, **k: "sk-or-v1-test")
    monkeypatch.setattr(jev, "post_json", _Recorder(status=400, body="nope"))

    batch._batch_jev_verdict(tree)   # must not raise

    payload = json.loads((tree / "jev_verdict.json").read_text(encoding="utf-8"))
    assert payload["failures"] == 4
    assert payload["ratings"] == {}
    assert all(r["status"] == 400 for r in payload["results"])


def test_a_transport_exception_is_recorded_and_not_raised(monkeypatch, tmp_path):
    tree = _tree(tmp_path)
    monkeypatch.setattr(jev, "resolve_key", lambda *a, **k: "sk-or-v1-test")

    def boom(*a, **k):
        raise TimeoutError("vendor hung")

    monkeypatch.setattr(jev, "post_json", boom)

    batch._batch_jev_verdict(tree)   # must not raise

    payload = json.loads((tree / "jev_verdict.json").read_text(encoding="utf-8"))
    assert payload["failures"] == 4
    assert "TimeoutError" in payload["results"][0]["error"]


# ---------------------------------------------------------------------------
# the core entry point
# ---------------------------------------------------------------------------


def test_judge_tree_returns_the_path_and_the_payload(tmp_path, _keyed):
    tree = _tree(tmp_path)

    path, payload = jev.judge_tree(tree, key="sk-or-v1-test")

    assert path == tree / "jev_verdict.json"
    assert path.is_file()
    assert payload["origin"] == tree.name


def test_verdict_for_tree_on_a_tree_with_no_analyst_reports(tmp_path):
    """No reports is not an error - it is an empty verdict."""
    payload = jev.verdict_for_tree(tmp_path, key="sk-or-v1-test")

    assert payload["stems"] == []
    assert payload["ratings"] == {}
    assert payload["failures"] == 0
