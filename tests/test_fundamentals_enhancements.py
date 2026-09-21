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
    """A blank ticker is a caller error, and it must NOT reach the network.

    This used to assert the prose "congress trades unavailable" was returned.
    That contract was the defect: ``route_to_vendor`` treats any returned
    string as a successful result and stops the chain, so a vendor that answers
    prose instead of raising makes every later vendor for the method
    unreachable. It now raises before any fetch.
    """
    with pytest.raises(ValueError):
        congress.get_congress_trades("")


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


def _cfacts(tags: dict, dei: dict | None = None) -> dict:
    """A companyfacts payload from ``{tag: [rows]}`` (+ optional dei units)."""
    facts: dict = {"us-gaap": {t: {"units": {"USD": rows}} for t, rows in tags.items()}}
    if dei is not None:
        facts["dei"] = {"EntityCommonStockSharesOutstanding": {"units": dei}}
    return {"facts": facts}


def _patch_facts(monkeypatch, payload, cik="1234"):
    monkeypatch.setattr(sec_edgar, "_json_get", lambda url, *a, **k: payload)
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: cik)


def test_xbrl_annual_facts_merge_candidate_tags_by_period_end(monkeypatch):
    """A filer that switches concepts mid-history keeps BOTH halves.

    "The first tag with any data wins" returned a series that stopped the year
    the filer changed tag - so a point-in-time read found nothing at the
    reference year while the value sat in the next candidate all along. NVDA is
    the live case: its ``CostOfGoodsAndServicesSold`` stops in 2021 and
    ``CostOfRevenue`` carries on, and GP/A was n/a until the candidates merged.
    """
    _patch_facts(monkeypatch, _cfacts({
        "RevenueFromContractWithCustomerExcludingAssessedTax": [
            _concept("2024-06-30", 200_000_000_000, start="2023-07-01"),
            _concept("2025-06-30", 300_000_000_000, start="2024-07-01"),
        ],
        "Revenues": [_concept("2022-06-30", 100_000_000_000, start="2021-07-01")],
    }))
    facts = sec_edgar.annual_facts("X")
    assert sorted(facts["series"]["Revenue"]) == ["2022-06-30", "2024-06-30", "2025-06-30"]
    assert facts["series"]["Revenue"]["2022-06-30"]["val"] == 100_000_000_000
    assert facts["span"] == ["2022-06-30", "2025-06-30"]


def test_xbrl_annual_facts_read_foreign_private_issuer_annual_reports(monkeypatch):
    """20-F is an FPI's annual report; SIMO files nothing else.

    Before the form list existed, every foreign private issuer contributed zero
    tags - a coverage hole that would have silently thinned the panel's
    cross-section by however many FPIs the universe holds.
    """
    _patch_facts(monkeypatch, _cfacts({"Assets": [
        _concept("2025-12-31", 1_222_719_000),
        {"end": "2024-12-31", "val": 900, "form": "10-Q", "fp": "FY"},  # not an annual report
    ]}))
    facts = sec_edgar.annual_facts("SIMO")
    assert list(facts["series"]["Total assets"]) == ["2025-12-31"]
    assert "2024-12-31" not in facts["series"]["Total assets"]


def test_xbrl_annual_facts_carry_the_cover_page_share_count(monkeypatch):
    """The dei count rides the same single request, and it is read from the
    cover page of ANY form - a 10-Q's count is newer than the last 10-K's."""
    _patch_facts(monkeypatch, _cfacts(
        {"Assets": [_concept("2025-06-30", 1_000_000_000)]},
        dei={"shares": [
            {"end": "2026-04-23", "val": 7.42e9, "form": "10-Q", "fp": "Q2",
             "filed": "2026-04-25"},
            {"end": "2026-07-23", "val": 7.43e9, "form": "10-K", "fp": "FY",
             "filed": "2026-07-29"},
        ]},
    ))
    facts = sec_edgar.annual_facts("MSFT")
    assert facts["shares"]["2026-04-23"]["val"] == 7.42e9, "a quarterly cover page counts"
    assert facts["shares"]["2026-07-23"]["filed"] == "2026-07-29"
    # and the rendered leaf still reads the flattened series contract
    out = sec_edgar.get_financial_history("MSFT", years=3)
    assert "1.0B" in out and "companyfacts" in out


