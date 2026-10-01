# 7. Persistence & recovery

These are the on-disk pieces that survive a run.

## 7.1 Memory log

- Location: `~/.tradingagents/memory/trading_memory.md` (or
  `TRADINGAGENTS_MEMORY_LOG_PATH`). Batch symbols get per-symbol memory files
  (`batch._per_symbol_memory_path`, same folder, one file per symbol), which is what
  keeps two concurrent workers from interleaving a read-modify-write cycle in one
  file. Proved by `tests/test_batch_workers.py::test_two_workers_memory_logs_do_not_see_each_others_entries`;
  the interactive CLI keeps the single shared file, which is correct for one run.
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

- `strategy_ledger.jsonl` (under `data_cache_dir`) — the reflection engine's
  per-analyst hit-rates. Written through
  `strategies/reflection.py::ReflectionLedger` (the class takes an explicit
  `path`; the caller at `graph/trading_graph.py:2066` supplies the filename).
  Read back by `scripts/strategy_quality_report.py:137` and
  `scripts/orderflow_evaluate.py:91`, both of which default to the same path.
  Each row is `{analyst, ticker, trade_date, delta_r, ts}`;
  the score is a recency-decayed hit-rate with a 30-day half-life.
- `calibration_ledger.jsonl` — bucket win-rates for the calibration overlay.
  Rows are stamped `{confidence, won: delta_r > 0}` (`trading_graph.py:2108`).
- `risk_audit.jsonl` (under `data_cache_dir`) — risk-governor audit rows
  `{ticker, verdict, reasons}` with `verdict ∈ PASS|WARN|REJECT`. Gated by
  `risk_audit_enabled` (**default ON**). **SHA-256-chained**: each row's
  `prev_hash` is the hash of the previous raw line
  (`strategies/hash_chain_audit.py::append`), so truncation or editing breaks
  the chain. Verify with `py -3.12 scripts/risk_report.py --verify-chain`;
  summarise verdict counts and limit hits with
  `py -3.12 scripts/risk_report.py --audit`.

## 7.5 Report tree

`reporting.py::write_report_tree(state, ticker, path)` writes:

```
<path>/1_analysts/{market,news,fundamentals,sentiment}.md
<path>/2_research/{bull,bear,manager}.md      (+ structured_debate.md, evidence only)
<path>/3_trading/trader.md
<path>/4_risk/{aggressive,conservative,neutral}.md
              (or a single verdict.md when risk_compact_report is set)
              (+ structured_risk_debate.md, evidence only)
<path>/5_portfolio/decision.md
<path>/complete_report.md      (H1 report -> H2 team -> H3 role -> H4+ agent content)
<path>/run_card.json           (config hash, commit, models, verdict, scorecard)
<path>/research_decision.json   (the executor contract; emitted by default)
<path>/tool_evidence.json       (only when the run captured evidence leaves)
```

`write_report_tree(..., emit_run_artifacts=False)` (used by
`rebuild_complete_report.py`) re-renders the markdown only and deliberately
leaves `run_card.json` / `research_decision.json` / `tool_evidence.json`
untouched — a rebuild reconstructs state from markdown and must not invent an
artifact the original run never wrote.

Further per-tree files are written by opt-in hooks, each behind its own gate:
`verify_flags.json` (batch `--verify` / `scripts/report_verify.py`),
`jev_verdict.json` (`enable_jev_verdict`), `alpha_ledger.jsonl`
(`alpha_ledger_enable`), and `pre_market_review_<date>.md`
(`enable_pre_market_review`).

The TOC auto-links every team/role heading. `5_portfolio/decision.md` carries
the `Risk Gate (computed)` verdict when the governor is on (plus, with the
tranche fold enabled, `Tranche peak-deployed` / `Tranche capital-at-risk` lines
from `tranche_context`).
`rebuild_complete_report.py` re-renders a folder without re-running and
preserves `Risk Gate (computed)` blocks.

## 7.6 Final-decision JSON log

`_log_state` writes `results_dir/<ticker>/TradingAgentsStrategy_logs/full_states_log_<date>.json`.
It takes the ticker as a parameter, so every entry point writes it - it used to
read `self.ticker`, which only `propagate()` ever set and which the interactive
CLI never set at all, so the CLI could not write a state log.


Continue to [`08-development.md`](08-development.md).