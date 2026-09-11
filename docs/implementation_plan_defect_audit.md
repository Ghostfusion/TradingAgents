# TradingAgents — Defect Audit & Implementation Plan

Audit of the TradingAgents repository @ `e99f8fd` (branch `main`, working tree clean; 3441 tests pass, ruff clean apart from 3 nits).
Method: 14 read-only subsystem scouts (strategies ×3, dataflows ×3, graph, analysts, agents-utils ×2, decision team, reporting/config, tests ×2) + mechanical scans run by the main thread + **direct reproduction of every high-severity claim**.

Legend: **[V]** = reproduced by the main thread (evidence quoted below); **[S]** = scout-reported, evidence cited but not independently reproduced; **[D]** = dismissed as a false positive (listed in §6).

---

## 1. P0 — Broken surfaces (a claimed capability does not work)

| id | file:line | symptom (reproduced) | fix |
|---|---|---|---|
| P0-1 | `agents/utils/analysis_tools.py:192-194, 7247` | `_cfg_idx` carries a stray `@tool` (it is a private helper), so `get_regime_gate_read` calls a `StructuredTool` as a function → **every call returns** `regime gate read unavailable for AAPL: 'StructuredTool' object is not callable` (the A1 knife-guard gate is absent from all risk debates). | Delete the `@tool` on `_cfg_idx`. |
| P0-2 | `agents/utils/analysis_tools.py:1581-1587` | `get_etf_mechanics` calls `get_corporate_actions(t)` — a `StructuredTool` — inside `try/except Exception` → **Distributions is permanently `n/a`** (live: SPY renders `- Distributions: n/a`), and the failure is reported as "no data". | Call `route_to_vendor("get_corporate_actions", t)` (what the tool body does) and narrow the except. |
| P0-3 | `agents/overrides/action_condition_judge.py:18,67` | Imports `render_action_condition_verdict`, which does not exist in `schemas.py` → **`ImportError`** (verified by import); `scripts/action_report.py` swallows it as `judge unavailable: …`, so the action-condition judge can never run. | Add `render_action_condition_verdict` to `schemas.py` (mirror `render_pre_market_verdict`) or import from the real module. |
| P0-4 | `graph/trading_graph.py:_create_tool_nodes` vs `analysts/fundamentals_analyst.py:63-81` | The fundamentals analyst binds 12 ETF tools; **5 are absent from the fundamentals ToolNode** (`get_etf_valuation`, `get_etf_decline_driver`, `get_etf_relative_strength`, `get_etf_risk`, `get_etf_mechanics`). `_create_tool_nodes` contains **zero** `get_etf_*` entries; `.env` sets `TRADINGAGENTS_ENABLE_ETF_ENGINE`. LangGraph answers `Error: get_etf_valuation is not a valid tool` — the whole fund methodology is unobtainable on the ETF path. | Derive the ToolNode tool list from the analyst's bound list (see S1). |
| P0-5 | `agents/managers/portfolio_manager.py:258-263` | `risk_rows = [... for v in (risk_matrix_block and [{}] or [])]` is **always `[{}]`** → `stabilize_decision` never sees a high-severity row → the risk-cap guardrail (rule 1) is unreachable. | Build `risk_rows` from `rds['round_records'][*]['risk_factors']`. |
| P0-6 | `agents/utils/analysis_tools.py:144-155` | `_ohlcv` writes the **failure** dict into `_RUN_OHLCV_CACHE[key]` (the dict itself says `"retryable": True`) → one transient vendor error degrades every OHLCV tool for that ticker for the whole process. | Don't cache the exception result (short negative TTL or none). |
| P0-7 | `default_config.py:89,239` + `_coerce` | `TRADINGAGENTS_ENABLE_PIT_REGISTRY` / `..._PRE_MARKET_REVIEW` map to keys absent from `DEFAULT_CONFIG`, so `_coerce(value, None)` returns the **raw string**: `'false'` → truthy. Reproduced: both read `'false'` (str), `bool == True`; `batch.py:418` therefore runs the pre-market review the user disabled. | Add the two keys to `DEFAULT_CONFIG` (or reject unknown override targets at import). |
| P0-8 | `agents/utils/rating.py:100` + `memory.py:62`, `graph/signal_processing.py:33` | `parse_rating` defaults to `"Hold"`; an unavailable/degenerate decision has no rating → **`parse_rating("**Decision**: unavailable …") == 'Hold'`** (reproduced), so a failed decision is stored and acted on as a tradeable Hold. | Pass a non-tradeable default / detect the unavailable notice at both call sites. |
| P0-9 | `strategies/security_type.py:31-45` | `_FUND_ISSUER_RE` includes `JPMorgan|Goldman|Morgan Stanley|BlackRock|Schwab|Fidelity|BNY|Nuveen|PIMCO…` and `_FUND_NAME_RE` matches any name with `Trust|Index|Fund`. Reproduced: **JPM, GS, MS, BLK, SCHW, NTRS, STT all classify as `ETF`** (`fund issuer name: …`) → the fundamentals analyst swaps its entire toolset to the ETF one for operating companies (the inverse of the IGV failure this module exists to prevent). | Require a fund-specific token (issuer + wrapper word) and never match a bare issuer name; keep provider `quote_type` authoritative. |
| P0-10 | `dataflows/statement_parsing.py:37,45,100` | Alias tables mis-match (reproduced via `_match_row`): `revenue` ← `Operating Income` (even when a `Sales` row exists), `operating_income` ← `EBITDA` (`'ebit' in 'ebitda'`), `total_liabilities` ← `Total Liabilities And Equity`. Corrupts margins, `revenue_yoy`, Beneish SGI/DSMI, Altman X3/X4, net-net. | Reorder/guard the aliases (`sales` before `operating income`; drop bare `ebit`; exclude `and equity`). |
| P0-11 | `dataflows/interface.py` VENDOR_METHODS | Dead chain entries (signature vs call site, verified by inspecting both): **tiingo** in `get_fundamentals` (3 required vs 2 passed), `get_balance_sheet`/`get_cashflow`/`get_income_statement` (gets `"quarterly"` as `start_date`); **gdelt** in `get_global_news` (`get_news_gdelt(ticker, start, end)` called as `(curr_date, look_back_days, limit)`). Each raises inside the router's generic `except`, so the configured fallback silently does not exist. | Give each adapter the method's contract, or drop it from the chain + `default_config`. |
| P0-12 | `strategies/value_dip.py:614, 879` | `volume_dry_up`: `prior = volumes[-window-lookback-1 : -window-1]` is **5 bars, not 20** (reproduced: slice `[-26:-21]` → 5 values) → the "20-day baseline" is a 5-bar baseline. `price_velocity_z`: the returns loop uses `range(1, window+1)` — the **oldest** bars of the series, not the trailing window (reproduced: wild-old/calm-recent series yields z≈0.0004, i.e. σ from the old bars). Both feed knife-guard verdicts. | Fix the slices (`[-window-lookback-1 : -lookback-1]`, `range(len(closes)-window, len(closes))`). |
| P0-13 | `agents/utils/analysis_tools.py:6831-6834` | `indicated_yield` returns a **fraction** (rendered `{iy:.2%}`) but is passed as `iy/100.0` to `macaulay_duration`/`modified_duration`/`bond_convexity`, whose contract is "annual yield (0.05 = 5%)" → yield 100× too small; modified duration/DV01/convexity wrong in the same direction. | Pass `iy` unchanged. |
| P0-14 | `agents/utils/report_verifier.py:414-415, 1149` | Verifier evasions (reproduced): `_TEMA_VAL` matches `10-EMA 54.66` / `10-EMA (graph 55.54)` but **not** `10-EMA = 54.66` / `10-EMA: 54.66` → the dual-value identity check silently skips the common shapes; `t1`/`t2` read the `3` of `3R` and the 2R price out of `2R/3R targets A / B`; the `"eps estimate"` pattern requires `eps actual` on the same line. | Allow a separator before the value; anchor the R-multiple reader; key the EPS-estimate pattern on the estimate token. |

