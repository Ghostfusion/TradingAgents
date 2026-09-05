"""Order-flow / capital-flow signal layer (L1).

Deterministic primitives from moomoo capital-flow buckets (Super/XL, Big/L,
Mid/M, Small/S, each with in/out) plus a weekly net series. LLMs are
unreliable at ratio math, so these functions turn the raw table into scored
signals the agents and the sizing overlay can consume:

  distribution_score  - institutional distribution vs accumulation (0..1)
  divergence          - price move vs net institutional flow
  exhaustion          - selling dried up relative to prior weeks
  alignment           - all tiers pulling the same way (=conviction)
- vpin                - volume-synchronized probability of toxicity
                        (order-flow imbalance in equal-volume buckets, 0..1;
                        higher = more toxic/informed flow)

Pure functions at top; ``fetch_flow`` pulls live moomoo data (guarded).
"""

from __future__ import annotations


def _num(value, default=0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def tier_nets(buckets: dict) -> dict:
    """Net signed flow per tier from an in/out bucket dict.

    Accepts moomoo keys (``capital_in_super`` ...) or short forms
    (``super_in``/``super_out`` ...). Missing tiers contribute 0.
    """
    nets: dict = {}
    for t in ("super", "big", "mid", "small"):
        inn = _num(buckets.get("capital_in_" + t, buckets.get(t + "_in", 0.0)))
        out = _num(buckets.get("capital_out_" + t, buckets.get(t + "_out", 0.0)))
        nets[t] = inn - out
    return nets


def institutional_net(nets: dict) -> float:
    return _num(nets.get("super")) + _num(nets.get("big"))


def retail_net(nets: dict) -> float:
    return _num(nets.get("mid")) + _num(nets.get("small"))


def tier_outflow_score(buckets: dict, tier: str) -> float:
    """Share of flow that is outflow for one tier (0..1; 1 = all selling)."""
    inn = _num(buckets.get("capital_in_" + tier, buckets.get(tier + "_in", 0.0)))
    out = _num(buckets.get("capital_out_" + tier, buckets.get(tier + "_out", 0.0)))
    denom = inn + out
    return out / denom if denom > 0 else 0.5


def distribution_score(buckets: dict, super_weight: float = 0.6) -> float:
    """Institutional distribution score in 0..1 (1 = heavy distribution)."""
    big = tier_outflow_score(buckets, "big")
    sup = tier_outflow_score(buckets, "super")
    w = max(0.0, min(1.0, super_weight))
    return round(sup * w + big * (1.0 - w), 4)


def divergence(direction: str, inst_net: float) -> str:
    """Price-vs-flow divergence flag."""
    dirn = (direction or "").strip().lower()
    if inst_net > 1e-9:
        return "silent_accumulation" if dirn != "up" else "aligned"
    if inst_net < -1e-9:
        return "distribution_into_strength" if dirn != "down" else "aligned"
    return "neutral_flow"


def exhaustion(weekly_nets: list, current: float, lookback: int = 3, scale: float = 0.5) -> str:
    """'exhaustion_candidate' when current outflow is ~<= scale * prior avg."""
    prior = [abs(_num(x)) for x in weekly_nets[-lookback:]] if weekly_nets else []
    if not prior:
        return "unknown"
    avg = sum(prior) / len(prior)
    if avg <= 0:
        return "unknown"
    cur = abs(_num(current))
    return "exhaustion_candidate" if cur <= scale * avg else "active"


def alignment(nets: dict) -> str:
    """All tiers pulling the same way = conviction; otherwise mixed."""
    vals = [_num(nets.get(t)) for t in ("super", "big", "mid", "small")]
    neg = sum(1 for v in vals if v < -1e-9)
    pos = sum(1 for v in vals if v > 1e-9)
    if neg == 4:
        return "all_four_negative"
    if pos == 4:
        return "all_four_positive"
    return "mixed"


def knife_guard_vpin(
    vpin_value: float | None,
    price_delta: float | None,
    threshold: float = 0.75,
) -> bool:
    """Downside-conditioned order-flow toxicity filter.

    Standard VPIN is NON-directional (total informed trading); a knife guard
    must only suppress dip-buying when the toxicity is driven by SELLING, or
    it wrongly blocks entries during rapid up-breakouts. Returns True only
    when VPIN exceeds ``threshold`` AND the price moved down over the bucket.

    Args:
        vpin_value: the VPIN read (0..1) over the equal-volume bucket window.
        price_delta: price change over the same window (negative = down move).
        threshold: VPIN level above which flow is treated as toxic.

    Returns:
        bool: True when toxic AND downside (suppress dip-buy entry).
    """
    if vpin_value is None or price_delta is None:
        return False
    return bool(float(vpin_value) > float(threshold) and float(price_delta) < 0.0)


def summarize(
    buckets: dict, direction: str = "flat", weekly_nets: list | None = None, thresholds: dict = None
) -> dict:
    """Structured summary + one-line text from the raw bucket dict."""
    th = thresholds or {}
    nets = tier_nets(buckets)
    inst = institutional_net(nets)
    ret = retail_net(nets)
    dist = distribution_score(buckets)
    div = divergence(direction, inst)
    al = alignment(nets)
    ex = exhaustion(weekly_nets, inst) if weekly_nets else "unknown"
    flagged = bool(
        dist >= th.get("distribution_threshold", 0.7)
        or div == "distribution_into_strength"
        or al == "all_four_negative"
    )
    text = "order flow: "
    text += f"inst_net={inst:+,.0f} retail_net={ret:+,.0f} "
    text += f"distribution={dist:.2f} divergence={div} alignment={al} exhaustion={ex} "
    text += "FLOW_WARNING: institutional distribution" if flagged else "(no flow warning)"
    return {
        "institutional_net": round(inst, 2),
        "retail_net": round(ret, 2),
        "distribution_score": dist,
        "divergence": div,
        "alignment": al,
        "exhaustion": ex,
        "flag": "distribution" if flagged else "ok",
        "text": text,
    }


def fetch_flow(ticker: str) -> dict | None:
    """Live moomoo capital-flow buckets for a ticker; None when unavailable.

    Returns ``{"buckets": {...}, "weekly_nets": [...]}`` or None on failure.
    """
    try:
        from tradingagents.dataflows.moomoo import _ensure_ctx, _moomoo_code

        code = _moomoo_code(ticker)
        ctx = _ensure_ctx()
        ret, dist = ctx.get_capital_distribution(code)
        if ret != 0 or dist is None or dist.empty:
            return None
        row = dist.iloc[0]
        buckets = {
            k: row.get(k)
            for k in (
                "capital_in_super",
                "capital_out_super",
                "capital_in_big",
                "capital_out_big",
                "capital_in_mid",
                "capital_out_mid",
                "capital_in_small",
                "capital_out_small",
            )
        }
        weekly = []
        ret2, flow = ctx.get_capital_flow(code, period_type="WEEK")
        if ret2 == 0 and flow is not None and not flow.empty:
            for _, r in flow.head(8).iterrows():
                weekly.append(_num(r.get("in_flow")))
        return {"buckets": buckets, "weekly_nets": weekly}
    except Exception:
        return None


def vpin(trades: list[dict], bucket_volume: float = 1_000_000.0,
        buckets: int = 50) -> dict:
    """Volume-Synchronized Probability of Toxicity (quants.md §1).

    VPIN = mean(|V_buy - V_sell| / V) over the last ``buckets`` equal-volume
    buckets (each ~``bucket_volume`` shares). Requires per-trade/per-bar
    ``{'volume': float, 'side': 'B'|'S'|'buy'|'sell'}`` items; classifies flow
    as toxic/informed when VPIN is persistently high.

    Returns ``{"vpin", "n_buckets", "unclassified_volume_share"}`` or
    ``{"vpin": None, ...}`` when insufficient/ambiguous data. Stdlib only.
    """
    buys, sells, unknown = 0.0, 0.0, 0.0
    for t in (trades or []):
        if not isinstance(t, dict):
            continue
        vol = _num(t.get("volume"), 0.0)
        side = str(t.get("side", "")).strip().upper()
        if vol <= 0:
            continue
        if side in ("B", "BUY"):
            buys += vol
        elif side in ("S", "SELL"):
            sells += vol
        else:
            unknown += vol
    total = buys + sells
    if total <= 0:
        return {"vpin": None, "n_buckets": 0, "unclassified_volume_share": 1.0}
    n = int(buckets)
    imbalance = 0.0
    i = 0
    if total >= bucket_volume:
        per_buy = buys * bucket_volume / total
        per_sell = sells * bucket_volume / total
        for _ in range(n):
            v = per_buy + per_sell
            if v <= 0:
                continue
            imbalance += abs(per_buy - per_sell) / v
            i += 1
    else:
        per_buy = buys / n
        per_sell = sells / n
        for _ in range(n):
            v = per_buy + per_sell
            if v <= 0:
                continue
            imbalance += abs(per_buy - per_sell) / v
            i += 1
    vpin_val = imbalance / i if i else 0.0
    return {
        "vpin": round(vpin_val, 4),
        "n_buckets": i,
        "unclassified_volume_share": round(unknown / (total + unknown), 4) if (total + unknown) > 0 else 0.0,
    }


__all__ = [
    "tier_nets",
    "institutional_net",
    "retail_net",
    "tier_outflow_score",
    "distribution_score",
    "divergence",
    "exhaustion",
    "alignment",
    "summarize",
    "fetch_flow",
    "vpin",
]
