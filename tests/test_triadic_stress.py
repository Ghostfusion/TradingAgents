"""R7 - the triadic stress index names the block, and refuses a thin book.

The paper behind item R7 builds a coincident stress index over the correlation
network and adds a per-node ``diag(A^3)`` attribution that names the epicentre.
Two things must hold at the code that produces it: on a cross-section where a
known subset of names carries the correlated block the epicentre names that
subset, and a cross-section below the eight-name floor returns `unavailable`
rather than a saturated index. The record must also carry its `coincident`
label on every read it returns, because the index says *where* stress is and
never that any is coming (regime constraint R8).

Offline and deterministic: every panel is synthetic, no vendor call.
"""

from __future__ import annotations

import numpy as np
import pytest

from tradingagents.strategies.triadic_stress import (
    COINCIDENT,
    LABEL,
    MIN_NAMES,
    MIN_OBS,
    triadic_stress,
)

pytestmark = pytest.mark.timeout(120)

NAMES = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L")

#: The manufactured stressed block: four names that share a factor of their own
#: on top of the market factor, so their pairwise correlation dominates.
BLOCK = ("A", "B", "C", "D")


def _gate(monkeypatch, on: bool) -> None:
    """Flip ``enable_triadic_stress`` at the config accessor the read uses."""
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"enable_triadic_stress": on},
    )


def _panel(bars: int = 320, seed: int = 7) -> dict:
    """A manufactured cross-section: a weak common market factor for everyone,
    plus a block factor shared only by ``BLOCK``. Returns are unitless draws -
    only the *network* they produce matters here."""
    rng = np.random.default_rng(seed)
    market = rng.normal(0.0, 1.0, bars)
    block_factor = rng.normal(0.0, 1.0, bars)
    out: dict = {}
    for name in NAMES:
        idio = rng.normal(0.0, 1.0, bars)
        if name in BLOCK:
            series = 0.30 * market + 0.90 * block_factor + 0.30 * idio
        else:
            series = 0.30 * market + 1.00 * idio
        out[name] = list(series)
    return out


def test_epicentre_names_the_stressed_block(monkeypatch) -> None:
    """On a panel whose block carries the correlated structure the epicentre is
    exactly that block, ordered by descending ``diag(A^3)``; a four-symbol book
    is thin and returns `unavailable`, never a saturated index."""
    _gate(monkeypatch, on=True)
    panel = _panel()

    rec = triadic_stress(panel)
    assert rec["status"] == "ok"
    assert rec["coincident"] is True
    assert isinstance(rec["tsi"], float)

    # the epicentre names the stressed subset, not the whole book
    assert set(rec["epicentre"]) == set(BLOCK)
    assert len(rec["epicentre"]) < rec["n_names"]
    # ... and it is ORDERED by its own attribution, descending
    attr = rec["attribution"]
    assert rec["epicentre"] == sorted(rec["epicentre"], key=lambda n: (-attr[n], n))
    # every block name carries more triadic load than every name outside it
    assert min(attr[n] for n in BLOCK) > max(attr[n] for n in NAMES if n not in BLOCK)

    # a four-symbol book IS thin: refused, with a reason, never a number
    thin = {name: panel[name] for name in BLOCK}
    small = triadic_stress(thin)
    assert small["status"] == "unavailable"
    assert small["tsi"] is None
    assert not isinstance(small["tsi"], (int, float))
    assert small["epicentre"] == []
    assert small["coincident"] is True
    assert str(small["unavailable"])
    assert small["n_names"] == len(BLOCK) < MIN_NAMES


def test_the_coincident_label_travels_on_every_returned_read(monkeypatch) -> None:
    """`coincident` is on every record - the available read, the thin-book
    refusal and the gate-off refusal alike - because the index never claims to
    see a shift coming."""
    _gate(monkeypatch, on=True)
    panel = _panel()
    ok = triadic_stress(panel)
    thin = triadic_stress({name: panel[name] for name in BLOCK})

    _gate(monkeypatch, on=False)
    off = triadic_stress(panel)

    assert off["status"] == "unavailable"
    assert off["tsi"] is None
    assert "enable_triadic_stress" in off["unavailable"]
    for rec in (ok, thin, off):
        assert rec["coincident"] is True is COINCIDENT
        assert rec["label"] == LABEL


def test_a_thin_window_is_refused_with_its_window_reported(monkeypatch) -> None:
    """Ground rule 4: the read reports the window it was taken over and refuses
    one too thin to estimate a network from - the window travels with the
    refusal."""
    _gate(monkeypatch, on=True)
    rec = triadic_stress(_panel(bars=20))
    assert rec["status"] == "unavailable"
    assert rec["tsi"] is None
    assert rec["window"]["n_bars"] == 20 < MIN_OBS
    assert "bar" in rec["unavailable"]
    # and the gate-off read reports no window at all rather than a fake one
    _gate(monkeypatch, on=False)
    assert triadic_stress(_panel())["window"] is None
