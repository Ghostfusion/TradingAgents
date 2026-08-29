# Changelog

All notable changes to TradingAgents are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Breaking changes within the 0.x line are called out explicitly.

## [Unreleased]

### Added
- **OpenBB enhancements (deep-study implementation)** (`docs/design_openbb_enhancements.md`) -
  design → implemented (Phases 1-4 + cross-cutting):
  - **Strategy depth** - `strategies/statistical.py` (normality, unit_root
    ADF+KPSS, omega, correlation_matrix, cointegration_pair, granger_causality,
    capm_decomposition, ols_factors, variance_inflation_factor) +
    `strategies/rotation.py` (relative_rotation RRG quadrants, clenow_momentum,
    vol_cones). 5 new market @tools (get_normality / get_unit_root /
    get_relative_rotation / get_capm_risk / get_clenow_momentum).
  - **Typed dataflow layer** - `dataflows/schema.py` VendorResult envelope
    (results/provider/warnings/error_kind + to_llm/to_markdown),
    `dataflows/registry.py` (coverage, required_credentials, filter_params,
    command_map), `route_to_vendor_typed()` mapping sentinels -> error_kind.
  - **Free-tier data surfaces** - `dataflows/cboe.py` (options surface ->
    options_math.black_vol_surface), `dataflows/federal_reserve.py` (SOFR +
    Treasury curve for term-structure discounting), `dataflows/screener.py`
    (yfinance universe screener + movers). 4 new config gates default OFF.
  - **Web product (trading_web)** - watchlist, SignalTable grid, TickerChart
    (candlestick/volume/drawdown), run presets, credential manager, job
    timeline + rerun (54 backend tests, vite build clean).
  - **Web user guide screen (trading_web)** - `HelpGuide.jsx` (`/"guide`),
    plain-language documentation for every screen (purpose, sample UI
    selections, likely result) written for non-technical / non-financial
    users; nav entry + route + guide CSS, `npm run build` clean.
  - **QuantLib + Lean enhancements (deep-study implementation)** (`docs/design_quantlib_lean_enhancements.md`) -
  design → implemented (Phases 1-4 + cross-cutting): new pure modules under
  `strategies/`, extended evaluation breadth, 4 new market analyst tools, and
  10 new config keys (all gates default OFF / advisory-only):
  - **New modules** - `options_math.py` (black76, implied_vol_and_greeks,
    black_vol_surface), `rate_utils.py` (discount_factor, compound_factor,
    equivalent_rate, monotone_fill, downside_measures),
    `portfolio_optimizer.py` (risk_parity_weights, min_variance_weights,
    confidence_weights, enforce_sector_exposure, risk_contribution),
    `risk_manager.py` (two-pass `manage_risk` exit override +
    `trailing_stop_targets`; advisory, not wired into the runtime graph yet),
    `alpha_eval.py` (alpha_score, insight_accuracy), `config_robustness.py`.
  - **Extended modules** - `evaluate.py` (skewness, kurtosis,
    downside_deviation, sortino, tracking_error, information_ratio, beta,
    alpha, treynor, rolling_beta, probabilistic_sharpe, underwater_drawdowns),
    `exits.py` (`trailing_stop_exit`, `max_giveback_exit`), `book_risk.py`
    (`return_autocorrelation`, `var_cvar_horizon`), `journal.py`
    (`trade_excursions` MAE/MFE), `liquidity_risk.py` (volume_share_slippage,
    market_impact_slippage).
  - **New analyst tools (market ToolNode)** - `get_downside_read`,
    `get_horizon_var`, `get_trailing_exit`, `get_risk_parity_alloc`;
    `get_strategy_quality` now also emits sortino + psr.
  - **Config keys (+ `TRADINGAGENTS_*` env overrides, gates default OFF)** -
    `psr_benchmark_sharpe` (0.0), `rolling_window` (132), `downside_mar` (0.0),
    `trailing_stop_pct` (0.05), `enable_trailing_exit` (False),
    `risk_parity_enabled` (False), `risk_manager_drawdown_pct` (0.05),
    `enable_risk_manager` (False), `volume_share_vol_limit` (0.1),
    `volume_share_price_impact` (0.025).
  Tests: 62 new + 176 regression green, ruff clean.

- **P1/P2/C3: pre-open + execution-quality advisory rows (Alpaca free IEX)** -
  implemented the measurable slices of the institutional extended-hours
  workflow with the tiers this machine actually has (probed live):
  - **P1 pre-market RVOL** (`dataflows/preopen.py::premarket_rvol`): today's
    pre-open volume / 30-day pre-open average (Alpaca 15-min bars pre 09:30
    ET) - the text's "RVOL > 2.0x institutional" read. Verified live on AAPL.
  - **P1 pre-open gap** (`preopen_gap`): gap anchored to the LIVE pre-open
    price (Alpaca latest trade), not yesterday's close.
  - **P2 live IEX quote-depth** (`preopen_book_depth`): spread_bps, bid/ask
    size imbalance, thin-book flag - the free-tier stand-in for NOII opening
    imbalance (true NOII is plan-gated; documented as a proxy).
  - **C3 alpha-profile** (`postfill_drift` + `strategy_quality_report`):
    post-fill N-day drift vs arrival on the paper ledger - the "did our fill
    leak / adverse selection" test. All advisory, default-ONLY-injected into
    the pre-market reviewer (never gates).
  - Web Pre-Market screen Help updated; config + env keys added
  - **Agent + web sync**: the 5 decision agents (Trader, PM, 3 risk debators)
    now receive the pre-open RVOL / gap / book-depth reads (plus the existing
    regime + re-rating + plan card) via `computed_decision_context`; the
    value-dip analyst tool renders regime_gate + re_rating rows (visible in
    the web Value Tools page), the pre-market reviewer prints them (web
    Pre-Market job output), and the report's `IVa. Computed Decision Context`
    section surfaces the full advisory set.
    (`enable_preopen_rvol` / `enable_preopen_depth` / `enable_alpha_profile`).
  - **Probed data availability** (your tiers): Alpaca free IEX = pre-market
    bars + live quote + news AVAILABLE; EODHD lowest tier = real-time OHLCV
    only (no pre-open volume baseline), Massive free = NOI 404 (plan-gated),
    short-locate/HTB = NOT AVAILABLE (out of scope, analysis-only).
  Tests: `test_preopen.py` (7, hermetic, mocked Alpaca). Full suite green.

- **Institutional workflow for value-dip + swing (Phases A-E, design
  `docs/design_institutional_value_dip_workflow.md`)** - mapped institutional
  practice (value-desk funnel, AQR-style mean reversion, risk-first tranches,
  desk risk policy, TCA, event sizing, regime switching, VCP/SEPA process,
  quant evaluation) onto the stack. ALL new rows are advisory (computed +
  injected into the LLMs); nothing gates by default (opt-in strict flags):
  - **A1 regime gate** (`strategies/regime.py::regime_gate_read`): rolling
    realized-vol percentile + fast-downtrend knife guard + catalyst window;
    new `regime_gate` row in `value_dip_setup`. Strict opt-in:
    `value_dip_regime_gate` (+ vol/downtrend/halve keys).
  - **A2 re-rating catalyst** (`value_dip.py`): `re_rating` row from REAL EPS
    surprise (earnings tool), revisions, institutional accumulation, forward
    PEG - "cheap stays cheap without a catalyst". Strict opt-in:
    `value_dip_require_catalyst`.
  - **B1 daily-loss + high-water-mark gates** (`risk_governor.govern`): new
    `daily_loss_pct` / `hwm_drawdown_pct` inputs; budget + soft/hard tiers
    (`risk_daily_loss_budget_pct`, `risk_hwm_soft/hard_pct`).
  - **B2 trade plan card** (new `strategies/trade_plan.py::build_trade_plan`):
    one markdown plan (unified stop, tranches, tiers, BE rule, trail,
    adherence checklist) compiled per run and injected into ALL 5 decision
    agents (Trader, PM, aggressive/conservative/neutral debators) via
    `graph._compiled_decision_context`, and appended to the report.
  - **B3 BE-after-confirmation** (`exits.py::breakeven_after_confirmation`,
    `breakeven_trigger` = atr|r|structure): move stop to BE only after 1R /
    higher-low - no more too-early BE.
  - **B4 stop-never-widen** (`stop_never_widen`): unified invalidation stop
    flagged in the plan card + trader prompt.
  - **C1 execution/TCA** (`pre_market.py::record_review`): arrival_price /
    fill_price / slippage_bps columns; `strategy_quality_report` gains an
    execution block (avg slippage, fill rate).
  - **C2 turnover guards** (`min_holding_days`, `max_trades_per_period`).
  - **D1 sleeve tagging** (`memory.store_decision(sleeve)` + parse): honest
    per-style attribution in `strategy_quality_report` sleeves block.
  - **D2 drift/alpha-decay monitor** (`strategy_quality_report`): rolling
    4-wk win-rate/Sharpe vs baseline; `drift_threshold`.
  - **Agent data-feeding**: every run seeds `computed_decision_context` into
    state; the 5 decision nodes cite the deterministic numbers (regime /
    re-rating / plan card / risk snapshot / decay hint) instead of inventing.
  - Config keys + env overrides + `.env.example`; web Help text updated.
  Tests: 1503 passed (2 skipped), ruff clean.

- **Value Dip + Swing enhancements (web-researched, matched to practice)** -
  research compared the setup/exit math against established swing-trading
  practice and closed the gaps:
  - **VCP halving progression** (`swing.py::vcp_setup`): the default
    `contraction_tol` is now `0.65` so each pullback must be *successively
    shallower* (reproducing the named 15%->8%->3%; ratios ~0.53/0.38), with a
    `max_final_depth` (default 8%) final-tightness gate and a `pivot` field =
    the highest high of the final contraction (the Minervini breakout buy
    point). Pass `contraction_tol=1.10` for the old permissive rule.
  - **Chandelier true-highs** (`swing.py::chandelier_exit`): accepts a real
    `highs` series so the trailing stop sits below the true 22-bar high
    (was using closes as an upper proxy); threaded through `swing_report` +
    `get_swing_exits`.
  - **Value-dip trend filter** (`value_dip.py::value_dip_setup`): adds a
    `trend` row (price >= 200-SMA and 50-SMA rising) reported when >=200
    closes; gates only when the caller opts in via `require_trend` (a value
    dip is often below its 200-SMA, so it is not a hard default reject).
  - **Stop harmonization** (`value_dip.py`): the `trade_risk` row now also
    reports `plan_stop_pct` / `plan_stop_ok` (the composite plan stop,
    ~3.5 ATR from P1) vs `max_plan_stop_pct` (8%), reconciling the setup's
    <=2% risk screen with the actual wider tranche stop.
  - **Strict-VDU** (`value_dip.py::value_dip_setup`): `strict_vdu=True`
    promotes the Step-2 VDU ladder, valuation-Z and support to hard gates
    (measured only; unknown still never fails).
  - **Configurable tranche ladder** (`value_dip.py::tranche_plan/risk_read`):
    new `steps` (ATR multiples, default 1.0/2.0) and `pct_steps` (fixed
    %-drawdown-from-P1 ladder) options.
  - **R-based breakeven** (`exits.py::stop_to_breakeven_r`): move the stop
    to break-even after `rr` x R in favor (mirrors practice of ~1R-1.5R).
  Tests: `test_strategies_value_dip` (ladder modes, trend, plan-stop),
  `test_strategies_vcp` (halving, final-tight, pivot), `test_strategies_value_style`
  (R-based BE). Docs: README, CHANGELOG.
- **Interactive CLI now applies the strategy overlays (CLI/batch parity)** -
  the interactive CLI built state directly and streamed the graph but NEVER
  called `_apply_strategy_overlays`, so a CLI report omitted the "Risk Gate
  (computed)" block, position contract and computed risk context that the
  `propagate()` (batch/API) path renders - two same-day NVDA runs diverged
  materially (batch 12:02: Hold / PT 323.37 / gate PASS vs CLI 13:48:
  Underweight / PT 188.32 / no gate block), not from LLM variance alone.
  Fix (`cli/main.py`): seed `risk_context` into the initial state BEFORE the
  Portfolio Manager (via `graph._precompute_risk_context`) and apply
  `graph._apply_strategy_overlays(final_state, ticker)` to the merged state
  before saving - the same two hooks `propagate()` uses, so the CLI report
  now carries the same gate/contract/context. Overlay failures degrade
  silently (cannot break saving, matching propagate). Tests:
  `test_cli_no_console` wiring guard (seed-before-stream, overlay-before-save).

### Fixed
- **Per-analyst tool-round cap + empty-report guard (NVDA missing market.md)** - a market/news/fundamentals analyst whose tool loop never terminates (model keeps calling tools, or a slow/hung vendor call keeps the loop spinning) previously left the analyst report empty, which reporting.py silently dropped - the run completed 'normally' with no `1_analysts/market.md` and no error. Now: `ConditionalLogic` forces the terminal report turn after `MAX_TOOL_ROUNDS` (8) tool rounds (routing back to the analyst node instead of the tool node), `structured.finalize_messages` runs that turn with the dangling tool_calls stripped (one final LLM call; truncation-retry + degrade intact), and `reporting.write_report_tree` writes an explicit "report unavailable" block (file + consolidated report) when an analyst report is empty - never a silent gap. Sequential and parallel (`analyst_concurrency>1`) analyst paths both covered. Tests: `tests/test_tool_round_cap.py` (12) + 3 reporting guard tests; ruff clean, 124 regression tests green.
- **Empty final decision after structured-output fallback** - a model that
  misses `with_structured_output` can answer the free-text retry with only a
  section header (live-run symptom: `**Decision` alone landed in
  `5_portfolio/decision.md`). `invoke_structured_or_freetext` now detects a
  degenerate stub, re-invokes once with a completion directive, and if still
  empty returns an explicit "**Decision**: unavailable" notice — never a bare
  header. Covers Trader / Research Manager / Portfolio Manager free-text
  paths. Tests: `test_invoke_structured_stub_freetext_regenerates`,
  `..._still_empty_returns_notice`, `..._retry_exception_returns_notice`.
- **End-to-end advisory-context injection (agent + report)** - the Phase A-E
  decision context (`computed_decision_context` / `risk_context`) was seeded
  onto `AgentState` but the keys were not declared as LangGraph channels, so
  native LangGraph silently dropped them: the Trader / PM / 3 risk debators
  never saw the regime gate / plan card / pre-open rows, and the report's
  `IVa. Computed Decision Context` section never rendered. Declared both keys
  on `AgentState` so they flow to the decision nodes and to `final_state`
  (report now surfaces IVa). Regression tests:
  `test_agent_state_declares_decision_context_channels` +
  `test_agent_state_carries_decision_context_through_graph` (a seeded value
  now reaches a node and the graph output).
