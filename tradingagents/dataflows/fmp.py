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

from tradingagents.dataflows.fmp_common import f_key, fmp_get

# Normalized-earnings helpers used by ``normalized_score``. Imported at module
# level so a NameError inside the try/except cannot silently degrade to None.
from tradingagents.strategies.normalized import (  # noqa: E402
    median_norm_ebit,
    percentile_hist,
)

from .statement_parsing import _latest  # noqa: F401 - used by normalized_score


def get_income_history(symbol: str, limit: int = 10, period: str = "annual") -> list | None:
    data = fmp_get("income-statement", {"symbol": symbol, "limit": limit, "period": period})
    return data if isinstance(data, list) else None


def get_balance_history(symbol: str, limit: int = 10, period: str = "annual") -> list | None:
    data = fmp_get("balance-sheet-statement", {"symbol": symbol, "limit": limit, "period": period})
    return data if isinstance(data, list) else None


def get_cashflow_history(symbol: str, limit: int = 10, period: str = "annual") -> list | None:
    data = fmp_get("cash-flow-statement", {"symbol": symbol, "limit": limit, "period": period})
    return data if isinstance(data, list) else None


def get_ev_history(symbol: str, limit: int = 8, period: str = "annual") -> list | None:
    data = fmp_get("enterprise-values", {"symbol": symbol, "limit": limit, "period": period})
    return data if isinstance(data, list) else None


def get_key_metrics_ttm(symbol: str) -> dict | None:
    data = fmp_get("key-metrics-ttm", {"symbol": symbol})
    if isinstance(data, list) and data:
        return data[0]
    return data if isinstance(data, dict) else None


def get_earnings_surprises(symbol: str, limit: int = 8) -> list | None:
    data = fmp_get("earnings-surprises", {"symbol": symbol})
    return data[:limit] if isinstance(data, list) else None


def get_historical_prices(symbol: str) -> list | None:
    data = fmp_get("historical-price-full", {"symbol": symbol})
    if isinstance(data, dict):
        return data.get("historical")
    return None


def get_company_profile(symbol: str) -> dict | None:
    """Company profile: market cap, public float, shares outstanding.

    Feeds the momentum low-float pillar (Strategies/momentum_day_trading.md).
    None when the key is missing or the call fails (optional enrichment).
    """
    data = fmp_get("profile", {"symbol": symbol})
    if isinstance(data, list) and data:
        return data[0]
    return None


def normalized_score(symbol: str, years: int = 5, current_date: str | None = None) -> dict | None:
    """5y median-margin normalized EBIT + EV/NEBIT + 5y PE percentile.

    Uses ``strategies.normalized``. Series are sourced from the project's own
    vendor chain (income statement via ``route_to_vendor`` + canonical
    fundamentals for EV / market cap / shares) rather than FMP, so the two
    enrichment columns no longer depend on the FMP free-tier rate limits. The
    historical P/E percentile is reconstructed best-effort from historical
    closes x current shares against each period's net income (approximate:
    share count is held at the current value). Returns None when the series
    are unusable. Optional FMP remains a fallback only when the vendor chain
    has no income history (key set and not rate-limited).
    """
    try:
        from tradingagents.dataflows.interface import route_to_vendor
        from tradingagents.dataflows.quantitative_scores import enterprise_value
        from tradingagents.dataflows.statement_parsing import (
            fetch_ticker,
            income_series,
        )

        payload = (
            route_to_vendor("get_income_statement", symbol, "annual", current_date) or ""
        )
        series = income_series(payload)
        # Fall back to FMP only if the vendor chain has no usable income history.
        if (not series or len(series) < 2) and f_key():
            fmp_series = get_income_history(symbol, limit=max(years + 1, 6), period="annual")
            series = [
                {
                    "year": _year_of(r),
                    "revenue": float(r["revenue"]),
                    "ebit": float(r.get("ebit") or r.get("operatingIncome"))
                    if (r.get("ebit") or r.get("operatingIncome")) is not None else None,
                    "net_income": r.get("netIncome"),
                }
                for r in (fmp_series or [])
                if r.get("revenue") is not None
            ]
        if not series or len(series) < 2:
            return None
        revs = [r["revenue"] for r in series if r.get("revenue") is not None]
        ebits = [r["ebit"] for r in series if r.get("ebit") is not None]
        if len(revs) < 2 or len(ebits) < 2:
            return None
        # median_norm_ebit takes the trailing ``years`` window; when fewer than
        # the requested window are available it uses what exists (>= 2).
        eff_years = min(years, len(revs))
        nebit = median_norm_ebit(revs, ebits=ebits, years=eff_years)
        fin = fetch_ticker(symbol, current_date) or {}
        ev = enterprise_value(fin)
        mcap = _latest(fin.get("market_cap"))
        if nebit is None or ev is None or float(ev) <= 0 or nebit <= 0:
            return None
        # 5y PE percentile: current EV / current NI vs a reconstructed
        # historical (historical mcap / NI) series from closes x shares.
        pe_pct = _hist_pe_percentile(fin, series, route_to_vendor, symbol)
        return {
            "normalized_ebit": round(nebit, 2),
            "ev": float(ev),
            "ev_nebit": round(float(ev) / float(nebit), 2),
            "pe_pct5": pe_pct,
            "market_cap": float(mcap) if mcap else None,
        }
    except Exception:
        return None


