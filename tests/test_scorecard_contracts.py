"""Contract tests for the two seams the scorecard's text crosses.

Two things are frozen here, and neither is cosmetic:

**1. The ground-truth parser's behaviour, as it actually is.** Three traps were
found by running `structured_debate._parse_key_value_lines` over the design
document's own examples, and each one *changed the meaning* of a rendered block:

- a non-numeric `key=value` before a numeric one on the same line is **swallowed
  into that pair's key** — `trade_status=RESEARCH_ONLY trade_coverage=0.95`
  recovers `research_only_trade_coverage`, and `trade_coverage` never exists;
- a leading `+` is **not matched** by the number pattern, so `trade_delta=+3.55`
  registers no key at all and the delta is silently invisible;
- an ISO date registers as **its year**: `trade_prev_date=2026-09-11` becomes
  `trade_prev_date = 2026`.

These assertions pin the parser, not our formatting. If the parser changes, this
file fails first and the block formats can be revisited deliberately instead of
drifting.

**2. The monotonicity classification, demonstrated rather than presumed.** The
`NON_MONOTONIC_INPUTS` set is a *claim about the producers' ramps*. A fixture that
merely assumed a component was monotonic — MFI, in the first draft of these tests —
encodes a mathematical property the producer never promised. So the claim is
checked against the real mapping here: a declared non-monotonic input must show at
least one raw value where a higher reading aligns **lower**, and a monotonic one
must never.

Offline and deterministic.
"""

from __future__ import annotations

from tradingagents.agents.researchers.structured_debate import _parse_key_value_lines
from tradingagents.strategies.score_engine import NON_MONOTONIC_INPUTS
from tradingagents.strategies.technical_score import COMPONENTS, align_components

# ---------------------------------------------------------------------------
# the parser's real behaviour
# ---------------------------------------------------------------------------


def test_a_non_numeric_pair_before_a_numeric_one_is_swallowed():
    """The trap §4.1's first draft walked into.

    The key pattern is case-insensitive and admits spaces, so it consumes
    `RESEARCH_ONLY trade_coverage` as one key. This is why the block puts a
    non-numeric token **last** on its line.
    """
    parsed = _parse_key_value_lines(
        "trade_score=76.75 trade_status=RESEARCH_ONLY trade_coverage=0.95"
    )
    assert parsed["trade_score"] == 76.75
    assert "trade_coverage" not in parsed
    assert parsed["research_only_trade_coverage"] == 0.95


def test_a_leading_plus_makes_the_pair_invisible():
    """The trap §4.3's first draft walked into.

    The number pattern is `-?\\d+`, so `+` fails the match and **no key is
    registered at all** — the delta would be missing from the registry while the
    block appeared to print it.
    """
    assert "trade_delta" not in _parse_key_value_lines("trade_delta=+3.55")
    # the unsigned and negative forms both register
    assert _parse_key_value_lines("trade_delta=3.55")["trade_delta"] == 3.55
    assert _parse_key_value_lines("trade_delta=-3.55")["trade_delta"] == -3.55


def test_an_iso_date_registers_as_its_year():
    """`trade_prev_date=2026-09-11` is `2026` to the parser, not a date."""
    parsed = _parse_key_value_lines("trade_prev_date=2026-09-11")
    assert parsed["trade_prev_date"] == 2026.0


def test_a_parenthesised_date_registers_no_key_at_all():
    """Which is why the block prints `prior observation (2026-09-11)`.

    No letter-led token precedes the digits, so the pattern finds nothing to
    anchor a key to and the date cannot be cited as a metric.
    """
    parsed = _parse_key_value_lines("prior observation (2026-09-11)")
    assert parsed == {}


def test_the_two_safe_forms_round_trip():
    """What the renderer actually emits: numbers first, token last, date bare."""
    parsed = _parse_key_value_lines(
        "trade_score=76.75 trade_coverage=0.95 trade_prev=73.2 trade_delta=3.55 "
        "trade_status=RESEARCH_ONLY\n"
        "prior observation (2026-09-11)"
    )
    assert parsed == {
        "trade_score": 76.75,
        "trade_coverage": 0.95,
        "trade_prev": 73.2,
        "trade_delta": 3.55,
    }


# ---------------------------------------------------------------------------
# monotonicity, demonstrated against the producer's own ramp
# ---------------------------------------------------------------------------


#: The components span **two sign conventions**: Williams %R lives on `-100..0`
#: while the rest live on `0..100`, and `Component` carries no domain field. A
#: sweep of one half is therefore itself an assumption — the first draft of this
#: test swept `0..100`, found `williams_r` flat, and had to be corrected. So the
#: demonstration sweeps both halves and requires the curve to *vary* before it
#: asks whether it ever falls.
RAW_SWEEP = [-95.0, -70.0, -50.0, -30.0, -10.0, 10.0, 30.0, 50.0, 70.0, 95.0]


def _aligned_curve(name: str, raws: list[float]) -> list[float]:
    out = []
    for raw in raws:
        value = align_components({name: raw}).get(name)
        if value is not None:
            out.append(value)
    return out


def test_every_mapped_non_monotonic_input_really_is_non_monotonic():
    """The set is a claim about the ramps; this checks the ramps.

    A raw value that aligns **lower** than a smaller raw value is the signature:
    RSI `50 -> 85` while RSI `70 -> 45`, because the producer's band says an
    overbought reading is not a strong one.
    """
    checked = 0
    for name in NON_MONOTONIC_INPUTS:
        if name not in COMPONENTS:
            # the set spans engines; `stochastic`/`stochrsi`/`elder_thermometer`
            # are not names this engine maps
            continue
        curve = _aligned_curve(name, RAW_SWEEP)
        assert curve, f"{name} produced no aligned values"
        assert len(set(curve)) > 1, (
            f"{name} maps every swept raw to one value ({curve[0]}): the sweep "
            "misses its domain, or the ramp is flat"
        )
        falls = [b < a for a, b in zip(curve, curve[1:], strict=False)]
        assert any(falls), f"{name} is declared non-monotonic but never falls: {curve}"
        checked += 1
    assert checked >= 4, f"only {checked} components were actually checked"


def test_a_monotonic_component_never_falls():
    """The other half of the claim: `adx` rises with its raw value."""
    curve = _aligned_curve("adx", [10.0, 20.0, 30.0, 40.0, 50.0])
    assert curve == sorted(curve), curve
    assert len(set(curve)) > 1, curve
    assert "adx" not in NON_MONOTONIC_INPUTS


def test_the_declared_set_is_not_larger_than_the_engine_can_show():
    """Every declared name must be either mapped here or mapped by a sibling.

    Guards against the set drifting into names nothing produces, which would make
    the triple unreachable while the declaration looked fine.
    """
    unmapped = [n for n in NON_MONOTONIC_INPUTS if n not in COMPONENTS]
    assert set(unmapped) <= {"stochastic", "stochrsi", "elder_thermometer"}
