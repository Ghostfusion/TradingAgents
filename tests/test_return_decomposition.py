"""Q5 - overnight/intraday return decomposition (N8).

Docs: ``docs/implementation_plan_quant_formula_additions.md`` phase Q5.

Observable contract: the intraday and overnight legs are a decomposition of the
close-to-close log return (which leg carried the move), never an attribution to
a cause; each leg's mean/stdev is in raw per-period log-return units.
"""

from __future__ import annotations

import math

import pytest

from tradingagents.strategies.market_session import (
    decompose_returns,
    decompose_returns_text,
)

# A deterministic synthetic series; every price positive. Deliberately shaped
# so neither leg is degenerate (both variances > 0).
OPENS = [100.0, 101.5, 100.8, 102.3, 101.9, 103.4]
CLOSES = [101.2, 100.9, 102.5, 102.1, 103.8, 104.1]

EXPECTED_KEYS = {
    "intraday_mean",
    "intraday_vol",
    "overnight_mean",
    "overnight_vol",
    "intraday_var_share",
    "n",
    "basis",
}


def _legs(opens, closes):
    """Independent per-pair legs; both leg lists indexed for t = 1..N-1."""
    intraday = [math.log(c / o) for o, c in zip(opens, closes, strict=True)][1:]
    overnight = [
        math.log(opens[t] / closes[t - 1]) for t in range(1, len(closes))
    ]
    return intraday, overnight


def test_legs_decompose_the_close_to_close_log_return():
    read = decompose_returns(OPENS, CLOSES)
    assert read is not None
    assert set(read) == EXPECTED_KEYS

    intraday, overnight = _legs(OPENS, CLOSES)
    close_to_close = [math.log(CLOSES[t] / CLOSES[t - 1]) for t in range(1, len(CLOSES))]

    # Every pair's two legs sum to the close-to-close log return.
    for i, cc in enumerate(close_to_close):
        assert intraday[i] + overnight[i] == pytest.approx(cc, abs=1e-12)

    # The returned means are per-period means of those legs, so the aggregate
    # identity must hold too (this is what the caller reads).
    assert read["intraday_mean"] == pytest.approx(math.fsum(intraday) / len(intraday))
    assert read["overnight_mean"] == pytest.approx(math.fsum(overnight) / len(overnight))
    assert read["intraday_mean"] + read["overnight_mean"] == pytest.approx(
        math.fsum(close_to_close) / len(close_to_close)
    )
    assert read["n"] == len(intraday) == len(CLOSES) - 1
    assert isinstance(read["basis"], str) and read["basis"]


def test_zero_overnight_variance_gives_share_one():
    # Opens equal the prior close: the entire move is intraday.
    closes = [101.0, 102.5, 101.7, 103.9, 102.8]
    opens = [100.0, closes[0], closes[1], closes[2], closes[3]]
    read = decompose_returns(opens, closes)
    assert read is not None
    assert read["overnight_vol"] == pytest.approx(0.0, abs=1e-12)
    assert read["intraday_var_share"] == pytest.approx(1.0, abs=1e-9)


def test_only_overnight_moves_gives_share_zero():
    # Intraday ratio is constant (zero intraday variance); all variance is the
    # overnight gap.
    opens = [100.0, 102.0, 105.0, 108.5, 113.0, 117.2]
    ratio = 1.01
    closes = [o * ratio for o in opens]
    read = decompose_returns(opens, closes)
    assert read is not None
    assert read["intraday_vol"] == pytest.approx(0.0, abs=1e-9)
    assert read["intraday_var_share"] == pytest.approx(0.0, abs=1e-9)


def test_missing_or_ragged_opens_return_none():
    assert decompose_returns(None, CLOSES) is None
    # Length mismatch is ragged input, never silently truncated.
    assert decompose_returns(OPENS[:-1], CLOSES) is None
    assert decompose_returns(OPENS + [104.0], CLOSES) is None
    # A None entry anywhere in the open series is a missing open.
    ragged = list(OPENS)
    ragged[2] = None
    assert decompose_returns(ragged, CLOSES) is None


def test_none_closes_returns_none():
    assert decompose_returns(OPENS, None) is None


def test_degenerate_inputs_return_none():
    # Fewer than 3 usable pairs.
    assert decompose_returns([1.0, 2.0, 3.0], [1.1, 2.1, 3.1]) is None
    # Non-positive price.
    assert decompose_returns([100.0, 0.0, 101.0, 102.0], [101.0, 100.0, 102.0, 103.0]) is None
    # Zero total variance: every leg exactly 0 (flat opens/closes).
    flat = [100.0, 100.0, 100.0, 100.0, 100.0]
    assert decompose_returns(flat, flat) is None


def test_deterministic_on_rerun():
    assert decompose_returns(OPENS, CLOSES) == decompose_returns(OPENS, CLOSES)


def test_renderer_states_decomposition_and_handles_unavailable():
    read = decompose_returns(OPENS, CLOSES)
    line = decompose_returns_text(read)
    assert "intraday" in line and "overnight" in line
    assert "var share" in line
    assert str(read["n"]) in line
    assert decompose_returns_text(None) == "return decomposition unavailable"
