<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>
<br>
<div align="center">
  <a href="https://github.com/TauricResearch" target="_blank"><img alt="TradingAgents #1 Repository of the Day" src="https://trendshift.io/api/badge/repositories/16192" width="250" height="55"/></a>
</div>
<br>
<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents: Multi-Agents LLM Financial Trading Framework

## News
<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

<sub><b>Fork changelog</b> - additions since the upstream [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) release list below.</sub>

- [2026-08-30] **News/sentiment providers (A-C)** - GDELT (keyless native
  news-tone + daily sentiment, `get_gdelt_sentiment` tool, opt-in chain),
  NewsAPI.org (free 100 req/day global macro headlines, `NEWSAPI_API_KEY`),
  and Benzinga (free ticker-scoped financial news, `BENZINGA_API_KEY`).
  Registered vendors; NewsAPI in the default chain, GDELT/Benzinga opt-in. See
  CHANGELOG.

- [2026-08-30] **Extended technical indicators** - the standard
  trend/momentum/volume/structure set the project lacked now computes locally
  (`strategies/extended_indicators.py`): Ichimoku cloud, CCI, ROC, momentum
  oscillator, TRIX, Force Index, A/D line, VPT, Chaikin Money Flow, anchored
  VWAP, golden/death cross + a candlestick pattern scanner (doji/hammer/
  engulfing/stars). Two new market-analyst tools `get_extended_indicators` +
  `get_candlestick_patterns` (no new vendor, no quota). See CHANGELOG.

- [2026-08-30] **Twelve Data + StockData.org vendors** - two new free-tier
  market-data providers: Twelve Data (free "Basic": 800 credits/day, realtime
  US stocks/forex/crypto quotes + historical OHLCV) and StockData.org (free
  "$0/mo": 100 requests/day, quote/EOD/intraday/news). Both keyed via
  `TWELVEDATA_API_KEY` / `STOCKDATA_API_KEY` in `.env` and wired as tails of
  `core_stock_apis` + `news_data`, plus market-snapshot / crypto-prices
  fallbacks. All key-gated; the existing chains stay first. See CHANGELOG.

- [2026-08-30] **Independent pre-debate stances (Option-A hybrid)** - the 3
  risk debators + bull/bear researchers each emit ONE independent stance
  (rating / confidence / strength / reason) BEFORE the debate runs, sampled
  with **no transcript and no opponents' responses** — so agreement/consensus
  (`enable_agreement`, G3), the G1 position-contract multiply, the PM's
  dissent flag and the Research Manager's read all come from uncontaminated,
  conformity-free opinions while the debate stays the risk-surfacing layer.
  Opt-in `enable_independent_vote` (`TRADINGAGENTS_ENABLE_INDEPENDENT_VOTE`);
  every fallback is the legacy parse-from-history path when off. See CHANGELOG.

- [2026-08-29] **Risk gate placement + compact verdict** - the computed risk
  gate is no longer repeated at the top of every analyst report (it appears
  once, in `4_risk/` + `5_portfolio/decision.md`), the compact `verdict.md` no
  longer duplicates the PM decision, and report re-renders are idempotent
  (no doubled `### Round N` headings). See CHANGELOG.

- [2026-08-29] **Readable reports + verbose risk files** - the interactive
  CLI now always writes the full risk-debate transcripts
  (`4_risk/aggressive.md` / `conservative.md` / `neutral.md`) instead of a
  single `verdict.md`, and debate/trader/research reports are automatically
  paragraph-spaced with `### Round N` headings (analyst-style readability) via
  `reporting._readable_section`. Re-render old folders with
  `scripts/rebuild_complete_report.py`. See CHANGELOG.

- [2026-08-29] **Canonical output root** - all `reports/`, `screener/` and
  `action_reports/` outputs now resolve against the TradingAgents repo,
  regardless of where the CLI or web server is launched from (previously the
  web app, started from `TradingNew` or `trading_web`, could drop `reports/`
  into those parent folders). Wired through a shared
  `resolve_output_path()` helper across batch/pipeline/screener/action-report/
  nightly-review/pre-market-review/rebuild. Stale stray `reports/` dirs were
  consolidated into `TradingAgents/reports/`. See CHANGELOG.

- [2026-08-29] **Provider-endpoint + calc-wiring pass** - audited every data
  provider's docs for exposable endpoints and every strategy calculator for
  agent wiring. New keyless yfinance fallbacks for `analyst_ratings`
  (recommendation summary + price-target consensus), `earnings_calendar`
  (earnings dates + EPS surprise) and `institution_data` (institutional +
  major holders), registered in the vendor chains — those signals no longer
  need a moomoo gateway or paid key. New market tools `get_scaleout_plan`
  (tiered profit-taking), `get_payoff_asymmetry` (Omega ratio) and
  `get_book_correlation` (book concentration); `get_strategy_quality` now also
  reports Calmar / Ulcer / tail-ratio / expectancy. See CHANGELOG.

- [2026-08-29] **Full-set audit fixes (correctness + agent wiring)** - a
  read-everything audit fixed 14 defects so the numbers the LLM agents cite are
  correct and reachable: `exit_check` target now anchored at entry (was close,
  so "target" could never fire); parametric horizon CVaR sign/tail-probability
  fix; `first_pullback` R:R no longer permanently dead; yfinance statement CSV
  parsed newest-first (was returning the OLDEST year as "latest") and its
  `# comment` header no longer mis-routes to the text parser; `tracking_error`
  now demeaned; `ev_ebitda` no longer collapses to P/EBITDA; FCF/dividend-yield
  sign-safe on GAAP-negative capex/divs; Alpha-Vantage error strings no longer
  cached as data; screener/movers invalid args return `DATA_UNAVAILABLE`
  sentinels; routed EODHD symbol list is a string. Wiring: new `get_exit_plan`
  tool (breakeven-after-confirmation + margin-giveback), and `get_consensus` +
  `get_sentiment_computed` (previously unbound) are now callable from the
  analyst ToolNodes; batch `--vendor` presets keep all 27 data categories. See
  CHANGELOG.

- [2026-08-28] **QuantLib + Lean enhancements (deep-study implementation)** -
  evaluation breadth beyond Sharpe (Sortino / PSR / rolling-beta / underwater
  drawdowns), horizon VaR/CVaR, options IV + Greeks (Black-76), risk-parity /
  min-variance / confidence-weighted allocation from a real covariance matrix,
  a two-pass risk manager (advisory, off), MAE/MFE excursion journaling, and
  volume-share / market-impact slippage - all as deterministic pure modules
  under `tradingagents/strategies/` plus 4 new market analyst tools, with every
  gate default OFF / advisory-only. See
  docs/design_quantlib_lean_enhancements.md and CHANGELOG.

- [2026-08-28] **Pre-open + execution-quality advisory rows** - probed your
  actual data tiers and built what's available on free: pre-market RVOL vs
  30-day pre-open average, gap vs the live pre-open price, and a live IEX
  quote-depth thin-book proxy (all Alpaca free IEX) fed into the pre-market
  review as advisory context; plus a post-fill drift (alpha-profile) block in
  the strategy-quality report. True opening-imbalance (NOII) and short-locate
  are plan-gated / out of scope - documented.

- [2026-08-28] **Institutional workflow for value-dip + swing (Phases A-E)** -
  mapped institutional best practice (regime switching, catalyst-first value,
  daily-loss/HWM risk gates, trade plan card, arrival-benchmark execution
  ledger, sleeve attribution, alpha-decay monitor) onto the stack. All new
  signals are ADVISORY - computed from real data and injected into the 5
  decision agents (Trader, PM, 3 risk debators) via a compiled decision
  context, so the LLMs reason over hard numbers; nothing blocks unless you
  opt into the strict flags. See docs/design_institutional_value_dip_workflow.md
  and CHANGELOG.

- [2026-08-28] **Value Dip + Swing enhancements (web-researched)** - compared
  the setup/exit math against established swing-trading practice and closed
  the gaps: VCP now enforces a **halving progression** (`contraction_tol=0.65`,
  default) with a final-tightness gate + a `pivot` breakout field; the
  **chandelier exit** uses real daily highs (was a closes proxy); the value-dip
  setup adds a `trend` row (opt-in `require_trend` gate), a `plan_stop_ok`
  harmonization field, a `strict_vdu` mode, configurable ATR/%-drawdown
  tranche ladders, and an R-based breakeven (`exits.stop_to_breakeven_r`).
  See CHANGELOG.

- [2026-08-28] **Dedupe repeated debate tables in reports** - deep runs
  rendered 4-6 near-identical summary tables per debate agent (one per round)
  - e.g. the latest NVDA report carried 28 tables in `complete_report.md`.
  Fix: debaters now append their summary table only in the FINAL round
  (`get_output_budget("debater")`), and `reporting._collapse_repeated_tables`
  keeps only the last table per header as a render-time guarantee (existing
  reports fixed via `rebuild_complete_report.py`). NVDA sample: complete
  report 28 -> 14 tables.

