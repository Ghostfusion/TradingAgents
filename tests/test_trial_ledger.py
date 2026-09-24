"""H1 - trial ledger and dispersion-aware deflation (honest-evaluation gate).

The deflation takes its trial count N and the trials' Sharpe dispersion V from
the ledger rows, never from a caller's assertion; with the gate off nothing
moves, and a deflated number always says which of the two it used.
"""

import math
from statistics import NormalDist

import pytest

from tradingagents.dataflows.config import reset_config, set_config
from tradingagents.strategies.alpha_zoo import bench_zoo
from tradingagents.strategies.evaluate import (
    deflated_sharpe,
    deflated_sharpe_report,
    sharpe,
)
from tradingagents.strategies.trial_ledger import (
    gate_on,
    record,
    returns_sha,
    trial_stats,
)

pytestmark = pytest.mark.timeout(30)

#: The observed series being deflated (the same one for every candidate set).
RETURNS = [0.011, -0.004, 0.007, -0.002, 0.009, 0.001, -0.006, 0.005,
           0.003, -0.001, 0.008, -0.003]
#: Two candidate sets: same size, very different Sharpe dispersion.
TIGHT = (0.40, 0.42, 0.38)
WIDE = (0.10, 0.50, 0.60)


def _seed(tmp_path, sharpes, name):
    """One ledger directory holding one row per evaluated candidate."""
    d = tmp_path / name
    for i, s in enumerate(sharpes):
        record(f"cand{i}", "design", returns_sha([s]), s, "2026-01-02",
               results_dir=str(d))
    return d


def _closed_form(n, v):
    """The card's SR*_0 with g Euler-Mascheroni, independently re-derived."""
    g = 0.5772156649015328606
    nd = NormalDist()
    return math.sqrt(v) * ((1.0 - g) * nd.inv_cdf(1.0 - 1.0 / n)
                           + g * nd.inv_cdf(1.0 - 1.0 / (n * math.e)))


def test_dispersion_changes_deflated_sharpe(tmp_path):
    set_config({"enable_trial_ledger": True})
    try:
        tight_dir = _seed(tmp_path, TIGHT, "tight")
        wide_dir = _seed(tmp_path, WIDE, "wide")
        # N and V are read back FROM the rows, never asserted by the caller.
        tight = trial_stats(results_dir=str(tight_dir))
        wide = trial_stats(results_dir=str(wide_dir))
        assert tight["n_trials"] == wide["n_trials"] == 3
        assert tight["unavailable"] is None and wide["unavailable"] is None
        assert wide["sharpe_dispersion"] > tight["sharpe_dispersion"] > 0.0

        # Same N, different dispersion -> different deflated Sharpe.
        tight_value = deflated_sharpe(RETURNS, n_trials=tight["n_trials"],
                                      sharpe_dispersion=tight["sharpe_dispersion"])
        wide_value = deflated_sharpe(RETURNS, n_trials=wide["n_trials"],
                                     sharpe_dispersion=wide["sharpe_dispersion"])
        assert wide_value != tight_value
        # A wilder search is penalised harder, and never less than the cluster.
        assert wide_value < tight_value < sharpe(RETURNS)

        # With the dispersion supplied the value is the closed form.
        assert abs(tight_value
                   - (sharpe(RETURNS) - _closed_form(3, tight["sharpe_dispersion"]))
                   ) < 1e-12

        # With it absent, today's behaviour bit for bit, tagged as an assumption.
        report = deflated_sharpe_report(RETURNS, n_trials=3)
        assert report["dispersion"] == "assumed"
        assert report["value"] == sharpe(RETURNS) - math.sqrt(2.0 * math.log(3.0))
        assert deflated_sharpe(RETURNS, n_trials=3) == report["value"]
    finally:
        reset_config()


def test_the_gate_off_keeps_the_caller_supplied_behaviour(tmp_path):
    """Default off means nothing moves: no rows written, dispersion ignored."""
    set_config({"enable_trial_ledger": False})
    try:
        assert gate_on() is False
        d = _seed(tmp_path, WIDE, "off")
        stats = trial_stats(results_dir=str(d))
        assert stats["unavailable"]
        assert stats["sharpe_dispersion"] is None
        # A supplied dispersion is ignored, and the report says which one ran.
        assert deflated_sharpe(RETURNS, n_trials=3, sharpe_dispersion=0.07) == (
            sharpe(RETURNS) - math.sqrt(2.0 * math.log(3.0)))
        assert deflated_sharpe_report(RETURNS, n_trials=3,
                                      sharpe_dispersion=0.07)["dispersion"] == "assumed"
    finally:
        reset_config()


def test_bench_zoo_takes_n_from_the_ledger_and_publishes_it(tmp_path):
    """The bench's deflated IC carries the ledger's N, not the caller's count."""
    set_config({"enable_trial_ledger": True})
    try:
        ledger = tmp_path / "ledger"
        recs = [{"close": 100.0 + i * 0.5, "volume": 1000 + i,
                 "date": f"2026-01-{i + 1:02d}"} for i in range(40)]
        out = bench_zoo(["close", "delta(close, 1)"], recs, forward_days=1,
                        n_trials=999, trial_ledger_dir=str(ledger))
        # One immutable row per evaluated candidate.
        assert trial_stats(results_dir=str(ledger))["n_trials"] == 2
        for row in out:
            assert row["deflated_ic_n_trials"] == 2  # the ledger's N, not 999
            assert row["deflated_ic_dispersion"] == "measured"
            assert row["deflated_ic"] is not None
    finally:
        reset_config()
