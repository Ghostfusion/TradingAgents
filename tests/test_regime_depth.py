"""The regime depth reads (REG-1/2/3/4/10/11/12/16/17), offline and deterministic.

Every fixture is synthetic and every producer is pure: no vendor call, no
network. Each producer gets a measured case and a refusal case, and the
percentile convention REG-3 fixes (strictly-below rank, floor 0) is pinned
directly, including the floor the self-inclusive ``<=`` used to impose.
"""

from __future__ import annotations

import math
import random

import pytest

from tradingagents.strategies.overlays import build_strategy_overlays
from tradingagents.strategies.regime import (
    hmm_transition_read,
    index_trend,
    index_trend_reads,
    market_stress_composite,
    regime_state_metadata,
    relative_vol_ratio,
    upside_downside_beta,
    vol_percentile,
    vol_percentile_of,
    vol_percentile_read,
)

pytestmark = pytest.mark.timeout(180)


def _additive(n: int, *, step: float, base: float = 100.0) -> list[float]:
    """Additive ramp: vol rises with the drift, so the latest window is extreme."""
    return [base + step * i for i in range(n)]


def _geometric(n: int, *, sigma: float, seed: int = 11) -> list[float]:
    """Deterministic noisy geometric tape (fixed seed, so the rank is stable)."""
    rng = random.Random(seed)
    out = [100.0]
    for _ in range(n - 1):
        out.append(out[-1] * math.exp(rng.gauss(0.0, sigma)))
    return out


def _windows(series: list[float], window: int = 21) -> list[list[float]]:
    """The overlapping windows a caller supplies to the percentile producer."""
    return [series[end - window:end] for end in range(window, len(series) + 1)]


def _tailed(*, tail: str, n: int = 240) -> list[float]:
    """One noisy history with a deterministic 21-bar tail: quiet or violent.

    The reference windows come from the noisy history, so the quiet tail is the
    minimum of the window distribution and the violent tail the maximum.
    """
    hist = _geometric(n, sigma=0.02, seed=1)
    last = hist[-1]
    out = list(hist)
    for i in range(21):
        if tail == "quiet":
            out.append(last * (1.0 + 0.0002 * i))
        else:
            out.append(last * (1.0 + (0.05 if i % 2 else -0.05)))
    return out


# ---------------------------------------------------------------------------
# REG-1 - the measured realized-vol percentile replaces the 3-valued proxy
# ---------------------------------------------------------------------------


def test_a_measured_vol_percentile_separates_a_mid_and_a_high_vol_tape() -> None:
    """REG-1: the label's volatility leg is a measured rank, not three buckets.

    A calm ramp's latest window is the minimum of its own window distribution and
    a volatile ramp's is near the maximum, so the two tapes must carry distinct
    ``vol_pct`` values - the old proxy read 0.5 for both (RegimeScore.md §3
    defect 2).
    """
    cfg = {"enable_strategy_overlays": True}
    calm = build_strategy_overlays(cfg, _tailed(tail="quiet"))
    wild = build_strategy_overlays(cfg, _tailed(tail="violent"))
    assert calm is not None and wild is not None
    assert calm["vol_pct"] is not None and wild["vol_pct"] is not None
    assert calm["vol_pct"] != wild["vol_pct"]
    assert wild["vol_pct"] > calm["vol_pct"]


def test_a_sixty_bar_tape_gets_a_measured_vol_percentile() -> None:
    """The defect REG-1 removes: 60-251-bar histories were pinned at 0.5."""
    ov = build_strategy_overlays(
        {"enable_strategy_overlays": True}, _geometric(60, sigma=0.02)
    )
    assert ov is not None
    assert ov["vol_pct"] is not None
    assert "40 overlapping 21-bar window(s)" in ov["basis"]


