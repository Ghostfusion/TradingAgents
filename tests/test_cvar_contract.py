"""The CVaR contract's invariants (owner review 2026-10-12).

The tests that already existed pin `c <= v` and the cash-sleeve dilution ratio;
these pin the properties a SECOND producer of "the CVaR" must not break: what
the estimator means, that it is scale-invariant, that the two public conventions
(confidence LEVEL vs tail PROBABILITY) are the same calculation, that a
portfolio's tail is not the weighted sum of its members' tails, and that the two
gate legs are bounded by SEPARATE limits.

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


def test_the_two_tail_legs_are_bounded_by_their_own_limits():
    """One key used to bound two policies at once: the analyzed name's own tail
    and the portfolio's.

    A 3 % portfolio budget against a 5 % standalone limit REJECTs on the book
    while the name leg stays silent, and the reverse configuration REJECTs on
    the name while the portfolio leg stays silent. That is the 2026-10-12
    artifact's defect - ``risk_gate: PASS`` (book 1.04 %) published beside
    ``binding_reason: analyzed-name CVaR 14.68% > budget 3.00%``: one key, two
    objects, opposite readings.
    """
    from tradingagents.strategies.risk_governor import govern

    name_slack = {
        "risk_portfolio_cvar_budget_pct": 0.03,
        "risk_standalone_cvar_limit_pct": 0.05,
    }
    v = govern(0.10, name_slack, cvar_pct=0.04, name_cvar_pct=0.04)
    assert v["verdict"] == "REJECT"
    assert any("portfolio cvar 4.00% > budget 3.00%" in r for r in v["reasons"])
    assert not any("name cvar" in r for r in v["reasons"])

    book_slack = {
        "risk_portfolio_cvar_budget_pct": 0.05,
        "risk_standalone_cvar_limit_pct": 0.03,
    }
    v2 = govern(0.10, book_slack, cvar_pct=0.04, name_cvar_pct=0.04)
    assert v2["verdict"] == "REJECT"
    assert any("name cvar 4.00% > limit 3.00%" in r for r in v2["reasons"])
    assert not any("portfolio cvar" in r for r in v2["reasons"])

    # Each leg is independently omittable and keeps its own limit: the same 4 %
    # tail is a WARN against the 5 % budget and a REJECT against the 3 % name
    # limit when the other leg was not measured.
    near_book = govern(0.10, book_slack, cvar_pct=0.04)
    assert near_book["verdict"] == "WARN"
    assert not near_book["reasons"]
    over_name = govern(0.10, book_slack, name_cvar_pct=0.04)
    assert over_name["verdict"] == "REJECT"


def test_the_decision_leg_and_the_tail_tool_are_one_measurement(monkeypatch):
    """One series, one convention - pinned across BOTH entry points.

    Before the owner's 2026-10-12 source decision these were two readings of one
    label: the decision leg read `_try_fetch_closes` (the raw vendor chain, 320
    CALENDAR days, LOG returns) while the market analyst's tool read `_ohlcv`
    (the PIT-filtered `load_ohlcv`, 320 BARS, SIMPLE returns) - 14.6849 % vs
    12.4172 % on SMCI, n=217 vs n=319. Both now go through the graph's
    `_pit_closes` and `contract._simple_returns`, so a difference between them is
    a defect rather than a basis to disclose.
    """
    import math

    import tradingagents.graph.trading_graph as tg
    from tradingagents.agents.utils import analysis_tools as at
    from tradingagents.strategies.contract import _simple_returns

    closes = [100.0 + 3.0 * math.sin(i / 5.0) - 0.02 * i for i in range(320)]
    frame = {"dates": [], "closes": closes, "highs": [], "lows": [], "volumes": [], "opens": []}
    monkeypatch.setattr(at, "_ohlcv", lambda ticker, days=320: frame)

    graph = object.__new__(tg.TradingAgentsGraph)
    graph.config = {
        "risk_standalone_cvar_limit_pct": 0.03,
        "risk_portfolio_cvar_budget_pct": 0.03,
    }
    monkeypatch.setattr(graph, "_pit_closes", lambda ticker, days=320: closes)
    monkeypatch.setattr(graph, "_basket_cvar", lambda ticker, alpha=0.05: None)

    ctx = graph._precompute_risk_context("SMCI")
    expected = abs(cvar(_simple_returns(closes), alpha=0.05))
    assert ctx["single_cvar"] == pytest.approx(expected)
    assert ctx["single_cvar_n"] == len(_simple_returns(closes))

    # The analyst-facing tool reads the same stubbed source, and its line
    # carries the same value and the same window.
    printed = at.get_tail_risk.invoke({"ticker": "SMCI"})
    assert f"cvar={ctx['single_cvar']:.2%}" in printed
    assert f"n={ctx['single_cvar_n']}" in printed
