"""ETF decline-driver hierarchy (advisory).

The IGV 2026-09-09 fundamentals report (reviewed 2026-09-09) ran
``get_decline_driver_check`` on an ETF and got ``clean=True`` — but that
screen is company-oriented (fraud/distress, negative FCF/ROE, EPS decline)
and meaningless for a fund. An ETF's decline has a different hierarchy:

  Level 1 — MARKET_DRIVEN:   SPY/QQQ drawdown, VIX spike, rates move
  Level 2 — SECTOR_DRIVEN:   XLK/QQQ relative weakness, sector breadth
  Level 3 — ETF_SPECIFIC:    IGV relative weakness vs XLK, volume/flow
                             divergence, NAV premium/discount, tracking
  Level 4 — CONSTITUENT_DRIVEN: top-constituent earnings revisions /
                             valuation compression
  UNKNOWN:                   no signal (replaces the misleading clean=True)

First hit wins; every input is None-safe; a missing series degrades to the
next level. Advisory by contract; never blocks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def _ret(series: Sequence[float], window: int) -> float | None:
    """Total return over the trailing ``window`` bars (None when short)."""
    if not series or len(series) <= window:
        return None
    base = series[-window - 1]
    if base is None or base <= 0:
        return None
    return series[-1] / base - 1.0


def _drawdown(series: Sequence[float]) -> float | None:
    """Peak-to-current drawdown (negative; None when short)."""
    if not series or len(series) < 2:
        return None
    peak = max(series)
    if peak <= 0:
        return None
    return series[-1] / peak - 1.0


def etf_decline_driver(
    ticker: str,
    *,
    etf_closes: Sequence[float] | None = None,
    spy_closes: Sequence[float] | None = None,
    qqq_closes: Sequence[float] | None = None,
    xlk_closes: Sequence[float] | None = None,
    vix_series: Sequence[float] | None = None,
    constituents_map: Mapping[str, Sequence[float]] | None = None,
    market_dd_threshold: float = -0.10,
    sector_dd_threshold: float = -0.08,
    etf_dd_threshold: float = -0.06,
    vix_spike_threshold: float = 30.0,
) -> dict:
    """Classify what is driving an ETF's decline.

    Args:
        ticker: the ETF symbol (informational).
        etf_closes / spy_closes / qqq_closes / xlk_closes: daily close
            series (None-safe).
        vix_series: VIX close series (None-safe).
        constituents_map: {constituent: closes} for the breadth leg.
        market_dd_threshold / sector_dd_threshold / etf_dd_threshold:
            drawdown levels that trigger each level (negative fractions).
        vix_spike_threshold: VIX level that counts as a market-stress spike.

    Returns:
        ``{"driver": "MARKET_DRIVEN"|"SECTOR_DRIVEN"|"ETF_SPECIFIC"|
        "CONSTITUENT_DRIVEN"|"UNKNOWN", "evidence": [..]}``.
    """
    evidence: list[str] = []
    t = (ticker or "").strip().upper()
    spy_dd = _drawdown(spy_closes or [])
    qqq_dd = _drawdown(qqq_closes or [])
    vix_now = vix_series[-1] if vix_series else None
    if (spy_dd is not None and spy_dd <= market_dd_threshold) or (
        qqq_dd is not None and qqq_dd <= market_dd_threshold
    ):
        spy_s = f"{spy_dd:.1%}" if spy_dd is not None else "n/a"
        qqq_s = f"{qqq_dd:.1%}" if qqq_dd is not None else "n/a"
        evidence.append(f"market drawdown (SPY {spy_s}, QQQ {qqq_s})")
        return {"driver": "MARKET_DRIVEN", "evidence": evidence}
    if vix_now is not None and vix_now >= vix_spike_threshold:
        evidence.append(f"VIX spike {vix_now:.1f}")
        return {"driver": "MARKET_DRIVEN", "evidence": evidence}

    # Level 2 — sector.
    xlk_dd = _drawdown(xlk_closes or [])
    if xlk_dd is not None and xlk_dd <= sector_dd_threshold:
        evidence.append(f"sector drawdown (XLK {xlk_dd:.1%})")
        return {"driver": "SECTOR_DRIVEN", "evidence": evidence}

    # Level 3 — ETF-specific (relative weakness vs its sector benchmark).
    etf_dd = _drawdown(etf_closes or [])
    if etf_dd is not None and etf_dd <= etf_dd_threshold:
        if xlk_closes:
            etf_3m = _ret(etf_closes or [], 63)
            xlk_3m = _ret(xlk_closes, 63)
            if etf_3m is not None and xlk_3m is not None and etf_3m < xlk_3m - 0.02:
                evidence.append(
                    f"ETF-specific relative weakness ({t} 3m {etf_3m:.1%} vs XLK {xlk_3m:.1%})"
                )
                return {"driver": "ETF_SPECIFIC", "evidence": evidence}
        evidence.append(f"{t} drawdown {etf_dd:.1%} without market/sector trigger")
        return {"driver": "ETF_SPECIFIC", "evidence": evidence}

    # Level 4 — constituent-driven (breadth collapse).
    if constituents_map:
        above = 0
        n = 0
        for closes in constituents_map.values():
            sma = _sma_last(closes, 50)
            if sma is None or not closes:
                continue
            n += 1
            if closes[-1] > sma:
                above += 1
        if n >= 3 and above / n <= 0.3:
            evidence.append(f"constituent breadth collapse ({above}/{n} above 50-SMA)")
            return {"driver": "CONSTITUENT_DRIVEN", "evidence": evidence}

    return {"driver": "UNKNOWN", "evidence": evidence}


def _sma_last(series: Sequence[float], window: int) -> float | None:
    if not series or len(series) < window:
        return None
    tail = series[-window:]
    if any(x is None for x in tail):
        return None
    return sum(tail) / window


__all__ = ["etf_decline_driver"]
