# Shadow Account Loop — design (Vibe-Trading transfer, P3-10)

**Status:** Draft (design only; NOT implemented). Advisory, default-off. No decision gates are touched.

**Source:** HKUDS/Vibe-Trading "Shadow Account" flagship loop (`analyze_trade_journal` → `extract_shadow_strategy` → `run_shadow_backtest` → `render_shadow_report` → `scan_shadow_signals`).

## Why

The repo already records per-decision history (`scripts/decision_history.py` reading `full_states_log_*.json` + `reports/<SYM>_*/5_portfolio/decision.md`), a trade-journal analyzer (`strategies/journal.py`), a persistent invalidation ledger (`strategies/invalidation_ledger.py`), and a deterministic backtest engine (`strategies/backtest_engine.py` with next-bar fills + fills-vs-targets). What is missing is the loop that turns a broker CSV / journal into *today's* watch list. The shadow loop is the flagship because it turns the system's own past decisions into an honest trading rulebook.

## Loop (pure + hermetic; no LLM required in the deterministic core)

```
1. ingest      journal/CSV  →  canonical roundtrips (pairs of (entry, exit) with
                              side, qty, price, date, symbol)   [strategies/journal.py]
2. profile     behavior diagnostics: holding period, win rate, disposition effect,
                              chasing, overtrading, anchoring      [journal.py + stats]
3. extract     distill 3-5 if-then entry rules from the PROFITABLE roundtrips
   (shadow_strategy)          (heuristic: cluster by feature thresholds that
                              separate wins from losses; deterministic, no LLM;
                              returns the rule table + coverage stats)
4. backtest    run each rule over a symbol universe (next-bar fills, real costs)
                              → delta-PnL vs the realized trades    [backtest_engine]
5. scan        today's symbols matching any rule's entry cadence (research only:
                              these are candidates for a full run, never orders)
6. render      HTML/MD report: 8 sections (profile, rules, backtest, delta, today's
                              matches, context)                    [reporting-style]
```

## Data flow

```
broker_export.csv ─► journal.ingest ─► roundtrips ─► profile
                                              └─► extract_shadow_strategy ─► rules.yaml
rules.yaml ─► backtest (universe = current reports universe + portfolio basket)
            ─► delta vs realized
            ─► scan_shadow_signals(today) ─► report
```

The rules file is plain YAML under `<results_dir>/shadow/` so a user edits it and the loop re-runs deterministically (mirrors the skill-YAML philosophy; no freeform code).

## Rule format (v1)

```yaml
rules:
  - id: shadow_1
    entry:
      side: long
      feature: momentum_20d        # one of the profile/computed features
      op: ">"
      threshold: 0.10
      hold_days: 5
    source: roundtrip cluster #2
    win_rate: 0.71
    coverage: 0.23
```

Extraction heuristic (deterministic): for each candidate feature (20d/60d momentum, RSI, value Z, volume ratio), find the threshold that maximizes (win_rate - baseline) with a minimum sample (>= 8 roundtrips). Only rules with win_rate > 0.6 AND coverage >= 0.1 are kept; a rule table with < 3 rules is reported as "insufficient profile" (honesty — no fabricated rules).

## Acceptance criteria

1. Given a synthetic CSV of 20 roundtrips (10 profitable), `extract_shadow_strategy` returns 3-5 rules whose threshold separates wins (check: a holdout win has higher rule score than a holdout loss), no LLM, < 1s.
2. `run_shadow_backtest` uses the existing `backtest_engine` (next-bar fill; no lookahead) and reports `delta_pnl = strategy_pnl - realized_pnl` with a fills-vs-targets note.
3. `scan_shadow_signals(today)` returns only symbols whose LAST bar satisfies a rule's entry condition using PIT-safe data (the vendor chain; no future data) — the existing `market_data_validator`/`pit_registry` applies.
4. Every number is honest: unavailable/unmeasurable -> explicit "unavailable"; a rule with insufficient samples is not emitted.
5. The whole pipeline runs offline on a fixture (hermetic; no vendor calls in tests).

## Suggested modules

- `tradingagents/strategies/shadow.py` — ingest/profile/extract/scan (pure).
- `scripts/shadow_report.py` — CLI (`--journal`, `--universe`, `--json`, `--out`).
- Reuses `strategies/backtest_engine.py`, `strategies/journal.py`, `reporting.py` card renderer, `pit_registry`.

## Non-goals (explicit)

- NOT trading: the scan is research-only, no order emission (the repo's hard gate stays: advisory, no execution).
- NO LLM in the extract/scan core — deterministic, so it is auditable and free. An optional `--llm` judge for rule prose is a later extension.
- No new data vendors.

## Rollout

- Phase 0 (this doc): agree the rule format + acceptance criteria.
- Phase 1: `tradingagents/strategies/shadow.py` + `scripts/shadow_report.py` + hermetic tests (synthetic CSV; 10-15 tests).
- Phase 2: wire `scan_shadow_signals` results into the nightly review as an optional advisory section (`--shadow` flag; default off).
- Phase 3: optional LLM prose + web report surface (trading_web mirror).

## Risks

- Rule overfitting to a tiny journal: min-sample + out-of-sample holdout check (built-in).
- PIT/lookahead: reuse the existing next-bar/pit discipline; the scan only uses last settled bar.
- Journal quality: CSV column drift — ingest is defensive (multiple header forms) and reports parse coverage.