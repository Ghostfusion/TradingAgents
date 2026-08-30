"""Sentiment factor cross-sectional evaluation (News_Sentiment.md §4-§7).

Builds a per-name daily news-sentiment panel (EODHD ``/sentiments`` primary,
GDELT tone fallback) and prices from the vendor chain, then measures whether
the sentiment factor actually predicts:

- rolling Information Coefficient (Pearson + Rank IC, IC-IR, %-positive)
- IC term structure with fitted alpha-decay half-life
- weekly rebalanced quintile long/short (long Q5 / short Q1) net of costs,
  walk-forward OOS split

Optional `--sectors` (CSV ``ticker,sector``) + `--mcap-file` (CSV
``ticker,mcap``) enable sector-neutralization / size-residualization of the
signal before the IC math (without them the report says so — never fabricates
breadth). The eval is advisory: it tells you whether to trust the sentiment
factor and at what cadence; it gates nothing by default.

Output: ``reports/sentiment_factor_<ts>.md`` + ``.jsonl``.

No-fabrication: names with no sentiment coverage are skipped, and the whole
analysis degrades with explicit messages when the universe is too thin
(< 10 names/date) for the cross-sectional pieces.
"""

import argparse
import contextlib
import json
import sys
from datetime import datetime, timedelta

from tradingagents.dataflows.utils import resolve_output_path


def _fetch_points(ticker: str, start: str, end: str) -> list[dict] | None:
    """EODHD /sentiments points, falling back to GDELT native tone."""
    try:
        from tradingagents.dataflows.eodhd import _sentiment_points_eodhd

        pts = _sentiment_points_eodhd(ticker, start, end)
        if pts:
            return pts
    except Exception:  # noqa: BLE001 - fall through
        pass
    try:
        from tradingagents.dataflows.gdelt import _sentiment_points_gdelt

        return _sentiment_points_gdelt(ticker, start, end)
    except Exception:  # noqa: BLE001 - no coverage
        return None


def _fetch_close_map(ticker: str, days: int = 320) -> dict[str, float]:
    """Date -> close map from the vendor chain (EODHD CSV first)."""
    from datetime import datetime as _dt, timedelta as _td

    try:
        from tradingagents.dataflows.interface import route_to_vendor

        end = _dt.now().strftime("%Y-%m-%d")
        start = (_dt.now() - _td(days=days)).strftime("%Y-%m-%d")
        raw = route_to_vendor("get_stock_data", ticker, start, end) or ""
        out = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("date,") or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) >= 6:
                with contextlib.suppress(ValueError):
                    out[parts[0].strip()] = float(parts[4])
        return out
    except Exception:  # noqa: BLE001 - name skipped
        return {}


def _universe_tickers(universe: str, limit: int, tickers: list[str]) -> list[str]:
    if tickers:
        return [t.strip().upper() for t in tickers if t.strip()]
    if universe == "tickers":
        return []
    from tradingagents.dataflows.eodhd import get_exchange_symbols_eodhd

    syms = get_exchange_symbols_eodhd("US") or []
    out = []
    for s in syms:
        code = str(s.get("Code") or s.get("code") or "")
        if not code or "." in code or "^" in code:
            continue
        out.append(code)
        if len(out) >= limit:
            break
    return out


def build_panel(
    tickers: list[str],
    start: str,
    end: str,
    min_days: int = 5,
) -> tuple[dict, dict]:
    """Sentiment panel + price panel (ticker -> aligned lists by date).

    Dates are the union of OHLCV dates; rows are aligned by date index.
    Returns (sentiment_panel, prices_panel); names without >= min_days of
    sentiment coverage are dropped (never fabricated).
    """
    sent: dict = {}
    prices: dict = {}
    for t in tickers:
        close_map = _fetch_close_map(t, days=320)
        if len(close_map) < 40:
            continue
        pts = _fetch_points(t, start, end)
        if not pts:
            continue
        by_date = {p["date"]: p["score"] for p in pts}
        common = sorted(set(close_map) & set(by_date))
        if len(common) < min_days:
            continue
        sent[t] = [by_date[d] for d in common]
        prices[t] = [close_map[d] for d in common]
    return sent, prices


def run_eval(
    tickers: list[str],
    start: str,
    end: str,
    horizons: tuple = (1, 3, 5, 10),
    holding: int = 5,
    fees_bps: float = 10.0,
    oos_split: float = 0.3,
    sectors: dict | None = None,
    mcap: dict | None = None,
) -> dict:
    """Run the cross-sectional sentiment-factor evaluation; return the report dict."""
    from tradingagents.strategies import sentiment_research as sr

    sent, prices = build_panel(tickers, start, end)
    if len(sent) < 10:
        return {
            "ok": False,
            "universe": len(tickers),
            "covered": len(sent),
            "message": (
                "insufficient sentiment coverage for cross-sectional analysis "
                f"({len(sent)}/ {len(tickers)} names; need >= 10)"
            ),
        }
    signals = sent
    if sectors and mcap:
        signals = sr.residualize_sentiment(sent, mcap, sectors, min_assets=10)
    elif sectors:
        signals = sr.sector_neutral_z(sent, sectors)
    ic = sr.rolling_information_coefficient(signals, prices, holding=holding, min_assets=10)
    ts = sr.ic_term_structure(signals, prices, max_horizon=max(horizons), min_assets=10)
    q = sr.quintile_long_short(
        signals, prices, rebalance="weekly", cost_bps=fees_bps, oos_split=oos_split
    )
    return {
        "ok": True,
        "universe": len(tickers),
        "covered": len(sent),
        "neutralization": "size+sector" if (sectors and mcap) else ("sector" if sectors else "none"),
        "rolling_ic": ic,
        "term_structure": ts,
        "quintile": q,
    }


