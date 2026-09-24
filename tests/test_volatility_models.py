"""V6 - jump-robust daily-bar proxies (implementation_plan_vol_surface_and_vrp.md §V6).

The card's failing-first test is
``test_jump_proxy_separates_one_print_from_diffusion``: it passes on the shipped
code and fails **by name** under the card's mutation - drop the lag-1
cross-product term so the bipower proxy collapses to a squared return.
"""

import math
import random

import pytest

import tradingagents.dataflows.config as _cfg
from tradingagents.strategies.book_risk import extreme_quantile_var
from tradingagents.strategies.volatility_models import (
    bipower_proxy,
    ewma_vol,
    garch11_fit,
    garman_klass_vol,
    jump_robust_proxies_enabled,
    parkinson_vol,
    quarticity_proxy,
    semivariance,
    yang_zhang_vol,
    yang_zhang_vol_series,
)

# The two synthetic tapes share this total variance exactly - the sum of
# squared log returns over the window.
_PATH_N = 60
_PATH_RET = 0.01
_TOTAL_VAR = _PATH_N * _PATH_RET * _PATH_RET


def _bars_from_returns(rets, base=100.0):
    """Run-cache-shaped bars whose close-to-close log returns are ``rets``."""
    closes = [base]
    for r in rets:
        closes.append(closes[-1] * math.exp(r))
    return {
        "opens": list(closes),
        "highs": list(closes),
        "lows": list(closes),
        "closes": closes,
        "volumes": [1_000_000.0] * len(closes),
    }


def _bar_dicts(bars):
    """The same tape in the sequence-of-bar-dicts shape."""
    return [
        {"open": o, "high": h, "low": lo, "close": c}
        for o, h, lo, c in zip(
            bars["opens"], bars["highs"], bars["lows"], bars["closes"], strict=True
        )
    ]


def _smooth_path():
    """60 alternating +/-1% returns: the variance spread over every bar."""
    return [_PATH_RET if i % 2 == 0 else -_PATH_RET for i in range(_PATH_N)]


