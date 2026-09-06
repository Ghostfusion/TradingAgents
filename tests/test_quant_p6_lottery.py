"""Tests for Phase 6 core: MAX / IVOL lottery factors + the lottery tool."""

import random

import pytest

from tradingagents.strategies.lottery import (
    idiosyncratic_vol,
    lottery_verdict,
    max_daily_return,
)

pytestmark = pytest.mark.timeout(60)


def _closes(n: int = 300, seed: int = 1, drift: float = 0.0003, vol: float = 0.01) -> list[float]:
    rnd = random.Random(seed)
    out, px = [], 100.0
    for _ in range(n):
        px *= 1 + rnd.gauss(drift, vol)
        out.append(px)
    return out


def _rets(closes) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def test_max_daily_return_plain_small():
    closes = _closes()
    mx = max_daily_return(closes)
    assert mx is not None and mx < 0.05


def test_max_daily_return_spike_detects():
    closes = _closes()[:-2] + [_closes()[-2] * 1.35] + [_closes()[-2] * 1.02]
    assert max_daily_return(closes) > 0.30


def test_max_daily_return_none_safe():
    assert max_daily_return([]) is None
    assert max_daily_return([100.0]) is None  # single close


def test_idiosyncratic_vol_falls_back_to_total():
    closes = _closes(seed=2)
    rets = _rets(closes)
    iv = idiosyncratic_vol(rets)  # no market -> total vol fallback
    assert iv is not None and iv > 0


def test_idiosyncratic_vol_short_none():
    assert idiosyncratic_vol([]) is None
    assert idiosyncratic_vol([0.01, -0.01]) is None  # < min_obs


def test_lottery_verdict_ok_for_plain():
    closes = _closes(seed=3)
    v = lottery_verdict(closes, _rets(closes))
    assert v["verdict"] == "ok"
    assert v["max_volatile"] is False


def test_lottery_verdict_tilt_on_spike():
    base = _closes(seed=4)
    spiked = base[:-2] + [base[-2] * 1.35] + [base[-2] * 1.02]
    v = lottery_verdict(spiked, _rets(spiked), max_cap=0.15)
    assert v["verdict"] == "lottery-tilt"
    assert v["max_volatile"] is True


def test_lottery_verdict_none_safe():
    v = lottery_verdict([], [])
    assert v["verdict"] == "ok" and v["max"] is None
