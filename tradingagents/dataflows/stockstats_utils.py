import glob
import logging
import os
import time
from typing import Annotated

import pandas as pd
import yfinance as yf
from stockstats import wrap
from yfinance.exceptions import YFRateLimitError

from .config import get_config
from .symbol_utils import NoMarketDataError, require_symbol
from .utils import safe_ticker_component

logger = logging.getLogger(__name__)

# A vendor's latest OHLCV row this many calendar days before the requested date
# is treated as stale. Generous enough to span long holiday weekends, tight
# enough to catch the year-old frames yfinance occasionally returns (#1021).
MAX_OHLCV_STALE_DAYS = 10

# How long a same-day cache that does not yet reach the requested day may be
# reused before it is refetched (#1150). Short enough that an intraday run picks
# up today's close soon after it publishes, long enough that a day with no bar
# at all (weekend, holiday) cannot trigger a download on every call.
OHLCV_CACHE_TTL_SECONDS = 900


def yf_retry(func, max_retries=3, base_delay=2.0):
    """Execute a yfinance call with exponential backoff on rate limits.

    yfinance raises YFRateLimitError on HTTP 429 responses but does not
    retry them internally. This wrapper adds retry logic specifically
    for rate limits. Other exceptions propagate immediately.
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except YFRateLimitError:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Yahoo Finance rate limited, retrying in {delay:.0f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                raise


def _ensure_date_column(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize the date column to ``Date``.

    Some yfinance builds leave the index unnamed (so ``reset_index()`` yields
    ``index``) or use ``Datetime`` for intraday data. Rename the first
    date-like column so indicators don't silently drop when it isn't ``Date``.
    """
    if "Date" in data.columns:
        return data
    for candidate in ("index", "Datetime", "date"):
        if candidate in data.columns:
            return data.rename(columns={candidate: "Date"})
    return data