## 2. P1 — Look-ahead, window and data-integrity defects

- **Vendors ignore the requested window** (look-ahead in backtests): `finnhub.get_global_news_finnhub` drops `curr_date/look_back_days/limit`; `finnhub.get_earnings_calendar_finnhub` queries a purely **backward** window so the "upcoming earnings date" can never be returned; `stockdata.get_stock_data_stockdata`/`get_news_stockdata` validate the dates then never send/filter them; `moomoo.get_news_moomoo` ignores both dates. Fix: thread the window through and filter with `date_window.in_window`. **[S]**
- `finnhub._window()` uses `datetime.now()` → historical runs see future insider data. **[S]**
- `stockstats_utils._clean_dataframe` runs `bfill()` **before** the `curr_date` filter → later rows fill earlier gaps (future leak). **[S]**
- `date_window.in_window` keeps undated items when the window ends within 24h → a prior-session backtest admits undated items. **[S]**
- **Rate-limit converted to no-data / entitlement**: `massive` wraps `get_ratios_massive`/`get_market_snapshot_massive`/`get_top_movers_massive` in `except Exception → _not_entitled(...)` (a 429/timeout becomes "upgrade your plan", which the router counts as served and caches) — 3 sites verified by reading; `stockdata`/`newsapi`/`benzinga`/`gdelt` classify the JSON body **before** the HTTP status, so an HTML 429 becomes `NoMarketDataError`. **[S] (massive sites [V])**
- `moomoo._format_financials` returns a placeholder string (not `NoMarketDataError`) and moomoo is **first** in `fundamental_data` (`moomoo,yfinance,tiingo,alpha_vantage`) → the chain stops on a moomoo miss. **[V for both halves]**
- `statement_parsing._parse_json_statements` keeps only `Sector` from the Alpha Vantage OVERVIEW dict → `market_cap`/`beta`/`shares` are never parsed when AV serves. **[S]**
- `agents/utils/market_position_tools._parse_statement_rows` substitutes **0.0** for unparseable cells → fabricated zeros enter sums/deltas. **[V]**
- `yfinance_options._nearest_expiry` falls back to `expiries[-1]` (**farthest**) when nothing clears the cutoff. **[S]**
- `market_data_validator.live_price_sanity`'s `OUTSIDE verified bar` branch is unreachable (containment already established) → a stale print is labelled INSIDE. **[S]**
- `finnhub.py:265` passes the message as `canonical=` instead of `detail=` → the typed absence loses its reason. **[S]**
- `analysis_tools` renders `None` risk metrics as hard zeros (`or 0`): `shortfall_prob=0.0%`, `jarque_bera_p=0.000`, `emp_var=0.0%` — "unmeasured" printed as "measured, benign". **[S]**
- `analysis_tools._dcf_beta` / `_dcf_cash_debt` substitute `1.0` / `0.0` and the DCF line labels the row "provider-derived" → an assumed beta is cited as measured. **[S]**
- `get_earnings_event_read` omits the GAAP-basis note that `get_earnings_surprise` appends → the news path cites an unreconciled surprise. **[S]**
- `y_finance` indicator fallbacks `print()` and return `""`, which the router treats as served and caches for 6h. **[S]**

