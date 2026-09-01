# Session Handoff — TradingAgents (2026-09-01, continuation)

## 1. Task Objective & Scope
- **Goal:** Expand the fork with the quant-strategy gap from `Strategies/cookbook.md` (5 recipes + common framework), bind the new calculators to the decision agents as tools, and port two data-safety/debate-quality fixes from the parent repo (`TauricResearch/TradingAgents`) — all without merging.
- **Sub-task in progress:** **None — all phases complete and pushed.** Last completed work: parent-repo ports #1 (look-ahead window) and #2 (debate opening markers). Open optional follow-ups: (a) memory holding-window settle + FRED vintage pin from the parent; (b) parent hardening of `structured.py`/`openai_client.py` (schema-only no tool priming, Responses-API gating) — assessed but not yet ported.

## 2. File Manifest & Modifications
**Created:**
- `tradingagents/strategies/cross_section.py` — winsorize / cross_sectional_z / centered_rank / quantile_split / residualize_returns / neutralize_book (numpy lstsq row-space projection: dollar+beta+sector neutral, gross-renormalized) / no_trade_band.
- `tradingagents/dataflows/date_window.py` — shared half-open UTC window `[start, end+1d)`; `in_window`/`to_utc`; undated items kept only when window reaches present.
- `tests/test_cookbook_gaps.py` (27 tests), `tests/test_parent_ports.py` (12 tests).

