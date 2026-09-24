"""K3 — the cross-strike IV skew proxy has a strike floor, and names itself.

The paper behind item K3 reads a *cross-strike IV proxy* for the risk-neutral
skewness and finds its predictive coefficient unstable across horizons and
regimes, so two things must hold at the code that produces it: a chain too thin
to identify the cross-strike slope returns `unavailable` rather than a number,
and the record that does carry a number says what it is (a cross-strike IV
proxy) rather than claiming the true BKM moment. The read is also conditioned on
the regime cell the engine already produces, so the record carries the cell it
was conditioned on.
"""

import json

import pytest

from tradingagents.strategies.options_surface import (
    RN_SKEW_LABEL,
    RN_SKEW_MIN_STRIKES,
    rn_skew_proxy,
)

pytestmark = pytest.mark.timeout(60)

#: The cell the regime producer hands over (`regime.hmm_filtered_regime(...)
#: ['last']` carries exactly these two keys).
CELL = {"state": 1, "label": "bear"}


def _chain(strikes: list[float], spot: float = 100.0, days: int = 30) -> list[dict]:
    """Synthetic chain: one call + one put per strike, IV richest at the low
    strikes (the equity smirk), quoted in DECIMALS as the vendors quote them."""
    import math

    rows = []
    for k in strikes:
        iv = max(0.05, 0.20 - 0.5 * math.log(k / spot))
        for side in ("call", "put"):
            rows.append({"strike": float(k), "iv": iv, "days_to_expiry": days,
                         "spot": float(spot), "side": side})
    return rows


def test_proxy_unavailable_below_five_strikes():
    """Four OTM strikes yields `unavailable` and never a number; five yields the
    labelled proxy; the record carries the cross-strike IV label and the regime
    cell it was conditioned on, never a BKM claim."""
    four = rn_skew_proxy(_chain([88.0, 96.0, 104.0, 112.0]), regime_cell=CELL)
    assert four["n_strikes"] == 4
    assert four["status"] == "unavailable"
    assert four["proxy"] is None
    assert not isinstance(four["proxy"], (int, float))  # never a number
    assert str(four["unavailable"])
    assert four["regime_cell"] == CELL

    five = rn_skew_proxy(_chain([85.0, 92.0, 95.0, 108.0, 118.0]), regime_cell=CELL)
    assert five["n_strikes"] == RN_SKEW_MIN_STRIKES == 5
    assert five["status"] == "ok"
    assert isinstance(five["proxy"], float)
    # Puts priced over calls (the smirk) reads negative, like the skewness it
    # proxies — the same direction surface_shape's rr25 reports.
    assert five["proxy"] < 0
    assert five["label"] == RN_SKEW_LABEL == "cross-strike IV proxy"
    assert five["regime_cell"] == CELL
    assert five["conditioned"] is True

    # The record names itself a proxy, not the moment: no field but the basis
    # may claim the BKM moment the paper says this is not.
    claims = json.dumps({k: v for k, v in five.items() if k != "basis"},
                        default=str).lower()
    assert "bkm" not in claims
    assert "moment" not in claims


def test_proxy_is_unconditioned_without_a_cell():
    """No cell supplied is reported as un-conditioned — the number is still the
    chain's own slope (the cell labels the read, it never rewrites it), but the
    record must not present it as a constant."""
    rows = _chain([85.0, 92.0, 95.0, 108.0, 118.0])
    rec = rn_skew_proxy(rows)
    assert rec["status"] == "ok"
    assert rec["regime_cell"] is None
    assert rec["conditioned"] is False
    assert rec["proxy"] == rn_skew_proxy(rows, regime_cell=CELL)["proxy"]


def test_proxy_is_invariant_to_the_iv_quote_unit():
    """A chain quoted in percent yields the same proxy as one in decimals: the
    statistic is a fractional-IV slope over standardized moneyness."""
    strikes = [85.0, 92.0, 95.0, 108.0, 118.0]
    dec = rn_skew_proxy(_chain(strikes), regime_cell=CELL)["proxy"]
    pct = rn_skew_proxy([{**r, "iv": r["iv"] * 100.0} for r in _chain(strikes)],
                        regime_cell=CELL)["proxy"]
    assert dec == pct