def test_the_overlay_is_none_below_sixty_bars_and_on_a_short_tape() -> None:
    """No crash below 60 bars: the overlay is disabled, not fabricated."""
    assert build_strategy_overlays({"enable_strategy_overlays": True}, []) is None
    assert (
        build_strategy_overlays(
            {"enable_strategy_overlays": True}, _geometric(59, sigma=0.02)
        )
        is None
    )


def test_the_basis_records_a_label_move_off_the_legacy_read() -> None:
    """A measured percentile that moves a label is printed, not silent (REG-1)."""
    down = build_strategy_overlays(
        {"enable_strategy_overlays": True}, _additive(260, step=-0.05)
    )
    assert down is not None
    assert down["regime"] == "high_vol"
    assert "the legacy 3-bucket read 0.5" in down["basis"]
    assert "moved the label to high_vol" in down["basis"]


# ---------------------------------------------------------------------------
# REG-2 - the volatility estimator enters the label, not only position_scale
# ---------------------------------------------------------------------------


def test_the_volatility_estimator_moves_the_label() -> None:
    """REG-2: the ewma override is ranked on the label's own percentile scale.

    A tape whose realized percentile and whose ewma vol sit on opposite sides of
    the 0.75 band must not carry the same label under the two estimators; if it
    does, the estimator is still scale-only and this test says so.
    """
    series = _geometric(300, sigma=0.02, seed=19)
    cfg = {"enable_strategy_overlays": True}
    close = build_strategy_overlays({**cfg, "volatility_estimator": "close"}, series)
    ewma = build_strategy_overlays({**cfg, "volatility_estimator": "ewma"}, series)
    assert close is not None and ewma is not None
    assert "the ewma estimator ranked against" in ewma["basis"]
    # the realized percentile is in the top band and the ewma rank is not: the
    # estimator moves the LABEL, not only position_scale (REG-2)
    assert close["regime"] == "high_vol" and close["vol_pct"] >= 0.75
    assert ewma["regime"] != close["regime"]
    assert ewma["vol_pct"] < 0.75
    # position_scale still uses the override, and stays a valid scale
    assert 0.0 < ewma["position_scale"] <= 1.5


# ---------------------------------------------------------------------------
# REG-3 - the strictly-below rank, floor 0
# ---------------------------------------------------------------------------


def test_the_printed_vol_percentile_falls_below_the_old_floor() -> None:
    """REG-3: a 15-window caller could never print below 1/15 under ``<=``."""
    rising = [[100.0 + 0.5 * i for i in range(30)] for _ in range(14)]
    flat = [100.0 + 0.0001 * i for i in range(30)]
    pct = vol_percentile(rising + [flat])
    assert pct == 0.0
    assert pct < 1.0 / 15.0


def test_vol_percentile_refuses_a_short_or_flat_history() -> None:
    """Two refusal reasons, both ``None`` - never the old fabricated 0.5."""
    assert vol_percentile([[100.0 + i for i in range(30)]]) is None
    flat = [[100.0 + 0.01 * i for i in range(30)] for _ in range(5)]
    assert vol_percentile(flat) is None
    read = vol_percentile_read(flat)
    assert read["percentile"] is None
    assert "no dispersion" in read["reason"]
    assert vol_percentile_read(flat[:1])["reason"].startswith("1 window(s)")


# ---------------------------------------------------------------------------
# vol_percentile_of - the estimator's vol on the window scale
# ---------------------------------------------------------------------------


def test_vol_percentile_of_ranks_one_value_against_the_windows() -> None:
    wins = _windows(_geometric(200, sigma=0.02))
    high = vol_percentile_of(10.0, wins)
    low = vol_percentile_of(1e-9, wins)
    assert high == 1.0
    assert low == 0.0
    assert vol_percentile_of(None, wins) is None
    assert vol_percentile_of(0.2, wins[:1]) is None
    flat = [[100.0] * 30 for _ in range(3)]
    assert vol_percentile_of(0.2, flat) is None


# ---------------------------------------------------------------------------
# REG-4 - index trend, one read per caller-supplied series
# ---------------------------------------------------------------------------