def test_xbrl_annual_facts_flag_a_foreign_private_issuer_cover_page(monkeypatch):
    """The flag exists because an FPI's US-listed line may be an ADS.

    The cover-page count is **ordinary** shares while a US-listed price is per
    **ADS**, and EDGAR does not carry the ratio - so a reader deriving a market
    capitalisation from the two has to be able to see which case it is in.
    SIMO 2026-09-17 is the live one: 1 ADS = 4 ordinary shares, and the
    unguarded product overstated its market cap fourfold.
    """
    _patch_facts(monkeypatch, _cfacts(
        {"Assets": [_concept("2025-12-31", 1_222_719_000)]},
        dei={"shares": [{"end": "2025-12-31", "val": 134_244_840, "form": "20-F",
                         "fp": "FY", "filed": "2026-04-30"}]},
    ))
    fpi = sec_edgar.annual_facts("SIMO")
    assert fpi["foreign_private_issuer"] is True
    assert fpi["shares"]["2025-12-31"]["val"] == 134_244_840

    _patch_facts(monkeypatch, _cfacts(
        {"Assets": [_concept("2025-06-30", 1_000_000_000)]},
        dei={"shares": [{"end": "2026-07-23", "val": 7.43e9, "form": "10-K",
                         "fp": "FY", "filed": "2026-07-29"}]},
    ))
    assert sec_edgar.annual_facts("MSFT")["foreign_private_issuer"] is False


def test_xbrl_annual_facts_do_not_fall_back_for_a_filer_without_us_gaap(monkeypatch):
    """TSM reports under IFRS: its payload arrives and carries no us-gaap.

    That is NOT the companyfacts-failure the per-tag fallback exists for. Falling
    back there spent 23 requests collecting 404s and still found nothing.
    """
    calls: list[str] = []

    def fake(url):
        calls.append(url)
        return {"facts": {"ifrs-full": {"Assets": {"units": {"USD": []}}}}}

    monkeypatch.setattr(sec_edgar, "_json_get", fake)
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: "1046179")
    with pytest.raises(NoMarketDataError) as exc:
        sec_edgar.annual_facts("TSM")
    assert len(calls) == 1, "one companyfacts request, no per-tag storm"
    assert "us-gaap" in str(exc.value)


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


def test_xbrl_history_costs_one_request_for_every_tag(monkeypatch):
    """D-4: the eight rows came from 11 ``companyconcept`` requests; one
    ``companyfacts`` payload carries every us-gaap tag, and the SEC's published
    fair-access ceiling is 10 requests/second per IP. The table must therefore
    render from a SINGLE fetch."""
    calls: list[str] = []

    def fake_json_get(url):
        calls.append(url)
        assert "companyfacts" in url, url
        return {
            "facts": {
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": {
                        "units": {"USD": [_concept("2020-09-26", 274_515_000_000, start="2019-09-28")]}
                    },
                    "Assets": {"units": {"USD": [_concept("2020-09-26", 323_888_000_000)]}},
                }
            }
        }

    monkeypatch.setattr(sec_edgar, "_json_get", fake_json_get)
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: "320193")
    out = sec_edgar.get_financial_history("AAPL", years=3)
    assert len(calls) == 1, calls
    assert "274.5B" in out and "323.9B" in out
    assert "companyfacts" in out


def test_xbrl_history_falls_back_to_per_tag_when_the_facts_payload_fails(monkeypatch):
    """The multi-MB payload can fail where a small one would not; losing one tag
    must never cost the whole table."""
    urls: list[str] = []

    def fake_json_get(url):
        urls.append(url)
        if "companyfacts" in url:
            raise ConnectionError("payload too large")
        tag = url.rsplit("/", 1)[-1]
        if tag == "Assets.json":
            return _payload([_concept("2020-09-26", 323_888_000_000)])
        return _payload([])

    monkeypatch.setattr(sec_edgar, "_json_get", fake_json_get)
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: "320193")
    out = sec_edgar.get_financial_history("AAPL", years=3)
    assert "323.9B" in out
    assert sum("companyfacts" in u for u in urls) == 1
    assert sum("companyconcept" in u for u in urls) > 1
