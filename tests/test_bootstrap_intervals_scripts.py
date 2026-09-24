"""H11 (attachment half): the interval beside every claim statistic published.

The estimator half lives in ``strategies/conformal.py`` (``iid_interval`` /
``block_bootstrap_interval`` / ``block_length``). This half is the attachment:
every claim statistic ``scripts/score_panel.py`` and
``scripts/coverage_scorecard.py`` publish carries an interval over its OWN
series, with the block length that series' ACF decay earned (checked against an
ADF stationarity test) and the draw count beside the bounds, and ``unavailable``
- never a zero-width interval - below the floor.

The card's named mutation is the one this file is built to catch: making the
attachment use the IID interval (or pinning the block length) collapses every
series to the same dependence assumption and must fail
``test_the_block_length_is_not_a_constant_across_persistences`` by name.
"""

from __future__ import annotations

import json
import math
import random

import pytest

import scripts.coverage_scorecard as cs
import scripts.score_panel as sp

#: The config read each script performs lazily inside its own gate helper.
GET_CONFIG = "tradingagents.dataflows.config.get_config"

#: 200 dates x 30 names: clears the 40-observation interval floor and is long
#: enough that a persistent series earns a block longer than the ``n**(1/3)``
#: base length the rule falls back to.
N_DATES, N_NAMES = 200, 30
DATES = [f"2026-{i // 28 + 1:02d}-{i % 28 + 1:02d}" for i in range(N_DATES)]
NAMES = [f"N{i:02d}" for i in range(N_NAMES)]
TRUTH = {t: (i - N_NAMES / 2) / (N_NAMES / 2) for i, t in enumerate(NAMES)}


def _persistent_panel() -> dict:
    """A panel whose ``fcf_yield`` series is persistent and whose ``adx`` is not.

    Every name's close loads on one common AR(1) with ``rho = 0.9``, weighted by
    that name's own ``fcf_yield`` truth, so the top-minus-bottom decile spread -
    and the rank IC against it - track the AR(1) and stay autocorrelated.
    ``adx`` is independent noise per date, so its series do not. The two factors
    therefore differ in persistence and must earn different block lengths.
    """
    rng = random.Random(5)
    g = [0.0] * N_DATES
    for i in range(1, N_DATES):
        g[i] = 0.9 * g[i - 1] + rng.gauss(0.0, 1.0) * math.sqrt(1.0 - 0.81)
    closes: dict[str, list[float]] = {}
    for t in NAMES:
        close = 50.0
        path = [close]
        for i in range(1, N_DATES):
            close *= 1.0 + 0.002 * TRUTH[t] * g[i] + rng.gauss(0.0, 0.0005)
            path.append(close)
        closes[t] = path
    panel: dict = {}
    for i, date in enumerate(DATES):
        panel[date] = {
            t: {"fcf_yield": 0.05 * math.exp(0.3 * TRUTH[t]) + rng.gauss(0.0, 0.02),
                "adx": rng.gauss(0.0, 1.0),
                "close": closes[t][i]}
            for t in NAMES
        }
    return panel


@pytest.fixture(scope="module")
def reports():
    """``(gate-off, gate-on)`` reports over the same panel - built once."""
    panel = _persistent_panel()
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(GET_CONFIG, lambda: {})
        off = sp.evaluate_panel(panel, dates=DATES, n_boot=50)
        mp.setattr(GET_CONFIG, lambda: {"enable_bootstrap_intervals": True})
        on = sp.evaluate_panel(panel, dates=DATES, n_boot=50)
    finally:
        mp.undo()
    return off, on


def _gated(monkeypatch, on: bool = True):
    monkeypatch.setattr(GET_CONFIG, lambda: {"enable_bootstrap_intervals": on})


def _write_trees(root, n: int) -> None:
    """``n`` trees where ``rsi`` is absent every third tree (a non-constant rate).

    ``technical_score`` publishes presence by the complement rule (``absent``),
    and every other declared field stays present in every tree - a constant
    presence sequence, which the attachment must refuse rather than publish as a
    zero-width interval.
    """
    for i in range(n):
        d = root / f"T{i:03d}"
        d.mkdir(parents=True)
        card = {"technical_score": {"score": 10.0,
                                    "absent": ["rsi"] if i % 3 == 0 else []}}
        (d / cs.CARD_NAME).write_text(json.dumps(card), encoding="utf-8")


