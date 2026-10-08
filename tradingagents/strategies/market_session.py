"""Market-session mechanics: pre-market / open / close reads (pure, offline).

Complements ``pre_market.py`` (the CONFIRM / REVISE / REJECT decision
arbiter) with the *session mechanics* the reviewer and the analyst LLMs can
ground claims in:

  opening_range          - first-N-minute high/low + ORB breakout read
  gap_type               - common / breakaway / runaway / exhaustion + fill stats
  order_imbalance        - buy-heavy / sell-heavy / balanced from flow nets
  premarket_liquidity    - thin-book warning from pre-market volume vs average
  post_close_confirmation- did the close confirm the plan (vs stop/target)?
  forming_bar_progress   - the elapsed share of the regular session, so a
                           partial bar's volume can be annualised instead of
                           read as a light day

Every function is pure and returns None on missing/invalid input (the
no-fabrication rule). No network, no state: ``forming_bar_progress`` reads the
run clock the graph publishes (``dataflows.date_window``) and is 1.0 - no
adjustment - whenever none was published, which is every offline call and every
historical run.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime

#: The regular US equity session, in exchange-time (ET) minutes: 09:30 to 16:00,
#: i.e. 390 minutes. ``_session_progress`` is the one definition of how far into
#: that window an instant sits.
SESSION_OPEN_MINUTE = 9 * 60 + 30
SESSION_MINUTES = 390

#: Below this fraction of the session elapsed, a forming bar's volume carries
#: too little of the day to annualise - the ratio is UNMEASURED (None), never a
#: wild number. 0.10 is roughly the first 39 minutes.
MIN_SESSION_PROGRESS = 0.10


def _session_progress(now: datetime) -> dict:
    """How far through the regular session ``now`` sits - the one session read.

    ``now`` is the run's wall-clock instant in exchange time (a naive value is
    read as ET; a weekend is not a session). Returns ``{fraction,
    minutes_elapsed, open, label}`` where ``fraction`` is 0.0 before the open,
    the elapsed share of the 390-minute session while it is open, and 1.0 from
    the close on - so a reader that annualises a partial bar by it is a no-op
    outside a live session.
    """
    if now.weekday() >= 5:
        return {"fraction": 1.0, "minutes_elapsed": 0, "open": False, "label": "weekend"}
    elapsed = now.hour * 60 + now.minute - SESSION_OPEN_MINUTE
    if elapsed < 0:
        return {"fraction": 0.0, "minutes_elapsed": 0, "open": False, "label": "pre"}
    if elapsed >= SESSION_MINUTES:
        return {
            "fraction": 1.0,
            "minutes_elapsed": SESSION_MINUTES,
            "open": False,
            "label": "post",
        }
    return {
        "fraction": round(elapsed / SESSION_MINUTES, 4),
        "minutes_elapsed": elapsed,
        "open": True,
        "label": "regular",
    }


def forming_bar_progress() -> float:
    """The session fraction to annualise a FORMING bar's volume by.

    Returns 1.0 - no adjustment - unless this process published a run clock
    (:func:`tradingagents.dataflows.date_window.get_run_clock`) AND that instant
    sits inside a live regular session. The unset default is deliberate: an
    offline call, a test or a historical run must read exactly as it did before
    the clock existed, never adjusted by the time of day the process ran at.
    """
    from tradingagents.dataflows.date_window import get_run_clock

    now = get_run_clock()
    if now is None:
        return 1.0
    fraction = _session_progress(now)["fraction"]
    return fraction if 0.0 < fraction < 1.0 else 1.0


def book_depth_read(
    bid: float | None,
    ask: float | None,
    bid_size: float | None,
    ask_size: float | None,
) -> dict:
    """Microprice + order-book imbalance (cookbook recipe 2 execution).

    microprice = (bid*ask_size + ask*bid_size) / (bid_size + ask_size) — the
    size-weighted fair value that shifts toward the thinner side of the book;
    OBI = (bid_size - ask_size) / (bid_size + ask_size) — signed depth
    asymmetry (+1 = heavy bid, -1 = heavy ask). Short-horizon price-pressure
    signal for the pre-market / thin-book path. None when any input is missing
    or the sizes don't sum positive (never fabricates a depth).
    """
    if bid is None or ask is None or bid_size is None or ask_size is None:
        return {"microprice": None, "obi": None, "verdict": None}
    try:
        b = float(bid)
        a = float(ask)
        bs = float(bid_size)
        as_ = float(ask_size)
    except (TypeError, ValueError):
        return {"microprice": None, "obi": None, "verdict": None}
    if b <= 0 or a <= 0 or bs < 0 or as_ < 0 or (bs + as_) <= 0:
        return {"microprice": None, "obi": None, "verdict": None}
    micro = (b * as_ + a * bs) / (bs + as_)
    obi = (bs - as_) / (bs + as_)
    if obi > 0.2:
        verdict = "bid-heavy"
    elif obi < -0.2:
        verdict = "ask-heavy"
    else:
        verdict = "balanced"
    return {"microprice": round(micro, 4), "obi": round(obi, 4), "verdict": verdict}


__all__ = [
    "opening_range",
    "gap_fill_sample",
    "classify_gap",
    "gap_type",
    "order_imbalance",
    "premarket_liquidity",
    "post_close_confirmation",
    "book_depth_read",
    "decompose_returns",
    "decompose_returns_text",
    "forming_bar_progress",
]


def opening_range(highs, lows, closes=None, n_minutes: int = 15) -> dict:
    """Opening range: the high/low of the first ``n_minutes`` of trading.

    Returns ``{or_high, or_low, mid, breakout, stop, target}`` where
    ``breakout`` is 'up' / 'down' / None (latest close vs the range),
    ``stop`` is below the range low (long) or above the range high (short),
    and ``target`` is a 2R multiple of the range width. ``closes`` is
    optional; without it the latest high is used as the breakout proxy.
    None when insufficient bars.
    """
    if not highs or not lows or len(highs) < 2 or len(lows) < 2:
        return {
            "or_high": None, "or_low": None, "mid": None,
            "breakout": None, "stop": None, "target": None,
        }
    try:
        seg_h = [float(x) for x in highs[:n_minutes]]
        seg_l = [float(x) for x in lows[:n_minutes]]
        or_high = max(seg_h)
        or_low = min(seg_l)
        mid = (or_high + or_low) / 2.0
        last = float(closes[-1]) if closes else (float(highs[-1]) if highs else None)
        if last is None:
            return {
                "or_high": round(or_high, 4), "or_low": round(or_low, 4),
                "mid": round(mid, 4), "breakout": None, "stop": None, "target": None,
            }
        width = or_high - or_low
        if width <= 0:
            return {
                "or_high": round(or_high, 4), "or_low": round(or_low, 4),
                "mid": round(mid, 4), "breakout": None, "stop": None, "target": None,
            }
        if last > or_high:
            breakout = "up"
            stop = or_low
        elif last < or_low:
            breakout = "down"
            stop = or_high
        else:
            breakout = None
            stop = or_low  # default long-side stop
        # A 2R target only makes sense for a real ORB breakout. A flat close
        # inside the range got `stop = or_low` (long-side) — emitting the
        # short-side target (`or_low - 2*width`, BELOW the stop) was incoherent.
        target = None
        if breakout == "up":
            target = or_high + 2.0 * width
        elif breakout == "down":
            target = or_low - 2.0 * width
        return {
            "or_high": round(or_high, 4),
            "or_low": round(or_low, 4),
            "mid": round(mid, 4),
            "breakout": breakout,
            "stop": round(stop, 4),
            "target": round(target, 4) if target is not None else None,
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return {
            "or_high": None, "or_low": None, "mid": None,
            "breakout": None, "stop": None, "target": None,
        }


#: How long a gap is given to fill (bars). A gap "fills" when price trades
#: back through the prior close.
GAP_FILL_HORIZON = 10

#: Minimum same-class historical gaps before the fill statistics are reported
#: as measured. Below this the lookup heuristic is used and *labelled* as such.
GAP_FILL_MIN_SAMPLE = 8

#: Heuristic fill stats per gap class, used only when the history is too thin
#: to measure. These were previously the ONLY values, printed as if measured.
_GAP_HEURISTIC: dict[str, tuple[float, int]] = {
    "breakaway": (0.3, 5),
    "exhaustion": (0.6, 3),
    "runaway": (0.4, 4),
    "common": (0.8, 2),
}


def classify_gap(abs_gap: float, vol_ratio: float | None) -> str:
    """Gap class from size + volume, the one rule both the live bar and the
    historical sample are classified with."""
    if vol_ratio is not None and vol_ratio >= 2.0 and abs_gap >= 0.02:
        return "breakaway"
    if abs_gap >= 0.05:
        return "exhaustion"
    if abs_gap >= 0.02:
        return "runaway"
    return "common"


def gap_fill_sample(
    closes, opens, highs, lows, volumes, *, n: int = 20, horizon: int = GAP_FILL_HORIZON
) -> dict:
    """Per-class gap-fill outcome sample over the whole supplied history.

    The stored-sample producer behind :func:`gap_type` (RISK-3 / RISK-8): walks
    every bar of the history the caller passes - normally the repo's stored
    OHLCV - classifies each overnight gap with :func:`classify_gap`, and asks
    whether price traded back through the prior close within ``horizon`` bars.
    The most recent bar is excluded, so the live gap is never in its own
    sample.

    Returns ``{<class>: {"sample", "filled", "fill_probability", "median_days",
    "mean_days"}}`` for every class in :data:`_GAP_HEURISTIC`, plus the
    ``"lookback"`` / ``"horizon"`` / ``"bars"`` provenance keys. A class with
    no occurrence reports ``None`` for its three statistics - never ``0``, and
    never the heuristic (the caller decides what a thin sample means).
    """
    out: dict = {
        cls: {"sample": 0, "filled": 0, "fill_probability": None,
              "median_days": None, "mean_days": None}
        for cls in _GAP_HEURISTIC
    }
    out["lookback"] = n
    out["horizon"] = horizon
    out["bars"] = len(closes or [])
    if not closes or n <= 0:
        return out
    try:
        hist = _classify_history(closes, opens, highs, lows, volumes, n, horizon)
    except (TypeError, ValueError, IndexError, ZeroDivisionError):
        return out
    for cls, days in hist.items():
        if not days:
            continue
        filled = sorted(d for d in days if d <= horizon)
        out[cls] = {
            "sample": len(days),
            "filled": len(filled),
            "fill_probability": len(filled) / len(days),
            "median_days": filled[len(filled) // 2] if filled else None,
            "mean_days": round(statistics.fmean(filled), 2) if filled else None,
        }
    return out


def _classify_history(
    closes, opens, highs, lows, volumes, n: int, horizon: int
) -> dict[str, list[int]]:
    """One walk over the bars, returning ``{class: [days_to_fill, ...]}``.

    A day count of ``horizon + 1`` means the gap never filled inside the
    window. Shared by :func:`gap_fill_sample` and :func:`_gap_fill_stats` so
    the live read and the stored sample cannot classify differently.
    """
    present = [bool(opens) and x is not None for x in (opens or [])]
    use_open = bool(opens) and all(present)
    hist: dict[str, list[int]] = {cls: [] for cls in _GAP_HEURISTIC}
    for i in range(n, len(closes) - 1):
        try:
            prev_close = float(closes[i - 1])
            today_open = float(opens[i]) if use_open else float(closes[i])
            if prev_close <= 0:
                continue
            gap = (today_open - prev_close) / prev_close
            avg_vol = sum(float(v) for v in volumes[i - n:i]) / n
            vr = float(volumes[i]) / avg_vol if avg_vol > 0 else None
            gtype = classify_gap(abs(gap), vr)
            end = min(i + horizon, len(closes) - 1)
            for j in range(i, end + 1):
                hit = (
                    float(lows[j]) <= prev_close
                    if gap > 0
                    else float(highs[j]) >= prev_close
                )
                if hit:
                    hist[gtype].append(j - i)
                    break
            else:
                hist[gtype].append(horizon + 1)  # never filled in the window
        except (TypeError, ValueError, IndexError, ZeroDivisionError):
            continue
    return hist


def _gap_fill_stats(
    closes, opens, highs, lows, volumes, gtype: str, n: int
) -> tuple[float | None, int | None, int]:
    """Empirical fill rate + median days-to-fill for one gap class.

    A thin wrapper over :func:`gap_fill_sample`, so one walk backs both the
    single-class read :func:`gap_type` needs and the full per-class sample.
    Returns ``(fill_probability, median_days, sample_size)``; the first two are
    ``None`` when the class has no occurrences at all.
    """
    entry = gap_fill_sample(closes, opens, highs, lows, volumes, n=n).get(gtype) or {}
    if not entry.get("sample"):
        return None, None, 0
    return entry["fill_probability"], entry["median_days"], entry["sample"]


def gap_type(closes, opens, highs, lows, volumes, n: int = 20) -> dict:
    """Classify the most recent overnight gap + its fill behavior.

    Gap = today's open vs yesterday's close. Types (Investopedia):
      common     - small gap, normal volume, fills fast (high fill prob)
      breakaway  - gaps out of a range/pattern on elevated volume (low fill)
      runaway    - mid-trend continuation gap (low fill)
      exhaustion - gap after a sharp run, likely trend end (high fill)

    Returns ``{type, gap_pct, fill_probability, days_to_fill, fill_basis,
    fill_sample}``. The fill statistics are **measured** over the same-class
    gaps in the history the caller passed (``GAP_FILL_HORIZON`` bars to fill,
    median days among those that did); when a class has fewer than
    ``GAP_FILL_MIN_SAMPLE`` historical occurrences the fixed lookup values are
    used and ``fill_basis`` says so. Nothing is fabricated: with no inputs the
    whole read is ``None``.
    """
    empty = {"type": None, "gap_pct": None, "fill_probability": None,
             "days_to_fill": None, "fill_basis": None, "fill_sample": 0}
    if len(closes) < n + 2 or len(highs) < n + 2 or len(lows) < n + 2 or len(volumes) < n + 2:
        return empty
    try:
        prev_close = float(closes[-2])
        # The gap is today's OPEN vs yesterday's close. A close-proxy for the
        # open silently turned the day's return into an "overnight gap" (SKHY
        # 2026-09-09: +7.32% session move mislabeled an exhaustion gap). Use
        # the real open when the caller passes it; only fall back to closes
        # when no open series exists.
        today_open = float(opens[-1]) if (opens and opens[-1] is not None) else float(closes[-1])
        if prev_close <= 0:
            return empty
        gap_pct = (today_open - prev_close) / prev_close
        avg_vol = sum(float(v) for v in volumes[-n:]) / n
        vol_ratio = float(volumes[-1]) / avg_vol if avg_vol > 0 else None
        # recent range width (volatility context)
        seg_h = [float(x) for x in highs[-n:]]
        seg_l = [float(x) for x in lows[-n:]]
        rng = max(seg_h) - min(seg_l)
        abs_gap = abs(gap_pct)
        if rng <= 0:
            return {**empty, "gap_pct": round(gap_pct, 6)}
        gtype = classify_gap(abs_gap, vol_ratio)
        prob, days, sample = _gap_fill_stats(
            closes, opens, highs, lows, volumes, gtype, n)
        if prob is not None and sample >= GAP_FILL_MIN_SAMPLE:
            basis = f"measured ({sample} historical {gtype} gaps)"
        else:
            prob, days = _GAP_HEURISTIC[gtype]
            basis = f"heuristic ({sample} historical {gtype} gaps < {GAP_FILL_MIN_SAMPLE})"
        return {
            "type": gtype,
            "gap_pct": round(gap_pct, 6),
            "fill_probability": round(prob, 4),
            "days_to_fill": days,
            "fill_basis": basis,
            "fill_sample": sample,
        }
    except (TypeError, ValueError, ZeroDivisionError):
        return empty


def order_imbalance(inst_net: float | None, retail_net: float | None) -> dict:
    """Order-imbalance verdict from institutional vs retail net flow.

    ``inst_net`` / ``retail_net`` are the net signed flows (e.g. from
    ``orderflow.institutional_net`` / ``retail_net``). Returns
    ``{verdict, ratio}`` where ratio = (inst_net + retail_net) /
    (|inst_net| + |retail_net|) - the signed net flow over total flow, so +1 is
    all-institutional buying, -1 all-retail selling, 0 perfectly balanced - and
    verdict is buy-heavy / sell-heavy / balanced. None when both are missing.
    """
    if inst_net is None and retail_net is None:
        return {"verdict": None, "ratio": None}
    inst = float(inst_net) if inst_net is not None else 0.0
    retail = float(retail_net) if retail_net is not None else 0.0
    denom = abs(inst) + abs(retail)
    if denom <= 0:
        return {"verdict": "balanced", "ratio": 0.0}
    # signed net / total flow: +1 = all institutional buying, -1 = all
    # retail/selling, 0 = perfectly balanced.
    ratio = (inst + retail) / denom
    if ratio > 0.3:
        verdict = "buy-heavy"
    elif ratio < -0.3:
        verdict = "sell-heavy"
    else:
        verdict = "balanced"
    return {"verdict": verdict, "ratio": round(ratio, 4)}


def premarket_liquidity(volume: float | None, avg_volume: float | None) -> dict:
    """Pre-market liquidity read: current pre-market volume vs the daily
    average. A very low ratio = thin book (wide spreads, gap risk).

    Returns ``{ratio, verdict}`` where verdict is liquid / thin / illiquid.
    None when either input is missing.
    """
    if volume is None or avg_volume is None or avg_volume <= 0:
        return {"ratio": None, "verdict": None}
    ratio = float(volume) / float(avg_volume)
    if ratio >= 0.10:
        verdict = "liquid"
    elif ratio >= 0.03:
        verdict = "thin"
    else:
        verdict = "illiquid"
    return {"ratio": round(ratio, 4), "verdict": verdict}


def post_close_confirmation(close: float | None, stop: float | None, target: float | None) -> dict:
    """Post-close confirmation: did the close confirm the plan?

    Returns ``{verdict, action}``:
      - close beyond the stop  -> 'stopped-out' (REJECT the plan)
      - close at/above target  -> 'target-hit' (take profit)
      - close between stop/target -> 'holding' (plan intact)
    None when close is missing.
    """
    if close is None:
        return {"verdict": None, "action": None}
    c = float(close)
    if stop is not None and target is not None:
        lo, hi = min(float(stop), float(target)), max(float(stop), float(target))
        if c < lo:
            return {"verdict": "stopped-out", "action": "exit"}
        if c > hi:
            return {"verdict": "target-hit", "action": "take-profit"}
        return {"verdict": "holding", "action": "hold"}
    if stop is not None and c < float(stop):
        return {"verdict": "stopped-out", "action": "exit"}
    if target is not None and c > float(target):
        return {"verdict": "target-hit", "action": "take-profit"}
    return {"verdict": "holding", "action": "hold"}


def decompose_returns(opens, closes) -> dict | None:
    """Overnight / intraday log-return decomposition (N8).

    For each pair ``t`` (1-based, needs the prior close):
      ``intraday_t = ln(close_t / open_t)``
      ``overnight_t = ln(open_t / close_{t-1})``
    so the two legs sum to the close-to-close log return
    ``ln(close_t / close_{t-1})``.

    This is a **decomposition** of where the move sat (the session vs the
    overnight gap), not an attribution to any news or cause.

    Returns ``{intraday_mean, intraday_vol, overnight_mean, overnight_vol,
    intraday_var_share, n, basis}`` where the means and stdevs are per-period
    in raw log-return units (``vol`` is a sample stdev, ``n-1`` denominator,
    *not* annualised) and ``intraday_var_share = var(intraday) /
    (var(intraday) + var(overnight))`` over the same pairs. ``n`` is the number
    of return pairs used. ``None`` when fewer than 3 pairs remain, any price is
    non-positive / non-finite, ``opens`` is missing, ragged (length mismatch or
    a ``None`` entry), or the total variance is zero.
    """
    if opens is None or closes is None:
        return None
    try:
        o = list(opens)
        c = list(closes)
    except TypeError:
        return None
    if len(o) != len(c) or len(o) < 4:
        return None
    intraday: list[float] = []
    overnight: list[float] = []
    for t in range(1, len(c)):
        o_t, c_t, c_prev = o[t], c[t], c[t - 1]
        if o_t is None or c_t is None or c_prev is None:
            return None
        try:
            o_t = float(o_t)
            c_t = float(c_t)
            c_prev = float(c_prev)
        except (TypeError, ValueError):
            return None
        if min(o_t, c_t, c_prev) <= 0 or not (
            math.isfinite(o_t) and math.isfinite(c_t) and math.isfinite(c_prev)
        ):
            return None
        intraday.append(math.log(c_t / o_t))
        overnight.append(math.log(o_t / c_prev))
    n = len(intraday)
    if n < 3:
        return None
    v_intraday = statistics.variance(intraday)
    v_overnight = statistics.variance(overnight)
    total = v_intraday + v_overnight
    if total <= 0:
        return None
    return {
        "intraday_mean": statistics.fmean(intraday),
        "intraday_vol": math.sqrt(v_intraday),
        "overnight_mean": statistics.fmean(overnight),
        "overnight_vol": math.sqrt(v_overnight),
        "intraday_var_share": v_intraday / total,
        "n": n,
        "basis": (
            "intraday=ln(C/O), overnight=ln(O/C_prev); "
            f"{n} pairs; raw per-period log-return mean/stdev (not annualised)"
        ),
    }


def decompose_returns_text(read: dict | None) -> str:
    """Render a ``decompose_returns`` read as one compact line.

    States the decomposition (which leg carried the move), never a cause.
    ``None`` -> ``"return decomposition unavailable"``.
    """
    if not read:
        return "return decomposition unavailable"
    return (
        f"intraday {read['intraday_mean']:+.4f} (sd {read['intraday_vol']:.4f}) | "
        f"overnight {read['overnight_mean']:+.4f} (sd {read['overnight_vol']:.4f}) | "
        f"intraday var share {read['intraday_var_share']:.1%} | "
        f"n={read['n']} | {read['basis']}"
    )
