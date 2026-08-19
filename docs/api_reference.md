# TradingAgents API Reference (fork)

Quick reference for the `tradingagents` package. Everything here is also
configured through `.env` via the `TRADINGAGENTS_*` overrides.

## 1. LLM providers

`llm_provider` selects the backend; `deep_think_llm` / `quick_think_llm` name
the models (deep = Research Manager + Portfolio Manager, quick = analysts,
researchers, debaters, reflector).

| Provider | Env key | Notes |
| --- | --- | --- |
| `openai` | `OPENAI_API_KEY` | Responses API, `reasoning_effort` |
| `google` | `GOOGLE_API_KEY` | `google_thinking_level` |
| `anthropic` | `ANTHROPIC_API_KEY` | `anthropic_effort` |
| `xai` · `deepseek` · `mistral` · `kimi` · `groq` · `nvidia` · `openrouter` | `XAI_/DEEPSEEK_/..._API_KEY` | OpenAI-compatible registry |
| `qwen` / `qwen-cn` | `DASHSCOPE_API_KEY` / `DASHSCOPE_CN_API_KEY` | intl / CN |
| `glm` / `glm-cn` | `ZHIPU_/ZHIPU_CN_API_KEY` | |
| `minimax` / `minimax-cn` | `MINIMAX_/MINIMAX_CN_API_KEY` | |
| `ollama` | `OLLAMA_BASE_URL` | keyless local |
| `openai_compatible` | `TRADINGAGENTS_LLM_BACKEND_URL` | vLLM / LM Studio / llama.cpp |
| `azure` / `bedrock` | see `.env.enterprise.example` / AWS creds | |

Cross-provider knobs: `temperature` (`TRADINGAGENTS_TEMPERATURE`),
`llm_max_retries` (`TRADINGAGENTS_LLM_MAX_RETRIES`),
`output_language` (`TRADINGAGENTS_OUTPUT_LANGUAGE`).

## 2. Graph flow

```
propagate(ticker, date, asset_type)
 └─ resolve pending memory-log entries (realised returns + reflections)
 └─ graph stream
    ├─ Analyst teams (market, sentiment, news, fundamentals)
    │    each: analyst LLM ⇄ ToolNode loop  (tools via route_to_vendor)
    ├─ Bull/Bear debate → Research Manager (structured ResearchPlan)
    ├─ Trader (structured TraderProposal)
    ├─ Aggressive/Conservative/Neutral debate
    ├─ Portfolio Manager (structured PortfolioDecision:
    │     rating, confidence, position_size, stop_loss, consensus) -> final
 ├─ _apply_strategy_overlays (compute, don't narrate)
 │    regime/position_scale → orderflow fold → catalyst fold
 │    → position contract (build_position_contract) → risk governor (risk_gate)
 ├─ memory log append (pending) + checkpoint clear
```

`analyst_concurrency` (`TRADINGAGENTS_ANALYST_CONCURRENCY`): `1` = sequential
(default); `>1` runs each analyst as an isolated sub-graph in its own thread
(opt-in; multiplies provider load).

## 3. Vendor data contract

Everything data flows through `route_to_vendor(method, *args)` in
`tradingagents/dataflows/interface.py`.

- **Categories → tools** (`TOOLS_CATEGORIES`): `core_stock_apis`,
  `technical_indicators`, `fundamental_data`, `news_data`, `macro_data`,
  `prediction_markets`, `analyst_ratings`, `earnings_calendar`, `options_data`,
  `sec_filings`, `short_interest`, plus moomoo enrichment: `capital_flow`,
  `smart_money`, `economic_calendar`, `fed_watch`, `market_breadth`,
  `revenue_breakdown`, `corporate_actions`, `earnings_catalyst`,
  `institution_data`, `earnings_surprise`, `expected_move`.
- **Vendor chain** (`VENDOR_METHODS` + `data_vendors` config): a category's
  chain is an ordered list ("moomoo,yfinance"). Only configured vendors serve;
  `none` disables a category; `default` = all available.
- **Error taxonomy** (`dataflows/errors.py`): `NoMarketDataError` (empty/stale),
  `VendorRateLimitError` (throttle), `VendorNotConfiguredError` (missing key /
  gateway down). Vendors raise these; the router falls through the chain and
  finally returns one of:
  `NO_DATA_AVAILABLE`, `DATA_UNAVAILABLE` (optional category), `DATA_DISABLED`.
- **Vendor cache**: disk-backed TTL (`vendor_cache_enabled`, 6h) skipping
  `news_data`; successful results only; sentinels never cached.
- **Moomoo** (`dataflows/moomoo.py`): quote-only via the local OpenD gateway
  (`moomoo_host`/`port`), credentials-free (one-time OpenD login,
  `TRADINGAGENTS_MOOMOO_AUTOSTART` with `-login_by_remember=1`),
  Yahoo→moomoo code mapping with fallback, typed errors, negative-probe TTL.

## 4. Strategy overlays (compute, don't narrate)

Config-gated deterministic layers applied in `_apply_strategy_overlays`:

| Layer | Flag | Module | Effect |
| --- | --- | --- | --- |
| Regime / size | `enable_strategy_overlays` | `strategies/regime.py`, `size.py` | vol/trend label, position_scale |
| Order flow | `enable_orderflow` | `strategies/orderflow.py` | distribution fold → scale |
| Position contract | `enable_position_contract` | `strategies/contract.py` | min(Kelly, risk/stop)×vol×flow×agree×catalyst |
| Risk governor | `enable_risk_governor` | `strategies/risk_governor.py` | PASS/WARN/REJECT + `risk_halt` |
| Catalyst (events) | `enable_events` **(on by default)** | `strategies/catalyst.py` | earnings/macro/Fed scale + verdict |
| Calibration | `enable_calibration` | `strategies/calibration.py` | calibrated P (ledger) |
| Agreement | `enable_agreement` | `strategies/consensus.py` | debate agreement → size |
| Computed context | `enable_computed_context` | `strategies/debate_context.py` | numbers into the debate |
| Screener | — | `scripts/value_screener.py` / `pipeline.py` | value screens, composite rank, cross-sectional batch |

## 5. Reporting

`write_report_tree(state, ticker, path)` writes:
`1_analysts/ 2_research/ 3_trading/ 4_risk/ 5_portfolio/ complete_report.md`.
`complete_report.md` has a strict hierarchy (H1 report → H2 team → H3 role →
H4+ agent content, agent headings auto-demoted) and an auto **Table of
Contents**. Re-render an existing folder without re-analysis:
`py scripts/rebuild_complete_report.py reports/<FOLDER>`.

## 6. Entry points

| Command | Purpose |
| --- | --- |
| `tradingagents` (CLI) | interactive analysis |
| `python batch.py --symbols ...` | headless concurrent, `--vendor moomoo|yfinance` |
| `python pipeline.py --universe top-losers --top 5` | screener → top-N → batch |
| `python scripts/value_screener.py ...` | watchlist screener alone |
| `python main.py` | minimal `propagate` demo |