## 3. P2 — Dead code, duplication and drift

- **Deprecated shim** `agents/analysts/social_media_analyst.py` (+ `create_social_media_analyst` alias in `sentiment_analyst.py:340`) — imported by nobody; repo policy is clean cutover, no shims. **[V]**
- `agents/utils/debate_roles.py:132-168` — `BULL_TOOLS/BEAR_TOOLS/NEUTRAL_EVIDENCE_TOOLS/role_tools` are bound nowhere and name a **nonexistent tool** `get_growth_metrics` (repo-wide: only that line). **[V]**
- `agents/researchers/structured_debate.py:605` reads `ds["independent_agreement"]`, which **nothing writes** (`independent_agreement` is computed as a local in `trading_graph.py:2208`) → the consensus-exit termination is dead; debates always run to the cap. **[V]**
- **EMA implemented three times, byte-identical** (`extended_indicators._ema`, `technical_factors._ema`, `value_dip._ema_series`) while the verifier pins EMA identities → drift risk. **[V]**
- `agents/utils/value_dip_tools.py:27-90` re-implements `_ohlcv`/`_load_ohlcv_df`/`_scale_note` without the run cache or the ascending-date normalization. **[V]**
- `agents/utils/structured.py:691-717` `retry_structured_missing_fields` has **no production caller** (tests only) → the documented per-field integrity retry never runs. **[V]**
- `graph/trading_graph.py:1317-1319` raises the `data_quality_failure` hard guard when the PM omits the optional `data_quality` (`or "unknown"`), while `schemas.py:39-51` coerces a *reported* `"unknown"` to `None` (so the documented confidence cap never applies) — the two halves contradict each other. **[V]**
- `schemas.L1Verdict`/`L1DeterministicResult` are a dead vocabulary (constructed only in tests); the pipeline emits `severity_tier`/`l1_action`. **[S]**
- `PortfolioDecision.risk_cap` is written by the guardrail and read by nothing. **[V]**
- 22 ToolNode entries no analyst binds (14 market, 5 fundamentals, 1 news, 2 social; the sentiment analyst binds no tools at all, so its ToolNode is unreachable) (the sentiment analyst binds no tools) — dead registry weight whose comment claims they are bound. **[V via drift scan]**
- Dead state channels: `security_type` is returned by the fundamentals node but is not an `AgentState` channel (LangGraph drops it); `sender` is written by the Trader and read nowhere. **[S]**
- Unreachable/duplicated leftovers: `eodhd.py:101` trailing `return None`; `report_verifier._internal_conflicts` `for…else: pass`; `debate_structured.repair_and_validate` "prime (unused)" call; `debate_structured.parse_markdown_fence` comment vs greedy regex (2 sites); `get_sec_filings` docstring documents `start_date/end_date` that are not in the signature; `_beat_streak_identity` word map stops at "six". **[S/V mixed]**
- Config/routing surface: `enable_market_routing` + `market_source_priority` are read by the router but absent from `DEFAULT_CONFIG` and from `_ENV_OVERRIDES` while **README.md:1407 / docs/api_reference.md:346 advertise them**; `resolve_market_priority` returns the configured names unfiltered (docstring promises skipping) so `VENDOR_METHODS[method][vendor]` raises an uncaught `KeyError`; `registry._PROVIDER_CREDENTIAL_KEYS` omits 5 key-gated vendors (tiingo, twelve_data, stockdata, newsapi, benzinga); `registry.method_requires_credentials` never passes a live config (reports everything missing); `default_config.validate_config` has no production caller. **[V for the first two, S for the rest]**
- `_run_signature` omits `enable_debate` (wrong-graph checkpoint resume); parallel merge drops `tool_evidence` (no `tool_evidence.json` when `analyst_concurrency>1`); `checkpointer.thread_id` collides for same-ticker+date concurrent runs; parallel subgraphs hardcode `recursion_limit=300` while the sequential path honours `max_recur_limit`; debate depth is `min(max_debate_rounds, debate_max_rounds)` so the larger knob is inert. **[S]**
- `interface.VENDOR_LIST` is stale relative to `VENDOR_METHODS` (no code reads it; tests/docs do). **[S]**

