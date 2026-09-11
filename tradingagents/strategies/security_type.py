"""Security-type classification (ETF vs operating company vs unknown).

The IGV 2026-09-09 fundamentals report (reviewed 2026-09-09) routed an index
ETF through company-level statement tools (get_balance_sheet, get_cashflow,
get_dcf_valuation, ...) that all returned honest "unavailable", and the
analyst then used that absence as a valuation conclusion ("no DCF -> no BUY").
This module is the routing gate: it classifies a ticker's security type so the
fundamentals analyst can select an ETF-appropriate methodology instead of the
company one.

Sources, in order of authority:
1. Provider identity ``quote_type`` (yfinance returns "ETF" for funds) —
   resolved once per run by ``resolve_instrument_identity`` and carried on the
   state.
2. Known ETF universe lists (``sector_rank.INDUSTRY_ETFS``,
   ``sector_rank.SPDR_SECTORS``, ``sector_screener.EW_CW_ETFS``).
3. Wrapper name patterns in the resolved company name that carry
   fund-specific evidence: a literal ``ETF``/``Fund`` token, or a pure
   fund-sponsor brand next to a ``Trust``/``Index`` structure. A bare issuer
   name (JPMorgan, BlackRock, State Street, Invesco, ...) is NOT evidence -
   those are listed operating companies and must never be classified ETF.
4. Fallback: UNKNOWN -> current company path (no behavior change).

Advisory by contract: never blocks, never raises; a classification failure
degrades to UNKNOWN and the pipeline runs exactly as it does today.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# A name may only prove a wrapper when it names one. "ETF"/"Fund" alone are
# unambiguous wrapper words; "Trust"/"Index" are not (Northern Trust
# Corporation is a bank holding company), so they count only next to a pure
# fund-sponsor brand.
_FUND_WRAPPER_RE = re.compile(r"\bETF\b|\bFund\b", re.I)
_FUND_STRUCTURE_RE = re.compile(r"\bTrust\b|\bIndex\b", re.I)
# ETF sponsors that are *not* also listed operating companies (EDGAR CIK
# 0001100663 = iShares Trust for IGV). Firms like JPMorgan/BlackRock/Invesco
# are deliberately absent: their names would otherwise re-classify the
# operating company itself as a fund.
_FUND_BRAND_RE = re.compile(
    r"iShares|SPDR|Vanguard|ProShares|Global X|VanEck|Direxion|Amplify|"
    r"Roundhill|Simplify|GraniteShares|YieldMax|Defiance|Pacer|Innovator|"
    r"KraneShares|ALPS|Sprott|Aberdeen|Valkyrie|Bitwise|WisdomTree|"
    r"First Trust|Tidal|FT Vest",
    re.I,
)


def _known_etf_universe() -> set[str]:
    """All tickers the repo already treats as ETFs (imports are lazy so the
    classifier never drags the sector modules into a bare import)."""
    out: set[str] = set()
    try:
        from tradingagents.strategies.sector_rank import INDUSTRY_ETFS, SPDR_SECTORS

        out |= set(INDUSTRY_ETFS) | set(SPDR_SECTORS)
    except Exception:  # noqa: BLE001 - degrade, never block
        pass
    try:
        from tradingagents.strategies.sector_screener import EW_CW_ETFS

        out |= set(EW_CW_ETFS) | set(EW_CW_ETFS.values())
    except Exception:  # noqa: BLE001 - degrade, never block
        pass
    return out


def classify_security(
    ticker: str,
    *,
    identity: Mapping[str, Any] | None = None,
    provider_meta: Mapping[str, Any] | None = None,
) -> dict:
    """Classify a ticker's security type.

    Args:
        ticker: the symbol (upper-cased internally).
        identity: the resolved instrument identity dict (from
            ``resolve_instrument_identity``) carrying ``quote_type`` and
            ``company_name`` when available.
        provider_meta: optional vendor metadata dict with an ``is_etf`` /
            ``quote_type`` / ``type`` key (future vendor plumbing).

    Returns:
        ``{"security_type": "ETF"|"operating_company"|"UNKNOWN",
        "confidence": "high"|"medium"|"low", "evidence": [..]}``.
    """
    t = (ticker or "").strip().upper()
    evidence: list[str] = []

    # 1. Provider identity quote_type (yfinance returns "ETF" for funds).
    qt = None
    if identity:
        qt = str(identity.get("quote_type") or "").strip()
    if provider_meta:
        qt = qt or str(provider_meta.get("quote_type") or "").strip()
        if provider_meta.get("is_etf") is True:
            qt = qt or "ETF"
    if qt and qt.lower() in ("etf", "fund", "mutualfund", "index"):
        evidence.append(f"provider quote_type={qt}")
        return {"security_type": "ETF", "confidence": "high", "evidence": evidence}

    # 2. Known ETF universe lists.
    if t in _known_etf_universe():
        evidence.append("member of the repo's ETF universe lists")
        return {"security_type": "ETF", "confidence": "high", "evidence": evidence}

    # 3. Wrapper name patterns. Evidence must be fund-specific: either a
    #    literal ETF/Fund token, or an unambiguous fund brand next to a
    #    Trust/Index structure. A bare issuer name (JPMorgan, BlackRock,
    #    State Street, ...) is never fund evidence - those are listed
    #    operating companies.
    name = ""
    if identity:
        name = str(identity.get("company_name") or identity.get("name") or "")
    if name and _FUND_WRAPPER_RE.search(name):
        evidence.append(f"fund wrapper name: {name[:60]}")
        return {"security_type": "ETF", "confidence": "medium", "evidence": evidence}
    if name and _FUND_STRUCTURE_RE.search(name) and _FUND_BRAND_RE.search(name):
        evidence.append(f"fund trust name: {name[:60]}")
        return {"security_type": "ETF", "confidence": "medium", "evidence": evidence}

    # 4. Fallback: unknown -> current company path.
    return {"security_type": "UNKNOWN", "confidence": "low", "evidence": evidence}


def is_etf(classification: Mapping[str, Any] | None) -> bool:
    """True when a classification dict resolves to an ETF."""
    return bool(classification) and classification.get("security_type") == "ETF"


__all__ = ["classify_security", "is_etf"]