- **Pre-market reviewer pre-open rows hidden behind news** - in
  `scripts/pre_market_review.py::_build_summary`, the pre-market RVOL /
  pre-open gap / book-depth lines were indented inside the `if news_titles:`
  block, so they only rendered when overnight headlines existed. They now
  print unconditionally (each still degrades to nothing when its data is
  unavailable), matching the design's independent-delta contract.
- **Audit-driven correctness fixes (data integrity + wiring)** - a repo-wide
  audit surfaced and fixed ~26 defects across strategies, dataflows, graph
  wiring, config, and entry points. All with hermetic regression tests.
  Correctness (HIGH):
  - `quantitative_scores.py`: Piotroski ROA point no longer awarded to
    negative-ROA firms (`if roa or 0 > 0` parsed as `roa or False`).
  - `interface.py`: `VendorRateLimitError` now recorded in `first_error`, so an
    all-throttled optional chain degrades to `DATA_UNAVAILABLE` instead of
    raising a raw `RuntimeError`.
  - `alpha_vantage_common.py`: HTTP 429/5xx / timeout mapped to
    `VendorRateLimitError` (was an untyped crash of the prime price path).
  - `strategies/dcf.py`: projects the LATEST FCF, not the historical max (a
    declining/hump series was overstated ~30-40%).
  - `strategies/technical_factors.py`: OBV bullish-divergence slice fixed
    (was always False).
  - `y_finance.py`: fundamentals/statement/insider functions re-raise instead
    of returning an "Error retrieving..." prose blob that the router cached as
    truth and never fell back from.
  - `default_config.py`: list-typed env overrides (e.g.
    `TRADINGAGENTS_TRANCHE_WEIGHTS`) coerce to the default's element type; a
    numeric list was landing as strings and silently disabling the tranche fold.
  - `market_analyst.py`/`fundamentals_analyst.py`/`news_analyst.py`: bound
    tools the prompts instruct (get_expected_move, get_institution_holdings,
    get_earnings_surprise_history, get_momentum_scan,
    get_market_snapshot_alpaca, get_insider_transactions), closing a
    no-fabrication gap (the model could not fetch those figures).
  Edge/wiring (MEDIUM):
  - `yfinance_short_interest.py` / `y_finance.py`: percent fields scaled x100
    with a `%` marker (was 100x unit drift).
  - `moomoo.py`: `_check_ret` classifies quota/throttle (incl. Chinese
    phrasing) as `VendorRateLimitError` before the permission check;
    `_moomoo_code` raises on forex/futures/non-whitelisted-crypto instead of
    returning a bogus `US.` code.
  - `pre_market.py`: `resolve_ledger` uses a stored `prior_close`
    (non-circular - was recomputing the exact review gap); `record_review` now
    stores it.
  - `size.py` `stop_loss_atr` returns None on insufficient data (was 0.0);
    `market_session.py` `opening_range` emits a target only for a real ORB
    breakout (was a below-stop short target on a flat close).
  - `normalized.py` `trap_verdict` accrual default 0.06 (consistent with
    `value_dip.decline_driver_check`; was 0.02).
  - `pipeline.py`: `_run_batch` caps workers via `batch.effective_workers()`
    (was bypassing the moomoo connection cap).
  - `value_screener.py`: `--rank composite` / `enable_composite_rank` now wired
    (were dead); eodhd-us universe truncation is warned, not silent.
  - `strategy_quality_report.py`: real `--illiq` flag + cost threading (was
    documented but rejected by argparse); `validate_massive_flat.py` returns a
    non-zero code when no CSV is present.
  - `trading_graph.py`: seeds deterministic `risk_context` into the initial
    state so the Portfolio Manager actually receives CVaR/liquidity context
    (was computed only after the graph, never reaching the PM).
  - `regime.py` `realized_vol` returns None on insufficient data
    (`factors.py` guard updated); `parabolic_sar` computes `below`/`exit` when
    a `closes` series is supplied.
  Docs/config truth:
  - `api_reference.md` §1.2/§5 + `.env.example`: strategy-overlay defaults
    aligned to code (only `enable_events`/`enable_reflection`/
    `enable_sentiment`/`enable_strategy_overlays` default True; the rest
    opt-in) - docs previously claimed default True.
  - Documented the two missing `TRADINGAGENTS_ENABLE_DECISION_AUDIT` /
    `TRADINGAGENTS_ENABLE_LIQUIDITY_GATE` overrides; corrected the stale
    `enable_sentiment` "no override / off" comment.
  - `api_reference.md` §9: batch `--vendor` eodhd, `--workers` 1-4,
    pipeline `--universe` top-movers-massive; AGENT_ONBOARDING "~40" tools.
  - `default_config.py`: marked reserved-but-not-yet-wired keys
    (`enable_regime`, `enable_factors`, `enable_threshold_gate`,
    `consensus_seeds`, `calibration_min_n`, `risk_stress_shock_pct_1/2`).
  Web (`TradingNew/trading_web`): `run_strategy_quality` now forwards `--illiq`
  (+ SPA checkbox). Tests: 1490 passed, 2 skipped; ruff clean repo-wide.

### Added
- **EODHD real-time snapshot + top movers (Massive 403 fallback)** - the
  Massive snapshot / top-movers endpoints are 403 on the free plan; EODHD's
  `/api/real-time` works on the EOD plan and now backs them:
  - `get_market_snapshot_eodhd(ticker)` - `/api/real-time/{ticker}`: live
    15-20 min delayed OHLCV + prev close + change% (the market analyst's
    "latest verified bar" + gap read).
  - `get_top_movers_eodhd(direction, count)` - `/api/real-time/{ticker}?ex=US`:
    one call returns ~18k US stocks sorted by change_p (gainers/losers +
    universe replacement).
  - `get_market_snapshot` / `get_top_movers` tools now fall back to EODHD
    when Massive returns an 'unavailable' string (403) or raises.
  - Fixed `_eodhd_get` error detection: a dict with a `code` field but no
    `message` is a normal payload (the real-time response's `code` is the
    ticker symbol), not an error.
  Tests: `test_eodhd_vendor.py` (7 new: snapshot render/no-data, movers
  sort/invalid/no-data, tool fallback x2) + `test_massive_vendor.py`
  failover updated (both-down degrades).
- **Truncation-retry enforcement (max_tokens is a ceiling, not a floor)** -
  when an LLM response is cut at the output cap (ends mid-sentence), the
  agent now re-invokes with a continuation prompt and merges, so reports are
  never truncated. Wired into every agent path:
  - `structured.py::_retry_if_truncated` (free-text fallback of PM/RM/trader/
    sentiment), `retry_chain_if_truncated` (market/news/fundamentals analyst
    tool-calling chains), `retry_llm_if_truncated` (bull/bear researchers +
    aggressive/conservative/neutral risk debators).
  - Up to 2 continuation attempts, each only when a cut was detected; a
    failed continuation degrades to the original text (never raises).
  - Tests: `tests/test_truncation_retry.py` (7).
- **Tool-wiring audit: 4 new market tools + run-level OHLCV cache + computed
  sentiment on** - the audit found strategy functions that were implemented
  but never exposed to the analyst LLMs, and duplicate OHLCV fetches across
  tools. Fixes:
  - `get_technical_factors(ticker)` (market) - ADX / pivots / Aroon / Fisher /
    Chaikin / Elder-Ray / Supertrend / volume-profile in ONE call.
  - `get_book_tail_risk(ticker, weights?)` (market) - portfolio CVaR +
    correlated -10% stress + drawdown gate (book-level tail).
  - `get_liquidation_days(ticker, shares_to_liquidate?)` (market) - days to
    absorb a block at a 15% participation cap.
  - `get_premarket_review(ticker, prior_close?, open_price?, prior_stop?,
    entry_price?)` (market) - deterministic CONFIRM / REVISE / REJECT arbiter.
  - Run-level OHLCV cache (`_RUN_OHLCV_CACHE` in analysis_tools.py): every
    tool shares ONE vendor fetch per (ticker, days) per run - no duplicate
    data / quota burn. Cleared in conftest between tests.
  - `enable_sentiment` now **True** (was False): the computed StockTwits
    score + surprise velocity is injected into the sentiment report (the
    sentiment functions existed but were never delivered).
  Tests: 8 new hermetic tool tests + cache test + market-toolnode guard.
- **Fix market tool-node binding gap + raise quick-tier output cap** -
  the market analyst's prompt lists `get_swing_exits` / `get_dip_technical` /
  `get_mean_reversion_tech` and the 5 market-session tools (`get_opening_range` /
  `get_gap_type` / `get_order_imbalance` / `get_premarket_liquidity` /
  `get_post_close_confirmation`), but they were never registered in the market
  `ToolNode` (a wiring gap from the original value-dip+swing commits) — so every
  run had the LLM call tools that error "not a valid tool" and the chandelier
  trail-stop wiring (`final_state["swing_exits"]`) was dead. All 8 are now bound
  (41 market tools). `max_output_tokens` / `max_output_tokens_quick` raised
  6000 → 8000 after 2026-08-27 WDC analyst reports truncated mid-sentence at
  the 6000 cap. Tests: `test_market_toolnode.py` regression guard (8 tools).
- **EODHD as primary OHLCV vendor + eodhd-us default universe** - the
  `core_stock_apis` chain is now `eodhd,moomoo,yfinance` (EODHD first,
  moomoo/yfinance as fallbacks); `news_data` is `eodhd,moomoo,yfinance` and
  `corporate_actions` is `eodhd,moomoo`. New EODHD endpoints on the EOD plan:
  `get_news_eodhd` (news), `get_corporate_actions_eodhd` (splits +
  dividends), `get_exchange_symbols_eodhd` (full US symbol list, ~18k common
  stocks). The value screener's default `--universe` is now `eodhd-us`
  (EODHD full-US list, no moomoo quota); `top-losers` / `heat-proxy` (moomoo
  movers) stay as the optional intraday-momentum source. Fundamentals /
  technicals / intraday / options are NOT on the EOD plan, so those chains
  keep moomoo/yfinance first. Tests: `test_eodhd_vendor.py` (14) +
  `test_value_screener.py` eodhd-us universe (1).
- **EODHD vendor (daily OHLCV)** - `dataflows/eodhd.py` serves daily bars as
  the same CSV shape yfinance/moomoo produce, registered in the
  `core_stock_apis` chain (`moomoo,eodhd,yfinance` by default) and as a
  `--vendor eodhd` preset (`batch.py`/`pipeline.py`). Key:
  `TRADINGAGENTS_EODHD_API_KEY` (in `.env`). Free tier 20 calls/day; the EOD
  plan ($19.99/mo) is 100k calls/day @ 1000/min with 30+ years history — a
  replacement for the moomoo K-line quota (100 calls/7 days) that the value
  screener exhausts. Tests: `tests/test_eodhd_vendor.py` (8).
