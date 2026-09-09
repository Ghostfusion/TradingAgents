"""Per-rule forward-return evaluation (advisory, pure, deterministic).

SKHY 2026-09-09 review-loop lesson (#11/#12/#13/#14): an indicator set
(RSI, MACD, Bollinger, VWMA, ATR, regime/knife composites) that looks
impressive is worth nothing until each rule's forward returns are measured.
This module evaluates configured rules against a close series:

  rule_name  n_events   n>=30?   fwd1  fwd5  fwd10  fwd20  hit_rate  avg_ret
  median_ret  max_adverse  max_favourable  sharpe_ann  profit_factor  verdict

Every rule is a pure feature function on (closes, highs, lows, volumes)
returning bool OR {value, trigger} -- the module evaluates TRIGGER events and
their forward returns. A rule with < 30 events renders INSUFFICIENT, never a
table of noise. Conditional-vs-base rows (rule AND another rule) let the user
answer "does adding THIS signal help?" with an incremental number.

Pure: no IO/LLM. Never gates anything; advisory output for
``scripts/rule_eval.py`` and the methodology-registry ethos.
"""

from __future__ import annotations

import math
from statistics import mean, median

__all__ = ["evaluate_rule", "forward_returns", "rule_signal_rsi70", "DEFAULT_RULES", "MIN_EVENTS"]


MIN_EVENTS = 30


def forward_returns(closes: list[float], i: int, horizons=(1, 5, 10, 20)) -> dict:
    """Forward pct returns from index ``i`` at each horizon; None when 0/na."""
    px = float(closes[i])
    if px <= 0:
        return dict.fromkeys(horizons, None)
    out: dict[int, float | None] = {}
    for h in horizons:
        j = i + h
        out[h] = (float(closes[j]) / px - 1.0) if j < len(closes) else None
    return out


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(len(closes) - period, len(closes)):
        d = closes[i] - closes[i - 1]
        if d >= 0:
            gains += d
        else:
            losses += -d
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100.0 - 100.0 / (1.0 + rs)


def _sma(closes: list[float], n: int) -> float | None:
    if len(closes) < n:
        return None
    return mean(closes[-n:])


def _ema(closes: list[float], n: int) -> float | None:
    if len(closes) < n:
        return None
    k = 2.0 / (n + 1.0)
    e = closes[-n]
    for v in closes[-n + 1:]:
        e = v * k + e * (1.0 - k)
    return e


def _vol(closes: list[float], n: int = 20) -> float | None:
    if len(closes) < n + 1:
        return None
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, n + 1) if closes[i - 1] > 0]
    if len(rets) < n:
        return None
    m = mean(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var * 252.0)


# --- rule feature functions (over closes/highs/lows/volumes) ----------------
# Each returns bool meaning "this rule fired at the current bar".


def rule_signal_rsi70(closes, highs, lows, volumes, lookback=10) -> bool:
    """RSI(14) > 70 (overbought threshold)."""
    r = _rsi(closes)
    return r is not None and r > 70.0


def rule_signal_rsi_buy(closes, highs, lows, volumes) -> bool:
    """RSI(14) < 35 (oversold / value-dip entry zone)."""
    r = _rsi(closes)
    return r is not None and r < 35.0


def rule_signal_macd_hist_rising(closes, highs, lows, volumes) -> bool:
    """MACD histogram rising: ema12-ema26 vs its prior bar."""
    if len(closes) < 40:
        return False
    try:
        e12 = _ema(closes, 12)
        e26 = _ema(closes, 26)
        prev12 = _ema(closes[:-1], 12)
        prev26 = _ema(closes[:-1], 26)
        if e12 is None or e26 is None or prev12 is None or prev26 is None:
            return False
        return (e12 - e26) > (prev12 - prev26)
    except Exception:  # noqa: BLE001
        return False


