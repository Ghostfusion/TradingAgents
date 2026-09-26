"""The value screen's scoring stage: WHICH panel the composite ranks against.

Offline by construction. ``stage_score`` reads a panel *file* and calls
``fundamental_score`` over the rows it finds; it reaches no vendor seam, so
there is no transport to mock here - and the cache dir is redirected to a temp
dir, so no real panel file is read or written.

The contract these tests defend is the one that changes what the number means:
the percentile is relative to the panel *given*, and a candidate the panel does
not carry is refused by name rather than silently ranked against the others.
"""

import json
import types

import pytest

import scripts.score_panel as sp
import scripts.value_score_screen as vss

# Every test file carries a deadline (AGENT_ONBOARDING rule 5); 120s is what the
# sibling script tests use.
pytestmark = pytest.mark.timeout(120)


def _fixture(n: int) -> dict:
    """The suite's rising cross-section (the same fixture ``offline_demo`` uses).

    FQS's six keys + VS's three, so every sub-score has what it needs and the
    composite is computable without a vendor.
    """
    return {
        f"N{i:02d}": {
            "f": float(i),
            "m": float(n - i),
            "gp_a": 0.30 + i / 100.0,
            "noa": 0.10 * i,
            "accruals": -0.02 * i,
            "return_on_equity": 0.05 + i / 100.0,
            "ev_ebit": 30.0 - i,
            "price_to_earnings": 40.0 - 2 * i,
            "earnings_yield": 0.02 + i / 200.0,
        }
        for i in range(n)
    }


@pytest.fixture
def panel_cache(tmp_path, monkeypatch):
    """A temp panel cache; ``write(date, n)`` puts an ``n``-name panel in it."""
    monkeypatch.setattr(sp, "default_cache_dir", lambda: str(tmp_path))

    def write(date: str, n: int) -> None:
        payload = _fixture(n)
        payload[sp.META_KEY] = {"built": "test-fixture", "n": n}
        path = tmp_path / sp.PANELS_DIRNAME / f"{date}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    return write


def _args(panel: str | None):
    return types.SimpleNamespace(panel=panel, date=panel or "2026-09-24")


def test_the_built_panel_is_the_peer_set_not_the_names_in_hand(panel_cache):
    """A 2-name cross-section over a 40-name panel scores the 40, not the 2."""
    panel_cache("1900-01-01", 40)

    scores, withheld, _basis, _subs, note = vss.stage_score(
        _args("1900-01-01"), {"AAA": {}, "N07": {}}
    )

    assert sum(1 for v in scores.values() if v is not None) == 40
    assert sp.META_KEY not in scores, "the reserved key is not a ticker"
    assert "40" in note and "1900-01-01" in note
    assert "AAA" in withheld


def test_the_same_candidate_is_ranked_against_the_panel_it_is_given(panel_cache):
    """Widening the panel changes the percentile - the whole point of --panel."""
    panel_cache("1900-01-01", 40)
    panel_cache("1900-01-02", 10)

    wide = vss.stage_score(_args("1900-01-01"), {"N07": {}})[0]["N07"]
    narrow = vss.stage_score(_args("1900-01-02"), {"N07": {}})[0]["N07"]

    assert wide is not None and narrow is not None
    assert wide != narrow, "the panel argument is not reaching the composite"


def test_a_candidate_absent_from_the_panel_is_refused_by_name(panel_cache):
    """Never scored as 0, and never silently dropped: the reason names the date."""
    panel_cache("1900-01-01", 40)

    scores, withheld, _basis, _subs, _note = vss.stage_score(
        _args("1900-01-01"), {"AAA": {}, "N07": {}}
    )

    assert scores.get("AAA") is None
    assert "1900-01-01" in withheld["AAA"]


def test_a_missing_panel_file_falls_back_and_says_so(panel_cache, caplog):
    """The denominator must never change silently: the note and the log both say."""
    with caplog.at_level("WARNING"):
        _scores, withheld, _basis, _subs, note = vss.stage_score(
            _args("1999-12-31"), {"ONLY": {}}
        )

    assert "1999-12-31" in note
    assert any("panel" in r.message.lower() for r in caplog.records)
    assert withheld["ONLY"], "the fallback still explains why nothing scored"


# --- the funnel's counters and the report's own file kind -------------------
#
# Both come from one measured run (2026-09-25, from the web app): the funnel
# line read "candidates 60 -> passed the ratio gates 0" beside 43 counted drops,
# and the report the reader opened was a Value Watchlist - the SCREENER's column
# set - because whichever screen ran last deleted the other's file.


def _fin(market_cap: float = 20e9) -> dict:
    """A canonical fin whose four ratio gates all pass at the panel's bounds."""
    return {
        "market_cap": market_cap,
        "revenue": 4e9,
        "operating_cashflow": 1e9,
        "net_income": 2e9,
        "total_equity": 10e9,
        "shares_outstanding": 1e8,
    }


def _ratio_args(**kw):
    base = {"limit": 10, "date": "2026-09-24", "ps_max": 8.0, "pcf_max": 25.0,
            "pe_max": 33.0, "pb_max": 9.0, "min_mcap": 10e9}
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_a_name_below_the_cap_floor_is_counted_not_silently_dropped(monkeypatch):
    """Every drop is counted, so the funnel line reconciles with the candidates."""
    monkeypatch.setattr(vss, "_fetch_fin_cached", lambda t, d: _fin(market_cap=4e9))

    kept, _fins, fails = vss.stage_ratios(
        _ratio_args(), [{"symbol": "SMALL", "price": 20.0}], {"SMALL": -3.0}
    )

    assert kept == []
    assert fails["cap"] == 1


def test_a_name_that_passes_every_gate_is_kept_and_uncounted(monkeypatch):
    """The counter's other side: a survivor is kept, not counted as a drop."""
    monkeypatch.setattr(vss, "_fetch_fin_cached", lambda t, d: _fin())

    kept, fins, fails = vss.stage_ratios(
        _ratio_args(), [{"symbol": "BIG", "price": 20.0}], {"BIG": -3.0}
    )

    assert [r["symbol"] for r in kept] == ["BIG"]
    assert fins["BIG"]["market_cap"] == 20e9
    assert sum(fails.values()) == 0


def test_the_report_lands_under_its_own_prefix_and_spares_the_sibling(
    tmp_path, monkeypatch
):
    """A Value screen report never takes the Screener's file, or its name space."""
    out = tmp_path / "screener"
    out.mkdir(parents=True, exist_ok=True)
    sibling = out / "watchlist_20260102_101112.md"
    sibling.write_text("# Value Watchlist\n", encoding="utf-8")
    monkeypatch.setattr(vss, "stage_decliners", lambda args: ({"AAPL": -3.0}, set()))
    monkeypatch.setattr(vss, "_fetch_fin_cached", lambda t, d: _fin())
    monkeypatch.setattr(
        vss, "stage_score",
        lambda args, fins: ({"AAPL": 70.0}, {}, "basis", {}, "note"),
    )

    assert vss.main(["--no-moomoo", "--out-dir", str(out), "-d", "2026-09-24"]) == 0

    written = sorted(p.name for p in out.glob("value_score_*.md"))
    assert len(written) == 1, written
    assert sibling.exists(), "the Screener's report is not the Value screen's to delete"
