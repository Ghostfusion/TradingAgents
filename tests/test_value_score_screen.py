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

# Every test file carries a deadline (AGENT_ONBOARDING rule 5). 600s, not the
# sibling script tests' 120s: the technical-cut tests import the module that
# produces the components (``analysis_tools``), and a file-level deadline
# overrides --timeout, so a cold interpreter has to fit inside it (a cold start
# spends 280-400s in conftest alone).
pytestmark = pytest.mark.timeout(600)


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


# --- the two cuts: 50 fundamental, 50 technical -----------------------------
#
# The owner set the fundamental cut at 50 (it was 64) and added a technical cut
# at 50. The contract these tests defend is that the technical column can never
# be read as a PASS when it was never measured: the engine's own rule is that
# `NA` is not `0`, and a cut that treated a missing composite as a pass would
# report an unmeasured name as a qualified one.


def test_the_default_fundamental_cut_is_fifty():
    """The owner's number, pinned where the CLI reads it."""
    assert vss.DEFAULT_FUNDAMENTAL_SCORE_MIN == 50.0


def test_the_fundamental_cut_is_spelled_fundamental_score_min():
    """The old `--score-min` spelling must be GONE, not silently accepted.

    The sibling adapter once shipped `value_screener.py`'s `--max-chg5d` /
    `--max-rsi` spellings for this script, and argparse exited 2 only after the
    job had been queued. A rename has the same failure mode, so the new spelling
    is exercised and the old one is pinned as rejected.
    """
    assert vss.main(["--offline-demo", "--fundamental-score-min", "70"]) == 0
    with pytest.raises(SystemExit) as err:
        vss.main(["--offline-demo", "--score-min", "70"])
    assert err.value.code == 2


def test_the_technical_default_is_the_engines_own_neutral_edge():
    """50 is not a free research cut - it is `TECH_BANDS`' own `neutral` edge."""
    from tradingagents.strategies.score_engine import band_label
    from tradingagents.strategies.technical_score import TECH_BANDS

    assert vss.DEFAULT_TECH_SCORE_MIN == 50.0
    assert band_label(vss.DEFAULT_TECH_SCORE_MIN, TECH_BANDS) == "neutral"


def _tech_args(**kw):
    """The arg surface `render` reads, with both cuts at their defaults."""
    base = {
        "date": "2026-09-24", "exchanges": "NYSE,NASDAQ", "min_mcap": 10e9,
        "pe_max": 33.0, "pb_max": 9.0, "ps_max": 8.0, "pcf_max": 25.0,
        "max_chg": -2.0, "roe_min": 0.0, "chg5d_max": 0.0, "rsi_max": 0.0,
        "no_moomoo": False, "show_excluded": True,
        "fundamental_score_min": vss.DEFAULT_FUNDAMENTAL_SCORE_MIN,
        "tech_score_min": vss.DEFAULT_TECH_SCORE_MIN,
    }
    base.update(kw)
    return types.SimpleNamespace(**base)


def _section(text: str, title: str) -> str:
    """The body of ``### {title}``, up to the next ``###`` heading."""
    marker = f"### {title}"
    start = text.index(marker)
    rest = text[start + len(marker):]
    nxt = rest.find("\n### ")
    return rest if nxt < 0 else rest[:nxt]


def _rows(*symbols):
    """Candidate rows with the two fields `render` reads off them."""
    return [{"symbol": s, "ratios": {}} for s in symbols]


_BOTH = "Clear both cuts (50 fundamental, 50 technical)"


def test_a_measured_score_below_the_cut_is_not_a_qualifier():
    """The technical cut's own side of the gate: measured, and below 50."""
    out = vss.render(
        _rows("PASS", "BELOW"), {"PASS": 80.0, "BELOW": 80.0}, {}, {},
        _tech_args(), "", "panel",
        tech={"PASS": {"score": 70.0, "band": "constructive"},
              "BELOW": {"score": 30.0, "band": "weak"}},
        tech_withheld={},
    )

    assert "| PASS " in _section(out, _BOTH)
    assert "| BELOW " not in _section(out, _BOTH)
    assert "| BELOW " in _section(
        out, "Cleared the fundamental cut, below the 50 technical cut")


