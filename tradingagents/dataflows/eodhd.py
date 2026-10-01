"""EODHD optional data vendor: daily OHLCV (EOD Historical Data).

EODHD (https://eodhd.com) is a low-cost end-of-day market data provider. The
``EOD Historical Data - All World`` plan ($19.99/mo) offers 100,000 calls/day
at 1,000 calls/min with 30+ years of daily OHLCV — a strong replacement for
the moomoo K-line quota (100 calls/7 days) that the value screener exhausts.

This module implements the ``get_stock_data`` vendor contract: daily OHLCV as
a CSV string in the same shape yfinance/moomoo produce (``Date,Open,High,Low,
Close,Volume``), so the screener's ``_fetch_ohlcv`` parser and the analyst
tool loops consume it unchanged.

Every function degrades to a typed error (``NoMarketDataError`` /
``VendorRateLimitError`` / ``VendorNotConfiguredError``) so the router falls
through to the next vendor in the chain — EODHD stays an optional layer.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

BASE = "https://eodhd.com/api"
TIMEOUT = 20
_MAX_RETRIES = 2


def eodhd_api_key() -> str | None:
    """API token from config or environment; None when unset."""
    try:
        from tradingagents.dataflows.config import get_config

        key = get_config().get("eodhd_api_key")
    except Exception:
        key = None
    if key:
        return str(key)
    return os.environ.get("EODHD_API_KEY") or os.environ.get("TRADINGAGENTS_EODHD_API_KEY")


def _eodhd_get(
    path: str, params: dict | None = None, *, timeout: float | None = None
) -> dict | list:
    """GET ``BASE/{path}`` with api_token; parsed JSON on success.

    EODHD returns HTTP 200 with a JSON error body (``{"code": ..., "message":
    ...}``) for most failures, and HTTP 429 for rate limits. This helper
    classifies both (raising a typed vendor error) so the router can fall
    through cleanly.

    ``timeout`` overrides the module default for a path measured slower than it
    (``/news-word-weights`` takes ~40 s: see ``_WORD_WEIGHTS_TIMEOUT``). Omitted,
    the default applies.
    """
    import requests as _requests

    key = eodhd_api_key()
    if not key:
        raise VendorNotConfiguredError(
            "EODHD API token is not set. Add EODHD_API_KEY (or "
            "TRADINGAGENTS_EODHD_API_KEY) to .env."
        )
    url = f"{BASE}/{path}"
    query = dict(params or {})
    query["api_token"] = key
    req_timeout = TIMEOUT if timeout is None else timeout
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _requests.get(url, params=query, timeout=req_timeout)
        except Exception as exc:  # noqa: BLE001 - network failure degrades
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"EODHD network error: {exc}") from exc
        if resp.status_code == 429:
            if attempt < _MAX_RETRIES:
                import time

                time.sleep(2 * (attempt + 1))
                continue
            raise VendorRateLimitError(f"EODHD rate limit (429) on {path}")
        if resp.status_code in (401, 403):
            raise VendorNotConfiguredError(
                f"EODHD auth/forbidden (check EODHD_API_KEY): {resp.status_code}"
            )
        if resp.status_code != 200:
            if attempt < _MAX_RETRIES:
                continue
            raise VendorRateLimitError(f"EODHD {path}: status {resp.status_code}")
        try:
            data = resp.json()
        except ValueError:
            raise NoMarketDataError("eodhd", path, detail="non-JSON response") from None
        # EODHD reports errors as a JSON body with a "code" field AND a
        # "message" field (e.g. {"code": 404, "message": "Not found"}). A
        # dict with only a "code" field (no "message") is a normal data
        # payload — e.g. /api/real-time/{ticker} returns {"code": "AAPL.US",
        # "close": ...} where "code" is the ticker symbol, not an error.
        if isinstance(data, dict) and data.get("code") is not None and data.get("message") is not None:
            msg = str(data.get("message") or data.get("code"))
            if "limit" in msg.lower() or "quota" in msg.lower():
                raise VendorRateLimitError(f"EODHD rate limit: {msg}")
            raise NoMarketDataError("eodhd", path, detail=msg)
        return data


def get_stock_data_eodhd(symbol: str, start_date: str, end_date: str) -> str:
    """Daily OHLCV via EODHD's ``/eod/{symbol}`` endpoint, as CSV.

    Matches the yfinance/moomoo CSV shape (``Date,Open,High,Low,Close,Volume``)
    so the screener's ``_fetch_ohlcv`` parser and the analyst tool loops consume
    it unchanged. Raises typed errors on no data / rate limit / bad key so the
    router falls through to the next vendor.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    data = _eodhd_get(
        f"eod/{symbol}",
        {
            "from": start_date,
            "to": end_date,
            "period": "d",
            "fmt": "json",
        },
    )
    if not isinstance(data, list) or not data:
        raise NoMarketDataError(
            symbol, symbol, detail=f"no rows between {start_date} and {end_date}"
        )
    # EODHD returns newest-first; the yfinance/moomoo CSV is oldest-first.
    rows = list(reversed(data))
    lines = ["Date,Open,High,Low,Close,Volume"]
    for r in rows:
        try:
            date = str(r.get("date") or "")[:10]
            o = float(r.get("open"))
            h = float(r.get("high"))
            lo = float(r.get("low"))
            c = float(r.get("close"))
            v = float(r.get("volume") or 0)
        except (TypeError, ValueError):
            continue
        lines.append(f"{date},{o:.2f},{h:.2f},{lo:.2f},{c:.2f},{v:.0f}")
    if len(lines) == 1:
        raise NoMarketDataError(
            symbol, symbol, detail=f"no rows between {start_date} and {end_date}"
        )
    header = (
        f"# Stock data for {symbol} (from {symbol}) from {start_date} to {end_date}\n"
        f"# Total records: {len(rows)}\n"
        f"# Data retrieved via EODHD on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + "\n".join(lines)


def _sentiment_points_eodhd(
    symbol: str, start_date: str, end_date: str
) -> list[dict] | None:
    """Daily aggregated sentiment series from EODHD ``/sentiments``.

    Returns ``[{"date", "score", "n"}]`` with ``score`` centered to [-1, 1]
    (EODHD ``normalized`` is 0..1), or None when the ticker has no rows.
    """
    data = _eodhd_get(
        "sentiments",
        {
            "s": symbol,
            "from": start_date,
            "to": end_date,
            "fmt": "json",
        },
    )
    if not isinstance(data, dict) or not data:
        raise NoMarketDataError(
            symbol, "sentiments",
            detail=f"no sentiment rows between {start_date} and {end_date}",
        )
    want = str(symbol).upper()
    key = want if want in data else None
    if key is None:
        for k in data:
            if str(k).upper().startswith(want) or want.startswith(str(k).upper().split(".")[0]):
                key = k
                break
    if key is None:
        raise NoMarketDataError(
            symbol, "sentiments", detail=f"no rows for {symbol} in response"
        )
    rows = data[key] or []
    out = []
    for r in rows:
        try:
            score = (float(r.get("normalized")) - 0.5) * 2.0
        except (TypeError, ValueError):
            continue
        if not -1.0 <= score <= 1.0:
            continue
        try:
            n = int(r.get("count") or 0)
        except (TypeError, ValueError):
            n = 0
        out.append({"date": str(r.get("date")), "score": score, "n": n})
    return sorted(out, key=lambda d: d["date"]) or None


def get_news_sentiment_eodhd(symbol: str, start_date: str, end_date: str) -> str:
    """Daily news-sentiment series for a ticker via EODHD ``/sentiments``.

    Renders the daily mean (centered to [-1,1]) + 7-day SMA + latest
    innovation + article count — the news-sentiment factor's computed series.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    points = _sentiment_points_eodhd(symbol, start_date, end_date)
    if not points:
        return f"News sentiment unavailable for {symbol} (EODHD)"
    from tradingagents.strategies.sentiment import daily_sentiment_sma

    series = daily_sentiment_sma(points, window=7) or [
        {"date": p["date"], "score": p["score"], "sma_7d": None, "innovation": None, "n": p["n"]}
        for p in points
    ]
    lines = [f"## {symbol} Daily News Sentiment — EODHD (scale -1..1)", ""]
    lines.append("| date | score | sma_7d | innovation | articles |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in series:
        sc = f"{r['score']:+.2f}" if r["score"] is not None else "n/a"
        sma = f"{r['sma_7d']:+.2f}" if r["sma_7d"] is not None else "n/a"
        inn = f"{r['innovation']:+.2f}" if r["innovation"] is not None else "n/a"
        lines.append(f"| {r['date']} | {sc} | {sma} | {inn} | {r['n']} |")
    latest = series[-1]
    # .4f: a computed score's repr leaked 17 digits (0.23340000000000005) into
    # the prompt, and the analysts copy tool numbers verbatim by rule, so it
    # reached report prose (AMZN news.md 2026-09-14). Format at the source.
    score = f"{latest['score']:.4f}" if latest["score"] is not None else "n/a"
    sma = f"{latest['sma_7d']:.4f}" if latest["sma_7d"] is not None else "n/a"
    tail = ["", f"- latest score {score}, 7d SMA {sma}"]
    if latest.get("innovation") is not None:
        tail.append(f"- latest sentiment innovation {latest['innovation']:+.2f}")
    return "\n".join(lines + tail)


def get_news_eodhd(symbol: str, start_date: str, end_date: str) -> str:
    """News for a ticker via EODHD's ``/news`` endpoint (works on the EOD plan).

    Renders each article with headline, date, source, and a content snippet —
    the same shape the other news vendors produce so the analyst tool loops
    consume it unchanged.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    data = _eodhd_get(
        "news",
        {
            "s": symbol,
            "from": start_date,
            "to": end_date,
            "limit": 20,
            "fmt": "json",
        },
    )
    if not isinstance(data, list) or not data:
        return f"No news found for {symbol} from {start_date} to {end_date} (EODHD)"
    lines = [f"## {symbol} News — EODHD", ""]
    for article in data[:20]:
        title = article.get("title") or "(no title)"
        content = article.get("content") or ""
        news_time = str(article.get("date") or "")[:16]
        source = article.get("source") or ""
        if content:
            content = str(content).replace("\n", " ").strip()[:200]
        lines.append(f"- **{title}**  ({news_time} {source})")
        if content:
            lines.append(f"  {content}")
    return "\n".join(lines)


def get_corporate_actions_eodhd(ticker: str) -> str:
    """Dividend history + stock splits via EODHD's ``/div`` and ``/splits``.

    Both endpoints work on the EOD plan. Renders the same shape as the moomoo
    corporate-actions vendor so the analyst tool loops consume it unchanged.
    """
    lines = [f"## Corporate Actions — {ticker} (EODHD)", ""]
    try:
        div = _eodhd_get(f"div/{ticker}", {"fmt": "json"})
        if isinstance(div, list) and div:
            lines.append("### Recent dividends")
            for d in div[-5:]:  # newest last in EODHD's ascending order
                lines.append(
                    f"- {d.get('date', '?')} | ex-date {d.get('date', '?')} "
                    f"| record {d.get('recordDate', '?')} | payable {d.get('paymentDate', '?')} "
                    f"| value {d.get('value', '?')} {d.get('currency', '')}"
                )
    except Exception:  # noqa: BLE001 - dividends degrade independently
        pass
    try:
        sp = _eodhd_get(f"splits/{ticker}", {"fmt": "json"})
        if isinstance(sp, list) and sp:
            lines.append("")
            lines.append("### Stock splits")
            for s in sp[-5:]:
                lines.append(f"- {s.get('date', '?')} | {s.get('split', '?')}")
    except Exception:  # noqa: BLE001 - splits degrade independently
        pass
    if len(lines) == 2:
        raise NoMarketDataError(ticker, ticker, detail="no corporate action data")
    # Forward-split watchlist: announced but not yet in the vendor feed. The
    # SOXX Nov-2026 forward split (iShares filed 2026-08-21; record 11-03,
    # effective after 11-04, split-adjusted trading 11-05) surfaced no vendor
    # row — an upcoming split changes the price/adjustment handling, so it
    # must be disclosed even before the feed catches up.
    _PENDING_SPLITS = {
        "SOXX": "forward split announced 2026-08-21 (record 2026-11-03, "
                "effective after close 2026-11-04, split-adjusted trading "
                "2026-11-05) - vendor row pending",
    }
    note = _PENDING_SPLITS.get((ticker or "").strip().upper())
    if note:
        lines.append("")
        lines.append(f"### Pending corporate actions (announced, not yet in vendor feed)\n- {note}")
    lines.append("")
    lines.append(
        "Interpretation: consistent dividend growth and share buybacks signal "
        "management confidence and shareholder return discipline; splits are "
        "usually cosmetic (note adjustment factors)."
    )
    return "\n".join(lines)


def get_exchange_symbols_eodhd(market: str = "US") -> list[dict]:
    """The full symbol list for an exchange via ``/exchange-symbol-list``.

    Works on the EOD plan (verified: 51,198 US symbols). Returns
    ``[{Code, Name, Country, Exchange, Currency, Type, Isin}]`` so the
    screener can build a universe without the moomoo movers rank.
    """
    data = _eodhd_get(f"exchange-symbol-list/{market}", {"fmt": "json"})
    if not isinstance(data, list) or not data:
        raise NoMarketDataError(market, market, detail="no exchange symbols")
    return data


def get_exchange_symbols_text_eodhd(market: str = "US") -> str:
    """String-rendered symbol list for the routed ``get_exchange_symbols``
    vendor path (the vendor contract requires a string; the raw list form is
    kept for the screener's direct import)."""
    data = get_exchange_symbols_eodhd(market)
    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rows.append(
            "{Code}\t{Name}\t{Country}\t{Exchange}\t{Currency}\t{Type}".format(**item)
        )
    if not rows:
        raise NoMarketDataError(market, market, detail="no exchange symbols")
    return "{Code}\tName\tCountry\tExchange\tCurrency\tType\n" + "\n".join(rows)


def get_market_snapshot_eodhd(ticker: str) -> str:
    """Latest live (15-20 min delayed) OHLCV + change for one ticker.

    Uses ``/api/real-time/{ticker}`` — works on the EOD plan (verified live:
    AAPL returns open/high/low/close/volume/previousClose/change/change_p).
    This is the EODHD replacement for the Massive snapshot (403 on the free
    plan): the market analyst's "latest verified bar" + gap read. Renders the
    same key:value block shape as the Massive snapshot so the tool output is
    interchangeable.
    """
    data = _eodhd_get(f"real-time/{ticker}", {"fmt": "json"})
    if not isinstance(data, dict) or not data.get("code"):
        raise NoMarketDataError(ticker, ticker, detail="no real-time data")
    lines = [f"## {ticker.upper()} Market Snapshot (EODHD)", ""]
    lines.append(
        f"- Last: {data.get('close')} | O {data.get('open')} "
        f"H {data.get('high')} L {data.get('low')} | Volume {data.get('volume')}"
    )
    lines.append(
        f"- Prev close: {data.get('previousClose')} | "
        f"Today's change: {data.get('change')} ({data.get('change_p')}%)"
    )
    return "\n".join(lines)


def get_top_movers_eodhd(direction: str = "gainers", count: int = 10) -> str:
    """Top U.S. market gainers/losers from the bulk real-time feed.

    Uses ``/api/real-time/{ticker}?ex=US`` — one call returns ~18k US stocks
    with live OHLCV + change_p (verified live on the EOD plan). Sorts by
    change_p (desc = gainers, asc = losers) and renders the top ``count``.
    This is the EODHD replacement for the Massive top-movers endpoint (403 on
    the free plan) — a clean, OpenD-independent universe source.
    """
    direction = str(direction).strip().lower()
    if direction not in ("gainers", "losers"):
        return f"invalid direction '{direction}'; use 'gainers' or 'losers'."
    data = _eodhd_get("real-time/US.US", {"ex": "US", "fmt": "json"})
    if not isinstance(data, list) or not data:
        raise NoMarketDataError("US", "US", detail="no real-time bulk data")
    rows = [r for r in data if r.get("change_p") is not None]
    rows.sort(key=lambda r: float(r["change_p"]), reverse=(direction == "gainers"))
    lines = [f"## Top U.S. Market {direction.title()} (EODHD)", ""]
    for row in rows[:count]:
        sym = (row.get("code") or "?").split(".")[0]
        lines.append(f"- {sym}: {row.get('close')} ({row.get('change_p')}%)")
    return "\n".join(lines)



def get_top_movers_symbols_eodhd(
    direction: str = "losers", count: int = 50, min_price: float | None = None
) -> list[dict]:
    """Symbol table behind ``get_top_movers_eodhd`` for machine consumers.

    One ``/api/real-time/US.US`` call returns the whole ~18k-row US feed
    (verified live: no name/type field on rows, so equity-filtering by name is
    impossible here - the caller's own gates must handle ETF/ETN rows). Rows
    are sorted by ``change_p`` in the requested direction and capped at
    ``count``. Each row: ``{symbol, close, change_p}`` with the ``.US`` suffix
    stripped and the per-cent change kept as-is (percent, not ratio) - the
    value screener divides by 100 when it renders ``DayChg``.
    """
    direction = str(direction).strip().lower()
    if direction not in ("gainers", "losers"):
        raise ValueError(
            f"invalid direction '{direction}'; use 'gainers' or 'losers'."
        )
    data = _eodhd_get("real-time/US.US", {"ex": "US", "fmt": "json"})
    if not isinstance(data, list) or not data:
        raise NoMarketDataError("US", "US", detail="no real-time bulk data")
    rows = []
    for r in data:
        cp = r.get("change_p")
        close = r.get("close")
        if cp is None or close is None:
            continue
        if min_price is not None and close < min_price:
            continue
        rows.append(
            {
                "symbol": (str(r.get("code") or "")).split(".")[0].upper(),
                "close": close,
                "change_p": float(cp),
            }
        )
    rows.sort(key=lambda r: r["change_p"], reverse=(direction == "gainers"))
    return rows[:count]


# ---------------------------------------------------------------------------
# Treasury real yields (TIPS) — /ust/real-yield-rates
#
# Nothing else in the tree reads TIPS. Paired with the nominal par curve that
# ``federal_reserve.treasury_curve_points`` already owns, this converts the
# market's inflation expectation from a constant someone assumed into a number
# someone read: ``strategies/dcf.py::wacc_from_beta:28`` is
# ``wacc_from_beta(rf, beta, erp: float = 0.05)`` and its own docstring calls
# 0.05 "the assumed equity risk premium". This endpoint is the missing half.
#
# The vendor IGNORES every query parameter on this path. Probed live
# 2026-09-19: ``year=2026``, ``filter[date]``, ``filter[tenor]`` and
# ``from``/``to`` each returned the identical 895-row body. So the read is
# whole-history and the filtering is CLIENT-SIDE — which is also why no ``year``
# argument is offered: it would silently do nothing.
# ---------------------------------------------------------------------------

_REAL_YIELD_PATH = "ust/real-yield-rates"

# The tenors the vendor actually publishes. TIPS start at 5Y — there is no
# bill-end real yield, and a caller asking for "3M" must be told that rather
# than handed an interpolated number.
REAL_YIELD_TENORS = ("5Y", "7Y", "10Y", "20Y", "30Y")


def _tenor_norm(label: str | None) -> str:
    """Normalise a maturity label to the vendor's tenor form.

    ``"10 Yr"`` (Treasury CSV) and ``"10y"`` (caller input) both become
    ``"10Y"``, so the two legs of the inflation pairing can be joined on one
    key without a hardcoded label table.
    """
    if not label:
        return ""
    return str(label).strip().upper().replace(" YR", "Y").replace(" ", "")


def real_yield_points_eodhd(tenor: str | None = None) -> list[dict]:
    """TIPS real yields from ``/ust/real-yield-rates`` as structured points.

    The single read behind both presentations: ``get_real_yield_rates_eodhd``
    renders these rows for an LLM surface, and ``inflation_expectation_eodhd``
    subtracts against the nominal curve. Returns ``[{date, tenor, rate}]``,
    **oldest-first**, optionally filtered to one ``tenor``.

    The vendor returns the whole history in one call and ignores every filter
    parameter (verified live), so the tenor filter is applied here. A tenor the
    vendor does not publish raises ``NoMarketDataError`` naming it — a missing
    tenor is never interpolated (master rule 1).

    ``rate`` is a **percent** (``2.61`` = 2.61%), matching the vendor's own
    field, and is always a float: a row whose rate will not parse is dropped
    rather than carried as ``0.0``.
    """
    data = _eodhd_get(_REAL_YIELD_PATH, {"fmt": "json"})
    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        raise NoMarketDataError("real-yield-rates", "real-yield-rates",
                                detail="no real-yield rows")

    want = _tenor_norm(tenor)
    points: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_tenor = _tenor_norm(row.get("tenor"))
        if want and row_tenor != want:
            continue
        try:
            rate = float(row.get("rate"))
        except (TypeError, ValueError):
            continue
        points.append({"date": row.get("date"), "tenor": row_tenor, "rate": rate})

    if not points:
        if want:
            raise NoMarketDataError(
                "real-yield-rates", "real-yield-rates",
                detail=f"no rows for tenor '{want}' (published tenors: "
                       f"{', '.join(REAL_YIELD_TENORS)})",
            )
        raise NoMarketDataError("real-yield-rates", "real-yield-rates",
                                detail="no parseable real-yield rows")

    points.sort(key=lambda r: (r.get("date") or "", r.get("tenor") or ""))
    return points


def get_real_yield_rates_eodhd(tenor: str | None = None, *, tail: int | None = None) -> str:
    """Rendered TIPS real-yield curve (EODHD ``/ust/real-yield-rates``).

    The string presentation of ``real_yield_points_eodhd``. Prints the read
    date and the tenor with every row, because **a rate without either is not a
    rate**, plus the coverage it actually achieved.

    ``tail`` bounds the rows rendered without hiding the coverage: the header
    still states the full row count and date span, and a note names how many
    were withheld. A year of daily rows is 179 lines, which is right for a file
    and wrong for a report head — this is the parameter that separates the two
    without giving the caller a second producer.
    """
    points = real_yield_points_eodhd(tenor)

    dates = sorted({p["date"] for p in points if p.get("date")})
    tenors = sorted({p["tenor"] for p in points})
    want = _tenor_norm(tenor)

    lines = [
        "## US Treasury real yields (TIPS) — EODHD /ust/real-yield-rates",
        f"Tenor(s): {', '.join(tenors)} | Rows: {len(points)} | "
        f"Coverage: {dates[0]} to {dates[-1]}" if dates else f"Rows: {len(points)}",
        "",
    ]
    shown = points
    withheld = 0
    if tail is not None and tail > 0 and len(points) > tail:
        shown = points[-tail:]
        withheld = len(points) - tail

    if want:
        # One tenor: the (possibly bounded) series reads as a table.
        lines += ["| Date | Real yield % |", "| --- | --- |"]
        for p in shown:
            lines.append(f"| {p['date']} | {p['rate']} |")
        if withheld:
            lines.append("")
            lines.append(
                f"_(showing the most recent {tail} of {len(points)} rows; "
                f"{withheld} withheld — the header's coverage is the full read)_"
            )
    else:
        # Every tenor: the most recent date reads as a curve, and the rest is a
        # tail so the block stays bounded.
        latest = dates[-1] if dates else None
        lines.append(f"| Tenor | Real yield % | (as of {latest}) |")
        lines.append("| --- | --- | --- |")
        for p in points:
            if p["date"] == latest:
                lines.append(f"| {p['tenor']} | {p['rate']} | |")
        lines.append("")
        lines.append(f"_(most recent date shown; {len(dates)} dates in the returned series)_")

    lines.append("")
    lines.append(
        "Interpretation: a TIPS real yield is the risk-free return net of "
        "expected inflation. It is not comparable to a nominal par yield "
        "without stating which is which — the two differ by the market's "
        "inflation compensation."
    )
    return "\n".join(lines)


def inflation_expectation_eodhd(
    tenor: str = "10Y",
    current_date: str | None = None,
    *,
    real_points: list[dict] | None = None,
    nominal_curve: dict | None = None,
) -> dict:
    """The market's inflation expectation: nominal par yield − TIPS real yield.

    **The single producer of this difference.** Both legs are reads the tree
    already owns — the nominal curve from
    ``federal_reserve.treasury_curve_points`` and the real curve from
    ``real_yield_points_eodhd`` — and the subtraction happens here and nowhere
    else (master rule 15: no derived quantity with two authoritative
    producers). A consumer that needs the premium calls this; it does not
    re-subtract the two series itself.

    ``real_points`` / ``nominal_curve`` accept legs the caller has **already
    fetched**. Both legs are whole-surface reads — one call returns every tenor
    — so a caller pairing five tenors would otherwise re-read the same two
    series five times. Passing them in changes nothing about where the
    subtraction happens; it only stops the caller paying for the same read
    repeatedly.

    Returns a dict that always carries **both legs' dates and the basis**, so a
    reader can tell whether the two were measured on the same day::

        {"tenor", "nominal", "nominal_date", "real", "real_date",
         "expectation", "aligned", "gap_days", "basis", "unavailable"}

    ``aligned`` is False when the legs are from different dates, and
    ``gap_days`` says by how much — the difference is still computed, but it is
    **never returned silently**: a nominal/real subtraction across a stale leg
    is a different number from one across an aligned pair, and the caller has
    to be able to see which it got.

    ``unavailable`` is the reason string when a leg is missing; in that case
    the numeric fields are ``None``. A missing leg is never ``0.0``.
    """
    want = _tenor_norm(tenor)
    basis = (
        f"nominal {want} par yield (home.treasury.gov) - TIPS {want} real "
        f"yield (EODHD {_REAL_YIELD_PATH})"
    )
    result: dict = {
        "tenor": want,
        "nominal": None,
        "nominal_date": None,
        "real": None,
        "real_date": None,
        "expectation": None,
        "aligned": None,
        "gap_days": None,
        "basis": basis,
        "unavailable": None,
    }

    # --- the real leg -----------------------------------------------------
    try:
        if real_points is None:
            real_points = real_yield_points_eodhd(want)
        else:
            real_points = [
                p for p in real_points if _tenor_norm(p.get("tenor")) == want
            ]
        if not real_points:
            raise NoMarketDataError(
                "real-yield-rates", "real-yield-rates",
                detail=f"no supplied rows for tenor '{want}'",
            )
    except Exception as exc:  # noqa: BLE001 - a missing leg is a named gap
        result["unavailable"] = f"real leg unavailable: {exc}"
        return result
    latest_real = real_points[-1]
    result["real"] = latest_real["rate"]
    result["real_date"] = latest_real.get("date")

    # --- the nominal leg --------------------------------------------------
    try:
        if nominal_curve is None:
            from .federal_reserve import treasury_curve_points

            nominal_curve = treasury_curve_points(current_date)
    except Exception as exc:  # noqa: BLE001 - a missing leg is a named gap
        result["unavailable"] = f"nominal leg unavailable: {exc}"
        return result
    result["nominal_date"] = nominal_curve.get("date")

    nominal = None
    for label, value in (nominal_curve.get("points") or {}).items():
        if _tenor_norm(label) == want:
            nominal = value
            break
    if nominal is None:
        result["unavailable"] = (
            f"nominal leg has no {want} maturity "
            f"(published: {', '.join(sorted(nominal_curve.get('points') or {}))})"
        )
        return result
    result["nominal"] = nominal

    # --- the one subtraction ---------------------------------------------
    result["expectation"] = round(nominal - latest_real["rate"], 4)

    nd, rd = result["nominal_date"], result["real_date"]
    if nd and rd:
        try:
            from datetime import date as _date

            gap = abs((_date.fromisoformat(nd) - _date.fromisoformat(rd)).days)
        except ValueError:
            gap = None
        result["gap_days"] = gap
        result["aligned"] = gap == 0
    return result


# ---------------------------------------------------------------------------
# Treasury bill auctions — /ust/bill-rates
#
# A bill curve point is not a note curve point. Bills are discount instruments
# and the endpoint carries auction IDENTITY (`cusip`, `maturity_date`) that no
# other producer in this tree has, alongside the auction's own `discount` /
# `coupon` and their averages. The nominal par curve (`federal_reserve.
# treasury_curve_points`) is the *secondary-market* note curve — it is not a
# substitute for this read, and this read is not a substitute for it.
#
# Like its sibling `/ust/real-yield-rates`, the design measured this path as a
# whole-history read (1,253 rows, 187 KB, one call), so the tenor filter is
# CLIENT-SIDE and no `year` argument is offered (P0 probed that the sibling
# ignores every query parameter — a `year` here would be a parameter that
# silently does nothing, the defect class this repo refuses). No live probe of
# the parameter behaviour on THIS path was made by this build.
# ---------------------------------------------------------------------------

_BILL_PATH = "ust/bill-rates"

# The tenors the vendor publishes for bill auctions. Bills are the short end;
# a note tenor like "10Y" is not a bill and must be named as absent rather than
# interpolated (master rule 1).
BILL_TENORS = ("4WK", "8WK", "13WK", "17WK", "26WK", "52WK")


def _rate_or_none(value) -> float | None:
    """Parse a vendor numeric field; an unparseable value is ``None``, never 0.0.

    A discount/coupon printed as ``0.0`` because the field was missing is a
    fabricated rate (master rule 1). Absent stays absent.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cell(value: float | None) -> str:
    """A numeric table cell: the value, or ``-`` when the field was absent."""
    return "-" if value is None else str(value)


def _bill_auction_points_eodhd(tenor: str | None = None) -> list[dict]:
    """Treasury bill auction rows from ``/ust/bill-rates``, oldest-first.

    The single read behind ``get_bill_auction_rates_eodhd``. Returns
    ``[{date, tenor, discount, coupon, avg_discount, avg_coupon,
    maturity_date, cusip}]``, optionally filtered to one ``tenor`` (client-side,
    as the vendor returns the whole history in one call).

    The numeric fields are **percent** floats or ``None`` — a missing field is
    never defaulted to ``0.0``. ``cusip`` and ``maturity_date`` are the auction
    identity no other producer carries. A tenor the vendor does not publish
    raises ``NoMarketDataError`` naming the published set.
    """
    data = _eodhd_get(_BILL_PATH, {"fmt": "json"})
    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        raise NoMarketDataError("bill-rates", "bill-rates", detail="no bill-auction rows")

    want = _tenor_norm(tenor)
    points: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_tenor = _tenor_norm(row.get("tenor"))
        if want and row_tenor != want:
            continue
        points.append(
            {
                "date": row.get("date"),
                "tenor": row_tenor,
                "discount": _rate_or_none(row.get("discount")),
                "coupon": _rate_or_none(row.get("coupon")),
                "avg_discount": _rate_or_none(row.get("avg_discount")),
                "avg_coupon": _rate_or_none(row.get("avg_coupon")),
                "maturity_date": row.get("maturity_date") or None,
                "cusip": row.get("cusip") or None,
            }
        )

    if not points:
        if want:
            raise NoMarketDataError(
                "bill-rates",
                "bill-rates",
                detail=f"no rows for tenor '{want}' (published tenors: "
                f"{', '.join(BILL_TENORS)})",
            )
        raise NoMarketDataError("bill-rates", "bill-rates", detail="no bill-auction rows")

    points.sort(key=lambda r: (r.get("date") or "", r.get("tenor") or ""))
    return points


def get_bill_auction_rates_eodhd(tenor: str | None = None, *, tail: int | None = None) -> str:
    """Rendered Treasury bill auction detail (EODHD ``/ust/bill-rates``).

    Prints the auction date, the tenor and the auction identity with every row,
    because a bill's ``cusip``/``maturity_date`` are what make it an auction
    rather than a curve point, plus the coverage the read achieved.

    With no ``tenor`` the table is the **current bill curve**: the most recent
    auction for each published tenor, one row each — the shape a report head
    wants. With a ``tenor`` the whole (optionally ``tail``-bounded) series for
    that tenor is rendered, and ``tail`` states how many rows it withheld while
    the header keeps the full coverage.
    """
    points = _bill_auction_points_eodhd(tenor)

    dates = sorted({p["date"] for p in points if p.get("date")})
    tenors = sorted({p["tenor"] for p in points})
    want = _tenor_norm(tenor)

    lines = [
        "## US Treasury bill auctions - EODHD /ust/bill-rates",
        f"Tenor(s): {', '.join(tenors)} | Rows: {len(points)} | "
        f"Coverage: {dates[0]} to {dates[-1]}" if dates else f"Rows: {len(points)}",
        "",
    ]

    if want:
        shown = points
        withheld = 0
        if tail is not None and tail > 0 and len(points) > tail:
            shown = points[-tail:]
            withheld = len(points) - tail
        lines += [
            "| Auction date | Discount % | Coupon % | Avg discount % | Avg coupon % | Maturity | CUSIP |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for p in shown:
            lines.append(
                f"| {p['date']} | {_cell(p['discount'])} | {_cell(p['coupon'])} | "
                f"{_cell(p['avg_discount'])} | {_cell(p['avg_coupon'])} | "
                f"{p['maturity_date'] or '-'} | {p['cusip'] or '-'} |"
            )
        if withheld:
            lines += [
                "",
                f"_(showing the most recent {tail} of {len(points)} rows; "
                f"{withheld} withheld - the header's coverage is the full read)_",
            ]
    else:
        # One row per tenor: the most recent auction of each. Different tenors
        # auction on different days, so each row carries its own date.
        lines += [
            "| Tenor | Latest auction | Discount % | Coupon % | Maturity | CUSIP |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for t in tenors:
            row = next((p for p in reversed(points) if p["tenor"] == t), None)
            if row is None:  # pragma: no cover - tenors come from the points
                continue
            lines.append(
                f"| {t} | {row['date']} | {_cell(row['discount'])} | "
                f"{_cell(row['coupon'])} | {row['maturity_date'] or '-'} | "
                f"{row['cusip'] or '-'} |"
            )
        lines += [
            "",
            f"_(most recent auction per tenor; {len(dates)} auction dates in the returned series)_",
        ]

    lines += [
        "",
        "Interpretation: a bill is a discount instrument - its auction `discount` "
        "rate is not a coupon-equivalent yield, and a bill curve point is not a "
        "note curve point. The nominal par curve is a different read.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Identifier join — /id-mapping
#
# FIGI / LEI / CUSIP have no producer anywhere in this tree. The CIK does:
# ``sec_edgar._cik_for`` resolves a ticker from SEC's own company_tickers.json,
# and SEC is the authoritative registrar for its own identifier. So the vendor's
# ``cik`` field is returned ONLY as a labelled cross-check (`cik_cross_check`)
# and no function here resolves or contributes a CIK — a second CIK path is the
# rule-15 violation the design demotes. `sec_edgar._cik_for` remains the
# authority.
# ---------------------------------------------------------------------------

_ID_MAPPING_PATH = "id-mapping"


def _primary_listing(rows: list[dict], symbol: str | None = None) -> dict | None:
    """Select the primary listing explicitly — never row 0.

    ``filter[isin]`` maps one ISIN to **every** listing of the security (the
    design measured 18 rows for one US ISIN), so taking row 0 would silently
    pick a foreign listing's identifiers. The primary listing is the ``.US``
    one; with no single primary and more than one candidate the read is
    *ambiguous* and yields ``None`` so the caller can say so.
    """
    if symbol:
        want = symbol.strip().upper()
        exact = [
            r for r in rows if str(r.get("symbol") or "").strip().upper() == want
        ]
        if len(exact) == 1:
            return exact[0]
    us = [r for r in rows if str(r.get("symbol") or "").upper().endswith(".US")]
    if len(us) == 1:
        return us[0]
    if len(rows) == 1:
        return rows[0]
    return None


def map_identifiers_eodhd(*, isin: str | None = None, symbol: str | None = None) -> dict:
    """FIGI / LEI / CUSIP for a security (EODHD ``/id-mapping``).

    **FIGI, LEI and CUSIP are the adopted identifiers** — the tree has none of
    the three. Exactly one of ``isin`` or ``symbol`` selects the query
    (``filter[isin]`` / ``filter[symbol]``); anything else is a ``ValueError``,
    because a call with neither would query the whole vendor surface and a call
    with both has no single meaning.

    Returns::

        {"query", "rows", "listing", "isin", "figi", "lei", "cusip",
         "cik_cross_check", "unavailable"}

    ``listing`` is the **primary** listing selected by ``_primary_listing``
    (never row 0 — an ISIN maps to every listing of the security). ``rows`` is
    how many the vendor returned, so a reader can see the selection was made.

    ``cik_cross_check`` is EODHD's own ``cik`` field, printed **only** for
    cross-checking: ``sec_edgar._cik_for`` is the sole authority for a CIK in
    this tree and nothing here resolves or returns one as an identifier. A field
    the chosen listing lacks is ``None``, never ``""`` (master rule 1).

    A vendor failure or an empty/ambiguous response is reported in
    ``unavailable`` with its reason rather than raised, so a caller can print
    the gap.
    """
    if bool(isin) == bool(symbol):
        raise ValueError(
            "map_identifiers_eodhd needs exactly one of isin= or symbol= "
            "(a call with neither queries the whole surface; a call with both "
            "has no single meaning)"
        )
    key = "filter[isin]" if isin else "filter[symbol]"
    value = str(isin or symbol).strip()
    result: dict = {
        "query": {"isin": isin, "symbol": symbol},
        "rows": 0,
        "listing": None,
        "isin": None,
        "figi": None,
        "lei": None,
        "cusip": None,
        "cik_cross_check": None,
        "unavailable": None,
    }

    try:
        data = _eodhd_get(_ID_MAPPING_PATH, {key: value, "fmt": "json"})
    except Exception as exc:  # noqa: BLE001 - a failed read is a named gap
        result["unavailable"] = f"identifier read failed: {exc}"
        return result

    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        result["unavailable"] = f"no identifier rows for {key}={value}"
        return result
    dicts = [r for r in rows if isinstance(r, dict)]
    result["rows"] = len(dicts)

    chosen = _primary_listing(dicts, symbol)
    if chosen is None:
        result["unavailable"] = (
            f"ambiguous: {len(dicts)} listings for {key}={value}, none primary (.US)"
        )
        return result

    result["listing"] = chosen.get("symbol") or None
    for field in ("isin", "figi", "lei", "cusip"):
        result[field] = chosen.get(field) or None
    result["cik_cross_check"] = chosen.get("cik") or None
    return result


# ---------------------------------------------------------------------------
# Batched last session — /eod-bulk-last-day/{EXCHANGE}
#
# This is the SAME producer as ``get_stock_data_eodhd`` (EODHD's own daily
# OHLCV), batched: ONE call returns every symbol on an exchange for one session
# (measured live 2026-10-01: 28,132 US rows for 2026-10-01, ~3.7 s, 6.6 MB). It
# is therefore a **transport**, not a new source — nothing here may become a
# second contributor to a price the tree already reads (master rule 15). Its
# consumer uses it to confirm the session and to cross-check the ranked names
# against the whole exchange's own feed in one call, which is what a transport
# is for.
#
# Rows carry no ``change_p`` and no ``previousClose`` (measured: ``code``,
# ``exchange_short_name``, ``date``, ``open``, ``high``, ``low``, ``close``,
# ``adjusted_close``, ``volume``), so a change needs a second session and is
# deliberately NOT computed here.
# ---------------------------------------------------------------------------

_BULK_LAST_DAY_PATH = "eod-bulk-last-day"


def _bare_symbol(value) -> str:
    """``AAPL.US`` / ``aapl`` -> ``AAPL``; ``""`` for an empty value."""
    return str(value or "").strip().upper().removesuffix(".US")


def get_bulk_last_day_eodhd(exchange: str = "US", date: str | None = None) -> list[dict]:
    """Every symbol on ONE exchange for ONE session, in a single call.

    The raw transport read: the vendor's row list exactly as returned. ``date``
    (``YYYY-MM-DD``) asks for a specific session and is validated **before** the
    call; omitted, the vendor returns its latest completed session. Raises a
    typed error on no data / rate limit / bad key like the other readers here,
    so a router can fall through to the next vendor.
    """
    if date is not None:
        datetime.strptime(date, "%Y-%m-%d")
    params: dict = {"fmt": "json"}
    if date:
        params["date"] = date
    data = _eodhd_get(f"{_BULK_LAST_DAY_PATH}/{exchange}", params)
    if not isinstance(data, list) or not data:
        raise NoMarketDataError(exchange, exchange, detail="no bulk last-day rows")
    return data


def bulk_last_day_index_eodhd(
    exchange: str = "US",
    date: str | None = None,
    symbols: list[str] | None = None,
) -> dict:
    """``{SYMBOL: {date, open, high, low, close, volume}}`` from ONE call.

    The machine form of the batched read. ``symbols`` (optional) restricts the
    index to those tickers and turns the read into a **coverage cross-check**:
    ``covered``/``requested`` say how many of them the exchange feed carried, so
    a caller can see a name that did not print rather than assume it did.

    Returns::

        {"exchange", "session", "rows", "requested", "covered",
         "symbols": {...}, "unavailable"}

    ``session`` is the **row's own** ``date`` (all rows of a response share one —
    measured), not the argument, so a caller that asked for a date the vendor
    ignored is still told what it got. ``rows`` is the vendor's row count.

    A row without a usable ``close`` is **dropped, never zero** (master rule 1),
    and a failed or empty read is reported in ``unavailable`` rather than raised
    — the consumer is a script that prints gaps.
    """
    result: dict = {
        "exchange": exchange,
        "session": None,
        "rows": 0,
        "requested": 0,
        "covered": 0,
        "symbols": {},
        "unavailable": None,
    }
    want: set[str] | None = None
    if symbols:
        want = {_bare_symbol(s) for s in symbols if _bare_symbol(s)}
        result["requested"] = len(want)
    try:
        rows = get_bulk_last_day_eodhd(exchange, date)
    except Exception as exc:  # noqa: BLE001 - a failed read is a named gap
        result["unavailable"] = f"bulk last-day read failed: {exc}"
        return result

    index: dict = {}
    session = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        sym = _bare_symbol(row.get("code"))
        if not sym:
            continue
        close = _rate_or_none(row.get("close"))
        if close is None:
            continue
        if session is None:
            session = str(row.get("date") or "") or None
        if want is not None and sym not in want:
            continue
        index[sym] = {
            "date": str(row.get("date") or "") or None,
            "open": _rate_or_none(row.get("open")),
            "high": _rate_or_none(row.get("high")),
            "low": _rate_or_none(row.get("low")),
            "close": close,
            "volume": _rate_or_none(row.get("volume")),
        }
    result["session"] = session
    result["rows"] = len(rows)
    result["symbols"] = index
    result["covered"] = len(index)
    if not index:
        result["unavailable"] = (
            "no rows in the response"
            if want is None
            else f"none of the {len(want)} requested symbols are in the {exchange} feed"
        )
    return result


# ---------------------------------------------------------------------------
# News term weights — /news-word-weights
#
# A descriptive read of the same vendor surface as ``/sentiments`` (already
# used): the terms driving a symbol's recent news, with their weights. It feeds
# NO score — ``strategies/sentiment`` and ``/sentiments`` own the news-derived
# number — so it is a reference read: printed, never contributed.
#
# MEASURED LATENCY 2026-10-01: ~40 s per call (the vendor aggregates ~300
# articles), well over this module's 20 s default, so the read carries its own
# longer timeout. A caller must budget for it, which is why the screener prints
# it for a bounded number of names.
# ---------------------------------------------------------------------------

_NEWS_WORD_WEIGHTS_PATH = "news-word-weights"
_WORD_WEIGHTS_TIMEOUT = 120


def news_word_weights_eodhd(symbol: str, limit: int = 12) -> dict:
    """Term -> weight for a symbol's recent news, heaviest first.

    Returns::

        {"symbol", "rows", "news_processed", "news_found",
         "terms": [{"term", "weight"}], "unavailable"}

    ``rows`` is how many terms the vendor returned (measured: 100) and
    ``terms`` is the sorted, ``limit``-capped head of them. A term whose weight
    does not parse is **dropped, never 0.0** (master rule 1). ``news_processed``
    / ``news_found`` are the vendor's own coverage counts, carried so a reader
    can see how much news the weights were built from. A failure or an empty
    payload is reported in ``unavailable`` rather than raised, so a caller can
    print the gap.
    """
    sym = _bare_symbol(symbol)
    result: dict = {
        "symbol": sym,
        "rows": 0,
        "news_processed": None,
        "news_found": None,
        "terms": [],
        "unavailable": None,
    }
    if not sym:
        result["unavailable"] = "no symbol given"
        return result
    query = f"{sym}.US"
    try:
        data = _eodhd_get(
            _NEWS_WORD_WEIGHTS_PATH,
            {"s": query, "fmt": "json"},
            timeout=_WORD_WEIGHTS_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 - a failed read is a named gap
        result["unavailable"] = f"word-weight read failed: {exc}"
        return result

    body = data.get("data") if isinstance(data, dict) else None
    meta = data.get("meta") if isinstance(data, dict) else None
    if isinstance(meta, dict):
        result["news_processed"] = meta.get("news_processed")
        result["news_found"] = meta.get("news_found")
    if not isinstance(body, dict) or not body:
        result["unavailable"] = f"no word weights for {query}"
        return result

    result["rows"] = len(body)
    terms = []
    for term, weight in body.items():
        w = _rate_or_none(weight)
        if w is None:
            continue
        terms.append({"term": str(term), "weight": w})
    terms.sort(key=lambda t: t["weight"], reverse=True)
    result["terms"] = terms[: max(0, int(limit))]
    if not terms:
        result["unavailable"] = f"no numeric word weights for {query}"
    return result
