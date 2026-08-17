"""Value watchlist screener - builds a master list of value candidates.

Usage
-----
    python scripts/value_screener.py AAPL MSFT GOOG -d 2026-06-30
    python scripts/value_screener.py --file universe.txt -d 2026-06-30 --limit 10

For each ticker the screener pulls the configured fundamental vendors
(``moomoo,yfinance`` by default, or whatever ``fundamental_data`` points at)
through ``route_to_vendor``, translates the vendor output into canonical line
items, computes the classic screens, and prints a ranked watchlist table.

Screens (from ``strategies/Math.md``):

* Magic Formula: Earnings Yield = EBIT / EV, Return on Capital (EBIT / invested
  capital) - rank on both.
* Acquirer's Multiple: EV / EBIT (lower is better).
* Piotroski Quality: F-Score >= 7 plus low P/B.
* Shareholder Yield: dividends + buybacks + net debt reduction / market cap.
* Net-Net: market cap < 2/3 * (current assets - total liabilities).
* Fraud / bankruptcy guards: Beneish M-Score, Altman Z-Score.

The screener never fabricates: a missing line item makes the corresponding
screen "n/a" rather than a guessed number.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.dataflows.interface import route_to_vendor  # noqa: E402
from tradingagents.dataflows.quantitative_scores import (  # noqa: E402
    beneish_m_score,
    altman_z_score,
    piotroski_f_score,
    enterprise_value,
    earnings_yield,
    acquirers_multiple,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("value_screener")

# ---------------------------------------------------------------------------
# Vendor-output -> canonical line items
# ---------------------------------------------------------------------------

# Canonical key -> list of substrings that identify the row in vendor output.
_ROW_ALIASES = {
    "revenue": ["total revenue", "revenue", "operating income", "sales"],
    "cogs": ["cost of revenue", "cost of goods sold"],
    "sga": ["selling general", "sg&a", "sga expense"],
    "depreciation": ["depreciation", "depreciation & amortization", "d&a"],
    "operating_income": ["operating income", "ebit", "operating profit"],
    "net_income": ["net income", "net profit", "net income (common)"],
    "interest_expense": ["interest expense", "interest paid"],
    "tax_expense": ["tax provision", "income tax", "tax expense"],
    "cash": ["cash and cash equivalents", "cash & equivalents", "cash & cash"],
    "total_debt": [
        "total debt",
        "total borrowings",
        "long-term debt",
        "long term borrowings",
        "interest-bearing liabilities",
        "total liabilities",  # last-resort fallback only
    ],
    "market_cap": ["market cap", "market capitalization"],
    "total_assets": ["total assets"],
    "total_liabilities": ["total liabilities"],
    "current_assets": ["total current assets", "current assets"],
    "current_liabilities": ["total current liabilities", "current liabilities"],
    "retained_earnings": ["retained earnings"],
    "ppem": ["property plant", "net ppe", "ppe", "fixed assets"],
    "marketable_securities": ["marketable securities", "short-term investments"],
    "net_receivables": ["net receivables", "accounts receivable", "receivables"],
    "operating_cashflow": ["operating cash flow", "cash flow from operating"],
    "dividends_paid": ["cash dividends paid", "dividends paid"],
    "share_buybacks": ["repurchase of common", "share repurchase", "buyback"],
    "debt_repayment": ["repayment of debt", "debt repayment"],
    "capex": ["capital expenditure", "purchase of property"],
}


def _norm(s: str) -> str:
    """Normalize a row label for loose matching."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _match_row(rows: dict, canonical: str):
    """Return the (label, value) for the best matching row, or None.

    Aliases are tried in ``_ROW_ALIASES`` order (most specific first) and the
    first alias that matches any row wins - so ``total_debt`` prefers a
    dedicated debt row over the catch-all ``total_liabilities`` row.
    """
    for alias in _ROW_ALIASES.get(canonical, []):
        key = _norm(alias)
        for label, value in rows.items():
            if key and key in _norm(label):
                return (label, value)
    return None


