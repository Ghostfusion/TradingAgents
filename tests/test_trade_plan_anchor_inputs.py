"""The card's three measured inputs that the close series alone cannot carry.

Each is wired from a producer that already existed; none is a new model.

* ``technical_price`` - ``entry_exit_families.support_level``, the SAME
  close-series support §103's ``support_entry_price`` row is built from, so the
  two members agree by construction instead of being two derived numbers that
  can drift apart.
* ``execution_spread`` - ``liquidity_risk.spread_estimate``, fed the verified
  OHLCV bundle. It is a FRACTION, so a scale difference between that bundle and
  the card's own series cannot reach the card (asserted below, because that
  property is the whole reason a foreign bundle is safe to feed it).
* ``fair_value`` - a measured DCF per-share value, filling §103's fair-value
  pair ONLY. It deliberately does not also become §100's valuation anchor or
  ceiling: measured on 2026-10-05 the repo's DCF returns 0.10x of price for VST
  and 0.42x for KGC, so those two roles would set the card's headline
  ``final_entry_price`` to the DCF value on every leveraged name.

Hermetic: no network, no LLM, no clock; the DCF module's seams are stubbed.
"""

from __future__ import annotations

import math

import pytest

from tradingagents.strategies.trade_plan import (
    build_trade_plan,
    measured_inputs,
    render_entry_exit_block,
)

# Cold-start: the DCF tests import the analysis tools, whose module scope drags
# in the vendor stack; the file-level marker overrides --timeout.
pytestmark = pytest.mark.timeout(600)


def _closes(n: int = 200) -> list[float]:
    """Deterministic positive series with 1-3% swings (no RNG, no clock)."""
    return [100.0 + 0.02 * i + 3.0 * math.sin(i / 5.0) for i in range(n)]


def _bars(closes: list[float], scale: float = 1.0) -> dict:
    """An ``_ohlcv``-shaped bundle: a constant 1% high/low band.

    Constant and PROPORTIONAL, so Corwin-Schultz is defined on it and the same
    bundle stays meaningful when rescaled - which is what the dimensionless
    test below asserts.
    """
    return {
        "closes": [c * scale for c in closes],
        "highs": [c * scale * 1.01 for c in closes],
        "lows": [c * scale * 0.99 for c in closes],
    }


def _line(text: str, prefix: str) -> str:
    return next((ln for ln in text.splitlines() if ln.startswith(prefix)), "")


def _value(text: str, prefix: str) -> str:
    """The value cell of a member row, which renders ``- name: <value> - reason``."""
    return _line(text, prefix).split(": ", 1)[1].split(" - ", 1)[0]


def _card(**inputs) -> str:
    """The plan card text for ``inputs``."""
    closes = inputs.get("closes") or _closes()
    return build_trade_plan(ticker="TST", price=closes[-1], config={}, **inputs)


def _block(**inputs) -> str:
    """The rendered ENTRY/EXIT block for ``inputs``.

    ``measured_inputs`` already carries the ``closes`` it measured on, so a
    caller passes its whole return value through - and the card needs that
    series, because its §103 rows are derived from it.
    """
    closes = inputs.get("closes") or _closes()
    capture: dict = {}
    build_trade_plan(
        ticker="TST", price=closes[-1], config={}, capture=capture, **inputs
    )
    return render_entry_exit_block(capture["entry_exit"])


def test_the_technical_anchor_is_the_cards_own_support_level():
    """One producer, so §103's two rows about the same level cannot disagree."""
    from tradingagents.strategies.entry_exit_families import (
        SUPPORT_BUFFER_PCT,
        support_level,
    )

    closes = _closes()
    expected, _basis = support_level(closes)
    inputs = measured_inputs(closes, {})
    assert inputs["technical_price"] == pytest.approx(expected)

    block = _block(**inputs)
    # The anchor IS the level; §103's support ENTRY is that level plus the §10
    # buffer. They differ by exactly the buffer, never arbitrarily.
    assert f"- technical_entry_price: {expected:.2f} " in block
    assert f"- support_entry_price: {expected * (1 + SUPPORT_BUFFER_PCT):.2f} " in block


def test_the_spread_is_a_fraction_that_survives_a_rescaled_bundle():
    """The dimensionless property is what makes a foreign bundle safe."""
    closes = _closes()
    plain = measured_inputs(closes, {}, bars=_bars(closes))
    scaled = measured_inputs(closes, {}, bars=_bars(closes, scale=17.0))
    assert 0.0 < plain["execution_spread"] < 1.0
    assert plain["execution_spread"] == pytest.approx(
        scaled["execution_spread"], rel=1e-9
    )
    # …and it reaches the two execution rows, which are empty without it.
    block = _block(**plain)
    assert "unavailable" not in _line(block, "- execution_price:")
    # §103 lists the §102 liquidity-adjusted price as the same number.
    assert _value(block, "- execution_price:") == _value(
        block, "- liquidity_adjusted_entry_price:"
    )


