"""Phase 1 unit tests: regime features + rule labels + the filtered HMM (offline).

The walk-forward HMM is pure NumPy (the same choice ``garch11_fit`` makes), so
it is covered here rather than skipped for a missing optional dependency.
"""

import numpy as np

from tradingagents.strategies.regime import (
    CHOP_TREND_THRESHOLD,
    choppiness,
    hmm_filtered_regime,
    hmm_regime,
    realized_vol,
    regime_label,
    trend_strength,
    vol_percentile,
)


def _uptrend(n=260, base=100.0, step=0.3):
    return [base + step * i for i in range(n)]


def test_trend_strength_positive_on_uptrend():
    t = trend_strength(_uptrend())
    assert t > 0


def test_trend_strength_negative_on_downtrend():
    t = trend_strength(_uptrend(step=-0.3))
    assert t < 0


def test_realized_vol_positive_and_finite():
    v = realized_vol(_uptrend())
    assert v >= 0


def test_vol_percentile_bounds():
    history = [_uptrend(base=b, step=0.1) for b in range(5)]
    pct = vol_percentile(history, current_window=21)
    assert 0.0 <= pct <= 1.0


def test_rule_labels():
    assert regime_label(0.9, 0.05, 0.1) == "high_vol"
    assert regime_label(0.1, 0.05, 0.1).startswith("bull")
    assert regime_label(0.1, -0.05, 0.1).startswith("bear")
    assert regime_label(0.5, 0.0, 90.0) == "neutral"  # CHOP scale 0-100


def test_choppiness_close_only_is_on_the_same_0_100_scale():
    """Close-only input now uses 100*(1 - efficiency ratio): the SAME 0-100
    scale and direction as the OHLC branch. It used to return a 0-1 dispersion
    (~0.01), which is why `overlays` passed a literal 0.4 and the label's
    choppiness branch could never fire."""
    c = choppiness(_uptrend())
    assert c is not None
    assert 0.0 <= c <= 100.0
    # a monotone trend is maximally efficient -> LOW choppiness
    assert c < CHOP_TREND_THRESHOLD
    # a flat tape makes no directional progress -> maximally choppy
    assert choppiness([100.0] * 40) == 100.0


def test_choppiness_is_none_when_unmeasurable():
    """Neither branch can be measured -> None, never a fabricated neutral."""
    assert choppiness([]) is None
    assert choppiness([100.0, 101.0, 102.0]) is None


def test_regime_label_moves_with_the_trend_on_the_default_path():
    """Regression for the dead chop branch: with vol_pct in the middle band
    (the common case) the label used to be `neutral` whatever the trend was,
    because overlays passed a literal chop of 0.4 against a 0.30 default."""
    from tradingagents.strategies.overlays import build_strategy_overlays

    cfg = {"enable_strategy_overlays": True}
    up = build_strategy_overlays(cfg, _trend_closes())
    down = build_strategy_overlays(cfg, _trend_closes(step=-0.05))
    assert up is not None and down is not None
    assert up["regime"] != down["regime"]
    assert up["regime"] == "bull" and down["regime"] == "bear"


def test_chop_threshold_sits_on_the_producers_own_scale():
    """The threshold must be comparable with what `choppiness` returns: the
    canonical branch is 0-100, so the trending/ranging split is 30. The other
    caller passed a literal 0.4 against a 0.30 default, which made the branch
    unreachable; this pins the contract in both directions."""
    highs = [100.0 + 1.0 * i for i in range(30)]
    lows = [99.0 + 1.0 * i for i in range(30)]
    closes = [99.5 + 1.0 * i for i in range(30)]
    c = choppiness(closes, highs=highs, lows=lows, window=14)
    assert c is not None and c < CHOP_TREND_THRESHOLD
    # a measurably trending tape fires the branch, in the direction of the trend
    assert regime_label(0.5, 0.05, c) == "bull"
    assert regime_label(0.5, -0.05, c) == "bear"
    # a ranging tape does not
    assert regime_label(0.5, 0.05, 70.0) == "neutral"
    # and an unmeasurable one does not assert a trend either
    assert regime_label(0.5, 0.05, None) == "neutral"