- [2026-08-28] **Interactive CLI now applies the strategy overlays** - the
  CLI streamed the graph but skipped `_apply_strategy_overlays`, so a CLI
  report omitted the Risk Gate block / position contract / computed risk
  context that the batch/API path renders (two same-day NVDA reports diverged
  structurally: batch showed a Risk Gate PASS, CLI showed none and a
  different decision). The CLI now seeds `risk_context` pre-PM and applies
  the overlays before saving - same hooks as `propagate()`, so CLI and batch
  reports carry the same computed risk surface.

- [2026-08-28] **Audit-driven correctness fixes (data integrity + wiring)** - a
  repo-wide audit fixed ~26 defects with hermetic tests (1490 passed, 2
  skipped, ruff clean). Highlights: Piotroski ROA point no longer awarded to
  negative-ROA firms; the vendor router records rate-limit errors so an
  all-throttled optional chain degrades instead of crashing; Alpha Vantage HTTP
  429/5xx/timeout map to a retryable error (was a hard crash of the price
  path); DCF projects the LATEST FCF (was the historical max); OBV bullish
  divergence slice fixed; yfinance statement/insider functions re-raise instead
  of caching prose as truth; `TRANCHE_WEIGHTS` env coerces to floats (was
  silently disabling the tranche fold); and six analyst tools the prompts
  instructed (get_expected_move, get_institution_holdings,
  get_earnings_surprise_history, get_momentum_scan, get_market_snapshot_alpaca,
  get_insider_transactions) are now actually bound. Edge fixes: percent-field
  unit drift, moomoo rate-limit classification + forex/futures fallback,
  non-circular pre-market ledger realized return, `--rank composite` wiring,
  pipeline worker cap, `--illiq` flag. The Portfolio Manager now receives the
  deterministic CVaR/liquidity context it was meant to argue from. Docs/config
  aligned (overlay defaults, missing env overrides, entry-point flags); web
  `--illiq` forwarded. See CHANGELOG for the full list.

- [2026-08-27] **EODHD real-time snapshot + top movers** - the Massive
  snapshot / top-movers endpoints are 403 on the free plan; EODHD's
  `/api/real-time` works on the EOD plan and now backs them:
  `get_market_snapshot_eodhd` (live OHLCV + prev close + change%) and
  `get_top_movers_eodhd` (bulk `?ex=US` ~18k stocks sorted by change_p). The
  `get_market_snapshot` / `get_top_movers` tools fall back to EODHD when
  Massive 403s.

- [2026-08-27] **Truncation-retry enforcement** - when an LLM response is cut
  at the output cap (ends mid-sentence), the agent re-invokes with a
  continuation prompt and merges, so reports are never truncated. Wired into
  every agent path: PM/RM/trader/sentiment free-text fallback, the 3 analyst
  tool-calling chains, and the bull/bear researchers + 3 risk debators. Up
  to 2 continuation attempts, only when a cut is detected; a failed
  continuation degrades to the original text.

- [2026-08-27] **Tool-wiring audit: 4 new market tools + OHLCV cache +
  computed sentiment on** - the audit found strategy functions that were
  implemented but never exposed to the analyst LLMs, and duplicate OHLCV
  fetches across tools. New market tools: `get_technical_factors` (ADX/pivots/
  Aroon/Fisher/Chaikin/Elder-Ray/Supertrend/volume-profile in one call),
  `get_book_tail_risk` (portfolio CVaR + correlated stress + drawdown gate),
  `get_liquidation_days` (block-absorption days), `get_premarket_review`
  (CONFIRM/REVISE/REJECT arbiter). A run-level OHLCV cache makes every tool
  share ONE vendor fetch per ticker per run (no duplicate data).
  `enable_sentiment` is now on (computed StockTwits score + surprise velocity
  injected into the sentiment report).

- [2026-08-27] **Market tool-node binding fix + higher output cap** - the
  market analyst's prompt listed `get_swing_exits` / `get_dip_technical` /
  `get_mean_reversion_tech` and the 5 market-session tools, but they were never
  registered in the market `ToolNode` (a wiring gap from the original
  value-dip+swing commits) — every run had the LLM call tools that error "not a
  valid tool". All 8 are now bound. `max_output_tokens` / `_quick` raised
  6000 → 8000 after 2026-08-27 WDC analyst reports truncated mid-sentence at
  the 6000 cap.

