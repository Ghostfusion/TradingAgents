"""Tests for the fundamentals-analyst enhancements (Phase: spec gaps 1-3).

Covers the congressional-trade normalizer/renderer (monkeypatched rows), the
FMP transcript block + report wrapper (monkeypatched fmp_get), and the SEC
EDGAR XBRL annual-history loader (monkeypatched _json_get). Network paths are
live-verified separately; these pin the pure logic.
"""

import pytest

import tradingagents.dataflows.congress as congress
import tradingagents.dataflows.fmp as fmp
import tradingagents.dataflows.sec_edgar as sec_edgar
from tradingagents.dataflows.errors import NoMarketDataError

pytestmark = pytest.mark.timeout(90)

# ---------------------------------------------------------------------------
# Congress
# ---------------------------------------------------------------------------


def test_classify_covers_watcher_types():
    assert congress._classify("Purchase") == "P"
    assert congress._classify("Sale (Full)") == "S"
    assert congress._classify("Exchange") == "X"
    assert congress._classify("Transfer") == "X"
    assert congress._classify("Bogus") == "?"


def test_filter_rows_only_open_market_matched():
    rows = [
        {"ticker": "NVDA", "type": "Purchase", "amount": "$1,001 - $15,000",
         "transaction_date": "08/01/2026", "owner": "Self", "representative": "Rep"},
        {"ticker": "NVDA", "type": "Sale (Full)", "amount": "$15,001 - $50,000",
         "transaction_date": "07/01/2026"},
        {"ticker": "NVDA", "type": "Exchange", "amount": "$50,001 - $100,000",
         "transaction_date": "06/01/2026"},  # not open-market -> dropped
        {"ticker": "AAPL", "type": "Purchase", "amount": "$1,001 - $15,000",
         "transaction_date": "05/01/2026"},  # wrong ticker -> dropped
        {"ticker": "NVDA", "type": "Purchase", "amount": None, "amount_mid": None,
         "transaction_date": "04/01/2026"},  # no amount -> dropped
    ]
    got = congress._filter_rows(rows, "nvda")
    assert [(r["ticker"], r["type"]) for r in got] == [("NVDA", "P"), ("NVDA", "S")]
    assert got[0]["name"] == "Rep"  # date desc order + representative name


def test_net_summary_counts():
    s = congress._net_summary(
        [{"type": "P"}, {"type": "P"}, {"type": "S"}, {"type": "P"}, {"type": "S"}]
    )
    assert s == {"buys": 3, "sells": 2, "net": 1}


def test_get_congress_trades_no_ticker_no_network():
    out = congress.get_congress_trades("")
    assert isinstance(out, str) and "unavailable" in out


def test_get_congress_trades_renders_both_chambers(monkeypatch):
    rows = [
        {"ticker": "NVDA", "type": "Purchase", "amount": "$1,001 - $15,000",
         "transaction_date": "08/01/2026", "representative": "Rep A"},
        {"ticker": "NVDA", "type": "Sale (Full)", "amount": "$15,001 - $50,000",
         "amount_mid": 30000, "transaction_date": "07/01/2026", "senator": "Sen B"},
    ]
    monkeypatch.setattr(congress, "_cached_rows", lambda key, url: rows)
    out = congress.get_congress_trades("nvda", limit=5)
    assert isinstance(out, str)
    assert "**House**" in out and "**Senate**" in out
    assert "net +" in out
    assert "Rep A" in out and "Sen B" in out


# ---------------------------------------------------------------------------
# FMP transcript
# ---------------------------------------------------------------------------


def _transcript_rows():
    return [{"symbol": "AAPL", "date": "2025-10-30", "year": 2025, "quarter": 4}]


