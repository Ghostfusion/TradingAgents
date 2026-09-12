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

The high-low spread estimators (Corwin-Schultz / Abdi-Ranaldo) give a name's
daily proportional cost floor from OHLC alone; the liquidity gate treats that
as a *floor*, and a quoted spread stays authoritative when the caller has one.
"""

from __future__ import annotations

_MIN_SPREAD_BARS = 5


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
    adv_dollar: float | None = None,
    min_dollar_volume: float | None = None,
    spread_bps: float | None = None,
    max_spread_bps: float | None = None,
) -> dict:
    """Composite liquidity/ownership risk verdict: LIQUID / CAUTION / ILLIQUID.

    Each checked input either confirms the current verdict or bumps it up;
    unknown inputs are ignored (never fail the read). Thresholds come from
    risk2.md (turnover floor 0.5%, IWF < 0.5, HHI > 2500). Optional dollar
    volume / spread guards (mean-reversion slippage): when adv_dollar /
    spread_bps are supplied and the matching thresholds are set, a thin book
    (dollar volume below the floor) or a wide estimated spread (above the bps
    cap) bumps the verdict to ILLIQUID - a dip-buy on a thin order book faces
    severe slippage.
    """
    dangers: list[str] = []
    verdict = "liquid"
    if illiq is not None and illiq > illiq_high:
        verdict = "illiquid"
        dangers.append(f"ILLIQ={illiq:.4f} (high price impact)")
    if (
        min_dollar_volume is not None
        and adv_dollar is not None
        and adv_dollar < min_dollar_volume
    ):
        verdict = "illiquid"
        dangers.append(
            f"ADV20d ${adv_dollar / 1e6:.1f}M < ${min_dollar_volume / 1e6:.1f}M floor"
        )
    if max_spread_bps is not None and spread_bps is not None and spread_bps > max_spread_bps:
        verdict = "illiquid"
        dangers.append(f"spread {spread_bps:.1f}bps > {max_spread_bps:.0f}bps cap")
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


def kyle_lambda(
    closes: list,
    volumes: list,
    min_obs: int = 30,
) -> float | None:
    """Kyle lambda (price-impact slope) from daily bars.

    ``Delta P_t = alpha + lambda * Q_t + eps`` where ``Q_t`` is the signed
    flow proxy ``sign(dP_t) * volume_t`` and ``lambda`` is the OLS slope —
    the price change per unit of signed volume. Larger lambda = thinner book
    (a small order moves the price). Daily-bar proxy: no quote data, so it is
    a cross-sectional / relative liquidity read, never an absolute market
    quote. Returns None with too little history or a degenerate regression
    (zero flow variance). Uses the repo-standard gaussian-elimination inverse
    (2x2) so it stays pure and offline.
    """
    import math as _math

    n = min(len(closes), len(volumes))
    if n < min_obs + 1:
        return None
    dp: list[float] = []
    q: list[float] = []
    for i in range(1, n):
        pc = float(closes[i - 1])
        cc = float(closes[i])
        v = float(volumes[i])
        if pc <= 0 or cc <= 0 or v <= 0 or not _math.isfinite(pc + cc + v):
            continue
        d = cc - pc
        dp.append(d)
        q.append((1.0 if d >= 0.0 else -1.0) * v)
    m = len(dp)
    if m < min_obs:
        return None
    mean_d = sum(dp) / m
    mean_q = sum(q) / m
    s_qq = sum((x - mean_q) ** 2 for x in q)
    if s_qq <= 0:
        return None
    s_dq = sum((dp[i] - mean_d) * (q[i] - mean_q) for i in range(m))
    lam = s_dq / s_qq
    if not _math.isfinite(lam):
        return None
    return round(lam, 8)


def roll_spread(closes: list, min_obs: int = 30) -> float | None:
    """Roll (1984) effective-spread estimator from daily prices alone.

    ``spread = 2 * sqrt(-Cov(Delta P_t, Delta P_{t-1}))`` when the first
    autocovariance of price changes is negative. Returns a spread proxy in
    **price units** (None when the autocovariance >= 0 or the series is too
    short). Use as a relative / cross-sectional liquidity proxy - it assumes
    zero drift, no autocorrelation in the efficient price, and symmetric
    spreads, so it under-estimates the true spread on daily bars.
    """
    import math as _math

    vals = []
    for c in closes:
        try:
            f = float(c)
        except (TypeError, ValueError):
            continue
        if f > 0:
            vals.append(f)
    if len(vals) < min_obs + 1:
        return None
    dp = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
    n = len(dp)
    mean = sum(dp) / n
    cov = sum((dp[i] - mean) * (dp[i - 1] - mean) for i in range(1, n)) / (n - 1)
    if cov >= 0:
        return None
    spread = 2.0 * _math.sqrt(-cov)
    return round(spread, 6) if _math.isfinite(spread) and spread > 0 else None


def _spread_bars(closes, highs, lows) -> list[tuple[float, float, float]] | None:
    """Align (close, high, low) bars for the high-low spread estimators.

    Requires three same-length series of at least ``_MIN_SPREAD_BARS`` bars
    with positive close/high/low and high >= low on every bar. Ragged /
    misaligned lengths, non-numeric entries, or a short sample return ``None``
    (never raise).
    """
    if closes is None or highs is None or lows is None:
        return None
    try:
        n = len(closes)
        if n != len(highs) or n != len(lows) or n < _MIN_SPREAD_BARS:
            return None
        bars = [(float(closes[i]), float(highs[i]), float(lows[i])) for i in range(n)]
    except (TypeError, ValueError):
        return None
    if any(c <= 0 or h <= 0 or lo <= 0 or h < lo for c, h, lo in bars):
        return None
    return bars


def corwin_schultz(closes: list, highs: list, lows: list) -> dict | None:
    """Corwin & Schultz (2012) proportional spread from daily high/low ranges.

    ``beta = ln(H_t/L_t)^2 + ln(H_{t+1}/L_{t+1})^2`` (single-day ranges),
    ``gamma = ln(H^(2)/L^(2))^2`` (the two-day range), ``alpha =
    (sqrt(2*beta)-sqrt(beta))/(3-2*sqrt(2)) - sqrt(gamma/(3-2*sqrt(2)))``,
    ``S = 2*(exp(alpha)-1)/(1+exp(alpha))`` averaged over overlapping two-day
    windows. If any window's corrected spread is negative (the two-day range
    correction, e.g. a gap day) the estimate is unavailable -> ``None``; the
    negative is never clamped to a fake spread. ``closes`` anchor the sample
    length/alignment, though only the high/low ranges enter the formula.

    The result is a **daily proportional cost floor**; the liquidity gate uses
    it as a floor and keeps a quoted spread authoritative when one exists (the
    caller decides which wins). ``n`` is the bar count.
    """
    import math as _math

    bars = _spread_bars(closes, highs, lows)
    if bars is None:
        return None
    denom = 3.0 - 2.0 * _math.sqrt(2.0)
    estimates: list[float] = []
    for t in range(len(bars) - 1):
        _, h0, l0 = bars[t]
        _, h1, l1 = bars[t + 1]
        beta = _math.log(h0 / l0) ** 2 + _math.log(h1 / l1) ** 2
        if beta <= 0:
            return None
        gamma = _math.log(max(h0, h1) / min(l0, l1)) ** 2
        alpha = (
            (_math.sqrt(2.0 * beta) - _math.sqrt(beta)) / denom
            - _math.sqrt(gamma / denom)
        )
        s = 2.0 * (_math.exp(alpha) - 1.0) / (1.0 + _math.exp(alpha))
        if not _math.isfinite(s) or s < 0:
            return None
        estimates.append(s)
    if not estimates:
        return None
    return {"spread": sum(estimates) / len(estimates),
            "basis": "corwin-schultz", "n": len(bars)}


def abdi_ranaldo(closes: list, highs: list, lows: list) -> dict | None:
    """Abdi & Ranaldo (2017) proportional spread from close/high/low.

    Two-moment form: ``S = sqrt(4 * mean_t[(c_t - eta_t)(c_t - eta_{t+1})])``
    with log close ``c_t`` and log mid-range ``eta_t = (ln H_t + ln L_t)/2``
    (Abdi & Ranaldo, *A Simple Estimation of Bid-Ask Spreads from Daily Close,
    High, and Low Prices*, Review of Financial Studies 30(12), 2017). When the
    term under the square root is negative the paper's published treatment
    floors it at zero; here the estimate is instead unavailable -> ``None``
    (never a clamped or fabricated spread).

    Same no-fabrication contract as :func:`corwin_schultz`: a **daily
    proportional cost floor**, with quoted spreads authoritative when the
    caller has them. ``n`` is the bar count.
    """
    import math as _math

    bars = _spread_bars(closes, highs, lows)
    if bars is None:
        return None
    moments = []
    for t in range(len(bars) - 1):
        c0, h0, l0 = bars[t]
        _, h1, l1 = bars[t + 1]
        c = _math.log(c0)
        eta_t = 0.5 * (_math.log(h0) + _math.log(l0))
        eta_next = 0.5 * (_math.log(h1) + _math.log(l1))
        moments.append((c - eta_t) * (c - eta_next))
    term = 4.0 * sum(moments) / len(moments)
    if not _math.isfinite(term) or term < 0:
        return None
    spread = _math.sqrt(term)
    return {"spread": spread, "basis": "abdi-ranaldo", "n": len(bars)}


def spread_estimate(closes: list, highs: list, lows: list) -> dict | None:
    """Aggregate daily proportional spread from both high-low estimators.

    Runs :func:`corwin_schultz` and :func:`abdi_ranaldo` on the same bars and
    returns ``{"spread", "basis", "n", "components"}``. The aggregate is the
    median of the available component spreads (the single one when only one
    survives); ``basis`` is ``"median(both)"``, ``"corwin-schultz"`` or
    ``"abdi-ranaldo"``. ``None`` when neither estimator is defined. The number
    is a **daily cost floor** for the liquidity gate, not a quote substitute:
    a quoted spread stays authoritative when available (the caller decides).
    """
    import statistics as _stats

    cs = corwin_schultz(closes, highs, lows)
    ar = abdi_ranaldo(closes, highs, lows)
    cs_spread = cs["spread"] if cs else None
    ar_spread = ar["spread"] if ar else None
    components = {"corwin-schultz": cs_spread, "abdi-ranaldo": ar_spread}
    available = [(name, v) for name, v in components.items() if v is not None]
    if not available:
        return None
    if len(available) == 1:
        basis, spread = available[0]
        n = (cs or ar)["n"]
    else:
        basis = "median(both)"
        spread = _stats.median([cs_spread, ar_spread])
        n = min(cs["n"], ar["n"])
    return {"spread": spread, "basis": basis, "n": n, "components": components}