# ---------------------------------------------------------------------------
# (a) the axis is additive and default-off
# ---------------------------------------------------------------------------


def test_the_score_panel_gate_off_publishes_no_interval(reports):
    """Gate off: the report is the one it always was, byte for byte."""
    off, on = reports
    assert "interval" not in json.dumps(off)
    assert "interval" not in sp.render_text(off)
    # The gate only ADDS lines: stripping them from the gate-on text leaves the
    # gate-off text exactly.
    assert "interval" in sp.render_text(on)
    assert sp.render_text(off) == "\n".join(
        line for line in sp.render_text(on).splitlines() if "interval" not in line
    )


def test_the_scorecard_gate_off_publishes_no_interval(tmp_path):
    """Gate off: no interval key anywhere, and the rendered text is unchanged."""
    _write_trees(tmp_path, 45)
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(GET_CONFIG, lambda: {})
        off = cs.build_scorecard(str(tmp_path), engines=("technical_score",))
        mp.setattr(GET_CONFIG, lambda: {"enable_bootstrap_intervals": True})
        on = cs.build_scorecard(str(tmp_path), engines=("technical_score",))
    finally:
        mp.undo()
    assert "interval" not in json.dumps(off)
    assert "interval" not in cs.render_text(off)
    assert "interval" in cs.render_text(on)
    assert cs.render_text(off) == "\n".join(
        line for line in cs.render_text(on).splitlines() if "interval" not in line
    )


# ---------------------------------------------------------------------------
# (b) the interval travels beside the number, with its dependence assumption
# ---------------------------------------------------------------------------


def test_the_score_panel_carries_an_interval_beside_each_claim_statistic(reports):
    """Each factor's rank IC and spread, and the family summary, gain an interval."""
    off, on = reports
    measured = [f for f, row in on["factors"].items() if row.get("measured")]
    assert measured, "the fixture panel must measure at least one factor"
    for factor in measured:
        rows_on = on["factors"][factor]["rows"]
        rows_off = off["factors"][factor]["rows"]
        series = on["factors"][factor]["series"]
        for key, number, series_key in (("ic", "mean_rank_ic", "rank_ic"),
                                        ("deciles", "spread", "spread")):
            rec = rows_on[key]["interval"]
            assert rec["unavailable"] is None, (factor, key, rec)
            assert rec["low"] < rec["point"] < rec["high"], (factor, key, rec)
            assert rec["block"] >= 1 and rec["draws"] >= 10
            assert rec["n"] == len(series[series_key])
            assert rec["method"] == "moving-block"
            assert rec["iid"]["block"] == 1, "the IID baseline rides beside it"
            assert "period" in rec["window"], "the window is named (rule 4)"
            # the interval never REPLACES the number: it is unchanged
            assert rows_on[key][number] == rows_off[key][number]
    fam = on["family"]["interval"]
    assert fam["unavailable"] is None
    assert fam["low"] <= fam["point"] <= fam["high"] and fam["block"] >= 1
    assert "factor(s)" in fam["window"]


def test_the_scorecard_carries_an_interval_beside_each_fill_rate(tmp_path, monkeypatch):
    """Each field's published fill rate keeps its number and gains an interval."""
    _write_trees(tmp_path, 45)
    _gated(monkeypatch)
    report = cs.build_scorecard(str(tmp_path), engines=("technical_score",))
    field = report["engines"]["technical_score"]["fields"]["rsi"]
    rec = field["interval"]
    assert rec["unavailable"] is None
    assert rec["low"] <= rec["point"] <= rec["high"]
    assert rec["block"] >= 1 and rec["draws"] >= 10 and rec["n"] == 45
    assert rec["method"] == "moving-block" and rec["iid"]["block"] == 1
    assert "tree(s)" in rec["window"] and "scorecard order" in rec["window"]
    # the interval never replaces the rate it qualifies
    assert field["fill_rate"] == rec["point"]
    assert field["stated"] == rec["n"]