def test_index_trend_reads_the_series_it_is_given() -> None:
    up = index_trend(_additive(260, step=0.05), label="SPY")
    down = index_trend(_additive(260, step=-0.05), label="QQQ")
    assert up["trend"] > 0 and up["above_sma"] is True and up["sma_window"] == 200
    assert down["trend"] < 0 and down["above_sma"] is False
    assert up["label"] == "SPY" and down["label"] == "QQQ"


def test_index_trend_refuses_a_short_series() -> None:
    read = index_trend(_additive(30, step=0.05), label="IWM")
    assert read["trend"] is None and read["above_sma"] is None
    assert "30 bar(s)" in read["withheld"]


def test_index_trend_reads_prints_three_separate_reads() -> None:
    out = index_trend_reads(
        {
            "SPY": _additive(260, step=0.05),
            "QQQ": _additive(260, step=-0.05),
            "IWM": _additive(40, step=0.05),
        }
    )
    assert sorted(out["reads"]) == ["IWM", "QQQ", "SPY"]
    assert out["measured"] == ["SPY", "QQQ"]
    assert "IWM" in out["withheld"]
    assert "2 of 3" in out["basis"]


# ---------------------------------------------------------------------------
# REG-10 - relative volatility
# ---------------------------------------------------------------------------


def test_relative_vol_ratio_is_above_one_when_a_is_noisier() -> None:
    out = relative_vol_ratio(
        _geometric(200, sigma=0.03), _geometric(200, sigma=0.01)
    )
    assert out["withheld"] is None
    assert out["ratio"] > 1.0
    assert out["a_vol"] > out["b_vol"] > 0


def test_relative_vol_ratio_refuses_a_short_leg() -> None:
    out = relative_vol_ratio(_geometric(10, sigma=0.03), _geometric(200, sigma=0.01))
    assert out["ratio"] is None and out["a_vol"] is None
    assert "needed for each" in out["withheld"]


# ---------------------------------------------------------------------------
# REG-11 - upside / downside beta
# ---------------------------------------------------------------------------


def test_upside_downside_beta_splits_by_the_benchmark_sign() -> None:
    """``ret = k * bench`` per side, so each leg's beta is exactly ``k``."""
    bm = [(0.005 + 0.005 * (i % 3)) * (1 if i % 2 == 0 else -1) for i in range(120)]
    ret = [1.5 * b if b > 0 else 3.0 * b for b in bm]
    out = upside_downside_beta(ret, bm)
    assert out["withheld"] is None
    assert abs(out["upside_beta"] - 1.5) < 1e-9
    assert abs(out["downside_beta"] - 3.0) < 1e-9
    assert abs(out["asymmetry"] - 1.5) < 1e-9
    assert out["n_up"] + out["n_down"] == 120


def test_upside_downside_beta_refuses_a_one_sided_benchmark() -> None:
    out = upside_downside_beta([0.01] * 40, [0.01] * 40)
    assert out["downside_beta"] is None and out["upside_beta"] is None
    assert "0 down aligned bar(s)" in out["withheld"]


# ---------------------------------------------------------------------------
# REG-12 - the market-stress composite
# ---------------------------------------------------------------------------


def test_market_stress_composite_is_zero_to_one_hundred() -> None:
    calm = _additive(260, step=0.05)
    rng = random.Random(9)
    stress = [200.0]
    for _ in range(259):
        stress.append(stress[-1] * math.exp(rng.gauss(-0.004, 0.02)))
    calm_out = market_stress_composite(calm, benchmark=calm, volumes=[1e6] * 260)
    stress_out = market_stress_composite(stress, benchmark=stress, volumes=[1e6] * 260)
    assert calm_out["score"] is not None and stress_out["score"] is not None
    assert 0.0 <= calm_out["score"] <= 100.0
    assert 0.0 <= stress_out["score"] <= 100.0
    assert stress_out["score"] > calm_out["score"]
    assert calm_out["measured"] == [
        "correlation",
        "drawdown",
        "illiquidity",
        "volatility",
    ]