def test_choppiness_ohlc_trend_is_low():
    """Canonical CHOP (0-100): a monotone uptrend is LOW CHOP (trending),
    a tight range-highs/lows series is HIGH CHOP (ranging)."""
    highs = [100.0 + 1.0 * i for i in range(30)]
    lows = [99.0 + 1.0 * i for i in range(30)]
    closes = [99.5 + 1.0 * i for i in range(30)]
    c = choppiness(closes, highs=highs, lows=lows, window=14)
    assert 0.0 <= c <= 100.0
    assert c < 40.0  # monotone trend -> low CHOP (not the old 0-1 std)
    # a wide, tight-range oscillation (noisy but bounded) reads high CHOP-ish
    ch = [100.0 + (10.0 if i % 2 else -10.0) for i in range(30)]
    lh = [95.0 + (10.0 if i % 2 else -10.0) for i in range(30)]
    ll = [90.0 + (10.0 if i % 2 else -10.0) for i in range(30)]
    c2 = choppiness(ch, highs=lh, lows=ll, window=14)
    assert c2 > c

def _trend_closes(n=260, base=100.0, step=0.05):
    """Monotone uptrend close series (low vol, above SMA200)."""
    return [base + step * i for i in range(n)]


def test_regime_market_stress_blocks_on_high_index_vol():
    # stock series calm, index series extremely volatile -> market_stress
    from tradingagents.strategies.regime import regime_gate_read
    calm = _trend_closes()
    # volatile index: alternate +/- big moves
    idx = []
    v = 100.0
    for i in range(260):
        v += (25.0 if i % 2 == 0 else -25.0)
        idx.append(v)
    rg = regime_gate_read(calm, cfg={"market_stress_vol_cap": 0.8}, index_closes=idx)
    assert rg["market_stress"] is True
    assert rg["pass"] is False
    assert any("market stress" in r for r in rg["reasons"])


def test_regime_market_stress_off_without_index():
    # no index series -> market_stress False, pass unaffected
    from tradingagents.strategies.regime import regime_gate_read
    calm = _trend_closes()
    rg = regime_gate_read(calm, cfg={})
    assert rg["market_stress"] is False      # default leg (no index -> False)
    assert rg["pass"] is True


def test_regime_market_stress_index_returns_fields():
    from tradingagents.strategies.regime import regime_gate_read
    calm = _trend_closes()
    rg = regime_gate_read(calm, cfg={}, index_closes=calm)
    assert "index_vol_pct" in rg and "index_fast_downtrend" in rg
    assert "market_stress" in rg


def test_regime_gate_reports_an_unsupplied_catalyst_axis_as_unmeasured():
    """D-11: `catalyst_window` is tri-state, and `None` is not `False`.

    `None` means the caller supplied no event fact, so the axis must be reported
    **unmeasured** - never coerced to `False`, which asserts a measurement nobody
    made. That coercion is what the compiled context did, and the model then
    quoted `catalyst_window=False` back as fact (AMKR 2026-09-17).
    """
    from tradingagents.strategies.regime import regime_gate_read
    calm = _trend_closes()

    unsupplied = regime_gate_read(calm, cfg={})
    assert unsupplied["catalyst_window"] is None
    assert unsupplied["pass"] is True  # no fact -> no veto either
    assert not any("no catalyst" in r for r in unsupplied["reasons"])
    assert any("not measured" in r for r in unsupplied["reasons"])

    # an explicit measured answer still reports itself, both ways
    measured_clear = regime_gate_read(calm, cfg={}, catalyst_window=False)
    assert measured_clear["catalyst_window"] is False
    assert any("no catalyst" in r for r in measured_clear["reasons"])

    measured_open = regime_gate_read(calm, cfg={}, catalyst_window=True)
    assert measured_open["catalyst_window"] is True
    assert measured_open["pass"] is False
    assert measured_open["verdict"] == "catalyst-window"
    assert any("catalyst window open" in r for r in measured_open["reasons"])


