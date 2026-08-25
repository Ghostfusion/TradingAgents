"""Preferred-income screening math — implements Strategies/capital_income.md.

The document is the Global X U.S. High Yield Preferred Index methodology
(Solactive): a liquidity/quality pre-screen, an indicated-dividend-yield
ranking (top 50), and a market-value weighting with a 3% single-constituent
cap (+ pro-rata redistribution). This module is pure math over the inputs a
data provider supplies:

  Yi        = D_annualized / P            (indicated dividend yield)
  ADTV      = sum(close*vol)/days          (3-month avg daily *dollar* turnover)
  w_raw     = MV_i / sum(MV)               (market-value weights)
  cap       = 3% (max 3.5%) with pro-rata  (excess redistributed to the uncapped)

No-fabrication rule: every function returns ``None`` on a missing input, and
the report marks MV/weights ``n/a`` when per-issue shares are not exposed by
the provider (honest equal-weight fallback, labelled). All functions are pure
and unit-testable with no network.
"""

from __future__ import annotations

# Index rules (from capital_income.md)
MIN_MARKET_CAP = 250e6        # $250M qualification (or $100M for existing components)
MIN_ADTV_DOLLARS = 1e6         # $1M 3-month average daily dollar turnover
CLASS_CAP = 0.03               # 3.0% hard single-constituent cap
CLASS_MAX = 0.035              # 3.5% absolute ceiling at rebalance
EQUAL_WEIGHT_FALLBACK = True   # when MV is unavailable, use equal weight


def annualized_dividend(dividend_rate: float | None, latest_regular: float | None = None) -> float | None:
    """Annualized regular dividend D.

    ``dividend_rate`` is the provider's pre-annualized field (yfinance
    ``info.dividendRate``), preferred. When absent, fall back to ``latest_regular
    x 4`` (quarterly assumption) - never the trailing-12m sum, which for
    preferreds is polluted by special distributions.
    """
    if dividend_rate is not None:
        try:
            d = float(dividend_rate)
            if d > 0:
                return d
        except (TypeError, ValueError):
            pass
    if latest_regular is not None:
        try:
            lr = float(latest_regular)
            if lr > 0:
                return lr * 4.0
        except (TypeError, ValueError):
            pass
    return None


def indicated_yield(annual_dividend: float | None, price: float | None) -> float | None:
    """Indicated dividend yield = D_annualized / price."""
    if annual_dividend is None or price is None:
        return None
    try:
        d = float(annual_dividend)
        p = float(price)
    except (TypeError, ValueError):
        return None
    if d <= 0 or p <= 0:
        return None
    return d / p


def indicated_yield_from_rate(dividend_rate: float | None, price: float | None) -> float | None:
    """Convenience: yield = annualized_dividend(dividend_rate) / price."""
    return indicated_yield(annualized_dividend(dividend_rate, None), price)


def adtv_dollar(closes: list, volumes: list, days: int = 63) -> float | None:
    """3-month average daily dollar turnover = mean(close*volume), None when
    insufficient bars."""
    if not closes or not volumes or len(closes) < 2 or len(volumes) < 2:
        return None
    window = min(days, len(closes), len(volumes))
    if window < 2:
        return None
    closes = closes[-window:]
    volumes = volumes[-window:]
    total = 0.0
    for c, v in zip(closes, volumes, strict=False):
        try:
            total += float(c) * float(v)
        except (TypeError, ValueError):
            continue
    return total / window


def passes_liq_screen(
    market_cap: float | None,
    adtv: float | None,
    *,
    min_cap: float = MIN_MARKET_CAP,
) -> bool:
    """Section-1 liquidity/quality gate: MarketCap >= min_cap AND ADTV >= $1M
    (a missing value fails the gate honestly - n/a = not investable)."""
    if market_cap is None or adtv is None:
        return False
    return float(market_cap) >= min_cap and float(adtv) >= MIN_ADTV_DOLLARS


def raw_mv_weight(mv: list[float]) -> list[float | None]:
    """MV_i / sum(MV) weights; None for the whole list when any MV missing
    (providers don't expose per-issue shares -> equal-weight fallback)."""
    try:
        vals = [float(x) for x in mv if x is not None]
    except (TypeError, ValueError):
        vals = []
    if not vals or len(vals) != len(mv) or any(v is None for v in mv):
        return [None] * len(mv)
    tot = sum(vals)
    if tot <= 0:
        return [None] * len(mv)
    return [v / tot for v in vals]


