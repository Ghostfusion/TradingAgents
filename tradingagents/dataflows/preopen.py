"""P1/P2/P3 - pre-open market data + execution-quality helpers (advisory).

Implements the measurable slices of the institutional extended-hours workflow
with the tiers this machine actually has (Alpaca free IEX for pre-market bars
+ live quote depth; existing vendors for the rest). Everything here is a PURE
read over data -> advisory numbers, default-ONLY-injected (never blocks).

Key primitives:

* ``premarket_rvol`` - the text's "RVOL > 2.0x vs 30-day pre-market run rate":
  today's pre-open volume / the 30-day average pre-open volume (Alpaca 15-min
  bars pre 09:30 ET). None (unavailable) when Alpaca is disabled or data is
  missing - never fabricated.
* ``preopen_gap`` - the gap anchored to the LIVE pre-open price (Alpaca latest
  quote/trade) instead of the previous close, so a gap that formed overnight
  is measured at pre-open, not at yesterday's close.
* ``preopen_book_depth`` - live IEX bid/ask depth read (free stand-in for the
  NOII opening-imbalance signal): spread vs 30d avg, bid/ask size imbalance,
  thin-book warning. Explicitly weaker than true NOII (plan-gated).
* ``postfill_drift`` - C3 alpha-profile: N-day drift after a paper fill vs the
  arrival price - the "did our fill leak / did price move against us" test,
  computed over the paper ledger's own prices (no new vendor).

All functions return dicts with explicit 'unavailable' on missing data.
"""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta, timezone

#: pre-market window end = 09:30 ET. Alpaca timestamps are UTC Z; convert.
PREOPEN_START = dtime(4, 0)  # 04:00 ET
REGULAR_OPEN = dtime(9, 30)  # 09:30 ET


def _et_now() -> datetime:
    """Current time in ET (naive). Alpaca clock is UTC; convert with the -4/-5 offset."""
    utc = datetime.now(timezone.utc)
    # US Eastern: EDT (-4) roughly Apr-Oct, EST (-5) otherwise (DST approx)

    try:
        from zoneinfo import ZoneInfo

        return utc.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
    except Exception:  # noqa: BLE001 - fixed-offset fallback
        return utc.replace(tzinfo=None) - timedelta(hours=4)


def _to_et(dt_utc: datetime) -> datetime:
    """Convert a UTC-aware datetime to naive ET (04:00-09:30 window compares)."""
    try:
        from zoneinfo import ZoneInfo

        return dt_utc.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
    except Exception:  # noqa: BLE001 - fixed-offset fallback (EST/EDT approx -4)
        return (dt_utc.replace(tzinfo=None) - timedelta(hours=4))


def _is_premarket(dt_utc: datetime) -> bool:
    """True when a UTC timestamp falls in the 04:00-09:30 ET pre-open window."""
    et = _to_et(dt_utc)
    return PREOPEN_START <= et.time() < REGULAR_OPEN


