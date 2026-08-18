"""FMP optional data vendor: multi-year fundamentals, EV, surprises, prices.

Ports of Financial Modeling Prep (/stable/ endpoints) that fill the project's
known gaps:

- 5+ year statement history         -> normalized earnings (strategies/normalized)
- enterprise-values + key metrics   -> 5y valuation percentiles
- earnings surprises                -> PEAD / event inputs
- historical price (OHLCV+vwap)     -> screener ATR/volume/scan bases

Every function degrades to None/[] when the API key is missing or the call
fails, so FMP stays an optional enrichment layer.
"""

from __future__ import annotations

from tradingagents.dataflows.fmp_common import fmp_get


def get_income_history(symbol: str, limit: int = 10,
                       period: str = "annual") -> "list | None":
    data = fmp_get("income-statement",
                   {"symbol": symbol, "limit": limit, "period": period})
    return data if isinstance(data, list) else None


def get_balance_history(symbol: str, limit: int = 10,
                        period: str = "annual") -> "list | None":
    data = fmp_get("balance-sheet-statement",
                   {"symbol": symbol, "limit": limit, "period": period})
    return data if isinstance(data, list) else None


def get_cashflow_history(symbol: str, limit: int = 10,
                         period: str = "annual") -> "list | None":
    data = fmp_get("cash-flow-statement",
                   {"symbol": symbol, "limit": limit, "period": period})
    return data if isinstance(data, list) else None


def get_ev_history(symbol: str, limit: int = 8,
                   period: str = "annual") -> "list | None":
    data = fmp_get("enterprise-values",
                   {"symbol": symbol, "limit": limit, "period": period})
    return data if isinstance(data, list) else None


def get_key_metrics_ttm(symbol: str) -> "dict | None":
    data = fmp_get("key-metrics-ttm", {"symbol": symbol})
    if isinstance(data, list) and data:
        return data[0]
    return data if isinstance(data, dict) else None


def get_earnings_surprises(symbol: str, limit: int = 8) -> "list | None":
    data = fmp_get("earnings-surprises", {"symbol": symbol})
    return data[:limit] if isinstance(data, list) else None


def get_historical_prices(symbol: str) -> "list | None":
    data = fmp_get("historical-price-full", {"symbol": symbol})
    if isinstance(data, dict):
        return data.get("historical")
    return None


def normalized_score(symbol: str, years: int = 5) -> "dict | None":
    """5y median-margin normalized EBIT + EV/NEBIT + 5y PE percentile.

    Uses strategies.normalized; returns None when the series are unusable.
    """
    try:
        from tradingagents.strategies.normalized import (
            median_norm_ebit, percentile_hist,
        )

        income = get_income_history(symbol, limit=max(years + 1, 6), period="annual")
        evs = get_ev_history(symbol, limit=years + 3, period="annual")
        if not income or not evs:
            return None
        revs, ebits = [], []
        for r in income:
            rev = r.get("revenue")
            eb = r.get("ebit")
            if eb is None:
                eb = r.get("operatingIncome")
            if rev is not None and eb is not None:
                revs.append(float(rev))
                ebits.append(float(eb))
        if len(revs) < years:
            return None
        nebit = median_norm_ebit(revs, ebits=ebits, years=years)
        ev = evs[0].get("enterpriseValue")
        mcap = evs[0].get("marketCapitalization")
        if nebit is None or ev is None or float(ev) <= 0 or nebit <= 0:
            return None
        # 5y PE percentile from (marketCap / netIncome) series + current EV basis
        pe_ratio = []
        for i, ev_row in enumerate(evs[: len(income)]):
            mc = ev_row.get("marketCapitalization")
            inc = income[i].get("netIncome")
            if mc and inc and float(inc) > 0:
                pe_ratio.append(float(mc) / float(inc))
        current_income = income[0].get("netIncome")
        pe_pct = None
        if current_income and float(current_income) > 0:
            pe_pct = percentile_hist(
                float(ev) / float(current_income), pe_ratio
            )
        return {
            "normalized_ebit": round(nebit, 2),
            "ev": float(ev),
            "ev_nebit": round(float(ev) / float(nebit), 2),
            "pe_pct5": pe_pct,
            "market_cap": float(mcap) if mcap else None,
        }
    except Exception:
        return None


__all__ = [
    "get_income_history", "get_balance_history", "get_cashflow_history",
    "get_ev_history", "get_key_metrics_ttm", "get_earnings_surprises",
    "get_historical_prices", "normalized_score",
]