def _clean_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize a stock DataFrame for stockstats: parse dates, drop invalid rows, fill price gaps."""
    data = _ensure_date_column(data)
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])

    price_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in data.columns]
    data[price_cols] = data[price_cols].apply(pd.to_numeric, errors="coerce")
    data = data.dropna(subset=["Close"])
    # Forward-fill only. A bfill would pull a leading gap's value from a LATER
    # row, which may be dated after the run's as-of date (this cleaning runs
    # before load_ohlcv's curr_date filter) - future data leaking into a backtest.
    data[price_cols] = data[price_cols].ffill()

    return data


def _coerce_ohlcv_dates(data: pd.DataFrame) -> pd.Series:
    """Return parsed dates from an OHLCV frame, whether Date is a column or the index."""
    if "Date" in data.columns:
        return pd.to_datetime(data["Date"], errors="coerce").dropna()
    # yfinance keeps the dates in the index (a DatetimeIndex, sometimes unnamed).
    if isinstance(data.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(data.index, errors="coerce")).dropna()
    # Fallback: expose the index and look for any date-like column.
    df = data.reset_index()
    for col in ("Date", "Datetime", "date", "index"):
        if col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce").dropna()
            if not parsed.empty:
                return parsed
    return pd.Series(dtype="datetime64[ns]")


def _assert_ohlcv_not_stale(
    data: pd.DataFrame,
    curr_date: str,
    symbol: str,
    canonical: str | None = None,
    *,
    max_stale_days: int = MAX_OHLCV_STALE_DAYS,
) -> None:
    """Reject OHLCV whose latest row is far older than curr_date.

    Raises NoMarketDataError (with a stale-specific detail) so the router treats
    it like any other "no usable data from this vendor" — try the next vendor,
    then emit one clear unavailable signal. Empty frames are left to the
    caller's existing no-data handling; this guards only the dangerous case of
    present-but-stale rows (a vendor returning a year-old frame that would
    otherwise feed wrong prices to the agent, #1021).
    """
    if data is None or data.empty:
        return
    requested = pd.to_datetime(curr_date, errors="coerce")
    if pd.isna(requested):
        return
    requested = requested.normalize()
    dates = _coerce_ohlcv_dates(data)
    if dates.empty:
        return
    latest = dates.max().normalize()
    stale_days = (requested - latest).days
    if stale_days > max_stale_days:
        raise NoMarketDataError(
            symbol,
            canonical,
            f"latest row is {latest.date()}, {stale_days} days before the "
            f"requested {requested.date()} (stale) — refusing to use it",
        )


def _needs_same_day_refresh(data_file, curr_date_dt, today_date) -> bool:
    """Whether a cached frame must be refetched to reflect the requested day.

    The cache file is keyed per day, so without this a run started before the
    day's bar was final keeps serving that snapshot to every later run (#1150).
    Two distinct staleness cases exist for a current-day request: the bar may be
    missing entirely, or present but still in progress — Yahoo publishes a
    partial daily candle during market hours, whose ``Close`` is not the closing
    price. Row inspection cannot tell a partial bar from a final one, so the TTL
    governs every current-day cache. Historical requests always reuse the cache,
    since those rows are immutable.
    """
    if curr_date_dt.date() < today_date.date():
        return False
    return time.time() - os.path.getmtime(data_file) > OHLCV_CACHE_TTL_SECONDS


# The cache file name embeds the request window, so yesterday's file is a
# DIFFERENT name today. Re-fetching all five years to add one session threw away
# a perfectly good history: these helpers let a miss tail off the newest file
# already on disk for the same symbol.
_TAIL_OVERLAP_DAYS = 5


def _newest_same_symbol_cache(cache_dir: str, safe_symbol: str, exclude: str) -> str | None:
    """The most recently written cache file for this symbol, or None.

    ``exclude`` (the canonical path for today's window) is skipped: the caller
    only reaches this when that file is missing or unusable. The symbol is
    escaped before globbing so a ticker can never expand into a pattern.
    """
    try:
        candidates = [
            p
            for p in glob.glob(os.path.join(cache_dir, f"{glob.escape(safe_symbol)}-YFin-data-*.csv"))
            if os.path.abspath(p) != os.path.abspath(exclude)
        ]
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda p: os.path.getmtime(p))


def _seed_frame(path: str) -> pd.DataFrame | None:
    """A usable cached frame from ``path``, or None (empty/columnless/poisoned)."""
    try:
        cached = pd.read_csv(path, on_bad_lines="skip", encoding="utf-8")
    except (OSError, ValueError, pd.errors.ParserError):
        return None
    if cached.empty or "Close" not in cached.columns:
        return None
    cleaned = _clean_dataframe(cached)
    if cleaned.empty:
        return None
    return cleaned


def _tail_fetch(
    *,
    canonical: str,
    safe_symbol: str,
    data_file: str,
    cache_dir: str,
    start_date: pd.Timestamp,
    end_str: str,
) -> pd.DataFrame | None:
    """Fetch only the sessions missing from the newest same-symbol cache file.

    Returns the seed MERGED with the freshly downloaded tail (one row per
    session, ascending), writing the merged frame under the canonical name, or
    ``None`` when there is no usable seed - in which case the caller does the
    full-window download. The download window starts a few days before the
    seed's last session so a vendor revision of a recent bar still lands, and
    the fresh row wins the de-duplication.

    An empty tail (a weekend, a holiday, a vendor gap) leaves the seed as the
    answer rather than throwing the history away; the caller's own staleness
    check still decides whether that is acceptable.
    """
    seed_path = _newest_same_symbol_cache(cache_dir, safe_symbol, data_file)
    if not seed_path:
        return None
    seed = _seed_frame(seed_path)
    if seed is None:
        return None
    seed_last = pd.to_datetime(seed["Date"], errors="coerce").max()
    if pd.isna(seed_last):
        return None
    tail_start = max(seed_last - pd.Timedelta(days=_TAIL_OVERLAP_DAYS), start_date)
    downloaded = yf_retry(lambda: yf.download(
        canonical,
        start=tail_start.strftime("%Y-%m-%d"),
        end=end_str,
        multi_level_index=False,
        progress=False,
        auto_adjust=True,
    ))
    tail = _ensure_date_column(downloaded.reset_index()) if downloaded is not None else None
    if tail is None or tail.empty or "Close" not in tail.columns:
        merged = seed
    else:
        merged = pd.concat([seed, _clean_dataframe(tail)], ignore_index=True)
        merged = (
            merged.drop_duplicates(subset=["Date"], keep="last")
            .sort_values("Date")
            .reset_index(drop=True)
        )
    merged.to_csv(data_file, index=False, encoding="utf-8")
    logger.info(
        "OHLCV incremental fetch for %s: seed %s -> %d rows, tail window from %s",
        canonical,
        seed_path,
        len(merged),
        tail_start.date(),
    )
    return merged


def load_ohlcv(symbol: str, curr_date: str) -> pd.DataFrame:
    """Fetch OHLCV data with caching, filtered to prevent look-ahead bias.

    Downloads 5 years of data up to today and caches per symbol. On
    subsequent calls the cache is reused. Rows after curr_date are
    filtered out so backtests never see future prices.
    """
    # Resolve broker/forex symbols (XAUUSD+ -> GC=F) to Yahoo's convention,
    # then reject values that would escape the cache directory when
    # interpolated into the cache filename (e.g. ``../../tmp/x``).
    canonical = require_symbol(symbol)
    safe_symbol = safe_ticker_component(canonical)

    config = get_config()
    curr_date_dt = pd.to_datetime(curr_date)

    # Cache uses a fixed window (5y to today) so one file per symbol.
    today_date = pd.Timestamp.today()
    start_date = today_date - pd.DateOffset(years=5)
    start_str = start_date.strftime("%Y-%m-%d")
    # yfinance ``end`` is EXCLUSIVE; request tomorrow so today's row is included
    # when curr_date is the current day (#986). Look-ahead is still prevented by
    # the curr_date filter below.
    end_str = (today_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    os.makedirs(config["data_cache_dir"], exist_ok=True)
    data_file = os.path.join(
        config["data_cache_dir"],
        f"{safe_symbol}-YFin-data-{start_str}-{end_str}.csv",
    )

    # A cached file may be empty if a prior fetch failed (unknown symbol,
    # transient rate limit). Treat an empty/columnless cache as a miss and
    # re-fetch rather than serving the poisoned file forever.
    data = None
    if os.path.exists(data_file):
        cached = pd.read_csv(data_file, on_bad_lines="skip", encoding="utf-8")
        # Serve the cache only when it is usable and not a stale snapshot of the
        # day being requested (#1150); otherwise fall through and refetch.
        if (
            not cached.empty
            and "Close" in cached.columns
            and not _needs_same_day_refresh(data_file, curr_date_dt, today_date)
        ):
            data = cached

    if data is None:
        # Tail off the newest same-symbol cache file when one exists: the
        # history it holds is still valid, so only the sessions since its last
        # row need fetching (with a small overlap, and de-duplicated keeping the
        # fresh row). Falls through to the full window when there is no seed or
        # the seed cannot be read.
        data = _tail_fetch(
            canonical=canonical,
            safe_symbol=safe_symbol,
            data_file=data_file,
            cache_dir=config["data_cache_dir"],
            start_date=start_date,
            end_str=end_str,
        )

    if data is None:
        downloaded = yf_retry(lambda: yf.download(
            canonical,
            start=start_str,
            end=end_str,
            multi_level_index=False,
            progress=False,
            auto_adjust=True,
        ))
        downloaded = _ensure_date_column(downloaded.reset_index())
        # Only cache real data — never persist an empty frame.
        if downloaded.empty or "Close" not in downloaded.columns:
            raise NoMarketDataError(
                symbol, canonical, "Yahoo Finance returned no rows"
            )
        downloaded.to_csv(data_file, index=False, encoding="utf-8")
        data = downloaded

    data = _clean_dataframe(data)

    # Filter to curr_date to prevent look-ahead bias in backtesting
    data = data[data["Date"] <= curr_date_dt]

    # Reject a stale frame (latest row far older than curr_date) rather than
    # feeding year-old prices into indicators (#1021).
    _assert_ohlcv_not_stale(data, curr_date, symbol, canonical)

    return data


def filter_financials_by_date(data: pd.DataFrame, curr_date: str) -> pd.DataFrame:
    """Drop financial statement columns (fiscal period timestamps) after curr_date.

    yfinance financial statements use fiscal period end dates as columns.
    Columns after curr_date represent future data and are removed to
    prevent look-ahead bias.
    """
    if not curr_date or data.empty:
        return data
    cutoff = pd.Timestamp(curr_date)
    mask = pd.to_datetime(data.columns, errors="coerce") <= cutoff
    return data.loc[:, mask]


class StockstatsUtils:
    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
    ):
        data = load_ohlcv(symbol, curr_date)
        df = wrap(data)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        curr_date_str = pd.to_datetime(curr_date).strftime("%Y-%m-%d")

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date_str)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"
