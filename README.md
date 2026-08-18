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
> ## Batch runner
>
> A headless, concurrent runner ships alongside the interactive CLI. Run several symbols at once, auto-save reports in the same layout the CLI produces, and get a machine-readable summary — no interactive prompts.
>
> ```bash
> python batch.py --symbols NVDA MSFT AAPL
> python batch.py --symbols NVDA MSFT AAPL 0700.HK --date 2026-07-22 --workers 4
> python batch.py --symbols NVDA --depth deep --analysts market news
> ```
>
> Options: `--symbols` (required), `--date` (default today), `--workers` (default 3), `--depth` (`shallow`/`medium`/`deep`, default `deep`), `--analysts` (default all four teams). Each symbol gets its own memory log (`~/.tradingagents/memory/<TICKER>.md`), reports land in `./reports/<TICKER>_<timestamp>/`, and a per-run summary is appended to `./reports/batch_summary_<timestamp>.jsonl`. Configuration (provider, models, API key) is inherited from `.env`.
>
> ## Extended data sources
>
> Beyond the core price, fundamental, and news vendors, TradingAgents can pull additional free, decision-relevant signals (all optional — a vendor failure degrades gracefully instead of aborting a run):
>
> - **Options market** (yfinance) — implied volatility, put/call open-interest and volume skew, surfaced to the market analyst.
> - **SEC EDGAR filings** — 8-K (material events), 10-K/10-Q (reports), S-1/S-3 (capital raises), SC 13D/G (stake disclosures), surfaced to the news analyst.
> - **Short interest / float** (yfinance) — days-to-cover, short % of float, ownership split, surfaced to the market analyst.
> - **Analyst ratings & price targets** (Finnhub) — recommendation trends and consensus targets, surfaced to the fundamentals analyst.
> - **Earnings calendar** (Finnhub) — upcoming earnings dates and EPS surprises, surfaced to the news analyst.
>
> Each source is a vendor behind the same `route_to_vendor` interface and is toggled per-category in `default_config.py` (`options_data`, `sec_filings`, `short_interest`, `analyst_ratings`, `earnings_calendar`). Set `finnhub_api_key` (or `TRADINGAGENTS_FINNHUB_API_KEY`) for the two Finnhub sources.
>
> ## Moomoo OpenAPI vendor
>
> Moomoo OpenAPI (formerly Futu OpenAPI) is available as an additional vendor behind the same `route_to_vendor` interface. It serves quotes/candlesticks, technical indicators, F10 financials, news, options chains, short interest, analyst consensus, the earnings calendar, and insider trades through the **local OpenD gateway** (TCP, default `127.0.0.1:11111`).
>
> - **No credentials in `.env`** — install OpenD, log in once with your (free) moomoo account and tick "remember password". The project only connects to the gateway.
> - **Headless autostart** — set `TRADINGAGENTS_MOOMOO_AUTOSTART=true` (default in `.env`) and `TRADINGAGENTS_MOOMOO_ACCOUNT=<your moomoo ID>` (not a password); the vendor launches OpenD with `-login_by_remember=1` when it is not running. `TRADINGAGENTS_MOOMOO_OPEND_PATH` overrides executable discovery. Note: OpenD is a local desktop gateway — inside Docker, moomoo simply degrades to the fallback vendors unless OpenD is reachable from the container.
> - **Analyst parallelism (opt-in)** — set `TRADINGAGENTS_ANALYST_CONCURRENCY=2` (or `analyst_concurrency` in config) to run the analyst teams concurrently, each in its own thread with isolated messages. Multiplies LLM/provider load and free-tier quota burn — start with 2, keep 1 (default) for rate-limited setups.
> - **Graceful fallback** — when OpenD is down, logged out, or lacks quote permission for a market, the router emits `DATA_UNAVAILABLE`/`NO_DATA_AVAILABLE` and falls back to the next configured vendor (yfinance, finnhub, …). Free quote rights cover US equities (LV3 promo), HK LV1, and crypto; A-shares and LSE/India are not covered for global accounts.
> - **Financial statements honor the tool contract** — `get_balance_sheet`, `get_cashflow`, and `get_income_statement` accept the same `freq` (`annual`/`quarterly`) and `curr_date` arguments as the yfinance and alpha_vantage vendors: `freq` selects the annual vs. quarterly report type on the moomoo SDK, and `curr_date` filters out statements published after the trading day (look-ahead guard). `get_fundamentals` accepts `curr_date` the same way.
> - Covered by default in `data_vendors` chains (`moomoo,yfinance` for prices/indicators/fundamentals/options/short-interest, `moomoo,finnhub` for ratings/earnings, `fred,moomoo` for macro). Prediction markets use `polymarket,moomoo` — Polymarket first, with moomoo's event contracts (category → series → event → contract → snapshot, live YES probabilities) as the fallback. Event contracts are server-gated to moomoo SG/MY accounts; other regions fall back to Polymarket automatically.
>
> **Decision-quality tiers** (all moomoo-only, optional, degrade to a `DATA_UNAVAILABLE` sentinel when OpenD is down or gated):
> - **Tier 1 — new evidence classes:** `get_capital_flow` (weekly net inflow by order size + session distribution → Market Analyst), `get_smart_money` (ARK institutional activity → Fundamentals), `get_economic_calendar` (dated CPI/FOMC/payroll catalysts → News), `get_fed_watch` (market-implied rate probabilities → News).
> - **Tier 2 — enrichment:** `get_market_breadth` (sector heat map + rise/fall distribution → News), `get_revenue_breakdown` (segment mix/concentration → Fundamentals), `get_corporate_actions` (dividends/splits → Fundamentals), `get_earnings_catalyst` (historical earnings implied move + IV crush → News, feeds catalyst-risk sizing).
> - **Tier 3 — accuracy infra:** the memory-log realized-return path uses moomoo's trading-day calendar for exact holding-day counting (falls back to the old calendar heuristic when OpenD is unreachable or the market is unsupported).
>
> The `batch.py` runner accepts a `--vendor moomoo|yfinance|default` flag to force a vendor-chain preset across all categories per run.
>
> ## Value watchlist screener
>
> `scripts/value_screener.py` builds a master watchlist *before* spending analyst LLM budget: it screens each symbol through the same `route_to_vendor` chain (`fundamental_data` defaults to `moomoo,yfinance`), translating vendor output (CSV/markdown/JSON/text) into canonical line items and computing the classic screens — **EV/EBIT (Acquirer's Multiple), Earnings Yield, Piotroski F-Score, Beneish M-Score, Altman Z-Score and net-net** (see [`strategies/value_strategy.md`](strategies/value_strategy.md) and `strategies/Math.md` for the playbook). Missing rows render `n/a`, never a fabricated number.
>
> The daily-changing universe can come from moomoo's intraday **top-movers"/"heat-proxy" rank** (领跌/领涨榜) — the biggest decliners at call time — so the watchlist rotates with the market:
>
> ```
> python scripts/value_screener.py -u heat-proxy -n 50 -d 2026-06-30
> ```
>
> `heat-proxy` is US-only (stocks only - ETFs/ETNs/funds/indices are excluded), takes the
> official hot master (gainers+losers, hottest first) and keeps the losers of the moment,
> then gates to **price ≥ $20, 0 < P/E (TTM) ≤ 40** (`--price-min 20`, `--pe-max 40`)
> and **market cap ≥ $100B** (`--min-mcap`, default; float cap NEVER exceeds total
> cap, so the total-cap floor covers the “cap or float cap ≥ $100B” rule) before
> the value screens run. It uses moomoo's official trade rank as the stand-in
> for the proprietary in-app **Heat List** (the composite Trade/Search/News
> telemetry isn't exposed by any moomoo API — the web endpoint is signed and
> undocumented). To use the literal app Heat List, save its top symbols to a
> file and pass `-f list.txt`. Output includes the day's change, name, and a
> screen-per-column table; pick from the ranked rows. Each run also saves
> the watchlist to `screener/<finish_timestamp>.md` (e.g. `screener/20260817_180415.md`,
> same `%Y%m%d_%H%M%S` format as reports; configurable via `--out-dir`).
> Requires OpenD running +
> logged in (same as every moomoo feature), and fails loudly if unavailable.

> Numeric hygiene: statements reported in a non-USD currency (JPY etc., e.g.
> many ADRs) are refused by the USD-only metrics (EV/EY/Acquirer/Z/net-net
> render `n/a` instead of mixing currencies), and the day's % change is
> normalized to a fraction regardless of the market session. `0` disables any gate.

> ## Decision quality
>
> The Portfolio Manager's structured output now captures the full risk-adjusted decision, not just a rating:
>
> - `confidence` (0–1) — conviction in the decision.
> - `position_size` — an explicit, risk-capped size that supersedes the trader's proposal.
> - `stop_loss` — a risk-derived stop level.
> - `consensus` (`high`/`low`) — a dissent flag when the aggressive/conservative/neutral analysts materially disagree.
>
> The decision log also feeds an aggregate track record back into the Portfolio Manager: on each same-ticker run it injects the historical directional win rate, mean realized return, and mean alpha, so future decisions weigh past accuracy.
>
> ## Operational hardening
>
> - **Thread-safe configuration** — `set_config`/`get_config` are thread-local, so concurrent batch workers never leak per-symbol overrides into each other.
> - **Vendor-result cache** — successful vendor fetches are cached on disk under a TTL (default 6 hours) to avoid re-burning free-tier API quotas; news is never cached, and failures are never cached.
> - **Vendor-served logging** — the routing layer logs which vendor answered each call, making free-tier quota burn visible.
> - **NaN-safe options chains** — yfinance option chains frequently carry missing/`NaN` open-interest, volume, and implied-volatility values; the options vendor skips non-finite values when summing (missing counts contribute 0) instead of crashing the call.
> - **Reddit rate limiting** — Reddit fetches are paced process-wide to avoid 429s, with a `TRADINGAGENTS_DISABLE_REDDIT=1` kill-switch for heavy batch days.

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
  from risk-DFV stances replaces the binary narrative flag; feeds G1.
- **G4 sentiment decay/velocity** (`strategies/sentiment.py`) - recency
  half-life weight, credibility factors, surprise z-score vs 30d baseline.
- **G5 threshold gate** (`scripts/evaluate_config_gate.py`) - walk-forward +
  PBO before tuning any new default (`enable_threshold_gate`).

Regression status: full suite passes (742 passed / 2 skipped / 56 subtests).

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
  catalyst-risk multipliers; `enable_events`.
- **P5 reflection** `reflection.py` - JSON-lines post-trade ledger, decayed
  analyst hit-rates, critique hints, ticker recall; `enable_reflection`.
- **Value-style hardening (V1-V5)** - `strategies/normalized.py` (5y
  median-margin normalized EBIT, historical percentiles, Sloan accruals,
  and a LOW/MED/HIGH trap verdict surfaced as the watchlist **Trap** column),
  `strategies/portfolio.py` (hard per-name/sector caps, residual cash),
  `strategies/exits.py` (stop-to-breakeven, ATR targets, rebalance cadence),
  `strategies/debate_context.py` (computed context snippets for the LLM debate).
  V2 wires value+momentum composite ranking into the screener
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

- **Graph wiring** (`enable_strategy_overlays`, `enable_reflection`): the graph
  attaches regime/sizing/momentum overlays to the final state and records
  realized outcomes to `strategy_ledger.jsonl` (**enabled by default**;
  disable via `enable_strategy_overlays: false` / `enable_reflection: false`;
  both are also settable through `.env` (see below).

Regression status: full suite passes (738 passed / 2 skipped / 56 subtests);
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