def test_the_fair_value_fills_the_pair_and_never_the_valuation_anchor():
    """The held seam: two rows filled, and the headline left alone."""
    closes = _closes()
    plain = measured_inputs(closes, {})
    with_fv = measured_inputs(closes, {}, fair_value=160.0)

    block_fv = _block(**with_fv)
    assert _line(block_fv, "- fair_value_price:").startswith(
        "- fair_value_price: 160.00 "
    )
    # §42's conservative haircut is 10% - and the result sits ABOVE the entry,
    # which is what makes it a target at all (see the wrong-side guard).
    assert _line(block_fv, "- fair_value_target:").startswith(
        "- fair_value_target: 144.00 "
    )
    # The anchor and the ceiling are NOT fed from it, so they stay as they were.
    assert "unavailable" in _line(block_fv, "- valuation_entry_price:")
    assert _line(_card(**plain), "- Entry ceiling") == _line(
        _card(**with_fv), "- Entry ceiling"
    )
    assert _line(_card(**plain), "- **Final entry price") == _line(
        _card(**with_fv), "- **Final entry price"
    )
    assert _line(_block(**plain), "- final_entry_price:") == _line(
        block_fv, "- final_entry_price:"
    )


def test_an_absent_input_leaves_its_rows_absent_never_zero():
    """A missing measurement is named absent, never defaulted to a number."""
    closes = _closes()
    inputs = measured_inputs(closes, {})
    assert "execution_spread" not in inputs
    assert "fair_value" not in inputs

    block = _block(**inputs)
    assert "unavailable" in _line(block, "- fair_value_price:")
    assert "unavailable" in _line(block, "- execution_price:")
    assert "unavailable" in _line(block, "- liquidity_adjusted_entry_price:")

    # A bundle without the OHLC columns is not a measurement of the spread.
    assert "execution_spread" not in measured_inputs(
        closes, {}, bars={"closes": closes}
    )


def test_the_technical_anchor_raises_the_target_coverage_but_not_the_ceiling():
    """It feeds §100's anchor BLEND, not the entry CEILING - two different lists."""
    closes = _closes()
    with_anchor = _card(**measured_inputs(closes, {}))
    without = _card(**{**measured_inputs(closes, {}), "technical_price": None})
    assert "coverage 2/3" in _line(with_anchor, "- Target entry")
    assert "coverage 1/3" in _line(without, "- Target entry")
    # The ceiling is built from the ceiling sources; an anchor is not one.
    assert _line(with_anchor, "- Entry ceiling").split("coverage")[1] == (
        _line(without, "- Entry ceiling").split("coverage")[1]
    )


# --- the DCF seam -----------------------------------------------------------


def _stub_dcf(monkeypatch, *, price: float, fair_value: float):
    """Point the DCF helper at a fixed context and a fixed model result."""
    import tradingagents.agents.utils.analysis_tools as at

    at._dcf_fair_value_cached.cache_clear()
    monkeypatch.setattr(
        at,
        "_dcf_context",
        lambda ticker, date: {
            "fcf": [1.0],
            "rf": 0.04,
            "beta": 1.0,
            "shares": 1.0,
            "cash": 0.0,
            "debt": 0.0,
            "price": price,
        },
    )
    monkeypatch.setattr(
        "tradingagents.strategies.dcf.compute_dcf",
        lambda *a, **k: {"price": fair_value},
    )
    monkeypatch.setattr(at, "get_run_trade_date", lambda: "2026-10-05")
    return at


def test_the_dcf_helper_refuses_a_value_five_times_the_price(monkeypatch):
    """The same >5x data-quality guard ``get_dcf_valuation`` applies.

    A fair value that far from the price is unit-mixed or share-basis
    inconsistent (TSM 2026-09-10: 2933.52 against a price of 429.55), so it is
    not a USD number and must not reach the card as one.
    """
    at = _stub_dcf(monkeypatch, price=10.0, fair_value=68.0)
    value, reason = at.dcf_fair_value_per_share("TST")
    assert value is None
    assert "data-quality" in reason
    # The guard is a refusal, not a clamp: in range the value passes through.
    at = _stub_dcf(monkeypatch, price=10.0, fair_value=12.5)
    assert at.dcf_fair_value_per_share("TST") == (12.5, "")


def test_one_statement_read_per_ticker_and_date(monkeypatch):
    """The memo keeps the pre-graph card and every tool call on one number.

    Without it each call would re-fetch, and the two surfaces could then print
    different values - the defect class that put two different entry ceilings in
    one report tree.
    """
    at = _stub_dcf(monkeypatch, price=10.0, fair_value=12.5)
    reads: list[tuple[str, str]] = []

    def _ctx(ticker, date):
        reads.append((ticker, date))
        return {"error": "no fcf"}

    monkeypatch.setattr(at, "_dcf_context", _ctx)
    for _ in range(3):
        assert at.dcf_fair_value_per_share("tst") == (None, "no fcf")
    # Uppercased once, on the run's trade_date, and read exactly once.
    assert reads == [("TST", "2026-10-05")]