def _year_of(r: dict) -> int:
    """Fiscal year from an FMP row (``date`` or ``calendarYear``)."""
    for key in ("calendarYear", "date"):
        v = r.get(key)
        if v and str(v)[:4].isdigit():
            return int(str(v)[:4])
    return 0


def _hist_pe_percentile(fin: dict, series: list, route_to_vendor, symbol: str) -> float | None:
    """Best-effort 5y P/E percentile from historical closes x current shares.

    Reconstructs per-year market cap = close x current shares (holding share
    count at today's value - an approximation), divides by that year's net
    income for the historical P/E series, and ranks the current EV/NI against
    it. Returns None when any input is missing (never fabricates).
    """
    try:
        from tradingagents.dataflows.statement_parsing import _latest

        sells = _latest(fin.get("shares"))
        if not sells:
            mcap = _latest(fin.get("market_cap"))
            last = None
            closes = _closes_by_year(route_to_vendor, symbol)
            cur_year = max((r.get("year") or 0 for r in series), default=0)
            if closes and cur_year in closes:
                last = closes[cur_year]  # newest close
            if last and mcap:
                sells = float(mcap) / float(last)
        if not sells or float(sells) <= 0:
            return None
        closes = _closes_by_year(route_to_vendor, symbol)
        pe_series = []
        for r in series:
            ni = r.get("net_income")
            yr = r.get("year") or 0
            if ni and closes and yr in closes and float(ni) > 0:
                mcap_hist = float(closes[yr]) * float(sells)
                pe_series.append(mcap_hist / float(ni))
        if not pe_series:
            return None
        current_income = series[-1].get("net_income")
        cur_ev = _latest(fin.get("market_cap"))
        from tradingagents.dataflows.quantitative_scores import enterprise_value

        cur_ev = enterprise_value(fin)
        if not current_income or not cur_ev or float(current_income) <= 0 or float(cur_ev) <= 0:
            return None
        return percentile_hist(float(cur_ev) / float(current_income), pe_series)
    except Exception:
        return None


def _closes_by_year(route_to_vendor, symbol: str, days: int = 2000) -> dict:
    """Last close of each calendar year from the vendor price history."""
    from datetime import date, timedelta

    end = date.today().isoformat()
    start = (date.today() - timedelta(days=days)).isoformat()
    try:
        out = route_to_vendor("get_stock_data", symbol, start, end) or ""
    except Exception:
        return {}
    closes: dict = {}
    for line in (out or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.lower().startswith("date,"):
            continue
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            yr = int(str(parts[0])[:4])
            c = float(parts[4])
            closes[yr] = c  # last occurrence = latest close of that year
        except (TypeError, ValueError):
            continue
    return closes


__all__ = [
    "get_income_history",
    "get_balance_history",
    "get_cashflow_history",
    "get_ev_history",
    "get_key_metrics_ttm",
    "get_earnings_surprises",
    "get_historical_prices",
    "normalized_score",
]