## 4. P3 — Test-quality defects (tests that cannot fail)

Highest-value, all **[V] or [S]** with quoted evidence:
- `tests/test_etf_mechanics.py` mocks `get_corporate_actions` with a **callable** mock — the mock supplies exactly the callability production lacks, hiding P0-2; and it asserts only `"Distributions:" in out`.
- `tests/test_risk_agent_wiring.py:262-266` accepts `"unavailable" in out or "verdict=" in out` — satisfied by P0-1's permanent failure.
- `tests/test_market_router.py:153-166` fabricates `get_vendor → "y_finance"` (a shape production never returns), green-lighting the always-`unknown` price-caliber path.
- Tautologies: `test_next_bar_fill.py:76` (`or True`), `test_scripts_config_gate.py` (`in (True, None, False)`), `test_sentiment_computed.py`, `test_sector_screen.py:225` and `test_alpha_zoo.py:62` (`is not None or is None`), `test_strategies_statistical.py:129-133`, `test_phase8_ops.py` (`assert True`).
- Source-text pins instead of behaviour: `test_reporting.py:342-356`, `test_moomoo_conn_cap.py` (`inspect.getsource` + wall-clock), `test_cli_no_console.py`, `test_graph_tool_loop.py`, `test_i18n_coverage.py`, `test_analysis_tools.py:2289`.
- Non-hermetic / state-mutating: `test_date_boundaries.py` (wall-clock), `test_evidence_gather.py` (timing bounds), `test_pipeline.py` (`os.chdir` global, dead `if False`, duplicate fixture).
- `test_debate_integration.py:399-402` wraps graph construction in `except Exception: pytest.skip`.
- `tests/test_calc_agent_wiring.py:120-130` reachability gate counts substrings over the whole tree (a comment satisfies it) and never validates advertised **signatures** (hence P0-4/§5 survive).
- `tests/test_structured_agents.py:112-121` pins the wrong `data_quality` contract (`"unknown"` → `None`).

## 5. P4 — Hygiene

- `ruff`: `B011` (`tests/test_calc_agent_wiring.py:316` `assert False`), `E741` (`tests/test_evidence_gather.py:436`), `E731` (`analysis_tools.py:3600` lambda assignment).
- `build/` is an ignored setuptools artifact (78 stale `.py` copies) — not tracked, no action beyond awareness.

