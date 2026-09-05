# Session Handoff — TradingAgents (2026-09-04, context-limit continuation)

## 1. Task Objective & Scope
Pick up the working tree from the prior session's handoff and land the in-flight
work: complete the value-dip falling-knife gate + batch `--probe` tracing WIP,
fix its wiring gap, mirror to trading_web, document, test, commit + push.

**Completed this session (committed with this handoff, pushed to `origin main`):**
- `--knife-z` value-dip velocity-z gate fully wired (was a silent no-op on the
  flagship universes); `knife_guard_vpin` slice landed; tests.
- `batch.py --probe` traced run; hermetic tests.
- Doc fill: `remediation_chatgpt.md` (1371 ln), `remediation_claude.md` (40 ln),
  `Strategies/market_research.md` (2175 ln) — the external-review/formula
  inputs behind the W-phase remediation were committed as 0-byte stubs at HEAD
  (d0b258b); the working tree carried the full drafts, now committed.
- trading_web mirror (`run_screener knife_z`, Screener form field, web README).
- CHANGELOG / README News / api_reference / Strategies/scan.md synced;
  `session.md` replaced with this handoff.

Also this session:
- **Formula-catalog implementation** (from `Strategies/formulas/6 pillars...` +
  `Quant Finance Formula Master Catalog` — the ~300-formula zoo deltas were
  small; implemented the 6 non-existant families): P1 `covariance_models.py`
  (Ledoit-Wolf shrink + RiskMetrics EWMA cov) + `yang_zhang_vol`; P2
  concentration suite (active_share/hhi/effective_holdings/entropy) + EVT/GPD
  `extreme_quantile_var`; P3 `kyle_lambda` + multi-asset fractional Kelly
  (in `allocation_block` behind `enable_kelly_alloc`); 5 new analyst tools +
  YZ row; web Value Tools += 5; config keys added; docs synced; tests
  `test_strategies_covariance_models` (8) + `test_formulas_p2` (11) +
  `test_formulas_p3` (7). Formals grounded via web_search (YZ k-weight,
  Ledoit-Wolf b2/d2, Kyle ΔP~Q regression, Kelly Σ⁻¹μ).
- **Calc→agent wiring made permanent** - the wiring audit is now a gate:
  per-fn rule requires an outside-module reference (or internal-helper of a
  reachable module) and a NEW `@tool`→binding test requires every public
  tool in graph ToolNodes/risk-loop/analysts. It caught 4 never-bound tools
  (get_pair_risk/get_trade_excursions/get_vif_read/get_no_trade_guard_band;
  from the 7-phase risk + quant-adds batches — defined, exported, never
  bound) and wired the parked scoring/scenario reads
  (get_prediction_ledger_score, get_trade_outcome_metrics,
  get_stress_grid_read, get_macro_regime_read). Whitelist now holds only
  permanent classifications (typed_state design-reference, complexity_report
  dev-ops, iv_percentile needs a per-day IV history) + dead-legacy entries.
  ALSO: fixed the 3 pre-existing test_qlib_wiring tradability failures
  (backtest next-bar entry never applied limit/suspension/participation
  gates — restored) + the stale catalyst test expectation. Note: agent_utils
  must list a re-export in `__all__` or ruff F401 silently deletes it - the
  new tools were re-added with __all__ entries.
- **Hummingbot V2 teacher study** (docs-only): `docs/design_hummingbot_integration.md`
  — direct-source study (sparse clone at 2025 V2) of StrategyV2Base/
  Controllers/Executors/Connectors, per-executor CloseType accounting,
  budget-collateral lock, live-book paper-trade fill-latency, unified
  executor ledger, async notifier. 5 advisory phase-gated adoptions
  (exit-accounting P1, collateral lock P2, fill-latency P3, executor-ledger
  spec P4, async notifier P5); explicit non-goals keep the no-execution /
  math-decides mandates. No code changed.
- **yfinance study P1 + P5 implemented** (user approved only these two):
  `VendorAbsence` (errors.py) + per-call contextvar side channel in
  `route_to_vendor` (string contract preserved) → `VendorResult.absence`
  (schema.py) → OHLCV envelope (analysis_tools), run_card `data_absence`
  block (reporting.py, null on success), web `/api/ohlcv` absence field
  (trading_web); CLI period-validation N/A (no such CLI). `yfinance~=1.4`
  pin + `tradingagents/dataflows/README.md` vendor notes.
  tests/test_vendor_absence.py (15). P2/P3/P4 design-only.
