"""Liquidity & ownership-risk metrics (pure, offline) — implements Strategies/risk2.md.

Institutional risk managers scale index weights, measure price impact, and
flag governance concentration with exact formulas. This module computes those
metrics locally from the project's OWN data (float shares, shares outstanding,
price history OHLCV, short interest ADV, institutional holdings) instead of a
paid data entitlement:

  IWF            = FloatShares / TotalSharesOutstanding          (1. index weight)
  FloatTurnover  = ADV / FloatShares                             (2. supply churn)
  ILLIQ          = mean(|R_t| / DollarVolume_t)                  (3. price impact / $)
  DaysToAbsorb   = SharesToLiquidate / (ADV * alpha)             (4. overhang)
  HHI            = sum(s_i^2)                                    (5. concentration)

Sources for each input are already in the project: fetch_float_shares (FMP ->
yfinance info), the ``shares`` canonical alias (moomoo balance sheet), the
vendor OHLCV chain (closes + volumes -> ADV + dollar volume), short-interest
vendors (ADV, days-to-cover), and institution-holdings vendors (% of float).

No-fabrication rule: every metric returns ``None`` when an input is missing;
a composite read reports unknown rather than guessing. All functions are pure
and unit-testable with no network.
"""

from __future__ import annotations


def free_float_factor(
    float_shares: float | None, total_shares: float | None
) -> float | None:
    """Investable weight factor = float / total outstanding (index-eligible %).

    IWF < 0.50 signals structural passive under-allocation (per risk2.md).
    """
    if float_shares is None or total_shares is None:
        return None
    try:
        fs = float(float_shares)
        ts = float(total_shares)
    except (TypeError, ValueError):
        return None
    if fs < 0 or ts <= 0:
        return None
    return fs / ts


def float_turnover(adv: float | None, float_shares: float | None) -> float | None:
    """Float turnover = average daily volume / float shares (2).

    0.5%-100%/day is the healthy tradable band; below is slippage risk, above
    is speculative churn / squeeze risk.
    """
    if adv is None or float_shares is None:
        return None
    try:
        adv = float(adv)
        fs = float(float_shares)
    except (TypeError, ValueError):
        return None
    if adv < 0 or fs <= 0:
        return None
    return adv / fs


def amihud_illiquidity(closes: list, volumes: list) -> float | None:
    """Amihud ILLIQ = mean(|daily return| / daily dollar volume).

    Dollar volume = close * volume (assumes per-share volume). Higher ILLIQ
    means a small order moves the price substantially (illiquid). Requires at
    least 2 closes + matching volumes; None otherwise (never fabricates).
    """
    if (
        not closes
        or not volumes
        or len(closes) < 2
        or len(volumes) < 2
    ):
        return None
    n = min(len(closes), len(volumes))
    closes = closes[-n:]
    volumes = volumes[-n:]
    ratios = []
    for t in range(1, n):
        prev = float(closes[t - 1])
        cur = float(closes[t])
        vol = float(volumes[t])
        if prev and vol and vol > 0:
            r = abs(cur / prev - 1.0)
            dollar = cur * vol
            if dollar > 0:
                ratios.append(r / dollar)
    if not ratios:
        return None
    return sum(ratios) / len(ratios)


def days_to_absorb(
    shares_to_liquidate: float | None,
    adv: float | None,
    alpha: float = 0.15,
) -> float | None:
    """Days for the public market to absorb a block at a participation cap.

    alpha: max fraction of daily volume to participate without breaking the
    market (10-20%). If a 70% owner unwinds X% of the company, this is how many
    days of heavy supply the float must absorb.
    """
    if shares_to_liquidate is None or adv is None:
        return None
    try:
        sh = float(shares_to_liquidate)
        adv = float(adv)
    except (TypeError, ValueError):
        return None
    try:
        alpha = float(alpha)
    except (TypeError, ValueError):
        alpha = 0.15
    if sh < 0 or adv <= 0 or alpha <= 0:
        return None
    return sh / (adv * alpha)


