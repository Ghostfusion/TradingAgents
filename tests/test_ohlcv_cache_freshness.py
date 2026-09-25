"""Same-day OHLCV cache must not serve a stale snapshot all day (#1150).

The cache file is keyed per day, so a run started before the day's bar was final
would be reused by every later run, feeding a stale close into technical
analysis. Two cases matter for a current-day request: the bar may be missing, or
present but still in progress (Yahoo publishes a partial daily candle intraday).
Refresh is bounded by a TTL so repeated runs cannot hammer the vendor.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import pytest

import tradingagents.dataflows.stockstats_utils as su

TODAY = pd.Timestamp("2026-07-18")
STALE = su.OHLCV_CACHE_TTL_SECONDS + 60


def _write(tmp_path, name="cache.csv", age_seconds=0.0, last_date="2026-07-17"):
    f = tmp_path / name
    pd.DataFrame({"Date": [last_date], "Close": [1.0]}).to_csv(f, index=False)
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(f, (old, old))
    return str(f)


@pytest.mark.unit
def test_current_day_cache_past_ttl_is_refreshed(tmp_path):
    # Bar missing (rows stop at yesterday) and file older than the TTL -> refetch.
    assert su._needs_same_day_refresh(_write(tmp_path, age_seconds=STALE), TODAY, TODAY) is True


@pytest.mark.unit
def test_partial_current_day_bar_is_still_refreshed(tmp_path):
    # Today's row is present but may be an in-progress candle whose Close is not
    # the closing price. Row inspection can't distinguish it, so the TTL governs.
    f = _write(tmp_path, age_seconds=STALE, last_date="2026-07-18")
    assert su._needs_same_day_refresh(f, TODAY, TODAY) is True


@pytest.mark.unit
def test_recent_cache_is_not_refetched(tmp_path):
    # Written moments ago: don't hammer the vendor (weekend/holiday guard).
    assert su._needs_same_day_refresh(_write(tmp_path), TODAY, TODAY) is False


@pytest.mark.unit
def test_historical_request_always_uses_cache(tmp_path):
    # Past dates are immutable: never refetch, however old the file is.
    past = pd.Timestamp("2026-05-01")
    f = _write(tmp_path, age_seconds=STALE, last_date="2026-04-30")
    assert su._needs_same_day_refresh(f, past, TODAY) is False


@pytest.mark.unit
def test_load_ohlcv_refetches_stale_same_day_cache(tmp_path, monkeypatch):
    """End-to-end: the helper is actually wired into load_ohlcv's cache branch.

    Without this, the unit tests above would still pass if the helper were never
    called from the real code path.
    """
    monkeypatch.setattr(su, "get_config", lambda: {"data_cache_dir": str(tmp_path)})
    monkeypatch.setattr(su.pd.Timestamp, "today", staticmethod(lambda: TODAY))

    # Pre-seed the cache file load_ohlcv will look for, aged past the TTL.
    start = (TODAY - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
    end = (TODAY + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cache_file = tmp_path / f"AAPL-YFin-data-{start}-{end}.csv"
    pd.DataFrame({"Date": ["2026-07-17"], "Close": [100.0]}).to_csv(cache_file, index=False)
    old = time.time() - STALE
    os.utime(cache_file, (old, old))

    calls = []

    def _fake_download(*a, **k):
        calls.append(1)
        return pd.DataFrame(
            {"Date": pd.to_datetime(["2026-07-17", "2026-07-18"]), "Close": [100.0, 222.0]}
        ).set_index("Date")

    monkeypatch.setattr(su.yf, "download", _fake_download)

    out = su.load_ohlcv("AAPL", TODAY.strftime("%Y-%m-%d"))

    assert calls, "stale same-day cache must trigger a refetch"
    assert 222.0 in out["Close"].values, "refreshed close must reach the caller"


@pytest.mark.unit
def test_load_ohlcv_reuses_fresh_same_day_cache(tmp_path, monkeypatch):
    # Mirror image: a fresh cache must NOT trigger a download.
    monkeypatch.setattr(su, "get_config", lambda: {"data_cache_dir": str(tmp_path)})
    monkeypatch.setattr(su.pd.Timestamp, "today", staticmethod(lambda: TODAY))

    start = (TODAY - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
    end = (TODAY + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    cache_file = tmp_path / f"AAPL-YFin-data-{start}-{end}.csv"
    pd.DataFrame({"Date": ["2026-07-18"], "Close": [100.0]}).to_csv(cache_file, index=False)

    def _fail_download(*a, **k):
        raise AssertionError("fresh cache must not refetch")

    monkeypatch.setattr(su.yf, "download", _fail_download)
    su.load_ohlcv("AAPL", TODAY.strftime("%Y-%m-%d"))


# ---------------------------------------------------------------------------
# Incremental tail fetch (E6): the cache name embeds the window, so every day
# is a "miss" for yesterday's file. A miss must add the missing sessions to the
# history already on disk instead of re-downloading five years for one bar.
# ---------------------------------------------------------------------------


def _seed(tmp_path, rows, name="AAPL-YFin-data-2021-07-19-2026-07-10.csv"):
    f = tmp_path / name
    pd.DataFrame(
        {"Date": pd.to_datetime(rows), "Close": [float(i + 1) for i in range(len(rows))]}
    ).to_csv(f, index=False)
    return f


@pytest.mark.unit
def test_a_missing_cache_tails_off_the_newest_same_symbol_file(tmp_path, monkeypatch):
    monkeypatch.setattr(su, "get_config", lambda: {"data_cache_dir": str(tmp_path)})
    monkeypatch.setattr(su.pd.Timestamp, "today", staticmethod(lambda: TODAY))
    _seed(tmp_path, ["2026-07-08", "2026-07-09", "2026-07-10"])

    calls = []

    def _fake_download(*a, **k):
        calls.append(k)
        return pd.DataFrame(
            {
                "Date": pd.to_datetime(["2026-07-09", "2026-07-10", "2026-07-17", "2026-07-18"]),
                "Close": [11.0, 12.0, 21.0, 22.0],
            }
        ).set_index("Date")

    monkeypatch.setattr(su.yf, "download", _fake_download)
    out = su.load_ohlcv("AAPL", TODAY.strftime("%Y-%m-%d"))

    assert calls, "a miss must still fetch"
    start = pd.Timestamp(calls[0]["start"])
    # The request starts just before the seed's last session, not five years back.
    assert pd.Timestamp("2026-07-04") <= start <= pd.Timestamp("2026-07-10")
    dates = list(out["Date"])
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates)) == 5  # 3 seed rows + 2 new sessions
    # The seed's old row survives, and the freshly downloaded row WINS the two
    # overlapping sessions (de-duplication keeps the later value).
    assert 1.0 in out["Close"].values
    fresh = out.set_index("Date")["Close"]
    assert fresh[pd.Timestamp("2026-07-09")] == 11.0
    assert fresh[pd.Timestamp("2026-07-18")] == 22.0


@pytest.mark.unit
def test_a_full_window_fetch_is_used_when_no_seed_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(su, "get_config", lambda: {"data_cache_dir": str(tmp_path)})
    monkeypatch.setattr(su.pd.Timestamp, "today", staticmethod(lambda: TODAY))

    calls = []

    def _fake_download(*a, **k):
        calls.append(k)
        return pd.DataFrame(
            {"Date": pd.to_datetime(["2026-07-18"]), "Close": [1.0]}
        ).set_index("Date")

    monkeypatch.setattr(su.yf, "download", _fake_download)
    su.load_ohlcv("AAPL", TODAY.strftime("%Y-%m-%d"))

    start = pd.Timestamp(calls[0]["start"])
    assert start == TODAY - pd.DateOffset(years=5)


@pytest.mark.unit
def test_the_tail_fetch_keeps_the_whole_seeded_history(tmp_path, monkeypatch):
    monkeypatch.setattr(su, "get_config", lambda: {"data_cache_dir": str(tmp_path)})
    monkeypatch.setattr(su.pd.Timestamp, "today", staticmethod(lambda: TODAY))
    long_rows = pd.date_range("2026-01-01", "2026-07-10", freq="D")
    _seed(tmp_path, long_rows)

    def _fake_download(*a, **k):
        return pd.DataFrame(
            {"Date": pd.date_range("2026-07-09", "2026-07-18", freq="D"), "Close": [5.0] * 10}
        ).set_index("Date")

    monkeypatch.setattr(su.yf, "download", _fake_download)
    out = su.load_ohlcv("AAPL", TODAY.strftime("%Y-%m-%d"))

    assert len(out) == len(long_rows) + 8  # 2 overlapping sessions collapse
    assert out["Date"].min() == pd.Timestamp("2026-01-01")
    # The merged frame is written under today's canonical name, so the next
    # call in this session is a cache hit.
    assert (tmp_path / f"AAPL-YFin-data-{TODAY - pd.DateOffset(years=5):%Y-%m-%d}-{(TODAY + pd.Timedelta(days=1)):%Y-%m-%d}.csv").exists()


@pytest.mark.unit
def test_an_empty_tail_leaves_the_seed_as_the_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(su, "get_config", lambda: {"data_cache_dir": str(tmp_path)})
    monkeypatch.setattr(su.pd.Timestamp, "today", staticmethod(lambda: TODAY))
    _seed(tmp_path, ["2026-07-17"])

    monkeypatch.setattr(su.yf, "download", lambda *a, **k: pd.DataFrame())
    out = su.load_ohlcv("AAPL", TODAY.strftime("%Y-%m-%d"))

    assert len(out) == 1
    assert out["Close"].iloc[-1] == 1.0