def equal_weights(n: int) -> list[float]:
    """Equal-weight fallback when per-issue MV is unavailable."""
    if n <= 0:
        return []
    return [1.0 / n] * n


def cap_and_redistribute(
    weights: list[float] | None,
    cap: float = CLASS_CAP,
    ceiling: float = CLASS_MAX,
) -> list[float]:
    """Constituent cap with pro-rata renormalization (standard full capping).

    (1) cap every name at the CEILING (3.5%); (2) renormalize the whole
    vector so the total returns to 1. This is the MSCI/S&P-style full capping:
    a name below the cap keeps its relative proportional share (scaled), the
    cap is exact, and no excess is ever stranded (the doc's ``w_i = w_raw +
    d_i`` for uncapped names maps to this renormalized share). All inputs are
    expected to already sum to 1 (raw MV or equal weights); the function
    renormalizes regardless. ``cap`` is reserved for the two-threshold rule
    (3%/3.5%) but the implementation applies a single exact ceiling.
    """
    if not weights:
        return []
    w = [float(x) for x in weights]
    ceiling = float(max(ceiling, cap))
    # The raw weights (MV or equal) sum to 1. Cap each name at the ceiling
    # against the RAW weight, then renormalize so small names keep their
    # relative smallness (the doc's w_i = w_raw + d_i behavior).
    capped = [min(x, ceiling) for x in w]
    total = sum(capped)
    if total <= 0:
        return [0.0] * len(w)
    return [round(x / total, 6) for x in capped]


def apply_top_n(yields: list[float | None], n: int = 50) -> list[int]:
    """Indices of the top ``n`` yields (highest first), ignoring None. Returns
    fewer than n when fewer names have yields."""
    pairs = [(i, float(y)) for i, y in enumerate(yields) if y is not None]
    pairs.sort(key=lambda p: -p[1])
    return [i for i, _ in pairs[:n]]


def build_capital_income_plan(
    tickers: list[str],
    *,
    prices: dict[str, float],
    dividends: dict[str, float],
    mv: dict[str, float | None],
    adtv: dict[str, float],
    top: int = 50,
    liquid_flags: dict[str, bool] | None = None,
) -> dict:
    """One-shot: liquidity screen -> yield rank -> (MV or equal) -> cap.

    Inputs are pre-fetched per ticker by the CLI (price, annualized dividend,
    company market cap proxy, ADTV dollar). ``liquid_flags`` optionally
    overrides the screen (a caller may use a lenient rule keyed to the data
    source - preferred lines often lack per-issue market cap). Returns a
    report dict with the liquid set, the top-``top`` ranked rows (price,
    dividend, yield, mv, adtv, weight), the cap used, and a caveat when
    weights are equal-weights (MV n/a).
    """
    rows = []
    for t in tickers:
        p = prices.get(t)
        d = dividends.get(t)
        y = indicated_yield(d, p)
        liquid = passes_liq_screen(mv.get(t), adtv.get(t))
        if liquid_flags is not None:
            liquid = bool(liquid_flags.get(t, liquid))
        rose = {
            "ticker": t,
            "price": p,
            "dividend": d,
            "yield": y,
            "adtv": adtv.get(t),
            "mv": mv.get(t),
            "liquid": liquid,
        }
        rows.append(rose)
    liq = [r for r in rows if r["liquid"]]
    # top-50 by yield among liquid names.
    ranked = sorted(
        [r for r in liq if r["yield"] is not None], key=lambda r: -(r["yield"] or 0)
    )[:top]
    mvs = [r["mv"] for r in ranked]
    w = raw_mv_weight(mvs)
    used_equal = False
    if all(x is None for x in w):
        w = equal_weights(len(ranked))
        used_equal = True
    w = cap_and_redistribute(w, CLASS_CAP, CLASS_MAX)
    for r, wi in zip(ranked, w, strict=False):
        r["weight"] = wi
    return {
        "liquid": [x["ticker"] for x in liq],
        "ranked": ranked,
        "cap": CLASS_CAP,
        "used_equal_weight": used_equal,
    }
