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

ANALYST_STEMS = ("fundamentals", "market", "news", "sentiment")


def _shipped_default(key: str):
    """The value in `SHIPPED_DEFAULTS`, before any env override is applied.

    `DEFAULT_CONFIG` is post-override - `tradingagents/__init__.py` loads a
    developer's `.env` into `os.environ` and `_apply_env_overrides` folds it in -
    so asserting it would assert the developer's machine. `SHIPPED_DEFAULTS` is
    the literal those overrides are applied to, kept as its own object for
    exactly this, so the value is read rather than parsed out of the source.
    """
    from tradingagents.default_config import SHIPPED_DEFAULTS

    if key not in SHIPPED_DEFAULTS:
        raise AssertionError(f"{key!r} is not in SHIPPED_DEFAULTS")
    return SHIPPED_DEFAULTS[key]


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

    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert called == [], "the gate was ignored - the judge ran while switched off"


def test_gate_on_calls_the_judge(monkeypatch, tmp_path):
    monkeypatch.setattr(batch, "DEFAULT_CONFIG", {"enable_jev_verdict": True})
    called: list = []
    monkeypatch.setattr(batch, "_batch_jev_verdict", lambda d: called.append(d))

    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert called == [tmp_path]


# ---------------------------------------------------------------------------
# the second decider - its own gate, its own file, run after the first
# ---------------------------------------------------------------------------


def test_the_second_decider_gate_ships_off_by_default():
    """A second paid judge is its own opt-in, so it ships off."""
    assert _shipped_default("enable_pplx_decider") is False


def test_pplx_gate_off_never_calls_the_second_decider(monkeypatch, tmp_path):
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": False, "enable_pplx_decider": False},
    )
    called: list = []
    monkeypatch.setattr(batch, "_batch_pplx_decider", lambda d: called.append(d))

    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert called == [], "the second decider ran while its gate was off"


def test_pplx_gate_on_calls_the_second_decider(monkeypatch, tmp_path):
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": False, "enable_pplx_decider": True},
    )
    called: list = []
    monkeypatch.setattr(batch, "_batch_pplx_decider", lambda d: called.append(d))

    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert called == [tmp_path]


def test_the_two_decider_gates_are_independent(monkeypatch, tmp_path):
    """Each judge is its own opt-in: one on must not drag the other on."""
    seen: list = []
    monkeypatch.setattr(batch, "_batch_jev_verdict", lambda d: seen.append(("jev", d)))
    monkeypatch.setattr(batch, "_batch_pplx_decider", lambda d: seen.append(("pplx", d)))

    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": True, "enable_pplx_decider": False},
    )
    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")
    assert seen == [("jev", tmp_path)]

    seen.clear()
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": False, "enable_pplx_decider": True},
    )
    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")
    assert seen == [("pplx", tmp_path)]


def test_the_second_decider_runs_after_the_first(monkeypatch, tmp_path):
    """Order is pinned: the tree log and the cost report read top-down."""
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": True, "enable_pplx_decider": True},
    )
    order: list = []
    monkeypatch.setattr(batch, "_batch_jev_verdict", lambda d: order.append("jev"))
    monkeypatch.setattr(batch, "_batch_pplx_decider", lambda d: order.append("pplx"))

    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert order == ["jev", "pplx"]


def test_the_two_post_save_gates_are_independent(monkeypatch, tmp_path):
    """Enabling the verdict must not drag the pre-market check along."""
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": True, "enable_pre_market_review": False},
    )
    pre: list = []
    monkeypatch.setattr(batch, "_batch_pre_market_check", lambda *a: pre.append(a))
    monkeypatch.setattr(batch, "_batch_jev_verdict", lambda d: None)

    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert pre == []


def test_a_missing_trade_date_skips_the_pre_market_check(monkeypatch, tmp_path):
    """The pre-market file is named after the trade date.

    A caller that cannot supply one (the interactive CLI always can, but the
    parameter is optional) must skip the check rather than write
    ``pre_market_review_None.md``. The verdict needs no date and still runs.
    """
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": True, "enable_pre_market_review": True},
    )
    pre: list = []
    jev_calls: list = []
    monkeypatch.setattr(batch, "_batch_pre_market_check", lambda *a: pre.append(a))
    monkeypatch.setattr(batch, "_batch_jev_verdict", lambda d: jev_calls.append(d))

    batch.post_save_annotations("MSFT", tmp_path, None)

    assert pre == [], "a date-less caller wrote a date-named file"
    assert jev_calls == [tmp_path], "the verdict does not need the date"


