#!/usr/bin/env python3
"""Standalone preferred-income screener — implements Strategies/capital_income.md.

Runs the Global X U.S. High Yield Preferred Index methodology on its own: it
does NOT wire into the trading graph or any agent. It pulls price + dividend
rate + market cap + OHLCV directly from the data providers (yfinance via the
project's safe symbol normalization + the vendor OHLCV chain) and computes:

  1. Liquidity & quality screen  - market cap >= $250M AND 3m ADTV >= $1M
  2. Yield rank                  - indicated yield = annualized dividend / price
                                   -> keep the top 50
  3. Weighting                   - MV-weighted (or equal-weight fallback when
                                   per-issue shares aren't exposed) with the
                                   3% cap + pro-rata renormalization.

Examples:
    py -3.12 scripts/capital_income_screener.py --file Strategies/preferred_universe.txt
    py -3.12 scripts/capital_income_screener.py GS-PD T-PC MS-PK --top 20
    py -3.12 scripts/capital_income_screener.py -f my_list.txt --out-dir preferred_income --json

No graph/agent wiring - pure standalone.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

# scripts/ is not a package; load like the other standalone repo scripts.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.dataflows.interface import route_to_vendor  # noqa: E402
from tradingagents.strategies.capital_income import (  # noqa: E402
    CLASS_CAP,
    CLASS_MAX,
    MIN_ADTV_DOLLARS,
    MIN_MARKET_CAP,
    build_capital_income_plan,
    indicated_yield,
)


def _f(v):
    try:
        if v is None:
            return None
        x = float(v)
        return x if x == x else None  # NaN -> None
    except (TypeError, ValueError):
        return None


def _fetch_ticker_metrics(ticker: str, days: int = 80) -> dict:
    """Pull price, dividend rate, market cap, ADTV dollars for one ticker."""
    import yfinance as yf

    out = {"ticker": ticker, "price": None, "dividend": None,
           "market_cap": None, "adtv_dollars": None, "ok": False, "why": ""}
    try:
        canonical = ticker.strip().upper()
        t = yf.Ticker(canonical)
        info = t.get_info() or {}
        px = _f(t.fast_info.last_price)
        if px is None or px <= 0:
            try:
                h = t.history(period="5d")
                if len(h):
                    px = _f(h["Close"].iloc[-1])
            except Exception:
                px = None
        if px is None or px <= 0:
            out["why"] = "no usable price"
            return out
        out["price"] = px
        out["dividend"] = _f(info.get("dividendRate"))
        out["market_cap"] = _f(info.get("marketCap"))
        try:
            end = datetime.date.today().isoformat()
            start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
            csv = route_to_vendor("get_stock_data", ticker, start, end) or ""
            sum_dv = 0.0
            n = 0
            for line in csv.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.lower().startswith("date,"):
                    continue
                parts = line.split(",")
                if len(parts) < 6:
                    continue
                try:
                    c = float(parts[4])
                    v = float(parts[5])
                except ValueError:
                    continue
                sum_dv += c * v
                n += 1
            if n >= 2:
                out["adtv_dollars"] = sum_dv / n
        except Exception:
            out["adtv_dollars"] = None
        out["ok"] = True
    except Exception as exc:  # noqa: BLE001
        out["why"] = str(exc)[:80]
    return out


def _render_markdown(plan: dict, source: str, top: int) -> str:
    lines = [
        "# Capital Income Screener (Strategies/capital_income.md)",
        "",
        f"- Universe source: {source}",
        f"- Screen: MarketCap >= ${MIN_MARKET_CAP / 1e6:.0f}M && 3m ADTV >= ${MIN_ADTV_DOLLARS / 1e6:.1f}M",
        f"- Selection: top {top} by indicated yield; weighting: "
        + ("equal-weight (per-issue MV n/a)" if plan.get("used_equal_weight") else "market-value")
        + f" with {CLASS_CAP:.0%} cap / {CLASS_MAX:.0%} max",
        "",
        "| Rank | Ticker | Price | Div | Yield% | MktCap | ADTV$ | Liq | Wt |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(plan.get("ranked", []), 1):
        px = "-" if r["price"] is None else f"{r['price']:.2f}"
        div = "-" if r.get("dividend") is None else f"{r['dividend']:.3f}"
        yld = "-" if r.get("yield") is None else f"{r['yield'] * 100:.2f}"
        mv = "-" if r.get("mv") is None else f"{r['mv'] / 1e6:.0f}M"
        adtv = "-" if r.get("adtv") is None else f"{r['adtv'] / 1e6:.2f}M"
        wt = "-" if r.get("weight") is None else f"{r['weight'] * 100:.1f}%"
        liq = "Y" if r.get("liquid") else "n"
        lines.append(
            f"| {i} | {r['ticker']} | {px} | {div} | {yld} | {mv} | {adtv} | {liq} | {wt} |"
        )
    if plan.get("used_equal_weight"):
        lines.append("")
        lines.append(
            "_Note: per-issue market value for preferreds is not exposed by the data "
            "source; weights shown are equal-weight with the 3% cap._"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="*", help="ticker symbols (hyphenated preferreds)")
    parser.add_argument("-f", "--file", default=None, help="file with one ticker per line")
    parser.add_argument("--top", type=int, default=50, help="top-N by yield (default 50)")
    parser.add_argument("--min-mcap", type=float, default=250, help="min market cap in $M (default 250; 0=off)")
    parser.add_argument("--min-adtv", type=float, default=1, help="min ADTV in $M (default 1; 0=off)")
    parser.add_argument("--out-dir", default="preferred_income", help="folder for the saved report")
    parser.add_argument("--dry-run", action="store_true", help="print rows without writing a file")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = parser.parse_args(argv)

    universe = [t.strip().upper() for t in args.tickers if t.strip()]
    if not universe and args.file:
        with open(args.file, encoding="utf-8") as fh:
            universe = [ln.split("#")[0].strip().upper() for ln in fh if ln.strip()]
    universe = [t for t in universe if t]
    if not universe:
        parser.error("no tickers provided (positional args or --file)")

    metas = []
    for t in universe:
        m = _fetch_ticker_metrics(t)
        if m["ok"]:
            m["yield"] = indicated_yield(m.get("dividend"), m.get("price"))
            min_cap = args.min_mcap * 1e6
            min_adtv = args.min_adtv * 1e6
            mc = m.get("market_cap")
            ad = m.get("adtv_dollars")
            m["liquid"] = bool(
                (mc is None and min_cap == 0 or (mc is not None and min_cap == 0) or (mc is not None and mc >= min_cap))
                and (ad is None and min_adtv == 0 or (ad is not None and min_adtv == 0) or (ad is not None and ad >= min_adtv))
            )
        metas.append(m)

    ok = [m for m in metas if m["ok"]]
    tickers = [m["ticker"] for m in ok]
    prices = {m["ticker"]: m["price"] for m in ok}
    dividends = {m["ticker"]: m.get("dividend") for m in ok}
    mv = {m["ticker"]: m.get("market_cap") for m in ok}
    adtv = {m["ticker"]: m.get("adtv_dollars") for m in ok}
    liquid_flags = {m["ticker"]: m.get("liquid", False) for m in ok}

    plan = build_capital_income_plan(
        tickers,
        prices=prices,
        dividends=dividends,
        mv=mv,
        adtv=adtv,
        top=args.top,
        liquid_flags=liquid_flags,
    )

    if args.json:
        print(json.dumps(plan, indent=2, default=str))
        return 0
    md = _render_markdown(plan, source=(args.file or "positional"), top=args.top)
    print(md)
    if not args.dry_run:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file = out / (stamp + ".md")
        file.write_text(md + "\n", encoding="utf-8")
        print(f"\n[screener] saved report to {file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
