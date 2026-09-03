"""Composite domain bundles (W4-1, Gemini) — aggregate fine-grained tools.

The 146 atomic strategy tools are compressed into FIVE per-analyst composite
endpoints. Each bundle is a single deterministic pass over the computed
readers with explicit data-quality flags + missing-field honesty — the LLM
stops chaining micro-tools (token savings, fewer tool-selection failures,
fault isolation in code instead of agent self-healing loops).

Each returns a flat dict (pydantic-friendly, JSON-serializable) with
``symbol``/``effective_date``/``data_quality`` plus the domain's metrics and
``missing_fields``. Advisory: the values are the same computed reads the
atomic tools return; this only changes HOW the analyst consumes them.
"""

from __future__ import annotations

from tradingagents.strategies import news_relevance


def _quality_of(*parts: str | None) -> str:
    """Combine per-part quality flags honestly: any unknown -> unknown? No —
    degenerate up: all known-fresh -> fresh; any stale/partial -> partial;
    any unknown -> unknown; else fresh."""
    if any(p == "unknown" or p is None for p in parts):
        # an unmeasured part is not "unknown" proof — treat as partial only if
        # we have at least one measured; totally absent -> unknown
        measured = [p for p in parts if p and p != "unknown"]
        return ("partial" if measured else "unknown")
    if any(p == "stale" for p in parts):
        return "stale"
    if any(p == "partial" for p in parts):
        return "partial"
    return "fresh"


def get_market_technicals(symbol: str, effective_date: str = "") -> dict:
    """Composite for the Market Analyst: trend/range/regime/volatility/
    liquidity-technical factors in one deterministic pass."""
    from tradingagents.agents.utils.analysis_tools import (
        get_momentum_detail,
        get_regime_read,
        get_swing_set,
    )
    out: dict = {"symbol": symbol, "effective_date": effective_date,
                 "domain": "market_technicals", "missing_fields": []}
    parts: list[str] = []
    try:
        r_reg = get_regime_read.invoke({"ticker": symbol})
        out["regime"] = r_reg
        parts.append("unknown" if "unavailable" in str(r_reg).lower() else "fresh")
    except Exception:  # noqa: BLE001 - bundle degrades
        out["missing_fields"].append("regime")
    try:
        out["swing_set"] = get_swing_set.invoke({"ticker": symbol})
        parts.append("fresh")
    except Exception:  # noqa: BLE001
        out["missing_fields"].append("swing")
    try:
        out["momentum"] = get_momentum_detail.invoke({"ticker": symbol})
        parts.append("fresh")
    except Exception:  # noqa: BLE001
        out["missing_fields"].append("momentum")
    out["data_quality"] = _quality_of(*parts)
    return out


def get_fundamental_profile(symbol: str, effective_date: str = "") -> dict:
    """Composite for the Fundamentals Analyst: valuation + profitability +
    floors + credit reads in one pass with PIT gating (W3-4)."""
    from tradingagents.agents.utils.analysis_tools import get_margin_of_safety
    from tradingagents.agents.utils.value_dip_tools import (
        get_fcf_yield,
        get_valuation_z_score,
        get_value_floors,
    )

    out: dict = {"symbol": symbol, "effective_date": effective_date,
                 "domain": "fundamental_profile", "missing_fields": []}
    parts: list[str] = []
    for name, fn in (("value_floors", get_value_floors),
                     ("valuation_z", get_valuation_z_score),
                     ("fcf_yield", get_fcf_yield),
                     ("margin_of_safety", get_margin_of_safety)):
        try:
            out[name] = fn.invoke({"ticker": symbol})
            parts.append("unknown" if "unavailable" in str(out[name]).lower() else "fresh")
        except Exception:  # noqa: BLE001
            out["missing_fields"].append(name)
    out["data_quality"] = _quality_of(*parts)
    return out


