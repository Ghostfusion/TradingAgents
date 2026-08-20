"""Massive.com Flat Files: bulk US OHLCV day-aggregates loader.

Massive's **Flat Files** are bulk, downloadable CSVs (S3-backed) covering all
U.S. equities at day/minute granularity. They are a *bulk* access mode - one
file holds every ticker for a window - so they do not fit the per-ticker
``route_to_vendor`` ``@tool`` contract. Their natural fit is a **historical
backend for the value-screener's OHLCV scans** (swing / VCP / ATR bases), which
today re-pull per-ticker daily bars from yfinance/moomoo/Alpaca.

This module:

- exposes ``load_day_aggregates(csv_path)`` - parse a Flat File day-aggregates
  CSV (columns ``ticker, volume, open, close, high, low, window_start,
  transactions``) into per-ticker ``{closes, opens, highs, lows, volumes,
  dates}`` series;
- exposes ``ohlcv_for(ticker, csv_path, ...)`` returning just that ticker's
  series in the same shape ``scripts/value_screener._fetch_ohlcv`` produces, so
  a screener run can optionally seed its ATR/scan bases from a bulk download
  instead of N per-ticker calls.

Plan-aware: Flat Files require a **Stocks Starter+** plan (free Basic is quote-
only) and the download URL is account-scoped (presigned / console-export), so
this module takes a local CSV path rather than hitting a REST endpoint. It
delegates to the caller to obtain the file (Massive console / SDK). On a free
plan the screener keeps its existing per-ticker chain.
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Column names as served by Massive's day-aggregates flat file (see
# https://massive.com/docs/flat-files/stocks/day-aggregates).
_FLAT_COLS = ("ticker", "volume", "open", "close", "high", "low", "window_start", "transactions")


def _window_dt(ts) -> str | None:
    """Convert a window_start (Unix ns int or numeric str) to 'YYYY-MM-DD'."""
    if ts is None or ts == "":
        return None
    try:
        ns = float(ts)
        # Unix nanoseconds -> seconds. Round to midnight UTC-ish; the file's
        # window_start is a market-day boundary in epoch ns.
        sec = ns / 1e9
        dt = datetime.fromtimestamp(sec, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def load_day_aggregates(csv_path) -> dict:
    """Parse a Massive Flat-File day-aggregates CSV into per-ticker series.

    Returns ``{ticker: {"closes": [...], "opens": [...], "highs": [...],
    "lows": [...], "volumes": [...], "dates": [...]}}`` with rows in file order
    (ascending by window when the file is window-ordered). An empty CSV / no
    parseable rows returns ``{}``.
    """
    series: dict = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        # Detect header row: the first row holds the column names.
        sample = fh.read(2000)
        fh.seek(0)
        has_header = "ticker" in sample.lower()
        reader = csv.reader(fh)
        if has_header:
            next(reader, None)
        for row in reader:
            if not row or len(row) < 6:
                continue
            ticker = (row[0] or "").strip().upper()
            if not ticker:
                continue
            # Flat-file column order: ticker, volume, open, close, high, low,
            # window_start, transactions (per Massive's day-aggregates schema).
            try:
                vol = float(row[1]) if row[1] else None
                open_ = float(row[2]) if row[2] else None
                close = float(row[3]) if row[3] else None
                high = float(row[4]) if len(row) > 4 and row[4] else None
                low = float(row[5]) if len(row) > 5 and row[5] else None
            except (TypeError, ValueError):
                close = open_ = high = low = vol = None
            date_s = _window_dt(row[6]) if len(row) > 6 else None
            bucket = series.setdefault(
                ticker,
                {"closes": [], "opens": [], "highs": [], "lows": [], "volumes": [], "dates": []},
            )
            if close is not None:
                bucket["closes"].append(close)
            if open_ is not None:
                bucket["opens"].append(open_)
            if high is not None:
                bucket["highs"].append(high)
            if low is not None:
                bucket["lows"].append(low)
            if vol is not None:
                bucket["volumes"].append(vol)
            if date_s is not None:
                bucket["dates"].append(date_s)
    return series


def ohlcv_for_ticker(csv_path, ticker: str) -> dict | None:
    """Return one ticker's OHLCV series from a flat-file, or ``None`` if absent."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return None
    series = load_day_aggregates(csv_path)
    out = series.get(ticker)
    if not out or not out["closes"]:
        return None
    return out


def _find_candidates(dir_path) -> list:
    """Top-level .csv files in the flat-file folder."""
    if not dir_path or not os.path.isdir(dir_path):
        return []
    return sorted(
        os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.lower().endswith(".csv")
    )


def ohlcv_for_ticker_dir(dir_path, ticker: str) -> dict | None:
    """Return ``ticker``'s OHLCV from the day-aggregates CSV in a folder (the
    ``massive_flat_dir`` config). Uses the file with the longest close history
    for the ticker, or None when no usable series is found.
    """
    best = None
    for csvf in _find_candidates(dir_path):
        out = ohlcv_for_ticker(csvf, ticker)
        if out and (best is None or len(out["closes"]) > len(best["closes"])):
            best = out
    return best



__all__ = ["load_day_aggregates", "ohlcv_for_ticker", "ohlcv_for_ticker_dir"]
