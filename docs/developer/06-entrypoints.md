# 6. Entry points — CLI, build scripts, python API

These are every way a developer / user invokes the system.

## 6.1 `tradingagents` interactive CLI

The typer/rich CLI steps through: ticker -> date -> language -> analysts ->
depth -> provider -> models. Use `py -3.12 -m cli.main` if the console script
isn't installed.

## 6.2 `batch.py` — headless concurrent runner

```
py -3.12 batch.py --symbols AAPL MSFT 0700.HK BTC-USD --date 2026-08-19 \
     --workers 3 --depth shallow --analysts market news fundamentals --vendor moomoo
```

Flags: `--symbols` (required) `--date` `--workers` (1 = default capped
under moomoo connection limits) `--depth` (shallow/medium/deep -> debate rounds
1/3/5) `--analysts` `--vendor` (default|moomoo|yfinance).

Each symbol gets its own memory file + report folder
`reports/<SYMBOL>_<YYYYMMDD_HHMMSS>/`; a `batch_summary_<ts>.jsonl` is appended.

## 6.3 `pipeline.py` — B2 cross-sectional

```
py -3.12 pipeline.py --universe top-losers --top 5 --workers 3 --depth deep
py -3.12 pipeline.py -f universe.txt --top 5 --date 2026-08-19
py -3.12 pipeline.py AAPL MSFT NVDA --top 3
```

Flags: `--universe` (tickers|top-losers|heat-proxy|top-movers-massive)
`--file` `--top` `--limit` `--market` `--movers-count`
`--min-mcap` `--price-min` `--pe-max` `--workers` `--analysts` `--depth`
`--vendor`.

Outputs `reports/pipeline_<ts>.md` (ranked candidates + per-symbol) and
`.jsonl`.

## 6.4 `scripts/value_screener.py` — the value watchlist

```
py -3.12 scripts/value_screener.py AAPL MSFT GOOG -d 2026-06-30
py -3.12 scripts/value_screener.py --universe top-losers --scan all --alloc
py -3.12 scripts/value_screener.py --file universe.txt --limit 10 --rank composite
```

Flags: `tickers` `-f/--file` `-d/--date` `-l/--limit`
`-u/--universe` `--market` `-n/--movers-count` `--min-mcap` `--price-min`
`--pe-max` `--min-avg-vol` `--min-atr-pct` `--max-mcap`
`--min-eps-yoy` `--min-rev-yoy` `--min-roe` `--sector-rank` `--revision`
`--inst-accum` `--intraday` `--scan`
(value|trend-pullback|breakout|momentum|swing|vcp|value-dip|all)
`--out-dir` `--rank` `--enable-float` `--journal` `--alloc`.

Screens: Magic Formula (EY, EV/EBIT), Acquirer's Multiple, Piotroski F,
Beneish M, Altman Z, Net-Net + trend-pullback / breakout / momentum / swing /
vcp / value-dip scans.

## 6.5 `scripts/*` utilities

- `rebuild_complete_report.py` — re-render a report folder / all.
- `smoke_structured_output.py` — smoke the structured-output path.
- `orderflow_evaluate.py` — L4b ledger win-rate/alpha.
- `evaluate_config_gate.py` — G5 walk-forward/PBO.
- `risk_report.py` — risk audit summary.
- `massive_noi_monitor.py` — WebSocket NOI live monitor app.
- `validate_massive_flat.py` — validate a Massive Flat-File CSV in the folder.

## 6.6 Python API (embedding)

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

cfg = DEFAULT_CONFIG.copy()
ta = TradingAgentsGraph(debug=True, config=cfg)
final_state, decision = ta.propagate("NVDA", "2026-08-19")
ta.save_reports(final_state, "NVDA")
```

Pass an explicit `save_path` (or use batch) to write under `./reports/`.

Continue to [`07-persistence.md`](07-persistence.md).