---

## 6. Dismissed (checked, not defects)

- 112 "never imported" modules from the first regex pass — **false positives** (relative imports); the AST import graph found **0** truly dead modules.
- 43 "defined but never read" config keys, incl. `enable_value_dip`/`enable_regime`/`enable_factors` — all referenced in docs/tests; **0** verified dead.
- 7 "requests without timeout" — all pass `timeout=` on a later line.
- `moomoo cfg["host"]/["port"]/["autostart"]` KeyErrors — `_get_moomoo_config()` always populates them with defaults.
- `alpha_vantage_news.py:16 get_news(...)` "undefined/tool call" — a local `def get_news` at line 62.
- `get_indicators` / `get_prediction_markets` / `get_earnings_calendar` arity flags — defaults make the extra arg optional (only the 5 in P0-11 are real).
- `report_verifier` `_ema_identity`/`_ema_trail_identity`/`_garch_cond_identity` near-identical bodies — a deliberate per-indicator template, not duplication to merge.
- Documented best-effort `except …: pass` blocks with an in-repo rationale comment (config lookups, advisory folds).

---

## 7. Class-killers (do these first — each removes a whole family)

- **S1 — single source of truth for tool binding.** Derive each analyst's ToolNode from the analyst's bound list (one helper in `graph/trading_graph.py`), so P0-4 and the 22 orphan ToolNode entries cannot recur. Add a test asserting `bound_tools(analyst) == ToolNode(analyst).tools_by_name`.
- **S2 — extend the wiring gate.** `tests/test_calc_agent_wiring.py` currently only checks that a tool *name* appears in the prompt. Add the advertised-signature check (parse `` `tool(args)` `` out of the prompt, compare against the real signature) — this finds the 4 live mismatches today (`get_earnings_quality`, `get_options_iv_read`, `get_options_surface`, `get_merton_distance` in `market_analyst.py:318,322,386`) and prevents regressions.
- **S3 — ban `@tool` objects called as functions.** A ~30-line AST test (tool-decorated name invoked with `(` in the same package) — catches P0-1/P0-2 and any future occurrence.
- **S4 — vendor signature compatibility test.** For every `VENDOR_METHODS[method]`, assert each adapter accepts the arity the router passes (P0-11), and that every adapter raises a typed error rather than returning a placeholder (P1 moomoo/massive).
- **S5 — config contract test.** Every key read via `config.get/[]` is in `DEFAULT_CONFIG`; every `_ENV_OVERRIDES` target is in `DEFAULT_CONFIG`; `_coerce` never returns a raw string for a boolean target (P0-7). Add the two missing keys.
- **S6 — test-quality guard.** A meta-test that rejects `assert True`, `... or True`, `assert x in (True, None, False)`, `is not None or … is None`, and `inspect.getsource` pins in new/edited tests; delete the existing offenders in §4.

---

## 8. Implementation sequence

Each batch: fix → regression test that **fails before / passes after** → `ruff` → targeted suites → full suite → CHANGELOG → commit+push.