def test_an_unmeasured_technical_score_is_withheld_never_passed():
    """`NA` is not `0` - and it is not a pass either.

    A name whose composite was never measured must not appear as qualified, and
    the reason printed for it must be the engine's, not a fabricated number.
    """
    out = vss.render(
        _rows("GAP", "PASS"), {"GAP": 80.0, "PASS": 80.0}, {}, {},
        _tech_args(), "", "panel",
        tech={"PASS": {"score": 70.0, "band": "constructive"}},
        tech_withheld={"GAP": "no component measurable from the run's bars"},
    )

    assert "| GAP " not in _section(out, _BOTH)
    withheld = _section(out, "Withheld - no TechnicalScore")
    assert "| GAP " in withheld
    assert "no component measurable" in withheld


def test_the_technical_cut_is_off_at_zero():
    """``--tech-score-min 0`` disables the pass, and the column reads `n/a`."""
    out = vss.render(
        _rows("ONLY"), {"ONLY": 80.0}, {}, {}, _tech_args(tech_score_min=0.0),
        "", "panel", tech={}, tech_withheld={},
    )

    assert "| ONLY " in _section(out, "Clear the 50 cut")
    assert "and TechnicalScore" not in out.splitlines()[0]


def test_the_report_names_both_cuts_in_its_title():
    """A reader must see both gates without reading the engine."""
    def title(**kw):
        out = vss.render(_rows("A"), {"A": 80.0}, {}, {}, _tech_args(**kw), "",
                         "panel", tech={"A": {"score": 70.0}}, tech_withheld={})
        return out.splitlines()[0]

    assert "and TechnicalScore >= 50" in title()
    assert "and TechnicalScore >= 50" not in title(tech_score_min=0.0)


def _patch_components(monkeypatch, fn):
    """Patch the component producer at its own module (it is imported lazily)."""
    import tradingagents.agents.utils.analysis_tools as at

    monkeypatch.setattr(at, "_technical_components", fn)


def _patch_score(monkeypatch, fn):
    """Patch the composite at its own module (imported lazily inside the stage)."""
    import tradingagents.strategies.technical_score as ts

    monkeypatch.setattr(ts, "technical_score", fn)


def test_stage_technical_reads_the_engines_own_components_and_composite(monkeypatch):
    """No formula is re-derived here: the components and the score are the engine's."""
    _patch_components(monkeypatch, lambda sym: {"sma_stack": 1.0})
    _patch_score(monkeypatch, lambda vals, **kw: {
        "score": 62.5, "bands": "constructive", "coverage": 4})

    tech, withheld = vss.stage_technical(_rows("OK"))

    assert tech["OK"] == {"score": 62.5, "band": "constructive", "coverage": 4}
    assert withheld == {}


def test_stage_technical_never_invents_a_score_from_too_few_bars(monkeypatch):
    """Fewer than 30 bars -> withheld with the reason, never a 0 and never a 50."""
    _patch_components(monkeypatch, lambda sym: {})

    tech, withheld = vss.stage_technical(_rows("SHORT"))

    assert tech == {}
    assert "30 bars" in withheld["SHORT"]


def test_a_withheld_composite_keeps_the_engines_own_reason(monkeypatch):
    """Below the coverage floor the engine's words are the reason, not a guess."""
    _patch_components(monkeypatch, lambda sym: {"sma_stack": 1.0})
    _patch_score(monkeypatch, lambda vals, **kw: {
        "score": None, "withheld": "coverage 1 < 3"})

    tech, withheld = vss.stage_technical(_rows("THIN"))

    assert tech == {}
    assert withheld["THIN"] == "coverage 1 < 3"


def test_one_unmeasurable_name_never_aborts_the_screen(monkeypatch):
    """A producer failure on one name is that name's problem, not the run's."""
    def _boom(sym):
        raise RuntimeError("vendor down")

    _patch_components(monkeypatch, _boom)

    tech, withheld = vss.stage_technical(_rows("BAD", "BAD2"))

    assert tech == {}
    assert "vendor down" in withheld["BAD"]
    assert "vendor down" in withheld["BAD2"]


