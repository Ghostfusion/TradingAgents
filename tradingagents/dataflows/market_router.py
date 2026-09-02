"""Market-classified vendor routing (DSA research §3.4, pillar 6).

Pure helpers for the vendor layer:

- ``market_for_symbol`` — classify a symbol's market FIRST (US default,
  exchange-suffix awareness: .TO/.V Canadian, .L/.PA/.DE/.MI Europe, .T
  Tokyo, .KS Korea, .TW Taiwan, ^... indices). Anything unrecognized
  resolves to "US" (fail-open, the fork's current behavior).
- ``resolve_market_priority`` — per-market vendor priority from config
  ``market_source_priority`` (dict market -> comma list), falling back to
  the current global chain when unconfigured (BIT-IDENTICAL default).
- ``gap_fill`` — merge a primary result with secondary results for missing
  ``_SUPPLEMENT_FIELDS`` (DSA first-success + gap-supplement).

The breaker lives in ``vendor_breaker.py`` (separate, thread-safe). These
are pure helpers consumed by ``dataflows/interface.route_to_vendor`` when
``enable_market_routing`` is on; the default path is untouched.
"""

from __future__ import annotations

_SUFFIX_MARKET = {
    ".TO": "CA", ".V": "CA", ".CN": "CA",
    ".L": "EU", ".PA": "EU", ".DE": "EU", ".MI": "EU", ".AS": "EU", ".MC": "EU",
    ".T": "JP", ".KS": "KR", ".TW": "TW", ".SS": "CN", ".SZ": "CN",
}

# Fields the vendor chain can gap-fill from a secondary source (DSA
# _SUPPLEMENT_FIELDS analog). The fork's quote consumers mainly need these
# enrichments; price/OHLCV are always considered primary.
_SUPPLEMENT_FIELDS = ("volume_ratio", "turnover_rate", "pe_ratio", "pb_ratio",
                      "total_mv", "circ_mv", "high_52w", "low_52w")


def market_for_symbol(symbol: str) -> str:
    """Classify a symbol's market; fail-open to "US" (the current default)."""
    sym = str(symbol or "").strip().upper()
    if not sym:
        return "US"
    if sym.startswith("^") or sym.startswith("$"):
        return "US"  # indices / FX proxies: US default
    # Check longest suffixes FIRST so a shorter suffix never shadows a longer
    # one (".T" must not match ".TW", ".TO", ".T" itself).
    for suffix, market in sorted(_SUFFIX_MARKET.items(), key=lambda kv: -len(kv[0])):
        if suffix in sym:
            return market
    # Bare numeric (A-share-style 6-digit) — the fork is US-first; keep US
    # so nothing silently re-routes away from the configured chain.
    return "US"


def resolve_market_priority(market: str, config: dict | None,
                            default_chain: list[str]) -> list[str]:
    """Per-market vendor priority; unconfigured -> the default (bit-identical).

    ``config`` is the resolved `market_source_priority` dict (market ->
    comma-separated vendor list, e.g. ``{"US": "eodhd,tiingo,yfinance,moomoo"}``).
    Unconfigured vendors in the list are skipped; the default chain is used
    as the tail when an explicit list names vendors the config also needs
    (never silently drops a vendor the user configured elsewhere).
    """
    if not config:
        return list(default_chain)
    # exact market key first, then any case-insensitive match
    raw = config.get(market)
    if raw is None:
        for k, v in config.items():
            if str(k).upper() == str(market).upper():
                raw = v
                break
    if not raw:
        return list(default_chain)
    if isinstance(raw, str):
        names = [v.strip() for v in raw.split(",") if v.strip()]
    else:
        names = [str(v).strip() for v in (raw or []) if str(v).strip()]
    if not names:
        return list(default_chain)
    return names


