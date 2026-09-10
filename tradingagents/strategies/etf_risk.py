"""ETF relative-strength + risk profile (advisory).

The IGV 2026-09-09 fundamentals report (reviewed 2026-09-09) inferred
relative performance from a single ``priceRelativeToS&P500`` field with no
benchmark leg shown, and treated beta alone as a risk signal. This module
renders relative returns with BOTH legs visible (IGV 3M +7.10% vs SPY
+3.85% -> relative +3.25%) and a richer risk profile (beta vs SPY and QQQ,
downside/upside capture, realized-vol percentile, ATR%, max drawdown).

Every metric is None-safe; a missing benchmark series degrades that leg to
None. Advisory by contract; never blocks.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def _rets(series: Sequence[float]) -> list[float]:
    out = []
    for i in range(1, len(series)):
        a, b = series[i - 1], series[i]
        if a is None or b is None or a <= 0:
            continue
        out.append(math.log(b / a))
    return out


def _period_ret(series: Sequence[float], window: int) -> float | None:
    if not series or len(series) <= window:
        return None
    base = series[-window - 1]
    if base is None or base <= 0:
        return None
    return series[-1] / base - 1.0


def _beta(x_rets: Sequence[float], y_rets: Sequence[float]) -> float | None:
    """OLS beta of y on x over the shared window."""
    n = min(len(x_rets), len(y_rets))
    if n < 3:
        return None
    x, y = x_rets[-n:], y_rets[-n:]
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    var = sum((a - mx) ** 2 for a in x)
    if var <= 0:
        return None
    return cov / var


def _capture(capture_series: Sequence[float], bench_rets: Sequence[float], downside: bool):
    """Mean capture_series return when bench is down (or up) / mean bench."""
    n = min(len(capture_series), len(bench_rets))
    if n < 3:
        return None
    cap, bench = capture_series[-n:], bench_rets[-n:]
    pairs = [(c, b) for c, b in zip(cap, bench, strict=True) if (b < 0 if downside else b > 0)]
    if not pairs:
        return None
    cap_avg = sum(c for c, _ in pairs) / len(pairs)
    bench_avg = sum(b for _, b in pairs) / len(pairs)
    if abs(bench_avg) < 1e-12:
        return None
    return cap_avg / bench_avg


def _realized_vol(series: Sequence[float], window: int = 20) -> float | None:
    rets = _rets(series)
    if len(rets) < window:
        return None
    tail = rets[-window:]
    mean = sum(tail) / len(tail)
    var = sum((r - mean) ** 2 for r in tail) / (len(tail) - 1)
    return math.sqrt(max(var, 0.0) * 252.0)


def _sma_last(series: Sequence[float], window: int) -> float | None:
    if not series or len(series) < window:
        return None
    tail = series[-window:]
    if any(x is None for x in tail):
        return None
    return sum(tail) / window


def etf_relative_strength(
    ticker: str,
    *,
    closes: Sequence[float] | None,
    bench_map: dict[str, Sequence[float] | None],
    windows: tuple[int, ...] = (21, 63, 126, 252),
) -> dict:
    """Relative returns vs each benchmark, both legs shown.

    Args:
        ticker: the ETF symbol.
        closes: the ETF's daily close series.
        bench_map: {benchmark_label: closes} (e.g. SPY, QQQ, XLK).

    Returns:
        ``{"ticker", "benchmarks": {label: {w: {"etf_ret", "bench_ret",
        "relative"}}}}`` — every value None-safe.
    """
    out: dict = {}
    for label, bench in (bench_map or {}).items():
        legs = {}
        for w in windows:
            er = _period_ret(closes or [], w) if closes else None
            br = _period_ret(bench or [], w) if bench else None
            rel = er - br if (er is not None and br is not None) else None
            legs[str(w)] = {
                "etf_ret": round(er, 4) if er is not None else None,
                "bench_ret": round(br, 4) if br is not None else None,
                "relative": round(rel, 4) if rel is not None else None,
            }
        out[label] = legs
    return {"ticker": ticker, "benchmarks": out}


def _atr(highs: Sequence[float] | None, lows: Sequence[float] | None,
         closes: Sequence[float] | None, window: int = 14) -> float | None:
    """Wilder ATR over the trailing bars; None when high/low series missing."""
    if not highs or not lows or len(highs) != len(lows) or len(highs) < window + 1:
        return None
    trs = []
    for i in range(len(highs) - window, len(highs)):
        h, lo, pc = highs[i], lows[i], closes[i - 1] if closes and i - 1 >= 0 and len(closes) > i - 1 else None
        if h is None or lo is None:
            continue
        tr = h - lo
        if pc is not None:
            tr = max(tr, abs(h - pc), abs(lo - pc))
        trs.append(tr)
    if not trs:
        return None
    # simple average (advisory; Wilder smoothing is a refinement)
    return sum(trs) / len(trs)


def etf_risk_profile(
    ticker: str,
    *,
    closes: Sequence[float] | None,
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
    bench_map: dict[str, Sequence[float] | None] | None = None,
    vol_window: int = 20,
) -> dict:
    """Risk profile for an ETF.

    Args:
        ticker: the ETF symbol.
        closes: the ETF's daily close series.
        highs / lows: optional high/low series for a real ATR% (None-safe).
        bench_map: {benchmark_label: closes} used for beta/capture vs each.
        vol_window: rolling realized-vol window (bars).

    Returns a dict with every metric None-safe.
    """
    rets = _rets(closes or [])
    vol = _realized_vol(closes or [], vol_window)
    vol_pctile = None
    if vol is not None and len(rets) >= 190:
        # realized vol over the last 63d window vs the trailing ~3Y of 63d windows
        tail = rets[-630:]
        windows = []
        for i in range(0, max(0, len(tail) - 62)):
            w = tail[i:i + 63]
            if len(w) < 63:
                continue
            mean = sum(w) / len(w)
            var = sum((r - mean) ** 2 for r in w) / (len(w) - 1)
            windows.append(math.sqrt(max(var, 0.0) * 252.0))
        if windows:
            vol_pctile = sum(1 for x in windows if x < vol) / len(windows)
    # ATR% = ATR(14) / price — requires high/low series; closes-only cannot
    # produce a real ATR, so render n/a unless highs/lows are supplied.
    atr = _atr(highs, lows, closes)
    atr_pct = atr / closes[-1] if (atr is not None and closes and closes[-1]) else None

    max_dd = None
    if closes and len(closes) >= 2:
        peak = max(closes)
        if peak > 0:
            max_dd = closes[-1] / peak - 1.0

    bs = {}
    for label, bench in (bench_map or {}).items():
        br = _rets(bench or [])
        entry: dict = {"beta": None, "downside_capture": None, "upside_capture": None}
        entry["beta"] = _beta(br, rets)
        entry["downside_capture"] = _capture(rets, br, downside=True)
        entry["upside_capture"] = _capture(rets, br, downside=False)
        bs[label] = {k: (round(v, 3) if v is not None else None) for k, v in entry.items()}

    return {
        "ticker": ticker,
        "realized_vol": round(vol, 4) if vol is not None else None,
        "vol_percentile": round(vol_pctile, 3) if vol_pctile is not None else None,
        "atr_pct": round(atr_pct, 4) if atr_pct is not None else None,
        "max_drawdown": round(max_dd, 4) if max_dd is not None else None,
        "benchmarks": bs,
    }


__all__ = ["etf_relative_strength", "etf_risk_profile"]