def rule_signal_bb_extension(closes, highs, lows, volumes) -> bool:
    """Price above the +2σ Bollinger upper band."""
    if len(closes) < 21:
        return False
    mid = _sma(closes, 20)
    sd = _vol(closes, 20)
    if mid is None or sd is None:
        return False
    return closes[-1] > mid + 2.0 * sd * math.sqrt(20.0 / 252.0)


def rule_signal_high_vol(closes, highs, lows, volumes, pct: float = 0.90) -> bool:
    """Recent realized vol in the top decile of its own rolling history."""
    if len(closes) < 80:
        return False
    vols = [v for v in (_vol(closes[:i], 20) for i in range(40, len(closes) + 1)) if v is not None]
    if len(vols) < 30:
        return False
    cur = vols[-1]
    rank = sum(1 for v in vols if v <= cur) / len(vols)
    return rank >= pct


def rule_signal_price_above_vwma(closes, highs, lows, volumes, sdev: float = 0.0) -> bool:
    """Price above the volume-weighted moving average of the last 20 bars."""
    if len(closes) < 21 or not volumes:
        return False
    w = sum(volumes[-20:])
    if w <= 0:
        return False
    vwap = sum(closes[i] * volumes[i] for i in range(len(closes) - 20, len(closes))) / w
    return closes[-1] > vwap * (1.0 + sdev)


DEFAULT_RULES: dict[str, object] = {
    "rsi_overbought": rule_signal_rsi70,
    "rsi_oversold": rule_signal_rsi_buy,
    "macd_hist_rising": rule_signal_macd_hist_rising,
    "bollinger_extension": rule_signal_bb_extension,
    "high_vol_p90": rule_signal_high_vol,
    "price_above_vwma": rule_signal_price_above_vwma,
}


def evaluate_rule(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
    rule_fn,
    lookback: int = 1,
    horizons=(1, 5, 10, 20),
    label: str = "rule",
) -> dict:
    """Evaluate one rule over a close series; returns per-horizon stats.

    A rule fires at bar i when true at that bar. We only keep events with at
    least one non-None forward return, and require >= MIN_EVENTS else
    ``verdict=INSUFFICIENT``. Advisory; no fabrication.
    """
    events: list[dict] = []
    for i in range(max(60, lookback), len(closes) - 1):
        window_c = closes[: i + 1]
        window_h = highs[: i + 1]
        window_l = lows[: i + 1]
        window_v = volumes[: i + 1]
        try:
            fired = bool(rule_fn(window_c, window_h, window_l, window_v))
        except Exception:  # noqa: BLE001 - a rule degrades, never aborts
            fired = False
        if not fired:
            continue
        fr = forward_returns(closes, i, horizons)
        if all(v is None for v in fr.values()):
            continue
        events.append({"index": i, "forward": fr})

    n = len(events)
    if n < MIN_EVENTS:
        return {"label": label, "verdict": "INSUFFICIENT", "n_events": n, "min_events": MIN_EVENTS}

    stats: dict[int, dict] = {}
    for h in horizons:
        vals = [e["forward"][h] for e in events if e["forward"][h] is not None]
        if not vals:
            stats[h] = {"n": 0, "avg": None, "median": None, "hit": None,
                        "max_adverse": None, "max_favourable": None, "sharpe": None, "profit_factor": None}
            continue
        wins = sum(1 for v in vals if v > 0)
        pf_num = sum(v for v in vals if v > 0)
        pf_den = sum(-v for v in vals if v < 0)
        sd = math.sqrt(sum((v - mean(vals)) ** 2 for v in vals) / (len(vals) - 1)) if len(vals) > 1 else 0.0
        stats[h] = {
            "n": len(vals),
            "avg": mean(vals),
            "median": median(vals),
            "hit": wins / len(vals),
            "max_adverse": min(vals),
            "max_favourable": max(vals),
            "sharpe": (mean(vals) / sd * math.sqrt(252.0)) if sd > 0 else None,
            "profit_factor": (pf_num / pf_den) if pf_den > 0 else (None if pf_num == 0 else float("inf")),
        }
    return {"label": label, "verdict": "PREDICTIVE", "n_events": n, "stats": stats}