# Verified price-caliber table (vendor, market) -> caliber. Grounded in the
# loader source, not assumed: alpha_vantage uses TIME_SERIES_DAILY_ADJUSTED
# (split+dividend adjusted); tiingo's OHLCV builds close from the split-
# adjusted ``close`` column (adjClose unused -> split_adjusted); y_finance
# history() defaults auto_adjust=True (adjusted). Anything not listed is
# "unknown" - never guessed. "*" = any market.
_VENDOR_PRICE_CALIBER: dict[tuple[str, str], str] = {
    ("alpha_vantage", "*"): "adjusted",
    ("tiingo", "*"): "split_adjusted",
    ("y_finance", "*"): "adjusted",
}

# Volume-unit convention per market (the unit the venue reports, not what the
# chart shows): A-share venues report board lots; everything else shares.
_MARKET_VOLUME_UNIT = {
    "US": "shares", "CA": "shares", "EU": "shares", "GB": "shares",
    "JP": "shares", "KR": "shares", "TW": "shares", "HK": "shares",
    "SG": "shares", "CN": "board_lots",
}


def price_caliber_for(vendor: str | None, market: str = "US") -> str:
    """The price adjustment caliber a vendor serves for a market (verified
    table; unknown when unlisted)."""
    v = str(vendor or "").lower()
    m = str(market or "").upper()
    if not v:
        return "unknown"
    return _VENDOR_PRICE_CALIBER.get(
        (v, m), _VENDOR_PRICE_CALIBER.get((v, "*"), "unknown")
    )


def volume_unit_for(market: str | None) -> str:
    """The volume-unit convention of a market (unknown when unlisted)."""
    return _MARKET_VOLUME_UNIT.get(str(market or "").upper(), "unknown")


def caliber_consistency(vendor_results: list[dict]) -> dict:
    """Cross-vendor calibration check over per-symbol result dicts (each with
    ``_vendor`` + optional ``_market``): do the sources that actually served
    agree on price caliber? mixed -> warning (a fallback mid-history silently
    rescaled volume or re-dated dividends exactly like Vibe-Trading's board-
    lot / dividend-gap bugs). Empty or all-unknown -> consistent (no claim).
    """
    calibers: dict[str, str] = {}
    for r in vendor_results or []:
        v = str(r.get("_vendor") or "").strip()
        if not v:
            continue
        m = str(r.get("_market") or "US")
        calibers[v] = price_caliber_for(v, m)
    known = {k: c for k, c in calibers.items() if c != "unknown"}
    distinct = set(known.values())
    consistent = len(distinct) <= 1
    warning = ""
    if not consistent:
        warning = ("mixed price caliber across vendors: "
                   + "; ".join(f"{k}={c}" for k, c in sorted(calibers.items())))
    return {"consistent": consistent, "calibers": calibers, "warning": warning}


def gap_fill(primary: dict | None, secondary: list[dict],
             supplement_fields: tuple[str, ...] = _SUPPLEMENT_FIELDS) -> dict:
    """Merge missing supplement fields from secondary results (no override).

    ``primary`` may be None (fully failed), in which case the first secondary
    with ANY data wins whole. Returns a dict with the primary's values and
    the first non-None/missing supplement value found across secondaries.
    ``filled_from`` lists which secondary supplied each filled field.
    """
    out = dict(primary or {})
    if not primary:
        for alt in secondary:
            if alt:
                return dict(alt)
        return {}
    filled: dict[str, str] = {}
    for f in supplement_fields:
        if out.get(f) not in (None, "", 0.0):
            continue
        for alt in secondary:
            v = alt.get(f)
            if v not in (None, "", 0.0):
                out[f] = v
                filled[f] = str(alt.get("_vendor", "secondary"))
                break
    if filled:
        out["_filled_from"] = filled
    return out


__all__ = [
    "market_for_symbol",
    "resolve_market_priority",
    "price_caliber_for",
    "volume_unit_for",
    "caliber_consistency",
    "gap_fill",
    "_SUPPLEMENT_FIELDS",
    "_VENDOR_PRICE_CALIBER",
    "_MARKET_VOLUME_UNIT",
]