def ownership_hhi(holdings: list[float] | None) -> float | None:
    """Herfindahl-Hirschman index over ownership percentages (0-10000).

    Pass a per-holder ``holder_pct`` list (0..100). Sum of squares; 0 =
    dispersed, 10000 = single 100% owner. Best-effort: None when no per-holder
    breakdown is available.
    """
    if not holdings:
        return None
    total_sq = 0.0
    for h in holdings:
        try:
            s = float(h)
        except (TypeError, ValueError):
            continue
        if s < 0:
            continue
        total_sq += s * s
    if total_sq == 0:
        return None
    return total_sq


def liquidity_verdict(
    illiq: float | None,
    float_turnover: float | None,
    days_to_absorb: float | None,
    hhi: float | None = None,
    iwf: float | None = None,
    *,
    illiq_high: float = 1e-6,
    float_turn_min: float = 0.005,
    float_turn_max: float = 1.0,
    days_max: float = 30.0,
    hhi_max: float = 2500.0,
    iwf_min: float = 0.5,
) -> dict:
    """Composite liquidity/ownership risk verdict: LIQUID / CAUTION / ILLIQUID.

    Each checked input either confirms the current verdict or bumps it up;
    unknown inputs are ignored (never fail the read). Thresholds come from
    risk2.md (turnover floor 0.5%, IWF < 0.5, HHI > 2500).
    """
    dangers: list[str] = []
    verdict = "liquid"
    if illiq is not None and illiq > illiq_high:
        verdict = "illiquid"
        dangers.append(f"ILLIQ={illiq:.4f} (high price impact)")
    if float_turnover is not None and float_turnover < float_turn_min:
        if verdict == "liquid":
            verdict = "caution"
        dangers.append(f"float-turnover={float_turnover:.3%} below {float_turn_min:.2%}")
    if float_turnover is not None and float_turnover > float_turn_max:
        verdict = "illiquid"
        dangers.append(f"float-turnover={float_turnover:.2%} above {float_turn_max:.0%} (squeeze)")
    if days_to_absorb is not None and days_to_absorb > days_max:
        if verdict == "liquid":
            verdict = "caution"
        dangers.append(f"days-to-absorb={days_to_absorb:.0f} > {days_max:.0f}")
    if iwf is not None and iwf < iwf_min:
        verdict = "illiquid"
        dangers.append(f"IWF={iwf:.2%} below {iwf_min:.2%}")
    if hhi is not None and hhi > hhi_max:
        if verdict == "liquid":
            verdict = "caution"
        dangers.append(f"HHI={hhi:.0f} > {hhi_max:.0f}")
    return {"verdict": verdict, "dangers": dangers}


def volume_share_slippage(order_qty: float, adv: float, price: float,
                          vol_limit: float = 0.1,
                          price_impact: float = 0.025) -> float | None:
    """Lean VolumeShareSlippageModel: per-share cost from participation rate.

    Cost = price * price_impact * min(qty/ADV, vol_limit)^2 — a classic
    square-root-ish participation model. ``vol_limit`` caps the participation
    assumption (a 2%-of-ADV order can't assume >10% participation). Returns
    the per-share slippage cost in price units, or None when ADV/price are
    missing/non-positive (never fabricated).
    """
    try:
        q = float(order_qty)
        a = float(adv)
        p = float(price)
    except (TypeError, ValueError):
        return None
    if a <= 0 or p <= 0 or q <= 0:
        return None
    participation = min(q / a, abs(float(vol_limit)))
    return p * abs(float(price_impact)) * participation ** 2


def market_impact_slippage(order_qty: float, adv: float, price: float,
                           impact_coeff: float = 0.1) -> float | None:
    """Lean MarketImpactSlippageModel (Almgren-Chriss style): impact ∝ qty/ADV.

    Per-share cost = price * impact_coeff * (order/ADV). Simpler than the
    volume-share square term; good for large-block orders. None on missing
    inputs.
    """
    try:
        q = float(order_qty)
        a = float(adv)
        p = float(price)
    except (TypeError, ValueError):
        return None
    if a <= 0 or p <= 0 or q <= 0:
        return None
    return p * abs(float(impact_coeff)) * (q / a)