def test_market_stress_composite_names_the_legs_it_withheld() -> None:
    out = market_stress_composite(_geometric(200, sigma=0.02))
    assert out["score"] is not None
    assert "correlation" in out["withheld"] and "illiquidity" in out["withheld"]
    assert out["coverage"] == 0.5
    assert market_stress_composite([1.0])["score"] is None
    assert market_stress_composite([1.0])["basis"] == (
        "market stress unmeasurable: fewer than 2 closes"
    )


# ---------------------------------------------------------------------------
# REG-16 - HMM transition probability / persistence / duration
# ---------------------------------------------------------------------------


def test_hmm_transition_read_surfaces_the_matrix() -> None:
    out = hmm_transition_read(
        {"params": {"transmat": [[0.9, 0.1], [0.2, 0.8]]}, "last": {"state": 1}}
    )
    assert out["withheld"] is None
    assert out["state"] == 1 and out["n_states"] == 2
    assert out["persistence"] == 0.8
    assert out["next_state_probs"] == [0.2, 0.8]
    assert abs(out["leave_probability"] - 0.2) < 1e-12
    assert abs(out["expected_duration"][0] - 10.0) < 1e-9


def test_hmm_transition_read_refuses_without_a_matrix() -> None:
    assert hmm_transition_read(None)["persistence"] is None
    assert "no HMM transition matrix" in hmm_transition_read({})["withheld"]
    assert "not square" in hmm_transition_read(
        {"transmat": [[0.5, 0.5, 0.5], [0.5, 0.5]]}
    )["withheld"]


def test_hmm_transition_read_consumes_the_real_producer_shape() -> None:
    """The matrix comes from ``hmm_filtered_regime``'s own ``params.transmat``."""
    from tradingagents.strategies.regime import hmm_filtered_regime

    rng = random.Random(3)
    closes = [100.0]
    for i in range(300):
        drift = 0.001 if i < 200 else -0.002
        closes.append(closes[-1] * math.exp(rng.gauss(drift, 0.01)))
    res = hmm_filtered_regime(closes, closes, closes, closes, n_states=2)
    assert res is not None
    out = hmm_transition_read(res)
    assert out["withheld"] is None
    assert out["n_states"] == 2
    assert 0.0 < out["persistence"] <= 1.0
    assert abs(sum(out["next_state_probs"]) - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# REG-17 - the confidence / state metadata block
# ---------------------------------------------------------------------------


def test_regime_state_metadata_computes_each_named_field() -> None:
    out = regime_state_metadata(
        [[0.5, 0.5], [0.6, 0.4]],
        scores=[50.0, 55.0, 60.0],
        transmat=[[0.9, 0.1], [0.2, 0.8]],
    )
    assert out["withheld"] == {}
    expected_entropy = -(0.6 * math.log(0.6) + 0.4 * math.log(0.4))
    assert abs(out["entropy"] - expected_entropy) < 1e-12
    assert abs(out["entropy_normalized"] - expected_entropy / math.log(2.0)) < 1e-12
    assert out["confidence"] == 0.6
    assert abs(out["stability"] - 0.9) < 1e-12
    assert out["change"] == 5.0 and out["velocity"] == 5.0
    assert out["acceleration"] == 0.0
    assert abs(out["surprise"] - -math.log(0.9)) < 1e-12


def test_regime_state_metadata_refuses_and_names_what_it_withheld() -> None:
    empty = regime_state_metadata([])
    assert empty["entropy"] is None
    assert empty["basis"].startswith("regime state metadata unmeasurable")
    partial = regime_state_metadata([[0.9, 0.1]])
    assert partial["entropy"] is not None
    assert "stability" in partial["withheld"]
    assert "velocity" in partial["withheld"]
    assert "surprise" in partial["withheld"]
    # a field with no input is None, never 0
    assert partial["velocity"] is None
