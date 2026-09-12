"""Q7 - Reality Check / SPA (N7): White's RC and Hansen's SPA over an alpha
universe, plus the ``bench_zoo`` opt-in universe row. Pure and offline: the
bootstrap is driven by an explicit seed, so every number here is fixed."""

import random

import pytest

from tradingagents.strategies.alpha_zoo import bench_zoo
from tradingagents.strategies.evaluate import reality_check, spa

pytestmark = pytest.mark.timeout(60)

# bench_zoo record keys before the Q7 opt-in key was added.
PRE_CHANGE_KEYS = {"expr", "rank_ic", "error", "oos_rank_ic", "wf_ic",
                   "cpcv_overfit", "deflated_ic"}


def _iid(rng, n, sd=0.01):
    return [rng.gauss(0.0, sd) for _ in range(n)]


def _ar1(rng, n, phi, sd=0.01):
    out, x = [], 0.0
    for _ in range(n):
        x = phi * x + rng.gauss(0.0, sd)
        out.append(x)
    return out


def _noise_universe(n=250, k=5, seed=4):
    """I.i.d. pure noise: no candidate beats the noise benchmark."""
    rng = random.Random(seed)
    bench = _iid(rng, n)
    return {f"c{i}": _iid(rng, n) for i in range(k)}, bench


def _ar_universe(n=250, k=6, phi=0.85, seed=2):
    """Autocorrelated pure noise: same lack of edge, persistent series."""
    rng = random.Random(seed)
    bench = _ar1(rng, n, phi)
    return {f"c{i}": _ar1(rng, n, phi) for i in range(k)}, bench


def _superior_universe(n=250, seed=11):
    """One candidate carries a persistent positive drift vs a noise benchmark."""
    rng = random.Random(seed)
    bench = _iid(rng, n)
    cands = {f"noise{i}": _iid(rng, n) for i in range(4)}
    cands["winner"] = [bench[i] + 0.0025 + rng.gauss(0.0, 0.002) for i in range(n)]
    return cands, bench


def _records(n=120, seed=3):
    rng = random.Random(seed)
    price, out = 100.0, []
    for i in range(n):
        price *= 1.0 + rng.gauss(0.0, 0.02)
        out.append({"close": price, "volume": 1000 + i, "open": price * 0.99,
                    "high": price * 1.01, "low": price * 0.98})
    return out


class TestRealityCheck:
    def test_pure_noise_not_detected(self):
        cands, bench = _noise_universe()
        assert reality_check(cands, bench)["p_value"] > 0.05
        assert spa(cands, bench)["p_value"] > 0.05

    def test_superior_candidate_detected(self):
        cands, bench = _superior_universe()
        assert reality_check(cands, bench)["p_value"] < 0.05
        assert spa(cands, bench)["p_value"] < 0.05

    def test_persistent_noise_keeps_block_calibration(self):
        # Persistent (AR1) noise has no edge, but its block structure inflates
        # the sampling spread of the mean; only the stationary (block)
        # bootstrap sees that. An i.i.d. shuffle calls the chance winner
        # significant, so this case fails without block resampling.
        cands, bench = _ar_universe()
        assert reality_check(cands, bench)["p_value"] > 0.05
        assert spa(cands, bench)["p_value"] > 0.05

    def test_reports_window_and_counts(self):
        cands, bench = _noise_universe()
        r = reality_check(cands, bench, block_len=8)
        assert r["block_len"] == 8
        assert r["n_candidates"] == len(cands)
        assert r["n_obs"] == len(bench)
        assert r["basis"]

    def test_spa_shape_adds_recentring(self):
        cands, bench = _superior_universe()
        rc, sp = reality_check(cands, bench), spa(cands, bench)
        assert set(sp) == set(rc) | {"recentring"}
        assert isinstance(sp["recentring"], int)

    def test_spa_recentres_significantly_below_candidate(self):
        # A dominated candidate is recentred to zero in the null; a genuine
        # winner is not, so exactly one of the two is recentred.
        rng = random.Random(21)
        bench = _iid(rng, 250)
        cands = {
            "winner": [bench[i] + 0.003 + rng.gauss(0.0, 0.001) for i in range(250)],
            "dead": [bench[i] - 0.003 + rng.gauss(0.0, 0.001) for i in range(250)],
        }
        assert spa(cands, bench)["recentring"] == 1

    def test_deterministic_from_seed(self):
        cands, bench = _noise_universe()
        first = [reality_check(cands, bench, seed=s)["p_value"] for s in range(5)]
        again = [reality_check(cands, bench, seed=s)["p_value"] for s in range(5)]
        assert first == again          # same seed -> byte-identical result
        assert len(set(first)) > 1     # different seeds -> different draws

    def test_sharpe_metric_is_honoured(self):
        cands, bench = _noise_universe()
        r = reality_check(cands, bench, metric="sharpe")
        assert r is not None and "sharpe" in r["basis"]
        assert reality_check(cands, bench, metric="bogus") is None

    def test_degenerate_inputs_return_none(self):
        cands, bench = _noise_universe()
        assert reality_check({"c0": cands["c0"]}, bench) is None
        assert spa({"c0": cands["c0"]}, bench) is None
        assert reality_check(cands, bench[:3]) is None
        assert spa(cands, bench[:3]) is None
        ragged = {"a": cands["c0"][:100], "b": cands["c1"]}
        assert reality_check(ragged, bench) is None
        assert spa(ragged, bench) is None
        flat = {"a": [1.0] * len(bench), "b": [2.0] * len(bench)}
        assert reality_check(flat, bench) is None
        assert spa(flat, bench) is None

    def test_block_window_boundary(self):
        rng = random.Random(5)
        short_bench = _iid(rng, 9)
        assert reality_check({"a": _iid(rng, 9), "b": _iid(rng, 9)}, short_bench) is None
        exact_bench = _iid(rng, 10)
        exact = {"a": _iid(rng, 10), "b": _iid(rng, 10)}
        assert reality_check(exact, exact_bench) is not None


class TestBenchZooRealityCheck:
    def test_default_path_key_set_unchanged(self):
        rows = bench_zoo(["pct_change(close, 1)", "delta(close, 1)"], _records())
        assert len(rows) == 2
        assert set(rows[0]) == PRE_CHANGE_KEYS
        assert set(rows[1]) == PRE_CHANGE_KEYS

    def test_opt_in_adds_one_universe_key(self):
        rows = bench_zoo(["pct_change(close, 1)", "delta(close, 1)"], _records(),
                         reality_check=True)
        for row in rows:
            assert set(row) == PRE_CHANGE_KEYS | {"reality_check"}
            universe = row["reality_check"]
            assert set(universe) == {"reality_check", "spa"}
            assert universe["reality_check"]["n_candidates"] == 2
            assert "recentring" in universe["spa"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