# ---------------------------------------------------------------------------
# (c) below the floor: `unavailable`, never a number and never a zero width
# ---------------------------------------------------------------------------


def test_a_series_below_the_floor_reads_unavailable_not_a_number(monkeypatch):
    """A 3-period series has no interval; the record says so instead of guessing."""
    short = {d: {f"A{i}": {"fcf_yield": float(i) + 0.1 * j,
                           "close": 10.0 + i + 0.5 * j}
                 for i in range(6)} for j, d in enumerate(DATES[:8])}
    _gated(monkeypatch)
    report = sp.evaluate_panel(short, dates=DATES[:8])
    assert report["factors"]["fcf_yield"]["series"]["rank_ic"], (
        "the floor, not an empty series, is what this test must exercise")
    for key in ("ic", "deciles"):
        row = report["factors"]["fcf_yield"]["rows"][key]
        rec = row["interval"]
        assert rec["unavailable"] and "floor" in rec["unavailable"], rec
        assert "low" not in rec and "high" not in rec
        assert "period" in rec["window"]


def test_the_scorecard_interval_reads_unavailable_below_the_floor(tmp_path, monkeypatch):
    """Five trees is below the floor: the record says so, with the window named."""
    _write_trees(tmp_path, 5)
    _gated(monkeypatch)
    report = cs.build_scorecard(str(tmp_path), engines=("technical_score",))
    rec = report["engines"]["technical_score"]["fields"]["rsi"]["interval"]
    assert rec["unavailable"] and "floor" in rec["unavailable"]
    assert "low" not in rec and "high" not in rec
    assert "tree(s)" in rec["window"]


def test_a_constant_series_is_never_published_as_a_zero_width_interval(tmp_path, monkeypatch):
    """A field present in every tree has no dispersion to resample: refuse it."""
    _write_trees(tmp_path, 45)
    _gated(monkeypatch)
    report = cs.build_scorecard(str(tmp_path), engines=("technical_score",))
    fields = report["engines"]["technical_score"]["fields"]
    assert fields["adx"]["fill_rate"] == 1.0
    rec = fields["adx"]["interval"]
    assert rec["unavailable"] and "dispersion" in rec["unavailable"]
    assert "low" not in rec and "high" not in rec


# ---------------------------------------------------------------------------
# (d) the block length is chosen from the series, not a constant
# ---------------------------------------------------------------------------


def test_the_block_length_is_not_a_constant_across_persistences(reports):
    """The persistent factor earns a longer block than the independent one.

    Substituting the IID interval (block 1 everywhere) or pinning the block to a
    constant collapses the two and fails this test by name.
    """
    _off, on = reports
    persistent = on["factors"]["fcf_yield"]["rows"]["deciles"]["interval"]
    independent = on["factors"]["adx"]["rows"]["deciles"]["interval"]
    assert persistent["block"] > independent["block"] > 0
    ic_persistent = on["factors"]["fcf_yield"]["rows"]["ic"]["interval"]
    ic_independent = on["factors"]["adx"]["rows"]["ic"]["interval"]
    assert ic_persistent["block"] > ic_independent["block"]
    # both series are the SAME length, so the difference is persistence, not n
    assert persistent["n"] == independent["n"]
    # the IID baseline is flat at block 1 for both - which is why the block arm
    # is the one that is published
    assert independent["iid"]["block"] == 1 == ic_independent["iid"]["block"]


# ---------------------------------------------------------------------------
# the render shows what the width cannot
# ---------------------------------------------------------------------------


def test_the_rendered_reports_show_the_block_length_and_the_draw_count(reports, tmp_path):
    """The dependence assumption is the thing a reader cannot recover from the width."""
    _off, on = reports
    text = sp.render_text(on)
    assert "block=" in text and "draws=" in text and "iid baseline" in text
    _write_trees(tmp_path, 45)
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(GET_CONFIG, lambda: {"enable_bootstrap_intervals": True})
        card_text = cs.render_text(
            cs.build_scorecard(str(tmp_path), engines=("technical_score",)))
    finally:
        mp.undo()
    assert "block=" in card_text and "draws=" in card_text
    assert "unavailable" in card_text, "the refused rows state why"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