def _one_print_path():
    """The SAME total variance in one print, on an otherwise flat tape."""
    rets = [0.0] * _PATH_N
    rets[_PATH_N // 2] = math.sqrt(_TOTAL_VAR)
    return rets


def _log_returns(closes):
    out = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            out.append(math.log(closes[i] / closes[i - 1]))
    return out


def _simple_returns(closes):
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def _realistic_bars(n=120, seed=11):
    """A random-walk OHLC tape with a real daily range."""
    rnd = random.Random(seed)
    closes = [100.0]
    for _ in range(n):
        closes.append(closes[-1] * math.exp(rnd.gauss(0.0, 0.012)))
    opens, highs, lows = [], [], []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i else c
        opens.append(o)
        highs.append(max(o, c) * (1.0 + abs(rnd.gauss(0.0, 0.004))))
        lows.append(min(o, c) * (1.0 - abs(rnd.gauss(0.0, 0.004))))
    return {
        "opens": opens,
        "highs": highs,
        "lows": lows,
        "closes": closes,
        "volumes": [1_000_000.0] * len(closes),
    }


def _estimator_snapshot(bars):
    """The seven estimators the card pins: their exact records over one tape."""
    closes = bars["closes"]
    rets = _log_returns(closes)
    return {
        "semivariance": semivariance(closes),
        "parkinson_vol": parkinson_vol(bars["highs"], bars["lows"]),
        "garman_klass_vol": garman_klass_vol(bars["opens"], bars["highs"], bars["lows"], closes),
        "yang_zhang_vol": yang_zhang_vol(bars["opens"], bars["highs"], bars["lows"], closes),
        "yang_zhang_vol_series": yang_zhang_vol_series(
            bars["opens"], bars["highs"], bars["lows"], closes, window=20
        ),
        "ewma_vol": ewma_vol(rets),
        "garch11_fit": garch11_fit(rets),
    }


def _tail_tape(n=300, seed=5, jump_sigma=25.0, legs=10, decay=0.8):
    """Two tapes of equal total variance: the loss in ONE print vs spread out.

    Both start from the same Gaussian noise, so the only difference is how the
    ``jump_sigma``-sized loss arrives: as one print, or as a geometrically
    decaying run of smaller losses whose squared sum is the same.
    """
    rnd = random.Random(seed)
    sigma = 0.01
    base = [rnd.gauss(0.0, sigma) for _ in range(n)]
    start = n // 2
    big = jump_sigma * sigma
    weights = [decay**i for i in range(legs)]
    norm = math.sqrt(sum(w * w for w in weights))

    one = list(base)
    one[start : start + legs] = [0.0] * legs
    one[start] = -big

    diffuse = list(base)
    diffuse[start : start + legs] = [-big * w / norm for w in weights]
    return one, diffuse


def test_jump_proxy_separates_one_print_from_diffusion(monkeypatch):
    """A one-print tape and a diffusive tape of the SAME total variance get
    different jump shares; below the floor the read refuses; and the gate does
    not touch a single pre-existing estimator."""
    one_path, smooth_path = _one_print_path(), _smooth_path()

    # Premise: the two tapes carry the same total variance.
    assert sum(r * r for r in one_path) == pytest.approx(sum(r * r for r in smooth_path))

    one = bipower_proxy(_bars_from_returns(one_path))
    smooth = bipower_proxy(_bars_from_returns(smooth_path))

    assert one["jump_share_proxy"] > smooth["jump_share_proxy"]
    assert one["jump_share_proxy"] > 0.9  # every bit of the variance, one print
    assert smooth["jump_share_proxy"] < 0.25  # none of it

    # The same tape in the other accepted shape reads the same numbers.
    assert bipower_proxy(_bar_dicts(_bars_from_returns(one_path))) == one

    # The quarticity proxy separates them too: equal variance, far more
    # concentrated when it arrives in one print.
    assert (
        quarticity_proxy(_bars_from_returns(one_path))["quarticity_proxy"]
        > quarticity_proxy(_bars_from_returns(smooth_path))["quarticity_proxy"]
    )

    # Below the estimator floor: unavailable, never 0.0.
    thin = bipower_proxy(_bars_from_returns([_PATH_RET] * 5))
    assert thin["bipower_proxy"] is None and thin["jump_share_proxy"] is None
    assert thin["n"] == 5 and "unavailable" in thin["basis"]
    thin_q = quarticity_proxy(_bars_from_returns([_PATH_RET] * 5))
    assert thin_q["quarticity_proxy"] is None and "unavailable" in thin_q["basis"]
    # ... and a long tape read over a window below the floor refuses too.
    win = bipower_proxy(_bars_from_returns(one_path), window=5)
    assert win["n"] == 5 and win["jump_share_proxy"] is None

    # Gate off: the seven pre-existing estimators are unchanged bit-for-bit.
    bars = _realistic_bars()
    monkeypatch.setattr(_cfg, "get_config", lambda: {"enable_jump_robust_proxies": False})
    assert jump_robust_proxies_enabled() is False
    off = _estimator_snapshot(bars)
    monkeypatch.setattr(_cfg, "get_config", lambda: {"enable_jump_robust_proxies": True})
    assert jump_robust_proxies_enabled() is True
    assert _estimator_snapshot(bars) == off


def test_tail_read_reports_one_print_versus_diffuse_when_gated_on():
    """The rule-7 caller: `book_risk`'s tail read carries the jump leg only
    when the gate is on, and it separates a one-print tail from a diffusive
    one of the same variance."""
    one, diffuse = _tail_tape()
    assert sum(r * r for r in one) == pytest.approx(sum(r * r for r in diffuse))

    one_bars, diffuse_bars = _bars_from_returns(one), _bars_from_returns(diffuse)
    one_rets = _simple_returns(one_bars["closes"])
    diffuse_rets = _simple_returns(diffuse_bars["closes"])

    gate_on = {"enable_jump_robust_proxies": True}
    r_one = extreme_quantile_var(one_rets, ohlc=one_bars, config=gate_on)
    r_diffuse = extreme_quantile_var(diffuse_rets, ohlc=diffuse_bars, config=gate_on)
    assert r_one is not None and r_diffuse is not None  # both tails still fit

    assert r_one["jump"]["tail_shape"] == "one_print"
    assert r_diffuse["jump"]["tail_shape"] == "diffuse"
    assert r_one["jump"]["jump_share_proxy"] > r_diffuse["jump"]["jump_share_proxy"]

    # Gate off: the tail record is exactly the pre-V6 one.
    off = extreme_quantile_var(
        one_rets, ohlc=one_bars, config={"enable_jump_robust_proxies": False}
    )
    assert off is not None and "jump" not in off
    assert off == extreme_quantile_var(one_rets)
