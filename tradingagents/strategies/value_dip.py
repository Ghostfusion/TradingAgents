"""Value Dip + Swing hybrid — deterministic calculations.

Implements the math in ``Strategies/Value_Dip_swing.md`` and
``Strategies/Value_Dip_swing_Continue.md``: buying fundamentally sound
assets at a margin of safety (value floor) into an oversold technical dip
(mean-reversion entry) with a tranche scale-in execution plan and strict
portfolio risk.

Pure, offline-testable functions; no network, no state. The analyst tools
(``agents/utils/value_dip_tools.py``) and the ``--scan value-dip`` screener
mode feed OHLCV / canonical financials in and read the flags back.

Gap coverage vs the existing codebase:

  * Bollinger %b  — vendors expose raw bands but no deterministic %b exists
  * valuation Z   — ``normalized.percentile_hist`` is a percentile rank, not
    a z-score against the name's own history
  * FCF yield     — FCF extraction only existed inside the DCF tool (private)
  * breakeven win rate / expectancy — absent from ``evaluate``/``journal``
  * tranche scale-in plan (P1/P2/P3, weighted avg entry, composite stop,
    capital-at-risk check) — nothing in ``portfolio``/``contract``
  * the hybrid allocation matrix (value floor + technical entry + trade risk
    + exit target) as one combined setup gate
"""

from __future__ import annotations

import math

from .size import atr as _atr
from .swing import rsi as _rsi

__all__ = [
    "bollinger_pct_b",
    "zscore",
    "valuation_z_read",
    "fcf_yield",
    "breakeven_win_rate",
    "expectancy",
    "tranche_plan",
    "tranche_risk_read",
    "balance_sheet_health",
    "profitability_quality",
    "macd_divergence",
    "volume_dry_up",
    "trigger_candle",
    "higher_low_structure",
    "vdu_entry_setup",
    "support_structure",
    "fib_retrace_entry",
    "_stochastic_oversold",
    "decline_driver_check",
    "value_dip_setup",
]

#: Value-floor thresholds from the matrix in Value_Dip_swing.md §4.
MOS_FLOOR = 0.20  # margin of safety >= 20%
FCFY_FLOOR = 0.06  # FCF yield >= 6%
RSI_ENTRY = 35.0  # RSI(14) <= 35
PCTB_ENTRY = 0.10  # %b <= 0.10 (near/piercing the lower band)
MAX_ACCOUNT_RISK = 0.02  # <= 2% account risk
STOP_ATR_MULT = 2.0  # the trade-risk row's 2 x ATR stop
RR_TARGET = 2.5  # exit-target row: R:R >= 2.5
Z_CHEAP = -1.5  # valuation Z <= -1.5 = trading significantly below norm


def _mean(values: list) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def bollinger_pct_b(closes: list, window: int = 20, k: float = 2.0) -> dict | None:
    """Bollinger Band %b = (price - lower band) / (upper - lower).

    ``%b <= 0`` signals the price is piercing (or below) the lower
    2-standard-deviation band; ``<= 0.10`` is the matrix's mean-reversion
    entry zone. Returns None with fewer than ``window`` closes.
    """
    if not closes or len(closes) < window or window <= 0:
        return None
    sample = [float(c) for c in closes[-window:]]
    mid = sum(sample) / len(sample)
    var = sum((c - mid) ** 2 for c in sample) / len(sample)
    sd = math.sqrt(var)
    lower = mid - k * sd
    upper = mid + k * sd
    price = float(closes[-1])
    if upper - lower <= 0:
        return {"pct_b": None, "price": price, "lower": lower, "upper": upper, "mid": mid}
    return {
        "pct_b": round((price - lower) / (upper - lower), 4),
        "price": price,
        "lower": round(lower, 4),
        "upper": round(upper, 4),
        "mid": round(mid, 4),
    }


def zscore(value: float | None, series: list, min_n: int = 4) -> float | None:
    """(value - mean) / std over ``series``; None when data is insufficient.

    Sign-preserving (a *negative* multiple value stays negative instead of
    being silently dropped, unlike the DCF's positive-only FCF series).
    """
    vals = [float(v) for v in series if v is not None]
    if value is None or len(vals) < min_n:
        return None
    m = sum(vals) / len(vals)
    if len(vals) < 2:
        return None
    var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    if var <= 0:
        return None
    return (float(value) - m) / math.sqrt(var)


def valuation_z_read(
    multiple_values: list,
    current_multiple: float | None,
    min_n: int = 4,
) -> dict:
    """Historical-deviation read of a valuation multiple vs its own history.

    ``multiple_values`` = the name's trailing P/E, EV/EBITDA or P/FCF series
    (one value per period); ``current_multiple`` = today's value. Verdict:
    ``cheap`` when Z <= -1.5, ``rich`` when Z >= +1.5, else ``fair``; None /
    ``unknown`` when the series is too short.
    """
    z = zscore(current_multiple, multiple_values, min_n=min_n)
    if z is None:
        return {"z": None, "mean": None, "std": None, "n": 0, "verdict": "unknown"}
    m = _mean(multiple_values)
    vals = [float(v) for v in multiple_values if v is not None]
    var = (
        sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
        if m is not None and len(vals) >= 2
        else 0.0
    )
    std = math.sqrt(var) if var > 0 else None
    verdict = "cheap" if z <= Z_CHEAP else ("rich" if z >= 1.5 else "fair")
    return {
        "z": round(z, 3),
        "mean": round(m, 4) if m is not None else None,
        "std": round(std, 4) if std is not None else None,
        "n": len(vals),
        "verdict": verdict,
    }