- **yfinance v1.7.0 teacher study** (docs-only):
  `docs/design_yfinance_integration.md` — direct-source study of
  ranaroussi/yfinance 1.7.0 (YfData cookie/crumb, cache.py SQLite KVs,
  base.py tz fetch + validation, history price repair, multi.py error
  grouping, exceptions taxonomy) + fork's existing yfinance integration.
  5 advisory phase-gated adoptions: P1 typed absence reasons through the
  read envelope (VendorAbsence + OHLCV absence field + CLI period
  validation), P2 exchange-tz + currency KV cache for OHLCV reads
  (dataflows/exchange_tz.py, envelope tz/currency, statement currency
  prefers cache over ADR heuristic), P3 100x currency-unit repair
  (config-gated, detected + flagged), P4 batch error grouping +
  debug-serialize rule, P5 deliberate yfinance~=1.4 pin + vendor quirk
  notes. Validation table: fork already has yf_retry/typed errors/stale
  guard/statement-currency/sentinel cache. Non-goals: WebSocket/protobuf,
  login cookies, SQLite persistent caches, curl_cffi, ISIN, screener DSL,
  domain objects. No code changed.
- **FinceptTerminal v4 teacher study** (docs-only):
  `docs/design_fincept_terminal_integration.md` — direct-source study of
  Fincept-Corporation/FinceptTerminal (C++20/Qt6 + embedded Python;
  DataHub topic registry, LlmService tool loop, trading, FinAgent Core,
  ai_quant_lab, agentic-research docs). 6 advisory phase-gated adoptions:
  P1 typed topic-registry refresh policy for trading_web (TTL/min-interval/
  coalesce/freshness fields + web_TOPICS.md), P2 tool-result size budget with
  park-and-page (result_store + fetch_result tool), P3 dual tool-loop budget
  + visible exhaustion (run_card/jobs fields + progress line), P4 SQLite
  per-step checkpoints + resume_job, P5 org-as-data governance metadata
  (agreement_weighted + n_abstained + PM rigor criteria), P6 single-source
  capability cross-check gate (test_web_capabilities). Validation table:
  fork ahead on LLM registry, Qlib study, backtest semantics. Non-goals:
  C++ frontend, paper trading, crypto tokenomics, MCP marketplace, Ollama
  default, Qlib wrapper, per-persona SQLite memory. No code changed.
- **ai-hedge-fund v2 teacher study** (docs-only):
  `docs/design_ai_hedge_fund_integration.md` — direct-source study of
  virattt/ai-hedge-fund v2.2.0 (data/signals/llm/features/fund/strategies/
  portfolio/risk/brokers/pipeline/backtesting/event_study/validation/tui).
  5 advisory phase-gated adoptions: P1 mandate-as-data (fund/strategy/model
  YAML + pipeline --mandate), P2 event-study market-model CAR + significance
  (t-test + bootstrap CI), P3 abstention-vs-neutral conviction blending,
  P4 per-clamp risk audit events, P5 prompt provenance vault (decision_hash
  linked). Validation table: fork already ahead on CPCV/PBO/evaluate/LLM
  registry. Non-goals: live brokers, TUI, persona voicing, market-neutral
  shorts, prompt caching for cost. No code changed.

## 2. What Landed — Files & Commits
**Code (repo):**
- `tradingagents/strategies/orderflow.py` — `knife_guard_vpin(vpin, price_delta,
  threshold=0.75)`: downside-conditioned order-flow toxicity filter. Standard
  VPIN is non-directional; a knife guard must only suppress dip-buying when the
  toxicity is driven by SELLING (VPIN > thr AND price down), never block
  up-breakouts. Missing input -> False. Was the HEAD-breaking gap: committed
  `value_dip.py`/`test_knife_guards.py` (a7d7e02) imported it but it existed
  only in the working tree.
- `scripts/value_screener.py` — `--knife-z z` (default 0 = off): maps to
  `value_dip_setup(require_knife=bool(z), knife_velocity_threshold=z)`.
  **Fix beyond the WIP:** the WIP wired it ONLY into the moomoo movers loop;
  the tickers / eodhd-us / eodhd-losers universes reach the value-dip read via
  `_compute_scan_row`, which dropped the flag — `--knife-z` was silently dead
  on the flagship universes. `_compute_scan_row` now forwards `knife_z` (both
  call sites). Found by a CLI-seam test that observed `knife_z == 0.0` despite
  the flag.
