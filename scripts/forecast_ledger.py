#!/usr/bin/env python3
"""Publish the registry's realized-volatility forecast into the prediction ledger (plan FL-9).

**Offline by construction, and that is a requirement rather than a preference.**
The forecasting theme's ground rule 8 forbids the decision path
(``prepare_initial_state``, ``finalize_run``, any agent tool) from calling any of
this; design doc §9.1 puts the same boundary around the admitted libraries. So
the one place a ``ForecastRecord`` can honestly be born is here - a script an
operator runs - and this script is also the first caller FL-5's ledger adapter
had, which is what let FL-5 land at all.

It adds no arithmetic. The number comes from
``strategies/long_memory.py::rv_forecast`` through the publisher, and the
identity comes from the sources that already own it:

  * the bars and their date filtering - ``dataflows.stockstats_utils.load_ohlcv``
  * the price caliber - ``dataflows.market_router.price_caliber_for``, asked
    about the loader's actual source, so the answer comes from the repo's
    verified table instead of an assumption
  * the evidence identity - ``agents.utils.prompt_metrics.snapshot_identity``

Usage::

    py -3.12 scripts/forecast_ledger.py --ticker AAPL
    py -3.12 scripts/forecast_ledger.py --ticker AAPL --as-of 2026-10-02 --json
    py -3.12 scripts/forecast_ledger.py --ticker AAPL --as-of 2026-10-02 \\
        --realized 0.00021 --score 0.00021 --benchmark-score 0.00034

Exit codes: 0 published, 2 an input was absent (no bars, no evidence identity),
3 the publisher refused because a provenance value had no true source.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import date

from tradingagents.agents.utils.prompt_metrics import snapshot_identity
from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.market_router import market_for_symbol, price_caliber_for
from tradingagents.dataflows.stockstats_utils import load_ohlcv
from tradingagents.strategies import forecast_contract as fc, forecast_registry as fr
from tradingagents.strategies.forecast_publisher import (
    PublishRefusal,
    publish_realized_volatility_forecast,
)
from tradingagents.strategies.prediction_ledger import (
    evaluate_forecast,
    forecast_rows,
    record_forecast,
)

#: The source ``load_ohlcv`` actually reads: its cache is
#: ``<SYM>-YFin-data-<start>-<end>.csv`` and its download passes
#: ``auto_adjust=True``. The caliber this script states is therefore the verified
#: table's entry for that source - which is why it can be stated at all.
_OHLCV_VENDOR = "y_finance"


def _log_returns(frame) -> list[tuple]:
    """Close-to-close log returns, each dated by the session it ends on.

    ``load_ohlcv`` already filters rows after the requested date, so the series
    is strictly backward and no as-of guard is needed here. A non-positive or
    unreadable close breaks the pair rather than producing a return from it.
    """
    dates = list(frame["Date"])
    closes = list(frame["Close"])
    out: list[tuple] = []
    for i in range(1, len(closes)):
        prev, cur = float(closes[i - 1]), float(closes[i])
        if prev > 0 and cur > 0:
            out.append((dates[i], math.log(cur / prev)))
    return out


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Publish the registry's realized-volatility forecast into the prediction ledger."
    )
    ap.add_argument("--ticker", required=True, help="the symbol to publish a forecast for")
    ap.add_argument("--as-of", default=None, help="session date (default: today)")
    ap.add_argument("--window", type=int, default=None, help="trailing window (default: MEMORY_WINDOW)")
    ap.add_argument("--results-dir", default=None, help="ledger directory (default: ~/.tradingagents/logs)")
    ap.add_argument("--realized", type=float, default=None,
                    help="the realized outcome, to append a ForecastEvaluation")
    ap.add_argument("--score", type=float, default=None, help="the forecast's own score")
    ap.add_argument("--benchmark-score", type=float, default=None, help="the benchmark's score")
    ap.add_argument("--scoring-rule", default="RMSE", choices=sorted(fc.SCORING_RULES))
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    return ap


def _registry_row(producer_id: str):
    return next((r for r in fr.FORECAST_REGISTRY if r.producer_id == producer_id), None)


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    ticker = args.ticker.strip().upper()
    as_of = args.as_of or date.today().isoformat()
    cfg = get_config() or {}

    frame = load_ohlcv(ticker, as_of)
    if frame is None or getattr(frame, "empty", True):
        print(f"no daily bars for {ticker} at {as_of}; nothing to publish", file=sys.stderr)
        return 2
    returns = _log_returns(frame)
    if not returns:
        print(f"{ticker}: no usable close-to-close returns; nothing to publish", file=sys.stderr)
        return 2

    market = market_for_symbol(ticker)
    caliber = price_caliber_for(_OHLCV_VENDOR, market)
    snap = snapshot_identity(
        cfg,
        {"company_of_interest": ticker, "trade_date": as_of, "price_caliber": caliber},
    )
    if not snap.get("snapshot_id") or not snap.get("data_snapshot_hash"):
        print(
            f"{ticker}: the run carries no evidence identity (snapshot_id/data_snapshot_hash); "
            "a record with an invented one would be reproducible against nothing",
            file=sys.stderr,
        )
        return 2
    snapshot_id = f"{snap['snapshot_id']}:{snap['data_snapshot_hash']}"

    try:
        record = publish_realized_volatility_forecast(
            returns,
            data_snapshot_id=snapshot_id,
            price_caliber=caliber,
            market=market,
            window=args.window,
            config=cfg,
        )
    except PublishRefusal as exc:
        print(f"{ticker}: the publisher refused - {exc}", file=sys.stderr)
        return 3

    record_forecast(record, args.results_dir)

    evaluation = None
    if args.realized is not None:
        row = _registry_row(record.producer_id)
        if args.score is None or args.benchmark_score is None or row is None or not row.benchmark_ref:
            print(
                "--realized needs --score, --benchmark-score and a registry row that declares the "
                "benchmark; nothing was scored",
                file=sys.stderr,
            )
            return 2
        evaluation = evaluate_forecast(
            forecast_id=record.forecast_id,
            realized_outcome=args.realized,
            evaluated_as_of=time.time(),
            n_observations=1,
            scoring_rule=args.scoring_rule,
            score=args.score,
            benchmark_ref=row.benchmark_ref,
            benchmark_score=args.benchmark_score,
            results_dir=args.results_dir,
        )

    rows = forecast_rows(args.results_dir)
    summary = {
        "ticker": ticker,
        "as_of": as_of,
        "forecast_id": record.forecast_id,
        "status": record.status,
        "value": record.value,
        "reason_code": record.reason_code,
        "gate": record.gate,
        "data_snapshot_id": record.provenance.data_snapshot_id,
        "price_caliber": caliber,
        "calendar_id": record.provenance.calendar_id,
        "adjusted_prices": record.provenance.adjusted_prices,
        "ledger_records": sum(1 for r in rows if r.get("kind") == "record"),
        "ledger_evaluations": sum(1 for r in rows if r.get("kind") == "evaluation"),
        "evaluated": evaluation is not None,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"{ticker} @ {as_of}: {record.status} ({record.reason_code or 'produced'})")
        print(f"  forecast_id       {record.forecast_id}")
        print(f"  value             {record.value!r}")
        print(f"  data_snapshot_id  {summary['data_snapshot_id']}")
        print(f"  price_caliber     {caliber} -> adjusted_prices={summary['adjusted_prices']}")
        print(f"  ledger            {summary['ledger_records']} record(s), "
              f"{summary['ledger_evaluations']} evaluation(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