def fcf_yield(free_cash_flow: float | None, market_cap: float | None) -> float | None:
    """Free cash flow yield = FCF / market cap (fraction).

    None when either input is missing or market cap is not positive.
    """
    if free_cash_flow is None or market_cap is None or market_cap <= 0:
        return None
    return float(free_cash_flow) / float(market_cap)


def breakeven_win_rate(rr: float | None) -> float | None:
    """Breakeven win rate = 1 / (1 + R:R); None when R:R is not positive."""
    if rr is None or rr <= 0:
        return None
    return 1.0 / (1.0 + float(rr))


def expectancy(p_win: float | None, avg_win: float | None, avg_loss: float | None) -> float | None:
    """E = p_win * avg_win - (1 - p_win) * avg_loss (per-trade expectancy).

    ``avg_win`` / ``avg_loss`` are average win / loss *amounts* (any unit).
    None when inputs are missing; avg_loss is bounded away from zero so the
    (1-p) loss term can't be silently dropped.
    """
    if p_win is None or avg_win is None or avg_loss is None:
        return None
    p = max(0.0, min(1.0, float(p_win)))
    loss = avg_loss if avg_loss != 0 else 1e-9
    return float(p) * float(avg_win) - (1.0 - p) * float(loss)


def tranche_plan(
    p1: float,
    atr_value: float | None,
    weights: tuple = (0.3, 0.3, 0.4),
    stop_mult: float = 1.5,
    account: float = 100_000.0,
    risk_pct: float = 0.015,
) -> dict:
    """Three-tranche scale-in plan (Value_Dip_swing_Continue.md §1-2).

    * P1 = initial signal price; P2 = P1 - 1.0*ATR; P3 = P1 - 2.0*ATR
    * composite stop = P3 - stop_mult*ATR (default 1.5 x ATR below the final
      tranche)
    * weighted average entry Pbar = sum(w_i * P_i) with sum(w_i) = 1
    * N_total = (account * risk%) / (Pbar - stop); N_i = w_i * N_total
    * capital at risk = sum(N_i * (P_i - stop)) must be <= account * risk%
      (``risk_ok``) - the sizing identity always holds by construction
    * targets: T1 = Pbar + 1.8R, T2 = Pbar + 3.0R, blended R = 0.5*R1 + 0.5*R2

    Returns a dict with the tranches, levels, risk check and blended
    expectancy; ``valid=False`` when ATR is unusable.
    """
    if atr_value is None or atr_value <= 0 or p1 is None or p1 <= 0:
        return {"valid": False, "reason": "no usable ATR / entry price"}
    if not weights or abs(sum(weights) - 1.0) > 1e-9:
        return {"valid": False, "reason": "tranche weights must sum to 1.0"}
    w = [float(x) for x in weights]
    p1f = float(p1)
    a = float(atr_value)
    p2 = p1f - 1.0 * a
    p3 = p1f - 2.0 * a
    stop = p3 - float(stop_mult) * a
    if stop <= 0:
        return {"valid": False, "reason": "stop level is non-positive"}
    prices = (p1f, p2, p3)
    avg_entry = sum(wi * pi for wi, pi in zip(w, prices, strict=False))
    risk_per_share = avg_entry - stop
    if risk_per_share <= 0:
        return {"valid": False, "reason": "risk per share is non-positive"}
    max_dollar_risk = float(account) * float(risk_pct)
    total_shares = int(max_dollar_risk / risk_per_share)
    n1 = int(total_shares * w[0])
    n2 = int(total_shares * w[1])
    n3 = total_shares - (n1 + n2)
    shares = (n1, n2, n3)
    risk_usd = sum(s * (p - stop) for s, p in zip(shares, prices, strict=False))
    # Deployed capital at full scale-in: what the position actually ties up
    # near the lows. This is the measure the per-trade cap must bound - it is
    # larger than the risk budget because capital is added as price falls.
    peak_deployed = sum(s * p for s, p in zip(shares, prices, strict=False))
    r1 = 1.8
    r2 = 3.0
    t1 = avg_entry + r1 * risk_per_share
    t2 = avg_entry + r2 * risk_per_share
    blended_rr = 0.5 * r1 + 0.5 * r2
    return {
        "valid": True,
        "p1": round(p1f, 4),
        "p2": round(p2, 4),
        "p3": round(p3, 4),
        "stop": round(stop, 4),
        "avg_entry": round(avg_entry, 4),
        "risk_per_share": round(risk_per_share, 4),
        "weights": [round(x, 4) for x in w],
        "shares": list(shares),
        "total_shares": total_shares,
        "max_dollar_risk": round(max_dollar_risk, 2),
        "capital_at_risk": round(risk_usd, 2),
        "capital_at_risk_pct": round(risk_usd / float(account), 6),
        "peak_deployed": round(peak_deployed, 2),
        "peak_deployed_pct": round(peak_deployed / float(account), 6),
        "risk_ok": bool(risk_usd <= max_dollar_risk + 1e-9),
        "targets": {
            "r1": r1,
            "r2": r2,
            "t1": round(t1, 4),
            "t2": round(t2, 4),
            "blended_rr": round(blended_rr, 4),
        },
        "breakeven_win_rate": round(1.0 / (1.0 + blended_rr), 4),
    }


