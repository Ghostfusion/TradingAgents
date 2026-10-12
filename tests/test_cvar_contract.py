"""The CVaR contract's invariants (owner review 2026-10-12).

The tests that already existed pin `c <= v` and the cash-sleeve dilution ratio;
these pin the properties a SECOND producer of "the CVaR" must not break: what
the estimator means, that it is scale-invariant, that the two public conventions
(confidence LEVEL vs tail PROBABILITY) are the same calculation, and that a
portfolio's tail is not the weighted sum of its members' tails.

Every assertion here is hand-calculable from the sample in the test, so a change
that breaks one is a change to the *definition*, not to a fixture.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.book_risk import (
    cvar,
    portfolio_cvar,
    simple_var,
    var_cvar_horizon,
)

#: Ten returns; the engine's tail convention is ``k = max(1, int(alpha * n))``
#: (a FLOOR, so a tail is never empty), and the CVaR is the mean of the worst
#: ``k`` - documented here because a rounded value alone cannot tell a reader
#: which tail it came from.
SAMPLE = [0.02, -0.01, -0.03, -0.05, -0.02, 0.01, -0.04, -0.06, 0.03, -0.07]


def test_the_hand_calculated_tail_defines_the_convention():
    # alpha=0.05 on n=10 -> k = max(1, int(0.5)) = 1 -> the single worst day.
    assert cvar(SAMPLE, alpha=0.05) == pytest.approx(-0.07)
    # alpha=0.20 -> k = 2 -> the mean of the two worst.
    assert cvar(SAMPLE, alpha=0.20) == pytest.approx((-0.07 + -0.06) / 2)
    # VaR is the quantile on the same sample; CVaR is never better than it.
    tail = cvar(SAMPLE, alpha=0.20)
    quantile = simple_var(SAMPLE, alpha=0.20)
    assert tail is not None and quantile is not None
    assert quantile == pytest.approx(-0.06)
    assert tail <= quantile


def test_zero_returns_and_a_constant_loss_are_their_own_cvar():
    assert cvar([0.0] * 50) == pytest.approx(0.0)
    assert cvar([-0.02] * 50) == pytest.approx(-0.02)


def test_cvar_is_scale_invariant():
    base = [-0.01, -0.04, 0.02, -0.06, 0.01, -0.02]
    base_cvar = cvar(base, alpha=0.2)
    scaled_cvar = cvar([2.0 * x for x in base], alpha=0.2)
    assert base_cvar is not None and scaled_cvar is not None
    assert scaled_cvar == pytest.approx(2.0 * base_cvar)


def test_the_confidence_level_and_the_tail_probability_are_one_calculation():
    """``var_cvar_horizon`` takes a confidence LEVEL (0.95), ``cvar`` a tail
    PROBABILITY (0.05) - the two conventions that made the sizing defect
    invisible. At a one-day horizon they must agree exactly."""
    break_even = var_cvar_horizon(SAMPLE, 1, confidence_level=0.95)
    assert break_even["emp_cvar"] == pytest.approx(cvar(SAMPLE, alpha=0.05))
    assert break_even["emp_var"] == pytest.approx(simple_var(SAMPLE, alpha=0.05))
    # And the sqrt(T) blessing stays REFUSED on a thin sample - scaling a
    # 10-observation tail is not a validated multi-day read.
    assert break_even["scaling_valid"] is False


def test_the_simple_return_convention_has_one_implementation():
    """The market-analyst tools' ``_daily_returns`` is a VIEW of
    ``contract._simple_returns`` (rule 8), so the convention cannot drift.

    The two used to carry their own copies and disagreed on ragged input: a
    ``None`` broke the chain in one and raised in the other, and a negative
    previous close made one fabricate a nonsense return (``106 / -1 - 1``).
    """
    from tradingagents.agents.utils.analysis_tools import _daily_returns
    from tradingagents.strategies.contract import _simple_returns

    clean = [100.0, 101.0, 99.0, 103.5]
    assert _daily_returns(clean) == _simple_returns(clean)
    assert _simple_returns(clean) == pytest.approx(
        [101.0 / 100.0 - 1.0, 99.0 / 101.0 - 1.0, 103.5 / 99.0 - 1.0]
    )
    ragged = [100.0, None, 102.0, 0.0, 105.0, -1.0, 106.0]
    assert _daily_returns(ragged) == _simple_returns(ragged)
    # No return across a gap; a zero previous close yields none; a NEGATIVE one
    # yields none either (the old copy returned 106 / -1 - 1 = -107.0 here).
    assert _simple_returns(ragged) == pytest.approx([0.0 / 102.0 - 1.0, -1.0 / 105.0 - 1.0])


def test_portfolio_cvar_is_not_the_weighted_sum_of_member_cvars():
    """Diversification, pinned structurally.

    Two names whose worst day falls on DIFFERENT days: the mixed book's worst
    day is half of either name's, so the portfolio tail is strictly smaller than
    ``sum_i w_i * |cvar_i|``. An implementation that summed member CVaRs (or
    paired mismatched days) would fail here.
    """
    a = [0.01] * 19 + [-0.10]
    b = [-0.10] + [0.01] * 19
    mix = portfolio_cvar({"a": a, "b": b}, weights={"a": 0.5, "b": 0.5}, alpha=0.05)
    a_cvar = cvar(a, alpha=0.05)
    b_cvar = cvar(b, alpha=0.05)
    assert mix is not None and a_cvar is not None and b_cvar is not None
    assert mix == pytest.approx(-0.045)  # 0.5 * (-0.10) + 0.5 * 0.01
    assert abs(mix) < 0.5 * abs(a_cvar) + 0.5 * abs(b_cvar)
