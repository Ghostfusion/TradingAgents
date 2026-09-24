"""H11: autocorrelation-aware intervals, and the information gap.

Two axes, both off by default behind ``enable_bootstrap_intervals``:

- an interval has to be computed *as if* the observations were independent for
  its nominal level to mean anything, so ``block_bootstrap_interval`` chooses a
  block length from the series' own ACF decay (checked against an ADF
  stationarity test) and reports it beside the bounds, with ``iid_interval``
  public as the baseline the block arm has to beat;
- a band can be wide and still carry nothing, so ``information_gap`` scores the
  pooled scale against a conditional-scale alternative on the same window.

The measured numbers these thresholds rest on are in the H11 block of
``strategies/conformal.py``: at n=250 and a nominal 0.90, an AR(1) with
``rho = 0.8`` covers 0.45 with the IID interval and 0.75 with the block
interval. The block arm does **not** restore nominal coverage there, which is
why the residual is asserted as a floor rather than as 0.90.
"""

from __future__ import annotations

import math
import random

import pytest

from tradingagents.strategies.conformal import (
    ADF_CRIT,
    GAP_THRESHOLD,
    INTERVAL_MIN_N,
    adf_t,
    block_bootstrap_interval,
    block_length,
    iid_interval,
    information_gap,
    rolling_band,
)


def _ar1(rho: float, n: int, seed: int) -> list[float]:
    """A unit-variance AR(1) with mean zero, so the true mean is known."""
    rng = random.Random(seed)
    out = [0.0] * n
    for i in range(1, n):
        out[i] = rho * out[i - 1] + rng.gauss(0.0, 1.0) * math.sqrt(1.0 - rho * rho)
    return out


def _covers(interval: dict | None) -> bool:
    assert interval is not None
    return interval["low"] <= 0.0 <= interval["high"]


def test_block_interval_covers_ar1():
    """The card's named test: on a persistent series the IID interval
    under-covers and the block interval does not.

    Removing the block arm (making ``block_bootstrap_interval`` resample one
    observation at a time) fails this by name.
    """
    n, reps, rho = 250, 40, 0.8
    series = [_ar1(rho, n, seed) for seed in range(reps)]

    iid_hits = sum(_covers(iid_interval(y, alpha=0.1, seed=i))
                   for i, y in enumerate(series))
    blk = [block_bootstrap_interval(y, alpha=0.1, seed=i) for i, y in enumerate(series)]
    blk_hits = sum(_covers(b) for b in blk)

    iid_cov = iid_hits / reps
    blk_cov = blk_hits / reps
    assert iid_cov <= 0.60, f"the IID interval was expected to under-cover, got {iid_cov}"
    assert blk_cov >= 0.65, f"the block interval was expected to recover, got {blk_cov}"
    assert blk_cov - iid_cov >= 0.15, (iid_cov, blk_cov)

    # The block length travels with the interval - it is the dependence
    # assumption, and it is the one thing a reader cannot recover from the width.
    assert all(b["block"] > 1 for b in blk)
    assert all(b["method"] == "moving-block" for b in blk)
    assert all(b["low"] < b["point"] < b["high"] for b in blk)
    assert all(b["n"] == n and b["draws"] >= 10 for b in blk)


def test_block_length_is_the_acf_horizon_not_a_constant():
    """An independent series keeps the base length; a persistent one earns a longer one."""
    iid = [random.Random(11).gauss(0.0, 1.0) for _ in range(250)]
    persistent = _ar1(0.8, 250, 5)
    assert block_length(iid) == max(2, round(250 ** (1 / 3)))
    assert block_length(persistent) > block_length(iid)
    # A series whose ACF does not decay inside the window is not given a block
    # longer than a quarter of it, and a short input is not given a long one.
    assert block_length(list(range(250))) <= 62
    assert block_length([1.0, 2.0, 3.0]) == 1
    assert block_length([]) == 1


def test_adf_statistic_separates_a_level_from_a_stationary_series():
    """The ADF check is what decides whether the ACF horizon is usable."""
    stationary = _ar1(0.5, 400, 7)
    assert adf_t(stationary) < ADF_CRIT
    assert adf_t([1.0] * 50) is None
    assert adf_t([1.0, 2.0]) is None


def test_information_gap_separates_an_uninformative_band():
    """A band that covers by being useless is not the same object as a tight one.

    Deterministic, no sampling: the same prediction spread, one with a constant
    residual scale and one whose residual scale tracks the prediction. The
    pooled band cannot tell them apart; the gap does.
    """
    preds = [-2.0 + 4.0 * i / 99 for i in range(100)]

    flat = [(p, p + (0.5 if i % 2 == 0 else -0.5)) for i, p in enumerate(preds)]
    informative = information_gap(flat)
    assert informative is not None
    assert informative["gap_nats"] < GAP_THRESHOLD
    assert informative["verdict"] == "informative"

    scaled = [(p, p + (0.1 + 0.5 * abs(p)) * (1 if i % 2 == 0 else -1))
              for i, p in enumerate(preds)]
    uninformative = information_gap(scaled)
    assert uninformative is not None
    assert uninformative["gap_nats"] > 0.10
    assert uninformative["verdict"] == "uninformative"
    assert uninformative["gap_nats"] > informative["gap_nats"] + 0.05


def test_both_axes_degrade_below_the_floor():
    """Below the floor every read is ``None`` - never a number, never zero."""
    short = [0.1, 0.2, 0.3]
    assert iid_interval(short) is None
    assert block_bootstrap_interval(short) is None
    assert information_gap([(1.0, 1.0)] * 3) is None
    assert information_gap([(1.0, 1.0)] * INTERVAL_MIN_N) is None  # zero variance
    assert block_bootstrap_interval([float("nan")] * 50) is None
    assert information_gap([]) is None


def test_rolling_band_gains_the_gap_only_when_the_gate_is_on(monkeypatch):
    """The second axis is additive and gated: gate-off is the dict it always was."""
    pairs = [(float(i), float(i) + (0.4 if i % 2 else -0.4)) for i in range(200)]

    monkeypatch.setattr("tradingagents.dataflows.config.get_config",
                        lambda: {"enable_bootstrap_intervals": False})
    off = rolling_band(pairs, window=150, alpha=0.1, min_n=40)
    assert "information_gap" not in off

    monkeypatch.setattr("tradingagents.dataflows.config.get_config",
                        lambda: {"enable_bootstrap_intervals": True})
    on = rolling_band(pairs, window=150, alpha=0.1, min_n=40)
    assert set(on) == set(off) | {"information_gap"}
    assert on["information_gap"] is not None
    assert on["information_gap"]["verdict"] in {"informative", "uninformative"}
    for key in off:
        if key != "basis":
            assert on[key] == off[key], key
    assert off["basis"] in on["basis"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
