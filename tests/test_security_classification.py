"""Security-classification regression tests (P0-9).

``classify_security`` gates the fundamentals analyst's toolset (company
statements vs the ETF methodology). The IGV case it exists to catch is an ETF
routed through company tools; the inverse bug was operating companies (JPM,
GS, MS, BLK, SCHW, NTRS, STT) classified "ETF" by a bare issuer name or a bare
"Trust" match, handing them the ETF toolset.

UNKNOWN is the deliberate non-fund fallback: the analyst branches only on
``security_type == "ETF"``, so UNKNOWN keeps the unchanged company path (see
the module docstring, source 4). A name may only prove a wrapper when it
carries fund-specific evidence - a literal ETF/Fund token, or a pure fund
brand next to a Trust/Index structure - never a bare issuer name.
"""

from __future__ import annotations

from tradingagents.strategies.security_type import classify_security, is_etf

# yfinance quoteType for common stock is "EQUITY"; company_name mirrors
# resolve_instrument_identity's longName.
_OPERATING_COMPANIES = {
    "JPM": "JPMorgan Chase & Co.",
    "GS": "The Goldman Sachs Group, Inc.",
    "MS": "Morgan Stanley",
    "BLK": "BlackRock, Inc.",
    "SCHW": "The Charles Schwab Corporation",
    "NTRS": "Northern Trust Corporation",
    "STT": "State Street Corporation",
    "AAPL": "Apple Inc.",
    "XOM": "Exxon Mobil Corporation",
}


def test_listed_operating_companies_are_not_etf():
    for ticker, name in _OPERATING_COMPANIES.items():
        c = classify_security(
            ticker, identity={"quote_type": "EQUITY", "company_name": name}
        )
        assert c["security_type"] == "UNKNOWN", (ticker, c)
        assert not is_etf(c)


def test_operating_company_names_are_not_etf_without_quote_type():
    for ticker, name in _OPERATING_COMPANIES.items():
        c = classify_security(ticker, identity={"company_name": name})
        assert c["security_type"] == "UNKNOWN", (ticker, c)


def test_genuine_funds_classify_as_etf():
    for t in ("IGV", "SOXX", "XLK"):  # curated universe lists, no identity
        assert classify_security(t)["security_type"] == "ETF", t
    for t, name in {
        "SPY": "SPDR S&P 500 ETF Trust",
        "IVV": "iShares Core S&P 500 ETF",
        "QQQ": "Invesco QQQ Trust",
    }.items():
        c = classify_security(t, identity={"quote_type": "ETF", "company_name": name})
        assert c["security_type"] == "ETF", t
        assert c["confidence"] == "high"


def test_fund_wrapper_names_classify_as_etf_without_quote_type():
    for name in (
        "SPDR S&P 500 ETF Trust",
        "iShares Core S&P 500 ETF",
        "Vanguard Total Stock Market Index Fund",
        "Financial Select Sector SPDR Fund",
        "iShares Trust",
    ):
        c = classify_security("ZZZZ", identity={"company_name": name})
        assert c["security_type"] == "ETF", name
        assert c["confidence"] == "medium"


def test_provider_quote_type_is_authoritative():
    # A corporate-looking name cannot override the provider's ETF quote type.
    c = classify_security(
        "XYZ", identity={"quote_type": "ETF", "company_name": "BlackRock, Inc."}
    )
    assert c["security_type"] == "ETF"
    assert c["confidence"] == "high"
    assert any("quote_type=ETF" in e for e in c["evidence"])
    assert (
        classify_security("IGV", provider_meta={"is_etf": True})["security_type"]
        == "ETF"
    )


def test_ambiguous_identity_without_fund_evidence_stays_unknown():
    c = classify_security("ZZZZ", identity={})
    assert c["security_type"] == "UNKNOWN"
    assert c["confidence"] == "low"