def test_zero_skips_the_technical_pass_entirely(tmp_path, monkeypatch):
    """The only value that costs no vendor call: the stage is never called."""
    out = tmp_path / "screener"
    monkeypatch.setattr(vss, "stage_decliners", lambda args: ({"AAPL": -3.0}, set()))
    monkeypatch.setattr(vss, "_fetch_fin_cached", lambda t, d: _fin())
    monkeypatch.setattr(
        vss, "stage_score",
        lambda args, fins: ({"AAPL": 70.0}, {}, "basis", {}, "note"),
    )
    monkeypatch.setattr(
        vss, "stage_technical",
        lambda kept: pytest.fail("the technical pass ran with the cut disabled"),
    )

    assert vss.main(["--no-moomoo", "--tech-score-min", "0",
                     "--out-dir", str(out), "-d", "2026-09-24"]) == 0


# --- the domicile gate: US-domiciled issuers only ---------------------------
#
# One predicate has to remove a foreign company AND its US-listed ADR, because
# every field this screen already holds fails to: the EODHD symbol list reports
# the EXCHANGE's country (USA for all 50,973 US rows), calls an ADR
# `Type == "Common Stock"`, and gives it a US-prefixed ISIN. The issuer's own
# country is the only column that separates them, so the gate reads it and
# fails CLOSED - a name whose country cannot be read is dropped, not assumed
# American, because the assumption IS the leak.


def _patch_country(monkeypatch, mapping):
    """Patch the issuer-country reader the gate imports lazily."""
    import tradingagents.dataflows.y_finance as yf_mod

    monkeypatch.setattr(yf_mod, "get_company_country_yfinance",
                        lambda sym: mapping.get(sym))


def test_the_domicile_gate_keeps_a_us_issuer_and_drops_an_adr(monkeypatch):
    """Domestic kept; a foreign issuer and its ADR both dropped by one rule."""
    _patch_country(monkeypatch, {
        "AAPL": "United States",     # domestic - kept
        "KSPI": "Kazakhstan",        # ADR, NYSE/Nasdaq listed - dropped
        "KOF": "Mexico",             # ADR - dropped
        "SHOP": "Canada",            # foreign ordinary - dropped
    })
    kept, dom = vss.stage_domicile(_tech_args(), [{"symbol": s} for s in
                                                  ("AAPL", "KSPI", "KOF", "SHOP")])

    assert [r["symbol"] for r in kept] == ["AAPL"]
    assert dom == {"foreign": 3, "unknown": 0}


def test_the_domicile_gate_fails_closed_when_the_country_cannot_be_read(monkeypatch):
    """No country is not evidence of a US country: dropped, and counted apart."""
    _patch_country(monkeypatch, {"AAPL": "United States", "MYSTERY": None})
    kept, dom = vss.stage_domicile(_tech_args(), [{"symbol": "MYSTERY"},
                                                  {"symbol": "AAPL"}])

    assert [r["symbol"] for r in kept] == ["AAPL"]
    assert dom == {"foreign": 0, "unknown": 1}, "unknown takes the fail-closed path"


def test_a_country_lookup_that_raises_is_unknown_not_american(monkeypatch):
    """One name's vendor failure never aborts the run, and never reads as US."""
    import tradingagents.dataflows.y_finance as yf_mod

    def _boom(sym):
        raise RuntimeError("yahoo 401")

    monkeypatch.setattr(yf_mod, "get_company_country_yfinance", _boom)

    kept, dom = vss.stage_domicile(_tech_args(), [{"symbol": "AAPL"}])

    assert kept == []
    assert dom == {"foreign": 0, "unknown": 1}


def test_a_us_country_variant_is_not_read_as_foreign():
    """A vendor spelling of the US must not silently drop a domestic name."""
    for name in ("United States", "united states of america", "USA", " us "):
        assert vss._is_us_domiciled(name) is True, name
    for name in ("", None, "Canada", "United Kingdom"):
        assert vss._is_us_domiciled(name) is False, name


def test_the_cli_declares_exclude_foreign():
    """The gate is reachable from the CLI the web adapter shells out to."""
    assert vss.main(["--offline-demo", "--exclude-foreign"]) == 0


def test_the_report_names_the_domicile_gate_only_when_it_is_on():
    """A reader must see the exclusion in the header, and never when it is off."""
    on = vss.render([], {}, {}, {}, _tech_args(exclude_foreign=True),
                    "", "", tech={}, tech_withheld={})
    off = vss.render([], {}, {}, {}, _tech_args(), "", "", tech={}, tech_withheld={})

    assert "US-domiciled issuers only" in on
    assert "US-domiciled issuers only" not in off
    assert "fails CLOSED" in on, "the report states the fail-closed rule"
    assert "fails CLOSED" not in off