def test_the_interactive_cli_writer_runs_the_same_annotations(monkeypatch, tmp_path):
    """`cli.main.save_report_to_disk` must annotate the tree it writes.

    The interactive CLI writes its tree directly (it never goes through
    ``batch.analyze``), so until 2026-09-28 it was the one producer that ran
    neither post-save hook. Measured: ``reports/TROW_20260928_124933`` and
    ``reports/PBR_20260925_142907`` are 9-entry trees with no
    ``jev_verdict.json``, against 10 entries for every batch tree.
    """
    from cli import main as cli_main

    seen: list = []
    monkeypatch.setattr(
        cli_main, "write_report_tree",
        lambda state, ticker, path: Path(path) / "complete_report.md",
    )
    monkeypatch.setattr(
        batch, "post_save_annotations",
        lambda symbol, report_dir, trade_date: seen.append((symbol, str(report_dir), trade_date)),
    )

    written = cli_main.save_report_to_disk({}, "TROW", tmp_path, "2026-09-28")

    assert seen == [("TROW", str(tmp_path), "2026-09-28")]
    assert written == tmp_path / "complete_report.md"


def test_the_cli_writer_survives_an_annotation_that_explodes(monkeypatch, tmp_path, capsys):
    """A saved run is already on disk; annotation failure must not undo that."""
    from cli import main as cli_main

    monkeypatch.setattr(
        cli_main, "write_report_tree",
        lambda state, ticker, path: Path(path) / "complete_report.md",
    )

    def boom(*a, **k):
        raise RuntimeError("hooks are broken")

    monkeypatch.setattr(batch, "post_save_annotations", boom)

    written = cli_main.save_report_to_disk({}, "TROW", tmp_path, "2026-09-28")

    assert written == tmp_path / "complete_report.md"
    assert "annotations skipped for TROW" in capsys.readouterr().out


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


def test_the_second_decider_writes_its_own_file_beside_the_first(tmp_path, _keyed):
    """Two deciders, two files - neither verdict overwrites the other."""
    tree = _tree(tmp_path)

    batch._batch_jev_verdict(tree)
    batch._batch_pplx_decider(tree)

    assert (tree / jev.VERDICT_FILENAME).is_file()
    pplx = tree / jev.PPLX_VERDICT_FILENAME
    assert pplx.is_file(), "the second verdict did not travel with its report"
    payload = json.loads(pplx.read_text(encoding="utf-8"))
    assert payload["model"] == jev.PPLX_MODEL
    assert payload["origin"] == tree.name
    assert payload["failures"] == 0


def test_the_second_decider_sends_the_same_neutralised_battery(tmp_path, _keyed):
    """Same recipe as the first - only the model differs."""
    tree = _tree(tmp_path)

    batch._batch_pplx_decider(tree)

    assert len(_keyed.calls) == 4, "one call per analyst report"
    for payload in _keyed.calls:
        assert payload["model"] == jev.PPLX_MODEL
        assert jev.POSITION_MARKER in payload["state"]
        assert "Buy" not in payload["state"], "the report's own call was sent"
        assert set(payload["questions"]) == {"rating", "evidence", "horizon"}


def test_judge_tree_all_runs_every_decider_in_order(tmp_path, _keyed):
    tree = _tree(tmp_path)

    results = jev.judge_tree_all(tree, key="sk-or-v1-test")

    assert [d.label for d, _, _ in results] == [d.label for d in jev.DECIDERS]
    assert [p.name for _, p, _ in results] == [
        jev.VERDICT_FILENAME, jev.PPLX_VERDICT_FILENAME, jev.NOUL_VERDICT_FILENAME,
    ]
    assert all(p.is_file() for _, p, _ in results)
    assert [pl["model"] for _, _, pl in results] == [d.model for d in jev.DECIDERS]


def test_the_second_decider_is_best_effort_too(monkeypatch, tmp_path):
    """A vendor failure on the second judge must not raise, and must not
    remove the first judge's file."""
    tree = _tree(tmp_path)
    monkeypatch.setattr(jev, "resolve_key", lambda *a, **k: "sk-or-v1-test")
    monkeypatch.setattr(jev, "post_json", _Recorder(status=429, body="rate limited"))

    batch._batch_pplx_decider(tree)   # must not raise

    payload = json.loads((tree / jev.PPLX_VERDICT_FILENAME).read_text(encoding="utf-8"))
    assert payload["failures"] == 4
    assert all(r["status"] == 429 for r in payload["results"])


# ---------------------------------------------------------------------------
# the third decider - noul-only, its own gate, its own file, run last
# ---------------------------------------------------------------------------


def _noul_body() -> str:
    """The answer shape Respan returns: a float per question, no prose."""
    return json.dumps({
        "provider": "Respan",
        "model": "respan/span-01-20260925",
        "answers": {
            "rating": {"type": "noul", "noul": 0.03422103},
            "evidence": {"type": "noul", "noul": 0.31},
        },
        "usage": {"input_tokens": 4200, "output_tokens": 0, "cost": 0.00008},
    })


@pytest.fixture
def _noul_keyed(monkeypatch):
    """A present key and a transport that answers the NOUL battery."""
    poster = _Recorder(body=_noul_body())
    monkeypatch.setattr(jev, "resolve_key", lambda *a, **k: "sk-or-v1-test")
    monkeypatch.setattr(jev, "post_json", poster)
    return poster


