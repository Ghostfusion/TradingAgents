"""Tests for the industry-depth additions (spec: fulltext + patents).

Covers the SEC EDGAR full-text-search renderer and the USPTO PatentsView
patent-activity aggregation + key-gate, via monkeypatched network/name
lookups. Router/exports are covered by the wiring gate.
"""

import pytest

import tradingagents.dataflows.patentsview as pv
from tradingagents.dataflows.sec_edgar import get_edgar_fulltext_search

pytestmark = pytest.mark.timeout(90)

# ---------------------------------------------------------------------------
# EDGAR full-text search
# ---------------------------------------------------------------------------


def _hit(src):
    return {"_source": src}


def test_fulltext_renders_hits(monkeypatch):
    data = {
        "hits": {
            "total": {"value": 1234, "relation": "gte"},
            "hits": [
                _hit({"file_date": "2024-02-01", "form": "10-K",
                      "display_names": ["ACME CORP (ACME) (CIK 0000123456)"],
                      "adsh": "0000000000-24-000001"}),
                _hit({"file_date": "2023-08-15", "form": "10-Q",
                      "display_names": ["OTHER CO (OTH) (CIK 0000999999)"],
                      "adsh": "1"}),
            ],
        }
    }
    monkeypatch.setattr("tradingagents.dataflows.sec_edgar._json_get", lambda url: data)
    out = get_edgar_fulltext_search('"major customer"', forms="10-K,10-Q", limit=2)
    assert "2024-02-01 10-K — ACME CORP" in out
    assert "Total matches: 1234" in out


def test_fulltext_no_hits_honest(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.sec_edgar._json_get",
                        lambda url: {"hits": {"total": None, "hits": []}})
    out = get_edgar_fulltext_search("zzz_nonexistent_phrase")
    assert "No matching filings" in out


def test_fulltext_degrades(monkeypatch):
    monkeypatch.setattr("tradingagents.dataflows.sec_edgar._json_get",
                        lambda url: (_ for _ in ()).throw(ConnectionError("down")))
    out = get_edgar_fulltext_search("x")
    assert "unavailable" in out


# ---------------------------------------------------------------------------
# PatentsView
# ---------------------------------------------------------------------------


def _patent(num, date, title):
    return {"patent_number": num, "patent_date": date, "patent_title": title}


def _fake_post(patents, status=200):
    class _Resp:
        status_code = status

        def raise_for_status(self):
            if status >= 400:
                raise RuntimeError(f"HTTP {status}")

        def json(self):
            return {"patents": patents}

    return lambda *a, **k: _Resp()


def test_patent_activity_aggregates_by_year(monkeypatch):
    monkeypatch.setattr(pv, "pv_key", lambda: "testkey")
    monkeypatch.setattr(pv, "_company_name", lambda ticker: "Apple Inc.")
    monkeypatch.setattr(
        "requests.post",
        _fake_post([_patent("1", "2024-03-01", "Widget A"),
                    _patent("2", "2024-07-15", "Widget B"),
                    _patent("3", "2023-11-20", "Gadget")]),
    )
    out = pv.get_patent_activity("AAPL")
    assert "2024: 2 granted" in out
    assert "2023: 1 granted" in out
    assert "Widget A" in out
    assert "name-based" in out.lower()


def test_patent_activity_requires_key(monkeypatch):
    monkeypatch.setattr(pv, "pv_key", lambda: None)
    out = pv.get_patent_activity("AAPL")
    assert "PATENTSVIEW_API_KEY not set" in out


def test_patent_activity_no_records_honest(monkeypatch):
    monkeypatch.setattr(pv, "pv_key", lambda: "k")
    monkeypatch.setattr(pv, "_company_name", lambda ticker: "UNKNOWN CO")
    monkeypatch.setattr("requests.post", _fake_post([]))
    out = pv.get_patent_activity("XYZ")
    assert "no PatentsView records" in out


def test_patent_activity_degrades(monkeypatch):
    monkeypatch.setattr(pv, "pv_key", lambda: "k")
    monkeypatch.setattr(pv, "_company_name", lambda ticker: "X")
    monkeypatch.setattr("requests.post",
                        lambda *a, **k: (_ for _ in ()).throw(TimeoutError("t")))
    out = pv.get_patent_activity("AAPL")
    assert "unavailable" in out
