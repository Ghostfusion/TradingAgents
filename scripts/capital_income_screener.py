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
    py -3.12 scripts/capital_income_screener.py --universe preferred-top   # live ETF top-preferreds
    py -3.12 scripts/capital_income_screener.py --universe preferred-top --refresh  # update the file

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
from tradingagents.strategies.fixed_income import (  # noqa: E402
    dv01,
    macaulay_duration,
    modified_duration,
    preferred_ytm,
)

# Preferred-stock ETFs whose top holdings are the live universe seed (path 3:
# no curated list needed - the screener pull the names at runtime).
PREFERRED_ETFS = ("PFF", "PFFD", "PGF", "PGX", "PFFV")


def fetch_preferred_top(max_per_etf: int = 8) -> list[str]:
    """Collect the top holdings of the major preferred ETFs as a live universe.

    Uses yfinance ``get_funds_data().top_holdings`` (free, no key) and returns
    the union of the symbols (deduped, uppercased). These are the actual
    preferred issues the ETFs hold today; the screener then validates each as
    it screens (price + dividendRate).
    """
    import yfinance as yf

    seen: dict[str, int] = {}
    for etf in PREFERRED_ETFS:
        try:
            fd = yf.Ticker(etf).get_funds_data()
            th = fd.top_holdings
            for sym in list(th.index)[: max_per_etf]:
                s = str(sym).strip().upper()
                if s and not s.startswith("X") and not s.endswith("$"):
                    seen[s] = seen.get(s, 0) + 1
        except Exception:  # noqa: BLE001 - a failed ETF must not abort
            continue
    return sorted(seen.keys())


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


