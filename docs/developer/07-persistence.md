# 7. Persistence & recovery

These are the on-disk pieces that survive a run.

## 7.1 Memory log

- Location: `~/.tradingagents/memory/trading_memory.md` (or
  `TRADINGAGENTS_MEMORY_LOG_PATH`). Batch symbols get per-symbol memory files.
- `TradingMemoryLog` (markdown append-only). Entries:
  `[date | TICKER | rating | pending]` -> resolved to
  `[date | TICKER | rating | resolved-return | alpha-vs-benchmark]` on a later
  run. Reflection notes / analyst hit-rates feed the PM context.
- `memory_log_max_entries` bounds resolved-entry rotation (pending never pruned).

## 7.2 Checkpoints

`graph/checkpointer.py`. Per-ticker SQLite under
`~/.tradingagents/cache/checkpoints/`. `--checkpoint` / `checkpoint_enabled`
engages. Keyed on ticker+date+graph-shape; cleared on success.

## 7.3 Vendor cache

`dataflows/vendor_cache.py`. Disk TTL (6h) under
`data_cache_dir/vendor_cache/`. Re-serves successful fetches; news excluded.

## 7.4 Strategy / calibration ledgers

- `strategy_ledger.jsonl` (under `data_cache_dir`) — analyst hit-rates (the
  reflection engine).
- `calibration_ledger.jsonl` — bucket win-rates for the calibration overlay.
- `risk_audit.jsonl` — risk-governor audit rows (PASS/WARN/REJECT).

## 7.5 Report tree

`reporting.py::write_report_tree(state, ticker, path)` writes:

```
<path>/1_analysts/{market,news,fundamentals,sentiment}.md
<path>/2_research/{bull,bear,manager}.md
<path>/3_trading/trader.md
<path>/4_risk/{aggressive,conservative,neutral}.md
<path>/5_portfolio/decision.md
<path>/complete_report.md      (H1 report -> H2 team -> H3 role -> H4+ agent content)
```

The TOC auto-links every team/role heading. `5_portfolio/decision.md` carries
the `Risk Gate (computed)` verdict when the governor is on (plus, with the
tranche fold enabled, `Tranche peak-deployed` / `Tranche capital-at-risk` lines
from `tranche_context`).
`rebuild_complete_report.py` re-renders a folder without re-running and
preserves `Risk Gate (computed)` blocks.

## 7.6 Final-decision JSON log

`_log_state` writes `results_dir/<ticker>/TradingAgentsStrategy_logs/full_states_log_<date>.json`.

Continue to [`08-development.md`](08-development.md).