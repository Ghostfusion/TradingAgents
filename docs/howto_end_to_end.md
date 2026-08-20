# End-to-end how-to (complete)

Everything about running TradingAgents on this fork: environment, config,
every entry point, the cross-sectional workflow, reading reports, persistence,
evaluation, and troubleshooting. Companion docs: `docs/AGENT_ONBOARDING.md`
(environment runbook) and `docs/api_reference.md` (reference).

---

## 0. Environment & prerequisites

- Python **3.12** via `py -3.12` (bare `python` is the hermes venv, no pytest).
- Dependencies installed from `pyproject.toml`; moomoo needs OpenD.
- `.env` at the repo root (gitignored) holds: provider keys (`OPENAI_API_KEY`,
  `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `XAI_API_KEY`, `DEEPSEEK_API_KEY`,
  `DASHSCOPE_*`, `ZHIPU_*`, `MINIMAX_*`, `OPENROUTER_API_KEY`, `MISTRAL_API_KEY`
  ...), `ALPHA_VANTAGE_API_KEY`, `FRED_API_KEY`, `TRADINGAGENTS_FINNHUB_API_KEY`,
  `TRADINGAGENTS_FMP_API_KEY`, Alpaca keys, and the strategy flag block
  (`TRADINGAGENTS_ENABLE_*` = true except opt-outs). Never commit it.

**One-time moomoo setup** (free account): install OpenD, log in once with
"remember password"; `TRADINGAGENTS_MOOMOO_AUTOSTART=true` in `.env` launches
it headlessly (`-login_by_remember=1`). Quote permissions: US LV3 / HK LV1 /
crypto free; US options need >$3k assets; event contracts need an SG/MY
account (else they fall back to Polymarket).

Check readiness:

```bash
py -3.12 -c "import tradingagents; print('ok')"
netstat -ano | findstr 11111       # OpenD listening
```

## 1. Run the analysis five ways

### 1a. Interactive CLI (watch every agent)

```bash
tradingagents
# or: py -3.12 -m cli.main
```
Steps: ticker -> date -> language -> analysts -> depth -> provider -> models.
The live dashboard shows team progress, LLM/tool/token stats, messages.

### 1b. Python API (embedding)

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

cfg = DEFAULT_CONFIG.copy()
ta = TradingAgentsGraph(debug=True, config=cfg)
final_state, decision = ta.propagate("NVDA", "2026-08-19")
ta.save_reports(final_state, "NVDA")   # writes reports/ (CLI layout)
```

### 1c. Batch runner (headless, concurrent)

```bash
py -3.12 batch.py --symbols NVDA MSFT 0700.HK BTC-USD --date 2026-08-19 \
     --workers 3 --depth deep --analysts market news fundamentals \
     --vendor moomoo
```

Each symbol gets its own memory log; reports land in
`reports/<SYMBOL>_<YYYYMMDD_HHMMSS>/`; summary appended to
`reports/batch_summary_<ts>.jsonl`. Crypto symbols auto-disable ratings,
earnings, and the A-series tooling.

### 1d. Cross-sectional pipeline (B2) — screen then analyze the top-N

```bash
py -3.12 pipeline.py --universe top-losers --top 5 --workers 3
py -3.12 pipeline.py -f universe.txt --top 5 --date 2026-08-19
py -3.12 pipeline.py AAPL MSFT NVDA --top 3 --depth deep --vendor moomoo
```

Output: `reports/pipeline_<ts>.md` (ranked candidates + per-symbol results +
report links) and `reports/pipeline_<ts>.jsonl`.

### 1e. Value screener alone

```bash
py -3.12 scripts/value_screener.py AAPL MSFT GOOG -d 2026-06-30
py -3.12 scripts/value_screener.py --universe top-losers --scan all --alloc
py -3.12 scripts/value_screener.py --file universe.txt --limit 10 --rank composite
```

Screens: Magic Formula (EY, EV/EBIT), Acquirer's Multiple, Piotroski
(F-Score), Shareholder Yield, Net-Net, and Beneish/Altman guards; trend
pullback / breakout / momentum / swing scans (see `Strategies/scan.md`);
portfolio alloc block; journaling.

## 2. What happens in one analysis

1. Analyst teams (market, sentiment, news, fundamentals) each run a
   tool-calling loop against the vendor layer.
2. Bull/Bear researchers debate; the Research Manager emits a plan.
3. The Trader binds an entry/stop/size proposal.
4. Aggressive/Conservative/Neutral risk analysts debate.
5. Portfolio Manager returns the structured decision
   (rating, confidence, `position_size`, `stop_loss`, `consensus`).
6. Deterministic overlays then adjust size: regime -> orderflow -> catalyst ->
   position contract -> risk governor (`PASS/WARN/REJECT`, `risk_halt`).
7. The decision is appended to the memory log; the next same-ticker run
   resolves the realized return vs the regional benchmark and reflects.

With `analyst_concurrency=2+` the four analysts run in parallel threads (raise
provider load; default 1).

## 3. The catalyst overlay (B1, on by default)

`enable_events=true`: the overlay fetches the next earnings date + last EPS
surprise, option-implied move/IV crush, HIGH economic events, and FOMC
probabilities; it emits a scale (0-1) and a verdict
(`earnings-window` / `macro-catalyst` / `fed-catalyst` / `no-imminent-catalyst`)
that de-risks position size near catalysts. Verify live:

```bash
py -3.12 -c "
from tradingagents.strategies.catalyst import fetch_catalyst_data, build_catalyst_snapshot
from tradingagents.default_config import DEFAULT_CONFIG
d = fetch_catalyst_data('AVGO', '2026-08-19')
s = build_catalyst_snapshot(d, '2026-08-19', DEFAULT_CONFIG)
print(s['verdict'], s['scale'], s['reasons'][:2])
"
```

Tuning keys: `catalyst_window_days`, `catalyst_baseline_move`,
`catalyst_macro_window_days/_scale`, `catalyst_fed_window_days/_scale`,
`catalyst_miss_scale`, `catalyst_scale_floor`.

## 4. Reading the reports

Every run's folder: `1_analysts/`, `2_research/`, `3_trading/`, `4_risk/`,
`5_portfolio/`, and `complete_report.md`:

- **TOC** at the top links every team and role.
- **Hierarchy**: H1 report -> H2 team -> H3 role -> H4+ agent content (agent
  headings are auto-demoted so nothing collides).
- `5_portfolio/decision.md` carries the `Risk Gate (computed)` verdict +
  snapshot when the governor is on.

Re-render an existing folder without re-analysis (after formatter changes):

```bash
py -3.12 scripts/rebuild_complete_report.py reports/SFTBY_20260819_115450
py -3.12 scripts/rebuild_complete_report.py      # all
```

## 5. Markets & asset types

Yahoo-style tickers with exchange suffixes; `asset_type` auto-detects
`crypto` (`BTC-USD`). Examples: `AAPL`, `SPY`, `0700.HK`, `7203.T`,
`RELIANCE.NS`, `BHP.AX`, `600519.SS`, `BTC-USD`. Alpha benchmarks auto-resolve
per exchange (`benchmark_map`). Moomoo coverage: US/HK/JP/SH/SZ/AU/CA/SG/MY +
crypto; LSE/India/futures fall back to yfinance.

## 6. Persistence

- Memory log: `~/.tradingagents/memory/trading_memory.md` (per-symbol files in
  batch); `TRADINGAGENTS_MEMORY_LOG_PATH` overrides. Entries start
  `[date | TICKER | rating | pending]` and resolve to returns+reflection on a
  later same-ticker run; track record stats feed the PM.
- Checkpoint resume (`--checkpoint` / `checkpoint_enabled`): per-ticker SQLite
  under `~/.tradingagents/cache/checkpoints/`, resume from the last node;
  `--clear-checkpoints` resets; keyed on ticker+date+graph-shape.
- Vendor cache: disk TTL under `data_cache_dir/vendor_cache/` (news excluded).

## 7. Evaluation & tuning scripts

```bash
py -3.12 scripts/orderflow_evaluate.py      # L4b: ledger win-rate/alpha
py -3.12 scripts/evaluate_config_gate.py    # G5: walk-forward + PBO gate
py -3.12 scripts/risk_report.py             # risk audit summary (risk_audit.jsonl)
py -3.12 scripts/smoke_structured_output.py # structured-output smoke
```

## 8. Troubleshooting

- `No module named pytest/pandas` -> you used `python`; use `py -3.12`.
- `Vendor 'moomoo' not configured ...` -> OpenD down / not logged in; the
  run falls back silently.
- `NO_DATA_AVAILABLE` for options on a US name -> account lacks options
  permission (threshold); chain falls back to yfinance.
- Catalyst scale stays 1 -> no imminent catalyst or no calendar coverage; by
  design neutral.
- Process hangs at process exit -> an `OpenQuoteContext` leaked; close it
  (see AGENT_ONBOARDING). Tests close contexts per-fixture.
- Corrupted escapes when a fresh agent uses heredocs on Windows -> write files
  with the write tool, not heredocs (see AGENT_ONBOARDING).

## 9. Extra tips

- Keep config per-run via `.env` or `DEFAULT_CONFIG.copy()`; threads get
  isolated copies (`config.set_config` is thread-local).
- The bond between this fork's modules: `dataflows` = data, `agents` = prompts,
  `graph` = wiring, `strategies` = numbers, `reporting` = output.
- Read `docs/api_reference.md` for the full keys/tools and `docs/AGENT_ONBOARDING.md`
  before deep hacking.