def _render_markdown(plan: dict, source: str, top: int, fi: bool = False, fi_horizon: float | None = None) -> str:
    lines = [
        "# Capital Income Screener (Strategies/capital_income.md)",
        "",
        f"- Universe source: {source}",
        f"- Screen: MarketCap >= ${MIN_MARKET_CAP / 1e6:.0f}M && 3m ADTV >= ${MIN_ADTV_DOLLARS / 1e6:.1f}M",
        f"- Selection: top {top} by indicated yield; weighting: "
        + ("equal-weight (per-issue MV n/a)" if plan.get("used_equal_weight") else "market-value")
        + f" with {CLASS_CAP:.0%} cap / {CLASS_MAX:.0%} max",
        "",
    ]
    if fi:
        lines.append("| Rank | Ticker | Price | Div | Yield% | MktCap | ADTV$ | Liq | Wt | YTM% | DMod | DV01 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    else:
        lines.append("| Rank | Ticker | Price | Div | Yield% | MktCap | ADTV$ | Liq | Wt |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for i, r in enumerate(plan.get("ranked", []), 1):
        px = "-" if r["price"] is None else f"{r['price']:.2f}"
        div = "-" if r.get("dividend") is None else f"{r['dividend']:.3f}"
        yld = "-" if r.get("yield") is None else f"{r['yield'] * 100:.2f}"
        mv = "-" if r.get("mv") is None else f"{r['mv'] / 1e6:.0f}M"
        adtv = "-" if r.get("adtv") is None else f"{r['adtv'] / 1e6:.2f}M"
        wt = "-" if r.get("weight") is None else f"{r['weight'] * 100:.1f}%"
        liq = "Y" if r.get("liquid") else "n"
        if fi:
            ytm = "-"
            dmod = "-"
            dv = "-"
            if r.get("price") is not None and r.get("dividend") is not None:
                yrs = fi_horizon if fi_horizon else None
                ytm_v = preferred_ytm(r["dividend"], r["price"], 100.0, yrs)
                if ytm_v is not None:
                    ytm = f"{ytm_v * 100:.2f}"
                    cash = [{"t": float(yrs), "amount": 100.0}]
                    mac = macaulay_duration(cash, ytm_v)
                    mod = modified_duration(mac, ytm_v)
                    dmod = "-" if mod is None else f"{mod:.2f}"
                    dv_v = dv01(mod, r["price"])
                    dv = "-" if dv_v is None else f"{dv_v:.4f}"
            lines.append(
                f"| {i} | {r['ticker']} | {px} | {div} | {yld} | {mv} | {adtv} | {liq} | {wt} | {ytm} | {dmod} | {dv} |"
            )
        else:
            lines.append(
                f"| {i} | {r['ticker']} | {px} | {div} | {yld} | {mv} | {adtv} | {liq} | {wt} |"
            )
    if plan.get("used_equal_weight"):
        lines.append("")
        lines.append(
            "_Note: per-issue market value for preferreds is not exposed by the data "
            "source; weights shown are equal-weight with the 3% cap._"
        )
    if fi and not fi_horizon:
        lines.append("")
        lines.append(
            "_YTM/DMod/DV01 require a call/redemption horizon: pass `--fi-horizon <years>` "
            "for the ones that have one; perpetuals render n/a (no fabricated YTM)._"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="*", help="ticker symbols (hyphenated preferreds)")
    parser.add_argument("-f", "--file", default=None, help="file with one ticker per line")
    parser.add_argument(
        "--universe",
        choices=("preferred-top",),
        default=None,
        help="'preferred-top': live universe from the top holdings of the major "
        "preferred ETFs (PFF/PFFD/PGF/PGX/PFFV) - validates each at runtime.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="with --universe preferred-top: also write the collected, validated "
        "symbols back into the favorite universe file.",
    )
    parser.add_argument("--top", type=int, default=50, help="top-N by yield (default 50)")
    parser.add_argument("--min-mcap", type=float, default=250, help="min market cap in $M (default 250; 0=off)")
    parser.add_argument("--min-adtv", type=float, default=1, help="min ADTV in $M (default 1; 0=off)")
    parser.add_argument("--out-dir", default="preferred_income", help="folder for the saved report")
    parser.add_argument("--dry-run", action="store_true", help="print rows without writing a file")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    parser.add_argument(
        "--fi",
        action="store_true",
        help="add YTM / modified-duration / DV01 columns from the price + "
        "dividend (requires --fi-horizon for a call/redemption horizon; "
        "perpetuals render n/a - never a fabricated YTM)",
    )
    parser.add_argument(
        "--fi-horizon",
        type=float,
        default=None,
        help="years to call/redemption for the YTM/duration columns (required "
        "for meaningful fixed-income reads; perpetuals without one stay n/a)",
    )
    args = parser.parse_args(argv)

    universe = [t.strip().upper() for t in args.tickers if t.strip()]
    if args.universe == "preferred-top":
        universe = fetch_preferred_top()
    elif not universe and args.file:
        with open(args.file, encoding="utf-8") as fh:
            universe = [ln.split("#")[0].strip().upper() for ln in fh if ln.strip()]
    universe = [t for t in universe if t]
    if not universe:
        parser.error("no tickers provided (positional args, --file or --universe preferred-top)")

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

    # --refresh: persist the live, validated preferred-top universe back into
    # the favorite file (only the symbols that resolved with a price + div).
    if args.refresh:
        validated = [m["ticker"] for m in ok if m.get("dividend") is not None]
        if validated:
            target = Path(args.file) if args.file else Path(
                __file__).resolve().parents[1] / "Strategies" / "preferred_universe.txt"
            header = (
                "# Preferred-income universe (Strategies/capital_income.md) - "
                "refreshed from the preferred ETF top holdings.\n"
                "# One ticker per line; '#' lines are comments.\n\n"
            )
            target.write_text(
                header + "\n".join(sorted(validated)) + "\n", encoding="utf-8"
            )
            print(f"[refresh] {len(validated)} validated symbols -> {target}")
        else:
            print("[refresh] nothing validated; file unchanged.")

    if args.json:
        print(json.dumps(plan, indent=2, default=str))
        return 0
    source = (
        "preferred-top (live ETF top-holdings)"
        if args.universe == "preferred-top"
        else (args.file or "positional")
    )
    md = _render_markdown(
        plan, source=source, top=args.top, fi=args.fi, fi_horizon=args.fi_horizon
    )
    print(md)
    if not args.dry_run:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file = out / (stamp + ".md")
        file.write_text(md + "\n", encoding="utf-8")
        print(f"\n[screener] saved report to {file}")
    # Close the moomoo context while the process is healthy (see value_screener
    # main()): the SDK's receive thread keeps the process alive after main()
    # returns, and closing at interpreter exit can block.
    try:
        from tradingagents.dataflows.moomoo import close_context

        close_context()
    except Exception:  # noqa: BLE001 - closing is best-effort
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
