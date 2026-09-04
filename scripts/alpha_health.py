"""Alpha-health monitor - join emitted decisions to realized forward returns.

Usage
-----
    python scripts/alpha_health.py                  # ledger + full monitor
    python scripts/alpha_health.py --ledger          # rebuild ledger only
    python scripts/alpha_health.py --monitor          # monitor only (ledger intact)
    python scripts/alpha_health.py --dates 2026-08-01 2026-09-04
    python scripts/alpha_health.py --horizons 1 5 20 60

Purpose (the market-research material's core diagnostic)
--------------------------------------------------------
When a research system stops emitting Buy/Overweight, is that because the
market got efficient (the signal was arbitraged) or because the scorer became
too conservative (score compression)? This tool answers that empirically:

* It scans ``reports/*/research_decision.json`` for emitted decisions - the
  alpha ledger - and (re)builds ``reports/alpha_ledger.jsonl`` (one JSON row
  per decision, hash-pinned, advisory).
* It joins each row's realized forward returns (1/5/20/60d) from the OHLCV
  vendor chain, then aggregates: score distribution + dispersion, rank IC per
  horizon + ICIR, the alpha-decay curve (does edge accrue with horizon?),
  win rates per rating band, and opportunity counts.

Everything is advisory and never gates. Rows whose forward returns are not
yet realized (a fresh report) simply carry None forward columns and are
excluded from the statistics that need them.

The monitor reads the ledger rows directly; ``--ledger`` re-collects from
``research_decision.json`` (idempotent - rows are replaced by ticker+date).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.strategies.alpha_health import (  # noqa: E402
    attach_forward_returns,
    rating_to_number,
)

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
LEDGER_PATH = REPORTS_DIR / "alpha_ledger.jsonl"


def _load_decisions(reports_dir: Path) -> list[dict]:
    rows = []
    if not reports_dir.is_dir():
        return rows
    for d in sorted(reports_dir.iterdir()):
        if not d.is_dir():
            continue
        f = d / "research_decision.json"
        if not f.is_file():
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - malformed artifact degrades
            continue
        rows.append(
            {
                "ticker": str(doc.get("ticker") or "").upper(),
                "effective_date": str(doc.get("effective_date") or ""),
                "rating": doc.get("rating"),
                "data_quality": doc.get("data_quality") or "unknown",
                "guardrail_reason": doc.get("guardrail_reason"),
                "risk_gate_verdict": (doc.get("risk_gate") or {}).get("verdict"),
                "decision_hash": doc.get("decision_hash"),
                "source": str(f),
            }
        )
    return rows


def _rebuild_ledger(rows: list[dict], path: Path) -> int:
    """Replace the ledger with the fresh rows, deduped by ticker+date."""
    seen: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["ticker"], r["effective_date"])
        if not key[0] or not key[1]:
            continue
        seen[key] = r  # last wins (an emitted row is newer than a legacy one)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in sorted(seen.values(), key=lambda x: (x["effective_date"], x["ticker"])):
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    return len(seen)


def _read_ledger(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:  # noqa: BLE001 - malformed row degrades
            continue
    return rows


def _prices(tickers: list[str], days: int = 320, cache: dict | None = None):
    """Vendor-chain OHLCV ({ticker: {'dates': [...], 'closes': [...]}}) with:

    * a run-local cache so repeated tickers hit once
    * a quiet per-ticker fallback: empty dict on failure (never fabricate)

    Uses the same private chain the analysis tools do (``_ohlcv``), so joins
    are consistent with what the agents actually saw at research time.
    """
    cache = cache if cache is not None else {}
    from tradingagents.agents.utils.analysis_tools import _ohlcv

    out = {}
    for t in tickers:
        if t in cache:
            out[t] = cache[t]
            continue
        oh = _ohlcv(t, days=days)
        cache[t] = oh
        out[t] = oh
    return out


def _monitor_report(rows: list[dict], horizons: tuple[int, ...]) -> dict:
    from tradingagents.strategies.alpha_health import alpha_health_report

    # numeric stance from the rating; forward returns joined below
    sc = []
    for r in rows:
        row = dict(r)
        row.setdefault("score", rating_to_number(r.get("rating")))
        sc.append(row)
    # join forward returns (uses each row's effective_date)
    tickers = sorted({str(r.get("ticker") or "").upper() for r in sc} - {""})
    prices = _prices(tickers)
    joined = []
    for r in sc:
        t = str(r.get("ticker") or "").upper()
        pr = prices.get(t) or {}
        dates, closes = pr.get("dates") or [], pr.get("closes") or []
        fwd = attach_forward_returns([r], dates, closes, horizons=horizons)
        joined.extend(fwd)
    return alpha_health_report(joined, horizons=horizons)


def _render(report: dict) -> str:
    lines = []
    lines.append("ALPHA HEALTH MONITOR")
    lines.append("=" * 56)
    opp = report.get("opportunity_counts") or {}
    lines.append(f"Total signals        {report.get('total_signals', 0)}")
    lines.append(
        "Ratings   "
        + "  ".join(f"{k}:{v}" for k, v in sorted(opp.items()))
    )
    dist = report.get("score_distribution") or {}
    if dist.get("n"):
        lines.append(
            f"Score dist  n={dist['n']} mean={dist.get('mean'):+.2f} "
            f"std={dist.get('std'):.2f} p25={dist.get('p25'):+.2f} "
            f"p75={dist.get('p75'):+.2f} max={dist.get('max'):+.1f}"
        )
    disp = (report.get("score_dispersion") or {})
    per_date = disp.get("per_date") or {}
    lines.append(
        f"Score dispersion      {disp.get('label')} "
        f"(mean per-day std {disp.get('mean_std'):.2f}, {len(per_date)} days)"
    )
    ic = report.get("rank_ic") or {}
    lines.append("Rank IC  " + "  ".join(f"{h}d:{ic.get(h)}" for h in report.get("horizons") or []))
    lines.append(f"ICIR (20d)            {report.get('icir')}")
    decay = report.get("alpha_decay") or {}
    curve = decay.get("curve") or {}
    lines.append(
        "Alpha decay   "
        + "  ".join(f"{h}d:{curve.get(str(h))}" for h in report.get("horizons") or [])
        + f"  [{decay.get('label')}]"
    )
    wr = report.get("horizon_win_rate") or {}
    lines.append("Win rate 20d  " + "  ".join(
        f"{k}:{v.get('win_share'):.0%}" for k, v in sorted((wr.get("20") or {}).items())
    ))
    lines.append("=" * 56)
    lines.append("Advisory: distribution/threshold info, never a gate.")
    return "\n".join(lines)


def main(argv=None) -> int:
    doc = (__doc__ or "").splitlines()
    ap = argparse.ArgumentParser(description=doc[0] if doc else "alpha-health monitor")
    ap.add_argument("--ledger", action="store_true", help="rebuild the ledger from research_decision.json")
    ap.add_argument("--monitor", action="store_true", help="print the monitor only")
    ap.add_argument("--dates", nargs="*", default=None, help="effective-date filter (YYYY-MM-DD)")
    ap.add_argument("--horizons", nargs="*", type=int, default=None, help="forward horizons (default 1 5 20 60)")
    ap.add_argument("--reports", default=str(REPORTS_DIR), help="reports tree root")
    args = ap.parse_args(argv)

    if args.ledger:
        decided = _load_decisions(Path(args.reports))
        n = _rebuild_ledger(decided, LEDGER_PATH)
        print(f"ledger: {n} rows -> {LEDGER_PATH}")

    rows = _read_ledger(LEDGER_PATH)
    if args.dates:
        lo, *rest = args.dates
        hi = rest[0] if rest else None
        rows = [r for r in rows
                if (not lo or str(r.get("effective_date")) >= lo)
                and (not hi or str(r.get("effective_date")) <= hi)]
    if not rows:
        print("no ledger rows - run a report with alpha_ledger_enable=true first, or --ledger to rebuild")
        return 1 if not args.monitor else 0

    horizons = tuple(args.horizons) if args.horizons else (1, 5, 20, 60)
    report = _monitor_report(rows, horizons)
    print(_render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