1. **Batch A (P0 tool/plumbing, ~8 files).** P0-1, P0-2, P0-3, P0-4 (+S1), P0-5, P0-6, P0-7 (+S5), P0-8. Tests: the 5 ETF tools execute on the ETF path; `get_regime_gate_read` returns `verdict=`; `get_etf_mechanics` renders a real distribution line; PM guardrail caps on a high-severity row; a failed `_ohlcv` is retried; `'false'` coerces to `False`; an unavailable decision is not `Hold`. Rewrite the two mock-hides-bug tests to drive the real path.
2. **Batch B (P0 numerics + verifier).** P0-9, P0-10, P0-11 (+S4), P0-12, P0-13, P0-14. Tests: `classify_security` returns `operating_company` for JPM/GS/MS/BLK/SCHW/NTRS/STT and `ETF` for SPY/IVV/IGV; `_match_row` returns `Sales`/`EBITDA`-free/standalone-liabilities; the 5 vendor methods route to a working adapter (or are removed); `volume_dry_up` baseline is 20 bars; `price_velocity_z` uses the trailing window; duration uses the fraction; the verifier catches `10-EMA = x` vs `10-EMA = y`.
3. **Batch C (P1 look-ahead/windows).** Vendor window threading (`finnhub` ×2, `stockdata` ×2, `moomoo` news), `datetime.now()` → as-of date, `bfill` ordering, `date_window` slack, status-before-body ordering ×4, `massive` `except` narrowing, moomoo placeholder → typed error, AV OVERVIEW numeric keys, `0.0` substitution, `expiries[-1]`, unreachable OUTSIDE branch, `detail=` fix, `None`-rendered-as-zero, assumed beta/cash/debt labelling, GAAP-basis note parity.
4. **Batch D (P2 dead code/duplication/drift).** Delete the shim + alias, phantom tool tuple, dead ToolNode entries (after S1), dead state channels, unreachable returns, "prime" call, `risk_cap`; unify EMA + `_ohlcv` + vendor key getters; wire or delete `retry_structured_missing_fields`; reconcile `data_quality`; L1 vocabulary; market-routing config (define the keys + fix `resolve_market_priority`); registry credential keys + cfg-aware `method_requires_credentials`; checkpoint signature/thread id; parallel merge of `tool_evidence`; `recursion_limit`; debate depth key; `validate_config` caller; `VENDOR_LIST`.
5. **Batch E (P3 tests + P4 hygiene).** Delete/replace the tautologies and source pins, fix `os.chdir`, remove the `pytest.skip` catch-all, re-pin `test_structured_agents`, add S2/S3/S6 gates, clear the 3 ruff nits.
6. **Batch F (verification).** Full suite + a live smoke run of one ETF ticker and one operating company (e.g. `IGV` and `JPM`) to prove the ETF toolset and the company path each execute end to end.

Dependencies: S1 before Batch D's ToolNode deletions; S4/S5 with Batch B; S2/S3/S6 with Batch E (S3 can land with Batch A).

## 9. Residual uncertainty

- Scout findings marked **[S]** are code-read with quoted evidence but not reproduced; each gets a reproduction step before its fix (the batches above name the assertion).
- `[S]` items I could not test live (vendor-key or OpenD dependent): moomoo ctx eviction, GDELT native-tone field, live Massive 429 behaviour, GDELT date-key join with real data.
- Not covered by this audit: `tradingagents/llm_clients/*` internals beyond config wiring, `trading_web/` (absent), and the ~10% of `analysis_tools.py`/`report_verifier.py` regions the scouts time-boxed (listed in their coverage notes).

---

## 10. Status (2026-09-10, after remediation)

Implemented in `892ade2` (A1/S1), `c82524c` (P0 + look-ahead + dead code + test hygiene) and the
part-2 commit (remaining contracts, routing config, honesty renders, test-quality gate).
Full suite at the end of remediation: **3638 passed, 0 failed** (start of audit: 3441 passed with
13 known failures plus the defects below). Live smoke on the fixed surfaces: `get_regime_gate_read`
returns a verdict (was "not callable"), `get_etf_mechanics` renders the vendor's corporate-actions
payload (was always `n/a`), `classify_security` returns ETF for IGV/SPY and UNKNOWN for JPM.

Class-killers landed: S1 single-source tool binding, S2 advertised-prompt-signature, S3
`@tool`-called-as-a-function, S4 vendor-signature, S5 config-contract, S6 test-quality gate.

### Deliberately left open (with the reason)

- **`TOOL_LEGACY_BINDING` (16 tools).** The audit's orphan-ToolNode entries are gone, but 16
  `@tool` functions no analyst binds remain defined and are declared in the gate's exemption map
  with their real consumers. Two have *no* consumer anywhere (`get_prompt_injection_read`,
  `get_thesis_evidence_matrix`): binding them needs prompt guidance (the prompts never mention
  them) and deleting them removes capability, so this is a product call, not a defect fix.
- **`security_type` is node-local.** The undeclared state channel was removed rather than
  declared, because nothing consumed it (LangGraph filtered it out anyway). If reporting should
  ever show "ETF run", declare the channel *and* consume it in the same change.
- **Not covered by the audit:** `llm_clients/*` internals beyond config wiring and the ~10% of
  `analysis_tools.py`/`report_verifier.py` the scouts time-boxed.
- **Scout findings marked `[S]` that were never reproduced** were fixed only where a batch owner
  could reproduce them; the vendored-SDK paths that need live credentials/OpenD (moomoo context
  eviction behaviour under real throttling, GDELT native tone, live Massive 429s) are covered by
  hermetic tests of the classification logic, not by a live vendor run.
