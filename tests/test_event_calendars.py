"""The forward company-event calendars (EventScore §4 / §7 Q5).

The vendor decision of 2026-09-18: pdufa.bio for FDA / clinical, CourtListener
for court, investor-day dropped. These tests are offline - every payload is
synthetic - and they hold the three properties the design turns on:

(a) only rows with an **announced day** become forward events, because pdufa.bio
    nulls ``date`` for every month / quarter / year estimate and a day-count
    built on a month midpoint would be an invented number;
(b) ``None`` (the question was not answered) never collapses into ``[]`` (it was
    answered and holds nothing) - the one mistake that turns "this source cannot
    carry a forward date" into the false claim "no event is scheduled";
(c) a source failure is a recorded reason, never a crash and never a zero.
"""

from __future__ import annotations

import os

import pytest

from tradingagents.dataflows import event_calendars as ec

# ---------------------------------------------------------------------------
# Synthetic pdufa.bio payloads
# ---------------------------------------------------------------------------


def _row(**kw) -> dict:
    base = {
        "id": "pdufa_x_2026-10-01", "ticker": "X", "company": "X Inc.",
        "date": "2026-10-01", "date_precision": "day", "date_month": "2026-10",
        "name": "Drug A", "type": "PDUFA", "status": "Upcoming",
        "indication": "Something", "source": "X 8-K", "source_url": "https://sec.gov/x",
        "url": "https://www.pdufa.bio/pdufa/X",
    }
    base.update(kw)
    return base


def _payload(rows) -> dict:
    return {"meta": {"total": len(rows)}, "data": rows}


def _patch(monkeypatch, payload):
    monkeypatch.setattr(ec, "_get_json", lambda url, params=None, timeout=25: payload)


# ---------------------------------------------------------------------------
# (a) the announced-day rule
# ---------------------------------------------------------------------------


def test_only_rows_with_an_announced_day_become_forward_events(monkeypatch) -> None:
    """The source's own 2026-09-09 breaking change: ``date`` is an announced day
    or null. A month-precision row carries a ``date_month`` and no day, and
    turning that into a day-count is exactly the fabrication this repo refuses."""
    _patch(monkeypatch, _payload([
        _row(date="2026-10-01", date_precision="day"),
        _row(date=None, date_precision="month", date_month="2027-10"),
        _row(date=None, date_precision="quarter", date_month="2027-04"),
        _row(date=None, date_precision="year", date_month="2027-01"),
    ]))
    rows = ec.fda_calendar_rows("X", "2026-09-18")
    assert rows is not None
    assert [r["date"] for r in rows] == ["2026-10-01"]


def test_a_decided_event_is_not_a_forward_catalyst(monkeypatch) -> None:
    """A row whose status says it already happened is excluded however its date
    reads: 'Decided' is not a pending catalyst."""
    _patch(monkeypatch, _payload([
        _row(status="Upcoming"), _row(status="Scheduled"),
        _row(status="Guided"), _row(status="Estimated"), _row(status="Awaiting"),
        _row(status="Decided"), _row(status="Reported"),
        _row(status="Ended"), _row(status="Held"),
    ]))
    rows = ec.fda_calendar_rows("X", "2026-09-18")
    assert rows is not None
    assert {r["status"] for r in rows} == ec.PDUFA_FORWARD_STATUSES
    assert len(rows) == 5


def test_the_payload_keeps_the_evidence_a_reviewer_needs(monkeypatch) -> None:
    _patch(monkeypatch, _payload([_row()]))
    rows = ec.fda_calendar_rows("X", "2026-09-18")
    assert rows is not None and len(rows) == 1
    row = rows[0]
    assert row["name"] == "Drug A" and row["type"] == "PDUFA"
    assert row["source"] == "X 8-K" and row["source_url"] == "https://sec.gov/x"
    assert row["url"].startswith("https://www.pdufa.bio/")


# ---------------------------------------------------------------------------
# (b) None is not []
# ---------------------------------------------------------------------------


def test_an_unreachable_source_is_none_and_an_empty_answer_is_a_list(monkeypatch) -> None:
    def _boom(url, params=None, timeout=25):
        raise OSError("network down")

    monkeypatch.setattr(ec, "_get_json", _boom)
    assert ec.fda_calendar_rows("X", "2026-09-18") is None, "the question was not answered"

    _patch(monkeypatch, _payload([]))
    assert ec.fda_calendar_rows("X", "2026-09-18") == [], "answered, and holds nothing"