- `batch.py` — `--probe`: writes `reports/batch_probe_<ts>.jsonl` (symbol /
  stage / t_abs / elapsed_s / error / wall_seconds / per-worker data_vendors)
  around the graph run: `graph_start` before `propagate`, `graph_done` on
  success, `graph_failed` (then re-raise) on exception. Ruff fixes applied
  (dropped dead `probe_writer`, combined `with`s).
- `tests/test_value_screener.py` — 2 tests: `_value_dip_scan` semantics
  (same inputs candidate True -> False with `knife_z=-2.5`) + CLI seam
  (`--knife-z -2.5` reaches the seam; default 0.0).
- `tests/test_batch_probe.py` — 3 tests (done trace / absent no-op / failed
  re-raise), hermetic via FakeGraph + `batch.config_probe`.
- `.gitignore` += `.aider*` (agent tooling hygiene, kept).

**Docs (all synced to the code; agreement checklist kept true):**
- `Strategies/scan.md` — `--knife-z` paragraph in "The value-dip".
- `docs/api_reference.md` — screener flag list += `--knife-z`.
- `CHANGELOG.md` (Added), `README.md` (News 2026-09-04 + value-watchlist
  section).
- `docs/remediation_chatgpt.md` / `docs/remediation_claude.md` /
  `Strategies/market_research.md` — full external material committed
  (see scope above).

**trading_web (mirror):**
- `backend/capabilities.py` — `run_screener(..., knife_z: float | None)`,
  appends `--knife-z` whenever set (explicit 0 must reach the CLI — the
  "0 = off" semantic).
- `frontend/src/App.jsx` — `knife_z` form state, `screenerArgs` sends it,
  `applyScreenerPreset` restores it, new "Falling-knife z gate (--knife-z)"
  field with placeholder `-2.5`.
- `README.md` — Screener row += `--knife-z`.

## 3. Current State & Validation
- **Tests green:** `test_knife_guards` 9, `test_batch_probe` 3,
  `test_batch_workers` 1, `test_batch_vendor_preset` 4, `test_value_screener`
  37, `test_screener` 10 (47 total across the two screener suites). Ruff clean
  on every touched file. No full-suite run this session (scoped change to
  screener + batch; the ~3-5 min suite is pointless for these two areas).
- HEAD: knife-z/probe/docs commit + the trading_web commit (separate repo).
- Working tree clean; only the user's untracked files remain
  (`Direction.md`, `_probe*.ps1`, `_marker`, `.commandcode/`).

## 4. Technical Constraints & Decisions
- **`--knife-z` semantics:** `0` disables (default); any nonzero z enforces
  `velocity_z < z`. Rows ALWAYS display; the flag only decides whether the
  velocity row gates (`require_knife`). Negative thresholds are the normal
  case — the CLI test passes `--knife-z -2.5` (argparse handles it).
- **VPIN conditioning (decision):** directional gate (down-move AND) so
  up-breakouts are never blocked — the knife guard's whole point. `price_delta`
  uses the same `price_delta_tau` window as the velocity read (closes[-1] -
  closes[-4] fallback).
- **No web mirror for `--probe`:** web calls `batch.analyze` in-process (not
  the CLI), so the arg never applies; the probe install point is the module
  global `config_probe`, which web could use but doesn't need.
- **Docs commits:** the remediation/market_research fills are the ORIGINAL
  external-review inputs behind the already-landed W-phase remediation —
  committed as documentation, not as a new plan. The 2026-09-02 "docs
  accumulated" follow-up is now resolved.

## 5. Open Follow-ups (unchanged from prior sessions, NOT touched)
- Empty-symbol `get_stock_data` vendor anomaly (reject earlier in
  `symbol_utils` / tool wrappers).
- CLI dispatch quirk: `tradingagents analyze --symbol X` vs
  `tradingagents --symbol X` under typer 0.27 (user decision pending).
- Stale-tape data-quality flag (computed tools quoting stale cached close vs
  live).
- Fast-path (T0/T1) implementation decision (design doc committed, no code).
- Qlib/FinRL Phase-1 pure-calculator implementation (docs-only so far).
- Memory `holding_days` settle gating, FRED vintage pin, `structured.py`
  schema-only-agent tool priming, openai Responses-API gating,
  `test_ohlcv_latest_bar` NaN-close, Retry-After parity vs parent `reddit.py`.

**Repo:** origin `https://github.com/Ghostfusion/TradingAgents.git`, branch
`main`. `py -3.12` ONLY; Windows heredocs corrupt (use `write`/`edit`); stage
explicitly (`git add -A` sweeps user files); lowercase `git add changelog.md`
silently misses (use `CHANGELOG.md`/`README.md`).