def premarket_rvol(
    symbol: str,
    today_volume: float | None = None,
    bars: list | None = None,
) -> dict:
    """Pre-market relative volume: today's pre-open volume / 30-day avg.

    ``bars``: optional Alpaca 15-min bars (UTC) covering pre-open windows so
    callers can pass a cached series. When omitted, fetches from Alpaca.
    Returns None-valued dict (unavailable) when Alpaca is disabled / data
    missing - never fabricated.
    """
    from tradingagents.dataflows.alpaca_common import alpaca_credentials, alpaca_get

    kid, sec = alpaca_credentials()
    if not kid or not sec:
        return {"rvol": None, "today_vol": None, "avg_vol": None,
                "window_days": 30, "reason": "alpaca not configured"}
    if bars is None:
        # Fetch ~40 calendar days of 15-min bars in one call (paced client).
        start = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%dT04:00:00Z")
        end = datetime.now(timezone.utc).strftime("%Y-%m-%dT13:30:00Z")
        data = alpaca_get(
            f"stocks/{symbol}/bars",
            {"timeframe": "15Min", "start": start, "end": end, "limit": 3000},
        )
        bars = (data or {}).get("bars") if isinstance(data, dict) else None
    if not bars:
        return {"rvol": None, "today_vol": None, "avg_vol": None,
                "window_days": 30, "reason": "no alpaca bars"}
    # group by session date (UTC -> ET date of the *open*)
    from collections import defaultdict

    days: dict[str, float] = defaultdict(float)
    for b in bars:
        ts = b.get("t", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        # only pre-open bars
        if not _is_premarket(dt):
            continue
        day_key = _to_et(dt).date().isoformat()
        days[day_key] += float(b.get("v", 0) or 0)
    if not days:
        return {"rvol": None, "today_vol": None, "avg_vol": None,
                "window_days": 30, "reason": "no pre-open bars"}
    ordered = [v for _, v in sorted(days.items())]
    today_vol = today_volume if today_volume is not None else ordered[-1]
    avg = sum(ordered[:-1]) / (len(ordered) - 1) if len(ordered) > 1 else None
    if not avg or avg <= 0:
        return {"rvol": None, "today_vol": today_vol, "avg_vol": None,
                "window_days": len(ordered), "reason": "no prior pre-open history"}
    rvol = today_vol / avg
    return {
        "rvol": round(rvol, 2),
        "today_vol": today_vol,
        "avg_vol": round(avg, 1),
        "window_days": len(ordered) - 1,
        "reason": "ok",
    }


def preopen_gap(
    symbol: str,
    prev_close: float | None = None,
    latest_trade: float | None = None,
) -> dict:
    """Gap anchored to the LIVE pre-open price (Alpaca latest trade), not the
    close. ``gap_pct = (preopen - prev_close)/prev_close``; None when data
    missing.
    """
    from tradingagents.dataflows.alpaca_common import alpaca_credentials, alpaca_get

    if latest_trade is None:
        kid, sec = alpaca_credentials()
        if not kid or not sec:
            return {"gap_pct": None, "preopen_price": None, "reason": "alpaca not configured"}
        data = alpaca_get("stocks/trades/latest", {"symbols": symbol, "feed": "iex"})
        latest_trade = ((data or {}).get("trades") or {}).get(symbol, {}).get("p") if isinstance(data, dict) else None
    if prev_close is None or latest_trade is None or prev_close <= 0:
        return {"gap_pct": None, "preopen_price": latest_trade,
                "prev_close": prev_close, "reason": "missing price inputs"}
    gap = (float(latest_trade) - float(prev_close)) / float(prev_close)
    return {
        "gap_pct": round(gap, 6),
        "preopen_price": float(latest_trade),
        "prev_close": float(prev_close),
        "reason": "ok",
    }


def preopen_book_depth(
    symbol: str,
    avg_spread_bps: float | None = None,
    quote: dict | None = None,
) -> dict:
    """Live IEX quote-depth read (free stand-in for NOII opening imbalance).

    ``quote``: optional pre-fetched latest-quote dict (``{ap, as, bp, bs}``).
    Computes spread_bps, bid/ask size imbalance and a thin-book warning.
    Weak than true NOII - documented as a free-tier proxy.
    """
    from tradingagents.dataflows.alpaca_common import alpaca_credentials, alpaca_get

    if quote is None:
        kid, sec = alpaca_credentials()
        if not kid or not sec:
            return {"spread_bps": None, "bid_ask_imbalance": None, "thin": None,
                    "reason": "alpaca not configured"}
        data = alpaca_get("stocks/quotes/latest", {"symbols": symbol, "feed": "iex"})
        quote = ((data or {}).get("quotes") or {}).get(symbol) if isinstance(data, dict) else None
    if not quote:
        return {"spread_bps": None, "bid_ask_imbalance": None, "thin": None,
                "reason": "no quote"}
    ap, as_ = quote.get("ap"), quote.get("as")
    bp, bs = quote.get("bp"), quote.get("bs")
    spread_bps = None
    mid = None
    if ap and bp and ap > 0 and bp > 0:
        mid = (float(ap) + float(bp)) / 2.0
        spread_bps = round((float(ap) - float(bp)) / mid * 1e4, 2) if mid else None
    biz = None
    if bs is not None and as_ is not None and (bs + as_) > 0:
        biz = round((float(bs) - float(as_)) / (float(bs) + float(as_)), 3)  # + = bid-heavy
    thin = None
    if bs is not None and as_ is not None:
        min_side = min(float(bs), float(as_))
        thin = bool(min_side < 1000)  # sub-1k shares on either side = thin
    return {
        "spread_bps": spread_bps,
        "mid": round(mid, 4) if mid else None,
        "bid_ask_imbalance": biz,
        "bid_size": bs,
        "ask_size": as_,
        "thin": thin,
        "reason": "ok",
    }


def postfill_drift(
    arrival_price: float,
    current_price: float,
    days_held: int = 1,
) -> dict:
    """C3 alpha-profile: post-fill drift vs arrival after N days.

    Positive = price moved IN OUR FAVOR post-fill (good/benign execution);
    negative = adverse drift (possible leak / our fill was the top tick).
    Pure; no vendor. None when prices missing.
    """
    if not arrival_price or not current_price or float(arrival_price) <= 0:
        return {"drift_pct": None, "days_held": days_held, "reason": "missing prices"}
    drift = (float(current_price) - float(arrival_price)) / float(arrival_price)
    return {"drift_pct": round(drift, 6), "days_held": days_held, "reason": "ok"}


__all__ = [
    "premarket_rvol",
    "preopen_gap",
    "preopen_book_depth",
    "postfill_drift",
]