def test_the_court_adapter_never_claims_no_event_is_scheduled() -> None:
    """CourtListener is a filing archive: its only date fields are backward.

    Returning ``[]`` would assert "this company has no scheduled court event",
    which nothing in the accessible data supports."""
    assert ec.court_calendar_rows("AAPL", "2026-09-18") is None
    assert "CourtListener" in ec.COURT_REASON
    assert "backward-looking" in ec.COURT_REASON


def test_the_investor_day_family_records_the_decision_not_an_omission() -> None:
    assert "DROPPED" in ec.INVESTOR_DAY_REASON
    assert "no free source" in ec.INVESTOR_DAY_REASON


# ---------------------------------------------------------------------------
# The interface mapping
# ---------------------------------------------------------------------------


def test_the_event_types_map_onto_the_two_engine_interfaces(monkeypatch) -> None:
    """PDUFA is the product's route to market; readouts, AdComm and conference
    presentations are clinical readouts. Both land in ``product_clinical``."""
    _patch(monkeypatch, _payload([
        _row(type="PDUFA", date="2026-10-01"),
        _row(type="Readout", date="2026-10-02"),
        _row(type="AdComm", date="2026-10-03"),
        _row(type="Conference", date="2026-10-04"),
    ]))
    got = ec.company_event_calendars("X", "2026-09-18")
    assert [r["type"] for r in got["product"]] == ["PDUFA"]
    assert {r["type"] for r in got["clinical"]} == {"Readout", "AdComm", "Conference"}
    assert got["court"] is None and got["investor_day"] is None


def test_every_pdufa_type_the_source_publishes_has_an_interface() -> None:
    """The four types pdufa.bio served live on 2026-09-18. An unmapped type would
    be dropped silently, which is a coverage hole rather than a decision."""
    assert set(ec.PDUFA_INTERFACE) == {"PDUFA", "Readout", "AdComm", "Conference"}
    assert set(ec.PDUFA_INTERFACE.values()) <= set(ec.CALENDAR_FAMILIES)


def test_the_calendar_families_are_the_four_declared_interfaces() -> None:
    assert ec.CALENDAR_FAMILIES == ("product", "clinical", "court", "investor_day")


# ---------------------------------------------------------------------------
# (c) coverage: the undated share is stated, never hidden
# ---------------------------------------------------------------------------


def test_coverage_states_the_undated_share(monkeypatch) -> None:
    """336 of pdufa.bio's 456 live rows carry no announced day. A family that
    reported '0 events' without saying 'of 6 rows, 5 undated' would read as an
    absence of catalysts rather than an absence of dates."""
    _patch(monkeypatch, _payload([
        _row(date="2026-10-01"), _row(date=None, date_precision="month"),
        _row(date=None, date_precision="month"), _row(date=None, date_precision="quarter"),
        _row(date=None, date_precision="month"), _row(date=None, date_precision="year"),
    ]))
    cov = ec.calendar_coverage("X", "2026-09-18")
    assert cov["reachable"] is True
    assert cov["rows_held"] == 6 and cov["rows_with_announced_day"] == 1
    assert cov["rows_undated"] == 5
    assert cov["source"] == "pdufa.bio" and cov["attribution"]


def test_coverage_of_an_unreachable_source_says_so(monkeypatch) -> None:
    def _boom(url, params=None, timeout=25):
        raise OSError("network down")

    monkeypatch.setattr(ec, "_get_json", _boom)
    cov = ec.calendar_coverage("X", "2026-09-18")
    assert cov["reachable"] is False
    assert cov["rows_held"] == 0 and cov["rows_undated"] == 0
    assert cov["families"]["court"] == ec.COURT_REASON


def test_an_empty_ticker_never_reaches_the_network(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(ec, "_get_json", lambda *a, **k: calls.append(a) or {})
    assert ec.fda_calendar_rows("", "2026-09-18") is None
    assert calls == []


# ---------------------------------------------------------------------------
# The live finding stays re-verifiable
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_the_court_finding_can_be_re_verified_live() -> None:
    """Opt-in, because it leaves the machine. The reason above is a claim about a
    third party's API, so it is kept as a callable rather than as prose that
    could quietly go stale: run with ``TRADINGAGENTS_LIVE_NETWORK_TESTS=1``."""
    if not os.environ.get("TRADINGAGENTS_LIVE_NETWORK_TESTS"):
        pytest.skip("set TRADINGAGENTS_LIVE_NETWORK_TESTS=1 to re-verify live")
    probe = ec.court_probe("Apple Inc")
    if not probe.get("reachable"):
        pytest.skip(f"CourtListener unreachable: {probe.get('error')}")
    assert probe["date_fields"] == ["dateArgued", "dateFiled", "dateTerminated"]
    assert probe["future_dated"] == [], "a forward date would invalidate COURT_REASON"
