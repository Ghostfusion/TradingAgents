"""ETF valuation engine — weighted constituent multiples (advisory).

The IGV 2026-09-09 fundamentals report (reviewed 2026-09-09) had no
ETF-level valuation: company statement tools returned "unavailable" and the
analyst concluded "no DCF -> no BUY". For an index wrapper the right
valuation is the weighted valuation of its constituents, not a company DCF.

This module computes, from a constituent map (ticker -> per-constituent
metric dict) and optional ETF weights:

  * weighted P/E (harmonic: 1 / sum(w_i / P/E_i)) — the correct aggregation
    for a price/earnings ratio across a basket
  * forward P/E (same on forward EPS)
  * earnings yield (1 / weighted P/E)
  * weighted FCF yield (sum w_i FCF_i / sum w_i mcap_i)
  * weighted revenue / EPS growth
  * valuation percentile vs the ETF's own trailing history (when the ETF's
    own P/E series is provided)
  * valuation vs SPY and vs XLK (ratio of ETF P/E to benchmark P/E)
  * top-N weight / concentration (from the weight vector)

Every metric is None-safe: a missing constituent metric is skipped and the
weights re-normalized over the contributing set (a single contributor yields
its own P/E, not a diluted one); a metric with no usable inputs renders
None — never fabricated. Advisory by contract; never blocks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def _renorm(weights: Mapping[str, float], present: Sequence[str]) -> dict[str, float]:
    """Re-normalize weights over the present constituents (missing -> skip)."""
    w = {t: float(weights.get(t) or 0.0) for t in present if (weights.get(t) or 0.0) > 0}
    total = sum(w.values())
    if total <= 0:
        return {}
    return {t: v / total for t, v in w.items()}


def _harmonic_pe(weights: Mapping[str, float], eps_map: Mapping[str, float | None],
                 price_map: Mapping[str, float | None]) -> float | None:
    """1 / sum(w_i / P/E_i) = 1 / sum(w_i * e_i / p_i), weights re-normalized
    over the names that actually contribute (a name with no EPS/price is
    skipped and the rest re-weighted, so a single contributor yields its own
    P/E, not a diluted one)."""
    contrib = {
        t: w for t, w in weights.items()
        if (eps_map.get(t) or 0) > 0 and (price_map.get(t) or 0) > 0
    }
    total = sum(contrib.values())
    if total <= 0:
        return None
    acc = sum((w / total) * float(eps_map[t]) / float(price_map[t]) for t, w in contrib.items())
    if acc <= 0:
        return None
    return 1.0 / acc


def _weighted_avg(weights: Mapping[str, float], values: Mapping[str, float | None]) -> float | None:
    """Weighted mean over the names with a value, weights re-normalized over
    the contributing set."""
    contrib = {t: w for t, w in weights.items() if values.get(t) is not None}
    total = sum(contrib.values())
    if total <= 0:
        return None
    return sum((w / total) * float(values[t]) for t, w in contrib.items())


def _percentile_rank(series: Sequence[float], value: float) -> float | None:
    """Percentile rank of ``value`` within ``series`` (0..1; None when empty)."""
    vals = [float(x) for x in series if x is not None and x > 0]
    if not vals:
        return None
    below = sum(1 for x in vals if x < value)
    return below / len(vals)


def etf_valuation(
    ticker: str,
    *,
    constituents: Mapping[str, Mapping[str, float | None]],
    weights: Mapping[str, float] | None = None,
    etf_pe_history: Sequence[float] | None = None,
    spy_pe: float | None = None,
    xlk_pe: float | None = None,
    top_n: int = 10,
) -> dict:
    """Weighted valuation of an ETF from its constituents.

    Args:
        ticker: the ETF symbol (informational).
        constituents: {ticker: {"price", "eps_ttm", "eps_fwd", "fcf",
            "mcap", "rev_growth", "eps_growth"}} — each value None-safe.
        weights: {ticker: weight} (fractions summing to 1). When None or
            empty, equal-weight over the present constituents.
        etf_pe_history: the ETF's own trailing P/E series (for the
            valuation-percentile leg).
        spy_pe / xlk_pe: benchmark P/Es for the vs-SPY / vs-XLK legs.
        top_n: how many names to include in the concentration leg.

    Returns a dict with every metric None-safe; ``weights_used`` reports
    whether the weights were provided or equal-weighted.
    """
    present = [t for t in constituents if any(
        v is not None for v in constituents[t].values()
    )]
    if not present:
        return {
            "ticker": ticker, "weighted_pe": None, "forward_pe": None,
            "earnings_yield": None, "fcf_yield": None, "rev_growth": None,
            "eps_growth": None, "valuation_percentile": None,
            "vs_spy": None, "vs_xlk": None, "top_n_weight": None,
            "n_constituents": 0, "weights_used": "none",
        }
    w = _renorm(weights, present) if weights else {t: 1.0 / len(present) for t in present}

    eps_map = {t: c.get("eps_ttm") for t, c in constituents.items()}
    fwd_map = {t: c.get("eps_fwd") for t, c in constituents.items()}
    price_map = {t: c.get("price") for t, c in constituents.items()}
    fcf_map = {t: c.get("fcf") for t, c in constituents.items()}
    mcap_map = {t: c.get("mcap") for t, c in constituents.items()}
    revg_map = {t: c.get("rev_growth") for t, c in constituents.items()}
    epsg_map = {t: c.get("eps_growth") for t, c in constituents.items()}

    wpe = _harmonic_pe(w, eps_map, price_map)
    fpe = _harmonic_pe(w, fwd_map, price_map)
    ey = (1.0 / wpe) if wpe and wpe > 0 else None
    fcf_y = None
    fcf_contrib = {t: w for t, w in w.items() if fcf_map.get(t) is not None and mcap_map.get(t) is not None}
    fcf_total = sum(fcf_contrib.values())
    if fcf_total > 0:
        num = sum((w / fcf_total) * float(fcf_map[t]) for t, w in fcf_contrib.items())
        den = sum((w / fcf_total) * float(mcap_map[t]) for t, w in fcf_contrib.items())
        if den and den > 0:
            fcf_y = num / den

    top_w = None
    if w:
        top_w = sum(sorted(w.values(), reverse=True)[:top_n])

    revg = _weighted_avg(w, revg_map)
    epsg = _weighted_avg(w, epsg_map)
    return {
        "ticker": ticker,
        "weighted_pe": round(wpe, 2) if wpe is not None else None,
        "forward_pe": round(fpe, 2) if fpe is not None else None,
        "earnings_yield": round(ey, 4) if ey is not None else None,
        "fcf_yield": round(fcf_y, 4) if fcf_y is not None else None,
        "rev_growth": round(revg, 4) if revg is not None else None,
        "eps_growth": round(epsg, 4) if epsg is not None else None,
        "valuation_percentile": round(_percentile_rank(etf_pe_history or [], wpe), 3) if wpe is not None and etf_pe_history else None,
        "vs_spy": round(wpe / spy_pe, 3) if wpe is not None and spy_pe else None,
        "vs_xlk": round(wpe / xlk_pe, 3) if wpe is not None and xlk_pe else None,
        "top_n_weight": round(top_w, 4) if top_w is not None else None,
        "n_constituents": len(present),
        "weights_used": "provided" if weights else "equal",
    }


__all__ = ["etf_valuation"]