def tranche_risk_read(
    closes,
    weights: tuple = (0.3, 0.3, 0.4),
    stop_mult: float = 1.5,
    risk_pct: float = 0.015,
    account: float = 100_000.0,
    atr_value: float | None = None,
    max_position_pct: float = 0.30,
    max_book_position_pct: float | None = None,
) -> dict:
    """Deterministic tranche-scaling risk read for the risk governor.

    The *control* computation for the Value Dip + Swing tranche plan
    (`Value_Dip_swing_Continue.md`): it derives the worst-case measures the
    gate must enforce from **measured** prices (last close = P1, ATR from the
    close series) and **config-frozen** parameters (weights, stop multiple,
    risk budget, account) - never from the LLM, so an agent's tranche choice
    can not inflate approved size.

    Worst-case measures returned:

    * ``avg_entry`` / ``risk_per_share`` - the tranche-weighted entry and the
      per-share risk distance (feed ``entry_price=avg_entry`` into
      ``build_position_contract`` so the G1 stop/risk matches the tranche
      plan, not the first tranche price)
    * ``peak_deployed_pct`` - total capital at full scale-in / account. This
      is the *missing* control: scale-in deploys more capital near the lows
      than a single entry, so the per-trade cap must bound the fully-scaled
      position (this is structurally > ``risk_pct`` by
      ``Pbar / (Pbar - stop)``)
    * ``capital_at_risk_pct`` - ``Risk$ / account`` at the hard stop
      (by construction == ``risk_pct`` - the budget the gate enforces)
    * ``peak_ok`` - ``peak_deployed_pct <= max_position_pct``
    * ``book_ok`` - ``peak_deployed_pct + book <= max_book_position_pct``
      when a book fraction is supplied
    * ``risk_ok`` - ``capital_at_risk_pct <= risk_pct`` (tautology, kept for
      audit)

    Returns ``{"valid": False}`` when the plan is unusable (no closes, bad
    ATR, weights not summing to 1 ...).
    """
    if not closes:
        return {"valid": False, "reason": "no closes"}
    p1 = float(closes[-1])
    if p1 <= 0:
        return {"valid": False, "reason": "non-positive price"}
    if atr_value is None:
        from .contract import _atr_or_proxy

        atr_value = _atr_or_proxy(closes, None, None, window=14)
    plan = tranche_plan(
        p1,
        atr_value,
        weights=weights,
        stop_mult=stop_mult,
        account=account,
        risk_pct=risk_pct,
    )
    if not plan.get("valid"):
        return plan  # carries valid=False + reason
    peak_deployed_pct = plan["peak_deployed_pct"]
    capital_at_risk_pct = plan["capital_at_risk_pct"]
    book_ok = None
    if max_book_position_pct is not None:
        book_ok = bool(peak_deployed_pct <= float(max_book_position_pct))
    return {
        "valid": True,
        "p1": plan["p1"],
        "p2": plan["p2"],
        "p3": plan["p3"],
        "stop": plan["stop"],
        "avg_entry": plan["avg_entry"],
        "risk_per_share": plan["risk_per_share"],
        "weights": plan["weights"],
        "shares": plan["shares"],
        "total_shares": plan["total_shares"],
        "peak_deployed_pct": peak_deployed_pct,
        "capital_at_risk_pct": capital_at_risk_pct,
        "peak_ok": bool(peak_deployed_pct <= float(max_position_pct)),
        "book_ok": book_ok,
        "risk_ok": bool(plan.get("risk_ok")),
        "targets": plan["targets"],
    }


# ---------------------------------------------------------------------------
# Step-1 fundamental gates (Value_Dip_swing.md §1)
# ---------------------------------------------------------------------------


def balance_sheet_health(
    debt_to_equity: float | None = None,
    current_ratio: float | None = None,
) -> dict:
    """Balance-sheet health: D/E < 1.0 OR current ratio > 1.5 (§1).

    Unknown inputs render that side None (ignored, never a failure); pass is
    None when neither side is measured. ``reasons`` lists which side passed.
    """
    d_ok = debt_to_equity is not None and debt_to_equity < 1.0
    cr_ok = current_ratio is not None and current_ratio > 1.5
    reasons = []
    if debt_to_equity is not None:
        reasons.append(f"d_e={debt_to_equity:.2f}" + ("<1.0" if d_ok else ">=1.0"))
    if current_ratio is not None:
        reasons.append(f"cr={current_ratio:.2f}" + (">1.5" if cr_ok else "<=1.5"))
    if debt_to_equity is None and current_ratio is None:
        return {
            "pass": None,
            "d_e": None,
            "current_ratio": None,
            "reasons": ["no balance-sheet data"],
        }
    return {
        "pass": bool(d_ok or cr_ok),
        "d_e": round(debt_to_equity, 4) if debt_to_equity is not None else None,
        "current_ratio": round(current_ratio, 4) if current_ratio is not None else None,
        "reasons": reasons,
    }


