"""Deterministic market-data verification snapshot.

The market analyst is an LLM that can confabulate exact numbers — citing a
Bollinger band or a "historically validated bounce" that the underlying data
doesn't support (#830). This module computes a ground-truth snapshot (latest
OHLCV row on or before the analysis date, common indicators, recent closes)
the analyst is told to treat as the source of truth for any exact numeric
claim. Deterministic, no LLM involved.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
from stockstats import wrap

from tradingagents.dataflows.stockstats_utils import load_ohlcv

# A fixed, common indicator set so the snapshot is the same shape every run.
DEFAULT_SNAPSHOT_INDICATORS: tuple[str, ...] = (
    "close_10_ema", "close_50_sma", "close_200_sma",
    "rsi", "boll", "boll_ub", "boll_lb",
    "macd", "macds", "macdh", "atr",
)

# Minimum observations every indicator needs BEFORE stockstats' rolling
# window is a genuine statistic, not a truncated-mean fallback. On a short
# history (e.g. SKHY ADR only 43 bars), stockstats silently returns a fallback
# equal to the short-series mean for a 200-day SMA — a real value that must
# never be read as a genuine 200-day average (reviewer: data-quality layer).
# When ``len(df) < min`` the rendered value is flagged "(insufficient
# history: N/MIN)".
_INDICATOR_MIN_BARS: dict[str, int] = {
    "close_10_ema": 10,
    "close_50_sma": 50,
    "close_200_sma": 200,
    "rsi": 15,
    "boll": 20, "boll_ub": 20, "boll_lb": 20,
    "macd": 35, "macds": 35, "macdh": 35,
    "atr": 15,
}


def _verified_rows(symbol: str, curr_date: str) -> pd.DataFrame:
    """OHLCV on or before curr_date, date-sorted. Raises if nothing usable.

    ``load_ohlcv`` already normalizes the Date column and filters out
    look-ahead rows, but we re-apply the cutoff defensively — this is a
    verification path, so it must not trust its input to be pre-filtered.
    """
    data = load_ohlcv(symbol, curr_date)
    if data is None or data.empty:
        raise ValueError(f"No OHLCV data available for {symbol}.")

    df = data.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df[df["Date"] <= pd.to_datetime(curr_date)].sort_values("Date")
    if df.empty:
        raise ValueError(f"No OHLCV rows on or before {curr_date} for {symbol}.")
    return df


def _fmt(value) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)



def live_price_sanity(live_price: float | None, day_low: float | None,
                      day_high: float | None, buffer_pct: float = 0.05) -> str:
    """Label a live print against the verified day's bar and its tolerance buffer.

    Guards the reconciliation path: a real-time quote outside the verified OHLC
    range is far more likely a stale feed / symbol-mismatch than a genuine move.
    Bands: INSIDE (within ``[low, high]``); OUTSIDE (past the bar edge but within
    the ``buffer_pct`` tolerance - the mild advisory); BELOW / ABOVE (beyond the
    tolerance, the strong mismatch). Returns a one-line advisory so reports can
    flag it instead of presenting it as a clean read.
    Unknown inputs -> 'no bar to compare' (never fabricates).
    """
    if live_price is None or day_low is None or day_high is None:
        return "live price sanity: insufficient data (no verified bar to compare)"
    low, high = float(day_low), float(day_high)
    lv = float(live_price)
    lo_buf = low * (1.0 - abs(float(buffer_pct)))
    hi_buf = high * (1.0 + abs(float(buffer_pct)))
    # Four explicit bands, so the OUTSIDE advisory is reachable: a print past the
    # bar edge but inside the stale-print buffer is not "INSIDE the bar", and a
    # print beyond the buffer is the strong below/above mismatch.
    if lv < lo_buf:
        return (
            f"live price sanity: BELOW verified day-low - live {lv:.2f} < "
            f"verified low {low:.2f} (buffer {buffer_pct:.0%} => threshold "
            f"{lo_buf:.2f}); likely stale feed / symbol mismatch - do not "
            f"reconcile as a true print"
        )
    if lv > hi_buf:
        return (
            f"live price sanity: ABOVE verified day-high - live {lv:.2f} > "
            f"verified high {high:.2f} (buffer {buffer_pct:.0%} => threshold "
            f"{hi_buf:.2f}); likely stale feed / symbol mismatch - do not "
            f"reconcile as a true print"
        )
    if low <= lv <= high:
        return f"live price sanity: INSIDE verified bar ({lv:.2f} within the verified day's range [{low:.2f},{high:.2f}]; stale-print tolerance +-{buffer_pct:.0%})"
    return (
        f"live price sanity: OUTSIDE verified bar - live {lv:.2f} vs "
        f"verified [{low:.2f},{high:.2f}] (buffer {buffer_pct:.0%}); "
        f"likely stale feed / symbol mismatch - do not reconcile as a true print"
    )


def build_verified_market_snapshot(
    symbol: str,
    curr_date: str,
    look_back_days: int = 30,
    indicators: Iterable[str] | None = None,
) -> str:
    """Render a ground-truth snapshot: latest OHLCV row, indicators, recent closes."""
    # `df` keeps the original capitalized OHLCV columns (Open/High/Low/Close/
    # Volume); stockstats `wrap()` lowercases columns and adds indicator
    # columns, so read raw prices from `df` and indicators from `stock_df`.
    df = _verified_rows(symbol, curr_date)
    stock_df = wrap(df.copy())

    selected = tuple(indicators or DEFAULT_SNAPSHOT_INDICATORS)
    n_rows = len(df)
    indicator_values: dict[str, str] = {}
    for name in selected:
        try:
            stock_df[name]  # triggers stockstats calculation
            val = _fmt(stock_df.iloc[-1][name])
            # stockstats SILENTLY substitutes a truncated-window mean for a
            # rolling indicator when the history is shorter than the window
            # (SKHY ADR n=43: close_200_sma == close_50_sma == full-series
            # mean). A 200-day SMA from 43 bars must be labeled as
            # insufficient history, never read as a genuine 200-day average.
            if val != "N/A":
                min_bars = _INDICATOR_MIN_BARS.get(name)
                if min_bars and n_rows < min_bars:
                    val = f"{val} (insufficient history: {n_rows}/{min_bars})"
            indicator_values[name] = val
        except Exception as exc:  # noqa: BLE001 — one bad indicator shouldn't sink the snapshot
            indicator_values[name] = f"N/A ({type(exc).__name__})"

    latest = df.iloc[-1]
    latest_date = _fmt(latest["Date"])
    window = max(1, min(int(look_back_days), 30))
    recent = df.tail(window)

    # Record the verified latest close so OHLCV-based tools (swing/support/
    # candlestick/etc.) can append a scale/staleness warning when their own
    # series disagrees with this authoritative level (INTU 2026-09-08).
    try:
        from tradingagents.agents.utils.price_consistency import set_verified_close

        set_verified_close(symbol, latest.get("Close"))
    except Exception:  # noqa: BLE001 - advisory, never break the snapshot
        pass

    lines = [
        f"## Verified market data snapshot for {symbol.upper()}",
        "",
        f"- Requested analysis date: {curr_date}",
        f"- Latest trading row used: {latest_date}",
        "- Rows after the requested analysis date are excluded before verification.",
    ]
    if str(latest["Date"])[:10] == str(curr_date):
        lines.append(
            "- NOTE: the latest row is dated = the requested analysis date - if that "
            "session is still in progress (an intraday run), it is a FORMING bar and "
            "its Close + all close-derived indicators (SMA/EMA/MACD/RSI/bands/ATR) "
            "are PROVISIONAL until the session closes; treat any EOD-signal claim as "
            "provisional, never a settled close."
        )
    lines += [
        "",
        "### Latest verified OHLCV row",
        "",
        "| Field | Value |",
        "|---|---:|",
    ]
    for field in ("Open", "High", "Low", "Close", "Volume"):
        lines.append(f"| {field} | {_fmt(latest.get(field))} |")

    lines += ["", "### Verified technical indicators (latest row)", "",
              "| Indicator | Value |", "|---|---:|"]
    for name, value in indicator_values.items():
        # stockstats computes ATR with the default 14-period window; label it
        # so a swing/tranche ATR(14) is not mistaken for a different window.
        label = "atr(14)" if name == "atr" else name
        lines.append(f"| {label} | {value} |")

    lines += ["", f"### Recent verified closes (last {len(recent)} rows)", "",
              "| Date | Close |", "|---|---:|"]
    for _, row in recent.iterrows():
        lines.append(f"| {_fmt(row['Date'])} | {_fmt(row.get('Close'))} |")

    lines += [
        "",
        "Use this snapshot as the source of truth for exact OHLCV, price-level, "
        "and indicator-value claims. If another tool output conflicts with it, "
        "flag the discrepancy rather than inventing a reconciled number. Do not "
        "claim historical validation, support/resistance bounces, or exact "
        "percentage moves unless directly supported by tool output with concrete "
        "dates and prices.",
    ]
    return "\n".join(lines)