def _first_number(text: str) -> "float | None":
    """Parse the first number from a formatted value like '$1.23B' or '1,234'."""
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    sign = -1.0 if text.startswith('-') else 1.0
    text = text.lstrip('-+')
    multiplier = 1.0
    for suffix, mult in (("b", 1e9), ("m", 1e6), ("k", 1e3)):
        if text.lower().endswith(suffix):
            multiplier = mult
            text = text[:-1].strip()
            break
    match = re.search(r"[-+]?[0-9][0-9,]*(\.[0-9]+)?([eE][-+]?[0-9]+)?", text)
    if not match:
        return None
    try:
        return sign * multiplier * float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _parse_csv_statements(payload: str) -> dict:
    """Parse a yfinance-style CSV statement into {row_label: latest_value}."""
    rows = {}
    try:
        reader = csv.reader(io.StringIO(payload))
        lines = [row for row in reader if row]
    except Exception:
        return rows
    if not lines:
        return rows
    # First line is the header: first cell is the label column, rest are dates.
    for row in lines[1:]:
        if not row or not row[0]:
            continue
        label = row[0].strip()
        # Pick the rightmost numeric cell (most recent period).
        value = None
        for cell in reversed(row[1:]):
            parsed = _first_number(cell)
            if parsed is not None:
                value = parsed
                break
        rows[label] = value
    return rows


def _parse_markdown_financials(payload: str) -> dict:
    """Parse a moomoo-style markdown table into {row_label: latest_value}."""
    rows = {}
    for line in payload.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0] in ("Item", "---", "Items"):
            continue
        label = cells[0]
        value = _first_number(cells[1]) if len(cells) > 1 else None
        if label and value is not None:
            rows[label] = value
    return rows


def _parse_json_statements(payload: str) -> dict:
    """Parse an alpha_vantage-style JSON payload into {row_label: latest_value}."""
    rows = {}
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return rows
    if not isinstance(data, dict):
        return rows
    for report in data.get("annualReports", []) or data.get("quarterlyReports", []):
        for key, value in report.items():
            if key in ("fiscalDateEnding", "reportedCurrency"):
                continue
            parsed = _first_number(value)
            if parsed is not None and key not in rows:
                rows[key.replace("_", " ")] = parsed
    return rows


def _parse_text_report(payload: str) -> dict:
    """Parse yfinance fundamentals-style text (``Label: value`` lines)."""
    rows = {}
    for line in payload.splitlines():
        if ":" not in line:
            continue
        label, _, rest = line.partition(":")
        parsed = _first_number(rest)
        if label.strip() and parsed is not None:
            rows[label.strip()] = parsed
    return rows


_NON_EQUITY_TOKENS = ("ETF", "ETN", "TRUST", "INDEX", "FUND")


def _is_non_equity(name: str) -> bool:
    """Best-effort flag for non-stock securities (ETFs, ETNs, funds, indices)."""
    upper = (name or "").upper()
    return any(tok in upper for tok in _NON_EQUITY_TOKENS)