def profitability_quality(
    fcf: float | None = None,
    fcf_yield: float | None = None,
    roe: float | None = None,
) -> dict:
    """Step-1 profitability/quality row: positive FCF AND ROE > 15%.

    A missing side is ignored; pass is None when neither is measured. FCF may
    be given directly or as a positive ``fcf_yield`` (same sign when the cap
    is positive).
    """
    fcf_pos = None
    if fcf is not None:
        fcf_pos = fcf > 0
    elif fcf_yield is not None:
        fcf_pos = fcf_yield > 0
    roe_ok = (roe is not None and roe > 0.15) if roe is not None else None
    reasons = []
    if fcf_pos is not None:
        reasons.append("fcf_positive" if fcf_pos else "fcf_non-positive")
    if roe is not None:
        reasons.append(f"roe={roe:.1%}" + (">15%" if roe_ok else "<=15%"))
    if fcf_pos is None and roe is None:
        return {
            "pass": None,
            "fcf_positive": None,
            "roe": None,
            "reasons": ["no profitability data"],
        }
    measured = [v for v in (fcf_pos, roe_ok) if v is not None]
    return {
        "pass": bool(all(measured)),
        "fcf_positive": fcf_pos,
        "roe": round(roe, 4) if roe is not None else None,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Step-2 technical structure (Value_Dip_swing.md §2)
# ---------------------------------------------------------------------------


def _sma(series: list, n: int) -> float | None:
    if len(series) < n or n <= 0:
        return None
    return sum(series[-n:]) / n


def _ema_series(values: list, n: int) -> list:
    """Full EMA series aligned to ``values`` (None for the first n-1 bars)."""
    if not values or n <= 0:
        return [None] * len(values)
    k = 2.0 / (n + 1)
    out = [None] * (n - 1)
    ema = sum(values[:n]) / n
    out.append(ema)
    for v in values[n:]:
        ema = float(v) * k + ema * (1 - k)
        out.append(ema)
    return out


def _rsi_series(closes: list, n: int = 14) -> list:
    """Wilder RSI series aligned to ``closes`` (None for the first n bars)."""
    if len(closes) <= n:
        return [None] * len(closes)
    out = [None] * (n)
    gains = losses = 0.0
    for i in range(1, n + 1):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff

    def _val(g, loss):
        if g + loss == 0:
            return 50.0
        rs = g / loss if loss > 0 else float("inf")
        return 100.0 - 100.0 / (1.0 + rs)

    out.append(_val(gains, losses))
    for i in range(n + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff >= 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        gains = (gains * (n - 1) + gain) / n
        losses = (losses * (n - 1) + loss) / n
        out.append(_val(gains, losses))
    return out


def _macd_hist(closes, fast=12, slow=26, signal=9):
    """MACD line / signal / histogram series aligned to ``closes``.

    Returns (line, signal, hist) each the same length as ``closes`` with None
    in the warm-up region, or None when there is insufficient history.
    """
    if not closes or len(closes) < slow + signal + 2:
        return None
    ema_f = _ema_series(closes, fast)
    ema_s = _ema_series(closes, slow)
    line = [
        (fl - sl) if (fl is not None and sl is not None) else None
        for fl, sl in zip(ema_f, ema_s, strict=False)
    ]
    start = next((i for i, v in enumerate(line) if v is not None), None)
    if start is None:
        return None
    valid = line[start:]
    sig_valid = _ema_series(valid, signal)
    sig = [None] * start + sig_valid
    hist = [
        (lv - s) if (lv is not None and s is not None) else None
        for lv, s in zip(line, sig, strict=False)
    ]
    return line, sig, hist


def _pivot_troughs(series: list, k: int = 3, window: int | None = None) -> list[int]:
    """Indices of strict local minima (troughs) in ``series``."""
    if not series:
        return []
    seg = series[-window:] if window else series
    base = len(series) - len(seg)
    out = []
    for i in range(k, len(seg) - k):
        if seg[i] < min(seg[i - k : i]) and seg[i] <= min(seg[i + 1 : i + k + 1]):
            out.append(base + i)
    return out


def macd_divergence(
    closes: list,
    lows: list | None = None,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    window: int = 120,
    k: int = 3,
) -> dict:
    """Bullish momentum divergence (Daily RSI / MACD histogram, §2).

    Compares the two most recent price troughs: a LOWER price low with a
    HIGHER MACD-histogram (or RSI) low is a bullish divergence. Verdicts:

    * ``bullish-divergence`` - lower price low + higher indicator low (entry)
    * ``higher-low`` - higher price low + higher indicator low (momentum shift)
    * ``lower-low-confirmation`` - lower low + lower indicator (no reversal)
    * ``none`` / ``unknown``

    ``bullish`` is True for the first two (a usable Step-2 momentum read).
    """
    if not closes or len(closes) < max(slow + signal, 40) + 4:
        return {"verdict": "unknown", "bullish": None, "reasons": ["insufficient history"]}
    lows_series = lows if (lows and len(lows) == len(closes)) else closes
    m = _macd_hist(closes, fast, slow, signal)
    rsi_s = _rsi_series(closes, 14)
    if m is None:
        return {"verdict": "unknown", "bullish": None, "reasons": ["insufficient history"]}
    _, _, hist = m
    piv = _pivot_troughs(lows_series, k, window)
    if len(piv) < 2:
        return {"verdict": "none", "bullish": False, "reasons": ["fewer than two troughs"]}
    i1, i2 = piv[-2], piv[-1]
    pl1, pl2 = float(lows_series[i1]), float(lows_series[i2])
    hv1, hv2 = hist[i1], hist[i2]
    rv1, rv2 = rsi_s[i1], rsi_s[i2]
    if hv1 is None or hv2 is None:
        return {"verdict": "none", "bullish": False, "reasons": ["no MACD at troughs"]}
    if pl2 < pl1:  # lower price low
        verdict = "bullish-divergence" if hv2 > hv1 else "lower-low-confirmation"
    elif pl2 > pl1:  # higher price low
        verdict = "higher-low" if hv2 > hv1 else "higher-low-weak-indicator"
    else:
        verdict = "none"
    rsi_note = None
    if rv1 is not None and rv2 is not None and pl2 < pl1 and rv2 > rv1:
        rsi_note = "rsi-divergence-also"
    return {
        "verdict": verdict,
        "bullish": verdict in ("bullish-divergence", "higher-low"),
        "price_lows": (round(pl1, 4), round(pl2, 4)),
        "macd_hist_lows": (round(hv1, 6), round(hv2, 6)),
        "rsi_lows": (
            round(rv1, 2) if rv1 is not None else None,
            round(rv2, 2) if rv2 is not None else None,
        ),
        "rsi_note": rsi_note,
        "reasons": [],
    }


def volume_dry_up(
    volumes: list,
    window: int = 20,
    lookback: int = 5,
    ratio: float = 0.7,
) -> dict:
    """Volume dry-up (VDU): selling volume drops below 70% of the 20-day
    average near support (§2). ``lookback`` bars before the trigger day are
    compared against the prior ``window`` bars, so the trigger candle's own
    volume does not count against the dry-up.
    """
    if not volumes or len(volumes) < window + lookback + 1:
        return {"dry_up": None, "vdu_ratio": None}
    recent = volumes[-lookback - 1 : -1]
    prior = volumes[-window - lookback - 1 : -window - 1]
    pm = sum(prior) / len(prior) if prior else 0.0
    if pm <= 0:
        return {"dry_up": None, "vdu_ratio": None}
    rm = sum(recent) / len(recent) if recent else 0.0
    r = rm / pm
    return {"dry_up": bool(r <= ratio), "vdu_ratio": round(r, 4)}


def trigger_candle(
    closes: list,
    highs: list,
    lows: list,
    volumes: list,
    window: int = 20,
    rvol_min: float = 1.3,
) -> dict:
    """Trigger candle (§2): daily close above the prior day's high (or a
    bullish engulfing candle) on above-average volume (RVOL >= 1.3x).
    """
    if not closes or len(closes) < window + 2 or len(highs) < 2 or not volumes:
        return {"trigger": None, "rvol": None}
    avg = sum(volumes[-window - 1 : -1]) / window if window else 0.0
    rvol = volumes[-1] / avg if avg > 0 else None
    prev_high = float(highs[-2])
    close = float(closes[-1])
    close_above_prev_high = close > prev_high
    # Bullish engulfing approximation (no opens): close > prior high and
    # the prior bar closed down vs the bar before it.
    engulfing = close > prev_high and len(closes) >= 3 and float(closes[-2]) <= float(closes[-3])
    trig = bool(rvol is not None and rvol >= rvol_min and (close_above_prev_high or engulfing))
    return {
        "trigger": trig,
        "rvol": round(rvol, 3) if rvol is not None else None,
        "close_above_prior_high": close_above_prev_high,
        "engulfing": engulfing,
        "rvol_min": rvol_min,
    }


def higher_low_structure(lows: list, k: int = 3, window: int = 60) -> dict:
    """Higher-low confirmation (§2): the most recent swing low is above the
    prior swing low - selling momentum is fading."""
    piv = _pivot_troughs(lows, k, window)
    if len(piv) < 2:
        return {"higher_low": None, "recent_low": None, "prior_low": None}
    lo1, lo2 = float(lows[piv[-2]]), float(lows[piv[-1]])
    return {
        "higher_low": bool(lo2 > lo1),
        "recent_low": round(lo2, 4),
        "prior_low": round(lo1, 4),
    }


def vdu_entry_setup(
    closes: list,
    highs: list,
    lows: list,
    volumes: list,
    window: int = 20,
    rvol_min: float = 1.3,
    k: int = 3,
    support_window: int = 60,
    div_window: int = 120,
) -> dict:
    """The full Step-2 entry ladder: VDU near support -> momentum divergence /\
    higher-low -> trigger candle with volume expansion (§2 diagram).

    ``candidate`` = trigger-candle AND momentum confirmation AND (dry-up is not
    False when measured). Each sub-signal is reported; a missing sub-signal is
    ignored (never fails) per the repo convention.
    """
    if not closes or len(closes) < 30 or not volumes:
        return {"candidate": False, "reasons": ["insufficient data"]}
    dry = volume_dry_up(volumes, window=window)
    trig = trigger_candle(closes, highs, lows, volumes, window=window, rvol_min=rvol_min)
    hl = higher_low_structure(lows, k=k, window=support_window)
    mom = macd_divergence(closes, lows, window=div_window, k=k)
    reasons = []
    if dry.get("dry_up") is False:
        reasons.append("volume dry-up absent")
    if not trig.get("trigger"):
        reasons.append("no trigger candle (RVOL/close above prior high)")
    confirmation = bool(mom.get("bullish") or hl.get("higher_low"))
    if not confirmation:
        reasons.append("no momentum confirmation (divergence / higher-low)")
    dry_ok = dry.get("dry_up") is not False  # None (no data) is ignored
    candidate = bool(trig.get("trigger") and confirmation and dry_ok)
    return {
        "candidate": candidate,
        "volume_dry_up": dry,
        "trigger_candle": trig,
        "higher_low": hl,
        "momentum": mom,
        "reasons": reasons,
    }


def support_structure(
    closes: list,
    highs: list,
    lows: list,
    atr_value: float | None = None,
    sma_window: int = 200,
    base_window: int = 150,
) -> dict:
    """Major support read (§2 Step 2): multi-month consolidation base low,
    200-day SMA proximity, or neither.

    Verdicts: ``multi-month-base-support`` (price within 1.5 ATR of the
    trailing ``base_window``-bar low), ``200-day-sma-support`` (price within
    1 ATR of the 200-day SMA), ``holding-above-base`` (price above the base
    on shallow depth), else ``no-near-support``. ``unknown`` when the history
    is too short (200+ closes required).
    """
    if not closes or len(closes) < max(sma_window, base_window) + 5:
        return {"verdict": "unknown", "reasons": ["insufficient history"]}
    price = float(closes[-1])
    sma200 = _sma(closes, sma_window)
    base_low = min(float(v) for v in lows[-base_window:])
    base_high = max(float(v) for v in highs[-base_window:])
    base_depth = (price - base_low) / price if price > 0 else None
    a = atr_value if atr_value and atr_value > 0 else None
    dist_base = (price - base_low) / price if price > 0 else None
    dist_sma = (price - sma200) / sma200 if sma200 else None
    reasons = []
    if a is not None and dist_base is not None and (price - base_low) <= 1.5 * a:
        verdict = "multi-month-base-support"
        reasons.append(f"within 1.5 ATR of {base_window}-bar base low")
    elif dist_sma is not None and (
        (a is not None and abs(price - sma200) <= a) or abs(dist_sma) <= 0.03
    ):
        verdict = "200-day-sma-support"
        reasons.append("price within 1 ATR / 3% of the 200-day SMA")
    elif dist_base is not None and base_depth is not None and base_depth < 0.15:
        verdict = "holding-above-base"
        reasons.append(f"close {dist_base:.1%} above the multi-month base low")
    else:
        verdict = "no-near-support"
        reasons.append("no major weekly / base / 200-SMA support nearby")
    return {
        "verdict": verdict,
        "price": round(price, 4),
        "sma200": round(sma200, 4) if sma200 else None,
        "base_low": round(base_low, 4),
        "base_high": round(base_high, 4),
        "distance_to_base_pct": round(dist_base, 4) if dist_base is not None else None,
        "distance_to_sma200_pct": round(dist_sma, 4) if dist_sma is not None else None,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Step-1 catalyst / negative-force screen (Value_Dip_swing.md §1)
# ---------------------------------------------------------------------------


def fib_retrace_entry(
    closes: list,
    highs: list,
    lows: list,
    window: int = 150,
) -> dict:
    """Fibonacci-retracement dip entry from the recent swing range.

    Uses the trailing ``window`` swing high/low, then reports the nearest
    0.382/0.5/0.618 retracement level to the current price and the
    retracement fraction. ``zone`` is True when price retraced into the
    0.382-0.618 golden zone (classic mean-reversion dip-buy). Returns None
    fields when history is insufficient or the range is flat (no-fabrication).
    """
    if not closes or not highs or not lows or len(closes) < 10:
        return {"near_level": None, "retrace_pct": None, "levels": None, "zone": None}
    seg_h = highs[-window:]
    seg_l = lows[-window:]
    hi = max(float(x) for x in seg_h)
    lo = min(float(x) for x in seg_l)
    if hi <= lo:
        return {"near_level": None, "retrace_pct": None, "levels": None, "zone": None}
    rng = hi - lo
    levels = {
        "0.382": round(hi - 0.382 * rng, 4),
        "0.5": round(hi - 0.5 * rng, 4),
        "0.618": round(hi - 0.618 * rng, 4),
    }
    price = float(closes[-1])
    near = min(levels, key=lambda k: abs(price - levels[k]))
    retrace = (hi - price) / rng
    return {
        "near_level": near,
        "near_price": round(levels[near], 4),
        "retrace_pct": round(retrace, 4),
        "levels": levels,
        "zone": bool(0.382 <= retrace <= 0.618),
    }


def _stochastic_oversold(highs, lows, closes, k_window: int = 14) -> bool | None:
    """bool: Stochastic %K < 20 (oversold); None when history insufficient."""
    from tradingagents.strategies.technical_factors import stochastic_oscillator

    s = stochastic_oscillator(highs, lows, closes, k_window=k_window)
    return s.get("oversold") if s else None


def decline_driver_check(
    *,
    trap_level: str | None = None,
    accrual: float | None = None,
    mom12: float | None = None,
    fcf: float | None = None,
    roe: float | None = None,
    eps_yoy: float | None = None,
) -> dict:
    """Negative-force screen (§1 catalyst check): is the dip a temporary macro/
    headline pullback or structural deterioration?

    Direct "loss of moat / regulatory ban" data is not available from the
    vendors, so this proxies those with the measurable red flags the pipeline
    already computes: trap_risk HIGH (Beneish manipulation / Altman distress),
    Sloan accruals > 6%, deeply negative 12-1m momentum, non-positive FCF,
    non-positive ROE, or a severe EPS YoY decline.

    Verdicts: ``clean`` (healthy dip), ``caution`` (one flag), ``structural``
    (two or more flags / trap HIGH) - a ``structural`` verdict means the
    decline looks company-specific and the value-dip setup should be rejected.
    """
    reasons = []
    if trap_level == "HIGH":
        reasons.append("trap_risk=HIGH (fraud/distress accounting evidence)")
    if accrual is not None and accrual > 0.06:
        reasons.append(f"accruals={accrual:.3f} > 0.06 (earnings quality risk)")
    if mom12 is not None and mom12 < -0.20:
        reasons.append(f"12-1m momentum {mom12:.1%} (structural downtrend)")
    if fcf is not None and fcf <= 0:
        reasons.append("negative free cash flow (business deterioration)")
    if roe is not None and roe <= 0:
        reasons.append(f"non-positive ROE ({roe:.1%})")
    if eps_yoy is not None and eps_yoy < -0.30:
        reasons.append(f"EPS YoY {eps_yoy:.1%} (severe earnings decline)")
    if trap_level == "MEDIUM" and not reasons:
        reasons.append("trap_risk=MEDIUM")
    if not reasons:
        verdict = "clean"
    elif trap_level == "HIGH" or len(reasons) >= 2:
        verdict = "structural"
    else:
        verdict = "caution"
    return {"verdict": verdict, "reasons": reasons, "clean": verdict == "clean"}


def value_dip_setup(
    closes: list,
    highs: list,
    lows: list,
    volumes: list,
    margin_of_safety: float | None = None,
    fcf_yield: float | None = None,
    val_z: float | None = None,
    atr_value: float | None = None,
    min_closes: int = 20,
    debt_to_equity: float | None = None,
    current_ratio: float | None = None,
    roe: float | None = None,
    fcf: float | None = None,
    min_closes_support: int = 200,
    eps: float | None = None,
    book_value_per_share: float | None = None,
    current_assets: float | None = None,
    total_liabilities: float | None = None,
    shares: float | None = None,
    adjusted_ebit: float | None = None,
    tax_rate: float | None = None,
    wacc: float | None = None,
    roic: float | None = None,
) -> dict:
    """The hybrid allocation matrix (§4) as one combined setup gate.

    Rows (all computed, never narrated):

    * **value_floor** - margin of safety >= 20% and/or FCF yield >= 6%
    * **technical_entry** - RSI(14) <= 35 and %b <= 0.10
    * **trade_risk** - atr-based stop distance <= 2 x ATR and the stop
      distance is <= 2% of price (<= 2% account risk proxy)
    * **exit_target** - R:R to the 2.5R target >= 2.5 (always true by
      construction of the R:R target)
    * **balance_sheet** - debt/equity < 1.0 OR current ratio > 1.5
    * **profitability** - positive FCF and ROE > 15% (the Step-1 quality row)
    * **momentum_divergence** - bullish RSI/MACD divergence or higher-low
      (display row; feeds the VDU ladder, never blocks alone)
    * **vdu** - the Step-2 trigger ladder (volume dry-up near support ->\
      trigger candle on RVOL >= 1.3 + higher-low/divergence confirmation)
    * **support** - major weekly / multi-month base support or 200-day SMA
      proximity (display row; 200+ closes required)

    ``candidate`` = the gating rows all pass when measured (unknown rows are
    ignored, never fail): value_floor + technical_entry + trade_risk +
    balance_sheet + profitability. The VDU/divergence/support rows are
    computed and displayed; their dedicated tools (`get_vdu_entry_setup`, etc.)
    expose the full Step-2 ladder as its own candidate.
    """
    if not closes or len(closes) < min_closes or not highs or not lows:
        return {"candidate": False, "reasons": ["no data"], "rows": {}}
    price = float(closes[-1])
    rsi_val = _rsi(closes, 14)
    bb = bollinger_pct_b(closes)
    pct_b = bb.get("pct_b") if bb else None
    a = atr_value if atr_value is not None else _atr(highs, lows, closes, window=14)
    stop_dist = STOP_ATR_MULT * a if a and a > 0 else None
    stop_pct = stop_dist / price if (stop_dist is not None and price > 0) else None

    value_floor = bool(
        (margin_of_safety is not None and margin_of_safety >= MOS_FLOOR)
        or (fcf_yield is not None and fcf_yield >= FCFY_FLOOR)
    )
    technical_entry = bool(
        (rsi_val is not None and rsi_val <= RSI_ENTRY)
        and (pct_b is not None and pct_b <= PCTB_ENTRY)
    )
    trade_risk = bool(stop_pct is not None and stop_pct <= MAX_ACCOUNT_RISK)
    exit_target = True  # 2.5R target is definitionally >= 2.5 R:R

    # Step-1 fundamental rows (unknown inputs never fail a gate).
    bs = balance_sheet_health(debt_to_equity, current_ratio)
    prof = profitability_quality(fcf=fcf, fcf_yield=fcf_yield, roe=roe)
    # Step-2 technical structure rows (computed from the OHLCV already given).
    vdu = vdu_entry_setup(closes, highs, lows, volumes) if volumes else None
    mom = None
    if len(closes) >= 45:
        mom = macd_divergence(closes, lows, window=min(120, len(closes)) // 2)
    support = (
        support_structure(closes, highs, lows, atr_value=a)
        if len(closes) >= min_closes_support
        else None
    )

    reasons = []
    if not value_floor:
        reasons.append("value floor missed (MoS/FCFY below thresholds)")
    if not technical_entry:
        reasons.append("technical entry missed (RSI/%b above thresholds)")
    if not trade_risk:
        reasons.append("trade risk too high (stop > 2% of price)")
    if bs.get("pass") is False:
        reasons.append("balance sheet health missed (D/E >= 1.0 and current ratio <= 1.5)")
    if prof.get("pass") is False:
        reasons.append("profitability missed (FCF not positive or ROE <= 15%)")

    rows = {
        "value_floor": {
            "pass": value_floor,
            "margin_of_safety": (
                round(margin_of_safety, 4) if margin_of_safety is not None else None
            ),
            "fcf_yield": round(fcf_yield, 4) if fcf_yield is not None else None,
            "thresholds": {"mos": MOS_FLOOR, "fcfy": FCFY_FLOOR},
        },
        "technical_entry": {
            "pass": technical_entry,
            "rsi": rsi_val,
            "pct_b": pct_b,
            "thresholds": {"rsi": RSI_ENTRY, "pct_b": PCTB_ENTRY},
        },
        "trade_risk": {
            "pass": trade_risk,
            "atr": round(a, 4) if a else None,
            "stop_mult": STOP_ATR_MULT,
            "stop_pct": round(stop_pct, 4) if stop_pct is not None else None,
            "max_account_risk": MAX_ACCOUNT_RISK,
        },
        "exit_target": {
            "pass": exit_target,
            "rr_target": RR_TARGET,
            "blended_rr": None,  # filled by tranche_plan when an entry exists
        },
        "balance_sheet": bs,
        "profitability": prof,
        "momentum_divergence": mom,
        "vdu": vdu,
        "support": support,
        "fib_retrace": fib_retrace_entry(closes, highs, lows),
        "stochastic": _stochastic_oversold(highs, lows, closes),
    }
    # Fundamental floors (Graham / NCAV / EPV) - the value-dip's structural
    # cheapness floor beyond MoS/FCFY. Computed when the inputs are present;
    # unknown rows never fail the gate (repo convention).
    try:
        from tradingagents.strategies.fundamental_floors import (
            earnings_power_value as _epv,
            epv_per_share as _epv_ps,
            graham_cheap as _g_cheap,
            graham_number as _g,
            ncav_cheap as _n_cheap,
            ncav_per_share as _ncav,
        )

        g_num = _g(eps, book_value_per_share)
        ncav = _ncav(current_assets, total_liabilities, shares)
        epv = _epv(adjusted_ebit, tax_rate, wacc, roic=roic)
        epv_ps = _epv_ps(epv.get("epv"), shares) if epv else None
        rows["graham"] = {
            "number": g_num,
            "cheap": _g_cheap(price, g_num),
        }
        rows["ncav"] = {
            "per_share": ncav,
            "cheap": _n_cheap(price, ncav),
        }
        rows["epv"] = {
            "epv": epv.get("epv") if epv else None,
            "per_share": epv_ps,
            "conclusion": epv.get("conclusion") if epv else None,
        }
    except Exception:  # noqa: BLE001 - floors degrade to n/a
        pass
    # Mean-reversion technicals (StochRSI / RSI2 / W%R / Keltner / Donchian /
    # OBV / PSAR / Elder) - dip-timing + exit confirmation rows.
    try:
        from tradingagents.strategies.technical_factors import (
            donchian_channel as _don,
            elder_thermometer as _elder,
            keltner_channel as _kelt,
            obv_divergence as _obv,
            parabolic_sar as _psar,
            rsi2 as _rsi2,
            stoch_rsi as _srsi,
            williams_r as _wr,
        )

        rows["stoch_rsi"] = _srsi(closes)
        rows["rsi2"] = _rsi2(closes)
        rows["williams_r"] = _wr(highs, lows, closes)
        rows["keltner"] = _kelt(closes, atr_value=a)
        rows["donchian"] = _don(highs, lows)
        rows["obv"] = _obv(closes, volumes)
        rows["psar"] = _psar(highs, lows)
        rows["elder"] = _elder(volumes)
    except Exception:  # noqa: BLE001 - technicals degrade to n/a
        pass
    val_z_row = None
    if val_z is not None:
        val_z_row = {
            "z": round(val_z, 3),
            "verdict": "cheap" if val_z <= Z_CHEAP else ("rich" if val_z >= 1.5 else "fair"),
            "threshold": Z_CHEAP,
        }
        if val_z > Z_CHEAP:
            reasons.append(f"valuation Z={val_z:.2f} not below {Z_CHEAP:.1f}")
    rows["valuation"] = val_z_row
    # Candidate: the gating rows must all pass when measured; unknown rows
    # (no data) are ignored, matching the repo's scan convention.
    measured_gates = [
        value_floor,
        technical_entry,
        trade_risk,
    ]
    if bs.get("pass") is not None:
        measured_gates.append(bs["pass"])
    if prof.get("pass") is not None:
        measured_gates.append(prof["pass"])
    return {
        "candidate": bool(all(measured_gates)),
        "reasons": reasons,
        "rows": rows,
        "price": round(price, 4),
    }
