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
