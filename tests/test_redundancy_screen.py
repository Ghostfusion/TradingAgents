"""X2: the redundancy screen over the engine's own components.

A double-selection LASSO over candidate components against a control set, with
an in-house L1 solver, a selection window disjoint from the evaluation window,
and one refusal-ledger row per dropped component. Offline by construction: a
scheduled script consumes it, never the in-run surface.

Mutation to prove the failing-first test can fail: delete the ``_log_dropped``
call at the end of ``alpha_zoo.redundancy_screen`` (the write for dropped
components); ``test_every_dropped_component_is_logged`` then has no ledger row
for the dropped component and goes red.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tradingagents.strategies.alpha_zoo import redundancy_screen
from tradingagents.strategies.refusal_ledger import rows

pytestmark = pytest.mark.timeout(60)

REPO = Path(__file__).resolve().parents[1]


def _pane() -> tuple[dict, dict, list]:
    """A deterministic pane: two informative components, one pure noise.

    ``A`` follows the target everywhere, ``B`` only over ``[0, 200)``, ``C`` is
    noise; the controls carry no signal, so a candidate's survival is its own.
    """
    rng = np.random.default_rng(11)
    n = 300
    latent = rng.standard_normal(n)
    target = (latent + rng.standard_normal(n) * 0.5).tolist()
    candidates = {
        "A": (np.asarray(target) + rng.standard_normal(n) * 0.3).tolist(),
        "B": np.concatenate([
            np.asarray(target)[:200] + rng.standard_normal(200) * 0.4,
            rng.standard_normal(100) * 3.0,
        ]).tolist(),
        "C": rng.standard_normal(n).tolist(),
    }
    controls = {
        "k1": rng.standard_normal(n).tolist(),
        "k2": rng.standard_normal(n).tolist(),
    }
    return candidates, controls, target


def _ledger_on(monkeypatch) -> None:
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"enable_refusal_ledger": True},
    )


def test_every_dropped_component_is_logged(monkeypatch, tmp_path):
    """Every dropped component has a refusal-ledger row naming this screen and
    the window it was dropped over, and kept/dropped partition the candidates."""
    _ledger_on(monkeypatch)
    candidates, controls, target = _pane()
    result = redundancy_screen(
        candidates, controls, target,
        selection_window=(0, 100), evaluation_window=(100, 200),
        results_dir=str(tmp_path),
    )

    assert sorted(result["kept"] + result["dropped"]) == sorted(candidates)
    assert len(set(result["kept"]) & set(result["dropped"])) == 0
    assert len(result["kept"]) + len(result["dropped"]) == len(candidates)
    assert result["dropped"], "the noise component must not survive the screen"

    logged = {(r.get("component"), r.get("screen"), r.get("window")) for r in rows(str(tmp_path))}
    for name in result["dropped"]:
        assert (name, "redundancy_screen", result["window"]) in logged, (
            f"dropped component {name!r} has no ledger row naming the screen "
            f"and window {result['window']!r}"
        )
    assert {r.get("gate") for r in rows(str(tmp_path))} == {"redundancy_screen"}


def test_a_shifted_window_reports_the_survivor_list_difference(monkeypatch, tmp_path):
    """The doc caveat is that a survivor list which changes every refit is not a
    finding, so a second run on a shifted window must report the difference."""
    _ledger_on(monkeypatch)
    candidates, controls, target = _pane()
    first = redundancy_screen(
        candidates, controls, target,
        selection_window=(0, 100), evaluation_window=(100, 200),
        results_dir=str(tmp_path),
    )
    second = redundancy_screen(
        candidates, controls, target,
        selection_window=(200, 300), evaluation_window=(0, 100),
        results_dir=str(tmp_path),
    )
    assert first["window"] != second["window"]
    assert "A" in first["kept"] and "A" in second["kept"]
    assert "B" in first["kept"] and "B" not in second["kept"]
    assert set(first["kept"]) ^ set(second["kept"]) == {"B"}


def test_the_screen_is_deterministic(tmp_path):
    """Fixed seed, no wall clock, no network: two runs on the same pane and
    windows give the same survivor list and the same coefficients."""
    candidates, controls, target = _pane()
    runs = [
        redundancy_screen(candidates, controls, target,
                          selection_window=(0, 100), evaluation_window=(100, 200),
                          results_dir=str(tmp_path))
        for _ in range(2)
    ]
    assert runs[0]["kept"] == runs[1]["kept"]
    assert runs[0]["coefficients"] == runs[1]["coefficients"]


def test_selection_window_must_not_overlap_evaluation_window():
    """A selection that overlaps its evaluation is in-sample and unreadable."""
    candidates, controls, target = _pane()
    with pytest.raises(ValueError, match="overlaps"):
        redundancy_screen(
            candidates, controls, target,
            selection_window=(0, 150), evaluation_window=(100, 200),
        )


def test_a_window_too_short_to_measure_is_unavailable_not_zero(tmp_path):
    candidates, controls, target = _pane()
    result = redundancy_screen(
        candidates, controls, target,
        selection_window=(0, 4), evaluation_window=(5, 9),
        results_dir=str(tmp_path),
    )
    assert result["unavailable"]
    assert result["kept"] == []
    assert sorted(result["dropped"]) == sorted(candidates)
    assert all(v["selection"] is None for v in result["coefficients"].values())


def test_the_screen_is_reachable_only_offline():
    """Ground rule 8: no in-run surface may reference the screen."""
    offenders = []
    for path in (REPO / "tradingagents").rglob("*.py"):
        if path.name == "alpha_zoo.py":
            continue
        if "redundancy_screen" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(path.relative_to(REPO).as_posix())
    assert offenders == [], f"redundancy_screen reached an in-run surface: {offenders}"
    # ...and it is reachable from the offline scheduled script (rule 7 wiring).
    script = (REPO / "scripts" / "redundancy_screen.py").read_text(encoding="utf-8")
    assert "redundancy_screen" in script


def test_the_scheduled_script_runs_the_screen(tmp_path, capsys):
    """The wiring consumer: the script reads a pane, runs the screen and prints
    the survivor list."""
    import scripts.redundancy_screen as script

    candidates, controls, target = _pane()
    pane = {
        "candidates": candidates,
        "controls": controls,
        "target": target,
        "selection_window": [0, 100],
        "evaluation_window": [100, 200],
    }
    src = tmp_path / "pane.json"
    src.write_text(json.dumps(pane), encoding="utf-8")
    assert script.main(["--input", str(src), "--results-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "kept" in out and "A" in out and "dropped" in out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
