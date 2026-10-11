"""G5 unit tests: config-gate verdict (offline deterministic)."""

import pytest

from scripts.evaluate_config_gate import gate_verdict

pytestmark = pytest.mark.timeout(120)


def test_too_few_samples_returns_none():
    v = gate_verdict([0.01, -0.02, 0.005])
    assert v["ok"] is None
    assert "too few" in v["reason"]


def test_consistent_edge_passes():
    # strong, stable daily returns -> walk-forward should pass (no PBO)
    returns = [0.002 if i % 2 else 0.001 for i in range(200)]
    v = gate_verdict(returns, train_len=60, test_len=20)
    assert v["ok"] is True
    assert v["reason"] == "pass"


def test_verdict_shape():
    returns = [0.001, -0.002, 0.003, 0.0, 0.002, -0.001] * 30
    v = gate_verdict(returns, train_len=60, test_len=20)
    assert set(v) >= {"ok", "reason", "in_best", "oos_best", "deflated_sharpe"}


def test_the_deflation_reads_the_trial_ledger_when_the_gate_is_on(tmp_path, monkeypatch):
    """With ``enable_trial_ledger`` on, N and V come from the recorded rows.

    That is the whole point of D2: the deflation is indexed to the search the
    ledger actually holds, not to a number the caller asserted. With the gate
    off the caller's count is all there is, and the record says which it used.
    """
    from tradingagents.dataflows import config as cfg
    from tradingagents.strategies.evaluate import sharpe
    from tradingagents.strategies.trial_ledger import record, returns_sha

    returns = [0.002 if i % 2 else 0.001 for i in range(200)]

    monkeypatch.setattr(cfg, "get_config", lambda: {"enable_trial_ledger": True})
    for i, scale in enumerate((0.001, -0.002, 0.003)):
        series = [scale * ((j % 7) - 3) for j in range(120)]
        record(f"cand{i}", "w", returns_sha(series), sharpe(series), "2026-01-01",
               results_dir=str(tmp_path))
    on = gate_verdict(returns, train_len=60, test_len=20, ledger_dir=str(tmp_path))
    assert on["n_trials"] == 3
    assert on["dispersion"] == "measured"
    assert on["deflated_sharpe_ratio"] is not None

    monkeypatch.setattr(cfg, "get_config", lambda: {})
    off = gate_verdict(returns, train_len=60, test_len=20)
    assert off["n_trials"] == 20  # the caller-supplied fallback
    assert "off" in off["dispersion"]


def test_an_unmeasured_ledger_never_reads_as_zero_dispersion(tmp_path, monkeypatch):
    """One row is not a dispersion: the verdict falls back and names the reason."""
    from tradingagents.dataflows import config as cfg
    from tradingagents.strategies.evaluate import sharpe
    from tradingagents.strategies.trial_ledger import record, returns_sha

    returns = [0.002 if i % 2 else 0.001 for i in range(200)]
    monkeypatch.setattr(cfg, "get_config", lambda: {"enable_trial_ledger": True})
    series = [0.001 * ((j % 7) - 3) for j in range(120)]
    record("only", "w", returns_sha(series), sharpe(series), "2026-01-01",
           results_dir=str(tmp_path))
    v = gate_verdict(returns, train_len=60, test_len=20, ledger_dir=str(tmp_path))
    assert v["n_trials"] == 20
    assert "ledger unavailable" in v["dispersion"]


def test_the_verdict_carries_the_minimum_track_record():
    """E2: the length the record would need, beside the numbers it is judged by.

    Per-observation units (Bailey & Lopez de Prado's own convention), so the
    years conversion is the module's ``periods_per_year`` and nothing else.
    """
    returns = [0.002 if i % 2 else 0.001 for i in range(200)]
    v = gate_verdict(returns, train_len=60, test_len=20)
    mintrl = v["min_track_record"]
    assert mintrl is not None
    assert mintrl["n"] == 200 and mintrl["benchmark_sharpe"] == 0.0
    assert mintrl["min_track_record"] > 0
    assert mintrl["min_track_record_years"] == pytest.approx(mintrl["min_track_record"] / 252.0)


def test_the_cost_grid_reports_the_crossing():
    """E5's grid form: the same series is judged at each rung, so a conclusion
    that flips across plausible costs reads as a crossing."""
    from scripts.evaluate_config_gate import cost_grid_verdicts

    returns = [0.002 if i % 2 else 0.001 for i in range(200)]  # mean 0.0015
    rows = cost_grid_verdicts(returns, costs=[0.0, 0.001, 0.002], train_len=60, test_len=20)
    assert [r["round_trip_cost"] for r in rows] == [0.0, 0.001, 0.002]
    assert [r["ok"] for r in rows] == [True, True, None]
    assert rows[2]["reason"] == "gross edge below round-trip cost"
    assert rows[2]["bps"] == pytest.approx(20.0)
    assert rows[0]["gross_edge"] == pytest.approx(0.0015, abs=1e-6)


def test_a_grid_rung_is_the_same_gate_as_the_single_rung():
    """The kwargs pass through, so the grid cannot test a different gate: the
    PBO refusal rides along with the cost sweep."""
    from scripts.evaluate_config_gate import cost_grid_verdicts

    returns = [0.002 if i % 2 else 0.001 for i in range(20)]
    fluke = [[1.0] * 10 + [-1.0] * 10, [0.0] * 20]
    rows = cost_grid_verdicts(
        returns, costs=[0.0], train_len=4, test_len=2, candidate_matrix=fluke
    )
    assert rows[0]["reason"] == "PBO"