def _detect_currency(payload: str) -> str:
    """Best-effort statement-currency detection from vendor payloads.

    moomoo markdown headers carry ``(FY 2025, currency: JPY)``; yfinance
    fundamentals text carries a ``Financial Currency: JPY`` line (when present);
    alpha_vantage JSON carries a ``reportedCurrency`` field. Returns ``""``
    when unknown (yfinance CSV carries no marker).
    """
    text = payload or ""
    for pattern in (
        r"currency:\s*([A-Za-z]{3})",
        r"Financial\s+Currency:\s*([A-Za-z]{3})",
        r"\"reportedCurrency\"\s*:\s*\"([A-Za-z]{3})\"",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return ""


def _canonicalize(payload: str) -> dict:
    """Turn a vendor payload string into a canonical line-item dict.

    Works for yfinance CSV (``get_balance_sheet`` etc.), moomoo markdown
    (``get_fundamentals``), alpha_vantage JSON (``get_fundamentals``) and
    yfinance fundamentals text (``get_fundamentals``). A ``currency`` key is
    added when the payload states a non-default reporting currency, so
    USD-only metrics can refuse to mix currencies.
    """
    text = (payload or "").strip()
    if not text or text.startswith("NO_DATA") or text.startswith("DATA_"):
        return {}
    if text.startswith("|"):
        rows = _parse_markdown_financials(text)
    elif text.lstrip().startswith("{"):
        rows = _parse_json_statements(text)
    elif ":" in text.splitlines()[0] if text.splitlines() else False:
        rows = _parse_text_report(text)
    else:
        rows = _parse_csv_statements(text)
    canonical = {}
    for key in _ROW_ALIASES:
        match = _match_row(rows, key)
        if match is not None:
            canonical[key] = match[1]
    currency = _detect_currency(text)
    if currency and currency != "USD":
        canonical["currency"] = currency
    return canonical


# ---------------------------------------------------------------------------
# Watchlist construction
# ---------------------------------------------------------------------------


def fetch_ticker(ticker: str, curr_date: str) -> dict:
    """Pull the canonical line items for one ticker via the vendor chain."""
    canonical = {}
    # Fundamentals carries market cap (yfinance info / alpha_vantage overview).
    try:
        fund = route_to_vendor("get_fundamentals", ticker, curr_date)
        canonical.update(_canonicalize(fund))
    except Exception as exc:  # noqa: BLE001 - vendor chain already degrades
        logger.warning("%s fundamentals: %s", ticker, exc)
    for method in ("get_balance_sheet", "get_income_statement"):
        try:
            stmt = route_to_vendor(method, ticker, "annual", curr_date)
            canonical.update(_canonicalize(stmt))
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s %s: %s", ticker, method, exc)
    # Guard: a cash figure larger than total assets means a wrong-row match.
    ca_ = canonical.get("cash")
    ta_ = canonical.get("total_assets")
    if ca_ is not None and ta_ is not None and ca_ > ta_:
        canonical["cash"] = None
    # Currency heuristic for ADRs: yfinance reports statements in the local
    # currency (e.g. JPY) with no marker in the CSV, while market cap arrives
    # in USD. A total-assets / market-cap ratio above 1000x only occurs when
    # currencies are mixed (e.g. 303T JPY assets vs 36B USD market cap) - flag
    # it so the USD-only metrics refuse to mix.
    if canonical.get("currency") is None:
        mc = canonical.get("market_cap")
        ta = canonical.get("total_assets")
        if mc and ta and ta / mc > 1000:
            canonical["currency"] = "non_usd"
    # Derive working capital when both sides are available (Altman Z needs it).
    if "working_capital" not in canonical:
        ca = canonical.get("current_assets")
        cl = canonical.get("current_liabilities")
        if ca is not None and cl is not None:
            canonical["working_capital"] = ca - cl
    return canonical


def _usd_consistent(fin: dict) -> bool:
    """True when EV-family screens can mix figures from this ticker.

    moomoo reports ADR statements in the underlying currency (e.g. JPY) while
    market cap arrives in USD - mixing them produces nonsense EV (e.g. JPY cash
    68T minus a USD 36B market cap). Refuse the USD-only metrics unless the
    statements are USD (or currency is unknown/yfinance-style) *and* the
    asset/market-cap scale looks sane.
    """
    if fin.get("currency") not in (None, "", "USD"):
        return False
    mc = fin.get("market_cap")
    ta = fin.get("total_assets")
    if mc and ta and ta / mc > 1000:
        # Only a currency mix produces assets >1000x the market cap.
        return False
    return True


def screen_ticker(ticker: str, fin: dict) -> dict:
    """Compute every screen for one ticker's canonical items."""
    usd = _usd_consistent(fin)
    ev = enterprise_value(fin) if usd else None
    am = acquirers_multiple(fin) if usd else None
    ey = earnings_yield(fin) if usd else None
    m_score = beneish_m_score(fin)
    z_score = altman_z_score(fin) if usd else None
    f_score = piotroski_f_score(fin)
    mc = fin.get("market_cap")
    ca = fin.get("current_assets")
    tl = fin.get("total_liabilities")
    net_net = (
        usd and mc is not None and ca is not None and tl is not None
        and mc < (2.0 / 3.0) * (ca - tl)
    )
    return {
        "ticker": ticker,
        "ev_ebit": round(am, 2) if am is not None else None,
        "earnings_yield": round(ey, 4) if ey is not None else None,
        "ev": round(ev, 2) if ev is not None else None,
        "f_score": f_score,
        "beneish_m": round(m_score, 3) if m_score is not None else None,
        "altman_z": round(z_score, 3) if z_score is not None else None,
        "net_net": net_net,
    }


def rank_watchlist(results: list) -> list:
    """Rank on earnings yield (desc), then EV/EBIT (asc); missing -> end."""
    def key(r):
        ey = r["earnings_yield"] if r["earnings_yield"] is not None else -1.0
        am = r["ev_ebit"] if r["ev_ebit"] is not None else float("inf")
        return (-ey, am)

    return sorted(results, key=key)


def print_watchlist(results: list) -> None:
    """Print the ranked watchlist as a table.

    ``Name`` / ``DayChg`` columns appear only when the run carried mover
    metadata (i.e. the universe came from moomoo's top-losers rank).
    """
    show_name = any(r.get("name") for r in results)
    show_chg = any(r.get("day_change") is not None for r in results)
    heads = ["Rank", "Ticker"]
    if show_name:
        heads.append("Name")
    heads += ["EY", "EV/EBIT", "EV", "F", "M", "Z", "NetNet"]
    if show_chg:
        heads.append("DayChg")
    seps = ["---"] * len(heads)
    header = ("# Value Watchlist "
              f"({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n")
    out = [
        header,
        "| " + " | ".join(heads) + " |",
        "| " + " | ".join(seps) + " |",
    ]
    for i, r in enumerate(results, 1):
        def cell(v, fmt=None):
            if v is None:
                return "n/a"
            return fmt.format(v) if fmt else str(v)

        cells = [str(i), r["ticker"]]
        if show_name:
            cells.append(cell(r.get("name")))
        cells += [
            cell(r["earnings_yield"], "{:.2%}"),
            cell(r["ev_ebit"]),
            cell(r["ev"]),
            cell(r["f_score"]),
            cell(r["beneish_m"]),
            cell(r["altman_z"]),
            "yes" if r["net_net"] else "no",
        ]
        if show_chg:
            cells.append(cell(r.get("day_change"), "{:+.2%}"))
        out.append("| " + " | ".join(cells) + " |")
    print("\n".join(out))


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="*", help="ticker symbols")
    parser.add_argument("-f", "--file", help="file with one ticker per line")
    parser.add_argument("-d", "--date", default=datetime.now().strftime("%Y-%m-%d"),
                        help="current date (yyyy-mm-dd)")
    parser.add_argument("-l", "--limit", type=int, default=50,
                        help="max tickers to process")
    parser.add_argument("-u", "--universe", choices=("tickers", "top-losers", "heat-proxy"),
                        default="tickers",
                        help="symbol source: 'tickers' (positional/file, default), "
                             "'top-losers' (moomoo intraday decliners; refreshes daily) "
                             "or 'heat-proxy' (same as top-losers, US-only - the official "
                             "trade-rank proxy for the proprietary in-app Heat List)")
    parser.add_argument("--market", default="US",
                        help="market key for --universe top-losers/heat-proxy (US/HK)")
    parser.add_argument("-n", "--movers-count", type=int, default=50,
                        help="how many decliners to pull (max 200)")
    parser.add_argument("--min-mcap", type=float, default=1e9,
                        help="market-cap floor (USD); 0 disables")
    parser.add_argument("--price-min", type=float, default=20.0,
                        help="min last price in USD (default 20; 0 disables)")
    parser.add_argument("--pe-max", type=float, default=40.0,
                        help="max P/E (TTM) (default 40; 0 disables)")
    args = parser.parse_args(argv)

    # The proprietary Heat List (search/news/trade telemetry) is app-only and
    # not exposed by any moomoo API; 'heat-proxy' is the sanctioned stand-in
    # (top-movers rank) so the daily losers-of-the-moment list keeps rotating.
    if args.universe == "heat-proxy":
        args.market = "US"

    mover_meta: dict = {}
    tickers = list(args.tickers)
    if args.universe in ("top-losers", "heat-proxy"):
        try:
            from tradingagents.dataflows.moomoo import (
                MoomooNotConfiguredError,
                get_hot_movers_moomoo,
                get_top_movers_moomoo,
            )

            if args.universe == "heat-proxy":
                # Heat-list stand-in: the official hot master (gainers+losers,
                # hottest first), then keep the losers of the moment.
                movers = get_hot_movers_moomoo(
                    count=args.movers_count,
                    market=args.market,
                    min_market_cap=args.min_mcap,
                )
                losers = [
                    m for m in movers
                    if m.get("change_ratio") is not None and m["change_ratio"] < 0
                ]
                movers = losers
            else:
                movers = get_top_movers_moomoo(
                    sort_dir="losers",
                    count=args.movers_count,
                    market=args.market,
                    min_market_cap=args.min_mcap,
                )
            # Equity-only, price >= $20, P/E (TTM) in (0, 40].
            gated = []
            for m in movers[: args.movers_count * 4]:
                if _is_non_equity(m.get("name")):
                    continue
                price = m.get("cur_price")
                pe = m.get("pe_ttm")
                if args.price_min and (price is None or price < args.price_min):
                    continue
                if args.pe_max and (pe is None or not (0.0 < pe <= args.pe_max)):
                    continue
                gated.append(m)
            movers = gated[: args.movers_count]
            if not movers:
                parser.error("no symbols after price/P-E/equity gates")
            for m in movers:
                symbol = (m.get("symbol") or "").upper()
                if not symbol:
                    continue
                tickers.append(symbol)
                if m.get("name") or m.get("change_ratio") is not None:
                    mover_meta[symbol] = {
                        "name": m.get("name"),
                        "day_change": m.get("change_ratio"),
                        "market_cap": m.get("market_cap"),
                    }
            logger.info("top-losers universe: %d symbols from moomoo", len(tickers))
        except MoomooNotConfiguredError as exc:
            parser.error(f"moomoo top-losers unavailable: {exc}")
        except Exception as exc:  # noqa: BLE001 - a universe source must fail loudly
            parser.error(f"moomoo top-losers failed: {exc}")
    elif args.file:
        with open(args.file, encoding="utf-8") as fh:
            tickers += [ln.strip().upper() for ln in fh if ln.strip()]
    if not tickers:
        parser.error("no tickers provided (positional args, --file, or --universe top-losers)")

    results = []
    for ticker in tickers[: args.limit]:
        try:
            fin = fetch_ticker(ticker, args.date)
            meta = mover_meta.get(ticker.upper(), {})
            # The moomoo rank carries market cap per symbol, but moomoo's
            # fundamentals feed (statements) does not - inject it so the EV /
            # earnings-yield / acquirer screens can run on the daily list.
            if fin.get("market_cap") is None and meta.get("market_cap"):
                fin["market_cap"] = meta["market_cap"]
            row = screen_ticker(ticker, fin)
            row["name"] = meta.get("name")
            row["day_change"] = meta.get("day_change")
            results.append(row)
            logger.info("screened %s", ticker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not screen %s: %s", ticker, exc)

    print_watchlist(rank_watchlist(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
