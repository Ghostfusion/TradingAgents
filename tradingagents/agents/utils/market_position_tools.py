"""Market-positioning and filing tools (free data sources)."""
import re
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor

_REPURCHASE_KEY = re.compile(r"(?i)repurchase|buyback|treasury\s+stock")
_SHARE_ROW = re.compile(r"(?i)ordinary\s*shares?\s*number|share\s*issued|shares?\s*outstanding")


def _row_series(rows: "list[tuple[str, list[float]]]", key_re: re.Pattern) -> list[float]:
    for key, values in rows:
        if key_re.search(key):
            return values
    return []


def _parse_statement_rows(text: str) -> "list[tuple[str, list[float]]]":
    """CSV-style vendor rows -> [(key, [period values ...]), ...]."""
    out = []
    for line in text.splitlines():
        parts = line.split(",")
        if len(parts) < 2:
            continue
        key = parts[0].strip()
        if not key:
            continue
        nums = []
        for p in parts[1:]:
            p = p.strip()
            if not p:
                continue
            try:
                nums.append(float(p.replace(",", "")))
            except ValueError:
                nums.append(0.0)
        out.append((key, nums))
    return out


@tool
def get_share_buyback_authorization(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """Share-repurchase activity from the vendor cash-flow/balance-sheet rows.

    Reports (a) the trailing four-quarter repurchase spend and (b) the
    trailing-four-quarter change in ordinary shares outstanding, when the
    vendor statement exposes the rows (row names vary: repurchase / buyback /
    treasury-stock rows on the cash-flow statement; ordinary-shares /
    shares-issued on the balance sheet).

    The REMAINING buyback AUTHORIZATION is a company-disclosure item (8-K /
    management announcement) that vendor financial statements do NOT carry -
    this tool never quotes a remaining-authorization number and states so
    explicitly, so the analyst reports it as unavailable rather than guessing.

    Use before any 'buybacks / share-purchase / capital-return' claim so the
    insider-selling narrative is balanced against actual corporate repurchases.
    """
    try:
        cf = route_to_vendor("get_cashflow", ticker, "quarterly", curr_date)
        bs = route_to_vendor("get_balance_sheet", ticker, "quarterly", curr_date)
    except Exception as exc:  # noqa: BLE001 - advisory tool, degrade
        return f"share buyback data unavailable for {ticker}: {exc}"

    rows_cf = _parse_statement_rows(cf or "") if cf else []
    rows_bs = _parse_statement_rows(bs or "") if bs else []

    repurch = _row_series(rows_cf, _REPURCHASE_KEY)
    sh = _row_series(rows_bs, _SHARE_ROW)

    lines = [f"## Share buyback / capital return — {ticker}"]
    if repurch:
        trailing = [v for v in repurch[:4] if v is not None]
        if trailing:
            total = sum(trailing)
            vals = ", ".join(f"{v/1e6:,.0f}M" for v in trailing)
            lines.append(
                f"- Repurchase row (cash-flow, latest period first): {vals} "
                f"=> trailing 4Q repurchase spend {total/1e6:,.0f}M "
                "(vendor sign convention: negative = cash outflow)"
            )
        else:
            lines.append("- Repurchase row present but no numeric quarters")
    else:
        lines.append("- No repurchase/buyback row in the vendor cash-flow statement.")

    if sh:
        nums = [v for v in sh[:5] if v is not None]
        if len(nums) >= 2:
            delta = nums[0] - nums[-1]
            lines.append(
                f"- Ordinary shares (latest {nums[0]:,.0f}): 4-quarter change "
                f"{delta:,.0f} shares ({'' if delta <= 0 else '+'}{delta/1e6:,.1f}M)"
            )
        else:
            lines.append(f"- Ordinary shares row: latest {nums[0]:,.0f} (series too short)")
    else:
        lines.append("- No ordinary-shares row in the vendor balance-sheet.")

    lines.append(
        "- Remaining buyback AUTHORIZATION: company-disclosure item (8-K / "
        "management release) - NOT in the vendor statement feed; report as "
        "unavailable unless the announcement text is quoted verbatim."
    )
    return "\n".join(lines)


@tool
def get_options_chain(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str | None, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve options-market data for a ticker: implied volatility, open
    interest, volume, and the put/call ratio for the nearest-dated expiry.
    Uses the configured options_data vendor.

    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date in yyyy-mm-dd format

    Returns:
        str: A formatted report of implied volatility and put/call positioning
    """
    return route_to_vendor("get_options_chain", ticker, curr_date)


@tool
def get_sec_filings(
    ticker: Annotated[str, "ticker symbol"],
    limit: Annotated[int | None, "Max filings to summarize; omit for a default of 10"] = None,
) -> str:
    """
    Retrieve recent SEC filings for a ticker: primarily SEC EDGAR 8-K (material
    events), 10-K/10-Q (annual/quarterly reports), S-1/S-3 (capital raises), and
    SC 13D/G (stake disclosures).

    **Fallback**: when official SEC EDGAR is unavailable for any reason (HTTP
    403 from SEC fair-access throttling, network failure, no EDGAR record for a
    non-US listing), this falls back to insider filing activity from Massive
    (Form 4 open-market insider transactions), which is a different, narrower
    dataset — the returned text states it is the Massive insider-activity
    fallback so the agent never mistakes Form-4 insider filings for the full
    8-K/10-K set.

    Args:
        ticker (str): Ticker symbol of the company
        limit (int): Max filings to return; omit for a default of 10
        start_date (str): Input for the Massive form-4 fallback window (default:
            one year ago today)
        end_date (str): End of the massive form-4 fallback window (default: today)

    Returns:
        str: SEC EDGAR filings, or a clearly-labelled Massive insider-activity
        fallback, or an explicit unavailable message.
    """
    if limit is None:
        limit = 10
    try:
        result = route_to_vendor("get_sec_filings", ticker, limit)
        # The router returns an explicit sentinel for a clean "no data" (e.g. no
        # CIK / EDGAR record). Treat any sentinel as an EDGAR miss -> fallback.
        if result and result.startswith(("NO_DATA", "DATA_UNAVAILABLE", "DATA_DISABLED")):
            return _sec_filings_massive_fallback(ticker)
        return result
    except Exception as exc:  # noqa: BLE001 - this category raises on primary failure
        _log_sec_fallback(ticker, exc)
        return _sec_filings_massive_fallback(ticker)


def _sec_filings_massive_fallback(ticker: str) -> str:
    """Insider filing activity from Massive when SEC EDGAR is unavailable.

    Returns Form-4 open-market insider transactions over the trailing 365 days,
    clearly labelled so the agent treats it as the insider-activity subset, not
    the full 8-K/10-K filing set. Degrades to an explicit unavailable message
    if Massive also fails (no fabrication).
    """
    from datetime import date, timedelta

    try:
        from tradingagents.dataflows.massive import get_form4_insider_massive

        end = date.today().isoformat()
        start = (date.today() - timedelta(days=365)).isoformat()
        header = (
            f"SEC EDGAR filings unavailable for {ticker.upper()}; showing the "
            "**Massive insider-activity fallback** (Form 4 open-market "
            "transactions — this is NOT the 8-K/10-K/S-1 filing set)."
        )
        body = get_form4_insider_massive(ticker, start, end)
        return f"{header}\n\n{body}"
    except Exception as exc:  # noqa: BLE001 - fallback also degraded
        return (
            f"SEC filings unavailable for {ticker.upper()}: SEC EDGAR failed and "
            f"the Massive insider fallback also had no data ({exc}). Do not "
            f"fabricate filing information."
        )


def _log_sec_fallback(ticker: str, exc: Exception) -> None:
    import logging

    logging.getLogger(__name__).warning(
        "sec_edgar unavailable for %s; falling back to Massive insider filings: %s",
        ticker,
        exc,
    )

@tool
def get_short_interest(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve short-interest and ownership data for a ticker: shares short,
    days-to-cover, short % of float, and insider/institutional ownership.
    Uses the configured short_interest vendor.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: A formatted report of short interest and ownership
    """
    return route_to_vendor("get_short_interest", ticker)


@tool
def get_short_volume(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve daily short-sale volume ratio (% of total volume sold short) for a
    ticker from FINRA/ATS data via Massive.com. Elevated readings indicate
    heavy intraday shorting — a conviction / squeeze signal.

    Args:
        ticker (str): Ticker symbol of the company
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format

    Returns:
        str: A formatted report of daily short-volume ratios
    """
    from tradingagents.dataflows.massive import get_short_volume_massive

    try:
        return get_short_volume_massive(ticker, start_date, end_date)
    except Exception as exc:  # noqa: BLE001
        return f"short volume unavailable for {ticker}: {exc}"


@tool
def get_market_snapshot(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Latest consolidated market snapshot for a stock from Massive.com: latest
    day/minute/prevDay bars, VWAP, today's change, plus quote/trade when the
    plan includes them. A verification-grade read for exact price-level
    claims. Returns an explicit 'unavailable' message when the account plan
    lacks snapshot access.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: snapshot OHLCV/VWAP/change, or an explicit 'unavailable' message
    """
    from tradingagents.dataflows.massive import get_market_snapshot_massive

    def _twelve(tk):
        from tradingagents.dataflows.twelve_data import get_market_snapshot_twelve_data

        return get_market_snapshot_twelve_data(tk)

    def _eodhd(tk):
        from tradingagents.dataflows.eodhd import get_market_snapshot_eodhd

        return get_market_snapshot_eodhd(tk)

    def _tiingo(tk):
        from tradingagents.dataflows.tiingo import get_market_snapshot_tiingo

        return get_market_snapshot_tiingo(tk)

    try:
        out = get_market_snapshot_massive(ticker)
        # Massive returns an explicit 'unavailable' string when the plan lacks
        # snapshot access (403) - fall back to EODHD (EOD plan), then Tiingo's
        # delayed IEX quote, then Twelve Data's realtime quote. Each degrades
        # independently so one outage never aborts the read.
        if out and "unavailable" not in out.lower():
            return out
    except Exception:  # noqa: BLE001 - try the fallbacks below
        pass

    for getter in (_eodhd, _tiingo, _twelve):
        try:
            out = getter(ticker)
            if out and "unavailable" not in out.lower():
                return out
        except Exception:  # noqa: BLE001 - each vendor degrades independently
            continue
    return f"market snapshot unavailable for {ticker}"


@tool
def get_top_movers(
    direction: Annotated[str, "'gainers' or 'losers'"] = "gainers",
    count: Annotated[int | None, "max rows to return; omit for a default of 10"] = None,
) -> str:
    """
    Top U.S. market gainers/losers by snapshot from Massive.com — a clean,
    OpenD-independent universe source. Returns a ranked list of tickers with
    their close and today's % change, or an explicit 'unavailable' message when
    the account plan lacks snapshot access.

    Args:
        direction (str): 'gainers' or 'losers'
        count (int): max rows to render; default 10

    Returns:
        str: a ranked list of top movers, or an explicit 'unavailable' message
    """
    if count is None:
        count = 10
    from tradingagents.dataflows.massive import get_top_movers_massive

    try:
        out = get_top_movers_massive(direction, count)
        # Massive returns an explicit 'unavailable' string when the plan lacks
        # snapshot access (403) - fall back to the EODHD bulk real-time feed
        # (works on the EOD plan) so the movers universe source stays up.
        if out and "unavailable" in out.lower():
            from tradingagents.dataflows.eodhd import get_top_movers_eodhd

            return get_top_movers_eodhd(direction, count)
        return out
    except Exception as exc:  # noqa: BLE001
        try:
            from tradingagents.dataflows.eodhd import get_top_movers_eodhd

            return get_top_movers_eodhd(direction, count)
        except Exception as exc2:  # noqa: BLE001
            return f"top movers unavailable: {exc} / {exc2}"


@tool
def get_liquidity_risk(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str | None, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """Liquidity / price-impact risk read (Strategies/risk2.md).

    Computes Amihud ILLIQ (price impact per dollar traded), float turnover
    (ADV / float shares), the free-float factor (IWF) and a composite
    LIQUID / CAUTION / ILLIQUID verdict from the vendor OHLCV + float +
    shares. Use before any 'liquid enough to trade / thin book / slippage
    risk' claim. Missing inputs render n/a - never fabricated.
    """
    try:
        from tradingagents.strategies.liquidity_risk import (
            amihud_illiquidity,
            float_turnover as _ft,
            free_float_factor as _iwf,
            liquidity_verdict as _lv,
            roll_spread,
        )
    except Exception as exc:  # noqa: BLE001
        return f"liquidity risk unavailable for {ticker}: {exc}"
    try:
        from tradingagents.agents.utils.analysis_tools import _ohlcv
        from tradingagents.dataflows.float_shares import fetch_float_shares
        from tradingagents.dataflows.statement_parsing import fetch_ticker

        ohlcv = _ohlcv(ticker)
        closes = ohlcv.get("closes") or []
        volumes = ohlcv.get("volumes") or []
        illiq = amihud_illiquidity(closes, volumes)
        adv = sum(volumes[-30:]) / len(volumes[-30:]) if len(volumes) >= 30 else None
        float_sh = fetch_float_shares(ticker)
        fin = fetch_ticker(ticker, current_date or "") or {}
        sh = fin.get("shares")
        tot_sh = sh.get("current") if isinstance(sh, dict) else sh
        ft = _ft(adv, float_sh)
        iwf = _iwf(float_sh, tot_sh)
        lv = _lv(illiq, ft, None, iwf=iwf)
        lines = [
            f"liquidity risk {ticker}: verdict={lv['verdict']}",
            f"  illiq={illiq:.4e}" if illiq is not None else "  illiq=n/a",
            f"  float_turnover={ft:.3%}" if ft is not None else "  float_turnover=n/a",
            f"  iwf={iwf:.2%}" if iwf is not None else "  iwf=n/a",
        ]
        spread = None
        if closes and len(closes) >= 60:
            try:
                spread = roll_spread(closes)
            except Exception:  # noqa: BLE001 - degrades to n/a
                spread = None
        lines.append(
            f"  roll_spread={spread:.4f} (px)" if spread is not None else "  roll_spread=n/a"
        )
        if lv["dangers"]:
            lines.append("  dangers: " + "; ".join(lv["dangers"]))
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"liquidity risk unavailable for {ticker}: {exc}"


@tool
def get_crypto_prices(
    ticker: Annotated[str, "crypto symbol (e.g. BTC-USD, ETH-USD)"],
    start_date: Annotated[str, "start date yyyy-mm-dd"],
    end_date: Annotated[str, "end date yyyy-mm-dd"],
) -> str:
    """
    Native crypto OHLCV via Tiingo (free tier): daily open/high/low/close/
    volume for a crypto pair such as BTC-USD or ETH-USD. This is a distinct
    endpoint from the equity ``get_stock_data`` path, giving the market
    analyst a dedicated crypto price source with per-asset volume and an
    explicit 'unavailable' degrade when the feed has no rows (no-fabrication).

    Args:
        ticker (str): Crypto symbol; ``BTC-USD`` / ``ETH-USD`` / ``SOL-USD``.
        start_date (str): Start date in yyyy-mm-dd format.
        end_date (str): End date in yyyy-mm-dd format.

    Returns:
        str: Tinco crypto OHLCV as a Date,Open,High,Low,Close,Volume CSV.
    """
    from tradingagents.dataflows.tiingo import _crypto_code, get_crypto_prices_tiingo

    try:
        return get_crypto_prices_tiingo(_crypto_code(ticker), start_date, end_date)
    except Exception as exc:  # noqa: BLE001 - Tiingo first, then Twelve Data
        try:
            from tradingagents.dataflows.twelve_data import get_crypto_prices_twelve_data

            return get_crypto_prices_twelve_data(ticker, start_date, end_date)
        except Exception as exc2:  # noqa: BLE001 - degrade, never raise in the tool loop
            return f"crypto prices unavailable for {ticker}: {exc} / {exc2}"