def test_transcript_block_with_content(monkeypatch):
    calls = {}

    def fake_get(path, params):
        calls[path] = params
        if path == "earning_call_transcripts":
            return _transcript_rows()
        return {"content": "Operator: welcome. Tim Cook: guidance raised..." * 200}

    monkeypatch.setattr(fmp, "fmp_get", fake_get)
    blk = fmp.get_earnings_transcript_fmp("AAPL")
    assert blk is not None and blk["year"] == 2025 and blk["quarter"] == 4 and blk["content_len"] > 3500
    assert blk["excerpt"].startswith("Operator: welcome.")


def test_transcript_block_metadata_only_when_body_missing(monkeypatch):
    def fake_get(path, params):
        if path == "earning_call_transcripts":
            return _transcript_rows()
        return None  # single-transcript fetch fails (quota/coverage)

    monkeypatch.setattr(fmp, "fmp_get", fake_get)
    blk = fmp.get_earnings_transcript_fmp("AAPL")
    assert blk is not None and blk["content_len"] == 0 and blk["excerpt"] == ""


def test_transcript_block_none_on_failure(monkeypatch):
    monkeypatch.setattr(fmp, "fmp_get", lambda path, params: None)
    assert fmp.get_earnings_transcript_fmp("AAPL") is None


def test_transcript_report_states_body_missing(monkeypatch):
    def fake_get(path, params):
        if path == "earning_call_transcripts":
            return _transcript_rows()
        return None

    monkeypatch.setattr(fmp, "fmp_get", fake_get)
    out = fmp.get_earnings_transcript_report("AAPL")
    assert "Q4 FY2025" in out and "do not fabricate" in out


# ---------------------------------------------------------------------------
# SEC EDGAR XBRL financial history
# ---------------------------------------------------------------------------


def _concept(end, val, start=None, form="10-K", fp="FY"):
    row = {"end": end, "val": val, "form": form, "fp": fp}
    if start:
        row["start"] = start
    return row


def _payload(rows):
    return {"units": {"USD": rows}}


def test_xbrl_annual_filter_drops_partial_and_keeps_instant(monkeypatch):
    def fake_json_get(url):
        tag = url.rsplit("/", 1)[-1]
        if tag == "RevenueFromContractWithCustomerExcludingAssessedTax.json":
            # full FY + a 90-day partial restatement under the same end
            return _payload([
                _concept("2020-09-26", 274_515_000_000, start="2019-09-28"),
                _concept("2020-09-26", 64_698_000_000, start="2020-06-28"),
            ])
        if tag == "Assets.json":
            return _payload([_concept("2020-09-26", 323_888_000_000)])  # instant: no start
        return _payload([])

    monkeypatch.setattr(sec_edgar, "_json_get", fake_json_get)
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: "320193")
    out = sec_edgar.get_financial_history("AAPL", years=3)
    # full-year revenue wins (not the 90-day partial), assets renders
    assert "274.5B" in out and "64.7B" not in out
    assert "323.9B" in out


def test_xbrl_raises_on_no_facts(monkeypatch):
    monkeypatch.setattr(sec_edgar, "_json_get", lambda url: _payload([]))
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: "320193")
    with pytest.raises(NoMarketDataError):
        sec_edgar.get_financial_history("XYZ")


def test_xbrl_raises_on_unknown_ticker(monkeypatch):
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: None)
    with pytest.raises(NoMarketDataError):
        sec_edgar.get_financial_history("NOTREAL")


def test_xbrl_fetch_logs_and_continues_on_single_tag_failure(monkeypatch, caplog):
    def fake_json_get(url):
        if url.rsplit("/", 1)[-1] == "Assets.json":
            raise ConnectionError("boom")
        return _payload([_concept("2023-12-31", 100_000_000_000, start="2023-01-01")])

    monkeypatch.setattr(sec_edgar, "_json_get", fake_json_get)
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: "1234")
    out = sec_edgar.get_financial_history("X", years=3)
    assert "100.0B" in out  # other tags still render
    assert any("Assets fetch failed" in r.message for r in caplog.records)