def test_the_compiled_context_never_asserts_a_catalyst_measurement():
    """D-11 regression, at the defect site.

    `_compiled_decision_context` is compiled BEFORE `graph.invoke`, so it holds
    no event fact. It used to derive one from `strategy_overlays.catalyst`, which
    the overlay only stamps AFTER the graph (`trading_graph.py:686`) - so the read
    was always `None` and the line asserted `catalyst_window=False`. The axis must
    be named unmeasured, and the overlay artifact must not be consulted even when
    the state happens to carry it.
    """
    import types

    from tradingagents.graph.trading_graph import TradingAgentsGraph

    closes = _trend_closes(n=320)
    stub = types.SimpleNamespace(
        config={"data_cache_dir": "C:/nonexistent-cache"},
        _try_fetch_closes=lambda ticker, days=320: closes,
    )

    def _gate_line(state):
        ctx = TradingAgentsGraph._compiled_decision_context(stub, "AAPL", state)
        return next(
            ln for ln in ctx.splitlines() if ln.startswith("Computed regime gate")
        )

    # the production shape: the pre-graph state carries no overlay at all
    production = _gate_line({})
    assert "catalyst_window=unavailable_pre_graph" in production
    assert "catalyst_window=False" not in production
    assert "no catalyst" not in production

    # a post-graph overlay snapshot must not be consumed even when present
    with_overlay = _gate_line(
        {
            "strategy_overlays": {
                "catalyst": {"verdict": "earnings-window", "scale": 0.5}
            }
        }
    )
    assert "catalyst_window=unavailable_pre_graph" in with_overlay
    assert "catalyst_window=True" not in with_overlay


# --- walk-forward filtered HMM (pure NumPy, no optional dependency) ---


def _two_regime_closes(n_up=150, n_down=150, seed=5):
    """An up-regime (positive drift, low vol) then a down-regime (negative drift,
    high vol): the simplest series whose regime the filter must recover."""
    rng = np.random.default_rng(seed)
    r = np.concatenate(
        [
            rng.normal(0.0012, 0.006, n_up),
            rng.normal(-0.0018, 0.020, n_down),
        ]
    )
    return [100.0 * float(v) for v in np.exp(np.cumsum(r))]


def test_the_filtered_probability_does_not_change_when_future_bars_arrive():
    """THE property that separates a filter from a smoother.

    A filtered probability is ``P(S_t | x_1:t)``, so appending bars AFTER ``t``
    must leave every earlier row identical. A smoothed posterior
    (``hmmlearn.predict_proba`` runs the backward pass too) changes instead -
    which is why this runs the forward recursion itself.
    """
    short = _two_regime_closes(n_down=150)
    long = _two_regime_closes(n_down=200)
    a = hmm_filtered_regime(short, short, short, short, n_states=2)
    b = hmm_filtered_regime(long, long, long, long, n_states=2)
    assert a is not None and b is not None
    assert a["n"] == len(short)  # bar-aligned to the closes it was given
    compared = 0
    for t in range(a["first_index"], a["n"]):
        ra, rb = a["probs"][t], b["probs"][t]
        if ra is None or rb is None:
            continue
        assert ra == rb, f"bar {t} changed when 50 future bars were appended"
        compared += 1
    assert compared > 10, "too few overlapping bars to prove anything"
    # the rows before the first filtered read are a named gap, not zeros
    assert all(p is None for p in a["probs"][: a["first_index"]])


def test_the_filter_labels_a_down_ending_series_as_bear():
    closes = _two_regime_closes()
    res = hmm_filtered_regime(closes, closes, closes, closes, n_states=2)
    assert res is not None
    assert res["last"]["label"] == "bear"
    # canonical order: state 0 carries the higher mean log return
    means = [m[0] for m in res["params"]["means"]]
    assert means[0] > means[1]
    # ...and the regime it ended in is the high-volatility one
    vols = res["params"]["vol_means"]
    assert vols[res["last"]["state"]] == max(vols)
    # every measured bar carries a full probability vector
    for row in res["probs"][res["first_index"] :]:
        assert row is not None
        assert abs(sum(row) - 1.0) < 1e-6


def test_the_filter_is_deterministic():
    closes = _two_regime_closes()
    a = hmm_filtered_regime(closes, closes, closes, closes, n_states=2)
    b = hmm_filtered_regime(closes, closes, closes, closes, n_states=2)
    assert a is not None and b is not None
    assert a["probs"] == b["probs"]
    assert a["last"] == b["last"]


def test_the_filter_reports_a_named_gap_when_the_history_is_too_short():
    """No fit on a series the walk-forward cannot train on - None, never a label
    from a model that saw three points."""
    flat = [100.0] * 30
    assert hmm_filtered_regime(flat, flat, flat, flat) is None
    assert hmm_filtered_regime([], [], [], []) is None


def test_hmm_regime_is_the_label_view_of_the_same_filter():
    """One HMM producer, two entry points: the label cannot disagree with the
    probabilities because it is read off them."""
    assert hmm_regime([100.0] * 30, 2) == "unknown"
    assert hmm_regime([], 2) == "unknown"
    assert hmm_regime(_two_regime_closes(), 2) == "bear"