- [2026-08-27] **EODHD primary + eodhd-us default universe** - the
  `core_stock_apis` chain is now `eodhd,moomoo,yfinance` (EODHD first,
  moomoo/yfinance fallback); `news_data` and `corporate_actions` also lead
  with EODHD. New EODHD endpoints: news, splits/dividends, and the full US
  symbol list (~18k common stocks) — the screener's default `--universe
  eodhd-us` (no moomoo quota). moomoo movers (`top-losers`/`heat-proxy`)
  stay as the optional intraday source. Fundamentals/technicals/intraday/
  options are not on the EOD plan, so those chains keep moomoo/yfinance.

- [2026-08-27] **EODHD vendor (daily OHLCV)** - new `dataflows/eodhd.py`
  serves daily bars in the same CSV shape as yfinance/moomoo, wired into the
  `core_stock_apis` chain (`moomoo,eodhd,yfinance`) and as a `--vendor eodhd`
  preset. Key: `TRADINGAGENTS_EODHD_API_KEY`. Free tier 20 calls/day; EOD
  plan $19.99/mo = 100k calls/day @ 1000/min, 30+ years — replaces the moomoo
  K-line quota (100 calls/7 days) the value screener exhausts.

- [2026-08-27] **Value-screener web-timeout fixes** - (1) every moomoo SDK
  call now runs under a 5s wall-clock timeout (`TRADINGAGENTS_MOOMOO_CALL_TIMEOUT`,
  default 5.0) instead of the SDK's own 20s per-call wait, so a degraded
  gateway can't stall a run; (2) the value-dip gating pass pre-filters on
  cheap OHLCV-only technicals (RSI/%b/stop) before the heavy fundamentals
  fetch, dropping ~7 vendor calls/symbol to 1 for non-candidates; (3) the
  web `run_screener` budget is 2400s and a timed-out capability kills its
  whole process tree so no orphaned process holds a moomoo connection.

- [2026-08-26] **Correlation-aware allocation** - the allocation plan
  (`portfolio.allocation_block`, the `get_allocation` analyst tool, and the
  screener's `--alloc`) now accepts return series and, when
  `TRADINGAGENTS_ENABLE_CORRELATION_PENALTY=true`, down-weights names whose
  average pairwise correlation with the rest of the book exceeds
  `TRADINGAGENTS_CORRELATION_THRESHOLD` (default 0.6) by
  `TRADINGAGENTS_CORRELATION_PENALTY_FRAC` (default 0.3) before the
  per-name/per-sector caps - risk-parity style concentration control
  (industry-practice item 1). Names without a measurable return series are
  never penalized (no fabrication).

- [2026-08-24] **Per-role max output tokens + density directives** - new env keys
  `TRADINGAGENTS_MAX_OUTPUT_TOKENS(_QUICK/_DEEP)` cap the LLM output via
  `max_tokens` (quick=analysts/researchers/debaters/trader 6000, deep=RM/PM
  2500, based on measured report sizes + your `min(1,048,576, 1,310,720 - input)`
  formula).
  Every agent prompt now carries a `get_output_budget(...)` directive: dense,
  bounded, tool-call-first (never approximate a number you can fetch).

- [2026-08-24] **OpenRouter provider-ignore routing** - add a configurable
  slow-provider blocklist: set `TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS` in
  `.env` (comma-separated provider slugs). It is sent as `provider.ignore` in
  the OpenRouter request body via `extra_body`, so OpenRouter skips those
  endpoints (e.g. slow/unreliable ones) on every request. No restriction when
  unset.

- [2026-08-23] **Free computed ratios (no paid Massive plan)** - new
  `strategies/ratios.py` replicates the plan-gated Massive `get_ratios` block
  locally from the project's own canonical statements: EV, EV/EBIT, EV/EBITDA,
  EV/Sales, P/E, P/B, P/S, P/CF, P/FCF, ROE, ROA, D/E, Current, Quick, cash
  ratio, dividend yield, FCF, market cap. Exposed as `get_ratios` on the
  fundamentals analyst (computed, free). Adds the `inventory` canonical alias
  so Quick ratio computes. A latent double-`@tool` bug in analysis_tools.py
  (which broke import once the file grew) was also fixed.

- [2026-08-23] **SEC EDGAR -> Massive insider fallback** - `get_sec_filings` now
  falls back to Massive's Form-4 insider-activity data when official SEC EDGAR
  fails for any reason (HTTP 403 from SEC fair-access throttling, network
  failure, or a non-US ticker with no EDGAR record). The fallback result is
  clearly labelled as insider-activity-only so the agent never mistakes Form-4
  for the full 8-K/10-K set; if both sources fail it returns an explicit
  unavailable message (no fabrication).

- [2026-08-23] **Web UI (sibling project)** - `TradingNew/trading_web/` (outside this
  repo, per the layout rule): a React SPA + FastAPI interface covering every
  capability (batch/pipeline/screener/pre-market/nightly/decision-history/
  reports/raw-read-only) with login security (scrypt passwords, HMAC-signed
  sessions, CSRF, lockout, path-defense, CSP, audit log). See
  `TradingNew/trading_web/README.md`.

- [2026-08-22] **Pre-market review (overnight reviewer)** - closes the gap
  between a close-time decision and the next open: a deterministic arbiter
  (`strategies/pre_market.py` - gap / catalyst-window / re-anchored tranche /
  cap breach -> CONFIRM/REVISE/REJECT), a `PreMarketVerdict` schema + a
  deep-think prompt-variant reviewer (no new graph node), a standalone
  `scripts/pre_market_review.py` for the pre-open gap/anchor path, and an
  opt-in same-night `batch.py` step (`enable_pre_market_review`). Design in
  `docs/pre_market_review.md`.
- [2026-08-22] **Pre-market review follow-up (fixes + features)** - defect
  fixes: the standalone script now extracts the prior plan's entry/stop and
  re-anchors the tranche plan to the measured open (gap/through-stop/adverse-fill
  checks actually run), the batch hook passes `results_dir` so it finds the
  full state JSON, and `_fetch_deltas` prefers a real-time pre-market price
  (Alpaca when enabled else yfinance `fast_info.last_price`) + ATR(14).
  Features: `scripts/nightly_review.py` (drive reviews from the batch summary),
  a paper-book ledger (`pre_market_ledger.jsonl` with pending->realized
  resolution), guarded overnight-headline context for the reviewer, and
  `scripts/decision_history.py` (per-ticker decision series).

- [2026-08-22] **Blank-symbol yfinance hardening** - a whitespace/empty ticker
  (e.g. a malformed LLM tool call in `batch.py --symbols ...`) previously
  leaked yfinance's raw `TypeError: 'NoneType' object does not support item
  assignment` + HTTP-4xx ERROR noise; it now canonicalizes to `""` and raises
  the typed NoMarketDataError, so the router returns one clean
  `NO_DATA_AVAILABLE: blank/empty ticker symbol` sentinel the agents report
  honestly.

- [2026-08-22] **Value Dip gaps (Step-1 + Step-2)** - five more deterministic strategies close the original doc's gaps: `balance_sheet_health` (D/E < 1.0 OR current ratio > 1.5) + `profitability_quality` (FCF + ROE > 15%) as Step-1 gates; the Step-2 technical ladder (`macd_divergence` on Daily RSI/MACD, `volume_dry_up` / `trigger_candle` RVOL>=1.3 / `higher_low_structure` composed into `vdu_entry_setup`), `support_structure` (multi-month base / 200-SMA), and the `decline_driver_check` negative-force screen. Exposed as five new analyst `@tool`s (market: get_macd_divergence / get_vdu_entry_setup / get_support_structure; fundamentals: get_balance_sheet_health / get_decline_driver_check); `value_dip_setup` and the `--scan value-dip` screener now gate on the new rows when measured. Hermetic-tested, doc'd.

- [2026-08-22] **Tranche risk fold (risk governor)** - with `enable_tranche_risk` (+ `tranche_*` keys), the risk governor sizes/throttles against the worst-case 3-tranche scale-in measured from the close + config-frozen weights (never the LLM): the **peak-deployed-at-scale-in** fraction is the per-trade cap the governor bounds (scale-in ties up more capital near the lows), and the **capital-at-risk** budget (sum of per-tranche losses at the hard stop) is enforced via `govern()`'s new `capital_at_risk_pct`/`risk_cap_pct` check. `build_position_contract` gains a weighted `entry_price` hook so the G1 stop/risk matches the tranche execution; the Risk Gate report block shows `Tranche peak-deployed` / `Tranche capital-at-risk`. Hermetic-tested.

- [2026-08-22] **Value Dip + Swing hybrid** - new `strategies/value_dip.py` implements the math from `Strategies/Value_Dip_swing.md` + `Value_Dip_swing_Continue.md` (Bollinger %b, historical valuation Z, FCF yield, breakeven win rate / expectancy, 3-tranche scale-in plan with weighted avg entry + composite stop + capital-at-risk check + blended 1.8R/3.0R, and the hybrid allocation matrix). Six new analyst `@tool`s bound to the market/fundamentals tool loops (`get_bollinger_pct_b`, `get_tranche_plan`, `get_trade_expectancy`; `get_fcf_yield`, `get_valuation_z_score`, `get_value_dip_setup`) so the agents reason over computed numbers, plus a new `--scan value-dip` screener mode. Config `enable_value_dip`; hermetic-tested.

- [2026-08-21] **Per-test timers** - every test runs under a `pytest-timeout` deadline (180s per-test default, thread method, 30-min session cap) so a hung vendor/network call can never block the whole session indefinitely; the live-vendor modules (`value_screener`/`scan_strategies`/`growth_screens`/`structured_agents`) carry a 600s module-level override. See `docs/developer/10-tests-layout.md`.
- [2026-08-21] **True portfolio CVaR (risk governor)** - the governor's daily
  tail budget can now come from the *weighted basket's* historical CVaR
  (`book_risk.portfolio_cvar`) instead of the single analyzed name: set
  `risk_basket_tickers` (comma list) + optional `risk_basket_weights` (k=v pairs
  or JSON) in config/env. Falls back to single-name when unconfigured/unresolvable.
- [2026-08-21] **Risk Gate shows both CVaRs** - with a basket configured, each
  report's `Risk Gate (computed)` block now shows `Analyzed-name CVaR` (the
  analyzed ticker's own tail) next to `Portfolio (book) CVaR — this fed the
  gate`; the same numbers are computed-injected into the Portfolio Manager
  prompt (`**Computed daily-tail CVaR**`) so the PM reasons from them.
- [2026-08-21] **Session-discipline + earnings-quality tool audit** - two more deterministic strategies exposed as analyst `@tool`s: `get_session_discipline` (intraday walk-away rules: giveback / max-daily-loss / past 10:00 ET optimal + psych levels, market node; wraps `momentum.session_flags`) and `get_earnings_quality` (Sloan accruals ratio folded into the forensic trap verdict incl. the accrual evidence trigger; fundamentals node; surfaces `normalized.accruals_ratio` that `screen_ticker`'s trap call had dropped). Bound in `_create_tool_nodes` + prompt; 6 hermetic tests; also documented the previously-omitted `TRADINGAGENTS_ENABLE_MASSIVE_FLAT` / `TRADINGAGENTS_MASSIVE_FLAT_DIR` env keys and sync'd `.env.example`.
- [2026-08-20] **Strategies index** - added `Strategies/index.md`, a navigation map linking every strategy plan doc under `Strategies/` to its implementation modules, config gates, scan modes, and consumers. Wired into the README docs pointer.
- [2026-08-20] **DCF valuation tool** - `get_dcf_valuation` + `strategies/dcf.py`: a pragmatic free-cash-flow DCF the fundamentals analyst can cite (fair value, EV, terminal-value share, WACC from provider data: cashflow statements, 10y treasury, beta, shares/cash/debt). Built from `Strategies/Discounted_Cash_Flow.md`; growth/ERP are analyst overrides; degrades to 'unavailable' if no usable FCF.
- [2026-08-20] **Massive no-data failover fix** - the direct Massive tool wrappers now degrade to an explicit "unavailable" string (instead of raising `NoMarketDataError`) when the vendor lacks a symbol's data, so a batch run falls back to moomoo/yfinance and completes instead of failing the whole symbol. Regression-tested in `tests/test_massive_vendor.py` (8 cases).
- [2026-08-20] **Data providers doc** - `docs/developer/12-data-providers.md` catalogs all **13 data providers** (8 routed vendors: yfinance, FRED, Polymarket, Alpha Vantage, Finnhub, SEC EDGAR, Moomoo, Massive; + 5 direct sources: Alpaca, FMP, Reddit, StockTwits, float_shares), with per-category chains and API-key gates.
- [2026-08-20] **Agent decision-tools** - `docs/developer/11-agent-decision-tools.md` plans + implements six computed decision tools the analyst LLMs now cite: `get_exit_check` (stop/target/action), `get_allocation` (cap-respecting book), `get_regime_components` (vol/trend/chop), `get_consensus` (rating agreement, also injected into the PM), `get_momentum_detail` (pillars/rvol/vwap), `get_beat_miss_sizing` (event multiplier). All bound to market/fundamentals/news tool nodes + hermetic-tested.
- [2026-08-21] **Credit-stress read (FRED OAS)** - `get_credit_spread_read(date)` bound to the market analyst: the ICE BofA US high-yield OAS series (HY `BAMLH0A0HYM2`, CCC & lower `BAMLH0A3HYC`, BB `BAMLH0A1HYBB`) flattened by `strategies/credit_spread.py::credit_stress_level` into a deterministic credit-cycle band (low/high/severe) + a 0..1 de-risk scale (thresholds: HY <3% low / 3.5-4.5% moderate / >5.5% severe; CCC <8% low / 10-12% moderate / >15% severe). FRED aliases `hy_oas` / `ccc_oas` / `bb_oas` added to the macro vendor; the read degrades to explicit 'unavailable' when `FRED_API_KEY` is unset. 8 hermetic tests; docs/README/CHANGELOG kept true.
- [2026-08-21] **Second decision-tool batch** - five more deterministic strategies exposed as analyst `@tool`s so the LLMs cite computed numbers instead of guessing: `get_sector_rank` (11-SPDR 1m/3m momentum + the ticker's sector standing, market node), `get_strategy_quality` (net CAGR / vol / Sharpe / max drawdown over a return series, market), `get_margin_of_safety` ((intrinsic-price)/intrinsic band, fundamentals), `get_composite_rank` (value+momentum composite percentile vs industry peers, fundamentals), `get_tail_risk` (VaR/CVaR tail budget + -10% stress loss, market). Bound in `_create_tool_nodes` + each analyst's tools list/prompt; 12 hermetic tests; ruff-clean.
- [2026-08-20] **Developer docs set** - added `docs/developer/` with 11 focused guides (topology, graph topology + run, dataflow/vendors, strategies, agents/tools, entrypoints, persistence, dev guide, Massive integration, tests layout) covering the *whole* project for a joining developer.
- [2026-08-20] **Massive Flat-File screener (folder, OFF by default)** - the value-screener's `_fetch_ohlcv` reads a Massive day-aggregates folder (`TRADINGAGENTS_MASSIVE_FLAT_DIR` / `massive_flat_dir`, default `data/massive_flat`) ONLY when `TRADINGAGENTS_ENABLE_MASSIVE_FLAT=true` (default OFF), giving bulk-history ATR/ATR-pct/scan bases before the per-ticker vendor chain. Opt-in, >=15-row gate; hermetic-tested. Also validated a live end-to-end `batch.py` run to AAPL (Underweight) exercising the new Massive tools.
- [2026-08-20] **Massive NOI + Flat Files (item 8)** - `massive_noi.py` (WebSocket Net Order Imbalance streamer + `scripts/massive_noi_monitor.py` monitor app) and `massive_flat.py` (bulk Flat-File day-aggregates loader into per-ticker OHLCV for the screener/backtests). Both are **plan-gated standalone utilities** - not batch `@tool`s. NOI needs the Imbalances Expansion add-on; Flat Files need Starter+.
- [2026-08-20] **Massive corporate actions, peers & IPOs (row 5)** - `get_company_peers` gains a `massive` option (`related-companies`, finnhub-format-compatible); `get_corporate_actions`/`get_dividends` (dividends + splits) bind Massive to the fundamentals analyst; `get_ipos` (IPO reference) binds to the news analyst. All entitled on the current tier (probed 200).
- [2026-08-20] **Massive fundamentals/ratios + snapshots (plan-aware)** - `get_ratios` (precomputed EV/EBITDA, P/E, P/B, ROE/ROA, FCF), `get_market_snapshot` (consolidated day/quote), and `get_top_movers` wired to the market/fundamentals analysts + `pipeline.py --universe top-movers-massive`. These endpoints return 403 on the free Basic plan, so all degrade with an explicit "upgrade at massive.com/pricing" message and activate when the plan includes them.
- [2026-08-20] **Massive Form-4 insider activity** - `get_form4_insider(ticker, start, end)` bound to the fundamentals analyst reports net open-market insider buying (buys P minus sells S, excluding grant/exercise A/M) from SEC Form 4 via Massive. 13-F institutional holdings are deliberately NOT wired (the endpoint has no security filter - only filer_cik/filing_date - so a per-ticker aggregate would be misleading); moomoo `get_institution_holdings` remains the source.
- [2026-08-20] **Massive short-interest/short-volume** - `get_short_interest_massive` adds a `massive` `short_interest` vendor (FINRA 2-week settlement: shares short, days-to-cover, avg daily volume); a dedicated `get_short_volume(ticker, start, end)` tool surfaces the daily short-sale volume ratio to the market analyst. Both degrade cleanly via the error taxonomy.
- [2026-08-20] **Massive economy + catalyst OpenD decoupling** - `get_macro_indicators_massive` adds a `massive` `macro_data` vendor (treasury-yields / inflation / inflation-expectations / labor-market, FRED-compatible aliases like `10y_treasury`/`yield_curve`/`cpi`); a deterministic `macro_backdrop` (yield-curve inversion x0.70, elevated 10y breakeven x0.75) keeps the B1 catalyst overlay de-risking near macro stress even when the moomoo OpenD event calendar is down — `fetch_catalyst_data` now degrades per-section instead of nulling the overlay on moomoo failure.
- [2026-08-20] **Massive.com vendor (news sentiment)** - new `dataflows/massive.py` + `get_massive_news`: per-article **structured sentiment** (positive/negative/neutral + reasoning) from `/v2/reference/news`, ticker-filtered; bound to the news/social tool nodes + news analyst; `get_news` chain gains a `massive` vendor (opt-in). Key: `MASSIVE_API_KEY`. US-only additive vendor — see `docs/massive_integration.md`.
- [2026-08-20] **Moomoo period-order + prior-period fix** - the value screener
  used to keep the OLDEST statement period (moomoo lists newest-first) and
  never supplied prior-period values, so the **Beneish M column was always
  `n/a`** and every metric (EY, EV/EBIT, F, Z, EpsYoY...) was computed on
  stale fiscal-2022-era data. The canonical parser is now period-order aware,
  emits `{current, prior}` dicts, skips moomoo `-` sub-item/contra lines, and
  fixes a `d&a` alias that silently aliased depreciation to SG&A. **M now
  computes** (e.g. MT -2.29, WMT -2.72). NetNet staying `no` on large caps is
  expected (needs `CA - TL` negative-threshold), not a bug.
- [2026-08-19] **Finnhub free-tier integration** - live-probed your key and wired the endpoints that work: `get_basic_financials` (EPS/revenue YoY + ROE metrics feed the screener `--min-eps-yoy/--min-rev-yoy/--min-roe` gates and the Fundamentals analyst), `get_insider_activity` (computed 12m net insider change + mspr + trend), `get_company_peers`, and Finnhub as the second-tier `--sector-rank` sector source (FMP → Finnhub → yfinance). All key-gated/guarded, no-fabrication.
- [2026-08-19] **Computed-analysis tools - follow-up batch (6 more)** - `get_regime_read`, `get_volatility_contraction`, `get_orderflow_read` bound to the Market analyst; `get_analyst_verdict` (EY/EV/EBIT/F/M/Z/trap-risk/ROE/YoY), `get_earnings_surprise`, `get_portfolio_weights` bound to the Fundamentals analyst. Full set = 12 computed-signal tools for the analyst LLMs.
- [2026-08-19] **Computed-analysis tools for the analyst LLMs** - `get_swing_set`, `get_relative_strength`, `get_earnings_event_read`, `get_catalyst_scale`, `get_position_sizing`, `get_risk_gate` wrap the deterministic strategy calculators (`strategies/{swing,relative_strength,events,catalyst,size,risk_governor}`) as LangChain tools bound to the market + news analyst tool loops - the agents now reason over computed stops/targets/RS/surprise/catalyst-scale/sizing/risk-gate numbers instead of re-deriving (or inventing) them. All follow the no-fabrication contract (exact numbers or explicit 'unavailable').
- [2026-08-19] **Framework Phase-1 screens** - optional `--min-eps-yoy` / `--min-rev-yoy` (moomoo statement YoY columns; also fixed moomoo markdown `##`-header payloads never reaching the parser), `--min-roe`, `--max-mcap`, `--sector-rank` (SPDR top-3 by 1m/3m momentum), `--revision` (net analyst upgrades 60d), `--inst-accum` (two-quarter institutional %-of-float); new EpsYoY/RevYoY/ROE, Sec/Rank, RevUp, Inst columns; gates only apply to measured values, missing data renders n/a.
- [2026-08-19] **VCP scan (`--scan vcp`)** - `strategies/swing.py::vcp_setup` (the classic 15%->8%->3% volatility-contraction base: strict pivot troughs, last-3 pullback depths vs the base high must contract, deepest pullback within 30%, fading volume across troughs - absent volume never fails); new screener mode with `VCP`/`Brk` columns; `swing_report` carries the VCP block as an extra signal; mode docs in `Strategies/scan.md`. Suite 924 passed / 2 skipped.
- [2026-08-19] **Swing scan + relative strength + catalyst hard veto** - new `--scan swing` screener mode built on `strategies/swing.py` (20-EMA-over-rising-50/200-SMA trend stack, RSI 45-70 band, pullback-into-EMA on fading volume, 1-ATR swing-low stop, 2R/3R targets, T1 scale-out + 20-EMA trail) and `strategies/relative_strength.py` (RS line vs `benchmark_ticker`, 63-day uptrend + new-high position + negative-divergence); PEAD post-earnings entry helpers (`events.py`); optional `catalyst_hard_block_days` that makes the risk governor REJECT new risk inside the earnings window; `Strategies/scan.md` filled with all scan-mode docs. Source: `Strategies/framework.md`. Suite 888 passed / 2 skipped.
- [2026-08-19] **Repo hygiene pass** - full lint cleanup to a green `ruff check` across `tradingagents/`, `scripts/`, `tests/`, `cli/` and the entry scripts, plus defect fixes found by the lint pass: removed a stale `__all__` entry in the Alpaca vendor (`latest_snapshot` -> `get_latest_snapshot`), fixed an unimported `Mapping` annotation, `raise ... from None` for expected data-format errors, explicit `zip(strict=)` everywhere, import-order fix in `batch.py`, deleted the committed scratch file `test.py`; **documentation completed**: `.env.example` now mirrors all 53 supported `TRADINGAGENTS_*` overrides (Alpaca/Finnhub/FMP keys, moomoo tuning, all strategy/catalyst/risk toggles, persistence paths), `docs/api_reference.md` deduped + env table completed, dev-machine paths scrubbed from `docs/AGENT_ONBOARDING.md`. Suite 843 passed / 2 skipped; "pip check" clean (rich / cryptography satisfied).
- [2026-08-19] **Fork changelog (since last remote)** - B2 cross-sectional pipeline (`pipeline.py`: universe -> value-screen -> composite rank -> top-N -> concurrent moomoo batch, with `reports/pipeline_<ts>.md` summaries and per-symbol TOC reports); **A-series analyst tools** (moomoo, optional) `get_institution_holdings` (13F-style institutional % + period change), `get_earnings_surprise_history` (EPS surprise vs estimate per print with day reaction and NaN-safe rendering), `get_expected_move` (option-implied 1-sigma move at the next earnings + price band), wired to the market/fundamentals analysts; **catalyst overlay (B1) on by default** (`enable_events`) plus moomoo earnings-calendar fixes (7-day-inclusive cap, real column normalization, 4-tuple unpacking) verified live (AVGO 2026/Q3 implied move 9.4%, band [328.39, 396.57]); **docs**: `docs/api_reference.md` (config keys, graph flow, vendor contract, overlays) and `docs/howto_end_to_end.md` (screener -> pipeline -> reports). Suite 843 passed / 2 skipped, clean exit; no env/credentials committed.
</td></tr>
</table>
- [2026-07] **TradingAgents v0.3.1** released with correctness and stability fixes: Alpha Vantage look-ahead filtering, graph-router crash-safety, graph-shape-aware checkpoint resume, working crypto sentiment sources, a configurable LLM retry budget, Bedrock API-key auth, and Claude Sonnet 5 / Fable 5 support. See [CHANGELOG.md](CHANGELOG.md) for the full list.
- [2026-06] **TradingAgents v0.3.0** released with a verified data-access contract, an expanded provider registry (NVIDIA, Kimi, Groq, Mistral, Bedrock, and any OpenAI-compatible endpoint), FRED and Polymarket data vendors, a current-generation model catalog, and a CI gate.
- [2026-05] **TradingAgents v0.2.5** released with the grounded Sentiment Analyst, GPT-5.5 etc. model coverage, Qwen/GLM/MiniMax dual-region support, `TRADINGAGENTS_*` env-var configurability with API-key auto-detection, remote Ollama support, non-US alpha benchmarks, and ticker path-traversal hardening.
- [2026-04] **TradingAgents v0.2.4** released with structured-output agents (Research Manager, Trader, Portfolio Manager), LangGraph checkpoint resume, persistent decision log, DeepSeek/Qwen/GLM/Azure provider support, Docker, and a Windows UTF-8 encoding fix.
- [2026-03] **TradingAgents v0.2.3** released with multi-language support, GPT-5.4 family models, unified model catalog, backtesting date fidelity, and proxy support.
- [2026-03] **TradingAgents v0.2.2** released with GPT-5.4/Gemini 3.1/Claude 4.6 model coverage, five-tier rating scale, OpenAI Responses API, Anthropic effort control, and cross-platform stability.
- [2026-02] **TradingAgents v0.2.0** released with multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x) and improved system architecture.
- [2026-01] **Trading-R1** [Technical Report](https://arxiv.org/abs/2509.11420) released, with [Terminal](https://github.com/TauricResearch/Trading-R1) expected to land soon.

<div align="center">

🚀 [TradingAgents](#tradingagents-framework) | ⚡ [Installation & CLI](#installation-and-cli) | 🎬 [Demo](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [Package Usage](#tradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Citation](#citation)

</div>

> 🎉 **TradingAgents** officially released! We have received numerous inquiries about the work, and we would like to express our thanks for the enthusiasm in our community.
>
> So we decided to fully open-source the framework. Looking forward to building impactful projects with you!

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. By deploying specialized LLM-powered agents: from fundamental analysts, sentiment experts, and technical analysts, to trader, risk management team, the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents framework is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. [It is not intended as financial, investment, or trading advice.](https://tauric.ai/disclaimer/)

Our framework decomposes complex trading tasks into specialized roles.

### Analyst Team
- Fundamentals Analyst: Evaluates company financials and performance metrics, identifying intrinsic values and potential red flags.
- Sentiment Analyst: Aggregates news headlines, StockTwits, and Reddit chatter into a single sentiment read to gauge short-term market mood.
- News Analyst: Monitors global news and macroeconomic indicators, interpreting the impact of events on market conditions.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) to detect trading patterns and forecast price movements.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions, determining the timing and magnitude of trades.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## Installation and CLI

### Installation

Clone TradingAgents:
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.12
conda activate tradingagents
```

Install the package and its dependencies:
```bash
pip install .
```

### Docker

Alternatively, run with Docker:
```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

For local models with Ollama:
```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required APIs

TradingAgents supports multiple LLM providers. Set the API key for your chosen provider:

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen — International (dashscope-intl.aliyuncs.com)
export DASHSCOPE_CN_API_KEY=...    # Qwen — China (dashscope.aliyuncs.com)
export ZHIPU_API_KEY=...           # GLM via Z.AI (international)
export ZHIPU_CN_API_KEY=...        # GLM via BigModel (China, open.bigmodel.cn)
export MINIMAX_API_KEY=...         # MiniMax — Global (api.minimax.io)
export MINIMAX_CN_API_KEY=...      # MiniMax — China (api.minimaxi.com)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
```

For Azure OpenAI, copy `.env.enterprise.example` to `.env.enterprise` and fill in your credentials.

For AWS Bedrock, install the extra with `pip install ".[bedrock]"`, set `llm_provider: "bedrock"`, configure AWS credentials (environment variables, `~/.aws/credentials`, or an IAM role) and `AWS_DEFAULT_REGION`, and use a Bedrock model ID, e.g. `us.anthropic.claude-opus-4-8-v1:0`.

For local models, configure Ollama with `llm_provider: "ollama"`. The default endpoint is `http://localhost:11434/v1`; set `OLLAMA_BASE_URL` to point at a remote `ollama-serve`. Pull models with `ollama pull <name>`, and pick "Custom model ID" in the CLI for any model not listed by default.

For any other OpenAI-compatible server (vLLM, LM Studio, llama.cpp, or a custom relay), use `llm_provider: "openai_compatible"` and set the endpoint via `backend_url` (or `TRADINGAGENTS_LLM_BACKEND_URL`), e.g. `http://localhost:8000/v1` for vLLM or `http://localhost:1234/v1` for LM Studio. The model is whatever your server serves. No key is needed for local servers; set `OPENAI_COMPATIBLE_API_KEY` when the endpoint requires one.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```
You will see a screen where you can select your desired tickers, analysis date, LLM provider, research depth, and more.

### Markets and tickers

TradingAgents works with any market Yahoo Finance covers, using the exchange-suffixed ticker. Company identity and the alpha benchmark resolve automatically per market.

- US: `AAPL`, `SPY`
- Hong Kong: `0700.HK` · Tokyo: `7203.T` · London: `AZN.L`
- India: `RELIANCE.NS`, `.BO` · Canada: `.TO` · Australia: `.AX`
- China A-shares: Shanghai `.SS`, Shenzhen `.SZ` (e.g. `600519.SS` for Kweichow Moutai)
- Crypto: `BTC-USD`, `ETH-USD`

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen (Alibaba DashScope, international and China endpoints), GLM (Zhipu), MiniMax (global + China), OpenRouter, Ollama for local models, and Azure OpenAI for enterprise.

### Python Usage

To use TradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # e.g. openai, google, anthropic, deepseek, groq, ollama; openai_compatible covers any OpenAI-compatible endpoint (vLLM, LM Studio, llama.cpp, ...)
config["deep_think_llm"] = "gpt-5.5"     # Model for complex reasoning
config["quick_think_llm"] = "gpt-5.4-mini" # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

## Persistence and Recovery

TradingAgents persists two kinds of state across runs.

### Decision log

The decision log is always on. Each completed run appends its decision to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, TradingAgents fetches the realised return (raw and alpha vs SPY), generates a one-paragraph reflection, and injects the most recent same-ticker decisions plus recent cross-ticker lessons into the Portfolio Manager prompt, so each analysis carries forward what worked and what didn't.

Override the path with `TRADINGAGENTS_MEMORY_LOG_PATH`.

### Checkpoint resume

Checkpoint resume is opt-in via `--checkpoint`. When enabled, LangGraph saves state after each node so a crashed or interrupted run resumes from the last successful step instead of starting over. On a resume run you will see `Resuming from step N for <TICKER> on <date>` in the logs; on a new run you will see `Starting fresh`. Checkpoints are cleared automatically on successful completion.

Per-ticker SQLite databases live at `~/.tradingagents/cache/checkpoints/<TICKER>.db` (override the base with `TRADINGAGENTS_CACHE_DIR`). Use `--clear-checkpoints` to reset all of them before a run.

```bash
tradingagents analyze --checkpoint           # enable for this run
tradingagents analyze --clear-checkpoints    # reset before running
```

```python
config = DEFAULT_CONFIG.copy()
config["checkpoint_enabled"] = True
ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

## Reproducibility

TradingAgents is LLM-driven, so two runs of the same ticker and date can differ. This is expected for a research tool built on language models, not a defect. The variation comes from a few distinct sources, and it helps to separate them.

Language model sampling is non-deterministic. Even at a fixed temperature, providers do not guarantee byte-identical output across calls, and reasoning models (the default GPT-5.x family, and any thinking-mode model) vary the most because their internal reasoning is itself sampled.

Live data moves. News, StockTwits, and Reddit return different content as time passes, so a run today sees different inputs than a run last week even for the same historical trade date. Pin the analysis date to hold the price and indicator window fixed, but the social and news sources still reflect "now".

To reduce variation you can lower the sampling temperature. Set `temperature` in your config (or `TRADINGAGENTS_TEMPERATURE` in `.env`); lower values make models that honor it more repeatable. The current curated models are reasoning-first and largely ignore temperature, so for tighter reproducibility use a non-reasoning model, which you can set explicitly via the Custom model ID option.

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["temperature"] = 0.0
# Reasoning models ignore temperature. For tighter reproducibility, set a
# non-reasoning deep/quick model explicitly (e.g. via the Custom model ID option).
```

What does not vary anymore: the analyzed company identity is resolved deterministically from the ticker before any agent runs, and the market analyst grounds exact price and indicator claims in a verified data snapshot. Earlier reports of "different companies" or fabricated price levels across runs are addressed by these two mechanisms.

Backtest results are not guaranteed to match any published figure. Returns depend on the model, the temperature, the date range, data quality, and the sampling above. Treat the framework as a research scaffold for studying multi-agent analysis, not as a strategy with a fixed, replicable return.

> [!IMPORTANT]
> **⚠️ The sections below are additions made in this fork and are not part of the original upstream TradingAgents project.**
>
> ---
>
> **Docs**: [`docs/api_reference.md`](docs/api_reference.md) (config keys, graph, vendor contract, overlays), [`docs/howto_end_to_end.md`](docs/howto_end_to_end.md) (screener → pipeline → reports), the full developer map in [`docs/developer/`](docs/developer/00-index.md), and the strategy-plan index in [`Strategies/index.md`](Strategies/index.md).
>


<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Batch runner

A headless, concurrent runner ships alongside the interactive CLI. Run several symbols at once, auto-save reports in the same layout the CLI produces, and get a machine-readable summary — no interactive prompts.

```bash
python batch.py --symbols NVDA MSFT AAPL
python batch.py --symbols NVDA MSFT AAPL 0700.HK --date 2026-07-22 --workers 4
python batch.py --symbols NVDA --depth deep --analysts market news
```

Options: `--symbols` (required), `--date` (default today), `--workers` (default 3), `--depth` (`shallow`/`medium`/`deep`, default `deep`), `--analysts` (default all four teams). Each symbol gets its own memory log (`~/.tradingagents/memory/<TICKER>.md`), reports land in `./reports/<TICKER>_<timestamp>/`, and a per-run summary is appended to `./reports/batch_summary_<timestamp>.jsonl`. Configuration (provider, models, API key) is inherited from `.env`.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Extended data sources

Beyond the core price, fundamental, and news vendors, TradingAgents can pull additional free, decision-relevant signals (all optional — a vendor failure degrades gracefully instead of aborting a run):

- **Options market** (yfinance) — implied volatility, put/call open-interest and volume skew, surfaced to the market analyst.
- **SEC EDGAR filings** — 8-K (material events), 10-K/10-Q (reports), S-1/S-3 (capital raises), SC 13D/G (stake disclosures), surfaced to the news analyst.
- **Short interest / float** (yfinance) — days-to-cover, short % of float, ownership split, surfaced to the market analyst.
- **Analyst ratings & price targets** (Finnhub) — recommendation trends and consensus targets, surfaced to the fundamentals analyst.
- **Earnings calendar** (Finnhub) — upcoming earnings dates and EPS surprises, surfaced to the news analyst.
- **News with structured sentiment** (Massive.com) — per-article sentiment (positive/negative/neutral) + reasoning, surfaced to the news/social analysts via `get_massive_news`. Set `MASSIVE_API_KEY` (or `TRADINGAGENTS_MASSIVE_API_KEY`). US-centric additive vendor; see `docs/massive_integration.md`.
- **Macro economy + catalyst OpenD decoupling** (Massive.com) — `get_macro_indicators` gains a `massive` vendor (treasury yields / inflation / inflation-expectations / labor-market, FRED-compatible aliases); a deterministic `macro_backdrop` (yield-curve inversion / elevated breakevens) keeps the B1 catalyst overlay de-risking near macro stress even when the moomoo OpenD event calendar is unavailable.
- **Short interest / short volume** (Massive.com) — `get_short_interest` gains a `massive` vendor (FINRA 2-week settlement, days-to-cover / shares short); a dedicated `get_short_volume` tool surfaces the daily short-sale volume ratio to the market analyst.
- **Form-4 insider activity** (Massive.com) — `get_form4_insider(ticker, start, end)` surfaces net open-market insider buying (P−S, excluding grant/exercise) to the fundamentals analyst.
- **Fundamentals ratios + market snapshots** (Massive.com, plan-gated) — `get_ratios` (precomputed EV/EBITDA, P/E, ROE...) to the fundamentals analyst; `get_market_snapshot` / `get_top_movers` to the market analyst; `pipeline.py --universe top-movers-massive`. These 403 on the free Basic plan and degrade with an explicit upgrade message — they activate when the account's plan includes them.
- **NOI + Flat Files** (Massive.com, plan-gated) — `massive_noi.py` (WebSocket NOI monitor app) and `massive_flat.py` (bulk OHLCV loader) are standalone utilities: the screener's `_fetch_ohlcv` reads a Massive day-aggregates folder when the `enable_massive_flat` toggle is on (bulk ATR/scan bases), a NOI monitor app consumes the WebSocket feed, and `scripts/validate_massive_flat.py` sanity-checks a dropped CSV. NOI needs the Imbalances Expansion add-on; Flat Files need Starter+.
- **Corporate actions, peers & IPOs** (Massive.com, entitled) — `get_company_peers` gains a `massive` option (`related-companies`); `get_corporate_actions`/`get_dividends` (dividends+splits) bind Massive to the fundamentals analyst; `get_ipos` (IPO reference) binds to the news analyst.

Each source is a vendor behind the same `route_to_vendor` interface and is toggled per-category in `default_config.py` (`options_data`, `sec_filings`, `short_interest`, `analyst_ratings`, `earnings_calendar`). Set `finnhub_api_key` (or `TRADINGAGENTS_FINNHUB_API_KEY`) for the two Finnhub sources.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Moomoo OpenAPI vendor

Moomoo OpenAPI (formerly Futu OpenAPI) is available as an additional vendor behind the same `route_to_vendor` interface. It serves quotes/candlesticks, technical indicators, F10 financials, news, options chains, short interest, analyst consensus, the earnings calendar, and insider trades through the **local OpenD gateway** (TCP, default `127.0.0.1:11111`).

- **No credentials in `.env`** — install OpenD, log in once with your (free) moomoo account and tick "remember password". The project only connects to the gateway.
- **Headless autostart** — set `TRADINGAGENTS_MOOMOO_AUTOSTART=true` (default in `.env`) and `TRADINGAGENTS_MOOMOO_ACCOUNT=<your moomoo ID>` (not a password); the vendor launches OpenD with `-login_by_remember=1` when it is not running. `TRADINGAGENTS_MOOMOO_OPEND_PATH` overrides executable discovery. Note: OpenD is a local desktop gateway — inside Docker, moomoo simply degrades to the fallback vendors unless OpenD is reachable from the container.
- **Analyst parallelism (opt-in)** — set `TRADINGAGENTS_ANALYST_CONCURRENCY=2` (or `analyst_concurrency` in config) to run the analyst teams concurrently, each in its own thread with isolated messages. Multiplies LLM/provider load and free-tier quota burn — start with 2, keep 1 (default) for rate-limited setups.
- **Graceful fallback** — when OpenD is down, logged out, or lacks quote permission for a market, the router emits `DATA_UNAVAILABLE`/`NO_DATA_AVAILABLE` and falls back to the next configured vendor (yfinance, finnhub, …). Free quote rights cover US equities (LV3 promo), HK LV1, and crypto; A-shares and LSE/India are not covered for global accounts.
- **Financial statements honor the tool contract** — `get_balance_sheet`, `get_cashflow`, and `get_income_statement` accept the same `freq` (`annual`/`quarterly`) and `curr_date` arguments as the yfinance and alpha_vantage vendors: `freq` selects the annual vs. quarterly report type on the moomoo SDK, and `curr_date` filters out statements published after the trading day (look-ahead guard). `get_fundamentals` accepts `curr_date` the same way.
- Covered by default in `data_vendors` chains (`moomoo,yfinance` for prices/indicators/fundamentals/options/short-interest, `moomoo,finnhub` for ratings/earnings, `fred,moomoo` for macro). Prediction markets use `polymarket,moomoo` — Polymarket first, with moomoo's event contracts (category → series → event → contract → snapshot, live YES probabilities) as the fallback. Event contracts are server-gated to moomoo SG/MY accounts; other regions fall back to Polymarket automatically.

**Decision-quality tiers** (all moomoo-only, optional, degrade to a `DATA_UNAVAILABLE` sentinel when OpenD is down or gated):
- **Tier 1 — new evidence classes:** `get_capital_flow` (weekly net inflow by order size + session distribution → Market Analyst), `get_smart_money` (ARK institutional activity → Fundamentals), `get_economic_calendar` (dated CPI/FOMC/payroll catalysts → News), `get_fed_watch` (market-implied rate probabilities → News).
- **Tier 2 — enrichment:** `get_market_breadth` (sector heat map + rise/fall distribution → News), `get_revenue_breakdown` (segment mix/concentration → Fundamentals), `get_corporate_actions` (dividends/splits → Fundamentals), `get_earnings_catalyst` (historical earnings implied move + IV crush → News, feeds catalyst-risk sizing).
- **Tier 3 — accuracy infra:** the memory-log realized-return path uses moomoo's trading-day calendar for exact holding-day counting (falls back to the old calendar heuristic when OpenD is unreachable or the market is unsupported).

The `batch.py` runner accepts a `--vendor moomoo|yfinance|default` flag to force a vendor-chain preset across all categories per run.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Value watchlist screener

`scripts/value_screener.py` builds a master watchlist *before* spending analyst LLM budget: it screens each symbol through the same `route_to_vendor` chain (`fundamental_data` defaults to `moomoo,yfinance`), translating vendor output (CSV/markdown/JSON/text) into canonical line items and computing the classic screens — **EV/EBIT (Acquirer's Multiple), Earnings Yield, Piotroski F-Score, Beneish M-Score, Altman Z-Score and net-net** (see [`strategies/value_strategy.md`](strategies/value_strategy.md) and `strategies/Math.md` for the playbook). Missing rows render `n/a`, never a fabricated number.

The daily-changing universe can come from moomoo's intraday **top-movers"/"heat-proxy" rank** (领跌/领涨榜) — the biggest decliners at call time — so the watchlist rotates with the market:

```
python scripts/value_screener.py -u heat-proxy -n 50 -d 2026-06-30
```

`heat-proxy` is US-only (stocks only - ETFs/ETNs/funds/indices are excluded), takes the
official hot master (gainers+losers, hottest first) and keeps the losers of the moment,
then gates to **price ≥ $15, 0 < P/E (TTM) ≤ 40, market cap ≥ $10B**
(`--price-min 15`, `--pe-max 40`, `--min-mcap 10000000000`) plus
**30-day avg volume ≥ 1M shares** (`--min-avg-vol`) and
**ATR(14) ≥ 2% of price** (`--min-atr-pct`)
and **market cap ≥ $100B** (`--min-mcap`, default; float cap NEVER exceeds total
cap, so the total-cap floor covers the “cap or float cap ≥ $100B” rule) before
the value screens run. It uses moomoo's official trade rank as the stand-in
for the proprietary in-app **Heat List** (the composite Trade/Search/News
telemetry isn't exposed by any moomoo API — the web endpoint is signed and
undocumented). To use the literal app Heat List, save its top symbols to a
file and pass `-f list.txt`. Output includes the day's change, name, and a
screen-per-column table; pick from the ranked rows. Each run also saves
the watchlist to `screener/<finish_timestamp>.md` (e.g. `screener/20260817_180415.md`,
same `%Y%m%d_%H%M%S` format as reports; configurable via `--out-dir`).
Requires OpenD running +
logged in (same as every moomoo feature), and fails loudly if unavailable.

Numeric hygiene: statements reported in a non-USD currency (JPY etc., e.g.
many ADRs) are refused by the USD-only metrics (EV/EY/Acquirer/Z/net-net
render `n/a` instead of mixing currencies), and the day's % change is
normalized to a fraction regardless of the market session. `0` disables any gate.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Decision quality

The Portfolio Manager's structured output now captures the full risk-adjusted decision, not just a rating:

- `confidence` (0–1) — conviction in the decision.
- `position_size` — an explicit, risk-capped size that supersedes the trader's proposal.
- `stop_loss` — a risk-derived stop level.
- `consensus` (`high`/`low`) — a dissent flag when the aggressive/conservative/neutral analysts materially disagree.

The decision log also feeds an aggregate track record back into the Portfolio Manager: on each same-ticker run it injects the historical directional win rate, mean realized return, and mean alpha, so future decisions weigh past accuracy.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Report format (consolidated hierarchy + Table of Contents)

Every run writes a per-section tree (`1_analysts/`, `2_research/`, `3_trading/`, `4_risk/`, `5_portfolio/` — raw per-agent markdown) plus a consolidated `complete_report.md`. The consolidated file auto-demotes each agent's own headings 3 levels so its outline sits strictly under its role label:

```
#  Trading Analysis Report: <ticker>    ← document
## I. Analyst Team Reports              ← team
### Market Analyst                      ← role
  #### <the analyst's own title>        ← agent content
    ##### <their sections>
    ###### <details>
```

The agent's raw files (`1_analysts/market.md`, `2_research/bull.md`, …) stay byte-identical — only the consolidated view is re-nested. `complete_report.md` also opens with an auto-generated **Table of Contents** (GitHub-anchor links to every team and role).

To re-render the consolidated report for an existing folder (e.g. after a formatter change) without re-running the analysis — preserving the `Risk Gate (computed)` block when present:
```bash
py -3.12 scripts/rebuild_complete_report.py reports/SFTBY_20260819_115450
py -3.12 scripts/rebuild_complete_report.py      # all folders
```

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Operational hardening

- **Thread-safe configuration** — `set_config`/`get_config` are thread-local, so concurrent batch workers never leak per-symbol overrides into each other.
- **Vendor-result cache** — successful vendor fetches are cached on disk under a TTL (default 6 hours) to avoid re-burning free-tier API quotas; news is never cached, and failures are never cached.
- **Vendor-served logging** — the routing layer logs which vendor answered each call, making free-tier quota burn visible.
- **NaN-safe options chains** — yfinance option chains frequently carry missing/`NaN` open-interest, volume, and implied-volatility values; the options vendor skips non-finite values when summing (missing counts contribute 0) instead of crashing the call.
- **Reddit rate limiting** — Reddit fetches are paced process-wide to avoid 429s, with a `TRADINGAGENTS_DISABLE_REDDIT=1` kill-switch for heavy batch days.

</td></tr>
</table>

<table>
<tr><td style="border-left: 6px solid #8250df; padding-left: 1em;">

## Decision hardening (compute, don't narrate)

Spec: [`Strategies/decision_hardening_spec.md`](Strategies/decision_hardening_spec.md).
All config-gated, off by default:

- **G1 position & stop contract** - `tradingagents/strategies/contract.py`:
  size = min(Kelly, risk/stop) x vol x flow x agreement, 2x-ATR stop, with an
  audit reason string; graph attaches `position_contract` when
  `enable_position_contract` is on.
- **G2 confidence calibration** (`strategies/calibration.py`) - bucket
  realized win-rates from the ledger into `calibrated_confidence` and a
  calibration table for the PM (`enable_calibration`).
- **G3 measured consensus** (`strategies/consensus.py`) - `agreement_score`
  replaces the binary narrative flag; feeds G1. With `enable_independent_vote`
  the agreement comes from the INDEPENDENT pre-debate stances (no
  conformity/adversarial-persuasion bias) instead of the debate transcript.
- **G4 sentiment decay/velocity** (`strategies/sentiment.py`) - recency
  half-life weight, credibility factors, surprise z-score vs 30d baseline.
- **G5 threshold gate** (`scripts/evaluate_config_gate.py`) - walk-forward +
  PBO before tuning any new default (`enable_threshold_gate`).
- **B2 cross-sectional pipeline** (`pipeline.py`) - screens the universe
  (positional/file tickers or moomoo's top-losers/heat-proxy movers) through
  the value-screener engine, ranks by the EY+momentum+52w composite, picks
  top-N, and runs them through the batch runner (moomoo-first) — one command
  to `reports/pipeline_<ts>.md` + per-symbol report folders with TOCs.
- **A-series analyst tools (moomoo, optional)** - `get_institution_holdings`
  (13F-style institutional % + period change), `get_earnings_surprise_history`
  (EPS actual vs estimate per print + day reaction + implied move, with
  NaN-safe rendering), and `get_expected_move` (option-implied 1σ move at the
  next earnings + price band) — wired to the market and fundamentals analysts.
- **B1 scheduled-catalyst overlay** (`tradingagents/strategies/catalyst.py`) -
  deterministic catalyst sizing (the Phase-4 PEAD wiring). `enable_events` is
  **on by default**; the graph folds earnings (next print date + last surprise side +
  market-implied move / IV crush), HIGH-importance economic events (CPI, FOMC,
  payrolls, ...), and Fed-watch meetings into a `0..1` position scale and a
  verdict (`earnings-window` / `earnings-hard-block` / `macro-catalyst` /
  `fed-catalyst` / `no-imminent-catalyst`). The scale multiplies the overlay's
  `position_scale` and caps the G1 contract (`catalyst_scale`, included in its
  reason string); the guarded fetch returns None (neutral) when OpenD is
  unavailable, and the rule never scales **up** beyond the base - it is
  pre-event de-risking. With `catalyst_hard_block_days > 0`, an earnings print
  inside that window makes the risk governor **REJECT** new risk outright
  (the framework's "never initiate" rule).
  Tuning keys: `catalyst_window_days`, `catalyst_baseline_move`,
  `catalyst_macro_window_days`/`_scale`, `catalyst_fed_window_days`/`_scale`,
  `catalyst_miss_scale`, `catalyst_scale_floor`, `catalyst_hard_block_days` (0 = off).

Regression status: full suite passes (1153 passed / 2 skipped / 56 subtests).


</td></tr>
</table>

## Research



Researched trading methods implemented as pure, offline-testable modules under
`tradingagents/strategies/` (plan: [`Strategies/enhancement_plan.md`](Strategies/enhancement_plan.md)).
All are **config-gated and off by default** (`default_config.py`); enable per phase
only after validating in the evaluation harness:

- **P0 eval** `evaluate.py` - cost-adjusted metrics, deflated Sharpe (multi-trial
  penalty), walk-forward splits, backtest-overfit flag, drawdown/CAGR.
- **P1 regime** `regime.py` - realized-vol percentile, 200-SMA trend, choppiness,
  optional 2-3 state HMM label (hmmlearn); `enable_regime`.
- **P2 sizing** `size.py` - quarter-Kelly, smoothed volatility targeting, ATR
  stops, CVaR budget; `position_sizing` (`kelly|vol_target|flat`), `target_vol`.
- **P3 factors** `factors.py` - 12-1m momentum, 52-week-high distance, vol-adjusted
  momentum and a cross-sectional composite rank folding the value screens.
- **P4 events** `events.py` - earnings surprise, post-earnings-drift side, and
  catalyst-risk multipliers; **B1 wiring** in `catalyst.py` folds earnings /
  macro / Fed-watch into a position scale + verdict applied by the graph when
  `enable_events` is on (see Decision hardening).
- **P5 reflection** `reflection.py` - JSON-lines post-trade ledger, decayed
  analyst hit-rates, critique hints, ticker recall; `enable_reflection`.
- **Value-style hardening (V1-V5)** - `strategies/normalized.py` (5y
  median-margin normalized EBIT, historical percentiles, Sloan accruals,
  and a LOW/MED/HIGH trap verdict surfaced as the watchlist **Trap** column),
  `strategies/portfolio.py` (hard per-name/sector caps, residual cash),
  `strategies/exits.py` (stop-to-breakeven, ATR targets, rebalance cadence),
  `strategies/debate_context.py` (computed context snippets for the LLM debate).
  V2 wires value+momentum composite ranking into the screener
  R0-R4: deterministic **RiskGovernor** gate (PASS/WARN/REJECT), stress/shock
  scenarios and CVaR book risk (`strategies/book_risk.py`), escalation via
  `risk_halt`, and a `risk_audit.jsonl` trail (`scripts/risk_report.py`).
  Plan: `Strategies/risk_management_plan.md`.
  (`--rank composite` / `enable_composite_rank`), alloc block via
  `--alloc`, contract exits via `enable_exits`.
  Plan: `Strategies/value_style_gap_plan.md`.
- **P7 order flow (L1-L4)** - `tradingagents/strategies/orderflow.py` turns moomoo
  capital-flow buckets (XL/L/M/S, in/out) into deterministic signals:
  `distribution_score`, divergence (distribution-into-strength / silent-accumulation),
  exhaustion, bucket alignment. Wired as: tool output enrichment (`**Flow Signal**`),
  sizing fold into the strategy overlay (`enable_orderflow`; flow-scaled even while
  `enable_orderflow` is off, the raw tool stays available), state/graph stamp, and
  `scripts/orderflow_evaluate.py` for ledger-based evaluation (win-rate, mean alpha). - sentiment velocity, mention spikes,
  N-seed consensus (majority/blend); `enable_sentiment`, `consensus_seeds`.

- **M1-M5 momentum day-trading** (Warrior Trading 5-step playbook, spec:
  `Strategies/momentum_day_trading.md`) - `tradingagents/strategies/momentum.py`
  + `tradingagents/strategies/journal.py`, analysis-only (no execution):
  - **M1 stock selection** (`pillars`) - RVOL vs 50-day avg volume, total
    volume, open-gap vs prior close, $2-$20 price band, float < 20M shares.
    Each pillar is True (pass) / False (measured fail) / None (no data) -
    missing data never fails a scan and the screener/tool gate on *known*
    failures only. The float pillar is fed by `dataflows/float_shares.py`
    (FMP company profile, guarded yfinance fallback).
  - **M2 entry pattern** (`first_pullback`) - initial surge, pullback that
    retraces <= 50%, holds the 9-EMA and VWAP, trigger = first new-high candle
    above the pullback high, R/R >= 2 with a hard stop at the pullback low;
    rulebook extras when opens are available: light-red/heavy-green volume
    (`volume_ok`) and no prominent topping tails (`tail_ok`).
  - **M3 execution** (`psych_level`) - next whole/half-dollar level for
    psychological support/resistance.
  - **M4 session gates** (`session_flags` + `past_optimal_window`) - 50%
    peak give-back, max daily loss, ~10:00 ET window cutoff, missing-setups
    flag, folded into a single `walk_away` verdict.
  - **M5 journal & analytics** (`strategies/journal.py`) - JSON-lines paper
    ledger (`record_momentum_trade`, `momentum_stats`, `format_summary`):
    win/loss rate, avg R, per-pillar pass rates, FOMO / session-flag counts.
  - **Intraday confirmation** (`intraday_pullback`) - same pattern on 1m/5m
    bars with a session-VWAP hold (bar `vw` preferred, else typical price).
  Wired: Market Analyst tool `get_momentum_scan` (daily pillars + pullback +
  intraday block), screener `--scan momentum` with `--enable-float`
  low-float enrichment and `--journal PATH` (records candidates, prints
  ledger stats at the end). Live-only enrichment toggles:
  `TRADINGAGENTS_MOMENTUM_OFFLINE=1` and `TRADINGAGENTS_MOMENTUM_NO_INTRADAY=1`.

- **Techno-fundamental swing (S1-S3, spec: `Strategies/framework.md`)** -
  `tradingagents/strategies/swing.py` + `tradingagents/strategies/relative_strength.py`,
  analysis-only, wired as the screener `--scan swing` mode:
  - **S1 trend architecture** - price above a *rising* SMA50/SMA200 with the
    20-day EMA stacked above the SMA50 (`trend_architecture`).
  - **S2 relative strength** - RS line vs `benchmark_ticker` (default SPY) in
    an established 63-day uptrend (`relative_strength_report`): `leading` /
    `uptrend` pass, `lagging` / `diverging` (price new-high without RS
    backing) fail, unknown benchmark never blocks.
  - **S3 pullback setup** (`pullback_setup`) - low trades into the 20-day EMA
    while the close holds it on declining volume (accumulation).
  - **S4 RSI discipline** (`rsi_band`) - RSI 45-70 operating band or 40-50
    reset zone; below 40 invalidates.
  - **S5 stops & targets** (`swing_low_stop`, `targets_rr`, `scaleout_plan`,
    `trail_ema`) - 1-ATR stop below the swing low, 2R/3R targets, 50% T1
    scale-out to break-even, 20-day-EMA trail.
  - **S6 PEAD entry** (`events.py`) - post-earnings 2.5x-volume gap ->
    opening-range consolidation -> break of consolidation high
    (`post_earnings_play`).
  Wired: `--scan swing` gates on the stack + RS + pullback and prints
  `ScanC`/`RS`/`Stp`/`T2` columns (mode docs: `Strategies/scan.md`).

- **Volatility Contraction Pattern (`vcp_setup`, framework Phase 3)** -
  successively shallower pullbacks off a base high on fading volume (e.g.
  15% -> 8% -> 3%): strict pivot troughs, last-3 depths must contract (10%
  noise tolerance), deepest pullback within 30% of the base, volume across
  troughs must not expand (absent volume never fails). Wired as the screener
  `--scan vcp` mode with `VCP`/`Brk` columns; `swing_report` carries the VCP
  block as an additional signal.

- **Graph wiring** (`enable_strategy_overlays`, `enable_reflection`): the graph
  attaches regime/sizing/momentum overlays to the final state and records
  realized outcomes to `strategy_ledger.jsonl` (**enabled by default**;
  disable via `enable_strategy_overlays: false` / `enable_reflection: false`;
  both are also settable through `.env` (see below).

Regression status: full suite passes (1153 passed / 2 skipped / 56 subtests);
smoke imports of graph/dataflow/agent/strategy modules green.

## Contributing

Contributions are welcome: bug fixes, documentation, and feature ideas; past contributions are credited per release in [`CHANGELOG.md`](CHANGELOG.md).

## Citation

Please reference our work if you find *TradingAgents* provides you with some help :)

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
