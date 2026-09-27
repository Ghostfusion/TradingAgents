"""The SEC filings producer: one fetch, two readers.

`recent_filing_forms` is the structured producer behind both `get_sec_filings`'
markdown and the form vocabulary `news_score.corporate_events_score` types
(NEWS-4). Offline: the submissions payload is supplied, so no EDGAR request is
made.

The four tests defend what a plausible bug would break - a form dropped before
the caller can type it, the label filter leaking into the structured producer, a
missing CIK silently returning an empty list, and `limit` being ignored.
"""

from __future__ import annotations

import pytest

from tradingagents.dataflows import sec_edgar
from tradingagents.dataflows.errors import NoMarketDataError

pytestmark = pytest.mark.timeout(600)


def _payload():
    return {
        "sic": "3674",
        "sicDescription": "Semiconductors",
        "filings": {
            "recent": {
                "form": ["8-K", "4", "10-Q", "SC 13G"],
                "filingDate": ["2026-09-02", "2026-09-01", "2026-08-30", "2026-08-20"],
                "accessionNumber": [
                    "0001-26-000001",
                    "0001-26-000002",
                    "0001-26-000003",
                    "0001-26-000004",
                ],
                "primaryDocument": ["a.htm", "b.xml", "c.htm", "d.htm"],
            }
        },
    }


@pytest.fixture()
def _filer(monkeypatch):
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: "320193")
    monkeypatch.setattr(sec_edgar, "_json_get", lambda url, retries=2: _payload())


def test_rows_carry_every_form_not_only_the_labelled_ones(_filer):
    """The typing decision belongs to the caller: a form `get_sec_filings`
    filters out of its prose (form 4) must still reach the event table, which
    ignores what it cannot type rather than defaulting it."""
    rows = sec_edgar.recent_filing_forms("AAPL")

    assert [r["form"] for r in rows] == ["8-K", "4", "10-Q", "SC 13G"]
    assert rows[0]["date"] == "2026-09-02"
    # the accession loses its dashes, as the URL builder expects
    assert rows[0]["accession"] == "000126000001"
    assert rows[0]["url"].endswith("/000126000001/a.htm")


def test_limit_caps_the_rows(_filer):
    assert len(sec_edgar.recent_filing_forms("AAPL", limit=2)) == 2


def test_the_markdown_still_filters_to_labelled_forms(_filer):
    """The render keeps its own contract: labelled forms only, and the note that
    says so when the window held nothing else."""
    out = sec_edgar.get_sec_filings("AAPL")

    assert "8-K" in out and "10-Q" in out
    assert "form 4" not in out and "**4**" not in out


def test_a_missing_cik_is_typed_no_data(monkeypatch):
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: None)
    with pytest.raises(NoMarketDataError):
        sec_edgar.recent_filing_forms("0700.HK")
