# Deep Study: OpenBB → TradingAgents + trading_web Enhancements

**Status:** design / research (no code yet).
**Source study:** shallow clone of
[`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) read in this
session (openbb_platform core + extensions + providers, desktop/, cli/, mcp_server),
mapped onto the fork's deterministic `strategies/*`, the `dataflows/` vendor layer,
and the `trading_web` FastAPI + React SPA.

Companion research-to-design doc: `docs/design_quantlib_lean_enhancements.md`
(measurement/operational rigor). OpenBB's unique lesson is **architecture &
product surfaces**: a typed provider abstraction, a self-describing REST/CLI/MCP
surface, and a desktop/UI that manages credentials/backends — plus a deeper
statistical/screener toolkit.

Nothing here is committed yet. Each item is concrete, no-fabrication
(`float | None` / typed envelope), and slots into the existing seams.

---

## 0. What OpenBB is (and is not)

- **Not** an LLM system or a source of alpha. OpenBB is a *data-access +
  analytics platform*: ~30 providers normalized behind one typed API, a
  quantitative/econometrics/technical extension toolkit, and a Tauri-desktop +
  CLI + REST + **MCP** surface that all derive from a single Router catalog.
- Its three transferable lessons for this fork:
  1. **Typed, machine-readable envelopes** (`OBBject` + `error_kind`) instead of
     ad-hoc string sentinels.
  2. **A single source-of-truth command catalog** (Router → SDK/REST/CLI/MCP)
     so UIs and jobs derive, not hardcode.
  3. **A product surface** (credential manager, watchlist, charting, data grid,
     workflow presets, MCP) that a thin passthrough web app lacks.

---

## 1. Platform-core lessons → `tradingagents/dataflows/`

Verified against source (`openbb_core` provider/abstract/*, app/model/*,
app/router.py, provider/query_executor.py, extensions/platform_api/main.py).

### P1. Typed `VendorResult` envelope + `to_llm()`/`to_df()` ⭐ quick win
- **Source:** `openbb_core/provider/abstract/data.py` (Data, extra='allow') +
  `app/model/obbject.py` (OBBject: `{results, provider, warnings[], extra}`,
  `to_df()`/`to_dict()`/`to_llm()`).
- **What:** every command returns a typed result carrying **provenance** (which
  provider), a **warnings channel**, and per-format converters.
- **Gap:** the fork's vendor layer returns flat `get_*` **strings** with sentinel
  prefixes (`NO_DATA_AVAILABLE`) that every strategy and reporter re-parses
  (`reporting._looks_truncated`, `_collapse_repeated_tables`). No provenance, no
  warnings, no shared converter.
- **Signature:**
  ```python
  # tradingagents/dataflows/schema.py
  class VendorResult(BaseModel):
      results: Any | None
      provider: str | None
      warnings: list[VendorWarning]
      extra: dict
      def to_df(...); to_dict(orient); to_llm() -> str  # records JSON, iso dates
  # route_to_vendor(method, ...) -> VendorResult (not str); output_type='llm'|'df'
  ```

### P2. Provider registry w/ coverage + required-credentials map ⭐ quick win
- **Source:** `openbb_core/provider/query_executor.py` + `app/provider_interface.py`
  (CommandMap/provider_coverage; `QueryExecutor.filter_credentials`).
- **What:** machine-queryable *which vendors serve method X and which need which
  key*, with pre-fetch credential gating.
- **Gap:** the fork hardcodes `VENDOR_METHODS` + inline per-vendor key checks; no
  way to auto-tune `data_vendors` from available keys or skip a missing-key vendor
  before the fetch (only `VendorNotConfiguredError` at fetch time).
- **Signature:**
  ```python
  # tradingagents/dataflows/registry.py
  class Registry: providers; get_fetcher(provider, model);
      required_credentials(model) -> set[str]; coverage(model) -> list[str]
  # route_to_vendor: registry.filter_credentials(creds, provider, require) BEFORE extract
  ```

### P3. Typed REST endpoint + machine-readable `error_kind` ⭐ quick win (web)
- **Source:** `openbb_platform/extensions/platform_api/main.py`:
  deterministic operation_id, response_model from return annotation, and
  `OpenBBErrorResponse{detail, error_kind}` on every 400/500/502.
- **Gap:** `trading_web` `POST /api/raw` shells a whitelisted string command via
  subprocess and returns a str blob; the SPA can only string-match errors. The
  internal `VendorError` taxonomy dies at the web boundary.
- **Signature:**
  ```python
  # trading_web/backend/main.py
  @app.post("/api/data/{method}") -> VendorDataRequest(symbol, provider|None, params)
      -> VendorResult {ok, data, error_kind}
  # frontend toasts/jobs branch on error_kind (NoMarketDataError|VendorRateLimitError|...)
  ```

### P4. `AnnotatedResult` metadata → "Sources" lineage block
- **Source:** `openbb_core/provider/abstract/annotated_result.py`
  (`{result, metadata}`), stashed into `OBBject.extra['results_metadata']`.
- **Gap:** the fork degrades to sentinels silently; news/analyst reports carry no
  per-fact source or fetched-at. Metadata gives cites for the no-fabrication rule.
- **Signature:** `VendorResult.extra['results_metadata'] = {vendor, fetched_at,
  url, rows}`; `strategy_quality_report`/report render a "Sources" block.

### P5. Per-provider param filtering w/ warnings
- **Source:** `app/provider_interface.py Query.filter_extra_params` +
  `abstract/query_params.py __json_schema_extra__`.
- **Gap:** the same kwargs go to every vendor; each `get_*` silently ignores
  extras (a silent misconfig). Add a filter step that surfaces unsupported args as
  warnings (fits the P1 warnings list) and enables per-vendor arg schemas (e.g.
  date formats av vs moomoo).

### P6. Credential manager kept server-side
- **Source:** `openbb_core/app/model/credentials.py` + `service/user_service.py`
  (SecretStr, env-merge, `USER_SETTINGS_ALLOWED_FIELD_SET`, redacted dump).
- **Gap:** the fork's API keys are inline per-vendor reading config/env; no unified
  store, no "which keys are missing" answer, no redaction guarantee; `trading_web`
  `PUT /api/config` is a no-op. Add a `trading_web` `Credentials` store + a
  `/api/credentials/required` endpoint (`{provider: [missing_keys]}`) so the SPA
  can show/enter keys and `route_to_vendor` can pre-gate.

---

## 2. Quantitative / econometrics / technical lessons → `strategies/`

Verified against `extensions/quantitative`, `extensions/econometrics`,
`extensions/technical`. Already-covered (Sharpe/sortino/PSR/rolling/underwater/
VaR/CVaR/skew/kurt/RSI/ADX/Bollinger/etc) deliberately declined.

### Q1. Normality + unit-root hypothesis tests ⭐ quick win
- **Source:** `openbb_quantitative.quantitative_router.normality` +
  `unitroot_test` / `econometrics.unit_root`.
- **Gap:** the fork has numeric skew/kurt but no distributional p-values
  ("is the return Gaussian?") or stationarity check (gates vol/momentum validity).
- **Signature:**
  ```python
  def normality(returns: list[float]) -> dict   # {jarque_bera, shapiro_wilk, kolmogorov_smirnov, ...: {statistic,p_value}, normal: bool}; scipy; None <4obs
  def unit_root(series: list[float], regression: str = "c") -> dict  # {adf:{stat,p,nlags,nobs}, kpss:{stat,p,nlags}, stationary: bool}; statsmodels
  ```

### Q2. CAPM decomposition, OLS factor regression + VIF ⭐ quick win
- **Source:** `openbb_quantitative.quantitative_router.capm` +
  `econometrics.ols_regression` / `variance_inflation_factor`.
- **Gap:** `evaluate.beta/alpha` are hand-rolled without significance; no
  systematic-vs-idiosyncratic split, no factor attribution or collinearity check.
- **Signature:**
  ```python
  def capm_decomposition(returns, market, periods=252) -> dict  # {beta, systematic_risk(R2), idiosyncratic_risk(1-R2)}; None <30
  def ols_factors(y, factors: dict[str,list]) -> dict          # {params, rsquared, fvalue, aic, pvalues, tvalues, bse, conf_int}
  def variance_inflation_factor(columns: dict[str,list]) -> dict  # {col: vif, high_>5}
  ```

### Q3. Omega ratio
- **Source:** `openbb_quantitative.performance.omega_ratio`.
- **Gap:** the fork has sortino/PSR but no parameter-free tail-weighted payoff
  asymmetry.
- **Signature:** `def omega(returns: list[float], threshold=0.0) -> float|None`
  (sum(max(r-t,0))/sum(max(t-r,0)); None on no positive mass).

### Q4. Robust correlation matrix + rank methods
- **Source:** `econometrics.correlation_matrix` (pearson/kendall/spearman).
- **Gap:** only pairwise `_pearson` + `mean_correlation`; no full matrix.
- **Signature:** `def correlation_matrix(returns_by_name, method='pearson') -> dict`
  (`{names, corr:{ni:{nj:r}}}`; None <2 aligned).

### Q5. Cointegration + Granger causality
- **Source:** `econometrics.cointegration` / `causality`.
- **Gap:** no pair mean-reversion or lead-lag test (single-name only today).
- **Signature:**
  ```python
  def cointegration_pair(x, y, maxlag=1) -> dict   # Engle-Granger + residual ADF stat/p
  def granger_causality(x, y, maxlag=3) -> dict    # lag-wise F/p
  ```

### Q6. Relative rotation (RRG quadrants) — flagship ⭐
- **Source:** `openbb_technical/relative_rotation.py`
  (`calculate_relative_strength_ratio`, `calculate_momentum`, `RelativeRotation`).
- **Gap:** the fork's `relative_strength.py` has an RS line/slope but no
  cross-sectional momentum×RS **quadrant** (leading/weakening/lagging/improving) —
  the classic rotation screen.
- **Signature:** `def relative_rotation(stock, benchmark, long=252, short=21) -> dict`
  (`{rs_ratio, rs_momentum, quadrant}`; None when benchmark < long+short).

### Q7. Clenow momentum (trend persistence × noise)
- **Source:** `openbb_technical` (`clenow`).
- **Gap:** `factors.momentum()` is a naive 12-1m; Clenow = exp(OLS log-slope ×
  periods) × R² — penalizes noise, upgrades `sector_rank`/rotation.
- **Signature:** `def clenow_momentum(closes, window=90, periods=252) -> float`
  (None < window/flat).

### Q8. Volatility cones (multi-horizon relative vol)
- **Source:** `openbb_technical` (`cones`).
- **Gap:** `regime.realized_vol/vol_percentile` is single-horizon; cones give
  realized-vol percentile bands across 5/10/21/63/126d.
- **Signature:** `def vol_cones(closes, windows=(5,10,21,63,126)) -> dict`
  (`{win:{current,p25,p50,p75}}` annualized).

---

## 3. Data-surface lessons → `dataflows/` new categories

Verified against `extensions/equity`, `derivatives`, `fixedincome`, `economy`,
`etf`. All providers noted are free/no-key on the machine's tiers (cboe, finviz,
yfinance, federal_reserve, sec), or already-entitled (fmp/eodhd keys held).

### D1. Options IV surface + market greeks (cboe, free) ⭐ quick win
- **Source:** `openbb_derivatives/options/options_router.py` `chains` + `surface`
  (market-quoted delta/gamma/theta/vega/rho, IV, OI, volume; IV surface by
  moneyness/DTE).
- **Gap:** the fork's `options_math.py` **derives** IV analytically (Black-76);
  analysts guesstimate the market's cross-strike/cross-expiry read.
  `options_math.black_vol_surface` + `credit_spread` need real market IVs.
- **Signature:** `interface.py` category `options_surface` /
  `get_options_surface(symbol, moneyness, dte_max)` -> rows of
  `{strike, dte, iv, delta, gamma, theta, vega, rho}`; route `cboe`; feed into
  `strategies/options_math.black_vol_surface`.

### D2. Real risk-free term structure (federal_reserve, free) ⭐ quick win
- **Source:** `openbb_fixedincome/rate/rate_router.py` `sofr`/`effr`/`sonia` +
  `openbb_fixedincome/government` `treasury_rates`/`yield_curve`/`svensson_yield_curve`.
- **Gap:** `rate_utils.discount_factor` takes a scalar; `dcf.py`/`options_math`
  discount at a constant; `fred.py` only has DGS2/10/30.
- **Signature:**
  ```python
  interface.py category 'risk_free_curve' / 'get_sofr_curve()' + 'get_treasury_curve()'
  # overload rate_utils.discount_factor(rate|curve, t) for dcf term-structure discounting
  ```

### D3. Equity screener + movers (finviz/yfinance, free) ⭐
- **Source:** `openbb_equity/discovery` `screener` (finviz/yfinance/nasdaq) +
  `gainers`/`losers`/`active`.
- **Gap:** the fork has **no** screener method — only `eodhd exchange_symbols` (a
  flat list); `value_screener.py`/`capital_income_screener.py` iterate symbol lists
  manually.
- **Signature:** `interface.py` category `equity_screener` /
  `screen_equities(market, limit, filters)` -> `[{symbol, price, pe, eps, beta,
  mkt_cap}]` (finviz/yfinance); `get_market_movers(kind)` (yfinance discovery).

### D4. Analyst consensus + price-target (finviz/fmp)
- **Source:** `openbb_equity/estimates` `consensus`/`price_target`.
- **Gap:** the fork has `get_analyst_ratings` (bucket) but no forward EPS/EBITDA/
  sales/PE consensus or aggregate price-target; `fundamentals_analyst`/`dcf.py`
  guesstimate forward growth.
- **Signature:** `get_consensus_estimates(symbol)` + `get_price_target_consensus(symbol)`
  -> feed `dcf.py` forward inputs + fundamentals analyst.

### D5. Equity calendars: dividend / splits / IPO (nasdaq/fmp)
- **Source:** `openbb_equity/calendar` `dividend`/`splits`/`ipo`.
- **Gap:** `corporate_actions` (moomoo) is ad-hoc; no structured dividend/split/
  IPO calendar. Calendar-driven catalysts feed `events.py`/`catalyst.py`/`pre_market`.
- **Signature:** `get_dividend_calendar`, `get_ipo_calendar`, `get_split_calendar`.

### D6. Ownership / float / SEC 13F (yfinance/sec, free)
- **Source:** `openbb_equity/ownership` `share_statistics`/`major_holders`/
  `form_13f` (sec=free).
- **Gap:** `liquidity_risk.py`/`risk_governor.py` estimate float; a concrete
  shares-outstanding/float/holder surface removes the guess.
- **Signature:** `get_share_statistics(symbol)` + `get_form_13f(symbol)` -> feed
  `liquidity_risk.py`.

(Lower priority / optional: ETF sector/weights via fmp, futures curves via
yfinance, FX/crypto via ecb — skip unless the pipeline actually trades those.)

---

## 4. UI / product-surface lessons → `trading_web`

Verified against `desktop/` (Tauri 2 + React, backend/credential manager),
`obbject_extensions/charting` (Plotly + PyWry + query-table grid),
`cli/` (auto-derived TUI, session/registry, `.openbb` routine files),
`extensions/mcp_server` (FastMCP auto-wrap of the FastAPI router).

### U1. Watchlist persistence ⭐ quick win
- **Gap confirmed:** trading_web has no persisted ticker set (SQLite = users +
  jobs only).
- **Add:** `watchlist(username, ticker, added_at, note)` + `GET/POST/DELETE
  /api/watchlist` (auth+CSRF) + `Watchlist.jsx` (add/remove, queue-all into
  Batch/Screener/PreMarket).

### U2. Interactive data grid for signal tables ⭐ quick win
- **Gap:** the SPA renders JSON as plain `<table>`.
- **Add:** `SignalTable.jsx` (sort/filter/pin/number-format) fed by the existing
  `GET /api/summaries/{name}` rows; replace `<table>` in Dashboard/Jobs/Screener.
  Zero backend change.

### U3. Chart types (OHLCV + correlation + drawdown) ⭐ (visual showcase)
- **Gap:** zero charts.
- **Add:** `TickerChart.jsx` (Plotly candle + volume + drawdown from
  `strategies.evaluate` rolling/underwater) reusing `POST /api/history` — no new
  backend; then correlation + SectorRank.

### U4. Workflow / run presets
- **Source:** `cli/assets/routines/*.openbb`.
- **Add:** `presets(username, name, capability, args_json)` + `GET/PUT/DELETE
  /api/presets`; "Save preset" on every job form + picker back-fill.

### U5. Credential manager (server-side safe)
- **Source:** `desktop` `api-keys.tsx`.
- **Add:** `api-keys` screen (moomoo/fmp/eodhd/alpaca/fred/massive), masked-on-
  read, admin-only, audit-logged; `GET/PUT /api/credentials` + a
  `/api/credentials/required` from P6.

### U6. MCP surface for the strategies (aligns with the P-series P2/P3)
- **Source:** `extensions/mcp_server` (FastMCP auto-wrap of the FastAPI router →
  tools + category_index + widgets).
- **Add:** a FastMCP server that wraps `dataflows/interface.route_to_vendor` +
  `analysis_tools`/`strategies` as MCP tools, served from `backend/main.py` or a
  sibling `mcp_server/` — the LangGraph/agent-facing analogue of the REST
  self-describing catalog.

### U7. REST client / run-history viewer + job timeline
- **Source:** `cli/obbject_registry` + desktop backend-logs.
- **Add:** a `GET /api/jobs` timeline UI (args/status/result_path) with rerun —
  reuses the existing jobs table.

(Theme toggle U8, extension/widget registry U9: enablers for U1–U5.)

---

## 5. Recommended phases (highest ROI first, smallest first)

### Phase 1 — Strategy depth (pure; no new data)
- Q1 `normality` + `unit_root`; Q2 `capm_decomposition` + `variance_inflation_factor`;
  Q3 `omega`; Q4 `correlation_matrix`; Q6 `relative_rotation`; Q7 `clenow_momentum`;
  Q8 `vol_cones`; Q5 `cointegration_pair`/`granger_causality`.
- Each a pure `float | None` calculator under `strategies/` (or a new
  `statistical.py`), hermetic-tested, wrapped as analyst `@tool`s.

### Phase 2 — Typed dataflow layer (architecture)
- P1 `VendorResult` envelope + `to_llm()`/`to_df()`;
  P5 per-provider param filtering; P4 metadata "Sources" block.
- P2 provider registry + required-credentials pre-gate.

### Phase 3 — Data surfaces (new categories, free tiers)
- D1 options surface (cboe), D2 risk-free curve (federal_reserve),
  D3 screener+movers (finviz/yfinance), then D4–D6 (estimates/calendars/ownership).

### Phase 4 — Web product (trading_web)
- U1 watchlist, U2 signal grid, U3 charts (quick wins first), then
  U4 presets, U5 credential manager, U6 MCP, U7 job timeline.
- P3 typed REST + `error_kind`; P6 credential endpoints.

---

## 6. Non-goals / risks

- **No new providers just to look busy** — prefer free/no-key (cboe, finviz,
  yfinance, federal_reserve, sec) and already-entitled (fmp/eodhd) surfaces;
  skip ETF/futures/FX/crypto unless the pipeline actually trades them.
- **No alpha claims** — every item is a computed signal or a UI/architecture
  surface; none overrides the LLM decision unless opt-in (advisory-first).
- **No-fabrication preserved** — all `float | None` / typed envelopes / explicit
  `error_kind`; a missing vendor degrades to an explicit "unavailable" + warning,
  never a fabricated value.
- **No breaking refactor of the string-based vendor layer in one step** — P1–P2
  land as an additive `VendorResult` that `route_to_vendor` can return alongside
  the current string until all callees migrate (clean cutover per item).
- **Web changes go through the existing auth/CSRF/audit/redact plumbing** — every
  new route uses it; credentials masked-on-read, admin-only, audit-logged.
- **Scope control** — U1/U2 are pure DB + component (exercise the auth path);
  U3 is a visual showcase; the rest are phased follow-ups.

---

## 7. Quick-wins verdict

1. **Strategy depth (Phase 1):** normality + unit-root (Q1), CAPM/VIF (Q2),
   relative-rotation + Clenow (Q6/Q7) — pure scipy/statsmodels, no data deps, and
   they give the LLM p-valued distributional/stationarity/rotation claims it
   currently asserts without tests.
2. **Options + rate data surfaces (D1/D2):** cboe options surface feeds
   `options_math.black_vol_surface`; federal_reserve curve fixes constant-rate
   discounting in `dcf`/`options_math`. Both free, high-value.
3. **Web watchlist + signal grid (U1/U2):** a DB table + thin routes (under the
   existing auth/CSRF/audit path) and an interactive grid over existing
   `/api/summaries` — the smallest, highest-leverage UI gap in `trading_web`.
