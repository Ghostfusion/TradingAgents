"""G1 - deterministic position & stop contract.

The LLM argues the thesis; this computes the number. Size = min over
independent budgets (Kelly, risk-per-trade) scaled by volatility targeting,
order-flow distribution and agreement - all clamped to config caps and
returned with an audit trail of which budget bound it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class PositionContract:
    size_pct: float
    stop_loss: float | None
    stop_pct: float
    reason_parts: list[str] = field(default_factory=list)
    breakeven_stop: float | None = None
    target: float | None = None
    exit_note: str | None = None

    def reason(self) -> str:
        return "; ".join(self.reason_parts) if self.reason_parts else "no budget bound"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _log_returns(closes) -> list:
    rets = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            rets.append(math.log(closes[i] / closes[i - 1]))
    return rets


def _atr_or_proxy(closes, high, low, window: int = 14) -> float:
    """ATR from H/L when present; else a close-to-close range proxy."""
    ok = (
        high is not None
        and low is not None
        and len(high) == len(closes)
        and len(low) == len(closes)
    )
    if ok:
        from tradingagents.strategies.size import atr

        a = atr(high, low, closes, window=window)
        if a > 0:
            return a
    sample = closes[-window:] if len(closes) > window else closes
    rets = _log_returns(sample)
    if not rets:
        return 0.0
    avg = sum(abs(r) for r in rets) / len(rets)
    return avg * closes[-1]


def build_position_contract(
    decision=None,
    cfg=None,
    closes=None,
    high=None,
    low=None,
    flow_summary=None,
    agreement: float | None = None,
    calibrated_p: float | None = None,
    catalyst_scale: float | None = None,
    entry_price: float | None = None,
    trail_stop: float | None = None,
    implied_move_pct: float | None = None,
    knife_factor: float = 1.0,
    regime_factor: float = 1.0,
    vol_cap_factor: float = 1.0,
) -> PositionContract | None:
    """Compute the authoritative size + stop from config budgets.

    cfg keys: risk_per_trade (default 0.01), max_position_pct (0.30),
    atr_mult (2.0), target_vol (0.15), position_odds (1.0), kelly_fraction
    (0.25). Returns None when no usable close prices are provided.

    ``entry_price`` (optional): the reference entry for the stop/risk. When
    set (e.g. a tranche plan's weighted average entry), dollar stop/risk
    levels are measured from it instead of the last close so the G1 contract
    matches the tranche execution. Position sizing stays a fraction of the
    book and is unchanged; None keeps the last-close behaviour.

    ``trail_stop`` (optional): a chandelier/ATR trailing stop level. When
    given, the contract's stop is the tighter of the ATR stop and the trail
    (a trailing stop below the ATR stop is the live exit).

    ``implied_move_pct`` (optional): the option-implied single-day move (e.g.
    from the earnings straddle). When set, the position is scaled down by
    (1 - implied_move_pct) so a binary event can't blow the risk budget.
    """
    if not closes:
        return None
    cfg = cfg or {}
    risk = float(cfg.get("risk_per_trade", 0.01))
    max_pct = float(cfg.get("max_position_pct", 0.30))
    atr_mult = float(cfg.get("atr_mult", 2.0))
    target_vol = float(cfg.get("target_vol", 0.15))
    odds = float(cfg.get("position_odds", 1.0))
    kelly_frac = float(cfg.get("kelly_fraction", 0.25))

    closes_f = [float(c) for c in closes]
    last = closes_f[-1]
    if last <= 0:
        return None

    from tradingagents.strategies.size import position_size_kelly, volatility_target_scale

    a = _atr_or_proxy(closes_f, high, low)
    stop_pct = _clamp(atr_mult * a / last if a > 0 else 0.02, 0.005, 0.50)

    # Reference entry for the dollar stop: the weighted tranche entry when a
    # tranche plan is in play, else the last close (unchanged behaviour).
    entry = entry_price if (entry_price is not None and float(entry_price) > 0) else last
    stop = float(entry) * (1.0 - stop_pct)
    # Chandelier/ATR trailing stop: when given and tighter than the ATR stop,
    # the live exit is the trail (a trailing stop below the ATR stop is the
    # active exit level).
    if trail_stop is not None:
        try:
            trail = float(trail_stop)
            if trail > 0 and trail > stop:
                stop = trail
                reasons_extra = [f"trail_stop={trail:.2f}"]
            else:
                reasons_extra = []
        except (TypeError, ValueError):
            reasons_extra = []
    else:
        reasons_extra = []

    p = calibrated_p if calibrated_p is not None else 0.5
    kelly_part = position_size_kelly(p, odds=odds, fraction=kelly_frac, max_size=max_pct)
    risk_part = risk / stop_pct if stop_pct > 0 else max_pct
    size_base = min(kelly_part, risk_part)
    reasons = [f"kelly={kelly_part:.3f}", f"risk/stop={risk_part:.3f}"]

    rets = _log_returns(closes_f)
    vol_s = 1.0
    if len(rets) >= 6:
        v = volatility_target_scale(rets, target_vol=target_vol)
        vol_s = 1.0 if v <= 0 else _clamp(v, 0.2, 1.5)
    reasons.append(f"vol_scale={vol_s:.2f}")

    flow_s = 1.0
    dist = (flow_summary or {}).get("distribution_score")
    if dist is not None:
        flow_s = _clamp(1.0 - float(dist), 0.0, 1.0)
        reasons.append(f"flow_scale={flow_s:.2f}")

    agree = float(agreement if agreement is not None else 1.0)
    agree = _clamp(agree, 0.0, 1.0)
    if agree < 1.0:
        reasons.append(f"agreement={agree:.2f}")

    cat_s = 1.0
    if catalyst_scale is not None:
        cat_s = _clamp(float(catalyst_scale), 0.0, 1.0)
        if cat_s < 1.0:
            reasons.append(f"catalyst_scale={cat_s:.2f}")

    kf = 1.0
    if knife_factor is not None:
        try:
            kf = _clamp(float(knife_factor), 0.0, 1.0)
        except (TypeError, ValueError):
            kf = 1.0
    if kf < 1.0:
        reasons.append(f"knife_scale={kf:.2f}")

    rf = 1.0
    if regime_factor is not None:
        try:
            rf = _clamp(float(regime_factor), 0.0, 1.0)
        except (TypeError, ValueError):
            rf = 1.0
    if rf < 1.0:
        reasons.append(f"regime_scale={rf:.2f}")

    vcf = 1.0
    if vol_cap_factor is not None:
        try:
            vcf = _clamp(float(vol_cap_factor), 0.0, 1.0)
        except (TypeError, ValueError):
            vcf = 1.0
    if vcf < 1.0:
        reasons.append(f"vol_cap_scale={vcf:.2f}")

    sized = min(size_base * vol_s * flow_s * agree * cat_s * kf * rf * vcf, max_pct)
    # Implied-move scaling: a binary event (earnings straddle) widens the
    # single-day gap; scale the position down by (1 - implied_move_pct) so the
    # event can't blow the risk budget.
    if implied_move_pct is not None:
        try:
            im = float(implied_move_pct)
            if 0 < im < 1:
                sized *= (1.0 - im)
                reasons.append(f"implied_move={im:.1%}")
        except (TypeError, ValueError):
            pass
    be_stop = None
    target = None
    if cfg.get("enable_exits") and a > 0:
        from tradingagents.strategies.exits import (
            stop_to_breakeven,
            target_level,
        )

        be_stop = stop_to_breakeven(entry, a, cushion_atr=float(cfg.get("breakeven_atr", 1.0)))
        target = target_level(entry, a, atr_mult=float(cfg.get("target_atr", 4.0)))
    note = None
    if be_stop is not None:
        note = f"exits: BE @ {be_stop:.2f}, target @ {target:.2f}"
    return PositionContract(
        size_pct=round(_clamp(sized, 0.0, max_pct), 4),
        stop_loss=round(stop, 4),
        stop_pct=round(stop_pct, 4),
        reason_parts=reasons + reasons_extra + (["tranche weighted entry"] if entry is not last else []),
        breakeven_stop=round(be_stop, 4) if be_stop is not None else None,
        target=round(target, 4) if target is not None else None,
        exit_note=note,
    )


__all__ = ["PositionContract", "build_position_contract"]
