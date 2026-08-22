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
) -> dict:
    """The hybrid allocation matrix (§4) as one combined setup gate.

    Rows (all computed, never narrated):

    * **value_floor** - margin of safety >= 20% and/or FCF yield >= 6%
    * **technical_entry** - RSI(14) <= 35 and %b <= 0.10
    * **trade_risk** - atr-based stop distance <= 2 x ATR and the stop
      distance is <= 2% of price (<= 2% account risk proxy)
    * **exit_target** - R:R to the 2.5R target >= 2.5 (always true by
      construction of the R:R target)

    ``candidate`` = value_floor + technical_entry + trade_risk all pass
    (exit_target is definitionally true, kept for the audit trail). Each row
    carries its computed numbers; a missing input renders the row unknown
    (ignored, not failed) - the same convention as the swing/VCP scans.
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

    reasons = []
    if not value_floor:
        reasons.append("value floor missed (MoS/FCFY below thresholds)")
    if not technical_entry:
        reasons.append("technical entry missed (RSI/%b above thresholds)")
    if not trade_risk:
        reasons.append("trade risk too high (stop > 2% of price)")

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
    }
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
    return {
        "candidate": bool(value_floor and technical_entry and trade_risk),
        "reasons": reasons,
        "rows": rows,
        "price": round(price, 4),
    }