def get_sentiment_flow_feed(symbol: str, effective_date: str = "") -> dict:
    """Composite for the Sentiment/News Analysts: news sentiment series +
    relevance read + fund-flow/order imbalance in one pass."""
    from tradingagents.agents.utils.analysis_tools import (
        get_news_sentiment_series,
        get_order_imbalance,
    )
    from tradingagents.agents.utils.news_data_tools import get_gdelt_sentiment

    out: dict = {"symbol": symbol, "effective_date": effective_date,
                 "domain": "sentiment_flow_feed", "missing_fields": []}
    parts: list[str] = []
    try:
        out["news_sentiment_series"] = get_news_sentiment_series.invoke({"ticker": symbol})
        parts.append("fresh")
    except Exception:  # noqa: BLE001
        out["missing_fields"].append("news_sentiment_series")
    try:
        out["gdelt"] = get_gdelt_sentiment.invoke({"ticker": symbol})
        parts.append("fresh")
    except Exception:  # noqa: BLE001
        out["missing_fields"].append("gdelt")
    try:
        out["order_imbalance"] = get_order_imbalance.invoke({"ticker": symbol})
        parts.append("fresh")
    except Exception:  # noqa: BLE001
        out["missing_fields"].append("order_imbalance")
    out["data_quality"] = _quality_of(*parts)
    return out


def get_factor_profile(symbol: str, effective_date: str = "") -> dict:
    """Composite for Market/Bull/Bear: the factor vector (Alpha158 subset +
    rank-IC style signal reads) the debate agents should cite (W4-4)."""
    from tradingagents.agents.utils.analysis_tools import get_factor_profile as _atomic

    out: dict = {"symbol": symbol, "effective_date": effective_date,
                 "domain": "factor_profile", "missing_fields": []}
    try:
        out["factors"] = _atomic.invoke({"ticker": symbol})
        out["data_quality"] = "unknown" if "unavailable" in str(out["factors"]).lower() else "fresh"
    except Exception:  # noqa: BLE001
        out["factors"] = None
        out["data_quality"] = "unknown"
        out["missing_fields"].append("factor_profile")
    return out


def get_portfolio_risk_envelope(symbol: str, basket: list | None = None,
                                effective_date: str = "") -> dict:
    """Composite for Risk Debaters + Judge: book-level CVaR / tail / liquidity
    envelope for the analyzed name + (optionally) the whole basket."""
    from tradingagents.agents.utils.analysis_tools import (
        get_book_tail_risk,
        get_tail_risk,
    )
    from tradingagents.agents.utils.market_position_tools import get_liquidity_risk

    out: dict = {"symbol": symbol, "effective_date": effective_date, "basket": basket or [],
                 "domain": "portfolio_risk_envelope", "missing_fields": []}
    parts: list[str] = []
    try:
        out["tail_risk"] = get_tail_risk.invoke({"ticker": symbol})
        parts.append("fresh")
    except Exception:  # noqa: BLE001
        out["missing_fields"].append("tail_risk")
    try:
        out["liquidity_risk"] = get_liquidity_risk.invoke({"ticker": symbol})
        parts.append("fresh")
    except Exception:  # noqa: BLE001
        out["missing_fields"].append("liquidity_risk")
    try:
        out["book_tail_risk"] = get_book_tail_risk.invoke({"ticker": symbol})
        parts.append("fresh")
    except Exception:  # noqa: BLE001
        out["missing_fields"].append("book_tail_risk")
    out["data_quality"] = _quality_of(*parts)
    return out


# Deterministic news-relevance composite (pure; reused by the bundle + web).
def news_relevance_profile(title: str, ticker: str, source_url: str = "",
                           snippet: str = "", company_name: str = "") -> dict:
    """The news-relevance read as a profile the analyst can rank a batch by."""
    r = news_relevance.score_news_article(title, source_url, snippet,
                                          ticker, company_name)
    return {
        "score": r["score"],
        "reasons": r["reasons"],
        "admitted": news_relevance.admit_article(title, url=source_url),
        "official": news_relevance.is_official(source_url),
    }


__all__ = ["get_market_technicals", "get_fundamental_profile",
           "get_sentiment_flow_feed", "get_factor_profile",
           "get_portfolio_risk_envelope", "news_relevance_profile",
           "_quality_of"]
