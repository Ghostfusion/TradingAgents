"""Tests for security-type classification (ETF vs operating company).

The IGV 2026-09-09 review loop: an index ETF was routed through company-level
statement tools that all returned "unavailable", and the analyst used that
absence as a valuation conclusion. classify_security is the routing gate that
lets the fundamentals analyst pick an ETF methodology instead.
"""

from __future__ import annotations

from tradingagents.strategies.security_type import classify_security, is_etf


def test_quote_type_etf_high_confidence():
    c = classify_security("IGV", identity={"quote_type": "ETF", "company_name": "iShares Expanded Tech-Software Sector ETF"})
    assert c["security_type"] == "ETF"
    assert c["confidence"] == "high"
    assert is_etf(c)


def test_known_universe_member():
    # IGV is in INDUSTRY_ETFS; SOXX/CIBR/SKYY too; XLK in SPDR_SECTORS.
    for t in ("IGV", "SOXX", "CIBR", "SKYY", "XLK"):
        c = classify_security(t)
        assert c["security_type"] == "ETF", t
        assert c["confidence"] == "high"
    # QQQ is a real ETF but not in the repo's curated universe lists; without
    # provider identity it must fall back to UNKNOWN (no false positive).
    assert classify_security("QQQ")["security_type"] == "UNKNOWN"


def test_fund_issuer_name_medium_confidence():
    c = classify_security("SOMETHING", identity={"company_name": "Vanguard Index Funds - Vanguard S&P 500 ETF"})
    assert c["security_type"] == "ETF"
    assert c["confidence"] == "medium"


def test_operating_company_unknown():
    c = classify_security("MSFT", identity={"quote_type": "EQUITY", "company_name": "Microsoft Corporation"})
    assert c["security_type"] == "UNKNOWN"
    assert not is_etf(c)


def test_unknown_fallback_no_behavior_change():
    c = classify_security("ZZZZ", identity={})
    assert c["security_type"] == "UNKNOWN"
    assert c["confidence"] == "low"


def test_provider_meta_is_etf_flag():
    c = classify_security("IGV", provider_meta={"is_etf": True})
    assert c["security_type"] == "ETF"
    assert c["confidence"] == "high"


def test_case_insensitive():
    assert classify_security("igv")["security_type"] == "ETF"
    assert classify_security("  soxx  ")["security_type"] == "ETF"