def test_the_noul_decider_gate_ships_off_by_default():
    """A third judge is its own opt-in, exactly like the second."""
    assert _shipped_default("enable_noul_decider") is False


def test_noul_gate_off_never_calls_the_third_decider(monkeypatch, tmp_path):
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": False, "enable_pplx_decider": False,
         "enable_noul_decider": False},
    )
    called: list = []
    monkeypatch.setattr(batch, "_batch_noul_decider", lambda d: called.append(d))

    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert called == [], "the third decider ran while its gate was off"


def test_noul_gate_on_calls_the_third_decider(monkeypatch, tmp_path):
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": False, "enable_pplx_decider": False,
         "enable_noul_decider": True},
    )
    called: list = []
    monkeypatch.setattr(batch, "_batch_noul_decider", lambda d: called.append(d))

    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert called == [tmp_path]


def test_the_noul_gate_is_independent_of_the_other_two(monkeypatch, tmp_path):
    """Enabling the third judge must not drag either of the other two on - and
    neither of them may drag it on."""
    seen: list = []
    monkeypatch.setattr(batch, "_batch_jev_verdict", lambda d: seen.append("jev"))
    monkeypatch.setattr(batch, "_batch_pplx_decider", lambda d: seen.append("pplx"))
    monkeypatch.setattr(batch, "_batch_noul_decider", lambda d: seen.append("noul"))

    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": True, "enable_pplx_decider": False,
         "enable_noul_decider": False},
    )
    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")
    assert seen == ["jev"]

    seen.clear()
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": False, "enable_pplx_decider": False,
         "enable_noul_decider": True},
    )
    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")
    assert seen == ["noul"]


def test_the_noul_decider_runs_last(monkeypatch, tmp_path):
    """Order is pinned: the tree log and the cost report read top-down."""
    monkeypatch.setattr(
        batch, "DEFAULT_CONFIG",
        {"enable_jev_verdict": True, "enable_pplx_decider": True,
         "enable_noul_decider": True},
    )
    order: list = []
    monkeypatch.setattr(batch, "_batch_jev_verdict", lambda d: order.append("jev"))
    monkeypatch.setattr(batch, "_batch_pplx_decider", lambda d: order.append("pplx"))
    monkeypatch.setattr(batch, "_batch_noul_decider", lambda d: order.append("noul"))

    batch.post_save_annotations("MSFT", tmp_path, "2026-09-21")

    assert order == ["jev", "pplx", "noul"]


def test_the_noul_decider_writes_its_own_file(tmp_path, _noul_keyed):
    """Three deciders, three files - none overwrites another."""
    tree = _tree(tmp_path)

    batch._batch_noul_decider(tree)

    path = tree / jev.NOUL_VERDICT_FILENAME
    assert path.is_file(), "the third verdict did not travel with its report"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["model"] == jev.NOUL_MODEL
    assert payload["origin"] == tree.name
    assert payload["failures"] == 0
    assert payload["scores"]["market"] == {"rating": 0.03422103, "evidence": 0.31}


def test_the_noul_decider_asks_the_noul_battery_not_the_shared_one(tmp_path, _noul_keyed):
    """The reason the recipe is separate at all: Respan 400s on choice/score,
    and it also refuses a ``criteria`` key on a noul question."""
    tree = _tree(tmp_path)

    batch._batch_noul_decider(tree)

    assert len(_noul_keyed.calls) == 4, "one call per analyst report"
    for payload in _noul_keyed.calls:
        assert payload["model"] == jev.NOUL_MODEL
        assert set(payload["questions"]) == {"rating", "evidence"}
        assert {q["type"] for q in payload["questions"].values()} == {"noul"}
        assert all("criteria" not in q for q in payload["questions"].values())
        # Same neutralisation as the other deciders.
        assert jev.POSITION_MARKER in payload["state"]
        assert "Buy" not in payload["state"], "the report's own call was sent"


def test_judge_tree_routes_a_noul_decider_to_the_noul_recipe(tmp_path, _noul_keyed):
    """The roll-up key follows the decider: ``scores``, never ``ratings``.

    One key for both would invite reading a document statistic as a
    buy/hold/sell call, which the probe says it is not.
    """
    tree = _tree(tmp_path)

    path, payload = jev.judge_tree(tree, key="sk-or-v1-test", decider=jev.DECIDERS[2])

    assert path == tree / jev.NOUL_VERDICT_FILENAME
    assert "scores" in payload
    assert "ratings" not in payload


def test_the_noul_recipe_is_best_effort_too(monkeypatch, tmp_path):
    tree = _tree(tmp_path)
    monkeypatch.setattr(jev, "resolve_key", lambda *a, **k: "sk-or-v1-test")
    monkeypatch.setattr(jev, "post_json", _Recorder(status=400, body="expected object"))

    batch._batch_noul_decider(tree)   # must not raise

    payload = json.loads((tree / jev.NOUL_VERDICT_FILENAME).read_text(encoding="utf-8"))
    assert payload["failures"] == 4
    assert payload["scores"] == {}


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