**Modified:**
- `tradingagents/strategies/{momentum,factors,evaluate,options_math,statistical,book_risk,portfolio_optimizer,credit_spread,rate_utils,market_session}.py` — new calculators (below).
- `tradingagents/agents/utils/analysis_tools.py` — new tools `get_ts_momentum_weights`, `get_pair_trade_signal`, `get_event_pnl_response`, `get_book_depth_read`, `get_merton_distance`; rewrote `get_variance_premium` (now real model-free VRP via machine chain `_machine_chain_vrp`); extended `get_tail_risk` (CDaR/DVaR), `get_risk_parity_alloc` (max-diversification row). Note: `statsmodels` unused; pure NumPy everywhere.
- `tradingagents/agents/utils/agent_utils.py` — imports/`__all__` for new tools; NEW `opponent_argument_or_opening(text, opponent)`.
- `tradingagents/agents/analysts/market_analyst.py` — 6 new tools bound + prompt lines.
- `tradingagents/graph/trading_graph.py` — market ToolNode += new tools.
- `tradingagents/agents/utils/risk_tool_loop.py` — `get_merton_distance` in RISK_DEBATOR_TOOLS.
- `tradingagents/agents/researchers/{bull,bear}_researcher.py` + `risk_mgmt/{aggressive,conservative,neutral}_debator.py` — opening-marker interpolation (#1176).
- `tradingagents/dataflows/{stocktwits,reddit}.py` — `_within_window` + `start_date`/`end_date` params (look-ahead safe, #1220). `yfinance_news.py` migrated to `date_window.in_window`.
- `tradingagents/agents/analysts/sentiment_analyst.py` — threads run window into both social fetchers.
- `scripts/pre_market_review.py` — thin-book directive += optional depth (microprice/OBI) line.
- `tests/test_news_lookahead.py` — migrated to shared `date_window.in_window`.
- Docs: README, CHANGELOG.md, docs/AGENT_ONBOARDING.md, docs/api_reference.md `§6.4`, docs/developer/04-strategies.md, Strategies/index.md (cookbook row 21).
- trading_web (separate repo `../TradingNew/trading_web`, own commit `db3217d`-style sync untracked here): `backend/capabilities.py` += `variance_premium`, `ts_momentum_weights` (+ `_ohlcv_closes` helper); `frontend/src/App.jsx` TOOL_OPTS += 2 entries.

**Key changes (calculators):**
- `momentum.py::ts_momentum_weights` — MOP sign(trailing log ret)/EWMA-vol, target-vol normalized, gross leverage cap; `_log_returns`.
- `factors.py::z_composite_alpha`, `momentum_multihorizon` (1/3/6/12m ensemble).
- `evaluate.py::turnover`, `turnover_cost`, `gross_exposure`, `net_exposure`, `rolling_sharpe`, `regime_split_performance`.
- `options_math.py::black76` += rho/vanna/vomma/charm; `bsm_equity_surface`; `greek_pnl_response` (ΔdS+½ΓdS²+νdσ+Θdt); `model_free_implied_variance` (Cboe/VIX form with F/K₀ term).
- `statistical.py::spread_zscore` (rolling beta hedge + z), `pair_signal` (entry |z|≥2 / exit ≤0.5 / stop ≥3, cointegration+half-life), `pair_quantities` (dollar-neutral G/2 legs), `ecm_loading` (VECM γ).
- `book_risk.py::cdar` (Chekhlov). `portfolio_optimizer.py::max_diversification_weights` (Σ⁻¹σ, non-neg + renormalize). `credit_spread.py::merton_distance_to_default` (fixed-point V/σV; DtD=d2, PD=N(−d2)). `rate_utils.py::forward_rate`. `market_session.py::book_depth_read` (microprice + OBI).
- `date_window.py`: `in_window(None, start, end)` → kept ONLY when `end ≥ now−1d` (backtests exclude undated).

**Untouched Dependencies (read-only):** `evaluate.py` tail (pbo/calmar etc. existing), `statistical.py` existing cointegration/granger, `options_math` `black_vol_surface`/`variance_swap_strike`, `_ohlcv` cache + `_daily_returns` in analysis_tools, `default_config.py`, `agents/schemas.py`, `graph/setup.py`/`conditional_logic.py`, `llm_clients/*`, `dataflows/interface.py` chains, `portfolio_optimizer._covariance_matrix`/`_invert` (single-name Gaussian inverse kept).

## 3. Current State & Validation
**Working/Passing:**
- `tests/test_cookbook_gaps.py` **27 passed**; `tests/test_parent_ports.py` **12 passed**; full suite **2114 passed / 2 skipped** (skips: bedrock extra, live DeepSeek key — baseline), `ruff check` clean repo-wide (`tradingagents/ scripts/ tests/ cli/`).
- Key identity checks passing: put-call parity + BSM↔Black-76 equivalence; neutralize_book constraint residuals ≤1e-5 (6dp rounding); MDP ≠ min-var; Merton DtD ≈ d2; CDaR=0.97 on monotone 100→1 decline; stocktwits/reddit window trim confirms post-date items excluded, undated excluded in backtest.
- Pushed: `94944d4` (cookbook gap) and `c97ee59` (parent ports) both on `origin/main`.

**Failing/Incomplete:**
- None known. Parent-repo diffs remaining (not yet ported): memory `holding_days` settle gating; FRED vintage pin; `structured.py` "no tool priming in schema-only agents"; `openai_client` Responses-API-only-native gating; `test_ohlcv_latest_bar` NaN-close-latest-bar-raise; `Retry-After` handling parity is already present in local `reddit.py` (verify parity vs parent `_jitter` if touching).
- Not wired to trading_web (needs structured args): pair-signal / event-pnl / depth-read / merton tools (graph-bound only; documented in api_reference §6.4).

**Active Errors/Stack Traces:** None. Prior session blockers resolved: json_object 400 "json" token; empty dimension_scores; ragged enums/booleans; degraded-turn crashes; CLI moomoo shutdown-hang; neutralize_book pure-python matrix-inverse bugs (replaced with numpy lstsq — do NOT reintroduce Gaussian `_invert` for constraint projection).

## 4. Technical Constraints & Decisions
- `py -3.12` only (bare `python` = hermes venv, no pytest). Windows heredocs corrupt → `write`/`edit` tools; existing files CRLF (match `\r?\n`); auto-fix import sorting with `ruff check --fix` but keep formatting scoped.
- No-fabrication: every calculator returns `float | None` / explicit "unavailable"; min-obs guards everywhere.
- Advisory-first: new tools never gate; hard gates stay in risk governor overlay.
- Pure NumPy/scipy only — NO new deps (statsmodels/plotly explicitly avoided); `sector_neutral_z`/`residualize_*` in `sentiment_research.py` remain the reference for cross-sectional helpers (don't duplicate).
- Rounding convention: financial numbers 4-6 dp; `neutralize_book` returns rounded-to-6dp weights → neutrality test tolerance `5e-5`; vol percentiles/ratios formatted `%`.
- Working rules: compute-as-tools; docs/README/CHANGELOG true per change; every test file carries `pytestmark = pytest.mark.timeout(N)` (180s default); full suite ~5-6 min (only run whole `tests/` after a change); commit+push `origin/main` with Conventional Commits; `git add -A` will sweep stray `_probe*.ps1`/`Direction.md` (user files) — stage explicitly; never commit `.env` (real keys inside, gitignored).
- Web mirror contract: repo capability adds must also land in `../TradingNew/trading_web` `backend/capabilities.py` job allowlist + `frontend/src/App.jsx` TOOL_OPTS; verify `py -3.12 -m py_compile` there.
- Parent repo `TauricResearch/TradingAgents` has release branches (v0.2/v0.4) + ~1000 PRs; fork diverged ~302 files / 68k insertions — do NOT merge wholesale; cherry-pick only reviewed fixes (ports #1/#2 done; see "Failing/Incomplete" for remaining candidates).