def _render(report: dict, date_str: str) -> str:
    if not report.get("ok"):
        return (
            f"# Sentiment Factor Evaluation ({date_str})\n\n"
            f"**{report.get('message', 'unavailable')}** — universe "
            f"{report.get('universe', 0)} names, {report.get('covered', 0)} with "
            "sentiment coverage.\n"
        )
    lines = [
        f"# Sentiment Factor Evaluation ({date_str})",
        "",
        f"- Universe: {report['universe']} names; {report['covered']} with "
        f"sentiment coverage (EODHD -> GDELT)",
        f"- Neutralization: {report['neutralization']}",
        "",
        "## Rolling Information Coefficient (holding "
        f"{report['rolling_ic'].get('metrics', {}).get('periods', '?')} periods)",
        "",
    ]
    m = report["rolling_ic"]["metrics"]
    for k in ("mean_rank_ic", "mean_pearson_ic", "ic_ir", "pct_positive", "t_stat", "p_value", "periods"):
        if k in m:
            lines.append(f"- {k}: {m[k]}")
    lines += ["", "## IC term structure / alpha decay", ""]
    if report["term_structure"]:
        lines.append("| horizon | mean rank IC | IC-IR | p | periods |")
        lines.append("| --- | --- | --- | --- | --- |")
        for r in report["term_structure"]:
            if "half_life_days" in r:
                continue
            lines.append(
                f"| {r['horizon_days']}d | {r['mean_rank_ic']} | {r['ic_ir']} | "
                f"{r['p_value']} | {r['periods']} |"
            )
        hl = report["term_structure"][-1].get("half_life_days")
        lines.append("")
        lines.append(f"- **Alpha-decay half-life: {hl} days**" if hl else "- Alpha-decay half-life: not fitted")
    else:
        lines.append("- IC term structure unavailable (too few aligned names/date)")
    lines += ["", "## Weekly quintile long/short (net of costs)", ""]
    if report["quintile"]:
        qm = report["quintile"]["metrics"]
        for k in ("annualized_return", "annualized_vol", "sharpe", "max_drawdown", "periods"):
            if k in qm:
                lines.append(f"- {k}: {qm[k]}")
        lines.append(f"- Monotonicity (Q5>Q4>...>Q1 share): {report['quintile'].get('monotonicity')}")
        lines.append(f"- Turnover (share of names changed/period): {report['quintile'].get('turnover')}")
    else:
        lines.append("- Quintile long/short unavailable (too few names/date)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="*", help="ticker symbols (optional; else --universe)")
    parser.add_argument("--universe", choices=("tickers", "eodhd-us"), default="eodhd-us")
    parser.add_argument("-l", "--limit", type=int, default=40, help="max names from the universe")
    parser.add_argument("-d", "--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--look-back", type=int, default=45, help="sentiment window days")
    parser.add_argument("--holding", type=int, default=5, help="IC forward horizon (days)")
    parser.add_argument("--max-horizon", type=int, default=10, help="term-structure max (days)")
    parser.add_argument("--fees-bps", type=float, default=10.0)
    parser.add_argument("--oos-split", type=float, default=0.3, help="in-sample fraction (0..1)")
    parser.add_argument("--sectors", help="CSV file ticker,sector for neutralization")
    parser.add_argument("--mcap-file", help="CSV file ticker,mcap for size residualization")
    args = parser.parse_args(argv)

    end = args.date
    start = (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=args.look_back + 10)).strftime("%Y-%m-%d")
    sectors = None
    mcap = None
    if args.sectors:
        sectors = {}
        with open(args.sectors, encoding="utf-8") as fh:
            for ln in fh:
                p = ln.strip().split(",")
                if len(p) == 2 and p[0]:
                    sectors[p[0].strip().upper()] = p[1].strip()
    if args.mcap_file:
        mcap = {}
        with open(args.mcap_file, encoding="utf-8") as fh:
            for ln in fh:
                p = ln.strip().split(",")
                if len(p) == 2 and p[0]:
                    with contextlib.suppress(ValueError):
                        mcap[p[0].strip().upper()] = [float(p[1])]
    tickers = _universe_tickers(args.universe, args.limit, args.tickers)
    if not tickers:
        print("no tickers (provide positional tickers or --universe eodhd-us)")
        return 2
    report = run_eval(
        tickers,
        start,
        end,
        horizons=tuple(range(1, args.max_horizon + 1)),
        holding=args.holding,
        fees_bps=args.fees_bps,
        oos_split=args.oos_split,
        sectors=sectors,
        mcap=mcap,
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = resolve_output_path("reports")
    md_path = out_dir / f"sentiment_factor_{ts}.md"
    json_path = out_dir / f"sentiment_factor_{ts}.jsonl"
    md_path.write_text(_render(report, end), encoding="utf-8")
    json_path.write_text(
        json.dumps({"date": end, **report}, default=str) + "\n", encoding="utf-8"
    )
    print(_render(report, end))
    print(f"\nwrote {md_path} + {json_path.name}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