- **Moomoo per-call timeout + value-dip gating pre-filter + web screener
  budget** - three fixes for the value-screener web timeouts:
  - `moomoo_call_timeout` (default 5.0s, env `TRADINGAGENTS_MOOMOO_CALL_TIMEOUT`):
    every moomoo SDK call now runs under a wall-clock timeout wrapper
    (`dataflows/moomoo.py::_sdk_call`) instead of the SDK's own 20s
    `ReqInfo.wait()`, so a degraded gateway can't burn 20s per call across
    hundreds of calls.
  - The value-dip gating pass runs a cheap OHLCV-only pre-filter
    (`scripts/value_screener.py::_value_dip_technical_prefilter` — RSI <= 35,
    %b <= 0.10, stop <= 2%) before the heavy fundamentals fetch, dropping the
    per-symbol vendor calls from ~7 to 1 for non-candidates.
  - The web `run_screener` capability budget is raised to 2400s (matching the
    action report's `--llm` budget) and a timed-out capability now kills its
    whole process tree (`taskkill /F /T`) so no orphaned process keeps a
    moomoo context / gateway connection open.
  Tests: `test_moomoo_vendor.py::MoomooSdkCallTimeoutTests` (5),
  `test_value_screener.py` prefilter (3), `test_backend.py` kill-tree (3).
- **Correlation-aware allocation wired into the allocation plan** -
  `portfolio.allocation_block` and the `get_allocation` analyst tool accept
  `returns_by_name` and, when `enable_correlation_penalty` is on (default
  False; `correlation_threshold` 0.6 / `correlation_penalty_frac` 0.3),
  down-weight names whose average pairwise correlation with the rest of the
  book exceeds the threshold before the per-name/per-sector caps. The
  screener's `--alloc` builds return series from the run's OHLCV cache and
  passes them through; names without a measurable series are never penalized.
  Env: `TRADINGAGENTS_ENABLE_CORRELATION_PENALTY` /
  `TRADINGAGENTS_CORRELATION_THRESHOLD` / `TRADINGAGENTS_CORRELATION_PENALTY_FRAC`.
  Tests: portfolio + analysis_tools + value_screener.
- **Industry-practice suggestions implemented (7 items)** -
  - Correlation-aware allocation: `portfolio.correlation_penalty` /
    `mean_correlation` down-weight names highly correlated with the book
    (risk-parity style).
  - Book-level stress: `book_risk.book_correlated_stress` shocks the whole
    basket together; surfaced in the risk snapshot + report risk-gate block.
  - Liquidity-aware costs: `exits.net_of_cost` / `evaluate.net_returns` accept
    an `illiq` (Amihud) param to scale cost for illiquid names.
  - Paper-ledger track record: `pre_market.ledger_track_record` measures the
    reviewer's win rate / avg realized return from resolved rows.
  - Limit-order directive: `pre_market_review.py` appends a thin-liquidity
    "prefer limit orders / reduce size" reason when the book is thin/illiquid.
  - Claim-vs-computed audit: `reporting.audit_decision_numbers` (opt-in via
    `enable_decision_audit` / `TRADINGAGENTS_ENABLE_DECISION_AUDIT`) flags a PM
    decision's Stop Loss far from the computed contract stop.
  - Strategy-quality report: `scripts/strategy_quality_report.py` reads the
    reflection + pre-market ledgers and reports net-of-cost Sharpe / drawdown /
    win rate (wired into the web raw allowlist).
  Tests: portfolio/book_risk/evaluate/pre_market/reporting/value_style.
  Full suite 1427 passed.

### Fixed
- **Moomoo exit-hang** - `dataflows/moomoo.py` had a shadowing duplicate
  `_close_all_ctxs()` (the atexit one called `ctx.close()` directly, which
  can block on the dead receive loop and keep the process alive after
  `main()` returns). Removed the duplicate; the daemon-thread + timeout
  version is the only one. Added `close_context()` to the end of
  `value_screener.py`, `action_report.py`, `capital_income_screener.py` and
  `pre_market_review.py` main() so the moomoo context closes while the
  process is healthy (the graph already did this). A screener run that
  previously hung ~15 min after writing its report (web job timed out) now
  exits cleanly. Regression test: `test_close_all_ctxs_uses_daemon_thread_timeout`.

### Added
- **Value-dip + swing + pre/post-market research implementation** -
  - `technical_factors.py`: 6 new pure factors - `aroon` (trend age),
    `fisher_transform` (normalized reversal), `chaikin_oscillator` (buying
    pressure), `elder_ray` (bull/bear power), `supertrend` (ATR trailing),
    `volume_profile` (POC + value area). All return None on insufficient data.
  - `market_session.py` (new): `opening_range` (ORB breakout + 2R stop/target),
    `gap_type` (common/breakaway/runaway/exhaustion + fill stats),
    `order_imbalance` (buy/sell-heavy from flow nets), `premarket_liquidity`
    (thin-book warning), `post_close_confirmation` (stopped-out/target-hit/hold).
  - 5 new market-analyst tools: `get_opening_range`, `get_gap_type`,
    `get_order_imbalance`, `get_premarket_liquidity`, `get_post_close_confirmation`
    (bound to the market analyst + prompt directives).
  - Screener columns: `Aroon`, `Fisher`, `Supertrend`, `POC` (volume profile).
  - Tests: `test_strategies_market_session.py` (30) + extended
    `test_strategies_technical_factors.py` (17 new).
- **Conditional action report** - `scripts/action_report.py` checks report
  verdicts against the risk basket (`TRADINGAGENTS_RISK_BASKET_WEIGHTS`):
  basket names are kept on their newest Underweight/Sell verdict (reduce/trim),
  non-basket names on their newest Overweight/Buy verdict (add). The report's
  stated condition (re-entry level, trim zone, scale-in confirmation) is
  extracted from Position Size + Executive Summary and checked against live
  OHLCV via the vendor chain — deterministic MET / NOT_MET / UNKNOWN, never
  fabricated. Stop/ATR levels are informational; unmeasurable qualifiers
  (PUC, VDU trigger, stabilization) render UNKNOWN. Optional `--llm` invokes
  a deep-think judge (`ActionConditionVerdict` schema +
  `overrides/action_condition_judge.py`) for UNKNOWN conditions. Output: a
  final action report (ADD/BUY, TRIM/REDUCE, MONITOR) printed + saved
  (keep-only-newest). Tests: `tests/test_action_report.py` (21).
- **Screener: full 11-SPDR sector ranking table** - `_sector_table_markdown`
  renders the whole sector ranking (ETF, name, 1m/3m returns, rank, top-3
  flags) and appends it to the report whenever the ranking is computed
  (`--sector-rank` / `--enrich-sector`). The watchlist previously showed only
  the candidate's SecRank column; now the reader sees the full table the
  framework's "top 3 of 11 SPDR groups" rule is based on. Rows without
  history render n/a and never rank top-3. Tests:
  `test_sector_table_markdown_renders_full_ranking` +
  `test_enrich_sector_populates_without_gating` (asserts the table appears).
- **Report truncation marker** - `reporting._finalize_section` appends a
  visible blockquote marker when a section ends mid-sentence (LLM max_tokens
  cut), so the reader knows the tail is missing at the LLM layer, not a file
  bug. Conservative heuristic: only bare lowercase/digit endings >= 120 chars
  that aren't sentence punctuation, markdown constructs, or bold-label lines
  (`**Consensus**: High`). Applied to every section file + the consolidated
  report. Tests: `test_truncation_marker_appended_to_mid_sentence_sections` +
  `test_finalize_section_roundtrip`.
- **Web: value-dip + swing tools page** - `trading_web` gains a `run_value_tools`
  capability (in-process, read-only) and a "Value tools" SPA page that runs
  `get_value_floors` / `get_swing_exits` / `get_dip_technical` /
  `get_mean_reversion_tech` for one ticker — the same computed numbers the
  analyst LLMs are bound to, inspectable before queueing a full run. Also
  fixed a pre-existing flaky web test: `security._secret()` read the secret
  file back with `.strip()`, which silently dropped a leading/trailing
  whitespace byte from the 32 random bytes and intermittently invalidated
  every session cookie (401s). Tests: `test_value_tools_capability_registered_and_guarded`
  + `test_secret_file_roundtrip_preserves_whitespace_bytes`.
- **Per-role max output tokens + density directives** -
  - Config: `max_output_tokens` (6000), `max_output_tokens_quick` (6000),
    `max_output_tokens_deep` (2500) + env overrides
    `TRADINGAGENTS_MAX_OUTPUT_TOKENS(_QUICK/_DEEP)`.
  - `openai_client._PASSTHROUGH_KWARGS` now forwards `max_tokens` (OpenAI /
    OpenRouter); Anthropic / Bedrock already did. `trading_graph` passes the
    per-tier value (quick vs deep) to each client.
  - `get_output_budget(section)` in `agent_utils`: per-role prompt directive
    (dense, bounded ~250-1400 words by role; tool-call-first: never approximate
    a number that a tool can return). Wired into all 12 agent prompts
    (4 analysts, bull/bear, 3 risk debators, RM, PM, trader).
  - Values grounded in your formula `min(1,048,576, 1,310,720 - input)` +
    measured per-role report maxes (analysts ~5k, RM 1.9k, trader .7k, PM 1.4k).
  Tests: `test_openai_compatible_provider` (max_tokens passthrough + budget
  helper). Docs: api_reference env table, .env.example, README, CHANGELOG.
- **OpenRouter provider-ignore routing** - `TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS`
  (.env, comma-separated provider slugs) lets you block slow/unreliable
  OpenRouter endpoints for every request. The list is sent as `provider.ignore`
  in the OpenRouter Chat-Completions body via `extra_body` (nested under the
  `provider` key, per OpenRouter's provider-routing docs). Applied only when
  `llm_provider=openrouter` and the list is non-empty; erased if empty.
  `default_config._ENV_OVERRIDES` coerces the CSV string to a list; default `[]`.
  Tests: `test_openai_compatible_provider` (3: payload present, empty omitted,
  non-openrouter ignored). Docs: api_reference env table, README, CHANGELOG.
- **Free computed ratios (no paid Massive plan)** - `strategies/ratios.py`
  replicates the plan-gated Massive `get_ratios` block from the project's own
  canonical statements: EV, EV/EBIT, EV/EBITDA, EV/Sales, P/E, P/B, P/S,
  P/CF, P/FCF, ROE, ROA, D/E, Current, Quick, cash ratio, dividend yield, FCF,
  market cap. Exposed as `get_ratios` on the fundamentals analyst (computed =
  free; missing inputs render n/a, never fabricated). Adds the `inventory`
  canonical alias so Quick ratio computes. Also fixes a latent double-`@tool`
  decorator bug in `analysis_tools.py` that broke import once the file grew.
  Tests: `test_strategies_ratios` (6 pure) + `test_analysis_tools` (2 tool).
  Docs: api_reference 6.4, developer/04, tests-layout.
- **SEC EDGAR -> Massive insider fallback** - `get_sec_filings` (`agents/utils/
  market_position_tools.py`) now falls back to Massive's `get_form4_insider_massive`
  (Form 4 open-market insider transactions) whenever official SEC EDGAR is
  unavailable: HTTP 403 from SEC fair-access throttling, network failure, or a
  non-US ticker with no EDGAR record (which previously surfaced as
  `NO_DATA_AVAILABLE` / a raised error and degraded the signal). The fallback
  text is explicitly labelled "Massive insider-activity fallback (Form 4 — NOT
  the 8-K/10-K/S-1 set)" so the agent never confuses the datasets; if Massive
  also returns nothing it degrades to an explicit unavailable message (no
  fabrication). Bound to the news analyst's `get_sec_filings` tool + prompt.
  Tests: `test_market_toolnode` (5 fallback cases: EDGAR ok, raise-on-403,
  no-data sentinel, insider body, both-down degrade). Docs: api_reference
  §6.2, data-providers, README, AGENT_ONBOARDING.

- **Web UI (sibling project, not in this repo)** - `TradingNew/trading_web/`
  adds a React SPA + FastAPI web front-end over every TradingAgents capability
  (batch / pipeline / screener / pre-market / nightly / decision-history /
  report viewer / raw read-only), with security-first auth: scrypt password
  hashes, HMAC-SHA256-signed session cookies, CSRF double-submit, login
  lockout, strict path defense on report reads, an allowlisted raw-command
  shell, CSP + security headers, and a JSONL audit log. Serves the SPA from
  the FastAPI backend; 127.0.0.1:8000 by default with `TRADINGAGENTS_WEB_*`
  overrides for a later public deployment. See
  `TradingNew/trading_web/README.md` (not tracked by this repo, per the
  layout rule).

- **Pre-market review (overnight reviewer)** - closes the gap between a
  close-time decision and the next open (design `docs/pre_market_review.md`,
  choice (a)):
  - `strategies/pre_market.py` - deterministic deltas + verdict arbiter:
    `premarket_gap` (gap % / ATR, through-stop / adverse-fill detection),
    `catalyst_window_read` (B1 hard-block / window tighten),
    `reanchor_plan` (tranche re-anchor with per-trade + book caps),
    `review_decision` (CONFIRM / REVISE / REJECT from measured deltas only),
    `load_prior_state` (fail-open loader for `full_states_log_*.json` +
    `5_portfolio/decision.md`).
  - `PreMarketVerdict` schema + `agents/overrides/pre_market_reviewer.py` - a
    deep-think prompt variant (reuses the PM's LLM; no new graph node) that reads
    the prior decision + a number-only deltas summary and emits a structured
    verdict; the deterministic REJECT is never downgraded by the LLM.
  - `scripts/pre_market_review.py` - standalone pre-open path (gap/anchor),
    default = newest report folder, `--prior-date` / `--report-dir` overrides,
    `--skip-llm` (deterministic only) / `--dry-run`.
  - `batch.py` - opt-in same-night step (`enable_pre_market_review`): after each
    symbol's report, a catalyst/quality re-check writes `pre_market_review_<date>.md`
    next to the report; never fails the symbol.
  Config: `enable_pre_market_review` (+ `TRADINGAGENTS_ENABLE_PRE_MARKET_REVIEW`).
  Tests: `test_strategies_pre_market` (pure, 19) + `test_pre_market_review`
  (script + batch, 3). Docs: `docs/pre_market_review.md` status -> implemented.
- **Pre-market review follow-up: defect fixes + 6 features** -
  - Fix 1: the standalone script now extracts the prior plan's entry/stop
    (`parse_planned_levels`) and re-anchors the tranche plan to the measured
    open, so the gap / through-stop / adverse-fill / cap-breach checks in
    `review_decision` actually run (previously the stand-alone passed no
    `prior_stop`/`reanchor` and degenerated to catalyst-only).
  - Fix 2: `batch._batch_pre_market_check` passes `results_dir`, so the
    same-night step finds the full state JSON (not just `decision.md`).
  - Fix 4 (+ feature 1): `_fetch_deltas` prefers a real-time pre-market price
    (Alpaca `get_intraday` when `enable_alpaca`, else yfinance
    `fast_info.last_price`) over the daily close, and adds ATR(14).
  - Feature 2: `scripts/nightly_review.py` drives pre-open reviews from the
    latest `reports/batch_summary_*.jsonl`.
  - Feature 3: paper-book ledger (`data_cache_dir/pre_market_ledger.jsonl`)
    via `record_review` / `resolve_ledger` (pending -> realized return).
  - Feature 4: `scripts/decision_history.py` prints a per-ticker decision
    series from the per-date `full_states_log_*.json` files.
  - Feature 5: guarded overnight-headline context (`_headline_delta`) into the
    reviewer summary (never a hard gate, titles only).
  - Feature 6: scheduler notes (cron / Task Scheduler) in
    `docs/pre_market_review.md` §15.
  Tests: `test_strategies_pre_market` + `test_pre_market_review` extended
  (planned-levels parse, results_dir lookup, headline delta, decision history,
  nightly driver). Full suite green; ruff clean.

### Added

- **Capital-income screener: live `--universe preferred-top` + `--refresh`** -
  the free providers don't expose a validated 500-symbol preferred list, so
  the standalone screener now seeds its universe at runtime from the top
  holdings of the major preferred ETFs (PFF / PFFD / PGF / PGX / PFFV) via
  yfinance `get_funds_data().top_holdings` (no key). Every candidate is
  validated during the run (price + dividendRate); only names that resolve
  are ranked. `--refresh` writes the validated set back to the universe file
  (header preserved), so the curated list stays current without manual edits.
  Tests: `test_capital_income_screener` (universe mode + refresh write-back).
  Full suite 1311 passed / 2 skipped; ruff clean.

- **Standalone preferred-income screener (Strategies/capital_income.md)** -
  a new self-contained screener that does NOT wire into the trading graph or
  any agent. Implements the Global X U.S. High Yield Preferred Index
  methodology: (1) liquidity/quality screen (market cap >= $250M AND 3m ADTV
  >= $1M), (2) indicated-dividend-yield ranking (annualized dividend / price,
  top 50), (3) MV weighting (or equal-weight fallback when per-issue shares
  aren't exposed - preferreds report no per-issue market cap) with the 3% cap
  + pro-rata renormalization.
  - `strategies/capital_income.py` - pure math (annualized dividend, indicated
    yield, ADTV dollar, liquidity gate, top-N, MV/equal weights, cap +
    renormalize). No-fabrication: None on missing input.
  - `scripts/capital_income_screener.py` - standalone CLI (positional/--file
    universe, --top, --min-mcap, --min-adtv, --out-dir, --dry-run, --json);
    pulls price + dividendRate + market cap + OHLCV via yfinance + the vendor
    chain. Uses `info.dividendRate` (pre-annualized) - never the trailing-12m
    sum, which preferreds pollute with special distributions.
  - `Strategies/preferred_universe.txt` - seeded ~24 liquid US preferreds
    (hyphenated Yahoo symbols that resolve with a dividendRate).
  Tests: `test_strategies_capital_income` (10 pure) + `test_capital_income_screener`
  (5 hermetic, mocked yfinance/OHLCV, asserts no graph/agent imports). Full
  suite green; ruff clean.

- **Liquidity gate on by default + surfaced in PM prompt & risk report** -
  `TRADINGAGENTS_ENABLE_LIQUIDITY_GATE=1` is set in `.env` (on by default), so
  the risk governor now REJECTs ILLIQUID names / WARNs on CAUTION ones using
  the risk2.md metrics. The computed liquidity block is surfaced in two places:
  - the **Portfolio Manager prompt** - a `Computed liquidity` line (verdict +
    ILLIQ + float-turnover + IWF + reasons) grounds the PM's liquidity/sizing
    language and instructs scaling size down (or to 0%) on CAUTION/ILLIQUID;
  - the **risk report** (`Risk Gate (computed)` block) - shows `Liquidity
    verdict` + ILLIQ / float-turnover / IWF + reasons when the gate computed it.
  Both degrade gracefully (no line) when the gate didn't run or had no data.
  Tests: `test_reporting` (liquidity block render + PM prompt wiring). Full
  suite 1291 passed / 2 skipped; ruff clean.

- **Liquidity & ownership risk (Strategies/risk2.md)** - implements the five
  institutional risk metrics as a pure, offline module
  (`strategies/liquidity_risk.py`): free-float factor (IWF), float turnover
  (ADV / float), Amihud ILLIQ (price impact per $ traded), days-to-absorb
  (overhang), and ownership HHI (concentration), plus a composite
  LIQUID / CAUTION / ILLIQUID verdict. No-fabrication: every metric returns
  None on missing input.
  - **Risk governor gate (opt-in)**: `govern()` accepts a liquidity verdict;
    ILLIQUID REJECTs, CAUTION WARNs. Enabled via `enable_liquidity_gate`
    (default False - preserves current behavior); the graph computes the
    verdict from vendor OHLCV + float + shares when on.
  - **Analyst tools**: `get_liquidity_risk` (market analyst) and
    `get_ownership_concentration` (fundamentals analyst, HHI best-effort -
    n/a when no per-holder breakdown) + prompt directives.
  - **Screener columns**: `ILLIQ` / `FltTurn` / `IWF` added to the report
    (pure-calculable from OHLCV + float + shares) + legend entries.
  Tests: `test_strategies_liquidity` (16 pure), governor liquidity cases,
  tool cases. Full suite green; ruff clean.

- **Screener: fill the n/a columns (compute + enrich)** - most columns were
  blank because they were gated behind a scan mode or a CLI flag, not because
  the data was missing:
  - **Piotroski F-Score now computes** - added `enrich_screen_ratios` in
    `statement_parsing` which derives the ratio inputs no vendor row provides
    directly (`roa`, `leverage`, `current_ratio`, `gross_margin`,
    `asset_turnover`, `shares_issued`, with prior periods) from the canonical
    statements the chain already fetches, so the F column (previously always
    `n/a`) computes from the moomoo data (- in a live AAPL run F=7, was n/a).
  - **`--scan all` now fills every technical column** - a new
    `_compute_scan_row` helper runs all scan buckets (TrendPB/Breakout/RSI +
    momentum `Pills/Pull/RR` + `Swing/RS/Stp/T2` + `VCP/Brk` +
    `VDip/FCFy/RSI/%b/Stp%`) for every symbol on the default `all` mode, so a
    standard positional run shows these columns instead of `n/a`. Added shared
    run-wide OHLCV/float/benchmark caches (reset per run) so the movers
    gating and the results loop fetch each symbol's OHLCV once. Dedicated
    `--scan <mode>` still filters (now also honoured on the positional path).
  - **New non-gating enrich flags** - `--enrich-sector`, `--enrich-rev`,
    `--enrich-inst` populate `Sec/SecRank`, `RevUp` and `Inst` without the
    filtering that `--sector-rank` / `--revision` / `--inst-accum` apply.
  - `Name` stays mover-metadata-only (classic path shows `n/a`) and
    `L1Px/VWAP1m/1mVol` stay behind `--intraday` (Alpaca cost) by design.
  Tests: F-score derivation, a positional `--scan all` that populates the
  technical columns, and `--enrich-sector` without gating. Full suite 1265
  passed / 2 skipped; ruff clean.

- **Screener FMP 429 rate-limit noise - normalized enrichment now uses the
  vendor chain** - the value screener's ``normalized_score()`` enrichment
  (columns ``nebit_ev_ebit`` / ``pe_pct5`` / ``fmp_ev``) fetched multi-year
  income + enterprise-values straight from FMP, so on the free tier it
  logged ``fmp income-statement: status 429`` / ``fmp enterprise-values:
  status 429`` warnings every run and blanked those columns. ``income_series``
  (new in ``statement_parsing``) now extracts 2+ annual
  ``{year, revenue, ebit, net_income}`` rows from the income statement the
  vendor chain already returns (moomoo markdown period tables or yfinance
  CSV), and ``normalized_score`` computes NEBIT / EV / EV-NEBIT from that +
  canonical fundamentals (market cap, debt, cash), reconstructing the 5y
  P/E percentile best-effort from historical closes x current shares. FMP is
  now only a last-resort fallback when the vendor chain has no income history
  AND an FMP key is set. No more 429s on the default moomoo,yfinance chain;
  the columns compute offline. Tests: `test_fmp` (vendor-chain normalized
  score, fmp_get never called on the default path, no-income degrade, CSV
  income series), `test_statement_parsing` (markdown + CSV income_series).
  Live: AAPL -> ev_nebit 33.96 / pe_pct5 0.75 with no FMP key.

- **Yahoo can't resolve moomoo's dotted US share-class symbols** - moomoo's
  US movers rank returns dotted share classes (`PBR.A`, `MOG.A`, `MOG.B`) but
  Yahoo only resolves the hyphen form (`PBR-A`, `MOG-A`, `MOG-B`, `BRK-B`), so
  yfinance (the second vendor in the default `core_stock_apis=moomoo,yfinance`
  chain) degraded those symbols to "Quote not found / possibly delisted" when
  moomoo couldn't serve them. `normalize_symbol` now converts a dotted
  single-letter US share-class suffix (`.A`/`.B`/`.C`/`.D`/`.K`...) to the
  Yahoo hyphen form, while leaving the `.L` London exchange and all multi-letter
  exchange suffixes (`.SA` Brazil, `.TO`, `.AX`, `.HK`, `.NS`, `.BO`, ...) untouched.
  Because moomoo's `_moomoo_code` doesn't use `normalize_symbol`, moomoo still
  receives the raw dotted form it understands (its own origin format), and the
  yfinance-facing paths hyphenate locally - so both vendors resolve. Also fixes
  manually-typed `BRK.B`/`BF.B` and the graph's `_fetch_cached_history` for
  dotted US share classes.
  Tests: `test_symbol_utils` (share-class dot->hyphen, idempotent hyphen,
  London/multi-letter exchange suffixes kept, plain/US futures unchanged).
  Verified live: `get_stock_data` now returns rows for MOG.A/PBR.A/MOG.B
  through the default chain (was empty). See docs/api_reference §5 symbol table.

- **Installed-CLI import bug: analyst tools could not find `scripts/`** -
  the agent analysis tools imported the vendor-output -> canonical parsing
  helpers from `scripts.value_screener`, but the installed `tradingagents` CLI
  wheel ships only `tradingagents*` and `cli*` (no `scripts/` on `sys.path`),
  so every DCF / fcf-yield / z-score / ratios / earnings-quality call degraded
  to `No module named 'scripts.value_screener'` (DCF) or a bare
  "unavailable ... from the vendor chain". The parsing layer moved to
  `tradingagents/dataflows/statement_parsing.py` (pure parsers + canonical
  aliases + `fetch_ticker`/`screen_ticker`), `scripts/value_screener.py`
  re-exports the same names (backend CLI + tests unchanged), and all 14 tool
  import sites now load from the package module. In a real NVDA run the three
  symptoms became: DCF returns a fair value (WACC from Beta, shares from
  market cap/close), fcf-yield returns a computed yield band, z-score compute
  from 4 real moomoo periods.
- **DCF tool: moomoo-markdown cashflow support** - `_dcf_fcf_series` only
  parsed yfinance-style CSV rows, so with moomoo (the default first vendor)
  serving `get_cashflow` the DCF degraded to "no usable free cash flow"
  series. It now parses moomoo per-period markdown tables too (Free Cash Flow
  row, else OCF - capex, positive-only, chronological), falling back to the
  CSV parser.
- **DCF market-cap / beta / shares resolution** - `get_dcf_valuation` now
  resolves the financial background with the screener-grade `fetch_ticker`
  (fundamentals + balance sheet + income + finnhub gap-fill) instead of a
  single raw `get_fundamentals` call, so market cap / shares resolve even
  when moomoo's statements have no "Market Cap" row; new canonical aliases
  `beta` and `shares` (shares outstanding / diluted / weighted-average) mean
  provider betas are no longer silently dropped to 1.0.
  Tests: `tests/test_statement_parsing.py` (new; imports + parsers + aliases
  + scripts re-export parity), moomoo-markdown DCF case in
  `test_analysis_tools`, hermetic-router updates across the screener/growth/
  scan/v2-v5/alpaca suites (patch `statement_parsing.route_to_vendor`
  alongside `scripts.value_screener`). Full suite 1250 passed / 2 skipped;
  ruff clean.

- **Blank-symbol yfinance hardening** - a whitespace/empty ticker reaching a
  yfinance entry point (e.g. a malformed LLM tool call during
  `batch.py --symbols ...`) used to canonicalize through `normalize_symbol`
  unchanged (`' '` stayed `' '`), hit `yf.Ticker(' ')`, and leak
  `TypeError: 'NoneType' object does not support item assignment` plus noisy
  yfinance HTTP-404/400 ERROR logs. `normalize_symbol` now canonicalizes
  blank/whitespace to `""`, and a new `require_symbol` helper raises the
  typed `NoMarketDataError` (`detail="blank/empty ticker symbol"`) at every
  yfinance entry point (`y_finance` statements/stock/insider,
  `stockstats_utils.load_ohlcv`, `yfinance_options`, `yfinance_short_interest`,
  `yfinance_news`) plus the graph's `_fetch_cached_history`. The router now
  returns one clean `NO_DATA_AVAILABLE: ... blank ticker ...` sentinel the
  agents can report honestly instead of a raw TypeError. Tests:
  `test_symbol_utils` (blank canonicalization + `require_symbol` raises),
  `test_vendor_routing` (blank -> sentinel across the chain).

### Added

- **Value Dip Step-1/Step-2 gap strategies** - five more deterministic
  calculators in `tradingagents/strategies/value_dip.py` close the original
  doc's gaps (`Strategies/Value_Dip_swing.md`):
  - **balance_sheet_health** - D/E < 1.0 OR current ratio > 1.5 (§1 gate),
  - **profitability_quality** - positive FCF AND ROE > 15% (§1 gate),
  - **Step-2 technical ladder** - `macd_divergence` (Daily RSI-14 / MACD-
    histogram bullish divergence or higher-low), `volume_dry_up` (VDU near
    support), `trigger_candle` (RVOL >= 1.3x + close above prior high /
    engulfing), `higher_low_structure`, composed by `vdu_entry_setup`,
  - **support_structure** - multi-month consolidation base low / 200-day SMA
    proximity (200+ closes),
  - **decline_driver_check** - the negative-force screen (clean / caution /
    structural) proxying moat/regulatory red flags with measurable signals
    (trap-HIGH, Sloan accruals > 6%, negative 12-1m momentum, non-positive
    FCF/ROE, severe EPS decline) - a `structural` verdict rejects the dip.
  Exposed as five new analyst `@tool`s: `get_macd_divergence` /
  `get_vdu_entry_setup` / `get_support_structure` (market), `get_balance_sheet_
  health` / `get_decline_driver_check` (fundamentals). `value_dip_setup` and
  the `--scan value-dip` screener now gate on balance-sheet + profitability
  when measured (unknown rows ignored, repo convention). Hermetic tests:
  `test_strategies_value_dip` (new gap cases) + `test_analysis_tools` (5
  tool cases).

- **Tranche risk fold for the risk governor** - the Value Dip + Swing tranche
  plan is now a *control* computation, not just a planning one:
  `strategies/value_dip.py::tranche_risk_read` derives the worst-case measures
  from the measured close (P1) + config-frozen weights / stop multiple / risk
  budget / account (never the LLM), and the governor enforces:
  - **peak-deployed-at-scale-in** (sum of per-tranche capital at full scale-in,
    typically > risk budget because capital is added near the lows) against the
    per-trade cap - the missing check neither the standalone tool nor the
    single-entry governor performed;
  - **capital-at-risk** (sum of per-tranche losses at the hard stop, == the
    risk budget by construction) via `govern()`'s new
    `capital_at_risk_pct`/`risk_cap_pct` check;
  - `build_position_contract` accepts an `entry_price` hook (the weighted
    tranche entry) so the G1 dollar stop/risk matches the tranche execution;
  - the report's `Risk Gate (computed)` block shows `Tranche peak-deployed` /
    `Tranche capital-at-risk` (+ cap-ok) when the fold ran.
  Config: `enable_tranche_risk` (default False), `tranche_weights`,
  `tranche_stop_mult`, `tranche_risk_pct`, `tranche_account` +
  `TRADINGAGENTS_*` env overrides. Tests: `test_strategies_risk_governor` (5),
  `test_strategies_contract` (2), `test_strategies_value_dip` (graph wiring,
  4 + pure 5), `test_reporting` (1).

- **Value Dip + Swing hybrid** - new `tradingagents/strategies/value_dip.py`
  implements the missing calculations from `Strategies/Value_Dip_swing.md` +
  `Value_Dip_swing_Continue.md`: Bollinger %b, historical valuation Z-score
  (vs own trailing P/E / EV/EBITDA / P/FCF), FCF yield, breakeven win rate /
  per-trade expectancy, the 3-tranche scale-in plan (P1/P2/P3 at 1.0/2.0 ATR,
  weighted avg entry, composite stop P3-1.5ATR, capital-at-risk check, 1.8R /
  3.0R targets + blended R:R), and the hybrid allocation matrix
  (`value_dip_setup`). Exposed as six analyst `@tool`s
  (`get_bollinger_pct_b` / `get_tranche_plan` / `get_trade_expectancy` on the
  market node; `get_fcf_yield` / `get_valuation_z_score` / `get_value_dip_setup`
  on the fundamentals node) and as a new `--scan value-dip` screener mode
  (`VDip` / `FCFy` / `RSI` / `%b` / `Stp%` columns). Config: `enable_value_dip`
  (+ `TRADINGAGENTS_ENABLE_VALUE_DIP`). Hermetic tests:
  `tests/test_strategies_value_dip.py` + `tests/test_analysis_tools.py`
  (value-dip cases).

- **Risk basket cash-remainder semantics** - `book_risk.portfolio_cvar` now
  treats a weight sum `< 1.0` as "weights + implicit zero-return cash": the raw
  weights are used (not renormalized), so the mixed daily series is scaled by
  the invested fraction and the portfolio CVaR is diluted by the cash sleeve.
  Weights summing `> 1.0` are still clamped to a valid portfolio. This is what
  makes "include cash as overall portfolio" (e.g. `risk_basket_weights` summing
  to ~0.68 with the rest in SPAXX/cash) actually lower the gate's tail budget.
  Tests: `test_strategies_book_risk` (2: sub-unity dilution + over-allocated
  clamp).

- **Risk Gate renders both CVaRs (analyzed-name + book)** - when a risk basket
  is configured, the report's `Risk Gate (computed)` (and compact verdict mode)
  now shows `Analyzed-name CVaR` (the analyzed ticker's own daily tail) next to
  `Portfolio (book) CVaR — this fed the gate` (the weighted-basket CVaR that is
  actually compared to the budget). The same comparison is computed-injected
  into the Portfolio Manager prompt as `**Computed daily-tail CVaR**`, so the PM
  grounds tail-risk/sizing language in these numbers (no `risk_context` on the
  state → the PM line is omitted, keeping old prompts unchanged). The graph
  writes `final_state["risk_context"] = {single_cvar, book_cvar}` when the
  governor runs. Tests: `test_reporting` (2: both-CVaR block + no-basket
  single-only), `test_structured_agent_prompts` (2: PM prompt injects both,
  omits when absent).

- **True portfolio CVaR for the risk governor (R2)** - the governor's daily-era
  tail budget now uses the *weighted basket's* historical CVaR when configured:
  new config keys `risk_basket_tickers` (list) + `risk_basket_weights` (dict,
  optional) + `TRADINGAGENTS_RISK_BASKET_TICKERS` / `TRADINGAGENTS_RISK_BASKET_WEIGHTS`
  env overrides. `book_risk.portfolio_cvar()` mixes each name's daily log-return
  series (aligned by index, weights normalized) and takes the historical CVaR of
  the weighted book, replacing the single analyzed name's series. Falls back to
  the single-name behavior when the basket is unconfigured or unresolvable (`>2`
  names with `>=5` aligned returns). Env coercion now handles list/dict values
  (comma-split / `k=v` pairs / JSON). Tests: `test_strategies_book_risk` (3),
  `test_env_overrides` (4), `test_strategies_catalyst` (1).

- **Session-discipline & earnings-quality analyst tools** - two more
deterministic strategies exposed as `@tool`s so the analysts cite computed
numbers instead of guessing: `get_session_discipline` (market node; wraps
`momentum.session_flags` + `psych_level` + `past_optimal_window` into an
intraday walk-away read: giveback, max-daily-loss, past the 10:00 ET optimal
window) and `get_earnings_quality` (fundamentals node; wraps
`normalized.accruals_ratio` + `trap_verdict`, surfacing the Sloan accruals
ratio - which `scripts/value_screener.screen_ticker`'s own trap call drops - as
an evidence trigger). Both bound in `_create_tool_nodes` + their analyst's
tool list/prompt, re-exported from `agent_utils`, and hermetic-tested in
  `tests/test_analysis_tools.py` (6 cases). Docs: `api_reference.md` §6.1/6.4
(tool list + table rows), README, CHANGELOG.

- **Docs backfill (missing env keys)** - documented the two `TRADINGAGENTS_*`
  env overrides (`ENABLE_MASSIVE_FLAT`, `MASSIVE_FLAT_DIR`) that were in code
  but absent from `api_reference.md` §1.1's env→config table; synced
  `.env.example` for `TRADINGAGENTS_MASSIVE_API_KEY` and the runtime toggles
  `TRADINGAGENTS_DISABLE_REDDIT` / `TRADINGAGENTS_MOMENTUM_OFFLINE` /
  `TRADINGAGENTS_MOMENTUM_NO_INTRADAY`.

- **Per-test timers (pytest-timeout)** - every test now carries a deadline so
  a hung vendor/network call can never block the whole session indefinitely:
  global 180s per-test default (thread method) + 30-minute session cap in
  `[tool.pytest.ini_options]`, and a 600s module-level `pytestmark` override
  for the modules that legitimately run live vendor calls end-to-end
  (`test_value_screener`, `test_scan_strategies`, `test_growth_screens`,
  `test_structured_agents`; 12-62s/test measured). `pytest-timeout>=2.4` added
  to the `[dev]` extra. Docs: `docs/developer/10-tests-layout.md`.

- **Credit-stress read (FRED ICE BofA OAS)** - `strategies/credit_spread.py`
  (`credit_stress_level`) plus a `get_credit_spread_read(date)` tool bound to
  the market analyst: pulls the three ICE BofA US high-yield option-adjusted
  spreads from FRED (`hy_oas`=BAMLH0A0HYM2, `ccc_oas`=BAMLH0A3HYC,
  `bb_oas`=BAMLH0A1HYBB, new aliases in `dataflows/fred.py::MACRO_SERIES`)
  and flattens them into a deterministic credit-cycle band (low/moderate/
  high/severe) + a 0..1 de-risk scale. Thresholds follow the credit-cycle
  table: HY <3% low / 3.5-4.5% moderate / >5.5% severe; CCC <8% low /
  10-12% moderate / >15% severe. The CCC spread is the leading risk-off
  sentinel. Degrades to an explicit 'unavailable' when FRED_API_KEY is unset
  (no-fabrication). Tests: `tests/test_strategies_credit_spread.py` (7),
  `tests/test_fred.py` (1), `tests/test_analysis_tools.py` (3).

- **Second decision-tool batch (sector/quality/safety/composite/tail)** -
  five more deterministic `strategies/*` functions exposed as analyst
  `@tool`s — `get_sector_rank` (11-SPDR 1m/3m momentum ranking + the
  ticker's sector standing; market node), `get_strategy_quality` (net CAGR,
  annualized vol, Sharpe, max drawdown over the price-derived or provided
  return series; market), `get_margin_of_safety` ((intrinsic - price)/
  intrinsic band, wide/modest/negative; fundamentals), `get_composite_rank`
  (cross-sectional value+momentum composite percentile vs industry peers;
  fundamentals), `get_tail_risk` (historical VaR/CVaR tail budget + -10%
  uniform stress loss; market). Each wraps an existing deterministic
  function, is bound to the market / fundamentals tool nodes and analyst
  prompts, and is hermetic-tested in `tests/test_analysis_tools.py` (12 new
  cases). No config or topology change; all degrade to an explicit
  'unavailable' per the no-fabrication contract.

- **DCF valuation tool** - `strategies/dcf.py` (pragmatic FCF-DCF: WACC via
  CAPM, Gordon terminal value, EV-to-equity bridge) + `get_dcf_valuation`
  tool bound to the fundamentals analyst. Provider-sourced inputs: free cash
  flow (from the cashflow statement chain), 10y Treasury (risk-free), beta,
  shares/cash/debt. growth/ERP are analyst overrides; degrades to
  "unavailable" when there is no usable FCF. Based on
  `Strategies/Discounted_Cash_Flow.md`. Tests in
  `tests/test_strategies_dcf.py` (8) + `tests/test_analysis_tools.py` (2).

- **Massive no-data failover fix** - the direct Massive tool wrappers
  (`get_short_volume`, `get_market_snapshot`, `get_top_movers`,
  `get_massive_news`) now catch `NoMarketDataError` and return an explicit
  "unavailable" string instead of letting the exception abort the analyst node
  and fail the whole batch symbol. Fallback to moomoo/yfinance now happens
  inside the report instead of crashing the run. Regression tests in
  `tests/test_massive_vendor.py::MassiveFailoverTests` (8).

- **Data providers doc (`docs/developer/12-data-providers.md`)** - catalogs
  all **13 data providers** the project uses: the 8 routed vendors
  (`yfinance, fred, polymarket, alpha_vantage, finnhub, sec_edgar, moomoo,
  massive`) plus 5 direct sources (Alpaca, FMP, Reddit, StockTwits,
  float_shares), with per-category `data_vendors` chains, Massive sub-modules,
  and API-key gates.

- **Agent decision-tools (implemented)** - `docs/developer/11-agent-decision-tools.md`
  audits the strategy + dataflow surface and lands six decision-grounding
  `@tool`s the analyst LLMs now cite: `get_exit_check` (stop/target/action),
  `get_allocation` (cap-respecting book), `get_regime_components`
  (vol/trend/chop regime breakdown), `get_consensus` (rating agreement;
  also computed-injected into the PM prompt), `get_momentum_detail`
  (pillars/rvol/vwap/first-pullback), and `get_beat_miss_sizing` (event
  multiplier). Each wraps an existing deterministic `strategies/*` function,
  is bound to the market / fundamentals / news tool nodes (and the PM's
  computed-consensus logic), with hermetic tests in
  `tests/test_analysis_tools.py`. No topology change; the PM keeps its
  NO_EXTERNAL_TOOLS single-structured-call design.

- **Strategies index (`Strategies/index.md`)** - navigation map linking each
  strategy plan doc under `Strategies/` (Math, value_strategy, framework, scan,
  momentum, risk/decision-hardening, enhancement_plan, alpaca_data_analysis) to
  its implementation modules, config gates, scan modes, and consumers. Linked
  from `docs/developer/04-strategies.md` and `docs/api_reference.md` §10.

- **Developer docs set (`docs/developer/`)** - 11 focused guides covering the
  whole project for a joining developer: topology (01), graph topology + run
  (02/02-01), dataflow+vendors (03), strategies (04), agents+tools (05),
  entrypoints (06), persistence (07), development guide (08), Massive
  integration (09), tests layout (10). Linked from `docs/api_reference.md` §10.

- **Massive Flat-File validator** - `scripts/validate_massive_flat.py`
  parses a day-aggregates CSV dropped in the flat folder and reports
  per-ticker close counts, date ranges and usability (>=15 rows) via the
  screener's exact `ohlcv_for_ticker_dir` lookup, so you confirm a genuine
  Massive file (needs Stocks Starter+) before enabling the bulk import.
  Hermetic test in `tests/test_massive_flat_noi.py`.

- **Massive Flat-File screener seam + live run** - the value-screener's
  `_fetch_ohlcv` now reads a configured Massive Flat-File day-aggregates CSV
  first from a Massive day-aggregates folder (`TRADINGAGENTS_MASSIVE_FLAT_DIR`, default `data/massive_flat`) when `enable_massive_flat` is ON (default OFF) for bulk
  ATR / ATR-pct / scan bases, falling back to the per-ticker vendor chain
  otherwise (opt-in, >=15-row gate). Hermetic test in
  `tests/test_massive_flat_noi.py`. A live end-to-end `batch.py` run to AAPL
  (Underweight) validated the new Massive tools end-to-end (see
  `docs/massive_integration.md` §3e).

- **Massive corporate actions, peers & IPOs (row 5)** - `get_company_peers`
  gains a `massive` option (`get_related_companies_massive`, finnhub-format-
  compatible output); `get_dividends_massive` + `get_splits_massive` are
  combined by `get_corporate_actions_massive` registered in the
  `corporate_actions` category; dedicated `get_dividends` (fundamentals
  analyst) and `get_ipos` (news analyst, IPO reference) tools. All row-5
  endpoints are **entitled on the current tier** (probed 200) so these are
  working enrichments, not plan stubs. Tests in `tests/test_massive_vendor.py`.
  Docs: `docs/massive_integration.md` §3f.

- **Massive NOI + Flat Files (item 8)** - `massive_noi.py` is a WebSocket
  Net Order Imbalance streamer (`build_url`/`parse_frame`/`describe`/
  `stream_noi`) wired to `scripts/massive_noi_monitor.py`; `massive_flat.py`
  loads bulk Flat-File day-aggregates into per-ticker OHLCV for the
  value-screener/backtests. Both are **standalone plan-gated utilities**, not
  batch-graph `@tool`s: NOI is a live stream (Imbalances Expansion add-on),
  Flat Files are bulk S3 (Stocks Starter+). Offline tests in
  `tests/test_massive_flat_noi.py`. Docs: `docs/massive_integration.md` §3e.

- **Massive fundamentals/ratios + market snapshots (plan-aware)** - `get_ratios`
  (precomputed EV/EBITDA, EV/Sales, P/E, P/B, ROE/ROA, D/E, FCF, dividend
  yield) registered for `get_fundamentals`/`get_basic_financials` and bound to
  the fundamentals analyst; `get_market_snapshot` (consolidated day/quote) and
  `get_top_movers` bound to the market analyst; new
  `pipeline.py --universe top-movers-massive --movers-direction` universe
  source. These Massive endpoints return 403 NOT_AUTHORIZED on the free Basic
  plan, so each tool degrades with an explicit
  "upgrade at massive.com/pricing" message and activates automatically (no
  code change) once the account's plan includes them. Tests in
  `tests/test_massive_vendor.py`. Docs: `docs/massive_integration.md` §3d.

- **Massive Form-4 insider activity** - `get_form4_insider(ticker, start, end)`
  bound to the fundamentals analyst computes net open-market insider buying from
  SEC Form 4 filings via Massive (`/stocks/filings/vX/form-4`): open-market
  purchases (P) minus sales (S), excluding grant/exercise (A/M) rows. The 13-F
  endpoint is intentionally **not** wired because it has no security (`ticker`)
  filter (only `filer_cik`/`filing_date`) — a per-ticker aggregate would be
  misleading; moomoo `get_institution_holdings` remains the per-ticker
  institutional signal. Tests in `tests/test_massive_vendor.py`. Docs:
  `docs/massive_integration.md` §3c.

- **Massive short interest / short volume** - `get_short_interest_massive`
  registers `massive` in the existing `short_interest` category (FINRA
  two-week settlement: shares short, days-to-cover, avg daily volume, sorted
  newest-first), so the existing `get_short_interest` tool routes to it when
  configured. A dedicated `get_short_volume(ticker, start, end)` tool (daily
  short-sale volume ratio) is bound to the market analyst. Both degrade via
  the error taxonomy (`NoMarketDataError` on empty). Tests in
  `tests/test_massive_vendor.py`. Docs: `docs/massive_integration.md` §3b.

- **Massive macro economy + catalyst OpenD decoupling** - `get_macro_indicators_massive`
  registers `massive` as a `macro_data` vendor (treasury-yields / inflation /
  inflation-expectations / labor-market with FRED-compatible aliases) so macro
  commentary no longer depends on a FRED key or the OpenD gateway. A
  deterministic `fetch_macro_backdrop` (yield-curve inversion / elevated 10y
  breakeven) feeds the B1 catalyst overlay so it keeps de-risking near macro
  stress even when the moomoo event calendar is unavailable; `fetch_catalyst_data`
  now degrades per-section instead of returning `None` on moomoo failure.
  New snapshot verdict `macro-backdrop`; applied only when no forward event
  calendar is present (no double-count with a live moomoo read). Tests in
  `tests/test_massive_vendor.py` + `tests/test_strategies_catalyst.py`. Docs:
  `docs/massive_integration.md` §2/§3a.

- **Massive.com data vendor (news sentiment)** - new `dataflows/massive.py`
  with `get_news_massive` returning per-article structured sentiment
  (positive/negative/neutral + reasoning) from `/v2/reference/news`,
  ticker-filtered so a peer ticker's sentiment never leaks in. Registered as
  a `massive` vendor in the `get_news` chain and `VENDOR_LIST`; a dedicated
  `get_massive_news` LangChain tool is bound to the news/social tool nodes
  and the news analyst prompt. New config key `massive_api_key`
  (`MASSIVE_API_KEY` / `TRADINGAGENTS_MASSIVE_API_KEY`), hermetic offline
  tests in `tests/test_massive_vendor.py`, and `docs/massive_integration.md`.
  US-centric additive vendor (supplements, not replaces, moomoo/yfinance);
  plan-dependent recency/entitlements, FMV/Greeks Business-only (unavailable,
  never invented).

### Fixed

- **README fork-additions highlight (purple border, per-section)** - the fork
  News changelog and EACH fork-additions section (Batch runner, Extended data
  sources, Moomoo OpenAPI vendor, Value watchlist screener, Decision quality,
  Report format, Operational hardening, Decision hardening) is wrapped in its
  own HTML table with a **purple left border** (GitHub's closest rendered
  equivalent to a diff-style added-line mark, since a rendered README cannot
  show the purple bar of the diff view). Each `##` section keeps a real
  heading; upstream sections stay unmarked. The `[!IMPORTANT]` callout stays
  as a GitHub alert.
- **Screener moomoo period-order + prior-period bug (M column always n/a)** -
  moomoo statement payloads list periods newest-first but `_parse_markdown_financials`
  used a last-write-wins dict, so the canonical "latest" was the OLDEST period
  and prior-period values were never captured. Consequently the Beneish
  M-Score - which needs current AND prior - was always `n/a`, and every metric
  (EY, EV/EBIT, F, Z, EpsYoY, ROE) was computed on stale fiscal data. Fixes:
  - `_markdown_period_tables` parses each `### <period>` table and sorts by
    period year (newest first); `_markdown_canonical` scans ALL tables (a
    `get_fundamentals` payload concatenates income+balance+cashflow) and emits
    `{"current", "prior"}` dicts for two-period keys.
  - `_match_row` skips moomoo `-`-prefixed sub-item / contra lines
    (`-Accounts Receivable`, `-Accumulated Depreciation`).
  - depreciation aliases drop the loose `d&a` (normalized to `d a`, it
    substring-matched "Selling and Admin Expenses") and add `depreciation &
    depletion`; `net_receivables` prefers the aggregate `receivables` row.
  - `_latest()` unwraps the dict form at every flat read site (screen_ticker,
    _usd_consistent, fetch_ticker, mover-meta injection).
  - Result: M-Score computes (e.g. MT -2.29, WMT -2.72), F/Z/EY/ROE reflect
    the newest period; NetNet staying `no` on large caps is expected (a
    negative-current-liabilities - current-assets threshold).
- **Regression tests** - tests/test_moomoo_period_fix.py (newest-period,
  prior dicts, dash-skip, d&a alias, M-computes, concatenated-fundamentals).

### Added

- **Finnhub free-tier integration (key: TRADINGAGENTS_FINNHUB_API_KEY)** -
  live-probed the free tier and wired the endpoints that actually work:
  - `get_basic_financials_finnhub` - company_basic_financials metrics
    (epsGrowthQuarterlyYoy / revenueGrowthTTMYoy / roeTTM -> the screener's
    --min-eps-yoy / --min-rev-yoy / --min-roe gates via new canonical aliases
    + a text-router fix so header-prefixed blobs parse); also registered as a
    `get_fundamentals` vendor option
  - `get_insider_activity_finnhub` - stock_insider_sentiment (12m net change
    + mspr + trend, computed)
  - `get_company_peers_finnhub` - comparable peer group
  - `get_profile_finnhub` - profile2 sector (finnhubIndustry -> sector) as
    the second-tier `--sector-rank` fallback (FMP -> Finnhub -> yfinance)
  - bound the three as analyst tools (get_basic_financials / get_insider_activity
    / get_company_peers) to the Fundamentals analyst; all key-gated / guarded
    / no-fabrication
  - docs: api_reference 6.5 table + vendor list
- **Computed-analysis tools - follow-up batch (6 more)** - `analysis_tools.py`
  grows `get_regime_read` (overlays.build_strategy_overlays: regime label +
  position scale + momentum/52w), `get_volatility_contraction` (swing.vcp_setup),
  `get_orderflow_read` (orderflow.summarize on the guarded live fetch),
  `get_analyst_verdict` (screener canonical pipeline -> EY/EV/EBIT/F/M/Z/
  trap-risk/ROE/YoY), `get_earnings_surprise` (standardized surprise % +
  side), and `get_portfolio_weights` (value-proportional + capped weights).
  Bound to the market analyst (regime/VCP/orderflow) and the fundamentals
  analyst (verdict/surprise/portfolio); same no-fabrication contract.
- **Computed-analysis tools for the analyst LLMs** - `agents/utils/analysis_tools.py`
  wraps the deterministic strategy calculators as LangChain tools so the
  agents reason over computed numbers instead of re-deriving (or inventing)
  them from raw vendor output: `get_swing_set` (trend stack + 1-ATR stop +
  2R/3R targets + VCP), `get_relative_strength` (RS line vs benchmark),
  `get_earnings_event_read` (surprise + PEAD setup), `get_catalyst_scale`
  (0..1 B1 scale + verdict), `get_position_sizing` (Kelly + risk budget) and
  `get_risk_gate` (PASS/WARN/REJECT). Bound to the market + news analyst tool
  loops (prompt + graph ToolNodes); all return exact numbers or an explicit
  'unavailable' (no-fabrication contract). Source:
  `tradingagents/strategies/{swing,relative_strength,events,catalyst,size,risk_governor}.py`.
- **Framework Phase-1 screens** - optional screener gates from
  `Strategies/framework.md`: `--min-eps-yoy` / `--min-rev-yoy` (moomoo
  statement YoY columns now parsed - also fixes a latent defect where moomoo
  markdown payloads with `##` headers were never routed to the markdown
  parser), `--min-roe` (net income / total equity via new `total_equity`
  canonical alias), `--max-mcap` ($2B-100B focus), `--sector-rank`
  (`strategies/sector_rank.py`: 11 SPDR ETF groups ranked by 1m/3m momentum,
  ticker sector via FMP profile (key-gated) with guarded
  `dataflows/yfinance_sector.py` fallback),
  `--revision` (net analyst upgrades in 60d as the forward-revisions proxy)
  and `--inst-accum` (two-quarter institutional %-of-float change). New
  EpsYoY/RevYoY/ROE, Sec/Rank, RevUp and Inst table columns; gates apply only
  to measured values (missing data renders n/a).
- **Volatility Contraction Pattern scan (`--scan vcp`)** -
  `strategies/swing.py::vcp_setup` (strict pivot troughs, last-3 pullback depths vs
  the base high must contract 15%->8%->3%-style, deepest pullback within 30%
  of the base, fading volume across troughs; absent volume never fails);
  wired as a screener mode with VCP/Brk columns; `swing_report` carries the
  VCP block as an additional signal. Docs in `Strategies/scan.md`.
- **Techno-fundamental swing scan (`--scan swing`)** - `strategies/swing.py`
  (trend architecture: 20-EMA stacked over rising 50/200-SMA, RSI 45-70 band
  with 40-50 reset, pullback-into-EMA20 on fading volume, 1-ATR swing-low
  stop, 2R/3R two-tier targets, 50% T1 scale-out + 20-EMA trail) and
  `strategies/relative_strength.py` (RS line vs `benchmark_ticker`, 63-day
  established-uptrend slope, new-high/near-high position, negative-divergence
  detection); wired as a new screener mode with ScanC/RS/Stp/T2 columns.
  Source: `Strategies/framework.md`; mode docs in `Strategies/scan.md`.
- **PEAD post-earnings entry helpers** - `events.py` gains
  `gap_up_qualifies` (2.5x-volume gap gate), `consolidation_and_break`
  (opening-range tightening + break trigger) and `post_earnings_play`.
- **Catalyst hard block (G5)** - `catalyst_hard_block_days` config (default
  0 = off; `TRADINGAGENTS_CATALYST_HARD_BLOCK_DAYS` env override): a
  scheduled earnings print inside the window makes the risk governor REJECT
  new risk outright (framework Phase-4 "never initiate" rule) while the
  scale-fold de-risk still applies.
- **Strategy docs** - `Strategies/scan.md` filled (was an empty placeholder)
  with all scan modes including swing.

### Added

- **Momentum day-trading signals (analysis-only)** - `strategies/momentum.py`
  (5-pillar pre-filter, RVOL/EMA9/VWAP, first-pullback pattern with R/R,
  session risk flags); screener `--scan momentum` (+Pills/Pull/RR
  columns); Market Analyst `get_momentum_scan` tool in the graph.
  Source: `Strategies/momentum_day_trading.md`.
- **Alpaca wired into the analyst graph (analysis-only)** -
  `get_market_snapshot_alpaca` tool on the Market Analyst ToolNode;
  `resolve_instrument_context` appends a one-line live 1m snapshot for
  every analyst (one call per run); enabled via `enable_alpaca`.
  Rate-limit aware for the free tier: global pacing (~171 req/min under
  the 200/min cap), batch symbol queries, Retry-After/X-RateLimit-Reset
  backoff on 429.
- **`--intraday` watchlist columns** - with Alpaca keys set, `--intraday`
  appends live **L1Px / VWAP1m / 1mVol** per symbol from the snapshots
  endpoint (latest trade price, 1m-bar VWAP & volume); live-verified
  against Alpaca (AAPL 292.04 / VWAP 309.66 - 2026-08-18).
- **Alpaca smk w/ live keys** - verified against `data.alpaca.markets/v2`
  (bars/batch/snapshots) and `paper-api.alpaca.markets/v2` (calendar/clock);
  free IEX tier limits daily history to the latest bar - screener OHLCV
  fallback now requires >=15 daily bars before use.
- **Alpaca market data (analysis-only)** - `dataflows/alpaca.py` +
  `alpaca_common.py`: signed daily/1m bars (OHLC+vwap), batch bars,
  latest snapshots, trading calendar, market clock; screener falls back
  to Alpaca bars when the vendor CSV is empty (enable_alpaca) and adds a
  market-hours note. No order/position/account endpoints are implemented.
  Plan: `Strategies/alpaca_data_analysis.md`.
- **FMP vendor (optional)** - `dataflows/fmp.py` + `fmp_common.py`: 5+ year
  income/balance/cashflow history, enterprise-values, key metrics TTM,
  earnings surprises, historical OHLCV; `normalized_score` fills the
  V1/V2 gaps (5y median-margin EBIT, EV/NEBIT, 5y PE percentile). Screener
  shows NEV/EBIT + PE5Y columns when `fmp_api_key` is set; register via
  `TRADINGAGENTS_FMP_API_KEY` in `.env`.
- **`--scan` strategies (scan.md)** - trend-pullback (20/50 EMA, RSI 40-55,
  quarter >= +10%, pullback to EMA20) and breakout (>=90% of 52w high,
  above SMA20/50, RVOL >1.5 or <0.75 + Bollinger squeeze) as screener
  modes; `--scan value|trend-pullback|breakout|all` (default all: flags
  ScanA/ScanB columns), combined with the existing value gates.
- **Screener filters updated** - defaults now: market cap >= $10B,
  price >= $15, 30-day avg daily volume >= 1M shares, ATR(14) >= 2%
  of price (new `--min-avg-vol` / `--min-atr-pct` gates computed from
  vendor daily OHLCV; `--min-mcap`/`--price-min` retuned).
- **Deterministic sentiment velocity** - StockTwits counts -> signed
  computed_score (-1..1) + surprise z-score vs a rolling per-ticker
  baseline, injected into the SentimentReport as `computed_score` /
  `computed_velocity` / `sample_size` (rendered **Computed Sentiment**
  line); enabled via `.env` `TRADINGAGENTS_ENABLE_SENTIMENT=true`.
- **Risk report R1b** - the computed risk gate (verdict/snapshot/reasons)
  is injected into every report: prepended to `4_risk/*` and the Risk
  section, mirrored into `5_portfolio/decision.md`; `--risk-compact`
  (`risk_compact_report`, config/.env) replaces 3-analyst transcripts
  with a single `4_risk/verdict.md`.
- **Risk governor R0-R4** - deterministic pre-trade gate
  (`strategies/risk_governor.py`): PASS/WARN/REJECT vs a limits registry;
  book & tail risk (`book_risk.py`): VaR/CVaR, stress shocks, drawdown
  gate; escalation `risk_halt`; `risk_audit.jsonl` + `scripts/risk_report.py`.
  Enabled via .env (`TRADINGAGENTS_ENABLE_RISK_GOVERNOR=true`).
- **V2-V5 value-style wiring** - composite (value+momentum) ranking in the
  screener (`enable_composite_rank`, `--rank composite`), allocation plan
  block (`--alloc`), contract exit levels (ATR breakeven/target via
  `enable_exits`), and computed-debate-context injection
  (`enable_computed_context`). .env defaults enabled.
- **Value-style enhancements (V1-V5)** - normalized earnings (5y median
  margin), historical valuation percentiles, Sloan accruals, trap verdict
  (Trap column in the screener), hard portfolio caps, ATR exits + rebalance
  hints, and computed debate-context snippets. See
  `strategies/value_style_gap_plan.md`.
- **Decision hardening (G1-G5)** - deterministic position/stop contract
  (Kelly x vol x flow x agreement, ATR stop), confidence calibration from
  ledger buckets, computed agreement/consensus, recency-decayed sentiment
  + surprise velocity, and a walk-forward/PBO threshold gate. See
  `strategies/decision_hardening_spec.md`.
- **``$100B market-cap floor``** - `--min-mcap` now defaults to
  $100B for the moomoo rank universes (total cap; float cap <= total so the
  floor satisfies the “cap OR float cap >= $100B” rule); the day-of rank
  cap takes precedence over parsed fundamentals, and `$T` (trillion) values
  parse correctly.
- **``--universe heat-proxy`` refinement** - US-only, stocks only (ETFs/ETNs/
  funds/indices excluded), pipeline is *hot master first (gainers+losers,
  hottest first), losers second*; universe gates now enforce price >= $20 and
  0 < P/E (TTM) <= 40 (`--price-min 20`, `--pe-max 40`, defaults).
- **``--universe heat-proxy``** in the value screener: US-only alias for
  ``top-losers`` that builds the daily universe from moomoo's official intraday
  trade rank as the sanctioned stand-in for the proprietary in-app Heat List
  (composite Trade/Search/News telemetry is not exposed by any moomoo API;
  the web endpoint's signed token is undocumented). Pass the literal app Heat
  List via ``-f list.txt`` to use it directly.
- **Value watchlist screener** — `scripts/value_screener.py` builds a master
  value watchlist by screening tickers through the configured vendor chain
  (`fundamental_data`: `moomoo,yfinance` by default). It normalizes yfinance
  CSV, moomoo markdown/JSON, alpha_vantage JSON, and info text into canonical
  line items, then computes EV/EBIT (Acquirer's Multiple), Earnings Yield, EV,
  Piotroski F-Score, Beneish M-Score, Altman Z and net-net (missing rows ->
  `n/a`, never fabricated). A `--universe top-losers` mode pulls moomoo's
  intraday decliners rank (`get_top_movers_rank`) so the universe changes
daily; output merges name/change columns for picking. See
  `strategies/value_strategy.md`.
- **Quantitative score library** — `tradingagents/dataflows/quantitative_scores.py`
  implements Beneish M-Score, Altman Z-Score, Piotroski F-Score and
  EV / Earnings-Yield / Acquirer's-Multiple helpers, vendor-agnostic over a
  canonical line-item schema (offline unit-tested in
  `tests/test_quantitative_scores.py`).
- **Moomoo top movers vendor call** — `get_top_movers_moomoo()` wraps the SDK's
  intraday gainers/losers rank with the usual error taxonomy (OpenD down /
  permission / rate-limit degrade via `_check_ret`) and converts codes to
  Yahoo-style symbols (`US.AAPL` -> `AAPL`, `HK.00700` -> `00700.HK`).
  Covered by `MoomooTopMoversTests` and `tests/test_value_screener.py`.

### Fixed

- **Value screener refuses mixed currencies.** moomoo reports ADR statements
  in the underlying currency (e.g. JPY) while market cap arrives in USD, which
  produced nonsense EV (e.g. a -62T "EV" for Japan Post's ADR). The screener
  now detects the statement currency (moomoo markdown headers, yfinance
  ``Financial Currency``, alpha_vantage ``reportedCurrency``) plus an
  assets/market-cap >1000x scale heuristic, and gates the USD-only metrics
  (EV / EY / Acquirer's Multiple / Altman Z / net-net) to ``n/a`` when
  currencies would be mixed. A cash > total-assets guard also drops wrong-row
  matches.
- **Moomoo top-movers ``change_ratio`` normalized to a fraction** - the SDK
  returns a ratio in some market sessions and a percent in others for the same
  symbol; the vendor now divides by 100 when \|\|>1.5 so ``DayChg`` formatting
  is always correct.
- **Moomoo fundamentals match the tool signatures.** The moomoo vendor's
  `get_fundamentals`/`get_balance_sheet`/`get_cashflow`/`get_income_statement`
  accepted only the symbol, so the interactive CLI's `curr_date` (and `freq`
  for statements) arguments raised `TypeError` and every call fell back to
  yfinance/alpha_vantage. The vendor now accepts the same arguments as the
  other fundamentals vendors: `freq` selects the annual vs. quarterly report
  type on the moomoo SDK, and `curr_date` filters out statements published
  after the trading day (look-ahead guard, mirroring alpha_vantage).
- **yfinance options chain no longer crashes on `NaN`.** Yahoo chains carry
  `float('nan')` for open interest/volume on many rows; `int(nan)` raised
  `ValueError` and the router logged `Vendor 'yfinance' failed for
  get_options_chain`. The vendor now sums only finite values (missing counts
  contribute 0) and skips non-finite implied-volatility values in the mean,
  so the call degrades to zeroed totals instead of aborting.

## [0.3.1] — 2026-07-05

Correctness and stability patch: data look-ahead, graph-router crash-safety,
checkpoint identity, crypto sentiment sources, and configurable resilience.

### Fixed

- **Alpha Vantage look-ahead filter now runs.** The fundamentals payload is a
  JSON string, so the dict-only guard skipped filtering and future-dated reports
  leaked into historical runs; parse before filtering. (#1115, @zachthebird)
- **News analyst prompt matches the tool.** The prompt advertised
  `get_news(query, ...)` but the tool takes a ticker; aligned to stop
  hallucinated free-text query calls. (#1116, @shcheuk)
- **Shared debate/risk routers can't crash mid-run.** Both routers return more
  targets than any one edge mapped; every edge now shares the complete path map,
  so a fall-through under prompt/i18n/refactor drift stays routable.
  (#1088, @Fr3ya, @sa7an7, @Sushanth012)
- **Checkpoint resume respects graph shape.** The thread id folds in selected
  analysts, debate/risk depth, and asset mode, so a resume under different
  choices no longer continues the wrong graph. (#1089, @bossjoker1, @Ghraven)
- **Crypto sentiment sources resolve.** StockTwits lists crypto as `<BASE>.X`
  (Yahoo's `BTC-USD` 404s) and Reddit needs the base symbol to match; the social
  path now maps crypto correctly for both. (#1113, @suremadoreai)

### Added

- **Configurable LLM retry budget.** `llm_max_retries` /
  `TRADINGAGENTS_LLM_MAX_RETRIES` is forwarded to every provider, so a transient
  429 burst no longer aborts a run. (#1091, @yanggaome)
- **Bedrock API-key auth.** `AWS_BEARER_TOKEN_BEDROCK` authenticates Amazon
  Bedrock without AWS access keys and takes precedence over an ambient
  `AWS_PROFILE`. (#1103, @praxstack)
- **Latest Claude models.** Added Claude Sonnet 5 (`claude-sonnet-5`) and
  Fable 5 (`claude-fable-5`); effort control now covers the Claude 5 line.

## [0.3.0] — 2026-06-22

Stabilization and extensibility release: a CI gate, a unified verified
data-access contract, a provider and data-vendor registry, and a maintenance
sweep that hardened config precedence, the model catalog, data resilience, and
structured output.

### Added

- **CI gate.** GitHub Actions runs the pytest suite across Python 3.10-3.13,
  strict `ruff`, and a clean-install smoke that imports the package and CLI to
  catch undeclared dependencies. (#994, #197)
- **Provider registry.** OpenAI-compatible providers register as a single spec,
  and a generic `openai_compatible` endpoint covers vLLM, LM Studio, and relays.
  Adds NVIDIA NIM, Kimi, Groq, Mistral, and a native Amazon Bedrock client.
- **Macro and prediction-market vendors.** FRED macro indicators and Polymarket
  event probabilities, surfaced to the news and macro analysts.
- **Programmatic report output.** `TradingAgentsGraph.save_reports()` writes the
  same report tree the CLI produces, for headless and API runs. (#1037)
- **Env-configurable reasoning depth** via `TRADINGAGENTS_OPENAI_REASONING_EFFORT`,
  `TRADINGAGENTS_GOOGLE_THINKING_LEVEL`, and `TRADINGAGENTS_ANTHROPIC_EFFORT`,
  each gated to the models that accept it.

### Changed

- **Verified data-access contract.** Symbol normalization on every vendor path
  (identity, returns, CLI, news); the configured vendor list is the exact
  resolution chain with no silent fallback to unselected vendors; a typed
  `VendorError` taxonomy; look-ahead-safe news windows; stale-OHLCV rejection;
  inclusive yfinance date ranges.
- **Config precedence.** An explicit `TRADINGAGENTS_*` value or CLI flag now wins
  over interactive defaults for debate and risk round counts,
  `--checkpoint / --no-checkpoint`, and the Docker provider profile; invalid
  boolean env values fail loudly. (#975, #976, #977)
- **Current-generation model catalog.** Refreshed provider lineups; retired
  `gpt-4.1`, Claude Sonnet 4.5, and the Gemini 2.5 line.
- **Optional vendors degrade** instead of aborting a run: a failed macro or
  prediction-market lookup returns a no-data sentinel.
- **Analyst prompts lead with the current date** so tool-call date ranges anchor
  to the run date rather than the model's training cutoff. (#836)

### Fixed

- **Instrument identity.** Deterministic ticker-to-company resolution prevents
  wrong-company hallucination, and a verified market-data snapshot grounds price
  and indicator claims. (#814, #830)
- **Social and market data sources.** Reddit RSS-first with 429 backoff,
  StockTwits transport hardening, and Alpha Vantage timeout plus
  key-versus-rate-limit handling.
- **Structured output.** Local OpenAI-compatible servers no longer reject
  object-form `tool_choice`; a thinking model that returns no parsed result falls
  back to free text; null-ish strings in optional price fields coerce to `None`.
  (#1038, #1051, #1057)

### Removed

- The no-op `analyst_concurrency_limit` config knob; parallel analyst execution
  is planned for a later release. (#979)
- The unused committed `uv.lock`. (#1030)

### Contributors

Thanks to everyone who shaped this release through code, design, and reports:

[@CadeYu](https://github.com/CadeYu), [@Zavianx](https://github.com/Zavianx), [@weijianz-opc](https://github.com/weijianz-opc), [@naltun](https://github.com/naltun), [@brahmasky](https://github.com/brahmasky), [@nik2208](https://github.com/nik2208), [@thieucong98](https://github.com/thieucong98), [@Derekko-web](https://github.com/Derekko-web), [@LukiPrince](https://github.com/LukiPrince), [@Eddieargenal](https://github.com/Eddieargenal), [@Ghraven](https://github.com/Ghraven), [@ms32035](https://github.com/ms32035), [@yting27](https://github.com/yting27), [@nyxst4ck](https://github.com/nyxst4ck), [@KenCheung-AIxFinance](https://github.com/KenCheung-AIxFinance), [@yangyusheng2n](https://github.com/yangyusheng2n), [@fareloj](https://github.com/fareloj), [@haosenwang1018](https://github.com/haosenwang1018), [@octo-patch](https://github.com/octo-patch), [@seifenk](https://github.com/seifenk), [@CaoYuhaoCarl](https://github.com/CaoYuhaoCarl), [@mihailnica10](https://github.com/mihailnica10), [@Dado-hash](https://github.com/Dado-hash), [@Handsomemikezzz](https://github.com/Handsomemikezzz), [@ydhawesome](https://github.com/ydhawesome), [@macd2](https://github.com/macd2), [@AyushKar2005](https://github.com/AyushKar2005), [@wildhuman](https://github.com/wildhuman), [@robert23kim](https://github.com/robert23kim), [@bngness](https://github.com/bngness), [@tedix-rodrigo](https://github.com/tedix-rodrigo), [@malaccan](https://github.com/malaccan), [@rfalken78](https://github.com/rfalken78), [@dengli1971-droid](https://github.com/dengli1971-droid), [@proofconcept39](https://github.com/proofconcept39), [@prasta1](https://github.com/prasta1), [@liximin](https://github.com/liximin), [@jeffhuen](https://github.com/jeffhuen), [@mazar](https://github.com/mazar), [@soyangelromero](https://github.com/soyangelromero), [@CNQQC](https://github.com/CNQQC), [@dovetaill](https://github.com/dovetaill), [@fperdigon](https://github.com/fperdigon), [@gyx09212214-prog](https://github.com/gyx09212214-prog), [@RSXLX](https://github.com/RSXLX).

## [0.2.5] — 2026-05-11

### Added

- **Grounded Sentiment Analyst.** The renamed `sentiment_analyst` now reads
  real Yahoo News, StockTwits, and Reddit data before generating its report,
  replacing the prior flow that could fabricate social posts under prompt
  pressure. (#557, #607)
- **MiniMax provider** with the full M2.x catalog (M2.7 / M2.5 / M2.1 / M2
  plus highspeed variants, 204K context). Dual-region: Global
  (`MINIMAX_API_KEY`) and China (`MINIMAX_CN_API_KEY`).
- **Dual-region Qwen and GLM** with separate keys per region — international
  (`DASHSCOPE_API_KEY`, `ZHIPU_API_KEY`) and China (`DASHSCOPE_CN_API_KEY`,
  `ZHIPU_CN_API_KEY`), selectable via a secondary region prompt. (#758)
- **`TRADINGAGENTS_*` env-var configurability for `DEFAULT_CONFIG`.** Override
  `llm_provider`, deep/quick model IDs, `backend_url`, `output_language`,
  debate-round counts, checkpoint flag, and benchmark ticker via `.env` with
  type-aware coercion (string / int / bool). (#602)
- **Interactive API-key detection in the CLI.** When the selected provider's
  key is missing, the CLI prompts for it and persists the value to `.env`
  so the analysis run continues without restart.
- **Remote Ollama support.** `OLLAMA_BASE_URL` points the CLI and the
  programmatic client at a remote `ollama-serve`. The CLI surfaces the
  resolved endpoint and warns on common malformed inputs. Adds a
  `"Custom model ID"` option for models pulled via `ollama pull`. (#648, #768)
- **Configurable news-fetch parameters** in `DEFAULT_CONFIG` — per-ticker
  article limit, macro headline limit, lookback window, and macro search
  queries. (#606, #683)
- **Configurable alpha benchmark** for non-US tickers. Replaces hardcoded
  SPY with regional indices for `.NS` (^NSEI), `.T` (^N225), `.HK` (^HSI),
  `.L` (^FTSE), `.TO` (^GSPTSE), `.AX` (^AXJO), `.BO` (^BSESN); explicit
  `benchmark_ticker` override available. Eliminates FX drift dominating
  alpha for non-USD listings. (#628, #684)
- **Multi-language output covers every user-facing agent** — researchers,
  risk debators, research manager, and trader, ending the previous
  partial-localization reports. (#575)
- **Model catalog refresh.** OpenAI GPT-5.5 frontier, Anthropic Claude Opus
  4.7, Gemini 3.1 Flash-Lite GA, xAI Grok 4.20, Qwen 3.6 line. Versioned IDs
  only; auto-shifting aliases moved to the `"Custom model ID"` option.

### Changed

- **Sentiment Analyst** is now consistently named across the CLI dropdown,
  status panel, and final reports (previously the backend was renamed but
  the CLI still said "Social Analyst"). The `AnalystType.SOCIAL = "social"`
  wire value is kept for saved-config back-compat.

### Fixed

- **Structured output works on DeepSeek V4 / reasoner and MiniMax M2.x.**
  Those providers reject `tool_choice` per their tool-calling docs; the
  binding flow now skips it automatically via a capability table.
- **`pip install .` installations pick up the project `.env`** when running
  the CLI as a console script. (#747)
- **Reports save end-to-end** — streamed chunks were previously dropped from
  `complete_report.md`. (#719, #736)
- **Ticker prompt preserves exchange suffixes** (`.SH`, `.SZ`, `.SS`, `.HK`,
  `.T`, etc.) for A-share, HK, Tokyo, and other non-US flows. (#770)
- **Docker permission errors** no longer block first-run write to
  `~/.tradingagents/`. (#519, #627, #672, #771)
- **Config state no longer leaks between runs** when sub-dicts are mutated;
  `set_config` partial updates preserve sibling defaults. (#788)
- **`max_recur_limit` config actually applies** — previously read but not
  forwarded to the propagator. (#764)
- **Missing-API-key error** names the exact env var to set. (#680)
- **Quieter startup** — suppressed the noisy upstream
  `LangChainPendingDeprecationWarning` from langgraph-checkpoint; will be
  removed once that package ships its fix.

### Security

- **Ticker path-traversal validation** at every filesystem-path site (cache,
  checkpoint database, results) so a malicious ticker cannot escape its
  intended directory. (#618)

## [0.2.4] — 2026-04-25

### Added

- **Structured-output decision agents.** Research Manager, Trader, and Portfolio
  Manager now use `llm.with_structured_output(Schema)` on their primary call
  and return typed Pydantic instances. Each provider's native structured-output
  mode is used (`json_schema` for OpenAI / xAI, `response_schema` for Gemini,
  tool-use for Anthropic, function-calling for OpenAI-compatible providers).
  Render helpers preserve the existing markdown shape so memory log, CLI
  display, and saved reports keep working unchanged. (#434)
- **LangGraph checkpoint resume** — opt-in via `--checkpoint`. State is saved
  after each node so crashed or interrupted runs resume from the last
  successful step. Per-ticker SQLite databases under
  `~/.tradingagents/cache/checkpoints/`. `--clear-checkpoints` resets them. (#594)
- **Persistent decision log** replacing the per-agent BM25 memory. Decisions
  are stored automatically at the end of `propagate()`; the next same-ticker
  run resolves prior pending entries with realised return, alpha vs SPY, and
  a one-paragraph reflection. Override path with `TRADINGAGENTS_MEMORY_LOG_PATH`.
  Optional `memory_log_max_entries` config caps resolved entries; pending
  entries are never pruned. (#578, #563, #564, #579)
- **DeepSeek, Qwen (Alibaba DashScope), GLM (Zhipu), and Azure OpenAI**
  providers, plus dynamic OpenRouter model selection.
- **Docker support** — multi-stage build with separate dev and runtime images.
- **`scripts/smoke_structured_output.py`** — diagnostic that exercises the
  three structured-output agents against any provider so contributors can
  verify their setup with one command.
- **5-tier rating scale** (Buy / Overweight / Hold / Underweight / Sell) used
  consistently by Research Manager, Portfolio Manager, signal processor, and
  the memory log; Trader keeps 3-tier (Buy / Hold / Sell) since transaction
  direction is naturally ternary.
- **Pytest fixtures** — lazy LLM client imports plus placeholder API keys so
  the test suite runs cleanly without credentials. (#588)

### Changed

- **`backend_url` default is now `None`** rather than the OpenAI URL. Each
  provider client falls back to its native default. The previous default
  leaked the OpenAI URL into non-OpenAI clients (e.g. Gemini), producing
  malformed request URLs for Python users who switched providers without
  overriding `backend_url`. The CLI flow is unaffected.
- All file I/O passes explicit `encoding="utf-8"` so Windows users no longer
  hit `UnicodeEncodeError` with the cp1252 default. (#543, #550, #576)
- Cache and log directories moved to `~/.tradingagents/` to resolve Docker
  permission issues. (#519)
- `SignalProcessor` reads the rating from the Portfolio Manager's rendered
  markdown via a deterministic heuristic — no extra LLM call.
- OpenAI structured-output calls default to `method="function_calling"` to
  avoid noisy `PydanticSerializationUnexpectedValue` warnings emitted by
  langchain-openai's Responses-API parse path. Same typed result, no warnings.

### Fixed

- Empty memory no longer triggers fabricated past-lessons in agent prompts;
  the memory-log redesign makes this structurally impossible since only the
  Portfolio Manager consults memory and only when entries exist. (#572)
- Tool-call logging processes every chunk message, not just the last one, and
  memory score normalization handles empty score arrays. (#534, #531)

### Removed

- `FinancialSituationMemory` (the per-agent BM25 system) and the dead
  `reflect_and_remember()` plumbing; subsumed by the persistent decision log.
- Hardcoded Google endpoint that caused 404 when `langchain-google-genai`
  changed its API path. (#493, #496)

### Contributors

Thanks to everyone who shaped this release through code, design, and reports:

- [@claytonbrown](https://github.com/claytonbrown) — checkpoint resume (#594), test fixtures (#588), design feedback on cost tracking (#582) and structured validation (#583)
- [@Bcardo](https://github.com/Bcardo) — memory-log redesign (#579), empty-memory hallucination report (#572), encoding fix proposal (#570)
- [@voidborne-d](https://github.com/voidborne-d) — memory persistence design (#564), portfolio manager state fix (#503)
- [@mannubaveja007](https://github.com/mannubaveja007) — structured-output feature request (#434)
- [@kelder66](https://github.com/kelder66) — RAM-only memory issue (#563)
- [@Gujiassh](https://github.com/Gujiassh) — tool-call logging fix (#534), test stub PR (#533)
- [@iuyup](https://github.com/iuyup) — memory score normalization fix (#531)
- [@kaihg](https://github.com/kaihg) — Google base_url fix (#496)
- [@32ryh98yfe](https://github.com/32ryh98yfe) — Gemini 404 report (#493)
- [@uppb](https://github.com/uppb) — OpenRouter dynamic model selection (#482)
- [@guoz14](https://github.com/guoz14) — OpenRouter limited-model report (#337)
- [@samchenku](https://github.com/samchenku) — indicator name normalization (#490)
- [@JasonOA888](https://github.com/JasonOA888) — y_finance pandas import fix (#488)
- [@tiffanychum](https://github.com/tiffanychum) — stale import cleanup (#499)
- [@zaizou](https://github.com/zaizou) — Docker permission issue (#519)
- [@Stosman123](https://github.com/Stosman123), [@mauropuga](https://github.com/mauropuga), [@hotwind2015](https://github.com/hotwind2015) — Windows encoding bug reports (#543, #550, #576)
- [@nnishad](https://github.com/nnishad), [@atharvajoshi01](https://github.com/atharvajoshi01) — encoding fix proposals (#568, #549)

## [0.2.3] — 2026-03-29

### Added

- **Multi-language output** for analyst reports and final decisions, with a
  CLI selector. Internal agent debate stays in English for reasoning quality. (#472)
- **GPT-5.4 family models** in the default catalog, with deep/quick model split.
- **Unified model catalog** as a single source of truth for CLI options and
  provider validation.

### Changed

- `base_url` is forwarded to Google and Anthropic clients so corporate proxies
  work consistently across providers. (#427)
- Standardised the Google `api_key` parameter to the unified `api_key` form.

### Fixed

- Backtesting fetchers no longer leak look-ahead data when `curr_date` is in
  the middle of a fetched window. (#475)
- Invalid indicator names from the LLM are caught at the tool boundary instead
  of crashing the run. (#429)
- yfinance news fetchers respect the same exponential-backoff retry as price
  fetchers. (#445)

### Contributors

- [@ahmedk20](https://github.com/ahmedk20) — multi-language output (#472)
- [@CadeYu](https://github.com/CadeYu) — model catalog typing (#464)
- [@javierdejesusda](https://github.com/javierdejesusda) — unified Google API key parameter (#453)
- [@voidborne-d](https://github.com/voidborne-d) — yfinance news retry (#445)
- [@kostakost2](https://github.com/kostakost2) — look-ahead bias report (#475)
- [@lu-zhengda](https://github.com/lu-zhengda) — proxy/base_url support request (#427)
- [@VamsiKrishna2021](https://github.com/VamsiKrishna2021) — invalid indicator crash report (#429)

## [0.2.2] — 2026-03-22

### Added

- **Five-tier rating scale** (Buy / Overweight / Hold / Underweight / Sell)
  introduced for the Portfolio Manager.
- **Anthropic effort level** support for Claude models.
- **OpenAI Responses API** path for native OpenAI models.

### Changed

- `risk_manager` renamed to `portfolio_manager` to match the role description
  shown in the CLI display.
- Exchange-qualified tickers (e.g. `7203.T`, `BRK.B`) preserved across all
  agent prompts and tool calls.
- Process-level UTF-8 default attempted for cross-platform consistency
  (note: this approach did not actually take effect; replaced in v0.2.4 with
  explicit per-call `encoding="utf-8"` arguments).

### Fixed

- yfinance rate-limit errors are retried with exponential backoff. (#426)
- HTTP client SSL customisation is supported for environments that need
  custom certificate bundles. (#379)
- Report-section writes handle list-of-string content gracefully.

### Contributors

- [@CadeYu](https://github.com/CadeYu) — exchange-qualified ticker preservation (#413)
- [@yang1002378395-cmyk](https://github.com/yang1002378395-cmyk) — HTTP client SSL customisation (#379)

## [0.2.1] — 2026-03-15

### Security

- Patched `langchain-core` vulnerability (LangGrinch). (#335)
- Removed `chainlit` dependency affected by CVE-2026-22218.

### Added

- `pyproject.toml` build-system configuration; the project now installs via
  modern packaging tooling.

### Removed

- `setup.py` — dependencies consolidated to `pyproject.toml`.

### Fixed

- Risk manager reads the correct fundamental report source. (#341)
- All `open()` calls receive an explicit UTF-8 encoding (initial pass).
- `get_indicators` tool handles comma-separated indicator names from the LLM. (#368)
- `Propagation` initialises every debate-state field so risk debaters never
  see missing keys.
- Stock data parsing tolerates malformed CSVs and NaN values.
- Conditional debate logic respects the configured round count. (#361)

### Contributors

- [@RinZ27](https://github.com/RinZ27) — `langchain-core` security patch (#335)
- [@Ljx-007](https://github.com/Ljx-007) — risk manager fundamental-report fix (#341)
- [@makk9](https://github.com/makk9) — debate-rounds config issue (#361)

## [0.2.0] — 2026-02-04

This is the largest release since the initial public version. The framework
moved from single-provider to a multi-provider architecture and grew several
production-ready surfaces.

### Added

- **Multi-provider LLM support** (OpenAI, Google, Anthropic, xAI, OpenRouter,
  Ollama) via a factory pattern, with provider-specific thinking configurations.
- **Alpha Vantage** integration as a configurable primary data provider, with
  yfinance as a community-stability fallback.
- **Footer statistics** in the CLI: real-time tracking of LLM calls, tool
  calls, and token usage via LangChain callbacks.
- **Post-analysis report saving** — the framework writes per-section markdown
  files (analyst reports, debate transcripts, final decision) when a run
  completes.
- **Announcements panel** — fetches updates from `api.tauric.ai/v1/announcements`
  for the CLI welcome screen.
- **Tool fallbacks** so a single vendor outage does not stop the pipeline.

### Changed

- Risky / Safe risk debaters renamed to **Aggressive / Conservative** for
  consistency with the displayed agent labels.
- Default data vendor switched to balance reliability and quota across
  community deployments.
- Ollama and OpenRouter model lists updated; default endpoints clarified.

### Fixed

- Analyst status tracking and message deduplication in the live display.
- Infinite-loop guard in the agent loop; reflection and logging hardened.
- Various data-vendor implementation bugs and tool-signature mismatches.

### Contributors

This release is the first with substantial outside contributions; many community
PRs from late 2025 also landed here.

- [@luohy15](https://github.com/luohy15) — Alpha Vantage data-vendor integration (#235)
- [@EdwardoSunny](https://github.com/EdwardoSunny) — yfinance fetching optimisations (#245)
- [@Mirza-Samad-Ahmed-Baig](https://github.com/Mirza-Samad-Ahmed-Baig) — infinite-loop guard, reflection, and logging fixes (#89)
- [@ZeroAct](https://github.com/ZeroAct) — saved results path support (#29)
- [@Zhongyi-Lu](https://github.com/Zhongyi-Lu) — `.env` gitignore (#49)
- [@csoboy](https://github.com/csoboy) — local Ollama setup (#53)
- [@chauhang](https://github.com/chauhang) — initial Docker support attempt (#47, later reverted; the merged Docker support shipped in v0.2.4)

## [0.1.1] — 2025-06-07

### Removed

- Static site assets that had been bundled with v0.1.0; the public site now
  lives separately.

## [0.1.0] — 2025-06-05

### Added

- **Initial public release** of the TradingAgents multi-agent trading
  framework: market / sentiment / news / fundamentals analysts; bull and bear
  researchers; trader; aggressive, conservative, and neutral risk debaters;
  portfolio manager. LangGraph orchestration, yfinance data, per-agent
  BM25 memory, single-provider OpenAI integration, interactive CLI.

[0.2.4]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/TauricResearch/TradingAgents/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/TauricResearch/TradingAgents/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/TauricResearch/TradingAgents/releases/tag/v0.1.0
